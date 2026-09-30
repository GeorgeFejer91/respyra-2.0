# Polar Mini mock through remote study and XDF

- Result/date: `VERIFIED`, 2026-09-30, on this Tower PC. Respyra 0.3.0
  (`codex/recorder-panel`, including Vernier fixes
  `4f83cd94f8ee991a28c666aea7244b39cb05eca6`, Polar audit/marker fixes
  `4397d3d61d68b6dcd4e11ce83ccbeb45f66dfe91`) and Polar/Vernier Mini
  0.6.3 (`codex/mini-window-resize` base
  `7899699bbcd372e05150c63dd7e4939862ed0ab2`, scoped mock/timestamp
  fixes `43c22ad016c21d2510cff6146fef0264b220da41`)
  came from `https://github.com/GeorgeFejer91/respyra-2.0.git` and
  `https://github.com/GeorgeFejer91/Polar-Mini-Stream.git`. The latter is one
  repository containing both Mini apps. Source clones were placed in
  `C:\Users\gfeje\Documents\GitHub` after checking for existing clones. The
  desktop executable was rebuilt from source and launched on a private Win32
  desktop; the phone controller was headless and LSL used private SessionIDs.
- Contracts: PCA `adr_pca_waveform` / `_adrPcaWaveform` /
  `respyra-polar-pca/1`; signed Phan `adr_axis_mean_difference` /
  `_adrAxisMeanDifference` / `respyra-polar-phan-signed/1`. Both are one-channel
  Float32 `Respiration`, unit g, irregular rate 0, `adr-waveform/1` schema,
  `respiration_candidate` role and `signed_breathing_level` input role. Both
  require `_adrPcaValid` (0/1) and `_adrPcaQuality` (0–1); signed Phan also
  requires `_adrAxisDifferenceValid` (0/1). Mock mode forces separate outlets
  for both candidates and all three companions. Raw ACC is 200 Hz, and each
  10 ms mock notification emits one candidate/companion sample. Inhale
  polarity remains a Respyra setup choice.
- Build/reference commands (PowerShell; MSVC environment activated through
  ignored `.for-ai-local/msvc/activate.ps1`):

  ```powershell
  # In Polar-Mini-Stream
  npm ci
  cargo build -p polar-stream-mini -p vernier-stream-mini --locked
  cargo build -p polar-h10-metrics --example mini_mock_reference --locked
  & '.\target\debug\examples\mini_mock_reference.exe' 30000 | Set-Content -Path 'C:\Users\gfeje\Documents\GitHub\respyra-2.0\.for-ai-local\polar-reference-30000.csv' -Encoding utf8
  cargo test -p polar-stream-time -p polar-h10-output -p stream-mini-runtime -p polar-h10-metrics --locked
  cargo clippy -p polar-stream-time -p polar-h10-output -p stream-mini-runtime -p polar-h10-metrics --all-targets --locked -- -D warnings
  cargo fmt --all --check
  # In respyra-2.0
  python -m uv sync --python C:\Users\gfeje\AppData\Roaming\uv\python\cpython-3.10.21-windows-x86_64-none\python.exe --frozen
  pnpm install --frozen-lockfile
  pnpm prepare:recorder
  pnpm tauri build --debug --no-bundle
  & '.venv\Scripts\python.exe' -m pytest tests/test_event_markers.py tests/test_experiment_flow.py tests/test_lsl_polar.py -q
  pnpm test:web
  pnpm check:ui
  ```

- Private native commands (PowerShell path variables below expand to the exact
  rebuilt `target/debug` binaries used):

  ```powershell
  $polarMini = 'C:\Users\gfeje\Documents\GitHub\Polar-Mini-Stream\target\debug\polar-stream-mini.exe'
  $vernierMini = 'C:\Users\gfeje\Documents\GitHub\Polar-Mini-Stream\target\debug\vernier-stream-mini.exe'
  $respyra = 'src-tauri\target\debug\respyra-desktop.exe'
  & '.venv\Scripts\python.exe' tests/run_private_mock.py startup --polar-metric pca --mini-exe $polarMini
  & '.venv\Scripts\python.exe' tests/run_private_mock.py remote-full --polar-metric pca --mini-exe $polarMini --respyra-exe $respyra
  & '.venv\Scripts\python.exe' tests/run_private_mock.py remote-full --polar-metric phan --mini-exe $polarMini --respyra-exe $respyra
  & '.venv\Scripts\python.exe' tests/run_private_mock.py remote-full --polar-metric pca --repeat 2 --mini-exe $polarMini --respyra-exe $respyra
  & '.venv\Scripts\python.exe' tests/run_private_mock.py remote-full --polar-metric phan --repeat 2 --mini-exe $polarMini --respyra-exe $respyra
  & '.venv\Scripts\python.exe' tests/run_private_mock.py remote-full --polar-metric pca --tracking-seconds 2 --mini-exe $polarMini --respyra-exe $respyra
  & '.venv\Scripts\python.exe' tests/run_private_mock.py remote-full --polar-metric phan --invert --mini-exe $polarMini --respyra-exe $respyra
  & '.venv\Scripts\python.exe' tests/run_private_mock.py remote --polar-metric pca --mini-exe $polarMini --respyra-exe $respyra
  & '.venv\Scripts\python.exe' tests/run_private_mock.py remote-full --polar-metric pca --disconnect-after-ready --mini-exe $polarMini --respyra-exe $respyra
  & '.venv\Scripts\python.exe' tests/run_private_mock.py remote-full --mini-exe $vernierMini --respyra-exe $respyra
  ```

  Startup probe joined both candidates at about 12.006 s stream age (the PCA
  axis-learning boundary), compared their first values with reference tick
  1200, and observed validity 0→1 plus axis validity and quality samples.
  All ten initial full-study XDFs were independently re-audited with the final
  audit logic: 48 trials, eight of each six conditions, 1,468 XDF marker rows
  plus 13 ordered setup markers embedded in `recording.started` = 1,481
  reconstructable markers, no sequence gaps. The ten XDFs contain 81,920
  contiguous raw ACC samples, 40,960 samples per candidate/companion stream,
  39,594 derived samples (35,942 finite); maximum candidate/reference error
  was `5.0e-10` g and maximum derived/calibration error was `4.77e-7`.
  The independent auditor checks all raw ACC samples against the analytic
  source, all five candidate/flag series against a separate metric-engine
  replay, timestamp cadence, stream metadata/source IDs/contracts, sign,
  polarity, calibration, condition/target/assessment fields, marker counts/order,
  participant-list state, and all required XDF stream footers. It loads XDF
  without pyxdf clock synchronization or dejitter.
- Retained Polar XDF paths below are relative to
  `C:\Users\gfeje\Documents\GitHub\respyra-2.0\.for-ai-local\`. `PCA` and
  `Phan` rows are complete studies. The two final-build rows used the 50 µs
  clock correction limit; their integrated runner and independent audit both
  exited successfully. Each candidate count also applies to the other
  candidate and each of the three companion outlets.

  | XDF path under the root above | Outcome | Raw ACC | Per candidate | XDF + embedded setup markers |
  | --- | --- | ---: | ---: | ---: |
  | `native-recordings-99151351ae16449595884ffd9fb2e879/synthetic-native_Session-001_11757678bfef46c99eab3afe179732dc.xdf` | PCA | 6602 | 3301 | 1468 + 13 |
  | `native-recordings-777e4cbe33ac43609376c8141558e84b/synthetic-native_Session-001_61dcd4f4accd4a64b89666134fc23828.xdf` | Phan | 6502 | 3251 | 1468 + 13 |
  | `native-recordings-aad8385678864150a40b797d0988a3bc/synthetic-native_Session-001_013ef71c2d54435da18d421047cadaa5.xdf` | PCA repeat 1 | 6402 | 3201 | 1468 + 13 |
  | `native-recordings-aad8385678864150a40b797d0988a3bc/synthetic-native_Session-001_5aa72384a7dd45a09c75b4fd69a9a766.xdf` | PCA repeat 2 | 6402 | 3201 | 1468 + 13 |
  | `native-recordings-7d8288564c6745bca4770f921201ac06/synthetic-native_Session-001_aca1a4798f3645adb2337d631a1f1a9d.xdf` | Phan repeat 1 | 6402 | 3201 | 1468 + 13 |
  | `native-recordings-7d8288564c6745bca4770f921201ac06/synthetic-native_Session-001_bba644850c4542dbbad4b5c520767628.xdf` | Phan repeat 2 | 6402 | 3201 | 1468 + 13 |
  | `native-recordings-dd232a8e6ba546269779ec91e997be4e/synthetic-native_Session-001_9d5b42fbc4e04f07bb07c29df6c333d9.xdf` | PCA sustained 120.5 s | 24102 | 12051 | 1468 + 13 |
  | `native-recordings-bb0a95a9332741f8948d034d4d227bc0/synthetic-native_Session-001_ca73df9cbe534c70813e8be3241a6d6f.xdf` | Phan inverted | 6402 | 3201 | 1468 + 13 |
  | `native-recordings-d35a15f1c396428f9fbca45e38da623c/synthetic-native_Session-001_72eb06b792844003afe871bf8f5289b1.xdf` | PCA after abort | 6402 | 3201 | 1468 + 13 |
  | `native-recordings-13deb9c51f214d719ee39f990786708a/synthetic-native_Session-001_ced2280311cd494abdfb3e95c2d39d20.xdf` | PCA after source loss | 6302 | 3151 | 1468 + 13 |
  | `native-recordings-026754ccb1fd40c78b2868e4fa63d997/synthetic-native_Session-001_b00e08fe669c434d8a215cf4e0c5e5ca.xdf` | Aborted | 902 | 451 | 12 + 13 |
  | `native-recordings-157a2d40193145209d4903c9d1ec924b/synthetic-native_Session-001_387c44a24f904c6aa524accd706a092b.xdf` | Source lost | 590 | 295 | 16 + 13 |
  | `native-recordings-8799ee1bb654400cb8d17ebe5c3880b2/synthetic-native_Session-001_9b62d82069834eaeb73f8754c0897237.xdf` | PCA sustained, 1 ms mapper prototype | 24302 | 12151 | 1468 + 13 |
  | `native-recordings-d5f3234e7a11465a98ece77f3cbdc1c3/synthetic-native_Session-001_10261674c3974d1bbf3648f1163f5d89.xdf` | Phan, 1 ms mapper prototype | 6402 | 3201 | 1468 + 13 |
  | `native-recordings-d60d073e351949a5937ac88ad57c330f/synthetic-native_Session-001_25805fc926d249a599962deab0e48b06.xdf` | PCA sustained, final build | 24102 | 12051 | 1468 + 13 |
  | `native-recordings-d7aa2049b1754c26be6ffd41d852f881/synthetic-native_Session-001_9b9b933afcdc475ab27c1c7adec506ce.xdf` | Phan, final build | 6402 | 3201 | 1468 + 13 |

  The 14 complete rows total 143,128 raw ACC samples, 71,564 samples per
  candidate/companion stream, and 69,645 derived samples (64,537 finite).
  Maximum recorded candidate/reference error was `5.0e-10` and maximum
  derived/calibration error was `4.77e-7`; all 14 had 1,481 reconstructable
  markers. The complete re-audit receipt is retained in ignored
  `.for-ai-local/polar-audit-publication.json`.

  Independently re-audit a completed row with
  `& '.venv\Scripts\python.exe' scripts/audit_polar_mock_xdf.py <full XDF path>`;
  use `--expect-abort` or `--expect-disconnect` for the two early endings.
  The failed pre-fix sustained XDF is
  `native-recordings-3e187417aeab43d581612813ca5773f2/synthetic-native_Session-001_dcd395bbe80447e5bc48b52b6c53be6c.xdf`:
  it exposed a 72.5 ms ACC timestamp jump and was retained as defect evidence,
  not counted as a passed audit.
- The final rebuilt Vernier Mini passed the same private remote full-study
  regression in
  `native-recordings-cdf4047ffd3d4aa195673c6b502d71dd/synthetic-native_Session-001_05f964539fc94185852f4f7627c0164d.xdf`
  under the same `.for-ai-local` root: 641 contiguous raw Force rows, 641
  producer breathing rows, 632 Respyra derived rows (541 finite), 1,468 XDF
  markers plus 12 embedded setup markers, all 48 trials and eight per condition.
  Optional unselected Force
  copy/combined outlets were absent as expected; the default four-stream
  recording and footers passed `scripts/audit_mock_xdf.py`.
- An early Stop produced 902 raw / 451 candidate samples and 12 XDF marker
  rows plus 13 embedded setup markers; `run.aborted` and finalization were
  preserved. Killing the Mini after first instructions produced 590 raw / 295
  candidate samples and 16 + 13 markers; `source.lost`, `run.failed` and a
  closed, footer-checked XDF were observed. Separate complete studies after
  each failure passed. Two back-to-back full PCA studies and two back-to-back
  full Phan studies passed without restarting their Mini process. An inverted
  Phan study verified `input_polarity=-1` and the calibrated sign formula.
- Defects fixed: Polar mock now selects both contracts and companions, and its
  metric source clock advances deterministically; Respyra now carries all
  pre-recording setup events in the first recorded marker; its Vernier auditor
  accepts legitimately unselected optional outlets; the private native runner
  drives/audits Polar full, repeated, sustained, abort and source-loss studies.
  A sustained run revealed a 72.5 ms LSL timestamp step during source-clock
  offset refitting. The Mini source mapper now slews fitted corrections by at
  most 50 µs per observation, with a focused late-first-observation test; the
  affected sustained study was rerun and re-audited after rebuilding.
- Reconstruction limit: the XDF and participant record reconstruct protocol,
  trial order/conditions/targets, calibration, inputs, derived breathing and
  assessments. Exact rendered pixels and frame flip times are not XDF samples;
  the final HTML Close marker follows XDF finalization. This is mock/software
  verification with shortened test timings and simulated responses; it does
  not establish physical H10/Vernier reliability or normal participant timing.
  `pnpm check:remote` was attempted but its separate Recorder companion gate
  could not start because `RECORDER_COMPANION` was unset; real remote phone
  setup/monitor/Start/Stop/Close was exercised by the private native runs.
