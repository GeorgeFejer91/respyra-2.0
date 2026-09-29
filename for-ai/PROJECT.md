# Project contract

## Purpose

A Python workspace for researchers to run and analyze a PsychoPy breathing-belt validation study with normal, amplified, and attenuated visual feedback. Vernier Stream Mini owns belt acquisition and publishes LSL; this project consumes its raw Force (N) stream.

## Primary goal

Run the configured breathing target-tracking study with its own bundled native
LSL/XDF recorder, capturing raw Force and markers before calibration and through
cleanup, and discovering later streams. Optimize the remote view for LSL channel
data and markers. Preserve study protocol and feedback. See `RECORDING.md`.

## Non-goals

- No speculative framework, service, abstraction, compatibility layer, or
  deployment system.
- No second implementation tree or duplicate source of truth.
- No capability claim without matching evidence.
- No direct Vernier Bluetooth/USB connection or reimplementation of the streamer's
  breathing algorithm. Export the study's accepted calibration in one place.
- No session CSV output unless the experimenter enables the original CSV mode.
- Do not publish raw session recordings or self-assessments from `data/`.

## Product/control-plane boundary

- Product source: `src/mpi/`, `native/`, `web/`, `src-tauri/`, `scripts/`, `notebooks/`, and `tests/`.
- Local session output: `data/` (ignored by Git).
- Agent orchestration and durable project memory: `for-ai/`.
- Local generated diagnostics and scratch evidence: `.for-ai-local/` (ignored).

## Architecture and ownership

- Python 3.10 project managed by `uv`; dependencies are declared in
  `pyproject.toml` and resolved in `uv.lock`.
- `src/mpi/validation_study_jenny.py` defines study conditions and trial order;
  `src/mpi/signal.py` provides signal helpers.
- `src/mpi/lsl_force.py` discovers and validates the Vernier Stream Mini raw
  Force (N) LSL outlet and stores accepted source identity. `src/mpi/lsl_setup.py`
  owns discovery/selection for the HTML participant/session form,
  reconnects saved input, and gates Start on a live accepted source plus native
  recording readiness. `src/mpi/recording.py` supervises the pinned LabRecorder
  adapter under `native/recorder/` and verifies XDF completion.
  The same Force source exports the accepted study calibration; `lsl_viewer.py`
  owns display-only all-stream subscriptions. `input_capture.py` owns optional
  Windows input hooks; the study owner publishes their queued marker events.
  `src/mpi/event_markers/` owns the LSL marker publisher
  and exhaustive `catalog.json`. `scripts/run_experiment.py` runs the PsychoPy
  task using that source and `respyra`'s existing study phases; it passes a
  no-op sample logger by default. Optional CSV mode reuses respyra's DataLogger,
  original configured sample columns and self-assessment schema in ignored data/.
- `web/` is plain HTML/CSS/JS with locally bundled Pretext/fonts. `src-tauri/`
  supervises one Python child through closed commands (`launch_backend`,
  `setup_action`, `close_app`, `viewer_action`) and private bounded JSON pipes. Python is the
  sole LSL source/experiment/marker authority; Rust validates the native command
  surface and process lifecycle. There is no web server. The opt-in phone
  controller is defined in `docs/remote-viewer.md`. Rust owns expiring grants,
  one peer/epoch-bound owner, a six-second lease, scopes, command deduplication
  and control revisions. Bundled BRSP JS owns mutual proof; remote pages have no
  IPC capability. Local and phone setup/Start/Stop use the same Python action
  path and receive backend acknowledgments. Python publishes latest marker
  progress and source freshness through a worker without network I/O on flips.
  BRSP/VDO grants `experiment.observe`, `experiment.setup`, `experiment.run`;
  enabling the private link explicitly shares setup fields. `companion/` supplies Remote
  Panel/1 assets hosted on Respyra's own GitHub Pages site at
  `https://georgefejer91.github.io/respyra-2.0/`. Only static companion files
  and source provenance are published on gh-pages; Python/data/grants stay local.
  The experiment control window remains available during PsychoPy, without
  taking participant focus. A second display or phone avoids focus changes.
  Stop cleans up the study; phone loss revokes control but leaves a run active.
  Debug workspace builds use the checkout's `.venv`. The Respyra 2.0
  Windows installer bundles the locked engine with isolated CPython; release
  builds never fall back to a checkout. Optional installed CSVs use the writable
  user folder. Packaging/release gates are in `PACKAGING.md`. App identity is
  `dev.georgefejer.respyra2`.
- `scripts/plot_session.py` remains a reader for historical local CSVs.
  `tests/test_lsl_force.py`, `tests/test_event_markers.py`,
  `tests/test_experiment_flow.py`, `tests/test_desktop_bridge.py`,
  `tests/test_desktop_process.py`,
  `tests/test_lsl_setup.py`, and
  `tests/test_signal.py` cover the local logic and a short simulated study run.
  Vernier Stream Mini in
  **Separate Streams** mode and a display are needed to
  verify the full experiment.

## Signal boundary

- Stream ecosystem: [Polar Stream Mini and Vernier Stream Mini](https://github.com/GeorgeFejer91/Polar-Mini-Stream)
  are the LSL applets this toolbox is currently optimized to receive. Its
  bundled LSL recorder is designed to capture streams published by both. The
  breathing study specifically uses Vernier Stream Mini's raw Force (N) input.
- Study input: Vernier Stream Mini. The checked contract at commit
  `0bd0bd23f30a4f4e36e73a7907b35f2521fc0699` publishes an LSL outlet of
  type `VernierRaw` with `raw_measurement_recording` metadata, including
  GDX-RB channel 1 `Force` in `N`. Its separate `Respiration` outlet is a
  processed 0–1 waveform and is not interchangeable with force in Newtons.
- Respyra owns only the study's range calibration, target generation, visual
  gain, performance error, and discrete event markers. Keep target/error units
  in N; do not silently replace raw Force with the normalized 0–1 outlet.
- The opening desktop UI is one two-segment Experiment hub and LSL streams page.
  It shows participant number and remembered custom variables beside compatible
  input selection, compact stream rows and a shared live plot. The Remote Viewer
  popup pairs the phone. A legacy session value remains internal. See
  `HTML-UI.md` for the no-scroll and explicit no-fit contract.
  Discovery lists visible outlets with compatibility
  reasons; only raw Force (N) with the producer contract, numeric float format,
  and unique source_id can be selected. Connection requires fresh finite Force
  samples. Setup discovery/connection uses one worker, without adding an
  experiment-time background service.
- Save only accepted source_id/name in local user settings, atomically. Later
  launches reconnect and validate that exact identity; the environment override
  `RESPYRA_LSL_SOURCE_ID` takes precedence. Missing/incompatible memory keeps
  the setup UI available, with Start disabled until a valid source is accepted.
  Never silently substitute another belt. Keep the accepted inlet drained
  during setup and disable Start on signal loss; in-experiment loss fails the
  run. Disable automatic inlet recovery so an outlet restart cannot reuse
  stale channel metadata. Settings are identity memory, not a persisted signal
  buffer.
- The bundled native recorder owns persisted samples. Respyra's marker stream uses one JSON
  string per event. Its outlet is advertised at desktop Python-engine startup,
  before study/PsychoPy imports or Force selection. Setup needs no external
  subscriber; Start requires native subscription and raw, derived and marker
  sample readiness.
  Marker pushes do not require a subscriber. Keep the run's outlet through final
  Close; its default name may change during setup before subscription or Start. Markers use a
  shared run UUID, monotonic sequence, LSL timestamp, and
  trial/condition/phase/screen context. The catalog is the authority for every
  emitted marker name and its timing meaning. Advertise the derived breathing
  outlet before recording starts, emit NaN until calibration, then finite
  normalized values on the same outlet. Record raw, derived and marker streams
  from Start through final cleanup. Additional visible and late streams record
  by default; a stream unchecked for recording before Start is excluded by its
  current LSL UID. The force inlet
  enables LSL clock synchronization so source and marker timestamps can be
  compared in the local LSL clock domain. Setup events sent before recording may
  be absent from the file. Only inspection of the recorder output verifies persistence.
- HTML actions capture `ui_seq` and `performance.now()` (`ui_time_ms`) before
  serialized IPC. Rust assigns global pipe `ui_seq` and retains browser sequence
  as `ui_client_seq` with `ui_origin` local/remote. Each browser has its own clock.
  Python consumes them in order and publishes field keys/edits,
  buttons, selections and accept/reject decisions on the same marker outlet.
  Their LSL timestamps describe backend observation; browser time is a separate
  clock. Worker completions describe Python observing the result. Experiment
  onset markers stay on PsychoPy flips without IPC. The outlet survives the final
  HTML screen through Close, including its button/closure markers. A disconnected
  recorder fails the run; forced termination cannot finalize markers or XDF.
  Continuous
  waveform/animation frames are represented by the Vernier stream plus phase,
  condition, and target-parameter markers.
- Monitoring reports actual finite Force-sample reception age, not physical
  belt contact or physiological quality. Blocking instruction/assessment waits
  drain the accepted inlet; active study phases keep their existing reads.
  The current raw Force contract provides no battery telemetry; do not invent it.
- Experiment control is the opening HTML panel and stays available in the
  background during PsychoPy. A Remote Viewer button opens a QR popup;
  scanning opens the phone name prompt, and Request access starts pairing. Desktop Approve grants one
  controller, while Reject/timeout deny state and commands. Its QR pairs over
  VDO.Ninja/BRSP from the public GitHub Pages site. Show compact run/input/output
  status, actual sent-event count, latest event and an expandable last-12 list.
  Native recording status reflects subscribed sources and verified file completion.
  The phone defaults to raw-channel data and recent markers, with compact run
  controls. It shares a bounded live preview, while recordings stay local.

## Current verified state

- Imported source from `MPI-main.zip` on 2026-09-24, excluding the bundled
  virtual environment and generated files.
- Raw legacy session files from the archive are present only in the ignored
  local `data/` directory; their sharing status is **Undecided**.
- The study module's header says 12 trials per session, while its
  `build_conditions()` lists 48; the intended protocol needs confirmation.
- Physical experiment runtime and hardware behavior have not been verified here.
- The locked `respyra==0.4.0` PyPI package differs from the sibling local
  `respyra` checkout; integration checks must use the installed package.
- The LSL inlet and marker outlet passed focused tests and in-process LSL
  outlet/inlet checks on 2026-09-24. A short simulated trial passed against the
  installed respyra/PsychoPy APIs with a simulated source and display. The HTML
  form passed Chromium layout checks; Windows WebView2 passed real LSL selection,
  identity reconnect, input markers, PsychoPy instruction-window handoff and
  graceful closure checks with synthetic data. The physical belt, scientific
  display timing remain unverified. Standalone native XDF round-trip checks now
  cover required data, calibration markers, late streams and closed footers;
  installed-runtime evidence follows `PACKAGING.md`.

Git and runnable checks are the authority for branch, revision, and behavior.
Do not turn this section into a second status ledger.
