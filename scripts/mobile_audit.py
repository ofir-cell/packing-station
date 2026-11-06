#!/usr/bin/env python3
"""Mobile audit harness — screenshots and measures every LiveOpsHub screen.

Boots the Flask app in-process against a throw-away DATA_DIR seeded with realistic
demo data (shows, orders, items, products), signs in as each role through the real
login (password + 2FA for admin), opens every HTML page that role can reach, and for
each device size records a full-page screenshot plus objective checks:

  overflow_px     content wider than the viewport (horizontal scroll)  → must be 0
  small_targets   visible links/buttons/inputs smaller than 44×44 CSS px
  small_inputs    inputs/selects/textareas with font-size < 16px (iOS zooms on focus)
  tiny_text       visible text nodes with font-size < 12px
  js_errors       uncaught page errors / console errors
  status          HTTP status of the page

Output: audit/<run>/report.json, audit/<run>/report.md, audit/<run>/<device>/<role>/<page>.png
(audit/ is git-ignored).

Usage:
  python3 scripts/mobile_audit.py                         # every page, every role, all devices
  python3 scripts/mobile_audit.py --only /pick /admin/shows
  python3 scripts/mobile_audit.py --devices se,pro --roles worker
  python3 scripts/mobile_audit.py --app-ua                # pretend to be the iOS app (UA + LOHubNative)
"""
import argparse, json, os, random, re, sys, tempfile, threading, time, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DEVICES = {
    "se":      {"viewport": {"width": 375, "height": 667},  "dpr": 2, "mobile": True},
    "pro":     {"viewport": {"width": 393, "height": 852},  "dpr": 3, "mobile": True},
    "max":     {"viewport": {"width": 430, "height": 932},  "dpr": 3, "mobile": True},
    "ipad":    {"viewport": {"width": 820, "height": 1180}, "dpr": 2, "mobile": True},
    "desktop": {"viewport": {"width": 1440, "height": 900}, "dpr": 1, "mobile": False},
}
IPHONE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
             "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1")
APP_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) LiveOpsHubiOS/1.0.0 Mobile")

ROLES = {   # username -> (role, display name)
    "worker":  ("worker",  "Ana Picker"),
    "manager": ("manager", "Maya Manager"),
    "admin":   ("admin",   "Ofir Admin"),
}
PASSWORD = "audit-pass-1234"

# Pages that need an id or are file/redirect endpoints — not screens.
SKIP = {"/logout", "/documents/dl/<doc_id>", "/product-image/<sku>", "/admin/hires/<int:hire_id>/file",
        "/label/file/<fn>", "/label/giveaway/<int:gid>", "/label/inbound/<int:iid>",
        "/label/inbound/batch/<batch_id>", "/label/inbound/multi", "/privacy.html", "/terms.html",
        "/admin/organizations", "/admin/support", "/admin/guides", "/hire/<token>"}
PARAM_FILL = {"/admin/employee/<username>": "/admin/employee/worker",
              "/giveaway/<int:gid>": None, "/admin/hires/<int:hire_id>": None}

MEASURE_JS = r"""
() => {
  const vw = document.documentElement.clientWidth;
  const sw = Math.max(document.documentElement.scrollWidth, document.body ? document.body.scrollWidth : 0);
  const vis = el => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none' && cs.opacity !== '0'; };
  const label = el => (el.innerText || el.value || el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.name || el.id || el.tagName).trim().replace(/\s+/g,' ').slice(0,40);
  const small = [];
  document.querySelectorAll('a[href],button,input:not([type=hidden]),select,textarea,[role=button],[onclick],label[for]').forEach(el => {
    if (!vis(el)) return;
    const r = el.getBoundingClientRect();
    if (r.width < 44 || r.height < 44) small.push({tag: el.tagName.toLowerCase(), text: label(el), w: Math.round(r.width), h: Math.round(r.height)});
  });
  const smallInputs = [];
  document.querySelectorAll('input:not([type=hidden]):not([type=checkbox]):not([type=radio]),select,textarea').forEach(el => {
    if (!vis(el)) return;
    const fs = parseFloat(getComputedStyle(el).fontSize);
    if (fs < 16) smallInputs.push({text: label(el), font: fs});
  });
  let tiny = 0; const tinySamples = [];
  const walker = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const n = walker.currentNode; const t = n.textContent.trim(); if (!t) continue;
    const el = n.parentElement; if (!el || !vis(el)) continue;
    const fs = parseFloat(getComputedStyle(el).fontSize);
    if (fs < 12) { tiny++; if (tinySamples.length < 5) tinySamples.push({text: t.slice(0,30), font: fs}); }
  }
  const wide = [];
  if (sw > vw + 1) document.querySelectorAll('body *').forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.right > vw + 1 && r.width > 0 && wide.length < 6 && getComputedStyle(el).position !== 'fixed')
      wide.push({tag: el.tagName.toLowerCase(), cls: (el.className && el.className.baseVal === undefined ? String(el.className) : '').slice(0,40), right: Math.round(r.right)});
  });
  return {title: document.title, viewport: vw, overflow_px: Math.max(0, sw - vw), wide_elements: wide,
          small_targets: small.length, small_target_samples: small.slice(0, 8),
          small_inputs: smallInputs.length, small_input_samples: smallInputs.slice(0, 5),
          tiny_text: tiny, tiny_text_samples: tinySamples};
}
"""


# ── demo data ──────────────────────────────────────────────────────────────────
def seed(A):
    """Users for each role (+ admin 2FA) and a few days of realistic orders."""
    secret = A._new_totp_secret() if hasattr(A, "_new_totp_secret") else None
    if not secret:
        import base64, secrets as _s
        secret = base64.b32encode(_s.token_bytes(20)).decode().rstrip("=")
    with A.update_json(A.USERS_FILE) as users:
        for uname, (role, name) in ROLES.items():
            users[uname] = {"password": A._h(PASSWORD), "role": role, "name": name, "org": A.DEFAULT_ORG}
        users["admin"].update(twofa_enabled=True, twofa_secret=secret)
    import sqlite3
    random.seed(7)
    c = A.sdb(A.DEFAULT_ORG)
    scols = {r[1] for r in c.execute("PRAGMA table_info(shipments)")}
    icols = {r[1] for r in c.execute("PRAGMA table_info(shipment_items)")}
    buyers = ["Jasmine Rivera", "Kayla Moore", "Destiny Price", "Brianna Taylor", "Alexis White",
              "María González", "Tiana Lewis", "Sofia Castillo", "Imani Brooks", "Nicole Chen"]
    prods = [("RB-BLUSH-01", "Rare Beauty Soft Pinch Liquid Blush — Joy"), ("KAY-VAN28", "Kayali Vanilla 28 Eau de Parfum 50ml"),
             ("SDJ-62MIST", "Sol de Janeiro Cheirosa 62 Body Mist 240ml"), ("YSL-LIBRE50", "YSL Libre Eau de Parfum 50ml"),
             ("DIOR-LIPGLOW", "Dior Addict Lip Glow Oil 001 Pink"), ("FENTY-GB", "Fenty Beauty Gloss Bomb Universal Lip Luminizer"),
             ("OLAPLEX-3", "Olaplex No.3 Hair Perfector 100ml"), ("CHAR-PILLOW", "Charlotte Tilbury Pillow Talk Lipstick")]
    now = datetime.datetime.now()
    shows = ["Peach LIVE · Nov 5 Evening", "Peach LIVE · Nov 5 Morning", "Hera LIVE · Nov 4", "Sydney B LIVE · Nov 3"]
    n = 0
    for s, show in enumerate(shows):
        for i in range(38 - s * 7):
            n += 1
            sid = f"57{n:014d}"
            st = random.choices(["pending", "picked", "packed", "shipped", "cancelled", "issue"], [40, 15, 20, 20, 3, 2])[0]
            ts = (now - datetime.timedelta(hours=s * 9, minutes=i)).strftime("%Y-%m-%d %H:%M:%S")
            row = {"shipment_id": sid, "tracking_code": f"9400111{random.randint(10**14, 10**15 - 1)}",
                   "buyer_name": random.choice(buyers), "buyer_username": f"buyer{n}", "status": st,
                   "import_label": show, "platform": "tiktok", "imported_at": ts, "show_date": ts[:10],
                   "address_full": f"{random.randint(100,9999)} Palm Ave, Miami, FL 33101", "postal_code": "33101",
                   "total_items": 1}
            if st in ("picked", "packed", "shipped"): row.update(picked_by="Ana Picker", picked_at=ts)
            if st in ("packed", "shipped"): row.update(packed_by="Tomi Packer", packed_at=ts)
            row = {k: v for k, v in row.items() if k in scols}
            c.execute(f"INSERT OR IGNORE INTO shipments({','.join(row)}) VALUES({','.join('?' * len(row))})", list(row.values()))
            for _ in range(random.choice([1, 1, 1, 2, 3])):
                sku, name = random.choice(prods)
                it = {k: v for k, v in {"shipment_id": sid, "sku": sku, "product_name": name, "quantity": 1}.items() if k in icols}
                c.execute(f"INSERT INTO shipment_items({','.join(it)}) VALUES({','.join('?' * len(it))})", list(it.values()))
    try:
        pcols = {r[1] for r in c.execute("PRAGMA table_info(products)")}
        for sku, name in prods:
            p = {k: v for k, v in {"sku": sku, "name": name, "stock": random.randint(0, 40), "price": round(random.uniform(18, 95), 2),
                                   "cost": round(random.uniform(6, 30), 2), "barcode": str(random.randint(10**11, 10**12 - 1))}.items() if k in pcols}
            c.execute(f"INSERT OR IGNORE INTO products({','.join(p)}) VALUES({','.join('?' * len(p))})", list(p.values()))
    except Exception as e:
        print("  (products not seeded:", e, ")")
    c.commit(); c.close()
    return secret


def page_routes(A):
    out = []
    for rule in A.app.url_map.iter_rules():
        p = rule.rule
        if "GET" not in rule.methods or p.startswith(("/api", "/media", "/static", "/guide-asset")):
            continue
        if re.search(r"\.(csv|pdf|json|png|js|svg|ico|xml|txt|webmanifest)$", p) or p in SKIP:
            continue
        if "<" in p:
            p = PARAM_FILL.get(p)
            if not p: continue
        out.append(p)
    return sorted(set(out))


def slug(path):
    return (path.strip("/").replace("/", "__") or "root")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="limit to these paths")
    ap.add_argument("--devices", default="se,pro,max,ipad,desktop")
    ap.add_argument("--roles", default="worker,manager,admin")
    ap.add_argument("--out", default=str(ROOT / "audit"))
    ap.add_argument("--app-ua", action="store_true", help="identify as the iOS app (UA + LOHubNative stub)")
    ap.add_argument("--port", type=int, default=5077)
    a = ap.parse_args()

    data = tempfile.mkdtemp(prefix="lohub-audit-")
    os.environ.update(DATA_DIR=data, SECRET_KEY="a" * 40, TIKTOK_APP_KEY="k", TIKTOK_APP_SECRET="s")
    for k in ("R2_BUCKET", "R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
        os.environ.pop(k, None)
    import app as A
    A.app.config["SESSION_COOKIE_SECURE"] = False
    secret = seed(A)
    routes = a.only or page_routes(A)

    from werkzeug.serving import make_server
    srv = make_server("127.0.0.1", a.port, A.app, threaded=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{a.port}"

    run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    outdir = Path(a.out) / run
    outdir.mkdir(parents=True, exist_ok=True)
    results = []

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for dev in a.devices.split(","):
            spec = DEVICES[dev]
            for role in a.roles.split(","):
                ctx = browser.new_context(viewport=spec["viewport"], device_scale_factor=1,
                                          is_mobile=spec["mobile"], has_touch=spec["mobile"],
                                          user_agent=(APP_UA if a.app_ua else IPHONE_UA) if spec["mobile"] else None)
                if a.app_ua:
                    ctx.add_init_script("window.LOHubNative={isApp:true,version:'audit',scan:()=>Promise.resolve(null),"
                                        "pack:()=>{},haptic:()=>{}};document.documentElement.classList.add('lohub-ios');")
                page = ctx.new_page()
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)[:200]))
                # ERR_TUNNEL/NAME_NOT_RESOLVED = external fonts/CDNs unreachable from a sandbox, not app bugs
                page.on("console", lambda m: errors.append(m.text[:200]) if m.type == "error"
                        and "ERR_TUNNEL" not in m.text and "ERR_NAME_NOT_RESOLVED" not in m.text else None)
                # real sign-in
                page.goto(base + "/login")
                tok = next((c["value"] for c in ctx.cookies() if c["name"] == "csrf_token"), "")
                r = page.evaluate("""async ([u,p,t]) => { const r = await fetch('/api/login', {method:'POST',
                    headers:{'Content-Type':'application/json','X-CSRF-Token':t}, body: JSON.stringify({username:u,password:p})});
                    return await r.json(); }""", [role, PASSWORD, tok])
                if r.get("twofa"):
                    code = A._totp_at(secret, time.time())
                    page.evaluate("""async ([c,t]) => (await fetch('/api/login/2fa', {method:'POST',
                        headers:{'Content-Type':'application/json','X-CSRF-Token':t}, body: JSON.stringify({code:c})})).json()""", [code, tok])
                for path in routes:
                    errors.clear()
                    try:
                        resp = page.goto(base + path, wait_until="networkidle", timeout=20000)
                    except Exception as e:
                        results.append({"device": dev, "role": role, "path": path, "error": str(e)[:200]}); continue
                    page.wait_for_timeout(400)
                    final = page.url.replace(base, "")
                    m = page.evaluate(MEASURE_JS)
                    shot = outdir / dev / role / f"{slug(path)}.png"
                    shot.parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(shot), full_page=True)
                    results.append({"device": dev, "role": role, "path": path, "final_url": final,
                                    "status": resp.status if resp else None,
                                    "redirected": final.split("?")[0] != path, "js_errors": list(errors)[:5],
                                    "screenshot": str(shot.relative_to(outdir)), **m})
                ctx.close()
                print(f"  {dev:8} {role:8} {len(routes)} pages", flush=True)
        browser.close()
    srv.shutdown()

    (outdir / "report.json").write_text(json.dumps(results, indent=1))
    write_markdown(outdir, results)
    print("report:", outdir / "report.md")


def write_markdown(outdir, results):
    """One row per (role, page) on the iPhone 16 Pro size, worst first."""
    rows = [r for r in results if r.get("device") == "pro" and not r.get("redirected") and not r.get("error")
            and r.get("status") == 200]
    def score(r): return (r["overflow_px"] > 0) * 100 + r["small_targets"] + r["small_inputs"] * 3 + min(r["tiny_text"], 50) / 5
    rows.sort(key=score, reverse=True)
    lines = ["# Mobile audit — iPhone 16 Pro (393×852)", "",
             f"{len(rows)} screens reachable. Hard rules: overflow 0, tap targets ≥44px, inputs ≥16px, text ≥12px.", "",
             "| Role | Page | Overflow px | <44px targets | <16px inputs | <12px text | JS errors |",
             "|---|---|---:|---:|---:|---:|---:|"]
    for r in rows:
        lines.append(f"| {r['role']} | `{r['path']}` | {r['overflow_px']} | {r['small_targets']} | {r['small_inputs']} | "
                     f"{r['tiny_text']} | {len(r['js_errors'])} |")
    (outdir / "report.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
