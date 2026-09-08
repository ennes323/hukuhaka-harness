from __future__ import annotations

import os
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.tests import docker_e2e as docker
from scripts.verification import FRESH_ENV


class DockerVerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        tests = self.source / "scripts/tests"
        tests.mkdir(parents=True)
        (tests / "codex-e2e-version.txt").write_text("0.149.0\n")
        (tests / "codex-real-e2e.Dockerfile").write_text("FROM fixture\n")
        self.image = "sha256:" + "a" * 64
        self.build_reference = ""
        self.fresh_attestation = True
        self.valid_image_data = True
        self.layers = ["sha256:" + "c" * 64]
        self.context, self.server = "context-a", "server-a linux arm64 version-a"
        self.calls = []
        self.fail_run = False
        self.cache = self.root / "cache"
        for patcher in (
            mock.patch.object(docker, "command", side_effect=self.command),
            mock.patch.object(docker, "environment_digest", return_value="environment"),
            mock.patch.object(docker, "tool_identity", return_value="docker-cli"),
            mock.patch.dict(os.environ, {FRESH_ENV: "0"}),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def command(self, args, **kwargs):
        self.calls.append(args)
        if args[1:3] == ["context", "show"]:
            return self.context
        if args[1] == "info":
            return self.server
        if args[1] == "build":
            # A fresh attestation can change the build index without changing
            # the image/config ID that Docker actually executes.
            self.build_reference = ("sha256:" + format(self.count("build"), "064x")
                                    if self.fresh_attestation else self.image)
            Path(args[args.index("--iidfile") + 1]).write_text(self.build_reference)
            return ""
        if args[1:3] == ["image", "inspect"]:
            self.assertEqual(self.build_reference, args[-1])
            return json.dumps([{
                "Id": self.build_reference, "Os": "linux", "Architecture": "arm64",
                "Config": {"Env": ["FIXTURE_PAYLOAD=" + self.image], "Entrypoint": ["python3"], "User": "node"}
                          if self.valid_image_data else None,
                "RootFS": {"Type": "layers", "Layers": self.layers},
            }])
        if args[1] == "run":
            self.assertEqual(self.build_reference, args[-1])
            self.assertNotIn("hukuhaka-codex-e2e:0.149.0", args)
            if self.fail_run:
                raise subprocess.CalledProcessError(1, args)
            return ""
        self.fail("unexpected Docker call: " + repr(args))

    def count(self, action):
        return sum(args[1] == action for args in self.calls)

    def test_repeated_build_reuses_only_the_immutable_image_result(self) -> None:
        self.assertIn("[verified]", docker.verify(self.source, self.cache))
        self.assertIn("[reuse]", docker.verify(self.source, self.cache))
        self.assertEqual(2, self.count("build"))
        self.assertEqual(1, self.count("run"))
        self.assertGreaterEqual(self.count("info"), 2)

    def test_changed_image_context_server_or_source_requires_a_new_run(self) -> None:
        docker.verify(self.source, self.cache)
        self.image = "sha256:" + "b" * 64
        docker.verify(self.source, self.cache)
        self.context = "context-b"
        docker.verify(self.source, self.cache)
        self.server = "server-b linux amd64 version-b"
        docker.verify(self.source, self.cache)
        (self.source / "new-file").write_text("changed")
        docker.verify(self.source, self.cache)
        self.assertEqual(5, self.count("run"))

    def test_failed_container_does_not_create_a_reusable_success(self) -> None:
        self.fail_run = True
        with self.assertRaises(subprocess.CalledProcessError):
            docker.verify(self.source, self.cache)
        self.fail_run = False
        self.assertIn("[verified]", docker.verify(self.source, self.cache))
        self.assertEqual(2, self.count("run"))

    def test_forced_fresh_builds_and_runs_again(self) -> None:
        docker.verify(self.source, self.cache)
        with mock.patch.dict(os.environ, {FRESH_ENV: "1"}):
            self.assertIn("[verified]", docker.verify(self.source, self.cache))
        self.assertEqual(2, self.count("run"))

    def test_standalone_checkout_does_not_reuse(self) -> None:
        (self.source / ".git").mkdir()
        docker.verify(self.source, self.cache)
        docker.verify(self.source, self.cache)
        self.assertEqual(2, self.count("run"))
        self.assertFalse(self.cache.exists())

    def test_missing_image_configuration_runs_normally_without_reusing_success(self) -> None:
        self.valid_image_data = False
        docker.verify(self.source, self.cache)
        docker.verify(self.source, self.cache)
        self.assertEqual(2, self.count("run"))
        self.assertFalse(self.cache.exists())

    def test_classic_builder_reuses_its_immutable_image_id(self) -> None:
        self.fresh_attestation = False
        docker.verify(self.source, self.cache)
        self.assertIn("[reuse]", docker.verify(self.source, self.cache))
        self.assertEqual(1, self.count("run"))

    def test_ordered_filesystem_layers_are_part_of_the_reuse_identity(self) -> None:
        self.layers.append("sha256:" + "d" * 64)
        docker.verify(self.source, self.cache)
        self.layers.reverse()
        self.assertIn("[verified]", docker.verify(self.source, self.cache))
        self.assertEqual(2, self.count("run"))


if __name__ == "__main__":
    unittest.main()
