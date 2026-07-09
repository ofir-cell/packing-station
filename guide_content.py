# -*- coding: utf-8 -*-
"""Starter help-guide content + anonymized screen mockups (SVG).

The platform owner can edit/delete these after boot; they're seeded once into
platform.db when the guides table is empty. Mockups carry NO real customer data
— buyers/orders are generic placeholders.
"""

# ── Shared SVG bits ────────────────────────────────────────────────
_W = 860
def _frame(title, inner, h=520, sub="LiveOpsHub"):
    """Wrap UI content in a light 'browser' frame."""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_W} {h}" font-family="'DM Sans',system-ui,Arial,sans-serif">
<rect width="{_W}" height="{h}" rx="16" fill="#f6f7f9"/>
<rect x="1" y="1" width="{_W-2}" height="{h-2}" rx="15" fill="none" stroke="#e4e7ec"/>
<rect x="0" y="0" width="{_W}" height="46" rx="16" fill="#ffffff"/>
<rect x="0" y="30" width="{_W}" height="16" fill="#ffffff"/>
<circle cx="24" cy="23" r="5" fill="#f87171"/><circle cx="42" cy="23" r="5" fill="#fbbf24"/><circle cx="60" cy="23" r="5" fill="#34d399"/>
<text x="90" y="28" font-size="13" font-weight="700" fill="#6366f1">{sub}</text>
<text x="{_W-24}" y="28" font-size="12" fill="#9ca3af" text-anchor="end">{title}</text>
{inner}
</svg>'''

def _num(x, y, n):
    """A numbered annotation badge."""
    return (f'<circle cx="{x}" cy="{y}" r="13" fill="#4f46e5"/>'
            f'<text x="{x}" y="{y+5}" font-size="15" font-weight="800" fill="#fff" text-anchor="middle">{n}</text>')

def _tile(x, y, icon, label, sub, accent="#4f46e5"):
    return (f'<rect x="{x}" y="{y}" width="240" height="96" rx="14" fill="#fff" stroke="#e4e7ec"/>'
            f'<rect x="{x}" y="{y}" width="6" height="96" rx="3" fill="{accent}"/>'
            f'<text x="{x+24}" y="{y+40}" font-size="26">{icon}</text>'
            f'<text x="{x+64}" y="{y+38}" font-size="16" font-weight="800" fill="#1a2130">{label}</text>'
            f'<text x="{x+64}" y="{y+62}" font-size="12" fill="#6b7280">{sub}</text>')

# ── Mockups ────────────────────────────────────────────────────────
_DASHBOARD = _frame("Operations", (
    '<text x="40" y="92" font-size="24" font-weight="800" fill="#1a2130">Operations hub</text>'
    '<text x="40" y="116" font-size="13" fill="#6b7280">Everything for running a live show — pick, pack, ship, and review.</text>'
    + _tile(40, 150, "🎬", "Shows", "Import &amp; track each live", "#6366f1")
    + _tile(310, 150, "⬇️", "Import orders", "TikTok / Whatnot CSV", "#8b5cf6")
    + _tile(580, 150, "📋", "Pick", "iPad picking list", "#ec4899")
    + _tile(40, 262, "📦", "Pack &amp; record", "Scan + film each box", "#0ea5e9")
    + _tile(310, 262, "🎁", "Giveaways", "Pack &amp; ship prizes", "#f59e0b")
    + _tile(580, 262, "📊", "Analytics", "Sales, packers, geography", "#10b981")
    + _num(258, 150, 1) + _num(528, 150, 2) + _num(258, 262, 3)
    + '<rect x="40" y="392" width="780" height="92" rx="14" fill="#eef2ff" stroke="#c7d2fe"/>'
    '<text x="60" y="428" font-size="14" font-weight="800" fill="#4338ca">💡 Tip</text>'
    '<text x="60" y="454" font-size="13" fill="#4338ca">Start at (1) Shows to import a live, then (2) Pick the orders, then (3) Pack &amp; record each box.</text>'
), h=520)

_IMPORT = _frame("Import", (
    '<rect x="150" y="80" width="560" height="380" rx="16" fill="#fff" stroke="#e4e7ec"/>'
    '<text x="184" y="126" font-size="20" font-weight="800" fill="#1a2130">Import TikTok Orders CSV</text>'
    '<text x="184" y="150" font-size="12.5" fill="#6b7280">Export "To Ship" orders from TikTok Seller Center → Orders → Export.</text>'
    '<text x="184" y="196" font-size="12" font-weight="700" fill="#6b7280">SHOW NAME *</text>'
    '<rect x="184" y="206" width="492" height="44" rx="10" fill="#fff" stroke="#c7d2fe" stroke-width="2"/>'
    '<text x="202" y="233" font-size="15" fill="#1a2130">TikTok Live — Fri</text>'
    '<text x="184" y="286" font-size="12" font-weight="700" fill="#6b7280">CSV FILE *</text>'
    '<rect x="184" y="296" width="492" height="52" rx="10" fill="#f9fafb" stroke="#cbd5e1" stroke-dasharray="5 4"/>'
    '<rect x="196" y="308" width="120" height="28" rx="8" fill="#d9748f"/>'
    '<text x="256" y="327" font-size="12.5" font-weight="700" fill="#fff" text-anchor="middle">Choose File</text>'
    '<text x="330" y="327" font-size="12.5" fill="#6b7280">To Ship orders.csv</text>'
    '<rect x="516" y="392" width="160" height="46" rx="10" fill="#4f46e5"/>'
    '<text x="596" y="421" font-size="15" font-weight="800" fill="#fff" text-anchor="middle">Import</text>'
    '<rect x="184" y="392" width="110" height="46" rx="10" fill="#f1f5f9"/>'
    '<text x="239" y="421" font-size="15" font-weight="700" fill="#475569" text-anchor="middle">Cancel</text>'
    + _num(676, 228, 1) + _num(676, 322, 2) + _num(676, 415, 3)
), h=520)

def _pickrow(y, sku, name, qty, done=False):
    box = ('<rect x="40" y="'+str(y)+'" width="26" height="26" rx="7" fill="#10b981"/>'
           '<text x="53" y="'+str(y+19)+'" font-size="16" fill="#fff" text-anchor="middle">✓</text>') if done else (
           '<rect x="40" y="'+str(y)+'" width="26" height="26" rx="7" fill="#fff" stroke="#cbd5e1" stroke-width="2"/>')
    op = '0.5' if done else '1'
    return (f'<g opacity="{op}">{box}'
            f'<rect x="82" y="{y-6}" width="40" height="40" rx="9" fill="#eef2ff"/>'
            f'<text x="102" y="{y+20}" font-size="18" text-anchor="middle">💄</text>'
            f'<text x="138" y="{y+9}" font-size="13" font-family="monospace" font-weight="700" fill="#4f46e5">{sku}</text>'
            f'<text x="138" y="{y+28}" font-size="14" font-weight="700" fill="#1a2130">{name}</text>'
            f'<rect x="700" y="{y-4}" width="120" height="36" rx="9" fill="#f1f5f9"/>'
            f'<text x="760" y="{y+20}" font-size="15" font-weight="800" fill="#1a2130" text-anchor="middle">×{qty}</text></g>')

_PICK = _frame("Pick", (
    '<text x="40" y="86" font-size="22" font-weight="800" fill="#1a2130">Order #1042 · Buyer A</text>'
    '<text x="40" y="108" font-size="13" fill="#6b7280">Scan or tap each item as you pick it into the tote.</text>'
    '<rect x="40" y="126" width="780" height="8" rx="4" fill="#eef2ff"/>'
    '<rect x="40" y="126" width="470" height="8" rx="4" fill="#4f46e5"/>'
    '<text x="820" y="120" font-size="12" font-weight="700" fill="#4f46e5" text-anchor="end">3 / 5 picked</text>'
    + _pickrow(168, "1042", "Rose Lip Oil", 1, True)
    + _pickrow(224, "2071", "Glow Serum", 2, True)
    + _pickrow(280, "3310", "Velvet Blush", 1, True)
    + _pickrow(336, "4088", "Silk Primer", 1, False)
    + _pickrow(392, "5127", "Setting Spray", 1, False)
    + _num(600, 130, 1)
    + '<rect x="40" y="446" width="780" height="46" rx="10" fill="#4f46e5"/>'
    '<text x="430" y="475" font-size="15" font-weight="800" fill="#fff" text-anchor="middle">Finish pick → send to packing</text>'
), h=520)

_PACK = _frame("Pack &amp; record", (
    '<rect x="40" y="76" width="470" height="300" rx="14" fill="#0b1220"/>'
    '<circle cx="275" cy="200" r="34" fill="#1e293b"/><circle cx="275" cy="200" r="12" fill="#ef4444"/>'
    '<text x="275" y="270" font-size="13" fill="#94a3b8" text-anchor="middle">● Recording — 00:14</text>'
    '<rect x="60" y="92" width="150" height="30" rx="8" fill="rgba(255,255,255,.12)"/>'
    '<text x="135" y="112" font-size="12.5" font-weight="700" fill="#fff" text-anchor="middle">Station 1 · You</text>'
    '<text x="534" y="104" font-size="12" font-weight="700" fill="#6b7280">SCAN TRACKING</text>'
    '<rect x="534" y="116" width="286" height="44" rx="10" fill="#fff" stroke="#c7d2fe" stroke-width="2"/>'
    '<text x="552" y="143" font-size="14" font-family="monospace" fill="#1a2130">9400 1000 0000 ****</text>'
    '<rect x="534" y="180" width="286" height="70" rx="12" fill="#ecfdf5" stroke="#a7f3d0"/>'
    '<text x="552" y="210" font-size="14" font-weight="800" fill="#059669">Order #1042 · Buyer A</text>'
    '<text x="552" y="232" font-size="12.5" fill="#065f46">5 items · expected 0.8 lb</text>'
    '<rect x="534" y="266" width="286" height="46" rx="10" fill="#4f46e5"/>'
    '<text x="677" y="295" font-size="15" font-weight="800" fill="#fff" text-anchor="middle">Weigh &amp; finish</text>'
    + _num(516, 138, 1) + _num(516, 289, 2)
    + '<rect x="40" y="398" width="780" height="86" rx="14" fill="#eef2ff" stroke="#c7d2fe"/>'
    '<text x="60" y="432" font-size="14" font-weight="800" fill="#4338ca">💡 How it works</text>'
    '<text x="60" y="458" font-size="13" fill="#4338ca">Scan the shipping label (1). The order pops up and recording starts. Weigh the box, then finish (2).</text>'
), h=520)

def _bar(x, h, label, val, color="#4f46e5"):
    top = 300 - h
    return (f'<rect x="{x}" y="{top}" width="52" height="{h}" rx="6" fill="{color}"/>'
            f'<text x="{x+26}" y="{top-8}" font-size="12" font-weight="800" fill="#1a2130" text-anchor="middle">{val}</text>'
            f'<text x="{x+26}" y="322" font-size="12" fill="#6b7280" text-anchor="middle">{label}</text>')

_ANALYTICS = _frame("Analytics", (
    '<text x="40" y="88" font-size="22" font-weight="800" fill="#1a2130">Packer performance — this week</text>'
    '<rect x="40" y="110" width="240" height="70" rx="12" fill="#fff" stroke="#e4e7ec"/>'
    '<text x="60" y="140" font-size="12" fill="#6b7280">Boxes packed</text><text x="60" y="166" font-size="22" font-weight="800" fill="#4f46e5">1,284</text>'
    '<rect x="300" y="110" width="240" height="70" rx="12" fill="#fff" stroke="#e4e7ec"/>'
    '<text x="320" y="140" font-size="12" fill="#6b7280">Avg / box</text><text x="320" y="166" font-size="22" font-weight="800" fill="#10b981">2m 12s</text>'
    '<rect x="560" y="110" width="260" height="70" rx="12" fill="#fff" stroke="#e4e7ec"/>'
    '<text x="580" y="140" font-size="12" fill="#6b7280">Top state</text><text x="580" y="166" font-size="22" font-weight="800" fill="#8b5cf6">California</text>'
    '<line x1="40" y1="300" x2="820" y2="300" stroke="#e4e7ec"/>'
    + _bar(120, 150, "Packer A", 402)
    + _bar(260, 120, "Packer B", 331, "#8b5cf6")
    + _bar(400, 95, "Packer C", 268, "#ec4899")
    + _bar(540, 70, "Packer D", 190, "#0ea5e9")
    + _bar(680, 45, "Packer E", 93, "#f59e0b")
    + '<text x="40" y="360" font-size="12.5" fill="#6b7280">Every screen filters by show and date range — packers, pickers, repeat buyers, and geography.</text>'
), h=420)

_SUPPORT = _frame("Support", (
    '<text x="40" y="88" font-size="22" font-weight="800" fill="#1a2130">Open a request</text>'
    '<text x="40" y="110" font-size="13" fill="#6b7280">The more detail you give, the faster we can help.</text>'
    '<text x="40" y="150" font-size="12" font-weight="700" fill="#6b7280">WHAT AREA?</text>'
    '<rect x="40" y="160" width="370" height="42" rx="10" fill="#fff" stroke="#c7d2fe" stroke-width="2"/>'
    '<text x="58" y="186" font-size="14" fill="#1a2130">Importing orders (TikTok / Whatnot CSV)</text>'
    '<text x="440" y="150" font-size="12" font-weight="700" fill="#6b7280">PRIORITY</text>'
    '<rect x="440" y="160" width="380" height="42" rx="10" fill="#fff" stroke="#e4e7ec"/>'
    '<text x="458" y="186" font-size="14" fill="#1a2130">Urgent — I\'m blocked</text>'
    '<text x="40" y="234" font-size="12" font-weight="700" fill="#6b7280">WHAT HAPPENED? *</text>'
    '<rect x="40" y="244" width="780" height="80" rx="10" fill="#fff" stroke="#e4e7ec"/>'
    '<text x="58" y="272" font-size="13.5" fill="#334155">The CSV import spinner never finishes…</text>'
    '<rect x="40" y="344" width="220" height="46" rx="10" fill="#4f46e5"/>'
    '<text x="150" y="373" font-size="15" font-weight="800" fill="#fff" text-anchor="middle">Send request</text>'
    + _num(430, 181, 1) + _num(676, 367, 2)
    + '<rect x="40" y="410" width="780" height="72" rx="12" fill="#fff7ed" stroke="#fed7aa"/>'
    '<text x="60" y="440" font-size="13.5" font-weight="800" fill="#9a3412">We capture your browser &amp; role automatically</text>'
    '<text x="60" y="463" font-size="12.5" fill="#9a3412">so you don\'t have to explain your setup — just tell us what went wrong.</text>'
), h=520)

GUIDE_ASSETS = {
    "dashboard": _DASHBOARD,
    "import": _IMPORT,
    "pick": _PICK,
    "pack": _PACK,
    "analytics": _ANALYTICS,
    "support": _SUPPORT,
}

# ── Seed guides (Markdown; images point at /guide-asset/<name>) ─────
GUIDE_SEEDS = [
{"category":"getting_started","audience":"all","status":"published","sort_order":1,
 "title":"Welcome — a 2-minute tour","video_url":"","body":
"""Welcome! This app runs your whole live-selling operation — from importing orders to packing, shipping, and reviewing results. Here's the map.

![Your Operations hub](/guide-asset/dashboard)

## The main flow
Every live show moves through the same three steps:

- **1. Shows** — import a live's orders so the system knows what sold.
- **2. Pick** — staff gather each order's items into a tote.
- **3. Pack & record** — scan the shipping label, film the box, weigh it, done.

Everything else (Giveaways, Analytics, Inventory) supports that flow.

## Who sees what
- **Admins & CS** see everything: operations, analytics, settings, and this help center.
- **Pickers & packers** get a simple, touch-friendly screen for their one job.

Use the **🛟 Support** tab any time something isn't working — we read every request.
"""},

{"category":"import","audience":"all","status":"published","sort_order":1,
 "title":"Importing orders from TikTok or Whatnot","video_url":"","body":
"""After a live ends, export the orders and import them here. The app auto-detects whether the file is from TikTok or Whatnot.

![The import window](/guide-asset/import)

## Steps
- **1. Show name** — give every upload from the same live the *exact same* name (orders + cancellations). Recent shows appear as you type, so reuse the name.
- **2. Choose file** — TikTok: Seller Center → Orders → Export "To Ship". Whatnot: your orders export.
- **3. Import** — the app reads tracking codes, items, and weights, and groups combined orders automatically.

## Good to know
- Re-importing the same show **updates** it — it won't create duplicates.
- Giveaway orders (stamp/no-scan tracking) are flagged automatically so they don't get stuck.
- A big file can take up to a minute — leave the window open until it finishes.
"""},

{"category":"picking","audience":"all","status":"published","sort_order":1,
 "title":"Picking an order on the iPad","video_url":"","body":
"""Picking is gathering each order's items into a tote before it goes to a packing station. It's built for touch.

![The picking screen](/guide-asset/pick)

## How to pick
- Open the order — every item shows its **photo, SKU, and quantity**.
- **1.** Tap or scan each item as you drop it in the tote. The progress bar fills up.
- When all items are checked, tap **Finish pick** to send it to packing.

## Tips
- The photo helps you grab the right shade fast — no guessing from the SKU.
- If an item is out of stock, flag it so CS can follow up instead of silently skipping it.
"""},

{"category":"packing","audience":"all","status":"published","sort_order":1,
 "title":"Packing & recording a box","video_url":"","body":
"""Every box is filmed as it's packed — that video is your proof of what shipped, tied to the tracking number.

![The packing station](/guide-asset/pack)

## The flow
- **1. Scan the shipping label.** The order pops up and recording starts automatically.
- Pack the items shown, then **2. weigh & finish**. The weight is checked against what's expected.
- The video saves against that tracking number — searchable later from Customer Search.

## If a weight looks off
A warning means the box weighs much more or less than expected — usually a missing or extra item. Re-check before you finish.

## Giveaways
Standalone giveaways are packed here too: scan their tracking like any order. Prizes riding inside an existing order are added during that order's pack.
"""},

{"category":"analytics","audience":"managers","status":"published","sort_order":1,
 "title":"Reading your analytics","video_url":"","body":
"""Every screen under Analytics filters by **show** and **date range**, so you can look at one live or the whole month.

![Packer performance report](/guide-asset/analytics)

## What you can see
- **Packers & pickers** — boxes done, average time per box, and who's fastest.
- **Hosts** — sales per host, with configurable commissions.
- **Geography** — which states your orders ship to.
- **Repeat customers** — who's buying again, sorted by orders or spend.

## Note on sales figures
Product revenue and buyer-paid shipping are shown **separately**, so a show's sales aren't inflated by pass-through shipping you collect and pay out.
"""},

{"category":"account","audience":"managers","status":"published","sort_order":1,
 "title":"Adding staff & badge logins","video_url":"","body":
"""Add your team under **Settings → Users**. Each person gets a role that decides what they can see.

## Roles
- **Admin** — full access, including settings and analytics.
- **CS** — customer service: imports, customer lookup, support.
- **Picker / Packer** — the simple floor screens only.

## Badges
Workers get a **badge token** automatically — print it as a barcode from Users → Badges. On a warehouse station they just **scan the badge to log in**, no password or keyboard needed.

Lost a badge? Regenerate it (the old one stops working instantly).
"""},

{"category":"troubleshooting","audience":"all","status":"published","sort_order":1,
 "title":"Something's not working — how to get help fast","video_url":"","body":
"""Open the **🛟 Support** tab and file a request. Give us the details up front and we'll resolve it faster.

![Opening a support request](/guide-asset/support)

## What helps most
- **1. Pick the area** (import, packing, analytics…) and a priority. "Urgent — I'm blocked" jumps the queue.
- Describe **what happened** and **what you were trying to do**, step by step.
- Note **when it started** and whether it happens every time.
- **2. Send** — we automatically capture your browser and role, so you don't have to.

## Quick self-checks first
- If a button seems stuck right after an update, **refresh the page** once.
- Make sure you're on the right show name before importing.
"""},
]
