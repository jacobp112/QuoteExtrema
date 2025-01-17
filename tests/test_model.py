import unittest

from quoteextrema import DeviceModel, QuoteState, Snapshot, ask, bid, decode_snapshot, frame, read, reset
from quoteextrema.protocol import Receiver, crc8


class ProtocolTests(unittest.TestCase):
    def test_documented_vectors(self):
        self.assertEqual(crc8(b"123456789"), 0xF4)
        expected = [(bid(0), "a5050100000000ef"),
                    (ask(0xFFFFFFFF), "a50502ffffffff97"),
                    (bid(100), "a5050164000000e2"),
                    (ask(90), "a505025a00000029"),
                    (read(0x1234), "a50303341254"),
                    (reset(), "a5010409"),
                    (Snapshot(0x1234, False, False, 0, 0).encode(),
                     "a50c8334120000000000000000006f"),
                    (Snapshot(0x1234, True, True, 100, 90).encode(),
                     "a50c83341203640000005a0000007a")]
        for actual, golden in expected:
            self.assertEqual(actual.hex(), golden)

    def test_host_rejects_out_of_range_prices_and_ids(self):
        for price in (-1, 1 << 32, 1.5, "100"):
            for encode in (bid, ask):
                with self.assertRaises(ValueError):
                    encode(price)
        for request_id in (-1, 1 << 16):
            with self.assertRaises(ValueError):
                read(request_id)
        for payload in (b"", bytes(17)):
            with self.assertRaises(ValueError):
                frame(payload)

    def test_snapshot_validation(self):
        snapshot = Snapshot(65535, True, True, 0, 0xFFFFFFFF)
        self.assertEqual(decode_snapshot(snapshot.encode()), snapshot)
        for data in (b"", snapshot.encode()[:-1], snapshot.encode()[:-1] + b"\x00",
                     frame(b"\x83\x00\x00\x04" + bytes(8)),
                     frame(b"\x83\x00\x00\x00\x01" + bytes(7))):
            with self.assertRaises(ValueError):
                decode_snapshot(data)

    def test_abort_keeps_an_earlier_completed_command(self):
        receiver = Receiver()
        for byte in bid(100):
            self.assertIsNone(receiver.step(data=byte, valid=True))
        self.assertEqual(receiver.step(abort=True), b"\x01\x64\x00\x00\x00")
        self.assertEqual(receiver.counts["incomplete_frames"], 0)


class StateTests(unittest.TestCase):
    def test_extremes_side_isolation_and_flags(self):
        state = QuoteState()
        self.assertEqual(state.snapshot(1), Snapshot(1, False, False, 0, 0))
        for price in (100, 100, 90, 110, 0xFFFFFFFF, 0):
            state.observe("bid", price)
        self.assertEqual(state.snapshot(2), Snapshot(2, True, False, 0xFFFFFFFF, 0))
        for price in (120, 120, 130, 115, 0, 0xFFFFFFFF):
            state.observe("ask", price)
        self.assertEqual(state.snapshot(3), Snapshot(3, True, True, 0xFFFFFFFF, 0))
        state.clear()
        state.observe("bid", 0)
        state.observe("ask", 0xFFFFFFFF)
        self.assertEqual(state.snapshot(4), Snapshot(4, True, True, 0, 0xFFFFFFFF))

    def test_rejected_quote_preserves_state(self):
        state = QuoteState(True, 100, True, 120)
        for side, price in (("other", 100), ("bid", -1), ("ask", 1 << 32)):
            before = state.snapshot(0)
            with self.assertRaises(ValueError):
                state.observe(side, price)
            self.assertEqual(state.snapshot(0), before)


class DeviceTests(unittest.TestCase):
    def setUp(self):
        self.device = DeviceModel()
        self.device.step(rst=True)

    def send(self, data, **signals):
        for byte in data:
            self.device.step(data=byte, valid=True, **signals)
        self.device.step(**signals)

    def test_snapshot_survives_quotes_and_serial_reset(self):
        stall = dict(tx_ready=False, tx_idle=False)
        self.send(bid(100), **stall)
        self.send(ask(120), **stall)
        self.send(read(42), **stall)
        original = self.device.tx_frame
        self.send(bid(110), **stall)
        self.send(reset(), **stall)
        self.assertEqual(self.device.tx_frame, original)
        self.assertEqual(decode_snapshot(original), Snapshot(42, True, True, 100, 120))
        self.assertEqual(self.device.state, QuoteState())
        self.assertEqual(self.device.receiver.counts["valid_frames"], 5)

    def test_busy_read_and_completion_edge(self):
        self.send(read(1), tx_ready=False)
        self.send(read(2), tx_ready=False)
        self.assertEqual(self.device.counts["busy_reads"], 1)
        for _ in range(15):
            self.device.step()
        self.assertEqual(self.device.tx_phase, "drain")
        self.device.receiver.pending = b"\x03\x03\x00"
        self.device.step(tx_idle=True)
        self.assertFalse(self.device.busy)
        self.assertEqual(self.device.counts["busy_reads"], 2)

    def test_invalid_frames_and_commands_preserve_state(self):
        self.send(bid(100))
        self.send(ask(120))
        expected = self.device.state.snapshot(0)
        bad = bytearray(bid(1000))
        bad[-1] ^= 1
        for data in (bad, b"\xa5\x00", b"\xa5\x11", frame(b"\x01"),
                     frame(b"\x7f"), frame(b"\x04\x00"), frame(b"\x83")):
            self.send(data)
            self.assertEqual(self.device.state.snapshot(0), expected)
        self.assertEqual(self.device.receiver.counts["crc_errors"], 1)
        self.assertEqual(self.device.receiver.counts["invalid_lengths"], 2)
        self.assertEqual(self.device.counts["semantic_errors"], 4)

    def test_hardware_reset_cancels_pending_quote_and_response(self):
        self.send(read(1), tx_ready=False)
        for byte in bid(100):
            self.device.step(data=byte, valid=True, tx_ready=False)
        self.device.step(rst=True)
        self.assertEqual(self.device.state, QuoteState())
        self.assertFalse(self.device.busy)
        self.assertTrue(all(x == 0 for x in self.device.receiver.counts.values()))


if __name__ == "__main__":
    unittest.main()
