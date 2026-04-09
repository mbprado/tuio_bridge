# TUIO Touch Bridge (Linux)

A lightweight TUIO → Linux input bridge that converts TUIO `/2Dcur`
messages into native Linux touch events using uinput. 
This project was initially planned as a replacement for Multitaction Cornerstone, but using TUIO instead.  

## Features

- Works with MultiTaction and other TUIO devices
- No proprietary runtime required (replacement for Cornerstone)
- Single-touch compatible (works on kernels without MT support)
- Native GNOME / Wayland support

## Requirements

- Linux
- Python 3
- evdev
- pyyaml
- uinput kernel module

## Installation

```bash
pip install -r requirements.txt
sudo python3 tuio_touch/bridge.py
``` 
## Command line options

--width
--height
--port
--debug
--config


## tuio_bridge project 

Reverse-engineered TUIO input
Built a custom OSC parser
Created a Linux input bridge

## Credits

This project was developed with assistance from ChatGPT (OpenAI),
which helped design the TUIO → Linux input bridge and debugging process.

Core implementation and integration by Murilo Borghi.
