"""Builds train_voice_colab.ipynb from the cells below. Run: python training/make_notebook.py"""

import json
from pathlib import Path

INTRO = """# Train an RVC voice model (Google Colab)

Makes a voice model you can use with the RVC voice conversion workflow in this repo.

**Before you start**
1. In Google Drive, make a folder (for example `RVC-datasets/Celi`) and put **10 to 30 minutes** of the voice in it.
   Clean recordings only: one person, no music, no echo, no background noise. Any common audio format works.
2. In this notebook's menu choose **Runtime > Change runtime type > T4 GPU**.

**Then** fill in the settings in step 1 and press **Runtime > Run all**. Keep this tab open while it trains.

**What you get** (in Drive, `RVC-training/<name>/`)
- `models/<name>.pth`: the finished voice model. Earlier saves like `<name>_e50_s1200.pth` are kept too, so you can compare.
- `added_..._<name>_v2.index`: the index that makes the voice sound closer to the original.
- `checkpoints/`: training progress. If Colab disconnects, run everything again with the same name and it carries on.

**Use it**: share the `.pth` and the `.index` in Drive with *Anyone with the link* and add the links in step 1 of the Voice Desk page
(or add them to `models/download.txt`).
"""

SETTINGS = r'''#@title 1. Settings { display-mode: "form" }
#@markdown Name of the voice (letters, numbers, - or _). The model file will be called `<name>.pth`.
MODEL_NAME = "Celi"  #@param {type:"string"}
#@markdown Folder in your Google Drive with the voice recordings (inside "My Drive").
DATASET_FOLDER = "RVC-datasets/Celi"  #@param {type:"string"}
#@markdown How long to train. 200 is a good start for 10-30 minutes of audio (about 1-2 hours on a T4).
EPOCHS = 200  #@param {type:"slider", min:20, max:1000, step:10}
#@markdown Save a usable model every this many epochs.
SAVE_EVERY = 25  #@param {type:"integer"}
#@markdown Lower this to 4 if you get "CUDA out of memory".
BATCH_SIZE = 8  #@param {type:"integer"}
print("Settings saved.")
'''

SETUP = r'''#@title 2. Set up (about 5 minutes) { display-mode: "form" }
import os, re, glob, json, shutil, random, subprocess, time

RVC_REF = "81eed5e8f68b6bed1789f682fe78cdd324495afc"  # same RVC version as the conversion workflow
RVC = "/content/RVC"
PY = "/content/rvcenv/bin/python"
HF = "https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main"
# PYTHONSAFEPATH: RVC's scripts sit next to train/train.py, which would otherwise
# shadow the "train" package and break their imports ("cannot import name 'utils'").
ENV = dict(os.environ, PYTHONPATH=RVC, PYTHONSAFEPATH="1")

def sh(cmd, cwd=None):
    # Print the program's output here: Colab doesn't show it otherwise, errors included.
    print("$", cmd)
    process = subprocess.Popen(cmd, shell=True, cwd=cwd, env=ENV, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for line in process.stdout:
        print(line, end="")
    if process.wait():
        raise RuntimeError("This step failed (exit code %d). The lines above say why." % process.returncode)

gpu = subprocess.run("nvidia-smi --query-gpu=name --format=csv,noheader", shell=True,
                     capture_output=True, text=True).stdout.strip()
if not gpu:
    raise SystemExit("No GPU found. Choose Runtime > Change runtime type > T4 GPU, then Runtime > Run all again.")
print("GPU:", gpu)

from google.colab import drive
drive.mount("/content/drive")

if not os.path.isdir(RVC + "/.git"):
    sh("git init -q %s && cd %s && git remote add origin "
       "https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI && "
       "git fetch -q --depth 1 origin %s && git checkout -q FETCH_HEAD" % (RVC, RVC, RVC_REF))

if not os.path.exists(PY):
    # Own Python 3.12 environment so RVC's pinned versions don't clash with Colab's.
    sh("pip install -q uv")
    sh("uv venv -q --python 3.12 /content/rvcenv")
    sh("uv pip install -q --python %s torch==2.7.1+cu128 torchaudio==2.7.1+cu128 "
       "--index-url https://download.pytorch.org/whl/cu128" % PY)
    requirements = open(RVC + "/requirments_cu128_py312.txt").read().replace(
        "https://mirrors.pku.edu.cn/pypi/simple", "https://pypi.org/simple")
    open("/content/requirements-rvc.txt", "w").write(requirements)
    sh("uv pip install -q --python %s -r /content/requirements-rvc.txt" % PY)

downloads = {
    "assets/hubert_base/config.json": "hubert_base/config.json",
    "assets/hubert_base/preprocessor_config.json": "hubert_base/preprocessor_config.json",
    "assets/hubert_base/pytorch_model.bin": "hubert_base/pytorch_model.bin",
    "assets/rmvpe/rmvpe.pt": "rmvpe.pt",
    "assets/pretrained_v2/f0G40k.pth": "pretrained_v2/f0G40k.pth",
    "assets/pretrained_v2/f0D40k.pth": "pretrained_v2/f0D40k.pth",
    "mute.zip": "mute.zip",
}
for target, source in downloads.items():
    path = os.path.join(RVC, target)
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        sh('curl -fsSL --retry 3 -o "%s" "%s/%s"' % (path, HF, source))
if not os.path.isdir(RVC + "/logs/mute"):
    sh("%s -m zipfile -e mute.zip logs" % PY, cwd=RVC)
print("Setup done.")
'''

PREPARE = r'''#@title 3. Prepare the recordings (5-15 minutes) { display-mode: "form" }
NAME = MODEL_NAME.strip()
if not re.fullmatch(r"[A-Za-z0-9_-]+", NAME):
    raise SystemExit("MODEL_NAME can only use letters, numbers, - and _.")
SOURCE = os.path.join("/content/drive/MyDrive", DATASET_FOLDER.strip().strip("/"))
OUT = "/content/drive/MyDrive/RVC-training/" + NAME
EXP = "%s/logs/%s" % (RVC, NAME)
NCPU = os.cpu_count() or 2

AUDIO = (".wav", ".mp3", ".flac", ".m4a", ".ogg", ".opus", ".aac", ".wma", ".mp4", ".webm")
files = sorted(p for p in glob.glob(SOURCE + "/**/*", recursive=True) if p.lower().endswith(AUDIO))
if not files:
    raise SystemExit("No audio found in %s. Check DATASET_FOLDER in step 1." % SOURCE)

seconds = 0.0
for path in files:
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", path], capture_output=True, text=True).stdout.strip()
    seconds += float(probe or 0)
print("%d file(s), %.1f minutes of audio." % (len(files), seconds / 60))
if seconds < 5 * 60:
    print("WARNING: under 5 minutes. The model will work but sound rough; 10-30 minutes is best.")

# Copy to local disk (much faster than reading from Drive) with simple names.
DATA = "/content/dataset/" + NAME
shutil.rmtree(DATA, ignore_errors=True)
os.makedirs(DATA)
for i, path in enumerate(files):
    shutil.copy(path, "%s/%04d%s" % (DATA, i, os.path.splitext(path)[1].lower()))

shutil.rmtree(EXP, ignore_errors=True)
os.makedirs(EXP)

def check(folder, what):
    found = len(glob.glob("%s/%s/*" % (EXP, folder)))
    if not found:
        for log in glob.glob(EXP + "/*.log"):
            print("--- " + os.path.basename(log))
            print("".join(open(log, encoding="utf8", errors="replace").readlines()[-30:]))
        raise RuntimeError(what + " produced nothing. The log above says why.")
    print("%s: %d files" % (what, found))

sh('%s train/preprocess.py "%s" 40000 %d "%s" False 3.7' % (PY, DATA, NCPU, EXP), cwd=RVC)
check("0_gt_wavs", "Slicing")
sh('%s train/dataset/extract_f0.py cuda 1 0 0 "%s" true' % (PY, EXP), cwd=RVC)
check("2a_f0", "Pitch extraction")
sh('%s train/dataset/extract_hubert_feature.py cuda:0 1 0 0 "%s" v2 true' % (PY, EXP), cwd=RVC)
check("3_feature768", "Voice features")

# The index only needs the features, so build it now and save it to Drive straight away.
sh('%s train/train_index.py "%s" v2 assets/indices %d single' % (PY, NAME, NCPU), cwd=RVC)
os.makedirs(OUT, exist_ok=True)
indexes = glob.glob(EXP + "/added_*.index")
if not indexes:
    raise RuntimeError("The index wasn't created. See %s/train_index.log" % EXP)
for path in indexes:
    shutil.copy(path, OUT)
    print("Saved to Drive:", OUT + "/" + os.path.basename(path))
'''

TRAIN = r'''#@title 4. Train (about 1-2 hours for 200 epochs) { display-mode: "form" }
# Same file list and config the RVC web UI writes before training.
names = None
for folder in ("0_gt_wavs", "3_feature768", "2a_f0", "2b-f0nsf"):
    stems = {f.split(".")[0] for f in os.listdir("%s/%s" % (EXP, folder))}
    names = stems if names is None else names & stems
lines = ["%s/0_gt_wavs/%s.wav|%s/3_feature768/%s.npy|%s/2a_f0/%s.wav.npy|%s/2b-f0nsf/%s.wav.npy|0"
         % (EXP, n, EXP, n, EXP, n, EXP, n) for n in sorted(names)]
mute = RVC + "/logs/mute"
lines += ["%s/0_gt_wavs/mute40k.wav|%s/3_feature768/mute.npy|%s/2a_f0/mute.wav.npy|%s/2b-f0nsf/mute.wav.npy|0"
          % (mute, mute, mute, mute)] * 2
random.shuffle(lines)
open(EXP + "/filelist.txt", "w").write("\n".join(lines))
config = json.load(open(RVC + "/configs/v1/40k.json"))  # the web UI uses v1/40k.json for v2 40k too
with open(EXP + "/config.json", "w") as f:
    json.dump(config, f, indent=4, sort_keys=True)
    f.write("\n")

# Keep progress and models on Drive, so nothing is lost if Colab disconnects.
os.makedirs(OUT + "/checkpoints", exist_ok=True)
os.makedirs(OUT + "/models", exist_ok=True)
for ckpt in ("G_2333333.pth", "D_2333333.pth"):
    link = "%s/%s" % (EXP, ckpt)
    if os.path.lexists(link):
        os.remove(link)
    os.symlink("%s/checkpoints/%s" % (OUT, ckpt), link)
weights = RVC + "/assets/weights"
if os.path.islink(weights) or os.path.isfile(weights):
    os.remove(weights)
elif os.path.isdir(weights):
    shutil.rmtree(weights)
os.symlink(OUT + "/models", weights)
if os.path.exists(OUT + "/checkpoints/G_2333333.pth"):
    print("Found earlier progress on Drive: carrying on from there.")

cmd = ("%s train/train.py -e %s -sr 40k -f0 1 -bs %d -g 0 -te %d -se %d "
       "-pg assets/pretrained_v2/f0G40k.pth -pd assets/pretrained_v2/f0D40k.pth "
       "-l 1 -c 0 -sw 1 -v v2" % (PY, NAME, BATCH_SIZE, EPOCHS, SAVE_EVERY))
print("$", cmd)
train_log = EXP + "/train.log"
seen = len(open(train_log, errors="replace").readlines()) if os.path.exists(train_log) else 0
console = open(EXP + "/train-console.log", "w")
process = subprocess.Popen(cmd, shell=True, cwd=RVC, env=ENV, stdout=console, stderr=subprocess.STDOUT)
while True:
    done = process.poll() is not None
    if os.path.exists(train_log):
        lines = open(train_log, encoding="utf8", errors="replace").readlines()
        for line in lines[seen:]:
            if "====>" in line or ".pth" in line or "rror" in line:
                print(line.rstrip().split("\t")[-1])
        seen = len(lines)
    if done:
        break
    time.sleep(20)

finals = glob.glob("%s/models/%s.pth" % (OUT, NAME))
if process.returncode or not finals:
    print("".join(open(EXP + "/train-console.log", errors="replace").readlines()[-40:]))
    raise RuntimeError("Training stopped early (exit code %s). The lines above say why." % process.returncode)
print("\nDone! Your model:", finals[0])
'''

FINISH = r'''#@title 5. Your files { display-mode: "form" }
for path in sorted(glob.glob(OUT + "/**/*", recursive=True)):
    if os.path.isfile(path):
        print("%8.1f MB  %s" % (os.path.getsize(path) / 1e6, path.replace("/content/drive/MyDrive/", "My Drive/")))
print("""
Next: in Google Drive, open RVC-training/%s. Share models/%s.pth and the added_...index file
with "Anyone with the link", then paste both links into step 1 of the Voice Desk page.""" % (NAME, NAME))
'''


def code(source):
    return {"cell_type": "code", "execution_count": None, "metadata": {"cellView": "form"},
            "outputs": [], "source": source.splitlines(keepends=True)}


notebook = {
    "nbformat": 4,
    "nbformat_minor": 0,
    "metadata": {
        "accelerator": "GPU",
        "colab": {"provenance": [], "gpuType": "T4"},
        "kernelspec": {"name": "python3", "display_name": "Python 3"},
        "language_info": {"name": "python"},
    },
    "cells": [
        {"cell_type": "markdown", "metadata": {}, "source": INTRO.splitlines(keepends=True)},
        code(SETTINGS), code(SETUP), code(PREPARE), code(TRAIN), code(FINISH),
    ],
}

target = Path(__file__).with_name("train_voice_colab.ipynb")
target.write_text(json.dumps(notebook, indent=1, ensure_ascii=False) + "\n")
print("Wrote", target)
