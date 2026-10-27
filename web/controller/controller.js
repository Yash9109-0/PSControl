'use strict';

// ---------- DOM refs ----------
const STATUS = document.getElementById('status');
const ERROR = document.getElementById('error');
const RECONNECT_BANNER = document.getElementById('reconnect-banner');
const SLOT_BADGE = document.getElementById('slot-badge');
const PING_DISPLAY = document.getElementById('ping-display');
const JOIN_SCREEN = document.getElementById('join-screen');
const CONTROLLER_SCREEN = document.getElementById('controller-screen');
const ROTATE_OVERLAY = document.getElementById('rotate-overlay');
const JOIN_NAME = document.getElementById('join-name');
const JOIN_BTN = document.getElementById('join-btn');
const JOIN_ERROR = document.getElementById('join-error');
const SETTINGS_OPEN = document.getElementById('settings-open');
const SETTINGS = document.getElementById('settings');

// ---------- Slot colors (P1 blue, P2 red, P3 green, P4 yellow) ----------
const SLOT_COLORS = ['#0af', '#f44', '#4f4', '#ff4'];
const SLOT_TEXT_COLORS = ['#000', '#fff', '#000', '#000'];

// ---------- Button bitmask (matches server) ----------
const BIT = {
  cross: 1 << 0, circle: 1 << 1, square: 1 << 2, triangle: 1 << 3,
  l1: 1 << 4, r1: 1 << 5, l2: 1 << 6, r2: 1 << 7,
  select: 1 << 8, start: 1 << 9, l3: 1 << 10, r3: 1 << 11,
  'dpad-up': 1 << 12, 'dpad-down': 1 << 13, 'dpad-left': 1 << 14, 'dpad-right': 1 << 15,
};

// ---------- Connection state ----------
let ws = null;
let token = localStorage.getItem('pp_token') || null;
let name = localStorage.getItem('pp_name') || '';
let slot = null;
let connected = false;
let reconnecting = false;
let reconnectTimer = null;
let LEFT_HAND = localStorage.getItem('pp_leftHand') === 'true';

// ---------- Input state ----------
let seq = 0;
let lastState = { b: 0, lx: 0, ly: 0, rx: 0, ry: 0 };
let lastSendTime = 0;
let inputTimer = null;
let pingTimer = null;
let lastPingTime = 0;

let pressed = new Set();   // currently pressed button names
let dpadPressed = new Set(); // currently pressed dpad names

// ---------- Stick geometry (computed on layout) ----------
const stickL = { cx: 0, cy: 0, r: 0, x: 0, y: 0, pid: null };
const stickR = { cx: 0, cy: 0, r: 0, x: 0, y: 0, pid: null };
let DEAD_ZONE = 0.18; // fraction of radius

let dpad = { cx: 0, cy: 0, r: 0, pid: null };

// ---------- Helpers ----------
function showStatus(msg) { STATUS.textContent = msg; STATUS.className = 'status'; }
function showError(msg) { ERROR.textContent = msg; }
function hideError() { ERROR.textContent = ''; }
function showReconnect(show) { if (show) RECONNECT_BANNER.hidden = false; else RECONNECT_BANNER.hidden = true; }
function vibrate() { if (navigator.vibrate) navigator.vibrate(20); }

// ---------- Left-handed button mirroring ----------
function mirrorButton(name) {
  if (!LEFT_HAND) return name;
  const swaps = {
    'l1': 'r1', 'r1': 'l1',
    'l2': 'r2', 'r2': 'l2',
    'square': 'cross', 'cross': 'square',
    'triangle': 'circle', 'circle': 'triangle',
    'dpad-left': 'dpad-right', 'dpad-right': 'dpad-left',
  };
  return swaps[name] || name;
}

// ---------- WakeLock + NoSleep fallback ----------
let wakeLock = null;
let noSleepVideo = null;
function tryWakeLock() {
  if (wakeLock) return;
  if (navigator.wakeLock) {
    navigator.wakeLock.request('screen').then((wl) => {
      wakeLock = wl;
      wl.addEventListener('release', () => { wakeLock = null; noSleepVideo.pause(); });
    }).catch(() => startNoSleepFallback());
  } else {
    startNoSleepFallback();
  }
}
function startNoSleepFallback() {
  if (noSleepVideo) return;
  noSleepVideo = document.createElement('video');
  noSleepVideo.src = 'data:video/mp4;base64,AAAAHGZ0eXAAAgAAaXNvbWlzbzJhdmMxbXA0MQAAAB5tZGF0AAAAAUIAHqZk4gAAAAHOBAAAAAGIwQAAAhJtb292AAAAVm12aGQAAAAAAAAAAAAAAAAAAV+QAAFfkAABAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAG0dHJhawAAAEB0a2hkAAAAAQAAAAcAAAAAAAAAAQAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAEAAQABAAAAFsbWRpYQAAACBtZGhkAAAAAAAAAAAAAAAAAAFfkAABX5AAAQAAAAAALGhkbHIAAAAAAAAAAHZpZGUAAAAAAAAAAAAAAABWaWRlb0hhbmRsZXIAAAEYbWluZgAAABR2bWhkAAAAAAAAAAAAAAAAAAAAJGRpbmYAAAAcZHJlZgAAAAAAAAABAAAADHVybCAAAAABAAAA2HN0YmwAAABwc3RzZAAAAAAAAAABAAAAYGF2YzEAAAAAAAAAAQAQABAASAAAAEgAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABj//wFCAB79AAoAAAABQgAepmTiAQAGAAAAAc4EAAAAGHN0dHMAAAAAAAAAAQAAAAEAAV+QAAAAHHN0c2MAAAAAAAAAAQAAAAEAAAABAAAAAQAAABhzdHN6AAAAAAAAAAAAAAABAAAABgAAABRzdGNvAAAAAAAAAAEAAAAQ';
  noSleepVideo.muted = true;
  noSleepVideo.playsInline = true;
  noSleepVideo.autoplay = true;
  noSleepVideo.loop = true;
  noSleepVideo.style.position = 'fixed';
  noSleepVideo.style.width = '1px';
  noSleepVideo.style.height = '1px';
  noSleepVideo.style.opacity = 0;
  noSleepVideo.style.pointerEvents = 'none';
  document.body.appendChild(noSleepVideo);
  noSleepVideo.play();
  const ls = localStorage.getItem('pp_wakeLock') === 'true';
  if (ls) tryWakeLock();
}
function toggleWakeLock() {
  if (wakeLock) {
    wakeLock.release(); wakeLock = null;
    localStorage.setItem('pp_wakeLock', 'false');
    if (noSleepVideo) noSleepVideo.pause();
  } else {
    tryWakeLock();
    localStorage.setItem('pp_wakeLock', 'true');
  }
}

// ---------- Fullscreen + Homescreen hint ----------
let firstTap = true;
function requestFs() {
  const el = document.documentElement;
  if (el.requestFullscreen) el.requestFullscreen();
  else if (el.webkitRequestFullscreen) el.webkitRequestFullscreen();
}
function showHsBanner() {
  const banner = document.getElementById('hs-banner');
  if (banner) banner.style.display = 'block';
}
document.addEventListener('click', () => {
  if (firstTap) {
    firstTap = false;
    requestFs();
    // On iPhone, fullscreen silently fails; show homescreen banner
    if (!document.fullscreenElement) {
      showHsBanner();
    }
  }
}, { once: true });

// ---------- Settings gear ----------
function openSettings() {
  SETTINGS.classList.remove('hidden');
  SETTINGS_OPEN.classList.add('hidden');
  // Load saved settings
  LEFT_HAND = localStorage.getItem('pp_leftHand') === 'true';
  document.getElementById('leftHand').checked = LEFT_HAND;
  document.getElementById('vibrate').checked = localStorage.getItem('pp_vibrate') !== 'false';
  const bs = localStorage.getItem('pp_buttonSize') || 'medium';
  document.getElementById('buttonSize').value = bs;
  document.getElementById('deadZone').value = localStorage.getItem('pp_deadZone') || '0.18';
  document.getElementById('deadZoneValue').textContent = localStorage.getItem('pp_deadZone') || '0.18';
}
function closeSettings() {
  SETTINGS.classList.add('hidden');
  SETTINGS_OPEN.classList.remove('hidden');
}
function saveSettings() {
  LEFT_HAND = document.getElementById('leftHand').checked;
  localStorage.setItem('pp_leftHand', LEFT_HAND);
  localStorage.setItem('pp_vibrate', document.getElementById('vibrate').checked);
  localStorage.setItem('pp_buttonSize', document.getElementById('buttonSize').value);
  localStorage.setItem('pp_deadZone', document.getElementById('deadZone').value);
  const val = parseFloat(document.getElementById('deadZone').value);
  DEAD_ZONE = val;
  document.getElementById('deadZoneValue').textContent = val;
  updateAllVisuals();
  closeSettings();
}
document.getElementById('hs-close').addEventListener('click', () => {
  document.getElementById('hs-banner').style.display = 'none';
});

// Initialize wakeLock after connectWs
function initWakeLock() {
  const ls = localStorage.getItem('pp_wakeLock') === 'true';
  if (ls) tryWakeLock();
}

// ---------- Tab/Hide Release-All ----------
document.addEventListener('visibilitychange', () => {
  if (document.hidden) releaseAllInput();
});
window.addEventListener('beforeunload', releaseAllInput);

function updateSlotBadge(s) {
  slot = s;
  const idx = Math.max(0, Math.min(3, s | 0));
  SLOT_BADGE.textContent = 'P' + (idx + 1);
  SLOT_BADGE.style.background = SLOT_COLORS[idx];
  SLOT_BADGE.style.color = SLOT_TEXT_COLORS[idx];
}

// ---------- WebSocket ----------
function connectWs() {
  connected = false;
  reconnecting = true;
  showReconnect(true);
  showStatus('Connecting…');
  hideError();

  const url = 'ws://' + location.host + '/ws/play';
  ws = new WebSocket(url);
  ws.onopen = onWsOpen;
  ws.onclose = onWsClose;
  ws.onerror = () => ws.close();
  ws.onmessage = (ev) => {
    try { handleMsg(JSON.parse(ev.data)); } catch (e) { /* ignore */ }
  };
}

function onWsOpen() {
  connected = true;
  reconnecting = false;
  showReconnect(false);
  if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
  showStatus('Connected');
  sendJoin();
  startLoops();
  initWakeLock();
}

function onWsClose() {
  connected = false;
  ws = null;
  stopLoops();
  releaseAllInput();
  showStatus('Disconnected – reconnecting…');
  showReconnect(true);
  reconnectTimer = setTimeout(connectWs, 1000);
}

function sendJoin() {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ t: 'join', name, token, slot }));
}

function send(obj) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
}

function handleMsg(msg) {
  if (msg.t === 'joined') {
    slot = msg.slot;
    token = msg.token;
    name = msg.name || name;
    localStorage.setItem('pp_token', token);
    localStorage.setItem('pp_name', name);
    updateSlotBadge(slot);
    showStatus('Connected');
  } else if (msg.t === 'pong') {
    const rtt = msg.c != null ? Math.max(0, Math.round(performance.now() - msg.c)) : 0;
    PING_DISPLAY.textContent = rtt + ' ms';
  } else if (msg.t === 'error') {
    showError(msg.message || 'Error');
    if ((msg.message || '') === 'room full') {
      ws.close();
      CONTROLLER_SCREEN.classList.add('hidden');
      JOIN_SCREEN.classList.remove('hidden');
      JOIN_ERROR.textContent = 'Room full — try again later';
    }
  }
}
// ---------- Send loops ----------
function startLoops() {
  stopLoops();
  lastSendTime = performance.now();
  inputTimer = setInterval(inputTick, 16); // ~60 fps
  pingTimer = setInterval(sendPing, 2000); // ping every 2s
  sendPing();
}

function stopLoops() {
  if (inputTimer) { clearInterval(inputTimer); inputTimer = null; }
  if (pingTimer) { clearInterval(pingTimer); pingTimer = null; }
}

function inputTick() {
  const now = performance.now();
  const state = computeState();
  const changed = state.b !== lastState.b ||
                  state.lx !== lastState.lx || state.ly !== lastState.ly ||
                  state.rx !== lastState.rx || state.ry !== lastState.ry;

  // Send input when changed (max 60fps via the 16ms tick)
  if (changed) {
    seq++;
    lastState = { ...state };
    send({ t: 'in', seq, b: state.b, lx: state.lx, ly: state.ly, rx: state.rx, ry: state.ry });
    lastSendTime = now;
  }
  // Heartbeat every 1s: send current state even if unchanged
  else if (now - lastSendTime >= 1000) {
    lastState = { ...state };
    send({ t: 'in', seq, b: state.b, lx: state.lx, ly: state.ly, rx: state.rx, ry: state.ry });
    lastSendTime = now;
  }
}

function sendPing() {
  if (!connected) return;
  send({ t: 'ping', c: performance.now() });
}

// ---------- Input computation ----------
function computeState() {
  let b = 0;
  for (const btn of pressed) if (BIT[btn]) b |= BIT[btn];
  for (const d of dpadPressed) if (BIT[d]) b |= BIT[d];

  // Apply dead zone to sticks
  let lx = stickL.x, ly = stickL.y;
  let rx = stickR.x, ry = stickR.y;
  if (Math.hypot(lx, ly) < DEAD_ZONE * 100) { lx = 0; ly = 0; }
  if (Math.hypot(rx, ry) < DEAD_ZONE * 100) { rx = 0; ry = 0; }

  return { b, lx, ly, rx, ry };
}

// ---------- Stick pointer handling ----------
function initStick(stickId, knobId, st) {
  const el = document.getElementById(stickId);
  const knob = document.getElementById(knobId);
  st.el = el; st.knob = knob;

  el.addEventListener('pointerdown', (e) => {
    if (st.pid !== null) return;
    st.pid = e.pointerId;
    el.setPointerCapture(e.pointerId);
    updateStickFromEvent(st, e.clientX, e.clientY, true);
    drawStick(st);
  }, { passive: false });

  el.addEventListener('pointermove', (e) => {
    if (st.pid !== e.pointerId) return;
    updateStickFromEvent(st, e.clientX, e.clientY, false);
    drawStick(st);
  }, { passive: false });

  const release = () => {
    if (st.pid === null) return;
    try { el.releasePointerCapture(st.pid); } catch (e) {}
    st.pid = null;
    stickCenter(st);
    drawStick(st);
  };
  el.addEventListener('pointerup', release, { passive: false });
  el.addEventListener('pointercancel', release, { passive: false });
  el.addEventListener('pointerleave', release, { passive: false });
}

function stickCenter(st) { st.x = 0; st.y = 0; }

function updateStickFromEvent(st, cx, cy, initial) {
  const rect = st.el.getBoundingClientRect();
  const centerX = rect.left + rect.width / 2;
  const centerY = rect.top + rect.height / 2;
  const radius = rect.width / 2;
  st.cx = centerX; st.cy = centerY; st.r = radius;

  let dx = cx - centerX;
  let dy = cy - centerY;
  const dist = Math.hypot(dx, dy);
  if (dist > radius) { dx = (dx / dist) * radius; dy = (dy / dist) * radius; }

  st.x = Math.round((dx / radius) * 100);
  st.y = Math.round((-dy / radius) * 100);
}

function drawStick(st) {
  if (!st.knob) return;
  const radius = st.r;
  const maxOffset = radius * 0.6;
  let dx = (st.x / 100) * maxOffset;
  let dy = (-st.y / 100) * maxOffset;
  st.knob.style.transform = `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px))`;
}

function releaseAllInput() {
  pressed.clear();
  dpadPressed.clear();
  stickL.x = 0; stickL.y = 0; stickL.pid = null;
  stickR.x = 0; stickR.y = 0; stickR.pid = null;
  dpad.pid = null;
}
// ---------- D-pad pointer handling (slide between directions + diagonals) ----------
function initDpad() {
  const el = document.querySelector('.dpad');
  if (!el) return;
  const start = (cx, cy, pid) => {
    if (dpad.pid !== null) return;
    dpad.pid = pid;
    const r = el.getBoundingClientRect();
    dpad.cx = r.left + r.width / 2;
    dpad.cy = r.top + r.height / 2;
    dpad.r = Math.max(r.width, r.height) / 2;
    updateDpadFromPos(cx, cy);
  };
  el.addEventListener('pointerdown', (e) => {
    if (!e.target.closest('.d-btn')) return;
    start(e.clientX, e.clientY, e.pointerId);
    el.setPointerCapture(e.pointerId);
  }, { passive: false });
  el.addEventListener('pointermove', (e) => {
    if (dpad.pid !== e.pointerId) return;
    updateDpadFromPos(e.clientX, e.clientY);
  }, { passive: false });
  const release = () => {
    dpad.pid = null;
    dpadPressed.clear();
    updateAllVisuals();
  };
  el.addEventListener('pointerup', release, { passive: false });
  el.addEventListener('pointercancel', release, { passive: false });
  el.addEventListener('pointerleave', release, { passive: false });
}

function updateDpadFromPos(cx, cy) {
  let dx = cx - dpad.cx;
  const dy = cy - dpad.cy;
  if (LEFT_HAND) dx = -dx;
  const dist = Math.hypot(dx, dy);
  if (dist < dpad.r * 0.25) { dpadPressed.clear(); updateAllVisuals(); return; }
  let ang = Math.atan2(dy, dx) * 180 / Math.PI;
  if (ang < 0) ang += 360;
  dpadPressed.clear();
  const inRange = (a, center) => { let d = Math.abs(a - center); if (d > 180) d = 360 - d; return d <= 45; };
  if (inRange(ang, 270)) dpadPressed.add('dpad-up');
  if (inRange(ang, 90)) dpadPressed.add('dpad-down');
  if (inRange(ang, 180)) dpadPressed.add('dpad-left');
  if (inRange(ang, 0)) dpadPressed.add('dpad-right');
  updateDpadVisuals();
  updateAllVisuals();
}

function updateDpadVisuals() {
  document.querySelectorAll('.d-btn').forEach(el => {
    const name = el.getAttribute('data-button');
    el.classList.toggle('pressed', dpadPressed.has(mirrorButton(name)));
  });
}

// ---------- Buttons ----------
function initButtons() {
  document.querySelectorAll('[data-button]').forEach(el => {
    const name = el.getAttribute('data-button');
    const press = () => { const m = mirrorButton(name); if (!pressed.has(m)) { pressed.add(m); vibrate(); el.classList.add('active'); updateAllVisuals(); } };
    const release = () => { const m = mirrorButton(name); if (pressed.has(m)) { pressed.delete(m); el.classList.remove('active'); updateAllVisuals(); } };
    el.addEventListener('pointerdown', (e) => { e.preventDefault(); press(); }, { passive: false });
    el.addEventListener('pointerup', release, { passive: false });
    el.addEventListener('pointercancel', release, { passive: false });
    el.addEventListener('pointerleave', release, { passive: false });
  });
}

function updateAllVisuals() { updateDpadVisuals(); }

// ---------- Init ----------
function init() {
  if (name) JOIN_NAME.value = name;
  JOIN_BTN.addEventListener('click', () => {
    name = JOIN_NAME.value.trim() || 'Player';
    localStorage.setItem('pp_name', name);
    JOIN_SCREEN.classList.add('hidden');
    CONTROLLER_SCREEN.classList.remove('hidden');
    connectWs();
  });
  JOIN_NAME.addEventListener('keypress', (e) => { if (e.key === 'Enter') JOIN_BTN.click(); });
  // Settings gear
  SETTINGS_OPEN.addEventListener('click', openSettings);
  SETTINGS.querySelector('.settings-close').addEventListener('click', closeSettings);
  SETTINGS.querySelector('#settings-save').addEventListener('click', saveSettings);
  // Wire settings controls
  document.getElementById('leftHand').addEventListener('change', e => {
    LEFT_HAND = e.target.checked;
    pressed.clear();
    dpadPressed.clear();
    updateAllVisuals();
  });
  document.getElementById('vibrate').addEventListener('change', e => {
    localStorage.setItem('pp_vibrate', e.target.checked);
    vibrate();
  });
  document.getElementById('buttonSize').addEventListener('change', e => {
    const val = e.target.value;
    localStorage.setItem('pp_buttonSize', val);
    const sizes = { small: '12px', medium: '14px', large: '16px' };
    document.body.style.setProperty('--button-size', sizes[val]);
  });
  document.getElementById('deadZone').addEventListener('input', e => {
    const val = parseFloat(e.target.value);
    localStorage.setItem('pp_deadZone', val);
    DEAD_ZONE = val;
    document.getElementById('deadZoneValue').textContent = val;
    updateAllVisuals();
  });
  initStick('stick-l', 'knob-l', stickL);
  initStick('stick-r', 'knob-r', stickR);
  initDpad();
  initButtons();

  function checkOrient() {
    ROTATE_OVERLAY.classList.toggle('show', window.innerWidth <= window.innerHeight);
  }
  window.addEventListener('resize', checkOrient);
  checkOrient();

  if (token) {
    connectWs();
  }
}
document.addEventListener('DOMContentLoaded', init);
