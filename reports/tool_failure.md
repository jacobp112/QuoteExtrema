# Synthesis tool failure and selected mapping flow

Actual observation date: 4 October 2026. The first build used the selected
OSS CAD Suite `20260928` Yosys release's default ABC9 LUT mapping. RTL
elaboration and earlier synthesis stages completed, but XAIGER2 export
aborted with:

```text
Warning: Feature 'write_xaiger2' is experimental.
ERROR: Assert `data_start == f->tellp()' failed in /work/_builds/windows-x64/yosys/yosys/backends/aiger2/aiger.cc:1078.
```

Yosys exited with status 1. Place-and-route had not run, so this attempt
produced no timing result. The original full log is preserved locally at
`build/icebreaker/yosys-abc9-failure.log`. No source RTL change was needed.
The precise underlying tool defect was not diagnosed; the reported failure
location identifies the backend stage, not an established root cause.

The installed `help synth_ice40` documents `-noabc`, which uses built-in
LUT techmapping instead of ABC9. The reproducible default flow therefore
uses `synth_ice40 -device u -noabc`. Resource and timing results apply to
that mapper. They are not a comparison with a successful ABC9 build.
`scripts/build.py --lut-mapper abc9` retains the alternative for diagnosis.
Neither flow permits a timing-failure override.

An initial netlist check also assumed named RTL registers and `init=1`
attributes would remain unchanged after technology mapping. That check
stopped on missing `button_meta`. Inspection showed two mapped FFs still
present: initial-one registers were legalized using initial-zero FFs and
inversions, and some original names disappeared.

The corrected checks inspect initialization and synchronizer attributes
after elaboration, trace both two-FF chains after mapping, require each
first FF to feed only the second FF's D port, and verify the common clock.
The mapped primitive netlist is also simulated through the board UART
sequence, including configuration startup and reset/recovery. Thus the
check was adapted to the mapped representation rather than removed.

There is no failed 12 MHz timing result in this project. The successful
target-device implementation and its limits are recorded separately in
[synthesis.md](synthesis.md).
