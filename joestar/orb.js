import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js';

let scene, camera, renderer, sphere, material;
let analyser, dataArray;
let audioContext, source;

export function initOrb(container) {
    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(75, 1, 0.1, 1000);
    camera.position.z = 2.5;

    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(400, 400);
    renderer.setPixelRatio(window.devicePixelRatio);
    container.appendChild(renderer.domElement);

    // Geometry
    const geometry = new THREE.IcosahedronGeometry(1, 6);

    material = new THREE.MeshPhongMaterial({
        color: 0x00bfff,
        emissive: 0x003366,
        wireframe: true,
        transparent: true,
        opacity: 0.85,
    });

    sphere = new THREE.Mesh(geometry, material);
    scene.add(sphere);

    // Lighting
    const light = new THREE.PointLight(0x00ffff, 2, 10);
    light.position.set(2, 2, 2);
    scene.add(light);
    scene.add(new THREE.AmbientLight(0x001133));

    animate();
}

function animate() {
    requestAnimationFrame(animate);

    let amplitude = 0;

    if (analyser) {
        analyser.getByteFrequencyData(dataArray);
        amplitude = dataArray.reduce((a, b) => a + b, 0) / dataArray.length / 255;
    }

    // Scale orb with audio amplitude
    const scale = 1 + amplitude * 0.5;
    sphere.scale.set(scale, scale, scale);

    // Subtle idle rotation
    sphere.rotation.x += 0.002;
    sphere.rotation.y += 0.003;

    // Color shift when speaking
    material.color.setHSL(0.55 + amplitude * 0.1, 1, 0.5 + amplitude * 0.3);
    material.emissive.setHSL(0.6, 1, amplitude * 0.2);

    renderer.render(scene, camera);
}

export function connectAudioToOrb(audioElement) {
    if (!audioContext) {
        audioContext = new AudioContext();
    }

    source = audioContext.createMediaElementSource(audioElement);
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    dataArray = new Uint8Array(analyser.frequencyBinCount);

    source.connect(analyser);
    analyser.connect(audioContext.destination);
}