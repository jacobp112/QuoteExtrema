"""Checks that saved rejection cases really exercise state preservation."""

import json
from pathlib import Path
import unittest

from quoteextrema import DeviceModel, ask, bid


class CorpusTests(unittest.TestCase):
    def test_every_malformed_case_preserves_both_sides(self):
        cases = json.loads((Path(__file__).parent / "corpus/malformed.json").read_text())
        self.assertEqual(len({case["name"] for case in cases}), len(cases))
        for case in cases:
            with self.subTest(case=case["name"]):
                device = DeviceModel()
                for packet in (bid(100), ask(120)):
                    for byte in packet:
                        device.step(data=byte, valid=True)
                    device.step()
                before = device.state.snapshot(0)
                for byte in bytes.fromhex(case["hex"]):
                    device.step(data=byte, valid=True)
                device.step(abort=case.get("abort", False))
                device.step()
                self.assertEqual(device.state.snapshot(0), before)
                diagnostics = {**device.receiver.counts, **device.counts}
                self.assertTrue(any(diagnostics[key] for key in
                                    ("crc_errors", "invalid_lengths", "semantic_errors",
                                     "incomplete_frames", "discarded_bytes")))


if __name__ == "__main__":
    unittest.main()
