"""Deterministic input streams shared by the simulator runner."""

from quoteextrema import Snapshot, ask, bid, frame, read, reset


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


def uart_smoke():
    actions = []
    expected = bytearray()

    def send(data):
        actions.extend((0, byte) for byte in data)

    def wait():
        actions.append((1, 20000))

    send(read(0x1234))
    expected.extend(Snapshot(0x1234, False, False, 0, 0).encode())
    wait()
    send(bid(100))
    send(ask(90))
    send(read(0x1234))
    expected.extend(Snapshot(0x1234, True, True, 100, 90).encode())
    wait()
    send(reset())
    send(read(9))
    expected.extend(Snapshot(9, False, False, 0, 0).encode())
    wait()
    return actions, bytes(expected)
