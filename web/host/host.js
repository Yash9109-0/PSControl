"use strict";

const CARDS_EL = document.getElementById("cards");
const STATUS_BAR = document.getElementById("status-bar");
const GAMEPAD_DOT = document.getElementById("gamepad-dot");
const GAMEPAD_TEXT = document.getElementById("gamepad-text");
const QR_IMG = document.getElementById("qr-big");
const JOIN_URL = document.getElementById("join-url");
const IP_EL = document.getElementById("ip");
const PORT_EL = document.getElementById("port");
const ERROR_EL = document.getElementById("error");

const SLOT_COLORS = ["#0af", "#f44", "#4f4", "#ff4"];

let ws = null;
let swapPending = null; // slot index awaiting swap partner
let lastSnapshot = null;

function showError(msg) {
  ERROR_EL.textContent = msg;
  ERROR_EL.classList.remove("hidden");
}
function hideError() {
  ERROR_EL.textContent = "";
  ERROR_EL.classList.add("hidden");
}

function pingClass(ms) {
  if (ms === null || ms === undefined) return "na";
  if (ms < 40) return "good";
  if (ms < 80) return "warn";
  return "bad";
}

function formatLastInput(t) {
  if (t === null || t === undefined) return "–";
  return t.toFixed(0);
}

function buildCardHtml(s, slot) {
  const idx = slot;
  const color = SLOT_COLORS[idx];
  const connected = s.connected === true;
  const empty = s.name === null && !connected;
  const isPending = swapPending === idx;

  let nameHtml = empty ? "Empty" : (s.name || `Player ${idx + 1}`);
  let statusHtml = empty ? "disconnected" : (connected ? "connected" : "disconnected");
  let statusText = empty ? "—" : (connected ? "Connected" : "Disconnected");

  const pingHtml = connected && s.ping_ms != null
    ? `<div class="ping ${pingClass(s.ping_ms)}">${Math.round(s.ping_ms)} ms</div>`
    : `<div class="ping na">— ms</div>`;

  const lastInputHtml = `<div class="last-input">Last input: ${formatLastInput(s.last_input_time)}</div>`;

  const kickBtn = empty
    ? `<button class="btn" disabled>Kick</button>`
    : `<button class="btn danger" onclick="app.kick(${idx})">Kick</button>`;

  const swapBtn = empty
    ? `<button class="btn" disabled>Swap</button>`
    : `<button class="btn ${isPending ? "primary" : "warn"}" onclick="app.toggleSwap(${idx})">${isPending ? "Cancel" : "Swap"}</button>`;

  const testBtn = empty
    ? `<button class="btn" disabled>Test Pad</button>`
    : `<button class="btn" onclick="app.testPad(${idx})">Test Pad</button>`;

  const swapTag = isPending ? `<div class="swap-tag">SWAP</div>` : "";

  return `
    <div class="card ${empty ? "empty" : ""} ${isPending ? "swap-pending" : ""}" id="card-${idx}">
      ${swapTag}
      <div class="card-header">
        <div class="badge p${idx + 1}" style="background:${color}">P${idx + 1}</div>
      </div>
      <div class="card-name">${escapeHtml(nameHtml)}</div>
      <div class="card-status ${statusHtml}">${statusText}</div>
      ${pingHtml}
      ${lastInputHtml}
      <div class="card-actions">${kickBtn} ${swapBtn} ${testBtn}</div>
    </div>
  `;
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function render(snapshot) {
  lastSnapshot = snapshot;
  CARDS_EL.innerHTML = snapshot.slots.map((s, i) => buildCardHtml(s, i)).join("");
}

function updateGamepadStatus(ready, hint) {
  if (ready) {
    GAMEPAD_DOT.className = "dot ready";
    GAMEPAD_TEXT.textContent = "Virtual gamepads ready";
  } else {
    GAMEPAD_DOT.className = "dot missing";
    GAMEPAD_TEXT.textContent = hint || "Gamepad driver missing — install ViGEmBus";
  }
}

function sendCmd(cmd) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify(cmd));
}

const app = {
  kick(slot) {
    if (!confirm(`Kick player in slot ${slot + 1}?`)) return;
    sendCmd({ cmd: "kick", slot });
  },

  toggleSwap(slot) {
    if (swapPending === null) {
      swapPending = slot;
    } else if (swapPending === slot) {
      swapPending = null;
    } else {
      sendCmd({ cmd: "swap", slot_a: swapPending, slot_b: slot });
      swapPending = null;
    }
    if (lastSnapshot) render(lastSnapshot);
  },

  testPad(slot) {
    sendCmd({ cmd: "test", slot, button: "cross" });
  },
};

function connectWs() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const url = `${proto}//${location.host}/ws/host`;
  ws = new WebSocket(url);

  ws.onopen = () => {
    hideError();
  };

  ws.onclose = () => {
    ws = null;
    showError("Lost contact with the host WebSocket. Reconnecting…");
    setTimeout(connectWs, 1500);
  };

  ws.onerror = () => {
    ws.close();
  };

  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      if (msg.t === "slots") {
        render(msg.slots);
        updateGamepadStatus(!!msg.gamepad_ready, msg.gamepad_hint);
      }
    } catch (e) {
      // ignore bad frames
    }
  };
}

async function loadInfo() {
  try {
    const res = await fetch("/api/info");
    const data = await res.json();
    IP_EL.textContent = data.ip || "–";
    PORT_EL.textContent = data.port || "–";
    JOIN_URL.textContent = data.join_url || "http://–:–/";
    QR_IMG.src = data.qr_url || "/api/qr.png";
  } catch (e) {
    showError("Cannot reach the server API.");
  }
}

function init() {
  loadInfo();
  connectWs();
}

document.addEventListener("DOMContentLoaded", init);