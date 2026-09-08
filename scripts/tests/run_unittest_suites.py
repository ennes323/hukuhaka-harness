#!/usr/bin/env python3
"""Run independent unittest suites with bounded concurrency and separate logs."""

from __future__ import annotations

import argparse
import concurrent.futures
import os
import signal
import subprocess
import sys
import threading
import time
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
    Suite("installer", "scripts/tests", "transactional installer state, rollback, drift, and recovery"),
    Suite("prepush", "scripts/prepush/tests", "private push policy, public readiness, and workflow completion", True),
    Suite("release", "scripts/release/tests", "release build safety + exact-tag public publish", True),
    Suite("eval", "eval/tests", "eval v2 transcript normalization and evidence contracts", True),
)


class SuiteRunner:
    def __init__(self, root: Path, logs: Path, profile: str, jobs: int, timeout: float = 1800):
        self.root, self.logs, self.profile, self.jobs, self.timeout = root, logs, profile, jobs, timeout
        self.processes: set[subprocess.Popen] = set()
        self.lock = threading.Lock()
        self.cancelled = threading.Event()

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
        started = time.monotonic()
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", HUKUHAKA_RUN_LIVE_CLI="0")
        timed_out = False
        with log.open("wb") as output:
            with self.lock:
                if self.cancelled.is_set():
                    return "fail", suite.label + " — interrupted"
                process = subprocess.Popen(
                    [sys.executable, "-m", "unittest", "discover", "-s", str(path), "-p", "test_*.py"],
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
        if code == 0 and not self.cancelled.is_set():
            return "pass", "{} ({:.2f}s)".format(suite.label, elapsed)
        tail = " ".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-8:])
        reason = "timeout" if timed_out else "exit {}".format(code)
        return "fail", "{} ({:.2f}s, {}) — {}".format(suite.label, elapsed, reason, tail)

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
    parser.add_argument("--profile", choices=("private", "public"), required=True)
    parser.add_argument("--log-dir", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args(argv)
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
        print(status + "\t" + message.replace("\t", " "), flush=True)
    return 1 if any(status == "fail" for status, _ in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
