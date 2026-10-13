# Polar Mini breathing inputs

Respyra 2.0 accepts either of these **separate breathing-variable** Polar Stream Mini
outlets as an alternative to Vernier's raw Force (N) inlet. Enable the chosen
waveform under **Realtime metrics → ACC derived** in Polar Stream Mini. Its
validity and quality channels are bundled automatically. In Respyra's **Polar breathing
input** dropdown, choose the outlet and then choose whether inhalation raises
or lowers its waveform. Start remains disabled until that direction is set.

| Contract | Polar metric ID and outlet suffix | Required validity channels |
| --- | --- | --- |
| `respyra-polar-pca/1` | Chest Motion: `adr_pca_waveform`, `_ChestPCA` | `adr_pca_valid` |
| `respyra-polar-phan-signed/1` | Chest Motion DT: `adr_axis_mean_difference`, `_ChestDT` | `adr_pca_valid`, `adr_axis_difference_valid` |

These are default display names, never discovery rules. Respyra identifies a
compatible waveform from a floating-point (`Float32` or `Double64`) channel
in `g`, a valid nonnegative nominal rate, and the declared signed waveform
role and contract. The Mini emits irregular source-timed `Float32` samples;
compatible regular-rate streams can also be read. Its metadata
must declare `schema=adr-waveform/2`, `stream_role=respiration_candidate`,
`raw_source_metric_id=raw_acc`, `respyra_signal_role=signed_breathing_level`,
and a supported `respyra_input_contract`. `waveform_channel` and `validity_channels` bind the signal/readiness
to unique channel `metric_id`s. Every channel declares its unit and role;
the waveform's label, stream name and source-ID spelling are unrestricted.
Earlier single-channel `adr-waveform/1` Mini inputs with separate readiness
outlets remain supported, including their stable source-ID bindings. Respyra
checks `0/1` units and same-row readiness in bundled inputs. It
consumes finite waveform values only while the required validity flags are live.
Chest Motion was previously displayed as PCA breathing, and Chest Motion DT
as Phan breathing. DT means detrended; both use the same learned PCA axis.
The internal metric IDs, contracts and LSL source IDs retain their previous
values, so saved input identities and earlier publishers remain compatible.
Flowborne's unitless phase classes and the rectified Phan magnitude are excluded:
they do not declare the supported continuous signed waveform role. A curve's
visual appearance alone does not establish respiratory meaning; ECG and
arbitrary motion remain incompatible without the required units and semantics.

Polar waveform `g` values are acceleration-derived projections, **not chest
displacement or belt force**. Respyra applies the selected direction, performs
its range calibration in those native units, and creates the same named
`Respyra_&lt;input name&gt;_calibrated` normalized waveform bundle with its source support channels, used by the study.
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

Updated source names are Polar_ChestPCA and Polar_ChestDT, transformed into Respyra_ChestPCA_calibrated and Respyra_ChestDT_calibrated. Their historical source IDs and metadata contracts remain unchanged; discovery does not depend on display names. The published Suite 2.3.14 installer retains H10-prefixed names until a new build is installed. See [stream names](stream-names.md).
