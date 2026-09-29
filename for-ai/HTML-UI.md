# HTML interface design principles

Read this before any HTML interface change. Always use `uncodixfy-pretext`,
its Pretext reference, `uncodixfy`, and `ponytail`. Reuse the locked local
Pretext package/fonts; measure bounded text and verify the rendered DOM.
Select verification by impact in `VERIFICATION.md` and reuse prior unaffected
evidence from `VERIFIED.md`. Isolated opening-panel presentation changes require
`pnpm check:ui` plus inspection of the changed area; they do not require a study,
recorder, Rust, remote-pairing or installer run. Qualify the actual WebView when
native-specific layout/focus, fonts, embedding or WebView inputs change.
Use headless browser screenshots/DOM evidence without opening preview windows.
Actual native WebView/focus checks follow the isolated-GUI requirement in
`VERIFICATION.md`; never cover the user's open windows during verification.

## Main experiment interface

- Never use page or panel scrollbars. All content in the active view fits the
  viewport. Do not hide scrollbars or clip overflow to pretend it fits.
- Keep the Experiment hub and LSL streams on the same page. The compact hub has
  participant number, up to six remembered custom label/value pairs, and Start.
  The streams segment has side-by-side Vernier and Polar breathing-input
  dropdowns populated by validated LSL discovery. Selecting one makes it the sole
  study input; the Polar dropdown offers the two exact signed waveforms.
  Keep compact R/V choices and one shared XY plot with channel pagination.
  R selects XDF recording; V
  controls the local plot independently. The selected raw input and Respyra
  breathing rows appear first and are mandatory recording
  channels. All discovered streams are recorded by default, including later
  streams unless their current LSL UID was unchecked before Start. The remote button opens a
  QR popup with desktop Approve/Reject on an authenticated request. Settings
  contains the pre-recording marker name and optional original CSV export.
- Polar input requires an explicit inhale-direction choice after selection.
  Start prepares the derived outlet, launches respyrecorder, and verifies exact
  selected-input/marker/derived subscriptions and samples before opening PsychoPy.
  Before calibration, the normalized derived channel contains NaN. After
  calibration, require actual native reception of finite derived values before trials.
- Automatically connect a unique compatible source or the exact remembered identity;
  require a choice only when discovery is ambiguous. Do not switch remembered sources.
- Paginate stream/channel/event lists, preserving all entries and backend row identities.
- Reflow and simplify before shrinking. Keep readable type, full critical
  instructions/errors, focus indicators, and accessible controls. Never undo
  user text enlargement. Impossible fits require an explicit no-fit outcome.
- Python retains Start prerequisites, study timing, input and marker authority.
  Layout work must preserve existing remote contracts.
- The setup form saves participant and custom variable entries on edits;
  do not add a Save field labels button. The labels and values are restored on
  launch and must fit the compact local and phone controls. A legacy internal
  session value remains in recording metadata; the desktop hub does not ask for it.

## Restrained utility design

Adapted from SecretTunnel-v2's `for-ai/README.md`: “Uncodixfy / UI design
discipline”, “Cheng Lou Pretext / bounded text”, and “Minimal UI rule”.
Respyra does not adopt that project's scrollable-sheet exception.

- Extend the existing palette, typography, spacing, and ordinary controls.
- Reuse rows before creating components. Prefer one concise label plus one
  obvious action/state. Keep visible contents YAGNI.
- Avoid decorative cards, hero sections, gradients, glass, oversized radii,
  ornamental labels, redundant helper copy, and unnecessary animation.
- Allocate Grid/Flex geometry first, using shrinkable tracks and balanced
  insets. Measure remaining text space after padding, icons, and gaps.
- Match loaded fonts, locale, weight, size, line height, whitespace, and letter
  spacing between Pretext and the DOM. Predictions alone do not prove fit.
- Verify page edges, text, neighbors, keyboard navigation and focus at minimum,
  normal, and large viewports, long identities, 200% text, and spacing overrides.
  Report unsupported conditions honestly; Chromium does not prove WebView2.
  Distinguish a fresh browser check from inherited native evidence; ordinary
  presentation iteration need not repeat native lifecycle/LSL qualification.

The phone companion is a separate surface. Its reflow policy must not
reintroduce scrolling into the desktop interface.
It opens the LSL data/marker monitor; experiment setup uses a separate controls
view. Plot only received finite channel values, retain declared units, show gaps
and stale/paused status, and label the coalesced trace as a preview. Keep recording
status and Stop/Close accessible. Use `RECORDING.md` for data/authority boundaries.
