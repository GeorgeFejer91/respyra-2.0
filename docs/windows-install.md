# Respyra 2.0 for Windows

Run `Respyra 2.0_0.3.2_x64-setup.exe` on Windows 10/11 x64. The installer lets you
choose a destination folder, creates a Respyra 2.0 Start menu shortcut and provides
an uninstaller. The default is a per-user installation; no administrator account
is needed for a folder your account can write. Choose another writable program
folder on the destination page if desired.

Python 3.10.11, the locked PsychoPy/Respyra/LSL study dependencies, app-local
MSVC runtime DLLs, fonts, **respyrecorder** native LSL/XDF recorder and HTML
controller are included. Qt/PyQt, OpenCV, PyArrow and FFmpeg media backends
used by unrelated PsychoPy features are omitted. Unused audio, video,
adaptive-staircase and HDF5 packages are omitted too. Users do not need Python,
Git, Node, Rust or a source checkout. If WebView2 is absent, setup downloads
its bootstrapper and runtime from Microsoft; that first installation requires
Internet access. Later launches do not need it for the local study.
The Windows Universal C Runtime supplied by Windows 10/11 is required.
QR phone pairing uses the public GitHub Pages controller and VDO.Ninja and
also needs Internet access. Hardware acquisition remains a separate
Vernier Stream Mini program. Respyra 2.0 owns recording; a separate LSL recorder is unnecessary.

Open Respyra 2.0 to use **Experiment control**. Enter participant/session and any
custom variable labels and values. These fields save automatically and reload on the
next launch; there is no separate Save button. A unique
live raw Force LSL stream connects automatically (ambiguous choices are in
**Settings**). The middle panel includes all streams and stacked live channel
previews in one plot with stream tabs and event-marker lines. The red **Start Experiment** button waits for native
recording readiness before opening PsychoPy, records raw input and markers through
calibration/cleanup, and discovers additional streams during the run. **XDF recording**
shows the file, subscribed sources and saved/failed status. PsychoPy owns participant screens. The local panel
and optional QR-linked phone retain the established controls and monitoring.

The app creates `%LOCALAPPDATA%\Respira\data` when it first opens. XDFs are
always saved there, with unique filenames.
Numeric participant entries become `P001`, `P002`, and so on in the filename;
session and each filled `label-value` pair follow as underscore-separated parts,
then a unique suffix. After a verified XDF closes, Respyra appends its filename,
participant number, session and full custom variables to `participant-list.jsonl`
in the same folder. Setup memory is stored locally in
`%LOCALAPPDATA%\Respyra\experiment-fields.json`.
The data folder keeps its previous name so existing recordings stay in place.
**Saved** means required stream data and closed XDF footers passed verification.
Failures preserve `.xdf.partial` files. The phone opens a live LSL channel/marker
monitor; select **Experiment controls** to set up the study.

**Save original CSV files locally** stays off by default. When enabled, the
original sample and assessment CSV schemas/filenames are saved in
`%LOCALAPPDATA%\Respira\data`. Program files and the source checkout are never
the installed app's recording destination. Source identity remains in
`%LOCALAPPDATA%\Respyra\lsl-source.json` for compatibility with prior launches.
Uninstall removes the program, retaining user recordings/settings.
Startup diagnostics are in `%LOCALAPPDATA%\Respira\engine.log` (replaced on each
launch); keep this local when it contains experiment identifiers.

This first installer is unsigned. Windows may show an unknown-publisher prompt.
Check its SHA-256 against the accompanying `SHA256SUMS.txt` before running it.
The same GitHub Release provides a separate source ZIP and runtime manifest;
the source ZIP is not required to install or run the program.
Respyra's original code is GPL-3.0; the installer includes its license and
third-party notices under `engine/notices/`. The exact source revision and lock
hashes are in `engine/manifest.json`.
Physical belt behavior, physical phone pairing and scientific display timing
need validation on the study computer; synthetic-source checks do not prove them.

Build from source on Windows using the tools in the root README:

```powershell
pnpm package:windows
# Regenerate icon formats from the vector logo only when needed:
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/package-windows.ps1 -GenerateIcons
```

The packaging command builds the pinned native recorder, syncs a private non-editable
locked Python environment, stages the official embedded interpreter, and checks a
synthetic native XDF round trip. Generated runtime and diagnostics
stay in `.for-ai-local/packaging/`; the final installer/checksums are in `dist/`.
After the installed artifact passes the release checks, run
`python scripts/build_release_sources.py` to assemble its matching source ZIP and
complete `dist/SHA256SUMS.txt`.
There is no self-updater or background startup task. See the bundled notices and
dependency inventory for licenses and original source links.
