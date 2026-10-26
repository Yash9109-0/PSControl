"""Protocol definitions for WebSocket messages between phone controllers and server."""

MAX_RAW_SIZE = 512
MAX_NAME_LENGTH = 16

BUTTON_CROSS = 1 << 0
BUTTON_CIRCLE = 1 << 1
BUTTON_SQUARE = 1 << 2
BUTTON_TRIANGLE = 1 << 3
BUTTON_L1 = 1 << 4
BUTTON_R1 = 1 << 5
BUTTON_L2 = 1 << 6
BUTTON_R2 = 1 << 7
BUTTON_SELECT = 1 << 8
BUTTON_START = 1 << 9
BUTTON_L3 = 1 << 10
BUTTON_R3 = 1 << 11
BUTTON_UP = 1 << 12
BUTTON_DOWN = 1 << 13
BUTTON_LEFT = 1 << 14
BUTTON_RIGHT = 1 << 15

BUTTON_MASK_ALL = (1 << 16) - 1

BUTTON_NAMES = {
    "cross": BUTTON_CROSS,
    "circle": BUTTON_CIRCLE,
    "square": BUTTON_SQUARE,
    "triangle": BUTTON_TRIANGLE,
    "l1": BUTTON_L1,
    "r1": BUTTON_R1,
    "l2": BUTTON_L2,
    "r2": BUTTON_R2,
    "select": BUTTON_SELECT,
    "start": BUTTON_START,
    "l3": BUTTON_L3,
    "r3": BUTTON_R3,
    "up": BUTTON_UP,
    "down": BUTTON_DOWN,
    "left": BUTTON_LEFT,
    "right": BUTTON_RIGHT,
}

AXIS_MIN = -100
AXIS_MAX = 100

MSG_TYPE_JOIN = "join"
MSG_TYPE_IN = "in"
MSG_TYPE_PING = "ping"


class ProtocolError(Exception):
    """Raised when a message fails protocol validation."""
    pass


def _clamp_axis(value: int) -> int:
    return max(AXIS_MIN, min(AXIS_MAX, value))


def parse_message(raw: str) -> dict:
    if not isinstance(raw, str):
        raise ProtocolError("Message must be a string")
    if len(raw.encode("utf-8")) > MAX_RAW_SIZE:
        raise ProtocolError(f"Message exceeds maximum size of {MAX_RAW_SIZE} bytes")
    if not raw.strip():
        raise ProtocolError("Empty message")

    import json
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ProtocolError(f"Invalid JSON: {e}") from e

    if not isinstance(msg, dict):
        raise ProtocolError("Message must be a JSON object")

    msg_type = msg.get("t")
    if msg_type not in (MSG_TYPE_JOIN, MSG_TYPE_IN, MSG_TYPE_PING):
        raise ProtocolError(f"Unknown message type: {msg_type}")

    if msg_type == MSG_TYPE_JOIN:
        name = msg.get("name")
        if not isinstance(name, str):
            raise ProtocolError("Join requires 'name' string")
        name = name.strip()
        if not name:
            raise ProtocolError("Name cannot be empty")
        if len(name) > MAX_NAME_LENGTH:
            raise ProtocolError(f"Name exceeds maximum length of {MAX_NAME_LENGTH}")
        token = msg.get("token")
        if token is not None and not isinstance(token, str):
            raise ProtocolError("Token must be string or null")
        slot = msg.get("slot")
        if slot is not None and not isinstance(slot, int):
            raise ProtocolError("Slot must be integer or null")
        return {
            "t": MSG_TYPE_JOIN,
            "name": name,
            "token": token,
            "slot": slot,
        }

    if msg_type == MSG_TYPE_IN:
        seq = msg.get("seq")
        if not isinstance(seq, int) or seq < 0:
            raise ProtocolError("seq must be non-negative integer")
        b = msg.get("b")
        if not isinstance(b, int) or b < 0 or b > BUTTON_MASK_ALL:
            raise ProtocolError(f"b must be integer 0..{BUTTON_MASK_ALL}")
        lx = msg.get("lx")
        ly = msg.get("ly")
        rx = msg.get("rx")
        ry = msg.get("ry")
        if not all(isinstance(v, int) for v in (lx, ly, rx, ry)):
            raise ProtocolError("All axes must be integers")
        return {
            "t": MSG_TYPE_IN,
            "seq": seq,
            "b": b,
            "lx": _clamp_axis(lx),
            "ly": _clamp_axis(ly),
            "rx": _clamp_axis(rx),
            "ry": _clamp_axis(ry),
        }

    if msg_type == MSG_TYPE_PING:
        c = msg.get("c")
        if not isinstance(c, (int, float)):
            raise ProtocolError("Ping requires numeric 'c'")
        return {
            "t": MSG_TYPE_PING,
            "c": c,
        }

    raise ProtocolError(f"Unknown message type: {msg_type}")