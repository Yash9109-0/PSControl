# PCSX2 Controller Setup Guide

This guide walks you through configuring **PCSX2 2.x on Windows** so that up to 4 players can use their phones as PS2 controllers via ps2-party-pad.

> [!NOTE]
> Menu names can differ slightly between PCSX2 releases (e.g. "Controller Settings" vs "Controllers", "Global Settings" vs "Controller Global Settings"). If you can't find something mentioned here, click the **search / filter box** at the top of the PCSX2 Settings window and type a keyword like "multitap" or "controller type."

---

## Before You Start — Why the Server Must Run First

When the server starts (`scripts\start.bat`), it creates **all 4 virtual Xbox 360 controllers** immediately via ViGEmBus, regardless of how many phones have joined. These virtual pads register with Windows the moment the server launches.

PCSX2 scans for available gamepads **when it opens** (and when you open its controller settings). If the server isn't running yet, those virtual pads don't exist, and PCSX2 can't see them.

**Always do it in this order:**

1. Run **`scripts\start.bat`** — virtual pads appear in Windows.
2. Launch **PCSX2**.
3. Configure controllers inside PCSX2 (steps below).

If you accidentally opened PCSX2 first, close it, start the server, then relaunch PCSX2.

---

## Step 1 — Enable the Multitap

1. Open PCSX2.
2. Go to **Settings → Controllers**.
3. At the top you should see a **Global Settings** or **Controller Global Settings** section.
4. Find the **Multitap** option for **Port 1** and **turn it on** (check the box or flip the toggle).

Once enabled, the left sidebar or tab bar will show four pad slots under Port 1:

| Slot | Player |
|------|--------|
| **Pad 1-A** | Player 1 |
| **Pad 1-B** | Player 2 |
| **Pad 1-C** | Player 3 |
| **Pad 1-D** | Player 4 |

Without the multitap, only Pad 1 and Pad 2 (Port 1 / Port 2) are available — limiting you to two players even if four phones are connected.

---

## Step 2 — Map Each Pad to a Virtual Controller

Repeat the following for **each** pad slot (1-A, 1-B, 1-C, 1-D):

### 2a. Set the Controller Type

1. Click on the pad slot (e.g. **Pad 1-A**) in the sidebar.
2. Set **Controller Type** to **DualShock 2**.
   - Do **not** leave it on "None" or "Digital Controller." DualShock 2 gives PCSX2 the full button set (✕ ○ □ △, L1/R1, L2/R2, L3/R3, dual analog sticks, Select, Start).

### 2b. Use Automatic Mapping

1. With the pad slot selected, look for the **Automatic Mapping** button (it may also be labelled "Auto Map" or appear in the binding section).
2. Click it. A dropdown or dialog will show a list of detected controllers.
3. You will see several entries named something like **"Xbox 360 Controller"** or **"XBOX 360 For Windows"** — one for each virtual pad the server created. Pick one.
4. PCSX2 will fill in every button binding (Cross → A, Circle → B, etc.) automatically.

### 2c. Figure Out Which Virtual Controller Is Which

The server creates four identical virtual Xbox 360 controllers. Their names in the list look the same, so you need a way to match each one to a pad slot.

#### Method 1 — Test Pad button on the host dashboard (recommended)

1. Open the **host dashboard** on the PC: `http://localhost:8000/host`.
2. In PCSX2, select **Pad 1-A** and click **Automatic Mapping**, then pick the *first* Xbox 360 controller in the list.
3. On the host dashboard, click the **Test Pad** button next to **Slot 1**. This sends a brief button press on virtual pad 1.
4. Back in PCSX2, look at the Pad 1-A bindings — if the test input is picked up (you may see a binding flash or the pad indicator move), this is the right controller for Pad 1-A.
5. If nothing happens, undo the mapping, try the *next* Xbox 360 controller in the list, and test again.
6. Once Pad 1-A is confirmed, move on to Pad 1-B, pick another controller from the list, and use Test Pad on Slot 2 to verify. Repeat for 1-C and 1-D.

#### Method 2 — Single-binding Detect

1. In PCSX2, select a pad slot (e.g. Pad 1-A).
2. Find any binding row (e.g. "Cross") and click the **Detect** or **Bind** button next to it.
3. PCSX2 will wait for input. On the host dashboard, click **Test Pad** for Slot 1 (or press a button on the phone assigned to slot 1).
4. If PCSX2 registers it, you now know which virtual controller corresponds to that slot.
5. Cancel out if needed, then use **Automatic Mapping** with that same controller.

> [!TIP]
> You only need to do this mapping once. PCSX2 saves your controller configuration, so the next time you launch it (with the server already running), the bindings will still be there.

---

## Step 3 — Verify Everything Works

1. Make sure the server is running and at least one phone has joined (check the host dashboard).
2. In PCSX2, go to **Settings → Controllers** and click on each pad slot. At the bottom of the binding list you should see an **Input Preview** or **Test** area — press buttons on the corresponding phone and watch the preview respond.
   - *If your version of PCSX2 doesn't show a live preview here, don't worry — just launch a game and test there.*
3. Start a game that supports the number of players you want and confirm each player's phone controls their character.

---

## Troubleshooting

### A pad does not respond in-game

| Check | How |
|-------|-----|
| Server running? | The `start.bat` console should still be open. If you closed it, restart it and then restart PCSX2. |
| Phone connected? | Open `http://localhost:8000/host` — each phone should appear in a slot. |
| Same network? | PC and phone must be on the same Wi-Fi / hotspot (see `docs/NETWORK_SETUP.md`). |
| Firewall? | Run `scripts\open_firewall.bat` once as administrator. |
| PCSX2 pad config? | Settings → Controllers → the pad slot in question. Controller Type must be **DualShock 2**, and Automatic Mapping must point to a virtual Xbox 360 controller. |
| Started in wrong order? | Close PCSX2, make sure the server is running, relaunch PCSX2. |
| Test the raw input | On the host dashboard, click **Test Pad** for the slot. If the dashboard shows the button press but PCSX2 doesn't react, the PCSX2 mapping is wrong — redo Automatic Mapping. |

### Two phones control the same character

This means two pad slots in PCSX2 are mapped to the **same** virtual Xbox 360 controller.

1. Go to **Settings → Controllers**.
2. Click through Pad 1-A, 1-B, 1-C, and 1-D.
3. Check the device name in the bindings or Automatic Mapping for each pad. Each pad must point to a **different** virtual controller.
4. If two pads share a controller, clear one (there may be a "Clear Bindings" or "Clear All" button) and re-run Automatic Mapping, choosing a different controller from the dropdown.

It is also possible that two phones joined the same server slot. Check the host dashboard — each phone should show a unique slot number (P1, P2, P3, P4). If two phones share a slot, have one player refresh their browser page to get re-assigned.

### Button layout feels wrong

- Make sure Controller Type is **DualShock 2**, not "Digital Controller" or something else.
- Re-run **Automatic Mapping** — this resets all bindings to the standard Xbox-to-PS2 layout (A → Cross, B → Circle, X → Square, Y → Triangle).
- If individual buttons still seem swapped, the *game itself* may remap controls in its options menu. Check in-game settings.
- I have not documented PCSX2's dead-zone, sensitivity, or vibration tuning options here because they vary between versions and the defaults work fine for ps2-party-pad. Adjust them only if you notice stick drift or other issues.

---

## Multitap Game Compatibility

> [!IMPORTANT]
> Not every PS2 game supports more than 2 players. Only games that were built for the PS2 **Multitap accessory** will use Pads 1-C and 1-D.

- **Before inviting 4 players**, check whether your game supports multitap.
- Search for **"[game name] PS2 multitap"** online, or check resources like:
  - The [PCSX2 compatibility list](https://pcsx2.net/compat/)
  - Game-specific pages on [GameFAQs](https://gamefaqs.gamespot.com/)
  - Community spreadsheets — search "PS2 multitap game list"
- If a game only supports 2 players, the extra phones will still be connected to the server, but the game will simply ignore pads 1-C and 1-D.
- Some games (e.g. *TimeSplitters 2*, *Champions of Norrath*, *Baldur's Gate: Dark Alliance*) require you to enable multitap in the game's own options menu as well.

---

## Quick-Start Checklist

```
1.  Run scripts\start.bat              ← creates 4 virtual pads
2.  Phones join the server             ← open the Join URL or scan QR
3.  Launch PCSX2
4.  Settings → Controllers → Global Settings → enable Multitap on Port 1
5.  For each of Pad 1-A through 1-D:
      • Controller Type  →  DualShock 2
      • Automatic Mapping  →  pick the matching Xbox 360 controller
      • Use Test Pad on the host dashboard to confirm the right one
6.  Start a multitap-compatible game and play!
```
