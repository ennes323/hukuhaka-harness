# Claude Code handoff

Use the plugin's native `hukuhaka-report-planner:artifact-designer` subagent.
Its bundled definition pins `model: claude-opus-5-5` and `effort: medium`.
This is a Claude profile, not an equivalence claim about the Codex designer.
Use a fresh subagent context, pass the complete shared payload, the resolved
sibling artifact-designer SKILL.md, and its references/worker-contract.md.
Instruct it to read that contract and use that exact skill before designing.

Delegate to the installed plugin-scoped subagent through Claude's native Agent
tool. Do not override its model or effort through the Agent call or settings,
substitute a generic agent, install a user-level or project-level copy, or build
in the planner context. If this exact native agent or profile is unavailable,
report the capability gap. Wait for completion in the current task and review
the shared completion receipt. Native packaging does not prove model
availability or design quality; confirm the selected profile in run evidence.

See [Claude subagent configuration](https://code.claude.com/docs/en/sub-agents).
