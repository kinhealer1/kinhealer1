"""CLI entry point: python -m faceless {run,auth}."""
import argparse
import datetime as dt
import json
import re
import tempfile
from pathlib import Path

from .config import ROOT, load_config, size
from .render import render
from .script import write_script
from .tts import narrate
from .visuals import fetch_visuals

QUEUE = ROOT / "scripts" / "queue"
DONE = ROOT / "scripts" / "done"


def _queued_script():
    """Scripts written by the ruflo agent swarm (or by you) take priority over auto-generated ones."""
    files = sorted(QUEUE.glob("*.json")) if QUEUE.exists() else []
    if not files:
        return None, None
    return json.loads(files[0].read_text()), files[0]


def run(args):
    cfg = load_config(args.config)
    if args.format:
        cfg["format"] = args.format
    dims = size(cfg)

    if args.script_file:
        script, source = json.loads(Path(args.script_file).read_text()), None
    elif not args.topic and (queued := _queued_script())[0]:
        script, source = queued
        print(f"[script] using queued script {source.name}")
    else:
        script, source = write_script(cfg, args.topic), None
    script.setdefault("topic", script["title"])
    print(f"[script] {script['title']} ({len(script['scenes'])} scenes)")

    out_dir = ROOT / "output"
    out_dir.mkdir(exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", script["title"].lower()).strip("-")[:50] or "video"
    video = out_dir / f"{dt.date.today()}-{slug}.mp4"

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        scenes = narrate(script["scenes"], cfg, work, offline=args.offline)
        total = sum(s["duration"] for s in scenes)
        if cfg["format"] == "short" and total > 179:
            print(f"[warn] {total:.0f}s is over 3 minutes, the YouTube Shorts limit")
        fetch_visuals(scenes, script, cfg, dims, work, offline=args.offline)
        render(scenes, cfg, dims, work, video)
    print(f"[render] {video} ({total:.1f}s)")

    (out_dir / f"{video.stem}.json").write_text(
        json.dumps({k: v for k, v in script.items() if k != "scenes"} | {"scenes": [{"text": s["text"], "search": s.get("search", [])} for s in script["scenes"]]}, indent=2)
    )

    video_id = None
    if args.upload:
        from .upload import upload

        video_id = upload(video, script, cfg)
    if source:
        DONE.mkdir(parents=True, exist_ok=True)
        source.rename(DONE / source.name)
    with open(ROOT / "history.jsonl", "a") as f:
        f.write(json.dumps({"date": str(dt.datetime.now(dt.timezone.utc)), "title": script["title"], "topic": script["topic"], "youtube_id": video_id}) + "\n")


def main():
    p = argparse.ArgumentParser(prog="faceless", description="Free faceless YouTube Shorts generator")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="make one video")
    r.add_argument("--topic", help="topic to cover (default: topics.txt queue, then random Wikipedia article)")
    r.add_argument("--script-file", help="use a ready-made script JSON")
    r.add_argument("--format", choices=["short", "long"])
    r.add_argument("--upload", action="store_true", help="upload to YouTube after rendering")
    r.add_argument("--offline", action="store_true", help="no network: silent audio + generated backgrounds (for testing)")
    r.add_argument("--config", help="path to channel.yaml")
    a = sub.add_parser("auth", help="one-time YouTube OAuth, run on your own computer")
    a.add_argument("client_secret", help="OAuth client JSON downloaded from Google Cloud")
    args = p.parse_args()
    if args.cmd == "auth":
        from .upload import authorize

        authorize(args.client_secret)
    else:
        run(args)
