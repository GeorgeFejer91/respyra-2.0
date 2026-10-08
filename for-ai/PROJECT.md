# Project contract

## Purpose

A Python workspace for researchers to run and analyze a PsychoPy breathing target-tracking study with normal, amplified, and attenuated visual feedback. It accepts Vernier Stream Mini's raw Force (N) outlet or either of two signed Polar Stream Mini ACC-derived waveforms. Both Mini apps own acquisition and publish LSL; this project consumes their checked outlets.

## Primary goal

Run the configured breathing target-tracking study with its own bundled native
LSL/XDF recorder, capturing the selected raw input and markers before calibration and through
cleanup, and discovering later streams. Prioritize low-latency, smooth remote
visualization of the freshest received LSL channel data and markers, without
compromising full-rate recording or study timing. Preserve study protocol and
feedback. See `RECORDING.md`.

## Non-goals

- No speculative framework, service, abstraction, compatibility layer, or
  deployment system.
- No second implementation tree or duplicate source of truth.
- No capability claim without matching evidence.
- No direct Vernier Bluetooth/USB connection or reimplementation of the streamer's
  breathing algorithm. Export the study's accepted calibration in one place.
- Do not publish raw session recordings, CSVs, or self-assessments from any selected folder.

## Product/control-plane boundary

- Original Respyra 2.0 study, controller and packaging code is GPL-3.0;
  bundled third-party components retain their own licenses. The root `LICENSE`
  and `docs/THIRD-PARTY.md` are the distribution notices.
- Product source: `src/mpi/`, `native/`, `web/`, `src-tauri/`, `scripts/`, `notebooks/`, and `tests/`.
- Local session output: the remembered user-selected folder, defaulting to `data/`
  (ignored by Git). External selected folders remain local.
- Agent orchestration and durable project memory: `for-ai/`.
- Local generated diagnostics and scratch evidence: `.for-ai-local/` (ignored).

## Architecture and ownership

- Python 3.10 project managed by `uv`; dependencies are declared in
  `pyproject.toml` and resolved in `uv.lock`.
- `src/mpi/validation_study_jenny.py` defines study conditions and trial order;
  `src/mpi/signal.py` provides signal helpers.
- `src/mpi/lsl_force.py` discovers the three supported input contracts and
  validates the Vernier raw Force (N) LSL outlet. `src/mpi/lsl_polar.py`
  validates and consumes the two Polar ACC-derived outlets and their validity
  companions; `src/mpi/polar_calibration.py` calibrates their signed g values.
  The input owner stores accepted source identity. `src/mpi/lsl_setup.py`
  owns discovery/selection for the HTML participant/session form,
  reconnects saved input, and gates Start on a live accepted source plus native
  recording readiness. `src/mpi/recording.py` supervises the pinned LabRecorder
  adapter under `native/recorder/` and verifies XDF completion.
  That XDF is the primary analysis artifact: LSL headers and the recorded
  start marker provide channel/source and subject/session/task context for
  direct PyXDF/MNE or MNELAB import. XDF is not itself a BIDS raw format.
  The selected source exports the accepted study calibration; `lsl_viewer.py`
  owns display-only all-stream subscriptions. `input_capture.py` owns optional
  Windows input hooks; the study owner publishes their queued marker events.
  `src/mpi/event_markers/` owns the LSL marker publisher
  and exhaustive `catalog.json`. `scripts/run_experiment.py` runs the PsychoPy
  task using that source and `respyra`'s existing study phases; it passes a
  respyra's DataLogger for automatic original-schema sample and assessment CSVs.
  After verified XDF promotion, `mpi.bids_export` creates a behavioral BIDS
  dataset for every nonempty recorded LSL outlet. Fixed-rate numeric outlets
  become physiology; irregular, sparse, and string outlets become timed
  behavioral tables. Respyra markers become BIDS events. `mpi.bids_mne` reads
  numeric tables into MNE Raw, requiring an explicit resampling rate for
  irregular data. The XDF retains exact source data and empty outlets.
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
  `https://georgefejer91.github.io/respyra-2.0/`. The root is a public app
  overview; existing private QR links redirect to the static controller at
  `/remote.html`. Only static site/controller files and source provenance are
  published on gh-pages; Python/data/grants stay local.
  The experiment control window remains available during PsychoPy, without
  taking participant focus. A second display or phone avoids focus changes.
  Stop cleans up the study; phone loss revokes control but leaves a run active.
  Debug workspace builds use the checkout's `.venv`. The Respyra 2.0
  Windows installer bundles the locked engine with isolated CPython; release
  builds never fall back to a checkout. Installed XDF and CSV files use the remembered
  recording folder; the default is `data/` inside the program folder. Packaging/release gates are in `PACKAGING.md`. App identity is
  `dev.georgefejer.respyra2`.
- `scripts/plot_session.py` remains a reader for historical local CSVs.
  `scripts/xdf_to_csv.py` is a separate, user-invoked offline export of an
  existing XDF to one timestamped CSV per stream; it is separate from the
  study's automatic original-schema CSV logger. `notebooks/xdf_to_csv_tutorial.ipynb` explains
  the export. Synthetic and participant XDF files stay out of Git.
  `tests/test_lsl_force.py`, `tests/test_event_markers.py`,
  `tests/test_experiment_flow.py`, `tests/test_desktop_bridge.py`,
  `tests/test_desktop_process.py`,
  `tests/test_lsl_setup.py`, and
  `tests/test_signal.py` cover the local logic and a short simulated study run.
  A selected Mini input, its validity companions when Polar is chosen, and an
  isolated display test environment are needed to verify the full experiment.

## Signal boundary

The suite starts with Mini acquisition defaults: Vernier publishes its raw
`VernierRaw` Force outlet; Polar publishes direct ECG, ACC, heart rate and RR
plus its Breathing/Breathing dynamics metrics and their quality companions.
Saved Mini choices survive upgrade. Respyra offers one grouped selector for
the main visual-feedback input. `mpi.parallel_inputs` opens other live
compatible inputs at Start and publishes a separately calibrated comparison
outlet for each. Native XDF records all visible and later LSL streams by
default. The operator can uncheck nonrequired raw streams or turn comparison
copies off in Settings. The selected raw, selected derived and markers are
required while running. Each alternative's own samples define its range
calibration; unselected Polar polarity stays native +1 pending analysis.

- Stream ecosystem: [Polar Stream Mini and Vernier Stream Mini](https://github.com/GeorgeFejer91/Polar-Mini-Stream)
  are pinned in the `mini-streams` submodule for the Windows suite build. Each
  keeps its own app identity and independent installer. The suite variant of
  Respyra's installer carries both finalized Mini payloads and adds three
  application shortcuts plus one launcher. These are the LSL applets this
  toolbox is currently optimized to receive. Its
  bundled LSL recorder is designed to capture streams published by both. The
  breathing study can use Vernier raw Force (N) or either exact Polar candidate.
- Study input: Vernier Stream Mini raw Force or the exact Polar PCA/signed Phan
  contracts in [`docs/polar-input-contracts.md`](../docs/polar-input-contracts.md).
  Vernier's checked contract at commit
  `0bd0bd23f30a4f4e36e73a7907b35f2521fc0699` publishes an LSL outlet of
  type `VernierRaw` with `raw_measurement_recording` metadata, including
  GDX-RB channel 1 `Force` in `N`. Its separate `Respiration` outlet is a
  processed 0–1 waveform and is not interchangeable with force in Newtons.
- Respyra owns the study's range calibration, target generation, visual
  gain, performance error, and discrete event markers. Keep Vernier target/error
  units in N; use native g for the selected Polar projection. Both paths
  advertise a separate normalized derived outlet before calibration and publish
  finite values afterward. Never reinterpret a
  Polar projection as force or silently replace raw Force with the normalized
  Vernier 0–1 outlet.
- The opening desktop UI is one two-segment Experiment hub and LSL streams page.
  It shows a participant-number dropdown (0–100) with previously recorded numbers
  marked red, and remembered custom variables beside compatible
  input selection, compact stream rows and a shared live plot. The Remote Viewer
  popup pairs the phone. Participant parity chooses block order; a legacy `001`
  session value remains internal for recording metadata. See
  `HTML-UI.md` for the no-scroll and explicit no-fit contract.
  Discovery lists visible outlets with compatibility
  reasons; only raw Force (N) or the two exact signed Polar waveforms with their
  producer contracts, numeric float format, and unique source_id can be selected.
  Polar also requires its validity companions and an explicit inhale direction.
  Connection requires fresh finite valid samples. Setup discovery/connection uses one worker, without adding an
  experiment-time background service.
- Save only accepted source_id/name in local user settings, atomically. Later
  launches reconnect and validate that exact identity; the environment override
  `RESPYRA_LSL_SOURCE_ID` takes precedence. Missing/incompatible memory keeps
  the setup UI available, with Start disabled until a valid source is accepted.
  Never silently substitute another source. Keep the accepted inlet drained
  during setup and disable Start on signal loss; in-experiment loss fails the
  run. Disable automatic inlet recovery so an outlet restart cannot reuse
  stale channel metadata. Settings are identity memory, not a persisted signal
  buffer.
- The bundled native recorder owns persisted samples. Respyra's marker stream uses one JSON
  string per event. Its outlet is advertised at desktop Python-engine startup,
  before study/PsychoPy imports or breathing-input selection. Setup needs no external
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
  current LSL UID. The selected study inlet
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
- Continue (Space) and calibration Retry (R) are typed controller intents in
  `experiment.run`, bound to the current run UUID and prompt shown sequence.
  Python admits them only at the visible prompt and acknowledges after its
  dismissal markers. Stale, unavailable and interrupted commands fail closed;
  `ui.prompt_control` records their outcome and controller origin. Questionnaire
  answers remain local and no generic keyboard injection is exposed.
- Monitoring reports actual finite accepted-sample reception age, not physical
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
- `build_conditions()` lists 48 trials in four blocks of 12; the intended
  protocol trial count still needs confirmation.
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
