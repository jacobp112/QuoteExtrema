"""Model-checked host transactions; transport supplied by the caller."""

from dataclasses import asdict, dataclass
import random
import time

from .model import QuoteState
from .protocol import MAX_U32, ask, bid, decode_snapshot, frame, read, reset


@dataclass(frozen=True)
class Command:
    kind: str
    value: int | bytes = 0

    def encode(self):
        if self.kind == "bid":
            return bid(self.value)
        if self.kind == "ask":
            return ask(self.value)
        if self.kind == "reset":
            return reset()
        if self.kind == "raw":
            return bytes(self.value)
        raise ValueError(f"unknown host command: {self.kind}")

    def apply(self, state):
        if self.kind in ("bid", "ask"):
            state.observe(self.kind, self.value)
        elif self.kind == "reset":
            state.clear()


class QuoteClient:
    def __init__(self, port, *, timeout=0.5, clock=time.monotonic, sleep=time.sleep):
        if timeout <= 0:
            raise ValueError("response timeout must be positive")
        self.port, self.timeout = port, timeout
        self.clock, self.sleep = clock, sleep
        self.started = clock()
        self.state = QuoteState()
        self.request_id = 0
        self.events, self.checks = [], []

    def record(self, kind, **values):
        event = dict(elapsed_s=self.clock() - self.started, kind=kind, **values)
        self.events.append(event)
        return event

    def transmit(self, packet, label):
        # A partial write can split a frame across the FPGA's 2 ms timeout.
        # Stop instead of silently retrying an ambiguous partial transaction.
        event = self.record("tx", label=label, hex=packet.hex(), written=None)
        try:
            written = self.port.write(packet)
            event["written"] = written
        except Exception as error:
            event["error"] = f"{type(error).__name__}: {error}"
            raise
        if written != len(packet):
            raise IOError(f"{label}: partial write ({written}/{len(packet)})")

    def receive(self, size):
        data = bytearray()
        deadline = self.clock() + self.timeout
        while len(data) < size:
            remaining = deadline - self.clock()
            if remaining <= 0:
                raise TimeoutError(f"response deadline exceeded ({len(data)}/{size} bytes)")
            self.port.timeout = min(0.05, remaining)
            part = self.port.read(size - len(data))
            if part:
                self.record("rx", hex=part.hex())
                data.extend(part)
            if self.clock() >= deadline:
                raise TimeoutError(f"response deadline exceeded ({len(data)}/{size} bytes)")
        return bytes(data)

    def quiet(self):
        # Also allows the final UART stop bit to finish before the next READ.
        self.port.timeout = 0.02
        extra = self.port.read(1)
        if extra:
            self.record("rx", hex=extra.hex())
            raise ValueError("unsolicited or duplicate response byte")

    def check(self, label, before=(), after=()):
        before, after = tuple(before), tuple(after)
        for command in before:
            command.apply(self.state)
        request_id = self.request_id
        self.request_id = (request_id + 1) & 0xFFFF
        expected = self.state.snapshot(request_id)
        packet = (b"".join(command.encode() for command in before) + read(request_id)
                  + b"".join(command.encode() for command in after))
        self.transmit(packet, label)
        for command in after:
            command.apply(self.state)
        observed = decode_snapshot(self.receive(15))
        if observed != expected:
            raise ValueError(f"{label}: expected {expected}, received {observed}")
        self.quiet()
        self.checks.append(dict(label=label, expected=asdict(expected), observed=asdict(observed)))
        return observed

    def truncate_and_recover(self):
        partial = bid(MAX_U32)[:4]
        self.transmit(partial, "truncated improving bid")
        # Include serial wire time, then more than the receiver's idle timeout.
        gap = len(partial) * 10 / 115200 + 0.03
        self.record("idle", seconds=gap)
        self.sleep(gap)
        self.check("truncated frame recovery")


def run_demo(client, *, seed=1931, random_quotes=1000, verify_initial_empty=False):
    if random_quotes < 0:
        raise ValueError("random quote count cannot be negative")
    command = Command
    client.check("empty after hardware reset" if verify_initial_empty else "serial reset",
                 () if verify_initial_empty else (command("reset"),))
    client.check("first bid", (command("bid", 100),))
    client.check("first ask", (command("ask", 120),))
    client.check("repeated and worse prices", (
        command("bid", 100), command("ask", 120), command("bid", 90), command("ask", 130)))
    client.check("improving prices", (command("bid", 110), command("ask", 115)))
    bad_bid, bad_ask, bad_reset = bytearray(bid(MAX_U32)), bytearray(ask(0)), bytearray(reset())
    for packet in (bad_bid, bad_ask, bad_reset):
        packet[-1] ^= 1
    invalid = (bytes(bad_bid), bytes(bad_ask), bytes(bad_reset), b"\xa5\x00",
               b"\xa5\x11", b"\xa5\xff", frame(b"\x7f"), frame(b"\x01"),
               frame(b"\x02"), frame(b"\x03"), frame(b"\x04\x00"),
               frame(b"\x83"), b"\x00\xffnoise")
    for index, packet in enumerate(invalid):
        client.check(f"malformed {index}", (command("raw", packet),))
    client.truncate_and_recover()
    client.check("snapshot during improving traffic", after=(
        command("bid", 200), command("ask", 90), command("bid", 201), command("ask", 89)))
    client.check("traffic result")
    # The second six-byte READ finishes while the first 15-byte response is busy.
    rejected_id = (client.request_id + 1) & 0xFFFF
    client.check("busy read rejection", after=(command("raw", read(rejected_id)), command("bid", 202)))
    client.check("quotes continue after busy read")
    client.check("snapshot survives serial reset", after=(command("reset"),))
    client.check("empty after serial reset")
    for side in ("bid", "ask"):
        client.check(f"{side} observed zero", (command("reset"), command(side, 0)))
        client.check(f"{side} observed maximum", (command("reset"), command(side, MAX_U32)))
    client.check("crossed historical extremes", (command("bid", MAX_U32), command("ask", 0)))
    client.check("random sequence reset", (command("reset"),))
    rng = random.Random(seed)
    batch = []
    for index in range(random_quotes):
        price = rng.choice((0, 1, 0x7FFFFFFF, 0x80000000, MAX_U32)) if rng.randrange(4) == 0 else rng.getrandbits(32)
        batch.append(command(rng.choice(("bid", "ask")), price))
        if len(batch) == 20 or index + 1 == random_quotes:
            client.check(f"random quotes through {index + 1}", batch)
            batch.clear()
    return dict(seed=seed, random_quotes=random_quotes, snapshots_verified=len(client.checks),
                final_state=asdict(client.state))
