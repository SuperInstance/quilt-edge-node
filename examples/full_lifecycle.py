"""
full_lifecycle.py — first-boot → heartbeat → defuse.

Walks the full lifecycle of an UNO Q Quilt cell:

  1. First-boot: read serial, derive identity, crystallize compartments.
  2. Heart-beat:  read hardware, show alive state, dump PTO surface.
  3. Use:         run a few energy flows through the cell.
  4. Witness:     print the witness chain.
  5. Identity:    print the network-keyed identity.
  6. Defuse:      reveal the cell's assembly (the witness + crystallization log).

Run:  python3 examples/full_lifecycle.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, "/workspace/repos/quilt-cell-harness")

from quilt_cell_uno_q import first_boot
from quilt_node_identity import short_id
from cell import Compartment


def banner(label: str):
    print()
    print("─" * 60)
    print(f"  {label}")
    print("─" * 60)


def main():
    banner("01 — first boot")
    cell = first_boot(ssid="boat-lan", bssid="aa:bb:cc:dd:ee:ff",
                      fleet_endpoint="https://orchestrator.superinstance.dev")
    print(f"  Node id:  {short_id(cell.identity.node_id)}")
    print(f"  Salt:     {cell.identity.network_salt[:16]}…")
    print(f"  Serial:   {cell.identity.board_serial}")

    banner("02 — heart-beat")
    beat = cell.heartbeat()
    print(f"  alive:           {beat['alive']}")
    print(f"  crystallized:    {beat['crystallized']}")
    print(f"  witness_count:   {beat['witness_count']}")
    print(f"  mem pressure:    {beat['hardware']['mem']['pressure']:.2f}")
    print(f"  storage used:    {beat['hardware']['storage']['used_gb']:.2f} GB")
    print(f"  uptime:          {beat['hardware']['uptime_s']:.0f}s")

    banner("03 — energy flows (cell is alive when energy moves)")
    flows = [
        ("echo:hello",        "echo",        "hello world"),
        ("sha256:hello",      "sha256",      "hello world"),
        ("reverse:hello",     "reverse",     "hello world"),
        ("hardware",          "hardware",    "sense"),
    ]
    for label, substrate, payload in flows:
        result = cell.engine.substrates[substrate](payload)
        cell.witness_chain.append({"event": "flow", "substrate": substrate, "out": str(result)[:40]})
        print(f"  {label:18s} → {str(result)[:40]}")

    banner("04 — witness chain")
    for i, ev in enumerate(cell.witness_chain.chain[-5:], 1):
        print(f"  [{i}] {json.dumps(ev)[:70]}")

    banner("05 — network-keyed identity")
    print(f"  Network SSID: {cell.identity.network_ssid}")
    print(f"  Network BSSID: {cell.identity.network_bssid}")
    print(f"  Network salt: {cell.identity.network_salt[:24]}…")
    print(f"  Node id:      {cell.identity.node_id}")
    print(f"  Fleet:        {cell.identity.fleet_endpoint}")

    banner("06 — defuse (reveal the cell's assembly)")
    alive, why = cell.is_alive()
    print(f"  is_alive: {bool(alive)}")
    print(f"  compartments: {len(cell.compartments)}")
    print(f"  crystallized: {sum(1 for c in cell.compartments.values() if c.crystallized)}")
    print(f"  substrates:   {sorted(cell.engine.substrates.keys())}")
    print(f"  PTO ports:    {sorted(cell.pto.ports.keys())}")

    banner("done")
    print("  Cell is alive. Network-keyed. Ready to be a Quilt node.")
    print()


if __name__ == "__main__":
    main()
