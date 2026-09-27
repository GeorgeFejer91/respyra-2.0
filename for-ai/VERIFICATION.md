# Verification and readiness gates

Evidence must match the claim. Missing dependencies, credentials, hardware, or
runtime access produce `BLOCKED` or `NOT RUN`, never `VERIFIED`.

## Result vocabulary

- `VERIFIED`: the named check directly observed the claimed surface and passed.
- `PARTIAL`: some required evidence passed and the missing scope is named.
- `BLOCKED`: a concrete external or authority blocker prevented the check.
- `NOT RUN`: the check was intentionally not applicable or not attempted, with
  the reason stated.

## Gate 0: bootstrap readiness

From the repository root:

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

Run the narrowest real check for the change. Add the exact commands here when
the project selects its stack. A syntax check proves syntax; a unit test proves
its tested logic; neither proves UI, deployment, hardware, performance, safety,
or scientific validity unless it directly observes that surface.

For signal helpers, run `uv run pytest tests/test_signal.py`. For LSL input
changes, run `uv run pytest tests/test_lsl_force.py`; inspect raw outlet metadata
against the Polar-Mini-Stream source revision used for the change. For
marker or experiment changes, run `uv run pytest tests/test_event_markers.py`
and `uv run pytest tests/test_experiment_flow.py` against the installed
`respyra` dependency (the sibling checkout can differ from the published
version). For HTML control/pipe changes, run
`uv run --frozen pytest tests/test_desktop_bridge.py tests/test_desktop_process.py`
and `pnpm test:web`. The real process check must receive setup state after a
real marker subscription and keep the outlet alive through final Close. Verify
the launcher imports no study/PsychoPy modules, the startup outlet is discoverable
without any belt, and a subscriber joining after 30 seconds still enables setup
on the same outlet identity. Run the lifecycle helper in its private LSL
SessionID so an existing recorder cannot satisfy its subscription gate.
For startup discovery and remembered selection, also run
`uv run pytest tests/test_lsl_setup.py`: exercise the Python form controller, reject
incompatible results, verify saved-source reconnect and loss, prevent Start
without valid input, and close cancelled connections without overwriting memory.
Check identity persistence/corruption and duplicate source IDs in the input
tests. Run a synthetic LSL outlet/inlet check for metadata, discovery, and exact
identity reconnect; use isolated settings so tests never overwrite lab choices.
Check that every emitted event name appears in `catalog.json`, every
blocking screen has shown/dismissed markers, phase start/end and abort paths
pair sensibly, no-data calibration fails, and the experiment creates no CSV
file. Inspect the configured trial order and target/error units in N.

For the desktop shell and text layout:

```powershell
pnpm install --frozen-lockfile
pnpm prepare:web
pnpm test:web
pnpm check:ui
cargo fmt --manifest-path src-tauri/Cargo.toml --check
cargo test --manifest-path src-tauri/Cargo.toml --locked
cargo clippy --manifest-path src-tauri/Cargo.toml --locked --all-targets -- -D warnings
pnpm tauri build --debug --no-bundle
uv run --frozen python tests/check_native_lsl.py
```

`check:ui` uses installed Chrome and a mocked native bridge with the actual form.
It checks controls, action order, long identities, 320/820/1440 CSS px, doubled
text and text-spacing overrides. The native check requires Windows/WebView2,
the built debug executable and port 9227 free. It opens real windows, uses
synthetic Force/normalized outlets, isolated settings, a private LSL SessionID
and a live marker inlet;
checks selection, automatic reconnect, PsychoPy instruction flip, abort/cleanup
and marker sequence, plus native WebView reflow at 320/1440 CSS px and doubled
text. The Rust lifecycle test covers normal, failed and deliberately hung Python
children, including the bounded process-tree termination fallback on Windows.
Keep diagnostic output in ignored `.for-ai-local/`.
The private SessionID keeps test streams out of live recordings. Neither check verifies a
physical belt or persistence to an XDF file.

Do not let Python library subprocesses inherit the control pipe. Windows Git
can hang when another thread reads that inherited stdin. The desktop worker
duplicates its control input and replaces standard input with the null device;
retain this isolation and verify the real process after startup/import changes.

## Gate 3: integrated readiness

Run proportionate build, test, lint, type, runtime, visual, device, security,
and compatibility checks for every affected boundary. Do not run an expensive
or irrelevant full matrix for a documentation-only edit.

The experiment runtime requires Vernier Stream Mini's live raw LSL outlet, a
recorder subscribed to `VernierRaw` and `Respyra-Events`, and a PsychoPy
display. Use the streamer's explicitly marked mock outlet to check discovery,
metadata, fresh samples, marker order, early/normal/failed endings, and an LSL
recording containing both streams. Then verify the physical belt separately.
Mark unavailable surfaces `NOT RUN`; an LSL subscriber is not proof that the
recorder persisted the recording.

## Gate 4: publication

1. Review status and diff; preserve unrelated changes.
2. Confirm only intended paths are staged.
3. Confirm all required gates passed or are honestly reported.
4. Create one coherent commit under normal repository policy.
5. Push without force and without bypassing protection or secret scanning.
6. Verify the remote commit and required CI/deployment for that exact SHA.

## Handoff evidence

Report exact commands or observed surfaces, results, untested scope, commit SHA,
remote synchronization, CI/deployment state, and whether `for-ai/` changed.
