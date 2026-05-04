#!/usr/bin/env python3
"""
5 Second Beauty — Packing Station
Production web app for packing video recording & lookup.
"""
import os,csv,json,hashlib,secrets,time,threading,re,sys,sqlite3
from datetime import datetime,timedelta
from functools import wraps
from flask import Flask,request,jsonify,send_file,redirect,session
from werkzeug.utils import secure_filename
import bcrypt

DATA_DIR=os.environ.get("DATA_DIR",os.path.join(os.path.expanduser("~"),"PackingStationData"))
VIDEO_DIR=os.path.join(DATA_DIR,"videos")
PHOTO_DIR=os.path.join(DATA_DIR,"photos")
LOG_FILE=os.path.join(DATA_DIR,"packing_log.csv")
USERS_FILE=os.path.join(DATA_DIR,"users.json")
STATIONS_FILE=os.path.join(DATA_DIR,"stations.json")

# FIX #1: SECRET_KEY must be set in environment - fail loud if missing.
# Auto-generating it would invalidate all sessions on every restart.
SECRET_KEY=os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    print("FATAL: SECRET_KEY environment variable is not set.",file=sys.stderr)
    print("Set it in Railway -> Variables. Generate one with: python -c \"import secrets;print(secrets.token_hex(32))\"",file=sys.stderr)
    sys.exit(1)
if len(SECRET_KEY)<32:
    print("FATAL: SECRET_KEY too short (must be >=32 chars).",file=sys.stderr)
    sys.exit(1)

PORT=int(os.environ.get("PORT",8080))
RETENTION_DAYS=int(os.environ.get("RETENTION_DAYS",30))

# Cloudflare R2 cloud storage config (S3-compatible).
# When configured, videos/photos are stored in R2 instead of local disk.
# Saves ~95% on storage cost vs Railway Volume + zero egress fees.
R2_BUCKET=os.environ.get("R2_BUCKET")
R2_ENDPOINT=os.environ.get("R2_ENDPOINT")
R2_ACCESS_KEY_ID=os.environ.get("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY=os.environ.get("R2_SECRET_ACCESS_KEY")
R2_PRESIGN_TTL=int(os.environ.get("R2_PRESIGN_TTL",3600))  # 1 hour
r2=None
_r2_vars=[R2_BUCKET,R2_ENDPOINT,R2_ACCESS_KEY_ID,R2_SECRET_ACCESS_KEY]
if any(_r2_vars):
    if not all(_r2_vars):
        print("FATAL: Partial R2 config. Set ALL of R2_BUCKET, R2_ENDPOINT, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY (or none).",file=sys.stderr)
        sys.exit(1)
    try:
        import boto3
        from botocore.client import Config as BotoConfig
        r2=boto3.client('s3',
            endpoint_url=R2_ENDPOINT,
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
            config=BotoConfig(signature_version='s3v4'),
            region_name='auto'
        )
        print("R2 storage enabled: bucket="+R2_BUCKET,flush=True)
    except Exception as e:
        print("FATAL: R2 client init failed:",e,file=sys.stderr)
        sys.exit(1)
else:
    print("R2 not configured - using local file storage at "+DATA_DIR,flush=True)

for d in [DATA_DIR,VIDEO_DIR,PHOTO_DIR]: os.makedirs(d,exist_ok=True)

def cleanup_old_files():
    """Delete video/photo files older than RETENTION_DAYS.
    When R2 is configured, file deletion is handled by R2 lifecycle rules.
    This function only cleans the local CSV log of old rows in that case."""
    cutoff=time.time()-RETENTION_DAYS*86400
    deleted=0;freed=0
    if not r2:  # only clean local files when not using R2
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
    # Always clean old log entries
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

def _h(pw):
    """Hash password with bcrypt (rounds=12)."""
    return bcrypt.hashpw(pw.encode(),bcrypt.gensalt(rounds=12)).decode()

def _legacy_sha256(pw):
    """Legacy SHA256 hash - only used to verify pre-bcrypt passwords once for migration."""
    return hashlib.sha256(pw.encode()).hexdigest()

def _verify(pw,stored):
    """Verify password against stored hash. Supports both bcrypt and legacy sha256."""
    if not stored: return False
    if stored.startswith("$2"):
        try: return bcrypt.checkpw(pw.encode(),stored.encode())
        except: return False
    if len(stored)==64:
        return secrets.compare_digest(stored,_legacy_sha256(pw))
    return False

def _gen_pw():
    """Generate a strong random password."""
    return secrets.token_urlsafe(12)

def _gen_badge_token():
    """Generate a barcode-friendly badge token: 16 alphanumeric chars in 4-char groups.
    Excludes ambiguous chars (0/O, 1/I/l) for visual scanning fallback."""
    alphabet="23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # 32 chars
    raw="".join(secrets.choice(alphabet) for _ in range(16))
    return raw[:4]+"-"+raw[4:8]+"-"+raw[8:12]+"-"+raw[12:16]

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

def _init(path,default):
    if not os.path.exists(path):
        with open(path,"w") as f: json.dump(default,f,indent=2)
def ldj(p):
    with open(p) as f: return json.load(f)
def svj(p,d):
    with open(p,"w") as f: json.dump(d,f,indent=2)

# On first run only: generate strong random passwords and print them once.
# After this file exists, change passwords via the admin UI.
if not os.path.exists(USERS_FILE):
    _initial_users={
        "admin":{"role":"admin","name":"Admin"},
        "cs1":{"role":"cs","name":"Customer Service"},
        "worker1":{"role":"worker","name":"Worker 1"},
        "worker2":{"role":"worker","name":"Worker 2"},
        "worker3":{"role":"worker","name":"Worker 3"},
        "worker4":{"role":"worker","name":"Worker 4"},
        "worker5":{"role":"worker","name":"Worker 5"},
        "worker6":{"role":"worker","name":"Worker 6"},
    }
    _generated={}
    _data={}
    for u,info in _initial_users.items():
        pw=_gen_pw()
        _generated[u]=pw
        _data[u]={"password":_h(pw),"role":info["role"],"name":info["name"]}
        # Workers get a badge token; admin/cs use password login
        if info["role"]=="worker":
            _data[u]["badge_token"]=_gen_badge_token()
    with open(USERS_FILE,"w") as f: json.dump(_data,f,indent=2)
    print("="*70,flush=True)
    print("INITIAL PASSWORDS GENERATED - SAVE THESE NOW (shown only once):",flush=True)
    print("="*70,flush=True)
    for u,p in _generated.items(): print("  "+u.ljust(10)+" -> "+p,flush=True)
    print("="*70,flush=True)
    print("Change them after first login via Admin -> Users.",flush=True)
    print("="*70,flush=True)

_init(STATIONS_FILE,{"S1":"Station 1","S2":"Station 2","S3":"Station 3","S4":"Station 4","S5":"Station 5","S6":"Station 6"})

# ══════════════════════════════════════════════════════════
# ANTHROPIC AI - for parsing addresses from DMs
# ══════════════════════════════════════════════════════════
ANTHROPIC_API_KEY=os.environ.get("ANTHROPIC_API_KEY")
anthropic_client=None
if ANTHROPIC_API_KEY:
    try:
        import anthropic
        anthropic_client=anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        print("Anthropic AI enabled (address parsing)",flush=True)
    except ImportError:
        print("WARN: ANTHROPIC_API_KEY set but 'anthropic' package not installed",flush=True)
    except Exception as e:
        print("WARN: Anthropic client init failed:",e,flush=True)
else:
    print("Anthropic AI not configured (manual address entry only)",flush=True)

# ══════════════════════════════════════════════════════════
# GIVEAWAY MODULE - SQLite database
# ══════════════════════════════════════════════════════════
GIVEAWAY_DB=os.path.join(DATA_DIR,"giveaways.db")
GIVEAWAY_BRANDS=["5 Sec Beauty","Hera Beauty","Peach Beauty"]
GIVEAWAY_STATUSES=["pending_address","address_received","label_created","shipped","cancelled"]

def gdb():
    """Get a SQLite connection with row factory."""
    c=sqlite3.connect(GIVEAWAY_DB,timeout=10.0)
    c.row_factory=sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c

def gdb_init():
    """Create the giveaway table if it doesn't exist."""
    c=gdb()
    c.execute("""CREATE TABLE IF NOT EXISTS giveaways(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        winner_username TEXT NOT NULL,
        prize_name TEXT NOT NULL,
        brand TEXT,
        platform TEXT DEFAULT 'tiktok',
        status TEXT NOT NULL DEFAULT 'pending_address',
        address_name TEXT,
        address_street1 TEXT,
        address_street2 TEXT,
        address_city TEXT,
        address_state TEXT,
        address_zip TEXT,
        address_country TEXT DEFAULT 'US',
        dm_text TEXT,
        shippo_label_url TEXT,
        shippo_label_pdf TEXT,
        tracking_number TEXT,
        label_cost REAL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        address_received_at TEXT,
        shipped_at TEXT,
        created_by TEXT,
        notes TEXT
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_giveaways_status ON giveaways(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_giveaways_created ON giveaways(created_at DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_giveaways_winner ON giveaways(winner_username)")
    c.commit();c.close()

gdb_init()

app=Flask(__name__)
app.secret_key=SECRET_KEY
app.config["MAX_CONTENT_LENGTH"]=250*1024*1024
# Secure session cookie config - HTTPS only, no JS access, CSRF protection via SameSite
app.config["SESSION_COOKIE_HTTPONLY"]=True
app.config["SESSION_COOKIE_SECURE"]=True
app.config["SESSION_COOKIE_SAMESITE"]="Lax"
app.config["PERMANENT_SESSION_LIFETIME"]=timedelta(days=7)

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
    if "user" not in session:
        # If this machine has a station configured, send to badge login by default
        if request.cookies.get("machine_station"):
            return redirect("/badge-login")
        return LOGIN_HTML
    if session.get("role")=="worker":
        # If station already chosen for this session, go to worker page
        if "station" in session:
            return WORKER_HTML.replace("__NAME__",session["name"]).replace("__STATION__",session.get("station_name","")).replace("__SID__",session.get("station","S0"))
        # Auto-assign station from machine cookie if set
        machine_sta=request.cookies.get("machine_station","")
        if machine_sta:
            stations=ldj(STATIONS_FILE)
            if machine_sta in stations:
                session["station"]=machine_sta;session["station_name"]=stations[machine_sta]
                return WORKER_HTML.replace("__NAME__",session["name"]).replace("__STATION__",stations[machine_sta]).replace("__SID__",machine_sta)
        # Fallback: manual station picker
        return STATION_HTML.replace("__NAME__",session["name"])
    return redirect("/dashboard")

@app.route("/dashboard")
@req_role("admin","cs")
def dashboard():
    disp="flex" if session.get("role")=="admin" else "none"
    return DASH_HTML.replace("__NAME__",session.get("name","")).replace("__ADMIN_VIS__",disp).replace("__NAVBAR__",_navbar("dash")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

@app.route("/users")
@req_role("admin")
def users_page(): return USERS_HTML.replace("__NAVBAR__",_navbar("users")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

@app.route("/logout")
def logout(): session.clear(); return redirect("/")

@app.route("/api/login",methods=["POST"])
def api_login():
    d=request.get_json();u=d.get("username","").strip().lower();p=d.get("password","")
    users=ldj(USERS_FILE);user=users.get(u)
    if user and _verify(p,user.get("password","")):
        # Auto-upgrade legacy SHA256 hash to bcrypt on successful login
        if user.get("password","").startswith("$2")==False:
            users[u]["password"]=_h(p);svj(USERS_FILE,users)
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
    # FIX #4: Sanitize tracking number - allow only alphanumeric, dash, underscore
    if not trk or not re.match(r'^[A-Za-z0-9_\-]{1,64}$',trk):
        return jsonify({"ok":False,"error":"Invalid tracking number"})
    sta=re.sub(r'[^A-Za-z0-9_\-]','',sta)[:16] or "S0"
    fn=sta+"_"+trk;now=datetime.now()
    vf=request.files.get("video");vn=None
    if vf:
        if r2:
            # R2 mode: always include timestamp to ensure uniqueness without an existence check
            vn=fn+"_"+now.strftime('%H%M%S')+".webm"
            try:
                r2.upload_fileobj(vf.stream,R2_BUCKET,"videos/"+vn,
                    ExtraArgs={'ContentType':'video/webm'})
            except Exception as e:
                print("R2 video upload failed:",e,flush=True)
                return jsonify({"ok":False,"error":"Storage upload failed"})
        else:
            vn=fn+".webm";vp=os.path.join(VIDEO_DIR,vn)
            if os.path.exists(vp):vn=fn+"_"+now.strftime('%H%M%S')+".webm";vp=os.path.join(VIDEO_DIR,vn)
            vf.save(vp)
    pf=request.files.get("photo");pn=None
    if pf:
        if r2:
            pn=fn+"_"+now.strftime('%H%M%S')+".jpg"
            try:
                r2.upload_fileobj(pf.stream,R2_BUCKET,"photos/"+pn,
                    ExtraArgs={'ContentType':'image/jpeg'})
            except Exception as e:
                print("R2 photo upload failed:",e,flush=True)
                pn=None
        else:
            pn=fn+".jpg";pp=os.path.join(PHOTO_DIR,pn)
            if os.path.exists(pp):pn=fn+"_"+now.strftime('%H%M%S')+".jpg";pp=os.path.join(PHOTO_DIR,pn)
            pf.save(pp)
    with open(LOG_FILE,"a") as f:
        f.write(trk+","+sta+","+now.strftime('%Y-%m-%d')+","+now.strftime('%H:%M:%S')+","+str(dur)+","+str(vn)+","+str(pn)+","+wrk+"\n")
    return jsonify({"ok":True})

@app.route("/api/search/<trk>")
@req_role("admin","cs")
def api_search(trk):
    """Search by tracking number using the CSV log as the index.
    Works identically for R2 and local storage."""
    r={"tracking":trk,"videos":[],"photos":[],"log":[]};t=trk.lower()
    seen_v=set();seen_p=set()
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as cf:
            for row in csv.DictReader(cf):
                if t in row.get("tracking_number","").lower():
                    r["log"].append(row)
                    vf=row.get("video_file","")
                    pf=row.get("photo_file","")
                    if vf and vf!="None" and vf not in seen_v:
                        seen_v.add(vf)
                        s=vf.split("_")[0] if "_" in vf else "?"
                        r["videos"].append({"filename":vf,"url":"/media/video/"+vf,"station":s})
                    if pf and pf!="None" and pf not in seen_p:
                        seen_p.add(pf)
                        s=pf.split("_")[0] if "_" in pf else "?"
                        r["photos"].append({"filename":pf,"url":"/media/photo/"+pf,"station":s})
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
    return ANALYTICS_HTML.replace("__NAME__",session.get("name","")).replace("__ADMIN_VIS__",disp).replace("__NAVBAR__",_navbar("analytics")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

@app.route("/api/users")
@req_role("admin")
def api_users():
    u=ldj(USERS_FILE)
    return jsonify({k:{"name":v["name"],"role":v["role"],"has_badge":bool(v.get("badge_token"))} for k,v in u.items()})

@app.route("/api/users/add",methods=["POST"])
@req_role("admin")
def api_add():
    d=request.get_json();u=d.get("username","").strip().lower();p=d.get("password","")
    n=d.get("name",u);role=d.get("role","worker")
    if not u or not p: return jsonify({"ok":False,"error":"Required"})
    if not re.match(r'^[a-z0-9_\-]{2,32}$',u):
        return jsonify({"ok":False,"error":"Username: lowercase letters, digits, _ -, 2-32 chars"})
    if role not in ("admin","cs","worker"):
        return jsonify({"ok":False,"error":"Invalid role"})
    users=ldj(USERS_FILE)
    if u in users: return jsonify({"ok":False,"error":"Already exists"})
    users[u]={"password":_h(p),"role":role,"name":n}
    # Workers automatically get a badge token for scan-to-login
    if role=="worker":
        users[u]["badge_token"]=_gen_badge_token()
    svj(USERS_FILE,users)
    return jsonify({"ok":True,"badge_token":users[u].get("badge_token")})

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

@app.route("/api/users/badge",methods=["POST"])
@req_role("admin")
def api_badge_regen():
    """Regenerate (or generate first time) a badge token for a worker.
    Use cases: lost badge, leaked token, switching from password to badge auth."""
    d=request.get_json();u=d.get("username","")
    users=ldj(USERS_FILE)
    if u not in users: return jsonify({"ok":False,"error":"User not found"})
    if users[u]["role"]!="worker":
        return jsonify({"ok":False,"error":"Badges are for workers only"})
    users[u]["badge_token"]=_gen_badge_token()
    svj(USERS_FILE,users)
    return jsonify({"ok":True,"badge_token":users[u]["badge_token"]})

@app.route("/api/users/badge/revoke",methods=["POST"])
@req_role("admin")
def api_badge_revoke():
    """Remove a worker's badge token (e.g. employee left). They'll need a password to log in."""
    d=request.get_json();u=d.get("username","")
    users=ldj(USERS_FILE)
    if u not in users: return jsonify({"ok":False,"error":"User not found"})
    if "badge_token" in users[u]: del users[u]["badge_token"]
    svj(USERS_FILE,users)
    return jsonify({"ok":True})

@app.route("/api/badge-login",methods=["POST"])
def api_badge_login():
    """Log in a worker by scanning their badge. No auth required (the token IS the auth)."""
    d=request.get_json() or {}
    token=(d.get("token") or "").strip().upper()
    if not token or not re.match(r'^[A-Z0-9\-]{8,32}$',token):
        return jsonify({"ok":False,"error":"Invalid badge"})
    users=ldj(USERS_FILE)
    matched_u=None
    for u,info in users.items():
        stored=info.get("badge_token","")
        if stored and secrets.compare_digest(stored.upper(),token):
            matched_u=u;break
    if not matched_u:
        # Brief delay to slow down brute force attempts
        time.sleep(0.5)
        return jsonify({"ok":False,"error":"Badge not recognized"})
    user=users[matched_u]
    session["user"]=matched_u;session["role"]=user["role"];session["name"]=user["name"]
    return jsonify({"ok":True,"role":user["role"],"name":user["name"]})

@app.route("/badge-login")
def badge_login_page():
    return BADGE_LOGIN_HTML

@app.route("/users/badges")
@req_role("admin")
def users_badges_page():
    return USERS_BADGES_HTML.replace("__NAME__",session.get("name","")).replace("__NAVBAR__",_navbar("badges")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

@app.route("/api/users/badge/pdf/<u>")
@req_role("admin")
def api_badge_pdf(u):
    """Generate a printable badge PDF for one worker (single label, ID-card sized, ~3.5x2 inches)."""
    users=ldj(USERS_FILE)
    if u not in users: return ("",404)
    info=users[u]
    token=info.get("badge_token")
    if not token: return jsonify({"ok":False,"error":"User has no badge token"}),400
    try:
        from io import BytesIO
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import inch
        import barcode
        from barcode.writer import ImageWriter
        # Generate barcode image (Code 128, scanner-friendly)
        bio=BytesIO()
        bc=barcode.Code128(token,writer=ImageWriter())
        bc.write(bio,options={"module_height":12.0,"module_width":0.4,"font_size":8,"text_distance":3.0,"quiet_zone":3})
        bio.seek(0)
        from reportlab.lib.utils import ImageReader
        img=ImageReader(bio)
        # Build PDF: ID-card sized (3.5x2 inches) on Letter page, centered
        out=BytesIO()
        c=canvas.Canvas(out,pagesize=letter)
        page_w,page_h=letter
        card_w,card_h=3.5*inch,2.0*inch
        x=(page_w-card_w)/2;y=(page_h-card_h)/2
        # Card border
        c.setStrokeColorRGB(0.2,0.2,0.2);c.setLineWidth(1)
        c.rect(x,y,card_w,card_h)
        # Header (top stripe)
        c.setFillColorRGB(0.31,0.27,0.90);c.rect(x,y+card_h-0.4*inch,card_w,0.4*inch,fill=1,stroke=0)
        c.setFillColorRGB(1,1,1);c.setFont("Helvetica-Bold",11)
        c.drawCentredString(x+card_w/2,y+card_h-0.27*inch,"PACKING STATION")
        # Worker name
        c.setFillColorRGB(0,0,0);c.setFont("Helvetica-Bold",16)
        c.drawCentredString(x+card_w/2,y+card_h-0.7*inch,info["name"])
        c.setFont("Helvetica",9);c.setFillColorRGB(0.4,0.4,0.4)
        c.drawCentredString(x+card_w/2,y+card_h-0.88*inch,"@"+u)
        # Barcode image
        c.drawImage(img,x+0.25*inch,y+0.15*inch,width=card_w-0.5*inch,height=0.85*inch,preserveAspectRatio=True,mask='auto')
        c.showPage();c.save()
        out.seek(0)
        return send_file(out,mimetype="application/pdf",download_name="badge_"+u+".pdf",as_attachment=False)
    except Exception as e:
        print("Badge PDF error:",e,flush=True)
        return jsonify({"ok":False,"error":"PDF generation failed: "+str(e)[:100]}),500

@app.route("/api/users/badge/sheet")
@req_role("admin")
def api_badge_sheet():
    """Generate a sheet of badges - all workers with badges, on Avery 5160 layout (30 per page)."""
    try:
        from io import BytesIO
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import inch
        import barcode
        from barcode.writer import ImageWriter
        from reportlab.lib.utils import ImageReader
        users=ldj(USERS_FILE)
        workers=[(u,info) for u,info in users.items() if info.get("badge_token")]
        if not workers:
            return jsonify({"ok":False,"error":"No workers with badges yet"}),400
        # Avery 5160: 30 labels per page, 3 cols x 10 rows
        # Label size: 2.625" x 1.0", with margins
        out=BytesIO()
        c=canvas.Canvas(out,pagesize=letter)
        margin_left=0.1875*inch;margin_top=0.5*inch
        col_w=2.75*inch;row_h=1.0*inch
        col_gap=0.125*inch
        cols=3;rows=10
        idx=0
        for u,info in workers:
            page_idx=idx//(cols*rows)
            local=idx%(cols*rows)
            row=local//cols;col=local%cols
            if local==0 and idx>0: c.showPage()
            x=margin_left+col*(col_w-col_gap+col_gap)
            x=margin_left+col*col_w
            y=letter[1]-margin_top-row_h-row*row_h
            # Generate barcode for this worker
            bio=BytesIO()
            bc=barcode.Code128(info["badge_token"],writer=ImageWriter())
            bc.write(bio,options={"module_height":8.0,"module_width":0.3,"font_size":6,"text_distance":2.0,"quiet_zone":2,"write_text":False})
            bio.seek(0)
            img=ImageReader(bio)
            # Draw label content
            c.setFillColorRGB(0,0,0);c.setFont("Helvetica-Bold",10)
            c.drawString(x+0.1*inch,y+row_h-0.18*inch,info["name"])
            c.setFont("Helvetica",7);c.setFillColorRGB(0.4,0.4,0.4)
            c.drawString(x+0.1*inch,y+row_h-0.32*inch,"@"+u)
            c.drawImage(img,x+0.1*inch,y+0.1*inch,width=col_w-0.2*inch,height=0.5*inch,preserveAspectRatio=True,mask='auto')
            idx+=1
        c.save()
        out.seek(0)
        return send_file(out,mimetype="application/pdf",download_name="badges_avery5160.pdf",as_attachment=False)
    except Exception as e:
        print("Badge sheet error:",e,flush=True)
        return jsonify({"ok":False,"error":"PDF failed: "+str(e)[:100]}),500

@app.route("/api/machine-station",methods=["GET","POST"])
def api_machine_station():
    """GET: read which station this machine is assigned to (from cookie).
    POST (admin only): set the station for this machine - persists in a long-lived cookie."""
    if request.method=="GET":
        sta=request.cookies.get("machine_station","")
        stations=ldj(STATIONS_FILE)
        return jsonify({"station":sta,"station_name":stations.get(sta,""),"all_stations":stations})
    # POST - admin only
    if session.get("role")!="admin":
        return jsonify({"ok":False,"error":"Admin required"}),403
    d=request.get_json() or {}
    sta=(d.get("station") or "").strip()
    stations=ldj(STATIONS_FILE)
    if sta and sta not in stations:
        return jsonify({"ok":False,"error":"Unknown station"})
    resp=jsonify({"ok":True,"station":sta})
    if sta:
        # 10-year cookie tied to this machine
        resp.set_cookie("machine_station",sta,max_age=10*365*24*3600,httponly=False,samesite="Lax",secure=True)
    else:
        resp.delete_cookie("machine_station")
    return resp


@app.route("/api/storage")
@req_role("admin")
def api_storage():
    if r2:
        # R2 mode: list objects with pagination
        vcount=0;vsize=0;pcount=0;psize=0
        oldest=None;newest=None
        try:
            paginator=r2.get_paginator('list_objects_v2')
            for prefix,is_v in [('videos/',True),('photos/',False)]:
                for page in paginator.paginate(Bucket=R2_BUCKET,Prefix=prefix):
                    for obj in page.get('Contents',[]):
                        sz=obj['Size'];mt=obj['LastModified'].timestamp()
                        if is_v: vcount+=1; vsize+=sz
                        else: pcount+=1; psize+=sz
                        if oldest is None or mt<oldest: oldest=mt
                        if newest is None or mt>newest: newest=mt
        except Exception as e:
            print("R2 list failed:",e,flush=True)
            return jsonify({"error":"R2 listing failed","backend":"r2"}),500
        total=(vsize+psize)/(1024*1024)
        return jsonify({
            "videos":vcount,"photos":pcount,
            "video_size_mb":round(vsize/(1024*1024),1),
            "photo_size_mb":round(psize/(1024*1024),1),
            "total_mb":round(total,1),
            "total_gb":round(total/1024,2),
            "retention_days":RETENTION_DAYS,
            "oldest":datetime.fromtimestamp(oldest).strftime('%Y-%m-%d') if oldest else None,
            "newest":datetime.fromtimestamp(newest).strftime('%Y-%m-%d') if newest else None,
            "backend":"r2","bucket":R2_BUCKET
        })
    # Local mode
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
        "newest":datetime.fromtimestamp(newest).strftime('%Y-%m-%d') if newest else None,
        "backend":"local"
    })

@app.route("/api/cleanup",methods=["POST"])
@req_role("admin")
def api_cleanup():
    r=cleanup_old_files()
    return jsonify({"ok":True,"deleted":r["deleted"],"freed_mb":r["freed_mb"]})

@app.route("/media/video/<fn>")
@req_role("admin","cs")
def serve_v(fn):
    # FIX #4: Prevent path traversal - only allow safe filenames
    fn=secure_filename(fn)
    if not fn: return ("",404)
    if r2:
        try:
            url=r2.generate_presigned_url('get_object',
                Params={'Bucket':R2_BUCKET,'Key':'videos/'+fn},
                ExpiresIn=R2_PRESIGN_TTL)
            return redirect(url)
        except Exception as e:
            print("R2 presign failed:",e,flush=True)
            return ("",404)
    p=os.path.join(VIDEO_DIR,fn)
    real=os.path.realpath(p)
    if not real.startswith(os.path.realpath(VIDEO_DIR)+os.sep): return ("",404)
    return send_file(real,mimetype="video/webm") if os.path.exists(real) else ("",404)

@app.route("/media/photo/<fn>")
@req_role("admin","cs")
def serve_p(fn):
    # FIX #4: Prevent path traversal - only allow safe filenames
    fn=secure_filename(fn)
    if not fn: return ("",404)
    if r2:
        try:
            url=r2.generate_presigned_url('get_object',
                Params={'Bucket':R2_BUCKET,'Key':'photos/'+fn},
                ExpiresIn=R2_PRESIGN_TTL)
            return redirect(url)
        except Exception as e:
            print("R2 presign failed:",e,flush=True)
            return ("",404)
    p=os.path.join(PHOTO_DIR,fn)
    real=os.path.realpath(p)
    if not real.startswith(os.path.realpath(PHOTO_DIR)+os.sep): return ("",404)
    return send_file(real,mimetype="image/jpeg") if os.path.exists(real) else ("",404)

# ══════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════
# GIVEAWAY ROUTES (Phase A - manual entry, no AI/Shippo yet)
# ══════════════════════════════════════════════════════════

@app.route("/giveaway")
@req_role("admin","cs")
def giveaway_dashboard():
    return GIVEAWAY_DASH_HTML.replace("__NAME__",session.get("name","")).replace("__NAVBAR__",_navbar("giveaway")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

@app.route("/giveaway/<int:gid>")
@req_role("admin","cs")
def giveaway_detail(gid):
    return GIVEAWAY_DETAIL_HTML.replace("__GID__",str(gid)).replace("__NAME__",session.get("name","")).replace("__NAVBAR__",_navbar("giveaway")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

@app.route("/api/giveaway/list")
@req_role("admin","cs")
def api_giveaway_list():
    """Get all giveaways grouped by status for dashboard."""
    c=gdb()
    rows=c.execute("SELECT * FROM giveaways WHERE status!='cancelled' ORDER BY created_at DESC").fetchall()
    c.close()
    grouped={"pending_address":[],"address_received":[],"label_created":[],"shipped":[]}
    today=datetime.now().strftime('%Y-%m-%d')
    for r in rows:
        d=dict(r)
        # Only show today's shipped on the dashboard to keep it focused
        if d["status"]=="shipped":
            ship_date=(d.get("shipped_at") or "")[:10]
            if ship_date!=today: continue
        if d["status"] in grouped: grouped[d["status"]].append(d)
    return jsonify({"groups":grouped,"brands":GIVEAWAY_BRANDS})

@app.route("/api/giveaway/<int:gid>")
@req_role("admin","cs")
def api_giveaway_get(gid):
    c=gdb()
    r=c.execute("SELECT * FROM giveaways WHERE id=?",(gid,)).fetchone()
    c.close()
    if not r: return jsonify({"ok":False,"error":"Not found"}),404
    return jsonify({"ok":True,"giveaway":dict(r),"brands":GIVEAWAY_BRANDS})

@app.route("/api/giveaway",methods=["POST"])
@req_role("admin","cs")
def api_giveaway_create():
    d=request.get_json() or {}
    winner=(d.get("winner_username") or "").strip().lstrip("@")
    prize=(d.get("prize_name") or "").strip()
    brand=(d.get("brand") or "").strip()
    platform=(d.get("platform") or "tiktok").strip()
    if not winner or not prize:
        return jsonify({"ok":False,"error":"Winner and prize are required"})
    if brand and brand not in GIVEAWAY_BRANDS:
        return jsonify({"ok":False,"error":"Invalid brand"})
    if platform not in ("tiktok","whatnot"):
        return jsonify({"ok":False,"error":"Invalid platform"})
    c=gdb()
    cur=c.execute("""INSERT INTO giveaways(winner_username,prize_name,brand,platform,created_by)
        VALUES(?,?,?,?,?)""",(winner,prize,brand or None,platform,session.get("name","")))
    gid=cur.lastrowid;c.commit();c.close()
    return jsonify({"ok":True,"id":gid})

@app.route("/api/giveaway/<int:gid>/address",methods=["POST"])
@req_role("admin","cs")
def api_giveaway_address(gid):
    """Save address (manual or after AI parse) and advance status."""
    d=request.get_json() or {}
    fields={
        "address_name":(d.get("address_name") or "").strip(),
        "address_street1":(d.get("address_street1") or "").strip(),
        "address_street2":(d.get("address_street2") or "").strip() or None,
        "address_city":(d.get("address_city") or "").strip(),
        "address_state":(d.get("address_state") or "").strip().upper(),
        "address_zip":(d.get("address_zip") or "").strip(),
        "address_country":(d.get("address_country") or "US").strip().upper(),
        "dm_text":(d.get("dm_text") or "").strip() or None,
    }
    # Required fields for shipping
    required=["address_name","address_street1","address_city","address_state","address_zip"]
    missing=[f for f in required if not fields[f]]
    if missing:
        return jsonify({"ok":False,"error":"Missing fields: "+", ".join(missing)})
    # Validate state and zip format (US)
    if fields["address_country"]=="US":
        if not re.match(r'^[A-Z]{2}$',fields["address_state"]):
            return jsonify({"ok":False,"error":"State must be 2-letter code (e.g. FL, NY)"})
        if not re.match(r'^\d{5}(-\d{4})?$',fields["address_zip"]):
            return jsonify({"ok":False,"error":"ZIP must be 5 digits or 5+4"})
    c=gdb()
    sets=", ".join([k+"=?" for k in fields.keys()])
    vals=list(fields.values())
    c.execute("UPDATE giveaways SET "+sets+", status=?, address_received_at=COALESCE(address_received_at,?) WHERE id=?",
        vals+["address_received",datetime.now().isoformat(timespec='seconds'),gid])
    c.commit();c.close()
    return jsonify({"ok":True})

@app.route("/api/giveaway/<int:gid>/ship",methods=["POST"])
@req_role("admin","cs")
def api_giveaway_ship(gid):
    """Mark as shipped (Phase A: manual tracking number entry)."""
    d=request.get_json() or {}
    tracking=(d.get("tracking_number") or "").strip()
    notes=(d.get("notes") or "").strip() or None
    if not tracking:
        return jsonify({"ok":False,"error":"Tracking number is required"})
    if not re.match(r'^[A-Za-z0-9_\- ]{1,64}$',tracking):
        return jsonify({"ok":False,"error":"Invalid tracking format"})
    c=gdb()
    c.execute("UPDATE giveaways SET tracking_number=?, notes=COALESCE(?,notes), status='shipped', shipped_at=? WHERE id=?",
        (tracking,notes,datetime.now().isoformat(timespec='seconds'),gid))
    c.commit();c.close()
    return jsonify({"ok":True})

@app.route("/api/giveaway/<int:gid>/cancel",methods=["POST"])
@req_role("admin","cs")
def api_giveaway_cancel(gid):
    c=gdb()
    c.execute("UPDATE giveaways SET status='cancelled' WHERE id=?",(gid,))
    c.commit();c.close()
    return jsonify({"ok":True})

@app.route("/api/giveaway/<int:gid>/notes",methods=["POST"])
@req_role("admin","cs")
def api_giveaway_notes(gid):
    d=request.get_json() or {}
    notes=(d.get("notes") or "").strip()
    c=gdb()
    c.execute("UPDATE giveaways SET notes=? WHERE id=?",(notes or None,gid))
    c.commit();c.close()
    return jsonify({"ok":True})

@app.route("/api/giveaway/parse-address",methods=["POST"])
@req_role("admin","cs")
def api_giveaway_parse_address():
    """Use Claude AI to extract a structured US shipping address from messy DM text."""
    if not anthropic_client:
        return jsonify({"ok":False,"error":"AI not configured. Add ANTHROPIC_API_KEY to environment."}),503
    d=request.get_json() or {}
    dm_text=(d.get("dm_text") or "").strip()
    if not dm_text:
        return jsonify({"ok":False,"error":"DM text is empty"})
    if len(dm_text)>5000:
        return jsonify({"ok":False,"error":"DM text too long (max 5000 chars)"})
    # Strict prompt: pure JSON output, no commentary, US-only assumption.
    prompt=("Extract a US shipping address from this message. The customer is providing their address "
        "for a giveaway prize. Return ONLY valid JSON (no markdown, no commentary) with these exact keys:\n"
        '{"name":"","street1":"","street2":"","city":"","state":"","zip":"","confidence":"high|medium|low","missing":[]}\n\n'
        "Rules:\n"
        "- name: full recipient name (capitalize properly)\n"
        "- street1: primary street address (number + street name)\n"
        "- street2: apt/suite/unit if present, else empty string\n"
        "- city: city name (capitalize properly)\n"
        "- state: 2-letter US state code (uppercase, e.g. NY, FL, CA)\n"
        "- zip: 5-digit ZIP, or 5+4 format\n"
        "- confidence: 'high' if all required fields clearly present, 'medium' if some are inferred, 'low' if uncertain\n"
        "- missing: array of field names that could not be extracted (e.g. ['street2'] if no apt provided is OK; only include truly missing required fields)\n\n"
        "If a field is genuinely absent or unclear, leave it as empty string and include in 'missing' array.\n"
        "Do NOT invent data. Do NOT add commentary. Output ONLY the JSON object.\n\n"
        "Message:\n"+dm_text)
    try:
        msg=anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role":"user","content":prompt}]
        )
        raw=msg.content[0].text.strip()
        # Strip code fences if Claude added them despite instructions
        if raw.startswith("```"):
            raw=re.sub(r'^```(?:json)?\s*','',raw)
            raw=re.sub(r'\s*```$','',raw)
        parsed=json.loads(raw)
        # Sanitize/normalize
        out={
            "name":(parsed.get("name") or "").strip(),
            "street1":(parsed.get("street1") or "").strip(),
            "street2":(parsed.get("street2") or "").strip(),
            "city":(parsed.get("city") or "").strip(),
            "state":(parsed.get("state") or "").strip().upper()[:2],
            "zip":(parsed.get("zip") or "").strip(),
            "confidence":(parsed.get("confidence") or "low").lower(),
            "missing":parsed.get("missing") or []
        }
        if out["confidence"] not in ("high","medium","low"): out["confidence"]="low"
        return jsonify({"ok":True,"parsed":out})
    except json.JSONDecodeError:
        return jsonify({"ok":False,"error":"AI returned invalid format. Try again or enter manually."})
    except Exception as e:
        print("AI parse failed:",e,flush=True)
        return jsonify({"ok":False,"error":"AI service error: "+str(e)[:100]})

# ══════════════════════════════════════════════════════════
# END GIVEAWAY ROUTES
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
