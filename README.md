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
Manual installation (Clone repository or Download ZIP)

```bash
git clone https://github.com/mbprado/tuio_bridge.git
```

Run and test:
```bash
pip install -r requirements.txt
sudo python3 tuio_bridge.py
``` 

Install service:
```bash
sudo ./install.sh
```

## Command line options

`--width`: Screen width  
`--height`: Screen width  
`--port`: TUIO UDP port  
`--debug`: Enable debug logs  
`--config`: Define configuration file  
`--mode`: Touch screen mode: single or multi  
`--slots`: Numer of simultaneous touchs. Multi-mode only  

## Troubleshooting

### Touch is not working at all:
#### Check connectivity between TUIO device and host. The default TUIO port is **3333**. 
You can change the port in the configuration file: `/etc/tuio-bridge.yaml`
```bash
ping <TUIO_DEVICE_IP>
```

#### Check for packages being received on host from TUIO device.
```bash
sudo tcpdump -i any udp port 3333
```
you must see a series of control packages coming from the TUIO device.  
ie: `16:45:32.350741 enp0s25 In  IP 192.168.137.145.42442 > 192.168.137.1.3333: UDP, length 7`

#### Check tuio-bridge service
```bash
sudo systemctl status tuio-bridge
```
Active: active (running)

```bash
sudo $ sudo netstat -pltnu 3333 | grep ":3333"
```
udp        0      0 0.0.0.0:3333            0.0.0.0:*                           1438/python3

#### Run tuio-bridge using `--debug` option.
```bash
sudo systemctl stop tuio-bridge
/usr/bin/tuio-bridge --debug
```
touch the screen and you must see touch coordinates

### Touch is working but missplaced.

#### Check if the resolution is properly set on config file. Default is 1920x1080
You can change the resolution in the configuration file: `/etc/tuio-bridge.yaml`

## About tuio_bridge project 

Reverse-engineered TUIO input  
Built a custom OSC parser  
Created a Linux input bridge

## To do 

Multi touch support for gestures on Gnome (in progress)  
deb package / installation script (in progress)  
Touch calibration help  

## Credits

This project was developed with assistance from ChatGPT (OpenAI),
which helped design the TUIO → Linux input bridge and debugging process.

Core implementation and integration by Murilo Borghi.
