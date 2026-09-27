# Character Bible — `main-character`

Single source of truth for keeping this AI character identical across every
image and video generator (Higgsfield, Nano Banana, Midjourney, Kling, Seedance, etc.).
Paste the **Identity Block** into every prompt, unchanged. Only the scene changes.

> Original AI character. Always enable TikTok's "AI-generated content" label when posting.

---

## Higgsfield references

| Asset | ID |
|---|---|
| Element (use as `<<<id>>>` in prompts) | `5006197b-1ddb-4990-829e-426e32307dbe` |
| Front portrait (media) | `002c2ec7-a1f9-4002-bca7-5694a76f0b2d` |
| Original character sheet (media) | `876c6a6a-e0d1-4497-aab3-e3a270ab6c04` |
| Restaurant reference (media) | `616f3bf7-9690-41ad-9d7a-fbda39aa2ddb` |
| Rolls-Royce selfie video (media) | `c66b0eba-d5a0-4d0c-8186-c0c04d54d54e` |
| Clothed master sheet (image job) | `13ae2d6b-9b53-48d7-b126-ab27093168d2` |

**Always attach at least 2 references** (front portrait + a character sheet) as
`image_references`. One reference alone lets the face drift softer/younger.

---

## Locked identity

| Trait | Spec |
|---|---|
| Age | 24, adult — mature bone structure, never babyfaced |
| Skin | Deep brown, warm undertone, matte, visible pores |
| Face | Defined angular jaw, defined cheekbones, straight broad nose, full lips |
| Facial hair | Thin mustache + light chin beard |
| Eyes | Dark brown, calm, slightly hooded |
| Hair | Black short two-strand twists / starter locs (~8 cm) falling forward, crisp temple fade, sharp lined-up hairline |
| Build | ~183 cm, lean athletic, defined shoulders/arms |
| Jewelry (always) | Thick 10 mm solid gold **Cuban link** chain, round diamond stud in each ear, plain gold ring right hand |
| Signature fit | Oversized heavyweight black tee, black relaxed cargo pants, all-white low-top leather sneakers, white crew socks |

---

## Identity Block (copy-paste into every prompt)

```
the same man as the reference images, identical face: adult Black man age 24,
deep brown skin with warm undertone, mature defined angular jawline and cheekbones
(not babyfaced), straight broad nose, full lips, thin mustache and light chin beard,
calm slightly hooded dark-brown eyes, black short two-strand twists falling forward
with crisp temple fade and sharp lined-up hairline, lean athletic build,
thick 10mm gold Cuban link chain, small diamond stud in each ear,
natural skin pores and texture, no beauty filter, no airbrushing
```

## Realism tail (append to every lifestyle shot)

```
candid iPhone photo, taken by a friend, slightly off-center framing,
authentic phone-camera grain, natural light direction consistent with the scene,
true-to-life colors, no visible text or badges, no logos, no watermark,
natural hands with five fingers
```

---

## Rules that prevent AI tells (learned from test #1)

1. **Cars:** avoid open scissor/butterfly doors and close-ups of badges or sill plates —
   they come out warped or with garbled text. Prefer: leaning on the fender,
   sitting with conventional door open, interior selfie, or car in background.
2. **Chain:** always say *"thick 10mm gold Cuban link"* — otherwise it drifts to a thin rope chain.
3. **Face:** always include *"mature defined jawline, not babyfaced"* and attach 2+ references.
4. **Skin tone:** say *"deep brown"* — warm golden-hour light lightens it otherwise.
5. **Lighting:** if the sun is behind him, say *"backlit, face in soft shade"* so lighting stays physically consistent.
6. **Text:** add *"no visible text"* — AI can't spell brand names reliably.

---

## Scene prompt template

```
[SCENE: where, time of day, what he's doing],
<<<5006197b-1ddb-4990-829e-426e32307dbe>>> [IDENTITY BLOCK],
wearing [OUTFIT or "signature fit"],
[REALISM TAIL]
```

Recommended settings: `nano_banana_pro`, `9:16`, `2k`. Convert PNG → JPEG ≤1080×1920 before TikTok.
