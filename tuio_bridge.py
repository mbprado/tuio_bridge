"""
TUIO → Linux Touch Bridge

Author: Murilo Borghi Prado
Assisted by: our beloved ChatGPT (OpenAI)

Implements a minimal OSC parser and uinput bridge
to convert TUIO (MultiTaction) events into Linux touch input.
"""

#!/usr/bin/env python3
import socket
import struct
import logging
import argparse
import yaml
import os
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
# CONFIG
# -------------------
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
PORT = 3333

logging.basicConfig(level=logging.INFO)

# -------------------
# UINPUT SETUP
# -------------------
capabilities = {
    e.EV_KEY: [e.BTN_TOUCH],
    e.EV_ABS: [
        (e.ABS_X, AbsInfo(0, 0, SCREEN_WIDTH, 0, 0, 0)),
        (e.ABS_Y, AbsInfo(0, 0, SCREEN_HEIGHT, 0, 0, 0)),
    ],
}

ui = UInput(capabilities, name="TUIO Touchscreen", bustype=e.BUS_USB)
logging.info("uinput device created")

# -------------------
# TUIO STATE
# -------------------
active_ids = []
positions = {}
touch_down = False

# -------------------
# SOCKET
# -------------------
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("", PORT))

logging.info(f"Listening on UDP {PORT}...")

# -------------------
# OSC HELPERS
# -------------------
def read_string(data, offset):
    end = data.find(b'\x00', offset)
    s = data[offset:end].decode(errors="ignore")
    next_offset = (end + 4) & ~0x03
    return s, next_offset

def read_int(data, offset):
    return struct.unpack(">i", data[offset:offset+4])[0], offset+4

def read_float(data, offset):
    return struct.unpack(">f", data[offset:offset+4])[0], offset+4

# -------------------
# MAIN PARSER
# -------------------
def parse_message(data, offset):
    global active_ids, positions, touch_down

    addr, offset = read_string(data, offset)
    types, offset = read_string(data, offset)

    if not types.startswith(","):
        return offset

    args = []
    for t in types[1:]:
        if t == "i":
            val, offset = read_int(data, offset)
        elif t == "f":
            val, offset = read_float(data, offset)
        elif t == "s":
            val, offset = read_string(data, offset)
        else:
            break
        args.append(val)

    if addr == "/tuio/2Dcur":
        cmd = args[0]

        if cmd == "alive":
            active_ids = args[1:]

        elif cmd == "set":
            sid = args[1]
            x = args[2]
            y = args[3]
            positions[sid] = (x, y)

        elif cmd == "fseq":
            # FRAME SYNC → update touch
            if active_ids:
                sid = active_ids[0]

                if sid in positions:
                    x, y = positions[sid]

                    px = int(x * SCREEN_WIDTH)
                    py = int(y * SCREEN_HEIGHT)

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
    offset = 16  # skip #bundle header

    while offset < len(data):
        size, offset = read_int(data, offset)
        message_end = offset + size
        parse_message(data, offset)
        offset = message_end

# -------------------
# PARSER
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
# MAIN LOOP
# -------------------
def main():
    args = parse_args()
    cfg = load_config(args.config)

    # --- Resolve configuration ---
    width = args.width or cfg.get("screen", {}).get("width", 1920)
    height = args.height or cfg.get("screen", {}).get("height", 1080)
    port = args.port or cfg.get("network", {}).get("port", 3333)
    debug = args.debug or cfg.get("debug", False)

    if debug:
        logging.getLogger().setLevel(logging.DEBUG)

    logging.info(f"Screen: {width}x{height}")
    logging.info(f"Port: {port}")

    # --- UINPUT ---
    capabilities = {
        e.EV_KEY: [e.BTN_TOUCH],
        e.EV_ABS: [
            (e.ABS_X, AbsInfo(0, 0, width, 0, 0, 0)),
            (e.ABS_Y, AbsInfo(0, 0, height, 0, 0, 0)),
        ],
    }

    ui = UInput(capabilities, name="TUIO Touchscreen", bustype=e.BUS_USB)

    active_ids = []
    positions = {}
    touch_down = False

    # --- socket ---
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", port))

    logging.info(f"Listening on UDP {port}...")

    # --- override globals inside parser ---
    def parse_message_local(data, offset):
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

        if addr == "/tuio/2Dcur":
            cmd = args_list[0]

            if cmd == "alive":
                active_ids = args_list[1:]

            elif cmd == "set":
                sid = args_list[1]
                positions[sid] = (args_list[2], args_list[3])

                if debug:
                    logging.debug(f"SET id={sid} x={args_list[2]:.3f} y={args_list[3]:.3f}")

            elif cmd == "fseq":
                if active_ids:
                    sid = active_ids[0]
                    if sid in positions:
                        x, y = positions[sid]

                        px = int(x * width)
                        py = int(y * height)

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

    def parse_bundle_local(data):
        offset = 16
        while offset < len(data):
            size, offset = read_int(data, offset)
            parse_message_local(data, offset)
            offset += size

    # --- main loop ---
    while True:
        data, _ = sock.recvfrom(65536)

        if data.startswith(b"#bundle"):
            parse_bundle_local(data)
        else:
            parse_message_local(data, 0)
