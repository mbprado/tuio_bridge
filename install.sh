#!/bin/bash
if [ "$EUID" -eq 0 ]; then
    echo "Running as root"
else
    echo "Not running as root"
    exit 255
fi

mkdir -p /opt/tuio_bridge
cp tuio_bridge.py /opt/tuio_bridge.py
cp systemd/tuio_bridge.service /etc/systemd/system/

systemctl daemon-reexec
systemctl enable tuio-touch
systemctl start tuio-touch
