import { auth } from "./firebase-config.js";
import { initOrb } from "./orb-render.js";
import {
  onAuthStateChanged,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  updateProfile,
  GoogleAuthProvider,
  signInWithPopup,
} from "https://www.gstatic.com/firebasejs/12.6.0/firebase-auth.js";

initOrb('orb-canvas', { minSize: 90, maxSize: 140, desktopSize: 130 });

// If already signed in when this page loads, skip straight to the app.
// Fires once then unsubscribes — otherwise this listener would also fire
// (and redirect prematurely) the moment our own sign-up/sign-in calls below
// create or authenticate a user, racing ahead of updateProfile()/goToApp().
const unsubscribe = onAuthStateChanged(auth, (user) => {
  unsubscribe();
  if (user) window.location.href = "/";
});

const errorEl = document.getElementById("auth-error");

function showError(message) {
  errorEl.textContent = message;
  errorEl.classList.add("visible");
}

function clearError() {
  errorEl.textContent = "";
  errorEl.classList.remove("visible");
}

const FRIENDLY_ERRORS = {
  "auth/invalid-email": "That email address doesn't look right.",
  "auth/user-not-found": "No account found with that email.",
  "auth/wrong-password": "Incorrect password.",
  "auth/invalid-credential": "Incorrect email or password.",
  "auth/email-already-in-use": "An account already exists with that email.",
  "auth/weak-password": "Password must be at least 6 characters.",
  "auth/popup-closed-by-user": null, // user cancelled — not an error worth showing
};

function friendlyError(err) {
  if (err.code in FRIENDLY_ERRORS) return FRIENDLY_ERRORS[err.code];
  return err.message || "Something went wrong. Please try again.";
}

function goToApp() {
  window.location.href = "/";
}

// ── TAB SWITCHING ──
const tabSignin = document.getElementById("tab-signin");
const tabSignup = document.getElementById("tab-signup");
const formSignin = document.getElementById("signin-form");
const formSignup = document.getElementById("signup-form");

tabSignin.addEventListener("click", () => {
  clearError();
  tabSignin.classList.add("active");
  tabSignup.classList.remove("active");
  formSignin.style.display = "flex";
  formSignup.style.display = "none";
});

tabSignup.addEventListener("click", () => {
  clearError();
  tabSignup.classList.add("active");
  tabSignin.classList.remove("active");
  formSignup.style.display = "flex";
  formSignin.style.display = "none";
});

// ── SIGN IN ──
formSignin.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearError();
  const email = document.getElementById("signin-email").value;
  const password = document.getElementById("signin-password").value;

  try {
    await signInWithEmailAndPassword(auth, email, password);
    goToApp();
  } catch (err) {
    const msg = friendlyError(err);
    if (msg) showError(msg);
  }
});

// ── SIGN UP ──
formSignup.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearError();
  const name = document.getElementById("signup-name").value.trim();
  const email = document.getElementById("signup-email").value;
  const password = document.getElementById("signup-password").value;

  try {
    const cred = await createUserWithEmailAndPassword(auth, email, password);
    await updateProfile(cred.user, { displayName: name });
    await cred.user.reload();
    goToApp();
  } catch (err) {
    const msg = friendlyError(err);
    if (msg) showError(msg);
  }
});

// ── GOOGLE SIGN-IN ──
document.getElementById("google-btn").addEventListener("click", async () => {
  clearError();
  try {
    await signInWithPopup(auth, new GoogleAuthProvider());
    goToApp();
  } catch (err) {
    const msg = friendlyError(err);
    if (msg) showError(msg);
  }
});
