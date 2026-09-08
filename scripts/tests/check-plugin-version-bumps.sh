#!/usr/bin/env bash
# Validate that every changed marketplace plugin bumps its native manifest version.
set -euo pipefail

BASE="${1:?usage: check-plugin-version-bumps.sh <base-ref>}"
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

changed_plugins=$(git diff --name-only "$BASE"...HEAD -- marketplace/ \
    | awk -F/ 'NF >= 2 {print $2}' | sort -u)

[ -n "$changed_plugins" ] || exit 0

failed=0
while IFS= read -r plugin; do
    [ -n "$plugin" ] || continue
    codex_manifest="marketplace/$plugin/.codex-plugin/plugin.json"
    if [ -f "$codex_manifest" ]; then
        manifest="$codex_manifest"
    else
        continue
    fi

    old_version=$(git show "$BASE:$manifest" 2>/dev/null \
        | python3 -c "import json,sys; print(json.load(sys.stdin)['version'])" 2>/dev/null \
        || echo "0.0.0")
    new_version=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['version'])" "$manifest")

    if [ "$old_version" = "$new_version" ]; then
        echo "ERROR: $plugin changed without a manifest version bump ($new_version)" >&2
        failed=1
    else
        echo "$plugin: $old_version -> $new_version"
    fi
done <<< "$changed_plugins"

exit "$failed"
