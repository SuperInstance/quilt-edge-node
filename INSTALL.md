# INSTALL — quilt-edge-node

## On the UNO Q (after first-boot with Arduino App Lab)

```bash
# SSH in: ssh arduino@unoq-XXXX.local
# The board has been through App Lab first-boot, Wi-Fi is set,
# SSH is enabled.

sudo apt update
sudo apt install -y python3-pip python3-websockets avahi-daemon
pip3 install --break-system-packages websockets

# Pull this repo:
git clone https://github.com/SuperInstance/quilt-edge-node
cd quilt-edge-node

# Run the installer (idempotent):
sudo bash scripts/quilt-edge-install.sh
```

This:
- Installs system packages (websockets, avahi)
- Creates `/opt/quilt-edge-node` and `/home/arduino/.quilt`
- Installs a systemd unit (`quilt-edge-pto.service`)
- Advertises the cell over mDNS as `_quilt-edge._tcp` on port 7681
- Starts the cell

## Verify

```bash
# On any computer on the same network:
websocat ws://unoq-XXXXXXXX.local:7681 <<<'{"op":"heartbeat"}' | jq
```

You should see a JSON dump with `alive: true`, hardware snapshot,
and the network-keyed identity.

## Plug-and-play (alternative to manual install)

```bash
# On your computer, plug the UNO Q via USB-C, then:
pip install websockets
python3 src/quilt_usb_provision.py \
    --ssid MyNetwork \
    --password MyPassword
```

This:
1. Waits for the UNO Q to appear over ADB
2. Joins the Wi-Fi network via nmcli
3. Pushes the Quilt node bundle via `adb push`
4. Runs the first-boot sequence
5. Starts the cell

## Troubleshooting

### `adb devices` shows nothing

- USB-C cable must be data-capable (charge-only cables don't work).
- On Linux, you may need udev rules. Run the App Lab post-install:
  `sudo ./post_install.sh`
- On macOS, install: `brew install android-platform-tools`
- On Windows: `winget install Google.PlatformTools`

### SSH doesn't connect

- Make sure your computer and the UNO Q are on the same network.
- After App Lab first-boot, the board's name is shown in the App Lab
  status bar. Use that name: `ssh arduino@<name>.local`
- Forgot the password? Reset via App Lab or ADB shell.

### WebSocket connection refused

- The cell starts on port 7681. If something else is on that port,
  change it: `--port 7682` in the systemd unit.
- Firewall? `sudo ufw allow 7681/tcp`

### High memory pressure / cell refuses LLM substrates

- Check the cell's heartbeat: `{"op":"hardware"}` shows current usage.
- The cell refuses LLM substrates when mem.pressure > 0.85. This is
  by design. To run an LLM, lower other memory usage first.

## Multiple boards

Just plug another UNO Q into your computer and re-run
`quilt_usb_provision.py`. Each board gets its own identity (because
its serial number is different) and joins the same network. The
orchestrator (or your mDNS browser) will see them all.
