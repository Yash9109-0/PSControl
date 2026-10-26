"""Virtual gamepad interface using vgamepad to send inputs to ViGEmBus."""

import sys

try:
    import vgamepad
    from vgamepad import VX360Gamepad, XUSB_BUTTON
except ImportError:
    print("vgamepad not installed. Install with: pip install vgamepad")
    sys.exit(1)
except Exception as e:
    print(f"Failed to initialize vgamepad: {e}")
    print("ViGEmBus driver may not be installed.")
    print("Download and install from: https://github.com/ViGEm/ViGEmBus/releases")
    sys.exit(1)


class GamepadHub:
    BUTTON_MAP = {
        "CROSS": XUSB_BUTTON.XUSB_GAMEPAD_A,
        "CIRCLE": XUSB_BUTTON.XUSB_GAMEPAD_B,
        "SQUARE": XUSB_BUTTON.XUSB_GAMEPAD_X,
        "TRIANGLE": XUSB_BUTTON.XUSB_GAMEPAD_Y,
        "L1": XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
        "R1": XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
        "SELECT": XUSB_BUTTON.XUSB_GAMEPAD_BACK,
        "START": XUSB_BUTTON.XUSB_GAMEPAD_START,
        "L3": XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB,
        "R3": XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB,
        "UP": XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
        "DOWN": XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
        "LEFT": XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
        "RIGHT": XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
    }

    def __init__(self):
        self._pads = []
        self._last_states = []
        for i in range(4):
            try:
                pad = VX360Gamepad()
                self._pads.append(pad)
                self._last_states.append({
                    "buttons": 0,
                    "lx": 0,
                    "ly": 0,
                    "rx": 0,
                    "ry": 0,
                    "lt": 0,
                    "rt": 0,
                })
            except Exception as e:
                print(f"Failed to create virtual gamepad {i+1}: {e}")
                print("ViGEmBus driver may not be installed.")
                print("Download and install from: https://github.com/ViGEm/ViGEmBus/releases")
                self.close()
                raise

    def _axis_to_short(self, value: int) -> int:
        """Convert -100..100 to -32768..32767."""
        return int(max(-32768, min(32767, value * 327.67)))

    def _apply_buttons(self, pad: VX360Gamepad, buttons_bitmask: int):
        for name, xusb_btn in self.BUTTON_MAP.items():
            bit = getattr(self, f"_BIT_{name}", None)
            if bit is None:
                continue
            if buttons_bitmask & bit:
                pad.press_button(button=xusb_btn)
            else:
                pad.release_button(button=xusb_btn)

    def apply_state(self, slot: int, buttons_bitmask: int, lx: int, ly: int, rx: int, ry: int):
        """Apply state to virtual pad at slot (1-4), then call update() once if changed."""
        if not 1 <= slot <= 4:
            raise ValueError("Slot must be 1-4")
        idx = slot - 1
        pad = self._pads[idx]
        last = self._last_states[idx]

        new_buttons = buttons_bitmask
        new_lx = self._axis_to_short(lx)
        new_ly = self._axis_to_short(-ly)
        new_rx = self._axis_to_short(rx)
        new_ry = self._axis_to_short(-ry)

        lt = 255 if (buttons_bitmask & self._BIT_L2) else 0
        rt = 255 if (buttons_bitmask & self._BIT_R2) else 0

        if (last["buttons"] == new_buttons and
            last["lx"] == new_lx and last["ly"] == new_ly and
            last["rx"] == new_rx and last["ry"] == new_ry and
            last["lt"] == lt and last["rt"] == rt):
            return

        for name, xusb_btn in self.BUTTON_MAP.items():
            bit = getattr(self, f"_BIT_{name}", 0)
            if buttons_bitmask & bit:
                pad.press_button(button=xusb_btn)
            else:
                pad.release_button(button=xusb_btn)

        pad.left_joystick(x_value=new_lx, y_value=new_ly)
        pad.right_joystick(x_value=new_rx, y_value=new_ry)
        pad.left_trigger(value=lt)
        pad.right_trigger(value=rt)

        try:
            pad.update()
            last["buttons"] = new_buttons
            last["lx"] = new_lx
            last["ly"] = new_ly
            last["rx"] = new_rx
            last["ry"] = new_ry
            last["lt"] = lt
            last["rt"] = rt
        except Exception:
            # On update failure, invalidate cache to force re-send next time
            last["buttons"] = -1
            raise

    def swap_slots(self, slot_a: int, slot_b: int) -> None:
        """Swap the cached states between two 0-indexed slots (0-3)."""
        if 0 <= slot_a < len(self._last_states) and 0 <= slot_b < len(self._last_states):
            self._last_states[slot_a], self._last_states[slot_b] = (
                self._last_states[slot_b],
                self._last_states[slot_a],
            )

    def release_all(self, slot: int):
        """Release all buttons, center sticks, set triggers to 0, and update."""
        if not 1 <= slot <= 4:
            raise ValueError("Slot must be 1-4")
        idx = slot - 1
        pad = self._pads[idx]

        for xusb_btn in self.BUTTON_MAP.values():
            pad.release_button(button=xusb_btn)

        pad.left_joystick(x_value=0, y_value=0)
        pad.right_joystick(x_value=0, y_value=0)
        pad.left_trigger(value=0)
        pad.right_trigger(value=0)

        pad.update()

        last = self._last_states[idx]
        last["buttons"] = 0
        last["lx"] = 0
        last["ly"] = 0
        last["rx"] = 0
        last["ry"] = 0
        last["lt"] = 0
        last["rt"] = 0

    def close(self):
        """Release and remove all pads."""
        for pad in self._pads:
            try:
                pad.reset()
            except Exception:
                pass
        self._pads.clear()
        self._last_states.clear()

    _BIT_CROSS = 1 << 0
    _BIT_CIRCLE = 1 << 1
    _BIT_SQUARE = 1 << 2
    _BIT_TRIANGLE = 1 << 3
    _BIT_L1 = 1 << 4
    _BIT_R1 = 1 << 5
    _BIT_L2 = 1 << 6
    _BIT_R2 = 1 << 7
    _BIT_SELECT = 1 << 8
    _BIT_START = 1 << 9
    _BIT_L3 = 1 << 10
    _BIT_R3 = 1 << 11
    _BIT_UP = 1 << 12
    _BIT_DOWN = 1 << 13
    _BIT_LEFT = 1 << 14
    _BIT_RIGHT = 1 << 15