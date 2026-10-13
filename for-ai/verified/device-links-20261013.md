# 2026-10-13 — Two recorded Bluetooth Link streams

Source-only D-0026 implementation, superseding D-0025. No installed-runtime,
deployment or physical-device claim.

## Scope

`Polar_Link` and `Vernier_Link` remain visible, directly recorded applet outlets.
The combined `Respyra_Housekeeping` worker, its lifecycle and startup requirement,
reserved transport exclusions, viewer filter and extra Start marker fields were
removed. Native discovery again records visible and late outlets except explicit
Record opt-outs. Waveform quality/readiness and Vernier acquisition diagnostics
remain intrinsic channels. With both devices and all three usable calibrated
inputs the factory inventory is 14 outlets. A quiet Link outlet does not block
Start. Link codes remain 1 lost / 2 restored, with original event timestamps;
they do not provide continuous RSSI or packet-loss estimates.

## Observed passes

- The new parallel fixture failed against the former implementation: seven
  required streams expected, eight with the combined collector observed.
  Evidence: `.for-ai-local/device-links-before.log`.
- 92 focused Python tests passed across recorder, setup, parallel input,
  event catalog, stream roles, Polar/Vernier consumers and BIDS/MNE readers.
  Evidence: `.for-ai-local/device-links-python.log`.
- Three headless private-session native recordings selected Force, PCA and DT.
  Each closed XDF contains three raw inputs, three calibrated bundles, study
  events and both direct Link streams: nine streams, seven required. Both Link
  outlets retain exact loss/recovery codes, increasing original timestamps and
  event roles. No combined outlet exists. The Force proof checks viewer
  visibility. Calibration, intrinsic diagnostics, comparison-source loss,
  independent PyXDF readback and stream footers passed.
  Evidence: `.for-ai-local/device-links-{force,pca,phan}.log`.
- The separate late/quiet native proof passed with seven streams. A preexisting
  Polar Link has zero samples and a zero footer without blocking Start; a late
  Vernier Link has both original events and a two-sample footer. Original raw
  timestamps before calibration, finite derived receipt, explicit opt-outs,
  marker order and anonymous int64 values above 2^53 also passed.
  Evidence: `.for-ai-local/device-links-late.log`.
- Direct PyXDF/MNE checks opened eight numeric streams from each of the three
  parallel XDFs, including Link events, using a declared 100 Hz analysis grid.
  Five Respyra events were read as annotations; MNELAB's importer opened the
  selected raw signal and its event annotations for each file.
  Evidence: `.for-ai-local/device-links-xdf-{force,pca,dt}.log`.
- Matching BIDS checks retained exact original values/timestamps and opened
  twelve numeric measurement/support views per capture. Pure supporting tables
  require explicit support selection in the Respyra MNE reader. Validator zero
  errors; optional `NO_AUTHORS` warning.
  Evidence: `.for-ai-local/device-links-bids-{force,pca,dt}.log`.
- Eight web tests passed. Static references passed five pages and forty
  headless Chrome layouts, enlarged text, event dictionary, search and links.
  Screenshot inspection confirmed the updated variable reference.
  Evidence: `.for-ai-local/device-links-site.log`.
- Unchanged Mini producer behavior reuses the real-publication interoperability
  and Rust checks in `stream-protocol-20261013.md`. The native recorder binary
  and serializer are unchanged; current captures test their changed selection.

## Capture inventory and SHA-256

- Force: `.for-ai-local/parallel-recording-2f85c361305c4d7e9aea5c3fc7b6c529/P017_Session-001_fe3fa90a8dd34d16aff6671e21abd6e8.xdf`
  `4bf6d6e4c4956b64cb94ceb3a5171deaa1a216d6625af18fdb297442f4f33f31`
- PCA: `.for-ai-local/parallel-recording-13cf15530c9f4b8d99a9ef66aeb5290b/P017_Session-001_ec36aebefffd45eb923fd6690825b2d9.xdf`
  `8bd9511d76d06349dd9fab9022240431c3eab5d59f1790fefa830757cd8a7fe8`
- DT: `.for-ai-local/parallel-recording-718be86ed7cd4152badda7b6bd4c2d4e/P017_Session-001_ae065fd26de84cfcb0c8ef5f13af65d5.xdf`
  `3708dff7a5fda79ff0c994cf64741d4db771ab3d0573852374a3e003f3c9c220`
- Late/quiet: `.for-ai-local/recording-proof/Unicode café/P002_Session-001_Age-28_7bc7054eee224c808fc86196a5896eb9.xdf`
  `72689c74c63c79cb67460cd3f720c33ac7349760eb4acc028f60d4f5da6fc52b`

## Corrections and limits

The first direct-MNE attempts lacked MNEXTEND, then its ONNX import dependency.
Their failed logs remain under `device-links-xdf-*-missing-{import,onnx}.log`.
Final checks use private ignored dependencies: MNE 1.13.2, PyXDF 1.17.5,
MNELAB 1.5.6 and MNEXTEND 0.2.0; no system package was changed. PCA/DT PyXDF
reported differing segments/clock-segments while checks passed. These synthetic
captures establish storage/import behavior, not physical Bluetooth or scientific
timing accuracy. Silence alone cannot establish a connected device, and an
applet shutdown may prevent a final transition report.

No new installed suite, physical H10/GDX-RB, native WebView or full PsychoPy
session was run. Both checkouts remain unborn/untracked; no commit/push/release.
A new qualified installer must include these source changes. Current docs,
decisions and verification gates were updated for D-0026.

## Source/artifact SHA-256

- `src/mpi/recording.py`: `2481e01d668bf44a7dc49d30ce393e248cc258bff265babbea3e72540d63ea5c`
- `src/mpi/lsl_viewer.py`: `07dbdcfd1f6bba0ddd21db75c4cdac10a60a5d554481928497b5174cb7f0fa1e`
- `src/mpi/event_markers/catalog.json`: `2bc297efae3c6ac723189701682bc2b6a012580d6cfb41097f91d5387b6bb6ec`
- `tests/test_event_markers.py`: `30b4ae9b8014ea4c664ceca1b17b9c37800ddeec0b9a258ad13fdd2f5d1c61e4`
- `tests/check_parallel_recording.py`: `0a865c7ee19a7ec5260b352fb3c8326adf0eee411f28417ecd0215c4b5c169a8`
- `tests/check_recording.py`: `aead228dfed33f2049f89223cd98f633f7c147ff18a2c873b8821c24ea9deae3`
- `tests/check_bids_compatibility.py`: `f826b6e48ab362f193357b5a377de57a4a786f8d76d26d8d73e1b8d6a11b28f4`
- `tests/check_project_site.cjs`: `8117b3685ff07fe6dba6706bc5293b6e135d36aec8bd961a5f6dd6c19c699bc6`
- `companion/variables.html`: `09b40f09fe2841c0a07078bb457f73050cda3490e7a761ab96a7751dd5884418`
- `companion/markers.html`: `2834e0be388fab8ea39cad01f8c6609ba4c75c050fe64ded002e70b64afd381f`
- `companion/marker-catalog.json`: `fb51c83f9781a151fb7a223012647f353edb93b19741d13a3c5b5571ae72708f`
- `web/marker-catalog.js`: `3386c971c78d5cc25dabe4277b14a955014214d4aeadabbc8d12512a1ffcc46c`
- `docs/stream-names.md`: `8aaf1e7decdcaf3995837b33d4875342641083e7dd9bb2a74c16872c84dd6ba6`
- `docs/stream-protocol.md`: `8ed72595860bc1ed3fd23fa5b1a299c3cfb5c023e9a3382bd19e2552b0f8353b`
- `.for-ai-local/recorder/runtime/respyrecorder.exe`: `817b43bf2d4da08515eeddcb48a3a169c1d014b03fa46a10768bf9139175a4fa`
