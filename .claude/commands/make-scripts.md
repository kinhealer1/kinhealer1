---
description: Use a ruflo agent swarm to research topics and queue fact-checked Shorts scripts
argument-hint: "[how many scripts, default 5] [optional theme]"
---
Fill `scripts/queue/` with new video scripts for the faceless channel using ruflo.

1. Read `channel.yaml` (niche, target_words), `history.jsonl` and `scripts/done/` so you don't repeat topics, and `scripts/example.json` for the exact JSON shape.
2. Start the ruflo swarm described in `ruflo-workflow.json` (research -> write -> review).
   - If the ruflo MCP tools are available, use them: init a small hierarchical swarm (max 4 agents), spawn a `researcher`, a `coder` (script writer) and a `reviewer`, then orchestrate the three stages in order, storing research notes in ruflo memory under the namespace `faceless`.
   - Otherwise run `npx ruflo@latest workflow run -f ruflo-workflow.json --task "$ARGUMENTS"` and do the stages yourself with subagents if it only records the plan.
3. Every scene needs an `"image"` prompt (one vivid, concrete picture of that moment; keep characters, place and era consistent; no text in the image) and `"search"` stock terms as a backup. The art style itself comes from `art_style` in `channel.yaml`, so leave style words out of the prompts.
4. Write $ARGUMENTS scripts (default 5) as `scripts/queue/<YYYYMMDD>-<slug>.json`. Every fact must come from a source you actually opened; list the sources at the end of the description.
5. Run `python -m faceless.check scripts/queue` and fix anything that fails.
6. Optionally preview one: `python -m faceless run --script-file scripts/queue/<file>.json`.
7. Commit and push the new queue files so the daily GitHub Action picks them up.
