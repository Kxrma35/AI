import * as THREE from 'three';

// ── WEBSOCKET ──
const ws = new WebSocket("ws://localhost:8000/ws");

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
  } else if (msg.type === "audio") {
    playAudio(msg.content);
    addLog(' Audio synthesized', true);
  }
};

// ── SEND MESSAGE ──
function sendMessage(text) {
  if (!text.trim()) return;
  if (ws.readyState !== WebSocket.OPEN) {
    addLog('ERROR: Not connected to backend');
    return;
  }
  addLog(`YOU: ${text}`);
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

// ── THREE.JS ORB ──
const canvas = document.getElementById('orb-canvas');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.setPixelRatio(window.devicePixelRatio);
renderer.setSize(280, 280);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(60, 1, 0.1, 100);
camera.position.z = 3;

const geo = new THREE.IcosahedronGeometry(1, 5);
const mat = new THREE.MeshPhongMaterial({
  color: 0x00d4ff,
  emissive: 0x002244,
  wireframe: true,
  transparent: true,
  opacity: 0.7,
});
const sphere = new THREE.Mesh(geo, mat);
scene.add(sphere);

const innerGeo = new THREE.SphereGeometry(0.85, 16, 16);
const innerMat = new THREE.MeshBasicMaterial({ color: 0x003355, transparent: true, opacity: 0.4 });
scene.add(new THREE.Mesh(innerGeo, innerMat));

const pLight = new THREE.PointLight(0x00d4ff, 3, 10);
pLight.position.set(2, 2, 2);
scene.add(pLight);
scene.add(new THREE.AmbientLight(0x001122, 2));

const posAttr = geo.attributes.position;
const origPos = new Float32Array(posAttr.array);
let amplitude = 0;
let targetAmplitude = 0;

function animate(time) {
  requestAnimationFrame(animate);
  amplitude += (targetAmplitude - amplitude) * 0.08;

  for (let i = 0; i < posAttr.count; i++) {
    const ox = origPos[i * 3], oy = origPos[i * 3 + 1], oz = origPos[i * 3 + 2];
    const idle = Math.sin(time * 0.001 + ox * 3 + oy * 2) * 0.04;
    const speech = amplitude * Math.sin(time * 0.005 * ((i % 7) + 1)) * 0.3;
    const s = 1 + idle + speech;
    posAttr.setXYZ(i, ox * s, oy * s, oz * s);
  }
  posAttr.needsUpdate = true;
  geo.computeVertexNormals();

  sphere.rotation.y += 0.004 + amplitude * 0.02;
  sphere.rotation.x += 0.001;
  mat.color.setHSL(0.55 + amplitude * 0.05, 1.0, 0.5 + amplitude * 0.2);
  mat.emissive.setHSL(0.6, 1, amplitude * 0.15);
  mat.opacity = 0.7 + amplitude * 0.25;
  pLight.intensity = 3 + amplitude * 8;

  renderer.render(scene, camera);
}
animate(0);

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

async function typeResponse(text) {
  responseText.textContent = '';
  targetAmplitude = 0.6;
  for (let i = 0; i < text.length; i++) {
    responseText.textContent += text[i];
    await new Promise(r => setTimeout(r, 14 + Math.random() * 10));
    targetAmplitude = 0.4 + Math.random() * 0.4;
  }
  targetAmplitude = 0;
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
    targetAmplitude = 0.2;
  };

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    addLog(`MIC: Captured — "${transcript}"`);
    sendMessage(transcript);
  };

  recognition.onend = () => {
    micBtn.classList.remove('active');
    targetAmplitude = 0;
  };

  recognition.onerror = (e) => {
    addLog(`MIC ERROR: ${e.error}`);
    micBtn.classList.remove('active');
    targetAmplitude = 0;
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
  addLog(`🔎 Searching: "${query}"`, true);
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
    typeResponse(`Found ${data.results.length || 0} results for "${query}". Sending to Claude for analysis...`);
    // Now send to brain for AI analysis
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

// Ctrl+K for search
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
    // Fallback: use Audio element
    try {
      const audio = new Audio(`data:audio/mp3;base64,${base64Audio}`);
      audio.play().catch(() => addLog('Audio playback error'));
    } catch (err) {
      addLog(`Audio error: ${err.message}`);
    }
  }
}

// Toggle audio with keyboard shortcut (Alt+M)
document.addEventListener('keydown', (e) => {
  if (e.altKey && e.key.toLowerCase() === 'm') {
    audioEnabled = !audioEnabled;
    addLog(`🔊 Audio ${audioEnabled ? 'ON' : 'OFF'}`, true);
  }
});

// ── BOOT LOG ──
addLog('Neural core initialized');
addLog('Memory systems loading...');
addLog('Tools ready: web search, files, calendar, voice');
addLog('Voice output active — Press Alt+M to toggle sound');
addLog('Awaiting your command, Sir...');