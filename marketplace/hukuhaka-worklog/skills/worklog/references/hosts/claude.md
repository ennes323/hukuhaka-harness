# Claude Code Worklog adapter

Invoke `/hukuhaka-worklog:worklog setup`, `status`, or `archive` for deterministic
commands. Trusted UserPromptSubmit hooks handle exact command prompts and report
the result without model work. Other requests use the shared recording procedure.
If the native Skill expansion reaches the model instead, execute the bundled
script with the explicit Claude adapter and report its observed result:

`python3 <this-skill>/scripts/worklog.py --host claude --root <project> setup`

Use `status` or `archive` in place of `setup` for those operations. Setup updates
the existing root CLAUDE.md when present; otherwise it uses AGENTS.md and does
not create CLAUDE.md. Claude Code 2.1.281 or later is required for the supported
AGENTS.md route. Existing local AGENTS.md rules are imported when updating a
CLAUDE.md that does not already import them. All unmanaged text and existing
Worklog records are preserved; ancestor instruction loading remains host-owned.

Native hooks explicitly use `--host claude` and
CLAUDE_PLUGIN_ROOT/CLAUDE_PLUGIN_DATA. PreToolUse pairs with PostToolUse or
PostToolUseFailure so a tool that changes history and then fails still archives.
Plan mode, read-only calls, missing Worklog files, and unmatched pairs do not
archive. Calls rejected before execution or interrupted without a post event
leave a snapshot that expires after 24 hours. The shared archive core serializes
writes and preserves concurrent edits. Hooks are silent on success and report
archive failures without blocking tools. Disabled or untrusted hooks cannot
provide automation; the same bundled manual archive command remains available.
