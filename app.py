#!/usr/bin/env python3
"""
5 Second Beauty — Packing Station
Production web app for packing video recording & lookup.
"""
import os,csv,json,hashlib,secrets,time,threading,re,sys,sqlite3,fcntl,io
from datetime import datetime,timedelta
from functools import wraps
from contextlib import contextmanager
from flask import Flask,request,jsonify,send_file,redirect,session,Response,has_request_context,g
from werkzeug.utils import secure_filename
from markupsafe import escape as _mescape
import bcrypt

def esc(s):
    """HTML-escape any value for safe interpolation into templates (& < > \" ')."""
    return str(_mescape("" if s is None else s))

def _clean_name(s,maxlen=100):
    """Sanitize a human name/display field: strip tag characters and control
    chars (kills text-context XSS at the source) while keeping apostrophes,
    ampersands and accents so real names like O'Brien survive intact."""
    s=(s or "").strip()
    s=re.sub(r'[<>\x00-\x1f\x7f]','',s)
    return s[:maxlen]
# HTML templates and navbar helper live in templates.py for readability.
from templates import (_navbar, _NAVBAR_CSS, _FONT,
    BILLING_HTML, DEMO_HTML, SETUP_HTML,
    LOGIN_HTML, STATION_HTML, WORKER_HTML, DASH_HTML, USERS_HTML,
    ANALYTICS_HTML, GIVEAWAY_DASH_HTML, GIVEAWAY_DETAIL_HTML,
    BADGE_LOGIN_HTML, USERS_BADGES_HTML,
    ME_HTML, LEADERBOARD_HTML, HOME_HTML, DOCUMENTS_HTML, WELCOME_HTML,
    ONBOARDING_HTML, ANNOUNCEMENTS_HTML,
    CUSTOMERS_HTML, SHIPMENTS_ADMIN_HTML, SKU_LOOKUP_HTML, SHOWS_HTML, PICK_HTML,
    ISSUES_HTML, CLEANUP_HTML, SHIPPING_STATUS_HTML, PERMISSIONS_HTML,
    INVENTORY_HTML, PURCHASING_HTML, STOCKTAKE_HTML, AUDIT_HTML, ROSTER_HTML, MYSCHEDULE_HTML, MYAVAIL_HTML, PROFIT_HTML, INBOUND_HTML, PRESHOW_HTML, HOSTS_HTML, PACKER_HTML, SETTINGS_HTML, GEO_HTML,
    PICKER_HTML, REPEAT_HTML,
    OPERATIONS_HTML, ORGANIZATIONS_HTML, SUPPORT_HTML, PLATFORM_SUPPORT_HTML,
    GUIDES_HTML, GUIDES_ADMIN_HTML,
    HIRES_ADMIN_HTML, HIRE_DETAIL_HTML, HIRE_ONBOARDING_HTML, HIRE_FILE_HTML)
from guide_content import GUIDE_ASSETS, GUIDE_SEEDS


# Default (founding) tenant id. Multi-tenancy: every user belongs to an org;
# existing single-tenant data is treated as belonging to this org.
DEFAULT_ORG=os.environ.get("DEFAULT_ORG","5sec")
# The platform owner (super-admin) is NOT a tenant. Their account carries this
# sentinel org so they never touch any customer's operational data — including
# the founding tenant (5sec), which is just a normal customer.
PLATFORM_ORG="__platform__"
DATA_DIR=os.environ.get("DATA_DIR",os.path.join(os.path.expanduser("~"),"PackingStationData"))
ORGS_DIR=os.path.join(DATA_DIR,"orgs")   # every tenant gets a private folder here
LOG_FIELDS=["tracking_number","station","date","time","duration_seconds","video_file","photo_file","worker"]

# ══════════════════════════════════════════════════════════════════
# MULTI-TENANCY — data isolation model
# ------------------------------------------------------------------
# CONTROL PLANE (shared across all tenants, lives at DATA_DIR root):
#   users.json      - maps a username -> {password, role, org}. Read at
#                     login, BEFORE we know the org, so it must be global.
#   stations.json   - shared station registry.
#   platform.db     - the `organizations` table (the tenant directory).
#
# TENANT DATA (per-org, physically isolated under /data/orgs/<org>/):
#   shipments.db, giveaways.db, videos/, photos/, packing_log.csv,
#   documents.json + documents/, onboarding.json, announcements.json
#
# A query literally cannot reach another tenant's file: isolation is by
# filesystem path, resolved from the logged-in user's session org through
# the single choke point below. Nothing may derive the org from a URL/param.
# ══════════════════════════════════════════════════════════════════
USERS_FILE=os.path.join(DATA_DIR,"users.json")       # control plane
STATIONS_FILE=os.path.join(DATA_DIR,"stations.json") # control plane
PLATFORM_DB=os.path.join(DATA_DIR,"platform.db")     # control plane (organizations)

def org_path(org,*parts):
    """Absolute path inside a tenant's private folder. org is REQUIRED."""
    if not org:
        raise RuntimeError("org_path() called without an org — tenant isolation bug")
    return os.path.join(ORGS_DIR,str(org),*parts)

def current_org():
    """The org for the current request: the logged-in user's session org, or
    for public token flows (e.g. new-hire onboarding) the org pinned into g.org
    after the token is resolved. None outside a request."""
    try:
        if has_request_context():
            o=session.get("org")
            if o: return o
            return getattr(g,"org",None)
    except Exception:
        pass
    return None

def _org_or_current(org):
    o=org or current_org()
    if not o:
        raise RuntimeError("tenant data accessed without an org in context")
    return o

# Per-org path helpers. Pass an explicit org from schedulers/boot (no session);
# in a request they default to the session's org.
def video_dir(org=None):    return org_path(_org_or_current(org),"videos")
def photo_dir(org=None):    return org_path(_org_or_current(org),"photos")
def docs_dir(org=None):     return org_path(_org_or_current(org),"documents")
def log_file(org=None):     return org_path(_org_or_current(org),"packing_log.csv")
def docs_file(org=None):    return org_path(_org_or_current(org),"documents.json")
def onb_file(org=None):     return org_path(_org_or_current(org),"onboarding.json")
def ann_file(org=None):     return org_path(_org_or_current(org),"announcements.json")
def shipments_db_path(org=None): return org_path(_org_or_current(org),"shipments.db")
def giveaway_db_path(org=None):  return org_path(_org_or_current(org),"giveaways.db")

def list_org_ids():
    """All active tenant org_ids (control plane). Used by schedulers/boot."""
    try:
        c=pdb()
        ids=[r["org_id"] for r in c.execute("SELECT org_id FROM organizations WHERE active=1").fetchall()]
        c.close()
        return ids or [DEFAULT_ORG]
    except Exception:
        return [DEFAULT_ORG]

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

# ── Per-tenant object keys ────────────────────────────────────────────────────
# Media used to be stored at bare prefixes ("videos/<station>_<tracking>.webm"),
# which are guessable AND shared across tenants — one customer could fetch another
# customer's packing video. Every media key is now namespaced by org.
def _r2_media_key(kind, name, org=None):
    """Per-tenant R2 key, e.g. '5sec/videos/S1_TRK_120000.webm'."""
    return "%s/%s/%s" % (_org_or_current(org), kind, name)

def _r2_resolve(kind, name, org=None):
    """Key to READ from: prefer the per-org key, else fall back to the pre-namespacing
    legacy key — but only for the original tenant, which owns all legacy objects.
    Other tenants can never resolve to a legacy (un-namespaced) key."""
    org=_org_or_current(org)
    k="%s/%s/%s" % (org, kind, name)
    if not r2: return k
    try:
        r2.head_object(Bucket=R2_BUCKET, Key=k); return k
    except Exception: pass
    if org==DEFAULT_ORG:
        legacy="%s/%s" % (kind, name)
        try:
            r2.head_object(Bucket=R2_BUCKET, Key=legacy); return legacy
        except Exception: pass
    return k

os.makedirs(DATA_DIR,exist_ok=True)
os.makedirs(ORGS_DIR,exist_ok=True)

# Default onboarding tasks seeded into each new tenant so their install isn't empty.
_ONB_SEED = {
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

def _seed_org_files(org):
    """Create a tenant's private folders + seed its empty JSON stores."""
    for d in (video_dir(org),photo_dir(org),docs_dir(org)):
        os.makedirs(d,exist_ok=True)
    df=docs_file(org)
    if not os.path.exists(df):
        with open(df,"w") as f: json.dump({},f)
    of=onb_file(org)
    if not os.path.exists(of):
        with open(of,"w") as f: json.dump(_ONB_SEED,f,indent=2)
    lf=log_file(org)
    if not os.path.exists(lf):
        with open(lf,"w") as f: f.write(",".join(LOG_FIELDS)+"\n")

MAX_DOC_SIZE = 50*1024*1024  # 50MB per document

# ══════════════════════════════════════════════════════════
# CONTROL-PLANE DB (platform.db) — shared across all tenants.
# Holds the organizations directory. This is the ONLY DB that is
# allowed to span tenants; all operational data is per-org.
# ══════════════════════════════════════════════════════════
def pdb():
    c=sqlite3.connect(PLATFORM_DB,timeout=10.0)
    c.row_factory=sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c

def pdb_init():
    c=pdb()
    c.execute("""CREATE TABLE IF NOT EXISTS organizations(
        org_id TEXT PRIMARY KEY,
        company_name TEXT NOT NULL,
        brand_mark TEXT NOT NULL DEFAULT '5 SEC',
        brand_sub TEXT NOT NULL DEFAULT 'Employee Hub',
        brand_color TEXT NOT NULL DEFAULT '#d9748f',
        logo_url TEXT DEFAULT '',
        plan TEXT DEFAULT 'standard',
        active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        contact_email TEXT,
        contact_phone TEXT,
        trial_ends_at TEXT,
        sub_status TEXT DEFAULT 'none',
        stripe_customer_id TEXT,
        stripe_subscription_id TEXT,
        current_period_end TEXT
    )""")
    # Backward-compatible: add subscription columns to existing platform DBs.
    _org_have={r[1] for r in c.execute("PRAGMA table_info(organizations)").fetchall()}
    for _col,_decl in (("trial_ends_at","TEXT"),("sub_status","TEXT DEFAULT 'none'"),
                       ("stripe_customer_id","TEXT"),("stripe_subscription_id","TEXT"),
                       ("current_period_end","TEXT"),("internal","INTEGER DEFAULT 0"),
                       ("contact_email","TEXT"),("contact_phone","TEXT")):
        if _col not in _org_have:
            c.execute("ALTER TABLE organizations ADD COLUMN %s %s" % (_col,_decl))
    # Manual billing ledger — one row per payment received (bank transfer, invoice,
    # PayPal, whatever). Recording a payment is what extends a tenant's access.
    c.execute("""CREATE TABLE IF NOT EXISTS payments(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id TEXT NOT NULL,
        amount REAL,
        currency TEXT DEFAULT 'USD',
        plan TEXT,
        months INTEGER,
        period_start TEXT,
        period_end TEXT,
        method TEXT,
        reference TEXT,
        notes TEXT,
        recorded_by TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_payments_org ON payments(org_id, created_at DESC)")
    # A tenant asking to start/upgrade a plan from the billing screen.
    c.execute("""CREATE TABLE IF NOT EXISTS billing_requests(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id TEXT NOT NULL,
        plan TEXT,
        requested_by TEXT,
        handled INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    # Sales-led leads from the public "request a demo" form.
    c.execute("""CREATE TABLE IF NOT EXISTS leads(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        company TEXT,
        contact_name TEXT,
        email TEXT,
        phone TEXT,
        platforms TEXT,
        volume TEXT,
        message TEXT,
        status TEXT DEFAULT 'new',
        notes TEXT,
        converted_org TEXT
    )""")
    # Seed the founding tenant (5 Second Beauty) if the table is empty.
    if not c.execute("SELECT 1 FROM organizations WHERE org_id=?", (DEFAULT_ORG,)).fetchone():
        c.execute("""INSERT INTO organizations(org_id,company_name,brand_mark,brand_sub,brand_color)
                     VALUES(?,?,?,?,?)""",
                  (DEFAULT_ORG, "5 Second Beauty", "5 SEC", "Employee Hub", "#d9748f"))
    c.execute("UPDATE organizations SET brand_color='#d9748f' WHERE brand_color='#f3c9c4'")
    # The founding tenant is the owner's own business — never gated, never billed,
    # and not subject to plan caps.
    c.execute("UPDATE organizations SET sub_status='active' WHERE org_id=? AND COALESCE(sub_status,'none') IN ('none','')",
              (DEFAULT_ORG,))
    c.execute("UPDATE organizations SET internal=1 WHERE org_id=?", (DEFAULT_ORG,))
    # Platform audit trail (super-admin actions: impersonation, org create/suspend).
    c.execute("""CREATE TABLE IF NOT EXISTS platform_audit(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        at TEXT DEFAULT CURRENT_TIMESTAMP,
        actor TEXT,
        action TEXT,
        org_id TEXT,
        detail TEXT
    )""")
    # Support tickets (cross-tenant: customers open them, platform owner answers).
    c.execute("""CREATE TABLE IF NOT EXISTS tickets(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id TEXT NOT NULL,
        created_by TEXT,
        created_by_name TEXT,
        category TEXT,
        subject TEXT NOT NULL,
        priority TEXT DEFAULT 'normal',
        status TEXT NOT NULL DEFAULT 'open',
        context TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        last_actor TEXT
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_tickets_org ON tickets(org_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status)")
    c.execute("""CREATE TABLE IF NOT EXISTS ticket_messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id INTEGER NOT NULL,
        author TEXT,
        author_name TEXT,
        author_side TEXT,
        body TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_tmsg_ticket ON ticket_messages(ticket_id)")
    # Screenshots / files attached to a ticket message.
    c.execute("""CREATE TABLE IF NOT EXISTS ticket_attachments(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id INTEGER NOT NULL,
        message_id INTEGER,
        filename TEXT,
        storage_key TEXT,
        mime TEXT,
        size_bytes INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_tatt_ticket ON ticket_attachments(ticket_id)")
    # Help guides — authored by the platform owner, shown to all tenants.
    c.execute("""CREATE TABLE IF NOT EXISTS guides(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT DEFAULT 'getting_started',
        title TEXT NOT NULL,
        body TEXT DEFAULT '',
        video_url TEXT DEFAULT '',
        audience TEXT DEFAULT 'all',
        status TEXT DEFAULT 'draft',
        sort_order INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_guides_status ON guides(status)")
    c.commit(); c.close()

pdb_init()

def plog(actor,action,org_id="",detail=""):
    """Append a row to the platform audit trail. Best-effort (never raises)."""
    try:
        c=pdb(); c.execute("INSERT INTO platform_audit(actor,action,org_id,detail) VALUES(?,?,?,?)",
                           (actor,action,org_id,detail)); c.commit(); c.close()
    except Exception as e:
        print("plog error:",e,flush=True)

def alog(action,detail=""):
    """Append to the CURRENT tenant's audit trail (sensitive staff actions).
    Best-effort — never breaks the request. Called from within request handlers."""
    try:
        c=sdb()
        c.execute("INSERT INTO audit_log(actor,role,action,detail,ip) VALUES(?,?,?,?,?)",
                  (session.get("user"),session.get("role"),action,str(detail)[:500],request.remote_addr))
        c.commit(); c.close()
    except Exception as e:
        print("alog error:",e,flush=True)

def cleanup_old_files(org):
    """Delete one tenant's video/photo files older than RETENTION_DAYS.
    When R2 is configured, file deletion is handled by R2 lifecycle rules.
    This function only cleans the local CSV log of old rows in that case."""
    cutoff=time.time()-RETENTION_DAYS*86400
    deleted=0;freed=0
    lf=log_file(org)
    if not r2:  # only clean local files when not using R2
        for folder in [video_dir(org),photo_dir(org)]:
            if not os.path.exists(folder): continue
            for f in os.listdir(folder):
                fp=os.path.join(folder,f)
                try:
                    if os.path.getmtime(fp)<cutoff:
                        sz=os.path.getsize(fp)
                        os.remove(fp)
                        deleted+=1;freed+=sz
                except: pass
    # Always clean old log entries. Serialize with the same lock the upload
    # append uses, and rewrite atomically, so a concurrent append is never lost.
    if os.path.exists(lf):
        cutoff_date=(datetime.now()-timedelta(days=RETENTION_DAYS)).strftime('%Y-%m-%d')
        try:
            with _flock("packing_log_"+str(org)):
                with open(lf) as f: rows=list(csv.DictReader(f))
                kept=[r for r in rows if r.get("date","")>=cutoff_date]
                if len(kept)<len(rows):
                    buf=io.StringIO()
                    w=csv.DictWriter(buf,fieldnames=LOG_FIELDS)
                    w.writeheader();w.writerows(kept)
                    _atomic_write(lf,buf.getvalue())
        except Exception as e: print("Log cleanup failed:",e,flush=True)
    if deleted>0: print("Cleanup["+str(org)+"]: deleted",deleted,"files, freed",round(freed/(1024*1024),1),"MB")
    return {"deleted":deleted,"freed_mb":round(freed/(1024*1024),1)}

def cleanup_all_orgs():
    """Run retention cleanup for every tenant."""
    total={"deleted":0,"freed_mb":0}
    for org in list_org_ids():
        try:
            r=cleanup_old_files(org)
            total["deleted"]+=r["deleted"]; total["freed_mb"]+=r["freed_mb"]
        except Exception as e: print("Cleanup error for",org,":",e,flush=True)
    return total

def cleanup_loop():
    # Only one worker should run the hourly cleanup. A non-blocking lock lets
    # exactly one of the 4 gunicorn workers win; the rest skip harmlessly.
    guard=open(os.path.join(DATA_DIR,".cleanup.guard"),"a+")
    try:
        fcntl.flock(guard.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:
        return  # another worker owns the cleanup loop
    while True:
        time.sleep(3600)
        try: cleanup_all_orgs()
        except Exception as e: print("Cleanup loop error:",e,flush=True)

cleanup_thread=threading.Thread(target=cleanup_loop,daemon=True)
cleanup_thread.start()

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

# Precomputed bcrypt hash used to equalize login timing on unknown usernames,
# so an attacker can't tell "user exists" from response speed.
_DUMMY_HASH=bcrypt.hashpw(b"dummy-timing-equalizer",bcrypt.gensalt(rounds=12))

def _gen_pw():
    """Generate a strong random password."""
    return secrets.token_urlsafe(12)

def _gen_badge_token():
    """Generate a barcode-friendly badge token: 16 alphanumeric chars in 4-char groups.
    Excludes ambiguous chars (0/O, 1/I/l) for visual scanning fallback."""
    alphabet="23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # 32 chars
    raw="".join(secrets.choice(alphabet) for _ in range(16))
    return raw[:4]+"-"+raw[4:8]+"-"+raw[8:12]+"-"+raw[12:16]


@contextmanager
def _flock(name):
    """Cross-process advisory lock via a lockfile in DATA_DIR.
    All 4 gunicorn workers coordinate through the same file, so
    read-modify-write cycles and file rewrites are serialized."""
    lp=os.path.join(DATA_DIR,"."+name+".lock")
    f=open(lp,"a+")
    try:
        fcntl.flock(f.fileno(),fcntl.LOCK_EX)
        yield
    finally:
        try: fcntl.flock(f.fileno(),fcntl.LOCK_UN)
        finally: f.close()

def _atomic_write(path,text):
    """Write text to path atomically: tmp file + fsync + os.replace.
    A crash mid-write leaves the original file intact instead of truncated."""
    tmp=path+".tmp."+str(os.getpid())
    with open(tmp,"w") as f:
        f.write(text);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)

def _lock_name(p):
    return os.path.basename(p)

def _init(path,default):
    if not os.path.exists(path):
        _atomic_write(path,json.dumps(default,indent=2))
def ldj(p):
    with open(p) as f: return json.load(f)
def svj(p,d):
    with _flock(_lock_name(p)):
        _atomic_write(p,json.dumps(d,indent=2))

@contextmanager
def update_json(p,default=None):
    """Locked read-modify-write of a JSON file. Holds the file's lock across
    both the load and the save so concurrent workers don't lose each other's
    updates. Usage: `with update_json(USERS_FILE) as users: users[...]=...`"""
    with _flock(_lock_name(p)):
        try:
            with open(p) as f: data=json.load(f)
        except (FileNotFoundError,json.JSONDecodeError):
            data={} if default is None else default
        yield data
        _atomic_write(p,json.dumps(data,indent=2))

# ── Login rate limiting (file-based so all 4 workers share the counter) ──
_RATE_FILE=os.path.join(DATA_DIR,".login_attempts.json")
LOGIN_MAX_FAILS=8       # failures allowed per (ip, username) ...
LOGIN_WINDOW=300        # ... within this many seconds

def _rate_load():
    try:
        with open(_RATE_FILE) as f: return json.load(f)
    except (FileNotFoundError,json.JSONDecodeError): return {}

def _rate_key(ip,user): return (ip or "?")+"|"+(user or "?")

# Generic in-process sliding-window limiter (used by the public lead form).
_hits={}
def _rate_ok(key, limit=5, window=3600):
    """True if this key is still under `limit` hits inside `window` seconds."""
    now=time.time()
    arr=[t for t in _hits.get(key,[]) if now-t < window]
    if len(arr)>=limit:
        _hits[key]=arr
        return False
    arr.append(now); _hits[key]=arr
    return True

def _login_rate_check(ip,user):
    """Return (ok, limited). limited=True means block this attempt."""
    now=time.time();key=_rate_key(ip,user)
    with _flock("login_attempts"):
        rec=_rate_load().get(key)
    limited=bool(rec and rec.get("count",0)>=LOGIN_MAX_FAILS and now-rec.get("first",0)<LOGIN_WINDOW)
    return (not limited,limited)

def _login_rate_fail(ip,user):
    now=time.time();key=_rate_key(ip,user)
    with _flock("login_attempts"):
        data=_rate_load();rec=data.get(key)
        if not rec or now-rec.get("first",0)>=LOGIN_WINDOW:
            rec={"first":now,"count":0}
        rec["count"]=rec.get("count",0)+1;data[key]=rec
        data={k:v for k,v in data.items() if now-v.get("first",0)<LOGIN_WINDOW*4}  # prune
        _atomic_write(_RATE_FILE,json.dumps(data))

def _login_rate_clear(ip,user):
    key=_rate_key(ip,user)
    with _flock("login_attempts"):
        data=_rate_load()
        if key in data: del data[key];_atomic_write(_RATE_FILE,json.dumps(data))

# On first run only: generate strong random passwords and print them once.
# After this file exists, change passwords via the admin UI.
# The lock + re-check inside guarantees exactly one of the 4 workers seeds,
# so the printed passwords always match what was actually written.
if not os.path.exists(USERS_FILE):
    with _flock(_lock_name(USERS_FILE)):
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
            _atomic_write(USERS_FILE,json.dumps(_data,indent=2))
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
# Seeded only for the founding tenant. Every other tenant defines their own in
# Settings → Company setup (stored per-org), so nobody sees another brand's names.
_FOUNDING_GIVEAWAY_BRANDS=["5 Sec Beauty","Hera Beauty","Peach Beauty"]

def giveaway_brands(org=None):
    """This tenant's giveaway brand list. Falls back to their own channel names, so a
    new customer gets something sensible instead of somebody else's brands."""
    try:
        raw=_get_setting("giveaway_brands")
        if raw:
            v=json.loads(raw)
            if isinstance(v,list): return [str(x)[:60] for x in v if str(x).strip()]
    except Exception: pass
    if _org_or_current(org)==DEFAULT_ORG:
        return list(_FOUNDING_GIVEAWAY_BRANDS)
    try:
        return [c["name"] for c in _channels()]
    except Exception:
        return []
# A giveaway winner with no order yet waits this many days for an order to appear in a
# CSV import before we give up and it moves to "need to create a label".
GIVEAWAY_NO_ORDER_DAYS=4
GIVEAWAY_STATUSES=["pending_address","address_received","label_created","shipped","cancelled"]

def gdb(org=None):
    """Giveaways DB connection for a tenant (defaults to the session's org)."""
    c=sqlite3.connect(giveaway_db_path(org),timeout=10.0)
    c.row_factory=sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c

def gdb_init(org):
    """Create the giveaway table for a tenant if it doesn't exist."""
    c=gdb(org)
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
    # --- "piggyback" attach feature: link a giveaway to an existing order so the
    #     prize ships inside that order's box instead of a separate shipment. ---
    _gv_cols={
        "attach_mode":"TEXT DEFAULT 'standalone'",  # 'standalone' | 'piggyback'
        "linked_shipment_id":"TEXT",
        "linked_tracking":"TEXT",
        "attach_status":"TEXT",                     # 'pending' | 'added' | 'missed'
        "attach_added_at":"TEXT",
        "attach_added_by":"TEXT",
        "attach_show":"TEXT",
        # Standalone giveaways get packed+filmed on the normal record screen by
        # scanning their own tracking; these capture that.
        "filmed_at":"TEXT",
        "filmed_by":"TEXT",
    }
    _have={r[1] for r in c.execute("PRAGMA table_info(giveaways)").fetchall()}
    for _col,_decl in _gv_cols.items():
        if _col not in _have:
            c.execute("ALTER TABLE giveaways ADD COLUMN %s %s" % (_col,_decl))
    c.execute("CREATE INDEX IF NOT EXISTS idx_giveaways_linked ON giveaways(linked_shipment_id)")
    c.commit();c.close()


# ══════════════════════════════════════════════════════════
# SHIPMENT WEIGHT VERIFICATION — separate SQLite DB
# Imported from Whatnot CSV exports. One row per shipment_id.
# Items in separate table. SKU weights cached for fast lookup.
# ══════════════════════════════════════════════════════════
def sdb(org=None):
    """Shipments DB connection for a tenant (defaults to the session's org)."""
    c = sqlite3.connect(shipments_db_path(org), timeout=10.0)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c

def sdb_init(org):
    """Create the shipments / items / sku_weights / weight_config tables for a tenant."""
    c = sdb(org)
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
        packed_by TEXT,
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
        "ALTER TABLE shipments ADD COLUMN packed_by TEXT",
        # USPS delivery tracking (statusCategory bucket + last event + timestamps)
        "ALTER TABLE shipments ADD COLUMN delivery_status TEXT",
        "ALTER TABLE shipments ADD COLUMN delivery_detail TEXT",
        "ALTER TABLE shipments ADD COLUMN delivered_at TEXT",
        "ALTER TABLE shipments ADD COLUMN tracked_at TEXT",
        "ALTER TABLE shipments ADD COLUMN stock_depleted INTEGER DEFAULT 0",
        # TikTok: shipping fee the buyer paid (collected, then paid out to carrier).
        "ALTER TABLE shipments ADD COLUMN shipping_fee REAL DEFAULT 0",
        "ALTER TABLE shipment_items ADD COLUMN order_id TEXT",
        "ALTER TABLE shipment_items ADD COLUMN cancelled INTEGER DEFAULT 0",
        "ALTER TABLE shipment_items ADD COLUMN cancel_reason TEXT",
        "ALTER TABLE shipment_items ADD COLUMN picked INTEGER DEFAULT 0",
        "ALTER TABLE shipment_items ADD COLUMN picked_at TEXT",
        "ALTER TABLE shipment_items ADD COLUMN revenue REAL DEFAULT 0",
        # Full sale timestamp + geography for show/audience analytics.
        "ALTER TABLE shipment_items ADD COLUMN created_time TEXT",
        "ALTER TABLE shipment_items ADD COLUMN buyer_state TEXT",
        "ALTER TABLE shipment_items ADD COLUMN buyer_city TEXT",
        # Pre-import match: how many units we've already deducted for a binding,
        # so re-binding / unmapping can restore on_hand correctly.
        "ALTER TABLE show_product_map ADD COLUMN depleted_qty INTEGER DEFAULT 0",
        # Inbound: group all labels bought in one click as a batch.
        "ALTER TABLE inbound_shipments ADD COLUMN batch_id TEXT",
        # Bilingual onboarding — Spanish translations live in *_es columns
        # alongside the English originals. NULL ES → frontend falls back to EN.
        "ALTER TABLE onboarding_steps ADD COLUMN title_es TEXT",
        "ALTER TABLE onboarding_steps ADD COLUMN description_es TEXT",
        "ALTER TABLE onboarding_steps ADD COLUMN body_es TEXT",
        "ALTER TABLE onboarding_steps ADD COLUMN config_json_es TEXT",
        "ALTER TABLE new_hires ADD COLUMN preferred_language TEXT DEFAULT 'en'",
        # Product page: target sell price + uploaded image storage key.
        "ALTER TABLE products ADD COLUMN target_price REAL DEFAULT 0",
        "ALTER TABLE products ADD COLUMN image_key TEXT",
        "ALTER TABLE products ADD COLUMN supplier TEXT",
        "ALTER TABLE products ADD COLUMN reorder_point INTEGER DEFAULT 0",
        "ALTER TABLE products ADD COLUMN parent_sku TEXT",
        "ALTER TABLE products ADD COLUMN variant_name TEXT",
        "ALTER TABLE availability ADD COLUMN end_time TEXT",
        # Show start time — used to attribute after-midnight sales to the right show.
        "ALTER TABLE show_state ADD COLUMN show_start TEXT",
        # Purchase orders: inbound tracking + attached invoice + ETA.
        "ALTER TABLE purchase_orders ADD COLUMN tracking TEXT",
        "ALTER TABLE purchase_orders ADD COLUMN carrier TEXT",
        "ALTER TABLE purchase_orders ADD COLUMN expected_at TEXT",
        "ALTER TABLE purchase_orders ADD COLUMN invoice_key TEXT",
        "ALTER TABLE purchase_orders ADD COLUMN invoice_name TEXT",
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
    # ── Table cleanup state ───────────────────────────────────────────
    # Tracks whether the warehouse manager has pulled cancelled items off
    # the table before picking starts. Keyed by (show name, SKU, Part N).
    # The /pick screen is hard-blocked from scanning until every SKU+Part
    # group for the show has a removed_at timestamp.
    c.execute("""CREATE TABLE IF NOT EXISTS cleanup_state(
        import_label TEXT NOT NULL,
        sku TEXT NOT NULL,
        part TEXT NOT NULL DEFAULT '',
        removed_at TEXT,
        removed_by TEXT,
        PRIMARY KEY (import_label, sku, part)
    )""")
    # ── New-hire onboarding system ────────────────────────────────────
    # `new_hires` is one row per candidate moving through onboarding (may
    # not yet be a real user account). `onboarding_workflows` is a template
    # (e.g. "Standard Packer Onboarding") with ordered `onboarding_steps`.
    # Per-hire status lives in `onboarding_progress`. Signatures and uploaded
    # files (ID, certifications) go in their own tables with full audit trail.
    c.execute("""CREATE TABLE IF NOT EXISTS new_hires(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        role_target TEXT,
        workflow_id INTEGER,
        invite_token TEXT UNIQUE NOT NULL,
        status TEXT DEFAULT 'invited',
        started_at TEXT,
        completed_at TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        created_by TEXT,
        notes TEXT,
        preferred_language TEXT DEFAULT 'en'
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS onboarding_workflows(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        role_target TEXT,
        is_default INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        created_by TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS onboarding_steps(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        workflow_id INTEGER NOT NULL,
        step_order INTEGER NOT NULL,
        step_type TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        body TEXT,
        config_json TEXT,
        is_required INTEGER DEFAULT 1,
        title_es TEXT,
        description_es TEXT,
        body_es TEXT,
        config_json_es TEXT,
        FOREIGN KEY (workflow_id) REFERENCES onboarding_workflows(id) ON DELETE CASCADE
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS onboarding_progress(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        hire_id INTEGER NOT NULL,
        step_id INTEGER NOT NULL,
        status TEXT DEFAULT 'pending',
        started_at TEXT,
        completed_at TEXT,
        data_json TEXT,
        UNIQUE (hire_id, step_id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS onboarding_signatures(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        hire_id INTEGER NOT NULL,
        step_id INTEGER NOT NULL,
        document_title TEXT,
        signed_name TEXT NOT NULL,
        signature_type TEXT DEFAULT 'typed',
        signature_data TEXT,
        document_hash TEXT,
        signed_at TEXT DEFAULT CURRENT_TIMESTAMP,
        ip_address TEXT,
        user_agent TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS onboarding_uploads(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        hire_id INTEGER NOT NULL,
        step_id INTEGER NOT NULL,
        field_name TEXT,
        original_filename TEXT,
        storage_key TEXT,
        mime_type TEXT,
        size_bytes INTEGER,
        uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_hires_token ON new_hires(invite_token)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_progress_hire ON onboarding_progress(hire_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_steps_wf ON onboarding_steps(workflow_id, step_order)")
    # Indexes
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_ship_tracking ON shipments(tracking_code) WHERE tracking_code IS NOT NULL")
    c.execute("CREATE INDEX IF NOT EXISTS idx_ship_status ON shipments(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_ship_imported ON shipments(imported_at DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_items_ship ON shipment_items(shipment_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_items_sku ON shipment_items(sku)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_items_order ON shipment_items(order_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_ship_batch ON shipments(import_batch)")
    # Per-show manual state: lets a manager mark a show DONE after verifying pending.
    c.execute("""CREATE TABLE IF NOT EXISTS show_state(
        import_label TEXT PRIMARY KEY,
        done INTEGER DEFAULT 0,
        done_at TEXT,
        done_by TEXT,
        show_start TEXT
    )""")
    # Key/value settings: manager PIN hash, permissions config, etc.
    c.execute("""CREATE TABLE IF NOT EXISTS settings(
        key TEXT PRIMARY KEY,
        value TEXT
    )""")
    # ── INVENTORY & COSTING ─────────────────────────────────
    # Product catalog (keyed by SKU). avg_cost = weighted-average cost from receiving.
    c.execute("""CREATE TABLE IF NOT EXISTS products(
        sku TEXT PRIMARY KEY,
        name TEXT,
        barcode TEXT,
        image_url TEXT,
        image_key TEXT,
        category TEXT,
        supplier TEXT,
        avg_cost REAL DEFAULT 0,
        target_price REAL DEFAULT 0,
        reorder_point INTEGER DEFAULT 0,
        on_hand INTEGER DEFAULT 0,
        parent_sku TEXT,
        variant_name TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode)")
    c.execute("""CREATE TABLE IF NOT EXISTS purchase_orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier TEXT,
        status TEXT DEFAULT 'open',
        notes TEXT,
        tracking TEXT,
        carrier TEXT,
        expected_at TEXT,
        invoice_key TEXT,
        invoice_name TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        received_at TEXT,
        created_by TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS po_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        po_id INTEGER NOT NULL,
        sku TEXT,
        product_name TEXT,
        qty_ordered INTEGER DEFAULT 0,
        qty_received INTEGER DEFAULT 0,
        unit_cost REAL DEFAULT 0
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_poitems_po ON po_items(po_id)")
    # Pre-show mapping: per-show, links a generic sticker (sticker#, Part) to a real
    # catalog product. Sticker numbers are reused each show, so this is show-scoped.
    c.execute("""CREATE TABLE IF NOT EXISTS show_product_map(
        import_label TEXT,
        sticker_sku TEXT,
        part INTEGER,
        product_sku TEXT,
        depleted_qty INTEGER DEFAULT 0,
        mapped_at TEXT DEFAULT CURRENT_TIMESTAMP,
        mapped_by TEXT,
        PRIMARY KEY (import_label, sticker_sku, part)
    )""")
    # Inbound shipments — labels bought for supplier → warehouse shipments.
    c.execute("""CREATE TABLE IF NOT EXISTS inbound_shipments(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier TEXT,
        carrier TEXT,
        service TEXT,
        tracking TEXT,
        cost REAL,
        label_url TEXT,
        po_id INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        created_by TEXT,
        batch_id TEXT
    )""")
    # Receiving ledger — every stock-in with cost, for audit + weighted average.
    c.execute("""CREATE TABLE IF NOT EXISTS stock_moves(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT,
        qty INTEGER,
        unit_cost REAL,
        po_id INTEGER,
        note TEXT,
        moved_at TEXT DEFAULT CURRENT_TIMESTAMP,
        moved_by TEXT
    )""")
    # Every CSV import, keyed by a hash of the file contents — so re-uploading the
    # exact same file can be detected and flagged instead of silently re-importing.
    c.execute("""CREATE TABLE IF NOT EXISTS import_files(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_hash TEXT,
        filename TEXT,
        label TEXT,
        platform TEXT,
        rows INTEGER,
        shipments_new INTEGER,
        shipments_updated INTEGER,
        imported_at TEXT DEFAULT CURRENT_TIMESTAMP,
        imported_by TEXT
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_import_hash ON import_files(file_hash)")
    # UPS rate quotes — hold the shipment context between "get rates" and "buy label"
    # so a label can be purchased with only the rate_id (UPS rating gives no buy token).
    c.execute("""CREATE TABLE IF NOT EXISTS ship_quotes(
        id TEXT PRIMARY KEY,
        ctx TEXT,
        created REAL
    )""")
    # Per-tenant audit trail of sensitive staff actions (accountability/forensics).
    c.execute("""CREATE TABLE IF NOT EXISTS audit_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        at TEXT DEFAULT CURRENT_TIMESTAMP,
        actor TEXT,
        role TEXT,
        action TEXT,
        detail TEXT,
        ip TEXT
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_audit_at ON audit_log(at DESC)")
    # ── Live-show scheduling (roster) ──────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS channels(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        platform TEXT,
        language TEXT,
        active INTEGER DEFAULT 1,
        sort INTEGER DEFAULT 0
    )""")
    # Seed the founding tenant's real channels. Every OTHER tenant starts with an empty
    # list and adds their own — seeding these names would show one customer another
    # customer's brands.
    if org==DEFAULT_ORG and not c.execute("SELECT 1 FROM channels LIMIT 1").fetchone():
        for i,(nm,pf,lg) in enumerate([
            ("Peach Beauty Live","tiktok","en"),
            ("Peach Beauty Español","tiktok","es"),
            ("Hera Beauty","whatnot",""),
            ("5 Sec Beauty","whatnot",""),
        ]):
            c.execute("INSERT INTO channels(name,platform,language,sort) VALUES(?,?,?,?)",(nm,pf,lg,i))
    c.execute("""CREATE TABLE IF NOT EXISTS shifts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id INTEGER NOT NULL,
        shift_date TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        host_user TEXT,
        assistant_user TEXT,
        week_start TEXT,
        status TEXT DEFAULT 'proposed',
        is_exception INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_shifts_week ON shifts(week_start)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_shifts_date ON shifts(shift_date)")
    # Availability the hosts/assistants submit (which slots they CAN work).
    c.execute("""CREATE TABLE IF NOT EXISTS availability(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        week_start TEXT NOT NULL,
        shift_date TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT,
        channel_id INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_avail_week ON availability(week_start)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_avail_user ON availability(username,week_start)")
    # NOTE: the `organizations` table is the cross-tenant control plane and now
    # lives in platform.db (see pdb_init), NOT here in a per-tenant shipments.db.
    c.commit(); c.close()

# ══════════════════════════════════════════════════════════
# TENANT PROVISIONING — create/prepare a tenant's private data.
# provision_org() is idempotent: safe to call at boot for every org,
# and it's what a future SaaS signup flow calls to create a new tenant.
# ══════════════════════════════════════════════════════════
def provision_org(org):
    """Ensure a tenant's folders, JSON stores and databases exist."""
    _seed_org_files(org)
    sdb_init(org)
    gdb_init(org)

# ── Organization / branding helpers (SaaS foundation) ──────────────
def org_get(org_id):
    """Return an org's config dict, or the default org's config as a fallback."""
    c = pdb()
    row = c.execute("SELECT * FROM organizations WHERE org_id=? AND active=1", (org_id or DEFAULT_ORG,)).fetchone()
    if not row and org_id != DEFAULT_ORG:
        row = c.execute("SELECT * FROM organizations WHERE org_id=?", (DEFAULT_ORG,)).fetchone()
    c.close()
    return dict(row) if row else {"org_id": org_id or DEFAULT_ORG,
        "company_name": (org_id or DEFAULT_ORG), "brand_mark": (org_id or "BRAND")[:12].upper(),
        "brand_sub": "Employee Hub", "brand_color": "#4f46e5", "logo_url": ""}

# ── PLANS / BILLING ───────────────────────────────────────────────────────────
# Sales-led: a prospect leaves details, sales talks to them, then a super-admin opens
# a 7-day trial. When the trial ends (or payment fails) the tenant is fully locked.
TRIAL_DAYS=7
PLANS={
    "starter":   {"label":"Starter","price":149,"max_users":3,   "max_orders_day":None,
                  "blurb":"Up to 3 users"},
    "pro":       {"label":"Pro","price":399,"max_users":None,"max_orders_day":1000,
                  "blurb":"Unlimited users · up to 1,000 orders/day"},
    "enterprise":{"label":"Enterprise","price":None,"max_users":None,"max_orders_day":None,
                  "blurb":"Custom — over 1,000 orders/day"},
}
def plan_of(org_row):
    """Plan config for an org row/dict; unknown or legacy plans fall back to starter."""
    p=(org_row or {}).get("plan") or ""
    return PLANS.get(p, PLANS["starter"])

def _org_user_count(org_id):
    """How many user accounts belong to a tenant."""
    try:
        users=ldj(USERS_FILE) if os.path.exists(USERS_FILE) else {}
    except Exception:
        return 0
    return sum(1 for _,i in users.items() if (i.get("org") or DEFAULT_ORG)==org_id)

def _plan_user_limit(org_id):
    """Max users for this tenant's plan, or None for unlimited. Internal accounts and
    trials are unlimited — a prospect should be able to try the whole product."""
    b=_org_billing(org_id)
    if not b: return None
    if b.get("internal"): return None
    if (b.get("sub_status") or "")=="trialing": return None
    return PLANS.get(b.get("plan") or "", PLANS["starter"]).get("max_users")

def _plan_orders_day_limit(org_id):
    """Max orders/day for this tenant's plan, or None for unlimited."""
    b=_org_billing(org_id)
    if not b: return None
    if b.get("internal"): return None
    if (b.get("sub_status") or "")=="trialing": return None
    return PLANS.get(b.get("plan") or "", PLANS["starter"]).get("max_orders_day")

def _org_billing(org_id):
    """Raw billing fields for a tenant, or None."""
    c=pdb()
    r=c.execute("""SELECT org_id,company_name,plan,active,trial_ends_at,sub_status,
                          stripe_customer_id,stripe_subscription_id,current_period_end,
                          COALESCE(internal,0) AS internal
                   FROM organizations WHERE org_id=?""",(org_id,)).fetchone()
    c.close()
    return dict(r) if r else None

def org_access(org_id):
    """(allowed, state, info) — is this tenant allowed to USE the app right now?
    state: 'ok' | 'suspended' | 'trial_expired' | 'unpaid' | 'no_subscription'."""
    if org_id==PLATFORM_ORG:
        return True,"ok",{}
    b=_org_billing(org_id)
    if not b:
        # Unknown org: only the founding tenant is tolerated (matches org_is_active).
        return ((org_id or DEFAULT_ORG)==DEFAULT_ORG),"ok",{}
    if not b.get("active"):
        return False,"suspended",b
    if b.get("internal"):
        return True,"ok",b          # our own / demo accounts are never billed or gated
    st=(b.get("sub_status") or "none").lower()
    if st=="active":
        # Manual billing: access runs until the paid period ends. No period end set
        # means open-ended (the founding tenant / a grandfathered account).
        pe=_parse_dt(b.get("current_period_end"))
        if pe and datetime.now()>=pe:
            return False,"period_ended",b
        if pe:
            b["days_left"]=max(0,(pe-datetime.now()).days)
        return True,"ok",b
    if st=="trialing":
        end=_parse_dt(b.get("trial_ends_at"))
        if end and datetime.now()<end:
            b["trial_days_left"]=max(0,(end-datetime.now()).days)
            return True,"ok",b
        return False,"trial_expired",b
    if st in ("past_due","unpaid","canceled"):
        return False,"unpaid",b
    return False,"no_subscription",b

def org_is_active(org_id):
    """True if the tenant is active (allowed to log in). Unknown org => only the
    founding tenant passes. Does NOT fall back to default (that would mask a
    suspension), unlike org_get()."""
    if org_id==PLATFORM_ORG: return True   # the platform owner is never a tenant
    c=pdb(); r=c.execute("SELECT active FROM organizations WHERE org_id=?",(org_id or DEFAULT_ORG,)).fetchone(); c.close()
    if r is None: return (org_id or DEFAULT_ORG)==DEFAULT_ORG
    return bool(r["active"])

def brand_for_session(org_id):
    """Shape an org's branding for session['brand'] (consumed by templates._brand)."""
    if org_id==PLATFORM_ORG:
        return {"mark":"LiveOpsHub","sub":"Platform","color":"#6366f1","logo_url":"",
                "company":"LiveOpsHub","org_id":PLATFORM_ORG}
    o = org_get(org_id)
    # Fallbacks are derived from the tenant's OWN company name — never another
    # tenant's brand.
    _co = o.get("company_name") or (org_id or DEFAULT_ORG)
    return {"mark": o.get("brand_mark") or _co[:12].upper(),
            "sub": o.get("brand_sub") or "Employee Hub",
            "color": o.get("brand_color") or "#4f46e5",
            "logo_url": o.get("logo_url") or "",
            "company": _co,
            "org_id": o.get("org_id") or DEFAULT_ORG}


# ══════════════════════════════════════════════════════════
# ONE-TIME LEGACY MIGRATION — single-tenant → per-org folders.
# Existing installs kept everything flat under DATA_DIR. Move that data
# into /data/orgs/<DEFAULT_ORG>/ exactly once. Idempotent + lock-guarded.
# BACK UP the /data volume before first deploy, just in case.
# ══════════════════════════════════════════════════════════
def _migrate_legacy_to_default_org():
    import shutil
    marker=org_path(DEFAULT_ORG,".migrated")
    if os.path.exists(marker):
        return  # already migrated — nothing to do
    legacy_ship=os.path.join(DATA_DIR,"shipments.db")
    if not os.path.exists(legacy_ship):
        return  # fresh install, no legacy data (marker written after provision seeds)
    print("[migrate] copying legacy single-tenant data into org", DEFAULT_ORG, flush=True)
    os.makedirs(org_path(DEFAULT_ORG), exist_ok=True)
    # 1) Preserve any customized org/branding rows from the old shipments.db.
    try:
        lc=sqlite3.connect(legacy_ship); lc.row_factory=sqlite3.Row
        if lc.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='organizations'").fetchone():
            pc=pdb()
            for r in lc.execute("SELECT * FROM organizations").fetchall():
                r=dict(r)
                pc.execute("""INSERT INTO organizations
                        (org_id,company_name,brand_mark,brand_sub,brand_color,logo_url,plan,active,created_at)
                        VALUES(?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(org_id) DO UPDATE SET
                          company_name=excluded.company_name, brand_mark=excluded.brand_mark,
                          brand_sub=excluded.brand_sub, brand_color=excluded.brand_color,
                          logo_url=excluded.logo_url, plan=excluded.plan, active=excluded.active""",
                    (r.get("org_id"),r.get("company_name"),r.get("brand_mark"),r.get("brand_sub"),
                     r.get("brand_color"),r.get("logo_url"),r.get("plan"),r.get("active",1),r.get("created_at")))
            pc.commit(); pc.close()
        lc.close()
    except Exception as e:
        print("[migrate] org-row import warning:", e, flush=True)
    # 2) COPY the databases + JSON stores (small; originals stay at the /data root
    #    as an automatic backup). MOVE the media dirs (usually absent when R2 is on).
    def _cp(src,dst):
        if os.path.exists(src) and not os.path.exists(dst):
            os.makedirs(os.path.dirname(dst),exist_ok=True)
            shutil.copy2(src,dst)
    def _mv_dir(src,dst):
        if os.path.isdir(src) and not os.path.exists(dst):
            os.makedirs(os.path.dirname(dst),exist_ok=True)
            shutil.move(src,dst)
    for base in ("shipments.db","giveaways.db"):
        for suf in ("","-wal","-shm"):
            _cp(os.path.join(DATA_DIR,base+suf), org_path(DEFAULT_ORG,base+suf))
    _cp(os.path.join(DATA_DIR,"packing_log.csv"), log_file(DEFAULT_ORG))
    _cp(os.path.join(DATA_DIR,"documents.json"),  docs_file(DEFAULT_ORG))
    _cp(os.path.join(DATA_DIR,"onboarding.json"), onb_file(DEFAULT_ORG))
    _cp(os.path.join(DATA_DIR,"announcements.json"), ann_file(DEFAULT_ORG))
    _mv_dir(os.path.join(DATA_DIR,"videos"),    video_dir(DEFAULT_ORG))
    _mv_dir(os.path.join(DATA_DIR,"photos"),    photo_dir(DEFAULT_ORG))
    _mv_dir(os.path.join(DATA_DIR,"documents"), docs_dir(DEFAULT_ORG))
    with open(marker,"w") as f: f.write(datetime.now().isoformat())
    print("[migrate] done — legacy DBs copied into", org_path(DEFAULT_ORG),
          "(originals kept at /data root as backup)", flush=True)

# ── Boot: migrate legacy data once, then provision every known tenant. ──
with _flock("provision"):
    try:
        _migrate_legacy_to_default_org()
    except Exception as e:
        print("[migrate] FAILED:", e, flush=True)
    for _org in list_org_ids():
        try: provision_org(_org)
        except Exception as e: print("provision failed for", _org, ":", e, flush=True)


# ══════════════════════════════════════════════════════════
# USPS DELIVERY TRACKING — official USPS v3 API (developers.usps.com)
# OAuth2 client_credentials → Tracking API. Env-driven; no-op if unset.
# Set USPS_CLIENT_ID / USPS_CLIENT_SECRET on Railway to enable.
# ══════════════════════════════════════════════════════════
import urllib.request as _urlreq, urllib.parse as _urlparse, urllib.error as _urlerr

USPS_CLIENT_ID=os.environ.get("USPS_CLIENT_ID")
USPS_CLIENT_SECRET=os.environ.get("USPS_CLIENT_SECRET")
USPS_BASE=os.environ.get("USPS_BASE","https://apis.usps.com").rstrip("/")
USPS_ENABLED=bool(USPS_CLIENT_ID and USPS_CLIENT_SECRET)
_usps_tok={"token":None,"exp":0}
_usps_lock=threading.Lock()

def _usps_token():
    """Valid OAuth bearer token, refreshing if needed (USPS tokens last ~8h)."""
    with _usps_lock:
        if _usps_tok["token"] and time.time()<_usps_tok["exp"]-120:
            return _usps_tok["token"]
        # USPS v3 token endpoint expects a JSON body (per USPS/api-examples), not form-encoded.
        body=json.dumps({"client_id":USPS_CLIENT_ID,"client_secret":USPS_CLIENT_SECRET,
                         "grant_type":"client_credentials"}).encode()
        req=_urlreq.Request(USPS_BASE+"/oauth2/v3/token",data=body,
            headers={"Content-Type":"application/json","Accept":"application/json"})
        with _urlreq.urlopen(req,timeout=20) as r:
            d=json.loads(r.read().decode())
        _usps_tok["token"]=d.get("access_token")
        _usps_tok["exp"]=time.time()+int(d.get("expires_in",3600))
        return _usps_tok["token"]

_USPS_BUCKET={"pre-shipment":"PRE_TRANSIT","pre shipment":"PRE_TRANSIT","accepted":"IN_TRANSIT",
    "in transit":"IN_TRANSIT","in-transit":"IN_TRANSIT","out for delivery":"OUT_FOR_DELIVERY",
    "delivered":"DELIVERED","available for pickup":"OUT_FOR_DELIVERY","alert":"EXCEPTION",
    "delivery attempt":"EXCEPTION","return to sender":"RETURNED"}

def _norm_usps_status(cat, status_text):
    c=(cat or "").strip().lower()
    if c in _USPS_BUCKET: return _USPS_BUCKET[c]
    s=(status_text or "").lower()
    if "delivered" in s: return "DELIVERED"
    if "out for delivery" in s: return "OUT_FOR_DELIVERY"
    if "return" in s: return "RETURNED"
    if "alert" in s or "no record" in s: return "EXCEPTION"
    if "pre-shipment" in s or ("label" in s and "created" in s): return "PRE_TRANSIT"
    return "IN_TRANSIT" if s else "UNKNOWN"

def _parse_track_detail(d):
    """Map one USPS TrackingDetail object → {status,detail,delivered_at}."""
    bucket=_norm_usps_status(d.get("statusCategory"), d.get("status") or "")
    events=d.get("trackingEvents") or []
    delivered_at=None
    for ev in events:
        if "delivered" in (ev.get("eventType") or "").lower():
            delivered_at=ev.get("eventTimestamp"); break
    if bucket=="DELIVERED" and not delivered_at and events:
        delivered_at=events[0].get("eventTimestamp")   # events are reverse-chronological
    detail=(d.get("statusSummary") or d.get("status") or (events[0].get("eventType") if events else "")) or ""
    return {"status":bucket,"detail":detail[:200],"delivered_at":delivered_at}

# Which tracking API the account actually serves. Auto-detected: we try the modern
# v3r2 (POST, batched) first; if that endpoint isn't available we fall back to the
# legacy v3 (GET, one number per call). Both use the same OAuth credentials.
_usps_mode={"v":"v3r2"}

def _usps_track_v3(tn):
    """Legacy v3: GET /tracking/v3/tracking/{trackingNumber}."""
    try:
        tok=_usps_token()
        url=USPS_BASE+"/tracking/v3/tracking/"+_urlparse.quote(tn)
        req=_urlreq.Request(url,headers={"Authorization":"Bearer "+tok,"Accept":"application/json"})
        with _urlreq.urlopen(req,timeout=20) as r:
            d=json.loads(r.read().decode())
        return _parse_track_detail(d)
    except _urlerr.HTTPError as e:
        if e.code==404: return {"status":"UNKNOWN","detail":"No USPS record yet","delivered_at":None}
        print("USPS v3 HTTP",e.code,"for",tn,flush=True); return None
    except Exception as e:
        print("USPS v3 failed",tn,":",e,flush=True); return None

def _usps_track_batch(tns):
    """Return {trackingNumber: {status,detail,delivered_at}} for up to 35 numbers.
    Prefers v3r2 (POST array, 200/207 both return arrays); auto-falls back to v3 GET."""
    out={}
    if not USPS_ENABLED or not tns: return out
    if _usps_mode["v"]=="v3":
        for t in tns:
            r=_usps_track_v3(t)
            if r: out[t]=r
        return out
    try:
        tok=_usps_token()
        body=json.dumps([{"trackingNumber":t} for t in tns]).encode()
        req=_urlreq.Request(USPS_BASE+"/tracking/v3r2/tracking",data=body,
            headers={"Authorization":"Bearer "+tok,"Content-Type":"application/json","Accept":"application/json"})
        with _urlreq.urlopen(req,timeout=30) as r:
            data=json.loads(r.read().decode())
        if isinstance(data,dict): data=[data]
        for item in (data or []):
            tn=item.get("trackingNumber")
            if not tn: continue
            if item.get("statusCategory") or item.get("status"):
                out[tn]=_parse_track_detail(item)
            else:
                out[tn]={"status":"UNKNOWN","detail":"No USPS record yet","delivered_at":None}
        return out
    except _urlerr.HTTPError as e:
        if e.code in (403,404,405,415):  # endpoint/method/entitlement → try legacy v3 GET
            print("USPS v3r2 returned HTTP",e.code,"— switching to legacy v3 GET",flush=True)
            _usps_mode["v"]="v3"
            return _usps_track_batch(tns)
        print("USPS track HTTP",e.code,flush=True); return out
    except Exception as e:
        print("USPS track batch failed:",e,flush=True); return out

def _is_usps_tracking(t):
    """True only for plausible USPS tracking numbers, so we don't waste calls (and
    trigger 400s) on Whatnot/other-platform IDs stored in the tracking field.
    USPS domestic IMpb = 20-34 digits starting with 9 (or a 420+ZIP routing prefix);
    international = 2 letters + 9 digits + 2 letters (e.g. EA123456789US)."""
    t=(t or "").strip().upper()
    if re.match(r'^[A-Z]{2}\d{9}[A-Z]{2}$', t): return True
    if t.isdigit() and 20<=len(t)<=34 and (t[0]=='9' or t.startswith('420')): return True
    return False

def refresh_tracking_batch(org=None, limit=120):
    """Poll USPS for one tenant's not-yet-delivered shipments; update rows.
    Batches 30 tracking numbers per request. Bounded per call and idempotent.
    Non-USPS tracking codes (Whatnot/other platforms) are skipped."""
    if not USPS_ENABLED: return {"checked":0,"updated":0,"note":"usps_disabled"}
    c=sdb(org)
    rows=c.execute("""SELECT shipment_id,tracking_code FROM shipments
                      WHERE tracking_code IS NOT NULL AND tracking_code!=''
                        AND (tracking_code GLOB '9*' OR tracking_code GLOB '420*'
                             OR tracking_code GLOB '[A-Z][A-Z]*')
                        AND COALESCE(delivery_status,'') NOT IN ('DELIVERED','RETURNED')
                      ORDER BY COALESCE(tracked_at,'') ASC LIMIT ?""",(limit,)).fetchall()
    by_tn={}; skipped=0
    for r in rows:
        if _is_usps_tracking(r["tracking_code"]):
            by_tn.setdefault(r["tracking_code"], r["shipment_id"])
        else:
            skipped+=1
    tns=list(by_tn.keys())
    checked=0;updated=0;now=datetime.now().isoformat(timespec='seconds')
    for i in range(0,len(tns),30):
        chunk=tns[i:i+30]; checked+=len(chunk)
        res=_usps_track_batch(chunk)
        for tn,info in res.items():
            sid=by_tn.get(tn)
            if not sid: continue
            c.execute("""UPDATE shipments SET delivery_status=?,delivery_detail=?,
                            delivered_at=COALESCE(?,delivered_at),tracked_at=? WHERE shipment_id=?""",
                      (info["status"],info["detail"],info["delivered_at"],now,sid))
            updated+=1
        c.commit(); time.sleep(0.4)
    c.close()
    return {"checked":checked,"updated":updated,"skipped_non_usps":skipped}

def _tracking_loop():
    # Refresh a few times a day. A shared marker file on the Railway volume keeps
    # the 4 gunicorn workers from all polling at once.
    while True:
        time.sleep(6*3600)
        if not USPS_ENABLED: continue
        try:
            marker=os.path.join(DATA_DIR,".tracking_last")
            last=os.path.getmtime(marker) if os.path.exists(marker) else 0
            if time.time()-last < 5*3600: continue
            open(marker,"w").close()
            for _org in list_org_ids():
                try: refresh_tracking_batch(org=_org, limit=600)
                except Exception as e: print("tracking error for",_org,":",e,flush=True)
        except Exception as e:
            print("tracking loop error:",e,flush=True)

if USPS_ENABLED:
    threading.Thread(target=_tracking_loop,daemon=True).start()
    print("USPS tracking enabled (base="+USPS_BASE+")",flush=True)
else:
    print("USPS tracking not configured — set USPS_CLIENT_ID / USPS_CLIENT_SECRET to enable",flush=True)

# ── SHIPSTATION (API V2) — buy shipping labels (giveaways + inbound). ──────────
# api.shipstation.com, single API key in the "API-Key" header. Rate → buy flow,
# carriers connected inside your ShipStation account. The helpers below return
# EasyPost-shaped output so the existing label routes work unchanged.
import base64 as _b64
SHIPSTATION_API_KEY=os.environ.get("SHIPSTATION_API_KEY") or os.environ.get("SHIPSTATION_KEY")
SHIPSTATION_ENABLED=bool(SHIPSTATION_API_KEY)
SHIPSTATION_BASE=os.environ.get("SHIPSTATION_BASE","https://api.shipstation.com")

# ── UPS DIRECT (own account, OAuth client-credentials) ─────────────────────────
# When these three env vars are set, labels go straight to UPS — no middleman.
# UPS takes priority over ShipStation; ShipStation stays as a fallback so nothing
# breaks before UPS is configured.
UPS_CLIENT_ID=os.environ.get("UPS_CLIENT_ID","").strip()
UPS_CLIENT_SECRET=os.environ.get("UPS_CLIENT_SECRET","").strip()
UPS_ACCOUNT_NUMBER=os.environ.get("UPS_ACCOUNT_NUMBER","").strip()
UPS_ENABLED=bool(UPS_CLIENT_ID and UPS_CLIENT_SECRET and UPS_ACCOUNT_NUMBER)
UPS_ENV=(os.environ.get("UPS_ENV","production") or "production").lower()
UPS_BASE=os.environ.get("UPS_BASE") or ("https://wwwcie.ups.com" if UPS_ENV in ("test","cie","sandbox") else "https://onlinetools.ups.com")
UPS_RATE_VERSION=os.environ.get("UPS_RATE_VERSION","v2409")
UPS_SHIP_VERSION=os.environ.get("UPS_SHIP_VERSION","v2409")

EASYPOST_ENABLED=bool(UPS_ENABLED or SHIPSTATION_ENABLED)   # back-compat alias used by the label routes

def _ss(method, path, payload=None):
    """Call the ShipStation V2 API. Raises RuntimeError('ShipStation: <msg>') on error."""
    data=json.dumps(payload).encode() if payload is not None else None
    req=_urlreq.Request(SHIPSTATION_BASE+path, data=data, method=method,
        headers={"API-Key":SHIPSTATION_API_KEY or "","Content-Type":"application/json","Accept":"application/json"})
    try:
        with _urlreq.urlopen(req, timeout=45) as r:
            return json.loads(r.read().decode())
    except _urlerr.HTTPError as e:
        try:
            b=json.loads(e.read().decode())
            msg=(b.get("errors") or [{}])[0].get("message") or b.get("message") or ("HTTP "+str(e.code))
        except Exception: msg="HTTP "+str(e.code)
        raise RuntimeError("ShipStation: "+str(msg))

_ss_carriers={"ids":None,"ts":0}
def _ship_carrier_ids(force=False):
    """Carrier IDs connected in the ShipStation account (cached 10min). Rates need these.
    Pass force=True to bust the cache after connecting a new carrier (e.g. UPS)."""
    if not force and _ss_carriers["ids"] is not None and time.time()-_ss_carriers["ts"]<600:
        return _ss_carriers["ids"]
    r=_ss("GET","/v2/carriers")
    ids=[c.get("carrier_id") for c in (r.get("carriers") or []) if c.get("carrier_id")]
    _ss_carriers["ids"]=ids; _ss_carriers["ts"]=time.time()
    return ids

def _ship_addr(a):
    out={"name":a.get("name") or "Recipient",
         "address_line1":a.get("street1") or "","address_line2":a.get("street2") or "",
         "city_locality":a.get("city") or "","state_province":a.get("state") or "",
         "postal_code":a.get("zip") or "","country_code":(a.get("country") or "US")}
    if a.get("phone"): out["phone"]=a.get("phone")
    if a.get("company"): out["company_name"]=a.get("company")
    return out

def _ship_rates(to, frm, weight, dims):
    """(shipment_id, [rates]) — rate dict shaped like EasyPost: id/carrier/service/rate/days.
    Routes to UPS direct when configured, else falls back to ShipStation."""
    if UPS_ENABLED:
        return _ups_rates(to, frm, weight, dims)
    pkg={"weight":{"value":float(weight),"unit":"ounce"}}
    dd={}
    for k in ("length","width","height"):
        try:
            if dims.get(k): dd[k]=float(dims[k])
        except Exception: pass
    if len(dd)==3: pkg["dimensions"]=dict(unit="inch",**dd)
    body={"rate_options":{"carrier_ids":_ship_carrier_ids()},
          "shipment":{"ship_from":_ship_addr(frm),"ship_to":_ship_addr(to),"packages":[pkg]}}
    resp=_ss("POST","/v2/rates",body)
    rr=resp.get("rate_response") or {}
    rates=[]
    for r in (rr.get("rates") or []):
        amt=(r.get("shipping_amount") or {}).get("amount")
        rates.append({"id":r.get("rate_id"),
                      "carrier":r.get("carrier_friendly_name") or r.get("carrier_code"),
                      "service":r.get("service_type") or r.get("service_code"),
                      "rate":amt,"days":r.get("delivery_days")})
    rates.sort(key=lambda x: float(x["rate"] if x["rate"] is not None else 9999))
    return resp.get("shipment_id"), rates

def _ship_buy(rate_id):
    """Purchase a label for a rate. Returns EasyPost-shaped dict so routes are unchanged.
    Routes to UPS direct when configured, else ShipStation."""
    if UPS_ENABLED:
        return _ups_buy(rate_id)
    lbl=_ss("POST","/v2/labels/rates/"+str(rate_id),{"label_layout":"4x6","label_format":"pdf"})
    dl=lbl.get("label_download") or {}
    url=dl.get("pdf") or dl.get("href") or dl.get("png")
    cost=float((lbl.get("shipment_cost") or {}).get("amount") or 0)
    return {"postage_label":{"label_url":url},"tracking_code":lbl.get("tracking_number"),
            "selected_rate":{"rate":cost,"carrier":lbl.get("carrier_code"),"service":lbl.get("service_code")}}

# ═══════════════════════════════════════════════════════════════════════════════
# UPS DIRECT — OAuth client-credentials + Rating (Shop) + Shipping (label).
# Returns EasyPost-shaped output so the existing label routes are unchanged.
# ═══════════════════════════════════════════════════════════════════════════════
UPS_SERVICE_NAMES={"01":"UPS Next Day Air","02":"UPS 2nd Day Air","03":"UPS Ground",
    "12":"UPS 3 Day Select","13":"UPS Next Day Air Saver","14":"UPS Next Day Air Early",
    "59":"UPS 2nd Day Air AM","07":"UPS Worldwide Express","08":"UPS Worldwide Expedited",
    "11":"UPS Standard","54":"UPS Worldwide Express Plus","65":"UPS Worldwide Saver",
    "70":"UPS Access Point Economy","82":"UPS Today Standard","83":"UPS Today Dedicated Courier",
    "85":"UPS Today Express","86":"UPS Today Express Saver"}

_ups_tok={"tok":None,"exp":0}
def _ups_token():
    """Cached OAuth bearer token (client-credentials). Refreshes 5 min before expiry."""
    if _ups_tok["tok"] and time.time()<_ups_tok["exp"]-300:
        return _ups_tok["tok"]
    auth=_b64.b64encode((UPS_CLIENT_ID+":"+UPS_CLIENT_SECRET).encode()).decode()
    body="grant_type=client_credentials".encode()
    req=_urlreq.Request(UPS_BASE+"/security/v1/oauth/token", data=body, method="POST",
        headers={"Authorization":"Basic "+auth,"Content-Type":"application/x-www-form-urlencoded","Accept":"application/json"})
    try:
        with _urlreq.urlopen(req, timeout=45) as r:
            d=json.loads(r.read().decode())
    except _urlerr.HTTPError as e:
        try: msg=json.loads(e.read().decode()).get("response",{}).get("errors",[{}])[0].get("message") or ("HTTP "+str(e.code))
        except Exception: msg="HTTP "+str(e.code)
        raise RuntimeError("UPS auth: "+str(msg))
    _ups_tok["tok"]=d.get("access_token")
    try: _ups_tok["exp"]=time.time()+float(d.get("expires_in") or 3600)
    except Exception: _ups_tok["exp"]=time.time()+3600
    return _ups_tok["tok"]

def _ups(method, path, payload=None):
    """Call a UPS REST API with a bearer token. Raises RuntimeError('UPS: <msg>')."""
    data=json.dumps(payload).encode() if payload is not None else None
    req=_urlreq.Request(UPS_BASE+path, data=data, method=method,
        headers={"Authorization":"Bearer "+_ups_token(),"Content-Type":"application/json",
                 "Accept":"application/json","transId":secrets.token_hex(8),"transactionSrc":"liveopshub"})
    try:
        with _urlreq.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except _urlerr.HTTPError as e:
        try:
            b=json.loads(e.read().decode())
            errs=(b.get("response") or {}).get("errors") or b.get("errors") or [{}]
            msg=errs[0].get("message") or ("HTTP "+str(e.code))
            if errs[0].get("code"): msg=str(errs[0]["code"])+": "+msg
        except Exception: msg="HTTP "+str(e.code)
        raise RuntimeError("UPS: "+str(msg))

def _ups_addr(a):
    """Map an internal address dict to a UPS Address block."""
    lines=[a.get("street1") or ""]
    if a.get("street2"): lines.append(a.get("street2"))
    return {"AddressLine":lines,"City":a.get("city") or "","StateProvinceCode":a.get("state") or "",
            "PostalCode":a.get("zip") or "","CountryCode":a.get("country") or "US"}

def _ups_party(a, with_acct=False):
    p={"Name":(a.get("name") or a.get("company") or "Shipper")[:35],"Address":_ups_addr(a)}
    if a.get("phone"): p["Phone"]={"Number":"".join(ch for ch in str(a.get("phone")) if ch.isdigit())[:15]}
    if with_acct: p["ShipperNumber"]=UPS_ACCOUNT_NUMBER
    return p

def _ups_package(weight_oz, dims, for_ship=False):
    lbs=max(round(float(weight_oz or 0)/16.0,1),0.1)
    pkg={("Packaging" if for_ship else "PackagingType"):{"Code":"02","Description":"Package"},
         "PackageWeight":{"UnitOfMeasurement":{"Code":"LBS"},"Weight":str(lbs)}}
    dd={}
    for k in ("length","width","height"):
        try:
            if dims.get(k): dd[k]=str(int(round(float(dims[k]))))
        except Exception: pass
    if len(dd)==3:
        pkg["Dimensions"]={"UnitOfMeasurement":{"Code":"IN"},"Length":dd["length"],"Width":dd["width"],"Height":dd["height"]}
    return pkg

def _ship_quote_save(quote_id, ctx):
    """Persist a rate quote's shipment context (per-org) so a label can be bought later."""
    try:
        c=sdb()
        c.execute("INSERT OR REPLACE INTO ship_quotes(id,ctx,created) VALUES(?,?,?)",
                  (quote_id,json.dumps(ctx),time.time()))
        # prune quotes older than 24h to keep the table tiny
        c.execute("DELETE FROM ship_quotes WHERE created < ?",(time.time()-86400,))
        c.commit(); c.close()
    except Exception as e:
        print("ship_quote save failed:",e,flush=True)

def _ship_quote_load(quote_id):
    try:
        c=sdb()
        r=c.execute("SELECT ctx FROM ship_quotes WHERE id=?",(quote_id,)).fetchone()
        c.close()
        return json.loads(r["ctx"]) if r and r["ctx"] else None
    except Exception as e:
        print("ship_quote load failed:",e,flush=True); return None

def _ups_rates(to, frm, weight, dims):
    """(quote_id, [rates]) — Shop all UPS services. Persists the quote so a label can be
    bought later with just the rate_id (which encodes quote_id + service code)."""
    biz=_ship_from() or frm
    shipment={"Shipper":_ups_party(biz, with_acct=True),
              "ShipFrom":_ups_party(frm),"ShipTo":_ups_party(to),
              "Package":[_ups_package(weight, dims, for_ship=False)]}
    body={"RateRequest":{"Request":{"SubVersion":UPS_RATE_VERSION.lstrip("v"),
              "RequestOption":"Shop","TransactionReference":{"CustomerContext":"rate"}},
          "Shipment":shipment}}
    resp=_ups("POST","/api/rating/"+UPS_RATE_VERSION+"/Shop",body)
    rr=resp.get("RateResponse") or {}
    rated=rr.get("RatedShipment") or []
    if isinstance(rated,dict): rated=[rated]
    quote_id="upsq_"+secrets.token_hex(8)
    _ship_quote_save(quote_id, {"to":to,"frm":frm,"weight_oz":weight,"dims":dims})
    rates=[]
    for rs in rated:
        code=((rs.get("Service") or {}).get("Code")) or ""
        tot=(rs.get("TotalCharges") or {}).get("MonetaryValue")
        days=(rs.get("GuaranteedDelivery") or {}).get("BusinessDaysInTransit")
        rates.append({"id":quote_id+"~"+code,"carrier":"UPS",
                      "service":UPS_SERVICE_NAMES.get(code,"UPS "+code),
                      "rate":tot,"days":days})
    rates.sort(key=lambda x: float(x["rate"] if x["rate"] is not None else 9999))
    return quote_id, rates

def _ups_buy(rate_id):
    """Buy a UPS label. rate_id = '<quote_id>~<serviceCode>'. Returns EasyPost-shaped dict."""
    quote_id,_,code=str(rate_id).partition("~")
    ctx=_ship_quote_load(quote_id)
    if not ctx: raise RuntimeError("UPS: quote expired — get rates again")
    to=ctx["to"]; frm=ctx["frm"]; biz=_ship_from() or frm
    shipment={"Description":"Merchandise",
              "Shipper":_ups_party(biz, with_acct=True),
              "ShipFrom":_ups_party(frm),"ShipTo":_ups_party(to),
              "PaymentInformation":{"ShipmentCharge":[{"Type":"01","BillShipper":{"AccountNumber":UPS_ACCOUNT_NUMBER}}]},
              "Service":{"Code":code or "03","Description":UPS_SERVICE_NAMES.get(code,"UPS")},
              "Package":[_ups_package(ctx.get("weight_oz"), ctx.get("dims") or {}, for_ship=True)]}
    body={"ShipmentRequest":{"Request":{"SubVersion":UPS_SHIP_VERSION.lstrip("v"),
              "RequestOption":"nonvalidate","TransactionReference":{"CustomerContext":"ship"}},
          "Shipment":shipment,
          "LabelSpecification":{"LabelImageFormat":{"Code":"GIF"},"LabelStockSize":{"Height":"6","Width":"4"}}}}
    resp=_ups("POST","/api/shipments/"+UPS_SHIP_VERSION+"/ship",body)
    sr=(resp.get("ShipmentResponse") or {})
    res=(sr.get("ShipmentResults") or {})
    pkgs=res.get("PackageResults") or []
    if isinstance(pkgs,dict): pkgs=[pkgs]
    tracking=(pkgs[0].get("TrackingNumber") if pkgs else None) or res.get("ShipmentIdentificationNumber")
    img=((pkgs[0].get("ShippingLabel") or {}).get("GraphicImage")) if pkgs else None
    label_url=None
    if img:
        try: label_url=_store_label(_b64.b64decode(img),"gif")
        except Exception as e: print("UPS label store failed:",e,flush=True)
    cost=0.0
    try: cost=float((res.get("ShipmentCharges") or {}).get("TotalCharges",{}).get("MonetaryValue") or 0)
    except Exception: pass
    return {"postage_label":{"label_url":label_url},"tracking_code":tracking,
            "selected_rate":{"rate":cost,"carrier":"UPS","service":UPS_SERVICE_NAMES.get(code,"UPS")}}

def _labels_dir(org=None):
    d=org_path(_org_or_current(org),"labels"); os.makedirs(d,exist_ok=True); return d

def _store_label(data, ext):
    """Persist raw label bytes (R2 if configured, else local) and return a served URL
    that ends in .<ext> so the print pages render it correctly."""
    fn=secrets.token_hex(10)+"."+ext
    if r2:
        try:
            ct={"gif":"image/gif","png":"image/png","pdf":"application/pdf"}.get(ext,"application/octet-stream")
            r2.put_object(Bucket=R2_BUCKET,Key=_r2_media_key("labels",fn),Body=data,ContentType=ct)
            return "/label/file/"+fn
        except Exception as e:
            print("R2 label put failed:",e,flush=True)
    with open(os.path.join(_labels_dir(),fn),"wb") as fh: fh.write(data)
    return "/label/file/"+fn

print("UPS direct "+("enabled (base="+UPS_BASE+")" if UPS_ENABLED else "not configured — set UPS_CLIENT_ID / UPS_CLIENT_SECRET / UPS_ACCOUNT_NUMBER"),flush=True)
print("ShipStation "+("enabled" if SHIPSTATION_ENABLED else "not configured — set SHIPSTATION_API_KEY"),flush=True)


def _weight_config():
    """Get singleton weight config row."""
    c = sdb()
    row = c.execute("SELECT * FROM weight_config WHERE id=1").fetchone()
    c.close()
    return dict(row) if row else {"tolerance_percent": 10, "tolerance_absolute_g": 5, "packaging_overhead_g": 30}


# ──────────────────────────────────────────────────────────────────────
# CANCELLATION CLEANUP HELPERS
# ──────────────────────────────────────────────────────────────────────
# A "table cleanup" pass happens before pickers start: the manager directs
# workers to physically pull every cancelled item off the warehouse table
# so whatever remains is known-good. State is per show + SKU + Part.
# A show is "clean" iff every cancelled (sku, part) group has been marked.
# ──────────────────────────────────────────────────────────────────────
import re as _re_cleanup
def _parse_dt(s):
    """Parse a sale timestamp from TikTok / Whatnot / ISO exports into a datetime.
    Returns None when it can't. Handles '07/15/2026 1:19:13 PM', ISO 8601, etc."""
    if not s: return None
    s=str(s).strip()
    if not s: return None
    # Strip a trailing timezone label some exports add (e.g. ' UTC', ' PDT').
    for tz in (" UTC"," GMT"," PST"," PDT"," EST"," EDT"," CST"," CDT"," MST"," MDT"):
        if s.upper().endswith(tz): s=s[:-len(tz)].strip()
    fmts=("%m/%d/%Y %I:%M:%S %p","%m/%d/%Y %I:%M %p","%m/%d/%Y %H:%M:%S","%m/%d/%Y %H:%M",
          "%Y-%m-%d %H:%M:%S","%Y-%m-%dT%H:%M:%S","%Y-%m-%dT%H:%M","%Y-%m-%d %H:%M","%m/%d/%Y","%Y-%m-%d")
    for f in fmts:
        try: return datetime.strptime(s, f)
        except Exception: pass
    # Last resort: ISO with timezone offset (strip the offset).
    try:
        return datetime.fromisoformat(s.replace("Z","").split("+")[0].strip())
    except Exception:
        return None

def _load_show_windows(c, extra_label=None, extra_start=None):
    """Return [(label, start_datetime), ...] sorted by start, for every show that has a
    show_start. Optionally include an in-flight (label,start) not yet committed."""
    rows=c.execute("SELECT import_label, show_start FROM show_state WHERE show_start IS NOT NULL AND show_start!=''").fetchall()
    wins={}
    for r in rows:
        dt=_parse_dt(r["show_start"])
        if dt: wins[r["import_label"]]=dt
    if extra_label and extra_start: wins[extra_label]=extra_start
    return sorted(wins.items(), key=lambda kv: kv[1])

def _owning_show(created_dt, windows, default_label):
    """The show whose window contains this sale = the one with the greatest start
    that is <= the sale time. Falls back to default_label (e.g. sale before any show)."""
    if not created_dt or not windows: return default_label
    owner=None; best=None
    for lbl,start in windows:
        if start<=created_dt and (best is None or start>best):
            best=start; owner=lbl
    return owner or default_label

def _extract_part(product_name):
    """Pull a 'Part N' label out of a product name. Returns empty string when
    there's no part suffix — that's the normal case for non-TikTok shows."""
    if not product_name:
        return ""
    m = _re_cleanup.search(r"Part\s*(\d+)", product_name, _re_cleanup.IGNORECASE)
    return f"Part {m.group(1)}" if m else ""

def _part_num(product_name):
    """Integer Part number from a product name, or 0 when there's no Part suffix."""
    if not product_name:
        return 0
    m = _re_cleanup.search(r"Part\s*(\d+)", product_name, _re_cleanup.IGNORECASE)
    return int(m.group(1)) if m else 0

def _cleanup_groups(label):
    """Aggregate cancelled items for a show into (sku, part) groups.
    Returns a list of dicts with sku, part, total_qty, product_name (one example),
    order_count, removed_at, removed_by. Sorted by SKU numerically when possible."""
    if not label:
        return []
    c = sdb()
    rows = c.execute("""
        SELECT i.sku, i.product_name, i.quantity, i.order_id, i.shipment_id
        FROM shipment_items i
        JOIN shipments s ON s.shipment_id = i.shipment_id
        WHERE s.import_label = ? AND COALESCE(i.cancelled, 0) = 1
    """, (label,)).fetchall()
    state_rows = c.execute("""
        SELECT sku, part, removed_at, removed_by
        FROM cleanup_state WHERE import_label = ?
    """, (label,)).fetchall()
    c.close()
    state = {(r["sku"], r["part"]): r for r in state_rows}
    groups = {}
    for r in rows:
        sku = (r["sku"] or "").strip()
        part = _extract_part(r["product_name"] or "")
        key = (sku, part)
        g = groups.setdefault(key, {
            "sku": sku, "part": part, "total_qty": 0,
            "product_name": r["product_name"] or "",
            "order_count": 0, "orders": set(),
            "removed_at": None, "removed_by": None,
        })
        g["total_qty"] += int(r["quantity"] or 1)
        oid = r["order_id"] or r["shipment_id"]
        if oid: g["orders"].add(oid)
        # Prefer the longest product_name we see (most descriptive)
        if r["product_name"] and len(r["product_name"]) > len(g["product_name"]):
            g["product_name"] = r["product_name"]
    out = []
    for (sku, part), g in groups.items():
        g["order_count"] = len(g["orders"])
        g.pop("orders", None)
        st = state.get((sku, part))
        if st:
            g["removed_at"] = st["removed_at"]
            g["removed_by"] = st["removed_by"]
        out.append(g)
    # Order to match the picking flow: Part ascending (1→2→3), then SKU ascending
    # (numeric first, then non-numeric). Items with no Part sort last.
    def sort_key(g):
        p = g["part"] if isinstance(g["part"], int) else 9999
        s = g["sku"]
        try:
            return (p, 0, int(s))
        except (ValueError, TypeError):
            return (p, 1, s)
    out.sort(key=sort_key)
    return out

def _cleanup_progress(label):
    """Returns dict with total/done/pending counts + is_clean bool. is_clean is
    True when every cancelled (sku,part) group has been pulled. A show with NO
    cancelled items is also considered clean (nothing to do)."""
    groups = _cleanup_groups(label)
    total = len(groups)
    done = sum(1 for g in groups if g.get("removed_at"))
    return {
        "label": label,
        "total_groups": total,
        "groups_done": done,
        "groups_pending": total - done,
        "is_clean": total == 0 or done == total,
        "has_cancellations": total > 0,
    }

def _show_is_clean(label):
    """Quick bool — used by /pick to decide whether to allow scanning."""
    return _cleanup_progress(label)["is_clean"]


# ──────────────────────────────────────────────────────────────────────
# NEW HIRE ONBOARDING HELPERS
# ──────────────────────────────────────────────────────────────────────
# Workflow = ordered list of steps. A hire gets a private invite_token,
# opens /hire/<token>, walks the workflow, and the admin gets a per-hire
# detail page with all collected data, signatures, and uploaded docs.
# ──────────────────────────────────────────────────────────────────────
import secrets as _secrets_hire

# Step types — kept small and composable. UI dispatches on these strings.
HIRE_STEP_TYPES = {
    "info":     "Read-only briefing (handbook section, policy summary, etc.)",
    "ack":      "Acknowledgement — read, tick a box, type your name to sign",
    "sign":     "Document signing — full document + typed signature",
    "form":     "Fill a form with multiple fields",
    "upload":   "Upload a file (ID, certificate, headshot)",
    "video":    "Watch a video, then mark complete",
}

def _new_invite_token():
    """Cryptographically-random URL-safe token for invite links."""
    return _secrets_hire.token_urlsafe(24)

def _i9_section1_step():
    """I-9 Section 1 form step. US federal Employment Eligibility Verification.
    Body text reproduces the legal attestation language; the form captures all
    Section 1 fields the new hire must complete. Spanish translation provided
    per USCIS guidance (the form itself remains in English but a Spanish form
    is permitted in Puerto Rico only — we provide ES labels as guidance)."""
    return {
        "step_type": "form",
        "title_en": "Form I-9 — Section 1 (Employee)",
        "title_es": "Formulario I-9 — Sección 1 (Empleado)",
        "description_en": "Federal Employment Eligibility Verification. Required by USCIS.",
        "description_es": "Verificación Federal de Elegibilidad de Empleo. Requerido por USCIS.",
        "body_en": (
            "FORM I-9 — EMPLOYMENT ELIGIBILITY VERIFICATION (Section 1)\n\n"
            "ANTI-DISCRIMINATION NOTICE: It is illegal to discriminate against any work-authorized "
            "individual in hiring, firing, or recruitment. The refusal to hire or continue to employ "
            "an individual because of a future expiration date may also constitute illegal discrimination.\n\n"
            "INSTRUCTIONS: This section must be completed by the employee no later than the first day "
            "of employment. Provide your full legal name as it appears on your government-issued ID. "
            "Select the correct citizenship/immigration status, and provide the corresponding identifier "
            "if applicable.\n\n"
            "ATTESTATION: I am aware that federal law provides for imprisonment and/or fines for false "
            "statements, or the use of false documents, in connection with the completion of this form. "
            "By signing the next step, I attest under penalty of perjury that the information provided "
            "here is true and correct."
        ),
        "body_es": (
            "FORMULARIO I-9 — VERIFICACIÓN DE ELEGIBILIDAD DE EMPLEO (Sección 1)\n\n"
            "AVISO ANTIDISCRIMINACIÓN: Es ilegal discriminar a cualquier persona autorizada a trabajar "
            "en la contratación, despido o reclutamiento. La negativa a contratar o continuar empleando "
            "a una persona debido a una fecha futura de vencimiento también puede constituir discriminación "
            "ilegal.\n\n"
            "INSTRUCCIONES: Esta sección debe ser completada por el empleado a más tardar el primer día "
            "de empleo. Proporciona tu nombre legal completo tal como aparece en tu identificación oficial. "
            "Selecciona el estado correcto de ciudadanía/inmigración, y proporciona el identificador "
            "correspondiente si aplica.\n\n"
            "DECLARACIÓN: Tengo conocimiento de que la ley federal prevé pena de prisión y/o multas por "
            "declaraciones falsas o el uso de documentos falsos en relación con la cumplimentación de este "
            "formulario. Al firmar en el siguiente paso, declaro bajo pena de perjurio que la información "
            "proporcionada aquí es verdadera y correcta."
        ),
        "config_json": (
            '{"fields":['
            '{"name":"last_name","label":"Last name (Family name)","type":"text","required":true},'
            '{"name":"first_name","label":"First name (Given name)","type":"text","required":true},'
            '{"name":"middle_initial","label":"Middle initial","type":"text","required":false},'
            '{"name":"other_last_names","label":"Other last names used (if any)","type":"text","required":false},'
            '{"name":"address_street","label":"Address (Street number and name)","type":"text","required":true},'
            '{"name":"address_apt","label":"Apt. number","type":"text","required":false},'
            '{"name":"address_city","label":"City or town","type":"text","required":true},'
            '{"name":"address_state","label":"State","type":"text","required":true},'
            '{"name":"address_zip","label":"ZIP code","type":"text","required":true},'
            '{"name":"date_of_birth","label":"Date of birth (mm/dd/yyyy)","type":"date","required":true},'
            '{"name":"ssn","label":"U.S. Social Security Number","type":"text","required":true},'
            '{"name":"email","label":"Email address","type":"email","required":true},'
            '{"name":"phone","label":"Telephone number","type":"tel","required":true},'
            '{"name":"citizenship_status","label":"Citizenship / Immigration status","type":"select","required":true,'
            '"options":["1. A citizen of the United States","2. A noncitizen national of the United States","3. A lawful permanent resident","4. An alien authorized to work"]},'
            '{"name":"a_number_or_uscis","label":"Alien Registration / USCIS Number (only for status 3 or 4)","type":"text","required":false},'
            '{"name":"work_auth_expiration","label":"Work authorization expiration (only for status 4, mm/dd/yyyy)","type":"date","required":false},'
            '{"name":"foreign_passport_number","label":"Foreign passport number (only for status 4, if applicable)","type":"text","required":false},'
            '{"name":"country_of_issuance","label":"Country of issuance (only for status 4, if applicable)","type":"text","required":false}'
            ']}'
        ),
        "config_json_es": (
            '{"fields":['
            '{"name":"last_name","label":"Apellido","type":"text","required":true},'
            '{"name":"first_name","label":"Nombre","type":"text","required":true},'
            '{"name":"middle_initial","label":"Inicial del segundo nombre","type":"text","required":false},'
            '{"name":"other_last_names","label":"Otros apellidos usados (si aplica)","type":"text","required":false},'
            '{"name":"address_street","label":"Dirección (Número y nombre de la calle)","type":"text","required":true},'
            '{"name":"address_apt","label":"Número de apto.","type":"text","required":false},'
            '{"name":"address_city","label":"Ciudad o pueblo","type":"text","required":true},'
            '{"name":"address_state","label":"Estado","type":"text","required":true},'
            '{"name":"address_zip","label":"Código postal","type":"text","required":true},'
            '{"name":"date_of_birth","label":"Fecha de nacimiento (mm/dd/aaaa)","type":"date","required":true},'
            '{"name":"ssn","label":"Número de Seguro Social (EE.UU.)","type":"text","required":true},'
            '{"name":"email","label":"Correo electrónico","type":"email","required":true},'
            '{"name":"phone","label":"Número de teléfono","type":"tel","required":true},'
            '{"name":"citizenship_status","label":"Estado de ciudadanía / inmigración","type":"select","required":true,'
            '"options":["1. Ciudadano de los Estados Unidos","2. Nacional no ciudadano de los EE.UU.","3. Residente permanente legal","4. Extranjero autorizado a trabajar"]},'
            '{"name":"a_number_or_uscis","label":"Número de Registro de Extranjero / USCIS (solo para estado 3 o 4)","type":"text","required":false},'
            '{"name":"work_auth_expiration","label":"Vencimiento de la autorización (solo estado 4, mm/dd/aaaa)","type":"date","required":false},'
            '{"name":"foreign_passport_number","label":"Número de pasaporte extranjero (solo estado 4, si aplica)","type":"text","required":false},'
            '{"name":"country_of_issuance","label":"País de emisión (solo estado 4, si aplica)","type":"text","required":false}'
            ']}'
        ),
    }

def _i9_documents_step():
    """The companion upload step — supporting documents proving identity and work authorization."""
    return {
        "step_type": "upload",
        "title_en": "I-9 Supporting Documents",
        "title_es": "Documentos de Apoyo para I-9",
        "description_en": "Upload one List A document, OR one document from List B + one from List C.",
        "description_es": "Sube un documento de la Lista A, O un documento de la Lista B + uno de la Lista C.",
        "body_en": (
            "ACCEPTABLE DOCUMENTS (Form I-9):\n\n"
            "LIST A — Documents that establish BOTH identity AND employment authorization:\n"
            "  • U.S. Passport or U.S. Passport Card\n"
            "  • Permanent Resident Card or Alien Registration Receipt Card (Form I-551)\n"
            "  • Employment Authorization Document with photo (Form I-766)\n"
            "  • Foreign passport with Form I-94/I-94A bearing a work-authorized endorsement\n\n"
            "LIST B — Documents that establish IDENTITY ONLY (must combine with a List C document):\n"
            "  • Driver's license or ID card issued by a U.S. state or outlying possession\n"
            "  • ID card issued by federal, state, or local government agencies\n"
            "  • School ID card with a photograph\n"
            "  • U.S. Military card or draft record\n\n"
            "LIST C — Documents that establish EMPLOYMENT AUTHORIZATION ONLY (must combine with a List B document):\n"
            "  • U.S. Social Security Account Number card\n"
            "  • Certification of Birth Abroad (Form FS-545)\n"
            "  • Original or certified copy of birth certificate issued by a U.S. state or municipal authority\n"
            "  • U.S. Citizen ID Card (Form I-197)\n\n"
            "Take clear photos. All four corners visible. Text must be readable. You may upload one List A document, "
            "or one each from Lists B and C."
        ),
        "body_es": (
            "DOCUMENTOS ACEPTABLES (Formulario I-9):\n\n"
            "LISTA A — Documentos que establecen TANTO identidad COMO autorización de empleo:\n"
            "  • Pasaporte de EE.UU. o Tarjeta de Pasaporte\n"
            "  • Tarjeta de Residente Permanente o Tarjeta de Recibo de Registro de Extranjero (Formulario I-551)\n"
            "  • Documento de Autorización de Empleo con foto (Formulario I-766)\n"
            "  • Pasaporte extranjero con Formulario I-94/I-94A con endoso de autorización de trabajo\n\n"
            "LISTA B — Documentos que establecen SOLO IDENTIDAD (debe combinarse con un documento de la Lista C):\n"
            "  • Licencia de conducir o tarjeta de identificación emitida por un estado o territorio de EE.UU.\n"
            "  • Tarjeta de identificación emitida por agencias federales, estatales o locales\n"
            "  • Tarjeta de identificación escolar con fotografía\n"
            "  • Tarjeta militar de EE.UU. o registro de reclutamiento\n\n"
            "LISTA C — Documentos que establecen SOLO AUTORIZACIÓN DE EMPLEO (debe combinarse con Lista B):\n"
            "  • Tarjeta de Número de Seguro Social\n"
            "  • Certificación de Nacimiento en el Extranjero (Formulario FS-545)\n"
            "  • Copia original o certificada del certificado de nacimiento emitido por una autoridad estatal o municipal\n"
            "  • Tarjeta de Identidad de Ciudadano de EE.UU. (Formulario I-197)\n\n"
            "Toma fotos claras. Las cuatro esquinas visibles. El texto debe ser legible. Puedes subir un documento "
            "de la Lista A, o uno de la Lista B y uno de la Lista C."
        ),
        "config_json": (
            '{"accept":"image/*,.pdf","max_mb":15,"fields":['
            '{"name":"list_a_or_b","label":"List A document OR List B identity document","required":true},'
            '{"name":"list_c","label":"List C employment authorization document (only if you uploaded a List B above)","required":false},'
            '{"name":"back_side","label":"Back side of any document (if applicable)","required":false}'
            ']}'
        ),
        "config_json_es": (
            '{"accept":"image/*,.pdf","max_mb":15,"fields":['
            '{"name":"list_a_or_b","label":"Documento de Lista A O documento de identidad de Lista B","required":true},'
            '{"name":"list_c","label":"Documento de autorización de empleo de Lista C (solo si subiste un documento de Lista B)","required":false},'
            '{"name":"back_side","label":"Reverso de cualquier documento (si aplica)","required":false}'
            ']}'
        ),
    }

def _ensure_i9_steps_on_existing_workflows(org=None):
    """Append the I-9 form + supporting documents step to every existing workflow
    that doesn't already have them. Idempotent — runs once per workflow."""
    c = sdb(org)
    workflows = c.execute("SELECT id, name FROM onboarding_workflows").fetchall()
    for wf in workflows:
        already = c.execute("""SELECT id FROM onboarding_steps
                               WHERE workflow_id=? AND step_type='form' AND title LIKE 'Form I-9%'""",
                            (wf["id"],)).fetchone()
        if already:
            continue
        max_order = c.execute("SELECT COALESCE(MAX(step_order),0) AS m FROM onboarding_steps WHERE workflow_id=?",
                              (wf["id"],)).fetchone()["m"]
        for offset, step in enumerate([_i9_section1_step(), _i9_documents_step()], start=1):
            c.execute("""INSERT INTO onboarding_steps
                         (workflow_id, step_order, step_type, title, description, body, config_json,
                          is_required, title_es, description_es, body_es, config_json_es)
                         VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)""",
                      (wf["id"], max_order + offset, step["step_type"],
                       step["title_en"], step["description_en"], step["body_en"], step["config_json"],
                       step["title_es"], step["description_es"], step["body_es"], step["config_json_es"]))
    c.commit(); c.close()


def _seed_workflows_from_module(org=None):
    """Seed the real workflows from onboarding_seed.WORKFLOWS on first boot.
    Each workflow gets created once (skipped if a workflow with the same name
    already exists). The first one becomes the default for new hires.
    After seeding, ensures every workflow has I-9 steps appended."""
    try:
        from onboarding_seed import WORKFLOWS
    except ImportError:
        _ensure_i9_steps_on_existing_workflows(org)
        return None
    c = sdb(org)
    first_wf_id = None
    for idx, wf in enumerate(WORKFLOWS):
        existing = c.execute("SELECT id FROM onboarding_workflows WHERE name=?",
                             (wf["name"],)).fetchone()
        if existing:
            if first_wf_id is None: first_wf_id = existing["id"]
            continue
        is_default = 1 if idx == 0 else 0
        cur = c.execute("""INSERT INTO onboarding_workflows
                           (name, description, role_target, is_default, created_by)
                           VALUES (?, ?, ?, ?, 'system')""",
                        (wf["name"], wf.get("description", ""), wf.get("role", ""), is_default))
        wf_id = cur.lastrowid
        if first_wf_id is None: first_wf_id = wf_id
        for order, step in enumerate(wf["steps"], start=1):
            cfg = step.get("config_json") or step.get("config_json_en")
            cfg_es = step.get("config_json_es")
            c.execute("""INSERT INTO onboarding_steps
                         (workflow_id, step_order, step_type,
                          title, description, body, config_json, is_required,
                          title_es, description_es, body_es, config_json_es)
                         VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)""",
                      (wf_id, order, step["step_type"],
                       step.get("title_en"), step.get("description_en"),
                       step.get("body_en"), cfg,
                       step.get("title_es"), step.get("description_es"),
                       step.get("body_es"), cfg_es))
    c.commit(); c.close()
    # Backfill I-9 onto every workflow (including ones we just seeded)
    _ensure_i9_steps_on_existing_workflows(org)
    return first_wf_id

def _seed_default_workflow_if_missing(org=None):
    """Backward-compat shim. If the real seed module ran, that's what we use.
    If for some reason it failed (e.g. file not deployed yet), fall back to a
    minimal hard-coded placeholder so the system isn't completely broken."""
    seeded = _seed_workflows_from_module(org)
    if seeded is not None:
        return seeded
    c = sdb(org)
    existing = c.execute("SELECT id FROM onboarding_workflows ORDER BY id LIMIT 1").fetchone()
    if existing:
        c.close()
        return existing["id"]
    cur = c.execute("""INSERT INTO onboarding_workflows (name, description, role_target, is_default, created_by)
                       VALUES (?, ?, ?, 1, 'system')""",
                    ("Standard Onboarding", "Fallback workflow.", ""))
    wf_id = cur.lastrowid
    # Each tuple: (step_type, title_en, description_en, body_en, config_json,
    #              title_es, description_es, body_es, config_json_es)
    # ES entries are placeholders ready to be replaced when the user sends their
    # official translated content.
    default_steps = [
        ("info", "Welcome to {company}",
         "A quick intro to the team and what your first week looks like.",
         "Welcome aboard! Over the next 30 minutes you'll work through a short series of forms and policies. "
         "Each step is saved automatically — you can pause and resume from the same link anytime. "
         "When you finish, your warehouse manager gets notified and your badge becomes active.",
         None,
         "Bienvenido a {company}",
         "Una breve introducción al equipo y a tu primera semana.",
         "¡Bienvenido a bordo! Durante los próximos 30 minutos completarás una serie corta de formularios y políticas. "
         "Cada paso se guarda automáticamente — puedes pausar y continuar desde el mismo enlace cuando quieras. "
         "Cuando termines, tu gerente de almacén recibirá una notificación y tu credencial se activará.",
         None),
        ("form", "Your contact information",
         "Tell us how to reach you and your emergency contact.",
         None,
         '{"fields":['
         '{"name":"full_legal_name","label":"Full legal name (as on ID)","type":"text","required":true},'
         '{"name":"preferred_name","label":"Preferred name / nickname","type":"text","required":false},'
         '{"name":"date_of_birth","label":"Date of birth","type":"date","required":true},'
         '{"name":"phone","label":"Personal phone","type":"tel","required":true},'
         '{"name":"address","label":"Home address","type":"textarea","required":true},'
         '{"name":"emergency_name","label":"Emergency contact — name","type":"text","required":true},'
         '{"name":"emergency_relation","label":"Emergency contact — relationship","type":"text","required":true},'
         '{"name":"emergency_phone","label":"Emergency contact — phone","type":"tel","required":true}'
         ']}',
         "Tu información de contacto",
         "Cuéntanos cómo contactarte y a tu contacto de emergencia.",
         None,
         '{"fields":['
         '{"name":"full_legal_name","label":"Nombre legal completo (como aparece en el ID)","type":"text","required":true},'
         '{"name":"preferred_name","label":"Nombre preferido / apodo","type":"text","required":false},'
         '{"name":"date_of_birth","label":"Fecha de nacimiento","type":"date","required":true},'
         '{"name":"phone","label":"Teléfono personal","type":"tel","required":true},'
         '{"name":"address","label":"Dirección de casa","type":"textarea","required":true},'
         '{"name":"emergency_name","label":"Contacto de emergencia — nombre","type":"text","required":true},'
         '{"name":"emergency_relation","label":"Contacto de emergencia — parentesco","type":"text","required":true},'
         '{"name":"emergency_phone","label":"Contacto de emergencia — teléfono","type":"tel","required":true}'
         ']}'),
        ("ack", "Employee Handbook",
         "Read and acknowledge our company policies.",
         "By signing below you confirm you have read and agree to follow the {company} Employee Handbook, "
         "including policies on attendance, conduct, dress code, breaks, and workplace safety. You understand "
         "that violation of these policies may result in disciplinary action up to and including termination.",
         None,
         "Manual del Empleado",
         "Lee y reconoce nuestras políticas de la empresa.",
         "Al firmar abajo confirmas que has leído y aceptas seguir el Manual del Empleado de {company}, "
         "incluyendo las políticas de asistencia, conducta, código de vestimenta, descansos y seguridad en el lugar de trabajo. "
         "Entiendes que la violación de estas políticas puede resultar en medidas disciplinarias hasta e incluyendo el despido.",
         None),
        ("sign", "Confidentiality Agreement (NDA)",
         "Protect customer data and company secrets.",
         "I agree to keep all company information confidential, including customer data, business processes, "
         "supplier relationships, sales figures, and any other non-public information I learn during my employment. "
         "This obligation continues after my employment ends. I will not share customer details, share screenshots "
         "of internal systems, or remove company property without written permission. Breach of this agreement "
         "may result in legal action and immediate termination.",
         None,
         "Acuerdo de Confidencialidad (NDA)",
         "Protege los datos de los clientes y los secretos de la empresa.",
         "Acepto mantener toda la información de la empresa de forma confidencial, incluyendo datos de clientes, procesos de negocio, "
         "relaciones con proveedores, cifras de ventas y cualquier otra información no pública que aprenda durante mi empleo. "
         "Esta obligación continúa después de que termine mi empleo. No compartiré detalles de clientes, no compartiré capturas de pantalla "
         "de sistemas internos, ni retiraré propiedad de la empresa sin permiso por escrito. La violación de este acuerdo "
         "puede resultar en acción legal y despido inmediato.",
         None),
        ("form", "Tax information (W-4 essentials)",
         "Basic federal tax withholding information.",
         None,
         '{"fields":['
         '{"name":"ssn_last4","label":"Last 4 digits of your SSN (full SSN given separately)","type":"text","required":true},'
         '{"name":"filing_status","label":"Filing status","type":"select","required":true,"options":["Single or married filing separately","Married filing jointly","Head of household"]},'
         '{"name":"dependents","label":"Number of dependents claimed","type":"number","required":false},'
         '{"name":"additional_withholding","label":"Additional withholding per paycheck ($)","type":"number","required":false},'
         '{"name":"exempt","label":"Claiming exempt from withholding?","type":"select","required":true,"options":["No","Yes"]}'
         ']}',
         "Información tributaria (W-4 básico)",
         "Información básica de retención de impuestos federales.",
         None,
         '{"fields":['
         '{"name":"ssn_last4","label":"Últimos 4 dígitos de tu SSN (el SSN completo se entrega aparte)","type":"text","required":true},'
         '{"name":"filing_status","label":"Estado civil para impuestos","type":"select","required":true,"options":["Soltero/a o casado/a declarando por separado","Casado/a declarando en conjunto","Cabeza de familia"]},'
         '{"name":"dependents","label":"Número de dependientes declarados","type":"number","required":false},'
         '{"name":"additional_withholding","label":"Retención adicional por cheque ($)","type":"number","required":false},'
         '{"name":"exempt","label":"¿Reclamas exención de retención?","type":"select","required":true,"options":["No","Sí"]}'
         ']}'),
        ("form", "Direct deposit setup",
         "Where should we send your paychecks?",
         None,
         '{"fields":['
         '{"name":"bank_name","label":"Bank name","type":"text","required":true},'
         '{"name":"account_type","label":"Account type","type":"select","required":true,"options":["Checking","Savings"]},'
         '{"name":"routing_number","label":"Routing number (9 digits)","type":"text","required":true},'
         '{"name":"account_number","label":"Account number","type":"text","required":true},'
         '{"name":"confirm_account","label":"Confirm account number","type":"text","required":true}'
         ']}',
         "Configuración de depósito directo",
         "¿Dónde debemos enviar tus cheques de pago?",
         None,
         '{"fields":['
         '{"name":"bank_name","label":"Nombre del banco","type":"text","required":true},'
         '{"name":"account_type","label":"Tipo de cuenta","type":"select","required":true,"options":["Corriente","Ahorros"]},'
         '{"name":"routing_number","label":"Número de ruta (9 dígitos)","type":"text","required":true},'
         '{"name":"account_number","label":"Número de cuenta","type":"text","required":true},'
         '{"name":"confirm_account","label":"Confirma el número de cuenta","type":"text","required":true}'
         ']}'),
        ("upload", "Upload your ID",
         "We need a photo of a government-issued ID to verify your eligibility to work (I-9 requirement).",
         "Take a clear photo of one of the following: passport, driver's license, state ID, or permanent resident card. "
         "Make sure all four corners are visible and the text is readable.",
         '{"accept":"image/*,.pdf","max_mb":15,"fields":[{"name":"id_front","label":"Front of ID","required":true},{"name":"id_back","label":"Back of ID (if applicable)","required":false}]}',
         "Sube tu identificación",
         "Necesitamos una foto de una identificación oficial para verificar tu elegibilidad para trabajar (requisito I-9).",
         "Toma una foto clara de uno de los siguientes: pasaporte, licencia de conducir, identificación estatal o tarjeta de residente permanente. "
         "Asegúrate de que las cuatro esquinas sean visibles y que el texto se pueda leer.",
         '{"accept":"image/*,.pdf","max_mb":15,"fields":[{"name":"id_front","label":"Frente del ID","required":true},{"name":"id_back","label":"Reverso del ID (si aplica)","required":false}]}'),
        ("sign", "Anti-harassment policy acknowledgment",
         "We take a zero-tolerance stance on harassment.",
         "{company} is committed to a workplace free of harassment and discrimination. By signing below I confirm "
         "I have read the Anti-Harassment Policy, understand my responsibilities, and will not engage in any conduct "
         "that creates a hostile work environment based on race, gender, religion, sexual orientation, disability, age, "
         "or any other protected category. I understand how to report concerns to my manager or HR, and that retaliation "
         "for good-faith reports is prohibited.",
         None,
         "Reconocimiento de la política antiacoso",
         "Tenemos una postura de cero tolerancia hacia el acoso.",
         "{company} está comprometido con un lugar de trabajo libre de acoso y discriminación. Al firmar abajo confirmo "
         "que he leído la Política Antiacoso, entiendo mis responsabilidades, y no participaré en ninguna conducta "
         "que cree un ambiente de trabajo hostil basado en raza, género, religión, orientación sexual, discapacidad, edad, "
         "o cualquier otra categoría protegida. Entiendo cómo reportar inquietudes a mi gerente o a Recursos Humanos, y que la represalia "
         "por reportes de buena fe está prohibida.",
         None),
        ("ack", "Camera & recording consent",
         "Our packing stations record video of every order for quality control.",
         "I understand that while I am working at a packing station, video is recorded of the area in front of me "
         "(the packing surface) for the purpose of verifying order accuracy. The video does not capture audio. "
         "Videos are kept for 30 days unless flagged by customer service. I consent to this recording as part of my "
         "job responsibilities.",
         None,
         "Consentimiento de cámara y grabación",
         "Nuestras estaciones de empaque graban video de cada pedido para control de calidad.",
         "Entiendo que mientras trabajo en una estación de empaque, se graba video del área frente a mí "
         "(la superficie de empaque) con el propósito de verificar la exactitud del pedido. El video no captura audio. "
         "Los videos se conservan durante 30 días a menos que el equipo de servicio al cliente los marque. Doy mi consentimiento a esta grabación como parte "
         "de mis responsabilidades laborales.",
         None),
    ]
    # Policy text must name THIS tenant — a handbook or harassment policy that a new
    # hire signs must not carry another company's name.
    try:
        _co=(org_get(_org_or_current(org)).get("company_name") or "the company")
    except Exception:
        _co="the company"
    def _sub(v):
        return v.replace("{company}", _co) if isinstance(v, str) else v
    for order, row in enumerate(default_steps, start=1):
        row = tuple(_sub(v) for v in row)
        # Bilingual rows are 9-tuples; legacy 5-tuples still work (ES left NULL)
        if len(row) == 9:
            stype, title, desc, body, cfg, t_es, d_es, b_es, cfg_es = row
        else:
            stype, title, desc, body, cfg = row
            t_es = d_es = b_es = cfg_es = None
        c.execute("""INSERT INTO onboarding_steps
                     (workflow_id, step_order, step_type, title, description, body, config_json, is_required,
                      title_es, description_es, body_es, config_json_es)
                     VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)""",
                  (wf_id, order, stype, title, desc, body, cfg, t_es, d_es, b_es, cfg_es))
    c.commit(); c.close()
    return wf_id

# Run once at boot — seed the default onboarding workflow for every tenant.
for _org in list_org_ids():
    try: _seed_default_workflow_if_missing(_org)
    except Exception as e: print("workflow seed failed for", _org, ":", e, flush=True)

def _seed_guides():
    """Seed starter help guides. Adds any seed whose title isn't present yet, so
    new starter guides show up on deploy without duplicating existing ones. The
    platform owner's edits to already-seeded guides are left untouched."""
    try:
        c=pdb()
        have={r["title"] for r in c.execute("SELECT title FROM guides").fetchall()}
        added=0
        for g in GUIDE_SEEDS:
            if g.get("title") in have: continue
            c.execute("""INSERT INTO guides(category,title,body,video_url,audience,status,sort_order)
                         VALUES(?,?,?,?,?,?,?)""",
                      (g.get("category","getting_started"),g.get("title",""),g.get("body",""),
                       g.get("video_url",""),g.get("audience","all"),g.get("status","published"),
                       g.get("sort_order",0)))
            added+=1
        c.commit(); c.close()
        if added: print("Seeded",added,"starter guides",flush=True)
    except Exception as e:
        print("guide seed error:",e,flush=True)
_seed_guides()

# ══════════════════════════════════════════════════════════
# AUTOMATED BACKUPS — daily snapshot of every DB to R2 (or local),
# rotated by day-of-week (7 rolling copies). Consistent SQLite snapshots
# via the online backup API. No-op-safe if R2 isn't configured.
# ══════════════════════════════════════════════════════════
def _snapshot_db(src_path):
    import tempfile
    fd,tmp=tempfile.mkstemp(suffix=".db"); os.close(fd)
    s=sqlite3.connect(src_path); d=sqlite3.connect(tmp)
    with d: s.backup(d)
    d.close(); s.close()
    return tmp

def _backup_all():
    dow=datetime.now().strftime('%a').lower()
    targets=[("platform.db",PLATFORM_DB),("users.json",USERS_FILE)]
    for org in list_org_ids():
        targets.append((org+"/shipments.db",shipments_db_path(org)))
        targets.append((org+"/giveaways.db",giveaway_db_path(org)))
    done=0
    for name,path in targets:
        if not os.path.exists(path): continue
        try:
            if path.endswith(".db"):
                snap=_snapshot_db(path)
                with open(snap,"rb") as fh: data=fh.read()
                os.remove(snap)
            else:
                with open(path,"rb") as fh: data=fh.read()
            if r2:
                r2.put_object(Bucket=R2_BUCKET,Key="backups/"+dow+"/"+name,Body=data)
            else:
                bp=os.path.join(DATA_DIR,"backups",dow,name); os.makedirs(os.path.dirname(bp),exist_ok=True)
                with open(bp,"wb") as fh: fh.write(data)
            done+=1
        except Exception as e: print("[backup] error",name,":",e,flush=True)
    print("[backup] %d files -> %s/backups/%s"%(done,"R2" if r2 else "local",dow),flush=True)
    return done

def _backup_loop():
    guard=open(os.path.join(DATA_DIR,".backup.guard"),"a+")
    try: fcntl.flock(guard.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError: return  # another worker owns backups
    while True:
        time.sleep(6*3600)
        try:
            marker=os.path.join(DATA_DIR,".backup_last")
            last=os.path.getmtime(marker) if os.path.exists(marker) else 0
            if time.time()-last < 20*3600: continue   # ~once per day
            open(marker,"w").close()
            _backup_all()
        except Exception as e: print("backup loop error:",e,flush=True)
threading.Thread(target=_backup_loop,daemon=True).start()

# ── Bootstrap the platform super-admin (you) from env ──────────────
# The platform owner is a DEDICATED account, separate from every tenant (5sec
# included). Use a NEW username — do NOT reuse a tenant's 'admin', or that tenant
# would lose its admin. Set in Railway:
#   SUPERADMIN_USER=ofir           (a fresh username, not a tenant user)
#   SUPERADMIN_PASSWORD=...         (optional; auto-generated + printed once if unset)
SUPERADMIN_USER=(os.environ.get("SUPERADMIN_USER") or "").strip().lower()
SUPERADMIN_PASSWORD=os.environ.get("SUPERADMIN_PASSWORD") or ""
if SUPERADMIN_USER:
    try:
        with update_json(USERS_FILE) as _uu:
            _ex=_uu.get(SUPERADMIN_USER)
            if _ex:
                if _ex.get("role")!="superadmin" or _ex.get("org")!=PLATFORM_ORG:
                    _ex["role"]="superadmin"; _ex["org"]=PLATFORM_ORG; _ex.pop("badge_token",None)
                    print("Configured platform super-admin:",SUPERADMIN_USER,flush=True)
            else:
                _pw=SUPERADMIN_PASSWORD or _gen_pw()
                _uu[SUPERADMIN_USER]={"password":_h(_pw),"role":"superadmin",
                                      "name":"Platform Owner","org":PLATFORM_ORG}
                if SUPERADMIN_PASSWORD:
                    print("Created platform super-admin:",SUPERADMIN_USER,flush=True)
                else:
                    print("="*60+"\nCREATED PLATFORM SUPER-ADMIN\n  username: "+SUPERADMIN_USER+
                          "\n  password: "+_pw+"\n  (set SUPERADMIN_PASSWORD to pick your own; change after login)\n"+"="*60,flush=True)
    except Exception as e:
        print("superadmin bootstrap error:",e,flush=True)

def _hire_by_token(token):
    """Look up a hire by their invite token. Returns dict (with '_org') or None.

    Public onboarding routes have no session, so we resolve which tenant owns
    the token by scanning tenants, then PIN that org into g.org so every later
    sdb()/media call in the request stays inside the right tenant. Authenticated
    callers are scoped to their own session org only — never scan cross-tenant."""
    if not token or len(token) > 64: return None
    sess_org=None
    try:
        if has_request_context(): sess_org=session.get("org")
    except Exception: pass
    orgs=[sess_org] if sess_org else list_org_ids()
    for org in orgs:
        c = sdb(org)
        row = c.execute("SELECT * FROM new_hires WHERE invite_token=?", (token,)).fetchone()
        c.close()
        if row:
            if not sess_org:
                try:
                    if has_request_context(): g.org=org
                except Exception: pass
            d=dict(row); d["_org"]=org
            return d
    return None

def _hire_steps_with_progress(hire_id, workflow_id, lang="en"):
    """Returns the ordered list of steps for a workflow with each hire's progress
    merged in. Each row: step + status (pending|in_progress|done) + data_json.
    If lang='es', returns Spanish title/description/body/config_json with
    English fallback for any field where the Spanish version is missing.
    For upload steps, the data_json is enriched with an `uploads` dict keyed
    by field_name with {filename, size_bytes, mime_type} so the page can show
    'already uploaded' state on resume."""
    import json as _json
    c = sdb()
    rows = c.execute("""
        SELECT s.id AS step_id, s.step_order, s.step_type,
               s.title, s.description, s.body, s.config_json,
               s.title_es, s.description_es, s.body_es, s.config_json_es,
               s.is_required,
               p.status, p.started_at, p.completed_at, p.data_json
        FROM onboarding_steps s
        LEFT JOIN onboarding_progress p
          ON p.step_id = s.id AND p.hire_id = ?
        WHERE s.workflow_id = ?
        ORDER BY s.step_order
    """, (hire_id, workflow_id)).fetchall()
    # Pre-fetch uploads for this hire (one extra query — keeps the inner loop simple)
    upload_rows = c.execute("""SELECT step_id, field_name, original_filename, mime_type, size_bytes
                                FROM onboarding_uploads WHERE hire_id=?""", (hire_id,)).fetchall()
    uploads_by_step = {}
    for u in upload_rows:
        uploads_by_step.setdefault(u["step_id"], {})[u["field_name"]] = {
            "filename": u["original_filename"],
            "mime_type": u["mime_type"],
            "size_bytes": u["size_bytes"],
        }
    c.close()
    out = []
    for r in rows:
        d = dict(r)
        if lang == "es":
            d["title"] = d.get("title_es") or d["title"]
            d["description"] = d.get("description_es") or d.get("description")
            d["body"] = d.get("body_es") or d.get("body")
            d["config_json"] = d.get("config_json_es") or d.get("config_json")
        for k in ("title_es", "description_es", "body_es", "config_json_es"):
            d.pop(k, None)
        # Merge upload info into data_json so the JS can show existing uploads on resume
        if d["step_type"] == "upload":
            existing = uploads_by_step.get(d["step_id"], {})
            current = {}
            if d.get("data_json"):
                try: current = _json.loads(d["data_json"]) or {}
                except: current = {}
            current["uploads"] = existing
            d["data_json"] = _json.dumps(current, ensure_ascii=False)
        out.append(d)
    return out

def _hire_completion_pct(hire_id, workflow_id):
    """Returns (done_count, total_count, pct)."""
    steps = _hire_steps_with_progress(hire_id, workflow_id)
    total = len(steps)
    done = sum(1 for s in steps if s["status"] == "done")
    return done, total, int(100 * done / total) if total else 0

def _mark_step(hire_id, step_id, data_dict=None, status="done"):
    """Insert/update a progress row for this hire+step. data_dict serialized to JSON."""
    import json as _json
    c = sdb()
    payload = _json.dumps(data_dict, ensure_ascii=False) if data_dict else None
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("""
        INSERT INTO onboarding_progress (hire_id, step_id, status, started_at, completed_at, data_json)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(hire_id, step_id) DO UPDATE SET
          status=excluded.status,
          completed_at=excluded.completed_at,
          data_json=excluded.data_json
    """, (hire_id, step_id, status, now, now if status == "done" else None, payload))
    # If this is the first completed step, mark the hire as started
    c.execute("UPDATE new_hires SET status='in_progress', started_at=COALESCE(started_at,?) WHERE id=? AND status='invited'",
              (now, hire_id))
    # Check if every required step is done — auto-promote to 'complete'
    workflow_id = c.execute("SELECT workflow_id FROM new_hires WHERE id=?", (hire_id,)).fetchone()["workflow_id"]
    pending = c.execute("""
        SELECT COUNT(*) AS pending
        FROM onboarding_steps s
        LEFT JOIN onboarding_progress p ON p.step_id=s.id AND p.hire_id=?
        WHERE s.workflow_id=? AND s.is_required=1 AND COALESCE(p.status,'pending')<>'done'
    """, (hire_id, workflow_id)).fetchone()["pending"]
    if pending == 0:
        c.execute("UPDATE new_hires SET status='complete', completed_at=? WHERE id=? AND status<>'complete'",
                  (now, hire_id))
    c.commit(); c.close()

def _sku_weight(sku):
    """Look up a single SKU's weight in grams. Returns None if unknown."""
    if not sku: return None
    c = sdb()
    row = c.execute("SELECT weight_g FROM sku_weights WHERE sku=?", (sku,)).fetchone()
    c.close()
    return row["weight_g"] if row else None

def _recompute_shipment_weight(conn, shipment_id, overhead=None):
    """Sum item weights × qty + packaging overhead. Updates the shipment row in place.
    Skips cancelled items. Caller passes an open connection. `overhead` may be passed
    in to avoid a per-shipment config query during bulk imports."""
    if overhead is None:
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

# Behind Railway's proxy: trust ONE hop of X-Forwarded-* so request.remote_addr
# is the real client IP (correct HTTPS detection + accurate login rate-limiting).
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app=ProxyFix(app.wsgi_app,x_for=1,x_proto=1,x_host=1,x_port=1)

# ── CSRF protection (double-submit cookie) ─────────────────────────
# SameSite=Lax already blocks most cross-site POSTs; this adds an explicit
# token check for all state-changing requests. A non-HttpOnly cookie holds a
# random token; JS echoes it back in the X-CSRF-Token header (see the shim
# injected below). The server requires header == cookie for mutating methods.
CSRF_COOKIE="csrf_token"
CSRF_HEADER="X-CSRF-Token"
_CSRF_SAFE=("GET","HEAD","OPTIONS","TRACE")

# The public lead form is unauthenticated — there is no session for a forged request
# to ride on, so CSRF adds nothing, and it must be POSTable from the marketing site
# on a different origin. It is rate-limited by IP instead.
_CSRF_EXEMPT={"/api/lead"}

@app.before_request
def _csrf_protect():
    if request.method in _CSRF_SAFE:
        return
    if request.path in _CSRF_EXEMPT:
        return
    ck=request.cookies.get(CSRF_COOKIE)
    hd=request.headers.get(CSRF_HEADER) or (request.form.get("_csrf") if request.form else None)
    if not ck or not hd or not secrets.compare_digest(str(ck),str(hd)):
        return jsonify({"ok":False,"error":"CSRF validation failed — please refresh the page and try again."}),403

# ── Billing gate (full lock) ──────────────────────────────────────────────────
# When a tenant's trial has expired or its subscription isn't active, everything is
# blocked except logging out, the billing screen, and the public/lead pages. The
# platform owner (super-admin) is never gated.
_BILLING_OPEN_PATHS={"/login","/logout","/billing","/api/billing/status","/healthz",
                     "/demo","/api/lead","/favicon.ico"}
_BILLING_OPEN_PREFIXES=("/static/","/api/billing/","/guide-asset/")

@app.before_request
def _billing_gate():
    p=request.path or "/"
    if p in _BILLING_OPEN_PATHS or p.startswith(_BILLING_OPEN_PREFIXES):
        return
    if not session.get("user") and not session.get("name"):
        return                      # not logged in — the auth decorators handle it
    if is_super():
        return                      # platform owner is never gated
    allowed,state,info=org_access(current_org())
    if allowed:
        return
    if p.startswith("/api/"):
        return jsonify({"ok":False,"error":"billing","state":state,
                        "message":_BILLING_MSG.get(state,"Your subscription is not active.")}),402
    return redirect("/billing")

_BILLING_MSG={
    "trial_expired":"Your 7-day trial has ended. Choose a plan and we'll send you an invoice to keep going.",
    "period_ended":"Your paid period has ended. Once we receive your renewal payment, access is restored immediately.",
    "unpaid":"There's an outstanding balance on this account. Get in touch and we'll sort it out right away.",
    "suspended":"This account has been suspended. Contact support.",
    "no_subscription":"This account doesn't have an active plan yet.",
}

# Injected into every HTML page so all fetch()/XHR mutating calls carry the token.
_CSRF_SHIM=("<script>(function(){function t(){var m=document.cookie.match(/(?:^|;\\s*)"
    +CSRF_COOKIE+"=([^;]+)/);return m?decodeURIComponent(m[1]):\"\";}"
    "function same(u){try{if(typeof u!=='string')u=(u&&u.url)||'';if(!u)return true;"
    "if(u[0]==='/')return true;var a=document.createElement('a');a.href=u;return a.host===location.host;}catch(e){return false;}}"
    "var M=['POST','PUT','PATCH','DELETE'];var of=window.fetch;"
    "window.fetch=function(i,init){init=init||{};var m=(init.method||(i&&i.method)||'GET').toUpperCase();"
    "if(M.indexOf(m)>=0&&same(i)){var h=new Headers(init.headers||(i&&i.headers)||{});"
    "if(!h.has('"+CSRF_HEADER+"'))h.set('"+CSRF_HEADER+"',t());init.headers=h;}return of.call(this,i,init);};"
    "var oo=XMLHttpRequest.prototype.open,os=XMLHttpRequest.prototype.send;"
    "XMLHttpRequest.prototype.open=function(m,u){this.__m=(m||'GET').toUpperCase();this.__s=same(u);return oo.apply(this,arguments);};"
    "XMLHttpRequest.prototype.send=function(){if(M.indexOf(this.__m)>=0&&this.__s){try{this.setRequestHeader('"
    +CSRF_HEADER+"',t());}catch(e){}}return os.apply(this,arguments);};})();</script>")

@app.after_request
def _security_headers(resp):
    """Baseline security headers on every response. The CSP allows inline
    script/style ('unsafe-inline') because the templates embed JS/CSS inline;
    it still blocks injected external scripts and framing (clickjacking)."""
    resp.headers.setdefault("X-Frame-Options","DENY")
    resp.headers.setdefault("X-Content-Type-Options","nosniff")
    resp.headers.setdefault("Referrer-Policy","same-origin")
    resp.headers.setdefault("Strict-Transport-Security","max-age=31536000; includeSubDomains")
    resp.headers.setdefault("Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: blob: https:; "
        "media-src 'self' blob: https:; "
        "connect-src 'self' https:; "
        "frame-src 'self' data: blob: https:; "
        "frame-ancestors 'none'; "
        "base-uri 'self'")
    # Ensure the CSRF cookie exists (readable by JS; Secure; SameSite=Lax).
    if not request.cookies.get(CSRF_COOKIE):
        resp.set_cookie(CSRF_COOKIE,secrets.token_urlsafe(32),max_age=7*24*3600,
                        secure=True,httponly=False,samesite="Lax")
    # Inject the token-forwarding shim into HTML pages (not JSON/file responses),
    # and resolve the brand tokens so no page ever shows another tenant's name.
    try:
        ct=resp.headers.get("Content-Type","")
        if ct.startswith("text/html") and not resp.direct_passthrough:
            body=resp.get_data(as_text=True)
            if "</body>" in body and "__m=" not in body:
                body=body.replace("</body>",_CSRF_SHIM+"</body>",1)
            if "__BRAND" in body:
                b=session.get("brand") or {}
                mark=b.get("mark") or "LiveOpsHub"
                name=b.get("company") or mark
                body=(body.replace("__BRANDNAME_UC__",esc(name).upper())
                          .replace("__BRANDNAME__",esc(name))
                          .replace("__BRANDMARK__",esc(mark)))
            resp.set_data(body)
    except Exception:
        pass
    return resp

def req_login(f):
    @wraps(f)
    def d(*a,**k):
        if "user" not in session: return redirect("/")
        return f(*a,**k)
    return d
def _effective_roles(info):
    """A user's full role set: primary role + any extra_roles (deduped)."""
    rs=[info.get("role")] + list(info.get("extra_roles") or [])
    return [r for r in dict.fromkeys(rs) if r]

def session_roles():
    return session.get("roles") or ([session.get("role")] if session.get("role") else [])

def req_role(*roles):
    def w(f):
        @wraps(f)
        def d(*a,**k):
            if "user" not in session: return redirect("/")
            # The super-admin is a pure platform owner (no tenant). They must NOT
            # reach tenant-operational routes — only the control plane (req_super).
            # A user passes if ANY of their roles (primary or extra) is allowed.
            if not any(r in roles for r in session_roles()): return "Access denied",403
            return f(*a,**k)
        return d
    return w
def req_super(f):
    """Platform-owner only (cross-tenant control plane: org management)."""
    @wraps(f)
    def d(*a,**k):
        if "user" not in session: return redirect("/")
        if session.get("role")!="superadmin": return "Access denied",403
        return f(*a,**k)
    return d
def is_super():
    return session.get("role")=="superadmin"
def _same_org_user(users,u):
    """True if target user u belongs to the caller's org (or caller is super).
    Stops one tenant's admin from touching another tenant's user account."""
    if is_super(): return True
    return users.get(u,{}).get("org",DEFAULT_ORG)==session.get("org",DEFAULT_ORG)


# ══════════════════════════════════════════════════════════
# STATS HELPERS — aggregate packing_log.csv for portal pages
# (Profile, Leaderboard, Packer-of-the-Month, Achievements)
# ══════════════════════════════════════════════════════════

def _read_log():
    """Return all rows from packing_log.csv, or [] if missing."""
    if not os.path.exists(log_file()): return []
    with open(log_file()) as f: return list(csv.DictReader(f))

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
    if not os.path.exists(onb_file()): return {"tasks": [], "completions": {}}
    try:
        with open(onb_file()) as f: return json.load(f)
    except: return {"tasks": [], "completions": {}}

def _onb_save(d):
    with open(onb_file(),"w") as f: json.dump(d,f,indent=2)

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
    if not os.path.exists(ann_file()): return {}
    try:
        with open(ann_file()) as f: return json.load(f)
    except: return {}

def _ann_save(d):
    with open(ann_file(), "w") as f: json.dump(d, f, indent=2)

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
    if not os.path.exists(docs_file()): return {}
    try:
        with open(docs_file()) as f: return json.load(f)
    except: return {}

def _docs_save(d):
    with open(docs_file(), "w") as f: json.dump(d, f, indent=2)

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


def _is_mobile_device():
    """User-Agent sniff. Used to send workers to /pick on iPad/phone automatically
    (touch-first UI), and keep desktop workers on the packing/recording screen."""
    ua = (request.headers.get("User-Agent", "") or "").lower()
    return any(m in ua for m in ("iphone", "ipad", "android", "mobile", "tablet"))

@app.route("/")
def index():
    machine_mode = request.cookies.get("machine_mode", "")
    machine_sta = request.cookies.get("machine_station", "")
    # ?force=pack lets a picker explicitly switch to packing screen on the same device
    # without the auto-routing pulling them back to /pick.
    force = (request.args.get("force") or "").lower()
    if "user" not in session:
        # Default to badge-login (warehouse stations have no keyboard/mouse).
        # Admins/anyone needing password type can click "Use password instead" → /login
        return redirect("/badge-login")
    # Platform owner has no tenant screens — land on the Organizations console.
    if session.get("role")=="superadmin":
        return redirect("/admin/organizations")
    # Explicit admin override via cookie wins over auto-detection
    if machine_mode == "pick" and force != "pack":
        return redirect("/pick")
    if (machine_mode != "pack" and force != "pack" and
        session.get("role")=="worker" and _is_mobile_device()):
        # Auto: worker on a touch device → picking UI
        return redirect("/pick")
    if session.get("role")=="worker":
        # Auto-assign a station so the worker never sees the picker — they don't care
        # which station they're at. Order of preference:
        #   1. Station already in session (returning visit)
        #   2. machine_station cookie (set by admin on this device)
        #   3. First station defined in stations.json
        #   4. Hard-coded "S1"
        if "station" not in session:
            stations = ldj(STATIONS_FILE)
            sid = machine_sta if machine_sta in stations else (next(iter(stations), "S1"))
            session["station"] = sid
            session["station_name"] = stations.get(sid, "Station 1")
        return (WORKER_HTML
            .replace("__NAME__", esc(session["name"]))
            .replace("__STATION__", session.get("station_name",""))
            .replace("__SID__", session.get("station","S1")))
    return redirect("/home")

@app.route("/home")
@req_login
def home_page():
    if session.get("role")=="superadmin": return redirect("/admin/organizations")
    role = session.get("role", "")
    brand = session.get("brand") or {}
    return (HOME_HTML
        .replace("__ROLE__", esc(role))
        .replace("__BRANDSUB__", esc(brand.get("sub", "Employee Hub")))
        .replace("__NAVBAR__", _navbar("home"))
        .replace("__NAVBAR_CSS__", _NAVBAR_CSS))

@app.route("/welcome")
@req_login
def welcome_page():
    """Post-login choice screen — workers pick between Portal and Packing.
    Non-workers don't pack, so we just send them straight to /home."""
    if session.get("role") != "worker":
        return redirect("/home")
    return WELCOME_HTML.replace("__NAME__", esc(session.get("name", "there")))

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
    return DASH_HTML.replace("__NAME__",esc(session.get("name",""))).replace("__ADMIN_VIS__",disp).replace("__NAVBAR__",_navbar("dash")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

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
    d=request.get_json(silent=True) or {}
    u=(d.get("username") or "").strip().lower();p=d.get("password") or ""
    ok,limited=_login_rate_check(request.remote_addr,u)
    if limited:
        return jsonify({"ok":False,"error":"Too many attempts, try again shortly"}),429
    users=ldj(USERS_FILE) if os.path.exists(USERS_FILE) else {}
    user=users.get(u)
    if user and _verify(p,user.get("password","")):
        if not org_is_active(user.get("org",DEFAULT_ORG)):
            return jsonify({"ok":False,"error":"This organization is suspended. Please contact support."}),403
        _login_rate_clear(request.remote_addr,u)
        # Auto-upgrade legacy SHA256 hash to bcrypt on successful login (locked)
        if not user.get("password","").startswith("$2"):
            with update_json(USERS_FILE) as uu:
                if u in uu: uu[u]["password"]=_h(p)
        session.clear()  # rotate session id to prevent fixation
        session["user"]=u;session["role"]=user["role"];session["name"]=user["name"]
        session["roles"]=_effective_roles(user)
        session["org"]=user.get("org",DEFAULT_ORG)
        session["brand"]=brand_for_session(session["org"])
        return jsonify({"ok":True,"role":user["role"]})
    # Equalize timing on unknown username so it doesn't return faster (enumeration oracle)
    if not user:
        try: bcrypt.checkpw(b"x",_DUMMY_HASH)
        except Exception: pass
    _login_rate_fail(request.remote_addr,u)
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

# A valid WebM/Matroska file must begin with the EBML magic 1A45DFA3.
# Some uploads have arrived with a corrupt high-entropy prefix prepended *before*
# that header. The video stream after the header is intact, but the junk prefix
# makes the container unparseable, so NO browser (Chrome or Safari) can play it.
# We defensively cut everything before the first EBML magic on the way in.
EBML_MAGIC = b'\x1a\x45\xdf\xa3'

def _clean_webm(data):
    """Return (cleaned_bytes, stripped_count). Strips any junk before EBML magic."""
    i = data.find(EBML_MAGIC)
    if i <= 0:          # 0 = already clean, -1 = no header found (leave as-is)
        return data, 0
    return data[i:], i

@app.route("/api/upload",methods=["POST"])
@req_login
def api_upload():
    trk=_normalize_tracking(request.form.get("tracking",""))
    sta=request.form.get("station",session.get("station","S0"))
    # Validate duration as a number so it can't inject extra CSV rows/columns.
    try: dur=round(float(request.form.get("duration","0") or 0),2)
    except (TypeError,ValueError): dur=0
    wrk=session.get("name","Unknown")
    # FIX #4: Sanitize tracking number - allow only alphanumeric, dash, underscore
    if not trk or not re.match(r'^[A-Za-z0-9_\-]{1,64}$',trk):
        return jsonify({"ok":False,"error":"Invalid tracking number"})
    sta=re.sub(r'[^A-Za-z0-9_\-]','',sta)[:16] or "S0"
    fn=sta+"_"+trk;now=datetime.now()
    vf=request.files.get("video");vn=None
    if vf:
        # Read fully so we can sanitize before storage (videos are small, ~3.5MB).
        vdata=vf.read()
        vdata,stripped=_clean_webm(vdata)
        if stripped:
            print("upload: stripped %d junk bytes before EBML for %s" % (stripped,fn),flush=True)
        if not vdata.startswith(EBML_MAGIC):
            # No header even after scanning — store raw but warn loudly for diagnosis.
            print("upload: WARNING no EBML header for %s (first8=%s)" % (fn,vdata[:8].hex()),flush=True)
        if r2:
            # R2 mode: always include timestamp to ensure uniqueness without an existence check
            vn=fn+"_"+now.strftime('%H%M%S')+".webm"
            try:
                r2.put_object(Bucket=R2_BUCKET,Key=_r2_media_key("videos",vn),Body=vdata,
                    ContentType='video/webm')
            except Exception as e:
                print("R2 video upload failed:",e,flush=True)
                return jsonify({"ok":False,"error":"Storage upload failed"})
        else:
            vn=fn+".webm";vp=os.path.join(video_dir(),vn)
            if os.path.exists(vp):vn=fn+"_"+now.strftime('%H%M%S')+".webm";vp=os.path.join(video_dir(),vn)
            with open(vp,"wb") as out: out.write(vdata)
    pf=request.files.get("photo");pn=None
    if pf:
        if r2:
            pn=fn+"_"+now.strftime('%H%M%S')+".jpg"
            try:
                r2.upload_fileobj(pf.stream,R2_BUCKET,_r2_media_key("photos",pn),
                    ExtraArgs={'ContentType':'image/jpeg'})
            except Exception as e:
                print("R2 photo upload failed:",e,flush=True)
                pn=None
        else:
            pn=fn+".jpg";pp=os.path.join(photo_dir(),pn)
            if os.path.exists(pp):pn=fn+"_"+now.strftime('%H%M%S')+".jpg";pp=os.path.join(photo_dir(),pn)
            pf.save(pp)
    with _flock("packing_log"):
        with open(log_file(),"a",newline="") as f:
            csv.writer(f).writerow([trk,sta,now.strftime('%Y-%m-%d'),now.strftime('%H:%M:%S'),dur,vn,pn,wrk])
    # Mark the shipment row as packed in the SQL table — that's what the Shows /
    # Customers / SKU Reconciliation pages read from. Without this update, every
    # shipment looks 'pending' even after the recording is done.
    # Skip if no matching shipment, if it's already shipped, or if it's cancelled.
    try:
        c = sdb()
        row = c.execute("SELECT shipment_id, status FROM shipments WHERE tracking_code=?", (trk,)).fetchone()
        if row and row["status"] not in ("shipped", "cancelled"):
            c.execute("""UPDATE shipments
                         SET status='packed', packed_at=CURRENT_TIMESTAMP, packed_by=?
                         WHERE tracking_code=?""", (wrk, trk))
            # Deplete inventory for the items in this shipment (once per shipment).
            try: _deplete_stock_for(c, row["shipment_id"])
            except Exception as e: print("stock deplete failed for", trk, ":", e, flush=True)
            c.commit()
        c.close()
    except Exception as e:
        # Don't fail the upload if the SQL update has a hiccup — the CSV log is the source of truth
        # for the recording itself, and we can backfill the shipments table later.
        print("packed-status update failed for", trk, ":", e, flush=True)
    # If this tracking is a standalone giveaway, mark it filmed/packed too.
    try:
        gv=_giveaway_by_tracking(trk)
        if gv:
            g=gdb()
            g.execute("UPDATE giveaways SET filmed_at=COALESCE(filmed_at,?), filmed_by=COALESCE(filmed_by,?) WHERE id=?",
                      (now.strftime('%Y-%m-%dT%H:%M:%S'), wrk, gv["id"]))
            g.commit(); g.close()
    except Exception as e:
        print("giveaway filmed-status update failed for", trk, ":", e, flush=True)
    return jsonify({"ok":True})

@app.route("/api/backfill-packed-status", methods=["POST"])
@req_role("admin")
def api_backfill_packed():
    """One-shot fix-up: walk the packing CSV log and mark any shipment whose
    tracking_code appears there as 'packed' (unless already shipped/cancelled).
    Use this after deploying the packed-status fix to retroactively close out
    shipments that were already recorded before the fix went live."""
    if not os.path.exists(log_file()):
        return jsonify({"ok": True, "log_rows": 0, "shipments_updated": 0})
    # Collect (tracking, latest_timestamp, worker) tuples from the CSV log
    by_track = {}
    with open(log_file()) as f:
        for row in csv.DictReader(f):
            trk = (row.get("tracking_number") or "").strip()
            if not trk: continue
            ts = (row.get("date","") + " " + row.get("time","")).strip()
            w = (row.get("worker") or "").strip()
            prev = by_track.get(trk)
            if not prev or ts > prev[0]:
                by_track[trk] = (ts, w)
    if not by_track:
        return jsonify({"ok": True, "log_rows": 0, "shipments_updated": 0})
    c = sdb()
    updated = 0
    not_found = 0
    skipped = 0
    for trk, (ts, w) in by_track.items():
        row = c.execute("SELECT shipment_id, status, packed_at FROM shipments WHERE tracking_code=?",
                        (trk,)).fetchone()
        if not row:
            not_found += 1
            continue
        if row["status"] in ("shipped", "cancelled"):
            skipped += 1
            continue
        if row["status"] == "packed" and row["packed_at"]:
            skipped += 1
            continue
        # Use the recording timestamp as packed_at; worker as packed_by
        c.execute("""UPDATE shipments SET status='packed',
                     packed_at=COALESCE(packed_at, ?), packed_by=COALESCE(packed_by, ?)
                     WHERE tracking_code=?""",
                  (ts or None, w or None, trk))
        updated += 1
    c.commit(); c.close()
    return jsonify({"ok": True, "log_rows": len(by_track),
                    "shipments_updated": updated,
                    "not_in_imports": not_found,
                    "skipped": skipped})


@app.route("/api/search/<trk>")
@req_role("admin","cs")
def api_search(trk):
    """Search by tracking number using the CSV log as the index.
    Works identically for R2 and local storage."""
    r={"tracking":trk,"videos":[],"photos":[],"log":[]};t=trk.lower()
    seen_v=set();seen_p=set()
    if os.path.exists(log_file()):
        with open(log_file()) as cf:
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
    if os.path.exists(log_file()):
        with open(log_file()) as f: recs=list(csv.DictReader(f))
    recs.reverse()
    return jsonify(recs[:100])

@app.route("/api/stats")
@req_role("admin","cs")
def api_stats():
    tv=0;ts=0
    if os.path.exists(video_dir()):
        for f in os.listdir(video_dir()):tv+=1;ts+=os.path.getsize(os.path.join(video_dir(),f))
    tp=len(os.listdir(photo_dir())) if os.path.exists(photo_dir()) else 0
    return jsonify({"total_videos":tv,"total_photos":tp,"total_size_mb":round(ts/(1024*1024),1)})

@app.route("/api/analytics")
@req_role("admin","cs")
def api_analytics():
    recs=[]
    if os.path.exists(log_file()):
        with open(log_file()) as f: recs=list(csv.DictReader(f))
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
    return ANALYTICS_HTML.replace("__NAME__",esc(session.get("name",""))).replace("__ADMIN_VIS__",disp).replace("__NAVBAR__",_navbar("analytics")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)


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
    return (LEADERBOARD_HTML
        .replace("__ME__", json.dumps(session.get("name", "")).replace("<", "\\u003c"))
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
            r2.upload_fileobj(f.stream, R2_BUCKET, _r2_media_key("documents", stored))
            # Get size by HEAD request after upload
            try:
                head = r2.head_object(Bucket=R2_BUCKET, Key=_r2_media_key("documents", stored))
                size = head.get('ContentLength', 0)
            except: size = 0
        except Exception as e:
            print("R2 document upload failed:", e, flush=True)
            return jsonify({"ok": False, "error": "Storage upload failed"})
    else:
        path = os.path.join(docs_dir(), stored)
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
                Params={'Bucket': R2_BUCKET, 'Key': _r2_resolve("documents", stored),
                        'ResponseContentDisposition': 'attachment; filename="' + d.get('filename','file') + '"'},
                ExpiresIn=R2_PRESIGN_TTL)
            return redirect(url)
        except Exception as e:
            print("R2 doc presign failed:", e, flush=True)
            return "Download error", 500
    else:
        path = os.path.join(docs_dir(), stored)
        # Path traversal guard
        rp = os.path.realpath(path)
        if not rp.startswith(os.path.realpath(docs_dir()) + os.sep):
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
    """Return 'tiktok' | 'whatnot' | None. Matching is case/space-insensitive so
    small header variations in the export don't break the upload."""
    fn = { (x or "").strip().lower() for x in (fieldnames or []) }
    if {"order id", "tracking id", "package id", "seller sku"}.issubset(fn):
        return "tiktok"
    # Whatnot: accept the canonical headers OR a looser signal (order + product + a
    # shipment/tracking id), so renamed/variant exports still import.
    if {"order_id", "shipment_id", "product_name", "product_quantity"}.issubset(fn):
        return "whatnot"
    has_order = ("order_id" in fn or "order id" in fn)
    has_prod  = ("product_name" in fn or "product name" in fn or "item name" in fn or "product" in fn)
    has_ship  = any(k in fn for k in ("shipment_id","shipment id","tracking_code","tracking code","order_number","order number"))
    if has_order and has_prod and has_ship:
        return "whatnot"
    return None

def _row_get(row):
    """Case/space-insensitive column accessor with alias support."""
    m = { (k or "").strip().lower(): v for k, v in row.items() }
    def g(*names):
        for nm in names:
            v = m.get(nm.strip().lower())
            if v not in (None, ""): return str(v).strip()
        return ""
    return g

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
    try: revenue = float((s("SKU Subtotal After Discount") or "0").replace(",","").replace("$",""))
    except: revenue = 0.0
    # Shipping fee the buyer paid — TikTok column names vary a bit; match loosely.
    _g = _row_get(row)
    _sf = _g("Shipping Fee After Discount", "shipping fee after discount",
             "Buyer Paid Shipping Fee", "buyer paid shipping fee",
             "Customer Paid Shipping Fee", "customer paid shipping fee",
             "Shipping Fee", "shipping fee", "Original Shipping Fee", "original shipping fee")
    try: ship_fee = float(str(_sf).replace(",", "").replace("$", "").strip()) if _sf else 0.0
    except Exception: ship_fee = 0.0
    return {
        "order_id":   s("Order ID"),
        "ship_fee":   ship_fee,
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
        "created_time": s("Created Time") or s("Paid Time"),   # full timestamp
        "state":      s("State"),
        "city":       s("City"),
        "shipped_time":   s("Shipped Time"),
        "delivered_time": s("Delivered Time"),
        "revenue":        revenue,
    }

def _derive_delivery(n):
    """From a TikTok order row, derive (delivery_status, detail, delivered_at).
    TikTok's export carries Shipped Time / Delivered Time / Order Status — so we get
    delivery status straight from the data, no carrier API needed."""
    dt=(n.get("delivered_time") or "").strip()
    st=(n.get("shipped_time") or "").strip()
    os=(n.get("status") or "").lower()
    if dt or "delivered" in os or "completed" in os:
        return ("DELIVERED", ("Delivered "+dt).strip()+" · per TikTok", (dt or None))
    if st or "shipped" in os or "in transit" in os or "transit" in os:
        return ("IN_TRANSIT", ("Shipped "+st).strip()+" · per TikTok", None)
    return (None, None, None)

_GV_KW = ("giveaway", "give away", "give-away", "freebie", "free item")
_STAMP_KW = ("stamp", "envelope", "letter", "first class mail", "non-machinable", "non machinable")
def _looks_giveaway(name, ship_method):
    """A row looks like a giveaway if the product name says so, or it ships by a
    non-scannable method (stamp / envelope)."""
    n = (name or "").lower(); m = (ship_method or "").lower()
    if any(k in n for k in _GV_KW): return True
    if m and any(k in m for k in _STAMP_KW): return True
    return False

def _norm_whatnot(row):
    """Normalize a Whatnot row to the same dict shape. Column lookups are
    case-insensitive with aliases so export variants still work."""
    s = _row_get(row)
    pname = s("product_name", "product name", "item name", "product")
    try: qty = int(float(s("product_quantity", "product quantity", "quantity", "qty") or "1"))
    except Exception: qty = 1
    pkg = s("shipment_id", "shipment id", "order_number", "order number", "order_id", "order id")
    addr = s("shipping_address", "shipping address", "address")
    placed = s("placed_at", "placed at", "created_at", "created at", "order_date", "date")
    cancelled = s("cancelled_or_failed", "cancelled or failed", "status", "order_status")
    # Revenue — Whatnot exports vary; try many common price column names.
    rev_raw = s("price", "sold_price", "sold price", "sale_price", "sale price", "sold_for", "sold for",
                "amount", "item_price", "item price", "price_paid", "price paid", "buyer_paid",
                "gross_sales", "gross sales", "gross", "total", "subtotal", "sale_amount",
                "product_price", "product price", "line_total", "line total")
    try: revenue = float(str(rev_raw).replace("$", "").replace(",", "").strip()) if rev_raw else 0.0
    except Exception: revenue = 0.0
    return {
        "order_id":   s("order_id", "order id", "order_number", "order number"),
        "package_id": pkg,
        "tracking":   s("tracking_code", "tracking code", "tracking", "tracking_number", "tracking number"),
        "sku":        s("sku", "seller sku") or pname,   # Whatnot live items have empty SKU
        "product_name": pname,
        "quantity":   qty,
        "weight_g":   0,                    # Whatnot doesn't provide per-row weight
        "buyer_username": s("buyer_username", "buyer username", "username", "buyer"),
        "buyer_name": _parse_buyer_name(addr),
        "address":    addr,
        "postal":     s("postal_code", "postal code", "zip", "zipcode", "zip code"),
        "status":     "cancelled" if cancelled.lower() in ("cancelled","failed","canceled") else "to_ship",
        "cancel_reason": cancelled if cancelled.lower() in ("cancelled","failed","canceled") else "",
        "created_at": placed[:10],
        "created_time": placed,
        "state":      s("state", "province"),
        "city":       s("city", "town"),
        "revenue":    revenue,
        "ship_method": s("shipping_method", "shipping method", "ship method", "label_type",
                         "label type", "shipping service", "mail class", "carrier service",
                         "shipping option", "service"),
    }

@app.route("/api/shipments/import", methods=["POST"])
@req_role("admin", "cs")
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
    # Optional: when the live show STARTED. Used to attribute after-midnight sales to
    # this show (a sale at 00:30 still belongs to the show that began the night before).
    show_start_raw = (request.form.get("show_start") or "").strip()
    try:
        raw = f.stream.read().decode("utf-8-sig", errors="replace")
    except Exception as e:
        return jsonify({"ok": False, "error": "Could not read file: " + str(e)})
    # ── Duplicate-file guard ──────────────────────────────────────────
    # Hash the file contents. If this exact file was imported before, stop and tell
    # the user when/where — unless they explicitly confirm (force=1).
    file_hash = hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()
    force_dup = str(request.form.get("force") or "").lower() in ("1", "true", "yes")
    if not force_dup:
        _c = sdb()
        prev = _c.execute("""SELECT filename,label,platform,imported_at,imported_by,
                                    shipments_new,shipments_updated
                             FROM import_files WHERE file_hash=? ORDER BY id DESC LIMIT 1""",
                          (file_hash,)).fetchone()
        _c.close()
        if prev:
            p = dict(prev)
            return jsonify({
                "ok": False, "duplicate": True,
                "error": "This exact file was already imported on %s into show \"%s\"%s." % (
                    (p.get("imported_at") or "").replace("T", " ")[:16],
                    p.get("label") or "?",
                    (" by " + p["imported_by"]) if p.get("imported_by") else ""),
                "previous": p,
            })
    import io
    reader = csv.DictReader(io.StringIO(raw))
    fmt = _detect_csv_format(reader.fieldnames)
    if not fmt:
        cols = ", ".join((reader.fieldnames or [])[:40]) or "(none)"
        return jsonify({"ok": False, "error": "Unrecognized CSV format — expected TikTok or Whatnot export. "
                        "Columns found in your file: " + cols})

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

    # Plan limit: Pro is capped at 1,000 orders/day. Count what's already imported today
    # plus what this file would add.
    _od_lim=_plan_orders_day_limit(current_org())
    if _od_lim:
        _today=datetime.now().strftime("%Y-%m-%d")
        _c=sdb()
        try:
            _already=_c.execute("SELECT COUNT(*) FROM shipments WHERE substr(COALESCE(show_date,''),1,10)=?",
                                (_today,)).fetchone()[0]
        except Exception:
            _already=0
        _c.close()
        if _already+len(by_pkg) > _od_lim:
            return jsonify({"ok":False,"upgrade":True,"error":
                "Your plan allows %d orders per day. This import would bring today to %d. "
                "Contact us to move to an Enterprise plan."%(_od_lim,_already+len(by_pkg))})

    c = sdb()
    # Faster bulk writes on slow (network-volume) disks — safe for a re-runnable import.
    try: c.execute("PRAGMA synchronous=NORMAL"); c.execute("PRAGMA temp_store=MEMORY")
    except Exception: pass
    sku_map = {r["sku"]: r["weight_g"] for r in c.execute("SELECT sku, weight_g FROM sku_weights").fetchall()}
    _cfgrow = c.execute("SELECT packaging_overhead_g FROM weight_config WHERE id=1").fetchone()
    _overhead = _cfgrow["packaging_overhead_g"] if _cfgrow else 30

    # ── Show-window attribution ──────────────────────────────────────────
    # Determine when this show started. If the user didn't type it, default to the
    # earliest sale time in the file (≈ when the show began). Store it, then build the
    # list of all shows' windows so each order can be routed to the show whose window
    # contains its sale time — even across midnight.
    show_start_dt = _parse_dt(show_start_raw)
    if not show_start_dt:
        _cands = [d for d in (_parse_dt(n.get("created_time")) for n in norm) if d]
        show_start_dt = min(_cands) if _cands else None
    if show_start_dt:
        c.execute("""INSERT INTO show_state(import_label, show_start) VALUES(?,?)
                     ON CONFLICT(import_label) DO UPDATE SET show_start=excluded.show_start""",
                  (label, show_start_dt.isoformat(timespec="seconds")))
    show_windows = _load_show_windows(c, label, show_start_dt)
    win_start = dict(show_windows)  # label -> start datetime

    inserted = 0; updated = 0; items_inserted = 0
    unique_skus = set()
    try:
        for pkg_id, group in by_pkg.items():
            first = group[0]
            tracking = first["tracking"] or None
            # Which show does this order really belong to? (window contains the sale time)
            _created_dt = _parse_dt(first.get("created_time"))
            owner_label = _owning_show(_created_dt, show_windows, label)
            _owner_start = win_start.get(owner_label)
            owner_show_date = _owner_start.date().isoformat() if _owner_start else first["created_at"]
            dvs, dvd, dva = _derive_delivery(first)
            dtrk = datetime.now().isoformat(timespec='seconds') if dvs else None
            # Giveaway orders ship free (stamp/envelope) with no scannable tracking —
            # flag them so they don't sit forever in the "pending / to pack" pipeline.
            group_rev = sum((n.get("revenue") or 0) for n in group)
            is_gv = (platform == "whatnot" and group_rev == 0) or \
                    any(_looks_giveaway(n.get("product_name"), n.get("ship_method")) for n in group)
            new_status = "giveaway" if is_gv else "pending"
            # Shipping fee is per order (repeated across a package's item rows) — count once per order.
            _ord_ship = {}
            for n in group:
                sf = n.get("ship_fee") or 0
                if sf:
                    oid = n.get("order_id") or pkg_id
                    _ord_ship[oid] = max(_ord_ship.get(oid, 0), sf)
            ship_fee = round(sum(_ord_ship.values()), 2)
            existing = c.execute("SELECT shipment_id FROM shipments WHERE shipment_id=?", (pkg_id,)).fetchone()
            if existing:
                c.execute("""UPDATE shipments
                             SET tracking_code=COALESCE(?,tracking_code),
                                 buyer_username=?, buyer_name=?, address_full=?, postal_code=?,
                                 show_date=?, platform=?, import_batch=COALESCE(import_batch,?),
                                 import_label=?,
                                 shipping_fee=?,
                                 delivery_status=COALESCE(?,delivery_status),
                                 delivery_detail=COALESCE(?,delivery_detail),
                                 delivered_at=COALESCE(?,delivered_at),
                                 tracked_at=COALESCE(?,tracked_at)
                             WHERE shipment_id=?""",
                          (tracking, first["buyer_username"], first["buyer_name"],
                           first["address"], first["postal"], owner_show_date,
                           platform, import_batch, owner_label, ship_fee,
                           dvs, dvd, dva, dtrk, pkg_id))
                if is_gv:   # move a still-pending giveaway out of the pipeline
                    c.execute("UPDATE shipments SET status='giveaway' WHERE shipment_id=? AND status='pending'", (pkg_id,))
                updated += 1
            else:
                c.execute("""INSERT INTO shipments
                    (shipment_id, tracking_code, buyer_username, buyer_name, address_full,
                     postal_code, show_date, status, platform, import_batch, import_label, shipping_fee,
                     delivery_status, delivery_detail, delivered_at, tracked_at)
                    VALUES (?,?,?,?,?,?,?, ?, ?, ?, ?, ?, ?,?,?,?)""",
                    (pkg_id, tracking, first["buyer_username"], first["buyer_name"],
                     first["address"], first["postal"], owner_show_date, new_status,
                     platform, import_batch, owner_label, ship_fee,
                     dvs, dvd, dva, dtrk))
                inserted += 1
            # Replace items for this shipment.
            # IMPORTANT: re-importing a show must NOT wipe picking progress. Snapshot
            # which lines were already picked, then restore those flags after the
            # rebuild (matched on sku + product name).
            prev_picked = {}
            for pr in c.execute("""SELECT sku, product_name, picked_at FROM shipment_items
                                   WHERE shipment_id=? AND COALESCE(picked,0)=1""", (pkg_id,)).fetchall():
                prev_picked[((pr["sku"] or "").strip(), (pr["product_name"] or "").strip())] = pr["picked_at"]
            c.execute("DELETE FROM shipment_items WHERE shipment_id=?", (pkg_id,))
            for n in group:
                sku = n["sku"]
                # Prefer per-row weight from CSV (TikTok); fall back to sku_weights map
                w = (n["weight_g"] / max(len(group), 1)) if n["weight_g"] > 0 else sku_map.get(sku)
                _key = ((sku or "").strip(), (n["product_name"] or "").strip())
                _wasp = _key in prev_picked
                c.execute("""INSERT INTO shipment_items
                             (shipment_id, order_id, sku, product_name, quantity, item_weight_g, revenue,
                              created_time, buyer_state, buyer_city, picked, picked_at)
                             VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                          (pkg_id, n["order_id"], sku, n["product_name"], n["quantity"], w, n.get("revenue", 0) or 0,
                           n.get("created_time") or None, n.get("state") or None, n.get("city") or None,
                           1 if _wasp else 0, prev_picked.get(_key) if _wasp else None))
                items_inserted += 1
                if sku: unique_skus.add(sku)
            _recompute_shipment_weight(c, pkg_id, overhead=_overhead)
        c.commit()
    finally:
        c.close()

    # SKUs missing weights
    c = sdb()
    have_weight = {r["sku"] for r in c.execute("SELECT sku FROM sku_weights WHERE sku IN ({})".format(
        ",".join("?"*len(unique_skus)) or "''"), tuple(unique_skus) if unique_skus else ()).fetchall()}
    c.close()
    sku_missing = sorted(unique_skus - have_weight)

    # Remember this file so an identical re-upload is caught next time.
    try:
        _c = sdb()
        _c.execute("""INSERT INTO import_files(file_hash,filename,label,platform,rows,
                                               shipments_new,shipments_updated,imported_by)
                      VALUES(?,?,?,?,?,?,?,?)""",
                   (file_hash, f.filename[:120], label, platform, len(norm),
                    inserted, updated, session.get("name","")[:60]))
        _c.commit(); _c.close()
    except Exception as e:
        print("import_files record error:", e, flush=True)
    alog("shipments.import","%s '%s': %d new, %d updated"%(platform,label,inserted,updated))
    # A winner who was waiting for an order may now have one in this import — attach it.
    gv_attached=_autoattach_giveaways()
    return jsonify({
        "ok": True,
        "format": fmt,
        "platform": platform,
        "import_batch": import_batch,
        "label": label,
        "shipments_new": inserted,
        "shipments_updated": updated,
        "giveaways_attached": gv_attached,
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
                                   status, missing_weights, show_date, imported_at, import_label, platform,
                                   delivery_status, delivery_detail, delivered_at, tracked_at
                            FROM shipments WHERE import_label=?
                            ORDER BY imported_at DESC LIMIT ?""", (show, limit)).fetchall()
    else:
        rows = c.execute("""SELECT shipment_id, tracking_code, buyer_username, buyer_name,
                                   total_items, expected_weight_g, actual_weight_g, weight_status,
                                   status, missing_weights, show_date, imported_at, import_label, platform,
                                   delivery_status, delivery_detail, delivered_at, tracked_at
                            FROM shipments ORDER BY imported_at DESC LIMIT ?""", (limit,)).fetchall()
    c.close()
    return jsonify([dict(r) for r in rows])


def _giveaway_by_tracking(code):
    """Find a STANDALONE giveaway by its own tracking number (exact or substring),
    for the pack/record screen. Piggyback giveaways ride an order and are excluded."""
    code=(code or "").strip()
    if not code: return None
    g=gdb()
    r=g.execute("""SELECT * FROM giveaways
                   WHERE tracking_number IS NOT NULL AND tracking_number!=''
                     AND COALESCE(attach_mode,'standalone')!='piggyback'
                     AND (tracking_number=? OR ? LIKE '%'||tracking_number||'%'
                          OR tracking_number LIKE '%'||?||'%')
                   ORDER BY id DESC LIMIT 1""",(code,code,code)).fetchone()
    g.close()
    return dict(r) if r else None

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
        # Standalone giveaway with its own label? Make it packable/filmable by tracking.
        gv=_giveaway_by_tracking(code)
        if gv:
            return jsonify({
                "ok": True, "is_giveaway": True,
                "shipment": {"shipment_id":"GA-"+str(gv["id"]),"tracking_code":gv.get("tracking_number") or code,
                             "buyer_name":gv.get("address_name") or gv.get("winner_username") or "Giveaway",
                             "status":"giveaway","is_giveaway":True,"giveaway_id":gv["id"]},
                "items": [{"sku":"🎁 GIVEAWAY","product_name":(gv.get("prize_name") or "Giveaway prize")+
                           (" — @"+gv["winner_username"] if gv.get("winner_username") else ""),"quantity":1,"item_weight_g":None}],
                "config": {}, "giveaways": [],
            })
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
        "giveaways": _pending_giveaways_for(row["shipment_id"], row["tracking_code"]),
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
    if os.path.exists(log_file()):
        with open(log_file()) as f:
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
        .replace("__NAME__", esc(session.get("name", "")))
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
    """Detail for picking — items with picked flag for tap-to-check workflow.
    Hard-blocks picking when the show still has cancelled items on the table."""
    if not re.match(r'^[A-Za-z0-9_\-]{1,64}$', sid):
        return jsonify({"ok": False, "error": "Invalid id"})
    c = sdb()
    s = c.execute("SELECT * FROM shipments WHERE shipment_id=?", (sid,)).fetchone()
    if not s:
        c.close()
        return jsonify({"ok": False, "error": "Shipment not found"})
    label = s["import_label"]
    items = c.execute("""SELECT id, sku, product_name, quantity, COALESCE(picked,0) AS picked,
                                picked_at, COALESCE(cancelled,0) AS cancelled
                         FROM shipment_items WHERE shipment_id=?
                         ORDER BY COALESCE(cancelled,0), COALESCE(picked,0), id""", (sid,)).fetchall()
    c.close()
    # Cleanup gate — if the show has cancelled items still sitting on the table,
    # tell the picker to go clear them first. Admin/CS can override via ?force=1.
    force = request.args.get("force") == "1"
    role = session.get("role", "")
    cleanup_blocked = False
    cleanup_info = None
    if label:
        cp = _cleanup_progress(label)
        if not cp["is_clean"] and not (force and role in ("admin", "cs")):
            cleanup_blocked = True
        cleanup_info = cp
    # Already-handled gate — an order that's been picked (or packed/shipped) must not
    # be re-opened for picking. Admin/CS can override with ?force=1 to fix a mistake.
    st = (s["status"] or "").lower()
    already = st in ("picked", "packed", "shipped") or bool(s["picked_at"])
    if already and not (force and role in ("admin", "cs")):
        already_picked = True
    else:
        already_picked = False
    return jsonify({
        "ok": True,
        "shipment": dict(s),
        "items": [dict(i) for i in items],
        "cleanup_blocked": cleanup_blocked,
        "cleanup": cleanup_info,
        "already_picked": already_picked,
        "picked_by": s["picked_by"],
        "picked_at": s["picked_at"],
        "giveaways": _pending_giveaways_for(s["shipment_id"], s["tracking_code"]),
    })

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
    s = c.execute("SELECT status, picked_by, picked_at FROM shipments WHERE shipment_id=?", (sid,)).fetchone()
    if not s:
        c.close()
        return jsonify({"ok": False, "error": "Shipment not found"})
    if s["status"] == "cancelled":
        c.close()
        return jsonify({"ok": False, "error": "This order is cancelled — do not pick"})
    # Already picked (or already packed/shipped) — don't re-attribute or double-count.
    st = (s["status"] or "").lower()
    if st in ("picked", "packed", "shipped") or s["picked_at"]:
        who = s["picked_by"] or "someone"
        c.close()
        return jsonify({"ok": False, "already_picked": True,
                        "picked_by": s["picked_by"], "picked_at": s["picked_at"],
                        "error": "Already picked by " + who})
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
    done_map = {r["import_label"]: dict(r) for r in c.execute("SELECT * FROM show_state").fetchall()}
    c.close()
    # Attach cleanup status so the picker can warn / block on unclean shows.
    out = []
    for r in rows:
        d = dict(r)
        cp = _cleanup_progress(d["name"])
        d["cleanup"] = {
            "is_clean": cp["is_clean"],
            "groups_total": cp["total_groups"],
            "groups_done": cp["groups_done"],
            "groups_pending": cp["groups_pending"],
        }
        st = done_map.get(d["name"])
        d["done"] = bool(st and st.get("done"))
        d["done_by"] = st.get("done_by") if st else None
        d["done_at"] = st.get("done_at") if st else None
        out.append(d)
    return jsonify(out)

@app.route("/api/home/fulfillment")
@req_role("admin","cs")
def api_home_fulfillment():
    """Per-show breakdown of orders still to pick / pack, for the manager home
    widget. 'to_pick' = still pending (not pulled); 'to_pack' = pending or
    picked but not yet recorded/packed. Limited to the recent show window."""
    cutoff_dt=(datetime.now()-timedelta(days=SHOW_WINDOW_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    c=sdb()
    rows=c.execute("""
        SELECT import_label AS name,
               COUNT(*) AS total,
               SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) AS to_pick,
               SUM(CASE WHEN status IN ('pending','picked') THEN 1 ELSE 0 END) AS to_pack,
               SUM(CASE WHEN status='packed' THEN 1 ELSE 0 END) AS packed,
               SUM(CASE WHEN status='shipped' THEN 1 ELSE 0 END) AS shipped,
               SUM(CASE WHEN status='cancelled' THEN 1 ELSE 0 END) AS cancelled,
               MAX(imported_at) AS last_import
        FROM shipments
        WHERE import_label IS NOT NULL AND import_label != ''
          AND imported_at >= ?
        GROUP BY import_label
        HAVING to_pack > 0
        ORDER BY to_pack DESC, last_import DESC
    """,(cutoff_dt,)).fetchall()
    c.close()
    shows=[dict(r) for r in rows]
    return jsonify({
        "total_to_pack": sum(s["to_pack"] for s in shows),
        "total_to_pick": sum(s["to_pick"] for s in shows),
        "shows_remaining": len(shows),
        "shows": shows,
    })

# ── Settings / Manager PIN / Permissions ───────────────────────────
_DEFAULT_PERMS={
    "mark_show_done": {"roles":["admin","cs"], "require_pin": True},
    "import_csv":     {"roles":["admin","cs"], "require_pin": False},
    "manage_users":   {"roles":["admin"],      "require_pin": False},
    "attach_giveaway":{"roles":["admin","cs"], "require_pin": False},
}
_PERM_LABELS={
    "mark_show_done":"Mark a show DONE",
    "import_csv":"Import orders CSV",
    "manage_users":"Manage users & badges",
    "attach_giveaway":"Attach a giveaway to an order",
}
def _get_setting(key, default=None):
    c=sdb(); r=c.execute("SELECT value FROM settings WHERE key=?",(key,)).fetchone(); c.close()
    return r["value"] if r else default
def _set_setting(key, value):
    c=sdb()
    c.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(key,str(value)))
    c.commit(); c.close()
def _get_perms():
    raw=_get_setting("permissions")
    out=dict(_DEFAULT_PERMS)
    if raw:
        try: out.update(json.loads(raw))
        except Exception: pass
    return out
def _manager_pin_set():
    return bool(_get_setting("manager_pin_hash"))
def _verify_manager_pin(pin):
    h=_get_setting("manager_pin_hash")
    if not h: return False
    try: return bcrypt.checkpw((pin or "").encode(), h.encode())
    except Exception: return False

@app.route("/api/shows/done", methods=["POST"])
@req_role("admin","cs")
def api_show_done():
    """Toggle a show's manual DONE flag (set after verifying pending).
    Gated by the permissions config: allowed roles + (optionally) manager PIN."""
    d = request.get_json() or {}
    label = (d.get("label") or "").strip()
    if not label:
        return jsonify({"ok": False, "error": "label required"})
    perm=_get_perms().get("mark_show_done",{})
    if session.get("role") not in (perm.get("roles") or ["admin","cs"]):
        return jsonify({"ok": False, "error": "Your role is not allowed to mark shows done."}), 403
    if perm.get("require_pin"):
        if not _manager_pin_set():
            return jsonify({"ok": False, "error": "Manager PIN not set yet — set it in Permissions.", "need_pin_setup": True}), 400
        if not _verify_manager_pin(d.get("pin","")):
            return jsonify({"ok": False, "error": "Wrong manager PIN.", "pin_required": True}), 401
    done = 1 if d.get("done", True) else 0
    c = sdb()
    c.execute("""INSERT INTO show_state(import_label,done,done_at,done_by) VALUES(?,?,?,?)
                 ON CONFLICT(import_label) DO UPDATE SET done=excluded.done,
                    done_at=excluded.done_at, done_by=excluded.done_by""",
              (label, done, datetime.now().isoformat(timespec='seconds') if done else None,
               session.get("name","")[:60] if done else None))
    c.commit(); c.close()
    return jsonify({"ok": True, "done": bool(done)})

@app.route("/admin/permissions")
@req_role("admin")
def permissions_page():
    return PERMISSIONS_HTML.replace("__NAME__",esc(session.get("name",""))).replace("__NAVBAR__",_navbar("permissions")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

@app.route("/api/permissions")
@req_role("admin")
def api_permissions_get():
    return jsonify({"ok":True,"permissions":_get_perms(),"labels":_PERM_LABELS,
                    "pin_set":_manager_pin_set(),
                    "actions":list(_DEFAULT_PERMS.keys()),
                    "roles":["admin","cs","picker","worker"]})

@app.route("/api/permissions",methods=["POST"])
@req_role("admin")
def api_permissions_save():
    d=request.get_json() or {}
    perms=d.get("permissions")
    if not isinstance(perms,dict):
        return jsonify({"ok":False,"error":"invalid permissions"})
    valid_roles={"admin","cs","picker","worker"}
    clean={}
    for k,v in perms.items():
        if k not in _DEFAULT_PERMS or not isinstance(v,dict): continue
        roles=[r for r in (v.get("roles") or []) if r in valid_roles] or ["admin"]
        clean[k]={"roles":roles,"require_pin":bool(v.get("require_pin"))}
    _set_setting("permissions", json.dumps(clean))
    return jsonify({"ok":True})

@app.route("/api/permissions/pin",methods=["POST"])
@req_role("admin")
def api_permissions_pin():
    d=request.get_json() or {}
    pin=(d.get("pin") or "").strip()
    if not pin.isdigit() or len(pin)<4:
        return jsonify({"ok":False,"error":"PIN must be at least 4 digits"})
    _set_setting("manager_pin_hash", bcrypt.hashpw(pin.encode(),bcrypt.gensalt()).decode())
    return jsonify({"ok":True})

# ══════════════════════════════════════════════════════════
# INVENTORY & COSTING — catalog, receiving (weighted-avg), profit
# ══════════════════════════════════════════════════════════
def _gen_sku():
    """Auto internal SKU for products with no manufacturer barcode. Plain 4-digit
    number (1000–9999) so it's easy to read/type; widens to 5–6 digits only if the
    4-digit space fills up or we keep colliding."""
    c=sdb()
    try:
        import random
        for lo,hi,tries in ((1000,9999,80),(10000,99999,80),(100000,999999,80)):
            for _ in range(tries):
                sku=str(random.randint(lo,hi))
                if not c.execute("SELECT 1 FROM products WHERE sku=?",(sku,)).fetchone():
                    return sku
        return str(secrets.randbelow(900000)+100000)
    finally:
        c.close()

def _receive_stock(c, sku, qty, cost, po_id=None, note=None, name=None, barcode=None):
    """Add qty of sku to stock at unit `cost`; recompute weighted-average cost.
    Returns (new_on_hand, new_avg_cost)."""
    now=datetime.now().isoformat(timespec='seconds')
    p=c.execute("SELECT on_hand,avg_cost FROM products WHERE sku=?",(sku,)).fetchone()
    if not p:
        c.execute("INSERT INTO products(sku,name,barcode,updated_at) VALUES(?,?,?,?)",
                  (sku,(name or sku),(barcode or None),now))
        oh,ac=0,0.0
    else:
        oh,ac=p["on_hand"] or 0, p["avg_cost"] or 0.0
    new_oh=oh+qty
    new_avg=((oh*ac)+(qty*cost))/new_oh if new_oh>0 else cost
    c.execute("UPDATE products SET on_hand=?,avg_cost=?,updated_at=? WHERE sku=?",
              (new_oh,round(new_avg,4),now,sku))
    c.execute("INSERT INTO stock_moves(sku,qty,unit_cost,po_id,note,moved_by) VALUES(?,?,?,?,?,?)",
              (sku,qty,cost,po_id,note,session.get("name","")[:60]))
    return new_oh, round(new_avg,4)

def _deplete_stock_for(c, shipment_id):
    """No-op. Stock depletion now happens at MATCH time (api_preshow_map), keyed to
    the real catalog product — not the generic sticker number, which isn't a product
    SKU and reuses across shows. Kept so existing pack-time call sites stay valid."""
    return

@app.route("/api/products")
@req_role("admin","cs")
def api_products():
    q=(request.args.get("q") or "").strip().lower()
    c=sdb()
    if q:
        like='%'+q+'%'
        rows=c.execute("""SELECT * FROM products WHERE LOWER(sku) LIKE ? OR LOWER(COALESCE(name,'')) LIKE ?
                          OR COALESCE(barcode,'') LIKE ? ORDER BY name LIMIT 500""",(like,like,like)).fetchall()
    else:
        rows=c.execute("SELECT * FROM products ORDER BY updated_at DESC, name LIMIT 500").fetchall()
    c.close()
    out=[dict(r) for r in rows]
    if session.get("role","")!="admin":   # cost is admin-only
        for d in out: d.pop("avg_cost",None)
    return jsonify(out)

@app.route("/api/product/lookup/<code>")
@req_role("admin","cs","worker","picker")
def api_product_lookup(code):
    code=(code or "").strip()
    c=sdb()
    r=c.execute("SELECT * FROM products WHERE sku=? OR barcode=?",(code,code)).fetchone()
    c.close()
    p=dict(r) if r else None
    if p and session.get("role","")!="admin": p.pop("avg_cost",None)
    return jsonify({"ok":bool(r),"product":p})

@app.route("/api/product/<sku>")
@req_role("admin","cs")
def api_product_detail(sku):
    c=sdb(); r=c.execute("SELECT * FROM products WHERE sku=?",(sku,)).fetchone(); c.close()
    if not r: return jsonify({"ok":False,"error":"Not found"}),404
    p=dict(r)
    if session.get("role")!="admin":   # cost is admin-only
        p.pop("avg_cost",None)
    # margin helper for the UI
    if p.get("target_price") and p.get("avg_cost") is not None:
        p["margin"]=round((p.get("target_price") or 0)-(p.get("avg_cost") or 0),2)
    return jsonify({"ok":True,"product":p})

def _gen_barcode():
    """A unique internal barcode value (12 digits, '20' prefix) for products that
    don't have a manufacturer barcode. Printable as Code128 via the label route."""
    import random
    c=sdb()
    try:
        for _ in range(300):
            code="20"+"".join(random.choice("0123456789") for _ in range(10))
            if not c.execute("SELECT 1 FROM products WHERE barcode=?",(code,)).fetchone():
                return code
        return "20"+str(int(time.time()))[-10:]
    finally: c.close()

@app.route("/api/products",methods=["POST"])
@req_role("admin","cs")
def api_product_save():
    d=request.get_json() or {}
    sku=(d.get("sku") or "").strip() or _gen_sku()
    is_admin=session.get("role")=="admin"
    now=datetime.now().isoformat(timespec='seconds')
    c=sdb()
    exists=c.execute("SELECT on_hand,avg_cost FROM products WHERE sku=?",(sku,)).fetchone()
    c.execute("""INSERT INTO products(sku,name,barcode,image_url,category,updated_at)
                 VALUES(?,?,?,?,?,?)
                 ON CONFLICT(sku) DO UPDATE SET name=excluded.name,barcode=excluded.barcode,
                    image_url=COALESCE(excluded.image_url,products.image_url),
                    category=excluded.category,updated_at=excluded.updated_at""",
              (sku,(d.get("name") or "").strip(),(d.get("barcode") or "").strip() or None,
               d.get("image_url"),d.get("category"),now))
    # Target sell price + supplier + reorder point are editable by admin/cs.
    if "target_price" in d:
        c.execute("UPDATE products SET target_price=? WHERE sku=?",(float(d.get("target_price") or 0),sku))
    if "supplier" in d:
        c.execute("UPDATE products SET supplier=? WHERE sku=?",((d.get("supplier") or "").strip() or None,sku))
    if "reorder_point" in d:
        try: rp=int(float(d.get("reorder_point") or 0))
        except Exception: rp=0
        c.execute("UPDATE products SET reorder_point=? WHERE sku=?",(rp,sku))
    if "parent_sku" in d or "variant_name" in d:
        psku=(d.get("parent_sku") or "").strip() or None
        if psku==sku: psku=None   # a product can't be its own parent
        c.execute("UPDATE products SET parent_sku=?,variant_name=? WHERE sku=?",
                  (psku,(d.get("variant_name") or "").strip() or None,sku))
    # Cost + on-hand are admin-only. A manual on-hand change is logged as a stock move.
    if is_admin and d.get("cost") not in (None,""):
        c.execute("UPDATE products SET avg_cost=? WHERE sku=?",(round(float(d.get("cost")),4),sku))
    if is_admin and d.get("on_hand") not in (None,""):
        new_oh=int(float(d.get("on_hand")))
        old_oh=(exists["on_hand"] if exists else 0) or 0
        c.execute("UPDATE products SET on_hand=? WHERE sku=?",(new_oh,sku))
        if new_oh!=old_oh:
            c.execute("""INSERT INTO stock_moves(sku,qty,unit_cost,note,moved_by)
                         VALUES(?,?,?,?,?)""",
                      (sku,new_oh-old_oh,round(float(exists["avg_cost"] if exists else 0) or 0,4),
                       "manual adjustment",session.get("user")))
    c.commit(); c.close()
    return jsonify({"ok":True,"sku":sku})

@app.route("/api/product/<sku>/gen-barcode",methods=["POST"])
@req_role("admin","cs")
def api_product_gen_barcode(sku):
    code=_gen_barcode()
    c=sdb()
    if not c.execute("SELECT 1 FROM products WHERE sku=?",(sku,)).fetchone():
        c.close(); return jsonify({"ok":False,"error":"Save the product first"})
    c.execute("UPDATE products SET barcode=?,updated_at=? WHERE sku=?",
              (code,datetime.now().isoformat(timespec='seconds'),sku))
    c.commit(); c.close()
    return jsonify({"ok":True,"barcode":code})

_PROD_IMG_EXT={"jpg","jpeg","png","webp","gif"}

@app.route("/api/product/<sku>/image",methods=["POST"])
@req_role("admin","cs")
def api_product_image_upload(sku):
    c=sdb()
    if not c.execute("SELECT 1 FROM products WHERE sku=?",(sku,)).fetchone():
        c.close(); return jsonify({"ok":False,"error":"Save the product first"})
    c.close()
    f=request.files.get("file")
    if not f or not f.filename: return jsonify({"ok":False,"error":"Pick an image"})
    ext=f.filename.rsplit(".",1)[-1].lower() if "." in f.filename else ""
    if ext not in _PROD_IMG_EXT: return jsonify({"ok":False,"error":"Use JPG, PNG, WEBP or GIF"})
    safe=secure_filename(sku) or "p"
    org=current_org()
    key=f"{org}/products/{safe}.{ext}"
    if r2:
        r2.upload_fileobj(f.stream,R2_BUCKET,key,ExtraArgs={"ContentType":f.mimetype or "image/"+ext})
    else:
        d=org_path(org,"products"); os.makedirs(d,exist_ok=True)
        f.save(os.path.join(d,safe+"."+ext))
        key=safe+"."+ext
    url=f"/product-image/{safe}?v={int(time.time())}"
    cc=sdb(); cc.execute("UPDATE products SET image_key=?,image_url=?,updated_at=? WHERE sku=?",
                         (key,url,datetime.now().isoformat(timespec='seconds'),sku)); cc.commit(); cc.close()
    return jsonify({"ok":True,"image_url":url})

@app.route("/product-image/<sku>")
@req_login
def product_image(sku):
    c=sdb(); r=c.execute("SELECT image_key FROM products WHERE sku=?",(sku,)).fetchone(); c.close()
    key=r["image_key"] if r else None
    if not key: return ("",404)
    if r2 and "/" in key:
        try:
            url=r2.generate_presigned_url("get_object",Params={"Bucket":R2_BUCKET,"Key":key},ExpiresIn=R2_PRESIGN_TTL)
            return redirect(url)
        except Exception: return ("",404)
    p=org_path(current_org(),"products",key)
    if not os.path.exists(p): return ("",404)
    return send_file(p)

@app.route("/api/inventory/stats")
@req_role("admin","cs")
def api_inventory_stats():
    c=sdb()
    r=c.execute("""SELECT COUNT(*) skus, COALESCE(SUM(on_hand),0) units,
                          COALESCE(SUM(CASE WHEN on_hand>0 THEN on_hand*avg_cost ELSE 0 END),0) value,
                          SUM(CASE WHEN reorder_point>0 AND on_hand<=reorder_point THEN 1 ELSE 0 END) low,
                          SUM(CASE WHEN on_hand<=0 THEN 1 ELSE 0 END) out,
                          SUM(CASE WHEN on_hand<0 THEN 1 ELSE 0 END) neg
                   FROM products""").fetchone()
    c.close()
    out={"skus":r["skus"],"units":r["units"],"low":r["low"] or 0,"out":r["out"] or 0,"negative":r["neg"] or 0}
    if session.get("role")=="admin": out["value"]=round(r["value"] or 0,2)
    return jsonify({"ok":True,"stats":out})

@app.route("/api/inventory/low-stock")
@req_role("admin","cs")
def api_inventory_low_stock():
    c=sdb()
    rows=[dict(x) for x in c.execute(
        """SELECT sku,name,on_hand,reorder_point,image_url FROM products
           WHERE (reorder_point>0 AND on_hand<=reorder_point) OR on_hand<0
           ORDER BY (on_hand-reorder_point) ASC LIMIT 300""").fetchall()]
    c.close()
    return jsonify({"ok":True,"products":rows})

@app.route("/api/product/<sku>/moves")
@req_role("admin","cs")
def api_product_moves(sku):
    c=sdb()
    rows=[dict(x) for x in c.execute(
        "SELECT qty,unit_cost,note,moved_at,moved_by FROM stock_moves WHERE sku=? ORDER BY id DESC LIMIT 100",(sku,)).fetchall()]
    c.close()
    if session.get("role")!="admin":
        for r in rows: r.pop("unit_cost",None)
    return jsonify({"ok":True,"moves":rows})

@app.route("/api/inventory/bestsellers")
@req_role("admin","cs")
def api_inventory_bestsellers():
    try: days=int(request.args.get("days") or 30)
    except Exception: days=30
    since=(datetime.now()-timedelta(days=days)).isoformat(timespec='seconds')
    c=sdb()
    rows=[dict(x) for x in c.execute(
        """SELECT m.sku, COALESCE(p.name,m.sku) name, p.on_hand, -SUM(m.qty) sold
           FROM stock_moves m LEFT JOIN products p ON p.sku=m.sku
           WHERE m.note LIKE 'sale (%' AND m.qty<0 AND m.moved_at>=?
           GROUP BY m.sku ORDER BY sold DESC LIMIT 20""",(since,)).fetchall()]
    c.close()
    return jsonify({"ok":True,"days":days,"products":rows})

@app.route("/api/products/export.csv")
@req_role("admin","cs")
def api_products_export():
    is_admin=session.get("role")=="admin"
    c=sdb()
    rows=c.execute("""SELECT sku,name,barcode,category,supplier,variant_name,parent_sku,
                             on_hand,reorder_point,avg_cost,target_price FROM products ORDER BY name""").fetchall()
    c.close()
    buf=io.StringIO(); w=csv.writer(buf)
    hdr=["SKU","Name","Barcode","Category","Supplier","Variant","Parent SKU","On hand","Reorder point","Target price"]
    if is_admin: hdr[9:9]=["Avg cost","Stock value"]
    w.writerow(hdr)
    for r in rows:
        row=[r["sku"],r["name"] or "",r["barcode"] or "",r["category"] or "",r["supplier"] or "",
             r["variant_name"] or "",r["parent_sku"] or "",r["on_hand"] or 0,r["reorder_point"] or 0]
        if is_admin:
            val=round((r["on_hand"] or 0)*(r["avg_cost"] or 0),2)
            row+=[round(r["avg_cost"] or 0,4),val]
        row.append(r["target_price"] or 0)
        w.writerow(row)
    return Response(buf.getvalue(),mimetype="text/csv",
                    headers={"Content-Disposition":"attachment; filename=inventory.csv"})

@app.route("/api/product/<sku>/count",methods=["POST"])
@req_role("admin","cs")
def api_product_count(sku):
    """Stock take: set on_hand to a counted value, logging the variance as a move."""
    d=request.get_json() or {}
    try: counted=int(float(d.get("counted")))
    except Exception: return jsonify({"ok":False,"error":"Enter a counted quantity"})
    c=sdb()
    r=c.execute("SELECT on_hand,avg_cost FROM products WHERE sku=?",(sku,)).fetchone()
    if not r: c.close(); return jsonify({"ok":False,"error":"Not found"}),404
    old=r["on_hand"] or 0; delta=counted-old
    c.execute("UPDATE products SET on_hand=?,updated_at=? WHERE sku=?",
              (counted,datetime.now().isoformat(timespec='seconds'),sku))
    if delta!=0:
        c.execute("INSERT INTO stock_moves(sku,qty,unit_cost,note,moved_by) VALUES(?,?,?,?,?)",
                  (sku,delta,round(r["avg_cost"] or 0,4),"stock take (counted %d)"%counted,session.get("user")))
    c.commit(); c.close()
    return jsonify({"ok":True,"sku":sku,"old":old,"counted":counted,"delta":delta})

@app.route("/api/po/<int:poid>/scan-receive",methods=["POST"])
@req_role("admin","cs")
def api_po_scan_receive(poid):
    """Scan a barcode/SKU on the receive screen → receive 1 unit of the matching line."""
    d=request.get_json() or {}
    code=(d.get("code") or "").strip()
    if not code: return jsonify({"ok":False,"error":"No code"})
    c=sdb()
    # resolve barcode -> sku
    pr=c.execute("SELECT sku FROM products WHERE sku=? OR barcode=?",(code,code)).fetchone()
    target=pr["sku"] if pr else code
    it=c.execute("""SELECT * FROM po_items WHERE po_id=? AND sku=? AND qty_received<qty_ordered
                    ORDER BY id LIMIT 1""",(poid,target)).fetchone()
    if not it:
        c.close(); return jsonify({"ok":False,"error":"No open line matches "+code})
    oh,ac=_receive_stock(c,it["sku"],1,it["unit_cost"] or 0,po_id=poid,note="PO receive (scan)",name=it["product_name"])
    c.execute("UPDATE po_items SET qty_received=qty_received+1 WHERE id=?",(it["id"],))
    left=c.execute("SELECT COALESCE(SUM(qty_ordered-qty_received),0) n FROM po_items WHERE po_id=?",(poid,)).fetchone()["n"]
    if left<=0:
        c.execute("UPDATE purchase_orders SET status='received',received_at=? WHERE id=?",
                  (datetime.now().isoformat(timespec='seconds'),poid))
    else:
        c.execute("UPDATE purchase_orders SET status='receiving' WHERE id=? AND status IN ('open','ordered','in_transit')",(poid,))
    newrec=c.execute("SELECT qty_received,qty_ordered,product_name FROM po_items WHERE id=?",(it["id"],)).fetchone()
    c.commit(); c.close()
    return jsonify({"ok":True,"sku":it["sku"],"name":newrec["product_name"],
                    "qty_received":newrec["qty_received"],"qty_ordered":newrec["qty_ordered"],"po_done":left<=0})

@app.route("/api/products/template.csv")
@req_role("admin")
def api_products_template():
    rows=("SKU,Name,Barcode,Category,Quantity,Unit Cost\r\n"
          ",Matte Lipstick - Red,012345678905,Lips,24,3.50\r\n"
          ",Velvet Blush,012345678912,Cheeks,12,2.10\r\n"
          "1042,House Brush (no barcode),,Tools,40,1.25\r\n")
    return Response(rows,mimetype="text/csv",
                    headers={"Content-Disposition":"attachment;filename=product_import_template.csv"})

@app.route("/api/products/import",methods=["POST"])
@req_role("admin")
def api_products_import():
    """Bulk-load the catalog + stock from a CSV. Headers are matched loosely
    (case-insensitive aliases). mode=add → receive qty at cost (weighted avg);
    mode=replace → set on_hand (and avg_cost when a cost is given) outright.
    Admin only (touches cost)."""
    f=request.files.get("file")
    if not f: return jsonify({"ok":False,"error":"No file uploaded"})
    mode=(request.form.get("mode") or "add").lower()
    import csv, io as _io
    try:
        text=f.read().decode("utf-8-sig",errors="replace")
    except Exception as e:
        return jsonify({"ok":False,"error":"Could not read file: "+str(e)})
    rdr=csv.DictReader(_io.StringIO(text))
    def pick(row,*keys):
        for k in list(row.keys()):
            if (k or "").strip().lower() in keys:
                return (row[k] or "").strip()
        return ""
    created=0; updated=0; stocked=0; skipped=0
    now=datetime.now().isoformat(timespec='seconds')
    c=sdb()
    for row in rdr:
        name=pick(row,"name","product","product name","title","description")
        sku=pick(row,"sku","id","code","item","item id")
        barcode=pick(row,"barcode","upc","ean","gtin","bar code")
        category=pick(row,"category","cat","type","department")
        qs=pick(row,"qty","quantity","on hand","on_hand","onhand","stock","count")
        cs=pick(row,"cost","unit cost","unit_cost","unitcost","price","avg cost","avg_cost")
        if not (name or sku or barcode): skipped+=1; continue
        try: qty=int(float(qs)) if qs else 0
        except Exception: qty=0
        try: cost=float(cs.replace("$","").replace(",","")) if cs else 0.0
        except Exception: cost=0.0
        existed=bool(c.execute("SELECT 1 FROM products WHERE sku=?",(sku,)).fetchone()) if sku else False
        if not sku: sku=_gen_sku()
        c.execute("""INSERT INTO products(sku,name,barcode,category,updated_at) VALUES(?,?,?,?,?)
                     ON CONFLICT(sku) DO UPDATE SET name=excluded.name,
                        barcode=COALESCE(NULLIF(excluded.barcode,''),products.barcode),
                        category=COALESCE(NULLIF(excluded.category,''),products.category),
                        updated_at=excluded.updated_at""",
                  (sku,name or sku,barcode or None,category or None,now))
        if mode=="replace":
            if cs!="":
                c.execute("UPDATE products SET on_hand=?,avg_cost=? WHERE sku=?",(qty,round(cost,4),sku))
            else:
                c.execute("UPDATE products SET on_hand=? WHERE sku=?",(qty,sku))
            if qty: stocked+=1
        else:
            if qty>0:
                _receive_stock(c,sku,qty,cost,note="CSV import",name=name,barcode=barcode); stocked+=1
        updated+=1 if existed else 0
        created+=0 if existed else 1
    c.commit(); c.close()
    return jsonify({"ok":True,"created":created,"updated":updated,"stocked":stocked,
                    "skipped":skipped,"mode":mode})

@app.route("/api/receive",methods=["POST"])
@req_role("admin","cs")
def api_receive():
    d=request.get_json() or {}
    sku=(d.get("sku") or "").strip()
    if not sku: return jsonify({"ok":False,"error":"SKU required"})
    try: qty=int(d.get("qty",0))
    except Exception: qty=0
    try: cost=float(d.get("unit_cost",0))
    except Exception: cost=0.0
    if qty<=0: return jsonify({"ok":False,"error":"Qty must be > 0"})
    c=sdb()
    oh,ac=_receive_stock(c, sku, qty, cost, po_id=d.get("po_id"), note=d.get("note"),
                         name=d.get("name"), barcode=d.get("barcode"))
    c.commit(); c.close()
    return jsonify({"ok":True,"sku":sku,"on_hand":oh,"avg_cost":ac})

def _po_insert_items(c, poid, items):
    now=datetime.now().isoformat(timespec='seconds')
    for it in (items or []):
        sku=(it.get("sku") or "").strip()
        name=(it.get("name") or "").strip()
        try: qty=int(float(it.get("qty") or 0))
        except Exception: qty=0
        try: cost=float(it.get("unit_cost") or 0)
        except Exception: cost=0.0
        if not name and not sku: continue
        # Ensure a catalog product exists for this line so it's always receivable
        # (new supplier products enter the catalog here — that's the intent).
        if sku:
            if not c.execute("SELECT 1 FROM products WHERE sku=?",(sku,)).fetchone():
                c.execute("INSERT INTO products(sku,name,updated_at) VALUES(?,?,?)",(sku,name or sku,now))
        else:
            sku=_gen_sku()
            c.execute("INSERT INTO products(sku,name,updated_at) VALUES(?,?,?)",(sku,name or sku,now))
        c.execute("INSERT INTO po_items(po_id,sku,product_name,qty_ordered,unit_cost) VALUES(?,?,?,?,?)",
                  (poid,sku,name,qty,cost))

@app.route("/api/po",methods=["POST"])
@req_role("admin","cs")
def api_po_create():
    d=request.get_json() or {}
    c=sdb()
    cur=c.execute("""INSERT INTO purchase_orders(supplier,notes,tracking,carrier,expected_at,status,created_by)
                     VALUES(?,?,?,?,?,?,?)""",
                  (d.get("supplier"),d.get("notes"),(d.get("tracking") or "").strip() or None,
                   (d.get("carrier") or "").strip() or None,(d.get("expected_at") or "").strip() or None,
                   d.get("status") or "open",session.get("name","")[:60]))
    poid=cur.lastrowid
    _po_insert_items(c,poid,d.get("items"))
    c.commit(); c.close()
    return jsonify({"ok":True,"po_id":poid})

@app.route("/api/po/<int:poid>",methods=["POST"])
@req_role("admin","cs")
def api_po_update(poid):
    """Update a PO header and (optionally) replace its unreceived line items."""
    d=request.get_json() or {}
    c=sdb()
    if not c.execute("SELECT 1 FROM purchase_orders WHERE id=?",(poid,)).fetchone():
        c.close(); return jsonify({"ok":False,"error":"Not found"}),404
    c.execute("""UPDATE purchase_orders SET supplier=?,notes=?,tracking=?,carrier=?,expected_at=?,status=COALESCE(?,status)
                 WHERE id=?""",
              (d.get("supplier"),d.get("notes"),(d.get("tracking") or "").strip() or None,
               (d.get("carrier") or "").strip() or None,(d.get("expected_at") or "").strip() or None,
               d.get("status"),poid))
    if "items" in d:
        # Replace lines only if nothing has been received yet (avoid clobbering receipts).
        got=c.execute("SELECT COALESCE(SUM(qty_received),0) n FROM po_items WHERE po_id=?",(poid,)).fetchone()["n"]
        if got==0:
            c.execute("DELETE FROM po_items WHERE po_id=?",(poid,))
            _po_insert_items(c,poid,d.get("items"))
    c.commit(); c.close()
    return jsonify({"ok":True})

@app.route("/api/po/<int:poid>/detail")
@req_role("admin","cs")
def api_po_detail(poid):
    c=sdb()
    r=c.execute("SELECT * FROM purchase_orders WHERE id=?",(poid,)).fetchone()
    if not r: c.close(); return jsonify({"ok":False,"error":"Not found"}),404
    po=dict(r)
    po["items"]=[dict(x) for x in c.execute("SELECT * FROM po_items WHERE po_id=? ORDER BY id",(poid,)).fetchall()]
    # attach current product image for the receive screen
    for it in po["items"]:
        pr=c.execute("SELECT image_url,on_hand FROM products WHERE sku=?",(it.get("sku"),)).fetchone()
        it["image_url"]=pr["image_url"] if pr else None
        it["on_hand"]=pr["on_hand"] if pr else None
    c.close()
    if session.get("role")!="admin":
        for it in po["items"]: it.pop("unit_cost",None)
    return jsonify({"ok":True,"po":po})

@app.route("/api/po/<int:poid>/item/<int:item_id>/receive",methods=["POST"])
@req_role("admin","cs")
def api_po_item_receive(poid,item_id):
    """Receive some/all of one line — updates stock + weighted-avg cost. iPad checkoff."""
    d=request.get_json() or {}
    c=sdb()
    it=c.execute("SELECT * FROM po_items WHERE id=? AND po_id=?",(item_id,poid)).fetchone()
    if not it: c.close(); return jsonify({"ok":False,"error":"Line not found"}),404
    remaining=(it["qty_ordered"] or 0)-(it["qty_received"] or 0)
    try: qty=int(float(d.get("qty"))) if d.get("qty") not in (None,"") else remaining
    except Exception: qty=remaining
    qty=max(0,min(qty,remaining))
    sku=(it["sku"] or "").strip()
    if qty<=0 or not sku:
        c.close(); return jsonify({"ok":False,"error":"Nothing to receive"})
    oh,ac=_receive_stock(c,sku,qty,it["unit_cost"] or 0,po_id=poid,note="PO receive",name=it["product_name"])
    c.execute("UPDATE po_items SET qty_received=qty_received+? WHERE id=?",(qty,item_id))
    # auto-complete PO when every line is fully received
    left=c.execute("SELECT COALESCE(SUM(qty_ordered-qty_received),0) n FROM po_items WHERE po_id=?",(poid,)).fetchone()["n"]
    if left<=0:
        c.execute("UPDATE purchase_orders SET status='received',received_at=? WHERE id=?",
                  (datetime.now().isoformat(timespec='seconds'),poid))
    else:
        c.execute("UPDATE purchase_orders SET status='receiving' WHERE id=? AND status IN ('open','ordered','in_transit')",(poid,))
    c.commit(); c.close()
    alog("stock.receive","PO#%d %s x%d"%(poid,sku,qty))
    return jsonify({"ok":True,"sku":sku,"on_hand":oh,"avg_cost":ac,"received_now":qty,"po_done":left<=0})

@app.route("/api/po")
@req_role("admin","cs")
def api_po_list():
    c=sdb()
    rows=c.execute("SELECT * FROM purchase_orders ORDER BY created_at DESC LIMIT 200").fetchall()
    out=[]
    for r in rows:
        d=dict(r); d["items"]=[dict(x) for x in c.execute("SELECT * FROM po_items WHERE po_id=?",(r["id"],)).fetchall()]
        out.append(d)
    c.close()
    return jsonify(out)

@app.route("/api/po/<int:poid>/receive",methods=["POST"])
@req_role("admin","cs")
def api_po_receive(poid):
    c=sdb()
    items=c.execute("SELECT * FROM po_items WHERE po_id=?",(poid,)).fetchall()
    received=0
    for it in items:
        sku=(it["sku"] or "").strip()
        qty=(it["qty_ordered"] or 0)-(it["qty_received"] or 0)
        if not sku or qty<=0: continue
        _receive_stock(c, sku, qty, it["unit_cost"] or 0, po_id=poid, note="PO receive", name=it["product_name"])
        c.execute("UPDATE po_items SET qty_received=qty_ordered WHERE id=?",(it["id"],))
        received+=qty
    c.execute("UPDATE purchase_orders SET status='received',received_at=? WHERE id=?",
              (datetime.now().isoformat(timespec='seconds'),poid))
    c.commit(); c.close()
    return jsonify({"ok":True,"received":received})

_PO_INVOICE_EXT={"pdf","jpg","jpeg","png","webp"}

@app.route("/api/po/<int:poid>/invoice",methods=["POST"])
@req_role("admin","cs")
def api_po_invoice_upload(poid):
    c=sdb()
    if not c.execute("SELECT 1 FROM purchase_orders WHERE id=?",(poid,)).fetchone():
        c.close(); return jsonify({"ok":False,"error":"PO not found"}),404
    c.close()
    f=request.files.get("file")
    if not f or not f.filename: return jsonify({"ok":False,"error":"Pick a file"})
    ext=f.filename.rsplit(".",1)[-1].lower() if "." in f.filename else ""
    if ext not in _PO_INVOICE_EXT: return jsonify({"ok":False,"error":"Use PDF or an image"})
    org=current_org(); data=f.read()
    key=f"{org}/invoices/po{poid}.{ext}"
    if r2:
        r2.put_object(Bucket=R2_BUCKET,Key=key,Body=data,ContentType=f.mimetype or "application/octet-stream")
    else:
        d=org_path(org,"invoices"); os.makedirs(d,exist_ok=True)
        with open(os.path.join(d,f"po{poid}.{ext}"),"wb") as fh: fh.write(data)
        key=f"po{poid}.{ext}"
    cc=sdb(); cc.execute("UPDATE purchase_orders SET invoice_key=?,invoice_name=? WHERE id=?",
                         (key,f.filename[:120],poid)); cc.commit(); cc.close()
    return jsonify({"ok":True,"invoice_name":f.filename})

@app.route("/api/po/<int:poid>/invoice-file")
@req_role("admin","cs")
def api_po_invoice_file(poid):
    c=sdb(); r=c.execute("SELECT invoice_key FROM purchase_orders WHERE id=?",(poid,)).fetchone(); c.close()
    key=r["invoice_key"] if r else None
    if not key: return ("",404)
    if r2 and "/" in key:
        try:
            url=r2.generate_presigned_url("get_object",Params={"Bucket":R2_BUCKET,"Key":key},ExpiresIn=R2_PRESIGN_TTL)
            return redirect(url)
        except Exception: return ("",404)
    p=org_path(current_org(),"invoices",key)
    if not os.path.exists(p): return ("",404)
    return send_file(p)

@app.route("/api/po/extract-invoice",methods=["POST"])
@req_role("admin","cs")
def api_po_extract_invoice():
    """Best-effort: read a supplier invoice IMAGE and suggest line items to review.
    Requires Anthropic to be configured; the user always reviews before saving."""
    if not anthropic_client:
        return jsonify({"ok":False,"error":"Auto-extract isn't set up — add the lines manually."})
    f=request.files.get("file")
    if not f or not f.filename: return jsonify({"ok":False,"error":"Pick an invoice file"})
    ext=f.filename.rsplit(".",1)[-1].lower() if "." in f.filename else ""
    if ext not in ("jpg","jpeg","png","webp","pdf"):
        return jsonify({"ok":False,"error":"Use an image (JPG/PNG) or a PDF invoice."})
    import base64
    b64=base64.standard_b64encode(f.read()).decode()
    prompt=("Extract the purchased line items from this supplier invoice. Return ONLY a JSON array; "
            "each element: {\"name\": product name, \"sku\": supplier SKU or code if shown else \"\", "
            "\"qty\": integer quantity, \"unit_cost\": number}. No prose, no code fences.")
    if ext=="pdf":
        block={"type":"document","source":{"type":"base64","media_type":"application/pdf","data":b64}}
    else:
        media="image/png" if ext=="png" else ("image/webp" if ext=="webp" else "image/jpeg")
        block={"type":"image","source":{"type":"base64","media_type":media,"data":b64}}
    try:
        msg=anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=2000,
            messages=[{"role":"user","content":[block,{"type":"text","text":prompt}]}])
        txt="".join(b.text for b in msg.content if getattr(b,"type","")=="text").strip()
        if txt.startswith("```"): txt=txt.strip("`").split("\n",1)[-1]
        import json as _j
        items=_j.loads(txt)
        clean=[]
        for it in (items if isinstance(items,list) else []):
            clean.append({"name":str(it.get("name",""))[:120],"sku":str(it.get("sku",""))[:40],
                          "qty":int(float(it.get("qty") or 0)),"unit_cost":float(it.get("unit_cost") or 0)})
        return jsonify({"ok":True,"items":clean})
    except Exception as e:
        print("invoice extract error:",e,flush=True)
        return jsonify({"ok":False,"error":"Couldn't read the invoice automatically — add the lines manually."})

@app.route("/api/po/<int:poid>/slip.pdf")
@req_role("admin","cs")
def api_po_slip(poid):
    """Warehouse receiving slip — quantities only, NO costs."""
    c=sdb()
    po=c.execute("SELECT * FROM purchase_orders WHERE id=?",(poid,)).fetchone()
    if not po: c.close(); return ("",404)
    items=c.execute("SELECT * FROM po_items WHERE po_id=? ORDER BY id",(poid,)).fetchall()
    c.close()
    from io import BytesIO
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm
    out=BytesIO(); cv=canvas.Canvas(out,pagesize=letter); W,H=letter
    y=H-24*mm
    cv.setFont("Helvetica-Bold",18); cv.drawString(20*mm,y,f"Receiving slip — PO #{poid}")
    y-=8*mm; cv.setFont("Helvetica",11)
    cv.drawString(20*mm,y,f"Supplier: {po['supplier'] or '-'}    Tracking: {po['tracking'] or '-'}")
    y-=6*mm; cv.drawString(20*mm,y,f"Printed: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    y-=12*mm
    cv.setFont("Helvetica-Bold",10)
    cv.drawString(20*mm,y,"✓"); cv.drawString(30*mm,y,"SKU"); cv.drawString(60*mm,y,"Product")
    cv.drawString(150*mm,y,"Qty"); cv.line(20*mm,y-2*mm,195*mm,y-2*mm); y-=8*mm
    cv.setFont("Helvetica",10)
    for it in items:
        if y<24*mm: cv.showPage(); y=H-24*mm; cv.setFont("Helvetica",10)
        cv.rect(20*mm,y-1*mm,4*mm,4*mm)  # checkbox
        cv.drawString(30*mm,y,str(it["sku"] or "-"))
        cv.drawString(60*mm,y,str(it["product_name"] or "")[:52])
        cv.drawRightString(165*mm,y,str(it["qty_ordered"] or 0))
        y-=8*mm
    cv.showPage(); cv.save(); out.seek(0)
    return send_file(out,mimetype="application/pdf",download_name=f"PO{poid}_slip.pdf")

@app.route("/api/preshow/map",methods=["POST"])
@req_role("admin","cs","worker","picker")
def api_preshow_map():
    """Bind a generic sticker (sticker#, Part) for a show to a real catalog product.
    Resolve the product by barcode or SKU. Sticker numbers reuse each show, so the
    binding is scoped to import_label."""
    d=request.get_json() or {}
    show=(d.get("show") or "").strip()
    sticker=(d.get("sticker") or "").strip()
    try: part=int(d.get("part") or 0)
    except Exception: part=0
    code=(d.get("code") or "").strip()           # scanned barcode / SKU
    product_sku=(d.get("product_sku") or "").strip()  # explicit pick from catalog
    if not show or not sticker:
        return jsonify({"ok":False,"error":"show and sticker required"})
    c=sdb()
    prod=None
    if product_sku:
        prod=c.execute("SELECT * FROM products WHERE sku=?",(product_sku,)).fetchone()
    elif code:
        prod=c.execute("SELECT * FROM products WHERE barcode=? OR sku=?",(code,code)).fetchone()
    if not prod:
        c.close()
        return jsonify({"ok":False,"error":"Product not found in catalog","not_found":True,
                        "code":code or product_sku})
    # Units sold under this sticker this show (one product per sticker per show).
    items=c.execute("""SELECT i.product_name, i.quantity FROM shipment_items i
                       JOIN shipments s ON s.shipment_id=i.shipment_id
                       WHERE s.import_label=? AND i.sku=? AND COALESCE(i.cancelled,0)=0""",(show,sticker)).fetchall()
    sold_qty=sum((it["quantity"] or 1) for it in items if _part_num(it["product_name"] or "")==part)
    # Restore any prior deduction (re-bind / corrected scan), then deduct from the real product.
    ex=c.execute("SELECT product_sku,COALESCE(depleted_qty,0) dq FROM show_product_map WHERE import_label=? AND sticker_sku=? AND part=?",(show,sticker,part)).fetchone()
    _now=datetime.now().isoformat(timespec='seconds'); _who=session.get("name","")[:60]
    if ex and ex["product_sku"] and ex["dq"]:
        c.execute("UPDATE products SET on_hand=on_hand+? WHERE sku=?",(ex["dq"],ex["product_sku"]))
        c.execute("INSERT INTO stock_moves(sku,qty,note,moved_at,moved_by) VALUES(?,?,?,?,?)",
                  (ex["product_sku"],ex["dq"],"sale reversal (re-map "+show+")",_now,_who))
    c.execute("UPDATE products SET on_hand=on_hand-? WHERE sku=?",(sold_qty,prod["sku"]))
    if sold_qty:
        _ac=c.execute("SELECT avg_cost FROM products WHERE sku=?",(prod["sku"],)).fetchone()
        c.execute("INSERT INTO stock_moves(sku,qty,unit_cost,note,moved_at,moved_by) VALUES(?,?,?,?,?,?)",
                  (prod["sku"],-sold_qty,(_ac["avg_cost"] if _ac else 0) or 0,"sale ("+show+")",_now,_who))
    c.execute("""INSERT INTO show_product_map(import_label,sticker_sku,part,product_sku,depleted_qty,mapped_at,mapped_by)
                 VALUES(?,?,?,?,?,?,?)
                 ON CONFLICT(import_label,sticker_sku,part) DO UPDATE SET
                    product_sku=excluded.product_sku,depleted_qty=excluded.depleted_qty,
                    mapped_at=excluded.mapped_at,mapped_by=excluded.mapped_by""",
              (show,sticker,part,prod["sku"],sold_qty,datetime.now().isoformat(timespec='seconds'),
               session.get("name","")[:60]))
    c.commit()
    newoh=c.execute("SELECT on_hand FROM products WHERE sku=?",(prod["sku"],)).fetchone()
    c.close()
    return jsonify({"ok":True,"sticker":sticker,"part":part,"sold_qty":sold_qty,
                    "product":{"sku":prod["sku"],"name":prod["name"],"image_url":prod["image_url"],
                               "on_hand":newoh["on_hand"] if newoh else None}})

@app.route("/api/preshow/map")
@req_role("admin","cs","worker","picker")
def api_preshow_map_list():
    """Existing bindings for a show, plus simple progress counts."""
    show=(request.args.get("show") or "").strip()
    if not show: return jsonify({"ok":False,"error":"show required"})
    c=sdb()
    rows=c.execute("""SELECT m.sticker_sku,m.part,m.product_sku,m.mapped_by,m.mapped_at,
                             p.name pname,p.image_url,p.avg_cost,p.on_hand
                      FROM show_product_map m LEFT JOIN products p ON p.sku=m.product_sku
                      WHERE m.import_label=? ORDER BY m.part, CAST(m.sticker_sku AS INTEGER)""",(show,)).fetchall()
    c.close()
    role=session.get("role","")
    out=[]
    for r in rows:
        d={"sticker":r["sticker_sku"],"part":r["part"],"product_sku":r["product_sku"],
           "name":r["pname"],"image_url":r["image_url"],"on_hand":r["on_hand"],
           "mapped_by":r["mapped_by"],"mapped_at":r["mapped_at"]}
        if role=="admin": d["avg_cost"]=r["avg_cost"]   # cost only for admin
        out.append(d)
    return jsonify({"ok":True,"show":show,"count":len(out),"maps":out})

@app.route("/api/preshow/map",methods=["DELETE"])
@req_role("admin","cs","worker","picker")
def api_preshow_unmap():
    d=request.get_json() or {}
    show=(d.get("show") or "").strip(); sticker=(d.get("sticker") or "").strip()
    try: part=int(d.get("part") or 0)
    except Exception: part=0
    c=sdb()
    ex=c.execute("SELECT product_sku,COALESCE(depleted_qty,0) dq FROM show_product_map WHERE import_label=? AND sticker_sku=? AND part=?",(show,sticker,part)).fetchone()
    if ex and ex["product_sku"]:
        c.execute("UPDATE products SET on_hand=on_hand+? WHERE sku=?",(ex["dq"],ex["product_sku"]))
    c.execute("DELETE FROM show_product_map WHERE import_label=? AND sticker_sku=? AND part=?",(show,sticker,part))
    c.commit(); c.close()
    return jsonify({"ok":True})

@app.route("/api/profit")
@req_role("admin")
def api_profit():
    """Per real-product P&L. Sticker numbers are reused each show, so revenue is
    attributed to the real catalog product via the per-show binding (show_product_map).
    Revenue from import; COGS = qty × current avg cost. Admin only."""
    show=(request.args.get("show") or "").strip()
    c=sdb()
    where="WHERE COALESCE(i.cancelled,0)=0"; params=[]
    if show:
        where+=" AND s.import_label=?"; params.append(show)
    rows=c.execute("""SELECT s.import_label, i.sku, i.product_name, i.quantity,
                             COALESCE(i.revenue,0) revenue
                      FROM shipment_items i
                      JOIN shipments s ON s.shipment_id=i.shipment_id """+where,params).fetchall()
    # all bindings (optionally scoped to one show)
    if show:
        mrows=c.execute("SELECT import_label,sticker_sku,part,product_sku FROM show_product_map WHERE import_label=?",(show,)).fetchall()
    else:
        mrows=c.execute("SELECT import_label,sticker_sku,part,product_sku FROM show_product_map").fetchall()
    mp={(m["import_label"],(m["sticker_sku"] or "").strip(),m["part"]):m["product_sku"] for m in mrows}
    prods={p["sku"]:p for p in c.execute("SELECT sku,name,avg_cost FROM products").fetchall()}
    c.close()
    agg={}  # key -> line
    total_rev=0; total_cogs=0; unmapped=0
    for r in rows:
        sku=(r["sku"] or "").strip(); part=_part_num(r["product_name"] or "")
        qty=r["quantity"] or 0; rev=r["revenue"] or 0
        psku=mp.get((r["import_label"],sku,part))
        if psku and psku in prods:
            p=prods[psku]; key=psku; name=p["name"] or psku; ac=p["avg_cost"]; mapped=True
        else:
            key="?"+sku+"|"+str(part); name=(r["product_name"] or sku); ac=None; mapped=False
            unmapped+=1
        g=agg.setdefault(key,{"product_sku":psku if mapped else None,"name":name,"qty":0,
                              "revenue":0,"avg_cost":ac,"mapped":mapped,"stickers":set()})
        g["qty"]+=qty; g["revenue"]+=rev; g["stickers"].add(sku)
        total_rev+=rev
    lines=[]
    for g in agg.values():
        ac=g["avg_cost"]; cogs=(g["qty"]*ac) if ac is not None else 0
        total_cogs+=cogs
        lines.append({"product_sku":g["product_sku"],"name":g["name"],
                      "stickers":sorted(g["stickers"]),"qty":g["qty"],
                      "revenue":round(g["revenue"],2),"avg_cost":ac,
                      "cogs":round(cogs,2),"profit":round(g["revenue"]-cogs,2),
                      "mapped":g["mapped"]})
    lines.sort(key=lambda x:x["revenue"],reverse=True)
    return jsonify({"ok":True,"show":show or "ALL","revenue":round(total_rev,2),
                    "cogs":round(total_cogs,2),"profit":round(total_rev-total_cogs,2),
                    "margin":round(100*(total_rev-total_cogs)/total_rev,1) if total_rev else 0,
                    "unmapped_lines":unmapped,"lines":lines})

@app.route("/admin/preshow")
@req_role("admin","cs","worker","picker")
def preshow_page():
    return PRESHOW_HTML.replace("__NAME__",esc(session.get("name",""))).replace("__NAVBAR__",_navbar("preshow")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

@app.route("/admin/inventory")
@req_role("admin")
def inventory_page():
    return INVENTORY_HTML.replace("__NAME__",esc(session.get("name",""))).replace("__ROLE__",esc(session.get("role",""))).replace("__NAVBAR__",_navbar("inventory")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

@app.route("/admin/purchasing")
@req_role("admin","cs")
def purchasing_page():
    return PURCHASING_HTML.replace("__NAME__",esc(session.get("name",""))).replace("__ROLE__",esc(session.get("role",""))).replace("__NAVBAR__",_navbar("purchasing")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

@app.route("/admin/stocktake")
@req_role("admin","cs")
def stocktake_page():
    return STOCKTAKE_HTML.replace("__NAME__",esc(session.get("name",""))).replace("__NAVBAR__",_navbar("purchasing")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

@app.route("/admin/profit")
@req_role("admin")
def profit_page():
    return PROFIT_HTML.replace("__NAME__",esc(session.get("name",""))).replace("__NAVBAR__",_navbar("profit")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

# ── HOST ANALYTICS — per-show seller performance + commissions (admin only) ──
def _host_from_label(label):
    """Pull the host's name out of a show label like '... w/ Tali Part 1'."""
    if not label: return ""
    m=re.search(r'w/\s*(.*)$', label, re.I) or re.search(r'\bwith\s+(.*)$', label, re.I)
    if not m: return ""
    rest=re.split(r'\bPart\s*\d+', m.group(1), flags=re.I)[0]
    rest=re.split(r'[|/]', rest)[0]
    return " ".join(rest.split()[:2]).strip()

def _host_overrides():
    raw=_get_setting("host_overrides")
    try: return json.loads(raw) if raw else {}
    except Exception: return {}

def _get_commission_cfg():
    raw=_get_setting("commission_config")
    if raw:
        try: return json.loads(raw)
        except Exception: pass
    return {"mode":"flat","flat_pct":10.0,"pct":10.0,"tiers":[{"min":0,"pct":8},{"min":2000,"pct":12}]}

def _compute_commission(rev, cfg):
    rev=rev or 0
    mode=(cfg or {}).get("mode","flat")
    if mode=="tiered":
        pct=0
        for t in sorted(cfg.get("tiers") or [], key=lambda x:x.get("min",0)):
            if rev>=(t.get("min") or 0): pct=t.get("pct") or 0
        return round(rev*pct/100.0,2)
    if mode=="base_pct":   # hourly base needs live hours (not captured yet) → % only
        return round(rev*(cfg.get("pct") or 0)/100.0,2)
    return round(rev*(cfg.get("flat_pct") or 0)/100.0,2)

@app.route("/api/host-analytics")
@req_role("admin")
def api_host_analytics():
    c=sdb()
    rows=c.execute("""SELECT s.import_label lbl, s.show_date sd, i.shipment_id sid,
                             i.quantity qty, COALESCE(i.revenue,0) rev, COALESCE(i.cancelled,0) canc, i.sku
                      FROM shipment_items i JOIN shipments s ON s.shipment_id=i.shipment_id
                      WHERE s.import_label IS NOT NULL AND s.import_label!=''""").fetchall()
    # Shipping collected per show (buyer-paid, pass-through) — excludes cancelled.
    shipmap={r["lbl"]:(r["sf"] or 0) for r in c.execute("""SELECT import_label lbl, COALESCE(SUM(shipping_fee),0) sf
                      FROM shipments WHERE import_label IS NOT NULL AND import_label!=''
                        AND COALESCE(status,'')!='cancelled' GROUP BY import_label""").fetchall()}
    c.close()
    ov=_host_overrides(); cfg=_get_commission_cfg()
    shows={}
    for r in rows:
        g=shows.setdefault(r["lbl"],{"label":r["lbl"],"show_date":r["sd"],"revenue":0.0,"units":0,
                                     "orders":set(),"canc_units":0,"skus":set()})
        if not g["show_date"] and r["sd"]: g["show_date"]=r["sd"]
        if r["canc"]:
            g["canc_units"]+=r["qty"] or 0
        else:
            g["revenue"]+=r["rev"] or 0; g["units"]+=r["qty"] or 0; g["orders"].add(r["sid"])
            if r["sku"]: g["skus"].add(r["sku"])
    show_list=[]
    for g in shows.values():
        host=ov.get(g["label"]) or _host_from_label(g["label"]) or "Unknown"
        orders=len(g["orders"]); rev=round(g["revenue"],2); tot=g["units"]+g["canc_units"]
        ship=round(shipmap.get(g["label"],0),2)
        show_list.append({"label":g["label"],"host":host,"show_date":g["show_date"],
                          "revenue":rev,"shipping":ship,"gross":round(rev+ship,2),
                          "units":g["units"],"orders":orders,
                          "aov":round(rev/orders,2) if orders else 0,"products":len(g["skus"]),
                          "cancel_rate":round(100.0*g["canc_units"]/tot,1) if tot else 0,
                          "commission":_compute_commission(rev,cfg),
                          "auto_host":_host_from_label(g["label"]) or ""})
    show_list.sort(key=lambda x:((x["show_date"] or ""), x["label"]))
    hosts={}
    for s in show_list:
        h=hosts.setdefault(s["host"],{"host":s["host"],"shows":0,"revenue":0.0,"shipping":0.0,"gross":0.0,"units":0,"orders":0,"commission":0.0})
        h["shows"]+=1; h["revenue"]+=s["revenue"]; h["shipping"]+=s["shipping"]; h["gross"]+=s["gross"]
        h["units"]+=s["units"]; h["orders"]+=s["orders"]; h["commission"]+=s["commission"]
    host_list=[]
    for h in hosts.values():
        h["revenue"]=round(h["revenue"],2); h["shipping"]=round(h["shipping"],2); h["gross"]=round(h["gross"],2); h["commission"]=round(h["commission"],2)
        h["avg_per_show"]=round(h["revenue"]/h["shows"],2) if h["shows"] else 0
        host_list.append(h)
    host_list.sort(key=lambda x:x["revenue"],reverse=True)
    return jsonify({"ok":True,"shows":show_list,"hosts":host_list,"config":cfg})

@app.route("/api/commission-config",methods=["GET","POST"])
@req_role("admin")
def api_commission_config():
    if request.method=="POST":
        d=request.get_json() or {}
        cfg={"mode":d.get("mode","flat"),
             "flat_pct":float(d.get("flat_pct") or 0),
             "pct":float(d.get("pct") or 0),
             "tiers":[{"min":float(t.get("min") or 0),"pct":float(t.get("pct") or 0)}
                      for t in (d.get("tiers") or [])][:8]}
        _set_setting("commission_config", json.dumps(cfg))
        return jsonify({"ok":True})
    return jsonify({"ok":True,"config":_get_commission_cfg()})

@app.route("/api/host-override",methods=["POST"])
@req_role("admin")
def api_host_override():
    d=request.get_json() or {}
    lbl=(d.get("label") or "").strip(); host=(d.get("host") or "").strip()
    if not lbl: return jsonify({"ok":False,"error":"label required"})
    ov=_host_overrides()
    if host: ov[lbl]=host
    else: ov.pop(lbl,None)
    _set_setting("host_overrides", json.dumps(ov))
    return jsonify({"ok":True})

@app.route("/admin/hosts")
@req_role("admin")
def hosts_page():
    return HOSTS_HTML.replace("__NAME__",esc(session.get("name",""))).replace("__NAVBAR__",_navbar("hosts")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

# ── PACKER ANALYTICS — pack speed per worker from the recording log ──
@app.route("/api/packer-analytics")
@req_role("admin","cs")
def api_packer_analytics():
    worker=(request.args.get("worker") or "").strip()
    station=(request.args.get("station") or "").strip()
    frm=(request.args.get("from") or "").strip(); to=(request.args.get("to") or "").strip()
    c=sdb()
    tmap={}
    for r in c.execute("SELECT tracking_code,shipment_id,total_items FROM shipments").fetchall():
        ti=r["total_items"] or 0
        if r["tracking_code"]: tmap[r["tracking_code"]]=ti
        if r["shipment_id"]: tmap.setdefault(r["shipment_id"],ti)
    c.close()
    rows=[]; all_workers=set(); all_stations=set()
    if os.path.exists(log_file()):
        with open(log_file()) as f:
            for row in csv.DictReader(f):
                d=row.get("date","") or ""
                wk=(row.get("worker","") or "Unknown"); stn=row.get("station","") or ""
                all_workers.add(wk);
                if stn: all_stations.add(stn)
                if frm and d<frm: continue
                if to and d>to: continue
                if worker and wk!=worker: continue
                if station and stn!=station: continue
                try: dur=float(row.get("duration_seconds","0") or 0)
                except Exception: dur=0
                if dur<=0 or dur>3600: continue   # ignore bogus durations
                rows.append({"worker":wk,"date":d,"station":stn,"dur":dur,
                             "items":tmap.get(row.get("tracking_number","") or "",0)})
    def agg(items):
        pk=len(items); sec=sum(x["dur"] for x in items); it=sum(x["items"] for x in items)
        return {"packages":pk,"items":it,"avg_sec_pkg":round(sec/pk,1) if pk else 0,
                "avg_sec_item":round(sec/it,1) if it else 0,
                "pkgs_per_hr":round(3600.0/(sec/pk),1) if pk and sec else 0,
                "active_hours":round(sec/3600,2)}
    W={}
    for r in rows: W.setdefault(r["worker"],[]).append(r)
    workers=[dict({"worker":w},**agg(v)) for w,v in W.items()]
    workers.sort(key=lambda x:x["packages"],reverse=True)
    D={}
    for r in rows: D.setdefault(r["date"],[]).append(r)
    days=[dict({"date":d},**agg(v)) for d,v in sorted(D.items())]
    return jsonify({"ok":True,"overall":agg(rows),"workers":workers,"days":days,
                    "worker_list":sorted(all_workers),"station_list":sorted(all_stations)})

@app.route("/admin/packer-analytics")
@req_role("admin","cs")
def packer_analytics_page():
    return PACKER_HTML.replace("__NAME__",esc(session.get("name",""))).replace("__NAVBAR__",_navbar("packer")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

# Operations hub: (tab_key, tab_label, [ (icon, title, sublabel, url, admin_only), ... ])
OPS_GROUPS = [
    ("shows", "🎬 Shows", [
        ("🎬", "Shows", "Last 5 days · live rollup", "/admin/shows", False),
        ("📥", "Import Shipments", "Upload To-Ship / cancel CSV", "/admin/shipments", False),
        ("🔗", "Match Products", "Bind stickers to real SKUs", "/admin/preshow", False),
        ("🧾", "SKU Reconciliation", "Verify packed vs sold", "/admin/sku-lookup", False),
    ]),
    ("warehouse", "🏭 Warehouse", [
        ("📦", "Inventory", "Catalog, stock, costs", "/admin/inventory", True),
        ("📥", "Purchasing", "Supplier orders & receiving", "/admin/purchasing", False),
        ("🔢", "Stock Take", "Count & reconcile stock", "/admin/stocktake", False),
        ("🧹", "Table Cleanup", "Clear tables between shows", "/admin/cleanup", False),
        ("🚧", "Picking Issues", "Flagged / unresolved picks", "/admin/issues", False),
        ("🎥", "Search Recordings", "Find a packing video", "/dashboard", False),
        ("🔎", "Customer Lookup", "Orders & history by buyer", "/customers", False),
    ]),
    ("shipping", "🚚 Shipping", [
        ("🚚", "Shipping Status", "USPS tracking dashboard", "/shipping-status", False),
        ("📦", "Inbound Labels", "Supplier inbound labels", "/admin/inbound", False),
    ]),
    ("giveaway", "🎁 Giveaways", [
        ("🎁", "Giveaways", "Winners, addresses & label printing", "/giveaway", False),
    ]),
    ("insights", "📊 Insights & Money", [
        ("⏱️", "Packer Analytics", "Speed & volume per packer", "/admin/packer-analytics", False),
        ("🧺", "Picker Analytics", "Speed & volume per picker", "/admin/picker-analytics", False),
        ("🗺️", "Geography", "Where orders ship, by state", "/admin/geo-analytics", False),
        ("🔁", "Repeat Customers", "Returning buyers & loyalty", "/admin/repeat-customers", False),
        ("🎤", "Host Analytics", "Sales & commission by host", "/admin/hosts", True),
        ("📈", "Analytics", "Overall performance", "/analytics", True),
        ("💰", "Profit", "Margins & cost of goods", "/admin/profit", True),
    ]),
]

def _render_operations(role):
    """Build the tab bar + panels for the Operations hub, hiding admin-only
    cards for non-admin (CS) users and dropping any group left empty."""
    is_admin = (role == "admin")
    tabs_html, panels_html, first = "", "", True
    for key, label, cards in OPS_GROUPS:
        visible = [c for c in cards if is_admin or not c[4]]
        if not visible:
            continue
        tabs_html += ('<button class="tab%s" data-tab="%s">%s</button>'
                      % (" active" if first else "", esc(key), esc(label)))
        cards_html = ""
        for icon, title, sub, url, _adm in visible:
            cards_html += ('<a class="opcard" href="%s"><span class="ic">%s</span>'
                           '<span class="t">%s</span><span class="s">%s</span></a>'
                           % (esc(url), esc(icon), esc(title), esc(sub)))
        panels_html += ('<div class="tab-panel%s" data-panel="%s"><div class="grid">%s</div></div>'
                        % (" active" if first else "", esc(key), cards_html))
        first = False
    return tabs_html, panels_html

@app.route("/operations")
@req_role("admin", "cs")
def operations_page():
    tabs, panels = _render_operations(session.get("role", ""))
    return (OPERATIONS_HTML
        .replace("__NAME__", esc(session.get("name", "")))
        .replace("__NAVBAR__", _navbar("operations"))
        .replace("__NAVBAR_CSS__", _NAVBAR_CSS)
        .replace("__OPS_TABS__", tabs)
        .replace("__OPS_PANELS__", panels))

@app.route("/admin/settings")
@req_role("admin")
def settings_page():
    return SETTINGS_HTML.replace("__NAME__",esc(session.get("name",""))).replace("__NAVBAR__",_navbar("settings")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

# ── GEOGRAPHY ANALYTICS — where orders ship, by state (audience map) ──
_US_STATES={"AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
 "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY",
 "NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC","PR"}
_ZIP_RANGES=[(5,5,"NY"),(10,27,"MA"),(28,29,"RI"),(30,38,"NH"),(39,49,"ME"),(50,59,"VT"),
 (60,69,"CT"),(70,89,"NJ"),(100,149,"NY"),(150,196,"PA"),(197,199,"DE"),(200,205,"DC"),
 (206,219,"MD"),(220,246,"VA"),(247,268,"WV"),(270,289,"NC"),(290,299,"SC"),(300,319,"GA"),
 (320,349,"FL"),(350,369,"AL"),(370,385,"TN"),(386,397,"MS"),(398,399,"GA"),(400,427,"KY"),
 (430,459,"OH"),(460,479,"IN"),(480,499,"MI"),(500,528,"IA"),(530,549,"WI"),(550,567,"MN"),
 (570,577,"SD"),(580,588,"ND"),(590,599,"MT"),(600,629,"IL"),(630,658,"MO"),(660,679,"KS"),
 (680,693,"NE"),(700,714,"LA"),(716,729,"AR"),(730,749,"OK"),(750,799,"TX"),(800,816,"CO"),
 (820,831,"WY"),(832,838,"ID"),(840,847,"UT"),(850,865,"AZ"),(870,884,"NM"),(889,898,"NV"),
 (900,961,"CA"),(967,968,"HI"),(970,979,"OR"),(980,994,"WA"),(995,999,"AK"),(6,9,"PR")]
def _state_from_zip(z):
    z=(z or "").strip()
    if len(z)<3 or not z[:3].isdigit(): return ""
    p=int(z[:3])
    for lo,hi,st in _ZIP_RANGES:
        if lo<=p<=hi: return st
    return ""
def _state_from_addr(a):
    m=re.search(r'\b([A-Za-z]{2})\s+\d{5}', a or "")
    if m and m.group(1).upper() in _US_STATES: return m.group(1).upper()
    return ""
def _resolve_state(postal, addr, bstate):
    b=(bstate or "").strip().upper()
    if len(b)==2 and b in _US_STATES: return b
    return _state_from_zip(postal) or _state_from_addr(addr) or ""

@app.route("/api/geo-analytics")
@req_role("admin","cs")
def api_geo_analytics():
    frm=(request.args.get("from") or "").strip(); to=(request.args.get("to") or "").strip()
    show=(request.args.get("show") or "").strip()
    c=sdb()
    where="WHERE COALESCE(s.status,'')!='cancelled'"; params=[]
    if show: where+=" AND s.import_label=?"; params.append(show)
    if frm: where+=" AND s.show_date>=?"; params.append(frm)
    if to: where+=" AND s.show_date<=?"; params.append(to)
    ships=c.execute("SELECT shipment_id,postal_code,address_full,show_date FROM shipments s "+where,params).fetchall()
    itmap={}
    for r in c.execute("""SELECT shipment_id, COALESCE(SUM(CASE WHEN COALESCE(cancelled,0)=0 THEN quantity ELSE 0 END),0) units,
                                 COALESCE(SUM(CASE WHEN COALESCE(cancelled,0)=0 THEN revenue ELSE 0 END),0) rev,
                                 MAX(buyer_state) bs, MAX(buyer_city) bc
                          FROM shipment_items GROUP BY shipment_id""").fetchall():
        itmap[r["shipment_id"]]={"units":r["units"] or 0,"rev":r["rev"] or 0,"bs":r["bs"],"bc":r["bc"]}
    c.close()
    states={}; cities={}; total_orders=0; unresolved=0
    for s in ships:
        it=itmap.get(s["shipment_id"],{})
        st=_resolve_state(s["postal_code"], s["address_full"], it.get("bs"))
        total_orders+=1
        if not st: unresolved+=1; continue
        g=states.setdefault(st,{"state":st,"orders":0,"units":0,"revenue":0.0})
        g["orders"]+=1; g["units"]+=it.get("units",0); g["revenue"]+=it.get("rev",0)
        city=(it.get("bc") or "").strip()
        if city:
            key=city+", "+st; cities[key]=cities.get(key,0)+1
    slist=sorted(states.values(),key=lambda x:x["orders"],reverse=True)
    resolved=total_orders-unresolved
    for g in slist:
        g["revenue"]=round(g["revenue"],2)
        g["pct"]=round(100.0*g["orders"]/resolved,1) if resolved else 0
    clist=sorted([{"k":k,"v":v} for k,v in cities.items()],key=lambda x:-x["v"])[:15]
    return jsonify({"ok":True,"states":slist,"cities":clist,"total_orders":total_orders,
                    "resolved":resolved,"unresolved":unresolved,"states_reached":len(slist),
                    "top_state":slist[0]["state"] if slist else None})

@app.route("/admin/geo-analytics")
@req_role("admin","cs")
def geo_analytics_page():
    return GEO_HTML.replace("__NAME__",esc(session.get("name",""))).replace("__NAVBAR__",_navbar("geo")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

# ── PICKER ANALYTICS — pick speed/volume per picker (timing from completion gaps) ──
@app.route("/api/picker-analytics")
@req_role("admin","cs")
def api_picker_analytics():
    picker=(request.args.get("picker") or "").strip()
    show=(request.args.get("show") or "").strip()
    frm=(request.args.get("from") or "").strip(); to=(request.args.get("to") or "").strip()
    c=sdb()
    where="WHERE picked_by IS NOT NULL AND picked_by!='' AND picked_at IS NOT NULL"; params=[]
    if show: where+=" AND import_label=?"; params.append(show)
    if frm: where+=" AND substr(picked_at,1,10)>=?"; params.append(frm)
    if to: where+=" AND substr(picked_at,1,10)<=?"; params.append(to)
    ships=c.execute("SELECT shipment_id,picked_by,picked_at FROM shipments "+where+" ORDER BY picked_by, picked_at",params).fetchall()
    itmap={}
    for r in c.execute("SELECT shipment_id, COALESCE(SUM(CASE WHEN COALESCE(cancelled,0)=0 THEN quantity ELSE 0 END),0) u FROM shipment_items GROUP BY shipment_id").fetchall():
        itmap[r["shipment_id"]]=r["u"] or 0
    c.close()
    CAP=1200  # gaps over 20 min are treated as breaks (excluded from active time)
    all_pickers=set()
    perp={}; perday={}
    prev={}  # picker -> last picked_at datetime
    for s in ships:
        pk=s["picked_by"]; all_pickers.add(pk)
        if picker and pk!=picker: continue
        dt=_parse_sale_dt(s["picked_at"])
        items=itmap.get(s["shipment_id"],0)
        g=perp.setdefault(pk,{"picker":pk,"orders":0,"items":0,"active_sec":0.0,"timed":0})
        g["orders"]+=1; g["items"]+=items
        day=(s["picked_at"] or "")[:10]
        d=perday.setdefault(day,{"date":day,"orders":0,"items":0})
        d["orders"]+=1; d["items"]+=items
        if dt and pk in prev and prev[pk] is not None:
            gap=(dt-prev[pk]).total_seconds()
            if 0<gap<=CAP: g["active_sec"]+=gap; g["timed"]+=1
        prev[pk]=dt
    def fin(g):
        avg=(g["active_sec"]/g["timed"]) if g["timed"] else 0
        return {"picker":g["picker"],"orders":g["orders"],"items":g["items"],
                "avg_sec_order":round(avg,1),"orders_per_hr":round(3600.0/avg,1) if avg else 0,
                "active_hours":round(g["active_sec"]/3600,2)}
    pickers=sorted([fin(g) for g in perp.values()],key=lambda x:x["orders"],reverse=True)
    tot={"orders":sum(g["orders"] for g in perp.values()),"items":sum(g["items"] for g in perp.values()),
         "active_sec":sum(g["active_sec"] for g in perp.values()),"timed":sum(g["timed"] for g in perp.values())}
    ov=fin({"picker":"","orders":tot["orders"],"items":tot["items"],"active_sec":tot["active_sec"],"timed":tot["timed"]})
    days=[perday[k] for k in sorted(perday)]
    return jsonify({"ok":True,"overall":ov,"pickers":pickers,"days":days,"picker_list":sorted(all_pickers)})

@app.route("/admin/picker-analytics")
@req_role("admin","cs")
def picker_analytics_page():
    return PICKER_HTML.replace("__NAME__",esc(session.get("name",""))).replace("__NAVBAR__",_navbar("pickeran")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

# ── REPEAT CUSTOMERS — buyers with more than one order ──
@app.route("/api/repeat-customers")
@req_role("admin","cs")
def api_repeat_customers():
    try: min_orders=int(request.args.get("min_orders") or 2)
    except Exception: min_orders=2
    sort=(request.args.get("sort") or "orders").strip()
    frm=(request.args.get("from") or "").strip(); to=(request.args.get("to") or "").strip()
    c=sdb()
    where="WHERE buyer_username IS NOT NULL AND buyer_username!='' AND COALESCE(status,'')!='cancelled'"; params=[]
    if frm: where+=" AND show_date>=?"; params.append(frm)
    if to: where+=" AND show_date<=?"; params.append(to)
    rows=c.execute("""SELECT s.buyer_username u, MAX(s.buyer_name) nm, COUNT(DISTINCT s.shipment_id) orders,
                             COUNT(DISTINCT s.import_label) shows, MIN(s.show_date) first, MAX(s.show_date) last
                      FROM shipments s """+where+" GROUP BY s.buyer_username",params).fetchall()
    # revenue per buyer (non-cancelled items)
    rev=c.execute("""SELECT s.buyer_username u, COALESCE(SUM(CASE WHEN COALESCE(i.cancelled,0)=0 THEN i.revenue ELSE 0 END),0) r
                     FROM shipments s JOIN shipment_items i ON i.shipment_id=s.shipment_id
                     WHERE s.buyer_username IS NOT NULL AND s.buyer_username!='' GROUP BY s.buyer_username""").fetchall()
    c.close()
    revmap={x["u"]:x["r"] or 0 for x in rev}
    total_customers=len(rows)
    cust=[]
    for r in rows:
        cust.append({"username":r["u"],"name":r["nm"],"orders":r["orders"],"shows":r["shows"],
                     "first":r["first"],"last":r["last"],"revenue":round(revmap.get(r["u"],0),2)})
    repeat=[x for x in cust if x["orders"]>=2]
    keyf=(lambda x:(-x["revenue"],-x["orders"])) if sort=="revenue" else (lambda x:(-x["orders"],-x["revenue"]))
    filtered=sorted([x for x in cust if x["orders"]>=min_orders],key=keyf)
    return jsonify({"ok":True,"total_customers":total_customers,"repeat_customers":len(repeat),
        "repeat_rate":round(100.0*len(repeat)/total_customers,1) if total_customers else 0,
        "repeat_revenue":round(sum(x["revenue"] for x in repeat),2),
        "min_orders":min_orders,"customers":filtered[:500]})

@app.route("/admin/repeat-customers")
@req_role("admin","cs")
def repeat_customers_page():
    return REPEAT_HTML.replace("__NAME__",esc(session.get("name",""))).replace("__NAVBAR__",_navbar("repeat")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

@app.route("/api/org/branding")
@req_role("admin")
def api_org_branding_get():
    """Current tenant's branding, for the Settings → Branding panel."""
    return jsonify(org_get(session.get("org", DEFAULT_ORG)))

@app.route("/api/org/branding", methods=["POST"])
@req_role("admin")
def api_org_branding_set():
    """Update this tenant's white-label branding (company name, wordmark, colour, logo)."""
    d = request.get_json(silent=True) or {}
    org_id = session.get("org", DEFAULT_ORG)
    company = _clean_name(d.get("company_name"), 80)
    mark = _clean_name(d.get("brand_mark"), 24)
    sub = _clean_name(d.get("brand_sub"), 40)
    color = (d.get("brand_color") or "").strip()
    logo = (d.get("logo_url") or "").strip()
    if not re.match(r'^#[0-9a-fA-F]{6}$', color): color = "#4f46e5"
    # Only allow https logo URLs (or empty) to avoid mixed-content / javascript: URIs.
    if logo and not re.match(r'^https://', logo): logo = ""
    if len(logo) > 500: logo = logo[:500]
    # `organizations` is the control plane and lives in platform.db — writing it via
    # sdb() silently targeted a table that doesn't exist there.
    cur = org_get(org_id) or {}
    _cur_company = cur.get("company_name") or org_id
    company = company or _cur_company
    c = pdb()
    c.execute("""UPDATE organizations SET company_name=?, brand_mark=?, brand_sub=?,
                    brand_color=?, logo_url=? WHERE org_id=?""",
              (company, mark or company[:12].upper(),
               sub or (cur.get("brand_sub") or "Employee Hub"), color, logo, org_id))
    c.commit(); c.close()
    # Refresh the live session so the navbar updates immediately for this admin.
    session["brand"] = brand_for_session(org_id)
    return jsonify({"ok": True, "brand": org_get(org_id)})

def _parse_sale_dt(x):
    x=(x or "").strip().replace("T"," ")
    if not x: return None
    for fmt in ("%Y-%m-%d %H:%M:%S","%m/%d/%Y %H:%M:%S","%Y/%m/%d %H:%M:%S",
                "%m/%d/%Y %H:%M","%Y-%m-%d %H:%M"):
        try: return datetime.strptime(x[:19], fmt)
        except Exception: pass
    try: return datetime.fromisoformat(x[:19])
    except Exception: return None

@app.route("/api/show-detail")
@req_role("admin")
def api_show_detail():
    """Deep-dive for one show: duration (from sale times), hourly sales, geography,
    giveaways, cancellations, pack time, top products."""
    label=(request.args.get("label") or "").strip()
    if not label: return jsonify({"ok":False,"error":"label required"})
    c=sdb()
    rows=c.execute("""SELECT i.quantity qty, COALESCE(i.revenue,0) rev, COALESCE(i.cancelled,0) canc,
                             i.created_time ct, i.buyer_state st, i.buyer_city ci, i.product_name pn, i.sku,
                             s.tracking_code tc, s.shipment_id sid
                      FROM shipment_items i JOIN shipments s ON s.shipment_id=i.shipment_id
                      WHERE s.import_label=?""",(label,)).fetchall()
    _shrow=c.execute("SELECT COALESCE(SUM(shipping_fee),0) sf FROM shipments WHERE import_label=? AND COALESCE(status,'')!='cancelled'",(label,)).fetchone()
    shipping=round((_shrow["sf"] if _shrow else 0) or 0,2)
    c.close()
    hours={}; states={}; cities={}; prods={}; times=[]
    revenue=0.0; units=0; canc_units=0; order_ids=set()
    for r in rows:
        if r["canc"]:
            canc_units+=r["qty"] or 0; continue
        revenue+=r["rev"] or 0; units+=r["qty"] or 0
        if r["sid"]: order_ids.add(r["sid"])
        dt=_parse_sale_dt(r["ct"])
        if dt:
            times.append(dt)
            hh=hours.setdefault(dt.hour,{"hour":dt.hour,"revenue":0.0,"units":0})
            hh["revenue"]+=r["rev"] or 0; hh["units"]+=r["qty"] or 0
        st=(r["st"] or "").strip()
        if st: states[st]=states.get(st,0)+(r["qty"] or 0)
        ci=(r["ci"] or "").strip()
        if ci: cities[ci]=cities.get(ci,0)+(r["qty"] or 0)
        pn=(r["pn"] or r["sku"] or "?")
        p=prods.setdefault(pn,{"name":pn,"units":0,"revenue":0.0}); p["units"]+=r["qty"] or 0; p["revenue"]+=r["rev"] or 0
    dur_min=start=end=None
    if times:
        mn=min(times); mx=max(times); dur_min=round((mx-mn).total_seconds()/60,1)
        start=mn.strftime("%Y-%m-%d %H:%M"); end=mx.strftime("%H:%M")
    g=gdb()
    try: gv=g.execute("SELECT COUNT(*) n FROM giveaways WHERE attach_show=?",(label,)).fetchone()["n"]
    except Exception: gv=0
    g.close()
    tset=set()
    for r in rows:
        if r["tc"]: tset.add(r["tc"])
        if r["sid"]: tset.add(r["sid"])
    packsec=[]
    if os.path.exists(log_file()):
        with open(log_file()) as f:
            for row in csv.DictReader(f):
                if (row.get("tracking_number","") or "") in tset:
                    try: dd=float(row.get("duration_seconds","0") or 0)
                    except Exception: dd=0
                    if 0<dd<=3600: packsec.append(dd)
    tot=units+canc_units
    return jsonify({"ok":True,"label":label,"host":_host_overrides().get(label) or _host_from_label(label) or "Unknown",
        "revenue":round(revenue,2),"shipping":shipping,"gross":round(revenue+shipping,2),
        "units":units,"orders":len(order_ids),
        "cancel_units":canc_units,"cancel_rate":round(100.0*canc_units/tot,1) if tot else 0,
        "duration_min":dur_min,"start":start,"end":end,
        "sales_per_hour_live":round(units/(dur_min/60.0),1) if dur_min else 0,
        "rev_per_hour_live":round(revenue/(dur_min/60.0),2) if dur_min else 0,
        "giveaways":gv,"avg_pack_sec":round(sum(packsec)/len(packsec),1) if packsec else 0,"packed":len(packsec),
        "hours":[hours[k] for k in sorted(hours)],
        "has_times":bool(times),
        "top_states":sorted([{"k":k,"v":v} for k,v in states.items()],key=lambda x:-x["v"])[:8],
        "top_cities":sorted([{"k":k,"v":v} for k,v in cities.items()],key=lambda x:-x["v"])[:6],
        "top_products":sorted(prods.values(),key=lambda x:-x["revenue"])[:10]})

@app.route("/api/product/<sku>/label.pdf")
@req_role("admin","cs")
def api_product_label(sku):
    """Printable Code128 barcode label for a SKU (for no-barcode products)."""
    safe=secure_filename(sku) or sku
    c=sdb(); p=c.execute("SELECT name FROM products WHERE sku=?",(safe,)).fetchone(); c.close()
    name=(p["name"] if p else "") or ""
    import io as _io
    try:
        import barcode
        from barcode.writer import ImageWriter
        bio=_io.BytesIO()
        barcode.get('code128', safe, writer=ImageWriter()).write(bio, options={"module_height":12.0,"font_size":9,"text_distance":3,"quiet_zone":2})
        bio.seek(0)
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import mm
        from reportlab.lib.utils import ImageReader
        out=_io.BytesIO(); W,H=60*mm,30*mm
        cp=canvas.Canvas(out,pagesize=(W,H))
        cp.drawImage(ImageReader(bio), 4*mm, 8*mm, width=52*mm, height=18*mm, preserveAspectRatio=True, anchor='sw')
        cp.setFont("Helvetica-Bold",9); cp.drawString(4*mm, 2.5*mm, name[:34])
        cp.showPage(); cp.save(); out.seek(0)
        return send_file(out, mimetype="application/pdf", download_name="label_"+safe+".pdf", as_attachment=False)
    except Exception as e:
        return ("Label generation failed: "+str(e), 500)

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
    """List import labels (shows) so the manager can filter to a specific show.
    Groups all CSVs of the same show into ONE row regardless of how many files were uploaded."""
    c = sdb()
    rows = c.execute("""SELECT import_label AS label,
                               COUNT(*) AS shipments,
                               MAX(imported_at) AS imported_at,
                               GROUP_CONCAT(DISTINCT platform) AS platform
                        FROM shipments
                        WHERE import_label IS NOT NULL AND import_label <> ''
                        GROUP BY import_label
                        ORDER BY MAX(imported_at) DESC""").fetchall()
    c.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/sku-lookup/<sku>")
@req_role("admin", "cs")
def api_sku_lookup(sku):
    """Find every item with this SKU. Optional filter by import_label (show name).
    Returns enough info to identify which physical item this is and where it went."""
    sku = (sku or "").strip()
    if not sku or len(sku) > 64:
        return jsonify({"ok": False, "error": "Invalid SKU"})
    label = (request.args.get("label") or request.args.get("batch") or "").strip()
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
    if label:
        q += " AND s.import_label = ?"
        params.append(label)
    q += " ORDER BY s.import_label DESC, i.cancelled, s.status"
    rows = c.execute(q, params).fetchall()
    c.close()
    return jsonify({
        "ok": True,
        "sku": sku,
        "label_filter": label or None,
        "matches": [dict(r) for r in rows],
    })


# ──────────────────────────────────────────────────────────────────────
# NEW-HIRE ONBOARDING — admin + public token-based flow
# ──────────────────────────────────────────────────────────────────────
@app.route("/admin/hires")
@req_role("admin", "cs")
def admin_hires_page():
    """List of all new hires with status + create-new-hire button."""
    return (HIRES_ADMIN_HTML
        .replace("__USER__", session.get("username", ""))
        .replace("__ROLE__", session.get("role", ""))
        .replace("__NAVBAR__", _navbar("hires"))
        .replace("__NAVBAR_CSS__", _NAVBAR_CSS))

@app.route("/admin/hires/<int:hire_id>/file")
@req_role("admin", "cs")
def admin_hire_file(hire_id):
    """Printable Employee File. Renders all hire data + signed docs + uploads
    on one long page styled for print. Admin's browser does the PDF export."""
    c = sdb()
    h = c.execute("SELECT * FROM new_hires WHERE id=?", (hire_id,)).fetchone()
    if not h:
        c.close()
        return "Hire not found", 404
    h = dict(h)
    # English content for the printed file regardless of hire's preferred language
    # (HR/legal/IRS need English for compliance).
    steps = _hire_steps_with_progress(h["id"], h["workflow_id"], lang="en") if h["workflow_id"] else []
    sigs = [dict(r) for r in c.execute("SELECT * FROM onboarding_signatures WHERE hire_id=? ORDER BY signed_at",
                                       (hire_id,)).fetchall()]
    uploads = [dict(r) for r in c.execute("SELECT * FROM onboarding_uploads WHERE hire_id=? ORDER BY uploaded_at",
                                          (hire_id,)).fetchall()]
    wf = c.execute("SELECT name FROM onboarding_workflows WHERE id=?", (h["workflow_id"],)).fetchone()
    c.close()
    workflow_name = wf["name"] if wf else "Onboarding"
    # Build the page as plain HTML — print stylesheet handles paper-friendly layout
    return render_hire_file_page(h, steps, sigs, uploads, workflow_name)

def render_hire_file_page(h, steps, sigs, uploads, workflow_name):
    """Helper to assemble HIRE_FILE_HTML — keeps the route slim."""
    import json as _json
    # Index uploads by step_id for inline rendering
    uploads_by_step = {}
    for u in uploads:
        uploads_by_step.setdefault(u["step_id"], []).append(u)
    # Index signatures by step_id
    sigs_by_step = {}
    for s in sigs:
        sigs_by_step.setdefault(s["step_id"], []).append(s)
    # Build the step sections
    step_html = []
    for s in steps:
        title = esc(s["title"])
        desc = esc(s["description"])
        body = esc(s["body"]).replace("\n", "<br>")
        section = f'<section class="step">'
        section += f'<div class="step-num">Step {s["step_order"]}</div>'
        section += f'<h2>{title}</h2>'
        if desc: section += f'<p class="step-desc">{desc}</p>'
        status = s.get("status") or "pending"
        completed_at = (s.get("completed_at") or "")[:16].replace("T", " ")
        section += f'<div class="step-status {status}">Status: <b>{status.upper()}</b>'
        if completed_at: section += f' &middot; Completed: {completed_at}'
        section += '</div>'
        if body:
            section += f'<div class="doc-body">{body}</div>'
        # Form responses
        if s["step_type"] == "form" and s.get("data_json"):
            try: data = _json.loads(s["data_json"]) or {}
            except: data = {}
            responses = data.get("responses") or {}
            if responses:
                section += '<table class="form-table"><thead><tr><th>Field</th><th>Response</th></tr></thead><tbody>'
                cfg = {}
                try: cfg = _json.loads(s.get("config_json") or "{}")
                except: pass
                label_lookup = {f.get("name"): f.get("label", f.get("name")) for f in cfg.get("fields", [])}
                for k, v in responses.items():
                    label = esc(label_lookup.get(k, k))
                    val = esc(v) if v else "—"
                    section += f'<tr><td>{label}</td><td>{val}</td></tr>'
                section += '</tbody></table>'
        # Signatures
        for sig in sigs_by_step.get(s["step_id"], []):
            section += '<div class="sig-block">'
            section += f'<div class="sig-name"><span class="cursive">{esc(sig["signed_name"])}</span></div>'
            section += '<div class="sig-line"></div>'
            section += f'<div class="sig-audit">'
            section += f'Signed by <b>{esc(sig["signed_name"])}</b> &middot; '
            section += f'{(sig.get("signed_at") or "")[:19].replace("T"," ")} UTC &middot; '
            section += f'IP {sig.get("ip_address") or "—"}'
            if sig.get("document_hash"):
                section += f' &middot; doc hash {sig["document_hash"][:16]}…'
            section += '</div>'
            section += '</div>'
        # Uploaded files
        if s["step_type"] == "upload":
            ups = uploads_by_step.get(s["step_id"], [])
            if ups:
                section += '<div class="uploads-list">'
                for u in ups:
                    fn = esc(u["original_filename"] or "file")
                    field = esc(u["field_name"])
                    size_kb = (u["size_bytes"] or 0) / 1024
                    is_image = (u.get("mime_type") or "").startswith("image/")
                    section += f'<div class="upload-item">'
                    section += f'<div class="upload-meta"><b>{field}</b> &middot; {fn} &middot; {size_kb:.0f} KB</div>'
                    if is_image:
                        section += f'<img class="upload-thumb" src="/api/hires/{h["id"]}/upload/{u["id"]}?inline=1" alt="{fn}">'
                    else:
                        section += f'<a href="/api/hires/{h["id"]}/upload/{u["id"]}" class="upload-link no-print">📎 Download {fn}</a>'
                    section += '</div>'
                section += '</div>'
            else:
                section += '<p class="empty-note">No files uploaded for this step.</p>'
        section += '</section>'
        step_html.append(section)
    return (HIRE_FILE_HTML
        .replace("__HIRE_NAME__", esc(h["full_name"]))
        .replace("__HIRE_EMAIL__", esc(h.get("email") or "—"))
        .replace("__HIRE_PHONE__", esc(h.get("phone") or "—"))
        .replace("__HIRE_ROLE__", esc(h.get("role_target") or "—"))
        .replace("__HIRE_STATUS__", (h.get("status") or "").upper().replace("_", " "))
        .replace("__HIRE_CREATED__", (h.get("created_at") or "")[:10])
        .replace("__HIRE_COMPLETED__", (h.get("completed_at") or "—")[:16].replace("T", " "))
        .replace("__HIRE_LANG__", (h.get("preferred_language") or "en").upper())
        .replace("__WORKFLOW_NAME__", esc(workflow_name))
        .replace("__STEPS_HTML__", "\n".join(step_html))
        .replace("__HIRE_ID__", str(h["id"]))
        .replace("__GENERATED_AT__", datetime.now().strftime("%Y-%m-%d %H:%M")))


@app.route("/admin/hires/<int:hire_id>")
@req_role("admin", "cs")
def admin_hire_detail(hire_id):
    """Per-hire detail: progress, signed docs, uploaded files, copy-link button."""
    c = sdb()
    h = c.execute("SELECT * FROM new_hires WHERE id=?", (hire_id,)).fetchone()
    c.close()
    if not h:
        return "Hire not found", 404
    return (HIRE_DETAIL_HTML
        .replace("__USER__", session.get("username", ""))
        .replace("__ROLE__", session.get("role", ""))
        .replace("__HIRE_ID__", str(hire_id))
        .replace("__HIRE_NAME__", esc(h["full_name"]))
        .replace("__INVITE_URL__", request.url_root.rstrip("/") + "/hire/" + h["invite_token"])
        .replace("__NAVBAR__", _navbar("hires"))
        .replace("__NAVBAR_CSS__", _NAVBAR_CSS))

@app.route("/api/hires", methods=["GET"])
@req_role("admin", "cs")
def api_hires_list():
    """Return all hires with progress %."""
    c = sdb()
    rows = c.execute("""
        SELECT h.*, w.name AS workflow_name
        FROM new_hires h
        LEFT JOIN onboarding_workflows w ON w.id = h.workflow_id
        ORDER BY h.created_at DESC
    """).fetchall()
    c.close()
    out = []
    for r in rows:
        d = dict(r)
        if d["workflow_id"]:
            done, total, pct = _hire_completion_pct(d["id"], d["workflow_id"])
            d["progress_done"] = done
            d["progress_total"] = total
            d["progress_pct"] = pct
        else:
            d["progress_done"] = d["progress_total"] = d["progress_pct"] = 0
        # Don't expose the raw token in the list view — only on detail page
        d.pop("invite_token", None)
        out.append(d)
    return jsonify(out)

@app.route("/api/workflows")
@req_role("admin", "cs")
def api_workflows_list():
    """List all onboarding workflows for the create-hire dropdown."""
    c = sdb()
    rows = c.execute("""SELECT id, name, description, role_target, is_default
                        FROM onboarding_workflows ORDER BY is_default DESC, id""").fetchall()
    c.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/hires", methods=["POST"])
@req_role("admin", "cs")
def api_hires_create():
    """Create a new hire + assign workflow + return the invite link."""
    d = request.get_json() or {}
    full_name = _clean_name(d.get("full_name"), 200)
    if not full_name:
        return jsonify({"ok": False, "error": "Full name is required"}), 400
    email = (d.get("email") or "").strip() or None
    phone = (d.get("phone") or "").strip() or None
    role_target = (d.get("role_target") or "worker").strip()
    preferred_language = (d.get("preferred_language") or "en").lower()
    if preferred_language not in ("en", "es"):
        preferred_language = "en"
    workflow_id = d.get("workflow_id")
    c = sdb()
    if not workflow_id:
        row = c.execute("SELECT id FROM onboarding_workflows WHERE is_default=1 ORDER BY id LIMIT 1").fetchone()
        if not row:
            c.close()
            wf_id = _seed_default_workflow_if_missing()
            c = sdb()
        else:
            wf_id = row["id"]
    else:
        wf_id = int(workflow_id)
    token = _new_invite_token()
    cur = c.execute("""INSERT INTO new_hires (full_name, email, phone, role_target, workflow_id,
                       invite_token, status, created_by, preferred_language)
                       VALUES (?, ?, ?, ?, ?, ?, 'invited', ?, ?)""",
                    (full_name, email, phone, role_target, wf_id, token,
                     session.get("username", ""), preferred_language))
    hire_id = cur.lastrowid
    c.commit(); c.close()
    invite_url = request.url_root.rstrip("/") + "/hire/" + token
    return jsonify({"ok": True, "id": hire_id, "invite_token": token, "invite_url": invite_url})

@app.route("/api/hires/<int:hire_id>", methods=["GET"])
@req_role("admin", "cs")
def api_hire_get(hire_id):
    """Full detail for admin view: hire info, workflow, every step + status + data."""
    c = sdb()
    h = c.execute("SELECT * FROM new_hires WHERE id=?", (hire_id,)).fetchone()
    if not h:
        c.close()
        return jsonify({"ok": False, "error": "Not found"}), 404
    h = dict(h)
    steps = _hire_steps_with_progress(h["id"], h["workflow_id"]) if h["workflow_id"] else []
    sigs = [dict(r) for r in c.execute("SELECT * FROM onboarding_signatures WHERE hire_id=? ORDER BY signed_at DESC",
                                       (hire_id,)).fetchall()]
    uploads = [dict(r) for r in c.execute("SELECT * FROM onboarding_uploads WHERE hire_id=? ORDER BY uploaded_at DESC",
                                          (hire_id,)).fetchall()]
    c.close()
    done, total, pct = _hire_completion_pct(h["id"], h["workflow_id"]) if h["workflow_id"] else (0, 0, 0)
    return jsonify({"ok": True, "hire": h, "steps": steps, "signatures": sigs,
                    "uploads": uploads,
                    "progress": {"done": done, "total": total, "pct": pct}})

@app.route("/api/hires/<int:hire_id>/regenerate-token", methods=["POST"])
@req_role("admin", "cs")
def api_hire_regen_token(hire_id):
    """Rotate the invite token — invalidates the old link. Useful if it leaked."""
    new_tok = _new_invite_token()
    c = sdb()
    c.execute("UPDATE new_hires SET invite_token=? WHERE id=?", (new_tok, hire_id))
    c.commit(); c.close()
    invite_url = request.url_root.rstrip("/") + "/hire/" + new_tok
    return jsonify({"ok": True, "invite_token": new_tok, "invite_url": invite_url})

@app.route("/api/hires/<int:hire_id>", methods=["DELETE"])
@req_role("admin")
def api_hire_delete(hire_id):
    """Hard-delete a hire and their progress (admin only). Use with care."""
    c = sdb()
    c.execute("DELETE FROM onboarding_progress WHERE hire_id=?", (hire_id,))
    c.execute("DELETE FROM onboarding_signatures WHERE hire_id=?", (hire_id,))
    c.execute("DELETE FROM onboarding_uploads WHERE hire_id=?", (hire_id,))
    c.execute("DELETE FROM new_hires WHERE id=?", (hire_id,))
    c.commit(); c.close()
    return jsonify({"ok": True})

# ─── Public flow (no login — token IS the auth) ────────────────────────
@app.route("/hire/<token>")
def public_hire_onboarding(token):
    """The new hire's own page. They reach this from the invite link.
    No login required — the URL token authenticates them to their own record."""
    h = _hire_by_token(token)
    if not h:
        return "<h1>Invite link not valid</h1><p>Please ask your manager to send a new link.</p>", 404
    return (HIRE_ONBOARDING_HTML
        .replace("__TOKEN__", token)
        .replace("__HIRE_NAME__", esc(h["full_name"]))
        .replace("__HIRE_ROLE__", h["role_target"] or ""))

@app.route("/api/hire/<token>")
def api_public_hire_get(token):
    """Public API the onboarding page uses to load its data.
    Language selection priority: ?lang query param → hire's preferred_language → 'en'."""
    h = _hire_by_token(token)
    if not h:
        return jsonify({"ok": False, "error": "Invalid token"}), 404
    lang = (request.args.get("lang") or h.get("preferred_language") or "en").lower()
    if lang not in ("en", "es"):
        lang = "en"
    steps = _hire_steps_with_progress(h["id"], h["workflow_id"], lang=lang) if h["workflow_id"] else []
    done, total, pct = _hire_completion_pct(h["id"], h["workflow_id"]) if h["workflow_id"] else (0, 0, 0)
    h.pop("invite_token", None)
    return jsonify({"ok": True, "hire": h, "lang": lang, "steps": steps,
                    "progress": {"done": done, "total": total, "pct": pct}})

@app.route("/api/hire/<token>/lang", methods=["POST"])
def api_public_hire_set_lang(token):
    """Persist the new hire's chosen language so the admin sees what they prefer."""
    h = _hire_by_token(token)
    if not h:
        return jsonify({"ok": False, "error": "Invalid token"}), 404
    lang = ((request.get_json() or {}).get("lang") or "en").lower()
    if lang not in ("en", "es"):
        lang = "en"
    c = sdb()
    c.execute("UPDATE new_hires SET preferred_language=? WHERE id=?", (lang, h["id"]))
    c.commit(); c.close()
    return jsonify({"ok": True, "lang": lang})


# ─── File upload on an onboarding step ─────────────────────────────────
HIRE_UPLOAD_MAX_BYTES = 15 * 1024 * 1024   # 15 MB
HIRE_UPLOAD_ALLOWED_EXT = {"pdf", "png", "jpg", "jpeg", "gif", "webp", "heic"}
# Map extension -> MIME server-side. NEVER trust the client's Content-Type:
# a file uploaded as image/jpeg with Content-Type text/html would otherwise be
# served back as HTML on our origin (stored XSS). This mapping is the source of truth.
HIRE_UPLOAD_EXT_MIME = {
    "pdf": "application/pdf", "png": "image/png", "jpg": "image/jpeg",
    "jpeg": "image/jpeg", "gif": "image/gif", "webp": "image/webp",
    "heic": "image/heic",
}
HIRE_LOCAL_UPLOAD_DIR = os.path.join(DATA_DIR, "hire_uploads")
os.makedirs(HIRE_LOCAL_UPLOAD_DIR, exist_ok=True)

def _hire_upload_storage_key(hire_id, step_id, field_name, filename):
    """Build a deterministic-ish R2 key for this upload. Filename collisions
    inside a hire+step+field overwrite the old one — that's intentional, the
    hire can re-upload to fix a blurry photo."""
    safe_field = re.sub(r'[^A-Za-z0-9_\-]', '_', field_name)[:40] or "file"
    safe_fn = secure_filename(filename) or "file"
    # Org-scoped: hire_id is a per-tenant autoincrement, so a bare key would collide
    # (and overwrite) across tenants.
    return f"{current_org()}/hire_uploads/{hire_id}/{step_id}/{safe_field}_{safe_fn}"

@app.route("/api/hire/<token>/step/<int:step_id>/upload", methods=["POST"])
def api_public_hire_upload(token, step_id):
    """Accept a file upload from the new hire. multipart fields:
       file: the actual file
       field_name: which slot this fills (e.g. 'id_front' / 'id_back')"""
    h = _hire_by_token(token)
    if not h:
        return jsonify({"ok": False, "error": "Invalid token"}), 404
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "Pick a file to upload"}), 400
    field_name = (request.form.get("field_name") or "file").strip()[:40]
    fn = secure_filename(f.filename) or "file"
    ext = fn.rsplit(".", 1)[-1].lower() if "." in fn else ""
    if ext not in HIRE_UPLOAD_ALLOWED_EXT:
        return jsonify({"ok": False, "error": "File type not allowed. Use PDF or image."}), 400
    # Validate step exists and is an upload step
    c = sdb()
    step = c.execute("SELECT * FROM onboarding_steps WHERE id=? AND workflow_id=?",
                     (step_id, h["workflow_id"])).fetchone()
    if not step or step["step_type"] != "upload":
        c.close()
        return jsonify({"ok": False, "error": "Not an upload step"}), 400
    # Size check by reading into memory once
    f.stream.seek(0, 2)
    size = f.stream.tell()
    f.stream.seek(0)
    if size > HIRE_UPLOAD_MAX_BYTES:
        c.close()
        return jsonify({"ok": False, "error": f"File too large (max {HIRE_UPLOAD_MAX_BYTES // (1024*1024)}MB)"}), 400
    key = _hire_upload_storage_key(h["id"], step_id, field_name, fn)
    # Derive MIME from the (already whitelisted) extension, not from the client.
    mime = HIRE_UPLOAD_EXT_MIME.get(ext, "application/octet-stream")
    if r2:
        try:
            r2.upload_fileobj(f.stream, R2_BUCKET, key,
                              ExtraArgs={"ContentType": mime})
        except Exception as e:
            print("R2 hire upload failed:", e, flush=True)
            c.close()
            return jsonify({"ok": False, "error": "Storage upload failed"}), 500
    else:
        local_path = os.path.join(HIRE_LOCAL_UPLOAD_DIR, key.replace("/", "__"))
        f.save(local_path)
    # Replace any previous upload for this (hire, step, field) so re-uploads work
    c.execute("""DELETE FROM onboarding_uploads
                 WHERE hire_id=? AND step_id=? AND field_name=?""",
              (h["id"], step_id, field_name))
    c.execute("""INSERT INTO onboarding_uploads
                 (hire_id, step_id, field_name, original_filename, storage_key, mime_type, size_bytes)
                 VALUES (?, ?, ?, ?, ?, ?, ?)""",
              (h["id"], step_id, field_name, fn, key, mime, size))
    c.commit(); c.close()
    return jsonify({"ok": True, "field_name": field_name, "filename": fn, "size_bytes": size, "mime_type": mime})

@app.route("/api/hire/<token>/step/<int:step_id>/upload/<field>", methods=["DELETE"])
def api_public_hire_upload_delete(token, step_id, field):
    """Remove an uploaded file (re-upload often does this via the POST handler,
    but this lets the hire actively delete a slot before completion)."""
    h = _hire_by_token(token)
    if not h:
        return jsonify({"ok": False, "error": "Invalid token"}), 404
    c = sdb()
    rows = c.execute("""SELECT id, storage_key FROM onboarding_uploads
                        WHERE hire_id=? AND step_id=? AND field_name=?""",
                     (h["id"], step_id, field)).fetchall()
    for r in rows:
        if r2:
            try: r2.delete_object(Bucket=R2_BUCKET, Key=r["storage_key"])
            except: pass
        else:
            try: os.remove(os.path.join(HIRE_LOCAL_UPLOAD_DIR, r["storage_key"].replace("/", "__")))
            except: pass
        c.execute("DELETE FROM onboarding_uploads WHERE id=?", (r["id"],))
    c.commit(); c.close()
    return jsonify({"ok": True, "deleted": len(rows)})

@app.route("/api/hires/<int:hire_id>/upload/<int:upload_id>")
@req_role("admin", "cs")
def api_admin_hire_upload_view(hire_id, upload_id):
    """Admin-side: redirect to a short-lived presigned R2 URL (or serve local file)
    so they can view/download the new hire's ID, certifications, etc."""
    c = sdb()
    row = c.execute("SELECT * FROM onboarding_uploads WHERE id=? AND hire_id=?",
                    (upload_id, hire_id)).fetchone()
    c.close()
    if not row:
        return "Not found", 404
    key = row["storage_key"]
    fn = row["original_filename"] or "file"
    inline = request.args.get("inline") == "1"
    # Re-derive MIME from the extension (don't trust the stored/old value) so an
    # image row can never be served as text/html on our origin.
    ext = fn.rsplit(".", 1)[-1].lower() if "." in fn else ""
    safe_mime = HIRE_UPLOAD_EXT_MIME.get(ext, "application/octet-stream")
    # Only images/PDF may be shown inline; anything else is forced to download.
    inline = inline and (safe_mime.startswith("image/") or safe_mime == "application/pdf")
    # Sanitize filename for the Content-Disposition header (strip quotes/CR/LF).
    safe_fn = re.sub(r'["\r\n]', "", fn)
    disposition = "inline" if inline else f'attachment; filename="{safe_fn}"'
    if r2:
        try:
            url = r2.generate_presigned_url("get_object",
                Params={"Bucket": R2_BUCKET, "Key": key,
                        "ResponseContentDisposition": disposition,
                        "ResponseContentType": safe_mime},
                ExpiresIn=R2_PRESIGN_TTL)
            return redirect(url)
        except Exception as e:
            return f"Storage error: {e}", 500
    local_path = os.path.join(HIRE_LOCAL_UPLOAD_DIR, key.replace("/", "__"))
    if not os.path.exists(local_path):
        return "File missing", 404
    from flask import send_file
    resp = send_file(local_path, mimetype=safe_mime,
                     as_attachment=not inline, download_name=fn)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp


@app.route("/api/hire/<token>/step/<int:step_id>/complete", methods=["POST"])
def api_public_hire_complete_step(token, step_id):
    """Mark a step complete. Body is type-specific. Validated by step_type."""
    import json as _json, hashlib as _hashlib
    h = _hire_by_token(token)
    if not h:
        return jsonify({"ok": False, "error": "Invalid token"}), 404
    c = sdb()
    step = c.execute("SELECT * FROM onboarding_steps WHERE id=? AND workflow_id=?",
                     (step_id, h["workflow_id"])).fetchone()
    if not step:
        c.close()
        return jsonify({"ok": False, "error": "Step not found"}), 404
    step = dict(step)
    payload = request.get_json() or {}
    data = {}
    if step["step_type"] in ("info", "video"):
        # Nothing required — just mark done
        data = {"acknowledged": True}
    elif step["step_type"] == "ack":
        # Require the checkbox confirmation
        if not payload.get("acknowledged"):
            c.close()
            return jsonify({"ok": False, "error": "You must check the acknowledgement box"}), 400
        data = {"acknowledged": True, "signed_name": (payload.get("signed_name") or "").strip()}
        if data["signed_name"]:
            # Capture signature record for audit trail
            body_hash = _hashlib.sha256((step.get("body") or "").encode("utf-8")).hexdigest()
            c.execute("""INSERT INTO onboarding_signatures
                         (hire_id, step_id, document_title, signed_name, signature_type, signature_data,
                          document_hash, ip_address, user_agent)
                         VALUES (?, ?, ?, ?, 'typed', ?, ?, ?, ?)""",
                      (h["id"], step_id, step["title"], data["signed_name"], data["signed_name"],
                       body_hash, request.remote_addr, request.headers.get("User-Agent", "")[:300]))
    elif step["step_type"] == "sign":
        signed_name = (payload.get("signed_name") or "").strip()
        if not signed_name or len(signed_name) < 2:
            c.close()
            return jsonify({"ok": False, "error": "Type your full name to sign"}), 400
        body_hash = _hashlib.sha256((step.get("body") or "").encode("utf-8")).hexdigest()
        c.execute("""INSERT INTO onboarding_signatures
                     (hire_id, step_id, document_title, signed_name, signature_type, signature_data,
                      document_hash, ip_address, user_agent)
                     VALUES (?, ?, ?, ?, 'typed', ?, ?, ?, ?)""",
                  (h["id"], step_id, step["title"], signed_name, signed_name,
                   body_hash, request.remote_addr, request.headers.get("User-Agent", "")[:300]))
        data = {"signed_name": signed_name, "document_hash": body_hash}
    elif step["step_type"] == "form":
        # Validate against the configured fields
        try:
            cfg = _json.loads(step.get("config_json") or "{}")
        except: cfg = {}
        fields = cfg.get("fields", [])
        responses = payload.get("responses", {}) or {}
        missing = []
        for f in fields:
            if f.get("required") and not str(responses.get(f["name"], "")).strip():
                missing.append(f.get("label") or f.get("name"))
        if missing:
            c.close()
            return jsonify({"ok": False, "error": "Missing: " + ", ".join(missing)}), 400
        data = {"responses": responses}
    elif step["step_type"] == "upload":
        # The actual file upload uses a separate endpoint; this completes the step
        # after at least one required field has a row in onboarding_uploads.
        try:
            cfg = _json.loads(step.get("config_json") or "{}")
        except: cfg = {}
        for f in cfg.get("fields", []):
            if f.get("required"):
                count = c.execute("""SELECT COUNT(*) AS n FROM onboarding_uploads
                                     WHERE hire_id=? AND step_id=? AND field_name=?""",
                                  (h["id"], step_id, f["name"])).fetchone()["n"]
                if count == 0:
                    c.close()
                    return jsonify({"ok": False, "error": "Please upload: " + (f.get("label") or f["name"])}), 400
        data = {"completed": True}
    else:
        c.close()
        return jsonify({"ok": False, "error": "Unknown step type"}), 400
    c.commit(); c.close()
    _mark_step(h["id"], step_id, data, status="done")
    return jsonify({"ok": True})


# ──────────────────────────────────────────────────────────────────────
# TABLE CLEANUP — admin page + API
# ──────────────────────────────────────────────────────────────────────
@app.route("/admin/cleanup")
@req_role("admin", "cs", "worker", "picker")
def admin_cleanup_page():
    """Table-cleanup tab. Lists shows with cancelled items, lets manager and
    workers tap rows as they pull cancelled inventory off the warehouse table.
    Workers reach this page via /pick when their show is still blocked."""
    return (CLEANUP_HTML
        .replace("__USER__", session.get("username", ""))
        .replace("__ROLE__", session.get("role", ""))
        .replace("__NAVBAR__", _navbar("cleanup"))
        .replace("__NAVBAR_CSS__", _NAVBAR_CSS))

@app.route("/api/cleanup/shows")
@req_role("admin", "cs", "worker", "picker")
def api_cleanup_shows():
    """List shows from the active 5-day window with cleanup progress for each.
    The picker frontend uses this to decide whether to allow scanning."""
    c = sdb()
    rows = c.execute("""
        SELECT import_label AS label,
               COUNT(*) AS shipments,
               MAX(imported_at) AS imported_at,
               GROUP_CONCAT(DISTINCT platform) AS platform
        FROM shipments
        WHERE import_label IS NOT NULL AND import_label <> ''
          AND imported_at >= datetime('now', '-5 days')
        GROUP BY import_label
        ORDER BY MAX(imported_at) DESC
    """).fetchall()
    c.close()
    out = []
    for r in rows:
        p = _cleanup_progress(r["label"])
        out.append({
            "label": r["label"],
            "shipments": r["shipments"],
            "platform": r["platform"],
            "imported_at": r["imported_at"],
            **p,
        })
    return jsonify(out)

@app.route("/api/cleanup/<path:label>")
@req_role("admin", "cs", "worker", "picker")
def api_cleanup_groups(label):
    """Get cancelled-item groups for a show. One row per (SKU, Part) combo
    with the total quantity to physically pull and an order_count for context."""
    groups = _cleanup_groups(label)
    progress = _cleanup_progress(label)
    return jsonify({"ok": True, "label": label, "groups": groups, **progress})

@app.route("/api/cleanup/<path:label>/mark", methods=["POST"])
@req_role("admin", "cs", "worker", "picker")
def api_cleanup_mark(label):
    """Toggle a (sku, part) cleanup row as removed/not-removed. Body: {sku, part, removed:bool}."""
    d = request.get_json() or {}
    sku = (d.get("sku") or "").strip()
    part = (d.get("part") or "").strip()
    removed = bool(d.get("removed", True))
    if not sku:
        return jsonify({"ok": False, "error": "Missing SKU"}), 400
    user = session.get("username", "")
    c = sdb()
    if removed:
        # Upsert — set removed_at to now
        c.execute("""
            INSERT INTO cleanup_state (import_label, sku, part, removed_at, removed_by)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
            ON CONFLICT(import_label, sku, part)
            DO UPDATE SET removed_at = CURRENT_TIMESTAMP, removed_by = excluded.removed_by
        """, (label, sku, part, user))
    else:
        # Unmark — delete the row so it goes back to pending
        c.execute("""DELETE FROM cleanup_state WHERE import_label=? AND sku=? AND part=?""",
                  (label, sku, part))
    c.commit(); c.close()
    progress = _cleanup_progress(label)
    return jsonify({"ok": True, **progress})


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
            try: r2.delete_object(Bucket=R2_BUCKET, Key=_r2_resolve("documents", stored))
            except Exception as e: print("R2 doc delete failed:", e, flush=True)
        else:
            path = os.path.join(docs_dir(), stored)
            rp = os.path.realpath(path)
            if rp.startswith(os.path.realpath(docs_dir()) + os.sep) and os.path.exists(rp):
                try: os.remove(rp)
                except: pass
    del docs[doc_id]
    _docs_save(docs)
    return jsonify({"ok": True})


@app.route("/api/users")
@req_role("admin")
def api_users():
    u=ldj(USERS_FILE)
    myorg=session.get("org",DEFAULT_ORG)
    return jsonify({k:{"name":v["name"],"role":v["role"],"extra_roles":v.get("extra_roles",[]),
                       "has_badge":bool(v.get("badge_token"))}
                    for k,v in u.items() if v.get("org",DEFAULT_ORG)==myorg})

@app.route("/api/audit-log")
@req_role("admin")
def api_audit_log():
    c=sdb()
    rows=[dict(r) for r in c.execute(
        "SELECT at,actor,role,action,detail,ip FROM audit_log ORDER BY id DESC LIMIT 300").fetchall()]
    c.close()
    return jsonify({"ok":True,"entries":rows})

@app.route("/admin/audit")
@req_role("admin")
def audit_page():
    return AUDIT_HTML.replace("__NAME__",esc(session.get("name",""))).replace(
        "__NAVBAR__",_navbar("audit")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

# ══════════════════════════════════════════════════════════
# ROSTER — schedule hosts + assistants across the live channels 24/7.
# 6-hour blocks, auto-assigned (eligibility + no double-booking + fair hours),
# reviewed & approved by a manager. Everyone else sees their own shifts.
# ══════════════════════════════════════════════════════════
_ROSTER_BLOCKS=[("00:00","06:00"),("06:00","12:00"),("12:00","18:00"),("18:00","24:00")]

def _week_start(dstr):
    """Monday of the week containing dstr (YYYY-MM-DD)."""
    try: d=datetime.strptime(dstr[:10],"%Y-%m-%d").date()
    except Exception: d=datetime.now().date()
    return (d - timedelta(days=d.weekday())).isoformat()

def _channels():
    c=sdb(); rows=[dict(r) for r in c.execute(
        "SELECT id,name,platform,language FROM channels WHERE active=1 ORDER BY sort,id").fetchall()]; c.close()
    return rows

def _roster_staff():
    """Hosts + assistants in this org, with their allowed channel ids."""
    users=ldj(USERS_FILE) if os.path.exists(USERS_FILE) else {}
    org=session.get("org",DEFAULT_ORG)
    out={"host":[],"assistant":[]}
    for un,info in users.items():
        if info.get("org",DEFAULT_ORG)!=org: continue
        roles=_effective_roles(info)
        person={"username":un,"name":info.get("name") or un,"allowed_channels":info.get("allowed_channels") or []}
        if "host" in roles: out["host"].append(person)
        if "assistant" in roles: out["assistant"].append(dict(person))
    return out

@app.route("/api/roster/channels")
@req_role("admin","cs","host","assistant")
def api_roster_channels():
    return jsonify({"ok":True,"channels":_channels()})

@app.route("/api/roster/channels",methods=["POST"])
@req_role("admin")
def api_roster_channel_add():
    """Create one of this tenant's selling channels (their own brands/accounts)."""
    d=request.get_json() or {}
    name=(d.get("name") or "").strip()[:60]
    if not name: return jsonify({"ok":False,"error":"Channel name is required"})
    platform=(d.get("platform") or "").strip().lower()
    if platform not in ("tiktok","whatnot",""): platform=""
    lang=(d.get("language") or "").strip()[:8]
    c=sdb()
    if c.execute("SELECT 1 FROM channels WHERE LOWER(name)=LOWER(?)",(name,)).fetchone():
        c.close(); return jsonify({"ok":False,"error":"You already have a channel with that name"})
    nxt=(c.execute("SELECT COALESCE(MAX(sort),-1)+1 FROM channels").fetchone()[0]) or 0
    cur=c.execute("INSERT INTO channels(name,platform,language,sort) VALUES(?,?,?,?)",(name,platform,lang,nxt))
    cid=cur.lastrowid; c.commit(); c.close()
    alog("roster.channel_add",name)
    return jsonify({"ok":True,"id":cid,"channels":_channels()})

@app.route("/api/roster/channels/<int:cid>",methods=["POST"])
@req_role("admin")
def api_roster_channel_update(cid):
    """Rename, re-platform, or deactivate a channel. Deactivating keeps history intact."""
    d=request.get_json() or {}
    c=sdb()
    row=c.execute("SELECT * FROM channels WHERE id=?",(cid,)).fetchone()
    if not row:
        c.close(); return jsonify({"ok":False,"error":"Channel not found"})
    if d.get("name") is not None:
        nm=(d.get("name") or "").strip()[:60]
        if not nm: c.close(); return jsonify({"ok":False,"error":"Name cannot be empty"})
        if c.execute("SELECT 1 FROM channels WHERE LOWER(name)=LOWER(?) AND id!=?",(nm,cid)).fetchone():
            c.close(); return jsonify({"ok":False,"error":"Another channel already uses that name"})
        c.execute("UPDATE channels SET name=? WHERE id=?",(nm,cid))
    if d.get("platform") is not None:
        pf=(d.get("platform") or "").strip().lower()
        if pf in ("tiktok","whatnot",""): c.execute("UPDATE channels SET platform=? WHERE id=?",(pf,cid))
    if d.get("language") is not None:
        c.execute("UPDATE channels SET language=? WHERE id=?",((d.get("language") or "").strip()[:8],cid))
    if d.get("active") is not None:
        c.execute("UPDATE channels SET active=? WHERE id=?",(1 if d.get("active") else 0,cid))
    c.commit(); c.close()
    alog("roster.channel_update","channel #%d"%cid)
    return jsonify({"ok":True,"channels":_channels()})

@app.route("/api/roster/staff")
@req_role("admin","cs")
def api_roster_staff():
    return jsonify({"ok":True,"staff":_roster_staff(),"channels":_channels()})

@app.route("/api/roster/staff/<username>/channels",methods=["POST"])
@req_role("admin","cs")
def api_roster_set_channels(username):
    ids=(request.get_json() or {}).get("allowed_channels")
    if not isinstance(ids,list): return jsonify({"ok":False,"error":"channels list required"})
    ids=[int(x) for x in ids if str(x).isdigit()]
    with update_json(USERS_FILE) as users:
        if username not in users or not _same_org_user(users,username):
            return jsonify({"ok":False,"error":"User not found"}),404
        if not any(r in ("host","assistant") for r in _effective_roles(users[username])):
            return jsonify({"ok":False,"error":"Only hosts/assistants have channels"})
        users[username]["allowed_channels"]=ids
    alog("roster.channels",username+" -> "+",".join(map(str,ids)))
    return jsonify({"ok":True})

def _eligible(person, ch_id):
    ac=person.get("allowed_channels") or []
    return (not ac) or (ch_id in ac)   # empty = allowed everywhere

def _ov(a_st,a_en,b_st,b_en):
    return _tmin(a_st)<_tmin(b_en) and _tmin(b_st)<_tmin(a_en)

def _avail_covers(c, u, date, s, e):
    """True if user u submitted an availability range covering [s,e] on date."""
    for r in c.execute("SELECT start_time,end_time FROM availability WHERE username=? AND shift_date=?",(u,date)).fetchall():
        if _tmin(r["start_time"])<=_tmin(s) and _tmin(r["end_time"] or "24:00")>=_tmin(e):
            return True
    return False

def _person_free(c, u, date, s, e, exclude=None):
    for r in c.execute("SELECT id,start_time,end_time FROM shifts WHERE shift_date=? AND (host_user=? OR assistant_user=?)",(date,u,u)).fetchall():
        if exclude and r["id"]==exclude: continue
        if _ov(s,e,r["start_time"],r["end_time"]): return False
    return True

@app.route("/api/roster/available")
@req_role("admin","cs")
def api_roster_available():
    """Who can take a proposed shift: eligible for the channel, available for the
    whole time range, and not already booked in an overlapping shift."""
    ch_id=request.args.get("channel_id",type=int)
    date=(request.args.get("date") or "").strip()
    s=(request.args.get("start") or "").strip(); e=(request.args.get("end") or "").strip()
    exclude=request.args.get("exclude",type=int)
    if not (ch_id and re.match(r'^\d{4}-\d{2}-\d{2}$',date) and _tmin(s) is not None and _tmin(e) is not None and _tmin(e)>_tmin(s)):
        return jsonify({"ok":False,"error":"Set channel, date and a valid time range"})
    staff=_roster_staff(); c=sdb()
    def avail_pool(pool):
        out=[]
        for p in pool:
            if not _eligible(p,ch_id): continue
            if not _avail_covers(c,p["username"],date,s,e): continue
            free=_person_free(c,p["username"],date,s,e,exclude)
            out.append({"username":p["username"],"name":p["name"],"free":free})
        return out
    res={"hosts":avail_pool(staff["host"]),"assistants":avail_pool(staff["assistant"])}
    c.close()
    return jsonify({"ok":True,**res})

@app.route("/api/roster/shift/create",methods=["POST"])
@req_role("admin","cs")
def api_roster_shift_create():
    """Create a custom shift. Validates host/assistant availability + no overlap."""
    d=request.get_json() or {}
    ch_id=d.get("channel_id"); date=(d.get("date") or "").strip()
    s=(d.get("start") or "").strip(); e=(d.get("end") or "").strip()
    if not (ch_id and re.match(r'^\d{4}-\d{2}-\d{2}$',date) and _tmin(s) is not None and _tmin(e) is not None and _tmin(e)>_tmin(s)):
        return jsonify({"ok":False,"error":"Pick a channel, date and valid start/end times"})
    host=(d.get("host_user") or "").strip() or None
    asst=(d.get("assistant_user") or "").strip() or None
    ws=_week_start(date)
    c=sdb()
    for who in (host,asst):
        if who and not _person_free(c,who,date,s,e):
            c.close(); return jsonify({"ok":False,"error":who+" is already booked in an overlapping shift"})
    c.execute("""INSERT INTO shifts(channel_id,shift_date,start_time,end_time,host_user,assistant_user,week_start,status,is_exception)
                 VALUES(?,?,?,?,?,?,?, 'proposed', 1)""",(ch_id,date,s,e,host,asst,ws))
    c.commit(); c.close()
    alog("roster.shift_add",date+" "+s+"-"+e)
    return jsonify({"ok":True})

@app.route("/api/roster/shift/<int:sid>/delete",methods=["POST"])
@req_role("admin","cs")
def api_roster_shift_delete(sid):
    c=sdb(); c.execute("DELETE FROM shifts WHERE id=?",(sid,)); c.commit(); c.close()
    return jsonify({"ok":True})

@app.route("/api/roster/week")
@req_role("admin","cs")
def api_roster_week():
    ws=_week_start(request.args.get("week_start") or datetime.now().date().isoformat())
    c=sdb()
    rows=[dict(r) for r in c.execute("SELECT * FROM shifts WHERE week_start=? ORDER BY shift_date,channel_id,start_time",(ws,)).fetchall()]
    c.close()
    users=ldj(USERS_FILE) if os.path.exists(USERS_FILE) else {}
    def nm(u): return (users.get(u,{}).get("name") or u) if u else None
    incomplete=0; covered=0
    for r in rows:
        r["host_name"]=nm(r["host_user"]); r["assistant_name"]=nm(r["assistant_user"])
        if not r["host_user"] or not r["assistant_user"]: incomplete+=1
        else: covered+=max(0,_tmin(r["end_time"])-_tmin(r["start_time"]))
    approved=any(r["status"]=="approved" for r in rows)
    # 24/7 target across every channel & day
    nchan=len(_channels()); target=nchan*7*1440
    return jsonify({"ok":True,"week_start":ws,"shifts":rows,"channels":_channels(),
                    "incomplete":incomplete,"approved":approved,
                    "covered_hours":round(covered/60,1),"target_hours":round(target/60,1)})

@app.route("/api/roster/shift/<int:sid>",methods=["POST"])
@req_role("admin","cs")
def api_roster_reassign(sid):
    """Reassign a shift's host/assistant; blocks overlap conflicts."""
    d=request.get_json() or {}
    c=sdb()
    sh=c.execute("SELECT * FROM shifts WHERE id=?",(sid,)).fetchone()
    if not sh: c.close(); return jsonify({"ok":False,"error":"Shift not found"}),404
    sh=dict(sh)
    for field,who in (("host_user",d.get("host_user")),("assistant_user",d.get("assistant_user"))):
        if field not in d: continue
        who=(who or "").strip() or None
        if who and not _person_free(c,who,sh["shift_date"],sh["start_time"],sh["end_time"],exclude=sid):
            c.close(); return jsonify({"ok":False,"error":who+" is already booked in that time slot"})
        c.execute("UPDATE shifts SET "+field+"=? WHERE id=?",(who,sid))
    c.commit(); c.close()
    alog("roster.reassign","shift #"+str(sid))
    return jsonify({"ok":True})

@app.route("/api/roster/approve",methods=["POST"])
@req_role("admin","cs")
def api_roster_approve():
    ws=_week_start((request.get_json() or {}).get("week_start") or "")
    c=sdb(); n=c.execute("UPDATE shifts SET status='approved' WHERE week_start=?",(ws,)).rowcount; c.commit(); c.close()
    alog("roster.approve","week "+ws)
    return jsonify({"ok":True,"approved":n})

@app.route("/api/my-schedule")
@req_login
def api_my_schedule():
    """A host/assistant's own upcoming approved shifts."""
    u=session.get("user")
    today=datetime.now().date().isoformat()
    c=sdb()
    rows=[dict(r) for r in c.execute(
        """SELECT s.*, c.name channel_name, c.platform FROM shifts s JOIN channels c ON c.id=s.channel_id
           WHERE (s.host_user=? OR s.assistant_user=?) AND s.shift_date>=? AND s.status='approved'
           ORDER BY s.shift_date,s.start_time LIMIT 200""",(u,u,today)).fetchall()]
    c.close()
    users=ldj(USERS_FILE) if os.path.exists(USERS_FILE) else {}
    for r in rows:
        r["role_here"]="Host" if r["host_user"]==u else "Assistant"
        other=r["assistant_user"] if r["host_user"]==u else r["host_user"]
        r["with"]=users.get(other,{}).get("name") or other
    return jsonify({"ok":True,"shifts":rows})

@app.route("/admin/roster")
@req_role("admin","cs")
def roster_page():
    return ROSTER_HTML.replace("__NAME__",esc(session.get("name",""))).replace(
        "__NAVBAR__",_navbar("roster")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

@app.route("/my-schedule")
@req_login
def my_schedule_page():
    return MYSCHEDULE_HTML.replace("__NAME__",esc(session.get("name",""))).replace(
        "__NAVBAR__",_navbar("myschedule")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

def _tmin(t):
    """'HH:MM' -> minutes. '24:00' allowed as end-of-day."""
    t=(t or "").strip()
    if t=="24:00": return 1440
    m=re.match(r'^(\d{1,2}):(\d{2})$',t)
    if not m: return None
    h,mn=int(m.group(1)),int(m.group(2))
    if h>23 or mn>59: return None
    return h*60+mn

@app.route("/api/availability")
@req_role("host","assistant","admin","cs")
def api_availability_get():
    """The logged-in user's submitted availability ranges for a week + their channels."""
    ws=_week_start(request.args.get("week_start") or datetime.now().date().isoformat())
    u=session.get("user")
    c=sdb()
    ranges=[{"date":r["shift_date"],"start":r["start_time"],"end":r["end_time"] or "24:00"} for r in c.execute(
        "SELECT shift_date,start_time,end_time FROM availability WHERE username=? AND week_start=? ORDER BY shift_date,start_time",(u,ws)).fetchall()]
    c.close()
    info=(ldj(USERS_FILE) if os.path.exists(USERS_FILE) else {}).get(u,{})
    return jsonify({"ok":True,"week_start":ws,"ranges":ranges,
                    "channels":_channels(),"allowed_channels":info.get("allowed_channels") or []})

@app.route("/api/availability",methods=["POST"])
@req_role("host","assistant","admin","cs")
def api_availability_save():
    """Replace the user's availability for a week with submitted time RANGES."""
    d=request.get_json() or {}
    ws=_week_start(d.get("week_start") or "")
    u=session.get("user")
    ranges=d.get("ranges") or []
    c=sdb()
    c.execute("DELETE FROM availability WHERE username=? AND week_start=?",(u,ws))
    n=0
    for r in ranges:
        dt=(r.get("date") or "").strip(); st=(r.get("start") or "").strip(); en=(r.get("end") or "").strip()
        if not re.match(r'^\d{4}-\d{2}-\d{2}$',dt): continue
        sm,em=_tmin(st),_tmin(en)
        if sm is None or em is None or em<=sm: continue
        c.execute("INSERT INTO availability(username,week_start,shift_date,start_time,end_time) VALUES(?,?,?,?,?)",(u,ws,dt,st,en))
        n+=1
    c.commit(); c.close()
    return jsonify({"ok":True,"saved":n})

@app.route("/api/roster/submissions")
@req_role("admin","cs")
def api_roster_submissions():
    """Manager view: who submitted what for a week + who hasn't + coverage per slot."""
    ws=_week_start(request.args.get("week_start") or datetime.now().date().isoformat())
    staff=_roster_staff()
    everyone={}
    for role,grp in staff.items():
        for p in grp: everyone.setdefault(p["username"],{"username":p["username"],"name":p["name"],"roles":set()})["roles"].add(role)
    c=sdb()
    rows=c.execute("SELECT username,shift_date,start_time,end_time FROM availability WHERE week_start=? ORDER BY shift_date,start_time",(ws,)).fetchall()
    c.close()
    byuser={}
    for r in rows:
        byuser.setdefault(r["username"],[]).append({"date":r["shift_date"],"start":r["start_time"],"end":r["end_time"] or "24:00"})
    submitted=[]; missing=[]
    for un,info in everyone.items():
        rngs=byuser.get(un,[])
        entry={"username":un,"name":info["name"],"roles":sorted(info["roles"]),
               "count":len(rngs),"ranges":rngs}
        (submitted if rngs else missing).append(entry)
    submitted.sort(key=lambda x:-x["count"])
    return jsonify({"ok":True,"week_start":ws,"submitted":submitted,"missing":missing,
                    "total_staff":len(everyone),"submitted_count":len(submitted)})

@app.route("/my-availability")
@req_role("host","assistant","admin","cs")
def my_availability_page():
    return MYAVAIL_HTML.replace("__NAME__",esc(session.get("name",""))).replace(
        "__NAVBAR__",_navbar("myavail")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

@app.route("/api/users/add",methods=["POST"])
@req_role("admin")
def api_add():
    d=request.get_json();u=d.get("username","").strip().lower();p=d.get("password","")
    n=_clean_name(d.get("name") or u);role=d.get("role","worker")
    if not u or not p: return jsonify({"ok":False,"error":"Required"})
    if not re.match(r'^[a-z0-9_\-]{2,32}$',u):
        return jsonify({"ok":False,"error":"Username: lowercase letters, digits, _ -, 2-32 chars"})
    if role not in ("admin","cs","worker","picker","host","assistant"):
        return jsonify({"ok":False,"error":"Invalid role"})
    # Extra roles let one person do several jobs (e.g. picker + host).
    _valid_extra={"worker","picker","cs","host","assistant"}
    extra=[r for r in (d.get("extra_roles") or []) if r in _valid_extra and r!=role]
    # Plan limit: Starter is capped at 3 users per tenant.
    _lim=_plan_user_limit(current_org())
    if _lim is not None:
        _cur=_org_user_count(current_org())
        if _cur>=_lim:
            return jsonify({"ok":False,"error":
                "Your plan allows %d users and you already have %d. Upgrade to Pro for unlimited users."%(_lim,_cur),
                "upgrade":True})
    with update_json(USERS_FILE) as users:
        if u in users: return jsonify({"ok":False,"error":"Already exists"})
        users[u]={"password":_h(p),"role":role,"name":n,"org":session.get("org",DEFAULT_ORG)}
        if extra: users[u]["extra_roles"]=extra
        # On-camera staff (host/assistant) can be limited to specific channels.
        if role in ("host","assistant") or "host" in extra or "assistant" in extra:
            ch=d.get("allowed_channels")
            if isinstance(ch,list): users[u]["allowed_channels"]=[int(x) for x in ch if str(x).isdigit()]
        # Workers automatically get a badge token for scan-to-login
        if role=="worker":
            users[u]["badge_token"]=_gen_badge_token()
        badge=users[u].get("badge_token")
    alog("user.create",u+" (role="+role+")")
    return jsonify({"ok":True,"badge_token":badge})

@app.route("/api/users/roles",methods=["POST"])
@req_role("admin")
def api_user_roles():
    """Update an existing user's primary role + extra roles."""
    d=request.get_json() or {}
    u=(d.get("username") or "").strip().lower()
    role=(d.get("role") or "").strip()
    if role not in ("admin","cs","worker","picker","host","assistant"):
        return jsonify({"ok":False,"error":"Invalid role"})
    _valid_extra={"worker","picker","cs","host","assistant"}
    extra=[r for r in (d.get("extra_roles") or []) if r in _valid_extra and r!=role]
    with update_json(USERS_FILE) as users:
        if u not in users or not _same_org_user(users,u):
            return jsonify({"ok":False,"error":"User not found"}),404
        if u=="admin" and role!="admin":
            return jsonify({"ok":False,"error":"The founding admin must stay admin"})
        users[u]["role"]=role
        if extra: users[u]["extra_roles"]=extra
        else: users[u].pop("extra_roles",None)
        # keep a badge for anyone who can work the floor
        if ("worker" in [role]+extra) and not users[u].get("badge_token"):
            users[u]["badge_token"]=_gen_badge_token()
    alog("user.roles",u+" -> "+role+("+"+",".join(extra) if extra else ""))
    return jsonify({"ok":True})

@app.route("/api/users/delete",methods=["POST"])
@req_role("admin")
def api_del():
    d=request.get_json();u=d.get("username","")
    if u=="admin": return jsonify({"ok":False,"error":"Cannot delete admin"})
    with update_json(USERS_FILE) as users:
        if u in users and _same_org_user(users,u): del users[u]
    alog("user.delete",u)
    return jsonify({"ok":True})

@app.route("/api/users/pw",methods=["POST"])
@req_role("admin")
def api_pw():
    d=request.get_json();u=d.get("username","");p=d.get("password","")
    if not p: return jsonify({"ok":False})
    with update_json(USERS_FILE) as users:
        if u not in users or not _same_org_user(users,u): return jsonify({"ok":False})
        users[u]["password"]=_h(p)
    alog("user.password_reset",u)
    return jsonify({"ok":True})

@app.route("/api/users/badge",methods=["POST"])
@req_role("admin")
def api_badge_regen():
    """Regenerate (or generate first time) a badge token for a worker.
    Use cases: lost badge, leaked token, switching from password to badge auth."""
    d=request.get_json();u=d.get("username","")
    with update_json(USERS_FILE) as users:
        if u not in users or not _same_org_user(users,u): return jsonify({"ok":False,"error":"User not found"})
        if users[u]["role"]!="worker":
            return jsonify({"ok":False,"error":"Badges are for workers only"})
        users[u]["badge_token"]=_gen_badge_token()
        tok=users[u]["badge_token"]
    return jsonify({"ok":True,"badge_token":tok})

@app.route("/api/users/badge/revoke",methods=["POST"])
@req_role("admin")
def api_badge_revoke():
    """Remove a worker's badge token (e.g. employee left). They'll need a password to log in."""
    d=request.get_json();u=d.get("username","")
    with update_json(USERS_FILE) as users:
        if u not in users or not _same_org_user(users,u): return jsonify({"ok":False,"error":"User not found"})
        if "badge_token" in users[u]: del users[u]["badge_token"]
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
    if not org_is_active(user.get("org",DEFAULT_ORG)):
        return jsonify({"ok":False,"error":"This organization is suspended. Please contact support."}),403
    session.clear()  # rotate session id to prevent fixation
    session["user"]=matched_u;session["role"]=user["role"];session["name"]=user["name"]
    session["roles"]=_effective_roles(user)
    session["org"]=user.get("org",DEFAULT_ORG)
    session["brand"]=brand_for_session(session["org"])
    return jsonify({"ok":True,"role":user["role"],"name":user["name"]})

@app.route("/badge-login")
def badge_login_page():
    return BADGE_LOGIN_HTML

@app.route("/users/badges")
@req_role("admin")
def users_badges_page():
    return USERS_BADGES_HTML.replace("__NAME__",esc(session.get("name",""))).replace("__NAVBAR__",_navbar("badges")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

# ══════════════════════════════════════════════════════════
# BILLING — paywall, subscription status, and the public lead form
# ══════════════════════════════════════════════════════════
SALES_EMAIL=os.environ.get("SALES_EMAIL","sales@liveopshub.com")

_BILLING_HEADLINE={
    "trial_expired":"Your trial has ended",
    "period_ended":"Time to renew",
    "unpaid":"Outstanding balance",
    "suspended":"Account suspended",
    "no_subscription":"Choose a plan to get started",
    "ok":"Your plan",
}
_BILLING_STATE_LABEL={
    "trial_expired":("warn","TRIAL ENDED"),
    "period_ended":("warn","RENEWAL DUE"),
    "unpaid":("bad","PAYMENT DUE"),
    "suspended":("bad","SUSPENDED"),
    "no_subscription":("warn","NO PLAN"),
    "ok":("ok","ACTIVE"),
}
# Shown on the billing screen so customers know how to actually pay you.
PAYMENT_INSTRUCTIONS=os.environ.get("PAYMENT_INSTRUCTIONS",
    "Pick a plan below and we'll email you an invoice. Access is restored the moment payment clears.")

@app.route("/billing")
@req_login
def billing_page():
    """Paywall / plan chooser. Reachable even when the tenant is locked."""
    allowed,state,info=org_access(current_org())
    if allowed: state="ok"
    cls,label=_BILLING_STATE_LABEL.get(state,("warn",state.upper()))
    msg=_BILLING_MSG.get(state,"")
    if state=="ok":
        b=info or {}
        if (b.get("sub_status") or "")=="trialing" and b.get("trial_days_left") is not None:
            msg="You're on a free trial — %d day(s) left. Pick a plan any time and we'll invoice you." % b["trial_days_left"]
            label="TRIAL · %d DAYS LEFT" % b["trial_days_left"]; cls="warn"
        elif b.get("current_period_end"):
            msg="Your %s plan is active through %s." % (
                PLANS.get(b.get("plan") or "", PLANS["starter"])["label"],
                (b.get("current_period_end") or "")[:10])
        else:
            msg="Your plan is active. Thanks for using LiveOpsHub!"
    return (BILLING_HTML.replace("__FONT__",_FONT)
            .replace("__STATE_CLS__",cls).replace("__STATE_LABEL__",label)
            .replace("__HEADLINE__",esc(_BILLING_HEADLINE.get(state,"Billing")))
            .replace("__MESSAGE__",esc(msg))
            .replace("__PAY_INSTRUCTIONS__",esc(PAYMENT_INSTRUCTIONS))
            .replace("__SALES_EMAIL__",esc(SALES_EMAIL)))

@app.route("/api/billing/status")
@req_login
def api_billing_status():
    allowed,state,info=org_access(current_org())
    b=info or {}
    return jsonify({"ok":True,"allowed":allowed,"state":state,
        "plan":b.get("plan"),"sub_status":b.get("sub_status"),
        "trial_ends_at":b.get("trial_ends_at"),
        "trial_days_left":b.get("trial_days_left"),
        "current_period_end":b.get("current_period_end"),
        "plans":PLANS})

# ── Public lead capture (no auth) ─────────────────────────────────────────────
@app.route("/demo")
def demo_page():
    return DEMO_HTML.replace("__FONT__",_FONT)

_LEAD_MAX=2000
MARKETING_ORIGIN=os.environ.get("MARKETING_ORIGIN","")   # e.g. https://liveopshub.com

@app.route("/api/lead",methods=["POST","OPTIONS"])
def api_lead():
    # CORS preflight/response so the static marketing site can submit the form.
    if request.method=="OPTIONS":
        r=Response("",204)
        if MARKETING_ORIGIN:
            r.headers["Access-Control-Allow-Origin"]=MARKETING_ORIGIN
            r.headers["Access-Control-Allow-Headers"]="Content-Type"
            r.headers["Access-Control-Allow-Methods"]="POST, OPTIONS"
            r.headers["Access-Control-Max-Age"]="86400"
        return r
    return _api_lead_create()

def _api_lead_create():
    """Public 'request a demo' submission. Rate-limited by IP to stop spam."""
    d=request.get_json(silent=True) or {}
    company=(d.get("company") or "").strip()[:120]
    # The marketing site posts `name`; the in-app form posts `contact_name`.
    name=(d.get("contact_name") or d.get("name") or "").strip()[:120]
    email=(d.get("email") or "").strip()[:160]
    if not company or not name or not email or "@" not in email:
        return jsonify({"ok":False,"error":"Company, name and a valid email are required."})
    ip=request.remote_addr or "?"
    if not _rate_ok("lead:"+ip, limit=5, window=3600):
        return jsonify({"ok":False,"error":"Too many requests — please try again later."})
    c=pdb()
    c.execute("""INSERT INTO leads(company,contact_name,email,phone,platforms,volume,message)
                 VALUES(?,?,?,?,?,?,?)""",
              (company,name,email,(d.get("phone") or "").strip()[:60],
               (d.get("platforms") or "").strip()[:60],(d.get("volume") or "").strip()[:60],
               (d.get("message") or "").strip()[:_LEAD_MAX]))
    c.commit();c.close()
    print("NEW LEAD: %s / %s / %s" % (company,name,email),flush=True)
    resp=jsonify({"ok":True})
    if MARKETING_ORIGIN:
        resp.headers["Access-Control-Allow-Origin"]=MARKETING_ORIGIN
    return resp

@app.route("/api/leads")
@req_super
def api_leads_list():
    c=pdb();rows=[dict(r) for r in c.execute(
        "SELECT * FROM leads ORDER BY created_at DESC LIMIT 500").fetchall()];c.close()
    return jsonify({"ok":True,"leads":rows})

@app.route("/api/leads/<int:lid>",methods=["POST"])
@req_super
def api_lead_update(lid):
    """Update a lead's status/notes as sales works it."""
    d=request.get_json() or {}
    st=(d.get("status") or "").strip()
    if st and st not in ("new","contacted","trial","won","lost"):
        return jsonify({"ok":False,"error":"Invalid status"})
    c=pdb()
    if st: c.execute("UPDATE leads SET status=? WHERE id=?",(st,lid))
    if d.get("notes") is not None:
        c.execute("UPDATE leads SET notes=? WHERE id=?",((d.get("notes") or "")[:_LEAD_MAX],lid))
    if d.get("converted_org"):
        c.execute("UPDATE leads SET converted_org=?, status='trial' WHERE id=?",
                  ((d.get("converted_org") or "")[:40],lid))
    c.commit();c.close()
    plog(session.get("user"),"lead_update","","lead #%d"%lid)
    return jsonify({"ok":True})

# ── Super-admin subscription controls ─────────────────────────────────────────
@app.route("/api/orgs/<org_id>/subscription",methods=["POST"])
@req_super
def api_org_subscription(org_id):
    """Start/extend a trial, change plan, or mark a tenant active/unpaid by hand.
    Sales-led flow: this is how a trial gets opened after the sales call."""
    d=request.get_json() or {}
    c=pdb()
    if not c.execute("SELECT 1 FROM organizations WHERE org_id=?",(org_id,)).fetchone():
        c.close(); return jsonify({"ok":False,"error":"Unknown org"})
    action=(d.get("action") or "").strip()
    if action=="start_trial":
        try: days=max(1,min(90,int(d.get("days",TRIAL_DAYS))))
        except Exception: days=TRIAL_DAYS
        ends=(datetime.now()+timedelta(days=days)).isoformat(timespec="seconds")
        c.execute("UPDATE organizations SET sub_status='trialing', trial_ends_at=? WHERE org_id=?",(ends,org_id))
        detail="trial %d days (until %s)"%(days,ends[:10])
    elif action=="extend_trial":
        try: days=max(1,min(90,int(d.get("days",7))))
        except Exception: days=7
        row=c.execute("SELECT trial_ends_at FROM organizations WHERE org_id=?",(org_id,)).fetchone()
        base=_parse_dt(row["trial_ends_at"]) or datetime.now()
        if base<datetime.now(): base=datetime.now()
        ends=(base+timedelta(days=days)).isoformat(timespec="seconds")
        c.execute("UPDATE organizations SET sub_status='trialing', trial_ends_at=? WHERE org_id=?",(ends,org_id))
        detail="extended %d days (until %s)"%(days,ends[:10])
    elif action=="set_plan":
        plan=(d.get("plan") or "").strip()
        if plan not in PLANS:
            c.close(); return jsonify({"ok":False,"error":"Unknown plan"})
        c.execute("UPDATE organizations SET plan=? WHERE org_id=?",(plan,org_id))
        detail="plan=%s"%plan
    elif action=="set_internal":
        val=1 if d.get("internal") else 0
        c.execute("UPDATE organizations SET internal=? WHERE org_id=?",(val,org_id))
        detail="internal=%d"%val
    elif action=="set_status":
        st=(d.get("sub_status") or "").strip()
        if st not in ("active","trialing","past_due","canceled","none"):
            c.close(); return jsonify({"ok":False,"error":"Invalid status"})
        c.execute("UPDATE organizations SET sub_status=? WHERE org_id=?",(st,org_id))
        detail="sub_status=%s"%st
    else:
        c.close(); return jsonify({"ok":False,"error":"Unknown action"})
    c.commit()
    row=dict(c.execute("SELECT * FROM organizations WHERE org_id=?",(org_id,)).fetchone())
    c.close()
    plog("org.subscription","%s: %s"%(org_id,detail),org_id)
    return jsonify({"ok":True,"org":row})

# ── Storage cost per tenant ───────────────────────────────────────────────────
# Cloudflare R2: $0.015 per GB-month, no egress charge, 10 GB free per account.
R2_GB_MONTH_USD=float(os.environ.get("R2_GB_MONTH_USD","0.015"))
R2_FREE_GB=float(os.environ.get("R2_FREE_GB","10"))
_STORAGE_KINDS=("videos","photos","labels","documents","invoices","hire_uploads")
_storage_cache={}   # org -> (ts, payload)
_STORAGE_TTL=int(os.environ.get("STORAGE_CACHE_SECONDS","1800"))

def _org_storage(org, force=False):
    """Bytes stored per tenant, broken down by kind. Listing costs a Class A op and
    is slow with many objects, so results are cached for 30 minutes."""
    hit=_storage_cache.get(org)
    if hit and not force and time.time()-hit[0]<_STORAGE_TTL:
        return hit[1]
    by={k:{"count":0,"bytes":0} for k in _STORAGE_KINDS}
    if r2:
        prefixes=[(k, "%s/%s/"%(org,k)) for k in _STORAGE_KINDS]
        # The founding tenant also owns the pre-namespacing bare prefixes.
        if org==DEFAULT_ORG:
            prefixes+=[(k,"%s/"%k) for k in ("videos","photos","documents","labels")]
        try:
            pg=r2.get_paginator("list_objects_v2")
            for kind,pref in prefixes:
                for page in pg.paginate(Bucket=R2_BUCKET,Prefix=pref):
                    for obj in page.get("Contents",[]):
                        by[kind]["count"]+=1; by[kind]["bytes"]+=obj["Size"]
        except Exception as e:
            print("storage list failed for %s: %s"%(org,e),flush=True)
    else:
        # Local storage mode — walk the tenant's folders.
        for kind in _STORAGE_KINDS:
            d=org_path(org,kind)
            if not os.path.isdir(d): continue
            for root,_dirs,files in os.walk(d):
                for f in files:
                    try:
                        by[kind]["count"]+=1
                        by[kind]["bytes"]+=os.path.getsize(os.path.join(root,f))
                    except Exception: pass
    total=sum(v["bytes"] for v in by.values())
    gb=total/(1024.0**3)
    payload={"org_id":org,"by_kind":by,"total_bytes":total,"total_gb":round(gb,3),
             "video_bytes":by["videos"]["bytes"],"video_count":by["videos"]["count"],
             "cost_month":round(gb*R2_GB_MONTH_USD,2),"rate":R2_GB_MONTH_USD}
    _storage_cache[org]=(time.time(),payload)
    return payload

@app.route("/api/orgs/storage")
@req_super
def api_orgs_storage():
    """Storage footprint + estimated R2 cost per tenant, with the margin impact."""
    force=bool(request.args.get("refresh"))
    c=pdb(); orgs=[dict(r) for r in c.execute(
        "SELECT org_id,plan,COALESCE(internal,0) AS internal FROM organizations").fetchall()]; c.close()
    out=[]; grand=0
    for o in orgs:
        s=_org_storage(o["org_id"],force=force)
        s["internal"]=bool(o.get("internal"))
        # Internal accounts generate no revenue, so a margin % would be meaningless.
        price=0 if o.get("internal") else (PLANS.get(o.get("plan") or "", PLANS["starter"]).get("price") or 0)
        s["plan_price"]=price
        s["cost_pct_of_revenue"]=round(100.0*s["cost_month"]/price,1) if price else None
        grand+=s["total_bytes"]
        out.append(s)
    gb=grand/(1024.0**3)
    billable=max(0.0, gb-R2_FREE_GB)
    return jsonify({"ok":True,"storage":out,"rate":R2_GB_MONTH_USD,"free_gb":R2_FREE_GB,
        "total_gb":round(gb,2),"billable_gb":round(billable,2),
        "total_cost_month":round(billable*R2_GB_MONTH_USD,2),
        "cached_seconds":_STORAGE_TTL})

@app.route("/api/orgs/usage")
@req_super
def api_orgs_usage():
    """Per-tenant usage against plan limits — powers the usage bars in the console.
    Shows who's near their cap (upsell) and who's barely active (churn risk)."""
    today=datetime.now().strftime("%Y-%m-%d")
    d7=(datetime.now()-timedelta(days=7)).strftime("%Y-%m-%d")
    d30=(datetime.now()-timedelta(days=30)).strftime("%Y-%m-%d")
    c=pdb(); orgs=[dict(r) for r in c.execute("SELECT * FROM organizations ORDER BY company_name").fetchall()]; c.close()
    out=[]
    for o in orgs:
        org=o["org_id"]
        plan=PLANS.get(o.get("plan") or "", PLANS["starter"])
        trialing=(o.get("sub_status") or "")=="trialing"
        internal=bool(o.get("internal"))
        users=_org_user_count(org)
        u_lim=None if (trialing or internal) else plan.get("max_users")
        o_lim=None if (trialing or internal) else plan.get("max_orders_day")
        today_n=w7=w30=0; last=None; peak=0
        try:
            sc=sdb(org)
            today_n=sc.execute("SELECT COUNT(*) FROM shipments WHERE substr(COALESCE(show_date,''),1,10)=?",(today,)).fetchone()[0]
            w7  =sc.execute("SELECT COUNT(*) FROM shipments WHERE substr(COALESCE(show_date,''),1,10)>=?",(d7,)).fetchone()[0]
            w30 =sc.execute("SELECT COUNT(*) FROM shipments WHERE substr(COALESCE(show_date,''),1,10)>=?",(d30,)).fetchone()[0]
            r=sc.execute("SELECT MAX(substr(COALESCE(show_date,''),1,10)) FROM shipments").fetchone()
            last=r[0] if r else None
            pk=sc.execute("""SELECT MAX(n) FROM (SELECT COUNT(*) n FROM shipments
                             WHERE substr(COALESCE(show_date,''),1,10)>=?
                             GROUP BY substr(COALESCE(show_date,''),1,10))""",(d30,)).fetchone()
            peak=(pk[0] or 0) if pk else 0
            sc.close()
        except Exception as e:
            print("usage read failed for %s: %s"%(org,e),flush=True)
        # Headline % = the binding constraint (whichever cap they're closest to).
        pcts=[]
        if u_lim: pcts.append(round(100.0*users/u_lim))
        if o_lim: pcts.append(round(100.0*peak/o_lim))
        pct=max(pcts) if pcts else None
        allowed,state,_=org_access(org)
        out.append({"org_id":org,"company_name":o.get("company_name"),
            "plan":o.get("plan"),"plan_label":plan["label"],"internal":internal,
            "sub_status":o.get("sub_status"),"state":state,"allowed":allowed,
            "trial_ends_at":o.get("trial_ends_at"),"current_period_end":o.get("current_period_end"),
            "users":users,"users_limit":u_lim,
            "orders_today":today_n,"orders_limit":o_lim,
            "orders_7d":w7,"orders_30d":w30,"peak_day_30d":peak,
            "last_activity":last,"usage_pct":pct})
    return jsonify({"ok":True,"usage":out})

# ── Manual billing: record a payment, which is what grants access ─────────────
@app.route("/api/orgs/<org_id>/payment",methods=["POST"])
@req_super
def api_org_payment(org_id):
    """Record a payment received (bank transfer / invoice / whatever) and extend the
    tenant's paid period. This is the manual-billing equivalent of a Stripe webhook."""
    d=request.get_json() or {}
    c=pdb()
    row=c.execute("SELECT plan,current_period_end FROM organizations WHERE org_id=?",(org_id,)).fetchone()
    if not row:
        c.close(); return jsonify({"ok":False,"error":"Unknown org"})
    try: months=max(1,min(36,int(d.get("months",1))))
    except Exception: months=1
    plan=(d.get("plan") or row["plan"] or "starter")
    if plan not in PLANS: plan="starter"
    try: amount=float(d.get("amount") or 0) or float(PLANS[plan].get("price") or 0)*months
    except Exception: amount=0.0
    # Extend from the current period end when it's still in the future, else from today.
    base=_parse_dt(row["current_period_end"]) or datetime.now()
    if base<datetime.now(): base=datetime.now()
    start=datetime.now().isoformat(timespec="seconds")
    end=(base+timedelta(days=30*months)).isoformat(timespec="seconds")
    c.execute("""INSERT INTO payments(org_id,amount,currency,plan,months,period_start,period_end,
                                      method,reference,notes,recorded_by)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
              (org_id,amount,(d.get("currency") or "USD")[:8],plan,months,start,end,
               (d.get("method") or "manual")[:40],(d.get("reference") or "")[:80],
               (d.get("notes") or "")[:500],session.get("user","")[:60]))
    c.execute("""UPDATE organizations SET sub_status='active', plan=?, current_period_end=?
                 WHERE org_id=?""",(plan,end,org_id))
    c.execute("UPDATE billing_requests SET handled=1 WHERE org_id=? AND handled=0",(org_id,))
    c.commit()
    org=dict(c.execute("SELECT * FROM organizations WHERE org_id=?",(org_id,)).fetchone())
    c.close()
    plog(session.get("user"),"payment_recorded",org_id,
         "%s %.2f for %d month(s) → paid until %s"%(plan,amount,months,end[:10]))
    return jsonify({"ok":True,"org":org,"period_end":end})

@app.route("/api/orgs/<org_id>/payments")
@req_super
def api_org_payments(org_id):
    c=pdb();rows=[dict(r) for r in c.execute(
        "SELECT * FROM payments WHERE org_id=? ORDER BY created_at DESC LIMIT 200",(org_id,)).fetchall()];c.close()
    return jsonify({"ok":True,"payments":rows})

@app.route("/api/billing/request-plan",methods=["POST"])
@req_login
def api_billing_request_plan():
    """A locked/trialing tenant asks for a plan; super-admin sees it and invoices them."""
    d=request.get_json() or {}
    plan=(d.get("plan") or "").strip()
    if plan not in PLANS:
        return jsonify({"ok":False,"error":"Unknown plan"})
    org=current_org()
    c=pdb()
    c.execute("INSERT INTO billing_requests(org_id,plan,requested_by) VALUES(?,?,?)",
              (org,plan,session.get("user","")[:60]))
    c.commit();c.close()
    print("PLAN REQUEST: org=%s plan=%s by=%s"%(org,plan,session.get("user","")),flush=True)
    plog(session.get("user"),"plan_requested",org,plan)
    return jsonify({"ok":True,"plan":plan,"sales_email":SALES_EMAIL})

@app.route("/api/billing/requests")
@req_super
def api_billing_requests():
    c=pdb();rows=[dict(r) for r in c.execute(
        """SELECT b.*, o.company_name FROM billing_requests b
           LEFT JOIN organizations o ON o.org_id=b.org_id
           ORDER BY b.handled, b.created_at DESC LIMIT 200""").fetchall()];c.close()
    return jsonify({"ok":True,"requests":rows})

# ══════════════════════════════════════════════════════════
# PLATFORM / TENANT MANAGEMENT — super-admin only (control plane)
# ══════════════════════════════════════════════════════════
_ORG_ID_RE=re.compile(r'^[a-z0-9][a-z0-9\-]{1,30}$')

@app.route("/api/orgs")
@req_super
def api_orgs_list():
    """All tenant organizations + a live user count per org."""
    c=pdb(); rows=[dict(r) for r in c.execute(
        "SELECT * FROM organizations ORDER BY created_at").fetchall()]; c.close()
    users=ldj(USERS_FILE) if os.path.exists(USERS_FILE) else {}
    counts={}
    for _,info in users.items():
        o=info.get("org",DEFAULT_ORG); counts[o]=counts.get(o,0)+1
    for r in rows:
        r["user_count"]=counts.get(r["org_id"],0)
        r["is_default"]=(r["org_id"]==DEFAULT_ORG)
    return jsonify({"ok":True,"orgs":rows,"default_org":DEFAULT_ORG})

@app.route("/api/orgs/create",methods=["POST"])
@req_super
def api_orgs_create():
    """Create a new tenant: register it, provision its isolated data, and create
    its first admin user. Returns the admin's one-time password."""
    d=request.get_json() or {}
    org_id=(d.get("org_id") or "").strip().lower()
    company=(d.get("company_name") or "").strip()
    admin_user=(d.get("admin_username") or "").strip().lower()
    admin_pw=(d.get("admin_password") or "").strip()
    if not _ORG_ID_RE.match(org_id):
        return jsonify({"ok":False,"error":"Org ID: lowercase letters/digits/-, 2-31 chars, must start alphanumeric"})
    if not company:
        return jsonify({"ok":False,"error":"Company name is required"})
    if not re.match(r'^[a-z0-9_\-]{2,32}$',admin_user):
        return jsonify({"ok":False,"error":"Admin username: lowercase letters, digits, _ -, 2-32 chars"})
    # Contact details for the account owner (who we invoice and call).
    contact_email=(d.get("contact_email") or "").strip()[:160]
    contact_phone=(d.get("contact_phone") or "").strip()[:60]
    if contact_email and "@" not in contact_email:
        return jsonify({"ok":False,"error":"That contact email doesn't look valid"})
    # This account can see every order and customer address in the tenant — don't let
    # it be created with a throwaway password.
    if not admin_pw:
        admin_pw=_gen_pw()
    elif len(admin_pw)<8:
        return jsonify({"ok":False,"error":"Admin password must be at least 8 characters (or leave it blank to auto-generate a strong one)"})
    # org_id must be unique
    c=pdb()
    if c.execute("SELECT 1 FROM organizations WHERE org_id=?",(org_id,)).fetchone():
        c.close(); return jsonify({"ok":False,"error":"That Org ID already exists"})
    # username must be globally unique (usernames are global across tenants)
    users=ldj(USERS_FILE) if os.path.exists(USERS_FILE) else {}
    if admin_user in users:
        c.close(); return jsonify({"ok":False,"error":"That admin username is already taken (usernames are global)"})
    # 1) register the tenant
    # New tenants start on a 7-day trial (sales-led: opened after the sales call).
    _plan=(d.get("plan") or "starter")
    if _plan not in PLANS: _plan="starter"
    try: _tdays=max(0,min(90,int(d.get("trial_days",TRIAL_DAYS))))
    except Exception: _tdays=TRIAL_DAYS
    _tends=(datetime.now()+timedelta(days=_tdays)).isoformat(timespec="seconds")
    c.execute("""INSERT INTO organizations(org_id,company_name,brand_mark,brand_sub,brand_color,logo_url,plan,
                                           sub_status,trial_ends_at,contact_email,contact_phone)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
              (org_id,company,(d.get("brand_mark") or company[:12] or "BRAND").upper(),
               (d.get("brand_sub") or "Employee Hub"),(d.get("brand_color") or "#d9748f"),
               (d.get("logo_url") or ""),_plan,
               ("trialing" if _tdays>0 else "none"), (_tends if _tdays>0 else None),
               contact_email or None, contact_phone or None))
    c.commit(); c.close()
    # 2) provision its isolated data folders/DBs + seed defaults
    try:
        provision_org(org_id)
        _seed_default_workflow_if_missing(org_id)
    except Exception as e:
        print("provision error for new org",org_id,":",e,flush=True)
    # 3) create its first admin user
    with update_json(USERS_FILE) as uu:
        uu[admin_user]={"password":_h(admin_pw),"role":"admin",
                        "name":_clean_name(d.get("admin_name") or "Admin"),"org":org_id}
    plog(session.get("user"),"org_create",org_id,"company="+company+" admin="+admin_user)
    return jsonify({"ok":True,"org_id":org_id,"admin_username":admin_user,"admin_password":admin_pw})

@app.route("/api/orgs/toggle",methods=["POST"])
@req_super
def api_orgs_toggle():
    """Suspend or reactivate a tenant. Suspended tenants' users cannot log in."""
    d=request.get_json() or {}
    org_id=(d.get("org_id") or "").strip().lower()
    active=1 if d.get("active") else 0
    if org_id==DEFAULT_ORG:
        return jsonify({"ok":False,"error":"The founding tenant cannot be suspended"})
    c=pdb()
    if not c.execute("SELECT 1 FROM organizations WHERE org_id=?",(org_id,)).fetchone():
        c.close(); return jsonify({"ok":False,"error":"Org not found"})
    c.execute("UPDATE organizations SET active=? WHERE org_id=?",(active,org_id)); c.commit(); c.close()
    plog(session.get("user"),"org_"+("activate" if active else "suspend"),org_id,"")
    return jsonify({"ok":True,"org_id":org_id,"active":bool(active)})

@app.route("/admin/organizations")
@req_super
def organizations_page():
    return ORGANIZATIONS_HTML.replace("__NAME__",esc(session.get("name",""))).replace(
        "__NAVBAR__",_navbar("organizations")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

@app.route("/api/impersonate",methods=["POST"])
@req_super
def api_impersonate():
    """Enter a tenant as a support admin. Keeps a marker so the UI shows a banner
    and the session can be restored to the platform owner on exit."""
    d=request.get_json() or {}
    org_id=(d.get("org_id") or "").strip().lower()
    if org_id in ("",PLATFORM_ORG):
        return jsonify({"ok":False,"error":"Pick a tenant"})
    o=org_get(org_id)
    if not o or o.get("org_id")!=org_id:
        return jsonify({"ok":False,"error":"Org not found"})
    owner=session.get("user")
    plog(owner,"impersonate_enter",org_id,"support session started")
    # Act as that tenant's admin, remembering who we really are.
    session["impersonator"]=owner
    session["role"]="admin"; session["roles"]=["admin"]
    session["org"]=org_id
    session["name"]="Support · "+(o.get("company_name") or org_id)
    session["brand"]=brand_for_session(org_id)
    return jsonify({"ok":True,"redirect":"/home"})

@app.route("/api/impersonate/exit",methods=["POST"])
@req_login
def api_impersonate_exit():
    """Leave support mode and restore the platform-owner session."""
    owner=session.get("impersonator")
    if not owner:
        return jsonify({"ok":False,"error":"Not in support mode"})
    plog(owner,"impersonate_exit",session.get("org",""),"support session ended")
    session.pop("impersonator",None)
    session["user"]=owner
    session["role"]="superadmin"; session["roles"]=["superadmin"]
    session["org"]=PLATFORM_ORG
    session["name"]="Platform Owner"
    session["brand"]=brand_for_session(PLATFORM_ORG)
    return jsonify({"ok":True,"redirect":"/admin/organizations"})

# ══════════════════════════════════════════════════════════
# SUPPORT TICKETS — customers open them, the platform owner answers.
# Stored in platform.db (cross-tenant), strictly scoped by org for customers.
# ══════════════════════════════════════════════════════════
TICKET_CATEGORIES=[
    ("import","Importing orders (TikTok / Whatnot CSV)"),
    ("packing","Packing / video recording"),
    ("picking","Picking / barcode scanning"),
    ("shipping","Shipping labels & tracking"),
    ("giveaways","Giveaways"),
    ("inventory","Inventory / SKUs / catalog"),
    ("analytics","Analytics / reports"),
    ("access","Login / users / badges / permissions"),
    ("billing","Billing / account"),
    ("other","Something else"),
]
_TICKET_CAT_KEYS={k for k,_ in TICKET_CATEGORIES}
TICKET_PRIORITIES=["low","normal","high","urgent"]
TICKET_STATUSES=["open","pending","resolved","closed"]

def _is_support_session():
    """True when the caller is the platform owner acting as support (not
    impersonating a tenant)."""
    return session.get("role")=="superadmin" and not session.get("impersonator")

def _ticket_get(tid):
    c=pdb(); r=c.execute("SELECT * FROM tickets WHERE id=?",(tid,)).fetchone(); c.close()
    return dict(r) if r else None

def _ticket_visible(t):
    """Support sees all; a customer only sees tickets in their own org."""
    if not t: return False
    if _is_support_session(): return True
    return t.get("org_id")==session.get("org")

@app.route("/api/support/tickets",methods=["POST"])
@req_login
def api_ticket_create():
    d=request.get_json() or {}
    org=session.get("org")
    if not org or org==PLATFORM_ORG:
        return jsonify({"ok":False,"error":"Open a tenant first"})
    subject=(d.get("subject") or "").strip()[:200]
    body=(d.get("body") or "").strip()
    if not subject or not body:
        return jsonify({"ok":False,"error":"Please add a subject and describe the issue"})
    cat=(d.get("category") or "other").strip()
    if cat not in _TICKET_CAT_KEYS: cat="other"
    prio=(d.get("priority") or "normal").strip()
    if prio not in TICKET_PRIORITIES: prio="normal"
    # Capture diagnostic context automatically + the structured intake fields.
    ctx={
        "steps":(d.get("steps") or "").strip()[:2000],
        "when":(d.get("when") or "").strip()[:300],
        "url":(d.get("url") or "").strip()[:500],
        "user_agent":(request.headers.get("User-Agent") or "")[:400],
        "role":session.get("role"),
        "reported_by_role":session.get("role"),
    }
    who=session.get("user"); who_name=session.get("name") or who
    c=pdb()
    cur=c.execute("""INSERT INTO tickets(org_id,created_by,created_by_name,category,subject,priority,status,context,last_actor)
                     VALUES(?,?,?,?,?,?, 'open', ?, ?)""",
                  (org,who,who_name,cat,subject,prio,json.dumps(ctx),who))
    tid=cur.lastrowid
    m=c.execute("""INSERT INTO ticket_messages(ticket_id,author,author_name,author_side,body)
                 VALUES(?,?,?,'customer',?)""",(tid,who,who_name,body))
    mid=m.lastrowid
    c.commit(); c.close()
    return jsonify({"ok":True,"id":tid,"message_id":mid})

@app.route("/api/support/tickets")
@req_login
def api_tickets_list():
    c=pdb()
    if _is_support_session():
        st=(request.args.get("status") or "").strip()
        org=(request.args.get("org") or "").strip()
        q="SELECT * FROM tickets"; where=[]; args=[]
        if st in TICKET_STATUSES: where.append("status=?"); args.append(st)
        if org: where.append("org_id=?"); args.append(org)
        if where: q+=" WHERE "+" AND ".join(where)
        q+=" ORDER BY (status IN ('resolved','closed')), updated_at DESC"
        rows=[dict(r) for r in c.execute(q,tuple(args)).fetchall()]
    else:
        org=session.get("org")
        rows=[dict(r) for r in c.execute(
            "SELECT * FROM tickets WHERE org_id=? ORDER BY (status IN ('resolved','closed')), updated_at DESC",(org,)).fetchall()]
    # attach company names for the support view
    comp={}
    if _is_support_session():
        for o in c.execute("SELECT org_id,company_name FROM organizations").fetchall():
            comp[o["org_id"]]=o["company_name"]
    c.close()
    for r in rows:
        r["company"]=comp.get(r["org_id"],r["org_id"])
    return jsonify({"ok":True,"tickets":rows,"is_support":_is_support_session(),
                    "categories":dict(TICKET_CATEGORIES)})

@app.route("/api/support/tickets/<int:tid>")
@req_login
def api_ticket_get(tid):
    t=_ticket_get(tid)
    if not _ticket_visible(t): return jsonify({"ok":False,"error":"Not found"}),404
    c=pdb()
    msgs=[dict(m) for m in c.execute(
        "SELECT * FROM ticket_messages WHERE ticket_id=? ORDER BY id",(tid,)).fetchall()]
    atts=[dict(a) for a in c.execute(
        "SELECT id,message_id,filename,mime FROM ticket_attachments WHERE ticket_id=? ORDER BY id",(tid,)).fetchall()]
    by_msg={}
    for a in atts: by_msg.setdefault(a["message_id"],[]).append(a)
    for m in msgs: m["attachments"]=by_msg.get(m["id"],[])
    o=c.execute("SELECT company_name FROM organizations WHERE org_id=?",(t["org_id"],)).fetchone()
    c.close()
    t["company"]=o["company_name"] if o else t["org_id"]
    try: t["context"]=json.loads(t.get("context") or "{}")
    except Exception: t["context"]={}
    return jsonify({"ok":True,"ticket":t,"messages":msgs,"is_support":_is_support_session(),
                    "categories":dict(TICKET_CATEGORIES)})

@app.route("/api/support/tickets/<int:tid>/reply",methods=["POST"])
@req_login
def api_ticket_reply(tid):
    t=_ticket_get(tid)
    if not _ticket_visible(t): return jsonify({"ok":False,"error":"Not found"}),404
    body=((request.get_json() or {}).get("body") or "").strip()
    if not body: return jsonify({"ok":False,"error":"Write a message"})
    support=_is_support_session()
    who=session.get("user"); who_name=("Support" if support else (session.get("name") or who))
    new_status="pending" if support else "open"
    now=datetime.now().isoformat(timespec="seconds")
    c=pdb()
    m=c.execute("""INSERT INTO ticket_messages(ticket_id,author,author_name,author_side,body)
                 VALUES(?,?,?,?,?)""",(tid,who,who_name,"support" if support else "customer",body))
    mid=m.lastrowid
    # Don't resurrect a closed ticket unless the customer reopens by replying.
    if t["status"]=="closed" and support:
        new_status="closed"
    c.execute("UPDATE tickets SET status=?,updated_at=?,last_actor=? WHERE id=?",(new_status,now,who,tid))
    c.commit(); c.close()
    return jsonify({"ok":True,"message_id":mid})

_TICKET_ATT_EXT={"png","jpg","jpeg","webp","gif","pdf"}
_TICKET_ATT_MAX=10*1024*1024   # 10 MB per attachment

@app.route("/api/support/messages/<int:mid>/attachment",methods=["POST"])
@req_login
def api_ticket_attach(mid):
    """Attach a screenshot/file to a ticket message (customer or support)."""
    c=pdb()
    m=c.execute("SELECT ticket_id FROM ticket_messages WHERE id=?",(mid,)).fetchone()
    c.close()
    if not m: return jsonify({"ok":False,"error":"Message not found"}),404
    tid=m["ticket_id"]
    t=_ticket_get(tid)
    if not _ticket_visible(t): return jsonify({"ok":False,"error":"Not found"}),404
    f=request.files.get("file")
    if not f or not f.filename: return jsonify({"ok":False,"error":"Pick a file"})
    ext=f.filename.rsplit(".",1)[-1].lower() if "." in f.filename else ""
    if ext not in _TICKET_ATT_EXT:
        return jsonify({"ok":False,"error":"Use an image (PNG/JPG/WEBP/GIF) or a PDF"})
    data=f.read()
    if len(data)>_TICKET_ATT_MAX:
        return jsonify({"ok":False,"error":"File too large (max 10 MB)"})
    fname=secure_filename(f.filename) or ("file."+ext)
    key="support/%d/%s_%s"%(tid,secrets.token_hex(4),fname)
    if r2:
        r2.put_object(Bucket=R2_BUCKET,Key=key,Body=data,
                      ContentType=f.mimetype or "application/octet-stream")
    else:
        p=os.path.join(DATA_DIR,"support",str(tid)); os.makedirs(p,exist_ok=True)
        key=os.path.basename(key)
        with open(os.path.join(p,key),"wb") as fh: fh.write(data)
    c=pdb()
    cur=c.execute("""INSERT INTO ticket_attachments(ticket_id,message_id,filename,storage_key,mime,size_bytes)
                     VALUES(?,?,?,?,?,?)""",
                  (tid,mid,fname,key,f.mimetype or "",len(data)))
    aid=cur.lastrowid; c.commit(); c.close()
    return jsonify({"ok":True,"id":aid,"filename":fname})

@app.route("/api/support/attachment/<int:aid>")
@req_login
def api_ticket_attachment_file(aid):
    c=pdb()
    a=c.execute("SELECT * FROM ticket_attachments WHERE id=?",(aid,)).fetchone()
    c.close()
    if not a: return ("",404)
    t=_ticket_get(a["ticket_id"])
    if not _ticket_visible(t): return ("",404)
    key=a["storage_key"]
    if r2 and key.startswith("support/"):
        try:
            url=r2.generate_presigned_url("get_object",
                Params={"Bucket":R2_BUCKET,"Key":key},ExpiresIn=R2_PRESIGN_TTL)
            return redirect(url)
        except Exception: return ("",404)
    p=os.path.join(DATA_DIR,"support",str(a["ticket_id"]),key)
    if not os.path.exists(p): return ("",404)
    return send_file(p)

@app.route("/api/support/tickets/<int:tid>/status",methods=["POST"])
@req_login
def api_ticket_status(tid):
    t=_ticket_get(tid)
    if not _ticket_visible(t): return jsonify({"ok":False,"error":"Not found"}),404
    st=((request.get_json() or {}).get("status") or "").strip()
    if st not in TICKET_STATUSES: return jsonify({"ok":False,"error":"Bad status"})
    # Customers may only close/reopen their own tickets; support can set any status.
    if not _is_support_session() and st not in ("closed","open"):
        return jsonify({"ok":False,"error":"Not allowed"}),403
    now=datetime.now().isoformat(timespec="seconds")
    c=pdb(); c.execute("UPDATE tickets SET status=?,updated_at=? WHERE id=?",(st,now,tid)); c.commit(); c.close()
    return jsonify({"ok":True})

@app.route("/api/support/open-count")
@req_login
def api_ticket_open_count():
    c=pdb()
    if _is_support_session():
        n=c.execute("SELECT COUNT(*) n FROM tickets WHERE status IN ('open','pending')").fetchone()["n"]
    else:
        org=session.get("org")
        n=c.execute("SELECT COUNT(*) n FROM tickets WHERE org_id=? AND status IN ('open','pending')",(org,)).fetchone()["n"]
    c.close()
    return jsonify({"ok":True,"count":n})

@app.route("/support")
@req_role("admin","cs")
def support_page():
    return SUPPORT_HTML.replace("__NAME__",esc(session.get("name",""))).replace(
        "__NAVBAR__",_navbar("support")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

@app.route("/admin/support")
@req_super
def platform_support_page():
    return PLATFORM_SUPPORT_HTML.replace("__NAME__",esc(session.get("name",""))).replace(
        "__NAVBAR__",_navbar("support")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

# ══════════════════════════════════════════════════════════
# HELP GUIDES — authored by the platform owner, read by all tenants.
# ══════════════════════════════════════════════════════════
GUIDE_CATEGORIES=[
    ("getting_started","Getting started"),
    ("import","Importing orders"),
    ("packing","Packing & recording"),
    ("picking","Picking & scanning"),
    ("shipping","Shipping & tracking"),
    ("giveaways","Giveaways"),
    ("inventory","Inventory & SKUs"),
    ("analytics","Analytics & reports"),
    ("account","Account, users & badges"),
    ("troubleshooting","Troubleshooting"),
]
_GUIDE_CAT_KEYS={k for k,_ in GUIDE_CATEGORIES}
GUIDE_AUDIENCES=["all","managers"]

def _guide_visible_to_role(audience,role):
    if audience=="managers": return role in ("admin","cs")
    return True

@app.route("/api/guides")
@req_login
def api_guides_list():
    """Published guides visible to the caller's role (customer help center)."""
    role=session.get("role")
    c=pdb()
    rows=[dict(r) for r in c.execute(
        "SELECT id,category,title,audience,video_url,updated_at FROM guides WHERE status='published' ORDER BY sort_order,id").fetchall()]
    c.close()
    rows=[r for r in rows if _guide_visible_to_role(r.get("audience","all"),role)]
    return jsonify({"ok":True,"guides":rows,"categories":dict(GUIDE_CATEGORIES),
                    "cat_order":[k for k,_ in GUIDE_CATEGORIES]})

@app.route("/api/guides/<int:gid>")
@req_login
def api_guide_get(gid):
    c=pdb(); r=c.execute("SELECT * FROM guides WHERE id=?",(gid,)).fetchone(); c.close()
    if not r: return jsonify({"ok":False,"error":"Not found"}),404
    g=dict(r)
    if not is_super():
        if g.get("status")!="published" or not _guide_visible_to_role(g.get("audience","all"),session.get("role")):
            return jsonify({"ok":False,"error":"Not found"}),404
    return jsonify({"ok":True,"guide":g,"categories":dict(GUIDE_CATEGORIES)})

@app.route("/api/admin/guides")
@req_super
def api_admin_guides_list():
    c=pdb(); rows=[dict(r) for r in c.execute(
        "SELECT id,category,title,audience,status,sort_order,updated_at FROM guides ORDER BY sort_order,id").fetchall()]; c.close()
    return jsonify({"ok":True,"guides":rows,"categories":dict(GUIDE_CATEGORIES),
                    "cat_list":GUIDE_CATEGORIES,"audiences":GUIDE_AUDIENCES})

def _guide_payload(d):
    cat=(d.get("category") or "getting_started").strip()
    if cat not in _GUIDE_CAT_KEYS: cat="getting_started"
    aud=(d.get("audience") or "all").strip()
    if aud not in GUIDE_AUDIENCES: aud="all"
    st=(d.get("status") or "draft").strip()
    if st not in ("draft","published"): st="draft"
    try: order=int(d.get("sort_order") or 0)
    except Exception: order=0
    return {"category":cat,"title":(d.get("title") or "").strip()[:200],
            "body":(d.get("body") or ""),"video_url":(d.get("video_url") or "").strip()[:500],
            "audience":aud,"status":st,"sort_order":order}

@app.route("/api/admin/guides",methods=["POST"])
@req_super
def api_admin_guide_create():
    p=_guide_payload(request.get_json() or {})
    if not p["title"]: return jsonify({"ok":False,"error":"Title is required"})
    c=pdb()
    cur=c.execute("""INSERT INTO guides(category,title,body,video_url,audience,status,sort_order)
                     VALUES(?,?,?,?,?,?,?)""",
                  (p["category"],p["title"],p["body"],p["video_url"],p["audience"],p["status"],p["sort_order"]))
    gid=cur.lastrowid; c.commit(); c.close()
    return jsonify({"ok":True,"id":gid})

@app.route("/api/admin/guides/<int:gid>",methods=["POST"])
@req_super
def api_admin_guide_update(gid):
    p=_guide_payload(request.get_json() or {})
    if not p["title"]: return jsonify({"ok":False,"error":"Title is required"})
    now=datetime.now().isoformat(timespec="seconds")
    c=pdb()
    if not c.execute("SELECT 1 FROM guides WHERE id=?",(gid,)).fetchone():
        c.close(); return jsonify({"ok":False,"error":"Not found"}),404
    c.execute("""UPDATE guides SET category=?,title=?,body=?,video_url=?,audience=?,status=?,sort_order=?,updated_at=?
                 WHERE id=?""",
              (p["category"],p["title"],p["body"],p["video_url"],p["audience"],p["status"],p["sort_order"],now,gid))
    c.commit(); c.close()
    return jsonify({"ok":True})

@app.route("/api/admin/guides/<int:gid>/delete",methods=["POST"])
@req_super
def api_admin_guide_delete(gid):
    c=pdb(); c.execute("DELETE FROM guides WHERE id=?",(gid,)); c.commit(); c.close()
    return jsonify({"ok":True})

@app.route("/guides")
@req_login
def guides_page():
    if session.get("role")=="superadmin": return redirect("/admin/guides")
    return GUIDES_HTML.replace("__NAME__",esc(session.get("name",""))).replace(
        "__NAVBAR__",_navbar("guides")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

@app.route("/admin/guides")
@req_super
def admin_guides_page():
    return GUIDES_ADMIN_HTML.replace("__NAME__",esc(session.get("name",""))).replace(
        "__NAVBAR__",_navbar("guides")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

@app.route("/guide-asset/<name>")
@req_login
def guide_asset(name):
    """Serve an anonymized screen mockup used inside the help guides."""
    svg=GUIDE_ASSETS.get((name or "").replace(".svg",""))
    if not svg: return ("",404)
    return Response(svg,mimetype="image/svg+xml")

@app.route("/api/users/badge/pdf/<u>")
@req_role("admin")
def api_badge_pdf(u):
    """Generate a printable badge PDF for one worker (single label, ID-card sized, ~3.5x2 inches)."""
    users=ldj(USERS_FILE)
    if u not in users or not _same_org_user(users,u): return ("",404)
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
    if u not in users or not _same_org_user(users,u): return ("", 404)
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
        c.setFillColorRGB(0.851, 0.455, 0.561)  # #d9748f brand rose
        c.roundRect(0.15*inch, 3*inch - 0.15*inch - stripe_h, page_w - 0.3*inch, stripe_h, 8, stroke=0, fill=1)
        # Stripe text
        c.setFillColorRGB(0.10, 0.06, 0.05)
        _bmark=((session.get("brand") or {}).get("mark") or "").strip() or \
               (org_get(current_org()).get("brand_mark") or "STAFF")
        c.setFont("Helvetica-Bold", 22); c.drawCentredString(page_w/2, 3*inch - 0.40*inch, _bmark[:14])
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
        myorg=session.get("org",DEFAULT_ORG)
        workers=[(u,info) for u,info in users.items()
                 if info.get("badge_token") and info.get("org",DEFAULT_ORG)==myorg]
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
            # Per-tenant prefixes; the original tenant also owns the legacy bare prefixes.
            _org=current_org()
            _prefixes=[(_org+'/videos/',True),(_org+'/photos/',False)]
            if _org==DEFAULT_ORG:
                _prefixes+=[('videos/',True),('photos/',False)]
            for prefix,is_v in _prefixes:
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
    if os.path.exists(video_dir()):
        for f in os.listdir(video_dir()):
            fp=os.path.join(video_dir(),f);vcount+=1;vsize+=os.path.getsize(fp)
            mt=os.path.getmtime(fp)
            if oldest is None or mt<oldest: oldest=mt
            if newest is None or mt>newest: newest=mt
    if os.path.exists(photo_dir()):
        for f in os.listdir(photo_dir()):
            fp=os.path.join(photo_dir(),f);pcount+=1;psize+=os.path.getsize(fp)
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

@app.route("/api/admin/repair-videos",methods=["POST"])
@req_role("admin")
def api_repair_videos():
    """Repair existing R2 webm objects that have a corrupt prefix before the EBML
    header (the cause of 'video found but won't play'). Strips everything before
    the first 1A45DFA3 and rewrites a clean object.

    Processes ONE bounded page per call (so the request can never time out) and
    returns next_cursor for the following page. Drive it with a small JS loop that
    keeps calling until next_cursor is null. Idempotent: a clean file (magic at
    offset 0) is skipped.

    Params (JSON body or query string):
      dry_run : 'true' (default) only reports; 'false' actually rewrites.
      max     : objects per page (default 40, capped 200). Keep small for repair
                runs since each corrupt file is fully downloaded + re-uploaded.
      cursor  : continuation token from the previous call's next_cursor.

    Detection reads only the first 64KB of each object (cheap); a full download
    happens only when a corrupt file is actually being repaired."""
    if not r2:
        return jsonify({"ok":False,"error":"R2 not configured (backend is local)"})
    d=request.get_json(silent=True) or {}
    def _p(name,default): return d.get(name, request.args.get(name,default))
    dry=str(_p("dry_run","true")).lower() not in ("false","0","no")
    try: page_size=max(1,min(200,int(_p("max",40))))
    except Exception: page_size=40
    cursor=_p("cursor",None)
    scanned=0;corrupt=0;repaired=0;errors=0;no_header=0;samples=[]
    # Scan every tenant's videos (keys are now '<org>/videos/…'; legacy ones are 'videos/…').
    # The .webm filter below skips anything that isn't a recording.
    kw={"Bucket":R2_BUCKET,"Prefix":_p("prefix",""),"MaxKeys":page_size}
    if cursor: kw["ContinuationToken"]=cursor
    try:
        resp=r2.list_objects_v2(**kw)
    except Exception as e:
        return jsonify({"ok":False,"error":"R2 listing failed: %s"%e})
    for obj in resp.get("Contents",[]):
        key=obj["Key"]
        if not key.lower().endswith(".webm"): continue
        scanned+=1
        try:
            # Read first 1MB so we catch even a large junk prefix (cheap Range read).
            head=r2.get_object(Bucket=R2_BUCKET,Key=key,Range='bytes=0-1048575')['Body'].read()
            i=head.find(EBML_MAGIC)
            if i==0:
                continue                # already clean
            if i<0:
                no_header+=1            # magic not in first 1MB — likely truly broken
                if len(samples)<25: samples.append({"key":key,"status":"no_header",
                    "size":obj.get("Size"),"first8":head[:8].hex()})
                continue
            corrupt+=1
            if len(samples)<25: samples.append({"key":key,"junk_bytes":i})
            if not dry:
                body=r2.get_object(Bucket=R2_BUCKET,Key=key)['Body'].read()
                j=body.find(EBML_MAGIC)
                if j>0:
                    r2.put_object(Bucket=R2_BUCKET,Key=key,Body=body[j:],ContentType='video/webm')
                    repaired+=1
        except Exception as e:
            errors+=1
            print("repair-videos failed for",key,":",e,flush=True)
    next_cursor=resp.get("NextContinuationToken") if resp.get("IsTruncated") else None
    return jsonify({"ok":True,"dry_run":dry,"scanned":scanned,"corrupt":corrupt,
                    "repaired":repaired,"no_header":no_header,"errors":errors,
                    "page_size":page_size,"next_cursor":next_cursor,"samples":samples,
                    "hint":"Use the auto-loop snippet; reruns are safe (idempotent)."})

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
                Params={'Bucket':R2_BUCKET,'Key':_r2_resolve("videos",fn)},
                ExpiresIn=R2_PRESIGN_TTL)
            return redirect(url)
        except Exception as e:
            print("R2 presign failed:",e,flush=True)
            return ("",404)
    p=os.path.join(video_dir(),fn)
    real=os.path.realpath(p)
    if not real.startswith(os.path.realpath(video_dir())+os.sep): return ("",404)
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
                Params={'Bucket':R2_BUCKET,'Key':_r2_resolve("photos",fn)},
                ExpiresIn=R2_PRESIGN_TTL)
            return redirect(url)
        except Exception as e:
            print("R2 presign failed:",e,flush=True)
            return ("",404)
    p=os.path.join(photo_dir(),fn)
    real=os.path.realpath(p)
    if not real.startswith(os.path.realpath(photo_dir())+os.sep): return ("",404)
    return send_file(real,mimetype="image/jpeg") if os.path.exists(real) else ("",404)

@app.route("/label/file/<fn>")
@req_role("admin","cs")
def serve_label(fn):
    """Serve a stored shipping label (UPS direct). R2 presign or local file."""
    fn=secure_filename(fn)
    if not fn: return ("",404)
    ext=fn.rsplit(".",1)[-1].lower() if "." in fn else ""
    mt={"gif":"image/gif","png":"image/png","pdf":"application/pdf"}.get(ext,"application/octet-stream")
    if r2:
        try:
            url=r2.generate_presigned_url("get_object",
                Params={"Bucket":R2_BUCKET,"Key":_r2_resolve("labels",fn)}, ExpiresIn=R2_PRESIGN_TTL)
            return redirect(url)
        except Exception as e:
            print("R2 label presign failed:",e,flush=True); return ("",404)
    p=os.path.join(_labels_dir(),fn)
    real=os.path.realpath(p)
    if not real.startswith(os.path.realpath(_labels_dir())+os.sep): return ("",404)
    return send_file(real,mimetype=mt) if os.path.exists(real) else ("",404)

# ══════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════
# GIVEAWAY ROUTES (Phase A - manual entry, no AI/Shippo yet)
# ══════════════════════════════════════════════════════════

@app.route("/giveaway")
@req_role("admin","cs")
def giveaway_dashboard():
    return GIVEAWAY_DASH_HTML.replace("__NAME__",esc(session.get("name",""))).replace("__NAVBAR__",_navbar("giveaway")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

@app.route("/giveaway/<int:gid>")
@req_role("admin","cs")
def giveaway_detail(gid):
    return GIVEAWAY_DETAIL_HTML.replace("__GID__",str(gid)).replace("__NAME__",esc(session.get("name",""))).replace("__NAVBAR__",_navbar("giveaway")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

def _lifetime_spend(c, usernames):
    """{username: total_spend}, {username: order_count} across all their store orders.
    Keyed by exact buyer_username. revenue may be 0 on Whatnot exports (best-effort)."""
    usernames=[u for u in usernames if u]
    spend={}; orders={}
    if not usernames: return spend, orders
    qm=",".join("?"*len(usernames))
    for r in c.execute(
        "SELECT s.buyer_username bu, COALESCE(SUM(i.revenue),0) sp, COUNT(DISTINCT s.shipment_id) oc "
        "FROM shipments s JOIN shipment_items i ON i.shipment_id=s.shipment_id "
        "WHERE s.buyer_username IN ("+qm+") GROUP BY s.buyer_username", usernames).fetchall():
        spend[r["bu"]]=round(r["sp"] or 0,2); orders[r["bu"]]=r["oc"]
    return spend, orders

def _giveaway_stage(d, s):
    """New board model:
       pending_pick — attached to an order still being picked (waiting to go in the box)
       no_order     — winner has no order yet, still inside the 4-day wait window
       need_label   — 4-day window elapsed with no order → ship a standalone label
       done         — packed / shipped (leaves the board, kept for history/search)"""
    if d.get("attach_mode")=="piggyback" and s:
        st=(s.get("status") or ""); dv=(s.get("delivery_status") or "")
        if st in ("packed","shipped") or dv in ("PRE_TRANSIT","IN_TRANSIT","OUT_FOR_DELIVERY","DELIVERED","RETURNED","EXCEPTION"):
            return "done"
        return "pending_pick"
    # standalone (no linked order)
    if d.get("status") in ("shipped",) or d.get("tracking_number"):
        return "done"
    created=_parse_dt(d.get("created_at"))
    age_days=(datetime.now()-created).days if created else 0
    return "need_label" if age_days>=GIVEAWAY_NO_ORDER_DAYS else "no_order"

@app.route("/api/giveaway/list")
@req_role("admin","cs")
def api_giveaway_list():
    """Active giveaways in the new 3-lane board:
       pending_pick → no_order → need_label.
    Packed/shipped giveaways drop off the board (searchable in history). Each card is
    enriched with the winner's lifetime spend so you know what tier of prize to give."""
    c=gdb()
    rows=c.execute("SELECT * FROM giveaways WHERE status!='cancelled' ORDER BY created_at DESC").fetchall()
    c.close()
    items=[dict(r) for r in rows]
    sids=[d["linked_shipment_id"] for d in items if d.get("linked_shipment_id")]
    winners=sorted({(d.get("winner_username") or "").strip() for d in items if d.get("winner_username")})
    smap={}; spend={}; orders={}
    try:
        sc=sdb()
        if sids:
            qm=",".join("?"*len(sids))
            for sr in sc.execute("SELECT shipment_id,buyer_username,buyer_name,address_full,postal_code,"
                             "tracking_code,status,delivery_status,delivery_detail,delivered_at,"
                             "packed_by,packed_at,picked_by FROM shipments WHERE shipment_id IN ("+qm+")", sids).fetchall():
                smap[sr["shipment_id"]]=dict(sr)
        spend,orders=_lifetime_spend(sc, winners)
        sc.close()
    except Exception as e:
        print("giveaway enrich failed:",e,flush=True)
    grouped={"pending_pick":[],"no_order":[],"need_label":[]}
    for d in items:
        s=smap.get(d.get("linked_shipment_id"))
        wu=(d.get("winner_username") or "").strip()
        d["lifetime_spend"]=spend.get(wu,0.0)
        d["lifetime_orders"]=orders.get(wu,0)
        if s:
            d["order_recipient"]=s.get("buyer_name")
            d["order_address"]=s.get("address_full")
            d["order_status"]=s.get("status")
            d["order_delivery"]=s.get("delivery_status")
            d["order_delivery_detail"]=s.get("delivery_detail")
            d["order_delivered_at"]=s.get("delivered_at")
            d["order_tracking"]=s.get("tracking_code") or d.get("linked_tracking")
        st=_giveaway_stage(d, s)
        if st=="done":
            continue
        if st=="no_order":
            created=_parse_dt(d.get("created_at"))
            age=max(0,(datetime.now()-created).days) if created else 0
            d["days_left"]=max(0, min(GIVEAWAY_NO_ORDER_DAYS, GIVEAWAY_NO_ORDER_DAYS-age))
        grouped[st].append(d)
    return jsonify({"groups":grouped,"brands":giveaway_brands()})

@app.route("/api/giveaway/brands",methods=["POST"])
@req_role("admin")
def api_giveaway_brands_set():
    """This tenant's own giveaway brand list (replaces the old hardcoded one)."""
    d=request.get_json() or {}
    brands=[str(x).strip()[:60] for x in (d.get("brands") or []) if str(x).strip()]
    if len(brands)>30: return jsonify({"ok":False,"error":"Too many brands (max 30)"})
    _set_setting("giveaway_brands", json.dumps(brands))
    alog("settings.giveaway_brands", ", ".join(brands)[:200])
    return jsonify({"ok":True,"brands":giveaway_brands()})

# ── Company setup: one screen a new tenant works through on day one ───────────
@app.route("/setup")
@req_role("admin")
def setup_page():
    return (SETUP_HTML.replace("__NAME__",esc(session.get("name","")))
            .replace("__NAVBAR__",_navbar("setup")).replace("__NAVBAR_CSS__",_NAVBAR_CSS))

@app.route("/api/setup/status")
@req_role("admin")
def api_setup_status():
    """Drives the setup checklist — what's configured and what's still missing."""
    org=current_org()
    o=org_get(org) or {}
    addr=_ship_from() or {}
    try: chans=_channels()
    except Exception: chans=[]
    users=_org_user_count(org)
    brands=giveaway_brands()
    steps=[
        {"key":"company","label":"Name your company and set your brand",
         "done":bool(o.get("company_name") and o.get("brand_mark")),
         "hint":"Shown in the top-left of every screen and on staff badges."},
        {"key":"address","label":"Add your warehouse address",
         "done":bool(addr.get("street1") and addr.get("zip")),
         "hint":"Used as the ship-from/ship-to when buying shipping labels."},
        {"key":"channels","label":"Add the channels you sell on",
         "done":bool(chans),"count":len(chans),
         "hint":"Needed before you can schedule hosts on the roster."},
        {"key":"brands","label":"Set your giveaway brands",
         "done":bool(brands),"count":len(brands),
         "hint":"The brand options when logging a giveaway winner."},
        {"key":"team","label":"Invite your team",
         "done":users>1,"count":users,
         "hint":"Pickers, packers and hosts each get their own login."},
    ]
    return jsonify({"ok":True,"org":{k:o.get(k) for k in
        ("org_id","company_name","brand_mark","brand_sub","brand_color","logo_url")},
        "address":addr,"channels":chans,"brands":brands,"users":users,
        "steps":steps,"done":sum(1 for s in steps if s["done"]),"total":len(steps)})

@app.route("/api/giveaway/customer")
@req_role("admin","cs")
def api_giveaway_customer():
    """Customer card for a winner: lifetime spend + order count + last order date.
    Lets the team see the customer's tier before deciding what prize to give."""
    u=(request.args.get("username") or "").strip().lstrip("@")
    if not u: return jsonify({"ok":False,"error":"username required"})
    try:
        c=sdb()
        row=c.execute("""SELECT buyer_name,
                                COUNT(DISTINCT s.shipment_id) orders,
                                COALESCE(SUM(i.revenue),0) spend,
                                MAX(s.show_date) last_order
                         FROM shipments s LEFT JOIN shipment_items i ON i.shipment_id=s.shipment_id
                         WHERE LOWER(s.buyer_username)=LOWER(?)""",(u,)).fetchone()
        c.close()
    except Exception as e:
        return jsonify({"ok":False,"error":str(e)})
    found=bool(row and row["orders"])
    return jsonify({"ok":True,"username":u,"found":found,
        "name":(row["buyer_name"] if row else None),
        "lifetime_spend":round((row["spend"] if row else 0) or 0,2),
        "orders":(row["orders"] if row else 0),
        "last_order":(row["last_order"] if row else None)})

@app.route("/api/giveaway/search")
@req_role("admin","cs")
def api_giveaway_search():
    """Search giveaways by winner username (incl shipped history), plus the customer card.
    Replaces the old shipped/delivered history columns."""
    u=(request.args.get("username") or "").strip().lstrip("@")
    if not u: return jsonify({"ok":True,"giveaways":[],"card":None})
    g=gdb()
    rows=g.execute("SELECT * FROM giveaways WHERE LOWER(winner_username) LIKE LOWER(?) ORDER BY created_at DESC LIMIT 100",
                   ("%"+u+"%",)).fetchall()
    g.close()
    gvs=[dict(r) for r in rows]
    # Enrich with linked order status + a plain status label.
    sids=[d["linked_shipment_id"] for d in gvs if d.get("linked_shipment_id")]
    smap={}
    card=None
    try:
        c=sdb()
        if sids:
            qm=",".join("?"*len(sids))
            for sr in c.execute("SELECT shipment_id,status,delivery_status,tracking_code FROM shipments WHERE shipment_id IN ("+qm+")",sids).fetchall():
                smap[sr["shipment_id"]]=dict(sr)
        row=c.execute("""SELECT buyer_name, COUNT(DISTINCT s.shipment_id) orders,
                                COALESCE(SUM(i.revenue),0) spend, MAX(s.show_date) last_order
                         FROM shipments s LEFT JOIN shipment_items i ON i.shipment_id=s.shipment_id
                         WHERE LOWER(s.buyer_username)=LOWER(?)""",(u,)).fetchone()
        c.close()
        if row and row["orders"]:
            card={"name":row["buyer_name"],"orders":row["orders"],
                  "lifetime_spend":round((row["spend"] or 0),2),"last_order":row["last_order"]}
    except Exception as e:
        print("giveaway search enrich failed:",e,flush=True)
    for d in gvs:
        s=smap.get(d.get("linked_shipment_id"))
        d["stage"]=_giveaway_stage(d, s)
        d["order_status"]=(s.get("status") if s else None)
    return jsonify({"ok":True,"giveaways":gvs,"card":card})

@app.route("/api/giveaway/<int:gid>")
@req_role("admin","cs")
def api_giveaway_get(gid):
    c=gdb()
    r=c.execute("SELECT * FROM giveaways WHERE id=?",(gid,)).fetchone()
    c.close()
    if not r: return jsonify({"ok":False,"error":"Not found"}),404
    return jsonify({"ok":True,"giveaway":dict(r),"brands":giveaway_brands()})

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
    if brand and brand not in giveaway_brands():
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

# ── PIGGYBACK GIVEAWAYS — attach a prize to an order already in the pipeline ──
def _rank_attachable(c, username, first, last, show):
    """Return shipments (not yet shipped/cancelled) matching the winner, ranked so
    the best candidate to receive the prize is first: pending → picked → packed,
    and within a status the most recent show. Username match is preferred over name."""
    username=(username or "").strip()
    first=(first or "").strip().lower()
    last=(last or "").strip().lower()
    ors=[]; params=[]
    if username:
        ors.append("LOWER(buyer_username)=LOWER(?)"); params.append(username)
    name_conds=[]
    if first:
        name_conds.append("LOWER(buyer_name) LIKE ?"); params.append("%"+first+"%")
    if last:
        name_conds.append("LOWER(buyer_name) LIKE ?"); params.append("%"+last+"%")
    if name_conds:
        ors.append("("+" AND ".join(name_conds)+")")
    if not ors:
        return [], False
    base="SELECT * FROM shipments WHERE (%s)" % " OR ".join(ors)
    extra=""; qp=list(params)
    if show:
        extra=" AND import_label=?"; qp.append(show)
    attachable=c.execute(base+" AND status IN ('pending','picked','packed')"+extra, qp).fetchall()
    # Was there anything at all (incl. shipped)? Used to decide fallback messaging.
    any_match=c.execute(base+extra, qp).fetchone() is not None
    prio={"pending":0,"picked":1,"packed":2}
    cand=[dict(r) for r in attachable]
    cand.sort(key=lambda r:((r.get("show_date") or ""),(r.get("shipment_id") or "")),reverse=True)
    cand.sort(key=lambda r:prio.get(r.get("status"),9))
    return cand, any_match

def _slim_ship(r):
    return {"shipment_id":r.get("shipment_id"),"tracking_code":r.get("tracking_code"),
            "buyer_name":r.get("buyer_name"),"buyer_username":r.get("buyer_username"),
            "status":r.get("status"),"import_label":r.get("import_label"),
            "show_date":r.get("show_date"),"total_items":r.get("total_items"),
            "address_full":r.get("address_full"),"postal_code":r.get("postal_code")}

def _pending_giveaways_for(shipment_id, tracking=None):
    """Piggyback giveaways still waiting to be added to this order. Cheap lookup
    used by the pick/pack scan flows."""
    try:
        c=gdb()
        rows=c.execute("""SELECT id,prize_name,brand,winner_username FROM giveaways
                          WHERE attach_mode='piggyback' AND attach_status='pending'
                            AND (linked_shipment_id=? OR (linked_tracking IS NOT NULL AND linked_tracking=?))""",
                       (shipment_id, tracking or "")).fetchall()
        c.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print("pending-giveaways lookup failed:",e,flush=True)
        return []

def _autoattach_giveaways():
    """After a CSV import, try to attach any still-waiting 'no order yet' giveaways to a
    freshly-imported order for the same winner. If found, the giveaway becomes a piggyback
    and moves from 'no order' → 'pending to picking'. Returns how many were attached."""
    try:
        g=gdb()
        waiting=[dict(r) for r in g.execute(
            "SELECT * FROM giveaways WHERE COALESCE(attach_mode,'standalone')!='piggyback' "
            "AND status NOT IN ('shipped','cancelled') AND COALESCE(tracking_number,'')=''").fetchall()]
        g.close()
    except Exception as e:
        print("autoattach load failed:",e,flush=True); return 0
    if not waiting: return 0
    n=0
    try:
        c=sdb(); g=gdb()
        for d in waiting:
            u=(d.get("winner_username") or "").strip()
            if not u: continue
            cand,_=_rank_attachable(c, u, None, None, None)
            # Only auto-attach to an order that can still receive the prize during picking.
            cand=[x for x in cand if x.get("status") in ("pending","picked")]
            if not cand: continue
            ship=cand[0]
            g.execute("""UPDATE giveaways SET attach_mode='piggyback', linked_shipment_id=?,
                            linked_tracking=?, attach_status='pending', attach_show=?,
                            status='address_received'
                         WHERE id=?""",
                      (ship.get("shipment_id"), ship.get("tracking_code"), ship.get("import_label"), d["id"]))
            n+=1
        g.commit(); g.close(); c.close()
    except Exception as e:
        print("autoattach failed:",e,flush=True)
    return n

@app.route("/api/giveaway/match",methods=["POST"])
@req_role("admin","cs")
def api_giveaway_match():
    """Preview matching orders for a winner (no write). Body: username, first_name,
    last_name, show (optional import_label)."""
    d=request.get_json() or {}
    try:
        c=sdb()
        cand,any_match=_rank_attachable(c, d.get("username"), d.get("first_name"),
                                        d.get("last_name"), (d.get("show") or "").strip() or None)
        # How many orders this customer has in history (per username)
        hist={}
        unames=sorted({(r.get("buyer_username") or "") for r in cand if r.get("buyer_username")})
        if unames:
            uq=",".join("?"*len(unames))
            for hr in c.execute("SELECT buyer_username, COUNT(*) n FROM shipments "
                                "WHERE buyer_username IN ("+uq+") GROUP BY buyer_username", unames).fetchall():
                hist[hr["buyer_username"]]=hr["n"]
        spend,_o=_lifetime_spend(c, unames)
        c.close()
    except Exception as e:
        print("giveaway match failed:",e,flush=True)
        return jsonify({"ok":False,"error":"Match failed: "+str(e)})
    if not cand:
        reason="all_shipped" if any_match else "no_match"
        return jsonify({"ok":True,"candidates":[],"best":None,"reason":reason})
    slim=[]
    for r in cand:
        s=_slim_ship(r); s["order_history"]=hist.get(r.get("buyer_username"),1)
        s["lifetime_spend"]=spend.get(r.get("buyer_username"),0.0); slim.append(s)
    return jsonify({"ok":True,"candidates":slim,"best":slim[0]})

@app.route("/api/giveaway/attach",methods=["POST"])
@req_role("admin","cs")
def api_giveaway_attach():
    """Create a piggyback giveaway linked to an order in the pipeline. Body:
    prize_name (req), brand, username (winner), platform, and either shipment_id
    (explicit choice) or the matcher fields to auto-pick the best order."""
    d=request.get_json() or {}
    prize=(d.get("prize_name") or "").strip()
    if not prize:
        return jsonify({"ok":False,"error":"Prize name required"})
    brand=(d.get("brand") or "").strip() or None
    if brand and brand not in giveaway_brands():
        return jsonify({"ok":False,"error":"Invalid brand"})
    username=(d.get("username") or "").strip()
    sid=(d.get("shipment_id") or "").strip()
    c=sdb()
    if sid:
        row=c.execute("SELECT * FROM shipments WHERE shipment_id=?",(sid,)).fetchone()
        ship=dict(row) if row else None
        if ship and ship.get("status") in ("shipped","cancelled"):
            c.close(); return jsonify({"ok":False,"error":"Order already %s — ship the prize separately."%ship["status"]})
    else:
        cand,_=_rank_attachable(c, username, d.get("first_name"), d.get("last_name"),
                                (d.get("show") or "").strip() or None)
        ship=cand[0] if cand else None
    c.close()
    if not ship:
        return jsonify({"ok":False,"error":"No attachable order found for this winner"})
    g=gdb()
    cur=g.execute("""INSERT INTO giveaways(winner_username,prize_name,brand,platform,status,created_by,
                        attach_mode,linked_shipment_id,linked_tracking,attach_status,attach_show)
                     VALUES(?,?,?,?, 'address_received', ?, 'piggyback',?,?, 'pending', ?)""",
                  (username or ship.get("buyer_username") or "", prize, brand,
                   (d.get("platform") or "tiktok"), session.get("name","")[:60],
                   ship.get("shipment_id"), ship.get("tracking_code"), ship.get("import_label")))
    gid=cur.lastrowid
    g.commit();g.close()
    return jsonify({"ok":True,"giveaway_id":gid,"linked":_slim_ship(ship)})

@app.route("/api/giveaway/<int:gid>/mark-added",methods=["POST"])
@req_login
def api_giveaway_mark_added(gid):
    """Picker/packer checks the prize off (it's in the box). Toggles attach_status.
    Body {added:false} un-checks it (parity with tapping a product line off)."""
    d=request.get_json(silent=True) or {}
    added = d.get("added", True)
    c=gdb()
    if added:
        c.execute("""UPDATE giveaways SET attach_status='added',
                        attach_added_at=?, attach_added_by=?
                     WHERE id=? AND attach_mode='piggyback'""",
                  (datetime.now().isoformat(timespec='seconds'), session.get("name","")[:60], gid))
    else:
        c.execute("""UPDATE giveaways SET attach_status='pending',
                        attach_added_at=NULL, attach_added_by=NULL
                     WHERE id=? AND attach_mode='piggyback'""", (gid,))
    c.commit();c.close()
    return jsonify({"ok":True,"added":bool(added)})

@app.route("/api/tracking/refresh",methods=["POST"])
@req_role("admin","cs")
def api_tracking_refresh():
    """Poll USPS now for not-yet-delivered shipments. Body/query: limit (default 150)."""
    if not USPS_ENABLED:
        return jsonify({"ok":False,"error":"USPS not configured. Set USPS_CLIENT_ID / USPS_CLIENT_SECRET on Railway."})
    d=request.get_json(silent=True) or {}
    try: lim=max(1,min(600,int(d.get("limit",request.args.get("limit",150)))))
    except Exception: lim=150
    res=refresh_tracking_batch(limit=lim); res["ok"]=True
    return jsonify(res)

# Unified status across ALL store orders: prefer the live USPS delivery bucket,
# otherwise fall back to the internal pipeline status. Used for counts + filtering.
_UNIFIED_CASE="""CASE
  WHEN COALESCE(delivery_status,'')!='' THEN delivery_status
  WHEN status='pending' THEN 'PENDING'
  WHEN status='picked'  THEN 'PICKED'
  WHEN status='packed'  THEN 'PACKED'
  WHEN status='shipped' THEN 'SHIPPED'
  WHEN status='cancelled' THEN 'CANCELLED'
  WHEN status='giveaway' THEN 'GIVEAWAY'
  WHEN status='issue'   THEN 'ISSUE'
  ELSE 'UNKNOWN' END"""

@app.route("/api/tracking/summary")
@req_role("admin","cs")
def api_tracking_summary():
    """Counts + list across ALL store orders. Filters: status, show (import_label),
    date (show_date). Status is the unified bucket (USPS if tracked, else pipeline)."""
    show=(request.args.get("show") or "").strip()
    date=(request.args.get("date") or "").strip()
    flt=(request.args.get("status") or "").strip().upper()
    base=[]; bp=[]
    if show: base.append("import_label=?"); bp.append(show)
    if date: base.append("show_date=?"); bp.append(date)
    basewhere=(" WHERE "+" AND ".join(base)) if base else ""
    c=sdb()
    counts={}
    for row in c.execute("SELECT "+_UNIFIED_CASE+" AS st, COUNT(*) n FROM shipments"+basewhere+" GROUP BY st", bp).fetchall():
        counts[row["st"]]=row["n"]
    lw=list(base); lp=list(bp)
    if flt:
        lw.append("("+_UNIFIED_CASE+")=?"); lp.append(flt)
    listwhere=(" WHERE "+" AND ".join(lw)) if lw else ""
    rows=c.execute("SELECT shipment_id,tracking_code,buyer_name,buyer_username,delivery_status,"
                   "delivery_detail,delivered_at,tracked_at,import_label,show_date,status, "
                   +_UNIFIED_CASE+" AS unified FROM shipments"+listwhere+
                   " ORDER BY COALESCE(show_date,'') DESC, COALESCE(tracked_at,'') DESC LIMIT 400", lp).fetchall()
    shows=c.execute("""SELECT import_label, MAX(show_date) AS show_date FROM shipments
                       WHERE import_label IS NOT NULL AND import_label!=''
                       GROUP BY import_label ORDER BY show_date DESC LIMIT 100""").fetchall()
    dates=c.execute("""SELECT DISTINCT show_date FROM shipments
                       WHERE show_date IS NOT NULL AND show_date!='' ORDER BY show_date DESC LIMIT 60""").fetchall()
    c.close()
    return jsonify({"ok":True,"enabled":USPS_ENABLED,"counts":counts,
        "rows":[dict(r) for r in rows],
        "shows":[{"label":s["import_label"],"date":s["show_date"]} for s in shows],
        "dates":[d["show_date"] for d in dates]})

@app.route("/shipping-status")
@req_role("admin","cs")
def shipping_status_page():
    return SHIPPING_STATUS_HTML.replace("__NAME__",esc(session.get("name",""))).replace("__NAVBAR__",_navbar("shipstatus")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

@app.route("/api/ship-from",methods=["GET","POST"])
@req_role("admin","cs")
def api_ship_from():
    """The warehouse/sender address used when buying labels."""
    if request.method=="POST":
        d=request.get_json() or {}
        _set_setting("ship_from", json.dumps({k:(d.get(k) or "") for k in
            ("name","company","street1","street2","city","state","zip","country","phone")}))
        return jsonify({"ok":True})
    raw=_get_setting("ship_from")
    return jsonify({"ok":True,"address": json.loads(raw) if raw else {}})

def _ship_from():
    raw=_get_setting("ship_from")
    return json.loads(raw) if raw else {}

@app.route("/api/giveaway/<int:gid>/rates",methods=["POST"])
@req_role("admin","cs")
def api_giveaway_rates(gid):
    """Get EasyPost rates for shipping this giveaway's prize."""
    if not EASYPOST_ENABLED:
        return jsonify({"ok":False,"error":"ShipStation not configured — set SHIPSTATION_API_KEY on Railway."})
    d=request.get_json() or {}
    c=gdb(); g=c.execute("SELECT * FROM giveaways WHERE id=?",(gid,)).fetchone(); c.close()
    if not g: return jsonify({"ok":False,"error":"Giveaway not found"})
    g=dict(g)
    to={"name":g.get("address_name") or g.get("winner_username") or "Recipient",
        "street1":g.get("address_street1") or "","street2":g.get("address_street2") or "",
        "city":g.get("address_city") or "","state":g.get("address_state") or "",
        "zip":g.get("address_zip") or "","country":g.get("address_country") or "US"}
    if not (to["street1"] and to["city"] and to["state"] and to["zip"]):
        return jsonify({"ok":False,"error":"Winner address incomplete — fill street/city/state/ZIP first."})
    frm=_ship_from()
    if not (frm.get("street1") and frm.get("zip")):
        return jsonify({"ok":False,"error":"Set your warehouse 'ship-from' address first (Settings).","need_ship_from":True})
    try: weight=float(d.get("weight_oz") or 0)
    except Exception: weight=0
    if weight<=0: return jsonify({"ok":False,"error":"Enter package weight (oz)."})
    try:
        sid,rates=_ship_rates(to, frm, weight, d)
    except Exception as e:
        return jsonify({"ok":False,"error":str(e)})
    return jsonify({"ok":True,"shipment_id":sid,"rates":rates})

@app.route("/api/giveaway/<int:gid>/buy-label",methods=["POST"])
@req_role("admin","cs")
def api_giveaway_buy_label(gid):
    if not EASYPOST_ENABLED:
        return jsonify({"ok":False,"error":"ShipStation not configured."})
    d=request.get_json() or {}
    sid=(d.get("shipment_id") or "").strip(); rate_id=(d.get("rate_id") or "").strip()
    if not sid or not rate_id: return jsonify({"ok":False,"error":"Missing shipment/rate"})
    # Serialize per-giveaway so a double-click can't buy two labels / double-charge.
    with _flock("giveaway_buy_"+str(gid)):
        c=gdb()
        g=c.execute("SELECT status,shippo_label_url FROM giveaways WHERE id=?",(gid,)).fetchone()
        if not g:
            c.close(); return jsonify({"ok":False,"error":"Giveaway not found"})
        if g["status"]=="shipped" or g["shippo_label_url"]:
            c.close(); return jsonify({"ok":False,"error":"A label was already purchased for this giveaway"})
        c.close()
        try:
            sh=_ship_buy(rate_id)
        except _urlerr.HTTPError as e:
            try: msg=json.loads(e.read().decode()).get("error",{}).get("message",str(e))
            except Exception: msg="HTTP "+str(e.code)
            return jsonify({"ok":False,"error":"ShipStation: "+str(msg)})
        except Exception as e:
            return jsonify({"ok":False,"error":str(e)})
        label=(sh.get("postage_label") or {}).get("label_url")
        tracking=sh.get("tracking_code")
        cost=float((sh.get("selected_rate") or {}).get("rate") or 0)
        c=gdb()
        c.execute("""UPDATE giveaways SET shippo_label_url=?, shippo_label_pdf=?, tracking_number=?,
                        label_cost=?, status='shipped', shipped_at=? WHERE id=?""",
                  (label, label, tracking, cost, datetime.now().isoformat(timespec='seconds'), gid))
        c.commit(); c.close()
    return jsonify({"ok":True,"label_url":label,"tracking":tracking,"cost":cost})

def _label_print_page(url, title="Shipping label", subtitle=""):
    """Wrap a carrier label (PNG/PDF) in a page locked to 4x6 inches with a Print
    button, so it prints at true thermal-label size instead of being scaled to Letter."""
    low=(url or "").split("?")[0].lower()
    if low.endswith(".pdf"):
        media='<iframe src="%s" title="label"></iframe>' % url
    else:
        media='<img src="%s" alt="label">' % url
    sub=('<span class="trk">%s</span>' % subtitle) if subtitle else ""
    return """<!DOCTYPE html><html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>"""+title+"""</title>
<style>
@page { size: 4in 6in; margin: 0; }
*{box-sizing:border-box}
body{margin:0;background:#0c0f16;color:#e4e8f1;font-family:-apple-system,'Segoe UI',sans-serif}
.bar{display:flex;gap:14px;align-items:center;justify-content:center;padding:16px;flex-wrap:wrap}
.bar .ttl{font-weight:800}.trk{font-family:monospace;color:#a5b4fc}
.btn{border:none;border-radius:10px;padding:12px 26px;font-size:16px;font-weight:800;cursor:pointer;background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff}
.sheet{width:4in;height:6in;margin:10px auto 30px;background:#fff;display:flex;align-items:center;justify-content:center;overflow:hidden;border-radius:4px}
.sheet img{max-width:100%;max-height:100%;display:block}
.sheet iframe{width:4in;height:6in;border:0}
@media print{ .bar{display:none!important} body{background:#fff} .sheet{margin:0;border-radius:0} }
</style></head><body>
<div class="bar"><span class="ttl">🏷️ """+title+"""</span>"""+sub+"""<button class="btn" onclick="window.print()">🖨️ Print 4×6</button></div>
<div class="sheet">"""+media+"""</div>
</body></html>"""

def _multi_label_print_page(items, title="Shipping labels"):
    """Stack many labels, each on its own 4x6 page, with one Print button that
    prints them all. items = [{url, sub}]."""
    sheets=[]
    for it in items:
        url=it.get("url") or ""
        low=url.split("?")[0].lower()
        media=('<iframe src="%s" title="label"></iframe>' % url) if low.endswith(".pdf") else ('<img src="%s" alt="label">' % url)
        sheets.append('<div class="sheet">%s</div>' % media)
    return """<!DOCTYPE html><html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>"""+title+"""</title>
<style>
@page { size: 4in 6in; margin: 0; }
*{box-sizing:border-box}
body{margin:0;background:#0c0f16;color:#e4e8f1;font-family:-apple-system,'Segoe UI',sans-serif}
.bar{position:sticky;top:0;display:flex;gap:14px;align-items:center;justify-content:center;padding:16px;background:#0c0f16;border-bottom:1px solid rgba(255,255,255,.08)}
.btn{border:none;border-radius:10px;padding:12px 26px;font-size:16px;font-weight:800;cursor:pointer;background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff}
.sheet{width:4in;height:6in;margin:14px auto;background:#fff;display:flex;align-items:center;justify-content:center;overflow:hidden;border-radius:4px;page-break-after:always}
.sheet img{max-width:100%;max-height:100%;display:block}
.sheet iframe{width:4in;height:6in;border:0}
@media print{ .bar{display:none!important} body{background:#fff} .sheet{margin:0;border-radius:0} }
</style></head><body>
<div class="bar"><span style="font-weight:800">🏷️ """+title+"""</span><button class="btn" onclick="window.print()">🖨️ Print all</button></div>
"""+"".join(sheets)+"""
</body></html>"""

@app.route("/label/giveaway/<int:gid>")
@req_role("admin","cs")
def giveaway_label_print(gid):
    c=gdb(); r=c.execute("SELECT shippo_label_url,tracking_number FROM giveaways WHERE id=?",(gid,)).fetchone(); c.close()
    if not r or not r["shippo_label_url"]:
        return ("No label for this giveaway yet.",404)
    return _label_print_page(r["shippo_label_url"],"Giveaway label",r["tracking_number"] or "")

@app.route("/label/inbound/<int:iid>")
@req_role("admin","cs")
def inbound_label_print(iid):
    c=sdb(); r=c.execute("SELECT label_url,tracking,supplier FROM inbound_shipments WHERE id=?",(iid,)).fetchone(); c.close()
    if not r or not r["label_url"]:
        return ("No label for this shipment yet.",404)
    return _label_print_page(r["label_url"],"Inbound · "+(r["supplier"] or ""),r["tracking"] or "")

@app.route("/api/packages",methods=["GET","POST"])
@req_role("admin","cs")
def api_packages():
    """Saved package presets (box sizes) reused when buying labels."""
    if request.method=="POST":
        pkgs=(request.get_json() or {}).get("packages")
        if not isinstance(pkgs,list): return jsonify({"ok":False,"error":"invalid"})
        clean=[]
        for p in pkgs[:50]:
            try:
                clean.append({"name":(p.get("name") or "").strip()[:40] or "Box",
                    "weight":float(p.get("weight") or 0),"length":float(p.get("length") or 0),
                    "width":float(p.get("width") or 0),"height":float(p.get("height") or 0)})
            except Exception: pass
        _set_setting("packages", json.dumps(clean))
        return jsonify({"ok":True})
    raw=_get_setting("packages")
    return jsonify({"ok":True,"packages": json.loads(raw) if raw else []})

def _easypost_rates(to, frm, weight, dims):
    # Back-compat name — now backed by ShipStation V2.
    return _ship_rates(to, frm, weight, dims)

@app.route("/api/ship/carriers")
@req_role("admin","cs")
def api_ship_carriers():
    """Diagnostic: which carriers are available for rate/label. UPS direct takes priority."""
    if UPS_ENABLED:
        # UPS direct — verify the OAuth credentials actually work by fetching a token.
        try:
            _ups_token()
            return jsonify({"ok":True,"provider":"ups","count":1,
                "carriers":[{"carrier_id":UPS_ACCOUNT_NUMBER,"carrier_code":"ups",
                             "name":"UPS (direct account "+UPS_ACCOUNT_NUMBER+")","services":len(UPS_SERVICE_NAMES)}]})
        except Exception as e:
            return jsonify({"ok":False,"provider":"ups","error":str(e)})
    if not SHIPSTATION_ENABLED:
        return jsonify({"ok":False,"error":"No carrier configured — set UPS_CLIENT_ID/SECRET/ACCOUNT_NUMBER (or SHIPSTATION_API_KEY)."})
    try:
        r=_ss("GET","/v2/carriers")
        cs=[{"carrier_id":c.get("carrier_id"),"carrier_code":c.get("carrier_code"),
             "name":c.get("friendly_name") or c.get("nickname"),
             "services":len(c.get("services") or [])} for c in (r.get("carriers") or [])]
        # If the caller asked to refresh, rebuild the carrier-id cache used for rating
        # so a just-connected carrier (e.g. UPS) is included in the next rate request.
        if request.args.get("refresh"):
            _ship_carrier_ids(force=True)
        return jsonify({"ok":True,"count":len(cs),"carriers":cs})
    except Exception as e:
        return jsonify({"ok":False,"error":str(e)})

@app.route("/api/label/rates",methods=["POST"])
@req_role("admin","cs")
def api_label_rates():
    if not EASYPOST_ENABLED: return jsonify({"ok":False,"error":"ShipStation not configured — set SHIPSTATION_API_KEY."})
    d=request.get_json() or {}
    to=d.get("to_address") or {}
    frm=d.get("from_address") or _ship_from()
    if not (to.get("street1") and to.get("city") and to.get("state") and to.get("zip")):
        return jsonify({"ok":False,"error":"Destination address incomplete (street/city/state/ZIP)."})
    if not (frm.get("street1") and frm.get("zip")):
        return jsonify({"ok":False,"error":"From address incomplete."})
    try: weight=float(d.get("weight_oz") or 0)
    except Exception: weight=0
    if weight<=0: return jsonify({"ok":False,"error":"Enter weight (oz)."})
    try:
        sid,rates=_easypost_rates(to, frm, weight, d)
    except _urlerr.HTTPError as e:
        try: msg=json.loads(e.read().decode()).get("error",{}).get("message",str(e))
        except Exception: msg="HTTP "+str(e.code)
        return jsonify({"ok":False,"error":"ShipStation: "+str(msg)})
    except Exception as e: return jsonify({"ok":False,"error":str(e)})
    return jsonify({"ok":True,"shipment_id":sid,"rates":rates})

@app.route("/api/label/buy",methods=["POST"])
@req_role("admin","cs")
def api_label_buy():
    if not EASYPOST_ENABLED: return jsonify({"ok":False,"error":"EasyPost not configured."})
    d=request.get_json() or {}
    sid=(d.get("shipment_id") or "").strip(); rid=(d.get("rate_id") or "").strip()
    if not sid or not rid: return jsonify({"ok":False,"error":"Missing shipment/rate"})
    try:
        sh=_ship_buy(rid)
    except _urlerr.HTTPError as e:
        try: msg=json.loads(e.read().decode()).get("error",{}).get("message",str(e))
        except Exception: msg="HTTP "+str(e.code)
        return jsonify({"ok":False,"error":"ShipStation: "+str(msg)})
    except Exception as e: return jsonify({"ok":False,"error":str(e)})
    label=(sh.get("postage_label") or {}).get("label_url"); tracking=sh.get("tracking_code")
    sr=sh.get("selected_rate") or {}
    c=sdb()
    c.execute("""INSERT INTO inbound_shipments(supplier,carrier,service,tracking,cost,label_url,po_id,created_by)
                 VALUES(?,?,?,?,?,?,?,?)""",
              (d.get("supplier"),sr.get("carrier"),sr.get("service"),tracking,float(sr.get("rate") or 0),
               label,d.get("po_id"),session.get("name","")[:60]))
    c.commit(); c.close()
    return jsonify({"ok":True,"label_url":label,"tracking":tracking,"cost":float(sr.get("rate") or 0)})

@app.route("/api/label/rates-multi",methods=["POST"])
@req_role("admin","cs")
def api_label_rates_multi():
    """Rates for a multi-box supplier shipment. One EasyPost shipment per box; we
    return only services available on EVERY box, with the summed total."""
    if not EASYPOST_ENABLED: return jsonify({"ok":False,"error":"ShipStation not configured — set SHIPSTATION_API_KEY."})
    d=request.get_json() or {}
    to=d.get("to_address") or {}
    frm=d.get("from_address") or _ship_from()
    boxes=d.get("boxes") or []
    if not boxes: return jsonify({"ok":False,"error":"Add at least one box."})
    if not (to.get("street1") and to.get("city") and to.get("state") and to.get("zip")):
        return jsonify({"ok":False,"error":"Destination address incomplete (street/city/state/ZIP)."})
    if not (frm.get("street1") and frm.get("zip")):
        return jsonify({"ok":False,"error":"From address incomplete."})
    legs=[]
    try:
        for i,b in enumerate(boxes,1):
            try: w=float(b.get("weight_oz") or 0)
            except Exception: w=0
            if w<=0: return jsonify({"ok":False,"error":"Box "+str(i)+": enter weight (oz)."})
            sid,rates=_easypost_rates(to,frm,w,b)
            legs.append({"sid":sid,"rates":rates})
    except _urlerr.HTTPError as e:
        try: msg=json.loads(e.read().decode()).get("error",{}).get("message",str(e))
        except Exception: msg="HTTP "+str(e.code)
        return jsonify({"ok":False,"error":"ShipStation: "+str(msg)})
    except Exception as e: return jsonify({"ok":False,"error":str(e)})
    nb=len(legs); combo={}
    for leg in legs:
        for r in leg["rates"]:
            key=(r["carrier"],r["service"])
            g=combo.setdefault(key,{"carrier":r["carrier"],"service":r["service"],"total":0.0,"days":r.get("days"),"legs":[]})
            g["total"]+=float(r["rate"] or 0)
            g["legs"].append({"shipment_id":leg["sid"],"rate_id":r["id"]})
    out=[g for g in combo.values() if len(g["legs"])==nb]
    for g in out: g["total"]=round(g["total"],2)
    out.sort(key=lambda x:x["total"])
    # Cheapest-per-box (carriers may differ between boxes) — usually the lowest total.
    best=None
    if all(leg["rates"] for leg in legs):
        bl=[]; bt=0.0; det=[]
        for leg in legs:
            r0=leg["rates"][0]   # _easypost_rates already sorts ascending
            bl.append({"shipment_id":leg["sid"],"rate_id":r0["id"]})
            bt+=float(r0["rate"] or 0)
            det.append({"carrier":r0["carrier"],"service":r0["service"],"rate":r0["rate"]})
        best={"legs":bl,"total":round(bt,2),"detail":det}
    return jsonify({"ok":True,"boxes":nb,"rates":out,"best_mix":best})

@app.route("/api/label/buy-multi",methods=["POST"])
@req_role("admin","cs")
def api_label_buy_multi():
    """Buy one label per box for the chosen service; record each + return all labels."""
    if not EASYPOST_ENABLED: return jsonify({"ok":False,"error":"EasyPost not configured."})
    d=request.get_json() or {}
    legs=d.get("legs") or []
    if not legs: return jsonify({"ok":False,"error":"No boxes selected"})
    batch=secrets.token_hex(6)
    labels=[]; total=0.0; c=sdb(); err=None
    try:
        for leg in legs:
            sid=(leg.get("shipment_id") or "").strip(); rid=(leg.get("rate_id") or "").strip()
            if not sid or not rid: continue
            sh=_ship_buy(rid)
            label=(sh.get("postage_label") or {}).get("label_url"); tracking=sh.get("tracking_code")
            sr=sh.get("selected_rate") or {}; cost=float(sr.get("rate") or 0); total+=cost
            c.execute("""INSERT INTO inbound_shipments(supplier,carrier,service,tracking,cost,label_url,po_id,created_by,batch_id)
                         VALUES(?,?,?,?,?,?,?,?,?)""",
                      (d.get("supplier"),sr.get("carrier"),sr.get("service"),tracking,cost,label,d.get("po_id"),session.get("name","")[:60],batch))
            labels.append({"label_url":label,"tracking":tracking,"cost":cost,"carrier":sr.get("carrier"),"service":sr.get("service")})
    except _urlerr.HTTPError as e:
        try: err="EasyPost: "+str(json.loads(e.read().decode()).get("error",{}).get("message",str(e)))
        except Exception: err="HTTP "+str(e.code)
    except Exception as e: err=str(e)
    c.commit(); c.close()
    if err: return jsonify({"ok":False,"error":err,"labels":labels,"total":round(total,2),"batch_id":batch})
    return jsonify({"ok":True,"labels":labels,"total":round(total,2),"count":len(labels),"batch_id":batch})

@app.route("/api/inbound")
@req_role("admin","cs")
def api_inbound_list():
    """Inbound labels grouped by batch (one buy-click). Each group collapses to a
    single row (supplier + count + total) and expands to its individual labels."""
    c=sdb()
    rows=c.execute("SELECT * FROM inbound_shipments ORDER BY created_at DESC LIMIT 400").fetchall()
    c.close()
    groups=[]; idx={}
    for r in rows:
        d=dict(r)
        key=d.get("batch_id") or ("single-"+str(d["id"]))
        if key not in idx:
            idx[key]={"batch_id":d.get("batch_id"),"key":key,"supplier":d.get("supplier") or "—",
                      "when":d.get("created_at"),"carrier":d.get("carrier"),"count":0,"total":0.0,
                      "printable":bool(d.get("batch_id")),"shipments":[]}
            groups.append(idx[key])
        g=idx[key]
        g["count"]+=1; g["total"]=round(g["total"]+float(d.get("cost") or 0),2)
        g["shipments"].append({"id":d["id"],"tracking":d.get("tracking"),"carrier":d.get("carrier"),
                               "service":d.get("service"),"cost":d.get("cost"),"label_url":d.get("label_url"),
                               "created_at":d.get("created_at")})
    return jsonify({"ok":True,"groups":groups})

@app.route("/api/suppliers",methods=["GET","POST"])
@req_role("admin","cs")
def api_suppliers():
    """Saved supplier address book — reused when buying inbound labels."""
    if request.method=="POST":
        sup=(request.get_json() or {}).get("suppliers")
        if not isinstance(sup,list): return jsonify({"ok":False,"error":"invalid"})
        clean=[]
        for s in sup[:200]:
            try:
                e={k:((s.get(k) or "").strip()[:80]) for k in ("name","street1","street2","city","state","zip","phone")}
                if e["name"] or e["street1"]: clean.append(e)
            except Exception: pass
        _set_setting("suppliers", json.dumps(clean))
        return jsonify({"ok":True,"count":len(clean)})
    raw=_get_setting("suppliers")
    return jsonify({"ok":True,"suppliers": json.loads(raw) if raw else []})

@app.route("/label/inbound/batch/<batch_id>")
@req_role("admin","cs")
def inbound_batch_print(batch_id):
    """All labels in a batch on one page (4x6 each) — print the whole shipment at once."""
    c=sdb()
    rows=c.execute("SELECT label_url,tracking,supplier FROM inbound_shipments WHERE batch_id=? ORDER BY id",(batch_id,)).fetchall()
    c.close()
    items=[{"url":r["label_url"],"sub":r["tracking"] or ""} for r in rows if r["label_url"]]
    if not items: return ("No labels in this batch.",404)
    sup=rows[0]["supplier"] if rows else ""
    return _multi_label_print_page(items,"Inbound · "+(sup or "")+" · "+str(len(items))+" labels")

@app.route("/label/inbound/multi")
@req_role("admin","cs")
def inbound_multi_print():
    """Combined 4x6 print page for an arbitrary set of inbound shipment ids."""
    ids=[x for x in (request.args.get("ids") or "").split(",") if x.strip().isdigit()][:300]
    if not ids: return ("No labels selected.",404)
    c=sdb()
    qm=",".join("?"*len(ids))
    rows=c.execute("SELECT label_url,tracking FROM inbound_shipments WHERE id IN ("+qm+") ORDER BY id",ids).fetchall()
    c.close()
    items=[{"url":r["label_url"],"sub":r["tracking"] or ""} for r in rows if r["label_url"]]
    if not items: return ("No printable labels in selection.",404)
    return _multi_label_print_page(items,"Selected labels · "+str(len(items)))

@app.route("/admin/inbound")
@req_role("admin","cs")
def inbound_page():
    return INBOUND_HTML.replace("__NAME__",esc(session.get("name",""))).replace("__NAVBAR__",_navbar("inbound")).replace("__NAVBAR_CSS__",_NAVBAR_CSS)

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
    print("LiveOpsHub — Packing Station")
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
