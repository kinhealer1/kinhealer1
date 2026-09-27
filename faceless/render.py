"""Assemble scenes + narration + burned-in captions into the final MP4 with ffmpeg."""
import random

from .config import ROOT
from .media import duration, ffmpeg

FPS = 30


def _segment(scene, size, out):
    w, h = size
    dur = f"{scene['duration']:.3f}"
    if scene["kind"] == "video":
        inputs = ["-stream_loop", "-1", "-i", scene["visual"]]
        vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={FPS},setsar=1"
    else:
        # Ken Burns: slow zoom into a still image
        frames = int(scene["duration"] * FPS) + 1
        inputs = ["-i", scene["visual"]]
        vf = (
            f"scale={int(w * 1.5)}:{int(h * 1.5)}:force_original_aspect_ratio=increase,"
            f"crop={int(w * 1.5)}:{int(h * 1.5)},"
            f"zoompan=z='1+0.18*on/{frames}':d={frames}:s={w}x{h}:fps={FPS}"
            ":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',setsar=1"
        )
    ffmpeg(
        *inputs, "-i", scene["audio"],
        "-map", "0:v", "-map", "1:a", "-t", dur,
        "-vf", vf, "-af", f"apad=whole_dur={dur}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
        out,
    )


def _ts(t):
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def write_captions(scenes, size, font, out, per_line=3):
    """Short, punchy word-group captions in the middle of the frame (Shorts style)."""
    w, h = size
    fs = int(w * 0.085)
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {w}", f"PlayResY: {h}", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Cap,{font},{fs},&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,{max(fs // 12, 3)},2,5,60,60,0,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    offset = 0.0
    for scene in scenes:
        words = scene["words"]
        for i in range(0, len(words), per_line):
            group = words[i : i + per_line]
            start = offset + group[0][0]
            nxt = words[i + per_line][0] if i + per_line < len(words) else group[-1][1] + 0.2
            text = " ".join(g[2] for g in group).upper().replace("{", "(").replace("}", ")")
            lines.append(f"Dialogue: 0,{_ts(start)},{_ts(offset + nxt)},Cap,,0,0,0,,{{\\fscx110\\fscy110\\t(0,90,\\fscx100\\fscy100)}}{text}")
        offset += scene["duration"]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def render(scenes, cfg, size, workdir, out):
    parts = []
    for i, scene in enumerate(scenes):
        part = workdir / f"seg_{i:02d}.mp4"
        _segment(scene, size, part)
        parts.append(part)
    listing = workdir / "concat.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in parts))
    joined = workdir / "joined.mp4"
    ffmpeg("-f", "concat", "-safe", "0", "-i", listing, "-c", "copy", joined)

    captions = write_captions(scenes, size, cfg["subtitle_font"], workdir / "captions.ass")
    vf = f"ass={captions.as_posix()}"
    music = sorted((ROOT / "music").glob("*.mp3")) if (ROOT / "music").exists() else []
    if music:
        # royalty-free background track (e.g. from the YouTube Audio Library), ducked under the voice
        track = random.choice(music)
        total = duration(joined)
        ffmpeg(
            "-i", joined, "-stream_loop", "-1", "-i", track,
            "-filter_complex", f"[0:v]{vf}[v];[1:a]volume=0.12,atrim=0:{total:.2f}[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[a]",
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
            "-movflags", "+faststart", out,
        )
    else:
        ffmpeg(
            "-i", joined, "-vf", vf,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "copy",
            "-movflags", "+faststart", out,
        )
    return out
