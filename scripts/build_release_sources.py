"""Bundle the exact public source inputs beside a qualified Windows installer."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
CACHE = ROOT / ".for-ai-local/release-sources"
VENDOR = ROOT / ".for-ai-local/release-vendor"
BIDI_VENDOR = ROOT / ".for-ai-local/bidi-vendor"


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    staged = ROOT / ".for-ai-local/packaging/engine"
    runtime_path = DIST / "runtime-manifest.json"
    check(runtime_path.read_bytes() == (staged / "manifest.json").read_bytes(),
          "Staged runtime differs from the installer runtime manifest")
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    check(runtime["source_revision"] == revision and not runtime["source_dirty"],
          "Build the installer from a clean committed revision first")
    check(not subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT),
          "Commit the exact release source before creating a source bundle")
    version = runtime["version"]
    installer = DIST / f"Respyra 2.0_{version}_x64-setup.exe"
    check(installer.is_file(), "Matching NSIS installer is missing")
    installer_sha256 = digest(installer)

    python_manifest_path = staged / "notices/python-source-manifest.json"
    python_packages_path = staged / "notices/python-packages.json"
    native_manifest_path = staged / "notices/native-source-manifest.json"
    for path in (python_manifest_path, python_packages_path, native_manifest_path):
        relative = path.relative_to(staged).as_posix()
        check(digest(path) == runtime["files"][relative], f"Staged notice changed: {relative}")
    python_sources = json.loads(python_manifest_path.read_text(encoding="utf-8"))
    packages = json.loads(python_packages_path.read_text(encoding="utf-8"))
    check({(item["name"].lower(), item["version"]) for item in python_sources} ==
          {(item["name"].lower(), item["version"]) for item in packages if item["name"].lower() != "mpi"},
          "Python source list does not match the installed runtime")
    for item in python_sources:
        archive = CACHE / item["filename"]
        check(archive.is_file() and archive.stat().st_size == item["size"] and
              digest(archive) == item["sha256"], f"Source archive mismatch: {archive.name}")

    native = json.loads(native_manifest_path.read_text(encoding="utf-8"))
    for item in native["archives"]:
        archive = CACHE / item["filename"]
        check(archive.is_file() and digest(archive) == item["sha256"],
              f"Native source archive mismatch: {archive.name}")
    for item in native["binary_matches"]:
        installed = staged / item["installed"]
        check(digest(installed) == item["sha256"], f"Native binary changed: {installed.name}")
        if "wheel" in item:
            wheel = CACHE / item["wheel"]
            check(digest(wheel) == item["wheel_sha256"], f"Reference wheel changed: {wheel.name}")
            with zipfile.ZipFile(wheel) as reference:
                check(hashlib.sha256(reference.read(item["wheel_member"])).hexdigest() == item["sha256"],
                      f"Reference binary differs: {wheel.name}")
    lock = tomllib.loads((ROOT / "src-tauri/Cargo.lock").read_text(encoding="utf-8"))
    registry = {f"{item['name']}-{item['version']}": item["checksum"]
                for item in lock["package"] if item.get("source", "").startswith("registry+")}
    vendored = {directory.name: directory for directory in VENDOR.iterdir() if directory.is_dir()}
    check(set(vendored) == set(registry), "Vendored Cargo packages differ from Cargo.lock")
    for name, directory in vendored.items():
        checksum = json.loads((directory / ".cargo-checksum.json").read_text(encoding="utf-8"))
        check(checksum["package"] == registry[name], f"Vendored Cargo checksum mismatch: {name}")
        for relative, expected in checksum["files"].items():
            check(digest(directory / relative) == expected,
                  f"Vendored Cargo source changed: {name}/{relative}")
    bidi = next(item for item in python_sources if item["name"].lower() == "python-bidi")
    with tarfile.open(CACHE / bidi["filename"], "r:*") as archive:
        bidi_lock = next(member for member in archive if member.name.endswith("/Cargo.lock"))
        bidi_packages = tomllib.loads(archive.extractfile(bidi_lock).read().decode("utf-8"))["package"]
    bidi_registry = {f"{item['name']}-{item['version']}": item["checksum"]
                     for item in bidi_packages if item.get("source", "").startswith("registry+")}
    bidi_vendored = {directory.name: directory for directory in BIDI_VENDOR.iterdir() if directory.is_dir()}
    check(set(bidi_vendored) == set(bidi_registry), "python-bidi Rust sources differ from its Cargo.lock")
    for name, directory in bidi_vendored.items():
        checksum = json.loads((directory / ".cargo-checksum.json").read_text(encoding="utf-8"))
        check(checksum["package"] == bidi_registry[name], f"python-bidi crate changed: {name}")
        for relative, expected in checksum["files"].items():
            check(digest(directory / relative) == expected,
                  f"python-bidi crate source changed: {name}/{relative}")

    source_name = f"Respyra-2.0_{version}_sources.zip"
    source_path = DIST / source_name
    readme = f"""# Respyra 2.0 {version} source bundle

This bundle accompanies `{installer.name}` (SHA-256 `{installer_sha256}`).
First-party source is Git revision `{revision}`. The matching installer embeds
the runtime manifest in `engine/manifest.json`; a copy is in the release assets.

`python-sources/` contains the pinned source archive for each of the {len(python_sources)}
installed external Python distributions. `src/mpi` is the local Respyra package.
The archive names, upstream URLs, sizes and SHA-256 checksums are in
`licenses/python-source-manifest.json`; the installer carries this manifest and
its collected license notices. `native-sources/libusb-1.0.26.tar.bz2` is the
official source for Psychtoolbox's `libusb-1.0.dll`, independently matched byte
for byte to the official Windows x64 1.0.26 binary release. Its packaged DLL
SHA-256 is `{native['binary_matches'][0]['sha256']}`. Psychtoolbox's PortAudio DLL is identical to
the one in its pinned PyPI source archive.

`cargo-vendor/` contains all {len(vendored)} registry crates pinned by
`src-tauri/Cargo.lock`, including the source of the MPL-licensed crates. The
included `.cargo/config.toml` points Cargo at this directory for offline Rust
builds. `bidi-cargo-vendor/` contains the {len(bidi_vendored)} Rust crates pinned by
the LGPL python-bidi source archive's Cargo.lock. `native-sources/` also contains
GCC 8.3.0 and 10.3.0, OpenBLAS 0.3.28 and 0.3.29, the exact OpenBLAS wheel
build recipes, and the Rtools GCC recipe/patches. The NumPy/SciPy OpenBLAS DLLs
were matched byte for byte to their separately published wheel binaries; see
`licenses/native-source-manifest.json` for exact hashes and mappings.

The root project source includes the Windows installer script, recorder
adapter/patches, the native recorder source inputs, and every tracked frontend
asset. Build prerequisites and the ordinary build command are in
`docs/windows-install.md` and `scripts/package-windows.ps1`. The build recipe
fetches official CPython, WebView2 when absent, and locked binary wheels;
the source archives here provide their corresponding inspectable source.

This bundle is supplied for the exact public installer, including licenses and
the ability to inspect and modify covered code. Different platforms, optional
notebook dependencies, and unrelated development caches are outside its scope.
"""
    source_manifest = {
        "product": runtime["product"], "version": version, "source_revision": revision,
        "installer": installer.name, "installer_sha256": installer_sha256,
        "runtime_manifest_sha256": digest(runtime_path),
        "python_archives": len(python_sources), "cargo_registry_crates": len(vendored),
        "bidi_registry_crates": len(bidi_vendored), "native_archives": len(native["archives"]),
    }
    git_tar = subprocess.check_output(["git", "archive", "--format=tar", "HEAD"], cwd=ROOT)
    with zipfile.ZipFile(source_path, "w", allowZip64=True, strict_timestamps=False) as output:
        with tarfile.open(fileobj=io.BytesIO(git_tar), mode="r:") as tracked:
            for member in tracked:
                if member.isfile():
                    data = tracked.extractfile(member).read()
                    output.writestr("source/" + member.name, data, compress_type=zipfile.ZIP_DEFLATED)
        output.writestr("source/RELEASE-SOURCES.md", readme, compress_type=zipfile.ZIP_DEFLATED)
        output.writestr("source/RELEASE-SOURCES.json", json.dumps(source_manifest, indent=2) + "\n",
                        compress_type=zipfile.ZIP_DEFLATED)
        output.writestr("source/.cargo/config.toml",
                        '[source.crates-io]\nreplace-with = "vendored-sources"\n\n'
                        '[source.vendored-sources]\ndirectory = "cargo-vendor"\n',
                        compress_type=zipfile.ZIP_DEFLATED)
        for item in python_sources:
            output.write(CACHE / item["filename"], "source/python-sources/" + item["filename"],
                         compress_type=zipfile.ZIP_STORED)
        for item in native["archives"]:
            output.write(CACHE / item["filename"], "source/native-sources/" + item["filename"],
                         compress_type=zipfile.ZIP_STORED)
        for index, directory in enumerate(sorted(vendored.values())):
            for path in sorted(directory.rglob("*")):
                if path.is_file():
                    output.write(path, "source/cargo-vendor/" + path.relative_to(VENDOR).as_posix(),
                                 compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
            if (index + 1) % 100 == 0:
                print(f"Packed {index + 1}/{len(vendored)} Rust crates", flush=True)
        for directory in sorted(bidi_vendored.values()):
            for path in sorted(directory.rglob("*")):
                if path.is_file():
                    output.write(path, "source/bidi-cargo-vendor/" + path.relative_to(BIDI_VENDOR).as_posix(),
                                 compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
    sums = DIST / "SHA256SUMS.txt"
    sums.write_text(f"{installer_sha256}  {installer.name}\n{digest(source_path)}  {source_name}\n"
                    f"{digest(runtime_path)}  {runtime_path.name}\n", encoding="ascii")
    print(f"Source bundle ready: {source_path.name} ({source_path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
