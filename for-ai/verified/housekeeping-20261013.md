# 2026-10-13 — One recorded Housekeeping stream

Source-only D-0025 implementation; no installer/deployment/physical-device claim.

## Scope

`mpi.housekeeping` consumes both Mini Link transports and publishes one required
JSON diagnostic outlet, `Respyra_Housekeeping`. NativeRecording owns its lifecycle
and sample-readiness gate. Native discovery excludes the reserved transport IDs,
including late discovery; the viewer hides them. Waveform/calibration contracts
are unchanged. Mini publisher content was restored to this turn's baseline after
the user chose aggregation; two restored files have normalized line endings.
Current full-device defaults record 13 streams; two internal Link outlets remain
on LSL. Marker payload definitions and generated references were updated.

## Observed passes

- 88 focused Python tests: Housekeeping, recording, setup, parallel inputs,
  Polar/Vernier consumers, stream roles and BIDS/MNE. Another 14 marker tests
  passed after adding the new required Start fields to their fixture.
  Evidence: `.for-ai-local/housekeeping-python-final.log` and executed marker check.
- A deliberate lost/restored mutation failed both device cases; source was
  restored and normal tests passed. Evidence: `housekeeping-mutation.log`.
- Three private-session native XDF captures selected Force, PCA and DT. Each
  contains three raw inputs, three calibrated bundles, study events and one
  Housekeeping stream, all eight required and nonempty. Both devices' loss/
  recovery reports are present; no separate Link stream is recorded. The Force
  proof also observed viewer filtering and Polar input disappearance while
  Vernier collection continued. Footers and independent PyXDF readback passed.
- Matching BIDS checks retained all values/timestamps and opened ten numeric
  MNE data/support views per capture. Validator zero errors; optional NO_AUTHORS
  warning. Logs: `.for-ai-local/housekeeping-bids-{force,pca,dt}.log`.
- Final-catalog native proof passed late Link discovery/exclusion, original
  raw timestamps before calibration, finite calibrated receipt, explicit
  opt-outs, anonymous int64 values above 2^53 and complete footers.
  Evidence: `.for-ai-local/housekeeping-exact-time-proof.log`.
- Publisher restoration: cargo fmt and 47 output library tests passed.
  Evidence: `.for-ai-local/housekeeping-publisher-recheck.log`; prior real Mini
  publication evidence remains applicable to its unchanged behavior.
- Eight web tests passed. Updated references passed five pages and 40 headless
  Chrome layouts, enlarged text, marker dictionary, links and search.
  Evidence: `.for-ai-local/housekeeping-site-complete.log`.

## Capture inventory

- Force/disappearance: `.for-ai-local/parallel-recording-b9ce17c66b9d4094af5e69f2fa633b92/P017_Session-001_afd6c3fc199149d790145ea14c741e26.xdf`
- PCA: `.for-ai-local/parallel-recording-6e687c8d89eb450b950c8fe513eb6970/P017_Session-001_5c12c58f485544a695086c3b7604daf5.xdf`
- DT: `.for-ai-local/parallel-recording-c61b628c59b54d5d806255fdd467d5b1/P017_Session-001_6a580e83553b4c91b4840eff0e242916.xdf`
- Late/final catalog: `.for-ai-local/recording-proof/Unicode café/P002_Session-001_Age-28_4e0a07931dff40b88e83b9015e15ed18.xdf`

## Corrections and limits

The first disappearance fixture closed its publisher before observing queued
reports; it now waits for actual forwarding. The older standalone recorder
fixture needed matching run IDs and real channel metadata. Default PyXDF
dejittering shifted timestamps; the proof now inspects original timestamps.
A stale site assertion of 17 outlets now requires the current 13 recorded
streams and visible Housekeeping definition. No production timing or assertion
was weakened.

Applet availability is distinct from Bluetooth state. Unknown is not connected;
snapshots retain the last report and its time. Shutdown can lose unconsumed
reports; availability loss does not invent a physical disconnect event. JSON
diagnostics are inspected directly rather than as numeric MNE Raw.

No new installed suite, physical H10/GDX-RB, native WebView or full PsychoPy
session was run. Both checkouts remain unborn/untracked; no commit/push/release.
A new installer must include and qualify the source changes.

## Source/artifact SHA-256

- `src/mpi/housekeeping.py`: `5a57a67e3235567f9b54fe5361c1464e496d95511c1a18d02fc27a40390d5929`
- `src/mpi/recording.py`: `07895351fbc3e835f65b9f8c83487b0c923553a79de202a1e8b0b5ed4116fb62`
- `src/mpi/lsl_viewer.py`: `82fa29194ff6188d1d86f488212464263876e16b5b67125cb3510650476287a6`
- `src/mpi/event_markers/catalog.json`: `0fc1082e7418e4b4d8885463ae49609f5377345f6f91bb0d7712f883f5a6333b`
- `tests/test_housekeeping.py`: `893fc9e740d967cb225db90b90516d4e7f7bd18e5eed00da9683f3abe2059084`
- `tests/test_event_markers.py`: `13e442259ed3aa6a9a41de478fbca314f169ad6a946e95660669047ccd1e2064`
- `tests/check_parallel_recording.py`: `8cd63453d1d799a7ca804039210d1142c2100b92f13838607c876d6ca36e456b`
- `tests/check_recording.py`: `396f3c21cd6f05efe478e2746c6d9d72e69c436cfb1fe1354f18509a53d5cfcc`
- `tests/check_project_site.cjs`: `aca5372577ef5968a07d928ae2909f93cfb2bad0fb1826db87e3dc3741206a3b`
- `companion/variables.html`: `aac307ba86ba4906d04eaded9fdaa11acf728c17c1479dc54ab0e300d2a50da5`
- `companion/markers.html`: `9e027aa09e42e8f3491377de7d5bdf46ccbbea1ab46cb23282892b52c9044bee`
- `companion/marker-catalog.json`: `c727db5d60b9433a38c9251b55e2fa729af17c3602f41ef643e7e93e9d73593c`
- `web/marker-catalog.js`: `627ccb1fa96438a9252b4751a3869644e1674e0cb99f9d244d7e6247088aa48e`
- `docs/stream-names.md`: `ed3e3fa9866128eb0c637e81d927cd65533570b6dce749e0f8d02d150e30e803`
- `docs/stream-protocol.md`: `ffda23c585362fed1b88089ade2f1b515b45bd74447b9045f4c3f34f1b14fd2c`
- `mini-streams/crates/polar-h10-output/src/lib.rs`: `861298f08a3b9c9696baa467b04e4a3e47d155f06375cc212df18e1ebea88d2f`
- `mini-streams/crates/polar-h10-output/src/lsl.rs`: `14778ee7593d1473ea3818e6bb8a179c1446d9ef324d38f906fd6fe732c5aa9d`
- `.for-ai-local/recorder/runtime/respyrecorder.exe`: `817b43bf2d4da08515eeddcb48a3a169c1d014b03fa46a10768bf9139175a4fa`
