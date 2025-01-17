"""Run reference unit tests and byte-interface differential simulation."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

from quoteextrema.model import DeviceModel, INTERFACE_COUNTERS
from quoteextrema.protocol import FRAME_COUNTERS
from streams import smoke_stream, uart_smoke


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


def simulate(events, build, env):
    build.mkdir(parents=True, exist_ok=True)
    device = DeviceModel()
    transmitted = []
    vectors = build / "vectors.txt"
    with vectors.open("w", newline="\n") as output:
        for event in events:
            signals = dict(rst=False, valid=False, data=0, abort=False, error=False,
                           tx_ready=True, tx_idle=True)
            signals.update(event)
            before_tx = device.peek_tx(rst=signals["rst"])
            byte = device.step(**signals)
            if byte is not None:
                transmitted.append(byte)
            state = device.state
            counts = {**device.receiver.counts, **device.counts}
            row = [signals[key] for key in ("rst", "valid", "data", "abort", "error", "tx_ready", "tx_idle")]
            row += [before_tx is not None, before_tx if before_tx is not None else -1,
                    state.bid, state.ask, int(state.bid_valid) | int(state.ask_valid) << 1, device.busy]
            row += [counts[key] for key in FRAME_COUNTERS + INTERFACE_COUNTERS]
            output.write(" ".join(str(int(value)) for value in row) + "\n")
    iverilog = shutil.which("iverilog", path=env["PATH"])
    vvp = shutil.which("vvp", path=env["PATH"])
    if not iverilog or not vvp:
        raise RuntimeError("Icarus tools missing; activate OSS CAD Suite or provide --suite")
    executable = build / "simulation.vvp"
    sources = [ROOT / "rtl" / name for name in
               ("framelatch.sv", "quote_core.sv", "frame_tx.sv", "quote_interface.sv")]
    checked([iverilog, "-g2012", "-Wall", "-s", "tb_link", "-o", executable,
             *sources, ROOT / "tests/tb_link.sv"], env=env)
    log = checked([vvp, executable, f"+vectors={vectors.as_posix()}"], env=env)
    if f"PASS differential: {len(events)} cycles" not in log:
        raise RuntimeError("simulation did not confirm every generated cycle")
    result = dict(cycles=len(events), counts=counts,
                  final_state=vars(device.state), tx_bytes=bytes(transmitted).hex())
    (build / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def simulate_uart(build, env):
    build.mkdir(parents=True, exist_ok=True)
    actions, expected = uart_smoke()
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
    log = checked([vvp, executable, f"+actions={action_path.as_posix()}",
                   f"+expected={expected_path.as_posix()}", f"+count={len(expected)}"], env=env)
    if f"PASS UART: {len(expected)} bytes matched" not in log:
        raise RuntimeError("UART simulation did not confirm all expected bytes")
    return dict(response_bytes=len(expected), host_baud=115200, clock_hz=12000000)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("unit", "smoke", "uart", "all"))
    parser.add_argument("--suite", help="extracted OSS CAD Suite directory; otherwise use PATH")
    args = parser.parse_args()
    if args.command in ("unit", "all"):
        checked([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"])
    if args.command in ("smoke", "all"):
        print(json.dumps(simulate(smoke_stream(), ROOT / "build/smoke", environment(args.suite)), indent=2))
    if args.command in ("uart", "all"):
        print(json.dumps(simulate_uart(ROOT / "build/uart", environment(args.suite)), indent=2))


if __name__ == "__main__":
    main()
