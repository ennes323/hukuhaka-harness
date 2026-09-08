#!/usr/bin/env python3
"""Build an exact image, then verify or reuse its isolated Codex lifecycle result."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.verification import (  # noqa: E402
    CACHE_DIR_ENV, VerificationError, digest, environment_digest, run_verified, tool_identity, tree_digest,
)


def command(args: list[str], *, capture: bool = True, timeout: int = 600) -> str:
    result = subprocess.run(args, capture_output=capture, text=True, timeout=timeout, check=True)
    return result.stdout.strip() if capture else ""


def runtime_image_digest(image: str) -> str:
    inspected = json.loads(command(["docker", "image", "inspect", image]))
    if not isinstance(inspected, list) or len(inspected) != 1 or not isinstance(inspected[0], dict):
        raise VerificationError("Docker did not identify the executable image payload")
    item = inspected[0]
    rootfs = item.get("RootFS")
    if (not isinstance(item.get("Config"), dict) or not item.get("Os") or not item.get("Architecture")
            or not isinstance(rootfs, dict) or rootfs.get("Type") != "layers"
            or not isinstance(rootfs.get("Layers"), list) or not rootfs["Layers"]
            or any(not isinstance(layer, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", layer)
                   for layer in rootfs["Layers"])):
        raise VerificationError("Docker execution settings or layer identity are unavailable")
    # OCI execution identity is the complete runtime configuration and ordered
    # rootfs changesets. The inspected index ID can additionally include fresh
    # build attestations; it is used to execute this build, not to key reuse.
    return digest({key: item.get(key) for key in
                   ("Config", "RootFS", "Os", "Architecture", "Variant", "OsVersion", "OsFeatures")})


def verify(source: Path, cache: Optional[Path] = None) -> str:
    version_file = source / "scripts/tests/codex-e2e-version.txt"
    dockerfile = source / "scripts/tests/codex-real-e2e.Dockerfile"
    if not version_file.is_file() or not dockerfile.is_file():
        raise VerificationError("source tree is missing its Docker contract")
    version = version_file.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[0-9A-Za-z._-]+", version):
        raise VerificationError("invalid Codex E2E version")
    # Always contact the selected server and build. Layer caching still applies,
    # while a new image/server can never borrow an old container result.
    context = command(["docker", "context", "show"])
    server_format = "{{.ID}} {{.OSType}} {{.Architecture}} {{.ServerVersion}}"
    server = command(["docker", "info", "--format", server_format])
    reusable = cache is not None and not (source / ".git").exists()
    source_before = tree_digest(source) if reusable else None
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="hukuhaka-docker-build-") as name:
        iidfile = Path(name) / "image-id"
        command([
            "docker", "build", "--build-arg", "CODEX_VERSION=" + version,
            "--file", str(dockerfile), "--tag", "hukuhaka-codex-e2e:" + version,
            "--iidfile", str(iidfile), str(source),
        ], capture=False)
        image = iidfile.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
        raise VerificationError("Docker build did not produce a full immutable image ID")
    print("Docker build: {:.2f}s ({})".format(time.monotonic() - started, image[:19]), flush=True)
    if reusable and tree_digest(source) != source_before:
        raise VerificationError("Docker source changed during build")

    def identity() -> dict[str, object]:
        current_context = command(["docker", "context", "show"])
        current_server = command(["docker", "info", "--format", server_format])
        if current_context != context or current_server != server:
            raise VerificationError("Docker context/server changed during verification")
        return {
            "source": tree_digest(source), "image_runtime": runtime_image_digest(image),
            "context": context, "server": server, "environment": environment_digest(),
            "docker_cli": tool_identity("docker"),
            "driver": digest(Path(__file__).read_text(encoding="utf-8")),
        }

    def run_container() -> str:
        # The tag can be overwritten by a concurrent build; the iidfile cannot.
        command(["docker", "run", "--rm", image], capture=False)
        return ""

    checked = run_verified("Docker Codex lifecycle", identity, run_container, cache=cache, reusable=reusable)
    return checked.summary("Docker Codex lifecycle")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    args = parser.parse_args()
    cache = os.environ.get(CACHE_DIR_ENV)
    try:
        print(verify(args.source_dir.resolve(), Path(cache) if cache else None), flush=True)
    except (OSError, VerificationError, subprocess.SubprocessError) as exc:
        print("codex-e2e: {}".format(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
