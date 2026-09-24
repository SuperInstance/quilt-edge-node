"""
uno_q_adapters.py — read hardware state from the UNO Q's Linux sysfs/procfs.

These are read-only adapters that surface chip state to the Quilt cell.
The cell uses these to make substrate-routing decisions (e.g. "if RAM
pressure > 0.85, refuse LLM substrates" — a real survival instinct).

The adapters degrade gracefully: if a path is missing (e.g. running
in CI), the call returns a sentinel value rather than raising.
"""
from __future__ import annotations

import os
import re
from pathlib import Path


# === RAM / memory pressure ====================================================

def read_meminfo() -> dict:
    """Parse /proc/meminfo into a dict.

    Returns keys: total_kb, available_kb, used_kb, pressure (0..1).
    """
    info = {"total_kb": 0, "available_kb": 0, "used_kb": 0, "pressure": 0.0}
    try:
        text = Path("/proc/meminfo").read_text()
    except FileNotFoundError:
        return info
    for line in text.splitlines():
        key, _, rest = line.partition(":")
        value_kb = int(re.findall(r"\d+", rest)[0])
        if key == "MemTotal":
            info["total_kb"] = value_kb
        elif key == "MemAvailable":
            info["available_kb"] = value_kb
    if info["total_kb"]:
        info["used_kb"] = info["total_kb"] - info["available_kb"]
        info["pressure"] = info["used_kb"] / info["total_kb"]
    return info


# === CPU usage (sampled delta) ===============================================

def read_cpu_times() -> dict:
    """Snapshot of /proc/stat 'cpu' line.

    Call read_cpu_times() at t0, again at t1, then call cpu_usage(t0, t1)
    to get the utilization ratio over that window.
    """
    try:
        line = Path("/proc/stat").read_text().splitlines()[0]
    except (FileNotFoundError, IndexError):
        return {}
    parts = line.split()
    return {"parts": [int(x) for x in parts[1:]]}  # user,nice,system,idle,iowait,irq,softirq,steal


def cpu_usage(t0: dict, t1: dict) -> float:
    """Compute CPU utilization over (t0, t1) snapshots."""
    if not t0 or not t1:
        return 0.0
    p0, p1 = t0["parts"], t1["parts"]
    total0, total1 = sum(p0), sum(p1)
    idle0 = p0[3] if len(p0) > 3 else 0
    idle1 = p1[3] if len(p1) > 3 else 0
    d_total = total1 - total0
    d_idle = idle1 - idle0
    if d_total <= 0:
        return 0.0
    return 1.0 - (d_idle / d_total)


# === Temperature =============================================================

def read_cpu_temp_c() -> float:
    """Read SoC temperature (°C) from the QRB2210 thermal zone.

    The path varies by kernel version; we search /sys/class/thermal for
    anything tagged 'cpu' or 'soc'.
    """
    thermal = Path("/sys/class/thermal")
    if not thermal.exists():
        return 0.0
    candidates = []
    for zone in thermal.glob("thermal_zone*"):
        try:
            t = (zone / "type").read_text().strip().lower()
            if any(tag in t for tag in ("cpu", "soc", "tsens", "mpu")):
                candidates.append(zone)
        except (FileNotFoundError, PermissionError):
            continue
    # Prefer the highest-temperature reading if multiple.
    temps = []
    for zone in candidates or thermal.glob("thermal_zone*"):
        try:
            millic = int((zone / "temp").read_text().strip())
            temps.append(millic / 1000.0)
        except (FileNotFoundError, PermissionError, ValueError):
            continue
    return max(temps) if temps else 0.0


# === eMMC storage ============================================================

def read_storage() -> dict:
    """Stat the eMMC mount. UNO Q ships with a rootfs on /dev/mmcblk0."""
    try:
        st = os.statvfs("/")
    except OSError:
        return {"total_gb": 0.0, "used_gb": 0.0, "free_gb": 0.0, "pressure": 0.0}
    total = st.f_blocks * st.f_frsize
    free = st.f_bavail * st.f_frsize
    used = total - free
    return {
        "total_gb": total / (1024 ** 3),
        "used_gb": used / (1024 ** 3),
        "free_gb": free / (1024 ** 3),
        "pressure": used / total if total else 0.0,
    }


# === Uptime + load ===========================================================

def read_uptime() -> dict:
    """Read /proc/uptime + /proc/loadavg."""
    try:
        with open("/proc/uptime") as f:
            up = float(f.read().split()[0])
    except (FileNotFoundError, ValueError, IndexError):
        up = 0.0
    try:
        with open("/proc/loadavg") as f:
            parts = f.read().split()
            load1, load5, load15 = float(parts[0]), float(parts[1]), float(parts[2])
    except (FileNotFoundError, ValueError, IndexError, OSError):
        load1 = load5 = load15 = 0.0
    return {"uptime_s": up, "load1": load1, "load5": load5, "load15": load15}


# === Composite: full hardware snapshot ======================================

def snapshot() -> dict:
    """One-call read of all the hardware state.

    This is the "physical substrate" view that the Quilt cell observes.
    """
    return {
        "mem": read_meminfo(),
        "temp_c": read_cpu_temp_c(),
        "storage": read_storage(),
        **read_uptime(),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(snapshot(), indent=2))
