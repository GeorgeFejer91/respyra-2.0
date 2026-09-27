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
- Use three compact parts: participant/session and optional input markers;
  automatic stream checks plus checked inclusion list and stacked channel traces;
  one salient red Start/action bar. Record all available and late LSL streams by
  default. Never add a desktop view dropdown. Source selection, CSV, naming and
  diagnostics are optional native Settings dialogs; recording-file details stay
  outside the default workflow. The remote controller is a button opening a QR
  popup automatically, with desktop Approve/Reject on an authenticated request.
- Start launches respyrecorder and verifies exact Force/marker subscriptions and
  raw and marker samples before opening PsychoPy. After calibration, require actual
  native reception of the study's calibrated outlet before trials begin.
- Automatically connect a unique compatible belt or the exact remembered identity;
  require a choice only when discovery is ambiguous. Do not switch remembered belts.
- Paginate stream/channel/event lists, preserving all entries and backend row identities.
- Reflow and simplify before shrinking. Keep readable type, full critical
  instructions/errors, focus indicators, and accessible controls. Never undo
  user text enlargement. Impossible fits require an explicit no-fit outcome.
- Python retains Start prerequisites, study timing, input and marker authority.
  Layout work must preserve existing remote contracts.

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
