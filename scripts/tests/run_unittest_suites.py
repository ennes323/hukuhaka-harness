#!/usr/bin/env python3
"""Run independent unittest suites with bounded concurrency and separate logs."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import signal
import subprocess
import sys
import threading
import time
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Suite:
    name: str
    path: str
    label: str
    private: bool = False


SUITES = (
    Suite("installer", "scripts/tests", "scripts unit and integration tests"),
    Suite("prepush", "scripts/prepush/tests", "private push policy, public readiness, and workflow completion", True),
    Suite("release", "scripts/release/tests", "release build safety + exact-tag public publish", True),
    Suite("eval", "eval/tests", "eval v2 transcript normalization and evidence contracts", True),
)

COUNT_FIELDS = (
    ("tests_discovered", "tests discovered"), ("tests_run", "tests run"),
    ("tests_executed", "tests executed (excluding whole-test skips)"),
    ("failures", "failures"), ("errors", "errors"),
    ("skipped", "skipped events"), ("expected_failures", "expected failures"),
    ("unexpected_successes", "unexpected successes"),
)


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.started_ids: set[str] = set()

    def startTest(self, test):
        self.started_ids.add(test.id())
        super().startTest(test)


def run_child(path: Path, result_file: Path) -> int:
    """Collect unittest's own result rather than interpreting its text output."""
    sys.path.insert(0, str(Path.cwd()))
    suite = unittest.defaultTestLoader.discover(str(path), pattern="test_*.py")
    discovered = suite.countTestCases()
    result = unittest.TextTestRunner(verbosity=1, resultclass=RecordedResult).run(suite)
    report = {
        "tests_discovered": discovered,
        "tests_run": result.testsRun,
        "tests_executed": result.testsRun - sum(test.id() in result.started_ids for test, _ in result.skipped),
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "expected_failures": len(result.expectedFailures),
        "unexpected_successes": len(result.unexpectedSuccesses),
        "skip_reasons": [{"test": test.id(), "reason": reason} for test, reason in result.skipped],
        "failure_details": [
            {"kind": kind, "test": test.id(), "traceback": traceback}
            for kind, entries in (("failure", result.failures), ("error", result.errors))
            for test, traceback in entries
        ] + [{"kind": "unexpected success", "test": test.id(), "traceback": ""}
             for test in result.unexpectedSuccesses],
    }
    result_file.write_text(json.dumps(report) + "\n", encoding="utf-8")
    return 0 if result.wasSuccessful() and discovered else 1


def counts(report: dict) -> str:
    return ", ".join("{} {}".format(report[key], label) for key, label in COUNT_FIELDS)


class SuiteRunner:
    def __init__(self, root: Path, logs: Path, profile: str, jobs: int, timeout: float = 1800):
        self.root, self.logs, self.profile, self.jobs, self.timeout = root, logs, profile, jobs, timeout
        self.processes: set[subprocess.Popen] = set()
        self.lock = threading.Lock()
        self.cancelled = threading.Event()
        self.reports: dict[str, dict] = {}

    @staticmethod
    def stop(process: subprocess.Popen) -> None:
        try:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except ProcessLookupError:
            pass

    def cancel(self) -> None:
        self.cancelled.set()
        with self.lock:
            for process in self.processes:
                self.stop(process)

    def run_one(self, suite: Suite) -> tuple[str, str]:
        path = self.root / suite.path
        if not path.is_dir() or not any(path.glob("test_*.py")):
            status = "skip" if suite.private and self.profile == "public" else "fail"
            return status, suite.label + " — suite is missing"
        if suite.name == "eval" and not (self.root / "eval/run.py").is_file():
            return ("fail" if self.profile == "private" else "skip"), "eval runner is missing"
        self.logs.mkdir(parents=True, exist_ok=True)
        log = self.logs / (suite.name + "-tests.log")
        result_file = self.logs / (suite.name + "-result.json")
        result_file.unlink(missing_ok=True)
        started = time.monotonic()
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", HUKUHAKA_RUN_LIVE_CLI="0")
        timed_out = False
        with log.open("wb") as output:
            with self.lock:
                if self.cancelled.is_set():
                    return "fail", suite.label + " — interrupted"
                process = subprocess.Popen(
                    [sys.executable, str(Path(__file__).resolve()), "--suite-path", str(path),
                     "--result-file", str(result_file.resolve())],
                    cwd=self.root, env=environment, stdout=output, stderr=subprocess.STDOUT,
                    start_new_session=(os.name == "posix"),
                )
                self.processes.add(process)
            try:
                try:
                    code = process.wait(timeout=self.timeout)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    self.stop(process)
                    code = process.wait()
            finally:
                with self.lock:
                    self.processes.discard(process)
        elapsed = time.monotonic() - started
        try:
            report = json.loads(result_file.read_text()) if result_file.is_file() else None
        except (OSError, ValueError):
            report = None
        detail = "no unittest result recorded"
        if report is not None:
            with self.lock:
                self.reports[suite.name] = report
            detail = counts(report)
            for failure in report["failure_details"]:
                summary = failure["traceback"].strip().splitlines()
                detail += "; {} {}: {}".format(failure["kind"], failure["test"],
                                                summary[-1] if summary else failure["kind"])
            if report["skip_reasons"]:
                detail += "; skip reasons: " + "; ".join(
                    "{}: {}".format(item["test"], item["reason"]) for item in report["skip_reasons"])
        if code == 0 and report is not None and report["tests_discovered"] and not self.cancelled.is_set():
            status = "skip" if report["skipped"] and not report["tests_executed"] else "pass"
            return status, "{} ({:.2f}s) — {}".format(suite.label, elapsed, detail)
        tail = " ".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-8:])
        reason = "timeout" if timed_out else "exit {}".format(code)
        return "fail", "{} ({:.2f}s, {}) — {}; {}".format(suite.label, elapsed, reason, detail, tail)

    def run(self, suites: tuple[Suite, ...] = SUITES) -> list[tuple[str, str]]:
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=self.jobs)
        try:
            futures = [pool.submit(self.run_one, suite) for suite in suites]
            return [future.result() for future in futures]
        except BaseException:
            self.cancel()
            raise
        finally:
            pool.shutdown(wait=True)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("private", "public"))
    parser.add_argument("--log-dir", type=Path)
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--suite-path", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--result-file", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.suite_path is not None:
        if args.result_file is None:
            parser.error("--suite-path requires --result-file")
        return run_child(args.suite_path, args.result_file)
    if args.profile is None or args.log_dir is None:
        parser.error("--profile and --log-dir are required")
    if not 1 <= args.jobs <= 4:
        parser.error("jobs must be an integer from 1 to 4")
    runner = SuiteRunner(ROOT, args.log_dir, args.profile, args.jobs)
    def interrupted(signum: int, frame: object) -> None:
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    try:
        results = runner.run()
    except KeyboardInterrupt:
        print("fail\tunit test suites interrupted", flush=True)
        return 130
    for status, message in results:
        print(status + "\t" + " ".join(message.split()), flush=True)
    if runner.reports:
        total = {key: sum(report[key] for report in runner.reports.values())
                 for key, _ in COUNT_FIELDS}
        print("info\tunittest totals (completed result files): " + counts(total), flush=True)
    return 1 if any(status == "fail" for status, _ in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
