"""Frame -> SKU matching using the Claude API (vision).

Strategy for a catalog of hundreds of similar beauty products:
1. The frame is sent together with a compact text catalog (SKU | brand | name).
2. Claude is asked to read any visible text on packaging (built-in OCR) and to
   return the top 3 candidate SKUs with confidence, as strict JSON.
3. If no product is clearly presented (transition, host talking, chat overlay
   only), it returns product_visible=false and the frame is marked 'skipped'.

Cost control:
- Model is configurable (default claude-haiku-4-5 — cheap and fast for frames).
- The agent already de-duplicates near-identical frames before upload.
- Catalog text is cached and only rebuilt when the catalog changes.
"""
import base64
import json
import os
import re

import anthropic

MODEL = os.environ.get("MATCH_MODEL", "claude-haiku-4-5")
MAX_CATALOG_ITEMS = int(os.environ.get("MAX_CATALOG_ITEMS", "800"))

_client = None
_catalog_cache = {"n": -1, "text": ""}


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic()  # ANTHROPIC_API_KEY from env
    return _client


def _catalog_text(catalog):
    if _catalog_cache["n"] == len(catalog):
        return _catalog_cache["text"]
    lines = []
    for p in catalog[:MAX_CATALOG_ITEMS]:
        brand = p.get("brand") or ""
        lines.append(f"{p['sku']} | {brand} | {p['name']}")
    text = "\n".join(lines)
    _catalog_cache.update(n=len(catalog), text=text)
    return text


PROMPT = """You are a product identification system for a live-commerce beauty show.
You receive one video frame from a TikTok live stream. The host presents beauty
products (skincare, makeup, tools) one at a time.

Below is the seller's product catalog (one product per line: SKU | brand | name):

<catalog>
{catalog}
</catalog>

Analyze the frame:
1. Is a product clearly being presented/held/shown right now? (Ignore background
   shelf products; only the product in focus counts.)
2. Read ALL visible text on the product packaging (brand names, product names,
   shade names, sizes).
3. Match against the catalog using the visible text, shape, color and packaging.

Respond with ONLY a JSON object, no markdown fences, exactly this schema:
{{
  "product_visible": true/false,
  "visible_text": "text you can read on the packaging, or empty string",
  "candidates": [
    {{"sku": "<sku from catalog>", "confidence": 0.0-1.0, "reason": "short reason"}}
  ]
}}
Rules:
- candidates: up to 3, best first, ONLY SKUs that appear in the catalog.
- If product_visible is false, candidates must be [].
- confidence 0.9+ only when visible text clearly matches the catalog name."""


def match_frame(image_path, catalog):
    """Returns dict: {product_visible, visible_text, candidates:[{sku,confidence,reason}]}"""
    with open(image_path, "rb") as f:
        img_b64 = base64.standard_b64encode(f.read()).decode()

    msg = _get_client().messages.create(
        model=MODEL,
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image",
                 "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}},
                {"type": "text", "text": PROMPT.format(catalog=_catalog_text(catalog))},
            ],
        }],
    )
    raw = "".join(b.text for b in msg.content if b.type == "text").strip()
    raw = re.sub(r"^```(json)?|```$", "", raw, flags=re.MULTILINE).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"product_visible": False, "visible_text": "", "candidates": [],
                "error": f"unparseable: {raw[:200]}"}

    # Keep only candidates whose SKU really exists in the catalog
    valid = {p["sku"] for p in catalog}
    cands = [c for c in data.get("candidates", []) if c.get("sku") in valid]
    return {
        "product_visible": bool(data.get("product_visible")),
        "visible_text": (data.get("visible_text") or "")[:500],
        "candidates": cands[:3],
    }
