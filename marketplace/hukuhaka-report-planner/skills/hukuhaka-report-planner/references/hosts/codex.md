# Codex handoff

Spawn one write-capable worker with explicit `model: gpt-5.6-terra` and
`reasoning_effort: high`. Use a fresh context (`fork_turns: none`) and pass the
complete payload above, the resolved `artifact-designer` SKILL.md path, and its
sibling `references/worker-contract.md` path. Instruct the worker to read the
worker contract and use that skill before designing or writing.
Use the generic worker route; hosts may record an untyped spawn as `default`.
The specialist is defined by its explicit profile and bundled instructions,
not by that host role label.

The plugin owns this specialist through the handoff and bundled instructions;
it does not register a native agent through the plugin manifest. Do not use
`astra_worker`, whose role pin would override Terra, or the execution-only
`result-runner`. Do not inherit the parent's model or reasoning effort.
If explicit model/effort selection is unavailable, report that limitation
instead of silently substituting a model. Wait for completion in this task;
do not install a user-level or project-level agent.
