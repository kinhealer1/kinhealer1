"""Thin ffmpeg helpers. Uses system ffmpeg if present, else the pip-bundled binary."""
import re
import shutil
import subprocess


def ffmpeg_exe():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def ffmpeg(*args):
    cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", *map(str, args)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode:
        raise RuntimeError(f"ffmpeg failed: {' '.join(cmd)}\n{res.stderr[-2000:]}")


def duration(path):
    """Media duration in seconds (no ffprobe needed)."""
    res = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", res.stderr)
    if not m:
        raise RuntimeError(f"could not read duration of {path}")
    h, mnt, s = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(s)
