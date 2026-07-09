"""LiveVision server — receives frames from the studio agent, matches products
via Claude, builds a product timeline and cross-matches TikTok Shop orders.

Endpoints:
  GET  /                                dashboard (latest show)
  GET  /show/<id>                       dashboard for a show
  POST /api/shows                       {name} -> create show
  POST /api/shows/<id>/end              mark show ended
  POST /api/frames                      multipart: show_id, ts, image
  GET  /api/shows/<id>/state            live state JSON (current product, segments)
  POST /api/shows/<id>/confirm          {start_ts, end_ts, sku}
  POST /api/catalog/upload              multipart: file (CSV)
  GET  /api/catalog                     catalog JSON
  POST /api/shows/<id>/match_orders     multipart: file (orders CSV) -> enriched CSV
"""
import csv
import io
import json
import os
import threading
import time
import traceback

from flask import Flask, jsonify, render_template, request, send_file

import db
import matcher

app = Flask(__name__)
FRAMES_DIR = os.environ.get("FRAMES_DIR", "/data/frames")
API_TOKEN = os.environ.get("AGENT_TOKEN", "")  # shared secret for the agent
GAP_SECONDS = float(os.environ.get("SEGMENT_GAP", "20"))  # merge frames closer than this
MIN_CONF = float(os.environ.get("MIN_CONFIDENCE", "0.35"))

db.init_db()
os.makedirs(FRAMES_DIR, exist_ok=True)


# ---------------- background matcher worker ----------------

def _worker():
    while True:
        frame = db.next_pending_frame()
        if not frame:
            time.sleep(1.0)
            continue
        try:
            catalog = db.get_catalog()
            if not catalog:
                db.save_match(frame["id"], None, 0, [], "", status="error")
                continue
            result = matcher.match_frame(frame["image_path"], catalog)
            cands = result["candidates"]
            if result["product_visible"] and cands and cands[0]["confidence"] >= MIN_CONF:
                db.save_match(frame["id"], cands[0]["sku"], cands[0]["confidence"],
                              cands, result["visible_text"])
            else:
                db.save_match(frame["id"], None, 0, cands,
                              result["visible_text"], status="skipped")
        except Exception:
            traceback.print_exc()
            db.save_match(frame["id"], None, 0, [], "", status="error")
            time.sleep(2)


threading.Thread(target=_worker, daemon=True).start()


# ---------------- segments ----------------

def build_segments(show_id):
    """Group consecutive matched frames with the same SKU into segments."""
    frames = [f for f in db.frames_for_show(show_id) if f["status"] == "matched"]
    segments = []
    for f in frames:
        if (segments and segments[-1]["sku"] == f["top_sku"]
                and f["ts"] - segments[-1]["end_ts"] <= GAP_SECONDS):
            seg = segments[-1]
            seg["end_ts"] = f["ts"]
            seg["frames"] += 1
            seg["confidence"] = max(seg["confidence"], f["confidence"] or 0)
        else:
            segments.append({
                "sku": f["top_sku"], "start_ts": f["ts"], "end_ts": f["ts"],
                "frames": 1, "confidence": f["confidence"] or 0,
                "candidates": json.loads(f["candidates"] or "[]"),
            })
    # attach product info + confirmation status
    confirmed = db.confirmations_for_show(show_id)
    for seg in segments:
        p = db.get_product(seg["sku"]) or {}
        seg["name"] = p.get("name", seg["sku"])
        seg["brand"] = p.get("brand", "")
        seg["barcode"] = p.get("barcode", "")
        seg["image_url"] = p.get("image_url", "")
        seg["confirmed"] = any(
            c["sku"] == seg["sku"]
            and abs(c["start_ts"] - seg["start_ts"]) < 1
            for c in confirmed
        )
    return segments


# ---------------- API ----------------

def _auth_ok(req):
    return not API_TOKEN or req.headers.get("X-Agent-Token") == API_TOKEN


@app.post("/api/shows")
def create_show():
    if not _auth_ok(request):
        return jsonify(error="unauthorized"), 401
    name = (request.json or {}).get("name") or f"Show {time.strftime('%Y-%m-%d %H:%M')}"
    return jsonify(show_id=db.create_show(name))


@app.post("/api/shows/<int:show_id>/end")
def end_show(show_id):
    db.end_show(show_id)
    return jsonify(ok=True)


@app.post("/api/frames")
def receive_frame():
    if not _auth_ok(request):
        return jsonify(error="unauthorized"), 401
    show_id = int(request.form["show_id"])
    ts = float(request.form["ts"])
    img = request.files["image"]
    path = os.path.join(FRAMES_DIR, f"s{show_id}_{int(ts*10)}.jpg")
    img.save(path)
    frame_id = db.add_frame(show_id, ts, path)
    return jsonify(frame_id=frame_id)


@app.get("/api/shows/<int:show_id>/state")
def show_state(show_id):
    show = db.get_show(show_id)
    if not show:
        return jsonify(error="not found"), 404
    segments = build_segments(show_id)
    frames = db.frames_for_show(show_id)
    pending = sum(1 for f in frames if f["status"] == "pending")
    current = segments[-1] if segments else None
    return jsonify(show=show, segments=segments, current=current,
                   frames_total=len(frames), frames_pending=pending)


@app.post("/api/shows/<int:show_id>/confirm")
def confirm(show_id):
    d = request.json
    db.confirm_segment(show_id, d["start_ts"], d["end_ts"], d["sku"])
    return jsonify(ok=True)


@app.post("/api/catalog/upload")
def catalog_upload():
    f = request.files["file"]
    text = f.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    cols = {c.lower().strip(): c for c in reader.fieldnames or []}

    def col(*names):
        for n in names:
            if n in cols:
                return cols[n]
        return None

    c_sku = col("sku", "seller sku", "seller_sku")
    c_name = col("name", "product name", "product_name", "title")
    if not c_sku or not c_name:
        return jsonify(error="CSV must contain 'sku' and 'name' columns"), 400
    c_brand = col("brand")
    c_barcode = col("barcode", "upc", "ean", "gtin")
    c_price = col("price", "retail price")
    c_img = col("image_url", "image", "main image")

    rows = []
    for r in reader:
        sku = (r.get(c_sku) or "").strip()
        if not sku:
            continue
        rows.append({
            "sku": sku,
            "name": (r.get(c_name) or "").strip(),
            "brand": (r.get(c_brand) or "").strip() if c_brand else "",
            "barcode": (r.get(c_barcode) or "").strip() if c_barcode else "",
            "price": (r.get(c_price) or "").strip() if c_price else "",
            "image_url": (r.get(c_img) or "").strip() if c_img else "",
        })
    total = db.upsert_products(rows)
    return jsonify(imported=len(rows), catalog_total=total)


@app.get("/api/catalog")
def catalog():
    return jsonify(db.get_catalog())


@app.post("/api/shows/<int:show_id>/match_orders")
def match_orders(show_id):
    """Upload a TikTok Seller Center orders CSV; each order is assigned the SKU
    that was on screen at the order's creation time. Returns an enriched CSV."""
    show = db.get_show(show_id)
    if not show:
        return jsonify(error="show not found"), 404
    segments = build_segments(show_id)

    f = request.files["file"]
    text = f.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    fields = reader.fieldnames or []
    time_col = request.form.get("time_column") or next(
        (c for c in fields if "created" in c.lower() and "time" in c.lower()), None)
    if not time_col:
        return jsonify(error="Could not find order time column; pass time_column"), 400

    def parse_ts(val):
        for fmt in ("%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M",
                    "%d/%m/%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return time.mktime(time.strptime(val.strip(), fmt))
            except (ValueError, AttributeError):
                continue
        return None

    started = show["started_at"]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields + [
        "Matched SKU", "Matched Product", "Barcode", "Segment Start (min)", "Match Confidence"])
    writer.writeheader()
    matched = 0
    for r in reader:
        abs_ts = parse_ts(r.get(time_col, ""))
        rel = abs_ts - started if abs_ts else None
        hit = None
        if rel is not None:
            for seg in segments:
                if seg["start_ts"] - 30 <= rel <= seg["end_ts"] + 90:
                    hit = seg  # last matching segment wins (product just shown)
        if hit:
            matched += 1
            r.update({"Matched SKU": hit["sku"], "Matched Product": hit["name"],
                      "Barcode": hit["barcode"],
                      "Segment Start (min)": round(hit["start_ts"] / 60, 1),
                      "Match Confidence": round(hit["confidence"], 2)})
        else:
            r.update({"Matched SKU": "", "Matched Product": "", "Barcode": "",
                      "Segment Start (min)": "", "Match Confidence": ""})
        writer.writerow(r)

    out.seek(0)
    return send_file(io.BytesIO(out.getvalue().encode("utf-8-sig")),
                     mimetype="text/csv", as_attachment=True,
                     download_name=f"orders_matched_show{show_id}.csv")


# ---------------- dashboard ----------------

@app.get("/")
def home():
    shows = db.list_shows()
    if shows:
        return render_template("dashboard.html", show_id=shows[0]["id"], shows=shows)
    return render_template("dashboard.html", show_id=None, shows=[])


@app.get("/show/<int:show_id>")
def show_page(show_id):
    return render_template("dashboard.html", show_id=show_id, shows=db.list_shows())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
