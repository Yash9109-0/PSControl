"""Integration test: run smoke mode against the FastAPI test client with a faked gamepad hub.

This test exercises the full WebSocket flow (join → button presses → pong → disconnect)
without requiring ViGEmBus or a real network connection.
"""

from __future__ import annotations

import json

import pytest
from starlette.testclient import TestClient

from server.rooms import NUM_SLOTS
from server.protocol import BUTTON_CROSS, BUTTON_CIRCLE, BUTTON_SQUARE, BUTTON_TRIANGLE
from server.protocol import BUTTON_L1, BUTTON_R1, BUTTON_L2, BUTTON_R2
from server.protocol import BUTTON_SELECT, BUTTON_START, BUTTON_L3, BUTTON_R3
from server.protocol import BUTTON_UP, BUTTON_DOWN, BUTTON_LEFT, BUTTON_RIGHT

ALL_BUTTONS = {
    "CROSS": BUTTON_CROSS,
    "CIRCLE": BUTTON_CIRCLE,
    "SQUARE": BUTTON_SQUARE,
    "TRIANGLE": BUTTON_TRIANGLE,
    "L1": BUTTON_L1,
    "R1": BUTTON_R1,
    "L2": BUTTON_L2,
    "R2": BUTTON_R2,
    "SELECT": BUTTON_SELECT,
    "START": BUTTON_START,
    "L3": BUTTON_L3,
    "R3": BUTTON_R3,
    "UP": BUTTON_UP,
    "DOWN": BUTTON_DOWN,
    "LEFT": BUTTON_LEFT,
    "RIGHT": BUTTON_RIGHT,
}


class FakeHub:
    """Records all calls to apply_state and release_all for assertions."""

    def __init__(self):
        self.states: list[tuple] = []
        self.releases: list[int] = []

    def apply_state(self, slot: int, buttons: int, lx: int, ly: int, rx: int, ry: int):
        self.states.append((slot, buttons, lx, ly, rx, ry))

    def release_all(self, slot: int):
        self.releases.append(slot)

    def close(self):
        pass


@pytest.fixture()
def fake_app():
    """Create a fresh FastAPI app with a FakeHub instead of real gamepads."""
    # We need to patch the hub BEFORE the app module's global state is used.
    # Import the module and swap out the hub + room at module level.
    import server.main as srv

    original_hub = srv.hub
    original_room = srv.room
    original_gamepad_ready = srv.gamepad_ready
    original_gamepad_hint = srv.gamepad_hint

    fake_hub = FakeHub()
    srv.hub = fake_hub
    srv.gamepad_ready = True
    srv.gamepad_hint = ""

    from server.rooms import Room
    srv.room = Room(fake_hub)

    yield srv.app, fake_hub

    # Restore originals.
    srv.hub = original_hub
    srv.room = original_room
    srv.gamepad_ready = original_gamepad_ready
    srv.gamepad_hint = original_gamepad_hint


def _drain_until(ws, msg_type: str, timeout_messages: int = 20) -> dict | None:
    """Read messages from the test websocket until we find one of the given type."""
    for _ in range(timeout_messages):
        data = ws.receive_json()
        if data.get("t") == msg_type:
            return data
    return None


class TestSmokeIntegration:
    """Mirrors the fake_client smoke mode: join 4 clients, press every button, verify pong."""

    def test_four_clients_join_press_all_buttons_and_disconnect(self, fake_app):
        app, fake_hub = fake_app

        with TestClient(app) as client:
            # Connect 4 websocket clients.
            contexts = []
            websockets = []
            for i in range(4):
                ctx = client.websocket_connect("/ws/play")
                ws = ctx.__enter__()
                contexts.append(ctx)
                websockets.append(ws)

            try:
                tokens = []
                slots_assigned = []

                # Each client joins.
                for i, ws in enumerate(websockets):
                    ws.send_json({"t": "join", "name": f"Smoke{i}", "slot": i})
                    resp = _drain_until(ws, "joined")
                    assert resp is not None, f"Client {i} did not receive 'joined'"
                    assert resp["name"] == f"Smoke{i}"
                    tokens.append(resp["token"])
                    slots_assigned.append(resp["slot"])

                assert len(set(slots_assigned)) == 4, "All 4 clients should have unique slots"

                # Each client presses every button.
                for i, ws in enumerate(websockets):
                    seq = 0
                    for btn_name, bit in ALL_BUTTONS.items():
                        seq += 1
                        ws.send_json({
                            "t": "in", "seq": seq,
                            "b": bit, "lx": 0, "ly": 0, "rx": 0, "ry": 0,
                        })

                    # Release all.
                    seq += 1
                    ws.send_json({
                        "t": "in", "seq": seq,
                        "b": 0, "lx": 0, "ly": 0, "rx": 0, "ry": 0,
                    })

                # Verify the hub received apply_state calls.
                assert len(fake_hub.states) > 0, "Hub should have received apply_state calls"

                # Each client sends a ping and expects a pong.
                for i, ws in enumerate(websockets):
                    ws.send_json({"t": "ping", "c": 42 + i})
                    resp = _drain_until(ws, "pong")
                    assert resp is not None, f"Client {i} did not receive 'pong'"
                    assert resp["c"] == 42 + i

            finally:
                # Disconnect all.
                for ctx in contexts:
                    try:
                        ctx.__exit__(None, None, None)
                    except Exception:
                        pass

            # After disconnect, hub.release_all should have been called for each slot.
            assert len(fake_hub.releases) >= 4, (
                f"Expected at least 4 release_all calls, got {len(fake_hub.releases)}"
            )

    def test_room_full_rejects_fifth_client(self, fake_app):
        app, fake_hub = fake_app

        with TestClient(app) as client:
            contexts = []
            websockets = []

            # Fill all 4 slots.
            for i in range(4):
                ctx = client.websocket_connect("/ws/play")
                ws = ctx.__enter__()
                contexts.append(ctx)
                websockets.append(ws)
                ws.send_json({"t": "join", "name": f"P{i}", "slot": i})
                resp = _drain_until(ws, "joined")
                assert resp is not None

            # 5th client should be rejected.
            ctx5 = client.websocket_connect("/ws/play")
            ws5 = ctx5.__enter__()
            contexts.append(ctx5)
            ws5.send_json({"t": "join", "name": "Extra"})
            resp = _drain_until(ws5, "error")
            assert resp is not None
            assert "full" in resp.get("message", "").lower()

            for ctx in contexts:
                try:
                    ctx.__exit__(None, None, None)
                except Exception:
                    pass

    def test_duplicate_seq_is_ignored(self, fake_app):
        app, fake_hub = fake_app

        with TestClient(app) as client:
            with client.websocket_connect("/ws/play") as ws:
                ws.send_json({"t": "join", "name": "SeqTest"})
                resp = _drain_until(ws, "joined")
                assert resp is not None

                # Send seq=1.
                ws.send_json({"t": "in", "seq": 1, "b": BUTTON_CROSS, "lx": 0, "ly": 0, "rx": 0, "ry": 0})
                # Send seq=1 again (duplicate — should be dropped).
                ws.send_json({"t": "in", "seq": 1, "b": BUTTON_CIRCLE, "lx": 0, "ly": 0, "rx": 0, "ry": 0})
                # Send seq=2 (should go through).
                ws.send_json({"t": "in", "seq": 2, "b": BUTTON_SQUARE, "lx": 0, "ly": 0, "rx": 0, "ry": 0})

                # Give the server a moment to process.
                ws.send_json({"t": "ping", "c": 1})
                _drain_until(ws, "pong")

                # Should have 2 apply_state calls (seq 1 and seq 2), not 3.
                assert len(fake_hub.states) == 2
                assert fake_hub.states[0][1] == BUTTON_CROSS   # seq 1
                assert fake_hub.states[1][1] == BUTTON_SQUARE   # seq 2

    def test_api_stats_endpoint(self, fake_app):
        app, fake_hub = fake_app

        with TestClient(app) as client:
            resp = client.get("/api/stats")
            assert resp.status_code == 200
            data = resp.json()
            assert "slots" in data
            assert len(data["slots"]) == NUM_SLOTS
            for slot_stat in data["slots"]:
                assert "messages_per_second" in slot_stat
                assert "avg_processing_ms" in slot_stat

    def test_api_status_endpoint(self, fake_app):
        app, fake_hub = fake_app

        with TestClient(app) as client:
            resp = client.get("/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["gamepad_ready"] is True
            assert len(data["slots"]) == NUM_SLOTS

    def test_invalid_join_rejected(self, fake_app):
        app, fake_hub = fake_app

        with TestClient(app) as client:
            with client.websocket_connect("/ws/play") as ws:
                # Missing name in join violates protocol
                ws.send_text('{"t":"join"}')
                resp = ws.receive_json()
                assert resp["t"] == "error"
                assert "name" in resp.get("message", "").lower()

    def test_host_kick_disconnects_client(self, fake_app):
        app, fake_hub = fake_app

        with TestClient(app) as client:
            with client.websocket_connect("/ws/play") as ws_player:
                ws_player.send_json({"t": "join", "name": "KickTarget", "slot": 0})
                joined = _drain_until(ws_player, "joined")
                assert joined is not None

                # Connect host and kick slot 0
                with client.websocket_connect("/ws/host") as ws_host:
                    ws_host.send_json({"cmd": "kick", "slot": 0})
                    # Player receives kicked message
                    resp = _drain_until(ws_player, "error")
                    assert resp is not None
                    assert "kicked" in resp.get("message", "").lower()
