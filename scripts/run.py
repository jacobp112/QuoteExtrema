"""Run reference unit tests and byte-interface differential simulation."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

from quoteextrema.model import DeviceModel, INTERFACE_COUNTERS
from quoteextrema.protocol import FRAME_COUNTERS
from streams import (corpus_stream, directed_stream, random_stream,
                     saturation_stream, smoke_stream, uart_cases)


def environment(suite):
    env = os.environ.copy()
    if suite:
        suite = Path(suite).resolve()
        if not (suite / "bin").is_dir():
            raise ValueError("--suite must name an extracted OSS CAD Suite directory")
        env["PATH"] = os.pathsep.join([str(suite / "bin"), str(suite / "lib"), env.get("PATH", "")])
    return env


def checked(command, *, env=None):
    print("+ " + " ".join(map(str, command)), flush=True)
    result = subprocess.run(list(map(str, command)), cwd=ROOT, env=env,
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(result.stdout, end="", flush=True)
    if result.returncode:
        raise RuntimeError(f"command exited with status {result.returncode}")
    return result.stdout


def simulate(events, build, env, executable=None):
    build.mkdir(parents=True, exist_ok=True)
    device = DeviceModel()
    transmitted = []
    peaks = dict.fromkeys(FRAME_COUNTERS + INTERFACE_COUNTERS, 0)
    vectors = build / "vectors.txt"
    with vectors.open("w", newline="\n") as output:
        for event in events:
            signals = dict(rst=False, valid=False, data=0, abort=False, error=False,
                           tx_ready=True, tx_idle=True)
            signals.update(event)
            seed = signals.pop("_seed", False)
            if seed:
                for counters in (device.receiver.counts, device.counts):
                    counters.update(dict.fromkeys(counters, 0xFFFFFFFE))
            before_tx = device.peek_tx(rst=signals["rst"])
            byte = device.step(**signals)
            if byte is not None:
                transmitted.append(byte)
            state = device.state
            counts = {**device.receiver.counts, **device.counts}
            peaks = {key: max(peaks[key], counts[key]) for key in peaks}
            row = [signals[key] for key in ("rst", "valid", "data", "abort", "error", "tx_ready", "tx_idle")]
            row.append(seed)
            row += [before_tx is not None, before_tx if before_tx is not None else -1,
                    state.bid, state.ask, int(state.bid_valid) | int(state.ask_valid) << 1, device.busy]
            row += [counts[key] for key in FRAME_COUNTERS + INTERFACE_COUNTERS]
            output.write(" ".join(str(int(value)) for value in row) + "\n")
    iverilog = shutil.which("iverilog", path=env["PATH"])
    vvp = shutil.which("vvp", path=env["PATH"])
    if not iverilog or not vvp:
        raise RuntimeError("Icarus tools missing; activate OSS CAD Suite or provide --suite")
    if executable is None:
        executable = compile_link(build, env)
    log = checked([vvp, executable, f"+vectors={vectors.as_posix()}"], env=env)
    if f"PASS differential: {len(events)} cycles" not in log:
        raise RuntimeError("simulation did not confirm every generated cycle")
    result = dict(cycles=len(events), counts=counts, counter_peaks=peaks,
                  final_state=vars(device.state), tx_bytes=bytes(transmitted).hex())
    (build / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def compile_link(build, env):
    build.mkdir(parents=True, exist_ok=True)
    compiler = shutil.which("iverilog", path=env["PATH"])
    if not compiler:
        raise RuntimeError("Icarus compiler missing")
    executable = build / "simulation.vvp"
    sources = [ROOT / "rtl" / name for name in
               ("framelatch.sv", "quote_core.sv", "frame_tx.sv", "quote_interface.sv")]
    checked([compiler, "-g2012", "-Wall", "-s", "tb_link", "-o", executable,
             *sources, ROOT / "tests/tb_link.sv"], env=env)
    return executable


def regression(env, seeds, attempts):
    build = ROOT / "build/regression"
    executable = compile_link(build, env)
    results = {}
    for name, stream in (("directed", directed_stream()), ("saturation", saturation_stream()),
                         ("corpus", corpus_stream())):
        result = simulate(stream, build / name, env, executable)
        results[name] = {key: value for key, value in result.items() if key != "tx_bytes"}
    assert all(value == 0xFFFFFFFF for value in results["saturation"]["counter_peaks"].values())
    for seed in range(1931, 1931 + seeds):
        result = simulate(random_stream(seed, attempts), build / f"seed_{seed}", env, executable)
        results[f"seed_{seed}"] = {key: value for key, value in result.items() if key != "tx_bytes"}
    summary = dict(actual_run_utc=datetime.now(timezone.utc).isoformat(),
                   random_seeds=seeds, attempts_per_seed=attempts,
                   total_random_attempts=seeds * attempts,
                   total_cycles=sum(result["cycles"] for result in results.values()),
                   results=results)
    (build / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"PASS regression: {seeds * attempts} randomized attempts, {summary['total_cycles']} cycles")
    return summary


def simulate_uart(build, env):
    build.mkdir(parents=True, exist_ok=True)
    actions, expected = uart_cases()
    action_path = build / "actions.txt"
    expected_path = build / "expected.hex"
    action_path.write_text("".join(f"{op} {value}\n" for op, value in actions))
    expected_path.write_text("".join(f"{byte:02x}\n" for byte in expected))
    iverilog = shutil.which("iverilog", path=env["PATH"])
    vvp = shutil.which("vvp", path=env["PATH"])
    if not iverilog or not vvp:
        raise RuntimeError("Icarus tools missing; activate OSS CAD Suite or provide --suite")
    executable = build / "simulation.vvp"
    checked([iverilog, "-g2012", "-Wall", "-s", "tb_uart", "-o", executable,
             *sorted((ROOT / "rtl").glob("*.sv")), ROOT / "tests/tb_uart.sv"], env=env)
    for offset, phase in ((-10000, 17000), (0, 37000), (10000, 59000)):
        log = checked([vvp, executable, f"+actions={action_path.as_posix()}",
                       f"+expected={expected_path.as_posix()}", f"+count={len(expected)}",
                       f"+baud_ppm={offset}", f"+phase_ps={phase}"], env=env)
        if f"PASS UART: {len(expected)} bytes matched" not in log:
            raise RuntimeError("UART simulation did not confirm all expected bytes")
    executable = build / "timeout.vvp"
    checked([iverilog, "-g2012", "-Wall", "-s", "tb_timeout", "-o", executable,
             *sorted((ROOT / "rtl").glob("*.sv")), ROOT / "tests/tb_timeout.sv"], env=env)
    log = checked([vvp, executable], env=env)
    if "PASS timeout: boundary byte, expiry, and error priority" not in log:
        raise RuntimeError("timeout priority test incomplete")
    result = dict(response_bytes_per_run=len(expected), host_baud=115200, clock_hz=12000000,
                  baud_offsets_ppm=[-10000, 0, 10000], phases_ns=[17, 37, 59], timeout_priority_passed=True)
    (build / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("unit", "smoke", "uart", "regression", "all"))
    parser.add_argument("--suite", help="extracted OSS CAD Suite directory; otherwise use PATH")
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--attempts", type=int, default=5000)
    args = parser.parse_args()
    if args.command in ("unit", "all"):
        checked([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"])
    if args.command in ("smoke", "all"):
        print(json.dumps(simulate(smoke_stream(), ROOT / "build/smoke", environment(args.suite)), indent=2))
    if args.command in ("uart", "all"):
        print(json.dumps(simulate_uart(ROOT / "build/uart", environment(args.suite)), indent=2))
    if args.command in ("regression", "all"):
        if args.seeds < 1 or args.attempts < 1:
            raise ValueError("seeds and attempts must be positive")
        regression(environment(args.suite), args.seeds, args.attempts)


if __name__ == "__main__":
    main()
