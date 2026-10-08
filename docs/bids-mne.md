# BIDS and MNE analysis

## Open the XDF itself

The `.xdf` is the primary recording. It contains the recorded LSL signal and
marker streams, their timestamps, and the producers' channel labels, units,
sample formats, and provenance. Respyra's `recording.started` marker also carries
the BIDS-style `subject`, `session`, and `task` labels and the original custom
participant fields. Open this file directly with [PyXDF](https://github.com/xdf-modules/pyxdf)
and [MNE-Python's documented XDF workflow](https://mne.tools/stable/auto_examples/io/read_xdf.html):

```python
import mne
import pyxdf

streams, _ = pyxdf.load_xdf("recording.xdf", dejitter_timestamps=False)
signal = next(s for s in streams if s["info"]["type"][0] == "ECG")
labels = [c["label"][0] for c in signal["info"]["desc"][0]["channels"][0]["channel"]]
rate = float(signal["info"]["nominal_srate"][0])
raw = mne.io.RawArray(signal["time_series"].T,
                      mne.create_info(labels, rate, ch_types="misc"))
```

Select the intended stream by its `source_id` or name when several share a type.
Map physical units deliberately before assigning MNE channel types such as ECG.
For irregular streams (`nominal_srate == 0`), choose and document an analysis
grid before constructing MNE `Raw`; the original XDF timestamps remain the
timing authority. Respyra's JSON marker samples can be converted to MNE
`Annotations` using each payload's `event` and its XDF timestamp. The
`tests/check_xdf_mne_compatibility.py` gate exercises every nonempty numeric
stream and the Respyra markers directly from a recorded XDF. With `--mnelab`,
it also opens the selected raw stream and events using [MNELAB's XDF importer](https://github.com/cbrnr/mnelab).

An XDF can carry BIDS-style identifiers and useful LSL metadata, but XDF is
not a BIDS raw signal format and `mne_bids.read_raw_bids()` does not read it.
The separate BIDS export below provides actual BIDS dataset files when needed.

## Separate BIDS export

Respyra writes a BIDS 1.11.2 behavioral dataset in the selected recording
folder's `bids/` directory after a verified XDF closes. `beh/` contains Respyra
events and one pair of files for each nonempty recorded LSL outlet, including
Polar and Vernier Mini streams. The JSON sidecar names the original LSL source,
channel labels, units, nominal rate and processing metadata. Every table keeps
recorded sample timestamps relative to the first selected raw breathing sample.
The XDF is the complete original recording, including empty outlets.

For one combined recording, use the run's `.xdf` file in the parent recording
folder. BIDS is a dataset directory containing data tables and JSON metadata,
so several dozen files can be expected when many LSL outlets are recorded.
These files describe the same run, rather than separate participant sessions.
Keep the `bids/` folder structure together when transferring a BIDS dataset;
the original study CSV and self-assessment CSV beside the XDF are separate
exports and do not use BIDS naming.

Regular numeric outlets whose timestamps agree with their advertised rate use
headerless `_physio.tsv.gz` plus `_physio.json` and declare `SamplingFrequency`,
`StartTime`, and `Columns`. Irregular, sparse, and unverified-rate outlets use
headered `_beh.tsv` plus `_beh.json`, with a timestamp column and no asserted
sampling frequency. Respyra JSON markers become `_events.tsv`/JSON; other
recorded marker outlets retain their own timed tables. No missing samples are
invented. This distinction follows the BIDS rule that physiology files contain
regularly sampled recordings.

To inspect numeric signals in MNE, install `mne` in an analysis environment and
use Respyra's optional reader:

```python
from mpi.bids_mne import read_bids_signal

raw, original_times = read_bids_signal("sub-002_ses-001_task-respyra_run-01_recording-lsl05_physio.tsv.gz")
raw.plot()

# For an irregular waveform, explicitly choose a grid in Hz:
raw, original_times = read_bids_signal("sub-002_ses-001_task-respyra_acq-raw_run-01_beh.tsv", sfreq=100)
```

The returned `Raw` uses MNE `misc` channels with the original LSL labels.
Original units and source provenance remain in the JSON sidecar and
`raw.info["description"]`; values are not silently converted to volts. For
irregular data, the requested grid linearly interpolates only between adjacent
finite source samples; missing-value gaps remain missing. Keep
`original_times` and the BIDS table for precise timing analyses. MNE Raw itself
requires a regular sample grid. Generic BIDS physiology is not a direct
`mne_bids.read_raw_bids()` neural recording input.

MNE-BIDS can parse the BIDS `beh`/`physio` paths with
`mne_bids.get_bids_path_from_fname`; use the reader above to obtain an MNE Raw
object. For large integer counters, use the BIDS table or XDF for exact values:
MNE Raw stores floating-point data and may round integers above 2^53.
