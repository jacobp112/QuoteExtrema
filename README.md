# QuoteExtrema

QuoteExtrema receives unsigned 32-bit bid and ask prices over UART and stores
the highest bid and lowest ask observed since reset. Each side has a valid
flag. Reset clears both values and flags. These are historical extremes;
withdrawals and order-book depth are outside the project scope.

Status: RTL and Python reference implemented and verified in simulation.
Twenty-four model, host and CLI tests, 100,000 randomized attempts across 20 seeds, directed
malformed/reset/saturation tests, and UART tests at nominal baud and +/-1%
pass. The target build passes 12 MHz with 1065/5280 logic cells and a routed
28.99 MHz reported maximum. The model-checked serial host tool is implemented;
its simulated-transport tests pass. The physical demonstration is pending. See
[verification](reports/verification.md) and [implementation results](reports/synthesis.md).

Planned target: iCEBreaker (iCE40UP5K-SG48), 12 MHz system clock, onboard FTDI
UART, 115200 baud, 8N1. Confirm board revision and pinout before programming.

The project reuses the framed receiver from
[jacobp112/framelatch](https://github.com/jacobp112/framelatch) at revision
`8d2ce380478418aeb4fc07ed3407d590143f3cdd`. The source and reuse scope are
recorded in [provenance](docs/PROVENANCE.md). Frames
use `0xA5 | length | payload | CRC-8`, length 1..16, polynomial `0x07`, initial
`0x00`, no reflection or final XOR; CRC covers length and payload.

Layout: `rtl/`, `quoteextrema/`, `tests/`, `constraints/`, `scripts/`,
`docs/`, `reports/`, and `evidence/`. Reports contain observed simulation and
implementation results. The physical evidence directory is explicitly pending;
no physical board is currently available.

- [Protocol](docs/PROTOCOL.md): wire bytes, CRC, command ordering, reset, and counters.
- [Board and clocking](docs/BOARD.md): target, pins, synchronization, and toolchain.
- [Acceptance and milestones](docs/PLAN.md): tests, evidence, and completion gates.
- [Planning checks](reports/planning.md): checks actually performed and their limits.
- [Build and test commands](docs/BUILD.md): reproduce the current checks.
- [Board bring-up](docs/HARDWARE.md): program explicitly, run the host checker,
  and capture physical evidence.
- [Host verification](reports/host.md): tested serial checks and their limits.
