# Respyra experiment control and phone panel

The HTML window is the experimenter controller: participant/session setup,
LSL discovery and selection, automatic CSV saving, marker stream naming,
Start/Cancel, live monitoring, Continue (Space), Retry calibration (R), Stop experiment,
and the final Close. PsychoPy still owns participant instructions, calibration,
stimuli, keyboard responses, assessments and display-flip markers.

## Use it

1. Launch Respyra and select one compatible live Vernier or Polar breathing
   input for feedback. Start automatically records XDF
   with the bundled native recorder before calibration. Original CSV output is automatic.
2. Click **Remote Viewer**. Its popup creates a QR code automatically. Scan it
   or open its private link in a phone browser.
3. Enter a name on the phone and tap **Request access**. The desktop popup shows
   that self-entered name. Click **Approve** to share state and controls, or
   **Reject** to revoke the invitation.
   Requests expire after 60 seconds; no state or commands are available before
   approval. One approved phone controls the same setup and run.
   Approval explicitly shares participant/session fields and
   live raw-channel readings, marker names and LSL metadata with that phone. Keep it private.
4. **Stop experiment** ends the study and cleans up its source/display, while
   the native recorder finalizes XDF after cleanup; the controller and marker
   outlet stay open. Wait for **Saved**, then **Close**.
5. During a run, **Continue (Space)** dismisses the current instruction, ready,
   calibration result, feedback or final screen. **Retry calibration (R)** is
   available only on the calibration result. These buttons appear above the
   phone's monitor and in the desktop Experiment hub. Questionnaire answers
   remain local. Each command targets one visible prompt; delayed or duplicate
   taps cannot advance a later screen.
6. **Disconnect remote controller**, app closure, phone disconnect or ownership expiry
   revokes remote control. Open the button again for a fresh link. Phone loss leaves an
   ongoing study running; PsychoPy retains response and display authority.

A second display or the phone lets the experimenter monitor without moving
focus away from the participant window. On a single display the control
window may sit behind PsychoPy's full-screen window.

The phone shows experiment setup and the LSL monitor on one scrolling page.
Select a channel from the accepted raw Vernier stream to view its value/unit,
a ten-second trace and timestamped marker ticks. Four recent markers stay
visible; the full last-12 list is under details below the monitor. Start,
Stop/Close and recording status remain on the same page. The trace uses coalesced
four-Hz snapshots of the existing clock-synchronized inlet, holds through loss,
and breaks across gaps. It is a live preview, not an analysis waveform; XDF
contains full-rate data and late streams. No extra LSL inlet or processing is added.

Both controllers show run status, trial/condition, phase/screen, sent-event count, latest marker,
and the age of received finite LSL Force samples. “Live” confirms LSL reception,
not correct belt placement or physiological signal quality. The current
VernierRaw Force contract has no battery telemetry, so battery is **Not reported**.
The recent-marker list retains only 12 event names/sequences, with no assessment
payloads. Marker output reports successful pushes to the local LSL outlet,
not recorder persistence. Name changes are refused after subscription or Start
to avoid disrupting the selected stream. The private invitation shares the bounded
raw-channel preview; assessment payloads, native paths and files stay local.

## Connection and authority

The invitation lasts at most four hours and uses fresh 256-bit credentials.
The QR contains room/secret in a fragment; native grant/owner tokens never
leave the bundled desktop WebView. The fragment is scrubbed on phone load,
and neither invitations nor participant fields are saved in browser storage.

BRSP/1 negotiates:
- experiment.observe: bounded latest state and lease renewal.
- experiment.setup: participant/session key/edit, marker name,
  scan/select/use, Cancel.
- experiment.run: Start, prompt Continue/Retry, Stop, final Close.

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

Continue/Retry use a closed `prompt_control` action, never arbitrary keyboard
injection. Python exposes an opaque run UUID + shown-marker sequence only at
the actual display flip, plus the currently allowed controls. It checks that
identity again when consuming the response and clears it on dismissal or
interruption. The viewer permits only one pending control and disables the
consumed prompt until a fresh prompt arrives. Python acknowledges success
after the normal dismissal and calibration retry/accept markers.
`ui.prompt_control` records control, prompt identity, accepted/rejected outcome,
reason, and controller sequence/origin/time on the study LSL outlet. The normal
`input.key` uses `remote_control` or `local_control` as its source and has no
physical key timestamp. Authentication, schema and revision denials before the
Python pipe are protocol outcomes; they do not emit study markers.

Rust owns the invitation, single pending approval request, peer/epoch-bound owner, six-second monotonic lease,
scopes, ordered dispatch sequence, mutation-ID/body deduplication and separate
control revision. The phone renews through authenticated commands every second.
Native reads/effects fail after revocation or expiry. Only the bundled main
WebView has the narrow native capability; external pages have none.
The local-only review action binds approval to the current request and invitation.
Authentication plus the phone's bounded name introduction creates a pending
request, never an owner. The name is self-entered and does not prove identity.
Reject invalidates the
invitation; timeout denies late approval. Opening the popup or scanning its QR
does not start an experiment. Closing the popup does not disconnect an approved
controller. Restored base pages stay disconnected and retain a manual Request
access option for a pasted fresh invitation; private links wait for the phone's
name and request action.

Mutual HMAC proof and the wire sequence remain in pinned BRSP JavaScript in
that trusted bundled WebView. Native claim/dispatch therefore trusts its
authenticated identity assertion; this is an owned native safety fence, not
independent Rust verification of every network proof. Compromise of bundled
code/native IPC is outside that boundary. Arbitrary invoke, shell, DOM/keyboard
injection, remote intent and protocol-variable edits are not exposed.

The host sends complete latest state at four updates per second. Python's
worker publishes latest/recent marker metadata and source freshness without
pipe/network I/O on display flips. Blocking participant prompt waits drain the
accepted inlet; active study phases retain their existing acquisition path.
Intermediate monitor events may be skipped; only a correctly operated recorder
can retain the complete event timeline. Progress traffic does not advance the control revision.

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
supports one controller: use the private invitation on the intended controller
and approve it in Respyra. Recorder's pairing does not grant Respyra controls.

The Respyra QR opens this controller directly; Recorder's QR opens its combined
workspace. Import companion/panel.json for a permanent disconnected tab.
Recorder saves the base page only and mirrors invitations in memory.
Never publish an invitation inside a panel descriptor.

Source lives here in companion/ with shared presentation/profile generated
from web/. pnpm prepare:web produces reviewed static assets and pinned vendor
licenses. The configured GitHub Pages site is:
https://georgefejer91.github.io/respyra-2.0/
It introduces the desktop app and links the installer. The phone controller is
at `/remote.html`; existing QR invitations to the root redirect there without
changing the private invitation or desktop installer. The gh-pages branch
contains static site/controller files and their source SHA only.
Python, session data and grants are never deployed. The Recorder iframe is
opaque and denies parent/native access and storage; the pinned SDK connector
disables only its unavailable optional cache hooks.

After committing validated source, run scripts/publish-phone.ps1. It prepares
the locked assets and publishes only companion/ to an isolated gh-pages
worktree. First-time site enablement uses GitHub Pages' branch source setting.
The user authorized this repository to be public. Session data remain ignored;
the Pages branch deploys only static controller assets. Pushing a static branch
alone does not prove site activation or a completed deployment.
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
continuous marker ordering, rejection and a fresh locally approved request.
Use `tests/check_native_lsl.py remote` to run only the affected remote path.
Its phone assets are locally routed; deployment
checks must confirm the published static bytes separately.

Physical phone camera/touch/browser lifecycle, physical belt, Raspberry Pi,
scientific timing and independently persisted XDF are separate gates.
