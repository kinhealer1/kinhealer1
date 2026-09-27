"""Free text-to-speech with fallbacks.

1. edge-tts (Microsoft Edge neural voices, no key, exact word timings)
2. Gemini TTS (free tier, needs GEMINI_API_KEY)
3. espeak-ng (offline, robotic, always available on the runner)
"""
import asyncio
import base64
import os
import re
import shutil
import subprocess
import time

import requests

from .media import duration, ffmpeg

GEMINI_TTS_MODELS = ["gemini-3.8-flash-tts", "gemini-2.5-flash-preview-tts"]


async def _edge(text, voice, rate, out):
    import edge_tts

    words = []
    com = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    with open(out, "wb") as f:
        async for chunk in com.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 1e7
                words.append((start, start + chunk["duration"] / 1e7, chunk["text"]))
    return words


def _estimate_words(text, length):
    """Spread words over the clip, weighted by length, with pauses after punctuation."""
    tokens = text.split()
    weights = [len(t) + 2 + (4 if re.search(r"[.,!?;:]$", t) else 0) for t in tokens]
    scale = length / max(sum(weights), 1)
    words, t = [], 0.0
    for tok, w in zip(tokens, weights):
        words.append((t, t + w * scale, tok))
        t += w * scale
    return words


def _gemini(text, cfg, out):
    key = os.environ["GEMINI_API_KEY"]
    style = cfg.get("gemini_tts_style", "Read this quickly, like an energetic, fast-talking YouTube Shorts narrator")
    last = None
    for model in GEMINI_TTS_MODELS:
        for attempt in range(3):
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": key},
                timeout=180,
                json={
                    "contents": [{"parts": [{"text": f"{style}: {text}"}]}],
                    "generationConfig": {
                        "responseModalities": ["AUDIO"],
                        "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": cfg.get("gemini_voice", "Charon")}}},
                    },
                },
            )
            if r.ok:
                part = r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
                raw = base64.b64decode(part["data"])
                tmp = out + ".raw"
                with open(tmp, "wb") as f:
                    f.write(raw)
                if "wav" in part["mimeType"]:
                    ffmpeg("-i", tmp, out)
                else:  # raw 16-bit PCM, e.g. audio/L16;codec=pcm;rate=24000
                    rate = re.search(r"rate=(\d+)", part["mimeType"])
                    ffmpeg("-f", "s16le", "-ar", rate.group(1) if rate else "24000", "-ac", "1", "-i", tmp, out)
                os.remove(tmp)
                # trim leading/trailing silence so scenes flow tightly
                trimmed = out + ".trim.mp3"
                speed = float(cfg.get("gemini_tts_speed", 1.3))  # Gemini voices are slow for Shorts
                ffmpeg("-i", out, "-af", "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                       f"atempo={speed}", trimmed)
                os.replace(trimmed, out)
                return _estimate_words(text, duration(out))
            last = f"{model}: {r.status_code} {r.text[:200]}"
            if r.status_code not in (429, 500, 503):
                break
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(last)


def _espeak(text, cfg, out):
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if not exe:
        raise RuntimeError("espeak-ng not installed")
    wav = out + ".wav"
    subprocess.run([exe, "-v", cfg.get("espeak_voice", "en-us"), "-s", "165", "-w", wav, text], check=True)
    ffmpeg("-i", wav, out)
    os.remove(wav)
    return _estimate_words(text, duration(out))


def _silent(text, out, wps=2.6):
    """Offline stand-in used by --offline: silence with evenly spaced word timings."""
    length = max(len(text.split()) / wps, 1.5)
    ffmpeg("-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", f"{length:.2f}", "-q:a", "9", out)
    return _estimate_words(text, length)


def speak(text, cfg, out):
    engines = []
    if cfg.get("tts", "auto") in ("auto", "edge"):
        engines.append(("edge-tts", lambda: asyncio.run(_edge(text, cfg["voice"], cfg["voice_rate"], out))))
    if cfg.get("tts", "auto") in ("auto", "gemini") and os.getenv("GEMINI_API_KEY"):
        engines.append(("gemini", lambda: _gemini(text, cfg, out)))
    engines.append(("espeak", lambda: _espeak(text, cfg, out)))
    for name, engine in engines:
        for attempt in range(2 if name == "edge-tts" else 1):
            try:
                words = engine()
                if words and os.path.getsize(out) > 0:
                    return name, words
            except Exception as e:
                print(f"[tts] {name} failed: {str(e)[:200]}")
            time.sleep(2)
    raise RuntimeError("all TTS engines failed")


def narrate(scenes, cfg, workdir, offline=False):
    """Voice each scene separately so we know exactly how long each visual must last."""
    engine = None
    i = 0
    while i < len(scenes):
        scene = scenes[i]
        out = str(workdir / f"voice_{i:02d}.mp3")
        if offline:
            words = _silent(scene["text"], out)
        else:
            used, words = speak(scene["text"], cfg, out)
            if engine and used != engine:
                # an engine gave out mid-video: re-voice from the start so there is only one narrator
                print(f"[tts] switched {engine} -> {used}, re-voicing earlier scenes")
                cfg = {**cfg, "tts": "gemini" if used == "gemini" else "espeak"}
                engine, i = used, 0
                continue
            engine = used
            if engine != "edge-tts":
                cfg = {**cfg, "tts": "gemini" if engine == "gemini" else "espeak"}
            print(f"[tts] scene {i}: {engine}")
        scene["audio"] = out
        scene["words"] = words
        scene["duration"] = duration(out) + 0.25  # small breath between scenes
        i += 1
    return scenes
