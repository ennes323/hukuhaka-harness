# Codex Worklog adapter

Invoke `$hukuhaka-worklog:worklog setup`, `status`, or `archive` for deterministic
commands. Legacy `$worklog` commands remain accepted. Trusted UserPromptSubmit
hooks handle exact command prompts and report the result without model work.
Other requests use the shared recording procedure.

Setup owns only its managed block in project AGENTS.md and creates missing
Worklog files without replacing existing records. The native hooks declare
`--host codex` and use PLUGIN_ROOT/PLUGIN_DATA; environment aliases never select
the host. Paired PreToolUse/PostToolUse events share the archive core and safety
rules. Without trusted hooks, run the bundled deterministic command directly:

`python3 <this-skill>/scripts/worklog.py --host codex --root <project> archive`

Use `setup` or `status` in place of `archive` for those operations. Automatic
archiving is unavailable when hooks are disabled or untrusted; report that limit.
