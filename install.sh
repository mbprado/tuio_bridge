#!/usr/bin/env bash
set -e
if [ "$EUID" -eq 0 ]; then
    echo "Running as root..."
else
    echo "Not running as root..."
    exit 255
fi

APP_NAME="tuio-bridge"
INSTALL_PATH="/usr/local/bin/$APP_NAME"
CONFIG_PATH="/etc/tuio-bridge.yaml"

echo "[*] Installing dependencies..."
if command -v apt >/dev/null; then
	    apt update
	        apt install -y python3 python3-pip python3-evdev python3-yaml
	elif command -v dnf >/dev/null; then
		    dnf install -y python3 python3-pip python3-evdev python3-PyYAML
fi

echo "[*] Installing app..."
install -m 0755 tuio_bridge.py "$INSTALL_PATH"

echo "[*] Installing config..."
mkdir -p /etc
cp -n config.yaml "$CONFIG_PATH" || true

echo "[*] Creating systemd service..."

cat > /etc/systemd/system/tuio-bridge.service <<EOF
[Unit]
Description=TUIO Touch Bridge
After=network.target

[Service]
ExecStart=$INSTALL_PATH --config $CONFIG_PATH
Restart=always
User=root

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reexec
systemctl daemon-reload
systemctl start tuio-bridge

echo "[*] Done!"
echo "Run: systemctl enable --now tuio-touch"

