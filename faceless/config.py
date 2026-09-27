import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULTS = {
    "niche": "surprising facts about history, science and nature",
    "language": "en",
    "voice": "en-US-AndrewNeural",
    "voice_rate": "+8%",
    "format": "short",  # short = 1080x1920 (<60s), long = 1920x1080
    "target_words": 130,
    "privacy": "private",  # private | unlisted | public
    "category_id": "27",  # Education
    "made_for_kids": False,
    "subtitle_font": "DejaVu Sans",
    "llm": {
        # Any OpenAI-compatible endpoint. All of these have free tiers / are free:
        #   gemini: https://generativelanguage.googleapis.com/v1beta/openai  (GEMINI_API_KEY)
        #   groq:   https://api.groq.com/openai/v1                           (GROQ_API_KEY)
        #   ollama: http://localhost:11434/v1                                (no key, local)
        "provider": "auto",
    },
}


def load_config(path=None):
    cfg = dict(DEFAULTS)
    path = Path(path or ROOT / "channel.yaml")
    if path.exists():
        cfg.update(yaml.safe_load(path.read_text()) or {})
    cfg["llm"] = {**DEFAULTS["llm"], **(cfg.get("llm") or {})}
    cfg["pexels_key"] = os.getenv("PEXELS_API_KEY", "")
    return cfg


def size(cfg):
    return (1080, 1920) if cfg["format"] == "short" else (1920, 1080)
