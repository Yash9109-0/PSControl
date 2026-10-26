"""Tests for server/rooms.py using a fake GamepadHub (no real driver)."""

import json

import pytest

from server.rooms import Room, RoomFullError


class FakeHub:
    """In-memory stand-in for GamepadHub that records release_all calls."""

    def __init__(self):
        self.released = []

    def release_all(self, slot: int):
        self.released.append(slot)

    def swap_slots(self, slot_a: int, slot_b: int):
        pass


class TestJoin:
    def test_assigns_preferred_slot_when_free(self):
        room = Room(FakeHub())
        slot, token = room.join("Alice", None, 2)
        assert slot == 2
        assert isinstance(token, str) and len(token) > 0
        player = room.slots[2]
        assert player["name"] == "Alice"
        assert player["connected"] is True
        assert player["token"] == token
        assert isinstance(player["last_input_time"], float)

    def test_assigns_lowest_free_slot_when_preferred_taken(self):
        room = Room(FakeHub())
        room.join("A", None, 1)
        slot, _ = room.join("B", None, 1)
        assert slot == 0

    def test_ignores_out_of_range_preference(self):
        room = Room(FakeHub())
        room.join("A", None, 1)
        slot, _ = room.join("B", None, 99)
        assert slot == 0

    def test_first_join_gets_slot_zero(self):
        room = Room(FakeHub())
        slot, _ = room.join("A", None, None)
        assert slot == 0

    def test_room_full_raises_clear_error(self):
        room = Room(FakeHub())
        for i, name in enumerate(["A", "B", "C", "D"]):
            room.join(name, None, i)
        with pytest.raises(RoomFullError, match="room full"):
            room.join("E", None, None)

    def test_room_full_message_is_clear(self):
        room = Room(FakeHub())
        for i in range(4):
            room.join(f"P{i}", None, i)
        try:
            room.join("Z", None, None)
        except RoomFullError as exc:
            assert "room full" in str(exc).lower()
        else:  # pragma: no cover - defensive
            pytest.fail("RoomFullError was not raised")

    def test_generates_random_token_per_player(self):
        room = Room(FakeHub())
        _, token_a = room.join("A", None, 0)
        _, token_b = room.join("B", None, 1)
        assert token_a != token_b
        assert room._players_by_token[token_a]["name"] == "A"

    def test_reconnect_within_grace_returns_old_slot(self):
        room = Room(FakeHub())
        slot, token = room.join("Alice", None, 0)
        assert slot == 0

        room.leave(0)
        assert room.slots[0]["connected"] is False

        slot2, token2 = room.join("Alice", token, None)
        assert slot2 == 0  # old slot returned
        assert token2 == token  # same token
        assert room.slots[0]["connected"] is True

    def test_reconnect_uses_lowest_free_slot_if_old_slot_taken(self):
        room = Room(FakeHub())
        slot, token = room.join("Alice", None, 0)
        room.join("Bob", None, 1)
        room.leave(0)
        # Alice's old slot is free, so she still gets it back.
        slot2, _ = room.join("Alice", token, None)
        assert slot2 == 0

    def test_token_from_other_player_is_not_recognized(self):
        room = Room(FakeHub())
        room.join("A", None, 0)
        slot, token = room.join("B", "definitely-unknown-token", None)
        # An unknown token is treated as a fresh player with a new token.
        assert slot == 1
        assert token != "definitely-unknown-token"


class TestLeave:
    def test_release_all_called_immediately(self):
        hub = FakeHub()
        room = Room(hub)
        room.join("A", None, 0)
        room.join("B", None, 3)
        room.leave(0)
        # Slot 0 maps to hub pad 1, released right away.
        assert hub.released == [1]

    def test_marks_player_disconnected_during_grace(self):
        room = Room(FakeHub())
        room.join("A", None, 0)
        room.leave(0)
        player = room.slots[0]
        assert player is not None
        assert player["connected"] is False
        assert player["name"] == "A"
        assert player["left_at"] is not None

    def test_slot_not_reusable_during_grace(self):
        room = Room(FakeHub())
        room.join("A", None, 0)
        room.join("B", None, 1)
        room.leave(1)
        # Slot 1 is reserved during the grace period, so C gets slot 2.
        slot, _ = room.join("C", None, None)
        assert slot == 2
        assert room.slots[1] is not None

    def test_preferred_slot_in_grace_is_skipped(self):
        room = Room(FakeHub())
        room.join("A", None, 1)
        room.leave(1)
        slot, _ = room.join("B", None, 1)  # preferred slot 1 is reserved
        assert slot == 0

    def test_leave_empty_slot_is_noop(self):
        room = Room(FakeHub())
        assert room.leave(2) == 2
        assert room.slots[2] is None

    def test_invalid_slot_raises(self):
        room = Room(FakeHub())
        with pytest.raises(ValueError):
            room.leave(4)
        with pytest.raises(ValueError):
            room.leave(-1)


class TestKick:
    def test_kick_frees_slot_immediately(self):
        hub = FakeHub()
        room = Room(hub)
        _, token = room.join("A", None, 0)
        removed = room.kick(0)
        assert room.slots[0] is None
        assert removed["name"] == "A"
        assert hub.released == [1]
        assert token not in room._players_by_token

    def test_kicked_slot_can_be_reused_right_away(self):
        room = Room(FakeHub())
        room.join("A", None, 0)
        room.kick(0)
        slot, _ = room.join("B", None, 0)
        assert slot == 0

    def test_kick_empty_slot_returns_none(self):
        room = Room(FakeHub())
        assert room.kick(1) is None


class TestSwap:
    def test_swap_exchanges_players(self):
        room = Room(FakeHub())
        room.join("A", None, 0)
        room.join("B", None, 3)
        pa, pb = room.swap(0, 3)
        assert pa["name"] == "A" and pa["slot"] == 3
        assert pb["name"] == "B" and pb["slot"] == 0
        assert room.slots[0]["name"] == "B"
        assert room.slots[3]["name"] == "A"

    def test_swap_requires_both_occupied(self):
        room = Room(FakeHub())
        room.join("A", None, 0)
        with pytest.raises(ValueError, match="both slots must be occupied"):
            room.swap(0, 1)

    def test_swap_invalid_slot_raises(self):
        room = Room(FakeHub())
        with pytest.raises(ValueError):
            room.swap(0, 4)
        with pytest.raises(ValueError):
            room.swap(-1, 0)


class TestTracking:
    def test_per_player_fields_are_tracked(self):
        room = Room(FakeHub())
        slot, token = room.join("Alice", None, 2)
        player = room.slots[slot]
        assert player["name"] == "Alice"
        assert player["slot"] == slot
        assert player["token"] == token
        assert player["connected"] is True
        assert isinstance(player["last_input_time"], float)
        assert player["ping_ms"] is None
        assert player["left_at"] is None

    def test_note_input_updates_last_input_time(self):
        room = Room(FakeHub())
        room.join("A", None, 0)
        first = room.slots[0]["last_input_time"]
        room.note_input(0)
        assert room.slots[0]["last_input_time"] >= first

    def test_set_ping(self):
        room = Room(FakeHub())
        room.join("A", None, 0)
        room.set_ping(0, 42.5)
        assert room.slots[0]["ping_ms"] == 42.5


class TestSnapshot:
    def test_snapshot_is_json_safe(self):
        room = Room(FakeHub())
        room.join("Alice", None, 0)
        room.join("Bob", None, 1)
        room.set_ping(0, 12.5)
        snap = room.snapshot()
        assert len(snap) == 4
        json.dumps(snap)  # must not raise
        assert snap[0] == {
            "slot": 0,
            "name": "Alice",
            "connected": True,
            "ping_ms": 12.5,
            "last_input_time": pytest.approx(snap[0]["last_input_time"]),
        }
        assert snap[1]["name"] == "Bob"
        assert snap[2]["name"] is None
        assert snap[2]["connected"] is False

    def test_snapshot_shows_disconnected_during_grace(self):
        room = Room(FakeHub())
        room.join("A", None, 0)
        room.leave(0)
        snap = room.snapshot()
        assert snap[0]["name"] == "A"
        assert snap[0]["connected"] is False


class TestCheckTimeouts:
    def test_releases_inputs_for_idle_player(self, monkeypatch):
        clock = {"now": 0.0}
        monkeypatch.setattr("server.rooms.time.monotonic", lambda: clock["now"])
        hub = FakeHub()
        room = Room(hub)
        room.join("A", None, 0)
        room.note_input(0)
        clock["now"] = 5.0  # well past INPUT_TIMEOUT_SECONDS (2.0)
        released = room.check_timeouts()
        assert released == [0]
        assert hub.released == [1]

    def test_does_not_release_recent_player(self, monkeypatch):
        clock = {"now": 0.0}
        monkeypatch.setattr("server.rooms.time.monotonic", lambda: clock["now"])
        hub = FakeHub()
        room = Room(hub)
        room.join("A", None, 0)
        room.note_input(0)
        clock["now"] = 1.0  # within INPUT_TIMEOUT_SECONDS
        assert room.check_timeouts() == []
        assert hub.released == []

    def test_only_idle_players_are_released(self, monkeypatch):
        clock = {"now": 0.0}
        monkeypatch.setattr("server.rooms.time.monotonic", lambda: clock["now"])
        hub = FakeHub()
        room = Room(hub)
        room.join("A", None, 0)
        room.join("B", None, 1)
        room.note_input(0)
        clock["now"] = 4.9
        room.note_input(1)  # B is recent
        clock["now"] = 5.0  # A is idle (5.0 > INPUT_TIMEOUT_SECONDS), B is not
        released = room.check_timeouts()
        assert released == [0]
        assert hub.released == [1]  # slot 0 -> pad 1

    def test_grace_period_slot_is_not_timed_out(self, monkeypatch):
        clock = {"now": 0.0}
        monkeypatch.setattr("server.rooms.time.monotonic", lambda: clock["now"])
        hub = FakeHub()
        room = Room(hub)
        room.join("A", None, 0)
        room.leave(0)  # connected False; release_all already called once
        assert hub.released == [1]
        clock["now"] = 5.0
        # A left-connected players are skipped by check_timeouts.
        assert room.check_timeouts() == []
        assert hub.released == [1]  # no additional releases

    def test_no_repeated_release_on_timeout(self, monkeypatch):
        clock = {"now": 0.0}
        monkeypatch.setattr("server.rooms.time.monotonic", lambda: clock["now"])
        hub = FakeHub()
        room = Room(hub)
        room.join("A", None, 0)
        room.note_input(0)
        clock["now"] = 5.0
        assert room.check_timeouts() == [0]
        assert hub.released == [1]

        # Second check: already timed out, so release_all is NOT spammed
        assert room.check_timeouts() == []
        assert hub.released == [1]
