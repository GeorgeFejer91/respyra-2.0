# Project contract

## Purpose

A Python workspace for researchers to run and analyze a PsychoPy breathing-belt validation study with normal, amplified, and attenuated visual feedback. Vernier Stream Mini owns belt acquisition and publishes LSL; this project consumes its raw Force (N) stream.

## Primary goal

Run the configured breathing target-tracking study while an external LSL
recorder captures Vernier raw force and Respyra's complete discrete-event
marker timeline. Preserve the study protocol, calibration, and visual feedback.

## Non-goals

- No speculative framework, service, abstraction, compatibility layer, or
  deployment system.
- No second implementation tree or duplicate source of truth.
- No capability claim without matching evidence.
- No direct Vernier Bluetooth/USB connection or second force-to-breathing processor in this project.
- No new session CSV or self-assessment CSV output from the experiment.
- Do not publish raw session recordings or self-assessments from `data/`.

## Product/control-plane boundary

- Product source: `src/mpi/`, `scripts/`, `notebooks/`, and `tests/`.
- Local session output: `data/` (ignored by Git).
- Agent orchestration and durable project memory: `for-ai/`.
- Local generated diagnostics and scratch evidence: `.for-ai-local/` (ignored).

## Architecture and ownership

- Python 3.10 project managed by `uv`; dependencies are declared in
  `pyproject.toml` and resolved in `uv.lock`.
- `src/mpi/validation_study_jenny.py` defines study conditions and trial order;
  `src/mpi/signal.py` provides signal helpers.
- `src/mpi/lsl_force.py` discovers and validates the Vernier Stream Mini raw
  Force (N) LSL outlet. `src/mpi/event_markers/` owns the LSL marker publisher
  and exhaustive `catalog.json`. `scripts/run_experiment.py` runs the PsychoPy
  task using that source and `respyra`'s existing study phases; it passes a
  no-op sample logger to those phases and writes no session files.
- `scripts/plot_session.py` remains a reader for historical local CSVs.
  `tests/test_lsl_force.py`, `tests/test_event_markers.py`,
  `tests/test_experiment_flow.py`, and `tests/test_signal.py` cover the local
  logic and a short simulated study run. Vernier Stream Mini in
  **Separate Streams** mode, an LSL recorder, and a display are needed to
  verify the full experiment.

## Signal boundary

- Source: [Polar-Mini-Stream](https://github.com/GeorgeFejer91/Polar-Mini-Stream),
  Vernier Stream Mini. The checked contract at commit
  `0bd0bd23f30a4f4e36e73a7907b35f2521fc0699` publishes an LSL outlet of
  type `VernierRaw` with `raw_measurement_recording` metadata, including
  GDX-RB channel 1 `Force` in `N`. Its separate `Respiration` outlet is a
  processed 0–1 waveform and is not interchangeable with force in Newtons.
- Respyra owns only the study's range calibration, target generation, visual
  gain, performance error, and discrete event markers. Keep target/error units
  in N; do not silently replace raw Force with the normalized 0–1 outlet.
- Discovery requires one matching live raw outlet. Missing, ambiguous, or
  stalled force data fails the experiment rather than substituting simulated
  or default belt values.
- The recorder owns persisted samples. Respyra's marker stream uses one JSON
  string per event, a shared run UUID, monotonic sequence, LSL timestamp, and
  trial/condition/phase/screen context. The catalog is the authority for every
  emitted marker name and its timing meaning. Record both LSL streams from
  before participant interaction through final cleanup. The force inlet
  enables LSL clock synchronization so source and marker timestamps can be
  compared in the local LSL clock domain. Marker publication fails if its
  subscriber disconnects, but only inspection of the recorder output verifies
  persistence.
- Native participant-dialog character edits are outside PsychoPy's keyboard
  event API; the submitted participant/session values and submit/cancel event
  are marked. Continuous waveform/animation frames are represented by the
  Vernier stream plus phase, condition, and target-parameter markers.

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
  installed respyra/PsychoPy APIs with a simulated source and display. The
  physical belt, visual timing, and recorder file remain unverified.

Git and runnable checks are the authority for branch, revision, and behavior.
Do not turn this section into a second status ledger.
