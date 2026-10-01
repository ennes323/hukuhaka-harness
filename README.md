# hukuhaka-harness

Reusable Codex and Claude Code workflows for engineering plans, project maintenance, and UI/UX work, with optional Paseo delegation profiles.

## Install

Requires macOS or Linux, Python 3.9+ as `python3`, and the CLI for your selected target (`codex`, `claude`, or `paseo`).
Remote installation also requires `curl`. Native Windows and WSL are outside
the tested support matrix.

### Interactive install

From a clone:

```bash
./scripts/install.sh
```

From the public repository:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/hukuhaka/hukuhaka-harness/main/scripts/install.sh)"
```

The remote command downloads the latest release, asks which host to manage,
and opens that host’s component picker.
Use `bash -c` so the terminal remains available for keyboard input.
Review the selected components and installation plan before confirming.

For automation from a checkout:

```bash
./scripts/install.sh codex install --recommended --yes
./scripts/install.sh claude install --recommended --yes
./scripts/install.sh paseo install --recommended --dry-run
```

Component installation preserves your settings, including agent switches.
Use `./scripts/install.sh codex settings` to review settings and profiles.
Each installer section is enabled explicitly. Paseo manages saved delegation
profiles; it does not install provider CLIs, native plugins, or the Paseo app.

See [installation and management](INSTALL.md) for updates, removal, selected
components, native plugin installation, settings, and troubleshooting.

## Included components

Recommended installs include Worklog and the selected host’s managed global
guidance template. All seven plugins have native Codex and Claude Code packages.
Project Docs remains experimental / opt-in on both hosts.

| Component | Version | Status | What it provides |
|-----------|---------|--------|------------------|
| **hukuhaka-report-planner** | <code>0.8.1</code> | Optional | Research sources and plan document content; delegate design and construction when requested. |
| **hukuhaka-engineering-plan** | <code>0.3.1</code> | Optional | Inspect the repository and plan implementation steps and checks. |
| **hukuhaka-worklog** | <code>0.5.1</code> | Recommended | Track project progress and decisions; archive older history automatically. |
| **hukuhaka-uiux-foundation** | <code>0.1.2</code> | Optional | Guide interface design, implementation, and usability reviews. |
| **hukuhaka-memory-audit** | <code>0.2.1</code> | Optional | Review host memory for outdated, duplicate, or overly specific notes. |
| **hukuhaka-project-docs** | <code>0.2.1</code> | Experimental / opt-in | Find project documents in Codex and Claude Code and review needed updates, with or without an index. |
| **hukuhaka-paseo** | <code>0.1.0</code> | Optional | Brief and coordinate bounded Paseo roles through the upstream Paseo Skills; Main retains decisions and integration. |
| **AGENTS.md template** | — | Recommended for Codex | Managed global guidance; preserves content outside its block. |
| **CLAUDE.md template** | — | Recommended for Claude Code | Managed global guidance; preserves content outside its block. |
| **Worker** | — | Optional, Codex | Sol medium agent for implementation, investigation, and review. |
| **Result Runner** | — | Optional, Codex | Luna xhigh agent for running supplied commands and reporting results. |
| **Evidence Scout** | — | Optional, Codex | Luna xhigh agent for read-only source lookup. |

The optional agents and Report Planner's delegated construction require subagent
support enabled in your host. Installing role files alone does not enable it.
Project Docs can also maintain its optional documentation index.

Plugin versions are independent of the [repository release](CHANGELOG.md).

Paseo's separate section selects all seven profiles by default when enabled:
`advisor-gpt`, `advisor-claude`, `worker`, `scouter`, `designer`, `writer`, and
`vision`. These are saved profiles rather than native plugin ports. Existing
profiles require explicit UUID adoption; matching names alone confer no ownership.
Scouter enables Fast mode, which uses priority processing and increases usage.
See [Paseo profile management](INSTALL.md#paseo-profile-management) for models,
adoption, preservation, and removal.

## Use

Start a new task in your selected host after installation so newly installed skills and hooks
can be discovered. Invoke the workflow you need:

Codex:

```text
$hukuhaka-report-planner
$engineering-plan
$hukuhaka-worklog:worklog
```

Claude Code:

```text
/hukuhaka-report-planner:hukuhaka-report-planner
/hukuhaka-engineering-plan:engineering-plan
/hukuhaka-worklog:worklog
```

Claude Code uses its native plugin artifact designer. Worker, Result Runner,
Evidence Scout, and the global visualization guidance are Codex-only.
Memory Audit in Claude Code uses native memory warnings and manual invocation;
it does not install a Codex memory-pressure hook.

If you select the optional `hukuhaka-paseo` plugin for Codex or Claude Code,
invoke `$hukuhaka-paseo` or `/hukuhaka-paseo:hukuhaka-paseo` respectively.
Install the upstream Paseo Skills separately if needed; this installer does not
install personal plugins automatically. The Skill adds task briefings and
coordination guidance, without enforcing role behavior at runtime.

Report planning creates a content-only
`.hukuhaka/reports/<short-name>/spec.md`. Engineering planning inspects the
repository and defines the implementation and verification needed for the task.
Worklog maintains `.hukuhaka/work.md` and `.hukuhaka/changelog.md`.

## Releases and support

- [Release notes](CHANGELOG.md) describe changes and known limitations.
- [GitHub releases](https://github.com/hukuhaka/hukuhaka-harness/releases) provide published versions.
- [Installation guide](INSTALL.md) covers supported commands and recovery.
- [Issues](https://github.com/hukuhaka/hukuhaka-harness/issues) are the place to report problems. Include the harness version, OS, command, and redacted error.

Licensed under [MIT](LICENSE).
