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
    items=[]
    # All authenticated non-worker users see these
    if role in ("admin","cs"):
        items.append(("dash","/dashboard","🔍 Search"))
        items.append(("giveaway","/giveaway","🎁 Giveaways"))
    if role=="admin":
        items.append(("analytics","/analytics","📊 Analytics"))
        items.append(("users","/users","👥 Users"))
        items.append(("badges","/users/badges","🎫 Badges"))
    # Build HTML
    nav_html='<nav class="topnav"><div class="topnav-inner">'
    nav_html+='<div class="topnav-brand">📦 Packing Station</div>'
    nav_html+='<div class="topnav-links">'
    for key,url,label in items:
        cls="topnav-link active" if key==active_page else "topnav-link"
        nav_html+='<a href="'+url+'" class="'+cls+'">'+label+'</a>'
    nav_html+='</div>'
    nav_html+='<div class="topnav-user"><span class="topnav-name">'+name+'</span>'
    nav_html+='<a href="/logout" class="topnav-logout">Logout</a></div>'
    nav_html+='</div></nav>'
    return nav_html

# CSS for the unified top navbar - injected into every page that uses it
_NAVBAR_CSS='''<style>
.topnav{background:rgba(15,18,25,.95);border-bottom:1px solid rgba(255,255,255,.08);backdrop-filter:blur(20px);position:sticky;top:0;z-index:100;font-family:'DM Sans',sans-serif}
.topnav-inner{max-width:1600px;margin:0 auto;padding:0 24px;display:flex;align-items:center;gap:24px;height:56px}
.topnav-brand{font-size:15px;font-weight:800;color:#e4e8f1;letter-spacing:.3px;flex-shrink:0}
.topnav-links{display:flex;gap:4px;flex:1;align-items:center}
.topnav-link{color:#9ba9c1;text-decoration:none;font-size:13px;font-weight:600;padding:8px 14px;border-radius:8px;transition:all .15s;white-space:nowrap}
.topnav-link:hover{color:#e4e8f1;background:rgba(255,255,255,.05)}
.topnav-link.active{color:#a5b4fc;background:rgba(79,70,229,.15);border:1px solid rgba(79,70,229,.25)}
.topnav-user{display:flex;align-items:center;gap:12px;flex-shrink:0}
.topnav-name{font-size:13px;color:#6b7a90;font-weight:500}
.topnav-logout{color:#fb7185;text-decoration:none;font-size:12px;font-weight:600;padding:7px 14px;border-radius:7px;background:rgba(244,63,94,.08);border:1px solid rgba(244,63,94,.15);transition:all .15s}
.topnav-logout:hover{background:rgba(244,63,94,.15)}
@media(max-width:768px){
.topnav-inner{padding:0 12px;gap:8px;height:auto;flex-wrap:wrap;padding-top:8px;padding-bottom:8px}
.topnav-brand{font-size:13px;width:100%}
.topnav-links{order:2;width:100%;overflow-x:auto;flex:initial}
.topnav-user{order:1}
.topnav-name{display:none}
}
</style>'''


_FONT = '<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">'

LOGIN_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Packing Station</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#0c0f16;color:#e4e8f1;display:flex;align-items:center;justify-content:center;min-height:100vh;overflow:hidden}
.glow{position:fixed;border-radius:50%;filter:blur(100px);opacity:.12;pointer-events:none}
.g1{width:600px;height:600px;top:-200px;right:-150px;background:#4f46e5}
.g2{width:400px;height:400px;bottom:-100px;left:-100px;background:#7c3aed}
.wrap{position:relative;z-index:1;width:100%;max-width:440px;padding:24px}
.logo{text-align:center;margin-bottom:36px}
.logo-box{width:80px;height:80px;background:linear-gradient(135deg,#4f46e5,#7c3aed);border-radius:22px;display:inline-flex;align-items:center;justify-content:center;font-size:40px;box-shadow:0 12px 40px rgba(79,70,229,.3);margin-bottom:18px}
.logo h1{font-size:30px;font-weight:800;letter-spacing:-.5px}
.logo p{font-size:14px;color:#6b7a90;margin-top:4px}
.card{background:rgba(21,25,33,.8);backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,.06);border-radius:20px;padding:40px 36px}
.card h2{font-size:22px;font-weight:700;margin-bottom:4px}
.card .sub{font-size:13px;color:#6b7a90;margin-bottom:28px}
.field{margin-bottom:20px}
.field label{display:block;font-size:11px;font-weight:700;color:#6b7a90;margin-bottom:7px;text-transform:uppercase;letter-spacing:.6px}
.field input{width:100%;background:rgba(11,14,20,.8);border:2px solid rgba(255,255,255,.08);border-radius:12px;padding:15px 18px;font-size:16px;color:#e4e8f1;font-family:inherit;outline:none;transition:all .2s}
.field input:focus{border-color:#4f46e5;box-shadow:0 0 0 3px rgba(79,70,229,.15)}
.field input::placeholder{color:#3a4252}
.btn{width:100%;border:none;border-radius:12px;padding:16px;font-size:16px;font-weight:700;cursor:pointer;font-family:inherit;transition:all .15s}
.btn-primary{background:linear-gradient(135deg,#4f46e5,#7c3aed);color:white;margin-top:8px;box-shadow:0 4px 20px rgba(79,70,229,.3)}
.btn-primary:hover{transform:translateY(-1px);box-shadow:0 6px 28px rgba(79,70,229,.4)}
.btn-primary:active{transform:scale(.98)}
.err{color:#f43f5e;font-size:13px;margin-top:14px;text-align:center;min-height:18px}
.foot{text-align:center;margin-top:28px;font-size:11px;color:#2a3040}
</style></head><body>
<div class="glow g1"></div><div class="glow g2"></div>
<div class="wrap">
<div class="logo"><div class="logo-box">📦</div><h1>Packing Station</h1><p>5 Second Beauty — Warehouse System</p></div>
<div class="card">
<h2>Welcome back</h2><p class="sub">Sign in to start your shift</p>
<div class="field"><label>Username</label><input type="text" id="u" placeholder="Enter your username" autofocus></div>
<div class="field"><label>Password</label><input type="password" id="p" placeholder="Enter your password"></div>
<button class="btn btn-primary" id="loginBtn">Sign In</button>
<div class="err" id="e"></div>
</div>
<div class="foot">5 Second Beauty &copy; 2025</div>
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
    if(d.ok)window.location.href='/';
    else document.getElementById('e').textContent=d.error;
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
</style></head><body>
__NAVBAR__
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
loadRecent();loadStats();
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
