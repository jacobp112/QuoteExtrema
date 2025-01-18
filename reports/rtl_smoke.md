# RTL and reference smoke checks

Actual run date: 30 September 2026. Target board is still unavailable.
These are the initial results at revision `ff85188`; the current runner
also includes the expanded [verification campaign](verification.md).

Implemented the core, decoder, framed response serializer, 8N1 UARTs, and
board top. The imported FrameLatch source is unchanged. The reference
computes CRC by whole-message polynomial division and prices by independent
max/min semantics; the RTL uses incremental CRC and conditional compares.

Executed from the repository root with Python 3.13.1 and the suite specified
in [planning.md](planning.md):

```powershell
py -3 scripts/run.py all --suite C:\Users\jacob\tools\oss-cad-suite-20260928
```

The completed `all` entry point ran the unit, byte-interface, and UART
checks together successfully. Source compilation and relative document
links were also checked; all 19 checkpoint files passed whitespace checks.

| Check | Result |
| --- | --- |
| Python unittest | 10 tests passed |
| Icarus byte-interface compile | Passed with `-g2012 -Wall` |
| RTL/Python byte-interface differential | 635 input edges passed |
| Core state-preservation/monotonicity assertions | No failures during smoke simulation |
| Icarus board-top/UART compile | Passed with `-g2012 -Wall` |
| UART waveform simulation | 45 response bytes across three responses matched |

The byte test covers improving, repeated and worse quotes; zero and maximum;
CRC and frame-length errors; invalid command lengths/types; marker bytes in
prices; truncation/abort; UART-error indication; busy reads; snapshot
preservation during quotes and serial reset; and hardware reset canceling a
pending quote and response. It compares both prices, both flags, all eight
diagnostics, response busy, and TX valid/data every simulated edge.

The UART smoke test starts with the top-level configuration reset, reads an
empty snapshot, sends bid 100 and ask 90, reads the crossed snapshot, then
sends serial reset and reads empty state. An independent host-side decoder
samples TX start, data, and stop bits. Host RX stimulus is nominal 115200
baud while the RTL divider remains 104 clocks at the 12 MHz simulated clock.

The model's checked byte stream contains snapshot IDs 1, 2, 3, 6, 7, and 9.
IDs 4 and 5 were intentionally rejected during response send/drain; ID 8
was canceled by hardware reset before transmission. Final hardware reset
clears diagnostics, so the final counter values do not describe the entire
earlier smoke stream; counters were compared at every preceding edge.

These are initial integration checks. No randomized campaign, counter
saturation test, UART baud-offset/error/timeout suite, formal proof,
synthesis, timing result, board programming, or physical observation is
claimed here. Expanded tests are the next verification milestone.
