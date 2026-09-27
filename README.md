# RVC voice conversion (GitHub Actions)

Converts audio with your [RVC](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI)
voice models automatically. Add files and push, then collect the results. Nothing to install.

## How to use

1. **Add your model** to `models/`: the `.pth` file and, if you have it, the matching `.index`
   file (for example `models/MyVoice.pth` and `models/added_IVF123_Flat_nprobe_1_MyVoice_v2.index`).
   The `.index` is optional but improves quality. Its name only has to contain the model name,
   or it can sit in the same folder as the `.pth`.
   A folder named `model/` works too.
2. **Add audio** to `input/` (wav, mp3, flac, m4a, ogg and more). Use clean vocals only: remove
   music and background noise first for best results.
3. **Push.** The *RVC voice conversion* workflow starts on its own (see the **Actions** tab).
4. **Get the result** from `output/<model-name>/` once the run finishes (it commits them back),
   or download the `converted-audio` artifact from the run page.

Files that already have an output are skipped, so each run only converts new audio.
To redo a file, delete its output and push.

## Several models

Put audio in a subfolder named after the model and it will use that model:

```
input/song.wav          -> DEFAULT_MODEL (or the only model, if there is just one)
input/MyVoice/song.wav  -> models/MyVoice.pth
input/Other/talk.mp3    -> models/Other.pth
```

## Settings

Edit [`rvc-settings.env`](rvc-settings.env): pitch shift (use `12` for male to female and
`-12` for female to male), index strength, output format and more.
Changing it starts a new run, but only audio without an output yet gets converted.

## Big model files

- The GitHub website only accepts uploads up to **25 MB**. Most `.pth` files are bigger (around 55 MB),
  so push them with `git` or [GitHub Desktop](https://desktop.github.com/) instead (up to 100 MB per file).
- Alternatively, list download links in [`models/download.txt`](models/download.txt) (`.pth`, `.index`
  or a `.zip` of both, e.g. from Google Drive or Hugging Face). They are fetched at run time and never
  stored in the repo. For Google Drive, share each file with "Anyone with the link" and paste its link.
- Keep the repo **private** if the voices or recordings are personal.

## Limits

- It runs on CPU, so expect roughly one to a few minutes per minute of audio, plus about
  5 minutes of setup per run (faster once cached).
- Inference only. Training a new model needs a GPU (e.g. Google Colab).
- Private repos get 2,000 free Actions minutes per month; public repos are unlimited.
