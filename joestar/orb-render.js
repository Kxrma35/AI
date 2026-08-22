import * as THREE from 'three';

// Shared Three.js orb renderer used by both the main app and the login page.
export function initOrb(canvasId, { minSize = 170, maxSize = 320, desktopSize = 280 } = {}) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return null;

  function getOrbSize() {
    if (window.innerWidth > 768) return desktopSize;
    const smallest = Math.min(window.innerWidth, window.innerHeight);
    return Math.round(Math.min(Math.max(smallest * 0.6, minSize), maxSize));
  }

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(window.devicePixelRatio);

  function resizeRenderer() {
    const size = getOrbSize();
    renderer.setSize(size, size);
    canvas.style.width = size + 'px';
    canvas.style.height = size + 'px';
  }
  resizeRenderer();
  window.addEventListener('resize', resizeRenderer);

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

  return {
    setAmplitude(value) { targetAmplitude = value; },
  };
}
