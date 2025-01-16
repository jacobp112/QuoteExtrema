# Board and implementation decisions

The target is the classic iCEBreaker with iCE40UP5K in SG48, an external
12 MHz clock, onboard FT2232H programming/UART, and a USB data cable. This
matches the FPGA family used by the owner's icebbo project and avoids
requiring a fabricated custom board for bring-up. No board has been obtained;
board revision, electrical behaviour, and programming remain unverified.

The [board documentation](https://docs.icebreaker-fpga.org/hardware/icebreaker/)
describes the FPGA, oscillator, and FTDI interface. The provisional pins
below follow the
[IceStorm iCEBreaker example](https://github.com/YosysHQ/icestorm/blob/main/examples/icebreaker/icebreaker.pcf).
Check the actual board revision's schematic before using these constraints.
If its clock or UART connections differ, update constraints and record that
revision before programming. This target is not iCEBreaker Bitsy.

| Top-level port | SG48 pin | Purpose |
| --- | ---: | --- |
| `clk_12m` | 35 | 12 MHz clock |
| `uart_rx` | 6 | Host to FPGA |
| `uart_tx` | 9 | FPGA to host |
| `button_n` | 10 | Active-low hardware-reset button |
| `bid_led_n` | 11 | Active-low bid-valid indicator |
| `ask_led_n` | 37 | Active-low ask-valid indicator |

The design does not drive configuration-flash pins or use FTDI FIFO mode.
Use the onboard UART route. An external adapter, if substituted, must use
3.3 V logic and a common ground; do not connect an RS-232 voltage-level port
directly to FPGA I/O.

## Clock and UART

All RTL runs on the external 12 MHz clock. There is no derived UART clock,
PLL, or CDC FIFO. UART input and button input each pass through a two-flop
synchronizer before downstream logic samples them. The first synchronizer
stage has no fan-out to functional logic. Mark the stages as synchronizers
and preserve them as far as the toolchain supports; verify their mapped
placement in the implementation review. A synchronizer reduces metastability
risk; simulation does not prove its physical reliability.

UART RX validates a start bit at its midpoint and samples data and stop bit
at nominal bit centers. At 12 MHz, integer divider 104 gives approximately
115384.615 baud, a +0.1603% deviation from nominal 115200. TX uses the same
divider. RX must reject a false start and a low stop-bit sample. Following
a framing error, it waits for the line to return high before searching for
a new start, so a sustained break does not produce repeated fake bytes.

The synchronized button level drives a synchronous reset. Holding the
button holds the design in reset; contact bounce can retrigger reset, which
is acceptable for a manual reset control. Input synchronizers continue
running during reset so a held button can be released. Initialize their
input-idle values and use an initialized startup counter to hold system
reset for at least 16 rising clock edges after configuration. Verify that
the iCE40 synthesis flow preserves those initial register values.

RX produces at most one byte per ten UART bit periods, over 1000 core
cycles. FrameLatch has a completed-frame register, and the command decoder
always consumes it on the next edge unless hardware reset is asserted.
The quote core receives only validated complete payloads. TX occupies an
independent single response slot and never backpressures the parser.

## Module boundaries

| Planned file | Responsibility |
| --- | --- |
| `rtl/framelatch.sv` | Pinned CRC receiver, unchanged initially |
| `rtl/quote_core.sv` | Atomic bid/ask updates, quote reset, snapshot fields |
| `rtl/quote_interface.sv` | Payload decoding, read admission, semantic counters |
| `rtl/uart_rx.sv` | Synchronized 8N1 reception and framing errors |
| `rtl/uart_tx.sv` | Byte ready/valid and 8N1 transmission |
| `rtl/frame_tx.sv` | Serialize immutable snapshot, framing, and CRC |
| `rtl/quoteextrema_top.sv` | Board reset, RX timeout, integration, LEDs |

Core state updates in one clock edge; no DSP or memory block is required
by the extrema algorithm. Actual resources are to be measured, not predicted
as synthesis results. Internal counters remain observable to simulation;
their optimization in the board top must be reported if unused outputs are
removed by synthesis.

## Tools and constraints

Selected baseline: Windows x64 OSS CAD Suite release `20260928`, Python
3.13.1 for host/reference tools, Icarus for simulation, Yosys for synthesis,
nextpnr-ice40 for SG48 UP5K placement/routing, and icepack for the bitstream.
This release is already installed locally. Reproducible build instructions
must use an explicit suite directory or activated environment, record tool
versions, and fail if compilation or timing checks fail. The distributor's
[installation instructions](https://github.com/YosysHQ/oss-cad-suite-build)
describe environment activation.

Constrain the system clock to 12 MHz in nextpnr, with no timing-allow-fail
option. Check the actual clock name and utilization after routing. Serial
and button pins are asynchronous to the clock; the only intended entry
paths are their synchronizer first stages. Document the tool's treatment
of asynchronous input paths and inspect internal timed paths. Do not label
external UART transport latency as core datapath latency.

Programming and physical tests will use the actual board's FTDI interface.
On Windows, establish both the programmer's required USB driver and the
UART COM port before programming. Preserve a working serial channel when
changing the programming channel's driver. Record driver and tool versions
in the hardware demonstration report.
