# Experimental stream protocol

`respyra-stream/1` is the shared engineering contract for new and changed
Respyra/Mini streams. Treat the experimental variable as the primary channel;
attach the information needed to interpret that variable to the same sample.
Preserve the acquisition timestamp, source identity and physical units.

## Names, channels and provenance

- Use a full producer prefix: `Polar_`, `Vernier_` or `Respyra_`.
  Respyra replaces the input's producer prefix and appends `_calibrated`.
  Retain the original name, source ID, input channel and formula in metadata.
- Every channel declares its label, unit, type and role. Roles are
  `measurement`, `waveform`, `quality`, `validity`, `diagnostic` and `event`.
  Measurements and waveforms are the experimental data variables.
- Bundle only values evaluated at the same acquisition timestamp. Keep signals
  with different sampling schedules in separate outlets. Never invent samples
  during a connection gap or carry an earlier validity value into a new row.
- Keep the main waveform first. Publish its quality/readiness as other channels
  in the same row, with stable `metric_id` values and explicit role metadata.
  Consumers bind by metadata rather than display names or fixed positions.
- If a stream contains several waveforms, each declares its own
  `validity_channels` by channel metric ID. One method's readiness never gates
  another method merely because their values share a stream.
- Record implementation/processing provenance in immutable stream headers;
  record accepted calibration parameters and study transitions as events.

## Polar breathing bundle

| Outlet | Primary variable | Supporting channels |
| --- | --- | --- |
| `Polar_ChestPCA` | Signed PCA chest-motion projection, g | PCA quality; PCA validity |
| `Polar_ChestDT` | Signed detrended chest-motion projection, g | DT validity; PCA validity; PCA quality |

These use `schema=adr-waveform/2`, declare `waveform_channel`,
`diagnostic_channels` and `validity_channels`, and retain the two existing
Respyra input contract IDs. Quality does not directly gate feedback. All required
validity values must be finite and at least 0.5 for the corresponding waveform
sample. Readiness describes processing, not physiological accuracy.

The original bundles retain diagnostic waveform values in unusable intervals.
Respyra excludes those intervals from range calibration and feedback. Its
calibrated Polar bundles have a normalized waveform followed by the source
supporting channels; all channels are NaN before accepted range calibration.
After calibration, only valid source rows produce calibrated rows, with
unchanged support values and the original timestamps. Each input has its own
calibration; only the selected input drives feedback.

The default standalone PCAQuality/PCAValid/DTValid outlets are removed. Their
scalar copies remain optional research outputs. Legacy `adr-waveform/1` inputs
with separate validity outlets remain accepted. Connection loss/recovery is
recorded in each applet's dedicated Link stream below. View selection never changes recording selection;
bundled supporting channels are recorded even though the plot prioritizes the
measurement channels.

## Dedicated Bluetooth housekeeping streams

`Polar_Link` and `Vernier_Link` are the two exceptions to the default data-stream
bundling rule. Each applet owns its own sparse housekeeping outlet, reporting
its Bluetooth device connection rather than physiological signal quality:

| Channel | Value | Meaning |
| --- | --- | --- |
| `signal_state` | 1 | Applet detected Bluetooth connection loss |
| `signal_state` | 2 | Applet detected Bluetooth connection restoration |

Both streams are visible and recorded by default, including late discovery.
Their stable source IDs, manufacturer and event timestamps identify the applet
and device. Event times are host-observed detection/publication times. A paired
loss/recovery gives the observed outage duration; an unmatched loss remains an
open outage. No RSSI, packet-loss percentage or missing recovery is fabricated.
Applet shutdown may prevent a final event; silence alone does not prove a live
Bluetooth link or identify a physical cause.

The default setup has no combined Respyra Housekeeping outlet. Quality/readiness
and acquisition diagnostics remain channels of their relevant measurements.
The Link outlets declare event roles and nominal rate zero. They can be empty
when no transition occurs, so Start does not require their sample receipt. XDF
retains their headers/footers; BIDS exports their nonempty event data as timed
support tables. MNE selects experimental measurements by default; explicitly
include supporting channels to analyze the Link codes. Study events remain in
`Respyra-Events` as experimental timing data.

## Automatic XDF to BIDS

The existing recorder completion path exports each successfully verified,
closed XDF to the run's `bids/` folder. XDF remains the complete source archive.
No exporter operates on an unfinished recording or rewrites its raw samples.

Primary tables contain experimental measurement/waveform columns. A mixed
stream also gets a linked `support` table containing its quality, validity,
acquisition diagnostics or event columns at the same timestamps. Sidecars retain
the original channel indices, labels, roles, units, stream name/source ID,
processing metadata, MNE type/scale and `SupportTable` linkage. Optional streams
use readable source names in their BIDS acquisition/recording labels, with
collision handling. Empty outlets remain represented by the XDF.

Verified regular-rate numeric signals use headerless `_physio.tsv.gz` plus
JSON with `SamplingFrequency`, `StartTime` and `Columns`. Irregular or
unverified-rate data and other markers use timed `_beh.tsv`; no regular rate
is fabricated. Respyra's study markers become `_events.tsv`. UTC/Berlin clock
columns remain timing metadata rather than experimental channels.

## MNE analysis

```python
from mpi.bids_mne import read_bids_signal

# Regular physiology uses its verified stored rate.
raw, original_times = read_bids_signal("..._physio.tsv.gz")

# Irregular signals require an analysis rate chosen explicitly.
raw, original_times = read_bids_signal("..._beh.tsv", sfreq=20)
```

The reader returns MNE `RawArray` with source-qualified channel names and only
experimental variables by default. It applies bundled readiness to waveform
values before interpolation, keeps missing data as NaN and does not bridge
gaps longer than three median source intervals. Class codes/counters use the
previous value between adjacent samples instead of inventing intermediate
codes. Original values and timestamps remain in the BIDS tables and XDF.

Declared ECG and other supported voltage channels are converted to volts and
given their MNE channel type. Force in N, acceleration in g/mg and normalized
breathing remain `misc`, with their original units retained in metadata.
They are never mislabeled as voltage. Use `include_support=True` to inspect
supporting channels explicitly. This is an MNE reader for the exported BIDS
tables; no mandatory analysis dependency or automatic FIF export is added to
the recording application.

References: [MNE channel types and required units](https://mne.tools/stable/generated/mne.create_info.html),
[BIDS physiological recordings](https://bids-specification.readthedocs.io/en/stable/modality-specific-files/physiological-recordings.html).

## Change verification

For any stream contract change, check producer metadata/channel counts and
source timing, invalid-sample rejection, native XDF values/headers/footers,
the automatically produced BIDS data/support tables, MNE role selection/units,
and legacy input compatibility. Report synthetic and physical-device evidence
separately. A successful build does not establish physiological validation.
