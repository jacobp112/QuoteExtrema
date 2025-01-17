"""Independent extrema semantics and edge-by-edge byte interface model."""

from dataclasses import dataclass, field

from .protocol import MAX_U32, Receiver, Snapshot

INTERFACE_COUNTERS = ("semantic_errors", "busy_reads", "uart_errors")


@dataclass
class QuoteState:
    bid_valid: bool = False
    bid: int = 0
    ask_valid: bool = False
    ask: int = 0

    def clear(self) -> None:
        self.bid_valid = self.ask_valid = False
        self.bid = self.ask = 0

    def observe(self, side: str, price: int) -> None:
        if side not in ("bid", "ask") or not isinstance(price, int) or not 0 <= price <= MAX_U32:
            raise ValueError("quote requires bid/ask and an unsigned 32-bit price")
        if side == "bid":
            self.bid = max(self.bid, price) if self.bid_valid else price
            self.bid_valid = True
        else:
            self.ask = min(self.ask, price) if self.ask_valid else price
            self.ask_valid = True

    def snapshot(self, request_id: int) -> Snapshot:
        return Snapshot(request_id, self.bid_valid, self.ask_valid, self.bid, self.ask)


@dataclass
class DeviceModel:
    state: QuoteState = field(default_factory=QuoteState)
    receiver: Receiver = field(default_factory=Receiver)
    counts: dict[str, int] = field(default_factory=lambda: dict.fromkeys(INTERFACE_COUNTERS, 0))
    tx_phase: str = "idle"
    tx_frame: bytes = b""
    tx_index: int = 0

    @property
    def busy(self) -> bool:
        return self.tx_phase != "idle"

    def peek_tx(self, *, rst=False) -> int | None:
        return self.tx_frame[self.tx_index] if not rst and self.tx_phase == "send" else None

    def bump(self, name: str) -> None:
        self.counts[name] = min(MAX_U32, self.counts[name] + 1)

    def step(self, *, data=0, valid=False, abort=False, error=False,
             rst=False, tx_ready=True, tx_idle=True) -> int | None:
        was_busy = self.busy
        transmitted = self.peek_tx(rst=rst) if tx_ready else None
        command = self.receiver.step(data=data, valid=valid, abort=abort or error, rst=rst)
        if rst:
            self.state.clear()
            self.counts = dict.fromkeys(INTERFACE_COUNTERS, 0)
            self.tx_phase, self.tx_frame, self.tx_index = "idle", b"", 0
            return None
        if self.tx_phase == "send" and tx_ready:
            self.tx_index += 1
            if self.tx_index == len(self.tx_frame):
                self.tx_phase = "drain"
        elif self.tx_phase == "drain" and tx_idle:
            self.tx_phase = "idle"
        if error:
            self.bump("uart_errors")
        if command:
            kind = command[0]
            if kind in (1, 2) and len(command) == 5:
                self.state.observe("bid" if kind == 1 else "ask",
                                   int.from_bytes(command[1:], "little"))
            elif kind == 4 and len(command) == 1:
                self.state.clear()
            elif kind == 3 and len(command) == 3:
                if was_busy:
                    self.bump("busy_reads")
                else:
                    request_id = int.from_bytes(command[1:], "little")
                    self.tx_frame = self.state.snapshot(request_id).encode()
                    self.tx_index, self.tx_phase = 0, "send"
            else:
                self.bump("semantic_errors")
        return transmitted
