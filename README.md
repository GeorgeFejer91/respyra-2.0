# Respyra 2.0

**[Download Respyra Suite for Windows](https://github.com/GeorgeFejer91/respyra-2.0/releases/download/v2.3.13/00-Respyra-Suite_2.3.13_x64-setup.exe)** · [Separate installers](https://github.com/GeorgeFejer91/respyra-2.0/releases/tag/v2.3.13) · [Project wiki and data-flow diagrams](https://github.com/GeorgeFejer91/respyra-2.0/wiki) · [Installation guide](docs/windows-install.md) · [Project website](https://georgefejer91.github.io/respyra-2.0/)

Respyra 2.0 is a Windows app for a Python breathing target-tracking study. The PsychoPy task asks
participants to follow a breathing target while visual feedback is normal,
amplified, attenuated, or absent. Vernier Stream Mini can publish raw belt Force;
Polar Stream Mini can publish two signed ACC-derived breathing candidates.
Respyra accepts either source through LSL, publishes an event-marker stream,
and records LSL to XDF automatically.

The study builds on [the original respyra toolbox by Micah Allen and the Embodied Computation Group](https://github.com/embodied-computation-group/respyra). Cite its preprint when using that work: Allen, M. (2026). *respyra: A General-Purpose Respiratory Tracking Toolbox for Interoception Research*. [PsyArXiv](https://osf.io/preprints/psyarxiv/wjuce_v1).

Respyra 2.0 is developed by George Fejer. The project site includes a [default recorded-variable reference](https://georgefejer91.github.io/respyra-2.0/variables.html), [study procedure](https://georgefejer91.github.io/respyra-2.0/study.html) and [credits with Scholar/ORCID links](https://georgefejer91.github.io/respyra-2.0/about.html).

The pinned `mini-streams` submodule provides [Vernier Stream Mini and Polar Stream Mini](https://github.com/GeorgeFejer91/Polar-Mini-Stream). `pnpm package:suite` builds both individual Mini installers, the separate Respyra installer, and a suite installer with all three applications and a common launcher. Clone with `git clone --recurse-submodules` to build the suite.

The **v2.3.13 Windows suite preview** is the primary download above. Its installer provides four desktop and Start menu shortcuts: Respyra 2.0, Polar Stream Mini, Vernier Stream Mini, and **Launch Respyra Suite**. All [four installers and their checksums](https://github.com/GeorgeFejer91/respyra-2.0/releases/tag/v2.3.13) are on this repository's GitHub Release. Fresh Polar preferences select ECG, three-axis accelerometer, native heart rate/RR, Chest Motion, Chest Motion DT and Flowborne phase, with required readiness flags; other Polar metrics remain optional. Vernier defaults to raw device data (including Force) and connection events; its other six outputs remain optional. Respyra has one main feedback-input selector and records every visible LSL stream by default, with a separately calibrated comparison outlet for each other live compatible input. Closing a study recording automatically produces its six-panel summary from the verified XDF. The Data folder path is visible and editable. Settings and Record boxes allow opt-outs. Physical Bluetooth reconnect and real-device recording remain unqualified for this preview.

The importable Python package keeps its original name, `mpi`.

Respyra 2.0's original study, controller and packaging code is licensed under
[GPL-3.0](LICENSE). Bundled third-party components retain their own licenses;
see [third-party notices](docs/THIRD-PARTY.md).

## Windows program

The **Respyra 2.0** installer includes **respyrecorder**, the native LSL/XDF recorder, and a locked Python/PsychoPy engine.
If WebView2 is missing, setup downloads it from Microsoft. It allows choosing the installation folder and
creates a Start menu shortcut. See [Windows installation](docs/windows-install.md)
for build/download checks, writable CSV location and qualification limits.
The attributed original [Respyra logo](assets/branding/README.md) is included.

## Setup

The [experiment audit](docs/experiment-audit.md) compares this study with the
original import. Suite 2.3.13 adds
[UTC/Berlin timestamp fields](docs/timestamps.md), using an optional free HTTPS
reference and automatic offline computer-clock fallback.

Use Python 3.10, [`uv`](https://docs.astral.sh/uv/), Node/pnpm, Rust/Cargo,
and the Tauri Windows prerequisites (MSVC build tools and WebView2). From the
checkout, launch the desktop app:

```powershell
python -m uv sync --frozen --python 3.10.11
pnpm install --frozen-lockfile
pnpm prepare:recorder
# If Cargo is not already in PATH:
$env:PATH = "$env:USERPROFILE\.cargo\bin;$env:PATH"
pnpm tauri dev
```

To build a development executable, run `pnpm tauri build --debug --no-bundle`;
it uses the checkout's `.venv`. For the standalone release installer, run
`pnpm package:windows`. Release builds require the packaged engine and never
fall back to development Python.

Running the experiment requires a working PsychoPy display and one accepted
breathing input from [Polar-Mini-Stream](https://github.com/GeorgeFejer91/Polar-Mini-Stream):
Vernier's raw Force outlet or Polar's signed PCA or signed Phan outlet in
**Separate Streams** mode. [Polar input contracts](docs/polar-input-contracts.md)
describe the exact waveform metadata, validity companions and calibration.
Launch Respyra; its **Respyra-Events** outlet (type **Markers**) is advertised
at Python-engine startup, before breathing-input selection or PsychoPy initialization.
**Start Experiment** starts the bundled **respyrecorder** and requires selected input
samples and actual marker reception by the recorder before opening PsychoPy.
Recording includes calibration and study cleanup. Additional LSL streams join
when discovered, including streams started later. No separate recorder is required.
The first window is
the **Experiment control** panel with participant and breathing-input setup.
The three-part control center shows a participant-number dropdown (0–100) at the top,
one shared plot with stacked live channels, stream tabs and event markers in the middle, and a
red **Start Experiment** button at the bottom. All streams are included
automatically. Additional channels are paged without dropping them. Select the
participant number, then Start. Odd/even participant parity determines the study's
block order. Numbers with a previously verified XDF are red and remain selectable;
the legacy session metadata defaults to 001.

Respyra automatically discovers and connects a unique compatible breathing
input. The **Main feedback input** dropdown shows compatible Vernier and Polar
streams found by the LSL scan; choosing one makes it the study input. Discovery lists visible
streams and reasons for rejecting incompatible study inputs. It
requires Vernier's metadata-identified Force channel in **N**, or one of the
two exact Polar contracts with its live validity flags. All require floating-point
samples and a unique stable source ID. Polar also requires the experimenter to
choose whether inhalation raises or lowers the waveform. The run stops if valid
samples disappear.

**Respyra-Calibrated-Breathing** is advertised before recording and contains
NaN until calibration. It then publishes the selected signal centered and
scaled by its calibrated amplitude, retaining the raw inlet's synchronized
timestamps and calibration metadata. Values are not clipped or adjusted by
condition feedback gain. The recorder must receive this stream before trials
begin, and final XDF verification requires its samples. Its compact indicator
shows waiting, recording, then saved.

Optional **Keyboard events** and **Mouse events** record Windows key down/up,
mouse movement, buttons and wheel as markers during recording, within Respyra's
controller and participant windows. Both default off. Callback LSL time is
retained separately from marker publication time; normal study response markers
remain automatic. Recording folder, source selection, marker naming and diagnostics are in
**Settings**.

The accepted source ID is saved in `%LOCALAPPDATA%/Respyra/lsl-source.json`
on Windows (otherwise `$LOCALAPPDATA`, or `~/.config/Respyra`). Later launches
automatically reconnect that exact source and recheck metadata and live data;
no repeated scan or acceptance is needed. Missing, changed, duplicate, or
incompatible outlets keep Start unavailable; missing/restarted outlets retry
automatically. There is no automatic switch to
another source. Each accepted inlet stays pinned to that outlet; a streamer
restart is revalidated before connection. Settings contain only source
identity/name, never breathing samples or participant details.
`RESPYRA_LSL_SOURCE_ID`, when set, overrides
the saved identity on launch; remove it to use remembered UI selections.

The first window is the experimenter-facing HTML control window in Tauri's
WebView. After Start Experiment, PsychoPy presents the original instructions,
calibration, trials, and assessments in its separate participant window.
Experiment control remains available for monitoring and **Stop experiment**;
on one display it may sit behind PsychoPy's full-screen window. Use a second
display or the phone controller to monitor without taking participant focus.
**XDF recording** shows subscribed streams, the local file, bytes and completion
status. Wait for **Saved** before closing. Discovery and connection
run in one Python setup worker; experiment input keeps the existing nonblocking
LSL read path. Qt is not used by this study or controller; Qt modules are
omitted from the Windows installer while PsychoPy's study and timing modules
remain bundled.

Every run saves the original sample CSV columns and companion
`-self-assessment.csv` file alongside the XDF in the remembered recording
folder, using the existing respyra logger. The Experiment hub shows the path;
you can open, browse, or paste an existing folder there. A `bids/` subfolder contains behavioral
events and every nonempty recorded LSL stream in BIDS TSV/JSON form, with
fixed-rate signals as physiology and irregular signals as timed tables. The
[BIDS and MNE guide](docs/bids-mne.md) shows how to open these signals. CSV writes flush
each row and may add disk latency. The one-channel
`Respyra-Events` stream sends named JSON markers documented in
[`src/mpi/event_markers/catalog.json`](src/mpi/event_markers/catalog.json).
Marker output is independent of recorder connection. Setup events sent before
recording may be absent from the file. The final HTML result and Close markers
follow XDF finalization. A complete `.xdf` requires matching chunk counts and
closed footers, with data from the required input, calibrated output and study
events. Failed files retain
`.xdf.partial`; inspect them before analysis.
The marker outlet's default name is **Respyra-Events**; change it in **Marker name**
before any recorder subscribes or the experiment starts.
The HTML participant form marks each field key press and text edit, Start/Cancel
button clicks, accept/reject, and final field values. LSL selection, scan
results, connection outcomes, saved-source actions, and source loss also send
named markers. The final Close button and native closure also have markers.
Python publishes the single marker stream in order. Controller actions include
global `ui_seq`, `ui_origin`, browser `ui_client_seq` and `ui_time_ms`; their LSL timestamp describes Python observing
the action after IPC. Browser time is a separate clock and must not be aligned
directly with breathing samples. Experiment screen/phase onset markers remain
on PsychoPy display flips, without desktop IPC. Animation frames are not
individual markers. A forced termination after the shell's 15-second shutdown
limit cannot produce final markers; inspect the recording's ending and sequence.

```sh
uv run --frozen pytest
pnpm test:web
pnpm check:ui
```

`web/` owns the shared setup/monitor/controller UI; `src-tauri/` supervises its Python process through
closed native commands and a private control pipe. `src/mpi/` contains
study configuration, LSL input, marker catalog, and signal
helpers. `mpi.session_summary` generates the six-panel summary automatically from
the verified XDF after recording closes. `scripts/plot_session.py` provides the same
reader for manual use, with XDF as its primary input and legacy CSV support:

```sh
uv run --frozen python scripts/plot_session.py "data/recording.xdf" --no-show
```

The PNG is saved beside its input as `<recording>_summary.png`. CSV input remains
supported. XDF selects the recorded study input, applies the chosen Polar polarity
when applicable, and uses the recorded trial/target parameters; labels retain N
for Vernier and g for Polar PCA/signed Phan. Targets and errors are reconstructed
at synchronized sample times, so CSV display-frame statistics need not be identical.
Baseline calibration uses the study's recorded diagnostic markers. Automatic
generation runs without opening a plotting window. A run stopped before any
calibration or trial samples has no summary; a later stop produces a partial-run
summary. The installed engine also includes this command for regenerating a plot.

`notebooks/` contains signal exploration,
and `tests/` covers source, marker and recorded-file contracts. Install notebook
tools only when using those files: `python -m uv sync --frozen --python 3.10.11 --group notebooks`.

Older session CSVs and generated plots remain in the ignored local `data/`
folder. Review and de-identify any recording separately before sharing it.

Agent instructions start at [`AGENTS.md`](./AGENTS.md).

The Qt checkpoint before this migration is the Git tag
`qt-wrapper-checkpoint-2026-09-27`.

## QR phone controller

**Connect remote experiment controller** opens a QR popup and creates a private
link automatically. Scanning it requests access; click **Approve** on the desktop
before the phone receives study state or controls. **Reject** revokes the request.
The phone can select the participant number,
scan/select/use LSL input, Start, Cancel, Stop experiment and Close the final
screen. The phone opens **LSL data & markers**: select a raw Vernier channel,
view its current value/unit and a ten-second trace with marker ticks and recent
event names. **Experiment controls** contains setup. The preview coalesces live
samples at four updates per second; XDF retains full-rate data. Both controllers
show phase/trial progress and recording status.
The named marker outlet, sent-event count and latest event stay visible; recent
12 markers, identities and battery status expand under details. The current
stream provides no battery telemetry, so battery reads **Not reported**.
**Disconnect remote controller** revokes the session; phone disconnect does not stop an
ongoing study. The link needs Internet signaling and must stay private.
You can also paste it into Recorder's **+** tab; approved Recorder phones receive
the same tab. The permanent descriptor is
[`companion/panel.json`](companion/panel.json). See
[remote-viewer.md](docs/remote-viewer.md) for pairing, one-controller lifecycle,
hosting, privacy, checks and qualification limits. The static phone interface is
hosted at [Respyra phone controller](https://georgefejer91.github.io/respyra-2.0/remote.html).
