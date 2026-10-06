# JOESTAR compliance checklist (branch `compliance-testing`)

Status of the standing project checklist. **Legal text is draft, not legal advice. Have a lawyer review it before launch.**

| # | Item | Status | Where |
|---|------|--------|-------|
| 1 | Privacy policy | Done (draft) | `joestar/privacy.html` |
| 2 | Terms of service | Done (draft) | `joestar/terms.html` |
| 3 | Refund policy | Done: app is free, commitments for any future paid plan | `joestar/refund.html` |
| 4 | Cookie policy | Done | `joestar/cookies.html` |
| 5 | Cookie consent banner | Done: honest notice (only strictly-necessary storage exists); equal-weight opt-in buttons appear automatically if optional categories are added | `joestar/consent.js` |
| 6 | Form consents | Done: unticked 18+/Terms/Privacy checkbox required for sign-up and Google sign-in | `login.html`, `login.js` |
| 7 | No unnecessary data | Done: no analytics/ads; memory scoped per user; unused data not collected | |
| 8 | Third-party SDK audit | Done: see below | |
| 9 | Remove dark patterns | Done: none found; equal-weight consent buttons; two-step deletion confirm | |
| 10 | Hidden fees | N/A (free); Terms/Refund pledge up-front total pricing | |
| 11 | Fake reviews | None present | |
| 12 | Unsupported claims | Fixed: removed hard-coded CPU/MEM/memory %/"5/5 tools READY"/fake schedule/fake weather; status now reflects the real connection | `index.html`, `script.js` |
| 13 | Alt text / a11y labels | Done: no raster images; canvas `aria-hidden`; icon buttons labelled; form labels; live region for replies | |
| 14 | Colour contrast | Fixed: `--cyan-dim` lightened (4.8:1 to ~6.5:1), placeholders now full opacity | `style.css` |
| 15 | Keyboard navigation | Done: skip links, visible focus ring, modals trap focus/Esc/restore focus, sign-out and privacy are real buttons, reduced-motion support | |
| 16 | Business details | **Needs your input**: `joestar/legal-config.js` (address, email, registration no., country) | |
| 17 | Age consent / kids' data | Done: 18+ confirmation at sign-up; policy states service is not for children | |
| 18 | Unsubscribe link in emails | N/A: JOESTAR sends no marketing email (Firebase sends only transactional auth emails) | |
| 19 | License fonts/images/data | Done: fonts self-hosted with OFL texts, three.js MIT, Font Awesome CC BY attribution | `licenses.html`, `joestar/vendor/` |
| 20 | Data deletion request | Done: in-app "Privacy" panel (delete conversations / delete account) + `DELETE /account/data` | `main.py`, `memory.py`, `script.js` |

## Third-party audit
| Service | Receives | Notes |
|---|---|---|
| Firebase Auth / Google sign-in (Google) | email, name, password hash | SDK loaded from gstatic.com, the only third-party script on the pages |
| Groq, Google Gemini | messages + recent context | AI providers |
| Supabase | conversations + embeddings | database |
| Microsoft Edge TTS | reply text (<=600 chars) | **Uses an unofficial endpoint via `edge-tts`; check Microsoft's terms before commercial use** |
| Serper, OpenWeather | search terms / place names | only when used |
| Render | request logs | hosting |
| Browser speech recognition | audio (Chrome sends it to Google) | disclosed in privacy policy |
| ~~Google Fonts, jsDelivr (three.js), cdnjs (Font Awesome)~~ | | **Removed**: now self-hosted in `joestar/vendor/` (stops leaking visitor IPs to those CDNs) |

## Security issues found and fixed while auditing
1. **Public file exposure (critical):** the static mount served the whole `joestar/` folder, including `.env` (API keys, DB URL), `*.py`, and `data/`. Now an explicit allow-list is served. **If this app was ever run on a public host with a `.env` file present (not the Render deploy, where `.env` is gitignored, but possibly Docker/local), rotate the keys.**
2. `/search` was unauthenticated: now requires a sign-in.
3. Wildcard CORS removed (same-origin only). Security headers added.
4. `/history` token moved from the URL query string to an `Authorization` header (query strings end up in logs).
5. Conversations were shared across all users (history panel showed everyone's chats): now tagged with and scoped to the Firebase UID. Old untagged rows are hidden from everyone.
6. New optional `ALLOWED_EMAILS` env var (comma list). **Recommended: set it.** JOESTAR has a shell tool and sign-up is open to anyone, so without it any registered user can run commands on the server.

## Still open / for you to decide
- Fill in `legal-config.js` (marked `[to be provided]` on every page).
- Lawyer review of the policies; confirm governing-law country.
- Old conversations (`user_id` NULL) are invisible. To claim them as yours: `UPDATE conversations SET user_id = '<your firebase uid>' WHERE user_id IS NULL;`
- Firebase password minimum is 6 characters (Firebase default); consider raising it in the Firebase console.
- `Brain.user_name`, the reflection timestamp and SecureBot watermark are still global (single shared `Brain`); fine for one user, wrong for many.
- Legacy unused files `app.js`, `orb.js`, `voice.js` still reference a CDN but are not served.
- Not tested: signed-in screens (needs a real Firebase account) and the delete flows against live Supabase.
