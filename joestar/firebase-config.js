import { initializeApp } from "https://www.gstatic.com/firebasejs/12.6.0/firebase-app.js";
import { getAuth } from "https://www.gstatic.com/firebasejs/12.6.0/firebase-auth.js";

const firebaseConfig = {
  apiKey: "AIzaSyBCzhgJy_Q0WzBlCz1a2gpA4C_PL-aznBc",
  authDomain: "joestar-633bf.firebaseapp.com",
  projectId: "joestar-633bf",
  storageBucket: "joestar-633bf.firebasestorage.app",
  messagingSenderId: "1097927046667",
  appId: "1:1097927046667:web:261636a738e6bcc03d390e",
  measurementId: "G-Q3C958V06F"
};

export const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
