"""SQLite storage for LiveVision: catalog, shows, frames, segments."""
import json
import os
import sqlite3
import threading
import time

DB_PATH = os.environ.get("LIVEVISION_DB", "/data/livevision.db")
_lock = threading.Lock()


def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    with _lock, _connect() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS catalog (
                sku TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                brand TEXT DEFAULT '',
                barcode TEXT DEFAULT '',
                price TEXT DEFAULT '',
                image_url TEXT DEFAULT '',
                extra TEXT DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS shows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                started_at REAL NOT NULL,
                status TEXT DEFAULT 'live'
            );
            CREATE TABLE IF NOT EXISTS frames (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                show_id INTEGER NOT NULL,
                ts REAL NOT NULL,              -- seconds since show start
                received_at REAL NOT NULL,     -- unix time frame arrived
                status TEXT DEFAULT 'pending', -- pending | matched | error | skipped
                top_sku TEXT,
                confidence REAL,
                candidates TEXT DEFAULT '[]',  -- JSON [{sku, confidence, reason}]
                visible_text TEXT DEFAULT '',
                image_path TEXT DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_frames_show ON frames(show_id, ts);
            CREATE TABLE IF NOT EXISTS confirmations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                show_id INTEGER NOT NULL,
                start_ts REAL NOT NULL,
                end_ts REAL NOT NULL,
                sku TEXT NOT NULL,
                confirmed_at REAL NOT NULL
            );
            """
        )


# ---------- catalog ----------

def upsert_products(rows):
    with _lock, _connect() as c:
        for r in rows:
            c.execute(
                """INSERT INTO catalog (sku, name, brand, barcode, price, image_url, extra)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(sku) DO UPDATE SET
                     name=excluded.name, brand=excluded.brand, barcode=excluded.barcode,
                     price=excluded.price, image_url=excluded.image_url, extra=excluded.extra""",
                (
                    r["sku"], r["name"], r.get("brand", ""), r.get("barcode", ""),
                    r.get("price", ""), r.get("image_url", ""),
                    json.dumps(r.get("extra", {}), ensure_ascii=False),
                ),
            )
        return c.execute("SELECT COUNT(*) AS n FROM catalog").fetchone()["n"]


def get_catalog():
    with _lock, _connect() as c:
        return [dict(r) for r in c.execute("SELECT * FROM catalog ORDER BY sku")]


def get_product(sku):
    with _lock, _connect() as c:
        r = c.execute("SELECT * FROM catalog WHERE sku=?", (sku,)).fetchone()
        return dict(r) if r else None


# ---------- shows ----------

def create_show(name):
    with _lock, _connect() as c:
        cur = c.execute(
            "INSERT INTO shows (name, started_at) VALUES (?, ?)", (name, time.time())
        )
        return cur.lastrowid


def get_show(show_id):
    with _lock, _connect() as c:
        r = c.execute("SELECT * FROM shows WHERE id=?", (show_id,)).fetchone()
        return dict(r) if r else None


def list_shows():
    with _lock, _connect() as c:
        return [dict(r) for r in c.execute("SELECT * FROM shows ORDER BY id DESC")]


def end_show(show_id):
    with _lock, _connect() as c:
        c.execute("UPDATE shows SET status='ended' WHERE id=?", (show_id,))


# ---------- frames ----------

def add_frame(show_id, ts, image_path):
    with _lock, _connect() as c:
        cur = c.execute(
            "INSERT INTO frames (show_id, ts, received_at, image_path) VALUES (?,?,?,?)",
            (show_id, ts, time.time(), image_path),
        )
        return cur.lastrowid


def next_pending_frame():
    with _lock, _connect() as c:
        r = c.execute(
            "SELECT * FROM frames WHERE status='pending' ORDER BY id LIMIT 1"
        ).fetchone()
        return dict(r) if r else None


def save_match(frame_id, top_sku, confidence, candidates, visible_text, status="matched"):
    with _lock, _connect() as c:
        c.execute(
            """UPDATE frames SET status=?, top_sku=?, confidence=?, candidates=?, visible_text=?
               WHERE id=?""",
            (status, top_sku, confidence,
             json.dumps(candidates, ensure_ascii=False), visible_text, frame_id),
        )


def frames_for_show(show_id):
    with _lock, _connect() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM frames WHERE show_id=? ORDER BY ts", (show_id,)
        )]


# ---------- confirmations ----------

def confirm_segment(show_id, start_ts, end_ts, sku):
    with _lock, _connect() as c:
        c.execute(
            """INSERT INTO confirmations (show_id, start_ts, end_ts, sku, confirmed_at)
               VALUES (?,?,?,?,?)""",
            (show_id, start_ts, end_ts, sku, time.time()),
        )


def confirmations_for_show(show_id):
    with _lock, _connect() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM confirmations WHERE show_id=? ORDER BY start_ts", (show_id,)
        )]
