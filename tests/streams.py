"""Deterministic directed and randomized simulator inputs."""

import json
from pathlib import Path
import random

from quoteextrema import QuoteState, Snapshot, ask, bid, frame, read, reset

EDGE_PRICES = (0, 1, 0x7FFFFFFF, 0x80000000, 0xA5A5A5A5, 0xFFFFFFFF)


def smoke_stream():
    events = []

    def emit(**signals):
        events.append(signals)

    def idle(n=1, **signals):
        for _ in range(n):
            emit(**signals)

    def send(data, **signals):
        for byte in data:
            emit(data=byte, valid=True, **signals)
            idle(**signals)

    emit(rst=True)
    idle()
    for data in (bid(100), ask(120), bid(100), ask(120), bid(90), ask(130),
                 bid(110), ask(115), read(1)):
        send(data)
    idle(30)
    bad_crc = bytearray(bid(1000))
    bad_crc[-1] ^= 1
    for data in (bad_crc, b"\xa5\x00", b"\xa5\xff", frame(b"\x7f"),
                 frame(b"\x01"), frame(b"\x04\x00"),
                 Snapshot(2, False, False, 0, 0).encode(), b"noise"):
        send(data)
    send(bid(200)[:4])
    emit(abort=True)
    emit(error=True)
    send(read(2))
    idle(30)
    stall = dict(tx_ready=False, tx_idle=False)
    send(read(3), **stall)
    send(read(4), **stall)
    send(ask(0), **stall)
    send(bid(0xFFFFFFFF), **stall)
    send(reset(), **stall)
    idle(15, tx_idle=False)
    send(read(5), **stall)  # Still busy during drain.
    idle(2)
    send(read(6))
    idle(30)
    for data in (bid(0), ask(0xFFFFFFFF), read(7), reset(), bid(0xA5A5A5A5), ask(0xA5)):
        send(data)
    idle(30)
    send(read(8), **stall)
    send(bid(1000)[:-1], **stall)
    emit(data=bid(1000)[-1], valid=True, **stall)
    emit(rst=True, valid=True, data=0xA5)
    idle(2)
    send(read(9))
    idle(30)
    return events


def directed_stream():
    events = [dict(rst=True), {}]

    def send(data, **signals):
        for byte in data:
            events.append(dict(data=byte, valid=True, **signals))
        events.append(signals)

    # Independently clear before each first-observation boundary price.
    for price in EDGE_PRICES:
        send(reset())
        for data in (bid(price), ask(price), bid(price), ask(price), read(price & 65535)):
            send(data)
        events.extend({} for _ in range(18))
    send(reset())
    for price in EDGE_PRICES:
        send(bid(price))
    for price in reversed(EDGE_PRICES):
        send(ask(price))
    send(frame(b"\xa5"))
    send(bid(next(price for price in range(256) if bid(price)[-1] == 0xA5)))
    send(read(0xA5A5))
    events.extend({} for _ in range(18))
    events.extend(dict(data=byte, valid=True) for byte in bid(123))
    events.append(dict(abort=True, error=True))  # Earlier completed quote must survive abort.
    for prefix_length in range(1, len(bid(100))):
        send(bid(100)[:prefix_length])
        events.append(dict(abort=True))
        send(ask(100))
    # Hardware reset at every frame position, including the CRC publication edge.
    for prefix_length in range(len(bid(100)) + 1):
        for byte in bid(100)[:prefix_length]:
            events.append(dict(data=byte, valid=True))
        events.append(dict(rst=True, valid=True, data=0xA5, abort=True, error=True))
        send(read(prefix_length))
        events.extend({} for _ in range(18))
    # Reset during every possible TX byte position.
    for count in range(16):
        send(read(count), tx_ready=False)
        events.extend({} for _ in range(count))
        events.append(dict(rst=True))
        send(bid(100 + count))
    events.extend({} for _ in range(32))
    return events


def uart_cases():
    actions, expected = [], bytearray()
    state = QuoteState()

    def send(data):
        actions.extend((0, byte) for byte in data)

    def wait(cycles=20000):
        actions.append((1, cycles))

    def quote(side, price):
        send((bid if side == "bid" else ask)(price))
        state.observe(side, price)

    def snapshot(request_id):
        send(read(request_id))
        expected.extend(state.snapshot(request_id).encode())

    actions.append((3, 20))  # False start shorter than the half-bit check.
    snapshot(0)
    wait()
    quote("bid", 100)
    quote("ask", 90)
    snapshot(1)
    quote("bid", 200)  # Arrives while response 1 is on TX.
    wait()
    snapshot(2)
    send(reset())  # Reset cannot change response 2's captured state.
    state.clear()
    wait()
    snapshot(3)
    wait()
    quote("bid", 0)
    quote("ask", 0xFFFFFFFF)
    packet = bytearray(bid(999))
    packet[-1] ^= 1
    send(packet)
    send(b"\xa5\x11")
    send(frame(b"\x7f"))
    send(b"\xa5\x05\x01")
    actions.append((4, 100))  # Bad stop bit aborts a partial quote.
    send(b"\xa5\x05\x01")
    wait(25000)  # Actual top-level timeout of a truncated quote.
    actions.append((5, 4000))  # Sustained break counts once, then recovers.
    actions.extend(((8, 2), (9, 2)))
    snapshot(4)
    wait()
    quote("bid", 0xFFFFFFFF)
    quote("ask", 0)
    snapshot(5)
    wait()
    # Cancel during the first TX byte, before any complete response byte.
    send(read(0xBEEF))
    actions.append((2, 512))
    state.clear()
    wait(25000)
    snapshot(6)
    wait()
    return actions, bytes(expected)


def saturation_stream():
    events = [dict(rst=True), {}, dict(_seed=True)]

    def send(data, **signals):
        events.extend(dict(data=byte, valid=True, **signals) for byte in data)
        events.append(signals)

    for _ in range(2):
        send(bid(100))
        send(b"\xa5\x00")
        send(bid(100)[:-1] + bytes([bid(100)[-1] ^ 1]))
        send(frame(b"\x7f"))
        send(b"noise")
        send(b"\xa5\x05\x01")
        events.append(dict(abort=True))
        events.append(dict(error=True))
    for request_id in (1, 2, 3):
        send(read(request_id), tx_ready=False, tx_idle=False)
    events.extend({} for _ in range(20))
    return events


def corpus_stream():
    corpus = json.loads((Path(__file__).parent / "corpus/malformed.json").read_text())
    events = [dict(rst=True), {}]
    for case in corpus:
        for data in (reset(), bid(100), ask(120), bytes.fromhex(case["hex"])):
            events.extend(dict(data=byte, valid=True) for byte in data)
            events.append({})
        if case.get("abort"):
            events.append(dict(abort=True))
        events.extend({} for _ in range(2))
    return events


def random_stream(seed, attempts):
    rng = random.Random(seed)
    events = [dict(rst=True), {}]
    previous = 100

    def cycle(**signals):
        event = dict(tx_ready=rng.random() < .7, tx_idle=rng.random() < .6)
        event.update(signals)
        events.append(event)

    def send(data):
        for byte in data:
            cycle(data=byte, valid=True)
            for _ in range(rng.randrange(3)):
                cycle()

    for attempt in range(attempts):
        choice = rng.randrange(100)
        if choice < 65:
            price = rng.choice(EDGE_PRICES) if rng.random() < .35 else rng.getrandbits(32)
            if rng.random() < .25:
                price = previous
            previous = price
            send((bid if choice < 33 else ask)(price))
        elif choice < 75:
            send(read(rng.randrange(65536)))
        elif choice < 80:
            send(reset())
        elif choice < 85:
            cycle(rst=True, valid=True, data=rng.randrange(256), abort=True)
        elif choice < 90:
            packet = bytearray((bid if rng.randrange(2) else ask)(rng.getrandbits(32)))
            packet[-1] ^= 1 << rng.randrange(8)
            send(packet)
        elif choice < 94:
            send(b"\xa5" + bytes([rng.choice((0, 17, 255))]))
        elif choice < 97:
            send(frame(rng.choice((b"\x01", b"\x03", b"\x04\x00", b"\xff"))))
        else:
            send(bid(rng.getrandbits(32))[:rng.randrange(1, 8)])
            cycle(abort=True, error=rng.random() < .5)
        if rng.random() < .03:
            cycle(error=True)
    events.extend({} for _ in range(64))
    return events
