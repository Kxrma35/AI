import { initOrb } from './orb-render.js';
import { auth } from './firebase-config.js';
import { onAuthStateChanged, signOut } from 'https://www.gstatic.com/firebasejs/12.6.0/firebase-auth.js';

// ── AUTH ──
let ws;
const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';

function connectWebSocket(token) {
  ws = new WebSocket(`${wsProtocol}//${window.location.host}/ws?token=${encodeURIComponent(token)}`);

  ws.onopen = () => addLog('JOESTAR ONLINE — Connected to backend', true);

  ws.onerror = () => {
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

  for (let i = 0; i < text.length; i++) {
    if (typingAborted) return;
    responseText.textContent += text[i];
    await new Promise(r => setTimeout(r, 14 + Math.random() * 10));
    orb.setAmplitude(0.4 + Math.random() * 0.4);
  }
  orb.setAmplitude(0);
}

// ── VOICE INPUT ──
const micBtn = document.getElementById('mic-btn');
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

if (SpeechRecognition) {
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
  micBtn.style.opacity = '0.4';
  micBtn.title = 'Voice requires Chrome';
  micBtn.addEventListener('click', () => {
    addLog('ERROR: Voice not supported — use Chrome');
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
    const res = await fetch('/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
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
addLog('Neural core initialized');
addLog('Memory systems loading...');
addLog('Tools ready: web search, files, calendar, voice');
addLog('Voice output active — Press Alt+M to toggle sound');
addLog('Awaiting your command, Sir...');
updateMobileLog('SYSTEMS ONLINE — AWAITING COMMAND');