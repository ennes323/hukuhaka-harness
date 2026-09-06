# hukuhaka-harness

A small distribution of coding-agent workflows for Claude Code and Codex. Each
component declares its supported host explicitly; sharing a repository does not
imply that a Claude Code plugin is portable to Codex.

## Who this is for

- You use Claude Code, Codex, or both and want reusable workflows with honest host boundaries.
- You want evidence-backed document planning to constrain artifact construction.
- You need a Claude-to-Codex collaboration harness without pretending it is a native Codex plugin.

## What's in the bundle

| Component | Version | Status | Hosts | What it gives you |
|-----------|---------|--------|-------|-------------------|
| **hukuhaka-report-planner** | `0.6.0` | Supported | Claude Code, Codex | Frames and structures visual-document requests, directs source-backed anchor construction, and records a finalized `spec.md`. Explicit plan requests stop there; artifact requests delegate construction and visual verification to one designer subagent. |
| **hukuhaka-engineering-plan** | `0.2.2` | Supported | Claude Code, Codex | Produces repository-grounded implementation plans with closed impact surfaces, exact change deltas, and requirement-to-verification mapping. |
| **hukuhaka-worklog** | `0.4.0` | Supported | Claude Code, Codex | Reads current work at the first non-trivial project task, tracks lifecycle changes from natural requests, records completed or closed outcomes, keeps the newest 25 history entries automatically, and runs setup, status, and recovery archive commands before model invocation. |
| **hukuhaka-memory-audit** | `0.1.0` | Supported | Codex only | Audits local Codex memory against current engineering evidence and suggests cleanup once the always-loaded summary or supporting store crosses a review threshold. |
| **hukuhaka-codex** | `0.4.1` | Supported | Claude Code only | Claude Code plugin that delegates planning, review, debate, and transfer work to the Codex runtime. It is not installed into Codex itself. |
| **CLAUDE.md template** | — | Supported | Claude Code only | Shared scoped-change and verification policy with Claude-specific `spec.md` sign-off and attribution-free commits, deployed to `~/.claude/CLAUDE.md`. |
| **AGENTS.md template** | — | Supported | Codex only | Codex policy for grounded responses to user challenges, scoped change previews, evidence-backed verification, compact-resilient task state, and a safe local Git lifecycle, merged into `$CODEX_HOME/AGENTS.md`. |
| **Evidence Scout** | — | Supported | Codex only | Installs a Luna max, read-only custom agent plus compact routing guidance for dynamic parallel repository exploration while the primary retains decisions, writes, and final verification. |

## Install

The public installer detects Claude Code and Codex, shows only the hosts that
are installed, and applies each selected host independently. Automation always
names exactly one host; there is no implicit default host or `both` command.

### Requirements and support

| Requirement | Support contract |
|-------------|------------------|
| Operating system | macOS or Linux |
| Python | Python 3.9+ available as `python3`; Python 2 is unsupported |
| Bootstrap | `bash` and `curl` for remote installation |
| Claude Code host | `claude` CLI |
| Codex host | `codex` CLI |
| Windows | Native Windows is unsupported; WSL is not yet part of the tested matrix |

The installer uses only the Python standard library. If `python3` is missing,
the bootstrap prints the appropriate package-manager command.

Claude Code deployment is transactional: registry JSON is validated before
files change, writes are atomic, interrupted runs are recovered on the next
install, and locally modified managed files require an explicit `--force`.

The Claude and Codex instruction templates are separate sources. Both
distinguish analysis from mutation authority, preserve pre-existing work, and
keep push and other external actions explicitly opt-in. The Claude template
additionally protects `spec.md` contracts and attribution-free commits. The
Codex installer merges only a marked managed block into
`$CODEX_HOME/AGENTS.md`, preserves user text outside that block, and removes
only the managed block on uninstall. `CODEX_HOME` defaults to `~/.codex`.

### Interactive install

```bash
# From a clone:
./scripts/install.sh

# From the public repository:
bash -c "$(curl -fsSL https://raw.githubusercontent.com/hukuhaka/hukuhaka-harness/main/scripts/install.sh)"
```

The installer uses an arrow-key terminal selector on standard input/output:
Up/Down moves, Space selects, and Enter applies. It detects the `claude` and
`codex` CLIs and shows only available hosts. A component checkbox is the final
desired state: selected managed components are installed or updated and
unselected installed components are removed. Each host can reset managed
plugins and skills before installing; template reset remains a separate
choice. Claude is applied before Codex, and an independent Codex operation is
still attempted if Claude fails.

Plugin checkboxes show the target plugin version from the selected host
manifest. Before confirmation, the installation plan compares each selected
plugin's currently registered version with that target. Templates and features
remain unversioned.

Codex also offers an opt-in `Configure global Codex defaults` choice. It is
unchecked by default. Selecting Evidence Scout applies only its required
multi-agent enablement; it does not change agent concurrency, nesting, the primary
model, model catalog, or unrelated agent defaults. Reset and uninstall preserve
those runtime settings, memory, and unrelated Claude settings. Updating a
schema-v2 Evidence Scout install removes only its manifest-owned obsolete Luna
catalog and exact config pointer.

The interactive command uses `bash -c` so stdin remains attached to the
terminal. `curl ... | bash` remains supported for explicit non-interactive
flags, but cannot accept arrow-key input because the script itself occupies
stdin.

Without a TTY, a zero-argument run exits with guidance and changes nothing.
If neither host CLI is installed, the interactive installer also changes
nothing and exits nonzero.

### Claude Code

For automation, `--recommended` selects supported catalog defaults and
`--components` declares the complete desired component state:

```bash
./scripts/install.sh claude install --recommended --yes
./scripts/install.sh claude install \
  --components hukuhaka-report-planner,hukuhaka-engineering-plan,hukuhaka-worklog,hukuhaka-codex,claude-md \
  --yes
./scripts/install.sh claude reset --recommended --include-template --yes
./scripts/install.sh claude uninstall --yes
```

The installer honors `CLAUDE_CONFIG_DIR`, verifies the resulting user plugins
through `claude plugin list --json`, and rolls back the Claude transaction if
the native version, enabled state, or install path does not match. Run
`/reload-plugins` in an existing Claude Code session after a successful update.

### Codex

Codex has the same component lifecycle:

```bash
./scripts/install.sh codex install --recommended --yes
./scripts/install.sh codex reset --recommended --include-template --yes
./scripts/install.sh codex uninstall --yes
```

`--recommended` includes Evidence Scout. The same install creates
`$CODEX_HOME/agents/evidence-scout.toml`, merges a separately owned routing
block into `$CODEX_HOME/AGENTS.md`, and enables multi-agent execution. It leaves
agent concurrency and nesting under user control and leaves `models_cache.json`
untouched and relies on Codex's native Luna subagent support; it does not create
or select a model catalog. Codex uses one scout per genuinely independent
read-only scope and may use fewer than the configured capacity. An
existing byte-identical personal scout is adopted; a conflicting unmanaged
agent file is preserved unless `--force` is explicit. User-owned model-catalog
pointers are always left unchanged.
If `$CODEX_HOME/AGENTS.override.md` exists, Codex gives it precedence over the
global `AGENTS.md`; installation succeeds but warns that scout routing is
inactive until that override is removed or carries equivalent routing guidance.

Remote installs keep the marketplace pinned to the resolved harness release.
When the same official Git marketplace is registered at an older release, the
installer replaces that ref automatically and restores the previous commit if
the update fails. Local, forked, and otherwise different sources are preserved
and rejected instead of being repointed.

Remote automation passes the same host-first arguments:

```bash
curl -fsSL https://raw.githubusercontent.com/hukuhaka/hukuhaka-harness/main/scripts/install.sh \
  | bash -s -- codex install --recommended --yes
```

Modified managed files stop replacement unless `--force` is explicitly
supplied. `--dry-run` takes no installer lock, writes no file, and runs no
mutating host command.

The equivalent native Codex commands are:

```bash
codex plugin marketplace add hukuhaka/hukuhaka-harness
codex plugin add hukuhaka-report-planner@hukuhaka-harness
codex plugin add hukuhaka-engineering-plan@hukuhaka-harness
codex plugin add hukuhaka-worklog@hukuhaka-harness
codex plugin add hukuhaka-memory-audit@hukuhaka-harness
```

The native marketplace command follows the repository state selected by Codex
and is convenient for local development. For a reproducible release-equivalent
install, use `scripts/install.sh`; remote installer runs resolve and pin the
matching `vX.Y.Z` harness tag and restore the previous ref if an update fails.

The Codex marketplace intentionally exposes only the components with native
Codex packaging. Invoke the document planner as `$hukuhaka-report-planner`, the
engineering planner as `$engineering-plan`, and the worklog as
`$hukuhaka-worklog:worklog`. The optional memory audit uses
`$codex-memory-audit`; it is available from the marketplace but is not selected
by `--recommended`. Codex can otherwise select installed Skills from their descriptions.
The `agents-md` template and Evidence Scout are installed by this repository's
host-aware installer rather than the native plugin marketplace.

### Global Codex defaults

```bash
./scripts/install.sh codex configure
./scripts/install.sh codex configure --recommended --yes
```

The configurator edits only global `$CODEX_HOME/config.toml` (default
`~/.codex/config.toml`). It does not set a model and does not change sandbox,
approval, web search, MCP, provider, profile, or project configuration. It
shows a unified diff, preserves unmanaged keys, comments, order, and file mode,
and stores the previous file as `config.toml.hukuhaka-backup`. Unsafe duplicate
managed keys and inline managed tables are rejected before writing. After an
atomic replacement, `codex doctor --json` must report `config.load` as `ok` or
the original file is restored. See the
[Codex configuration reference](https://developers.openai.com/codex/config-reference/).
Evidence Scout installation reuses the same parser, preservation rules, and
`codex doctor` validation for its two multi-agent enablement keys; users do not
need to run `codex configure` separately.

### Codex agent execution policy

```bash
./scripts/install.sh codex agents
./scripts/install.sh codex agents set --max-concurrent 8 --max-depth 1 --yes
./scripts/install.sh codex agents reset --yes
```

Agent capacity is independent from component installation and global defaults.
The interactive installer exposes **Configure agent concurrency & nesting**
under Settings and shows whether the current values are Codex defaults,
Hukuhaka-managed, user-managed, or drifted. A set operation owns only
`agents.max_concurrent_threads_per_session` and `agents.max_depth` through
`.hukuhaka-agent-policy.json`; reset removes only those recorded overrides.
Existing unmanaged values and managed drift fail closed without mutation.
Older Evidence Scout installs that still carry their exact managed ceiling of
four are adopted when their manifest proves the source. The legacy
`agents.max_threads` spelling is normalized during that migration. Codex CLI
currently treats `max_depth` as V1-only and ignores it under V2, so every
interactive and non-interactive set flow displays that warning.

## Report planner workflow

The same skill tree is used by both hosts:

```text
Claude Code: /hukuhaka-report-planner:hukuhaka-report-planner
Codex:       $hukuhaka-report-planner
```

Both write `.hukuhaka/reports/<short-name>/spec.md`, a host-neutral compatibility
contract that either host can consume. Existing `.claude/reports/` plans remain a
read-only fallback. The shared workflow discovers the reader job and evidence, explores
the document structure, directs source-backed anchor construction, then locks a
selective-reference build contract. Explicit planning requests stop at the finalized spec; immediate
artifact requests use it as a preflight and delegate construction plus visual
verification to one designer subagent.

## Engineering plan workflow

The same portable Skill is packaged for both hosts:

```text
Claude Code: /hukuhaka-engineering-plan:engineering-plan
Codex:       $engineering-plan
```

It inspects the repository before planning, defines observable behavior before
file changes, challenges important invariants with concrete counterexamples,
revises contradictions in the main plan, and closes planning with `Ready`,
`Ready with assumptions`, or `Blocked`. Explicit planning-only requests and
Plan mode remain read-only. An authorized implementation request continues
through implementation and required verification once planning and applicable
approval gates are complete; routine assumptions do not add an approval gate.

## Worklog workflow

The same lifecycle Skill and mechanical commands are packaged for both hosts:

```text
Claude Code: /hukuhaka-worklog:worklog <setup|status|archive>
Codex:       $hukuhaka-worklog:worklog <setup|status|archive>
```

The exact setup, status, and archive forms are intercepted by a
`UserPromptSubmit` hook, run the bundled standard-library script, and stop
before model invocation. When both files exist, the managed project instruction
reads `work.md` before the first non-trivial project task in a new session and
loads history only when resuming, completing, closing, or checking a prior
decision. Natural lifecycle changes invoke the model Skill automatically;
analysis, implementation planning, routine one-off edits, and mechanical
commands do not update lifecycle state. Missing files never block automatic
use or get created by the model, while an explicit Worklog request directs the
user to setup. Only the primary agent writes Worklog state. Uncommitted,
staged, or untracked records do not prevent updates: existing notes and
unrelated entries are preserved, and only an item with a conflicting meaning
or user intent is left unchanged. The lifecycle report states whether recording
succeeded, needed no update, or was blocked and why. Setup creates the host-neutral
`.hukuhaka/{work,changelog}.md` files and replaces only its managed block in the
current host's project instruction file (`CLAUDE.md` or `AGENTS.md`). It never
reads or migrates a legacy `backlog.md`.

After a completion or closure, the Skill runs the bundled deterministic archive
operation. It leaves `Recent` unchanged through 25 entries and moves older
entries to monthly `changelog/YYYY-MM.md` files once the count exceeds 25. The
exact `worklog archive` command remains available as an idempotent recovery or
maintenance operation.

After installing the Codex plugin, open `/hooks`, review the worklog hook, and
trust it before using the mechanical commands. Codex skips untrusted plugin
hooks; if an exact command reaches the model, review its trust state and retry
instead of asking the Skill to emulate setup. See
[Review and trust hooks](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks).

Compatibility alias: `$worklog <setup|status|archive>` remains accepted since
`hukuhaka-worklog@0.2.2`, but generated instructions and documentation use the
canonical plugin-qualified identity.

## Codex memory audit

`$codex-memory-audit` inspects the generated files under
`${CODEX_HOME:-~/.codex}/memories/`, verifies drift-prone engineering claims
against current source and runtime evidence, and proposes `KEEP`, `CONDENSE`,
`SUPERSEDE`, or `DELETE` actions. It never hand-edits generated memory files.
Cleanup remains pending until the user approves the exact proposal and a
supported memory-management surface confirms the result.

An optional `SessionStart` hook checks `startup` and `resume` without parsing
memory semantics. It suggests the Skill when `memory_summary.md` reaches 25 KiB
or 200 physical lines, or when `MEMORY.md` reaches 1 MiB or rollout summaries
reach 300 files. The hook emits an English `systemMessage` once per pressure
transition, writes only its suppression state under `PLUGIN_DATA`, and becomes
eligible to warn again after memory returns below the thresholds.

After installing the plugin, open `/hooks`, review the memory-pressure hook,
and trust it if you want the optional suggestion. The Skill itself remains
available even when the hook is untrusted or hooks are disabled.

## Design principles

- **Host support is explicit.** A component is published for a host only when its native package and validation exist.
- **One portable workflow core.** Dual-host components share skill content and keep host-specific manifests at the boundary.
- **Plan before build.** Report framing, figures, and structure are agreed before a separate builder creates the artifact.
- **Idempotent install.** Detect state → install/skip/remove the delta. Re-runs are safe.

## Dependencies

| | Required | Optional |
|--|----------|----------|
| **Base** | Python 3.9+ (`python3`), `bash`; `curl` for remote bootstrap | `git` |
| **Codex host** | `codex` | — |
| **Extras** | — | `brew` (rtk on macOS), `node`/`npx` (ccstatusline) |

The installer's preflight check enumerates these per selected component and offers to auto-install via the detected package manager.

## License

This repository is MIT-licensed except for `marketplace/hukuhaka-codex`, an
Apache-2.0 derivative of OpenAI's Codex plugin for Claude Code. See the root
[LICENSE](LICENSE) and the plugin's `LICENSE` and `NOTICE` files.
