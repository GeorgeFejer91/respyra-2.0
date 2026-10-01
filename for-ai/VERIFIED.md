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
| `tests/check_native_lsl.py` (every mode), its `check_native_ui.cjs` helper, and installed-runtime variants | Requires isolated GUI execution. `tests/run_private_mock.py` provides a private Win32 desktop and private LSL SessionID for the installed Mini mock; direct invocation remains intrusive. Headless phone Chrome does not hide the native target or PsychoPy windows. |
| `tests/check_control_center.py --full-study` | Requires isolated GUI execution: launches actual PsychoPy displays even though responses are simulated. The same private-desktop runner supports `full`. |
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
| Raw Force metadata/units, finite samples, duplicate identities and saved selection: `src/mpi/lsl_force.py` | `tests/test_lsl_force.py` | verified for current inputs; see hub/recorder receipt | Force validation, source identity/storage, freshness or producer metadata contract changes. |
| Polar PCA/signed Phan contracts, validity, direction, calibration and native XDF: `src/mpi/lsl_polar.py`, `polar_calibration.py` | `tests/test_lsl_polar.py`, `tests/check_polar_lsl.py`, `tests/check_polar_recording.py` | verified for unchanged synthetic signal/recording inputs; UI has newer selector receipt | Producer metadata, companion timing, source selection, study calibration, recorder or derived formula changes. |
| Automatic discovery, exact reconnect, loss/retry, saved fields and cancelled selection: `src/mpi/lsl_setup.py` (`SourceSetup`) | `tests/test_lsl_setup.py` | verified for participant parity and recorded-number projection; see 2026-10-01 receipt | Setup state transitions, source selection, remembered identity or Start prerequisites change. |
| Marker payload/catalog, renaming, key timing and flip alignment: `src/mpi/event_markers/` | `tests/test_event_markers.py` | verified for current inputs; see hub/recorder and marker inventory receipts | Event owner/catalog, timing, phase wrappers or payload consumers change. |
| Short study completion/abort/error, no-data calibration and original CSV modes: `scripts/run_experiment.py`, `src/mpi/validation_study_jenny.py` | `tests/test_experiment_flow.py` | verified for participant parity; private-desktop full synthetic study passed; see 2026-10-01 receipt | Study flow, calibrated input, marker contract, logging schema or installed `respyra` APIs change. |
| Closed actions, ordered bounded pipe, public snapshots and Stop receipts: `src/mpi/desktop_bridge.py` | `tests/test_desktop_bridge.py` | verified for current inputs; see hub/recorder receipt | Action validation, sequence/framing/queue limits, projection or cleanup receipts change. |
| Real engine startup/import isolation and marker lifetime through Close: `scripts/run_experiment.py`, desktop bridge | `tests/test_desktop_process.py` | verified for current focused inputs; see hub/recorder receipt | Launcher/imports, inherited stdio, pipe contracts or engine lifetime change. |
| Optional Windows hooks and shutdown: `src/mpi/input_capture.py` | `tests/test_input_capture.py` | unrecorded | Hook registration, filtering, queues, drain/cleanup or marker handoff changes. |
| Recorder readiness, missing/failed/hung child, participant list, partial files and XDF completeness: `src/mpi/recording.py` | `tests/test_recording.py` | verified for history reader and unchanged writer; see 2026-10-01 receipt | `NativeRecording`, `inspect_xdf`, child/readiness protocol or XDF validation changes. |
| Native XDF persistence, calibration/cleanup markers, late/source-less streams and Unicode paths: `native/recorder/`, recording owner | `tests/check_recording.py` | verified for current inputs; see hub/recorder receipt | Recorder source/binary/DLLs, supervision or serialized data/marker contract changes. |
| Offline XDF-to-CSV export and tutorial: `scripts/xdf_to_csv.py`, `notebooks/xdf_to_csv_tutorial.ipynb` | `tests/test_xdf_to_csv.py`, headless notebook execution | verified for current inputs; see offline export receipt | Converter/notebook logic, CSV columns or PyXDF version changes. |
| All-channel preview, late markers and calibrated XDF values: `src/mpi/lsl_viewer.py`, `LSLForceSource`, recording owner | `tests/check_control_center.py` | verified for current inputs; see hub/recorder receipt | Viewer subscriptions, calibrated output/formula, time bases or recording data change. |
| Complete 48-trial study: study/calibration/recording owners | Private-desktop `tests/check_control_center.py --full-study`; Mini mock route remains separate | verified for current synthetic input and even participant; Mini mock evidence predates parity change | Study, inlet buffering, calibration, marker or recorder inputs change. |
| Browser action ordering, timestamps and overload: `web/action-queue.js` | `tests/action-queue.test.mjs` | unrecorded | Queue sequencing, clock capture, dispatch or failure behavior changes. |
| Finite trace geometry and sample-loss gaps: `web/lsl-monitor.js` | `tests/lsl-monitor.test.mjs` | reusable; see recorder preview receipt | Trace computation, sample/time assumptions or monitor rendering changes. |
| Invitation/command/state contracts and mutual BRSP proof: `web/remote-profile.js`, shared BRSP assets | `tests/remote-viewer.test.mjs` | verified for recorded-number setup projection; see 2026-10-01 receipt | Invitation, scopes, validation, proof/state or reliable mutation contracts change. |
| Opening panel, dialogs, actions, fit/recovery and enlarged text: `web/index.html`, `experiment-hub.css`, `experiment-hub.js` | `pnpm check:ui` plus inspect changed area | verified for participant dropdown and red recorded choice; see 2026-10-01 receipt | Relevant DOM/CSS, rendering/status projection, fonts or Pretext inputs change; no downstream rerun for isolated presentation. |
| Companion/Recorder embedding, responsive layouts and remote mutations: `companion/`, remote-host/profile modules | `pnpm check:remote` (Recorder companion configured); live VDO separately | verified for locally routed phone picker; published site remains older; see 2026-10-01 receipt | Shared phone behavior/assets, embedding or remote transport changes; truly desktop-only selectors/paths leave phone evidence valid. |
| Project landing, installer/Mini links, logo and legacy QR routing: `companion/index.html`, `remote.html`, `site.*`, publication inputs | `node tests/check_project_site.cjs`, published asset parity and private-desktop published phone check | verified for current source and deployment; see project site receipt | Site/route/assets, source attribution, linked release assets or published endpoint changes. |
| Rust engine paths, closed actions/framing and normal/failed/hung shutdown: `src-tauri/src/main.rs` | Cargo fmt/test/clippy commands in `VERIFICATION.md` | 0.3.4 fmt, test and clippy passed with portable MSVC; see 2026-10-01 receipt | Rust supervisor, command/capability/configuration or build/runtime inputs change. |
| Native remote ownership, approval, scopes, sequence, expiry, deduplication and bounded projection: `src-tauri/src/viewer.rs` | Cargo tests (viewer module), fmt/clippy | verified for current inputs; see Mini pipeline receipt | Grants/approval, owner/peer/epoch/lease, dispatch, revisions or data visibility change. |
| Actual WebView/Python/LSL selection/reconnect, Start/Stop/Close, QR and remote round trip | `tests/run_private_mock.py` after a matching native build | verified for installed Mini mock, early Stop and complete phone controlled study; see Mini pipeline receipt | Native/pipe/lifecycle/remote contracts or consuming runtime change. |
| Current public phone page pairing and published byte parity | Published mode in `tests/run_private_mock.py`; deployment/parity readback | current published route, native early-Stop run and ten-asset byte parity verified; see project site receipt | Deployed companion inputs or endpoint state changes, or current deployment is claimed; local intercepted assets cannot qualify it. |
| Standalone/installed Windows runtime and exact NSIS artifact | `PACKAGING.md` build/import/install/native/hash gates | public 0.3.2 verified; see release receipt | New installer/runtime/artifact bytes or release promotion; ordinary UI source iteration does not require packaging. |
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

### Participant parity and recorded-number picker

- Result/date: `VERIFIED`, 2026-10-01, source commit `4088bf92b933144ba0d37304ce99a831c10f4e42`.
  Python 3.10.21, Node 24.18.0, pnpm 11.19.0, Playwright 1.62.1 and headless Chrome.
- Checks: `.venv/Scripts/python.exe -m pytest tests/test_lsl_setup.py tests/test_recording.py tests/test_experiment_flow.py tests/test_desktop_bridge.py tests/test_desktop_process.py -q` (55 passed); `pnpm check:ui` (8 layouts, 15 actions, no page errors, red choice inspected at 390 px); configured `pnpm check:remote` (12 phone layouts, 11 mocked mutations, 390 px setup image inspected); `pnpm test:web` (6 passed); `node tests/check_project_site.cjs` (passed); `cargo fmt --manifest-path src-tauri/Cargo.toml --check` (passed). Captured CLI and headless browser runs left the active desktop untouched.
- Full study: the ignored `.for-ai-local/run_private_synthetic.py` launcher created a private Win32 desktop and ran `tests/check_control_center.py --full-study` there. An even participant (`2`) completed all 48 trials; PyXDF independently decoded the closed XDF with 803 raw, 771 calibrated, 1,467 marker and 10 late-marker samples. Evidence: `.for-ai-local/RespyraSynthetic44a3e221a317425ba2ecbde2b6869e12/full.log` and `.for-ai-local/control-center-ff2ed3377fb04fae9ccf9ab98f5ee8d7/`.
- Rust checks: the first `cargo test --locked` attempt lacked `cl.exe`. Activating the existing ignored `.for-ai-local/msvc/activate.ps1` toolchain (MSVC 14.44.35207, SDK 10.0.19041.0) gave `cargo test --locked` 10 passed and `cargo clippy --locked --all-targets -- -D warnings` passed. The first `pnpm package:windows` attempt met an old NMake CMake cache while no generator was selected; the remaining package attempt will select NMake explicitly.
- Limits: synthetic source and simulated responses, not a physical belt or scientific timing qualification. Installed WebView/installer and published phone selector were not tested at this point.

### Two-segment hub, early derived stream and recording choices

- Result/date: `VERIFIED` for the named headless/CLI surfaces, 2026-09-29.
  Base commit `74f234d660a81dca06b94352a04dbb271468ccce` plus changed source,
  tests, locks, rebuilt recorder and debug app hashes in ignored
  `.for-ai-local/verification-inputs-20260929.json` (SHA-256
  `3387e23b6ccde5fd07c4c6603d4f03d9dd232316651572d4f85aca0896945bb0`).
- UI: `pnpm check:ui` passed 12 ordered actions, Start/Stop, Record/View choices,
  Settings, four layouts and zero browser errors/clipped text. Preview discovery,
  splitter and live LSL checks passed. `pnpm check:remote` passed 12 phone layouts
  and 12 mocked mutations; `pnpm test:web` passed 6 tests.
- Backend: 62 focused Python tests passed. `tests/check_control_center.py`
  independently decoded an XDF with raw Force, markers, early NaN and later
  finite Respyra samples, and a late stream; it waited for the native recorder's
  first-finite receipt before proceeding. `tests/check_recording.py`
  independently decoded a five-stream XDF: mandatory raw/derived/markers survived
  submitted exclusions, an unchecked auxiliary UID was absent, and late streams
  joined. Both checks ran in private LSL sessions through captured CLI.
- Build: `pnpm prepare:recorder`, Cargo fmt check, 9 Rust tests, clippy with
  warnings denied, and `pnpm tauri build --debug --no-bundle` passed. The context
  checker passed with expected branch/dirty warnings; `git diff --check` passed.
- Limits: browser tests mocked Tauri; CLI XDF checks used synthetic LSL. The
  current native WebView/PsychoPy full study and installed-runtime checks were
  `NOT RUN: isolated GUI desktop unavailable`. Physical belt, phone camera,
  scientific timing and a new installer remain unverified. The old installed
  app does not contain these source changes.

### Compact live LSL design preview

- Result/date: `VERIFIED`, 2026-09-29, headless Chrome in a separate Playwright context.
- Scope: `web/experiment-hub-preview.html` with live-discovery fixtures: compact outlet labels, raw/Respyra entries first and automatically recorded, a shared bounded viewer with input markers, responsive no-scroll layout, adjustable splitters, and a Remote Viewer dialog that honestly identifies the browser preview as unable to issue a private QR. This is a design preview, not the shipped experiment UI or recorder.
- Checks: `node tests/check_experiment_preview.cjs` and `node tests/check_preview_splitters.cjs` passed. `pnpm check:ui` passed (17 actions, 5 reflow and 2 control-center layouts, no clipping or page errors). `.venv/Scripts/python.exe tests/check_preview_discovery.py` discovered a live synthetic Force (N) outlet in a private LSL session. Inspected `.for-ai-local/remote-viewer-preview-dialog.png` from the headless run.
- Inputs: HEAD `d2d8a349d82d91bb20fa26c645e747fb14c96129`; untracked preview SHA-256 `5c316f0a40e154f07b7d1dbb99f1a719e117b16544e8aa3dff4cefe93888beb8`; preview check SHA-256 `ab622a8c957f6c637540f045633be4efc05a65a1e88b3607b112eb092e35fdb2`; splitter check SHA-256 `4629094eb303c6804ee58a51b8ef76554164cc6e458ca6938aa46358445d7db3`; shared `web/text-fit.js` SHA-256 `fbc1b1d8b1586e0f29ab09e0dc5aae22abea1024875995d10a46c85d43c40951`.
- Discovery check inputs: `scripts/preview_lsl_ui.py` SHA-256 `a6ab0766373bda8dfe68f3dba17cbe0f4582024146447da1266403ebab1009c7`; `tests/check_preview_discovery.py` SHA-256 `92485f763f596b952476d090c797945d4b7e57fffb2065d9361ced7d26313cfb`.
- Limits/state: superseded by the current hub/recorder receipt above. Its
  synthetic preview evidence remains historical and does not qualify the shipped
  page, physical LSL source or installed app.

### Name-gated Remote Viewer

- Result/date: `VERIFIED`, 2026-09-29. Captured CLI and headless Chrome on Windows.
- Scope: the desktop's small Remote Viewer button creates its private QR; a phone must enter a bounded name before sending an authenticated BRSP introduction. Rust binds that name to the single pending request, and the desktop displays it for local Approve/Reject. No state or Start control is available before approval. The approved phone has setup, LSL monitoring and run controls on one responsive page.
- Checks: `pnpm test:web` (6 pass); `pnpm check:ui` (17 actions, 5 reflow and 2 control-center layouts, no clipping/page errors); `node tests/check_remote_viewer.cjs` with configured Recorder companion (12 layouts, 12 mocked native mutations, opaque iframe); the same test with `RESPYRA_REAL_VDO=1` (public VDO signaling, observed direct route, same 12 mutations); Rust fmt check, 5 viewer unit tests and clippy `-D warnings` passed. OpenCV decoded the QR pixels from `.for-ai-local/remote-viewer-qr.png` to a private-link shape. Inspected headless name, approval, phone, QR and preview dialog screenshots.
- Inputs: base `d2d8a349d82d91bb20fa26c645e747fb14c96129` plus scoped source/test hashes in `.for-ai-local/remote-viewer-inputs.json` (SHA-256 `cc77a8936ccdaf00a95de5e025e5f65ab73dd7eedaa8850c213517f94f203008`).
- Publication: source `3450bf011cbc4788e768650f81ecff409d98c766` was pushed to `codex/recorder-panel`; static phone assets and `source.json` were pushed as `gh-pages` commit `390d9986ea6ae2544077dff1ed773265c5f2f972`. GitHub Pages reported `built` for that commit on 2026-09-29, and eight changed public assets matched its Git blobs byte for byte over HTTPS.
- Limits: native authorization and real VDO were checked separately; the VDO browser test mocked Rust/Python, and the Rust tests did not run a native WebView. No isolated native GUI, physical phone/camera, or new installer was tested. The installed app still serves its previous bundled version; live pairing with this new public revision was not run.

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

### Clean Windows 0.3.0 release candidate

- Result/date: `PARTIAL`, 2026-09-30. A fresh installer was built but has not passed the installed-runtime and public-distribution gates.
- Inputs: committed source `cae1d1e9b9fa62e3f022be341cff9dba63b30856`, already pushed to `origin/codex/recorder-panel`; `dist/runtime-manifest.json` records `source_dirty: false`, version `0.3.0`, Windows x64. Exact `dist/Respyra 2.0_0.3.0_x64-setup.exe` is 495,599,431 bytes with SHA-256 `6594f2091089732f0df204b1927e5be0bac9c41038a1977e4e85b3bca5135c77`, matching `dist/SHA256SUMS.txt`. This replaces the older dirty local candidate above; it does not inherit that candidate's installed evidence.
- Evidence: captured `pwsh -NoProfile -File scripts/package-windows.ps1` passed the embedded Python 3.10.11 imports, app-local MSVC check, native recorder build and synthetic XDF round trip with raw, derived and marker streams; Tauri completed the release NSIS bundle. Logs: ignored `.for-ai-local/release-build-20260930.log` and `.for-ai-local/release-engine-probe-20260930.log`. The packaging probe was corrected for the current derived-stream requirement before this clean build. The project's 2026-09-30 private-desktop Vernier mock and full-study receipt covers unchanged product inputs, not these installer bytes.
- Limits: the exact installer has not been installed or exercised as a packaged WebView/PsychoPy app. Public distribution review remains open: packaged PyQt6 is GPL-3.0-only; the `ffpyplayer` wheel metadata says its Windows wheels are GPL due to FFmpeg options; and bundled `imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe -L` reports GPLv3. The repo has no license for its own code, and corresponding source/notice availability for bundled native libraries has not been completed. Do not publish this candidate as a public release under `PACKAGING.md`.

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

### Polar PCA and signed Phan study inputs

- Result/date: `VERIFIED` for synthetic software paths, 2026-09-29.
- Inputs: Respyra base `74f234d660a81dca06b94352a04dbb271468ccce`
  plus changed/untracked product and test hashes in ignored
  `.for-ai-local/polar-contract-inputs.json` (SHA-256
  `8d04c16050fd710a74c8cd12abeecbcdbfdc563a0389dc6fc149faaa769440dc`).
  Polar Mini base `440ca293e4051b840a310583652b0deed332fac4`
  plus `.for-ai-local/polar-respyra-contract-inputs.json` (SHA-256
  `75f4b07aeba31606d486a4ac7f7971718c99ffd5b83e2dd0c92e395db4f60b02`).
- Checks: Polar `cargo fmt --all -- --check`, `cargo test -p polar-h10-output --locked`
  (46 pass), `cargo clippy -p polar-h10-output --all-targets --locked -- -D warnings`,
  `npm run validate:docs`; real metric engine and bundled liblsl producer with
  official pylsl receiver in `separate`, `single`, `both` modes passed. The
  `separate` producer also passed Respyra `tests/check_polar_lsl.py` for both
  exact contracts. Respyra focused pytest including input, setup, study, marker,
  desktop bridge/process and recording tests passed after the final study-text
  correction (68 tests overall; invalidated files rerun); `pnpm check:ui`
  passed source switching, direction gate and fit checks; `pnpm test:web` passed
  6. Rust fmt/test (9 pass)/clippy and `pnpm tauri build --debug --no-bundle`
  passed (debug executable SHA-256
  `c061c70b6b68abb73246cffd1b4267a9932ca76925957bf7e44b9912a71a181b`). `pnpm prepare:recorder`,
  `tests/check_recording.py`, `tests/check_control_center.py` and
  `tests/check_polar_recording.py` passed. The last check independently decoded
  XDF for each Polar contract and confirmed raw/companion/marker/derived samples,
  missing values before calibration, finite values afterward and signed formula.
- Evidence: captured command results, Polar `.for-ai-local/adr-receiver-final.out`,
  `adr-respyra-single.json`, `adr-respyra-both.json`, and Respyra ignored
  `.for-ai-local/polar-recording-0b8898ca894d464f9525ce6a57e3d797/` XDFs.
- Limits: headless browser and synthetic LSL/XDF on Windows. Native WebView,
  real PsychoPy display, full 48-trial run, physical Polar/Vernier paired data,
  respiratory agreement and packaged installer behavior were not run for these
  inputs. An isolated GUI runner is unavailable under the standing background
  verification rule.

### Separate Vernier and Polar source dropdowns

- Result/date: `VERIFIED` for headless browser behavior and layout, 2026-09-30.
- Inputs: base `74f234d660a81dca06b94352a04dbb271468ccce` plus changed
  frontend/test hashes in ignored `.for-ai-local/dual-input-ui-inputs.json`
  (SHA-256 `aceee33081a4a138e844c00f3b3e54410d1b2e7d7f7c481a63f9f51c36c950af`).
- Checks: `pnpm check:ui` passed separate device lists, one active dropdown,
  Vernier-to-Polar switching, Polar direction gate, remembered-source projection,
  compact and enlarged-text fit; `node tests/check_experiment_preview.cjs`
  passed automatic unique Vernier selection, later source choice and loss;
  `pnpm test:web` passed 6 and `node --check tests/check_native_ui.cjs` passed.
- Evidence: captured command output and inspected headless screenshots
  `.for-ai-local/polar-hub-820.png`, `polar-hub-390.png`, `hub-390.png`.
- Limits: Chromium mock/native-bridge and browser preview. Actual WebView2 and
  PsychoPy windows were `NOT RUN: isolated test desktop unavailable`; the
  selector change did not alter Python, Rust or recording contracts.

### Marker inventory before branch integration

- Result/date: `VERIFIED` for the headless browser and marker catalog checks,
  2026-09-30. Base commit `a90bfea90f8191468f4fb45a752b5246db38fa7c`
  plus scoped source, generated catalog, test, font and lock hashes in ignored
  `.for-ai-local/marker-inventory-inputs-20260930.json` (SHA-256
  `24c6ec5534c3e7fe45e116888586bb04ad9851b2df284b312a875cf280893ccc`).
- Checks: `pnpm check:ui` passed 8 main layouts, 12 ordered actions, setup and
  running-state popup access, all 89 active catalog entries in source order,
  search/no-match/Close, 390 px dialog bounds and 320×480 enlarged-text dialog
  bounds without horizontal overflow or clipped labels, with zero browser
  errors. Inspected `.for-ai-local/marker-inventory-390.png` and
  `marker-inventory-320-large.png`. `tests/test_event_markers.py` passed 8 tests;
  `node --check web/experiment-hub.js` and `git diff --check` passed.
- Scope: the popup uses the generated browser catalog from the Python marker
  catalog; the retired `run.recorder_connected` entry is inactive and excluded
  from both browser inventories. No marker publication or study timing changed.
- Limits: this receipt precedes integration with the two Polar input contracts
  and the dual source selector. Chrome was headless and Tauri IPC was mocked;
  native WebView, full study, installed runtime and physical belt were not run.

### Integrated breathing selectors and marker inventory

- Result/date: `VERIFIED` for the combined headless browser and catalog paths,
  2026-09-30. Base `8c2884cf7fe8173cd8fd8f9f8f0c9cc57705890c` plus
  source, generated catalog, test, local font, Pretext and lock hashes in ignored
  `.for-ai-local/combined-input-ui-inputs.json` (SHA-256
  `a186044a259a1ed40964a8650e340494a54f54156549ae0615170fe57c23bc4a`).
- Checks: `pnpm check:ui` passed eight layouts, 15 ordered actions, one Start and
  Stop, separate Vernier/Polar selection, Polar direction, all 90 active marker
  types, search/Close, compact and enlarged-text dialog bounds, and zero page
  errors. `pnpm test:web` passed six; `tests/test_event_markers.py` passed eight;
  `node tests/check_experiment_preview.cjs` and `node --check web/experiment-hub.js`
  passed. `for-ai/scripts/check-context.ps1` and `git diff --check` passed.
- Evidence: captured CLI results and inspected headless screenshots
  `.for-ai-local/marker-inventory-390.png` and
  `marker-inventory-320-large.png`.
- Limits: Chromium with mocked Tauri IPC and a browser preview. The merge changed
  only the marker catalog, generated browser catalog and opening panel relative
  to the validated Polar input commit. Backend, recorder and Rust evidence from
  the Polar contract receipt remains reusable for unchanged inputs. Native
  WebView2/PsychoPy, physical sensors, full study and installer remain untested
  for this revision because no isolated GUI runner was available.

### Vernier Mini mock XDF and phone controlled full study

- Result/date: `VERIFIED`, 2026-09-30, on base commit
  `4c176e4d356566a4f1551551b81b12e87c092552` plus the uncommitted
  source/test inputs and exact runtime/XDF hashes in ignored
  `.for-ai-local/vernier-mini-mock-inputs-20260930.json` (SHA-256
  `c19dc6d193192c9cb5a6d55a9d28df049ca539b9cf64bb5414bf3f52fc2537c7`).
  The manifest also binds the mock generator and breathing-algorithm source at
  Polar Mini Stream commit `a236479d4c8e2a07ed7b8424215b4364f6c8d4e9`.
  Installed Vernier Stream Mini 0.6.3 ran `--mock`; Respyra 0.3.0 was rebuilt
  as the debug native app. The runner used a private Win32 desktop and private
  LSL SessionID without switching the user's input desktop.
- Direct full-study checks: three private-desktop runs completed 48 trials
  each with actual PsychoPy windows, accelerated timings and simulated
  responses; the last used checked-in `tests/run_private_mock.py full`.
  Independent `scripts/audit_mock_xdf.py` accepted XDFs in ignored
  `control-center-160184e796c4499ca72eda5c95b5d293/` (800 raw rows) and
  `control-center-e87d2ec0dd4149f4bc6eafbc314147d3/` (1,120 raw rows),
  and `control-center-ffa5a300df11435b847c63e635b6a43a/` (970 raw rows).
  The pre-fix run failed the audit with 289 raw rows missing from the derived
  stream; a 60-second inlet buffer repaired the PsychoPy startup gap.
- Native/phone checks: a local Start/Stop and a phone-controlled early Stop
  passed with saved XDFs. Three `remote-full` runs completed all 48 trials:
  one locally routed phone and one public hosted phone through the scratch
  isolated runner, then one locally routed phone through checked-in
  `tests/run_private_mock.py`. Their independently decoded XDFs are under
  ignored `native-recordings-81e8346386d34dd4813dfe9defbba414/` (791 raw),
  `native-recordings-34fd4b9b377e42e7a973aced2ecc9901/` (751 raw), and
  `native-recordings-ef59238009ff4e17bd909362ce91fca4/` (751 raw).
  A fourth full XDF under `native-recordings-538e98eda17c4719b0a7405759060647/`
  independently passed the same audit (741 raw); its live-subscriber harness
  assertion joined after setup markers and was corrected before the final pass.
  Each full native XDF had 1,468 recorded markers and eight completed trials
  per condition. Raw Mini sequence was contiguous, Force matched the mock sine
  formula exactly, raw Force copy retained values/timestamps, producer drop
  diagnostics were zero, the Mini's 0–1 breathing stream and sparse combined
  stream matched an independent replay sample for sample, Respyra derived values
  matched calibration and sample times, and all required stream footers matched.
  The expanded audit passed all seven retained full-study XDFs.
- Focused gates: 43 Python tests, six web tests, `pnpm check:ui` (eight layouts,
  15 actions), `pnpm check:remote` with real public VDO (direct route, 12
  layouts/mutations and mocked native backend), Rust tests (10), Rust clippy,
  native debug build, private WebView fit and QR decode all passed. The public
  phone page also paired and controlled a complete native run. Captured logs,
  screenshots and XDFs remain in ignored `.for-ai-local/`.
- Limits: the XDF reconstructs trial order, condition/target parameters,
  phase and response markers, calibration and breathing samples. It does not
  contain exact rendered pixels or frame flip times, and setup markers sent
  before Start cannot be in the recording. The Mini's optional signal-status
  stream may have zero rows when no status change occurs. Phone setup/monitor
  can scroll vertically with the Mini's 11 channels while retaining 390 px
  width fit. Tests used mock force, simulated responses, shortened phase times,
  headless Chrome and private-desktop WebView/PsychoPy. A physical belt/phone,
  full-duration participant timing, installed Respyra package, and public asset
  byte parity remain unverified.

### Polar Mini mock through remote study and XDF

- Result/date: `VERIFIED`, 2026-09-30, on the Tower PC. Final rebuilt Polar
  Mini 0.6.3 and Respyra 0.3.0 completed both 48-trial contracts, a 120-second
  PCA study, repeated studies, polarity inversion, abort, source loss/restart,
  and a final Vernier Mini regression. Fourteen complete Polar XDFs, one abort,
  and one source-loss XDF passed independent recorded-sample/marker audits.
- Exact commands, commits, all XDF paths/counts, defects and limits:
  [`POLAR-MOCK-VERIFIED.md`](./POLAR-MOCK-VERIFIED.md).

### Tower PC Windows installer candidate

- Result/date: `VERIFIED` for the exact installed mock runtime, `BLOCKED` for public release, 2026-09-30. A clean 0.3.0 installer from commit `617621f` passed deep-path manifest parity, embedded engine/XDF, installed Polar PCA and signed Phan abort/XDF, hosted QR, LSL Data viewer, Vernier/CSV regression, and native select/memory/remote checks. Public promotion remains blocked by corresponding-source review for GPL FFmpeg native libraries in bundled wheels.
- Exact installer hash, commands, XDF paths/counts, fixes, and limits: [`WINDOWS-INSTALLER-TOWER-2026-09-30.md`](./WINDOWS-INSTALLER-TOWER-2026-09-30.md).

### Windows 0.3.1 standalone installer with trimmed media and notebook runtime

- Result/date: `VERIFIED` for exact installed synthetic Windows runtime,
  `BLOCKED` for public release, 2026-09-30. The clean 0.3.1 installer from
  `b0d43ac` passed installed manifest parity, embedded XDF, private-desktop
  select/memory/remote, hosted QR and CSV on/off. The remaining public gate is
  corresponding-source and notice review for retained copyleft components.
- Exact hashes, commands, observations and limits:
  [`WINDOWS-INSTALLER-0.3.1-2026-09-30.md`](./WINDOWS-INSTALLER-0.3.1-2026-09-30.md).

### Windows 0.3.2 public installer and source companion

- Result/date: `VERIFIED` for exact installed synthetic runtime, source asset
  integrity and public GitHub Release, 2026-09-30. The clean 0.3.2 installer
  from `98c89eb` has 18,433 manifest-matched engine files, passed installed
  native LSL/XDF/hosted-QR/CSV checks, and is 113,152,255 bytes. The 696 MB
  companion ZIP contains pinned Python, Rust and native source with verified
  checksums. The public release asset digests match local files.
- Exact commands, hashes, source review and limits:
  [`WINDOWS-INSTALLER-0.3.2-2026-09-30.md`](./WINDOWS-INSTALLER-0.3.2-2026-09-30.md).
  Silent uninstall, clean-machine WebView2 download, physical hardware,
  full-duration timing and signing remain unverified.

### Project website, live phone route and release links

- Result/date: `VERIFIED`, 2026-09-30. Source commit
  `7d0c2b5cf7dbaa96ecbc30f00966ff9986b0dcc5` was pushed to `main`;
  Pages commit `3bc62fc56d8c40862dfc87278323aab346296afe` was reported
  `built`. Ten public HTML, CSS, JS, logo and attribution assets matched that
  commit's Git blobs byte for byte, and published `source.json` named the
  source commit. The GitHub repository homepage and 0.3.2 release notes now
  link the site, both Stream Mini installers and the original Micah Allen work.
  Existing release asset digests were unchanged.
- Checks: `pnpm test:web` (6 pass), `node tests/check_project_site.cjs`
  (project links, logo, 320–1440 px fit, enlarged text and private-link
  redirect), configured `pnpm check:remote` (12 layouts and 12 mocked
  mutations), `pnpm check:ui` (8 layouts, 15 actions, no page errors),
  `python .for-ai-local/check_published_site.py` (10 public assets matched).
  Headless site screenshots at 320 and 960 px were inspected.
- Live route: `tests/run_private_mock.py remote --published-phone` used the
  installed 0.3.2 executable, Vernier Mini mock outlet and a private Win32
  desktop. The QR decoded to the public root invitation; the phone browser
  reached `/remote.html`, requested access and completed Start/Stop/Close.
  The independently checked XDF had four nonempty streams with matching
  footers and 27 ordered markers; Chrome reported zero page errors. The
  QR-check test source had SHA-256
  `23f2c51a0a5fa85e8b9a0b4ea133558eb30eb523b5acc63d1c3f5beb0b82baed`.
  Captured log: `.for-ai-local/RespyraProbeb81a10c7fc62414398a3afc60b828ddc/remote.log`.
- Limits: local desktop plus headless Chrome and synthetic breathing, with
  early Stop. A physical phone or belt and full-duration scientific timing
  were not checked. The release EXE itself was not rebuilt for this site edit.

### Windows 0.3.3 full-rate ECG preview and public installer

- Result/date: `VERIFIED`, 2026-10-01. Clean commit `4513b56` shipped as
  [v0.3.3](https://github.com/GeorgeFejer91/respyra-2.0/releases/tag/v0.3.3).
  The exact installed NSIS artifact matched all 18,433 engine files and passed
  native select/memory/remote, Polar mock ECG preview and XDF, and install-folder
  recording checks. A reinstall and successful isolated uninstall retained a
  test XDF byte for byte. The source ZIP and four public asset digests matched;
  the updated Pages build and ten public assets were verified.
- Exact hashes, commands, observations and limits:
  [`WINDOWS-INSTALLER-0.3.3-2026-10-01.md`](./WINDOWS-INSTALLER-0.3.3-2026-10-01.md).

### Offline XDF-to-CSV teaching export

- Result/date: `VERIFIED`, 2026-10-01, for source commit `e12db61` and PyXDF
  1.17.5. Captured CLI checks used no visible windows.
- Checks: `.venv/Scripts/python.exe -m pytest tests/test_xdf_to_csv.py -q`
  (1 passed); `.venv/Scripts/python.exe .for-ai-local/smoke_intern_notebook.py`
  executed the notebook without its already-satisfied install cell and
  independently ran the standalone script. Both produced four per-stream CSVs:
  148 Force, 6 heart-rate, 3 marker and 0 empty-status rows. Notebook JSON
  validation and `for-ai/scripts/check-context.ps1` passed.
- Inputs: sanitized local mock XDF SHA-256
  `d5faba93e052422a756dcaf6981ebed8041d0609b0357be5f9a734923d2c4a88`;
  ignored smoke harness SHA-256
  `1d1a6440b340f69d629e7fad911df27ebb0da58c43aae72f68e175bbf5cd6c5c`;
  nbclient 0.11.0. The XDF is excluded from Git.
- Limits: synthetic LSL streams only, with no participant recording or GUI
  qualification. The notebook install cell was not rerun because packages
  were already available in the kernel.
### Selectable recording folder, automatic CSV, and BIDS export

- Result/date: `VERIFIED` for source-level and headless synthetic checks,
  `NOT RUN` for the native folder picker and installed runtime, 2026-10-01.
  This entry supersedes earlier CSV-on/off evidence for the changed source.
- Checks: 51 focused Python tests passed across BIDS export, setup, recording,
  experiment flow and desktop bridge. `tests/check_recording.py` produced a
  verified native XDF with required raw/derived/marker streams and a BIDS export.
  A fresh export of that synthetic XDF passed `bids-validator@1.15.0 --json`
  with zero errors; it reported only missing optional Authors metadata.
  `pnpm check:ui` passed eight headless layouts and 15 actions; the changed
  Settings dialog was visually inspected. `pnpm test:web` passed six tests.
  Configured `pnpm check:remote` passed 12 layouts and 11 mocked mutations.
  MSVC-activated Cargo check, 10 Rust tests, fmt and clippy passed.
- Covered: local folder selection contract and persistence, XDF/CSV path owner,
  automatic CSV schemas, BIDS event/physiology files and Rust phone path redaction.
  BIDS physiology retains exact sample times in a timestamp column and describes
  the median observed rate; XDF remains the full-stream timing source. A failed
  export leaves no partial run files during ordinary error handling.
- Limits: Headless Chromium and native recorder CLI used synthetic LSL. The
  actual Windows folder dialog, installed app, restart, uninstall and release
  artifact were not exercised in an isolated desktop for this change. No physical belt,
  full-duration run or MNE-BIDS import was tested. The validator version is the
  deprecated npm CLI, not the newer Deno validator.

### All-stream BIDS export and MNE analysis reader

- Result/date: `VERIFIED` for source-level and offline mock XDF checks,
  2026-10-01. This supersedes the previous entry's selected-only BIDS coverage
  and median-rate physiology description; installed runtime remains `NOT RUN`.
- Checks: focused `pytest tests/test_bids_export.py tests/test_recording.py -q`
  passed 16 tests. Isolated MNE 1.10.2 `pytest tests/test_bids_mne.py -q`
  passed one test. `uv tree --no-dev` includes PyXDF 1.17.5 in the runtime
  dependency set. A retained Polar mock XDF exported 10 nonempty streams;
  2,663 rows were independently compared to the XDF for timestamps, values,
  channel count and stream identity. An empty status outlet stayed only in XDF.
  A separate Vernier mock XDF exported raw and derived outlets. Each BIDS
  dataset passed `bids-validator@1.15.0 --json` with zero errors and one optional
  `NO_AUTHORS` warning. MNE 1.10.2 read the Polar raw ECG physiology at 130 Hz
  and the irregular selected breathing waveform at an explicitly requested
  100 Hz; returned original timestamp counts matched 384 and 295 samples.
  MNE also read Vernier's 11-channel raw outlet and one-channel derived waveform
  at an explicitly requested 50 Hz, returning 661 original timestamps for each.
- Repeatable gate, 2026-10-01: `tests/check_bids_compatibility.py` ran on the
  same retained Polar and Vernier XDFs plus a native recorder proof XDF containing
  an anonymous int64 outlet. It checked 10/3/4 streams and 2,663/1,971/393
  sample rows against XDF, parsed every signal path with MNE-BIDS 0.20.0, and
  opened 10/3/4 numeric signals as MNE Raw with MNE 1.13.2 on Python 3.12.
  All three datasets had zero `bids-validator@1.15.0` errors and the optional
  `NO_AUTHORS` warning. The int64 BIDS table retained `9007199254740993`
  exactly. Focused exporter/recording tests passed 16 tests and the isolated
  MNE reader test passed one test against the final gate inputs.
- Inputs: ignored Polar mock XDF SHA-256
  `3d1762ca8215da2e12bb1715c171ca3762a2a90a3e86154520192f086ca1d254`;
  ignored Vernier mock XDF SHA-256
  `fcd2f4e804df53b606951b251fc95f2be68421049ffbcf06195c327e652dabcb`;
  ignored native int64 proof XDF SHA-256
  `aa71278f3b06adb16ec163d566395ed02cd0135f3d656ac629e55e1a8089ae1a`.
- Limits: synthetic Mini outlets, offline conversion, deprecated npm validator;
  no physical sensor, installed Respyra run, or direct
  `mne_bids.read_raw_bids()` qualification. Irregular signals require explicit
  resampling for MNE Raw. MNE-BIDS parsed BIDS paths; it was not used as a
  generic physiology Raw reader. XDF preserves the original values and timestamps.
