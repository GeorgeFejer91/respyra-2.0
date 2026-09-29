# Polar Mini breathing inputs

Respyra 2.0 accepts either of these **separate, one-channel** Polar Stream Mini
outlets as an alternative to Vernier's raw Force (N) inlet. Enable the chosen
waveform under **Realtime metrics → ACC derived** in Polar Stream Mini. Its
validity companions are selected automatically. In Respyra's **Polar breathing
input** dropdown, choose the outlet and then choose whether inhalation raises
or lowers its waveform. Start remains disabled until that direction is set.

| Contract | Polar metric ID and outlet suffix | Required validity outlets |
| --- | --- | --- |
| `respyra-polar-pca/1` | `adr_pca_waveform`, `_adrPcaWaveform` | `_adrPcaValid` |
| `respyra-polar-phan-signed/1` | `adr_axis_mean_difference`, `_adrAxisMeanDifference` | `_adrPcaValid`, `_adrAxisDifferenceValid` |

Each candidate is `Respiration`, one `Float32` channel in `g`, with irregular
source-timed samples. The source ID is `polar-h10-<outlet name>`. Its metadata
must declare `schema=adr-waveform/1`, `stream_role=respiration_candidate`,
`raw_source_metric_id=raw_acc`, `respyra_signal_role=signed_breathing_level`,
and the matching `respyra_input_contract`. Respyra checks the companion outlet
identities, `SignalQuality` type, one `Float32` channel, and `0/1` unit. It
consumes finite waveform values only while the required validity flags are live.
The unsigned/rectified Phan magnitude is deliberately excluded: its peaks do
not retain inhale/exhale direction.

Polar waveform `g` values are acceleration-derived projections, **not chest
displacement or belt force**. Respyra applies the selected direction, performs
its range calibration in those native units, and creates the same named
`Respyra-Calibrated-Breathing` one-channel normalized outlet used by the study.
For Polar its formula is `(polarity × waveform_g − center_g) / amplitude_g`;
samples are NaN before calibration and retain source LSL timestamps. The study
uses its existing phases and target generator, with targets and feedback errors
scaled to the calibrated Polar amplitude. The post-start
`calibration.completed` marker carries `input_polarity` (+1/−1), units and
calibration parameters; `run.configured` identifies the input contract.
Optional Polar CSV columns use
`signal_g`, `target_signal_g`, `error_g`, and `compensated_error_g` in place of
Force-named columns. Vernier's Force input and its Newton-based calibration
remain available.

These are software input contracts, not a claim that either Polar waveform
measures the same quantity as the Vernier belt or gives equivalent study
performance. Paired recordings and analysis are still needed for that claim.
See [Polar Mini's waveform methods and output contracts](https://github.com/GeorgeFejer91/Polar-Mini-Stream/blob/main/docs/adr-waveforms.md).
