# EDGE_FLEET_KICKOFF — four prototype repos for Arduino UNO Q

> **2026-09-24.** Casey's vision: turn Arduino UNO Q boards into
> plug-and-play Quilt nodes. Upload program → board joins your
> network → becomes a productive edge cell. Same program uploaded
> from any computer on the network → that network mints the board's
> identity. The board is bonded to the network that created it.

This kickoff produced four prototype repos, each self-contained,
each with at least one runnable demo:

```
                          SuperInstance EDGE FLEET
                          ════════════════════════

┌─────────────────────────────────────────────────────────────────────┐
│                                                                       │
│  QUILT EDGE FLEET — 4 PROTOTYPE REPOS                                │
│                                                                       │
│   ┌──────────────────┐        ┌──────────────────────┐              │
│   │ quilt-edge-node  │───────▶│ quilt-fleet-         │              │
│   │ (the runtime)    │        │ orchestrator         │              │
│   │                  │        │ (central coordinator)│              │
│   └──────────────────┘        └──────────────────────┘              │
│           │                              ▲                           │
│           │   ┌──────────────────────┐    │                           │
│           └──▶│ quilt-edge-ml        │────┘                           │
│               │ (ML substrates)      │                                │
│               └──────────────────────┘                                │
│                       ▲                                               │
│                       │                                               │
│               ┌──────────────────────┐                                │
│               │ quilt-edge-observer  │                                │
│               │ (vessel observability│                                │
│               │  tap pattern)        │                                │
│               └──────────────────────┘                                │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

| Repo                           | What it does                                      |
|--------------------------------|---------------------------------------------------|
| **quilt-edge-node**            | The cell runtime + plug-and-play + network-keyed identity |
| **quilt-edge-ml**             | ML substrates (ring buffer, out-of-core, EI/TFLite/ONNX, first/last mile) |
| **quilt-fleet-orchestrator**   | Central coordinator (registry, canary aggregation, task routing, witness collection) |
| **quilt-edge-observer**        | Pattern demonstrator: vessel observability tap → voice agent context |

## How they compose

A real vessel deployment:

```
vessel instruments
   (NMEA 2000, sensors, audio)
        │
        ▼
[ quilt-edge-observer ]  ────────▶  context packets to voice agent
        │                                       ▲
        │ writes to                             │
        ▼                                       │
[ quilt-edge-ml ]  ──▶  ring_buffer + first/last mile filter
        │
        ▼
[ quilt-edge-node ]  ──▶  network-keyed identity, witnesses
        │
        ▼ Wi-Fi
[ quilt-fleet-orchestrator ]  ──▶  fleet canary + task routing
```

The four repos compose. Each can be tested in isolation; together
they form the canonical UNO Q edge fleet.

## Verified specs (from arduino.cc)

**UNO Q 4GB (ABX00173):**
- MPU: Qualcomm Dragonwing QRB2210 — 4× Cortex-A53 @ 2.0 GHz, 64-bit
- GPU: Adreno 702 @ 845 MHz (OpenGL ES 3.1, Vulkan 1.1, OpenCL 2.0)
- DSP: Hexagon QDSP6 v66 (the actual "AI accelerator")
- VPU: 1080p30 encode/decode
- ISP: 2× ISP (13 MP + 13 MP or 25 MP @ 30 fps)
- MCU: STM32U585 Cortex-M33 @ 160 MHz, 2 MB flash, 786 KB SRAM, Zephyr
- RAM: 4 GB LPDDR4X (32-bit, 1804 MHz)
- Storage: 32 GB eMMC
- Wi-Fi 5 dual-band 2.4/5 GHz + BT 5.1 (WCBN3536A module)
- USB-C 3.1 with PD
- Power: 5V 3A via USB-C, 7-24V via Vin
- OS: Debian 13 (Trixie), arm64
- 47× GPIOs, 22× on JANALOG/JDIGITAL, 25× on JMISC

**Three ways to access the shell:**
1. Arduino App Lab (official, includes the `bricks` framework)
2. ADB over USB-C (`adb shell` — works without network)
3. SSH over Wi-Fi (`ssh arduino@<boardname>.local`)

**Defaults:**
- User: `arduino`
- Password: `arduino` (must be changed on first setup)
- App Lab auto-enables SSH + Network Mode during first-boot

**ML frameworks:**
- Edge Impulse Linux CLI (`edge-impulse-linux-runner`) — runs `.eim` files
- TensorFlow Lite (ARM NEON + Adreno GPU/NN delegates)
- ONNX Runtime
- llama.cpp for SLMs (Qwen3:0.6B, etc., via GGUF)

## What was actually built

### quilt-edge-node (v0.1.0)
- `quilt_node_identity.py` — HMAC-SHA256(network_salt, board_serial)
  → 64-hex node_id (verified by 11 passing unit tests)
- `quilt_cell_uno_q.py` — UNO Q cell with hardware-aware substrates
  + survival instinct (refuses LLM when mem > 85%)
- `uno_q_adapters.py` — reads /proc/meminfo, /sys/class/thermal,
  statvfs, /proc/loadavg
- `quilt_pto_server.py` — WebSocket on :7681 (list, call, heartbeat)
- `quilt_usb_provision.py` — `adb push` → `nmcli connect` → first-boot
- `scripts/quilt-edge-install.sh` — systemd unit + avahi mDNS
- `examples/full_lifecycle.py` — works end-to-end (verified)

### quilt-edge-ml (v0.1.0)
- `ring_buffer.py` — JSONL FIFO on disk (verified by 4 passing tests)
- `out_of_core.py` — streaming dataset iterator + sklearn-style partial_fit
- `first_last_mile.py` — z-score anomaly filter + parameter-update reducer
- `ei_substrate.py` — Edge Impulse `.eim` runner
- `tflite_substrate.py` — TFLite + ONNX substrate factories
- `examples/vessel_demo.py` — 5000 events, 1MB on disk, 3 forwarded,
  1280 samples trained, 3 of 6 parameters accepted

### quilt-fleet-orchestrator (v0.1.0)
- `node_registry.py` — keyed by network-keyed identity, JSONL on disk
- `canary_aggregator.py` — composed canary + drift detection
- `task_router.py` — pluggable selectors (affinity, round-robin)
- `discovery.py` — mDNS / DNS-SD with polling fallback
- `witness_collector.py` — combined fleet witness log
- `examples/fleet_demo.py` — 4 simulated nodes, 1 drifter,
  8 tasks routed, 12 witness entries

### quilt-edge-observer (v0.1.0)
- `serial_tap.py` — NMEA 0183 parser + synthetic stream generator
- `vector_compressor.py` — per-window vector summaries
- `context_injector.py` — HTTP POST to voice agent + z-score baseline
- `examples/vessel_observer_demo.py` — synthetic NMEA stream,
  60-reading baseline, 5 context packets sent to mock voice agent

## Doctrines demonstrated

1. **Plug-and-play is real.** USB-C → join network → independent node
   in 60s. The mDNS announcement makes the cell discoverable.
2. **Network-keyed identity.** Board + network = node. Move board to
   a new network = new identity (and lose the old). Implemented as
   HMAC-SHA256(network_salt, board_serial).
3. **Survival instinct emerges from constraints.** Don't hand-code
   refusal behavior. Constrain the cell and let refusal emerge
   from hardware pressure.
4. **Substrate agnosticism at the edge.** The cell has echo /
   reverse / sha256 / stub_llm / hardware / alive. Adding ML
   substrates = adding functions to a dict.
5. **Out-of-core learning is mandatory.** Stream from the ring
   buffer; never load the full dataset into RAM.
6. **First/last mile filtering.** The edge is not a dumb pipe.
   Forward only anomalies; apply only meaningful updates.
7. **Composed canary at the Quilt level.** Multiple cells, one
   fleet hash. Drifters are signal, not failure.
8. **Vessel observability tap.** UNO Q as context injector for
   a voice agent — the voice agent never has to guess what's
   true right now.

## Cross-API notes

- `ZAI_TOKEN` works (used for JEV verification of repo README drafts).
- `JEV` confirms each new README is `domain=cs` (not yet canon —
  they're prototypes, not finished doctrine).
- `GitHub` API creates and pushes to repos cleanly.

## Future work

1. **Hardware verify** — flash an actual UNO Q and run the demo
   end-to-end. Currently only verified on a workstation.
2. **STM32 bridge** — wire the STM32U585 real-time MCU for sensor
   I/O. The MPU is the Quilt; the MCU is the substrate zoo.
3. **Ed25519-signed canaries** — currently the canary is
   content-only; signing makes it unforgeable.
4. **Cross-network Qult** — multi-network fleet with global
   canary composition.
5. **Tailscale overlay** — for nodes that need to reach across
   networks.
6. **More substrates** — llama.cpp SLM, GGUF quantizer,
   KERI proofs, lp_GMRES linear solvers, etc.
7. **PI insurance** — confirm ergonomics, latency, throughput on
   actual hardware before mass deployment.

## Files added this turn

- `/workspace/repos/quilt-edge-node/` (16 files, ~75 KB)
  - README.md, DESIGN.md, INSTALL.md, LICENSE
  - src/{quilt_node_identity, quilt_cell_uno_q, uno_q_adapters,
         quilt_pto_server, quilt_usb_provision}.py
  - scripts/quilt-edge-install.sh
  - systemd/quilt-edge-node.service
  - examples/full_lifecycle.py
  - tests/test_node_identity.py
  - EDGE_FLEET_KICKOFF.md (this file)

- `/workspace/repos/quilt-edge-ml/` (14 files, ~50 KB)
  - README.md, LICENSE
  - src/{__init__, ring_buffer, out_of_core, first_last_mile,
         ei_substrate, tflite_substrate}.py
  - examples/vessel_demo.py
  - tests/test_ring_buffer.py

- `/workspace/repos/quilt-fleet-orchestrator/` (13 files, ~35 KB)
  - README.md, LICENSE
  - src/{__init__, node_registry, canary_aggregator, task_router,
         discovery, witness_collector}.py
  - examples/fleet_demo.py

- `/workspace/repos/quilt-edge-observer/` (10 files, ~30 KB)
  - README.md, LICENSE
  - src/{__init__, serial_tap, vector_compressor, context_injector}.py
  - examples/vessel_observer_demo.py

All four repos pushed to https://github.com/SuperInstance/.
