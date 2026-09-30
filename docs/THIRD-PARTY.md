# Included third-party software

Respyra 2.0's original study, controller and packaging code is GPL-3.0;
`engine/notices/RESPYRA-LICENSE.txt` and the public source release contain the
license. Third-party components below retain their own licenses.

The Respyra 2.0 distribution retains the original licensed dependencies
listed in `engine/notices/python-packages.json`, their metadata, original
license files, and needed DLL/data files, plus the resolved `uv.lock`. Upstream
source archives are pinned in `engine/notices/python-source-manifest.json`;
license and attribution files extracted from those archives are in
`engine/notices/python-license-files.zip`. The private CPython
runtime includes its own `LICENSE.txt`. These components keep their own licenses.
PsychoPy and Go Direct are GPL-licensed. PyQt6/Qt are present in the
locked packaging environment because PsychoPy declares them, but their Qt/PyQt
modules and DLLs are omitted from the installer. Only unmodified Microsoft MSVC
support DLLs from that wheel are copied into the app-local Python runtime.
The packaging environment installs PsychoPy's `ffpyplayer` and
`imageio-ffmpeg` dependencies, but the Windows application uses no video or
camera functions. Their packages and FFmpeg binaries are excluded from the
installer, together with unused OpenCV, PyArrow, soundfile, python-vlc,
QuestPlus, MeshPy and HDF5/PyTables packages.
Jupyter and `ipympl` are notebook-only tools and are not in the installer.
The locked build environment still contains PsychoPy's media dependencies;
`uv.lock` is
included to document that input, not to claim every resolved wheel is shipped.

The original Respyra package and transparent logo are by Micah Allen,
[embodied-computation-group/respyra](https://github.com/embodied-computation-group/respyra).
Its MIT copyright/license is retained. The logo provenance is in `ARTWORK.md`.
The study/controller source and packaging scripts are available in
[respyra-2.0](https://github.com/GeorgeFejer91/respyra-2.0).

Bundled Noto Sans, Pretext, QR code generator, BRSP and VDO.Ninja SDK licenses
and pinned provenance are retained with the static frontend assets. See
`vendor/remote/PROVENANCE.md` in the source repository. Microsoft WebView2 is
downloaded from Microsoft only when absent and is not shipped in the installer.

PsychoPy's Psychtoolbox wheel includes a libusb DLL under LGPL-2.1-or-later
and an MIT-licensed PortAudio DLL. Psychtoolbox's original license and the
corresponding source of the bundled libusb belong with the public installer
release. The original mixed-license notice is included at
`engine/notices/PSYCHTOOLBOX-LICENSE.txt`. Cargo crate license texts are in
`engine/notices/rust-licenses.zip` with a version and license inventory in
`engine/notices/rust-crates.json`. Additional upstream BSD/MIT notices for
Esprima, pyParallel and PyWinRT are copied into `engine/notices/`.
`engine/notices/MPL-2.0.txt` supplies the common MPL text for Rust crates
including `selectors`, whose crate archive does not carry its own license file.
Each public installer release also carries a separate source ZIP with the exact
Python source archives, vendored Cargo crates, libusb, OpenBLAS, and GCC runtime
sources named by its installer manifest. The NumPy and SciPy OpenBLAS DLLs were
matched byte for byte to the separately published Windows OpenBLAS wheels; their
build recipes, GCC source and Rtools patches are in the source ZIP. The mapping
and hashes are in `engine/notices/native-source-manifest.json`. Source files are
separate so they do not burden installation.
The upstream wheels' identical Windows OpenBLAS/GCC runtime notice is retained
as `engine/notices/OPENBLAS-WINDOWS-LICENSE.txt`.

The native recorder uses the MIT-licensed
[LabRecorder recording/XDF engine](https://github.com/labstreaminglayer/App-LabRecorder/tree/ce74750748c784774d07b6938b482c4e0608071b)
and [liblsl 1.18.0.b5](https://github.com/sccn/liblsl/tree/v1.18.0.b5).
Exact source/SDK hashes and reviewed adapter patches are in `native/recorder/`
and `scripts/build_recorder.py`. Their original notices are retained in
`engine/recorder/LABRECORDER-LICENSE` and `LIBLSL-LICENSE`; the runtime manifest
identifies the adapter and packaged binaries. No Qt LabRecorder UI is bundled.

The source ZIP and installed notices cover the reviewed copyleft components,
including native libraries inside wheels. New dependency versions require a
fresh source and license review before publishing an installer.
