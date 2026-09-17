"""Single definition of the supported, intentionally bounded settings surface.

Recommendations are harness choices, never claims about host defaults. None
means preserve/unset, not a value to write. Runtime/session overrides are not
observable from config.toml. Internal app, credential and provider keys are
deliberately outside this catalog.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class Option:
    key: str
    group: str
    description: str
    kind: str = "string"
    choices: Tuple[str, ...] = ()
    recommended: Optional[str] = None  # TOML literal
    minimum: Optional[int] = None
    maximum: Optional[int] = None
    official_default: str = "not established"

    @property
    def path(self) -> Tuple[str, ...]:
        return tuple(self.key.split("."))


OPTIONS = (
    Option("model", "Model and response", "Default model; preserve the user's model selection."),
    Option("model_reasoning_effort", "Model and response", "Reasoning effort; availability depends on the selected model.", choices=("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"), recommended='"medium"'),
    Option("plan_mode_reasoning_effort", "Model and response", "Reasoning effort in Plan mode; model support still applies.", choices=("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"), recommended='"high"'),
    Option("model_reasoning_summary", "Model and response", "Visible reasoning-summary detail.", choices=("auto", "concise", "detailed", "none"), recommended='"concise"'),
    Option("model_verbosity", "Model and response", "Response detail, independent of reasoning effort.", choices=("low", "medium", "high"), recommended='"low"'),
    Option("personality", "Model and response", "Response personality.", choices=("pragmatic", "friendly", "none"), recommended='"pragmatic"'),
    Option("model_context_window", "Context", "Context window override; does not enlarge a model's server capacity.", "integer", minimum=1),
    Option("model_auto_compact_token_limit", "Context", "Token threshold for automatic compaction.", "integer", minimum=1),
    Option("model_auto_compact_token_limit_scope", "Context", "Count total context or growth after the carried prefix.", choices=("total", "body_after_prefix"), official_default="total"),
    Option("compact_prompt", "Context", "Custom compaction instructions; preserve existing text."),
    Option("features.multi_agent", "Agents", "V1 collaboration feature flag; does not alone establish V2 availability.", "boolean", recommended="true", official_default="true"),
    Option("agents.enabled", "Agents", "Agent tools switch; enabled V2 takes precedence.", "boolean", recommended="true", official_default="true"),
    Option("features.multi_agent_v2.enabled", "Agents", "V2 backend switch; takes precedence over agents.enabled.", "boolean", recommended="true"),
    Option("agents.max_concurrent_threads_per_session", "Agents", "Maximum concurrent children, excluding the primary agent.", "integer", minimum=1),
    Option("agents.max_depth", "Agents", "V1 nesting depth; ignored by V2.", "integer", minimum=1),
    Option("agents.default_subagent_model", "Agents", "Global child-model override; role and spawn selection are separate."),
    Option("agents.default_subagent_reasoning_effort", "Agents", "Global child-effort override; role and spawn selection are separate.", choices=("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra")),
    Option("features.multi_agent_v2.min_wait_timeout_ms", "Agent waits", "Minimum notification wait in milliseconds; completion may return early.", "integer", recommended="120000", minimum=0, maximum=3600000),
    Option("features.multi_agent_v2.default_wait_timeout_ms", "Agent waits", "Notification wait when omitted; not a command execution timeout.", "integer", recommended="120000", minimum=0, maximum=3600000),
    Option("features.multi_agent_v2.max_wait_timeout_ms", "Agent waits", "Maximum notification wait; schema upper bound is one hour.", "integer", minimum=0, maximum=3600000),
    Option("features.prevent_idle_sleep", "Notifications and display", "Prevent idle sleep during a turn.", "boolean", recommended="true"),
    Option("tui.notifications", "Notifications and display", "TUI notifications: boolean or event-name array.", "notifications", recommended='["agent-turn-complete", "approval-requested"]'),
    Option("tui.notification_condition", "Notifications and display", "When TUI notifications are shown.", choices=("always", "unfocused"), recommended='"unfocused"'),
    Option("tui.status_line", "Notifications and display", "Ordered TUI status-line items; desktop display is separate.", "strings", recommended='["model-with-reasoning", "context-used", "context-window-size", "five-hour-limit", "weekly-limit", "git-branch", "current-dir"]'),
    Option("tui.status_line_use_colors", "Notifications and display", "Use colors in the TUI status line.", "boolean", recommended="true"),
    Option("web_search", "Advanced", "Search mode; installed host validates supported values."),
    Option("service_tier", "Advanced", "Request service tier; preserve host/account choice."),
    Option("approval_policy", "Advanced", "Approval request policy; managed/session policy may override.", choices=("on-request", "never", "untrusted", "on-failure")),
    Option("approvals_reviewer", "Advanced", "Approval reviewer; saved value is not necessarily the session reviewer.", choices=("user", "auto_review", "guardian_subagent")),
    Option("sandbox_mode", "Advanced", "Execution sandbox; managed/session policy may override.", choices=("read-only", "workspace-write", "danger-full-access")),
    Option("shell_environment_policy.inherit", "Advanced", "Baseline child-process environment inheritance.", choices=("all", "core", "none")),
    Option("features.memories", "Advanced", "Memory feature preference; preserve the user's choice.", "boolean"),
    Option("features.js_repl", "Advanced", "JS REPL feature preference; host-dependent availability.", "boolean"),
)
CATALOG = {option.key: option for option in OPTIONS}
KEYS = tuple(option.path for option in OPTIONS)
RECOMMENDED = {option.path: option.recommended for option in OPTIONS if option.recommended is not None}
WAIT_SETTINGS = {key: value for key, value in RECOMMENDED.items() if key[-1].endswith("wait_timeout_ms")}
CONTEXT_KEYS = tuple(option.path for option in OPTIONS if option.key.startswith("model_") and option.group == "Context")
CAPACITY_KEYS = tuple(CATALOG[key].path for key in ("agents.max_concurrent_threads_per_session", "agents.max_depth"))
