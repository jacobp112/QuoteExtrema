# Verification results

Actual final verification date: 4 October 2026. The first randomized run
completed on 30 September; the final run below includes additional directed
and saved malformed cases. No board is connected and no physical result
is claimed. Tool versions remain those in [planning.md](planning.md).

Executed with Python 3.13.1 and Windows x64 OSS CAD Suite `20260928`:

```powershell
$suiteRoot = 'C:\Users\jacob\tools\oss-cad-suite-20260928'
py -3 scripts/run.py unit
py -3 scripts/run.py regression --suite $suiteRoot
py -3 scripts/run.py uart --suite $suiteRoot
```

| Check | Observed result |
| --- | --- |
| Reference tests | 11 passed, including all 12 saved malformed cases |
| Directed byte-interface stream | 1358 cycles passed |
| Counter saturation stream | 120 cycles passed; all eight counters reach and remain at `0xFFFFFFFF` |
| Saved malformed corpus | 372 cycles passed |
| Randomized streams | 20 seeds, 5000 attempts each; all 100,000 attempts passed |
| Combined directed/corpus/saturation/random | 1,359,051 byte-interface cycles passed |
| UART waveform suite | 105 response bytes per run at -1%, nominal, +1%; 315 bytes matched |
| Timeout boundary integration | Completing byte wins over timeout; expiry and framing-error priority passed |
| Core assertions | No simulation failures |

Machine-readable results and source hashes (with CRLF normalized to LF) are in
[verification.json](verification.json). Each differential edge compares
both prices, both flags, all eight counters, response busy, and pre-edge
TX valid/data against the Python model. The model uses whole-message
polynomial CRC and direct max/min semantics, while RTL uses incremental
CRC and compare/update logic.

## Covered behaviours

Directed cases include first observations at zero, maximum, signed-boundary
values, repeated/worse prices, marker bytes in prices/read IDs/CRC, a marker
used as invalid length, every quote-frame truncation position, hardware
reset at every frame position and TX byte position, and an abort coinciding
with consumption of an earlier completed valid quote. Assertions check
state preservation without an accepted quote/reset, side isolation, and
monotonic extremes while flags remain valid.

The malformed corpus contains invalid lengths, noise, CRC-bad improving
bid/ask quotes, CRC-bad reset, too-short ask, too-long bid, marker-as-bad-CRC,
and truncation with abort. Cases begin from bid 100/ask 120; improving bad
quotes and reset would visibly change state if accepted. The independent
reference test checks preservation for every corpus case.

Random seeds 1931..1950 mix valid quotes, repeated/boundary/random prices,
reads, serial/hardware reset, CRC errors, invalid lengths, invalid command
lengths/types, truncations, UART-error indications, arbitrary byte gaps,
and TX stalls. The byte interface permits one byte per clock in this test;
it stresses parser/control ordering independently of the slower UART.
Counters clear on hardware reset, so final values do not count all campaign
events. Counter peaks and saturation outcomes are recorded separately.

The UART suite uses the 12 MHz board top and nominal 115200 host baud with
offsets -1%, 0%, +1%, starting at three different phases relative to the
clock. It verifies false-start rejection, a low stop bit during a partial
quote, a sustained break counted once, actual 24,000-cycle timeout,
subsequent valid-frame recovery, readback during quotes, serial reset during
TX preserving a snapshot, zero/maximum prices, and asynchronous button
reset canceling the first byte of a response before recovery readback.

The timeout-boundary test forces completed-byte/error strobes at the wrapper
boundary to hit the exact edge. It complements UART waveform tests; it is
not a physical line measurement. Saturation likewise seeds registers in a
testbench; no special seeding path exists in synthesizable RTL.

## Limits and acceptance status

A01-A12 have directed/randomized simulation coverage. This is finite
testing, not a formal proof or exhaustive enumeration of all streams.
No formal solver was run. Simulation cannot establish analog signal quality,
metastability MTBF, electrical pin correctness, or USB-driver behaviour.

The waveform reset case cancels the first response byte. Byte-interface
tests reset at every serialized byte position, but do not enumerate every
possible physical TX bit phase. Host baud offsets are tested at three
specified values, not across a continuous tolerance sweep.

A13 (target-device synthesis/timing), A14 (host demonstration tool), and
A15 (physical board evidence) remain pending at this checkpoint. No RTL
functional discrepancy was found in the campaigns described above.
