"""
quilt_pto_server.py — exposes the cell's PTO ports over WebSocket.

The Quilt cell has ports for state, constraints, witness, hardware,
identity. The orchestrator (or any other client) can read or invoke
them over a WebSocket on port 7681 (the IANA-registered "language
ports" range — 7681 is `vrt` per /etc/services; we use it because the
UNO Q is small and we want a port the user has never seen before).

Messages are JSON over WebSocket:
    {"op": "list"}                                 -> {"ports": [...]}
    {"op": "call", "port": "hardware"}             -> {"result": {...}}
    {"op": "call", "port": "witness", "args": []} -> {"result": [...]}
    {"op": "heartbeat"}                            -> {"result": {...}}
    {"op": "shutdown"}                             -> {"result": "ok"}

Dependencies:
    websockets>=11  (pip install websockets)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import signal
import sys
from pathlib import Path

sys.path.insert(0, "/workspace/repos/quilt-cell-harness")
sys.path.insert(0, str(Path(__file__).parent))

from quilt_cell_uno_q import UnoQCell, first_boot
from quilt_node_identity import short_id

try:
    import websockets
    from websockets.legacy.server import serve as ws_serve
except ImportError:  # pragma: no cover
    websockets = None
    ws_serve = None


log = logging.getLogger("quilt-edge-pto")


# === Operation dispatch ======================================================

async def handle_message(cell: UnoQCell, raw: str) -> str:
    """Run one op and return a JSON string."""
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"bad json: {e}"})
    op = msg.get("op")
    if op == "list":
        return json.dumps({"ports": sorted(cell.pto.ports.keys())})
    if op == "call":
        port = msg.get("port")
        args = msg.get("args", [])
        try:
            result = cell.pto.do(cell, port, *args)
            return json.dumps({"result": result}, default=str)
        except Exception as e:
            return json.dumps({"error": f"{type(e).__name__}: {e}"})
    if op == "heartbeat":
        return json.dumps({"result": cell.heartbeat()}, default=str)
    if op == "shutdown":
        # Caller signals shutdown; we let the server's main loop quit.
        return json.dumps({"result": "ok, shutting down"})
    return json.dumps({"error": f"unknown op: {op}"})


async def serve(cell: UnoQCell, host: str, port: int):
    if websockets is None:
        raise RuntimeError("pip install websockets to run the PTO server")
    log.info("Quilt PTO server listening on ws://%s:%d", host, port)
    log.info("Node id: %s", short_id(cell.identity.node_id))
    log.info("Ports: %s", sorted(cell.pto.ports.keys()))

    async def handler(ws):
        async for raw in ws:
            try:
                response = await handle_message(cell, raw)
            except Exception as e:
                response = json.dumps({"error": f"{type(e).__name__}: {e}"})
            await ws.send(response)

    async with ws_serve(handler, host, port):
        await asyncio.Future()  # run forever


# === CLI ====================================================================

def main():
    p = argparse.ArgumentParser(description="UNO Q Quilt cell — PTO server")
    p.add_argument("--ssid", default="dev-network")
    p.add_argument("--bssid", default="00:00:00:00:00:00")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=7681)
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    cell = first_boot(args.ssid, args.bssid)
    try:
        asyncio.run(serve(cell, args.host, args.port))
    except KeyboardInterrupt:
        log.info("PTO server stopped")


if __name__ == "__main__":
    main()
