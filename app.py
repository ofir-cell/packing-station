#!/usr/bin/env python3
"""
5 Second Beauty - Packing Station
===================================
Production web app for packing video recording.

Roles:
  worker:  select station > scan > record > save
  cs:      search recordings by tracking number
  admin:   search + manage users + stations

Run:    python3 app.py
Deploy: gunicorn -w 4 -b 0.0.0.0:8080 app:app
"""
import os,csv,json,hashlib,secrets,time
from datetime import datetime
from functools import wraps
from flask import Flask,request,jsonify,send_file,redirect,session,make_response

DATA_DIR=os.environ.get("DATA_DIR",os.path.join(os.path.expanduser("~"),"PackingStationData"))
VIDEO_DIR=os.path.join(DATA_DIR,"videos")
PHOTO_DIR=os.path.join(DATA_DIR,"photos")
LOG_FILE=os.path.join(DATA_DIR,"packing_log.csv")
USERS_FILE=os.path.join(DATA_DIR,"users.json")
STATIONS_FILE=os.path.join(DATA_DIR,"stations.json")
SECRET_KEY=os.environ.get("SECRET_KEY",secrets.token_hex(32))
PORT=int(os.environ.get("PORT",8080))

for d in [DATA_DIR,VIDEO_DIR,PHOTO_DIR]:
    os.makedirs(d,exist_ok=True)

if not os.path.exists(LOG_FILE):
    with open(LOG_FILE,"w") as f:
        f.write("tracking_number,station,date,time,duration_seconds,video_file,photo_file,worker\n")

def _h(pw): return hashlib.sha256(pw.encode()).hexdigest()

def _init(path,default):
    if not os.path.exists(path):
        with open(path,"w") as f: json.dump(default,f,indent=2)

_init(USERS_FILE,{
    "admin":{"password":_h("admin123"),"role":"admin","name":"Admin"},
    "cs1":{"password":_h("cs123"),"role":"cs","name":"Customer Service"},
    "worker1":{"password":_h("pack1"),"role":"worker","name":"Worker 1"},
    "worker2":{"password":_h("pack2"),"role":"worker","name":"Worker 2"},
    "worker3":{"password":_h("pack3"),"role":"worker","name":"Worker 3"},
    "worker4":{"password":_h("pack4"),"role":"worker","name":"Worker 4"},
    "worker5":{"password":_h("pack5"),"role":"worker","name":"Worker 5"},
    "worker6":{"password":_h("pack6"),"role":"worker","name":"Worker 6"},
})
_init(STATIONS_FILE,{"S1":"Station 1","S2":"Station 2","S3":"Station 3","S4":"Station 4","S5":"Station 5","S6":"Station 6"})

def ldj(p):
    with open(p) as f: return json.load(f)
def svj(p,d):
    with open(p,"w") as f: json.dump(d,f,indent=2)

app=Flask(__name__)
app.secret_key=SECRET_KEY
app.config["MAX_CONTENT_LENGTH"]=250*1024*1024

def req_login(f):
    @wraps(f)
    def d(*a,**k):
        if "user" not in session: return redirect("/")
        return f(*a,**k)
    return d

def req_role(*roles):
    def w(f):
        @wraps(f)
        def d(*a,**k):
            if "user" not in session: return redirect("/")
            if session.get("role") not in roles: return "Access denied",403
            return f(*a,**k)
        return d
    return w

# ── PAGES ─────────────────────────────────────────────────
@app.route("/")
def index():
    if "user" not in session: return LOGIN_HTML
    if session.get("role")=="worker":
        if "station" not in session:
            return STATION_HTML.replace("{{NAME}}",session["name"])
        return (WORKER_HTML
            .replace("{{NAME}}",session["name"])
            .replace("{{STATION}}",session.get("station_name",""))
            .replace("{{SID}}",session.get("station","S0")))
    return redirect("/dashboard")

@app.route("/dashboard")
@req_role("admin","cs")
def dashboard():
    disp="inline-block" if session.get("role")=="admin" else "none"
    return (DASH_HTML
        .replace("{{NAME}}",session.get("name",""))
        .replace("{{ADMIN_VIS}}",disp))

@app.route("/users")
@req_role("admin")
def users_page(): return USERS_HTML

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ── AUTH API ──────────────────────────────────────────────
@app.route("/api/login",methods=["POST"])
def api_login():
    d=request.get_json();u=d.get("username","").strip().lower();p=d.get("password","")
    users=ldj(USERS_FILE);user=users.get(u)
    if user and user["password"]==_h(p):
        session["user"]=u;session["role"]=user["role"];session["name"]=user["name"]
        return jsonify({"ok":True,"role":user["role"]})
    return jsonify({"ok":False,"error":"Invalid username or password"})

@app.route("/api/select-station",methods=["POST"])
@req_login
def api_station():
    d=request.get_json();sid=d.get("station","")
    stations=ldj(STATIONS_FILE)
    if sid in stations:
        session["station"]=sid;session["station_name"]=stations[sid]
        return jsonify({"ok":True})
    return jsonify({"ok":False})

@app.route("/api/stations")
@req_login
def api_stations(): return jsonify(ldj(STATIONS_FILE))

# ── UPLOAD API ────────────────────────────────────────────
@app.route("/api/upload",methods=["POST"])
@req_login
def api_upload():
    trk=request.form.get("tracking","").strip()
    sta=request.form.get("station",session.get("station","S0"))
    dur=request.form.get("duration","0")
    wrk=session.get("name","Unknown")
    if not trk: return jsonify({"ok":False,"error":"No tracking"})
    fn=f"{sta}_{trk}";now=datetime.now()
    vf=request.files.get("video");vn=None
    if vf:
        vn=f"{fn}.webm";vp=os.path.join(VIDEO_DIR,vn)
        if os.path.exists(vp):vn=f"{fn}_{now.strftime('%H%M%S')}.webm";vp=os.path.join(VIDEO_DIR,vn)
        vf.save(vp)
    pf=request.files.get("photo");pn=None
    if pf:
        pn=f"{fn}.jpg";pp=os.path.join(PHOTO_DIR,pn)
        if os.path.exists(pp):pn=f"{fn}_{now.strftime('%H%M%S')}.jpg";pp=os.path.join(PHOTO_DIR,pn)
        pf.save(pp)
    with open(LOG_FILE,"a") as f:
        f.write(f"{trk},{sta},{now.strftime('%Y-%m-%d')},{now.strftime('%H:%M:%S')},{dur},{vn},{pn},{wrk}\n")
    print(f"[{sta}] {wrk}: {trk} ({dur}s)")
    return jsonify({"ok":True})

# ── SEARCH API ────────────────────────────────────────────
@app.route("/api/search/<trk>")
@req_role("admin","cs")
def api_search(trk):
    r={"tracking":trk,"videos":[],"photos":[],"log":[]};t=trk.lower()
    if os.path.exists(VIDEO_DIR):
        for f in sorted(os.listdir(VIDEO_DIR)):
            if t in f.lower():
                fp=os.path.join(VIDEO_DIR,f);mb=os.path.getsize(fp)/(1024*1024)
                s=f.split("_")[0] if "_" in f else "?"
                r["videos"].append({"filename":f,"size_mb":round(mb,1),"url":f"/media/video/{f}","station":s})
    if os.path.exists(PHOTO_DIR):
        for f in sorted(os.listdir(PHOTO_DIR)):
            if t in f.lower():
                s=f.split("_")[0] if "_" in f else "?"
                r["photos"].append({"filename":f,"url":f"/media/photo/{f}","station":s})
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as cf:
            for row in csv.DictReader(cf):
                if t in row.get("tracking_number","").lower(): r["log"].append(row)
    return jsonify(r)

@app.route("/api/recent")
@req_role("admin","cs")
def api_recent():
    recs=[]
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f: recs=list(csv.DictReader(f))
    recs.reverse()
    return jsonify(recs[:100])

@app.route("/api/stats")
@req_role("admin","cs")
def api_stats():
    tv=0;ts=0
    if os.path.exists(VIDEO_DIR):
        for f in os.listdir(VIDEO_DIR):tv+=1;ts+=os.path.getsize(os.path.join(VIDEO_DIR,f))
    tp=len(os.listdir(PHOTO_DIR)) if os.path.exists(PHOTO_DIR) else 0
    return jsonify({"total_videos":tv,"total_photos":tp,"total_size_mb":round(ts/(1024*1024),1)})

# ── USER MGMT API ────────────────────────────────────────
@app.route("/api/users")
@req_role("admin")
def api_users():
    u=ldj(USERS_FILE)
    return jsonify({k:{"name":v["name"],"role":v["role"]} for k,v in u.items()})

@app.route("/api/users/add",methods=["POST"])
@req_role("admin")
def api_add():
    d=request.get_json();u=d.get("username","").strip().lower();p=d.get("password","")
    n=d.get("name",u);role=d.get("role","worker")
    if not u or not p: return jsonify({"ok":False,"error":"Required"})
    users=ldj(USERS_FILE)
    if u in users: return jsonify({"ok":False,"error":"Exists"})
    users[u]={"password":_h(p),"role":role,"name":n};svj(USERS_FILE,users)
    return jsonify({"ok":True})

@app.route("/api/users/delete",methods=["POST"])
@req_role("admin")
def api_del():
    d=request.get_json();u=d.get("username","")
    if u=="admin": return jsonify({"ok":False,"error":"Cannot delete admin"})
    users=ldj(USERS_FILE)
    if u in users: del users[u];svj(USERS_FILE,users)
    return jsonify({"ok":True})

@app.route("/api/users/pw",methods=["POST"])
@req_role("admin")
def api_pw():
    d=request.get_json();u=d.get("username","");p=d.get("password","")
    if not p: return jsonify({"ok":False,"error":"Required"})
    users=ldj(USERS_FILE)
    if u not in users: return jsonify({"ok":False})
    users[u]["password"]=_h(p);svj(USERS_FILE,users)
    return jsonify({"ok":True})

# ── MEDIA ─────────────────────────────────────────────────
@app.route("/media/video/<fn>")
@req_role("admin","cs")
def sv(fn):
    p=os.path.join(VIDEO_DIR,fn)
    return send_file(p,mimetype="video/webm") if os.path.exists(p) else ("",404)

@app.route("/media/photo/<fn>")
@req_role("admin","cs")
def sp(fn):
    p=os.path.join(PHOTO_DIR,fn)
    return send_file(p,mimetype="image/jpeg") if os.path.exists(p) else ("",404)

# ╔═══════════════════════════════════════════════════════╗
# ║  HTML                                                 ║
# ╚═══════════════════════════════════════════════════════╝
_F='<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">'
_V=":root{--bg:#0b0e14;--c:#151921;--c2:#1a1f2b;--bd:#252b37;--t:#dfe4ed;--t2:#6b7a90;--bl:#3b82f6;--bl2:#60a5fa;--gn:#10b981;--rd:#ef4444;--or:#f59e0b;--pu:#8b5cf6;--r:14px}"

LOGIN_HTML=f'''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">{_F}
<title>Packing Station - Login</title><style>*{{margin:0;padding:0;box-sizing:border-box}}{_V}
body{{font-family:'Inter',sans-serif;background:linear-gradient(135deg,#0b0e14,#111827,#0b0e14);color:var(--t);display:flex;align-items:center;justify-content:center;height:100vh;overflow:hidden}}
.g{{position:fixed;width:500px;height:500px;border-radius:50%;filter:blur(120px);opacity:.15;pointer-events:none}}
.g1{{top:-100px;right:-100px;background:var(--bl)}}.g2{{bottom:-100px;left:-100px;background:var(--pu)}}
.box{{position:relative;z-index:1;width:100%;max-width:420px;padding:20px}}
.br{{text-align:center;margin-bottom:36px}}
.br-logo{{width:70px;height:70px;background:linear-gradient(135deg,var(--bl),var(--pu));border-radius:18px;display:flex;align-items:center;justify-content:center;font-size:34px;margin:0 auto 18px;box-shadow:0 8px 30px rgba(59,130,246,.25)}}
.br-n{{font-size:26px;font-weight:800;letter-spacing:-.5px}}.br-s{{font-size:13px;color:var(--t2);margin-top:5px}}
.cd{{background:var(--c);border:1px solid var(--bd);border-radius:var(--r);padding:32px 28px}}
.cd-t{{font-size:18px;font-weight:700;margin-bottom:3px}}.cd-s{{font-size:12px;color:var(--t2);margin-bottom:24px}}
.f{{margin-bottom:16px}}.f label{{display:block;font-size:11px;font-weight:600;color:var(--t2);margin-bottom:5px;text-transform:uppercase;letter-spacing:.4px}}
.f input{{width:100%;background:var(--bg);border:2px solid var(--bd);border-radius:10px;padding:13px 15px;font-size:15px;color:var(--t);font-family:inherit;outline:none;transition:border .2s}}
.f input:focus{{border-color:var(--bl)}}.f input::placeholder{{color:#3a4252}}
.btn{{width:100%;border:none;border-radius:10px;padding:14px;font-size:15px;font-weight:700;cursor:pointer;font-family:inherit;background:linear-gradient(135deg,var(--bl),#6366f1);color:white;margin-top:6px}}
.btn:hover{{opacity:.9}}.btn:active{{transform:scale(.98)}}
.err{{color:var(--rd);font-size:12px;margin-top:10px;min-height:16px;text-align:center}}
.ft{{text-align:center;margin-top:20px;font-size:11px;color:#2a3040}}
</style></head><body>
<div class="g g1"></div><div class="g g2"></div>
<div class="box"><div class="br"><div class="br-logo">📦</div><div class="br-n">Packing Station</div><div class="br-s">5 Second Beauty — Warehouse System</div></div>
<div class="cd"><div class="cd-t">Welcome back</div><div class="cd-s">Sign in to start your shift</div>
<div class="f"><label>Username</label><input type="text" id="u" placeholder="Enter username" autofocus></div>
<div class="f"><label>Password</label><input type="password" id="p" placeholder="Enter password"></div>
<button class="btn" onclick="go()">Sign In</button><div class="err" id="e"></div></div>
<div class="ft">5 Second Beauty © 2025</div></div>
<script>document.getElementById('p').onkeydown=e=>{{if(e.key==='Enter')go()}};
document.getElementById('u').onkeydown=e=>{{if(e.key==='Enter')document.getElementById('p').focus()}};
async function go(){{const u=document.getElementById('u').value.trim(),p=document.getElementById('p').value;
if(!u||!p){{document.getElementById('e').textContent='Enter username and password';return}}
const r=await fetch('/api/login',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{username:u,password:p}})}});
const d=await r.json();if(d.ok)location.href='/';else document.getElementById('e').textContent=d.error}}</script></body></html>'''

STATION_HTML=f'''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">{_F}
<title>Select Station</title><style>*{{margin:0;padding:0;box-sizing:border-box}}{_V}
body{{font-family:'Inter',sans-serif;background:linear-gradient(135deg,#0b0e14,#111827,#0b0e14);color:var(--t);display:flex;align-items:center;justify-content:center;height:100vh}}
.c{{text-align:center;padding:20px;width:100%;max-width:600px}}
.gr{{font-size:14px;color:var(--t2);margin-bottom:3px}}.ti{{font-size:30px;font-weight:800;margin-bottom:6px}}
.su{{font-size:15px;color:var(--t2);margin-bottom:36px}}
.sg{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}}
.sb{{background:var(--c);border:2px solid var(--bd);border-radius:14px;padding:24px 14px;cursor:pointer;transition:all .2s;text-align:center}}
.sb:hover{{border-color:var(--bl);background:var(--c2);transform:translateY(-2px)}}.sb:active{{transform:scale(.97)}}
.si{{font-size:30px;margin-bottom:8px}}.sl{{font-size:15px;font-weight:700}}.sid{{font-size:11px;color:var(--t2);margin-top:3px}}
.out{{position:fixed;top:16px;right:16px;color:var(--t2);text-decoration:none;font-size:12px;border:1px solid var(--bd);padding:5px 12px;border-radius:7px}}
</style></head><body>
<a href="/logout" class="out">Logout</a>
<div class="c"><div class="gr">Hello, {{{{NAME}}}} 👋</div><div class="ti">Select Your Station</div>
<div class="su">Choose where you're working today</div><div class="sg" id="g"></div></div>
<script>async function ld(){{const r=await fetch('/api/stations');const d=await r.json();
const g=document.getElementById('g');const ic=['📦','🏷️','📋','🔖','📮','✉️'];let i=0;
for(const[id,nm]of Object.entries(d)){{const b=document.createElement('div');b.className='sb';
b.innerHTML='<div class="si">'+ic[i%6]+'</div><div class="sl">'+nm+'</div><div class="sid">'+id+'</div>';
b.onclick=async()=>{{const r=await fetch('/api/select-station',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{station:id}})}});
const d=await r.json();if(d.ok)location.href='/'}};g.appendChild(b);i++}}}}ld();</script></body></html>'''

WORKER_HTML=f'''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">{_F}
<title>Packing Station</title><style>*{{margin:0;padding:0;box-sizing:border-box}}{_V}
html,body{{height:100%;overflow:hidden}}
body{{font-family:'Inter',sans-serif;display:flex;flex-direction:column;align-items:center;justify-content:center;transition:background .4s}}
body.sr{{background:var(--bg)}}body.sc{{background:#1a0a0a}}body.sd{{background:#061a0f}}body.su{{background:var(--bg)}}
.x{{display:none;text-align:center;padding:24px;width:100%}}.x.on{{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:80vh}}
.tb{{position:fixed;top:0;left:0;right:0;padding:10px 18px;display:flex;justify-content:space-between;align-items:center;z-index:10}}
.bg{{background:var(--c);border:1.5px solid var(--bd);border-radius:50px;padding:6px 16px;font-size:12px;font-weight:700;color:var(--bl2)}}
.tr{{display:flex;gap:8px;align-items:center}}
.ci{{display:flex;align-items:center;gap:4px;font-size:11px;padding:4px 9px;border-radius:14px;background:rgba(0,0,0,.3)}}
.cd{{width:6px;height:6px;border-radius:50%}}.co .cd{{background:var(--gn)}}.co span{{color:var(--gn)}}.ce .cd{{background:var(--rd)}}.ce span{{color:var(--rd)}}
.ob{{background:none;border:1px solid var(--bd);border-radius:7px;padding:4px 10px;font-size:11px;color:var(--t2);cursor:pointer;font-family:inherit}}
.pv{{position:fixed;bottom:12px;left:12px;width:140px;border-radius:9px;overflow:hidden;border:2px solid var(--bd);opacity:.35;transition:all .3s}}
.pv video{{width:100%;display:block}}body.sc .pv{{width:180px;opacity:1;border-color:var(--rd)}}
.ri{{width:100px;height:100px;background:var(--c);border-radius:24px;display:flex;align-items:center;justify-content:center;font-size:48px;margin-bottom:24px;border:2.5px solid var(--bd)}}
.rt{{font-size:36px;font-weight:800;margin-bottom:8px}}.rs{{font-size:17px;color:var(--t2);margin-bottom:32px}}
.iw{{width:100%;max-width:460px}}
.ip{{width:100%;background:var(--c);border:3px solid var(--bl);border-radius:12px;padding:16px 20px;font-size:20px;color:var(--t);font-family:inherit;text-align:center;outline:none}}
.ip:focus{{border-color:var(--bl2);box-shadow:0 0 20px rgba(59,130,246,.2)}}.ip::placeholder{{color:#3a4252}}
.ht{{margin-top:12px;font-size:13px;color:var(--t2)}}
.pd{{display:inline-block;width:6px;height:6px;background:var(--bl);border-radius:50%;margin-right:6px;animation:pls 1.5s ease infinite}}
@keyframes pls{{0%,100%{{opacity:.3;transform:scale(1)}}50%{{opacity:1;transform:scale(1.3)}}}}
.ct{{margin-top:32px;font-size:13px;color:var(--t2)}}.ct b{{color:var(--bl2)}}
.rp{{display:flex;align-items:center;gap:10px;background:rgba(239,68,68,.12);border:2px solid rgba(239,68,68,.35);border-radius:50px;padding:9px 22px;margin-bottom:24px;animation:rpl 1.5s ease infinite}}
@keyframes rpl{{0%,100%{{border-color:rgba(239,68,68,.35)}}50%{{border-color:rgba(239,68,68,.75)}}}}
.rd{{width:13px;height:13px;background:var(--rd);border-radius:50%;animation:bk 1s ease infinite}}
@keyframes bk{{0%,100%{{opacity:1}}50%{{opacity:.25}}}}.rl{{font-size:17px;font-weight:700;color:var(--rd)}}
.rk{{font-size:42px;font-weight:900;color:#f1f5f9;margin-bottom:10px;letter-spacing:.5px}}
.rm{{font-size:64px;font-weight:900;color:var(--rd);font-feature-settings:'tnum';margin-bottom:18px}}
.ss{{display:flex;flex-direction:column;gap:9px;margin-top:14px}}
.st{{display:flex;align-items:center;gap:9px;font-size:17px;color:#6b7a90}}.st.nw{{color:#f1f5f9;font-weight:700}}
.sic{{width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:13px;background:var(--c);border:2px solid var(--bd);flex-shrink:0}}
.st.ok .sic{{background:#065f46;border-color:var(--gn)}}.st.nw .sic{{background:#7c2d12;border-color:var(--or);animation:spl 1.5s ease infinite}}
@keyframes spl{{0%,100%{{box-shadow:0 0 0 0 rgba(249,115,22,.25)}}50%{{box-shadow:0 0 0 6px rgba(249,115,22,0)}}}}
.hi{{position:absolute;top:-9999px;left:-9999px}}
.di{{width:100px;height:100px;background:#065f46;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:52px;margin-bottom:18px;animation:pp .4s cubic-bezier(.175,.885,.32,1.275)}}
@keyframes pp{{0%{{transform:scale(0)}}100%{{transform:scale(1)}}}}.dt{{font-size:36px;font-weight:800;color:var(--gn);margin-bottom:5px}}
.dk{{font-size:24px;font-weight:700;margin-bottom:5px}}.df{{font-size:15px;color:var(--t2);margin-bottom:24px}}.dn{{font-size:15px;color:var(--t2)}}
.us{{width:40px;height:40px;border:3px solid var(--bd);border-top-color:var(--bl);border-radius:50%;animation:sp .8s linear infinite;margin-bottom:18px}}
@keyframes sp{{to{{transform:rotate(360deg)}}}}.ut{{font-size:20px;font-weight:700;margin-bottom:5px}}.uu{{font-size:14px;color:var(--t2)}}
</style></head><body class="sr">
<div class="tb"><div class="bg">{{{{STATION}}}} — {{{{NAME}}}}</div><div class="tr"><div class="ci" id="cm"><div class="cd"></div><span>Camera</span></div><button class="ob" onclick="location.href='/logout'">End Shift</button></div></div>
<div class="pv"><video id="pv" autoplay muted playsinline></video></div>
<div class="x on" id="xr"><div class="ri">📦</div><div class="rt">Scan Tracking Number</div><div class="rs">Scan the barcode to start recording</div><div class="iw"><input class="ip" id="mi" placeholder="Waiting for scan..." autofocus autocomplete="off"></div><div class="ht"><span class="pd"></span>Scanner ready</div><div class="ct">Recorded: <b id="cn">0</b></div></div>
<div class="x" id="xc"><div class="rp"><div class="rd"></div><div class="rl">RECORDING</div></div><div class="rk" id="rk"></div><div class="rm" id="rm">00:00</div><div class="ss"><div class="st ok"><div class="sic">✓</div><span>Scan tracking number</span></div><div class="st nw"><div class="sic">2</div><span>Pack the order in front of the camera</span></div><div class="st"><div class="sic">3</div><span>Scan again to finish</span></div></div><input class="hi" id="ri" autocomplete="off"></div>
<div class="x" id="xu"><div class="us"></div><div class="ut">Saving...</div><div class="uu">Please wait</div></div>
<div class="x" id="xd"><div class="di">✓</div><div class="dt">Saved!</div><div class="dk" id="dk"></div><div class="df" id="dd"></div><div class="dn">Next order...</div></div>
<script>
let st='r',ti=null,t0=0,n=0,mr=null,ch=[],sm=null,ct='';
const mi=document.getElementById('mi'),ri=document.getElementById('ri');
const X={{r:document.getElementById('xr'),c:document.getElementById('xc'),u:document.getElementById('xu'),d:document.getElementById('xd')}};
function go(s){{st=s;document.body.className=s==='c'?'sc':s==='d'?'sd':s==='u'?'su':'sr';Object.keys(X).forEach(k=>X[k].classList.toggle('on',k===s));if(s==='r'){{mi.value='';setTimeout(()=>mi.focus(),100)}}if(s==='c'){{ri.value='';setTimeout(()=>ri.focus(),100)}}}}
document.addEventListener('click',()=>{{if(st==='r')mi.focus();if(st==='c')ri.focus()}});
setInterval(()=>{{if(st==='r'&&document.activeElement!==mi)mi.focus();if(st==='c'&&document.activeElement!==ri)ri.focus()}},400);
async function ic(){{try{{sm=await navigator.mediaDevices.getUserMedia({{video:{{width:{{ideal:1280}},height:{{ideal:720}}}},audio:false}});document.getElementById('pv').srcObject=sm;document.getElementById('cm').className='ci co'}}catch(e){{document.getElementById('cm').className='ci ce'}}}}ic();
function sr(t){{if(!sm){{alert('No camera');return}}ct=t;ch=[];mr=new MediaRecorder(sm,{{mimeType:'video/webm;codecs=vp8'}});mr.ondataavailable=e=>{{if(e.data.size>0)ch.push(e.data)}};mr.start(1000);t0=Date.now();stmr();document.getElementById('rk').textContent=t;go('c')}}
async function stp(){{return new Promise(r=>{{mr.onstop=()=>r();mr.stop()}})}}
function cp(){{const v=document.getElementById('pv'),c=document.createElement('canvas');c.width=v.videoWidth;c.height=v.videoHeight;c.getContext('2d').drawImage(v,0,0);return new Promise(r=>c.toBlob(r,'image/jpeg',.9))}}
async function ul(){{go('u');const dur=Math.round((Date.now()-t0)/1000);const vb=new Blob(ch,{{type:'video/webm'}});const pb=await cp();
const fd=new FormData();fd.append('tracking',ct);fd.append('station','{{{{SID}}}}');fd.append('duration',dur);fd.append('video',vb,ct+'.webm');if(pb)fd.append('photo',pb,ct+'.jpg');
try{{const r=await fetch('/api/upload',{{method:'POST',body:fd}});const d=await r.json();if(d.ok){{n++;document.getElementById('cn').textContent=n;document.getElementById('dk').textContent=ct;document.getElementById('dd').textContent='Duration: '+dur+'s';go('d');setTimeout(()=>go('r'),3000)}}else{{alert('Failed');go('r')}}}}catch(e){{alert('Upload failed');go('r')}}}}
mi.addEventListener('keydown',e=>{{if(e.key==='Enter'){{const t=mi.value.trim();if(t)sr(t)}}}});
ri.addEventListener('keydown',async e=>{{if(e.key!=='Enter')return;const t=ri.value.trim();if(!t)return;sptmr();if(t===ct){{await stp();await ul()}}else{{await stp();await ul();setTimeout(()=>sr(t),500)}}}});
function stmr(){{sptmr();ti=setInterval(()=>{{const s=Math.floor((Date.now()-t0)/1000);document.getElementById('rm').textContent=String(Math.floor(s/60)).padStart(2,'0')+':'+String(s%60).padStart(2,'0')}},200)}}
function sptmr(){{if(ti){{clearInterval(ti);ti=null}}}}
</script></body></html>'''

DASH_HTML=f'''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">{_F}
<title>Search Recordings</title><style>*{{margin:0;padding:0;box-sizing:border-box}}{_V}
body{{font-family:'Inter',sans-serif;background:var(--bg);color:var(--t);min-height:100vh}}
.hd{{background:var(--c);border-bottom:1px solid var(--bd);padding:12px 20px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px}}
.lo{{display:flex;align-items:center;gap:8px;font-size:17px;font-weight:700}}
.li{{width:34px;height:34px;background:linear-gradient(135deg,var(--bl),#6366f1);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:17px}}
.hr{{display:flex;gap:12px;align-items:center}}.sts{{display:flex;gap:12px;font-size:11px;color:var(--t2)}}.sts b{{color:var(--bl2)}}
.nl{{color:var(--pu);text-decoration:none;font-size:11px;padding:4px 9px;border:1px solid var(--bd);border-radius:6px}}
.ol{{color:var(--t2);text-decoration:none;font-size:11px}}
.sr{{padding:22px 20px 16px;max-width:660px;margin:0 auto}}.sb{{display:flex;gap:8px}}
.sb input{{flex:1;background:var(--c);border:2px solid var(--bd);border-radius:var(--r);padding:12px 14px;font-size:16px;color:var(--t);font-family:inherit;outline:none}}
.sb input:focus{{border-color:var(--bl)}}.sb input::placeholder{{color:#3a4252}}
.sb button{{background:linear-gradient(135deg,var(--bl),#6366f1);border:none;border-radius:var(--r);padding:12px 20px;font-size:14px;font-weight:700;color:white;cursor:pointer;font-family:inherit}}
.cn{{padding:0 20px 36px;max-width:860px;margin:0 auto}}
.rc{{background:var(--c);border:1px solid var(--bd);border-radius:var(--r);margin-bottom:12px;overflow:hidden;animation:fu .3s ease}}
@keyframes fu{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:translateY(0)}}}}
.rh{{padding:12px 16px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--bd)}}
.rl{{font-size:16px;font-weight:700;letter-spacing:.3px}}.rm{{font-size:11px;color:var(--t2);display:flex;gap:8px;align-items:center}}
.rb{{padding:14px;display:grid;grid-template-columns:1fr 1fr;gap:12px}}@media(max-width:600px){{.rb{{grid-template-columns:1fr}}}}
.mb{{border-radius:7px;overflow:hidden;background:var(--bg);border:1px solid var(--bd)}}.mb video,.mb img{{width:100%;display:block}}
.ml{{padding:6px 10px;font-size:10px;color:var(--t2);border-top:1px solid var(--bd)}}
.stt{{font-size:13px;font-weight:600;color:var(--t2);margin:18px 0 8px}}
.tbl{{width:100%;background:var(--c);border:1px solid var(--bd);border-radius:var(--r);overflow:hidden}}
.tbl table{{width:100%;border-collapse:collapse}}.tbl th{{background:var(--c2);padding:8px 12px;font-size:10px;font-weight:600;color:var(--t2);text-align:left;border-bottom:1px solid var(--bd);text-transform:uppercase;letter-spacing:.3px}}
.tbl td{{padding:8px 12px;font-size:12px;border-bottom:1px solid var(--bd)}}.tbl tr:last-child td{{border-bottom:none}}.tbl tr:hover td{{background:var(--c2)}}
.cr{{cursor:pointer}}.tc{{font-weight:600;color:var(--bl2)}}.sn{{font-weight:600;color:var(--or)}}.wn{{color:var(--t2)}}
.bg{{display:inline-block;padding:1px 6px;border-radius:4px;font-size:9px;font-weight:600}}
.bg-g{{background:rgba(16,185,129,.1);color:var(--gn)}}.bg-s{{background:rgba(245,158,11,.1);color:var(--or)}}
.em{{text-align:center;padding:44px 16px;color:var(--t2)}}.em .ei{{font-size:32px;margin-bottom:8px}}.em .et{{font-size:14px;font-weight:600;color:var(--t)}}
.ld{{text-align:center;padding:26px;color:var(--t2)}}
.spn{{width:24px;height:24px;border:3px solid var(--bd);border-top-color:var(--bl);border-radius:50%;animation:sp .8s linear infinite;margin:0 auto 6px}}
@keyframes sp{{to{{transform:rotate(360deg)}}}}
</style></head><body>
<div class="hd"><div class="lo"><div class="li">🔍</div>Search Recordings</div><div class="hr"><div class="sts">🎥 <b id="sv">-</b> &nbsp;📸 <b id="sph">-</b> &nbsp;💾 <b id="ss">-</b></div><a href="/users" class="nl" style="display:{{{{ADMIN_VIS}}}}">👥 Users</a><a href="/logout" class="ol">Logout ({{{{NAME}}}})</a></div></div>
<div class="sr"><div class="sb"><input type="text" id="si" placeholder="Enter tracking number..." autofocus><button onclick="ds()">Search</button></div></div>
<div class="cn"><div id="res"></div><div class="stt">🕐 Recent Recordings</div><div id="rl"><div class="ld"><div class="spn"></div>Loading...</div></div></div>
<script>
const si=document.getElementById('si');si.onkeydown=e=>{{if(e.key==='Enter')ds()}};
async function ds(){{const q=si.value.trim();if(!q)return;document.getElementById('res').innerHTML='<div class="ld"><div class="spn"></div>Searching...</div>';
const r=await fetch('/api/search/'+encodeURIComponent(q));const d=await r.json();
if(!d.videos.length&&!d.photos.length){{document.getElementById('res').innerHTML='<div class="em"><div class="ei">🔍</div><div class="et">No results for '+d.tracking+'</div></div>';return}}
let h='';for(let i=0;i<d.videos.length;i++){{const v=d.videos[i],p=d.photos[i]||null,l=d.log[i]||null;
h+='<div class="rc"><div class="rh"><span class="rl">'+d.tracking+'</span><div class="rm">'+(l?'<span>'+l.date+'</span><span>'+l.duration_seconds+'s</span>':'')+(l&&l.worker?'<span>👤 '+l.worker+'</span>':'')+'<span class="bg bg-s">'+v.station+'</span><span class="bg bg-g">✓</span></div></div><div class="rb"><div class="mb"><video controls preload="metadata"><source src="'+v.url+'" type="video/webm"></video><div class="ml">🎥 '+v.size_mb+' MB</div></div>'+(p?'<div class="mb"><img src="'+p.url+'"><div class="ml">📸 Photo</div></div>':'')+'</div></div>'}}
document.getElementById('res').innerHTML=h}}
async function lr(){{const r=await fetch('/api/recent');const d=await r.json();if(!d.length){{document.getElementById('rl').innerHTML='<div class="em"><div class="ei">📭</div><div class="et">No recordings</div></div>';return}}
let rows=d.map(r=>'<tr class="cr" onclick="si.value=\''+r.tracking_number+'\';ds()"><td class="tc">'+r.tracking_number+'</td><td class="sn">'+(r.station||'-')+'</td><td class="wn">'+(r.worker||'-')+'</td><td>'+(r.date||'-')+'</td><td>'+(r.time||'-')+'</td><td>'+(r.duration_seconds||'-')+'s</td></tr>').join('');
document.getElementById('rl').innerHTML='<div class="tbl"><table><thead><tr><th>Tracking</th><th>Station</th><th>Worker</th><th>Date</th><th>Time</th><th>Duration</th></tr></thead><tbody>'+rows+'</tbody></table></div>'}}
async function ls(){{const r=await fetch('/api/stats');const d=await r.json();document.getElementById('sv').textContent=d.total_videos;document.getElementById('sph').textContent=d.total_photos;document.getElementById('ss').textContent=d.total_size_mb+' MB'}}
lr();ls();
</script></body></html>'''

USERS_HTML=f'''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">{_F}
<title>Users</title><style>*{{margin:0;padding:0;box-sizing:border-box}}{_V}
body{{font-family:'Inter',sans-serif;background:var(--bg);color:var(--t);padding:20px;max-width:680px;margin:0 auto}}
.bk{{color:var(--bl2);text-decoration:none;font-size:12px;display:inline-block;margin-bottom:14px}}
h1{{font-size:20px;margin-bottom:18px}}
.cd{{background:var(--c);border:1px solid var(--bd);border-radius:var(--r);padding:18px;margin-bottom:16px}}
.cd h2{{font-size:12px;color:var(--t2);margin-bottom:12px;text-transform:uppercase;letter-spacing:.3px}}
table{{width:100%;border-collapse:collapse}}th{{text-align:left;padding:7px 8px;font-size:10px;color:var(--t2);border-bottom:1px solid var(--bd);text-transform:uppercase}}
td{{padding:7px 8px;font-size:12px;border-bottom:1px solid var(--bd)}}tr:last-child td{{border-bottom:none}}
.rb{{padding:1px 6px;border-radius:4px;font-size:9px;font-weight:600}}.ra{{background:rgba(99,102,241,.1);color:#818cf8}}.rw{{background:rgba(245,158,11,.1);color:var(--or)}}.rc{{background:rgba(16,185,129,.1);color:var(--gn)}}
.db{{background:none;border:1px solid var(--rd);color:var(--rd);padding:2px 8px;border-radius:4px;cursor:pointer;font-size:10px;font-family:inherit}}
.cb{{background:none;border:1px solid var(--bl);color:var(--bl);padding:2px 8px;border-radius:4px;cursor:pointer;font-size:10px;font-family:inherit;margin-right:4px}}
.fr{{display:flex;gap:6px;margin-bottom:6px;flex-wrap:wrap}}
.fr input,.fr select{{background:var(--bg);border:1px solid var(--bd);border-radius:7px;padding:8px 10px;color:var(--t);font-size:12px;font-family:inherit;outline:none;flex:1;min-width:90px}}
.ab{{background:var(--gn);border:none;border-radius:7px;padding:8px 14px;color:white;font-weight:600;cursor:pointer;font-family:inherit;font-size:12px}}
.mg{{font-size:11px;margin-top:5px;min-height:14px}}.mg.ok{{color:var(--gn)}}.mg.er{{color:var(--rd)}}
</style></head><body>
<a href="/dashboard" class="bk">← Back</a><h1>👥 Users</h1>
<div class="cd"><h2>Current Users</h2><table id="ut"><tbody></tbody></table></div>
<div class="cd"><h2>Add User</h2><div class="fr"><input id="nu" placeholder="Username"><input type="password" id="np" placeholder="Password"><input id="nn" placeholder="Display Name"><select id="nr"><option value="worker">Worker</option><option value="cs">CS</option><option value="admin">Admin</option></select><button class="ab" onclick="au()">Add</button></div><div class="mg" id="am"></div></div>
<script>
async function ld(){{const r=await fetch('/api/users');const d=await r.json();let rows='';
for(const[k,v]of Object.entries(d)){{const rc=v.role==='admin'?'ra':v.role==='cs'?'rc':'rw';
rows+='<tr><td><b>'+k+'</b></td><td>'+v.name+'</td><td><span class="rb '+rc+'">'+v.role+'</span></td><td>'+(k!=='admin'?'<button class="cb" onclick="cp(\''+k+'\')">PW</button><button class="db" onclick="dl(\''+k+'\')">Del</button>':'')+'</td></tr>'}}
document.querySelector('#ut tbody').innerHTML=rows}}
async function au(){{const u=document.getElementById('nu').value.trim(),p=document.getElementById('np').value,n=document.getElementById('nn').value.trim()||u,rl=document.getElementById('nr').value,m=document.getElementById('am');
if(!u||!p){{m.className='mg er';m.textContent='Required';return}}
const r=await fetch('/api/users/add',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{username:u,password:p,name:n,role:rl}})}});
const d=await r.json();if(d.ok){{m.className='mg ok';m.textContent='Added!';ld();document.getElementById('nu').value='';document.getElementById('np').value='';document.getElementById('nn').value=''}}else{{m.className='mg er';m.textContent=d.error}}}}
async function dl(u){{if(!confirm('Delete "'+u+'"?'))return;await fetch('/api/users/delete',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{username:u}})}});ld()}}
async function cp(u){{const p=prompt('New password for "'+u+'":');if(!p)return;const r=await fetch('/api/users/pw',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{username:u,password:p}})}});const d=await r.json();alert(d.ok?'Changed!':d.error)}}
ld();
</script></body></html>'''

if __name__=="__main__":
    print("="*50)
    print("📦 5 Second Beauty — Packing Station")
    print("="*50)
    print(f"\n📂 Data: {DATA_DIR}")
    print(f"🌐 http://localhost:{PORT}")
    try:
        import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.connect(("8.8.8.8",80))
        print(f"📱 Network: http://{s.getsockname()[0]}:{PORT}");s.close()
    except:pass
    print(f"\n👤 admin/admin123  📞 cs1/cs123  👷 worker1-6/pack1-6")
    print("="*50)
    app.run(host="0.0.0.0",port=PORT,debug=False,threaded=True)
