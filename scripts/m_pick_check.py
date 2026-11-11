#!/usr/bin/env python3
"""End-to-end check of the mobile Pick screen (/m/pick) in a real browser.

Boots the app against a throw-away DATA_DIR with the audit harness's demo data, signs in
as a warehouse worker, then drives the screen the way the floor does and asserts on what
the SERVER recorded:

  1. queue renders; choose a show
  2. a Bluetooth/USB scanner "types" a tracking number + Enter with nothing focused
     -> the order opens (keyboard-wedge capture)
  3. tick every item, Done -> shipment is 'picked' in the database
  4. scan a cancelled order -> red stop screen, nothing changes
  5. type a code by hand, report a problem -> shipment is 'issue'
  6. layout gates on every state: no horizontal overflow, tap targets >= 44pt,
     inputs >= 16px, text >= 12px

Screenshots go to audit/m-pick/ (git-ignored).  Usage: python3 scripts/m_pick_check.py
"""
import os, sys, tempfile, threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import mobile_audit as H   # noqa: E402  (seed data, device sizes, MEASURE_JS)

OUT = ROOT / "audit" / "m-pick"
PORT = 5078
CHROME = next((p for p in ("/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser") if os.path.exists(p)), None)
fails = []


def check(ok, msg):
    print(("  ok   " if ok else "  FAIL ") + msg)
    if not ok:
        fails.append(msg)


def main():
    data = tempfile.mkdtemp(prefix="lohub-mpick-")
    os.environ.update(DATA_DIR=data, SECRET_KEY="a" * 40, TIKTOK_APP_KEY="k", TIKTOK_APP_SECRET="s")
    for k in ("R2_BUCKET", "R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
        os.environ.pop(k, None)
    import app as A
    A.app.config["SESSION_COOKIE_SECURE"] = False
    H.seed(A)

    # Demo state: tables already cleaned out (so shows are pickable), someone else on one show.
    c = A.sdb(A.DEFAULT_ORG)
    A._cleanout_ensure(c)
    labels = [r[0] for r in c.execute("SELECT DISTINCT import_label FROM shipments").fetchall()]
    for lbl in labels:
        A._show_mark_cleanout(c, lbl, "seed")
    c.execute("""UPDATE shipments SET pick_started_by='Maria Lopez', pick_started_at=CURRENT_TIMESTAMP
                 WHERE shipment_id IN (SELECT shipment_id FROM shipments WHERE status='pending' AND import_label=? LIMIT 2)""",
              ("Peach LIVE · Nov 5 Morning",))
    show = "Peach LIVE · Nov 5 Evening"
    pend = c.execute("""SELECT shipment_id, tracking_code FROM shipments WHERE status='pending' AND import_label=?
                        ORDER BY shipment_id LIMIT 3""", (show,)).fetchall()
    canc = c.execute("SELECT shipment_id, tracking_code FROM shipments WHERE status='cancelled' LIMIT 1").fetchone()
    c.commit(); c.close()
    assert len(pend) == 3 and canc, "seed data changed"

    def status(sid):
        k = A.sdb(A.DEFAULT_ORG)
        try:
            return k.execute("SELECT status, picked_by, flag_reason FROM shipments WHERE shipment_id=?", (sid,)).fetchone()
        finally:
            k.close()

    from werkzeug.serving import make_server
    srv = make_server("127.0.0.1", PORT, A.app, threaded=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{PORT}"
    OUT.mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=CHROME) if CHROME else pw.chromium.launch()

        def session(dev, app_ua=False, dark=False):
            spec = H.DEVICES[dev]
            ctx = browser.new_context(viewport=spec["viewport"], device_scale_factor=2, is_mobile=True, has_touch=True,
                                      user_agent=H.APP_UA if app_ua else H.IPHONE_UA,
                                      color_scheme="dark" if dark else "light")
            if app_ua:
                ctx.add_init_script("window.LOHubNative={isApp:true,version:'check',scan:()=>Promise.resolve(null),"
                                    "pack:()=>{},haptic:()=>{}};")
            page = ctx.new_page()
            errs = []
            page.on("pageerror", lambda e: errs.append(str(e)[:300]))
            page.on("console", lambda m: errs.append(m.text[:300]) if m.type == "error"
                    and "ERR_TUNNEL" not in m.text and "ERR_NAME_NOT_RESOLVED" not in m.text
                    and "ERR_CONNECTION" not in m.text and "ERR_PROXY" not in m.text else None)
            page.goto(base + "/login")
            tok = next((k["value"] for k in ctx.cookies() if k["name"] == "csrf_token"), "")
            r = page.evaluate("""async ([u,p,t]) => (await fetch('/api/login', {method:'POST',
                headers:{'Content-Type':'application/json','X-CSRF-Token':t}, body: JSON.stringify({username:u,password:p})})).json()""",
                              ["worker", H.PASSWORD, tok])
            assert r.get("ok"), r
            errs.clear()                 # only errors from the /m/ screens count
            return ctx, page, errs

        def gates(page, label):
            m = page.evaluate(H.MEASURE_JS)
            check(m["overflow_px"] == 0, f"{label}: no horizontal overflow (got {m['overflow_px']}px)")
            check(m["small_targets"] == 0, f"{label}: tap targets >= 44pt (small: {m.get('small_target_samples')})")
            check(m["small_inputs"] == 0, f"{label}: inputs >= 16px")
            # 10pt tab-bar labels are the size the HIG prescribes (DESIGN_SYSTEM.md 1.3) — exempt.
            tabs = {"Today", "Pick", "Pack", "Track", "More"}
            tiny = [s for s in (m.get("tiny_text_samples") or []) if s.get("text") not in tabs]
            exempt = len(m.get("tiny_text_samples") or []) - len(tiny)
            check(m["tiny_text"] - exempt == 0, f"{label}: text >= 12px (tiny: {tiny})")

        def scanner(page, code):
            """What a paired Bluetooth scanner does: types fast, then Enter. No field is focused."""
            page.keyboard.type(code, delay=8)
            page.keyboard.press("Enter")

        # ── iPhone, in the app (native tab bar; web tab bar hidden) ──────────────
        ctx, page, errs = session("pro", app_ua=True)
        page.goto(base + "/m/pick", wait_until="networkidle")
        page.wait_for_selector("#showList button.pk-row")
        check(page.locator("#showList button.pk-row").count() == 4, "queue lists the 4 shows with orders to pick")
        check("Maria" in page.inner_text("#showList"), "queue shows who is picking another show")
        page.screenshot(path=str(OUT / "1-queue-no-show.png"), full_page=True)

        scanner(page, pend[0]["tracking_code"])
        page.wait_for_timeout(500)
        check(page.is_hidden("#order"), "scan before choosing a show is refused ('Choose a show first')")

        page.locator("#showList button.pk-row", has_text=show).click()
        page.wait_for_selector("#hero")
        check(show in page.inner_text("#hero"), "tapping a show makes it the current show (hero card)")
        page.wait_for_timeout(2800)    # toast gone
        gates(page, "queue")
        page.screenshot(path=str(OUT / "2-queue.png"), full_page=True)

        scanner(page, pend[0]["tracking_code"])
        page.wait_for_selector("#order:not([hidden])")
        check(True, "Bluetooth-scanner keystrokes + Enter open the order (no field focused)")
        check(status(pend[0]["shipment_id"])["status"] == "pending", "opening an order does not change its status")
        page.wait_for_timeout(300)
        gates(page, "order")
        page.screenshot(path=str(OUT / "3-order.png"), full_page=True)

        rows = page.locator("#oItems .pk-item[data-id]")
        n = rows.count()
        for i in range(n):
            page.locator("#oItems .pk-item[data-id]").nth(i).click()
            page.wait_for_function("i => document.querySelectorAll('#oItems .pk-item.is-picked').length > i", arg=i)
        check(page.inner_text("#doneBtn").startswith("Done"), f"all {n} item(s) ticked -> primary action is 'Done — scan next'")
        page.screenshot(path=str(OUT / "4-order-all-picked.png"), full_page=True)
        page.click("#doneBtn")
        page.wait_for_selector("#queue:not([hidden])")
        st = status(pend[0]["shipment_id"])
        check(st["status"] == "picked" and st["picked_by"] == "Ana Picker", f"Done -> server has it picked by the worker (status={st['status']}, by={st['picked_by']})")
        check(page.inner_text("#stSession") == "1", "session counter went to 1")

        scanner(page, pend[0]["tracking_code"])
        page.wait_for_timeout(700)
        check(page.is_hidden("#order"), "re-scanning a picked order does not reopen it ('Already picked by')")

        scanner(page, canc["tracking_code"])
        page.wait_for_selector("#stop:not([hidden])")
        check(True, "cancelled order -> full-screen 'Don't pick this order'")
        page.screenshot(path=str(OUT / "5-cancelled.png"))
        check(status(canc["shipment_id"])["status"] == "cancelled", "cancelled order untouched")
        page.evaluate("document.getElementById('stop').hidden = true")

        # a partly ticked order asks before it is marked picked
        scanner(page, pend[1]["tracking_code"])
        page.wait_for_selector("#order:not([hidden])")
        page.click("#doneBtn")
        page.wait_for_selector(".m-sheet.is-open")
        check("Not everything is ticked" in page.inner_text(".m-sheet.is-open"), "Done with unticked items asks first (same bypass as desktop)")
        page.wait_for_timeout(400)
        page.screenshot(path=str(OUT / "6-confirm.png"))
        page.locator(".m-sheet.is-open button", has_text="Keep picking").click()
        page.wait_for_timeout(450)
        check(status(pend[1]["shipment_id"])["status"] == "pending", "'Keep picking' leaves the order pending")

        # report a problem
        page.click("#issueBtn")
        page.wait_for_selector("#issueSheet.is-open")
        page.wait_for_timeout(400)
        gates(page, "problem sheet")
        page.locator("#issueSheet .m-radio", has_text="Damaged").click()
        page.fill("#issueNote", "box crushed")
        page.screenshot(path=str(OUT / "7-problem.png"))
        page.click("#issueSubmit")
        page.wait_for_selector("#queue:not([hidden])")
        st = status(pend[1]["shipment_id"])
        check(st["status"] == "issue" and "Item damaged — box crushed" in (st["flag_reason"] or ""), f"Report & skip -> server status 'issue' with the reason ({st['flag_reason']})")
        check(not errs, f"no JavaScript errors in the app session ({errs[:3]})")
        ctx.close()

        # ── iPhone Safari (browser fallback): web tab bar, type-it sheet ─────────
        ctx, page, errs = session("se")
        page.goto(base + "/m/pick?show=" + show.replace(" ", "%20"), wait_until="networkidle")
        page.wait_for_selector("#hero")
        check(page.is_visible(".m-tabbar"), "browser on a phone shows the web tab bar")
        page.wait_for_timeout(300)
        gates(page, "queue (iPhone SE, browser)")
        page.screenshot(path=str(OUT / "8-queue-se-browser.png"), full_page=True)
        page.click("#typeBtn")
        page.wait_for_selector(".m-sheet.is-open input")
        page.wait_for_timeout(400)
        page.screenshot(path=str(OUT / "9-type-code.png"))
        page.fill(".m-sheet.is-open input", pend[2]["shipment_id"])
        page.keyboard.press("Enter")
        page.wait_for_selector("#order:not([hidden])")
        check(True, "typing an order number by hand opens the order")
        gates(page, "order (iPhone SE, browser)")
        check(not errs, f"no JavaScript errors in the browser session ({errs[:3]})")
        ctx.close()

        # ── dark mode + iPad ────────────────────────────────────────────────────
        ctx, page, errs = session("pro", app_ua=True, dark=True)
        page.goto(base + "/m/pick", wait_until="networkidle")
        page.wait_for_selector("#showList button.pk-row")
        page.locator("#showList button.pk-row").first.click()
        page.wait_for_selector("#hero"); page.wait_for_timeout(2800)
        page.screenshot(path=str(OUT / "10-queue-dark.png"), full_page=True)
        ctx.close()
        ctx, page, errs = session("ipad", app_ua=True)
        page.goto(base + "/m/pick", wait_until="networkidle")
        page.wait_for_selector("#showList button.pk-row")
        page.locator("#showList button.pk-row").first.click()
        page.wait_for_selector("#hero"); page.wait_for_timeout(2800)
        gates(page, "queue (iPad)")
        page.screenshot(path=str(OUT / "11-queue-ipad.png"), full_page=True)
        ctx.close()
        browser.close()
    srv.shutdown()
    print(("\nFAILED: %d check(s)" % len(fails)) if fails else "\nAll checks passed. Screenshots: " + str(OUT))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
