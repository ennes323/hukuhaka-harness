#!/usr/bin/env bash
# hukuhaka-harness bootstrap for macOS and Linux.
set -euo pipefail

REPO="hukuhaka/hukuhaka-harness"
MIN_PYTHON="3.9"
SOURCE_DIR=""
REQUESTED_VERSION=""
ARGS=("$@")

for ((i = 0; i < ${#ARGS[@]}; i++)); do
    case "${ARGS[$i]}" in
        --source-dir)
            ((i + 1 < ${#ARGS[@]})) || { echo "Error: --source-dir requires a value." >&2; exit 2; }
            SOURCE_DIR="${ARGS[$((i + 1))]}"
            i=$((i + 1))
            ;;
        --version)
            ((i + 1 < ${#ARGS[@]})) || { echo "Error: --version requires a value." >&2; exit 2; }
            REQUESTED_VERSION="${ARGS[$((i + 1))]#v}"
            i=$((i + 1))
            ;;
        --source-dir=*)
            SOURCE_DIR="${ARGS[$i]#--source-dir=}"
            [ -n "$SOURCE_DIR" ] || { echo "Error: --source-dir requires a value." >&2; exit 2; }
            ;;
        --version=*)
            REQUESTED_VERSION="${ARGS[$i]#--version=}"
            [ -n "$REQUESTED_VERSION" ] || { echo "Error: --version requires a value." >&2; exit 2; }
            REQUESTED_VERSION="${REQUESTED_VERSION#v}"
            ;;
    esac
done

python_ok() {
    command -v python3 >/dev/null 2>&1 &&
        python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1
}

if ! python_ok; then
    echo "Error: Python $MIN_PYTHON+ is required as 'python3'." >&2
    echo "  macOS: brew install python" >&2
    echo "  Debian/Ubuntu: sudo apt-get install python3" >&2
    echo "  Fedora/RHEL: sudo dnf install python3" >&2
    echo "Native Windows and Python 2 are not supported." >&2
    exit 1
fi

DOWNLOAD_DIR=""
cleanup() {
    local rc=$?
    if [ -n "$DOWNLOAD_DIR" ] && [ -d "$DOWNLOAD_DIR" ]; then
        rm -rf "$DOWNLOAD_DIR"
    fi
    return "$rc"
}
trap cleanup EXIT INT TERM

SCRIPT_PATH="${BASH_SOURCE[0]:-}"
if [ -z "$SOURCE_DIR" ] && [ -n "$SCRIPT_PATH" ] && [ -f "$SCRIPT_PATH" ]; then
    LOCAL_REPO="$(cd "$(dirname "$SCRIPT_PATH")/.." 2>/dev/null && pwd -P || true)"
    if [ -n "$LOCAL_REPO" ] && [ -f "$LOCAL_REPO/components.json" ] && \
       [ -f "$LOCAL_REPO/scripts/install/main.py" ]; then
        SOURCE_DIR="$LOCAL_REPO"
    fi
fi

if [ -n "$SOURCE_DIR" ]; then
    SOURCE_DIR="$(cd "$SOURCE_DIR" && pwd -P)"
    [ -f "$SOURCE_DIR/VERSION" ] || {
        echo "Error: incomplete hukuhaka-harness source (missing VERSION)." >&2
        exit 1
    }
    RESOLVED_VERSION="${REQUESTED_VERSION:-$(tr -d '[:space:]' < "$SOURCE_DIR/VERSION")}"
    LOCAL_SOURCE=true
    echo "Using local source: $SOURCE_DIR" >&2
else
    if ! command -v curl >/dev/null 2>&1; then
        echo "Error: curl is required to download hukuhaka-harness." >&2
        exit 1
    fi
    if [ -n "$REQUESTED_VERSION" ]; then
        RESOLVED_VERSION="$REQUESTED_VERSION"
    else
        RELEASE_JSON=$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest") || {
            echo "Error: failed to query GitHub for the latest release." >&2
            exit 1
        }
        RESOLVED_VERSION=$(printf '%s' "$RELEASE_JSON" | python3 -c \
            'import json,sys; print(json.load(sys.stdin).get("tag_name", "").lstrip("v"))')
        [ -n "$RESOLVED_VERSION" ] || { echo "Error: latest release has no tag_name." >&2; exit 1; }
    fi
    DOWNLOAD_DIR=$(mktemp -d "${TMPDIR:-/tmp}/hukuhaka-install.XXXXXX")
    ARCHIVE="$DOWNLOAD_DIR/archive.tar.gz"
    echo "Downloading hukuhaka-harness v$RESOLVED_VERSION..."
    curl -fsSL "https://github.com/$REPO/archive/refs/tags/v${RESOLVED_VERSION}.tar.gz" -o "$ARCHIVE"
    python3 - "$ARCHIVE" "$DOWNLOAD_DIR" <<'PY'
import pathlib, sys, tarfile
archive = pathlib.Path(sys.argv[1])
target = pathlib.Path(sys.argv[2]).resolve()
with tarfile.open(archive, "r:gz") as handle:
    roots = set()
    for member in handle.getmembers():
        parts = pathlib.PurePosixPath(member.name).parts
        if not parts:
            continue
        roots.add(parts[0])
        destination = (target / member.name).resolve()
        if target != destination and target not in destination.parents:
            raise SystemExit("Error: unsafe path in release archive: " + member.name)
        if member.issym() or member.islnk():
            raise SystemExit("Error: links are not allowed in release archive: " + member.name)
        if not (member.isdir() or member.isfile()):
            raise SystemExit("Error: special files are not allowed in release archive: " + member.name)
    if len(roots) != 1:
        raise SystemExit("Error: release archive must contain exactly one top-level directory")
    handle.extractall(target)
    (target / ".source-root").write_text(next(iter(roots)), encoding="utf-8")
PY
    EXTRACTED_ROOT=$(cat "$DOWNLOAD_DIR/.source-root")
    SOURCE_DIR="$DOWNLOAD_DIR/$EXTRACTED_ROOT"
    [ -d "$SOURCE_DIR" ] || {
        echo "Error: release archive did not extract to exactly one source directory." >&2
        exit 1
    }
    LOCAL_SOURCE=false
fi

for required in components.json VERSION scripts/install/main.py; do
    [ -f "$SOURCE_DIR/$required" ] || {
        echo "Error: incomplete hukuhaka-harness source (missing $required)." >&2
        exit 1
    }
done

SOURCE_VERSION=$(tr -d '[:space:]' < "$SOURCE_DIR/VERSION")
[ "$SOURCE_VERSION" = "$RESOLVED_VERSION" ] || {
    echo "Error: requested v$RESOLVED_VERSION but source VERSION is $SOURCE_VERSION." >&2
    exit 1
}

export PYTHONPATH="$SOURCE_DIR${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONDONTWRITEBYTECODE=1
# Run from the verified source, not from wherever the user happened to stand.
# `python3 -m` puts the process cwd at sys.path[0], ahead of PYTHONPATH, and
# scripts/ has no __init__.py -- so these are PEP 420 namespace packages whose
# __path__ merges every match on sys.path. A caller's cwd containing
# scripts/install/main.py therefore beat the tree this script just downloaded
# and version-checked. Nothing in the runtime reads the caller's cwd:
# --repo-root is already absolute (see the pwd -P above) and no code path calls
# os.getcwd().
cd "$SOURCE_DIR"
RUNTIME_ARGS=(--repo-root "$SOURCE_DIR" --resolved-version "$RESOLVED_VERSION")
$LOCAL_SOURCE && RUNTIME_ARGS+=(--local-source)
if [ "${#ARGS[@]}" -eq 0 ]; then
    python3 -m scripts.install.main "${RUNTIME_ARGS[@]}"
else
    python3 -m scripts.install.main "${RUNTIME_ARGS[@]}" "${ARGS[@]}"
fi
