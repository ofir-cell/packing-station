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
# HTML templates and navbar helper live in templates.py for readability.
from templates import (_navbar, _NAVBAR_CSS, _FONT,
    LOGIN_HTML, STATION_HTML, WORKER_HTML, DASH_HTML, USERS_HTML,
    ANALYTICS_HTML, GIVEAWAY_DASH_HTML, GIVEAWAY_DETAIL_HTML,
    BADGE_LOGIN_HTML, USERS_BADGES_HTML,
    ME_HTML, LEADERBOARD_HTML, HOME_HTML, DOCUMENTS_HTML, WELCOME_HTML,
    ONBOARDING_HTML, ANNOUNCEMENTS_HTML,
    CUSTOMERS_HTML, SHIPMENTS_ADMIN_HTML, SKU_LOOKUP_HTML, SHOWS_HTML, PICK_HTML,
    ISSUES_HTML)


DATA_DIR=os.environ.get("DATA_DIR",os.path.join(os.path.expanduser("~"),"PackingStationData"))
VIDEO_DIR=os.path.join(DATA_DIR,"videos")
PHOTO_DIR=os.path.join(DATA_DIR,"photos")
LOG_FILE=os.path.join(DATA_DIR,"packing_log.csv")
USERS_FILE=os.path.join(DATA_DIR,"users.json")
STATIONS_FILE=os.path.join(DATA_DIR,"stations.json")
DOCS_FILE=os.path.join(DATA_DIR,"documents.json")
DOCS_DIR=os.path.join(DATA_DIR,"documents")
ONB_FILE=os.path.join(DATA_DIR,"onboarding.json")
ANN_FILE=os.path.join(DATA_DIR,"announcements.json")
SHIPMENTS_DB=os.path.join(DATA_DIR,"shipments.db")

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

for d in [DATA_DIR,VIDEO_DIR,PHOTO_DIR,DOCS_DIR]: os.makedirs(d,exist_ok=True)
if not os.path.exists(DOCS_FILE):
    with open(DOCS_FILE,"w") as f: json.dump({},f)
if not os.path.exists(ONB_FILE):
    # Seed with a few common onboarding tasks so new installs aren't empty
    _onb_seed = {
        "tasks": [
            {"id":"ob_safety",     "title":"Watch warehouse safety training",
             "description":"Required 10-minute video covering forklift area, lifting, and emergency exits.",
             "category":"safety",   "required":True,  "created_at":""},
            {"id":"ob_handbook",   "title":"Read & sign the employee handbook",
             "description":"Find it under Documents → Policies.",
             "category":"paperwork","required":True,  "created_at":""},
            {"id":"ob_tour",       "title":"Take the warehouse floor tour",
             "description":"Shift lead will walk you through stations, stockroom, and break area.",
             "category":"intro",    "required":True,  "created_at":""},
            {"id":"ob_packing",    "title":"Shadow an experienced packer for 1 hour",
             "description":"Learn how recordings, tracking scans, and station selection work in practice.",
             "category":"training", "required":True,  "created_at":""},
            {"id":"ob_meet_team",  "title":"Meet your team",
             "description":"Introductions with the rest of the packing crew and management.",
             "category":"intro",    "required":False, "created_at":""},
        ],
        "completions": {}
    }
    with open(ONB_FILE,"w") as f: json.dump(_onb_seed,f,indent=2)
MAX_DOC_SIZE = 50*1024*1024  # 50MB per document

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


# ══════════════════════════════════════════════════════════
# SHIPMENT WEIGHT VERIFICATION — separate SQLite DB
# Imported from Whatnot CSV exports. One row per shipment_id.
# Items in separate table. SKU weights cached for fast lookup.
# ══════════════════════════════════════════════════════════
def sdb():
    """SQLite connection for the shipments DB."""
    c = sqlite3.connect(SHIPMENTS_DB, timeout=10.0)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c

def sdb_init():
    """Create the shipments / items / sku_weights / weight_config tables."""
    c = sdb()
    c.execute("""CREATE TABLE IF NOT EXISTS shipments(
        shipment_id TEXT PRIMARY KEY,
        tracking_code TEXT,
        buyer_username TEXT,
        buyer_name TEXT,
        address_full TEXT,
        postal_code TEXT,
        total_items INTEGER DEFAULT 0,
        expected_weight_g REAL DEFAULT 0,
        actual_weight_g REAL,
        weight_status TEXT,
        weighed_at TEXT,
        weighed_by TEXT,
        packed_at TEXT,
        show_date TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        flag_reason TEXT,
        flag_resolved_at TEXT,
        flag_resolved_by TEXT,
        missing_weights INTEGER DEFAULT 0,
        imported_at TEXT DEFAULT CURRENT_TIMESTAMP,
        platform TEXT DEFAULT 'whatnot',
        import_batch TEXT,
        import_label TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS shipment_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        shipment_id TEXT NOT NULL,
        order_id TEXT,
        sku TEXT,
        product_name TEXT,
        quantity INTEGER DEFAULT 1,
        item_weight_g REAL,
        cancelled INTEGER DEFAULT 0,
        cancel_reason TEXT,
        FOREIGN KEY (shipment_id) REFERENCES shipments(shipment_id) ON DELETE CASCADE
    )""")
    # Backward-compatible migrations — add columns if older DBs are missing them.
    for stmt in (
        "ALTER TABLE shipments ADD COLUMN platform TEXT DEFAULT 'whatnot'",
        "ALTER TABLE shipments ADD COLUMN import_batch TEXT",
        "ALTER TABLE shipments ADD COLUMN import_label TEXT",
        "ALTER TABLE shipments ADD COLUMN picked_at TEXT",
        "ALTER TABLE shipments ADD COLUMN picked_by TEXT",
        "ALTER TABLE shipment_items ADD COLUMN order_id TEXT",
        "ALTER TABLE shipment_items ADD COLUMN cancelled INTEGER DEFAULT 0",
        "ALTER TABLE shipment_items ADD COLUMN cancel_reason TEXT",
        "ALTER TABLE shipment_items ADD COLUMN picked INTEGER DEFAULT 0",
        "ALTER TABLE shipment_items ADD COLUMN picked_at TEXT",
    ):
        try: c.execute(stmt)
        except sqlite3.OperationalError: pass  # column already exists
    c.execute("""CREATE TABLE IF NOT EXISTS sku_weights(
        sku TEXT PRIMARY KEY,
        weight_g REAL NOT NULL,
        last_product_name TEXT,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_by TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS weight_config(
        id INTEGER PRIMARY KEY CHECK (id=1),
        tolerance_percent REAL DEFAULT 10,
        tolerance_absolute_g REAL DEFAULT 5,
        packaging_overhead_g REAL DEFAULT 30,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    # Singleton config row
    c.execute("INSERT OR IGNORE INTO weight_config (id, tolerance_percent, tolerance_absolute_g, packaging_overhead_g) VALUES (1, 10, 5, 30)")
    # Indexes
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_ship_tracking ON shipments(tracking_code) WHERE tracking_code IS NOT NULL")
    c.execute("CREATE INDEX IF NOT EXISTS idx_ship_status ON shipments(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_ship_imported ON shipments(imported_at DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_items_ship ON shipment_items(shipment_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_items_sku ON shipment_items(sku)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_items_order ON shipment_items(order_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_ship_batch ON shipments(import_batch)")
    c.commit(); c.close()

sdb_init()


def _weight_config():
    """Get singleton weight config row."""
    c = sdb()
    row = c.execute("SELECT * FROM weight_config WHERE id=1").fetchone()
    c.close()
    return dict(row) if row else {"tolerance_percent": 10, "tolerance_absolute_g": 5, "packaging_overhead_g": 30}

def _sku_weight(sku):
    """Look up a single SKU's weight in grams. Returns None if unknown."""
    if not sku: return None
    c = sdb()
    row = c.execute("SELECT weight_g FROM sku_weights WHERE sku=?", (sku,)).fetchone()
    c.close()
    return row["weight_g"] if row else None

def _recompute_shipment_weight(conn, shipment_id):
    """Sum item weights × qty + packaging overhead. Updates the shipment row in place.
    Skips cancelled items. Caller passes an open connection."""
    cfg = conn.execute("SELECT packaging_overhead_g FROM weight_config WHERE id=1").fetchone()
    overhead = cfg["packaging_overhead_g"] if cfg else 30
    items = conn.execute("""SELECT quantity, item_weight_g, COALESCE(cancelled,0) AS cancelled
                            FROM shipment_items WHERE shipment_id=?""", (shipment_id,)).fetchall()
    total_g = 0.0
    missing = 0
    total_items = 0
    active_items = 0
    for it in items:
        if it["cancelled"]: continue
        qty = it["quantity"] or 1
        total_items += qty
        active_items += 1
        w = it["item_weight_g"]
        if w is None:
            missing += qty
        else:
            total_g += float(w) * qty
    expected = round(total_g + overhead, 1) if total_g > 0 else 0
    # If every item is cancelled, mark shipment cancelled too
    if active_items == 0 and items:
        conn.execute("""UPDATE shipments SET total_items=0, expected_weight_g=0,
                        missing_weights=0, status='cancelled' WHERE shipment_id=?""", (shipment_id,))
    else:
        conn.execute("""UPDATE shipments SET total_items=?, expected_weight_g=?,
                        missing_weights=? WHERE shipment_id=?""",
                     (total_items, expected, missing, shipment_id))

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


# ══════════════════════════════════════════════════════════
# STATS HELPERS — aggregate packing_log.csv for portal pages
# (Profile, Leaderboard, Packer-of-the-Month, Achievements)
# ══════════════════════════════════════════════════════════

def _read_log():
    """Return all rows from packing_log.csv, or [] if missing."""
    if not os.path.exists(LOG_FILE): return []
    with open(LOG_FILE) as f: return list(csv.DictReader(f))

def _filter_by_window(rows, window='month'):
    """Filter log rows by time window: 'today' | 'week' | 'month' | 'all'.
    'month' uses calendar month; 'week' uses rolling 7 days."""
    if window == 'all': return rows
    now = datetime.now()
    if window == 'today':
        cutoff = now.strftime('%Y-%m-%d')
        return [r for r in rows if r.get('date','') == cutoff]
    if window == 'week':
        cutoff = (now - timedelta(days=7)).strftime('%Y-%m-%d')
        return [r for r in rows if r.get('date','') >= cutoff]
    if window == 'month':
        prefix = now.strftime('%Y-%m')
        return [r for r in rows if r.get('date','').startswith(prefix)]
    return rows

def _aggregate_by_worker(rows):
    """Group rows by worker name. Returns {name: {count, total_dur, avg_dur, days, last_date}}."""
    agg = {}
    for r in rows:
        w = r.get('worker','Unknown') or 'Unknown'
        if w == 'None': w = 'Unknown'
        if w not in agg:
            agg[w] = {'count':0, 'total_dur':0.0, '_dates':set(), 'last_date':''}
        agg[w]['count'] += 1
        try: agg[w]['total_dur'] += float(r.get('duration_seconds',0))
        except: pass
        d = r.get('date','')
        if d:
            agg[w]['_dates'].add(d)
            if d > agg[w]['last_date']: agg[w]['last_date'] = d
    out = {}
    for w,s in agg.items():
        out[w] = {
            'count': s['count'],
            'total_dur': round(s['total_dur'],1),
            'avg_dur': round(s['total_dur']/s['count'],1) if s['count']>0 else 0,
            'days': len(s['_dates']),
            'last_date': s['last_date'],
        }
    return out

def _packer_of_the_month():
    """Top worker by count for the current calendar month, or None if no data."""
    rows = _filter_by_window(_read_log(), 'month')
    if not rows: return None
    agg = _aggregate_by_worker(rows)
    if not agg: return None
    top_name = max(agg.keys(), key=lambda w: agg[w]['count'])
    top = dict(agg[top_name])
    top['name'] = top_name
    return top

def _leaderboard(window='month', limit=10):
    """Top N workers by count in the given window. Adds 'rank' field."""
    rows = _filter_by_window(_read_log(), window)
    agg = _aggregate_by_worker(rows)
    sorted_list = sorted(agg.items(), key=lambda kv: kv[1]['count'], reverse=True)
    return [{'rank': i+1, 'name': name, **stats} for i,(name,stats) in enumerate(sorted_list[:limit])]

def _achievements(worker_name):
    """Compute earned achievements for a worker. Threshold-based + 'Packer of the Month'."""
    rows = _read_log()
    total = sum(1 for r in rows if r.get('worker','') == worker_name)
    badges = [
        {'key':'first',  'label':'First pack',      'emoji':'🎁',  'threshold':1},
        {'key':'100',    'label':'100 packages',    'emoji':'📦',  'threshold':100},
        {'key':'500',    'label':'500 packages',    'emoji':'🚚',  'threshold':500},
        {'key':'1000',   'label':'1,000 packages',  'emoji':'🏆',  'threshold':1000},
        {'key':'5000',   'label':'5,000 packages',  'emoji':'💎',  'threshold':5000},
    ]
    for b in badges:
        b['earned'] = total >= b['threshold']
    potm = _packer_of_the_month()
    if potm and potm.get('name') == worker_name:
        badges.append({'key':'potm','label':'Packer of the Month','emoji':'👑','earned':True})
    return badges

def _doc_id():
    """Short unique document id like 'doc_a3f9k2x1' — easy to debug, ~36 bits."""
    return 'doc_' + secrets.token_hex(4)


# ── Onboarding helpers ──────────────────────────────────────────
def _onb_id():
    return 'ob_' + secrets.token_hex(4)

def _onb_load():
    if not os.path.exists(ONB_FILE): return {"tasks": [], "completions": {}}
    try:
        with open(ONB_FILE) as f: return json.load(f)
    except: return {"tasks": [], "completions": {}}

def _onb_save(d):
    with open(ONB_FILE,"w") as f: json.dump(d,f,indent=2)

def _onb_user_progress(username):
    """Return current user's checklist with done-status per task + totals."""
    data = _onb_load()
    tasks = data.get("tasks", [])
    completions = data.get("completions", {}).get(username, {})
    out_tasks = []
    done_required = 0; total_required = 0
    done_total = 0
    for t in tasks:
        st = completions.get(t["id"], {})
        is_done = bool(st.get("done"))
        out_tasks.append({**t, "done": is_done, "done_at": st.get("done_at","")})
        if t.get("required"):
            total_required += 1
            if is_done: done_required += 1
        if is_done: done_total += 1
    total = len(tasks)
    return {
        "tasks": out_tasks,
        "done_count": done_total,
        "total_count": total,
        "done_required": done_required,
        "total_required": total_required,
        "percent": round(100*done_total/total) if total else 0,
        "required_percent": round(100*done_required/total_required) if total_required else 100,
        "all_required_done": done_required == total_required,
    }

# ── Announcement helpers ────────────────────────────────────────
def _ann_id():
    return 'ann_' + secrets.token_hex(4)

def _ann_load():
    if not os.path.exists(ANN_FILE): return {}
    try:
        with open(ANN_FILE) as f: return json.load(f)
    except: return {}

def _ann_save(d):
    with open(ANN_FILE, "w") as f: json.dump(d, f, indent=2)

def _ann_visible(a, role):
    """Whether this announcement is visible to the current user's role.
    Admin sees everything (for moderation) regardless of audience."""
    if role == 'admin': return True
    aud = a.get('audience', 'all')
    if aud == 'all': return True
    if aud == 'workers': return role == 'worker'
    if aud == 'admin_cs': return role in ('admin', 'cs')
    return False

def _ann_list(role, limit=None):
    """Return announcements visible to role, pinned first then newest first."""
    data = _ann_load()
    items = []
    for aid, a in data.items():
        if _ann_visible(a, role):
            items.append({'id': aid, **a})
    items.sort(key=lambda a: (not a.get('pinned'), -1 * len(a.get('created_at', '')), a.get('created_at', '')), reverse=False)
    # Simpler sort: pinned first (False sorts before True with our trick), then created_at desc
    items.sort(key=lambda a: (0 if a.get('pinned') else 1, a.get('created_at', '')), reverse=False)
    # Actually we want pinned first, and within each group newest first
    pinned = sorted([a for a in items if a.get('pinned')], key=lambda a: a.get('created_at', ''), reverse=True)
    rest = sorted([a for a in items if not a.get('pinned')], key=lambda a: a.get('created_at', ''), reverse=True)
    final = pinned + rest
    if limit: return final[:limit]
    return final


def _onb_team_progress():
    """Admin view: every employee's progress as a list, sorted by completion %."""
    data = _onb_load()
    tasks = data.get("tasks", [])
    total = len(tasks)
    required_ids = {t["id"] for t in tasks if t.get("required")}
    completions = data.get("completions", {})
    users = ldj(USERS_FILE) if os.path.exists(USERS_FILE) else {}
    out = []
    for uname, info in users.items():
        c = completions.get(uname, {})
        done_total = sum(1 for tid,st in c.items() if st.get("done") and any(t["id"]==tid for t in tasks))
        done_required = sum(1 for tid in required_ids if c.get(tid,{}).get("done"))
        out.append({
            "username": uname,
            "name": info.get("name",uname),
            "role": info.get("role",""),
            "done": done_total,
            "total": total,
            "percent": round(100*done_total/total) if total else 0,
            "required_done": done_required,
            "required_total": len(required_ids),
            "complete": done_required == len(required_ids) and len(required_ids) > 0,
        })
    out.sort(key=lambda u: (-u["percent"], u["name"]))
    return out

def _docs_load():
    if not os.path.exists(DOCS_FILE): return {}
    try:
        with open(DOCS_FILE) as f: return json.load(f)
    except: return {}

def _docs_save(d):
    with open(DOCS_FILE, "w") as f: json.dump(d, f, indent=2)

def _doc_visible(doc, user, role):
    """Whether the current user can see this document based on its visibility tag."""
    v = doc.get('visibility', 'all')
    if v == 'all': return True
    if v == 'admin_cs': return role in ('admin', 'cs')
    if v == 'admin': return role == 'admin'
    if v.startswith('personal:'):
        target = v.split(':', 1)[1]
        return target == user or role == 'admin'
    return False


def _worker_summary(worker_name):
    """Full stats bundle for one worker — used by /me and /api/me/stats."""
    rows = _read_log()
    user_rows = [r for r in rows if r.get('worker','') == worker_name]
    def _stats_for(window_rows):
        agg = _aggregate_by_worker(window_rows)
        return agg.get(worker_name, {'count':0,'total_dur':0,'avg_dur':0,'days':0,'last_date':''})
    all_time   = _stats_for(user_rows)
    this_month = _stats_for(_filter_by_window(user_rows, 'month'))
    today_st   = _stats_for(_filter_by_window(user_rows, 'today'))
    # Current rank this month (out of all workers active this month)
    lb_month = _leaderboard('month', 999)
    rank = next((e['rank'] for e in lb_month if e['name'] == worker_name), None)
    # Recent 10 packages (newest first)
    recent = sorted(user_rows, key=lambda r: (r.get('date',''), r.get('time','')), reverse=True)[:10]
    return {
        'name': worker_name,
        'all_time': all_time,
        'this_month': this_month,
        'today': today_st,
        'rank_this_month': rank,
        'total_workers_this_month': len(lb_month),
        'achievements': _achievements(worker_name),
        'recent': recent,
    }


@app.route("/")
def index():
    machine_mode = request.cookies.get("machine_mode", "")
    machine_sta = request.cookies.get("machine_station", "")
    if "user" not in session:
        # Default to badge-login (warehouse stations have no keyboard/mouse).
        # Admins/anyone needing password type can click "Use password instead" → /login
        return redirect("/badge-login")
    # If this machine is dedicated to picking, every logged-in worker/picker goes straight there
    if machine_mode == "pick":
        return redirect("/pick")
    if session.get("role")=="worker":
        # If station already chosen for this session, go to worker page
        if "station" in session:
            return WORKER_HTML.replace("__NAME__",session["name"]).replace("__STATION__",session.get("station_name","")).replace("__SID__",session.get("station","S0"))
        # Auto-assign station from machine cookie if set
        if machine_sta:
            stations=ldj(STATIONS_FILE)
            if machine_sta in stations:
                session["station"]=machine_sta;session["station_name"]=stations[machine_sta]
                return WORKER_HTML.replace("__NAME__",session["name"]).replace("__STATION__",stations[machine_sta]).replace("__SID__",machine_sta)
        # Fallback: manual station picker
        return STATION_HTML.replace("__NAME__",session["name"])
    return redirect("/home")

@app.route("/home")
@req_login
def home_page():
    role = session.get("role", "")
    return (HOME_HTML
        .replace("__ROLE__", role)
        .replace("__NAVBAR__", _navbar("home"))
        .replace("__NAVBAR_CSS__", _NAVBAR_CSS))

@app.route("/welcome")
@req_login
def welcome_page():
    """Post-login choice screen — workers pick between Portal and Packing.
    Non-workers don't pack, so we just send them straight to /home."""
    if session.get("role") != "worker":
        return redirect("/home")
    return WELCOME_HTML.replace("__NAME__", session.get("name", "there"))

@app.route("/pack-start")
@req_role("worker")
def pack_start():
    """Worker chose 'Start Packing' on /welcome — drop them on the regular
    worker flow (station picker or packing screen)."""
    return redirect("/")

@app.route("/dashboard")
@req_role("admin","cs")
def dashboard():
    disp="flex" if session.get("role")=="admin" else "none"
    return DASH_HTML.replace("__NAME__",session.get("name","")).replace("__ADMIN_VIS__",disp).replace("__NAVBAR__",_navbar("dash")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

@app.route("/users")
@req_role("admin")
def users_page(): return USERS_HTML.replace("__NAVBAR__",_navbar("users")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

@app.route("/login")
def login_page():
    """Password login form — fallback for stations without a barcode scanner,
    or admin/CS who don't carry a badge. Default landing is /badge-login."""
    if "user" in session:
        return redirect("/")
    return LOGIN_HTML

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

def _normalize_tracking(s):
    """USPS IMpb barcodes prepend service code + ZIP before the 22-digit tracking.
    Strip the prefix so DB lookups and CSV logs always use the clean 22-digit code."""
    s = (s or "").strip()
    if re.match(r'^\d{23,40}$', s):
        return s[-22:]
    return s

@app.route("/api/upload",methods=["POST"])
@req_login
def api_upload():
    trk=_normalize_tracking(request.form.get("tracking",""))
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


# ══════════════════════════════════════════════════════════
# EMPLOYEE PORTAL ROUTES — /me profile, leaderboard
# ══════════════════════════════════════════════════════════

@app.route("/me")
@req_login
def me_page():
    return (ME_HTML
        .replace("__NAVBAR__", _navbar("me"))
        .replace("__NAVBAR_CSS__", _NAVBAR_CSS))

@app.route("/api/me/stats")
@req_login
def api_me_stats():
    name = session.get("name", "")
    role = session.get("role", "")
    summary = _worker_summary(name)
    summary["role"] = role
    return jsonify(summary)

@app.route("/leaderboard")
@req_login
def leaderboard_page():
    name = session.get("name", "").replace("'", "&#39;")
    return (LEADERBOARD_HTML
        .replace("__ME__", name)
        .replace("__NAVBAR__", _navbar("leaderboard"))
        .replace("__NAVBAR_CSS__", _NAVBAR_CSS))

@app.route("/api/leaderboard")
@req_login
def api_leaderboard():
    window = request.args.get("window", "month")
    if window not in ("today", "week", "month", "all"):
        window = "month"
    return jsonify({"window": window, "leaderboard": _leaderboard(window, 25)})

@app.route("/api/packer-of-month")
@req_login
def api_potm():
    """Compact info for the dashboard widget."""
    p = _packer_of_the_month()
    return jsonify(p or {})


# ══════════════════════════════════════════════════════════
# DOCUMENT LIBRARY — list, upload (admin), download, delete
# ══════════════════════════════════════════════════════════

@app.route("/documents")
@req_login
def documents_page():
    return (DOCUMENTS_HTML
        .replace("__ROLE__", session.get("role", ""))
        .replace("__NAVBAR__", _navbar("documents"))
        .replace("__NAVBAR_CSS__", _NAVBAR_CSS))

@app.route("/api/documents")
@req_login
def api_documents_list():
    user = session.get("user", "")
    role = session.get("role", "")
    docs = _docs_load()
    out = []
    for did, d in docs.items():
        if not _doc_visible(d, user, role): continue
        out.append({
            "id": did,
            "title": d.get("title", ""),
            "description": d.get("description", ""),
            "filename": d.get("filename", ""),
            "category": d.get("category", "other"),
            "visibility": d.get("visibility", "all"),
            "uploaded_by": d.get("uploaded_by", ""),
            "uploaded_at": d.get("uploaded_at", ""),
            "size_bytes": d.get("size_bytes", 0),
        })
    out.sort(key=lambda d: d.get("uploaded_at", ""), reverse=True)
    return jsonify(out)

@app.route("/api/documents/upload", methods=["POST"])
@req_role("admin")
def api_documents_upload():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "Pick a file to upload"})
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    category = request.form.get("category", "other")
    visibility = request.form.get("visibility", "all")
    personal_user = request.form.get("personal_user", "").strip().lower()
    if not title:
        return jsonify({"ok": False, "error": "Title is required"})
    if category not in ("policies", "personal", "onboarding", "other"):
        category = "other"
    if visibility not in ("all", "admin_cs", "admin", "personal"):
        visibility = "all"
    if visibility == "personal":
        if not personal_user:
            return jsonify({"ok": False, "error": "Pick a user for a personal document"})
        users = ldj(USERS_FILE)
        if personal_user not in users:
            return jsonify({"ok": False, "error": "User not found"})
        visibility = "personal:" + personal_user
    fn = secure_filename(f.filename)
    if not fn:
        return jsonify({"ok": False, "error": "Invalid filename"})
    did = _doc_id()
    stored = did + "_" + fn
    if r2:
        try:
            r2.upload_fileobj(f.stream, R2_BUCKET, "documents/" + stored)
            # Get size by HEAD request after upload
            try:
                head = r2.head_object(Bucket=R2_BUCKET, Key="documents/" + stored)
                size = head.get('ContentLength', 0)
            except: size = 0
        except Exception as e:
            print("R2 document upload failed:", e, flush=True)
            return jsonify({"ok": False, "error": "Storage upload failed"})
    else:
        path = os.path.join(DOCS_DIR, stored)
        f.save(path)
        size = os.path.getsize(path)
        if size > MAX_DOC_SIZE:
            os.remove(path)
            return jsonify({"ok": False, "error": "File too large (max 50MB)"})
    docs = _docs_load()
    docs[did] = {
        "filename": fn,
        "stored_filename": stored,
        "title": title,
        "description": description,
        "category": category,
        "visibility": visibility,
        "uploaded_by": session.get("name", "Admin"),
        "uploaded_at": datetime.now().isoformat(timespec='seconds'),
        "size_bytes": size,
    }
    _docs_save(docs)
    return jsonify({"ok": True, "id": did})

@app.route("/documents/dl/<doc_id>")
@req_login
def documents_download(doc_id):
    if not re.match(r'^doc_[a-f0-9]{8}$', doc_id):
        return "Invalid id", 400
    user = session.get("user", "")
    role = session.get("role", "")
    docs = _docs_load()
    d = docs.get(doc_id)
    if not d: return "Not found", 404
    if not _doc_visible(d, user, role): return "Access denied", 403
    stored = d.get("stored_filename", "")
    if not stored: return "File missing", 404
    if r2:
        try:
            url = r2.generate_presigned_url('get_object',
                Params={'Bucket': R2_BUCKET, 'Key': 'documents/' + stored,
                        'ResponseContentDisposition': 'attachment; filename="' + d.get('filename','file') + '"'},
                ExpiresIn=R2_PRESIGN_TTL)
            return redirect(url)
        except Exception as e:
            print("R2 doc presign failed:", e, flush=True)
            return "Download error", 500
    else:
        path = os.path.join(DOCS_DIR, stored)
        # Path traversal guard
        rp = os.path.realpath(path)
        if not rp.startswith(os.path.realpath(DOCS_DIR) + os.sep):
            return "Bad path", 400
        if not os.path.exists(rp): return "File missing", 404
        return send_file(rp, as_attachment=True, download_name=d.get('filename', 'file'))

# ══════════════════════════════════════════════════════════
# ONBOARDING CHECKLIST — for new hires
# ══════════════════════════════════════════════════════════

@app.route("/onboarding")
@req_login
def onboarding_page():
    return (ONBOARDING_HTML
        .replace("__ROLE__", session.get("role", ""))
        .replace("__NAVBAR__", _navbar("onboarding"))
        .replace("__NAVBAR_CSS__", _NAVBAR_CSS))

@app.route("/api/onboarding/me")
@req_login
def api_onb_me():
    return jsonify(_onb_user_progress(session.get("user", "")))

@app.route("/api/onboarding/toggle", methods=["POST"])
@req_login
def api_onb_toggle():
    d = request.get_json() or {}
    task_id = d.get("task_id", "")
    if not re.match(r'^ob_[a-zA-Z0-9_]{1,32}$', task_id):
        return jsonify({"ok": False, "error": "Invalid task id"})
    data = _onb_load()
    if not any(t["id"] == task_id for t in data.get("tasks", [])):
        return jsonify({"ok": False, "error": "Task not found"})
    user = session.get("user", "")
    completions = data.setdefault("completions", {})
    user_c = completions.setdefault(user, {})
    cur = user_c.get(task_id, {}).get("done", False)
    if cur:
        user_c[task_id] = {"done": False}
    else:
        user_c[task_id] = {"done": True, "done_at": datetime.now().isoformat(timespec='seconds')}
    _onb_save(data)
    return jsonify({"ok": True, "done": user_c[task_id]["done"]})

@app.route("/api/onboarding/tasks/add", methods=["POST"])
@req_role("admin")
def api_onb_add():
    d = request.get_json() or {}
    title = (d.get("title") or "").strip()
    description = (d.get("description") or "").strip()
    category = d.get("category", "other")
    required = bool(d.get("required", True))
    if not title: return jsonify({"ok": False, "error": "Title required"})
    if category not in ("safety", "paperwork", "training", "intro", "other"):
        category = "other"
    data = _onb_load()
    new_task = {
        "id": _onb_id(),
        "title": title,
        "description": description,
        "category": category,
        "required": required,
        "created_at": datetime.now().isoformat(timespec='seconds'),
    }
    data.setdefault("tasks", []).append(new_task)
    _onb_save(data)
    return jsonify({"ok": True, "task": new_task})

@app.route("/api/onboarding/tasks/<task_id>/delete", methods=["POST"])
@req_role("admin")
def api_onb_delete(task_id):
    if not re.match(r'^ob_[a-zA-Z0-9_]{1,32}$', task_id):
        return jsonify({"ok": False, "error": "Invalid id"})
    data = _onb_load()
    before = len(data.get("tasks", []))
    data["tasks"] = [t for t in data.get("tasks", []) if t["id"] != task_id]
    if len(data["tasks"]) == before:
        return jsonify({"ok": False, "error": "Task not found"})
    # Also clean up completions for the deleted task
    for u, c in data.get("completions", {}).items():
        c.pop(task_id, None)
    _onb_save(data)
    return jsonify({"ok": True})

@app.route("/api/onboarding/team")
@req_role("admin")
def api_onb_team():
    return jsonify(_onb_team_progress())

@app.route("/api/onboarding/reset/<username>", methods=["POST"])
@req_role("admin")
def api_onb_reset(username):
    if not re.match(r'^[a-z0-9_\-]+$', username):
        return jsonify({"ok": False, "error": "Invalid username"})
    data = _onb_load()
    data.get("completions", {}).pop(username, None)
    _onb_save(data)
    return jsonify({"ok": True})


# ══════════════════════════════════════════════════════════
# ANNOUNCEMENTS — admin broadcasts to the team
# ══════════════════════════════════════════════════════════

@app.route("/announcements")
@req_login
def announcements_page():
    return (ANNOUNCEMENTS_HTML
        .replace("__ROLE__", session.get("role", ""))
        .replace("__NAVBAR__", _navbar("announcements"))
        .replace("__NAVBAR_CSS__", _NAVBAR_CSS))

@app.route("/api/announcements")
@req_login
def api_ann_list():
    role = session.get("role", "")
    limit = request.args.get("limit", type=int)
    return jsonify(_ann_list(role, limit=limit))

@app.route("/api/announcements/create", methods=["POST"])
@req_role("admin")
def api_ann_create():
    d = request.get_json() or {}
    title = (d.get("title") or "").strip()
    body = (d.get("body") or "").strip()
    priority = d.get("priority", "info")
    audience = d.get("audience", "all")
    pinned = bool(d.get("pinned", False))
    if not title:
        return jsonify({"ok": False, "error": "Title is required"})
    if len(title) > 120:
        return jsonify({"ok": False, "error": "Title too long (max 120 chars)"})
    if len(body) > 5000:
        return jsonify({"ok": False, "error": "Body too long (max 5000 chars)"})
    if priority not in ("info", "important", "urgent"): priority = "info"
    if audience not in ("all", "workers", "admin_cs"): audience = "all"
    data = _ann_load()
    aid = _ann_id()
    data[aid] = {
        "title": title,
        "body": body,
        "priority": priority,
        "audience": audience,
        "pinned": pinned,
        "author": session.get("name", "Admin"),
        "created_at": datetime.now().isoformat(timespec='seconds'),
    }
    _ann_save(data)
    return jsonify({"ok": True, "id": aid})

@app.route("/api/announcements/<aid>/delete", methods=["POST"])
@req_role("admin")
def api_ann_delete(aid):
    if not re.match(r'^ann_[a-f0-9]{8}$', aid):
        return jsonify({"ok": False, "error": "Invalid id"})
    data = _ann_load()
    if aid not in data:
        return jsonify({"ok": False, "error": "Not found"})
    del data[aid]
    _ann_save(data)
    return jsonify({"ok": True})

@app.route("/api/announcements/<aid>/pin", methods=["POST"])
@req_role("admin")
def api_ann_pin(aid):
    if not re.match(r'^ann_[a-f0-9]{8}$', aid):
        return jsonify({"ok": False, "error": "Invalid id"})
    data = _ann_load()
    if aid not in data:
        return jsonify({"ok": False, "error": "Not found"})
    data[aid]['pinned'] = not data[aid].get('pinned', False)
    _ann_save(data)
    return jsonify({"ok": True, "pinned": data[aid]['pinned']})


# ══════════════════════════════════════════════════════════
# WEIGHT VERIFICATION — Whatnot CSV import + SKU weights + lookup
# ══════════════════════════════════════════════════════════

def _parse_buyer_name(addr):
    """The Whatnot shipping_address column is comma-separated; first chunk is the name."""
    if not addr: return ""
    return addr.split(",", 1)[0].strip()

def _detect_csv_format(fieldnames):
    """Return 'tiktok_ship' | 'tiktok_cancel' | 'whatnot' | None.
    Cancellation files have the same TikTok columns; distinguish later by Order Status data."""
    fn = set(fieldnames or [])
    if {"Order ID", "Tracking ID", "Package ID", "Seller SKU"}.issubset(fn):
        return "tiktok"  # tiktok_ship or tiktok_cancel — caller checks row data
    if {"order_id", "shipment_id", "product_name", "product_quantity"}.issubset(fn):
        return "whatnot"
    return None

def _norm_tiktok(row):
    """Normalize a TikTok row to common dict. TikTok appends a TAB to many ID fields
    (`Package ID`, `Tracking ID`) — strip whitespace and tabs."""
    def s(k): return (row.get(k) or "").strip().strip("\t")
    addr_parts = [s("Address Line 1"), s("Address Line 2"), s("City"), s("State"),
                  s("Zipcode"), s("Country")]
    address = ", ".join(p for p in addr_parts if p)
    try: qty = int(float(s("Quantity") or "1"))
    except: qty = 1
    try: weight_g = round(float(s("Weight(kg)") or "0") * 1000, 1)  # kg → grams
    except: weight_g = 0
    return {
        "order_id":   s("Order ID"),
        "package_id": s("Package ID"),
        "tracking":   s("Tracking ID"),
        "sku":        s("Seller SKU"),
        "product_name": s("Product Name"),
        "quantity":   qty,
        "weight_g":   weight_g,
        "buyer_username": s("Buyer Username"),
        "buyer_name":     s("Recipient") or s("Buyer Nickname"),
        "address":    address,
        "postal":     s("Zipcode"),
        "status":     s("Order Status"),
        "cancel_reason": s("Cancel Reason"),
        "created_at": s("Created Time")[:10],
    }

def _norm_whatnot(row):
    """Normalize a Whatnot row to the same dict shape."""
    def s(k): return (row.get(k) or "").strip()
    pname = s("product_name")
    try: qty = int(float(s("product_quantity") or "1"))
    except: qty = 1
    return {
        "order_id":   s("order_id"),
        "package_id": s("shipment_id"),
        "tracking":   s("tracking_code"),
        "sku":        s("sku") or pname,   # Whatnot live items have empty SKU
        "product_name": pname,
        "quantity":   qty,
        "weight_g":   0,                    # Whatnot doesn't provide per-row weight
        "buyer_username": s("buyer_username"),
        "buyer_name": _parse_buyer_name(s("shipping_address")),
        "address":    s("shipping_address"),
        "postal":     s("postal_code"),
        "status":     "cancelled" if s("cancelled_or_failed") in ("cancelled","failed") else "to_ship",
        "cancel_reason": s("cancelled_or_failed") if s("cancelled_or_failed") else "",
        "created_at": s("placed_at")[:10],
    }

@app.route("/api/shipments/import", methods=["POST"])
@req_role("admin")
def api_shipments_import():
    """Accept a TikTok or Whatnot CSV upload and ingest into the shipments DB.
    Auto-detects format. Cancelled rows from a TO SHIP file are marked cancelled.
    A pure cancellation file is detected and routed through the cancel path."""
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "Pick a CSV file"})
    if not f.filename.lower().endswith(".csv"):
        return jsonify({"ok": False, "error": "Must be a .csv file"})
    label = (request.form.get("label") or "").strip()
    if not label:
        return jsonify({"ok": False, "error": "Show name is required — name it after the live show (e.g. 'Beauty 5/15 — TikTok')"})
    if len(label) > 80:
        return jsonify({"ok": False, "error": "Show name too long (max 80 characters)"})
    try:
        raw = f.stream.read().decode("utf-8-sig", errors="replace")
    except Exception as e:
        return jsonify({"ok": False, "error": "Could not read file: " + str(e)})
    import io
    reader = csv.DictReader(io.StringIO(raw))
    fmt = _detect_csv_format(reader.fieldnames)
    if not fmt:
        return jsonify({"ok": False, "error": "Unrecognized CSV format — expected TikTok or Whatnot export"})

    rows = list(reader)
    if not rows:
        return jsonify({"ok": False, "error": "CSV is empty"})

    # Normalize all rows to common shape
    if fmt == "tiktok":
        norm = [_norm_tiktok(r) for r in rows]
        # Detect if this is purely a cancel file — TikTok cancel export has empty package_id
        # on every row and Order Status starts with "Cancel"
        cancel_count = sum(1 for n in norm if n["status"].lower().startswith("cancel"))
        no_pkg = sum(1 for n in norm if not n["package_id"])
        is_cancel_file = (cancel_count / len(norm) > 0.8) and (no_pkg / len(norm) > 0.8)
        if is_cancel_file:
            return _process_cancel_file(norm, "tiktok", label)
        platform = "tiktok"
    else:
        norm = [_norm_whatnot(r) for r in rows]
        platform = "whatnot"

    # Group rows by package_id (Whatnot uses shipment_id, TikTok uses Package ID)
    import_batch = "imp_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    by_pkg = {}
    skipped = 0
    cancelled_inline = []  # cancelled rows in a TO SHIP file (rare)
    for n in norm:
        pkg = n["package_id"]
        if not pkg:
            skipped += 1
            continue
        if n["status"].lower().startswith("cancel"):
            cancelled_inline.append(n)
            continue
        by_pkg.setdefault(pkg, []).append(n)

    if not by_pkg:
        return jsonify({"ok": False, "error": "No usable shipments found in CSV (all rows skipped or cancelled)"})

    c = sdb()
    sku_map = {r["sku"]: r["weight_g"] for r in c.execute("SELECT sku, weight_g FROM sku_weights").fetchall()}

    inserted = 0; updated = 0; items_inserted = 0
    unique_skus = set()
    try:
        for pkg_id, group in by_pkg.items():
            first = group[0]
            tracking = first["tracking"] or None
            existing = c.execute("SELECT shipment_id FROM shipments WHERE shipment_id=?", (pkg_id,)).fetchone()
            if existing:
                c.execute("""UPDATE shipments
                             SET tracking_code=COALESCE(?,tracking_code),
                                 buyer_username=?, buyer_name=?, address_full=?, postal_code=?,
                                 show_date=?, platform=?, import_batch=COALESCE(import_batch,?),
                                 import_label=COALESCE(import_label,?)
                             WHERE shipment_id=?""",
                          (tracking, first["buyer_username"], first["buyer_name"],
                           first["address"], first["postal"], first["created_at"],
                           platform, import_batch, label, pkg_id))
                updated += 1
            else:
                c.execute("""INSERT INTO shipments
                    (shipment_id, tracking_code, buyer_username, buyer_name, address_full,
                     postal_code, show_date, status, platform, import_batch, import_label)
                    VALUES (?,?,?,?,?,?,?, 'pending', ?, ?, ?)""",
                    (pkg_id, tracking, first["buyer_username"], first["buyer_name"],
                     first["address"], first["postal"], first["created_at"],
                     platform, import_batch, label))
                inserted += 1
            # Replace items for this shipment
            c.execute("DELETE FROM shipment_items WHERE shipment_id=?", (pkg_id,))
            for n in group:
                sku = n["sku"]
                # Prefer per-row weight from CSV (TikTok); fall back to sku_weights map
                w = (n["weight_g"] / max(len(group), 1)) if n["weight_g"] > 0 else sku_map.get(sku)
                c.execute("""INSERT INTO shipment_items
                             (shipment_id, order_id, sku, product_name, quantity, item_weight_g)
                             VALUES (?,?,?,?,?,?)""",
                          (pkg_id, n["order_id"], sku, n["product_name"], n["quantity"], w))
                items_inserted += 1
                if sku: unique_skus.add(sku)
            _recompute_shipment_weight(c, pkg_id)
        c.commit()
    finally:
        c.close()

    # SKUs missing weights
    c = sdb()
    have_weight = {r["sku"] for r in c.execute("SELECT sku FROM sku_weights WHERE sku IN ({})".format(
        ",".join("?"*len(unique_skus)) or "''"), tuple(unique_skus) if unique_skus else ()).fetchall()}
    c.close()
    sku_missing = sorted(unique_skus - have_weight)

    return jsonify({
        "ok": True,
        "format": fmt,
        "platform": platform,
        "import_batch": import_batch,
        "label": label,
        "shipments_new": inserted,
        "shipments_updated": updated,
        "items": items_inserted,
        "skipped_rows": skipped,
        "cancelled_inline": len(cancelled_inline),
        "unique_skus": len(unique_skus),
        "skus_missing_weight": len(sku_missing),
        "missing_sku_list": sku_missing[:50],
    })


def _process_cancel_file(norm_rows, source, label):
    """A pure cancellation file from TikTok lists orders that were canceled BEFORE the
    To-Ship export. They never enter the normal shipment flow, so we (a) try to update
    existing matching shipments, AND (b) insert standalone cancelled rows so the SKU
    reconciliation screen can find them. Both code paths are idempotent."""
    c = sdb()
    import_batch = "cancel_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    matched_existing = 0
    inserted_new = 0
    affected_ships = set()
    # Group by order_id to combine multiple SKUs per cancelled order
    by_order = {}
    for n in norm_rows:
        if not n["order_id"]: continue
        by_order.setdefault(n["order_id"], []).append(n)

    for oid, group in by_order.items():
        first = group[0]
        reason = first["cancel_reason"] or "cancelled"
        # Path A: this order is already in our shipments (was in a previous To-Ship)
        existing = c.execute("SELECT DISTINCT shipment_id FROM shipment_items WHERE order_id=?", (oid,)).fetchall()
        if existing:
            c.execute("""UPDATE shipment_items SET cancelled=1, cancel_reason=?
                         WHERE order_id=? AND COALESCE(cancelled,0)=0""", (reason, oid))
            matched_existing += 1
            for r in existing: affected_ships.add(r["shipment_id"])
            continue
        # Path B: never seen — insert a synthetic shipment so reconciliation can find it
        synthetic_id = "cancel_" + oid
        c.execute("""INSERT OR REPLACE INTO shipments
            (shipment_id, tracking_code, buyer_username, buyer_name, address_full,
             postal_code, show_date, status, platform, import_batch, import_label,
             total_items, expected_weight_g, missing_weights, flag_reason)
            VALUES (?, NULL, ?, ?, ?, ?, ?, 'cancelled', ?, ?, ?, 0, 0, 0, ?)""",
            (synthetic_id, first["buyer_username"], first["buyer_name"], first["address"],
             first["postal"], first["created_at"], source, import_batch, label, reason))
        c.execute("DELETE FROM shipment_items WHERE shipment_id=?", (synthetic_id,))
        for n in group:
            c.execute("""INSERT INTO shipment_items
                         (shipment_id, order_id, sku, product_name, quantity, item_weight_g,
                          cancelled, cancel_reason)
                         VALUES (?,?,?,?,?,?, 1, ?)""",
                      (synthetic_id, oid, n["sku"], n["product_name"], n["quantity"],
                       n["weight_g"] or None, reason))
        inserted_new += 1

    for sid in affected_ships:
        _recompute_shipment_weight(c, sid)
    c.commit(); c.close()
    return jsonify({
        "ok": True,
        "format": "cancellation",
        "source": source,
        "label": label,
        "import_batch": import_batch,
        "orders_matched_existing": matched_existing,
        "orders_inserted_as_cancelled": inserted_new,
        "shipments_recomputed": len(affected_ships),
    })


@app.route("/api/shipments/recent")
@req_role("admin","cs")
def api_shipments_recent():
    """List most-recently-imported shipments. Optionally filter by show name."""
    limit = min(request.args.get("limit", type=int) or 200, 500)
    show = (request.args.get("show") or "").strip()
    c = sdb()
    if show:
        rows = c.execute("""SELECT shipment_id, tracking_code, buyer_username, buyer_name,
                                   total_items, expected_weight_g, actual_weight_g, weight_status,
                                   status, missing_weights, show_date, imported_at, import_label, platform
                            FROM shipments WHERE import_label=?
                            ORDER BY imported_at DESC LIMIT ?""", (show, limit)).fetchall()
    else:
        rows = c.execute("""SELECT shipment_id, tracking_code, buyer_username, buyer_name,
                                   total_items, expected_weight_g, actual_weight_g, weight_status,
                                   status, missing_weights, show_date, imported_at, import_label, platform
                            FROM shipments ORDER BY imported_at DESC LIMIT ?""", (limit,)).fetchall()
    c.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/shipment/<code>")
@req_login
def api_shipment_lookup(code):
    """Look up a single shipment by tracking_code OR shipment_id.
    Used by worker page when a barcode is scanned.
    First normalizes USPS IMpb barcodes (23-40 digit numeric → last 22 digits),
    then tries exact match, then substring match as a safety net."""
    code = _normalize_tracking(code or "")
    if not re.match(r'^[A-Za-z0-9_\-]{1,64}$', code):
        return jsonify({"ok": False, "error": "Invalid code"})
    c = sdb()
    # 1) Exact match
    row = c.execute("""SELECT * FROM shipments
                       WHERE tracking_code=? OR shipment_id=? LIMIT 1""", (code, code)).fetchone()
    # 2) Stored tracking is a SUBSTRING of the scanned code (USPS prefix case)
    if not row and len(code) > 10:
        row = c.execute("""SELECT * FROM shipments
                           WHERE tracking_code IS NOT NULL
                             AND length(tracking_code) >= 10
                             AND ? LIKE '%' || tracking_code || '%'
                           LIMIT 1""", (code,)).fetchone()
    # 3) Scanned is a substring of stored — handles rare truncation
    if not row and len(code) >= 10:
        row = c.execute("""SELECT * FROM shipments
                           WHERE tracking_code IS NOT NULL
                             AND tracking_code LIKE '%' || ? || '%'
                           LIMIT 1""", (code,)).fetchone()
    if not row:
        c.close()
        return jsonify({"ok": False, "error": "Shipment not found"})
    items = c.execute("""SELECT sku, product_name, quantity, item_weight_g
                         FROM shipment_items WHERE shipment_id=?""", (row["shipment_id"],)).fetchall()
    cfg = c.execute("SELECT * FROM weight_config WHERE id=1").fetchone()
    c.close()
    return jsonify({
        "ok": True,
        "shipment": dict(row),
        "items": [dict(i) for i in items],
        "config": dict(cfg) if cfg else {},
    })


@app.route("/api/sku-weights")
@req_role("admin")
def api_sku_weights_list():
    """All SKUs we've ever imported, with current weight (if set) and times seen."""
    c = sdb()
    # SKUs from items + their assigned weight + frequency
    rows = c.execute("""
        SELECT i.sku,
               MAX(i.product_name) AS last_product_name,
               COUNT(DISTINCT i.shipment_id) AS shipments,
               SUM(i.quantity) AS total_qty,
               sw.weight_g,
               sw.updated_at,
               sw.updated_by
        FROM shipment_items i
        LEFT JOIN sku_weights sw ON sw.sku = i.sku
        WHERE i.sku IS NOT NULL AND i.sku != ''
        GROUP BY i.sku
        ORDER BY (sw.weight_g IS NULL) DESC, shipments DESC
    """).fetchall()
    c.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/sku-weights/set", methods=["POST"])
@req_role("admin")
def api_sku_weight_set():
    """Insert or update a SKU's weight in grams."""
    d = request.get_json() or {}
    sku = (d.get("sku") or "").strip()
    try:
        weight = float(d.get("weight_g", 0))
    except:
        return jsonify({"ok": False, "error": "Weight must be a number"})
    if not sku:
        return jsonify({"ok": False, "error": "SKU required"})
    if weight <= 0 or weight > 100000:
        return jsonify({"ok": False, "error": "Weight must be 0 < w <= 100000 grams"})
    c = sdb()
    pname = c.execute("SELECT product_name FROM shipment_items WHERE sku=? ORDER BY id DESC LIMIT 1",
                      (sku,)).fetchone()
    pname = pname["product_name"] if pname else None
    c.execute("""INSERT INTO sku_weights (sku, weight_g, last_product_name, updated_at, updated_by)
                 VALUES (?,?,?,CURRENT_TIMESTAMP,?)
                 ON CONFLICT(sku) DO UPDATE SET
                   weight_g=excluded.weight_g,
                   last_product_name=excluded.last_product_name,
                   updated_at=CURRENT_TIMESTAMP,
                   updated_by=excluded.updated_by""",
              (sku, weight, pname, session.get("name", "Admin")))
    # Push the new weight into existing shipment_items snapshots and recompute their shipments
    affected = c.execute("SELECT DISTINCT shipment_id FROM shipment_items WHERE sku=?", (sku,)).fetchall()
    c.execute("UPDATE shipment_items SET item_weight_g=? WHERE sku=?", (weight, sku))
    for r in affected:
        _recompute_shipment_weight(c, r["shipment_id"])
    c.commit(); c.close()
    return jsonify({"ok": True, "shipments_updated": len(affected)})


# ══════════════════════════════════════════════════════════
# CUSTOMER SEARCH — for CS lookups across all imported shipments
# ══════════════════════════════════════════════════════════

@app.route("/customers")
@req_role("admin", "cs")
def customers_page():
    return (CUSTOMERS_HTML
        .replace("__ROLE__", session.get("role", ""))
        .replace("__NAVBAR__", _navbar("customers"))
        .replace("__NAVBAR_CSS__", _NAVBAR_CSS))

@app.route("/api/customers/search")
@req_role("admin", "cs")
def api_customers_search():
    """Fuzzy search across buyer_username and buyer_name. Min 2 chars."""
    q = (request.args.get("q") or "").strip().lower()
    if len(q) < 2:
        return jsonify([])
    c = sdb()
    rows = c.execute("""
        SELECT buyer_username,
               MAX(buyer_name) AS buyer_name,
               COUNT(*) AS shipments,
               COALESCE(SUM(total_items), 0) AS total_items,
               MAX(show_date) AS last_show,
               MAX(address_full) AS last_address,
               MAX(postal_code) AS last_postal
        FROM shipments
        WHERE buyer_username != '' AND
              (LOWER(buyer_username) LIKE ? OR LOWER(buyer_name) LIKE ?)
        GROUP BY buyer_username
        ORDER BY shipments DESC, last_show DESC
        LIMIT 50
    """, ('%' + q + '%', '%' + q + '%')).fetchall()
    c.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/customers/<username>")
@req_role("admin", "cs")
def api_customer_detail(username):
    """Full profile: every shipment, items, recordings (cross-reference with packing_log.csv)."""
    if not re.match(r'^[a-zA-Z0-9._\-]+$', username) or len(username) > 64:
        return jsonify({"ok": False, "error": "Invalid username"})
    c = sdb()
    ships = c.execute("""
        SELECT * FROM shipments WHERE buyer_username=? ORDER BY show_date DESC, shipment_id DESC
    """, (username,)).fetchall()
    if not ships:
        c.close()
        return jsonify({"ok": False, "error": "Customer not found"})
    ship_ids = {s["shipment_id"] for s in ships}
    tracking_codes = {s["tracking_code"] for s in ships if s["tracking_code"]}
    ships_out = []
    for s in ships:
        items = c.execute("""SELECT product_name, quantity, item_weight_g, sku
                             FROM shipment_items WHERE shipment_id=?""", (s["shipment_id"],)).fetchall()
        ships_out.append({**dict(s), "items": [dict(i) for i in items]})
    c.close()
    # Cross-reference with packing_log.csv to find recordings
    recordings = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f:
            for row in csv.DictReader(f):
                t = row.get("tracking_number", "")
                if t and (t in ship_ids or t in tracking_codes):
                    recordings.append({
                        "tracking": t,
                        "station": row.get("station", ""),
                        "date": row.get("date", ""),
                        "time": row.get("time", ""),
                        "duration": row.get("duration_seconds", ""),
                        "video_file": row.get("video_file", ""),
                        "photo_file": row.get("photo_file", ""),
                        "worker": row.get("worker", ""),
                    })
    # Summary
    addresses = list(set(s["address_full"] for s in ships if s["address_full"]))
    shows = sorted(set(s["show_date"] for s in ships if s["show_date"]), reverse=True)
    return jsonify({
        "ok": True,
        "username": username,
        "buyer_name": ships[0]["buyer_name"],
        "shipments_total": len(ships),
        "items_total": sum((s["total_items"] or 0) for s in ships),
        "shows_count": len(shows),
        "first_show": shows[-1] if shows else None,
        "last_show": shows[0] if shows else None,
        "addresses": addresses,
        "shipments": ships_out,
        "recordings": recordings,
    })


# ══════════════════════════════════════════════════════════
# PICKING — pickers (iPad workflow) collect items from tables BEFORE the
# packer scans + records. Separates the "find items" step from the "verify
# + film + ship" step so the two roles don't bottleneck each other.
# ══════════════════════════════════════════════════════════

@app.route("/pick")
@req_role("picker", "worker", "admin", "cs")
def pick_page():
    return (PICK_HTML
        .replace("__ROLE__", session.get("role", ""))
        .replace("__NAME__", session.get("name", ""))
        .replace("__STATION__", session.get("station_name", "")))

@app.route("/api/pick/queue")
@req_role("picker", "worker", "admin", "cs")
def api_pick_queue():
    """List shipments still waiting to be picked. Optional filters by show name
    or platform. Excludes cancelled and already-picked shipments."""
    show = (request.args.get("show") or "").strip()
    c = sdb()
    q = """SELECT s.shipment_id, s.tracking_code, s.buyer_name, s.buyer_username,
                  s.import_label, s.platform, s.show_date,
                  (SELECT COUNT(*) FROM shipment_items i WHERE i.shipment_id=s.shipment_id
                   AND COALESCE(i.cancelled,0)=0) AS item_count
           FROM shipments s
           WHERE s.status='pending'"""
    params = []
    if show:
        q += " AND s.import_label=?"
        params.append(show)
    q += " ORDER BY s.imported_at DESC LIMIT 200"
    rows = c.execute(q, params).fetchall()
    c.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/pick/<sid>")
@req_role("picker", "worker", "admin", "cs")
def api_pick_get(sid):
    """Detail for picking — items with picked flag for tap-to-check workflow."""
    if not re.match(r'^[A-Za-z0-9_\-]{1,64}$', sid):
        return jsonify({"ok": False, "error": "Invalid id"})
    c = sdb()
    s = c.execute("SELECT * FROM shipments WHERE shipment_id=?", (sid,)).fetchone()
    if not s:
        c.close()
        return jsonify({"ok": False, "error": "Shipment not found"})
    items = c.execute("""SELECT id, sku, product_name, quantity, COALESCE(picked,0) AS picked,
                                picked_at, COALESCE(cancelled,0) AS cancelled
                         FROM shipment_items WHERE shipment_id=?
                         ORDER BY COALESCE(cancelled,0), COALESCE(picked,0), id""", (sid,)).fetchall()
    c.close()
    return jsonify({"ok": True, "shipment": dict(s), "items": [dict(i) for i in items]})

@app.route("/api/pick/item/<int:item_id>/toggle", methods=["POST"])
@req_role("picker", "worker", "admin", "cs")
def api_pick_item_toggle(item_id):
    c = sdb()
    row = c.execute("SELECT id, COALESCE(picked,0) AS picked FROM shipment_items WHERE id=?", (item_id,)).fetchone()
    if not row:
        c.close()
        return jsonify({"ok": False, "error": "Item not found"})
    new_state = 0 if row["picked"] else 1
    if new_state:
        c.execute("UPDATE shipment_items SET picked=1, picked_at=CURRENT_TIMESTAMP WHERE id=?", (item_id,))
    else:
        c.execute("UPDATE shipment_items SET picked=0, picked_at=NULL WHERE id=?", (item_id,))
    c.commit(); c.close()
    return jsonify({"ok": True, "picked": new_state})

@app.route("/api/pick/my-stats")
@req_role("picker", "worker", "admin", "cs")
def api_pick_my_stats():
    """Personal picking counters for today + this week. Drives the encouragement
    card on the iPad scan view ('You've picked X orders today')."""
    user = session.get("name", "")
    today = datetime.now().strftime("%Y-%m-%d")
    c = sdb()
    today_n = c.execute("""SELECT COUNT(*) FROM shipments
                           WHERE picked_by=? AND substr(picked_at,1,10)=?""", (user, today)).fetchone()[0]
    week_n = c.execute("""SELECT COUNT(*) FROM shipments
                          WHERE picked_by=? AND picked_at >= date('now','-7 days')""", (user,)).fetchone()[0]
    # Last pick time
    last = c.execute("""SELECT picked_at FROM shipments
                        WHERE picked_by=? ORDER BY picked_at DESC LIMIT 1""", (user,)).fetchone()
    c.close()
    return jsonify({
        "today": today_n,
        "week": week_n,
        "last_picked_at": last["picked_at"] if last else None,
    })


@app.route("/api/pick/issue/<sid>", methods=["POST"])
@req_role("picker", "worker", "admin", "cs")
def api_pick_issue(sid):
    """Picker flags an order as having a problem (missing item, damaged, etc).
    Status moves to 'issue' so the order disappears from the pick queue. Admin
    can review on /admin/shipments and either resolve back to 'pending' or cancel."""
    if not re.match(r'^[A-Za-z0-9_\-]{1,64}$', sid):
        return jsonify({"ok": False, "error": "Invalid id"})
    d = request.get_json() or {}
    reason = (d.get("reason") or "").strip()
    if not reason:
        return jsonify({"ok": False, "error": "Reason is required"})
    if len(reason) > 500:
        return jsonify({"ok": False, "error": "Reason too long (max 500 chars)"})
    reporter = session.get("name", "Unknown")
    stamped = datetime.now().strftime("%Y-%m-%d %H:%M") + " · " + reporter + ": " + reason
    c = sdb()
    s = c.execute("SELECT status FROM shipments WHERE shipment_id=?", (sid,)).fetchone()
    if not s:
        c.close()
        return jsonify({"ok": False, "error": "Shipment not found"})
    if s["status"] == "cancelled":
        c.close()
        return jsonify({"ok": False, "error": "Order is cancelled — nothing to flag"})
    c.execute("""UPDATE shipments SET status='issue', flag_reason=?, flag_resolved_at=NULL,
                 flag_resolved_by=NULL WHERE shipment_id=?""", (stamped, sid))
    c.commit(); c.close()
    return jsonify({"ok": True})

@app.route("/admin/issues")
@req_role("admin", "cs")
def issues_admin_page():
    return (ISSUES_HTML
        .replace("__ROLE__", session.get("role", ""))
        .replace("__NAVBAR__", _navbar("issues"))
        .replace("__NAVBAR_CSS__", _NAVBAR_CSS))

@app.route("/api/issues")
@req_role("admin", "cs")
def api_issues():
    """Every shipment currently flagged with status='issue', most-recent first.
    Includes items so admin can see what was supposed to be picked."""
    c = sdb()
    rows = c.execute("""SELECT shipment_id, tracking_code, buyer_name, buyer_username,
                               total_items, import_label, platform, flag_reason,
                               flag_resolved_at, flag_resolved_by, imported_at, show_date
                        FROM shipments WHERE status='issue'
                        ORDER BY imported_at DESC""").fetchall()
    out = []
    for s in rows:
        items = c.execute("""SELECT sku, product_name, quantity, COALESCE(picked,0) AS picked,
                                    COALESCE(cancelled,0) AS cancelled
                             FROM shipment_items WHERE shipment_id=?""", (s["shipment_id"],)).fetchall()
        out.append({**dict(s), "items": [dict(i) for i in items]})
    c.close()
    return jsonify(out)


@app.route("/api/pick/resolve/<sid>", methods=["POST"])
@req_role("admin", "cs")
def api_pick_resolve(sid):
    """Admin/CS resolves a picking issue. Either puts back to 'pending' (picker can try again)
    or cancels the order. Records resolver name + timestamp for audit trail."""
    if not re.match(r'^[A-Za-z0-9_\-]{1,64}$', sid):
        return jsonify({"ok": False, "error": "Invalid id"})
    d = request.get_json() or {}
    action = (d.get("action") or "").strip()
    if action not in ("retry", "cancel"):
        return jsonify({"ok": False, "error": "Action must be 'retry' or 'cancel'"})
    resolver = session.get("name", "Unknown")
    c = sdb()
    if action == "retry":
        c.execute("""UPDATE shipments SET status='pending', flag_resolved_at=CURRENT_TIMESTAMP,
                     flag_resolved_by=? WHERE shipment_id=? AND status='issue'""", (resolver, sid))
    else:
        c.execute("""UPDATE shipments SET status='cancelled', flag_resolved_at=CURRENT_TIMESTAMP,
                     flag_resolved_by=? WHERE shipment_id=? AND status='issue'""", (resolver, sid))
    c.commit(); c.close()
    return jsonify({"ok": True})


@app.route("/api/pick/complete/<sid>", methods=["POST"])
@req_role("picker", "worker", "admin", "cs")
def api_pick_complete(sid):
    """Mark every active item picked + shipment status='picked' + record picker name.
    Pickers walking through a list of items confirm done here, even if they didn't tap each one."""
    if not re.match(r'^[A-Za-z0-9_\-]{1,64}$', sid):
        return jsonify({"ok": False, "error": "Invalid id"})
    user = session.get("name", "Unknown")
    c = sdb()
    s = c.execute("SELECT status FROM shipments WHERE shipment_id=?", (sid,)).fetchone()
    if not s:
        c.close()
        return jsonify({"ok": False, "error": "Shipment not found"})
    if s["status"] == "cancelled":
        c.close()
        return jsonify({"ok": False, "error": "This order is cancelled — do not pick"})
    c.execute("""UPDATE shipment_items SET picked=1, picked_at=CURRENT_TIMESTAMP
                 WHERE shipment_id=? AND COALESCE(cancelled,0)=0 AND COALESCE(picked,0)=0""", (sid,))
    c.execute("""UPDATE shipments SET status='picked', picked_at=CURRENT_TIMESTAMP, picked_by=?
                 WHERE shipment_id=? AND status='pending'""", (user, sid))
    c.commit(); c.close()
    return jsonify({"ok": True})


# ══════════════════════════════════════════════════════════
# SHOWS — group imports by user-supplied "show name" for last 5 days.
# A single show can span multiple CSV imports (TikTok orders + cancellations,
# Whatnot, re-uploads after corrections). Packers may be working multiple
# active shows simultaneously, so this is the index they need.
# ══════════════════════════════════════════════════════════
SHOW_WINDOW_DAYS = 5

@app.route("/admin/shows")
@req_role("admin","cs")
def shows_admin_page():
    return (SHOWS_HTML
        .replace("__ROLE__", session.get("role",""))
        .replace("__NAVBAR__", _navbar("shows"))
        .replace("__NAVBAR_CSS__", _NAVBAR_CSS))

@app.route("/api/shows")
@req_role("admin","cs","picker","worker")
def api_shows():
    """Return distinct shows (import_label) from the last 5 days, with rollup
    stats per show. Used by the Shows page, the import autocomplete, and the picker."""
    cutoff_dt = (datetime.now() - timedelta(days=SHOW_WINDOW_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    c = sdb()
    rows = c.execute("""
        SELECT import_label AS name,
               COUNT(*) AS shipments,
               SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) AS pending,
               SUM(CASE WHEN status='packed' THEN 1 ELSE 0 END) AS packed,
               SUM(CASE WHEN status='shipped' THEN 1 ELSE 0 END) AS shipped,
               SUM(CASE WHEN status='cancelled' THEN 1 ELSE 0 END) AS cancelled,
               COUNT(DISTINCT platform) AS platform_count,
               MAX(platform) AS platform,
               MIN(imported_at) AS first_import,
               MAX(imported_at) AS last_import
        FROM shipments
        WHERE import_label IS NOT NULL AND import_label != ''
          AND imported_at >= ?
        GROUP BY import_label
        ORDER BY last_import DESC
    """, (cutoff_dt,)).fetchall()
    c.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/shows/recent")
@req_role("admin","cs","picker","worker")
def api_shows_recent():
    """Lightweight — just distinct show names from the last 5 days, for
    autocomplete dropdowns. Same data, slimmer payload."""
    cutoff_dt = (datetime.now() - timedelta(days=SHOW_WINDOW_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    c = sdb()
    rows = c.execute("""SELECT import_label AS name, MAX(imported_at) AS last
                        FROM shipments
                        WHERE import_label IS NOT NULL AND import_label != ''
                          AND imported_at >= ?
                        GROUP BY import_label
                        ORDER BY last DESC""", (cutoff_dt,)).fetchall()
    c.close()
    return jsonify([r["name"] for r in rows])


@app.route("/admin/shipments")
@req_role("admin","cs")
def shipments_admin_page():
    return (SHIPMENTS_ADMIN_HTML
        .replace("__ROLE__", session.get("role",""))
        .replace("__NAVBAR__", _navbar("shipments"))
        .replace("__NAVBAR_CSS__", _NAVBAR_CSS))


# ══════════════════════════════════════════════════════════
# SKU RECONCILIATION — end-of-show "where did SKU 12 go?" lookup
# ══════════════════════════════════════════════════════════

@app.route("/admin/sku-lookup")
@req_role("admin", "cs")
def sku_lookup_page():
    return (SKU_LOOKUP_HTML
        .replace("__ROLE__", session.get("role", ""))
        .replace("__NAVBAR__", _navbar("sku_lookup"))
        .replace("__NAVBAR_CSS__", _NAVBAR_CSS))

@app.route("/api/sku-lookup/batches")
@req_role("admin", "cs")
def api_sku_batches():
    """List import batches so the manager can filter to current show."""
    c = sdb()
    rows = c.execute("""SELECT import_batch, MAX(import_label) AS label,
                               COUNT(*) AS shipments,
                               MAX(imported_at) AS imported_at,
                               MAX(platform) AS platform
                        FROM shipments WHERE import_batch IS NOT NULL
                        GROUP BY import_batch
                        ORDER BY imported_at DESC""").fetchall()
    c.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/sku-lookup/<sku>")
@req_role("admin", "cs")
def api_sku_lookup(sku):
    """Find every item with this SKU. Optional filter by import_batch.
    Returns enough info to identify which physical item this is and where it went."""
    sku = (sku or "").strip()
    if not sku or len(sku) > 64:
        return jsonify({"ok": False, "error": "Invalid SKU"})
    batch = (request.args.get("batch") or "").strip()
    c = sdb()
    q = """SELECT i.id AS item_id, i.sku, i.product_name, i.quantity, i.cancelled, i.cancel_reason,
                  i.order_id, i.item_weight_g,
                  s.shipment_id, s.tracking_code, s.buyer_username, s.buyer_name,
                  s.status, s.platform, s.import_batch, s.import_label,
                  s.packed_at, s.actual_weight_g
           FROM shipment_items i
           JOIN shipments s ON s.shipment_id = i.shipment_id
           WHERE i.sku = ?"""
    params = [sku]
    if batch:
        q += " AND s.import_batch = ?"
        params.append(batch)
    q += " ORDER BY s.import_batch DESC, i.cancelled, s.status"
    rows = c.execute(q, params).fetchall()
    c.close()
    return jsonify({
        "ok": True,
        "sku": sku,
        "batch_filter": batch or None,
        "matches": [dict(r) for r in rows],
    })


@app.route("/api/weight-config", methods=["GET", "POST"])
@req_role("admin")
def api_weight_config():
    """Get or update the singleton tolerance / packaging-overhead config row."""
    if request.method == "GET":
        return jsonify(_weight_config())
    d = request.get_json() or {}
    try:
        tp = float(d.get("tolerance_percent", 10))
        tg = float(d.get("tolerance_absolute_g", 5))
        po = float(d.get("packaging_overhead_g", 30))
    except:
        return jsonify({"ok": False, "error": "All values must be numbers"})
    if not (0 <= tp <= 100 and 0 <= tg <= 1000 and 0 <= po <= 5000):
        return jsonify({"ok": False, "error": "Values out of sensible range"})
    c = sdb()
    c.execute("""UPDATE weight_config SET tolerance_percent=?, tolerance_absolute_g=?,
                 packaging_overhead_g=?, updated_at=CURRENT_TIMESTAMP WHERE id=1""", (tp, tg, po))
    # Re-snapshot packaging overhead into all shipments' expected_weight
    sids = [r["shipment_id"] for r in c.execute("SELECT shipment_id FROM shipments").fetchall()]
    for sid in sids:
        _recompute_shipment_weight(c, sid)
    c.commit(); c.close()
    return jsonify({"ok": True, "shipments_recomputed": len(sids)})


@app.route("/api/documents/<doc_id>/delete", methods=["POST"])
@req_role("admin")
def api_documents_delete(doc_id):
    if not re.match(r'^doc_[a-f0-9]{8}$', doc_id):
        return jsonify({"ok": False, "error": "Invalid id"})
    docs = _docs_load()
    d = docs.get(doc_id)
    if not d: return jsonify({"ok": False, "error": "Not found"})
    stored = d.get("stored_filename", "")
    if stored:
        if r2:
            try: r2.delete_object(Bucket=R2_BUCKET, Key="documents/" + stored)
            except Exception as e: print("R2 doc delete failed:", e, flush=True)
        else:
            path = os.path.join(DOCS_DIR, stored)
            rp = os.path.realpath(path)
            if rp.startswith(os.path.realpath(DOCS_DIR) + os.sep) and os.path.exists(rp):
                try: os.remove(rp)
                except: pass
    del docs[doc_id]
    _docs_save(docs)
    return jsonify({"ok": True})


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

@app.route("/api/users/badge/label4x6/<u>")
@req_role("admin")
def api_badge_label4x6(u):
    """Generate a 4×6 inch shipping-label-sized badge PDF.
    The badge occupies a 4×3" area at the BOTTOM half of the label so the top
    half can be folded over the badge or left blank for hole-punching/lamination.
    Optimized for thermal label printers (DYMO 4XL, Rollo, Zebra, etc.)."""
    users = ldj(USERS_FILE)
    if u not in users: return ("", 404)
    info = users[u]
    token = info.get("badge_token")
    if not token: return jsonify({"ok": False, "error": "User has no badge token"}), 400
    try:
        from io import BytesIO
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import inch
        import barcode
        from barcode.writer import ImageWriter
        # Generate barcode image (Code 128 — scanner-friendly)
        bio = BytesIO()
        bc = barcode.Code128(token, writer=ImageWriter())
        bc.write(bio, options={"module_height": 14.0, "module_width": 0.5, "font_size": 9,
                               "text_distance": 3.0, "quiet_zone": 3})
        bio.seek(0)
        from reportlab.lib.utils import ImageReader
        img = ImageReader(bio)
        # Page = 4×6" (thermal label), with badge content in bottom 3"
        page_w, page_h = 4 * inch, 6 * inch
        out = BytesIO()
        c = canvas.Canvas(out, pagesize=(page_w, page_h))
        # ─── Bottom half: the badge (4×3", from y=0 to y=3") ───
        # Outer rounded border
        c.setStrokeColorRGB(0.2, 0.2, 0.2); c.setLineWidth(1.2)
        c.roundRect(0.15*inch, 0.15*inch, page_w - 0.3*inch, 3*inch - 0.3*inch, 8, stroke=1, fill=0)
        # Top stripe — brand pink
        stripe_h = 0.6 * inch
        c.setFillColorRGB(0.953, 0.788, 0.769)  # #f3c9c4 brand pink
        c.roundRect(0.15*inch, 3*inch - 0.15*inch - stripe_h, page_w - 0.3*inch, stripe_h, 8, stroke=0, fill=1)
        # Stripe text
        c.setFillColorRGB(0.10, 0.06, 0.05)
        c.setFont("Helvetica-Bold", 22); c.drawCentredString(page_w/2, 3*inch - 0.40*inch, "5 SEC")
        c.setFont("Helvetica-Bold", 9); c.drawCentredString(page_w/2, 3*inch - 0.60*inch, "EMPLOYEE BADGE")
        # Worker name (big, centered)
        c.setFillColorRGB(0, 0, 0); c.setFont("Helvetica-Bold", 24)
        c.drawCentredString(page_w/2, 3*inch - 1.15*inch, info["name"])
        # Username
        c.setFont("Helvetica", 11); c.setFillColorRGB(0.4, 0.4, 0.4)
        c.drawCentredString(page_w/2, 3*inch - 1.42*inch, "@" + u)
        # Role pill
        role_text = info.get("role", "").upper()
        if role_text:
            c.setFont("Helvetica-Bold", 9); c.setFillColorRGB(0.4, 0.4, 0.4)
            c.drawCentredString(page_w/2, 3*inch - 1.65*inch, role_text)
        # Barcode (large, scanner-friendly across the bottom)
        bc_w = page_w - 0.6*inch; bc_h = 1.0*inch
        c.drawImage(img, 0.30*inch, 0.30*inch, width=bc_w, height=bc_h,
                    preserveAspectRatio=True, mask='auto')
        c.showPage(); c.save()
        out.seek(0)
        return send_file(out, mimetype="application/pdf",
                         download_name="badge_4x6_" + u + ".pdf", as_attachment=False)
    except Exception as e:
        print("Badge 4x6 PDF error:", e, flush=True)
        return jsonify({"ok": False, "error": "PDF generation failed: " + str(e)[:100]}), 500


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


@app.route("/api/machine-mode",methods=["GET","POST"])
def api_machine_mode():
    """Per-device role assignment: 'pick' (iPad picker), 'pack' (packing PC), or '' (default).
    After badge login, the / route uses this cookie to decide where to send the worker."""
    if request.method=="GET":
        return jsonify({"mode": request.cookies.get("machine_mode","")})
    if session.get("role")!="admin":
        return jsonify({"ok":False,"error":"Admin required"}),403
    d=request.get_json() or {}
    mode=(d.get("mode") or "").strip()
    if mode not in ("pick","pack",""):
        return jsonify({"ok":False,"error":"Invalid mode"})
    resp=jsonify({"ok":True,"mode":mode})
    if mode:
        resp.set_cookie("machine_mode",mode,max_age=10*365*24*3600,httponly=False,samesite="Lax",secure=True)
    else:
        resp.delete_cookie("machine_mode")
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
