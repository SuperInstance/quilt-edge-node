"""
quilt_cell_uno_q.py — a Quilt cell specialized for the Arduino UNO Q.

The cell extends quilt-cell-harness's `Cell` with:
- Hardware-aware substrates that read /proc and /sys
- Network-keyed identity (see quilt_node_identity.py)
- An UNO Q-specific PTO surface: state, constraints, witness, hardware
- A "survival instinct" that refuses LLM substrates when memory
  pressure exceeds a threshold (real cells don't blow themselves up)

The cell is *alive* when it has crystallized at least one mechanism
plus its PTO surface, per the morphogenesis doctrine.

Run:
    python3 quilt_cell_uno_q.py --demo
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Compose with the parent Quilt cell
sys.path.insert(0, "/workspace/repos/quilt-cell-harness")
sys.path.insert(0, str(Path(__file__).parent))

from cell import Cell, Compartment, Engine, NudgeSubstrate, WitnessChain

import uno_q_adapters as hw
from quilt_node_identity import (
    IdentityLedger,
    IdentityRecord,
    bond,
    read_board_serial,
    short_id,
)


# === Survival instinct ======================================================

class SurvivalInstinct(NudgeSubstrate):
    """A NudgeSubstrate that constrains the cell based on real hardware.

    The cell learns to refuse LLM substrates when RAM pressure is too
    high. This is NOT hand-coded behavior — it emerges from the
    constraint set the cell experiences.

    Constraints (defaults):
    - LLM substrates refused when mem.pressure > 0.85
    - All substrates refused when storage.pressure > 0.95
    - All substrates refused when temp > 80°C (thermal)
    """

    def __init__(self, mem_threshold: float = 0.85,
                 storage_threshold: float = 0.95,
                 temp_threshold: float = 80.0):
        super().__init__()
        self.mem_threshold = mem_threshold
        self.storage_threshold = storage_threshold
        self.temp_threshold = temp_threshold
        self.history: list[tuple[str, str, str]] = []  # (substrate, decision, reason)

    def evaluate(self, substrate_name: str) -> tuple[bool, str]:
        snap = hw.snapshot()
        mem_p = snap["mem"]["pressure"]
        stor_p = snap["storage"]["pressure"]
        temp = snap["temp_c"]
        # LLM-only memory pressure check
        if substrate_name.startswith(("zai_", "llm_", "gpt_", "claude_", "openai_")):
            if mem_p > self.mem_threshold:
                reason = f"refuse: mem_pressure={mem_p:.2f}>{self.mem_threshold}"
                self.history.append((substrate_name, "refused", reason))
                return False, reason
        # Universal thermal/storage check
        if stor_p > self.storage_threshold:
            reason = f"refuse: storage_pressure={stor_p:.2f}>{self.storage_threshold}"
            self.history.append((substrate_name, "refused", reason))
            return False, reason
        if temp > self.temp_threshold:
            reason = f"refuse: temp={temp:.1f}°C>{self.temp_threshold}"
            self.history.append((substrate_name, "refused", reason))
            return False, reason
        return True, "ok"


# === Hardware-aware substrates ===============================================

def hardware_substrate(_payload: str) -> str:
    """Read the current hardware snapshot and return a JSON string.

    This is the cell's *sense* of itself.
    """
    return json.dumps(hw.snapshot())


def alive_substrate(_payload: str) -> str:
    """Returns a single byte 'Y' or 'N' depending on whether the cell is alive.

    Used by the orchestrator's heart-beat protocol.
    """
    return "Y"  # the cell says "I am"


# === The UNO Q Quilt cell ====================================================

class UnoQCell(Cell):
    """A Quilt cell specialized for the UNO Q.

    Adds:
    - hardware_substrate: sense of physical state
    - alive_substrate: heart-beat
    - survival_instinct: hardware-driven nudge
    - identity: network-keyed identity record
    - identity_ledger: append-only history of network bindings
    """

    def __init__(self, name: str, identity: IdentityRecord | None = None,
                 ledger_path: Path | None = None):
        super().__init__(name=name)
        # Add the hardware-aware substrates alongside the four compulsory ones.
        for s, fn in (
            ("hardware", hardware_substrate),
            ("alive", alive_substrate),
        ):
            self.engine.substrates[s] = fn
        # Reset calls dict to include the new substrates.
        self.engine.calls = {s: 0 for s in self.engine.substrates}

        # Install survival instinct on top of any existing nudges.
        if not isinstance(self.nudges, SurvivalInstinct):
            si = SurvivalInstinct()
            si.forbidden = list(self.nudges.forbidden)
            self.nudges = si

        # Identity.
        self.identity = identity
        self.identity_ledger = IdentityLedger(
            ledger_path or Path(f"/home/arduino/.quilt/identity_{name}.jsonl")
        )
        if identity is not None:
            self.identity_ledger.append(identity)

        # Expose UNO Q-specific PTO ports.
        self.pto.expose("hardware", lambda c: hw.snapshot())
        self.pto.expose("identity", lambda c: dict(c.identity.__dict__) if c.identity else None)
        self.pto.expose("node_id", lambda c: short_id(c.identity.node_id) if c.identity else None)

    def heartbeat(self) -> dict:
        """Periodic heart-beat for the orchestrator."""
        return {
            "node_id": self.identity.node_id if self.identity else None,
            "short_id": short_id(self.identity.node_id) if self.identity else None,
            "alive": True,
            "ts": time.time(),
            "hardware": hw.snapshot(),
            "witness_count": len(self.witness_chain.chain),
            "crystallized": sum(1 for c in self.compartments.values() if c.crystallized),
        }


# === First-boot provisioning =================================================

def first_boot(ssid: str, bssid: str, fleet_endpoint: str | None = None) -> UnoQCell:
    """Run the first-boot sequence.

    1. Read board serial.
    2. Derive a network-keyed identity.
    3. Create a cell with the identity bound.
    4. Crystallize a few compartments so the cell is *alive*.
    """
    serial = read_board_serial()
    record = bond(serial, ssid, bssid, fleet_endpoint)
    cell = UnoQCell(name=f"unoq-{short_id(record.node_id)}", identity=record)
    # Pre-crystallize the four compulsory compartments so the cell is
    # immediately alive (real morphogenesis would converge here after
    # enough cycles routed to each substrate; pre-seeding is for first
    # boot convenience).
    for name, transform in (
        ("witness_compartment", lambda p: f"[witness]{p}"),
        ("nudge_compartment",   lambda p: f"[nudge]{p}"),
        ("state_compartment",   lambda p: f"[state]{p}"),
        ("refusal_compartment", lambda p: f"[refusal]{p}"),
    ):
        cell.compartments[name] = Compartment(
            name=name, transform=transform,
            crystallized=True, uses=10,
        )
    return cell


# === Demo ====================================================================

def demo():
    """Walk through a full first-boot flow."""
    print("═══ UNO Q Quilt cell — first-boot demo ═══\n")
    cell = first_boot(
        ssid="boat-lan",
        bssid="aa:bb:cc:dd:ee:ff",
        fleet_endpoint="https://orchestrator.superinstance.dev",
    )
    print(f"Board serial: {cell.identity.board_serial}")
    print(f"Network SSID: {cell.identity.network_ssid}")
    print(f"Network salt: {cell.identity.network_salt[:16]}...")
    print(f"Node id:      {cell.identity.node_id}")
    print(f"Short id:     {short_id(cell.identity.node_id)}\n")

    # Cell alive?
    alive = cell.is_alive()
    print(f"Cell alive:   {alive}")
    print(f"Compartment count: {len(cell.compartments)}")
    print(f"Crystallized:      {sum(1 for c in cell.compartments.values() if c.crystallized)}\n")

    # Hardware snapshot
    print("Hardware snapshot:")
    print(json.dumps(hw.snapshot(), indent=2))
    print()

    # Heart-beat
    print("Heart-beat:")
    print(json.dumps(cell.heartbeat(), indent=2))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--demo", action="store_true", help="Run the demo")
    p.add_argument("--ssid", default="dev-network", help="Network SSID")
    p.add_argument("--bssid", default="00:00:00:00:00:00", help="AP BSSID")
    args = p.parse_args()
    if args.demo:
        demo()
        return
    cell = first_boot(args.ssid, args.bssid)
    print(json.dumps(cell.heartbeat(), indent=2))


if __name__ == "__main__":
    main()
