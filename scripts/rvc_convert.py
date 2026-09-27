"""Convert new audio in input/ with the RVC models in models/ (or model/).

Called by .github/workflows/rvc.yml. Layout:
  input/<file>          -> converted with DEFAULT_MODEL
  input/<model>/<file>  -> converted with models/**/<model>.pth
  output/<model>/<file> -> results; files that already exist are skipped
"""

import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"
# model/ is accepted too, since it is an easy slip when uploading.
MODEL_DIRS = [MODELS, ROOT / "model"]
INPUT = ROOT / "input"
OUTPUT = ROOT / "output"
RVC_CLI = Path(os.environ.get("RVC_DIR", ROOT / "rvc")) / "infer" / "cli.py"
DOWNLOADS = MODELS / ".downloads"

AUDIO_EXTENSIONS = {
    ".wav", ".flac", ".mp3", ".m4a", ".ogg", ".opus",
    ".aac", ".wma", ".mp4", ".mkv", ".webm",
}


def setting(name, default):
    value = os.environ.get(name, "").strip()
    return value if value else default


def download_models():
    lines = []
    for folder in MODEL_DIRS:
        list_file = folder / "download.txt"
        if list_file.is_file():
            lines += list_file.read_text().splitlines()
    for line in lines:
        url = line.strip()
        if not url or url.startswith("#"):
            continue
        name = url.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
        target = DOWNLOADS / name
        if not target.exists():
            print("Downloading %s" % url)
            DOWNLOADS.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(url, target)
        if target.suffix.lower() == ".zip":
            extract_dir = DOWNLOADS / target.stem
            if not extract_dir.exists():
                with zipfile.ZipFile(target) as archive:
                    archive.extractall(extract_dir)


def model_files(pattern):
    return [path for folder in MODEL_DIRS for path in sorted(folder.rglob(pattern))]


def find_models():
    models = {}
    for path in model_files("*.pth"):
        models.setdefault(path.stem, path)
    return models


def find_index(model_path):
    stem = model_path.stem.lower()
    candidates = [
        path for path in model_files("*.index")
        if stem in path.stem.lower() and "trained" not in path.stem.lower()
    ]
    # Fall back to an index sitting next to the model (e.g. from the same zip).
    if not candidates:
        candidates = [
            path for path in model_path.parent.glob("*.index")
            if "trained" not in path.stem.lower()
        ]
    candidates.sort(key=lambda path: ("added" not in path.stem.lower(), str(path)))
    return candidates[0] if candidates else None


def collect_jobs(models, default_model, output_format):
    jobs = {}
    for path in sorted(INPUT.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in AUDIO_EXTENSIONS:
            continue
        relative = path.relative_to(INPUT)
        model_name = relative.parts[0] if len(relative.parts) > 1 else default_model
        if not model_name:
            print("::warning::Skipping %s: set DEFAULT_MODEL in rvc-settings.env "
                  "or put it in input/<model-name>/" % relative)
            continue
        if model_name not in models:
            print("::warning::Skipping %s: no models/**/%s.pth found" % (relative, model_name))
            continue
        output_file = OUTPUT / model_name / relative.with_suffix("." + output_format).name
        if output_file.exists():
            continue
        jobs.setdefault(model_name, []).append(path)
    return jobs


def main():
    download_models()
    models = find_models()
    print("Models found: %s" % (", ".join(models) or "none"))

    default_model = setting("DEFAULT_MODEL", "")
    if not default_model and len(models) == 1:
        default_model = next(iter(models))
    output_format = setting("OUTPUT_FORMAT", "wav")

    jobs = collect_jobs(models, default_model, output_format)
    if not jobs:
        print("Nothing new to convert.")
        return 0

    failed = 0
    for model_name, files in jobs.items():
        model_path = models[model_name]
        index_path = find_index(model_path)
        index_rate = setting("INDEX_RATE", "0.75")
        if index_path is None:
            print("::warning::No .index file found for %s; converting without one." % model_name)
            index_rate = "0"

        # Stage only the pending files so the CLI never sees finished ones.
        with tempfile.TemporaryDirectory() as staging:
            for path in files:
                shutil.copy2(path, Path(staging) / path.name)
            command = [
                sys.executable, str(RVC_CLI),
                "--model", str(model_path),
                "--input", staging,
                "--output", str(OUTPUT / model_name),
                "--pitch", setting("PITCH", "0"),
                "--f0-method", setting("F0_METHOD", "rmvpe"),
                "--index-rate", index_rate,
                "--protect", setting("PROTECT", "0.33"),
                "--rms-mix-rate", setting("RMS_MIX_RATE", "1.0"),
                "--format", output_format,
            ]
            if index_path is not None:
                command += ["--index", str(index_path)]
            print("::group::%s: %d file(s)" % (model_name, len(files)))
            result = subprocess.run(command)
            print("::endgroup::")
            if result.returncode != 0:
                print("::error::Conversion with %s failed" % model_name)
                failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
