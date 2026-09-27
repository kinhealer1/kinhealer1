"""Free text-to-speech via Microsoft Edge's online voices (edge-tts, no key)."""
import asyncio

from .media import duration, ffmpeg


async def _speak(text, voice, rate, out):
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


def _silent(text, out, wps=2.6):
    """Offline stand-in used by --offline: silence with evenly spaced word timings."""
    tokens = text.split()
    length = max(len(tokens) / wps, 1.5)
    ffmpeg("-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", f"{length:.2f}", "-q:a", "9", out)
    step = length / max(len(tokens), 1)
    return [(i * step, (i + 1) * step, w) for i, w in enumerate(tokens)]


def narrate(scenes, cfg, workdir, offline=False):
    """Voice each scene separately so we know exactly how long each visual must last."""
    for i, scene in enumerate(scenes):
        out = str(workdir / f"voice_{i:02d}.mp3")
        if offline:
            words = _silent(scene["text"], out)
        else:
            words = asyncio.run(_speak(scene["text"], cfg["voice"], cfg["voice_rate"], out))
        scene["audio"] = out
        scene["words"] = words
        scene["duration"] = duration(out) + 0.25  # small breath between scenes
    return scenes
