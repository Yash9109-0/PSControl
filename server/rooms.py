"""Room management for the PS2 party pad server.

A :class:`Room` manages four gamepad slots (0-3) and the players bound to
them. It owns all slot/bookkeeping logic; the actual virtual pads live in
a ``GamepadHub`` passed in at construction time, which makes the room easy
to test with a fake hub (no real driver needed).
"""

from __future__ import annotations

import secrets
import time
from typing import Optional

from server.config import INPUT_TIMEOUT_SECONDS, MAX_PLAYERS
from server.gamepad import GamepadHub


NUM_SLOTS = MAX_PLAYERS
GRACE_SECONDS = 60.0


class RoomFullError(Exception):
    """Raised when a player tries to join a room that has no free slot."""


class Room:
    """Four-slot gamepad room with a reconnect grace period."""

    def __init__(self, hub: GamepadHub):
        self.hub = hub
        # slots[i] is a player dict or None while the slot is free.
        self.slots: list[Optional[dict]] = [None] * NUM_SLOTS
        # token -> player, for players connected or inside the grace period.
        self._players_by_token: dict[str, dict] = {}

    # -- clock -----------------------------------------------------------

    def _now(self) -> float:
        return time.monotonic()

    # -- internal helpers ------------------------------------------------

    def _validate_slot(self, slot: int) -> None:
        if not isinstance(slot, int) or isinstance(slot, bool):
            raise ValueError("slot must be an integer between 0 and 3")
        if not 0 <= slot < NUM_SLOTS:
            raise ValueError("slot must be an integer between 0 and 3")

    def _reap_grace_periods(self, now: float) -> None:
        """Permanently free slots whose 60 s reconnect grace expired."""
        for idx in range(NUM_SLOTS):
            player = self.slots[idx]
            if player is None or player["left_at"] is None:
                continue
            if now - player["left_at"] >= GRACE_SECONDS:
                self.slots[idx] = None
                self._players_by_token.pop(player["token"], None)

    def _slot_free(self, idx: int, now: float) -> bool:
        """True if a new player may take slot ``idx`` right now."""
        player = self.slots[idx]
        if player is None:
            return True
        if player["left_at"] is not None and now - player["left_at"] >= GRACE_SECONDS:
            return True  # grace expired; will be reaped on the next sweep
        return False

    def _pick_slot(self, preferred_slot: Optional[int], now: float) -> Optional[int]:
        order: list[int] = []
        if (
            isinstance(preferred_slot, int)
            and not isinstance(preferred_slot, bool)
            and 0 <= preferred_slot < NUM_SLOTS
        ):
            order.append(preferred_slot)
        order.extend(i for i in range(NUM_SLOTS) if i not in order)
        for idx in order:
            if self._slot_free(idx, now):
                return idx
        return None
    # -- public API ------------------------------------------------------

    def join(self, name: str, token: Optional[str], preferred_slot: Optional[int]):
        """Add a player to the room.

        Returns ``(slot, token)``. A known token (page refresh or reconnect
        within the grace period) gets its old slot back. Otherwise the
        preferred slot is used if free, else the lowest free slot. Raises
        :class:`RoomFullError` when no slot is available.
        """
        now = self._now()
        self._reap_grace_periods(now)

        # Reconnecting player: give back their old slot.
        if token is not None and token in self._players_by_token:
            player = self._players_by_token[token]
            slot = player["slot"]
            player["connected"] = True
            player["left_at"] = None
            player["last_input_time"] = now
            player["name"] = name
            player["timed_out"] = False
            return slot, player["token"]

        slot = self._pick_slot(preferred_slot, now)
        if slot is None:
            raise RoomFullError("room full")

        new_token = secrets.token_hex(16)
        player = {
            "name": name,
            "slot": slot,
            "token": new_token,
            "last_input_time": now,
            "ping_ms": None,
            "connected": True,
            "left_at": None,
            "timed_out": False,
        }
        self.slots[slot] = player
        self._players_by_token[new_token] = player
        return slot, new_token

    def leave(self, slot: int) -> int:
        """Mark ``slot`` free after the grace period; release its pad now.

        The slot stays reserved for the leaving player for
        :data:`GRACE_SECONDS` so a reconnect with the same token gets it
        back. :meth:`hub.release_all` is called immediately on the pad.
        """
        self._validate_slot(slot)
        now = self._now()
        self._reap_grace_periods(now)

        player = self.slots[slot]
        if player is None:
            return slot

        self.hub.release_all(slot + 1)  # hub pads are 1-based
        player["connected"] = False
        player["left_at"] = now
        return slot

    def kick(self, slot: int) -> Optional[dict]:
        """Remove the player in ``slot`` immediately (host dashboard)."""
        self._validate_slot(slot)
        player = self.slots[slot]
        if player is None:
            return None
        self.hub.release_all(slot + 1)
        player["connected"] = False
        self.slots[slot] = None
        self._players_by_token.pop(player["token"], None)
        return player

    def swap(self, slot_a: int, slot_b: int):
        """Exchange the players in two slots (host dashboard)."""
        self._validate_slot(slot_a)
        self._validate_slot(slot_b)
        if slot_a == slot_b:
            return
        player_a = self.slots[slot_a]
        player_b = self.slots[slot_b]
        if player_a is None or player_b is None:
            raise ValueError("both slots must be occupied to swap")
        self.slots[slot_a] = player_b
        self.slots[slot_b] = player_a
        player_a["slot"] = slot_b
        player_b["slot"] = slot_a
        if hasattr(self.hub, "swap_slots"):
            try:
                self.hub.swap_slots(slot_a, slot_b)
            except Exception:
                pass
        return player_a, player_b

    def note_input(self, slot: int) -> None:
        """Record that the player in ``slot`` just sent an input message."""
        self._validate_slot(slot)
        player = self.slots[slot]
        if player is not None:
            player["last_input_time"] = self._now()
            player["timed_out"] = False

    def set_ping(self, slot: int, ping_ms: float) -> None:
        """Store the last measured round-trip ping for ``slot``."""
        self._validate_slot(slot)
        player = self.slots[slot]
        if player is not None:
            player["ping_ms"] = ping_ms

    def check_timeouts(self) -> list[int]:
        """Release all inputs of players silent longer than INPUT_TIMEOUT_SECONDS.

        Returns the list of slots whose pads were released.
        """
        now = self._now()
        self._reap_grace_periods(now)
        released: list[int] = []
        for player in self.slots:
            if player is None or not player["connected"]:
                continue
            if player.get("timed_out"):
                continue
            last = player["last_input_time"]
            if last is None:
                continue
            if now - last > INPUT_TIMEOUT_SECONDS:
                self.hub.release_all(player["slot"] + 1)
                player["timed_out"] = True
                released.append(player["slot"])
        return released

    def snapshot(self) -> list[dict]:
        """JSON-safe description of all four slots for broadcasting."""
        now = self._now()
        self._reap_grace_periods(now)
        result: list[dict] = []
        for idx in range(NUM_SLOTS):
            player = self.slots[idx]
            if player is None:
                result.append({
                    "slot": idx,
                    "name": None,
                    "connected": False,
                    "ping_ms": None,
                    "last_input_time": None,
                })
            else:
                result.append({
                    "slot": idx,
                    "name": player["name"],
                    "connected": bool(player["connected"]),
                    "ping_ms": player["ping_ms"],
                    "last_input_time": player["last_input_time"],
                })
        return result