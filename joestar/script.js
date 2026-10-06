import { initOrb } from './orb-render.js';
import { auth } from './firebase-config.js';
import { onAuthStateChanged, signOut, deleteUser } from 'https://www.gstatic.com/firebasejs/12.6.0/firebase-auth.js';

// ── CONNECTION STATUS (real, not decorative) ──
function setStatus(label) {
  for (const id of ['conn-status', 'backend-state']) {
    const el = document.getElementById(id);
    if (el) el.textContent = label;
  }
  const mobile = document.getElementById('mobile-log');
  if (mobile && label !== 'ONLINE') mobile.textContent = label;
}

// ── AUTH ──
let ws;
const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';

function connectWebSocket(token) {
  ws = new WebSocket(`${wsProtocol}//${window.location.host}/ws?token=${encodeURIComponent(token)}`);

  ws.onopen = () => {
    setStatus('ONLINE');
    updateMobileLog('ONLINE — AWAITING COMMAND');
    addLog('Connected to backend', true);
  };

  ws.onclose = () => setStatus('OFFLINE');

  ws.onerror = () => {
    setStatus('OFFLINE');
    addLog('ERROR: Could not connect to backend');
    document.getElementById('response-text').textContent = 'Cannot connect to backend. Is the server running?';
  };

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === "text") {
      typeResponse(msg.content);
      addLog('JOESTAR: Response received', true);
      updateMobileLog('JOESTAR responded');
    } else if (msg.type === "audio") {
      playAudio(msg.content);
      addLog('Audio synthesized', true);
    } else if (msg.type === "auth_error") {
      addLog(`AUTH ERROR: ${msg.content}`);
      window.location.href = '/login.html';
    }
  };
}

onAuthStateChanged(auth, async (user) => {
  if (!user) {
    window.location.href = '/login.html';
    return;
  }

  const nameEl = document.getElementById('user-name');
  if (nameEl) nameEl.textContent = (user.displayName || user.email || '').toUpperCase();

  const token = await user.getIdToken(true); // force refresh so the ID token's name claim is current
  connectWebSocket(token);
});

document.getElementById('signout-link')?.addEventListener('click', async () => {
  await signOut(auth);
  window.location.href = '/login.html';
});

// ── HISTORY PANEL ──
const HISTORY_PAGE_SIZE = 50;
let historyOffset = 0;
let historyTotal = 0;

const historyOverlay = document.getElementById('history-overlay');
const historyList = document.getElementById('history-list');
const historyLoadMoreBtn = document.getElementById('history-load-more');

function formatHistoryTimestamp(iso) {
  try {
    return new Date(iso).toLocaleString('en-US', { hour12: false });
  } catch {
    return iso;
  }
}

function renderHistoryEntries(items, { append = false } = {}) {
  if (!append) historyList.innerHTML = '';

  if (items.length === 0 && !append) {
    historyList.innerHTML = '<div class="history-empty">No conversations yet.</div>';
    return;
  }

  for (const item of items) {
    const el = document.createElement('div');
    el.className = 'history-entry';
    el.innerHTML = `
      <div class="history-timestamp">${formatHistoryTimestamp(item.timestamp)}</div>
      <div class="history-user"></div>
      <div class="history-response"></div>
    `;
    el.querySelector('.history-user').textContent = item.user_input;
    el.querySelector('.history-response').textContent = item.assistant_response;
    historyList.appendChild(el);
  }
}

async function fetchHistory(offset) {
  const user = auth.currentUser;
  if (!user) return;
  const token = await user.getIdToken();
  const res = await fetch(`/history?limit=${HISTORY_PAGE_SIZE}&offset=${offset}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    historyList.innerHTML = '<div class="history-empty">Could not load history.</div>';
    return;
  }
  const data = await res.json();
  historyTotal = data.total || 0;
  historyOffset = offset + (data.items || []).length;
  renderHistoryEntries(data.items || [], { append: offset > 0 });
  historyLoadMoreBtn.style.display = historyOffset < historyTotal ? 'block' : 'none';
}

// ── ACCESSIBLE MODALS (focus moved in, trapped, Esc to close, focus restored) ──
let activeModal = null;
const FOCUSABLE = 'button:not([disabled]), a[href], input:not([disabled]), [tabindex]:not([tabindex="-1"])';

function openModal(overlay, opener) {
  overlay.classList.add('visible');
  activeModal = { overlay, opener };
  const first = overlay.querySelector(FOCUSABLE);
  if (first) first.focus();
}

function closeModal() {
  if (!activeModal) return;
  const { overlay, opener } = activeModal;
  overlay.classList.remove('visible');
  activeModal = null;
  opener?.focus();
}

document.addEventListener('keydown', (e) => {
  if (!activeModal) return;
  if (e.key === 'Escape') { e.preventDefault(); closeModal(); return; }
  if (e.key !== 'Tab') return;
  const items = [...activeModal.overlay.querySelectorAll(FOCUSABLE)].filter(el => el.offsetParent !== null);
  if (!items.length) return;
  const firstEl = items[0], lastEl = items[items.length - 1];
  if (e.shiftKey && document.activeElement === firstEl) { e.preventDefault(); lastEl.focus(); }
  else if (!e.shiftKey && document.activeElement === lastEl) { e.preventDefault(); firstEl.focus(); }
});

document.getElementById('history-btn')?.addEventListener('click', (e) => {
  openModal(historyOverlay, e.currentTarget);
  fetchHistory(0);
});

document.getElementById('history-close')?.addEventListener('click', closeModal);

historyOverlay?.addEventListener('click', (e) => {
  if (e.target === historyOverlay) closeModal();
});

// ── PRIVACY / DATA DELETION ──
const privacyOverlay = document.getElementById('privacy-overlay');
const privacyStatus = document.getElementById('privacy-status');
const deleteDataBtn = document.getElementById('delete-data-btn');
const deleteAccountBtn = document.getElementById('delete-account-btn');
const DELETE_DATA_LABEL = deleteDataBtn.textContent;
const DELETE_ACCOUNT_LABEL = deleteAccountBtn.textContent;

function resetPrivacyButtons() {
  deleteDataBtn.textContent = DELETE_DATA_LABEL;
  deleteAccountBtn.textContent = DELETE_ACCOUNT_LABEL;
  deleteDataBtn.dataset.armed = deleteAccountBtn.dataset.armed = '';
}

document.getElementById('privacy-btn')?.addEventListener('click', (e) => {
  privacyStatus.textContent = '';
  resetPrivacyButtons();
  openModal(privacyOverlay, e.currentTarget);
});
document.getElementById('privacy-close')?.addEventListener('click', closeModal);
privacyOverlay?.addEventListener('click', (e) => { if (e.target === privacyOverlay) closeModal(); });

async function deleteConversations() {
  const user = auth.currentUser;
  if (!user) throw new Error('Not signed in.');
  const token = await user.getIdToken(true);
  const res = await fetch('/account/data', { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) {
    let detail = 'Request failed.';
    try { detail = (await res.json()).detail || detail; } catch { /* keep default */ }
    throw new Error(detail);
  }
  return (await res.json()).conversations_deleted;
}

// Two-step confirm (first click arms, second click performs) — no blocking browser dialogs.
function armOrRun(btn, armedText, action) {
  btn.addEventListener('click', async () => {
    if (btn.dataset.armed !== '1') {
      resetPrivacyButtons();
      btn.dataset.armed = '1';
      btn.textContent = armedText;
      privacyStatus.textContent = 'Press the button again to confirm. This cannot be undone.';
      return;
    }
    resetPrivacyButtons();
    btn.disabled = true;
    try {
      await action();
    } catch (err) {
      privacyStatus.textContent = `Error: ${err.message}`;
    } finally {
      btn.disabled = false;
    }
  });
}

armOrRun(deleteDataBtn, 'CONFIRM: DELETE ALL MY CONVERSATIONS', async () => {
  const n = await deleteConversations();
  historyList.innerHTML = '';
  privacyStatus.textContent = `Deleted ${n} conversation${n === 1 ? '' : 's'}.`;
  addLog('Your stored conversations were deleted', true);
});

armOrRun(deleteAccountBtn, 'CONFIRM: DELETE ACCOUNT AND ALL DATA', async () => {
  await deleteConversations();
  try {
    await deleteUser(auth.currentUser);
  } catch (err) {
    if (err.code === 'auth/requires-recent-login') {
      privacyStatus.textContent = 'Your conversations were deleted. To finish deleting your account, sign out, sign in again, then retry (a recent sign-in is required).';
      return;
    }
    throw err;
  }
  window.location.href = '/login.html';
});

historyLoadMoreBtn?.addEventListener('click', () => fetchHistory(historyOffset));

// ── SEND MESSAGE ──
function sendMessage(text) {
  if (!text.trim()) return;
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    addLog('ERROR: Not connected to backend');
    return;
  }
  addLog(`YOU: ${text}`);
  updateMobileLog(`YOU: ${text}`);
  document.getElementById('response-text').textContent = 'Processing...';
  ws.send(JSON.stringify({ text }));
}

// ── CLOCK ──
function updateClock() {
  document.getElementById('clock').textContent =
    new Date().toLocaleTimeString('en-US', { hour12: false });
}
setInterval(updateClock, 1000);
updateClock();

// ── MOBILE LOG ──
function updateMobileLog(text) {
  const el = document.getElementById('mobile-log');
  if (el) el.textContent = text;
}

// ── THREE.JS ORB ──
const orb = initOrb('orb-canvas');

// ── LOG ──
const logContainer = document.getElementById('log-container');

function addLog(text, highlight = false) {
  const el = document.createElement('div');
  el.className = 'log-entry' + (highlight ? ' highlight' : '');
  el.textContent = `[${new Date().toLocaleTimeString('en-US', { hour12: false })}] ${text}`;
  logContainer.prepend(el);
  while (logContainer.children.length > 10) logContainer.removeChild(logContainer.lastChild);
}

// ── TYPEWRITER ──
const responseText = document.getElementById('response-text');
let typingAborted = false;

async function typeResponse(text) {
  typingAborted = true;
  await new Promise(r => setTimeout(r, 0));
  typingAborted = false;

  responseText.textContent = '';
  orb.setAmplitude(0.6);

  // Reveal in chunks rather than one character at a time — each DOM update
  // has its own overhead, which dominates for long text if the per-char
  // delay is pushed very low. Capping the step count bounds total time
  // regardless of response length while still looking like it's typing.
  const TARGET_TOTAL_MS = 700;
  const MAX_STEPS = 40;
  const steps = Math.min(text.length, MAX_STEPS);
  const chunkSize = Math.ceil(text.length / steps);
  const perStepDelay = TARGET_TOTAL_MS / steps;

  for (let i = 0; i < text.length; i += chunkSize) {
    if (typingAborted) return;
    responseText.textContent = text.slice(0, i + chunkSize);
    await new Promise(r => setTimeout(r, perStepDelay));
    orb.setAmplitude(0.4 + Math.random() * 0.4);
  }
  responseText.textContent = text;
  orb.setAmplitude(0);
}

// ── VOICE INPUT ──
const micBtn = document.getElementById('mic-btn');
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

if (SpeechRecognition) {
  document.getElementById('voice-state').textContent = 'AVAILABLE';
  const recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.lang = 'en-US';
  recognition.interimResults = false;

  recognition.onstart = () => {
    micBtn.classList.add('active');
    addLog('MIC: Listening...', true);
    updateMobileLog('Listening...');
    orb.setAmplitude(0.2);
  };

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    addLog(`MIC: Captured — "${transcript}"`);
    sendMessage(transcript);
  };

  recognition.onend = () => {
    micBtn.classList.remove('active');
    orb.setAmplitude(0);
  };

  recognition.onerror = (e) => {
    addLog(`MIC ERROR: ${e.error}`);
    micBtn.classList.remove('active');
    orb.setAmplitude(0);
  };

  micBtn.addEventListener('click', () => recognition.start());

} else {
  document.getElementById('voice-state').textContent = 'UNSUPPORTED';
  micBtn.setAttribute('aria-disabled', 'true');
  micBtn.style.opacity = '0.6';
  micBtn.title = 'Voice input is not supported in this browser';
  micBtn.addEventListener('click', () => {
    addLog('Voice input is not supported in this browser — you can type instead');
  });
}

// ── TEXT INPUT & SEARCH ──
const chatInput = document.getElementById('chat-input');
const searchBtn = document.getElementById('search-btn');

document.getElementById('send-btn').addEventListener('click', () => {
  sendMessage(chatInput.value);
  chatInput.value = '';
});

chatInput.addEventListener('keydown', e => {
  if (e.key === 'Enter') {
    sendMessage(chatInput.value);
    chatInput.value = '';
  }
});

// Web search button + Ctrl+K shortcut
async function doWebSearch(query) {
  if (!query.trim()) return;
  addLog(`Searching: "${query}"`, true);
  document.getElementById('response-text').textContent = 'Searching the web...';

  try {
    const token = await auth.currentUser?.getIdToken();
    const res = await fetch('/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ query })
    });
    const data = await res.json();
    if (data.error) {
      addLog(`Search error: ${data.error}`);
      return;
    }
    typeResponse(`Found ${data.results.length || 0} results for "${query}". Sending to JOESTAR for analysis...`);
    sendMessage(`Search results for "${query}": ${JSON.stringify(data.results).slice(0, 500)}...`);
  } catch (e) {
    addLog(`Search failed: ${e.message}`);
  }
}

searchBtn.addEventListener('click', () => {
  const query = chatInput.value;
  if (query.trim()) {
    doWebSearch(query);
    chatInput.value = '';
  }
});

document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    chatInput.focus();
    addLog('Search mode active', true);
  }
});

// ── AUDIO OUTPUT ──
let audioEnabled = true;

function playAudio(base64Audio) {
  if (!audioEnabled) return;
  try {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const binaryString = atob(base64Audio);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    audioContext.decodeAudioData(bytes.buffer, (buffer) => {
      const source = audioContext.createBufferSource();
      source.buffer = buffer;
      source.connect(audioContext.destination);
      source.start(0);
    });
  } catch (e) {
    try {
      const audio = new Audio(`data:audio/mp3;base64,${base64Audio}`);
      audio.play().catch(() => addLog('Audio playback error'));
    } catch (err) {
      addLog(`Audio error: ${err.message}`);
    }
  }
}

document.addEventListener('keydown', (e) => {
  if (e.altKey && e.key.toLowerCase() === 'm') {
    audioEnabled = !audioEnabled;
    addLog(`Audio ${audioEnabled ? 'ON' : 'OFF'}`, true);
  }
});

// ── BOOT LOG ──
addLog('Connecting to backend...');
addLog('Press Alt+M to toggle spoken replies');