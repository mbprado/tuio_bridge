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
from evdev import UInput, AbsInfo, ecodes as e

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
# MAIN LOOP
# -------------------
while True:
    data, addr = sock.recvfrom(65536)

    if data.startswith(b"#bundle"):
        parse_bundle(data)
    else:
        parse_message(data, 0)
