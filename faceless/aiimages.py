"""Free AI image generation for "AI faceless" style videos.

Providers, tried in order:
  1. Cloudflare Workers AI, FLUX.1 schnell (free account: set CF_ACCOUNT_ID and
     CF_API_TOKEN; the free daily allowance covers roughly 100+ images)
  2. Pollinations.ai (no account or key; rate-limited, so requests are spaced out)
"""
import base64
import os
import random
import time
import urllib.parse

import requests

from .script import UA

NEGATIVE = "no text, no letters, no captions, no watermark, no logo"
_last_pollinations = 0.0


def _cloudflare(prompt, out, seed):
    account, token = os.getenv("CF_ACCOUNT_ID"), os.getenv("CF_API_TOKEN")
    if not (account and token):
        return None
    r = requests.post(
        f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/@cf/black-forest-labs/flux-1-schnell",
        headers={"Authorization": f"Bearer {token}"},
        json={"prompt": prompt, "steps": 8, "seed": seed},
        timeout=120,
    )
    r.raise_for_status()
    data = r.json()["result"]["image"]
    with open(out, "wb") as f:
        f.write(base64.b64decode(data))
    return out


def _pollinations(prompt, out, seed, size):
    global _last_pollinations
    wait = 16 - (time.time() - _last_pollinations)  # anonymous tier: about one image every 15s
    if wait > 0:
        time.sleep(wait)
    w, h = size
    scale = 1280 / max(w, h)  # generate ~720x1280 and let ffmpeg scale up
    url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt) + "?" + urllib.parse.urlencode(
        {"width": int(w * scale), "height": int(h * scale), "seed": seed, "model": "flux", "nologo": "true", "private": "true"}
    )
    r = requests.get(url, headers=UA, timeout=180)
    _last_pollinations = time.time()
    r.raise_for_status()
    if not r.headers.get("content-type", "").startswith("image"):
        raise RuntimeError(f"pollinations returned {r.headers.get('content-type')}")
    with open(out, "wb") as f:
        f.write(r.content)
    return out


def generate(prompt, style, out, size, seed=None):
    """Return the path of a generated image, or None if every free provider failed."""
    seed = seed if seed is not None else random.randint(1, 10**6)
    orientation = "vertical 9:16 portrait composition, subject centered" if size[1] > size[0] else "wide 16:9 composition"
    full = f"{prompt}. {style}. {orientation}. {NEGATIVE}"
    for name, fn in (("cloudflare", lambda: _cloudflare(full, out, seed)), ("pollinations", lambda: _pollinations(full, out, seed, size))):
        for attempt in range(3):
            try:
                path = fn()
                if path is None:
                    break  # provider not configured
                if os.path.getsize(path) > 10_000:
                    return path, name
            except Exception as e:
                print(f"[ai-image] {name} attempt {attempt + 1}: {str(e)[:160]}")
                time.sleep(8 * (attempt + 1))
    return None, None
