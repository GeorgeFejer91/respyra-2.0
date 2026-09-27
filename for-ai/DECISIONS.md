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

## D-0004 — Remember validated input in the existing startup form

- Date: 2026-09-26
- Status: Superseded for Qt UI ownership by D-0005; source identity policy retained
- Context: Operators need to discover compatible LSL input and reuse their
  accepted belt without setting environment variables each session.
- Decision: Extend the existing PsychoPy Qt participant/session form with
  Add LSL Stream, compatibility results, and Use Selected Stream. Reuse the
  existing Force adapter and marker publisher. Require raw Vernier Force (N),
  unique stable source identity, full metadata, and live data before acceptance.
  Atomically save only identity/name in local user settings and revalidate on
  every launch. An absent or incompatible remembered outlet requires selection;
  do not substitute another source. Retain the environment override.
- Consequences: There is no new dashboard, dependency, signal processor, or
  persisted sample buffer. Discovery and connection run in one setup worker;
  markers are published by the UI when it observes results. Start is gated on
  accepted live input, and setup drains the inlet to avoid accumulating old data.
- Supersedes: None; extends D-0003 with UI selection and identity persistence.

## D-0005 — HTML/Tauri setup with the PsychoPy experiment authority retained

- Date: 2026-09-27
- Status: Accepted
- Context: The user approved replacing the Qt wrapper after requesting a GitHub
  rollback checkpoint. Experiment screens and paradigm decisions must remain
  governed by PsychoPy. The prior revision is tagged
  `qt-wrapper-checkpoint-2026-09-27`.
- Decision: Use a plain local HTML form in Tauri v2, with user-supplied identifier
  `dev.georgefejer.respyra2`. Rust supervises the fixed workspace Python engine
  over private bounded pipes and three closed commands. Reuse Python's Force
  validation, remembered selection, study phases and single marker outlet.
  Delete the Qt form and its event filters. Keep onset markers directly on
  PsychoPy flips; label HTML marker timestamps as backend receipt after IPC,
  with separate browser action sequence/time capture. Retain the outlet until
  final desktop closure so cleanup/Close events can be received.
- Consequences: No waveform samples or experiment frames cross desktop IPC.
  Qt remains a transitive distribution dependency. The initial executable needs
  the checkout and `.venv`; self-contained packaging needs separate work. Native
  shutdown attempts cleanup and has a 15-second kill limit, which cannot
  guarantee final markers if the engine hangs. Isolate standard input from
  library subprocesses to avoid Windows inherited-pipe hangs.
- Supersedes: Qt-specific ownership in D-0003/D-0004; preserves their signal,
  units, no-CSV, recorder and remembered-identity decisions.

## D-0006 — Experiment control window and opt-in phone controller

- Date: 2026-09-27
- Status: Accepted
- Context: The user designated HTML as the experimenter controller and requested
  QR-paired phone control of setup plus monitoring, while retaining PsychoPy.
- Decision: Reuse the existing BRSP/VDO transport with explicit local enable,
  phone Connect, and observe/setup/run scopes. Rust fences one owner by private
  grant, peer, epoch, native expiry/lease, sequence and control revision. Bundled
  JS retains mutual proof; external pages have no native capability. Reuse one
  HTML controller module and one Python action path with backend receipts.
  Global pipe sequencing retains the originating browser's sequence and clock.
  Keep the local control window available while PsychoPy owns participant
  screens. Add deliberate Stop with source/display cleanup and final markers;
  disconnecting a phone leaves the ongoing study running.
- Consequences: The enabled private invitation grants access to participant,
  session and LSL selection metadata. Monitoring uses received Force freshness
  and latest phase/trial markers, without raw waveform or flip-time network I/O.
  The user requested Respyra's own GitHub Pages hosting: publish static phone
  assets/provenance on gh-pages, and point QR/panel descriptors to that site.
  Keep the private repository's backend and session data off the Pages branch.
  Battery stays unavailable under the existing producer contract. Internet
  signaling is required; responsive browser evidence is not physical-phone,
  Raspberry Pi or scientific timing qualification.
- Supersedes: Startup-only HTML visibility in D-0005 and the read-only observer
  contract; retains Python/PsychoPy, recorder, no-CSV and source ownership.
