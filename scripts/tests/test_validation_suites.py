from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from scripts.tests.run_unittest_suites import Suite, SuiteRunner


class ValidationSuitesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def suite(self, name: str, body: str) -> Suite:
        path = self.root / name
        path.mkdir()
        (path / "test_fixture.py").write_text(
            "import unittest, os, time\nfrom pathlib import Path\n"
            "class Fixture(unittest.TestCase):\n    def test_check(self):\n" + body,
        )
        return Suite(name, name, name)

    def runner(self, jobs=2, profile="private", timeout=10) -> SuiteRunner:
        return SuiteRunner(self.root, self.root / "logs", profile, jobs, timeout)

    def test_two_suites_reach_a_barrier_concurrently(self) -> None:
        suites = []
        for own, peer in (("a", "b"), ("b", "a")):
            suites.append(self.suite(own,
                "        Path({!r}).touch()\n".format(str(self.root / (own + ".ready"))) +
                "        until = time.monotonic() + 5\n"
                "        while not Path({!r}).exists() and time.monotonic() < until:\n".format(str(self.root / (peer + ".ready"))) +
                "            time.sleep(0.01)\n"
                "        self.assertTrue(Path({!r}).exists())\n".format(str(self.root / (peer + ".ready"))),
            ))
        self.assertEqual(["pass", "pass"], [status for status, _ in self.runner().run(tuple(suites))])

    def test_failure_is_aggregated_and_live_opt_in_is_not_inherited(self) -> None:
        good = self.suite("good", "        self.assertEqual('0', os.environ['HUKUHAKA_RUN_LIVE_CLI'])\n")
        bad = self.suite("bad", "        self.fail('deliberate failure')\n")
        for jobs in (1, 2):
            results = self.runner(jobs=jobs).run((bad, good))
            self.assertEqual(["fail", "pass"], [status for status, _ in results])
            self.assertIn("deliberate failure", results[0][1])

    def test_missing_suites_fail_private_and_only_private_suites_skip_public(self) -> None:
        suites = (Suite("shared", "absent-shared", "shared"), Suite("private", "absent-private", "private", True))
        self.assertEqual(["fail", "fail"], [s for s, _ in self.runner().run(suites)])
        self.assertEqual(["fail", "skip"], [s for s, _ in self.runner(profile="public").run(suites)])

    def test_timeout_stops_and_reaps_the_suite(self) -> None:
        slow = self.suite("slow", "        time.sleep(30)\n")
        runner = self.runner(timeout=0.5)
        started = time.monotonic()
        result = runner.run((slow,))
        self.assertEqual("fail", result[0][0])
        self.assertIn("timeout", result[0][1])
        self.assertFalse(runner.processes)
        self.assertLess(time.monotonic() - started, 5)


if __name__ == "__main__":
    unittest.main()
