# Network Setup Guide

ps2-party-pad needs the PC and every player's phone to be on the **same local network**. This guide walks you through three ways to set that up, starting with the best option.

> [!IMPORTANT]
> Before starting any option below, run **`scripts\open_firewall.bat`** once (right-click → Run as administrator). This adds a Windows Firewall rule so phones can reach the server.

---

## Why College / Dorm / Hotel Wi-Fi Usually Won't Work

Most campus and hotel networks enable **client isolation** (also called AP isolation). This is a security feature that stops devices on the same Wi-Fi from talking to each other — which is exactly what ps2-party-pad needs to do.

You'll know you're hitting this problem when:

- The phone can reach the internet, but **the Join URL times out**.
- The host dashboard shows no players connecting.

Some networks also force a **captive portal** (a login page) that blocks WebSocket connections even after you sign in.

**The fix:** Create your own little private network using one of the options below. You do **not** need internet access — ps2-party-pad is entirely local.

---

## Option A — Travel Router or Spare Phone Hotspot (Best)

A dedicated hotspot gives you the most reliable, lowest-latency setup. A cheap travel router or an old phone you aren't using as a controller works great.

### What you need

- A small travel router **or** a spare phone (any phone that can create a Wi-Fi hotspot).
- The router/phone does **not** need a SIM card or internet connection.

### Steps

1. **Turn on the hotspot / router.**
   - *Travel router:* Follow its instructions to power it on. Set the Wi-Fi band to **5 GHz** if it has the option (faster, lower latency).
   - *Spare phone:* Open **Settings → Hotspot & Tethering → Wi-Fi Hotspot**, turn it on, and set the band to **5 GHz** (see the phone-specific steps in Option C below).

2. **Connect the PC to the hotspot.**
   - Click the **Wi-Fi icon** in the Windows taskbar (bottom-right).
   - Select the hotspot name, enter the password, and connect.
   - You'll see "No internet" — **that's perfectly fine**.

3. **Connect every player's phone to the same hotspot.**

4. **Run `scripts\start.bat`** on the PC.
   - The console prints a **Join URL** like `http://192.168.43.1:8000/`.
   - Share that URL with players, or let them scan the QR code on the host dashboard.

5. **Verify:** On a player's phone, open the Join URL in the browser. You should see the controller page. If it loads, you're good to go.

---

## Option B — Windows Mobile Hotspot on the PC (Easiest)

Windows can turn your PC's Wi-Fi adapter into a hotspot. No extra hardware needed.

### Steps

1. **Open Mobile Hotspot settings.**
   - Press **Win + I** to open Settings.
   - Go to **Network & Internet → Mobile Hotspot**.

2. **Configure the hotspot.**
   - Under *"Share my internet connection from"*, pick any adapter (it doesn't matter if it says "No internet" — ps2-party-pad works offline).
   - Click **Edit** next to the network name and password.
     - Set a simple **Network name** and **Password**.
     - **Band:** Choose **5 GHz** for the lowest latency. If your adapter doesn't support 5 GHz, leave it on "Any available" or 2.4 GHz — it will still work, just slightly slower.
   - Click **Save**.

3. **Turn the hotspot on.**
   - Flip the **Mobile Hotspot** toggle to **On**.

4. **"No internet connection to share" error?**
   - This message appears if the PC itself has no internet. That's okay — you just need to trick Windows into allowing it:
     1. Open **Control Panel → Network and Sharing Center → Change adapter settings** (or press **Win + R**, type `ncpa.cpl`, press Enter).
     2. Find a network adapter that is connected (e.g., Ethernet or another Wi-Fi). Right-click it → **Properties** → **Sharing** tab.
     3. Check **"Allow other network users to connect through this computer's internet connection"** and click **OK**.
     4. If *no* adapter is connected to the internet, try this instead:
        - Connect to *any* Wi-Fi network (even one with no internet), then turn on Mobile Hotspot again.
        - Or use a USB cable to connect your phone and enable **USB Tethering** on the phone, then share *that* connection through Mobile Hotspot.
   - Once the hotspot is running, phones don't actually need internet — ps2-party-pad is fully local.

5. **Connect every player's phone to the hotspot** you just created.

6. **Run `scripts\start.bat`** on the PC.
   - The console prints the **Join URL**. Share it with players.

7. **Verify:** Open the Join URL in a player's phone browser. The controller page should appear.

> [!NOTE]
> Windows Mobile Hotspot supports up to 8 devices and works fine for 4-player sessions. If the toggle greys out, make sure your Wi-Fi adapter supports Hosted Network (most modern adapters do).

---

## Option C — A Player's Phone Hotspot (Fallback)

If you don't have a travel router and Windows Mobile Hotspot won't cooperate, any player's phone can be the hotspot. That player uses the hotspot phone as their controller too.

### Steps

1. **Enable the phone hotspot.**
   - **Android:** Settings → Network & Internet → Hotspot & Tethering → Wi-Fi Hotspot → turn it **On**.
     - Tap **AP Band** or **Wi-Fi Band** and choose **5 GHz preferred** if available.
   - **iPhone:** Settings → Personal Hotspot → toggle **Allow Others to Join** on.
     - iPhones with Wi-Fi 6 default to 5 GHz when possible. On older models you can toggle **Maximize Compatibility** *off* to prefer 5 GHz.

2. **Connect the PC to the phone's hotspot** (same as Option A, step 2).

3. **Connect the other players' phones to the same hotspot.**

4. **Run `scripts\start.bat`** on the PC.

5. **Share the Join URL** with all players (including the one whose phone is the hotspot — they open the URL in a browser on the *same* phone).

6. **Verify:** Each player opens the Join URL. Controller page = success.

> [!TIP]
> If the hotspot phone's battery drains fast, keep it plugged in. Hotspot + controller at the same time uses a lot of power.

---

## How to Confirm a Phone Can Reach the Server

If a player says "it's not connecting," do this quick test:

1. On the PC, look at the `scripts\start.bat` console output for the line:
   ```
   Join URL : http://192.168.x.x:8000/
   ```
2. On the player's phone, open **Chrome / Safari** and type that exact URL into the address bar.
3. **If the controller page loads** → The network is fine. The player can scan the QR code or tap the URL to join.
4. **If it times out or says "can't reach this page":**
   - Confirm the phone is on the **same Wi-Fi / hotspot** as the PC.
   - Make sure you ran **`scripts\open_firewall.bat`** on the PC.
   - Try temporarily disabling any third-party antivirus/firewall (Windows Defender Firewall is handled by the script, but other firewalls like Norton or Kaspersky have their own rules).
   - Double-check the IP address — it changes when you switch networks. Restart `start.bat` to get a fresh URL.

---

## Quick Reference

| Step | What to do |
|------|-----------|
| **1** | Run `scripts\open_firewall.bat` once (as admin) |
| **2** | Create a hotspot (Option A, B, or C) |
| **3** | Connect the PC + all phones to that hotspot |
| **4** | Run `scripts\start.bat` |
| **5** | Players open the Join URL or scan the QR code |
