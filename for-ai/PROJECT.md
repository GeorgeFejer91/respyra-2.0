# Project contract

## Purpose

A Python workspace for researchers to run and analyze a PsychoPy breathing-belt validation study with normal, amplified, and attenuated visual feedback.

## Primary goal

Run the configured breathing target-tracking study and inspect its session
measurements and self-assessments without changing the study protocol by
accident.

## Non-goals

- No speculative framework, service, abstraction, compatibility layer, or
  deployment system.
- No second implementation tree or duplicate source of truth.
- No capability claim without matching evidence.

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
- `scripts/run_experiment.py` runs the belt/PsychoPy task using `respyra`;
  `scripts/plot_session.py` summarizes session CSVs.
- `tests/test_signal.py` checks signal helper behavior. A belt and display are
  needed to verify the experiment itself.

## Current verified state

- Imported source from `MPI-main.zip` on 2026-09-24, excluding the bundled
  virtual environment and generated files.
- Raw session files from the archive are present only in the ignored local
  `data/` directory; their sharing status is **Undecided**.
- The study module's header says 12 trials per session, while its
  `build_conditions()` lists 48; the intended protocol needs confirmation.
- Experiment runtime and hardware behavior have not been verified here.

Git and runnable checks are the authority for branch, revision, and behavior.
Do not turn this section into a second status ledger.
