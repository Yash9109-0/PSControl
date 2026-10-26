"use strict";

const STATUS = document.getElementById("status");
const ERROR = document.getElementById("error");
let config = null;

function showError(text) {
  ERROR.textContent = text;
  ERROR.classList.remove("hidden");
}

function slotLabel(i) {
  const div = document.createElement("div");
  div.className = "slot";
  div.id = `slot-${i}`;

  const qr = document.createElement("img");
  qr.className = "qr";
  qr.src = `/qr/${i}.png`;
  qr.alt = `QR code for player ${i + 1}`;

  const name = document.createElement("div");
  name.className = "status connected";
  name.id = `name-${i}`;
  name.textContent = `Player ${i + 1} — disconnected`;

  const hint = document.createElement("div");
  hint.className = "hint";
  hint.textContent = "Scan with phone camera";

  div.append(qr, name, hint);
  return div;
}

async function loadConfig() {
  try {
    const res = await fetch("/config");
    config = await res.json();
  } catch (e) {
    showError("Cannot reach the server. Is PS2 Party Pad running on this PC?");
  }
}

async function loadStatus() {
  if (!config) return;
  try {
    const res = await fetch("/status");
    const data = await res.json();
    document.getElementById("ip").textContent = config.ws_url.replace("ws://", "").split(":")[0];
    document.getElementById("port").textContent = config.port;
    let anyError = false;
    for (const s of data.slots) {
      const box = document.getElementById(`slot-${s.slot}`);
      const name = document.getElementById(`name-${s.slot}`);
      if (s.error) {
        anyError = true;
        name.className = "status disconnected";
        name.textContent = `Player ${s.slot + 1} — driver error`;
        continue;
      }
      if (s.connected) {
        name.className = "status connected";
        name.textContent = s.name ? `Player ${s.slot + 1} — ${s.name}` : `Player ${s.slot + 1} — connected`;
      } else {
        name.className = "status disconnected";
        name.textContent = `Player ${s.slot + 1} — disconnected`;
      }
    }
    document.getElementById("driver-note").style.display = anyError ? "block" : "none";
  } catch (e) {
    showError("Lost contact with the server.");
  }
}

async function init() {
  await loadConfig();
  const slots = document.getElementById("slots");
  for (let i = 0; i < config.slots; i++) slots.appendChild(slotLabel(i));
  loadStatus();
  setInterval(loadStatus, 1000);
}

init();
