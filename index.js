type="module">
  // ── CLOCK ──
  function updateClock() {
    const now = new Date();
    document.getElementById('clock').textContent =
      now.toLocaleTimeString('en-US', { hour12: false });
  }
  setInterval(updateClock, 1000);
  updateClock();
 
  // ── THREE.JS ORB ──
  import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js';
 
  const canvas = document.getElementById('orb-canvas');
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(280, 280);
 
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(60, 1, 0.1, 100);
  camera.position.z = 3;
 
  // Core sphere
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
 
  // ── Vertex displacement (breathing effect) ──
  const posAttr = geo.attributes.position;
  const origPos = new Float32Array(posAttr.array);
  let speaking = false;
  let amplitude = 0;
  let targetAmplitude = 0;
 
  function animate(time) {
    requestAnimationFrame(animate);
 
    // Smooth amplitude
    amplitude += (targetAmplitude - amplitude) * 0.08;
 
    // Displace vertices
    for (let i = 0; i < posAttr.count; i++) {
      const ox = origPos[i * 3];
      const oy = origPos[i * 3 + 1];
      const oz = origPos[i * 3 + 2];
      const noise = Math.sin(time * 0.001 + ox * 3 + oy * 2) * 0.04;
      const speechNoise = amplitude * Math.sin(time * 0.005 * (i % 7 + 1)) * 0.3;
      const scale = 1 + noise + speechNoise;
      posAttr.setXYZ(i, ox * scale, oy * scale, oz * scale);
    }
    posAttr.needsUpdate = true;
    geo.computeVertexNormals();
 
    // Rotation
    sphere.rotation.y += 0.004 + amplitude * 0.02;
    sphere.rotation.x += 0.001;
 
    // Color
    const hue = 0.55 + amplitude * 0.05;
    mat.color.setHSL(hue, 1.0, 0.5 + amplitude * 0.2);
    mat.emissive.setHSL(0.6, 1, amplitude * 0.15);
    mat.opacity = 0.7 + amplitude * 0.25;
 
    // Light pulse
    pLight.intensity = 3 + amplitude * 8;
 
    renderer.render(scene, camera);
  }
  animate(0);
 
  // ── DEMO INTERACTION ──
  const logContainer = document.getElementById('log-container');
  const responseText = document.getElementById('response-text');
  const chatInput = document.getElementById('chat-input');
  const micBtn = document.getElementById('mic-btn');
 
  const RESPONSES = [
    "Good morning, Sir. You have four engagements today, beginning with Meridian Logistics at 0930 hours. Shall I prepare a briefing?",
    "Weather analysis complete. Current conditions: 28 degrees Celsius, clear skies. Humidity at 72%. Optimal conditions for outdoor activity, Sir.",
    "Meridian Logistics — 42 staff, ongoing engagement for six weeks. I've identified three structural bottlenecks in their management hierarchy. Recommend flattening to two tiers.",
    "Running diagnostics. All systems nominal. Neural core operating at peak efficiency. Memory allocation stable at 67 percent.",
    "Of course, Sir. I've located the relevant files and summarized the key points. Shall I send them to your display?",
  ];
 
  let responseIdx = 0;
 
  function addLog(text, highlight = false) {
    const el = document.createElement('div');
    el.className = 'log-entry' + (highlight ? ' highlight' : '');
    el.textContent = `[${new Date().toLocaleTimeString('en-US',{hour12:false})}] ${text}`;
    logContainer.prepend(el);
    while (logContainer.children.length > 10) {
      logContainer.removeChild(logContainer.lastChild);
    }
  }
 
  async function typeResponse(text) {
    responseText.textContent = '';
    responseText.parentElement.style.borderColor = 'var(--cyan)';
    speaking = true;
    targetAmplitude = 0.6;
 
    for (let i = 0; i < text.length; i++) {
      responseText.textContent += text[i];
      await new Promise(r => setTimeout(r, 18 + Math.random() * 12));
      // Vary amplitude as if speaking
      targetAmplitude = 0.4 + Math.random() * 0.4;
    }
 
    targetAmplitude = 0;
    speaking = false;
  }
 
  async function handleSend() {
    const query = chatInput.value.trim();
    if (!query) return;
 
    addLog(`USER: ${query}`, false);
    chatInput.value = '';
 
    await new Promise(r => setTimeout(r, 400));
 
    const reply = RESPONSES[responseIdx % RESPONSES.length];
    responseIdx++;
 
    addLog('JARVIS: Processing...', true);
    await typeResponse(reply);
    addLog(`JARVIS: ${reply.substring(0, 40)}...`, true);
  }
 
  document.getElementById('send-btn').addEventListener('click', handleSend);
  chatInput.addEventListener('keydown', e => { if (e.key === 'Enter') handleSend(); });
 
  micBtn.addEventListener('click', () => {
    micBtn.classList.toggle('active');
    if (micBtn.classList.contains('active')) {
      addLog('MIC: Listening...', true);
      targetAmplitude = 0.2;
      setTimeout(() => {
        micBtn.classList.remove('active');
        targetAmplitude = 0;
        chatInput.value = RESPONSES[responseIdx % RESPONSES.length].substring(0, 30) + '...';
        addLog('MIC: Input captured', false);
      }, 2500);
    }
  });
 
  // Initial log
  addLog('JARVIS ONLINE — All systems nominal', true);
  addLog('Neural core initialized');
  addLog('Memory systems loaded — 847 entries');
  addLog('Tools loaded: weather, calendar, files, search');
  addLog('Awaiting user input...');
 
  // Auto demo
  setTimeout(async () => {
    await typeResponse(RESPONSES[0]);
    addLog('JARVIS: Morning briefing delivered', true);
  }, 1500);