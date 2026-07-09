"""LiveVision studio agent.

Runs on the studio PC. Takes a video source (RTMP restream from OBS, a camera
device, or a recorded video file for testing), samples one frame every N
seconds with ffmpeg, drops near-duplicate frames, and uploads the rest to the
LiveVision server over HTTPS.

Usage:
  # Test on a recorded show:
  python capture_agent.py --source recording.mp4 --server https://<railway-url> --name "Peach Live test"

  # Live RTMP from OBS (OBS sends a second output to rtmp://localhost/live):
  python capture_agent.py --source rtmp://localhost/live --server https://<railway-url> --name "Peach Live"

  # Direct camera (Windows DirectShow example):
  python capture_agent.py --source "video=USB Camera" --input-format dshow --server ...

Requires: ffmpeg on PATH, `pip install requests pillow`.
"""
import argparse
import io
import struct
import subprocess
import sys
import time

import requests
from PIL import Image

HASH_SIZE = 8          # average-hash grid
DIFF_THRESHOLD = 6     # hamming distance below this = duplicate frame, skip


def ahash(img):
    small = img.convert("L").resize((HASH_SIZE, HASH_SIZE))
    px = list(small.getdata())
    avg = sum(px) / len(px)
    bits = 0
    for p in px:
        bits = (bits << 1) | (1 if p > avg else 0)
    return bits


def hamming(a, b):
    return bin(a ^ b).count("1")


def iter_jpeg_frames(source, interval, input_format=None, realtime_file=False):
    """Yield JPEG bytes from ffmpeg, one frame per `interval` seconds."""
    cmd = ["ffmpeg", "-loglevel", "error"]
    if input_format:
        cmd += ["-f", input_format]
    if realtime_file:
        cmd += ["-re"]
    cmd += ["-i", source, "-vf", f"fps=1/{interval},scale=960:-2",
            "-f", "image2pipe", "-vcodec", "mjpeg", "-q:v", "5", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    buf = b""
    while True:
        chunk = proc.stdout.read(65536)
        if not chunk:
            break
        buf += chunk
        while True:
            start = buf.find(b"\xff\xd8")
            end = buf.find(b"\xff\xd9", start + 2)
            if start == -1 or end == -1:
                break
            yield buf[start:end + 2]
            buf = buf[end + 2:]
    proc.wait()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="RTMP URL, device, or video file")
    ap.add_argument("--server", required=True, help="LiveVision server base URL")
    ap.add_argument("--name", default=None, help="Show name")
    ap.add_argument("--interval", type=float, default=3.0, help="Seconds between frames")
    ap.add_argument("--token", default="", help="AGENT_TOKEN if the server requires it")
    ap.add_argument("--input-format", default=None, help="ffmpeg -f value (e.g. dshow)")
    ap.add_argument("--show-id", type=int, default=None, help="Attach to an existing show")
    args = ap.parse_args()

    headers = {"X-Agent-Token": args.token} if args.token else {}
    is_file = not args.source.startswith(("rtmp://", "rtsp://", "http", "video=", "/dev/"))

    show_id = args.show_id
    if show_id is None:
        name = args.name or f"Show {time.strftime('%Y-%m-%d %H:%M')}"
        r = requests.post(f"{args.server}/api/shows", json={"name": name},
                          headers=headers, timeout=15)
        r.raise_for_status()
        show_id = r.json()["show_id"]
    print(f"[agent] show #{show_id} — dashboard: {args.server}/show/{show_id}")

    started = time.time()
    last_hash = None
    sent = skipped = 0
    for i, jpeg in enumerate(iter_jpeg_frames(args.source, args.interval,
                                              args.input_format, realtime_file=is_file)):
        ts = i * args.interval if is_file else (time.time() - started)
        try:
            h = ahash(Image.open(io.BytesIO(jpeg)))
        except Exception:
            continue
        if last_hash is not None and hamming(h, last_hash) < DIFF_THRESHOLD:
            skipped += 1
            continue
        last_hash = h
        try:
            requests.post(f"{args.server}/api/frames", headers=headers, timeout=20,
                          data={"show_id": show_id, "ts": f"{ts:.1f}"},
                          files={"image": ("frame.jpg", jpeg, "image/jpeg")})
            sent += 1
            print(f"\r[agent] sent {sent}  skipped-dup {skipped}  t={ts:6.1f}s", end="")
        except requests.RequestException as e:
            print(f"\n[agent] upload failed ({e}); retrying next frame", file=sys.stderr)

    print(f"\n[agent] done. {sent} frames sent, {skipped} duplicates skipped.")
    requests.post(f"{args.server}/api/shows/{show_id}/end", headers=headers, timeout=15)


if __name__ == "__main__":
    main()
