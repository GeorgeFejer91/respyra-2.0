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
    # Galata is JupyterLab's browser-test fixture, not part of the study runtime.
    # NSIS silently omitted one of its assets at a deep installation path.
    galata = site / "jupyterlab/galata"
    if galata.is_dir():
        shutil.rmtree(galata)
    for name in ("share", "etc"):
        installed_data = Path(sys.prefix) / name
        if installed_data.is_dir():
            shutil.copytree(installed_data, python / name, copy_function=link_or_copy)
    # Keep PsychoPy's declared dependencies in the locked build environment.
    # The installed study uses Tauri controls, pyglet visuals and LSL input;
    # it does not use Qt Builder, camera/video, or Arrow data interchange.
    # Exact paths fail packaging if an upstream wheel changes its layout.
    unused_runtime = (
        "Lib/site-packages/ffpyplayer",
        "Lib/site-packages/ffpyplayer-4.5.3.dist-info",
        "Lib/site-packages/imageio_ffmpeg",
        "Lib/site-packages/imageio_ffmpeg-0.6.0.dist-info",
        "share/ffpyplayer",
        "Lib/site-packages/cv2",
        "Lib/site-packages/opencv_python-5.0.0.93.dist-info",
        "Lib/site-packages/pyarrow",
        "Lib/site-packages/pyarrow.libs",
        "Lib/site-packages/pyarrow-25.0.1.dist-info",
        "Lib/site-packages/soundfile.py",
        "Lib/site-packages/_soundfile.py",
        "Lib/site-packages/_soundfile_data",
        "Lib/site-packages/soundfile-0.14.0.dist-info",
        "Lib/site-packages/vlc.py",
        "Lib/site-packages/python_vlc-3.0.21203.dist-info",
        "Lib/site-packages/questplus",
        "Lib/site-packages/questplus-2023.1.dist-info",
        "Lib/site-packages/meshpy",
        "Lib/site-packages/meshpy.libs",
        "Lib/site-packages/meshpy-2026.1.1.dist-info",
        "Lib/site-packages/tables",
        "Lib/site-packages/tables.libs",
        "Lib/site-packages/tables-3.10.1.dist-info",
        "Lib/site-packages/blosc2",
        "Lib/site-packages/blosc2-4.3.3.dist-info",
        "Lib/site-packages/pypiwin32-223.dist-info",
    )
    for relative in unused_runtime:
        path = python / relative
        if not path.exists():
            raise RuntimeError(f"Locked media payload changed: {relative}")
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    # Qt's locked wheel supplies current MSVC support. Retain only these
    # redistributable DLLs beside python.exe; the study does not use Qt itself.
    for support in (site / "PyQt6/Qt6/bin").glob("*140*.dll"):
        shutil.copy2(support, python / support.name)
    unused_qt = (
        "PyQt6", "pyqt6-6.11.0.dist-info", "pyqt6_qt6-6.11.2.dist-info",
        "pyqt6_sip-13.12.0.dist-info",
    )
    for name in unused_qt:
        path = site / name
        if not path.exists():
            raise RuntimeError(f"Locked Qt payload changed: {name}")
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
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
    shutil.copy2(ROOT / "LICENSE", notices / "RESPYRA-LICENSE.txt")
    shutil.copy2(ROOT / "assets/branding/LICENSE.upstream.txt", notices)
    shutil.copy2(ROOT / "assets/branding/README.md", notices / "ARTWORK.md")
    for name in ("PSYCHTOOLBOX-LICENSE.txt", "ESPRIMA-LICENSE.txt",
                 "ESPRIMA-LICENSE.BSD.txt", "PYPARALLEL-LICENSE.txt",
                 "PYWINRT-LICENSE.txt", "python-license-files.zip",
                 "python-source-manifest.json", "native-source-manifest.json",
                 "MPL-2.0.txt", "OPENBLAS-WINDOWS-LICENSE.txt"):
        shutil.copy2(ROOT / "licenses" / name, notices)
    shutil.copy2(ROOT / "docs/windows-install.md", ENGINE / "README.md")
    shutil.copy2(ROOT / "docs/THIRD-PARTY.md", notices)
    cargo = json.loads(subprocess.check_output(
        ["cargo", "metadata", "--manifest-path", str(ROOT / "src-tauri/Cargo.toml"),
         "--locked", "--format-version", "1", "--filter-platform", "x86_64-pc-windows-msvc"],
        cwd=ROOT, text=True, encoding="utf-8"))
    crates = []
    with zipfile.ZipFile(notices / "rust-licenses.zip", "w", zipfile.ZIP_DEFLATED,
                         strict_timestamps=False) as archive:
        for package in sorted(cargo["packages"], key=lambda item: (item["name"], item["version"])):
            crate = {key: package.get(key) for key in ("name", "version", "license", "repository", "source")}
            crate["notice_files"] = []
            if (package.get("source") or "").startswith("registry+"):
                directory = Path(package["manifest_path"]).parent
                for pattern in ("LICENSE*", "COPYING*", "NOTICE*"):
                    for path in sorted(directory.glob(pattern)):
                        if path.is_file():
                            relative = f"{package['name']}-{package['version']}/{path.name}"
                            archive.write(path, relative)
                            crate["notice_files"].append(relative)
            crates.append(crate)
    (notices / "rust-crates.json").write_text(json.dumps(crates, indent=2) + "\n", encoding="utf-8")
    # Every distribution's original license/data/DLL files remain in site-packages.
    inventory = [{"name": d.metadata["Name"], "version": d.version,
                  "license": d.metadata.get("License-Expression") or d.metadata.get("License"),
                  "license_classifiers": [c for c in d.metadata.get_all("Classifier", []) if "License" in c],
                  "project_urls": d.metadata.get_all("Project-URL", []),
                  "source": f"https://pypi.org/project/{d.metadata['Name']}/{d.version}/#files"}
                 for d in metadata.distributions(path=[str(site)])]
    inventory.sort(key=lambda d: d["name"].lower())
    sources = json.loads((notices / "python-source-manifest.json").read_text(encoding="utf-8"))
    expected = {(item["name"].lower(), item["version"]) for item in inventory
                if item["name"].lower() != "mpi"}
    actual = {(item["name"].lower(), item["version"]) for item in sources}
    if actual != expected:
        raise RuntimeError(f"Python source manifest differs from packaged runtime: {sorted(expected ^ actual)}")
    (notices / "python-packages.json").write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(ROOT / "uv.lock", notices)
    print(f"Staged {len(inventory)} locked packages; hashing installed inputs…", flush=True)
    manifest = {"product": json.loads((ROOT / "src-tauri/tauri.conf.json").read_text())["productName"],
                "version": json.loads((ROOT / "package.json").read_text())["version"],
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


if __name__ == "__main__":
    if not sys.argv[1:]:
        stage_runtime()
    else:
        raise SystemExit("Usage: package_runtime.py")
