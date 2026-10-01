# Installation and management

[Back to the overview](README.md)

## Install or update

Use the [interactive commands in the README](README.md#interactive-install) to
review the component selection before applying it. Rerunning the remote command
uses the latest published release. Running from a clone uses that clone's files;
update the checkout to the intended release first.

For Codex, when a checkout installs plugins, the installer switches an existing official
remote or local marketplace registration to that checkout. If switching fails,
it attempts to restore the previous local path or exact remote revision before
reporting the failure. Unrecognized remote sources remain conflicts. Keep the
checkout available while it is registered as the local marketplace. Claude Code
uses a durable owned source copy in its config directory; an existing registration
pointing to another source remains a conflict.

The picker starts with the detected installed components, or the recommended
set for a new installation. Review the final set when updating.

For a specific published release, replace `X.Y.Z` with its version:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/hukuhaka/hukuhaka-harness/main/scripts/install.sh)" -- --version X.Y.Z
```

The bootstrap downloads the selected release and checks its VERSION. In a local
clone, `--version` checks the source version; it does not switch Git revisions.

## Automation

From a checkout, choose the host explicitly:

```bash
./scripts/install.sh codex install --recommended --dry-run
./scripts/install.sh codex install --recommended --yes
./scripts/install.sh claude install --recommended --yes
./scripts/install.sh paseo install --recommended --dry-run
```

Without a clone:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/hukuhaka/hukuhaka-harness/main/scripts/install.sh)" -- codex install --recommended --yes
```

`--yes` skips confirmation. `--dry-run` previews without writing files or running
mutating host commands. Use `--help` at each command level for accepted options.
Do not pipe the script into `bash` for an interactive installation: the pipe
occupies stdin and prevents keyboard input.

## Choose components

`--recommended` selects catalog defaults. `--components` specifies the
**complete desired managed set**, not components to add to the current set.
For example, this selects only the global guidance and Worklog:

```bash
./scripts/install.sh codex install --components agents-md,hukuhaka-worklog --dry-run
./scripts/install.sh codex install --components agents-md,hukuhaka-worklog --yes
```

Previously managed native-host components omitted from the set are removed. Edited managed
agent files are preserved as conflicts. See the [component table](README.md#included-components)
and [catalog](components.json) for names and recommended defaults. Paseo profile
omissions follow the [profile ownership rules](#paseo-profile-management).

## Reset or uninstall

```bash
./scripts/install.sh codex reset --recommended --include-template --dry-run
./scripts/install.sh codex reset --recommended --include-template --yes
./scripts/install.sh codex uninstall --dry-run
./scripts/install.sh codex uninstall --yes
```

Reset rebuilds the selected managed components. `--include-template` includes
the managed global instruction block in that reset. Uninstall removes managed
components; it does not reset independent Codex settings or re-enable subagents.
Unrelated plugins, configuration, and guidance outside managed blocks are preserved.
Review reported conflicts before using `--force` to authorize replacement.

Install, reset, and uninstall check managed agent and instruction files before
changing plugins. A detected file conflict leaves the plugins in place. Failures
during later CLI operations can still leave a partial result; successful earlier
components are not rolled back as a group.

## Installer records and recovery

The installer announces and maintains `hk-config.toml` in the Codex home
(`~/.codex` by default). This file is only for Hukuhaka installation management.
It records component versions, ownership receipts, installer versions, timestamps,
completed steps, and failure stages. It is not a Codex runtime configuration.
The most recent 50 finished operations are retained; error records contain a
stage and error type, not raw command output.

```bash
./scripts/install.sh codex state show
./scripts/install.sh codex state show --json
./scripts/install.sh codex state recover --dry-run
./scripts/install.sh codex state recover --yes
```

Validated legacy agent and guidance manifests are backed up under `hk-backups/`
and moved into the central record during component operations. The migration
and component file changes share a file transaction. Existing instruction block
markers remain necessary to distinguish managed text from your own text.
Independent settings and policy restoration records are preserved.

`state show` reads recorded state; it does not verify the current installed files.
New operations record partial failures and mark abandoned attempts as interrupted.
If interrupted file transactions remain, `state recover` announces and replays
them, including their affected component files. Otherwise, it restores only
`hk-config.toml.bak`, preserving the replaced record under `hk-backups/` and
leaving component files and Codex settings unchanged. Use `--dry-run` to inspect
the pending recovery action. Rerun installation to check the restored receipts
against actual files.
Malformed legacy receipts and conflicting user files still require review; a
record backup does not establish ownership of unknown files.

### Cleanup of older installations

The retired `project-doc-reader` cannot be selected or installed. On the next
install, reset, or uninstall, the installer removes only its agent and resources
recorded as managed, after checking their hashes. Edited files remain conflicts
until you review them and authorize replacement with `--force`. Unmanaged and
user-owned files are preserved. Older receipts listing fewer helper resources
are also supported.

If the global instruction receipt remains but its block is absent, installing
`agents-md` restores the block without replacing your text. Removing it clears
the stale receipt. Incomplete or edited blocks remain conflicts.

## Claude Code management

Claude uses `CLAUDE_CONFIG_DIR` (`~/.claude` by default) for managed records,
backups, the global `CLAUDE.md` block, and a durable owned marketplace source at
`plugins/hukuhaka-plugin`. The native marketplace name stays `hukuhaka-plugin`.
The installer supports `install`, `reset`, `uninstall`, `state show`, and
`state recover`, with the same dry-run and desired-set conventions as Codex:

```bash
./scripts/install.sh claude install --components claude-md,hukuhaka-worklog --dry-run
./scripts/install.sh claude reset --recommended --include-template --dry-run
./scripts/install.sh claude uninstall --dry-run
./scripts/install.sh claude state show --json
./scripts/install.sh claude state recover --dry-run
```

`claude-md` installs a managed block and preserves text outside it. Validated
legacy whole-file receipts migrate to block ownership. Edited legacy content is
a conflict; the installer does not append duplicate instructions. Existing
retired bridge files and their entries are retained, and no bridge is shipped.
Unknown files remain user-owned. Codex Worker, Result Runner, Evidence Scout,
and global visualization guidance are unavailable for Claude Code.

Claude settings support only `model`, `effortLevel`, `language`, and
`autoMemoryEnabled`. Changes are explicit; there is no recommended Claude
settings profile. Use `claude settings show`, `set`, `unset`, `apply`, `diff`,
`export`, `history`, or `restore` through the installer to inspect a plan and
manage the selected keys. Plugin installation preserves execution settings.

## Paseo profile management

Paseo is an independent installer target for saved profiles. Enable its section
explicitly in the terminal picker, or name it in a command. All seven profiles
are recommended when that section is enabled:

| Profile | Provider | Model | Mode | Reasoning | Intended work |
|---|---|---|---|---|---|
| `advisor-gpt` | Codex | `gpt-6-astra` | `auto-review` | `high` | Independent advice |
| `advisor-claude` | Claude Code | `claude-opus-5-5` | `default` | `high` | Independent advice |
| `worker` | Codex | `gpt-6.1-sol` | `auto-review` | `high` | Implementation and investigation |
| `scouter` | Codex | `gpt-6-luna` | `auto-review` | `xhigh` | Bounded source lookup; Fast mode enabled |
| `designer` | Claude Code | `claude-opus-5-5` | `default` | `high` | UI/UX and interface design |
| `writer` | Antigravity | `gemini-3.8-flash-high` | `default` | In model ID | Meaning-preserving editing proposals |
| `vision` | Codex | `gpt-6.1-sol` | `auto` | `high` | Visual inspection |

```bash
./scripts/install.sh paseo status --json
./scripts/install.sh paseo state recover --dry-run
./scripts/install.sh paseo install --recommended --dry-run
./scripts/install.sh paseo install --recommended --yes
./scripts/install.sh paseo install --components worker,scouter --dry-run
./scripts/install.sh paseo reset --recommended --dry-run
./scripts/install.sh paseo uninstall --dry-run
```

Applying profiles requires Paseo 0.10.2+, Node.js 22+, and npm. The first
approved apply installs pinned `@getpaseo/client` 0.10.2 under the selected
`PASEO_HOME/hk-runtime/paseo-sdk-0.10.2` using `npm ci --ignore-scripts`.
The preview discloses this local runtime dependency. It is not installed globally.
The initial transport supports a local loopback TCP daemon; remote and Unix
socket connections are unavailable.
Tested with Paseo 0.10.2; later versions are accepted but unverified.

`status` and `state show` inspect local saved profiles and management records
without requiring a running daemon. Dry runs also work offline and show
validation gaps without downloads or writes. Profile create/update requires a
supported Paseo CLI, a reachable daemon, and SDK validation of the exact
provider, model, mode, reasoning, and feature values before profiles change.
Unchanged adoption and retention confirm UUIDs online without requiring model
availability; their saved fields remain intact. The SDK reads configuration;
the native CLI applies profile changes.
Unavailable models block the affected profile; valid independent profiles may
proceed with a partial result. No substitute is selected. Scouter's
Fast mode requests priority processing and increases usage.

Missing configuration reports an empty saved-profile snapshot; malformed
configuration or ownership receipts fail inspection without implicit repair.
`state recover` recovers only pending receipt transactions or a valid receipt
backup after preview and confirmation. It refuses transactions targeting the
Paseo configuration and never restores profiles or `config.json`. Review the
records and rerun status or installation after recovery.
An interrupted profile write can leave a receipt marked `pending apply`.
This records UUID ownership without claiming the daemon has applied the saved
values. Ownership receipts are recorded before native profile writes, so a
failed write does not leave a created UUID unowned. The next installation
reconciles saved and live profiles; a pending receipt triggers reload only when
those snapshots differ. The installer verifies application before completing
the receipt. Retry after inspecting status; it never blindly restores the
shared configuration after a failed write or verification.

`--components` is the **complete desired managed profile set**. The preview
includes omitted profiles: unchanged installer-created profiles are removed;
edited ones are retained and released from management. Adopted
profiles are retained and released from management. Unmanaged profiles are
preserved. Normal updates preserve a changed managed profile as a whole local
override. Explicit `reset` or `--force` authorizes replacing that override.
Paseo has no instruction-template reset or host-settings operation.

An existing profile is adopted only through an explicit role-to-UUID mapping.
Use the terminal picker's separate adoption review, or specify each mapping:

```bash
./scripts/install.sh paseo install --recommended --adopt advisor-gpt=EXISTING_UUID --dry-run
./scripts/install.sh paseo install --recommended --adopt advisor-gpt=EXISTING_UUID --rename-adopted advisor-gpt --dry-run
```

Replace `EXISTING_UUID` with the exact ID shown by `status`. Review the UUID and
profile fields before applying. The terminal adoption path confirms adoption
separately before the installation confirmation. Each UUID maps to at most one
role, and each role maps to at most one UUID. Adoption preserves all saved
fields by default. `--rename-adopted ROLE` explicitly changes only the name and
notes to the role template; for an existing `advisor`, this opts into the
`advisor-gpt` name and briefing while preserving its model, mode, and effort.
Adopt `worker`, `scouter`, `designer`, `writer`, and `vision` unchanged through
their UUIDs. Selecting `advisor-claude` creates it if absent; no name-based
adoption occurs. Adopted profiles survive uninstall.

The installer uses Paseo's native profile API and verifies saved results.
Do not edit Paseo profiles while applying; the native API has no conditional
update. A reread detects observed changes before mutation, and verification
detects unexpected results after it; this does not guarantee concurrent-write
protection. New profile selections and newly created agents use the saved
defaults. Existing agents retain their launch configuration.

The optional `hukuhaka-paseo` plugin is installed separately for Codex or Claude
Code by adding it to that host's complete desired component set. It uses the
upstream Paseo Skills and adds role briefings, not runtime enforcement. Installing
Paseo profiles never installs that plugin, upstream Skills, providers, or the app.

## Settings and profiles

Run `codex settings` through the installer to review saved settings or apply a
profile. For individual changes and other operations:

```bash
./scripts/install.sh codex settings
./scripts/install.sh codex settings show --json
./scripts/install.sh codex settings set model_reasoning_effort high --dry-run
./scripts/install.sh codex settings unset model_reasoning_effort --dry-run
./scripts/install.sh codex settings diff --recommended
./scripts/install.sh codex settings apply --recommended --dry-run
./scripts/install.sh codex settings export personal.toml
./scripts/install.sh codex settings diff --file experiment.toml
./scripts/install.sh codex settings apply --file experiment.toml --dry-run
./scripts/install.sh codex settings history
./scripts/install.sh codex settings restore RECEIPT --dry-run
./scripts/install.sh codex settings organize --dry-run
```

Settings are listed with descriptions, accepted values, and harness
recommendations. `show --json` also reports where values come from, their limits,
and official defaults when known. Saved values may differ from overrides in a
running app or task.

Replace `--dry-run` with `--yes` to apply a reviewed change. Export creates a new
file and refuses to overwrite one. Profiles are partial TOML files containing
catalog keys and JSON-style strings, booleans, integers or string arrays; literal
and multiline strings are also accepted. Table sections and dotted keys are
supported. Unknown keys, duplicates and unsupported syntax are rejected.

For example, an experiment profile can contain just:

```toml
model_reasoning_effort = "high"
model_verbosity = "medium"
```

Omitted keys are preserved. `unset` removes an explicit override; it does not
apply a recommended value. Recommendations are harness preferences, not measured
optimal values or official model defaults. Model, context limits, child model
pins and advanced environment/security settings are preserved by the recommended
profile. Its three agent switches explicitly enable V1 and V2; installing components
does not apply this profile. Model-specific value support remains host-dependent.

Each applied change records the touched keys and their previous values in
`$CODEX_HOME/.hukuhaka-settings-history/`, with a private full-config backup.
Restore changes only those keys and refuses conflicts with later edits. Direct
edits are supported and shown as unrecorded or changed since the last receipt;
profiles are never reapplied automatically. `organize` reorders root assignments
and whole tables while preserving values and comments. Formatting-only receipts
have backups but no key changes to restore automatically. Array tables are not
reordered. Keep exports and backups private; they may contain personal instructions.

All writes use the existing installer lock, transaction recovery and Codex config
load validation. A failed validation rolls back the write. Dry runs do not
acquire a lock or create state. Successful loading does not prove that a running
session reloaded settings or that a model supports a requested context capacity.

V1 `features.multi_agent`, `agents.enabled`, and V2
`features.multi_agent_v2.enabled` are displayed separately: enabled V2 takes
precedence over `agents.enabled`. V1 nesting depth is ignored by V2. The three V2
wait settings accept 0–3600000 milliseconds; the public schema does not state
their defaults. Explicit values must satisfy minimum ≤ default ≤ maximum.
The recommended minimum/default are 120000 ms. Notifications can return early;
these waits do not limit command or child execution duration.

This interface manages saved configuration, not the entire agent runtime.
Role-file model/effort pins and spawn-call arguments are separate inputs;
`fork_turns` is a V2 spawn argument, not a global settings key. Full-history
forks and explicit model overrides have different inheritance rules. Actual
child model, permissions and tool availability must be established from the
active host or execution evidence. Enabling switches neither forces delegation
nor changes instruction-based delegation policy. See the official
[subagent guide](https://learn.chatgpt.com/docs/agent-configuration/subagents).

`configure` is a compatibility spelling for the settings wizard, and
`configure --recommended` uses the same recommended profile. Existing `context`
and `agents` commands retain their scoped ownership and reset safeguards. Old
policy manifests are preserved; an edit through `settings` can make an old
policy drift, in which case its legacy reset refuses to proceed rather than
discarding that edit. Use settings receipts to restore new changes. Experimental context
management, app internals, MCP credentials and project trust lists are outside
the catalog and are preserved.

## Optional Codex agents

Component installs, updates and optional-agent reinstalls preserve execution
settings. Installing role files does not enable agent tools.

With subagents disabled, Report Planner's delegated construction is unavailable.
Project Docs has direct context and documentation-impact paths that require no
index; bounded direct workflows have been exercised, while broader routing
acceptance remains pending.

Optional component names are `astra_worker` (Sol medium Worker), `result-runner`
(Luna xhigh), and `evidence-scout` (Luna xhigh, read-only). The retired
`project-doc-reader` name is reserved for ownership-checked cleanup of existing
installations and is rejected as a selectable component. Worker retains its
historical identifier for compatibility.
The global template provides general delegation guidance; agent files define
specialist roles and their boundaries. Installing roles does not add routing
instructions to the template. Upgrades remove unchanged legacy routing blocks;
edited legacy blocks are reported as conflicts.

The following compatibility commands remain available:

```bash
./scripts/install.sh codex configure
./scripts/install.sh codex configure --recommended --dry-run
./scripts/install.sh codex context
./scripts/install.sh codex agents
./scripts/install.sh codex agents set --max-concurrent 4 --max-depth 1 --dry-run
./scripts/install.sh codex agents reset --dry-run
./scripts/install.sh codex agents model inspect
./scripts/install.sh codex agents model inherit --dry-run
```

Context and agent commands without an action open a terminal wizard. Agent
capacity changes do not enable subagents. `model inspect` reports saved settings;
`model inherit` removes only the two global child model/effort overrides,
preserving parent settings and role pins. Replace `--dry-run` with `--yes` to
apply a reviewed change. See [Settings and profiles](#settings-and-profiles) for
notification waits, runtime limits, and the recommended profile; review the
wizard's plan before applying it.

## Native plugin installation

To manage plugins directly through Codex:

```bash
codex plugin marketplace add hukuhaka/hukuhaka-harness
codex plugin add hukuhaka-report-planner@hukuhaka-harness
codex plugin add hukuhaka-engineering-plan@hukuhaka-harness
codex plugin add hukuhaka-worklog@hukuhaka-harness
codex plugin add hukuhaka-uiux-foundation@hukuhaka-harness
```

Optional plugins use the same form with `hukuhaka-memory-audit` or
`hukuhaka-project-docs`. Native plugin commands do not install the harness's
global AGENTS.md template, optional role files, or installer-managed settings.
Start a new Codex task after installing or updating plugins to reload discovery
and hook state.

Claude Code native installation:

```bash
claude plugin marketplace add hukuhaka/hukuhaka-harness
claude plugin install hukuhaka-worklog@hukuhaka-plugin --scope user
claude plugin install hukuhaka-engineering-plan@hukuhaka-plugin --scope user
```

All seven plugins use this namespace. Native plugin commands do not install the
managed global template. Restart the affected host to rediscover packages and
hooks. Package availability and deterministic checks do not establish a live
workflow verdict; Claude requires its own isolated workflow evidence.

## Troubleshooting

- **Terminal required:** use the interactive `bash -c` command in a terminal,
  or an explicit `codex install` or `claude install` command with `--yes` for automation.
- **Host not detected:** ensure the selected `codex` or `claude` CLI is available on PATH in that terminal.
- **Version mismatch:** use a matching checkout or the remote bootstrap for
  the requested version; `--version` does not update a local clone.
- **Managed-file conflict:** review the reported file and backup before
  authorizing replacement. Do not remove unrelated configuration to retry.
- **Partial installation:** retain the error output, resolve the named cause,
  and rerun the same desired-set command. Repeated installation/removal is
  designed to be idempotent.

For a downloaded checkout, `scripts/validate.sh --profile public` checks package
and document consistency. `scripts/validate.sh --live-cli` is a separate,
isolated lifecycle check requiring an installed Codex CLI and local model cache.
`scripts/validate.sh --live-claude-cli` separately exercises the actual installed
Claude CLI in temporary HOME and CLAUDE_CONFIG_DIR directories. It requires
Claude Code 2.1.281+, performs native package lifecycle commands, and makes no
model or authentication calls. Native registration keys may change; unrelated
settings, personal guidance, agents, and retained plugin data must be preserved.
The default profiles use deterministic/fake CLI tests and do not run this check.
Neither native lifecycle check establishes a model workflow or output-quality
verdict. These checks are not prerequisites for ordinary installation.
