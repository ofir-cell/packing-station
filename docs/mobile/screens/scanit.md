# Scanit — `/m/scanit` (data: `GET /api/scanit/scan?code=`, `GET /api/scanit/item?sku=`)

**Blueprint:** S13, flow 4.9, rules 5.1, 5.8, 5.12, pieces N6, N9, N15, N17. **Release: 1.0. Read-only.**
**Mockup:** [`../mockups/scanit.html`](../mockups/scanit.html) → `scanit.png`, `scanit-dark.png`, `scanit-ipad.png`
**User:** a host on air. The phone or iPad stands beside her; one hand holds the product; she glances at the screen from arm's length and must never have to touch it between products. Also opened by cs, manager and admin to check a product.
**Purpose:** scan the product in her hand → read its name, retail price, our target price and its notes, and know which of those are checked facts and which are guesses before she says them on air.

## Two entries, one screen
| Account | Entry | Nav bar |
|---|---|---|
| host (`can.scanit`, not `can.pick`) | the **Scanit tab** — tab root | no back button; trailing avatar → `openTab('account')` |
| cs, manager, admin | Today → row "Scanit" — pushed in the Today tab | `.m-navbar__back` "Today"; no trailing button |
| worker | none; the server answers 403 | — |

The page is the same in both; it shows the back button only when it was pushed (the Today row adds `?from=today`; with no parameter it is a root).

## Layout at 390pt — ready (before the first scan)
1. **Nav bar** as above. Inline title "Scanit".
2. **Large title** "Scanit". Subtitle "Scan a product to see its price and notes."
3. **Demo banner** when the session says `sandbox` (`.m-banner--warn`): "Demo company — sample data."
4. **Ready block** (`.m-empty`): barcode icon tile · title **"Ready to scan"** · body "Scan the barcode on the product, or tap Scan product."
   - Once a hardware scanner has been seen on this device (`M.scannerSeen`), a `.m-banner--ok` sits above it: "Scanner ready — scan a product any time".
5. **Sticky action bar:** primary **"Scan product"** (`.m-btn--primary`, barcode icon → `M.scan()`: the camera sheet in the app, the type-it sheet in a browser) + auxiliary keyboard button (`.m-actionbar__aux`, `aria-label` "Type a barcode or SKU" → `M.typeCode()`; sheet title "Type a barcode or SKU", field label "Barcode or SKU", button "Show product").

Three inputs, as on every scan screen (blueprint rule 5.1): Bluetooth/USB scanner with nothing tapped (`M.onScan`), camera, typing.

**Screen stays awake** while this page is in front (bridge keep-awake on at `pageshow` / `visibilitychange: visible`, off at `pagehide` / hidden). In a browser nothing happens; that is acceptable.

## Layout at 390pt — the product card
The card replaces the ready block. Top to bottom:

1. **Flags row** (only when one applies; `.m-pill`s, wrap allowed):
   - `created: true` and not `needs_review` → `.m-pill--brand` **"New — added to the catalog"**
   - `needs_review: true` → no pill; the banner in "States" below
2. **Product** (`.m-card`, class `sc-card`):
   - **Picture** 112×112, radius 12, `object-fit: contain` on `--surface`. No `image_url`, or the image fails to load → a placeholder tile with the `tag` icon (never a broken image).
   - **Name** — 22px / 800 (`--m-fs-title2`), up to 3 lines, then ellipsis. Shown as stored.
   - **Category** — 15px muted, one line. Hidden when empty or "Needs review".
   - **Barcode** — 13px muted, tabular digits. Hidden when empty.
3. **Prices** — two tiles side by side (`.m-stats`, each `.m-stat` with class `sc-price`); the value is **34px / 800** (`--m-fs-largetitle`), so both prices read from arm's length:
   - **Retail price** — `msrp` as "$48.00". Under it, the **source line** (13px) and, when the price is not a checked fact, a pill. See "Source labels".
   - **Our target** — `target_price` as "$19.00" in `--brand-ink`. `0` → value "—" and the line "No target price set".
   - Long values (≥ $1,000.00) step down to 28px so two tiles always fit at 375pt.
4. **Notes** (`.m-section`, header "Notes", trailing source text or pill):
   - Fragrance shape (`notes.top` / `heart` / `base`): `.m-list` of three rows, label 13px/700 uppercase muted ("Top", "Heart", "Base") above the text at **19px / 600**, wrapping freely. A missing line is omitted.
   - Points shape (`notes.points`, up to 6): `.m-list`, one row per point, 19px / 600, each with a leading 6px dot.
   - No notes → see "Looking up details" and "States".
5. **Scanned this session** (`.m-section`, header "Scanned this session · {n}"; shown from the second product on): `.m-list` rows, newest first, the product in front marked with the 3px brand inset bar — lead = 36pt picture or placeholder, title = name, sub = "Retail $48.00 · Target $19.00", trailing chevron. Tap → that product's card (re-read with `GET /api/scanit/item` so it is current). Held in memory only: up to 20 products, gone when the page reloads or the app closes. No "clear" control.
6. **Sticky action bar** unchanged: "Scan product" + keyboard. The next scan from any input replaces the card; the previous product moves into the list.

### On a stand: iPad and landscape (width ≥ 700px)
Two columns inside the centred column: left = picture (200×200), name (28px), category, the two price tiles with **44px** values; right = Notes at **22px** and, under them, "Scanned this session". The action bar stays at the bottom, the primary button capped at 604px as on Pick. Portrait and both landscapes use the same rule (size class, not device). Nothing exists only on iPad.

## Source labels (blueprint rule 5.12)
A host must be able to tell a checked fact from a guess at a glance. Checked sources are plain text; anything else carries a pill with a word, never colour alone.

**Retail price** (`msrp`, `msrp_manual`, `msrp_source`):
| Data | Source line | Pill |
|---|---|---|
| `msrp_manual: true` | "Set by your team" | none |
| `msrp_source` starts with `http` | "From the brand's page · {site name}" (the host part of the address, as text — **not a link**) | none |
| `msrp_source` = `ai-estimate` | "Not a checked price" | `.m-pill--pending` **"Estimate"** |
| any other non-empty `msrp_source` (a barcode database name, e.g. "UPCitemdb") | "Store price · {database name}" | `.m-pill` (gray) **"Store price"** |
| `msrp` > 0 and no source recorded | "Source not recorded" | `.m-pill` (gray) **"Unchecked"** |
| `msrp` = 0 | value "—", line "No retail price yet" | none |

**Notes** (`notes_source`):
| Data | Header trailing text | Pill |
|---|---|---|
| `manual` | "Written by your team" | none |
| starts with `http` | "Found on the web · {site name}" (text, not a link) | none |
| `web` | "Found on the web" | none |
| `ai-unchecked` | "Not checked against a source" | `.m-pill--pending` **"Unchecked"** |
| notes present, source empty | "Source not recorded" | `.m-pill` (gray) **"Unchecked"** |

Source addresses are never tappable: `/m/` screens do not open other sites (rule 5.8).

## Looking up details (`info_status: "looking"`)
- The card shows everything the catalog already has. Missing parts show their place: a price tile with a `.m-skeleton` value, and/or the Notes section with two skeleton rows.
- One line under the prices, with a small spinner: **"Looking up details…"**.
- The page re-reads `GET /api/scanit/item?sku=` every 3 s while this product is in front and the page is visible, and fills the card in place (no jump: reserved heights). The host does nothing.
- `info_status` becomes `done` → the line disappears; new values appear with their source labels.
- `info_status` becomes `failed`, or stays `looking` for 90 s → polling stops; the line reads **"No more details found."** (muted, no button — there is no "look up again" on the phone in 1.0; the server retries on its own later).
- A new scan, or leaving the card, stops the polling for the old product.

## States
| State | Trigger | Treatment |
|---|---|---|
| Looking a barcode up | a scan request has not answered within 0.6 s | the card area shows a skeleton card and **"Looking this barcode up…"**; after 4 s the line adds "New products take a little longer." The primary button is disabled. The request is never sent twice: a scan that arrives meanwhile gets the toast "Still looking up the last one — scan again in a moment." (said, not dropped) |
| Lookup too slow | no answer after 30 s (see "Assumptions") | `.m-banner--error`: "This is taking too long. Scan the product again." The previous card, if any, returns |
| New, recognised | `found`, `created: true`, not `needs_review` | card + pill "New — added to the catalog" + under the name "Found in {created_source}" when given. Haptic `success` |
| New, not recognised | `needs_review: true` | `.m-banner--warn` above the card: **"New product — not recognised. Ask an admin to complete it."** The card shows the barcode as the title (the stored placeholder name is not read out as a product name), no category, prices "—". Haptic `warning` |
| Not a product barcode | `found: false` (shipping label, link, text) | `.m-banner--error` under the title, kept until the next good scan: **"That's not a product barcode"** · "{code, first 24 characters}" · "Scan the barcode on the product's box." Toast with the same first line. Haptic `error`. The last card stays below |
| Empty code | `ok: false` | nothing changes |
| Details failed / AI not set up | `info_status` `failed`, or no notes and no lookup running | card as stored; Notes section reads "No notes for this product." or "No more details found." |
| Offline | `navigator.onLine` false or the request fails to connect | `.m-banner--offline`: **"Scanit needs a connection."** The last card stays on screen. A scan while offline: toast "Scanit needs a connection" (haptic `error`) |
| Server error | 5xx / unreadable answer | toast "Couldn't look that up. Scan it again." The last card stays |
| Wrong role | 403 | the page shows only `.m-empty`: "Your account can't open this." / "Ask your manager." No action bar |
| Session ended | 401 or a sign-in redirect | tell the shell (bridge "session ended"); the shell shows Sign-in. After sign-in the person lands on Today — one tap back to Scanit |
| Subscription inactive | 402 `billing` | tell the shell; it shows the "subscription not active" state. Never `/billing` |
| Demo company | session `sandbox` | the demo banner; nothing else differs on the phone. The server answers every scan from seeded data or a fixed answer (blueprint N17) |

**Feedback:** haptic `success` on a found product, `warning` on "not recognised", `error` on "not a product barcode" and on failures. **No sound from the phone**: it stands next to a live microphone, and a hardware scanner already beeps. (If Ofir wants a sound, it is a setting for 1.1, not a default.)

## What is not on this screen (1.0)
No edit of name, price or notes. No "look up again". No favourites. No search by product name. No selling scripts. No scan history that outlives the page. No link to the desktop `/scanit`. No "coming soon" row for any of these.

## Copy (EN → ES needed for every label; product names, categories and notes stay as stored)
| Key | English | Spanish |
|---|---|---|
| title | Scanit | Scanit |
| sub | Scan a product to see its price and notes. | Escanea un producto para ver su precio y notas. |
| ready | Ready to scan | Listo para escanear |
| readybody | Scan the barcode on the product, or tap Scan product. | Escanea el código de barras del producto o toca Escanear producto. |
| scan | Scan product | Escanear producto |
| type | Type a barcode or SKU | Escribir código de barras o SKU |
| show | Show product | Ver producto |
| retail | Retail price | Precio de lista |
| target | Our target | Nuestro objetivo |
| notes | Notes | Notas |
| top / heart / base | Top / Heart / Base | Salida / Corazón / Fondo |
| team | Set by your team | Definido por tu equipo |
| teamnotes | Written by your team | Escrito por tu equipo |
| brand | From the brand's page | De la página de la marca |
| estimate | Estimate | Estimado |
| notchecked | Not a checked price | Precio no verificado |
| store | Store price | Precio de tienda |
| unchecked | Unchecked | Sin verificar |
| web | Found on the web | Encontrado en la web |
| nosource | Source not recorded | Fuente no registrada |
| looking | Looking up details… | Buscando detalles… |
| nomore | No more details found. | No se encontraron más detalles. |
| lookingcode | Looking this barcode up… | Buscando este código… |
| new | New — added to the catalog | Nuevo — agregado al catálogo |
| unknown | New product — not recognised. Ask an admin to complete it. | Producto nuevo — no reconocido. Pide a un administrador que lo complete. |
| notproduct | That's not a product barcode | Ese no es un código de producto |
| offline | Scanit needs a connection. | Scanit necesita conexión. |
| session | Scanned this session | Escaneados en esta sesión |

Spanish wording is a first draft for whoever reviews floor Spanish.

## Components
`.m-screen--has-actionbar` `.m-navbar` `.m-navbar__back` `.m-largetitle` `.m-banner--warn|--ok|--error|--offline` `.m-empty` `.m-card` `.m-stats` `.m-stat` `.m-pill` `.m-pill--brand` `.m-pill--pending` `.m-section` `.m-list` `.m-row--lead` `.m-skeleton` `.m-actionbar` `.m-btn--primary` `.m-actionbar__aux` `.m-toast` + the type-it sheet from `mobile.js`. Screen-local classes (prefix `sc-`): `sc-card`, `sc-pic`, `sc-name`, `sc-price`, `sc-src`, `sc-note`, `sc-cols` (the ≥700px two-column grid).

## Bridge
`scan()` · `haptic()` · `openTab('account')` (host avatar) · keep-awake on/off · session ended.

## Assumptions the spec makes — to be confirmed by their owners
- **Total time limit of a first scan** (N15c): the spec gives up at 30 s on the phone. The server limit must be shorter than that, or this number changes. → programmer.
- **Pictures from other hosts** (N15d): the spec draws `image_url` as given, with a placeholder on failure. If outside pictures are not allowed in `/m/`, the picture is the placeholder until pictures are stored on our side. → programmer / security-reviewer / app-review.
- **The scan is a GET that writes** (N15b): the page calls it exactly once per scan and never prefetches or retries it automatically. → mobile-engineer.
- A product with no `msrp_source` and `msrp_manual: false` is treated as unchecked. → programmer to say whether such rows exist.

## Question for Ofir (not a blocker; look at the mockup)
The phone may be caught by the live camera. **Our target price** is shown as large as the retail price. Options: (a) keep it as drawn; (b) show it smaller and unlabelled so only the host knows what it is. The mockup draws (a).

## Acceptance
Passes DESIGN_SYSTEM §6.3 for host, cs, manager and admin. At 390pt with a 3-line name and three fragrance notes, both prices and the first note are visible without scrolling above the action bar. No tappable element links off our host. A worker gets the 403 state, not a blank page.
