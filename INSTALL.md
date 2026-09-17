# Installation and management

[Back to the overview](README.md)

## Install or update

Use the [interactive commands in the README](README.md#interactive-install) to
review the component selection before applying it. Rerunning the remote command
uses the latest published release. Running from a clone uses that clone's files;
update the checkout to the intended release first.

The picker starts with the detected installed components, or the recommended
set for a new installation. Review the final set when updating.

For a specific published release, replace `X.Y.Z` with its version:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/hukuhaka/hukuhaka-harness/main/scripts/install.sh)" -- --version X.Y.Z
```

The bootstrap downloads the selected release and checks its VERSION. In a local
clone, `--version` checks the source version; it does not switch Git revisions.

## Automation

From a checkout:

```bash
./scripts/install.sh codex install --recommended --dry-run
./scripts/install.sh codex install --recommended --yes
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

Previously managed components omitted from the set are removed. Edited managed
agent files are preserved as conflicts. See the [component table](README.md#included-components)
and [catalog](components.json) for names and recommended defaults.

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

## Settings and profiles

Use one catalog for descriptions, saved values, allowed value shapes and harness
recommendations. `show --json` also includes provenance, explicit bounds and
known official defaults. Unknown defaults stay unknown. Saved configuration is
not a claim about overrides in an already running app or task.

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

## Optional agents

Component installs, updates and optional-agent reinstalls preserve execution
settings. Installing role files does not enable agent tools.

With subagents disabled, Report Planner's delegated construction and explicit
Project Doc Reader delegation are unavailable. Project Docs has direct context
and documentation-impact paths that require neither a Reader nor an index;
bounded direct workflows have been exercised, while broader routing acceptance
remains pending.

Optional component names are `astra_worker` (Sol medium Worker), `result-runner`
(Luna xhigh), `evidence-scout` (Luna xhigh, read-only), and `project-doc-reader`
(read-only). Worker retains its historical identifier for compatibility.
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
it does not establish which model a running child used. `model inherit` removes
only the two global child model/effort overrides, preserving parent settings
and role pins. Replace `--dry-run` with `--yes` to apply a reviewed change.

Recommended configuration includes 120-second minimum/default agent notification
waits. Completion can return early; these settings do not change command
execution timeouts. The wizard manages broader settings, so inspect its plan
before applying recommended configuration.

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

## Troubleshooting

- **Terminal required:** use the interactive `bash -c` command in a terminal,
  or an explicit `codex install` command with `--yes` for automation.
- **Codex not detected:** ensure `codex` is available on PATH in that terminal.
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
These checks are not prerequisites for ordinary installation.
