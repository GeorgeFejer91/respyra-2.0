# Default stream names

Suite 2.3.14 includes Stream Mini 0.6.10. A fresh suite installation, upgrade or
reinstallation restores the essential output selection, with a backup of previous
preferences. Device choices, custom stream prefixes and recorded data are retained.

| Current factory stream name | Previous factory name | Measure and unit |
| --- | --- | --- |
| `H10_ECG` | `Polar-H10-Mini_ECG` | Single-lead electrocardiogram, µV |
| `H10_ACC` | `Polar-H10-Mini_Accelerometer` | Three raw acceleration axes, mg |
| `H10_HR` | `Polar-H10-Mini_Heart-Rate` | Device heart rate, bpm |
| `H10_RR` | `Polar-H10-Mini_RR-Intervals` | Device R–R intervals, ms |
| `H10_ChestPCA` | `Polar-H10-Mini_ChestMotion` | Signed chest-motion PCA projection, g |
| `H10_ChestDT` | `Polar-H10-Mini_ChestMotion-DT` | Detrended signed chest-motion projection, g |
| `H10_BreathPhase` | `Polar-H10-Mini_Flowborne` | Estimated phase: +1 inhale, −1 exhale, 0 pause, −2 unavailable |
| `H10_PCAQuality` | `Polar-H10-Mini_PCA-Quality` | App-specific signal-quality index, 0–1 |
| `H10_PCAValid` | `Polar-H10-Mini_PCA-Valid` | Processing readiness flag, 0/1 |
| `H10_DTValid` | `Polar-H10-Mini_Phan-Valid` | Detrending short-window readiness flag, 0/1 |
| `H10_Link` | `Polar-H10-Mini-signalStatus` | Connection transition: 1 lost, 2 restored |
| `Vernier_Raw` | `Vernier-GDX-Mini_rawVernier` | All available device channels and seven acquisition diagnostics |
| `Vernier_Link` | `Vernier-GDX-Mini-signalStatus` | Connection transition: 1 lost, 2 restored |
| `Respyra-BreathCal` | `Respyra-Calibrated-Breathing` | Selected input after study calibration, dimensionless |
| `Respyra-Compare-<hash>` | `Respyra-Comparison-<hash>` | Calibrated copy of each usable alternative, dimensionless |
| `Respyra-Events` | Same name | Study events, one JSON string channel |

ECG means electrocardiogram; ACC acceleration; HR heart rate; RR the interval
between successive cardiac R peaks; PCA principal component analysis; DT
detrended; Cal calibrated. `ChestPCA` and `ChestDT` are acceleration-based
breathing candidates, not validated airflow or lung-volume measurements.
`BreathPhase` records an estimated classifier output, not a continuous feedback
waveform. Quality, validity and connection flags are technical diagnostics.

The seven Polar primary outputs require three quality/validity companions;
the connection marker is separate. That gives 11 Polar outlets and two Vernier
outlets. With both devices and all three compatible breathing inputs usable,
Respyra adds one selected calibrated waveform, two comparison copies and events:
17 default outlets. Availability and comparison calibration affect this count.

`Vernier_Raw` includes Force (N), firmware respiration rate (bpm), Steps and
Step Rate (spm) when the connected device exposes them, plus `sequence`,
`dropped_rows_before`, `device_drop_reports_before`, `sample_period_us`,
`decode_latency_ns`, `host_receive_timestamp_ns` and `encoding_code`.
These channels are not separate default streams. Optional metric copies and
All-in-one outputs start unchecked. Their metric identifiers remain unchanged;
for example the optional processed waveform is `Vernier_vernierBreathing`.

Use the shortest unambiguous descriptive stream name. Prefer established
scientific abbreviations where they identify the actual measure. Include a
short source prefix when it distinguishes devices, and a method qualifier when
different calculations share a construct. Keep units, formulas, validity and
provenance in channel metadata and documentation. Do not imply scientific
validation beyond the implementation's evidence.

The default prefixes migrate from `Polar-H10-Mini` to `H10` and
`Vernier-GDX-Mini` to `Vernier`. Custom prefixes are retained. Display names
change; historical source IDs and internal metric IDs remain stable for saved
connections. Old XDF files retain their original names, and Respyra task CSV column names,
units, formulas, timestamps and study behavior are unchanged.

`H10` and `Vernier` are now reserved factory prefixes and use their historical
factory source IDs. A previous custom prefix with either exact name adopts that
factory identity; reselect it if it was saved under the former custom source ID.
Other custom prefixes retain their existing identity base.

Respyra records all visible and later-discovered streams unless their Record
boxes are unchecked before Start. This essential selection is a publisher
default, not a recorder whitelist. Input hooks remain off by default.

See the [live variable reference](https://georgefejer91.github.io/respyra-2.0/variables.html)
for definitions and [timestamps](timestamps.md) for optional online UTC/Berlin
clock anchoring and offline fallback.
