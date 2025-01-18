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
py -3 scripts/run.py regression --suite $suiteRoot
```

`all` runs all four checks. Tests exit nonzero on a Python failure,
compile error, simulator failure, missing simulator tools, or incomplete
simulation result. The byte-interface runner also requires an explicit
PASS count equal to the number of generated input edges; a clean process
exit alone is not sufficient.

The generated `build/smoke/vectors.txt` contains inputs and expected
post-edge state/counters, plus pre-edge TX data/valid. `tb_link.sv` checks
every row. Its final model state and oracle bytes are in
`build/smoke/result.json`. UART inputs and expected output bytes are in
`build/uart/actions.txt` and `build/uart/expected.hex`; `tb_uart.sv` drives
the top-level RX signal in simulation and checks TX at nominal 115200 host
baud and +/-1% offsets. It exercises false starts, bad stops, break,
timeout, traffic during readback, and reset during TX. The timeout-boundary
test injects completed-byte strobes at the wrapper boundary separately.
These files are intermediate simulation outputs and
are regenerated, not checked in as physical evidence.

The top-level RTL defaults to 12 MHz, 104 clocks per UART bit, and 24,000
clocks for byte-completion timeout. Parameter overrides for simulation
must not be confused with the programmed board's clock or baud.

Regression defaults to 20 seeds (1931..1950) and 5000 attempts per seed.
It also runs directed reset/marker/price cases, a saved malformed corpus,
and saturation with counters seeded near their maximum in simulation.
`--seeds` and `--attempts` can reduce debugging time; a reduced run does
not meet the 100,000-attempt acceptance budget. Per-case vectors/results
and the complete regression summary are saved under `build/regression/`.
Failure messages identify a cycle; retain that case's vectors and replay
with the printed `vvp` command. Fixed seeds regenerate the same stream.

Synthesis, place-and-route, and host-serial entry points will be documented
when implemented and exercised. No programming command is run by tests.
