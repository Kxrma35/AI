// Cookie / browser-storage consent.
//
// Today JOESTAR only uses strictly necessary storage (Firebase sign-in session + this
// consent record), which does not require consent, so the banner is an honest notice.
// If an optional category is ever added (analytics, etc.) put its id in OPTIONAL_CATEGORIES
// and gate the code behind `window.joestarConsent.allowed("<id>")` — the banner then shows
// equally weighted "Accept optional" / "Essential only" buttons, and nothing optional
// may load before the visitor opts in.
const KEY = "joestar_consent_v1";
const OPTIONAL_CATEGORIES = []; // e.g. [{ id: "analytics", label: "Anonymous usage analytics" }]

function read() {
  try { return JSON.parse(localStorage.getItem(KEY)); } catch { return null; }
}
function write(choice) {
  try { localStorage.setItem(KEY, JSON.stringify({ ...choice, ts: new Date().toISOString() })); } catch { /* storage blocked */ }
}

window.joestarConsent = {
  allowed(id) {
    const c = read();
    return !!(c && Array.isArray(c.accepted) && c.accepted.includes(id));
  },
  reopen: () => showBanner(true),
};

function showBanner(force = false) {
  if (!force && read()) return;
  document.getElementById("consent-banner")?.remove();

  const hasOptional = OPTIONAL_CATEGORIES.length > 0;
  const el = document.createElement("div");
  el.id = "consent-banner";
  el.className = "consent-banner";
  el.setAttribute("role", "dialog");
  el.setAttribute("aria-labelledby", "consent-title");
  el.setAttribute("aria-modal", "false");
  el.innerHTML = `
    <h2 id="consent-title">COOKIES &amp; BROWSER STORAGE</h2>
    <p>JOESTAR only uses storage that is strictly necessary: it keeps you signed in and remembers this choice.
    We do not use advertising, analytics or tracking cookies.
    ${hasOptional ? `Optional: ${OPTIONAL_CATEGORIES.map(c => c.label).join(", ")}.` : ""}
    See our <a href="/cookies.html">Cookie Policy</a> and <a href="/privacy.html">Privacy Policy</a>.</p>
    <div class="consent-actions"></div>`;
  const actions = el.querySelector(".consent-actions");

  const mk = (text, fn) => {
    const b = document.createElement("button");
    b.type = "button"; b.textContent = text;
    b.addEventListener("click", () => { fn(); el.remove(); });
    actions.appendChild(b);
    return b;
  };
  let first;
  if (hasOptional) {
    first = mk("ESSENTIAL ONLY", () => write({ accepted: [] }));
    mk("ACCEPT OPTIONAL", () => write({ accepted: OPTIONAL_CATEGORIES.map(c => c.id) }));
  } else {
    first = mk("GOT IT", () => write({ accepted: [] }));
  }
  document.body.appendChild(el);
  if (force) first.focus();
}

function wire() {
  showBanner();
  document.querySelectorAll("[data-cookie-settings]").forEach((b) =>
    b.addEventListener("click", () => showBanner(true)));
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire);
else wire();
