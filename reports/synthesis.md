# Target-device synthesis and timing

Actual build date: 4 October 2026. Device: iCE40UP5K, SG48, provisional
classic iCEBreaker pin map, external 12 MHz clock. No board was programmed.
Machine-readable measurements are in [synthesis.json](synthesis.json).

Executed:

```powershell
py -3 scripts/build.py --suite C:\Users\jacob\tools\oss-cad-suite-20260928 --seed 1
```

Suite `20260928`, Yosys `0.69+154 / 30d62572e-dirty`, and nextpnr
`nextpnr-0.11.1-34-gc4fbb55a` were used. Yosys mapped with
`synth_ice40 -device u -noabc`, followed by `check -assert` and mapped
zero-delay UART simulation. nextpnr used `--up5k --package sg48 --freq 12
--seed 1`, the PCF file, and detailed reports. No timing-failure override
was passed. icepack produced a 104,090-byte configuration bitstream.

## Measured resource use

| Resource | Used | Available |
| --- | ---: | ---: |
| Packed logic cells | 1065 | 5280 |
| I/O cells | 6 | 39 |
| Global buffers | 6 | 8 |
| Block RAM | 0 | 30 |
| SPRAM | 0 | 4 |
| DSP | 0 | 8 |
| PLL | 0 | 1 |

Packed logic-cell utilization is 20.17%. Before packing, Yosys reports
758 LUT4 cells, 109 carry cells, and 349 FF cells across the listed FF
variants. LUTs, carries, and FFs share packed logic cells; their counts
must not be added and called packed utilization. Global buffers also
include promoted high-fanout control nets; they are not six independent
clock domains. All functional registers use the single 12 MHz clock.

The board top leaves diagnostic counters unconnected, and synthesis removes
them. Their saturation and reset semantics were verified in the byte
interface, where they are observable. Version-1 serial readback exposes
quote state only. Reported board resources do not include retained debug
counters or embedded instrumentation.

## Timing

The routed clock `clk_12m$SB_IO_IN_$glb_clk` reports **28.9922 MHz achieved**
against **12 MHz constrained**. The corresponding critical-path delay is
34.492 ns; the 12 MHz period is 83.333 ns, leaving about 48.841 ns of period
margin according to this static model. The path runs from timeout-counter
logic through abort/receive-control gating. This is not a measured maximum
operating frequency or a claim that the board was clocked above 12 MHz.

There was no 12 MHz timing failure. The initial build failed before routing
in a synthesis backend; [tool_failure.md](tool_failure.md) records it and
the supported mapper used instead. No speed comparison with ABC9 is claimed.

nextpnr also reports asynchronous input-to-clock paths (maximum 5.272 ns)
and clock-to-asynchronous-output paths (maximum 10.522 ns). These are I/O
path delays, not synchronous setup guarantees for UART or button arrivals.
There is no external synchronous I/O timing relationship to constrain.
UART RX and the button enter through the verified two-FF chains below;
their analogue behaviour still needs physical testing.

## Initialization and synchronization

Elaborated JSON retains startup `init=00000` and initial-high input
synchronizers with `async_reg` attributes. After mapping, each asynchronous
input passes through two free-running FFs on the system clock; the first
stage feeds only the second FF's data input. Initial-one FFs are represented
using zero-initialized primitives and inversions, so mapped RTL names and
initialization attributes need not remain identical to source names.

| Input | First FF placement | Second FF placement | Reported chain delay |
| --- | --- | --- | ---: |
| Button | `X16/Y2/lc5` | `X16/Y2/lc6` | 4.078 ns |
| UART RX | `X3/Y1/lc4` | `X3/Y1/lc3` | 4.078 ns |

Both pairs are in the same tile in seed 1. Placement was inspected; no
numerical metastability MTBF is claimed. A different seed requires renewed
inspection. The mapped primitive UART simulation matched 105 response
bytes, including startup, corrupted input, timeout, traffic, and hardware
reset/recovery. It is a zero-delay functional simulation, separate from
routed timing; it does not simulate analogue metastability.

## Artifacts and remaining work

Observed bitstream SHA-256:
`faaffeed972d822bfd89ad96dd32b5a888bb74a688304fd92396ad7ddae88857`.
The bitstream is generated under ignored `build/icebreaker/`; source,
constraints, suite, mapper, and seed are sufficient to rebuild it. Logs
and full detailed timing/netlist reports are preserved there. Checked-in
JSON includes measured utilization/timing, source hashes, and artifact hashes.

A13 passes for the provisional target configuration. Electrical pin/revision
confirmation, programmer/UART driver bring-up, host serial verification,
and photographs/video remain pending. This implementation report does not
meet physical acceptance A15.
