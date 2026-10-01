# Claude Code memory adapter

Use the current session's memory instructions or native `/memory` view to locate
the actual auto-memory directory. Do not guess a project-key encoding or assume
the default directory when `autoMemoryDirectory` or provider configuration
changes it. Distinguish auto-memory from user/project CLAUDE.md, AGENTS.md, and
rules: instruction-file changes require their own authorized scope.

Claude native auto-memory contains an editable MEMORY.md index and topic files.
Unlike generated Codex memory, these Markdown files are a supported edit surface.
Review the index and the relevant topic files, preserve exact references and
frontmatter meaning, and exclude transcripts and other evidence from edits.

After approval of the exact proposal, re-read the approved files and apply only
that change set through native file tools. Preserve unrelated changes and stop
the dependent edit if content drift invalidates the approved proposal. Update
index links when an approved topic change requires it, then re-read affected
files to verify the observed result. Report successful file edits separately
from whether a new session has loaded the updated memory.

No custom Claude memory-pressure hook is installed. Claude Code already checks
MEMORY.md after writes against its native 200-line and 25 KB loading limits,
reminds the model near the limit, and reports an over-limit write as an error
while retaining that write. Treat native size feedback as a review trigger;
this Skill's approval gate still applies to cleanup. Native feedback does not
measure topic-file quality or guarantee full index loading.

Source: [Claude memory](https://code.claude.com/docs/en/memory).
