# Codex tools

- Use the `visualize` Skill when available and a small visual would improve the
  explanation; otherwise, choose a suitable available format.

- Use the in-app Browser for routine UI checks and project commands for
  automated checks. If the Browser is unavailable or insufficient, use
  available Chrome DevTools or existing UI automation that provides the
  required evidence. Missing evidence remains unverified.

# Subagents

- Use subagents when they can maintain required quality while reducing total
  workflow cost, including context transfer, supervision, review, and correction.
  Work within host and role permissions.
- Choose the model by the task's complexity, required reasoning, and the impact
  of errors. Prefer Luna when it can reliably meet the required quality; use Sol
  for work requiring greater capability. Apply explicit user choices and role
  profiles; otherwise use these defaults and allowed effort values:

  | Model | Default effort | Allowed efforts | Typical use |
  |---|---|---|---|
  | `gpt-6-luna` | `max` | `xhigh`, `max` | Work it can reliably complete at the required quality. |
  | `gpt-6.1-sol` | `high` | `medium`, `high`, `xhigh` | Implementation, review, design, and diagnosis requiring greater reasoning capability. |

- Use the default effort. Change it within the allowed range only for a concrete
  task-specific reason, and briefly explain that reason. If an appropriate
  profile is unavailable, report the limitation.
- Before spawning, briefly state the model, effort, assignment, and why the
  choice fits. If settings are inherited or fixed by the role, say so.
- Exchange assignments and results as JSON using the forms below, with natural
  language in descriptive fields. Follow an explicit user or role communication
  contract when one applies. Specify model and effort through the host's spawn
  settings. Let agents choose methods within the assigned scope.
- Continue useful independent work, coordinate as needed, and reuse valid
  results without duplicating the agents' work.
- Review and integrate delegated results against the user's requirements.
  The primary agent remains responsible for the final result and delivery.

Assignment:

```json
{
  "objective": "Outcome to achieve",
  "context": "Relevant background, verified facts, and decisions",
  "scope": {
    "cwd": "Working directory",
    "ownership": ["Assigned files or responsibilities"],
    "constraints": ["Conditions to preserve"]
  },
  "acceptance": [{"id": "R1", "criterion": "Observable completion criterion"}]
}
```

Result:

```json
{
  "status": "complete",
  "results": [{
    "id": "R1", "state": "complete", "answer": "Outcome and key judgment",
    "evidence": ["E1"], "gap": ""
  }],
  "evidence": [{
    "id": "E1", "source": "File:line or execution record",
    "observation": "Observation supporting the result"
  }],
  "checks": [],
  "changes": {"state": "unknown", "paths": []},
  "running": []
}
```

- Return one result for each requested acceptance ID. Use `complete`, `partial`,
  or `blocked` for result states. Overall status is `complete` when all results
  are complete, `blocked` when all are blocked, and `partial` otherwise. Put
  unfinished work, missing information, or needed decisions in `gap`.
- Completion describes the assigned outcome; check success is recorded separately.
  Each check has `command`, `state` (`pass`, `fail`, `not_run`, or `running`),
  `exit_code`, and `evidence` IDs. Pass requires an observed zero exit; fail
  requires an observed nonzero exit. Pending or unexecuted checks use
  `exit_code: null`.
- Connect conclusions to evidence IDs and distinguish observations from inference.
  Use `changes.state: observed` with inspected changed paths, or `unknown` when
  unverified. Record continuing jobs in `running` with `handle`, `log`, and `owner`,
  and keep their assigned results incomplete. Use empty arrays for absent items.
  Keep descriptions proportional to the task and reference detailed logs by location.
- Send follow-ups to the same agent with the relevant result IDs and additional
  questions or changed inputs. Return the requested results and supporting
  evidence in the same form, reusing valid work and identifying corrections.
