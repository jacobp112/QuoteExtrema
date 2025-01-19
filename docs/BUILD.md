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

## Target-device build

```powershell
py -3 scripts/build.py --suite $suiteRoot --seed 1
```

The build script elaborates RTL, checks hierarchy, maps iCE40 primitives,
checks initialization and synchronizer topology, runs the nominal host UART
sequence against the mapped netlist, routes UP5K-SG48 with the PCF pin map,
requires 12 MHz timing, and packs `build/icebreaker/quoteextrema.bin`.
No timing-allow-fail or unconstrained-pin override is used.

The default LUT mapper is the supported built-in Yosys path (`-noabc`),
because the selected Windows release's ABC9/XAIGER2 backend aborted in the
observed initial build. See [tool_failure.md](../reports/tool_failure.md).
`--lut-mapper abc9` is available for diagnosis; its results must be validated
separately. Changing mapper, suite, seed, clock, sources, or constraints
requires a new implementation report.

Logs, generated synthesis script, elaborated/mapped/routed netlists, detailed
timing JSON, mapped simulation inputs, bitstream, and result JSON remain in
`build/icebreaker/`. On failure the result records its status and error;
the script stops nonzero. A previous bitstream is removed before starting,
and a new one is packed only after the preceding checks pass.

Mapped simulation uses the selected suite's `share/yosys/ice40/cells_sim.v`
with zero delays. Diagnostic-counter checks are omitted in that simulation
because those unused ports are optimized out of the board top; functional
UART bytes and reset recovery remain checked. It supplements RTL simulation
and routed static timing, and is not a physical test.

Source/constraint hashes are calculated after CRLF-to-LF normalization.
Binary artifact hashes identify the observed local build. Tool-generated
netlists contain source paths, so byte hashes of intermediate files can
depend on checkout location even when functional RTL is identical.
No test or build command programs hardware. Host-serial instructions follow
when that demonstration tool is implemented.
