#!/usr/bin/env python3
"""
5 Second Beauty — Packing Station
Production web app for packing video recording & lookup.
"""
import os,csv,json,hashlib,secrets,time,threading
from datetime import datetime,timedelta
from functools import wraps
from flask import Flask,request,jsonify,send_file,redirect,session

DATA_DIR=os.environ.get("DATA_DIR",os.path.join(os.path.expanduser("~"),"PackingStationData"))
VIDEO_DIR=os.path.join(DATA_DIR,"videos")
PHOTO_DIR=os.path.join(DATA_DIR,"photos")
LOG_FILE=os.path.join(DATA_DIR,"packing_log.csv")
USERS_FILE=os.path.join(DATA_DIR,"users.json")
STATIONS_FILE=os.path.join(DATA_DIR,"stations.json")
SECRET_KEY=os.environ.get("SECRET_KEY",secrets.token_hex(32))
PORT=int(os.environ.get("PORT",8080))
RETENTION_DAYS=int(os.environ.get("RETENTION_DAYS",30))

for d in [DATA_DIR,VIDEO_DIR,PHOTO_DIR]: os.makedirs(d,exist_ok=True)

def cleanup_old_files():
    """Delete video/photo files older than RETENTION_DAYS"""
    cutoff=time.time()-RETENTION_DAYS*86400
    deleted=0;freed=0
    for folder in [VIDEO_DIR,PHOTO_DIR]:
        if not os.path.exists(folder): continue
        for f in os.listdir(folder):
            fp=os.path.join(folder,f)
            try:
                if os.path.getmtime(fp)<cutoff:
                    sz=os.path.getsize(fp)
                    os.remove(fp)
                    deleted+=1;freed+=sz
            except: pass
    # Clean old log entries
    if os.path.exists(LOG_FILE):
        cutoff_date=(datetime.now()-timedelta(days=RETENTION_DAYS)).strftime('%Y-%m-%d')
        try:
            with open(LOG_FILE) as f: rows=list(csv.DictReader(f))
            kept=[r for r in rows if r.get("date","")>=cutoff_date]
            if len(kept)<len(rows):
                with open(LOG_FILE,"w") as f:
                    w=csv.DictWriter(f,fieldnames=["tracking_number","station","date","time","duration_seconds","video_file","photo_file","worker"])
                    w.writeheader();w.writerows(kept)
        except: pass
    if deleted>0: print("Cleanup: deleted",deleted,"files, freed",round(freed/(1024*1024),1),"MB")
    return {"deleted":deleted,"freed_mb":round(freed/(1024*1024),1)}

def cleanup_loop():
    while True:
        time.sleep(3600)
        try: cleanup_old_files()
        except: pass

cleanup_thread=threading.Thread(target=cleanup_loop,daemon=True)
cleanup_thread.start()
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE,"w") as f: f.write("tracking_number,station,date,time,duration_seconds,video_file,photo_file,worker\n")

def _h(pw): return hashlib.sha256(pw.encode()).hexdigest()
def _init(path,default):
    if not os.path.exists(path):
        with open(path,"w") as f: json.dump(default,f,indent=2)
def ldj(p):
    with open(p) as f: return json.load(f)
def svj(p,d):
    with open(p,"w") as f: json.dump(d,f,indent=2)

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

@app.route("/")
def index():
    if "user" not in session: return LOGIN_HTML
    if session.get("role")=="worker":
        if "station" not in session:
            return STATION_HTML.replace("__NAME__",session["name"])
        return WORKER_HTML.replace("__NAME__",session["name"]).replace("__STATION__",session.get("station_name","")).replace("__SID__",session.get("station","S0"))
    return redirect("/dashboard")

@app.route("/dashboard")
@req_role("admin","cs")
def dashboard():
    disp="flex" if session.get("role")=="admin" else "none"
    return DASH_HTML.replace("__NAME__",session.get("name","")).replace("__ADMIN_VIS__",disp)

@app.route("/users")
@req_role("admin")
def users_page(): return USERS_HTML

@app.route("/logout")
def logout(): session.clear(); return redirect("/")

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

@app.route("/api/upload",methods=["POST"])
@req_login
def api_upload():
    trk=request.form.get("tracking","").strip()
    sta=request.form.get("station",session.get("station","S0"))
    dur=request.form.get("duration","0")
    wrk=session.get("name","Unknown")
    if not trk: return jsonify({"ok":False})
    fn=sta+"_"+trk;now=datetime.now()
    vf=request.files.get("video");vn=None
    if vf:
        vn=fn+".webm";vp=os.path.join(VIDEO_DIR,vn)
        if os.path.exists(vp):vn=fn+"_"+now.strftime('%H%M%S')+".webm";vp=os.path.join(VIDEO_DIR,vn)
        vf.save(vp)
    pf=request.files.get("photo");pn=None
    if pf:
        pn=fn+".jpg";pp=os.path.join(PHOTO_DIR,pn)
        if os.path.exists(pp):pn=fn+"_"+now.strftime('%H%M%S')+".jpg";pp=os.path.join(PHOTO_DIR,pn)
        pf.save(pp)
    with open(LOG_FILE,"a") as f:
        f.write(trk+","+sta+","+now.strftime('%Y-%m-%d')+","+now.strftime('%H:%M:%S')+","+str(dur)+","+str(vn)+","+str(pn)+","+wrk+"\n")
    return jsonify({"ok":True})

@app.route("/api/search/<trk>")
@req_role("admin","cs")
def api_search(trk):
    r={"tracking":trk,"videos":[],"photos":[],"log":[]};t=trk.lower()
    if os.path.exists(VIDEO_DIR):
        for f in sorted(os.listdir(VIDEO_DIR)):
            if t in f.lower():
                fp=os.path.join(VIDEO_DIR,f);mb=os.path.getsize(fp)/(1024*1024)
                s=f.split("_")[0] if "_" in f else "?"
                r["videos"].append({"filename":f,"size_mb":round(mb,1),"url":"/media/video/"+f,"station":s})
    if os.path.exists(PHOTO_DIR):
        for f in sorted(os.listdir(PHOTO_DIR)):
            if t in f.lower():
                s=f.split("_")[0] if "_" in f else "?"
                r["photos"].append({"filename":f,"url":"/media/photo/"+f,"station":s})
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

@app.route("/api/analytics")
@req_role("admin","cs")
def api_analytics():
    recs=[]
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f: recs=list(csv.DictReader(f))
    today=datetime.now().strftime('%Y-%m-%d')
    # Per worker stats
    workers={}
    workers_today={}
    for r in recs:
        w=r.get("worker","Unknown")
        dur=0
        try: dur=float(r.get("duration_seconds",0))
        except: pass
        if w not in workers: workers[w]={"count":0,"total_dur":0,"dates":set()}
        workers[w]["count"]+=1
        workers[w]["total_dur"]+=dur
        workers[w]["dates"].add(r.get("date",""))
        if r.get("date","")==today:
            if w not in workers_today: workers_today[w]={"count":0,"total_dur":0}
            workers_today[w]["count"]+=1
            workers_today[w]["total_dur"]+=dur
    # Per station stats
    stations={}
    for r in recs:
        s=r.get("station","?")
        if s not in stations: stations[s]={"count":0}
        stations[s]["count"]+=1
    # Build response
    worker_list=[]
    for w,d in workers.items():
        avg=round(d["total_dur"]/d["count"],1) if d["count"]>0 else 0
        td=workers_today.get(w,{"count":0,"total_dur":0})
        avg_today=round(td["total_dur"]/td["count"],1) if td["count"]>0 else 0
        worker_list.append({"name":w,"total":d["count"],"avg_seconds":avg,
            "today":td["count"],"avg_today":avg_today,"days_worked":len(d["dates"])})
    worker_list.sort(key=lambda x:x["today"],reverse=True)
    station_list=[{"id":k,"count":v["count"]} for k,v in stations.items()]
    # Daily totals (last 14 days)
    daily={}
    for r in recs:
        dt=r.get("date","")
        if dt not in daily: daily[dt]={"count":0,"total_dur":0}
        daily[dt]["count"]+=1
        try: daily[dt]["total_dur"]+=float(r.get("duration_seconds",0))
        except: pass
    daily_list=[]
    for dt in sorted(daily.keys(),reverse=True)[:14]:
        d=daily[dt]
        avg=round(d["total_dur"]/d["count"],1) if d["count"]>0 else 0
        daily_list.append({"date":dt,"count":d["count"],"avg_seconds":avg})
    total_today=sum(v["count"] for v in workers_today.values())
    return jsonify({"workers":worker_list,"stations":station_list,"daily":daily_list,
        "total_today":total_today,"total_all":len(recs),"date":today})

@app.route("/analytics")
@req_role("admin","cs")
def analytics_page():
    disp="flex" if session.get("role")=="admin" else "none"
    return ANALYTICS_HTML.replace("__NAME__",session.get("name","")).replace("__ADMIN_VIS__",disp)

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
    if u in users: return jsonify({"ok":False,"error":"Already exists"})
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
    if not p: return jsonify({"ok":False})
    users=ldj(USERS_FILE)
    if u not in users: return jsonify({"ok":False})
    users[u]["password"]=_h(p);svj(USERS_FILE,users)
    return jsonify({"ok":True})

@app.route("/api/storage")
@req_role("admin")
def api_storage():
    vcount=0;vsize=0;pcount=0;psize=0
    oldest=None;newest=None
    if os.path.exists(VIDEO_DIR):
        for f in os.listdir(VIDEO_DIR):
            fp=os.path.join(VIDEO_DIR,f);vcount+=1;vsize+=os.path.getsize(fp)
            mt=os.path.getmtime(fp)
            if oldest is None or mt<oldest: oldest=mt
            if newest is None or mt>newest: newest=mt
    if os.path.exists(PHOTO_DIR):
        for f in os.listdir(PHOTO_DIR):
            fp=os.path.join(PHOTO_DIR,f);pcount+=1;psize+=os.path.getsize(fp)
    total=(vsize+psize)/(1024*1024)
    return jsonify({
        "videos":vcount,"photos":pcount,
        "video_size_mb":round(vsize/(1024*1024),1),
        "photo_size_mb":round(psize/(1024*1024),1),
        "total_mb":round(total,1),
        "total_gb":round(total/1024,2),
        "retention_days":RETENTION_DAYS,
        "oldest":datetime.fromtimestamp(oldest).strftime('%Y-%m-%d') if oldest else None,
        "newest":datetime.fromtimestamp(newest).strftime('%Y-%m-%d') if newest else None
    })

@app.route("/api/cleanup",methods=["POST"])
@req_role("admin")
def api_cleanup():
    r=cleanup_old_files()
    return jsonify({"ok":True,"deleted":r["deleted"],"freed_mb":r["freed_mb"]})

@app.route("/media/video/<fn>")
@req_role("admin","cs")
def serve_v(fn):
    p=os.path.join(VIDEO_DIR,fn)
    return send_file(p,mimetype="video/webm") if os.path.exists(p) else ("",404)

@app.route("/media/photo/<fn>")
@req_role("admin","cs")
def serve_p(fn):
    p=os.path.join(PHOTO_DIR,fn)
    return send_file(p,mimetype="image/jpeg") if os.path.exists(p) else ("",404)

# ══════════════════════════════════════════════════════════
# HTML TEMPLATES (no f-strings to avoid escaping nightmares)
# ══════════════════════════════════════════════════════════

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
function initCam(){navigator.mediaDevices.getUserMedia({video:{width:{ideal:1280},height:{ideal:720}},audio:false}).then(function(s){sm=s;document.getElementById('pv').srcObject=s;document.getElementById('cm').className='cam ok'}).catch(function(){document.getElementById('cm').className='cam err'})}
initCam();
function startRec(t){if(!sm){alert('No camera');return}ct=t;ch=[];mr=new MediaRecorder(sm,{mimeType:'video/webm;codecs=vp8'});mr.ondataavailable=function(e){if(e.data.size>0)ch.push(e.data)};mr.start(1000);t0=Date.now();startTmr();document.getElementById('rk').textContent=t;go('c')}
function stopRec(){return new Promise(function(res){mr.onstop=res;mr.stop()})}
function capPhoto(){var v=document.getElementById('pv'),c=document.createElement('canvas');c.width=v.videoWidth;c.height=v.videoHeight;c.getContext('2d').drawImage(v,0,0);return new Promise(function(res){c.toBlob(res,'image/jpeg',.9)})}
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
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#0c0f16;color:#e4e8f1;min-height:100vh}
.hdr{background:rgba(21,25,33,.9);backdrop-filter:blur(10px);border-bottom:1px solid rgba(255,255,255,.06);padding:16px 28px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;position:sticky;top:0;z-index:10}
.logo{display:flex;align-items:center;gap:10px;font-size:18px;font-weight:800}
.logo-i{width:36px;height:36px;background:linear-gradient(135deg,#4f46e5,#7c3aed);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px}
.hdr-r{display:flex;gap:16px;align-items:center;flex-wrap:wrap}
.stat-pills{display:flex;gap:8px}
.pill{display:flex;align-items:center;gap:6px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.06);border-radius:20px;padding:6px 14px;font-size:12px;color:#6b7a90}
.pill b{color:#a5b4fc}
.nav-btn{color:#a5b4fc;text-decoration:none;font-size:13px;font-weight:600;padding:8px 16px;border:1.5px solid rgba(79,70,229,.3);border-radius:10px;background:rgba(79,70,229,.08);transition:all .2s;display:__ADMIN_VIS__}
.nav-btn:hover{background:rgba(79,70,229,.15);border-color:rgba(79,70,229,.5)}
.out-link{color:#6b7a90;text-decoration:none;font-size:13px;padding:8px 14px;border:1px solid rgba(255,255,255,.06);border-radius:10px;transition:all .2s}
.out-link:hover{color:#e4e8f1;border-color:rgba(255,255,255,.12)}

.search-area{padding:32px 28px 20px;max-width:720px;margin:0 auto}
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
<div class="hdr">
<div class="logo"><div class="logo-i">🔍</div>Search Recordings</div>
<div class="hdr-r">
<div class="stat-pills"><div class="pill">🎥 <b id="sv">-</b></div><div class="pill">📸 <b id="sph">-</b></div><div class="pill">💾 <b id="ss">-</b></div></div>
<a href="/analytics" class="nav-btn" style="display:flex">📊 Analytics</a>
<a href="/users" class="nav-btn">👥 Manage Users</a>
<a href="/logout" class="out-link">Logout (__NAME__)</a>
</div></div>
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
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#0c0f16;color:#e4e8f1;min-height:100vh;padding:28px;max-width:760px;margin:0 auto}
.back{color:#a5b4fc;text-decoration:none;font-size:14px;font-weight:600;display:inline-flex;align-items:center;gap:6px;margin-bottom:20px;padding:8px 14px;border-radius:10px;background:rgba(79,70,229,.08);border:1px solid rgba(79,70,229,.2);transition:all .2s}
.back:hover{background:rgba(79,70,229,.15)}
h1{font-size:26px;font-weight:800;margin-bottom:24px}
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
<a href="/dashboard" class="back">← Back to Dashboard</a>
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
</script></body></html>'''

# ── ANALYTICS PAGE ────────────────────────────────────────
ANALYTICS_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
''' + _FONT + '''
<title>Analytics</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#0c0f16;color:#e4e8f1;min-height:100vh}
.hdr{background:rgba(21,25,33,.9);backdrop-filter:blur(10px);border-bottom:1px solid rgba(255,255,255,.06);padding:16px 28px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;position:sticky;top:0;z-index:10}
.logo{display:flex;align-items:center;gap:10px;font-size:18px;font-weight:800}
.logo-i{width:36px;height:36px;background:linear-gradient(135deg,#f59e0b,#ef4444);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px}
.hdr-r{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.nav-btn{color:#a5b4fc;text-decoration:none;font-size:13px;font-weight:600;padding:8px 16px;border:1.5px solid rgba(79,70,229,.3);border-radius:10px;background:rgba(79,70,229,.08);transition:all .2s}
.nav-btn:hover{background:rgba(79,70,229,.15)}
.out-link{color:#6b7a90;text-decoration:none;font-size:13px;padding:8px 14px;border:1px solid rgba(255,255,255,.06);border-radius:10px}

.content{padding:28px;max-width:1000px;margin:0 auto}

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
<div class="hdr">
<div class="logo"><div class="logo-i">📊</div>Analytics</div>
<div class="hdr-r">
<a href="/dashboard" class="nav-btn">🔍 Search</a>
<a href="/users" class="nav-btn" style="display:__ADMIN_VIS__">👥 Users</a>
<a href="/logout" class="out-link">Logout (__NAME__)</a>
</div></div>

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

if __name__=="__main__":
    print("="*50)
    print("5 Second Beauty - Packing Station")
    print("="*50)
    print("Data:",DATA_DIR)
    print("URL: http://localhost:"+str(PORT))
    try:
        import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.connect(("8.8.8.8",80))
        print("Net: http://"+s.getsockname()[0]+":"+str(PORT));s.close()
    except:pass
    print("Admin: admin/admin123  CS: cs1/cs123  Workers: worker1-6/pack1-6")
    print("="*50)
    app.run(host="0.0.0.0",port=PORT,debug=False,threaded=True)
