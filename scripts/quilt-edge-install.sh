#!/usr/bin/env bash
# quilt-edge-install.sh — install the Quilt edge node on an UNO Q.
#
# Idempotent: re-running just refreshes the install.
# Run over ADB: adb push install.sh /tmp/ && adb shell bash /tmp/install.sh
set -euo pipefail

echo "==> Installing Quilt edge node on $(hostname)"

# === System packages =========================================================
echo "==> apt packages"
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip python3-websockets \
    avahi-daemon avahi-utils

# === Quilt directory =========================================================
echo "==> Quilt directories"
sudo mkdir -p /opt/quilt-edge-node
sudo mkdir -p /home/arduino/.quilt
sudo chown -R arduino:arduino /opt/quilt-edge-node /home/arduino/.quilt

# === Copy source =============================================================
echo "==> Copying source from /tmp/quilt-edge-node to /opt/quilt-edge-node"
sudo cp -r /tmp/quilt-edge-node/* /opt/quilt-edge-node/
sudo chown -R arduino:arduino /opt/quilt-edge-node

# === Python deps ============================================================
echo "==> Python dependencies"
pip3 install --quiet --break-system-packages \
    "websockets>=11" || true

# === systemd unit ============================================================
echo "==> systemd unit"
sudo tee /etc/systemd/system/quilt-edge-pto.service >/dev/null <<'UNIT'
[Unit]
Description=Quilt edge node — PTO server
After=network-online.target avahi-daemon.service
Wants=network-online.target

[Service]
Type=simple
User=arduino
ExecStart=/usr/bin/python3 /opt/quilt-edge-node/src/quilt_pto_server.py
Restart=on-failure
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable --now quilt-edge-pto.service

# === mDNS announcement =======================================================
echo "==> mDNS service"
sudo tee /etc/avahi/services/quilt-edge-node.service >/dev/null <<'AVAHI'
<?xml version="1.0" standalone='no'?>
<!DOCTYPE service-group SYSTEM "avahi-service.dtd">
<service-group>
  <name replace-wildcards="yes">Quilt edge node (%h)</name>
  <service>
    <type>_quilt-edge._tcp</type>
    <port>7681</port>
  </service>
</service-group>
AVAHI
sudo systemctl restart avahi-daemon

# === Done ====================================================================
echo
echo "✓ Quilt edge node installed."
echo "  PTO server:    ws://$(hostname).local:7681"
echo "  Identity file: /home/arduino/.quilt/identity_$(hostname).jsonl"
echo
echo "Try:"
echo "  websocat ws://$(hostname).local:7681 <<<'{\"op\":\"heartbeat\"}'"
