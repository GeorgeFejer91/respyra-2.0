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
| Automatic discovery, exact reconnect, loss/retry, saved fields and cancelled selection: `src/mpi/lsl_setup.py` (`SourceSetup`) | `tests/test_lsl_setup.py` | reusable; see experiment fields receipt | Setup state transitions, source selection, remembered identity or Start prerequisites change. |
| Marker payload/catalog, renaming, key timing and flip alignment: `src/mpi/event_markers/` | `tests/test_event_markers.py` | unrecorded | Event owner/catalog, timing, phase wrappers or payload consumers change. |
| Short study completion/abort/error, no-data calibration and original CSV modes: `scripts/run_experiment.py`, `src/mpi/validation_study_jenny.py` | `tests/test_experiment_flow.py` | unrecorded | Study flow, calibrated input, marker contract, logging schema or installed `respyra` APIs change. |
| Closed actions, ordered bounded pipe, public snapshots and Stop receipts: `src/mpi/desktop_bridge.py` | `tests/test_desktop_bridge.py` | reusable; see experiment fields receipt | Action validation, sequence/framing/queue limits, projection or cleanup receipts change. |
| Real engine startup/import isolation and marker lifetime through Close: `scripts/run_experiment.py`, desktop bridge | `tests/test_desktop_process.py` | unrecorded | Launcher/imports, inherited stdio, pipe contracts or engine lifetime change. |
| Optional Windows hooks and shutdown: `src/mpi/input_capture.py` | `tests/test_input_capture.py` | unrecorded | Hook registration, filtering, queues, drain/cleanup or marker handoff changes. |
| Recorder readiness, missing/failed/hung child, participant list, partial files and XDF completeness: `src/mpi/recording.py` | `tests/test_recording.py` | reusable; see experiment fields receipt | `NativeRecording`, `inspect_xdf`, child/readiness protocol or XDF validation changes. |
| Native XDF persistence, calibration/cleanup markers, late/source-less streams and Unicode paths: `native/recorder/`, recording owner | `tests/check_recording.py` | reusable for current output contract; see experiment fields receipt | Recorder source/binary/DLLs, supervision or serialized data/marker contract changes. |
| All-channel preview, late markers and calibrated XDF values: `src/mpi/lsl_viewer.py`, `LSLForceSource`, recording owner | `tests/check_control_center.py` | historical-unbound; covered by full-study receipt below | Viewer subscriptions, calibrated output/formula, time bases or recording data change. |
| Complete 48-trial synthetic study: study/calibration/recording owners | `tests/check_control_center.py --full-study` | historical-unbound; see full-study receipt below | Complete-study triggers in `VERIFICATION.md`; panel presentation does not invalidate it. |
| Browser action ordering, timestamps and overload: `web/action-queue.js` | `tests/action-queue.test.mjs` | unrecorded | Queue sequencing, clock capture, dispatch or failure behavior changes. |
| Finite trace geometry and sample-loss gaps: `web/lsl-monitor.js` | `tests/lsl-monitor.test.mjs` | reusable; see recorder preview receipt | Trace computation, sample/time assumptions or monitor rendering changes. |
| Invitation/command/state contracts and mutual BRSP proof: `web/remote-profile.js`, shared BRSP assets | `tests/remote-viewer.test.mjs` | reusable; see experiment fields receipt | Invitation, scopes, validation, proof/state or reliable mutation contracts change. |
| Opening panel, dialogs, actions, fit/recovery and enlarged text: `web/index.html`, `style.css`, controller/desktop/text-fit modules | `pnpm check:ui` plus inspect changed area | reusable; see experiment fields receipt | Relevant DOM/CSS, rendering/status projection, fonts or Pretext inputs change; no downstream rerun for isolated presentation. |
| Companion/Recorder embedding, responsive layouts and remote mutations: `companion/`, remote-host/profile modules | `pnpm check:remote` (Recorder companion configured); live VDO separately | reusable; see experiment fields receipt for shared controls and remote approval receipt for native ownership | Shared phone behavior/assets, embedding or remote transport changes; truly desktop-only selectors/paths leave phone evidence valid. |
| Rust engine paths, closed actions/framing and normal/failed/hung shutdown: `src-tauri/src/main.rs` | Cargo fmt/test/clippy commands in `VERIFICATION.md` | reusable; see experiment fields receipt | Rust supervisor, command/capability/configuration or build/runtime inputs change. |
| Native remote ownership, approval, scopes, sequence, expiry, deduplication and bounded projection: `src-tauri/src/viewer.rs` | Cargo tests (viewer module), fmt/clippy | reusable; see remote approval receipt | Grants/approval, owner/peer/epoch/lease, dispatch, revisions or data visibility changes. |
| Actual WebView/Python/LSL selection/reconnect, Start/Stop/Close, QR and remote round trip | `tests/check_native_lsl.py` after a matching native build | historical-unbound; see native receipt below | Native/pipe/lifecycle/remote contracts or consuming runtime change; UI-sensitive changes need focused WebView evidence rather than automatically this whole harness. |
| Current public phone page pairing and published byte parity | Published mode in `tests/check_native_lsl.py`; deployment/parity readback | see published approval receipt | Deployed companion inputs or endpoint state changes, or current deployment is claimed; local intercepted assets cannot qualify it. |
| Standalone/installed Windows runtime and exact NSIS artifact | `PACKAGING.md` build/import/install/native/hash gates | partial local install; see naming/install receipt | New installer/runtime/artifact bytes or release promotion; ordinary UI source iteration does not require packaging. |
| Windows shortcut icon transparency and circle tint: `assets/icon.svg`, packaging generator, PNG/ICO | Direct SVG icon generation, alpha/color assertions and 48 px preview | reusable; see shortcut icon receipt | SVG, icon generation, generated PNG/ICO or icon tooling changes. A new installer has its own packaging gate. |
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

### Compact live LSL design preview

- Result/date: `VERIFIED`, 2026-09-29, headless Chrome in a separate Playwright context.
- Scope: `web/experiment-hub-preview.html` with live-discovery fixtures: compact outlet labels, raw/Respyra entries first and automatically recorded, a shared bounded viewer with input markers, responsive no-scroll layout, adjustable splitters, and a Remote Viewer dialog that honestly identifies the browser preview as unable to issue a private QR. This is a design preview, not the shipped experiment UI or recorder.
- Checks: `node tests/check_experiment_preview.cjs` and `node tests/check_preview_splitters.cjs` passed. `pnpm check:ui` passed (17 actions, 5 reflow and 2 control-center layouts, no clipping or page errors). `.venv/Scripts/python.exe tests/check_preview_discovery.py` discovered a live synthetic Force (N) outlet in a private LSL session. Inspected `.for-ai-local/remote-viewer-preview-dialog.png` from the headless run.
- Inputs: HEAD `d2d8a349d82d91bb20fa26c645e747fb14c96129`; untracked preview SHA-256 `5c316f0a40e154f07b7d1dbb99f1a719e117b16544e8aa3dff4cefe93888beb8`; preview check SHA-256 `ab622a8c957f6c637540f045633be4efc05a65a1e88b3607b112eb092e35fdb2`; splitter check SHA-256 `4629094eb303c6804ee58a51b8ef76554164cc6e458ca6938aa46358445d7db3`; shared `web/text-fit.js` SHA-256 `fbc1b1d8b1586e0f29ab09e0dc5aae22abea1024875995d10a46c85d43c40951`.
- Discovery check inputs: `scripts/preview_lsl_ui.py` SHA-256 `a6ab0766373bda8dfe68f3dba17cbe0f4582024146447da1266403ebab1009c7`; `tests/check_preview_discovery.py` SHA-256 `92485f763f596b952476d090c797945d4b7e57fffb2065d9361ced7d26313cfb`.
- Limits: synthetic discovered outlets in preview tests; no foreground/native WebView run, physical LSL source, XDF recording, or calibration execution.

### Name-gated Remote Viewer

- Result/date: `VERIFIED`, 2026-09-29. Captured CLI and headless Chrome on Windows.
- Scope: the desktop's small Remote Viewer button creates its private QR; a phone must enter a bounded name before sending an authenticated BRSP introduction. Rust binds that name to the single pending request, and the desktop displays it for local Approve/Reject. No state or Start control is available before approval. The approved phone has setup, LSL monitoring and run controls on one responsive page.
- Checks: `pnpm test:web` (6 pass); `pnpm check:ui` (17 actions, 5 reflow and 2 control-center layouts, no clipping/page errors); `node tests/check_remote_viewer.cjs` with configured Recorder companion (12 layouts, 12 mocked native mutations, opaque iframe); the same test with `RESPYRA_REAL_VDO=1` (public VDO signaling, observed direct route, same 12 mutations); Rust fmt check, 5 viewer unit tests and clippy `-D warnings` passed. OpenCV decoded the QR pixels from `.for-ai-local/remote-viewer-qr.png` to a private-link shape. Inspected headless name, approval, phone, QR and preview dialog screenshots.
- Inputs: base `d2d8a349d82d91bb20fa26c645e747fb14c96129` plus scoped source/test hashes in `.for-ai-local/remote-viewer-inputs.json` (SHA-256 `cc77a8936ccdaf00a95de5e025e5f65ab73dd7eedaa8850c213517f94f203008`).
- Limits: native authorization and real VDO were checked separately; the VDO browser test mocked Rust/Python, and the Rust tests did not run a native WebView. No isolated native GUI, physical phone/camera, new installer, or updated public phone deployment was tested. The public site and installed app still serve the previously published version until separately updated.

### Experiment field memory and recording names

- Result/date: `VERIFIED`, 2026-09-29. Captured CLI and headless Chrome on Windows.
- Scope: automatic local participant/session/custom-variable memory, bounded local and phone edit contracts, compact UI layout, numeric `P002` naming with underscore-separated label/value parts, a participant-list entry after independently verified XDF closure, and preservation of a closed XDF when list append fails.
- Checks: `.venv/Scripts/python.exe -m pytest tests/test_lsl_setup.py tests/test_recording.py tests/test_desktop_bridge.py` (37 pass); `tests/test_desktop_process.py tests/test_experiment_flow.py` (10 pass); `.venv/Scripts/python.exe tests/check_recording.py` (four nonempty, footered XDF streams and matching `P002_Session-001_Age-28_…xdf` list entry); `pnpm test:web` (6 pass); `pnpm check:ui` (17 actions, 5 reflow and 2 control-center layouts, no clipping/errors); configured `pnpm check:remote` (12 layouts, 12 mocked mutations, opaque iframe); Cargo fmt/test (9 pass)/clippy; `pnpm tauri build --debug --no-bundle`; context checker (pass with branch/dirty warnings). The changed desktop area and narrow preview were inspected from headless screenshots.
- Inputs: base `58296ef` plus scoped source/test/lock hashes in `.for-ai-local/experiment-fields-inputs.json` (SHA-256 `090dd206037a4d0265efde3c858d68785c5793ea76673b8e6d40a0952c798098`). Python 3.10.11, Node 24.19.0. The design preview and its checks were pre-existing untracked work and are excluded from this product receipt.
- Limits/state: reusable for the named source inputs. Browser/phone bridge checks mocked the native shell; the real native XDF proof used synthetic LSL, not a physical belt. Actual WebView/focus, full PsychoPy study, installed runtime, physical phone, live VDO and publication were `NOT RUN`; no isolated GUI runner was used. The separate untracked preview changed concurrently and its later check did not run against a live preview feed.

### Windows shortcut icon

- Result/date: `VERIFIED`, 2026-09-28, captured CLI on Windows. The desktop shortcut retains its installed-app target and points to the regenerated ICO.
- Scope/checks: `pnpm tauri icon assets/icon.svg` and a separate 1024 px render from the same SVG; XML assertion that the SVG embeds no image; Pillow assertions for transparent exterior, translucent blue interior, darker ring, 512/1024 px PNGs and 48 px ICO; visual inspection of `.for-ai-local/icon-preview.png` and `icon-hires/1024x1024.png`; Python compile, PowerShell parse and shortcut target/icon readback.
- Inputs: base `2d4a26adf7c3f498ea0f3f31c54d765a1854174d` plus uncommitted SHA-256 `assets/icon.svg` `05e0d17fa1432da6944fdfa6d42f76083f5bea0d1db4155b3d3ea9826c09f4b0`, `scripts/package-windows.ps1` `383c86b4fe96357f0ca5f87088e4bc34afb7f4f5ed43c9240f57892cd4c4802c`, `scripts/package_runtime.py` `38a90af614a50c3b2c10eb2f629c29b644d396744fa61beb69e625552f3217b2`, `icon.png` `4d14508e49b41dd08dd87e8bf33708f4375209b1ab4489588a0e875747e5d6af`, `icon.ico` `8cc96f839c5fe2d7db2983f4c9d5eb8a805b002fb8198c3fa81b65f761d9fea9`. Tauri CLI 2.11.4, Python 3.14.7, pnpm 11.19.0.
- Evidence/limits: `.for-ai-local/icon-check.log`, `shortcut-check.log`, `icon-preview.png`, `icon-hires/1024x1024.png`; direct SVG generation and readback passed. No new installer or installed executable was built, and Explorer's on-screen refresh was not observed.

### Recorder preview and event catalog

- Result/date: `VERIFIED`, 2026-09-28. Headless Chrome 153.0.8010.54 on Windows; captured CLI for the unit check.
- Scope: one shared time axis for paged channel lanes, marker lines crossing the visible plot with distinct event-group colors, no marker lane, per-stream tabs, reachable later streams, searchable/paged 89-entry program catalog generated from the Python marker authority, 320 px no-fit behavior, and unchanged phone rendering with shared CSS/trace code.
- Checks: `node --test tests/lsl-monitor.test.mjs` (1 pass); `pnpm check:ui` (14 actions, 5 reflow layouts, 2 control-center layouts, no clipping/page errors); `pnpm check:remote` with `RECORDER_COMPANION` set to the clean `Remote-LSL-Recorder-respyra-control/companion` checkout (12 layouts, 9 mocked mutations, opaque iframe). The first remote invocation without that required variable stopped before running; the configured invocation passed.
- Inputs: base `11ac8763cf3680e5835fb8b8a12bb6ec5bc41a69` plus scoped source/test/lock and generated-catalog hashes in `.for-ai-local/recorder-preview-inputs.json` (SHA-256 `1699ba0f00bc564f0267ea6b43902ab0da44d906cd3a9383074c1c0dcb74f0db`); Recorder companion commit `d95b1976613e1298ae3f5ead6726087b80703cea`, clean worktree. Node 24.19.0, pnpm 11.19.0.
- Evidence: `.for-ai-local/recorder-preview-unit.log`, `recorder-preview-ui.log`, `recorder-preview-remote.log`, and headless screenshots `html-setup.png` and `html-markers.png`; the changed areas were inspected.
- Limits/state: `reusable` for the named inputs. Browser/native bridge and remote transport were mocked; the actual WebView, physical belt, XDF persistence, installed runtime, and live VDO were not rerun for this presentation change.

### Respyra 2.0 product name

- Result/date: `VERIFIED`, 2026-09-28, for the local debug build and browser title.
- Scope: Tauri product/window name, HTML title, installer overlay labels, package-manifest source and retained legacy data path. No new release artifact was promoted.
- Checks: `pnpm check:ui` passed its headless layout/action suite with the exact HTML title assertion; `.venv/Scripts/python.exe -m pytest tests/test_recording.py` passed 10 tests; `pnpm tauri build --debug --no-bundle` compiled the renamed app. Parsed the Tauri/NSIS JSON labels and PowerShell/Python packaging script syntax. A user-requested visible review launch exposed a responsive window titled `Respyra 2.0 — Experiment control` through `EnumWindows/GetWindowText`; this was not an isolated GUI qualification run.
- Inputs: base `d557aac0c7c9a5daa6579464f4b48ef261fc97d0`, scoped source/config/test hashes and debug executable hash in `.for-ai-local/product-name-inputs.json` (SHA-256 `4a7b741559e18394a1438897fec755ca16fed4aa887aa35fcc73f623fa824e80`). Node 24.19.0, Python 3.10.11, Cargo 1.96.0.
- Evidence: captured command results in this task and the ignored input/window manifest above.
- Limits/state: `reusable` for the local title and named checks. The 495 MB `Respira_0.3.0_x64-setup.exe` was an older artifact; the later local naming/install receipt below covers a new installer and local shortcuts, while release qualification remains incomplete. The `%LOCALAPPDATA%/Respira` data path deliberately remains unchanged.

### Local Windows naming and installation

- Result/date: `VERIFIED` for local installed metadata, shortcut targets and bundled-engine check, 2026-09-29; release qualification remains `PARTIAL`.
- Inputs: commit `2113ee823d49a4c562326735ec9fb8630c6eb8fd`; exact NSIS artifact `dist/Respyra 2.0_0.3.0_x64-setup.exe` SHA-256 `e9f6a9e9be9557e5ec15116cb04c246f846a6cc4a670ff8933eab2a49941b76b`; installed executable SHA-256 `2d5feaac015339d2a4b27cc7553689b5e40a497d82cb31881ea357ae4c68ee8f`; installed `engine/manifest.json` SHA-256 `5395548b2330856ecb2692b739d9d4188c13e76979f48c52d81798684d958f89`. Manifest `product` is `Respyra 2.0`, version `0.3.0`, with `source_dirty: true` because unrelated untracked preview/test work existed during staging. The preview page was held outside `web/` during the frontend build and later concurrently changed; its newer copy was preserved.
- Evidence: captured `scripts/package-windows.ps1` built the NSIS artifact and passed isolated embedded-Python imports, app-local MSVC loading and a native XDF round trip (`.for-ai-local/name-package-main.log`). The exact installer ran silently with exit code 0. Installed `engine/scripts/check_packaged_engine.py` run by installed Python `-I -B -X utf8` passed the same native round trip. The installed manifest hash matched staging. Windows readback found only `Respyra 2.0` 0.3.0 in per-user uninstall entries; desktop, Start menu and taskbar `Respyra 2.0.lnk` targets all resolve to its installed executable. The old 0.2.0 `Respira` uninstall completed with exit code 0; its install folder, registry entry and shortcuts disappeared while `%LOCALAPPDATA%/Respira` remained.
- Limits/state: reusable only for these exact local artifact bytes and observed machine state. The installer manifest is dirty and must not be promoted. Installer wizard, installed WebView/PsychoPy, physical devices, hosted QR and visible Explorer/taskbar refresh were `NOT RUN` because no isolated GUI runner was used. Installation and checks used hidden/captured CLI processes.

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
