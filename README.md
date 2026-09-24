# MPI

Python workspace for a breathing-belt validation study. The PsychoPy task asks
participants to follow a breathing target while visual feedback is normal,
amplified, attenuated, or absent. It records force measurements and brief
self-assessments; the plotting script summarizes a session.

## Setup

Use Python 3.10 and [`uv`](https://docs.astral.sh/uv/), then run `uv sync`.
Running the experiment also requires the breathing belt and a working PsychoPy
display setup.

```sh
uv run python scripts/run_experiment.py
uv run python scripts/plot_session.py data/<session>.csv --no-show
uv run pytest
```

`src/mpi/` contains study configuration and signal helpers, `scripts/` contains
the task and plotting entry points, `notebooks/` contains signal exploration,
and `tests/` covers signal helpers.

Session CSVs, self-assessments, and generated plots belong in the local `data/`
folder, which is ignored by Git. Review and de-identify any dataset separately
before sharing it.

Agent instructions start at [`AGENTS.md`](./AGENTS.md).
