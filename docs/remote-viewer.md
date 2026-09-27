# Respyra remote experiment panel

Respyra 2.0 adopts Remote LSL Recorder's
[Remote Panel/1](https://github.com/GeorgeFejer91/Remote-LSL-Recorder/blob/main/docs/remote-panel-profile.md).
The read-only viewer shows setup/run/result status, trial, condition, phase,
screen and the latest marker's name, sequence and original LSL timestamp.
It excludes participant/session fields, responses, source identities, raw
force samples, private paths and detailed error messages.

The default view is four plain rows: status, trial/condition, phase/screen and
latest event. Pairing input disappears once an invitation is present. Route,
revision, input readiness and marker timestamps are under Connection details.
VDO.Ninja is the coupling mechanism; there is no HTTP polling between peers.
The host sends complete latest state at up to four updates per second and the
viewer replaces its displayed state. The two-second stale indicator remains
visible. This is live monitoring, not a scientific timing guarantee.

## Use it

1. Launch the updated Respyra desktop executable. Select **Start viewer**.
   This explicitly grants progress viewing to the holder of a fresh private
   invitation, for up to four hours.
2. Select **Copy viewer link**. In the desktop Recorder, select **+**, name
   the tab `Respyra 2.0`, paste the complete link as the URL and **Load page**.
   Select **Connect** inside Respyra to view progress.
3. For phone use, leave the desktop Respyra panel disconnected. Start Recorder
   pairing, scan its QR and approve the phone on the PC. The phone automatically
   receives the Respyra tab and current invitation. Select **Connect** inside it.
   This version supports one observer at a time.
4. **Stop viewer**, Respyra closure or observer disconnect ends the session.
   Start again for a fresh invitation. Viewer closure does not stop the study
   or recorder. PsychoPy participant controls remain local.

The Respyra QR opens its viewer directly; the Recorder QR opens the combined
workspace. They represent separate sessions and scopes.

For a permanent disconnected tab, import [`panel.json`](../companion/panel.json)
using **Import app panel (.json)**. Its URL is
`https://georgefejer91.github.io/Remote-LSL-Recorder/panels/respyra/`.
After restart, paste a new private invitation inside that viewer. Recorder
remembers the base URL/name and mirrors current invitations only in memory.
Sharing a Recorder panel exports its base URL, not Respyra access. Do not put
a private invitation in a public descriptor.

## Ownership

- Python owns study logic, input, acquisition and the LSL marker clock. After
  each successfully published marker, an observer replaces a small public
  projection. A worker sends the newest projection at most four times per
  second. Viewer pipe/network I/O never runs on PsychoPy display flips.
  Intermediate viewer events may be skipped; LSL retains the full timeline.
- Rust supervises Python, issues/revokes expiring grants and sanitizes every
  observer snapshot. The closed `viewer_action` surface accepts only start,
  token-bound snapshot and token-bound stop. Network commands never reach
  experiment setup, Start, abort, input injection or files.
- Local bundled JavaScript adapts native projections into BRSP/1 mutual proof,
  reliable snapshots and replaceable state. Only `experiment.observe` is
  granted. All commands and intent are refused; starting the viewer approves
  only this observation scope.
- Pinned VDO.Ninja SDK 1.5.5 uses one data-only duplex WebRTC connection and
  Internet signaling/STUN/TURN. No media capture or application-data WebSocket
  fallback. Direct/relay/unknown comes from peer-quality readback.
- A preloaded viewer remains disconnected until Connect. The Recorder iframe
  denies storage and parent access. The reviewed connector disables only the
  pinned SDK's unavailable cache hooks. Current-URL fragments are scrubbed;
  credentials remain in memory. No service worker or analytics.
- Missing updates are flagged after two seconds. Hidden WebView/browser
  throttling can delay presentation while study/LSL publication continues.
  Last marker time is diagnostic, not evidence of display timing.

## Source and hosting

`companion/` owns viewer source; typography/profile are generated from `web/`.
`pnpm prepare:web` produces deployable assets using pinned transport sources
and licenses in `vendor/remote/`. Only those static assets are published under
the Recorder's `panels/respyra/` path. The Python engine, participant data and
invitations are never deployed. Hosting there grants no Recorder DOM/native
access.

## Checks and qualification

```powershell
pnpm prepare:web
pnpm test:web
$env:RECORDER_COMPANION = '<Recorder checkout>\companion'
pnpm check:remote
# Optional public VDO browser check:
$env:RESPYRA_REAL_VDO = '1'
pnpm check:remote
```

The browser check exercises actual modules in an opaque Recorder iframe,
explicit activation, mutual proof, progress, secret-free preferences,
revocation and 320/390/844/1280 CSS px, doubled text and text spacing.
Default transport is deterministic; native grant/projection is mocked.
The optional public VDO check still mocks native IPC. Rust tests exercise grant
rotation/expiry and privacy. Python tests cover marker ordering, latest-only
projection, study endings and the real private pipe/LSL lifetime.

Packaged WebView transport, physical phone/belt and independent XDF inspection
are separate gates. Browser checks do not establish scientific timing or
recording persistence.
