# Native recording contract

Read for recorder, Start, calibration/stream lifecycle, XDF or remote-data work.
The user superseded external-recorder-only operation with recording bundled into
the standard experiment as **respyrecorder** (`respyrecorder.exe` on Windows).
Source/provenance is in `native/recorder/README.md`.

- Rust launches one fixed Python engine with its packaged recorder path.
  `mpi.recording.NativeRecording` owns the native child's private pipes, output,
  readiness, stop and file completion. HTML/phone Start uses the existing action
  path; neither may select an executable, arbitrary path or shell command.
- Start requires the exact raw Force and marker subscriptions and a first raw
  sample before participant setup acceptance or PsychoPy creation. Failure rejects
  Start. Calibration changes study parameters; it never delays or rewrites raw
  capture. Calibration result markers retain the parameters used for later analysis.
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
- Remote default is the LSL monitor: selected raw-channel value/unit, ten-second
  trace, recent marker names and recording status. Four-Hz coalesced snapshots
  reuse the existing clock-synchronized inlet; no second acquisition/transform.
  Preview is bounded to 32 channels and 100 local points. The private invitation
  shares this data; native paths, file summaries and assessment payloads stay local.
  Recording remains full-rate and includes supplementary streams beyond the preview.

Verify `tests/check_recording.py` with independent PyXDF import, pre-calibration
raw samples, marker order, late numeric/int64/source-less streams, clock offsets,
Unicode paths and matching footers. Run failure tests in `tests/test_recording.py`,
then the real native UI/LSL check and packaged synthetic round trip. Report the
physical belt, scientific display timing and physical phone separately.
