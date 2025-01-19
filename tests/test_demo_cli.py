"""Check evidence preservation and nonzero CLI failures without a board."""

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("demo_cli", ROOT / "scripts/demo.py")
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


class DemoCliTests(unittest.TestCase):
    def prepare(self, directory):
        root = Path(directory)
        bitstream = root / "test.bin"
        bitstream.write_bytes(b"test fixture, not an FPGA image")
        report = root / "test-build.json"
        report.write_text(json.dumps(dict(status="passed", device="iCE40UP5K", package="sg48",
                                         clock_mhz=12, seed=1, lut_mapper="test fixture", versions={},
                                         artifact_sha256={"quoteextrema.bin": hashlib.sha256(bitstream.read_bytes()).hexdigest()})))
        output = root / "session.json"
        argv = ["demo.py", "--port", "TEST_ONLY", "--board-revision", "test fixture",
                "--cable", "test fixture", "--driver", "test fixture",
                "--bitstream", str(bitstream), "--build-report", str(report), "--output", str(output)]
        return argv, bitstream, output

    def test_serial_open_failure_is_saved_and_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as directory:
            argv, _, output = self.prepare(directory)
            serial = SimpleNamespace(VERSION="test fixture", EIGHTBITS=8, PARITY_NONE="N", STOPBITS_ONE=1,
                                     Serial=Mock(side_effect=OSError("test port unavailable")))
            with patch.object(sys, "argv", argv), patch.dict(sys.modules, {"serial": serial}), \
                    redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(demo.main(), 1)
            saved = json.loads(output.read_text())
            self.assertEqual(saved["status"], "failed")
            self.assertIn("test port unavailable", saved["error"])
            self.assertEqual(saved["events"], [])
            self.assertFalse(saved["complete_physical_acceptance"])

    def test_existing_session_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            argv, _, output = self.prepare(directory)
            output.write_text("original evidence")
            with patch.object(sys, "argv", argv), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    demo.main()
            self.assertEqual(error.exception.code, 2)
            self.assertEqual(output.read_text(), "original evidence")

    def test_wrong_image_fails_before_touching_serial(self):
        with tempfile.TemporaryDirectory() as directory:
            argv, bitstream, output = self.prepare(directory)
            bitstream.write_bytes(b"changed image")
            serial = SimpleNamespace(Serial=Mock())
            with patch.object(sys, "argv", argv), patch.dict(sys.modules, {"serial": serial}), \
                    redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    demo.main()
            self.assertEqual(error.exception.code, 2)
            serial.Serial.assert_not_called()
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
