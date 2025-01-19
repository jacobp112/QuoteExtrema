"""Synthesize, route, timing-check, and pack the iCEBreaker bitstream."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from run import ROOT, environment
from streams import uart_cases


def digest(path, *, normalize=False):
    data = path.read_bytes()
    if normalize:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def invoke(command, env, log):
    result = subprocess.run(list(map(str, command)), cwd=ROOT, env=env,
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write_text(result.stdout)
    print("+ " + " ".join(map(str, command)), flush=True)
    print("\n".join(result.stdout.splitlines()[-8:]), flush=True)
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}); see {log}")
    return result.stdout


def synchronizers(module):
    result = {}
    for name in ("button_meta", "button_sync", "input_uart.rx_meta", "input_uart.rx_sync"):
        net = module["netnames"][name]
        if net.get("attributes", {}).get("async_reg") != "true":
            raise RuntimeError(f"synchronizer attribute missing: {name}")
        if net.get("attributes", {}).get("init") != "1":
            raise RuntimeError(f"synchronizer initialization missing: {name}")
        if name.endswith("meta"):
            bit = net["bits"][0]
            loads = [(cell_name, port) for cell_name, cell in module["cells"].items()
                     for port, bits in cell["connections"].items()
                     if cell["port_directions"][port] == "input" and bit in bits]
            if len(loads) != 1 or loads[0][1] != "D":
                raise RuntimeError(f"first synchronizer stage has unexpected loads: {name}: {loads}")
            result[name] = dict(init=1, async_reg=True, loads=loads)
        else:
            result[name] = dict(init=1, async_reg=True)
    startup = module["netnames"]["startup"]
    if startup.get("attributes", {}).get("init") != "00000":
        raise RuntimeError("startup reset counter initialization was not preserved")
    result["startup"] = dict(init=startup["attributes"]["init"])
    return result


def mapped_chains(module):
    cells = module["cells"]

    def loads(bit):
        return [(name, port) for name, cell in cells.items()
                for port, bits in cell["connections"].items()
                if cell["port_directions"][port] == "input" and bit in bits]

    result = {}
    for pin in ("button_n", "uart_rx"):
        bit = module["ports"][pin]["bits"][0]
        consumers = loads(bit)
        if len(consumers) == 1 and cells[consumers[0][0]]["type"] == "SB_LUT4":
            # Initial-one FFs are legalized as initial-zero FFs with inversions.
            bit = cells[consumers[0][0]]["connections"]["O"][0]
            consumers = loads(bit)
        if len(consumers) != 1 or consumers[0][1] != "D":
            raise RuntimeError(f"unexpected asynchronous entry path for {pin}: {consumers}")
        first = consumers[0][0]
        if cells[first]["type"] != "SB_DFF":
            raise RuntimeError(f"first input stage is not a free-running FF: {pin}")
        second_load = loads(cells[first]["connections"]["Q"][0])
        if len(second_load) != 1 or second_load[0][1] != "D":
            raise RuntimeError(f"first-stage fan-out is unsafe: {pin}: {second_load}")
        second = second_load[0][0]
        if cells[second]["type"] != "SB_DFF":
            raise RuntimeError(f"second input stage is not a free-running FF: {pin}")
        clock = module["ports"]["clk_12m"]["bits"]
        if cells[first]["connections"]["C"] != clock or cells[second]["connections"]["C"] != clock:
            raise RuntimeError(f"input stages use a different clock: {pin}")
        result[pin] = dict(first_cell=first, second_cell=second, first_stage_load_count=1)
    return result


def placed_chains(mapped, routed, timing, chains):
    result = {}
    for pin, chain in chains.items():
        first_bit = mapped["cells"][chain["first_cell"]]["connections"]["Q"][0]
        aliases = [name for name, net in mapped["netnames"].items() if net["bits"] == [first_bit]]
        nets = [net for net in timing["detailed_net_timings"] if net["net"] in aliases]
        if len(nets) != 1 or len(nets[0]["endpoints"]) != 1:
            raise RuntimeError(f"cannot verify routed synchronizer chain: {pin}")
        net = nets[0]
        endpoint = net["endpoints"][0]
        source_bel = routed["cells"][net["driver"]]["attributes"]["NEXTPNR_BEL"]
        sink_bel = routed["cells"][endpoint["cell"]]["attributes"]["NEXTPNR_BEL"]
        result[pin] = dict(first_bel=source_bel, second_bel=sink_bel,
                           same_tile=source_bel.rsplit("/", 1)[0] == sink_bel.rsplit("/", 1)[0],
                           reported_delay_ns=endpoint["delay"])
    return result


def mapped_simulation(build, env, verilog, suite):
    compiler = shutil.which("iverilog", path=env["PATH"])
    simulator = shutil.which("vvp", path=env["PATH"])
    suite_root = Path(suite).resolve() if suite else Path(shutil.which("yosys", path=env["PATH"])).parent.parent
    cells = suite_root / "share/yosys/ice40/cells_sim.v"
    if not compiler or not simulator or not cells.is_file():
        raise RuntimeError("Icarus or iCE40 simulation cells missing")
    actions, expected = uart_cases()
    action_path, expected_path = build / "actions.txt", build / "expected.hex"
    action_path.write_text("".join(f"{op} {value}\n" for op,value in actions))
    expected_path.write_text("".join(f"{byte:02x}\n" for byte in expected))
    executable = build / "mapped.vvp"
    invoke([compiler, "-g2012", "-DGATE_LEVEL", "-s", "tb_uart", "-o", executable,
            verilog, cells, ROOT / "tests/tb_uart.sv"], env, build / "mapped-compile.log")
    output = invoke([simulator, executable, f"+actions={action_path.as_posix()}",
                     f"+expected={expected_path.as_posix()}", f"+count={len(expected)}",
                     "+baud_ppm=0", "+phase_ps=37000"], env, build / "mapped-simulation.log")
    if f"PASS UART: {len(expected)} bytes matched" not in output:
        raise RuntimeError("mapped simulation incomplete")
    return dict(response_bytes=len(expected), host_baud=115200,
                zero_delay=True, optimized_diagnostic_checks_skipped=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", help="extracted OSS CAD Suite directory; otherwise use PATH")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--lut-mapper", choices=("builtin", "abc9"), default="builtin",
                        help="builtin avoids the selected Windows release's XAIGER2 failure")
    args = parser.parse_args()
    env = environment(args.suite)
    tools = {name: shutil.which(name, path=env["PATH"])
             for name in ("yosys", "nextpnr-ice40", "icepack")}
    if not all(tools.values()):
        raise RuntimeError("build tools missing; activate the suite or pass --suite")
    build = ROOT / "build/icebreaker"
    build.mkdir(parents=True, exist_ok=True)
    netlist = build / "netlist.json"
    elaborated = build / "elaborated.json"
    mapped_verilog = build / "mapped.v"
    routed = build / "routed.json"
    pnr_report = build / "nextpnr.json"
    asc, bitstream = build / "quoteextrema.asc", build / "quoteextrema.bin"
    bitstream.unlink(missing_ok=True)
    sources = sorted((ROOT / "rtl").glob("*.sv"))
    script = build / "synth.ys"
    script.write_text("read_verilog -sv -D SYNTHESIS " + " ".join(f'"{p.as_posix()}"' for p in sources)
                      + "\nhierarchy -check -top quoteextrema_top\n"
                      + f'proc\nflatten\nwrite_json "{elaborated.as_posix()}"\n'
                      + f'synth_ice40 -device u {"-noabc " if args.lut_mapper == "builtin" else ""}'
                      + f'-top quoteextrema_top -json "{netlist.as_posix()}"\n'
                      + f'check -assert\nstat\nwrite_verilog -noattr -noexpr "{mapped_verilog.as_posix()}"\n')
    result_path = build / "result.json"
    result = dict(actual_run_utc=datetime.now(timezone.utc).isoformat(), status="started",
                  device="iCE40UP5K", package="sg48", clock_mhz=12, seed=args.seed,
                  lut_mapper=args.lut_mapper)
    try:
        versions = {}
        for name, flag in (("yosys", "-V"), ("nextpnr-ice40", "--version")):
            versions[name] = invoke([tools[name], flag], env, build / f"{name}-version.log").strip()
        result["versions"] = versions
        invoke([tools["yosys"], "-Q", "-T", "-s", script], env, build / "yosys.log")
        module = json.loads(netlist.read_text())["modules"]["quoteextrema_top"]
        result["synthesis_cells"] = dict(Counter(cell["type"] for cell in module["cells"].values()))
        result["initialization_and_cdc"] = synchronizers(
            json.loads(elaborated.read_text())["modules"]["quoteextrema_top"])
        result["mapped_input_chains"] = mapped_chains(module)
        result["mapped_simulation"] = mapped_simulation(build, env, mapped_verilog, args.suite)
        invoke([tools["nextpnr-ice40"], "--up5k", "--package", "sg48", "--json", netlist,
                "--pcf", ROOT / "constraints/icebreaker.pcf", "--asc", asc,
                "--write", routed, "--report", pnr_report, "--detailed-timing-report",
                "--freq", "12", "--seed", args.seed], env, build / "nextpnr.log")
        result["place_and_route"] = json.loads(pnr_report.read_text())
        result["placed_input_chains"] = placed_chains(
            module, json.loads(routed.read_text())["modules"]["top"],
            result["place_and_route"], result["mapped_input_chains"])
        timing = result["place_and_route"]["fmax"]
        if not timing or any(value["achieved"] < value["constraint"] for value in timing.values()):
            raise RuntimeError("routed report does not meet every reported clock constraint")
        invoke([tools["icepack"], asc, bitstream], env, build / "icepack.log")
        result["source_sha256_lf"] = {p.relative_to(ROOT).as_posix(): digest(p, normalize=True) for p in sources}
        result["constraint_sha256_lf"] = digest(ROOT / "constraints/icebreaker.pcf", normalize=True)
        result["artifact_sha256"] = {p.name: digest(p) for p in (netlist, asc, bitstream)}
        result["bitstream_bytes"] = bitstream.stat().st_size
        result["status"] = "passed"
    except Exception as error:
        result["status"] = "failed"
        result["error"] = str(error)
        raise
    finally:
        result_path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k:v for k,v in result.items() if k != "place_and_route"}, indent=2))
    print("PASS build: target constraints met; bitstream packed")


if __name__ == "__main__":
    main()
