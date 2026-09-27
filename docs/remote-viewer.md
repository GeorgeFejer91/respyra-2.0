# Respyra experiment control and phone panel

The HTML window is the experimenter controller: participant/session setup,
LSL discovery and selection, Start/Cancel, live monitoring, Stop experiment,
and the final Close. PsychoPy still owns participant instructions, calibration,
stimuli, keyboard responses, assessments and display-flip markers.

## Use it

1. Launch Respyra and keep the LSL recorder running.
2. Select **Enable phone control** in Experiment control. Scan the QR code or
   open its private link in a phone browser.
3. Select **Connect** on the phone. One phone controls the same setup and run.
   The enabled invitation explicitly shares participant/session fields and
   LSL source metadata with that phone. Keep it private.
4. **Stop experiment** ends the study and cleans up its source/display, while
   the controller and marker outlet stay open. Keep recording through **Close**.
5. **Disable phone control**, app closure, phone disconnect or ownership expiry
   revokes remote control. Enable again for a fresh link. Phone loss leaves an
   ongoing study running; participant inputs remain local to PsychoPy.

A second display or the phone lets the experimenter monitor without moving
focus away from the participant window. On a single display the control
window may sit behind PsychoPy's full-screen window.

Both controllers show run status, trial/condition, phase/screen, latest marker,
and the age of received finite LSL Force samples. “Live” confirms LSL reception,
not correct belt placement or physiological signal quality. The current
VernierRaw Force contract has no battery telemetry, so battery is **Not reported**.
No raw waveform or assessment responses are sent to the phone.

## Connection and authority

The invitation lasts at most four hours and uses fresh 256-bit credentials.
The QR contains room/secret in a fragment; native grant/owner tokens never
leave the bundled desktop WebView. The fragment is scrubbed on phone load,
and neither invitations nor participant fields are saved in browser storage.

BRSP/1 negotiates:
- experiment.observe: bounded latest state and lease renewal.
- experiment.setup: participant/session key/edit, scan/select/use, Cancel.
- experiment.run: Start, Stop, final Close.

Python remains the sole study/source/LSL-clock authority. Rust serializes local
and remote commands onto the same bounded private pipe, assigning global
ui_seq while preserving ui_origin, ui_client_seq and each browser's
ui_time_ms. Local and phone clocks are separate from LSL. A valid stale
precondition is a rejected command, rather than a failed study.

Mutations use reliable BRSP commands and receive applied only after Python
accepts the action. Start acknowledges study acceptance; scan/use acknowledges
launch of the source operation, whose completion arrives in state. Stop
acknowledges source/display cleanup. Close acknowledges the accepted shutdown
request; it cannot establish XDF persistence. An uncertain command outcome
pauses control and requires checking the local controller; there is no automatic
new-ID retry.

Rust owns the invitation, peer/epoch-bound owner, six-second monotonic lease,
scopes, ordered dispatch sequence, mutation-ID/body deduplication and separate
control revision. The phone renews through authenticated commands every second.
Native reads/effects fail after revocation or expiry. Only the bundled main
WebView has the narrow native capability; external pages have none.

Mutual HMAC proof and the wire sequence remain in pinned BRSP JavaScript in
that trusted bundled WebView. Native claim/dispatch therefore trusts its
authenticated identity assertion; this is an owned native safety fence, not
independent Rust verification of every network proof. Compromise of bundled
code/native IPC is outside that boundary. Arbitrary invoke, shell, DOM/keyboard
injection, remote intent and protocol-variable edits are not exposed.

The host sends complete latest state at four updates per second. Python's
worker publishes latest marker metadata and source freshness without
pipe/network I/O on display flips. Blocking participant prompt waits drain the
accepted inlet; active study phases retain their existing acquisition path.
Intermediate monitor events may be skipped; the LSL recorder retains the
complete event timeline. Progress traffic does not advance the control revision.

The phone disables mutations after two seconds without fresh state.
Disconnect/hidden phone pages end ownership; native expiry also fences a
suspended or lost peer. Background WebView/browser throttling can delay status.
Monitoring and command latency are not scientific display-timing guarantees.

Pinned VDO.Ninja SDK 1.5.5 provides data-only duplex WebRTC with Internet
signaling/STUN/TURN. No microphone/camera capture, local HTTP server, opened
port or application-data WebSocket fallback. Report direct/relay/unknown from
actual quality readback; this is not offline-LAN control.

## Recorder workspace and hosting

You can load the private link in Recorder's **+** external page tab. Approved
Recorder phones receive that tab, but Respyra has its own connection and
supports one controller: leave the desktop Respyra panel disconnected and
Connect on the phone. Recorder's pairing does not grant Respyra controls.

The Respyra QR opens this controller directly; Recorder's QR opens its combined
workspace. Import companion/panel.json for a permanent disconnected tab.
Recorder saves the base page only and mirrors invitations in memory.
Never publish an invitation inside a panel descriptor.

Source lives here in companion/ with shared presentation/profile generated
from web/. pnpm prepare:web produces reviewed static assets and pinned vendor
licenses. The configured GitHub Pages destination for these assets is:
https://georgefejer91.github.io/respyra-2.0/
The gh-pages branch contains static companion files and their source SHA only.
Python, session data and grants are never deployed. The Recorder iframe is
opaque and denies parent/native access and storage; the pinned SDK connector
disables only its unavailable optional cache hooks.

After committing validated source, run scripts/publish-phone.ps1. It prepares
the locked assets and publishes only companion/ to an isolated gh-pages
worktree. First-time site enablement uses GitHub Pages' branch source setting.
GitHub Pages needs an eligible account plan for a private source repository;
pushing the static branch does not activate hosting. Site activation must
succeed before the generated QR link can open the controller on a phone.
Confirm the Pages build and public source.json/index/module bytes before
claiming the updated phone controller is live.

## Qualification

Run pnpm test:web, pnpm check:ui, Rust tests/clippy and the focused Python
desktop/source/marker/study tests. With RECORDER_COMPANION set, pnpm check:remote
exercises actual modules in Recorder's opaque iframe, controls/acknowledgments,
monitoring, revocation, secret-free preferences and narrow/enlarged layouts.
Its native bridge is mocked; default transport is deterministic.
RESPYRA_REAL_VDO=1 exercises public VDO with that same mocked backend.

tests/check_native_lsl.py additionally pairs the built Windows WebView target
with an external Chrome controller over real VDO and actual Rust/Python,
synthetic Force streams, a real PsychoPy instruction display and LSL marker
inlet. It checks controller-origin edits/Start/Stop/final Close, cleanup and
continuous marker ordering. Its phone assets are locally routed; deployment
checks must confirm the published static bytes separately.

Physical phone camera/touch/browser lifecycle, physical belt, Raspberry Pi,
scientific timing and independently persisted XDF are separate gates.
