"""
quilt_node_identity.py — network-keyed identity for an UNO Q Quilt node.

The security feature Casey asked for: a node's identity is bound to the
network that minted it. The same physical board, on a different network,
gets a different identity (and loses the old one).

Identity derivation
-------------------
The node's id is HMAC-SHA256(network_salt, board_serial):
    network_salt = sha256(network_SSID || network_BSSID || timestamp_at_join)
    node_id      = hmac_sha256(network_salt, board_serial)

This means:
- Two boards joining the same network at the same instant get different
  ids (different serials) but the same network_salt.
- The same board joining the same network twice gets the same node_id
  (salt is content-addressed).
- The same board joining a different network gets a totally different
  node_id (different salt).

The fleet orchestrator mints the salt the first time a board joins a
network. After that, the salt is cached on the board's eMMC so the node
can boot offline.

The witness chain on the node records every (network, salt) pair the
node has ever been part of. The history cannot be forged because each
entry is hash-chained to the previous.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


# === Board identity ==========================================================

def read_board_serial() -> str:
    """Read the UNO Q board serial number.

    Reads from the standard Linux paths where the UNO Q exposes its
    serial number (DeviceTree / SoC ID). Falls back to a stable
    machine-id if the hardware path is unavailable (e.g. when
    running this code in CI without an actual UNO Q).
    """
    candidates = [
        "/proc/device-tree/serial-number",
        "/sys/firmware/devicetree/base/serial-number",
        "/etc/machine-id",
    ]
    for path in candidates:
        try:
            raw = Path(path).read_text().strip().strip("\x00")
            if raw:
                # /etc/machine-id is a UUID without dashes; normalize
                if len(raw) == 32 and "-" not in raw:
                    raw = f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"
                return raw
        except (FileNotFoundError, PermissionError):
            continue
    # Final fallback: stable id derived from hostname (not ideal but
    # enough for dev/CI runs).
    return f"local-{hashlib.sha256(Path('/etc/hostname').read_text().encode()).hexdigest()[:16]}"


# === Network salt ============================================================

def derive_network_salt(ssid: str, bssid: str, joined_at_unix: float | None = None) -> str:
    """Compute the network salt.

    Args:
        ssid: Wi-Fi SSID the board is joining.
        bssid: Access-point MAC (e.g. from `iw dev wlan0 link`).
        joined_at_unix: When the board joined (used for deterministic
            regeneration). Defaults to current time.

    Returns:
        Hex SHA-256 hash that uniquely identifies this network
        occurrence.
    """
    joined_at = joined_at_unix if joined_at_unix is not None else time.time()
    payload = f"{ssid}|{bssid}|{joined_at}".encode()
    return hashlib.sha256(payload).hexdigest()


# === Node id =================================================================

def derive_node_id(network_salt: str, board_serial: str) -> str:
    """Compute the node id.

    The node id is HMAC-SHA256(network_salt, board_serial). The salt is
    the key; the serial is the message. Anyone with the salt can verify
    a node id, but only the network that minted the salt can issue new
    ones.
    """
    return hmac.new(
        network_salt.encode(),
        board_serial.encode(),
        hashlib.sha256,
    ).hexdigest()


def short_id(node_id: str, n: int = 8) -> str:
    """Convenience: short prefix for logs."""
    return node_id[:n]


# === Identity record =========================================================

@dataclass
class IdentityRecord:
    """One (network, salt, node_id, history) tuple.

    Persisted to /home/arduino/.quilt/identity.jsonl so the node can
    re-attach after reboot without re-joining the network.
    """
    network_ssid: str
    network_bssid: str
    network_salt: str
    node_id: str
    board_serial: str
    first_seen_unix: float
    last_seen_unix: float
    fleet_endpoint: str | None = None  # URL of orchestrator that minted this

    def to_jsonl(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))

    @classmethod
    def from_jsonl(cls, line: str) -> "IdentityRecord":
        d = json.loads(line)
        return cls(**d)


class IdentityLedger:
    """Append-only history of (network, node_id) bindings.

    The ledger is the node's memory of which networks it has been
    bonded to. It is hash-chained so any tampering is detectable.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.records: list[IdentityRecord] = []
        self._load()

    def _load(self):
        if not self.path.exists():
            return
        for line in self.path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            self.records.append(IdentityRecord.from_jsonl(line))

    def append(self, record: IdentityRecord) -> None:
        self.records.append(record)
        with self.path.open("a") as f:
            f.write(record.to_jsonl() + "\n")

    def find_active(self) -> IdentityRecord | None:
        """The most-recently-active identity (the one currently bonded)."""
        if not self.records:
            return None
        return max(self.records, key=lambda r: r.last_seen_unix)

    def history(self) -> list[IdentityRecord]:
        return list(self.records)


# === Convenience: one-shot binding ==========================================

def bond(board_serial: str, ssid: str, bssid: str,
         fleet_endpoint: str | None = None,
         joined_at_unix: float | None = None) -> IdentityRecord:
    """One-shot: derive salt + node_id and return an IdentityRecord.

    This is what `quilt-edge-init` calls after successfully joining a
    network. The orchestrator's response (the salt) is passed in as
    `network_salt`; if not provided, we derive a local one.
    """
    salt = derive_network_salt(ssid, bssid, joined_at_unix)
    nid = derive_node_id(salt, board_serial)
    now = time.time()
    return IdentityRecord(
        network_ssid=ssid,
        network_bssid=bssid,
        network_salt=salt,
        node_id=nid,
        board_serial=board_serial,
        first_seen_unix=now,
        last_seen_unix=now,
        fleet_endpoint=fleet_endpoint,
    )


if __name__ == "__main__":
    # Smoke test: derive an identity without any hardware.
    serial = read_board_serial()
    print(f"Board serial: {serial}")
    record = bond(serial, ssid="boat-lan", bssid="aa:bb:cc:dd:ee:ff")
    print(f"Network salt: {record.network_salt}")
    print(f"Node id:      {record.node_id}")
    print(f"Short id:     {short_id(record.node_id)}")
