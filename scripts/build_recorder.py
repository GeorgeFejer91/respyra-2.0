"""Build the pinned native recorder with reviewed, reproducible adapter patches."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "native/recorder"
STAGE = ROOT / ".for-ai-local/recorder"
OUTPUT = STAGE / "runtime"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError("Pinned recorder patch no longer matches its source")
    return text.replace(old, new)


def build():
    lock = json.loads((SOURCE / "source-lock.json").read_text())
    STAGE.mkdir(parents=True, exist_ok=True)
    patched = STAGE / "source"
    for name, expected in lock["files"].items():
        original = SOURCE / "upstream" / name
        if sha256(original) != expected:
            raise RuntimeError(f"Recorder source hash mismatch: {name}")
        target = patched / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, target)
    cpp = patched / "src/recording.cpp"
    text = cpp.read_text()
    # Native readiness identifies the exact subscribed source, not another consumer.
    text = '#include <cmath>\n#include <cstdio>\n#include <type_traits>\n' + text
    helper = '''
static std::string hex_text(const std::string &value) {
    const char *digits = "0123456789abcdef";
    std::string result;
    for (unsigned char byte : value) { result += digits[byte >> 4]; result += digits[byte & 15]; }
    return result;
}
'''
    text = helper + text
    # Include the helper's types before its definition.
    text = '#include <string>\n' + text
    text = replace_once(text, '\t\t\tcase lsl::cf_float32:',
        '\t\t\tcase lsl::cf_int64:\n\t\t\t\ttyped_transfer_loop<int64_t>(streamid, nominal_srate, in, first_timestamp, last_timestamp, sample_count);\n\t\t\t\tbreak;\n\t\t\tcase lsl::cf_float32:')
    text = replace_once(text, '<< std::endl;\n\t\t\t}\n\t\t\tfile_.write_stream_offset',
        '<< std::endl;\n                continue; // A timed-out query has no valid offset to write.\n\t\t\t}\n\t\t\tfile_.write_stream_offset')
    text = replace_once(text, '''!result.source_id().empty() &&
\t\t\t\t\t\t\t(!known_source_ids.count(result.source_id()))''',
                        '''(result.source_id().empty() || !known_source_ids.count(result.source_id()))''')
    text = replace_once(text,
        'std::cout << "Started data collection for stream " << src.name() << "." << std::endl;',
        '''std::fprintf(stderr, "\\nRESPYRA_RECORDER/1 %s %s\\n",
            hex_text(src.source_id().empty() ? "uid:" + src.uid() : src.source_id()).c_str(),
            hex_text(src.name().empty() ? "(unnamed)" : src.name()).c_str()); std::fflush(stderr);''')
    sample_count = 'sample_count += timestamps.size();'
    if text.count(sample_count) != 2:
        raise RuntimeError("Pinned native sample notification patch no longer matches")
    text = replace_once(text, 'double sample_interval = srate ? 1.0 / srate : 0;',
                        'double sample_interval = srate ? 1.0 / srate : 0;\n\t\tbool finite_reported = false;')
    text = text.replace(sample_count, '''if (sample_count == 0 && !timestamps.empty() && !in->info().source_id().empty()) {
                std::fprintf(stderr, "\\nRESPYRA_RECORDER_DATA/1 %s\\n",
                    hex_text(in->info().source_id()).c_str()); std::fflush(stderr);
            }
            if constexpr (std::is_floating_point_v<T>) {
                if (!finite_reported && !timestamps.empty() &&
                    (in->info().source_id().rfind("respyra-breathing-", 0) == 0 ||
                     in->info().source_id().rfind("respyra-comparison-", 0) == 0)) {
                    for (const auto value : chunk) if (std::isfinite(value)) {
                        std::fprintf(stderr, "\\nRESPYRA_RECORDER_FINITE/1 %s\\n",
                            hex_text(in->info().source_id()).c_str()); std::fflush(stderr);
                        finite_reported = true;
                        break;
                    }
                }
            }
            sample_count += timestamps.size();''')
    for kind in ("record_from_query_results", "record_from_streaminfo", "record_boundaries", "record_offsets"):
        text = replace_once(text,
            f'std::cout << "Error in the {kind} thread: " << e.what() << std::endl;',
            'std::fprintf(stderr, "\\nRESPYRA_RECORDER_ERROR %s\\n", e.what()); std::fflush(stderr);')
    cpp.write_text(text, encoding="utf-8")
    header = patched / "src/recording.h"
    header.write_text(replace_once(header.read_text(), 'const double resolve_interval = 5;', 'const double resolve_interval = 1;'), encoding="utf-8")
    writer = patched / "xdfwriter/xdfwriter.cpp"
    text = '#include <filesystem>\n' + writer.read_text()
    text = replace_once(text, 'file_(filename, std::ios::binary | std::ios::trunc)',
                        'file_(std::filesystem::u8path(filename), std::ios::binary | std::ios::trunc)')
    text = replace_once(text, '// [MagicCode]',
        'file_.exceptions(std::ios::badbit | std::ios::failbit);\n\t// [MagicCode]')
    text = replace_once(text, 'file_ << content;', 'file_ << content;\n\tfile_.flush();')
    writer.write_text(text, encoding="utf-8")
    archive = STAGE / "liblsl.zip"
    if not archive.exists():
        urllib.request.urlretrieve(lock["liblsl"]["url"], archive)
    if sha256(archive) != lock["liblsl"]["sha256"]:
        raise RuntimeError("liblsl SDK archive hash mismatch")
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(STAGE / "sdk")
    sdk = STAGE / "sdk/liblsl-1.18.0-Win_amd64"
    generator = os.environ.get("CMAKE_GENERATOR") or ("NMake Makefiles" if os.environ.get("CXX") else None)
    single_config = generator is not None and not generator.startswith("Visual Studio")
    # CMake caches its generator; keep Ninja and NMake outputs separate.
    build_name = "build-ninja" if generator == "Ninja" else "build-single" if single_config else "build"
    build_dir = STAGE / build_name
    configure = ["cmake", "-S", str(SOURCE), "-B", str(build_dir)]
    configure += ["-G", generator] if generator else []
    configure += ["-DCMAKE_BUILD_TYPE=Release"] if single_config else ["-A", "x64"]
    configure += [f"-DRECORDER_SOURCE={patched.as_posix()}", f"-DCMAKE_PREFIX_PATH={sdk.as_posix()}"]
    subprocess.run(configure, check=True)
    subprocess.run(["cmake", "--build", str(build_dir), "--config", "Release"], check=True)
    OUTPUT.mkdir(exist_ok=True)
    shutil.copy2(build_dir / ("respyrecorder.exe" if single_config else "Release/respyrecorder.exe"), OUTPUT)
    # Drop the previous executable name from cached runtime bundles.
    (OUTPUT / "RespiraRecorder.exe").unlink(missing_ok=True)
    shutil.copy2(sdk / "bin/lsl.dll", OUTPUT)
    shutil.copy2(SOURCE / "upstream/LICENSE", OUTPUT / "LABRECORDER-LICENSE")
    shutil.copy2(SOURCE / "LIBLSL-LICENSE", OUTPUT / "LIBLSL-LICENSE")
    # Supply the locked engine's app-local MSVC dependencies beside the native DLL.
    support = Path(sys.prefix) / "Lib/site-packages/PyQt6/Qt6/bin"
    if not all((support / name).is_file() for name in ("msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll")):
        raise RuntimeError("Build using the locked uv environment with PyQt6's app-local MSVC DLLs")
    for dll in support.glob("*140*.dll"):
        shutil.copy2(dll, OUTPUT / dll.name)
    manifest = {"source": lock, "patches": sha256(Path(__file__)),
                "adapter": {name: sha256(SOURCE / name) for name in ("main.cpp", "CMakeLists.txt", "source-lock.json")},
                "files": {p.name: sha256(p) for p in OUTPUT.iterdir() if p.is_file() and p.name != "manifest.json"}}
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Native recorder ready: {OUTPUT}")


if __name__ == "__main__":
    build()
