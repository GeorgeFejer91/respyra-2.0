# Respyra 2.0 for Windows

See the [default recorded-variable reference](https://georgefejer91.github.io/respyra-2.0/variables.html) for signal sources, units and interpretation, and the [study procedure](https://georgefejer91.github.io/respyra-2.0/study.html) for calibration and outputs.

**Recommended:** [Download the Respyra Suite installer](https://github.com/GeorgeFejer91/respyra-2.0/releases/download/v0.3.8/00-Respyra-Suite_0.3.8_x64-setup.exe) for Windows 10/11 x64. Its filename is
`00-Respyra-Suite_0.3.8_x64-setup.exe`; the `00-` prefix places it first in the
[v0.3.8 Release downloads](https://github.com/GeorgeFejer91/respyra-2.0/releases/tag/v0.3.8).
It installs Respyra 2.0, Polar Stream Mini, and Vernier Stream Mini, and adds four
Start menu and desktop shortcuts: one for each program and **Launch Respyra Suite**.
The latter starts the two sensor publishers and Respyra together.

Separate installers are also on the same release: [Respyra 2.0](https://github.com/GeorgeFejer91/respyra-2.0/releases/download/v0.3.8/Respyra-2.0_0.3.8_x64-setup.exe),
[Polar Stream Mini](https://github.com/GeorgeFejer91/respyra-2.0/releases/download/v0.3.8/Polar-Stream-Mini_0.6.6_x64-setup.exe),
and [Vernier Stream Mini](https://github.com/GeorgeFejer91/respyra-2.0/releases/download/v0.3.8/Vernier-Stream-Mini_0.6.6_x64-setup.exe).
The [project wiki](https://github.com/GeorgeFejer91/respyra-2.0/wiki) diagrams
the three-app data flow and explains each Mini's streams.
The installer lets you choose a destination folder, creates
a Respyra 2.0 Start menu shortcut and provides
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
also needs Internet access. Hardware acquisition uses the included Mini apps
when installed as a suite. The same release also offers separate Polar and
Vernier installers. Each Mini remembers the last successfully connected device
and, with Automatic reconnect enabled, retries that device on the next launch.
Fresh Polar settings publish the available raw ECG, ACC, heart rate and RR
outputs plus the breathing and breathing-dynamics metrics and an All-in-one
outlet. Fresh Vernier settings publish its raw device row, raw Force, breath
wave, signal events, steps, step rate, respiration rate and All-in-one.
Every Mini outlet can be unchecked; saved choices take precedence over the defaults. Respyra 2.0
owns recording; a separate LSL recorder is unnecessary.

Open Respyra 2.0 to use **Experiment control**. Select a participant number from
0 to 100 and enter any custom variable labels and values. These fields save
automatically and reload on the next launch; there is no separate Save button.
Numbers with a previously verified XDF are red in the dropdown and remain
selectable. The selected number's odd/even parity chooses the block order;
session defaults to `001` and remains only in recording metadata. A red number may have an
early-stopped recording and does not certify all trials were completed. A unique
compatible live input reconnects automatically. If several are available, the
single **Main feedback input** dropdown lets you choose Vernier Force or either
supported Polar waveform. Only this choice drives the on-screen feedback.
The middle panel includes all streams and stacked live channel
previews in one plot with stream tabs and event-marker lines. The red **Start Experiment** button waits for native
recording readiness before opening PsychoPy, records raw input and markers through
calibration/cleanup, and discovers additional streams during the run. **XDF recording**
shows the file, subscribed sources and saved/failed status. PsychoPy owns participant screens. The local panel
and optional QR-linked phone retain the established controls and monitoring.

By default, Respyra records every visible and later LSL outlet, including Mini
raw ECG, ACC, heart rate, RR, belt Force and breathing metrics when published.
It also creates a separate calibrated comparison waveform for every other live
compatible study input. Each candidate uses its own measured range from the
same calibration attempt. Three compatible inputs therefore normally produce
three raw and three Respyra-derived outlets in XDF, plus markers and other
published Mini data. The chosen input alone controls the participant display.
Unselected Polar comparison waveforms keep their native +1 direction; check
their polarity before comparing phases. Use the Record checkboxes to omit an
alternative raw input and its comparison, or turn off comparison copies in
**Settings**. The chosen input, its calibrated waveform and markers are required
while the study runs. A missing or unusable alternative is marked in the XDF
events and is not silently replaced.

The installer creates a default `data` folder inside the chosen Respyra 2.0 program
folder. With the default per-user installation, it is
`%LOCALAPPDATA%\Respyra 2.0\data`. The **Data folder** segment in the Experiment
hub shows the active path. Click **Open** to view it, **Browse** to choose
another existing folder, or paste an absolute folder path and click **Use path**.
Respyra remembers that folder for later launches and saves
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
recordings/settings. That behavior must be qualified for each installer version.
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

Build from source on Windows using the tools in the root README. Initialize
the `mini-streams` submodule and install 7-Zip before the suite build; it
extracts the Mini executables from their finalized installers.

```powershell
pnpm package:windows
pnpm package:suite
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
