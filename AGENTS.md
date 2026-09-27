# Respyra 2.0 agent instructions

Before inspecting, planning, editing, testing, or publishing this repository,
read [`for-ai/README.md`](./for-ai/README.md). It is the canonical router to the
project context, skill rules, verification gates, decisions, and workflow.

Keep `AGENTS.md` short. Durable orchestration belongs in `for-ai/`; product
source, shipped assets, end-user documentation, and deliverables belong outside
it. Read only the task-routed documents and skills, preserve unrelated work,
apply YAGNI, and never claim a check or deployment that was not observed.

System, developer, and current user instructions take precedence. Before
handoff, select gates by change impact in `for-ai/VERIFICATION.md`, reuse valid
recorded evidence in `for-ai/VERIFIED.md`, and update the
control plane only when a durable fact or rule changed.
Run verification in the background under `for-ai/VERIFICATION.md`; never cover
the user's windows or take focus on their active desktop.
