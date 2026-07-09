# LiveVision — On-Air Product Recognition for TikTok Live Commerce

Identifies which product is being presented on a live show in real time, links it
to its SKU / barcode / catalog data, and cross-matches incoming orders to the
product that was on screen when each order was placed.

**Architecture (Route 1 — stream split at the source):**

```
Studio PC (OBS / camera / recording)
   └─ capture_agent.py  → samples 1 frame / 3s, drops duplicates
        └─ HTTPS POST → LiveVision server (Railway)
             ├─ Claude API vision matcher (frame → top-3 SKU candidates)
             ├─ SQLite timeline (segments: "12:34–15:02 = SKU X")
             ├─ Live dashboard (/show/<id>) with one-click confirm
             └─ Order matcher (To_Ship CSV → enriched with Matched SKU + Barcode)
```

No connection to TikTok's servers is needed — the video is captured at the
studio, so nothing breaks if TikTok changes anything.

---

## 1. Deploy the server (Railway)

1. Push the `server/` folder to a GitHub repo (or add it as a second service in
   the existing packing-station repo).
2. In Railway: **New Service → GitHub repo**, root directory = `server/`.
   The Dockerfile is picked up automatically.
3. Add a **Volume** mounted at `/data` (stores the DB + frame images).
4. Environment variables:
   | Variable | Value |
   |---|---|
   | `ANTHROPIC_API_KEY` | your Claude API key |
   | `MATCH_MODEL` | `claude-haiku-4-5` (default; cheap/fast) |
   | `AGENT_TOKEN` | any random string — shared secret for the agent |
   | `SEGMENT_GAP` | `20` — max gap (sec) to merge frames into one segment |
   | `MIN_CONFIDENCE` | `0.35` — below this a frame is skipped |
5. Open the public URL → dashboard.

## 2. Load the product catalog

Export products from TikTok Shop Seller Center (or Shopify) as CSV with at least
`sku` and `name` columns (`brand`, `barcode`, `price`, `image_url` recognized
automatically), then upload it from the dashboard ("Upload catalog CSV") or:

```bash
curl -F "file=@catalog.csv" https://<server>/api/catalog/upload
```

## 3. Test on a recorded show (do this first)

On any PC with ffmpeg installed:

```bash
cd agent
pip install -r requirements.txt
python capture_agent.py --source last_show_recording.mp4 \
    --server https://<railway-url> --token <AGENT_TOKEN> --name "Peach test run"
```

Open the dashboard — segments appear as the recording is processed. Confirm or
correct each segment with one click.

## 4. Go live

**If you broadcast with OBS:** install the *Multiple RTMP Outputs* plugin, add a
second output to a local RTMP relay (e.g. [MediaMTX](https://github.com/bluenviron/mediamtx),
one .exe, zero config), then run:

```bash
python capture_agent.py --source rtmp://localhost:1935/live \
    --server https://<railway-url> --token <AGENT_TOKEN> --name "Peach Live 07/05"
```

**If you broadcast from a phone:** point a cheap second camera (or capture card
on an HDMI splitter) at the presentation table and use it as the agent source:

```bash
python capture_agent.py --source "video=USB Camera" --input-format dshow ...
```

## 5. Match orders after (or during) the show

Upload the To_Ship CSV from Seller Center on the dashboard ("Match orders CSV").
Each order gets `Matched SKU`, `Matched Product`, `Barcode` and
`Match Confidence` columns based on what was on screen at the order's creation
time (window: 30s before segment start to 90s after segment end).

> Order times in the CSV must be in the same timezone as the server clock.
> Railway defaults to UTC — set the `TZ` env var to `America/New_York` so show
> start times and Seller Center times line up.

---

## Cost estimate

At 1 frame / 3s with duplicate-dropping, a 4-hour show produces roughly
1,500–2,500 analyzed frames. With claude-haiku and a ~500-product catalog in the
prompt, expect a few dollars per show. Prompt caching of the catalog block can
cut this further (next iteration).

## Roadmap (next iterations)

- **Audio transcription** of the host (product names spoken aloud) fused with
  the visual match — the biggest accuracy jump for similar-looking beauty SKUs.
- **Prompt caching** for the catalog block (~90% input-token saving).
- **Learning loop**: confirmed segments become few-shot examples per SKU.
- **Auto order sync** via TikTok Shop webhooks instead of CSV upload.
- **/cs + packing-station integration**: matched SKU flows into the daily show
  report and the packing video index.
