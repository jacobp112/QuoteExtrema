"""Wire codec and whole-message polynomial CRC oracle."""

from dataclasses import dataclass, field

MAX_U32 = 0xFFFFFFFF
FRAME_COUNTERS = ("valid_frames", "crc_errors", "invalid_lengths",
                  "incomplete_frames", "discarded_bytes")


def crc8(data: bytes) -> int:
    remainder = int.from_bytes(data, "big") << 8
    while remainder.bit_length() > 8:
        remainder ^= 0x107 << (remainder.bit_length() - 9)
    return remainder


def frame(payload: bytes) -> bytes:
    payload = bytes(payload)
    if not 1 <= len(payload) <= 16:
        raise ValueError("frame payload length must be 1..16")
    body = bytes([len(payload)]) + payload
    return b"\xa5" + body + bytes([crc8(body)])


def _unsigned(value: int, bits: int) -> bytes:
    if not isinstance(value, int) or not 0 <= value < 1 << bits:
        raise ValueError(f"value must be an unsigned {bits}-bit integer")
    return value.to_bytes(bits // 8, "little")


def bid(price: int) -> bytes:
    return frame(b"\x01" + _unsigned(price, 32))


def ask(price: int) -> bytes:
    return frame(b"\x02" + _unsigned(price, 32))


def read(request_id: int) -> bytes:
    return frame(b"\x03" + _unsigned(request_id, 16))


def reset() -> bytes:
    return frame(b"\x04")


@dataclass(frozen=True)
class Snapshot:
    request_id: int
    bid_valid: bool
    ask_valid: bool
    bid: int
    ask: int

    def payload(self) -> bytes:
        flags = int(self.bid_valid) | (int(self.ask_valid) << 1)
        return (b"\x83" + _unsigned(self.request_id, 16) + bytes([flags])
                + _unsigned(self.bid if self.bid_valid else 0, 32)
                + _unsigned(self.ask if self.ask_valid else 0, 32))

    def encode(self) -> bytes:
        return frame(self.payload())


def decode_snapshot(data: bytes) -> Snapshot:
    if len(data) != 15 or data[:2] != b"\xa5\x0c":
        raise ValueError("snapshot must be a 15-byte frame")
    if crc8(data[1:-1]) != data[-1]:
        raise ValueError("snapshot CRC mismatch")
    p = data[2:-1]
    if p[0] != 0x83 or p[3] & 0xFC:
        raise ValueError("invalid snapshot type or reserved flag bits")
    result = Snapshot(int.from_bytes(p[1:3], "little"), bool(p[3] & 1),
                      bool(p[3] & 2), int.from_bytes(p[4:8], "little"),
                      int.from_bytes(p[8:12], "little"))
    if (not result.bid_valid and result.bid) or (not result.ask_valid and result.ask):
        raise ValueError("unseen side must have zero price")
    return result


@dataclass
class Receiver:
    """One-edge output delay, matching FrameLatch's always-ready sink."""

    phase: str = "search"
    length: int = 0
    assembly: bytearray = field(default_factory=bytearray)
    pending: bytes | None = None
    counts: dict[str, int] = field(default_factory=lambda: dict.fromkeys(FRAME_COUNTERS, 0))

    def bump(self, name: str) -> None:
        self.counts[name] = min(MAX_U32, self.counts[name] + 1)

    def clear_parser(self) -> None:
        self.phase = "search"
        self.length = 0
        self.assembly.clear()

    def step(self, *, data=0, valid=False, abort=False, rst=False) -> bytes | None:
        if rst:
            self.clear_parser()
            self.pending = None
            self.counts = dict.fromkeys(FRAME_COUNTERS, 0)
            return None
        transferred, self.pending = self.pending, None
        if abort:
            if self.phase != "search":
                self.bump("incomplete_frames")
            self.clear_parser()
        elif valid:
            if not 0 <= data <= 255:
                raise ValueError("input byte must be 0..255")
            if self.phase == "search":
                if data == 0xA5:
                    self.clear_parser()
                    self.phase = "length"
                else:
                    self.bump("discarded_bytes")
            elif self.phase == "length":
                if not 1 <= data <= 16:
                    self.bump("invalid_lengths")
                    self.clear_parser()
                else:
                    self.length = data
                    self.phase = "payload"
            elif self.phase == "payload":
                self.assembly.append(data)
                if len(self.assembly) == self.length:
                    self.phase = "crc"
            else:
                if data == crc8(bytes([self.length]) + self.assembly):
                    self.pending = bytes(self.assembly)
                    self.bump("valid_frames")
                else:
                    self.bump("crc_errors")
                self.clear_parser()
        return transferred
