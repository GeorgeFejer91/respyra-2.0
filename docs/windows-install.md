# Respyra 2.0 for Windows

Run `Respyra-2.0_0.3.4_x64-setup.exe` on Windows 10/11 x64. The installer lets you
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
also needs Internet access. Hardware acquisition uses a separate
[Vernier Stream Mini](https://github.com/GeorgeFejer91/Polar-Mini-Stream/releases/download/v0.6.3/Vernier-Stream-Mini_0.6.3_x64-setup.exe)
or [Polar Stream Mini](https://github.com/GeorgeFejer91/Polar-Mini-Stream/releases/download/v0.6.3/Polar-Stream-Mini_0.6.3_x64-setup.exe)
program. Respyra 2.0 owns recording; a separate LSL recorder is unnecessary.

Open Respyra 2.0 to use **Experiment control**. Select a participant number from
0 to 100 and enter any custom variable labels and values. These fields save
automatically and reload on the next launch; there is no separate Save button.
Numbers with a previously verified XDF are red in the dropdown and remain
selectable. The selected number's odd/even parity chooses the block order;
session defaults to `001` and remains only in recording metadata. A red number may have an
early-stopped recording and does not certify all trials were completed. A unique
live raw Force LSL stream connects automatically (ambiguous choices are in
**Settings**). The middle panel includes all streams and stacked live channel
previews in one plot with stream tabs and event-marker lines. The red **Start Experiment** button waits for native
recording readiness before opening PsychoPy, records raw input and markers through
calibration/cleanup, and discovers additional streams during the run. **XDF recording**
shows the file, subscribed sources and saved/failed status. PsychoPy owns participant screens. The local panel
and optional QR-linked phone retain the established controls and monitoring.

The installer creates a default `data` folder inside the chosen Respyra 2.0 program
folder. With the default per-user installation, it is
`%LOCALAPPDATA%\Respyra 2.0\data`. Click the folder icon beside **Start experiment**
to open the active recording folder. To change it, open **Settings** and choose
**Choose folder**. Respyra remembers that folder for later launches and saves
XDF, CSV, the participant list, and BIDS output there. XDFs have unique filenames.
Numeric participant entries become `P001`, `P002`, and so on in the filename;
session and each filled `label-value` pair follow as underscore-separated parts,
then a unique suffix. After a verified XDF closes, Respyra appends its filename,
participant number, session and full custom variables to `participant-list.jsonl`
in the same folder. Setup memory is stored locally in
`%LOCALAPPDATA%\Respyra\experiment-fields.json`; the recording folder is remembered
in `recording-folder.json` beside it. Existing files are not moved when the folder changes.
Recordings made by earlier versions remain in `%LOCALAPPDATA%\Respira\data`;
copy them into the new folder if you want them together. The installer does not
delete that older folder.
**Saved** means required stream data and closed XDF footers passed verification.
Failures preserve `.xdf.partial` files. The phone opens a live LSL channel/marker
monitor; select **Experiment controls** to set up the study.

The original sample and assessment CSV files are saved automatically alongside
every XDF, with their original schemas. A `bids` subfolder contains a BIDS
behavioral dataset: `sub-<number>/ses-001/beh/` holds event TSV/JSON and every
nonempty recorded LSL outlet. Fixed-rate numeric outlets use `physio.tsv.gz`/JSON;
irregular or sparse outlets use timestamped `beh.tsv`/JSON. All signal tables
retain their actual recorded sample times and sidecars describe the original
channels, units and LSL provenance. The XDF remains the authoritative archive,
including outlets with no samples. The separate CSV files retain their existing
study format. See [BIDS and MNE analysis](bids-mne.md) for opening a signal in
MNE and the explicit resampling step for irregular data. Generic physiology is
not a one-call MNE-BIDS `read_raw_bids()` neural Raw import. Source identity remains in
`%LOCALAPPDATA%\Respyra\lsl-source.json` for compatibility with prior launches.
The uninstaller is intended to remove the program and retain user
recordings/settings. That behavior has not been qualified for v0.3.4.
Startup diagnostics are in `engine.log` beside the installed Respyra program (replaced on each
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
