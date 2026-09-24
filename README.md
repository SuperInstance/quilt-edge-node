# quilt-edge-node

> **Plug-and-play Quilt cell on the Arduino UNO Q.**
> Upload program → board joins your network → becomes a productive node.

```
┌─────────────────────────────────────────────────────────────────────┐
│              Arduino UNO Q  (Qualcomm QRB2210 + STM32U585)            │
│                                                                       │
│  ┌───────────────────────────────────────────────────────────────┐   │
│  │                    Quilt cell  (Debian 13 arm64)               │   │
│  │                                                                  │   │
│  │   ┌─────────┐    ┌─────────┐    ┌──────────┐    ┌──────────┐ │   │
│  │   │ engine  │───▶│ witness │───▶│identity  │───▶│  PTO     │ │   │
│  │   │         │    │  chain  │    │ (network │    │  server  │ │   │
│  │   │ subs:   │    │         │    │   keyed) │    │   :7681  │ │   │
│  │   │  echo   │    └─────────┘    └──────────┘    └──────────┘ │   │
│  │   │  rev    │                                                   │   │
│  │   │  sha256 │    ┌──────────────┐    ┌───────────────┐        │   │
│  │   │  stub   │───▶│  hardware    │───▶│  survival     │        │   │
│  │   │  hw     │    │  adapter     │    │  instinct     │        │   │
│  │   │  alive  │    │ (proc/sysfs) │    │  (RAM/temp)   │        │   │
│  │   └─────────┘    └──────────────┘    └───────────────┘        │   │
│  │                                                                  │   │
│  └───────────────────────────────────────────────────────────────┘   │
│                                  │                                      │
│              Wi-Fi 5 + BT 5.1   │  USB-C 3.1                           │
│              (WCBN3536A)        │  (ADB / power / video)              │
└──────────────────────────────────┼──────────────────────────────────────┘
                                   │
                          mDNS _quilt-edge._tcp
                                   │
                                   ▼
                       fleet orchestrator (LAN)
```

## What it does

A single Python program that turns any UNO Q into a **Quilt cell**:

- **Plug-and-play.** Connect USB-C. Run `quilt_usb_provision.py`. Board
  joins the network. Done.
- **Network-keyed identity.** Each node's id is
  `HMAC-SHA256(network_salt, board_serial)`. The salt is minted by the
  fleet orchestrator the first time the board joins a network. The
  same board on a different network → different identity.
- **Survival instinct.** Cell reads `/proc/meminfo`, `/sys/class/thermal`,
  `statvfs` and refuses LLM substrates when memory pressure exceeds
  85% (or storage > 95%, or temp > 80°C). No hand-coded behavior — just
  constraints the cell has to live with.
- **PTO server.** Exposes the cell over WebSocket on port 7681. Other
  nodes, the orchestrator, or a voice agent can read state / witness /
  hardware / identity.

## Hardware target

Arduino **UNO Q 4GB** (ABX00173):
- Qualcomm Dragonwing QRB2210 — 4× Cortex-A53 @ 2.0 GHz, 64-bit
- Adreno 702 GPU @ 845 MHz
- STM32U585 Cortex-M33 @ 160 MHz (real-time MCU, runs Zephyr)
- 4 GB LPDDR4X RAM
- 32 GB eMMC
- Wi-Fi 5 dual-band + BT 5.1
- Debian 13 (Trixie), arm64
- USB-C 3.1 with PD

The 2 GB / 16 GB variant works too but you have ~3 GB less headroom for
LLM substrates.

## Install

```bash
# On the UNO Q (after App Lab first-boot):
sudo apt install -y python3-pip python3-websockets
pip3 install --break-system-packages websockets
git clone https://github.com/SuperInstance/quilt-edge-node
cd quilt-edge-node
sudo bash scripts/quilt-edge-install.sh
```

Or, plug the UNO Q into your computer and:

```bash
# On your computer:
pip install websockets   # only needed for the PTO client
python3 src/quilt_usb_provision.py --ssid MyNetwork --password MyPassword
```

## Try

```bash
# Heart-beat the cell:
websocat ws://unoq-XXXXXXXX.local:7681 <<<'{"op":"heartbeat"}' | jq

# List available PTO ports:
websocat ws://unoq-XXXXXXXX.local:7681 <<<'{"op":"list"}'

# Read hardware:
websocat ws://unoq-XXXXXXXX.local:7681 <<<'{"op":"call","port":"hardware"}'

# Read identity:
websocat ws://unoq-XXXXXXXX.local:7681 <<<'{"op":"call","port":"identity"}'
```

## Files

- `src/quilt_node_identity.py` — network-keyed identity
- `src/quilt_cell_uno_q.py` — UNO Q Quilt cell + survival instinct
- `src/uno_q_adapters.py` — /proc and /sys readers
- `src/quilt_pto_server.py` — WebSocket PTO server
- `src/quilt_usb_provision.py` — plug-and-play USB-C provisioner
- `scripts/quilt-edge-install.sh` — systemd installer
- `examples/full_lifecycle.py` — first-boot → heartbeat → defuse
- `tests/test_node_identity.py` — identity determinism tests
- `DESIGN.md` — architecture and design rationale
- `INSTALL.md` — detailed install + troubleshooting

## Doctrines

This repo demonstrates:

1. **Cell = engine + compartments.** Not LLM-with-stuff. The LLM is one
   substrate among many.
2. **Plug-and-play is real.** USB-C → Wi-Fi → identity in under 60 s.
3. **Network-keyed identity.** A node's id is bound to the network that
   minted it. The board can never impersonate a node on another network.
4. **Survival instinct emerges from constraints.** Don't hand-code
   refusal. Constrain the cell and let refusal emerge.
5. **PTO is a port, not a path.** Read state, witness, hardware,
   identity the same way you would read a database row.
