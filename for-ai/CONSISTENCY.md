# Suite consistency sweeper protocol

Keep the suite's implementation, documentation and delivered installers aligned
with the latest intentional, authoritative contract. A rename is complete only
when its producers, consumers, generated references and applicable delivery
surfaces agree, with intentional compatibility exceptions explicitly identified.
This protocol also covers types, units, channel roles/order, defaults, formulas,
paths, settings, commands, versions and supported behavior, not just spelling.

## When to sweep

- Every affected change: run a focused sweep before handoff for renamed or
  changed variables, stream/channel names, fields, configuration keys, defaults,
  versions or behavior described elsewhere. Include additions and removals.
- Every installer/release promotion: review the whole suite inventory below,
  then qualify the exact candidate under [PACKAGING.md](./PACKAGING.md).
- Periodically during active development: at session start, check the latest
  suite-wide sweep receipt in [VERIFIED.md](./VERIFIED.md). If absent or at least
  seven days old, do a suite-wide inventory review during that session. A
  focused sweep does not reset this date. An incomplete sweep remains due.
- Any reported mismatch or stale generated output: trace the affected contract
  immediately; expand scope if its owner or consumers are uncertain.

These are agent workflow checkpoints, not a scheduled background service. A
suite-wide review covers the inventory; it does not require rerunning every
test or rebuilding unchanged installers. Apply [VERIFICATION.md](./VERIFICATION.md)
and reuse evidence only while its actual inputs and scope still match.

## Establish the current norm

Follow the [router's authority order](./README.md). Trace an apparent rename to
the current user instruction, accepted decision and owning implementation/test.
Use revision history and explicit supersession to establish the latest
intentional convention; file modification times, the highest version string,
the majority spelling or a single recently edited occurrence are not authority.
An authorized rename can be only partly implemented: treat its remaining old
consumers as drift, not as votes against the new name. If intent or authority is
ambiguous, surface the specific conflict before changing that contract; continue
independent checks.

For each affected concept, identify its canonical owner, old name(s), current
name, effective source/release scope, semantic contract and intentional aliases.
Elevate the resolved convention in its existing canonical contract and update
active consumers in the same change. Use [DECISIONS.md](./DECISIONS.md) only for
a durable choice/supersession that needs rationale. Do not create another master
variable list here: stream naming belongs in [stream-names.md](../docs/stream-names.md),
stream semantics in [stream-protocol.md](../docs/stream-protocol.md), and marker
definitions in the existing source catalog.

Distinguish display names from stable metric/source IDs, saved-selection keys,
wire fields and recording schemas. A display rename does not authorize changing
all of those identities or scientific meaning. Keep deliberate legacy readers,
custom identifiers and historical recording names; test required migration and
compatibility. Different internal and display names can be valid when the mapping
is explicit. Never rewrite participant data, released artifacts or historical
evidence to make a text search clean.

## Coverage inventory

Trace each affected definition through these surfaces. A suite-wide review must
account for every row, with explicit scope/evidence or a reason it is not applicable.
Read nested agent instructions before changing a component; a missing submodule,
artifact or deployment is an evidence gap, not proof of consistency.

| Surface | Owners and comparisons |
| --- | --- |
| Producers and computation | `mini-streams/`, `src/mpi/`, `native/`: published names, identities, channel metadata, units, formulas, defaults, timing and optional outputs. |
| Consumers and analysis | Python discovery/setup/recording, calibration, CSV/XDF, BIDS/MNE, summaries, scripts and notebooks: selectors, transforms, headers, labels, saved keys and compatibility readers. |
| Controls and transport | `web/`, `companion/`, `src-tauri/`: desktop/phone labels, field IDs, action/IPC payloads, permissions, persistence and defaults. |
| Tests and generated references | Owning tests/fixtures, `src/mpi/event_markers/catalog.json`, reference/site generators and generated outputs: current expectations, old-input fixtures and reproducible derived files. |
| Documentation | Root/component READMEs, `docs/`, public variable/marker references, installation guides, release notes and current `for-ai/` contracts: names, units, examples, counts, paths and supported behavior. |
| Packaging and installation | `package.json`, Cargo/Tauri versions, locks, Mini revision, runtime/suite scripts and NSIS hooks: resource inputs, fresh defaults, upgrades, preference migration, shortcuts and installed behavior. Mini versions remain independent. |
| Delivered surfaces | Exact installer and extracted/installed payload, runtime/suite manifests, source archive/checksums, release/download links and deployed site/phone assets: bind each claim to its version, revision and artifact identity. |

## Sweep procedure

1. **Bound the work.** Inspect Git status and the latest relevant sweep/evidence.
   Name focused or suite-wide scope, source/component revisions and target
   release/deployment. Preserve unrelated changes. When HEAD is unavailable,
   bind inspected inputs by hashes; never manufacture a source revision.
2. **Trace both directions.** Start at each owner and follow callers, consumers,
   serializers, generators and packaging inputs. Search old and new spellings,
   case/prefix variants and related defaults/counts with `rg`. Include applicable
   submodule source explicitly and inspect relevant untracked files; a parent
   Git diff alone is insufficient. Exclude dependencies, caches, local recordings
   and raw evidence from ordinary source searches. Inspect generated/artifact
   contents separately. No textual matches does not prove runtime consistency.
3. **Classify every mismatch.** Record its owner and affected surfaces as actual
   drift, an intentional compatibility alias, a historical/version-pinned
   reference, or pending delivery/unknown. Give every retained old spelling an
   explicit reason. Resolve intent before propagating a convention.
4. **Reconcile the owned chain.** Fix the authoritative definition and affected
   consumers/docs/tests together. Regenerate derived references with the existing
   generator; do not patch only its output. Remove obsolete active examples and
   contradictory current rules. Preserve historical decisions/evidence and add
   explicit supersession or input invalidation where needed. Never bulk-replace
   substrings across unrelated concepts, saved data or compatibility fixtures.
5. **Verify observable agreement.** Re-search the variants and inspect remaining
   matches. Run only impact-selected checks, observing the producer-to-consumer
   boundary rather than merely asserting that two constants match. For stream
   changes, follow the existing stream/recording gates for actual outlet metadata,
   closed XDF and analysis outputs. For delivery claims, inspect the exact packaged
   and installed inputs plus deployed assets as applicable. All checks remain
   captured/headless or isolated under the background-execution policy.
6. **Record and report.** Update the narrowest canonical documentation and the
   sweep receipt below. Name remaining drift, unverified surfaces and the next
   concrete repair/check; do not hand off a blanket claim that everything is
   current while any applicable surface is unknown or pending.

## Source, installer and live documentation can have different states

A source-only rename does not change an existing installer or live website.
Keep released-version references accurate; document the new source convention
and its migration separately until the corresponding artifact is qualified and
published. Do not relabel an old binary, edit a generated manifest/checksum to
pretend it was rebuilt, or replace version-pinned documentation with unshipped
behavior. Record this as pending delivery, not fully aligned delivery.

For an authorized release, apply [PACKAGING.md](./PACKAGING.md) to the exact
installer, including fresh and upgraded settings where relevant, bundled Mini
revision/resources and installed observable names/defaults. Compare release and
live documentation against that artifact. Source tests or a debug build cannot
certify it. This sweep adds no publishing, installation, messaging or security
authorization; follow the existing task and workflow boundaries. Missing access
or isolation leaves the affected claim `BLOCKED` or `NOT RUN`.

## Sweep receipt and completion

Maintain one current suite-wide receipt and the latest relevant focused results
in [VERIFIED.md](./VERIFIED.md), linking a narrow `for-ai/verified/` record if the
details grow. Use its existing entry format and result vocabulary; keep raw
searches, logs and input hashes in ignored `.for-ai-local/`.

Record:

- Review date, focused/suite-wide scope, canonical owners and resolved mappings.
- Inspected source revisions/hashes and each installer/deployment identity.
- Each inventory surface's result: `VERIFIED`, `REUSED` with its original receipt,
  `PARTIAL`, `BLOCKED`, or `NOT RUN` with a scope-specific reason.
- Intentional aliases/history, actual drift repaired, remaining gaps, invalidated
  evidence, and the next concrete repair or release step.
- Exact checks/evidence and limits. A documentation-only protocol edit is not
  a suite sweep; do not advance the suite-wide review date for it.

An inventory review may finish with gaps, but it is not a fully passing sweep.
Full consistency requires matching evidence for every applicable surface and
no unresolved drift or pending delivery within the declared scope. Reused passes
retain their original execution dates. Periodic reviews refresh the comparison
against current inputs, not the age of old test results.
