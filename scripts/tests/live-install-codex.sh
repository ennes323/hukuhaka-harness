#!/usr/bin/env bash
# Cross-platform Codex release smoke. With no source directory it exercises the
# documented public bootstrap at the exact release tag. Tests may pass a source
# directory to exercise the same lifecycle without network access.
set -euo pipefail

EXPECTED_VERSION="${1:-}"
SOURCE_DIR="${2:-}"

if [ -z "$EXPECTED_VERSION" ]; then
    echo "usage: $0 <version> [source-dir]" >&2
    exit 2
fi
EXPECTED_VERSION="${EXPECTED_VERSION#v}"

SMOKE_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/hukuhaka-codex-live-install.XXXXXX")
cleanup() {
    local rc=$?
    rm -rf "$SMOKE_ROOT"
    return "$rc"
}
trap cleanup EXIT INT TERM

mkdir -p "$SMOKE_ROOT/bin" "$SMOKE_ROOT/home" "$SMOKE_ROOT/codex-home" "$SMOKE_ROOT/state"

if [ -n "$SOURCE_DIR" ]; then
    SOURCE_ROOT=$(cd "$SOURCE_DIR" && pwd -P)
    INSTALL_COMMAND=(
        /bin/bash "$SOURCE_ROOT/scripts/install.sh"
        --source-dir "$SOURCE_ROOT"
        --version "$EXPECTED_VERSION"
        codex install --recommended --yes
    )
else
    SOURCE_ROOT=$(git rev-parse --show-toplevel)
    git -C "$SOURCE_ROOT" rev-parse --verify "v${EXPECTED_VERSION}^{commit}" >/dev/null
    INSTALL_URL="https://raw.githubusercontent.com/hukuhaka/hukuhaka-harness/v${EXPECTED_VERSION}/scripts/install.sh"
fi

cat > "$SMOKE_ROOT/bin/codex" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

state_dir="${FAKE_CODEX_STATE:?}"
marketplace="$state_dir/marketplace"
plugins="$state_dir/plugins"
touch "$plugins"

if [ "${1:-}" = "--version" ]; then
    printf 'codex release smoke\n'
elif [ "${1:-}" = "plugin" ] && [ "${2:-}" = "marketplace" ] && [ "${3:-}" = "add" ]; then
    printf '%s\n' "${4:?}" > "$marketplace"
    printf '{"alreadyAdded":false}\n'
elif [ "${1:-}" = "plugin" ] && [ "${2:-}" = "marketplace" ] && [ "${3:-}" = "list" ]; then
    if [ -f "$marketplace" ]; then
        source_value=$(cat "$marketplace")
        if [ "$source_value" = "hukuhaka/hukuhaka-harness" ]; then
            source_type=git
            source_value="https://github.com/hukuhaka/hukuhaka-harness.git"
        else
            source_type=local
        fi
        printf '{"marketplaces":[{"name":"hukuhaka-harness","root":"%s","marketplaceSource":{"sourceType":"%s","source":"%s"}}]}\n' \
            "$FAKE_SOURCE_ROOT" "$source_type" "$source_value"
    else
        printf '{"marketplaces":[]}\n'
    fi
elif [ "${1:-}" = "plugin" ] && [ "${2:-}" = "marketplace" ] && [ "${3:-}" = "remove" ]; then
    rm -f "$marketplace"
    printf '{}\n'
elif [ "${1:-}" = "plugin" ] && [ "${2:-}" = "list" ]; then
    first=1
    printf '{"installed":['
    while IFS= read -r name; do
        [ -n "$name" ] || continue
        [ "$first" -eq 1 ] || printf ','
        first=0
        version=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' \
            "$FAKE_SOURCE_ROOT/marketplace/$name/.codex-plugin/plugin.json")
        installed="$CODEX_HOME/plugins/cache/hukuhaka-harness/$name/$version"
        printf '{"name":"%s","marketplaceName":"hukuhaka-harness","pluginId":"%s@hukuhaka-harness","version":"%s","installedPath":"%s"}' \
            "$name" "$name" "$version" "$installed"
    done < "$plugins"
    printf ']}\n'
elif [ "${1:-}" = "plugin" ] && [ "${2:-}" = "add" ]; then
    name="${3%%@*}"
    version=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' \
        "$FAKE_SOURCE_ROOT/marketplace/$name/.codex-plugin/plugin.json")
    cache_root="$CODEX_HOME/plugins/cache/hukuhaka-harness/$name"
    installed="$cache_root/$version"
    rm -rf "$cache_root"
    mkdir -p "$cache_root"
    cp -R "$FAKE_SOURCE_ROOT/marketplace/$name" "$installed"
    if ! grep -Fxq "$name" "$plugins"; then
        printf '%s\n' "$name" >> "$plugins"
    fi
    printf '{"pluginId":"%s@hukuhaka-harness","name":"%s","marketplaceName":"hukuhaka-harness","version":"%s","installedPath":"%s"}\n' \
        "$name" "$name" "$version" "$installed"
elif [ "${1:-}" = "plugin" ] && [ "${2:-}" = "remove" ]; then
    name="${3%%@*}"
    next="$plugins.next"
    grep -Fxv "$name" "$plugins" > "$next" || true
    mv "$next" "$plugins"
    rm -rf "$CODEX_HOME/plugins/cache/hukuhaka-harness/$name"
    printf '{}\n'
elif [ "${1:-}" = "doctor" ] && [ "${2:-}" = "--json" ]; then
    config="$CODEX_HOME/config.toml"
    if grep -Eq '^[[:space:]]*(agents\.)?max_threads[[:space:]]*=' "$config" && \
       grep -Eq '^[[:space:]]*(agents\.)?max_concurrent_threads_per_session[[:space:]]*=' "$config"; then
        printf '{"checks":{"config.load":{"status":"warning","summary":"config loaded","details":{"startup warning":"Ignoring malformed agent role definition: duplicate field `max_concurrent_threads_per_session`"}}}}\n'
    else
        printf '{"checks":{"config.load":{"status":"ok","summary":"config loaded"}}}\n'
    fi
else
    printf 'unexpected fake codex args: %s\n' "$*" >&2
    exit 2
fi
SH
chmod +x "$SMOKE_ROOT/bin/codex"

python3 - "$SMOKE_ROOT/codex-home/models_cache.json" <<'PY'
import json
import sys

payload = {
    "client_version": "release-smoke",
    "models": [
        {
            "slug": "gpt-5.6-sol",
            "multi_agent_version": "v2",
            "display_name": "GPT-5.6-Sol",
        },
        {
            "slug": "gpt-5.6-luna",
            "multi_agent_version": "v1",
            "display_name": "GPT-5.6-Luna",
        },
    ],
}
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(payload, handle, separators=(",", ":"))
    handle.write("\n")
PY
cp "$SMOKE_ROOT/codex-home/models_cache.json" "$SMOKE_ROOT/source-models-cache.json"

export HOME="$SMOKE_ROOT/home"
export CODEX_HOME="$SMOKE_ROOT/codex-home"
export FAKE_CODEX_STATE="$SMOKE_ROOT/state"
export FAKE_SOURCE_ROOT="$SOURCE_ROOT"
export PATH="$SMOKE_ROOT/bin:$PATH"

cat > "$CODEX_HOME/config.toml" <<'TOML'
[agents]
max_threads = 4 # legacy alias
default_subagent_model = "user-model"
TOML

run_install() {
    if [ -n "$SOURCE_DIR" ]; then
        "${INSTALL_COMMAND[@]}"
    else
        curl -fsSL "$INSTALL_URL" \
            | /bin/bash -s -- --version "$EXPECTED_VERSION" codex install --recommended --yes
    fi
}

first_output=$(run_install 2>&1)
second_output=$(run_install 2>&1)
printf '%s\n' "$first_output"
printf '%s\n' "$second_output"

if [ -z "$SOURCE_DIR" ]; then
    grep -Fq "Downloading hukuhaka-harness v${EXPECTED_VERSION}..." <<<"$first_output"
fi
grep -Eq "  Codex: +success" <<<"$first_output"
grep -Eq "  Codex: +success" <<<"$second_output"
if grep -Fq "install astra_worker" <<<"$second_output" || \
   grep -Fq "install result-runner" <<<"$second_output" || \
   grep -Fq "install evidence-scout" <<<"$second_output"; then
    echo "recommended selection installed an optional specialist" >&2
    exit 1
fi

if [ -n "$SOURCE_DIR" ]; then
    optional_output=$(/bin/bash "$SOURCE_ROOT/scripts/install.sh" \
        --source-dir "$SOURCE_ROOT" --version "$EXPECTED_VERSION" \
        codex install --components agents-md,astra_worker,result-runner,evidence-scout --yes 2>&1)
else
    optional_output=$(curl -fsSL "$INSTALL_URL" | /bin/bash -s -- \
        --version "$EXPECTED_VERSION" codex install \
        --components agents-md,astra_worker,result-runner,evidence-scout --yes 2>&1)
fi
printf '%s\n' "$optional_output"
grep -Fq "multi-agent enabled" <<<"$optional_output"

python3 - "$CODEX_HOME" "$SMOKE_ROOT/source-models-cache.json" "$EXPECTED_VERSION" <<'PY'
import json
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
source_cache = pathlib.Path(sys.argv[2])
version = sys.argv[3]

agent = root / "agents" / "astra_worker.toml"
routing = root / "AGENTS.md"
manifest_path = root / ".hukuhaka-astra_worker-manifest.json"
config_path = root / "config.toml"

for path in (agent, routing, manifest_path, config_path):
    if not path.is_file():
        raise SystemExit("missing installed Astra Worker artifact: {}".format(path))
runner = root / "agents" / "result-runner.toml"
if not runner.is_file() or not (root / ".hukuhaka-result-runner-manifest.json").is_file():
    raise SystemExit("missing installed Result Runner artifacts")
scout = root / "agents" / "evidence-scout.toml"
if not scout.is_file() or not (root / ".hukuhaka-evidence-scout-manifest.json").is_file():
    raise SystemExit("missing installed Evidence Scout artifacts")
for path, model, effort in (
    (agent, "gpt-5.6-sol", "medium"),
    (runner, "gpt-5.6-luna", "xhigh"),
    (scout, "gpt-5.6-luna", "xhigh"),
):
    text = path.read_text()
    if 'model = "{}"'.format(model) not in text or 'model_reasoning_effort = "{}"'.format(effort) not in text:
        raise SystemExit("agent model/effort pin differs: {}".format(path))
if 'sandbox_mode = "read-only"' not in scout.read_text():
    raise SystemExit("Evidence Scout is not read-only")
if (root / "models-luna-v2.json").exists():
    raise SystemExit("obsolete Luna v2 model catalog was installed")

if (root / "models_cache.json").read_bytes() != source_cache.read_bytes():
    raise SystemExit("models_cache.json changed")

for name in ("astra_worker", "result-runner", "evidence-scout"):
    current_manifest = json.loads(
        (root / ".hukuhaka-{}-manifest.json".format(name)).read_text(encoding="utf-8")
    )
    if current_manifest.get("version") != version:
        raise SystemExit(
            "{} manifest version {!r} != {!r}".format(
                name, current_manifest.get("version"), version
            )
        )
    if current_manifest.get("schemaVersion") != 4:
        raise SystemExit("{} manifest is not schema v4".format(name))
    if any(key.startswith("catalog") or key.startswith("routing") for key in current_manifest):
        raise SystemExit("{} manifest still owns a model catalog or routing".format(name))

routing_text = routing.read_text(encoding="utf-8")
if any("<!-- hukuhaka-{}:".format(name) in routing_text
       for name in ("astra_worker", "evidence-scout", "result-runner", "project-doc-reader")):
    raise SystemExit("agent installation injected obsolete routing")
config = config_path.read_text(encoding="utf-8")
for expected_line in ("multi_agent = false",):
    if expected_line not in config:
        raise SystemExit("missing config setting: {}".format(expected_line))
if "model_catalog_json" in config:
    raise SystemExit("obsolete model_catalog_json pointer was installed")
if "max_threads = 4 # legacy alias" not in config:
    raise SystemExit("user-owned legacy agent limit was not preserved")
if "max_concurrent_threads_per_session" in config or "max_depth" in config:
    raise SystemExit("component install unexpectedly wrote agent execution policy")
if 'default_subagent_model = "user-model"' not in config:
    raise SystemExit("unmanaged agent default was not preserved")

backup = (root / "config.toml.hukuhaka-backup").read_text(encoding="utf-8")
if "max_threads = 4 # legacy alias" not in backup:
    raise SystemExit("legacy pre-migration config was not backed up")
PY

printf 'Codex Worker, Runner, and Scout live install verified for v%s\n' "$EXPECTED_VERSION"
