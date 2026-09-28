# Verification and readiness gates

Evidence must match the claim. Missing dependencies, credentials, hardware, or
runtime access produce `BLOCKED` or `NOT RUN`, never `VERIFIED`.

## Result vocabulary

- `VERIFIED`: the named check directly observed the claimed surface and passed.
- `REUSED`: a recorded `VERIFIED` result still covers unchanged inputs; cite its
  entry in `VERIFIED.md`. This is inherited evidence, not a new execution.
- `PARTIAL`: some required evidence passed and the missing scope is named.
- `BLOCKED`: a concrete external or authority blocker prevented the check.
- `NOT RUN`: the check was intentionally not applicable or not attempted, with
  the reason stated.

## Background execution is required

All verification runs must leave the user's open windows, focus and input
undisturbed. This is a standing user instruction for every gate, including
build helpers, browser checks, native integration, study and installer checks.

- Run command-line checks through captured tool output without opening a
  terminal/console window or allocating an interactive PTY. Redirect long logs
  to ignored `.for-ai-local/` and retain the actual exit status/completion;
  background execution does not mean abandoning an unobserved process.
- Keep Playwright browsers `headless: true`, with separate test contexts/profiles.
  Inspect screenshots and DOM results through tool output. Do not open/focus
  browser tabs, native apps or artifact previews automatically for verification.
- For Windows console helpers launched with PowerShell, use
  `Start-Process -WindowStyle Hidden` with redirected output. Where a Python or
  Rust launcher creates a console child, use `CREATE_NO_WINDOW` or the equivalent
  creation flag. Review children too: these flags hide consoles, not Tauri,
  PsychoPy, installer dialogs, or arbitrary GUI descendants.
- Checks that create actual GUI windows or exercise focus/keyboard/input hooks
  must use an available isolated Windows desktop/session, VM or test runner,
  separate from the user's interactive desktop. Confirm that the chosen
  environment supports the claimed graphics/WebView/input behavior before
  launching. Do not use the user's currently running study/app as a test target.
- Minimized/offscreen windows, a second monitor, Windows virtual desktops and
  hiding after launch are not proof of isolation; they may flash or take focus.
  Do not move/minimize existing user windows, change display settings, bring a
  test window forward or send global keyboard/mouse input to make a check pass.
- If no compatible isolation is available, do not launch the intrusive check.
  Continue applicable headless/CLI checks and valid evidence reuse; report the
  GUI scope `NOT RUN: isolated test desktop unavailable` (or the actual blocker).
  A mocked/headless browser pass does not replace native/PsychoPy/installer proof.
  Do not ask for routine foreground-testing permission. Only a later explicit
  user request for a visible interactive verification may change this rule.

Before launching a check, use the execution-mode inventory in `VERIFIED.md` and
inspect changed launchers. Existing native/full-study scripts are not currently
isolated by themselves and must not run on the active desktop. Record the actual
headless/CLI/isolated environment with new evidence; do not relabel older visible
passes as background-qualified. This policy edit does not require a GUI test.

## Select checks by impact

This is the default for every task, including opening-panel UI work. The command
lists below are a catalogue, not a checklist to run in full. Select only checks
whose behavior or dependencies the final diff can affect. Repository impact
selection takes precedence over broader generic skill checklists, as explicitly
requested by the user. Keep the skills' implementation and design requirements.

| Changed surface | Required focused evidence | Broader checks only when |
| --- | --- | --- |
| Documentation or `for-ai/` rules only | Context checker, diff and local-link review | Runnable commands or product contracts also change; check only that affected surface. No product build or runtime suite. |
| Opening-panel wording, colors, spacing, CSS or presentation markup | `pnpm check:ui` and inspect the changed rendered area | Native-specific fit/focus, font loading, WebView configuration or embedding changes need a focused real WebView check. No Python, Cargo, recorder, study or remote-pairing rerun for isolated presentation work. |
| UI interactions, state projection or action queue | Relevant `node --test tests/<affected>.test.mjs` and `pnpm check:ui` | Action names/payloads, sequencing, field identity, readiness, Start/Stop/Close semantics or shared phone controls change: add the affected bridge/remote checks. |
| Python signal, discovery, setup, markers or study logic | Corresponding `pytest` files from Gate 2 | A changed cross-process, LSL, study or recording contract needs its consuming integration check. Unchanged sibling modules keep their prior evidence. |
| Rust IPC, supervision, permissions or remote ownership | Rust fmt/test/clippy for the affected crate | Changed lifecycle/IPC needs the real process/native check; changed remote grants or dispatch needs remote qualification. |
| Recorder, calibration output, input capture or XDF contracts | Corresponding focused tests and affected recording/control-center proof | Run `--full-study` only for changes affecting trial progression, calibration use, study timing/markers, all-phase logging or finalization across the complete study, or a regression in those paths. |
| Locks, toolchain, runtime resources, installer or release candidate | Checks for consumers of the changed input; packaging gates for a new installer | A shared input change invalidates only its consuming evidence. Qualify each new promoted installer by exact artifact bytes as `PACKAGING.md` requires. |

Trace affected callers, imports, consumers and shared assets before declaring
an edit presentation-only. Moving controls can affect handlers or field IDs;
changing disabled states can affect readiness. Follow behavior, not just file
extensions. If impact is uncertain, inspect the boundary and run its smallest
relevant integration check; uncertainty alone does not require the full matrix.
`prepare-web.mjs` copies shared CSS/controller assets into the phone companion;
check affected phone rendering when a presentation edit reaches that surface,
without requalifying unchanged live pairing or study behavior.

Run selected checks once against the final relevant inputs. After a fix or later
edit, rerun only checks invalidated by that change. Do not repeat a passing check
for handoff, a new agent/session, a commit/push, or a control-plane update.
Do not install dependencies or rebuild unchanged runtimes as a ritual:
`pnpm install --frozen-lockfile` is needed only when dependencies are missing or
the lock changed; `pnpm check:ui` already runs `prepare:web`.

## Reuse recorded verification

Read [`VERIFIED.md`](./VERIFIED.md) for affected scopes before expensive checks.
After an observed pass, keep one compact entry per behavior/check, recording:
the command, result/date, tested commit (plus hashes for any uncommitted tested
inputs), covered behavior, relevant source/test/shared paths, locks/configuration,
runtime/tool versions or artifact hashes, evidence location and limitations.
Keep raw logs, screenshots and recordings in ignored `.for-ai-local/`.

A function's pass is reusable only for the behavior tested and while its inputs,
relevant dependencies, consuming contract, test and environment remain compatible.
A new commit SHA or time elapsed alone does not invalidate it. Compare the
recorded revision with the current tree, including staged, unstaged and new
inputs; for example `git diff <tested-commit> -- <covered-paths>`, then inspect
untracked inputs and recorded runtime/artifact identity. Use narrower function
reuse within a changed file only when the dependency review supports it.

Invalidate only affected entries when those inputs change, a relevant regression
appears, or the prior result lacks the evidence needed for the current claim.
Mark the reason and refresh the smallest necessary check. A missing entry does
not make unrelated checks applicable: populate the ledger as relevant work is
verified, never by running the whole project just to fill it. Preserve historical
passes without inventing source bindings. Live hosted endpoints, physical devices
and installed artifacts retain their separate evidence limits; reused local
evidence cannot certify their current state or a different installer.

## Gate 0: local context; bootstrap only when initializing

For an existing checkout, inspect `git status --short` and `git rev-parse HEAD`.
Run the context checker once when `for-ai/` changes or bootstrap is being checked;
it is not a product test. A feature branch or unrelated work is not a failure.
Check the actual branch's remote during publication, not `origin/main` on each
UI iteration.

For initial bootstrap synchronization only, from the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File for-ai/scripts/check-context.ps1 -ProjectRoot . -RequireRemote
git status --short
git rev-parse HEAD
git ls-remote origin refs/heads/main
```

Pass when the context checker succeeds, the intended tree is clean, and local
`HEAD` equals `origin/main`.

## Gate 1: task contract

Before implementation, name:

- the observable user outcome;
- affected product surface and owner;
- acceptance criteria;
- focused check that can fail for the requested behavior;
- broader checks required by affected boundaries;
- explicitly deferred work.

## Gate 2: focused change

Run the narrowest real check selected by impact above. A syntax check proves
syntax; a unit test proves its tested logic; neither proves UI, deployment, hardware, performance, safety,
or scientific validity unless it directly observes that surface.

For signal helpers, run `uv run pytest tests/test_signal.py`. For LSL input
changes, run `uv run pytest tests/test_lsl_force.py`; inspect raw outlet metadata
against the Polar-Mini-Stream source revision used for the change. For
marker or experiment changes, run `uv run pytest tests/test_event_markers.py`
and `uv run pytest tests/test_experiment_flow.py` against the installed
`respyra` dependency (the sibling checkout can differ from the published
version). For changed HTML-to-Python action/pipe contracts, run
`uv run --frozen pytest tests/test_desktop_bridge.py tests/test_desktop_process.py`
and `pnpm test:web`. The real process check must receive setup state after a
real marker subscription and keep the outlet alive through final Close. Verify
the launcher imports no study/PsychoPy modules, the startup outlet is discoverable
without any belt, setup edits work before any subscriber and markers remain
available through Close. Verify pre-subscription renaming; setup requires no
external subscriber, while Start requires native recording readiness and raw samples.
Run the lifecycle helper in its private LSL
SessionID so an existing recorder cannot satisfy its subscription gate.
For startup discovery and remembered selection, also run
`uv run pytest tests/test_lsl_setup.py`: exercise the Python form controller, reject
incompatible results, verify saved-source reconnect and loss, prevent Start
without valid input, and close cancelled connections without overwriting memory.
Check identity persistence/corruption and duplicate source IDs in the input
tests. Run a synthetic LSL outlet/inlet check for metadata, discovery, and exact
identity reconnect; use isolated settings so tests never overwrite lab choices.
For affected marker/study/logging contracts, check that every emitted event name
appears in `catalog.json`, every blocking screen has shown/dismissed markers,
phase start/end and abort paths
pair sensibly and no-data calibration fails. Run original CSV mode both on/off:
off creates no files; on preserves sample columns and self-assessment schema,
writes all phases and closes files even on early/error exit. Inspect trial order
and target/error units in N.

For text layout, use `pnpm check:ui`. For changed frontend logic, add the relevant
web tests (`pnpm test:web` runs all of them). For changed Rust shell/lifecycle
inputs, select these checks; this block is not required for layout-only edits:

```powershell
cargo fmt --manifest-path src-tauri/Cargo.toml --check
cargo test --manifest-path src-tauri/Cargo.toml --locked
cargo clippy --manifest-path src-tauri/Cargo.toml --locked --all-targets -- -D warnings
pnpm tauri build --debug --no-bundle
uv run --frozen python tests/check_native_lsl.py
```

`check:ui` uses installed Chrome and a mocked native bridge with the actual form.
For desktop layout changes, read `HTML-UI.md`. Verify the single control center at
820×760 and 1440×900, with the three-part minimal layout, all-stream recording
status, one paged plot of stacked channel lanes, colored marker lines crossing
the lanes, stream and event-catalog tabs, and centered red Start.
Check automatic unique-belt discovery, waiting/received calibration indicators,
optional input checkboxes, optional dialogs, stream/channel pagination with
original row identities, Escape closing a dialog without cancelling setup, and
read-only setup plus accessible Stop during a run. At small windows (320/360 CSS
px or 480 px height), doubled text and impossible fits, verify the explicit resize
notice and recovery. Assert page dimensions fit and visible content is unclipped;
never form a scrolling desktop page. The phone companion retains its reflow policy.
It checks controls, action order, long identities, 320/820/1440 CSS px, doubled
text and text-spacing overrides. The native check requires Windows/WebView2,
the built debug executable and port 9227 free. Under the background requirement
above, it opens real windows only in an isolated test environment, uses
synthetic Force/normalized outlets, isolated settings, a private LSL SessionID
and a live marker inlet;
checks selection, automatic reconnect, PsychoPy instruction flip, abort/cleanup
and marker sequence, plus native WebView reflow at 320/1440 CSS px and doubled
text. The Rust lifecycle test covers normal, failed and deliberately hung Python
children, including the bounded process-tree termination fallback on Windows.
Keep diagnostic output in ignored `.for-ai-local/`.
The private SessionID keeps test streams out of live recordings. The native check
imports the actual saved XDFs with independent PyXDF, checks required data before
display creation, contiguous marker sequences, cleanup/finalization and footers.
It verifies a synthetic source, not a physical belt. Give WebView2 a unique test
user-data folder as described by [Playwright](https://playwright.dev/docs/webview2).

For recorder/calibration/input changes, select the affected checks below.
Build the recorder only when its source/build inputs or required binary change.
The full-study trigger is defined in the impact table; it is not a default
recorder or UI check:

```powershell
pnpm prepare:recorder
uv run --frozen pytest tests/test_recording.py
uv run --frozen python tests/check_recording.py
uv run --frozen pytest tests/test_input_capture.py
uv run --frozen python tests/check_control_center.py
uv run --frozen python tests/check_control_center.py --full-study
```

The standalone native proof checks pre-calibration raw samples, calibration/cleanup
markers, late numeric/int64/source-less streams, Unicode output, clock offsets and
independent full XDF decoding. Failure tests cover missing required data, bad chunk
bounds/footers, missing bundle, Start rejection and hung-child reaping. Read
`RECORDING.md`; subscription or header receipts alone cannot prove persistence.

Do not let Python library subprocesses inherit the control pipe. Windows Git
can hang when another thread reads that inherited stdin. The desktop worker
duplicates its control input and replaces standard input with the null device;
retain this isolation and verify the real process after startup/import changes.

## Gate 3: integrated readiness

For changed remote controller contracts or shared control behavior, run the
affected web tests, `pnpm check:ui` and
`pnpm check:remote` with `RECORDER_COMPANION` pointing to Recorder's companion.
Run Rust tests/clippy and Python desktop/marker/study tests only for affected
owners. Presentation-only changes follow the UI row above. Qualify live VDO
separately with `RESPYRA_REAL_VDO=1`; browser checks still mock native IPC.
`check_native_lsl.py` also pairs an actual packaged WebView target with a Chrome
controller over public VDO and observes remote edits/Start/Stop/Close in Python,
with synthetic LSL input and real PsychoPy instruction flips. The static phone
assets are locally routed by default. Set RESPYRA_PUBLISHED_PHONE=1 to qualify
the real Pages endpoint without interception. The native check decodes the
rendered opening-panel QR and pairs the phone. Verify published byte parity and
ordinary 390×844 compact setup separately. Enlarged text/expanded details may
scroll while preserving every control.
For remote ownership changes, `tests/check_native_lsl.py remote` selects only
the remote mode. Check automatic private-link requests, inert restored base pages,
no state/commands before local approval, Reject followed by a fresh invitation,
late/wrong-request approval denial, wrong owner/epoch/scope/sequence, expiry/revocation,
stale revisions, unknown actions and duplicate IDs without repeated effects.
Report physical phone/belt, Raspberry Pi and XDF evidence separately.
See `docs/remote-viewer.md` for the ownership contract.

Run proportionate build, test, lint, type, runtime, visual, device, security,
and compatibility checks for every affected boundary. Do not run an expensive
or irrelevant full matrix for a documentation-only edit.

The experiment runtime requires Vernier Stream Mini's live raw LSL outlet and a
PsychoPy display. The bundled native recorder must receive raw input before Start acceptance.
Use the streamer's explicitly marked mock outlet to check discovery,
metadata, fresh samples, marker order, early/normal/failed endings, and an LSL
recording containing both streams. Then verify the physical belt separately.
Mark unavailable surfaces `NOT RUN`; an LSL subscriber is not proof that the
recorder persisted the recording.

## Gate 4: publication

Standalone installer work additionally follows `PACKAGING.md`. A workspace
build is not an installed-runtime check. Use `pnpm package:windows`, the staged
embedded import/resource check and the installed native/LSL/QR check via
`RESPIRA_INSTALLED_EXE`; retain exact installer hashes and release evidence.
Installer dialogs and installed native checks also require isolated execution;
an unavailable isolated runner leaves those release gates unverified.

1. Review status and diff; preserve unrelated changes.
2. Confirm only intended paths are staged.
3. Confirm all required gates passed or are honestly reported.
4. Create one coherent commit under normal repository policy.
5. Push without force and without bypassing protection or secret scanning.
6. Verify the remote commit and required CI/deployment for that exact SHA.

## Handoff evidence

Report checks run now, recorded evidence reused and why omitted suites are
unaffected. Report exact commands or observed surfaces, results, untested scope,
commit SHA,
remote synchronization, CI/deployment state, and whether `for-ai/` changed.
