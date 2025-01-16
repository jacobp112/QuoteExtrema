# QuoteExtrema

QuoteExtrema receives unsigned 32-bit bid and ask prices over UART and stores
the highest bid and lowest ask observed since reset. Each side has a valid
flag. Reset clears both values and flags. These are historical extremes;
withdrawals and order-book depth are outside the project scope.

Status: board target, protocol, and acceptance plan documented. RTL,
differential verification, synthesis, and physical demonstration are pending.

Planned target: iCEBreaker (iCE40UP5K-SG48), 12 MHz system clock, onboard FTDI
UART, 115200 baud, 8N1. Confirm board revision and pinout before programming.

Planned reuse of the framed receiver from
[jacobp112/framelatch](https://github.com/jacobp112/framelatch) at revision
`8d2ce380478418aeb4fc07ed3407d590143f3cdd`. The source and reuse scope are
recorded in [provenance](docs/PROVENANCE.md). Frames
use `0xA5 | length | payload | CRC-8`, length 1..16, polynomial `0x07`, initial
`0x00`, no reflection or final XOR; CRC covers length and payload.

Planned layout: `rtl/`, `quoteextrema/`, `tests/`, `constraints/`, `scripts/`,
`docs/`, `reports/`, and `evidence/`. Reports and hardware evidence will contain
actual measured results only. No physical board is currently available.

- [Protocol](docs/PROTOCOL.md): wire bytes, CRC, command ordering, reset, and counters.
- [Board and clocking](docs/BOARD.md): target, pins, synchronization, and toolchain.
- [Acceptance and milestones](docs/PLAN.md): tests, evidence, and completion gates.
- [Planning checks](reports/planning.md): checks actually performed and their limits.
