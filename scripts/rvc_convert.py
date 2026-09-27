"""Convert new audio in input/ with the RVC models in models/ (or model/).

Called by .github/workflows/rvc.yml. Layout:
  input/<file>          -> converted with DEFAULT_MODEL
  input/<model>/<file>  -> converted with models/**/<model>.pth
  input/_all/<file>     -> converted with every model (handy for comparing)
  output/<model>/<file> -> results; files that already exist are skipped
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"
# model/ is accepted too, since it is an easy slip when uploading.
MODEL_DIRS = [MODELS, ROOT / "model"]
INPUT = ROOT / "input"
OUTPUT = ROOT / "output"
RVC_DIR = (ROOT / os.environ.get("RVC_DIR", "rvc")).resolve()
RVC_CLI = RVC_DIR / "infer" / "cli.py"
DOWNLOADS = MODELS / ".downloads"
ALL_MODELS_FOLDER = "_all"

AUDIO_EXTENSIONS = {
    ".wav", ".flac", ".mp3", ".m4a", ".ogg", ".opus",
    ".aac", ".wma", ".mp4", ".mkv", ".webm",
}


def setting(name, default):
    value = os.environ.get(name, "").strip()
    return value if value else default


def google_drive_id(url):
    """Return the file ID of a Google Drive share link, or None for other links."""
    parsed = urllib.parse.urlparse(url)
    if not parsed.netloc.endswith(("drive.google.com", "docs.google.com",
                                   "drive.usercontent.google.com")):
        return None
    match = re.search(r"/file/d/([\w-]+)", parsed.path)
    if match:
        return match.group(1)
    ids = urllib.parse.parse_qs(parsed.query).get("id")
    return ids[0] if ids else None


def download_google_drive(file_id, url):
    """Download a Drive file into its own folder, keeping its real name."""
    folder = DOWNLOADS / ("gdrive-" + file_id)
    if folder.is_dir():
        files = [path for path in folder.iterdir()
                 if path.is_file() and not path.name.startswith(".")]
        if files:
            return files[0]
    print("Downloading %s from Google Drive" % url)
    # This endpoint skips the "can't scan for viruses" page for big files.
    direct = ("https://drive.usercontent.google.com/download?export=download&confirm=t&id="
              + urllib.parse.quote(file_id))
    with urllib.request.urlopen(direct) as response:
        if response.headers.get_content_type() == "text/html":
            raise SystemExit(
                "::error::Could not download %s. In Google Drive, open Share and set "
                "General access to 'Anyone with the link'. Folder links are not "
                "supported; share each file." % url)
        name = response.headers.get_filename() or (file_id + ".pth")
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / Path(name).name
        partial = folder / (".partial-" + target.name)
        with open(partial, "wb") as handle:
            shutil.copyfileobj(response, handle)
    partial.rename(target)
    return target


def download_models():
    lines = []
    # download.txt, plus any other .txt in the folder (one file per model is fine).
    for folder in MODEL_DIRS:
        for list_file in sorted(folder.glob("*.txt")):
            lines += list_file.read_text().splitlines()
    for line in lines:
        url = line.strip()
        if not url or url.startswith("#"):
            continue
        file_id = google_drive_id(url)
        if "/folders/" in url:
            print("::warning::Skipping %s: Google Drive folder links are not supported; "
                  "share each file instead." % url)
            continue
        if file_id:
            target = download_google_drive(file_id, url)
        else:
            name = url.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
            target = DOWNLOADS / name
            if not target.exists():
                print("Downloading %s" % url)
                DOWNLOADS.mkdir(parents=True, exist_ok=True)
                urllib.request.urlretrieve(url, target)
        if target.suffix.lower() == ".zip":
            extract_dir = target.with_suffix("")
            if not extract_dir.exists():
                with zipfile.ZipFile(target) as archive:
                    archive.extractall(extract_dir)


def model_files(pattern):
    return [path for folder in MODEL_DIRS for path in sorted(folder.rglob(pattern))]


def is_training_checkpoint(path):
    # RVC training also saves G_400.pth / D_400.pth (or Name_G_400.pth); these
    # can't convert audio, only the exported model can.
    return re.search(r"(^|_)[GD]_\d+$", path.stem) is not None


def find_models():
    models = {}
    for path in model_files("*.pth"):
        if is_training_checkpoint(path):
            print("::warning::Skipping %s: it is a training checkpoint, not a voice model."
                  % path.name)
            continue
        models.setdefault(path.stem, path)
    return models


def find_index(model_path):
    stem = model_path.stem.lower()
    candidates = [
        path for path in model_files("*.index")
        if stem in path.stem.lower() and "trained" not in path.stem.lower()
    ]
    # Then the name without its epoch number (Celi400.pth -> *celi*.index).
    base = re.sub(r"[\W_]*\d+$", "", stem)
    if not candidates and len(base) >= 3:
        candidates = [
            path for path in model_files("*.index")
            if base in path.stem.lower() and "trained" not in path.stem.lower()
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
        if model_name == ALL_MODELS_FOLDER:
            names = list(models)
        elif not model_name:
            print("::warning::Skipping %s: set DEFAULT_MODEL in rvc-settings.env "
                  "or put it in input/<model-name>/" % relative)
            continue
        elif model_name not in models:
            print("::warning::Skipping %s: no models/**/%s.pth found" % (relative, model_name))
            continue
        else:
            names = [model_name]
        for name in names:
            output_file = OUTPUT / name / relative.with_suffix("." + output_format).name
            if not output_file.exists():
                jobs.setdefault(name, []).append(path)
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
            # The CLI imports RVC's own packages (infer, configs), so put RVC on the path.
            env = dict(os.environ)
            env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(RVC_DIR), env.get("PYTHONPATH")]))
            result = subprocess.run(command, env=env)
            print("::endgroup::")
            if result.returncode != 0:
                print("::error::Conversion with %s failed" % model_name)
                failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
