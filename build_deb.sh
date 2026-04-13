set -e

APP_NAME="tuio-bridge"
VERSION="${VERSION:-1.01}"

BUILD_DIR="$(mktemp -d)"
PKG_DIR="$BUILD_DIR/${APP_NAME}_${VERSION}"

echo "[*] Building package in $BUILD_DIR"

# -------------------------
# Create structure
# -------------------------
mkdir -p "$PKG_DIR/DEBIAN"
mkdir -p "$PKG_DIR/usr/bin"
mkdir -p "$PKG_DIR/etc"
mkdir -p "$PKG_DIR/lib/systemd/system"
mkdir -p "$PKG_DIR/etc/udev/rules.d"

# -------------------------
# Copy main script
# -------------------------
install -m 0755 tuio_touch.py "$PKG_DIR/usr/bin/$APP_NAME"

# -------------------------
# Default config (optional)
# -------------------------
if [ -f config.yaml ]; then
    cp config.yaml "$PKG_DIR/etc/${APP_NAME}.yaml"
fi

# -------------------------
# systemd service
# -------------------------
cat > "$PKG_DIR/lib/systemd/system/${APP_NAME}.service" <<EOF
[Unit]
Description=TUIO Bridge (TUIO → Linux Touch)
After=network.target

[Service]
ExecStart=/usr/bin/${APP_NAME} --config /etc/${APP_NAME}.yaml
Restart=always
User=root

[Install]
WantedBy=multi-user.target
EOF

# -------------------------
# udev rule
# -------------------------
cat > "$PKG_DIR/etc/udev/rules.d/99-${APP_NAME}.rules" <<EOF
KERNEL=="uinput", MODE="0660", GROUP="input"
EOF

# -------------------------
# control file
# -------------------------
cat > "$PKG_DIR/DEBIAN/control" <<EOF
Package: ${APP_NAME}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: all
Depends: python3, python3-evdev, python3-yaml
Maintainer: Murilo Borghi Prado
Description: TUIO to Linux touch bridge
 Converts TUIO events into Linux multitouch input using uinput.
EOF

# -------------------------
# conffiles (preserve config)
# -------------------------
if [ -f config.yaml ]; then
cat > "$PKG_DIR/DEBIAN/conffiles" <<EOF
/etc/${APP_NAME}.yaml
EOF
fi

# -------------------------
# postinst
# -------------------------
cat > "$PKG_DIR/DEBIAN/postinst" <<EOF
#!/bin/sh
set -e

systemctl daemon-reload || true
udevadm control --reload-rules || true

echo "Installed ${APP_NAME}"
echo "Run: systemctl enable --now ${APP_NAME}"

exit 0
EOF

chmod +x "$PKG_DIR/DEBIAN/postinst"

# -------------------------
# prerm
# -------------------------
cat > "$PKG_DIR/DEBIAN/prerm" <<EOF
#!/bin/sh
systemctl stop ${APP_NAME} || true
exit 0
EOF

chmod +x "$PKG_DIR/DEBIAN/prerm"

# -------------------------
# Build package
# -------------------------
OUTPUT="${APP_NAME}_${VERSION}_all.deb"

dpkg-deb --build "$PKG_DIR" "$OUTPUT"

echo "[+] Package created: $OUTPUT"

# -------------------------
# Cleanup
# -------------------------
rm -rf "$BUILD_DIR"

echo "[*] Cleaned up"
