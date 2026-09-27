# Faceless YouTube Shorts on autopilot, for $0

Every day, a free GitHub Action writes a script, voices it, adds stock footage and captions, renders a
vertical Short, and uploads it to your channel. [ruflo](https://github.com/ruvnet/ruflo) agents
can do the research and script writing when you want higher-quality, fact-checked videos.

```
topic ─► script ─► voice ─► footage ─► captions + render ─► YouTube
          │         │         │              │                  │
   ruflo swarm /  edge-tts  Pexels /       ffmpeg          YouTube Data
   Gemini / Groq  (free)    Wikimedia /    (free)          API (free)
   / Wikipedia              generated
```

| Piece | Tool | Cost |
|---|---|---|
| Scheduler + render machine | GitHub Actions (2,000 min/month free on private repos, unlimited on public) | free |
| Script | ruflo swarm in Claude Code, **or** Gemini / Groq free API tier, **or** local Ollama, **or** a no-key Wikipedia template | free |
| Voice | `edge-tts` (Microsoft Edge neural voices, no key) | free |
| Footage | Pexels API (free key), falls back to a Wikimedia image, then a generated background | free |
| Captions and editing | ffmpeg + libass | free |
| Upload | YouTube Data API v3 (about 6 uploads/day on the default quota) | free |

## Setup (about 20 minutes, no credit card needed)

### 1. Free keys (recommended, but it still runs without them)
- **Pexels**: sign up at <https://www.pexels.com/api/> and copy the API key → secret `PEXELS_API_KEY`
- **Gemini** (better scripts): <https://aistudio.google.com/apikey> → secret `GEMINI_API_KEY`
  (or Groq: <https://console.groq.com/keys> → `GROQ_API_KEY`)

Add secrets in GitHub under **Settings → Secrets and variables → Actions → New repository secret**.

### 2. YouTube upload access (one time, on your own computer)
1. Go to <https://console.cloud.google.com/>, create a project, and enable **YouTube Data API v3**.
2. On the **OAuth consent screen**, choose External and add yourself as a test user. Then click
   **Publish app** so it moves to *In production*. In *Testing* mode, the login stops working after 7 days.
3. Under **Credentials**, create an OAuth client ID of type **Desktop app** and download the JSON.
4. Run the one-time login:
   ```bash
   pip install -r requirements.txt
   python -m faceless auth client_secret.json
   ```
5. Save the three printed values as secrets: `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.

> **Important:** YouTube keeps every video uploaded through a new, unaudited API project **private**.
> Either switch each video to public in YouTube Studio, or fill in the free
> [API audit form](https://support.google.com/youtube/contact/yt_api_form) once to lift the limit.
> Uploads start as `privacy: private` in `channel.yaml` anyway, so you can review the first few videos.

### 3. Turn it on
Commit this repo to GitHub, open **Actions → Faceless YouTube video → Run workflow** to test it,
then leave the daily schedule running. Each rendered video is also saved as a run artifact for 7 days.

## Choosing what gets made
The pipeline picks the first source that has something, in this order:
1. `scripts/queue/*.json`: scripts written by the ruflo swarm (or by you). Best quality.
2. `topics.txt`: one topic per line. The LLM writes the script, and the used line is removed.
3. A random Wikipedia article.

### Writing scripts with ruflo
This repo registers the ruflo MCP server in `.mcp.json`. In Claude Code, run:
```
/make-scripts 7 space mysteries
```
This runs the swarm in `ruflo-workflow.json`: a **researcher** finds fresh topics with sources, a
**writer** produces the scene JSON, and a **reviewer** fact-checks it and runs
`python -m faceless.check`. The scripts go into `scripts/queue/`, and the daily Action turns
one per day into a video.

## Running locally
```bash
pip install -r requirements.txt           # ffmpeg is bundled via imageio-ffmpeg
python -m faceless run                    # next topic, no upload
python -m faceless run --topic "Black holes"
python -m faceless run --script-file scripts/example.json
python -m faceless run --offline          # no network: test the render path
python -m faceless run --upload           # needs the YT_* env vars
```
Videos are written to `output/`. For background music, add royalty-free `.mp3` files (for example
from the YouTube Studio Audio Library) to `music/`. They are mixed quietly under the voice.

## Growing the channel without getting demonetized
- YouTube demonetizes "mass-produced / repetitive" content. Scripts from the ruflo swarm or Gemini,
  a consistent niche, and accurate facts matter much more than posting volume. The no-key Wikipedia
  template is only a fallback.
- `containsSyntheticMedia` is set on every upload, because YouTube requires AI voices to be disclosed.
- Pexels footage is free for commercial use. Wikipedia text is CC BY-SA, so the source is credited in
  the description.
