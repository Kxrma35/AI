import { initOrb, connectAudioToOrb } from './orb.js';
import { initSpeechRecognition } from './voice.js';

const ws = new WebSocket("ws://localhost:8000/ws");
const audioEl = new Audio();
const orbContainer = document.getElementById("orb-container");

// Init orb
initOrb(orbContainer);

// Speech recognition
const recognition = initSpeechRecognition((transcript) => {
    console.log("Heard:", transcript);
    document.getElementById("transcript").textContent = transcript;
    ws.send(JSON.stringify({ text: transcript }));
});

// Handle WebSocket messages
ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);

    if (msg.type === "text") {
        document.getElementById("response").textContent = msg.content;
    }

    if (msg.type === "audio") {
        const audioData = atob(msg.content);
        const byteArray = new Uint8Array(audioData.length);
        for (let i = 0; i < audioData.length; i++) {
            byteArray[i] = audioData.charCodeAt(i);
        }
        const blob = new Blob([byteArray], { type: "audio/mpeg" });
        audioEl.src = URL.createObjectURL(blob);
        connectAudioToOrb(audioEl);
        audioEl.play();
    }
};

// Mic button
document.getElementById("mic-btn").addEventListener("click", () => {
    recognition.start();
    document.getElementById("mic-btn").classList.add("active");
});

audioEl.onended = () => {
    document.getElementById("mic-btn").classList.remove("active");
};