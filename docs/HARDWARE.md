# Board bring-up and evidence

Physical status: pending. No iCEBreaker, serial port, programming run, or
board photograph has been supplied. The source and target build are ready
for the following procedure; [host tests](../reports/host.md) exercise a
reference transport only.

## Obtain and identify the board

Use the classic iCEBreaker with UP5K-SG48, its onboard FT2232H, and a USB
data cable. The [manufacturer's hardware documentation](https://docs.icebreaker-fpga.org/hardware/icebreaker/)
describes the 12 MHz oscillator and programming/UART connections. Record the
printed board revision and compare its schematic with
[BOARD.md](BOARD.md) and `constraints/icebreaker.pcf`. Do this before loading
the image. A different FPGA, package, revision pin map, or clock requires a
new implementation build and report.

On Windows, identify the FTDI programming interface A and UART interface B
by device serial number. Record driver names/versions and the UART COM port.
If the programming interface requires a libusb-compatible driver, change
only that interface; preserve the UART's VCP driver. This project has not
validated a driver installation on hardware. Disconnect unrelated FTDI
programmers or select the intended serial number explicitly.

## Build and explicitly program

First reproduce the [verification and build commands](BUILD.md). Activate
the selected suite in the shell, for example:

```powershell
. 'C:\path\to\oss-cad-suite\environment.ps1'
iceprog --help
```

The selected suite's help was inspected. Its default mode writes and
verifies SPI flash; interface A is the default. This command replaces the
flash image on the selected board, so retain any existing image you need:

```powershell
iceprog -I A -d 's:0x0403:0x6010:YOUR_BOARD_SERIAL' build/icebreaker/quoteextrema.bin
if ($LASTEXITCODE -ne 0) { throw 'Programming or verification failed' }
```

Replace the serial number with the observed device identity. Save complete
programming output and the exact invocation in the evidence directory.
Do not use `-X` to skip verification. SRAM programming (`-S`) depends on
the board's jumper configuration and is not assumed here. See the
[iceprog source and usage](https://github.com/YosysHQ/icestorm/blob/main/iceprog/iceprog.c)
for programmer options. None of these programming commands has been run
against a board during this project.

After successful configuration, hold and release the user reset button.
Both active-low valid LEDs should be off until their side receives a quote.
Check CDONE and power indications if configuration fails. Record the clock
as the board's specified 12 MHz source; label any oscilloscope frequency
measurement separately with the instrument and measured value.

## Run the serial checker

```powershell
py -3 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements-host.txt
& .\.venv\Scripts\python.exe -m serial.tools.list_ports -v
& .\.venv\Scripts\python.exe scripts/demo.py `
  --port COM7 --board-revision 'ACTUAL_PRINTED_REVISION' `
  --cable 'ACTUAL_CABLE_DESCRIPTION' --driver 'ACTUAL_DRIVER_AND_VERSION' `
  --output evidence/session-ACTUAL-RUN-UTC.json --verify-hardware-reset
if ($LASTEXITCODE -ne 0) { throw 'Serial checks failed; preserve the session log' }
```

Substitute the observed COM port and hardware details; the example values
are placeholders. Stop other applications using that port. The optional
reset prompt requires the operator to press and release the physical
button before the initial read; that first check sends no serial reset.
Without the option, the script establishes an empty state using serial
reset and records no physical reset result.

The host uses pySerial 3.5, 115200 baud, 8N1, no flow control, bounded reads
and writes. The [pySerial API](https://pyserial.readthedocs.io/en/latest/pyserial_api.html)
allows partial reads; the checker assembles exactly 15 response bytes
within an overall deadline. It rejects bad CRC/type/flags, wrong request
IDs or prices, incomplete responses, and unexpected extra response bytes.
A partial write stops the run without retrying a potentially timed-out
frame. The port's RTS/DTR signals do not provide this design's button reset.

The default sequence checks 81 snapshots: first, repeated, worse, and
improving prices; 13 malformed inputs; truncated-frame timeout recovery;
quotes during readback; a second busy READ; serial reset after snapshot;
zero, maximum, crossed extremes; and 1,000 seeded quotes in batches of 20.
Each accepted READ has an independent expected snapshot from `QuoteState`.
READ plus following traffic is sent in one write, so the captured state
must precede that traffic. A 20 ms quiet check detects an unexpected second
response and allows outgoing traffic and the final stop bit to finish.
USB scheduling that breaks the protocol's inter-byte timing can fail these
checks and must be investigated rather than ignored.

The script verifies the local bitstream hash against a passing build report
before opening the port. This ties the recorded image to a build; successful
programmer verification must separately establish that this image was
loaded. The JSON contains actual UTC times, declared hardware metadata,
Python/pySerial and build versions, image hash, seed, requested TX bytes,
write counts, received chunks, and expected/observed snapshots. Failures
return nonzero and retain collected data. An existing output is never
overwritten. `serial_checks_passed` covers the scripted serial checks only;
`complete_physical_acceptance` remains false until the separate evidence
review below.

## Reset during transmission and capture evidence

A UART response lasts about 1.3 ms, too short to assume a button press
occurred within TX merely from a human instruction. Capture UART TX and
the reset-button signal with a logic analyzer or oscilloscope while
issuing repeated READs and pressing reset. Repeat until the capture shows
reset asserted after TX starts and before its final stop bit. Record the
instrument, sample rate, decode settings, and trace. The expected outcome
is cancellation of the response; an incomplete frame is then a deliberate
reset result, not a passing normal read. Preserve that failed session,
release reset, stop traffic, and rerun the empty-state/recovery check.
Never label an uncaptured button press as a verified reset-during-TX test.

Add clear photographs of the connected board, printed revision, programmer
connection, and valid LEDs, or a short video with those details and the
host's final result visible. Identify which session and bitstream each
capture accompanies. Use [the evidence record](../evidence/TEMPLATE.md)
to record actual observations, failures and fixes. A15 remains pending
until board identification, flash verification, scripted checks, physical
reset/recovery, and authentic photographs/video are reviewed together.
