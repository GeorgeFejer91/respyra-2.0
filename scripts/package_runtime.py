"""Stage only locked runtime packages + public product source for Windows NSIS."""
from __future__ import annotations

import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / ".for-ai-local/packaging"
ENGINE = STAGE / "engine"
PYTHON_SHA256 = "608619f8619075629c9c69f361352a0da6ed7e62f83a0e19c63e0ea32eb7629d"
PYTHON_URL = "https://www.python.org/ftp/python/3.10.11/python-3.10.11-embed-amd64.zip"


def digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest() if hasattr(hashlib, "file_digest") else hashlib.sha256(handle.read()).hexdigest()


def stage_runtime() -> None:
    if sys.version_info[:3] != (3, 10, 11) or sys.maxsize <= 2**32:
        raise RuntimeError("Package with CPython 3.10.11 x64, matching the embedded interpreter")
    if Path(sys.prefix).resolve() != (STAGE / "venv").resolve():
        raise RuntimeError("Run with the isolated, freshly synced packaging venv")
    archive = STAGE / "python-3.10.11-embed-amd64.zip"
    if digest(archive) != PYTHON_SHA256:
        raise RuntimeError("Embedded Python archive hash mismatch")
    # This fixed staging directory is owned by this script, never user data.
    if ENGINE.exists():
        if ENGINE.resolve().parent != STAGE.resolve():
            raise RuntimeError("Staging directory escaped packaging root")
        shutil.rmtree(ENGINE)
    python = ENGINE / "python"
    python.mkdir(parents=True)
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(python)
    site = python / "Lib/site-packages"
    packages = Path(sys.prefix) / "Lib/site-packages"
    def link_or_copy(source, destination):
        # Immutable build inputs: save disk space; the installer contains real files.
        try:
            os.link(source, destination)
        except OSError:
            shutil.copy2(source, destination)
        return destination
    shutil.copytree(packages, site, copy_function=link_or_copy,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "_virtualenv.*", "direct_url.json"))
    # Qt's locked wheel supplies current MSVC support. Put the same DLLs beside
    # python.exe so Windows never needs a separately installed VC redistributable.
    for support in (site / "PyQt6/Qt6/bin").glob("*140*.dll"):
        shutil.copy2(support, python / support.name)
    if list(site.glob("__editable__*")) or not (site / "mpi/event_markers/catalog.json").is_file():
        raise RuntimeError("Runtime must contain the installed project, not an editable checkout link")
    (python / "python310._pth").write_text("python310.zip\n.\nLib/site-packages\nimport site\n", encoding="utf-8")
    scripts = ENGINE / "scripts"
    scripts.mkdir()
    shutil.copy2(ROOT / "scripts/run_experiment.py", scripts)
    shutil.copy2(ROOT / "scripts/check_packaged_engine.py", scripts)
    recorder = ROOT / ".for-ai-local/recorder/runtime"
    recorder_manifest = json.loads((recorder / "manifest.json").read_text())
    if recorder_manifest["patches"] != digest(ROOT / "scripts/build_recorder.py"):
        raise RuntimeError("Native recorder was built with a different adapter patch script")
    for name, expected in recorder_manifest["adapter"].items():
        if digest(ROOT / "native/recorder" / name) != expected:
            raise RuntimeError(f"Native recorder adapter is stale: {name}")
    target = ENGINE / "recorder"
    target.mkdir()
    for name, expected in recorder_manifest["files"].items():
        if Path(name).name != name or digest(recorder / name) != expected:
            raise RuntimeError(f"Native recorder bundle hash mismatch: {name}")
        shutil.copy2(recorder / name, target / name)
    shutil.copy2(recorder / "manifest.json", target)
    notices = ENGINE / "notices"
    notices.mkdir()
    shutil.copy2(ROOT / "assets/branding/LICENSE.upstream.txt", notices)
    shutil.copy2(ROOT / "assets/branding/README.md", notices / "ARTWORK.md")
    shutil.copy2(ROOT / "docs/windows-install.md", ENGINE / "README.md")
    shutil.copy2(ROOT / "docs/THIRD-PARTY.md", notices)
    # Every distribution's original license/data/DLL files remain in site-packages.
    inventory = [{"name": d.metadata["Name"], "version": d.version,
                  "license": d.metadata.get("License-Expression") or d.metadata.get("License"),
                  "license_classifiers": [c for c in d.metadata.get_all("Classifier", []) if "License" in c],
                  "project_urls": d.metadata.get_all("Project-URL", []),
                  "source": f"https://pypi.org/project/{d.metadata['Name']}/{d.version}/#files"}
                 for d in metadata.distributions(path=[str(site)])]
    inventory.sort(key=lambda d: d["name"].lower())
    (notices / "python-packages.json").write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(ROOT / "uv.lock", notices)
    print(f"Staged {len(inventory)} locked packages; hashing installed inputs…", flush=True)
    manifest = {"product": "Respira", "version": json.loads((ROOT / "package.json").read_text())["version"],
                "platform": "windows-x86_64", "python": {"version": "3.10.11", "url": PYTHON_URL, "sha256": PYTHON_SHA256},
                "runtime_support": "App-local MSVC DLLs from the locked PyQt6-Qt6 wheel",
                "source_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)),
                "locks": {name: digest(ROOT / name) for name in ("uv.lock", "pnpm-lock.yaml", "src-tauri/Cargo.lock")},
                "files": {p.relative_to(ENGINE).as_posix(): digest(p) for p in sorted(ENGINE.rglob("*")) if p.is_file()}}
    (ENGINE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("Checking isolated Python imports, resources and liblsl…", flush=True)
    result = subprocess.run([str(python / "python.exe"), "-I", "-B", "-X", "utf8", str(scripts / "check_packaged_engine.py")], cwd=STAGE,
                            stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", timeout=90)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    print(result.stdout.strip())
    print(f"Staged {len(inventory)} locked Python distributions; {len(manifest['files'])} files")


def icons() -> None:
    # Keep the attributed logo intact; tint only the transparent circle interior.
    from PIL import Image, ImageDraw
    source = Image.open(ROOT / "assets/branding/respyra-upstream.png").convert("RGBA")
    size = max(source.size)
    canvas = Image.new("RGBA", (size, size))
    left = (size - source.width) // 2
    ImageDraw.Draw(canvas).ellipse((left + 110, 150, left + 1875, 1915), fill=(132, 191, 224, 96))
    canvas.alpha_composite(source, (left, (size - source.height) // 2))
    canvas.save(STAGE / "icon-square.png")


if __name__ == "__main__":
    if sys.argv[1:] == ["--icons"]:
        icons()
    elif not sys.argv[1:]:
        stage_runtime()
    else:
        raise SystemExit("Usage: package_runtime.py [--icons]")
