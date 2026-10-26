# ps2-party-pad

## Project Goal
Enable local multiplayer PS2 gaming on PCSX2 by using phones as controllers. Up to 4 players connect via WebSocket to a Python server that translates their touch inputs into virtual gamepad signals via ViGEmBus.

## Architecture
```
Phone Controller Page (WebSocket)
        ↓
Python FastAPI Server (WebSocket handler)
        ↓
vgamepad library
        ↓
ViGEmBus kernel driver
        ↓
PCSX2 with Multitap (4 virtual controllers)
```

## Folder Structure
```
controller/
├── server/                 # Python FastAPI backend
│   ├── __init__.py        # Package marker
│   ├── __main__.py        # Run with: python -m server
│   ├── main.py            # Application entry point & WebSockets
│   ├── config.py          # Configuration constants
│   ├── protocol.py        # WebSocket message parser & validation
│   ├── rooms.py           # Multiplayer room management
│   ├── gamepad.py         # vgamepad virtual controller interface
│   └── net_utils.py       # Network/websocket utilities
├── web/
│   ├── controller/        # Phone controller HTML/JS/CSS
│   ├── host/              # Host session management dashboard
│   └── static/            # Shared static assets (styles, scripts)
├── tools/                 # Development & test utilities
│   ├── fake_client.py     # Multi-mode client simulator (smoke, stress, drop)
│   └── test_pads.py       # Virtual gamepad verification utility
├── scripts/               # Helper scripts
│   ├── start.bat          # Launch server, venv setup, open dashboard
│   └── open_firewall.bat  # Add Windows Firewall rule for port 8000
├── docs/                  # Documentation
│   ├── NETWORK_SETUP.md   # Wi-Fi / Hotspot setup guide
│   └── PCSX2_SETUP.md     # PCSX2 2.x Multitap controller mapping
├── tests/                 # Pytest test suite
│   ├── test_integration.py# End-to-end WebSocket client tests
│   ├── test_protocol.py   # Protocol serialization & validation tests
│   └── test_rooms.py      # Room allocation, timeout & grace period tests
├── requirements.txt       # Python dependencies
└── README.md              # This file
```

## Run Instructions

1. Install [ViGEmBus](https://github.com/ViGEm/ViGEmBus/releases) (virtual gamepad driver).
2. Double-click `scripts\start.bat` — it installs Python dependencies and starts the server.
3. Open the Join URL on each player's phone.

See [`docs/NETWORK_SETUP.md`](docs/NETWORK_SETUP.md) for Wi-Fi/hotspot setup and [`docs/PCSX2_SETUP.md`](docs/PCSX2_SETUP.md) for PCSX2 controller mapping.

## Troubleshooting

### 1. Cannot reach the server from a phone
- Make sure the PC and phone are on the **same Wi-Fi or hotspot**. College/hotel Wi-Fi often blocks device-to-device traffic (client isolation). Use a personal hotspot instead — see [`docs/NETWORK_SETUP.md`](docs/NETWORK_SETUP.md).
- Confirm the Join URL is correct. The IP changes when you switch networks — restart `start.bat` to get a fresh URL.
- Try opening the Join URL in the phone's browser. If the page doesn't load, it's a network problem, not a server problem.

### 2. Windows Firewall is blocking connections
- Run **`scripts\open_firewall.bat`** as administrator. This adds an inbound rule for TCP port 8000 on private networks.
- If you use a third-party firewall (Norton, Kaspersky, etc.), you'll also need to allow TCP 8000 in that software.

### 3. Wrong IP address / "localhost" in the Join URL
- If the console shows `http://127.0.0.1:8000/` instead of a LAN IP like `http://192.168.x.x:8000/`, the PC isn't connected to a network the phones can reach. Connect to a hotspot first, then restart the server.

### 4. Laggy or delayed input
- Use a **5 GHz** hotspot if possible — 2.4 GHz adds latency.
- Close other bandwidth-heavy apps on the PC and phones.
- Check the host dashboard for ping times. If a player's ping is above 50 ms, the network is the bottleneck.
- Try a dedicated hotspot (travel router or spare phone) instead of Windows Mobile Hotspot.

### 5. A button is stuck / character keeps moving
- This usually means a phone disconnected mid-press. The server auto-releases all buttons after 2 seconds of silence. Wait briefly and the stuck input should clear.
- If it persists, kick the player from the host dashboard and have them rejoin.
- Restarting the server always resets all virtual pads.

### 6. Room full — cannot join
- The server supports **4 players maximum**. A 5th phone will get a "room full" error.
- After a player disconnects, their slot is reserved for 60 seconds in case they reconnect (e.g., page refresh). Wait for the grace period to expire, or kick the ghost player from the host dashboard.

### 7. Pad not showing in PCSX2
- **Start the server before launching PCSX2.** The server creates 4 virtual Xbox 360 controllers at startup. PCSX2 scans for controllers when it opens — if the server isn't running yet, PCSX2 won't see them.
- If you already launched PCSX2 first, close it, make sure the server is running, and relaunch PCSX2.
- See [`docs/PCSX2_SETUP.md`](docs/PCSX2_SETUP.md) for the full setup walkthrough.

### 8. ViGEmBus not installed
- The `start.bat` console will print a warning if ViGEmBus is not detected. The server still starts (so you can test the web UI), but virtual gamepads won't work.
- Download and install from: https://github.com/ViGEm/ViGEmBus/releases
- Reboot after installation, then run `start.bat` again.