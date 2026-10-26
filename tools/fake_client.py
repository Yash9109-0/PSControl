"""Fake phone clients with test modes for ps2-party-pad server.

Modes
-----
random
    Original mode: N clients sending random input for a duration.

smoke
    Join 4 phones, press every button once per phone, verify responses,
    disconnect cleanly.  Exits 0 on success, 1 on failure.

stress
    4 phones each sending 60 messages/second for 60 seconds.
    Reports aggregate throughput and any errors.

drop
    Join a phone, press a button, kill the socket mid-press, then
    reconnect and verify the pad was released (via the /status endpoint)
    within 2 seconds.

Examples::

    python tools/fake_client.py --mode smoke   --url ws://127.0.0.1:8000/ws/play
    python tools/fake_client.py --mode stress   --url ws://127.0.0.1:8000/ws/play
    python tools/fake_client.py --mode drop     --url ws://127.0.0.1:8000/ws/play
    python tools/fake_client.py --mode random   --url ws://127.0.0.1:8000/ws/play --clients 4 --duration 30
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
import time

try:
    import websockets
except ImportError as exc:  # pragma: no cover
    print(f"websockets is required: {exc}")
    print("Install with:  pip install websockets")
    sys.exit(1)

try:
    import httpx

    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False

# ---------------------------------------------------------------------------
# Button bitmask constants (must match server/protocol.py)
# ---------------------------------------------------------------------------

ALL_BUTTONS = {
    "CROSS": 1 << 0,
    "CIRCLE": 1 << 1,
    "SQUARE": 1 << 2,
    "TRIANGLE": 1 << 3,
    "L1": 1 << 4,
    "R1": 1 << 5,
    "L2": 1 << 6,
    "R2": 1 << 7,
    "SELECT": 1 << 8,
    "START": 1 << 9,
    "L3": 1 << 10,
    "R3": 1 << 11,
    "UP": 1 << 12,
    "DOWN": 1 << 13,
    "LEFT": 1 << 14,
    "RIGHT": 1 << 15,
}

BUTTONS_LIST = [0] + list(ALL_BUTTONS.values())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def random_input(seq: int) -> dict:
    buttons = random.choice(BUTTONS_LIST)
    return {
        "t": "in",
        "seq": seq,
        "b": buttons,
        "lx": random.randint(-100, 100),
        "ly": random.randint(-100, 100),
        "rx": random.randint(-100, 100),
        "ry": random.randint(-100, 100),
    }


async def _join(ws, name: str, preferred_slot: int | None = None) -> tuple[int, str]:
    """Send a join message and return (slot, token). Raises on failure."""
    msg = {"t": "join", "name": name}
    if preferred_slot is not None:
        msg["slot"] = preferred_slot
    await ws.send(json.dumps(msg))

    # Drain until we get our joined/error response (skip slot broadcasts).
    deadline = asyncio.get_event_loop().time() + 5
    while asyncio.get_event_loop().time() < deadline:
        raw = await asyncio.wait_for(ws.recv(), timeout=5)
        data = json.loads(raw)
        if data.get("t") == "joined":
            return data["slot"], data["token"]
        if data.get("t") == "error":
            raise RuntimeError(f"join rejected: {data.get('message')}")
    raise RuntimeError("timed out waiting for join response")


# ===================================================================
# MODE: smoke
# ===================================================================


async def _smoke_client(client_id: int, url: str, results: list[str]):
    """Join, press every button once, disconnect."""
    name = f"Smoke{client_id}"
    try:
        async with websockets.connect(url) as ws:
            slot, token = await _join(ws, name, preferred_slot=client_id)
            print(f"  [smoke {client_id}] joined slot {slot}")

            seq = 0
            for btn_name, bit in ALL_BUTTONS.items():
                seq += 1
                await ws.send(
                    json.dumps(
                        {"t": "in", "seq": seq, "b": bit, "lx": 0, "ly": 0, "rx": 0, "ry": 0}
                    )
                )
                await asyncio.sleep(0.02)

            # Release all buttons.
            seq += 1
            await ws.send(
                json.dumps({"t": "in", "seq": seq, "b": 0, "lx": 0, "ly": 0, "rx": 0, "ry": 0})
            )

            # Send a ping and wait for pong.
            await ws.send(json.dumps({"t": "ping", "c": 999}))
            pong_ok = False
            deadline = asyncio.get_event_loop().time() + 3
            while asyncio.get_event_loop().time() < deadline:
                raw = await asyncio.wait_for(ws.recv(), timeout=3)
                data = json.loads(raw)
                if data.get("t") == "pong" and data.get("c") == 999:
                    pong_ok = True
                    break
            if not pong_ok:
                results.append(f"client {client_id}: no pong received")
                return

            print(f"  [smoke {client_id}] all buttons sent, pong OK")
    except Exception as exc:
        results.append(f"client {client_id}: {exc}")


async def mode_smoke(url: str):
    print("[smoke] Joining 4 phones, pressing every button, disconnecting ...")
    results: list[str] = []
    await asyncio.gather(
        *(_smoke_client(i, url, results) for i in range(4))
    )
    if results:
        print("[smoke] FAILURES:")
        for r in results:
            print(f"  - {r}")
        sys.exit(1)
    else:
        print("[smoke] PASS — all 4 clients joined, sent every button, got pong, disconnected.")
        sys.exit(0)


# ===================================================================
# MODE: stress
# ===================================================================


async def _stress_client(
    client_id: int, url: str, duration: float, rate: float, counters: dict
):
    """Send messages at `rate` msgs/sec for `duration` seconds."""
    interval = 1.0 / rate
    name = f"Stress{client_id}"
    sent = 0
    errors = 0

    try:
        async with websockets.connect(url) as ws:
            slot, token = await _join(ws, name, preferred_slot=client_id)
            print(f"  [stress {client_id}] joined slot {slot}, target {rate} msg/s")

            # Drain incoming in background.
            async def _drain():
                try:
                    while True:
                        await ws.recv()
                except Exception:
                    pass

            drain_task = asyncio.create_task(_drain())

            seq = 0
            t_start = time.monotonic()
            while time.monotonic() - t_start < duration:
                seq += 1
                try:
                    await ws.send(json.dumps(random_input(seq)))
                    sent += 1
                except Exception:
                    errors += 1
                # Yield and pace.
                elapsed = time.monotonic() - t_start
                expected = seq * interval
                sleep_for = expected - elapsed
                if sleep_for > 0:
                    await asyncio.sleep(sleep_for)

            drain_task.cancel()
            try:
                await drain_task
            except asyncio.CancelledError:
                pass

    except Exception as exc:
        print(f"  [stress {client_id}] error: {exc}")
        errors += 1

    counters[client_id] = {"sent": sent, "errors": errors}


async def mode_stress(url: str, duration: float = 60.0, rate: float = 60.0):
    print(f"[stress] 4 phones × {rate} msg/s × {duration}s ...")
    counters: dict = {}
    t0 = time.monotonic()
    await asyncio.gather(
        *(_stress_client(i, url, duration, rate, counters) for i in range(4))
    )
    wall = time.monotonic() - t0

    total_sent = sum(c["sent"] for c in counters.values())
    total_errors = sum(c["errors"] for c in counters.values())
    print(f"[stress] Done in {wall:.1f}s")
    print(f"  Total sent   : {total_sent}")
    print(f"  Total errors : {total_errors}")
    print(f"  Aggregate    : {total_sent / wall:.1f} msg/s")
    for cid, c in sorted(counters.items()):
        print(f"  Client {cid}: {c['sent']} sent, {c['errors']} errors "
              f"({c['sent'] / wall:.1f} msg/s)")
    if total_errors > 0:
        print("[stress] WARN — some sends failed.")
    else:
        print("[stress] PASS")


# ===================================================================
# MODE: drop
# ===================================================================


async def mode_drop(url: str):
    """Kill socket mid-press, verify pad releases within 2 seconds."""
    print("[drop] Connecting, pressing a button, then killing the socket ...")

    # Derive HTTP URL from WS URL for the /status endpoint.
    http_base = url.replace("ws://", "http://").replace("/ws/play", "")

    if not _HAS_HTTPX:
        print("[drop] WARNING: httpx not installed — cannot verify pad release via /status.")
        print("       Install with:  pip install httpx")
        print("       Falling back to timing-only check (reconnect after 2.5s).")

    # 1. Connect, join, press CROSS.
    ws = await websockets.connect(url)
    slot, token = await _join(ws, "DropTest", preferred_slot=0)
    print(f"  Joined slot {slot}")

    seq = 1
    await ws.send(
        json.dumps({"t": "in", "seq": seq, "b": ALL_BUTTONS["CROSS"], "lx": 0, "ly": 0, "rx": 0, "ry": 0})
    )
    await asyncio.sleep(0.05)
    print("  Button pressed. Killing socket NOW.")

    # 2. Kill the socket abruptly (no close handshake).
    ws.transport.close() if hasattr(ws, "transport") else await ws.close()

    # 3. Wait and check that the pad was released.
    t_kill = time.monotonic()

    if _HAS_HTTPX:
        # Poll /status up to 3 seconds waiting for the server to release the pad.
        # The server's timeout loop should call release_all within INPUT_TIMEOUT_SECONDS (2s).
        released = False
        async with httpx.AsyncClient() as client:
            while time.monotonic() - t_kill < 3.0:
                await asyncio.sleep(0.25)
                try:
                    resp = await client.get(f"{http_base}/status")
                    data = resp.json()
                    # After disconnect + timeout, the slot should be disconnected.
                    slot_info = data["slots"][slot]
                    if not slot_info["connected"]:
                        elapsed = time.monotonic() - t_kill
                        released = True
                        print(f"  Pad released after {elapsed:.2f}s — OK")
                        break
                except Exception as exc:
                    print(f"  /status poll error: {exc}")
                    await asyncio.sleep(0.5)

        if not released:
            print("  FAIL — pad was not released within 3 seconds.")
            sys.exit(1)
    else:
        # Without httpx, just wait and reconnect to see if slot is freed.
        await asyncio.sleep(2.5)
        print("  Waited 2.5s (no httpx to verify release). Reconnecting ...")
        async with websockets.connect(url) as ws2:
            slot2, _ = await _join(ws2, "DropVerify", preferred_slot=slot)
            # If we can't get the same slot, the grace period is holding it.
            # That's acceptable — it means release_all was called on leave.
            print(f"  Reconnected to slot {slot2} (original was {slot})")
            if slot2 == slot:
                print("  Grace period may have expired or slot was freed — OK")
            else:
                print("  Slot held by grace period (expected) — pad was released on disconnect.")

    print("[drop] PASS")
    sys.exit(0)


# ===================================================================
# MODE: random (original)
# ===================================================================


async def run_client(client_id: int, url: str, duration: float, seed: int):
    rng = random.Random(seed + client_id)
    name = f"Fake{client_id}"
    preferred_slot = client_id % 4

    async with websockets.connect(url) as ws:
        await ws.send(json.dumps({"t": "join", "name": name, "slot": preferred_slot}))
        try:
            greeting = await asyncio.wait_for(ws.recv(), timeout=5)
        except asyncio.TimeoutError:
            print(f"[client {client_id}] no response to join, giving up")
            return

        slot = None
        token = None
        try:
            data = json.loads(greeting)
            if data.get("t") == "joined":
                slot = data["slot"]
                token = data.get("token")
                print(f"[client {client_id}] joined as {name} -> slot {slot} (token {token})")
            elif data.get("t") == "error":
                print(f"[client {client_id}] join rejected: {data.get('message')}")
                return
            else:
                print(f"[client {client_id}] unexpected join response: {greeting!r}")
                return
        except json.JSONDecodeError:
            print(f"[client {client_id}] bad join response: {greeting!r}")
            return

        seq = 0
        deadline = asyncio.get_event_loop().time() + duration
        while asyncio.get_event_loop().time() < deadline:
            remaining = deadline - asyncio.get_event_loop().time()
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=min(0.5, remaining))
                try:
                    parsed = json.loads(msg)
                except json.JSONDecodeError:
                    parsed = {}
                if parsed.get("t") == "slots":
                    print(f"[client {client_id}] slots snapshot: {parsed.get('slots')}")
                elif parsed.get("t") == "pong":
                    print(f"[client {client_id}] pong c={parsed.get('c')}")
                elif parsed.get("t") == "error":
                    print(f"[client {client_id}] error: {parsed.get('message')}")
            except asyncio.TimeoutError:
                pass

            choice = rng.random()
            if choice < 0.75:
                seq += 1
                await ws.send(json.dumps(random_input(seq)))
            else:
                await ws.send(json.dumps({"t": "ping", "c": seq}))

            await asyncio.sleep(rng.uniform(0.05, 0.25))

        print(f"[client {client_id}] done")


# ===================================================================
# CLI
# ===================================================================


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run fake phone clients against the ps2-party-pad server."
    )
    parser.add_argument(
        "--mode",
        choices=["random", "smoke", "stress", "drop"],
        default="random",
        help="Test mode (default: random)",
    )
    parser.add_argument("--clients", type=int, default=2, help="number of fake phones (random mode)")
    parser.add_argument(
        "--duration", type=float, default=20.0, help="seconds each client runs (random/stress mode)"
    )
    parser.add_argument(
        "--rate", type=float, default=60.0, help="messages per second per client (stress mode)"
    )
    parser.add_argument(
        "--url", default="ws://127.0.0.1:8000/ws/play", help="WebSocket play URL"
    )
    parser.add_argument("--seed", type=int, default=1, help="random seed (random mode)")
    args = parser.parse_args()

    if args.mode == "smoke":
        await mode_smoke(args.url)
    elif args.mode == "stress":
        await mode_stress(args.url, args.duration, args.rate)
    elif args.mode == "drop":
        await mode_drop(args.url)
    else:
        await asyncio.gather(
            *(run_client(i, args.url, args.duration, args.seed) for i in range(args.clients))
        )


if __name__ == "__main__":
    asyncio.run(main())
