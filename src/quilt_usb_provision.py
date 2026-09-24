"""
quilt_usb_provision.py — provision a freshly-unboxed UNO Q via USB-C.

Plug-and-play flow:
1. Operator connects UNO Q to their computer via USB-C.
2. Operator runs `python3 quilt_usb_provision.py` on the computer.
3. This script uses ADB to push the Quilt node program + identity.
4. On first power-on, the UNO Q auto-joins the operator's network.
5. The board mints a network-keyed identity.

The script is idempotent: re-running on an already-provisioned board
just refreshes the identity (e.g. after the operator changed Wi-Fi).

Requires: `adb` on PATH (sudo apt install android-sdk-platform-tools).
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_SRC = Path(__file__).parent
INSTALL_DEST = Path("/home/arduino/quilt-edge-node")


# === ADB helpers =============================================================

def adb(*args: str, timeout: int = 60) -> tuple[int, str, str]:
    """Run an adb command. Returns (rc, stdout, stderr)."""
    cmd = ["adb", *args]
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return cp.returncode, cp.stdout, cp.stderr
    except FileNotFoundError:
        print("ERROR: adb not found. Run: sudo apt install android-sdk-platform-tools",
              file=sys.stderr)
        sys.exit(2)
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


def adb_devices() -> list[str]:
    rc, out, _ = adb("devices")
    if rc != 0:
        return []
    # Lines like: "0123abc device"  Skip header.
    return [line.split()[0] for line in out.splitlines()
            if line.strip() and not line.startswith("List") and "device" in line]


def adb_wait(timeout_s: int = 90) -> str | None:
    """Wait for an UNO Q to appear. Returns its serial or None."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        devs = adb_devices()
        if devs:
            return devs[0]
        time.sleep(2)
    return None


def adb_shell(serial: str, cmd: str, timeout: int = 30) -> tuple[int, str, str]:
    return adb("-s", serial, "shell", cmd, timeout=timeout)


# === Provisioning steps =====================================================

def push_payload(serial: str, local: Path, remote: str) -> bool:
    rc, out, err = adb("-s", serial, "push", str(local), remote)
    if rc != 0:
        print(f"push {local} failed: {err}", file=sys.stderr)
        return False
    return True


def provision(serial: str, ssid: str, password: str,
              bundle: Path = REPO_SRC.parent) -> bool:
    """Push the Quilt node bundle to the UNO Q and run first-boot."""
    print(f"Provisioning UNO Q {serial}...")
    print(f"  SSID:  {ssid}")
    print(f"  Bundle: {bundle}")

    # 1. Configure Wi-Fi (via nmcli).
    rc, out, err = adb_shell(
        serial,
        f"sudo nmcli dev wifi connect '{ssid}' password '{password}'",
        timeout=60,
    )
    if rc != 0:
        print(f"wifi connect failed: {err}", file=sys.stderr)
        return False

    # 2. Get BSSID + IP for the joined network.
    rc, out, _ = adb_shell(serial, "iw dev wlan0 link", timeout=15)
    bssid = "00:00:00:00:00:00"
    for line in out.splitlines():
        if "bssid" in line.lower():
            bssid = line.split()[-1]
            break

    # 3. Push the bundle.
    remote_tmp = "/tmp/quilt-edge-node"
    adb_shell(serial, f"mkdir -p {remote_tmp}")
    files_to_push = [
        REPO_SRC / "quilt_node_identity.py",
        REPO_SRC / "quilt_cell_uno_q.py",
        REPO_SRC / "uno_q_adapters.py",
        REPO_SRC / "quilt_pto_server.py",
    ]
    for f in files_to_push:
        if not f.exists():
            print(f"WARNING: missing {f}", file=sys.stderr)
            continue
        if not push_payload(serial, f, remote_tmp + "/"):
            return False

    # 4. Install via quilt-edge-install.sh (if present).
    installer = REPO_SRC.parent / "scripts" / "quilt-edge-install.sh"
    if installer.exists():
        adb_shell(serial, f"cat > /tmp/install.sh", timeout=10)
        # Actually push the installer file:
        push_payload(serial, installer, remote_tmp + "/install.sh")
        adb_shell(serial, f"bash {remote_tmp}/install.sh", timeout=120)

    # 5. Run first-boot.
    rc, out, err = adb_shell(
        serial,
        f"python3 {remote_tmp}/quilt_cell_uno_q.py --ssid {ssid} --bssid {bssid}",
        timeout=30,
    )
    if rc != 0:
        print(f"first-boot failed: {err}", file=sys.stderr)
        print(out)
        return False
    print(out)
    print(f"\n✓ Provisioned {serial}. Identity bound to network '{ssid}'.")
    return True


# === CLI ====================================================================

def main():
    p = argparse.ArgumentParser(description="Provision UNO Q via USB-C")
    p.add_argument("--ssid", required=True, help="Wi-Fi SSID")
    p.add_argument("--password", required=True, help="Wi-Fi password")
    p.add_argument("--serial", default=None,
                   help="ADB serial (default: first device found)")
    p.add_argument("--timeout", type=int, default=90,
                   help="Seconds to wait for the board")
    args = p.parse_args()

    if not shutil.which("adb"):
        print("ERROR: adb not on PATH. Try: sudo apt install android-sdk-platform-tools",
              file=sys.stderr)
        sys.exit(2)

    serial = args.serial or adb_wait(args.timeout)
    if not serial:
        print(f"No UNO Q appeared in {args.timeout}s. Check USB-C and ADB.",
              file=sys.stderr)
        sys.exit(1)
    ok = provision(serial, args.ssid, args.password)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
