# Default stream names

These are the factory names for Suite 2.3.15 / Mini 0.6.11. The second column
records the prior Suite 2.3.14 names for migration. A suite installation, upgrade or
reinstallation restores the essential output selection, with a backup of previous
preferences. Device choices, custom stream prefixes and recorded data are retained.

| Updated factory stream name | Suite 2.3.14 name | Measure and unit |
| --- | --- | --- |
| `Polar_rawECG` | `H10_ECG` | Single-lead electrocardiogram, µV |
| `Polar_rawACC` | `H10_ACC` | Three raw acceleration axes, mg |
| `Polar_HR` | `H10_HR` | Device heart rate, bpm |
| `Polar_RR` | `H10_RR` | Device R–R intervals, ms |
| `Polar_ChestPCA` | `H10_ChestPCA` | Signed chest-motion PCA projection, g, with quality/validity channels |
| `Polar_ChestDT` | `H10_ChestDT` | Detrended signed chest-motion projection, g, with DT/PCA validity and quality |
| `Polar_BreathPhase` | `H10_BreathPhase` | Estimated phase: +1 inhale, −1 exhale, 0 pause, −2 unavailable |
| `Polar_Link` | `H10_Link` | Bluetooth connection events: 1 lost, 2 restored; recorded by default |
| `Vernier_rawForce` | `Vernier_Raw` | All available device channels and seven acquisition diagnostics |
| `Vernier_Link` | Same name | Bluetooth connection events: 1 lost, 2 restored; recorded by default |
| `Respyra_<input name>_calibrated` | `Respyra-BreathCal` / `Respyra-Compare-<hash>` | Selected or alternative input after its own range calibration, dimensionless |
| `Respyra-Events` | Same name | Study events, one JSON string channel |

ECG means electrocardiogram; ACC acceleration; HR heart rate; RR the interval
between successive cardiac R peaks; PCA principal component analysis; DT
detrended; Cal calibrated. `ChestPCA` and `ChestDT` are acceleration-based
breathing candidates, not validated airflow or lung-volume measurements.
`BreathPhase` records an estimated classifier output, not a continuous feedback
waveform. Quality, validity and connection flags are technical diagnostics.

The seven Polar data outputs contain their quality/validity channels, plus
one separate `Polar_Link` housekeeping stream. Vernier publishes its aggregate
measurements and `Vernier_Link`. With both devices and all three breathing inputs
usable, Respyra adds three calibrated copies and study events: 14 default streams,
all recorded by default. Availability and calibration affect this count.
The two Link streams are the dedicated housekeeping exceptions in the default
setup; other processing/acquisition diagnostics remain inside their data streams.
PCAQuality/PCAValid/DTValid remain optional scalar copies and start off. See the
[experimental stream protocol](stream-protocol.md) for the channel and BIDS/MNE contracts.

`Vernier_rawForce` includes Force (N), firmware respiration rate (bpm), Steps and
Step Rate (spm) when the connected device exposes them, plus `sequence`,
`dropped_rows_before`, `device_drop_reports_before`, `sample_period_us`,
`decode_latency_ns`, `host_receive_timestamp_ns` and `encoding_code`.
These channels are not separate default streams. The optional Force-only copy is `Vernier_rawForceOnly`. Optional metric copies and
All-in-one outputs start unchecked. Their metric identifiers remain unchanged;
for example the optional processed waveform is `Vernier_vernierBreathing`.

Use the shortest unambiguous descriptive stream name. Prefer established
scientific abbreviations where they identify the actual measure. Include a
short source prefix when it distinguishes devices, and a method qualifier when
different calculations share a construct. Keep units, formulas, validity and
provenance in channel metadata and documentation. Do not imply scientific
validation beyond the implementation's evidence.

The default prefixes migrate from `Polar-H10-Mini` or `H10` to `Polar` and
`Vernier-GDX-Mini` to `Vernier`. Custom identifiers follow the source prefix,
for example `Polar_Session7_ChestPCA`. Display names
change; historical source IDs and internal metric IDs remain stable for saved
connections. Old XDF files retain their original names, and Respyra task CSV column names,
units, formulas, timestamps and study behavior are unchanged.

`Polar`, legacy `H10`, and `Vernier` are reserved factory prefixes and use their historical
factory source IDs. A previous custom prefix with one of these exact names adopts that
factory identity; reselect it if it was saved under the former custom source ID.
Other custom prefixes retain their existing identity base.

Respyra records visible and later-discovered streams unless their Record boxes
are unchecked before Start. Both Link streams start selected and retain their own
source identities and event timestamps. They are sparse events and need not
supply samples to pass Start when no connection changes occur. The selected raw
input, calibrated output and study events remain required. This essential
selection is not a recorder whitelist. Input hooks remain off by default.

See the [live variable reference](https://georgefejer91.github.io/respyra-2.0/variables.html)
for definitions and [timestamps](timestamps.md) for optional online UTC/Berlin
clock anchoring and offline fallback.

The desktop shows the complete outlet name, including its source prefix.
`Polar_Link` and `Vernier_Link` identify their own applet/device connection.
Their codes describe loss/recovery, not a continuous signal-strength reading.
Respyra replaces
the source prefix and adds `_calibrated`: `Polar_ChestPCA` becomes
`Respyra_ChestPCA_calibrated`, and the default `Vernier_rawForce` becomes
`Respyra_rawForce_calibrated`; this derived outlet contains only its Force
channel after calibration, not all the aggregate's channels. Headers retain
`raw_source_name`, `raw_source_id`, formula, units and feedback/comparison role.
Both selected and alternative inputs use the same naming convention. NaN
means calibration is not yet available. Optional combined Mini outlets use
`Polar_AllInOne` or `Vernier_AllInOne` and start off.

Start advertises calibrated outlets for every live compatible recorded input.
Each uses its own valid range samples. They are recorded by default even when
their View checkbox is off; only the selected input drives feedback. Record
opt-outs and the comparison-recording switch remain explicit choices. A lost
or insufficiently calibrated alternative is reported in event markers.

For breathing-task analysis, keep the selected input, its calibrated Respyra
waveform and `Respyra-Events`. Keep raw ACC and both chest-motion candidates
when comparing Polar processing methods. `ChestPCA` projects motion onto a
learned axis; `ChestDT` projects short-term motion after subtracting a rolling
baseline. Use `PCAValid` with either candidate and `DTValid` additionally with
`ChestDT`; flag low `PCAQuality` intervals. `BreathPhase` is an optional estimated
inhale/exhale/hold label, and Link events help explain Bluetooth connection interruptions.
The default all-stream recording retains these for later inspection.
