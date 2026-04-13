#!/usr/bin/env python3
"""
TUIO → Linux Touch Bridge (Single + Multi-touch Type B)

Author: Murilo Borghi Prado
"""

import socket
import struct
import logging
import argparse
import yaml
import os
import signal
import sys
from evdev import UInput, AbsInfo, ecodes as e

VERSION = "1.02"
# -------------------
# CONFIG LOADER
# -------------------
def load_config(path):
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}

# -------------------
# OSC HELPERS
# -------------------
def read_string(data, offset):
    end = data.find(b'\x00', offset)
    if end == -1:
        return "", len(data)
    s = data[offset:end].decode(errors="ignore")
    return s, (end + 4) & ~0x03

def read_int(data, offset):
    if offset + 4 > len(data):
        return 0, len(data)
    return struct.unpack(">i", data[offset:offset+4])[0], offset + 4

def read_float(data, offset):
    if offset + 4 > len(data):
        return 0.0, len(data)
    return struct.unpack(">f", data[offset:offset+4])[0], offset + 4

# -------------------
# CLI
# -------------------
def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config")
    p.add_argument("--width", type=int)
    p.add_argument("--height", type=int)
    p.add_argument("--port", type=int)
    p.add_argument("--debug", action="store_true")
    p.add_argument("--single", action="store_true", help="Force single-touch mode")
    p.add_argument("--slots", type=int, help="Max multitouch slots")
    p.add_argument("--version", action="version", version=f"tuio_bridge {VERSION}")
    return p.parse_args()

# -------------------
# MAIN
# -------------------
def main():
    args = parse_args()
    cfg = load_config(args.config)

    width = args.width or cfg.get("screen", {}).get("width", 1920)
    height = args.height or cfg.get("screen", {}).get("height", 1080)
    port = args.port or cfg.get("network", {}).get("port", 3333)
    debug = args.debug or cfg.get("debug", False)
    MAX_SLOTS = args.slots or cfg.get("input", {}).get("slots", 10)
    mode = "single" if args.single else cfg.get("input", {}).get("mode", "multi")

    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)

    logging.info(f"Mode: {mode}")
    logging.info(f"Screen: {width}x{height}")
    logging.info(f"Port: {port}")

    # -------------------
    # UINPUT SETUP
    # -------------------
    if mode == "single":
        capabilities = {
            e.EV_KEY: [e.BTN_TOUCH],
            e.EV_ABS: [
                (e.ABS_X, AbsInfo(0, 0, width - 1, 0, 0, 0)),
                (e.ABS_Y, AbsInfo(0, 0, height - 1, 0, 0, 0)),
            ],
        }
    else:
        capabilities = {
            e.EV_KEY: [e.BTN_TOUCH],
            e.EV_ABS: [
                (e.ABS_MT_SLOT, AbsInfo(0, 0, MAX_SLOTS - 1, 0, 0, 0)),
                (e.ABS_MT_TRACKING_ID, AbsInfo(0, 0, 65535, 0, 0, 0)),
                (e.ABS_MT_POSITION_X, AbsInfo(0, 0, width - 1, 0, 0, 0)),
                (e.ABS_MT_POSITION_Y, AbsInfo(0, 0, height - 1, 0, 0, 0)),
            ],
        }

    ui = UInput(capabilities, name="TUIO Touchscreen", bustype=e.BUS_USB)
    logging.info("uinput device created")

    # -------------------
    # STATE
    # -------------------
    active_ids = []
    positions = {}
    touch_down = False

    # multitouch
    slot_map = {}      # sid → slot
    used_slots = set()

    def get_slot(sid):
        if sid in slot_map:
            return slot_map[sid]

        for i in range(MAX_SLOTS):
            if i not in used_slots:
                slot_map[sid] = i
                used_slots.add(i)
                return i

        return None  # no slots available

    def release_slot(sid):
        if sid in slot_map:
            used_slots.discard(slot_map[sid])
            del slot_map[sid]

    # -------------------
    # CLEANUP
    # -------------------
    def cleanup(*_):
        logging.info("Shutting down")
        try:
            ui.write(e.EV_KEY, e.BTN_TOUCH, 0)
            ui.syn()
        except:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # -------------------
    # SOCKET
    # -------------------
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", port))
    sock.settimeout(1.0)

    # -------------------
    # PARSER
    # -------------------
    def parse_message(data, offset):
        nonlocal active_ids, positions, touch_down

        addr, offset = read_string(data, offset)
        types, offset = read_string(data, offset)

        if not types.startswith(","):
            return offset

        args_list = []
        for t in types[1:]:
            if t == "i":
                val, offset = read_int(data, offset)
            elif t == "f":
                val, offset = read_float(data, offset)
            elif t == "s":
                val, offset = read_string(data, offset)
            else:
                break
            args_list.append(val)

        if addr != "/tuio/2Dcur" or not args_list:
            return offset

        cmd = args_list[0]

        # -------------------
        # ALIVE
        # -------------------
        if cmd == "alive":
            new_ids = args_list[1:]

            if mode == "multi":
                # release removed fingers
                for sid in list(slot_map.keys()):
                    if sid not in new_ids:
                        slot = slot_map[sid]
                        ui.write(e.EV_ABS, e.ABS_MT_SLOT, slot)
                        ui.write(e.EV_ABS, e.ABS_MT_TRACKING_ID, -1)
                        release_slot(sid)

            active_ids[:] = new_ids

        # -------------------
        # SET
        # -------------------
        elif cmd == "set" and len(args_list) >= 4:
            sid = args_list[1]
            x = args_list[2]
            y = args_list[3]

            positions[sid] = (x, y)

            if debug:
                logging.debug(f"SET {sid} {x:.3f},{y:.3f}")

        # -------------------
        # FSEQ
        # -------------------
        elif cmd == "fseq":
            if mode == "single":
                if active_ids:
                    sid = active_ids[0]
                    if sid in positions:
                        x, y = positions[sid]

                        px = min(width - 1, max(0, int(x * width)))
                        py = min(height - 1, max(0, int(y * height)))

                        ui.write(e.EV_ABS, e.ABS_X, px)
                        ui.write(e.EV_ABS, e.ABS_Y, py)

                        if not touch_down:
                            ui.write(e.EV_KEY, e.BTN_TOUCH, 1)
                            touch_down = True

                        ui.syn()
                else:
                    if touch_down:
                        ui.write(e.EV_KEY, e.BTN_TOUCH, 0)
                        ui.syn()
                        touch_down = False

            else:
                # multitouch
                for sid in active_ids:
                    if sid not in positions:
                        continue

                    slot = get_slot(sid)
                    if slot is None:
                        continue

                    x, y = positions[sid]

                    px = min(width - 1, max(0, int(x * width)))
                    py = min(height - 1, max(0, int(y * height)))

                    ui.write(e.EV_ABS, e.ABS_MT_SLOT, slot)
                    ui.write(e.EV_ABS, e.ABS_MT_TRACKING_ID, sid)
                    ui.write(e.EV_ABS, e.ABS_MT_POSITION_X, px)
                    ui.write(e.EV_ABS, e.ABS_MT_POSITION_Y, py)

                # global touch state
                ui.write(e.EV_KEY, e.BTN_TOUCH, 1 if active_ids else 0)
                ui.syn()

        return offset

    def parse_bundle(data):
        offset = 16
        while offset < len(data):
            size, offset = read_int(data, offset)
            end = offset + size
            parse_message(data, offset)
            offset = end

    # -------------------
    # LOOP
    # -------------------
    while True:
        try:
            data, _ = sock.recvfrom(65536)
        except socket.timeout:
            continue
        except Exception as ex:
            logging.error(ex)
            continue

        try:
            if data.startswith(b"#bundle"):
                parse_bundle(data)
            else:
                parse_message(data, 0)
        except Exception as ex:
            logging.error(f"Parse error: {ex}")


if __name__ == "__main__":
    main()
