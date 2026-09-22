from __future__ import annotations

import tempfile
import json
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
            self.assertIn("1 failures", results[0][1])
            self.assertIn("1 tests run", results[1][1])

    def test_partial_and_all_skips_report_counts_and_reasons(self) -> None:
        partial = self.suite("partial", "        self.assertTrue(True)\n")
        fixture = self.root / partial.path / "test_fixture.py"
        fixture.write_text(fixture.read_text() +
            "    @unittest.skip('external service unavailable')\n"
            "    def test_external(self):\n        self.fail('must not run')\n")
        skipped = self.suite("skipped", "        self.skipTest('model tests require explicit opt-in')\n")
        runner = self.runner()
        results = runner.run((partial, skipped))
        self.assertEqual(["pass", "skip"], [status for status, _ in results])
        self.assertIn("2 tests run", results[0][1])
        self.assertIn("1 skipped", results[0][1])
        self.assertIn("test_fixture.Fixture.test_external: external service unavailable", results[0][1])
        self.assertIn("model tests require explicit opt-in", results[1][1])
        report = json.loads((runner.logs / "partial-result.json").read_text())
        self.assertEqual(2, report["tests_discovered"])
        self.assertEqual(2, report["tests_run"])
        self.assertEqual(1, report["skipped"])
        self.assertEqual(0, report["failures"])

    def test_buffered_product_output_does_not_hide_failure_identity(self) -> None:
        suite = self.suite("noisy_failure",
            "        for value in range(20):\n"
            "            print('product output', value)\n"
            "        self.fail('specific regression')\n")
        runner = self.runner()
        result = runner.run((suite,))[0]
        self.assertEqual("fail", result[0])
        self.assertIn("failure test_fixture.Fixture.test_check: AssertionError: specific regression", result[1])
        report = json.loads((runner.logs / "noisy_failure-result.json").read_text())
        self.assertEqual("test_fixture.Fixture.test_check", report["failure_details"][0]["test"])
        self.assertIn("AssertionError: specific regression", report["failure_details"][0]["traceback"])

    def test_empty_discovery_fails_but_class_skip_is_visible(self) -> None:
        empty = self.suite("empty", "        pass\n")
        (self.root / empty.path / "test_fixture.py").write_text("# No test cases\n")
        skipped = self.suite("class_skip", "        pass\n")
        fixture = self.root / skipped.path / "test_fixture.py"
        fixture.write_text(fixture.read_text().replace(
            "    def test_check(self):", "    @classmethod\n"
            "    def setUpClass(cls):\n        raise unittest.SkipTest('platform unavailable')\n"
            "    def test_check(self):"))
        results = self.runner().run((empty, skipped))
        self.assertEqual(["fail", "skip"], [status for status, _ in results])
        self.assertIn("0 tests discovered", results[0][1])
        self.assertIn("platform unavailable", results[1][1])

    def test_skipped_subtests_do_not_hide_the_executed_parent_test(self) -> None:
        suite = self.suite("subtests",
            "        for value in (1, 2):\n"
            "            with self.subTest(value=value):\n"
            "                self.skipTest('optional subcase')\n"
            "        self.assertEqual(4, 2 + 2)\n")
        runner = self.runner()
        result = runner.run((suite,))[0]
        self.assertEqual("pass", result[0])
        report = json.loads((runner.logs / "subtests-result.json").read_text())
        self.assertEqual(1, report["tests_run"])
        self.assertEqual(1, report["tests_executed"])
        self.assertEqual(2, report["skipped"])
        self.assertIn("2 skipped events", result[1])
        self.assertIn("test_check (value=1): optional subcase", result[1])
        self.assertIn("test_check (value=2): optional subcase", result[1])

    def test_errors_and_expected_outcomes_remain_distinct(self) -> None:
        suite = self.suite("outcomes", "        raise RuntimeError('fixture error')\n")
        fixture = self.root / suite.path / "test_fixture.py"
        fixture.write_text(fixture.read_text() +
            "    @unittest.expectedFailure\n"
            "    def test_expected(self):\n        self.fail('known')\n"
            "    @unittest.expectedFailure\n"
            "    def test_unexpected(self):\n        pass\n")
        result = self.runner().run((suite,))[0]
        self.assertEqual("fail", result[0])
        for detail in ("3 tests run", "1 errors", "1 expected failures", "1 unexpected successes"):
            self.assertIn(detail, result[1])
        self.assertIn("error test_fixture.Fixture.test_check: RuntimeError: fixture error", result[1])
        self.assertIn("unexpected success test_fixture.Fixture.test_unexpected", result[1])

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
