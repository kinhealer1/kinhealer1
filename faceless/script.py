"""Pick a topic and write a narration script, using only free sources."""
import json
import os
import random
import re
import time

import requests

from .config import ROOT

UA = {"User-Agent": "faceless-yt-bot/1.0 (https://github.com/kinhealer1/kinhealer1)"}

PROVIDERS = {
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY", "gemini-flash-latest"),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY", "llama-3.3-70b-versatile"),
    "ollama": ("http://localhost:11434/v1", None, "llama3.2"),
}

FALLBACK_MODELS = {"gemini": ["gemini-flash-lite-latest"], "groq": ["llama-3.1-8b-instant"]}

PROMPT = """You write scripts for a faceless YouTube Shorts channel about: {niche}.
Topic for this video: {topic}

Write a punchy narration of about {words} words. Start with a strong hook in the
first sentence, no greetings, no "in this video". End with a short question to
drive comments. Split it into 5-8 scenes. For each scene give 1-3 short, concrete
stock-footage search terms (things a camera can film, e.g. "ancient ruins",
"ocean waves", not abstract ideas).

Reply with JSON only, in this exact shape:
{{"title": "<max 90 chars, curiosity-driven, no clickbait lies>",
  "description": "<2-3 sentences>",
  "tags": ["tag1", "tag2", "..."],
  "scenes": [{{"text": "<narration>", "search": ["term", "term"]}}]}}
"""


# ---------------------------------------------------------------- topics
def next_topic(cfg):
    """Pop the first line from topics.txt; fall back to a random Wikipedia article."""
    queue = ROOT / "topics.txt"
    if queue.exists():
        lines = [l for l in queue.read_text().splitlines() if l.strip() and not l.startswith("#")]
        if lines:
            topic = lines[0].strip()
            rest = [l for l in queue.read_text().splitlines() if l.strip() != topic]
            queue.write_text("\n".join(rest) + "\n")
            return topic, None
    page = _wiki_random()
    return page["title"], page


def _wiki_random():
    for _ in range(8):
        r = requests.get("https://en.wikipedia.org/api/rest_v1/page/random/summary", headers=UA, timeout=20)
        r.raise_for_status()
        page = r.json()
        # skip stubs, lists and disambiguation pages
        if page.get("type") == "standard" and len(page.get("extract", "")) > 400 and not page["title"].startswith("List of"):
            return page
    return page


def _wiki_summary(title):
    try:
        r = requests.get(
            "https://en.wikipedia.org/api/rest_v1/page/summary/" + requests.utils.quote(title.replace(" ", "_")),
            headers=UA,
            timeout=20,
        )
    except requests.RequestException:
        return None
    return r.json() if r.ok else None


# ---------------------------------------------------------------- LLM
def _pick_provider(cfg):
    want = cfg["llm"].get("provider", "auto")
    if want != "auto":
        return want
    for name in ("gemini", "groq"):
        if os.getenv(PROVIDERS[name][1]):
            return name
    if os.getenv("OLLAMA_HOST") or _ollama_up():
        return "ollama"
    return None


def _ollama_up():
    try:
        return requests.get("http://localhost:11434/api/tags", timeout=2).ok
    except requests.RequestException:
        return False


def _llm_script(cfg, provider, topic, page):
    base, key_env, model = PROVIDERS[provider]
    base = cfg["llm"].get("base_url", base)
    model = cfg["llm"].get("model", model)
    context = f"\nBackground facts (stay accurate to these):\n{page['extract']}\n" if page else ""
    headers = {"Authorization": f"Bearer {os.getenv(key_env)}"} if key_env else {}
    prompt = PROMPT.format(niche=cfg["niche"], topic=topic, words=cfg["target_words"]) + context
    # free tiers often answer 429/503 when busy: retry, then try the lighter fallback model
    for m in [model, *FALLBACK_MODELS.get(provider, [])]:
        for attempt in range(3):
            r = requests.post(
                f"{base}/chat/completions",
                headers=headers,
                timeout=120,
                json={"model": m, "temperature": 0.8, "messages": [{"role": "user", "content": prompt}]},
            )
            if r.ok:
                text = r.json()["choices"][0]["message"]["content"]
                return json.loads(re.search(r"\{.*\}", text, re.S).group(0))
            print(f"[script] {m} answered {r.status_code}, attempt {attempt + 1}")
            if r.status_code not in (429, 500, 503):
                break
            time.sleep(10 * (attempt + 1))
    r.raise_for_status()


# ---------------------------------------------------------------- no-key fallback
HOOKS = [
    "Here is something most people never learn about {t}.",
    "You have probably never heard the real story of {t}.",
    "This is one of the strangest facts about {t}.",
]


def _template_script(topic, page):
    """No LLM available: build a script straight from the Wikipedia summary."""
    page = page or _wiki_summary(topic) or {"extract": topic, "title": topic}
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", page["extract"]) if len(s.strip()) > 20][:6]
    words = re.findall(r"[A-Za-z]{5,}", " ".join(sentences))
    common = {w for w in words if words.count(w) > 1} or set(words[:6])
    scenes = [{"text": random.choice(HOOKS).format(t=page["title"]), "search": [page["title"]]}]
    for s in sentences:
        terms = [w for w in re.findall(r"[A-Za-z]{5,}", s) if w in common][:2] or [page["title"]]
        scenes.append({"text": s, "search": terms})
    scenes.append({"text": "Did you already know this? Tell me in the comments.", "search": [page["title"]]})
    return {
        "title": f"The surprising truth about {page['title']}"[:95],
        "description": page["extract"][:300] + "\n\nSource: Wikipedia (CC BY-SA 4.0).",
        "tags": [page["title"], "facts", "did you know", "shorts"],
        "scenes": scenes,
    }


def write_script(cfg, topic=None):
    page = None
    if not topic:
        topic, page = next_topic(cfg)
    provider = _pick_provider(cfg)
    script = None
    if provider:
        try:
            script = _llm_script(cfg, provider, topic, page)
        except Exception as e:  # free tiers rate-limit; don't fail the whole run
            print(f"[script] {provider} failed ({e}); using Wikipedia template")
    if not script:
        script = _template_script(topic, page)
    script["topic"] = topic
    return script
