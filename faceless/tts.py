"""Free text-to-speech with fallbacks.

1. edge-tts (Microsoft Edge neural voices, no key, exact word timings)
2. Gemini TTS (free tier, needs GEMINI_API_KEY). The free tier allows about 10
   requests per model per day, so the whole script is voiced in ONE request and
   then cut into scenes at the natural pauses. Several TTS models are rotated.
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

from .media import duration, ffmpeg, ffmpeg_exe

# each model has its own free daily quota; when one is used up the next is tried
GEMINI_TTS_MODELS = ["gemini-3.8-flash-tts", "gemini-2.5-flash-preview-tts", "gemini-3.1-flash-tts-preview", "gemini-3.8-flash-lite-tts"]
PAUSE = 0.25  # breath between scenes


# ---------------------------------------------------------------- edge-tts
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


def _edge_scenes(scenes, cfg, workdir):
    for i, scene in enumerate(scenes):
        out = str(workdir / f"voice_{i:02d}.mp3")
        for attempt in range(3):
            try:
                words = asyncio.run(_edge(scene["text"], cfg["voice"], cfg["voice_rate"], out))
                if words and os.path.getsize(out) > 0:
                    break
            except Exception as e:
                print(f"[tts] edge-tts scene {i} attempt {attempt + 1}: {str(e)[:150]}")
            time.sleep(3 * (attempt + 1))
        else:
            raise RuntimeError(f"edge-tts gave no audio for scene {i}")
        _set(scene, out, words)


# ---------------------------------------------------------------- Gemini (one request per video)
def _syllables(token):
    word = token.lower()
    digits = re.sub(r"\D", "", word)
    if digits:  # "1932" is spoken "nineteen thirty-two": numbers are long when read aloud
        return 1.4 * len(digits) + len(re.findall(r"[a-z]+", word))
    return max(1, len(re.findall(r"[aeiouy]+", word)))


def _weights(text):
    """Relative speaking time per word: syllables plus a pause after punctuation."""
    return [_syllables(t) + (1.5 if re.search(r"[.,!?;:]$", t) else 0) for t in text.split()]


def _estimate_words(text, length):
    """Spread words over the clip, weighted by length, with pauses after punctuation."""
    tokens, weights = text.split(), _weights(text)
    scale = length / max(sum(weights), 1)
    words, t = [], 0.0
    for tok, w in zip(tokens, weights):
        words.append((t, t + w * scale, tok))
        t += w * scale
    return words


def _silences(path):
    """(midpoint, length) of every pause in the narration (ffmpeg silencedetect)."""
    res = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-i", str(path), "-af", "silencedetect=noise=-38dB:d=0.18", "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", res.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", res.stderr)]
    return [((s + e) / 2, e - s) for s, e in zip(starts, ends)]


def _gemini_request(text, cfg):
    """Returns (bytes, mime). Only the narration is sent: any instruction in the
    prompt risks being read out loud, so pace is fixed afterwards with atempo."""
    key = os.environ["GEMINI_API_KEY"]
    last = None
    for model in GEMINI_TTS_MODELS:
        for attempt in range(3):
            try:
                r = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    headers={"x-goog-api-key": key},
                    timeout=300,
                    json={
                        "contents": [{"parts": [{"text": text}]}],
                        "generationConfig": {
                            "responseModalities": ["AUDIO"],
                            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": cfg.get("gemini_voice", "Charon")}}},
                        },
                    },
                )
            except requests.RequestException as e:
                last = f"{model}: {e}"
                time.sleep(5 * (attempt + 1))
                continue
            if r.ok:
                part = r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
                print(f"[tts] gemini voice from {model}")
                return base64.b64decode(part["data"]), part["mimeType"]
            last = f"{model}: {r.status_code} {r.text[:200]}"
            if r.status_code == 429 and "PerDay" in r.text:
                print(f"[tts] {model} daily free quota used up, trying next model")
                break
            if r.status_code not in (429, 500, 502, 503, 504):
                break
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(last)


def _gemini_scenes(scenes, cfg, workdir):
    # blank lines between scenes make the voice pause there, which we use to cut
    raw, mime = _gemini_request("\n\n".join(s["text"] for s in scenes), cfg)
    src = str(workdir / "gemini.raw")
    with open(src, "wb") as f:
        f.write(raw)
    full = str(workdir / "gemini_full.mp3")
    speed = float(cfg.get("gemini_tts_speed", 1.2))  # Gemini voices are slow for Shorts
    trim = "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse"
    if "wav" in mime:
        ffmpeg("-i", src, "-af", f"{trim},atempo={speed}", full)
    else:  # raw 16-bit PCM, e.g. audio/L16;codec=pcm;rate=24000
        rate = re.search(r"rate=(\d+)", mime)
        ffmpeg("-f", "s16le", "-ar", rate.group(1) if rate else "24000", "-ac", "1", "-i", src, "-af", f"{trim},atempo={speed}", full)

    # expected scene boundaries from text length, snapped to the nearest real pause
    total = duration(full)
    weights = [sum(_weights(s["text"])) for s in scenes]
    pauses = _silences(full)
    cuts, acc = [0.0], 0
    for w in weights[:-1]:
        acc += w
        guess = total * acc / sum(weights)
        near = [(mid, length) for mid, length in pauses if abs(mid - guess) < 2.0 and mid > cuts[-1] + 0.5]
        cuts.append(min(near, key=lambda p: abs(p[0] - guess))[0] if near else guess)
    cuts.append(total)

    for i, scene in enumerate(scenes):
        out = str(workdir / f"voice_{i:02d}.mp3")
        ffmpeg("-i", full, "-ss", f"{cuts[i]:.3f}", "-to", f"{cuts[i + 1]:.3f}", out)
        _set(scene, out, _estimate_words(scene["text"], duration(out)))


# ---------------------------------------------------------------- espeak / offline
def _espeak_scenes(scenes, cfg, workdir):
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if not exe:
        raise RuntimeError("espeak-ng not installed")
    for i, scene in enumerate(scenes):
        out = str(workdir / f"voice_{i:02d}.mp3")
        wav = out + ".wav"
        subprocess.run([exe, "-v", cfg.get("espeak_voice", "en-us"), "-s", "165", "-w", wav, scene["text"]], check=True)
        ffmpeg("-i", wav, out)
        os.remove(wav)
        _set(scene, out, _estimate_words(scene["text"], duration(out)))


def _silent_scenes(scenes, cfg, workdir, wps=2.6):
    """Offline stand-in used by --offline: silence with evenly spaced word timings."""
    for i, scene in enumerate(scenes):
        out = str(workdir / f"voice_{i:02d}.mp3")
        length = max(len(scene["text"].split()) / wps, 1.5)
        ffmpeg("-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", f"{length:.2f}", "-q:a", "9", out)
        _set(scene, out, _estimate_words(scene["text"], length))


def _set(scene, out, words):
    scene["audio"] = out
    scene["words"] = words
    scene["duration"] = duration(out) + PAUSE


def narrate(scenes, cfg, workdir, offline=False):
    """Voice the whole video with ONE engine so there is only one narrator."""
    if offline:
        return _silent_scenes(scenes, cfg, workdir) or scenes
    want = cfg.get("tts", "auto")
    engines = []
    if want in ("auto", "edge"):
        engines.append(("edge-tts", _edge_scenes))
    if want in ("auto", "gemini") and os.getenv("GEMINI_API_KEY"):
        engines.append(("gemini", _gemini_scenes))
    engines.append(("espeak", _espeak_scenes))
    for name, engine in engines:
        try:
            engine(scenes, cfg, workdir)
            print(f"[tts] voiced all {len(scenes)} scenes with {name}")
            return scenes
        except Exception as e:
            print(f"[tts] {name} failed: {str(e)[:300]}")
    raise RuntimeError("all TTS engines failed")
