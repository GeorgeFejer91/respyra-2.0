# Verification inventory and reusable evidence

Use `VERIFICATION.md` for selection and invalidation rules. Keep one current
entry per behavior/check; replace superseded entries rather than adding session
narration. Record new observed passes here before handoff. Do not run unrelated
suites to initialize this ledger.

## Execution modes

Apply the background requirement in `VERIFICATION.md` before every run.
These modes describe inspected launch paths, not a new runtime verification.
Reclassify affected checks when their launchers or descendants change.

| Checks | Execution mode / constraint |
| --- | --- |
| Context/link/diff checks, Node unit tests, Cargo fmt/test/clippy and non-GUI build/import helpers | Captured CLI output, no visible consoles. Audit spawned children; Rust's shutdown test already uses `CREATE_NO_WINDOW` for its Python workers. |
| `pnpm check:ui`, `pnpm check:remote`, including the latter's live-VDO browser mode | Playwright launches headless Chrome. Preserve that setting and isolated browser contexts; inspect rendered results without showing a browser. |
| Python focused tests excluding the real Windows hook test, including marker/study-flow tests with fake `Window` objects and the desktop pipe process check | Nonvisual as inspected; keep fake-display/controlled-input boundaries and console children hidden. Real focus/input-hook behavior requires isolation. |
| `tests/check_recording.py` and `tests/check_control_center.py` without `--full-study` | Nonvisual LSL/recorder workers as inspected; hide console children, retain private sessions and observe cleanup. |
| `tests/check_native_lsl.py` (every mode), its `check_native_ui.cjs` helper, and installed-runtime variants | Requires isolated GUI execution. The Python harness launches a real Tauri executable; headless phone Chrome does not hide its native target or PsychoPy windows. No established desktop isolation in the harness. |
| `tests/check_control_center.py --full-study` | Requires isolated GUI execution: launches actual PsychoPy displays even though responses are simulated. No established desktop isolation in the harness. |
| `tests/test_input_capture.py`, installer wizard, native focus/input checks and physical display/device qualification | Requires a compatible isolated environment or a later explicit user request for a visible check. The hook test registers real Windows hooks. Quiet/silent installation alone does not prove wizard behavior or suppress later GUI children. |

If an isolated runner is unavailable, mark the applicable GUI check `NOT RUN`
and keep its existing evidence limits. Do not run a GUI check merely to verify
that its windows will be hidden. Historical receipts below record behavior;
they do not establish compliance with this new background-execution policy.
This launch policy does not invalidate unaffected behavioral evidence or
require rerunning checks merely to classify their execution mode.

## Inventory

This maps existing owners and checks; it does not certify the current working
tree. `unrecorded` means no scope-specific receipt has been imported here, not
that a check failed or was never run. `historical-unbound` means an inspected log
passed but lacks the exact tested input identities required for current reuse.
Update the affected row and its compact receipt after the next relevant pass.

Python check cells list arguments to `uv run --frozen pytest`; Python integration
scripts use `uv run --frozen python`. Node unit checks use `node --test`.
Paths below identify owners, not an exhaustive dependency closure: include the
relevant callers, consumers and shared inputs when recording a reusable pass.

| Behavior / owner | Focused check | Recorded evidence state | Invalidate / rerun when |
| --- | --- | --- | --- |
| Signal stitching and rise/fall waveforms: `src/mpi/signal.py` | `tests/test_signal.py` | unrecorded | Signal functions, input assumptions or numeric dependencies change. |
| Raw Force metadata/units, finite samples, duplicate identities and saved selection: `src/mpi/lsl_force.py` | `tests/test_lsl_force.py` | unrecorded | Force validation, source identity/storage, freshness or producer metadata contract changes. |
| Automatic discovery, exact reconnect, loss/retry and cancelled selection: `src/mpi/lsl_setup.py` (`SourceSetup`) | `tests/test_lsl_setup.py` | unrecorded | Setup state transitions, source selection, remembered identity or Start prerequisites change. |
| Marker payload/catalog, renaming, key timing and flip alignment: `src/mpi/event_markers/` | `tests/test_event_markers.py` | unrecorded | Event owner/catalog, timing, phase wrappers or payload consumers change. |
| Short study completion/abort/error, no-data calibration and original CSV modes: `scripts/run_experiment.py`, `src/mpi/validation_study_jenny.py` | `tests/test_experiment_flow.py` | unrecorded | Study flow, calibrated input, marker contract, logging schema or installed `respyra` APIs change. |
| Closed actions, ordered bounded pipe, public snapshots and Stop receipts: `src/mpi/desktop_bridge.py` | `tests/test_desktop_bridge.py` | unrecorded | Action validation, sequence/framing/queue limits, projection or cleanup receipts change. |
| Real engine startup/import isolation and marker lifetime through Close: `scripts/run_experiment.py`, desktop bridge | `tests/test_desktop_process.py` | unrecorded | Launcher/imports, inherited stdio, pipe contracts or engine lifetime change. |
| Optional Windows hooks and shutdown: `src/mpi/input_capture.py` | `tests/test_input_capture.py` | unrecorded | Hook registration, filtering, queues, drain/cleanup or marker handoff changes. |
| Recorder readiness, missing/failed/hung child, partial files and XDF completeness: `src/mpi/recording.py` | `tests/test_recording.py` | unrecorded | `NativeRecording`, `inspect_xdf`, child/readiness protocol or XDF validation changes. |
| Native XDF persistence, calibration/cleanup markers, late/source-less streams and Unicode paths: `native/recorder/`, recording owner | `tests/check_recording.py` | historical-unbound; see recorder receipt below | Recorder source/binary/DLLs, supervision or serialized data/marker contract changes. |
| All-channel preview, late markers and calibrated XDF values: `src/mpi/lsl_viewer.py`, `LSLForceSource`, recording owner | `tests/check_control_center.py` | historical-unbound; covered by full-study receipt below | Viewer subscriptions, calibrated output/formula, time bases or recording data change. |
| Complete 48-trial synthetic study: study/calibration/recording owners | `tests/check_control_center.py --full-study` | historical-unbound; see full-study receipt below | Complete-study triggers in `VERIFICATION.md`; panel presentation does not invalidate it. |
| Browser action ordering, timestamps and overload: `web/action-queue.js` | `tests/action-queue.test.mjs` | unrecorded | Queue sequencing, clock capture, dispatch or failure behavior changes. |
| Finite trace geometry and sample-loss gaps: `web/lsl-monitor.js` | `tests/lsl-monitor.test.mjs` | unrecorded | Trace computation, sample/time assumptions or monitor rendering changes. |
| Invitation/command/state contracts and mutual BRSP proof: `web/remote-profile.js`, shared BRSP assets | `tests/remote-viewer.test.mjs` | unrecorded | Invitation, scopes, validation, proof/state or reliable mutation contracts change. |
| Opening panel, dialogs, actions, fit/recovery and enlarged text: `web/index.html`, `style.css`, controller/desktop/text-fit modules | `pnpm check:ui` plus inspect changed area | reusable; see remote approval receipt | Relevant DOM/CSS, rendering/status projection, fonts or Pretext inputs change; no downstream rerun for isolated presentation. |
| Companion/Recorder embedding, responsive layouts and remote mutations: `companion/`, remote-host/profile modules | `pnpm check:remote` (Recorder companion configured); live VDO separately | reusable; see remote approval receipt | Shared phone behavior/assets, embedding or remote transport changes; truly desktop-only selectors/paths leave phone evidence valid. |
| Rust engine paths, closed actions/framing and normal/failed/hung shutdown: `src-tauri/src/main.rs` | Cargo fmt/test/clippy commands in `VERIFICATION.md` | unrecorded | Rust supervisor, command/capability/configuration or build/runtime inputs change. |
| Native remote ownership, approval, scopes, sequence, expiry, deduplication and bounded projection: `src-tauri/src/viewer.rs` | Cargo tests (viewer module), fmt/clippy | reusable; see remote approval receipt | Grants/approval, owner/peer/epoch/lease, dispatch, revisions or data visibility changes. |
| Actual WebView/Python/LSL selection/reconnect, Start/Stop/Close, QR and remote round trip | `tests/check_native_lsl.py` after a matching native build | historical-unbound; see native receipt below | Native/pipe/lifecycle/remote contracts or consuming runtime change; UI-sensitive changes need focused WebView evidence rather than automatically this whole harness. |
| Current public phone page pairing and published byte parity | Published mode in `tests/check_native_lsl.py`; deployment/parity readback | see published approval receipt | Deployed companion inputs or endpoint state changes, or current deployment is claimed; local intercepted assets cannot qualify it. |
| Standalone/installed Windows runtime and exact NSIS artifact | `PACKAGING.md` build/import/install/native/hash gates | unrecorded | New installer/runtime/artifact bytes or release promotion; ordinary UI source iteration does not require packaging. |
| Physical belt/phone, scientific timing and other operating systems | Separate named hardware/platform qualification | NOT RUN / unverified in `PROJECT.md` | Those surfaces are requested or claimed; synthetic/browser evidence does not qualify them. |
| Agent routing, policy links and control-plane structure | `for-ai/scripts/check-context.ps1`, diff and local-link review | Record the policy change's final checks in handoff | Router/rule/linked document changes; this never triggers product suites by itself. |

Shared inputs invalidate their consumers only: Python locks/packages/config for
Python checks; Cargo locks/toolchain/capabilities for native Rust checks; pnpm
locks/local fonts/Pretext/prepared assets for web checks; recorder binaries/DLLs
for recording integrations. A dependency edit does not invalidate every row by
default. A discovered regression invalidates the implicated rows even if their
source files are unchanged. Stop once selected checks pass for the final inputs.

`scripts/prepare-web.mjs` copies `web/style.css`, text-fit, controller, action
queue, monitor and remote-profile modules into `companion/`. A `web/` path is
therefore not automatically desktop-only. If shared presentation changes reach
the phone, check its affected rendering too (the mocked `pnpm check:remote`
provides existing coverage); preserve unchanged transport/pairing/study evidence.

## Entry format

- Scope: behavior/function and the check that actually covers it.
- Result/date: observed result and date; distinguish new execution from reuse.
- Inputs: tested commit; hashes of any uncommitted tested inputs; relevant
  source, callers, consumers, tests, shared assets, locks/config and runtime/tool
  versions. Artifact checks bind the actual executable/installer hash.
- Evidence: exact command/options and a retained output location or CI link;
  include a concise observed result. Keep raw/private output out of Git.
- Limits/state: tested environment and exclusions; `reusable`, `invalidated`
  with reason, or `historical-unbound` when input identity is unavailable.
- Execution: captured CLI, headless browser or isolated GUI runner; identify
  the isolated environment and its supported native/graphics scope when used.

Reuse requires comparison with current relevant inputs, including uncommitted
work. A different HEAD alone does not discard a pass. `REUSED` cites the original
entry; it never updates the execution date or pretends the check ran again.

## Retained baseline evidence

### Remote QR request and local approval

- Result/date: `VERIFIED`, 2026-09-27; Windows debug WebView2 target and Chrome.
- Scope: QR button/popup; automatic private-link request; pending native consent,
  no state/effects before Approve; Reject, fresh QR retry in the same tab,
  request expiry/binding; approved setup/Start/Stop/Close, real PsychoPy flip and
  independently decoded XDF. Restored base pages remain disconnected.
- Checks: `pnpm test:web` (6 pass), `pnpm check:ui` (14 actions, 7 layouts,
  zero clipping/errors), `pnpm check:remote` (12 phone layouts, 9 mutations,
  opaque Recorder iframe, plus QR popup at 820×760/1440×900); Cargo fmt/test
  (9 pass)/clippy; `pnpm tauri build --debug --no-bundle`;
  `uv run --frozen python tests/check_native_lsl.py remote` (public VDO,
  locally routed companion, 27 markers through Close, 3 nonempty XDF streams).
- Inputs: base `5262dab597ac74dc270226f1122d610531037991` plus scoped working
  source/test/lock hashes in ignored `.for-ai-local/approval-inputs.json`;
  manifest SHA-256 `3ff39ba64aaee8c8d70137a9a0f4adf218472b98447418ff06286396db49dbca`.
  Native executable SHA-256
  `a323cd101539febd1ca7f25014d80026989ba4d9b288d3766d94dfc2b08a9fa6`.
  Node 24.19.0, Cargo 1.96.0, Python 3.10.11; locked dependencies unchanged.
- Evidence: `.for-ai-local/native-approval-check.log`,
  `.for-ai-local/remote-approval-browser.log`, rendered native QR/approval PNGs.
  The QR pixels decoded to the private link; no physical camera was used.
- Limits/state: `reusable` for the named inputs; no physical phone/belt,
  installed release, forced relay or scientific timing claim. Public asset
  publication and non-intercepted pairing require their own receipt.

### Published approval flow

- Result/date: `VERIFIED`, 2026-09-27. GitHub Pages reported `built` for
  `f4f92132f0f72d394684eda1f2051203c8aaed29`, from source
  `73991b1fad951065c903e08bb30d8e6ce1ab2b8a`.
- Checks: fetched 14 public HTML/module/profile/vendor/provenance assets and
  compared exact bytes with the Pages Git blobs; all matched. With
  `RESPYRA_PUBLISHED_PHONE=1`, `uv run --frozen python tests/check_native_lsl.py remote`
  passed without asset interception: displayed QR decoded, phone requested
  access, desktop rejected then approved a fresh same-tab request, typed remote
  setup/Start/Stop/Close reached Rust/Python, and 3 XDF streams had nonempty
  samples and matching footers. 27 markers stayed contiguous through Close.
- Inputs: source commit above, executable hash in the remote approval receipt,
  locked runtime unchanged. Evidence: `.for-ai-local/public-approval-bytes.json`
  (SHA-256 `28bd2cd36a01f103fdfbf1ac26261f24be1fefbe9ac850d5321400300d66f743`),
  `.for-ai-local/published-approval-check.log`
  (SHA-256 `c5aed12866f15140313fe0c76b1cc1fc0b8a0460639655c4f64d239ea525d41a`).
- Harness follow-up: removed Python 3.10's invalid list default/choices
  combination. The actual parser prefix passed default/all-mode and explicit
  remote-mode checks; no runtime behavior or published bytes changed.
  Final harness SHA-256 `3e073aacc77c978c8891b558b65b2f73c1ca0cded7237a1fb87cb159d439a2f8`.
- Limits: observed public endpoint and same-machine Windows WebView2/Chrome
  pairing with synthetic LSL. No physical camera/touch, live belt, installed
  release or forced-relay qualification. Reuse requires unchanged relevant
  source/runtime inputs and deployment; this receipt is not indefinite endpoint monitoring.

These local logs were inspected when this policy was adopted. Their passing
results remain historical evidence, but they do not record the exact tested
Respyra revision/runtime identity. Do not infer that binding from timestamps,
the current HEAD, or the liblsl revision printed in a log. Refresh only when
the respective scope needs current evidence; panel styling does not need it.

### Complete synthetic study and XDF

- Result/date: `VERIFIED` historical pass, 2026-09-27.
- Scope: `tests/check_control_center.py --full-study`; 48 completed trials,
  calibration, all-channel preview and independently decoded raw, marker,
  calibrated and late-marker streams with matching sample counts/footers.
- Evidence: `.for-ai-local/full-study-check.log`, ending with `result: passed`,
  `full_study: true`, `trials: 48`. Invocation wrapper was not retained.
- Log SHA-256: `d15e374621ec157163ff51bdc45d0ad72ddd6633739ad0bff68a22c5cf928239`.
- Inputs/state: `historical-unbound`; exact tested source/dependency/artifact
  identities were not retained. No new full-study execution in this policy edit.
- Limits: accelerated synthetic responses/data and real PsychoPy displays;
  no physical belt or scientific timing qualification.

### Native selection, reconnect, remote control and XDF

- Result/date: `VERIFIED` historical pass, 2026-09-27.
- Scope: `tests/check_native_lsl.py`; select, memory and remote modes, native
  WebView geometry, displayed QR decoding, markers through wrapper Close and
  independently decoded XDF streams with nonempty samples/matching footers.
- Evidence: `.for-ai-local/native-check.log`, ending with `result: passed` for
  all three modes. Exact invocation/options were not retained.
- Log SHA-256: `536e717597652fb2d5782d846a6da6efd8e0b078c550b11c75c6f40a1af82002`.
- Inputs/state: `historical-unbound`; exact Respyra source/runtime/executable
  identities were not retained. No new native execution in this policy edit.
- Limits: Windows/WebView2 with synthetic LSL, `publishedPhone: false` (locally
  routed phone assets). No current hosted-page, physical phone/belt or installed
  release qualification. Ignored logs may be absent in another checkout.

### Native recorder XDF round trip

- Result/date: `VERIFIED` historical pass, 2026-09-27.
- Scope: `tests/check_recording.py`; nonempty raw/marker/late/source-less streams,
  clock offsets, matching sample counts/footers, Unicode output and calibration
  through abort/display-close/finalizing markers.
- Evidence: `.for-ai-local/recording-check.log`, ending with `result: passed`.
  Exact invocation/options were not retained.
- Log SHA-256: `5f25e0fb98b809e14882963153027ec2a9692d030a33d52884b28e1ea37f553a`.
- Inputs/state: `historical-unbound`; exact source/recorder/runtime identities
  were not retained. No new recorder execution in this policy edit.
- Limits: synthetic local LSL and independent PyXDF decoding; no physical belt
  or installed-runtime qualification.
