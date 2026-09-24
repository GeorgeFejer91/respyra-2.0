# Decision log

Record only durable choices whose rationale future agents would otherwise have
to rediscover. Source and tests remain the authority for implementation facts.

## D-0001 — Minimal control plane before product scaffolding

- Date: 2026-09-24
- Status: Accepted
- Context: The project needs a predictable AI entrypoint without choosing an
  application stack or inventing product structure prematurely.
- Decision: Use a short root `AGENTS.md` that routes to a lowercase `for-ai/`
  control plane. Keep product output outside that folder and add project files,
  skills, and protocols only for current requirements.
- Consequences: New agents get a reliable map and readiness gates. The first
  product task must still choose the smallest suitable output structure.
- Supersedes: None

## Record format

For later decisions, add one compact entry with:

- identifier and title;
- date and status (`Proposed`, `Accepted`, `Superseded`, or `Rejected`);
- context;
- decision;
- consequences;
- supersession link when applicable.

Do not rewrite accepted history to hide a changed direction. Add a superseding
decision and link both entries.

## D-0002 — Keep raw session data local

- Date: 2026-09-24
- Status: Accepted
- Context: The imported archive contains session force traces and
  self-assessments with participant-style identifiers in filenames.
- Decision: Unpack these files to local `data/` and ignore that directory in
  Git. Exclude the bundled virtual environment and generated files.
- Consequences: Source can be shared through the private repository; raw data
  remains available locally for review and requires a separate sharing decision.
- Supersedes: None

## D-0003 — Source study force through Vernier Stream Mini LSL

- Date: 2026-09-24
- Status: Accepted
- Context: The belt acquisition path now belongs to
  [Polar-Mini-Stream](https://github.com/GeorgeFejer91/Polar-Mini-Stream).
  Its raw LSL outlet carries Force in N; its derived respiration outlet carries
  a normalized 0–1 value. The study's targets and errors use N. An external LSL
  recorder, not Respyra, will persist the breathing signal and timeline.
- Decision: Discover and validate one live `VernierRaw` outlet from Vernier
  Stream Mini in Separate Streams mode, select the metadata-identified GDX-RB
  Force channel, and feed it into the existing study phases. Publish every
  discrete experiment and observed accepted/rejected PsychoPy key event on a
  catalogued LSL marker outlet. Require a marker-stream consumer before
  participant input.
  Do not write new session or self-assessment CSVs. Reject the upstream
  calibration's no-data fallback so an unmeasured run cannot continue with
  default force values. Retain the measured calibration and feedback logic
  until a separately reviewed protocol change.
- Consequences: Vernier Stream Mini must run first. Discovery ambiguity or
  signal loss stops a run. The recorder must select both the Vernier raw and
  Respyra marker streams; a marker subscriber alone does not prove persistence
  of either stream. The `respyra` dependency still contains its own unused Go
  Direct and CSV modules because this project uses its study phases; removing
  those transitive modules needs an upstream package split or a separate phase
  replacement. The native participant-dialog text fields use Qt callbacks for
  keys and edits; individual animation frames are outside the discrete marker
  contract.
- Supersedes: None
