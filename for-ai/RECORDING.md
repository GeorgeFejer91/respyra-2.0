# Native recording contract

Read for recorder, Start, calibration/stream lifecycle, XDF or remote-data work.
The user superseded external-recorder-only operation with recording bundled into
the standard experiment as **respyrecorder** (`respyrecorder.exe` on Windows).
Source/provenance is in `native/recorder/README.md`.

- Rust launches one fixed Python engine with its packaged recorder path.
  `mpi.recording.NativeRecording` owns the native child's private pipes, output,
  readiness, stop and file completion. HTML/phone Start uses the existing action
  path; neither may select an executable, arbitrary path or shell command.
- Start requires the exact raw Force and marker subscriptions and actual samples
  from both before participant setup acceptance or PsychoPy creation. Failure rejects
  Start. Calibration changes study parameters; it never delays or rewrites raw
  capture. Calibration result markers retain the parameters used for later analysis.
- The accepted study calibration creates `Respyra-Calibrated-Breathing`, with
  `(force_n - center_n) / amplitude_n`, synchronized inlet timestamps, original
  source identity and calibration parameters in its metadata. No clipping or
  condition feedback gain applies. Wait for native data reception before trials;
  add this identity to final nonempty-stream verification only after calibration.
- One native watch query records visible streams and discovers later streams.
  Stable source IDs deduplicate; source-less streams use UID. A producer must
  exist before subscription: late discovery cannot recover samples sent before
  connection. Publish a required derived outlet early if its first sample matters.
  Additional streams do not replace the study's validated Force input.
- Recorder errors fail the study at cancellation checkpoints. Normal, stopped
  and failed runs attempt recording finalization after source/display cleanup.
  `recording.finalizing` remains inside XDF; final HTML result/Close markers follow it.
- Drain 600 ms, request native close, wait at most ten seconds, reap failures.
  Completion checks XDF bounds, headers, sample-chunk counts and matching footers
  for all streams, plus nonempty exact required streams. Promote `.xdf.partial`
  only on success. Preserve failures; never report an outlet/subscriber as disk evidence.
- Installed XDF/optional original CSV files use the writable user data folder,
  survive uninstall, and never enter Git/Pages. CSV remains opt-in and unchanged.
- Local `mpi.lsl_viewer.LSLViewer` owns separate display-only subscriptions to all
  visible numeric and string streams, with UID identity, full channel metadata
  and late discovery. The study's Force inlet remains its only acquisition and
  calibrated-output owner. The study marker display uses the owner's projection;
  its readiness indicator uses native receipt, preserving pre-subscription naming.
  HTML stacks channels in one paged, ten-second plot (100 points each), with
  marker lines crossing the visible lanes. Its event catalog tab is generated
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
