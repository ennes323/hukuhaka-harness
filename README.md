# hukuhaka-harness

A Codex-first collection of evidence-grounded planning, project maintenance,
and UI/UX workflows. Components are packaged for Codex and keep their
repository-specific boundaries explicit.

## Who this is for

- You want reusable Codex workflows that inspect current source before acting.
- You need evidence-backed document planning before artifact construction.
- You want repeatable validation, isolated evaluation, and safe local Git work.

## Included components

| Component | Version | Status | What it provides |
|-----------|---------|--------|------------------|
| **hukuhaka-report-planner** | <code>0.7.2</code> | Supported | Finalizes evidence-backed content in <code>spec.md</code>; artifact requests hand representation, design, construction, and visual verification to one designer. |
| **hukuhaka-engineering-plan** | <code>0.2.3</code> | Supported | Produces repository-grounded, decision-complete implementation plans with closed impact surfaces and exact verification mapping. |
| **hukuhaka-worklog** | <code>0.4.1</code> | Supported | Tracks current work, records durable completion or closure history, and runs lifecycle checks before model invocation. |
| **hukuhaka-memory-audit** | <code>0.1.0</code> | Supported, optional | Audits generated Codex memory against current engineering evidence and proposes approval-gated cleanup. |
| **hukuhaka-project-docs** | <code>0.1.3</code> | Experimental / opt-in | Codex-only authority indexes that route the primary agent to selected source documents for reconciliation. |
| **hukuhaka-uiux-foundation** | <code>0.1.0</code> | Supported | Grounds user-visible frontend and UI/UX work in existing design authority and verifies rendered responsive and accessible behavior. |
| **AGENTS.md template** | — | Supported | Supplies the managed Codex instruction block while preserving user content outside the block. |
| **Worker** | — | Supported, optional | Uses Sol medium for bounded implementation, investigation, and independent review. |
| **Result Runner** | — | Supported, optional | Uses Luna xhigh to execute supplied commands and report completion and exit evidence. |
| **Evidence Scout** | — | Supported, optional | Uses Luna xhigh in a read-only sandbox to collect evidence for bounded source questions. |
| **Project Doc Reader** | — | Experimental / opt-in | Provides a Codex-only, manifest-gated, read-only custom agent for selected project documents. |

The version values above come from the native Codex manifests. The repository
version and plugin versions are separate; this documentation change does not
prepare or publish a release.

## Requirements

- macOS or Linux
- Python 3.9+ as <code>python3</code>
- <code>bash</code> and <code>curl</code> for remote bootstrap
- Codex CLI as <code>codex</code>

Native Windows and WSL are outside the tested support matrix.

## Install

From a checkout:

~~~bash
./scripts/install.sh codex install --recommended --yes
~~~

A zero-argument interactive run detects Codex and presents the managed
component state. Automation names the Codex operation explicitly:

~~~bash
./scripts/install.sh codex install --recommended --yes
./scripts/install.sh codex reset --recommended --include-template --yes
./scripts/install.sh codex uninstall --yes
~~~

<code>--components</code> declares the complete desired managed set;
<code>--recommended</code> selects catalog defaults; <code>--dry-run</code>
writes no files and runs no mutating host command. Repeated installation and
removal are intended to be idempotent. Review the plan before confirming a
mutation.

Worker, Result Runner, and Evidence Scout are optional and excluded from
recommended installs. Select them explicitly with a complete component set:

~~~bash
./scripts/install.sh codex install --components agents-md,astra_worker,result-runner,evidence-scout --yes
~~~

Unmodified managed agents absent from the new desired set are removed; locally
edited files are preserved as conflicts. Worker uses Sol medium for bounded
implementation, investigation, and independent review. Runner uses Luna xhigh
for supplied commands and result reporting. Scout uses Luna xhigh in a read-only
sandbox for bounded evidence collection.
The Worker retains the <code>astra_worker</code> identifier for installation and
existing task compatibility; its model is Sol.
The common <code>agents-md</code> template provides routing guidance. Agent
installation alone does not add instructions to global <code>AGENTS.md</code>.
Upgrades remove unmodified routing blocks owned by older installers; edited
legacy blocks remain conflicts and unrelated guidance is preserved.

The retired Scout definition remains frozen under
<code>scripts/tests/fixtures/archived-agents/</code> for legacy manifest, drift,
and removal checks. New explicit installs use the active definition under
<code>agents/</code> and do not install a model catalog or global routing block.

Inspect or explicitly remove global child model defaults:

~~~bash
./scripts/install.sh codex agents model inspect
./scripts/install.sh codex agents model inherit --dry-run
./scripts/install.sh codex agents model inherit --yes
~~~

The transition removes only <code>agents.default_subagent_model</code> and
<code>agents.default_subagent_reasoning_effort</code>, with a backup and validated
transaction. It preserves parent settings, capacity, and role-specific pins.
Ordinary installation does not perform this transition. Inspect reports saved
settings; child execution records establish the actual model.

## Native plugin commands

~~~bash
codex plugin marketplace add hukuhaka/hukuhaka-harness
codex plugin add hukuhaka-report-planner@hukuhaka-harness
codex plugin add hukuhaka-engineering-plan@hukuhaka-harness
codex plugin add hukuhaka-worklog@hukuhaka-harness
codex plugin add hukuhaka-memory-audit@hukuhaka-harness
codex plugin add hukuhaka-project-docs@hukuhaka-harness
codex plugin add hukuhaka-uiux-foundation@hukuhaka-harness
~~~

The marketplace exposes native Codex packages. The repository installer also
manages the global <code>AGENTS.md</code> block and optional custom-agent
files. Start a new Codex task after installing or updating a plugin when
discovery or hook state needs to reload.

## Common workflows

Report planning:

~~~text
$hukuhaka-report-planner
~~~

Engineering planning:

~~~text
$engineering-plan
~~~

Worklog lifecycle:

~~~text
$hukuhaka-worklog:worklog
~~~

The report planner first finalizes a content-only
<code>.hukuhaka/reports/&lt;short-name&gt;/spec.md</code>. When an artifact is
requested, one designer chooses representations, owns the sibling
<code>design.md</code>, builds the artifact, and reports visual verification.
Planning and design are separate responsibilities; the spec remains read-only
during design.

The engineering planner inspects current source, defines observable behavior,
stress-tests important invariants, and maps each requirement to evidence.
An explicit planning request ends with a read-only plan. For an implementation
request, planning is a read-only phase; once material decisions are resolved,
the agent continues through the authorized implementation and verification.
Routine disclosed assumptions do not create a new approval gate.
Worklog keeps current work and durable history in host-neutral files.

## Optional Codex settings and agents

~~~bash
./scripts/install.sh codex configure
./scripts/install.sh codex agents
./scripts/install.sh codex agents set --max-concurrent <threads> --max-depth <depth> --yes
./scripts/install.sh codex agents reset --yes
~~~

Installation and recommended configuration disable subagents with
<code>features.multi_agent = false</code>, including reinstalling optional agents.
The global guidance contains no subagent routing. Optional role files are retained
for later use. Other settings and agent capacity remain separate from plugin
installation, preserving unmanaged configuration. Worker may edit
assigned files, Result Runner executes supplied commands, and Evidence Scout and
Project Doc Reader remain read-only. The primary owns scope and final acceptance.

Recommended Codex settings set the agent-wait minimum and default to 120 seconds
through <code>features.multi_agent_v2.min_wait_timeout_ms</code> and
<code>features.multi_agent_v2.default_wait_timeout_ms</code>. Completion or new
user input can return early. These settings do not lengthen command execution
waits. Ordinary agent installation preserves this separate runtime policy.

## Verification and evaluation

Run public-checkout validation and focused contracts:

~~~bash
scripts/validate.sh --profile public
python3 scripts/tests/document_contracts.py
python3 -m unittest discover -s scripts/tests
~~~

Maintainers use <code>--profile private</code> in the private source checkout.
Validation reports suite durations and uses two workers by default; set
<code>VALIDATE_JOBS=1</code> for serial execution (1–4 are supported).
To test the installed Codex CLI separately, run
<code>scripts/validate.sh --live-cli</code>. It requires the CLI and local model
cache and performs its lifecycle checks in a temporary home. Ordinary validation
does not activate this live check based on what happens to be installed.

Run an isolated case with Eval v2:

~~~bash
python3 eval/run.py run --case <case-id> --host codex --model <model>
~~~

Mechanical results do not replace human review. For visual artifacts, inspect
the rendered output for every affected viewport and state; an unavailable
browser or renderer is reported as unavailable.

## Documentation and license

Maintainer contracts live in the private <code>docs/</code> tree and are not
part of the public checkout. Public users should follow the commands and
official links in this README.

The repository is MIT-licensed. See [LICENSE](LICENSE).
