"""
HTML templates and navbar helper for Packing Station.

All page templates are Python triple-quoted strings (no f-strings, to avoid
escaping nightmares with embedded JS/CSS). Route handlers replace placeholders
like `__NAME__`, `__NAVBAR__`, `__NAVBAR_CSS__` with `.replace()` at request time.
"""
from flask import session


def _brand():
    """Resolve the current tenant's branding. Every value is per-organization
    (SaaS white-labeling); app.py populates session['brand'] at login from the org
    config. The fallbacks are deliberately neutral — never another tenant's brand."""
    b = session.get("brand") or {}
    return {
        "mark": b.get("mark") or "LiveOpsHub",
        "sub": b.get("sub") or "Employee Hub",
        "logo_url": b.get("logo_url", ""),
        "color": b.get("color") or "#4f46e5",
    }

def _brand_style():
    """Per-tenant CSS override so the whole UI recolors to the org's brand color.
    Also derives darker variants (--brand-strong, --brand-ink) that stay readable
    as text/borders on the white theme. Injected once by _navbar."""
    import re as _re
    c = _brand()["color"]
    if not _re.match(r'^#[0-9a-fA-F]{6}$', c or ""):
        return ""
    r, g, bl = int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)
    def dark(f):
        return "#%02x%02x%02x" % (int(r*f), int(g*f), int(bl*f))
    glow = "rgba(%d,%d,%d,.16)" % (r, g, bl)
    return ('<style>:root{--brand:%s;--brand-strong:%s;--brand-ink:%s;--brand-glow:%s}</style>'
            % (c, dark(0.78), dark(0.5), glow))

def _initials(name):
    """Two-letter initials for the avatar (e.g. 'Maria Lopez' -> 'ML')."""
    parts = [p for p in (name or "").strip().split() if p]
    if not parts: return "?"
    if len(parts) == 1: return parts[0][:2].upper()
    return (parts[0][:1] + parts[-1][:1]).upper()

def _navbar(active_page=""):
    """Generate the unified top navigation bar based on user role.
    Operations/workflow links stay in the top row; everything personal, the
    team/admin config, and Logout live in the avatar menu at the top-right.
    `active_page` is the current page key for highlighting."""
    from markupsafe import escape as _e
    role=session.get("role","")
    raw_name=session.get("name","")
    name=str(_e(raw_name))
    if not role: return ""
    # A user can hold several roles (primary + extras). The nav shows everything
    # any of their roles grants.
    _rr=set(session.get("roles") or [role])
    def has(*rs):
        return any(r in _rr for r in rs)
    brand=_brand()
    initials=str(_e(_initials(raw_name)))

    # ── Support-mode banner (super-admin impersonating a tenant) ──
    imp = session.get("impersonator")
    imp_banner = ""
    if imp:
        _co = str(_e(brand.get("company", "this tenant")))
        imp_banner = (
            '<div style="position:sticky;top:0;z-index:1000;background:#b45309;color:#fff;'
            'padding:8px 16px;font-size:13px;font-weight:700;display:flex;align-items:center;'
            "justify-content:center;gap:14px;font-family:'DM Sans',sans-serif\">"
            '🛟 Support mode — viewing <b style="margin:0 2px">' + _co + '</b>'
            '<button onclick="impExit()" style="background:#fff;color:#b45309;border:none;'
            'border-radius:6px;padding:5px 12px;font-weight:800;cursor:pointer;font-family:inherit">'
            'Exit to platform</button></div>'
            '<script>function impExit(){fetch("/api/impersonate/exit",{method:"POST"})'
            '.then(function(r){return r.json()}).then(function(d){'
            'location.href=(d&&d.redirect)||"/admin/organizations"})}</script>')

    # ── Top-row entries (operations / fast links only) ──
    if role == "superadmin":
        # Platform owner: no tenant screens — the platform consoles only.
        entries = [("organizations", "/admin/organizations", "🏢 Organizations"),
                   ("support", "/admin/support", "🛟 Support"),
                   ("guides", "/admin/guides", "📚 Guides")]
    else:
        entries = [("home", "/home", "🏠 Home")]
        entries.append(("announcements", "/announcements", "📣 News"))
        if has("worker"):
            entries.append(("pack", "/", "📦 Pack"))
        if has("worker", "picker"):
            entries.append(("preshow", "/admin/preshow", "🔗 Match Products"))
        if has("admin", "cs"):
            # Operations is now a dedicated hub page (/operations) with tabbed cards
            # (Giveaways is one of its tabs).
            entries.append(("operations", "/operations", "📦 Operations"))
            entries.append(("roster", "/admin/roster", "🗓️ Roster"))
            entries.append(("support", "/support", "🛟 Support"))
            entries.append(("guides", "/guides", "📚 Guides"))
        if has("host", "assistant"):
            entries.append(("myavail", "/my-availability", "🕒 My Availability"))
            entries.append(("myschedule", "/my-schedule", "🗓️ My Schedule"))
        if has("host", "assistant", "admin", "cs"):
            entries.append(("scanit", "/scanit", "🍑 Scanit"))

    # ── Avatar menu sections (personal + team/settings) ──
    # Each section: (title, [(key,url,label),...]). Titles of "" render with no header.
    if role == "superadmin":
        # Platform owner has no personal/tenant sections — only Logout.
        user_sections = []
    else:
        _common = [
            ("me", "/me", "👤 My Profile"),
            ("leaderboard", "/leaderboard", "🏆 Leaderboard"),
            ("documents", "/documents", "📄 Documents"),
            ("onboarding", "/onboarding", "✅ Onboarding"),
        ]
        if has("worker", "picker"):
            _common.append(("guides", "/guides", "📚 Guides"))
        if has("host", "assistant"):
            _common.append(("myavail", "/my-availability", "🕒 My Availability"))
            _common.append(("myschedule", "/my-schedule", "🗓️ My Schedule"))
        user_sections = [("", _common)]
        if has("admin"):
            # Users / Badges / Permissions live *inside* Settings now, so they're
            # not repeated here — Settings is the single entry point for org config.
            user_sections.append(("Team & Admin", [
                ("setup", "/setup", "🚀 Company setup"),
                ("hires", "/admin/hires", "🧑‍💼 New Hires"),
                ("settings", "/admin/settings", "⚙️ Settings"),
                ("audit", "/admin/audit", "🧾 Audit log"),
            ]))
        elif has("cs"):
            user_sections.append(("Team", [
                ("hires", "/admin/hires", "🧑‍💼 New Hires"),
            ]))

    # ── Render row ──
    logo = ('<img src="' + str(_e(brand["logo_url"])) + '" alt="" class="brand-logo">') if brand["logo_url"] else ""
    nav_html = _brand_style() + imp_banner
    nav_html += '<nav class="topnav"><div class="topnav-inner">'
    _home_url = "/admin/organizations" if role == "superadmin" else "/home"
    nav_html += ('<a href="' + _home_url + '" class="topnav-brand">' + logo +
                 '<span class="brand-txt"><span class="brand-mark">' + str(_e(brand["mark"])) +
                 '</span><span class="brand-sub">' + str(_e(brand["sub"])) + '</span></span></a>')
    # Any Operations sub-page should light up the Operations link.
    ops_children = {"shows","shipments","cleanup","issues","dash","packer","customers",
                    "sku_lookup","shipstatus","inbound","giveaway","inventory","profit","purchasing",
                    "hosts","analytics","geo","pickeran","repeat"}
    nav_html += '<div class="topnav-links">'
    for e in entries:
        if isinstance(e, tuple):
            key, url, label = e
            is_active = (key == active_page) or (key == "operations" and active_page in ops_children)
            cls = "topnav-link active" if is_active else "topnav-link"
            nav_html += '<a href="' + url + '" class="' + cls + '">' + label + '</a>'
        else:
            group_active = any(it[0] == active_page for it in e["items"])
            gcls = "nav-group" + (" active" if group_active else "")
            nav_html += '<details class="' + gcls + '"><summary class="topnav-link">' + e["label"] + '<span class="caret">▾</span></summary>'
            nav_html += '<div class="nav-menu">'
            for it_key, it_url, it_label in e["items"]:
                it_cls = "nav-menu-item active" if it_key == active_page else "nav-menu-item"
                nav_html += '<a href="' + it_url + '" class="' + it_cls + '">' + it_label + '</a>'
            nav_html += '</div></details>'
    nav_html += '</div>'

    # ── Render avatar user menu (right) ──
    # Users/Badges/Permissions now live under Settings, so treat them as the
    # Settings entry for highlighting purposes.
    settings_children = {"users", "badges", "permissions"}
    eff_active = "settings" if active_page in settings_children else active_page
    umenu_active = any(it[0] == eff_active for _title, items in user_sections for it in items)
    ucls = "nav-user-group" + (" active" if umenu_active else "")
    nav_html += '<div class="topnav-user">'
    nav_html += '<details class="' + ucls + '"><summary class="user-avatar-btn" title="' + name + '">'
    nav_html += '<span class="user-avatar">' + initials + '</span>'
    nav_html += '<span class="user-name-inline">' + name + '</span><span class="caret">▾</span>'
    nav_html += '</summary><div class="nav-menu user-menu">'
    nav_html += '<div class="user-menu-head"><span class="user-avatar lg">' + initials + '</span>'
    nav_html += '<span class="user-menu-id"><b>' + name + '</b><small>' + str(_e(role.upper())) + '</small></span></div>'
    for title, items in user_sections:
        if title:
            nav_html += '<div class="user-menu-title">' + str(_e(title)) + '</div>'
        for it_key, it_url, it_label in items:
            it_cls = "nav-menu-item active" if it_key == eff_active else "nav-menu-item"
            nav_html += '<a href="' + it_url + '" class="' + it_cls + '">' + it_label + '</a>'
    nav_html += '<div class="user-menu-div"></div>'
    nav_html += '<a href="/logout" class="nav-menu-item logout">🚪 Logout</a>'
    nav_html += '</div></details>'
    nav_html += '</div>'
    nav_html += '</div></nav>'
    # Single-open + click-outside-to-close behaviour (covers row groups + user menu)
    nav_html += '<script>(function(){var ds=document.querySelectorAll(".nav-group,.nav-user-group");ds.forEach(function(d){d.addEventListener("toggle",function(){if(d.open)ds.forEach(function(o){if(o!==d)o.open=false})})});document.addEventListener("click",function(e){if(!e.target.closest(".nav-group")&&!e.target.closest(".nav-user-group"))ds.forEach(function(d){d.open=false})});document.addEventListener("keydown",function(e){if(e.key==="Escape")ds.forEach(function(d){d.open=false})})})();</script>'
    return nav_html

# CSS for the unified top navbar - injected into every page that uses it.
# Brand uses the 5 Second Beauty pink wordmark.
_NAVBAR_CSS='''<style>
:root{
  --brand:#d9748f;              /* per-tenant fill / avatar */
  --brand-strong:#c25c79;       /* darker hover */
  --brand-ink:#a63456;          /* readable brand accent text/border on white */
  --brand-glow:rgba(217,116,143,.18);
  --bg:#ffffff;
  --surface:#f6f7f9;
  --surface-strong:#eef0f4;
  --border:#e4e7ec;
  --text:#1a2130;
  --text-muted:#586274;
  --text-dim:#7b8494;
}
.topnav{background:rgba(255,255,255,.88);border-bottom:1px solid var(--border);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);position:sticky;top:0;z-index:100;font-family:'DM Sans',sans-serif}
.topnav-inner{max-width:1600px;margin:0 auto;padding:0 28px;display:flex;align-items:center;gap:28px;height:64px}
.topnav-brand{display:flex;flex-direction:row;align-items:center;gap:10px;line-height:1;text-decoration:none;flex-shrink:0;padding:6px 0}
.brand-logo{height:34px;width:auto;max-width:120px;border-radius:8px;display:block}
.brand-txt{display:flex;flex-direction:column;justify-content:center;line-height:1}
.brand-mark{font-size:20px;font-weight:900;color:var(--brand-ink);letter-spacing:1.5px;font-family:'DM Sans',sans-serif}
.brand-sub{font-size:9px;font-weight:700;color:var(--text-dim);letter-spacing:2.4px;text-transform:uppercase;margin-top:3px}
.topnav-brand:hover .brand-mark{color:var(--brand-strong)}
.topnav-links{display:flex;gap:2px;flex:1;align-items:center}
.topnav-link{color:var(--text-muted);text-decoration:none;font-size:13px;font-weight:600;padding:9px 14px;border-radius:10px;transition:all .15s;white-space:nowrap}
.topnav-link:hover{color:var(--text);background:var(--surface-strong)}
.topnav-link.active{color:var(--brand-ink);background:var(--brand-glow);box-shadow:inset 0 0 0 1px var(--brand-strong)}
/* Dropdown groups using HTML <details> */
.nav-group{position:relative;list-style:none}
.nav-group>summary{list-style:none;cursor:pointer;display:inline-flex;align-items:center;gap:4px;user-select:none}
.nav-group>summary::-webkit-details-marker,.nav-group>summary::marker{display:none;content:""}
.nav-group.active>summary{color:var(--brand-ink);background:var(--brand-glow);box-shadow:inset 0 0 0 1px var(--brand-strong)}
.nav-group .caret{font-size:9px;opacity:.6;transition:transform .15s;line-height:1}
.nav-group[open] .caret{transform:rotate(180deg);opacity:1}
.nav-menu{position:absolute;top:calc(100% + 6px);left:0;background:#ffffff;border:1px solid var(--border);border-radius:12px;padding:5px;min-width:200px;z-index:110;box-shadow:0 12px 32px rgba(15,23,42,.14);animation:menuIn .15s ease-out}
@keyframes menuIn{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:translateY(0)}}
.nav-menu-item{display:block;padding:9px 14px;font-size:13px;font-weight:600;color:var(--text-muted);text-decoration:none;border-radius:8px;transition:all .12s;white-space:nowrap}
.nav-menu-item:hover{color:var(--text);background:var(--surface-strong)}
.nav-menu-item.active{color:var(--brand-ink);background:var(--brand-glow)}
.topnav-user{display:flex;align-items:center;gap:12px;flex-shrink:0}
/* Avatar user menu */
.nav-user-group{position:relative;list-style:none}
.nav-user-group>summary{list-style:none;cursor:pointer;user-select:none}
.nav-user-group>summary::-webkit-details-marker,.nav-user-group>summary::marker{display:none;content:""}
.user-avatar-btn{display:inline-flex;align-items:center;gap:9px;padding:5px 12px 5px 5px;border-radius:999px;border:1px solid var(--border);background:var(--surface);transition:all .15s;min-height:44px}
.user-avatar-btn:hover{background:var(--surface-strong);border-color:var(--brand-strong)}
.nav-user-group[open]>summary .user-avatar-btn,.nav-user-group.active .user-avatar-btn{border-color:rgba(217,116,143,.35)}
.user-avatar{width:34px;height:34px;border-radius:50%;flex-shrink:0;display:inline-flex;align-items:center;justify-content:center;font-size:13px;font-weight:800;color:#1a1013;background:linear-gradient(135deg,var(--brand),var(--brand-strong));letter-spacing:.5px}
.user-avatar.lg{width:42px;height:42px;font-size:15px}
.user-name-inline{font-size:13px;color:var(--text);font-weight:700;white-space:nowrap;max-width:150px;overflow:hidden;text-overflow:ellipsis}
.nav-user-group .caret{font-size:9px;opacity:.6;transition:transform .15s;line-height:1;color:var(--text-dim)}
.nav-user-group[open] .caret{transform:rotate(180deg);opacity:1}
.user-menu{right:0;left:auto;min-width:248px}
.user-menu-head{display:flex;align-items:center;gap:11px;padding:9px 12px 11px;margin-bottom:4px;border-bottom:1px solid var(--border)}
.user-menu-id{display:flex;flex-direction:column;gap:2px;min-width:0}
.user-menu-id b{font-size:14px;color:var(--text);font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.user-menu-id small{font-size:10px;color:var(--text-dim);font-weight:700;letter-spacing:1.5px}
.user-menu-title{font-size:10px;font-weight:800;color:var(--text-dim);letter-spacing:1.4px;text-transform:uppercase;padding:9px 14px 4px}
.user-menu-div{height:1px;background:var(--border);margin:5px 8px}
.nav-menu-item.logout{color:#e11d48}
.nav-menu-item.logout:hover{color:#e11d48;background:rgba(244,63,94,.1)}
@media(max-width:768px){
.topnav-inner{padding:0 14px;gap:10px;height:auto;flex-wrap:wrap;padding-top:10px;padding-bottom:10px}
.brand-mark{font-size:17px}
.brand-logo{height:28px}
.topnav-links{order:3;width:100%;overflow-x:visible;flex:initial;padding-bottom:4px;flex-wrap:wrap}
.topnav-links::-webkit-scrollbar{display:none}
.topnav-user{order:2;margin-left:auto}
.user-name-inline{display:none}
.user-avatar-btn{padding:5px}
.nav-menu{position:static;margin-top:4px;width:100%;animation:none;background:rgba(17,24,39,0.048);box-shadow:none}
.user-menu{position:absolute;width:auto}
}
</style>'''


_FONT = '<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">'

LOGIN_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>__BRANDMARK__ — Employee Hub</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#ffffff;color:#1a2130;display:flex;align-items:center;justify-content:center;min-height:100vh;overflow:hidden;-webkit-font-smoothing:antialiased}
.glow{position:fixed;border-radius:50%;filter:blur(120px);opacity:.18;pointer-events:none}
.g1{width:640px;height:640px;top:-220px;right:-160px;background:#4f46e5}
.g2{width:480px;height:480px;bottom:-140px;left:-120px;background:#7c3aed}
.wrap{position:relative;z-index:1;width:100%;max-width:440px;padding:24px}
.logo{display:flex;align-items:center;justify-content:center;gap:13px;margin-bottom:34px}
.brand-tile{width:48px;height:48px;border-radius:13px;background:linear-gradient(135deg,#4f46e5,#7c3aed);display:flex;align-items:center;justify-content:center;box-shadow:0 10px 26px rgba(79,70,229,.34);flex:none}
.brand-txt{text-align:left}
.brand-mark-big{font-size:26px;font-weight:800;color:#141b26;letter-spacing:-.5px;line-height:1}
.brand-sub-big{font-size:9px;font-weight:700;color:#8a93a5;letter-spacing:2.6px;text-transform:uppercase;margin-top:5px}
.card{background:#ffffff;backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px);border:1px solid rgba(17,24,39,0.096);border-radius:22px;padding:40px 36px;box-shadow:0 24px 60px rgba(79,70,229,.10)}
.card h2{font-size:24px;font-weight:800;margin-bottom:4px;color:#141b26}
.card .sub{font-size:13px;color:#586274;margin-bottom:28px}
.field{margin-bottom:18px}
.field label{display:block;font-size:11px;font-weight:700;color:#586274;margin-bottom:8px;text-transform:uppercase;letter-spacing:.8px}
.field input{width:100%;background:#ffffff;border:2px solid rgba(17,24,39,0.096);border-radius:12px;padding:15px 18px;font-size:16px;color:#1a2130;font-family:inherit;outline:none;transition:all .2s}
.field input:focus{border-color:#6366f1;box-shadow:0 0 0 3px rgba(79,70,229,.12)}
.field input::placeholder{color:#6b7280}
.btn{width:100%;border:none;border-radius:12px;padding:16px;font-size:15px;font-weight:800;cursor:pointer;font-family:inherit;transition:all .15s;letter-spacing:.5px}
.btn-primary{background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#ffffff;margin-top:8px;box-shadow:0 8px 28px rgba(79,70,229,.28)}
.btn-primary:hover{filter:brightness(1.06);transform:translateY(-1px);box-shadow:0 10px 36px rgba(79,70,229,.36)}
.btn-primary:active{transform:scale(.98)}
.err{color:#f43f5e;font-size:13px;margin-top:14px;text-align:center;min-height:18px}
.back-to-badge{display:flex;align-items:center;justify-content:center;gap:8px;margin-top:22px;padding:14px;text-align:center;background:#f4f5fb;border:1px solid #e6e8f5;border-radius:12px;color:#586274;text-decoration:none;font-size:14px;font-weight:700;letter-spacing:.2px;transition:all .15s}
.back-to-badge:hover{background:#eef0fb;color:#4f46e5;border-color:rgba(79,70,229,.28)}
.foot{text-align:center;margin-top:28px;font-size:11px;color:#8a93a5;letter-spacing:1.5px}
</style></head><body>
<div class="glow g1"></div><div class="glow g2"></div>
<div class="wrap">
<div class="logo"><span class="brand-tile"><svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2"/><path d="M7 12h10"/></svg></span><span class="brand-txt"><span class="brand-mark-big">__BRANDMARK__</span><span class="brand-sub-big">Employee Sign-In</span></span></div>
<div class="card">
<h2>Sign in with password</h2><p class="sub">For admin or when no badge is available</p>
<div class="field"><label>Username</label><input type="text" id="u" placeholder="Enter your username" autofocus></div>
<div class="field"><label>Password</label><input type="password" id="p" placeholder="Enter your password"></div>
<button class="btn btn-primary" id="loginBtn">Sign In</button>
<div class="err" id="e"></div>
<a href="/badge-login" class="back-to-badge"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M7 9v6M11 9v6M15 9v6"/></svg> Back to badge scan</a>
</div>
<div class="foot">__BRANDNAME_UC__ &copy; 2026</div>
</div>
<script>
document.getElementById('p').addEventListener('keydown',function(e){if(e.key==='Enter')login()});
document.getElementById('u').addEventListener('keydown',function(e){if(e.key==='Enter')document.getElementById('p').focus()});
document.getElementById('loginBtn').addEventListener('click',login);
async function login(){
    var u=document.getElementById('u').value.trim(),p=document.getElementById('p').value;
    if(!u||!p){document.getElementById('e').textContent='Please enter username and password';return}
    var r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p})});
    var d=await r.json();
    if(d.ok){
        // / does device-aware routing: workers on mobile → /pick,
        // workers on desktop → packing screen, admin/cs → /home.
        window.location.href = '/';
    } else document.getElementById('e').textContent=d.error;
}
</script></body></html>'''

# ── STATION SELECT ────────────────────────────────────────
STATION_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Select Station</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#ffffff;color:#1a2130;display:flex;align-items:center;justify-content:center;min-height:100vh}
.wrap{text-align:center;padding:24px;width:100%;max-width:700px}
.hi{font-size:16px;color:#6b7280;margin-bottom:4px}
.hi b{color:#d9748f}
.title{font-size:34px;font-weight:800;margin-bottom:8px}
.sub{font-size:16px;color:#6b7280;margin-bottom:44px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:16px}
.s-btn{background:#ffffff;border:2px solid rgba(17,24,39,0.096);border-radius:18px;padding:32px 16px;cursor:pointer;transition:all .25s;text-align:center}
.s-btn:hover{border-color:#d9748f;background:rgba(217,116,143,.08);transform:translateY(-4px);box-shadow:0 8px 30px rgba(217,116,143,.18)}
.s-btn:active{transform:scale(.96)}
.s-icon{font-size:36px;margin-bottom:12px}
.s-name{font-size:17px;font-weight:700}
.s-id{font-size:12px;color:#6b7280;margin-top:4px}
.out{position:fixed;top:20px;right:20px;color:#6b7280;text-decoration:none;font-size:13px;border:1px solid rgba(17,24,39,0.128);padding:8px 16px;border-radius:10px;transition:all .2s}
.out:hover{color:#1a2130;border-color:rgba(17,24,39,0.16)}
</style></head><body>
<a href="/logout" class="out">Logout</a>
<div class="wrap">
<div class="hi">Hello, <b>__NAME__</b> 👋</div>
<div class="title">Select Your Station</div>
<div class="sub">Choose the packing station you are working at today</div>
<div class="grid" id="g"></div>
</div>
<script>
var icons=['📦','🏷️','📋','🔖','📮','✉️'];
fetch('/api/stations').then(function(r){return r.json()}).then(function(d){
    var g=document.getElementById('g');var i=0;
    Object.keys(d).forEach(function(id){
        var btn=document.createElement('div');btn.className='s-btn';
        btn.innerHTML='<div class="s-icon">'+icons[i%6]+'</div><div class="s-name">'+d[id]+'</div><div class="s-id">'+id+'</div>';
        btn.addEventListener('click',function(){
            fetch('/api/select-station',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({station:id})})
            .then(function(r){return r.json()}).then(function(r){if(r.ok)location.href='/'});
        });
        g.appendChild(btn);i++;
    });
});
</script></body></html>'''

# ── WORKER PACKING SCREEN ────────────────────────────────
WORKER_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
''' + _FONT + '''
<title>__BRANDMARK__ — Packing</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{height:100%;overflow:hidden}
body{font-family:'DM Sans',sans-serif;color:#1a2130;display:flex;flex-direction:column;align-items:center;justify-content:center;transition:background .4s}
body.sr{background:#ffffff}body.sc{background:#fff1f2}body.sd{background:#f0fdf4}body.su{background:#ffffff}
.x{display:none;text-align:center;padding:24px;width:100%}
.x.on{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:80vh}
.top{position:fixed;top:0;left:0;right:0;padding:12px 18px;display:flex;justify-content:space-between;align-items:center;z-index:10;gap:12px}
.brand-tag{display:flex;align-items:center;gap:10px;min-width:0}
.brand-mark-mini{font-size:14px;font-weight:900;color:#d9748f;letter-spacing:1.2px;flex-shrink:0}
.portal-b{background:rgba(217,116,143,.08);border:1px solid rgba(217,116,143,.22);border-radius:8px;padding:7px 13px;font-size:12px;font-weight:700;color:#d9748f;text-decoration:none;font-family:inherit;transition:all .15s}
.portal-b:hover{background:rgba(217,116,143,.16)}
.role-switch{background:rgba(16,185,129,.1);border:1px solid rgba(16,185,129,.28);border-radius:8px;padding:7px 13px;font-size:12px;font-weight:700;color:#059669;text-decoration:none;font-family:inherit;transition:all .15s}
.role-switch:hover{background:rgba(16,185,129,.2)}
.badge{background:rgba(217,116,143,.12);border:1.5px solid rgba(217,116,143,.28);border-radius:50px;padding:8px 20px;font-size:13px;font-weight:700;color:#d9748f}
.top-r{display:flex;gap:10px;align-items:center}
.cam{display:flex;align-items:center;gap:5px;font-size:12px;padding:6px 12px;border-radius:20px;background:rgba(0,0,0,.3)}
.cam-d{width:7px;height:7px;border-radius:50%}
.cam.ok .cam-d{background:#10b981}.cam.ok span{color:#10b981}
.cam.err .cam-d{background:#f43f5e}.cam.err span{color:#f43f5e}
.out-b{background:none;border:1px solid rgba(17,24,39,0.128);border-radius:8px;padding:6px 14px;font-size:12px;color:#6b7280;cursor:pointer;font-family:inherit}
.pv{position:fixed;bottom:16px;left:16px;width:150px;border-radius:12px;overflow:hidden;border:2px solid rgba(17,24,39,0.096);opacity:.35;transition:all .3s}
.pv video{width:100%;display:block}
body.sc .pv{width:200px;opacity:1;border-color:#f43f5e}

.r-icon{width:120px;height:120px;background:#ffffff;border-radius:30px;display:flex;align-items:center;justify-content:center;font-size:56px;margin-bottom:32px;border:2.5px solid rgba(17,24,39,0.096)}
.r-title{font-size:40px;font-weight:800;margin-bottom:10px}
.r-sub{font-size:18px;color:#6b7280;margin-bottom:36px}
.inp-w{width:100%;max-width:500px}
.inp{width:100%;background:#ffffff;border:3px solid #d9748f;border-radius:16px;padding:20px 24px;font-size:24px;color:#1a2130;font-family:inherit;text-align:center;outline:none;transition:all .2s}
.inp:focus{border-color:#c25c79;box-shadow:0 0 30px rgba(217,116,143,.3)}
.inp::placeholder{color:#6b7280}
.hint{margin-top:14px;font-size:14px;color:#6b7280}
.pd{display:inline-block;width:8px;height:8px;background:#d9748f;border-radius:50%;margin-right:8px;animation:pls 1.5s ease infinite}
@keyframes pls{0%,100%{opacity:.3;transform:scale(1)}50%{opacity:1;transform:scale(1.3)}}
.ctr{margin-top:36px;font-size:14px;color:#6b7280}.ctr b{color:#d9748f}

.rp{display:flex;align-items:center;gap:12px;background:rgba(244,63,94,.1);border:2px solid rgba(244,63,94,.3);border-radius:50px;padding:12px 28px;margin-bottom:28px;animation:rpls 1.5s ease infinite}
@keyframes rpls{0%,100%{border-color:rgba(244,63,94,.3)}50%{border-color:rgba(244,63,94,.7)}}
.rd{width:15px;height:15px;background:#f43f5e;border-radius:50%;animation:bk 1s ease infinite}
@keyframes bk{0%,100%{opacity:1}50%{opacity:.2}}
.rl{font-size:18px;font-weight:800;color:#f43f5e;letter-spacing:1px}
.rk{font-size:48px;font-weight:900;color:#f1f5f9;margin-bottom:14px;letter-spacing:.5px}
.rm{font-size:72px;font-weight:900;color:#f43f5e;font-feature-settings:'tnum';margin-bottom:20px}
.steps{display:flex;flex-direction:column;gap:12px;margin-top:16px}
.step{display:flex;align-items:center;gap:12px;font-size:18px;color:#6b7280}
.step.now{color:#f1f5f9;font-weight:700}
.si{width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:14px;background:#ffffff;border:2px solid rgba(17,24,39,0.128);flex-shrink:0}
.step.ok .si{background:#065f46;border-color:#10b981}
.step.now .si{background:#7c2d12;border-color:#b45309;animation:spls 1.5s ease infinite}
@keyframes spls{0%,100%{box-shadow:0 0 0 0 rgba(245,158,11,.2)}50%{box-shadow:0 0 0 8px rgba(245,158,11,0)}}
.hinp{position:absolute;top:-9999px;left:-9999px}

/* ────────────────────────────────────────────────────────────────
   PACKER ITEM-COUNT REMINDER (no-touch)
   ────────────────────────────────────────────────────────────────
   Stage 1 (first 8s after scan): big centered overlay showing how
   many items should be in the package + SKU list. Impossible to miss.
   Stage 2 (after 8s, persists during recording): same info shrunk
   to a corner card so the packer can keep glancing at it.
   NO buttons, NO clicking — packers work with scanner only.
*/
#countOverlay{position:fixed;inset:0;background:#ffffff;backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);z-index:900;display:none;align-items:center;justify-content:center;padding:24px;animation:countFade .25s ease}
#countOverlay.on{display:flex}
@keyframes countFade{from{opacity:0}to{opacity:1}}
.count-card{max-width:640px;width:100%;text-align:center;animation:countPop .45s cubic-bezier(.175,.885,.32,1.275)}
@keyframes countPop{from{transform:scale(.7);opacity:0}to{transform:scale(1);opacity:1}}
.count-icon{font-size:80px;margin-bottom:8px}
.count-buyer{font-size:18px;color:#586274;font-weight:700;margin-bottom:6px}
.count-buyer b{color:#1a2130;font-weight:800}
.count-big{font-size:180px;font-weight:900;color:#d9748f;line-height:.95;letter-spacing:-6px;font-feature-settings:'tnum';margin:8px 0 2px;text-shadow:0 8px 50px rgba(217,116,143,.35)}
.count-label{font-size:30px;font-weight:900;color:#141b26;letter-spacing:2px;text-transform:uppercase;margin-bottom:18px}
.count-label.warn{color:#b45309}
.count-items{display:flex;flex-direction:column;gap:8px;max-height:38vh;overflow-y:auto;padding:4px;margin-bottom:14px}
.count-item{display:flex;align-items:center;gap:14px;padding:14px 18px;background:#ffffff;border:2px solid rgba(217,116,143,.18);border-radius:14px;text-align:left}
.count-item.cancelled{opacity:.5;border-color:rgba(244,63,94,.3);background:rgba(244,63,94,.04)}
.count-item.cancelled .ci-name,.count-item.cancelled .ci-sku{text-decoration:line-through}
.count-item .ci-sku{flex-shrink:0;font-family:'SF Mono',Menlo,monospace;font-size:24px;font-weight:900;color:#d9748f;min-width:60px;text-align:center;background:rgba(217,116,143,.14);padding:6px 12px;border-radius:10px;letter-spacing:.5px}
.count-item .ci-name{flex:1;font-size:16px;color:#1a2130;line-height:1.4;min-width:0;font-weight:600}
.count-item .ci-name .part-tag{display:inline-block;background:rgba(217,116,143,.22);color:#d9748f;font-family:'SF Mono',Menlo,monospace;font-weight:900;font-size:15px;padding:3px 10px;border-radius:8px;letter-spacing:.5px;margin-right:8px;vertical-align:middle;text-transform:uppercase}
.count-item .ci-qty{font-size:22px;color:#141b26;font-weight:900;flex-shrink:0;font-feature-settings:'tnum'}
.count-foot{font-size:14px;color:#6b7280;font-weight:600;letter-spacing:.5px;text-transform:uppercase}
.count-foot.warn{color:#b45309}

/* Stage 2 — persistent side card during recording */
.reminder-side{position:fixed;top:90px;right:24px;width:280px;background:#ffffff;backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);border:1px solid rgba(217,116,143,.28);border-radius:18px;padding:18px 20px;z-index:50;display:none;box-shadow:0 14px 40px rgba(0,0,0,.5);animation:sideIn .35s ease}
@keyframes sideIn{from{opacity:0;transform:translateX(20px)}to{opacity:1;transform:translateX(0)}}
.reminder-side.on{display:block}
.reminder-side .rs-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
.reminder-side .rs-count{font-size:48px;font-weight:900;color:#d9748f;line-height:1;font-feature-settings:'tnum';letter-spacing:-2px}
.reminder-side .rs-lbl{font-size:11px;color:#586274;font-weight:800;letter-spacing:1.5px;text-transform:uppercase;text-align:right}
.reminder-side .rs-lbl b{color:#d9748f;display:block;font-size:13px}
.reminder-side .rs-list{display:flex;flex-direction:column;gap:6px;max-height:42vh;overflow-y:auto;padding-right:4px}
.reminder-side .rs-list::-webkit-scrollbar{width:4px}.reminder-side .rs-list::-webkit-scrollbar-thumb{background:rgba(17,24,39,0.16);border-radius:2px}
.rs-item{display:flex;align-items:center;gap:10px;padding:9px 12px;background:rgba(17,24,39,0.064);border-radius:10px;font-size:12px}
.rs-item.cancelled{opacity:.45;text-decoration:line-through}
.rs-item .rs-sku{font-family:'SF Mono',Menlo,monospace;font-size:14px;font-weight:900;color:#d9748f;background:rgba(217,116,143,.12);padding:2px 8px;border-radius:6px;min-width:38px;text-align:center;letter-spacing:.4px}
.rs-item .rs-name{flex:1;color:#1a2130;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:600}
.rs-item .rs-name .part-tag{display:inline-block;background:rgba(217,116,143,.18);color:#d9748f;font-family:'SF Mono',Menlo,monospace;font-weight:900;font-size:11px;padding:1px 6px;border-radius:5px;letter-spacing:.4px;margin-right:5px;vertical-align:middle;text-transform:uppercase}
.rs-item .rs-qty{font-size:14px;font-weight:900;color:#141b26;font-feature-settings:'tnum'}
.reminder-side.warn{border-color:rgba(245,158,11,.4)}
.reminder-side.warn .rs-count{color:#b45309}
.reminder-side .rs-show{font-size:10px;color:#6b7280;font-weight:700;letter-spacing:.5px;text-transform:uppercase;margin-top:10px;padding-top:10px;border-top:1px solid rgba(17,24,39,0.096)}
.reminder-side .rs-show b{color:#d9748f}

/* Cancellation alert — fullscreen red overlay */
#cancelOverlay{position:fixed;inset:0;background:linear-gradient(135deg,#e11d48,#b91c1c);z-index:1000;align-items:center;justify-content:center;padding:24px;animation:cancelIn .3s ease}
#cancelOverlay[style*="flex"]{display:flex!important}
@keyframes cancelIn{from{opacity:0}to{opacity:1}}
.cancel-box{max-width:520px;width:100%;text-align:center;animation:cancelPop .4s cubic-bezier(.175,.885,.32,1.275)}
@keyframes cancelPop{from{transform:scale(.85)}to{transform:scale(1)}}
.cancel-icon{font-size:120px;margin-bottom:14px;animation:cancelShake .5s ease}
@keyframes cancelShake{0%,100%{transform:translateX(0)}25%{transform:translateX(-12px)}75%{transform:translateX(12px)}}
.cancel-title{font-size:60px;font-weight:900;color:#fff;letter-spacing:2px;margin-bottom:8px;text-shadow:0 4px 24px rgba(0,0,0,.3)}
.cancel-sub{font-size:22px;color:#ffe4e6;margin-bottom:32px;font-weight:600}
.cancel-buyer-row,.cancel-reason-row{font-size:18px;color:#fff;margin-bottom:10px}
.cancel-buyer-row b,.cancel-reason-row b{color:#fff;font-weight:700}
.cancel-ok{margin-top:36px;background:#fff;color:#1a0e0b;border:none;border-radius:14px;padding:18px 36px;font-size:16px;font-weight:800;cursor:pointer;font-family:inherit;letter-spacing:.5px;box-shadow:0 8px 28px rgba(17,24,39,0.16)}
.cancel-ok:hover{background:#e11d48;color:#1a0e0b}
.cancel-ok:active{transform:scale(.97)}

.d-icon{width:120px;height:120px;background:#065f46;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:60px;margin-bottom:24px;animation:pop .4s cubic-bezier(.175,.885,.32,1.275)}
@keyframes pop{0%{transform:scale(0)}100%{transform:scale(1)}}
.dt{font-size:40px;font-weight:800;color:#10b981;margin-bottom:6px}
.dk{font-size:26px;font-weight:700;margin-bottom:6px}
.dd{font-size:16px;color:#6b7280;margin-bottom:28px}
.dn{font-size:16px;color:#6b7280}

.us{width:48px;height:48px;border:4px solid rgba(17,24,39,0.128);border-top-color:#d9748f;border-radius:50%;animation:sp .8s linear infinite;margin-bottom:20px}
@keyframes sp{to{transform:rotate(360deg)}}
.ut{font-size:22px;font-weight:700;margin-bottom:6px}
.uu{font-size:15px;color:#6b7280}

.w-icon{font-size:80px;margin-bottom:24px;animation:pop .5s cubic-bezier(.175,.885,.32,1.275)}
.w-title{font-size:38px;font-weight:900;color:#1a2130;margin-bottom:8px}
.w-sub{font-size:20px;color:#d9748f;margin-bottom:20px}
.w-sub b{color:#c25c79}
.w-msg{font-size:16px;color:#6b7280;max-width:400px}

.f-icon{font-size:80px;margin-bottom:24px;animation:pop .5s cubic-bezier(.175,.885,.32,1.275)}
.f-title{font-size:38px;font-weight:900;color:#10b981;margin-bottom:8px}
.f-sub{font-size:20px;color:#1a2130;margin-bottom:20px}
.f-msg{font-size:16px;color:#6b7280}
body.sw{background:linear-gradient(135deg,#ffffff,#fffbeb)}
body.sf{background:linear-gradient(135deg,#ffffff,#f0fdf4)}
</style></head><body class="sr">
<div class="top"><div class="brand-tag"><span class="brand-mark-mini">5&nbsp;SEC</span><span class="badge">__STATION__ — __NAME__</span></div><div class="top-r"><div class="cam" id="cm"><div class="cam-d"></div><span data-i18n="camera">Camera</span></div><button class="role-switch" id="langBtn" onclick="toggleLang()" style="cursor:pointer">ES</button><a href="/pick" class="role-switch" data-i18n="switchpick">📋 Switch to Picking</a><a href="/home" class="portal-b" data-i18n="portal">🏠 Portal</a><button class="out-b" id="endBtn" data-i18n="endshift">End Shift</button></div></div>
<div class="pv"><video id="pv" autoplay muted playsinline></video></div>

<div class="x on" id="xw"><div class="w-icon">👋</div><div class="w-title"><span data-i18n="welcomeg">Welcome</span>, __NAME__!</div><div class="w-sub"><span data-i18n="youareat">You are at</span> <b>__STATION__</b></div><div class="w-msg" data-i18n="greatshift">Have a great shift! Your camera is being set up...</div></div>

<div class="x" id="xr"><div class="r-icon">📦</div><div class="r-title" data-i18n="scantracking">Scan Tracking Number</div><div class="r-sub" data-i18n="scantostart">Scan the barcode to start recording</div><div class="inp-w"><input class="inp" id="mi" placeholder="Waiting for scan..." data-i18n-ph="waitscan" autocomplete="off"></div><div class="hint"><span class="pd"></span><span data-i18n="scannerready">Scanner ready</span></div><div class="ctr"><span data-i18n="recorded">Recorded:</span> <b id="cn">0</b></div></div>

<div class="x" id="xc"><div class="rp"><div class="rd"></div><div class="rl" data-i18n="recording">RECORDING</div></div><div class="rk" id="rk"></div><div class="rm" id="rmm">00:00</div>
<div class="steps" id="stepsLight"><div class="step ok"><div class="si">✓</div><span data-i18n="step_scan">Scan tracking number</span></div><div class="step now"><div class="si">2</div><span data-i18n="step_pack">Pack the order in front of the camera</span></div><div class="step"><div class="si">3</div><span data-i18n="step_again">Scan again to finish</span></div></div><input class="hinp" id="ri" autocomplete="off"></div>

<!-- Stage 1 (8s): big centered count overlay shown after every scan -->
<div id="countOverlay">
  <div class="count-card">
    <div class="count-icon">📦</div>
    <div class="count-buyer" id="countBuyer" data-i18n="lookingup">Looking up order…</div>
    <div class="count-big" id="countBig">—</div>
    <div class="count-label" id="countLabel" data-i18n="itemsinpkg">items in package</div>
    <div class="count-items" id="countItems"></div>
    <div class="count-foot" id="countFoot" data-i18n="ifmissing">If an item is missing — set the package aside</div>
  </div>
</div>

<!-- Stage 2: small persistent reminder card while recording -->
<div class="reminder-side" id="reminderSide">
  <div class="rs-head">
    <div class="rs-count" id="rsCount">—</div>
    <div class="rs-lbl">items<br><b id="rsBuyer">—</b></div>
  </div>
  <div class="rs-list" id="rsList"></div>
  <div class="rs-show" id="rsShow"></div>
</div>

<!-- Cancellation alert overlay - shows red full-screen when scanned shipment is cancelled -->
<div id="cancelOverlay" style="display:none">
  <div class="cancel-box">
    <div class="cancel-icon">🚨</div>
    <div class="cancel-title" data-i18n="donotpack">DO NOT PACK</div>
    <div class="cancel-sub" data-i18n="ordercancelled">This order has been cancelled</div>
    <div class="cancel-buyer-row"><span data-i18n="buyer">Buyer:</span> <b id="cancelBuyer">—</b></div>
    <div class="cancel-reason-row" id="cancelReasonRow"><span data-i18n="reason">Reason:</span> <b id="cancelReason">—</b></div>
    <button class="cancel-ok" id="cancelOk" data-i18n="gotitreturn">Got it — return to scan</button>
  </div>
</div>

<!-- Giveaway add overlay - green full-screen when the scanned order has a prize to add -->
<div id="giveawayOverlay" style="display:none;position:fixed;inset:0;z-index:60;background:#ffffff;align-items:center;justify-content:center">
  <div class="cancel-box" style="border-color:rgba(52,211,153,.5)">
    <div class="cancel-icon">🎁</div>
    <div class="cancel-title" style="color:#059669" data-i18n="addgiveaway">ADD GIVEAWAY</div>
    <div class="cancel-sub" data-i18n="gotomanagerpack">Go to the <b>manager</b> to get the prize, then add it to the box before sealing</div>
    <div id="gvList" style="margin:16px 0;font-size:20px;font-weight:800;color:#1a2130"></div>
    <button class="cancel-ok" id="gvOk" style="background:#10b981" data-i18n="addedcontinue">✓ Added — continue</button>
  </div>
</div>

<div class="x" id="xu"><div class="us"></div><div class="ut" data-i18n="savingrec">Saving recording...</div><div class="uu" data-i18n="pleasewait">Please wait</div></div>

<div class="x" id="xd"><div class="d-icon">✓</div><div class="dt" data-i18n="saved">Saved!</div><div class="dk" id="dkk"></div><div class="dd" id="ddd"></div><div class="dn" data-i18n="nextorder">Next order...</div></div>

<div class="x" id="xf"><div class="f-icon">🌟</div><div class="f-title" data-i18n="greatjob">Great job today!</div><div class="f-sub"><span data-i18n="thankyou">Thank you for your hard work</span>, __NAME__</div><div class="f-msg" data-i18n="wonderfulday">Have a wonderful day! See you next time 👋</div></div>

<script>
var st='w',ti=null,t0=0,n=0,mr=null,ch=[],sm=null,ct='';
var mi=document.getElementById('mi'),ri=document.getElementById('ri');
var X={w:document.getElementById('xw'),r:document.getElementById('xr'),c:document.getElementById('xc'),u:document.getElementById('xu'),d:document.getElementById('xd'),f:document.getElementById('xf')};
var LANG=localStorage.getItem('lang')||'en';
var T={en:{
 camera:'Camera',switchpick:'📋 Switch to Picking',portal:'🏠 Portal',endshift:'End Shift',welcomeg:'Welcome',youareat:'You are at',
 greatshift:'Have a great shift! Your camera is being set up...',scantracking:'Scan Tracking Number',scantostart:'Scan the barcode to start recording',
 waitscan:'Waiting for scan...',scannerready:'Scanner ready',recorded:'Recorded:',recording:'RECORDING',step_scan:'Scan tracking number',
 step_pack:'Pack the order in front of the camera',step_again:'Scan again to finish',lookingup:'Looking up order…',itemsinpkg:'items in package',
 iteminpkg:'item in package',ifmissing:'If an item is missing — set the package aside',donotpack:'DO NOT PACK',ordercancelled:'This order has been cancelled',
 buyer:'Buyer:',reason:'Reason:',gotitreturn:'Got it — return to scan',addgiveaway:'ADD GIVEAWAY',
 gotomanagerpack:'Go to the <b>manager</b> to get the prize, then add it to the box before sealing',addedcontinue:'✓ Added — continue',
 savingrec:'Saving recording...',pleasewait:'Please wait',saved:'Saved!',nextorder:'Next order...',greatjob:'Great job today!',
 thankyou:'Thank you for your hard work',wonderfulday:'Have a wonderful day! See you next time 👋',nocamera:'No camera',
 countbox:'Count what you put in the box — if anything is missing, set the package aside',prepicked:'✓ Pre-picked by',justverify:'· just verify count and pack',ordernotfound:'Order not found in system'
},es:{
 camera:'Cámara',switchpick:'📋 Cambiar a Recolección',portal:'🏠 Portal',endshift:'Terminar Turno',welcomeg:'Bienvenido',youareat:'Estás en',
 greatshift:'¡Que tengas un buen turno! Tu cámara se está configurando...',scantracking:'Escanea el Número de Rastreo',scantostart:'Escanea el código para empezar a grabar',
 waitscan:'Esperando escaneo...',scannerready:'Escáner listo',recorded:'Grabados:',recording:'GRABANDO',step_scan:'Escanea el número de rastreo',
 step_pack:'Empaca el pedido frente a la cámara',step_again:'Escanea de nuevo para terminar',lookingup:'Buscando pedido…',itemsinpkg:'artículos en el paquete',
 iteminpkg:'artículo en el paquete',ifmissing:'Si falta un artículo — aparta el paquete',donotpack:'NO EMPACAR',ordercancelled:'Este pedido fue cancelado',
 buyer:'Comprador:',reason:'Motivo:',gotitreturn:'Entendido — volver a escanear',addgiveaway:'AGREGAR REGALO',
 gotomanagerpack:'Ve al <b>gerente</b> por el regalo, luego agrégalo a la caja antes de sellar',addedcontinue:'✓ Agregado — continuar',
 savingrec:'Guardando grabación...',pleasewait:'Por favor espera',saved:'¡Guardado!',nextorder:'Siguiente pedido...',greatjob:'¡Buen trabajo hoy!',
 thankyou:'Gracias por tu esfuerzo',wonderfulday:'¡Que tengas un buen día! Hasta la próxima 👋',nocamera:'Sin cámara',
 countbox:'Cuenta lo que pones en la caja — si falta algo, aparta el paquete',prepicked:'✓ Pre-recolectado por',justverify:'· solo verifica y empaca',ordernotfound:'Pedido no encontrado en el sistema'
}};
function t(k){return (T[LANG]&&T[LANG][k])||T.en[k]||k}
function toggleLang(){LANG=(LANG==='en'?'es':'en');localStorage.setItem('lang',LANG);location.reload()}
function applyLang(){
 document.querySelectorAll('[data-i18n]').forEach(function(e){e.innerHTML=t(e.dataset.i18n)});
 document.querySelectorAll('[data-i18n-ph]').forEach(function(e){e.placeholder=t(e.dataset.i18nPh)});
 var lb=document.getElementById('langBtn');if(lb)lb.textContent=(LANG==='en'?'ES':'EN');
}
applyLang();
function go(s){st=s;document.body.className=s==='c'?'sc':s==='d'?'sd':s==='u'?'su':s==='w'?'sw':s==='f'?'sf':'sr';
for(var k in X)X[k].classList.toggle('on',k===s);
if(s==='r'){mi.value='';setTimeout(function(){mi.focus()},100)}
if(s==='c'){ri.value='';setTimeout(function(){ri.focus()},100)}}
setTimeout(function(){go('r')},3000);
document.getElementById('endBtn').addEventListener('click',function(){go('f');setTimeout(function(){location.href='/logout'},3500)});
document.addEventListener('click',function(){if(st==='r')mi.focus();if(st==='c')ri.focus()});
setInterval(function(){if(st==='r'&&document.activeElement!==mi)mi.focus();if(st==='c'&&document.activeElement!==ri)ri.focus()},400);
function initCam(){navigator.mediaDevices.getUserMedia({video:{width:{ideal:854,max:1280},height:{ideal:480,max:720},frameRate:{ideal:15,max:24}},audio:false}).then(function(s){sm=s;document.getElementById('pv').srcObject=s;document.getElementById('cm').className='cam ok'}).catch(function(){document.getElementById('cm').className='cam err'})}
initCam();
function pickMime(){var c=['video/webm;codecs=vp8','video/webm;codecs=vp9','video/webm','video/mp4'];
  for(var i=0;i<c.length;i++){try{if(window.MediaRecorder&&MediaRecorder.isTypeSupported&&MediaRecorder.isTypeSupported(c[i]))return c[i]}catch(e){}}return '';}
function startRec(trk){if(!sm){alert(t('nocamera'));return}ct=trk;ch=[];
  // Match bitrate to the ACTUAL capture resolution — a fixed rate starves VP8 at
  // 720p/1080p and the picture pixelates on motion with no keyframe to recover.
  // Target ~0.15 bit/pixel, clamped 1.5–6 Mbps (short clips stay small).
  var vt=sm.getVideoTracks?sm.getVideoTracks()[0]:null;
  var vs=(vt&&vt.getSettings)?vt.getSettings():{};
  var w=vs.width||854,h=vs.height||480,fps=vs.frameRate||15;
  var br=Math.round(w*h*fps*0.15);br=Math.max(1500000,Math.min(br,6000000));
  var opts={videoBitsPerSecond:br};var mime=pickMime();if(mime)opts.mimeType=mime;
  try{mr=new MediaRecorder(sm,opts)}catch(e){try{mr=new MediaRecorder(sm,{videoBitsPerSecond:br})}catch(e2){mr=new MediaRecorder(sm)}}
  try{console.log('[rec] '+w+'x'+h+'@'+fps+'fps '+Math.round(br/1000)+'kbps '+(mime||'default'))}catch(e){}
  mr.ondataavailable=function(e){if(e.data.size>0)ch.push(e.data)};
  mr.start();  // no timeslice → one complete blob on stop (no chunk-join risk)
  t0=Date.now();startTmr();document.getElementById('rk').textContent=trk;go('c');loadChecklist(trk)}

// ─── Packer item-count reminder (NO touch / NO buttons) ───
// After each scan we look up the shipment and:
//   1) Pop a huge centered overlay showing the count for ~8 seconds.
//   2) Slide a small side card with the count + SKU list into the corner so the
//      packer can keep glancing at it while packing.
// The packer scans the tracking number a second time to finish — no clicks ever.
var countTimer=null;

function renderProductNameHtml(s){
    var safe=(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    var m=safe.match(/(Part\s*\d+)/i);
    if(!m)return safe;
    var stripped=safe.replace(/[\s·,—–-]*Part\s*\d+[\s·,—–-]*/i,' ').replace(/\s{2,}/g,' ').trim();
    return '<span class="part-tag">'+m[1].toUpperCase()+'</span>'+stripped;
}

function hideReminder(){
    var ov=document.getElementById('countOverlay');
    var side=document.getElementById('reminderSide');
    if(ov)ov.classList.remove('on');
    if(side)side.classList.remove('on');
    if(countTimer){clearTimeout(countTimer);countTimer=null}
}

function loadChecklist(tracking){
    // Clear any leftover reminder from a previous scan
    hideReminder();
    var ov=document.getElementById('countOverlay');
    var side=document.getElementById('reminderSide');
    document.getElementById('countBuyer').textContent='Looking up order…';
    document.getElementById('countBig').textContent='—';
    document.getElementById('countLabel').textContent='items in package';
    document.getElementById('countLabel').className='count-label';
    document.getElementById('countItems').innerHTML='';
    document.getElementById('countFoot').textContent='If an item is missing — set the package aside';
    document.getElementById('countFoot').className='count-foot';
    ov.classList.add('on');

    fetch('/api/shipment/'+encodeURIComponent(tracking)).then(function(r){return r.json()}).then(function(d){
        if(!d.ok){
            // Order not in system — still show the overlay so the packer knows to verify manually
            document.getElementById('countBuyer').textContent=t('ordernotfound');
            document.getElementById('countBig').textContent='?';
            document.getElementById('countLabel').textContent='unknown — verify by hand';
            document.getElementById('countLabel').className='count-label warn';
            document.getElementById('countItems').innerHTML='';
            document.getElementById('countFoot').textContent='⚠️ Not in current imports';
            document.getElementById('countFoot').className='count-foot warn';
            // Side card with a warning state
            document.getElementById('rsCount').textContent='?';
            document.getElementById('rsBuyer').textContent='(not in system)';
            document.getElementById('rsList').innerHTML='';
            document.getElementById('rsShow').innerHTML='';
            side.classList.add('warn');
            countTimer=setTimeout(function(){ov.classList.remove('on');side.classList.add('on')},8000);
            return;
        }
        var s=d.shipment, items=d.items||[];
        if(s.status==='cancelled'){
            ov.classList.remove('on');
            showCancelAlert(s.buyer_name||s.buyer_username||'(unknown)', s.flag_reason||'Order was cancelled');
            return;
        }

        // Active items only (skip cancelled lines for the count)
        var active=items.filter(function(it){return !it.cancelled});
        var totalQty=active.reduce(function(sum,it){return sum+(it.quantity||1)},0);
        var buyer=s.buyer_name||s.buyer_username||'Customer';
        var safeBuyer=buyer.replace(/&/g,'&amp;').replace(/</g,'&lt;');

        // ── Stage 1: big overlay ─────────────────────────────
        document.getElementById('countBuyer').innerHTML='Buyer: <b>'+safeBuyer+'</b>';
        document.getElementById('countBig').textContent=totalQty;
        document.getElementById('countLabel').textContent=(totalQty===1?t('iteminpkg'):t('itemsinpkg'));
        document.getElementById('countLabel').className='count-label';
        document.getElementById('countItems').innerHTML=items.map(function(it){
            var cls='count-item'+(it.cancelled?' cancelled':'');
            return '<div class="'+cls+'">'+
                '<div class="ci-sku">'+(it.sku||'?').toString().replace(/</g,'&lt;')+'</div>'+
                '<div class="ci-name">'+renderProductNameHtml(it.product_name||'')+(it.cancelled?' · CANCELLED':'')+'</div>'+
                '<div class="ci-qty">×'+(it.quantity||1)+'</div>'+
            '</div>';
        }).join('');
        if(items.length===0){
            document.getElementById('countFoot').textContent='⚠️ No items registered — verify manually';
            document.getElementById('countFoot').className='count-foot warn';
        } else if(s.status==='picked' && s.picked_by){
            var when=s.picked_at?' '+(s.picked_at.replace('T',' ').slice(0,16)):'';
            document.getElementById('countFoot').textContent=t('prepicked')+' '+s.picked_by+when+' '+t('justverify');
            document.getElementById('countFoot').className='count-foot';
        } else {
            document.getElementById('countFoot').textContent=t('countbox');
            document.getElementById('countFoot').className='count-foot';
        }

        // ── Stage 2: side reminder ───────────────────────────
        document.getElementById('rsCount').textContent=totalQty;
        document.getElementById('rsBuyer').textContent=buyer;
        document.getElementById('rsList').innerHTML=items.map(function(it){
            var cls='rs-item'+(it.cancelled?' cancelled':'');
            return '<div class="'+cls+'">'+
                '<div class="rs-sku">'+(it.sku||'?').toString().replace(/</g,'&lt;')+'</div>'+
                '<div class="rs-name">'+renderProductNameHtml(it.product_name||'')+'</div>'+
                '<div class="rs-qty">×'+(it.quantity||1)+'</div>'+
            '</div>';
        }).join('');
        side.classList.remove('warn');
        if(d.giveaways&&d.giveaways.length){
            document.getElementById('rsList').innerHTML+=d.giveaways.map(function(g){
                return '<div class="rs-item" style="background:rgba(52,211,153,.14);border:1px solid rgba(52,211,153,.45)">'+
                    '<div class="rs-sku">🎁</div>'+
                    '<div class="rs-name"><b>GIVEAWAY</b> · '+(g.prize_name||"").replace(/</g,"&lt;")+' — get from manager</div>'+
                    '<div class="rs-qty">+1</div></div>';
            }).join('');
        }
        document.getElementById('rsShow').innerHTML=s.import_label?('Show: <b>'+s.import_label.replace(/</g,'&lt;')+'</b>'+(s.platform?' · '+s.platform:'')):'';

        // Giveaway piggyback: if this order has a prize waiting to be added, pop a
        // must-acknowledge overlay so the packer puts it in the box before sealing.
        if(d.giveaways&&d.giveaways.length){showGiveawayAdd(d.giveaways);}

        // After 8 seconds, hide overlay, slide in side card. Stays until next scan / scan-out.
        countTimer=setTimeout(function(){
            ov.classList.remove('on');
            side.classList.add('on');
        },8000);
    }).catch(function(){
        document.getElementById('countBuyer').textContent='—';
        document.getElementById('countBig').textContent='?';
        document.getElementById('countLabel').textContent='lookup failed';
        document.getElementById('countLabel').className='count-label warn';
        document.getElementById('countFoot').textContent='⚠️ Could not reach server — record anyway';
        document.getElementById('countFoot').className='count-foot warn';
        countTimer=setTimeout(function(){ov.classList.remove('on')},8000);
    });
}

function showCancelAlert(buyer,reason){
    hideReminder();
    document.getElementById('cancelBuyer').textContent=buyer;
    document.getElementById('cancelReason').textContent=reason;
    document.getElementById('cancelOverlay').style.display='flex';
    // Stop the recording immediately — we will NOT save this
    if(mr&&mr.state==='recording'){try{mr.stop()}catch(e){}}
    stopTmr();
}
document.getElementById('cancelOk').addEventListener('click',function(){
    document.getElementById('cancelOverlay').style.display='none';
    hideReminder();
    go('r');
});
// ── Giveaway piggyback overlay (packer) ──
var gvPending=[];
function showGiveawayAdd(list){
    gvPending=list||[];
    document.getElementById('gvList').innerHTML=gvPending.map(function(g){
        return '🎁 '+(g.prize_name||'').replace(/</g,'&lt;')+(g.winner_username?' · for @'+g.winner_username:'')+(g.brand?' · '+g.brand:'');
    }).join('<br>');
    document.getElementById('giveawayOverlay').style.display='flex';
}
document.getElementById('gvOk').addEventListener('click',function(){
    document.getElementById('giveawayOverlay').style.display='none';
    gvPending.forEach(function(g){
        fetch('/api/giveaway/'+g.id+'/mark-added',{method:'POST'}).catch(function(){});
    });
    gvPending=[];
    if(st==='c')ri.focus();
});
function stopRec(){return new Promise(function(res){mr.onstop=res;mr.stop()})}
function capPhoto(){var v=document.getElementById('pv'),c=document.createElement('canvas');c.width=v.videoWidth;c.height=v.videoHeight;c.getContext('2d').drawImage(v,0,0);return new Promise(function(res){c.toBlob(res,'image/jpeg',.7)})}
function upload(){go('u');var dur=Math.round((Date.now()-t0)/1000);var vb=new Blob(ch,{type:'video/webm'});
capPhoto().then(function(pb){var fd=new FormData();fd.append('tracking',ct);fd.append('station','__SID__');fd.append('duration',dur);fd.append('video',vb,ct+'.webm');if(pb)fd.append('photo',pb,ct+'.jpg');
return fetch('/api/upload',{method:'POST',body:fd})}).then(function(r){return r.json()}).then(function(d){
if(d.ok){n++;document.getElementById('cn').textContent=n;document.getElementById('dkk').textContent=ct;document.getElementById('ddd').textContent='Duration: '+dur+'s';go('d');setTimeout(function(){go('r')},3000)}
else{alert('Failed');go('r')}}).catch(function(){alert('Upload failed');go('r')})}
// USPS labels carry "service + ZIP + tracking" in the barcode (up to ~33 digits)
// but humans only see the 22-digit tracking. Strip the prefix on entry so the
// recording, the upload payload, and the CSV log all carry the clean 22-digit code.
function normTrk(s){s=(s||'').trim();if(/^\d{23,40}$/.test(s))return s.slice(-22);return s}
mi.addEventListener('keydown',function(e){if(e.key==='Enter'){var t=normTrk(mi.value);if(t)startRec(t)}});
ri.addEventListener('keydown',function(e){if(e.key!=='Enter')return;var t=normTrk(ri.value);if(!t)return;stopTmr();
hideReminder();
if(t===ct){stopRec().then(upload)}else{stopRec().then(upload).then(function(){setTimeout(function(){startRec(t)},500)})}});
function startTmr(){stopTmr();ti=setInterval(function(){var s=Math.floor((Date.now()-t0)/1000);document.getElementById('rmm').textContent=String(Math.floor(s/60)).padStart(2,'0')+':'+String(s%60).padStart(2,'0')},200)}
function stopTmr(){if(ti){clearInterval(ti);ti=null}}
</script></body></html>'''

# ── DASHBOARD ─────────────────────────────────────────────
DASH_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Search Recordings</title>
__NAVBAR_CSS__
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#ffffff;color:#1a2130;min-height:100vh}
.page-hdr{padding:24px 28px 8px;display:flex;align-items:center;justify-content:space-between;max-width:1600px;margin:0 auto;flex-wrap:wrap;gap:12px}
.page-title{display:flex;align-items:center;gap:10px;font-size:20px;font-weight:800}
.page-title-icon{width:36px;height:36px;background:linear-gradient(135deg,#4f46e5,#7c3aed);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px}
.stat-pills{display:flex;gap:8px;flex-wrap:wrap}
.pill{display:flex;align-items:center;gap:6px;background:rgba(17,24,39,0.064);border:1px solid rgba(17,24,39,0.096);border-radius:20px;padding:6px 14px;font-size:12px;color:#6b7280}
.pill b{color:#4f46e5}

.search-area{padding:24px 28px 20px;max-width:720px;margin:0 auto}
.sb{display:flex;gap:10px}
.sb input{flex:1;background:#ffffff;border:2px solid rgba(17,24,39,0.096);border-radius:14px;padding:16px 20px;font-size:18px;color:#1a2130;font-family:inherit;outline:none;transition:all .2s}
.sb input:focus{border-color:#4f46e5;box-shadow:0 0 0 3px rgba(79,70,229,.1)}
.sb input::placeholder{color:#6b7280}
.sb button{background:linear-gradient(135deg,#4f46e5,#7c3aed);border:none;border-radius:14px;padding:16px 28px;font-size:16px;font-weight:700;color:white;cursor:pointer;font-family:inherit;box-shadow:0 4px 16px rgba(79,70,229,.25);transition:all .15s}
.sb button:hover{transform:translateY(-1px)}

.content{padding:0 28px 40px;max-width:920px;margin:0 auto}
.rc{background:#ffffff;border:1px solid rgba(17,24,39,0.096);border-radius:16px;margin-bottom:16px;overflow:hidden;animation:fu .3s ease}
@keyframes fu{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
.rc-h{padding:16px 20px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid rgba(17,24,39,0.064)}
.rc-t{font-size:18px;font-weight:800;letter-spacing:.3px}
.rc-m{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.rc-m span{font-size:12px;color:#6b7280;background:rgba(17,24,39,0.064);padding:3px 10px;border-radius:8px}
.tag{padding:3px 10px;border-radius:8px;font-size:11px;font-weight:700}
.tag-s{background:rgba(245,158,11,.1);color:#b45309}
.tag-g{background:rgba(16,185,129,.1);color:#10b981}
.rc-b{padding:16px;display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:600px){.rc-b{grid-template-columns:1fr}}
.mb{border-radius:10px;overflow:hidden;background:#ffffff;border:1px solid rgba(17,24,39,0.064)}
.mb video,.mb img{width:100%;display:block}
.ml{padding:8px 14px;font-size:12px;color:#6b7280;border-top:1px solid rgba(17,24,39,0.064);display:flex;justify-content:space-between;align-items:center}
.dl-btn{color:#4f46e5;text-decoration:none;font-size:12px;font-weight:700;padding:4px 12px;border-radius:8px;background:rgba(79,70,229,.1);border:1px solid rgba(79,70,229,.2);transition:all .15s}
.dl-btn:hover{background:rgba(79,70,229,.2)}

.sec-t{font-size:15px;font-weight:700;color:#6b7280;margin:24px 0 12px;display:flex;align-items:center;gap:8px}
.tbl{width:100%;background:#ffffff;border:1px solid rgba(17,24,39,0.096);border-radius:14px;overflow:hidden}
.tbl table{width:100%;border-collapse:collapse}
.tbl th{background:rgba(17,24,39,0.032);padding:12px 16px;font-size:11px;font-weight:700;color:#6b7280;text-align:left;border-bottom:1px solid rgba(17,24,39,0.064);text-transform:uppercase;letter-spacing:.4px}
.tbl td{padding:12px 16px;font-size:13px;border-bottom:1px solid rgba(17,24,39,0.048)}
.tbl tr:last-child td{border-bottom:none}
.tbl tr:hover td{background:rgba(79,70,229,.04)}
.tbl tr{cursor:pointer;transition:background .15s}
.tc{font-weight:700;color:#4f46e5}
.sn{font-weight:600;color:#b45309}
.wn{color:#6b7280}
.empty{text-align:center;padding:52px 20px;color:#6b7280}
.empty .ei{font-size:40px;margin-bottom:10px}
.empty .et{font-size:16px;font-weight:600;color:#1a2130}
.ld{text-align:center;padding:32px;color:#6b7280}
.spn{width:28px;height:28px;border:3px solid rgba(17,24,39,0.096);border-top-color:#4f46e5;border-radius:50%;animation:sp .8s linear infinite;margin:0 auto 8px}
@keyframes sp{to{transform:rotate(360deg)}}
.potm-wrap{max-width:1600px;margin:16px auto 0;padding:0 28px}
.potm-card{display:flex;align-items:center;gap:18px;padding:18px 24px;background:linear-gradient(135deg,rgba(251,191,36,.12),rgba(245,158,11,.04));border:1px solid rgba(251,191,36,.25);border-radius:16px;text-decoration:none;color:inherit;transition:transform .15s,border-color .15s}
.potm-card:hover{transform:translateY(-2px);border-color:rgba(251,191,36,.4)}
.potm-crown{font-size:42px;line-height:1;filter:drop-shadow(0 4px 8px rgba(251,191,36,.3))}
.potm-meta{flex:1}
.potm-label{font-size:11px;color:#b45309;text-transform:uppercase;letter-spacing:1px;font-weight:700;margin-bottom:2px}
.potm-name{font-size:20px;font-weight:800;color:#141b26;margin-bottom:2px}
.potm-stats{font-size:13px;color:#586274}
.potm-stats b{color:#1a2130;font-weight:700}
.potm-cta{color:#b45309;font-size:13px;font-weight:700;padding:8px 14px;border:1px solid rgba(251,191,36,.3);border-radius:10px}
@media(max-width:600px){.potm-cta{display:none}}
</style></head><body>
__NAVBAR__
<div class="potm-wrap" id="potmWrap" style="display:none"><a href="/leaderboard" class="potm-card"><div class="potm-crown">👑</div><div class="potm-meta"><div class="potm-label">Packer of the Month</div><div class="potm-name" id="potmName">—</div><div class="potm-stats"><b id="potmCount">0</b> packages · avg <b id="potmAvg">0s</b> · <b id="potmDays">0</b> active days</div></div><div class="potm-cta">View leaderboard →</div></a></div>
<div class="page-hdr">
<div class="page-title"><div class="page-title-icon">🔍</div>Search Recordings</div>
<div class="stat-pills"><div class="pill">🎥 <b id="sv">-</b></div><div class="pill">📸 <b id="sph">-</b></div><div class="pill">💾 <b id="ss">-</b></div></div>
</div>
<div class="search-area"><div class="sb"><input type="text" id="si" placeholder="Enter tracking number..." autofocus><button id="searchBtn">Search</button></div></div>
<div class="content"><div id="res"></div><div class="sec-t">🕐 Recent Recordings</div><div id="rl"><div class="ld"><div class="spn"></div>Loading...</div></div></div>
<script>
var si=document.getElementById('si');
si.addEventListener('keydown',function(e){if(e.key==='Enter')doSearch()});
document.getElementById('searchBtn').addEventListener('click',doSearch);

function doSearch(){
    var q=si.value.trim();if(!q)return;
    document.getElementById('res').innerHTML='<div class="ld"><div class="spn"></div>Searching...</div>';
    fetch('/api/search/'+encodeURIComponent(q)).then(function(r){return r.json()}).then(function(d){
        if(!d.videos.length&&!d.photos.length){document.getElementById('res').innerHTML='<div class="empty"><div class="ei">🔍</div><div class="et">No results for '+d.tracking+'</div></div>';return}
        var h='';
        for(var i=0;i<d.videos.length;i++){
            var v=d.videos[i],p=d.photos[i]||null,l=d.log[i]||null;
            h+='<div class="rc"><div class="rc-h"><span class="rc-t"><a href="https://tools.usps.com/go/TrackConfirmAction?tLabels='+encodeURIComponent(d.tracking)+'" target="_blank" rel="noopener" style="color:inherit;text-decoration:underline" title="Track on USPS.com">'+d.tracking+' ↗</a></span><div class="rc-m">';
            if(l){h+='<span>'+l.date+'</span><span>'+l.duration_seconds+'s</span>'}
            if(l&&l.worker)h+='<span>👤 '+l.worker+'</span>';
            h+='<span class="tag tag-s">'+v.station+'</span><span class="tag tag-g">✓ Found</span>';
            h+='</div></div><div class="rc-b"><div class="mb"><video controls preload="metadata"><source src="'+v.url+'" type="video/webm"></video><div class="ml"><span>🎥 Video'+(v.size_mb?(' · '+v.size_mb+' MB'):'')+'</span><a href="'+v.url+'" download class="dl-btn">⬇ Download</a></div></div>';
            if(p)h+='<div class="mb"><img src="'+p.url+'"><div class="ml">📸 Photo</div></div>';
            h+='</div></div>';
        }
        document.getElementById('res').innerHTML=h;
    });
}

function loadRecent(){
    fetch('/api/recent').then(function(r){return r.json()}).then(function(d){
        if(!d.length){document.getElementById('rl').innerHTML='<div class="empty"><div class="ei">📭</div><div class="et">No recordings yet</div></div>';return}
        var rows='';
        d.forEach(function(r){
            rows+='<tr data-t="'+r.tracking_number+'"><td class="tc">'+r.tracking_number+' <a href="https://tools.usps.com/go/TrackConfirmAction?tLabels='+encodeURIComponent(r.tracking_number)+'" target="_blank" rel="noopener" onclick="event.stopPropagation()" style="text-decoration:underline" title="Track on USPS.com">↗</a></td><td class="sn">'+(r.station||'-')+'</td><td class="wn">'+(r.worker||'-')+'</td><td>'+(r.date||'-')+'</td><td>'+(r.time||'-')+'</td><td>'+(r.duration_seconds||'-')+'s</td></tr>';
        });
        document.getElementById('rl').innerHTML='<div class="tbl"><table><thead><tr><th>Tracking</th><th>Station</th><th>Worker</th><th>Date</th><th>Time</th><th>Duration</th></tr></thead><tbody>'+rows+'</tbody></table></div>';
        document.querySelectorAll('tr[data-t]').forEach(function(row){
            row.addEventListener('click',function(){si.value=this.dataset.t;doSearch()});
        });
    });
}

function loadStats(){
    fetch('/api/stats').then(function(r){return r.json()}).then(function(d){
        document.getElementById('sv').textContent=d.total_videos;
        document.getElementById('sph').textContent=d.total_photos;
        document.getElementById('ss').textContent=d.total_size_mb+' MB';
    });
}
function loadPOTM(){
    fetch('/api/packer-of-month').then(function(r){return r.json()}).then(function(d){
        if(!d||!d.name)return;
        document.getElementById('potmName').textContent=d.name;
        document.getElementById('potmCount').textContent=d.count;
        document.getElementById('potmAvg').textContent=(d.avg_dur||0)+'s';
        document.getElementById('potmDays').textContent=d.days;
        document.getElementById('potmWrap').style.display='block';
    });
}
function esc(s){var d=document.createElement('div');d.textContent=(s==null?'':String(s));return d.innerHTML}
function filterByWorkerDay(){
    var p=new URLSearchParams(location.search);
    var w=p.get('worker'),dt=p.get('date');
    if(!w&&!dt)return false;
    document.getElementById('res').innerHTML='<div class="ld"><div class="spn"></div>Loading recordings…</div>';
    fetch('/api/recordings?worker='+encodeURIComponent(w||'')+'&date='+encodeURIComponent(dt||'')).then(function(r){return r.json()}).then(function(d){
        if(!d||!d.ok){document.getElementById('res').innerHTML='<div class="empty"><div class="ei">⚠️</div><div class="et">Could not load recordings</div></div>';return}
        var head='<div class="rc" style="animation:none"><div class="rc-h"><span class="rc-t">🎥 '+esc(w||'All')+(dt?(' · '+esc(dt)):'')+'</span><div class="rc-m"><span>'+d.count+' recordings</span><a href="/dashboard" style="font-size:12px;color:#4f46e5;font-weight:700;text-decoration:none">✕ Clear filter</a></div></div></div>';
        if(!d.items.length){document.getElementById('res').innerHTML=head+'<div class="empty"><div class="ei">📭</div><div class="et">No recordings for this packer on this day</div></div>';return}
        var h=head;
        d.items.forEach(function(v){
            h+='<div class="rc"><div class="rc-h"><span class="rc-t">'+esc(v.tracking||'—')+'</span><div class="rc-m"><span>'+esc(v.time||'')+'</span><span>'+esc(v.duration_seconds||'0')+'s</span>'+(v.station?('<span class="tag tag-s">'+esc(v.station)+'</span>'):'')+'</div></div>';
            if(v.video_url){h+='<div class="rc-b"><div class="mb"><video controls preload="metadata"><source src="'+esc(v.video_url)+'" type="video/webm"></video><div class="ml"><span>🎥 Video</span><a href="'+esc(v.video_url)+'" download class="dl-btn">⬇ Download</a></div></div>'+(v.photo_url?('<div class="mb"><img src="'+esc(v.photo_url)+'"><div class="ml">📸 Photo</div></div>'):'')+'</div>';}
            h+='</div>';
        });
        document.getElementById('res').innerHTML=h;
        var st=document.querySelector('.sec-t');if(st)st.textContent='🕐 All recent recordings';
    }).catch(function(){document.getElementById('res').innerHTML='<div class="empty"><div class="ei">⚠️</div><div class="et">Could not load recordings</div></div>';});
    return true;
}
filterByWorkerDay();
loadRecent();
loadStats();loadPOTM();
</script></body></html>'''

# ── USERS MANAGEMENT ──────────────────────────────────────
USERS_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Manage Users</title>
__NAVBAR_CSS__
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#ffffff;color:#1a2130;min-height:100vh}
.upage{padding:24px 28px;max-width:760px;margin:0 auto}
h1{font-size:24px;font-weight:800;margin-bottom:24px}
.card{background:#ffffff;border:1px solid rgba(17,24,39,0.096);border-radius:16px;padding:24px;margin-bottom:20px}
.card h2{font-size:14px;font-weight:700;color:#6b7280;margin-bottom:16px;text-transform:uppercase;letter-spacing:.5px}
table{width:100%;border-collapse:collapse}
th{text-align:left;padding:10px 12px;font-size:11px;font-weight:700;color:#6b7280;border-bottom:1px solid rgba(17,24,39,0.064);text-transform:uppercase;letter-spacing:.3px}
td{padding:12px;font-size:14px;border-bottom:1px solid rgba(17,24,39,0.048)}
tr:last-child td{border-bottom:none}
tr:hover td{background:rgba(79,70,229,.03)}
.role{padding:4px 10px;border-radius:8px;font-size:11px;font-weight:700;display:inline-block}
.r-admin{background:rgba(99,102,241,.1);color:#4f46e5}
.r-worker{background:rgba(245,158,11,.1);color:#b45309}
.r-cs{background:rgba(16,185,129,.1);color:#10b981}
.actions{display:flex;gap:6px;flex-wrap:wrap}
.act-btn{border:none;padding:6px 14px;border-radius:8px;font-size:12px;font-weight:600;cursor:pointer;font-family:inherit;transition:all .15s}
.act-pw{background:rgba(79,70,229,.1);color:#4f46e5;border:1px solid rgba(79,70,229,.2)}
.act-pw:hover{background:rgba(79,70,229,.2)}
.act-del{background:rgba(244,63,94,.08);color:#f43f5e;border:1px solid rgba(244,63,94,.2)}
.act-del:hover{background:rgba(244,63,94,.15)}
.add-form{display:grid;grid-template-columns:1fr 1fr;gap:10px}
@media(max-width:500px){.add-form{grid-template-columns:1fr}}
.add-form input,.add-form select{background:#ffffff;border:1.5px solid rgba(17,24,39,0.096);border-radius:10px;padding:12px 14px;color:#1a2130;font-size:14px;font-family:inherit;outline:none;transition:all .2s}
.add-form input:focus,.add-form select:focus{border-color:#4f46e5}
.add-form input::placeholder{color:#6b7280}
.add-form select{cursor:pointer}
.add-btn{grid-column:1/-1;background:linear-gradient(135deg,#10b981,#059669);border:none;border-radius:10px;padding:13px;color:white;font-weight:700;cursor:pointer;font-family:inherit;font-size:14px;margin-top:4px;transition:all .15s}
.add-btn:hover{transform:translateY(-1px);box-shadow:0 4px 16px rgba(16,185,129,.25)}
.msg{font-size:13px;margin-top:10px;grid-column:1/-1;min-height:16px}
.msg.ok{color:#10b981}.msg.err{color:#f43f5e}
</style></head><body>
__NAVBAR__
<div class="upage">
<h1>👥 User Management</h1>
<div class="card"><h2>Current Users</h2><table><thead><tr><th>Username</th><th>Name</th><th>Role</th><th>Actions</th></tr></thead><tbody id="ut"></tbody></table></div>
<div class="card"><h2>Add New User</h2>
<div class="add-form">
<input type="text" id="nu" placeholder="Username">
<input type="password" id="np" placeholder="Password">
<input type="text" id="nn" placeholder="Display Name">
<select id="nr"><option value="worker">Worker</option><option value="picker">Picker</option><option value="cs">Customer Service</option><option value="host">Live Show Host</option><option value="assistant">Show Assistant</option><option value="admin">Admin</option></select>
<button class="add-btn" id="addBtn">+ Add User</button>
<div style="flex-basis:100%;margin-top:8px;font-size:13px;color:#6b7280">Also does (optional — for people with more than one job):
  <label style="margin-left:8px"><input type="checkbox" class="xrole" value="picker"> Picker</label>
  <label style="margin-left:8px"><input type="checkbox" class="xrole" value="worker"> Worker</label>
  <label style="margin-left:8px"><input type="checkbox" class="xrole" value="cs"> CS</label>
  <label style="margin-left:8px"><input type="checkbox" class="xrole" value="host"> Host</label>
  <label style="margin-left:8px"><input type="checkbox" class="xrole" value="assistant"> Assistant</label>
</div>
<div class="msg" id="am"></div>
</div></div>
<script>
function loadUsers(){
    fetch('/api/users').then(function(r){return r.json()}).then(function(d){
        var rows='';
        Object.keys(d).forEach(function(k){
            var v=d[k];
            var rc=v.role==='admin'?'r-admin':v.role==='cs'?'r-cs':'r-worker';
            var xr=(v.extra_roles||[]).map(function(r){return '<span class="role r-worker" style="opacity:.7;margin-left:4px">+'+r+'</span>'}).join('');
            rows+='<tr><td><b>'+k+'</b></td><td>'+v.name+'</td><td><span class="role '+rc+'">'+v.role+'</span>'+xr+'</td><td>';
            rows+='<div class="actions"><button class="act-btn" data-u="'+k+'" data-a="roles">Edit Roles</button>';
            if(k!=='admin'){
                rows+='<button class="act-btn act-pw" data-u="'+k+'" data-a="pw">Change Password</button><button class="act-btn act-del" data-u="'+k+'" data-a="del">Delete</button>';
            }
            rows+='</div></td></tr>';
        });
        document.getElementById('ut').innerHTML=rows;
        USERS=d;
        document.querySelectorAll('[data-a="pw"]').forEach(function(b){
            b.addEventListener('click',function(){changePw(this.dataset.u)});
        });
        document.querySelectorAll('[data-a="del"]').forEach(function(b){
            b.addEventListener('click',function(){delUser(this.dataset.u)});
        });
        document.querySelectorAll('[data-a="roles"]').forEach(function(b){
            b.addEventListener('click',function(){editRoles(this.dataset.u)});
        });
    });
}
document.getElementById('addBtn').addEventListener('click',function(){
    var u=document.getElementById('nu').value.trim();
    var p=document.getElementById('np').value;
    var n=document.getElementById('nn').value.trim()||u;
    var rl=document.getElementById('nr').value;
    var extra=[];document.querySelectorAll('.xrole:checked').forEach(function(x){if(x.value!==rl)extra.push(x.value)});
    var m=document.getElementById('am');
    if(!u||!p){m.className='msg err';m.textContent='Username and password are required';return}
    fetch('/api/users/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p,name:n,role:rl,extra_roles:extra})})
    .then(function(r){return r.json()}).then(function(d){
        if(d.ok){m.className='msg ok';m.textContent='User added successfully!';loadUsers();document.getElementById('nu').value='';document.getElementById('np').value='';document.getElementById('nn').value='';document.querySelectorAll('.xrole').forEach(function(x){x.checked=false})}
        else{m.className='msg err';m.textContent=d.error||'Failed to add user'}
    });
});
function delUser(u){
    if(!confirm('Are you sure you want to delete "'+u+'"?'))return;
    fetch('/api/users/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u})})
    .then(function(){loadUsers()});
}
function changePw(u){
    var p=prompt('Enter new password for "'+u+'":');
    if(!p)return;
    fetch('/api/users/pw',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p})})
    .then(function(r){return r.json()}).then(function(d){alert(d.ok?'Password changed!':'Failed')});
}
var USERS={};
var ALL_ROLES=[['worker','Worker'],['picker','Picker'],['cs','Customer Service'],['host','Live Show Host'],['assistant','Show Assistant'],['admin','Admin']];
function editRoles(u){
    var v=USERS[u]||{};var cur=v.role||'worker';var ex=v.extra_roles||[];
    var ov=document.createElement('div');
    ov.style.cssText='position:fixed;inset:0;background:rgba(0,0,0,.55);display:flex;align-items:center;justify-content:center;z-index:9999';
    var primOpts=ALL_ROLES.map(function(r){return '<option value="'+r[0]+'"'+(r[0]===cur?' selected':'')+'>'+r[1]+'</option>'}).join('');
    var extOpts=ALL_ROLES.filter(function(r){return r[0]!=='admin'}).map(function(r){
        return '<label style="display:inline-flex;gap:5px;align-items:center;margin:4px 12px 4px 0;font-size:14px"><input type="checkbox" class="er" value="'+r[0]+'"'+(ex.indexOf(r[0])>=0?' checked':'')+'> '+r[1]+'</label>'}).join('');
    ov.innerHTML='<div style="background:#fff;border-radius:14px;padding:22px;max-width:440px;width:92%;font-family:inherit">'+
        '<h3 style="margin:0 0 14px;font-size:17px">Roles — '+u+'</h3>'+
        '<label style="font-size:12px;font-weight:700;color:#6b7280">Primary role</label>'+
        '<select id="erPrim" style="width:100%;padding:9px;border:2px solid #e4e7ec;border-radius:9px;margin:4px 0 14px;font-size:14px">'+primOpts+'</select>'+
        '<label style="font-size:12px;font-weight:700;color:#6b7280">Also does (extra roles)</label><div style="margin-top:6px">'+extOpts+'</div>'+
        '<div style="display:flex;gap:10px;justify-content:flex-end;margin-top:18px">'+
        '<button id="erCancel" style="padding:9px 16px;border:1px solid #e4e7ec;background:#f6f7f9;border-radius:9px;font-weight:700;cursor:pointer">Cancel</button>'+
        '<button id="erSave" style="padding:9px 16px;border:none;background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff;border-radius:9px;font-weight:700;cursor:pointer">Save</button></div></div>';
    document.body.appendChild(ov);
    ov.querySelector('#erCancel').onclick=function(){ov.remove()};
    ov.querySelector('#erSave').onclick=function(){
        var role=ov.querySelector('#erPrim').value;var extra=[];
        ov.querySelectorAll('.er:checked').forEach(function(x){if(x.value!==role)extra.push(x.value)});
        fetch('/api/users/roles',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,role:role,extra_roles:extra})})
          .then(function(r){return r.json()}).then(function(d){if(d.ok){ov.remove();loadUsers()}else alert(d.error||'Failed')});
    };
}
loadUsers();
</script></div></body></html>'''

# ── ANALYTICS PAGE ────────────────────────────────────────
ANALYTICS_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Analytics</title>
__NAVBAR_CSS__
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#ffffff;color:#1a2130;min-height:100vh}
.page-hdr{padding:24px 28px 8px;display:flex;align-items:center;gap:10px;max-width:1000px;margin:0 auto}
.page-title{display:flex;align-items:center;gap:10px;font-size:20px;font-weight:800}
.page-title-icon{width:36px;height:36px;background:linear-gradient(135deg,#b45309,#ef4444);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px}

.content{padding:0 28px 28px;max-width:1000px;margin:0 auto}

.big-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin-bottom:28px}
.big-stat{background:#ffffff;border:1px solid rgba(17,24,39,0.096);border-radius:16px;padding:24px;text-align:center}
.big-stat .num{font-size:42px;font-weight:900;line-height:1}
.big-stat .lbl{font-size:13px;color:#6b7280;margin-top:8px;font-weight:500}
.c-blue .num{color:#4f46e5}
.c-green .num{color:#10b981}
.c-orange .num{color:#b45309}
.c-pink .num{color:#f43f5e}

.sec{margin-bottom:28px}
.sec-t{font-size:17px;font-weight:800;margin-bottom:14px;display:flex;align-items:center;gap:8px}

.w-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px}
.w-card{background:#ffffff;border:1px solid rgba(17,24,39,0.096);border-radius:16px;padding:20px;transition:all .2s}
.w-card:hover{border-color:rgba(79,70,229,.2);background:#ffffff}
.w-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}
.w-name{font-size:18px;font-weight:800}
.w-badge{font-size:12px;font-weight:700;padding:4px 12px;border-radius:20px}
.w-active{background:rgba(16,185,129,.1);color:#10b981}
.w-idle{background:rgba(17,24,39,0.064);color:#6b7280}
.w-stats{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.w-stat{background:rgba(17,24,39,0.048);border-radius:10px;padding:12px;text-align:center}
.w-stat .val{font-size:24px;font-weight:800;color:#1a2130}
.w-stat .lab{font-size:11px;color:#6b7280;margin-top:2px;text-transform:uppercase;letter-spacing:.3px}
.w-stat.hl .val{color:#4f46e5}

.d-table{width:100%;background:#ffffff;border:1px solid rgba(17,24,39,0.096);border-radius:14px;overflow:hidden}
.d-table table{width:100%;border-collapse:collapse}
.d-table th{background:rgba(17,24,39,0.032);padding:12px 16px;font-size:11px;font-weight:700;color:#6b7280;text-align:left;border-bottom:1px solid rgba(17,24,39,0.064);text-transform:uppercase;letter-spacing:.4px}
.d-table td{padding:12px 16px;font-size:14px;border-bottom:1px solid rgba(17,24,39,0.048)}
.d-table tr:last-child td{border-bottom:none}
.d-table tr:hover td{background:rgba(79,70,229,.03)}
.d-table .today{background:rgba(79,70,229,.06)}
.d-table .today td{font-weight:700;color:#4f46e5}
.bar{height:6px;background:rgba(17,24,39,0.096);border-radius:3px;overflow:hidden;margin-top:4px}
.bar-fill{height:100%;border-radius:3px;background:linear-gradient(90deg,#4f46e5,#4f46e5)}

.ld{text-align:center;padding:40px;color:#6b7280}
.spn{width:28px;height:28px;border:3px solid rgba(17,24,39,0.096);border-top-color:#4f46e5;border-radius:50%;animation:sp .8s linear infinite;margin:0 auto 8px}
@keyframes sp{to{transform:rotate(360deg)}}
</style></head><body>
__NAVBAR__
<div class="page-hdr">
<div class="page-title"><div class="page-title-icon">📊</div>Analytics</div>
</div>

<div class="content">
<div class="big-stats" id="bigStats"><div class="ld"><div class="spn"></div>Loading...</div></div>

<div class="sec">
<div class="sec-t">👷 Worker Performance — Today</div>
<div class="w-grid" id="workerGrid"><div class="ld"><div class="spn"></div></div></div>
</div>

<div class="sec">
<div class="sec-t">📅 Daily Summary (Last 14 Days)</div>
<div id="dailyTable"><div class="ld"><div class="spn"></div></div></div>
</div>

<div class="sec" id="storageSection" style="display:none">
<div class="sec-t">💾 Storage</div>
<div class="w-grid" id="storageGrid"></div>
</div>
</div>

<script>
fetch('/api/analytics').then(function(r){return r.json()}).then(function(d){
    // Big stats
    var avgAll=0;
    if(d.workers.length){
        var totalSec=0,totalCount=0;
        d.workers.forEach(function(w){totalSec+=w.avg_seconds*w.total;totalCount+=w.total});
        avgAll=totalCount?Math.round(totalSec/totalCount):0;
    }
    document.getElementById('bigStats').innerHTML=
        '<div class="big-stat c-blue"><div class="num">'+d.total_today+'</div><div class="lbl">Packed Today</div></div>'+
        '<div class="big-stat c-green"><div class="num">'+d.total_all+'</div><div class="lbl">Total All Time</div></div>'+
        '<div class="big-stat c-orange"><div class="num">'+avgAll+'s</div><div class="lbl">Avg Pack Time</div></div>'+
        '<div class="big-stat c-pink"><div class="num">'+d.workers.length+'</div><div class="lbl">Total Workers</div></div>';

    // Worker cards
    if(!d.workers.length){
        document.getElementById('workerGrid').innerHTML='<div class="ld">No data yet</div>';
    } else {
        var maxToday=Math.max.apply(null,d.workers.map(function(w){return w.today}))||1;
        var cards='';
        d.workers.forEach(function(w){
            var active=w.today>0;
            cards+='<div class="w-card">'+
                '<div class="w-top"><div class="w-name">'+w.name+'</div><span class="w-badge '+(active?'w-active':'w-idle')+'">'+(active?'Active today':'Idle')+'</span></div>'+
                '<div class="w-stats">'+
                '<div class="w-stat hl"><div class="val">'+w.today+'</div><div class="lab">Today</div></div>'+
                '<div class="w-stat"><div class="val">'+w.avg_today+'s</div><div class="lab">Avg Today</div></div>'+
                '<div class="w-stat"><div class="val">'+w.total+'</div><div class="lab">All Time</div></div>'+
                '<div class="w-stat"><div class="val">'+w.avg_seconds+'s</div><div class="lab">Avg All</div></div>'+
                '</div>'+
                '<div class="bar"><div class="bar-fill" style="width:'+Math.round(w.today/maxToday*100)+'%"></div></div>'+
                '</div>';
        });
        document.getElementById('workerGrid').innerHTML=cards;
    }

    // Daily table
    if(!d.daily.length){
        document.getElementById('dailyTable').innerHTML='<div class="ld">No data yet</div>';
    } else {
        var maxDay=Math.max.apply(null,d.daily.map(function(dy){return dy.count}))||1;
        var rows='';
        d.daily.forEach(function(dy){
            var isToday=dy.date===d.date;
            rows+='<tr class="'+(isToday?'today':'')+'">'+
                '<td>'+(isToday?'📌 Today — ':'')+dy.date+'</td>'+
                '<td><b>'+dy.count+'</b> packages</td>'+
                '<td>'+dy.avg_seconds+'s avg</td>'+
                '<td><div class="bar"><div class="bar-fill" style="width:'+Math.round(dy.count/maxDay*100)+'%"></div></div></td>'+
                '</tr>';
        });
        document.getElementById('dailyTable').innerHTML=
            '<div class="d-table"><table><thead><tr><th>Date</th><th>Packages</th><th>Avg Time</th><th>Volume</th></tr></thead><tbody>'+rows+'</tbody></table></div>';
    }
});
fetch('/api/storage').then(function(r){return r.json()}).then(function(s){
    document.getElementById('storageSection').style.display='block';
    document.getElementById('storageGrid').innerHTML=
        '<div class="w-card"><div class="w-top"><div class="w-name">Videos</div></div><div class="w-stats"><div class="w-stat hl"><div class="val">'+s.videos+'</div><div class="lab">Files</div></div><div class="w-stat"><div class="val">'+s.video_size_mb+' MB</div><div class="lab">Size</div></div></div></div>'+
        '<div class="w-card"><div class="w-top"><div class="w-name">Photos</div></div><div class="w-stats"><div class="w-stat hl"><div class="val">'+s.photos+'</div><div class="lab">Files</div></div><div class="w-stat"><div class="val">'+s.photo_size_mb+' MB</div><div class="lab">Size</div></div></div></div>'+
        '<div class="w-card"><div class="w-top"><div class="w-name">Total Storage</div></div><div class="w-stats"><div class="w-stat hl"><div class="val">'+s.total_gb+' GB</div><div class="lab">Used</div></div><div class="w-stat"><div class="val">'+s.retention_days+' days</div><div class="lab">Retention</div></div></div></div>'+
        '<div class="w-card"><div class="w-top"><div class="w-name">Date Range</div></div><div class="w-stats"><div class="w-stat"><div class="val">'+(s.oldest||'-')+'</div><div class="lab">Oldest</div></div><div class="w-stat"><div class="val">'+(s.newest||'-')+'</div><div class="lab">Newest</div></div></div></div>';
}).catch(function(){});
</script></body></html>'''

# ══════════════════════════════════════════════════════════
# GIVEAWAY HTML TEMPLATES
# ══════════════════════════════════════════════════════════

GIVEAWAY_DASH_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Giveaway Manager</title>
__NAVBAR_CSS__
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#ffffff;color:#1a2130;min-height:100vh}
.page-hdr{padding:24px 28px 8px;display:flex;align-items:center;justify-content:space-between;max-width:1600px;margin:0 auto}
.page-title{font-size:22px;font-weight:800}
.page-title span{color:#4f46e5;margin-left:8px;font-weight:600;font-size:14px}
.wrap{max-width:1600px;margin:0 auto;padding:0 28px 28px}
.add-card{background:#ffffff;border:1px solid rgba(17,24,39,0.096);border-radius:16px;padding:20px 24px;margin-bottom:24px}
.add-title{font-size:14px;font-weight:700;color:#4f46e5;margin-bottom:14px;text-transform:uppercase;letter-spacing:.6px}
.add-row{display:grid;grid-template-columns:1fr 2fr 1fr 1fr auto;gap:12px;align-items:end}
.f label{display:block;font-size:11px;font-weight:700;color:#6b7280;margin-bottom:6px;text-transform:uppercase;letter-spacing:.5px}
.f input,.f select{width:100%;background:#ffffff;border:2px solid rgba(17,24,39,0.128);border-radius:10px;padding:11px 14px;font-size:14px;color:#1a2130;font-family:inherit;outline:none;transition:all .2s}
.f input:focus,.f select:focus{border-color:#4f46e5}
.btn{border:none;border-radius:10px;padding:11px 22px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit;transition:all .15s}
.btn-p{background:linear-gradient(135deg,#4f46e5,#7c3aed);color:white;box-shadow:0 4px 16px rgba(79,70,229,.3)}
.btn-p:hover{transform:translateY(-1px)}
.btn-s{background:rgba(17,24,39,0.128);color:#1a2130;border:1px solid rgba(17,24,39,0.16)}
.cols{display:grid;grid-template-columns:repeat(4,1fr);gap:18px}
.cols.cols3{grid-template-columns:repeat(3,1fr)}
.spendchip{display:inline-block;background:rgba(16,185,129,.14);color:#059669;font-weight:800;font-size:11px;padding:2px 9px;border-radius:50px;letter-spacing:.2px}
.daysleft{display:inline-block;background:rgba(245,158,11,.16);color:#b45309;font-weight:800;font-size:11px;padding:2px 9px;border-radius:50px}
.daysleft.urgent{background:rgba(244,63,94,.16);color:#e11d48}
@media(max-width:1100px){.cols{grid-template-columns:repeat(2,1fr)}.cols.cols3{grid-template-columns:repeat(2,1fr)}.add-row{grid-template-columns:1fr 1fr;}}
@media(max-width:640px){.cols{grid-template-columns:1fr}.add-row{grid-template-columns:1fr}}
.col{background:#ffffff;border:1px solid rgba(17,24,39,0.064);border-radius:14px;padding:16px;min-height:200px}
.col-h{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;padding-bottom:12px;border-bottom:1px solid rgba(17,24,39,0.08)}
.col-t{font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;display:flex;align-items:center;gap:8px}
.col.pa .col-t{color:#b45309}.col.ar .col-t{color:#2563eb}.col.lc .col-t{color:#7c3aed}.col.sh .col-t{color:#059669}
.cnt{font-size:11px;font-weight:700;background:rgba(17,24,39,0.08);padding:3px 9px;border-radius:50px;color:#6b7280}
.card{background:#ffffff;border:1px solid rgba(17,24,39,0.096);border-radius:10px;padding:14px;margin-bottom:10px;cursor:pointer;transition:all .15s;display:block;text-decoration:none;color:inherit}
.card:hover{transform:translateY(-1px);border-color:rgba(79,70,229,.4)}
.card-w{font-size:14px;font-weight:700;margin-bottom:4px}
.card-w .at{color:#6b7280;font-weight:400}
.card-p{font-size:13px;color:#4f46e5;margin-bottom:8px;line-height:1.4}
.card-m{display:flex;justify-content:space-between;align-items:center;font-size:11px;color:#6b7280}
.card-m .pl{padding:2px 8px;border-radius:50px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;font-size:10px}
.pl.tt{background:rgba(244,63,94,.15);color:#e11d48}
.pl.wn{background:rgba(245,158,11,.15);color:#b45309}
.empty{text-align:center;color:#6b7280;font-size:13px;padding:30px 10px;font-style:italic}
.toast{position:fixed;bottom:24px;right:24px;background:#10b981;color:white;padding:14px 22px;border-radius:10px;font-weight:600;box-shadow:0 10px 40px rgba(16,185,129,.4);z-index:100;display:none;animation:slideIn .3s}
.toast.err{background:#f43f5e;box-shadow:0 10px 40px rgba(244,63,94,.4)}
@keyframes slideIn{from{transform:translateX(120%)}to{transform:translateX(0)}}
</style></head><body>
__NAVBAR__
<div class="page-hdr"><div class="page-title">🎁 Giveaway Manager <span>__NAME__</span></div></div>
<div class="wrap">
<div class="add-card">
<div class="add-title">+ Add New Giveaway Winner</div>
<div class="add-row">
<div class="f"><label>Platform</label><select id="pl"><option value="tiktok">TikTok</option><option value="whatnot">Whatnot</option></select></div>
<div class="f"><label>Prize Name</label><input id="pn" placeholder="e.g. Sol for the soul GIVYYYY"></div>
<div class="f"><label>Winner Username</label><input id="wu" placeholder="e.g. jackiiealaniz"></div>
<div class="f"><label>Brand</label><select id="br"><option value="">-- Select --</option></select></div>
<button class="btn btn-p" id="add">Add Giveaway</button>
</div>
</div>

<div class="add-card" style="border-color:rgba(52,211,153,.25)">
<div class="add-title" style="color:#059669">🎁➕ Attach Prize to an Existing Order</div>
<div class="add-row" style="grid-template-columns:1.4fr 1fr 1fr 1.2fr auto">
<div class="f"><label>Prize Name</label><input id="a-prize" placeholder="e.g. Mini glow set"></div>
<div class="f"><label>First Name</label><input id="a-first" placeholder="First"></div>
<div class="f"><label>Last Name</label><input id="a-last" placeholder="Last"></div>
<div class="f"><label>Username</label><input id="a-user" placeholder="@username"></div>
<button class="btn btn-s" id="a-find">Find Order</button>
</div>
<div id="a-result" style="margin-top:14px;display:none"></div>
</div>

<div class="add-card" style="border-color:rgba(79,70,229,.25)">
<div class="add-title" style="color:#4f46e5">🔎 Look up a winner</div>
<div class="add-row" style="grid-template-columns:1.4fr auto">
<div class="f"><label>Winner username</label><input id="s-user" placeholder="@username — see spend + giveaway history"></div>
<button class="btn btn-s" id="s-find">Search</button>
</div>
<div id="s-result" style="margin-top:14px;display:none"></div>
</div>

<div class="cols cols3">
<div class="col pa"><div class="col-h"><div class="col-t">📋 Pending → Picking</div><div class="cnt" id="c-pending_pick">0</div></div><div id="g-pending_pick"></div></div>
<div class="col ar"><div class="col-h"><div class="col-t">⏳ No order yet</div><div class="cnt" id="c-no_order">0</div></div><div id="g-no_order"></div></div>
<div class="col lc"><div class="col-h"><div class="col-t">🏷️ Need to create a label</div><div class="cnt" id="c-need_label">0</div></div><div id="g-need_label"></div></div>
</div>
</div>
<div class="toast" id="t"></div>
<script>
function toast(m,e){var t=document.getElementById('t');t.textContent=m;t.className=e?'toast err':'toast';t.style.display='block';setTimeout(function(){t.style.display='none'},3000)}
function timeAgo(ts){if(!ts)return '';var d=new Date(ts);var s=Math.floor((Date.now()-d.getTime())/1000);if(s<60)return s+'s ago';if(s<3600)return Math.floor(s/60)+'m ago';if(s<86400)return Math.floor(s/3600)+'h ago';return Math.floor(s/86400)+'d ago'}
function esc(s){var d=document.createElement('div');d.textContent=(s==null?'':String(s));return d.innerHTML}
var STAGE={pending:'🕗 Awaiting pick',picked:'📋 Picked',packed:'📦 Packed',shipped:'🚚 Shipped',cancelled:'🚫 Cancelled',
    PRE_TRANSIT:'🚚 Shipped',IN_TRANSIT:'✈️ In transit',OUT_FOR_DELIVERY:'📬 Out for delivery',DELIVERED:'✅ Delivered',EXCEPTION:'⚠️ Exception',RETURNED:'↩️ Returned'};
function spendChip(g){
    var sp=g.lifetime_spend||0; var oc=g.lifetime_orders||0;
    if(sp>0)return '<span class="spendchip">💰 $'+Number(sp).toFixed(2)+' lifetime'+(oc?' · '+oc+' ord':'')+'</span>';
    if(oc>0)return '<span class="spendchip">'+oc+' order'+(oc>1?'s':'')+'</span>';
    return '<span class="spendchip" style="background:rgba(148,163,184,.16);color:#64748b">new customer</span>';
}
function card(g,stage){
    var pl=g.platform==='tiktok'?'<span class="pl tt">TikTok</span>':'<span class="pl wn">Whatnot</span>';
    var extra='';
    if(stage==='pending_pick'){
        var ast=g.attach_status==='added'
            ?'<span style="color:#059669;font-weight:700">✓ ADDED'+(g.attach_added_by?' · '+esc(g.attach_added_by):'')+'</span>'
            :'<span style="color:#b45309;font-weight:700">⏳ get from manager</span>';
        extra='<div style="font-size:13px;color:#475569;margin-bottom:2px">👤 '+esc(g.order_recipient||g.winner_username||'')+'</div>'+
            (g.order_address?'<div style="font-size:11px;color:#6b7280;margin-bottom:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">📍 '+esc(g.order_address)+'</div>':'')+
            '<div class="card-m"><span style="font-family:monospace;color:#4f46e5">📦 '+esc(g.order_tracking||g.linked_tracking||'')+'</span><span style="color:#475569;font-weight:600">'+(STAGE[g.order_status]||esc(g.order_status||''))+'</span></div>'+
            '<div class="card-m" style="margin-top:4px">'+ast+'</div>';
    } else if(stage==='no_order'){
        var dl=(g.days_left==null?4:g.days_left);
        var cls=dl<=1?'daysleft urgent':'daysleft';
        extra='<div class="card-m"><span style="color:#6b7280">⏳ waiting for their order</span>'+
              '<span class="'+cls+'">'+dl+' day'+(dl===1?'':'s')+' left</span></div>';
    } else if(stage==='need_label'){
        extra='<div class="card-m"><span style="color:#e11d48;font-weight:700">🏷️ No order arrived — create a label</span></div>';
    }
    return '<a class="card" href="/giveaway/'+g.id+'">'+
        '<div class="card-w"><span class="at">@</span>'+esc(g.winner_username)+' '+spendChip(g)+'</div>'+
        '<div class="card-p">🎁 '+esc(g.prize_name)+'</div>'+
        extra+
        '<div class="card-m" style="margin-top:8px">'+pl+'<span>'+timeAgo(g.created_at)+'</span></div>'+
        '</a>';
}
var attachPrizeName='';
function shipRow(s,best){
    var col={pending:'#b45309',picked:'#2563eb',packed:'#7c3aed'}[s.status]||'#6b7280';
    var hist=s.order_history?(' · '+s.order_history+' order'+(s.order_history>1?'s':'')+' in history'):'';
    var sp=(s.lifetime_spend>0)?(' <span class="spendchip">💰 $'+Number(s.lifetime_spend).toFixed(2)+' lifetime</span>'):'';
    return '<div class="card" style="cursor:default;border-color:'+(best?'rgba(52,211,153,.45)':'rgba(17,24,39,0.096)')+'">'+
        '<div class="card-w">'+esc(s.buyer_name||'?')+' <span class="at">@'+esc(s.buyer_username||'')+'</span>'+sp+'</div>'+
        '<div style="font-size:11px;color:#6b7280;margin:2px 0 6px">📍 '+esc(s.address_full||'—')+hist+'</div>'+
        '<div class="card-m"><span style="color:'+col+';font-weight:700;text-transform:uppercase">'+s.status+'</span>'+
        '<span>'+esc(s.import_label||'')+' · '+(s.total_items||0)+' items</span></div>'+
        '<div class="card-m" style="margin-top:8px"><span style="font-family:monospace">'+esc(s.tracking_code||s.shipment_id||'')+'</span>'+
        '<button class="btn btn-p" style="padding:6px 14px;font-size:12px" onclick="doAttach(\\''+s.shipment_id+'\\')">'+(best?'Attach here →':'Use this')+'</button></div>'+
        '</div>';
}
document.getElementById('a-find').addEventListener('click',function(){
    var prize=document.getElementById('a-prize').value.trim();
    var first=document.getElementById('a-first').value.trim();
    var last=document.getElementById('a-last').value.trim();
    var user=document.getElementById('a-user').value.trim().replace(/^@/,'');
    if(!prize){toast('Prize name required',true);return}
    if(!user&&!(first&&last)){toast('Enter username, or first + last name',true);return}
    attachPrizeName=prize;
    var box=document.getElementById('a-result');box.style.display='block';box.innerHTML='<div class="empty">Searching…</div>';
    fetch('/api/giveaway/match',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({username:user,first_name:first,last_name:last})})
    .then(function(r){return r.json()}).then(function(d){
        if(!d.ok){box.innerHTML='<div class="empty">'+esc(d.error||'Lookup failed')+'</div>';return}
        if(!d.candidates.length){
            var msg=d.reason==='all_shipped'
                ?'All matching orders already shipped — ship the prize separately using "Add New Giveaway Winner" above.'
                :'No matching order found in the pipeline for that winner.';
            box.innerHTML='<div class="empty">'+msg+'</div>';return;
        }
        var html='<div style="font-size:12px;color:#059669;font-weight:700;margin-bottom:8px">BEST MATCH (auto-selected) — confirm, or pick another:</div>';
        html+=d.candidates.map(function(s,i){return shipRow(s,i===0)}).join('');
        box.innerHTML=html;
    }).catch(function(e){box.innerHTML='<div class="empty">Request failed: '+esc(String(e))+'</div>'});
});
function doAttach(sid){
    fetch('/api/giveaway/attach',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({prize_name:attachPrizeName,shipment_id:sid,
            username:document.getElementById('a-user').value.trim().replace(/^@/,''),
            platform:document.getElementById('pl').value})})
    .then(function(r){return r.json()}).then(function(d){
        if(d.ok){
            toast('Attached to '+(d.linked.tracking_code||d.linked.shipment_id)+' ✓');
            ['a-prize','a-first','a-last','a-user'].forEach(function(id){document.getElementById(id).value=''});
            document.getElementById('a-result').style.display='none';load();
        } else toast(d.error||'Failed',true);
    });
}
function load(){
    fetch('/api/giveaway/list').then(function(r){return r.json()}).then(function(d){
        var br=document.getElementById('br');
        if(br.children.length===1){d.brands.forEach(function(b){var o=document.createElement('option');o.value=b;o.textContent=b;br.appendChild(o)})}
        ['pending_pick','no_order','need_label'].forEach(function(k){
            var arr=d.groups[k]||[];
            document.getElementById('c-'+k).textContent=arr.length;
            var html=arr.length?arr.map(function(g){return card(g,k)}).join(''):'<div class="empty">No giveaways here</div>';
            document.getElementById('g-'+k).innerHTML=html;
        });
    });
}
// ── Winner lookup (search + customer card) ──
var GVSTAGE={pending_pick:['#2563eb','📋 Pending → picking'],no_order:['#b45309','⏳ Waiting for order'],
    need_label:['#e11d48','🏷️ Needs a label'],done:['#059669','✅ Sent']};
function runSearch(){
    var u=document.getElementById('s-user').value.trim().replace(/^@/,'');
    var box=document.getElementById('s-result');box.style.display='block';
    if(!u){box.innerHTML='<div class="empty">Type a username to search.</div>';return}
    box.innerHTML='<div class="empty">Searching…</div>';
    fetch('/api/giveaway/search?username='+encodeURIComponent(u)).then(function(r){return r.json()}).then(function(d){
        if(!d.ok){box.innerHTML='<div class="empty">'+esc(d.error||'Search failed')+'</div>';return}
        var html='';
        if(d.card){
            html+='<div class="card" style="cursor:default;border-color:rgba(16,185,129,.4);background:rgba(16,185,129,.04)">'+
                '<div class="card-w">👤 '+esc(d.card.name||u)+' <span class="at">@'+esc(u)+'</span></div>'+
                '<div style="display:flex;gap:22px;margin-top:6px;flex-wrap:wrap">'+
                  '<div><div style="font-size:22px;font-weight:900;color:#059669">$'+Number(d.card.lifetime_spend||0).toFixed(2)+'</div><div style="font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px;font-weight:800">Lifetime spend</div></div>'+
                  '<div><div style="font-size:22px;font-weight:900;color:#141b26">'+(d.card.orders||0)+'</div><div style="font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px;font-weight:800">Orders</div></div>'+
                  (d.card.last_order?'<div><div style="font-size:16px;font-weight:800;color:#475569;padding-top:4px">'+esc((d.card.last_order||'').slice(0,10))+'</div><div style="font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px;font-weight:800">Last order</div></div>':'')+
                '</div></div>';
        } else {
            html+='<div style="font-size:12px;color:#6b7280;margin-bottom:8px">No store orders on record for this username yet.</div>';
        }
        if(d.giveaways.length){
            html+='<div style="font-size:12px;color:#6b7280;font-weight:700;margin:12px 0 6px">GIVEAWAY HISTORY ('+d.giveaways.length+')</div>';
            html+=d.giveaways.map(function(g){
                var st=GVSTAGE[g.stage]||['#6b7280',esc(g.stage||'')];
                return '<a class="card" href="/giveaway/'+g.id+'" style="padding:10px 12px">'+
                  '<div class="card-m"><span style="font-weight:700">🎁 '+esc(g.prize_name)+'</span>'+
                  '<span style="color:'+st[0]+';font-weight:700;font-size:11px">'+st[1]+'</span></div>'+
                  '<div class="card-m" style="margin-top:4px"><span style="color:#6b7280;font-size:11px">'+esc(g.brand||g.platform||'')+'</span><span>'+timeAgo(g.created_at)+'</span></div></a>';
            }).join('');
        } else {
            html+='<div class="empty">No giveaways for this winner.</div>';
        }
        box.innerHTML=html;
    }).catch(function(e){box.innerHTML='<div class="empty">Request failed: '+esc(String(e))+'</div>'});
}
document.getElementById('s-find').addEventListener('click',runSearch);
document.getElementById('s-user').addEventListener('keydown',function(e){if(e.key==='Enter')runSearch()});
document.getElementById('add').addEventListener('click',function(){
    var pn=document.getElementById('pn').value.trim();
    var wu=document.getElementById('wu').value.trim().replace(/^@/,'');
    var br=document.getElementById('br').value;
    var pl=document.getElementById('pl').value;
    if(!pn||!wu){toast('Prize and winner are required',true);return}
    fetch('/api/giveaway',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({prize_name:pn,winner_username:wu,brand:br,platform:pl})})
    .then(function(r){return r.json()}).then(function(d){
        if(d.ok){toast('Added! ID #'+d.id);document.getElementById('pn').value='';document.getElementById('wu').value='';load()}
        else toast(d.error||'Failed',true);
    });
});
['pn','wu'].forEach(function(id){document.getElementById(id).addEventListener('keydown',function(e){if(e.key==='Enter')document.getElementById('add').click()})});
load();
setInterval(load,30000);
</script></body></html>'''

GIVEAWAY_DETAIL_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Giveaway Detail</title>
__NAVBAR_CSS__
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#ffffff;color:#1a2130;min-height:100vh}
.page-hdr{padding:24px 28px 8px;display:flex;align-items:center;justify-content:space-between;max-width:900px;margin:0 auto}
.page-title{font-size:20px;font-weight:800}
.page-title-link{font-size:13px;color:#6b7280;text-decoration:none;padding:6px 14px;border-radius:8px;background:rgba(17,24,39,0.064)}
.page-title-link:hover{color:#4f46e5;background:rgba(17,24,39,0.128)}
.wrap{max-width:900px;margin:0 auto;padding:0 28px 28px}
.hdr{background:#ffffff;border:1px solid rgba(17,24,39,0.096);border-radius:16px;padding:24px 28px;margin-bottom:20px}
.hdr-top{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px}
.h-w{font-size:24px;font-weight:800;margin-bottom:4px}
.h-w .at{color:#6b7280;font-weight:400}
.h-p{font-size:16px;color:#4f46e5}
.status{padding:8px 18px;border-radius:50px;font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:.6px;white-space:nowrap}
.s-pa{background:rgba(251,191,36,.15);color:#b45309;border:1.5px solid rgba(251,191,36,.3)}
.s-ar{background:rgba(96,165,250,.15);color:#2563eb;border:1.5px solid rgba(96,165,250,.3)}
.s-lc{background:rgba(167,139,250,.15);color:#7c3aed;border:1.5px solid rgba(167,139,250,.3)}
.s-sh{background:rgba(52,211,153,.15);color:#059669;border:1.5px solid rgba(52,211,153,.3)}
.s-cl{background:rgba(244,63,94,.15);color:#e11d48;border:1.5px solid rgba(244,63,94,.3)}
.meta{display:flex;gap:18px;font-size:13px;color:#6b7280}
.meta b{color:#1a2130}
.section{background:#ffffff;border:1px solid rgba(17,24,39,0.096);border-radius:16px;padding:24px 28px;margin-bottom:20px}
.section h3{font-size:14px;font-weight:700;color:#4f46e5;margin-bottom:16px;text-transform:uppercase;letter-spacing:.6px}
.f{margin-bottom:14px}
.f label{display:block;font-size:11px;font-weight:700;color:#6b7280;margin-bottom:6px;text-transform:uppercase;letter-spacing:.5px}
.f input,.f select,.f textarea{width:100%;background:#ffffff;border:2px solid rgba(17,24,39,0.128);border-radius:10px;padding:11px 14px;font-size:14px;color:#1a2130;font-family:inherit;outline:none;transition:all .2s}
.f input:focus,.f select:focus,.f textarea:focus{border-color:#4f46e5}
.f textarea{resize:vertical;min-height:90px;line-height:1.5}
.row{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.row3{display:grid;grid-template-columns:2fr 1fr 1fr;gap:14px}
.btn{border:none;border-radius:10px;padding:12px 24px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit;transition:all .15s}
.btn-p{background:linear-gradient(135deg,#4f46e5,#7c3aed);color:white;box-shadow:0 4px 16px rgba(79,70,229,.3)}
.btn-p:hover{transform:translateY(-1px)}
.btn-s{background:rgba(16,185,129,.15);color:#059669;border:1.5px solid rgba(16,185,129,.3)}
.btn-s:hover{background:rgba(16,185,129,.25)}
.btn-d{background:rgba(244,63,94,.1);color:#e11d48;border:1.5px solid rgba(244,63,94,.2)}
.btn-d:hover{background:rgba(244,63,94,.2)}
.btn-ai{background:linear-gradient(135deg,#7c3aed,#ec4899);color:white;box-shadow:0 4px 16px rgba(167,139,250,.3)}
.btn-ai:hover{transform:translateY(-1px)}
.btn-ai:disabled{opacity:.5;cursor:not-allowed;transform:none}
.conf-badge{display:inline-block;padding:2px 9px;border-radius:50px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;margin-left:8px}
.conf-high{background:rgba(52,211,153,.15);color:#059669}
.conf-medium{background:rgba(251,191,36,.15);color:#b45309}
.conf-low{background:rgba(244,63,94,.15);color:#e11d48}
.btn-row{display:flex;gap:10px;flex-wrap:wrap;margin-top:16px}
.toast{position:fixed;bottom:24px;right:24px;background:#10b981;color:white;padding:14px 22px;border-radius:10px;font-weight:600;box-shadow:0 10px 40px rgba(16,185,129,.4);z-index:100;display:none}
.toast.err{background:#f43f5e}
.tip{background:rgba(79,70,229,.08);border:1px solid rgba(79,70,229,.2);border-radius:10px;padding:14px 18px;font-size:13px;color:#4f46e5;margin-bottom:14px;line-height:1.5}
.addr-display{background:#ffffff;border-radius:10px;padding:14px 18px;font-size:14px;line-height:1.7;color:#1a2130;margin-bottom:14px}
.addr-display b{color:#4f46e5}
.tracking{font-family:monospace;font-size:18px;color:#059669;font-weight:700;letter-spacing:1px}
</style></head><body>
__NAVBAR__
<div class="page-hdr"><div class="page-title">🎁 Giveaway #__GID__</div><a href="/giveaway" class="page-title-link">← Back to Giveaways</a></div>
<div class="wrap" id="wrap"><div style="text-align:center;padding:60px;color:#6b7280">Loading...</div></div>
<div class="toast" id="t"></div>
<script>
var GID=__GID__;var G=null;
function toast(m,e){var t=document.getElementById('t');t.textContent=m;t.className=e?'toast err':'toast';t.style.display='block';setTimeout(function(){t.style.display='none'},3000)}
function esc(s){var d=document.createElement('div');d.textContent=s||'';return d.innerHTML}
function statusLabel(s){var m={pending_address:['s-pa','📋 Pending Address'],address_received:['s-ar','✏️ Address Received'],label_created:['s-lc','📦 Label Created'],shipped:['s-sh','✅ Shipped'],cancelled:['s-cl','❌ Cancelled']};var v=m[s]||['s-pa',s];return '<span class="status '+v[0]+'">'+v[1]+'</span>'}
function fmt(ts){if(!ts)return '-';var d=new Date(ts);return d.toLocaleString()}

function render(){
    var g=G;
    var h='<div class="hdr"><div class="hdr-top"><div><div class="h-w"><span class="at">@</span>'+esc(g.winner_username)+'</div><div class="h-p">'+esc(g.prize_name)+'</div></div>'+statusLabel(g.status)+'</div>'+
        '<div class="meta"><div>Platform: <b>'+(g.platform==='tiktok'?'TikTok':'Whatnot')+'</b></div>'+
        (g.brand?'<div>Brand: <b>'+esc(g.brand)+'</b></div>':'')+
        '<div>Created: <b>'+fmt(g.created_at)+'</b></div>'+
        (g.created_by?'<div>By: <b>'+esc(g.created_by)+'</b></div>':'')+
        '</div></div>';

    // Address section
    if(g.status==='pending_address'){
        h+='<div class="section"><h3>📥 Capture Address from DM</h3>'+
            '<div class="tip">💡 Paste the DM text below and click <b>✨ Parse with AI</b> to extract the address automatically. Then review and save.</div>'+
            '<div class="f"><label>DM Text from Winner</label><textarea id="dm" placeholder="Paste the DM here, e.g.: hi! my address is jane smith 123 main st apt 5 brooklyn ny 11201"></textarea></div>'+
            '<div class="btn-row" style="margin-bottom:18px"><button class="btn btn-ai" id="parseBtn">✨ Parse with AI</button>'+
            '<span id="parseStatus" style="align-self:center;font-size:13px;color:#6b7280"></span></div>'+
            addressForm({})+
            '<div class="btn-row"><button class="btn btn-p" id="saveAddr">Save Address</button>'+
            '<button class="btn btn-d" id="cancel">Cancel Giveaway</button></div></div>';
    } else if(g.status==='address_received'||g.status==='label_created'){
        h+='<div class="section"><h3>📍 Shipping Address</h3>'+
            addressDisplay(g)+
            '<details><summary style="cursor:pointer;color:#4f46e5;font-size:13px;margin-bottom:10px">✏️ Edit address</summary>'+
            addressForm(g)+
            '<button class="btn btn-p" id="saveAddr" style="margin-top:10px">Update Address</button></details></div>';
        h+='<div class="section"><h3>📦 Ship It</h3>'+
            '<div class="tip">🏷️ Buy a label here (EasyPost) — pick the cheapest carrier. Or enter a tracking number manually below.</div>'+
            '<div class="f"><label>Package preset</label><select id="pkgSel"><option value="">— custom —</option></select></div>'+
            '<div style="display:flex;gap:8px;align-items:flex-end"><div class="f" style="flex:1"><label>Package weight</label><input id="wt" type="number" step="0.01" placeholder="e.g. 6"></div><div class="f"><label>Unit</label><select id="wUnit"><option value="oz">oz</option><option value="lb">lb</option></select></div></div>'+
            '<div style="display:flex;gap:8px"><div class="f" style="flex:1"><label>L (in)</label><input id="ln" type="number" step="0.1"></div><div class="f" style="flex:1"><label>W (in)</label><input id="wd" type="number" step="0.1"></div><div class="f" style="flex:1"><label>H (in)</label><input id="ht" type="number" step="0.1"></div></div>'+
            '<button class="btn btn-p" id="getRates">Get rates →</button>'+
            '<div id="ratesBox" style="margin-top:12px"></div>'+
            '<details style="margin-top:14px"><summary style="cursor:pointer;color:#4f46e5;font-size:13px">✏️ Or enter a tracking number manually</summary>'+
            '<div class="f" style="margin-top:8px"><label>Tracking Number</label><input id="trk" placeholder="e.g. 9400111202533112341234"></div>'+
            '<div class="f"><label>Notes (optional)</label><textarea id="nt" placeholder="Any notes about this shipment..."></textarea></div>'+
            '<button class="btn btn-s" id="ship">Mark as Shipped</button></details>'+
            '<div class="btn-row" style="margin-top:12px"><button class="btn btn-d" id="cancel">Cancel Giveaway</button></div></div>';
    } else if(g.status==='shipped'){
        h+='<div class="section"><h3>📍 Shipped to</h3>'+addressDisplay(g)+'</div>';
        h+='<div class="section"><h3>✅ Shipment</h3>'+
            '<div class="addr-display"><b>Tracking:</b> <span class="tracking">'+esc(g.tracking_number||'-')+'</span><br>'+
            '<b>Shipped at:</b> '+fmt(g.shipped_at)+'</div>'+
            (g.shippo_label_url?'<button class="btn btn-s" style="margin-top:8px" onclick="window.open(\\'/label/giveaway/\\'+GID,\\'_blank\\')">🖨️ Print label (4×6)</button>':'')+
            (g.filmed_at?'<div class="tip" style="margin-top:8px">📹 Packing filmed by '+esc(g.filmed_by||'')+' · '+fmt(g.filmed_at)+'</div>':(g.shippo_label_url?'<div class="tip" style="margin-top:8px">📹 Scan this label\\'s tracking on the packing screen to film it.</div>':''))+
            (g.notes?'<div class="f"><label>Notes</label><textarea id="nt" readonly>'+esc(g.notes)+'</textarea></div>':'')+
            '<div class="tip">⚠️ Don\\'t forget to mark this as sent in TikTok/Whatnot too!</div></div>';
    } else if(g.status==='cancelled'){
        h+='<div class="section"><h3>❌ Cancelled</h3><div class="tip">This giveaway was cancelled.</div></div>';
    }
    document.getElementById('wrap').innerHTML=h;
    bindEvents();
    if(g.dm_text&&document.getElementById('dm'))document.getElementById('dm').value=g.dm_text;
}
function addressDisplay(g){
    var s2=g.address_street2?'<br>'+esc(g.address_street2):'';
    return '<div class="addr-display"><b>'+esc(g.address_name||'-')+'</b><br>'+
        esc(g.address_street1||'-')+s2+'<br>'+
        esc(g.address_city||'-')+', '+esc(g.address_state||'-')+' '+esc(g.address_zip||'-')+
        (g.address_country&&g.address_country!=='US'?'<br>'+esc(g.address_country):'')+
        '</div>';
}
function addressForm(g){
    return '<div class="f"><label>Recipient Name *</label><input id="an" value="'+esc(g.address_name||'')+'" placeholder="Jane Smith"></div>'+
        '<div class="f"><label>Street Address 1 *</label><input id="as1" value="'+esc(g.address_street1||'')+'" placeholder="123 Main Street"></div>'+
        '<div class="f"><label>Street Address 2 (Apt, Suite — optional)</label><input id="as2" value="'+esc(g.address_street2||'')+'" placeholder="Apt 5"></div>'+
        '<div class="row3"><div class="f"><label>City *</label><input id="ac" value="'+esc(g.address_city||'')+'" placeholder="Brooklyn"></div>'+
        '<div class="f"><label>State *</label><input id="ast" value="'+esc(g.address_state||'')+'" placeholder="NY" maxlength="2" style="text-transform:uppercase"></div>'+
        '<div class="f"><label>ZIP *</label><input id="az" value="'+esc(g.address_zip||'')+'" placeholder="11201"></div></div>';
}
function bindEvents(){
    var pb=document.getElementById('parseBtn');
    if(pb)pb.addEventListener('click',function(){
        var dm=document.getElementById('dm').value.trim();
        if(!dm){toast('Paste the DM first',true);return}
        pb.disabled=true;pb.textContent='✨ Parsing...';
        var st=document.getElementById('parseStatus');st.textContent='AI is reading the message...';
        fetch('/api/giveaway/parse-address',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dm_text:dm})})
            .then(function(r){return r.json()}).then(function(d){
                pb.disabled=false;pb.textContent='✨ Parse with AI';
                if(d.ok){
                    var p=d.parsed;
                    document.getElementById('an').value=p.name||'';
                    document.getElementById('as1').value=p.street1||'';
                    document.getElementById('as2').value=p.street2||'';
                    document.getElementById('ac').value=p.city||'';
                    document.getElementById('ast').value=p.state||'';
                    document.getElementById('az').value=p.zip||'';
                    var conf={high:'conf-high',medium:'conf-medium',low:'conf-low'}[p.confidence]||'conf-low';
                    var miss=p.missing&&p.missing.length?' · Missing: '+p.missing.join(', '):'';
                    st.innerHTML='<span class="conf-badge '+conf+'">'+p.confidence+'</span> Review the fields below'+miss;
                    if(p.confidence==='high')toast('Parsed! Please verify the fields');
                    else if(p.confidence==='medium')toast('Parsed with some uncertainty - please verify',true);
                    else toast('Low confidence - please review carefully',true);
                } else {
                    st.textContent='';
                    toast(d.error||'AI parsing failed',true);
                }
            }).catch(function(){
                pb.disabled=false;pb.textContent='✨ Parse with AI';
                st.textContent='';toast('Network error',true);
            });
    });
    var sa=document.getElementById('saveAddr');
    if(sa)sa.addEventListener('click',function(){
        var p={
            address_name:document.getElementById('an').value.trim(),
            address_street1:document.getElementById('as1').value.trim(),
            address_street2:document.getElementById('as2').value.trim(),
            address_city:document.getElementById('ac').value.trim(),
            address_state:document.getElementById('ast').value.trim().toUpperCase(),
            address_zip:document.getElementById('az').value.trim(),
            dm_text:(document.getElementById('dm')||{}).value
        };
        fetch('/api/giveaway/'+GID+'/address',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)})
            .then(function(r){return r.json()}).then(function(d){
                if(d.ok){toast('Address saved');load()}else toast(d.error||'Failed',true);
            });
    });
    var sh=document.getElementById('ship');
    if(sh)sh.addEventListener('click',function(){
        var trk=document.getElementById('trk').value.trim();
        var nt=document.getElementById('nt').value.trim();
        if(!trk){toast('Tracking number required',true);return}
        fetch('/api/giveaway/'+GID+'/ship',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({tracking_number:trk,notes:nt})})
            .then(function(r){return r.json()}).then(function(d){
                if(d.ok){toast('Marked as shipped! 📦');load()}else toast(d.error||'Failed',true);
            });
    });
    var cn=document.getElementById('cancel');
    if(cn)cn.addEventListener('click',function(){
        if(!confirm('Cancel this giveaway? This cannot be undone.'))return;
        fetch('/api/giveaway/'+GID+'/cancel',{method:'POST'}).then(function(r){return r.json()}).then(function(d){
            if(d.ok){toast('Cancelled');setTimeout(function(){location.href='/giveaway'},1000)}else toast(d.error||'Failed',true);
        });
    });
    // Weight unit (oz/lb) — stored value is oz; selector only changes display/entry.
    var gwUnit=document.getElementById('wUnit');
    function gFromOz(oz){oz=parseFloat(oz||0);if(!oz)return '';return gwUnit.value==='lb'?Math.round(oz/16*1000)/1000:oz;}
    function gToOz(v){v=parseFloat(v||0);return gwUnit.value==='lb'?v*16:v;}
    if(gwUnit){
        gwUnit.value=localStorage.getItem('wunit')||'oz';
        gwUnit.addEventListener('change',function(){localStorage.setItem('wunit',this.value);
            var w=parseFloat(document.getElementById('wt').value||0);
            if(w)document.getElementById('wt').value=(this.value==='lb')?Math.round(w/16*1000)/1000:Math.round(w*16*100)/100;});
    }
    var psel=document.getElementById('pkgSel');
    if(psel){
        fetch('/api/packages').then(function(r){return r.json()}).then(function(d){
            var pk=d.packages||[];window._pk=pk;
            psel.innerHTML='<option value="">— custom —</option>'+pk.map(function(p,i){return '<option value="'+i+'">'+esc(p.name)+' ('+(p.weight||0)+'oz)</option>'}).join('');
        });
        psel.addEventListener('change',function(){var i=this.value;if(i===''||!window._pk)return;var p=window._pk[+i];
            document.getElementById('wt').value=gFromOz(p.weight);document.getElementById('ln').value=p.length||'';
            document.getElementById('wd').value=p.width||'';document.getElementById('ht').value=p.height||'';});
    }
    var gr=document.getElementById('getRates');
    if(gr)gr.addEventListener('click',function(){
        var wt=document.getElementById('wt').value;
        if(!wt||parseFloat(wt)<=0){toast('Enter weight',true);return}
        var box=document.getElementById('ratesBox');box.innerHTML='<div style="color:#6b7280;font-size:13px">Getting rates…</div>';
        fetch('/api/giveaway/'+GID+'/rates',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({weight_oz:gToOz(wt),length:document.getElementById('ln').value,width:document.getElementById('wd').value,height:document.getElementById('ht').value})})
         .then(function(r){return r.json()}).then(function(d){
            if(!d.ok){box.innerHTML='<div style="color:#e11d48;font-size:13px">'+esc(d.error||'Failed')+'</div>';return}
            if(!d.rates.length){box.innerHTML='<div style="color:#e11d48;font-size:13px">No rates returned</div>';return}
            box.innerHTML=d.rates.map(function(rt){
                return '<div class="addr-display" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">'+
                  '<div><b>'+esc(rt.carrier)+'</b> '+esc(rt.service)+(rt.days?(' · '+rt.days+'d'):'')+'</div>'+
                  '<button class="btn btn-p" style="padding:6px 14px" onclick="buyLabel(\\''+d.shipment_id+'\\',\\''+rt.id+'\\',this)">$'+rt.rate+'</button></div>';
            }).join('');
        });
    });
}
function buyLabel(sid,rid,btn){
    if(btn){btn.disabled=true;btn.textContent='Buying…'}
    fetch('/api/giveaway/'+GID+'/buy-label',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({shipment_id:sid,rate_id:rid})})
     .then(function(r){return r.json()}).then(function(d){
        if(!d.ok){toast(d.error||'Failed',true);if(btn){btn.disabled=false;btn.textContent='Retry'}return}
        toast('Label bought! 🏷️');
        window.open('/label/giveaway/'+GID,'_blank');
        load();
    });
}
function load(){
    fetch('/api/giveaway/'+GID).then(function(r){return r.json()}).then(function(d){
        if(!d.ok){document.getElementById('wrap').innerHTML='<div style="text-align:center;padding:60px;color:#e11d48">Giveaway not found</div>';return}
        G=d.giveaway;render();
    });
}
load();
</script></body></html>'''


# ══════════════════════════════════════════════════════════
# BADGE LOGIN + ADMIN BADGE MANAGEMENT HTML
# ══════════════════════════════════════════════════════════

BADGE_LOGIN_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Scan Your Badge — __BRANDMARK__</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:radial-gradient(760px 520px at 20% 0%, rgba(79,70,229,.10), transparent 60%),radial-gradient(700px 520px at 80% 100%, rgba(124,58,237,.07), transparent 60%),#fbfcff;color:#141b26;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
.box{max-width:500px;width:100%;text-align:center}
.brand-line{display:flex;align-items:center;justify-content:center;gap:13px;margin-bottom:38px;line-height:1}
.brand-tile{width:48px;height:48px;border-radius:13px;background:linear-gradient(135deg,#4f46e5,#7c3aed);display:flex;align-items:center;justify-content:center;box-shadow:0 10px 26px rgba(79,70,229,.34);flex:none}
.brand-txt{text-align:left}
.brand-mark-page{display:block;font-size:25px;font-weight:800;color:#141b26;letter-spacing:-.5px}
.brand-mark-page .hl{color:#4f46e5}
.brand-sub-page{display:block;font-size:9px;font-weight:700;color:#8a93a5;letter-spacing:2.6px;text-transform:uppercase;margin-top:5px}
h1{font-size:36px;font-weight:800;letter-spacing:-.8px;margin-bottom:12px}
.sub{color:#4f46e5;font-size:18px;margin-bottom:38px;font-weight:600}
.scan-area{background:#ffffff;border:2px dashed rgba(79,70,229,.32);border-radius:24px;padding:46px 30px;margin-bottom:24px;transition:all .3s;box-shadow:0 18px 50px rgba(79,70,229,.08)}
.scan-area.focus{border-color:#6366f1;background:#ffffff}
.scan-area.success{border-color:#10b981;background:rgba(16,185,129,.05)}
.scan-area.error{border-color:#f43f5e;background:rgba(244,63,94,.05);animation:shake .4s}
@keyframes shake{0%,100%{transform:translateX(0)}25%{transform:translateX(-10px)}75%{transform:translateX(10px)}}
.scan-graphic{position:relative;width:154px;height:80px;margin:0 auto 22px}
.scan-graphic svg{display:block}
.scan-beam{position:absolute;top:4px;left:0;width:100%;height:3px;background:linear-gradient(90deg,transparent,#4f46e5,transparent);box-shadow:0 0 12px 3px rgba(79,70,229,.6);border-radius:3px;animation:sweep 2.2s ease-in-out infinite}
@keyframes sweep{0%{top:4px}50%{top:70px}100%{top:4px}}
.scan-area.success .scan-beam,.scan-area.error .scan-beam{display:none}
.scan-text{font-size:20px;font-weight:700;margin-bottom:8px}
.scan-hint{color:#7b8494;font-size:14px}
input{position:absolute;opacity:0;pointer-events:none}
.alt-link{display:inline-flex;align-items:center;gap:8px;margin-top:24px;padding:14px 28px;border-radius:12px;background:#f4f5fb;border:1px solid #e6e8f5;color:#586274;text-decoration:none;font-size:14px;font-weight:700;letter-spacing:.2px;transition:all .15s}
.alt-link:hover{color:#4f46e5;background:#eef0fb;border-color:rgba(79,70,229,.28)}
.toast{position:fixed;top:24px;left:50%;transform:translateX(-50%);background:#10b981;color:white;padding:14px 28px;border-radius:50px;font-weight:700;font-size:15px;box-shadow:0 10px 40px rgba(16,185,129,.4);z-index:100;display:none}
.toast.err{background:#f43f5e;box-shadow:0 10px 40px rgba(244,63,94,.4)}

/* Welcome overlay shown after a successful badge scan, before redirect */
.welcome-ov{position:fixed;inset:0;background:radial-gradient(800px 600px at 50% 30%, rgba(79,70,229,.16), transparent 60%),#fbfcff;z-index:200;display:none;align-items:center;justify-content:center;flex-direction:column;padding:30px;animation:fadeIn .25s ease}
.welcome-ov.on{display:flex}
@keyframes fadeIn{from{opacity:0}to{opacity:1}}
.welcome-avatar{width:160px;height:160px;border-radius:50%;background:linear-gradient(135deg,#4f46e5,#7c3aed);display:flex;align-items:center;justify-content:center;font-size:78px;font-weight:900;color:#ffffff;margin-bottom:32px;box-shadow:0 24px 80px rgba(79,70,229,.35),0 0 0 8px rgba(79,70,229,.08);animation:pop .5s cubic-bezier(.175,.885,.32,1.275)}
@keyframes pop{from{transform:scale(.4);opacity:0}to{transform:scale(1);opacity:1}}
.welcome-eyebrow{font-size:13px;font-weight:800;color:#4f46e5;letter-spacing:2.5px;text-transform:uppercase;margin-bottom:8px}
.welcome-name{font-size:46px;font-weight:900;color:#141b26;letter-spacing:-1px;line-height:1.05;text-align:center;margin-bottom:28px}
.welcome-loading{display:flex;align-items:center;gap:10px;color:#586274;font-size:14px;font-weight:600}
.welcome-loading .sp{width:14px;height:14px;border:2px solid rgba(17,24,39,0.16);border-top-color:#4f46e5;border-radius:50%;animation:sp 1s linear infinite}
@keyframes sp{to{transform:rotate(360deg)}}
</style></head><body>
<button id="langBtn" onclick="toggleLang()" style="position:fixed;top:14px;right:14px;z-index:200;background:#f4f5fb;border:1px solid #e6e8f5;color:#141b26;border-radius:10px;padding:8px 14px;font-size:14px;font-weight:800;cursor:pointer;font-family:inherit">ES</button>
<div class="box">
<div class="brand-line"><span class="brand-tile"><svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2"/><path d="M7 12h10"/></svg></span><span class="brand-txt"><span class="brand-mark-page">__BRANDMARK__</span><span class="brand-sub-page">Employee Sign-In</span></span></div>
<h1 data-i18n="welcome">Welcome!</h1>
<div class="sub" data-i18n="sub">Scan your employee badge to begin</div>
<div class="scan-area focus" id="sa">
<div class="scan-graphic"><svg width="154" height="80" viewBox="0 0 154 80"><g fill="#141b26"><rect x="8" y="11" width="4" height="58"/><rect x="16" y="11" width="2" height="58"/><rect x="22" y="11" width="6" height="58"/><rect x="32" y="11" width="3" height="58"/><rect x="39" y="11" width="2" height="58"/><rect x="45" y="11" width="5" height="58"/><rect x="54" y="11" width="2" height="58"/><rect x="60" y="11" width="4" height="58"/><rect x="68" y="11" width="6" height="58"/><rect x="78" y="11" width="2" height="58"/><rect x="84" y="11" width="4" height="58"/><rect x="92" y="11" width="3" height="58"/><rect x="99" y="11" width="5" height="58"/><rect x="108" y="11" width="2" height="58"/><rect x="114" y="11" width="4" height="58"/><rect x="122" y="11" width="6" height="58"/><rect x="132" y="11" width="2" height="58"/><rect x="138" y="11" width="4" height="58"/></g></svg><div class="scan-beam" id="beam"></div></div>
<div class="scan-text" id="st" data-i18n="ready">Ready to scan</div>
<div class="scan-hint" data-i18n="hold">Hold your badge under the scanner</div>
</div>
<input type="text" id="tk" autofocus autocomplete="off" inputmode="none">
<a href="/login" class="alt-link" data-i18n="altlink">⌨ Use username & password instead</a>
</div>
<div class="welcome-ov" id="welcomeOv">
  <div class="welcome-avatar" id="welcomeAvatar">?</div>
  <div class="welcome-eyebrow" id="welcomeEyebrow">Welcome back</div>
  <div class="welcome-name" id="welcomeName">—</div>
  <div class="welcome-loading"><div class="sp"></div><span data-i18n="loadws">Loading your workspace…</span></div>
</div>
<div class="toast" id="toast"></div>
<script>
var LANG=localStorage.getItem('lang')||'en';
var T={
 en:{welcome:'Welcome!',sub:'Scan your employee badge to begin',ready:'Ready to scan',hold:'Hold your badge under the scanner',altlink:'⌨ Use username & password instead',loadws:'Loading your workspace…',verifying:'Verifying...',reading:'Reading...',notrec:'Badge not recognized',connerr:'Connection error',tryagain:'Try again',gm:'Good morning',ga:'Good afternoon',ge:'Good evening',late:'Late night shift',workinglate:'Working late',hi:'Hi'},
 es:{welcome:'¡Bienvenido!',sub:'Escanea tu credencial para comenzar',ready:'Listo para escanear',hold:'Coloca tu credencial bajo el escáner',altlink:'⌨ Usar usuario y contraseña',loadws:'Cargando tu espacio…',verifying:'Verificando...',reading:'Leyendo...',notrec:'Credencial no reconocida',connerr:'Error de conexión',tryagain:'Intenta de nuevo',gm:'Buenos días',ga:'Buenas tardes',ge:'Buenas noches',late:'Turno nocturno',workinglate:'Trabajando tarde',hi:'¡Hola'}
};
function t(k){return (T[LANG]&&T[LANG][k])||T.en[k]||k}
function toggleLang(){LANG=(LANG==='en'?'es':'en');localStorage.setItem('lang',LANG);location.reload()}
function applyLang(){document.querySelectorAll('[data-i18n]').forEach(function(e){e.textContent=t(e.dataset.i18n)});var lb=document.getElementById('langBtn');if(lb)lb.textContent=(LANG==='en'?'ES':'EN')}
var inp=document.getElementById('tk'),sa=document.getElementById('sa'),st=document.getElementById('st');
var buf="",lastKey=0,timer=null;
applyLang();

function showToast(m,err){
    var t=document.getElementById('toast');t.textContent=m;t.className=err?'toast err':'toast';t.style.display='block';
    setTimeout(function(){t.style.display='none'},3000);
}

function tryLogin(token){
    sa.className='scan-area';st.textContent=t('verifying');
    fetch('/api/badge-login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:token})})
    .then(function(r){return r.json()}).then(function(d){
        if(d.ok){
            // Show big welcome overlay with avatar initial, then redirect
            var nm=d.name||'';
            var initial=(nm.trim().charAt(0)||'?').toUpperCase();
            // Time-of-day eyebrow
            var hr=new Date().getHours();
            var eb=hr<5?t('late'):hr<12?t('gm'):hr<17?t('ga'):hr<22?t('ge'):t('workinglate');
            document.getElementById('welcomeAvatar').textContent=initial;
            document.getElementById('welcomeEyebrow').textContent=eb;
            document.getElementById('welcomeName').textContent=t('hi')+', '+nm+'!';
            document.getElementById('welcomeOv').classList.add('on');
            sa.className='scan-area success';st.textContent=t('hi')+', '+d.name+'!';
            setTimeout(function(){location.href='/'},1500);
        } else {
            sa.className='scan-area error';st.textContent=t('notrec');
            showToast(d.error||t('tryagain'),true);
            setTimeout(function(){sa.className='scan-area focus';st.textContent=t('ready');buf=""},1500);
        }
    }).catch(function(){
        sa.className='scan-area error';st.textContent=t('connerr');
        setTimeout(function(){sa.className='scan-area focus';st.textContent=t('ready');buf=""},1500);
    });
}

// Listen for keyboard input from USB barcode scanner
// Scanners type fast (chars within ~10ms) and end with Enter
document.addEventListener('keydown',function(e){
    var now=Date.now();
    // Reset buffer if too much time elapsed (manual typing vs scanner)
    if(now-lastKey>300) buf="";
    lastKey=now;
    if(e.key==='Enter'){
        if(buf.length>=8){
            var token=buf.toUpperCase();
            buf="";
            tryLogin(token);
        }
        e.preventDefault();
    } else if(e.key.length===1) {
        buf+=e.key;
        if(buf.length===1){sa.className='scan-area';st.textContent=t('reading')}
        // Auto-reset display if user stops typing (didn't hit Enter)
        clearTimeout(timer);
        timer=setTimeout(function(){
            if(buf.length>0&&Date.now()-lastKey>500){buf="";sa.className='scan-area focus';st.textContent=t('ready')}
        },1500);
    }
});

// Keep focus on the hidden input so the page is always "listening"
inp.focus();
setInterval(function(){if(document.activeElement!==inp)inp.focus()},500);
</script></body></html>'''


USERS_BADGES_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Employee Badges</title>
__NAVBAR_CSS__
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#ffffff;color:#1a2130;min-height:100vh}
.page-hdr{padding:24px 28px 8px;max-width:1100px;margin:0 auto}
.page-title{font-size:22px;font-weight:800}
.page-title span{color:#4f46e5;margin-left:8px;font-weight:600;font-size:14px}
.wrap{max-width:1100px;margin:0 auto;padding:0 28px 28px}
.intro{background:rgba(79,70,229,.08);border:1px solid rgba(79,70,229,.2);border-radius:14px;padding:18px 22px;margin-bottom:24px;color:#4f46e5;font-size:14px;line-height:1.6}
.intro b{color:#1a2130}
.actions-bar{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px;flex-wrap:wrap;gap:12px}
h2{font-size:18px;font-weight:700}
.btn{border:none;border-radius:10px;padding:11px 22px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit;transition:all .15s;text-decoration:none;display:inline-flex;align-items:center;gap:6px}
.btn-p{background:linear-gradient(135deg,#4f46e5,#7c3aed);color:white;box-shadow:0 4px 16px rgba(79,70,229,.3)}
.btn-p:hover{transform:translateY(-1px)}
.btn-s{background:rgba(17,24,39,0.128);color:#1a2130;border:1px solid rgba(17,24,39,0.16)}
.btn-s:hover{background:rgba(17,24,39,0.16)}
.btn-d{background:rgba(244,63,94,.1);color:#e11d48;border:1.5px solid rgba(244,63,94,.2)}
.btn-d:hover{background:rgba(244,63,94,.2)}
.btn-sm{padding:7px 13px;font-size:12px}
table{width:100%;background:#ffffff;border:1px solid rgba(17,24,39,0.096);border-radius:14px;border-collapse:separate;border-spacing:0;overflow:hidden}
th,td{padding:14px 18px;text-align:left;border-bottom:1px solid rgba(17,24,39,0.064)}
th{background:#ffffff;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:#6b7280}
tr:last-child td{border-bottom:none}
.role-w{background:rgba(96,165,250,.15);color:#2563eb;padding:3px 10px;border-radius:50px;font-size:11px;font-weight:700;text-transform:uppercase}
.role-c{background:rgba(167,139,250,.15);color:#7c3aed;padding:3px 10px;border-radius:50px;font-size:11px;font-weight:700;text-transform:uppercase}
.role-a{background:rgba(244,63,94,.15);color:#e11d48;padding:3px 10px;border-radius:50px;font-size:11px;font-weight:700;text-transform:uppercase}
.has-badge{color:#059669;font-weight:600}
.no-badge{color:#6b7280;font-style:italic}
.actions{display:flex;gap:6px;flex-wrap:wrap}
.toast{position:fixed;bottom:24px;right:24px;background:#10b981;color:white;padding:14px 22px;border-radius:10px;font-weight:600;box-shadow:0 10px 40px rgba(16,185,129,.4);z-index:100;display:none}
.toast.err{background:#f43f5e}
.station-select{margin-bottom:24px;background:#ffffff;border:1px solid rgba(17,24,39,0.096);border-radius:14px;padding:18px 22px}
.station-select h3{font-size:13px;font-weight:700;color:#4f46e5;text-transform:uppercase;letter-spacing:.6px;margin-bottom:8px}
.station-select .row{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.station-select select{background:#ffffff;border:2px solid rgba(17,24,39,0.128);border-radius:10px;padding:9px 14px;font-size:14px;color:#1a2130;font-family:inherit;outline:none}
.station-select .current{font-size:14px;color:#059669;font-weight:600}
</style></head><body>
__NAVBAR__
<div class="page-hdr"><div class="page-title">🎫 Employee Badges <span>__NAME__</span></div></div>
<div class="wrap">

<div class="intro">
💡 <b>How badges work:</b> Each worker gets a unique barcode they scan to log in.
Workers don't need passwords — just scan the badge. Print them on Avery 5160 sticker sheets (30 per page).
</div>

<div class="station-select">
<h3>📍 This Computer's Station</h3>
<div class="row">
<div class="current" id="curSta">Loading...</div>
<select id="staSel"><option value="">-- Choose station --</option></select>
<button class="btn btn-s btn-sm" id="setSta">Set as this machine's station</button>
<button class="btn btn-d btn-sm" id="clrSta">Clear</button>
</div>
<div style="font-size:12px;color:#6b7280;margin-top:8px">When set, workers who scan their badge on this machine will automatically be assigned to this station.</div>
</div>

<div class="actions-bar">
<h2>Workers with Badges</h2>
<a href="/api/users/badge/sheet" class="btn btn-p" target="_blank">🖨️ Print All Badges (Avery 5160)</a>
</div>

<table>
<thead><tr><th>Username</th><th>Name</th><th>Role</th><th>Badge</th><th>Actions</th></tr></thead>
<tbody id="tb"><tr><td colspan="5" style="text-align:center;color:#6b7280;padding:40px">Loading...</td></tr></tbody>
</table>
</div>

<div class="toast" id="t"></div>
<script>
function toast(m,e){var t=document.getElementById('t');t.textContent=m;t.className=e?'toast err':'toast';t.style.display='block';setTimeout(function(){t.style.display='none'},3000)}

function loadStation(){
    fetch('/api/machine-station').then(function(r){return r.json()}).then(function(d){
        var cur=document.getElementById('curSta');
        if(d.station)cur.innerHTML='✓ Currently set to: <b>'+d.station_name+' ('+d.station+')</b>';
        else cur.innerHTML='<span style="color:#b45309">⚠️ No station assigned to this machine</span>';
        var sel=document.getElementById('staSel');
        sel.innerHTML='<option value="">-- Choose station --</option>';
        Object.keys(d.all_stations).forEach(function(sid){
            var o=document.createElement('option');o.value=sid;o.textContent=sid+' - '+d.all_stations[sid];
            if(sid===d.station)o.selected=true;
            sel.appendChild(o);
        });
    });
}
document.getElementById('setSta').addEventListener('click',function(){
    var sta=document.getElementById('staSel').value;
    if(!sta){toast('Pick a station first',true);return}
    fetch('/api/machine-station',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({station:sta})})
        .then(function(r){return r.json()}).then(function(d){
            if(d.ok){toast('Station saved for this machine');loadStation()}else toast(d.error||'Failed',true);
        });
});
document.getElementById('clrSta').addEventListener('click',function(){
    if(!confirm('Clear station for this machine?'))return;
    fetch('/api/machine-station',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({station:''})})
        .then(function(r){return r.json()}).then(function(d){
            if(d.ok){toast('Cleared');loadStation()}
        });
});

function loadUsers(){
    fetch('/api/users').then(function(r){return r.json()}).then(function(users){
        var tb=document.getElementById('tb');
        var rows=Object.keys(users).map(function(u){
            var info=users[u];
            var roleClass='role-'+(info.role==='admin'?'a':info.role==='cs'?'c':'w');
            var badgeText=info.has_badge?'<span class="has-badge">✓ Active</span>':'<span class="no-badge">— None</span>';
            var actions='';
            if(info.role==='worker'){
                if(info.has_badge){
                    actions='<a class="btn btn-s btn-sm" href="/api/users/badge/pdf/'+u+'" target="_blank">🖨️ Card</a>'+
                        '<a class="btn btn-s btn-sm" href="/api/users/badge/label4x6/'+u+'" target="_blank">🖨️ 4×6 Label</a>'+
                        '<button class="btn btn-d btn-sm" data-act="regen" data-u="'+u+'">↻ Regen</button>'+
                        '<button class="btn btn-d btn-sm" data-act="revoke" data-u="'+u+'">✕ Revoke</button>';
                } else {
                    actions='<button class="btn btn-p btn-sm" data-act="regen" data-u="'+u+'">+ Issue Badge</button>';
                }
            } else {
                actions='<span style="color:#6b7280;font-size:12px">Badges are for workers</span>';
            }
            return '<tr><td><b>'+u+'</b></td><td>'+info.name+'</td><td><span class="'+roleClass+'">'+info.role+'</span></td><td>'+badgeText+'</td><td><div class="actions">'+actions+'</div></td></tr>';
        });
        tb.innerHTML=rows.join('')||'<tr><td colspan="5" style="text-align:center;color:#6b7280;padding:40px">No users yet</td></tr>';
        tb.querySelectorAll('button[data-act]').forEach(function(b){
            b.addEventListener('click',function(){
                var u=b.dataset.u,act=b.dataset.act;
                if(act==='revoke'&&!confirm('Revoke badge for '+u+'? They will need a password to log in.'))return;
                if(act==='regen'){
                    fetch('/api/users/badge',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u})})
                        .then(function(r){return r.json()}).then(function(d){
                            if(d.ok){toast('Badge issued. Print it next.');loadUsers()}else toast(d.error||'Failed',true);
                        });
                } else if(act==='revoke'){
                    fetch('/api/users/badge/revoke',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u})})
                        .then(function(r){return r.json()}).then(function(d){
                            if(d.ok){toast('Badge revoked');loadUsers()}else toast(d.error||'Failed',true);
                        });
                }
            });
        });
    });
}
loadStation();
loadUsers();
</script></body></html>'''


# ══════════════════════════════════════════════════════════
# EMPLOYEE PORTAL — profile page, leaderboard
# ══════════════════════════════════════════════════════════

ME_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>My Profile — Packing Station</title>
__NAVBAR_CSS__
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'DM Sans',-apple-system,sans-serif;background:#ffffff;color:#1a2130;min-height:100vh;padding-bottom:80px}
.wrap{max-width:1100px;margin:0 auto;padding:32px 24px}
.hero{display:flex;align-items:center;gap:24px;margin-bottom:32px;padding:28px;background:linear-gradient(135deg,rgba(79,70,229,.12),rgba(168,85,247,.06));border:1px solid rgba(79,70,229,.18);border-radius:18px}
.avatar{width:80px;height:80px;border-radius:50%;background:linear-gradient(135deg,#6366f1,#7c3aed);display:flex;align-items:center;justify-content:center;font-size:36px;font-weight:800;color:#fff;flex-shrink:0}
.hero-info h1{font-size:28px;font-weight:800;margin-bottom:4px;color:#141b26}
.hero-info .role{font-size:13px;color:#4f46e5;font-weight:600;text-transform:uppercase;letter-spacing:.5px}
.hero-info .since{font-size:13px;color:#6b7280;margin-top:6px}
.rank-pill{margin-left:auto;text-align:center;padding:14px 20px;background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.18);border-radius:12px;min-width:120px}
.rank-pill .num{font-size:32px;font-weight:900;color:#b45309;line-height:1}
.rank-pill .lbl{font-size:11px;color:#586274;text-transform:uppercase;letter-spacing:.5px;margin-top:4px}
.section-title{font-size:13px;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:1px;margin:32px 0 12px}
.grid-4{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.stat-card{background:rgba(17,24,39,0.032);border:1px solid rgba(17,24,39,0.096);border-radius:14px;padding:18px}
.stat-card .lbl{font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px;font-weight:600}
.stat-card .val{font-size:32px;font-weight:800;color:#1a2130;margin:8px 0 2px;line-height:1}
.stat-card .sub{font-size:12px;color:#586274}
.stat-card.highlight{background:linear-gradient(135deg,rgba(99,102,241,.12),rgba(99,102,241,.04));border-color:rgba(99,102,241,.25)}
.stat-card.highlight .val{color:#4f46e5}
.achievements{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:14px}
.medal{background:rgba(17,24,39,0.032);border:1px solid rgba(17,24,39,0.096);border-radius:14px;padding:18px;text-align:center;position:relative;transition:transform .15s}
.medal.earned{background:linear-gradient(135deg,rgba(251,191,36,.1),rgba(245,158,11,.04));border-color:rgba(251,191,36,.25)}
.medal.earned:hover{transform:translateY(-2px)}
.medal .emoji{font-size:44px;line-height:1;filter:grayscale(1);opacity:.35}
.medal.earned .emoji{filter:none;opacity:1}
.medal .label{font-size:12px;color:#586274;margin-top:8px;font-weight:600}
.medal.earned .label{color:#b45309}
.medal.earned::after{content:'✓';position:absolute;top:8px;right:8px;background:#10b981;color:#fff;width:18px;height:18px;border-radius:50%;font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center}
.recent-table{width:100%;background:rgba(17,24,39,0.032);border:1px solid rgba(17,24,39,0.096);border-radius:14px;overflow:hidden;border-collapse:collapse}
.recent-table th{text-align:left;padding:12px 16px;font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px;background:rgba(17,24,39,0.032);border-bottom:1px solid rgba(17,24,39,0.096)}
.recent-table td{padding:12px 16px;font-size:13px;color:#1a2130;border-bottom:1px solid rgba(17,24,39,0.064)}
.recent-table tr:last-child td{border-bottom:none}
.recent-table td.muted{color:#586274}
.recent-table td.mono{font-family:'SF Mono',Menlo,monospace;font-size:12px}
.empty{text-align:center;padding:40px;color:#6b7280;font-size:14px;background:rgba(17,24,39,0.032);border:1px dashed rgba(17,24,39,0.128);border-radius:14px}
@media(max-width:700px){
.grid-4{grid-template-columns:repeat(2,1fr)}
.hero{flex-wrap:wrap}
.rank-pill{margin-left:0;width:100%}
}
</style>
</head><body>
__NAVBAR__
<div class="wrap">
  <div class="hero">
    <div class="avatar" id="avatar">?</div>
    <div class="hero-info">
      <h1 id="name">Loading…</h1>
      <div class="role" id="role"></div>
      <div class="since" id="since"></div>
    </div>
    <div class="rank-pill" id="rankPill" style="display:none">
      <div class="num" id="rankNum">—</div>
      <div class="lbl">Rank this month</div>
    </div>
  </div>

  <div class="section-title">Your numbers</div>
  <div class="grid-4">
    <div class="stat-card"><div class="lbl">Today</div><div class="val" id="todayCount">0</div><div class="sub" id="todayAvg">—</div></div>
    <div class="stat-card highlight"><div class="lbl">This month</div><div class="val" id="monthCount">0</div><div class="sub" id="monthAvg">—</div></div>
    <div class="stat-card"><div class="lbl">All time</div><div class="val" id="allCount">0</div><div class="sub" id="allAvg">—</div></div>
    <div class="stat-card"><div class="lbl">Days worked</div><div class="val" id="allDays">0</div><div class="sub">total active days</div></div>
  </div>

  <div class="section-title">Achievements</div>
  <div class="achievements" id="achievements"></div>

  <div class="section-title">Recent packages</div>
  <div id="recentWrap"></div>
</div>

<script>
function fmtDur(s){if(!s||s==='0')return '—';var n=parseFloat(s);return isNaN(n)?'—':n.toFixed(1)+'s avg'}
fetch('/api/me/stats').then(function(r){return r.json()}).then(function(d){
  document.getElementById('name').textContent=d.name||'Unknown';
  document.getElementById('avatar').textContent=(d.name||'?').charAt(0).toUpperCase();
  document.getElementById('role').textContent=d.role||'';
  if(d.all_time && d.all_time.last_date){
    document.getElementById('since').textContent='Most recent activity: '+d.all_time.last_date;
  }
  if(d.rank_this_month){
    document.getElementById('rankPill').style.display='block';
    document.getElementById('rankNum').textContent='#'+d.rank_this_month;
  }
  document.getElementById('todayCount').textContent=d.today.count;
  document.getElementById('todayAvg').textContent=fmtDur(d.today.avg_dur);
  document.getElementById('monthCount').textContent=d.this_month.count;
  document.getElementById('monthAvg').textContent=fmtDur(d.this_month.avg_dur);
  document.getElementById('allCount').textContent=d.all_time.count;
  document.getElementById('allAvg').textContent=fmtDur(d.all_time.avg_dur);
  document.getElementById('allDays').textContent=d.all_time.days;
  // Achievements
  var ach=document.getElementById('achievements');
  ach.innerHTML=d.achievements.map(function(b){
    return '<div class="medal'+(b.earned?' earned':'')+'"><div class="emoji">'+b.emoji+'</div><div class="label">'+b.label+'</div></div>';
  }).join('');
  // Recent
  var w=document.getElementById('recentWrap');
  if(!d.recent || d.recent.length===0){
    w.innerHTML='<div class="empty">No packages logged yet. Once you start packing, your recent activity will show here.</div>';
  } else {
    var rows=d.recent.map(function(r){
      return '<tr><td class="mono">'+(r.tracking_number||'—')+'</td><td>'+(r.station||'—')+'</td><td class="muted">'+(r.date||'')+' '+(r.time||'')+'</td><td>'+(r.duration_seconds||'0')+'s</td></tr>';
    }).join('');
    w.innerHTML='<table class="recent-table"><thead><tr><th>Tracking</th><th>Station</th><th>When</th><th>Duration</th></tr></thead><tbody>'+rows+'</tbody></table>';
  }
});
</script>
</body></html>'''


LEADERBOARD_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Leaderboard — Packing Station</title>
__NAVBAR_CSS__
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'DM Sans',-apple-system,sans-serif;background:#ffffff;color:#1a2130;min-height:100vh;padding-bottom:80px}
.wrap{max-width:1000px;margin:0 auto;padding:32px 24px}
.page-title{font-size:32px;font-weight:900;margin-bottom:6px}
.subtitle{color:#586274;margin-bottom:24px;font-size:14px}
.window-tabs{display:flex;gap:6px;background:rgba(17,24,39,0.048);padding:5px;border-radius:11px;border:1px solid rgba(17,24,39,0.096);margin-bottom:32px;max-width:fit-content}
.window-tab{padding:9px 18px;border-radius:8px;font-size:13px;font-weight:600;color:#586274;cursor:pointer;transition:all .15s;background:transparent;border:none;font-family:inherit}
.window-tab:hover{color:#1a2130}
.window-tab.active{background:rgba(99,102,241,.18);color:#4f46e5}
.podium{display:grid;grid-template-columns:1fr 1.2fr 1fr;gap:14px;margin-bottom:24px;align-items:end}
.podium-slot{background:rgba(17,24,39,0.048);border:1px solid rgba(17,24,39,0.096);border-radius:14px;padding:20px;text-align:center;position:relative;transition:transform .2s}
.podium-slot.gold{background:linear-gradient(180deg,rgba(251,191,36,.16),rgba(251,191,36,.04));border-color:rgba(251,191,36,.3);min-height:240px}
.podium-slot.silver{background:linear-gradient(180deg,rgba(148,163,184,.14),rgba(148,163,184,.04));border-color:rgba(148,163,184,.25);min-height:210px}
.podium-slot.bronze{background:linear-gradient(180deg,rgba(217,119,6,.14),rgba(217,119,6,.04));border-color:rgba(217,119,6,.25);min-height:190px}
.podium-medal{font-size:44px;margin-bottom:8px}
.podium-name{font-size:18px;font-weight:800;color:#141b26;margin-bottom:4px}
.podium-count{font-size:28px;font-weight:900;color:#b45309;margin-bottom:2px}
.silver .podium-count{color:#475569}
.bronze .podium-count{color:#b45309}
.podium-meta{font-size:12px;color:#586274}
.rest-list{background:rgba(17,24,39,0.032);border:1px solid rgba(17,24,39,0.096);border-radius:14px;overflow:hidden}
.rest-row{display:grid;grid-template-columns:60px 1fr 100px 100px 100px;gap:12px;align-items:center;padding:14px 20px;border-bottom:1px solid rgba(17,24,39,0.064);font-size:14px}
.rest-row:last-child{border-bottom:none}
.rest-row.me{background:rgba(99,102,241,.08);border-left:3px solid #4f46e5}
.rest-rank{font-weight:800;color:#6b7280;font-size:16px}
.rest-name{font-weight:600;color:#1a2130}
.rest-stat{color:#586274;font-size:13px;text-align:right}
.rest-stat .big{color:#1a2130;font-weight:700;font-size:15px}
.empty{text-align:center;padding:60px 20px;color:#6b7280}
@media(max-width:700px){
.podium{grid-template-columns:1fr;gap:10px}
.podium-slot{min-height:auto!important}
.rest-row{grid-template-columns:50px 1fr 70px;gap:8px;padding:12px 14px;font-size:12px}
.rest-row .desktop-only{display:none}
}
</style>
</head><body>
__NAVBAR__
<div class="wrap">
  <div class="page-title">🏆 Leaderboard</div>
  <div class="subtitle" id="subtitle">Top packers — ranked by packages completed</div>

  <div class="window-tabs">
    <button class="window-tab" data-w="today">Today</button>
    <button class="window-tab" data-w="week">This week</button>
    <button class="window-tab active" data-w="month">This month</button>
    <button class="window-tab" data-w="all">All time</button>
  </div>

  <div id="podium"></div>
  <div id="restList"></div>
</div>

<script>
var ME=__ME__;
var currentWindow='month';
function esc(s){var d=document.createElement('div');d.textContent=(s==null?'':String(s));return d.innerHTML}

function load(w){
  currentWindow=w;
  document.querySelectorAll('.window-tab').forEach(function(b){
    b.classList.toggle('active', b.dataset.w===w);
  });
  fetch('/api/leaderboard?window='+w).then(function(r){return r.json()}).then(function(d){
    var lb=d.leaderboard||[];
    var podiumDiv=document.getElementById('podium');
    var restDiv=document.getElementById('restList');
    if(lb.length===0){
      podiumDiv.innerHTML='';
      restDiv.innerHTML='<div class="empty">No packing activity yet for this period.</div>';
      return;
    }
    // Podium for top 3
    var top3=lb.slice(0,3);
    if(top3.length>=1){
      var slots='';
      // Render in podium order: 2nd, 1st, 3rd (silver, gold, bronze)
      var ordered=[top3[1],top3[0],top3[2]];
      var classes=['silver','gold','bronze'];
      var medals=['🥈','🥇','🥉'];
      for(var i=0;i<3;i++){
        var p=ordered[i];
        if(!p){slots+='<div></div>';continue}
        slots+='<div class="podium-slot '+classes[i]+'">';
        slots+='<div class="podium-medal">'+medals[i]+'</div>';
        slots+='<div class="podium-name">'+esc(p.name)+'</div>';
        slots+='<div class="podium-count">'+p.count+'</div>';
        slots+='<div class="podium-meta">packages · avg '+(p.avg_dur||0)+'s</div>';
        slots+='</div>';
      }
      podiumDiv.innerHTML='<div class="podium">'+slots+'</div>';
    }
    // Rest of list (ranks 4+)
    var rest=lb.slice(3);
    if(rest.length===0){
      restDiv.innerHTML='';
      return;
    }
    var rows=rest.map(function(p){
      var me=(p.name===ME)?' me':'';
      return '<div class="rest-row'+me+'"><div class="rest-rank">#'+p.rank+'</div><div class="rest-name">'+esc(p.name)+'</div><div class="rest-stat"><span class="big">'+p.count+'</span> packs</div><div class="rest-stat desktop-only">'+(p.avg_dur||0)+'s avg</div><div class="rest-stat desktop-only">'+p.days+' days</div></div>';
    }).join('');
    restDiv.innerHTML='<div class="rest-list">'+rows+'</div>';
  });
}

document.querySelectorAll('.window-tab').forEach(function(b){
  b.addEventListener('click',function(){load(b.dataset.w)});
});
load('month');
</script>
</body></html>'''


# ══════════════════════════════════════════════════════════
# PORTAL HOME — categorized hub for all employees
# Sections: Personal · Operations (admin/cs) · Documents
# ══════════════════════════════════════════════════════════

HOME_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Home — __BRANDSUB__</title>
__NAVBAR_CSS__
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'DM Sans',-apple-system,sans-serif;background:#ffffff;color:var(--text);min-height:100vh;padding-bottom:120px;-webkit-font-smoothing:antialiased}
/* Soft ambient gradient behind everything */
body::before{content:'';position:fixed;inset:0;background:radial-gradient(900px 500px at 12% -10%, rgba(217,116,143,.06), transparent 60%),radial-gradient(700px 500px at 92% -10%, rgba(168,85,247,.05), transparent 60%);pointer-events:none;z-index:-1}
.wrap{max-width:1240px;margin:0 auto;padding:48px 28px 0}

/* Hero greeting */
.hero{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;margin-bottom:36px;flex-wrap:wrap}
.greet-eyebrow{font-size:12px;font-weight:700;color:var(--brand);text-transform:uppercase;letter-spacing:2px;margin-bottom:6px}
.greet-title{font-size:44px;font-weight:900;color:#141b26;line-height:1.05;letter-spacing:-1px}
.greet-title .name{background:linear-gradient(135deg,var(--brand),var(--brand-strong));-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
.greet-sub{font-size:15px;color:var(--text-muted);margin-top:8px;font-weight:500}
.quick-stats{display:flex;gap:12px;flex-wrap:wrap}
.qs{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:14px 18px;min-width:120px}
.qs .lbl{font-size:11px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.8px;font-weight:600}
.qs .val{font-size:26px;font-weight:800;color:#141b26;line-height:1;margin-top:6px}
.qs.brand{background:linear-gradient(135deg,rgba(217,116,143,.12),rgba(217,116,143,.03));border-color:rgba(217,116,143,.22)}
.qs.brand .val{color:var(--brand)}

/* Champions of the Month — packer / picker / host */
.champs{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:40px}
@media(max-width:900px){.champs{grid-template-columns:1fr}}
.potm{display:none;align-items:center;gap:16px;padding:20px 22px;background:linear-gradient(135deg,rgba(251,191,36,.12),rgba(245,158,11,.04));border:1px solid rgba(251,191,36,.22);border-radius:18px;text-decoration:none;color:inherit;transition:transform .2s,border-color .2s}
.potm.show{display:flex}
.potm:hover{transform:translateY(-2px);border-color:rgba(251,191,36,.4)}
.potm-icon{font-size:44px;line-height:1;filter:drop-shadow(0 6px 12px rgba(251,191,36,.3))}
.potm-text{flex:1;min-width:0}
.potm-lbl{font-size:11px;color:#b45309;text-transform:uppercase;letter-spacing:1.2px;font-weight:700;margin-bottom:3px}
.potm-name{font-size:20px;font-weight:800;color:#141b26;margin-bottom:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.potm-stats{font-size:12px;color:var(--text-muted)}
.potm-stats b{color:var(--text);font-weight:700}
.potm-arrow{font-size:18px;color:#b45309;font-weight:700}
.potm.pick{background:linear-gradient(135deg,rgba(99,102,241,.12),rgba(99,102,241,.04));border-color:rgba(99,102,241,.22)}
.potm.pick:hover{border-color:rgba(99,102,241,.42)}
.potm.pick .potm-lbl,.potm.pick .potm-arrow{color:#4f46e5}
.potm.pick .potm-icon{filter:drop-shadow(0 6px 12px rgba(99,102,241,.3))}
.potm.host{background:linear-gradient(135deg,rgba(124,58,237,.12),rgba(124,58,237,.04));border-color:rgba(124,58,237,.22)}
.potm.host:hover{border-color:rgba(124,58,237,.42)}
.potm.host .potm-lbl,.potm.host .potm-arrow{color:#7c3aed}
.potm.host .potm-icon{filter:drop-shadow(0 6px 12px rgba(124,58,237,.3))}

/* Fulfillment widget (admin/cs) — orders still to pick/pack by show */
.fulfil{display:none;margin-bottom:40px}
.fulfil.show{display:block}
.fulfil-panel{background:var(--surface);border:1px solid var(--border);border-radius:18px;padding:22px 24px}
.fulfil-head{display:flex;align-items:baseline;justify-content:space-between;gap:16px;margin-bottom:18px;flex-wrap:wrap}
.fulfil-head .ttl{font-size:14px;font-weight:800;color:var(--text-dim);text-transform:uppercase;letter-spacing:2px;display:flex;align-items:center;gap:10px}
.fulfil-head .ttl .dot{width:8px;height:8px;border-radius:50%;background:var(--brand)}
.fulfil-head a{color:var(--brand);text-decoration:none;font-size:12px;font-weight:700}
.fulfil-tiles{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:20px}
@media(max-width:560px){.fulfil-tiles{grid-template-columns:1fr}}
.ftile{border-radius:14px;padding:16px 18px;border:1px solid var(--border);background:rgba(17,24,39,0.032)}
.ftile.pack{background:linear-gradient(135deg,rgba(245,158,11,.12),rgba(245,158,11,.03));border-color:rgba(245,158,11,.22)}
.ftile.pick{background:linear-gradient(135deg,rgba(99,102,241,.12),rgba(99,102,241,.03));border-color:rgba(99,102,241,.22)}
.ftile .lbl{font-size:11px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.8px;font-weight:700}
.ftile .val{font-size:34px;font-weight:900;line-height:1;margin-top:8px;color:#141b26}
.ftile.pack .val{color:#b45309}.ftile.pick .val{color:#4f46e5}
.ftile .cap{font-size:12px;color:var(--text-muted);margin-top:5px}
.fulfil-rowhead,.fulfil-row{display:grid;grid-template-columns:1fr 78px 78px 130px;gap:12px;align-items:center}
.fulfil-rowhead{padding:0 6px 8px;font-size:10px;font-weight:800;color:var(--text-dim);text-transform:uppercase;letter-spacing:1px}
.fulfil-rowhead span:not(:first-child),.fulfil-row .n{text-align:center}
.fulfil-row{padding:12px 6px;border-top:1px solid var(--border);text-decoration:none;color:inherit;transition:background .12s}
.fulfil-row:hover{background:rgba(17,24,39,0.048)}
.fulfil-row .nm{font-size:14px;font-weight:700;color:#141b26;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.fulfil-row .n{font-size:17px;font-weight:800}
.fulfil-row .n.pack{color:#b45309}.fulfil-row .n.pick{color:#4f46e5}
.fulfil-row .n.zero{color:var(--text-dim);opacity:.5}
.fulfil-bar{height:8px;border-radius:5px;background:rgba(17,24,39,0.096);overflow:hidden;position:relative}
.fulfil-bar>i{display:block;height:100%;background:linear-gradient(90deg,#059669,#10b981);border-radius:5px}
.fulfil-bar .pct{position:absolute;right:0;top:-18px;font-size:10px;color:var(--text-dim);font-weight:700}
.fulfil-empty{padding:20px;text-align:center;color:var(--text-muted);font-size:14px}
.fulfil-empty b{color:#059669}

/* News strip on home — newest 2 announcements */
.news-strip{display:none;flex-direction:column;gap:10px;margin-bottom:32px}
.news-strip.show{display:flex}
.news-strip-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px}
.news-strip-title{font-size:13px;font-weight:800;color:var(--text-dim);text-transform:uppercase;letter-spacing:2px;display:flex;align-items:center;gap:10px}
.news-strip-title .dot{width:8px;height:8px;border-radius:50%;background:var(--brand)}
.news-strip-all{color:var(--brand);text-decoration:none;font-size:12px;font-weight:700;transition:color .15s}
.news-strip-all:hover{color:var(--brand-strong)}
.news-card{display:flex;gap:14px;padding:16px 20px;background:var(--surface);border:1px solid var(--border);border-radius:14px;text-decoration:none;color:inherit;transition:all .15s;align-items:flex-start}
.news-card:hover{border-color:rgba(217,116,143,.18);background:rgba(17,24,39,0.072);transform:translateY(-1px)}
.news-card.pri-important{border-left:3px solid #b45309}
.news-card.pri-urgent{border-left:3px solid #e11d48}
.news-card.pinned{background:linear-gradient(135deg,rgba(217,116,143,.06),rgba(217,116,143,.01))}
.news-icon{font-size:24px;line-height:1.2;flex-shrink:0}
.news-body{flex:1;min-width:0}
.news-title{font-size:15px;font-weight:700;color:#141b26;margin-bottom:3px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.news-meta{font-size:12px;color:var(--text-dim)}
.news-meta b{color:var(--text-muted);font-weight:600}
.tiny-pill{font-size:9px;padding:2px 7px;border-radius:5px;font-weight:700;letter-spacing:.5px;text-transform:uppercase}
.tiny-pill.pri-info{background:rgba(99,102,241,.14);color:#4f46e5}
.tiny-pill.pri-important{background:rgba(251,191,36,.16);color:#b45309}
.tiny-pill.pri-urgent{background:rgba(244,63,94,.16);color:#e11d48}
.tiny-pill.pinned{background:rgba(217,116,143,.16);color:var(--brand)}

/* Section heading */
.hub-section{margin-bottom:44px}
.section-head{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:18px;gap:16px}
.section-title{font-size:14px;font-weight:800;color:var(--text-dim);text-transform:uppercase;letter-spacing:2px;display:flex;align-items:center;gap:10px}
.section-title .dot{width:8px;height:8px;border-radius:50%;background:var(--brand)}
.section-sub{font-size:13px;color:var(--text-dim)}

/* Card grid */
.card-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
@media(max-width:900px){.card-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:560px){.card-grid{grid-template-columns:1fr}}

.card{position:relative;display:flex;flex-direction:column;padding:24px;background:var(--surface);border:1px solid var(--border);border-radius:18px;text-decoration:none;color:inherit;transition:all .2s;overflow:hidden;min-height:160px}
.card::before{content:'';position:absolute;inset:0;background:linear-gradient(135deg,transparent,rgba(217,116,143,.04));opacity:0;transition:opacity .2s;pointer-events:none}
.card:hover{transform:translateY(-3px);border-color:rgba(217,116,143,.22);background:rgba(17,24,39,0.072)}
.card:hover::before{opacity:1}
.card-icon{font-size:32px;margin-bottom:14px;line-height:1}
.card-title{font-size:17px;font-weight:800;color:#141b26;margin-bottom:6px}
.card-desc{font-size:13px;color:var(--text-muted);line-height:1.5;flex:1}
.card-meta{display:flex;justify-content:space-between;align-items:center;margin-top:14px;font-size:12px;color:var(--brand);font-weight:700}
.card-meta .arrow{transition:transform .2s}
.card:hover .card-meta .arrow{transform:translateX(4px)}
.card.disabled{opacity:.55;cursor:not-allowed;pointer-events:none}
.card.disabled .badge-soon{background:rgba(148,163,184,.12);color:var(--text-muted);padding:3px 9px;border-radius:6px;font-size:10px;font-weight:700;letter-spacing:.5px;text-transform:uppercase}
.card .pill-new{position:absolute;top:14px;right:14px;background:rgba(16,185,129,.16);color:#059669;padding:3px 9px;border-radius:6px;font-size:10px;font-weight:700;letter-spacing:.5px;text-transform:uppercase}
.card .pill-alert{position:absolute;top:14px;right:14px;background:rgba(245,158,11,.16);color:#b45309;padding:3px 9px;border-radius:6px;font-size:10px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;display:none}
.card.has-alert{border-color:rgba(245,158,11,.4);background:rgba(245,158,11,.06)}
.card.has-alert .pill-alert{display:block}

/* Role-based hide */
body[data-role="worker"] .hub-section-ops{display:none}

/* Worker hero CTA - giant "Start Packing" for workers */
body[data-role="worker"] .worker-cta{display:flex}
.worker-cta{display:none;align-items:center;gap:18px;padding:24px 28px;margin-bottom:36px;background:linear-gradient(135deg,var(--brand-glow),rgba(17,24,39,0.032));border:1px solid rgba(217,116,143,.3);border-radius:20px;text-decoration:none;color:inherit;transition:transform .2s}
.worker-cta:hover{transform:translateY(-2px);border-color:rgba(217,116,143,.45)}
.worker-cta-icon{font-size:48px}
.worker-cta-text{flex:1}
.worker-cta-text .ttl{font-size:22px;font-weight:800;color:#141b26;margin-bottom:4px}
.worker-cta-text .desc{font-size:14px;color:var(--text-muted)}
.worker-cta-arrow{font-size:32px;color:var(--brand);font-weight:300}
</style>
</head><body data-role="__ROLE__">
__NAVBAR__
<div class="wrap">
  <div class="hero">
    <div>
      <div class="greet-eyebrow" id="eyebrow">Welcome back</div>
      <div class="greet-title">Hello, <span class="name" id="name">there</span></div>
      <div class="greet-sub" id="sub">Loading your day…</div>
    </div>
    <div class="quick-stats" id="quickStats"></div>
  </div>

  <!-- Worker-only: huge Start Packing CTA -->
  <a href="/" class="worker-cta">
    <div class="worker-cta-icon">📦</div>
    <div class="worker-cta-text">
      <div class="ttl">Start Packing</div>
      <div class="desc">Open the recording station and log a package</div>
    </div>
    <div class="worker-cta-arrow">→</div>
  </a>

  <!-- Latest news -->
  <div class="news-strip" id="newsStrip">
    <div class="news-strip-head">
      <div class="news-strip-title"><span class="dot"></span>Latest news</div>
      <a href="/announcements" class="news-strip-all">View all →</a>
    </div>
    <div id="newsList"></div>
  </div>

  <!-- Champions of the Month -->
  <div class="champs">
  <a href="/leaderboard" class="potm" id="potm">
    <div class="potm-icon">👑</div>
    <div class="potm-text">
      <div class="potm-lbl">Packer of the Month</div>
      <div class="potm-name" id="potmName">—</div>
      <div class="potm-stats"><b id="potmCount">0</b> packages · avg <b id="potmAvg">0s</b></div>
    </div>
    <div class="potm-arrow">→</div>
  </a>
  <a href="/admin/packer-analytics" class="potm pick" id="pickotm">
    <div class="potm-icon">🧺</div>
    <div class="potm-text">
      <div class="potm-lbl">Picker of the Month</div>
      <div class="potm-name" id="pickotmName">—</div>
      <div class="potm-stats"><b id="pickotmCount">0</b> orders · <b id="pickotmDays">0</b> active days</div>
    </div>
    <div class="potm-arrow">→</div>
  </a>
  <a href="/admin/hosts" class="potm host" id="hostotm">
    <div class="potm-icon">🎤</div>
    <div class="potm-text">
      <div class="potm-lbl">Top Seller of the Month</div>
      <div class="potm-name" id="hostotmName">—</div>
      <div class="potm-stats"><b id="hostotmShows">0</b> shows this month</div>
    </div>
    <div class="potm-arrow">→</div>
  </a>
  </div>

  <!-- Fulfillment widget (admin/cs) — orders still to pick/pack, by show -->
  <div class="fulfil hub-section-ops" id="fulfil">
    <div class="fulfil-panel">
      <div class="fulfil-head">
        <div class="ttl"><span class="dot"></span>Fulfillment · last 5 days</div>
        <a href="/admin/shows">Open Shows →</a>
      </div>
      <div class="fulfil-tiles">
        <div class="ftile pack"><div class="lbl">Orders to pack</div><div class="val" id="fTotalPack">0</div><div class="cap" id="fShowsCap">across 0 shows</div></div>
        <div class="ftile pick"><div class="lbl">Orders to pull</div><div class="val" id="fTotalPick">0</div><div class="cap">still need picking</div></div>
        <div class="ftile"><div class="lbl">Shows in progress</div><div class="val" id="fShowsRemain">0</div><div class="cap">with packing left</div></div>
      </div>
      <div id="fulfilList"></div>
    </div>
  </div>

  <!-- Workspace section (admin/cs only) — clean shortcuts into the new IA -->
  <section class="hub-section hub-section-ops">
    <div class="section-head">
      <div class="section-title"><span class="dot"></span>Workspace</div>
      <div class="section-sub">Your daily warehouse shortcuts</div>
    </div>
    <div class="card-grid">
      <a href="/operations" class="card" id="cardOps">
        <span class="pill-alert" id="opsAlert"></span>
        <div class="card-icon">📦</div>
        <div class="card-title">Operations</div>
        <div class="card-desc">Shows, shipments, picking, recordings and insights — all warehouse tools grouped in one place.</div>
        <div class="card-meta"><span id="opsMeta">Open operations</span><span class="arrow">→</span></div>
      </a>
      <a href="/giveaway" class="card">
        <div class="card-icon">🎁</div>
        <div class="card-title">Giveaways</div>
        <div class="card-desc">Winners, shipping addresses and label printing.</div>
        <div class="card-meta"><span>Open queue</span><span class="arrow">→</span></div>
      </a>
      <a href="/shipping-status" class="card">
        <div class="card-icon">🚚</div>
        <div class="card-title">Shipping Status</div>
        <div class="card-desc">Live USPS tracking across every open package.</div>
        <div class="card-meta"><span>View tracking</span><span class="arrow">→</span></div>
      </a>
    </div>
  </section>

  <!-- Personal section (everyone) -->
  <section class="hub-section">
    <div class="section-head">
      <div class="section-title"><span class="dot"></span>Personal</div>
      <div class="section-sub">Your stats, documents and paperwork</div>
    </div>
    <div class="card-grid">
      <a href="/me" class="card">
        <div class="card-icon">👤</div>
        <div class="card-title">My Profile</div>
        <div class="card-desc">Your packing stats, achievements, and recent activity</div>
        <div class="card-meta"><span>Open profile</span><span class="arrow">→</span></div>
      </a>
      <a href="/leaderboard" class="card">
        <div class="card-icon">🏆</div>
        <div class="card-title">Leaderboard</div>
        <div class="card-desc">See who is leading the team this week and month</div>
        <div class="card-meta"><span>View ranking</span><span class="arrow">→</span></div>
      </a>
      <a href="/documents" class="card">
        <div class="card-icon">📄</div>
        <div class="card-title">Documents</div>
        <div class="card-desc">Policies, pay stubs, contracts and personal records</div>
        <div class="card-meta"><span>Open files</span><span class="arrow">→</span></div>
      </a>
      <a href="/onboarding" class="card">
        <div class="card-icon">🎓</div>
        <div class="card-title">Onboarding</div>
        <div class="card-desc">Checklist to get fully set up — required tasks and training</div>
        <div class="card-meta"><span>Open checklist</span><span class="arrow">→</span></div>
      </a>
    </div>
  </section>
</div>

<script>
// Time-of-day greeting
(function(){
  var h=new Date().getHours();
  var eb=document.getElementById('eyebrow');
  if(h<5)eb.textContent='Late night shift';
  else if(h<12)eb.textContent='Good morning';
  else if(h<17)eb.textContent='Good afternoon';
  else if(h<22)eb.textContent='Good evening';
  else eb.textContent='Working late';
})();

var role=document.body.dataset.role;

// Surface pending table-cleanup work on the Operations card so the manager sees
// it before opening anything else. If any show is dirty, badge the card.
if(role==='admin'||role==='cs'){
  fetch('/api/cleanup/shows').then(function(r){return r.json()}).then(function(shows){
    if(!Array.isArray(shows))return;
    var dirty=shows.filter(function(s){return !s.is_clean && s.total_groups>0});
    var card=document.getElementById('cardOps');
    var meta=document.getElementById('opsMeta');
    var alert=document.getElementById('opsAlert');
    if(card && dirty.length>0){
      card.classList.add('has-alert');
      var totalPending=dirty.reduce(function(sum,s){return sum+s.groups_pending},0);
      if(alert)alert.textContent='⚠ '+totalPending+' to clean';
      if(meta)meta.innerHTML='<b style="color:#b45309">'+totalPending+'</b> cleanup pending · '+dirty.length+' show'+(dirty.length===1?'':'s');
    }
  }).catch(function(){});
}

// Fulfillment widget: orders still to pick/pack, broken down by show
function homeEsc(s){var d=document.createElement('div');d.textContent=(s==null?'':String(s));return d.innerHTML}
if(role==='admin'||role==='cs'){
  fetch('/api/home/fulfillment').then(function(r){return r.json()}).then(function(d){
    if(!d||!d.shows)return;
    document.getElementById('fulfil').classList.add('show');
    document.getElementById('fTotalPack').textContent=d.total_to_pack;
    document.getElementById('fTotalPick').textContent=d.total_to_pick;
    document.getElementById('fShowsRemain').textContent=d.shows_remaining;
    document.getElementById('fShowsCap').textContent='across '+d.shows_remaining+' show'+(d.shows_remaining===1?'':'s');
    var list=document.getElementById('fulfilList');
    if(d.shows.length===0){
      list.innerHTML='<div class="fulfil-empty">🎉 <b>All caught up</b> — every recent show is fully packed.</div>';
      return;
    }
    var head='<div class="fulfil-rowhead"><span>Show</span><span>To pull</span><span>To pack</span><span>Packed</span></div>';
    var rows=d.shows.map(function(s){
      var done=s.packed+s.shipped, denom=(s.total-s.cancelled)||1;
      var pct=Math.round(done/denom*100);
      return '<a class="fulfil-row" href="/admin/shows">'+
        '<div class="nm" title="'+homeEsc(s.name)+'">'+homeEsc(s.name)+'</div>'+
        '<div class="n pick'+(s.to_pick?'':' zero')+'">'+s.to_pick+'</div>'+
        '<div class="n pack'+(s.to_pack?'':' zero')+'">'+s.to_pack+'</div>'+
        '<div class="fulfil-bar"><span class="pct">'+pct+'%</span><i style="width:'+pct+'%"></i></div>'+
        '</a>';
    }).join('');
    list.innerHTML=head+rows;
  }).catch(function(){});
}

// Load my stats for the hero
fetch('/api/me/stats').then(function(r){return r.json()}).then(function(d){
  document.getElementById('name').textContent=d.name||'there';
  var sub=document.getElementById('sub');
  if(d.this_month && d.this_month.count>0){
    var msg='You have logged <b style="color:var(--text)">'+d.this_month.count+'</b> packages this month';
    if(d.rank_this_month) msg+=' · currently ranked <b style="color:var(--brand)">#'+d.rank_this_month+'</b>';
    sub.innerHTML=msg;
  } else {
    sub.textContent='No packages yet this month — let\\'s get started';
  }
  // Quick stats pills
  var qs=document.getElementById('quickStats');
  qs.innerHTML=
    '<div class="qs"><div class="lbl">Today</div><div class="val">'+(d.today?d.today.count:0)+'</div></div>'+
    '<div class="qs brand"><div class="lbl">This month</div><div class="val">'+(d.this_month?d.this_month.count:0)+'</div></div>'+
    '<div class="qs"><div class="lbl">All time</div><div class="val">'+(d.all_time?d.all_time.count:0)+'</div></div>';
});

// Champions of the Month — packer / picker / host
fetch('/api/packer-of-month').then(function(r){return r.json()}).then(function(d){
  if(!d||!d.name)return;
  document.getElementById('potmName').textContent=d.name;
  document.getElementById('potmCount').textContent=d.count;
  document.getElementById('potmAvg').textContent=(d.avg_dur||0)+'s';
  document.getElementById('potm').classList.add('show');
});
fetch('/api/picker-of-month').then(function(r){return r.json()}).then(function(d){
  if(!d||!d.name)return;
  document.getElementById('pickotmName').textContent=d.name;
  document.getElementById('pickotmCount').textContent=(d.count||0).toLocaleString();
  document.getElementById('pickotmDays').textContent=d.days||0;
  document.getElementById('pickotm').classList.add('show');
});
fetch('/api/host-of-month').then(function(r){return r.ok?r.json():null}).then(function(d){
  if(!d||!d.name)return;
  document.getElementById('hostotmName').textContent=d.name;
  document.getElementById('hostotmShows').textContent=d.shows||0;
  document.getElementById('hostotm').classList.add('show');
}).catch(function(){});

// Load latest news (top 2)
function homeEscapeHtml(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function homeFmtTime(s){
  if(!s)return '';
  try{var d=new Date(s);var diff=(new Date()-d)/1000;
    if(diff<60)return 'just now';if(diff<3600)return Math.floor(diff/60)+'m ago';
    if(diff<86400)return Math.floor(diff/3600)+'h ago';if(diff<604800)return Math.floor(diff/86400)+'d ago';
    return d.toLocaleDateString(undefined,{month:'short',day:'numeric'})
  }catch(e){return ''}
}
fetch('/api/announcements?limit=2').then(function(r){return r.json()}).then(function(arr){
  if(!arr||arr.length===0)return;
  var icons={info:'📣',important:'⚠️',urgent:'🔴'};
  document.getElementById('newsList').innerHTML=arr.map(function(a){
    var pills='<span class="tiny-pill pri-'+a.priority+'">'+a.priority+'</span>';
    if(a.pinned)pills+='<span class="tiny-pill pinned">📌 Pinned</span>';
    return '<a href="/announcements" class="news-card pri-'+a.priority+(a.pinned?' pinned':'')+'">'+
      '<div class="news-icon">'+(icons[a.priority]||'📣')+'</div>'+
      '<div class="news-body">'+
        '<div class="news-title">'+homeEscapeHtml(a.title)+pills+'</div>'+
        '<div class="news-meta">Posted by <b>'+homeEscapeHtml(a.author)+'</b> · '+homeFmtTime(a.created_at)+'</div>'+
      '</div></a>';
  }).join('');
  document.getElementById('newsStrip').classList.add('show');
});
</script>
</body></html>'''


# ══════════════════════════════════════════════════════════
# DOCUMENT LIBRARY — categorized file repository
# ══════════════════════════════════════════════════════════

DOCUMENTS_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Documents — __BRANDMARK__ Employee Hub</title>
__NAVBAR_CSS__
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'DM Sans',-apple-system,sans-serif;background:#ffffff;color:var(--text);min-height:100vh;padding-bottom:120px;-webkit-font-smoothing:antialiased}
.wrap{max-width:1100px;margin:0 auto;padding:40px 28px 0}
.page-head{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;margin-bottom:28px;flex-wrap:wrap}
.page-title{font-size:36px;font-weight:900;color:#141b26;letter-spacing:-.5px;line-height:1.05}
.page-sub{color:var(--text-muted);margin-top:6px;font-size:14px}
.upload-btn{background:var(--brand);color:#1a0e0b;border:none;border-radius:12px;padding:12px 22px;font-size:14px;font-weight:800;cursor:pointer;font-family:inherit;transition:all .15s;display:inline-flex;align-items:center;gap:8px;box-shadow:0 6px 22px rgba(217,116,143,.15)}
.upload-btn:hover{background:var(--brand-strong);transform:translateY(-1px)}
body[data-role="admin"] .admin-only{display:inline-flex}
.admin-only{display:none}

/* Category tabs */
.tabs{display:flex;gap:4px;background:rgba(17,24,39,0.048);padding:5px;border-radius:12px;border:1px solid var(--border);margin-bottom:28px;max-width:fit-content;flex-wrap:wrap}
.tab{padding:9px 18px;border-radius:8px;font-size:13px;font-weight:600;color:var(--text-muted);cursor:pointer;transition:all .15s;background:transparent;border:none;font-family:inherit;display:flex;align-items:center;gap:6px}
.tab:hover{color:var(--text)}
.tab.active{background:var(--brand-glow);color:var(--brand)}
.tab .count{font-size:11px;background:rgba(17,24,39,0.096);padding:2px 7px;border-radius:6px;font-weight:700}
.tab.active .count{background:rgba(217,116,143,.2)}

/* Doc list */
.doc-list{display:flex;flex-direction:column;gap:10px}
.doc{display:grid;grid-template-columns:48px 1fr auto;gap:16px;align-items:center;padding:18px 22px;background:var(--surface);border:1px solid var(--border);border-radius:14px;transition:all .15s}
.doc:hover{border-color:rgba(217,116,143,.18);background:rgba(17,24,39,0.072)}
.doc-icon{width:48px;height:48px;border-radius:12px;background:rgba(217,116,143,.1);display:flex;align-items:center;justify-content:center;font-size:24px;flex-shrink:0}
.doc-info{min-width:0}
.doc-title{font-size:15px;font-weight:700;color:#141b26;margin-bottom:3px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.doc-desc{font-size:13px;color:var(--text-muted);line-height:1.4;margin-bottom:6px;overflow:hidden;text-overflow:ellipsis;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.doc-meta{font-size:11px;color:var(--text-dim);display:flex;gap:14px;flex-wrap:wrap;align-items:center}
.doc-meta b{color:var(--text-muted);font-weight:600}
.vis-pill{font-size:10px;padding:2px 8px;border-radius:6px;font-weight:700;letter-spacing:.4px;text-transform:uppercase}
.vis-all{background:rgba(16,185,129,.12);color:#059669}
.vis-admin_cs{background:rgba(99,102,241,.14);color:#4f46e5}
.vis-admin{background:rgba(244,63,94,.12);color:#e11d48}
.vis-personal{background:rgba(245,158,11,.14);color:#b45309}
.doc-actions{display:flex;gap:8px;align-items:center}
.dl{background:var(--brand-glow);color:var(--brand);text-decoration:none;font-size:13px;font-weight:700;padding:9px 16px;border-radius:9px;transition:all .15s;border:1px solid rgba(217,116,143,.18);display:inline-flex;align-items:center;gap:6px}
.dl:hover{background:rgba(217,116,143,.2)}
.del{background:rgba(244,63,94,.08);color:#e11d48;border:1px solid rgba(244,63,94,.18);border-radius:9px;padding:9px 12px;font-size:13px;font-weight:700;cursor:pointer;transition:all .15s;font-family:inherit;display:none}
body[data-role="admin"] .del{display:inline-flex}
.del:hover{background:rgba(244,63,94,.16)}
.empty{text-align:center;padding:80px 20px;color:var(--text-dim)}
.empty-icon{font-size:56px;margin-bottom:14px;opacity:.5}
.empty-title{font-size:18px;font-weight:700;color:var(--text-muted);margin-bottom:6px}
.empty-sub{font-size:14px}

/* Modal */
.modal-bg{position:fixed;inset:0;background:rgba(0,0,0,.65);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);z-index:200;display:none;align-items:center;justify-content:center;padding:20px}
.modal-bg.show{display:flex}
.modal{background:#f6f7f9;border:1px solid var(--border);border-radius:20px;padding:32px;max-width:520px;width:100%;max-height:90vh;overflow-y:auto}
.modal h3{font-size:22px;font-weight:800;margin-bottom:6px;color:#141b26}
.modal .modal-sub{color:var(--text-muted);font-size:13px;margin-bottom:24px}
.fld{margin-bottom:16px}
.fld label{display:block;font-size:11px;font-weight:700;color:var(--text-muted);margin-bottom:7px;text-transform:uppercase;letter-spacing:.6px}
.fld input[type="text"],.fld textarea,.fld select{width:100%;background:#ffffff;border:1px solid var(--border);border-radius:10px;padding:11px 14px;font-size:14px;color:var(--text);font-family:inherit;outline:none;transition:all .2s}
.fld input[type="text"]:focus,.fld textarea:focus,.fld select:focus{border-color:var(--brand);box-shadow:0 0 0 3px rgba(217,116,143,.1)}
.fld textarea{resize:vertical;min-height:80px}
.fld input[type="file"]{width:100%;color:var(--text-muted);font-size:13px;padding:9px;background:#ffffff;border:1px dashed var(--border);border-radius:10px;cursor:pointer;font-family:inherit}
.fld input[type="file"]::file-selector-button{background:var(--brand);color:#1a0e0b;border:none;border-radius:8px;padding:6px 14px;margin-right:10px;font-size:12px;font-weight:700;cursor:pointer;font-family:inherit}
.fld-row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.modal-actions{display:flex;justify-content:flex-end;gap:10px;margin-top:24px}
.btn-cancel{background:transparent;color:var(--text-muted);border:1px solid var(--border);border-radius:10px;padding:10px 18px;font-size:14px;font-weight:600;cursor:pointer;font-family:inherit}
.btn-cancel:hover{color:var(--text);background:rgba(17,24,39,0.064)}
.btn-submit{background:var(--brand);color:#1a0e0b;border:none;border-radius:10px;padding:10px 22px;font-size:14px;font-weight:800;cursor:pointer;font-family:inherit;transition:all .15s}
.btn-submit:hover{background:var(--brand-strong)}
.btn-submit:disabled{opacity:.5;cursor:not-allowed}
.modal-err{color:#f43f5e;font-size:13px;margin-top:12px;min-height:18px}
.personal-row{display:none}
.personal-row.show{display:block}
</style>
</head><body data-role="__ROLE__">
__NAVBAR__
<div class="wrap">
  <div class="page-head">
    <div>
      <div class="page-title">📂 Documents</div>
      <div class="page-sub">Company policies, personal records, and onboarding materials</div>
    </div>
    <button class="upload-btn admin-only" id="openUpload">＋ Upload document</button>
  </div>

  <div class="tabs" id="tabs">
    <button class="tab active" data-cat="all">All <span class="count" id="cnt-all">0</span></button>
    <button class="tab" data-cat="policies">📋 Policies <span class="count" id="cnt-policies">0</span></button>
    <button class="tab" data-cat="personal">📄 Personal <span class="count" id="cnt-personal">0</span></button>
    <button class="tab" data-cat="onboarding">🎓 Onboarding <span class="count" id="cnt-onboarding">0</span></button>
    <button class="tab" data-cat="other">📎 Other <span class="count" id="cnt-other">0</span></button>
  </div>

  <div class="doc-list" id="docList"></div>
</div>

<!-- Upload modal (admin only) -->
<div class="modal-bg" id="modal">
  <div class="modal">
    <h3>Upload document</h3>
    <div class="modal-sub">PDFs, Word docs, spreadsheets, or images — max 50MB.</div>
    <div class="fld">
      <label>File</label>
      <input type="file" id="upFile">
    </div>
    <div class="fld">
      <label>Title</label>
      <input type="text" id="upTitle" placeholder="Employee Handbook 2026">
    </div>
    <div class="fld">
      <label>Description (optional)</label>
      <textarea id="upDesc" placeholder="Updated policies on time off, conduct, and safety."></textarea>
    </div>
    <div class="fld-row">
      <div class="fld">
        <label>Category</label>
        <select id="upCategory">
          <option value="policies">📋 Policies</option>
          <option value="onboarding">🎓 Onboarding</option>
          <option value="personal">📄 Personal</option>
          <option value="other">📎 Other</option>
        </select>
      </div>
      <div class="fld">
        <label>Visibility</label>
        <select id="upVis">
          <option value="all">Everyone</option>
          <option value="admin_cs">Admin & CS only</option>
          <option value="admin">Admin only</option>
          <option value="personal">One specific user</option>
        </select>
      </div>
    </div>
    <div class="fld personal-row" id="personalRow">
      <label>Send to user</label>
      <select id="upUser"><option value="">Loading users…</option></select>
    </div>
    <div class="modal-err" id="modalErr"></div>
    <div class="modal-actions">
      <button class="btn-cancel" id="cancelUpload">Cancel</button>
      <button class="btn-submit" id="doUpload">Upload</button>
    </div>
  </div>
</div>

<script>
var allDocs=[],currentCat='all';

function fmtSize(b){if(!b)return '—';var u=['B','KB','MB','GB'];var i=0;while(b>=1024&&i<3){b/=1024;i++}return b.toFixed(b<10?1:0)+' '+u[i]}
function fmtDate(s){if(!s)return '';try{var d=new Date(s);return d.toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'})}catch(e){return s}}
function iconFor(fn){var x=(fn||'').toLowerCase().split('.').pop();if(x==='pdf')return '📕';if(x==='doc'||x==='docx')return '📘';if(x==='xls'||x==='xlsx'||x==='csv')return '📗';if(x==='png'||x==='jpg'||x==='jpeg'||x==='gif')return '🖼️';if(x==='txt')return '📝';return '📄'}
function visLabel(v){if(v==='all')return 'Everyone';if(v==='admin_cs')return 'Admin & CS';if(v==='admin')return 'Admin only';if(v&&v.indexOf('personal:')===0)return 'Personal · '+v.slice(9);return v}
function visClass(v){if(v==='all')return 'vis-all';if(v==='admin_cs')return 'vis-admin_cs';if(v==='admin')return 'vis-admin';if(v&&v.indexOf('personal:')===0)return 'vis-personal';return 'vis-all'}

function load(){
  fetch('/api/documents').then(function(r){return r.json()}).then(function(d){
    allDocs=d||[];
    var counts={all:allDocs.length,policies:0,personal:0,onboarding:0,other:0};
    allDocs.forEach(function(x){if(counts[x.category]!==undefined)counts[x.category]++});
    Object.keys(counts).forEach(function(c){var el=document.getElementById('cnt-'+c);if(el)el.textContent=counts[c]});
    render();
  });
}

function render(){
  var list=document.getElementById('docList');
  var docs=allDocs.filter(function(x){return currentCat==='all'||x.category===currentCat});
  if(docs.length===0){
    list.innerHTML='<div class="empty"><div class="empty-icon">📂</div><div class="empty-title">No documents here yet</div><div class="empty-sub">'+(document.body.dataset.role==='admin'?'Click "Upload document" to add the first one.':'Check back soon.')+'</div></div>';
    return;
  }
  list.innerHTML=docs.map(function(d){
    return '<div class="doc"><div class="doc-icon">'+iconFor(d.filename)+'</div>'+
      '<div class="doc-info"><div class="doc-title">'+escapeHtml(d.title)+
        '<span class="vis-pill '+visClass(d.visibility)+'">'+visLabel(d.visibility)+'</span></div>'+
      (d.description?'<div class="doc-desc">'+escapeHtml(d.description)+'</div>':'')+
      '<div class="doc-meta"><span>'+escapeHtml(d.filename)+'</span>·<span>'+fmtSize(d.size_bytes)+'</span>·<span>by <b>'+escapeHtml(d.uploaded_by)+'</b></span>·<span>'+fmtDate(d.uploaded_at)+'</span></div></div>'+
      '<div class="doc-actions">'+
        '<a href="/documents/dl/'+d.id+'" class="dl">⬇ Download</a>'+
        '<button class="del" data-id="'+d.id+'" title="Delete">🗑</button>'+
      '</div></div>';
  }).join('');
  list.querySelectorAll('.del').forEach(function(b){
    b.addEventListener('click',function(){
      if(!confirm('Delete this document permanently?'))return;
      fetch('/api/documents/'+b.dataset.id+'/delete',{method:'POST'}).then(function(r){return r.json()}).then(function(d){
        if(d.ok)load();else alert(d.error||'Delete failed');
      });
    });
  });
}

function escapeHtml(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}

// Tabs
document.querySelectorAll('.tab').forEach(function(t){
  t.addEventListener('click',function(){
    currentCat=t.dataset.cat;
    document.querySelectorAll('.tab').forEach(function(x){x.classList.toggle('active',x===t)});
    render();
  });
});

// Initial category from URL ?cat=
var urlCat=new URLSearchParams(location.search).get('cat');
if(urlCat){
  var tab=document.querySelector('.tab[data-cat="'+urlCat+'"]');
  if(tab)tab.click();
}

// Upload modal
var modal=document.getElementById('modal');
var openBtn=document.getElementById('openUpload');
if(openBtn){
  openBtn.addEventListener('click',function(){
    document.getElementById('modalErr').textContent='';
    modal.classList.add('show');
    if(document.getElementById('upUser').options.length<=1){
      fetch('/api/users').then(function(r){return r.json()}).then(function(u){
        var sel=document.getElementById('upUser');
        sel.innerHTML='<option value="">— pick a user —</option>'+
          Object.keys(u).map(function(uid){return '<option value="'+uid+'">'+u[uid].name+' ('+uid+')</option>'}).join('');
      });
    }
  });
  document.getElementById('cancelUpload').addEventListener('click',function(){modal.classList.remove('show')});
  modal.addEventListener('click',function(e){if(e.target===modal)modal.classList.remove('show')});
  document.getElementById('upVis').addEventListener('change',function(e){
    document.getElementById('personalRow').classList.toggle('show',e.target.value==='personal');
  });
  document.getElementById('doUpload').addEventListener('click',function(){
    var f=document.getElementById('upFile').files[0];
    var title=document.getElementById('upTitle').value.trim();
    if(!f){document.getElementById('modalErr').textContent='Pick a file';return}
    if(!title){document.getElementById('modalErr').textContent='Title is required';return}
    var fd=new FormData();
    fd.append('file',f);
    fd.append('title',title);
    fd.append('description',document.getElementById('upDesc').value.trim());
    fd.append('category',document.getElementById('upCategory').value);
    fd.append('visibility',document.getElementById('upVis').value);
    fd.append('personal_user',document.getElementById('upUser').value);
    var btn=document.getElementById('doUpload');btn.disabled=true;btn.textContent='Uploading…';
    fetch('/api/documents/upload',{method:'POST',body:fd}).then(function(r){return r.json()}).then(function(d){
      btn.disabled=false;btn.textContent='Upload';
      if(d.ok){
        modal.classList.remove('show');
        document.getElementById('upFile').value='';
        document.getElementById('upTitle').value='';
        document.getElementById('upDesc').value='';
        load();
      } else {
        document.getElementById('modalErr').textContent=d.error||'Upload failed';
      }
    });
  });
}

load();
</script>
</body></html>'''


# ══════════════════════════════════════════════════════════
# WELCOME — post-login choice between Portal and Packing
# Shown after password login for workers only (admin/cs skip)
# Badge login stays on the fast path (badge → packing direct)
# ══════════════════════════════════════════════════════════

WELCOME_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Welcome — __BRANDMARK__</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'DM Sans',-apple-system,sans-serif;background:#ffffff;color:#1a2130;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:32px 24px;-webkit-font-smoothing:antialiased;position:relative;overflow:hidden}
body::before{content:'';position:fixed;inset:0;background:radial-gradient(900px 600px at 20% 0%, rgba(217,116,143,.08), transparent 60%),radial-gradient(800px 600px at 80% 100%, rgba(99,102,241,.06), transparent 60%);pointer-events:none;z-index:-1}
.brand{text-align:center;margin-bottom:40px}
.brand-mark{font-size:28px;font-weight:900;color:#d9748f;letter-spacing:2.2px;line-height:1;text-shadow:0 4px 18px rgba(217,116,143,.2)}
.brand-sub{font-size:9px;font-weight:700;color:#6b7280;letter-spacing:2.8px;text-transform:uppercase;margin-top:5px}
.greet{text-align:center;margin-bottom:8px}
.greet-eyebrow{font-size:12px;font-weight:700;color:#d9748f;text-transform:uppercase;letter-spacing:2.2px;margin-bottom:8px}
.greet-name{font-size:38px;font-weight:900;color:#141b26;line-height:1.1;letter-spacing:-.8px}
.greet-name b{background:linear-gradient(135deg,#d9748f,#c25c79);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
.greet-prompt{font-size:15px;color:#586274;margin-top:14px;margin-bottom:44px}
.choices{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:18px;max-width:720px;width:100%}
.choice{background:rgba(17,24,39,0.048);border:1px solid rgba(17,24,39,0.112);border-radius:22px;padding:36px 28px;text-decoration:none;color:inherit;display:flex;flex-direction:column;align-items:flex-start;gap:14px;transition:all .25s cubic-bezier(.4,0,.2,1);position:relative;overflow:hidden;min-height:260px;cursor:pointer}
.choice::after{content:'';position:absolute;inset:0;background:linear-gradient(135deg,transparent 60%, rgba(217,116,143,.08));opacity:0;transition:opacity .25s;pointer-events:none}
.choice:hover{transform:translateY(-4px);border-color:rgba(217,116,143,.3);background:rgba(17,24,39,0.08)}
.choice:hover::after{opacity:1}
.choice.pack{background:linear-gradient(135deg,rgba(99,102,241,.14),rgba(168,85,247,.06));border-color:rgba(99,102,241,.3)}
.choice.pack:hover{border-color:rgba(99,102,241,.5)}
.choice.pick{background:linear-gradient(135deg,rgba(16,185,129,.12),rgba(20,184,166,.04));border-color:rgba(16,185,129,.3)}
.choice.pick:hover{border-color:rgba(16,185,129,.5)}
.choice.pick .choice-cta{color:#059669}
.choice-icon{font-size:64px;line-height:1;margin-bottom:6px}
.choice-label{font-size:11px;font-weight:700;color:#586274;text-transform:uppercase;letter-spacing:1.5px}
.choice-title{font-size:26px;font-weight:900;color:#141b26;letter-spacing:-.4px;line-height:1.1}
.choice-desc{font-size:14px;color:#586274;line-height:1.5;flex:1}
.choice-cta{display:flex;align-items:center;gap:8px;color:#d9748f;font-size:13px;font-weight:800;letter-spacing:.5px;text-transform:uppercase;margin-top:6px}
.choice.pack .choice-cta{color:#4f46e5}
.choice-cta .arrow{transition:transform .2s}
.choice:hover .choice-cta .arrow{transform:translateX(6px)}
.footer-link{margin-top:32px;font-size:12px;color:#6b7280;text-align:center}
.footer-link a{color:#586274;text-decoration:none;border-bottom:1px dotted rgba(155,169,193,.3);transition:color .15s}
.footer-link a:hover{color:#1a2130}
@media(max-width:560px){
  .greet-name{font-size:30px}
  .choice{min-height:200px;padding:28px 22px}
  .choice-icon{font-size:48px}
  .choice-title{font-size:22px}
}
</style>
</head><body>
<div class="brand">
  <div class="brand-mark">5&nbsp;SEC</div>
  <div class="brand-sub">Employee Hub</div>
</div>
<div class="greet">
  <div class="greet-eyebrow" id="eyebrow">Welcome back</div>
  <div class="greet-name">Hello, <b>__NAME__</b></div>
  <div class="greet-prompt">What would you like to do?</div>
</div>
<div class="choices">
  <a href="/pick" class="choice pick">
    <div class="choice-icon">📋</div>
    <div class="choice-label">Collecting items</div>
    <div class="choice-title">Start Picking</div>
    <div class="choice-desc">Walk the floor, pull items off the tables — touch-friendly checklist for iPad.</div>
    <div class="choice-cta">Open picker <span class="arrow">→</span></div>
  </a>
  <a href="/pack-start" class="choice pack">
    <div class="choice-icon">📦</div>
    <div class="choice-label">For your shift</div>
    <div class="choice-title">Start Packing</div>
    <div class="choice-desc">Open the recording station and log packages by tracking number.</div>
    <div class="choice-cta">Open station <span class="arrow">→</span></div>
  </a>
  <a href="/home" class="choice portal">
    <div class="choice-icon">🏠</div>
    <div class="choice-label">Personal area</div>
    <div class="choice-title">Open Portal</div>
    <div class="choice-desc">Your stats, leaderboard ranking, documents, and team updates.</div>
    <div class="choice-cta">Browse portal <span class="arrow">→</span></div>
  </a>
</div>
<div class="footer-link"><a href="/logout">Not you? Log out</a></div>
<script>
(function(){
  var h=new Date().getHours();
  var eb=document.getElementById('eyebrow');
  if(h<5)eb.textContent='Late night shift';
  else if(h<12)eb.textContent='Good morning';
  else if(h<17)eb.textContent='Good afternoon';
  else if(h<22)eb.textContent='Good evening';
  else eb.textContent='Working late';
})();
</script>
</body></html>'''


# ══════════════════════════════════════════════════════════
# ONBOARDING CHECKLIST — new-hire task tracker
# Employee view (their list) + admin view (team progress + manage tasks)
# ══════════════════════════════════════════════════════════

ONBOARDING_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Onboarding — __BRANDMARK__</title>
__NAVBAR_CSS__
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'DM Sans',-apple-system,sans-serif;background:#ffffff;color:var(--text);min-height:100vh;padding-bottom:120px;-webkit-font-smoothing:antialiased}
.wrap{max-width:1000px;margin:0 auto;padding:40px 28px 0}

/* Hero / progress */
.hero{background:linear-gradient(135deg,rgba(217,116,143,.1),rgba(217,116,143,.02));border:1px solid rgba(217,116,143,.18);border-radius:20px;padding:28px;margin-bottom:32px}
.hero-eyebrow{font-size:11px;font-weight:700;color:var(--brand);text-transform:uppercase;letter-spacing:2px;margin-bottom:6px}
.hero-title{font-size:32px;font-weight:900;color:#141b26;letter-spacing:-.5px;margin-bottom:6px}
.hero-sub{font-size:14px;color:var(--text-muted);margin-bottom:18px}
.progress-row{display:flex;align-items:center;gap:18px;flex-wrap:wrap}
.progress-bar{flex:1;height:12px;background:rgba(17,24,39,0.096);border-radius:8px;overflow:hidden;min-width:200px}
.progress-fill{height:100%;background:linear-gradient(90deg,var(--brand),var(--brand-strong));border-radius:8px;transition:width .4s cubic-bezier(.4,0,.2,1)}
.progress-text{font-size:14px;color:var(--text);font-weight:700;white-space:nowrap}
.progress-text b{color:var(--brand);font-size:18px;font-weight:900}
.complete-badge{display:inline-flex;align-items:center;gap:6px;background:rgba(16,185,129,.14);color:#059669;padding:5px 12px;border-radius:20px;font-size:12px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;margin-top:10px}
.complete-badge.show{display:inline-flex}

/* Sections */
.section-title{font-size:13px;font-weight:800;color:var(--text-dim);text-transform:uppercase;letter-spacing:2px;display:flex;align-items:center;gap:10px;margin:36px 0 14px}
.section-title .dot{width:8px;height:8px;border-radius:50%;background:var(--brand)}

/* Task list */
.task-list{display:flex;flex-direction:column;gap:10px}
.task{display:flex;align-items:flex-start;gap:14px;padding:18px 22px;background:var(--surface);border:1px solid var(--border);border-radius:14px;transition:all .15s;cursor:pointer}
.task:hover{border-color:rgba(217,116,143,.18);background:rgba(17,24,39,0.072)}
.task.done{opacity:.6}
.task.done .task-title{text-decoration:line-through;color:var(--text-muted)}
.task-check{width:24px;height:24px;border-radius:50%;border:2px solid rgba(17,24,39,0.16);flex-shrink:0;margin-top:1px;display:flex;align-items:center;justify-content:center;transition:all .2s}
.task.done .task-check{background:var(--brand);border-color:var(--brand);color:#1a0e0b;font-weight:900;font-size:14px}
.task-check::before{content:'';display:none}
.task.done .task-check::before{content:'✓';display:block}
.task-body{flex:1;min-width:0}
.task-title{font-size:15px;font-weight:700;color:#141b26;margin-bottom:3px;display:flex;flex-wrap:wrap;align-items:center;gap:8px}
.task-desc{font-size:13px;color:var(--text-muted);line-height:1.5}
.task-meta{display:flex;gap:10px;align-items:center;margin-top:8px;font-size:11px;color:var(--text-dim);flex-wrap:wrap}
.cat-pill{font-size:10px;padding:2px 8px;border-radius:6px;font-weight:700;letter-spacing:.4px;text-transform:uppercase}
.cat-safety{background:rgba(244,63,94,.12);color:#e11d48}
.cat-paperwork{background:rgba(99,102,241,.14);color:#4f46e5}
.cat-training{background:rgba(245,158,11,.14);color:#b45309}
.cat-intro{background:rgba(16,185,129,.12);color:#059669}
.cat-other{background:rgba(148,163,184,.12);color:#64748b}
.req-pill{font-size:10px;padding:2px 7px;border-radius:5px;background:rgba(244,63,94,.12);color:#e11d48;font-weight:700;letter-spacing:.4px;text-transform:uppercase}
.del-task-btn{background:rgba(244,63,94,.08);color:#e11d48;border:1px solid rgba(244,63,94,.18);border-radius:8px;width:30px;height:30px;font-size:13px;cursor:pointer;display:none;align-items:center;justify-content:center;font-family:inherit;flex-shrink:0}
body[data-role="admin"] .del-task-btn{display:inline-flex}
.del-task-btn:hover{background:rgba(244,63,94,.18)}

/* Admin sections */
.admin-only{display:none}
body[data-role="admin"] .admin-only{display:block}
.add-row{background:var(--surface);border:1px dashed var(--border);border-radius:14px;padding:18px 22px;display:flex;gap:10px;align-items:flex-start;flex-wrap:wrap;margin-bottom:14px}
.add-row input[type="text"],.add-row select{background:#ffffff;border:1px solid var(--border);border-radius:9px;padding:9px 13px;font-size:13px;color:var(--text);font-family:inherit;outline:none;transition:border .15s}
.add-row input[type="text"]:focus,.add-row select:focus{border-color:var(--brand)}
.add-row input[name="title"]{flex:1;min-width:200px}
.add-row label.req-check{display:flex;align-items:center;gap:6px;color:var(--text-muted);font-size:13px;cursor:pointer;user-select:none}
.add-btn{background:var(--brand);color:#1a0e0b;border:none;border-radius:9px;padding:9px 18px;font-size:13px;font-weight:800;cursor:pointer;font-family:inherit}
.add-btn:hover{background:var(--brand-strong)}

.team-list{background:var(--surface);border:1px solid var(--border);border-radius:14px;overflow:hidden}
.team-row{display:grid;grid-template-columns:1fr auto 200px auto;gap:14px;align-items:center;padding:14px 20px;border-bottom:1px solid rgba(17,24,39,0.064);font-size:14px}
.team-row:last-child{border-bottom:none}
.team-row.complete{background:rgba(16,185,129,.04)}
.team-name{display:flex;flex-direction:column;gap:2px}
.team-name b{color:#141b26;font-weight:700;font-size:14px}
.team-name .role{font-size:11px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.6px;font-weight:700}
.team-count{font-size:13px;color:var(--text-muted);font-weight:600;white-space:nowrap}
.team-bar{height:8px;background:rgba(17,24,39,0.096);border-radius:6px;overflow:hidden}
.team-bar-fill{height:100%;background:linear-gradient(90deg,var(--brand),var(--brand-strong));border-radius:6px;transition:width .3s}
.team-row.complete .team-bar-fill{background:#059669}
.reset-btn{background:transparent;color:var(--text-dim);border:1px solid var(--border);border-radius:8px;padding:6px 10px;font-size:11px;cursor:pointer;font-family:inherit;transition:all .15s}
.reset-btn:hover{color:#e11d48;border-color:rgba(244,63,94,.3)}

.empty{text-align:center;padding:60px 20px;color:var(--text-dim);background:var(--surface);border:1px dashed var(--border);border-radius:14px}
.empty-icon{font-size:48px;margin-bottom:12px;opacity:.5}

@media(max-width:700px){
.team-row{grid-template-columns:1fr;gap:8px}
.team-row .team-bar{order:3}
}
</style>
</head><body data-role="__ROLE__">
__NAVBAR__
<div class="wrap">
  <div class="hero">
    <div class="hero-eyebrow">Onboarding</div>
    <div class="hero-title">Your checklist</div>
    <div class="hero-sub">Complete these steps to get fully set up at __BRANDNAME__.</div>
    <div class="progress-row">
      <div class="progress-bar"><div class="progress-fill" id="progFill" style="width:0%"></div></div>
      <div class="progress-text"><b id="progDone">0</b> / <span id="progTotal">0</span> complete</div>
    </div>
    <div class="complete-badge" id="completeBadge" style="display:none">✓ All required steps complete</div>
  </div>

  <div class="section-title"><span class="dot"></span>My checklist</div>
  <div class="task-list" id="taskList"></div>

  <!-- Admin-only sections -->
  <div class="admin-only">
    <div class="section-title"><span class="dot"></span>Manage tasks</div>
    <div class="add-row">
      <input type="text" name="title" id="newTitle" placeholder="New task title (e.g. Complete W-4 form)">
      <select id="newCategory">
        <option value="safety">Safety</option>
        <option value="paperwork" selected>Paperwork</option>
        <option value="training">Training</option>
        <option value="intro">Intro</option>
        <option value="other">Other</option>
      </select>
      <label class="req-check"><input type="checkbox" id="newRequired" checked> Required</label>
      <button class="add-btn" id="addBtn">＋ Add task</button>
    </div>

    <div class="section-title"><span class="dot"></span>Team progress</div>
    <div id="teamList"></div>
  </div>
</div>

<script>
function escapeHtml(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}

function loadMe(){
  fetch('/api/onboarding/me').then(function(r){return r.json()}).then(function(d){
    document.getElementById('progDone').textContent=d.done_count;
    document.getElementById('progTotal').textContent=d.total_count;
    document.getElementById('progFill').style.width=(d.percent||0)+'%';
    document.getElementById('completeBadge').style.display=d.all_required_done&&d.total_required>0?'inline-flex':'none';
    var list=document.getElementById('taskList');
    if(!d.tasks||d.tasks.length===0){
      list.innerHTML='<div class="empty"><div class="empty-icon">🎯</div>No onboarding tasks yet.'+(document.body.dataset.role==='admin'?' Add the first one below.':'')+'</div>';
      return;
    }
    list.innerHTML=d.tasks.map(function(t){
      return '<div class="task'+(t.done?' done':'')+'" data-id="'+t.id+'">'+
        '<div class="task-check"></div>'+
        '<div class="task-body">'+
          '<div class="task-title">'+escapeHtml(t.title)+(t.required?' <span class="req-pill">required</span>':'')+'</div>'+
          (t.description?'<div class="task-desc">'+escapeHtml(t.description)+'</div>':'')+
          '<div class="task-meta"><span class="cat-pill cat-'+t.category+'">'+t.category+'</span>'+(t.done&&t.done_at?'<span>Completed '+t.done_at.replace("T"," ").slice(0,16)+'</span>':'')+'</div>'+
        '</div>'+
        '<button class="del-task-btn" data-del="'+t.id+'" title="Delete task" onclick="event.stopPropagation()">🗑</button>'+
      '</div>';
    }).join('');
    list.querySelectorAll('.task').forEach(function(el){
      el.addEventListener('click',function(){
        var tid=el.dataset.id;
        fetch('/api/onboarding/toggle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task_id:tid})})
          .then(function(r){return r.json()}).then(function(d){if(d.ok)loadMe();if(d.ok&&document.body.dataset.role==='admin')loadTeam();});
      });
    });
    list.querySelectorAll('.del-task-btn').forEach(function(b){
      b.addEventListener('click',function(){
        if(!confirm('Delete this task for everyone?'))return;
        fetch('/api/onboarding/tasks/'+b.dataset.del+'/delete',{method:'POST'})
          .then(function(r){return r.json()}).then(function(d){if(d.ok){loadMe();loadTeam()}else alert(d.error||'Failed')});
      });
    });
  });
}

function loadTeam(){
  if(document.body.dataset.role!=='admin')return;
  fetch('/api/onboarding/team').then(function(r){return r.json()}).then(function(team){
    var box=document.getElementById('teamList');
    if(!team||team.length===0){box.innerHTML='<div class="empty">No employees yet.</div>';return}
    box.innerHTML='<div class="team-list">'+team.map(function(u){
      return '<div class="team-row'+(u.complete?' complete':'')+'">'+
        '<div class="team-name"><b>'+escapeHtml(u.name)+'</b><span class="role">'+u.role+'</span></div>'+
        '<div class="team-count">'+u.done+' / '+u.total+(u.required_total>0?' · '+u.required_done+'/'+u.required_total+' req':'')+'</div>'+
        '<div class="team-bar"><div class="team-bar-fill" style="width:'+u.percent+'%"></div></div>'+
        '<button class="reset-btn" data-u="'+escapeHtml(u.username)+'">Reset</button>'+
      '</div>';
    }).join('')+'</div>';
    box.querySelectorAll('.reset-btn').forEach(function(b){
      b.addEventListener('click',function(){
        if(!confirm('Reset onboarding progress for '+b.dataset.u+'? Their completions will be erased.'))return;
        fetch('/api/onboarding/reset/'+b.dataset.u,{method:'POST'}).then(function(r){return r.json()}).then(function(d){if(d.ok){loadTeam();loadMe()}});
      });
    });
  });
}

document.getElementById('addBtn').addEventListener('click',function(){
  var title=document.getElementById('newTitle').value.trim();
  if(!title){document.getElementById('newTitle').focus();return}
  var payload={title:title,category:document.getElementById('newCategory').value,required:document.getElementById('newRequired').checked};
  fetch('/api/onboarding/tasks/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
    .then(function(r){return r.json()}).then(function(d){if(d.ok){document.getElementById('newTitle').value='';loadMe();loadTeam()}else alert(d.error||'Failed')});
});

loadMe();
loadTeam();
</script>
</body></html>'''


# ══════════════════════════════════════════════════════════
# ANNOUNCEMENTS — admin broadcasts to the team
# ══════════════════════════════════════════════════════════

ANNOUNCEMENTS_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>News — __BRANDMARK__</title>
__NAVBAR_CSS__
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'DM Sans',-apple-system,sans-serif;background:#ffffff;color:var(--text);min-height:100vh;padding-bottom:120px;-webkit-font-smoothing:antialiased}
.wrap{max-width:920px;margin:0 auto;padding:40px 28px 0}
.page-head{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;margin-bottom:28px;flex-wrap:wrap}
.page-title{font-size:34px;font-weight:900;color:#141b26;letter-spacing:-.5px;line-height:1.05}
.page-sub{color:var(--text-muted);margin-top:6px;font-size:14px}
.compose-btn{background:var(--brand);color:#1a0e0b;border:none;border-radius:12px;padding:12px 22px;font-size:14px;font-weight:800;cursor:pointer;font-family:inherit;transition:all .15s;display:inline-flex;align-items:center;gap:8px;box-shadow:0 6px 22px rgba(217,116,143,.15)}
.compose-btn:hover{background:var(--brand-strong);transform:translateY(-1px)}
.admin-only{display:none}
body[data-role="admin"] .admin-only{display:inline-flex}

/* Composer (inline, expands when "New" clicked) */
.composer{background:var(--surface);border:1px solid var(--border);border-radius:18px;padding:24px;margin-bottom:24px;display:none}
.composer.show{display:block}
.composer h3{font-size:18px;font-weight:800;color:#141b26;margin-bottom:14px}
.fld{margin-bottom:14px}
.fld label{display:block;font-size:11px;font-weight:700;color:var(--text-muted);margin-bottom:7px;text-transform:uppercase;letter-spacing:.6px}
.fld input[type="text"],.fld textarea,.fld select{width:100%;background:#ffffff;border:1px solid var(--border);border-radius:10px;padding:11px 14px;font-size:14px;color:var(--text);font-family:inherit;outline:none;transition:all .2s}
.fld input[type="text"]:focus,.fld textarea:focus,.fld select:focus{border-color:var(--brand);box-shadow:0 0 0 3px rgba(217,116,143,.1)}
.fld textarea{resize:vertical;min-height:110px;line-height:1.5}
.fld-row{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}
@media(max-width:600px){.fld-row{grid-template-columns:1fr 1fr}}
.fld .pin-check{display:flex;align-items:center;gap:6px;font-size:13px;color:var(--text-muted);cursor:pointer;user-select:none}
.composer-actions{display:flex;justify-content:flex-end;gap:10px;margin-top:6px}
.btn-cancel{background:transparent;color:var(--text-muted);border:1px solid var(--border);border-radius:10px;padding:9px 18px;font-size:14px;font-weight:600;cursor:pointer;font-family:inherit}
.btn-cancel:hover{color:var(--text);background:rgba(17,24,39,0.064)}
.btn-publish{background:var(--brand);color:#1a0e0b;border:none;border-radius:10px;padding:9px 22px;font-size:14px;font-weight:800;cursor:pointer;font-family:inherit;transition:all .15s}
.btn-publish:hover{background:var(--brand-strong)}
.composer-err{color:#f43f5e;font-size:13px;margin-top:10px;min-height:18px}

/* Announcement cards */
.ann-list{display:flex;flex-direction:column;gap:14px}
.ann{position:relative;background:var(--surface);border:1px solid var(--border);border-radius:18px;padding:22px 26px;transition:all .15s}
.ann:hover{border-color:rgba(17,24,39,0.16)}
.ann.pri-important{background:linear-gradient(135deg,rgba(251,191,36,.08),rgba(245,158,11,.02));border-color:rgba(251,191,36,.22)}
.ann.pri-urgent{background:linear-gradient(135deg,rgba(244,63,94,.1),rgba(244,63,94,.02));border-color:rgba(244,63,94,.28)}
.ann.pinned{box-shadow:inset 4px 0 0 var(--brand)}
.ann-head{display:flex;align-items:flex-start;gap:14px;margin-bottom:10px;flex-wrap:wrap}
.ann-title{flex:1;font-size:18px;font-weight:800;color:#141b26;line-height:1.3;min-width:0}
.ann-pills{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.pri-pill{font-size:10px;padding:3px 10px;border-radius:6px;font-weight:800;letter-spacing:.5px;text-transform:uppercase}
.pri-info{background:rgba(99,102,241,.14);color:#4f46e5}
.pri-important{background:rgba(251,191,36,.16);color:#b45309}
.pri-urgent{background:rgba(244,63,94,.16);color:#e11d48}
.aud-pill{font-size:10px;padding:3px 9px;border-radius:6px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;background:rgba(148,163,184,.12);color:#64748b}
.pinned-pill{font-size:10px;padding:3px 9px;border-radius:6px;font-weight:800;letter-spacing:.5px;text-transform:uppercase;background:rgba(217,116,143,.16);color:var(--brand);display:inline-flex;align-items:center;gap:4px}
.ann-body{font-size:14px;color:var(--text);line-height:1.65;white-space:pre-wrap;margin-bottom:14px}
.ann-foot{display:flex;justify-content:space-between;align-items:center;gap:14px;font-size:12px;color:var(--text-dim);flex-wrap:wrap}
.ann-meta b{color:var(--text-muted);font-weight:600}
.ann-actions{display:none;gap:6px}
body[data-role="admin"] .ann-actions{display:flex}
.icon-btn{background:rgba(17,24,39,0.064);color:var(--text-muted);border:1px solid var(--border);border-radius:8px;padding:6px 10px;font-size:11px;font-weight:600;cursor:pointer;font-family:inherit;transition:all .15s}
.icon-btn:hover{color:var(--text);background:rgba(17,24,39,0.128)}
.icon-btn.danger:hover{color:#e11d48;border-color:rgba(244,63,94,.3);background:rgba(244,63,94,.08)}
.icon-btn.pin.active{color:var(--brand);background:var(--brand-glow);border-color:rgba(217,116,143,.25)}

.empty{text-align:center;padding:80px 20px;background:var(--surface);border:1px dashed var(--border);border-radius:18px;color:var(--text-dim)}
.empty-icon{font-size:56px;margin-bottom:14px;opacity:.5}
.empty-title{font-size:18px;font-weight:700;color:var(--text-muted);margin-bottom:6px}
.empty-sub{font-size:14px}
</style>
</head><body data-role="__ROLE__">
__NAVBAR__
<div class="wrap">
  <div class="page-head">
    <div>
      <div class="page-title">📣 Team News</div>
      <div class="page-sub">Updates, reminders, and announcements from management</div>
    </div>
    <button class="compose-btn admin-only" id="openCompose">＋ New announcement</button>
  </div>

  <!-- Composer (admin only) -->
  <div class="composer" id="composer">
    <h3>New announcement</h3>
    <div class="fld">
      <label>Title</label>
      <input type="text" id="aTitle" placeholder="e.g. Q3 inventory count this Friday" maxlength="120">
    </div>
    <div class="fld">
      <label>Message</label>
      <textarea id="aBody" placeholder="Add details — start times, who is affected, what to bring, etc." maxlength="5000"></textarea>
    </div>
    <div class="fld-row">
      <div class="fld">
        <label>Priority</label>
        <select id="aPriority">
          <option value="info" selected>ℹ️ Info</option>
          <option value="important">⚠️ Important</option>
          <option value="urgent">🔴 Urgent</option>
        </select>
      </div>
      <div class="fld">
        <label>Audience</label>
        <select id="aAudience">
          <option value="all" selected>Everyone</option>
          <option value="workers">Workers only</option>
          <option value="admin_cs">Admin & CS only</option>
        </select>
      </div>
      <div class="fld" style="display:flex;align-items:flex-end;padding-bottom:11px">
        <label class="pin-check"><input type="checkbox" id="aPinned"> 📌 Pin to top</label>
      </div>
    </div>
    <div class="composer-err" id="composerErr"></div>
    <div class="composer-actions">
      <button class="btn-cancel" id="cancelCompose">Cancel</button>
      <button class="btn-publish" id="publish">Publish</button>
    </div>
  </div>

  <div class="ann-list" id="annList"></div>
</div>

<script>
function escapeHtml(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
function fmtTime(s){
  if(!s)return '';
  try{
    var d=new Date(s);var now=new Date();
    var diff=(now-d)/1000;
    if(diff<60)return 'just now';
    if(diff<3600)return Math.floor(diff/60)+'m ago';
    if(diff<86400)return Math.floor(diff/3600)+'h ago';
    if(diff<604800)return Math.floor(diff/86400)+'d ago';
    return d.toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'});
  }catch(e){return s}
}
function audLabel(a){if(a==='all')return 'Everyone';if(a==='workers')return 'Workers';if(a==='admin_cs')return 'Admin & CS';return a}

function load(){
  fetch('/api/announcements').then(function(r){return r.json()}).then(function(arr){
    var box=document.getElementById('annList');
    if(!arr||arr.length===0){
      box.innerHTML='<div class="empty"><div class="empty-icon">📣</div><div class="empty-title">No announcements yet</div><div class="empty-sub">'+(document.body.dataset.role==='admin'?'Tap "New announcement" to post the first one.':'Check back later for updates.')+'</div></div>';
      return;
    }
    box.innerHTML=arr.map(function(a){
      var pills='';
      pills+='<span class="pri-pill pri-'+a.priority+'">'+a.priority+'</span>';
      pills+='<span class="aud-pill">'+audLabel(a.audience)+'</span>';
      if(a.pinned)pills+='<span class="pinned-pill">📌 Pinned</span>';
      return '<div class="ann pri-'+a.priority+(a.pinned?' pinned':'')+'" data-id="'+a.id+'">'+
        '<div class="ann-head"><div class="ann-title">'+escapeHtml(a.title)+'</div><div class="ann-pills">'+pills+'</div></div>'+
        (a.body?'<div class="ann-body">'+escapeHtml(a.body)+'</div>':'')+
        '<div class="ann-foot">'+
          '<div class="ann-meta">Posted by <b>'+escapeHtml(a.author)+'</b> · '+fmtTime(a.created_at)+'</div>'+
          '<div class="ann-actions">'+
            '<button class="icon-btn pin'+(a.pinned?' active':'')+'" data-pin="'+a.id+'">'+(a.pinned?'Unpin':'Pin')+'</button>'+
            '<button class="icon-btn danger" data-del="'+a.id+'">Delete</button>'+
          '</div>'+
        '</div>'+
      '</div>';
    }).join('');
    box.querySelectorAll('[data-pin]').forEach(function(b){
      b.addEventListener('click',function(){
        fetch('/api/announcements/'+b.dataset.pin+'/pin',{method:'POST'}).then(function(r){return r.json()}).then(function(d){if(d.ok)load()});
      });
    });
    box.querySelectorAll('[data-del]').forEach(function(b){
      b.addEventListener('click',function(){
        if(!confirm('Delete this announcement?'))return;
        fetch('/api/announcements/'+b.dataset.del+'/delete',{method:'POST'}).then(function(r){return r.json()}).then(function(d){if(d.ok)load();else alert(d.error||'Failed')});
      });
    });
  });
}

// Composer
var composer=document.getElementById('composer');
var openBtn=document.getElementById('openCompose');
if(openBtn){
  openBtn.addEventListener('click',function(){
    document.getElementById('composerErr').textContent='';
    composer.classList.add('show');
    document.getElementById('aTitle').focus();
  });
  document.getElementById('cancelCompose').addEventListener('click',function(){composer.classList.remove('show')});
  document.getElementById('publish').addEventListener('click',function(){
    var title=document.getElementById('aTitle').value.trim();
    if(!title){document.getElementById('composerErr').textContent='Title is required';return}
    var payload={
      title:title,
      body:document.getElementById('aBody').value.trim(),
      priority:document.getElementById('aPriority').value,
      audience:document.getElementById('aAudience').value,
      pinned:document.getElementById('aPinned').checked,
    };
    var btn=document.getElementById('publish');btn.disabled=true;btn.textContent='Publishing…';
    fetch('/api/announcements/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
      .then(function(r){return r.json()}).then(function(d){
        btn.disabled=false;btn.textContent='Publish';
        if(d.ok){
          composer.classList.remove('show');
          document.getElementById('aTitle').value='';
          document.getElementById('aBody').value='';
          document.getElementById('aPinned').checked=false;
          load();
        } else {
          document.getElementById('composerErr').textContent=d.error||'Failed';
        }
      });
  });
}

load();
</script>
</body></html>'''


# ══════════════════════════════════════════════════════════
# WEIGHT VERIFICATION — Admin shipments management
# ══════════════════════════════════════════════════════════

SHIPMENTS_ADMIN_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Shipments — __BRANDMARK__ Admin</title>
__NAVBAR_CSS__
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'DM Sans',-apple-system,sans-serif;background:#ffffff;color:var(--text);min-height:100vh;padding-bottom:120px;-webkit-font-smoothing:antialiased}
.wrap{max-width:1300px;margin:0 auto;padding:40px 28px 0}
.page-head{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;margin-bottom:28px;flex-wrap:wrap}
.page-title{font-size:32px;font-weight:900;color:#141b26;letter-spacing:-.5px;line-height:1.05}
.page-sub{color:var(--text-muted);margin-top:6px;font-size:14px}
.import-btn-group{display:flex;gap:10px;flex-wrap:wrap}
.import-btn{background:var(--brand);color:#1a0e0b;border:none;border-radius:12px;padding:12px 18px;font-size:13px;font-weight:800;cursor:pointer;font-family:inherit;transition:all .15s;display:inline-flex;align-items:center;gap:8px;box-shadow:0 6px 22px rgba(217,116,143,.12);white-space:nowrap}
.import-btn:hover{background:var(--brand-strong);transform:translateY(-1px)}
.import-btn-alt{background:rgba(99,102,241,.15);color:#4f46e5;box-shadow:none;border:1px solid rgba(99,102,241,.3)}
.import-btn-alt:hover{background:rgba(99,102,241,.25);color:#6366f1}
.import-btn-warn{background:rgba(244,63,94,.12);color:#e11d48;box-shadow:none;border:1px solid rgba(244,63,94,.28)}
.import-btn-warn:hover{background:rgba(244,63,94,.2);color:#e11d48}

/* Stat tiles */
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin-bottom:28px}
.stat{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:18px 22px}
.stat .lbl{font-size:11px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.8px;font-weight:700}
.stat .val{font-size:30px;font-weight:900;color:#141b26;line-height:1;margin-top:8px}
.stat .sub{font-size:12px;color:var(--text-muted);margin-top:6px}
.stat.warn .val{color:#b45309}
.stat.good .val{color:#059669}
.stat.bad .val{color:#e11d48}

/* Table */
.section-title{font-size:13px;font-weight:800;color:var(--text-dim);text-transform:uppercase;letter-spacing:2px;display:flex;align-items:center;gap:10px;margin:32px 0 14px}
.section-title .dot{width:8px;height:8px;border-radius:50%;background:var(--brand)}
.tbl-wrap{background:var(--surface);border:1px solid var(--border);border-radius:14px;overflow:hidden}
.tbl{width:100%;border-collapse:collapse;font-size:13px}
.tbl th{text-align:left;padding:12px 16px;font-size:11px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.6px;font-weight:700;background:rgba(17,24,39,0.032);border-bottom:1px solid var(--border);position:sticky;top:0}
.tbl td{padding:12px 16px;color:var(--text);border-bottom:1px solid rgba(17,24,39,0.064)}
.tbl tr:last-child td{border-bottom:none}
.tbl tr.row{cursor:pointer;transition:background .12s}
.tbl tr.row:hover{background:rgba(17,24,39,0.048)}
.tbl tr.detail td{padding:0;background:rgba(17,24,39,0.024)}
.detail-inner{padding:16px 22px}
.detail-inner h4{font-size:11px;color:var(--text-dim);text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;font-weight:700}
.detail-table{width:100%;font-size:12px}
.detail-table td{padding:6px 0;border:none;color:var(--text-muted)}
.undo-note{font-size:12.5px;color:var(--text-muted);margin-bottom:10px;line-height:1.5}
.undo-who{display:block;font-size:11px;color:var(--text-dim);margin-top:3px}
.undo-row{display:flex;gap:9px;flex-wrap:wrap}
.undo-btn{border:1.5px solid rgba(79,70,229,.35);background:#fff;color:#4f46e5;border-radius:9px;
  padding:8px 14px;font-size:12.5px;font-weight:800;cursor:pointer}
.undo-btn:hover{background:rgba(79,70,229,.06)}
.undo-btn.danger{border-color:rgba(244,63,94,.4);color:#e11d48}
.undo-btn.danger:hover{background:rgba(244,63,94,.06)}
.undo-btn:disabled{opacity:.5;cursor:default}
.undo-fine{font-size:11px;color:var(--text-dim);margin-top:9px}
.detail-table td.lbl{color:var(--text-dim);text-transform:uppercase;font-size:10px;letter-spacing:.5px;font-weight:700;width:140px;vertical-align:top}
.items-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:6px;margin-top:8px}
.item-pill{background:rgba(17,24,39,0.064);border-radius:8px;padding:8px 12px;font-size:12px;color:var(--text);display:flex;justify-content:space-between;gap:8px}
.item-pill .qty{color:var(--brand);font-weight:700}
.item-pill.no-weight{border-left:3px solid #b45309}
.mono{font-family:'SF Mono',Menlo,monospace;font-size:12px}
.col-tracking{color:var(--brand);font-weight:700}
.col-id{font-family:'SF Mono',Menlo,monospace;color:var(--text-muted)}
.weight-cell{font-weight:700}
.weight-cell.unknown{color:var(--text-dim);font-weight:500}
.weight-cell.ok{color:#059669}
.weight-cell.flag{color:#e11d48}
.status-pill{font-size:10px;padding:3px 9px;border-radius:6px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;white-space:nowrap}
.st-pending{background:rgba(148,163,184,.12);color:#64748b}
.st-packed{background:rgba(16,185,129,.14);color:#059669}
.st-weight_flagged{background:rgba(244,63,94,.14);color:#e11d48}
.st-shipped{background:rgba(99,102,241,.14);color:#4f46e5}

.empty{text-align:center;padding:80px 20px;color:var(--text-dim)}
.empty-icon{font-size:56px;margin-bottom:14px;opacity:.5}

/* Modal */
.modal-bg{position:fixed;inset:0;background:rgba(0,0,0,.65);backdrop-filter:blur(8px);z-index:200;display:none;align-items:center;justify-content:center;padding:20px}
.modal-bg.show{display:flex}
.modal{background:#f6f7f9;border:1px solid var(--border);border-radius:20px;padding:32px;max-width:600px;width:100%}
.modal h3{font-size:22px;font-weight:800;color:#141b26;margin-bottom:6px}
.modal-sub{color:var(--text-muted);font-size:13px;margin-bottom:24px;line-height:1.5}
.fld{margin-bottom:14px}
.fld label{display:block;font-size:11px;font-weight:700;color:var(--text-muted);margin-bottom:7px;text-transform:uppercase;letter-spacing:.6px}
.fld input[type="file"]{width:100%;color:var(--text-muted);font-size:13px;padding:12px;background:#ffffff;border:2px dashed var(--border);border-radius:12px;cursor:pointer;font-family:inherit}
.fld input[type="file"]::file-selector-button{background:var(--brand);color:#1a0e0b;border:none;border-radius:8px;padding:7px 14px;margin-right:10px;font-size:12px;font-weight:700;cursor:pointer;font-family:inherit}
.fld input[type="text"]{width:100%;background:#ffffff;border:1px solid var(--border);border-radius:10px;padding:11px 14px;font-size:14px;color:var(--text);font-family:inherit;outline:none;transition:border .15s}
.fld input[type="text"]:focus{border-color:var(--brand);box-shadow:0 0 0 3px rgba(217,116,143,.1)}
.fld input[type="text"]::placeholder{color:var(--text-dim)}
.fld-hint{font-size:11px;color:var(--text-dim);margin-top:6px;line-height:1.4}
.req-star{color:#e11d48;font-weight:900;font-size:14px;margin-left:2px}
.modal-actions{display:flex;justify-content:flex-end;gap:10px;margin-top:24px}
.btn-cancel{background:transparent;color:var(--text-muted);border:1px solid var(--border);border-radius:10px;padding:10px 18px;font-size:14px;font-weight:600;cursor:pointer;font-family:inherit}
.btn-cancel:hover{color:var(--text);background:rgba(17,24,39,0.064)}
.btn-submit{background:var(--brand);color:#1a0e0b;border:none;border-radius:10px;padding:10px 22px;font-size:14px;font-weight:800;cursor:pointer;font-family:inherit}
.btn-submit:hover{background:var(--brand-strong)}
.btn-submit:disabled{opacity:.5;cursor:not-allowed}
.modal-result{margin-top:18px;padding:14px;background:rgba(16,185,129,.08);border:1px solid rgba(16,185,129,.22);border-radius:10px;color:#059669;font-size:13px;line-height:1.6;display:none}
.modal-result.show{display:block}
.modal-result.err{background:rgba(244,63,94,.08);border-color:rgba(244,63,94,.22);color:#e11d48}
.modal-result b{color:#141b26}
</style>
</head><body data-role="__ROLE__">
__NAVBAR__
<div class="wrap">
  <div class="page-head">
    <div>
      <div class="page-title">📦 Shipments</div>
      <div class="page-sub">Imported from TikTok and Whatnot · weight verification per package</div>
    </div>
    <div class="import-btn-group">
      <button class="import-btn" data-kind="tiktok_orders">＋ TikTok Orders</button>
      <button class="import-btn import-btn-warn" data-kind="tiktok_cancel">＋ TikTok Cancellations</button>
      <button class="import-btn import-btn-alt" data-kind="whatnot">＋ Whatnot</button>
    </div>
  </div>

  <div class="stats" id="stats"></div>

  <div class="section-title"><span class="dot"></span>Recent shipments</div>
  <div id="listWrap"></div>
</div>

<!-- Import modal -->
<div class="modal-bg" id="modal">
  <div class="modal">
    <h3 id="modalTitle">Import CSV</h3>
    <div class="modal-sub" id="modalSub">Pick a CSV file from your platform.</div>
    <div class="fld">
      <label>Show name <span class="req-star">*</span></label>
      <input type="text" id="showName" list="recentShowsList" placeholder="e.g. Beauty 5/15 — TikTok" maxlength="80" autocomplete="off">
      <datalist id="recentShowsList"></datalist>
      <div class="fld-hint">Required. Same name for all uploads of the same show (orders + cancellations). Recent shows appear as you type.</div>
    </div>
    <div class="fld">
      <label>Host name <span class="muted" style="font-weight:400">(optional)</span></label>
      <input type="text" id="hostName" list="recentHostsList" placeholder="e.g. Tali" maxlength="60" autocomplete="off">
      <datalist id="recentHostsList"></datalist>
      <div class="fld-hint">Who hosted this live. Fills the Host column in Host Analytics automatically — no need to type it in later.</div>
    </div>
    <div class="fld">
      <label>Show start <span class="muted" style="font-weight:400">(optional)</span></label>
      <input type="datetime-local" id="showStart" autocomplete="off">
      <div class="fld-hint">When the live show began. Sales after midnight are matched to this show — not the next day's. Leave blank to auto-use the earliest sale time in the file.</div>
    </div>
    <div class="fld">
      <label id="modalLabel">CSV file <span class="req-star">*</span></label>
      <input type="file" id="csvFile" accept=".csv">
    </div>
    <div class="modal-result" id="modalResult"></div>
    <div class="modal-actions">
      <button class="btn-cancel" id="cancelImport">Cancel</button>
      <button class="btn-submit" id="doImport">Import</button>
    </div>
  </div>
</div>

<script>
function fmt(n){return n==null?'—':(typeof n==='number'?n.toLocaleString():n)}
function escapeHtml(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
function fmtWeight(g){if(g==null||g===0)return '—';return g.toFixed(1)+'g'}
function fmtDate(s){if(!s)return '—';try{return new Date(s).toLocaleDateString(undefined,{month:'short',day:'numeric',year:'2-digit'})}catch(e){return s.slice(0,10)}}

// Optional filter via ?show=NAME — when present we show a breadcrumb + only that show's shipments
var showFilter=new URLSearchParams(location.search).get('show')||'';
if(showFilter){
  var sub=document.querySelector('.page-sub');
  if(sub)sub.innerHTML='Filtering by show: <b style="color:var(--brand)">'+showFilter.replace(/</g,'&lt;')+'</b> · <a href="/admin/shipments" style="color:var(--text-muted)">Clear filter</a>';
}
function loadShipments(){
  var url='/api/shipments/recent?limit=500';
  if(showFilter)url+='&show='+encodeURIComponent(showFilter);
  fetch(url).then(function(r){return r.json()}).then(function(rows){
    // Stats
    var total=rows.length;
    var withWeight=rows.filter(function(s){return s.expected_weight_g>0}).length;
    var missing=rows.filter(function(s){return s.missing_weights>0}).length;
    var withTracking=rows.filter(function(s){return s.tracking_code}).length;
    var packed=rows.filter(function(s){return s.status==='packed'||s.status==='shipped'}).length;
    var picked=rows.filter(function(s){return s.status==='picked'||s.status==='packed'||s.status==='shipped'}).length;
    document.getElementById('stats').innerHTML=
      '<div class="stat"><div class="lbl">Total</div><div class="val">'+total+'</div><div class="sub">shipments imported</div></div>'+
      '<div class="stat '+(withWeight===total?'good':'warn')+'"><div class="lbl">With expected weight</div><div class="val">'+withWeight+'</div><div class="sub">'+(total?Math.round(100*withWeight/total):0)+'% of total</div></div>'+
      '<div class="stat '+(missing===0?'good':'warn')+'"><div class="lbl">Missing weight data</div><div class="val">'+missing+'</div><div class="sub">need SKU weight set</div></div>'+
      '<div class="stat"><div class="lbl">With tracking</div><div class="val">'+withTracking+'</div><div class="sub">label generated</div></div>'+
      '<div class="stat"><div class="lbl">Picked</div><div class="val">'+picked+'</div><div class="sub">collected off the table</div></div>'+
      '<div class="stat good"><div class="lbl">Packed</div><div class="val">'+packed+'</div><div class="sub">already weighed</div></div>';

    // Store rows and render with the current status filter.
    window._allRows=rows;
    renderTable();
  });
}
var _statusFilter='all';
var _MOVING=['DELIVERED','IN_TRANSIT','OUT_FOR_DELIVERY'];
function setFilter(f){_statusFilter=f;renderTable();}
function renderTable(){
  var rows=window._allRows||[];
  var lw=document.getElementById('listWrap');
  if(rows.length===0){lw.innerHTML='<div class="empty"><div class="empty-icon">📦</div>No shipments imported yet. Click "＋ Import" to start.</div>';return}
  var counts={all:rows.length,
    pending:rows.filter(function(s){return s.status==='pending'}).length,
    packed:rows.filter(function(s){return s.status==='packed'}).length,
    shipped:rows.filter(function(s){return s.status==='shipped'}).length,
    cancelled:rows.filter(function(s){return s.status==='cancelled'}).length,
    pdel:rows.filter(function(s){return s.status==='pending'&&_MOVING.indexOf(s.delivery_status)>=0}).length};
  var fb=[['all','All'],['pending','Pending'],['packed','Packed'],['shipped','Shipped'],['cancelled','Cancelled'],['pdel','⚠️ Pending but moving/delivered']];
  var bar='<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px">'+fb.map(function(f){
    var a=_statusFilter===f[0];
    return '<button onclick="setFilter(\\''+f[0]+'\\')" style="background:'+(a?'var(--brand)':'var(--surface)')+';color:'+(a?'#f6f7f9':'var(--text-muted)')+';border:1px solid var(--border);border-radius:8px;padding:7px 12px;font-size:12px;font-weight:700;cursor:pointer;font-family:inherit">'+f[1]+' ('+(counts[f[0]]||0)+')</button>';
  }).join('')+'</div>';
  var view=rows.filter(function(s){
    if(_statusFilter==='all')return true;
    if(_statusFilter==='pdel')return s.status==='pending'&&_MOVING.indexOf(s.delivery_status)>=0;
    return s.status===_statusFilter;
  });
  var DEL={DELIVERED:['#059669','✅ Delivered'],IN_TRANSIT:['#2563eb','✈️ In transit'],OUT_FOR_DELIVERY:['#0891b2','📬 Out for delivery'],PRE_TRANSIT:['#b45309','🚚 Shipped'],EXCEPTION:['#f43f5e','⚠️ Exception'],RETURNED:['#c2410c','↩️ Returned'],UNKNOWN:['#64748b','—']};
  var html='<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Shipment</th><th>Buyer</th><th>Items</th><th>Tracking</th><th>Status</th><th>USPS</th><th>Show date</th></tr></thead><tbody>';
  view.forEach(function(s,i){
    var trk=s.tracking_code?'<a href="https://tools.usps.com/go/TrackConfirmAction?tLabels='+encodeURIComponent(s.tracking_code)+'" target="_blank" rel="noopener" onclick="event.stopPropagation()" class="col-tracking" style="text-decoration:underline" title="Track on USPS.com">'+escapeHtml(s.tracking_code)+' ↗</a>':'<span class="col-id" style="opacity:.5">—</span>';
    var dv=s.delivery_status?(DEL[s.delivery_status]||['#64748b',s.delivery_status]):null;
    var delCell=dv?'<span style="color:'+dv[0]+';font-weight:600;font-size:12px" title="'+escapeHtml(s.delivery_detail||'')+'">'+dv[1]+'</span>':'<span style="opacity:.4">—</span>';
    html+='<tr class="row" data-i="'+i+'">'+
      '<td class="col-id">'+escapeHtml(s.shipment_id)+'</td>'+
      '<td>'+escapeHtml(s.buyer_name||s.buyer_username||'?')+'</td>'+
      '<td>'+s.total_items+'</td>'+
      '<td>'+trk+'</td>'+
      '<td><span class="status-pill st-'+s.status+'">'+s.status.replace('_',' ')+'</span></td>'+
      '<td>'+delCell+'</td>'+
      '<td style="color:var(--text-dim)">'+fmtDate(s.show_date||s.imported_at)+'</td>'+
    '</tr>'+
    '<tr class="detail" data-detail="'+i+'" style="display:none"><td colspan="7"><div class="detail-inner" id="detail-'+i+'">Loading…</div></td></tr>';
  });
  html+='</tbody></table></div>';
  lw.innerHTML=bar+html;
  document.querySelectorAll('tr.row').forEach(function(tr){
    tr.addEventListener('click',function(){
      var i=tr.dataset.i;
      var detail=document.querySelector('tr.detail[data-detail="'+i+'"]');
      if(detail.style.display==='table-row'){detail.style.display='none';return}
      detail.style.display='table-row';
      var s=view[i];
      if(detail.dataset.loaded){return}
      window.revertShipment=window.revertShipment||function(sid,to,btn){
        var msg=(to==='pending')
          ? 'Reset this order to PENDING?\\n\\nIt goes back to the top of the queue and all item ticks are cleared, so it must be picked and packed again.'
          : 'Undo the packing on this order?\\n\\nIt returns to PICKED — the pick stands, only the packing is undone.';
        if(!confirm(msg))return;
        btn.disabled=true;var old=btn.textContent;btn.textContent='Working…';
        function send(force){
          return fetch('/api/shipment/'+encodeURIComponent(sid)+'/revert',{method:'POST',
            headers:{'Content-Type':'application/json'},body:JSON.stringify({to:to,force:!!force})})
            .then(function(r){return r.json()});
        }
        send(false).then(function(d){
          if(d.needs_confirm){
            if(confirm(d.error+'\\n\\nContinue anyway?'))return send(true);
            btn.disabled=false;btn.textContent=old;return null;
          }
          return d;
        }).then(function(d){
          if(!d)return;
          if(!d.ok){btn.disabled=false;btn.textContent=old;alert(d.error||'Could not revert');return}
          alert('Done — order '+sid+' moved from '+d.was.toUpperCase()+' back to '+d.now.toUpperCase()+'.');
          location.reload();
        }).catch(function(){btn.disabled=false;btn.textContent=old;alert('Network error')});
      };
      fetch('/api/shipment/'+encodeURIComponent(s.shipment_id)).then(function(r){return r.json()}).then(function(d){
        if(!d.ok){document.getElementById('detail-'+i).innerHTML='<div style="color:#e11d48">Failed</div>';return}
        var box=document.getElementById('detail-'+i);
        var addr=d.shipment.address_full||'';
        var itemsHtml=d.items.map(function(it){
          return '<div class="item-pill'+(it.item_weight_g==null?' no-weight':'')+'"><span>'+escapeHtml(it.product_name||it.sku||'?')+'</span><span class="qty">×'+it.quantity+'</span></div>';
        }).join('');
        var st=(d.shipment.status||'').toLowerCase();
        var who=(d.shipment.packed_by?(' · packed by '+escapeHtml(d.shipment.packed_by)):'')+
                (d.shipment.picked_by?(' · picked by '+escapeHtml(d.shipment.picked_by)):'');
        var undo='';
        if(st!=='cancelled'){
          undo='<h4 style="margin-top:18px">Fix a mistake</h4>'+
            '<div class="undo-note">Sent this one down the line by accident? Put it back in the queue.'+
            (who?'<span class="undo-who">'+who+'</span>':'')+'</div>'+
            '<div class="undo-row">'+
              ((st==='packed'||st==='shipped')
                ? '<button class="undo-btn" data-rev="picked" data-sid="'+escapeHtml(s.shipment_id)+'">↩︎ Undo packing — back to picked</button>' : '')+
              '<button class="undo-btn danger" data-rev="pending" data-sid="'+escapeHtml(s.shipment_id)+'">⟲ Reset to pending — re-pick &amp; re-pack</button>'+
            '</div>'+
            '<div class="undo-fine">The packing video is kept either way — it is your proof if a customer disputes.</div>';
        }
        box.innerHTML='<h4>Address</h4><div style="color:var(--text);margin-bottom:14px">'+escapeHtml(addr)+'</div>'+
          (d.shipment.delivery_detail?'<h4>USPS status</h4><div style="margin-bottom:14px;color:var(--text)">'+escapeHtml(d.shipment.delivery_detail)+'</div>':'')+
          '<h4>Items ('+d.items.length+')</h4><div class="items-grid">'+itemsHtml+'</div>'+undo;
        box.querySelectorAll('button[data-rev]').forEach(function(b){
          b.addEventListener('click',function(){revertShipment(b.dataset.sid,b.dataset.rev,b)});
        });
        detail.dataset.loaded='1';
      });
    });
  });
}

// Import modal — three entry points (TikTok orders / TikTok cancellations / Whatnot)
// share a single modal but with context-appropriate copy.
var modal=document.getElementById('modal');
var importContexts={
  tiktok_orders: {
    title:'Import TikTok Orders CSV',
    sub:'Export "To Ship" orders from TikTok Seller Center → Orders → Export. The file has tracking codes, package IDs, and weight per label.',
    label:'TikTok TO SHIP CSV'
  },
  tiktok_cancel: {
    title:'Import TikTok Cancellations CSV',
    sub:'Export cancelled / failed orders from TikTok Seller Center → Orders → Canceled tab → Export. These orders will be flagged so workers won\\'t pack them.',
    label:'TikTok CANCELED CSV'
  },
  whatnot: {
    title:'Import Whatnot Show CSV',
    sub:'Export the show CSV from Whatnot Seller dashboard. One file per show contains both orders and any cancellations.',
    label:'Whatnot CSV'
  }
};
document.querySelectorAll('.import-btn[data-kind]').forEach(function(btn){
  btn.addEventListener('click',function(){
    var ctx=importContexts[btn.dataset.kind]||importContexts.tiktok_orders;
    document.getElementById('modalTitle').textContent=ctx.title;
    document.getElementById('modalSub').textContent=ctx.sub;
    document.getElementById('modalLabel').firstChild.nodeValue=ctx.label+' ';
    document.getElementById('csvFile').value='';
    document.getElementById('modalResult').className='modal-result';
    document.getElementById('modalResult').innerHTML='';
    // Pull recent show names (last 5 days) for the autocomplete dropdown.
    fetch('/api/shows/recent').then(function(r){return r.json()}).then(function(names){
      var dl=document.getElementById('recentShowsList');
      dl.innerHTML=(names||[]).map(function(n){return '<option value="'+n.replace(/"/g,'&quot;')+'"></option>'}).join('');
    });
    fetch('/api/hosts/recent').then(function(r){return r.ok?r.json():[]}).then(function(names){
      var dl=document.getElementById('recentHostsList');if(!dl)return;
      dl.innerHTML=(names||[]).map(function(n){return '<option value="'+String(n).replace(/"/g,'&quot;')+'"></option>'}).join('');
    }).catch(function(){});
    modal.classList.add('show');
    setTimeout(function(){document.getElementById('showName').focus()},80);
  });
});
document.getElementById('cancelImport').addEventListener('click',function(){modal.classList.remove('show')});
modal.addEventListener('click',function(e){if(e.target===modal)modal.classList.remove('show')});
// Auto-fill show name / start / host straight from the chosen CSV — no re-typing.
document.getElementById('csvFile').addEventListener('change',function(){
  var f=this.files&&this.files[0];if(!f)return;
  var fd=new FormData();fd.append('file',f);
  fetch('/api/shipments/preview',{method:'POST',body:fd}).then(function(r){return r.ok?r.json():null}).then(function(d){
    if(!d||!d.ok)return;
    var sn=document.getElementById('showName');if(sn&&!sn.value.trim()&&d.label)sn.value=d.label;
    var ss=document.getElementById('showStart');if(ss&&!ss.value&&d.start)ss.value=d.start;
    var hn=document.getElementById('hostName');if(hn&&!hn.value.trim()&&d.host)hn.value=d.host;
    var res=document.getElementById('modalResult');
    if(res&&(d.label||d.start)){res.className='modal-result show';res.textContent='✓ Auto-filled from the file — edit anything before importing.';}
  }).catch(function(){});
});

function runImport(force){
  var f=document.getElementById('csvFile').files[0];
  var label=document.getElementById('showName').value.trim();
  var res=document.getElementById('modalResult');
  if(!label){res.className='modal-result err show';res.textContent='Show name is required';document.getElementById('showName').focus();return}
  if(!f){res.className='modal-result err show';res.textContent='Pick a CSV file';return}
  var fd=new FormData();fd.append('file',f);fd.append('label',label);
  var ss=document.getElementById('showStart');if(ss&&ss.value)fd.append('show_start',ss.value);
  var hn=document.getElementById('hostName');if(hn&&hn.value.trim())fd.append('host',hn.value.trim());
  if(force)fd.append('force','1');
  var btn=document.getElementById('doImport');btn.disabled=true;btn.textContent='Importing…';
  res.className='modal-result show';res.textContent='Importing… large shows can take up to a minute, please wait.';
  fetch('/api/shipments/import',{method:'POST',body:fd}).then(function(r){
    if(!r.ok)throw new Error('HTTP '+r.status);return r.json();
  }).then(function(d){
    btn.disabled=false;btn.textContent='Import';
    if(d.ok){
      res.className='modal-result show';
      res.innerHTML='<b>✓ Import complete</b><br>'+
        '<b>'+d.shipments_new+'</b> new shipments · <b>'+d.shipments_updated+'</b> updated<br>'+
        '<b>'+d.items+'</b> items · <b>'+d.skipped_rows+'</b> rows skipped (cancelled/failed)<br>'+
        '<b>'+d.unique_skus+'</b> unique products · <b>'+d.skus_missing_weight+'</b> still need weights set';
      loadShipments();
      return;
    }
    if(d.duplicate){
      // Same file contents already imported — make the user confirm.
      var p=d.previous||{};
      res.className='modal-result err show';
      res.innerHTML='<b>⚠️ This file was already imported</b><br>'+
        escapeHtml(d.error||'')+'<br>'+
        '<span style="opacity:.85">It brought in '+(p.shipments_new||0)+' new and '+(p.shipments_updated||0)+' updated shipments.</span><br><br>'+
        '<button id="dupYes" class="btn btn-p" style="padding:8px 16px">Import it again anyway</button> '+
        '<button id="dupNo" class="btn btn-s" style="padding:8px 16px">Cancel</button>';
      document.getElementById('dupYes').addEventListener('click',function(){runImport(true)});
      document.getElementById('dupNo').addEventListener('click',function(){
        res.className='modal-result';res.innerHTML='';document.getElementById('csvFile').value='';
      });
      return;
    }
    res.className='modal-result err show';
    res.innerHTML='<b>Import failed:</b> '+(d.error||'unknown error');
  }).catch(function(e){
    btn.disabled=false;btn.textContent='Import';
    res.className='modal-result err show';
    res.innerHTML='<b>Import interrupted</b> ('+escapeHtml(String(e.message||e))+'). The file may be very large or the connection dropped — part of it may have imported. Refresh and check the list, or try again.';
    loadShipments();
  });
}
document.getElementById('doImport').addEventListener('click',function(){runImport(false)});

loadShipments();
</script>
</body></html>'''


# ══════════════════════════════════════════════════════════
# CUSTOMER SEARCH — CS lookup tool across all shipments
# ══════════════════════════════════════════════════════════

CUSTOMERS_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Customers — __BRANDMARK__</title>
__NAVBAR_CSS__
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'DM Sans',-apple-system,sans-serif;background:#ffffff;color:var(--text);min-height:100vh;padding-bottom:120px;-webkit-font-smoothing:antialiased}
.wrap{max-width:1100px;margin:0 auto;padding:40px 28px 0}
.page-head{margin-bottom:28px}
.page-title{font-size:32px;font-weight:900;color:#141b26;letter-spacing:-.5px;line-height:1.05}
.page-sub{color:var(--text-muted);margin-top:6px;font-size:14px}

/* Search */
.search-box{position:relative;margin-bottom:22px}
.search-box input{width:100%;background:var(--surface);border:2px solid var(--border);border-radius:14px;padding:18px 22px 18px 50px;font-size:17px;color:var(--text);font-family:inherit;outline:none;transition:all .2s}
.search-box input:focus{border-color:var(--brand);box-shadow:0 0 0 4px rgba(217,116,143,.1)}
.search-box input::placeholder{color:#6b7280}
.search-box .icon{position:absolute;left:18px;top:50%;transform:translateY(-50%);font-size:20px;color:var(--text-muted)}
.search-box .clear{position:absolute;right:18px;top:50%;transform:translateY(-50%);background:transparent;border:none;color:var(--text-dim);cursor:pointer;font-size:18px;padding:4px 8px;display:none;font-family:inherit}
.search-box .clear.show{display:block}

/* Results list */
.results-info{font-size:13px;color:var(--text-dim);margin-bottom:14px}
.results{display:flex;flex-direction:column;gap:8px}
.result{display:grid;grid-template-columns:48px 1fr auto;gap:14px;align-items:center;padding:14px 18px;background:var(--surface);border:1px solid var(--border);border-radius:12px;cursor:pointer;transition:all .12s}
.result:hover{border-color:rgba(217,116,143,.22);background:rgba(17,24,39,0.072)}
.result.selected{border-color:var(--brand);background:rgba(217,116,143,.06)}
.result-avatar{width:44px;height:44px;border-radius:50%;background:linear-gradient(135deg,var(--brand),var(--brand-strong));display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:800;color:#1a0e0b;flex-shrink:0}
.result-info{min-width:0}
.result-name{font-size:15px;font-weight:700;color:#141b26;display:flex;align-items:center;gap:8px}
.result-username{font-size:12px;color:var(--text-dim);font-weight:500;font-family:'SF Mono',Menlo,monospace}
.result-meta{font-size:12px;color:var(--text-muted);margin-top:4px;display:flex;gap:14px;flex-wrap:wrap}
.result-stats{text-align:right;font-size:12px;color:var(--text-muted);font-weight:600;white-space:nowrap}
.result-stats b{color:var(--brand);font-size:14px}

/* Inline accordion detail under each result */
.result-wrap{display:flex;flex-direction:column}
.result-detail{display:none;background:rgba(17,24,39,0.032);border:1px solid var(--border);border-top:none;border-radius:0 0 12px 12px;margin-top:-4px;padding:6px 18px 16px}
.result-detail.open{display:block}
.result.selected{border-radius:12px 12px 0 0}
.rd-addr{font-size:12px;color:var(--text-muted);padding:10px 2px 6px;line-height:1.6}
.rd-addr .addr-pill{display:inline-block;background:rgba(17,24,39,0.064);padding:5px 10px;border-radius:8px;margin:0 6px 6px 0}

/* Empty / loading */
.empty{text-align:center;padding:80px 20px;color:var(--text-dim);background:var(--surface);border:1px dashed var(--border);border-radius:14px}
.empty-icon{font-size:56px;margin-bottom:14px;opacity:.5}
.empty-title{font-size:18px;font-weight:700;color:var(--text-muted);margin-bottom:6px}
.empty-sub{font-size:14px}
.loading{text-align:center;padding:40px;color:var(--text-dim);font-size:13px}

/* Customer detail panel (slides in below search) */
.detail{margin-top:24px;background:var(--surface);border:1px solid var(--border);border-radius:18px;overflow:hidden;display:none}
.detail.show{display:block}
.detail-head{padding:26px 28px;background:linear-gradient(135deg,rgba(217,116,143,.08),rgba(217,116,143,.01));border-bottom:1px solid var(--border);display:flex;gap:18px;align-items:flex-start;flex-wrap:wrap}
.detail-avatar{width:64px;height:64px;border-radius:50%;background:linear-gradient(135deg,var(--brand),var(--brand-strong));display:flex;align-items:center;justify-content:center;font-size:26px;font-weight:900;color:#1a0e0b;flex-shrink:0}
.detail-meta{flex:1;min-width:240px}
.detail-name{font-size:24px;font-weight:900;color:#141b26;line-height:1.1;margin-bottom:4px}
.detail-username{font-size:13px;color:var(--brand);font-family:'SF Mono',Menlo,monospace;margin-bottom:14px}
.detail-stats{display:flex;gap:24px;flex-wrap:wrap}
.dstat{font-size:12px;color:var(--text-muted)}
.dstat b{display:block;color:#141b26;font-size:20px;font-weight:800;line-height:1;margin-bottom:3px}

.section-title{font-size:13px;font-weight:800;color:var(--text-dim);text-transform:uppercase;letter-spacing:2px;display:flex;align-items:center;gap:10px;padding:22px 28px 10px}
.section-title .dot{width:8px;height:8px;border-radius:50%;background:var(--brand)}
.section-title .count{font-size:11px;background:rgba(17,24,39,0.096);padding:2px 8px;border-radius:6px;font-weight:700;color:var(--text-muted)}

.addresses{padding:0 28px 18px}
.addr-pill{display:inline-block;font-size:12px;color:var(--text-muted);background:rgba(17,24,39,0.064);padding:6px 12px;border-radius:8px;margin-right:6px;margin-bottom:6px;line-height:1.4}

.ships{padding:0 28px 20px;display:flex;flex-direction:column;gap:10px}
.ship{padding:16px 18px;background:rgba(17,24,39,0.032);border:1px solid var(--border);border-radius:12px}
.ship-head{display:flex;justify-content:space-between;align-items:flex-start;gap:14px;margin-bottom:8px;flex-wrap:wrap}
.ship-id{font-family:'SF Mono',Menlo,monospace;font-size:13px;color:var(--text-muted)}
.ship-tracking{color:var(--brand);font-weight:700;font-size:13px;font-family:'SF Mono',Menlo,monospace}
.ship-show-date{font-size:12px;color:var(--text-dim)}
.ship-status{font-size:10px;padding:3px 9px;border-radius:6px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;display:inline-block}
.st-pending{background:rgba(148,163,184,.12);color:#64748b}
.st-packed{background:rgba(16,185,129,.14);color:#059669}
.st-shipped{background:rgba(99,102,241,.14);color:#4f46e5}
.ship-items{font-size:12px;color:var(--text-muted);margin-top:6px;line-height:1.5}
.ship-items .item{display:inline-block;background:rgba(17,24,39,0.064);padding:3px 9px;border-radius:6px;margin:3px 4px 0 0;font-size:11px}
.ship-rec{margin-top:10px;padding-top:10px;border-top:1px solid rgba(17,24,39,0.064);font-size:12px;color:var(--text-muted);display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.ship-rec a{color:var(--brand);text-decoration:none;font-weight:700}
.ship-rec a:hover{text-decoration:underline}
</style>
</head><body data-role="__ROLE__">
__NAVBAR__
<div class="wrap">
  <div class="page-head">
    <div class="page-title">🔎 Customer search</div>
    <div class="page-sub">Look up any buyer — see their shipments, addresses, items, and packing recordings</div>
  </div>

  <div class="search-box">
    <span class="icon">🔍</span>
    <input type="text" id="q" placeholder="Search by username or name (type at least 2 letters)" autocomplete="off" autofocus>
    <button class="clear" id="clearBtn">✕</button>
  </div>

  <div id="info" class="results-info" style="display:none"></div>
  <div id="results" class="results"></div>
</div>

<script>
var resultsEl=document.getElementById('results'),infoEl=document.getElementById('info');
var qEl=document.getElementById('q'),clearBtn=document.getElementById('clearBtn');
var debounceTimer=null;

function escapeHtml(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
function initial(s){return (s||'?').charAt(0).toUpperCase()}
function fmtDate(s){if(!s)return '';try{return new Date(s).toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'})}catch(e){return s.slice(0,10)}}
function trackUrl(t){t=(t||'').trim();if(!t)return '';
  if(/^1Z/i.test(t))return 'https://www.ups.com/track?loc=en_US&tracknum='+encodeURIComponent(t);
  return 'https://tools.usps.com/go/TrackConfirmAction?tLabels='+encodeURIComponent(t);}

function showEmpty(title,sub){
  resultsEl.innerHTML='<div class="empty"><div class="empty-icon">🔍</div><div class="empty-title">'+title+'</div><div class="empty-sub">'+sub+'</div></div>';
}

function search(q){
  if(q.length<2){
    resultsEl.innerHTML='';infoEl.style.display='none';
    if(q.length===0)showEmpty('Start typing to search','Type a username or partial name above');
    return;
  }
  resultsEl.innerHTML='<div class="loading">Searching…</div>';
  fetch('/api/customers/search?q='+encodeURIComponent(q)).then(function(r){return r.json()}).then(function(rows){
    if(!rows||rows.length===0){
      showEmpty('No matches','Try a different spelling or shorter search');
      infoEl.style.display='none';return;
    }
    infoEl.textContent='Found '+rows.length+' '+(rows.length===1?'customer':'customers');
    infoEl.style.display='block';
    resultsEl.innerHTML=rows.map(function(r){
      return '<div class="result-wrap">'+
        '<div class="result" data-u="'+escapeHtml(r.buyer_username)+'">'+
          '<div class="result-avatar">'+initial(r.buyer_name||r.buyer_username)+'</div>'+
          '<div class="result-info">'+
            '<div class="result-name">'+escapeHtml(r.buyer_name||'(no name)')+
              ' <span class="result-username">@'+escapeHtml(r.buyer_username)+'</span></div>'+
            '<div class="result-meta">'+
              '<span>📍 '+escapeHtml((r.last_address||'').split(',').slice(1,3).join(',').trim()||'no address')+'</span>'+
              (r.last_show?'<span>🕒 last '+fmtDate(r.last_show)+'</span>':'')+
            '</div>'+
          '</div>'+
          '<div class="result-stats"><b>'+r.shipments+'</b> '+(r.shipments===1?'shipment':'shipments')+'<br>'+r.total_items+' items</div>'+
        '</div>'+
        '<div class="result-detail"></div>'+
      '</div>';
    }).join('');
    resultsEl.querySelectorAll('.result').forEach(function(el){
      el.addEventListener('click',function(){
        var wrap=el.parentNode, panel=wrap.querySelector('.result-detail');
        var wasOpen=panel.classList.contains('open');
        resultsEl.querySelectorAll('.result').forEach(function(x){x.classList.remove('selected')});
        resultsEl.querySelectorAll('.result-detail').forEach(function(p){p.classList.remove('open')});
        if(wasOpen)return;             // toggle closed
        el.classList.add('selected');panel.classList.add('open');
        if(!panel.dataset.loaded){panel.dataset.loaded='1';loadDetail(el.dataset.u,panel);}
      });
    });
    if(rows.length===1){resultsEl.querySelector('.result').click();}
  });
}

function loadDetail(username,panel){
  panel.innerHTML='<div class="loading">Loading…</div>';
  fetch('/api/customers/'+encodeURIComponent(username)).then(function(r){return r.json()}).then(function(d){
    if(!d.ok){panel.innerHTML='<div class="loading">Could not load: '+(d.error||'?')+'</div>';return}
    var html='';
    if(d.addresses && d.addresses.length){
      html+='<div class="rd-addr">'+d.addresses.map(function(a){return '<span class="addr-pill">📍 '+escapeHtml(a)+'</span>'}).join('')+'</div>';
    }
    html+='<div class="ships" style="padding:4px 0 0">';
    if(!d.shipments.length){html+='<div class="loading">No shipments yet</div>';}
    else {
      html+=d.shipments.map(function(s){
        var recs=d.recordings.filter(function(r){return r.tracking===s.shipment_id||r.tracking===s.tracking_code});
        var itemsHtml=(s.items||[]).map(function(it){return '<span class="item">'+escapeHtml(it.product_name||it.sku||'?')+' ×'+it.quantity+'</span>'}).join('');
        var trk=s.tracking_code?('<a class="ship-tracking" href="'+trackUrl(s.tracking_code)+'" target="_blank" rel="noopener">'+escapeHtml(s.tracking_code)+' ↗</a>'):'';
        var vids=recs.map(function(r){return r.video_file?'<a href="/media/video/'+encodeURIComponent(r.video_file)+'" target="_blank">🎥 Watch ('+(r.duration||'?')+'s)</a>':''}).filter(Boolean).join(' · ');
        var photo=recs.map(function(r){return r.photo_file?'<a href="/media/photo/'+encodeURIComponent(r.photo_file)+'" target="_blank">📷 Photo</a>':''}).filter(Boolean).join(' · ');
        var recHtml = recs.length
          ? '<div class="ship-rec">📹 Packed by <b style="color:var(--text-muted)">'+escapeHtml(recs[0].worker||'?')+'</b> · '+escapeHtml(recs[0].date||'')+' '+escapeHtml(recs[0].time||'')+(vids?(' · '+vids):'')+(photo?(' · '+photo):'')+'</div>'
          : '<div class="ship-rec" style="color:var(--text-dim)">📹 No packing video found for this package</div>';
        return '<div class="ship">'+
          '<div class="ship-head">'+
            '<div><span class="ship-id">'+escapeHtml(s.shipment_id)+'</span>'+(trk?(' · '+trk):'')+'</div>'+
            '<div><span class="ship-status st-'+s.status+'">'+s.status.replace('_',' ')+'</span> '+
              '<span class="ship-show-date">'+fmtDate(s.show_date)+'</span></div>'+
          '</div>'+
          '<div class="ship-items"><b style="color:var(--text-muted)">'+s.total_items+' items</b> · '+itemsHtml+'</div>'+
          recHtml+
        '</div>';
      }).join('');
    }
    html+='</div>';
    panel.innerHTML=html;
  });
}

qEl.addEventListener('input',function(){
  clearBtn.classList.toggle('show', qEl.value.length>0);
  clearTimeout(debounceTimer);
  debounceTimer=setTimeout(function(){search(qEl.value.trim())},250);
});
clearBtn.addEventListener('click',function(){qEl.value='';clearBtn.classList.remove('show');qEl.focus();search('')});
showEmpty('Start typing to search','Type a username or partial name above');
</script>
</body></html>'''


# ══════════════════════════════════════════════════════════
# SKU RECONCILIATION — end-of-show leftover item finder
# ══════════════════════════════════════════════════════════

SKU_LOOKUP_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>SKU Lookup — __BRANDMARK__</title>
__NAVBAR_CSS__
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'DM Sans',-apple-system,sans-serif;background:#ffffff;color:var(--text);min-height:100vh;padding-bottom:120px;-webkit-font-smoothing:antialiased}
.wrap{max-width:1100px;margin:0 auto;padding:40px 28px 0}
.page-head{margin-bottom:28px}
.page-title{font-size:32px;font-weight:900;color:#141b26;letter-spacing:-.5px;line-height:1.05}
.page-sub{color:var(--text-muted);margin-top:6px;font-size:14px}

/* Big sticky search */
.search-row{display:grid;grid-template-columns:1fr 240px;gap:14px;margin-bottom:26px}
@media(max-width:640px){.search-row{grid-template-columns:1fr}}
.sku-input-wrap{position:relative}
.sku-input{width:100%;background:var(--surface);border:2px solid var(--border);border-radius:14px;padding:24px 28px 24px 60px;font-size:36px;font-weight:900;color:var(--brand);font-family:'SF Mono',Menlo,monospace;outline:none;transition:all .2s;letter-spacing:2px;text-align:center;font-variant-numeric:tabular-nums}
.sku-input:focus{border-color:var(--brand);box-shadow:0 0 0 4px rgba(217,116,143,.12)}
.sku-input::placeholder{color:var(--text-dim);font-weight:600;letter-spacing:.5px;font-size:18px;font-family:'DM Sans',sans-serif}
.sku-icon{position:absolute;left:20px;top:50%;transform:translateY(-50%);font-size:22px;color:var(--text-muted)}
.batch-select{background:var(--surface);border:2px solid var(--border);border-radius:14px;padding:0 18px;color:var(--text);font-family:inherit;font-size:14px;font-weight:600;cursor:pointer;outline:none;transition:border .15s}
.batch-select:focus{border-color:var(--brand)}

/* Results */
.results-info{font-size:13px;color:var(--text-dim);margin-bottom:14px;display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap}
.results-info b{color:var(--brand);font-weight:700}

.match{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:18px 22px;margin-bottom:10px;display:grid;grid-template-columns:auto 1fr auto;gap:18px;align-items:center}
.match.packed{border-left:3px solid #059669}
.match.pending{border-left:3px solid #b45309}
.match.cancelled{border-left:3px solid #e11d48;background:rgba(244,63,94,.04)}

.match-status{font-size:11px;font-weight:800;letter-spacing:.6px;text-transform:uppercase;padding:5px 12px;border-radius:8px;white-space:nowrap;min-width:90px;text-align:center}
.match-status.pending{background:rgba(251,191,36,.16);color:#b45309}
.match-status.packed{background:rgba(16,185,129,.14);color:#059669}
.match-status.shipped{background:rgba(99,102,241,.14);color:#4f46e5}
.match-status.cancelled{background:rgba(244,63,94,.16);color:#e11d48}

.match-info{min-width:0}
.match-name{font-size:15px;font-weight:700;color:#141b26;margin-bottom:4px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.match-product{font-size:13px;color:var(--text-muted);margin-bottom:4px}
.match-meta{font-size:12px;color:var(--text-dim);display:flex;gap:14px;flex-wrap:wrap;align-items:center}
.match-meta .label{color:var(--text-muted);font-weight:600}
.match-meta .id{font-family:'SF Mono',Menlo,monospace;font-size:11px}
.match-cancel{margin-top:6px;font-size:12px;color:#e11d48;font-weight:600}

.match-action{text-align:right;min-width:130px}
.action-pill{font-size:11px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;padding:6px 12px;border-radius:8px;display:inline-block}
.action-pill.go{background:rgba(217,116,143,.12);color:var(--brand)}
.action-pill.keep{background:rgba(148,163,184,.12);color:#64748b}
.action-pill.done{background:rgba(16,185,129,.1);color:#059669}
.match-tracking{font-size:11px;font-family:'SF Mono',Menlo,monospace;color:var(--brand);margin-top:4px;font-weight:700}

.empty{text-align:center;padding:80px 20px;color:var(--text-dim);background:var(--surface);border:1px dashed var(--border);border-radius:14px}
.empty-icon{font-size:64px;margin-bottom:14px;opacity:.5}
.empty-title{font-size:18px;font-weight:700;color:var(--text-muted);margin-bottom:6px}
.empty-sub{font-size:14px}

/* Summary tiles when there's data */
.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:18px}
.sum{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px 16px;text-align:center}
.sum .val{font-size:24px;font-weight:900;color:#141b26;line-height:1}
.sum .lbl{font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.6px;font-weight:700;margin-top:6px}
.sum.warn .val{color:#b45309}
.sum.good .val{color:#059669}
.sum.bad .val{color:#e11d48}
</style>
</head><body data-role="__ROLE__">
__NAVBAR__
<div class="wrap">
  <div class="page-head">
    <div class="page-title">🔢 SKU Reconciliation</div>
    <div class="page-sub">Type a sticker number to find where it went. Use at the end of packing to track down leftover items on the tables.</div>
  </div>

  <div class="search-row">
    <div class="sku-input-wrap">
      <span class="sku-icon">🏷️</span>
      <input type="text" id="sku" class="sku-input" placeholder="Type sticker number…" inputmode="numeric" autofocus autocomplete="off">
    </div>
    <select class="batch-select" id="batch"><option value="">All shows / batches</option></select>
  </div>

  <div id="resultsArea"></div>
</div>

<script>
function escapeHtml(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function fmtDate(s){if(!s)return '';try{return new Date(s).toLocaleDateString(undefined,{month:'short',day:'numeric'})}catch(e){return s.slice(0,10)}}

// Highlight "Part N" pattern in product names — bold and colored, just like SKU numbers
function highlightPart(s){
  if(!s)return s;
  return s.replace(/(Part\s*\d+)/gi,'<b style="color:var(--brand);font-weight:800">$1</b>');
}

// Load shows (grouped — one row per show name across all CSVs)
fetch('/api/sku-lookup/batches').then(function(r){return r.json()}).then(function(batches){
  var sel=document.getElementById('batch');
  batches.forEach(function(b){
    var opt=document.createElement('option');
    opt.value=b.label||'';
    var platforms=b.platform||'';
    opt.textContent=(b.label||'(unnamed)')+' · '+b.shipments+' shipments'+(platforms?' · '+platforms:'');
    sel.appendChild(opt);
  });
});

var debounce=null;
function doSearch(){
  var sku=document.getElementById('sku').value.trim();
  var batch=document.getElementById('batch').value;
  var area=document.getElementById('resultsArea');
  if(!sku){
    area.innerHTML='<div class="empty"><div class="empty-icon">🏷️</div><div class="empty-title">Type a SKU number above</div><div class="empty-sub">Look at the sticker on the item — type the number on it (e.g. "12", "85", "247")</div></div>';
    return;
  }
  area.innerHTML='<div class="empty">Looking up SKU '+escapeHtml(sku)+'…</div>';
  var url='/api/sku-lookup/'+encodeURIComponent(sku);
  if(batch)url+='?label='+encodeURIComponent(batch);
  fetch(url).then(function(r){return r.json()}).then(function(d){
    if(!d.ok){area.innerHTML='<div class="empty">'+escapeHtml(d.error||'Error')+'</div>';return}
    var m=d.matches||[];
    if(m.length===0){
      area.innerHTML='<div class="empty"><div class="empty-icon">🤷</div><div class="empty-title">No order found for SKU '+escapeHtml(sku)+'</div><div class="empty-sub">This sticker number was not sold this show. Return the item to inventory.</div></div>';
      return;
    }
    // Summary
    var pending=m.filter(function(x){return x.status==='pending'&&!x.cancelled}).length;
    var packed=m.filter(function(x){return (x.status==='packed'||x.status==='shipped')&&!x.cancelled}).length;
    var cancelled=m.filter(function(x){return x.cancelled||x.status==='cancelled'}).length;
    var summary='<div class="summary">'+
      '<div class="sum"><div class="val">'+m.length+'</div><div class="lbl">Total matches</div></div>'+
      (pending>0?'<div class="sum warn"><div class="val">'+pending+'</div><div class="lbl">Pending (still to pack)</div></div>':'')+
      (packed>0?'<div class="sum good"><div class="val">'+packed+'</div><div class="lbl">Packed / shipped</div></div>':'')+
      (cancelled>0?'<div class="sum bad"><div class="val">'+cancelled+'</div><div class="lbl">Cancelled</div></div>':'')+
      '</div>';
    var html=summary+m.map(function(x){
      var cls=x.cancelled?'cancelled':(x.status==='packed'||x.status==='shipped'?'packed':'pending');
      var statusText=x.cancelled?'Cancelled':x.status;
      var action,actionCls;
      if(x.cancelled){
        action='Keep aside';actionCls='keep';
      } else if(x.status==='pending'){
        action='⚠️ Add to package';actionCls='go';
      } else {
        action='Already packed';actionCls='done';
      }
      var meta='<div class="match-meta">'+
        '<span><span class="label">Buyer:</span> '+escapeHtml(x.buyer_name||x.buyer_username||'?')+'</span>'+
        (x.shipment_id&&!x.shipment_id.startsWith('cancel_')?'<span><span class="label">Package:</span> <span class="id">'+escapeHtml(x.shipment_id)+'</span></span>':'')+
        '<span><span class="label">Batch:</span> '+escapeHtml(x.import_label||x.import_batch||'?')+'</span>'+
        '<span><span class="label">Platform:</span> '+(x.platform||'?')+'</span>'+
        '</div>';
      return '<div class="match '+cls+'">'+
        '<div class="match-status '+cls+'">'+statusText+'</div>'+
        '<div class="match-info">'+
          '<div class="match-name">SKU '+escapeHtml(x.sku)+' × '+x.quantity+(x.product_name?'<span style="font-weight:400;color:var(--text-muted);font-size:13px">— '+highlightPart(escapeHtml(x.product_name))+'</span>':'')+'</div>'+
          meta+
          (x.cancel_reason?'<div class="match-cancel">⚠️ '+escapeHtml(x.cancel_reason)+'</div>':'')+
        '</div>'+
        '<div class="match-action">'+
          '<span class="action-pill '+actionCls+'">'+action+'</span>'+
          (x.tracking_code?'<div class="match-tracking">'+escapeHtml(x.tracking_code)+'</div>':'')+
        '</div>'+
      '</div>';
    }).join('');
    area.innerHTML=html;
  });
}

document.getElementById('sku').addEventListener('input',function(){
  clearTimeout(debounce);debounce=setTimeout(doSearch,200);
});
document.getElementById('batch').addEventListener('change',doSearch);
doSearch();  // initial empty state
</script>
</body></html>'''


# ══════════════════════════════════════════════════════════
# SHOWS — index of active shows from last 5 days
# Each show groups one or more CSV imports under a user-supplied name.
# Multiple shows can be active simultaneously (workers pack across).
# ══════════════════════════════════════════════════════════

SHOWS_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Shows — __BRANDMARK__</title>
__NAVBAR_CSS__
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'DM Sans',-apple-system,sans-serif;background:#ffffff;color:var(--text);min-height:100vh;padding-bottom:120px;-webkit-font-smoothing:antialiased}
.wrap{max-width:1280px;margin:0 auto;padding:40px 28px 0}
.page-head{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;margin-bottom:6px;flex-wrap:wrap}
.page-title{font-size:32px;font-weight:900;color:#141b26;letter-spacing:-.5px;line-height:1.05}
.window-pill{display:inline-flex;align-items:center;gap:6px;background:rgba(217,116,143,.1);border:1px solid rgba(217,116,143,.2);color:var(--brand);padding:6px 14px;border-radius:20px;font-size:12px;font-weight:700;letter-spacing:.4px;text-transform:uppercase}
.page-sub{color:var(--text-muted);margin-top:8px;font-size:14px;margin-bottom:26px}
.go-import-btn{background:var(--brand);color:#1a0e0b;border:none;border-radius:12px;padding:12px 22px;font-size:14px;font-weight:800;cursor:pointer;font-family:inherit;text-decoration:none;display:inline-flex;align-items:center;gap:8px;transition:all .15s}
.go-import-btn:hover{background:var(--brand-strong);transform:translateY(-1px)}

/* Top KPI strip */
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:32px}
.kpi{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:18px 22px}
.kpi .lbl{font-size:11px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.8px;font-weight:700}
.kpi .val{font-size:32px;font-weight:900;color:#141b26;line-height:1;margin-top:8px}
.kpi.brand .val{color:var(--brand)}
.kpi.good .val{color:#059669}
.kpi.warn .val{color:#b45309}
.kpi.bad .val{color:#e11d48}

/* Show cards grid */
.shows-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:16px}
.show-card{display:block;background:var(--surface);border:1px solid var(--border);border-radius:18px;padding:24px;text-decoration:none;color:inherit;transition:all .2s;position:relative;overflow:hidden}
.show-card:hover{transform:translateY(-3px);border-color:rgba(217,116,143,.25);background:rgba(17,24,39,0.072)}
.show-card-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:18px}
.show-card-name{font-size:20px;font-weight:800;color:#141b26;line-height:1.2;flex:1;min-width:0}
.platform-pill{font-size:10px;padding:3px 9px;border-radius:6px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;white-space:nowrap;flex-shrink:0}
.platform-tiktok{background:rgba(244,63,94,.14);color:#e11d48}
.platform-whatnot{background:rgba(168,85,247,.14);color:#7c3aed}
.platform-mixed{background:rgba(99,102,241,.14);color:#4f46e5}

.show-totals{display:flex;align-items:baseline;gap:8px;margin-bottom:14px}
.show-totals .big{font-size:38px;font-weight:900;color:var(--brand);line-height:1;font-feature-settings:'tnum'}
.show-totals .small{font-size:13px;color:var(--text-muted);font-weight:600}

.show-progress{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:14px}
.sp{background:rgba(17,24,39,0.048);border-radius:8px;padding:8px 10px;text-align:center}
.sp .v{font-size:16px;font-weight:800;line-height:1}
.sp .l{font-size:9px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.4px;font-weight:700;margin-top:4px}
.sp.pending .v{color:#b45309}
.sp.packed .v{color:#059669}
.sp.shipped .v{color:#4f46e5}
.sp.cancelled .v{color:#e11d48}

.show-bar{height:6px;background:rgba(17,24,39,0.08);border-radius:4px;overflow:hidden;display:flex;margin-bottom:14px}
.bar-packed{background:#059669;height:100%}
.bar-shipped{background:#4f46e5;height:100%}
.bar-cancelled{background:#e11d48;height:100%}
.bar-pending{background:#b45309;height:100%;opacity:.5}

.show-footer{font-size:12px;color:var(--text-dim);display:flex;justify-content:space-between;align-items:center;border-top:1px solid var(--border);padding-top:12px;margin-top:auto}
.show-footer .when b{color:var(--text-muted);font-weight:600}
.show-cta{color:var(--brand);font-weight:700;font-size:12px}

.empty{text-align:center;padding:80px 20px;background:var(--surface);border:1px dashed var(--border);border-radius:18px;color:var(--text-dim)}
.empty-icon{font-size:56px;margin-bottom:14px;opacity:.5}
.empty-title{font-size:18px;font-weight:700;color:var(--text-muted);margin-bottom:6px}
.empty-sub{font-size:14px;margin-bottom:20px}
</style>
</head><body data-role="__ROLE__">
__NAVBAR__
<div class="wrap">
  <div class="page-head">
    <div>
      <div class="page-title">📺 Shows</div>
    </div>
    <a href="/admin/shipments" class="go-import-btn">＋ Import a CSV</a>
  </div>
  <div class="page-sub">
    <span class="window-pill">Last 5 days</span>
    <span style="margin-left:12px">Active shows currently being packed. Click any show to see its packages.</span>
  </div>

  <div class="kpis" id="kpis"></div>

  <div id="grid"></div>
</div>

<script>
function escapeHtml(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
function fmtDateShort(s){if(!s)return '';try{return new Date(s).toLocaleString(undefined,{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'})}catch(e){return s}}

var SHOWS=[];
function loadShows(){fetch('/api/shows').then(function(r){return r.json()}).then(function(shows){SHOWS=shows||[];renderKpis();renderGrid();});}
function renderKpis(){
  var t=0,p=0,d=0,s=0,x=0;
  SHOWS.forEach(function(sh){t+=sh.shipments;p+=sh.pending||0;d+=sh.packed||0;s+=sh.shipped||0;x+=sh.cancelled||0});
  document.getElementById('kpis').innerHTML=
    '<div class="kpi brand"><div class="lbl">Active shows</div><div class="val">'+SHOWS.length+'</div></div>'+
    '<div class="kpi"><div class="lbl">Total shipments</div><div class="val">'+t+'</div></div>'+
    '<div class="kpi warn"><div class="lbl">Pending</div><div class="val">'+p+'</div></div>'+
    '<div class="kpi good"><div class="lbl">Packed</div><div class="val">'+(d+s)+'</div></div>'+
    '<div class="kpi bad"><div class="lbl">Cancelled</div><div class="val">'+x+'</div></div>';
}
function dropCard(name){
  var el=document.querySelector('.show-card[data-show="'+encodeURIComponent(name)+'"]');
  if(el)el.remove();
  SHOWS=SHOWS.filter(function(s){return s.name!==name});
  renderKpis();
  if(!SHOWS.length)renderGrid();
}
function renderGrid(){
  var shows=SHOWS;
  var grid=document.getElementById('grid');
  if(!shows||shows.length===0){
    grid.innerHTML='<div class="empty"><div class="empty-icon">📺</div><div class="empty-title">No active shows</div><div class="empty-sub">No CSVs have been imported in the last 5 days.</div><a href="/admin/shipments" class="go-import-btn">＋ Import your first show</a></div>';
    return;
  }
  grid.innerHTML='<div class="shows-grid">'+shows.map(function(sh){
    var packed=(sh.packed||0)+(sh.shipped||0);
    var total=sh.shipments;
    var pctP=total?(100*(sh.packed||0)/total):0;
    var pctS=total?(100*(sh.shipped||0)/total):0;
    var pctC=total?(100*(sh.cancelled||0)/total):0;
    var pctPnd=total?(100*(sh.pending||0)/total):0;
    var isWhatnot=(sh.platform==='whatnot' && (sh.platform_count||1)<=1);
    var platCls='platform-'+(sh.platform||'mixed');
    if(sh.platform_count>1)platCls='platform-mixed';
    var platName=sh.platform_count>1?'Mixed':(sh.platform||'?');
    // NEW = uploaded, nobody touched it yet; DONE = manually marked, or nothing pending.
    var untouched=(packed===0 && total>0);
    var isDone=sh.done||((sh.pending||0)===0 && total>0);
    // Whole-card highlight: colored border + full-width banner so status is obvious.
    var cardStyle='position:relative;';
    var banner='';
    if(isDone){
      cardStyle+='border:2px solid rgba(52,211,153,.65);box-shadow:0 0 0 1px rgba(52,211,153,.25),0 0 24px rgba(52,211,153,.12);';
      banner='<div style="background:linear-gradient(90deg,rgba(52,211,153,.25),rgba(52,211,153,.12));color:#059669;font-weight:900;text-align:center;padding:8px;border-radius:10px;margin-bottom:12px;letter-spacing:2px;font-size:14px">✓ DONE</div>';
    } else if(untouched){
      cardStyle+='border:2px solid rgba(96,165,250,.65);box-shadow:0 0 0 1px rgba(96,165,250,.25),0 0 24px rgba(96,165,250,.12);';
      banner='<div style="background:linear-gradient(90deg,rgba(96,165,250,.28),rgba(96,165,250,.12));color:#2563eb;font-weight:900;text-align:center;padding:8px;border-radius:10px;margin-bottom:12px;letter-spacing:2px;font-size:14px">● NEW · not started</div>';
    }
    return '<a href="/admin/shipments?show='+encodeURIComponent(sh.name)+'" class="show-card" data-show="'+encodeURIComponent(sh.name)+'" style="'+cardStyle+'">'+
      banner+
      '<div class="show-card-head">'+
        '<div class="show-card-name">'+escapeHtml(sh.name)+'</div>'+
        '<span class="platform-pill '+platCls+'">'+platName+'</span>'+
      '</div>'+
      '<div class="show-totals"><span class="big">'+total+'</span><span class="small">shipments</span></div>'+
      '<div class="show-bar">'+
        (sh.shipped?'<div class="bar-shipped" style="width:'+pctS+'%"></div>':'')+
        (sh.packed?'<div class="bar-packed" style="width:'+pctP+'%"></div>':'')+
        (sh.pending?'<div class="bar-pending" style="width:'+pctPnd+'%"></div>':'')+
        ((!isWhatnot&&sh.cancelled)?'<div class="bar-cancelled" style="width:'+pctC+'%"></div>':'')+
      '</div>'+
      '<div class="show-progress">'+
        '<div class="sp pending"><div class="v">'+(sh.pending||0)+'</div><div class="l">Pending</div></div>'+
        '<div class="sp packed"><div class="v">'+(sh.packed||0)+'</div><div class="l">Packed</div></div>'+
        '<div class="sp shipped"><div class="v">'+(sh.shipped||0)+'</div><div class="l">Shipped</div></div>'+
        (isWhatnot?'':'<div class="sp cancelled"><div class="v">'+(sh.cancelled||0)+'</div><div class="l">Cancelled</div></div>')+
      '</div>'+
      '<div class="show-footer">'+
        '<div class="when">Last import <b>'+fmtDateShort(sh.last_import)+'</b>'+(sh.done&&sh.done_by?'<br><span style="color:#059669">✓ done by '+escapeHtml(sh.done_by)+'</span>':'')+'</div>'+
        '<div style="display:flex;gap:6px;align-items:center">'+
          '<button onclick="toggleDone(event,\\''+encodeURIComponent(sh.name)+'\\','+(sh.done?'false':'true')+')" style="background:'+(sh.done?'rgba(17,24,39,0.128)':'rgba(52,211,153,.15)')+';color:'+(sh.done?'#586274':'#059669')+';border:1px solid '+(sh.done?'rgba(17,24,39,0.16)':'rgba(52,211,153,.35)')+';border-radius:8px;padding:6px 12px;font-size:12px;font-weight:700;cursor:pointer;font-family:inherit">'+(sh.done?'↩︎ Undo':'✓ Mark DONE')+'</button>'+
          '<button onclick="deleteShow(event,\\''+encodeURIComponent(sh.name)+'\\')" title="Delete this show (manager PIN)" style="background:rgba(244,63,94,.1);color:#e11d48;border:1px solid rgba(244,63,94,.25);border-radius:8px;padding:6px 10px;font-size:12px;font-weight:700;cursor:pointer;font-family:inherit">🗑</button>'+
        '</div>'+
      '</div>'+
    '</a>';
  }).join('')+'</div>';
}
loadShows();
function toggleDone(ev,name,done){
  ev.preventDefault();ev.stopPropagation();
  var nm=decodeURIComponent(name);
  var pin=prompt(done?'Enter Manager PIN to mark this show DONE:':'Enter Manager PIN to undo DONE:');
  if(pin===null)return;
  fetch('/api/shows/done',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({label:nm,done:done,pin:pin})})
   .then(function(r){return r.json()}).then(function(d){
     if(d.ok){if(done){dropCard(nm);}else{loadShows();}return}
     if(d.need_pin_setup){alert('No Manager PIN set yet. An admin must set it in Team → Permissions.');return}
     alert(d.error||'Failed');
   }).catch(function(){alert('Request failed')});
}
function deleteShow(ev,name){
  ev.preventDefault();ev.stopPropagation();
  var nm=decodeURIComponent(name);
  if(!confirm('Permanently DELETE the show "'+nm+'" and all of its shipments? This cannot be undone — use it only to remove a wrong CSV import.'))return;
  var pin=prompt('Enter Manager PIN to delete this show:');
  if(pin===null)return;
  fetch('/api/shows/delete',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({label:nm,pin:pin})})
   .then(function(r){return r.json()}).then(function(d){
     if(d.ok){dropCard(nm);return}
     if(d.need_pin_setup){alert('No Manager PIN set yet. An admin must set it in Team → Permissions.');return}
     alert(d.error||'Failed');
   }).catch(function(){alert('Request failed')});
}
</script>
</body></html>'''


# ══════════════════════════════════════════════════════════
# PICKING — iPad-optimised picker workflow.
# Pickers walk the warehouse with an iPad, see the queue of orders that
# need items pulled, tap a shipment, walk to the tables and tap each item
# as they grab it. Done → ships moves to 'picked' status for the packer.
# ══════════════════════════════════════════════════════════

PICK_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
''' + _FONT + '''
<title>Pick · __BRANDMARK__</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
html,body{height:100%;overflow:hidden;background:var(--bg);color:var(--text);font-family:'DM Sans',-apple-system,sans-serif;-webkit-font-smoothing:antialiased;transition:background .25s,color .25s}
:root{
    --brand:#d9748f;
    --brand-strong:#c25c79;
    --bg:#ffffff;
    --top-bg:#ffffff;
    --surface:rgba(17,24,39,0.064);
    --surface-strong:#ffffff;
    --border:rgba(17,24,39,0.128);
    --border-strong:rgba(17,24,39,0.16);
    --text:#1a2130;
    --text-muted:#586274;
    --text-dim:#64748b;
    --input-bg:#ffffff;
}
:root.theme-light{
    --brand:#c25c79;
    --brand-strong:#a63456;
    --bg:#f5f4f0;
    --top-bg:rgba(255,255,255,.92);
    --surface:rgba(0,0,0,.04);
    --surface-strong:#fff;
    --border:rgba(0,0,0,.1);
    --border-strong:rgba(0,0,0,.2);
    --text:#f6f7f9;
    --text-muted:#6b7280;
    --text-dim:#888896;
    --input-bg:#fff;
}

/* Top bar */
.top{position:fixed;top:0;left:0;right:0;height:60px;background:var(--top-bg);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border-bottom:1px solid var(--border);display:flex;align-items:center;padding:0 18px;gap:10px;z-index:50}
.theme-toggle{background:var(--surface);border:1px solid var(--border);color:var(--text-muted);border-radius:10px;width:38px;height:38px;font-size:16px;cursor:pointer;font-family:inherit;display:flex;align-items:center;justify-content:center}
.theme-toggle:active{transform:scale(.95)}
.role-switch-top{background:rgba(99,102,241,.12);border:1px solid rgba(99,102,241,.3);color:#4f46e5;text-decoration:none;font-size:12px;font-weight:700;padding:9px 14px;border-radius:10px;transition:all .15s;white-space:nowrap}
.role-switch-top:hover{background:rgba(99,102,241,.22)}
.brand-mark{font-size:18px;font-weight:900;color:var(--brand);letter-spacing:1.5px;line-height:1}
.brand-sub{font-size:9px;color:var(--text-dim);letter-spacing:2px;text-transform:uppercase;font-weight:700;line-height:1;margin-top:3px}
.top-brand{flex-shrink:0}
.top-show{flex:1;text-align:center;font-size:14px;color:var(--text-muted);min-width:0;overflow:hidden;text-overflow:ellipsis}
.top-show b{color:var(--brand);font-weight:800}
.top-show .change-link{color:var(--text-dim);font-size:11px;text-decoration:underline;margin-left:8px;text-decoration-color:rgba(17,24,39,0.16)}
.top-logout{background:rgba(244,63,94,.1);border:1px solid rgba(244,63,94,.22);color:#e11d48;text-decoration:none;font-size:13px;font-weight:700;padding:8px 14px;border-radius:10px}

.page{position:absolute;top:60px;left:0;right:0;bottom:0;overflow-y:auto;-webkit-overflow-scrolling:touch}

/* ───── State A: Show picker ───── */
#showView{display:none;padding:48px 24px;text-align:center;min-height:100%}
#showView.on{display:block}
.show-prompt{font-size:14px;color:var(--text-dim);letter-spacing:2px;text-transform:uppercase;font-weight:800;margin-bottom:10px}
.show-h1{font-size:36px;font-weight:900;color:var(--text);margin-bottom:8px;letter-spacing:-.6px}
.show-help{font-size:15px;color:var(--text-muted);margin-bottom:36px}
.show-list{display:flex;flex-direction:column;gap:14px;max-width:600px;margin:0 auto}
.show-card{display:block;width:100%;padding:24px 26px;background:var(--surface);border:2px solid var(--border);border-radius:18px;cursor:pointer;text-align:left;font-family:inherit;color:inherit;transition:all .15s}
.show-card:active{transform:scale(.99);background:rgba(217,116,143,.06);border-color:var(--brand)}
.show-card .name{font-size:22px;font-weight:800;color:var(--text);margin-bottom:6px}
.show-card .meta{display:flex;gap:12px;align-items:center;font-size:13px;color:var(--text-muted)}
.show-card .pill{font-size:10px;padding:3px 8px;border-radius:6px;font-weight:700;letter-spacing:.4px;text-transform:uppercase}
.show-card .pill-tiktok{background:rgba(244,63,94,.14);color:#e11d48}
.show-card .pill-whatnot{background:rgba(168,85,247,.14);color:#7c3aed}
.show-card .pill-mixed{background:rgba(99,102,241,.14);color:#4f46e5}
.show-card.show-dirty{border-color:rgba(245,158,11,.4);background:rgba(245,158,11,.04)}
.show-card.show-dirty:active{background:rgba(245,158,11,.08);border-color:#b45309}
.show-card .pending-count{margin-left:auto;font-size:22px;font-weight:900;color:var(--brand);font-feature-settings:'tnum'}
.show-card .pending-count .lbl{font-size:9px;color:var(--text-dim);font-weight:700;letter-spacing:.6px;text-transform:uppercase;display:block;text-align:right;margin-top:-3px}
.show-empty{text-align:center;padding:60px 20px;color:var(--text-dim);font-size:15px}

/* Admin: configure this iPad as a picking station */
.ipad-setup{max-width:600px;margin:36px auto 0;padding:22px 24px;background:rgba(99,102,241,.05);border:1px dashed rgba(99,102,241,.25);border-radius:14px;display:none}
.ipad-setup.on{display:block}
.ipad-setup-title{font-size:12px;color:#4f46e5;text-transform:uppercase;letter-spacing:1.5px;font-weight:800;margin-bottom:8px;display:flex;align-items:center;gap:8px}
.ipad-setup-help{font-size:13px;color:var(--text-muted);line-height:1.5;margin-bottom:14px}
.ipad-setup-actions{display:flex;gap:8px;flex-wrap:wrap}
.ipad-setup-btn{background:rgba(99,102,241,.18);border:1px solid rgba(99,102,241,.32);color:#6366f1;border-radius:10px;padding:10px 16px;font-size:13px;font-weight:700;cursor:pointer;font-family:inherit}
.ipad-setup-btn:active{transform:scale(.97)}
.ipad-setup-btn.primary{background:var(--brand);color:#1a0e0b;border-color:var(--brand)}
.ipad-setup-status{font-size:11px;color:var(--text-dim);margin-top:8px}

/* Tiny mode badge in topbar */
.mode-badge{display:none;align-items:center;gap:6px;background:rgba(99,102,241,.14);border:1px solid rgba(99,102,241,.28);color:#4f46e5;border-radius:8px;padding:5px 10px;font-size:11px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;margin-left:6px;cursor:pointer}
.mode-badge.on{display:inline-flex}

/* ───── State B: Scan-ready ───── */
#scanView{display:none;padding:30px 24px 100px;min-height:calc(100% - 60px);align-items:center;justify-content:center;flex-direction:column}
#scanView.on{display:flex}
.scan-icon{font-size:80px;margin-bottom:16px;animation:pulse 2.5s ease-in-out infinite}
@keyframes pulse{0%,100%{transform:scale(1);opacity:1}50%{transform:scale(1.05);opacity:.85}}
.scan-title{font-size:28px;font-weight:900;color:var(--text);letter-spacing:-.4px;margin-bottom:8px;text-align:center}
.scan-sub{font-size:15px;color:var(--text-muted);margin-bottom:36px;text-align:center;max-width:480px}
.scan-input-wrap{position:relative;width:100%;max-width:600px;margin-bottom:24px}
.scan-input{width:100%;background:var(--surface-strong);border:3px solid var(--brand);border-radius:18px;padding:24px 28px;font-size:28px;color:#1a2130;font-family:'SF Mono',Menlo,monospace;text-align:center;outline:none;transition:all .2s;letter-spacing:1px;box-shadow:0 0 30px rgba(217,116,143,.12)}
.scan-input:focus{border-color:var(--brand-strong);box-shadow:0 0 40px rgba(217,116,143,.25)}
.scan-input::placeholder{color:var(--text-dim);font-family:'DM Sans',sans-serif;font-size:18px;letter-spacing:.5px}
.scan-status{display:flex;align-items:center;gap:8px;font-size:14px;color:var(--text-muted);margin-bottom:32px}
.scan-status .dot{width:8px;height:8px;border-radius:50%;background:var(--brand);animation:dotpulse 1.4s ease infinite}
@keyframes dotpulse{0%,100%{opacity:.3;transform:scale(.9)}50%{opacity:1;transform:scale(1.2)}}
.stats-row{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;width:100%;max-width:600px}
.session-stat{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:14px 16px;text-align:center}
.session-stat .num{font-size:30px;font-weight:900;color:var(--text);line-height:1;font-feature-settings:'tnum';margin-bottom:4px}
.session-stat .txt{font-size:11px;color:var(--text-dim);letter-spacing:.6px;text-transform:uppercase;font-weight:700}
.session-stat .txt b{color:var(--text-muted);font-weight:700}
.session-stat.brand{background:linear-gradient(135deg,rgba(217,116,143,.12),rgba(217,116,143,.02));border-color:rgba(217,116,143,.28)}
.session-stat.brand .num{color:var(--brand)}

/* ───── State C: Checklist ───── */
#listView{display:none;padding-bottom:130px}
#listView.on{display:block}
.list-head{padding:18px 20px;background:var(--surface);border-bottom:1px solid var(--border)}
.back-btn{display:inline-flex;align-items:center;gap:6px;background:rgba(17,24,39,0.064);border:1px solid var(--border);border-radius:10px;padding:8px 14px;color:var(--text-muted);font-size:13px;font-weight:700;font-family:inherit;cursor:pointer;margin-bottom:14px}
.back-btn:active{background:rgba(17,24,39,0.128)}
.list-buyer{font-size:26px;font-weight:900;color:var(--text);letter-spacing:-.4px;margin-bottom:6px;line-height:1.15}
.list-meta{display:flex;flex-wrap:wrap;gap:6px;font-size:12px}
.list-meta .pill{padding:4px 10px;border-radius:7px;font-weight:700;font-size:11px;letter-spacing:.3px}
.pill-id{background:rgba(17,24,39,0.08);color:var(--text-muted);font-family:'SF Mono',Menlo,monospace}
.pill-track{background:rgba(99,102,241,.14);color:#4f46e5;font-family:'SF Mono',Menlo,monospace}

.progress-row{display:flex;align-items:center;gap:14px;padding:14px 20px;background:rgba(217,116,143,.04);border-bottom:1px solid var(--border)}
.progress-text{font-size:15px;color:var(--text);font-weight:700;white-space:nowrap}
.progress-text b{font-size:22px;font-weight:900;color:var(--brand)}
.progress-bar{flex:1;height:8px;background:rgba(17,24,39,0.096);border-radius:4px;overflow:hidden}
.progress-fill{height:100%;background:linear-gradient(90deg,var(--brand),var(--brand-strong));transition:width .3s}

.items-list{padding:14px 20px}
.pi{display:grid;grid-template-columns:48px 1fr auto;gap:14px;align-items:center;padding:18px 18px;background:var(--surface);border:2px solid var(--border);border-radius:16px;margin-bottom:10px;cursor:pointer;transition:all .12s;user-select:none;min-height:88px}
.pi:active{transform:scale(.98)}
.pi.done{background:rgba(16,185,129,.06);border-color:rgba(16,185,129,.22)}
.pi.done .pi-name{color:var(--text-muted);text-decoration:line-through;text-decoration-color:rgba(255,255,255,.3)}
.pi.cancelled{background:rgba(244,63,94,.04);border-color:rgba(244,63,94,.22);opacity:.55;cursor:not-allowed}
.pi.cancelled .pi-sku,.pi.cancelled .pi-name{text-decoration:line-through}
.pi-box{width:40px;height:40px;border-radius:50%;border:4px solid rgba(17,24,39,0.16);display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:900;color:transparent;flex-shrink:0;transition:all .15s}
.pi.done .pi-box{background:#10b981;border-color:#10b981;color:#ffffff}
.pi.done .pi-box::before{content:'✓'}
.pi.gv{background:rgba(16,185,129,.05);border-color:rgba(16,185,129,.3)}
.pi.gv .pi-sku{font-size:24px}
.pi.gv.done{background:rgba(16,185,129,.1);border-color:rgba(16,185,129,.45)}
.pi-info{min-width:0}
.pi-sku{font-family:'SF Mono',Menlo,monospace;font-size:30px;font-weight:900;color:var(--brand);background:rgba(217,116,143,.12);padding:6px 14px;border-radius:12px;display:inline-block;letter-spacing:1px;line-height:1;margin-bottom:6px}
.pi-name{font-size:14px;color:var(--text);line-height:1.4}
.pi-name .part-tag{display:inline-block;background:rgba(217,116,143,.18);color:var(--brand);font-family:'SF Mono',Menlo,monospace;font-weight:900;font-size:15px;padding:3px 10px;border-radius:8px;letter-spacing:1px;margin-right:6px;vertical-align:middle;text-transform:uppercase}
.pi.done .pi-name .part-tag{opacity:.5}
.pi-qty{font-size:20px;font-weight:800;color:var(--text);background:rgba(17,24,39,0.096);padding:8px 14px;border-radius:10px}

.done-bar{position:fixed;bottom:0;left:0;right:0;padding:14px 18px 18px;background:linear-gradient(180deg,transparent,var(--bg) 30%);z-index:60;display:none;flex-direction:column;gap:8px;max-width:none}
.done-bar.on{display:flex}
.issue-btn{width:100%;background:rgba(244,63,94,.08);border:1px solid rgba(244,63,94,.25);color:#e11d48;border-radius:14px;padding:14px;font-size:14px;font-weight:700;font-family:inherit;cursor:pointer;transition:all .12s}
.issue-btn:active{transform:scale(.98);background:rgba(244,63,94,.14)}
.done-btn{width:100%;background:var(--brand);color:#1a0e0b;border:none;border-radius:18px;padding:22px;font-size:18px;font-weight:900;letter-spacing:.6px;font-family:inherit;box-shadow:0 12px 36px rgba(217,116,143,.22);cursor:pointer;text-transform:uppercase;transition:all .12s}
.done-btn:active{transform:translateY(2px);box-shadow:0 6px 20px rgba(217,116,143,.18)}
.done-btn.idle{background:rgba(17,24,39,0.096);color:var(--text-muted);box-shadow:none}
.done-btn.idle:active{transform:none}

/* Cancelled overlay */
.cancel-overlay{position:fixed;inset:0;background:rgba(35,5,10,.95);backdrop-filter:blur(14px);z-index:200;display:none;align-items:center;justify-content:center;padding:30px;text-align:center;flex-direction:column}
.cancel-overlay.on{display:flex}
.cancel-overlay .icn{font-size:120px;margin-bottom:12px}
.cancel-overlay .ttl{font-size:48px;font-weight:900;color:#f43f5e;letter-spacing:2px;margin-bottom:14px}
.cancel-overlay .sub{font-size:18px;color:#e11d48;margin-bottom:30px;font-weight:600;max-width:500px;line-height:1.4}
.cancel-overlay .ok{background:#fff;color:#1a0e0b;border:none;border-radius:14px;padding:18px 36px;font-size:16px;font-weight:800;cursor:pointer;font-family:inherit}

/* Not-found toast */
.toast{position:fixed;top:80px;left:50%;transform:translateX(-50%);background:rgba(244,63,94,.95);color:#fff;padding:14px 26px;border-radius:12px;font-size:15px;font-weight:700;box-shadow:0 10px 30px rgba(244,63,94,.3);z-index:300;display:none}
.toast.on{display:block}
.toast.ok{background:rgba(16,185,129,.95)}

/* Issue report modal */
.issue-modal{position:fixed;inset:0;background:#ffffff;backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);z-index:300;display:none;align-items:center;justify-content:center;padding:24px}
.issue-modal[style*="flex"]{display:flex!important}
.issue-card{background:var(--surface-strong);border:1px solid var(--border);border-radius:22px;padding:28px;max-width:520px;width:100%;max-height:90vh;overflow-y:auto}
.issue-card h3{font-size:22px;font-weight:900;color:var(--text);margin-bottom:6px;line-height:1.2}
.issue-help{font-size:13px;color:var(--text-muted);line-height:1.5;margin-bottom:18px}
.issue-presets{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px}
.issue-presets .preset{background:rgba(17,24,39,0.08);border:1px solid var(--border);color:var(--text);border-radius:10px;padding:9px 14px;font-size:13px;font-weight:700;cursor:pointer;font-family:inherit}
.issue-presets .preset:active{background:rgba(217,116,143,.12);border-color:var(--brand);color:var(--brand)}
.issue-presets .preset.active{background:rgba(217,116,143,.16);border-color:var(--brand);color:var(--brand)}
.issue-card textarea{width:100%;background:var(--input-bg);border:1px solid var(--border);border-radius:12px;padding:12px 14px;font-size:14px;color:var(--text);font-family:inherit;resize:vertical;min-height:80px;outline:none;line-height:1.5}
.issue-card textarea:focus{border-color:var(--brand);box-shadow:0 0 0 3px rgba(217,116,143,.1)}
.issue-actions{display:flex;justify-content:flex-end;gap:10px;margin-top:20px}
.btn-cancel{background:transparent;color:var(--text-muted);border:1px solid var(--border);border-radius:12px;padding:11px 22px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit}
.btn-cancel:active{background:rgba(17,24,39,0.064)}
.btn-submit{background:#f43f5e;color:#fff;border:none;border-radius:12px;padding:11px 22px;font-size:14px;font-weight:800;cursor:pointer;font-family:inherit;letter-spacing:.4px}
.btn-submit:active{transform:scale(.97)}
</style>
</head><body data-role="__ROLE__">
<div class="top">
  <div class="top-brand">
    <div class="brand-mark">5&nbsp;SEC</div>
    <div class="brand-sub">Picking</div>
  </div>
  <div class="top-show" id="topShow"></div>
  <span class="mode-badge" id="modeBadge" title="This iPad is set as a picking station">📋 PICK iPAD</span>
  <a href="/?force=pack" class="role-switch-top" title="Switch to packing screen (stays logged in)" data-i18n="switchpack">📦 Switch to Packing</a>
  <button class="theme-toggle" id="langBtn" onclick="toggleLang()" title="Language" style="width:auto;padding:0 12px;font-weight:800;font-size:13px">ES</button>
  <button class="theme-toggle" id="themeToggle" title="Toggle light/dark mode">☀️</button>
  <a href="/logout" class="top-logout" data-i18n="logout">Logout</a>
</div>

<div class="page">
  <!-- STATE A: Show picker -->
  <div id="showView">
    <div class="show-prompt" data-i18n="step1">Step 1</div>
    <div class="show-h1" data-i18n="whichshow">Which show are you picking?</div>
    <div class="show-help" data-i18n="showhelp">Pick the show you'll be collecting orders for. You can switch later if you change tables.</div>
    <div class="show-list" id="showList"></div>

    <!-- Admin-only: configure this device as a permanent picking station -->
    <div class="ipad-setup" id="ipadSetup">
      <div class="ipad-setup-title">⚙️ Admin · iPad setup</div>
      <div class="ipad-setup-help">Set this iPad as a dedicated picking station. After badge login from this device, workers will land directly on this screen — no choice menu in the way.</div>
      <div class="ipad-setup-actions">
        <button class="ipad-setup-btn primary" id="setPickBtn">📋 Set as picking iPad</button>
        <button class="ipad-setup-btn" id="clearModeBtn" style="display:none">Clear setting</button>
      </div>
      <div class="ipad-setup-status" id="ipadSetupStatus"></div>
    </div>
  </div>

  <!-- STATE B: Scan ready -->
  <div id="scanView">
    <div class="scan-icon">📋</div>
    <div class="scan-title" data-i18n="readyscan">Ready to scan</div>
    <div class="scan-sub" data-i18n="aimscan">Aim the scanner at the barcode on the packing label.</div>
    <div class="scan-input-wrap">
      <input class="scan-input" id="scanInput" placeholder="Waiting for scan…" data-i18n-ph="waitscan" inputmode="none" autocomplete="off">
    </div>
    <div class="scan-status"><span class="dot"></span><span data-i18n="scannerready">Scanner ready</span></div>
    <div class="stats-row">
      <div class="session-stat"><div class="num" id="sessionCount">0</div><div class="txt" data-i18n="st_session">this session</div></div>
      <div class="session-stat brand"><div class="num" id="todayCount">0</div><div class="txt" data-i18n="st_today">today total</div></div>
      <div class="session-stat"><div class="num" id="weekCount">0</div><div class="txt" data-i18n="st_week">past 7 days</div></div>
    </div>
  </div>

  <!-- STATE C: Checklist -->
  <div id="listView">
    <div class="list-head">
      <button class="back-btn" id="backBtn" data-i18n="backscan">← Cancel — back to scan</button>
      <div class="list-buyer" id="listBuyer">—</div>
      <div class="list-meta" id="listMeta"></div>
    </div>
    <div class="progress-row">
      <div class="progress-text"><b id="pickedCount">0</b> <span data-i18n="of">of</span> <span id="totalCount">0</span> <span data-i18n="pickedw">picked</span></div>
      <div class="progress-bar"><div class="progress-fill" id="progressFill" style="width:0%"></div></div>
    </div>
    <div class="items-list" id="itemsList"></div>
  </div>
</div>

<div class="done-bar" id="doneBar">
  <button class="done-btn idle" id="doneBtn" data-i18n="tapitems">Tap items above as you pick them</button>
  <button class="issue-btn" id="issueBtn" data-i18n="reportproblem">🚧 Report a problem with this order</button>
</div>

<!-- Issue report modal -->
<div class="issue-modal" id="issueModal" style="display:none">
  <div class="issue-card">
    <h3 data-i18n="problemtitle">Problem with this order</h3>
    <div class="issue-help" data-i18n="problemhelp">Tell the manager what's wrong so they can fix it. The order moves to the "Issues" queue and you can continue picking the next one.</div>
    <div class="issue-presets" id="issuePresets">
      <button class="preset" data-r="Item missing — not on the table" data-i18n="p_missing">Item missing</button>
      <button class="preset" data-r="Item damaged" data-i18n="p_damaged">Damaged</button>
      <button class="preset" data-r="Wrong SKU on the table" data-i18n="p_wrongsku">Wrong SKU</button>
      <button class="preset" data-r="Can't find the table" data-i18n="p_cantfind">Can't find</button>
    </div>
    <textarea id="issueReason" placeholder="Or describe the problem here…" data-i18n-ph="describeproblem" rows="3"></textarea>
    <div class="issue-actions">
      <button class="btn-cancel" id="issueCancel" data-i18n="cancel">Cancel</button>
      <button class="btn-submit" id="issueSubmit" data-i18n="reportskip">Report & skip</button>
    </div>
  </div>
</div>

<!-- Cancelled alert -->
<div class="cancel-overlay" id="cancelOverlay">
  <div class="icn">🚨</div>
  <div class="ttl" data-i18n="donotpick">DO NOT PICK</div>
  <div class="sub" data-i18n="cancelledsub">This order has been cancelled by the customer.<br>Skip it and scan the next label.</div>
  <button class="ok" id="cancelOk" data-i18n="gotitscan">Got it — back to scan</button>
</div>

<div class="toast" id="toast">—</div>

<script>
var LANG=localStorage.getItem('lang')||'en';
var T={en:{
 switchpack:'📦 Switch to Packing',logout:'Logout',step1:'Step 1',whichshow:'Which show are you picking?',
 showhelp:"Pick the show you'll be collecting orders for. You can switch later if you change tables.",
 readyscan:'Ready to scan',aimscan:'Aim the scanner at the barcode on the packing label.',waitscan:'Waiting for scan…',
 scannerready:'Scanner ready',st_session:'this session',st_today:'today total',st_week:'past 7 days',
 backscan:'← Cancel — back to scan',of:'of',pickedw:'picked',tapitems:'Tap items above as you pick them',
 reportproblem:'🚧 Report a problem with this order',problemtitle:'Problem with this order',
 problemhelp:'Tell the manager what\\'s wrong so they can fix it. The order moves to the "Issues" queue and you can continue picking the next one.',
 p_missing:'Item missing',p_damaged:'Damaged',p_wrongsku:'Wrong SKU',p_cantfind:"Can't find",
 describeproblem:'Or describe the problem here…',cancel:'Cancel',reportskip:'Report & skip',
 donotpick:'DO NOT PICK',cancelledsub:'This order has been cancelled by the customer.<br>Skip it and scan the next label.',
 gotitscan:'Got it — back to scan',donebring:'✓ Done — bring to packer',moretopick:'more to pick',
 combined:'⚠️ COMBINED ORDER',shows:'SHOWS',combinedsub:'Items come from different shows — pick each TABLE SET below in order',
 tableset:'TABLE SET',giveaway:'GIVEAWAY',gotomanager:'GO TO MANAGER TO GET IT',alreadypicked:'Already picked by',
 clearcancelled:'Clear cancelled items off the table first',noshipment:'No shipment for',lookupfailed:'Lookup failed'
},es:{
 switchpack:'📦 Cambiar a Empaque',logout:'Salir',step1:'Paso 1',whichshow:'¿Qué show estás recolectando?',
 showhelp:'Elige el show del que recolectarás pedidos. Puedes cambiar después si cambias de mesa.',
 readyscan:'Listo para escanear',aimscan:'Apunta el escáner al código de barras de la etiqueta de envío.',waitscan:'Esperando escaneo…',
 scannerready:'Escáner listo',st_session:'esta sesión',st_today:'total de hoy',st_week:'últimos 7 días',
 backscan:'← Cancelar — volver a escanear',of:'de',pickedw:'recolectados',tapitems:'Toca los artículos a medida que los recolectas',
 reportproblem:'🚧 Reportar un problema con este pedido',problemtitle:'Problema con este pedido',
 problemhelp:'Dile al gerente qué está mal para que lo arregle. El pedido pasa a la cola de "Problemas" y puedes seguir con el siguiente.',
 p_missing:'Falta artículo',p_damaged:'Dañado',p_wrongsku:'SKU incorrecto',p_cantfind:'No lo encuentro',
 describeproblem:'O describe el problema aquí…',cancel:'Cancelar',reportskip:'Reportar y saltar',
 donotpick:'NO RECOLECTAR',cancelledsub:'Este pedido fue cancelado por el cliente.<br>Sáltalo y escanea la siguiente etiqueta.',
 gotitscan:'Entendido — volver a escanear',donebring:'✓ Listo — llévalo al empacador',moretopick:'por recolectar',
 combined:'⚠️ PEDIDO COMBINADO',shows:'SHOWS',combinedsub:'Los artículos son de shows distintos — recolecta cada SET DE MESAS abajo en orden',
 tableset:'SET DE MESAS',giveaway:'REGALO',gotomanager:'VE AL GERENTE POR ESTE REGALO',alreadypicked:'Ya recolectado por',
 clearcancelled:'Primero retira los artículos cancelados de la mesa',noshipment:'No hay envío para',lookupfailed:'Búsqueda fallida'
}};
function t(k){return (T[LANG]&&T[LANG][k])||T.en[k]||k}
function toggleLang(){LANG=(LANG==='en'?'es':'en');localStorage.setItem('lang',LANG);location.reload()}
function applyLang(){
 document.querySelectorAll('[data-i18n]').forEach(function(e){e.innerHTML=t(e.dataset.i18n)});
 document.querySelectorAll('[data-i18n-ph]').forEach(function(e){e.placeholder=t(e.dataset.i18nPh)});
 var lb=document.getElementById('langBtn');if(lb)lb.textContent=(LANG==='en'?'ES':'EN');
}
applyLang();
var currentShow=localStorage.getItem('pickShow')||'';
var currentDetail=null,currentItems=[],currentGiveaways=[],sessionCount=0;
var availableShows=[];

// ─── Audio feedback (Web Audio API). Mobile Safari needs a user gesture to start. ───
var audioCtx=null;
function ensureAudio(){
    if(audioCtx)return audioCtx;
    try{audioCtx=new (window.AudioContext||window.webkitAudioContext)()}catch(e){}
    return audioCtx;
}
function beep(freq,dur,type,vol){
    var a=ensureAudio();if(!a)return;
    var osc=a.createOscillator(),gain=a.createGain();
    osc.type=type||'sine';osc.frequency.value=freq;
    var v=vol||0.18;
    gain.gain.setValueAtTime(0,a.currentTime);
    gain.gain.linearRampToValueAtTime(v,a.currentTime+0.005);
    gain.gain.exponentialRampToValueAtTime(0.0001,a.currentTime+dur/1000);
    osc.connect(gain);gain.connect(a.destination);
    osc.start();osc.stop(a.currentTime+dur/1000+0.01);
}
function sndClick(){beep(1400,40,'sine',0.12)}
function sndCheck(){beep(880,80);setTimeout(function(){beep(1318,100)},90)}
function sndComplete(){beep(659,90);setTimeout(function(){beep(988,90)},90);setTimeout(function(){beep(1318,180)},180)}
function sndError(){beep(220,200,'square',0.12)}
// Unlock audio on first touch (iOS requirement)
document.body.addEventListener('touchstart',ensureAudio,{once:true,passive:true});
document.body.addEventListener('click',ensureAudio,{once:true});

// ─── Theme toggle (light/dark, persisted) ───
function setTheme(mode){
    document.documentElement.classList.toggle('theme-light',mode==='light');
    localStorage.setItem('pickTheme',mode);
    document.getElementById('themeToggle').textContent=mode==='light'?'🌙':'☀️';
}
setTheme(localStorage.getItem('pickTheme')||'dark');
document.getElementById('themeToggle').addEventListener('click',function(){
    var cur=localStorage.getItem('pickTheme')||'dark';
    setTheme(cur==='light'?'dark':'light');
});

function escapeHtml(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}

// Pull out a "Part N" tag from a product name and render it as a bold pink chip
// next to the SKU number (critical for TikTok shows where Part 1/2/3 distinguishes items).
function renderProductName(s){
    var safe=escapeHtml(s||'');
    var m=safe.match(/(Part\s*\d+)/i);
    if(!m)return safe;
    var stripped=safe.replace(/[\s·,—–-]*Part\s*\d+[\s·,—–-]*/i,' ').replace(/\s{2,}/g,' ').trim();
    return '<span class="part-tag">'+m[1].toUpperCase()+'</span>'+stripped;
}

function showToast(msg,ok){
    var t=document.getElementById('toast');
    t.textContent=msg;
    t.className='toast on'+(ok?' ok':'');
    setTimeout(function(){t.className='toast'},2200);
}

function switchState(s){
    document.getElementById('showView').classList.toggle('on',s==='show');
    document.getElementById('scanView').classList.toggle('on',s==='scan');
    document.getElementById('listView').classList.toggle('on',s==='list');
    document.getElementById('doneBar').classList.toggle('on',s==='list');
    if(s==='scan'){
        var inp=document.getElementById('scanInput');
        inp.value='';
        setTimeout(function(){inp.focus()},120);
    }
}

function renderTopShow(){
    var el=document.getElementById('topShow');
    if(!currentShow){el.innerHTML='';return}
    el.innerHTML='Show: <b>'+escapeHtml(currentShow)+'</b><a href="#" class="change-link" id="changeShowLink">Change</a>';
    document.getElementById('changeShowLink').addEventListener('click',function(e){
        e.preventDefault();
        currentShow='';
        localStorage.removeItem('pickShow');
        renderTopShow();
        loadShows();
    });
}

function loadShows(){
    fetch('/api/shows').then(function(r){
        if(!r.ok)throw new Error('HTTP '+r.status);
        return r.json();
    }).then(function(rows){
        availableShows=rows||[];
        if(currentShow){
            // Already chose one — go straight to scan
            switchState('scan');
            return;
        }
        // Render show picker
        var list=document.getElementById('showList');
        if(availableShows.length===0){
            list.innerHTML='<div class="show-empty">No active shows in the last 5 days.<br>Ask your admin to import a CSV first.</div>';
            switchState('show');
            return;
        }
        list.innerHTML=availableShows.map(function(sh){
            var platCls='pill-'+(sh.platform||'mixed');
            if(sh.platform_count>1)platCls='pill-mixed';
            var pendN=sh.pending||0;
            // Cleanup status pill — shows "🧹 X to clear" on dirty shows so the
            // picker knows up-front they need to clear the table first.
            var cleanupPill='';
            var dirty=sh.cleanup && !sh.cleanup.is_clean && sh.cleanup.groups_total>0;
            if(dirty){
                cleanupPill='<span class="pill" style="background:rgba(245,158,11,.18);color:#b45309">🧹 '+sh.cleanup.groups_pending+' to clear</span>';
            }
            return '<button class="show-card'+(dirty?' show-dirty':'')+'" data-name="'+escapeHtml(sh.name)+'" data-dirty="'+(dirty?'1':'0')+'">'+
                '<div class="name">'+escapeHtml(sh.name)+'</div>'+
                '<div class="meta">'+
                    '<span class="pill '+platCls+'">'+(sh.platform_count>1?'mixed':escapeHtml(sh.platform||'?'))+'</span>'+
                    cleanupPill+
                    '<span>'+sh.shipments+' total</span>'+
                    '<span class="pending-count">'+pendN+'<span class="lbl">to pick</span></span>'+
                '</div>'+
            '</button>';
        }).join('');
        list.querySelectorAll('.show-card').forEach(function(b){
            b.addEventListener('click',function(){
                if(b.dataset.dirty==='1'){
                    // Hard block — send to cleanup screen for this show
                    location.href='/admin/cleanup?show='+encodeURIComponent(b.dataset.name);
                    return;
                }
                currentShow=b.dataset.name;
                localStorage.setItem('pickShow',currentShow);
                renderTopShow();
                switchState('scan');
            });
        });
        switchState('show');
    }).catch(function(err){
        // Network error or permission denied — keep the user informed instead of a blank screen
        var list=document.getElementById('showList');
        if(list)list.innerHTML='<div class="show-empty">Could not load shows.<br>Error: '+(err.message||err)+'<br>Try refreshing the page.</div>';
        switchState('show');
    });
}

// USPS IMpb barcodes embed extras (service code + ZIP + ...) BEFORE the 22-digit
// tracking number. We want clean 22-digit values everywhere in the system —
// strip the prefix here so the server, the UI, and the API all see the same code.
function normalizeTracking(s){
    s=(s||'').trim();
    // 23-40 all-digit string = USPS barcode with prefix → take the last 22 digits
    if(/^\d{23,40}$/.test(s)) return s.slice(-22);
    return s;
}

// Scan input handling — the barcode scanner types into this field and hits Enter
document.getElementById('scanInput').addEventListener('keydown',function(e){
    if(e.key!=='Enter')return;
    var code=normalizeTracking(this.value);
    if(!code)return;
    this.value='';
    lookupAndOpen(code);
});
// Keep focus on the scan input so barcode reads always land there
setInterval(function(){
    if(document.getElementById('scanView').classList.contains('on')){
        var inp=document.getElementById('scanInput');
        if(document.activeElement!==inp)inp.focus();
    }
},500);

function lookupAndOpen(code){
    fetch('/api/pick/'+encodeURIComponent(code)).then(function(r){return r.json()}).then(function(d){
        // /api/pick/<id> takes shipment_id. The label barcode is likely tracking_code.
        // Fall back to the generic shipment lookup which accepts either.
        if(!d.ok){
            return fetch('/api/shipment/'+encodeURIComponent(code)).then(function(r){return r.json()}).then(function(d2){
                if(!d2.ok){sndError();showToast(t('noshipment')+' "'+code+'"');return}
                openDetail(d2.shipment.shipment_id);
            });
        }
        openDetail(d.shipment.shipment_id);
    });
}

function openDetail(sid){
    fetch('/api/pick/'+encodeURIComponent(sid)).then(function(r){return r.json()}).then(function(d){
        if(!d.ok){showToast(d.error||t('lookupfailed'));return}
        var s=d.shipment, items=d.items||[];
        // Hard cleanup gate — server tells us the show isn't clean yet.
        // Send the picker straight to the cleanup screen for that show.
        if(d.cleanup_blocked){
            sndError();
            var lbl=s.import_label||'';
            showToast(t('clearcancelled'),true);
            setTimeout(function(){location.href='/admin/cleanup?show='+encodeURIComponent(lbl)},900);
            return;
        }
        if(s.status==='cancelled'){
            sndError();
            document.getElementById('cancelOverlay').classList.add('on');
            return;
        }
        // Server is the source of truth: blocks picked / packed / shipped orders.
        if(d.already_picked || s.status==='picked'){
            sndError();
            var who=d.picked_by||s.picked_by||'someone';
            var when=(d.picked_at||s.picked_at||'').replace('T',' ').slice(0,16);
            showToast(t('alreadypicked')+' '+who+(when?(' · '+when):''),true);
            return;
        }
        // The scanned tracking number uniquely identifies this exact order in the
        // database — no guessing needed. We pick whatever the label in hand points
        // to, regardless of which show was selected. (Show attribution can be wrong
        // for TikTok, whose one CSV mixes many shows; the tracking never is.)
        currentDetail=sid;
        currentItems=items;
        currentGiveaways=(d.giveaways||[]).map(function(g){return {id:g.id,prize_name:g.prize_name,winner_username:g.winner_username,brand:g.brand,added:(g.attach_status==='added')}});
        document.getElementById('listBuyer').textContent=s.buyer_name||s.buyer_username||'Customer';
        var meta='<span class="pill pill-id">'+escapeHtml(s.shipment_id)+'</span>';
        if(s.tracking_code)meta+='<span class="pill pill-track">'+escapeHtml(s.tracking_code)+'</span>';
        if(d.giveaways&&d.giveaways.length){
            meta+='<span class="pill" style="background:rgba(52,211,153,.2);color:#059669;font-weight:800;display:block;width:100%;margin-top:8px;padding:10px 12px;font-size:14px">🎁 '+t('giveaway')+': '+d.giveaways.map(function(g){return escapeHtml(g.prize_name)+(g.winner_username?' (@'+escapeHtml(g.winner_username)+')':'')}).join(', ')+' — '+t('gotomanager')+'</span>';
        }
        document.getElementById('listMeta').innerHTML=meta;
        renderItems();
        switchState('list');
        window.scrollTo(0,0);
    });
}

// Parse the show (date+name), Part number, and SKU number from an item so the
// pick list follows the warehouse flow: show by date → Part 1→2→3 → SKU ascending.
function _showOf(name){
    name=name||'';
    var base=name.replace(/\s*Part\s*\d+.*$/i,'').trim();
    var dm=name.match(/(\d{1,2})\/(\d{1,2})\/(\d{2,4})/);
    var dnum=dm?(parseInt(dm[3].length===2?'20'+dm[3]:dm[3])*10000+parseInt(dm[1])*100+parseInt(dm[2])):99999999;
    return {base:base||'Show', date:dnum};
}
function _partOf(name){var m=(name||'').match(/Part\s*(\d+)/i);return m?parseInt(m[1]):9999}
function _skuNum(s){var m=(s||'').toString().match(/\d+/);return m?parseInt(m[0]):999999}
function renderItems(){
    var active=currentItems.filter(function(i){return !i.cancelled});
    var gvs=currentGiveaways||[];
    var gvAdded=gvs.filter(function(g){return g.added}).length;
    var pickedN=active.filter(function(i){return i.picked}).length + gvAdded;
    var total=active.length + gvs.length;
    document.getElementById('pickedCount').textContent=pickedN;
    document.getElementById('totalCount').textContent=total;
    document.getElementById('progressFill').style.width=(total?100*pickedN/total:0)+'%';
    var arr=currentItems.map(function(it){
        var si=_showOf(it.product_name);
        return {it:it,base:si.base,date:si.date,part:_partOf(it.product_name),sku:_skuNum(it.sku)};
    });
    arr.sort(function(a,b){return (a.date-b.date)||(a.part-b.part)||(a.sku-b.sku)||0});
    var shows=[];arr.forEach(function(x){if(shows.indexOf(x.base)<0)shows.push(x.base)});
    var multi=shows.length>1, lastBase=null, setIdx=0, html='';
    if(multi){
        html+='<div style="margin-bottom:12px;padding:13px 14px;border-radius:12px;background:rgba(251,191,36,.18);border:2px solid rgba(251,191,36,.6);color:#b45309;font-weight:900;font-size:15px;text-align:center;letter-spacing:.3px">'+t('combined')+' · '+shows.length+' '+t('shows')+'<div style="font-weight:600;font-size:12px;color:var(--text-muted);margin-top:4px">'+t('combinedsub')+'</div></div>';
    }
    arr.forEach(function(x){
        if(multi && x.base!==lastBase){
            setIdx++; lastBase=x.base;
            html+='<div style="margin:16px 0 8px;padding:9px 13px;border-radius:10px;background:rgba(217,116,143,.16);border:1px solid rgba(217,116,143,.35);color:var(--brand);font-weight:800;font-size:14px;display:flex;justify-content:space-between;gap:8px"><span>📋 '+t('tableset')+' '+setIdx+'</span><span style="font-weight:600;color:var(--text-muted)">'+escapeHtml(x.base)+'</span></div>';
        }
        var it=x.it, cls='pi'+(it.cancelled?' cancelled':(it.picked?' done':''));
        html+='<div class="'+cls+'" data-id="'+it.id+'">'+
            '<div class="pi-box"></div>'+
            '<div class="pi-info">'+
                '<div class="pi-sku">'+escapeHtml(it.sku||'?')+'</div>'+
                '<div class="pi-name">'+renderProductName(it.product_name||'')+(it.cancelled?' · CANCELLED':'')+'</div>'+
            '</div>'+
            '<div class="pi-qty">×'+(it.quantity||1)+'</div>'+
        '</div>';
    });
    // Attached giveaways — checked off like any other product before the order is done.
    if(gvs.length){
        html+='<div style="margin:16px 0 8px;padding:9px 13px;border-radius:10px;background:rgba(16,185,129,.14);border:1px solid rgba(16,185,129,.4);color:#059669;font-weight:800;font-size:14px">🎁 '+t('giveaway')+' — '+t('gotomanager')+'</div>';
        gvs.forEach(function(g){
            html+='<div class="pi gv'+(g.added?' done':'')+'" data-gid="'+g.id+'">'+
                '<div class="pi-box"></div>'+
                '<div class="pi-info">'+
                    '<div class="pi-sku">🎁</div>'+
                    '<div class="pi-name"><b>'+t('giveaway')+'</b> · '+escapeHtml(g.prize_name||'')+(g.winner_username?' · @'+escapeHtml(g.winner_username):'')+'</div>'+
                '</div>'+
                '<div class="pi-qty">×1</div>'+
            '</div>';
        });
    }
    document.getElementById('itemsList').innerHTML=html;
    document.getElementById('itemsList').querySelectorAll('.pi').forEach(function(el){
        if(el.classList.contains('cancelled'))return;
        if(el.classList.contains('gv')){el.addEventListener('click',function(){toggleGiveaway(parseInt(el.dataset.gid))});return;}
        el.addEventListener('click',function(){toggleItem(parseInt(el.dataset.id))});
    });
    var btn=document.getElementById('doneBtn');
    if(pickedN===total && total>0){
        btn.classList.remove('idle');
        btn.textContent=t('donebring');
    } else {
        btn.classList.add('idle');
        btn.textContent=(total-pickedN)+' '+t('moretopick');
    }
}

function toggleItem(itemId){
    fetch('/api/pick/item/'+itemId+'/toggle',{method:'POST'}).then(function(r){return r.json()}).then(function(d){
        if(!d.ok){sndError();showToast(d.error||'Error');return}
        var it=currentItems.find(function(x){return x.id===itemId});
        if(it)it.picked=d.picked;
        if(d.picked)sndCheck();else sndClick();
        renderItems();
    });
}
function toggleGiveaway(gid){
    var g=(currentGiveaways||[]).find(function(x){return x.id===gid});
    if(!g)return;
    var newAdded=!g.added;
    g.added=newAdded;                 // optimistic
    if(newAdded)sndCheck();else sndClick();
    renderItems();
    fetch('/api/giveaway/'+gid+'/mark-added',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({added:newAdded})})
    .then(function(r){return r.json()}).then(function(d){
        if(!d.ok){g.added=!newAdded;renderItems();sndError();showToast(d.error||'Error')}
    }).catch(function(){g.added=!newAdded;renderItems();sndError()});
}

function refreshMyStats(){
    fetch('/api/pick/my-stats').then(function(r){return r.json()}).then(function(d){
        document.getElementById('todayCount').textContent=d.today||0;
        document.getElementById('weekCount').textContent=d.week||0;
    });
}

function completePick(){
    if(!currentDetail)return;
    var active=currentItems.filter(function(i){return !i.cancelled});
    var pickedN=active.filter(function(i){return i.picked}).length;
    if(pickedN<active.length){
        if(!confirm('Only '+pickedN+' of '+active.length+' items are checked. Mark this order picked anyway?'))return;
    }
    fetch('/api/pick/complete/'+encodeURIComponent(currentDetail),{method:'POST'}).then(function(r){return r.json()}).then(function(d){
        if(!d.ok){sndError();showToast(d.error||'Error');return}
        sndComplete();
        sessionCount++;
        document.getElementById('sessionCount').textContent=sessionCount;
        currentDetail=null;currentItems=[];
        showToast('✓ Picked — bring to packer',true);
        switchState('scan');
        refreshMyStats();
    });
}

document.getElementById('backBtn').addEventListener('click',function(){
    currentDetail=null;currentItems=[];
    switchState('scan');
});
document.getElementById('doneBtn').addEventListener('click',completePick);

// ─── Issue reporting ───
var issueModal=document.getElementById('issueModal');
var issueReasonText='';
function openIssue(){
    issueReasonText='';
    document.getElementById('issueReason').value='';
    document.querySelectorAll('.issue-presets .preset').forEach(function(b){b.classList.remove('active')});
    issueModal.style.display='flex';
    setTimeout(function(){document.getElementById('issueReason').focus()},80);
}
function closeIssue(){issueModal.style.display='none'}
document.getElementById('issueBtn').addEventListener('click',openIssue);
document.getElementById('issueCancel').addEventListener('click',closeIssue);
document.querySelectorAll('.issue-presets .preset').forEach(function(b){
    b.addEventListener('click',function(){
        document.querySelectorAll('.issue-presets .preset').forEach(function(x){x.classList.remove('active')});
        b.classList.add('active');
        issueReasonText=b.dataset.r;
        document.getElementById('issueReason').value=b.dataset.r;
    });
});
document.getElementById('issueSubmit').addEventListener('click',function(){
    if(!currentDetail)return;
    var reason=document.getElementById('issueReason').value.trim()||issueReasonText;
    if(!reason){showToast('Pick a reason or type one');sndError();return}
    fetch('/api/pick/issue/'+encodeURIComponent(currentDetail),{
        method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({reason:reason})
    }).then(function(r){return r.json()}).then(function(d){
        if(!d.ok){sndError();showToast(d.error||'Failed');return}
        sndClick();
        closeIssue();
        currentDetail=null;currentItems=[];
        showToast('🚧 Issue reported — manager will handle it',true);
        switchState('scan');
        refreshMyStats();
    });
});
document.getElementById('cancelOk').addEventListener('click',function(){
    document.getElementById('cancelOverlay').classList.remove('on');
    switchState('scan');
});

// Admin-only: check + manage machine_mode cookie that controls iPad behaviour.
// When mode='pick', any badge login on this device routes straight to /pick.
function refreshMachineMode(){
    var isAdmin=document.body.dataset.role==='admin';
    fetch('/api/machine-mode').then(function(r){return r.json()}).then(function(d){
        var mode=d.mode||'';
        var badge=document.getElementById('modeBadge');
        badge.classList.toggle('on', mode==='pick');
        if(!isAdmin)return;
        var setup=document.getElementById('ipadSetup');
        setup.classList.add('on');  // admins see the setup panel any time they hit the show picker
        var status=document.getElementById('ipadSetupStatus');
        var clearBtn=document.getElementById('clearModeBtn');
        var setBtn=document.getElementById('setPickBtn');
        if(mode==='pick'){
            status.textContent='✓ This iPad is set as a picking station — workers go straight to /pick after badge login.';
            clearBtn.style.display='inline-block';
            setBtn.textContent='Already configured';
            setBtn.style.opacity='.5';
        } else {
            status.textContent='Not configured yet. After tapping, any worker who scans their badge from this device goes straight to picking.';
            clearBtn.style.display='none';
            setBtn.textContent='📋 Set as picking iPad';
            setBtn.style.opacity='1';
        }
    });
}
document.getElementById('setPickBtn').addEventListener('click',function(){
    fetch('/api/machine-mode',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:'pick'})})
        .then(function(r){return r.json()}).then(function(d){
            if(d.ok){showToast('✓ iPad set for picking',true);refreshMachineMode()}
            else showToast(d.error||'Failed');
        });
});
document.getElementById('clearModeBtn').addEventListener('click',function(){
    if(!confirm('Clear iPad picking-station setting?'))return;
    fetch('/api/machine-mode',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:''})})
        .then(function(r){return r.json()}).then(function(d){
            if(d.ok){showToast('Cleared',true);refreshMachineMode()}
        });
});
document.getElementById('modeBadge').addEventListener('click',function(){
    if(document.body.dataset.role==='admin'){
        currentShow='';
        localStorage.removeItem('pickShow');
        renderTopShow();
        loadShows();
    }
});

renderTopShow();
loadShows();
refreshMachineMode();
refreshMyStats();
// Periodically refresh personal stats — picks made on other devices show up too
setInterval(refreshMyStats,30000);
</script>
</body></html>'''


# ══════════════════════════════════════════════════════════
# PICKING ISSUES — admin queue for shipments flagged by pickers
# ══════════════════════════════════════════════════════════

ISSUES_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Picking issues — __BRANDMARK__</title>
__NAVBAR_CSS__
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'DM Sans',-apple-system,sans-serif;background:#ffffff;color:var(--text);min-height:100vh;padding-bottom:120px;-webkit-font-smoothing:antialiased}
.wrap{max-width:1100px;margin:0 auto;padding:40px 28px 0}
.page-head{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;margin-bottom:6px;flex-wrap:wrap}
.page-title{font-size:32px;font-weight:900;color:#141b26;letter-spacing:-.5px;line-height:1.05}
.page-sub{color:var(--text-muted);margin-top:8px;font-size:14px;margin-bottom:26px}
.refresh-btn{background:var(--surface);border:1px solid var(--border);color:var(--text-muted);border-radius:10px;padding:9px 16px;font-size:13px;font-weight:700;cursor:pointer;font-family:inherit}
.refresh-btn:hover{color:var(--text);background:rgba(17,24,39,0.096)}

.count-pill{display:inline-flex;align-items:center;gap:8px;background:rgba(244,63,94,.1);border:1px solid rgba(244,63,94,.25);color:#e11d48;padding:8px 16px;border-radius:20px;font-size:13px;font-weight:700;letter-spacing:.4px;text-transform:uppercase}
.count-pill .dot{width:8px;height:8px;border-radius:50%;background:#e11d48;animation:pulse 1.5s ease infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}

/* Issue cards */
.issues-list{display:flex;flex-direction:column;gap:14px}
.issue{background:var(--surface);border:1px solid rgba(244,63,94,.22);border-left:4px solid #e11d48;border-radius:16px;padding:20px 22px}
.issue-head{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;margin-bottom:12px;flex-wrap:wrap}
.issue-buyer{font-size:20px;font-weight:800;color:#141b26;line-height:1.2;margin-bottom:4px}
.issue-meta{display:flex;flex-wrap:wrap;gap:6px;font-size:12px;align-items:center}
.issue-meta .pill{padding:3px 10px;border-radius:7px;font-weight:700;font-size:11px;letter-spacing:.3px}
.pill-show{background:rgba(217,116,143,.12);color:#d9748f}
.pill-id{background:rgba(17,24,39,0.08);color:var(--text-muted);font-family:'SF Mono',Menlo,monospace}
.pill-track{background:rgba(99,102,241,.14);color:#4f46e5;font-family:'SF Mono',Menlo,monospace}
.pill-platform{background:rgba(148,163,184,.08);color:#64748b;text-transform:uppercase}

.reason-box{background:rgba(244,63,94,.06);border:1px solid rgba(244,63,94,.15);border-radius:10px;padding:14px 18px;margin-bottom:14px;display:flex;gap:12px;align-items:flex-start}
.reason-box .icon{font-size:22px;flex-shrink:0;line-height:1}
.reason-box .txt{flex:1;font-size:14px;color:var(--text);line-height:1.5}
.reason-box .txt b{color:#e11d48;font-weight:700}

.items-strip{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px}
.item-tag{display:inline-flex;align-items:center;gap:8px;background:rgba(17,24,39,0.064);border:1px solid var(--border);border-radius:8px;padding:5px 10px;font-size:12px}
.item-tag .sku{font-family:'SF Mono',Menlo,monospace;color:#d9748f;font-weight:700;background:rgba(217,116,143,.1);padding:2px 6px;border-radius:5px;font-size:11px}
.item-tag .name{color:var(--text-muted);max-width:180px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.item-tag .qty{color:var(--text-dim);font-weight:700}
.item-tag.cancelled{opacity:.5;text-decoration:line-through}

.issue-actions{display:flex;gap:10px;flex-wrap:wrap;padding-top:14px;border-top:1px solid var(--border)}
.action-retry{background:rgba(16,185,129,.14);color:#059669;border:1px solid rgba(16,185,129,.3);border-radius:11px;padding:11px 22px;font-size:14px;font-weight:800;cursor:pointer;font-family:inherit;flex:1;min-width:200px;display:flex;align-items:center;justify-content:center;gap:8px}
.action-retry:hover{background:rgba(16,185,129,.22)}
.action-retry:active{transform:scale(.98)}
.action-cancel{background:rgba(244,63,94,.1);color:#e11d48;border:1px solid rgba(244,63,94,.22);border-radius:11px;padding:11px 22px;font-size:14px;font-weight:800;cursor:pointer;font-family:inherit;flex:1;min-width:200px;display:flex;align-items:center;justify-content:center;gap:8px}
.action-cancel:hover{background:rgba(244,63,94,.18)}
.action-cancel:active{transform:scale(.98)}

.empty{text-align:center;padding:80px 20px;background:var(--surface);border:1px dashed var(--border);border-radius:18px}
.empty-icon{font-size:64px;margin-bottom:14px;opacity:.6}
.empty-title{font-size:20px;font-weight:800;color:#059669;margin-bottom:6px}
.empty-sub{font-size:14px;color:var(--text-muted)}
.loading{text-align:center;padding:40px;color:var(--text-dim);font-size:14px}

/* Resolution toast */
.toast{position:fixed;top:80px;left:50%;transform:translateX(-50%);background:rgba(16,185,129,.95);color:#fff;padding:14px 26px;border-radius:12px;font-size:15px;font-weight:700;box-shadow:0 10px 30px rgba(16,185,129,.3);z-index:300;display:none}
.toast.on{display:block}
.toast.err{background:rgba(244,63,94,.95);box-shadow:0 10px 30px rgba(244,63,94,.3)}
</style>
</head><body data-role="__ROLE__">
__NAVBAR__
<div class="wrap">
  <div class="page-head">
    <div>
      <div class="page-title">🚧 Picking issues</div>
    </div>
    <button class="refresh-btn" id="refreshBtn">↻ Refresh</button>
  </div>
  <div class="page-sub">
    Orders flagged by pickers because something was wrong on the table.
    Resolve by sending back to the queue (item is now available) or cancelling.
  </div>
  <div id="countWrap" style="margin-bottom:24px"></div>
  <div id="list"></div>
</div>

<div class="toast" id="toast">—</div>

<script>
function escapeHtml(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
function showToast(msg,err){
    var t=document.getElementById('toast');
    t.textContent=msg;t.className='toast on'+(err?' err':'');
    setTimeout(function(){t.className='toast'},2400);
}

function load(){
    document.getElementById('list').innerHTML='<div class="loading">Loading issues…</div>';
    fetch('/api/issues').then(function(r){return r.json()}).then(function(rows){
        var count=rows.length;
        document.getElementById('countWrap').innerHTML=count>0
            ? '<span class="count-pill"><span class="dot"></span>'+count+' open '+(count===1?'issue':'issues')+'</span>'
            : '';
        var list=document.getElementById('list');
        if(count===0){
            list.innerHTML='<div class="empty"><div class="empty-icon">✓</div><div class="empty-title">All clear</div><div class="empty-sub">No picking issues right now. Pickers can keep going.</div></div>';
            return;
        }
        list.innerHTML='<div class="issues-list">'+rows.map(function(s){
            var platCls='pill-platform';
            var itemsHtml=(s.items||[]).map(function(it){
                var cls='item-tag'+(it.cancelled?' cancelled':'');
                return '<span class="'+cls+'"><span class="sku">'+escapeHtml(it.sku||'?')+'</span><span class="name">'+escapeHtml(it.product_name||'')+'</span><span class="qty">×'+it.quantity+'</span></span>';
            }).join('');
            return '<div class="issue" data-sid="'+escapeHtml(s.shipment_id)+'">'+
                '<div class="issue-head">'+
                    '<div>'+
                        '<div class="issue-buyer">'+escapeHtml(s.buyer_name||s.buyer_username||'(unknown buyer)')+'</div>'+
                        '<div class="issue-meta">'+
                            (s.import_label?'<span class="pill pill-show">'+escapeHtml(s.import_label)+'</span>':'')+
                            (s.platform?'<span class="pill '+platCls+'">'+escapeHtml(s.platform)+'</span>':'')+
                            '<span class="pill pill-id">'+escapeHtml(s.shipment_id)+'</span>'+
                            (s.tracking_code?'<span class="pill pill-track">'+escapeHtml(s.tracking_code)+'</span>':'')+
                        '</div>'+
                    '</div>'+
                '</div>'+
                '<div class="reason-box">'+
                    '<div class="icon">🚧</div>'+
                    '<div class="txt"><b>Reported issue:</b><br>'+escapeHtml(s.flag_reason||'(no reason given)')+'</div>'+
                '</div>'+
                (itemsHtml?'<div class="items-strip">'+itemsHtml+'</div>':'')+
                '<div class="issue-actions">'+
                    '<button class="action-retry" data-act="retry">↻ Resolved — send back to picking</button>'+
                    '<button class="action-cancel" data-act="cancel">✕ Cancel order</button>'+
                '</div>'+
            '</div>';
        }).join('')+'</div>';
        // Wire buttons
        list.querySelectorAll('.issue button').forEach(function(btn){
            btn.addEventListener('click',function(){
                var card=btn.closest('.issue');
                var sid=card.dataset.sid;
                var act=btn.dataset.act;
                var msg=act==='retry'
                    ? 'Send this order back to the pick queue?'
                    : 'Cancel this order permanently?';
                if(!confirm(msg))return;
                btn.disabled=true;btn.textContent='Working…';
                fetch('/api/pick/resolve/'+encodeURIComponent(sid),{
                    method:'POST',headers:{'Content-Type':'application/json'},
                    body:JSON.stringify({action:act})
                }).then(function(r){return r.json()}).then(function(d){
                    if(d.ok){
                        showToast(act==='retry'?'✓ Back in pick queue':'Cancelled');
                        load();
                    } else {
                        showToast(d.error||'Failed',true);
                        btn.disabled=false;
                        btn.textContent=act==='retry'?'↻ Resolved — send back to picking':'✕ Cancel order';
                    }
                });
            });
        });
    });
}

document.getElementById('refreshBtn').addEventListener('click',load);
load();
// Auto-refresh every 30s so a manager who leaves the page open sees new issues as they come in
setInterval(load,30000);
</script>
</body></html>'''


# ══════════════════════════════════════════════════════════
# TABLE CLEANUP — pre-pick cancellation removal
# Manager + workers see this. One tap per (SKU, Part) group as
# inventory is pulled off the warehouse table. Hard-blocks /pick
# until the show hits 100% clean.
# ══════════════════════════════════════════════════════════

CLEANUP_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Table Cleanup — __BRANDMARK__</title>
__NAVBAR_CSS__
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'DM Sans',-apple-system,sans-serif;background:#ffffff;color:var(--text);min-height:100vh;padding-bottom:120px;-webkit-font-smoothing:antialiased}
.wrap{max-width:1100px;margin:0 auto;padding:40px 28px 0}
.page-head{margin-bottom:14px}
.page-title{font-size:32px;font-weight:900;color:#141b26;letter-spacing:-.5px;line-height:1.05}
.page-sub{color:var(--text-muted);margin-top:6px;font-size:14px}

/* Show picker */
.shows-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px;margin-bottom:34px}
.show-card{background:var(--surface);border:2px solid var(--border);border-radius:18px;padding:22px;cursor:pointer;text-align:left;color:inherit;font-family:inherit;transition:all .15s;display:block;width:100%}
.show-card:hover{border-color:var(--brand);transform:translateY(-2px)}
.show-card.dirty{border-color:rgba(245,158,11,.4);background:rgba(245,158,11,.05)}
.show-card.clean{border-color:rgba(16,185,129,.35);background:rgba(16,185,129,.04)}
.show-card .name{font-size:20px;font-weight:800;color:#141b26;margin-bottom:8px;line-height:1.2}
.show-card .meta{display:flex;gap:10px;align-items:center;font-size:12px;color:var(--text-muted);margin-bottom:12px}
.show-card .pill{font-size:10px;font-weight:800;letter-spacing:.5px;text-transform:uppercase;padding:3px 9px;border-radius:6px}
.show-card .pill-clean{background:rgba(16,185,129,.18);color:#059669}
.show-card .pill-dirty{background:rgba(245,158,11,.18);color:#b45309}
.show-card .pill-empty{background:rgba(148,163,184,.18);color:#64748b}
.show-card .prog{display:flex;align-items:center;gap:12px}
.show-card .prog-bar{flex:1;height:8px;background:rgba(17,24,39,0.096);border-radius:4px;overflow:hidden}
.show-card .prog-fill{height:100%;background:linear-gradient(90deg,#10b981,#059669);transition:width .3s}
.show-card.dirty .prog-fill{background:linear-gradient(90deg,#b45309,#b45309)}
.show-card .prog-txt{font-size:13px;font-weight:800;color:var(--text);font-feature-settings:'tnum';white-space:nowrap}

/* Detail view (single show, group list) */
.detail{display:none}
.detail.on{display:block}
.detail-head{display:flex;justify-content:space-between;align-items:flex-end;gap:18px;margin-bottom:18px;flex-wrap:wrap}
.back-btn{background:var(--surface);border:1px solid var(--border);color:var(--text-muted);font-size:14px;font-weight:700;padding:10px 18px;border-radius:12px;cursor:pointer;font-family:inherit;text-decoration:none;display:inline-flex;align-items:center;gap:6px}
.back-btn:hover{color:var(--text);border-color:var(--border-strong)}
.detail-title{font-size:26px;font-weight:900;color:#141b26;letter-spacing:-.3px}
.detail-help{font-size:13px;color:var(--text-muted);margin-top:4px}

/* Big progress bar */
.big-prog{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:20px 24px;margin-bottom:18px}
.big-prog-row{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}
.big-prog-count{font-size:18px;font-weight:800;color:var(--text)}
.big-prog-count b{font-size:26px;color:var(--brand);font-feature-settings:'tnum'}
.big-prog-status{font-size:13px;font-weight:800;letter-spacing:.5px;text-transform:uppercase;padding:5px 12px;border-radius:8px}
.big-prog-status.dirty{background:rgba(245,158,11,.16);color:#b45309}
.big-prog-status.clean{background:rgba(16,185,129,.16);color:#059669}
.big-prog-bar{height:14px;background:rgba(17,24,39,0.096);border-radius:7px;overflow:hidden}
.big-prog-fill{height:100%;background:linear-gradient(90deg,#b45309,#b45309);transition:width .35s ease;border-radius:7px}
.big-prog-fill.done{background:linear-gradient(90deg,#10b981,#059669)}

/* Clean banner */
.clean-banner{background:rgba(16,185,129,.1);border:1px solid rgba(16,185,129,.35);border-radius:16px;padding:18px 22px;margin-bottom:18px;display:none;align-items:center;gap:14px}
.clean-banner.on{display:flex}
.clean-banner .icn{font-size:34px}
.clean-banner .txt{font-size:16px;color:#059669;font-weight:800;letter-spacing:.3px}
.clean-banner .txt b{color:#6ee7b7}

/* Group rows — the actual checklist */
.groups{display:flex;flex-direction:column;gap:10px}
.grp{display:grid;grid-template-columns:60px auto 1fr auto auto;gap:18px;align-items:center;background:var(--surface);border:2px solid var(--border);border-radius:16px;padding:18px 22px;cursor:pointer;transition:all .12s;user-select:none}
.grp:hover{border-color:rgba(217,116,143,.3)}
.grp:active{transform:scale(.995)}
.grp.done{background:rgba(16,185,129,.05);border-color:rgba(16,185,129,.22);opacity:.7}
.grp.done .g-name-txt,.grp.done .g-sku{text-decoration:line-through;text-decoration-color:rgba(255,255,255,.4)}
.g-box{width:42px;height:42px;border-radius:50%;border:4px solid rgba(17,24,39,0.16);display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:900;color:transparent;flex-shrink:0;transition:all .15s}
.grp.done .g-box{background:#10b981;border-color:#10b981;color:#ffffff}
.grp.done .g-box::before{content:'✓'}
.g-sku{font-family:'SF Mono',Menlo,monospace;font-size:30px;font-weight:900;color:var(--brand);background:rgba(217,116,143,.14);padding:8px 16px;border-radius:12px;min-width:80px;text-align:center;letter-spacing:.5px;line-height:1}
.g-info{min-width:0}
.g-name{display:flex;align-items:center;gap:14px;min-width:0}
.g-name-txt{font-size:15px;color:var(--text);font-weight:600;line-height:1.3;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}
.g-part-wrap{flex:none;text-align:center}
.g-part-big{font-family:'SF Mono',Menlo,monospace;font-size:30px;font-weight:900;color:#fff;background:var(--brand);padding:5px 16px;border-radius:12px;min-width:56px;text-align:center;letter-spacing:.5px;line-height:1;box-shadow:0 2px 6px rgba(217,116,143,.35)}
.g-part-lbl{font-size:9px;font-weight:900;letter-spacing:.7px;color:var(--text-dim);text-transform:uppercase;margin-top:3px}
.grp.done .g-part-big{opacity:.45;box-shadow:none}
.g-meta{font-size:11px;color:var(--text-dim);margin-top:4px;letter-spacing:.4px}
.g-meta b{color:var(--text-muted);font-weight:700}
.g-qty{font-size:34px;font-weight:900;color:#141b26;font-feature-settings:'tnum';line-height:1}
.g-qty-lbl{font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.6px;font-weight:800;margin-top:3px;text-align:center}
.g-stamp{font-size:11px;color:#059669;font-weight:700;text-align:right;line-height:1.4;white-space:nowrap;display:none}
.grp.done .g-stamp{display:block}

.empty{text-align:center;padding:80px 20px;color:var(--text-dim);background:var(--surface);border:1px dashed var(--border);border-radius:14px}
.empty .icn{font-size:64px;margin-bottom:12px;opacity:.55}
.empty .ttl{font-size:18px;font-weight:800;color:var(--text-muted);margin-bottom:6px}

.toast{position:fixed;top:80px;left:50%;transform:translateX(-50%);background:rgba(16,185,129,.95);color:#fff;padding:14px 26px;border-radius:12px;font-size:14px;font-weight:700;z-index:200;display:none;box-shadow:0 10px 30px rgba(0,0,0,.4)}
.toast.on{display:block}
.toast.err{background:rgba(244,63,94,.95)}
</style>
</head><body data-role="__ROLE__">
__NAVBAR__
<div class="wrap">

  <!-- VIEW A: pick a show -->
  <div id="listView">
    <div class="page-head">
      <div class="page-title">🧹 Table Cleanup</div>
      <div class="page-sub">Pull cancelled inventory off the warehouse table before picking starts. Pick a show below to see what needs to come off.</div>
    </div>
    <div id="showsGrid" class="shows-grid"></div>
    <div id="emptyShows"></div>
  </div>

  <!-- VIEW B: single show, list of groups to clear -->
  <div id="detailView" class="detail">
    <div class="detail-head">
      <div>
        <a href="#" id="backLink" class="back-btn">← All shows</a>
        <div class="detail-title" id="detailTitle" style="margin-top:10px"></div>
        <div class="detail-help">One row per <b>SKU + Part</b>. Tap a row when those items are off the table. Pickers can start as soon as the bar hits 100%.</div>
      </div>
    </div>

    <div class="big-prog">
      <div class="big-prog-row">
        <div class="big-prog-count"><b id="bpDone">0</b> / <b id="bpTotal">0</b> groups cleared</div>
        <div class="big-prog-status dirty" id="bpStatus">Not clean</div>
      </div>
      <div class="big-prog-bar"><div class="big-prog-fill" id="bpFill" style="width:0%"></div></div>
    </div>

    <div class="clean-banner" id="cleanBanner">
      <div class="icn">✅</div>
      <div class="txt">Table is clean. <b>Pickers can start picking this show.</b></div>
    </div>

    <div id="groupsList" class="groups"></div>
  </div>

</div>
<div class="toast" id="toast">—</div>

<script>
var currentLabel=null;
var role='__ROLE__';
var preLabel=new URLSearchParams(location.search).get('show');

function esc(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function fmtPart(name){var safe=esc(name||'');var m=safe.match(/(Part\\s*\\d+)/i);if(!m)return safe;var stripped=safe.replace(/[\\s·,—–-]*Part\\s*\\d+[\\s·,—–-]*/i,' ').replace(/\\s{2,}/g,' ').trim();return '<span class="part-tag">'+m[1].toUpperCase()+'</span>'+stripped}
// Split a product name into {part, base}. Handles "…Part 2" and a bare trailing
// number ("LUXURY PERFUMES AND BEAUTY 2" → part "2"). Base must contain a letter.
function splitPart(name){
  var raw=String(name||'').trim();
  var m=raw.match(/\\bPart\\s*(\\d+)\\b/i);
  if(m){var base=raw.replace(/[\\s·,—–-]*Part\\s*\\d+[\\s·,—–-]*/i,' ').replace(/\\s{2,}/g,' ').trim();return {part:m[1],base:base};}
  var t=raw.match(/^(.*[A-Za-z].*?)[\\s·,—–-]+(\\d+)\\s*$/);
  if(t){return {part:t[2],base:t[1].trim()};}
  return {part:'',base:raw};
}
function nameCell(name){
  var s=splitPart(name);
  var badge=s.part?('<div class="g-part-wrap"><div class="g-part-big">'+esc(s.part)+'</div><div class="g-part-lbl">Part</div></div>'):'';
  return badge+'<span class="g-name-txt">'+esc(s.base)+'</span>';
}
function toast(m,err){var t=document.getElementById('toast');t.textContent=m;t.className='toast on'+(err?' err':'');setTimeout(function(){t.className='toast'},2200)}

function loadShows(){
    fetch('/api/cleanup/shows').then(function(r){return r.json()}).then(function(shows){
        var grid=document.getElementById('showsGrid');
        var empty=document.getElementById('emptyShows');
        if(!shows||shows.length===0){
            grid.innerHTML='';
            empty.innerHTML='<div class="empty"><div class="icn">📦</div><div class="ttl">No active shows in the last 5 days</div><div>Import a TikTok or Whatnot CSV to get started.</div></div>';
            return;
        }
        empty.innerHTML='';
        grid.innerHTML=shows.map(function(s){
            var pct=s.total_groups>0?Math.round(100*s.groups_done/s.total_groups):100;
            var cls=s.total_groups===0?'show-card':(s.is_clean?'show-card clean':'show-card dirty');
            var pill=s.total_groups===0?'<span class="pill pill-empty">No cancellations</span>':(s.is_clean?'<span class="pill pill-clean">✓ Clean</span>':'<span class="pill pill-dirty">⚠ '+s.groups_pending+' to clear</span>');
            var platform=s.platform?'<span>· '+esc(s.platform)+'</span>':'';
            return '<button class="'+cls+'" data-label="'+esc(s.label)+'">'+
                '<div class="name">'+esc(s.label)+'</div>'+
                '<div class="meta">'+pill+platform+'<span>· '+s.shipments+' shipments</span></div>'+
                '<div class="prog"><div class="prog-bar"><div class="prog-fill" style="width:'+pct+'%"></div></div><div class="prog-txt">'+s.groups_done+'/'+s.total_groups+'</div></div>'+
            '</button>';
        }).join('');
        grid.querySelectorAll('.show-card').forEach(function(el){
            el.addEventListener('click',function(){openShow(el.dataset.label)});
        });
        // Deep-link via ?show=NAME — pickers get redirected here from /pick.
        if(preLabel){var match=shows.find(function(x){return x.label===preLabel});if(match){openShow(preLabel);preLabel=null}}
    });
}

function openShow(label){
    currentLabel=label;
    document.getElementById('listView').style.display='none';
    document.getElementById('detailView').classList.add('on');
    document.getElementById('detailTitle').textContent=label;
    loadDetail();
}

function loadDetail(){
    if(!currentLabel)return;
    fetch('/api/cleanup/'+encodeURIComponent(currentLabel)).then(function(r){return r.json()}).then(function(d){
        if(!d.ok){toast('Failed to load',true);return}
        renderDetail(d);
    });
}

function renderDetail(d){
    var groups=d.groups||[];
    document.getElementById('bpDone').textContent=d.groups_done;
    document.getElementById('bpTotal').textContent=d.total_groups;
    var pct=d.total_groups>0?(100*d.groups_done/d.total_groups):100;
    var fill=document.getElementById('bpFill');
    fill.style.width=pct+'%';
    fill.classList.toggle('done',d.is_clean);
    var st=document.getElementById('bpStatus');
    st.textContent=d.is_clean?'✓ Clean':'Not clean';
    st.className='big-prog-status '+(d.is_clean?'clean':'dirty');
    document.getElementById('cleanBanner').classList.toggle('on',d.is_clean && d.total_groups>0);
    var list=document.getElementById('groupsList');
    if(groups.length===0){
        list.innerHTML='<div class="empty"><div class="icn">🎉</div><div class="ttl">No cancelled items for this show</div><div>Nothing to remove. Pickers can start whenever.</div></div>';
        return;
    }
    list.innerHTML=groups.map(function(g){
        var done=g.removed_at?'done':'';
        var when=g.removed_at?('Cleared '+g.removed_at.replace('T',' ').slice(0,16)+'<br>by '+esc(g.removed_by||'')):'';
        return '<div class="grp '+done+'" data-sku="'+esc(g.sku)+'" data-part="'+esc(g.part)+'">'+
            '<div class="g-box"></div>'+
            '<div class="g-sku">'+esc(g.sku||'?')+'</div>'+
            '<div class="g-info">'+
                '<div class="g-name">'+nameCell(g.product_name)+'</div>'+
                '<div class="g-meta">From <b>'+g.order_count+'</b> cancelled order'+(g.order_count===1?'':'s')+'</div>'+
            '</div>'+
            '<div style="text-align:center"><div class="g-qty">×'+g.total_qty+'</div><div class="g-qty-lbl">to remove</div></div>'+
            '<div class="g-stamp">'+when+'</div>'+
        '</div>';
    }).join('');
    list.querySelectorAll('.grp').forEach(function(el){
        el.addEventListener('click',function(){toggleGroup(el)});
    });
}

function toggleGroup(el){
    var isDone=el.classList.contains('done');
    var newRemoved=!isDone;
    var sku=el.dataset.sku;
    var part=el.dataset.part||'';
    // Optimistic UI
    el.classList.toggle('done',newRemoved);
    fetch('/api/cleanup/'+encodeURIComponent(currentLabel)+'/mark',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({sku:sku,part:part,removed:newRemoved})
    }).then(function(r){return r.json()}).then(function(d){
        if(!d.ok){
            el.classList.toggle('done',!newRemoved);
            toast(d.error||'Failed',true);
            return;
        }
        toast(newRemoved?'✓ Cleared':'Marked pending');
        // Refresh so stamps + progress are accurate
        loadDetail();
    });
}

document.getElementById('backLink').addEventListener('click',function(e){
    e.preventDefault();
    currentLabel=null;
    document.getElementById('detailView').classList.remove('on');
    document.getElementById('listView').style.display='block';
    loadShows();  // refresh tile progress
});

loadShows();
</script>
</body></html>'''


# ══════════════════════════════════════════════════════════
# NEW HIRE ONBOARDING — admin list + per-hire detail + public flow
# ══════════════════════════════════════════════════════════

HIRES_ADMIN_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>New Hires — __BRANDMARK__</title>
__NAVBAR_CSS__
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'DM Sans',-apple-system,sans-serif;background:#ffffff;color:var(--text);min-height:100vh;padding-bottom:120px;-webkit-font-smoothing:antialiased}
.wrap{max-width:1300px;margin:0 auto;padding:40px 28px 0}
.page-head{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;margin-bottom:26px;flex-wrap:wrap}
.page-title{font-size:32px;font-weight:900;color:#141b26;letter-spacing:-.5px}
.page-sub{color:var(--text-muted);margin-top:6px;font-size:14px;max-width:600px}
.new-btn{background:var(--brand);color:#1a0e0b;border:none;border-radius:12px;padding:14px 24px;font-size:15px;font-weight:800;cursor:pointer;font-family:inherit;display:inline-flex;gap:8px;align-items:center;transition:all .15s}
.new-btn:hover{background:var(--brand-strong);transform:translateY(-1px)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:28px}
.kpi{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:18px 22px}
.kpi .lbl{font-size:11px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.8px;font-weight:700}
.kpi .val{font-size:30px;font-weight:900;color:#141b26;line-height:1;margin-top:8px}
.kpi.brand .val{color:var(--brand)}.kpi.good .val{color:#059669}.kpi.warn .val{color:#b45309}
.tbl{width:100%;background:var(--surface);border:1px solid var(--border);border-radius:14px;overflow:hidden;border-collapse:separate;border-spacing:0}
.tbl th,.tbl td{padding:14px 18px;text-align:left;border-bottom:1px solid var(--border);font-size:14px}
.tbl th{font-size:11px;text-transform:uppercase;letter-spacing:.6px;color:var(--text-dim);font-weight:700;background:rgba(17,24,39,0.032)}
.tbl tr:hover td{background:rgba(17,24,39,0.04)}
.tbl tr:last-child td{border-bottom:none}
.tbl td.name{font-weight:700;color:#141b26}
.tbl td.name a{color:inherit;text-decoration:none}
.tbl td.name a:hover{color:var(--brand)}
.status{display:inline-block;padding:4px 10px;border-radius:8px;font-size:11px;font-weight:800;letter-spacing:.5px;text-transform:uppercase}
.status.invited{background:rgba(148,163,184,.18);color:#64748b}
.status.in_progress{background:rgba(99,102,241,.18);color:#4f46e5}
.status.complete{background:rgba(16,185,129,.18);color:#059669}
.prog{display:flex;align-items:center;gap:10px;min-width:140px}
.prog-bar{flex:1;height:6px;background:rgba(17,24,39,0.096);border-radius:3px;overflow:hidden}
.prog-fill{height:100%;background:linear-gradient(90deg,var(--brand),var(--brand-strong));transition:width .3s}
.prog-txt{font-size:12px;color:var(--text-muted);font-weight:700;font-feature-settings:'tnum';white-space:nowrap}
.empty{text-align:center;padding:80px 20px;color:var(--text-dim);background:var(--surface);border:1px dashed var(--border);border-radius:14px}
.empty .icn{font-size:56px;margin-bottom:14px;opacity:.55}
.empty .ttl{font-size:18px;font-weight:800;color:var(--text-muted);margin-bottom:6px}

/* Modal */
.modal{position:fixed;inset:0;background:#ffffff;backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);z-index:300;display:none;align-items:center;justify-content:center;padding:24px;animation:fade .15s ease}
.modal.on{display:flex}
@keyframes fade{from{opacity:0}to{opacity:1}}
.modal-card{background:#ffffff;border:1px solid var(--border);border-radius:22px;padding:32px;max-width:520px;width:100%;animation:pop .2s ease}
@keyframes pop{from{transform:scale(.96);opacity:0}to{transform:scale(1);opacity:1}}
.modal-card h3{font-size:24px;font-weight:900;color:#141b26;margin-bottom:6px}
.modal-card p{font-size:13px;color:var(--text-muted);margin-bottom:20px}
.field{display:block;margin-bottom:14px}
.field-lbl{display:block;font-size:12px;color:var(--text-muted);font-weight:700;margin-bottom:6px;text-transform:uppercase;letter-spacing:.4px}
.field-in,.field-sel{width:100%;background:#ffffff;border:1px solid var(--border);border-radius:10px;padding:11px 14px;font-size:14px;color:var(--text);font-family:inherit;outline:none;transition:border .15s}
.field-in:focus,.field-sel:focus{border-color:var(--brand)}
.modal-actions{display:flex;justify-content:flex-end;gap:10px;margin-top:24px}
.btn-cancel{background:transparent;color:var(--text-muted);border:1px solid var(--border);border-radius:10px;padding:11px 22px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit}
.btn-primary{background:var(--brand);color:#1a0e0b;border:none;border-radius:10px;padding:11px 22px;font-size:14px;font-weight:800;cursor:pointer;font-family:inherit}
.invite-show{background:rgba(217,116,143,.08);border:1px solid rgba(217,116,143,.22);border-radius:12px;padding:18px;margin-top:16px;display:none}
.invite-show.on{display:block}
.invite-show .ttl{font-size:12px;color:var(--brand);font-weight:800;text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px}
.invite-show .url{display:flex;gap:8px;align-items:center}
.invite-show .url input{flex:1;background:#ffffff;border:1px solid var(--border);border-radius:8px;padding:9px 12px;font-family:'SF Mono',Menlo,monospace;font-size:11px;color:var(--text);outline:none}
.invite-show .url button{background:var(--brand);color:#1a0e0b;border:none;border-radius:8px;padding:9px 14px;font-size:12px;font-weight:800;cursor:pointer;font-family:inherit;white-space:nowrap}
.invite-show .help{font-size:12px;color:var(--text-muted);margin-top:10px;line-height:1.5}
.toast{position:fixed;top:80px;left:50%;transform:translateX(-50%);background:rgba(16,185,129,.96);color:#fff;padding:13px 24px;border-radius:11px;font-size:13px;font-weight:800;z-index:400;display:none;box-shadow:0 10px 30px rgba(0,0,0,.4)}
.toast.on{display:block}.toast.err{background:rgba(244,63,94,.96)}
</style>
</head><body data-role="__ROLE__">
__NAVBAR__
<div class="wrap">
  <div class="page-head">
    <div>
      <div class="page-title">👥 New Hires</div>
      <div class="page-sub">Onboard new team members with paperwork, signatures, and ID verification — all in one link.</div>
    </div>
    <div style="display:flex;gap:10px;align-items:center">
      <button class="new-btn" id="testEmailBtn" style="background:#fff;color:#4f46e5;border:1px solid rgba(79,70,229,.3)">📧 Test email</button>
      <button class="new-btn" id="newBtn">+ New Hire</button>
    </div>
  </div>

  <div class="kpis">
    <div class="kpi"><div class="lbl">Total</div><div class="val" id="kTotal">0</div></div>
    <div class="kpi warn"><div class="lbl">Invited (not started)</div><div class="val" id="kInvited">0</div></div>
    <div class="kpi brand"><div class="lbl">In progress</div><div class="val" id="kInProgress">0</div></div>
    <div class="kpi good"><div class="lbl">Complete</div><div class="val" id="kComplete">0</div></div>
  </div>

  <div id="content"></div>
</div>

<div class="modal" id="modal">
  <div class="modal-card">
    <h3>New Hire</h3>
    <p>Create their record and you'll get a one-time link to send.</p>
    <label class="field"><span class="field-lbl">Full legal name</span><input class="field-in" id="fName" placeholder="Jane Doe"></label>
    <label class="field"><span class="field-lbl">Email (optional)</span><input class="field-in" id="fEmail" type="email" placeholder="jane@example.com"></label>
    <label class="field"><span class="field-lbl">Phone (optional)</span><input class="field-in" id="fPhone" type="tel" placeholder="+1 555…"></label>
    <label class="field"><span class="field-lbl">Onboarding workflow</span><select class="field-sel" id="fWorkflow"></select></label>
    <label class="field"><span class="field-lbl">Preferred language</span><select class="field-sel" id="fLang">
      <option value="en">🇺🇸 English</option>
      <option value="es">🇪🇸 Español</option>
    </select></label>
    <label class="field"><span class="field-lbl">Role</span><select class="field-sel" id="fRole">
      <option value="worker">Packer / Worker</option>
      <option value="picker">Picker</option>
      <option value="cs">Customer Service</option>
      <option value="host">Live Show Host</option>
      <option value="assistant">Show Assistant</option>
      <option value="admin">Admin</option>
    </select></label>
    <div class="modal-actions">
      <button class="btn-cancel" id="cBtn">Cancel</button>
      <button class="btn-primary" id="okBtn">Create & get invite link</button>
    </div>
    <div class="invite-show" id="inviteShow">
      <div class="ttl">✓ Hire created — share this link</div>
      <div id="inviteEmailStatus" style="font-size:13px;font-weight:700;margin:2px 0 8px"></div>
      <div class="url"><input id="inviteUrl" readonly><button id="copyBtn">Copy</button></div>
      <div class="help">Send this link to your new hire via WhatsApp, email, or SMS. They open it (no password needed) and walk through onboarding step-by-step. You can see their progress on their detail page.</div>
    </div>
  </div>
</div>
<div class="toast" id="toast"></div>

<script>
function esc(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;')}
function toast(m,err){var t=document.getElementById('toast');t.textContent=m;t.className='toast on'+(err?' err':'');setTimeout(function(){t.className='toast'},2500)}

function load(){
    fetch('/api/hires').then(function(r){return r.json()}).then(function(rows){
        var content=document.getElementById('content');
        document.getElementById('kTotal').textContent=rows.length;
        document.getElementById('kInvited').textContent=rows.filter(function(r){return r.status==='invited'}).length;
        document.getElementById('kInProgress').textContent=rows.filter(function(r){return r.status==='in_progress'}).length;
        document.getElementById('kComplete').textContent=rows.filter(function(r){return r.status==='complete'}).length;
        if(rows.length===0){
            content.innerHTML='<div class="empty"><div class="icn">👥</div><div class="ttl">No hires yet</div><div>Click "+ New Hire" to send your first onboarding invite.</div></div>';
            return;
        }
        var html='<table class="tbl"><thead><tr><th>Name</th><th>Role</th><th>Status</th><th>Progress</th><th>Created</th></tr></thead><tbody>';
        rows.forEach(function(r){
            html+='<tr>'+
                '<td class="name"><a href="/admin/hires/'+r.id+'">'+esc(r.full_name)+'</a></td>'+
                '<td>'+esc(r.role_target||'')+'</td>'+
                '<td><span class="status '+r.status+'">'+r.status.replace('_',' ')+'</span></td>'+
                '<td><div class="prog"><div class="prog-bar"><div class="prog-fill" style="width:'+r.progress_pct+'%"></div></div><div class="prog-txt">'+r.progress_done+'/'+r.progress_total+'</div></div></td>'+
                '<td>'+(r.created_at||'').slice(0,10)+'</td>'+
            '</tr>';
        });
        html+='</tbody></table>';
        content.innerHTML=html;
    });
}
load();

// Populate workflow dropdown once on page load
fetch('/api/workflows').then(function(r){return r.json()}).then(function(wfs){
    var sel=document.getElementById('fWorkflow');
    sel.innerHTML=(wfs||[]).map(function(w){
        return '<option value="'+w.id+'"'+(w.is_default?' selected':'')+'>'+esc(w.name)+'</option>';
    }).join('');
});

document.getElementById('newBtn').addEventListener('click',function(){
    document.getElementById('modal').classList.add('on');
    document.getElementById('inviteShow').classList.remove('on');
    document.getElementById('fName').value='';
    document.getElementById('fEmail').value='';
    document.getElementById('fPhone').value='';
    document.getElementById('fName').focus();
});
document.getElementById('testEmailBtn').addEventListener('click',function(){
    var to=prompt('Send a test email to which address?\\n(Leave blank to send to your sending account)');
    if(to===null)return;
    var b=this;b.disabled=true;b.textContent='Sending…';
    fetch('/api/email/test',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({to:to.trim()})})
     .then(function(r){return r.json()}).then(function(d){
        b.disabled=false;b.textContent='📧 Test email';
        if(d.ok){alert('✅ Test email sent to '+d.sent_to+'\\n\\nFrom: '+d.from+'\\nReplies go to: '+d.reply_to+'\\n\\nCheck the inbox (and spam folder).');}
        else{alert('⚠️ '+(d.error||'Failed to send')+(d.configured===false?'':'\\n\\nDouble-check SMTP_USER / SMTP_PASS (App Password, no spaces) in Railway.'));}
     }).catch(function(){b.disabled=false;b.textContent='📧 Test email';alert('Request failed');});
});
document.getElementById('cBtn').addEventListener('click',function(){document.getElementById('modal').classList.remove('on')});
document.getElementById('okBtn').addEventListener('click',function(){
    var btn=this;btn.disabled=true;
    fetch('/api/hires',{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
            full_name:document.getElementById('fName').value,
            email:document.getElementById('fEmail').value,
            phone:document.getElementById('fPhone').value,
            role_target:document.getElementById('fRole').value,
            workflow_id:document.getElementById('fWorkflow').value,
            preferred_language:document.getElementById('fLang').value
        })
    }).then(function(r){return r.json()}).then(function(d){
        btn.disabled=false;
        if(!d.ok){toast(d.error||'Failed',true);return}
        document.getElementById('inviteUrl').value=d.invite_url;
        var st=document.getElementById('inviteEmailStatus');
        if(d.emailed){st.style.color='#059669';st.textContent='📧 Invite email sent automatically.';}
        else if(d.has_email&&d.email_configured){st.style.color='#e11d48';st.textContent='⚠️ Email failed'+(d.email_error?(': '+d.email_error):'')+' — copy the link below and send it manually.';}
        else if(d.has_email&&!d.email_configured){st.style.color='#b45309';st.textContent='ℹ️ Email not set up (add SMTP in Railway). Copy the link and send it manually.';}
        else{st.style.color='#8a93a5';st.textContent='No email on file — copy the link and send it manually.';}
        document.getElementById('inviteShow').classList.add('on');
        load();
    });
});
document.getElementById('copyBtn').addEventListener('click',function(){
    var inp=document.getElementById('inviteUrl');inp.select();
    document.execCommand('copy');
    toast('✓ Link copied');
});
</script>
</body></html>'''


HIRE_DETAIL_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>__HIRE_NAME__ — __BRANDMARK__</title>
__NAVBAR_CSS__
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'DM Sans',-apple-system,sans-serif;background:#ffffff;color:var(--text);min-height:100vh;padding-bottom:120px}
.wrap{max-width:1100px;margin:0 auto;padding:36px 28px 0}
.back{color:var(--text-muted);font-size:13px;font-weight:700;text-decoration:none;display:inline-flex;align-items:center;gap:6px;margin-bottom:14px}
.back:hover{color:var(--text)}
.head{display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap;margin-bottom:24px}
.h-name{font-size:30px;font-weight:900;color:#141b26;letter-spacing:-.4px;line-height:1.1}
.h-meta{font-size:13px;color:var(--text-muted);margin-top:6px;display:flex;flex-wrap:wrap;gap:14px}
.h-meta b{color:var(--text);font-weight:700}
.status-big{display:inline-block;padding:7px 14px;border-radius:10px;font-size:12px;font-weight:800;letter-spacing:.5px;text-transform:uppercase}
.status-big.invited{background:rgba(148,163,184,.18);color:#64748b}
.status-big.in_progress{background:rgba(99,102,241,.18);color:#4f46e5}
.status-big.complete{background:rgba(16,185,129,.18);color:#059669}

.card{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:22px 24px;margin-bottom:14px}
.card-title{font-size:13px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.6px;font-weight:800;margin-bottom:14px}
.invite-row{display:flex;gap:8px;align-items:center}
.invite-row input{flex:1;background:#ffffff;border:1px solid var(--border);border-radius:10px;padding:10px 14px;font-family:'SF Mono',Menlo,monospace;font-size:11px;color:var(--text);outline:none}
.invite-row button{background:var(--brand);color:#1a0e0b;border:none;border-radius:10px;padding:10px 16px;font-size:13px;font-weight:800;cursor:pointer;font-family:inherit;white-space:nowrap}
.invite-row button.warn{background:rgba(244,63,94,.16);color:#e11d48;border:1px solid rgba(244,63,94,.3)}

.bigprog{display:flex;align-items:center;gap:18px;margin-bottom:20px;background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:18px 22px}
.bigprog .pct{font-size:34px;font-weight:900;color:var(--brand);font-feature-settings:'tnum';min-width:80px}
.bigprog .bar{flex:1;height:12px;background:rgba(17,24,39,0.096);border-radius:6px;overflow:hidden}
.bigprog .fill{height:100%;background:linear-gradient(90deg,var(--brand),var(--brand-strong));transition:width .35s}
.bigprog .txt{font-size:13px;color:var(--text-muted);font-weight:700;white-space:nowrap}

.step{display:grid;grid-template-columns:50px 1fr auto;gap:18px;align-items:start;background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:18px 22px;margin-bottom:8px}
.step.done{background:rgba(16,185,129,.05);border-color:rgba(16,185,129,.22)}
.step .num{width:36px;height:36px;border-radius:50%;background:rgba(17,24,39,0.096);display:flex;align-items:center;justify-content:center;font-weight:900;color:var(--text-muted);font-size:14px;flex-shrink:0}
.step.done .num{background:#10b981;color:#ffffff}
.step.done .num::before{content:'✓'}
.step.done .num span{display:none}
.step .info{min-width:0}
.step .ttl{font-size:15px;font-weight:800;color:var(--text);margin-bottom:4px}
.step .typ{font-size:11px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.5px;font-weight:700;margin-bottom:6px}
.step .typ .dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--brand);margin-right:6px;vertical-align:middle}
.step .data{font-size:12px;color:var(--text-muted);margin-top:8px;line-height:1.5;background:rgba(17,24,39,0.04);padding:10px 14px;border-radius:10px;display:none}
.step .data.on{display:block}
.step .data b{color:var(--text)}
.step .stamp{font-size:11px;color:#059669;font-weight:700;text-align:right;white-space:nowrap;line-height:1.5}
.step:not(.done) .stamp{color:var(--text-dim)}
</style>
</head><body data-role="__ROLE__">
__NAVBAR__
<div class="wrap">
  <a href="/admin/hires" class="back">← All hires</a>

  <div class="head">
    <div>
      <div class="h-name">__HIRE_NAME__</div>
      <div class="h-meta" id="hMeta"></div>
    </div>
    <div id="hStatus"></div>
  </div>

  <div class="bigprog">
    <div class="pct" id="bpPct">0%</div>
    <div class="bar"><div class="fill" id="bpFill" style="width:0%"></div></div>
    <div class="txt" id="bpTxt">—</div>
  </div>

  <div class="card">
    <div class="card-title">🔗 Invite link</div>
    <div class="invite-row">
      <input id="iUrl" readonly value="__INVITE_URL__">
      <button id="copyBtn">Copy</button>
      <button id="regenBtn" class="warn">Regenerate</button>
    </div>
    <div style="margin-top:10px"><button id="emailBtn" class="btn-primary" style="padding:9px 16px">📧 Send invite email</button><span id="emailStat" style="font-size:13px;font-weight:700;margin-left:10px"></span></div>
    <div style="font-size:12px;color:var(--text-muted);margin-top:10px">Send to the new hire via WhatsApp, email, or SMS. Regenerate to invalidate the old link if it was shared by mistake.</div>
  </div>

  <div class="card" id="editCard">
    <div class="card-title">✏️ Edit details</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;max-width:640px">
      <label style="font-size:12px;font-weight:700;color:var(--text-muted)">Full name<input id="eName" style="width:100%;margin-top:4px;padding:9px;border:1px solid var(--border);border-radius:9px;font-family:inherit"></label>
      <label style="font-size:12px;font-weight:700;color:var(--text-muted)">Email<input id="eEmail" type="email" style="width:100%;margin-top:4px;padding:9px;border:1px solid var(--border);border-radius:9px;font-family:inherit"></label>
      <label style="font-size:12px;font-weight:700;color:var(--text-muted)">Phone<input id="ePhone" style="width:100%;margin-top:4px;padding:9px;border:1px solid var(--border);border-radius:9px;font-family:inherit"></label>
      <label style="font-size:12px;font-weight:700;color:var(--text-muted)">Role<select id="eRole" style="width:100%;margin-top:4px;padding:9px;border:1px solid var(--border);border-radius:9px;font-family:inherit"><option value="worker">Warehouse Worker</option><option value="picker">Picker</option><option value="host">Host</option><option value="assistant">Assistant</option><option value="cs">Customer Service</option><option value="admin">Admin</option></select></label>
      <label style="font-size:12px;font-weight:700;color:var(--text-muted)">Onboarding workflow<select id="eWorkflow" style="width:100%;margin-top:4px;padding:9px;border:1px solid var(--border);border-radius:9px;font-family:inherit"></select></label>
      <label style="font-size:12px;font-weight:700;color:var(--text-muted)">Language<select id="eLang" style="width:100%;margin-top:4px;padding:9px;border:1px solid var(--border);border-radius:9px;font-family:inherit"><option value="en">English</option><option value="es">Español</option></select></label>
    </div>
    <div style="margin-top:12px"><button id="saveEditBtn" class="btn-primary" style="padding:9px 18px">Save changes</button><span id="editStat" style="font-size:13px;font-weight:700;margin-left:10px"></span></div>
  </div>

  <div class="card" id="acctCard" style="display:none;border:1px solid #10b981">
    <div class="card-title">🔐 System login account</div>
    <div id="acctBody" style="font-size:14px;line-height:1.7"></div>
    <div style="font-size:12px;color:var(--text-muted);margin-top:8px">Created automatically when onboarding was completed. Hand these credentials to the new hire. Workers can also scan their badge to log in.</div>
  </div>

  <div class="card">
    <div class="card-title">📁 Employee File</div>
    <div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap">
      <a href="/admin/hires/__HIRE_ID__/file" target="_blank" style="background:var(--brand);color:#1a0e0b;border:none;border-radius:10px;padding:11px 22px;font-size:14px;font-weight:800;text-decoration:none;display:inline-flex;align-items:center;gap:6px">📄 Open printable file</a>
      <span style="font-size:12px;color:var(--text-muted);max-width:480px">Comprehensive packet with all signed documents, form responses, and uploaded IDs. Use your browser's Print → Save as PDF for the deliverable.</span>
    </div>
  </div>

  <div class="card-title" style="margin-top:8px;padding:0 4px">📋 Onboarding steps</div>
  <div id="stepsList"></div>
</div>

<script>
function esc(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function fmtData(s){
    if(!s||s.status!=='done')return '';
    var d={};try{d=JSON.parse(s.data_json||'{}')}catch(e){return ''}
    var parts=[];
    if(d.signed_name)parts.push('Signed as: <b>'+esc(d.signed_name)+'</b>');
    if(d.acknowledged && !d.signed_name)parts.push('Acknowledged');
    if(d.responses){
        Object.keys(d.responses).forEach(function(k){
            var v=d.responses[k];if(!v)return;
            parts.push(esc(k)+': <b>'+esc(String(v).slice(0,80))+'</b>');
        });
    }
    return parts.length?parts.join(' · '):'';
}

var WORKFLOWS=[];
function fillEdit(h){
    document.getElementById('eName').value=h.full_name||'';
    document.getElementById('eEmail').value=h.email||'';
    document.getElementById('ePhone').value=h.phone||'';
    if(h.role_target)document.getElementById('eRole').value=h.role_target;
    document.getElementById('eLang').value=(h.preferred_language||'en');
    var wsel=document.getElementById('eWorkflow');
    wsel.innerHTML=WORKFLOWS.map(function(w){return '<option value="'+w.id+'"'+(w.id===h.workflow_id?' selected':'')+'>'+esc(w.name)+'</option>'}).join('');
}
function renderAccount(h){
    var card=document.getElementById('acctCard');
    if(!h.provisioned_username){card.style.display='none';return;}
    card.style.display='';
    var rows='<div>Username: <b>'+esc(h.provisioned_username)+'</b></div>';
    if(h.provisioned_password)rows+='<div>Temporary password: <b style="font-family:monospace;background:#f1f5f9;padding:2px 8px;border-radius:6px">'+esc(h.provisioned_password)+'</b></div>';
    if(h.role_target==='worker')rows+='<div style="color:#059669;font-weight:700">📇 Badge login enabled — this worker can scan their badge on the login screen.</div>';
    if(h.provisioned_at)rows+='<div style="font-size:12px;color:var(--text-muted)">Account created '+(h.provisioned_at||'').slice(0,16)+'</div>';
    document.getElementById('acctBody').innerHTML=rows;
}
function load(){
    fetch('/api/workflows').then(function(r){return r.json()}).then(function(ws){WORKFLOWS=ws||[];
    fetch('/api/hires/__HIRE_ID__').then(function(r){return r.json()}).then(function(d){
        if(!d.ok)return;
        var h=d.hire;
        fillEdit(h);
        renderAccount(h);
        document.getElementById('hMeta').innerHTML=
            (h.email?'<span>📧 <b>'+esc(h.email)+'</b></span>':'')+
            (h.phone?'<span>📞 <b>'+esc(h.phone)+'</b></span>':'')+
            (h.role_target?'<span>Role: <b>'+esc(h.role_target)+'</b></span>':'')+
            '<span>Created '+(h.created_at||'').slice(0,10)+'</span>';
        document.getElementById('hStatus').innerHTML='<span class="status-big '+h.status+'">'+h.status.replace('_',' ')+'</span>';
        document.getElementById('bpPct').textContent=d.progress.pct+'%';
        document.getElementById('bpFill').style.width=d.progress.pct+'%';
        document.getElementById('bpTxt').textContent=d.progress.done+' of '+d.progress.total+' steps complete';
        var html='';
        (d.steps||[]).forEach(function(s,i){
            var done=s.status==='done';
            var dataLine=fmtData(s);
            html+='<div class="step'+(done?' done':'')+'">'+
                '<div class="num"><span>'+(i+1)+'</span></div>'+
                '<div class="info">'+
                    '<div class="typ"><span class="dot"></span>'+s.step_type+'</div>'+
                    '<div class="ttl">'+esc(s.title)+'</div>'+
                    (s.description?'<div style="font-size:13px;color:var(--text-muted);margin-top:3px">'+esc(s.description)+'</div>':'')+
                    (dataLine?'<div class="data on">'+dataLine+'</div>':'')+
                '</div>'+
                '<div class="stamp">'+(done?'Done '+(s.completed_at||'').slice(0,16):'Pending')+'</div>'+
            '</div>';
        });
        document.getElementById('stepsList').innerHTML=html;
    });
    });
}
load();

document.getElementById('saveEditBtn').addEventListener('click',function(){
    var b=this,st=document.getElementById('editStat');b.disabled=true;st.style.color='#8a93a5';st.textContent='Saving…';
    var body={full_name:document.getElementById('eName').value,email:document.getElementById('eEmail').value,
        phone:document.getElementById('ePhone').value,role_target:document.getElementById('eRole').value,
        preferred_language:document.getElementById('eLang').value,workflow_id:document.getElementById('eWorkflow').value};
    fetch('/api/hires/__HIRE_ID__',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
      .then(function(r){return r.json()}).then(function(d){
        b.disabled=false;
        if(d.ok){st.style.color='#059669';st.textContent='✓ Saved';load();}
        else{st.style.color='#e11d48';st.textContent='⚠️ '+(d.error||'Failed');}
    }).catch(function(){b.disabled=false;st.style.color='#e11d48';st.textContent='Request failed';});
});

document.getElementById('copyBtn').addEventListener('click',function(){
    var inp=document.getElementById('iUrl');inp.select();
    document.execCommand('copy');
    this.textContent='✓ Copied';
    setTimeout(function(){document.getElementById('copyBtn').textContent='Copy'},1200);
});
document.getElementById('regenBtn').addEventListener('click',function(){
    if(!confirm('Generate a new invite link? The old link will stop working.'))return;
    fetch('/api/hires/__HIRE_ID__/regenerate-token',{method:'POST'}).then(function(r){return r.json()}).then(function(d){
        if(d.ok){document.getElementById('iUrl').value=d.invite_url;alert('✓ New link generated')}
    });
});
document.getElementById('emailBtn').addEventListener('click',function(){
    var b=this,st=document.getElementById('emailStat');b.disabled=true;st.style.color='#8a93a5';st.textContent='Sending…';
    fetch('/api/hires/__HIRE_ID__/send-invite',{method:'POST'}).then(function(r){return r.json()}).then(function(d){
        b.disabled=false;
        if(d.ok){st.style.color='#059669';st.textContent='✓ Sent to '+(d.sent_to||'the hire');}
        else{st.style.color='#e11d48';st.textContent='⚠️ '+(d.error||'Failed');}
    }).catch(function(){b.disabled=false;st.style.color='#e11d48';st.textContent='Request failed';});
});
</script>
</body></html>'''


# Public token-based onboarding (no login)
HIRE_ONBOARDING_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Welcome — __BRANDMARK__ Onboarding</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
body{font-family:'DM Sans',-apple-system,sans-serif;background:#ffffff;color:#1a2130;min-height:100vh;padding-bottom:80px;-webkit-font-smoothing:antialiased}
:root{--brand:#d9748f;--brand-strong:#c25c79}
.top{background:#ffffff;backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border-bottom:1px solid rgba(17,24,39,0.096);padding:16px 22px;position:sticky;top:0;z-index:50}
.brand-mark{font-size:18px;font-weight:900;color:var(--brand);letter-spacing:1.5px;line-height:1}
.brand-sub{font-size:9px;color:#64748b;letter-spacing:2px;text-transform:uppercase;font-weight:700;margin-top:3px}

.wrap{max-width:760px;margin:0 auto;padding:30px 22px 0}
.hello{font-size:30px;font-weight:900;color:#141b26;letter-spacing:-.4px;margin-bottom:8px}
.hello-sub{font-size:15px;color:#586274;margin-bottom:24px;line-height:1.5}

.progress-card{background:rgba(17,24,39,0.064);border:1px solid rgba(17,24,39,0.112);border-radius:16px;padding:18px 22px;margin-bottom:24px;display:flex;align-items:center;gap:16px}
.pc-pct{font-size:30px;font-weight:900;color:var(--brand);font-feature-settings:'tnum';min-width:70px}
.pc-bar{flex:1;height:10px;background:rgba(17,24,39,0.096);border-radius:5px;overflow:hidden}
.pc-fill{height:100%;background:linear-gradient(90deg,var(--brand),var(--brand-strong));transition:width .4s}
.pc-txt{font-size:13px;color:#586274;white-space:nowrap;font-weight:700}

.step-card{background:rgba(17,24,39,0.064);border:2px solid rgba(17,24,39,0.112);border-radius:18px;padding:24px 24px;margin-bottom:14px;transition:all .15s}
.step-card.next{border-color:rgba(217,116,143,.4);background:rgba(217,116,143,.04)}
.step-card.done{opacity:.65}
.step-head{display:flex;align-items:center;gap:14px;cursor:pointer;user-select:none}
.step-num{width:36px;height:36px;border-radius:50%;background:rgba(17,24,39,0.096);display:flex;align-items:center;justify-content:center;font-weight:900;color:#586274;font-size:14px;flex-shrink:0}
.step-card.done .step-num{background:#10b981;color:#ffffff}
.step-card.done .step-num::before{content:'✓'}
.step-card.done .step-num span{display:none}
.step-card.next .step-num{background:var(--brand);color:#1a0e0b}
.step-info{flex:1;min-width:0}
.step-title{font-size:18px;font-weight:800;color:#141b26;line-height:1.25}
.step-card.done .step-title{color:#586274;text-decoration:line-through;text-decoration-color:rgba(255,255,255,.3)}
.step-desc{font-size:13px;color:#586274;margin-top:3px;line-height:1.4}
.step-status{font-size:11px;color:#586274;font-weight:700;text-transform:uppercase;letter-spacing:.4px;flex-shrink:0}
.step-card.done .step-status{color:#059669}
.step-card.next .step-status{color:var(--brand)}

.step-body{margin-top:18px;padding-top:18px;border-top:1px solid rgba(17,24,39,0.096);display:none}
.step-card.open .step-body{display:block;animation:expand .25s ease}
@keyframes expand{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:translateY(0)}}
.doc-body{background:#ffffff;border:1px solid rgba(17,24,39,0.096);border-radius:12px;padding:18px 20px;color:#1a2130;font-size:14px;line-height:1.6;margin-bottom:18px;white-space:pre-line;max-height:50vh;overflow-y:auto}
.ack-row{display:flex;align-items:flex-start;gap:12px;padding:14px;background:rgba(217,116,143,.06);border:1px solid rgba(217,116,143,.18);border-radius:12px;margin-bottom:14px;cursor:pointer;user-select:none}
.ack-row input[type=checkbox]{width:22px;height:22px;accent-color:var(--brand);flex-shrink:0;margin-top:1px}
.ack-row label{font-size:14px;color:#1a2130;cursor:pointer;line-height:1.5;font-weight:600}

.sign-block{background:rgba(17,24,39,0.064);border:1px dashed rgba(17,24,39,0.16);border-radius:12px;padding:18px 20px;margin-bottom:16px}
.sign-lbl{font-size:12px;color:var(--brand);font-weight:800;text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px}
.sign-input{width:100%;background:#ffffff;border:none;border-bottom:2px solid var(--brand);padding:14px 4px;font-size:24px;color:var(--brand);font-family:"Brush Script MT",cursive;outline:none;font-style:italic}
.sign-input:focus{border-bottom-color:#141b26}
.sign-hint{font-size:11px;color:#64748b;margin-top:8px;line-height:1.5}

.field{display:block;margin-bottom:14px}
.field-lbl{display:block;font-size:13px;color:#586274;font-weight:700;margin-bottom:6px}
.field-lbl .req{color:#e11d48;margin-left:4px}
.field-in,.field-sel,.field-ta{width:100%;background:#ffffff;border:1px solid rgba(17,24,39,0.128);border-radius:10px;padding:12px 14px;font-size:15px;color:#1a2130;font-family:inherit;outline:none;transition:border .15s}
.field-in:focus,.field-sel:focus,.field-ta:focus{border-color:var(--brand)}
.field-ta{min-height:80px;resize:vertical}

.complete-btn{width:100%;background:var(--brand);color:#1a0e0b;border:none;border-radius:14px;padding:16px;font-size:15px;font-weight:900;letter-spacing:.5px;text-transform:uppercase;cursor:pointer;font-family:inherit;transition:all .15s}
.complete-btn:hover{background:var(--brand-strong);transform:translateY(-1px)}
.complete-btn:disabled{background:rgba(17,24,39,0.096);color:#6b7280;cursor:not-allowed;transform:none}

.finished{text-align:center;padding:60px 20px;background:rgba(16,185,129,.05);border:1px solid rgba(16,185,129,.25);border-radius:18px;margin-top:20px;display:none}
.finished.on{display:block}
.finished .icn{font-size:80px;margin-bottom:14px}
.finished .ttl{font-size:28px;font-weight:900;color:#059669;margin-bottom:6px}
.finished .sub{font-size:15px;color:#586274}

.upload-zone{background:rgba(17,24,39,0.064);border:2px dashed rgba(17,24,39,0.16);border-radius:14px;padding:24px;text-align:center;cursor:pointer;transition:all .15s;margin-bottom:14px}
.upload-zone:hover{border-color:var(--brand);background:rgba(217,116,143,.04)}
.upload-zone .icn{font-size:42px;margin-bottom:8px;opacity:.7}
.upload-zone .ttl{font-size:14px;color:#1a2130;font-weight:700}
.upload-zone .sub{font-size:11px;color:#64748b;margin-top:4px;letter-spacing:.3px}
.upload-zone input{display:none}
.upload-field{margin-bottom:18px}
.upload-lbl{font-size:13px;color:#586274;font-weight:700;margin-bottom:8px}
.upload-pick{padding:8px}
.upload-have{display:flex;align-items:center;gap:14px;padding:6px;background:rgba(16,185,129,.05);border-radius:10px;text-align:left;border:1px solid rgba(16,185,129,.25)}
.upload-have .icn{font-size:24px;flex-shrink:0;opacity:1}
.upload-have .fn{flex:1;color:#059669;font-weight:700;font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.upload-have .upload-rm{background:rgba(244,63,94,.12);border:1px solid rgba(244,63,94,.3);color:#e11d48;font-size:11px;font-weight:700;padding:6px 12px;border-radius:8px;cursor:pointer;font-family:inherit;flex-shrink:0}
.upload-have .upload-rm:hover{background:rgba(244,63,94,.22)}
.upload-status{font-size:12px;color:#586274;margin-top:6px;min-height:16px}
.upload-status.err{color:#e11d48}
.upload-status.ok{color:#059669}
.upload-note{font-size:12px;color:#64748b;margin-top:14px;padding:10px 14px;background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.2);border-radius:10px;color:#b45309}

.toast{position:fixed;top:60px;left:50%;transform:translateX(-50%);background:rgba(16,185,129,.95);color:#fff;padding:13px 24px;border-radius:11px;font-size:13px;font-weight:800;z-index:300;display:none;box-shadow:0 10px 30px rgba(0,0,0,.4)}
.toast.on{display:block}.toast.err{background:rgba(244,63,94,.95)}

/* Language toggle in top bar */
.top{display:flex;justify-content:space-between;align-items:center;gap:14px}
.top-brand{display:flex;flex-direction:column}
.lang-toggle{display:inline-flex;background:rgba(17,24,39,0.08);border:1px solid rgba(17,24,39,0.128);border-radius:10px;padding:3px;gap:0}
.lang-btn{background:transparent;border:none;color:#586274;font-size:13px;font-weight:700;padding:7px 14px;border-radius:8px;cursor:pointer;font-family:inherit;transition:all .15s}
.lang-btn.active{background:var(--brand);color:#1a0e0b}
.lang-btn:not(.active):hover{color:#1a2130}
</style>
</head><body>
<div class="top">
  <div class="top-brand">
    <div class="brand-mark">5&nbsp;SEC</div>
    <div class="brand-sub" id="brandSub">Onboarding</div>
  </div>
  <div class="lang-toggle">
    <button class="lang-btn" data-lang="en" id="langEn">🇺🇸 EN</button>
    <button class="lang-btn" data-lang="es" id="langEs">🇪🇸 ES</button>
  </div>
</div>

<div class="wrap">
  <div class="hello" id="hello">Welcome, __HIRE_NAME__ 👋</div>
  <div class="hello-sub" id="helloSub">Let's get you set up. Work through each step below — your progress saves automatically. You can leave and come back anytime using this link.</div>

  <div class="progress-card">
    <div class="pc-pct" id="pcPct">0%</div>
    <div class="pc-bar"><div class="pc-fill" id="pcFill" style="width:0%"></div></div>
    <div class="pc-txt" id="pcTxt">—</div>
  </div>

  <div id="stepsList"></div>

  <div class="finished" id="finished">
    <div class="icn">🎉</div>
    <div class="ttl">All done!</div>
    <div class="sub">Your manager has been notified. They'll reach out about your start date and getting you a badge.</div>
  </div>
</div>
<div class="toast" id="toast"></div>

<script>
var TOKEN='__TOKEN__';
var STEPS=[];
// Locale strings for static UI chrome. Step content itself comes from the API.
var I18N = {
    en: {
        sub:'Onboarding',
        hello:'Welcome, __HIRE_NAME__ 👋',
        helloSub:"Let's get you set up. Work through each step below — your progress saves automatically. You can leave and come back anytime using this link.",
        progressTxt:function(done,total){return done+' of '+total+' done'},
        finishedTtl:'All done!',
        finishedSub:"Your manager has been notified. They'll reach out about your start date and getting you a badge.",
        statusDone:'Done',
        statusNext:'Next →',
        statusPending:'Pending',
        infoCta:'Got it — mark complete',
        ackBoxLabel:'I have read this and agree to abide by it.',
        signLabel:'Type your full name to sign',
        signPlaceholder:'Your full legal name',
        signHintAck:'By typing your name you confirm you have read and agree to the policy above. Your signature is recorded with the current timestamp and your IP address as proof.',
        signHintSign:'By typing your name you legally sign this document. We record the document content, your name, current timestamp, and your IP address as proof of signature (ESIGN Act compliant).',
        ackCta:'Submit & continue',
        signCta:'Sign & continue',
        formCta:'Save & continue',
        selectPrompt:'— select —',
        uploadNote:'',
        uploadCta:'Continue',
        tapToUpload:'Tap to upload',
        maxSize:'Max',
        uploading:'Uploading…',
        uploadError:'Upload failed',
        uploadOk:'✓ Uploaded',
        uploadRemove:'Remove',
        uploadRequired:'Please upload all required files first.',
        savingCta:'Saving…',
        tryAgain:'Try again',
        savedToast:'✓ Saved',
        invalidLink:'Invalid link. Ask your manager for a new one.',
    },
    es: {
        sub:'Orientación',
        hello:'Bienvenido, __HIRE_NAME__ 👋',
        helloSub:'Vamos a configurarte. Completa cada paso abajo — tu progreso se guarda automáticamente. Puedes salir y volver cuando quieras desde este mismo enlace.',
        progressTxt:function(done,total){return done+' de '+total+' completados'},
        finishedTtl:'¡Todo listo!',
        finishedSub:'Tu gerente ha sido notificado. Te contactará sobre tu fecha de inicio y para entregarte tu credencial.',
        statusDone:'Listo',
        statusNext:'Siguiente →',
        statusPending:'Pendiente',
        infoCta:'Entendido — marcar como completo',
        ackBoxLabel:'He leído esto y acepto cumplir con ello.',
        signLabel:'Escribe tu nombre completo para firmar',
        signPlaceholder:'Tu nombre legal completo',
        signHintAck:'Al escribir tu nombre confirmas que has leído y aceptas la política anterior. Tu firma se registra con la fecha/hora actual y tu dirección IP como prueba.',
        signHintSign:'Al escribir tu nombre firmas legalmente este documento. Registramos el contenido del documento, tu nombre, la fecha/hora actual y tu dirección IP como prueba de firma (cumple con la ley ESIGN).',
        ackCta:'Enviar y continuar',
        signCta:'Firmar y continuar',
        formCta:'Guardar y continuar',
        selectPrompt:'— selecciona —',
        uploadNote:'',
        uploadCta:'Continuar',
        tapToUpload:'Toca para subir',
        maxSize:'Máx',
        uploading:'Subiendo…',
        uploadError:'Falló la subida',
        uploadOk:'✓ Subido',
        uploadRemove:'Quitar',
        uploadRequired:'Por favor sube todos los archivos requeridos primero.',
        savingCta:'Guardando…',
        tryAgain:'Intenta de nuevo',
        savedToast:'✓ Guardado',
        invalidLink:'Enlace no válido. Pide a tu gerente uno nuevo.',
    }
};
var CUR_LANG='en';
var L=I18N.en;

function esc(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function toast(m,err){var t=document.getElementById('toast');t.textContent=m;t.className='toast on'+(err?' err':'');setTimeout(function(){t.className='toast'},2400)}

function applyStaticI18n(){
    document.getElementById('brandSub').textContent=L.sub;
    document.getElementById('hello').textContent=L.hello.replace('__HIRE_NAME__',document.title.split('—')[0].trim()||'');
    document.getElementById('helloSub').textContent=L.helloSub;
    document.getElementById('finished').querySelector('.ttl').textContent=L.finishedTtl;
    document.getElementById('finished').querySelector('.sub').textContent=L.finishedSub;
    document.getElementById('langEn').classList.toggle('active',CUR_LANG==='en');
    document.getElementById('langEs').classList.toggle('active',CUR_LANG==='es');
    document.documentElement.lang=CUR_LANG;
}

function setLang(lang,persist){
    CUR_LANG = (lang==='es')?'es':'en';
    L = I18N[CUR_LANG];
    try{localStorage.setItem('hireLang',CUR_LANG)}catch(e){}
    if(persist){
        // Server-side preference (so admin sees what the hire chose)
        fetch('/api/hire/'+TOKEN+'/lang',{method:'POST',headers:{'Content-Type':'application/json'},
            body:JSON.stringify({lang:CUR_LANG})}).catch(function(){});
    }
    applyStaticI18n();
    load();
}

function load(){
    fetch('/api/hire/'+TOKEN+'?lang='+CUR_LANG).then(function(r){return r.json()}).then(function(d){
        if(!d.ok){document.body.innerHTML='<div style="padding:80px 20px;text-align:center;color:#e11d48">'+L.invalidLink+'</div>';return}
        STEPS=d.steps||[];
        // On first load, sync to whichever language the hire actually has saved
        if(!window._langInited){
            // Order of preference: query string > localStorage > server-side preference > browser language > en
            var url=new URLSearchParams(location.search).get('lang');
            var stored=null;try{stored=localStorage.getItem('hireLang')}catch(e){}
            var browser=((navigator.language||'en').toLowerCase().slice(0,2)==='es')?'es':'en';
            var chosen=url||stored||d.lang||browser;
            window._langInited=true;
            if(chosen!==CUR_LANG){setLang(chosen,false);return}
        }
        document.getElementById('pcPct').textContent=d.progress.pct+'%';
        document.getElementById('pcFill').style.width=d.progress.pct+'%';
        document.getElementById('pcTxt').textContent=L.progressTxt(d.progress.done,d.progress.total);
        document.getElementById('finished').classList.toggle('on',d.progress.pct===100 && d.progress.total>0);
        applyStaticI18n();
        render();
    });
}

document.getElementById('langEn').addEventListener('click',function(){setLang('en',true)});
document.getElementById('langEs').addEventListener('click',function(){setLang('es',true)});

function render(){
    var firstPendingIdx=STEPS.findIndex(function(s){return s.status!=='done'});
    document.getElementById('stepsList').innerHTML=STEPS.map(function(s,i){
        var done=s.status==='done';
        var isNext=(i===firstPendingIdx);
        var cls='step-card'+(done?' done':'')+(isNext?' next':'');
        return '<div class="'+cls+'" data-id="'+s.step_id+'" data-idx="'+i+'">'+
            '<div class="step-head">'+
                '<div class="step-num"><span>'+(i+1)+'</span></div>'+
                '<div class="step-info">'+
                    '<div class="step-title">'+esc(s.title)+'</div>'+
                    (s.description?'<div class="step-desc">'+esc(s.description)+'</div>':'')+
                '</div>'+
                '<div class="step-status">'+(done?L.statusDone:(isNext?L.statusNext:L.statusPending))+'</div>'+
            '</div>'+
            '<div class="step-body"></div>'+
        '</div>';
    }).join('');
    document.querySelectorAll('.step-card').forEach(function(el){
        el.querySelector('.step-head').addEventListener('click',function(){
            if(el.classList.contains('done'))return;
            var open=el.classList.contains('open');
            document.querySelectorAll('.step-card.open').forEach(function(x){x.classList.remove('open');x.querySelector('.step-body').innerHTML=''});
            if(!open){
                el.classList.add('open');
                renderStepBody(el);
            }
        });
    });
    // Auto-open the next pending step on load
    var nextEl=document.querySelector('.step-card.next');
    if(nextEl && !nextEl.classList.contains('open')){
        nextEl.classList.add('open');
        renderStepBody(nextEl);
    }
}

function renderStepBody(el){
    var idx=parseInt(el.dataset.idx);
    var s=STEPS[idx];
    var bodyEl=el.querySelector('.step-body');
    if(s.step_type==='info'){
        bodyEl.innerHTML=(s.body?'<div class="doc-body">'+esc(s.body)+'</div>':'')+
            '<button class="complete-btn" data-act="info">'+L.infoCta+'</button>';
    } else if(s.step_type==='ack'){
        bodyEl.innerHTML=(s.body?'<div class="doc-body">'+esc(s.body)+'</div>':'')+
            '<label class="ack-row"><input type="checkbox" id="ackChk_'+s.step_id+'"><label for="ackChk_'+s.step_id+'">'+L.ackBoxLabel+'</label></label>'+
            '<div class="sign-block"><div class="sign-lbl">'+L.signLabel+'</div>'+
                '<input class="sign-input" id="ackName_'+s.step_id+'" placeholder="'+L.signPlaceholder+'">'+
                '<div class="sign-hint">'+L.signHintAck+'</div></div>'+
            '<button class="complete-btn" data-act="ack" disabled>'+L.ackCta+'</button>';
        var chk=bodyEl.querySelector('input[type=checkbox]');
        var name=bodyEl.querySelector('.sign-input');
        var btn=bodyEl.querySelector('.complete-btn');
        function upd(){btn.disabled=!(chk.checked && name.value.trim().length>=2)}
        chk.addEventListener('change',upd);name.addEventListener('input',upd);
    } else if(s.step_type==='sign'){
        bodyEl.innerHTML=(s.body?'<div class="doc-body">'+esc(s.body)+'</div>':'')+
            '<div class="sign-block"><div class="sign-lbl">'+L.signLabel+'</div>'+
                '<input class="sign-input" id="signName_'+s.step_id+'" placeholder="'+L.signPlaceholder+'">'+
                '<div class="sign-hint">'+L.signHintSign+'</div></div>'+
            '<button class="complete-btn" data-act="sign" disabled>'+L.signCta+'</button>';
        var name=bodyEl.querySelector('.sign-input');
        var btn=bodyEl.querySelector('.complete-btn');
        name.addEventListener('input',function(){btn.disabled=name.value.trim().length<2});
    } else if(s.step_type==='form'){
        var cfg={};try{cfg=JSON.parse(s.config_json||'{}')}catch(e){}
        var fields=cfg.fields||[];
        var existing={};try{existing=(JSON.parse(s.data_json||'{}').responses)||{}}catch(e){}
        bodyEl.innerHTML=fields.map(function(f){
            var req=f.required?'<span class="req">*</span>':'';
            var val=esc(existing[f.name]||'');
            if(f.type==='select'){
                var opts=(f.options||[]).map(function(o){return '<option'+(existing[f.name]===o?' selected':'')+'>'+esc(o)+'</option>'}).join('');
                return '<label class="field"><span class="field-lbl">'+esc(f.label)+req+'</span><select class="field-sel" data-name="'+esc(f.name)+'"><option value="">'+L.selectPrompt+'</option>'+opts+'</select></label>';
            }
            if(f.type==='textarea'){
                return '<label class="field"><span class="field-lbl">'+esc(f.label)+req+'</span><textarea class="field-ta" data-name="'+esc(f.name)+'">'+val+'</textarea></label>';
            }
            return '<label class="field"><span class="field-lbl">'+esc(f.label)+req+'</span><input class="field-in" data-name="'+esc(f.name)+'" type="'+esc(f.type||'text')+'" value="'+val+'"></label>';
        }).join('')+'<button class="complete-btn" data-act="form">'+L.formCta+'</button>';
    } else if(s.step_type==='upload'){
        // Real file upload — multipart POST per field, then mark step complete
        // when all required fields have a saved upload.
        var cfg={};try{cfg=JSON.parse(s.config_json||'{}')}catch(e){}
        var fields=cfg.fields||[{name:'file',label:'File',required:true}];
        var accept=cfg.accept||'image/*,.pdf';
        var maxMb=cfg.max_mb||15;
        var captureAttr=cfg.capture?(' capture="'+esc(cfg.capture)+'"'):'';
        var existing={};try{existing=JSON.parse(s.data_json||'{}').uploads||{}}catch(e){existing={}}
        bodyEl.innerHTML=(s.body?'<div class="doc-body">'+esc(s.body)+'</div>':'')+
            fields.map(function(f){
                var has=existing[f.name];
                return '<div class="upload-field" data-field="'+esc(f.name)+'">'+
                    '<div class="upload-lbl">'+esc(f.label||f.name)+(f.required?' <span style="color:#e11d48">*</span>':'')+'</div>'+
                    '<div class="upload-zone" data-field="'+esc(f.name)+'">'+
                      (has
                        ? '<div class="upload-have"><span class="icn">📎</span><span class="fn">'+esc(has.filename||'uploaded')+'</span>'+
                          '<button class="upload-rm" data-field="'+esc(f.name)+'">Remove</button></div>'
                        : '<div class="upload-pick"><div class="icn">📤</div><div class="ttl">'+(L.tapToUpload||'Tap to upload')+'</div><div class="sub">'+(L.maxSize||'Max')+' '+maxMb+'MB · '+esc(accept)+'</div></div>')+
                      '<input type="file" accept="'+esc(accept)+'"'+captureAttr+' data-field="'+esc(f.name)+'">'+
                    '</div>'+
                    '<div class="upload-status" data-status="'+esc(f.name)+'"></div>'+
                '</div>';
            }).join('')+
            '<button class="complete-btn" data-act="upload">'+L.uploadCta+'</button>';

        // Wire upload zones
        bodyEl.querySelectorAll('.upload-zone').forEach(function(zone){
            var fname=zone.dataset.field;
            var input=zone.querySelector('input[type=file]');
            zone.addEventListener('click',function(e){
                if(e.target.classList.contains('upload-rm'))return;
                input.click();
            });
            input.addEventListener('change',function(){
                if(!input.files||input.files.length===0)return;
                doUpload(s.step_id,fname,input.files[0],bodyEl);
            });
        });
        bodyEl.querySelectorAll('.upload-rm').forEach(function(btn){
            btn.addEventListener('click',function(e){
                e.stopPropagation();
                doDeleteUpload(s.step_id,btn.dataset.field,bodyEl,s);
            });
        });
    }
    bodyEl.querySelectorAll('button.complete-btn').forEach(function(b){
        b.addEventListener('click',function(){submitStep(b,s,bodyEl)});
    });
}

function doUpload(stepId,fieldName,file,bodyEl){
    var status=bodyEl.querySelector('[data-status="'+fieldName+'"]');
    status.textContent=L.uploading;
    status.className='upload-status';
    var fd=new FormData();
    fd.append('file',file);
    fd.append('field_name',fieldName);
    fetch('/api/hire/'+TOKEN+'/step/'+stepId+'/upload',{method:'POST',body:fd})
      .then(function(r){return r.json()})
      .then(function(d){
        if(!d.ok){
            status.textContent=d.error||L.uploadError;
            status.className='upload-status err';
            return;
        }
        status.textContent=L.uploadOk;
        status.className='upload-status ok';
        // Re-render the step to flip the zone into 'have' state with delete button
        load();
      })
      .catch(function(){
        status.textContent=L.uploadError;
        status.className='upload-status err';
      });
}

function doDeleteUpload(stepId,fieldName,bodyEl,s){
    fetch('/api/hire/'+TOKEN+'/step/'+stepId+'/upload/'+encodeURIComponent(fieldName),{method:'DELETE'})
      .then(function(r){return r.json()}).then(function(d){
        load();
      });
}

function submitStep(btn,s,bodyEl){
    var act=btn.dataset.act;
    var body={};
    if(act==='info'){body={};}
    else if(act==='ack'){
        body={acknowledged:bodyEl.querySelector('input[type=checkbox]').checked,
              signed_name:bodyEl.querySelector('.sign-input').value.trim()};
    } else if(act==='sign'){
        body={signed_name:bodyEl.querySelector('.sign-input').value.trim()};
    } else if(act==='form'){
        var responses={};
        bodyEl.querySelectorAll('[data-name]').forEach(function(el){responses[el.dataset.name]=el.value});
        body={responses:responses};
    } else if(act==='upload'){
        // Server checks required fields against onboarding_uploads — just POST nothing
        body={};
    }
    btn.disabled=true;btn.textContent=L.savingCta;
    fetch('/api/hire/'+TOKEN+'/step/'+s.step_id+'/complete',{
        method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)
    }).then(function(r){return r.json()}).then(function(d){
        btn.disabled=false;
        if(!d.ok){toast(d.error||'Failed',true);btn.textContent=L.tryAgain;return}
        toast(L.savedToast);
        load();
        window.scrollTo({top:0,behavior:'smooth'});
    });
}

// Force a load — the inside of load() detects first-visit language preference
load();
</script>
</body></html>'''


# ══════════════════════════════════════════════════════════
# EMPLOYEE FILE — printable per-hire packet for HR
# Comprehensive view of everything an admin needs in the file:
# profile, every signed document with audit trail, form responses,
# uploaded IDs. CSS @media print yields clean paper output;
# browser Print → Save as PDF gives the deliverable.
# ══════════════════════════════════════════════════════════

HIRE_FILE_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Employee File — __HIRE_NAME__</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --brand:#c25c79;
  --bg:#fff;
  --text:#f6f7f9;
  --text-muted:#6b7280;
  --text-dim:#9b9bab;
  --border:#dadae3;
  --surface:#f7f7f9;
}
body{font-family:'DM Sans',-apple-system,sans-serif;background:#e9e9ec;color:var(--text);min-height:100vh;padding:40px 20px;-webkit-font-smoothing:antialiased}
.page{max-width:850px;margin:0 auto;background:var(--bg);border-radius:10px;box-shadow:0 4px 24px rgba(0,0,0,.08);padding:60px 70px}

/* Header / cover area */
.cover{border-bottom:3px solid var(--brand);padding-bottom:28px;margin-bottom:32px}
.cover-top{display:flex;justify-content:space-between;align-items:flex-start;gap:24px;flex-wrap:wrap;margin-bottom:18px}
.cover-brand{font-size:14px;font-weight:900;color:var(--brand);letter-spacing:3px;text-transform:uppercase}
.cover-brand-sub{font-size:10px;color:var(--text-dim);letter-spacing:2px;text-transform:uppercase;font-weight:700;margin-top:3px}
.cover-meta{font-size:11px;color:var(--text-dim);text-align:right;line-height:1.6}
.cover-meta b{color:var(--text)}
.cover h1{font-size:38px;font-weight:900;color:var(--text);letter-spacing:-.5px;line-height:1.1;margin-bottom:6px}
.cover-sub{font-size:14px;color:var(--text-muted);font-weight:700;letter-spacing:.5px;text-transform:uppercase}

/* Profile facts grid */
.profile-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px 32px;margin:24px 0 40px;padding:20px 24px;background:var(--surface);border-radius:8px}
.fact{display:flex;flex-direction:column;gap:3px}
.fact-lbl{font-size:10px;color:var(--text-dim);font-weight:800;text-transform:uppercase;letter-spacing:1px}
.fact-val{font-size:14px;color:var(--text);font-weight:600;word-break:break-word}
.fact-val.status-complete{color:#1f7a52}
.fact-val.status-in_progress{color:#9a6500}
.fact-val.status-invited{color:var(--text-muted)}

/* Section heading */
.section-head{margin-top:48px;margin-bottom:8px;padding-bottom:8px;border-bottom:2px solid var(--text)}
.section-head h2{font-size:22px;font-weight:900;color:var(--text);letter-spacing:-.2px}
.section-head-sub{font-size:11px;color:var(--text-dim);text-transform:uppercase;letter-spacing:1px;font-weight:700;margin-top:3px}

/* Each step block */
.step{padding:24px 0;border-bottom:1px dashed var(--border);page-break-inside:avoid}
.step:last-child{border-bottom:none}
.step-num{font-size:11px;color:var(--text-dim);text-transform:uppercase;letter-spacing:1px;font-weight:800;margin-bottom:4px}
.step h2{font-size:18px;font-weight:800;color:var(--text);margin-bottom:6px;letter-spacing:-.1px}
.step-desc{font-size:13px;color:var(--text-muted);margin-bottom:12px;line-height:1.5}
.step-status{display:inline-block;font-size:10px;padding:3px 10px;border-radius:6px;font-weight:800;letter-spacing:.5px;text-transform:uppercase;margin-bottom:14px;background:var(--surface);color:var(--text-muted)}
.step-status.done{background:#dcf5e8;color:#1f7a52}
.step-status.in_progress{background:#fff4d6;color:#9a6500}
.step-status.pending{background:#fce0e0;color:#a13a3a}

.doc-body{background:#fafafc;border:1px solid var(--border);border-radius:6px;padding:18px 22px;font-size:13px;line-height:1.6;color:var(--text);margin:14px 0}

/* Form responses table */
.form-table{width:100%;border-collapse:collapse;margin:14px 0;font-size:13px}
.form-table th{text-align:left;font-size:10px;text-transform:uppercase;letter-spacing:.8px;color:var(--text-dim);font-weight:800;padding:8px 12px;border-bottom:2px solid var(--border);background:var(--surface)}
.form-table td{padding:9px 12px;border-bottom:1px solid var(--border);vertical-align:top}
.form-table td:first-child{color:var(--text-muted);width:42%;font-weight:600}
.form-table td:last-child{font-weight:700;color:var(--text)}

/* Signature block */
.sig-block{margin:18px 0 6px;padding:14px 18px;background:#fff;border:1.5px solid var(--brand);border-radius:6px}
.sig-name{font-size:30px;line-height:1.1;margin-bottom:4px}
.sig-name .cursive{font-family:'Brush Script MT','Lucida Handwriting',cursive;color:var(--brand);font-style:italic;font-weight:400}
.sig-line{border-bottom:1px solid var(--text);margin:2px 0 8px;width:60%}
.sig-audit{font-size:10px;color:var(--text-muted);font-family:'SF Mono',Menlo,monospace;letter-spacing:.2px}
.sig-audit b{color:var(--text);font-weight:700}

/* Uploads */
.uploads-list{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}
.upload-item{background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:10px;page-break-inside:avoid}
.upload-meta{font-size:11px;color:var(--text-muted);margin-bottom:8px;line-height:1.4}
.upload-meta b{color:var(--text);font-weight:700}
.upload-thumb{width:100%;height:auto;max-height:260px;object-fit:contain;border-radius:4px;background:#fff;border:1px solid var(--border)}
.upload-link{display:inline-block;margin-top:6px;font-size:12px;color:var(--brand);text-decoration:none;font-weight:700}
.upload-link:hover{text-decoration:underline}

.empty-note{font-size:12px;color:var(--text-dim);font-style:italic;padding:14px;background:var(--surface);border-radius:6px}

/* Action bar — visible on screen, hidden in print */
.action-bar{position:sticky;top:0;background:rgba(255,255,255,.96);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);border-bottom:1px solid var(--border);padding:14px 20px;margin:-40px -20px 30px;z-index:50;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;border-radius:0}
.action-bar-info{font-size:12px;color:var(--text-muted)}
.action-bar-info b{color:var(--text);font-weight:700}
.action-bar-buttons{display:flex;gap:8px;flex-wrap:wrap}
.btn{background:var(--brand);color:#fff;border:none;border-radius:8px;padding:9px 18px;font-size:13px;font-weight:800;cursor:pointer;font-family:inherit;text-decoration:none;display:inline-flex;align-items:center;gap:6px;letter-spacing:.3px}
.btn:hover{background:#a63456}
.btn.secondary{background:transparent;color:var(--text-muted);border:1px solid var(--border)}
.btn.secondary:hover{background:var(--surface);color:var(--text)}

.footer{margin-top:50px;padding-top:20px;border-top:1px solid var(--border);font-size:10px;color:var(--text-dim);text-align:center;letter-spacing:.5px;text-transform:uppercase;font-weight:700;line-height:1.7}

/* Print styles — clean paper */
@media print{
  body{background:#fff;padding:0;margin:0}
  .page{box-shadow:none;border-radius:0;padding:0.5in 0.6in;max-width:none;margin:0}
  .no-print,.action-bar{display:none !important}
  .step{page-break-inside:avoid}
  .sig-block{page-break-inside:avoid}
  .upload-item{page-break-inside:avoid}
  .section-head{page-break-after:avoid}
  @page{size:Letter;margin:0.5in 0.6in}
}
</style>
</head><body>
<div class="page">

  <div class="action-bar no-print">
    <div class="action-bar-info">
      Employee File &middot; <b>__HIRE_NAME__</b> &middot; ID #__HIRE_ID__
    </div>
    <div class="action-bar-buttons">
      <a href="/admin/hires/__HIRE_ID__" class="btn secondary">← Back to detail</a>
      <button class="btn" onclick="window.print()">🖨️ Print / Save as PDF</button>
    </div>
  </div>

  <div class="cover">
    <div class="cover-top">
      <div>
        <div class="cover-brand">__BRANDNAME_UC__</div>
        <div class="cover-brand-sub">Employee File</div>
      </div>
      <div class="cover-meta">
        Workflow: <b>__WORKFLOW_NAME__</b><br>
        Generated: <b>__GENERATED_AT__</b><br>
        Hire ID: <b>#__HIRE_ID__</b>
      </div>
    </div>
    <h1>__HIRE_NAME__</h1>
    <div class="cover-sub">Role · __HIRE_ROLE__</div>
  </div>

  <div class="profile-grid">
    <div class="fact"><div class="fact-lbl">Email</div><div class="fact-val">__HIRE_EMAIL__</div></div>
    <div class="fact"><div class="fact-lbl">Phone</div><div class="fact-val">__HIRE_PHONE__</div></div>
    <div class="fact"><div class="fact-lbl">Status</div><div class="fact-val status-__HIRE_STATUS__">__HIRE_STATUS__</div></div>
    <div class="fact"><div class="fact-lbl">Preferred Language</div><div class="fact-val">__HIRE_LANG__</div></div>
    <div class="fact"><div class="fact-lbl">Created</div><div class="fact-val">__HIRE_CREATED__</div></div>
    <div class="fact"><div class="fact-lbl">Onboarding Completed</div><div class="fact-val">__HIRE_COMPLETED__</div></div>
  </div>

  <div class="section-head">
    <h2>📋 Onboarding Steps</h2>
    <div class="section-head-sub">Full record of every document acknowledged, signed, submitted, or uploaded</div>
  </div>

  __STEPS_HTML__

  <div class="footer">
    This document is an official Employee File generated by the __BRANDNAME__ HR system.<br>
    All signatures are recorded with timestamps and IP addresses for compliance with the ESIGN Act.<br>
    Confidential — for HR use only.
  </div>

</div>
</body></html>'''

# ── SHIPPING STATUS — USPS delivery tracking dashboard ──
SHIPPING_STATUS_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Shipping Status</title>
__NAVBAR_CSS__
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#ffffff;color:#1a2130;min-height:100vh}
.page-hdr{padding:24px 28px 8px;display:flex;align-items:center;justify-content:space-between;max-width:1500px;margin:0 auto}
.page-title{font-size:22px;font-weight:800}
.page-title span{color:#4f46e5;margin-left:8px;font-weight:600;font-size:14px}
.wrap{max-width:1500px;margin:0 auto;padding:0 28px 28px}
.btn{border:none;border-radius:10px;padding:11px 20px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit;transition:all .15s}
.btn-p{background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff;box-shadow:0 4px 16px rgba(79,70,229,.3)}
.btn-p:hover{transform:translateY(-1px)}.btn-p:disabled{opacity:.5;cursor:default;transform:none}
.cards{display:grid;grid-template-columns:repeat(8,1fr);gap:10px;margin:18px 0 22px}
@media(max-width:1100px){.cards{grid-template-columns:repeat(4,1fr)}}
@media(max-width:560px){.cards{grid-template-columns:repeat(2,1fr)}}
.sc{background:#ffffff;border:1px solid rgba(17,24,39,0.096);border-radius:12px;padding:14px;cursor:pointer;transition:all .15s;text-align:center}
.sc:hover{border-color:rgba(79,70,229,.5)}.sc.active{border-color:#4f46e5;background:rgba(79,70,229,.12)}
.sc .n{font-size:26px;font-weight:800}.sc .l{font-size:11px;color:#6b7280;margin-top:4px;font-weight:700;text-transform:uppercase;letter-spacing:.4px}
.sc.delivered .n{color:#059669}.sc.transit .n{color:#2563eb}.sc.ofd .n{color:#0891b2}.sc.pre .n{color:#b45309}
.sc.exc .n{color:#f43f5e}.sc.ret .n{color:#c2410c}.sc.unk .n{color:#64748b}.sc.none .n{color:#64748b}
table{width:100%;border-collapse:collapse;background:#ffffff;border-radius:12px;overflow:hidden}
th,td{text-align:left;padding:11px 14px;font-size:13px;border-bottom:1px solid rgba(17,24,39,0.08)}
th{font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px}
.tn{font-family:monospace;color:#4f46e5}
.pill{padding:3px 9px;border-radius:50px;font-size:11px;font-weight:700;text-transform:uppercase}
.p-DELIVERED{background:rgba(52,211,153,.16);color:#059669}.p-IN_TRANSIT{background:rgba(96,165,250,.16);color:#2563eb}
.p-OUT_FOR_DELIVERY{background:rgba(34,211,238,.16);color:#0891b2}.p-PRE_TRANSIT{background:rgba(251,191,36,.16);color:#b45309}
.p-EXCEPTION{background:rgba(244,63,94,.16);color:#f43f5e}.p-RETURNED{background:rgba(251,146,60,.16);color:#c2410c}
.p-UNKNOWN,.p-UNCHECKED{background:rgba(148,163,184,.16);color:#64748b}
.p-PENDING{background:rgba(148,163,184,.16);color:#475569}.p-PICKED{background:rgba(129,140,248,.16);color:#4f46e5}
.p-PACKED{background:rgba(167,139,250,.16);color:#7c3aed}.p-SHIPPED{background:rgba(45,212,191,.16);color:#0d9488}
.p-CANCELLED{background:rgba(100,116,139,.18);color:#64748b}.p-ISSUE{background:rgba(244,63,94,.16);color:#f43f5e}
.p-GIVEAWAY{background:rgba(236,72,153,.16);color:#db2777}
.sc.pending .n{color:#475569}.sc.picked .n{color:#4f46e5}.sc.packed .n{color:#7c3aed}.sc.shipped .n{color:#0d9488}.sc.cancelled .n{color:#64748b}.sc.issue .n{color:#f43f5e}
.filters{display:flex;gap:12px;flex-wrap:wrap;align-items:end;margin:6px 0 4px}
.filters .f label{display:block;font-size:11px;font-weight:700;color:#6b7280;margin-bottom:5px;text-transform:uppercase;letter-spacing:.4px}
.filters select{background:#ffffff;border:2px solid rgba(17,24,39,0.128);border-radius:10px;padding:9px 12px;font-size:13px;color:#1a2130;font-family:inherit;outline:none;min-width:180px}
.filters select:focus{border-color:#4f46e5}
.filters .clr{background:rgba(17,24,39,0.096);color:#1a2130;border:1px solid rgba(17,24,39,0.16);border-radius:10px;padding:9px 16px;font-size:13px;font-weight:700;cursor:pointer}
.empty{text-align:center;color:#6b7280;font-style:italic;padding:30px}
.warn{background:rgba(251,191,36,.1);border:1px solid rgba(251,191,36,.3);color:#b45309;padding:12px 16px;border-radius:10px;margin-bottom:18px;font-size:13px}
.toast{position:fixed;bottom:24px;right:24px;background:#10b981;color:#fff;padding:14px 22px;border-radius:10px;font-weight:600;z-index:100;display:none}
.toast.err{background:#f43f5e}
</style></head><body>
__NAVBAR__
<div class="page-hdr"><div class="page-title">🚚 Shipping Status <span>__NAME__</span></div>
<button class="btn btn-p" id="refresh">↻ Reload</button></div>
<div class="wrap">
<div id="notice"></div>
<div class="filters">
<div class="f"><label>Show</label><select id="fShow"><option value="">All shows</option></select></div>
<div class="f"><label>Date</label><select id="fDate"><option value="">All dates</option></select></div>
<button class="clr" id="fClear">Clear filters</button>
</div>
<div class="cards" id="cards"></div>
<table><thead><tr><th>Buyer</th><th>Tracking</th><th>Status</th><th>Detail</th><th>Show</th><th>Delivered</th><th>Checked</th></tr></thead>
<tbody id="rows"><tr><td colspan="7" class="empty">Loading…</td></tr></tbody></table>
</div>
<div class="toast" id="t"></div>
<script>
var BUCKETS=[['PENDING','Pending','pending'],['PICKED','Picked','picked'],['PACKED','Packed','packed'],
['SHIPPED','Shipped','shipped'],['PRE_TRANSIT','Pre-transit','pre'],['IN_TRANSIT','In transit','transit'],
['OUT_FOR_DELIVERY','Out for delivery','ofd'],['DELIVERED','Delivered','delivered'],
['EXCEPTION','Exception','exc'],['RETURNED','Returned','ret'],['CANCELLED','Cancelled','cancelled'],
['GIVEAWAY','Giveaway','giveaway'],['ISSUE','Issue','issue'],['UNKNOWN','Unknown','unk']];
var filter='';var fillsDone=false;
function toast(m,e){var t=document.getElementById('t');t.textContent=m;t.className=e?'toast err':'toast';t.style.display='block';setTimeout(function(){t.style.display='none'},3500)}
function esc(s){return (s==null?'':String(s)).replace(/&/g,'&amp;').replace(/</g,'&lt;')}
function fmt(ts){if(!ts)return '—';var d=new Date(ts);return isNaN(d)?esc(ts):d.toLocaleDateString()+' '+d.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}
function qs(){
    var p=[];if(filter)p.push('status='+encodeURIComponent(filter));
    var sh=document.getElementById('fShow').value;if(sh)p.push('show='+encodeURIComponent(sh));
    var dt=document.getElementById('fDate').value;if(dt)p.push('date='+encodeURIComponent(dt));
    return p.length?('?'+p.join('&')):'';
}
function fillSelect(sel,opts,cur){
    sel.innerHTML=opts;sel.value=cur||'';
}
function load(){
    fetch('/api/tracking/summary'+qs()).then(function(r){return r.json()}).then(function(d){
        document.getElementById('notice').innerHTML='<div style="background:rgba(96,165,250,.1);border:1px solid rgba(96,165,250,.3);color:#2563eb;padding:10px 14px;border-radius:10px;margin-bottom:18px;font-size:13px">📦 Delivery statuses come from your TikTok order imports (Shipped Time / Delivered Time). To refresh, export <b>All orders</b> from TikTok Seller Center and re-import the show.</div>';
        // Populate the show/date dropdowns once (preserve current selection)
        if(!fillsDone){
            var shOpts='<option value="">All shows</option>'+(d.shows||[]).map(function(s){return '<option value="'+esc(s.label)+'">'+esc(s.label)+(s.date?(' · '+esc(s.date)):'')+'</option>'}).join('');
            var dtOpts='<option value="">All dates</option>'+(d.dates||[]).map(function(x){return '<option value="'+esc(x)+'">'+esc(x)+'</option>'}).join('');
            fillSelect(document.getElementById('fShow'),shOpts,document.getElementById('fShow').value);
            fillSelect(document.getElementById('fDate'),dtOpts,document.getElementById('fDate').value);
            fillsDone=true;
        }
        var ch='';BUCKETS.forEach(function(b){
            var n=(d.counts&&d.counts[b[0]])||0;
            ch+='<div class="sc '+b[2]+(filter===b[0]?' active':'')+'" onclick="setFilter(\\''+b[0]+'\\')"><div class="n">'+n+'</div><div class="l">'+b[1]+'</div></div>';
        });
        document.getElementById('cards').innerHTML=ch;
        var rows=d.rows||[];
        if(!rows.length){document.getElementById('rows').innerHTML='<tr><td colspan="7" class="empty">No orders'+(filter?' in this status':'')+'</td></tr>';return}
        document.getElementById('rows').innerHTML=rows.map(function(s){
            var st=s.unified||'UNKNOWN';
            return '<tr><td>'+esc(s.buyer_name||s.buyer_username||'—')+'</td>'+
                '<td class="tn">'+(s.tracking_code?'<a href="https://tools.usps.com/go/TrackConfirmAction?tLabels='+encodeURIComponent(s.tracking_code)+'" target="_blank" rel="noopener" class="tn" style="text-decoration:underline" title="Track on USPS.com">'+esc(s.tracking_code)+' ↗</a>':'—')+'</td>'+
                '<td><span class="pill p-'+st+'">'+st.replace(/_/g,' ')+'</span></td>'+
                '<td>'+esc(s.delivery_detail||'')+'</td>'+
                '<td>'+esc(s.import_label||'')+'</td>'+
                '<td>'+(s.delivered_at?fmt(s.delivered_at):'—')+'</td>'+
                '<td>'+fmt(s.tracked_at)+'</td></tr>';
        }).join('');
    });
}
function setFilter(b){filter=(filter===b?'':b);load()}
document.getElementById('fShow').addEventListener('change',load);
document.getElementById('fDate').addEventListener('change',load);
document.getElementById('fClear').addEventListener('click',function(){
    filter='';document.getElementById('fShow').value='';document.getElementById('fDate').value='';load();
});
document.getElementById('refresh').addEventListener('click',function(){load();toast('Reloaded')});
load();
</script></body></html>'''


# ── PERMISSIONS — manager PIN + who-can-do-what ──
PERMISSIONS_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Permissions</title>
__NAVBAR_CSS__
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#ffffff;color:#1a2130;min-height:100vh}
.page-hdr{padding:24px 28px 8px;max-width:1000px;margin:0 auto}
.page-title{font-size:22px;font-weight:800}.page-title span{color:#4f46e5;margin-left:8px;font-weight:600;font-size:14px}
.wrap{max-width:1000px;margin:0 auto;padding:8px 28px 40px}
.card{background:#ffffff;border:1px solid rgba(17,24,39,0.096);border-radius:16px;padding:22px 24px;margin-bottom:20px}
.card h2{font-size:15px;font-weight:800;color:#4f46e5;text-transform:uppercase;letter-spacing:.6px;margin-bottom:6px}
.card .desc{font-size:13px;color:#586274;margin-bottom:16px}
.row{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
input[type=password],input[type=text]{background:#ffffff;border:2px solid rgba(17,24,39,0.128);border-radius:10px;padding:11px 14px;font-size:15px;color:#1a2130;font-family:inherit;outline:none;width:200px}
input:focus{border-color:#4f46e5}
.btn{border:none;border-radius:10px;padding:11px 20px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit}
.btn-p{background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff}
.pin-state{font-size:13px;font-weight:700;padding:4px 10px;border-radius:50px}
.pin-on{background:rgba(52,211,153,.16);color:#059669}.pin-off{background:rgba(251,191,36,.16);color:#b45309}
table{width:100%;border-collapse:collapse;margin-top:8px}
th,td{padding:11px 10px;font-size:13px;border-bottom:1px solid rgba(17,24,39,0.096);text-align:center}
th{font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px}
td.act{text-align:left;font-weight:600}
input[type=checkbox]{width:18px;height:18px;cursor:pointer;accent-color:#4f46e5}
.toast{position:fixed;bottom:24px;right:24px;background:#10b981;color:#fff;padding:14px 22px;border-radius:10px;font-weight:600;z-index:100;display:none}
.toast.err{background:#f43f5e}
.note{font-size:12px;color:#6b7280;margin-top:10px}
</style></head><body>
__NAVBAR__
<div class="page-hdr"><div class="page-title">🔑 Permissions <span>__NAME__</span></div></div>
<div class="wrap">

<div class="card">
  <h2>Manager PIN</h2>
  <div class="desc">A secret code required for sensitive actions (like marking a show DONE). Only senior managers who know it can perform those actions. <span id="pinState" class="pin-state pin-off">not set</span></div>
  <div class="row">
    <input type="password" id="pin" placeholder="New PIN (4+ digits)" inputmode="numeric">
    <button class="btn btn-p" id="savePin">Save PIN</button>
  </div>
  <div class="note">Changing the PIN replaces the old one. Anyone who knew the old PIN will need the new one.</div>
</div>

<div class="card">
  <h2>Who can do what</h2>
  <div class="desc">Tick which roles may perform each sensitive action, and whether it also requires the Manager PIN.</div>
  <div id="matrix"></div>
  <div class="row" style="margin-top:16px"><button class="btn btn-p" id="savePerms">Save permissions</button></div>
  <div class="note">Built-in roles: <b>admin</b> (full access), <b>cs</b> (customer service), <b>picker</b> &amp; <b>worker</b> (floor staff). These settings apply on top of each role's base access.</div>
</div>

<div class="card">
  <h2>🏷️ Ship-from address (for buying labels)</h2>
  <div class="desc">Your warehouse address — used as the sender when buying shipping labels (giveaways, inbound).</div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;max-width:640px">
    <input type="text" id="sf_name" placeholder="Name"><input type="text" id="sf_company" placeholder="Company">
    <input type="text" id="sf_street1" placeholder="Street 1"><input type="text" id="sf_street2" placeholder="Street 2">
    <input type="text" id="sf_city" placeholder="City"><input type="text" id="sf_state" placeholder="State (e.g. FL)">
    <input type="text" id="sf_zip" placeholder="ZIP"><input type="text" id="sf_phone" placeholder="Phone">
  </div>
  <div class="row" style="margin-top:14px"><button class="btn btn-p" id="saveShipFrom">Save ship-from</button></div>
</div>

</div>
<div class="toast" id="t"></div>
<script>
function toast(m,e){var t=document.getElementById('t');t.textContent=m;t.className=e?'toast err':'toast';t.style.display='block';setTimeout(function(){t.style.display='none'},3000)}
fetch('/api/ship-from').then(function(r){return r.json()}).then(function(d){
  var a=d.address||{};['name','company','street1','street2','city','state','zip','phone'].forEach(function(k){
    var el=document.getElementById('sf_'+k);if(el)el.value=a[k]||'';});
});
document.getElementById('saveShipFrom').addEventListener('click',function(){
  var a={};['name','company','street1','street2','city','state','zip','phone'].forEach(function(k){a[k]=(document.getElementById('sf_'+k).value||'').trim()});
  a.country='US';
  fetch('/api/ship-from',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(a)})
   .then(function(r){return r.json()}).then(function(d){toast(d.ok?'Ship-from saved ✓':'Failed',!d.ok)});
});
var DATA=null;
function render(){
  document.getElementById('pinState').className='pin-state '+(DATA.pin_set?'pin-on':'pin-off');
  document.getElementById('pinState').textContent=DATA.pin_set?'PIN is set ✓':'not set yet';
  var roles=DATA.roles;
  var h='<table><thead><tr><th class="act">Action</th>'+roles.map(function(r){return '<th>'+r+'</th>'}).join('')+'<th>Needs PIN</th></tr></thead><tbody>';
  DATA.actions.forEach(function(a){
    var p=DATA.permissions[a]||{roles:[],require_pin:false};
    h+='<tr><td class="act">'+(DATA.labels[a]||a)+'</td>'+
       roles.map(function(r){
         var on=(p.roles||[]).indexOf(r)>=0;
         return '<td><input type="checkbox" data-a="'+a+'" data-r="'+r+'"'+(on?' checked':'')+'></td>';
       }).join('')+
       '<td><input type="checkbox" data-a="'+a+'" data-pin="1"'+(p.require_pin?' checked':'')+'></td></tr>';
  });
  h+='</tbody></table>';
  document.getElementById('matrix').innerHTML=h;
}
fetch('/api/permissions').then(function(r){return r.json()}).then(function(d){DATA=d;render()});
document.getElementById('savePin').addEventListener('click',function(){
  var pin=document.getElementById('pin').value.trim();
  fetch('/api/permissions/pin',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pin:pin})})
   .then(function(r){return r.json()}).then(function(d){
     if(d.ok){toast('Manager PIN saved ✓');document.getElementById('pin').value='';DATA.pin_set=true;render()}
     else toast(d.error||'Failed',true);
   });
});
document.getElementById('savePerms').addEventListener('click',function(){
  var perms={};
  DATA.actions.forEach(function(a){perms[a]={roles:[],require_pin:false}});
  document.querySelectorAll('#matrix input[type=checkbox]').forEach(function(cb){
    var a=cb.dataset.a;
    if(cb.dataset.pin){perms[a].require_pin=cb.checked}
    else if(cb.checked){perms[a].roles.push(cb.dataset.r)}
  });
  fetch('/api/permissions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({permissions:perms})})
   .then(function(r){return r.json()}).then(function(d){
     if(d.ok){toast('Permissions saved ✓');DATA.permissions=perms}
     else toast(d.error||'Failed',true);
   });
});
</script></body></html>'''


# ── INVENTORY — product catalog + receiving (weighted-avg cost) ──
INVENTORY_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Inventory</title>
__NAVBAR_CSS__
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#ffffff;color:#1a2130;min-height:100vh}
.page-hdr{padding:24px 28px 8px;max-width:1300px;margin:0 auto}
.page-title{font-size:22px;font-weight:800}.page-title span{color:#4f46e5;margin-left:8px;font-weight:600;font-size:14px}
.wrap{max-width:1300px;margin:0 auto;padding:8px 28px 40px}
.card{background:#ffffff;border:1px solid rgba(17,24,39,0.096);border-radius:16px;padding:20px 22px;margin-bottom:20px}
.card h2{font-size:14px;font-weight:800;color:#4f46e5;text-transform:uppercase;letter-spacing:.6px;margin-bottom:14px}
.row{display:flex;gap:12px;align-items:end;flex-wrap:wrap}
.f label{display:block;font-size:11px;font-weight:700;color:#6b7280;margin-bottom:5px;text-transform:uppercase;letter-spacing:.4px}
.f input{background:#ffffff;border:2px solid rgba(17,24,39,0.128);border-radius:10px;padding:11px 14px;font-size:15px;color:#1a2130;font-family:inherit;outline:none}
.f input:focus{border-color:#4f46e5}
.btn{border:none;border-radius:10px;padding:11px 20px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit}
.btn-p{background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff}.btn-s{background:rgba(17,24,39,0.128);color:#1a2130;border:1px solid rgba(17,24,39,0.16)}
table{width:100%;border-collapse:collapse}th,td{padding:10px 12px;font-size:13px;border-bottom:1px solid rgba(17,24,39,0.096);text-align:left}
th{font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px}
.thumb{width:42px;height:42px;border-radius:8px;object-fit:cover;background:rgba(17,24,39,0.08)}
.sku{font-family:monospace;color:#4f46e5;font-weight:700}
.toast{position:fixed;bottom:24px;right:24px;background:#10b981;color:#fff;padding:14px 22px;border-radius:10px;font-weight:600;z-index:100;display:none}.toast.err{background:#f43f5e}
.muted{color:#6b7280}
.modal{position:fixed;inset:0;background:rgba(0,0,0,.6);display:none;align-items:center;justify-content:center;z-index:200;padding:20px}
.modal.on{display:flex}
.modal .box{background:#f6f7f9;border:1px solid rgba(17,24,39,0.16);border-radius:16px;padding:24px;max-width:520px;width:100%}
.modal h3{font-size:17px;font-weight:800;margin-bottom:16px}
.modal .grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.modal .grid .full{grid-column:1/3}
</style></head><body>
__NAVBAR__
<div class="page-hdr"><div class="page-title">📦 Inventory <span>__NAME__</span></div></div>
<div class="wrap">
<div class="card">
  <h2>📥 Receive stock</h2>
  <div class="row">
    <div class="f"><label>SKU / Barcode</label><input id="rSku" placeholder="Scan or type" autofocus></div>
    <div class="f"><label>Qty</label><input id="rQty" type="number" style="width:90px" value="1"></div>
    <div class="f"><label>Unit cost ($)</label><input id="rCost" type="number" step="0.01" style="width:120px" placeholder="0.00"></div>
    <div class="f"><label>Name (if new)</label><input id="rName" placeholder="Product name"></div>
    <button class="btn btn-p" id="rBtn">Receive →</button>
  </div>
  <div class="muted" id="rResult" style="margin-top:10px;font-size:13px"></div>
</div>
<div class="card">
  <h2>📄 Bulk import (CSV)</h2>
  <div class="muted" style="font-size:13px;margin-bottom:12px">Load your whole catalog + stock at once. Columns (any order): <b>SKU, Name, Barcode, Category, Quantity, Unit Cost</b>. Leave SKU blank for an auto 4-digit number. <a href="/api/products/template.csv" style="color:#4f46e5;text-decoration:underline">Download template</a></div>
  <div class="row">
    <div class="f" style="flex:1;min-width:220px"><label>CSV file</label><input id="csvFile" type="file" accept=".csv,text/csv" style="width:100%;padding:9px"></div>
    <div class="f"><label>On-hand mode</label>
      <select id="csvMode" style="background:#ffffff;border:2px solid rgba(17,24,39,0.128);border-radius:10px;padding:11px 14px;font-size:14px;color:#1a2130;font-family:inherit;outline:none">
        <option value="add">Add to stock (receive)</option>
        <option value="replace">Replace on-hand (set)</option>
      </select></div>
    <button class="btn btn-p" id="csvBtn">Import →</button>
  </div>
  <div class="muted" id="csvResult" style="margin-top:10px;font-size:13px"></div>
</div>
<div class="card">
  <h2>📊 Inventory at a glance</h2>
  <div id="kpis" style="display:flex;gap:12px;flex-wrap:wrap"></div>
  <div id="bestsellers" style="margin-top:16px"></div>
</div>

<div class="card">
  <h2>🗂️ Product catalog</h2>
  <div class="row" style="margin-bottom:14px">
    <div class="f" style="flex:1"><label>Search</label><input id="q" placeholder="SKU, name, or barcode" style="width:100%"></div>
    <button class="btn btn-s" id="lowBtn">⚠️ Low stock</button>
    <a class="btn btn-s" href="/admin/stocktake" style="text-decoration:none">🔢 Stock take</a>
    <a class="btn btn-s" href="/api/products/export.csv" style="text-decoration:none">⬇️ Export</a>
    <a class="btn btn-s" href="/admin/purchasing" style="text-decoration:none">📥 Purchasing</a>
    <button class="btn btn-s" id="addBtn">+ New product</button>
  </div>
  <table><thead><tr><th></th><th>SKU</th><th>Name</th><th>Barcode</th><th>On hand</th><th>Avg cost</th><th>Target</th><th>Label</th></tr></thead>
  <tbody id="rows"><tr><td colspan="8" class="muted">Loading…</td></tr></tbody></table>
</div>
</div>

<datalist id="prodList2"></datalist>
<div class="modal" id="pModal"><div class="box" style="max-width:660px">
  <h3 id="pTitle">Product</h3>
  <div style="display:flex;gap:18px;align-items:flex-start">
    <div style="flex:0 0 140px;text-align:center">
      <img id="pImg" alt="" style="width:140px;height:140px;object-fit:cover;border-radius:12px;background:#eef0f4;border:1px solid #e4e7ec;display:block">
      <input type="file" id="pCamera" accept="image/*" capture="environment" style="display:none">
      <input type="file" id="pFile" accept="image/*" style="display:none">
      <button class="btn btn-p" style="margin-top:8px;width:100%;font-size:12px" id="pCamBtn">📸 Take photo</button>
      <button class="btn btn-s" style="margin-top:6px;width:100%;font-size:12px" id="pPhotoBtn">🖼️ Upload photo</button>
    </div>
    <div style="flex:1">
      <div class="grid">
        <div class="f full"><label>Name *</label><input id="pName" placeholder="Product name" style="width:100%"></div>
        <div class="f"><label>SKU</label><input id="pSku" placeholder="Blank = auto 4-digit" style="width:100%"></div>
        <div class="f"><label>Category</label><input id="pCat" placeholder="Optional" style="width:100%"></div>
        <div class="f full"><label>Barcode</label>
          <div style="display:flex;gap:6px">
            <input id="pBarcode" placeholder="Manufacturer barcode — or generate one" style="flex:1">
            <button class="btn btn-s" id="pGenBc" style="white-space:nowrap">Generate</button>
          </div>
        </div>
        <div class="f adminOnly"><label>Cost price ($)</label><input id="pCost" type="number" step="0.01" placeholder="0.00" style="width:100%"></div>
        <div class="f"><label>Target sell price ($)</label><input id="pTarget" type="number" step="0.01" placeholder="0.00" style="width:100%"></div>
        <div class="f adminOnly"><label>Quantity on hand</label><input id="pQty" type="number" placeholder="0" style="width:100%"></div>
        <div class="f"><label>Reorder point (alert when ≤)</label><input id="pReorder" type="number" placeholder="0" style="width:100%"></div>
        <div class="f"><label>Supplier</label><input id="pSupplier" placeholder="Optional" style="width:100%"></div>
        <div class="f"><label>Variant (shade / size)</label><input id="pVariant" placeholder="e.g. Red, Large" style="width:100%"></div>
        <div class="f"><label>Parent SKU (if a variant)</label><input id="pParent" list="prodList2" placeholder="Groups shades together" style="width:100%"></div>
      </div>
      <div class="muted" id="pMargin" style="margin-top:10px;font-size:13px"></div>
      <div id="pHistory" style="margin-top:12px"></div>
    </div>
  </div>
  <div class="muted" id="pResult" style="margin:12px 0;font-size:13px"></div>
  <div style="display:flex;gap:10px;justify-content:space-between;align-items:center;margin-top:6px">
    <a id="pLabel" href="#" target="_blank" class="btn btn-s" style="text-decoration:none;visibility:hidden">🏷️ Print label</a>
    <div style="display:flex;gap:10px">
      <button class="btn btn-s" onclick="closeP()">Close</button>
      <button class="btn btn-p" id="pSave">Save</button>
    </div>
  </div>
</div></div>

<div class="toast" id="t"></div>
<script>
function toast(m,e){var t=document.getElementById('t');t.textContent=m;t.className=e?'toast err':'toast';t.style.display='block';setTimeout(function(){t.style.display='none'},3000)}
function esc(s){var d=document.createElement('div');d.textContent=(s==null?'':String(s));return d.innerHTML}
function money(v){return v==null?'—':'$'+Number(v).toFixed(2)}
var lowMode=false;
function renderRows(rows){
  if(!rows.length){document.getElementById('rows').innerHTML='<tr><td colspan="8" class="muted">'+(lowMode?'Nothing low on stock. 🎉':'No products yet. Receive stock or add a product.')+'</td></tr>';return}
  document.getElementById('rows').innerHTML=rows.map(function(p){
    var img=p.image_url?'<img class="thumb" src="'+esc(p.image_url)+'">':'<div class="thumb"></div>';
    var oh=(p.on_hand||0);
    var low=oh<0?' style="color:#e11d48;font-weight:800"':((p.reorder_point>0&&oh<=p.reorder_point)||oh<=0?' style="color:#c2410c;font-weight:700"':'');
    var vlabel=p.variant_name?' <span style="background:#eef2ff;color:#4338ca;border-radius:50px;padding:1px 8px;font-size:11px;font-weight:700">'+esc(p.variant_name)+'</span>':'';
    var vind=p.parent_sku?'<span class="muted" style="margin-right:4px">↳</span>':'';
    return '<tr style="cursor:pointer" onclick="openP(\\''+esc(p.sku)+'\\')"><td>'+img+'</td><td class="sku">'+esc(p.sku)+'</td><td>'+vind+esc(p.name||'')+vlabel+'</td><td class="muted">'+esc(p.barcode||'—')+'</td>'+
      '<td'+low+'>'+oh+(p.reorder_point>0?(' <span class="muted" style="font-size:11px">/'+p.reorder_point+'</span>'):'')+'</td><td>'+money(p.avg_cost)+'</td><td>'+money(p.target_price)+'</td>'+
      '<td><a href="/api/product/'+encodeURIComponent(p.sku)+'/label.pdf" target="_blank" onclick="event.stopPropagation()" style="color:#4f46e5;text-decoration:underline">🏷️ Print</a></td></tr>';
  }).join('');
}
function load(){
  if(lowMode){fetch('/api/inventory/low-stock').then(function(r){return r.json()}).then(function(d){renderRows(d.products||[])});return}
  fetch('/api/products'+(document.getElementById('q').value.trim()?('?q='+encodeURIComponent(document.getElementById('q').value.trim())):'')).then(function(r){return r.json()}).then(renderRows);
}
function kpi(label,val,color){return '<div style="flex:1;min-width:130px;background:#fff;border:1px solid rgba(17,24,39,.1);border-radius:12px;padding:14px 16px"><div style="font-size:12px;color:#6b7280">'+label+'</div><div style="font-size:22px;font-weight:800;color:'+(color||'#1a2130')+'">'+val+'</div></div>'}
function loadStats(){
  fetch('/api/inventory/stats').then(function(r){return r.json()}).then(function(d){
    if(!d.ok)return;var s=d.stats;var h='';
    h+=kpi('Products',s.skus);h+=kpi('Units on hand',s.units);
    if(s.value!=null)h+=kpi('Inventory value',money(s.value),'#4f46e5');
    h+=kpi('Low stock',s.low,s.low?'#c2410c':'#059669');
    h+=kpi('Out of stock',s.out,s.out?'#e11d48':'#059669');
    document.getElementById('kpis').innerHTML=h;
  });
}
function loadBestsellers(){
  fetch('/api/inventory/bestsellers?days=30').then(function(r){return r.json()}).then(function(d){
    if(!d.ok||!d.products.length){document.getElementById('bestsellers').innerHTML='';return}
    var items=d.products.slice(0,8).map(function(p){return '<span style="display:inline-flex;gap:6px;align-items:center;background:#f6f7f9;border:1px solid rgba(17,24,39,.1);border-radius:50px;padding:5px 12px;font-size:12.5px;margin:3px"><b>'+esc(p.name)+'</b> <span class="muted">'+p.sold+' sold</span></span>'}).join('');
    document.getElementById('bestsellers').innerHTML='<div style="font-size:12px;font-weight:700;color:#6b7280;margin-bottom:6px">🔥 TOP SELLERS · LAST 30 DAYS</div>'+items;
  });
}
document.getElementById('rBtn').addEventListener('click',function(){
  var sku=document.getElementById('rSku').value.trim();
  if(!sku){toast('SKU/barcode required',true);return}
  fetch('/api/receive',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
    sku:sku,qty:parseInt(document.getElementById('rQty').value||'0'),unit_cost:parseFloat(document.getElementById('rCost').value||'0'),
    name:document.getElementById('rName').value.trim()})}).then(function(r){return r.json()}).then(function(d){
    if(!d.ok){toast(d.error||'Failed',true);return}
    document.getElementById('rResult').innerHTML='✓ '+esc(d.sku)+' — on hand: <b>'+d.on_hand+'</b> · avg cost: <b>'+money(d.avg_cost)+'</b>';
    document.getElementById('rSku').value='';document.getElementById('rCost').value='';document.getElementById('rName').value='';document.getElementById('rSku').focus();
    toast('Received ✓');load();
  });
});
// ── CSV bulk import ──
document.getElementById('csvBtn').addEventListener('click',function(){
  var fi=document.getElementById('csvFile');
  if(!fi.files||!fi.files[0]){toast('Choose a CSV file first',true);return}
  var fd=new FormData();fd.append('file',fi.files[0]);fd.append('mode',document.getElementById('csvMode').value);
  document.getElementById('csvResult').textContent='Importing…';
  fetch('/api/products/import',{method:'POST',body:fd}).then(function(r){return r.json()}).then(function(d){
    if(!d.ok){document.getElementById('csvResult').innerHTML='<span style="color:#f43f5e">'+esc(d.error||'Failed')+'</span>';return}
    document.getElementById('csvResult').innerHTML='✓ '+d.created+' new · '+d.updated+' updated · '+d.stocked+' stocked'+(d.skipped?(' · '+d.skipped+' skipped'):'');
    toast('Imported ✓');fi.value='';load();
  }).catch(function(){document.getElementById('csvResult').innerHTML='<span style="color:#f43f5e">Upload failed</span>'});
});
// ── Product editor (full product page) ──
var ROLE='__ROLE__';var curSku='';
if(ROLE!=='admin'){document.querySelectorAll('.adminOnly').forEach(function(e){e.style.display='none'})}
function gv(id){return (document.getElementById(id).value||'').trim()}
var PLACEHOLDER='data:image/svg+xml;utf8,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="140" height="140"><rect width="140" height="140" fill="#eef0f4"/><text x="70" y="76" font-size="34" text-anchor="middle" fill="#c3c9d4">📦</text></svg>');
function calcMargin(){
  var cost=parseFloat(gv('pCost')||'0'),tgt=parseFloat(gv('pTarget')||'0');
  var el=document.getElementById('pMargin');
  if(tgt>0&&cost>0){var m=tgt-cost,pct=Math.round(m/tgt*100);el.innerHTML='Margin: <b>'+money(m)+'</b> ('+pct+'%)';}
  else el.innerHTML='';
}
function fillP(p){
  curSku=p.sku||'';
  document.getElementById('pTitle').textContent=p.sku?('Product · '+p.sku):'New product';
  document.getElementById('pName').value=p.name||'';
  document.getElementById('pSku').value=p.sku||'';
  document.getElementById('pCat').value=p.category||'';
  document.getElementById('pBarcode').value=p.barcode||'';
  document.getElementById('pCost').value=(p.avg_cost!=null?p.avg_cost:'');
  document.getElementById('pTarget').value=(p.target_price||'');
  document.getElementById('pQty').value=(p.on_hand!=null?p.on_hand:'');
  document.getElementById('pReorder').value=(p.reorder_point||'');
  document.getElementById('pSupplier').value=p.supplier||'';
  document.getElementById('pVariant').value=p.variant_name||'';
  document.getElementById('pParent').value=p.parent_sku||'';
  document.getElementById('pImg').src=p.image_url||PLACEHOLDER;
  var lbl=document.getElementById('pLabel');
  if(p.sku){lbl.href='/api/product/'+encodeURIComponent(p.sku)+'/label.pdf';lbl.style.visibility='visible'}else{lbl.style.visibility='hidden'}
  document.getElementById('pResult').innerHTML='';calcMargin();
  loadHistory(p.sku);
}
function loadHistory(sku){
  var h=document.getElementById('pHistory');if(!sku){h.innerHTML='';return}
  fetch('/api/product/'+encodeURIComponent(sku)+'/moves').then(function(r){return r.json()}).then(function(d){
    if(!d.ok||!d.moves.length){h.innerHTML='<div class="muted" style="font-size:12px">No stock movements yet.</div>';return}
    var rows=d.moves.map(function(m){
      var q=m.qty>0?('<span style="color:#059669">+'+m.qty+'</span>'):('<span style="color:#e11d48">'+m.qty+'</span>');
      return '<tr><td style="padding:4px 8px">'+esc((m.moved_at||'').replace('T',' ').slice(0,16))+'</td><td style="padding:4px 8px">'+q+'</td><td style="padding:4px 8px" class="muted">'+esc(m.note||'')+'</td></tr>';
    }).join('');
    h.innerHTML='<div style="font-size:12px;font-weight:700;color:#6b7280;margin-bottom:4px">STOCK HISTORY</div><div style="max-height:160px;overflow:auto;border:1px solid rgba(17,24,39,.08);border-radius:10px"><table style="width:100%;font-size:12.5px">'+rows+'</table></div>';
  });
}
function openP(sku){
  document.getElementById('pModal').classList.add('on');
  if(sku){fetch('/api/product/'+encodeURIComponent(sku)).then(function(r){return r.json()}).then(function(d){if(d.ok)fillP(d.product);else toast('Not found',true)});}
  else{fillP({});document.getElementById('pName').focus();}
}
function closeP(){document.getElementById('pModal').classList.remove('on')}
document.getElementById('addBtn').addEventListener('click',function(){openP(null)});
document.getElementById('pCost').addEventListener('input',calcMargin);
document.getElementById('pTarget').addEventListener('input',calcMargin);
function saveP(cb){
  var name=gv('pName');if(!name){toast('Name required',true);return}
  var body={name:name,sku:gv('pSku')||curSku,barcode:gv('pBarcode'),category:gv('pCat'),
    target_price:gv('pTarget')||0,supplier:gv('pSupplier'),reorder_point:gv('pReorder')||0,
    variant_name:gv('pVariant'),parent_sku:gv('pParent')};
  if(ROLE==='admin'){if(gv('pCost')!=='')body.cost=gv('pCost');if(gv('pQty')!=='')body.on_hand=gv('pQty');}
  fetch('/api/products',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
    .then(function(r){return r.json()}).then(function(d){
      if(!d.ok){toast(d.error||'Failed',true);return}
      curSku=d.sku;document.getElementById('pSku').value=d.sku;
      var lbl=document.getElementById('pLabel');lbl.href='/api/product/'+encodeURIComponent(d.sku)+'/label.pdf';lbl.style.visibility='visible';
      document.getElementById('pTitle').textContent='Product · '+d.sku;
      load();if(cb)cb(d.sku);else{toast('Saved ✓');document.getElementById('pResult').innerHTML='✓ Saved.';}
    });
}
document.getElementById('pSave').addEventListener('click',function(){saveP()});
document.getElementById('pGenBc').addEventListener('click',function(){
  function gen(sku){fetch('/api/product/'+encodeURIComponent(sku)+'/gen-barcode',{method:'POST'}).then(function(r){return r.json()}).then(function(d){if(d.ok){document.getElementById('pBarcode').value=d.barcode;toast('Barcode generated')}else toast(d.error||'Failed',true)})}
  if(curSku)gen(curSku);else saveP(gen);
});
function uploadPhoto(f){
  if(!f)return;
  function up(sku){var fd=new FormData();fd.append('file',f);
    document.getElementById('pResult').textContent='Uploading photo…';
    fetch('/api/product/'+encodeURIComponent(sku)+'/image',{method:'POST',body:fd}).then(function(r){return r.json()}).then(function(d){
      if(d.ok){document.getElementById('pImg').src=d.image_url;document.getElementById('pResult').innerHTML='✓ Photo updated.';load()}else{toast(d.error||'Upload failed',true);document.getElementById('pResult').innerHTML=''}}).catch(function(){toast('Upload failed',true)});}
  if(curSku)up(curSku);else saveP(up);
}
document.getElementById('pPhotoBtn').addEventListener('click',function(){document.getElementById('pFile').click()});
document.getElementById('pCamBtn').addEventListener('click',function(){document.getElementById('pCamera').click()});
document.getElementById('pFile').addEventListener('change',function(){uploadPhoto(this.files&&this.files[0]);this.value=''});
document.getElementById('pCamera').addEventListener('change',function(){uploadPhoto(this.files&&this.files[0]);this.value=''});
document.getElementById('rSku').addEventListener('keydown',function(e){if(e.key==='Enter')document.getElementById('rBtn').click()});
var dq=null;document.getElementById('q').addEventListener('input',function(){lowMode=false;document.getElementById('lowBtn').classList.remove('btn-p');clearTimeout(dq);dq=setTimeout(load,200)});
document.getElementById('lowBtn').addEventListener('click',function(){lowMode=!lowMode;this.classList.toggle('btn-p',lowMode);if(lowMode)document.getElementById('q').value='';load()});
function refreshAll(){load();loadStats();loadBestsellers();}
function fillParentList(){fetch('/api/products').then(function(r){return r.json()}).then(function(rows){
  document.getElementById('prodList2').innerHTML=(rows||[]).filter(function(p){return !p.parent_sku}).map(function(p){return '<option value="'+esc(p.sku)+'">'+esc(p.name||'')+'</option>'}).join('');})}
load();loadStats();loadBestsellers();fillParentList();
</script></body></html>'''


# ── PROFIT — revenue minus COGS per show ──
ROSTER_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Roster</title>
__NAVBAR_CSS__
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#fff;color:#1a2130;min-height:100vh}
.page-hdr{padding:24px 28px 8px;max-width:1200px;margin:0 auto}
.page-title{font-size:22px;font-weight:800}.page-title span{color:#4f46e5;margin-left:8px;font-weight:600;font-size:14px}
.wrap{max-width:1200px;margin:0 auto;padding:8px 28px 50px}
.card{background:#fff;border:1px solid rgba(17,24,39,0.096);border-radius:16px;padding:18px 20px;margin-bottom:18px}
.card h2{font-size:14px;font-weight:800;color:#4f46e5;text-transform:uppercase;letter-spacing:.6px;margin-bottom:12px}
.controls{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:10px}
input[type=date],select{background:#fff;border:2px solid rgba(17,24,39,0.128);border-radius:9px;padding:8px 11px;font-size:14px;font-family:inherit;outline:none}
select{padding:6px 8px}
.btn{border:none;border-radius:10px;padding:9px 16px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit}
.btn-p{background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff}
.btn-g{background:rgba(52,211,153,.16);color:#059669}
.btn-s{background:#f6f7f9;color:#1a2130;border:1px solid rgba(17,24,39,0.12)}
.pill{font-size:11px;font-weight:700;padding:3px 10px;border-radius:50px}
.p-app{background:rgba(52,211,153,.16);color:#059669}.p-prop{background:rgba(251,191,36,.18);color:#b45309}
.p-gap{background:rgba(244,63,94,.14);color:#e11d48}
.days{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px}
.day{border:1px solid rgba(17,24,39,.12);background:#f6f7f9;border-radius:50px;padding:6px 14px;font-size:13px;font-weight:700;cursor:pointer}
.day.on{background:#4f46e5;color:#fff;border-color:#4f46e5}
table{width:100%;border-collapse:collapse}
th,td{border:1px solid rgba(17,24,39,0.1);padding:8px;font-size:13px;text-align:left;vertical-align:top}
th{background:#f6f7f9;font-size:11px;text-transform:uppercase;letter-spacing:.4px;color:#6b7280}
td.gap{background:#fff5f5}
.cell label{display:block;font-size:10px;color:#9ca3af;font-weight:700;margin:2px 0}
.cell select{width:100%;font-size:12.5px}
.staff-row{display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid rgba(17,24,39,.07);flex-wrap:wrap}
.staff-row .nm{font-weight:700;min-width:150px}.staff-row .rl{font-size:11px;color:#6b7280;text-transform:uppercase}
.chk{font-size:12.5px;display:inline-flex;align-items:center;gap:4px;margin-right:10px}
.muted{color:#9ca3af;font-size:13px}
.toast{position:fixed;bottom:24px;right:24px;background:#10b981;color:#fff;padding:14px 22px;border-radius:10px;font-weight:600;z-index:100;display:none}
.toast.err{background:#f43f5e}
</style></head><body>
__NAVBAR__
<div class="page-hdr"><div class="page-title">🗓️ Roster <span>__NAME__</span></div></div>
<div class="wrap">
<div class="card">
  <div class="controls">
    <label class="muted" style="font-weight:700">Week of</label>
    <input type="date" id="week">
    <button class="btn btn-g" id="apprBtn">✓ Approve week</button>
    <span id="status"></span>
  </div>
  <div class="muted" style="font-size:12.5px">Build shifts from the time ranges the girls submitted. Only people available for the whole shift (and not already booked) can be chosen. Approve to publish.</div>
</div>

<div class="card">
  <h2>📥 Availability submissions <span id="subCount" class="muted" style="text-transform:none;font-weight:600"></span></h2>
  <div id="subs"><div class="muted">Loading…</div></div>
</div>

<div class="card">
  <h2>📅 Week at a glance</h2>
  <div id="weekgrid"><div class="muted">—</div></div>
  <div class="muted" style="font-size:11.5px;margin-top:8px">🟩 fully staffed · 🟨 needs a person · 🟥 empty. Each cell: time · Host / Assistant.</div>
</div>

<div class="card">
  <h2>✏️ Build the day</h2>
  <div class="days" id="days"></div>
  <div id="grid"><div class="muted">Pick a day.</div></div>
</div>

<div class="card">
  <h2 style="margin-bottom:2px">📺 Your channels</h2>
  <style>
  .chrow{display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid rgba(17,24,39,.07)}
  .chrow input{flex:1;padding:8px 11px;border:1px solid rgba(17,24,39,.15);border-radius:8px;font-size:14px}
  .chplat{font-size:10px;font-weight:900;text-transform:uppercase;letter-spacing:.5px;padding:3px 9px;border-radius:50px}
  .chplat.tiktok{background:rgba(244,63,94,.15);color:#e11d48}
  .chplat.whatnot{background:rgba(245,158,11,.15);color:#b45309}
  .chlang{font-size:11px;color:#6b7280;text-transform:uppercase;font-weight:800}
  .chadd{display:flex;gap:9px;margin-top:14px;flex-wrap:wrap}
  .chadd input,.chadd select{padding:9px 12px;border:1px solid rgba(17,24,39,.15);border-radius:9px;font-size:14px}
  .chadd input:first-child{flex:1;min-width:220px}
  .emptych{padding:22px;text-align:center;color:#6b7280;background:rgba(99,102,241,.05);border:1px dashed rgba(99,102,241,.3);border-radius:12px;line-height:1.7}
  </style>
  <div class="muted" style="font-size:12.5px;margin-bottom:10px">The accounts you go live on. Add one row per channel — these are what you schedule hosts onto.</div>
  <div id="chList"><div class="muted">Loading…</div></div>
  <div class="chadd">
    <input id="chName" placeholder="Channel name (e.g. Glam Beauty Live)" maxlength="60">
    <select id="chPlat"><option value="">— platform —</option><option value="tiktok">TikTok</option><option value="whatnot">Whatnot</option></select>
    <input id="chLang" placeholder="Lang (en)" maxlength="8" style="max-width:110px">
    <button class="btn btn-p" id="chAdd">+ Add channel</button>
  </div>
</div>

<div class="card">
  <h2>👥 Who can run which channel</h2>
  <div class="muted" style="font-size:12.5px;margin-bottom:10px">Tick the channels each host/assistant is allowed on. Unticked = never scheduled there.</div>
  <div id="staff"><div class="muted">Loading…</div></div>
</div>
</div>
<div class="toast" id="t"></div>
<script>
function toast(m,e){var t=document.getElementById('t');t.textContent=m;t.className=e?'toast err':'toast';t.style.display='block';setTimeout(function(){t.style.display='none'},3000)}
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
// Date-only values must never round-trip through UTC — that shifts the day for
// anyone west of Greenwich. Parse and format the week strictly by components.
function weekBase(){
  var v=(document.getElementById('week').value||'').split('-');
  if(v.length!==3)return new Date();
  return new Date(+v[0],+v[1]-1,+v[2]);
}
function fmtISO(d){
  return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');
}
var CH=[],STAFF={host:[],assistant:[]},WEEK=[],DAYSEL=0,RANGES={};
function monday(){var d=new Date();var g=(d.getDay()+6)%7;d.setDate(d.getDate()-g);return d.toISOString().slice(0,10)}
document.getElementById('week').value=monday();
function tmin(t){if(!t)return null;if(t==='24:00')return 1440;var m=t.split(':');return parseInt(m[0])*60+parseInt(m[1])}
function eligibleCh(p,chId){return !p.allowed_channels.length||p.allowed_channels.indexOf(chId)>=0}
function covers(u,day,s,e){var rs=RANGES[u]||[];return rs.some(function(r){return r.date===day&&tmin(r.start)<=tmin(s)&&tmin(r.end)>=tmin(e)})}
function isFree(u,day,s,e,exceptId){return !WEEK.some(function(sh){return sh.shift_date===day&&sh.id!==exceptId&&(sh.host_user===u||sh.assistant_user===u)&&tmin(s)<tmin(sh.end_time)&&tmin(sh.start_time)<tmin(e)})}
function loadStaff(){fetch('/api/roster/staff').then(function(r){return r.json()}).then(function(d){CH=d.channels;STAFF=d.staff;renderStaff();renderChannelList()})}
// ── Channel setup (each tenant defines their own) ──
function renderChannelList(){
  var el=document.getElementById('chList'); if(!el)return;
  if(!CH.length){
    el.innerHTML='<div class="emptych">👋 <b>No channels yet.</b><br>Add the accounts you go live on below — then you can build the week and set who may host each one.</div>';
    return;
  }
  el.innerHTML=CH.map(function(c){
    var badge=c.platform?('<span class="chplat '+esc(c.platform)+'">'+esc(c.platform)+'</span>'):'';
    return '<div class="chrow"><input value="'+esc(c.name)+'" data-ren="'+c.id+'" maxlength="60">'+badge+
      (c.language?'<span class="chlang">'+esc(c.language)+'</span>':'')+
      '<button class="btn btn-s" data-del="'+c.id+'">Remove</button></div>';
  }).join('');
  el.querySelectorAll('input[data-ren]').forEach(function(i){
    i.addEventListener('change',function(){
      fetch('/api/roster/channels/'+i.dataset.ren,{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({name:i.value})}).then(function(r){return r.json()}).then(function(d){
          if(d.ok){toast('Renamed');CH=d.channels;loadWeek()}else{toast(d.error||'Failed',1);loadStaff()}});
    });
  });
  el.querySelectorAll('button[data-del]').forEach(function(b){
    b.addEventListener('click',function(){
      if(!confirm('Remove this channel? Existing shifts stay in history, but you can no longer schedule onto it.'))return;
      fetch('/api/roster/channels/'+b.dataset.del,{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({active:false})}).then(function(r){return r.json()}).then(function(d){
          if(d.ok){toast('Removed');loadStaff();loadWeek()}else toast(d.error||'Failed',1)});
    });
  });
}
function addChannel(){
  var n=document.getElementById('chName').value.trim();
  if(!n){toast('Enter a channel name',1);return}
  fetch('/api/roster/channels',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({name:n,platform:document.getElementById('chPlat').value,language:document.getElementById('chLang').value.trim()})})
  .then(function(r){return r.json()}).then(function(d){
    if(!d.ok){toast(d.error||'Failed',1);return}
    document.getElementById('chName').value='';document.getElementById('chLang').value='';
    toast('Channel added');loadStaff();loadWeek();
  });
}
function renderStaff(){
  var el=document.getElementById('staff');var all=STAFF.host.concat(STAFF.assistant);
  if(!all.length){el.innerHTML='<div class="muted">No hosts or assistants yet. Create them in Settings → Users (role: host / assistant).</div>';return}
  function row(p,role){
    var chk=CH.map(function(c){var on=!p.allowed_channels.length||p.allowed_channels.indexOf(c.id)>=0;
      return '<label class="chk"><input type="checkbox" data-u="'+esc(p.username)+'" value="'+c.id+'" '+(on?'checked':'')+'> '+esc(c.name)+'</label>'}).join('');
    return '<div class="staff-row"><span class="nm">'+esc(p.name)+'</span><span class="rl">'+role+'</span><span>'+chk+'</span>'+
      '<button class="btn btn-s" style="padding:5px 12px;font-size:12px" onclick="saveChannels(\\''+esc(p.username)+'\\')">Save</button></div>';
  }
  el.innerHTML=STAFF.host.map(function(p){return row(p,'host')}).join('')+STAFF.assistant.map(function(p){return row(p,'assistant')}).join('');
}
function saveChannels(u){
  var ids=[];document.querySelectorAll('input[data-u="'+u+'"]:checked').forEach(function(x){ids.push(parseInt(x.value))});
  fetch('/api/roster/staff/'+encodeURIComponent(u)+'/channels',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({allowed_channels:ids})})
    .then(function(r){return r.json()}).then(function(d){if(d.ok){toast('Saved');loadStaff();loadWeek()}else toast(d.error||'Failed',1)});
}
function fmtRanges(rngs){var by={};rngs.forEach(function(r){(by[r.date]=by[r.date]||[]).push(r.start+'–'+(r.end==='24:00'?'24:00':r.end))});
  return Object.keys(by).sort().map(function(dt){var d=new Date(dt+'T00:00');return '<b>'+['Su','Mo','Tu','We','Th','Fr','Sa'][d.getDay()]+'</b> '+by[dt].join(', ')}).join(' &nbsp;·&nbsp; ')}
function loadSubs(){
  fetch('/api/roster/submissions?week_start='+document.getElementById('week').value).then(function(r){return r.json()}).then(function(d){
    if(!d.ok)return;RANGES={};d.submitted.forEach(function(p){RANGES[p.username]=p.ranges});
    document.getElementById('subCount').textContent='('+d.submitted_count+' of '+d.total_staff+' submitted)';
    var sub=d.submitted.map(function(p){return '<div style="background:#ecfdf5;border:1px solid #a7f3d0;border-radius:10px;padding:8px 12px;font-size:12.5px;margin:4px 0"><b>'+esc(p.name)+'</b> <span class="muted">('+p.roles.join('/')+')</span> — '+fmtRanges(p.ranges)+'</div>'}).join('');
    var miss=d.missing.map(function(p){return '<span style="display:inline-flex;background:#fff5f5;border:1px solid #fecaca;border-radius:50px;padding:3px 12px;font-size:12.5px;margin:3px;color:#b91c1c">'+esc(p.name)+' <span style="opacity:.7">&nbsp;('+p.roles.join('/')+')</span></span>'}).join('');
    document.getElementById('subs').innerHTML=(sub||'<span class="muted">No submissions yet.</span>')+
      (miss?('<div style="margin-top:10px;font-size:12px;font-weight:700;color:#6b7280">STILL WAITING ON</div>'+miss):'');
    renderChannels();
  });
}
function loadWeek(){
  fetch('/api/roster/week?week_start='+document.getElementById('week').value).then(function(r){return r.json()}).then(function(d){
    WEEK=d.shifts;CH=d.channels;
    document.getElementById('status').innerHTML=(d.approved?'<span class="pill p-app">approved</span>':(WEEK.length?'<span class="pill p-prop">proposed</span>':''))+
      (d.incomplete?(' <span class="pill p-gap">'+d.incomplete+' need people</span>'):'')+
      ' <span class="muted" style="font-size:12px">'+d.covered_hours+'h covered</span>';
    renderDays();renderWeekGrid();loadSubs();
  });
}
function renderWeekGrid(){
  var base=weekBase();var days=[];
  for(var i=0;i<7;i++){var d=new Date(base);d.setDate(d.getDate()+i);days.push(fmtISO(d))}
  var names=['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
  if(!CH.length){document.getElementById('weekgrid').innerHTML='<div class="muted">No channels.</div>';return}
  var head='<tr><th>Channel</th>'+names.map(function(n,i){var d=new Date(days[i]+'T00:00');return '<th>'+n+' '+(d.getMonth()+1)+'/'+d.getDate()+'</th>'}).join('')+'</tr>';
  var body=CH.map(function(c){
    var tds=days.map(function(day){
      var shifts=WEEK.filter(function(s){return s.shift_date===day&&s.channel_id===c.id}).sort(function(a,b){return tmin(a.start_time)-tmin(b.start_time)});
      if(!shifts.length)return '<td class="muted" style="text-align:center">·</td>';
      return '<td>'+shifts.map(function(s){var full=s.host_user&&s.assistant_user;
        var bg=full?'#ecfdf5':((s.host_user||s.assistant_user)?'#fffbeb':'#fff5f5');
        var bd=full?'#a7f3d0':((s.host_user||s.assistant_user)?'#fde68a':'#fecaca');
        return '<div style="background:'+bg+';border:1px solid '+bd+';border-radius:6px;padding:3px 6px;margin-bottom:3px;font-size:11px;line-height:1.35"><b>'+s.start_time+'–'+s.end_time+'</b><br>'+esc(s.host_name||'— host')+'<br><span class="muted">'+esc(s.assistant_name||'— asst')+'</span></div>';
      }).join('')+'</td>';
    }).join('');
    return '<tr><td style="font-weight:800;font-size:12px;white-space:nowrap">'+esc(c.name)+'</td>'+tds+'</tr>';
  }).join('');
  document.getElementById('weekgrid').innerHTML='<div style="overflow-x:auto"><table style="min-width:920px">'+head+body+'</table></div>';
}
function renderDays(){
  var names=['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];var base=weekBase();
  document.getElementById('days').innerHTML=names.map(function(n,i){
    var dt=new Date(base);dt.setDate(dt.getDate()+i);
    return '<div class="day'+(i===DAYSEL?' on':'')+'" onclick="DAYSEL='+i+';renderDays();renderChannels()">'+n+' '+(dt.getMonth()+1)+'/'+dt.getDate()+'</div>';
  }).join('');
}
function dateForSel(){var b=weekBase();b.setDate(b.getDate()+DAYSEL);return fmtISO(b)}
function personSel(role,chId,day,sh,which){
  var cur=which==='host'?sh.host_user:sh.assistant_user;
  var pool=STAFF[role].filter(function(p){return eligibleCh(p,chId)&&covers(p.username,day,sh.start_time,sh.end_time)&&(p.username===cur||isFree(p.username,day,sh.start_time,sh.end_time,sh.id))});
  var opts='<option value="">— pick —</option>'+pool.map(function(p){return '<option value="'+esc(p.username)+'"'+(p.username===cur?' selected':'')+'>'+esc(p.name)+'</option>'}).join('');
  if(cur&&!pool.some(function(p){return p.username===cur}))opts+='<option value="'+esc(cur)+'" selected>'+esc(cur)+' (was)</option>';
  return '<select onchange="reassign('+sh.id+',\\''+which+'\\',this.value)">'+opts+'</select>';
}
function renderChannels(){
  var day=dateForSel();
  document.getElementById('grid').innerHTML=CH.map(function(c){
    var shifts=WEEK.filter(function(s){return s.shift_date===day&&s.channel_id===c.id}).sort(function(a,b){return tmin(a.start_time)-tmin(b.start_time)});
    var cov=0;shifts.forEach(function(s){if(s.host_user&&s.assistant_user)cov+=tmin(s.end_time)-tmin(s.start_time)});
    var rows=shifts.map(function(s){
      var gap=(!s.host_user||!s.assistant_user);
      return '<div class="cell'+(gap?' gap':'')+'" style="border:1px solid rgba(17,24,39,.1);border-radius:10px;padding:8px 10px;margin-bottom:6px;display:flex;gap:10px;align-items:center;flex-wrap:wrap">'+
        '<b style="min-width:110px">'+s.start_time+'–'+s.end_time+'</b>'+
        '<span><label style="font-size:10px;color:#9ca3af;font-weight:700">Host</label>'+personSel('host',c.id,day,s,'host')+'</span>'+
        '<span><label style="font-size:10px;color:#9ca3af;font-weight:700">Assistant</label>'+personSel('assistant',c.id,day,s,'assistant')+'</span>'+
        '<button class="btn btn-s" style="margin-left:auto;padding:5px 10px;color:#e11d48" onclick="delShift('+s.id+')">Delete</button></div>';
    }).join('');
    return '<div style="border:1px solid rgba(17,24,39,.12);border-radius:14px;padding:14px;margin-bottom:12px">'+
      '<div style="font-weight:800;margin-bottom:8px">'+esc(c.name)+' <span class="muted" style="font-weight:600;font-size:12px">· '+(cov/60).toFixed(1)+'h / 24h covered</span></div>'+
      (rows||'<div class="muted" style="font-size:12.5px;margin-bottom:8px">No shifts yet.</div>')+
      '<div style="display:flex;gap:8px;align-items:center;margin-top:8px"><span class="muted" style="font-size:12px">Add shift:</span>'+
      '<input type="time" id="ns'+c.id+'" style="padding:6px;border:2px solid #e4e7ec;border-radius:8px"><span class="muted">to</span>'+
      '<input type="time" id="ne'+c.id+'" style="padding:6px;border:2px solid #e4e7ec;border-radius:8px">'+
      '<button class="btn btn-p" style="padding:7px 14px" onclick="addShift('+c.id+')">+ Add</button></div></div>';
  }).join('');
}
function addShift(chId){
  var s=document.getElementById('ns'+chId).value,e=document.getElementById('ne'+chId).value;
  if(!s||!e||e<=s){toast('Enter a valid start/end',1);return}
  fetch('/api/roster/shift/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({channel_id:chId,date:dateForSel(),start:s,end:e})})
    .then(function(r){return r.json()}).then(function(d){if(d.ok){toast('Shift added');loadWeek()}else toast(d.error||'Failed',1)});
}
function delShift(id){if(!confirm('Delete this shift?'))return;
  fetch('/api/roster/shift/'+id+'/delete',{method:'POST'}).then(function(r){return r.json()}).then(function(){toast('Deleted');loadWeek()})}
function reassign(sid,role,val){
  var body={};body[role+'_user']=val;
  fetch('/api/roster/shift/'+sid,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
    .then(function(r){return r.json()}).then(function(d){if(d.ok){toast('Updated');loadWeek()}else{toast(d.error||'Conflict',1);loadWeek()}});
}
document.getElementById('apprBtn').addEventListener('click',function(){
  if(!confirm('Approve & publish this week to all hosts and assistants?'))return;
  fetch('/api/roster/approve',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({week_start:document.getElementById('week').value})})
    .then(function(r){return r.json()}).then(function(d){if(d.ok){toast('Approved ✓');loadWeek()}else toast(d.error||'Failed',1)});
});
document.getElementById('week').addEventListener('change',function(){DAYSEL=0;loadWeek()});
document.getElementById('chAdd').addEventListener('click',addChannel);
document.getElementById('chName').addEventListener('keydown',function(e){if(e.key==='Enter')addChannel()});
loadStaff();loadWeek();
</script></body></html>'''


MYAVAIL_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>My Availability</title>
__NAVBAR_CSS__
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#fff;color:#1a2130;min-height:100vh}
.page-hdr{padding:24px 28px 8px;max-width:900px;margin:0 auto}
.page-title{font-size:22px;font-weight:800}.page-title span{color:#4f46e5;margin-left:8px;font-weight:600;font-size:14px}
.wrap{max-width:900px;margin:0 auto;padding:8px 28px 50px}
.card{background:#fff;border:1px solid rgba(17,24,39,0.096);border-radius:16px;padding:18px 20px;margin-bottom:18px}
.controls{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:8px}
input[type=date]{border:2px solid rgba(17,24,39,0.128);border-radius:9px;padding:8px 11px;font-size:14px;font-family:inherit;outline:none}
.btn{border:none;border-radius:10px;padding:10px 18px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit}
.btn-p{background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff}.btn-s{background:#f6f7f9;color:#1a2130;border:1px solid rgba(17,24,39,0.12)}
table{width:100%;border-collapse:collapse;margin-top:6px}
th,td{border:1px solid rgba(17,24,39,0.1);padding:10px 6px;text-align:center;font-size:13px}
th{background:#f6f7f9;font-size:11px;text-transform:uppercase;letter-spacing:.4px;color:#6b7280}
td.blk{background:#f9fafb;font-weight:800;text-align:left;white-space:nowrap}
td.on{background:#ecfdf5}
td label{display:block;cursor:pointer;padding:6px}
input[type=checkbox]{width:20px;height:20px;cursor:pointer;accent-color:#4f46e5}
.muted{color:#9ca3af;font-size:13px}
.toast{position:fixed;bottom:24px;right:24px;background:#10b981;color:#fff;padding:14px 22px;border-radius:10px;font-weight:600;z-index:100;display:none}
</style></head><body>
__NAVBAR__
<div class="page-hdr"><div class="page-title">🕒 My Availability <span>__NAME__</span></div></div>
<div class="wrap">
<div class="card">
  <div class="controls">
    <span class="muted" style="font-weight:700">Week of</span>
    <input type="date" id="week">
    <button class="btn btn-p" id="saveBtn" style="margin-left:auto">Submit availability</button>
  </div>
  <div class="muted" id="chnote"></div>
  <div class="muted" style="font-size:12.5px;margin-top:4px">For each day, add the time ranges you can work (e.g. 14:00–20:00). Add more than one if there's a gap. Your manager builds the shifts from these.</div>
  <div id="dayList" style="margin-top:14px"></div>
</div>
</div>
<div class="toast" id="t"></div>
<script>
function toast(m){var t=document.getElementById('t');t.textContent=m;t.style.display='block';setTimeout(function(){t.style.display='none'},2600)}
function monday(){var d=new Date();var g=(d.getDay()+6)%7;d.setDate(d.getDate()-g);return d.toISOString().slice(0,10)}
document.getElementById('week').value=monday();
function days(){var names=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];var b=new Date(document.getElementById('week').value);
  return names.map(function(n,i){var d=new Date(b);d.setDate(d.getDate()+i);return {name:n+' '+(d.getMonth()+1)+'/'+d.getDate(),iso:d.toISOString().slice(0,10)}})}
function rangeRow(iso,st,en){
  return '<div class="rr" data-date="'+iso+'" style="display:flex;gap:8px;align-items:center;margin-bottom:6px">'+
    '<input type="time" class="rs" value="'+(st||'')+'" style="padding:7px;border:2px solid #e4e7ec;border-radius:8px;font-size:14px">'+
    '<span class="muted">to</span>'+
    '<input type="time" class="re" value="'+(en||'')+'" style="padding:7px;border:2px solid #e4e7ec;border-radius:8px;font-size:14px">'+
    '<button class="btn btn-s" style="padding:5px 10px" onclick="this.parentNode.remove()">✕</button></div>';
}
function render(byday){
  var D=days();
  document.getElementById('dayList').innerHTML=D.map(function(x){
    var rs=(byday[x.iso]||[]);
    var rows=rs.map(function(r){return rangeRow(x.iso,r.start==='24:00'?'':r.start,r.end==='24:00'?'':r.end)}).join('');
    return '<div style="border:1px solid rgba(17,24,39,.1);border-radius:12px;padding:12px 14px;margin-bottom:10px">'+
      '<div style="font-weight:800;margin-bottom:8px">'+x.name+'</div><div class="rows" data-day="'+x.iso+'">'+rows+'</div>'+
      '<button class="btn btn-s" style="padding:6px 12px;font-size:13px" onclick="addRange(\\''+x.iso+'\\')">+ Add time range</button></div>';
  }).join('');
}
function addRange(iso){
  var box=document.querySelector('.rows[data-day="'+iso+'"]');
  var tmp=document.createElement('div');tmp.innerHTML=rangeRow(iso,'','');box.appendChild(tmp.firstChild);
}
function load(){
  fetch('/api/availability?week_start='+document.getElementById('week').value).then(function(r){return r.json()}).then(function(d){
    var chn=(d.channels||[]).filter(function(c){return !d.allowed_channels.length||d.allowed_channels.indexOf(c.id)>=0}).map(function(c){return c.name});
    document.getElementById('chnote').innerHTML='You can be scheduled on: <b>'+(chn.join(', ')||'any channel')+'</b>';
    var byday={};(d.ranges||[]).forEach(function(r){(byday[r.date]=byday[r.date]||[]).push(r)});
    render(byday);
  });
}
document.getElementById('saveBtn').addEventListener('click',function(){
  var ranges=[];document.querySelectorAll('#dayList .rr').forEach(function(rr){
    var s=rr.querySelector('.rs').value,e=rr.querySelector('.re').value;
    if(s&&e&&e>s)ranges.push({date:rr.getAttribute('data-date'),start:s,end:e});
  });
  fetch('/api/availability',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({week_start:document.getElementById('week').value,ranges:ranges})})
    .then(function(r){return r.json()}).then(function(d){if(d.ok)toast('Submitted '+d.saved+' time ranges ✓');else toast('Check your times')});
});
document.getElementById('week').addEventListener('change',load);
load();
</script></body></html>'''


MYSCHEDULE_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>My Schedule</title>
__NAVBAR_CSS__
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#fff;color:#1a2130;min-height:100vh}
.page-hdr{padding:24px 28px 8px;max-width:720px;margin:0 auto}
.page-title{font-size:22px;font-weight:800}.page-title span{color:#4f46e5;margin-left:8px;font-weight:600;font-size:14px}
.wrap{max-width:720px;margin:0 auto;padding:8px 28px 40px}
.day-h{font-size:13px;font-weight:800;color:#6b7280;text-transform:uppercase;letter-spacing:.5px;margin:18px 0 8px}
.shift{display:flex;align-items:center;gap:14px;background:#fff;border:1px solid rgba(17,24,39,0.1);border-radius:14px;padding:14px 16px;margin-bottom:10px}
.shift .time{font-weight:800;font-size:16px;min-width:120px}
.shift .ch{flex:1}.shift .cn{font-weight:700}.shift .meta{font-size:12.5px;color:#6b7280;margin-top:2px}
.role{font-size:11px;font-weight:800;padding:3px 10px;border-radius:50px;background:rgba(79,70,229,.14);color:#4338ca}
.muted{color:#9ca3af;font-size:14px}
</style></head><body>
__NAVBAR__
<div class="page-hdr"><div class="page-title">🗓️ My Schedule <span>__NAME__</span></div></div>
<div class="wrap"><div id="list"><div class="muted">Loading…</div></div></div>
<script>
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
fetch('/api/my-schedule').then(function(r){return r.json()}).then(function(d){
  var el=document.getElementById('list');
  if(!d.shifts.length){el.innerHTML='<div class="muted">No upcoming shifts published yet. Check back after your manager approves the week.</div>';return}
  var byday={},order=[];
  d.shifts.forEach(function(s){if(!byday[s.shift_date]){byday[s.shift_date]=[];order.push(s.shift_date)}byday[s.shift_date].push(s)});
  el.innerHTML=order.map(function(dt){
    var d2=new Date(dt+'T00:00');var hdr=d2.toLocaleDateString(undefined,{weekday:'long',month:'short',day:'numeric'});
    return '<div class="day-h">'+hdr+'</div>'+byday[dt].map(function(s){
      return '<div class="shift"><div class="time">'+s.start_time+'–'+s.end_time+'</div>'+
        '<div class="ch"><div class="cn">'+esc(s.channel_name)+'</div><div class="meta">'+esc(s.platform||'')+' · with '+esc(s['with']||'—')+'</div></div>'+
        '<span class="role">'+esc(s.role_here)+'</span></div>';
    }).join('');
  }).join('');
});
</script></body></html>'''


AUDIT_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Audit log</title>
__NAVBAR_CSS__
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#fff;color:#1a2130;min-height:100vh}
.page-hdr{padding:24px 28px 8px;max-width:1000px;margin:0 auto}
.page-title{font-size:22px;font-weight:800}.page-title span{color:#4f46e5;margin-left:8px;font-weight:600;font-size:14px}
.wrap{max-width:1000px;margin:0 auto;padding:8px 28px 40px}
.card{background:#fff;border:1px solid rgba(17,24,39,0.096);border-radius:16px;padding:20px 22px}
.card h2{font-size:15px;font-weight:800;color:#4f46e5;text-transform:uppercase;letter-spacing:.6px;margin-bottom:12px}
table{width:100%;border-collapse:collapse}
th,td{padding:10px 8px;font-size:13px;border-bottom:1px solid rgba(17,24,39,0.08);text-align:left;vertical-align:top}
th{font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px}
.act{font-weight:700;color:#4338ca}
.muted{color:#9ca3af;font-size:13px}
input{background:#fff;border:2px solid rgba(17,24,39,0.128);border-radius:10px;padding:9px 12px;font-size:14px;font-family:inherit;outline:none}
</style></head><body>
__NAVBAR__
<div class="page-hdr"><div class="page-title">🧾 Audit log <span>__NAME__</span></div></div>
<div class="wrap">
<div class="card">
  <div style="margin-bottom:12px"><input id="q" placeholder="Filter by user, action…" style="width:280px"></div>
  <table><thead><tr><th>When</th><th>User</th><th>Role</th><th>Action</th><th>Details</th><th>IP</th></tr></thead>
  <tbody id="rows"><tr><td colspan="6" class="muted">Loading…</td></tr></tbody></table>
</div>
</div>
<script>
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
var ALL=[];
function render(){
  var q=(document.getElementById('q').value||'').toLowerCase();
  var rows=ALL.filter(function(e){return !q||((e.actor||'')+' '+(e.action||'')+' '+(e.detail||'')).toLowerCase().indexOf(q)>=0});
  document.getElementById('rows').innerHTML=rows.length?rows.map(function(e){
    return '<tr><td class="muted">'+esc((e.at||'').replace('T',' ').slice(0,19))+'</td><td>'+esc(e.actor||'')+'</td>'+
      '<td class="muted">'+esc(e.role||'')+'</td><td class="act">'+esc(e.action||'')+'</td><td>'+esc(e.detail||'')+'</td>'+
      '<td class="muted">'+esc(e.ip||'')+'</td></tr>';
  }).join(''):'<tr><td colspan="6" class="muted">No matching activity.</td></tr>';
}
document.getElementById('q').addEventListener('input',render);
fetch('/api/audit-log').then(function(r){return r.json()}).then(function(d){ALL=d.entries||[];render();});
</script></body></html>'''


STOCKTAKE_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Stock take</title>
__NAVBAR_CSS__
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#fff;color:#1a2130;min-height:100vh}
.page-hdr{padding:24px 28px 8px;max-width:760px;margin:0 auto}
.page-title{font-size:22px;font-weight:800}.page-title span{color:#4f46e5;margin-left:8px;font-weight:600;font-size:14px}
.wrap{max-width:760px;margin:0 auto;padding:8px 28px 40px}
.card{background:#fff;border:1px solid rgba(17,24,39,0.096);border-radius:16px;padding:22px 24px;margin-bottom:18px}
.card h2{font-size:15px;font-weight:800;color:#4f46e5;text-transform:uppercase;letter-spacing:.6px;margin-bottom:12px}
label{font-size:12px;font-weight:700;color:#6b7280;display:block;margin:8px 0 4px}
input[type=text],input[type=number]{background:#fff;border:2px solid rgba(17,24,39,0.128);border-radius:10px;padding:13px 15px;font-size:17px;color:#1a2130;font-family:inherit;outline:none;width:100%}
input:focus{border-color:#4f46e5}
.btn{border:none;border-radius:10px;padding:13px 22px;font-size:15px;font-weight:700;cursor:pointer;font-family:inherit}
.btn-p{background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff}
.prod{display:flex;align-items:center;gap:14px;margin-bottom:14px}
.prod img,.prod .ni{width:64px;height:64px;border-radius:12px;object-fit:cover;background:#eef0f4;flex:0 0 64px}
.prod .nm{font-weight:800;font-size:17px}.prod .sub{color:#6b7280;font-size:13px;margin-top:2px}
.var{font-size:15px;font-weight:800;margin:8px 0}
.var.up{color:#059669}.var.down{color:#e11d48}.var.zero{color:#6b7280}
table{width:100%;border-collapse:collapse;margin-top:6px}
th,td{padding:9px 8px;font-size:13px;border-bottom:1px solid rgba(17,24,39,0.08);text-align:left}
th{font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px}
.muted{color:#9ca3af;font-size:13px}.hide{display:none}
.toast{position:fixed;bottom:24px;right:24px;background:#10b981;color:#fff;padding:14px 22px;border-radius:10px;font-weight:600;z-index:100;display:none}
.toast.err{background:#f43f5e}
</style></head><body>
__NAVBAR__
<div class="page-hdr"><div class="page-title">🔢 Stock take <span>__NAME__</span></div></div>
<div class="wrap">
<div class="card">
  <label>Scan or type a barcode / SKU</label>
  <input type="text" id="scan" placeholder="Scan a product…" autocomplete="off" autofocus>
  <div id="panel" class="hide" style="margin-top:18px">
    <div class="prod"><img id="pi" alt=""><div><div class="nm" id="pn"></div><div class="sub" id="ps"></div></div></div>
    <label>Counted quantity (physically on the shelf)</label>
    <input type="number" id="counted" placeholder="0" inputmode="numeric">
    <div class="var zero" id="variance"></div>
    <button class="btn btn-p" id="applyBtn" style="width:100%;margin-top:8px">Apply count</button>
  </div>
</div>
<div class="card">
  <h2>Counted this session</h2>
  <table><thead><tr><th>SKU</th><th>Product</th><th>Was</th><th>Counted</th><th>Change</th></tr></thead>
  <tbody id="log"><tr><td colspan="5" class="muted">Nothing counted yet.</td></tr></tbody></table>
</div>
</div>
<div class="toast" id="t"></div>
<script>
function toast(m,e){var t=document.getElementById('t');t.textContent=m;t.className=e?'toast err':'toast';t.style.display='block';setTimeout(function(){t.style.display='none'},2600)}
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
var cur=null,logRows=[];
function lookup(code){
  fetch('/api/product/lookup/'+encodeURIComponent(code)).then(function(r){return r.json()}).then(function(d){
    if(!d.ok){toast('Not found: '+code,true);return}
    cur=d.product;
    document.getElementById('pn').textContent=(cur.name||cur.sku)+(cur.variant_name?(' · '+cur.variant_name):'');
    document.getElementById('ps').textContent='SKU '+cur.sku+' · recorded on hand: '+(cur.on_hand!=null?cur.on_hand:'—');
    document.getElementById('pi').src=cur.image_url||'data:image/svg+xml;utf8,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><rect width="64" height="64" fill="#eef0f4"/><text x="32" y="40" font-size="20" text-anchor="middle">📦</text></svg>');
    document.getElementById('panel').classList.remove('hide');
    var ci=document.getElementById('counted');ci.value='';document.getElementById('variance').textContent='';ci.focus();
  });
}
document.getElementById('scan').addEventListener('keydown',function(e){if(e.key==='Enter'){var v=this.value.trim();if(v){lookup(v);this.value=''}}});
document.getElementById('counted').addEventListener('input',function(){
  if(!cur)return;var c=parseInt(this.value||'0');var d=c-(cur.on_hand||0);
  var el=document.getElementById('variance');
  el.className='var '+(d>0?'up':d<0?'down':'zero');
  el.textContent=(this.value==='')?'':(d===0?'✓ Matches the system':((d>0?'+':'')+d+' vs system ('+(cur.on_hand||0)+')'));
});
document.getElementById('applyBtn').addEventListener('click',function(){
  if(!cur)return;var c=document.getElementById('counted').value;if(c===''){toast('Enter a count',true);return}
  fetch('/api/product/'+encodeURIComponent(cur.sku)+'/count',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({counted:parseInt(c)})})
    .then(function(r){return r.json()}).then(function(d){
      if(!d.ok){toast(d.error||'Failed',true);return}
      logRows.unshift({sku:cur.sku,name:cur.name||cur.sku,old:d.old,counted:d.counted,delta:d.delta});
      renderLog();toast('Counted ✓');document.getElementById('panel').classList.add('hide');cur=null;document.getElementById('scan').focus();
    });
});
function renderLog(){
  var el=document.getElementById('log');
  if(!logRows.length){el.innerHTML='<tr><td colspan="5" class="muted">Nothing counted yet.</td></tr>';return}
  el.innerHTML=logRows.map(function(r){
    var ch=r.delta>0?'<span style="color:#059669">+'+r.delta+'</span>':(r.delta<0?'<span style="color:#e11d48">'+r.delta+'</span>':'<span class="muted">0</span>');
    return '<tr><td class="muted">'+esc(r.sku)+'</td><td>'+esc(r.name)+'</td><td>'+r.old+'</td><td><b>'+r.counted+'</b></td><td>'+ch+'</td></tr>';
  }).join('');
}
</script></body></html>'''


PURCHASING_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Purchasing</title>
__NAVBAR_CSS__
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#fff;color:#1a2130;min-height:100vh}
.page-hdr{padding:24px 28px 8px;max-width:1040px;margin:0 auto;display:flex;justify-content:space-between;align-items:center}
.page-title{font-size:22px;font-weight:800}.page-title span{color:#4f46e5;margin-left:8px;font-weight:600;font-size:14px}
.wrap{max-width:1040px;margin:0 auto;padding:8px 28px 60px}
.card{background:#fff;border:1px solid rgba(17,24,39,0.096);border-radius:16px;padding:20px 22px;margin-bottom:18px}
.card h2{font-size:15px;font-weight:800;color:#4f46e5;text-transform:uppercase;letter-spacing:.6px;margin-bottom:14px}
label{font-size:12px;font-weight:700;color:#6b7280;display:block;margin:10px 0 4px}
input[type=text],input[type=number],input[type=date],select{background:#fff;border:2px solid rgba(17,24,39,0.128);border-radius:10px;padding:10px 13px;font-size:14px;color:#1a2130;font-family:inherit;outline:none;width:100%}
input:focus,select:focus{border-color:#4f46e5}
.row{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}
.btn{border:none;border-radius:10px;padding:11px 18px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit}
.btn-p{background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff}
.btn-s{background:#f6f7f9;color:#1a2130;border:1px solid rgba(17,24,39,0.12)}
.btn-g{background:rgba(52,211,153,.16);color:#059669}
.btn-d{background:rgba(244,63,94,.12);color:#e11d48}
table{width:100%;border-collapse:collapse}
th,td{padding:11px 8px;font-size:13px;border-bottom:1px solid rgba(17,24,39,0.08);text-align:left}
th{font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px}
tr.click{cursor:pointer}tr.click:hover td{background:#f9fafb}
.pill{font-size:11px;font-weight:700;padding:3px 10px;border-radius:50px;white-space:nowrap}
.s-open{background:rgba(148,163,184,.2);color:#475569}.s-ordered{background:rgba(79,70,229,.14);color:#4338ca}
.s-in_transit{background:rgba(14,165,233,.16);color:#0369a1}.s-receiving{background:rgba(251,191,36,.18);color:#b45309}
.s-received{background:rgba(52,211,153,.16);color:#059669}
.linerow{display:grid;grid-template-columns:1fr 120px 90px 110px 34px;gap:8px;align-items:center;margin-bottom:8px}
.linerow.nocost{grid-template-columns:1fr 120px 90px 34px}
.muted{color:#9ca3af;font-size:13px}.hide{display:none}
.backlink{color:#4f46e5;font-weight:700;font-size:13px;cursor:pointer;display:inline-block;margin-bottom:12px}
.rcv{display:flex;align-items:center;gap:14px;padding:14px 10px;border-bottom:1px solid rgba(17,24,39,0.08)}
.rcv img,.rcv .noimg{width:52px;height:52px;border-radius:10px;object-fit:cover;background:#eef0f4;flex:0 0 52px}
.rcv .info{flex:1}.rcv .nm{font-weight:700;font-size:15px}.rcv .sub{font-size:12px;color:#6b7280;margin-top:2px}
.rcv .qbox{display:flex;align-items:center;gap:8px}
.rcv input{width:70px;text-align:center}
.done{background:#ecfdf5}
.toast{position:fixed;bottom:24px;right:24px;background:#10b981;color:#fff;padding:14px 22px;border-radius:10px;font-weight:600;z-index:100;display:none}
.toast.err{background:#f43f5e}
.filebtn{display:inline-block}
</style></head><body>
__NAVBAR__
<div class="page-hdr"><div class="page-title">📥 Purchasing <span>__NAME__</span></div>
  <button class="btn btn-p" id="newBtn">+ New order</button></div>
<div class="wrap">
<datalist id="prodList"></datalist>

<div id="listView">
  <div class="card">
    <h2>Purchase orders</h2>
    <table><thead><tr><th>PO</th><th>Supplier</th><th>Items</th><th>Tracking</th><th>Status</th><th>Created</th></tr></thead>
    <tbody id="poRows"><tr><td colspan="6" class="muted">Loading…</td></tr></tbody></table>
  </div>
</div>

<div id="editView" class="hide">
  <span class="backlink" onclick="showList()">← Back to orders</span>
  <div class="card">
    <h2 id="editTitle">New purchase order</h2>
    <input type="hidden" id="poId">
    <div class="row">
      <div><label>Supplier</label><input type="text" id="supplier" placeholder="e.g. GlowCo"></div>
      <div><label>Tracking number (if you have it)</label><input type="text" id="tracking" placeholder="Enter, or generate a label below"></div>
      <div><label>Carrier</label><input type="text" id="carrier" placeholder="UPS / USPS / DHL"></div>
    </div>
    <div class="row">
      <div><label>Expected date</label><input type="date" id="expected_at"></div>
      <div style="grid-column:span 2"><label>Notes</label><input type="text" id="notes" placeholder="Optional"></div>
    </div>

    <label style="margin-top:18px">Invoice (optional)</label>
    <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
      <input type="file" id="invFile" accept="image/*,.pdf" style="display:none">
      <button class="btn btn-s" id="invBtn">📎 Attach invoice</button>
      <button class="btn btn-s" id="extractBtn">✨ Extract items from photo</button>
      <span class="muted" id="invName"></span>
    </div>
    <div class="muted" style="font-size:12px;margin-top:4px">Photo of an invoice → we suggest the line items for you to review. PDFs attach for reference.</div>

    <h2 style="margin-top:22px">Items to receive</h2>
    <div class="linerow" id="lineHead"><div class="muted">Product</div><div class="muted">SKU</div><div class="muted">Qty</div><div class="muted costcol">Unit cost</div><div></div></div>
    <div id="lines"></div>
    <button class="btn btn-s" id="addLine" style="margin-top:6px">+ Add item</button>

    <div style="margin-top:20px;display:flex;gap:10px;flex-wrap:wrap">
      <button class="btn btn-p" id="saveBtn">Save order</button>
      <button class="btn btn-g" id="genLabelBtn">🏷️ Generate inbound label</button>
      <span class="muted" id="editResult"></span>
    </div>
  </div>
</div>

<div id="recvView" class="hide">
  <span class="backlink" onclick="showList()">← Back to orders</span>
  <div class="card" id="recvCard"></div>
</div>

</div>
<div class="toast" id="t"></div>
<script>
var ROLE='__ROLE__';var isAdmin=ROLE==='admin';
function toast(m,e){var t=document.getElementById('t');t.textContent=m;t.className=e?'toast err':'toast';t.style.display='block';setTimeout(function(){t.style.display='none'},3200)}
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function gv(id){return (document.getElementById(id).value||'').trim()}
function money(v){return v==null?'—':'$'+Number(v).toFixed(2)}
function stpill(s){return '<span class="pill s-'+esc(s)+'">'+esc(s).replace('_',' ')+'</span>'}
if(!isAdmin){document.querySelectorAll('.costcol').forEach(function(e){e.style.display='none'})}
// product autocomplete
fetch('/api/products').then(function(r){return r.json()}).then(function(rows){
  document.getElementById('prodList').innerHTML=(rows||[]).map(function(p){return '<option value="'+esc(p.name||'')+'" data-sku="'+esc(p.sku)+'">'}).join('');
});
function show(v){['listView','editView','recvView'].forEach(function(x){document.getElementById(x).classList.add('hide')});document.getElementById(v).classList.remove('hide');window.scrollTo(0,0)}
function showList(){show('listView');loadPOs()}
function loadPOs(){
  fetch('/api/po').then(function(r){return r.json()}).then(function(rows){
    var el=document.getElementById('poRows');
    if(!rows.length){el.innerHTML='<tr><td colspan="6" class="muted">No orders yet. Create one to start.</td></tr>';return}
    el.innerHTML=rows.map(function(p){
      var items=(p.items||[]).length;
      return '<tr class="click" onclick="openPO('+p.id+',\\''+esc(p.status)+'\\')"><td><b>#'+p.id+'</b></td><td>'+esc(p.supplier||'—')+'</td>'+
        '<td>'+items+'</td><td class="muted">'+esc(p.tracking||'—')+'</td><td>'+stpill(p.status)+'</td>'+
        '<td class="muted">'+esc((p.created_at||'').replace('T',' ').slice(0,16))+'</td></tr>';
    }).join('');
  });
}
function openPO(id,status){
  // Always open the receive screen — you can receive from any status.
  // (Edit the order via the "Edit order" button there.)
  openReceive(id);
}
// ── line rows ──
function lineRow(it){
  it=it||{};
  var cost=isAdmin?'<input type="number" step="0.01" class="l-cost" placeholder="0.00" value="'+(it.unit_cost!=null?it.unit_cost:'')+'">':'';
  var div=document.createElement('div');div.className='linerow'+(isAdmin?'':' nocost');
  div.innerHTML='<input type="text" class="l-name" list="prodList" placeholder="Product name" value="'+esc(it.product_name||it.name||'')+'" oninput="skuFromName(this)">'+
    '<input type="text" class="l-sku" placeholder="auto" value="'+esc(it.sku||'')+'">'+
    '<input type="number" class="l-qty" placeholder="0" value="'+(it.qty_ordered!=null?it.qty_ordered:(it.qty!=null?it.qty:''))+'">'+
    cost+'<button class="btn btn-d" style="padding:6px 10px" onclick="this.parentNode.remove()">✕</button>';
  return div;
}
function skuFromName(inp){
  var opt=document.querySelector('#prodList option[value="'+inp.value.replace(/"/g,'')+'"]');
  if(opt){var sku=opt.getAttribute('data-sku');var row=inp.parentNode.querySelector('.l-sku');if(row&&!row.value)row.value=sku}
}
function addLine(it){document.getElementById('lines').appendChild(lineRow(it))}
function collectLines(){
  return Array.prototype.map.call(document.querySelectorAll('#lines .linerow'),function(r){
    return {name:(r.querySelector('.l-name').value||'').trim(),sku:(r.querySelector('.l-sku').value||'').trim(),
      qty:parseInt(r.querySelector('.l-qty').value||'0'),unit_cost:isAdmin?parseFloat((r.querySelector('.l-cost').value||'0')):0};
  }).filter(function(l){return l.name||l.sku});
}
function newPO(){
  document.getElementById('poId').value='';document.getElementById('editTitle').textContent='New purchase order';
  ['supplier','tracking','carrier','expected_at','notes'].forEach(function(id){document.getElementById(id).value=''});
  document.getElementById('invName').textContent='';document.getElementById('editResult').textContent='';
  document.getElementById('lines').innerHTML='';addLine();addLine();show('editView');
}
function editPO(id){
  fetch('/api/po/'+id+'/detail').then(function(r){return r.json()}).then(function(d){
    if(!d.ok)return;var p=d.po;
    document.getElementById('poId').value=p.id;document.getElementById('editTitle').textContent='Edit PO #'+p.id;
    document.getElementById('supplier').value=p.supplier||'';document.getElementById('tracking').value=p.tracking||'';
    document.getElementById('carrier').value=p.carrier||'';document.getElementById('expected_at').value=(p.expected_at||'').slice(0,10);
    document.getElementById('notes').value=p.notes||'';document.getElementById('invName').textContent=p.invoice_name||'';
    document.getElementById('lines').innerHTML='';(p.items||[]).forEach(addLine);if(!p.items||!p.items.length){addLine()}
    document.getElementById('editResult').textContent='';show('editView');
  });
}
function savePO(cb){
  var body={supplier:gv('supplier'),tracking:gv('tracking'),carrier:gv('carrier'),expected_at:gv('expected_at'),
    notes:gv('notes'),items:collectLines()};
  var id=gv('poId');var url=id?('/api/po/'+id):'/api/po';
  fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
    .then(function(r){return r.json()}).then(function(d){
      if(!d.ok){toast(d.error||'Failed',true);return}
      var pid=d.po_id||id;document.getElementById('poId').value=pid;
      toast('Saved ✓');if(cb)cb(pid);else{document.getElementById('editResult').textContent='Saved PO #'+pid;}
    });
}
document.getElementById('newBtn').addEventListener('click',newPO);
document.getElementById('addLine').addEventListener('click',function(){addLine()});
document.getElementById('saveBtn').addEventListener('click',function(){savePO()});
// invoice attach (needs a saved PO)
document.getElementById('invBtn').addEventListener('click',function(){document.getElementById('invFile').click()});
document.getElementById('invFile').addEventListener('change',function(){
  var f=this.files&&this.files[0];if(!f)return;var self=this;
  function up(pid){var fd=new FormData();fd.append('file',f);
    fetch('/api/po/'+pid+'/invoice',{method:'POST',body:fd}).then(function(r){return r.json()}).then(function(d){
      if(d.ok){document.getElementById('invName').textContent='📎 '+d.invoice_name;toast('Invoice attached')}else toast(d.error||'Failed',true)});}
  if(gv('poId'))up(gv('poId'));else savePO(up);
});
// extract items from an invoice photo
document.getElementById('extractBtn').addEventListener('click',function(){
  var inp=document.createElement('input');inp.type='file';inp.accept='image/*';
  inp.onchange=function(){var f=inp.files[0];if(!f)return;var fd=new FormData();fd.append('file',f);
    document.getElementById('editResult').textContent='Reading invoice…';
    fetch('/api/po/extract-invoice',{method:'POST',body:fd}).then(function(r){return r.json()}).then(function(d){
      if(!d.ok){document.getElementById('editResult').textContent='';toast(d.error||'Failed',true);return}
      document.getElementById('lines').innerHTML='';(d.items||[]).forEach(addLine);if(!d.items.length)addLine();
      document.getElementById('editResult').textContent='✨ Added '+(d.items||[]).length+' items — review before saving.';toast('Extracted ✓')});};
  inp.click();
});
document.getElementById('genLabelBtn').addEventListener('click',function(){
  savePO(function(pid){window.location.href='/admin/inbound';});
});
// ── receive view ──
function openReceive(id){
  fetch('/api/po/'+id+'/detail').then(function(r){return r.json()}).then(function(d){
    if(!d.ok)return;var p=d.po;
    var rows=(p.items||[]).map(function(it){
      var remaining=(it.qty_ordered||0)-(it.qty_received||0);
      var img=it.image_url?'<img src="'+esc(it.image_url)+'">':'<div class="noimg"></div>';
      var doneCls=remaining<=0?' done':'';
      var ctrl=remaining<=0?'<span class="pill s-received">✓ received</span>':
        '<div class="qbox"><input type="number" id="q'+it.id+'" value="'+remaining+'" min="1" max="'+remaining+'"><button class="btn btn-g" onclick="recvLine('+p.id+','+it.id+')">Receive</button></div>';
      return '<div class="rcv'+doneCls+'">'+img+'<div class="info"><div class="nm">'+esc(it.product_name||it.sku)+'</div>'+
        '<div class="sub">SKU '+esc(it.sku)+' · ordered '+(it.qty_ordered||0)+' · received '+(it.qty_received||0)+' · on hand '+(it.on_hand!=null?it.on_hand:'—')+
        ' &nbsp;<a href="/admin/inventory" style="color:#4f46e5">edit product ›</a></div></div>'+ctrl+'</div>';
    }).join('');
    document.getElementById('recvCard').innerHTML='<h2>Receive PO #'+p.id+' '+stpill(p.status)+'</h2>'+
      '<div class="muted" style="margin-bottom:12px">'+esc(p.supplier||'')+(p.tracking?(' · '+esc(p.tracking)):'')+'</div>'+
      '<div style="margin-bottom:14px;display:flex;gap:10px;flex-wrap:wrap">'+
      '<a class="btn btn-s" href="/api/po/'+p.id+'/slip.pdf" target="_blank" style="text-decoration:none">🖨️ Print receiving slip</a>'+
      (p.invoice_name?('<a class="btn btn-s" href="/api/po/'+p.id+'/invoice-file" target="_blank" style="text-decoration:none">📎 Invoice</a>'):'')+
      (p.status!=='received'?('<button class="btn btn-s" onclick="editPO('+p.id+')">✎ Edit order</button>'):'')+
      '<button class="btn btn-g" onclick="receiveAll('+p.id+')">✓ Receive all remaining</button>'+'</div>'+
      '<div style="margin-bottom:14px"><label>📷 Scan to receive (1 unit each)</label>'+
      '<input type="text" id="scanBox" placeholder="Scan barcode or SKU…" style="width:100%" autocomplete="off" '+
      'onkeydown="if(event.key===\\'Enter\\'){scanRecv('+p.id+')}"></div>'+
      rows;
    show('recvView');
    var sb=document.getElementById('scanBox');if(sb)sb.focus();
  });
}
function recvLine(poid,itemId){
  var q=parseInt((document.getElementById('q'+itemId)||{}).value||'0');
  fetch('/api/po/'+poid+'/item/'+itemId+'/receive',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({qty:q})})
    .then(function(r){return r.json()}).then(function(d){if(d.ok){toast('Received ✓');openReceive(poid)}else toast(d.error||'Failed',true)});
}
function receiveAll(poid){
  if(!confirm('Receive all remaining items into inventory?'))return;
  fetch('/api/po/'+poid+'/receive',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})})
    .then(function(r){return r.json()}).then(function(d){if(d.ok){toast('Received all ✓');openReceive(poid)}else toast(d.error||'Failed',true)});
}
function scanRecv(poid){
  var box=document.getElementById('scanBox');var code=(box.value||'').trim();if(!code)return;box.value='';
  fetch('/api/po/'+poid+'/scan-receive',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:code})})
    .then(function(r){return r.json()}).then(function(d){
      if(d.ok){toast('✓ '+esc(d.name)+' ('+d.qty_received+'/'+d.qty_ordered+')');openReceive(poid)}
      else{toast(d.error||'No match',true);var b=document.getElementById('scanBox');if(b)b.focus()}});
}
loadPOs();
</script></body></html>'''


PROFIT_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Profit</title>
__NAVBAR_CSS__
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#ffffff;color:#1a2130;min-height:100vh}
.page-hdr{padding:24px 28px 8px;max-width:1300px;margin:0 auto;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px}
.page-title{font-size:22px;font-weight:800}.page-title span{color:#4f46e5;margin-left:8px;font-weight:600;font-size:14px}
.wrap{max-width:1300px;margin:0 auto;padding:8px 28px 40px}
select{background:#ffffff;border:2px solid rgba(17,24,39,0.128);border-radius:10px;padding:10px 14px;font-size:14px;color:#1a2130;font-family:inherit;outline:none;min-width:240px}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:18px 0}
@media(max-width:760px){.cards{grid-template-columns:repeat(2,1fr)}}
.kpi{background:#ffffff;border:1px solid rgba(17,24,39,0.096);border-radius:14px;padding:18px}
.kpi .l{font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px;font-weight:700;margin-bottom:6px}
.kpi .v{font-size:30px;font-weight:900}
.kpi.rev .v{color:#2563eb}.kpi.cogs .v{color:#b45309}.kpi.profit .v{color:#059669}.kpi.profit.neg .v{color:#f43f5e}.kpi.margin .v{color:#4f46e5}
table{width:100%;border-collapse:collapse;background:#ffffff;border-radius:12px;overflow:hidden}
th,td{padding:11px 13px;font-size:13px;border-bottom:1px solid rgba(17,24,39,0.096);text-align:right}
th:first-child,td:first-child,th:nth-child(2),td:nth-child(2){text-align:left}
th{font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px}
.sku{font-family:monospace;color:#4f46e5;font-weight:700}.pos{color:#059669}.neg{color:#f43f5e}
.warn{background:rgba(251,191,36,.1);border:1px solid rgba(251,191,36,.3);color:#b45309;padding:10px 14px;border-radius:10px;margin-bottom:16px;font-size:13px}
.nocost{color:#b45309}
</style></head><body>
__NAVBAR__
<div class="page-hdr"><div class="page-title">💰 Profit <span>__NAME__</span></div>
<select id="showSel"><option value="">All shows</option></select></div>
<div class="wrap">
<div id="notice"></div>
<div class="cards" id="cards"></div>
<table><thead><tr><th>Product</th><th>Stickers</th><th>Qty sold</th><th>Revenue</th><th>Avg cost</th><th>COGS</th><th>Profit</th></tr></thead>
<tbody id="rows"><tr><td colspan="7">Loading…</td></tr></tbody></table>
</div>
<script>
function money(v){return v==null?'—':'$'+Number(v).toFixed(2)}
function esc(s){var d=document.createElement('div');d.textContent=(s==null?'':String(s));return d.innerHTML}
fetch('/api/shows').then(function(r){return r.json()}).then(function(shows){
  var sel=document.getElementById('showSel');
  shows.forEach(function(s){var o=document.createElement('option');o.value=s.name;o.textContent=s.name;sel.appendChild(o)});
});
function load(){
  var show=document.getElementById('showSel').value;
  fetch('/api/profit'+(show?('?show='+encodeURIComponent(show)):'')).then(function(r){return r.json()}).then(function(d){
    document.getElementById('notice').innerHTML=d.unmapped_lines?('<div class="warn">⚠️ '+d.unmapped_lines+' sold sticker groups are not yet linked to a real product — their cost is unknown, so profit is overstated. Link them on the 🔗 Pre-Show Scan screen for this show.</div>'):'';
    var profCls=d.profit<0?'profit neg':'profit';
    document.getElementById('cards').innerHTML=
      '<div class="kpi rev"><div class="l">Revenue</div><div class="v">'+money(d.revenue)+'</div></div>'+
      '<div class="kpi cogs"><div class="l">COGS (cost of goods)</div><div class="v">'+money(d.cogs)+'</div></div>'+
      '<div class="kpi '+profCls+'"><div class="l">Profit</div><div class="v">'+money(d.profit)+'</div></div>'+
      '<div class="kpi margin"><div class="l">Margin</div><div class="v">'+(d.margin||0)+'%</div></div>';
    var rows=d.lines||[];
    if(!rows.length){document.getElementById('rows').innerHTML='<tr><td colspan="7">No sales for this show</td></tr>';return}
    document.getElementById('rows').innerHTML=rows.map(function(l){
      var pc=l.profit<0?'neg':'pos';
      var cost=l.mapped?money(l.avg_cost):'<span class="nocost">not linked</span>';
      var nm=l.mapped?(esc(l.name||'')+' <span class="sku">'+esc(l.product_sku||'')+'</span>'):'<span class="nocost">⚠ '+esc(l.name||'unlinked')+'</span>';
      var st=(l.stickers||[]).join(', ');
      return '<tr><td>'+nm+'</td><td class="sku">'+esc(st)+'</td><td>'+l.qty+'</td>'+
        '<td>'+money(l.revenue)+'</td><td>'+cost+'</td><td>'+money(l.cogs)+'</td><td class="'+pc+'">'+money(l.profit)+'</td></tr>';
    }).join('');
  });
}
document.getElementById('showSel').addEventListener('change',load);
load();
</script></body></html>'''


# ── HOST ANALYTICS — seller performance per show + configurable commissions ──
HOSTS_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Host Analytics</title>
__NAVBAR_CSS__
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#ffffff;color:#1a2130;min-height:100vh}
.page-hdr{padding:24px 28px 8px;max-width:1300px;margin:0 auto;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px}
.page-title{font-size:22px;font-weight:800}.page-title span{color:#4f46e5;margin-left:8px;font-weight:600;font-size:14px}
.wrap{max-width:1300px;margin:0 auto;padding:8px 28px 40px}
.card{background:#ffffff;border:1px solid rgba(17,24,39,0.096);border-radius:16px;padding:18px 20px;margin-bottom:18px}
.card h2{font-size:13px;font-weight:800;color:#4f46e5;text-transform:uppercase;letter-spacing:.6px;margin-bottom:14px}
select,input{background:#ffffff;border:2px solid rgba(17,24,39,0.128);border-radius:10px;padding:10px 13px;font-size:14px;color:#1a2130;font-family:inherit;outline:none}
select:focus,input:focus{border-color:#4f46e5}
label{display:block;font-size:11px;font-weight:700;color:#6b7280;margin-bottom:5px;text-transform:uppercase;letter-spacing:.4px}
.row{display:flex;gap:12px;align-items:end;flex-wrap:wrap}
.btn{border:none;border-radius:10px;padding:11px 20px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit}
.btn-p{background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff}.btn-s{background:rgba(17,24,39,0.128);color:#1a2130;border:1px solid rgba(17,24,39,0.16)}
.btn-x{background:rgba(244,63,94,.14);color:#e11d48;border:1px solid rgba(244,63,94,.3);border-radius:8px;padding:6px 10px;font-size:12px;cursor:pointer}
.cards{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin:6px 0 4px}
@media(max-width:860px){.cards{grid-template-columns:repeat(2,1fr)}}
.kpi{background:#ffffff;border:1px solid rgba(17,24,39,0.096);border-radius:14px;padding:16px}
.kpi .l{font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px;font-weight:700;margin-bottom:6px}
.kpi .v{font-size:26px;font-weight:900}
.kpi.rev .v{color:#2563eb}.kpi.comm .v{color:#b45309}.kpi.units .v{color:#4f46e5}.kpi.shows .v{color:#059669}.kpi.aov .v{color:#1a2130}
table{width:100%;border-collapse:collapse;background:#ffffff;border-radius:12px;overflow:hidden}
th,td{padding:10px 12px;font-size:13px;border-bottom:1px solid rgba(17,24,39,0.096);text-align:right}
th:first-child,td:first-child,th:nth-child(2),td:nth-child(2),th:nth-child(3),td:nth-child(3){text-align:left}
th{font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px}
.host-in{width:120px;padding:6px 8px;font-size:13px}
.comm{color:#b45309;font-weight:700}.rev{color:#2563eb;font-weight:700}
.chart-wrap{overflow-x:auto}
.modal{position:fixed;inset:0;background:rgba(0,0,0,.7);display:none;align-items:flex-start;justify-content:center;z-index:200;padding:30px 16px;overflow:auto}
.modal.on{display:flex}
.modal .box{background:#f6f7f9;border:1px solid rgba(17,24,39,0.16);border-radius:16px;padding:22px;max-width:820px;width:100%}
.modal h3{font-size:17px;font-weight:800;margin-bottom:4px}
.mini{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:14px 0}
@media(max-width:680px){.mini{grid-template-columns:repeat(2,1fr)}}
.mini .m{background:rgba(17,24,39,0.048);border:1px solid rgba(17,24,39,0.096);border-radius:10px;padding:12px}
.mini .m .l{font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px;font-weight:700}
.mini .m .v{font-size:19px;font-weight:800;margin-top:3px}
.geo{display:flex;gap:20px;flex-wrap:wrap;margin-top:6px}
.geo .col{flex:1;min-width:180px}
.geo .b{display:flex;justify-content:space-between;font-size:13px;padding:4px 0;border-bottom:1px solid rgba(17,24,39,0.08)}
.bar{fill:#4f46e5}.bar:hover{fill:#7c3aed}
.axis{stroke:rgba(17,24,39,0.16)}.axtx{fill:#6b7280;font-size:10px}
.tier-row{display:flex;gap:8px;align-items:center;margin-bottom:8px}
.muted{color:#6b7280;font-size:13px}
.toast{position:fixed;bottom:24px;right:24px;background:#10b981;color:#fff;padding:14px 22px;border-radius:10px;font-weight:700;z-index:100;display:none}.toast.err{background:#f43f5e}
</style></head><body>
__NAVBAR__
<div class="page-hdr"><div class="page-title">🎤 Host Analytics <span>__NAME__</span></div>
  <div class="row"><div><label>Host</label><select id="hostSel"><option value="">All hosts</option></select></div></div>
</div>
<div class="wrap">

<div class="card">
  <h2>💸 Commission rule</h2>
  <div class="row">
    <div><label>Model</label><select id="cMode">
      <option value="flat">Flat % of net sales</option>
      <option value="tiered">Tiered by sales volume</option>
      <option value="base_pct">% only (hourly base later)</option>
    </select></div>
    <div id="flatBox"><label>Flat %</label><input id="cFlat" type="number" step="0.1" style="width:100px"></div>
    <div id="pctBox" style="display:none"><label>%</label><input id="cPct" type="number" step="0.1" style="width:100px"></div>
    <button class="btn btn-p" id="saveCfg">Save rule</button>
  </div>
  <div id="tierBox" style="display:none;margin-top:14px">
    <label>Tiers — rate applies to whole show once its sales reach the threshold</label>
    <div id="tiers"></div>
    <button class="btn btn-s" id="addTier" style="margin-top:6px">+ Add tier</button>
  </div>
  <div class="muted" style="margin-top:10px">Commissions are computed on <b>net sales</b> (after cancellations), from the uploaded show CSVs.</div>
</div>

<div class="cards" id="kpis"></div>

<div class="card">
  <h2>📈 Revenue per show <span id="chartHost" class="muted"></span></h2>
  <div class="chart-wrap"><div id="chart"></div></div>
</div>

<div class="card">
  <h2>🗂️ Shows</h2>
  <table><thead><tr><th>Date</th><th>Show</th><th>Host</th><th>Net sales</th><th>Shipping</th><th>Gross</th><th>Orders</th><th>Units</th><th>AOV</th><th>Cancel%</th><th>Commission</th></tr></thead>
  <tbody id="rows"><tr><td colspan="9" class="muted">Loading…</td></tr></tbody></table>
</div>
</div>
<div class="modal" id="showModal"><div class="box" id="showBox"></div></div>
<div class="toast" id="t"></div>
<script>
function toast(m,e){var x=document.getElementById('t');x.textContent=m;x.className=e?'toast err':'toast';x.style.display='block';setTimeout(function(){x.style.display='none'},2500)}
function esc(s){var d=document.createElement('div');d.textContent=(s==null?'':String(s));return d.innerHTML}
function money(v){return '$'+Number(v||0).toLocaleString(undefined,{maximumFractionDigits:0})}
function money2(v){return '$'+Number(v||0).toFixed(2)}
function secFmt(s){s=Number(s||0);if(!s)return '—';if(s<60)return s.toFixed(0)+'s';return Math.floor(s/60)+'m '+Math.round(s%60)+'s'}
var DATA={shows:[],hosts:[],config:{}};

function closeShow(){document.getElementById('showModal').classList.remove('on')}
function openShow(gi){
  var s=DATA.shows[gi];if(!s)return;
  document.getElementById('showModal').classList.add('on');
  document.getElementById('showBox').innerHTML='<div class="muted">Loading '+esc(s.label)+'…</div>';
  fetch('/api/show-detail?label='+encodeURIComponent(s.label)).then(function(r){return r.json()}).then(function(d){
    if(!d.ok){document.getElementById('showBox').innerHTML='<div class="muted">Failed</div>';return}
    var dur=d.duration_min?( (d.duration_min/60).toFixed(1)+'h' ):'—';
    var win=d.has_times?('🕒 '+esc(d.start||'')+' → '+esc(d.end||'')+' · '+dur):'🕒 no sale-time data (older import)';
    var h='<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px"><div><h3>'+esc(d.label)+'</h3><div class="muted">🎤 '+esc(d.host)+' · '+win+'</div></div><button class="btn btn-s" onclick="closeShow()">Close</button></div>';
    h+='<div class="mini">'+
      '<div class="m"><div class="l">Net sales (products)</div><div class="v rev">'+money(d.revenue)+'</div></div>'+
      '<div class="m"><div class="l">Shipping collected</div><div class="v" style="color:#b45309">'+money(d.shipping||0)+'</div></div>'+
      '<div class="m"><div class="l">Units</div><div class="v">'+d.units.toLocaleString()+'</div></div>'+
      '<div class="m"><div class="l">Orders</div><div class="v">'+d.orders.toLocaleString()+'</div></div>'+
      '<div class="m"><div class="l">Giveaways</div><div class="v">'+d.giveaways+'</div></div>'+
      '<div class="m"><div class="l">Cancellations</div><div class="v">'+d.cancel_units+' ('+d.cancel_rate+'%)</div></div>'+
      '<div class="m"><div class="l">Show length</div><div class="v">'+dur+'</div></div>'+
      '<div class="m"><div class="l">Sales / live hr</div><div class="v">'+(d.rev_per_hour_live?money(d.rev_per_hour_live):'—')+'</div></div>'+
      '<div class="m"><div class="l">Avg pack time</div><div class="v">'+secFmt(d.avg_pack_sec)+'</div></div>';
    h+='</div>';
    if(d.hours&&d.hours.length){h+='<div style="margin:8px 0 4px;font-size:12px;font-weight:700;color:#4f46e5;text-transform:uppercase;letter-spacing:.5px">Sales by hour of day</div><div class="chart-wrap">'+hourChart(d.hours)+'</div>';}
    h+='<div class="geo">';
    h+='<div class="col"><div style="font-size:12px;font-weight:700;color:#4f46e5;text-transform:uppercase;margin-bottom:4px">Top states</div>'+
       (d.top_states.length?d.top_states.map(function(x){return '<div class="b"><span>'+esc(x.k)+'</span><span class="muted">'+x.v+' units</span></div>'}).join(''):'<div class="muted">No state data (older import)</div>')+'</div>';
    h+='<div class="col"><div style="font-size:12px;font-weight:700;color:#4f46e5;text-transform:uppercase;margin-bottom:4px">Top products</div>'+
       d.top_products.slice(0,6).map(function(p){return '<div class="b"><span>'+esc(p.name)+'</span><span class="muted">'+money(p.revenue)+'</span></div>'}).join('')+'</div>';
    h+='</div>';
    document.getElementById('showBox').innerHTML=h;
  });
}
function hourChart(hrs){
  var byh={};hrs.forEach(function(x){byh[x.hour]=x});
  var W=720,H=170,top=10,bot=26,n=24,bw=(W-30)/n;
  var max=Math.max.apply(null,hrs.map(function(x){return x.revenue}))||1;
  var bars='',lbls='';
  for(var hh=0;hh<24;hh++){var v=byh[hh]?byh[hh].revenue:0;var bh=Math.round((H-top-bot)*(v/max));
    var x=28+hh*bw,y=H-bot-bh;
    bars+='<rect class="bar" x="'+(x+1)+'" y="'+y+'" width="'+(bw-2)+'" height="'+Math.max(1,bh)+'" rx="2"><title>'+hh+':00 — '+money(v)+' ('+(byh[hh]?byh[hh].units:0)+' units)</title></rect>';
    if(hh%3===0)lbls+='<text class="axtx" x="'+(x+bw/2)+'" y="'+(H-bot+13)+'" text-anchor="middle">'+hh+'h</text>';
  }
  return '<svg width="'+W+'" height="'+H+'" viewBox="0 0 '+W+' '+H+'" style="min-width:600px">'+bars+lbls+'</svg>';
}
document.getElementById('showModal').addEventListener('click',function(e){if(e.target===this)closeShow()});

function curHost(){return document.getElementById('hostSel').value}
function filteredShows(){var h=curHost();return DATA.shows.filter(function(s){return !h||s.host===h})}

function renderConfig(){
  var c=DATA.config||{};
  document.getElementById('cMode').value=c.mode||'flat';
  document.getElementById('cFlat').value=c.flat_pct!=null?c.flat_pct:10;
  document.getElementById('cPct').value=c.pct!=null?c.pct:10;
  renderTiers(c.tiers||[]);
  applyModeUI();
}
function applyModeUI(){var m=document.getElementById('cMode').value;
  document.getElementById('flatBox').style.display=(m==='flat')?'block':'none';
  document.getElementById('pctBox').style.display=(m==='base_pct')?'block':'none';
  document.getElementById('tierBox').style.display=(m==='tiered')?'block':'none';}
var TIERS=[];
function renderTiers(ts){TIERS=ts.length?ts.slice():[{min:0,pct:8}];
  document.getElementById('tiers').innerHTML=TIERS.map(function(t,i){
    return '<div class="tier-row"><span class="muted">from</span> $<input type="number" value="'+(t.min||0)+'" data-i="'+i+'" data-k="min" style="width:110px"> <span class="muted">→</span> <input type="number" step="0.1" value="'+(t.pct||0)+'" data-i="'+i+'" data-k="pct" style="width:80px">% <button class="btn-x" onclick="delTier('+i+')">✕</button></div>';
  }).join('');
  document.getElementById('tiers').querySelectorAll('input').forEach(function(el){el.addEventListener('input',function(){TIERS[+el.dataset.i][el.dataset.k]=parseFloat(el.value||'0')})});
}
function delTier(i){TIERS.splice(i,1);renderTiers(TIERS)}
document.getElementById('addTier').addEventListener('click',function(){TIERS.push({min:0,pct:10});renderTiers(TIERS)});
document.getElementById('cMode').addEventListener('change',applyModeUI);
document.getElementById('saveCfg').addEventListener('click',function(){
  var body={mode:document.getElementById('cMode').value,flat_pct:parseFloat(document.getElementById('cFlat').value||'0'),
            pct:parseFloat(document.getElementById('cPct').value||'0'),tiers:TIERS};
  fetch('/api/commission-config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
   .then(function(r){return r.json()}).then(function(d){if(d.ok){toast('Rule saved ✓');load()}else toast('Failed',true)});
});

function renderKpis(){
  var sh=filteredShows();
  var rev=0,comm=0,units=0,orders=0,ship=0;
  sh.forEach(function(s){rev+=s.revenue;comm+=s.commission;units+=s.units;orders+=s.orders;ship+=(s.shipping||0)});
  document.getElementById('kpis').innerHTML=
    '<div class="kpi rev"><div class="l">Net sales (products)</div><div class="v">'+money(rev)+'</div></div>'+
    '<div class="kpi comm" style="border-color:rgba(180,83,9,.3)"><div class="l">Shipping collected</div><div class="v" style="color:#b45309">'+money(ship)+'</div></div>'+
    '<div class="kpi comm"><div class="l">Commission</div><div class="v">'+money(comm)+'</div></div>'+
    '<div class="kpi units"><div class="l">Units sold</div><div class="v">'+units.toLocaleString()+'</div></div>'+
    '<div class="kpi aov"><div class="l">Avg / show</div><div class="v">'+money(sh.length?rev/sh.length:0)+'</div></div>';
}

function renderChart(){
  var sh=filteredShows();
  document.getElementById('chartHost').textContent=curHost()?('· '+curHost()):'· all hosts';
  if(!sh.length){document.getElementById('chart').innerHTML='<div class="muted">No data</div>';return}
  var n=sh.length,bw=Math.max(26,Math.min(70,Math.floor(1100/n))),gap=10,W=n*(bw+gap)+50,H=240,top=14,bot=44;
  var max=Math.max.apply(null,sh.map(function(s){return s.revenue}))||1;
  var bars='',lbls='';
  sh.forEach(function(s,i){
    var bh=Math.round((H-top-bot)*(s.revenue/max));
    var x=44+i*(bw+gap),y=H-bot-bh;
    bars+='<rect class="bar" x="'+x+'" y="'+y+'" width="'+bw+'" height="'+Math.max(1,bh)+'" rx="3"><title>'+esc(s.host)+' — '+esc((s.show_date||'').slice(0,10))+': '+money(s.revenue)+' ('+money(s.commission)+' comm)</title></rect>';
    lbls+='<text class="axtx" x="'+(x+bw/2)+'" y="'+(H-bot+14)+'" text-anchor="middle">'+esc((s.show_date||'').slice(5,10))+'</text>';
    if(bh>16)bars+='<text class="axtx" x="'+(x+bw/2)+'" y="'+(y-4)+'" text-anchor="middle" style="fill:#64748b">'+money(s.revenue)+'</text>';
  });
  var grid='';for(var g=0;g<=4;g++){var gy=top+(H-top-bot)*g/4;grid+='<line class="axis" x1="40" y1="'+gy+'" x2="'+W+'" y2="'+gy+'"/><text class="axtx" x="0" y="'+(gy+3)+'">'+money(max*(4-g)/4)+'</text>';}
  document.getElementById('chart').innerHTML='<svg width="'+W+'" height="'+H+'" viewBox="0 0 '+W+' '+H+'">'+grid+bars+lbls+'</svg>';
}

function renderTable(){
  var sh=filteredShows().slice().reverse();
  if(!sh.length){document.getElementById('rows').innerHTML='<tr><td colspan="11" class="muted">No shows</td></tr>';return}
  document.getElementById('rows').innerHTML=sh.map(function(s){
    var gi=DATA.shows.indexOf(s);
    return '<tr><td class="muted">'+esc((s.show_date||'').slice(0,10))+'</td>'+
      '<td><a href="#" onclick="openShow('+gi+');return false" style="color:#4f46e5;text-decoration:underline">'+esc(s.label)+'</a></td>'+
      '<td><input class="host-in" value="'+esc(s.host)+'" data-gi="'+gi+'"></td>'+
      '<td class="rev">'+money2(s.revenue)+'</td>'+
      '<td style="color:#b45309">'+money2(s.shipping||0)+'</td><td class="muted">'+money2(s.gross||s.revenue)+'</td>'+
      '<td>'+s.orders+'</td><td>'+s.units+'</td>'+
      '<td>'+money2(s.aov)+'</td><td>'+(s.cancel_rate||0)+'%</td>'+
      '<td class="comm">'+money2(s.commission)+'</td></tr>';
  }).join('');
  document.getElementById('rows').querySelectorAll('.host-in').forEach(function(el){
    el.addEventListener('change',function(){var s=DATA.shows[+el.dataset.gi];
      fetch('/api/host-override',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({label:s.label,host:el.value.trim()})})
       .then(function(r){return r.json()}).then(function(d){if(d.ok){toast('Host updated ✓');load()}else toast('Failed',true)});
    });
  });
}

function renderHostFilter(){
  var sel=document.getElementById('hostSel');var cur=sel.value;
  sel.innerHTML='<option value="">All hosts</option>'+DATA.hosts.map(function(h){return '<option value="'+esc(h.host)+'">'+esc(h.host)+' ('+money(h.revenue)+')</option>'}).join('');
  sel.value=cur;
}
function renderAll(){renderKpis();renderChart();renderTable()}
document.getElementById('hostSel').addEventListener('change',renderAll);

function load(){
  fetch('/api/host-analytics').then(function(r){return r.json()}).then(function(d){
    if(!d.ok){toast('Failed to load',true);return}
    DATA=d;renderConfig();renderHostFilter();renderAll();
  });
}
load();
</script></body></html>'''


# ── GEOGRAPHY ANALYTICS — where orders ship, by state ──
GEO_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Geography</title>
__NAVBAR_CSS__
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#ffffff;color:#1a2130;min-height:100vh}
.page-hdr{padding:24px 28px 8px;max-width:1300px;margin:0 auto}
.page-title{font-size:22px;font-weight:800}.page-title span{color:#4f46e5;margin-left:8px;font-weight:600;font-size:14px}
.wrap{max-width:1300px;margin:0 auto;padding:8px 28px 40px}
.card{background:#ffffff;border:1px solid rgba(17,24,39,0.096);border-radius:16px;padding:18px 20px;margin-bottom:18px}
.card h2{font-size:13px;font-weight:800;color:#4f46e5;text-transform:uppercase;letter-spacing:.6px;margin-bottom:14px}
select,input{background:#ffffff;border:2px solid rgba(17,24,39,0.128);border-radius:10px;padding:10px 13px;font-size:14px;color:#1a2130;font-family:inherit;outline:none}
select:focus,input:focus{border-color:#4f46e5}
label{display:block;font-size:11px;font-weight:700;color:#6b7280;margin-bottom:5px;text-transform:uppercase;letter-spacing:.4px}
.row{display:flex;gap:12px;align-items:end;flex-wrap:wrap}
.btn{border:none;border-radius:10px;padding:11px 18px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit;background:rgba(17,24,39,0.128);color:#1a2130;border:1px solid rgba(17,24,39,0.128)}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:6px 0 18px}
@media(max-width:760px){.cards{grid-template-columns:repeat(2,1fr)}}
.kpi{background:#ffffff;border:1px solid rgba(17,24,39,0.096);border-radius:14px;padding:16px}
.kpi .l{font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px;font-weight:700;margin-bottom:6px}
.kpi .v{font-size:26px;font-weight:900}
.kpi.a .v{color:#059669}.kpi.b .v{color:#2563eb}.kpi.c .v{color:#4f46e5}.kpi.d .v{color:#b45309}
.bars .brow{display:grid;grid-template-columns:44px 1fr 130px;gap:10px;align-items:center;margin-bottom:7px}
.bars .st{font-weight:800;font-size:14px}
.bars .track{background:rgba(17,24,39,0.05);border-radius:6px;height:22px;overflow:hidden}
.bars .fill{height:100%;background:linear-gradient(90deg,#4f46e5,#7c3aed);border-radius:6px}
.bars .val{font-size:12.5px;color:#9aa6bd;text-align:right}
table{width:100%;border-collapse:collapse}th,td{padding:9px 12px;font-size:13px;border-bottom:1px solid rgba(17,24,39,0.096);text-align:right}
th:first-child,td:first-child{text-align:left}
th{font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px}
.two{display:grid;grid-template-columns:1.4fr 1fr;gap:18px}@media(max-width:820px){.two{grid-template-columns:1fr}}
.muted{color:#6b7280;font-size:13px}.rev{color:#2563eb;font-weight:700}
.warn{background:rgba(251,191,36,.1);border:1px solid rgba(251,191,36,.3);color:#b45309;padding:10px 14px;border-radius:10px;font-size:13px;margin-bottom:14px}
</style></head><body>
__NAVBAR__
<div class="page-hdr"><div class="page-title">🗺️ Geography <span>__NAME__</span></div></div>
<div class="wrap">
<div class="card">
  <div class="row">
    <div style="flex:1;min-width:200px"><label>Show</label><select id="fShow" style="width:100%"><option value="">All shows</option></select></div>
    <div><label>From (show date)</label><input id="fFrom" type="date"></div>
    <div><label>To</label><input id="fTo" type="date"></div>
    <button class="btn" id="clr">Clear</button>
  </div>
</div>
<div id="notice"></div>
<div class="cards" id="kpis"></div>
<div class="two">
  <div class="card"><h2>📊 Orders by state</h2><div class="bars" id="bars"></div>
    <table style="margin-top:14px"><thead><tr><th>State</th><th>Orders</th><th>%</th><th>Units</th><th>Revenue</th></tr></thead>
    <tbody id="rows"><tr><td colspan="5" class="muted">Loading…</td></tr></tbody></table>
  </div>
  <div class="card"><h2>🏙️ Top cities</h2><div id="cities"></div></div>
</div>
</div>
<div class="toast" id="t" style="position:fixed;bottom:24px;right:24px;background:#10b981;color:#fff;padding:14px 22px;border-radius:10px;font-weight:700;z-index:100;display:none"></div>
<script>
function esc(s){var d=document.createElement('div');d.textContent=(s==null?'':String(s));return d.innerHTML}
function money(v){return '$'+Number(v||0).toLocaleString(undefined,{maximumFractionDigits:0})}
var FILL=false;
fetch('/api/shows').then(function(r){return r.json()}).then(function(shows){
  var sel=document.getElementById('fShow');(shows||[]).forEach(function(s){var o=document.createElement('option');o.value=s.name;o.textContent=s.name;sel.appendChild(o)});
});
function qs(){var p=[];var sh=document.getElementById('fShow').value;var fr=document.getElementById('fFrom').value;var to=document.getElementById('fTo').value;
  if(sh)p.push('show='+encodeURIComponent(sh));if(fr)p.push('from='+fr);if(to)p.push('to='+to);return p.length?('?'+p.join('&')):''}
function load(){
  fetch('/api/geo-analytics'+qs()).then(function(r){return r.json()}).then(function(d){
    if(!d.ok)return;
    document.getElementById('notice').innerHTML=d.unresolved?('<div class="warn">⚠️ '+d.unresolved+' of '+d.total_orders+' orders had no usable ZIP/state and are excluded.</div>'):'';
    document.getElementById('kpis').innerHTML=
      '<div class="kpi a"><div class="l">Orders mapped</div><div class="v">'+d.resolved.toLocaleString()+'</div></div>'+
      '<div class="kpi b"><div class="l">States reached</div><div class="v">'+d.states_reached+'</div></div>'+
      '<div class="kpi c"><div class="l">Top state</div><div class="v">'+(d.top_state||'—')+'</div></div>'+
      '<div class="kpi d"><div class="l">Top state share</div><div class="v">'+(d.states.length?d.states[0].pct+'%':'—')+'</div></div>';
    var mx=d.states.length?d.states[0].orders:1;
    document.getElementById('bars').innerHTML=d.states.slice(0,12).map(function(s){
      return '<div class="brow"><div class="st">'+esc(s.state)+'</div>'+
        '<div class="track"><div class="fill" style="width:'+Math.max(2,Math.round(100*s.orders/mx))+'%"></div></div>'+
        '<div class="val">'+s.orders+' · '+s.pct+'%</div></div>';
    }).join('')||'<div class="muted">No data</div>';
    document.getElementById('rows').innerHTML=(d.states.length?d.states.map(function(s){
      return '<tr><td><b>'+esc(s.state)+'</b></td><td>'+s.orders+'</td><td>'+s.pct+'%</td><td>'+s.units+'</td><td class="rev">'+money(s.revenue)+'</td></tr>';
    }).join(''):'<tr><td colspan="5" class="muted">No orders for this filter</td></tr>');
    document.getElementById('cities').innerHTML=(d.cities.length?d.cities.map(function(c){
      return '<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid rgba(17,24,39,0.05);font-size:13.5px"><span>'+esc(c.k)+'</span><span class="muted">'+c.v+' orders</span></div>';
    }).join(''):'<div class="muted">No city data yet (newer imports capture city)</div>');
  });
}
['fShow','fFrom','fTo'].forEach(function(id){document.getElementById(id).addEventListener('change',load)});
document.getElementById('clr').addEventListener('click',function(){['fShow','fFrom','fTo'].forEach(function(id){document.getElementById(id).value=''});load()});
load();
</script></body></html>'''


# ── PICKER ANALYTICS — pick speed/volume per picker ──
PICKER_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Picker Analytics</title>
__NAVBAR_CSS__
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#ffffff;color:#1a2130;min-height:100vh}
.page-hdr{padding:24px 28px 8px;max-width:1300px;margin:0 auto}
.page-title{font-size:22px;font-weight:800}.page-title span{color:#4f46e5;margin-left:8px;font-weight:600;font-size:14px}
.wrap{max-width:1300px;margin:0 auto;padding:8px 28px 40px}
.card{background:#ffffff;border:1px solid rgba(17,24,39,0.096);border-radius:16px;padding:18px 20px;margin-bottom:18px}
.card h2{font-size:13px;font-weight:800;color:#4f46e5;text-transform:uppercase;letter-spacing:.6px;margin-bottom:14px}
select,input{background:#ffffff;border:2px solid rgba(17,24,39,0.128);border-radius:10px;padding:10px 13px;font-size:14px;color:#1a2130;font-family:inherit;outline:none}
select:focus,input:focus{border-color:#4f46e5}
label{display:block;font-size:11px;font-weight:700;color:#6b7280;margin-bottom:5px;text-transform:uppercase;letter-spacing:.4px}
.row{display:flex;gap:12px;align-items:end;flex-wrap:wrap}
.cards{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin:6px 0 18px}
@media(max-width:860px){.cards{grid-template-columns:repeat(2,1fr)}}
.kpi{background:#ffffff;border:1px solid rgba(17,24,39,0.096);border-radius:14px;padding:16px}
.kpi .l{font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px;font-weight:700;margin-bottom:6px}
.kpi .v{font-size:26px;font-weight:900}
.kpi.pk .v{color:#059669}.kpi.sp .v{color:#2563eb}.kpi.it .v{color:#4f46e5}.kpi.hr .v{color:#b45309}.kpi.act .v{color:#1a2130}
table{width:100%;border-collapse:collapse;background:#ffffff;border-radius:12px;overflow:hidden}
th,td{padding:10px 12px;font-size:13px;border-bottom:1px solid rgba(17,24,39,0.096);text-align:right}
th:first-child,td:first-child{text-align:left}
th{font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px}
.bar{fill:#4f46e5}.bar:hover{fill:#7c3aed}.axtx{fill:#6b7280;font-size:10px}.axis{stroke:rgba(17,24,39,0.16)}
.muted{color:#6b7280;font-size:13px}.chart-wrap{overflow-x:auto}
.fast{color:#059669;font-weight:700}.slow{color:#b45309;font-weight:700}
.note{font-size:12px;color:#6b7280;margin-top:8px}
</style></head><body>
__NAVBAR__
<div class="page-hdr"><div class="page-title">🧺 Picker Analytics <span>__NAME__</span></div></div>
<div class="wrap">
<div class="card">
  <div class="row">
    <div><label>Picker</label><select id="fPicker"><option value="">All pickers</option></select></div>
    <div style="min-width:180px"><label>Show</label><select id="fShow" style="width:100%"><option value="">All shows</option></select></div>
    <div><label>From</label><input id="fFrom" type="date"></div>
    <div><label>To</label><input id="fTo" type="date"></div>
    <button class="btn" style="background:rgba(17,24,39,0.128);color:#1a2130;border:1px solid rgba(17,24,39,0.128);border-radius:10px;padding:11px 18px;font-weight:700;cursor:pointer;font-family:inherit" id="clr">Clear</button>
  </div>
</div>
<div class="cards" id="kpis"></div>
<div class="card">
  <h2>🧑‍🌾 By picker</h2>
  <table><thead><tr><th>Picker</th><th>Orders picked</th><th>Items</th><th>Avg / order</th><th>Orders / hr</th><th>Active hrs</th></tr></thead>
  <tbody id="prows"><tr><td colspan="6" class="muted">Loading…</td></tr></tbody></table>
  <div class="note">⏱️ Time-per-order is estimated from the gap between consecutive completed picks (gaps over 20 min are treated as breaks and excluded).</div>
</div>
<div class="card">
  <h2>👥 Team comparison — all pickers</h2>
  <div id="teamCmp"><div class="muted">Loading…</div></div>
  <div class="note">Ranked by orders picked. Click any picker to open their shift timeline.</div>
</div>
<div class="card" id="shiftCard">
  <h2>🕑 Shift timeline — pick vs pack &amp; idle time</h2>
  <div id="shiftBody"><div class="muted">Select a single picker above to see their day-by-day shift: first vs last scan, the pick-vs-pack split, and the idle time in between.</div></div>
</div>
</div>
<div class="toast" id="t" style="position:fixed;bottom:24px;right:24px;background:#10b981;color:#fff;padding:14px 22px;border-radius:10px;font-weight:700;z-index:100;display:none"></div>
<script>
function esc(s){var d=document.createElement('div');d.textContent=(s==null?'':String(s));return d.innerHTML}
function secFmt(s){s=Number(s||0);if(!s)return '—';if(s<60)return s.toFixed(0)+'s';return Math.floor(s/60)+'m '+Math.round(s%60)+'s'}
var FILL=false;
fetch('/api/shows').then(function(r){return r.json()}).then(function(shows){var sel=document.getElementById('fShow');(shows||[]).forEach(function(s){var o=document.createElement('option');o.value=s.name;o.textContent=s.name;sel.appendChild(o)})});
function qs(){var p=[];var m={fPicker:'picker',fShow:'show',fFrom:'from',fTo:'to'};['fPicker','fShow','fFrom','fTo'].forEach(function(id){var v=document.getElementById(id).value;if(v)p.push(m[id]+'='+encodeURIComponent(v))});return p.length?('?'+p.join('&')):''}
function load(){
  fetch('/api/picker-analytics'+qs()).then(function(r){return r.json()}).then(function(d){
    if(!d.ok)return;
    if(!FILL){FILL=true;var ps=document.getElementById('fPicker');ps.innerHTML='<option value="">All pickers</option>'+d.picker_list.map(function(w){return '<option>'+esc(w)+'</option>'}).join('')}
    var o=d.overall;
    document.getElementById('kpis').innerHTML=
      '<div class="kpi pk"><div class="l">Orders picked</div><div class="v">'+o.orders.toLocaleString()+'</div></div>'+
      '<div class="kpi sp"><div class="l">Avg / order</div><div class="v">'+secFmt(o.avg_sec_order)+'</div></div>'+
      '<div class="kpi it"><div class="l">Items picked</div><div class="v">'+o.items.toLocaleString()+'</div></div>'+
      '<div class="kpi hr"><div class="l">Orders / hour</div><div class="v">'+o.orders_per_hr+'</div></div>'+
      '<div class="kpi act"><div class="l">Active hours</div><div class="v">'+o.active_hours+'</div></div>';
    var avg=o.avg_sec_order||0;
    document.getElementById('prows').innerHTML=(d.pickers.length?d.pickers.map(function(w){
      var cls=w.avg_sec_order<=avg?'fast':'slow';
      return '<tr><td><b>'+esc(w.picker)+'</b></td><td>'+w.orders+'</td><td>'+w.items+'</td>'+
        '<td class="'+cls+'">'+secFmt(w.avg_sec_order)+'</td><td>'+w.orders_per_hr+'</td><td>'+w.active_hours+'</td></tr>';
    }).join(''):'<tr><td colspan="6" class="muted">No picking records for this filter</td></tr>');
    renderTeam(d.pickers,'picker','orders','orders','orders_per_hr','fPicker');
    renderShift(d.shift, document.getElementById('fPicker').value);
  });
}
function renderTeam(list,nameKey,valKey,unit,hrKey,selId){
  var el=document.getElementById('teamCmp');
  if(!list||!list.length){el.innerHTML='<div class="muted">No pickers yet</div>';return}
  var srt=list.slice().sort(function(a,b){return (b[valKey]||0)-(a[valKey]||0)});
  var max=Math.max.apply(null,srt.map(function(w){return w[valKey]||0}))||1;
  el.innerHTML=srt.map(function(w){
    var nm=w[nameKey]||'',val=w[valKey]||0,pct=Math.max(2,Math.round(100*val/max));
    return '<div class="cmpRow" data-w="'+esc(nm)+'" style="display:flex;align-items:center;gap:10px;padding:5px 0;cursor:pointer">'+
      '<div style="width:120px;font-size:13px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="'+esc(nm)+'">'+esc(nm)+'</div>'+
      '<div style="flex:1;background:rgba(79,70,229,.08);border-radius:6px;height:22px"><div style="width:'+pct+'%;background:linear-gradient(90deg,#818cf8,#4f46e5);height:100%;border-radius:6px;min-width:4px"></div></div>'+
      '<div style="width:130px;text-align:right;font-size:12px;color:#586274">'+val.toLocaleString()+' '+unit+' · '+(w[hrKey]||0)+'/hr</div></div>';
  }).join('');
  Array.prototype.forEach.call(el.querySelectorAll('.cmpRow'),function(r){
    r.addEventListener('click',function(){var s=document.getElementById(selId);if(s){s.value=this.getAttribute('data-w');load();window.scrollTo({top:document.body.scrollHeight,behavior:'smooth'});}});
  });
}
function hms(s){s=Math.round(Number(s||0));if(s<=0)return '—';var h=Math.floor(s/3600),m=Math.round((s%3600)/60);return (h?h+'h ':'')+m+'m'}
function renderShift(shift,workerName){
  var b=document.getElementById('shiftBody');
  if(!workerName){b.innerHTML='<div class="muted">Select a single picker above to see their day-by-day shift: first vs last scan, the pick-vs-pack split, and the idle time in between.</div>';return}
  if(!shift||!shift.length){b.innerHTML='<div class="muted">No pick or pack activity for this person in the selected range.</div>';return}
  var legend='<div style="display:flex;gap:18px;margin-bottom:12px;font-size:12px;font-weight:700">'+
    '<span><span style="display:inline-block;width:11px;height:11px;background:#a5b4fc;border-radius:3px;margin-right:5px;vertical-align:-1px"></span>Picked</span>'+
    '<span><span style="display:inline-block;width:11px;height:11px;background:#4f46e5;border-radius:3px;margin-right:5px;vertical-align:-1px"></span>Packed</span></div>';
  var n=shift.length,bw=Math.max(22,Math.min(60,Math.floor(1100/n))),gap=10,W=n*(bw+gap)+50,H=230,top=16,bot=44;
  var max=Math.max.apply(null,shift.map(function(d){return d.picked+d.packed}))||1;
  var bars='',lbls='';
  shift.forEach(function(d,i){
    var x=44+i*(bw+gap),base=H-bot;
    var ph=Math.round((H-top-bot)*(d.picked/max)),kh=Math.round((H-top-bot)*(d.packed/max)),tot=d.picked+d.packed;
    bars+='<rect x="'+x+'" y="'+(base-ph)+'" width="'+bw+'" height="'+Math.max(0,ph)+'" fill="#a5b4fc" rx="2"><title>'+esc(d.date)+': '+d.picked+' picked</title></rect>';
    bars+='<rect class="packedBar" data-day="'+esc(d.date)+'" x="'+x+'" y="'+(base-ph-kh)+'" width="'+bw+'" height="'+Math.max(0,kh)+'" fill="#4f46e5" rx="2" style="cursor:pointer"><title>'+esc(d.date)+': '+d.packed+' packed — click to see the videos packed this day</title></rect>';
    lbls+='<text class="axtx" x="'+(x+bw/2)+'" y="'+(H-bot+14)+'" text-anchor="middle">'+esc((d.date||'').slice(5))+'</text>';
    if(ph+kh>14)bars+='<text class="axtx" x="'+(x+bw/2)+'" y="'+(base-ph-kh-4)+'" text-anchor="middle" style="fill:#64748b">'+tot+'</text>';
  });
  var grid='';for(var g=0;g<=4;g++){var gy=top+(H-top-bot)*g/4;grid+='<line class="axis" x1="40" y1="'+gy+'" x2="'+W+'" y2="'+gy+'"/><text class="axtx" x="0" y="'+(gy+3)+'">'+Math.round(max*(4-g)/4)+'</text>';}
  var chart='<div class="chart-wrap"><svg width="'+W+'" height="'+H+'" viewBox="0 0 '+W+' '+H+'">'+grid+bars+lbls+'</svg></div>';
  var hint='<div style="font-size:12px;color:#6b7280;margin-top:6px">Tip: click the packed (dark) part of a bar to see the videos '+esc(workerName)+' packed that day.</div>';
  b.innerHTML=legend+chart+hint;
  Array.prototype.forEach.call(document.querySelectorAll('#shiftBody .packedBar'),function(el){
    el.addEventListener('click',function(){
      var day=this.getAttribute('data-day');
      window.location.href='/dashboard?worker='+encodeURIComponent(workerName)+'&date='+encodeURIComponent(day);
    });
  });
}
function renderChart(days){
  if(!days||!days.length){document.getElementById('chart').innerHTML='<div class="muted">No data</div>';return}
  var n=days.length,bw=Math.max(20,Math.min(60,Math.floor(1100/n))),gap=8,W=n*(bw+gap)+50,H=220,top=14,bot=42;
  var max=Math.max.apply(null,days.map(function(d){return d.orders}))||1;var bars='',lbls='';
  days.forEach(function(d,i){var bh=Math.round((H-top-bot)*(d.orders/max)),x=44+i*(bw+gap),y=H-bot-bh;
    bars+='<rect class="bar" x="'+x+'" y="'+y+'" width="'+bw+'" height="'+Math.max(1,bh)+'" rx="3"><title>'+esc(d.date)+': '+d.orders+' orders · '+d.items+' items</title></rect>';
    lbls+='<text class="axtx" x="'+(x+bw/2)+'" y="'+(H-bot+14)+'" text-anchor="middle">'+esc((d.date||'').slice(5))+'</text>';
    if(bh>14)bars+='<text class="axtx" x="'+(x+bw/2)+'" y="'+(y-4)+'" text-anchor="middle" style="fill:#9aa6bd">'+d.orders+'</text>';});
  var grid='';for(var g=0;g<=4;g++){var gy=top+(H-top-bot)*g/4;grid+='<line class="axis" x1="40" y1="'+gy+'" x2="'+W+'" y2="'+gy+'"/><text class="axtx" x="0" y="'+(gy+3)+'">'+Math.round(max*(4-g)/4)+'</text>';}
  document.getElementById('chart').innerHTML='<svg width="'+W+'" height="'+H+'" viewBox="0 0 '+W+' '+H+'">'+grid+bars+lbls+'</svg>';
}
['fPicker','fShow','fFrom','fTo'].forEach(function(id){document.getElementById(id).addEventListener('change',load)});
document.getElementById('clr').addEventListener('click',function(){['fPicker','fShow','fFrom','fTo'].forEach(function(id){document.getElementById(id).value=''});load()});
load();
</script></body></html>'''


# ── REPEAT CUSTOMERS — returning buyers & loyalty ──
REPEAT_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Repeat Customers</title>
__NAVBAR_CSS__
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#ffffff;color:#1a2130;min-height:100vh}
.page-hdr{padding:24px 28px 8px;max-width:1300px;margin:0 auto}
.page-title{font-size:22px;font-weight:800}.page-title span{color:#4f46e5;margin-left:8px;font-weight:600;font-size:14px}
.wrap{max-width:1300px;margin:0 auto;padding:8px 28px 40px}
.card{background:#ffffff;border:1px solid rgba(17,24,39,0.096);border-radius:16px;padding:18px 20px;margin-bottom:18px}
.card h2{font-size:13px;font-weight:800;color:#4f46e5;text-transform:uppercase;letter-spacing:.6px;margin-bottom:14px}
select,input{background:#ffffff;border:2px solid rgba(17,24,39,0.128);border-radius:10px;padding:10px 13px;font-size:14px;color:#1a2130;font-family:inherit;outline:none}
select:focus,input:focus{border-color:#4f46e5}
label{display:block;font-size:11px;font-weight:700;color:#6b7280;margin-bottom:5px;text-transform:uppercase;letter-spacing:.4px}
.row{display:flex;gap:12px;align-items:end;flex-wrap:wrap}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:6px 0 18px}
@media(max-width:760px){.cards{grid-template-columns:repeat(2,1fr)}}
.kpi{background:#ffffff;border:1px solid rgba(17,24,39,0.096);border-radius:14px;padding:16px}
.kpi .l{font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px;font-weight:700;margin-bottom:6px}
.kpi .v{font-size:26px;font-weight:900}
.kpi.a .v{color:#4f46e5}.kpi.b .v{color:#059669}.kpi.c .v{color:#b45309}.kpi.d .v{color:#2563eb}
table{width:100%;border-collapse:collapse;background:#ffffff;border-radius:12px;overflow:hidden}
th,td{padding:10px 12px;font-size:13px;border-bottom:1px solid rgba(17,24,39,0.096);text-align:right}
th:first-child,td:first-child,th:nth-child(2),td:nth-child(2){text-align:left}
th{font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px}
.uname{font-family:monospace;color:#4f46e5}.rev{color:#2563eb;font-weight:700}.ord{font-weight:800}
a.cust{color:#1a2130;text-decoration:none}a.cust:hover{color:#4f46e5;text-decoration:underline}
.muted{color:#6b7280;font-size:13px}
</style></head><body>
__NAVBAR__
<div class="page-hdr"><div class="page-title">🔁 Repeat Customers <span>__NAME__</span></div></div>
<div class="wrap">
<div class="card">
  <div class="row">
    <div><label>Show at least</label><select id="fMin"><option value="2">2+ orders (repeat)</option><option value="3">3+ orders</option><option value="5">5+ orders (VIP)</option><option value="1">1+ (all buyers)</option></select></div>
    <div><label>Sort by</label><select id="fSort"><option value="orders">Most orders</option><option value="revenue">Most spent ($)</option></select></div>
    <div><label>From (show date)</label><input id="fFrom" type="date"></div>
    <div><label>To</label><input id="fTo" type="date"></div>
    <button class="btn" style="background:rgba(17,24,39,0.128);color:#1a2130;border:1px solid rgba(17,24,39,0.128);border-radius:10px;padding:11px 18px;font-weight:700;cursor:pointer;font-family:inherit" id="clr">Clear</button>
  </div>
</div>
<div class="cards" id="kpis"></div>
<div class="card">
  <h2>🔁 Customers <span class="muted" id="cnt"></span></h2>
  <table><thead><tr><th>Customer</th><th>Username</th><th>Orders</th><th>Shows</th><th>Total spent</th><th>First</th><th>Last</th></tr></thead>
  <tbody id="rows"><tr><td colspan="7" class="muted">Loading…</td></tr></tbody></table>
</div>
</div>
<script>
function esc(s){var d=document.createElement('div');d.textContent=(s==null?'':String(s));return d.innerHTML}
function money(v){return '$'+Number(v||0).toLocaleString(undefined,{maximumFractionDigits:0})}
function load(){
  var p=[];var mn=document.getElementById('fMin').value;var fr=document.getElementById('fFrom').value;var to=document.getElementById('fTo').value;
  p.push('min_orders='+mn);p.push('sort='+document.getElementById('fSort').value);if(fr)p.push('from='+fr);if(to)p.push('to='+to);
  fetch('/api/repeat-customers?'+p.join('&')).then(function(r){return r.json()}).then(function(d){
    if(!d.ok)return;
    document.getElementById('kpis').innerHTML=
      '<div class="kpi a"><div class="l">Total customers</div><div class="v">'+d.total_customers.toLocaleString()+'</div></div>'+
      '<div class="kpi b"><div class="l">Repeat (2+ orders)</div><div class="v">'+d.repeat_customers.toLocaleString()+'</div></div>'+
      '<div class="kpi c"><div class="l">Repeat rate</div><div class="v">'+d.repeat_rate+'%</div></div>'+
      '<div class="kpi d"><div class="l">Repeat revenue</div><div class="v">'+money(d.repeat_revenue)+'</div></div>';
    document.getElementById('cnt').textContent='('+d.customers.length+' shown)';
    document.getElementById('rows').innerHTML=(d.customers.length?d.customers.map(function(x){
      return '<tr><td><a class="cust" href="/customers?u='+encodeURIComponent(x.username)+'">'+esc(x.name||'(no name)')+'</a></td>'+
        '<td class="uname">@'+esc(x.username)+'</td><td class="ord">'+x.orders+'</td><td>'+x.shows+'</td>'+
        '<td class="rev">'+money(x.revenue)+'</td><td class="muted">'+esc((x.first||'').slice(0,10))+'</td><td class="muted">'+esc((x.last||'').slice(0,10))+'</td></tr>';
    }).join(''):'<tr><td colspan="7" class="muted">No customers match this filter</td></tr>');
  });
}
['fMin','fSort','fFrom','fTo'].forEach(function(id){document.getElementById(id).addEventListener('change',load)});
document.getElementById('clr').addEventListener('click',function(){document.getElementById('fMin').value='2';document.getElementById('fSort').value='orders';document.getElementById('fFrom').value='';document.getElementById('fTo').value='';load()});
load();
</script></body></html>'''


# ── PACKER ANALYTICS — pack-speed per worker ──
PACKER_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Packer Analytics</title>
__NAVBAR_CSS__
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#ffffff;color:#1a2130;min-height:100vh}
.page-hdr{padding:24px 28px 8px;max-width:1300px;margin:0 auto}
.page-title{font-size:22px;font-weight:800}.page-title span{color:#4f46e5;margin-left:8px;font-weight:600;font-size:14px}
.wrap{max-width:1300px;margin:0 auto;padding:8px 28px 40px}
.card{background:#ffffff;border:1px solid rgba(17,24,39,0.096);border-radius:16px;padding:18px 20px;margin-bottom:18px}
.card h2{font-size:13px;font-weight:800;color:#4f46e5;text-transform:uppercase;letter-spacing:.6px;margin-bottom:14px}
select,input{background:#ffffff;border:2px solid rgba(17,24,39,0.128);border-radius:10px;padding:10px 13px;font-size:14px;color:#1a2130;font-family:inherit;outline:none}
select:focus,input:focus{border-color:#4f46e5}
label{display:block;font-size:11px;font-weight:700;color:#6b7280;margin-bottom:5px;text-transform:uppercase;letter-spacing:.4px}
.row{display:flex;gap:12px;align-items:end;flex-wrap:wrap}
.cards{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin:6px 0 18px}
@media(max-width:860px){.cards{grid-template-columns:repeat(2,1fr)}}
.kpi{background:#ffffff;border:1px solid rgba(17,24,39,0.096);border-radius:14px;padding:16px}
.kpi .l{font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px;font-weight:700;margin-bottom:6px}
.kpi .v{font-size:26px;font-weight:900}
.kpi.pk .v{color:#059669}.kpi.sp .v{color:#2563eb}.kpi.it .v{color:#4f46e5}.kpi.hr .v{color:#b45309}.kpi.act .v{color:#1a2130}
table{width:100%;border-collapse:collapse;background:#ffffff;border-radius:12px;overflow:hidden}
th,td{padding:10px 12px;font-size:13px;border-bottom:1px solid rgba(17,24,39,0.096);text-align:right}
th:first-child,td:first-child{text-align:left}
th{font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px}
.bar{fill:#4f46e5}.bar:hover{fill:#7c3aed}.axtx{fill:#6b7280;font-size:10px}.axis{stroke:rgba(17,24,39,0.16)}
.muted{color:#6b7280;font-size:13px}.chart-wrap{overflow-x:auto}
.fast{color:#059669;font-weight:700}.slow{color:#b45309;font-weight:700}
.secLabel{font-size:13px;font-weight:800;color:#4f46e5;text-transform:uppercase;letter-spacing:.6px;margin:20px 0 2px;display:flex;align-items:center;gap:7px}
</style></head><body>
__NAVBAR__
<div class="page-hdr"><div class="page-title">📊 Warehouse Analytics <span>__NAME__</span></div></div>
<div class="wrap">
<div class="card">
  <div class="row">
    <div><label>Worker</label><select id="fWorker"><option value="">All workers</option></select></div>
    <div><label>Station</label><select id="fStation"><option value="">All stations</option></select></div>
    <div><label>From</label><input id="fFrom" type="date"></div>
    <div><label>To</label><input id="fTo" type="date"></div>
    <button class="btn" style="background:rgba(17,24,39,0.128);color:#1a2130;border:1px solid rgba(17,24,39,0.16);border-radius:10px;padding:11px 18px;font-weight:700;cursor:pointer;font-family:inherit" id="clr">Clear</button>
  </div>
</div>
<div class="secLabel">📦 Packing</div>
<div class="cards" id="kpis"></div>
<div class="card">
  <h2>👷 By worker</h2>
  <table><thead><tr><th>Worker</th><th>Packages</th><th>Items</th><th>Avg / package</th><th>Avg / item</th><th>Pkgs / hr</th><th>Active hrs</th></tr></thead>
  <tbody id="wrows"><tr><td colspan="7" class="muted">Loading…</td></tr></tbody></table>
</div>
<div class="secLabel">🧺 Picking</div>
<div class="cards" id="kpisPick"></div>
<div class="card">
  <h2>🧑‍🌾 By picker</h2>
  <table><thead><tr><th>Picker</th><th>Orders picked</th><th>Items</th><th>Avg / order</th><th>Orders / hr</th><th>Active hrs</th></tr></thead>
  <tbody id="prows"><tr><td colspan="6" class="muted">Loading…</td></tr></tbody></table>
  <div style="font-size:12px;color:#6b7280;margin-top:8px">⏱️ Time-per-order is estimated from the gap between consecutive picks (gaps over 20 min are treated as breaks).</div>
</div>
<div class="secLabel">👥 Team</div>
<div class="card">
  <h2>👥 Team comparison — all workers</h2>
  <div id="teamCmp"><div class="muted">Loading…</div></div>
  <div style="font-size:12px;color:#6b7280;margin-top:8px">Ranked by packages. Click any worker to open their shift timeline.</div>
</div>
<div class="card">
  <h2>📅 Packages per day <span class="muted" id="dayNote"></span></h2>
  <div class="chart-wrap"><div id="chart"></div></div>
</div>
<div class="card" id="shiftCard">
  <h2>🕑 Shift timeline — pick vs pack &amp; idle time</h2>
  <div id="shiftBody"><div class="muted">Select a single worker above to see their day-by-day shift: first vs last scan, the pick-vs-pack split, and the idle time in between.</div></div>
</div>
</div>
<div class="toast" id="t" style="position:fixed;bottom:24px;right:24px;background:#10b981;color:#fff;padding:14px 22px;border-radius:10px;font-weight:700;z-index:100;display:none"></div>
<script>
function esc(s){var d=document.createElement('div');d.textContent=(s==null?'':String(s));return d.innerHTML}
function secFmt(s){s=Number(s||0);if(s<60)return s.toFixed(0)+'s';var m=Math.floor(s/60),r=Math.round(s%60);return m+'m '+r+'s'}
var FILL=false;
function qs(){var p=[];['fWorker','fStation','fFrom','fTo'].forEach(function(id){var v=document.getElementById(id).value;if(v){var k={fWorker:'worker',fStation:'station',fFrom:'from',fTo:'to'}[id];p.push(k+'='+encodeURIComponent(v))}});return p.length?('?'+p.join('&')):''}
function load(){
  fetch('/api/packer-analytics'+qs()).then(function(r){return r.json()}).then(function(d){
    if(!d.ok)return;
    if(!FILL){FILL=true;
      var wsel=document.getElementById('fWorker');wsel.innerHTML='<option value="">All workers</option>'+d.worker_list.map(function(w){return '<option>'+esc(w)+'</option>'}).join('');
      var ssel=document.getElementById('fStation');ssel.innerHTML='<option value="">All stations</option>'+d.station_list.map(function(s){return '<option>'+esc(s)+'</option>'}).join('');
    }
    var o=d.overall;
    document.getElementById('kpis').innerHTML=
      '<div class="kpi pk"><div class="l">Packages</div><div class="v">'+o.packages.toLocaleString()+'</div></div>'+
      '<div class="kpi sp"><div class="l">Avg / package</div><div class="v">'+secFmt(o.avg_sec_pkg)+'</div></div>'+
      '<div class="kpi it"><div class="l">Avg / item</div><div class="v">'+secFmt(o.avg_sec_item)+'</div></div>'+
      '<div class="kpi hr"><div class="l">Packages / hour</div><div class="v">'+o.pkgs_per_hr+'</div></div>'+
      '<div class="kpi act"><div class="l">Active hours</div><div class="v">'+o.active_hours+'</div></div>';
    var avg=o.avg_sec_pkg||0;
    document.getElementById('wrows').innerHTML=(d.workers.length?d.workers.map(function(w){
      var cls=w.avg_sec_pkg<=avg?'fast':'slow';
      return '<tr><td><b>'+esc(w.worker)+'</b></td><td>'+w.packages+'</td><td>'+w.items+'</td>'+
        '<td class="'+cls+'">'+secFmt(w.avg_sec_pkg)+'</td><td>'+secFmt(w.avg_sec_item)+'</td>'+
        '<td>'+w.pkgs_per_hr+'</td><td>'+w.active_hours+'</td></tr>';
    }).join(''):'<tr><td colspan="7" class="muted">No packing records for this filter</td></tr>');
    renderTeam(d.workers,'worker','packages','pkgs','pkgs_per_hr','fWorker');
    renderChart(d.days);
    renderShift(d.shift, document.getElementById('fWorker').value);
    loadPick();
  });
}
function qsPick(){var p=[];var w=document.getElementById('fWorker').value;if(w)p.push('picker='+encodeURIComponent(w));var f=document.getElementById('fFrom').value;if(f)p.push('from='+f);var t=document.getElementById('fTo').value;if(t)p.push('to='+t);return p.length?('?'+p.join('&')):''}
function loadPick(){
  fetch('/api/picker-analytics'+qsPick()).then(function(r){return r.json()}).then(function(d){
    if(!d.ok)return;
    var o=d.overall;
    document.getElementById('kpisPick').innerHTML=
      '<div class="kpi pk"><div class="l">Orders picked</div><div class="v">'+o.orders.toLocaleString()+'</div></div>'+
      '<div class="kpi sp"><div class="l">Avg / order</div><div class="v">'+secFmt(o.avg_sec_order)+'</div></div>'+
      '<div class="kpi it"><div class="l">Items picked</div><div class="v">'+o.items.toLocaleString()+'</div></div>'+
      '<div class="kpi hr"><div class="l">Orders / hour</div><div class="v">'+o.orders_per_hr+'</div></div>'+
      '<div class="kpi act"><div class="l">Active hours</div><div class="v">'+o.active_hours+'</div></div>';
    var avg=o.avg_sec_order||0;
    document.getElementById('prows').innerHTML=(d.pickers.length?d.pickers.map(function(w){
      var cls=w.avg_sec_order<=avg?'fast':'slow';
      return '<tr><td><b>'+esc(w.picker)+'</b></td><td>'+w.orders+'</td><td>'+w.items+'</td><td class="'+cls+'">'+secFmt(w.avg_sec_order)+'</td><td>'+w.orders_per_hr+'</td><td>'+w.active_hours+'</td></tr>';
    }).join(''):'<tr><td colspan="6" class="muted">No picking records for this filter</td></tr>');
  });
}
function renderTeam(list,nameKey,valKey,unit,hrKey,selId){
  var el=document.getElementById('teamCmp');
  if(!list||!list.length){el.innerHTML='<div class="muted">No workers yet</div>';return}
  var srt=list.slice().sort(function(a,b){return (b[valKey]||0)-(a[valKey]||0)});
  var max=Math.max.apply(null,srt.map(function(w){return w[valKey]||0}))||1;
  el.innerHTML=srt.map(function(w){
    var nm=w[nameKey]||'',val=w[valKey]||0,pct=Math.max(2,Math.round(100*val/max));
    return '<div class="cmpRow" data-w="'+esc(nm)+'" style="display:flex;align-items:center;gap:10px;padding:5px 0;cursor:pointer">'+
      '<div style="width:120px;font-size:13px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="'+esc(nm)+'">'+esc(nm)+'</div>'+
      '<div style="flex:1;background:rgba(79,70,229,.08);border-radius:6px;height:22px"><div style="width:'+pct+'%;background:linear-gradient(90deg,#818cf8,#4f46e5);height:100%;border-radius:6px;min-width:4px"></div></div>'+
      '<div style="width:130px;text-align:right;font-size:12px;color:#586274">'+val.toLocaleString()+' '+unit+' · '+(w[hrKey]||0)+'/hr</div></div>';
  }).join('');
  Array.prototype.forEach.call(el.querySelectorAll('.cmpRow'),function(r){
    r.addEventListener('click',function(){var s=document.getElementById(selId);if(s){s.value=this.getAttribute('data-w');load();window.scrollTo({top:document.body.scrollHeight,behavior:'smooth'});}});
  });
}
function hms(s){s=Math.round(Number(s||0));if(s<=0)return '—';var h=Math.floor(s/3600),m=Math.round((s%3600)/60);return (h?h+'h ':'')+m+'m'}
function renderShift(shift,workerName){
  var b=document.getElementById('shiftBody');
  if(!workerName){b.innerHTML='<div class="muted">Select a single worker above to see their day-by-day shift: first vs last scan, the pick-vs-pack split, and the idle time in between.</div>';return}
  if(!shift||!shift.length){b.innerHTML='<div class="muted">No pick or pack activity for this person in the selected range.</div>';return}
  var legend='<div style="display:flex;gap:18px;margin-bottom:12px;font-size:12px;font-weight:700">'+
    '<span><span style="display:inline-block;width:11px;height:11px;background:#a5b4fc;border-radius:3px;margin-right:5px;vertical-align:-1px"></span>Picked</span>'+
    '<span><span style="display:inline-block;width:11px;height:11px;background:#4f46e5;border-radius:3px;margin-right:5px;vertical-align:-1px"></span>Packed</span></div>';
  var n=shift.length,bw=Math.max(22,Math.min(60,Math.floor(1100/n))),gap=10,W=n*(bw+gap)+50,H=230,top=16,bot=44;
  var max=Math.max.apply(null,shift.map(function(d){return d.picked+d.packed}))||1;
  var bars='',lbls='';
  shift.forEach(function(d,i){
    var x=44+i*(bw+gap),base=H-bot;
    var ph=Math.round((H-top-bot)*(d.picked/max)),kh=Math.round((H-top-bot)*(d.packed/max)),tot=d.picked+d.packed;
    bars+='<rect x="'+x+'" y="'+(base-ph)+'" width="'+bw+'" height="'+Math.max(0,ph)+'" fill="#a5b4fc" rx="2"><title>'+esc(d.date)+': '+d.picked+' picked</title></rect>';
    bars+='<rect class="packedBar" data-day="'+esc(d.date)+'" x="'+x+'" y="'+(base-ph-kh)+'" width="'+bw+'" height="'+Math.max(0,kh)+'" fill="#4f46e5" rx="2" style="cursor:pointer"><title>'+esc(d.date)+': '+d.packed+' packed — click to see the videos packed this day</title></rect>';
    lbls+='<text class="axtx" x="'+(x+bw/2)+'" y="'+(H-bot+14)+'" text-anchor="middle">'+esc((d.date||'').slice(5))+'</text>';
    if(ph+kh>14)bars+='<text class="axtx" x="'+(x+bw/2)+'" y="'+(base-ph-kh-4)+'" text-anchor="middle" style="fill:#64748b">'+tot+'</text>';
  });
  var grid='';for(var g=0;g<=4;g++){var gy=top+(H-top-bot)*g/4;grid+='<line class="axis" x1="40" y1="'+gy+'" x2="'+W+'" y2="'+gy+'"/><text class="axtx" x="0" y="'+(gy+3)+'">'+Math.round(max*(4-g)/4)+'</text>';}
  var chart='<div class="chart-wrap"><svg width="'+W+'" height="'+H+'" viewBox="0 0 '+W+' '+H+'">'+grid+bars+lbls+'</svg></div>';
  var hint='<div style="font-size:12px;color:#6b7280;margin-top:6px">Tip: click the packed (dark) part of a bar to see the videos '+esc(workerName)+' packed that day.</div>';
  b.innerHTML=legend+chart+hint;
  Array.prototype.forEach.call(document.querySelectorAll('#shiftBody .packedBar'),function(el){
    el.addEventListener('click',function(){
      var day=this.getAttribute('data-day');
      window.location.href='/dashboard?worker='+encodeURIComponent(workerName)+'&date='+encodeURIComponent(day);
    });
  });
}
function renderChart(days){
  if(!days||!days.length){document.getElementById('chart').innerHTML='<div class="muted">No data</div>';return}
  var n=days.length,bw=Math.max(20,Math.min(60,Math.floor(1100/n))),gap=8,W=n*(bw+gap)+50,H=220,top=14,bot=42;
  var max=Math.max.apply(null,days.map(function(d){return d.packages}))||1;
  var bars='',lbls='';
  days.forEach(function(d,i){
    var bh=Math.round((H-top-bot)*(d.packages/max)),x=44+i*(bw+gap),y=H-bot-bh;
    bars+='<rect class="bar" x="'+x+'" y="'+y+'" width="'+bw+'" height="'+Math.max(1,bh)+'" rx="3"><title>'+esc(d.date)+': '+d.packages+' pkgs · avg '+secFmt(d.avg_sec_pkg)+'</title></rect>';
    lbls+='<text class="axtx" x="'+(x+bw/2)+'" y="'+(H-bot+14)+'" text-anchor="middle">'+esc((d.date||'').slice(5))+'</text>';
    if(bh>14)bars+='<text class="axtx" x="'+(x+bw/2)+'" y="'+(y-4)+'" text-anchor="middle" style="fill:#64748b">'+d.packages+'</text>';
  });
  var grid='';for(var g=0;g<=4;g++){var gy=top+(H-top-bot)*g/4;grid+='<line class="axis" x1="40" y1="'+gy+'" x2="'+W+'" y2="'+gy+'"/><text class="axtx" x="0" y="'+(gy+3)+'">'+Math.round(max*(4-g)/4)+'</text>';}
  document.getElementById('chart').innerHTML='<svg width="'+W+'" height="'+H+'" viewBox="0 0 '+W+' '+H+'">'+grid+bars+lbls+'</svg>';
}
['fWorker','fStation','fFrom','fTo'].forEach(function(id){document.getElementById(id).addEventListener('change',load)});
document.getElementById('clr').addEventListener('click',function(){['fWorker','fStation','fFrom','fTo'].forEach(function(id){document.getElementById(id).value=''});load()});
load();
</script></body></html>'''


# ── SETTINGS — central hub for all app configuration ──
SETTINGS_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Settings</title>
__NAVBAR_CSS__
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#ffffff;color:#1a2130;min-height:100vh}
.page-hdr{padding:24px 28px 8px;max-width:1100px;margin:0 auto}
.page-title{font-size:22px;font-weight:800}.page-title span{color:#4f46e5;margin-left:8px;font-weight:600;font-size:14px}
.wrap{max-width:1100px;margin:0 auto;padding:8px 28px 40px}
.card{background:#ffffff;border:1px solid rgba(17,24,39,0.096);border-radius:16px;padding:20px 22px;margin-bottom:20px}
.card h2{font-size:14px;font-weight:800;color:#4f46e5;text-transform:uppercase;letter-spacing:.6px;margin-bottom:6px}
.desc{font-size:13px;color:#586274;margin-bottom:14px}
.links{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}
.lnk{display:block;background:rgba(17,24,39,0.048);border:1px solid rgba(17,24,39,0.128);border-radius:12px;padding:16px 18px;text-decoration:none;color:#1a2130;transition:all .12s}
.lnk:hover{border-color:rgba(79,70,229,.5);background:rgba(79,70,229,.08)}
.lnk .t{font-size:15px;font-weight:800}.lnk .s{font-size:12.5px;color:#586274;margin-top:3px}
input,select{background:#ffffff;border:2px solid rgba(17,24,39,0.128);border-radius:10px;padding:10px 13px;font-size:14px;color:#1a2130;font-family:inherit;outline:none;width:100%}
input:focus,select:focus{border-color:#4f46e5}
label{display:block;font-size:11px;font-weight:700;color:#6b7280;margin:8px 0 4px;text-transform:uppercase;letter-spacing:.4px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:10px;max-width:420px}
.btn{border:none;border-radius:10px;padding:11px 20px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit}
.btn-p{background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff}.btn-s{background:rgba(17,24,39,0.128);color:#1a2130;border:1px solid rgba(17,24,39,0.16)}
.btn-x{background:rgba(244,63,94,.14);color:#e11d48;border:1px solid rgba(244,63,94,.3);border-radius:8px;padding:6px 10px;font-size:12px;cursor:pointer}
.pkgrow{display:grid;grid-template-columns:1.6fr .8fr .8fr .8fr .8fr auto;gap:8px;margin-bottom:8px;align-items:center}
.pkghdr{display:grid;grid-template-columns:1.6fr .8fr .8fr .8fr .8fr auto;gap:8px;margin-bottom:4px}
.pkghdr span{font-size:10px;color:#6b7280;font-weight:700;text-transform:uppercase;letter-spacing:.4px}
.toast{position:fixed;bottom:24px;right:24px;background:#10b981;color:#fff;padding:14px 22px;border-radius:10px;font-weight:700;z-index:100;display:none}.toast.err{background:#f43f5e}
/* Settings tabs */
.tabs{display:flex;gap:4px;flex-wrap:wrap;border-bottom:1px solid rgba(17,24,39,0.128);margin-bottom:22px}
.tab{appearance:none;background:none;border:none;border-bottom:2px solid transparent;color:#586274;font-family:inherit;font-size:14px;font-weight:700;padding:11px 16px;cursor:pointer;border-radius:8px 8px 0 0;transition:all .15s;white-space:nowrap;min-height:44px}
.tab:hover{color:#1a2130;background:rgba(17,24,39,0.048)}
.tab.active{color:var(--brand,#d9748f);border-bottom-color:var(--brand,#d9748f)}
.tab-panel{display:none;animation:tabIn .2s ease-out}
.tab-panel.active{display:block}
@keyframes tabIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
:where(a,button,input,select,[tabindex]):focus-visible{outline:2px solid var(--brand,#d9748f);outline-offset:2px}
</style></head><body>
__NAVBAR__
<div class="page-hdr"><div class="page-title">⚙️ Settings <span>__NAME__</span></div></div>
<div class="wrap">

<div class="tabs" role="tablist">
  <button class="tab active" data-tab="branding">🎨 Branding</button>
  <button class="tab" data-tab="team">👥 Team &amp; Access</button>
  <button class="tab" data-tab="packages">📦 Packages</button>
  <button class="tab" data-tab="integrations">🔗 Integrations</button>
</div>

<div class="tab-panel active" data-panel="branding">
<div class="card">
  <h2>🎨 Branding &amp; white-label</h2>
  <div class="desc">Your organization's identity across the app — shown in the top bar and login.</div>
  <div class="grid2" style="max-width:560px">
    <div><label>Company name</label><input id="bCompany" maxlength="80" placeholder="Your company name"></div>
    <div><label>Brand color</label><input id="bColor" type="color" value="#d9748f" style="height:44px;padding:4px"></div>
    <div><label>Wordmark (top-left)</label><input id="bMark" maxlength="24" placeholder="Short brand mark"></div>
    <div><label>Sub-label</label><input id="bSub" maxlength="40" placeholder="Employee Hub"></div>
  </div>
  <div style="max-width:560px"><label>Logo URL (https only, optional)</label><input id="bLogo" maxlength="500" placeholder="https://…/logo.png"></div>
  <button class="btn btn-p" id="saveBrand" style="margin-top:12px">Save branding</button>
  <span class="desc" style="margin-left:10px">Changes apply on your next page load.</span>
</div>
</div><!-- /branding panel -->

<div class="tab-panel" data-panel="team">
<div class="card">
  <h2>👥 Team &amp; access</h2>
  <div class="desc">Manage who can log in and what each role can do.</div>
  <div class="links">
    <a class="lnk" href="/users"><div class="t">Users</div><div class="s">Add / edit staff accounts &amp; roles</div></a>
    <a class="lnk" href="/users/badges"><div class="t">Badges</div><div class="s">Printable scan-to-login badges</div></a>
    <a class="lnk" href="/admin/permissions"><div class="t">Permissions &amp; Manager PIN</div><div class="s">Role matrix, ship-from address, PIN</div></a>
    <a class="lnk" href="/admin/hires"><div class="t">New Hires · Onboarding</div><div class="s">Track new-employee paperwork</div></a>
  </div>
</div>
</div><!-- /team panel -->

<div class="tab-panel" data-panel="packages">
<div class="card">
  <h2>📦 Package presets</h2>
  <div class="desc">Common box sizes, reused when buying labels (Inbound / Giveaways). Dimensions in inches.</div>
  <div class="grid2" style="margin-bottom:12px"><div><label>Weight unit</label>
    <select id="wUnit"><option value="oz">Ounces (oz)</option><option value="lb">Pounds (lb)</option></select></div></div>
  <div class="pkghdr"><span>Name</span><span id="hW">Weight (oz)</span><span>L (in)</span><span>W (in)</span><span>H (in)</span><span></span></div>
  <div id="pkgList"></div>
  <button class="btn btn-s" id="addPkg" style="margin-top:6px">+ Add package</button>
  <button class="btn btn-p" id="savePkgs" style="margin-top:6px;margin-left:8px">Save presets</button>
</div>
</div><!-- /packages panel -->

<div class="tab-panel" data-panel="integrations">
<div class="card">
  <h2>🔗 More configuration</h2>
  <div class="desc">Other settings live on their own screens for now.</div>
  <div class="links">
    <a class="lnk" href="/admin/hosts"><div class="t">Commission rule</div><div class="s">Host commission model (in Host Analytics)</div></a>
    <a class="lnk" href="/admin/inventory"><div class="t">Product catalog</div><div class="s">SKUs, barcodes, costs, CSV import</div></a>
  </div>
</div>
</div><!-- /integrations panel -->

</div>
<div class="toast" id="t"></div>
<script>
function toast(m,e){var x=document.getElementById('t');x.textContent=m;x.className=e?'toast err':'toast';x.style.display='block';setTimeout(function(){x.style.display='none'},2500)}
function esc(s){var d=document.createElement('div');d.textContent=(s==null?'':String(s));return d.innerHTML}
// ── Tabs ──
function showTab(name){
  document.querySelectorAll('.tab').forEach(function(t){t.classList.toggle('active',t.dataset.tab===name)});
  document.querySelectorAll('.tab-panel').forEach(function(p){p.classList.toggle('active',p.dataset.panel===name)});
  try{localStorage.setItem('settingsTab',name)}catch(e){}
  if(location.hash.slice(1)!==name) history.replaceState(null,'','#'+name);
}
document.querySelectorAll('.tab').forEach(function(t){t.addEventListener('click',function(){showTab(t.dataset.tab)})});
(function(){var valid=['branding','team','packages','integrations'];
  var want=location.hash.slice(1)||localStorage.getItem('settingsTab')||'branding';
  if(valid.indexOf(want)<0)want='branding'; showTab(want);})();
var UNIT=localStorage.getItem('wunit')||'oz';
function fromOz(oz){if(oz===''||oz==null||!oz)return (oz===0||oz==='0')?0:'';return UNIT==='lb'?Math.round((oz/16)*1000)/1000:oz;}
function toOz(v){var n=parseFloat(v||0);return UNIT==='lb'?n*16:n;}
function wLabel(){return UNIT==='lb'?'lb':'oz';}
var PKGS=[];
function renderPkgs(){
  document.getElementById('hW').textContent='Weight ('+wLabel()+')';
  document.getElementById('wUnit').value=UNIT;
  document.getElementById('pkgList').innerHTML=PKGS.map(function(p,i){
    return '<div class="pkgrow"><input value="'+esc(p.name)+'" data-i="'+i+'" data-k="name" placeholder="Name">'+
      '<input type="number" step="0.01" value="'+(fromOz(p.weight))+'" data-i="'+i+'" data-k="weight" placeholder="'+wLabel()+'">'+
      '<input type="number" value="'+(p.length||'')+'" data-i="'+i+'" data-k="length" placeholder="L">'+
      '<input type="number" value="'+(p.width||'')+'" data-i="'+i+'" data-k="width" placeholder="W">'+
      '<input type="number" value="'+(p.height||'')+'" data-i="'+i+'" data-k="height" placeholder="H">'+
      '<button class="btn-x" onclick="delPkg('+i+')">✕</button></div>';
  }).join('');
  document.getElementById('pkgList').querySelectorAll('input').forEach(function(el){
    el.addEventListener('input',function(){var k=el.dataset.k,i=+el.dataset.i;
      PKGS[i][k]=(k==='name')?el.value:(k==='weight'?toOz(el.value):parseFloat(el.value||'0'));});
  });
}
function delPkg(i){PKGS.splice(i,1);renderPkgs()}
document.getElementById('addPkg').addEventListener('click',function(){PKGS.push({name:'Box',weight:0,length:0,width:0,height:0});renderPkgs()});
document.getElementById('wUnit').addEventListener('change',function(){UNIT=this.value;localStorage.setItem('wunit',UNIT);renderPkgs();});
document.getElementById('savePkgs').addEventListener('click',function(){
  fetch('/api/packages',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({packages:PKGS})}).then(function(r){return r.json()}).then(function(d){toast(d.ok?'Presets saved ✓':'Failed',!d.ok)});
});
fetch('/api/packages').then(function(r){return r.json()}).then(function(d){PKGS=d.packages||[];renderPkgs()});
// ── Branding ──
fetch('/api/org/branding').then(function(r){return r.json()}).then(function(b){
  document.getElementById('bCompany').value=b.company_name||'';
  document.getElementById('bMark').value=b.brand_mark||'';
  document.getElementById('bSub').value=b.brand_sub||'';
  document.getElementById('bColor').value=/^#[0-9a-fA-F]{6}$/.test(b.brand_color||'')?b.brand_color:'#d9748f';
  document.getElementById('bLogo').value=b.logo_url||'';
}).catch(function(){});
document.getElementById('saveBrand').addEventListener('click',function(){
  var body={company_name:document.getElementById('bCompany').value,brand_mark:document.getElementById('bMark').value,
    brand_sub:document.getElementById('bSub').value,brand_color:document.getElementById('bColor').value,
    logo_url:document.getElementById('bLogo').value};
  fetch('/api/org/branding',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
    .then(function(r){return r.json()}).then(function(d){toast(d.ok?'Branding saved ✓':'Failed',!d.ok)})
    .catch(function(){toast('Failed',true)});
});
</script></body></html>'''


# ── OPERATIONS HUB — one landing page for all warehouse tools, grouped into
# tabs (Shows / Warehouse / Shipping / Insights). Tabs + panels are injected by
# app.py per role so admin-only cards (Profit, Inventory…) stay hidden from CS.
OPERATIONS_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Operations</title>
__NAVBAR_CSS__
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#ffffff;color:#1a2130;min-height:100vh}
.page-hdr{padding:24px 28px 8px;max-width:1200px;margin:0 auto}
.page-title{font-size:22px;font-weight:800}.page-title span{color:var(--text-dim,#64748b);margin-left:8px;font-weight:600;font-size:14px}
.wrap{max-width:1200px;margin:0 auto;padding:8px 28px 44px}
.tabs{display:flex;gap:4px;flex-wrap:wrap;border-bottom:1px solid rgba(17,24,39,0.128);margin-bottom:22px}
.tab{appearance:none;background:none;border:none;border-bottom:2px solid transparent;color:#586274;font-family:inherit;font-size:14px;font-weight:700;padding:11px 16px;cursor:pointer;border-radius:8px 8px 0 0;transition:all .15s;white-space:nowrap;min-height:44px}
.tab:hover{color:#1a2130;background:rgba(17,24,39,0.048)}
.tab.active{color:var(--brand,#d9748f);border-bottom-color:var(--brand,#d9748f)}
.tab-panel{display:none;animation:tabIn .2s ease-out}
.tab-panel.active{display:block}
@keyframes tabIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(258px,1fr));gap:14px}
.opcard{display:flex;flex-direction:column;gap:5px;background:rgba(17,24,39,0.048);border:1px solid rgba(17,24,39,0.128);border-radius:14px;padding:18px 18px 16px;text-decoration:none;color:#1a2130;transition:all .14s}
.opcard:hover{border-color:var(--brand,#d9748f);background:rgba(17,24,39,0.088);transform:translateY(-2px)}
.opcard .ic{font-size:22px;margin-bottom:4px}
.opcard .t{font-size:15.5px;font-weight:800}
.opcard .s{font-size:12.5px;color:var(--text-muted,#586274);line-height:1.5}
:where(a,button,input,select,[tabindex]):focus-visible{outline:2px solid var(--brand,#d9748f);outline-offset:2px}
</style></head><body>
__NAVBAR__
<div class="page-hdr"><div class="page-title">📦 Operations <span>__NAME__</span></div></div>
<div class="wrap">
<div class="tabs" role="tablist">__OPS_TABS__</div>
__OPS_PANELS__
</div>
<script>
function showTab(name){
  document.querySelectorAll('.tab').forEach(function(t){t.classList.toggle('active',t.dataset.tab===name)});
  document.querySelectorAll('.tab-panel').forEach(function(p){p.classList.toggle('active',p.dataset.panel===name)});
  try{localStorage.setItem('opsTab',name)}catch(e){}
  if(location.hash.slice(1)!==name) history.replaceState(null,'','#'+name);
}
document.querySelectorAll('.tab').forEach(function(t){t.addEventListener('click',function(){showTab(t.dataset.tab)})});
(function(){var tabs=[].map.call(document.querySelectorAll('.tab'),function(t){return t.dataset.tab});
  var want=location.hash.slice(1)||localStorage.getItem('opsTab')||(tabs[0]||'');
  if(tabs.indexOf(want)<0)want=tabs[0]||''; if(want)showTab(want);})();
</script></body></html>'''


# ── PRE-SHOW SCAN — bind generic stickers (sticker#, Part) to real products ──
# Warehouse workflow: end of show, before import. Go Part by Part, sticker 1→N,
# scan each product's real barcode (or pick from catalog) to give it an identity.
PRESHOW_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Match Products</title>
__NAVBAR_CSS__
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#ffffff;color:#1a2130;min-height:100vh}
.page-hdr{padding:20px 24px 6px;max-width:1100px;margin:0 auto;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
.page-title{font-size:22px;font-weight:800}.page-title span{color:#4f46e5;margin-left:8px;font-weight:600;font-size:14px}
.langbtn{background:rgba(17,24,39,0.128);border:1px solid rgba(17,24,39,0.16);color:#1a2130;border-radius:8px;padding:7px 13px;font-size:13px;font-weight:700;cursor:pointer;font-family:inherit}
.wrap{max-width:1100px;margin:0 auto;padding:8px 24px 40px}
.card{background:#ffffff;border:1px solid rgba(17,24,39,0.096);border-radius:16px;padding:18px 20px;margin-bottom:18px}
.card h2{font-size:13px;font-weight:800;color:#4f46e5;text-transform:uppercase;letter-spacing:.6px;margin-bottom:12px}
.row{display:flex;gap:12px;align-items:end;flex-wrap:wrap}
.f label{display:block;font-size:11px;font-weight:700;color:#6b7280;margin-bottom:5px;text-transform:uppercase;letter-spacing:.4px}
.f input,.f select{background:#ffffff;border:2px solid rgba(17,24,39,0.128);border-radius:10px;padding:12px 14px;font-size:16px;color:#1a2130;font-family:inherit;outline:none}
.f input:focus,.f select:focus{border-color:#4f46e5}
.big input{font-size:26px;font-weight:800;padding:14px 16px;letter-spacing:1px}
.btn{border:none;border-radius:10px;padding:12px 20px;font-size:15px;font-weight:700;cursor:pointer;font-family:inherit}
.btn-p{background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff}.btn-s{background:rgba(17,24,39,0.128);color:#1a2130;border:1px solid rgba(17,24,39,0.16)}
.btn:disabled{opacity:.4;cursor:not-allowed}
.scanbox{display:flex;gap:14px;align-items:stretch;flex-wrap:wrap}
.scanbox .cur{background:linear-gradient(135deg,rgba(79,70,229,.25),rgba(124,58,237,.18));border:2px solid #4f46e5;border-radius:14px;padding:12px 18px;text-align:center;min-width:150px}
.scanbox .cur .lab{font-size:11px;color:#4f46e5;text-transform:uppercase;letter-spacing:.6px;font-weight:700}
.scanbox .cur .numin{width:120px;background:#ffffff;border:2px solid rgba(124,58,237,.5);border-radius:10px;color:#141b26;font-size:38px;font-weight:900;text-align:center;font-family:inherit;outline:none;padding:2px 0;margin:3px 0}
.scanbox .cur .numin:focus{border-color:#7c3aed}
.scanbox .cur .pt{font-size:13px;color:#6366f1;font-weight:700}
.lane{background:rgba(96,165,250,.1);border:1px solid rgba(96,165,250,.3);color:#2563eb;padding:9px 14px;border-radius:10px;margin-bottom:14px;font-size:13px}
.scanbox .grow{flex:1;min-width:240px}
.last{margin-top:14px;border-radius:12px;padding:14px 16px;display:none;align-items:center;gap:14px}
.last.ok{display:flex;background:rgba(16,185,129,.12);border:1px solid rgba(16,185,129,.35)}
.last.err{display:flex;background:rgba(244,63,94,.12);border:1px solid rgba(244,63,94,.4)}
.last .thumb{width:56px;height:56px;border-radius:10px;object-fit:cover;background:rgba(17,24,39,0.096)}
.last .nm{font-size:17px;font-weight:800}.last .sub{font-size:13px;color:#64748b}
.pill{display:inline-block;background:rgba(17,24,39,0.16);border-radius:20px;padding:3px 11px;font-size:12px;font-weight:700;margin-left:8px}
table{width:100%;border-collapse:collapse}th,td{padding:9px 11px;font-size:13px;border-bottom:1px solid rgba(17,24,39,0.096);text-align:left}
th{font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px}
.thumb-s{width:34px;height:34px;border-radius:7px;object-fit:cover;background:rgba(17,24,39,0.08)}
.sku{font-family:monospace;color:#4f46e5;font-weight:700}
.muted{color:#6b7280}
.del{color:#f43f5e;cursor:pointer;font-weight:700}
.toast{position:fixed;bottom:24px;right:24px;background:#10b981;color:#fff;padding:14px 22px;border-radius:10px;font-weight:700;z-index:100;display:none}.toast.err{background:#f43f5e}
.modal{position:fixed;inset:0;background:rgba(0,0,0,.6);display:none;align-items:center;justify-content:center;z-index:200;padding:20px}
.modal.on{display:flex}
.modal .box{background:#f6f7f9;border:1px solid rgba(17,24,39,0.16);border-radius:16px;padding:22px;max-width:560px;width:100%;max-height:80vh;overflow:auto}
.modal h3{font-size:16px;font-weight:800;margin-bottom:12px}
.pickrow{display:flex;align-items:center;gap:12px;padding:9px;border-radius:10px;cursor:pointer;border:1px solid transparent}
.pickrow:hover{background:rgba(17,24,39,0.08);border-color:rgba(79,70,229,.4)}
</style></head><body>
__NAVBAR__
<div class="page-hdr"><div class="page-title">🔗 <span data-i18n="title">Match Sold Products</span> <span>__NAME__</span></div>
<button class="langbtn" onclick="toggleLang()" id="langBtn">ES</button></div>
<div class="wrap">

<div class="card">
  <h2 data-i18n="step1">1 · Pick the show & your Part (lane)</h2>
  <div class="row">
    <div class="f grow" style="flex:1;min-width:240px"><label data-i18n="show">Show</label>
      <select id="showSel" style="width:100%"><option value="" data-i18n="pickshow">Pick a show…</option></select></div>
    <div class="f"><label data-i18n="part">Part (your lane)</label>
      <select id="partSel"><option value="1">Part 1</option><option value="2">Part 2</option><option value="3">Part 3</option><option value="4">Part 4</option><option value="5">Part 5</option><option value="0" data-i18n="nopart">No part</option></select></div>
    <div class="f"><label data-i18n="startat">Start at sticker #</label><input id="startSku" type="number" value="1" style="width:120px"></div>
  </div>
  <div class="lane" data-i18n="lanehint">💡 Each Part is its own lane — several workers can run Part 1, Part 2, Part 3… at the same time on different iPads without clashing.</div>
  <div class="muted" id="progress" style="font-size:13px"></div>
</div>

<div class="card" id="scanCard" style="opacity:.45;pointer-events:none">
  <h2 data-i18n="step2">2 · For each product on the table: scan its real barcode</h2>
  <div class="scanbox">
    <div class="cur"><div class="lab" data-i18n="sticker">Sticker #</div><input class="numin" id="curNum" type="number" value="1"><div class="pt" id="curPart">Part 1</div></div>
    <div class="grow f big"><label data-i18n="scanbarcode">Scan product barcode (or type SKU)</label>
      <input id="code" placeholder="📷 …" style="width:100%" autocomplete="off"></div>
    <div class="f"><label>&nbsp;</label><button class="btn btn-s" id="pickBtn" data-i18n="pickcat">🔍 Search catalog</button></div>
  </div>
  <div class="last" id="last"></div>
  <div class="muted" style="margin-top:12px;font-size:12.5px" data-i18n="hint">After each scan the sticker # advances by 1. Type a different number anytime — handy since cancelled items were already pulled, so numbers may skip. If a barcode won\\'t scan, tap Search catalog and find it by name, a few barcode digits, or SKU.</div>
</div>

<div class="card">
  <h2><span data-i18n="linked">Linked this show</span> <span class="pill" id="cnt">0</span></h2>
  <table><thead><tr><th data-i18n="thpart">Part</th><th data-i18n="thsticker">Sticker</th><th></th><th data-i18n="thproduct">Product</th><th data-i18n="thby">By</th><th></th></tr></thead>
  <tbody id="rows"><tr><td colspan="6" class="muted" data-i18n="none">Pick a show to begin.</td></tr></tbody></table>
</div>
</div>

<div class="modal" id="pickModal"><div class="box">
  <h3 data-i18n="pickttl">Pick product from catalog</h3>
  <input id="pickQ" placeholder="Search name / SKU / barcode" style="width:100%;background:#ffffff;border:2px solid rgba(17,24,39,0.128);border-radius:10px;padding:11px 14px;font-size:15px;color:#1a2130;font-family:inherit;outline:none;margin-bottom:12px">
  <div id="pickRows"></div>
  <div style="margin-top:14px;display:flex;gap:10px;justify-content:space-between">
    <button class="btn btn-s" id="newProdBtn" data-i18n="newprod">+ New product</button>
    <button class="btn btn-s" onclick="closePick()" data-i18n="cancel">Cancel</button>
  </div>
</div></div>

<div class="toast" id="t"></div>
<script>
var T={en:{title:"Match Sold Products",step1:"1 · Pick the show & your Part (lane)",show:"Show",pickshow:"Pick a show…",part:"Part (your lane)",nopart:"No part",startat:"Start at sticker #",step2:"2 · For each product on the table: scan its real barcode",sticker:"Sticker #",scanbarcode:"Scan product barcode (or type SKU)",pickcat:"🔍 Search catalog",lanehint:"💡 Each Part is its own lane — several workers can run Part 1, Part 2, Part 3… at the same time on different iPads without clashing.",hint:"After each scan the sticker # advances by 1. Type a different number anytime — handy since cancelled items were already pulled, so numbers may skip. If a barcode won't scan, tap Search catalog and find it by name, a few barcode digits, or SKU.",linked:"Matched this show",thpart:"Part",thsticker:"Sticker",thproduct:"Product",thby:"By",none:"Pick a show to begin.",pickttl:"Find product in catalog",newprod:"+ New product",cancel:"Cancel",notfound:"Not in catalog — search or add it",linkedok:"Matched ✓",removed:"Removed",chooseshow:"Choose a show first"},
es:{title:"Vincular productos vendidos",step1:"1 · Elige el show y tu Parte (carril)",show:"Show",pickshow:"Elige un show…",part:"Parte (tu carril)",nopart:"Sin parte",startat:"Empezar en etiqueta #",step2:"2 · Por cada producto en la mesa: escanea su código real",sticker:"Etiqueta #",scanbarcode:"Escanea el código (o escribe SKU)",pickcat:"🔍 Buscar catálogo",lanehint:"💡 Cada Parte es su propio carril — varios trabajadores pueden hacer Parte 1, Parte 2, Parte 3… al mismo tiempo en distintos iPads sin chocar.",hint:"Tras cada escaneo el número avanza en 1. Escribe otro número cuando quieras — útil porque los cancelados ya se retiraron y los números pueden saltarse. Si un código no escanea, toca Buscar catálogo y encuéntralo por nombre, unos dígitos del código, o SKU.",linked:"Vinculados este show",thpart:"Parte",thsticker:"Etiqueta",thproduct:"Producto",thby:"Por",none:"Elige un show para empezar.",pickttl:"Buscar producto en el catálogo",newprod:"+ Nuevo producto",cancel:"Cancelar",notfound:"No está en el catálogo — búscalo o agrégalo",linkedok:"Vinculado ✓",removed:"Eliminado",chooseshow:"Elige un show primero"}};
var lang=localStorage.getItem('lang')||'en';
function t(k){return (T[lang]&&T[lang][k])||T.en[k]||k}
function applyLang(){document.querySelectorAll('[data-i18n]').forEach(function(e){e.textContent=t(e.getAttribute('data-i18n'))});document.getElementById('langBtn').textContent=lang==='en'?'ES':'EN';document.documentElement.lang=lang}
function toggleLang(){lang=lang==='en'?'es':'en';localStorage.setItem('lang',lang);applyLang()}
function toast(m,e){var x=document.getElementById('t');x.textContent=m;x.className=e?'toast err':'toast';x.style.display='block';setTimeout(function(){x.style.display='none'},2500)}
function esc(s){var d=document.createElement('div');d.textContent=(s==null?'':String(s));return d.innerHTML}

function show(){return document.getElementById('showSel').value}
function part(){return parseInt(document.getElementById('partSel').value||'0')}
function partLabel(p){return p?('Part '+p):t('nopart')}
function curVal(){return parseInt(document.getElementById('curNum').value||'1')}
function setCur(n){document.getElementById('curNum').value=n;document.getElementById('curPart').textContent=partLabel(part())}

fetch('/api/shows/recent').then(function(r){return r.json()}).then(function(shows){
  var sel=document.getElementById('showSel');
  (shows||[]).forEach(function(s){var o=document.createElement('option');o.value=s;o.textContent=s;sel.appendChild(o)});
});

function enableScan(on){var c=document.getElementById('scanCard');c.style.opacity=on?'1':'.45';c.style.pointerEvents=on?'auto':'none';if(on){document.getElementById('code').focus()}}
function onShowChange(){if(show()){enableScan(true);refresh();setCur(parseInt(document.getElementById('startSku').value||'1'))}else{enableScan(false)}}
document.getElementById('showSel').addEventListener('change',onShowChange);
document.getElementById('partSel').addEventListener('change',function(){setCur(parseInt(document.getElementById('startSku').value||'1'));refresh()});
document.getElementById('startSku').addEventListener('change',function(){setCur(parseInt(document.getElementById('startSku').value||'1'))});

function bind(payload){
  payload.show=show();payload.part=part();payload.sticker=String(curVal());
  return fetch('/api/preshow/map',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}).then(function(r){return r.json()});
}
function showLast(ok,html){var l=document.getElementById('last');l.className='last '+(ok?'ok':'err');l.innerHTML=html}

document.getElementById('code').addEventListener('keydown',function(e){
  if(e.key!=='Enter')return;
  var code=this.value.trim();if(!code){return}
  if(!show()){toast(t('chooseshow'),true);return}
  var self=this;
  bind({code:code}).then(function(d){
    if(d.ok){
      var img=d.product.image_url?'<img class="thumb" src="'+esc(d.product.image_url)+'">':'<div class="thumb"></div>';
      showLast(true,img+'<div><div class="nm">'+esc(d.product.name||d.product.sku)+'</div><div class="sub">'+t('linkedok')+' → '+t('sticker')+' '+esc(d.sticker)+' · '+esc(partLabel(d.part))+' · <span class="sku">'+esc(d.product.sku)+'</span></div></div>');
      self.value='';setCur(curVal()+1);document.getElementById('startSku').value=curVal();refresh();self.focus();
    } else if(d.not_found){
      openPick(code);
    } else { toast(d.error||'Failed',true) }
  });
});

document.getElementById('pickBtn').addEventListener('click',function(){openPick('')});

// ── catalog pick / add modal ──
var pendingCode='';
function openPick(code){pendingCode=code;document.getElementById('pickModal').classList.add('on');var q=document.getElementById('pickQ');q.value='';document.getElementById('pickRows').innerHTML='';q.focus();if(code){toast(t('notfound'),true)}}
function closePick(){document.getElementById('pickModal').classList.remove('on');document.getElementById('code').focus()}
var pq=null;
document.getElementById('pickQ').addEventListener('input',function(){clearTimeout(pq);var v=this.value.trim();pq=setTimeout(function(){
  fetch('/api/products'+(v?('?q='+encodeURIComponent(v)):'')).then(function(r){return r.json()}).then(function(rows){
    document.getElementById('pickRows').innerHTML=(rows||[]).map(function(p){
      var img=p.image_url?'<img class="thumb-s" src="'+esc(p.image_url)+'">':'<div class="thumb-s"></div>';
      return '<div class="pickrow" onclick="pickProduct(\\''+esc(p.sku).replace(/'/g,"")+'\\')">'+img+'<div><div style="font-weight:700">'+esc(p.name||p.sku)+'</div><div class="sub muted"><span class="sku">'+esc(p.sku)+'</span> · '+esc(p.barcode||'no barcode')+'</div></div></div>';
    }).join('')||'<div class="muted">No matches</div>';
  });
},200)});
function pickProduct(sku){
  bind({product_sku:sku}).then(function(d){
    if(d.ok){closePick();var img=d.product.image_url?'<img class="thumb" src="'+esc(d.product.image_url)+'">':'<div class="thumb"></div>';
      showLast(true,img+'<div><div class="nm">'+esc(d.product.name||d.product.sku)+'</div><div class="sub">'+t('linkedok')+' → '+t('sticker')+' '+esc(d.sticker)+'</div></div>');
      setCur(curVal()+1);document.getElementById('startSku').value=curVal();refresh();
    } else toast(d.error||'Failed',true);
  });
}
document.getElementById('newProdBtn').addEventListener('click',function(){
  var name=prompt('Product name:');if(!name)return;
  fetch('/api/products',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:name.trim(),barcode:pendingCode})})
   .then(function(r){return r.json()}).then(function(d){if(d.ok){pickProduct(d.sku)}else toast(d.error||'Failed',true)});
});

function refresh(){
  if(!show()){return}
  fetch('/api/preshow/map?show='+encodeURIComponent(show())).then(function(r){return r.json()}).then(function(d){
    document.getElementById('cnt').textContent=d.count||0;
    document.getElementById('progress').textContent=(d.count||0)+' '+t('linked').toLowerCase();
    var rows=d.maps||[];
    if(!rows.length){document.getElementById('rows').innerHTML='<tr><td colspan="6" class="muted">'+t('none')+'</td></tr>';return}
    document.getElementById('rows').innerHTML=rows.map(function(m){
      var img=m.image_url?'<img class="thumb-s" src="'+esc(m.image_url)+'">':'<div class="thumb-s"></div>';
      return '<tr><td>'+esc(partLabel(m.part))+'</td><td class="sku">'+esc(m.sticker)+'</td><td>'+img+'</td>'+
        '<td>'+esc(m.name||m.product_sku)+' <span class="sku">'+esc(m.product_sku)+'</span></td>'+
        '<td class="muted">'+esc(m.mapped_by||'')+'</td>'+
        '<td><span class="del" onclick="unmap(\\''+esc(m.sticker)+'\\','+m.part+')">✕</span></td></tr>';
    }).join('');
  });
}
function unmap(sticker,p){
  fetch('/api/preshow/map',{method:'DELETE',headers:{'Content-Type':'application/json'},body:JSON.stringify({show:show(),sticker:sticker,part:p})})
   .then(function(r){return r.json()}).then(function(){toast(t('removed'));refresh()});
}
applyLang();
</script></body></html>'''


# ── INBOUND — buy labels for supplier → warehouse shipments + package presets ──
INBOUND_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Inbound Shipments</title>
__NAVBAR_CSS__
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#ffffff;color:#1a2130;min-height:100vh}
.page-hdr{padding:24px 28px 8px;max-width:1100px;margin:0 auto}
.page-title{font-size:22px;font-weight:800}.page-title span{color:#4f46e5;margin-left:8px;font-weight:600;font-size:14px}
.wrap{max-width:1100px;margin:0 auto;padding:8px 28px 40px}
.card{background:#ffffff;border:1px solid rgba(17,24,39,0.096);border-radius:16px;padding:20px 22px;margin-bottom:20px}
.card h2{font-size:14px;font-weight:800;color:#4f46e5;text-transform:uppercase;letter-spacing:.6px;margin-bottom:6px}
.desc{font-size:13px;color:#586274;margin-bottom:14px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
input,select{background:#ffffff;border:2px solid rgba(17,24,39,0.128);border-radius:10px;padding:10px 13px;font-size:14px;color:#1a2130;font-family:inherit;outline:none;width:100%}
input:focus,select:focus{border-color:#4f46e5}
label{display:block;font-size:11px;font-weight:700;color:#6b7280;margin:8px 0 4px;text-transform:uppercase;letter-spacing:.4px}
.btn{border:none;border-radius:10px;padding:11px 20px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit}
.btn-p{background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff}.btn-s{background:rgba(17,24,39,0.128);color:#1a2130;border:1px solid rgba(17,24,39,0.16)}
.btn-x{background:rgba(244,63,94,.14);color:#e11d48;border:1px solid rgba(244,63,94,.3);border-radius:8px;padding:6px 10px;font-size:12px;cursor:pointer}
table{width:100%;border-collapse:collapse}th,td{padding:9px 11px;font-size:13px;border-bottom:1px solid rgba(17,24,39,0.096);text-align:left}
th{font-size:11px;color:#6b7280;text-transform:uppercase}
.pkgrow{display:grid;grid-template-columns:1.6fr .8fr .8fr .8fr .8fr auto;gap:8px;margin-bottom:8px;align-items:center}
.boxrow{display:grid;grid-template-columns:1.4fr .9fr .7fr .7fr .7fr .6fr auto;gap:8px;margin-bottom:8px;align-items:center}
.boxrow .bhead,.boxhdr>span{font-size:10px;color:#6b7280;font-weight:700;text-transform:uppercase;letter-spacing:.4px}
.boxhdr{display:grid;grid-template-columns:1.4fr .9fr .7fr .7fr .7fr .6fr auto;gap:8px;margin-bottom:4px}
.toast{position:fixed;bottom:24px;right:24px;background:#10b981;color:#fff;padding:14px 22px;border-radius:10px;font-weight:600;z-index:100;display:none}.toast.err{background:#f43f5e}
.muted{color:#6b7280;font-size:13px}.warn{background:rgba(251,191,36,.1);border:1px solid rgba(251,191,36,.3);color:#b45309;padding:10px 14px;border-radius:10px;font-size:13px;margin-bottom:14px}
</style></head><body>
__NAVBAR__
<div class="page-hdr"><div class="page-title">📥 Inbound Shipments <span>__NAME__</span></div></div>
<div class="wrap">
<div id="notice"></div>

<div class="card">
  <h2>🏷️ Buy a label (supplier → us)</h2>
  <div class="desc">Ships from the supplier to your warehouse (your ship-from address). Set ship-from in Permissions.</div>
  <div class="grid2" style="margin-bottom:10px">
    <div><label>Saved suppliers</label><select id="supSel"><option value="">— new supplier —</option></select></div>
    <div style="display:flex;gap:8px;align-items:flex-end"><button class="btn btn-s" id="saveSup" type="button" style="flex:1">💾 Save supplier</button><button class="btn-x" id="delSup" type="button">Delete</button></div>
  </div>
  <label>Supplier name</label><input id="supName" placeholder="Acme Supplies">
  <div class="grid2">
    <div><label>Supplier street</label><input id="sStreet1" placeholder="Street"></div>
    <div><label>Street 2</label><input id="sStreet2" placeholder="Suite / unit"></div>
    <div><label>City</label><input id="sCity"></div>
    <div><label>State</label><input id="sState" placeholder="FL"></div>
    <div><label>ZIP</label><input id="sZip"></div>
    <div><label>Phone</label><input id="sPhone"></div>
  </div>
  <div class="grid2" style="margin-top:10px;margin-bottom:8px"><div><label>Weight unit</label>
    <select id="wUnit"><option value="oz">Ounces (oz)</option><option value="lb">Pounds (lb)</option></select></div></div>
  <div id="carrierStrip" style="margin:6px 0 12px;padding:10px 12px;border:1px solid rgba(148,163,184,.35);border-radius:10px;background:rgba(148,163,184,.06)">
    <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
      <b style="font-size:13px">🚚 Carriers used for rating</b>
      <button class="btn btn-s" id="refreshCarriers" style="padding:3px 10px;font-size:12px;margin-left:auto">↻ Refresh</button>
    </div>
    <div class="desc" style="font-size:12px;margin:4px 0 6px">Tick only the carriers you want to buy labels with. Leave all ticked to compare everything. Your own UPS accounts give your negotiated rates.</div>
    <div id="carrierList" style="display:flex;flex-direction:column;gap:3px"><span class="muted" style="font-size:13px">Checking…</span></div>
    <div style="display:flex;align-items:center;gap:10px;margin-top:8px">
      <button class="btn btn-p" id="saveCarriers" style="padding:5px 14px;font-size:12px;display:none">💾 Save selection</button>
      <span id="carrierSaved" class="muted" style="font-size:12px"></span>
    </div>
    <div id="carrierHint" class="muted" style="font-size:12px;margin-top:6px;display:none"></div>
  </div>
  <label>Boxes in this shipment</label>
  <div class="desc" style="margin-bottom:8px">Supplier sending several packages? Add a row per box (or set <b>×copies</b> for identical boxes). One label is bought per box and the total is summed. Edit saved box presets in ⚙️ Settings.</div>
  <div class="boxhdr"><span>Preset</span><span id="bhWeight">Weight (oz)</span><span>L (in)</span><span>W (in)</span><span>H (in)</span><span>×Copies</span><span></span></div>
  <div id="boxList"></div>
  <button class="btn btn-s" id="addBox" style="margin-top:8px">+ Add box</button>
  <button class="btn btn-p" id="getRates" style="margin-top:14px;margin-left:8px">Get rates →</button>
  <div id="ratesBox" style="margin-top:12px"></div>
</div>

<div class="card">
  <h2>🧾 Recent inbound shipments</h2>
  <div class="desc">Each row is one shipment (one buy-click). Tap a row to see its labels. Tick rows and use “Print selected”, or “Print all” to reprint a whole batch.</div>
  <div style="margin-bottom:10px;display:flex;align-items:center;gap:12px">
    <button class="btn btn-p" id="printSel">🖨️ Print selected</button>
    <span class="muted" id="selCount">0 selected</span>
  </div>
  <table><thead><tr><th style="width:34px"><input type="checkbox" id="selAll" style="width:auto"></th><th>Supplier</th><th>Labels</th><th>Total</th><th>When</th><th>Print</th></tr></thead>
  <tbody id="inRows"><tr><td colspan="6" class="muted">None yet</td></tr></tbody></table>
</div>
</div>
<div class="toast" id="t"></div>
<script>
function toast(m,e){var t=document.getElementById('t');t.textContent=m;t.className=e?'toast err':'toast';t.style.display='block';setTimeout(function(){t.style.display='none'},3000)}
function esc(s){var d=document.createElement('div');d.textContent=(s==null?'':String(s));return d.innerHTML}
// Weights are always stored in OUNCES (what EasyPost needs); the unit toggle only
// changes how they're shown/entered.
var UNIT=localStorage.getItem('wunit')||'oz';
function fromOz(oz){if(oz===''||oz==null||!oz)return (oz===0||oz==='0')?0:'';return UNIT==='lb'?Math.round((oz/16)*1000)/1000:oz;}
function toOz(v){var n=parseFloat(v||0);return UNIT==='lb'?n*16:n;}
function wLabel(){return UNIT==='lb'?'lb':'oz';}
var PKGS=[];  // box presets — read-only here; edited in ⚙️ Settings
function applyUnit(){document.getElementById('bhWeight').textContent='Weight ('+wLabel()+')';document.getElementById('wUnit').value=UNIT;renderBoxes();}
document.getElementById('wUnit').addEventListener('change',function(){UNIT=this.value;localStorage.setItem('wunit',UNIT);applyUnit();});

// ── Multi-box shipment ──
var BOXES=[];
function renderBoxes(){
  var presetOpts=function(sel){return '<option value="">— custom —</option>'+PKGS.map(function(p,j){return '<option value="'+j+'"'+(String(sel)===String(j)?' selected':'')+'>'+esc(p.name)+'</option>'}).join('')};
  document.getElementById('boxList').innerHTML=BOXES.map(function(b,i){
    return '<div class="boxrow"><select data-i="'+i+'" data-k="preset">'+presetOpts(b.preset)+'</select>'+
      '<input type="number" step="0.01" value="'+(fromOz(b.weight))+'" data-i="'+i+'" data-k="weight" placeholder="'+wLabel()+'">'+
      '<input type="number" step="0.1" value="'+(b.length||'')+'" data-i="'+i+'" data-k="length" placeholder="L">'+
      '<input type="number" step="0.1" value="'+(b.width||'')+'" data-i="'+i+'" data-k="width" placeholder="W">'+
      '<input type="number" step="0.1" value="'+(b.height||'')+'" data-i="'+i+'" data-k="height" placeholder="H">'+
      '<input type="number" value="'+(b.copies||1)+'" data-i="'+i+'" data-k="copies" placeholder="×">'+
      '<button class="btn-x" onclick="delBox('+i+')">✕</button></div>';
  }).join('');
  document.getElementById('boxList').querySelectorAll('input,select').forEach(function(el){
    el.addEventListener('change',function(){
      var k=el.dataset.k,i=+el.dataset.i;
      if(k==='preset'){BOXES[i].preset=el.value;if(el.value!==''){var p=PKGS[+el.value];BOXES[i].weight=p.weight;BOXES[i].length=p.length;BOXES[i].width=p.width;BOXES[i].height=p.height;renderBoxes();}}
      else{BOXES[i][k]=(k==='weight')?toOz(el.value):parseFloat(el.value||'0');}
    });
  });
}
function delBox(i){BOXES.splice(i,1);if(!BOXES.length)BOXES.push({preset:'',weight:0,length:0,width:0,height:0,copies:1});renderBoxes()}
document.getElementById('addBox').addEventListener('click',function(){BOXES.push({preset:'',weight:0,length:0,width:0,height:0,copies:1});renderBoxes()});

fetch('/api/packages').then(function(r){return r.json()}).then(function(d){PKGS=d.packages||[];
  BOXES=[{preset:'',weight:0,length:0,width:0,height:0,copies:1}];applyUnit();});
var WAREHOUSE={};
fetch('/api/ship-from').then(function(r){return r.json()}).then(function(d){WAREHOUSE=d.address||{};
  if(!WAREHOUSE.street1){document.getElementById('notice').innerHTML='<div class="warn">⚠️ Set your warehouse ship-from address in Team → Permissions first — it is the destination for inbound labels.</div>'}});

// ── Supplier address book ──
var SUPPLIERS=[];
function supFields(){return {name:document.getElementById('supName').value.trim(),street1:document.getElementById('sStreet1').value.trim(),
  street2:document.getElementById('sStreet2').value.trim(),city:document.getElementById('sCity').value.trim(),
  state:document.getElementById('sState').value.trim().toUpperCase(),zip:document.getElementById('sZip').value.trim(),
  phone:document.getElementById('sPhone').value.trim()};}
function fillSup(s){document.getElementById('supName').value=s.name||'';document.getElementById('sStreet1').value=s.street1||'';
  document.getElementById('sStreet2').value=s.street2||'';document.getElementById('sCity').value=s.city||'';
  document.getElementById('sState').value=s.state||'';document.getElementById('sZip').value=s.zip||'';document.getElementById('sPhone').value=s.phone||'';}
function renderSuppliers(){var sel=document.getElementById('supSel');var cur=sel.value;
  sel.innerHTML='<option value="">— new supplier —</option>'+SUPPLIERS.map(function(s,i){return '<option value="'+i+'">'+esc(s.name||('Supplier '+(i+1)))+'</option>'}).join('');
  sel.value=cur;}
function saveSuppliers(){return fetch('/api/suppliers',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({suppliers:SUPPLIERS})}).then(function(r){return r.json()});}
document.getElementById('supSel').addEventListener('change',function(){if(this.value!==''){fillSup(SUPPLIERS[+this.value])}});
document.getElementById('saveSup').addEventListener('click',function(){
  var f=supFields();if(!f.name&&!f.street1){toast('Enter supplier name/address first',true);return}
  var i=SUPPLIERS.findIndex(function(s){return (s.name||'').toLowerCase()===f.name.toLowerCase()});
  if(i>=0)SUPPLIERS[i]=f; else SUPPLIERS.push(f);
  saveSuppliers().then(function(d){if(d.ok){renderSuppliers();toast('Supplier saved ✓')}else toast('Failed',true)});
});
document.getElementById('delSup').addEventListener('click',function(){
  var v=document.getElementById('supSel').value;if(v===''){toast('Pick a saved supplier to delete',true);return}
  SUPPLIERS.splice(+v,1);saveSuppliers().then(function(){renderSuppliers();document.getElementById('supSel').value='';toast('Removed')});
});
fetch('/api/suppliers').then(function(r){return r.json()}).then(function(d){SUPPLIERS=d.suppliers||[];renderSuppliers()});

// ── Connected carriers strip (so you can confirm UPS is there before rating) ──
var CARRIERS=[];
function carrierLabel(c){var code=(c.carrier_code||'').toLowerCase();
  if(code.indexOf('ups')>=0)return 'UPS';if(code.indexOf('fedex')>=0)return 'FedEx';
  if(code.indexOf('usps')>=0||code.indexOf('stamps')>=0)return 'USPS';
  if(code.indexOf('dhl')>=0)return 'DHL';return c.name||c.carrier_code||'Carrier';}
function loadCarriers(refresh){
  var list=document.getElementById('carrierList');var hint=document.getElementById('carrierHint');
  list.innerHTML='<span class="muted" style="font-size:13px">Checking…</span>';
  fetch('/api/ship/carriers'+(refresh?'?refresh=1':'')).then(function(r){return r.json()}).then(function(d){
    if(!d.ok){list.innerHTML='<span style="color:#e11d48">'+esc(d.error||'ShipStation not reachable')+'</span>';return}
    CARRIERS=d.carriers||[];
    if(!CARRIERS.length){list.innerHTML='<span style="color:#e11d48">None connected</span>';return}
    var restricted=d.restricted;
    list.innerHTML=CARRIERS.map(function(c){
      var lbl=carrierLabel(c);var up=lbl==='UPS';
      var checked = restricted ? c.selected : true;
      return '<label style="display:flex;align-items:center;gap:8px;font-size:13px;cursor:pointer">'+
        '<input type="checkbox" class="carrierCk" data-id="'+esc(c.carrier_id)+'"'+(checked?' checked':'')+'>'+
        '<span style="font-weight:700;'+(up?'color:#b45309':'')+'">'+esc(lbl)+'</span>'+
        '<span class="muted" style="font-family:monospace;font-size:11px">'+esc(c.carrier_id)+'</span>'+
        (c.services?'<span class="muted" style="font-size:11px">· '+c.services+' svc</span>':'')+'</label>';
    }).join('');
    document.getElementById('saveCarriers').style.display='inline-block';
    document.getElementById('carrierSaved').textContent = restricted ? ('✓ Restricted to '+(d.preferred||[]).length+' carrier(s)') : 'Using all connected carriers';
    var hasUPS=CARRIERS.some(function(c){return (c.carrier_code||'').toLowerCase().indexOf('ups')>=0});
    if(!hasUPS){hint.style.display='block';hint.innerHTML='⚠️ UPS is not connected in ShipStation. Add it in ShipStation → Settings → Carriers, then hit ↻ Refresh.';}
    else{hint.style.display='none';}
  });
}
document.getElementById('refreshCarriers').addEventListener('click',function(){loadCarriers(true)});
document.getElementById('saveCarriers').addEventListener('click',function(){
  var cks=document.querySelectorAll('.carrierCk');var ids=[],all=true;
  cks.forEach(function(ck){if(ck.checked)ids.push(ck.getAttribute('data-id'));else all=false;});
  if(!all&&!ids.length){toast('Pick at least one carrier',true);return}
  var payload=all?[]:ids;  // all ticked => use everything
  fetch('/api/ship/carriers/prefer',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ids:payload})})
   .then(function(r){return r.json()}).then(function(d){
     if(d.ok){toast(d.restricted?('Saved — rating uses '+d.preferred.length+' carrier(s)'):'Saved — using all carriers');loadCarriers(false);}
     else toast('Save failed',true);
   });
});
loadCarriers(false);

document.getElementById('getRates').addEventListener('click',function(){
  if(!BOXES.length){toast('Add at least one box',true);return}
  var boxes=[];
  for(var i=0;i<BOXES.length;i++){var b=BOXES[i];var w=parseFloat(b.weight||0);
    if(w<=0){toast('Box '+(i+1)+': enter weight (oz)',true);return}
    var n=parseInt(b.copies||1);if(!n||n<1)n=1;
    for(var k=0;k<n;k++){boxes.push({weight_oz:w,length:b.length,width:b.width,height:b.height});}}
  var supplier={name:document.getElementById('supName').value.trim(),street1:document.getElementById('sStreet1').value.trim(),
    street2:document.getElementById('sStreet2').value.trim(),city:document.getElementById('sCity').value.trim(),
    state:document.getElementById('sState').value.trim().toUpperCase(),zip:document.getElementById('sZip').value.trim(),
    phone:document.getElementById('sPhone').value.trim(),country:'US'};
  if(!(supplier.street1&&supplier.city&&supplier.state&&supplier.zip)){toast('Fill supplier street/city/state/ZIP',true);return}
  var box=document.getElementById('ratesBox');box.innerHTML='<div class="muted">Getting rates for '+boxes.length+' box(es)…</div>';
  fetch('/api/label/rates-multi',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
    to_address:WAREHOUSE,from_address:supplier,boxes:boxes})})
   .then(function(r){return r.json()}).then(function(d){
     if(!d.ok){box.innerHTML='<div style="color:#e11d48">'+esc(d.error||'Failed')+'</div>';return}
     window._sup=supplier.name;window._legsById={};
     var html='<div class="muted" style="margin-bottom:8px">'+d.boxes+' box(es) — total price buys one label per box:</div>';
     if(d.best_mix){
       window._legsById['best']=d.best_mix.legs;
       var mix=(d.best_mix.detail||[]).map(function(x,k){return 'box '+(k+1)+': '+esc(x.carrier)+' '+esc(x.service)+' $'+x.rate}).join(' · ');
       html+='<div class="card" style="display:flex;justify-content:space-between;align-items:center;margin:0 0 10px;padding:12px 14px;border:1px solid rgba(52,211,153,.5);background:rgba(16,185,129,.1)"><div><b style="color:#059669">💸 Cheapest per box (mixed carriers)</b> · <span class="muted">'+d.boxes+' labels</span><div class="muted" style="margin-top:3px;font-size:12px">'+mix+'</div></div>'+
         '<button class="btn btn-p" style="padding:6px 14px" onclick="buyMulti(\\'best\\',this)">$'+d.best_mix.total+'</button></div>';
     }
     if(!d.rates.length&&!d.best_mix){box.innerHTML='<div style="color:#e11d48">No service is available for all '+d.boxes+' boxes. Try different dimensions.</div>';return}
     // Keep a stable legs map by original index; render list with a carrier filter.
     window._rates=d.rates||[];window._rboxes=d.boxes;
     (window._rates).forEach(function(rt,idx){window._legsById[idx]=rt.legs;});
     if(window._rates.length){
       // Build carrier filter chips (UPS first), so you can jump straight to UPS.
       var order={'UPS':0,'FedEx':1,'USPS':2,'DHL':3};
       var cset=[];window._rates.forEach(function(rt){var c=rt.carrier||'?';if(cset.indexOf(c)<0)cset.push(c)});
       cset.sort(function(a,b){var oa=(order[a]==null?9:order[a]),ob=(order[b]==null?9:order[b]);return oa-ob||a.localeCompare(b)});
       html+='<div style="margin:12px 0 8px"><span class="muted" style="font-size:12px">Show carrier: </span>'+
         '<button class="crf btn btn-s" data-c="" style="padding:3px 10px;font-size:12px;margin:2px">All</button>'+
         cset.map(function(c){return '<button class="crf btn btn-s" data-c="'+esc(c)+'" style="padding:3px 10px;font-size:12px;margin:2px">'+esc(c)+'</button>'}).join('')+'</div>';
       html+='<div id="rateList"></div>';
     }
     box.innerHTML=html;
     if(window._rates.length){
       document.querySelectorAll('.crf').forEach(function(btn){btn.addEventListener('click',function(){renderRateList(this.dataset.c)})});
       // Default filter: if UPS exists, show UPS first; else show all.
       var hasUPS=window._rates.some(function(rt){return /ups/i.test(rt.carrier||'')});
       renderRateList(hasUPS?'':'');
     }
   });
});
function renderRateList(filter){
  var el=document.getElementById('rateList');if(!el)return;
  var order={'UPS':0,'FedEx':1,'USPS':2,'DHL':3};
  function ck(c){c=c||'';if(/ups/i.test(c))return 'UPS';if(/fedex/i.test(c))return 'FedEx';if(/usps|stamps/i.test(c))return 'USPS';if(/dhl/i.test(c))return 'DHL';return c;}
  // Attach original index, filter, then sort UPS-first then cheapest.
  var rows=window._rates.map(function(rt,idx){return {rt:rt,idx:idx}});
  if(filter)rows=rows.filter(function(x){return (x.rt.carrier||'')===filter});
  rows.sort(function(a,b){var oa=(order[ck(a.rt.carrier)]==null?9:order[ck(a.rt.carrier)]),ob=(order[ck(b.rt.carrier)]==null?9:order[ck(b.rt.carrier)]);
    return oa-ob||(parseFloat(a.rt.total||0)-parseFloat(b.rt.total||0));});
  if(!rows.length){el.innerHTML='<div class="muted">No options for this carrier.</div>';return}
  el.innerHTML='<div class="muted" style="margin:2px 0 6px;font-size:12px">Choose one carrier for all boxes:</div>'+rows.map(function(x){
    var rt=x.rt;var up=/ups/i.test(rt.carrier||'');
    return '<div class="card" style="display:flex;justify-content:space-between;align-items:center;margin:0 0 8px;padding:12px 14px'+(up?';border:1px solid rgba(234,88,12,.5)':'')+'"><div><b>'+esc(rt.carrier)+'</b> '+esc(rt.service)+(rt.days?(' · '+rt.days+'d'):'')+' · <span class="muted">'+window._rboxes+' labels</span></div>'+
      '<button class="btn btn-p" style="padding:6px 14px" onclick="buyMulti('+x.idx+',this)">$'+rt.total+'</button></div>';
  }).join('');
}
function buyMulti(idx,btn){
  var legs=window._legsById[idx];if(!legs){toast('Pick rates again',true);return}
  if(btn){btn.disabled=true;btn.textContent='Buying '+legs.length+'…'}
  fetch('/api/label/buy-multi',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({legs:legs,supplier:window._sup})})
   .then(function(r){return r.json()}).then(function(d){
     var bought=(d.labels||[]).length;
     if(!bought){toast(d.error||'Failed',true);if(btn){btn.disabled=false;btn.textContent='Retry'}return}
     toast(bought+' label(s) bought! Total $'+(d.total||0));
     if(d.batch_id)window.open('/label/inbound/batch/'+d.batch_id,'_blank');  // bulk print page
     if(!d.ok&&d.error)toast('Some failed: '+d.error,true);
     loadInbound();
   });
}
function toggleBatch(k){var el=document.getElementById('kids-'+k);if(el)el.style.display=(el.style.display==='none'?'table-row':'none')}
function updateSel(){var n=0;document.querySelectorAll('.selbox').forEach(function(b){if(b.checked)n++});document.getElementById('selCount').textContent=n+' selected'}
function loadInbound(){
  fetch('/api/inbound').then(function(r){return r.json()}).then(function(d){
    var groups=(d&&d.groups)||[];
    if(!groups.length){document.getElementById('inRows').innerHTML='<tr><td colspan="6" class="muted">None yet</td></tr>';document.getElementById('selCount').textContent='0 selected';return}
    document.getElementById('inRows').innerHTML=groups.map(function(g,gi){
      var k=esc(g.key||('g'+gi));
      var ids=g.shipments.map(function(s){return s.id}).join(',');
      var printAll=g.batch_id?'<a href="/label/inbound/batch/'+esc(g.batch_id)+'" target="_blank" style="color:#4f46e5;text-decoration:underline">🖨️ Print all</a>':
                   (g.shipments[0]&&g.shipments[0].label_url?'<a href="/label/inbound/'+g.shipments[0].id+'" target="_blank" style="color:#4f46e5;text-decoration:underline">🖨️ Print</a>':'—');
      var head='<tr><td><input type="checkbox" class="selbox" data-ids="'+ids+'" style="width:auto" onclick="updateSel()"></td>'+
        '<td style="cursor:pointer" onclick="toggleBatch(\\''+k+'\\')"><b>'+esc(g.supplier||'—')+'</b> <span class="muted">▾</span></td>'+
        '<td>'+g.count+' label'+(g.count>1?'s':'')+' <span class="muted">'+esc(g.carrier||'')+'</span></td>'+
        '<td>$'+(g.total||0).toFixed(2)+'</td>'+
        '<td class="muted">'+esc((g.when||'').slice(0,16).replace('T',' '))+'</td>'+
        '<td>'+printAll+'</td></tr>';
      var kids='<tr id="kids-'+k+'" style="display:none"><td colspan="6" style="padding:0"><table style="margin:0">'+
        g.shipments.map(function(s){return '<tr><td style="padding-left:24px;font-family:monospace">'+esc(s.tracking||'—')+'</td>'+
          '<td>'+esc((s.carrier||'')+' '+(s.service||''))+'</td><td>$'+(s.cost||0)+'</td><td class="muted">'+esc((s.created_at||'').slice(11,16))+'</td>'+
          '<td>'+(s.label_url?'<a href="/label/inbound/'+s.id+'" target="_blank" style="color:#4f46e5;text-decoration:underline">🖨️ Print</a>':'—')+'</td></tr>';}).join('')+
        '</table></td></tr>';
      return head+kids;
    }).join('');
    updateSel();
  });
}
document.getElementById('selAll').addEventListener('change',function(){var on=this.checked;document.querySelectorAll('.selbox').forEach(function(b){b.checked=on});updateSel()});
document.getElementById('printSel').addEventListener('click',function(){
  var ids=[];document.querySelectorAll('.selbox').forEach(function(b){if(b.checked&&b.dataset.ids)ids=ids.concat(b.dataset.ids.split(','))});
  ids=ids.filter(function(x){return x});
  if(!ids.length){toast('Tick at least one shipment',true);return}
  window.open('/label/inbound/multi?ids='+ids.join(','),'_blank');
});
loadInbound();
</script></body></html>'''


_TICKET_CAT_OPTIONS = ('<option value="import">Importing orders (TikTok / Whatnot CSV)</option>'
'<option value="packing">Packing / video recording</option>'
'<option value="picking">Picking / barcode scanning</option>'
'<option value="shipping">Shipping labels &amp; tracking</option>'
'<option value="giveaways">Giveaways</option>'
'<option value="inventory">Inventory / SKUs / catalog</option>'
'<option value="analytics">Analytics / reports</option>'
'<option value="access">Login / users / badges / permissions</option>'
'<option value="billing">Billing / account</option>'
'<option value="other" selected>Something else</option>')

SUPPORT_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Support</title>
__NAVBAR_CSS__
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#ffffff;color:#1a2130;min-height:100vh}
.page-hdr{padding:24px 28px 8px;max-width:920px;margin:0 auto}
.page-title{font-size:22px;font-weight:800}.page-title span{color:#4f46e5;margin-left:8px;font-weight:600;font-size:14px}
.wrap{max-width:920px;margin:0 auto;padding:8px 28px 40px}
.card{background:#fff;border:1px solid rgba(17,24,39,0.096);border-radius:16px;padding:22px 24px;margin-bottom:20px}
.card h2{font-size:15px;font-weight:800;color:#4f46e5;text-transform:uppercase;letter-spacing:.6px;margin-bottom:6px}
.card .desc{font-size:13px;color:#586274;margin-bottom:16px}
label{font-size:12px;font-weight:700;color:#6b7280;display:block;margin:12px 0 4px}
input[type=text],select,textarea{background:#fff;border:2px solid rgba(17,24,39,0.128);border-radius:10px;padding:11px 14px;font-size:15px;color:#1a2130;font-family:inherit;outline:none;width:100%}
textarea{min-height:90px;resize:vertical}
input:focus,select:focus,textarea:focus{border-color:#4f46e5}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.btn{border:none;border-radius:10px;padding:11px 20px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit}
.btn-p{background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff}
.btn-s{background:#f6f7f9;color:#1a2130;border:1px solid rgba(17,24,39,0.12)}
.tick{display:flex;align-items:center;gap:12px;padding:14px 12px;border-bottom:1px solid rgba(17,24,39,0.08);cursor:pointer}
.tick:hover{background:#f9fafb}
.tick .s{flex:1}.tick .subj{font-weight:700;font-size:14px}.tick .meta{font-size:12px;color:#6b7280;margin-top:2px}
.pill{font-size:11px;font-weight:700;padding:3px 10px;border-radius:50px;white-space:nowrap}
.st-open{background:rgba(79,70,229,.14);color:#4338ca}.st-pending{background:rgba(251,191,36,.18);color:#b45309}
.st-resolved{background:rgba(52,211,153,.16);color:#059669}.st-closed{background:rgba(148,163,184,.18);color:#475569}
.pr-urgent{background:rgba(244,63,94,.14);color:#e11d48}.pr-high{background:rgba(251,146,60,.16);color:#c2410c}
.msg{padding:12px 14px;border-radius:12px;margin-bottom:10px;font-size:14px;line-height:1.5;white-space:pre-wrap}
.msg.customer{background:#f3f4f6}.msg.support{background:#eef2ff;border:1px solid #c7d2fe}
.msg .who{font-size:11px;font-weight:700;color:#6b7280;margin-bottom:4px;text-transform:uppercase;letter-spacing:.4px}
.muted{color:#9ca3af;font-size:13px}
.toast{position:fixed;bottom:24px;right:24px;background:#10b981;color:#fff;padding:14px 22px;border-radius:10px;font-weight:600;z-index:100;display:none}
.toast.err{background:#f43f5e}
.hide{display:none}
.backlink{color:#4f46e5;font-weight:700;font-size:13px;cursor:pointer;display:inline-block;margin-bottom:12px}
</style></head><body>
__NAVBAR__
<div class="page-hdr"><div class="page-title">🛟 Support <span>__NAME__</span></div></div>
<div class="wrap">

<div id="listView">
  <div class="card">
    <h2>Open a request</h2>
    <div class="desc">Tell us what went wrong. The more detail you give, the faster we can help.</div>
    <div class="grid2">
      <div><label>What area?</label><select id="category">''' + _TICKET_CAT_OPTIONS + '''</select></div>
      <div><label>Priority</label><select id="priority"><option value="low">Low</option><option value="normal" selected>Normal</option><option value="high">High</option><option value="urgent">Urgent — I'm blocked</option></select></div>
    </div>
    <label>Subject</label><input type="text" id="subject" placeholder="Short summary, e.g. 'CSV import stuck on spinner'">
    <label>What happened? *</label><textarea id="body" placeholder="Describe the problem and any error message you saw."></textarea>
    <label>What were you trying to do? (steps)</label><textarea id="steps" placeholder="1) I clicked Import  2) chose the file  3) it froze…"></textarea>
    <div class="grid2">
      <div><label>When did it start / how often?</label><input type="text" id="when" placeholder="e.g. since this morning, every time"></div>
      <div><label>Which page/URL? (optional)</label><input type="text" id="url" placeholder="e.g. /operations shipments"></div>
    </div>
    <label>📷 Screenshot (optional — this helps us a lot)</label>
    <input type="file" id="shot" accept="image/*,.pdf">
    <div style="margin-top:16px"><button class="btn btn-p" id="submitBtn">Send request</button></div>
  </div>

  <div class="card">
    <h2>Your requests</h2>
    <div id="ticketList"><div class="muted">Loading…</div></div>
  </div>
</div>

<div id="detailView" class="hide">
  <span class="backlink" onclick="showList()">← Back to your requests</span>
  <div class="card" id="detailCard"></div>
</div>

</div>
<div class="toast" id="t"></div>
<script>
function toast(m,e){var t=document.getElementById('t');t.textContent=m;t.className=e?'toast err':'toast';t.style.display='block';setTimeout(function(){t.style.display='none'},3200)}
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function val(id){return (document.getElementById(id).value||'').trim()}
var CATS={};
function stpill(s){return '<span class="pill st-'+esc(s)+'">'+esc(s)+'</span>'}
function attHtml(atts){
  if(!atts||!atts.length)return '';
  return '<div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap">'+atts.map(function(a){
    var u='/api/support/attachment/'+a.id;
    if((a.mime||'').indexOf('image')===0)
      return '<a href="'+u+'" target="_blank"><img src="'+u+'" alt="'+esc(a.filename)+'" style="max-width:200px;max-height:150px;border-radius:8px;border:1px solid rgba(17,24,39,.12);display:block"></a>';
    return '<a href="'+u+'" target="_blank" style="font-size:12.5px;color:#4f46e5">📎 '+esc(a.filename)+'</a>';
  }).join('')+'</div>';
}
function uploadAtt(mid,inputId,done){
  var el=document.getElementById(inputId);
  var f=el&&el.files&&el.files[0];
  if(!f||!mid){if(done)done();return}
  var fd=new FormData();fd.append('file',f);
  fetch('/api/support/messages/'+mid+'/attachment',{method:'POST',body:fd})
    .then(function(r){return r.json()}).then(function(d){
      if(!d.ok)toast(d.error||'Attachment failed',1);
      if(el)el.value='';if(done)done();
    }).catch(function(){toast('Attachment failed',1);if(done)done()});
}
function loadList(){
  fetch('/api/support/tickets').then(function(r){return r.json()}).then(function(d){
    if(!d.ok)return; CATS=d.categories||{};
    var el=document.getElementById('ticketList');
    if(!d.tickets.length){el.innerHTML='<div class="muted">No requests yet. Open one above if something isn\\'t working.</div>';return}
    el.innerHTML=d.tickets.map(function(t){
      var pr=(t.priority==='urgent'||t.priority==='high')?'<span class="pill pr-'+esc(t.priority)+'">'+esc(t.priority)+'</span> ':'';
      return '<div class="tick" onclick="openTicket('+t.id+')"><div class="s"><div class="subj">'+esc(t.subject)+'</div>'+
        '<div class="meta">'+esc(CATS[t.category]||t.category)+' · updated '+esc((t.updated_at||'').replace('T',' '))+'</div></div>'+
        pr+stpill(t.status)+'</div>';
    }).join('');
  });
}
function openTicket(id){
  fetch('/api/support/tickets/'+id).then(function(r){return r.json()}).then(function(d){
    if(!d.ok){toast('Not found',1);return}
    var t=d.ticket;
    var msgs=d.messages.map(function(m){return '<div class="msg '+(m.author_side==='support'?'support':'customer')+'"><div class="who">'+(m.author_side==='support'?'Support':esc(m.author_name||'You'))+' · '+esc((m.created_at||'').replace('T',' '))+'</div>'+esc(m.body)+attHtml(m.attachments)+'</div>'}).join('');
    var canClose=t.status!=='closed';
    document.getElementById('detailCard').innerHTML=
      '<h2>'+esc(t.subject)+'</h2><div class="desc">'+esc(CATS[t.category]||t.category)+' · '+stpill(t.status)+'</div>'+
      msgs+
      (t.status==='closed'?'<div class="muted">This request is closed. Reply to reopen it.</div>':'')+
      '<label>Reply</label><textarea id="replyBox" placeholder="Add more detail or answer a question…"></textarea>'+
      '<label>📷 Attach a screenshot (optional)</label><input type="file" id="replyShot" accept="image/*,.pdf">'+
      '<div style="margin-top:12px;display:flex;gap:10px"><button class="btn btn-p" onclick="sendReply('+t.id+')">Send reply</button>'+
      (canClose?'<button class="btn btn-s" onclick="setStatus('+t.id+',\\'closed\\')">Mark resolved / close</button>':'<button class="btn btn-s" onclick="setStatus('+t.id+',\\'open\\')">Reopen</button>')+'</div>';
    document.getElementById('listView').classList.add('hide');
    document.getElementById('detailView').classList.remove('hide');
    window.scrollTo(0,0);
  });
}
function showList(){document.getElementById('detailView').classList.add('hide');document.getElementById('listView').classList.remove('hide');loadList()}
function sendReply(id){
  var b=val('replyBox'); if(!b){toast('Write a message',1);return}
  fetch('/api/support/tickets/'+id+'/reply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({body:b})})
    .then(function(r){return r.json()}).then(function(d){
      if(!d.ok){toast(d.error||'Failed',1);return}
      uploadAtt(d.message_id,'replyShot',function(){openTicket(id)});
    });
}
function setStatus(id,s){
  fetch('/api/support/tickets/'+id+'/status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:s})})
    .then(function(r){return r.json()}).then(function(d){if(d.ok){toast('Updated');openTicket(id)}else{toast(d.error||'Failed',1)}});
}
document.getElementById('submitBtn').addEventListener('click',function(){
  if(!val('subject')||!val('body')){toast('Add a subject and describe the issue',1);return}
  var b={category:val('category'),priority:val('priority'),subject:val('subject'),body:val('body'),
    steps:val('steps'),when:val('when'),url:val('url')};
  this.disabled=true;var btn=this;
  fetch('/api/support/tickets',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)})
    .then(function(r){return r.json()}).then(function(d){
      if(!d.ok){btn.disabled=false;toast(d.error||'Failed',1);return}
      uploadAtt(d.message_id,'shot',function(){
        btn.disabled=false;toast('Request sent');
        ['subject','body','steps','when','url'].forEach(function(i){document.getElementById(i).value=''});
        loadList();
      });
    }).catch(function(){btn.disabled=false;toast('Network error',1)});
});
loadList();
</script></body></html>'''


_MD_JS = '''
function mdEsc(s){return String(s==null?'':s).replace(/[&<>]/g,function(c){return c=='&'?'&amp;':c=='<'?'&lt;':'&gt;'})}
function mdInline(s){return s.replace(/\\[([^\\]]+)\\]\\((https?:\\/\\/[^) ]+)\\)/g,'<a href="$2" target="_blank" rel="noopener">$1</a>').replace(/\\*\\*([^*]+)\\*\\*/g,'<b>$1</b>').replace(/`([^`]+)`/g,'<code>$1</code>')}
function mdImg(l){var m=l.match(/^!\\[([^\\]]*)\\]\\(([^)]+)\\)/);if(!m)return '';var u=m[2].replace(/["']/g,'');if(!/^(https?:\\/\\/|\\/)/.test(u))return '';var cap=m[1]?'<figcaption style="font-size:12px;color:#6b7280;margin-top:6px;text-align:center">'+m[1]+'</figcaption>':'';return '<figure style="margin:16px 0"><img src="'+u+'" alt="'+m[1]+'" style="max-width:100%;border-radius:12px;border:1px solid rgba(17,24,39,.1);display:block">'+cap+'</figure>'}
function md(src){var L=mdEsc(src).split('\\n'),o=[],ul=false;function c(){if(ul){o.push('</ul>');ul=false}}
for(var i=0;i<L.length;i++){var l=L[i];
if(/^!\\[[^\\]]*\\]\\(([^)]+)\\)\\s*$/.test(l)){c();o.push(mdImg(l));continue}
if(/^### /.test(l)){c();o.push('<h3>'+mdInline(l.slice(4))+'</h3>');continue}
if(/^## /.test(l)){c();o.push('<h2>'+mdInline(l.slice(3))+'</h2>');continue}
if(/^# /.test(l)){c();o.push('<h1>'+mdInline(l.slice(2))+'</h1>');continue}
if(/^\\s*[-*] /.test(l)){if(!ul){o.push('<ul>');ul=true}o.push('<li>'+mdInline(l.replace(/^\\s*[-*] /,''))+'</li>');continue}
if(/^\\s*$/.test(l)){c();continue}
c();o.push('<p>'+mdInline(l)+'</p>')}
c();return o.join('')}
'''

GUIDES_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Guides</title>
__NAVBAR_CSS__
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#fff;color:#1a2130;min-height:100vh}
.page-hdr{padding:24px 28px 8px;max-width:920px;margin:0 auto}
.page-title{font-size:22px;font-weight:800}.page-title span{color:#4f46e5;margin-left:8px;font-weight:600;font-size:14px}
.wrap{max-width:920px;margin:0 auto;padding:8px 28px 40px}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:18px}
.chip{border:1px solid rgba(17,24,39,0.12);background:#f6f7f9;border-radius:50px;padding:7px 16px;font-size:13px;font-weight:700;cursor:pointer;font-family:inherit}
.chip.on{background:#4f46e5;color:#fff;border-color:#4f46e5}
.gcard{background:#fff;border:1px solid rgba(17,24,39,0.1);border-radius:14px;padding:16px 18px;margin-bottom:12px;cursor:pointer;display:flex;align-items:center;gap:12px}
.gcard:hover{border-color:#c7d2fe;background:#fafaff}
.gcard .t{flex:1}.gcard .ti{font-weight:700;font-size:15px}.gcard .ca{font-size:12px;color:#6b7280;margin-top:2px}
.arw{color:#9ca3af;font-size:18px}
.muted{color:#9ca3af;font-size:14px}.hide{display:none}
.backlink{color:#4f46e5;font-weight:700;font-size:13px;cursor:pointer;display:inline-block;margin-bottom:12px}
.article{background:#fff;border:1px solid rgba(17,24,39,0.096);border-radius:16px;padding:26px 28px}
.article h1{font-size:26px;font-weight:800;margin:2px 0 14px}
.article h2{font-size:19px;font-weight:800;margin:22px 0 8px}
.article h3{font-size:16px;font-weight:800;margin:18px 0 6px;color:#374151}
.article p{font-size:15px;line-height:1.65;margin-bottom:12px}
.article ul{margin:0 0 14px 22px}.article li{font-size:15px;line-height:1.6;margin-bottom:6px}
.article code{background:#f3f4f6;border-radius:5px;padding:1px 6px;font-size:13.5px}
.article a{color:#4f46e5}
.vid{display:inline-block;background:#4f46e5;color:#fff;border-radius:10px;padding:10px 18px;font-weight:700;text-decoration:none;margin-bottom:16px}
</style></head><body>
__NAVBAR__
<div class="page-hdr"><div class="page-title">📚 Guides <span>__NAME__</span></div></div>
<div class="wrap">
<div id="listView">
  <div class="chips" id="chips"></div>
  <div id="guideList"><div class="muted">Loading…</div></div>
</div>
<div id="detailView" class="hide">
  <span class="backlink" onclick="showList()">← Back to guides</span>
  <div class="article" id="article"></div>
</div>
</div>
<script>''' + _MD_JS + '''
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
var GUIDES=[],CATS={},ORDER=[],FILTER='';
function renderChips(){
  var cats=ORDER.filter(function(k){return GUIDES.some(function(g){return g.category===k})});
  var html='<button class="chip'+(FILTER===''?' on':'')+'" data-c="">All</button>';
  html+=cats.map(function(k){return '<button class="chip'+(FILTER===k?' on':'')+'" data-c="'+esc(k)+'">'+esc(CATS[k]||k)+'</button>'}).join('');
  document.getElementById('chips').innerHTML=html;
  document.querySelectorAll('#chips .chip').forEach(function(b){b.addEventListener('click',function(){FILTER=b.getAttribute('data-c');renderChips();renderList()})});
}
function renderList(){
  var el=document.getElementById('guideList');
  var gs=GUIDES.filter(function(g){return !FILTER||g.category===FILTER});
  if(!gs.length){el.innerHTML='<div class="muted">No guides here yet.</div>';return}
  el.innerHTML=gs.map(function(g){return '<div class="gcard" onclick="openGuide('+g.id+')"><div class="t"><div class="ti">'+esc(g.title)+'</div><div class="ca">'+esc(CATS[g.category]||g.category)+(g.video_url?' · 🎬 video':'')+'</div></div><span class="arw">›</span></div>'}).join('');
}
function openGuide(id){
  fetch('/api/guides/'+id).then(function(r){return r.json()}).then(function(d){
    if(!d.ok){return}
    var g=d.guide;
    var vid=g.video_url?'<a class="vid" href="'+esc(g.video_url)+'" target="_blank" rel="noopener">🎬 Watch the video</a><br>':'';
    document.getElementById('article').innerHTML='<h1>'+esc(g.title)+'</h1>'+vid+md(g.body||'');
    document.getElementById('listView').classList.add('hide');
    document.getElementById('detailView').classList.remove('hide');window.scrollTo(0,0);
  });
}
function showList(){document.getElementById('detailView').classList.add('hide');document.getElementById('listView').classList.remove('hide')}
fetch('/api/guides').then(function(r){return r.json()}).then(function(d){
  if(!d.ok)return;GUIDES=d.guides;CATS=d.categories||{};ORDER=d.cat_order||[];renderChips();renderList();
});
</script></body></html>'''


_GUIDE_CAT_OPTIONS = ('<option value="getting_started">Getting started</option>'
'<option value="import">Importing orders</option><option value="packing">Packing &amp; recording</option>'
'<option value="picking">Picking &amp; scanning</option><option value="shipping">Shipping &amp; tracking</option>'
'<option value="giveaways">Giveaways</option><option value="inventory">Inventory &amp; SKUs</option>'
'<option value="analytics">Analytics &amp; reports</option><option value="account">Account, users &amp; badges</option>'
'<option value="troubleshooting">Troubleshooting</option>')

GUIDES_ADMIN_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Guides · Platform</title>
__NAVBAR_CSS__
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#fff;color:#1a2130;min-height:100vh}
.page-hdr{padding:24px 28px 8px;max-width:1100px;margin:0 auto}
.page-title{font-size:22px;font-weight:800}.page-title span{color:#4f46e5;margin-left:8px;font-weight:600;font-size:14px}
.wrap{max-width:1100px;margin:0 auto;padding:8px 28px 40px;display:grid;grid-template-columns:340px 1fr;gap:20px;align-items:start}
.card{background:#fff;border:1px solid rgba(17,24,39,0.096);border-radius:16px;padding:18px 20px}
.card h2{font-size:14px;font-weight:800;color:#4f46e5;text-transform:uppercase;letter-spacing:.6px;margin-bottom:12px}
.grow{display:flex;flex-direction:column;gap:6px}
.gitem{border:1px solid rgba(17,24,39,0.1);border-radius:10px;padding:10px 12px;cursor:pointer}
.gitem:hover{background:#fafaff;border-color:#c7d2fe}.gitem.sel{border-color:#4f46e5;background:#eef2ff}
.gitem .ti{font-weight:700;font-size:14px}.gitem .mt{font-size:11px;color:#6b7280;margin-top:3px;display:flex;gap:6px;align-items:center}
.pill{font-size:10px;font-weight:700;padding:2px 8px;border-radius:50px}
.pub{background:rgba(52,211,153,.16);color:#059669}.draft{background:rgba(148,163,184,.2);color:#475569}
label{font-size:12px;font-weight:700;color:#6b7280;display:block;margin:12px 0 4px}
input[type=text],select,textarea{background:#fff;border:2px solid rgba(17,24,39,0.128);border-radius:10px;padding:10px 13px;font-size:14px;color:#1a2130;font-family:inherit;outline:none;width:100%}
textarea{min-height:220px;resize:vertical;font-family:ui-monospace,Menlo,monospace;font-size:13px;line-height:1.5}
input:focus,select:focus,textarea:focus{border-color:#4f46e5}
.row3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}
.btn{border:none;border-radius:10px;padding:10px 18px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit}
.btn-p{background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff}
.btn-s{background:#f6f7f9;color:#1a2130;border:1px solid rgba(17,24,39,0.12)}
.btn-d{background:rgba(244,63,94,.12);color:#e11d48}
.preview{border:1px dashed rgba(17,24,39,0.18);border-radius:12px;padding:16px;margin-top:10px;max-height:340px;overflow:auto}
.preview h1{font-size:22px;margin:0 0 10px}.preview h2{font-size:17px;margin:16px 0 6px}.preview h3{font-size:15px;margin:12px 0 5px;color:#374151}
.preview p{font-size:14px;line-height:1.6;margin-bottom:10px}.preview ul{margin:0 0 10px 20px}.preview li{font-size:14px;margin-bottom:5px}
.preview code{background:#f3f4f6;border-radius:5px;padding:1px 6px}.preview a{color:#4f46e5}
.muted{color:#9ca3af;font-size:13px}
.toast{position:fixed;bottom:24px;right:24px;background:#10b981;color:#fff;padding:14px 22px;border-radius:10px;font-weight:600;z-index:100;display:none}
.toast.err{background:#f43f5e}
.hint{font-size:11px;color:#9ca3af;margin-top:4px}
</style></head><body>
__NAVBAR__
<div class="page-hdr"><div class="page-title">📚 Guides <span>__NAME__</span></div></div>
<div class="wrap">
  <div class="card">
    <h2>Guides</h2>
    <button class="btn btn-p" style="width:100%;margin-bottom:12px" onclick="newGuide()">+ New guide</button>
    <div class="grow" id="glist"><div class="muted">Loading…</div></div>
  </div>
  <div class="card">
    <h2 id="formTitle">New guide</h2>
    <input type="hidden" id="gid">
    <label>Title</label><input type="text" id="title" placeholder="e.g. How to import a TikTok order CSV">
    <div class="row3">
      <div><label>Category</label><select id="category">''' + _GUIDE_CAT_OPTIONS + '''</select></div>
      <div><label>Audience</label><select id="audience"><option value="all">Everyone</option><option value="managers">Managers only (admin/CS)</option></select></div>
      <div><label>Status</label><select id="status"><option value="draft">Draft</option><option value="published">Published</option></select></div>
    </div>
    <div class="row3">
      <div style="grid-column:span 2"><label>Video URL (optional)</label><input type="text" id="video_url" placeholder="https://youtu.be/… or Loom link"></div>
      <div><label>Sort order</label><input type="text" id="sort_order" placeholder="0"></div>
    </div>
    <label>Body (Markdown)</label>
    <textarea id="body" placeholder="# Heading&#10;Some text with **bold**, `code`, and [a link](https://example.com).&#10;&#10;## Steps&#10;- First&#10;- Second"></textarea>
    <div class="hint">Supports # / ## / ### headings, **bold**, *italic*, `code`, - bullet lists, and [text](https://url).</div>
    <div style="margin:12px 0;display:flex;gap:8px;flex-wrap:wrap">
      <button class="btn btn-p" onclick="saveGuide()">Save</button>
      <button class="btn btn-s" onclick="newGuide()">Clear</button>
      <button class="btn btn-d" id="delBtn" style="display:none" onclick="delGuide()">Delete</button>
    </div>
    <label>Live preview</label><div class="preview" id="preview"></div>
  </div>
</div>
<div class="toast" id="t"></div>
<script>''' + _MD_JS + '''
function toast(m,e){var t=document.getElementById('t');t.textContent=m;t.className=e?'toast err':'toast';t.style.display='block';setTimeout(function(){t.style.display='none'},3000)}
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function val(id){return (document.getElementById(id).value||'').trim()}
var CATS={};
function loadList(){
  fetch('/api/admin/guides').then(function(r){return r.json()}).then(function(d){
    if(!d.ok)return;CATS=d.categories||{};
    var el=document.getElementById('glist');
    if(!d.guides.length){el.innerHTML='<div class="muted">No guides yet. Create your first one.</div>';return}
    el.innerHTML=d.guides.map(function(g){
      var pill=g.status==='published'?'<span class="pill pub">published</span>':'<span class="pill draft">draft</span>';
      return '<div class="gitem" data-id="'+g.id+'" onclick="editGuide('+g.id+')"><div class="ti">'+esc(g.title)+'</div>'+
        '<div class="mt">'+esc(CATS[g.category]||g.category)+' · '+esc(g.audience)+' '+pill+'</div></div>';
    }).join('');
  });
}
function fill(g){
  document.getElementById('gid').value=g.id||'';
  document.getElementById('title').value=g.title||'';
  document.getElementById('category').value=g.category||'getting_started';
  document.getElementById('audience').value=g.audience||'all';
  document.getElementById('status').value=g.status||'draft';
  document.getElementById('video_url').value=g.video_url||'';
  document.getElementById('sort_order').value=g.sort_order||0;
  document.getElementById('body').value=g.body||'';
  document.getElementById('formTitle').textContent=g.id?'Edit guide':'New guide';
  document.getElementById('delBtn').style.display=g.id?'inline-block':'none';
  renderPreview();
}
function newGuide(){fill({});window.scrollTo(0,0)}
function editGuide(id){fetch('/api/guides/'+id).then(function(r){return r.json()}).then(function(d){if(d.ok){fill(d.guide);window.scrollTo(0,0)}})}
function renderPreview(){document.getElementById('preview').innerHTML=md(val('body')||'*Nothing yet.*')}
document.getElementById('body').addEventListener('input',renderPreview);
function payload(){return {title:val('title'),category:val('category'),audience:val('audience'),status:val('status'),
  video_url:val('video_url'),sort_order:val('sort_order'),body:document.getElementById('body').value}}
function saveGuide(){
  if(!val('title')){toast('Title is required',1);return}
  var id=val('gid');var url=id?('/api/admin/guides/'+id):'/api/admin/guides';
  fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload())})
    .then(function(r){return r.json()}).then(function(d){if(d.ok){toast('Saved');if(d.id)document.getElementById('gid').value=d.id;document.getElementById('formTitle').textContent='Edit guide';document.getElementById('delBtn').style.display='inline-block';loadList()}else{toast(d.error||'Failed',1)}});
}
function delGuide(){var id=val('gid');if(!id)return;if(!confirm('Delete this guide?'))return;
  fetch('/api/admin/guides/'+id+'/delete',{method:'POST'}).then(function(r){return r.json()}).then(function(d){if(d.ok){toast('Deleted');newGuide();loadList()}});
}
loadList();newGuide();
</script></body></html>'''


PLATFORM_SUPPORT_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Support · Platform</title>
__NAVBAR_CSS__
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#fff;color:#1a2130;min-height:100vh}
.page-hdr{padding:24px 28px 8px;max-width:1100px;margin:0 auto}
.page-title{font-size:22px;font-weight:800}.page-title span{color:#4f46e5;margin-left:8px;font-weight:600;font-size:14px}
.wrap{max-width:1100px;margin:0 auto;padding:8px 28px 40px}
.card{background:#fff;border:1px solid rgba(17,24,39,0.096);border-radius:16px;padding:20px 22px;margin-bottom:18px}
.card h2{font-size:15px;font-weight:800;color:#4f46e5;text-transform:uppercase;letter-spacing:.6px;margin-bottom:12px}
.filters{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px}
.fbtn{border:1px solid rgba(17,24,39,0.12);background:#f6f7f9;border-radius:50px;padding:7px 16px;font-size:13px;font-weight:700;cursor:pointer;font-family:inherit}
.fbtn.on{background:#4f46e5;color:#fff;border-color:#4f46e5}
table{width:100%;border-collapse:collapse}
th,td{padding:11px 10px;font-size:13px;border-bottom:1px solid rgba(17,24,39,0.08);text-align:left}
th{font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px}
tr.row{cursor:pointer}tr.row:hover td{background:#f9fafb}
.pill{font-size:11px;font-weight:700;padding:3px 10px;border-radius:50px;white-space:nowrap}
.st-open{background:rgba(79,70,229,.14);color:#4338ca}.st-pending{background:rgba(251,191,36,.18);color:#b45309}
.st-resolved{background:rgba(52,211,153,.16);color:#059669}.st-closed{background:rgba(148,163,184,.18);color:#475569}
.pr-urgent{background:rgba(244,63,94,.14);color:#e11d48}.pr-high{background:rgba(251,146,60,.16);color:#c2410c}.pr-normal{color:#6b7280}.pr-low{color:#9ca3af}
.msg{padding:12px 14px;border-radius:12px;margin-bottom:10px;font-size:14px;line-height:1.5;white-space:pre-wrap}
.msg.customer{background:#f3f4f6}.msg.support{background:#eef2ff;border:1px solid #c7d2fe}
.msg .who{font-size:11px;font-weight:700;color:#6b7280;margin-bottom:4px;text-transform:uppercase;letter-spacing:.4px}
.ctx{background:#fafafa;border:1px solid rgba(17,24,39,0.08);border-radius:12px;padding:14px;font-size:13px;margin-bottom:14px}
.ctx b{color:#374151}.ctx div{margin-bottom:5px}
label{font-size:12px;font-weight:700;color:#6b7280;display:block;margin:12px 0 4px}
textarea{background:#fff;border:2px solid rgba(17,24,39,0.128);border-radius:10px;padding:11px 14px;font-size:15px;color:#1a2130;font-family:inherit;outline:none;width:100%;min-height:90px;resize:vertical}
textarea:focus{border-color:#4f46e5}
.btn{border:none;border-radius:10px;padding:10px 18px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit}
.btn-p{background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff}
.btn-s{background:#f6f7f9;color:#1a2130;border:1px solid rgba(17,24,39,0.12)}
.muted{color:#9ca3af;font-size:13px}.hide{display:none}
.backlink{color:#4f46e5;font-weight:700;font-size:13px;cursor:pointer;display:inline-block;margin-bottom:12px}
.toast{position:fixed;bottom:24px;right:24px;background:#10b981;color:#fff;padding:14px 22px;border-radius:10px;font-weight:600;z-index:100;display:none}
.toast.err{background:#f43f5e}
</style></head><body>
__NAVBAR__
<div class="page-hdr"><div class="page-title">🛟 Support <span id="cnt"></span></div></div>
<div class="wrap">

<div id="listView">
  <div class="card">
    <div class="filters" id="filters">
      <button class="fbtn on" data-f="">All</button>
      <button class="fbtn" data-f="open">Open</button>
      <button class="fbtn" data-f="pending">Pending</button>
      <button class="fbtn" data-f="resolved">Resolved</button>
      <button class="fbtn" data-f="closed">Closed</button>
    </div>
    <table><thead><tr><th>Company</th><th>Subject</th><th>Area</th><th>Priority</th><th>Status</th><th>Updated</th></tr></thead>
    <tbody id="rows"><tr><td colspan="6" class="muted">Loading…</td></tr></tbody></table>
  </div>
</div>

<div id="detailView" class="hide">
  <span class="backlink" onclick="showList()">← Back to all tickets</span>
  <div class="card" id="detailCard"></div>
</div>

</div>
<div class="toast" id="t"></div>
<script>
function toast(m,e){var t=document.getElementById('t');t.textContent=m;t.className=e?'toast err':'toast';t.style.display='block';setTimeout(function(){t.style.display='none'},3200)}
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
var CATS={};var FILTER='';
function stpill(s){return '<span class="pill st-'+esc(s)+'">'+esc(s)+'</span>'}
function attHtml(atts){
  if(!atts||!atts.length)return '';
  return '<div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap">'+atts.map(function(a){
    var u='/api/support/attachment/'+a.id;
    if((a.mime||'').indexOf('image')===0)
      return '<a href="'+u+'" target="_blank"><img src="'+u+'" alt="'+esc(a.filename)+'" style="max-width:240px;max-height:180px;border-radius:8px;border:1px solid rgba(17,24,39,.12);display:block"></a>';
    return '<a href="'+u+'" target="_blank" style="font-size:12.5px;color:#4f46e5">📎 '+esc(a.filename)+'</a>';
  }).join('')+'</div>';
}
function uploadAtt(mid,inputId,done){
  var el=document.getElementById(inputId);
  var f=el&&el.files&&el.files[0];
  if(!f||!mid){if(done)done();return}
  var fd=new FormData();fd.append('file',f);
  fetch('/api/support/messages/'+mid+'/attachment',{method:'POST',body:fd})
    .then(function(r){return r.json()}).then(function(d){
      if(!d.ok)toast(d.error||'Attachment failed',1);
      if(el)el.value='';if(done)done();
    }).catch(function(){toast('Attachment failed',1);if(done)done()});
}
function loadCount(){fetch('/api/support/open-count').then(function(r){return r.json()}).then(function(d){document.getElementById('cnt').textContent=d.count?('· '+d.count+' open'):''})}
function loadList(){
  fetch('/api/support/tickets'+(FILTER?('?status='+FILTER):'')).then(function(r){return r.json()}).then(function(d){
    if(!d.ok)return; CATS=d.categories||{};
    var el=document.getElementById('rows');
    if(!d.tickets.length){el.innerHTML='<tr><td colspan=6 class=muted>No tickets</td></tr>';return}
    el.innerHTML=d.tickets.map(function(t){
      return '<tr class="row" onclick="openTicket('+t.id+')"><td><b>'+esc(t.company)+'</b></td><td>'+esc(t.subject)+'</td>'+
        '<td>'+esc(CATS[t.category]||t.category)+'</td><td><span class="pill pr-'+esc(t.priority)+'">'+esc(t.priority)+'</span></td>'+
        '<td>'+stpill(t.status)+'</td><td>'+esc((t.updated_at||'').replace('T',' '))+'</td></tr>';
    }).join('');
  });
}
function openTicket(id){
  fetch('/api/support/tickets/'+id).then(function(r){return r.json()}).then(function(d){
    if(!d.ok){toast('Not found',1);return}
    var t=d.ticket,cx=t.context||{};
    var ctx='<div class="ctx"><div><b>Company:</b> '+esc(t.company)+' ('+esc(t.org_id)+')</div>'+
      '<div><b>Reported by:</b> '+esc(t.created_by_name||t.created_by)+' ('+esc(cx.role||'')+')</div>'+
      (cx.steps?'<div><b>Steps:</b> '+esc(cx.steps)+'</div>':'')+
      (cx.when?'<div><b>When/frequency:</b> '+esc(cx.when)+'</div>':'')+
      (cx.url?'<div><b>Page:</b> '+esc(cx.url)+'</div>':'')+
      (cx.user_agent?'<div><b>Browser:</b> '+esc(cx.user_agent)+'</div>':'')+'</div>';
    var msgs=d.messages.map(function(m){return '<div class="msg '+(m.author_side==='support'?'support':'customer')+'"><div class="who">'+(m.author_side==='support'?'Support (you)':esc(m.author_name||'Customer'))+' · '+esc((m.created_at||'').replace('T',' '))+'</div>'+esc(m.body)+attHtml(m.attachments)+'</div>'}).join('');
    document.getElementById('detailCard').innerHTML=
      '<h2>'+esc(t.subject)+' '+stpill(t.status)+'</h2>'+ctx+msgs+
      '<label>Reply to customer</label><textarea id="replyBox" placeholder="Type your answer…"></textarea>'+
      '<label>📷 Attach a screenshot (optional)</label><input type="file" id="replyShot" accept="image/*,.pdf" style="font-size:13px">'+
      '<div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap">'+
      '<button class="btn btn-p" onclick="sendReply('+t.id+')">Send reply</button>'+
      '<button class="btn btn-s" onclick="setStatus('+t.id+',\\'pending\\')">Pending</button>'+
      '<button class="btn btn-s" onclick="setStatus('+t.id+',\\'resolved\\')">Resolved</button>'+
      '<button class="btn btn-s" onclick="setStatus('+t.id+',\\'closed\\')">Close</button>'+
      '<button class="btn btn-s" onclick="setStatus('+t.id+',\\'open\\')">Reopen</button></div>';
    document.getElementById('listView').classList.add('hide');
    document.getElementById('detailView').classList.remove('hide');window.scrollTo(0,0);
  });
}
function showList(){document.getElementById('detailView').classList.add('hide');document.getElementById('listView').classList.remove('hide');loadList();loadCount()}
function sendReply(id){var b=(document.getElementById('replyBox').value||'').trim();if(!b){toast('Write a message',1);return}
  fetch('/api/support/tickets/'+id+'/reply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({body:b})})
    .then(function(r){return r.json()}).then(function(d){
      if(!d.ok){toast(d.error||'Failed',1);return}
      uploadAtt(d.message_id,'replyShot',function(){openTicket(id);loadCount()});
    })}
function setStatus(id,s){fetch('/api/support/tickets/'+id+'/status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:s})})
    .then(function(r){return r.json()}).then(function(d){if(d.ok){toast('Set to '+s);openTicket(id);loadCount()}else{toast(d.error||'Failed',1)}})}
document.querySelectorAll('#filters .fbtn').forEach(function(b){b.addEventListener('click',function(){
  document.querySelectorAll('#filters .fbtn').forEach(function(x){x.classList.remove('on')});b.classList.add('on');FILTER=b.getAttribute('data-f');loadList()})});
loadList();loadCount();
</script></body></html>'''


ORGANIZATIONS_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Organizations</title>
__NAVBAR_CSS__
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#ffffff;color:#1a2130;min-height:100vh}
.page-hdr{padding:24px 28px 8px;max-width:1040px;margin:0 auto}
.page-title{font-size:22px;font-weight:800}.page-title span{color:#4f46e5;margin-left:8px;font-weight:600;font-size:14px}
.wrap{max-width:1040px;margin:0 auto;padding:8px 28px 40px}
.card{background:#ffffff;border:1px solid rgba(17,24,39,0.096);border-radius:16px;padding:22px 24px;margin-bottom:20px}
.card h2{font-size:15px;font-weight:800;color:#4f46e5;text-transform:uppercase;letter-spacing:.6px;margin-bottom:6px}
.card .desc{font-size:13px;color:#586274;margin-bottom:16px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;max-width:720px}
label{font-size:12px;font-weight:700;color:#6b7280;display:block;margin-bottom:4px}
input[type=text],input[type=password],select{background:#ffffff;border:2px solid rgba(17,24,39,0.128);border-radius:10px;padding:11px 14px;font-size:15px;color:#1a2130;font-family:inherit;outline:none;width:100%}
input:focus,select:focus{border-color:#4f46e5}
.btn{border:none;border-radius:10px;padding:11px 20px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit}
.btn-p{background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff}
.btn-s{background:#f6f7f9;color:#1a2130;border:1px solid rgba(17,24,39,0.12)}
.btn-warn{background:rgba(251,191,36,.16);color:#b45309}
.btn-ok{background:rgba(52,211,153,.16);color:#059669}
table{width:100%;border-collapse:collapse;margin-top:8px}
th,td{padding:12px 10px;font-size:13px;border-bottom:1px solid rgba(17,24,39,0.096);text-align:left}
th{font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px}
.pill{font-size:11px;font-weight:700;padding:3px 10px;border-radius:50px}
.pill.on{background:rgba(52,211,153,.16);color:#059669}.pill.off{background:rgba(244,63,94,.14);color:#e11d48}
.ucard{border:1px solid rgba(17,24,39,.09);border-radius:12px;padding:15px 17px;margin-bottom:12px;background:#fff}
.ucard.internal{border-color:rgba(99,102,241,.35);background:#fbfbff}
.hint{font-size:11px;color:#9ca3af;margin-top:4px;line-height:1.4}
.colorpick{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-top:6px}
.colorpick input[type=color]{width:52px;height:40px;padding:2px;border:1px solid rgba(17,24,39,.15);border-radius:9px;background:#fff;cursor:pointer}
.swatches{display:flex;gap:7px;flex-wrap:wrap}
.sw{width:28px;height:28px;border-radius:50%;cursor:pointer;border:2px solid transparent;transition:transform .1s}
.sw:hover{transform:scale(1.12)}
.sw.on{border-color:#141b26;box-shadow:0 0 0 2px #fff inset}
.cpreview{margin-left:auto;padding:9px 16px;border-radius:10px;color:#fff;font-weight:900;letter-spacing:.5px;font-size:14px}
.uhead{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:11px}
.uhead code{background:rgba(17,24,39,.06);padding:1px 7px;border-radius:5px;font-size:11.5px}
.ubar-row{display:flex;align-items:center;gap:11px;margin:6px 0}
.ubar-lbl{width:128px;font-size:11.5px;font-weight:800;color:#6b7280;text-transform:uppercase;letter-spacing:.4px}
.ubar-track{flex:1;height:9px;background:rgba(17,24,39,.08);border-radius:50px;overflow:hidden}
.ubar-fill{display:block;height:100%;border-radius:50px;transition:width .3s}
.ubar-num{width:118px;text-align:right;font-size:12px;font-weight:800}
.ubar-none{flex:1;font-size:12px;color:#9ca3af}
.ustats{display:flex;gap:16px;flex-wrap:wrap;margin-top:11px;font-size:11.5px;color:#6b7280}
.ustore{display:flex;gap:16px;flex-wrap:wrap;margin-top:8px;padding-top:9px;border-top:1px dashed rgba(17,24,39,.12);font-size:11.5px;color:#6b7280}
.storetotal{background:#f7f8fc;border:1px solid rgba(17,24,39,.07);border-radius:10px;padding:11px 14px;margin-bottom:14px;font-size:12.5px;display:flex;align-items:center;flex-wrap:wrap}
.warnchip{background:rgba(245,158,11,.16);color:#b45309;padding:1px 9px;border-radius:50px;font-weight:800}
.hotchip{background:rgba(16,185,129,.16);color:#059669;padding:1px 9px;border-radius:50px;font-weight:800}
.uacts{margin-top:12px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.uacts select{padding:6px 9px;border-radius:8px;border:1px solid rgba(17,24,39,.15);font-size:12.5px}
.reqrow{padding:10px 12px;border:1px solid rgba(245,158,11,.3);background:rgba(245,158,11,.06);border-radius:9px;margin-bottom:8px;font-size:13.5px}
.swatch{display:inline-block;width:14px;height:14px;border-radius:4px;vertical-align:middle;margin-right:6px;border:1px solid rgba(0,0,0,.1)}
.cred{background:#eef2ff;border:1px solid #c7d2fe;border-radius:12px;padding:16px;margin-top:14px;display:none}
.cred b{color:#4338ca}
.cred code{background:#fff;border:1px solid #c7d2fe;border-radius:6px;padding:2px 8px;font-size:14px;font-weight:700}
.toast{position:fixed;bottom:24px;right:24px;background:#10b981;color:#fff;padding:14px 22px;border-radius:10px;font-weight:600;z-index:100;display:none}
.toast.err{background:#f43f5e}
.note{font-size:12px;color:#6b7280;margin-top:10px}
.muted{color:#9ca3af}
</style></head><body>
__NAVBAR__
<div class="page-hdr"><div class="page-title">🏢 Organizations <span>__NAME__</span></div></div>
<div class="wrap">

<div class="card">
  <h2>All tenants</h2>
  <div class="desc">Every company using the platform. Each tenant's data is fully isolated.</div>
  <table><thead><tr><th>Company</th><th>Org ID</th><th>Brand</th><th>Plan</th><th>Users</th><th>Status</th><th></th></tr></thead>
  <tbody id="orgRows"><tr><td colspan="7" class="muted">Loading…</td></tr></tbody></table>
</div>

<div class="card">
  <h2>Usage &amp; billing</h2>
  <div class="desc">How hard each customer is leaning on their plan. <b>Near the cap</b> = upsell. <b>Quiet</b> = churn risk.</div>
  <div class="storetotal"><span id="storeTotal" class="muted">Calculating storage…</span>
    <button class="btn btn-s" id="refreshStore" style="margin-left:10px">↻ Recount</button></div>
  <div id="usageList"><div class="muted">Loading…</div></div>
</div>

<div class="card">
  <h2>Plan requests</h2>
  <div class="desc">Customers who picked a plan on their billing screen — send them an invoice, then record the payment above.</div>
  <div id="reqList"><div class="muted">Loading…</div></div>
</div>

<div class="card">
  <h2>Leads</h2>
  <div class="desc">Submissions from the public demo form at <code>/demo</code>.</div>
  <table><thead><tr><th>When</th><th>Company</th><th>Contact</th><th>Volume</th><th>Status</th></tr></thead>
  <tbody id="leadRows"><tr><td colspan="5" class="muted">Loading…</td></tr></tbody></table>
</div>

<div class="card">
  <h2>Create a new tenant</h2>
  <div class="desc">Registers the company, provisions its isolated data, and creates its first admin login.</div>
  <div class="grid">
    <div><label>Company name *</label><input type="text" id="company" placeholder="Glam Co"></div>
    <div><label>Org ID * (lowercase, no spaces)</label><input type="text" id="org_id" placeholder="glamco"></div>
    <div><label>Brand mark (short)</label><input type="text" id="brand_mark" placeholder="GLAM"></div>
    <div><label>Brand subtitle</label><input type="text" id="brand_sub" placeholder="Employee Hub"></div>
    <div><label>Contact email</label><input type="email" id="contact_email" placeholder="owner@glamco.com"></div>
    <div><label>Contact phone</label><input type="text" id="contact_phone" placeholder="+1 555 123 4567"></div>
    <div><label>Plan</label><select id="plan">
      <option value="starter">Starter — $149/mo · up to 3 users</option>
      <option value="pro">Pro — $399/mo · unlimited users, 1,000 orders/day</option>
      <option value="enterprise">Enterprise — custom</option>
    </select></div>
    <div><label>First admin username *</label><input type="text" id="admin_username" placeholder="glamco_admin" autocapitalize="off" autocorrect="off" spellcheck="false">
      <div class="hint">Lowercase letters, digits, _ and - only. Typed capitals are converted automatically.</div></div>
    <div><label>First admin name</label><input type="text" id="admin_name" placeholder="Admin"></div>
    <div><label>Admin password (blank = auto-generate)</label><input type="text" id="admin_password" placeholder="leave blank to auto-generate">
      <div class="hint">Minimum 8 characters. Blank is safest — we generate a strong one and show it once.</div></div>
  </div>
  <div style="margin-top:14px">
    <label>Brand color</label>
    <div class="colorpick">
      <input type="color" id="brand_color_pick" value="#d9748f">
      <input type="text" id="brand_color" placeholder="#d9748f" maxlength="7" style="max-width:130px">
      <div class="swatches" id="swatches"></div>
      <div class="cpreview" id="cpreview"><span id="cpmark">BRAND</span></div>
    </div>
  </div>
  <div class="row" style="margin-top:16px"><button class="btn btn-p" id="createBtn">Create organization</button></div>
  <div class="cred" id="cred"></div>
  <div class="note">Usernames are global across all tenants, so pick something unique (e.g. prefix with the company).</div>
</div>

</div>
<div class="toast" id="t"></div>
<script>
function toast(m,e){var t=document.getElementById('t');t.textContent=m;t.className=e?'toast err':'toast';t.style.display='block';setTimeout(function(){t.style.display='none'},3200)}
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}

// ── Usage & billing ─────────────────────────────────────────────
var STATE_PILL={ok:['#059669','ACTIVE'],trial_expired:['#e11d48','TRIAL ENDED'],
  period_ended:['#b45309','RENEWAL DUE'],unpaid:['#e11d48','PAYMENT DUE'],
  suspended:['#e11d48','SUSPENDED'],no_subscription:['#b45309','NO PLAN']};
function bar(used,limit,label){
  if(!limit) return '<div class="ubar-row"><span class="ubar-lbl">'+label+'</span>'+
    '<span class="ubar-none">'+used+' · unlimited</span></div>';
  var pct=Math.min(100,Math.round(100*used/limit));
  var col=pct>=100?'#e11d48':(pct>=80?'#f59e0b':'#10b981');
  return '<div class="ubar-row"><span class="ubar-lbl">'+label+'</span>'+
    '<span class="ubar-track"><span class="ubar-fill" style="width:'+pct+'%;background:'+col+'"></span></span>'+
    '<span class="ubar-num" style="color:'+col+'">'+used+'/'+limit+' · '+pct+'%</span></div>';
}
function daysAgo(d){if(!d)return 'never';var n=Math.floor((Date.now()-new Date(d).getTime())/86400000);
  return n<=0?'today':(n===1?'yesterday':n+'d ago')}
function loadUsage(){
  fetch('/api/orgs/usage').then(function(r){return r.json()}).then(function(d){
    if(!d.ok){document.getElementById('usageList').innerHTML='<div class="muted">Failed to load</div>';return}
    document.getElementById('usageList').innerHTML=d.usage.map(function(u){
      var sp=STATE_PILL[u.state]||['#6b7280',u.state];
      var quiet=(!u.orders_30d)?'<span class="warnchip">⚠︎ no orders in 30 days</span>':'';
      var hot=(!u.internal&&u.usage_pct!=null&&u.usage_pct>=80)?'<span class="hotchip">▲ near cap — upsell</span>':'';
      var until=u.internal?'not billed'
        :(u.sub_status==='trialing'
          ? ('trial ends '+String(u.trial_ends_at||'').slice(0,10))
          : (u.current_period_end?('paid through '+String(u.current_period_end).slice(0,10)):'no end date'));
      var badge=u.internal
        ? '<span class="pill" style="background:rgba(99,102,241,.15);color:#4f46e5">🏠 INTERNAL</span>'
        : '<span class="pill" style="background:'+sp[0]+'22;color:'+sp[0]+'">'+sp[1]+'</span>';
      return '<div class="ucard'+(u.internal?' internal':'')+'">'+
        '<div class="uhead"><div><b>'+esc(u.company_name||u.org_id)+'</b> <code>'+esc(u.org_id)+'</code></div>'+
        '<div>'+badge+' '+
        '<span class="muted">'+(u.internal?'':esc(u.plan_label||'')+' · ')+esc(until)+'</span></div></div>'+
        bar(u.users,u.users_limit,'Users')+
        bar(u.peak_day_30d,u.orders_limit,'Peak orders/day')+
        '<div class="ustats"><span>'+u.orders_today+' today</span><span>'+u.orders_7d+' last 7d</span>'+
        '<span>'+u.orders_30d+' last 30d</span><span>last activity: '+daysAgo(u.last_activity)+'</span>'+quiet+hot+'</div>'+
        '<div class="ustore" id="st-'+esc(u.org_id)+'"><span class="muted">storage…</span></div>'+
        '<div class="uacts">'+
          (u.internal
            ? '<span class="muted">Own / demo account — no plan caps, never billed or locked.</span> '+
              '<button class="btn btn-s" data-intern="'+esc(u.org_id)+'" data-val="0">Make billable</button>'
            : '<button class="btn btn-s" data-pay="'+esc(u.org_id)+'" data-plan="'+esc(u.plan||'starter')+'">💵 Record payment</button> '+
              '<button class="btn btn-s" data-trial="'+esc(u.org_id)+'">＋7 trial days</button> '+
              '<select data-setplan="'+esc(u.org_id)+'">'+
                ['starter','pro','enterprise'].map(function(p){return '<option value="'+p+'"'+(u.plan===p?' selected':'')+'>'+p+'</option>'}).join('')+
              '</select> '+
              '<button class="btn btn-s" data-intern="'+esc(u.org_id)+'" data-val="1">🏠 Mark internal</button>')+
        '</div></div>';
    }).join('')||'<div class="muted">No tenants yet</div>';
    loadStorage(false);
    document.querySelectorAll('#usageList button[data-pay]').forEach(function(b){
      b.addEventListener('click',function(){
        var org=b.getAttribute('data-pay');
        var months=prompt('Record payment for '+org+'\\n\\nHow many months?','1');
        if(!months)return;
        var ref=prompt('Invoice / reference number (optional):','')||'';
        fetch('/api/orgs/'+encodeURIComponent(org)+'/payment',{method:'POST',
          headers:{'Content-Type':'application/json'},
          body:JSON.stringify({months:parseInt(months)||1,plan:b.getAttribute('data-plan'),method:'manual',reference:ref})})
        .then(function(r){return r.json()}).then(function(d){
          if(d.ok){toast('Payment recorded — paid through '+String(d.period_end).slice(0,10));loadUsage();load();loadReqs()}
          else toast(d.error||'Failed',1)});
      });
    });
    document.querySelectorAll('#usageList button[data-trial]').forEach(function(b){
      b.addEventListener('click',function(){
        fetch('/api/orgs/'+encodeURIComponent(b.getAttribute('data-trial'))+'/subscription',{method:'POST',
          headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'extend_trial',days:7})})
        .then(function(r){return r.json()}).then(function(d){
          if(d.ok){toast('Trial extended 7 days');loadUsage()}else toast(d.error||'Failed',1)});
      });
    });
    document.querySelectorAll('#usageList button[data-intern]').forEach(function(b){
      b.addEventListener('click',function(){
        var on=b.getAttribute('data-val')==='1';
        if(on&&!confirm('Mark this tenant as internal?\\n\\nIt will stop being billed, lose all plan caps, and never be locked out.'))return;
        fetch('/api/orgs/'+encodeURIComponent(b.getAttribute('data-intern'))+'/subscription',{method:'POST',
          headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'set_internal',internal:on})})
        .then(function(r){return r.json()}).then(function(d){
          if(d.ok){toast(on?'Marked internal':'Now billable');loadUsage()}else toast(d.error||'Failed',1)});
      });
    });
    document.querySelectorAll('#usageList select[data-setplan]').forEach(function(s){
      s.addEventListener('change',function(){
        fetch('/api/orgs/'+encodeURIComponent(s.getAttribute('data-setplan'))+'/subscription',{method:'POST',
          headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'set_plan',plan:s.value})})
        .then(function(r){return r.json()}).then(function(d){
          if(d.ok){toast('Plan updated');loadUsage();load()}else toast(d.error||'Failed',1)});
      });
    });
  });
}
function gb(b){if(!b)return '0 MB';var m=b/1048576;return m<1024?(m.toFixed(m<10?1:0)+' MB'):((m/1024).toFixed(2)+' GB')}
function loadStorage(refresh){
  fetch('/api/orgs/storage'+(refresh?'?refresh=1':'')).then(function(r){return r.json()}).then(function(d){
    if(!d.ok)return;
    d.storage.forEach(function(s){
      var el=document.getElementById('st-'+s.org_id); if(!el)return;
      var vid=s.by_kind&&s.by_kind.videos?s.by_kind.videos:{count:0,bytes:0};
      var margin='';
      if(s.cost_pct_of_revenue!=null){
        var c=s.cost_pct_of_revenue>=10?'#e11d48':(s.cost_pct_of_revenue>=5?'#b45309':'#059669');
        margin='<span style="color:'+c+';font-weight:800">'+s.cost_pct_of_revenue+'% of their $'+s.plan_price+'</span>';
      }
      el.innerHTML='<span>🎬 <b>'+gb(vid.bytes)+'</b> video ('+vid.count+' files)</span>'+
        '<span>💾 '+gb(s.total_bytes)+' total</span>'+
        '<span>💵 <b>'+(s.cost_month<0.01&&s.total_bytes>0?'&lt;$0.01':'$'+s.cost_month.toFixed(2))+'</b>/mo R2</span>'+margin;
    });
    var tot=document.getElementById('storeTotal');
    if(tot)tot.innerHTML='Across all tenants: <b>'+d.total_gb+' GB</b> stored · '+
      'first '+d.free_gb+' GB free · billable <b>'+d.billable_gb+' GB</b> = <b>$'+d.total_cost_month.toFixed(2)+'/mo</b> '+
      '<span class="muted">at $'+d.rate+'/GB, no egress fees. Figures cached ~30 min.</span>';
  });
}
function loadReqs(){
  fetch('/api/billing/requests').then(function(r){return r.json()}).then(function(d){
    if(!d.ok)return;
    var open=d.requests.filter(function(x){return !x.handled});
    document.getElementById('reqList').innerHTML=open.length?open.map(function(x){
      return '<div class="reqrow"><span><b>'+esc(x.company_name||x.org_id)+'</b> wants <b>'+esc(x.plan)+'</b>'+
        ' <span class="muted">· requested by '+esc(x.requested_by||'')+' · '+String(x.created_at||'').slice(0,16)+'</span></span></div>';
    }).join(''):'<div class="muted">No open requests</div>';
  });
}
function loadLeads(){
  fetch('/api/leads').then(function(r){return r.json()}).then(function(d){
    if(!d.ok)return;
    document.getElementById('leadRows').innerHTML=d.leads.length?d.leads.map(function(l){
      return '<tr><td class="muted">'+String(l.created_at||'').slice(0,16)+'</td>'+
        '<td><b>'+esc(l.company)+'</b></td>'+
        '<td>'+esc(l.contact_name)+'<br><span class="muted">'+esc(l.email)+(l.phone?' · '+esc(l.phone):'')+'</span></td>'+
        '<td>'+esc(l.volume||'')+'<br><span class="muted">'+esc(l.platforms||'')+'</span></td>'+
        '<td>'+esc(l.status||'new')+'</td></tr>';
    }).join(''):'<tr><td colspan=5 class=muted>No leads yet</td></tr>';
  });
}
function load(){
  fetch('/api/orgs').then(function(r){return r.json()}).then(function(d){
    if(!d.ok){document.getElementById('orgRows').innerHTML='<tr><td colspan=7 class=muted>Failed to load</td></tr>';return}
    var rows=d.orgs.map(function(o){
      var status=o.active?'<span class="pill on">active</span>':'<span class="pill off">suspended</span>';
      var enter=o.active?'<button class="btn btn-s" data-enter="'+esc(o.org_id)+'">🛟 Enter</button> ':'';
      var toggle=o.is_default?'<span class="muted">founding</span>':(o.active
        ?'<button class="btn btn-warn" data-o="'+esc(o.org_id)+'" data-a="0">Suspend</button>'
        :'<button class="btn btn-ok" data-o="'+esc(o.org_id)+'" data-a="1">Reactivate</button>');
      var contact=(o.contact_email||o.contact_phone)
        ? '<br><span class="muted" style="font-size:11px">'+esc(o.contact_email||'')+(o.contact_phone?' · '+esc(o.contact_phone):'')+'</span>' : '';
      return '<tr><td><b>'+esc(o.company_name)+'</b>'+contact+'</td><td><code>'+esc(o.org_id)+'</code></td>'+
        '<td><span class="swatch" style="background:'+esc(o.brand_color||'#ccc')+'"></span>'+esc(o.brand_mark||'')+'</td>'+
        '<td>'+esc(o.plan||'')+'</td><td>'+o.user_count+'</td><td>'+status+'</td><td>'+enter+toggle+'</td></tr>';
    }).join('');
    document.getElementById('orgRows').innerHTML=rows||'<tr><td colspan=7 class=muted>No organizations</td></tr>';
    document.querySelectorAll('#orgRows button[data-enter]').forEach(function(b){
      b.addEventListener('click',function(){
        var org=b.getAttribute('data-enter');
        fetch('/api/impersonate',{method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({org_id:org})})
          .then(function(r){return r.json()}).then(function(d){
            if(d.ok){location.href=d.redirect||'/home'}else{toast(d.error||'Failed',1)}});
      });
    });
    document.querySelectorAll('#orgRows button[data-o]').forEach(function(b){
      b.addEventListener('click',function(){
        var active=b.getAttribute('data-a')==='1';
        if(!active && !confirm('Suspend this tenant? Their users will not be able to log in.'))return;
        fetch('/api/orgs/toggle',{method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({org_id:b.getAttribute('data-o'),active:active})})
          .then(function(r){return r.json()}).then(function(d){if(d.ok){toast('Updated');load()}else{toast(d.error||'Failed',1)}});
      });
    });
  });
}
document.getElementById('createBtn').addEventListener('click',function(){
  var btn=this;btn.disabled=true;
  var body={company_name:val('company'),org_id:val('org_id'),brand_mark:val('brand_mark'),
    brand_sub:val('brand_sub'),brand_color:val('brand_color'),plan:val('plan'),
    contact_email:val('contact_email'),contact_phone:val('contact_phone'),
    admin_username:val('admin_username').toLowerCase(),admin_name:val('admin_name'),admin_password:val('admin_password')};
  fetch('/api/orgs/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
    .then(function(r){return r.json()}).then(function(d){
      btn.disabled=false;
      if(!d.ok){toast(d.error||'Failed',1);return}
      var c=document.getElementById('cred');
      c.style.display='block';
      c.innerHTML='<b>✅ Tenant created.</b> Save these credentials now — the password is shown only once.<br><br>'+
        'Login URL: <code>'+location.origin+'/login</code><br>'+
        'Username: <code>'+esc(d.admin_username)+'</code><br>'+
        'Password: <code>'+esc(d.admin_password)+'</code>';
      ['company','org_id','brand_mark','brand_sub','brand_color','contact_email','contact_phone','admin_username','admin_name','admin_password'].forEach(function(id){document.getElementById(id).value=''});
      setColor('#d9748f');
      toast('Organization created');load();loadUsage();
    }).catch(function(){btn.disabled=false;toast('Network error',1)});
});
function val(id){return (document.getElementById(id).value||'').trim()}

// ── Brand colour picker: swatches + native picker + hex, all kept in sync ──
var SWATCHES=['#d9748f','#e11d48','#f43f5e','#f59e0b','#f97316','#10b981','#059669',
              '#0891b2','#2563eb','#4f46e5','#7c3aed','#a855f7','#141b26','#64748b'];
function setColor(hex,skip){
  hex=(hex||'').trim();
  if(!/^#[0-9a-fA-F]{6}$/.test(hex))return;
  hex=hex.toLowerCase();
  if(skip!=='text')document.getElementById('brand_color').value=hex;
  if(skip!=='pick')document.getElementById('brand_color_pick').value=hex;
  var pv=document.getElementById('cpreview');pv.style.background=hex;
  document.getElementById('cpmark').textContent=(val('brand_mark')||val('company')||'BRAND').toUpperCase().slice(0,14);
  document.querySelectorAll('.sw').forEach(function(s){s.classList.toggle('on',s.dataset.c===hex)});
}
(function initColor(){
  document.getElementById('swatches').innerHTML=SWATCHES.map(function(c){
    return '<span class="sw" data-c="'+c+'" style="background:'+c+'" title="'+c+'"></span>'}).join('');
  document.querySelectorAll('.sw').forEach(function(s){
    s.addEventListener('click',function(){setColor(s.dataset.c)})});
  document.getElementById('brand_color_pick').addEventListener('input',function(){setColor(this.value,'pick')});
  document.getElementById('brand_color').addEventListener('input',function(){setColor(this.value,'text')});
  ['brand_mark','company'].forEach(function(id){
    document.getElementById(id).addEventListener('input',function(){setColor(val('brand_color')||'#d9748f')})});
  // usernames are lowercase-only server-side — normalise as they type
  document.getElementById('admin_username').addEventListener('input',function(){
    var p=this.selectionStart;this.value=this.value.toLowerCase().replace(/[^a-z0-9_\\-]/g,'');this.setSelectionRange(p,p)});
  document.getElementById('org_id').addEventListener('input',function(){
    var p=this.selectionStart;this.value=this.value.toLowerCase().replace(/[^a-z0-9\\-]/g,'');this.setSelectionRange(p,p)});
  setColor('#d9748f');
})();
load();loadUsage();loadReqs();loadLeads();
document.getElementById('refreshStore').addEventListener('click',function(){document.getElementById('storeTotal').textContent='Recounting…';loadStorage(true)});
setInterval(loadUsage,60000);
</script></body></html>'''


# ══════════════════════════════════════════════════════════
# BILLING / PAYWALL — shown when a tenant's trial ended or
# its subscription isn't active (full lock).
# ══════════════════════════════════════════════════════════
BILLING_HTML = '''<!DOCTYPE html><html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Billing · LiveOpsHub</title>
__FONT__
<style>
*{box-sizing:border-box}
body{margin:0;background:#f6f7fb;color:#141b26;font-family:'Inter',-apple-system,'Segoe UI',sans-serif}
.wrap{max-width:1000px;margin:0 auto;padding:48px 24px 60px}
.hero{text-align:center;margin-bottom:36px}
.hero h1{font-size:30px;font-weight:900;margin:0 0 10px}
.state{display:inline-block;padding:8px 18px;border-radius:50px;font-weight:800;font-size:13px;margin-bottom:16px}
.state.warn{background:rgba(245,158,11,.16);color:#b45309}
.state.bad{background:rgba(244,63,94,.14);color:#e11d48}
.state.ok{background:rgba(16,185,129,.14);color:#059669}
.msg{color:#5b6474;font-size:15px;max-width:620px;margin:0 auto;line-height:1.6}
.plans{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin-top:34px}
@media(max-width:860px){.plans{grid-template-columns:1fr}}
.plan{background:#fff;border:2px solid rgba(17,24,39,.08);border-radius:16px;padding:26px 22px;display:flex;flex-direction:column}
.plan.featured{border-color:#6366f1;box-shadow:0 10px 40px rgba(99,102,241,.14)}
.plan .tag{font-size:11px;font-weight:900;letter-spacing:.8px;text-transform:uppercase;color:#6366f1;margin-bottom:8px;min-height:14px}
.plan h3{margin:0 0 6px;font-size:20px;font-weight:900}
.price{font-size:38px;font-weight:900;letter-spacing:-1px}
.price small{font-size:14px;font-weight:700;color:#8b93a5}
.blurb{color:#5b6474;font-size:14px;margin:10px 0 18px;line-height:1.5;flex:1}
.btn{display:block;text-align:center;border:none;border-radius:11px;padding:13px 20px;font-size:15px;font-weight:800;cursor:pointer;text-decoration:none;
     background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff}
.btn.sec{background:#fff;color:#4f46e5;border:2px solid rgba(79,70,229,.35)}
.howto{margin-top:30px;background:#fff;border:1px solid rgba(17,24,39,.08);border-radius:14px;
  padding:20px 24px;color:#5b6474;font-size:14px;line-height:1.65;text-align:center}
.howto b{color:#141b26}
.howto a{color:#4f46e5;font-weight:700}
.foot{text-align:center;margin-top:34px;color:#8b93a5;font-size:13px}
.foot a{color:#4f46e5;font-weight:700}
.logout{position:absolute;top:20px;right:24px;color:#8b93a5;font-size:13px;font-weight:700;text-decoration:none}
</style></head><body>
<a class="logout" href="/logout">Log out</a>
<div class="wrap">
  <div class="hero">
    <div class="state __STATE_CLS__">__STATE_LABEL__</div>
    <h1>__HEADLINE__</h1>
    <div class="msg">__MESSAGE__</div>
  </div>
  <div class="plans">
    <div class="plan">
      <div class="tag"></div>
      <h3>Starter</h3>
      <div class="price">$149<small>/mo</small></div>
      <div class="blurb">Up to 3 users. The full warehouse workflow — imports, picking, packing with video proof, inventory and analytics.</div>
      <button class="btn sec" onclick="choose('starter')">Choose Starter</button>
    </div>
    <div class="plan featured">
      <div class="tag">Most popular</div>
      <h3>Pro</h3>
      <div class="price">$399<small>/mo</small></div>
      <div class="blurb">Unlimited users, up to 1,000 orders per day. Everything in Starter plus the full team roster and multi-channel scheduling.</div>
      <button class="btn" onclick="choose('pro')">Choose Pro</button>
    </div>
    <div class="plan">
      <div class="tag"></div>
      <h3>Enterprise</h3>
      <div class="price">Custom</div>
      <div class="blurb">More than 1,000 orders per day, multiple warehouses, or custom integrations. Let's build the right package for you.</div>
      <a class="btn sec" href="mailto:__SALES_EMAIL__?subject=LiveOpsHub%20Enterprise">Talk to sales</a>
    </div>
  </div>
  <div class="howto" id="howto">__PAY_INSTRUCTIONS__</div>
  <div class="foot">Questions about billing? <a href="mailto:__SALES_EMAIL__">__SALES_EMAIL__</a></div>
</div>
<script>
function choose(plan){
  var b=event.target;var old=b.textContent;b.disabled=true;b.textContent='Sending…';
  fetch('/api/billing/request-plan',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({plan:plan})})
   .then(function(r){return r.json()}).then(function(d){
     if(!d.ok){b.disabled=false;b.textContent=old;alert(d.error||'Could not send the request.');return}
     document.getElementById('howto').innerHTML=
       '<b>Thanks — request received.</b><br>We\\'ll email your invoice for the <b>'+plan+'</b> plan shortly. '+
       'Your access opens as soon as the payment clears. Questions? <a href="mailto:__SALES_EMAIL__">__SALES_EMAIL__</a>';
     document.getElementById('howto').scrollIntoView({behavior:'smooth',block:'center'});
     document.querySelectorAll('.plan button').forEach(function(x){x.disabled=true});
     b.textContent='Requested ✓';
   }).catch(function(){b.disabled=false;b.textContent=old;alert('Network error')});
}
</script></body></html>'''


# ══════════════════════════════════════════════════════════
# PUBLIC LEAD CAPTURE — "request a demo" (no auth).
# Sales talks to the prospect, then a super-admin opens the trial.
# ══════════════════════════════════════════════════════════
DEMO_HTML = '''<!DOCTYPE html><html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Request a demo · LiveOpsHub</title>
__FONT__
<style>
*{box-sizing:border-box}
body{margin:0;background:#0c0f16;color:#e9edf6;font-family:'Inter',-apple-system,'Segoe UI',sans-serif}
.wrap{max-width:1040px;margin:0 auto;padding:56px 24px 70px;display:grid;grid-template-columns:1.05fr .95fr;gap:52px}
@media(max-width:900px){.wrap{grid-template-columns:1fr;gap:34px;padding-top:36px}}
.brand{font-weight:900;font-size:20px;letter-spacing:-.3px;margin-bottom:30px}
.brand span{color:#818cf8}
h1{font-size:38px;line-height:1.12;font-weight:900;margin:0 0 16px;letter-spacing:-1px}
.sub{color:#9aa4b8;font-size:16px;line-height:1.65;margin-bottom:26px}
.pts{list-style:none;padding:0;margin:0}
.pts li{padding:9px 0 9px 30px;position:relative;color:#c8cfdd;font-size:15px}
.pts li:before{content:'✓';position:absolute;left:0;color:#34d399;font-weight:900}
.card{background:#141a25;border:1px solid rgba(255,255,255,.09);border-radius:18px;padding:30px}
.card h2{margin:0 0 6px;font-size:20px;font-weight:900}
.card p{margin:0 0 20px;color:#9aa4b8;font-size:13.5px}
label{display:block;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.6px;color:#8b93a5;margin:14px 0 6px}
input,select,textarea{width:100%;padding:12px 14px;border-radius:10px;border:1px solid rgba(255,255,255,.12);
  background:#0c0f16;color:#e9edf6;font-size:14.5px;font-family:inherit}
input:focus,select:focus,textarea:focus{outline:none;border-color:#6366f1}
textarea{min-height:78px;resize:vertical}
.btn{width:100%;margin-top:22px;border:none;border-radius:11px;padding:14px;font-size:15.5px;font-weight:800;cursor:pointer;
  background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff}
.btn:disabled{opacity:.6;cursor:default}
.note{margin-top:14px;color:#6b7488;font-size:12px;text-align:center;line-height:1.5}
.done{text-align:center;padding:34px 10px}
.done .ic{font-size:46px}
.done h2{margin:14px 0 8px}
.err{background:rgba(244,63,94,.12);color:#fb7185;padding:11px 13px;border-radius:9px;font-size:13.5px;margin-top:14px;display:none}
</style></head><body>
<div class="wrap">
  <div>
    <div class="brand">LiveOps<span>Hub</span></div>
    <h1>Run your live-selling warehouse without the chaos.</h1>
    <div class="sub">Built by a live-selling operation, for live-selling operations. Import your TikTok or Whatnot orders and every step after that is handled.</div>
    <ul class="pts">
      <li>Import orders straight from TikTok Shop &amp; Whatnot</li>
      <li>iPad picking and packing with video proof of every box</li>
      <li>Inventory, purchase orders and supplier receiving</li>
      <li>Host &amp; assistant scheduling across all your channels</li>
      <li>Per-show profit, packer and picker analytics</li>
    </ul>
  </div>
  <div class="card" id="card">
    <h2>Request a demo</h2>
    <p>Tell us about your operation and we'll set up a 7-day trial on a quick call.</p>
    <div id="form">
      <label>Company *</label><input id="company" placeholder="Your business name">
      <label>Your name *</label><input id="contact" placeholder="First and last name">
      <label>Email *</label><input id="email" type="email" placeholder="you@company.com">
      <label>Phone</label><input id="phone" placeholder="Optional">
      <label>Where do you sell?</label>
      <select id="platforms">
        <option value="">— select —</option>
        <option>TikTok Shop</option><option>Whatnot</option>
        <option>Both TikTok &amp; Whatnot</option><option>Other</option>
      </select>
      <label>Roughly how many orders a day?</label>
      <select id="volume">
        <option value="">— select —</option>
        <option>Under 100</option><option>100–500</option>
        <option>500–1,000</option><option>Over 1,000</option>
      </select>
      <label>Anything else?</label><textarea id="message" placeholder="What's slowing you down today?"></textarea>
      <button class="btn" id="send">Request my demo</button>
      <div class="err" id="err"></div>
      <div class="note">We'll only use your details to contact you about LiveOpsHub.</div>
    </div>
  </div>
</div>
<script>
function v(id){return (document.getElementById(id).value||'').trim()}
document.getElementById('send').addEventListener('click',function(){
  var e=document.getElementById('err');e.style.display='none';
  if(!v('company')||!v('contact')||!v('email')){e.textContent='Company, name and email are required.';e.style.display='block';return}
  if(v('email').indexOf('@')<0){e.textContent='Please enter a valid email address.';e.style.display='block';return}
  var b=this;b.disabled=true;b.textContent='Sending…';
  fetch('/api/lead',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
    company:v('company'),contact_name:v('contact'),email:v('email'),phone:v('phone'),
    platforms:v('platforms'),volume:v('volume'),message:v('message')})})
  .then(function(r){return r.json()}).then(function(d){
    if(!d.ok){b.disabled=false;b.textContent='Request my demo';e.textContent=d.error||'Something went wrong.';e.style.display='block';return}
    document.getElementById('card').innerHTML='<div class="done"><div class="ic">🎉</div><h2>Thanks — we got it!</h2>'+
      '<p>One of us will reach out within one business day to set up your trial.</p></div>';
  }).catch(function(){b.disabled=false;b.textContent='Request my demo';e.textContent='Network error — please try again.';e.style.display='block'});
});
</script></body></html>'''


# ══════════════════════════════════════════════════════════
# COMPANY SETUP — the screen a new tenant works through on
# day one. Everything they must configure, in one place.
# ══════════════════════════════════════════════════════════
SETUP_HTML = '''<!DOCTYPE html><html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Company setup — __BRANDMARK__</title>
__NAVBAR_CSS__
<style>
*{box-sizing:border-box}
body{margin:0;background:#f6f7fb;color:#141b26;font-family:'Inter',-apple-system,'Segoe UI',sans-serif}
.wrap{max-width:960px;margin:0 auto;padding:26px 20px 70px}
.page-hdr{padding:22px 0 6px}
.page-title{font-size:26px;font-weight:900}
.page-title span{color:var(--brand,#4f46e5);font-size:14px;font-weight:700;margin-left:8px}
.card{background:#fff;border:1px solid rgba(17,24,39,.08);border-radius:14px;padding:20px 22px;margin-bottom:16px}
.card h2{margin:0 0 4px;font-size:17px;font-weight:900}
.desc{color:#6b7280;font-size:13px;margin-bottom:14px;line-height:1.55}
label{display:block;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.5px;color:#6b7280;margin:12px 0 5px}
input,select{width:100%;padding:10px 12px;border:1px solid rgba(17,24,39,.15);border-radius:9px;font-size:14px;font-family:inherit}
input:focus,select:focus{outline:none;border-color:#4f46e5}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:0 16px}
@media(max-width:700px){.grid2{grid-template-columns:1fr}}
.btn{border:none;border-radius:10px;padding:10px 18px;font-size:14px;font-weight:800;cursor:pointer;
     background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff;margin-top:16px}
.btn.s{background:#fff;color:#4f46e5;border:1.5px solid rgba(79,70,229,.35);padding:8px 14px;font-size:13px;margin-top:0}
.btn:disabled{opacity:.55;cursor:default}
/* progress */
.prog{background:linear-gradient(135deg,#eef0fb,#f6f7fb);border:1px solid rgba(79,70,229,.18)}
.ptrack{height:10px;background:rgba(17,24,39,.08);border-radius:50px;overflow:hidden;margin:12px 0 16px}
.pfill{height:100%;background:linear-gradient(90deg,#4f46e5,#7c3aed);border-radius:50px;transition:width .4s}
.chk{display:flex;align-items:flex-start;gap:11px;padding:9px 0}
.dot{width:22px;height:22px;border-radius:50%;border:2.5px solid rgba(17,24,39,.18);flex-shrink:0;margin-top:1px;
     display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:900;color:transparent}
.chk.on .dot{background:#10b981;border-color:#10b981;color:#fff}
.chk.on .dot::before{content:'✓'}
.ctxt b{font-size:14px}
.chk.on .ctxt b{color:#6b7280;text-decoration:line-through}
.ctxt div{font-size:12px;color:#8b93a5;margin-top:2px}
/* colour picker */
.colorpick{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-top:6px}
.colorpick input[type=color]{width:52px;height:40px;padding:2px;border:1px solid rgba(17,24,39,.15);border-radius:9px;background:#fff;cursor:pointer}
.colorpick input[type=text]{max-width:130px}
.swatches{display:flex;gap:7px;flex-wrap:wrap}
.sw{width:28px;height:28px;border-radius:50%;cursor:pointer;border:2px solid transparent;transition:transform .1s}
.sw:hover{transform:scale(1.12)} .sw.on{border-color:#141b26;box-shadow:0 0 0 2px #fff inset}
.cprev{margin-left:auto;padding:9px 16px;border-radius:10px;color:#fff;font-weight:900;letter-spacing:.5px}
/* brand list */
.brow{display:flex;gap:9px;align-items:center;margin-bottom:8px}
.brow input{flex:1}
.brow button{background:none;border:none;color:#e11d48;font-weight:800;cursor:pointer;font-size:13px}
.muted{color:#9ca3af;font-size:13px}
.link{color:#4f46e5;font-weight:700;text-decoration:none}
.toast{position:fixed;bottom:24px;right:24px;background:#10b981;color:#fff;padding:13px 20px;border-radius:10px;font-weight:700;z-index:100;display:none}
.toast.err{background:#f43f5e}
</style></head><body>
__NAVBAR__
<div class="wrap">
<div class="page-hdr"><div class="page-title">🚀 Company setup <span>__NAME__</span></div></div>

<div class="card prog">
  <h2>Getting started</h2>
  <div class="desc">Work through these once and your warehouse is ready to run.</div>
  <div class="ptrack"><div class="pfill" id="pfill" style="width:0%"></div></div>
  <div id="checks"><div class="muted">Loading…</div></div>
</div>

<div class="card">
  <h2>1 · Your company</h2>
  <div class="desc">This is what your team sees in the top-left of every screen, and what gets printed on staff badges.</div>
  <div class="grid2">
    <div><label>Company name</label><input id="company" maxlength="80" placeholder="Glam Co"></div>
    <div><label>Wordmark (short)</label><input id="mark" maxlength="24" placeholder="GLAM"></div>
    <div><label>Subtitle</label><input id="sub" maxlength="40" placeholder="Employee Hub"></div>
    <div><label>Logo URL (https, optional)</label><input id="logo" maxlength="500" placeholder="https://…/logo.png"></div>
  </div>
  <label>Brand colour</label>
  <div class="colorpick">
    <input type="color" id="colorPick" value="#4f46e5">
    <input type="text" id="color" maxlength="7" placeholder="#4f46e5">
    <div class="swatches" id="swatches"></div>
    <div class="cprev" id="cprev">BRAND</div>
  </div>
  <button class="btn" id="saveCompany">Save company</button>
</div>

<div class="card">
  <h2>2 · Warehouse address</h2>
  <div class="desc">Where your parcels ship from — and where supplier deliveries are sent. Used every time you buy a label.</div>
  <div class="grid2">
    <div><label>Name / company</label><input id="aName" placeholder="Glam Co Warehouse"></div>
    <div><label>Phone</label><input id="aPhone" placeholder="+1 555 123 4567"></div>
    <div><label>Street</label><input id="aStreet1" placeholder="123 Main St"></div>
    <div><label>Street 2</label><input id="aStreet2" placeholder="Suite 4"></div>
    <div><label>City</label><input id="aCity"></div>
    <div><label>State</label><input id="aState" placeholder="FL" maxlength="2"></div>
    <div><label>ZIP</label><input id="aZip" placeholder="33101"></div>
    <div><label>Country</label><input id="aCountry" value="US" maxlength="2"></div>
  </div>
  <button class="btn" id="saveAddr">Save address</button>
</div>

<div class="card">
  <h2>3 · Giveaway brands</h2>
  <div class="desc">The brand options you pick from when logging a giveaway winner. Add one per line.</div>
  <div id="brandRows"></div>
  <button class="btn s" id="addBrand">+ Add brand</button>
  <div><button class="btn" id="saveBrands">Save brands</button></div>
</div>

<div class="card">
  <h2>4 · Channels &amp; team</h2>
  <div class="desc">Your live-selling accounts and the people who run them.</div>
  <div id="chSummary" class="muted">Loading…</div>
  <div style="margin-top:14px;display:flex;gap:10px;flex-wrap:wrap">
    <a class="btn s" href="/admin/roster">📺 Manage channels</a>
    <a class="btn s" href="/users">👥 Manage team</a>
  </div>
</div>
</div>
<div class="toast" id="t"></div>
<script>
function toast(m,e){var t=document.getElementById('t');t.textContent=m;t.className=e?'toast err':'toast';t.style.display='block';setTimeout(function(){t.style.display='none'},2800)}
function esc(s){var d=document.createElement('div');d.textContent=(s==null?'':String(s));return d.innerHTML}
function v(id){return (document.getElementById(id).value||'').trim()}
var SW=['#d9748f','#e11d48','#f59e0b','#f97316','#10b981','#059669','#0891b2','#2563eb','#4f46e5','#7c3aed','#a855f7','#141b26'];
function setColor(hex,skip){
  if(!/^#[0-9a-fA-F]{6}$/.test(hex||''))return; hex=hex.toLowerCase();
  if(skip!=='text')document.getElementById('color').value=hex;
  if(skip!=='pick')document.getElementById('colorPick').value=hex;
  var p=document.getElementById('cprev');p.style.background=hex;
  p.textContent=(v('mark')||v('company')||'BRAND').toUpperCase().slice(0,14);
  document.querySelectorAll('.sw').forEach(function(s){s.classList.toggle('on',s.dataset.c===hex)});
}
document.getElementById('swatches').innerHTML=SW.map(function(c){
  return '<span class="sw" data-c="'+c+'" style="background:'+c+'"></span>'}).join('');
document.querySelectorAll('.sw').forEach(function(s){s.addEventListener('click',function(){setColor(s.dataset.c)})});
document.getElementById('colorPick').addEventListener('input',function(){setColor(this.value,'pick')});
document.getElementById('color').addEventListener('input',function(){setColor(this.value,'text')});
['mark','company'].forEach(function(id){document.getElementById(id).addEventListener('input',function(){setColor(v('color')||'#4f46e5')})});

var BRANDS=[];
function renderBrands(){
  document.getElementById('brandRows').innerHTML=BRANDS.map(function(b,i){
    return '<div class="brow"><input value="'+esc(b)+'" data-i="'+i+'" maxlength="60" placeholder="Brand name">'+
           '<button data-x="'+i+'">Remove</button></div>'}).join('')
    ||'<div class="muted">No brands yet — add the brands you give away.</div>';
  document.querySelectorAll('#brandRows input').forEach(function(el){
    el.addEventListener('input',function(){BRANDS[+el.dataset.i]=el.value})});
  document.querySelectorAll('#brandRows button[data-x]').forEach(function(b){
    b.addEventListener('click',function(){BRANDS.splice(+b.dataset.x,1);renderBrands()})});
}
document.getElementById('addBrand').addEventListener('click',function(){BRANDS.push('');renderBrands()});

function load(){
  fetch('/api/setup/status').then(function(r){return r.json()}).then(function(d){
    if(!d.ok)return;
    var o=d.org||{};
    document.getElementById('company').value=o.company_name||'';
    document.getElementById('mark').value=o.brand_mark||'';
    document.getElementById('sub').value=o.brand_sub||'';
    document.getElementById('logo').value=o.logo_url||'';
    setColor(o.brand_color||'#4f46e5');
    var a=d.address||{};
    [['aName','name'],['aPhone','phone'],['aStreet1','street1'],['aStreet2','street2'],
     ['aCity','city'],['aState','state'],['aZip','zip'],['aCountry','country']].forEach(function(p){
       document.getElementById(p[0]).value=a[p[1]]||(p[1]==='country'?'US':'')});
    BRANDS=(d.brands||[]).slice(); renderBrands();
    document.getElementById('pfill').style.width=(d.total?100*d.done/d.total:0)+'%';
    document.getElementById('checks').innerHTML=d.steps.map(function(s){
      var cnt=(s.count!=null&&s.count>0)?(' · '+s.count):'';
      return '<div class="chk'+(s.done?' on':'')+'"><div class="dot"></div><div class="ctxt"><b>'+esc(s.label)+cnt+'</b><div>'+esc(s.hint)+'</div></div></div>';
    }).join('')+'<div style="margin-top:10px;font-weight:800;color:#4f46e5">'+d.done+' of '+d.total+' complete</div>';
    document.getElementById('chSummary').innerHTML=(d.channels||[]).length
      ? 'Channels: <b>'+d.channels.map(function(c){return esc(c.name)}).join('</b>, <b>')+'</b> · Team: <b>'+d.users+'</b> user(s)'
      : 'No channels yet · Team: <b>'+d.users+'</b> user(s)';
  });
}
document.getElementById('saveCompany').addEventListener('click',function(){
  var b=this;b.disabled=true;
  fetch('/api/org/branding',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({company_name:v('company'),brand_mark:v('mark'),brand_sub:v('sub'),
                         brand_color:v('color'),logo_url:v('logo')})})
  .then(function(r){return r.json()}).then(function(d){
    b.disabled=false;
    if(d.ok===false){toast(d.error||'Failed',1);return}
    toast('Saved — reloading to apply your brand');setTimeout(function(){location.reload()},700);
  }).catch(function(){b.disabled=false;toast('Network error',1)});
});
document.getElementById('saveAddr').addEventListener('click',function(){
  var b=this;b.disabled=true;
  fetch('/api/ship-from',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({name:v('aName'),company:v('aName'),phone:v('aPhone'),street1:v('aStreet1'),
      street2:v('aStreet2'),city:v('aCity'),state:v('aState').toUpperCase(),zip:v('aZip'),
      country:(v('aCountry')||'US').toUpperCase()})})
  .then(function(r){return r.json()}).then(function(d){
    b.disabled=false; if(d.ok===false){toast(d.error||'Failed',1);return}
    toast('Address saved');load();
  }).catch(function(){b.disabled=false;toast('Network error',1)});
});
document.getElementById('saveBrands').addEventListener('click',function(){
  var b=this;b.disabled=true;
  fetch('/api/giveaway/brands',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({brands:BRANDS.filter(function(x){return (x||'').trim()})})})
  .then(function(r){return r.json()}).then(function(d){
    b.disabled=false; if(!d.ok){toast(d.error||'Failed',1);return}
    BRANDS=d.brands||[];renderBrands();toast('Brands saved');load();
  }).catch(function(){b.disabled=false;toast('Network error',1)});
});
load();
</script></body></html>'''


# ── PEACH BEAUTY SCANIT — live-selling product intelligence (mobile-first) ──
SCANIT_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
''' + _FONT + '''
<title>Peach Beauty Scanit</title>
__NAVBAR_CSS__
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--peach:#ff9e80;--blush:#ff6f91;--peachbg:#fff6f2;--card:#ffffff;--ink:#2b2230;--muted:#8a7f88;--line:#f0e2dc}
body{font-family:'DM Sans',-apple-system,sans-serif;background:var(--peachbg);color:var(--ink);min-height:100vh}
.sc-wrap{max-width:520px;margin:0 auto;padding:14px 14px 96px}
.sc-hero{display:flex;align-items:center;gap:10px;margin:6px 2px 16px}
.sc-hero .logo{font-size:26px}
.sc-hero .t{font-size:20px;font-weight:900;letter-spacing:-.4px}
.sc-hero .t span{color:var(--blush)}
.big-btn{display:flex;align-items:center;gap:14px;width:100%;background:var(--card);border:1px solid var(--line);border-radius:20px;padding:20px;margin-bottom:12px;cursor:pointer;text-align:left;font-family:inherit;box-shadow:0 6px 18px rgba(255,111,145,.06);transition:transform .1s}
.big-btn:active{transform:scale(.98)}
.big-btn .ic{width:52px;height:52px;border-radius:15px;display:flex;align-items:center;justify-content:center;font-size:26px;flex:none;background:linear-gradient(135deg,#ffd9cc,#ffc2d1)}
.big-btn .tx b{display:block;font-size:17px;font-weight:800}
.big-btn .tx span{font-size:13px;color:var(--muted)}
.entry{display:none;background:var(--card);border:1px solid var(--line);border-radius:16px;padding:14px;margin-bottom:12px}
.entry.on{display:block}
.entry input{width:100%;border:2px solid var(--line);border-radius:12px;padding:14px 16px;font-size:17px;font-family:inherit;outline:none;margin-bottom:10px}
.entry input:focus{border-color:var(--blush)}
.btn-p{background:linear-gradient(135deg,var(--peach),var(--blush));color:#fff;border:none;border-radius:12px;padding:13px 18px;font-size:15px;font-weight:800;cursor:pointer;font-family:inherit;width:100%}
.btn-s{background:#fff;border:1px solid var(--line);border-radius:12px;padding:11px 16px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit;color:var(--ink)}
#viewResult,#viewList,#viewAdmin{display:none}
.rimg{width:100%;height:230px;background:#fff center/contain no-repeat;border:1px solid var(--line);border-radius:20px;margin-bottom:14px;display:flex;align-items:center;justify-content:center;color:var(--muted);font-size:40px}
.rbrand{font-size:13px;font-weight:800;letter-spacing:1.5px;text-transform:uppercase;color:var(--blush)}
.rname{font-size:23px;font-weight:900;line-height:1.15;margin:2px 0 3px}
.rsize{font-size:15px;color:var(--muted);font-weight:600}
.confirm{background:#fff;border:1px dashed var(--blush);border-radius:16px;padding:14px;margin:14px 0;text-align:center}
.confirm .q{font-size:15px;font-weight:800;margin-bottom:10px}
.confirm .row{display:flex;gap:10px}
.msrp-card{background:linear-gradient(135deg,#fff,#fff6f2);border:1px solid var(--line);border-radius:20px;padding:18px;margin:14px 0;text-align:center}
.msrp-lbl{font-size:12px;font-weight:800;letter-spacing:1px;color:var(--muted);text-transform:uppercase}
.msrp-val{font-size:46px;font-weight:900;line-height:1;margin:4px 0 6px}
.conf{display:inline-block;font-size:12px;font-weight:800;padding:4px 12px;border-radius:20px}
.conf.verified{background:rgba(16,185,129,.14);color:#059669}
.conf.check{background:rgba(245,158,11,.16);color:#b45309}
.conf.unknown{background:rgba(148,163,184,.18);color:#64748b}
.msrp-src{font-size:12px;color:var(--muted);margin-top:8px}
.msrp-src a{color:var(--blush);font-weight:700}
.internal{background:#2b2230;color:#fff;border-radius:18px;padding:16px;margin:14px 0}
.internal .ihd{font-size:11px;font-weight:800;letter-spacing:1px;color:#ffb3c6;text-transform:uppercase;margin-bottom:10px}
.internal .irow{display:flex;justify-content:space-between;align-items:center;padding:6px 0;font-size:14px;border-top:1px solid rgba(255,255,255,.08)}
.internal .irow:first-of-type{border-top:none}
.internal .irow b{font-size:17px;font-weight:900}
.prio{padding:3px 10px;border-radius:20px;font-size:12px;font-weight:800}
.prio.hot{background:#ff4d6d;color:#fff}.prio.push{background:#ff9e80;color:#3a1e12}.prio.normal{background:rgba(255,255,255,.16);color:#fff}.prio.clearance{background:#64748b;color:#fff}
.sell-btns{display:flex;gap:10px;margin:14px 0}
.sell-btns button{flex:1;border:none;border-radius:16px;padding:16px;font-size:15px;font-weight:900;cursor:pointer;font-family:inherit;color:#fff}
.b-quick{background:linear-gradient(135deg,#7c3aed,#a855f7)}
.b-sell{background:linear-gradient(135deg,var(--peach),var(--blush))}
.script{display:none;background:#fff;border:1px solid var(--line);border-left:4px solid var(--blush);border-radius:14px;padding:16px;margin-bottom:12px;font-size:17px;line-height:1.5;font-weight:600}
.script.on{display:block}
.sec{margin:16px 0}
.sec h4{font-size:12px;font-weight:800;letter-spacing:1px;text-transform:uppercase;color:var(--muted);margin-bottom:8px}
.chips{display:flex;flex-wrap:wrap;gap:7px}
.chip{background:#fff;border:1px solid var(--line);border-radius:20px;padding:6px 13px;font-size:14px;font-weight:700}
.notecol{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px}
.notecol .nc{background:#fff;border:1px solid var(--line);border-radius:14px;padding:10px;text-align:center}
.notecol .nc .l{font-size:10px;font-weight:800;color:var(--blush);letter-spacing:.5px}
.notecol .nc .v{font-size:13px;font-weight:600;margin-top:3px}
.howto{background:#fff;border:1px solid var(--line);border-radius:14px;padding:14px;font-size:15px;line-height:1.5}
.res-card{display:flex;gap:12px;align-items:center;background:#fff;border:1px solid var(--line);border-radius:16px;padding:11px;margin-bottom:10px;cursor:pointer}
.res-card .ri{width:56px;height:56px;border-radius:12px;background:#fff6f2 center/contain no-repeat;flex:none;border:1px solid var(--line)}
.res-card .rb{font-size:11px;font-weight:800;color:var(--blush);text-transform:uppercase;letter-spacing:.5px}
.res-card .rn{font-size:15px;font-weight:800;line-height:1.2}
.res-card .rm{font-size:12px;color:var(--muted)}
.res-card .rp{margin-left:auto;font-weight:900;font-size:16px;text-align:right;white-space:nowrap}
.empty2{text-align:center;color:var(--muted);padding:50px 16px}
.empty2 .e{font-size:40px;margin-bottom:8px}
.topbar{display:flex;align-items:center;gap:10px;margin-bottom:14px}
.topbar .back{background:#fff;border:1px solid var(--line);border-radius:12px;padding:9px 14px;font-weight:800;cursor:pointer;font-family:inherit;font-size:14px}
.topbar .fav{margin-left:auto;background:#fff;border:1px solid var(--line);border-radius:12px;padding:9px 13px;cursor:pointer;font-size:18px}
.searchbar{display:flex;gap:8px;margin-bottom:14px}
.searchbar input{flex:1;border:2px solid var(--line);border-radius:12px;padding:13px 15px;font-size:16px;font-family:inherit;outline:none}
.searchbar input:focus{border-color:var(--blush)}
.botnav{position:fixed;bottom:0;left:0;right:0;background:#fff;border-top:1px solid var(--line);display:flex;z-index:50;max-width:520px;margin:0 auto}
.botnav button{flex:1;background:none;border:none;padding:10px 0 12px;font-family:inherit;font-size:11px;font-weight:700;color:var(--muted);cursor:pointer;display:flex;flex-direction:column;align-items:center;gap:3px}
.botnav button .bi{font-size:21px}
.botnav button.on{color:var(--blush)}
.cammodal{position:fixed;inset:0;background:#000;z-index:100;display:none;flex-direction:column}
.cammodal.on{display:flex}
.cammodal video{flex:1;width:100%;object-fit:cover}
.cambar{display:flex;align-items:center;justify-content:space-between;padding:14px 18px;color:#fff}
.cambar button{background:rgba(255,255,255,.2);border:none;color:#fff;border-radius:10px;padding:9px 16px;font-weight:800;cursor:pointer;font-family:inherit}
.camhint{position:absolute;bottom:30px;left:0;right:0;text-align:center;color:#fff;font-weight:700;text-shadow:0 1px 4px #000}
#viewAdmin .fld{margin-bottom:10px}
#viewAdmin label{display:block;font-size:12px;font-weight:800;color:var(--muted);margin-bottom:4px;text-transform:uppercase;letter-spacing:.4px}
#viewAdmin input,#viewAdmin textarea,#viewAdmin select{width:100%;border:2px solid var(--line);border-radius:10px;padding:11px 13px;font-size:15px;font-family:inherit;outline:none}
#viewAdmin input:focus,#viewAdmin textarea:focus{border-color:var(--blush)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.adminfab{position:fixed;bottom:78px;right:calc(50% - 250px);background:#2b2230;color:#fff;border:none;border-radius:50px;padding:12px 18px;font-weight:800;cursor:pointer;font-family:inherit;z-index:40;box-shadow:0 6px 18px rgba(0,0,0,.2)}
@media(max-width:540px){.adminfab{right:16px}}
.toast{position:fixed;bottom:90px;left:50%;transform:translateX(-50%);background:#2b2230;color:#fff;padding:12px 22px;border-radius:30px;font-weight:700;font-size:14px;z-index:120;display:none}
</style></head><body>
__NAVBAR__
<div class="sc-wrap">
  <div class="sc-hero"><span class="logo">🍑</span><div class="t">Peach Beauty <span>Scanit</span></div></div>
  <div id="viewHome">
    <button class="big-btn" onclick="openCam()"><span class="ic">▣</span><div class="tx"><b>Scan Barcode</b><span>Point your camera at the UPC / EAN</span></div></button>
    <button class="big-btn" onclick="toggleEntry()"><span class="ic">⌨️</span><div class="tx"><b>Enter Barcode</b><span>Type or paste the number</span></div></button>
    <div class="entry" id="entryBox"><input id="upcInput" inputmode="numeric" placeholder="Enter UPC / EAN" autocomplete="off"><button class="btn-p" onclick="lookupUpc()">Find product</button></div>
    <button class="big-btn" onclick="showTab('search')"><span class="ic">🔎</span><div class="tx"><b>Search Product</b><span>No barcode? Search by name + size</span></div></button>
  </div>
  <div id="viewResult"></div>
  <div id="viewList"></div>
  <div id="viewAdmin"></div>
</div>
<button class="adminfab" id="adminFab" style="display:none" onclick="editProduct(null)">＋ Add product</button>
<div class="botnav">
  <button data-tab="scan" class="on" onclick="showTab('scan')"><span class="bi">▣</span>Scan</button>
  <button data-tab="search" onclick="showTab('search')"><span class="bi">🔎</span>Search</button>
  <button data-tab="recent" onclick="showTab('recent')"><span class="bi">🕘</span>Recent</button>
  <button data-tab="fav" onclick="showTab('fav')"><span class="bi">⭐</span>Favorites</button>
</div>
<div class="cammodal" id="camModal">
  <div class="cambar"><b>🍑 Scan a barcode</b><button onclick="closeCam()">✕ Close</button></div>
  <video id="camVideo" playsinline muted></video>
  <div class="camhint">Aim at the barcode…</div>
</div>
<div class="toast" id="toast"></div>
<script>
var ISADMIN=('__ISADMIN__'==='1');
var CUR=null, FAVSET={}, camStream=null, detector=null, scanning=false;
function esc(s){var d=document.createElement('div');d.textContent=(s==null?'':String(s));return d.innerHTML}
function money(v){if(v==null||v==='')return '';return '$'+Number(v).toLocaleString(undefined,{maximumFractionDigits:0})}
function toast(m){var t=document.getElementById('toast');t.textContent=m;t.style.display='block';setTimeout(function(){t.style.display='none'},2200)}
if(ISADMIN)document.getElementById('adminFab').style.display='block';
function hideAll(){['viewHome','viewResult','viewList','viewAdmin'].forEach(function(id){document.getElementById(id).style.display='none'})}
function setNav(tab){document.querySelectorAll('.botnav button').forEach(function(b){b.classList.toggle('on',b.dataset.tab===tab)})}
function showTab(tab){
  document.getElementById('adminFab').style.display=(ISADMIN&&(tab==='search'||tab==='scan'))?'block':'none';
  if(tab==='scan'){hideAll();document.getElementById('viewHome').style.display='block';setNav('scan');return}
  if(tab==='search'){renderSearch();setNav('search');return}
  if(tab==='recent'){loadList('/api/scanit/recent','🕘 Recent scans','Nothing scanned yet');setNav('recent');return}
  if(tab==='fav'){loadList('/api/scanit/favorites','⭐ Favorites','Star products you sell often');setNav('fav');return}
}
function toggleEntry(){var e=document.getElementById('entryBox');e.classList.toggle('on');if(e.classList.contains('on'))document.getElementById('upcInput').focus()}
document.getElementById('upcInput').addEventListener('keydown',function(e){if(e.key==='Enter')lookupUpc()});
function lookupUpc(){
  var v=(document.getElementById('upcInput').value||'').replace(/[\\s\\-]/g,'').trim();
  if(!v){toast('Enter a barcode');return}
  fetch('/api/scanit/lookup?upc='+encodeURIComponent(v)).then(function(r){return r.json()}).then(function(d){
    if(!d.ok){toast(d.error||'Lookup failed');return}
    if(d.found){openProduct(d.product);}else notFound(v);
  });
}
function notFound(upc){
  hideAll();setNav('scan');var v=document.getElementById('viewResult');v.style.display='block';
  v.innerHTML='<div class="topbar"><button class="back" onclick="showTab(\\'scan\\')">← Back</button></div>'+
    '<div class="empty2"><div class="e">🍑</div><div style="font-size:18px;font-weight:800">We don\\'t know this barcode yet</div>'+
    '<div style="font-family:monospace;color:var(--muted);margin:6px 0 16px">'+esc(upc)+'</div>'+
    '<button class="btn-p" style="margin-bottom:10px" onclick="showTab(\\'search\\')">🔎 Search product manually</button>'+
    (ISADMIN?'<button class="btn-s" onclick="editProduct(null,\\''+esc(upc)+'\\')">➕ Add new product</button>':'')+'</div>';
}
function openProduct(p){
  CUR=p; hideAll(); setNav('scan');
  fetch('/api/scanit/recent',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({product_id:p.id})});
  var v=document.getElementById('viewResult'); v.style.display='block';
  var conf=(p.verification_status||'unknown');
  var confTxt={verified:'✓ OFFICIAL BRAND PRICE',check:'⚠ CHECK — not fully confirmed',unknown:'⚠ OFFICIAL MSRP NOT VERIFIED'}[conf];
  var msrp=(conf==='verified'&&p.msrp!=null&&p.msrp!=='')?money(p.msrp):null;
  var img=p.image_url?('style="background-image:url(\\''+esc(p.image_url)+'\\')"'):'';
  var fav=!!FAVSET[p.id];
  var sizeline=[p.size,p.size_unit].filter(Boolean).join(' ');
  var h='<div class="topbar"><button class="back" onclick="showTab(\\'scan\\')">← Back</button>'+
        '<button class="fav" onclick="toggleFav('+p.id+',this)">'+(fav?'⭐':'☆')+'</button></div>';
  h+='<div class="rimg" '+img+'>'+(p.image_url?'':'🍑')+'</div>';
  h+='<div class="rbrand">'+esc(p.brand||'')+'</div><div class="rname">'+esc(p.product_name||'')+'</div>';
  h+='<div class="rsize">'+esc([p.variant,sizeline,p.concentration].filter(Boolean).join(' · '))+'</div>';
  h+='<div class="confirm"><div class="q">🍑 Is this the product in your hand?</div><div class="row">'+
     '<button class="btn-p" onclick="confirmYes()">✅ Yes, that\\'s it</button>'+
     '<button class="btn-s" style="flex:1" onclick="showTab(\\'search\\')">❌ No</button></div></div>';
  h+='<div id="afterConfirm" style="display:none">';
  h+='<div class="msrp-card"><div class="msrp-lbl">Official Retail / MSRP</div>'+
     '<div class="msrp-val">'+(msrp||'—')+'</div>'+
     '<span class="conf '+conf+'">'+confTxt+'</span>'+
     (p.msrp_url?('<div class="msrp-src">Source: <a href="'+esc(p.msrp_url)+'" target="_blank" rel="noopener">official page ↗</a>'+(p.msrp_verified_date?(' · '+esc(p.msrp_verified_date)):'')+'</div>'):'')+
     '</div>';
  if(p.target_price||p.min_price||(p.priority&&p.priority!=='normal')||p.host_note){
    h+='<div class="internal"><div class="ihd">🍑 Peach Beauty — internal</div>';
    if(p.target_price)h+='<div class="irow"><span>🎯 Our target</span><b>'+money(p.target_price)+'+</b></div>';
    if(p.min_price)h+='<div class="irow"><span>🚨 Do not clear below</span><b>'+money(p.min_price)+'</b></div>';
    if(p.priority&&p.priority!=='normal')h+='<div class="irow"><span>🔥 Priority</span><span class="prio '+esc(p.priority)+'">'+esc(p.priority.toUpperCase())+'</span></div>';
    if(p.host_note)h+='<div class="irow" style="display:block"><span>🎤 Host note</span><div style="margin-top:4px;font-weight:600">'+esc(p.host_note)+'</div></div>';
    h+='</div>';
  }
  h+='<div class="sell-btns"><button class="b-quick" onclick="genScript('+p.id+',\\'quick\\')">⚡ Quick Sell</button>'+
     '<button class="b-sell" onclick="genScript('+p.id+',\\'sell\\')">🎤 Sell It</button></div>';
  h+='<div class="script" id="scriptBox"></div>';
  h+=catInfo(p);
  if(ISADMIN)h+='<button class="btn-s" style="width:100%;margin-top:8px" onclick="editProduct(CUR)">✏️ Edit product (admin)</button>';
  h+='</div>';
  v.innerHTML=h;
}
function confirmYes(){document.getElementById('afterConfirm').style.display='block';document.querySelector('.confirm').style.display='none'}
function catInfo(p){
  var h='';
  function chips(arr,title){if(!arr||!arr.length)return '';return '<div class="sec"><h4>'+title+'</h4><div class="chips">'+arr.map(function(x){return '<span class="chip">'+esc(x)+'</span>'}).join('')+'</div></div>'}
  h+=chips(p.benefits,'⭐ Why people love it');
  h+=chips(p.key_points,'🍑 Key benefits');
  if(p.notes_top||p.notes_heart||p.notes_base){
    h+='<div class="sec"><h4>Fragrance notes</h4><div class="notecol">'+
      '<div class="nc"><div class="l">TOP</div><div class="v">'+esc(p.notes_top||'—')+'</div></div>'+
      '<div class="nc"><div class="l">HEART</div><div class="v">'+esc(p.notes_heart||'—')+'</div></div>'+
      '<div class="nc"><div class="l">BASE</div><div class="v">'+esc(p.notes_base||'—')+'</div></div></div></div>';
  }
  var meta=[];
  if(p.fragrance_family)meta.push(['Family',p.fragrance_family]);
  if(p.vibe)meta.push(['Vibe',p.vibe]);
  if(p.best_for)meta.push(['Best for',p.best_for]);
  if(p.finish)meta.push(['Finish',p.finish]);
  if(p.coverage)meta.push(['Coverage',p.coverage]);
  if(p.skin_type)meta.push(['Skin type',p.skin_type]);
  if(p.hair_type)meta.push(['Hair type',p.hair_type]);
  if(meta.length)h+='<div class="sec"><div class="chips">'+meta.map(function(m){return '<span class="chip"><b style="color:var(--blush)">'+esc(m[0])+':</b> '+esc(m[1])+'</span>'}).join('')+'</div></div>';
  if(p.how_to_use)h+='<div class="sec"><h4>How to use</h4><div class="howto">'+esc(p.how_to_use)+'</div></div>';
  if(p.ingredients)h+='<div class="sec"><h4>Key ingredients</h4><div class="howto">'+esc(p.ingredients)+'</div></div>';
  return h;
}
function genScript(pid,kind){
  var box=document.getElementById('scriptBox');box.classList.add('on');box.textContent='Writing…';
  fetch('/api/scanit/product/'+pid+'/scripts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})}).then(function(r){return r.json()}).then(function(d){
    if(!d.ok){box.textContent=d.error||'Could not generate';return}
    box.textContent=(kind==='quick'?d.quick:d.sell)||'(empty)';
  });
}
function toggleFav(pid,btn){
  fetch('/api/scanit/favorite',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({product_id:pid})}).then(function(r){return r.json()}).then(function(d){
    if(d.ok){FAVSET[pid]=d.favorited;if(btn)btn.textContent=d.favorited?'⭐':'☆';toast(d.favorited?'Added to favorites':'Removed')}
  });
}
function renderSearch(){
  hideAll();var v=document.getElementById('viewList');v.style.display='block';
  v.innerHTML='<div class="searchbar"><input id="qIn" placeholder="e.g. Dior J\\'adore EDP 50ml" autocomplete="off"><button class="btn-p" style="width:auto" onclick="runSearch()">Find</button></div><div id="results"></div>';
  var qi=document.getElementById('qIn');qi.focus();
  var tmr;qi.addEventListener('input',function(){clearTimeout(tmr);tmr=setTimeout(runSearch,300)});
  qi.addEventListener('keydown',function(e){if(e.key==='Enter')runSearch()});
}
function runSearch(){
  var q=(document.getElementById('qIn').value||'').trim();var box=document.getElementById('results');
  if(q.length<2){box.innerHTML='';return}
  fetch('/api/scanit/search?q='+encodeURIComponent(q)).then(function(r){return r.json()}).then(function(d){
    box.innerHTML=(d.results&&d.results.length)?d.results.map(cardHtml).join(''):'<div class="empty2"><div class="e">🔎</div>No matches — try fewer words'+(ISADMIN?'<br><button class="btn-s" style="margin-top:12px" onclick="editProduct(null)">➕ Add this product</button>':'')+'</div>';
  });
}
function loadList(url,title,emptyMsg){
  hideAll();var v=document.getElementById('viewList');v.style.display='block';
  v.innerHTML='<h4 style="font-size:13px;font-weight:800;text-transform:uppercase;color:var(--muted);margin:2px 2px 12px">'+title+'</h4><div id="results">Loading…</div>';
  fetch(url).then(function(r){return r.json()}).then(function(d){
    (d.results||[]).forEach(function(p){if(url.indexOf('favorites')>=0)FAVSET[p.id]=true});
    document.getElementById('results').innerHTML=(d.results&&d.results.length)?d.results.map(cardHtml).join(''):'<div class="empty2"><div class="e">🍑</div>'+emptyMsg+'</div>';
  });
}
function cardHtml(p){
  var img=p.image_url?('style="background-image:url(\\''+esc(p.image_url)+'\\')"'):'';
  var sizeline=[p.size,p.size_unit].filter(Boolean).join(' ');
  var price=(p.verification_status==='verified'&&p.msrp)?money(p.msrp):'';
  return '<div class="res-card" onclick="openById('+p.id+')"><div class="ri" '+img+'></div>'+
    '<div style="min-width:0"><div class="rb">'+esc(p.brand||'')+'</div><div class="rn">'+esc(p.product_name||'')+'</div>'+
    '<div class="rm">'+esc([p.variant,sizeline].filter(Boolean).join(' · '))+'</div></div>'+
    '<div class="rp">'+price+'</div></div>';
}
function openById(id){fetch('/api/scanit/product/'+id).then(function(r){return r.json()}).then(function(d){if(d.ok)openProduct(d.product)})}
function openCam(){
  if(!('BarcodeDetector' in window)){toast('Camera scan not supported here — use Enter Barcode');toggleEntry();return}
  var m=document.getElementById('camModal');m.classList.add('on');
  try{detector=new window.BarcodeDetector({formats:['ean_13','ean_8','upc_a','upc_e','code_128']});}catch(e){detector=new window.BarcodeDetector();}
  navigator.mediaDevices.getUserMedia({video:{facingMode:'environment'}}).then(function(s){
    camStream=s;var vid=document.getElementById('camVideo');vid.srcObject=s;vid.play();scanning=true;scanLoop();
  }).catch(function(){toast('Camera blocked — use Enter Barcode');closeCam();toggleEntry();});
}
function scanLoop(){
  if(!scanning)return;var vid=document.getElementById('camVideo');
  detector.detect(vid).then(function(codes){
    if(codes&&codes.length){var raw=(codes[0].rawValue||'').replace(/[\\s\\-]/g,'');if(raw){scanning=false;closeCam();document.getElementById('upcInput').value=raw;lookupUpc();return}}
    requestAnimationFrame(scanLoop);
  }).catch(function(){requestAnimationFrame(scanLoop)});
}
function closeCam(){scanning=false;document.getElementById('camModal').classList.remove('on');if(camStream){camStream.getTracks().forEach(function(t){t.stop()});camStream=null}}
var AF=['brand','product_name','variant','category','size','size_unit','concentration','upc','image_url','msrp','msrp_url','notes_top','notes_heart','notes_base','fragrance_family','vibe','best_for','finish','coverage','skin_type','hair_type','ingredients','how_to_use','host_note','target_price','min_price'];
function editProduct(p,presetUpc){
  if(!ISADMIN)return; p=p||{}; hideAll();var v=document.getElementById('viewAdmin');v.style.display='block';setNav('scan');
  document.getElementById('adminFab').style.display='none';
  function f(id,lbl,ph,val){return '<div class="fld"><label>'+lbl+'</label><input id="f_'+id+'" placeholder="'+(ph||'')+'" value="'+esc(val==null?'':val)+'"></div>'}
  function ta(id,lbl,val){return '<div class="fld"><label>'+lbl+'</label><textarea id="f_'+id+'" rows="2">'+esc(val==null?'':val)+'</textarea></div>'}
  var conf=p.verification_status||'unknown';
  var x='<div class="topbar"><button class="back" onclick="showTab(\\'scan\\')">← Back</button><b style="font-size:16px">'+(p.id?'Edit product':'Add product')+'</b></div>';
  x+='<div class="grid2">'+f('brand','Brand','Dior',p.brand)+f('product_name','Product name',"J'adore EDP",p.product_name)+'</div>';
  x+='<div class="grid2">'+f('variant','Variant','Eau de Parfum',p.variant)+f('concentration','Concentration','EDP',p.concentration)+'</div>';
  x+='<div class="grid2">'+f('size','Size','50',p.size)+f('size_unit','Unit','ml',p.size_unit)+'</div>';
  x+='<div class="grid2">'+f('category','Category','fragrance',p.category)+f('upc','UPC / barcode','',(presetUpc||p.upc))+'</div>';
  x+=f('image_url','Product image URL (official)','https://...',p.image_url);
  x+='<div class="fld"><label>Official MSRP ($) — verified from brand site</label><div class="grid2"><input id="f_msrp" inputmode="decimal" placeholder="140" value="'+esc(p.msrp==null?'':p.msrp)+'"><select id="f_verification_status"><option value="unknown"'+(conf==='unknown'?' selected':'')+'>Not verified</option><option value="check"'+(conf==='check'?' selected':'')+'>Check</option><option value="verified"'+(conf==='verified'?' selected':'')+'>Official verified</option></select></div></div>';
  x+=f('msrp_url','Official source URL','https://dior.com/...',p.msrp_url);
  x+='<div class="grid2">'+f('target_price','Our target ($)','65',p.target_price)+f('min_price','Do not clear below ($)','55',p.min_price)+'</div>';
  x+='<div class="fld"><label>Priority</label><select id="f_priority"><option value="normal">Normal</option><option value="hot">Hot</option><option value="push">Push</option><option value="clearance">Clearance</option></select></div>';
  x+=ta('host_note','Host note',p.host_note);
  x+=ta('benefits','Why people love it (one per line)',(p.benefits||[]).join('\\n'));
  x+=ta('key_points','Key benefits (one per line)',(p.key_points||[]).join('\\n'));
  x+='<div class="grid2">'+f('notes_top','Top notes','Pear • Bergamot',p.notes_top)+f('notes_heart','Heart notes','Jasmine • Rose',p.notes_heart)+'</div>';
  x+='<div class="grid2">'+f('notes_base','Base notes','Vanilla • Musk',p.notes_base)+f('fragrance_family','Family','Floral',p.fragrance_family)+'</div>';
  x+='<div class="grid2">'+f('vibe','Vibe','Elegant',p.vibe)+f('best_for','Best for','Date night',p.best_for)+'</div>';
  x+='<div class="grid2">'+f('finish','Finish','Dewy',p.finish)+f('coverage','Coverage','Medium',p.coverage)+'</div>';
  x+='<div class="grid2">'+f('skin_type','Skin type','All',p.skin_type)+f('hair_type','Hair type','',p.hair_type)+'</div>';
  x+=ta('ingredients','Key ingredients',p.ingredients);
  x+=ta('how_to_use','How to use',p.how_to_use);
  x+='<button class="btn-p" style="margin:12px 0" onclick="saveProduct('+(p.id||'null')+')">💾 Save product</button>';
  if(p.id)x+='<button class="btn-s" style="width:100%;color:#e11d48" onclick="delProduct('+p.id+')">Delete</button>';
  v.innerHTML=x;
  if(p.priority)document.getElementById('f_priority').value=p.priority;
}
function gv(id){var e=document.getElementById('f_'+id);return e?e.value.trim():''}
function saveProduct(id){
  var body={id:id||undefined};
  AF.forEach(function(k){body[k]=gv(k)});
  body.verification_status=gv('verification_status')||'unknown';
  body.priority=gv('priority')||'normal';
  body.benefits=gv('benefits').split('\\n').map(function(x){return x.trim()}).filter(Boolean);
  body.key_points=gv('key_points').split('\\n').map(function(x){return x.trim()}).filter(Boolean);
  ['msrp','target_price','min_price'].forEach(function(k){body[k]=body[k]?parseFloat(body[k]):null});
  if(!body.brand&&!body.product_name){toast('Brand or product name required');return}
  fetch('/api/scanit/product',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(function(r){return r.json()}).then(function(d){
    if(d.ok){toast('Saved');openProduct(d.product)}else toast(d.error||'Save failed');
  });
}
function delProduct(id){if(!confirm('Delete this product?'))return;fetch('/api/scanit/product/'+id+'/delete',{method:'POST'}).then(function(){toast('Deleted');showTab('search')})}
showTab('scan');
</script></body></html>'''
