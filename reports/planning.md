# Planning checks

Actual inspection date: 30 September 2026. This is a planning report;
there is no QuoteExtrema RTL test, utilization, timing, or physical result.

## Source and target checks

- Inspected the owner's five public repositories: QuoteExtrema, framelatch,
  tapestep, icebbo, and limit-order-book. Read FrameLatch protocol/RTL/model
  and icebbo protocol to determine compatibility.
- Compared local FrameLatch RTL with revision
  `8d2ce380478418aeb4fc07ed3407d590143f3cdd`; equal after newline normalization.
- Checked the provisional pin assignment against IceStorm's iCEBreaker
  example and board features against the board documentation. No physical
  revision or electrical test was performed.

## Tool discovery

Found installed OSS CAD Suite release `20260928` at
`C:\Users\jacob\tools\oss-cad-suite-20260928`. Activated its supplied
`environment.ps1` in a child PowerShell session, then queried tools:

| Tool | Observed version or discovery |
| --- | --- |
| Python via `py -3 --version` | 3.13.1 |
| Icarus via `iverilog -V` | 14.0 devel, `s20260301-500-g2e81fcccb-dirty` |
| Yosys via `yosys -V` | 0.69+154, git `30d62572e-dirty` |
| nextpnr via `nextpnr-ice40 --version` | `nextpnr-0.11.1-34-gc4fbb55a` |
| `icepack`, `iceprog`, `vvp` | Executables present in the selected suite's bin directory |

The reported `dirty` suffixes are distributor version strings; they are
retained exactly rather than claimed to identify clean upstream builds.
Executable discovery does not prove a build or board programming succeeded.
The suite is installed but not on the default shell PATH. Future scripts
must activate or locate it explicitly. Do not imply these 2026 tools were
available on the supplied 2025 planning calendar.

## Protocol example cross-check

Evaluated a whole-message polynomial-division CRC and an independently
written bytewise shift-register CRC with Python 3.13.1. Both agreed on
the `123456789 -> F4` check and all eight complete-frame examples saved
in `docs/PROTOCOL.md`. Each example's payload length was derived from
its bytes before CRC calculation. All nine comparisons passed.

This checks CRC arithmetic for proposed examples only. It is not a
differential RTL test or coverage result. The vectors will be included
in the executable regression suite when the model is implemented.

## Document and checkpoint checks

Checked all six Markdown files' relative links: six links resolved.
Parsed the eight saved hexadecimal frames and verified marker, exact length,
legal length range, and CRC using polynomial division; all passed. Parsed
the constraint file: six named ports with no duplicate pin numbers.
`git diff --check` passed for the tracked README change. No files were staged
or committed as part of these planning checks.

Python's first UK-timezone check failed because its installation has no
`tzdata` package. Used Windows `GMT Standard Time` via .NET `TimeZoneInfo`
instead. Checked winter offset zero and summer offset +1 hour. Checkpoint
arithmetic gave `2025-01-16T13:17:29+00:00 + 5h24m =
2025-01-16T18:41:29+00:00`. This is a proposed metadata timestamp, not
the date these checks were performed.

The read-only subagent review found one timeout wording ambiguity: a host
idle gap below 2 ms can still exceed 2 ms between completed UART bytes.
Corrected the contract to completion-to-completion timing and specified
an idle-gap margin of less than 1.8 ms. The remaining protocol, reset,
counter, readback, provisional-pin, and evidence rules passed its review.

## Open acceptance work

All RTL, model, differential, synthesis, timing, host-serial, and physical
acceptance cases remain pending. The target and pin map are provisional
until the purchased board revision is identified. A board, USB cable, and
working programmer/UART drivers are required for physical completion.
