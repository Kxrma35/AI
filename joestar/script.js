import * as THREE from 'three';

// ── CLOCK ──
function updateClock() {
  const now = new Date();
  document.getElementById('clock').textContent =
    now.toLocaleTimeString('en-US', { hour12: false });
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

// Core wireframe sphere
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

// Inner glow sphere
const innerGeo = new THREE.SphereGeometry(0.85, 16, 16);
const innerMat = new THREE.MeshBasicMaterial({
  color: 0x003355,
  transparent: true,
  opacity: 0.4,
});
scene.add(new THREE.Mesh(innerGeo, innerMat));

// Lights
const pLight = new THREE.PointLight(0x00d4ff, 3, 10);
pLight.position.set(2, 2, 2);
scene.add(pLight);

const pLight2 = new THREE.PointLight(0x0044ff, 2, 10);
pLight2.position.set(-2, -1, -2);
scene.add(pLight2);

scene.add(new THREE.AmbientLight(0x001122, 2));

// Vertex positions for displacement animation
const posAttr = geo.attributes.position;
const origPos = new Float32Array(posAttr.array);

let amplitude = 0;
let targetAmplitude = 0;

function animate(time) {
  requestAnimationFrame(animate);

  // Smooth amplitude interpolation
  amplitude += (targetAmplitude - amplitude) * 0.08;

  // Displace vertices — gives the orb a breathing / speaking look
  for (let i = 0; i < posAttr.count; i++) {
    const ox = origPos[i * 3];
    const oy = origPos[i * 3 + 1];
    const oz = origPos[i * 3 + 2];
    const idle = Math.sin(time * 0.001 + ox * 3 + oy * 2) * 0.04;
    const speech = amplitude * Math.sin(time * 0.005 * ((i % 7) + 1)) * 0.3;
    const scale = 1 + idle + speech;
    posAttr.setXYZ(i, ox * scale, oy * scale, oz * scale);
  }
  posAttr.needsUpdate = true;
  geo.computeVertexNormals();

  // Rotation
  sphere.rotation.y += 0.004 + amplitude * 0.02;
  sphere.rotation.x += 0.001;

  // Color and opacity shift when active
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
  // Keep log trimmed to 10 entries
  while (logContainer.children.length > 10) {
    logContainer.removeChild(logContainer.lastChild);
  }
}

// ── TYPEWRITER RESPONSE ──
const responseText = document.getElementById('response-text');

async function typeResponse(text) {
  responseText.textContent = '';
  targetAmplitude = 0.6;

  for (let i = 0; i < text.length; i++) {
    responseText.textContent += text[i];
    await new Promise(r => setTimeout(r, 18 + Math.random() * 12));
    targetAmplitude = 0.4 + Math.random() * 0.4;
  }

  targetAmplitude = 0;
}

// ── WEBSOCKET ──
const ws = new WebSocket(`ws://${location.host}/ws`);
const audioEl = new Audio();
let pendingReply = null;

ws.addEventListener('open', () => addLog('LINK: WebSocket established', true));
ws.addEventListener('close', () => addLog('LINK: WebSocket closed'));
ws.addEventListener('error', () => addLog('LINK: WebSocket error', true));

ws.addEventListener('message', async (event) => {
  const msg = JSON.parse(event.data);

  if (msg.type === 'text') {
    addLog('JOESTAR: Response received', true);
    pendingReply = typeResponse(msg.content);
  }

  if (msg.type === 'audio') {
    const bin = atob(msg.content);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    const blob = new Blob([bytes], { type: 'audio/mpeg' });
    audioEl.src = URL.createObjectURL(blob);
    audioEl.play().catch(err => addLog(`AUDIO: ${err.message}`));
  }
});

async function handleSend() {
  const query = chatInput.value.trim();
  if (!query) return;
  if (ws.readyState !== WebSocket.OPEN) {
    addLog('LINK: Not connected', true);
    return;
  }

  addLog(`USER: ${query}`);
  chatInput.value = '';
  addLog('JOESTAR: Processing...', true);
  ws.send(JSON.stringify({ text: query }));
}

// ── EVENT LISTENERS ──
const chatInput = document.getElementById('chat-input');
const micBtn = document.getElementById('mic-btn');

document.getElementById('send-btn').addEventListener('click', handleSend);

chatInput.addEventListener('keydown', e => {
  if (e.key === 'Enter') handleSend();
});

// ── SPEECH RECOGNITION ──
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const recognition = SpeechRecognition ? new SpeechRecognition() : null;
if (recognition) {
  recognition.continuous = false;
  recognition.lang = 'en-US';
  recognition.interimResults = false;

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    chatInput.value = transcript;
    handleSend();
  };
  recognition.onerror = (e) => addLog(`MIC: ${e.error}`, true);
  recognition.onend = () => {
    micBtn.classList.remove('active');
    targetAmplitude = 0;
    addLog('MIC: Input captured');
  };
}

micBtn.addEventListener('click', () => {
  if (!recognition) {
    addLog('MIC: Speech API unavailable', true);
    return;
  }
  if (micBtn.classList.contains('active')) {
    recognition.stop();
    return;
  }
  micBtn.classList.add('active');
  addLog('MIC: Listening...', true);
  targetAmplitude = 0.25;
  recognition.start();
});

// ── BOOT SEQUENCE ──
addLog('JOESTAR ONLINE — All systems nominal', true);
addLog('Neural core initialized');
addLog('Memory systems loaded — 847 entries');
addLog('Tools loaded: weather, calendar, files, search');
addLog('Awaiting user input...');

addLog('Awaiting user input...');