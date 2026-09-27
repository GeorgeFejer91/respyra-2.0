# HTML interface design principles

Read this before any HTML interface change. Always use `uncodixfy-pretext`,
its Pretext reference, `uncodixfy`, and `ponytail`. Reuse the locked local
Pretext package/fonts; measure bounded text and verify the rendered DOM.

## Main experiment interface

- Never use page or panel scrollbars. All content in the active view fits the
  viewport. Do not hide scrollbars or clip overflow to pretend it fits.
- Use one compact control center, modeled on Remote LSL Recorder's session/stream
  column, signal viewer and bottom recording/action bar. Never add a desktop view
  dropdown. Keep setup, accepted input, live signal, study status and recording
  status visible together. Optional marker/identity, recording-file and phone
  details use native HTML dialogs; they do not replace the main control center.
- Start launches respyrecorder and verifies exact Force/marker subscriptions and
  first raw samples before opening PsychoPy. Preserve these Python prerequisites.
- Paginate stream/event lists, preserving all entries and backend row identities.
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

The phone companion is a separate surface. Its reflow policy must not
reintroduce scrolling into the desktop interface.
It opens the LSL data/marker monitor; experiment setup uses a separate controls
view. Plot only received finite channel values, retain declared units, show gaps
and stale/paused status, and label the coalesced trace as a preview. Keep recording
status and Stop/Close accessible. Use `RECORDING.md` for data/authority boundaries.
