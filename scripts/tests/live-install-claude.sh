#!/usr/bin/env bash
# Public bootstrap and managed lifecycle evidence with a fake Claude CLI.
# Without source-dir this downloads the exact published tag; no model calls.
set -euo pipefail
EXPECTED_VERSION="${1:?usage: live-install-claude.sh <version> [source-dir]}"
EXPECTED_VERSION="${EXPECTED_VERSION#v}"
SOURCE_DIR="${2:-}"
SMOKE_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/hukuhaka-claude-live-install.XXXXXX")
trap 'rm -rf "$SMOKE_ROOT"' EXIT INT TERM
mkdir -p "$SMOKE_ROOT/bin" "$SMOKE_ROOT/home" "$SMOKE_ROOT/claude" "$SMOKE_ROOT/state"
SOURCE_ROOT=$(git rev-parse --show-toplevel)
if [ -n "$SOURCE_DIR" ]; then
    SOURCE_ROOT=$(cd "$SOURCE_DIR" && pwd -P)
else
    git -C "$SOURCE_ROOT" rev-parse --verify "v${EXPECTED_VERSION}^{commit}" >/dev/null
    INSTALL_URL="https://raw.githubusercontent.com/hukuhaka/hukuhaka-harness/v${EXPECTED_VERSION}/scripts/install.sh"
fi

cat > "$SMOKE_ROOT/bin/claude" <<'PY'
#!/usr/bin/env python3
import json
import os
import pathlib
import shutil
import sys

state = pathlib.Path(os.environ["FAKE_CLAUDE_STATE"])
home = pathlib.Path(os.environ["CLAUDE_CONFIG_DIR"])
inventory = state / "inventory.json"
data = json.loads(inventory.read_text()) if inventory.exists() else {"marketplace": None, "plugins": {}}
args = sys.argv[1:]
with (state / "commands.jsonl").open("a") as handle:
    handle.write(json.dumps(args) + "\n")

def save():
    inventory.write_text(json.dumps(data))

def emit(value):
    print(json.dumps(value))

if args == ["--version"]:
    print("2.1.286 (Claude Code)")
elif args[:3] == ["plugin", "marketplace", "list"]:
    registered = data["marketplace"]
    emit([] if registered is None else [{"name": "hukuhaka-plugin", "source": "directory",
         "path": registered, "installLocation": registered}])
elif args[:3] == ["plugin", "marketplace", "add"]:
    assert args[-2:] == ["--scope", "user"]
    data["marketplace"] = args[3]
    save()
    print("Marketplace added")
elif args[:3] == ["plugin", "marketplace", "update"]:
    assert data["marketplace"] and args[3] == "hukuhaka-plugin"
    print("Marketplace updated")
elif args[:3] == ["plugin", "marketplace", "remove"]:
    assert args[3] == "hukuhaka-plugin"
    data["marketplace"] = None
    save()
    print("Marketplace removed")
elif args[:2] == ["plugin", "list"]:
    emit(list(data["plugins"].values()))
elif args[:2] == ["plugin", "validate"]:
    assert args[2] == "--strict"
    root = pathlib.Path(args[3])
    json.loads((root / ".claude-plugin/plugin.json").read_text())
    print("Validation passed")
elif args[:2] in (["plugin", "install"], ["plugin", "update"]):
    assert args[-3:] == ["--scope", "user", "--json"]
    identity = args[2]
    name, marketplace = identity.split("@")
    assert marketplace == "hukuhaka-plugin" and data["marketplace"]
    root = pathlib.Path(data["marketplace"]) / name
    version = json.loads((root / ".claude-plugin/plugin.json").read_text())["version"]
    cache = home / "plugins/cache/hukuhaka-plugin" / name / version
    if cache.exists():
        shutil.rmtree(cache)
    cache.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(root, cache)
    plugin_data = home / "plugin_data" / name
    plugin_data.mkdir(parents=True, exist_ok=True)
    (plugin_data / "preserved.txt").write_text("persistent data")
    data["plugins"][identity] = {"id": identity, "name": name, "version": version,
         "scope": "user", "enabled": True, "installPath": str(cache)}
    save()
    emit({"success": True})
elif args[:2] == ["plugin", "uninstall"]:
    assert args[-4:] == ["--scope", "user", "--keep-data", "--json"]
    row = data["plugins"].pop(args[2], None)
    if row and pathlib.Path(row["installPath"]).exists():
        shutil.rmtree(row["installPath"])
    save()
    emit({"success": True})
else:
    raise SystemExit("unexpected fake Claude arguments: " + repr(args))
PY
chmod +x "$SMOKE_ROOT/bin/claude"
printf '{"model":"user-model","language":"Korean","unmanaged":{"enabled":true}}\n' > "$SMOKE_ROOT/claude/settings.json"
cp "$SMOKE_ROOT/claude/settings.json" "$SMOKE_ROOT/settings-before.json"
printf 'Personal instructions remain.\n' > "$SMOKE_ROOT/claude/CLAUDE.md"
mkdir -p "$SMOKE_ROOT/claude/agents"
printf 'User-owned agent.\n' > "$SMOKE_ROOT/claude/agents/personal.md"
export CLAUDE_CONFIG_DIR="$SMOKE_ROOT/claude"
export FAKE_CLAUDE_STATE="$SMOKE_ROOT/state"
export PATH="$SMOKE_ROOT/bin:$PATH"

run_installer() {
    if [ -n "$SOURCE_DIR" ]; then
        env HOME="$SMOKE_ROOT/home" /bin/bash "$SOURCE_ROOT/scripts/install.sh" \
            --source-dir "$SOURCE_ROOT" --version "$EXPECTED_VERSION" claude "$@"
    else
        curl -fsSL "$INSTALL_URL" | env HOME="$SMOKE_ROOT/home" /bin/bash -s -- \
            --version "$EXPECTED_VERSION" claude "$@"
    fi
}
run_installer install --recommended --dry-run
test ! -f "$CLAUDE_CONFIG_DIR/hk-config.toml"
run_installer install --recommended --yes
run_installer install --recommended --yes
python3 - "$CLAUDE_CONFIG_DIR" "$SMOKE_ROOT/state" "$SMOKE_ROOT/settings-before.json" <<'PY'
import json
import pathlib
import sys
home, state, prior = map(pathlib.Path, sys.argv[1:])
assert (home / "settings.json").read_bytes() == prior.read_bytes(), "settings changed"
guidance = (home / "CLAUDE.md").read_text()
assert "Personal instructions remain." in guidance, "personal instructions lost"
assert "hukuhaka-harness:begin" in guidance, "managed guidance absent"
assert "visualize" not in guidance and "# Subagents" not in guidance, "Codex guidance leaked"
assert not any((home / "agents" / (name + ".toml")).exists()
               for name in ("astra_worker", "result-runner", "evidence-scout")), "Codex roles installed"
assert (home / "agents/personal.md").read_text() == "User-owned agent.\n"
inventory = json.loads((state / "inventory.json").read_text())
assert set(inventory["plugins"]) == {"hukuhaka-worklog@hukuhaka-plugin"}
source = home / "plugins/hukuhaka-plugin"
assert pathlib.Path(inventory["marketplace"]) == source
assert (source / ".claude-plugin/marketplace.json").is_file(), "durable source missing"
PY
run_installer reset --recommended --include-template --yes
run_installer reset --recommended --include-template --yes
run_installer install --components claude-md,hukuhaka-report-planner,hukuhaka-engineering-plan,hukuhaka-worklog,hukuhaka-memory-audit,hukuhaka-project-docs,hukuhaka-uiux-foundation --yes
run_installer state show --json > "$SMOKE_ROOT/install-state.json"
python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$SMOKE_ROOT/install-state.json"
run_installer uninstall --yes
run_installer uninstall --yes
python3 - "$CLAUDE_CONFIG_DIR" "$SMOKE_ROOT/state" "$SMOKE_ROOT/settings-before.json" <<'PY'
import json
import pathlib
import sys
home, state, prior = map(pathlib.Path, sys.argv[1:])
assert (home / "settings.json").read_bytes() == prior.read_bytes(), "uninstall changed settings"
assert (home / "CLAUDE.md").read_text() == "Personal instructions remain.\n", "personal guidance changed"
assert (home / "agents/personal.md").is_file(), "user agent removed"
assert (home / "plugin_data/hukuhaka-worklog/preserved.txt").read_text() == "persistent data"
inventory = json.loads((state / "inventory.json").read_text())
assert inventory == {"marketplace": None, "plugins": {}}, "managed native entries remain"
assert not (home / "plugins/hukuhaka-plugin/.claude-plugin/marketplace.json").exists()
PY
printf 'Public bootstrap and component lifecycle verified with fake Claude CLI for v%s\n' "$EXPECTED_VERSION"
