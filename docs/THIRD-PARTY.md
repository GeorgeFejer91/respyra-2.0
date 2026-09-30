# Included third-party software

Respyra 2.0's original study, controller and packaging code is GPL-3.0;
`engine/notices/RESPYRA-LICENSE.txt` and the public source release contain the
license. Third-party components below retain their own licenses.

The standalone Respyra 2.0 distribution retains the original licensed dependencies
listed in `engine/notices/python-packages.json`, their metadata, original
license files, and needed DLL/data files, plus the resolved `uv.lock`. The private CPython
runtime includes its own `LICENSE.txt`. These components keep their own licenses.
PsychoPy and PyQt6 are GPL-licensed; no commercial Qt license is claimed.
The packaging environment installs PsychoPy's `ffpyplayer` and
`imageio-ffmpeg` dependencies, but the Windows application uses no video or
camera functions. Their packages and FFmpeg binaries are excluded from the
installer, together with unused OpenCV and Qt FFmpeg plugins and FFmpeg DLLs.
The locked build environment still contains those dependencies; `uv.lock` is
included to document that input, not to claim every resolved wheel is shipped.

The original Respyra package and transparent logo are by Micah Allen,
[embodied-computation-group/respyra](https://github.com/embodied-computation-group/respyra).
Its MIT copyright/license is retained. The logo provenance is in `ARTWORK.md`.
The study/controller source and packaging scripts are available in
[respyra-2.0](https://github.com/GeorgeFejer91/respyra-2.0).

Bundled Noto Sans, Pretext, QR code generator, BRSP and VDO.Ninja SDK licenses
and pinned provenance are retained with the static frontend assets. See
`vendor/remote/PROVENANCE.md` in the source repository. Microsoft WebView2 is
distributed through its official offline installer and retains Microsoft's
terms; it is not application source code.

The native recorder uses the MIT-licensed
[LabRecorder recording/XDF engine](https://github.com/labstreaminglayer/App-LabRecorder/tree/ce74750748c784774d07b6938b482c4e0608071b)
and [liblsl 1.18.0.b5](https://github.com/sccn/liblsl/tree/v1.18.0.b5).
Exact source/SDK hashes and reviewed adapter patches are in `native/recorder/`
and `scripts/build_recorder.py`. Their original notices are retained in
`engine/recorder/LABRECORDER-LICENSE` and `LIBLSL-LICENSE`; the runtime manifest
identifies the adapter and packaged binaries. No Qt LabRecorder UI is bundled.

Public release review must cover corresponding-source availability for
copyleft components and any native libraries contained inside wheels. Keeping
license notices alone does not establish that gate. Do not sign or promote a
release until its distribution review and installed runtime checks pass.
