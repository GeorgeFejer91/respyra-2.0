# Respyra 2.0

Python workspace for a breathing-belt validation study. The PsychoPy task asks
participants to follow a breathing target while visual feedback is normal,
amplified, attenuated, or absent. Vernier Stream Mini publishes the raw belt
signal through LSL; Respyra publishes a separate event-marker LSL stream.

The importable Python package keeps its original name, `mpi`.

## Setup

Use Python 3.10 and [`uv`](https://docs.astral.sh/uv/), then run `uv sync`.
Running the experiment requires Vernier Stream Mini from
[Polar-Mini-Stream](https://github.com/GeorgeFejer91/Polar-Mini-Stream) publishing
its **Separate Streams** raw Vernier LSL outlet, an LSL recorder subscribed to
both `VernierRaw` and `Respyra-Events`, and a working PsychoPy display.
The study discovers the raw Force (N) channel automatically. Start the streamer
and recorder before the experiment. The streamer's processed 0–1 breathing
outlet is not used because the study's targets and errors are in Newtons.
The run stops if no Force samples arrive during calibration or if the live
Force stream stalls.
If more than one Vernier raw outlet is visible, set `RESPYRA_LSL_SOURCE_ID` to
the intended outlet's LSL source ID.

Respyra does **not** write session or self-assessment CSVs. The recorder owns
the continuous breathing data and the event timeline. The one-channel
`Respyra-Events` stream sends named JSON markers documented in
[`src/mpi/event_markers/catalog.json`](src/mpi/event_markers/catalog.json).
The experiment waits for a marker-stream subscriber before accepting participant
input. The recorder must also select the Vernier raw stream; marker subscription
alone cannot prove that the force stream is being saved. Marker publication
fails if the subscriber disconnects; inspect the recorded file before using
the run for analysis.
The native participant dialog marks open, submit/cancel, and final field values;
its character-by-character edits are outside the current PsychoPy input hook.
Animation frames are not individual markers.

```sh
uv run python scripts/run_experiment.py
uv run pytest
```

`src/mpi/` contains study configuration, LSL input, marker catalog, and signal
helpers. `scripts/plot_session.py` remains for older local CSV sessions; the new
experiment does not produce its input. `notebooks/` contains signal exploration,
and `tests/` covers source and marker contracts.

Older session CSVs and generated plots remain in the ignored local `data/`
folder. Review and de-identify any recording separately before sharing it.

Agent instructions start at [`AGENTS.md`](./AGENTS.md).
