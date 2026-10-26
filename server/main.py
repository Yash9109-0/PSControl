"""Main FastAPI application entry point for ps2-party-pad server."""

from __future__ import annotations

import asyncio
import json
import os
import socket
import time
from collections import deque
from contextlib import asynccontextmanager
from io import BytesIO
from typing import Optional

import qrcode
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
import uvicorn

from server.config import PORT, HOST_ONLY_LOCALHOST, HEARTBEAT_SECONDS
from server.gamepad import GamepadHub
from server.net_utils import get_lan_ip, is_localhost
from server.protocol import (
    parse_message,
    ProtocolError,
    BUTTON_NAMES,
    BUTTON_CROSS,
    MAX_RAW_SIZE,
)
from server.rooms import Room, RoomFullError, NUM_SLOTS

WEB_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "web"))
CONTROLLER_DIR = os.path.join(WEB_DIR, "controller")
HOST_DIR = os.path.join(WEB_DIR, "host")
STATIC_DIR = os.path.join(WEB_DIR, "static")


class _NullHub:
    """Stand-in hub that accepts calls but drives no real pads."""

    def release_all(self, slot: int) -> None:
        pass

    def apply_state(self, slot: int, *args) -> None:
        pass

    def swap_slots(self, slot_a: int, slot_b: int) -> None:
        pass

    def close(self) -> None:
        pass


try:
    hub: GamepadHub | _NullHub = GamepadHub()
    gamepad_ready = True
    gamepad_hint = ""
except Exception as exc:
    print(f"[server] Could not initialize GamepadHub ({exc}). Running without a pad driver.")
    hub = _NullHub()
    gamepad_ready = False
    gamepad_hint = str(exc)

room = Room(hub)

play_connections: dict[WebSocket, dict] = {}
host_connections: set[WebSocket] = set()
timeout_task: Optional[asyncio.Task[None]] = None

# ---------------------------------------------------------------------------
# Per-slot message stats for /api/stats
# ---------------------------------------------------------------------------
STATS_WINDOW = 5.0  # seconds of history for rate calculation

# Per-slot: deque of (timestamp, processing_time_seconds) for recent messages
_slot_stats: list[deque] = [deque() for _ in range(NUM_SLOTS)]


def _record_message(slot: int, processing_time: float) -> None:
    """Record a processed input message for stats tracking."""
    if 0 <= slot < NUM_SLOTS:
        _slot_stats[slot].append((time.monotonic(), processing_time))


def _compute_stats() -> dict:
    """Compute per-slot message rate and avg processing time."""
    now = time.monotonic()
    cutoff = now - STATS_WINDOW
    slots = []
    for idx in range(NUM_SLOTS):
        q = _slot_stats[idx]
        # Evict old entries.
        while q and q[0][0] < cutoff:
            q.popleft()
        count = len(q)
        rate = count / STATS_WINDOW if STATS_WINDOW > 0 else 0.0
        avg_proc = 0.0
        if count > 0:
            avg_proc = sum(pt for _, pt in q) / count
        slots.append({
            "slot": idx,
            "messages_per_second": round(rate, 1),
            "avg_processing_ms": round(avg_proc * 1000, 3),
            "sample_count": count,
        })
    return {"window_seconds": STATS_WINDOW, "slots": slots}


def _snapshot_payload() -> str:
    return json.dumps({"t": "slots", "slots": room.snapshot()})


async def _safe_send(websocket: WebSocket, text: str) -> bool:
    try:
        await websocket.send_text(text)
        return True
    except Exception:
        return False


async def broadcast_snapshot() -> None:
    payload = _snapshot_payload()
    targets = list(play_connections.keys()) + list(host_connections)
    dead: list[WebSocket] = []
    for ws in targets:
        if not await _safe_send(ws, payload):
            dead.append(ws)
    for ws in dead:
        play_connections.pop(ws, None)
        host_connections.discard(ws)


async def _timeout_loop() -> None:
    while True:
        await asyncio.sleep(0.25)
        try:
            room.check_timeouts()
        except Exception as exc:
            print(f"[server] check_timeouts error: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global timeout_task
    timeout_task = asyncio.create_task(_timeout_loop())
    try:
        yield
    finally:
        if timeout_task is not None:
            timeout_task.cancel()
        try:
            hub.close()
        except Exception:
            pass


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def root():
    """Serve the phone controller page."""
    return FileResponse(os.path.join(CONTROLLER_DIR, "index.html"))


@app.get("/host")
async def host_dashboard(request: Request):
    """Serve the host dashboard, restricted to localhost when configured."""
    if HOST_ONLY_LOCALHOST and not is_localhost(request.client.host if request.client else None):
        raise HTTPException(status_code=403, detail="Host dashboard is restricted to localhost.")
    return FileResponse(os.path.join(HOST_DIR, "index.html"))


@app.get("/api/info")
async def api_info():
    ip = get_lan_ip()
    return {
        "ip": ip,
        "port": PORT,
        "ws_url": f"ws://{ip}:{PORT}/ws/play",
        "join_url": f"http://{ip}:{PORT}/",
        "qr_url": f"/api/qr.png",
        "slots": NUM_SLOTS,
    }


_qr_cache: dict[str, bytes] = {}


def _get_qr_png(url: str) -> bytes:
    if url not in _qr_cache:
        img = qrcode.make(url)
        buf = BytesIO()
        img.save(buf, format="PNG")
        _qr_cache[url] = buf.getvalue()
    return _qr_cache[url]


@app.get("/api/qr.png")
async def api_qr():
    """QR code image of the join URL."""
    ip = get_lan_ip()
    url = f"http://{ip}:{PORT}/"
    return Response(content=_get_qr_png(url), media_type="image/png")


@app.get("/config")
async def api_config():
    ip = get_lan_ip()
    return {"ws_url": f"ws://{ip}:{PORT}/ws/play", "port": PORT, "slots": NUM_SLOTS}


@app.get("/status")
async def api_status():
    return {"slots": room.snapshot(), "gamepad_ready": gamepad_ready, "gamepad_hint": gamepad_hint}


@app.get("/api/stats")
async def api_stats():
    """Per-slot message throughput and average server processing time."""
    return _compute_stats()


@app.get("/qr/{slot}.png")
async def api_qr_slot(slot: int):
    if not 0 <= slot < NUM_SLOTS:
        raise HTTPException(status_code=404, detail="unknown slot")
    ip = get_lan_ip()
    url = f"http://{ip}:{PORT}/?slot={slot}"
    return Response(content=_get_qr_png(url), media_type="image/png")


@app.get("/controller.css")
async def controller_css():
    return FileResponse(os.path.join(CONTROLLER_DIR, "controller.css"))


@app.get("/controller.js")
async def controller_js():
    return FileResponse(os.path.join(CONTROLLER_DIR, "controller.js"))


@app.get("/host/host.css")
async def host_css():
    return FileResponse(os.path.join(HOST_DIR, "host.css"))


@app.get("/host/host.js")
async def host_js():
    return FileResponse(os.path.join(HOST_DIR, "host.js"))


@app.websocket("/ws/play")
async def ws_play(websocket: WebSocket):
    """Phone endpoint.

    The first message must be a ``join``. Afterwards the phone may send
    ``in`` (gamepad input, applied only when seq is newer than the last seen)
    and ``ping`` (answered with a ``pong`` echoing ``c``). On disconnect the
    player leaves and the slot snapshot is re-broadcast.
    """
    await websocket.accept()
    slot: Optional[int] = None
    name: Optional[str] = None
    token: Optional[str] = None
    connected = False

    try:
        raw = await websocket.receive_text()
        try:
            msg = parse_message(raw)
        except ProtocolError as exc:
            await websocket.send_text(json.dumps({"t": "error", "message": str(exc)}))
            await websocket.close(code=1008)
            return

        if msg.get("t") != "join":
            await websocket.send_text(
                json.dumps({"t": "error", "message": "First message must be a join"})
            )
            await websocket.close(code=1008)
            return

        name = msg.get("name", "Player")
        token = msg.get("token")
        preferred_slot = msg.get("slot")
        try:
            slot, token = room.join(name, token, preferred_slot)
        except RoomFullError:
            await websocket.send_text(json.dumps({"t": "error", "message": "room full"}))
            await websocket.close(code=1008)
            return

        connected = True
        play_connections[websocket] = {
            "slot": slot,
            "name": name,
            "token": token,
            "last_seq": -1,
        }
        await websocket.send_text(
            json.dumps({"t": "joined", "slot": slot, "token": token, "name": name})
        )
        await broadcast_snapshot()

        while True:
            raw = await websocket.receive_text()
            try:
                msg = parse_message(raw)
            except ProtocolError:
                continue
            mtype = msg.get("t")

            if mtype == "join":
                name = msg.get("name", name or "Player")
                token = msg.get("token", token)
                preferred_slot = msg.get("slot")
                try:
                    slot, token = room.join(name, token, preferred_slot)
                except RoomFullError:
                    await websocket.send_text(json.dumps({"t": "error", "message": "room full"}))
                    continue
                connected = True
                info = play_connections.get(websocket, {})
                info.update({"slot": slot, "name": name, "token": token, "last_seq": -1})
                play_connections[websocket] = info
                await websocket.send_text(
                    json.dumps({"t": "joined", "slot": slot, "token": token, "name": name})
                )
                await broadcast_snapshot()

            elif mtype == "in":
                if not connected or slot is None:
                    continue
                info = play_connections[websocket]
                seq = msg.get("seq", 0)
                if not isinstance(seq, int) or isinstance(seq, bool):
                    seq = 0
                if seq <= info["last_seq"]:
                    continue
                info["last_seq"] = seq
                t0 = time.monotonic()
                room.note_input(slot)
                b = msg.get("b", 0)
                lx = msg.get("lx", 0)
                ly = msg.get("ly", 0)
                rx = msg.get("rx", 0)
                ry = msg.get("ry", 0)
                try:
                    hub.apply_state(slot + 1, b, lx, ly, rx, ry)
                except Exception:
                    pass
                _record_message(slot, time.monotonic() - t0)

            elif mtype == "ping":
                await websocket.send_text(json.dumps({"t": "pong", "c": msg.get("c")}))

    except WebSocketDisconnect:
        pass
    finally:
        play_connections.pop(websocket, None)
        if connected and slot is not None:
            room.leave(slot)
            await broadcast_snapshot()


@app.websocket("/ws/host")
async def ws_host(websocket: WebSocket):
    """Host dashboard endpoint (localhost only).

    Pushes the slot snapshot every second and accepts ``kick`` / ``swap``
    commands from the dashboard.
    """
    if HOST_ONLY_LOCALHOST and not is_localhost(websocket.client.host if websocket.client else None):
        await websocket.close(code=1008)
        return

    await websocket.accept()
    host_connections.add(websocket)
    sender_task = asyncio.create_task(_host_sender(websocket))
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except (ValueError, json.JSONDecodeError):
                continue
            cmd = msg.get("cmd")
            if cmd == "kick":
                slot = msg.get("slot")
                if isinstance(slot, int) and not isinstance(slot, bool):
                    try:
                        room.kick(slot)
                    except Exception:
                        pass
                    # Close and evict any active play connection on this slot
                    kicked_sockets = [
                        ws for ws, info in list(play_connections.items())
                        if info.get("slot") == slot
                    ]
                    for ws in kicked_sockets:
                        try:
                            await ws.send_text(json.dumps({"t": "error", "message": "kicked"}))
                            await ws.close(code=1000)
                        except Exception:
                            pass
                        play_connections.pop(ws, None)
                    await broadcast_snapshot()
            elif cmd == "swap":
                a = msg.get("slot_a")
                b = msg.get("slot_b")
                if (
                    isinstance(a, int)
                    and isinstance(b, int)
                    and not isinstance(a, bool)
                    and not isinstance(b, bool)
                ):
                    try:
                        room.swap(a, b)
                        for info in play_connections.values():
                            if info.get("slot") == a:
                                info["slot"] = b
                            elif info.get("slot") == b:
                                info["slot"] = a
                    except Exception:
                        pass
                    await broadcast_snapshot()
            elif cmd == "test":
                slot = msg.get("slot")
                button = msg.get("button", "cross")
                if isinstance(slot, int) and not isinstance(slot, bool) and 0 <= slot < NUM_SLOTS:
                    occupied = room.slots[slot] is not None and room.slots[slot].get("connected")
                    if not occupied:
                        asyncio.create_task(_test_pad(slot, button))
    except WebSocketDisconnect:
        pass
    finally:
        host_connections.discard(websocket)
        sender_task.cancel()


async def _host_sender(websocket: WebSocket) -> None:
    while True:
        try:
            await websocket.send_text(_snapshot_payload())
        except Exception:
            return
        await asyncio.sleep(HEARTBEAT_SECONDS)


async def _test_pad(slot: int, button: str) -> None:
    """Briefly press a button on a virtual pad to help with PCSX2 binding."""
    bit = BUTTON_NAMES.get(str(button).lower(), BUTTON_CROSS)
    try:
        hub.apply_state(slot + 1, bit, 0, 0, 0, 0)
        await asyncio.sleep(0.15)
        hub.release_all(slot + 1)
    except Exception:
        pass


class NoDelayServer(uvicorn.Server):
    """uvicorn.Server that enables TCP_NODELAY on the listening sockets."""

    async def startup(self, sockets=None):
        await super().startup(sockets=sockets)
        for server in getattr(self, "servers", []) or []:
            for sock in server.sockets or []:
                try:
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                except (OSError, AttributeError):
                    pass


def main():
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT)
    server = NoDelayServer(config=config)
    asyncio.run(server.serve())


if __name__ == "__main__":
    main()