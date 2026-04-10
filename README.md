# TUIO Touch Bridge (Linux)

A lightweight TUIO → Linux input bridge that converts TUIO `/2Dcur`
messages into native Linux touch events using uinput. 
This project was initially planned as a replacement for Multitaction Cornerstone, but using TUIO instead.  

## Features

- Works with MultiTaction and other TUIO devices
- No proprietary runtime required (replacement for Cornerstone)
- No need to deal with python-osc
- Single-touch compatible (works on kernels without MT support)
- Native GNOME / Wayland support

## Requirements

- Linux
- Python 3
- evdev
- pyyaml
- uinput kernel module

## Installation

Install and test:
```bash
pip install -r requirements.txt
sudo python3 tuio_touch/bridge.py
``` 

Install service:
```bash
sudo ./setup.sh
```

## Command line options

`--width`: Screen width
`--height`: Screen width
`--port`: TUIO UDP port
`--debug`: Enable debug logs 
`--config`: Define configuration file


## tuio_bridge project 

Reverse-engineered TUIO input
Built a custom OSC parser
Created a Linux input bridge

## Credits

This project was developed with assistance from ChatGPT (OpenAI),
which helped design the TUIO → Linux input bridge and debugging process.

Core implementation and integration by Murilo Borghi.
