"""Find a free visual for every scene.

Order of preference:
  1. Pexels stock video (free API key, commercial use allowed, no attribution required)
  2. Wikimedia image of the topic (no key)
  3. A generated gradient card (always works, fully offline)
"""
import random

import requests
from PIL import Image, ImageDraw, ImageFilter

from .script import UA, _wiki_summary

PALETTES = [((20, 30, 70), (120, 40, 140)), ((10, 60, 60), (20, 140, 110)), ((70, 20, 20), (200, 90, 40)), ((15, 15, 25), (60, 70, 110))]


def _pexels(term, key, portrait, used):
    r = requests.get(
        "https://api.pexels.com/videos/search",
        headers={"Authorization": key},
        params={"query": term, "per_page": 15, "orientation": "portrait" if portrait else "landscape", "size": "medium"},
        timeout=30,
    )
    r.raise_for_status()
    for video in r.json().get("videos", []):
        if video["id"] in used or video["duration"] < 3:
            continue
        files = [f for f in video["video_files"] if f.get("width") and f["file_type"] == "video/mp4"]
        # smallest file that is still >= 720p on the short side: fast downloads, good enough quality
        files.sort(key=lambda f: f["width"] * f["height"])
        good = [f for f in files if min(f["width"], f["height"]) >= 720] or files
        if good:
            used.add(video["id"])
            return good[0]["link"]
    return None


def _download(url, out):
    with requests.get(url, headers=UA, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(out, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
    return out


def gradient_card(out, size, seed=0):
    rnd = random.Random(seed)
    (a, b) = rnd.choice(PALETTES)
    w, h = size
    img = Image.new("RGB", (w, h))
    px = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        px.line([(0, y), (w, y)], fill=tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)))
    # soft bokeh blobs so the Ken Burns zoom has something to move over
    blobs = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(blobs)
    for _ in range(14):
        x, y, r = rnd.randint(0, w), rnd.randint(0, h), rnd.randint(w // 12, w // 4)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, rnd.randint(12, 40)))
    img = Image.alpha_composite(img.convert("RGBA"), blobs.filter(ImageFilter.GaussianBlur(40))).convert("RGB")
    img.save(out, quality=92)
    return out


def fetch_visuals(scenes, script, cfg, size, workdir, offline=False):
    portrait = size[1] > size[0]
    used = set()
    wiki_img = None
    for i, scene in enumerate(scenes):
        scene["visual"], scene["kind"] = None, "image"
        if not offline and cfg["pexels_key"]:
            for term in scene.get("search", []) + [script["topic"]]:
                try:
                    link = _pexels(term, cfg["pexels_key"], portrait, used)
                except requests.RequestException as e:
                    print(f"[visuals] pexels error for {term!r}: {e}")
                    link = None
                if link:
                    scene["visual"] = _download(link, workdir / f"clip_{i:02d}.mp4")
                    scene["kind"] = "video"
                    break
        if not scene["visual"] and not offline:
            if wiki_img is None:
                page = _wiki_summary(script["topic"]) or {}
                src = (page.get("originalimage") or page.get("thumbnail") or {}).get("source")
                wiki_img = _download(src, workdir / "wiki.jpg") if src else ""
            scene["visual"] = wiki_img or None
        if not scene["visual"]:
            scene["visual"] = gradient_card(workdir / f"card_{i:02d}.jpg", size, seed=i)
        print(f"[visuals] scene {i}: {scene['kind']} {scene['visual']}")
    return scenes
