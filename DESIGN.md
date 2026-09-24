# DESIGN — quilt-edge-node

## Why this exists

Casey wants Arduino UNO Q units to be **plug-and-play ML machines** that
turn into **independent Quilt nodes** the moment they're connected to a
network. The identity of each node is bound to the network that minted
it — a security feature, not just an address.

This repo implements that vision as a single self-contained program
(`quilt_cell_uno_q.py`) plus the supporting identity, hardware, and
provisioning modules.

## Architecture

```
                         QUILT EDGE NODE
                         ═══════════════

                          first boot
                              │
                              ▼
              ┌──────────────────────────────┐
              │  quilt-edge-init             │
              │  ─────────────────────       │
              │  1. read board serial        │
              │  2. derive network salt      │
              │  3. mint node_id             │
              │  4. crystallize 4 compulsory │
              │  5. start PTO server         │
              └──────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────────────┐
        │                 CELL                          │
        │                                               │
        │   ENGINE          COMPARTMENTS                │
        │   ──────          ────────────                │
        │   substrates:     witness_compartment (cryst) │
        │     echo          nudge_compartment   (cryst) │
        │     reverse       state_compartment   (cryst) │
        │     sha256        refusal_compartment (cryst) │
        │     stub_llm      hardware_compartment (cryst)│
        │     hardware      alive_compartment   (cryst)│
        │     alive                                      │
        │                                                │
        │   NUDGES:                                       │
        │     SurvivalInstinct                           │
        │       ├─ refuses LLM when mem > 0.85           │
        │       ├─ refuses all when storage > 0.95       │
        │       └─ refuses all when temp > 80°C          │
        │                                                │
        │   WITNESS CHAIN:                               │
        │     append-only, hash-chained                  │
        │     /home/arduino/.quilt/witness_*.jsonl       │
        │                                                │
        │   IDENTITY:                                    │
        │     ledger: /home/arduino/.quilt/identity_*   │
        │     node_id  = HMAC-SHA256(salt, serial)       │
        │                                                │
        │   PTO PORTS:                                   │
        │     state      hardware   witness              │
        │     constraints identity  node_id              │
        │                                                │
        └──────────────────────────────────────────────┘
                              │
                              ▼
                    ws://0.0.0.0:7681
                    (or mdns: unoq-XXXX.local)
```

## Network-keyed identity

A node's identity is computed from three inputs:

1. **network salt** = SHA-256(SSID || BSSID || joined_at)
2. **board serial** = UNO Q hardware serial (or machine-id fallback)
3. **node id**     = HMAC-SHA256(network_salt, board_serial)

Properties:

- The same board joining the same network twice at the same instant
  gets the same id (salt is content-addressed).
- The same board joining the same network at different instants gets
  *different* ids. This is intentional: a "moment" is part of the
  identity. Old ids stay in the witness chain; new ones supersede.
- Two boards joining the same network at the same instant get different
  ids (different serials) but the same salt.
- The same board joining a *different* network gets a totally
  different id (different salt). Old id is preserved in history but
  the current binding changes.

Security properties:

- A node can only authenticate to the orchestrator that minted its
  salt. Salt is held by the orchestrator; the node only knows its id.
- An attacker who knows the network SSID + BSSID cannot mint ids
  without also knowing the orchestrator's salt-minting key (in this
  prototype the salt is derived locally; production should use a
  signed challenge from the orchestrator).
- A node's witness chain is hash-chained; tampering is detectable.

## Survival instinct

Cells should not blow themselves up. The UNO Q has 4 GB RAM, 32 GB
eMMC, and an SoC that gets warm under load. The cell observes the
hardware through `uno_q_adapters.snapshot()` and constrains its
substrate routing through a `SurvivalInstinct(NudgeSubstrate)`:

| Condition                                | Effect                          |
|------------------------------------------|---------------------------------|
| `mem.pressure > 0.85`                    | Refuse LLM substrates           |
| `storage.pressure > 0.95`                | Refuse *all* substrates         |
| `temp_c > 80.0`                          | Refuse *all* substrates         |

The history of every refusal is recorded in the witness chain. The
cell *learns* which conditions caused it to refuse, and that learning
is durable.

In a more advanced version, the cell could:

- Crystallize new substrates in response to repeated thermal pressure
  (e.g. spin up a "cooldown" compartment that does nothing for 100ms
  when temp is critical).
- Use the refusal history to negotiate with the orchestrator for
  offload (the orchestrator sees the witness chain and knows when a
  node is throttled).

## Plug-and-play flow

```
        Computer                UNO Q               Fleet orchestrator
        ────────                ─────               ──────────────────
          │                       │                       │
          │ USB-C                 │                       │
          ├──────────────────────▶│                       │
          │                       │ boot                  │
          │                       │                       │
          │ adb push payload      │                       │
          ├──────────────────────▶│                       │
          │                       │                       │
          │ nmcli connect wifi    │                       │
          ├──────────────────────▶│                       │
          │                       │ join network          │
          │                       │                       │
          │ python3 first-boot    │                       │
          ├──────────────────────▶│                       │
          │                       │                       │
          │                       │ POST /register        │
          │                       ├──────────────────────▶│
          │                       │                       │
          │                       │  {salt, node_id}      │
          │                       │◀──────────────────────┤
          │                       │                       │
          │                       │ save identity         │
          │                       │ start PTO server      │
          │                       │                       │
          │ mDNS announce         │                       │
          │◀──────────────────────┤                       │
          │                       │                       │
          │ websocat :7681        │                       │
          ├──────────────────────▶│                       │
          │                       │                       │
```

Total time: ~60 seconds from USB-C connect to working node.

## What is "alive" for an UNO Q cell?

The cell's `is_alive()` check returns True when:

1. It has at least one crystallized compartment.
2. The PTO surface is exposed (the cell can be reached).
3. The hardware is reachable (`uno_q_adapters.snapshot()` returns
   non-zero values).
4. The identity has been minted (or, in dev mode, the local fallback
   has been generated).

The four compulsory tissues (witness, nudge, state, refusal) are
pre-crystallized on first boot for convenience, but a real
morphogenesis loop could grow them from zero over time.

## How this maps to the rest of the fleet

| Quilt concept        | quilt-edge-node implementation            |
|----------------------|------------------------------------------|
| Cell                 | `UnoQCell(Cell)`                         |
| Engine               | `Engine(substrates={echo,reverse,...})`  |
| Compartment          | `Compartment(transform, crystallized)`   |
| Substrate            | callable in `engine.substrates`          |
| Nudge / constraint   | `SurvivalInstinct`                       |
| Witness chain        | `Cell.witness_chain` (append-only)       |
| PTO port             | `cell.pto.expose(name, fn)`              |
| Energy               | WebSocket message or direct call         |
| Quilt (multi-cell)   | mDNS-discovered fleet of UnoQCell peers  |
| Qult (multi-quilt)   | multi-network fleet via orchestrator     |
| Death                | refusal history → cell.exit()            |

## Files

- `src/quilt_node_identity.py` — network-keyed identity + ledger
- `src/quilt_cell_uno_q.py` — UNO Q Quilt cell + survival instinct
- `src/uno_q_adapters.py` — /proc + /sys readers
- `src/quilt_pto_server.py` — WebSocket PTO server
- `src/quilt_usb_provision.py` — plug-and-play USB-C provisioner
- `scripts/quilt-edge-install.sh` — systemd installer
- `examples/full_lifecycle.py` — first-boot → heartbeat → defuse
- `tests/test_node_identity.py` — identity determinism

## Future work

- Tailscale / Wireguard overlay for cross-network quilt-of-quilts.
- Signed salt challenge from the orchestrator (HMAC over nonce).
- LLM substrate that auto-throttles based on mem pressure.
- MCU bridge to STM32U585 for real-time I/O (sensors, actuators).
- Ed25519 node identities for cryptographically-verifiable bindings.
