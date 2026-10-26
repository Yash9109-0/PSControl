#!/usr/bin/env python3
"""Test script to verify virtual gamepads work in Windows game controller settings (joy.cpl)."""

import sys
import time
from pathlib import Path

# Add parent directory to path so we can import server.gamepad
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from server.gamepad import GamepadHub
except ImportError as e:
    print(f"Failed to import GamepadHub: {e}")
    print("Make sure you're running from the controller directory and dependencies are installed.")
    sys.exit(1)


def main():
    print("Creating GamepadHub with 4 virtual Xbox 360 pads...")
    try:
        hub = GamepadHub()
    except Exception as e:
        print(f"Failed to create GamepadHub: {e}")
        print("\nViGEmBus driver may not be installed.")
        print("Download and install from: https://github.com/ViGEm/ViGEmBus/releases")
        sys.exit(1)

    print("GamepadHub created successfully.")
    print("Testing pad 1 (slot 1) - each button pressed for 0.5 seconds")
    print("Open joy.cpl to verify the inputs.")
    print()

    buttons_to_test = [
        ("CROSS (A)", GamepadHub._BIT_CROSS),
        ("CIRCLE (B)", GamepadHub._BIT_CIRCLE),
        ("SQUARE (X)", GamepadHub._BIT_SQUARE),
        ("TRIANGLE (Y)", GamepadHub._BIT_TRIANGLE),
        ("L1 (Left Shoulder)", GamepadHub._BIT_L1),
        ("R1 (Right Shoulder)", GamepadHub._BIT_R1),
        ("L2 (Left Trigger)", GamepadHub._BIT_L2),
        ("R2 (Right Trigger)", GamepadHub._BIT_R2),
        ("SELECT (Back)", GamepadHub._BIT_SELECT),
        ("START (Start)", GamepadHub._BIT_START),
        ("L3 (Left Thumb)", GamepadHub._BIT_L3),
        ("R3 (Right Thumb)", GamepadHub._BIT_R3),
        ("UP (D-pad Up)", GamepadHub._BIT_UP),
        ("DOWN (D-pad Down)", GamepadHub._BIT_DOWN),
        ("LEFT (D-pad Left)", GamepadHub._BIT_LEFT),
        ("RIGHT (D-pad Right)", GamepadHub._BIT_RIGHT),
    ]

    slot = 1

    try:
        for name, bit in buttons_to_test:
            print(f"Pressing {name}...")
            hub.apply_state(slot, bit, 0, 0, 0, 0)
            time.sleep(0.5)
            hub.release_all(slot)
            time.sleep(0.1)

        print("\nTesting left stick movement...")
        for x, y, desc in [
            (100, 0, "Right"),
            (-100, 0, "Left"),
            (0, 100, "Up (inverted Y)"),
            (0, -100, "Down (inverted Y)"),
            (0, 0, "Center"),
        ]:
            print(f"  Left stick {desc}...")
            hub.apply_state(slot, 0, x, y, 0, 0)
            time.sleep(0.5)

        print("\nTesting right stick movement...")
        for x, y, desc in [
            (100, 0, "Right"),
            (-100, 0, "Left"),
            (0, 100, "Up (inverted Y)"),
            (0, -100, "Down (inverted Y)"),
            (0, 0, "Center"),
        ]:
            print(f"  Right stick {desc}...")
            hub.apply_state(slot, 0, 0, 0, x, y)
            time.sleep(0.5)

        print("\nAll tests complete. Check joy.cpl to verify.")
    finally:
        print("Closing GamepadHub...")
        hub.close()
        print("Done.")


if __name__ == "__main__":
    main()