from __future__ import annotations

import importlib.util
import errno
import json
import os
import pty
import select
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "marketplace/hukuhaka-project-docs/skills/project-docs/scripts/project_docs.py"
SPEC = importlib.util.spec_from_file_location("project_docs_session", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def envelopes(raw: str) -> list[dict]:
    result = []
    decoder = json.JSONDecoder()
    offset = 0
    while raw[offset:].strip():
        item, offset = decoder.raw_decode(raw, offset + len(raw[offset:]) - len(raw[offset:].lstrip()))
        result.append(item)
    return result


class ReaderSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "docs").mkdir()
        (self.root / "docs/architecture.md").write_text("# Architecture\nDetails.\n", encoding="utf-8")
        document = {
            "id": "architecture", "path": "docs/architecture.md", "role": "contract",
            "status": "current", "authority": "normative", "summary": "Architecture",
            "appliesTo": ["src/**"], "readWhen": ["architecture changes"],
        }
        (self.root / "project-docs.json").write_text(
            json.dumps({"schemaVersion": 1, "documents": [document]}), encoding="utf-8")
        self.args = [sys.executable, str(SCRIPT), "reader-session", "--root", str(self.root),
                     "--max-documents", "2", "--max-bytes", str(MODULE.MAX_READER_BYTES)]

    def run_selection(self, raw: bytes) -> tuple[int, list[dict]]:
        process = subprocess.Popen(self.args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert process.stdin and process.stdout
        # The catalog must be available before any selection is sent.
        readable, _, _ = select.select([process.stdout], [], [], 2)
        self.assertTrue(readable)
        prefix = os.read(process.stdout.fileno(), 65536)
        self.assertEqual("ready", json.loads(prefix)["status"])
        suffix, stderr = process.communicate(raw, timeout=3)
        self.assertFalse(stderr, stderr.decode())
        return process.returncode, envelopes((prefix + suffix).decode())

    def test_pipe_selected_bytes_match_legacy_read(self) -> None:
        code, output = self.run_selection(b'{"ids":["architecture"]}\n')
        self.assertEqual(0, code)
        self.assertEqual("reader-catalog", output[0]["command"])
        legacy = subprocess.run(
            [sys.executable, str(SCRIPT), "reader-read", "--root", str(self.root),
             "--ids", "architecture", "--max-documents", "2", "--max-bytes", str(MODULE.MAX_READER_BYTES)],
            capture_output=True, check=True,
        )
        self.assertEqual(json.loads(legacy.stdout), output[1])

    def test_invalid_selections_never_call_reader_read(self) -> None:
        catalog = MODULE.reader_catalog(self.root.resolve(), "project-docs.json")
        cases = [
            b'{"ids":["architecture","architecture"]}\n',
            b'{"ids":["unknown"]}\n', b'{"ids":["../secret"]}\n',
            b'{"ids":["architecture"],"root":"/"}\n',
            b'{"ids":[],"command":"sh"}\n',
            b'{"ids":[],"ids":[]}\n', b'\xff\n',
        ]
        for raw in cases:
            with self.subTest(raw=raw), mock.patch.object(MODULE, "reader_read") as read:
                r, w = os.pipe()
                try:
                    os.write(w, raw)
                    os.close(w)
                    with mock.patch.object(MODULE, "reader_catalog", return_value=catalog), \
                         mock.patch.object(MODULE, "_json") as emit:
                        code = MODULE.reader_session(self.root.resolve(), "project-docs.json", 2, MODULE.MAX_READER_BYTES, fd=r)
                    self.assertEqual(1, code)
                    self.assertEqual("session.invalid-selection", emit.call_args_list[1].args[0]["errors"][0]["code"])
                    read.assert_not_called()
                finally:
                    os.close(r)

    def test_empty_close_and_budgets_are_frozen(self) -> None:
        code, output = self.run_selection(b'{"ids":[]}\n')
        self.assertEqual(0, code)
        self.assertEqual("complete", output[1]["status"])
        self.assertEqual([], output[1]["documents"])
        self.assertEqual(0, output[1]["documentBytes"])
        self.assertEqual(output[0]["manifestBytes"], output[1]["manifestBytes"])
        self.args[-1] = str(output[0]["manifestBytes"])
        code, output = self.run_selection(b'{"ids":["architecture"]}\n')
        self.assertEqual(1, code)
        self.assertEqual("partial", output[1]["status"])
        self.assertEqual("selection.byte-limit", output[1]["errors"][0]["code"])

    def test_eof_partial_line_timeout_and_input_bound(self) -> None:
        for raw, expected in [(b"", "session.eof"), (b'{"ids":[]}', "session.eof"),
                              (b" " * (MODULE.MAX_SESSION_INPUT_BYTES + 1), "session.invalid-selection")]:
            with self.subTest(expected=expected, size=len(raw)):
                code, output = self.run_selection(raw)
                self.assertEqual(1, code)
                self.assertEqual(expected, output[1]["errors"][0]["code"])
        r, w = os.pipe()
        try:
            os.write(w, b'{"ids":')
            with mock.patch.object(MODULE, "_json") as emit:
                code = MODULE.reader_session(self.root.resolve(), "project-docs.json", 2, MODULE.MAX_READER_BYTES,
                                             fd=r, timeout=0.01)
            self.assertEqual(1, code)
            self.assertEqual("session.timeout", emit.call_args_list[1].args[0]["errors"][0]["code"])
        finally:
            os.close(r)
            os.close(w)

    def test_preflight_and_manifest_budget_do_not_wait(self) -> None:
        for args, expected_count in [
            (self.args[:-1] + ["1"], 1),
            (self.args[:-3] + ["0", "--max-bytes", "10000"], 1),
            (self.args[:4] + ["/nonexistent", "--max-documents", "2", "--max-bytes", "10000"], 1),
        ]:
            with self.subTest(args=args):
                result = subprocess.run(args, stdin=subprocess.PIPE, capture_output=True, timeout=2)
                self.assertNotEqual(0, result.returncode)
                self.assertEqual(expected_count, len(envelopes(result.stdout.decode())))
        self.args[-1] = "1"
        result = subprocess.run(self.args, stdin=subprocess.PIPE, capture_output=True, timeout=2)
        self.assertEqual(1, result.returncode)
        self.assertEqual(["reader-catalog"], [item["command"] for item in envelopes(result.stdout.decode())])

    def test_pty_submission_does_not_echo_selection(self) -> None:
        master, slave = pty.openpty()
        process = subprocess.Popen(self.args, stdin=slave, stdout=slave, stderr=subprocess.PIPE, close_fds=True)
        os.close(slave)
        try:
            data = bytearray()
            while b'"status": "ready"' not in data:
                ready, _, _ = select.select([master], [], [], 2)
                self.assertTrue(ready)
                data.extend(os.read(master, 65536))
            # Wait for the terminal to leave echo mode (catalog is flushed just before this).
            import termios
            for _ in range(1000):
                if not termios.tcgetattr(master)[3] & termios.ECHO:
                    break
            self.assertFalse(termios.tcgetattr(master)[3] & termios.ECHO)
            os.write(master, b'{"ids":["architecture"]}\n')
            while process.poll() is None:
                ready, _, _ = select.select([master], [], [], 2)
                self.assertTrue(ready)
                try:
                    chunk = os.read(master, 65536)
                except OSError as exc:
                    if exc.errno != errno.EIO:
                        raise
                    break  # Linux reports PTY slave closure as EIO.
                if not chunk:
                    break
                data.extend(chunk)
            while select.select([master], [], [], 0)[0]:
                try:
                    chunk = os.read(master, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                data.extend(chunk)
            self.assertEqual(0, process.wait(timeout=2))
            assert process.stderr
            process.stderr.close()
            result = envelopes(data.decode().replace("\r\n", "\n"))
            self.assertEqual(["reader-catalog", "reader-read"], [item["command"] for item in result])
        finally:
            os.close(master)
            if process.poll() is None:
                process.kill()
                process.wait()


if __name__ == "__main__":
    unittest.main()
