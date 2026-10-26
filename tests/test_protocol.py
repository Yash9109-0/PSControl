"""Tests for server/protocol.py"""

import pytest
from server.protocol import (
    parse_message,
    ProtocolError,
    BUTTON_CROSS,
    BUTTON_CIRCLE,
    BUTTON_SQUARE,
    BUTTON_TRIANGLE,
    BUTTON_L1,
    BUTTON_R1,
    BUTTON_L2,
    BUTTON_R2,
    BUTTON_SELECT,
    BUTTON_START,
    BUTTON_L3,
    BUTTON_R3,
    BUTTON_UP,
    BUTTON_DOWN,
    BUTTON_LEFT,
    BUTTON_RIGHT,
    BUTTON_MASK_ALL,
    AXIS_MIN,
    AXIS_MAX,
    MAX_RAW_SIZE,
    MAX_NAME_LENGTH,
)


class TestJoinMessage:
    def test_valid_join_minimal(self):
        msg = parse_message('{"t":"join","name":"Player1"}')
        assert msg["t"] == "join"
        assert msg["name"] == "Player1"
        assert msg["token"] is None
        assert msg["slot"] is None

    def test_valid_join_with_token_and_slot(self):
        msg = parse_message('{"t":"join","name":"Player2","token":"abc123","slot":0}')
        assert msg["name"] == "Player2"
        assert msg["token"] == "abc123"
        assert msg["slot"] == 0

    def test_join_strips_whitespace(self):
        msg = parse_message('{"t":"join","name":"  Player  "}')
        assert msg["name"] == "Player"

    def test_join_name_too_long(self):
        with pytest.raises(ProtocolError, match="exceeds maximum length"):
            parse_message(f'{{"t":"join","name":"{"A" * (MAX_NAME_LENGTH + 1)}"}}')

    def test_join_empty_name(self):
        with pytest.raises(ProtocolError, match="cannot be empty"):
            parse_message('{"t":"join","name":""}')

    def test_join_name_not_string(self):
        with pytest.raises(ProtocolError, match="name.*string"):
            parse_message('{"t":"join","name":123}')

    def test_join_token_not_string(self):
        with pytest.raises(ProtocolError, match="Token must be string"):
            parse_message('{"t":"join","name":"P","token":123}')

    def test_join_slot_not_int(self):
        with pytest.raises(ProtocolError, match="Slot must be integer"):
            parse_message('{"t":"join","name":"P","slot":"0"}')


class TestInputMessage:
    def test_valid_input_all_axes_centered(self):
        msg = parse_message('{"t":"in","seq":1,"b":0,"lx":0,"ly":0,"rx":0,"ry":0}')
        assert msg["seq"] == 1
        assert msg["b"] == 0
        assert msg["lx"] == 0
        assert msg["ly"] == 0
        assert msg["rx"] == 0
        assert msg["ry"] == 0

    def test_valid_input_with_buttons_and_axes(self):
        buttons = BUTTON_CROSS | BUTTON_CIRCLE | BUTTON_L1 | BUTTON_UP
        msg = parse_message(f'{{"t":"in","seq":5,"b":{buttons},"lx":50,"ly":-30,"rx":100,"ry":-100}}')
        assert msg["seq"] == 5
        assert msg["b"] == buttons
        assert msg["lx"] == 50
        assert msg["ly"] == -30
        assert msg["rx"] == 100
        assert msg["ry"] == -100

    def test_input_axes_clamped_to_max(self):
        msg = parse_message('{"t":"in","seq":1,"b":0,"lx":200,"ly":150,"rx":300,"ry":1000}')
        assert msg["lx"] == AXIS_MAX
        assert msg["ly"] == AXIS_MAX
        assert msg["rx"] == AXIS_MAX
        assert msg["ry"] == AXIS_MAX

    def test_input_axes_clamped_to_min(self):
        msg = parse_message('{"t":"in","seq":1,"b":0,"lx":-200,"ly":-150,"rx":-300,"ry":-1000}')
        assert msg["lx"] == AXIS_MIN
        assert msg["ly"] == AXIS_MIN
        assert msg["rx"] == AXIS_MIN
        assert msg["ry"] == AXIS_MIN

    def test_input_seq_negative(self):
        with pytest.raises(ProtocolError, match="non-negative"):
            parse_message('{"t":"in","seq":-1,"b":0,"lx":0,"ly":0,"rx":0,"ry":0}')

    def test_input_seq_not_int(self):
        with pytest.raises(ProtocolError, match="non-negative integer"):
            parse_message('{"t":"in","seq":1.5,"b":0,"lx":0,"ly":0,"rx":0,"ry":0}')

    def test_input_buttons_out_of_range_high(self):
        with pytest.raises(ProtocolError, match=f"0..{BUTTON_MASK_ALL}"):
            parse_message(f'{{"t":"in","seq":1,"b":{BUTTON_MASK_ALL + 1},"lx":0,"ly":0,"rx":0,"ry":0}}')

    def test_input_buttons_negative(self):
        with pytest.raises(ProtocolError, match=f"0..{BUTTON_MASK_ALL}"):
            parse_message('{"t":"in","seq":1,"b":-1,"lx":0,"ly":0,"rx":0,"ry":0}')

    def test_input_axes_not_int(self):
        with pytest.raises(ProtocolError, match="All axes must be integers"):
            parse_message('{"t":"in","seq":1,"b":0,"lx":0.5,"ly":0,"rx":0,"ry":0}')


class TestPingMessage:
    def test_valid_ping_int(self):
        msg = parse_message('{"t":"ping","c":123}')
        assert msg["c"] == 123

    def test_valid_ping_float(self):
        msg = parse_message('{"t":"ping","c":123.45}')
        assert msg["c"] == 123.45

    def test_ping_missing_c(self):
        with pytest.raises(ProtocolError, match="numeric"):
            parse_message('{"t":"ping"}')

    def test_ping_c_not_numeric(self):
        with pytest.raises(ProtocolError, match="numeric"):
            parse_message('{"t":"ping","c":"abc"}')


class TestSizeLimits:
    def test_oversized_message(self):
        large_name = "A" * (MAX_RAW_SIZE + 10)
        with pytest.raises(ProtocolError, match="exceeds maximum size"):
            parse_message(f'{{"t":"join","name":"{large_name}"}}')

    def test_exactly_max_size(self):
        payload = '{"t":"join","name":"' + "A" * MAX_NAME_LENGTH + '"}'
        assert len(payload.encode("utf-8")) <= MAX_RAW_SIZE
        msg = parse_message(payload)
        assert msg["name"] == "A" * MAX_NAME_LENGTH


class TestUnknownTypes:
    def test_unknown_type(self):
        with pytest.raises(ProtocolError, match="Unknown message type"):
            parse_message('{"t":"unknown"}')

    def test_missing_type(self):
        with pytest.raises(ProtocolError, match="Unknown message type"):
            parse_message('{}')

    def test_type_not_string(self):
        with pytest.raises(ProtocolError, match="Unknown message type"):
            parse_message('{"t":123}')


class TestInvalidJSON:
    def test_invalid_json(self):
        with pytest.raises(ProtocolError, match="Invalid JSON"):
            parse_message('not json')

    def test_json_not_object(self):
        with pytest.raises(ProtocolError, match="JSON object"):
            parse_message('["array"]')

    def test_empty_message(self):
        with pytest.raises(ProtocolError, match="Empty message"):
            parse_message("")

    def test_whitespace_only(self):
        with pytest.raises(ProtocolError, match="Empty message"):
            parse_message("   ")


class TestButtonConstants:
    def test_button_bitmasks(self):
        assert BUTTON_CROSS == 1 << 0
        assert BUTTON_CIRCLE == 1 << 1
        assert BUTTON_SQUARE == 1 << 2
        assert BUTTON_TRIANGLE == 1 << 3
        assert BUTTON_L1 == 1 << 4
        assert BUTTON_R1 == 1 << 5
        assert BUTTON_L2 == 1 << 6
        assert BUTTON_R2 == 1 << 7
        assert BUTTON_SELECT == 1 << 8
        assert BUTTON_START == 1 << 9
        assert BUTTON_L3 == 1 << 10
        assert BUTTON_R3 == 1 << 11
        assert BUTTON_UP == 1 << 12
        assert BUTTON_DOWN == 1 << 13
        assert BUTTON_LEFT == 1 << 14
        assert BUTTON_RIGHT == 1 << 15

    def test_button_mask_all(self):
        assert BUTTON_MASK_ALL == (1 << 16) - 1


class TestAxisConstants:
    def test_axis_bounds(self):
        assert AXIS_MIN == -100
        assert AXIS_MAX == 100