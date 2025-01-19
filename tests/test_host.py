"""Host transaction tests with a byte-timed reference transport, no hardware."""

import unittest

from quoteextrema.host import Command, QuoteClient, run_demo
from quoteextrema.model import QuoteState
from quoteextrema.protocol import Receiver, Snapshot


class Clock:
    def __init__(self):
        self.now = 0
        self.on_sleep = lambda: None

    def __call__(self):
        return self.now

    def sleep(self, duration):
        self.now += duration
        self.on_sleep()


class ReferencePort:
    """Advance input in byte periods; a response occupies fifteen periods."""
    def __init__(self, clock, fault=None):
        self.clock, self.fault = clock, fault
        self.receiver, self.state = Receiver(), QuoteState()
        self.rx = bytearray()
        self.tick = self.busy_until = 0
        self.timeout = 0.05
        self.busy_reads = 0
        self.clock.on_sleep = self.idle

    def idle(self):
        self.receiver.step(abort=True)
        self.tick = max(self.tick, self.busy_until)

    def consume(self, payload):
        if not payload:
            return
        kind = payload[0]
        if kind in (1, 2) and len(payload) == 5:
            self.state.observe("bid" if kind == 1 else "ask", int.from_bytes(payload[1:], "little"))
        elif kind == 4 and len(payload) == 1:
            self.state.clear()
        elif kind == 3 and len(payload) == 3:
            if self.tick < self.busy_until:
                self.busy_reads += 1
                return
            snapshot = self.state.snapshot(int.from_bytes(payload[1:], "little"))
            if self.fault == "id":
                snapshot = Snapshot(snapshot.request_id ^ 1, snapshot.bid_valid,
                                    snapshot.ask_valid, snapshot.bid, snapshot.ask)
            elif self.fault == "state":
                snapshot = Snapshot(snapshot.request_id, True, snapshot.ask_valid, 999, snapshot.ask)
            response = bytearray(snapshot.encode())
            if self.fault == "crc":
                response[-1] ^= 1
            if self.fault == "truncated":
                response = response[:5]
            if self.fault == "missing":
                response.clear()
            if self.fault == "duplicate":
                response += bytes(response)
            self.rx.extend(response)
            self.busy_until = self.tick + 15

    def write(self, data):
        count = len(data) // 2 if self.fault == "partial_write" else len(data)
        for byte in data[:count]:
            self.tick += 1
            self.consume(self.receiver.step(valid=True, data=byte))
            self.consume(self.receiver.step())
        return count

    def read(self, size):
        # Fragmented USB/driver delivery must still yield a complete response.
        if self.rx:
            count = min(size, 2)
            result = bytes(self.rx[:count])
            del self.rx[:count]
            self.tick = max(self.tick, self.busy_until)
            return result
        self.clock.now += self.timeout
        self.tick += int(self.timeout * 115200 / 10)
        return b""


class HostTests(unittest.TestCase):
    def make_client(self, fault=None):
        clock = Clock()
        port = ReferencePort(clock, fault)
        return QuoteClient(port, clock=clock, sleep=clock.sleep), port

    def test_complete_sequence_and_busy_read(self):
        client, port = self.make_client()
        result = run_demo(client, random_quotes=1000)
        self.assertEqual(result["random_quotes"], 1000)
        self.assertEqual(result["final_state"], vars(port.state))
        self.assertEqual(port.busy_reads, 1)
        self.assertEqual(len(client.checks), result["snapshots_verified"])
        self.assertGreater(result["snapshots_verified"], 80)
        self.assertTrue(any(event["kind"] == "idle" for event in client.events))
        self.assertEqual(port.receiver.counts["incomplete_frames"], 1)
        self.assertEqual(port.receiver.counts["crc_errors"], 3)

    def test_snapshot_captured_before_tail_reset(self):
        client, port = self.make_client()
        client.check("baseline", (Command("bid", 123), Command("ask", 456)))
        old = client.check("reset after read", after=(Command("reset"),))
        self.assertEqual((old.bid, old.ask), (123, 456))
        empty = client.check("next snapshot")
        self.assertFalse(empty.bid_valid or empty.ask_valid)
        self.assertEqual(vars(client.state), vars(port.state))

    def test_corrupt_crc_wrong_id_and_wrong_state_fail(self):
        for fault, message in (("crc", "CRC"), ("id", "expected"), ("state", "expected")):
            with self.subTest(fault=fault):
                client, _ = self.make_client(fault)
                with self.assertRaisesRegex(ValueError, message):
                    client.check("fault")
                self.assertEqual(client.checks, [])

    def test_missing_and_truncated_responses_expire(self):
        for fault in ("missing", "truncated"):
            with self.subTest(fault=fault):
                client, _ = self.make_client(fault)
                with self.assertRaisesRegex(TimeoutError, "deadline exceeded"):
                    client.check("timeout")
                self.assertLessEqual(client.clock(), 0.501)

    def test_duplicate_response_fails(self):
        client, _ = self.make_client("duplicate")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            client.check("duplicate")

    def test_partial_write_stops_without_retry(self):
        client, _ = self.make_client("partial_write")
        with self.assertRaisesRegex(IOError, "partial write"):
            client.check("partial")
        self.assertEqual(len(client.events), 1)

    def test_write_exception_retains_attempt_without_retry(self):
        client, port = self.make_client()
        def failed_write(data):
            raise OSError("write timed out")
        port.write = failed_write
        with self.assertRaisesRegex(OSError, "write timed out"):
            client.check("write failure")
        self.assertEqual(len(client.events), 1)
        event = client.events[0]
        self.assertEqual(event["kind"], "tx")
        self.assertEqual(event["hex"], "a50303000087")
        self.assertIsNone(event["written"])
        self.assertIn("write timed out", event["error"])

    def test_final_chunk_after_deadline_fails(self):
        client, port = self.make_client()
        def late_read(size):
            client.clock.now += client.timeout + 0.01
            result = bytes(port.rx[:size])
            del port.rx[:size]
            return result
        port.read = late_read
        with self.assertRaisesRegex(TimeoutError, "deadline exceeded"):
            client.check("late final response")
        self.assertEqual(client.checks, [])
        self.assertEqual(client.events[-1]["kind"], "rx")

    def test_initial_hardware_reset_check_does_not_clear_stale_state(self):
        client, port = self.make_client()
        port.state.observe("bid", 999)
        with self.assertRaisesRegex(ValueError, "expected"):
            run_demo(client, random_quotes=0, verify_initial_empty=True)

    def test_request_id_wrap_and_repeatable_stream(self):
        first, _ = self.make_client()
        second, _ = self.make_client()
        for client in (first, second):
            client.request_id = 0xFFFF
            run_demo(client, seed=123, random_quotes=40)
        self.assertEqual(first.checks[0]["observed"]["request_id"], 0xFFFF)
        self.assertEqual(first.checks[1]["observed"]["request_id"], 0)
        self.assertEqual(first.events, second.events)


if __name__ == "__main__":
    unittest.main()
