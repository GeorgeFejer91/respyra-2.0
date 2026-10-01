# Native recording contract

Read for recorder, Start, calibration/stream lifecycle, XDF or remote-data work.
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
- Installed XDF/optional original CSV files use `data/` inside the selected
  Respyra installation folder, survive uninstall, and never enter Git/Pages.
  CSV remains opt-in and unchanged. Earlier recordings in
  `%LOCALAPPDATA%/Respira/data` remain untouched.
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
  reuse the existing clock-synchronized study inlet.
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
