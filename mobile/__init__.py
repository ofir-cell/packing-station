"""
Mobile screens for LiveOpsHub — a separate front end under /m/.

Why this is its own module
--------------------------
The desktop screens in templates.py run the warehouse floor every day. The iPhone/iPad
app needs screens designed for a phone, and rebuilding the desktop templates in place
would put the working floor at risk. So the mobile screens live here, with their own
HTML/CSS/JS, and talk to the SAME server:

  * same login and session cookie
  * same data
  * the same /api/pick/*, /api/shows, /api/shipment/* endpoints the desktop screens call

Business rules (cancelled orders, table clean-out, "already picked") therefore stay in
one place: app.py. Nothing in this module changes an existing route, template or table.

Wiring: app.py calls ``init_mobile(app, ...)`` once, after its auth decorators exist.
"""
import hashlib
import os
import re
from datetime import datetime

from flask import Blueprint, jsonify, redirect, session

_HERE = os.path.dirname(os.path.abspath(__file__))
_STATIC = os.path.join(_HERE, "static")

# Same roles as the desktop /pick screen (app.py pick_page). A Warehouse Manager gets in
# through req_role's manager->admin elevation, exactly as on desktop.
PICK_ROLES = ("picker", "worker", "admin", "cs")


def _read(name):
    with open(os.path.join(_HERE, name), encoding="utf-8") as f:
        return f.read()


def _asset_version():
    """Short content hash of everything in static/, so a deploy busts the web view's cache."""
    h = hashlib.sha256()
    for fn in sorted(os.listdir(_STATIC)):
        with open(os.path.join(_STATIC, fn), "rb") as f:
            h.update(fn.encode()); h.update(f.read())
    return h.hexdigest()[:10]


def _initials(name):
    parts = [p for p in (name or "").strip().split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][:1] + parts[-1][:1]).upper()


def init_mobile(app, *, req_role, sdb, esc, brand_style, staging_banner, heartbeat_js):
    """Register the /m/ screens on ``app``. Dependencies are passed in (not imported)
    so this module never imports app.py and can't create an import cycle."""
    bp = Blueprint("mobile", __name__, url_prefix="/m",
                   static_folder="static", static_url_path="/static")
    version = _asset_version()
    pick_html = _read("pick.html")

    def _brand_css():
        """Tenant brand colour — the same override the desktop navbar injects. The default
        LiveOpsHub indigo already lives in shell.css (with its violet gradient end), so
        only a tenant's OWN colour is emitted: its gradient ends on its darker shade, and
        dark mode keeps the colour too (with lightened text accents so they stay readable)."""
        css = brand_style() or ""
        m = re.search(r"--brand:(#[0-9a-fA-F]{6});--brand-strong:(#[0-9a-fA-F]{6})", css)
        if not m or m.group(1).lower() == "#4f46e5":
            return ""
        color, strong = m.group(1), m.group(2)
        r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
        tint = "#%02x%02x%02x" % tuple(int(v + (255 - v) * 0.55) for v in (r, g, b))
        return (css + "<style>:root{--brand-2:var(--brand-strong)}"
                "html.m.theme-dark{--brand:%s;--brand-2:%s;--brand-strong:%s;--brand-ink:%s;"
                "--brand-glow:rgba(%d,%d,%d,.20);--m-shadow-brand:0 8px 24px rgba(%d,%d,%d,.35)}</style>"
                % (color, strong, tint, tint, r, g, b, r, g, b))

    def _page(html, kind):
        name = session.get("name", "") or session.get("user", "")
        return (html
                .replace("__V__", version)
                .replace("__NAME__", esc(name))
                .replace("__INITIALS__", esc(_initials(name)))
                .replace("__ROLE__", esc(session.get("role", "")))
                .replace("__BRAND_STYLE__", _brand_css())
                # Appended after </html>, exactly as the desktop pages do: app.py's CSRF
                # shim is injected before </body>, and the heartbeat POST must run after it.
                .replace("__TAIL__", heartbeat_js(kind) + staging_banner()))

    @bp.route("/")
    def m_index():
        return redirect("/m/pick")

    @bp.route("/pick")
    @req_role(*PICK_ROLES)
    def m_pick():
        return _page(pick_html, "pick")

    @bp.route("/api/pick/extras")
    @req_role(*PICK_ROLES)
    def m_pick_extras():
        """Read-only companion to /api/shows for the mobile Pick queue: who is picking
        each show right now, and how many of its orders are flagged with an issue.
        (/api/shows has the counts; it doesn't carry picker names.)"""
        c = sdb()
        try:
            shows = {}
            for r in c.execute(
                    """SELECT import_label AS lbl, pick_started_by AS who, MAX(pick_started_at) AS last
                       FROM shipments
                       WHERE status='pending' AND COALESCE(pick_started_by,'')!=''
                         AND import_label IS NOT NULL AND import_label!=''
                       GROUP BY import_label, pick_started_by
                       ORDER BY last DESC""").fetchall():
                d = shows.setdefault(r["lbl"], {"pickers": [], "issues": 0})
                if len(d["pickers"]) < 5:
                    d["pickers"].append(r["who"])
            for r in c.execute(
                    """SELECT import_label AS lbl, COUNT(*) AS n FROM shipments
                       WHERE status='issue' AND import_label IS NOT NULL AND import_label!=''
                       GROUP BY import_label""").fetchall():
                shows.setdefault(r["lbl"], {"pickers": [], "issues": 0})["issues"] = r["n"]
        finally:
            c.close()
        return jsonify({"ok": True,
                        "me": session.get("name", "") or session.get("user", ""),
                        "today": datetime.now().strftime("%Y-%m-%d"),
                        "shows": shows})

    app.register_blueprint(bp)
    return bp
