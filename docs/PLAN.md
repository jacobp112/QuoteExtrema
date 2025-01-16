# Acceptance and milestone plan

Completion requires synthesizable RTL, an independent Python model,
differential verification, real target-device implementation reports,
reproducible host/build scripts, and a verified physical demonstration.
The board has not been obtained. RTL simulation and place-and-route can
proceed without it; physical acceptance cannot.

## Acceptance cases

| ID | Requirement and planned validation |
| --- | --- |
| A01 | Hardware reset produces zero prices, clear flags, empty parser/TX, and zero counters; assert it in every parser/TX phase and on a command edge |
| A02 | First bid/ask, equal, improving, and worse prices match an independent max/min model; include 0, 1, `0x7FFFFFFF`, `0x80000000`, and `0xFFFFFFFF` |
| A03 | Bid-only and ask-only streams preserve the other side; crossed historical extremes are allowed |
| A04 | CRC errors, lengths 0/17/255, unsupported opcodes, wrong semantic lengths, response opcodes on input, and noise never produce a quote update |
| A05 | Insert `0xA5` into every frame position; verify receiver consumption and recovery rules exactly, including malformed bytes that equal the marker |
| A06 | Truncate at every position, expire timeout, test a byte exactly on timeout, false starts, bad stops, break, and subsequent valid-frame recovery |
| A07 | Serial reset clears quote state but preserves diagnostics and earlier snapshots; a CRC-bad reset clears nothing |
| A08 | Reads echo IDs and snapshot all four fields atomically; quotes and serial reset during TX do not alter response bytes |
| A09 | Additional reads while busy are rejected/count once, including the TX-completion edge; quote traffic continues at full UART byte rate |
| A10 | Each diagnostic increments only on its specified event; seed counters near maximum in simulation and verify saturation and hardware-reset clearing |
| A11 | Differential byte/command simulation covers at least 20 fixed seeds and 100,000 total command attempts, including malformed input and resets; retain failing seeds/streams |
| A12 | Bit-level UART simulation checks nominal timing and host baud offsets of -1%, 0%, +1%, back-to-back bytes, arbitrary RX phase, and asynchronous button arrival |
| A13 | Yosys hierarchy/check succeeds; UP5K-SG48 nextpnr meets 12 MHz without allowing timing failure; record actual utilization, timing, warnings, seed, and artifact hashes |
| A14 | Host script programs no board implicitly, sends repeatable quotes/readbacks, compares every response with the model, and exits nonzero on mismatches or missing responses |
| A15 | Physical run identifies board/revision, cable/interface, clock, COM port, toolchain, bitstream, sequence, and responses, with clear photographs or a short video |

The randomized budget is an acceptance target, not a report of completed
tests. Random generation must track reads the device actually accepts,
distinguish semantic failures from CRC failures, and avoid interpreting an
intentionally rejected busy read as a missing accepted response.

Assertions will check that no accepted valid quote and no reset implies
both stored prices and valid flags remain stable. This covers rejected
frames, rejected commands, and reads. Check the parser/decoder boundary
as well: failed CRC and invalid frame lengths never publish a payload;
invalid semantic payloads never assert a quote-update event. An earlier
completed valid frame may be consumed on an abort edge, so assertions must
account for that valid event rather than attributing it to the aborted frame.
Also assert bid monotonicity, ask monotonicity, side isolation, snapshot
stability, and legal UART/ready-valid behaviour. Report simulation assertions
separately from any formal proof actually run.

## Physical demonstration sequence

1. Record board revision and check the pin map. Record tool and USB-driver
   versions, bitstream hash, system clock, UART baud, and actual run date.
2. Program explicitly, reset physically, open the serial port, discard
   partial input, and read an empty snapshot.
3. Send bid 100 and ask 120; verify both flags and values. Repeat equal
   prices and worse bid 90/ask 130; verify values remain 100/120.
4. Improve bid to 110 and ask to 115; verify. Send deliberately CRC-bad
   improving quotes, unknown commands, invalid lengths, and a truncated
   quote followed by an idle recovery gap; verify state remains unchanged.
5. Read during continuous quote traffic; compare the snapshot with state
   at request acceptance, independently of later received prices.
6. Test zero and maximum on both sides with intervening serial resets;
   verify flags distinguish unseen from observed zero. Verify a crossed
   state and a snapshot that remains stable across a later serial reset.
7. Run deterministic randomized host traffic with periodic model-checked
   readbacks. Physically reset during a response and demonstrate recovery.
8. Save raw transmitted/received bytes and machine-readable results. Capture
   the connected board and visible reset/valid indicators. Record actual
   failures and fixes; do not substitute a simulated waveform for hardware.

Start/stop physical traffic around manual reset as needed. Any optional
automation of reset requires documented hardware; the onboard UART alone
does not imply control of the physical reset button.

## Milestones

The user supplied a planning calendar ending 28 March 2025. The calendar
below retains that intent; it is not a claim of historical execution.
Actual validation dates and available hardware are recorded in reports.
Commit metadata follows the separately approved Git checkpoints.

| Milestone | Supplied calendar | Estimated human effort | Exit condition |
| --- | --- | ---: | --- |
| Board/protocol decisions | 16-22 January 2025 | 8-12 h | Protocol, target, pin plan, acceptance matrix, tool baseline; procurement remains explicit |
| RTL and model | 23 January-5 February 2025 | 20-30 h | Imported receiver validated; quote, UART, TX, model, basic integration run |
| Verification | 6-19 February 2025 | 20-30 h | A01-A12 pass, regressions retained, assertion results recorded |
| Synthesis and timing | 20 February-5 March 2025 | 15-25 h | A13 passes or failures accurately reported and resolved before physical acceptance |
| Board bring-up | 6-19 March 2025 | 15-25 h | Board acquired, programmed, UART verified, host sequence runs |
| Demonstration/documentation | 20-28 March 2025 | 12-18 h | A14-A15 pass with saved evidence and final measured limitations |

Total effort estimate is 90-140 hours. Hardware lead time and debugging may
extend actual completion. A requested metadata date cannot establish a
hardware result. Do not mark the project complete while A15 remains pending.

## Repository responsibilities

`rtl/` contains synthesizable modules; `quoteextrema/` the independent Python
model and codec; `tests/` directed and randomized verification; `constraints/`
the board pin map; `scripts/` build/test/host entry points; `docs/` specifications
and reproducibility instructions; `reports/` measured results; `evidence/`
the physical demonstration record. Generated intermediate outputs belong
in ignored `build/`. Keep reproducibility logs intended as deliverables
outside ignored directories.

At every natural engineering checkpoint, inspect the changes and ask the
review subagent to check correctness, clear wording, recorded evidence,
commit identity, and timestamp arithmetic. Show explicit staged paths and
commands, then wait for the user's approval before any Git mutation. Use
repo-local `jacobp112 <jacobcp112@gmail.com>`, verify Git's actual HTTPS
account before pushing, and never infer it from the author fields alone.

The approved anchor is T+00d 00h 00m = `2025-01-16T13:17:29+00:00`.
T+ at subsequent checkpoints is an estimated cumulative human effort
timeline, not the execution host's elapsed runtime. State that distinction
and show arithmetic. UK timezone conversion must use IANA `Europe/London`
or its Windows equivalent `GMT Standard Time`, including daylight-saving
transitions. Keep commits between 12:00 and
22:00, and propose any necessary next-day adjustment explicitly.
