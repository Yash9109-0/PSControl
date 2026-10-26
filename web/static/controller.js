"use strict";

const STATUS = document.getElementById("status");
const ERROR = document.getElementById("error");
const SLOT = new URLSearchParams(location.search).get("slot");
let ws = null;
let reconnectTimer = null;
let stickLast = { l: 0, r: 0 };

if (!SLOT) {
  STATUS.textContent = "Setup error: this page needs ?slot=0..3";
}

function showError(text, ms = 4000) {
  ERROR.textContent = text;
  ERROR.classList.remove("hidden");
  setTimeout(() => { ERROR.classList.add("hidden"); }, ms);
}

function send(obj) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify(obj));
}

function setBtnActive(button, active) {
  const el = document.querySelector(`[data-button="${button}"]`);
  if (el) el.classList.toggle("active", active);
}

function btnPressed(button, pressed) {
  send({ type: "button", button, pressed });
  setBtnActive(button, pressed);
}

function connect() {
  if (!SLOT) return;
  STATUS.textContent = "Connecting…";
  ws = new WebSocket(`ws://${location.host}/ws/${SLOT}`);
  ws.onopen = () => {
    STATUS.textContent = "Connected";
    send({ type: "hello", name: "Controller" });
  };
  ws.onclose = () => {
    ws = null;
    STATUS.textContent = "Disconnected – reconnecting…";
    document.querySelectorAll(".btn.active, .d-btn.active").forEach((el) => el.classList.remove("active"));
    moveStick("l", 0, 0);
    moveStick("r", 0, 0);
    reconnectTimer = setTimeout(connect, 1500);
  };
  ws.onerror = () => { ws.close(); };
  ws.onmessage = (ev) => {
    let msg;
    try { msg = JSON.parse(ev.data); } catch (e) { return; }
    if (msg.type === "error") showError(msg.message);
  };
}

function connectButton(el) {
  const button = el.dataset.button;
  const start = () => { el.classList.add("active"); btnPressed(button, true); };
  const end = () => { el.classList.remove("active"); btnPressed(button, false); };
  el.addEventListener("touchstart", (e) => { e.preventDefault(); start(); }, { passive: false });
  el.addEventListener("touchend", end);
  el.addEventListener("touchcancel", end);
  el.addEventListener("mousedown", start);
  el.addEventListener("mouseup", end);
  el.addEventListener("mouseleave", end);
}

function connectStick(id, side) {
  const stick = document.getElementById(id);
  const knob = stick.querySelector(".knob");
  const cx = stick.offsetWidth / 2;
  const cy = stick.offsetHeight / 2;
  const maxR = 64;
  let activeId = null;

  function update(tx, ty) {
    const r = Math.hypot(tx - cx, ty - cy) || 1;
    const scale = Math.min(maxR, r) / r;
    const dx = (tx - cx) * scale;
    const dy = (ty - cy) * scale;
    knob.style.transform = `translate(${dx}px, ${dy}px)`;
    const now = performance.now();
    if (now - stickLast[side] > 25) {
      stickLast[side] = now;
      const sx = side === "l" ? "lx" : "rx";
      const sy = side === "l" ? "ly" : "ry";
      // screen Y grows downward; joystick Y grows upward.
      send({ type: "axis", axis: sx, x: dx / maxR });
      send({ type: "axis", axis: sy, x: -dy / maxR });
    }
  }

  function release() {
    activeId = null;
    knob.style.transform = "translate(0, 0)";
    const sx = side === "l" ? "lx" : "rx";
    const sy = side === "l" ? "ly" : "ry";
    send({ type: "axis", axis: sx, x: 0 });
    send({ type: "axis", axis: sy, x: 0 });
  }

  stick.addEventListener("touchstart", (e) => {
    e.preventDefault();
    activeId = e.changedTouches[0].identifier;
  }, { passive: false });
  stick.addEventListener("touchmove", (e) => {
    e.preventDefault();
    for (const t of e.changedTouches) {
      if (t.identifier === activeId) {
        const rect = stick.getBoundingClientRect();
        update(t.clientX - rect.left, t.clientY - rect.top);
      }
    }
  }, { passive: false });
  stick.addEventListener("touchend", (e) => {
    for (const t of e.changedTouches) {
      if (t.identifier === activeId) release();
    }
  });
  stick.addEventListener("touchcancel", release);
  stick.addEventListener("mousedown", (e) => {
    activeId = 1;
    const rect = stick.getBoundingClientRect();
    update(e.clientX - rect.left, e.clientY - rect.top);
  });
  window.addEventListener("mousemove", (e) => {
    if (activeId !== 1) return;
    const rect = stick.getBoundingClientRect();
    update(e.clientX - rect.left, e.clientY - rect.top);
  });
  window.addEventListener("mouseup", release);
  window.addEventListener("mouseleave", release);
}

document.querySelectorAll("[data-button]").forEach(connectButton);
document.querySelectorAll(".stick").forEach((el) => connectStick(el.id, el.id.endsWith("-l") ? "l" : "r"));

connect();
