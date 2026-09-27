"""Validate script JSON files: python -m faceless.check scripts/queue"""
import json
import sys
from pathlib import Path


def problems(data):
    out = []
    for key in ("title", "description", "scenes"):
        if not data.get(key):
            out.append(f"missing {key}")
    if len(data.get("title", "")) > 100:
        out.append("title over 100 chars")
    scenes = data.get("scenes", [])
    if not 3 <= len(scenes) <= 12:
        out.append(f"{len(scenes)} scenes (want 3-12)")
    for i, s in enumerate(scenes):
        if not s.get("text"):
            out.append(f"scene {i} has no text")
        if not s.get("search"):
            out.append(f"scene {i} has no search terms")
    words = sum(len(s.get("text", "").split()) for s in scenes)
    if words > 160:
        out.append(f"{words} words: too long for a <60s Short")
    return out


def main(paths):
    files = [f for p in paths for f in (sorted(Path(p).glob("*.json")) if Path(p).is_dir() else [Path(p)])]
    bad = 0
    for f in files:
        try:
            issues = problems(json.loads(f.read_text()))
        except json.JSONDecodeError as e:
            issues = [f"invalid JSON: {e}"]
        print(f"{'FAIL' if issues else 'ok  '} {f}" + "".join(f"\n     - {i}" for i in issues))
        bad += bool(issues)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main(sys.argv[1:] or ["scripts/queue"])
