# Reproducing builds and tests

Run from the repository root with Python 3.10 or newer. Current observations
use Python 3.13.1 and Windows x64 OSS CAD Suite release `20260928`; exact
tool strings are recorded in [planning.md](../reports/planning.md).
The model and current test runner require only Python's standard library.

Download the matching suite from the
[official release](https://github.com/YosysHQ/oss-cad-suite-build/releases/tag/2026-09-28)
and extract it. Provide the directory containing `bin/` and `lib/` through
`--suite`, or activate the distributor's environment and use PATH. The
runner changes environment only for child processes, not global settings.

```powershell
$suiteRoot = 'C:\path\to\oss-cad-suite'
py -3 scripts/run.py unit
py -3 scripts/run.py smoke --suite $suiteRoot
py -3 scripts/run.py uart --suite $suiteRoot
```

`all` runs all three current checks. Tests exit nonzero on a Python failure,
compile error, simulator failure, missing simulator tools, or incomplete
simulation result. The byte-interface runner also requires an explicit
PASS count equal to the number of generated input edges; a clean process
exit alone is not sufficient.

The generated `build/smoke/vectors.txt` contains inputs and expected
post-edge state/counters, plus pre-edge TX data/valid. `tb_link.sv` checks
every row. Its final model state and oracle bytes are in
`build/smoke/result.json`. UART inputs and expected output bytes are in
`build/uart/actions.txt` and `build/uart/expected.hex`; `tb_uart.sv` drives
the physical top-level RX signal and checks the TX waveform at nominal
115200 host baud. These files are intermediate simulation outputs and
are regenerated, not checked in as physical evidence.

The top-level RTL defaults to 12 MHz, 104 clocks per UART bit, and 24,000
clocks for byte-completion timeout. Parameter overrides for simulation
must not be confused with the programmed board's clock or baud.

Synthesis, place-and-route, host-serial, and full regression entry points
will be documented when implemented and exercised. No programming command
is run as part of the current test commands.
