# Google Flow: putting `main-character` into a video

Flow can't swap a person inside a video you upload. Instead, you swap him into the
**first frame**, then have Veo **re-animate** that frame with the same motion.

Only use source videos that you own or have the rights to.

## References: use `flow_refs/`, not the full character sheet

A multi-panel sheet confuses video models: you get grids, duplicate people, or
panel labels in the output. Upload separate single-view images instead:

| File | Use |
|---|---|
| `flow_refs/1_face_front_outfit.jpg` | **Always**: face, chain, studs, black tee |
| `flow_refs/2_face_closeup.jpg` | **Always**: facial detail |
| `flow_refs/3_full_body.jpg` | Only for full-body shots (it's shirtless, so say "wearing ..." in the prompt) |

---

## Step 1: swap him into the first frame (Flow image editing / Nano Banana)

Take a screenshot of the first frame of the source video. Upload **frame + ref 1 + ref 2**.

```
Replace the person in the first image with the man from the second and third images.
Keep his face exactly identical: deep brown skin with warm undertone, mature defined
angular jawline, straight broad nose, full lips, thin mustache and light chin beard,
calm slightly hooded dark-brown eyes, black short two-strand twists falling forward
with a crisp temple fade and sharp lined-up hairline, small diamond stud in each ear,
thick 10mm gold Cuban link chain.
Keep everything else from the first image exactly the same: pose, body position, hand
placement, camera angle, framing, lighting, background, and the car interior.
Match the original lighting and color grade on his skin. Natural skin texture,
photorealistic, candid phone-camera look, no text, no watermark.
```

Regenerate until the face matches. **Don't move to Step 2 until the frame is right**,
because the video can only be as good as this frame.

---

## Step 2: animate it (Frames to Video)

Upload the edited frame as the **start frame**. Describe the motion from the original video.

**Example for the Rolls-Royce selfie:**
```
Handheld vertical selfie video filmed on an iPhone front camera. The same man sits in
the back seat of a Rolls-Royce at night, starlight headliner glowing above him, soft
warm interior lighting. He holds the phone at arm's length, glances at the camera, gives
a slight relaxed smile, nods to the music, and looks out the window for a moment before
looking back at the lens. Subtle natural hand shake, slight auto-exposure shifts, city
lights sliding past the window. His face, twists hairstyle, gold Cuban link chain and
diamond studs stay exactly the same in every frame. Photorealistic, natural skin
texture, real phone-video quality, no text, no subtitles, no watermark.
Audio: soft car cabin ambience and a quiet laid-back hip-hop beat from the speakers, no dialogue.
```

**Template:**
```
[Camera style: handheld selfie / friend filming / static on dashboard], vertical video.
The same man [where, time of day, lighting]. He [action 1], then [action 2], [small
natural gesture]. [Background movement]. His face, twists hairstyle, gold Cuban link
chain and diamond studs stay exactly the same in every frame. Photorealistic, natural
skin texture, real phone-video quality, no text, no subtitles, no watermark.
Audio: [ambience + music], [no dialogue / dialogue: "..."].
```

---

## Alternative: generate a brand-new scene (Ingredients to Video)

No source video needed. Upload **ref 1 + ref 2** (+ a car photo if you want a specific car):
```
The man from the reference images, [scene], [action], [camera style], vertical.
Keep his face, twists, gold Cuban link chain and diamond studs identical to the
references. Photorealistic iPhone video, natural skin texture, no text, no watermark.
```

## Tips
- Keep clips to 8 seconds; the face drifts in longer shots. To continue a shot, use **Extend**.
- If the face drifts mid-clip, pick an end frame where he still looks right and use it as the start frame of the next clip.
- Avoid the face turning fully sideways or getting covered by a hand; that's where identity breaks.
