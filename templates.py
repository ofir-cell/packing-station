"""
HTML templates and navbar helper for Packing Station.

All page templates are Python triple-quoted strings (no f-strings, to avoid
escaping nightmares with embedded JS/CSS). Route handlers replace placeholders
like `__NAME__`, `__NAVBAR__`, `__NAVBAR_CSS__` with `.replace()` at request time.
"""
from flask import session


def _navbar(active_page=""):
    """Generate the unified top navigation bar based on user role.
    `active_page` is the current page key for highlighting: dash|giveaway|users|badges|analytics."""
    role=session.get("role","")
    name=session.get("name","")
    if not role: return ""
    # Build the menu as a list of entries — either a single link tuple
    # (key, url, label) or a group dict {key, label, items:[...]}.
    # Goal: compress 9 flat items into 3-4 top-level entries with dropdowns.
    entries = [("home", "/home", "🏠 Home")]
    entries.append(("announcements", "/announcements", "📣 News"))
    if role == "worker":
        # Workers get a fast link straight to packing alongside Personal
        entries.append(("pack", "/", "📦 Pack"))
    entries.append({
        "key": "personal",
        "label": "👤 Personal",
        "items": [
            ("me", "/me", "My Profile"),
            ("leaderboard", "/leaderboard", "Leaderboard"),
            ("documents", "/documents", "Documents"),
            ("onboarding", "/onboarding", "Onboarding"),
        ],
    })
    if role in ("admin", "cs"):
        ops_items = [
            ("dash", "/dashboard", "Search Recordings"),
            ("giveaway", "/giveaway", "Giveaways"),
        ]
        if role == "admin":
            ops_items.append(("analytics", "/analytics", "Analytics"))
        entries.append({"key": "operations", "label": "📦 Operations", "items": ops_items})
    if role == "admin":
        entries.append({
            "key": "team",
            "label": "👥 Team",
            "items": [
                ("users", "/users", "Users"),
                ("badges", "/users/badges", "Badges"),
            ],
        })
    # Render
    nav_html = '<nav class="topnav"><div class="topnav-inner">'
    nav_html += '<a href="/home" class="topnav-brand"><span class="brand-mark">5&nbsp;SEC</span><span class="brand-sub">Employee Hub</span></a>'
    nav_html += '<div class="topnav-links">'
    for e in entries:
        if isinstance(e, tuple):
            key, url, label = e
            cls = "topnav-link active" if key == active_page else "topnav-link"
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
    nav_html += '<div class="topnav-user"><span class="topnav-name">' + name + '</span>'
    nav_html += '<a href="/logout" class="topnav-logout">Logout</a></div>'
    nav_html += '</div></nav>'
    # Single-open + click-outside-to-close behaviour
    nav_html += '<script>(function(){var ds=document.querySelectorAll(".nav-group");ds.forEach(function(d){d.addEventListener("toggle",function(){if(d.open)ds.forEach(function(o){if(o!==d)o.open=false})})});document.addEventListener("click",function(e){if(!e.target.closest(".nav-group"))ds.forEach(function(d){d.open=false})});document.addEventListener("keydown",function(e){if(e.key==="Escape")ds.forEach(function(d){d.open=false})})})();</script>'
    return nav_html

# CSS for the unified top navbar - injected into every page that uses it.
# Brand uses the 5 Second Beauty pink wordmark.
_NAVBAR_CSS='''<style>
:root{
  --brand:#f3c9c4;
  --brand-strong:#eab1a8;
  --brand-glow:rgba(243,201,196,.12);
  --bg:#0a0d14;
  --surface:rgba(255,255,255,.03);
  --border:rgba(255,255,255,.07);
  --text:#e4e8f1;
  --text-muted:#9ba9c1;
  --text-dim:#6b7a90;
}
.topnav{background:rgba(10,13,20,.92);border-bottom:1px solid var(--border);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);position:sticky;top:0;z-index:100;font-family:'DM Sans',sans-serif}
.topnav-inner{max-width:1600px;margin:0 auto;padding:0 28px;display:flex;align-items:center;gap:28px;height:64px}
.topnav-brand{display:flex;flex-direction:column;justify-content:center;line-height:1;text-decoration:none;flex-shrink:0;padding:6px 0}
.brand-mark{font-size:20px;font-weight:900;color:var(--brand);letter-spacing:1.5px;font-family:'DM Sans',sans-serif}
.brand-sub{font-size:9px;font-weight:700;color:var(--text-dim);letter-spacing:2.4px;text-transform:uppercase;margin-top:3px}
.topnav-brand:hover .brand-mark{color:var(--brand-strong)}
.topnav-links{display:flex;gap:2px;flex:1;align-items:center}
.topnav-link{color:var(--text-muted);text-decoration:none;font-size:13px;font-weight:600;padding:9px 14px;border-radius:10px;transition:all .15s;white-space:nowrap}
.topnav-link:hover{color:var(--text);background:rgba(255,255,255,.04)}
.topnav-link.active{color:var(--brand);background:var(--brand-glow);box-shadow:inset 0 0 0 1px rgba(243,201,196,.18)}
/* Dropdown groups using HTML <details> */
.nav-group{position:relative;list-style:none}
.nav-group>summary{list-style:none;cursor:pointer;display:inline-flex;align-items:center;gap:4px;user-select:none}
.nav-group>summary::-webkit-details-marker,.nav-group>summary::marker{display:none;content:""}
.nav-group.active>summary{color:var(--brand);background:var(--brand-glow);box-shadow:inset 0 0 0 1px rgba(243,201,196,.18)}
.nav-group .caret{font-size:9px;opacity:.6;transition:transform .15s;line-height:1}
.nav-group[open] .caret{transform:rotate(180deg);opacity:1}
.nav-menu{position:absolute;top:calc(100% + 6px);left:0;background:rgba(15,18,25,.98);border:1px solid var(--border);border-radius:12px;padding:5px;min-width:200px;z-index:110;box-shadow:0 12px 36px rgba(0,0,0,.4);animation:menuIn .15s ease-out;backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px)}
@keyframes menuIn{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:translateY(0)}}
.nav-menu-item{display:block;padding:9px 14px;font-size:13px;font-weight:600;color:var(--text-muted);text-decoration:none;border-radius:8px;transition:all .12s;white-space:nowrap}
.nav-menu-item:hover{color:var(--text);background:rgba(255,255,255,.05)}
.nav-menu-item.active{color:var(--brand);background:var(--brand-glow)}
.topnav-user{display:flex;align-items:center;gap:12px;flex-shrink:0}
.topnav-name{font-size:13px;color:var(--text-dim);font-weight:600}
.topnav-logout{color:#fb7185;text-decoration:none;font-size:12px;font-weight:600;padding:7px 14px;border-radius:9px;background:rgba(244,63,94,.06);border:1px solid rgba(244,63,94,.14);transition:all .15s}
.topnav-logout:hover{background:rgba(244,63,94,.14)}
@media(max-width:768px){
.topnav-inner{padding:0 14px;gap:10px;height:auto;flex-wrap:wrap;padding-top:10px;padding-bottom:10px}
.brand-mark{font-size:17px}
.topnav-links{order:3;width:100%;overflow-x:visible;flex:initial;padding-bottom:4px;flex-wrap:wrap}
.topnav-links::-webkit-scrollbar{display:none}
.topnav-user{order:2;margin-left:auto}
.topnav-name{display:none}
.nav-menu{position:static;margin-top:4px;width:100%;animation:none;background:rgba(255,255,255,.03);box-shadow:none}
}
</style>'''


_FONT = '<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">'

LOGIN_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>5 SEC — Employee Hub</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#0a0d14;color:#e4e8f1;display:flex;align-items:center;justify-content:center;min-height:100vh;overflow:hidden;-webkit-font-smoothing:antialiased}
.glow{position:fixed;border-radius:50%;filter:blur(120px);opacity:.18;pointer-events:none}
.g1{width:640px;height:640px;top:-220px;right:-160px;background:#f3c9c4}
.g2{width:480px;height:480px;bottom:-140px;left:-120px;background:#a855f7}
.wrap{position:relative;z-index:1;width:100%;max-width:440px;padding:24px}
.logo{text-align:center;margin-bottom:36px}
.brand-mark-big{font-size:54px;font-weight:900;color:#f3c9c4;letter-spacing:4px;line-height:1;margin-bottom:12px;text-shadow:0 8px 32px rgba(243,201,196,.25)}
.brand-sub-big{font-size:11px;font-weight:700;color:#6b7a90;letter-spacing:4px;text-transform:uppercase}
.card{background:rgba(21,25,33,.6);backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px);border:1px solid rgba(255,255,255,.06);border-radius:22px;padding:40px 36px}
.card h2{font-size:24px;font-weight:800;margin-bottom:4px;color:#fff}
.card .sub{font-size:13px;color:#9ba9c1;margin-bottom:28px}
.field{margin-bottom:18px}
.field label{display:block;font-size:11px;font-weight:700;color:#9ba9c1;margin-bottom:8px;text-transform:uppercase;letter-spacing:.8px}
.field input{width:100%;background:rgba(11,14,20,.7);border:2px solid rgba(255,255,255,.06);border-radius:12px;padding:15px 18px;font-size:16px;color:#e4e8f1;font-family:inherit;outline:none;transition:all .2s}
.field input:focus{border-color:#f3c9c4;box-shadow:0 0 0 3px rgba(243,201,196,.12)}
.field input::placeholder{color:#3a4252}
.btn{width:100%;border:none;border-radius:12px;padding:16px;font-size:15px;font-weight:800;cursor:pointer;font-family:inherit;transition:all .15s;letter-spacing:.5px}
.btn-primary{background:#f3c9c4;color:#1a0e0b;margin-top:8px;box-shadow:0 8px 28px rgba(243,201,196,.22)}
.btn-primary:hover{background:#eab1a8;transform:translateY(-1px);box-shadow:0 10px 36px rgba(243,201,196,.32)}
.btn-primary:active{transform:scale(.98)}
.err{color:#f43f5e;font-size:13px;margin-top:14px;text-align:center;min-height:18px}
.foot{text-align:center;margin-top:28px;font-size:11px;color:#2a3040;letter-spacing:1.5px}
</style></head><body>
<div class="glow g1"></div><div class="glow g2"></div>
<div class="wrap">
<div class="logo"><div class="brand-mark-big">5&nbsp;SEC</div><div class="brand-sub-big">Employee Hub</div></div>
<div class="card">
<h2>Welcome back</h2><p class="sub">Sign in to start your shift</p>
<div class="field"><label>Username</label><input type="text" id="u" placeholder="Enter your username" autofocus></div>
<div class="field"><label>Password</label><input type="password" id="p" placeholder="Enter your password"></div>
<button class="btn btn-primary" id="loginBtn">Sign In</button>
<div class="err" id="e"></div>
</div>
<div class="foot">5 SECOND BEAUTY &copy; 2026</div>
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
        // Workers see a choice screen between Portal and Packing.
        // Admin/CS skip it (they don't pack).
        window.location.href = d.role==='worker' ? '/welcome' : '/';
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
body{font-family:'DM Sans',sans-serif;background:#0c0f16;color:#e4e8f1;display:flex;align-items:center;justify-content:center;min-height:100vh}
.wrap{text-align:center;padding:24px;width:100%;max-width:700px}
.hi{font-size:16px;color:#6b7a90;margin-bottom:4px}
.hi b{color:#a5b4fc}
.title{font-size:34px;font-weight:800;margin-bottom:8px}
.sub{font-size:16px;color:#6b7a90;margin-bottom:44px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:16px}
.s-btn{background:rgba(21,25,33,.8);border:2px solid rgba(255,255,255,.06);border-radius:18px;padding:32px 16px;cursor:pointer;transition:all .25s;text-align:center}
.s-btn:hover{border-color:#4f46e5;background:rgba(79,70,229,.08);transform:translateY(-4px);box-shadow:0 8px 30px rgba(79,70,229,.15)}
.s-btn:active{transform:scale(.96)}
.s-icon{font-size:36px;margin-bottom:12px}
.s-name{font-size:17px;font-weight:700}
.s-id{font-size:12px;color:#6b7a90;margin-top:4px}
.out{position:fixed;top:20px;right:20px;color:#6b7a90;text-decoration:none;font-size:13px;border:1px solid rgba(255,255,255,.08);padding:8px 16px;border-radius:10px;transition:all .2s}
.out:hover{color:#e4e8f1;border-color:rgba(255,255,255,.15)}
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
<title>Packing Station</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{height:100%;overflow:hidden}
body{font-family:'DM Sans',sans-serif;display:flex;flex-direction:column;align-items:center;justify-content:center;transition:background .4s}
body.sr{background:#0c0f16}body.sc{background:#1c0a0f}body.sd{background:#061a0f}body.su{background:#0c0f16}
.x{display:none;text-align:center;padding:24px;width:100%}
.x.on{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:80vh}
.top{position:fixed;top:0;left:0;right:0;padding:14px 20px;display:flex;justify-content:space-between;align-items:center;z-index:10}
.badge{background:rgba(79,70,229,.15);border:1.5px solid rgba(79,70,229,.3);border-radius:50px;padding:8px 20px;font-size:13px;font-weight:700;color:#a5b4fc}
.top-r{display:flex;gap:10px;align-items:center}
.cam{display:flex;align-items:center;gap:5px;font-size:12px;padding:6px 12px;border-radius:20px;background:rgba(0,0,0,.3)}
.cam-d{width:7px;height:7px;border-radius:50%}
.cam.ok .cam-d{background:#10b981}.cam.ok span{color:#10b981}
.cam.err .cam-d{background:#f43f5e}.cam.err span{color:#f43f5e}
.out-b{background:none;border:1px solid rgba(255,255,255,.08);border-radius:8px;padding:6px 14px;font-size:12px;color:#6b7a90;cursor:pointer;font-family:inherit}
.pv{position:fixed;bottom:16px;left:16px;width:150px;border-radius:12px;overflow:hidden;border:2px solid rgba(255,255,255,.06);opacity:.35;transition:all .3s}
.pv video{width:100%;display:block}
body.sc .pv{width:200px;opacity:1;border-color:#f43f5e}

.r-icon{width:120px;height:120px;background:rgba(21,25,33,.8);border-radius:30px;display:flex;align-items:center;justify-content:center;font-size:56px;margin-bottom:32px;border:2.5px solid rgba(255,255,255,.06)}
.r-title{font-size:40px;font-weight:800;margin-bottom:10px}
.r-sub{font-size:18px;color:#6b7a90;margin-bottom:36px}
.inp-w{width:100%;max-width:500px}
.inp{width:100%;background:rgba(21,25,33,.8);border:3px solid #4f46e5;border-radius:16px;padding:20px 24px;font-size:24px;color:#e4e8f1;font-family:inherit;text-align:center;outline:none;transition:all .2s}
.inp:focus{border-color:#818cf8;box-shadow:0 0 30px rgba(79,70,229,.25)}
.inp::placeholder{color:#3a4252}
.hint{margin-top:14px;font-size:14px;color:#6b7a90}
.pd{display:inline-block;width:8px;height:8px;background:#4f46e5;border-radius:50%;margin-right:8px;animation:pls 1.5s ease infinite}
@keyframes pls{0%,100%{opacity:.3;transform:scale(1)}50%{opacity:1;transform:scale(1.3)}}
.ctr{margin-top:36px;font-size:14px;color:#6b7a90}.ctr b{color:#a5b4fc}

.rp{display:flex;align-items:center;gap:12px;background:rgba(244,63,94,.1);border:2px solid rgba(244,63,94,.3);border-radius:50px;padding:12px 28px;margin-bottom:28px;animation:rpls 1.5s ease infinite}
@keyframes rpls{0%,100%{border-color:rgba(244,63,94,.3)}50%{border-color:rgba(244,63,94,.7)}}
.rd{width:15px;height:15px;background:#f43f5e;border-radius:50%;animation:bk 1s ease infinite}
@keyframes bk{0%,100%{opacity:1}50%{opacity:.2}}
.rl{font-size:18px;font-weight:800;color:#f43f5e;letter-spacing:1px}
.rk{font-size:48px;font-weight:900;color:#f1f5f9;margin-bottom:14px;letter-spacing:.5px}
.rm{font-size:72px;font-weight:900;color:#f43f5e;font-feature-settings:'tnum';margin-bottom:20px}
.steps{display:flex;flex-direction:column;gap:12px;margin-top:16px}
.step{display:flex;align-items:center;gap:12px;font-size:18px;color:#6b7a90}
.step.now{color:#f1f5f9;font-weight:700}
.si{width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:14px;background:rgba(21,25,33,.8);border:2px solid rgba(255,255,255,.08);flex-shrink:0}
.step.ok .si{background:#065f46;border-color:#10b981}
.step.now .si{background:#7c2d12;border-color:#f59e0b;animation:spls 1.5s ease infinite}
@keyframes spls{0%,100%{box-shadow:0 0 0 0 rgba(245,158,11,.2)}50%{box-shadow:0 0 0 8px rgba(245,158,11,0)}}
.hinp{position:absolute;top:-9999px;left:-9999px}

.d-icon{width:120px;height:120px;background:#065f46;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:60px;margin-bottom:24px;animation:pop .4s cubic-bezier(.175,.885,.32,1.275)}
@keyframes pop{0%{transform:scale(0)}100%{transform:scale(1)}}
.dt{font-size:40px;font-weight:800;color:#10b981;margin-bottom:6px}
.dk{font-size:26px;font-weight:700;margin-bottom:6px}
.dd{font-size:16px;color:#6b7a90;margin-bottom:28px}
.dn{font-size:16px;color:#6b7a90}

.us{width:48px;height:48px;border:4px solid rgba(255,255,255,.08);border-top-color:#4f46e5;border-radius:50%;animation:sp .8s linear infinite;margin-bottom:20px}
@keyframes sp{to{transform:rotate(360deg)}}
.ut{font-size:22px;font-weight:700;margin-bottom:6px}
.uu{font-size:15px;color:#6b7a90}

.w-icon{font-size:80px;margin-bottom:24px;animation:pop .5s cubic-bezier(.175,.885,.32,1.275)}
.w-title{font-size:38px;font-weight:900;color:#e4e8f1;margin-bottom:8px}
.w-sub{font-size:20px;color:#a5b4fc;margin-bottom:20px}
.w-sub b{color:#818cf8}
.w-msg{font-size:16px;color:#6b7a90;max-width:400px}

.f-icon{font-size:80px;margin-bottom:24px;animation:pop .5s cubic-bezier(.175,.885,.32,1.275)}
.f-title{font-size:38px;font-weight:900;color:#10b981;margin-bottom:8px}
.f-sub{font-size:20px;color:#e4e8f1;margin-bottom:20px}
.f-msg{font-size:16px;color:#6b7a90}
body.sw{background:linear-gradient(135deg,#0c0f16,#111827)}
body.sf{background:linear-gradient(135deg,#061a0f,#0c1a14)}
</style></head><body class="sr">
<div class="top"><div class="badge">__STATION__ — __NAME__</div><div class="top-r"><div class="cam" id="cm"><div class="cam-d"></div><span>Camera</span></div><button class="out-b" id="endBtn">End Shift</button></div></div>
<div class="pv"><video id="pv" autoplay muted playsinline></video></div>

<div class="x on" id="xw"><div class="w-icon">👋</div><div class="w-title">Welcome, __NAME__!</div><div class="w-sub">You are at <b>__STATION__</b></div><div class="w-msg">Have a great shift! Your camera is being set up...</div></div>

<div class="x" id="xr"><div class="r-icon">📦</div><div class="r-title">Scan Tracking Number</div><div class="r-sub">Scan the barcode to start recording</div><div class="inp-w"><input class="inp" id="mi" placeholder="Waiting for scan..." autocomplete="off"></div><div class="hint"><span class="pd"></span>Scanner ready</div><div class="ctr">Recorded: <b id="cn">0</b></div></div>

<div class="x" id="xc"><div class="rp"><div class="rd"></div><div class="rl">RECORDING</div></div><div class="rk" id="rk"></div><div class="rm" id="rmm">00:00</div><div class="steps"><div class="step ok"><div class="si">✓</div><span>Scan tracking number</span></div><div class="step now"><div class="si">2</div><span>Pack the order in front of the camera</span></div><div class="step"><div class="si">3</div><span>Scan again to finish</span></div></div><input class="hinp" id="ri" autocomplete="off"></div>

<div class="x" id="xu"><div class="us"></div><div class="ut">Saving recording...</div><div class="uu">Please wait</div></div>

<div class="x" id="xd"><div class="d-icon">✓</div><div class="dt">Saved!</div><div class="dk" id="dkk"></div><div class="dd" id="ddd"></div><div class="dn">Next order...</div></div>

<div class="x" id="xf"><div class="f-icon">🌟</div><div class="f-title">Great job today!</div><div class="f-sub">Thank you for your hard work, __NAME__</div><div class="f-msg">Have a wonderful day! See you next time 👋</div></div>

<script>
var st='w',ti=null,t0=0,n=0,mr=null,ch=[],sm=null,ct='';
var mi=document.getElementById('mi'),ri=document.getElementById('ri');
var X={w:document.getElementById('xw'),r:document.getElementById('xr'),c:document.getElementById('xc'),u:document.getElementById('xu'),d:document.getElementById('xd'),f:document.getElementById('xf')};
function go(s){st=s;document.body.className=s==='c'?'sc':s==='d'?'sd':s==='u'?'su':s==='w'?'sw':s==='f'?'sf':'sr';
for(var k in X)X[k].classList.toggle('on',k===s);
if(s==='r'){mi.value='';setTimeout(function(){mi.focus()},100)}
if(s==='c'){ri.value='';setTimeout(function(){ri.focus()},100)}}
setTimeout(function(){go('r')},3000);
document.getElementById('endBtn').addEventListener('click',function(){go('f');setTimeout(function(){location.href='/logout'},3500)});
document.addEventListener('click',function(){if(st==='r')mi.focus();if(st==='c')ri.focus()});
setInterval(function(){if(st==='r'&&document.activeElement!==mi)mi.focus();if(st==='c'&&document.activeElement!==ri)ri.focus()},400);
function initCam(){navigator.mediaDevices.getUserMedia({video:{width:{ideal:854},height:{ideal:480},frameRate:{ideal:15,max:24}},audio:false}).then(function(s){sm=s;document.getElementById('pv').srcObject=s;document.getElementById('cm').className='cam ok'}).catch(function(){document.getElementById('cm').className='cam err'})}
initCam();
function startRec(t){if(!sm){alert('No camera');return}ct=t;ch=[];mr=new MediaRecorder(sm,{mimeType:'video/webm;codecs=vp8',videoBitsPerSecond:500000});mr.ondataavailable=function(e){if(e.data.size>0)ch.push(e.data)};mr.start(1000);t0=Date.now();startTmr();document.getElementById('rk').textContent=t;go('c')}
function stopRec(){return new Promise(function(res){mr.onstop=res;mr.stop()})}
function capPhoto(){var v=document.getElementById('pv'),c=document.createElement('canvas');c.width=v.videoWidth;c.height=v.videoHeight;c.getContext('2d').drawImage(v,0,0);return new Promise(function(res){c.toBlob(res,'image/jpeg',.7)})}
function upload(){go('u');var dur=Math.round((Date.now()-t0)/1000);var vb=new Blob(ch,{type:'video/webm'});
capPhoto().then(function(pb){var fd=new FormData();fd.append('tracking',ct);fd.append('station','__SID__');fd.append('duration',dur);fd.append('video',vb,ct+'.webm');if(pb)fd.append('photo',pb,ct+'.jpg');
return fetch('/api/upload',{method:'POST',body:fd})}).then(function(r){return r.json()}).then(function(d){
if(d.ok){n++;document.getElementById('cn').textContent=n;document.getElementById('dkk').textContent=ct;document.getElementById('ddd').textContent='Duration: '+dur+'s';go('d');setTimeout(function(){go('r')},3000)}
else{alert('Failed');go('r')}}).catch(function(){alert('Upload failed');go('r')})}
mi.addEventListener('keydown',function(e){if(e.key==='Enter'){var t=mi.value.trim();if(t)startRec(t)}});
ri.addEventListener('keydown',function(e){if(e.key!=='Enter')return;var t=ri.value.trim();if(!t)return;stopTmr();
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
body{font-family:'DM Sans',sans-serif;background:#0c0f16;color:#e4e8f1;min-height:100vh}
.page-hdr{padding:24px 28px 8px;display:flex;align-items:center;justify-content:space-between;max-width:1600px;margin:0 auto;flex-wrap:wrap;gap:12px}
.page-title{display:flex;align-items:center;gap:10px;font-size:20px;font-weight:800}
.page-title-icon{width:36px;height:36px;background:linear-gradient(135deg,#4f46e5,#7c3aed);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px}
.stat-pills{display:flex;gap:8px;flex-wrap:wrap}
.pill{display:flex;align-items:center;gap:6px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.06);border-radius:20px;padding:6px 14px;font-size:12px;color:#6b7a90}
.pill b{color:#a5b4fc}

.search-area{padding:24px 28px 20px;max-width:720px;margin:0 auto}
.sb{display:flex;gap:10px}
.sb input{flex:1;background:rgba(21,25,33,.8);border:2px solid rgba(255,255,255,.06);border-radius:14px;padding:16px 20px;font-size:18px;color:#e4e8f1;font-family:inherit;outline:none;transition:all .2s}
.sb input:focus{border-color:#4f46e5;box-shadow:0 0 0 3px rgba(79,70,229,.1)}
.sb input::placeholder{color:#3a4252}
.sb button{background:linear-gradient(135deg,#4f46e5,#7c3aed);border:none;border-radius:14px;padding:16px 28px;font-size:16px;font-weight:700;color:white;cursor:pointer;font-family:inherit;box-shadow:0 4px 16px rgba(79,70,229,.25);transition:all .15s}
.sb button:hover{transform:translateY(-1px)}

.content{padding:0 28px 40px;max-width:920px;margin:0 auto}
.rc{background:rgba(21,25,33,.8);border:1px solid rgba(255,255,255,.06);border-radius:16px;margin-bottom:16px;overflow:hidden;animation:fu .3s ease}
@keyframes fu{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
.rc-h{padding:16px 20px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid rgba(255,255,255,.04)}
.rc-t{font-size:18px;font-weight:800;letter-spacing:.3px}
.rc-m{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.rc-m span{font-size:12px;color:#6b7a90;background:rgba(255,255,255,.04);padding:3px 10px;border-radius:8px}
.tag{padding:3px 10px;border-radius:8px;font-size:11px;font-weight:700}
.tag-s{background:rgba(245,158,11,.1);color:#f59e0b}
.tag-g{background:rgba(16,185,129,.1);color:#10b981}
.rc-b{padding:16px;display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:600px){.rc-b{grid-template-columns:1fr}}
.mb{border-radius:10px;overflow:hidden;background:#0c0f16;border:1px solid rgba(255,255,255,.04)}
.mb video,.mb img{width:100%;display:block}
.ml{padding:8px 14px;font-size:12px;color:#6b7a90;border-top:1px solid rgba(255,255,255,.04);display:flex;justify-content:space-between;align-items:center}
.dl-btn{color:#818cf8;text-decoration:none;font-size:12px;font-weight:700;padding:4px 12px;border-radius:8px;background:rgba(79,70,229,.1);border:1px solid rgba(79,70,229,.2);transition:all .15s}
.dl-btn:hover{background:rgba(79,70,229,.2)}

.sec-t{font-size:15px;font-weight:700;color:#6b7a90;margin:24px 0 12px;display:flex;align-items:center;gap:8px}
.tbl{width:100%;background:rgba(21,25,33,.8);border:1px solid rgba(255,255,255,.06);border-radius:14px;overflow:hidden}
.tbl table{width:100%;border-collapse:collapse}
.tbl th{background:rgba(255,255,255,.02);padding:12px 16px;font-size:11px;font-weight:700;color:#6b7a90;text-align:left;border-bottom:1px solid rgba(255,255,255,.04);text-transform:uppercase;letter-spacing:.4px}
.tbl td{padding:12px 16px;font-size:13px;border-bottom:1px solid rgba(255,255,255,.03)}
.tbl tr:last-child td{border-bottom:none}
.tbl tr:hover td{background:rgba(79,70,229,.04)}
.tbl tr{cursor:pointer;transition:background .15s}
.tc{font-weight:700;color:#a5b4fc}
.sn{font-weight:600;color:#f59e0b}
.wn{color:#6b7a90}
.empty{text-align:center;padding:52px 20px;color:#6b7a90}
.empty .ei{font-size:40px;margin-bottom:10px}
.empty .et{font-size:16px;font-weight:600;color:#e4e8f1}
.ld{text-align:center;padding:32px;color:#6b7a90}
.spn{width:28px;height:28px;border:3px solid rgba(255,255,255,.06);border-top-color:#4f46e5;border-radius:50%;animation:sp .8s linear infinite;margin:0 auto 8px}
@keyframes sp{to{transform:rotate(360deg)}}
.potm-wrap{max-width:1600px;margin:16px auto 0;padding:0 28px}
.potm-card{display:flex;align-items:center;gap:18px;padding:18px 24px;background:linear-gradient(135deg,rgba(251,191,36,.12),rgba(245,158,11,.04));border:1px solid rgba(251,191,36,.25);border-radius:16px;text-decoration:none;color:inherit;transition:transform .15s,border-color .15s}
.potm-card:hover{transform:translateY(-2px);border-color:rgba(251,191,36,.4)}
.potm-crown{font-size:42px;line-height:1;filter:drop-shadow(0 4px 8px rgba(251,191,36,.3))}
.potm-meta{flex:1}
.potm-label{font-size:11px;color:#fbbf24;text-transform:uppercase;letter-spacing:1px;font-weight:700;margin-bottom:2px}
.potm-name{font-size:20px;font-weight:800;color:#fff;margin-bottom:2px}
.potm-stats{font-size:13px;color:#9ba9c1}
.potm-stats b{color:#e4e8f1;font-weight:700}
.potm-cta{color:#fbbf24;font-size:13px;font-weight:700;padding:8px 14px;border:1px solid rgba(251,191,36,.3);border-radius:10px}
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
            h+='<div class="rc"><div class="rc-h"><span class="rc-t">'+d.tracking+'</span><div class="rc-m">';
            if(l){h+='<span>'+l.date+'</span><span>'+l.duration_seconds+'s</span>'}
            if(l&&l.worker)h+='<span>👤 '+l.worker+'</span>';
            h+='<span class="tag tag-s">'+v.station+'</span><span class="tag tag-g">✓ Found</span>';
            h+='</div></div><div class="rc-b"><div class="mb"><video controls preload="metadata"><source src="'+v.url+'" type="video/webm"></video><div class="ml"><span>🎥 Video · '+v.size_mb+' MB</span><a href="'+v.url+'" download class="dl-btn">⬇ Download</a></div></div>';
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
            rows+='<tr data-t="'+r.tracking_number+'"><td class="tc">'+r.tracking_number+'</td><td class="sn">'+(r.station||'-')+'</td><td class="wn">'+(r.worker||'-')+'</td><td>'+(r.date||'-')+'</td><td>'+(r.time||'-')+'</td><td>'+(r.duration_seconds||'-')+'s</td></tr>';
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
loadRecent();loadStats();loadPOTM();
</script></body></html>'''

# ── USERS MANAGEMENT ──────────────────────────────────────
USERS_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Manage Users</title>
__NAVBAR_CSS__
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#0c0f16;color:#e4e8f1;min-height:100vh}
.upage{padding:24px 28px;max-width:760px;margin:0 auto}
h1{font-size:24px;font-weight:800;margin-bottom:24px}
.card{background:rgba(21,25,33,.8);border:1px solid rgba(255,255,255,.06);border-radius:16px;padding:24px;margin-bottom:20px}
.card h2{font-size:14px;font-weight:700;color:#6b7a90;margin-bottom:16px;text-transform:uppercase;letter-spacing:.5px}
table{width:100%;border-collapse:collapse}
th{text-align:left;padding:10px 12px;font-size:11px;font-weight:700;color:#6b7a90;border-bottom:1px solid rgba(255,255,255,.04);text-transform:uppercase;letter-spacing:.3px}
td{padding:12px;font-size:14px;border-bottom:1px solid rgba(255,255,255,.03)}
tr:last-child td{border-bottom:none}
tr:hover td{background:rgba(79,70,229,.03)}
.role{padding:4px 10px;border-radius:8px;font-size:11px;font-weight:700;display:inline-block}
.r-admin{background:rgba(99,102,241,.1);color:#818cf8}
.r-worker{background:rgba(245,158,11,.1);color:#f59e0b}
.r-cs{background:rgba(16,185,129,.1);color:#10b981}
.actions{display:flex;gap:6px;flex-wrap:wrap}
.act-btn{border:none;padding:6px 14px;border-radius:8px;font-size:12px;font-weight:600;cursor:pointer;font-family:inherit;transition:all .15s}
.act-pw{background:rgba(79,70,229,.1);color:#a5b4fc;border:1px solid rgba(79,70,229,.2)}
.act-pw:hover{background:rgba(79,70,229,.2)}
.act-del{background:rgba(244,63,94,.08);color:#f43f5e;border:1px solid rgba(244,63,94,.2)}
.act-del:hover{background:rgba(244,63,94,.15)}
.add-form{display:grid;grid-template-columns:1fr 1fr;gap:10px}
@media(max-width:500px){.add-form{grid-template-columns:1fr}}
.add-form input,.add-form select{background:rgba(11,14,20,.8);border:1.5px solid rgba(255,255,255,.06);border-radius:10px;padding:12px 14px;color:#e4e8f1;font-size:14px;font-family:inherit;outline:none;transition:all .2s}
.add-form input:focus,.add-form select:focus{border-color:#4f46e5}
.add-form input::placeholder{color:#3a4252}
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
<select id="nr"><option value="worker">Worker</option><option value="cs">Customer Service</option><option value="admin">Admin</option></select>
<button class="add-btn" id="addBtn">+ Add User</button>
<div class="msg" id="am"></div>
</div></div>
<script>
function loadUsers(){
    fetch('/api/users').then(function(r){return r.json()}).then(function(d){
        var rows='';
        Object.keys(d).forEach(function(k){
            var v=d[k];
            var rc=v.role==='admin'?'r-admin':v.role==='cs'?'r-cs':'r-worker';
            rows+='<tr><td><b>'+k+'</b></td><td>'+v.name+'</td><td><span class="role '+rc+'">'+v.role+'</span></td><td>';
            if(k!=='admin'){
                rows+='<div class="actions"><button class="act-btn act-pw" data-u="'+k+'" data-a="pw">Change Password</button><button class="act-btn act-del" data-u="'+k+'" data-a="del">Delete</button></div>';
            }
            rows+='</td></tr>';
        });
        document.getElementById('ut').innerHTML=rows;
        document.querySelectorAll('[data-a="pw"]').forEach(function(b){
            b.addEventListener('click',function(){changePw(this.dataset.u)});
        });
        document.querySelectorAll('[data-a="del"]').forEach(function(b){
            b.addEventListener('click',function(){delUser(this.dataset.u)});
        });
    });
}
document.getElementById('addBtn').addEventListener('click',function(){
    var u=document.getElementById('nu').value.trim();
    var p=document.getElementById('np').value;
    var n=document.getElementById('nn').value.trim()||u;
    var rl=document.getElementById('nr').value;
    var m=document.getElementById('am');
    if(!u||!p){m.className='msg err';m.textContent='Username and password are required';return}
    fetch('/api/users/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p,name:n,role:rl})})
    .then(function(r){return r.json()}).then(function(d){
        if(d.ok){m.className='msg ok';m.textContent='User added successfully!';loadUsers();document.getElementById('nu').value='';document.getElementById('np').value='';document.getElementById('nn').value=''}
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
body{font-family:'DM Sans',sans-serif;background:#0c0f16;color:#e4e8f1;min-height:100vh}
.page-hdr{padding:24px 28px 8px;display:flex;align-items:center;gap:10px;max-width:1000px;margin:0 auto}
.page-title{display:flex;align-items:center;gap:10px;font-size:20px;font-weight:800}
.page-title-icon{width:36px;height:36px;background:linear-gradient(135deg,#f59e0b,#ef4444);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px}

.content{padding:0 28px 28px;max-width:1000px;margin:0 auto}

.big-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin-bottom:28px}
.big-stat{background:rgba(21,25,33,.8);border:1px solid rgba(255,255,255,.06);border-radius:16px;padding:24px;text-align:center}
.big-stat .num{font-size:42px;font-weight:900;line-height:1}
.big-stat .lbl{font-size:13px;color:#6b7a90;margin-top:8px;font-weight:500}
.c-blue .num{color:#818cf8}
.c-green .num{color:#10b981}
.c-orange .num{color:#f59e0b}
.c-pink .num{color:#f43f5e}

.sec{margin-bottom:28px}
.sec-t{font-size:17px;font-weight:800;margin-bottom:14px;display:flex;align-items:center;gap:8px}

.w-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px}
.w-card{background:rgba(21,25,33,.8);border:1px solid rgba(255,255,255,.06);border-radius:16px;padding:20px;transition:all .2s}
.w-card:hover{border-color:rgba(79,70,229,.2);background:rgba(21,25,33,.95)}
.w-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}
.w-name{font-size:18px;font-weight:800}
.w-badge{font-size:12px;font-weight:700;padding:4px 12px;border-radius:20px}
.w-active{background:rgba(16,185,129,.1);color:#10b981}
.w-idle{background:rgba(255,255,255,.04);color:#6b7a90}
.w-stats{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.w-stat{background:rgba(255,255,255,.03);border-radius:10px;padding:12px;text-align:center}
.w-stat .val{font-size:24px;font-weight:800;color:#e4e8f1}
.w-stat .lab{font-size:11px;color:#6b7a90;margin-top:2px;text-transform:uppercase;letter-spacing:.3px}
.w-stat.hl .val{color:#818cf8}

.d-table{width:100%;background:rgba(21,25,33,.8);border:1px solid rgba(255,255,255,.06);border-radius:14px;overflow:hidden}
.d-table table{width:100%;border-collapse:collapse}
.d-table th{background:rgba(255,255,255,.02);padding:12px 16px;font-size:11px;font-weight:700;color:#6b7a90;text-align:left;border-bottom:1px solid rgba(255,255,255,.04);text-transform:uppercase;letter-spacing:.4px}
.d-table td{padding:12px 16px;font-size:14px;border-bottom:1px solid rgba(255,255,255,.03)}
.d-table tr:last-child td{border-bottom:none}
.d-table tr:hover td{background:rgba(79,70,229,.03)}
.d-table .today{background:rgba(79,70,229,.06)}
.d-table .today td{font-weight:700;color:#a5b4fc}
.bar{height:6px;background:rgba(255,255,255,.06);border-radius:3px;overflow:hidden;margin-top:4px}
.bar-fill{height:100%;border-radius:3px;background:linear-gradient(90deg,#4f46e5,#818cf8)}

.ld{text-align:center;padding:40px;color:#6b7a90}
.spn{width:28px;height:28px;border:3px solid rgba(255,255,255,.06);border-top-color:#4f46e5;border-radius:50%;animation:sp .8s linear infinite;margin:0 auto 8px}
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
body{font-family:'DM Sans',sans-serif;background:#0c0f16;color:#e4e8f1;min-height:100vh}
.page-hdr{padding:24px 28px 8px;display:flex;align-items:center;justify-content:space-between;max-width:1600px;margin:0 auto}
.page-title{font-size:22px;font-weight:800}
.page-title span{color:#a5b4fc;margin-left:8px;font-weight:600;font-size:14px}
.wrap{max-width:1600px;margin:0 auto;padding:0 28px 28px}
.add-card{background:rgba(21,25,33,.6);border:1px solid rgba(255,255,255,.06);border-radius:16px;padding:20px 24px;margin-bottom:24px}
.add-title{font-size:14px;font-weight:700;color:#a5b4fc;margin-bottom:14px;text-transform:uppercase;letter-spacing:.6px}
.add-row{display:grid;grid-template-columns:1fr 2fr 1fr 1fr auto;gap:12px;align-items:end}
.f label{display:block;font-size:11px;font-weight:700;color:#6b7a90;margin-bottom:6px;text-transform:uppercase;letter-spacing:.5px}
.f input,.f select{width:100%;background:rgba(11,14,20,.8);border:2px solid rgba(255,255,255,.08);border-radius:10px;padding:11px 14px;font-size:14px;color:#e4e8f1;font-family:inherit;outline:none;transition:all .2s}
.f input:focus,.f select:focus{border-color:#4f46e5}
.btn{border:none;border-radius:10px;padding:11px 22px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit;transition:all .15s}
.btn-p{background:linear-gradient(135deg,#4f46e5,#7c3aed);color:white;box-shadow:0 4px 16px rgba(79,70,229,.3)}
.btn-p:hover{transform:translateY(-1px)}
.btn-s{background:rgba(255,255,255,.08);color:#e4e8f1;border:1px solid rgba(255,255,255,.1)}
.cols{display:grid;grid-template-columns:repeat(4,1fr);gap:18px}
@media(max-width:1100px){.cols{grid-template-columns:repeat(2,1fr)}.add-row{grid-template-columns:1fr 1fr;}}
@media(max-width:640px){.cols{grid-template-columns:1fr}.add-row{grid-template-columns:1fr}}
.col{background:rgba(21,25,33,.4);border:1px solid rgba(255,255,255,.04);border-radius:14px;padding:16px;min-height:200px}
.col-h{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;padding-bottom:12px;border-bottom:1px solid rgba(255,255,255,.05)}
.col-t{font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;display:flex;align-items:center;gap:8px}
.col.pa .col-t{color:#fbbf24}.col.ar .col-t{color:#60a5fa}.col.lc .col-t{color:#a78bfa}.col.sh .col-t{color:#34d399}
.cnt{font-size:11px;font-weight:700;background:rgba(255,255,255,.05);padding:3px 9px;border-radius:50px;color:#6b7a90}
.card{background:rgba(11,14,20,.6);border:1px solid rgba(255,255,255,.06);border-radius:10px;padding:14px;margin-bottom:10px;cursor:pointer;transition:all .15s;display:block;text-decoration:none;color:inherit}
.card:hover{transform:translateY(-1px);border-color:rgba(79,70,229,.4)}
.card-w{font-size:14px;font-weight:700;margin-bottom:4px}
.card-w .at{color:#6b7a90;font-weight:400}
.card-p{font-size:13px;color:#a5b4fc;margin-bottom:8px;line-height:1.4}
.card-m{display:flex;justify-content:space-between;align-items:center;font-size:11px;color:#6b7a90}
.card-m .pl{padding:2px 8px;border-radius:50px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;font-size:10px}
.pl.tt{background:rgba(244,63,94,.15);color:#fb7185}
.pl.wn{background:rgba(245,158,11,.15);color:#fbbf24}
.empty{text-align:center;color:#3a4252;font-size:13px;padding:30px 10px;font-style:italic}
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

<div class="cols">
<div class="col pa"><div class="col-h"><div class="col-t">📋 Pending Address</div><div class="cnt" id="c-pa">0</div></div><div id="g-pa"></div></div>
<div class="col ar"><div class="col-h"><div class="col-t">✏️ Address Received</div><div class="cnt" id="c-ar">0</div></div><div id="g-ar"></div></div>
<div class="col lc"><div class="col-h"><div class="col-t">📦 Label Created</div><div class="cnt" id="c-lc">0</div></div><div id="g-lc"></div></div>
<div class="col sh"><div class="col-h"><div class="col-t">✅ Shipped Today</div><div class="cnt" id="c-sh">0</div></div><div id="g-sh"></div></div>
</div>
</div>
<div class="toast" id="t"></div>
<script>
function toast(m,e){var t=document.getElementById('t');t.textContent=m;t.className=e?'toast err':'toast';t.style.display='block';setTimeout(function(){t.style.display='none'},3000)}
function timeAgo(ts){if(!ts)return '';var d=new Date(ts);var s=Math.floor((Date.now()-d.getTime())/1000);if(s<60)return s+'s ago';if(s<3600)return Math.floor(s/60)+'m ago';if(s<86400)return Math.floor(s/3600)+'h ago';return Math.floor(s/86400)+'d ago'}
function card(g){
    var pl=g.platform==='tiktok'?'<span class="pl tt">TikTok</span>':'<span class="pl wn">Whatnot</span>';
    var br=g.brand?' · '+g.brand:'';
    return '<a class="card" href="/giveaway/'+g.id+'">'+
        '<div class="card-w"><span class="at">@</span>'+g.winner_username+'</div>'+
        '<div class="card-p">'+g.prize_name+'</div>'+
        '<div class="card-m">'+pl+'<span>'+timeAgo(g.created_at)+br+'</span></div>'+
        '</a>';
}
function load(){
    fetch('/api/giveaway/list').then(function(r){return r.json()}).then(function(d){
        var br=document.getElementById('br');
        if(br.children.length===1){d.brands.forEach(function(b){var o=document.createElement('option');o.value=b;o.textContent=b;br.appendChild(o)})}
        var groups={pa:'pending_address',ar:'address_received',lc:'label_created',sh:'shipped'};
        Object.keys(groups).forEach(function(k){
            var arr=d.groups[groups[k]]||[];
            document.getElementById('c-'+k).textContent=arr.length;
            var html=arr.length?arr.map(card).join(''):'<div class="empty">No giveaways here</div>';
            document.getElementById('g-'+k).innerHTML=html;
        });
    });
}
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
body{font-family:'DM Sans',sans-serif;background:#0c0f16;color:#e4e8f1;min-height:100vh}
.page-hdr{padding:24px 28px 8px;display:flex;align-items:center;justify-content:space-between;max-width:900px;margin:0 auto}
.page-title{font-size:20px;font-weight:800}
.page-title-link{font-size:13px;color:#6b7a90;text-decoration:none;padding:6px 14px;border-radius:8px;background:rgba(255,255,255,.04)}
.page-title-link:hover{color:#a5b4fc;background:rgba(255,255,255,.08)}
.wrap{max-width:900px;margin:0 auto;padding:0 28px 28px}
.hdr{background:rgba(21,25,33,.6);border:1px solid rgba(255,255,255,.06);border-radius:16px;padding:24px 28px;margin-bottom:20px}
.hdr-top{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px}
.h-w{font-size:24px;font-weight:800;margin-bottom:4px}
.h-w .at{color:#6b7a90;font-weight:400}
.h-p{font-size:16px;color:#a5b4fc}
.status{padding:8px 18px;border-radius:50px;font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:.6px;white-space:nowrap}
.s-pa{background:rgba(251,191,36,.15);color:#fbbf24;border:1.5px solid rgba(251,191,36,.3)}
.s-ar{background:rgba(96,165,250,.15);color:#60a5fa;border:1.5px solid rgba(96,165,250,.3)}
.s-lc{background:rgba(167,139,250,.15);color:#a78bfa;border:1.5px solid rgba(167,139,250,.3)}
.s-sh{background:rgba(52,211,153,.15);color:#34d399;border:1.5px solid rgba(52,211,153,.3)}
.s-cl{background:rgba(244,63,94,.15);color:#fb7185;border:1.5px solid rgba(244,63,94,.3)}
.meta{display:flex;gap:18px;font-size:13px;color:#6b7a90}
.meta b{color:#e4e8f1}
.section{background:rgba(21,25,33,.6);border:1px solid rgba(255,255,255,.06);border-radius:16px;padding:24px 28px;margin-bottom:20px}
.section h3{font-size:14px;font-weight:700;color:#a5b4fc;margin-bottom:16px;text-transform:uppercase;letter-spacing:.6px}
.f{margin-bottom:14px}
.f label{display:block;font-size:11px;font-weight:700;color:#6b7a90;margin-bottom:6px;text-transform:uppercase;letter-spacing:.5px}
.f input,.f select,.f textarea{width:100%;background:rgba(11,14,20,.8);border:2px solid rgba(255,255,255,.08);border-radius:10px;padding:11px 14px;font-size:14px;color:#e4e8f1;font-family:inherit;outline:none;transition:all .2s}
.f input:focus,.f select:focus,.f textarea:focus{border-color:#4f46e5}
.f textarea{resize:vertical;min-height:90px;line-height:1.5}
.row{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.row3{display:grid;grid-template-columns:2fr 1fr 1fr;gap:14px}
.btn{border:none;border-radius:10px;padding:12px 24px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit;transition:all .15s}
.btn-p{background:linear-gradient(135deg,#4f46e5,#7c3aed);color:white;box-shadow:0 4px 16px rgba(79,70,229,.3)}
.btn-p:hover{transform:translateY(-1px)}
.btn-s{background:rgba(16,185,129,.15);color:#34d399;border:1.5px solid rgba(16,185,129,.3)}
.btn-s:hover{background:rgba(16,185,129,.25)}
.btn-d{background:rgba(244,63,94,.1);color:#fb7185;border:1.5px solid rgba(244,63,94,.2)}
.btn-d:hover{background:rgba(244,63,94,.2)}
.btn-ai{background:linear-gradient(135deg,#a78bfa,#ec4899);color:white;box-shadow:0 4px 16px rgba(167,139,250,.3)}
.btn-ai:hover{transform:translateY(-1px)}
.btn-ai:disabled{opacity:.5;cursor:not-allowed;transform:none}
.conf-badge{display:inline-block;padding:2px 9px;border-radius:50px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;margin-left:8px}
.conf-high{background:rgba(52,211,153,.15);color:#34d399}
.conf-medium{background:rgba(251,191,36,.15);color:#fbbf24}
.conf-low{background:rgba(244,63,94,.15);color:#fb7185}
.btn-row{display:flex;gap:10px;flex-wrap:wrap;margin-top:16px}
.toast{position:fixed;bottom:24px;right:24px;background:#10b981;color:white;padding:14px 22px;border-radius:10px;font-weight:600;box-shadow:0 10px 40px rgba(16,185,129,.4);z-index:100;display:none}
.toast.err{background:#f43f5e}
.tip{background:rgba(79,70,229,.08);border:1px solid rgba(79,70,229,.2);border-radius:10px;padding:14px 18px;font-size:13px;color:#a5b4fc;margin-bottom:14px;line-height:1.5}
.addr-display{background:rgba(11,14,20,.4);border-radius:10px;padding:14px 18px;font-size:14px;line-height:1.7;color:#e4e8f1;margin-bottom:14px}
.addr-display b{color:#a5b4fc}
.tracking{font-family:monospace;font-size:18px;color:#34d399;font-weight:700;letter-spacing:1px}
</style></head><body>
__NAVBAR__
<div class="page-hdr"><div class="page-title">🎁 Giveaway #__GID__</div><a href="/giveaway" class="page-title-link">← Back to Giveaways</a></div>
<div class="wrap" id="wrap"><div style="text-align:center;padding:60px;color:#6b7a90">Loading...</div></div>
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
            '<span id="parseStatus" style="align-self:center;font-size:13px;color:#6b7a90"></span></div>'+
            addressForm({})+
            '<div class="btn-row"><button class="btn btn-p" id="saveAddr">Save Address</button>'+
            '<button class="btn btn-d" id="cancel">Cancel Giveaway</button></div></div>';
    } else if(g.status==='address_received'||g.status==='label_created'){
        h+='<div class="section"><h3>📍 Shipping Address</h3>'+
            addressDisplay(g)+
            '<details><summary style="cursor:pointer;color:#a5b4fc;font-size:13px;margin-bottom:10px">✏️ Edit address</summary>'+
            addressForm(g)+
            '<button class="btn btn-p" id="saveAddr" style="margin-top:10px">Update Address</button></details></div>';
        h+='<div class="section"><h3>📦 Ship It</h3>'+
            '<div class="tip">⚙️ Phase A: Manual entry. Create the label in Shippo as usual, then enter the tracking number here. (One-click Shippo integration coming next.)</div>'+
            '<div class="f"><label>Tracking Number</label><input id="trk" placeholder="e.g. 9400111202533112341234"></div>'+
            '<div class="f"><label>Notes (optional)</label><textarea id="nt" placeholder="Any notes about this shipment..."></textarea></div>'+
            '<div class="btn-row"><button class="btn btn-s" id="ship">Mark as Shipped</button>'+
            '<button class="btn btn-d" id="cancel">Cancel Giveaway</button></div></div>';
    } else if(g.status==='shipped'){
        h+='<div class="section"><h3>📍 Shipped to</h3>'+addressDisplay(g)+'</div>';
        h+='<div class="section"><h3>✅ Shipment</h3>'+
            '<div class="addr-display"><b>Tracking:</b> <span class="tracking">'+esc(g.tracking_number||'-')+'</span><br>'+
            '<b>Shipped at:</b> '+fmt(g.shipped_at)+'</div>'+
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
}
function load(){
    fetch('/api/giveaway/'+GID).then(function(r){return r.json()}).then(function(d){
        if(!d.ok){document.getElementById('wrap').innerHTML='<div style="text-align:center;padding:60px;color:#fb7185">Giveaway not found</div>';return}
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
<title>Scan Your Badge</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:linear-gradient(135deg,#1e1b4b 0%,#0c0f16 50%,#1e1b4b 100%);color:#e4e8f1;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
.box{max-width:500px;width:100%;text-align:center}
.logo{font-size:120px;margin-bottom:20px;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.05)}}
h1{font-size:36px;font-weight:800;margin-bottom:12px}
.sub{color:#a5b4fc;font-size:18px;margin-bottom:40px;font-weight:500}
.scan-area{background:rgba(255,255,255,.04);border:2px dashed rgba(165,180,252,.3);border-radius:24px;padding:50px 30px;margin-bottom:24px;transition:all .3s}
.scan-area.focus{border-color:#a5b4fc;background:rgba(165,180,252,.08)}
.scan-area.success{border-color:#10b981;background:rgba(16,185,129,.08)}
.scan-area.error{border-color:#f43f5e;background:rgba(244,63,94,.08);animation:shake .4s}
@keyframes shake{0%,100%{transform:translateX(0)}25%{transform:translateX(-10px)}75%{transform:translateX(10px)}}
.scan-icon{font-size:64px;margin-bottom:16px}
.scan-text{font-size:20px;font-weight:600;margin-bottom:8px}
.scan-hint{color:#6b7a90;font-size:14px}
input{position:absolute;opacity:0;pointer-events:none}
.alt-link{color:#6b7a90;text-decoration:none;font-size:13px;display:inline-block;margin-top:20px;padding:8px 16px;border-radius:8px}
.alt-link:hover{color:#a5b4fc;background:rgba(255,255,255,.04)}
.toast{position:fixed;top:24px;left:50%;transform:translateX(-50%);background:#10b981;color:white;padding:14px 28px;border-radius:50px;font-weight:700;font-size:15px;box-shadow:0 10px 40px rgba(16,185,129,.4);z-index:100;display:none}
.toast.err{background:#f43f5e;box-shadow:0 10px 40px rgba(244,63,94,.4)}
</style></head><body>
<div class="box">
<div class="logo">🎫</div>
<h1>Welcome!</h1>
<div class="sub">Scan your employee badge to begin</div>
<div class="scan-area focus" id="sa">
<div class="scan-icon">📡</div>
<div class="scan-text" id="st">Ready to scan</div>
<div class="scan-hint">Hold your badge under the scanner</div>
</div>
<input type="text" id="tk" autofocus autocomplete="off" inputmode="none">
<a href="/" class="alt-link">Use password instead</a>
</div>
<div class="toast" id="toast"></div>
<script>
var inp=document.getElementById('tk'),sa=document.getElementById('sa'),st=document.getElementById('st');
var buf="",lastKey=0,timer=null;

function showToast(m,err){
    var t=document.getElementById('toast');t.textContent=m;t.className=err?'toast err':'toast';t.style.display='block';
    setTimeout(function(){t.style.display='none'},3000);
}

function tryLogin(token){
    sa.className='scan-area';st.textContent='Verifying...';
    fetch('/api/badge-login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:token})})
    .then(function(r){return r.json()}).then(function(d){
        if(d.ok){
            sa.className='scan-area success';st.textContent='Welcome, '+d.name+'!';
            showToast('Welcome '+d.name+' 👋');
            setTimeout(function(){location.href='/'},800);
        } else {
            sa.className='scan-area error';st.textContent='Badge not recognized';
            showToast(d.error||'Try again',true);
            setTimeout(function(){sa.className='scan-area focus';st.textContent='Ready to scan';buf=""},1500);
        }
    }).catch(function(){
        sa.className='scan-area error';st.textContent='Connection error';
        setTimeout(function(){sa.className='scan-area focus';st.textContent='Ready to scan';buf=""},1500);
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
        if(buf.length===1){sa.className='scan-area';st.textContent='Reading...'}
        // Auto-reset display if user stops typing (didn't hit Enter)
        clearTimeout(timer);
        timer=setTimeout(function(){
            if(buf.length>0&&Date.now()-lastKey>500){buf="";sa.className='scan-area focus';st.textContent='Ready to scan'}
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
body{font-family:'DM Sans',sans-serif;background:#0c0f16;color:#e4e8f1;min-height:100vh}
.page-hdr{padding:24px 28px 8px;max-width:1100px;margin:0 auto}
.page-title{font-size:22px;font-weight:800}
.page-title span{color:#a5b4fc;margin-left:8px;font-weight:600;font-size:14px}
.wrap{max-width:1100px;margin:0 auto;padding:0 28px 28px}
.intro{background:rgba(79,70,229,.08);border:1px solid rgba(79,70,229,.2);border-radius:14px;padding:18px 22px;margin-bottom:24px;color:#a5b4fc;font-size:14px;line-height:1.6}
.intro b{color:#e4e8f1}
.actions-bar{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px;flex-wrap:wrap;gap:12px}
h2{font-size:18px;font-weight:700}
.btn{border:none;border-radius:10px;padding:11px 22px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit;transition:all .15s;text-decoration:none;display:inline-flex;align-items:center;gap:6px}
.btn-p{background:linear-gradient(135deg,#4f46e5,#7c3aed);color:white;box-shadow:0 4px 16px rgba(79,70,229,.3)}
.btn-p:hover{transform:translateY(-1px)}
.btn-s{background:rgba(255,255,255,.08);color:#e4e8f1;border:1px solid rgba(255,255,255,.1)}
.btn-s:hover{background:rgba(255,255,255,.14)}
.btn-d{background:rgba(244,63,94,.1);color:#fb7185;border:1.5px solid rgba(244,63,94,.2)}
.btn-d:hover{background:rgba(244,63,94,.2)}
.btn-sm{padding:7px 13px;font-size:12px}
table{width:100%;background:rgba(21,25,33,.6);border:1px solid rgba(255,255,255,.06);border-radius:14px;border-collapse:separate;border-spacing:0;overflow:hidden}
th,td{padding:14px 18px;text-align:left;border-bottom:1px solid rgba(255,255,255,.04)}
th{background:rgba(11,14,20,.6);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:#6b7a90}
tr:last-child td{border-bottom:none}
.role-w{background:rgba(96,165,250,.15);color:#60a5fa;padding:3px 10px;border-radius:50px;font-size:11px;font-weight:700;text-transform:uppercase}
.role-c{background:rgba(167,139,250,.15);color:#a78bfa;padding:3px 10px;border-radius:50px;font-size:11px;font-weight:700;text-transform:uppercase}
.role-a{background:rgba(244,63,94,.15);color:#fb7185;padding:3px 10px;border-radius:50px;font-size:11px;font-weight:700;text-transform:uppercase}
.has-badge{color:#34d399;font-weight:600}
.no-badge{color:#6b7a90;font-style:italic}
.actions{display:flex;gap:6px;flex-wrap:wrap}
.toast{position:fixed;bottom:24px;right:24px;background:#10b981;color:white;padding:14px 22px;border-radius:10px;font-weight:600;box-shadow:0 10px 40px rgba(16,185,129,.4);z-index:100;display:none}
.toast.err{background:#f43f5e}
.station-select{margin-bottom:24px;background:rgba(21,25,33,.6);border:1px solid rgba(255,255,255,.06);border-radius:14px;padding:18px 22px}
.station-select h3{font-size:13px;font-weight:700;color:#a5b4fc;text-transform:uppercase;letter-spacing:.6px;margin-bottom:8px}
.station-select .row{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.station-select select{background:rgba(11,14,20,.8);border:2px solid rgba(255,255,255,.08);border-radius:10px;padding:9px 14px;font-size:14px;color:#e4e8f1;font-family:inherit;outline:none}
.station-select .current{font-size:14px;color:#34d399;font-weight:600}
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
<div style="font-size:12px;color:#6b7a90;margin-top:8px">When set, workers who scan their badge on this machine will automatically be assigned to this station.</div>
</div>

<div class="actions-bar">
<h2>Workers with Badges</h2>
<a href="/api/users/badge/sheet" class="btn btn-p" target="_blank">🖨️ Print All Badges (Avery 5160)</a>
</div>

<table>
<thead><tr><th>Username</th><th>Name</th><th>Role</th><th>Badge</th><th>Actions</th></tr></thead>
<tbody id="tb"><tr><td colspan="5" style="text-align:center;color:#6b7a90;padding:40px">Loading...</td></tr></tbody>
</table>
</div>

<div class="toast" id="t"></div>
<script>
function toast(m,e){var t=document.getElementById('t');t.textContent=m;t.className=e?'toast err':'toast';t.style.display='block';setTimeout(function(){t.style.display='none'},3000)}

function loadStation(){
    fetch('/api/machine-station').then(function(r){return r.json()}).then(function(d){
        var cur=document.getElementById('curSta');
        if(d.station)cur.innerHTML='✓ Currently set to: <b>'+d.station_name+' ('+d.station+')</b>';
        else cur.innerHTML='<span style="color:#fbbf24">⚠️ No station assigned to this machine</span>';
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
                    actions='<a class="btn btn-s btn-sm" href="/api/users/badge/pdf/'+u+'" target="_blank">🖨️ Print</a>'+
                        '<button class="btn btn-d btn-sm" data-act="regen" data-u="'+u+'">↻ Regenerate</button>'+
                        '<button class="btn btn-d btn-sm" data-act="revoke" data-u="'+u+'">✕ Revoke</button>';
                } else {
                    actions='<button class="btn btn-p btn-sm" data-act="regen" data-u="'+u+'">+ Issue Badge</button>';
                }
            } else {
                actions='<span style="color:#6b7a90;font-size:12px">Badges are for workers</span>';
            }
            return '<tr><td><b>'+u+'</b></td><td>'+info.name+'</td><td><span class="'+roleClass+'">'+info.role+'</span></td><td>'+badgeText+'</td><td><div class="actions">'+actions+'</div></td></tr>';
        });
        tb.innerHTML=rows.join('')||'<tr><td colspan="5" style="text-align:center;color:#6b7a90;padding:40px">No users yet</td></tr>';
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
body{font-family:'DM Sans',-apple-system,sans-serif;background:#0a0d14;color:#e4e8f1;min-height:100vh;padding-bottom:80px}
.wrap{max-width:1100px;margin:0 auto;padding:32px 24px}
.hero{display:flex;align-items:center;gap:24px;margin-bottom:32px;padding:28px;background:linear-gradient(135deg,rgba(79,70,229,.12),rgba(168,85,247,.06));border:1px solid rgba(79,70,229,.18);border-radius:18px}
.avatar{width:80px;height:80px;border-radius:50%;background:linear-gradient(135deg,#6366f1,#a855f7);display:flex;align-items:center;justify-content:center;font-size:36px;font-weight:800;color:#fff;flex-shrink:0}
.hero-info h1{font-size:28px;font-weight:800;margin-bottom:4px;color:#fff}
.hero-info .role{font-size:13px;color:#a5b4fc;font-weight:600;text-transform:uppercase;letter-spacing:.5px}
.hero-info .since{font-size:13px;color:#6b7a90;margin-top:6px}
.rank-pill{margin-left:auto;text-align:center;padding:14px 20px;background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.18);border-radius:12px;min-width:120px}
.rank-pill .num{font-size:32px;font-weight:900;color:#fbbf24;line-height:1}
.rank-pill .lbl{font-size:11px;color:#9ba9c1;text-transform:uppercase;letter-spacing:.5px;margin-top:4px}
.section-title{font-size:13px;font-weight:700;color:#6b7a90;text-transform:uppercase;letter-spacing:1px;margin:32px 0 12px}
.grid-4{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.stat-card{background:rgba(255,255,255,.02);border:1px solid rgba(255,255,255,.06);border-radius:14px;padding:18px}
.stat-card .lbl{font-size:11px;color:#6b7a90;text-transform:uppercase;letter-spacing:.5px;font-weight:600}
.stat-card .val{font-size:32px;font-weight:800;color:#e4e8f1;margin:8px 0 2px;line-height:1}
.stat-card .sub{font-size:12px;color:#9ba9c1}
.stat-card.highlight{background:linear-gradient(135deg,rgba(99,102,241,.12),rgba(99,102,241,.04));border-color:rgba(99,102,241,.25)}
.stat-card.highlight .val{color:#a5b4fc}
.achievements{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:14px}
.medal{background:rgba(255,255,255,.02);border:1px solid rgba(255,255,255,.06);border-radius:14px;padding:18px;text-align:center;position:relative;transition:transform .15s}
.medal.earned{background:linear-gradient(135deg,rgba(251,191,36,.1),rgba(245,158,11,.04));border-color:rgba(251,191,36,.25)}
.medal.earned:hover{transform:translateY(-2px)}
.medal .emoji{font-size:44px;line-height:1;filter:grayscale(1);opacity:.35}
.medal.earned .emoji{filter:none;opacity:1}
.medal .label{font-size:12px;color:#9ba9c1;margin-top:8px;font-weight:600}
.medal.earned .label{color:#fbbf24}
.medal.earned::after{content:'✓';position:absolute;top:8px;right:8px;background:#10b981;color:#fff;width:18px;height:18px;border-radius:50%;font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center}
.recent-table{width:100%;background:rgba(255,255,255,.02);border:1px solid rgba(255,255,255,.06);border-radius:14px;overflow:hidden;border-collapse:collapse}
.recent-table th{text-align:left;padding:12px 16px;font-size:11px;color:#6b7a90;text-transform:uppercase;letter-spacing:.5px;background:rgba(255,255,255,.02);border-bottom:1px solid rgba(255,255,255,.06)}
.recent-table td{padding:12px 16px;font-size:13px;color:#e4e8f1;border-bottom:1px solid rgba(255,255,255,.04)}
.recent-table tr:last-child td{border-bottom:none}
.recent-table td.muted{color:#9ba9c1}
.recent-table td.mono{font-family:'SF Mono',Menlo,monospace;font-size:12px}
.empty{text-align:center;padding:40px;color:#6b7a90;font-size:14px;background:rgba(255,255,255,.02);border:1px dashed rgba(255,255,255,.08);border-radius:14px}
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
body{font-family:'DM Sans',-apple-system,sans-serif;background:#0a0d14;color:#e4e8f1;min-height:100vh;padding-bottom:80px}
.wrap{max-width:1000px;margin:0 auto;padding:32px 24px}
.page-title{font-size:32px;font-weight:900;margin-bottom:6px}
.subtitle{color:#9ba9c1;margin-bottom:24px;font-size:14px}
.window-tabs{display:flex;gap:6px;background:rgba(255,255,255,.03);padding:5px;border-radius:11px;border:1px solid rgba(255,255,255,.06);margin-bottom:32px;max-width:fit-content}
.window-tab{padding:9px 18px;border-radius:8px;font-size:13px;font-weight:600;color:#9ba9c1;cursor:pointer;transition:all .15s;background:transparent;border:none;font-family:inherit}
.window-tab:hover{color:#e4e8f1}
.window-tab.active{background:rgba(99,102,241,.18);color:#a5b4fc}
.podium{display:grid;grid-template-columns:1fr 1.2fr 1fr;gap:14px;margin-bottom:24px;align-items:end}
.podium-slot{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);border-radius:14px;padding:20px;text-align:center;position:relative;transition:transform .2s}
.podium-slot.gold{background:linear-gradient(180deg,rgba(251,191,36,.16),rgba(251,191,36,.04));border-color:rgba(251,191,36,.3);min-height:240px}
.podium-slot.silver{background:linear-gradient(180deg,rgba(148,163,184,.14),rgba(148,163,184,.04));border-color:rgba(148,163,184,.25);min-height:210px}
.podium-slot.bronze{background:linear-gradient(180deg,rgba(217,119,6,.14),rgba(217,119,6,.04));border-color:rgba(217,119,6,.25);min-height:190px}
.podium-medal{font-size:44px;margin-bottom:8px}
.podium-name{font-size:18px;font-weight:800;color:#fff;margin-bottom:4px}
.podium-count{font-size:28px;font-weight:900;color:#fbbf24;margin-bottom:2px}
.silver .podium-count{color:#cbd5e1}
.bronze .podium-count{color:#f59e0b}
.podium-meta{font-size:12px;color:#9ba9c1}
.rest-list{background:rgba(255,255,255,.02);border:1px solid rgba(255,255,255,.06);border-radius:14px;overflow:hidden}
.rest-row{display:grid;grid-template-columns:60px 1fr 100px 100px 100px;gap:12px;align-items:center;padding:14px 20px;border-bottom:1px solid rgba(255,255,255,.04);font-size:14px}
.rest-row:last-child{border-bottom:none}
.rest-row.me{background:rgba(99,102,241,.08);border-left:3px solid #a5b4fc}
.rest-rank{font-weight:800;color:#6b7a90;font-size:16px}
.rest-name{font-weight:600;color:#e4e8f1}
.rest-stat{color:#9ba9c1;font-size:13px;text-align:right}
.rest-stat .big{color:#e4e8f1;font-weight:700;font-size:15px}
.empty{text-align:center;padding:60px 20px;color:#6b7a90}
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
var ME='__ME__';
var currentWindow='month';

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
        slots+='<div class="podium-name">'+p.name+'</div>';
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
      return '<div class="rest-row'+me+'"><div class="rest-rank">#'+p.rank+'</div><div class="rest-name">'+p.name+'</div><div class="rest-stat"><span class="big">'+p.count+'</span> packs</div><div class="rest-stat desktop-only">'+(p.avg_dur||0)+'s avg</div><div class="rest-stat desktop-only">'+p.days+' days</div></div>';
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
<title>Home — 5 SEC Employee Hub</title>
__NAVBAR_CSS__
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'DM Sans',-apple-system,sans-serif;background:#0a0d14;color:var(--text);min-height:100vh;padding-bottom:120px;-webkit-font-smoothing:antialiased}
/* Soft ambient gradient behind everything */
body::before{content:'';position:fixed;inset:0;background:radial-gradient(900px 500px at 12% -10%, rgba(243,201,196,.06), transparent 60%),radial-gradient(700px 500px at 92% -10%, rgba(168,85,247,.05), transparent 60%);pointer-events:none;z-index:-1}
.wrap{max-width:1240px;margin:0 auto;padding:48px 28px 0}

/* Hero greeting */
.hero{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;margin-bottom:36px;flex-wrap:wrap}
.greet-eyebrow{font-size:12px;font-weight:700;color:var(--brand);text-transform:uppercase;letter-spacing:2px;margin-bottom:6px}
.greet-title{font-size:44px;font-weight:900;color:#fff;line-height:1.05;letter-spacing:-1px}
.greet-title .name{background:linear-gradient(135deg,var(--brand),var(--brand-strong));-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
.greet-sub{font-size:15px;color:var(--text-muted);margin-top:8px;font-weight:500}
.quick-stats{display:flex;gap:12px;flex-wrap:wrap}
.qs{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:14px 18px;min-width:120px}
.qs .lbl{font-size:11px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.8px;font-weight:600}
.qs .val{font-size:26px;font-weight:800;color:#fff;line-height:1;margin-top:6px}
.qs.brand{background:linear-gradient(135deg,rgba(243,201,196,.12),rgba(243,201,196,.03));border-color:rgba(243,201,196,.22)}
.qs.brand .val{color:var(--brand)}

/* Packer of the Month banner */
.potm{display:none;align-items:center;gap:20px;padding:22px 26px;margin-bottom:40px;background:linear-gradient(135deg,rgba(251,191,36,.12),rgba(245,158,11,.04));border:1px solid rgba(251,191,36,.22);border-radius:18px;text-decoration:none;color:inherit;transition:transform .2s,border-color .2s}
.potm.show{display:flex}
.potm:hover{transform:translateY(-2px);border-color:rgba(251,191,36,.4)}
.potm-icon{font-size:52px;line-height:1;filter:drop-shadow(0 6px 12px rgba(251,191,36,.3))}
.potm-text{flex:1}
.potm-lbl{font-size:11px;color:#fbbf24;text-transform:uppercase;letter-spacing:1.5px;font-weight:700;margin-bottom:3px}
.potm-name{font-size:22px;font-weight:800;color:#fff;margin-bottom:3px}
.potm-stats{font-size:13px;color:var(--text-muted)}
.potm-stats b{color:var(--text);font-weight:700}
.potm-arrow{font-size:18px;color:#fbbf24;font-weight:700}

/* News strip on home — newest 2 announcements */
.news-strip{display:none;flex-direction:column;gap:10px;margin-bottom:32px}
.news-strip.show{display:flex}
.news-strip-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px}
.news-strip-title{font-size:13px;font-weight:800;color:var(--text-dim);text-transform:uppercase;letter-spacing:2px;display:flex;align-items:center;gap:10px}
.news-strip-title .dot{width:8px;height:8px;border-radius:50%;background:var(--brand)}
.news-strip-all{color:var(--brand);text-decoration:none;font-size:12px;font-weight:700;transition:color .15s}
.news-strip-all:hover{color:var(--brand-strong)}
.news-card{display:flex;gap:14px;padding:16px 20px;background:var(--surface);border:1px solid var(--border);border-radius:14px;text-decoration:none;color:inherit;transition:all .15s;align-items:flex-start}
.news-card:hover{border-color:rgba(243,201,196,.18);background:rgba(255,255,255,.045);transform:translateY(-1px)}
.news-card.pri-important{border-left:3px solid #fbbf24}
.news-card.pri-urgent{border-left:3px solid #fb7185}
.news-card.pinned{background:linear-gradient(135deg,rgba(243,201,196,.06),rgba(243,201,196,.01))}
.news-icon{font-size:24px;line-height:1.2;flex-shrink:0}
.news-body{flex:1;min-width:0}
.news-title{font-size:15px;font-weight:700;color:#fff;margin-bottom:3px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.news-meta{font-size:12px;color:var(--text-dim)}
.news-meta b{color:var(--text-muted);font-weight:600}
.tiny-pill{font-size:9px;padding:2px 7px;border-radius:5px;font-weight:700;letter-spacing:.5px;text-transform:uppercase}
.tiny-pill.pri-info{background:rgba(99,102,241,.14);color:#a5b4fc}
.tiny-pill.pri-important{background:rgba(251,191,36,.16);color:#fbbf24}
.tiny-pill.pri-urgent{background:rgba(244,63,94,.16);color:#fb7185}
.tiny-pill.pinned{background:rgba(243,201,196,.16);color:var(--brand)}

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
.card::before{content:'';position:absolute;inset:0;background:linear-gradient(135deg,transparent,rgba(243,201,196,.04));opacity:0;transition:opacity .2s;pointer-events:none}
.card:hover{transform:translateY(-3px);border-color:rgba(243,201,196,.22);background:rgba(255,255,255,.045)}
.card:hover::before{opacity:1}
.card-icon{font-size:32px;margin-bottom:14px;line-height:1}
.card-title{font-size:17px;font-weight:800;color:#fff;margin-bottom:6px}
.card-desc{font-size:13px;color:var(--text-muted);line-height:1.5;flex:1}
.card-meta{display:flex;justify-content:space-between;align-items:center;margin-top:14px;font-size:12px;color:var(--brand);font-weight:700}
.card-meta .arrow{transition:transform .2s}
.card:hover .card-meta .arrow{transform:translateX(4px)}
.card.disabled{opacity:.55;cursor:not-allowed;pointer-events:none}
.card.disabled .badge-soon{background:rgba(148,163,184,.12);color:var(--text-muted);padding:3px 9px;border-radius:6px;font-size:10px;font-weight:700;letter-spacing:.5px;text-transform:uppercase}
.card .pill-new{position:absolute;top:14px;right:14px;background:rgba(16,185,129,.16);color:#34d399;padding:3px 9px;border-radius:6px;font-size:10px;font-weight:700;letter-spacing:.5px;text-transform:uppercase}

/* Role-based hide */
body[data-role="worker"] .hub-section-ops{display:none}

/* Worker hero CTA - giant "Start Packing" for workers */
body[data-role="worker"] .worker-cta{display:flex}
.worker-cta{display:none;align-items:center;gap:18px;padding:24px 28px;margin-bottom:36px;background:linear-gradient(135deg,rgba(99,102,241,.16),rgba(168,85,247,.08));border:1px solid rgba(99,102,241,.3);border-radius:20px;text-decoration:none;color:inherit;transition:transform .2s}
.worker-cta:hover{transform:translateY(-2px)}
.worker-cta-icon{font-size:48px}
.worker-cta-text{flex:1}
.worker-cta-text .ttl{font-size:22px;font-weight:800;color:#fff;margin-bottom:4px}
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

  <!-- Packer of the Month -->
  <a href="/leaderboard" class="potm" id="potm">
    <div class="potm-icon">👑</div>
    <div class="potm-text">
      <div class="potm-lbl">Packer of the Month</div>
      <div class="potm-name" id="potmName">—</div>
      <div class="potm-stats"><b id="potmCount">0</b> packages · avg <b id="potmAvg">0s</b> · <b id="potmDays">0</b> active days</div>
    </div>
    <div class="potm-arrow">→</div>
  </a>

  <!-- Personal section (everyone) -->
  <section class="hub-section">
    <div class="section-head">
      <div class="section-title"><span class="dot"></span>Personal</div>
      <div class="section-sub">Your stats, ranking, and progress</div>
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
      <div class="card disabled">
        <div class="card-icon">🎯</div>
        <div class="card-title">My Goals</div>
        <div class="card-desc">Personal targets and progress tracking</div>
        <div class="card-meta"><span class="badge-soon">Coming soon</span></div>
      </div>
    </div>
  </section>

  <!-- Operations section (admin/cs only) -->
  <section class="hub-section hub-section-ops">
    <div class="section-head">
      <div class="section-title"><span class="dot"></span>Operations</div>
      <div class="section-sub">Tools for daily warehouse work</div>
    </div>
    <div class="card-grid">
      <a href="/dashboard" class="card">
        <div class="card-icon">🔍</div>
        <div class="card-title">Search Recordings</div>
        <div class="card-desc">Look up packing videos by tracking number</div>
        <div class="card-meta"><span>Open search</span><span class="arrow">→</span></div>
      </a>
      <a href="/giveaway" class="card">
        <div class="card-icon">🎁</div>
        <div class="card-title">Giveaways</div>
        <div class="card-desc">Manage winners and shipping addresses</div>
        <div class="card-meta"><span>Open queue</span><span class="arrow">→</span></div>
      </a>
      <a href="/analytics" class="card" id="cardAnalytics">
        <div class="card-icon">📊</div>
        <div class="card-title">Analytics</div>
        <div class="card-desc">Daily totals, per-station and per-worker breakdowns</div>
        <div class="card-meta"><span>View metrics</span><span class="arrow">→</span></div>
      </a>
    </div>
  </section>

  <!-- Documents section (placeholder for now) -->
  <section class="hub-section">
    <div class="section-head">
      <div class="section-title"><span class="dot"></span>Documents</div>
      <div class="section-sub">Forms, policies, and personal paperwork</div>
    </div>
    <div class="card-grid">
      <a href="/documents?cat=policies" class="card">
        <div class="card-icon">📋</div>
        <div class="card-title">Company Policies</div>
        <div class="card-desc">Handbook, code of conduct, safety procedures</div>
        <div class="card-meta"><span>Browse policies</span><span class="arrow">→</span></div>
      </a>
      <a href="/documents?cat=personal" class="card">
        <div class="card-icon">📄</div>
        <div class="card-title">My Documents</div>
        <div class="card-desc">Pay stubs, contracts, and personal records</div>
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

// Hide admin-only card for CS
var role=document.body.dataset.role;
if(role==='cs'){
  var ca=document.getElementById('cardAnalytics');
  if(ca)ca.style.display='none';
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

// Load Packer of the Month
fetch('/api/packer-of-month').then(function(r){return r.json()}).then(function(d){
  if(!d||!d.name)return;
  document.getElementById('potmName').textContent=d.name;
  document.getElementById('potmCount').textContent=d.count;
  document.getElementById('potmAvg').textContent=(d.avg_dur||0)+'s';
  document.getElementById('potmDays').textContent=d.days;
  document.getElementById('potm').classList.add('show');
});

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
<title>Documents — 5 SEC Employee Hub</title>
__NAVBAR_CSS__
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'DM Sans',-apple-system,sans-serif;background:#0a0d14;color:var(--text);min-height:100vh;padding-bottom:120px;-webkit-font-smoothing:antialiased}
.wrap{max-width:1100px;margin:0 auto;padding:40px 28px 0}
.page-head{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;margin-bottom:28px;flex-wrap:wrap}
.page-title{font-size:36px;font-weight:900;color:#fff;letter-spacing:-.5px;line-height:1.05}
.page-sub{color:var(--text-muted);margin-top:6px;font-size:14px}
.upload-btn{background:var(--brand);color:#1a0e0b;border:none;border-radius:12px;padding:12px 22px;font-size:14px;font-weight:800;cursor:pointer;font-family:inherit;transition:all .15s;display:inline-flex;align-items:center;gap:8px;box-shadow:0 6px 22px rgba(243,201,196,.15)}
.upload-btn:hover{background:var(--brand-strong);transform:translateY(-1px)}
body[data-role="admin"] .admin-only{display:inline-flex}
.admin-only{display:none}

/* Category tabs */
.tabs{display:flex;gap:4px;background:rgba(255,255,255,.03);padding:5px;border-radius:12px;border:1px solid var(--border);margin-bottom:28px;max-width:fit-content;flex-wrap:wrap}
.tab{padding:9px 18px;border-radius:8px;font-size:13px;font-weight:600;color:var(--text-muted);cursor:pointer;transition:all .15s;background:transparent;border:none;font-family:inherit;display:flex;align-items:center;gap:6px}
.tab:hover{color:var(--text)}
.tab.active{background:var(--brand-glow);color:var(--brand)}
.tab .count{font-size:11px;background:rgba(255,255,255,.06);padding:2px 7px;border-radius:6px;font-weight:700}
.tab.active .count{background:rgba(243,201,196,.2)}

/* Doc list */
.doc-list{display:flex;flex-direction:column;gap:10px}
.doc{display:grid;grid-template-columns:48px 1fr auto;gap:16px;align-items:center;padding:18px 22px;background:var(--surface);border:1px solid var(--border);border-radius:14px;transition:all .15s}
.doc:hover{border-color:rgba(243,201,196,.18);background:rgba(255,255,255,.045)}
.doc-icon{width:48px;height:48px;border-radius:12px;background:rgba(243,201,196,.1);display:flex;align-items:center;justify-content:center;font-size:24px;flex-shrink:0}
.doc-info{min-width:0}
.doc-title{font-size:15px;font-weight:700;color:#fff;margin-bottom:3px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.doc-desc{font-size:13px;color:var(--text-muted);line-height:1.4;margin-bottom:6px;overflow:hidden;text-overflow:ellipsis;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.doc-meta{font-size:11px;color:var(--text-dim);display:flex;gap:14px;flex-wrap:wrap;align-items:center}
.doc-meta b{color:var(--text-muted);font-weight:600}
.vis-pill{font-size:10px;padding:2px 8px;border-radius:6px;font-weight:700;letter-spacing:.4px;text-transform:uppercase}
.vis-all{background:rgba(16,185,129,.12);color:#34d399}
.vis-admin_cs{background:rgba(99,102,241,.14);color:#a5b4fc}
.vis-admin{background:rgba(244,63,94,.12);color:#fb7185}
.vis-personal{background:rgba(245,158,11,.14);color:#fbbf24}
.doc-actions{display:flex;gap:8px;align-items:center}
.dl{background:var(--brand-glow);color:var(--brand);text-decoration:none;font-size:13px;font-weight:700;padding:9px 16px;border-radius:9px;transition:all .15s;border:1px solid rgba(243,201,196,.18);display:inline-flex;align-items:center;gap:6px}
.dl:hover{background:rgba(243,201,196,.2)}
.del{background:rgba(244,63,94,.08);color:#fb7185;border:1px solid rgba(244,63,94,.18);border-radius:9px;padding:9px 12px;font-size:13px;font-weight:700;cursor:pointer;transition:all .15s;font-family:inherit;display:none}
body[data-role="admin"] .del{display:inline-flex}
.del:hover{background:rgba(244,63,94,.16)}
.empty{text-align:center;padding:80px 20px;color:var(--text-dim)}
.empty-icon{font-size:56px;margin-bottom:14px;opacity:.5}
.empty-title{font-size:18px;font-weight:700;color:var(--text-muted);margin-bottom:6px}
.empty-sub{font-size:14px}

/* Modal */
.modal-bg{position:fixed;inset:0;background:rgba(0,0,0,.65);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);z-index:200;display:none;align-items:center;justify-content:center;padding:20px}
.modal-bg.show{display:flex}
.modal{background:#12161f;border:1px solid var(--border);border-radius:20px;padding:32px;max-width:520px;width:100%;max-height:90vh;overflow-y:auto}
.modal h3{font-size:22px;font-weight:800;margin-bottom:6px;color:#fff}
.modal .modal-sub{color:var(--text-muted);font-size:13px;margin-bottom:24px}
.fld{margin-bottom:16px}
.fld label{display:block;font-size:11px;font-weight:700;color:var(--text-muted);margin-bottom:7px;text-transform:uppercase;letter-spacing:.6px}
.fld input[type="text"],.fld textarea,.fld select{width:100%;background:rgba(11,14,20,.7);border:1px solid var(--border);border-radius:10px;padding:11px 14px;font-size:14px;color:var(--text);font-family:inherit;outline:none;transition:all .2s}
.fld input[type="text"]:focus,.fld textarea:focus,.fld select:focus{border-color:var(--brand);box-shadow:0 0 0 3px rgba(243,201,196,.1)}
.fld textarea{resize:vertical;min-height:80px}
.fld input[type="file"]{width:100%;color:var(--text-muted);font-size:13px;padding:9px;background:rgba(11,14,20,.7);border:1px dashed var(--border);border-radius:10px;cursor:pointer;font-family:inherit}
.fld input[type="file"]::file-selector-button{background:var(--brand);color:#1a0e0b;border:none;border-radius:8px;padding:6px 14px;margin-right:10px;font-size:12px;font-weight:700;cursor:pointer;font-family:inherit}
.fld-row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.modal-actions{display:flex;justify-content:flex-end;gap:10px;margin-top:24px}
.btn-cancel{background:transparent;color:var(--text-muted);border:1px solid var(--border);border-radius:10px;padding:10px 18px;font-size:14px;font-weight:600;cursor:pointer;font-family:inherit}
.btn-cancel:hover{color:var(--text);background:rgba(255,255,255,.04)}
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
<title>Welcome — 5 SEC</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'DM Sans',-apple-system,sans-serif;background:#0a0d14;color:#e4e8f1;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:32px 24px;-webkit-font-smoothing:antialiased;position:relative;overflow:hidden}
body::before{content:'';position:fixed;inset:0;background:radial-gradient(900px 600px at 20% 0%, rgba(243,201,196,.08), transparent 60%),radial-gradient(800px 600px at 80% 100%, rgba(99,102,241,.06), transparent 60%);pointer-events:none;z-index:-1}
.brand{text-align:center;margin-bottom:40px}
.brand-mark{font-size:28px;font-weight:900;color:#f3c9c4;letter-spacing:2.2px;line-height:1;text-shadow:0 4px 18px rgba(243,201,196,.2)}
.brand-sub{font-size:9px;font-weight:700;color:#6b7a90;letter-spacing:2.8px;text-transform:uppercase;margin-top:5px}
.greet{text-align:center;margin-bottom:8px}
.greet-eyebrow{font-size:12px;font-weight:700;color:#f3c9c4;text-transform:uppercase;letter-spacing:2.2px;margin-bottom:8px}
.greet-name{font-size:38px;font-weight:900;color:#fff;line-height:1.1;letter-spacing:-.8px}
.greet-name b{background:linear-gradient(135deg,#f3c9c4,#eab1a8);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
.greet-prompt{font-size:15px;color:#9ba9c1;margin-top:14px;margin-bottom:44px}
.choices{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:18px;max-width:720px;width:100%}
.choice{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);border-radius:22px;padding:36px 28px;text-decoration:none;color:inherit;display:flex;flex-direction:column;align-items:flex-start;gap:14px;transition:all .25s cubic-bezier(.4,0,.2,1);position:relative;overflow:hidden;min-height:260px;cursor:pointer}
.choice::after{content:'';position:absolute;inset:0;background:linear-gradient(135deg,transparent 60%, rgba(243,201,196,.08));opacity:0;transition:opacity .25s;pointer-events:none}
.choice:hover{transform:translateY(-4px);border-color:rgba(243,201,196,.3);background:rgba(255,255,255,.05)}
.choice:hover::after{opacity:1}
.choice.pack{background:linear-gradient(135deg,rgba(99,102,241,.14),rgba(168,85,247,.06));border-color:rgba(99,102,241,.3)}
.choice.pack:hover{border-color:rgba(99,102,241,.5)}
.choice-icon{font-size:64px;line-height:1;margin-bottom:6px}
.choice-label{font-size:11px;font-weight:700;color:#9ba9c1;text-transform:uppercase;letter-spacing:1.5px}
.choice-title{font-size:26px;font-weight:900;color:#fff;letter-spacing:-.4px;line-height:1.1}
.choice-desc{font-size:14px;color:#9ba9c1;line-height:1.5;flex:1}
.choice-cta{display:flex;align-items:center;gap:8px;color:#f3c9c4;font-size:13px;font-weight:800;letter-spacing:.5px;text-transform:uppercase;margin-top:6px}
.choice.pack .choice-cta{color:#a5b4fc}
.choice-cta .arrow{transition:transform .2s}
.choice:hover .choice-cta .arrow{transform:translateX(6px)}
.footer-link{margin-top:32px;font-size:12px;color:#6b7a90;text-align:center}
.footer-link a{color:#9ba9c1;text-decoration:none;border-bottom:1px dotted rgba(155,169,193,.3);transition:color .15s}
.footer-link a:hover{color:#e4e8f1}
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
<title>Onboarding — 5 SEC</title>
__NAVBAR_CSS__
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'DM Sans',-apple-system,sans-serif;background:#0a0d14;color:var(--text);min-height:100vh;padding-bottom:120px;-webkit-font-smoothing:antialiased}
.wrap{max-width:1000px;margin:0 auto;padding:40px 28px 0}

/* Hero / progress */
.hero{background:linear-gradient(135deg,rgba(243,201,196,.1),rgba(243,201,196,.02));border:1px solid rgba(243,201,196,.18);border-radius:20px;padding:28px;margin-bottom:32px}
.hero-eyebrow{font-size:11px;font-weight:700;color:var(--brand);text-transform:uppercase;letter-spacing:2px;margin-bottom:6px}
.hero-title{font-size:32px;font-weight:900;color:#fff;letter-spacing:-.5px;margin-bottom:6px}
.hero-sub{font-size:14px;color:var(--text-muted);margin-bottom:18px}
.progress-row{display:flex;align-items:center;gap:18px;flex-wrap:wrap}
.progress-bar{flex:1;height:12px;background:rgba(255,255,255,.06);border-radius:8px;overflow:hidden;min-width:200px}
.progress-fill{height:100%;background:linear-gradient(90deg,var(--brand),var(--brand-strong));border-radius:8px;transition:width .4s cubic-bezier(.4,0,.2,1)}
.progress-text{font-size:14px;color:var(--text);font-weight:700;white-space:nowrap}
.progress-text b{color:var(--brand);font-size:18px;font-weight:900}
.complete-badge{display:inline-flex;align-items:center;gap:6px;background:rgba(16,185,129,.14);color:#34d399;padding:5px 12px;border-radius:20px;font-size:12px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;margin-top:10px}
.complete-badge.show{display:inline-flex}

/* Sections */
.section-title{font-size:13px;font-weight:800;color:var(--text-dim);text-transform:uppercase;letter-spacing:2px;display:flex;align-items:center;gap:10px;margin:36px 0 14px}
.section-title .dot{width:8px;height:8px;border-radius:50%;background:var(--brand)}

/* Task list */
.task-list{display:flex;flex-direction:column;gap:10px}
.task{display:flex;align-items:flex-start;gap:14px;padding:18px 22px;background:var(--surface);border:1px solid var(--border);border-radius:14px;transition:all .15s;cursor:pointer}
.task:hover{border-color:rgba(243,201,196,.18);background:rgba(255,255,255,.045)}
.task.done{opacity:.6}
.task.done .task-title{text-decoration:line-through;color:var(--text-muted)}
.task-check{width:24px;height:24px;border-radius:50%;border:2px solid rgba(255,255,255,.18);flex-shrink:0;margin-top:1px;display:flex;align-items:center;justify-content:center;transition:all .2s}
.task.done .task-check{background:var(--brand);border-color:var(--brand);color:#1a0e0b;font-weight:900;font-size:14px}
.task-check::before{content:'';display:none}
.task.done .task-check::before{content:'✓';display:block}
.task-body{flex:1;min-width:0}
.task-title{font-size:15px;font-weight:700;color:#fff;margin-bottom:3px;display:flex;flex-wrap:wrap;align-items:center;gap:8px}
.task-desc{font-size:13px;color:var(--text-muted);line-height:1.5}
.task-meta{display:flex;gap:10px;align-items:center;margin-top:8px;font-size:11px;color:var(--text-dim);flex-wrap:wrap}
.cat-pill{font-size:10px;padding:2px 8px;border-radius:6px;font-weight:700;letter-spacing:.4px;text-transform:uppercase}
.cat-safety{background:rgba(244,63,94,.12);color:#fb7185}
.cat-paperwork{background:rgba(99,102,241,.14);color:#a5b4fc}
.cat-training{background:rgba(245,158,11,.14);color:#fbbf24}
.cat-intro{background:rgba(16,185,129,.12);color:#34d399}
.cat-other{background:rgba(148,163,184,.12);color:#94a3b8}
.req-pill{font-size:10px;padding:2px 7px;border-radius:5px;background:rgba(244,63,94,.12);color:#fb7185;font-weight:700;letter-spacing:.4px;text-transform:uppercase}
.del-task-btn{background:rgba(244,63,94,.08);color:#fb7185;border:1px solid rgba(244,63,94,.18);border-radius:8px;width:30px;height:30px;font-size:13px;cursor:pointer;display:none;align-items:center;justify-content:center;font-family:inherit;flex-shrink:0}
body[data-role="admin"] .del-task-btn{display:inline-flex}
.del-task-btn:hover{background:rgba(244,63,94,.18)}

/* Admin sections */
.admin-only{display:none}
body[data-role="admin"] .admin-only{display:block}
.add-row{background:var(--surface);border:1px dashed var(--border);border-radius:14px;padding:18px 22px;display:flex;gap:10px;align-items:flex-start;flex-wrap:wrap;margin-bottom:14px}
.add-row input[type="text"],.add-row select{background:rgba(11,14,20,.7);border:1px solid var(--border);border-radius:9px;padding:9px 13px;font-size:13px;color:var(--text);font-family:inherit;outline:none;transition:border .15s}
.add-row input[type="text"]:focus,.add-row select:focus{border-color:var(--brand)}
.add-row input[name="title"]{flex:1;min-width:200px}
.add-row label.req-check{display:flex;align-items:center;gap:6px;color:var(--text-muted);font-size:13px;cursor:pointer;user-select:none}
.add-btn{background:var(--brand);color:#1a0e0b;border:none;border-radius:9px;padding:9px 18px;font-size:13px;font-weight:800;cursor:pointer;font-family:inherit}
.add-btn:hover{background:var(--brand-strong)}

.team-list{background:var(--surface);border:1px solid var(--border);border-radius:14px;overflow:hidden}
.team-row{display:grid;grid-template-columns:1fr auto 200px auto;gap:14px;align-items:center;padding:14px 20px;border-bottom:1px solid rgba(255,255,255,.04);font-size:14px}
.team-row:last-child{border-bottom:none}
.team-row.complete{background:rgba(16,185,129,.04)}
.team-name{display:flex;flex-direction:column;gap:2px}
.team-name b{color:#fff;font-weight:700;font-size:14px}
.team-name .role{font-size:11px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.6px;font-weight:700}
.team-count{font-size:13px;color:var(--text-muted);font-weight:600;white-space:nowrap}
.team-bar{height:8px;background:rgba(255,255,255,.06);border-radius:6px;overflow:hidden}
.team-bar-fill{height:100%;background:linear-gradient(90deg,var(--brand),var(--brand-strong));border-radius:6px;transition:width .3s}
.team-row.complete .team-bar-fill{background:#34d399}
.reset-btn{background:transparent;color:var(--text-dim);border:1px solid var(--border);border-radius:8px;padding:6px 10px;font-size:11px;cursor:pointer;font-family:inherit;transition:all .15s}
.reset-btn:hover{color:#fb7185;border-color:rgba(244,63,94,.3)}

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
    <div class="hero-sub">Complete these steps to get fully set up at 5 Second Beauty.</div>
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
<title>News — 5 SEC</title>
__NAVBAR_CSS__
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'DM Sans',-apple-system,sans-serif;background:#0a0d14;color:var(--text);min-height:100vh;padding-bottom:120px;-webkit-font-smoothing:antialiased}
.wrap{max-width:920px;margin:0 auto;padding:40px 28px 0}
.page-head{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;margin-bottom:28px;flex-wrap:wrap}
.page-title{font-size:34px;font-weight:900;color:#fff;letter-spacing:-.5px;line-height:1.05}
.page-sub{color:var(--text-muted);margin-top:6px;font-size:14px}
.compose-btn{background:var(--brand);color:#1a0e0b;border:none;border-radius:12px;padding:12px 22px;font-size:14px;font-weight:800;cursor:pointer;font-family:inherit;transition:all .15s;display:inline-flex;align-items:center;gap:8px;box-shadow:0 6px 22px rgba(243,201,196,.15)}
.compose-btn:hover{background:var(--brand-strong);transform:translateY(-1px)}
.admin-only{display:none}
body[data-role="admin"] .admin-only{display:inline-flex}

/* Composer (inline, expands when "New" clicked) */
.composer{background:var(--surface);border:1px solid var(--border);border-radius:18px;padding:24px;margin-bottom:24px;display:none}
.composer.show{display:block}
.composer h3{font-size:18px;font-weight:800;color:#fff;margin-bottom:14px}
.fld{margin-bottom:14px}
.fld label{display:block;font-size:11px;font-weight:700;color:var(--text-muted);margin-bottom:7px;text-transform:uppercase;letter-spacing:.6px}
.fld input[type="text"],.fld textarea,.fld select{width:100%;background:rgba(11,14,20,.7);border:1px solid var(--border);border-radius:10px;padding:11px 14px;font-size:14px;color:var(--text);font-family:inherit;outline:none;transition:all .2s}
.fld input[type="text"]:focus,.fld textarea:focus,.fld select:focus{border-color:var(--brand);box-shadow:0 0 0 3px rgba(243,201,196,.1)}
.fld textarea{resize:vertical;min-height:110px;line-height:1.5}
.fld-row{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}
@media(max-width:600px){.fld-row{grid-template-columns:1fr 1fr}}
.fld .pin-check{display:flex;align-items:center;gap:6px;font-size:13px;color:var(--text-muted);cursor:pointer;user-select:none}
.composer-actions{display:flex;justify-content:flex-end;gap:10px;margin-top:6px}
.btn-cancel{background:transparent;color:var(--text-muted);border:1px solid var(--border);border-radius:10px;padding:9px 18px;font-size:14px;font-weight:600;cursor:pointer;font-family:inherit}
.btn-cancel:hover{color:var(--text);background:rgba(255,255,255,.04)}
.btn-publish{background:var(--brand);color:#1a0e0b;border:none;border-radius:10px;padding:9px 22px;font-size:14px;font-weight:800;cursor:pointer;font-family:inherit;transition:all .15s}
.btn-publish:hover{background:var(--brand-strong)}
.composer-err{color:#f43f5e;font-size:13px;margin-top:10px;min-height:18px}

/* Announcement cards */
.ann-list{display:flex;flex-direction:column;gap:14px}
.ann{position:relative;background:var(--surface);border:1px solid var(--border);border-radius:18px;padding:22px 26px;transition:all .15s}
.ann:hover{border-color:rgba(255,255,255,.12)}
.ann.pri-important{background:linear-gradient(135deg,rgba(251,191,36,.08),rgba(245,158,11,.02));border-color:rgba(251,191,36,.22)}
.ann.pri-urgent{background:linear-gradient(135deg,rgba(244,63,94,.1),rgba(244,63,94,.02));border-color:rgba(244,63,94,.28)}
.ann.pinned{box-shadow:inset 4px 0 0 var(--brand)}
.ann-head{display:flex;align-items:flex-start;gap:14px;margin-bottom:10px;flex-wrap:wrap}
.ann-title{flex:1;font-size:18px;font-weight:800;color:#fff;line-height:1.3;min-width:0}
.ann-pills{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.pri-pill{font-size:10px;padding:3px 10px;border-radius:6px;font-weight:800;letter-spacing:.5px;text-transform:uppercase}
.pri-info{background:rgba(99,102,241,.14);color:#a5b4fc}
.pri-important{background:rgba(251,191,36,.16);color:#fbbf24}
.pri-urgent{background:rgba(244,63,94,.16);color:#fb7185}
.aud-pill{font-size:10px;padding:3px 9px;border-radius:6px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;background:rgba(148,163,184,.12);color:#94a3b8}
.pinned-pill{font-size:10px;padding:3px 9px;border-radius:6px;font-weight:800;letter-spacing:.5px;text-transform:uppercase;background:rgba(243,201,196,.16);color:var(--brand);display:inline-flex;align-items:center;gap:4px}
.ann-body{font-size:14px;color:var(--text);line-height:1.65;white-space:pre-wrap;margin-bottom:14px}
.ann-foot{display:flex;justify-content:space-between;align-items:center;gap:14px;font-size:12px;color:var(--text-dim);flex-wrap:wrap}
.ann-meta b{color:var(--text-muted);font-weight:600}
.ann-actions{display:none;gap:6px}
body[data-role="admin"] .ann-actions{display:flex}
.icon-btn{background:rgba(255,255,255,.04);color:var(--text-muted);border:1px solid var(--border);border-radius:8px;padding:6px 10px;font-size:11px;font-weight:600;cursor:pointer;font-family:inherit;transition:all .15s}
.icon-btn:hover{color:var(--text);background:rgba(255,255,255,.08)}
.icon-btn.danger:hover{color:#fb7185;border-color:rgba(244,63,94,.3);background:rgba(244,63,94,.08)}
.icon-btn.pin.active{color:var(--brand);background:var(--brand-glow);border-color:rgba(243,201,196,.25)}

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
