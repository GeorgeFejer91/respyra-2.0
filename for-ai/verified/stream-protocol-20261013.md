# 2026-10-13 — Intrinsic stream diagnostics and BIDS/MNE protocol

Source-only change implementing D-0023/D-0024; no installer, deployment or physical-device claim.

## Observed passes

- Python 3.12 with the existing ignored timing-analysis dependencies: 79 focused
  tests across stream_protocol, BIDS export/MNE, Polar/Vernier input, parallel
  recording selection, setup and mock auditor. The original per-waveform
  get_all readiness mutation caused three expected failures; restoring the
  implementation passed. A new Rust computation-plan test failed before the
  fix because selected-only filtering discarded intrinsic quality/readiness.
- Locked Rust library tests: 60 metrics + 47 output + 16 runtime = 123 passed.
  cargo fmt and all-target clippy for these three crates passed.
- Real CLI Mini publication and official pylsl readback passed separate and
  single factory Polar modes and both custom Session7 mode. The actual Respyra
  reader opened both new Polar contracts in the same private session.
  Evidence: .for-ai-local/bundled-publisher-0735a6f728f3492588b872ad848cba96.
- Three private-session headless native XDF captures selected Force, PCA and DT.
  Each closed file has three raw inputs, three calibrated bundles and markers;
  XDF rows retain support channels, source formulas/timestamps and footers.
  Own calibration and optional-source loss were checked. PyXDF independently
  decoded every file. Per-source XDF channels were covered exactly once across
  BIDS data/support tables; MNE opened ten numeric data/support tables per run,
  default measurement counts were checked and BIDS validator 1.15 reported zero
  errors (optional NO_AUTHORS warning).
  Evidence: .for-ai-local/bundled-bids-mne.log and the three folders below.
- Root web tests: 8 passed. Root UI: 8 headless Chrome layouts, 22 actions,
  Start/Stop and zero page errors. Bundled support values do not become plot
  lanes. Screenshot inspection confirmed the main data lanes.
- Mini --streams: headless Chrome default/reset/reopen, optional diagnostic
  choices, metric picker, normal/mock behavior in both applets passed.
  This deliberately selects the changed stream behavior; the full battery/
  titlebar test remains outside this task and had failed in previous work.
  Screenshot inspection confirmed optional validity choices in the picker.
- Mini docs: catalog/filter checks at 320/375/1280 px passed. Root project site:
  five pages, 40 layouts, enlarged text, marker catalog and links passed.
- Both context checkers passed, with existing dirty/unborn-worktree warnings.

## Native recording folders

- parallel-recording-2e82885e96ff448697e8611dac2b1295 (Force)
- parallel-recording-b91393266723472d8cfb052940ca47ad (PCA)
- parallel-recording-98c08a3a5f284478acf7107923bc517e (DT)

These live under ignored .for-ai-local. The capture precedes the additive
raw_waveform_channel_index and per-channel validity-reference metadata fields;
its single-waveform readiness mapping is still valid. Fresh publisher metadata
and focused tests cover the added references. No full PsychoPy trial matrix,
physical Polar/Vernier, fresh installed-suite or native WebView run was performed.
The mock auditor's bundled channel lookup was tested; a new full mock-study
replay was not run. Older physical/full-study evidence is not upgraded to a new
bundle-format claim. MNE is an optional analysis dependency and no FIF export
is generated automatically.

## Skills and source state

The user authorized installing quality-implementation and test-engineering from
kabiir90/Software-Engineering-Skills, revision
13b9869e62be755e1bd254f6c4a90029185a50ed. The installed packages contain Markdown
instructions/references and the upstream MIT license. The shared repository
control plane takes precedence over their generic document/gate layout.

Both Git worktrees remain unborn/untracked; no commit or push was performed.
The optional Rusty backend compile check passed after fixing existing liblsl-only
Vernier construction/count guards inside the affected publisher setup. It still
rejects aggregate Vernier publication explicitly. This is compile evidence,
not live optional-backend interop; its unused adr_candidate_fields warning
remains outside the default all-target lint gate.

Source SHA-256 values for this receipt:

- `src/mpi/stream_protocol.py`: `9f742b3e595abf384c4b419c41994a1c8f9c54e6ed47519e6d4e3453cde578fc`
- `src/mpi/bids_export.py`: `d364ae53bb3b4a4951263823f150e06bc194c73e36fe1d99055e0651400cf370`
- `src/mpi/bids_mne.py`: `2c20caebab10ca618a20d095d39d8bdbea612ebb4324d25659589626f7987625`
- `src/mpi/lsl_polar.py`: `659000aa75c3d6d6e534a67531bfaf07c73ca658cbca7cceed826ca452b01fbd`
- `src/mpi/lsl_force.py`: `49989bfb800559419fdc8c6f7f768aeb76d808d9bfe9d5c34a64480893ded1e2`
- `src/mpi/lsl_viewer.py`: `a56f72e54d528fe557faaa3ce43f54b48469d485f7e427b12c8068d618b109b1`
- `web/experiment-hub.js`: `b2044b718c80e5453d7ed6ed3d9f5a704cfe7cbce32ace4a1d507f9ac3562c6d`
- `mini-streams/crates/polar-h10-metrics/src/lib.rs`: `f14a03979b155ac9d8353a9f272487c5050039ce0ed60e80bc02ff258112484d`
- `mini-streams/crates/polar-h10-output/src/config.rs`: `8e61a20b6890bd12e92b0c9c9850f59e0d4fa978a3daf707b6f552124b72d27c`
- `mini-streams/crates/polar-h10-output/src/lib.rs`: `be3fef089bec3e7c12084e2e5019f72517a6034e8425ba1b72ab64190aa9ece3`
- `mini-streams/crates/polar-h10-output/src/lsl.rs`: `31871f8f777426b7a92c8b923c00361e24a7d643a11877d19419d286139996e5`
- `mini-streams/crates/polar-h10-output/src/provenance.rs`: `51d04391192062a27039d39e55f7e86b1a17012ba0ac775f8669105ab33029b9`
- `mini-streams/crates/polar-h10-output/src/rusty_lsl.rs`: `abd0028ad27aa8eacee7e355ef967975a242cd6683a82a62d38820f52bd05758`
- `mini-streams/crates/stream-mini-runtime/src/lib.rs`: `515afe425e11400eb1ec38a16f4f8d2a0e4257b26e2afc2faa55ef223ec12aa1`
- `mini-streams/apps/polar-stream-mini/ui/app.js`: `01ec3f0d2ecf920a463452edbd8b565a03c5a01bf8040b12d7a639a914850ab8`
- `docs/stream-protocol.md`: `d7fb51d89b99ba2642f710e09aa6b400c013b0e2bf32bd23609610889da1f622`
