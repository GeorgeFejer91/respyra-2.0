# Experiment parity audit

Scope: the imported Jenny validation study in commit `1df21b0`, the current
PsychoPy runner, the pinned Respyra 0.4.0 phase/target APIs, new Mini input
contracts, CSV/XDF/BIDS outputs and session plots. This is not a claim that every
feature of the original general-purpose Respyra toolbox has been ported.

## Preserved study behavior

| Contract | Audit result |
| --- | --- |
| Trial structure | 48 sequential trials, four blocks of 12, eight occurrences of each of six named conditions. |
| Target | Four sine cycles at 0.1 Hz in each 40-second tracking phase; original target generator and global range center/amplitude. Per-trial natural baseline remains diagnostic and does not replace the global target range. |
| Phases | Instructions, range readiness/calibration/accept or retry, then trial readiness, 10-second baseline, 3-second countdown, tracking, three assessments, trial feedback and completion. |
| Range | 15 seconds; 5th/95th percentiles and 0.8 scale. Original Vernier minimum amplitude and saturation warning behavior remain. Polar has its separate signed-g calibration and validity gates. |
| Gains | Feedback normal 1.0, deep 0.5, shallow 1.5, applied around the calibrated center. The three legacy no-feedback definitions use gain 1.0. |
| Assessments | Accuracy 1–5, breathing judgment n/d/s, confidence 1–5, in the original order. |
| Logging | Original sample/assessment values retained; timestamp fields added as described in [timestamps.md](timestamps.md). Incremental flush and cleanup keep completed rows on ordinary failure/abort. |
| Summary | Original six-panel plot functions preserved: full trace, tracking errors, per-trial errors, distribution, baseline stability and text summary. XDF is primary; legacy CSV remains accepted. |

The original `feedback=False` suppresses target-dot colour feedback; it does
**not** hide the breathing trace or target. The current runner preserves this.
The condition names alone should not be interpreted as a blank display or as
three different physical breathing instructions during no-feedback trials.

## Deliberate differences

- The imported config used session parity for block order. The current accepted
  contract uses participant-number parity, with the same two realized orders.
  Participant 0 is in the even group. Record that choice when comparing old data.
- Acquisition now comes from Vernier Mini's raw Force channel in N, or Polar
  Chest Motion/Chest Motion DT in signed g, through validated LSL metadata. The
  experiment does not connect to a Vernier device itself. Polar values are not
  Newtons and do not establish physiological equivalence to belt force.
- Each alternative live input has its own comparison calibration. It does not
  drive the selected feedback. Essential Mini defaults reduce duplicated outputs;
  required raw, calibrated and event streams remain recorded.
- Missing/no-variation input fails visibly instead of silently substituting a
  plausible calibration. Escape during tracking or an assessment exits directly
  instead of continuing to ask subsequent questions. Cleanup retains recordings
  and completed CSV rows, and troubleshooting can show a separate copyable report.
- XDF reconstruction computes errors at accepted sample times. Legacy CSV values
  use the target evaluated when a display frame consumed the batch, so the two
  analyses can differ slightly. Neither records every rendered display frame.
- Optional wall-clock reference adds UTC/Berlin information without changing
  monotonic experiment timing. Offline operation remains supported.

## Evidence and limits

Focused clock/study/recording/export/summary tests passed. Two isolated,
shortened 48-trial native runs passed: one with a live API reference and one
using the offline computer reference. The study configuration retains the
full scientific durations; tests shorten them only to check progression. Exact
commands and observed results are recorded in `for-ai/VERIFIED.md`; recordings stay local.
Prior installed 2.3.12 evidence covers its unchanged UI, Mini defaults, popup,
upgrade retention and XDF plotting. It does not certify the new timestamp code
inside that existing installer.

Physical H10/GDX-RB acquisition, physiological validity, actual monitor refresh
and full-duration participant timing remain separate qualification boundaries.
This audit does not claim collection readiness on an untested lab setup.
