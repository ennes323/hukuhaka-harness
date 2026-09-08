# Changelog

All notable changes to hukuhaka-harness are documented here. The project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Plugin versions (`marketplace/<plugin>/.codex-plugin/plugin.json`) are
independent from the repository version.

## [1.2.0] — 2026-09-08

### Added

- Added the recommended Codex-only **UI/UX Foundation 0.1.0** plugin for
  source-grounded design systems, mockup/implementation synchronization, and
  rendered verification.
- Added the experimental, opt-in **Project Docs 0.1.3** plugin and optional
  read-only Project Doc Reader for manifest-guided document lookup and impact
  review. Neither is included in recommended installs.

### Changed

- Updated **Engineering Plan to 0.2.3** and **Worklog to 0.4.1** for the
  Codex-only instructions, completion boundaries, and verification reuse rules.
- Made the active packages, installer, and documentation Codex-only. Removed
  the retired Claude integration from the supported distribution.
- Updated **Report Planner from 0.6.0 to 0.7.2**. Planning finalizes content in
  `spec.md`; the bundled designer owns `design.md`, construction, and visual
  verification. Existing combined and paired plans retain compatibility.
- Global guidance now prohibits unnecessary testing and evaluation expansion,
  continues authorized work, and reuses valid checks for unchanged inputs.
- Installation and recommended settings disable subagents, including optional
  role reinstalls. Removed global subagent routing; preserved optional role
  files and existing configuration backup and validation safeguards.
- Updated optional Worker, Runner, and Scout assignment/result contracts.
  Worker uses Sol medium; Runner and Scout use Luna xhigh. Notification wait
  minimum/default settings remain 120 seconds for a future re-enablement.
- Added an explicit agent-model inheritance operation that preserves role pins
  and unrelated settings. Agent upgrades remove unchanged legacy routing
  blocks while reporting edited blocks as conflicts.
- Validation reports suite durations, runs bounded parallel suites, and reuses
  successful checks only for matching inputs. Installed-CLI lifecycle checks
  remain available through `scripts/validate.sh --live-cli`.

### Known limitations

- With subagents disabled, Report Planner's delegated construction and Project
  Docs' Reader-dependent operations remain unavailable under their current
  instructions. Planning and explicit Project Docs maintenance remain usable;
  automatic parent execution has not been verified.

## [1.1.17] — 2026-09-06

- Codex AGENTS guidance now continues authorized work across components, asks
  for approval on unresolved material decisions, and finishes after appropriate
  verification without unrelated investigation or refactoring.
- Engineering Plan 0.2.2 keeps explicit planning and Plan mode read-only while
  returning authorized implementation requests to implementation and verification.
  Routine assumptions do not create an additional approval gate.

## [1.1.16] — 2026-08-31

### Added

- Added the optional Codex-only **`hukuhaka-memory-audit@0.1.0`** plugin. Its
  `$codex-memory-audit` Skill verifies stale engineering context against current
  sources before proposing approval-gated cleanup, and its trusted
  `SessionStart` hook emits an English one-shot suggestion when the hot memory
  summary or cold retrieval store crosses a review threshold.

### Changed

- Worklog lifecycle updates preserve existing notes and continue with
  uncommitted records. Only unresolved conflicts in the affected item block
  its update, and the completion report makes any recording failure explicit.
- Updated **`hukuhaka-worklog@0.4.0`** to retain the newest 25 completed or
  closed entries and run its deterministic archive operation automatically
  after lifecycle closeout. The exact manual archive command remains available
  for idempotent recovery and maintenance.

## [1.1.15] — 2026-08-28

### Added

- Added an explicit `codex agents set|reset` policy for agent concurrency and
  V1 nesting depth, with the same ownership, drift protection, atomic backup,
  Doctor validation, and interactive Settings integration as context policy.

### Changed

- Evidence Scout installation now enables multi-agent execution without
  imposing a concurrency or nesting limit. Existing user-owned values remain
  untouched; the exact ceiling owned by an older Evidence Scout install can be
  adopted into the new agent policy.
- Expanded the managed Codex `AGENTS.md` policy to re-check evidence when a
  user challenges a claim and to prefer the in-app Browser for routine UI
  verification, reserving Chrome DevTools for evidence the in-app Browser
  cannot provide.

## [1.1.14] — 2026-08-24

### Fixed

- Updated **`hukuhaka-codex@0.4.1`** so a blocking Stop review does not
  rerun after its own continuation. Stuck detection now states its actual
  contract—three Bash failures within five minutes—and no-flag rescue runs
  consistently in the foreground.

### Changed

- Added deterministic plugin metadata, hook schema, and documentation-link
  validation, plus separate current authoring routes for Claude Code and Codex.

## [1.1.13] — 2026-08-18

### Added

- Added `codex context` for an explicit custom context-window policy or a
  reset to Codex defaults. It changes only the context-window, auto-compaction,
  and threshold-scope settings; recommended installs, plugin lifecycle, model
  selection, and other global preferences remain untouched.
- Added the same context-window policy as an independent Codex selection in
  the interactive installer.

### Fixed

- Codex reinstall after an Evidence Scout uninstall now handles native quoted
  plugin tables without misreading a plugin's `enabled` value as a duplicate
  `agents.enabled` setting.

### Changed

- Evidence Scout now uses Codex's native Luna subagent routing. New installs no
  longer generate or select a modified model catalog, and updates safely remove
  the exact obsolete catalog override owned by an older Evidence Scout
  manifest while preserving user-owned catalog settings.

## [1.1.12] — 2026-08-13

### Fixed

- Codex recommended installs now migrate the legacy `agents.max_threads`
  setting before adding the canonical concurrency limit, preventing Evidence
  Scout installation from failing Doctor validation with a duplicate-field
  warning. Unrelated agent settings, comments, backups, and rollback behavior
  remain preserved.

## [1.1.11] — 2026-08-13

### Added

- Added the recommended Codex **Evidence Scout** component. One normal
  `codex install --recommended` now installs the verified Luna max, read-only
  agent, its compact dynamic-routing guidance, and required multi-agent runtime
  settings without changing the primary model or unrelated agent defaults.

## [1.1.10] — 2026-08-11

### Changed

- Updated **`hukuhaka-worklog@0.3.0`** to read current work before the first
  non-trivial project task in a new session and automatically track natural
  lifecycle changes without requiring the user to name Worklog. Analysis,
  planning, routine one-off edits, missing Worklog files, delegated agents, and
  pre-existing user changes remain outside automatic mutation.

## [1.1.9] — 2026-08-10

### Fixed

- Codex installs now update an existing official `hukuhaka-harness` marketplace
  from its previous pinned release without requiring a manual reset. A failed
  ref update restores the previous commit, while local and foreign sources are
  left untouched.
- Claude installs now honor `CLAUDE_CONFIG_DIR` and commit only after the native
  plugin list confirms each requested user plugin's version, enabled state, and
  install path. Failed native verification rolls back the whole transaction,
  and successful updates tell existing sessions to run `/reload-plugins`.

## [1.1.8] — 2026-08-10

### Changed

- Expanded the distributed `AGENTS.md` guidance to use the `visualize` Skill
  proactively when diagrams, maps, plots, timelines, comparisons, or
  interactive scenarios materially improve understanding or decision-making.
- Updated **`hukuhaka-engineering-plan@0.2.1`** to activate automatically when
  non-trivial implementation needs planning across multiple files, layers, or
  coordinated workstreams. Routine local edits remain outside its scope.

## [1.1.7] — 2026-08-08

### Fixed

- Codex installs now verify the CLI-reported plugin version and versioned cache,
  including every declared Skill and hook payload. An incomplete or stale cache
  is repaired with one native remove-and-add cycle; installation fails if the
  repaired cache is still invalid.

## [1.1.6] — 2026-08-07

### Changed

- Updated **`hukuhaka-engineering-plan@0.2.0`** to close repository impact
  surfaces before planning, distinguish files that change from those that only
  need verification, and express each implementation slice as current evidence,
  exact delta, downstream effect, and verification. Implementation-shaping
  defaults are now disclosed as assumptions, and plans reuse existing test
  infrastructure unless a new harness is materially required.

## [1.1.5] — 2026-07-31

### Fixed

- Fixed **`hukuhaka-worklog@0.2.2`** Codex command interception for the
  plugin-qualified `$hukuhaka-worklog:worklog` identity and Codex Desktop's
  bound Skill mention, including host-appended terminal newlines. Generated
  `AGENTS.md` guidance now uses the canonical identity; the exact `$worklog`
  forms remain compatibility aliases.
- Documented Codex's `/hooks` review-and-trust gate. Untrusted hooks remain
  skipped instead of being auto-trusted or emulated by the lifecycle Skill.

## [1.1.4] — 2026-07-30

### Changed

- Reworked **`hukuhaka-report-planner@0.6.0`** into four planning stages:
  frame, structure, direct, and lock. The new direction stage gives each
  non-prose anchor a source-backed construction brief covering its material,
  composition, and static, animated, or interactive treatment before one
  designer builds it.
- The installer now shows each plugin's target version in the interactive
  selector and compares registered and target versions in the confirmation
  plan. Template and feature components remain unversioned, and matching
  versions still follow the normal reinstall and verification path.

### Removed

- Removed the structural spec validator and special external `DESIGN.md`
  handoff. Final plans now close through a designer-view self-review, while
  actual artifacts still require direct visual inspection and human acceptance.

## [1.1.3] — 2026-07-30

### Added

- Added **`hukuhaka-worklog@0.2.0`** for Claude Code and Codex. Its
  host-neutral files keep active work in `.hukuhaka/work.md` under
  `In Progress`, `Planned`, and `On Hold`, while completed or intentionally
  closed outcomes move to `.hukuhaka/changelog.md`. The model-invokable Skill
  infers lifecycle changes from natural requests, grounds entries in inspected
  evidence when applicable, and avoids imposing IDs, priorities, owners, or
  schedules.
- Exact setup, status, and archive commands run mechanically before model
  invocation. Setup creates missing worklog files and adds a marker-owned
  awareness block to `CLAUDE.md` or `AGENTS.md`; status validates and summarizes
  the current structure; archive keeps the newest 10 history entries in
  `Recent` and moves older entries to monthly files. Existing files are
  preserved, and legacy `backlog.md` files are never read or migrated.

### Changed

- Expanded **`hukuhaka-report-planner@0.5.1`** with selectively loaded craft
  guidance for maps, timelines, formulas, checklists, citations, imagery,
  glossaries, and interactive disclosure. Existing Skill invocation, planning,
  validation, and designer-handoff contracts are unchanged.

## [1.1.2] — 2026-07-28

### Added

- Added an opt-in global Codex configuration wizard for
  `$CODEX_HOME/config.toml`. It preserves unmanaged text and file mode, shows a
  unified diff, keeps the prior file as `config.toml.hukuhaka-backup`, writes
  atomically, and restores the original unless `codex doctor --json` confirms
  that the config loads successfully.

### Changed

- Replaced implicit and multi-host automation with explicit host-first
  commands such as `claude install --recommended --yes` and
  `codex uninstall --yes`. Interactive installs detect installed host CLIs and
  treat checked components as the exact desired managed state; non-TTY
  zero-argument runs now exit with guidance instead of choosing Claude
  implicitly.
- Codex plugin installation now converges to the requested component set,
  removes aliases only after the canonical plugin installs, and pins remote
  marketplaces to the resolved release tag. Reset and uninstall remain
  separate from global Codex configuration.

### Fixed

- Claude reset-and-install now uses one transaction, verifies the installed
  manifest and files, and restores the previous install on failure. Claude and
  Codex guidance removal also recover interrupted transactions before deciding
  that there is nothing to do.
- Missing Codex CLI and incomplete native operations are no longer reported as
  successful installation or uninstall.
- `--version=<x.y.z>` and `--source-dir=<path>` now work in the installer
  bootstrap. Previously only the space-separated forms were recognised, so a
  piped `curl … | bash -s -- --version=1.0.0` silently installed the latest
  release instead of the requested one, and the version-agreement check could
  not fail. An empty value is now rejected rather than falling back.
- An installer rollback that itself fails no longer deletes its journal and
  backups. The interrupted state is kept and replayed on the next run instead
  of leaving `~/.claude` partly written with nothing left to recover from.
- Codex guidance installs now recover interrupted runs and read state under the
  installer lock. A run killed between the `AGENTS.md` write and the manifest
  write used to leave every later run failing with "managed block is missing"
  on a file the user never edited; `--force` was the only way out.
- The installer no longer acts on a path that points outside `~/.claude`. An
  entry containing `..` in the install manifest or in Claude Code's
  `installed_plugins.json` used to be joined onto `~/.claude` and deleted for
  real during install, reset, or uninstall — including files in your home
  directory. Those paths are now refused, the error names the offending entry,
  and nothing is touched. Recovery for a manifest that trips this is to delete
  `~/.claude/.hukuhaka-manifest.json` and reinstall.
- The installer now runs the source it downloaded and version-checked. It never
  changed directory before starting the Python runtime, so running the
  documented `curl … | bash` from any directory that happened to contain
  `scripts/install/main.py` — a hukuhaka-harness clone being the obvious case —
  executed that copy instead, silently and regardless of the requested version.
- `--dry-run` uninstall no longer takes the installer lock. It used to create
  `~/.claude`, write a lock file, and fail outright with "another hukuhaka
  installer is already running" whenever a real install was in progress, even
  though it modifies nothing.
- Reset and uninstall now report interrupted transactions they replay, the way
  install already did. The recovery happened either way; it was just silent.

## [1.1.1] — 2026-07-25

### Fixed

- Fixed the documented zero-argument remote installer on macOS Bash 3.2, where
  an empty argument array under `set -u` stopped installation before the Python
  runtime started.
- Prevented macOS Bash 3.2 release validation from reporting false failures
  when successful installer output was matched under `pipefail`.

### Changed

- Public releases now run the documented installer against the live GitHub
  release on macOS and Ubuntu. Publication reports success only after public
  validation, release creation, and both live-install jobs are green.

## [1.1.0] — 2026-07-25

### Added

- Added a host-aware terminal installer that shows Claude Code and Codex as
  separate sections and lets each host reset managed plugins and skills before
  installation. Template reset remains an explicit separate choice through
  `--reset-templates`; unrelated host configuration and Codex memory are
  preserved.

### Changed

- Reorganized installation into a five-file Python standard-library runtime and
  consolidated pre-push, validation, and public release workflows behind their
  stable top-level entrypoints. Existing component selection, idempotent
  reinstall, uninstall, transactional rollback, managed-file drift protection,
  and non-interactive Claude defaults remain covered.
- Interactive remote installation now uses `bash -c "$(curl ...)"` so standard
  input remains attached to the terminal selector. Piped installation remains
  available for explicit non-interactive flags.

### Removed

- Removed installer-owned Codex preference editing, third-party extras,
  dependency automation, and their advanced CLI flags. Installation and reset
  now own only declared plugins, skills, and instruction templates.

## [1.0.13] — 2026-07-24

### Added

- **`hukuhaka-engineering-plan@0.1.0`** adds a dual-host Skill for
  repository-grounded engineering plans. It defines behavioral contracts before
  file changes, tests important invariants with concrete counterexamples, and
  maps material requirements to verifiable evidence.
- Added a separate Codex `AGENTS.md` template. The installer merges it into
  `$CODEX_HOME/AGENTS.md` as a managed block without replacing user-owned text.
  Both global instruction templates now ground decisions in inspected evidence,
  preview consequential changes, preserve task state across compaction, protect
  pre-existing work, and use a verified local branch/commit/fast-forward
  lifecycle. Push and other external actions remain explicitly opt-in, while
  the Claude template retains its `spec.md` and attribution rules.
- **`hukuhaka-report-planner@0.5.0`** adds a portable `artifact-designer` skill.
  Immediate artifact requests now delegate construction and direct visual inspection
  to one designer subagent after `spec.md` validates; plan requests still stop at the
  contract. Claude Code ships a named designer agent, while Codex uses the same skill
  through a write-capable worker adapter. User-supplied `DESIGN.md` files are explicit
  inputs rather than auto-loaded runtime fixtures. The handoff now carries selected
  craft references explicitly, and the reference library covers dashboards, decks,
  layouts, plots, screenshots, and timing diagrams without forcing a house style.
- Added an optional English Codex global-configuration wizard for interactive
  installs and the explicit `--configure-codex` path. It configures selected
  reasoning, agent, CLI, notification, sleep, and search preferences while
  preserving existing user settings, previewing the diff, backing up the
  prior file, and validating the result before writing. New reasoning-effort
  selections default to `medium`.

### Fixed

- Headless installs with no component-selection flags now preserve the current
  selection and add supported defaults instead of failing for lack of a TTY.
  Explicit `--configure-codex` requests still require an interactive terminal.

### Removed

- Removed the bundled Figma marketing-study fixture from the report planner. A pinned
  IBM `DESIGN.md` remains private eval input only and does not consume runtime context.
- Removed the deprecated `hukuhaka-project-mapper` and `hukuhaka-ltm` packages
  from the marketplace and installer catalog. Explicit selection now reports an
  unknown component; upgrading an existing hukuhaka installation removes their
  stale marketplace directories and registry entries.

## [1.0.12] — 2026-07-14

### Changed

- Reworked the macOS/Linux installer around a Python 3.9+ standard-library
  runtime shared by Claude Code and Codex. Claude deployment now validates
  state before mutation, writes registries atomically, detects managed-file
  drift, and recovers or rolls back interrupted installs.
- Clarified the runtime support contract: Python 2 and native Windows are not
  supported, and dependency installation runs only with explicit opt-in.

### Fixed

- Fixed Claude upgrades failing when a removed plugin's cache or install
  directory was already absent. Partial legacy state now converges safely on
  reinstall.
- Made optional-extras dry runs non-mutating, rejected malformed Claude
  settings before changes, and stopped core uninstall from deleting independently
  managed statusline state.

## [1.0.11] — 2026-07-14

### Changed

- Added a shared `--host claude|codex|both` installer. Codex installs now use
  the native marketplace lifecycle and support idempotent install, update, and
  removal alongside the existing Claude Code deployment path. The default
  interactive flow asks for the target host before component selection, while
  explicit non-interactive calls retain the existing Claude Code default.
  Dual-host runs show each host's filtered plan and completion status.
- Centralized component lifecycle and host support in `components.json`, and
  changed the public exporter to allow-list individual consumer scripts rather
  than publishing all of `scripts/` and removing private tools afterward.
- Hardened installer and release lifecycle checks for macOS Bash 3.2, physical
  path aliases, plugin-free Claude Code reinstalls, and idempotent version-pinned
  Codex installs. Public branch and tag publication is now atomic.
- Renamed the public distribution repository from `hukuhaka-claude` to
  `hukuhaka-harness`; installer and plugin metadata now use the new URL.
- Extended `scripts/refresh-officials.sh` to mirror official Codex, OpenAI API,
  Apps SDK, and Workspace Agents Markdown sources alongside Claude Code docs.
- **`hukuhaka-report-planner@0.4.0`** now turns reports and other visual-document
  requests into evidence-backed build contracts. The shared Claude Code/Codex
  workflow discovers the reader job and sources, derives structure and anchors,
  selects at most three relevant references after forming a design concept, and
  records locked/guided/open build decisions plus acceptance tests. Explicit plan
  requests stop at `spec.md`; immediate artifact requests continue from it. Both
  hosts write the shared contract under `.hukuhaka/reports/`, with legacy
  `.claude/reports/` plans retained as a read-only fallback.
- **`hukuhaka-project-mapper`** and **`hukuhaka-ltm`** are deprecated and remain
  available only for explicit legacy Claude Code installs. Fresh interactive
  installs and `--all` exclude them; explicit selection prints a warning.

### Removed

- Removed the standalone `hukuhaka-team` skill and its TEAM eval scenarios.

### Fixed

- Replaced the CI plugin-version guard's stale hard-coded project-mapper path
  with a per-changed-plugin check, including Claude/Codex manifest parity.

## [1.0.10] — 2026-07-10

### Fixed

- Public checkout validation now skips private-only Codex runtime tests when
  their complete harness is intentionally absent from the release mirror.

### Changed

- **`hukuhaka-codex@0.4.0`** — replaced model-specific GPT-5.4 prompt guidance
  with `codex-prompting`, strengthened the canonical `codex-plan` workflow,
  and isolated resumable plan threads from unrelated Codex tasks.
- **`hukuhaka-codex@0.3.0`** — added `/hukuhaka-codex:transfer` to move the
  current Claude Code transcript into a persistent, resumable Codex thread.
- **`hukuhaka-codex@0.2.0`** — clarified its Apache-2.0 fork provenance,
  established independent upstream tracking, and hardened Git subprocess
  execution. Added `/debate` plus opt-in, read-only proactive review and stuck
  diagnosis. Brokers now restart automatically when the installed Codex CLI
  version changes, preventing stale app-server compatibility failures.
- **`hukuhaka-report-planner@0.2.0`** — added optional build preferences as
  soft `prefer X over Y` guidance carried from framing into the recorded plan.

## [1.0.9] — 2026-06-25

### Added

- **New plugin `hukuhaka-codex` (`hukuhaka-codex@0.1.0`)** — a Codex + Claude
  collaboration harness, an additive Apache-2.0 fork of OpenAI's Codex plugin.
  On top of the unmodified Codex runtime it adds four orchestration commands:
  `plan` (Codex drafts a read-only implementation plan, Claude builds it),
  `review-loop` (Codex challenges, Claude hardens, repeat), `duel` (both solve
  the task independently, Claude synthesizes), and `full` (plan → build → review
  loop). Also ships `rescue`, `review`, `adversarial-review`, `setup`, and
  `status`/`cancel`/`result` commands, a `codex-rescue` agent, and a stop-time
  review-gate hook.

## [1.0.8] — 2026-06-18

### Changed

- **`hukuhaka-report-builder` rescoped and renamed to `hukuhaka-report-planner`**
  (`hukuhaka-report-planner@0.2.0`). The plugin now **plans** a report instead
  of building it: it looks at the material, proposes the concrete figures it
  needs (timing diagram, diff table, KPI strip, chart, hand-authored diagram)
  and a section/tab outline, captures the user's levers (purpose, audience,
  prose level, design direction), and records the plan to `spec.md`. Building
  the HTML is now a separate, unconstrained step the user runs afterward (e.g.
  hand the plan to a design skill). The old multi-stage build pipeline
  (`0-intake` through `5-assemble`) and its lint/validate scripts are removed in
  favor of a two-stage plan flow (`0-frame`, `1-plan`) plus a `craft/` reference
  set (typography, spacing, color, charts, diagrams, tables, KPI tiles,
  callouts, code blocks, cover) and a `spec-schema.md`.

### Fixed

- **`hukuhaka-project-mapper@1.1.2`** — a sweep of behavior fixes from a full
  plugin review:
  - the sync-cost hook now matches multi-line `record-sync` triggers it
    previously missed
  - `map-init` honors `--force` and skips existing files; `map-clean` is
    marker-based; `map-scan` preserves overrides; `spec.md` is seeded on init
  - `allowed-tools` declared for `map-init`, `map-clean`, `map-compact`
  - analyzer legacy mode removed; root guard and stale-scatter skip added
  - 14 further documentation / contract / edge-case corrections (trace is
    read-only, marker-based placeholder detection, full-sync on diff failure,
    live-only duplicate scan)
- **`hukuhaka-report-planner`** — figure-type accuracy and `validate`
  file-descriptor fixes from verification follow-ups.

## [1.0.7] — 2026-06-10

### Added

- **`hukuhaka-report-builder` promoted from a standalone skill to a marketplace
  plugin** (`hukuhaka-report-builder@0.2.0`). The build now opens with an
  **intake stage**: instead of assuming pre-classified material, it briefly
  investigates the target and proposes three framings (subject / audience /
  publication) for confirmation, then renders a register-identity preview before
  any section is built. A bundled `PreToolUse` hook mechanically blocks building
  a report against an incomplete spec — the design axes must be locked first.

### Changed

- **`hukuhaka-project-mapper` map-sync rebuilt around a deterministic skeleton.**
  Structure extraction (symbols, imports, file counts, the import graph) now
  runs as a zero-token script; the LLM agents only write prose over that fixed
  skeleton from a script-assembled context bundle, with no exploration tools of
  their own. On code-heavy projects this cut sync cost ~40% and wall-clock ~50%
  while keeping the same `.claude/` output contract.

### Fixed

- **`hukuhaka-project-mapper` map-sync no longer silently produces empty output
  on large projects.** When a project's context bundle was big enough to need
  more than one read, the analyze step could finish without generating the
  architecture docs. The fix lets that step run to completion regardless of
  bundle size.

## [1.0.6] — 2026-06-08

### Fixed

- Installing `hukuhaka-project-mapper` on a host without `tree-sitter` is no
  longer blocked. The dependency preflight mistook the plugin's own internal
  Python modules for missing third-party packages and trapped the installer
  in a dependency prompt that could never be satisfied. Plugin Python imports
  are now treated as non-blocking, and `tree-sitter` is correctly optional
  (it accelerates symbol extraction; map-sync falls back to a generic
  extractor when it is absent). Regression introduced in 1.0.5.
- `install.sh` now exits `0` on a successful run (it previously leaked a
  non-zero status from its cleanup step), so `curl … | bash` callers that
  check the exit code see success.

## [1.0.5] — 2026-06-05

### Removed

- `codex-coworker` skill (`skills/codex-coworker/`) — retired. For Codex
  second opinions, use the official OpenAI plugin
  (`openai/codex-plugin-cc`) instead.
- `gemini-coworker` skill (`skills/gemini-coworker/`) — retired alongside
  its sibling; the Gemini CLI it wraps is being discontinued upstream.

### Changed

- `hukuhaka-project-mapper` plugin bumped 1.0.2 → 1.1.0.
  - `/map-sync` analyze stage restructured: code structure (symbols,
    import graph, TODOs, stack) is now extracted **deterministically by
    bundled scripts** with zero LLM involvement; two restricted agents
    (`describe`, `synth`) write only the prose over that skeleton from a
    script-assembled context bundle. Structural hallucination (invented
    paths/symbols) is rejected at merge time by construction. Generated
    doc format and quality are unchanged.
  - Measurably faster and cheaper: on the reference testbed, median sync
    wall-clock −52% and cost −42% versus the previous exploring
    analyzer, with the worst-case exploration tail eliminated.
  - New: when a sync completes, a hook reports the run's wall-clock and
    exact billed token usage inline.
  - The `analyzer` agent is unchanged and continues to power `/audit`.
- `hukuhaka-project-mapper` `/map-sync` structural extraction extended to
  multi-language repos (follow-up on top of 1.1.0; plugin version
  unchanged). Previously only Python files got real symbols and dependency
  edges — non-Python sources fell through to a generic stub:
  - Optional tree-sitter symbol extraction via `tree-sitter-language-pack`,
    with vendored tag queries for 13 languages (Apache-2.0, attributed).
    Without the dependency, every file falls back to the previous regex
    behavior — worst case is exactly the old output, and the fallback is
    counted on stderr so degradation is visible.
  - Import extraction for 9 language families, always on (regex,
    no extra dependency). Imports that resolve to a repo file become
    `depends_on` edges; externals are dropped. Resolvers: js/ts (relative
    + extension inference + `index` barrels), c/c++ (quoted includes,
    unique-basename fallback), go (`go.mod` module prefix), java/kotlin
    (package suffix match), ruby (`require_relative`).
  - Declaration files merge into their definitions when they share a
    directory and stem (`.h`/`.hpp` vs `.c`/`.cpp`, `.d.ts` vs `.ts`) —
    headers no longer appear as duplicate components.
  - Stack detection now reads `build.gradle(.kts)`, `pom.xml`, `go.mod`,
    `Cargo.toml`, `Gemfile`, and `CMakeLists.txt` in addition to
    `pyproject.toml`/`package.json`, at any directory depth (monorepo
    `frontend/`/`backend/` layouts contribute). Manifest-declared entry
    points (`mainClass`, `bin`, `add_executable`, `[[bin]]`) feed entry
    detection.
- Global router template (`templates/CLAUDE.md`) slimmed: "Think Before
  Coding" renamed to "Think Before Acting"; "Suggestions" and "Team vs
  Subagent" sections removed; "Proposing Changes" absorbed into a
  compressed "Reporting"; "Debug" tightened.

## [1.0.4] — 2026-06-02

### Added

- `hukuhaka-report-builder` skill (`skills/hukuhaka-report-builder/`) —
  staged-workflow generator for long-form editorial HTML reports
  (masthead + numbered article + hand-built inline-SVG figures +
  sources). A preflight locks the report's design axes and scaffolds a
  per-report directory with its own `spec.md` before drafting, so the
  visual identity is fixed up front instead of drifting mid-generation.
- `hukuhaka-project-mapper` `/map-scan` command — emits a
  `.claude/scan.md` scatter manifest (per-directory keep/scatter
  decisions) that `/map-sync` then consumes. Classification is
  script-driven; user overrides live below a marker in the same file.

### Changed

- `hukuhaka-project-mapper` plugin bumped 1.0.1 → 1.0.2.
  - `/map-sync` reordered to **scatter-first, then incremental**. It now
    regenerates only the scatter `CLAUDE.md` directories that changed
    since the last sync (git-diff based) instead of every scatter row on
    every run — a large cost reduction on big repos. First run, the
    `--full` flag, or a non-git project falls back to a full sync.
  - Skill → command collapse: the `map-setup` / `map-scan` /
    `map-maintain` / `map-sync` skills were folded directly into their
    slash commands, removing a layer of skill indirection.
  - A `SessionStart` hook now supplies project context in place of the
    previous global-`CLAUDE.md` injection.
- `hukuhaka-ltm`: commands now declare `allowed-tools`, dropping the
  per-tool permission prompts that previously interrupted runs.

### Removed

- `hukuhaka-project-mapper` `/map-validate` command and its orphaned
  helper script removed.

## [1.0.3] — 2026-05-22

### Changed

- `hukuhaka-ltm` plugin bumped 0.4.0 → 0.5.0. Distill agent prompts
  rewritten — numeric thresholds replaced with qualitative tone
  guidance, eliminating an echo-stub failure mode where writers
  copied frontmatter into the body. Body authoring now adapts to
  topic shape instead of length targets.

## hukuhaka-ltm plugin 0.5.0 — 2026-05-22

### Changed

- Distill agent prompts (writer, validate, cluster, l1-update,
  final-review) switched from numeric floors/caps to qualitative
  tone guidance.
- `scripts/distill.py`: removed an internal per-line cap on
  `pinned.md` additions; the 2KB total file cap remains.

## [1.0.2] — 2026-05-21

### Added

- `gemini-coworker` skill (`skills/gemini-coworker/`) — sibling to
  `codex-coworker`, ports the same ask / review / compare workflow to
  Google's Gemini CLI as a parallel second-opinion path. Read-only via
  `--approval-mode plan --skip-trust`; stdout/stderr captured
  separately so non-fatal Gemini warnings don't corrupt JSON output.
- Persona + per-command framing for both `codex-coworker` and
  `gemini-coworker`. The external model now receives a role-identity
  prefix and ask/compare framing inside the same heredoc that already
  carries prompt-injection defences. Eliminates the prior failure mode
  where the sibling model hedged across options because it didn't know
  Claude would synthesize its reply.
- `templates/CLAUDE.md`: new *Reporting* stance — for non-trivial
  changes, surface As-is → Problem → To-be in order before acting, so
  the user can intervene at any layer instead of reverse-engineering
  the proposal.

### Changed

- `hukuhaka-project-mapper` plugin bumped 1.0.0 → 1.0.1. Marketplace
  directory renamed `marketplace/project-mapper/` →
  `marketplace/hukuhaka-project-mapper/` for prefix consistency with
  the rest of the bundle. Plugin name in `plugin.json` and the
  `/hukuhaka-project-mapper:*` slash command namespace are unchanged —
  no end-user-visible behavior change, internal layout only.
- `hukuhaka-ltm` plugin bumped 0.1.0 → 0.4.0. See the per-version
  plugin entries below (0.2.0 → 0.2.1 → 0.2.2 → 0.4.0) for the full
  pipeline redesign. Short version: `/ltm:distill` collapsed from a
  7-agent lock-step into a 6-step skeleton (cluster → file-mapping →
  N parallel writers → validate → l1-update → final-review) with
  body-authoring writers and a main-context Step 2 file map.
- `team` skill renamed to `hukuhaka-team` for prefix consistency.
- `codex-coworker` un-deprecated. Previously default-off and marked
  deprecated; now an active sibling to `gemini-coworker`. Use either
  or both for cross-model triangulation.

### Removed

- `hukuhaka-report` skill removed entirely. The prior IBM/Carbon and
  Figma baselines were both wiped pending a fresh design pass. The
  skill will return under a new design in a later release.

## hukuhaka-ltm plugin 0.4.0 — 2026-05-21

### Changed (breaking — pipeline collapsed to 6-step skeleton)

- `/ltm:distill` collapsed from a 7-agent lock-step (cluster + plan +
  validate + cluster-l1 + plan-l1 + validate-l1 + writer with multi-stage
  YAML actions + 2-revise loops at each tier) to a **6-step skeleton**:
  **cluster** (subagent: L3 → axes) → **file mapping** (main context, not
  a subagent: maps each axis to one of `edit | create | create-merging |
  retire | noop` against the existing L2 corpus, surfaces an assignment
  YAML for the user gate) → **N parallel writers** (subagents, one per
  assignment: author full reference body, not just frontmatter fields) →
  **validate** (subagent: per-card cold-read for stub regression,
  evidence drift, cross-card duplication) → **l1-update** (single
  subagent that reads new L2 corpus + current pinned.md and edits
  pinned.md directly) → **final-review** (single subagent: end-to-end
  anomaly report; read-only).
- `plan.md`, `plan-l1.md`, `cluster-l1.md`, `validate-l1.md` agents
  deleted. Their responsibilities collapsed into main-context file
  mapping (Step 2) + the new `l1-update.md` + the new `final-review.md`.
- `agents/writer.md` rewritten — input is now one assignment row + L3
  bodies + (if applicable) existing card content. Writer uses Write/Edit
  directly to author the card *body* in addition to frontmatter; the old
  `_render_card_body` mechanical assembly is removed. Reference exemplar
  for body density is `index/git-publish-workflow.md` (the only
  hand-authored card from prior cycles).
- `agents/validate.md` rewritten — was per-axis cold-read of a PLAN
  document; now per-card cold-read of finished cards on disk, reporting
  `{issues: [{card, problem, severity}]}` rather than ship/revise/reject.

### Removed

- `_render_card_body`, `_body_was_hand_edited`, `_read_body_stdin`,
  `_write_card`, `cmd_apply`, `cmd_merge`, `cmd_retire`, `_TOPIC_RE`
  from `scripts/distill.py`. The `apply`, `merge`, and `retire` CLI
  subcommands are gone — v0.4.0 writers use Write/Edit directly.
- 6-op enum (`{create, extend, set-evidence, merge, retire, noop}`)
  presented as a constrained action menu in plan PLANs. Step 2 in the
  v0.4.0 command uses similar op names as descriptive labels, but no
  YAML schema is enforced — main context emits assignments freely.
- Per-axis revise loop (≤2 retries). Validators surface issues; user
  re-spins individual writers as needed via the Step 4 gate.

### Added

- `agents/l1-update.md` — one subagent that reads the new L2 corpus +
  current `pinned.md` + policy and edits `pinned.md` to align L1 with
  L2. Replaces the cluster-l1 + plan-l1 + validate-l1 + writer (add-pin
  / retire-pin) sequence. Same 2KB cap.
- `agents/final-review.md` — read-only cross-tier anomaly check: orphan
  L3, pinned line without L2 backing, cross-card content duplication,
  evidence-body mismatch, supersedes drift, pinned.md over-cap.
  Reports; does not auto-fix.

### Why

v0.3.0 distill produced 11 of 12 L2 cards with body = `# {summary}` +
`{context}` echo because `_render_card_body` mechanically assembled body
from frontmatter fields and plan agents had no body-authoring contract.
The only "real" reference card (`git-publish-workflow.md`) was
hand-edited by the user. Cluster + plan also had a structural gap that
made cross-axis L2 merge impossible: cluster grouped L3s without seeing
L2; per-axis plans couldn't touch other axes' cards. The result was
monotonic index growth (10 → 12 over two cycles, with no retires) and
five single-L3 axes that obviously belonged together.

v0.4.0 fixes both: writers author body, and main-context file mapping
in Step 2 sees the full L2 corpus + cluster's axes simultaneously,
enabling `create-merging` and `retire` decisions that the per-axis plan
agents couldn't reach. The "trust AI" alignment is intentional — every
v0.1→v0.3 increment added schema to fight echo and produced new echo
surfaces; v0.4.0 removes schema and adds peer review (validate) +
user-gated assignment + final-review anomaly scan instead.

### Migration

L2 card frontmatter shape, L3 `distilled-into` 3-state pointer, and the
reproject + pin scan/apply CLI utilities are unchanged. Existing L2
cards with stub bodies will be detected and rewritten by writers on the
first v0.4.0 distill cycle. Hand-authored bodies (e.g.,
`git-publish-workflow.md`) are preserved by writer prompts when their
density already exceeds the stub bar.

## hukuhaka-ltm plugin 0.2.2 — 2026-05-20

### Changed (breaking — pipeline architecture)

- `/ltm:distill --retroactive` rebuilt as a **fluid 3-phase pipeline**:
  **cluster** (one agent reads all L3, decomposes into semantic axes with
  no mechanical size rule and no axis cap) → **plan** (axis-parallel
  fan-out — one agent per axis, sees axis L3 + full L2 corpus, writes a
  free-form markdown PLAN ending in a YAML actions block composing
  write-API actions `{create, extend, set-evidence, merge, retire,
  noop}`) → **validate** (axis-parallel fan-out, cold read — fresh agent
  per axis sees L3 + L2 + PLAN markdown only, returns `ship | revise |
  reject` + reason; revise loop bound = 2 retries per axis) → dry-run
  gate → **writer** (sequential per approved action) → deterministic
  `distill.py reproject`.
- v0.2.1's `extractor`, `clusterer`, `reconciler` agents deleted. Their
  responsibilities collapse into the new `cluster` + `plan` + `validate`
  triad. The 6-op enum, mandatory `counter_evidence` schema, reserved-
  phrase blocklist, and mechanical `size >= 2 → promote_candidate` rule
  are all removed — defence against echo migrates from schema gates to
  independent cold-read peer review.
- `agents/writer.md` slimmed — input is now an action dict parsed from
  PLAN YAML, not a reconciler proposal. Action types map 1:1 to existing
  `distill.py` write subcommands.
- `scripts/validate_proposals.py` deleted. Structural validation is
  replaced by validator agent's cold-read judgment. YAML parsing happens
  inline in the command orchestrator (Python heredoc, `yaml.safe_load`).

### Why

v0.2.1's staged pipeline + structural schema closed the v0.2.0 "already
cited" echo path on `extend`/`create`/`set-evidence`/`merge`/`retire` but
left `keep` exempt from `counter_evidence` burden. Real-data run on this
project produced 7 single-L3 "already cited" `keep` proposals — the v0.2.0
echo failure migrated one op over. v0.2.2 stops adding schema gates and
instead removes the menu entirely: the plan agent composes actions (not
picks from an enum); the validate agent peer-reviews cold. Same architectural
shape as `project-mapper`'s analyzer/auditor/verifier pattern.

### Migration

None for data shape — L2 card frontmatter, L3 `distilled-into` 3-state
pointer, and `distill.py` write API are all unchanged. Re-run `/ltm:distill
--retroactive` after upgrade; the new pipeline re-reconciles the full
corpus and proposes `retire` for paraphrase cards that v0.2.1's `keep`
loophole let through.

## hukuhaka-ltm plugin 0.2.1 — 2026-05-19

### Changed (breaking)

- `/ltm:distill --retroactive` rebuilt again — body-first reconciliation
  pipeline replaces v0.2.0's frontmatter-only discoverer/validator/writer
  triad. New 4-stage pipeline: **extractor** (reads full L3 bodies, emits
  atomic claims with line refs) → **clusterer** (semantic grouping with
  mechanical `size >= 2 → promote_candidate` rule, L2-blind) →
  **reconciler** (sees L2 for the first time, emits 6 ops `{extend,
  create, set-evidence, merge, retire, keep}` with structural
  `counter_evidence`) → orchestrator-side substring validation + dry-run
  gate → **writer** (sequential per approved op) → deterministic
  `distill.py reproject`. Same-class sweep on every run.
- `discoverer.md` and `validator.md` agents deleted (v0.2.0 contracts
  too entangled with the frontmatter-only failure mode for clean rewrite).
  Replaced by `extractor.md`, `clusterer.md`, `reconciler.md`.
- `distill.py apply --action` now accepts `set-evidence` (replaces the
  evidence list rather than merging). `extend` semantics unchanged.
- `keep` is a first-class reconciler op — explicit "no meaningful change"
  outcome, distinct from absence. Coverage invariant: every L2 card +
  every cluster appears in exactly one proposal modulo `keep`.

### Added

- `agents/extractor.md`, `agents/clusterer.md`, `agents/reconciler.md` —
  three new body-first agents replacing v0.2.0's three.
- `distill.py merge --topic <winner> --merge-from <loser>` — union
  evidence of winner + loser into winner, auto-add loser to `supersedes`,
  delete loser. Refuses if winner body has been hand-edited (auto-render
  mismatch detection).
- `distill.py retire --topic <slug>` — delete card. Reconciler-emitted op
  (gated by dry-run). `undo` retained as the user-driven escape (different
  audit trail).
- `scripts/validate_proposals.py` — orchestrator-side structural
  validation of reconciler output. For every non-`keep` proposal: checks
  every `counter_evidence` row's `l3_id` resolves to a log file, the
  `line_ref` parses, and the `entails` string is a literal substring of
  the cited L3 file at that line range. Also blocks v0.2.0 echo phrases
  (`"already cited"`, `"likely cited at"`, etc.) in `reason` fields.
  Drop rate > 30% triggers reconciler retry once.

### Migration

None — v0.2.0 data shape (3-state `distilled-into` pointer, L2 card
frontmatter) unchanged. v0.2.1 only changes how the pipeline computes
deltas. First v0.2.1 `--retroactive` run re-reconciles the full L2
corpus from scratch — expect `retire` proposals for any 1:1-paraphrase
cards that v0.2.0's permissive rubric let through.

## hukuhaka-ltm plugin 0.2.0 — 2026-05-19

### Changed (breaking)

- `/ltm:distill --retroactive` rebuilt around a 4-step subagent pipeline:
  `discoverer` (proposes L2 state delta from full L3 + L2 corpus + project
  policy) → user assent gate → `validator` (per-row peer review reading
  full bodies) → `writer` (per-row card create/extend) → deterministic
  `reproject` (syncs L3 `distilled-into` from L2 evidence). Replaces the
  v0.1.x for-each-cluster draft loop that was prone to single-entry
  narrative over-promotion.
- L3 frontmatter: `distilled: true|false` boolean **removed**. Replaced
  by `distilled-into` 3-state pointer (absent = unscanned, `[]` =
  scanned-uncited, `[index/foo.md, ...]` = currently cited). L2 evidence
  list is now the single source of truth; L3 pointer is a derived cache
  that `reproject` rebuilds every distill.
- `distill.py apply` requires `--action {extend,create}`. `extend` rejects
  if the card doesn't exist; `create` rejects if it does. Output is JSON
  `{card, action, evidence_added}`.
- `distill.py undo` no longer reverts a per-entry boolean — it deletes
  the card and auto-runs `reproject` so previously-citing L3 entries
  lose the pointer to the removed card.
- `scan` subcommand removed entirely (the discoverer subagent supersedes
  slug-prefix clustering + undistilled filter).

### Added

- `agents/discoverer.md`, `agents/validator.md`, `agents/writer.md` —
  the three subagents the new pipeline spawns sequentially.
- `distill.py reproject` — deterministic L3 pointer sync. Idempotent.
  Handles v0.1.x → v0.2.x migration (drops legacy `distilled` boolean,
  rewrites scalar `distilled-into` strings as lists). Reports orphan
  citations to stderr.
- Project-level policy surface: `.claude/ltm/CLAUDE.md` may declare L2
  axis inventory, cardinality caps, single-card topics, naming
  conventions, kind-based promotion overrides. Fed verbatim to the
  discoverer; honored as preconditions.

### Migration

First `/ltm:distill --retroactive` on a v0.1.x project runs `reproject`
automatically — drops the legacy boolean from every L3, rewrites any
scalar `distilled-into: index/foo.md` as `distilled-into: [index/foo.md]`.
No manual migration needed. Idempotent — running `reproject` standalone
beforehand is also safe.

## [1.0.1] — 2026-05-19

### Changed

- `skills/hukuhaka-report/`: hero display token bumped 54px → 60px. One step
  above Carbon `display-04`, calibrated for the 1200 max-width report
  hero container so it carries more typographic weight without
  inheriting the marketing-hero scale of `fluid-display-05` (76px).

## [1.0.0] — 2026-05-14

Fresh start. The pre-1.0 git history was discarded as part of a repository
architecture migration. The public repository was reinitialized to host only
the publish artifacts (`marketplace/`, `skills/`, `templates/`, `scripts/`,
plus `README`, `LICENSE`, `CHANGELOG`, `VERSION`). Internal development
artifacts (the eval framework, project documentation, `.claude/` workspace,
LTM history) now live in a separate private repository and never reach this
repo.

### Plugins at 1.0.0

- **hukuhaka-project-mapper** `1.0.0` — codebase analysis and `.claude/` documentation
  generation. Skills: `map-setup`, `map-sync`, `map-maintain`, `map-spec`,
  `audit`, `trace`, `backlog`.
- **hukuhaka-ltm** `0.1.0` — long-term memory plugin with three-tier
  storage (L1 pinned, L2 indexed cards, L3 raw log), autonomous L3 append
  via `<ltm-record>` markers parsed by the Stop hook, batch L2 distillation
  via `/hukuhaka-ltm:ltm-distill`.

### Notes

- Pre-1.0 development tracked plugin features, the eval framework, install
  flow, and documentation. That history is preserved in the private
  development repository but is not relevant to public consumers of the
  marketplace plugins.
- The split between development repository and public repository is the
  governance change that motivated 1.0.0 — see internal documentation.
