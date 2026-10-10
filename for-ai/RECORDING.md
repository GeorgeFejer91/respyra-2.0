# Native recording contract

Default candidate capture: Start advertises one `Respyra-Comparison-*`
normalized LSL outlet for every other live compatible Vernier Force or Polar
PCA/signed-Phan input whose raw Record box remains checked. The native recorder
requires each such raw and derived outlet to supply samples before the study
starts. All outputs are NaN before calibration. During the accepted range
attempt, each candidate accumulates its own valid samples; after acceptance,
its own percentile center/amplitude activates finite output at the source
timestamps. A skipped or lost candidate emits an event marker and is not
claimed as a valid transformed signal. The selected input alone drives visual
feedback. Unselected Polar candidates retain native +1 polarity because no
inhale direction was chosen for them. Settings can turn comparison copies off;
all other visible and later LSL streams still record by default unless their
Record boxes were unchecked.

Read for recorder, Start, calibration/stream lifecycle, XDF or remote-data work.
Input suitability uses channel format, units, measurement/waveform role and
declared readiness references, never stream or channel display names. Stable
source IDs bind recording/reconnection and declared validity companions;
their spelling is unrestricted. Polar supports one Float32/Double64 signed
g waveform with a known processing contract and finite live valid samples;
Flowborne class codes cannot drive feedback. Legacy Mini companion metadata
remains accepted. Raw Vernier Force is selected by sensor/unit/type metadata.
The user superseded external-recorder-only operation with recording bundled into
the standard experiment as **respyrecorder** (`respyrecorder.exe` on Windows).
Source/provenance is in `native/recorder/README.md`.

- Rust launches one fixed Python engine with its packaged recorder path.
  `mpi.recording.NativeRecording` owns the native child's private pipes, output,
  readiness, stop and file completion. HTML/phone Start uses the existing action
  path; neither may select an executable, arbitrary path or shell command.
- Start prepares `Respyra-Calibrated-Breathing` before launching the recorder and
  requires the exact selected raw input, marker and derived subscriptions plus actual samples
  from each before participant setup acceptance or PsychoPy creation. Failure
  rejects Start. Before calibration, the derived channel emits NaN with the raw
  inlet timestamps; this represents unavailable normalized values, not zero force.
  Calibration never delays or rewrites raw capture.
- Vernier calibration activates `(force_n - center_n) / amplitude_n`; Polar
  calibration activates `(polarity × waveform_g - center_g) / amplitude_g`
  on that same outlet, preserving source identity and synchronized inlet timestamps.
  Immutable LSL metadata identifies the raw source, formula and pre-calibration
  representation; `calibration.completed` markers carry the parameters. No clipping
  or condition feedback gain applies. Wait for native reception of finite derived
  values through its first-finite receipt before trials. Verify nonempty raw,
  marker and derived data in final XDF.
- The installed Vernier Stream Mini mock identifies its raw outlet as model
  `GDX-RB-MOCK`; the physical belt uses `GDX-RB`. Both require the same raw
  Vernier Force channel in N. The selected inlet retains 60 seconds of samples
  during PsychoPy startup so early raw samples are still emitted on the derived
  outlet. `scripts/audit_mock_xdf.py` independently checks mock sequence,
  Force waveform, the raw Force copy, the Mini's own normalized breathing
  waveform and combined stream, Respyra calibration, trial markers and XDF
  footers. Its reconstruction covers the protocol, response markers and breathing
  samples; exact rendered frame pixels and flip times are not in XDF.
- One native watch query records visible streams and discovers later streams.
  The setup Record checkboxes can exclude specific discovered LSL UIDs before
  Start; the accepted raw input, Respyra derived outlet and event markers override
  exclusions. Unseen later streams record by default. View selection is local
  to the plot and does not change XDF capture.
  Stable source IDs deduplicate; source-less streams use UID. A producer must
  exist before subscription: late discovery cannot recover samples sent before
  connection. Publish a required derived outlet early if its first sample matters.
  Additional streams do not replace the selected validated input. Polar validity
  companions remain separate recorded streams unless the experimenter excludes
  them; the accepted waveform, derived outlet and markers remain mandatory.
- Recorder errors fail the study at cancellation checkpoints. Normal, stopped
  and failed runs attempt recording finalization after source/display cleanup.
  `recording.finalizing` remains inside XDF; final HTML result/Close markers follow it.
- Drain 600 ms, request native close, wait at most ten seconds, reap failures.
  Completion checks XDF bounds, headers, sample-chunk counts and matching footers
  for all streams, plus nonempty exact required streams. Promote `.xdf.partial`
  only on success. Preserve failures; never report an outlet/subscriber as disk evidence.
- XDF and original-schema CSV files use the remembered recording folder, defaulting
  to `data/` inside the selected Respyra installation folder; they never enter
  Git/Pages. Settings stores the folder under `%LOCALAPPDATA%/Respyra/`.
  The Experiment hub's Data folder segment shows the current path, opens it,
  and accepts either a browsed or pasted existing writable absolute path during
  setup. Choosing a folder does not move earlier files. After XDF
  verification and promotion, `mpi.bids_export` writes `bids/` with BIDS 1.11.2
  behavioral events and every nonempty recorded outlet, including Polar and Vernier
  Mini streams. A numeric outlet is BIDS physiology only when its positive nominal
  rate agrees with every recorded interval within 2%; otherwise use a timed
  `_beh.tsv` table without asserting a regular rate. String outlets also use timed
  behavioral tables. Each table preserves the original sample timestamps relative
  to the selected raw input and sidecar metadata preserves LSL identity, labels,
  units, channel order and processing provenance. Do not invent dropped samples.
  BIDS tables preserve integer channel values exactly and retain double-precision
  values to round-trip precision; MNE Raw may lose precision for integers above
  2^53, so the BIDS table and XDF remain the data authority for those channels.
  `mpi.bids_mne.read_bids_signal` opens fixed-rate physiology as MNE Raw and
  requires an explicit rate for irregular resampling; all channels remain MNE
  `misc` until their physical units and type are mapped deliberately. XDF remains
  the full-stream timing authority, including empty streams. BIDS export failure reports
  an error while preserving the verified XDF and participant record. Earlier
  recordings in `%LOCALAPPDATA%/Respira/data` remain untouched.
- After successful XDF promotion and BIDS export, `mpi.session_summary` reads
  that closed XDF and saves `<recording>_summary.png` beside it through Agg.
  XDF is the primary summary input. Trial targets/errors use synchronized
  accepted sample times; baseline diagnostics come from the study markers.
  CSV frame-level statistics can differ. No plot window opens. Pre-study
  stops skip plotting; later stops use captured phases. Plot failure reports
  an error without undoing the verified recording, participant record or BIDS.
- XDF is the primary cross-tool artifact. Its LSL headers retain source
  identity, channel order, labels, units, format, rate and processing
  provenance. The `recording.started` JSON marker stores BIDS-style subject,
  session and task labels plus custom participant fields in the XDF itself.
  Direct PyXDF/MNE and MNELAB import is a separate acceptance gate from BIDS TSV/JSON
  export. XDF is not a BIDS-valid raw format; never describe its embedded
  metadata as a BIDS validator pass or a direct `mne_bids.read_raw_bids` input.
- Participant number (0–100) and up to six custom label/value pairs are saved
  atomically on setup edits in local user settings and restored on launch.
  Odd/even participant parity chooses the study block order; the legacy session
  value defaults to `001` in recording metadata. Numeric participant
  entries render as `P000`, `P001`, etc. in XDF names; session and label-value pairs
  form underscore-separated filename parts before the unique suffix. Python appends
  a `participant-list.jsonl` record with full values only after XDF verification
  and promotion. A list-write failure reports an error while preserving the closed XDF.
  The setup dropdown marks numbers in this list red while leaving them selectable.
  A marked number means a verified XDF was saved, even if the run stopped early.
- Local `mpi.lsl_viewer.LSLViewer` owns separate display-only subscriptions to all
  visible numeric and string streams, with UID identity, full channel metadata
  and late discovery. The selected study inlet remains its only acquisition and
  calibrated-output owner. The study marker display uses the owner's projection;
  its readiness indicator uses native receipt, preserving pre-subscription naming.
  HTML stacks channels in one paged, ten-second plot. The display-only LSL
  viewer forwards timestamped numeric batches, retaining every sample at Polar
  ECG's 130 Hz rate; the desktop updates in batches and keeps up to 4,096
  points per channel. The native recorder remains the full-rate authority.
  Marker lines cross the visible lanes. The event catalog tab is generated
  from `src/mpi/event_markers/catalog.json` during web preparation.
- Optional Windows keyboard/mouse hooks (`mpi.input_capture`) capture only the
  Python study and native desktop windows while XDF recording is active. Rust
  supplies its PID so a virtualenv launcher cannot change the controller identity.
  Queue callbacks; publish catalogued markers on the study owner with the callback
  LSL time retained in `event_lsl_time`. Overflow/initialization failures fail the
  run; hooks stop and drain before recorder finalization. Defaults are off.
- Remote default is the LSL monitor: selected raw-channel value/unit, ten-second
  trace, recent marker names and recording status. Four-Hz coalesced snapshots
  reuse the existing clock-synchronized study inlet; this is the current delivery
  rate, not a target for future responsiveness. Prioritize getting the newest
  received LSL samples onto the remote screen with as little avoidable delay as
  practical while keeping trace motion smooth. Preserve source timestamps and
  waveform detail within bounded transport/rendering limits. Visual smoothing
  must not present invented values as measured data or keep a trace moving after
  samples stop; show gaps and stale status promptly. Measure sample-to-display
  freshness and visible continuity when changing this path, rather than treating
  animation frame rate alone as proof of live data.
  Preview is bounded to 32 channels and 100 local points. The private invitation
  shares this data; native paths, file summaries and assessment payloads stay local.
  Recording remains full-rate and includes supplementary streams beyond the preview.
  Full-stream stacks, calibrated health, native data receipts and local input
  options stay outside the existing bounded phone protocol.

Select checks by affected behavior under `VERIFICATION.md`; reuse valid
unchanged recording/study evidence from `VERIFIED.md`. Merely editing the
opening panel or recording-status presentation does not require these proofs.
For affected recording contracts, verify `tests/check_recording.py` with
independent PyXDF import, pre-calibration raw samples, marker order,
late numeric/int64/source-less streams, clock offsets,
Unicode paths and matching footers. Run failure tests in `tests/test_recording.py`,
then the real native UI/LSL check when lifecycle/IPC is affected and the packaged
synthetic round trip for a new installer. Report the
physical belt, scientific display timing and physical phone separately.
`tests/check_control_center.py` proves all-channel/late-marker preview and calibrated
XDF values with independent PyXDF. `--full-study` additionally executes all 48
configured trials and real PsychoPy displays with accelerated timings and simulated
responses; it is not a full-duration participant or physical-belt qualification.
Run it only for the complete-study triggers in `VERIFICATION.md`, not on every
UI or recorder edit.
