# BIDS and MNE analysis

Respyra writes a BIDS 1.11.2 behavioral dataset in the selected recording
folder's `bids/` directory after a verified XDF closes. `beh/` contains Respyra
events and one pair of files for each nonempty recorded LSL outlet, including
Polar and Vernier Mini streams. The JSON sidecar names the original LSL source,
channel labels, units, nominal rate and processing metadata. Every table keeps
recorded sample timestamps relative to the first selected raw breathing sample.
The XDF is the complete original recording, including empty outlets.

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
