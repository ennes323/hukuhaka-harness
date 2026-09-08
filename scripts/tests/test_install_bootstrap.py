from __future__ import annotations

import io
import os
import shutil
import shlex
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from typing import List, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[2]


class InstallBootstrapTests(unittest.TestCase):
    def run_bootstrap(
        self,
        arguments: Sequence[str],
    ) -> Tuple[subprocess.CompletedProcess[str], List[str], str]:
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            source = temp / "source"
            script = source / "scripts" / "install.sh"
            runtime = source / "scripts" / "install" / "main.py"
            runtime.parent.mkdir(parents=True)
            shutil.copy2(ROOT / "scripts" / "install.sh", script)
            runtime.write_text("", encoding="utf-8")
            (source / "components.json").write_text("{}\n", encoding="utf-8")
            (source / "VERSION").write_text("1.1.1\n", encoding="utf-8")

            fake_bin = temp / "bin"
            fake_bin.mkdir()
            invocation_log = temp / "python-invocations.log"
            fake_python = fake_bin / "python3"
            fake_python.write_text(
                """#!/bin/bash
set -eu
if [ "${1:-}" = "-c" ]; then
    exit 0
fi
{
    printf '%s\\n' __CALL__
    printf '%s\\n' "$@"
} >> "$BOOTSTRAP_LOG"
""",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)

            env = os.environ.copy()
            env["PATH"] = "{}:{}".format(fake_bin, env.get("PATH", ""))
            env["HOME"] = str(temp / "home")
            env["BOOTSTRAP_LOG"] = str(invocation_log)
            result = subprocess.run(
                ("/bin/bash", str(script)) + tuple(arguments),
                cwd=temp,
                env=env,
                text=True,
                capture_output=True,
            )
            calls = (
                invocation_log.read_text(encoding="utf-8").splitlines()
                if invocation_log.is_file()
                else []
            )
            return result, calls, str(source.resolve())

    def run_remote_bootstrap(
        self, arguments: Sequence[str] = (), *, decoy: bool = False
    ) -> Tuple[subprocess.CompletedProcess[str], Path, List[str]]:
        temp_context = tempfile.TemporaryDirectory()
        self.addCleanup(temp_context.cleanup)
        temp = Path(temp_context.name)
        version = "1.1.1"
        archive_root = "hukuhaka-harness-{}".format(version)
        archive = temp / "release.tar.gz"
        public_sources = (
            ROOT / ".agents",
            ROOT / "agents",
            ROOT / "marketplace",
            ROOT / "templates",
            ROOT / "components.json",
            ROOT / "scripts" / "install",
        )
        with tarfile.open(archive, "w:gz") as handle:
            for source in public_sources:
                relative = source.relative_to(ROOT)
                handle.add(source, arcname="{}/{}".format(archive_root, relative.as_posix()))
            version_bytes = (version + "\n").encode("utf-8")
            version_info = tarfile.TarInfo("{}/VERSION".format(archive_root))
            version_info.size = len(version_bytes)
            version_info.mode = 0o644
            handle.addfile(version_info, io.BytesIO(version_bytes))

        fake_bin = temp / "bin"
        fake_bin.mkdir()
        fake_curl = fake_bin / "curl"
        fake_curl.write_text(
            """#!/bin/bash
set -eu
output=""
url=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        -o)
            output="$2"
            shift 2
            ;;
        -*)
            shift
            ;;
        *)
            url="$1"
            shift
            ;;
    esac
done
case "$url" in
    */releases/latest)
        printf '{"tag_name":"v%s"}\\n' "$BOOTSTRAP_VERSION"
        ;;
    */archive/refs/tags/v*.tar.gz)
        cp "$BOOTSTRAP_ARCHIVE" "$output"
        ;;
    *)
        printf 'unexpected curl URL: %s\\n' "$url" >&2
        exit 2
        ;;
esac
""",
            encoding="utf-8",
        )
        fake_curl.chmod(0o755)

        python_log = temp / "python.log"
        actual_python = shutil.which("python3")
        self.assertIsNotNone(actual_python)
        fake_python = fake_bin / "python3"
        fake_python.write_text(
            """#!/bin/bash
printf '%s ' "$@" >> "$BOOTSTRAP_PYTHON_LOG"
printf '\\n' >> "$BOOTSTRAP_PYTHON_LOG"
exec {} "$@"
""".format(shlex.quote(str(actual_python))),
            encoding="utf-8",
        )
        fake_python.chmod(0o755)

        fake_codex = fake_bin / "codex"
        fake_codex.write_text(
            """#!/bin/bash
set -eu
if [ "${1:-}" = "--version" ]; then
    printf 'codex bootstrap test double\\n'
elif [ "${1:-}" = "plugin" ] && [ "${2:-}" = "list" ] && [ "${3:-}" = "--json" ]; then
    printf '{"installed":[]}\\n'
else
    printf 'unexpected fake codex args: %s\\n' "$*" >&2
    exit 2
fi
""",
            encoding="utf-8",
        )
        fake_codex.chmod(0o755)

        if decoy:
            # A directory that merely looks like the package root is enough.
            # scripts/ carries no __init__.py, so `python3 -m scripts.install.main`
            # resolves through PEP 420 namespace packages whose __path__ is the
            # concatenation of every match on sys.path -- and sys.path[0] is the
            # process cwd, which comes before PYTHONPATH.
            decoy_runtime = temp / "scripts" / "install" / "main.py"
            decoy_runtime.parent.mkdir(parents=True)
            decoy_runtime.write_text(
                "import os\n"
                "with open(os.environ['BOOTSTRAP_DECOY_MARKER'], 'w') as handle:\n"
                "    handle.write('decoy ran')\n",
                encoding="utf-8",
            )

        home = temp / "home"
        home.mkdir()
        env = os.environ.copy()
        env.update(
            {
                "PATH": "{}:{}".format(fake_bin, env.get("PATH", "")),
                "HOME": str(home),
                "BOOTSTRAP_ARCHIVE": str(archive),
                "BOOTSTRAP_VERSION": version,
                "BOOTSTRAP_PYTHON_LOG": str(python_log),
                "BOOTSTRAP_DECOY_MARKER": str(temp / "decoy-ran.txt"),
            }
        )
        script_text = (ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")
        result = subprocess.run(
            ("/bin/bash", "-c", script_text, "install.sh") + tuple(arguments),
            cwd=temp,
            env=env,
            text=True,
            capture_output=True,
        )
        calls = (
            python_log.read_text(encoding="utf-8").splitlines()
            if python_log.is_file()
            else []
        )
        return result, home, calls

    def test_zero_arguments_forward_once_without_bash_32_nounset_failure(self) -> None:
        result, calls, source = self.run_bootstrap(())

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn("unbound variable", result.stderr)
        self.assertEqual(
            [
                "__CALL__",
                "-m",
                "scripts.install.main",
                "--repo-root",
                source,
                "--resolved-version",
                "1.1.1",
                "--local-source",
            ],
            calls,
        )

    def test_user_arguments_are_forwarded_once_and_unchanged(self) -> None:
        user_arguments = (
            "codex",
            "install",
            "--components",
            "alpha,beta",
            "--dry-run",
        )
        result, calls, source = self.run_bootstrap(user_arguments)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            [
                "__CALL__",
                "-m",
                "scripts.install.main",
                "--repo-root",
                source,
                "--resolved-version",
                "1.1.1",
                "--local-source",
            ]
            + list(user_arguments),
            calls,
        )

    def test_equals_form_options_are_parsed_by_the_pre_scan(self) -> None:
        # argparse binds --version=X, so the pre-scan must too. When it does not,
        # REQUESTED_VERSION stays empty, the source/resolved version agreement
        # check compares the source version to itself and cannot fail, and the
        # wrong version is installed with no error.
        user_arguments = (
            "--version=1.1.1",
            "codex",
            "install",
            "--recommended",
            "--dry-run",
        )
        result, calls, source = self.run_bootstrap(user_arguments)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            [
                "__CALL__",
                "-m",
                "scripts.install.main",
                "--repo-root",
                source,
                "--resolved-version",
                "1.1.1",
                "--local-source",
            ]
            + list(user_arguments),
            calls,
        )

    def test_equals_form_version_mismatch_is_rejected(self) -> None:
        result, _, _ = self.run_bootstrap(("--version=9.9.9",))

        self.assertNotEqual(0, result.returncode)
        self.assertIn("but source VERSION is 1.1.1", result.stderr)

    def test_equals_form_options_require_a_value(self) -> None:
        result, _, _ = self.run_bootstrap(("--version=",))

        self.assertEqual(2, result.returncode)
        self.assertIn("--version requires a value", result.stderr)

    def test_remote_zero_argument_bootstrap_requires_a_terminal(self) -> None:
        result, home, calls = self.run_remote_bootstrap()

        self.assertEqual(2, result.returncode, result.stderr)
        self.assertIn("interactive installation requires a terminal", result.stderr)
        runtime_calls = [line for line in calls if "-m scripts.install.main" in line]
        self.assertEqual(1, len(runtime_calls), calls)
        self.assertFalse((home / ".codex").exists())

    def test_remote_explicit_bootstrap_downloads_and_installs_once(self) -> None:
        result, home, calls = self.run_remote_bootstrap(
            ("codex", "install", "--components", "hukuhaka-report-planner", "--dry-run", "--yes")
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Downloading hukuhaka-harness v1.1.1...", result.stdout)
        self.assertNotIn("unbound variable", result.stderr)
        runtime_calls = [line for line in calls if "-m scripts.install.main" in line]
        self.assertEqual(1, len(runtime_calls), calls)
        self.assertIn("[dry-run] plugin add hukuhaka-report-planner@hukuhaka-harness", result.stdout)

    def test_remote_bootstrap_ignores_a_lookalike_runtime_in_the_caller_cwd(self) -> None:
        # The documented `curl ... | bash` run from inside any directory that
        # happens to hold scripts/install/main.py -- a hukuhaka-harness clone
        # being the obvious one. The downloaded, version-checked tree must be
        # what executes; before this was fixed the caller's copy won outright,
        # which made an attacker-writable cwd a code-execution vector during an
        # install of a verified release.
        result, home, _ = self.run_remote_bootstrap(
            (
                "codex",
                "install",
                "--components",
                "hukuhaka-report-planner",
                "--dry-run",
                "--yes",
            ),
            decoy=True,
        )
        marker = home.parent / "decoy-ran.txt"

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse(marker.exists(), "the caller's cwd shadowed the verified runtime")
        self.assertIn("[dry-run] plugin add hukuhaka-report-planner@hukuhaka-harness", result.stdout)


if __name__ == "__main__":
    unittest.main()
