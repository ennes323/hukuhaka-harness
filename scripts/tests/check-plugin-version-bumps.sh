#!/usr/bin/env bash
# Require changed native plugins to increase one version shared by their hosts.
set -euo pipefail
BASE="${1:?usage: check-plugin-version-bumps.sh <base-ref>}"
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
python3 - "$BASE" <<'PY'
import json
import re
import subprocess
import sys
from pathlib import Path

base = sys.argv[1]
changed = subprocess.check_output(["git", "diff", "--name-only", base + "...HEAD", "--", "marketplace/"], text=True)
names = sorted({path.split("/")[1] for path in changed.splitlines() if len(path.split("/")) >= 3})
pattern = re.compile(r"^([0-9]+)\.([0-9]+)\.([0-9]+)([a-z])?$")

def key(value):
    match = pattern.fullmatch(value)
    if match is None:
        raise ValueError("invalid version " + repr(value))
    major, minor, patch, suffix = match.groups()
    return int(major), int(minor), int(patch), suffix is None, suffix or ""

def versions(name, previous=False):
    found = []
    for host in ("codex", "claude"):
        path = "marketplace/{}/.{}-plugin/plugin.json".format(name, host)
        if previous:
            result = subprocess.run(["git", "show", base + ":" + path], text=True, capture_output=True)
            if result.returncode:
                continue
            text = result.stdout
        else:
            if not Path(path).is_file():
                continue
            text = Path(path).read_text(encoding="utf-8")
        version = json.loads(text)["version"]
        key(version)
        found.append(version)
    if len(set(found)) > 1:
        raise ValueError(name + ": host manifest versions differ")
    return found[0] if found else None

failed = False
for name in names:
    try:
        previous, candidate = versions(name, True), versions(name)
        if candidate is None:
            if not any(path.is_file() for path in Path("marketplace", name).rglob("*")):
                print(name + ": removed")
                continue
            raise ValueError(name + ": no readable native manifest")
        if previous is not None and key(candidate) <= key(previous):
            raise ValueError("{} version must increase: {} -> {}".format(name, previous, candidate))
        print("{}: {} -> {}".format(name, previous or "new", candidate))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        failed = True
sys.exit(1 if failed else 0)
PY
