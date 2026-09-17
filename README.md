# hukuhaka-harness

Reusable Codex workflows for engineering plans, project maintenance, and UI/UX work.

## Install

Requires macOS or Linux, Python 3.9+ as `python3`, and the Codex CLI.
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

The remote command downloads the latest release and opens the component picker.
Use `bash -c` so the terminal remains available for keyboard input.
Review the selected components and installation plan before confirming.

For automation from a checkout:

```bash
./scripts/install.sh codex install --recommended --yes
```

Component installation preserves your settings, including agent switches.
Use `./scripts/install.sh codex settings` to review settings and profiles.
When subagents are unavailable, Report Planner's delegated construction and
explicit Project Doc Reader delegation remain unavailable; installing role
files alone does not enable them. Project Docs can directly find governing
documents and review documentation impact without a Reader or an index.

See [installation and management](INSTALL.md) for updates, removal, selected
components, native plugin installation, settings, and troubleshooting.

## Included components

Recommended installs include Worklog and the managed global working guidance template.

| Component | Version | Status | What it provides |
|-----------|---------|--------|------------------|
| **hukuhaka-report-planner** | <code>0.8.0</code> | Optional | Evidence-backed document content planning; delegated construction requires available subagents. |
| **hukuhaka-engineering-plan** | <code>0.3.0</code> | Optional | Repository-grounded engineering plans. |
| **hukuhaka-worklog** | <code>0.5.0</code> | Recommended | Working memory, checkpoints, and automatic history archiving. |
| **hukuhaka-uiux-foundation** | <code>0.1.1</code> | Optional | Design foundations and rendered UI verification. |
| **hukuhaka-memory-audit** | <code>0.2.0</code> | Optional | Evidence-based review of Codex memory. |
| **hukuhaka-project-docs** | <code>0.2.0</code> | Experimental / opt-in | Codex project context, documentation impact, and optional index maintenance. |
| **AGENTS.md template** | — | Recommended | Managed global guidance; preserves content outside its block. |
| **Worker** | — | Optional | Sol medium role files; execution depends on host capabilities and settings. |
| **Result Runner** | — | Optional | Luna xhigh command-runner files; execution depends on host capabilities and settings. |
| **Evidence Scout** | — | Optional | Luna xhigh read-only lookup files; execution depends on host capabilities and settings. |
| **Project Doc Reader** | — | Experimental / opt-in | Codex read-only role files; execution depends on host capabilities and settings. |

Plugin versions are independent of the [repository release](CHANGELOG.md).

## Use

Start a new Codex task after installation so newly installed skills and hooks
can be discovered. Invoke the workflow you need:

```text
$hukuhaka-report-planner
$engineering-plan
$hukuhaka-worklog:worklog
```

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
