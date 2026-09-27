# Respyra 2.0

HTML/Tauri desktop setup for a Python breathing-belt validation study. The PsychoPy task asks
participants to follow a breathing target while visual feedback is normal,
amplified, attenuated, or absent. Vernier Stream Mini publishes the raw belt
signal through LSL; Respyra publishes a separate event-marker LSL stream.

The importable Python package keeps its original name, `mpi`.

## Setup

Use Python 3.10, [`uv`](https://docs.astral.sh/uv/), Node/pnpm, Rust/Cargo,
and the Tauri Windows prerequisites (MSVC build tools and WebView2). From the
checkout, launch the desktop app:

```powershell
py -3.10 -m uv sync --frozen
pnpm install --frozen-lockfile
# If Cargo is not already in PATH:
$env:PATH = "$env:USERPROFILE\.cargo\bin;$env:PATH"
pnpm tauri dev
```

To build the workspace executable, run `pnpm tauri build --no-bundle`
(`--debug` builds faster). This version requires the checkout and its `.venv`:
the native shell uses the fixed Python environment in the build's workspace.
Rebuild after moving the checkout. It is not a standalone installer.

Running the experiment requires Vernier Stream Mini from
[Polar-Mini-Stream](https://github.com/GeorgeFejer91/Polar-Mini-Stream) publishing
its **Separate Streams** raw Vernier LSL outlet, an LSL recorder subscribed to
both `VernierRaw` and `Respyra-Events`, and a working PsychoPy display.
Launch Respyra; its **Respyra-Events** outlet (type **Markers**) is advertised
at Python-engine startup, before breathing-input selection or PsychoPy initialization.
In LabRecorder, refresh the stream list, select **Respyra-Events** and the
streamer's **VernierRaw** outlet, then start recording. Respyra waits for a marker
subscriber without a 30-second deadline; participant controls remain disabled
until one connects. Keep both streams recording through the final **Close**.
The first window is
the participant/session form with breathing-input setup. Click **Add LSL
Stream**, select a compatible result, then **Use Selected Stream**. The scan
lists visible streams and reasons for rejecting incompatible inputs. It
requires the Vernier Stream Mini raw outlet, its metadata-identified Force
channel in **N**, floating-point samples, and a unique stable source ID. Live
Force values are checked before **Start Experiment** becomes available.
The streamer's processed 0–1 breathing outlet is not used because the study's
targets and errors are in Newtons.
The run stops if no Force samples arrive during calibration or if the live
Force stream stalls.

The accepted source ID is saved in `%LOCALAPPDATA%/Respyra/lsl-source.json`
on Windows (otherwise `$LOCALAPPDATA`, or `~/.config/Respyra`). Later launches
automatically reconnect that exact source and recheck metadata and live data;
no repeated scan or acceptance is needed. Missing, changed, duplicate, or
incompatible outlets require selection again. There is no automatic switch to
another belt. Each accepted inlet stays pinned to that outlet; a streamer
restart requires a new validated connection. Settings contain only source
identity/name, never breathing samples or participant details.
`RESPYRA_LSL_SOURCE_ID`, when set, overrides
the saved identity on launch; remove it to use remembered UI selections.

The first window is a local HTML form in Tauri's WebView. After Start Experiment,
the setup window hides and PsychoPy presents the original instructions,
calibration, trials, and assessments. The form returns after the run with its
result; keep the recorder running until **Close**. Discovery and connection
run in one Python setup worker; experiment input keeps the existing nonblocking
LSL read path. Qt is not used by this wrapper, although the installed PsychoPy
and respyra distributions still include Qt dependencies.

Respyra does **not** write session or self-assessment CSVs. The recorder owns
the continuous breathing data and the event timeline. The one-channel
`Respyra-Events` stream sends named JSON markers documented in
[`src/mpi/event_markers/catalog.json`](src/mpi/event_markers/catalog.json).
The experiment waits for a marker-stream subscriber before accepting participant
input. The recorder must also select the Vernier raw stream; marker subscription
alone cannot prove that the force stream is being saved. Marker publication
fails if the subscriber disconnects; inspect the recorded file before using
the run for analysis.
The HTML participant form marks each field key press and text edit, Start/Cancel
button clicks, accept/reject, and final field values. LSL selection, scan
results, connection outcomes, saved-source actions, and source loss also send
named markers. The final Close button and native closure also have markers.
Python publishes the single marker stream in order. Setup actions include
`ui_seq` and browser `ui_time_ms`; their LSL timestamp describes Python observing
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

`web/` owns the setup form; `src-tauri/` supervises its Python process through
closed native commands and a private control pipe. `src/mpi/` contains
study configuration, LSL input, marker catalog, and signal
helpers. `scripts/plot_session.py` remains for older local CSV sessions; the new
experiment does not produce its input. `notebooks/` contains signal exploration,
and `tests/` covers source and marker contracts.

Older session CSVs and generated plots remain in the ignored local `data/`
folder. Review and de-identify any recording separately before sharing it.

Agent instructions start at [`AGENTS.md`](./AGENTS.md).

The Qt checkpoint before this migration is the Git tag
`qt-wrapper-checkpoint-2026-09-27`.

## Remote LSL Recorder panel

**Start viewer** creates a private link and QR for read-only progress.
Paste it into Recorder's **+** tab and select **Connect** inside the panel.
Approved Recorder phones receive the same tab. The permanent descriptor is
[`companion/panel.json`](companion/panel.json). See
[remote-viewer.md](docs/remote-viewer.md) for pairing, one-observer lifecycle,
hosting, privacy, checks and qualification limits.
