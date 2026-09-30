"""Pin source archives and collect notices for the exact staged Python runtime."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import tarfile
from urllib.request import urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".for-ai-local/release-sources"
NOTICES = ROOT / "licenses"
PACKAGES = ROOT / ".for-ai-local/packaging/engine/notices/python-packages.json"


def source_for(package: dict) -> dict:
    name, version = package["name"], package["version"]
    if name.lower() == "pywin32":
        return {"name": name, "version": version, "filename": "pywin32-b312.zip",
                "url": "https://codeload.github.com/mhammond/pywin32/zip/refs/tags/b312"}
    with urlopen(f"https://pypi.org/pypi/{name}/{version}/json", timeout=30) as response:
        release = json.load(response)
    sources = [file for file in release["urls"] if file["packagetype"] == "sdist"]
    if len(sources) != 1:
        raise RuntimeError(f"Expected one source archive for {name}=={version}: {len(sources)}")
    file = sources[0]
    return {"name": name, "version": version, "filename": file["filename"],
            "url": file["url"], "sha256": file["digests"]["sha256"], "size": file["size"]}


def fetch(item: dict) -> dict:
    path = CACHE / item["filename"]
    if not path.is_file():
        with urlopen(item["url"], timeout=180) as response, path.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
    size = path.stat().st_size
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if "sha256" in item and (item["sha256"] != digest or item["size"] != size):
        raise RuntimeError(f"Source checksum mismatch: {item['filename']}")
    item.update(sha256=digest, size=size)
    return item


def members(path: Path):
    if path.name.endswith(".zip"):
        with zipfile.ZipFile(path) as source:
            for member in source.infolist():
                if not member.is_dir():
                    yield member.filename, source.read(member)
    else:
        with tarfile.open(path, "r:*") as source:
            for member in source:
                if member.isfile():
                    handle = source.extractfile(member)
                    if handle:
                        yield member.name, handle.read()


def notice_name(name: str) -> bool:
    filename = Path(name).name.lower()
    return filename.startswith(("license", "licence", "copying", "notice", "copyright", "authors"))


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    NOTICES.mkdir(exist_ok=True)
    packages = json.loads(PACKAGES.read_text(encoding="utf-8"))
    packages = [package for package in packages if package["name"].lower() not in {"mpi", "pypiwin32"}]
    with ThreadPoolExecutor(max_workers=12) as workers:
        sources = list(workers.map(source_for, packages))
        sources = list(workers.map(fetch, sources))
    sources.sort(key=lambda item: item["name"].lower())
    output = NOTICES / "python-license-files.zip"
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, strict_timestamps=False) as archive:
        for item in sources:
            count = 0
            prefix = f"{item['name']}-{item['version']}"
            for name, data in members(CACHE / item["filename"]):
                parts = Path(name.replace("\\", "/")).parts
                if ".." in parts or not notice_name(name):
                    continue
                relative = "/".join(parts[1:]) if len(parts) > 1 else parts[0]
                info = zipfile.ZipInfo(f"{prefix}/{relative}", date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, data)
                count += 1
            item["notice_files"] = count
    (NOTICES / "python-source-manifest.json").write_text(json.dumps(sources, indent=2) + "\n", encoding="utf-8")
    print(f"Pinned {len(sources)} source archives, {sum(item['size'] for item in sources)/1048576:.1f} MiB; "
          f"license archive {output.stat().st_size/1048576:.1f} MiB")
    print("No license files in source:", [(item["name"], item["version"]) for item in sources
                                          if not item["notice_files"]])


if __name__ == "__main__":
    main()
