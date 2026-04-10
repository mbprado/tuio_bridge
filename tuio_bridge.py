#!/usr/bin/env python3
"""
TUIO → Linux Touch Bridge

Author: Murilo Borghi Prado
Assisted by: ChatGPT (OpenAI)

Minimal OSC parser + uinput bridge (single-touch version)
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

# -------------------
# LOADER
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
    next_offset = (end + 4) & ~0x03
    return s, next_offset

def read_int(data, offset):
    if offset + 4 > len(data):
        return 0, len(data)
    return struct.unpack(">i", data[offset:offset+4])[0], offset + 4

def read_float(data, offset):
    if offset + 4 > len(data):
        return 0.0, len(data)
    return struct.unpack(">f", data[offset:offset+4])[0], offset + 4

# -------------------
# ARGUMENTS
# -------------------
def parse_args():
    parser = argparse.ArgumentParser(description="TUIO Touch Bridge")

    parser.add_argument("--config", help="Path to config file")
    parser.add_argument("--width", type=int, help="Screen width")
    parser.add_argument("--height", type=int, help="Screen height")
    parser.add_argument("--port", type=int, help="UDP port (default 3333)")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")

    return parser.parse_args()

# -------------------
# MAIN
# -------------------
def main():
    args = parse_args()
    cfg = load_config(args.config)

    # --- Resolve config ---
    width = args.width or cfg.get("screen", {}).get("width", 1920)
    height = args.height or cfg.get("screen", {}).get("height", 1080)
    port = args.port or cfg.get("network", {}).get("port", 3333)
    debug = args.debug or cfg.get("debug", False)

    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)

    logging.info(f"Screen: {width}x{height}")
    logging.info(f"Port: {port}")

    # --- UINPUT ---
    capabilities = {
        e.EV_KEY: [e.BTN_TOUCH],
        e.EV_ABS: [
            (e.ABS_X, AbsInfo(0, 0, width - 1, 0, 0, 0)),
            (e.ABS_Y, AbsInfo(0, 0, height - 1, 0, 0, 0)),
        ],
    }

    ui = UInput(capabilities, name="TUIO Touchscreen", bustype=e.BUS_USB)
    logging.info("uinput device created")

    # --- State ---
    active_ids = []
    positions = {}
    touch_down = False

    # --- Cleanup handler ---
    def cleanup(*_):
        logging.info("Shutting down, releasing touch...")
        try:
            ui.write(e.EV_KEY, e.BTN_TOUCH, 0)
            ui.syn()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # --- Socket ---
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", port))
    sock.settimeout(1.0)

    logging.info(f"Listening on UDP {port}...")

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

        if addr != "/tuio/2Dcur":
            return offset

        if not args_list:
            return offset

        cmd = args_list[0]

        # --- ALIVE ---
        if cmd == "alive":
            active_ids = args_list[1:]

        # --- SET ---
        elif cmd == "set" and len(args_list) >= 4:
            sid = args_list[1]
            x = args_list[2]
            y = args_list[3]

            positions[sid] = (x, y)

            if debug:
                logging.debug(f"SET id={sid} x={x:.3f} y={y:.3f}")

        # --- FSEQ (frame sync) ---
        elif cmd == "fseq":
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

        return offset

    def parse_bundle(data):
        offset = 16  # skip "#bundle" + timetag

        while offset < len(data):
            size, offset = read_int(data, offset)
            message_end = offset + size

            parse_message(data, offset)

            offset = message_end

    # -------------------
    # MAIN LOOP
    # -------------------
    while True:
        try:
            data, _ = sock.recvfrom(65536)
        except socket.timeout:
            continue
        except Exception as ex:
            logging.error(f"Socket error: {ex}")
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
