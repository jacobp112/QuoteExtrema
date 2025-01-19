"""Verify a programmed board over UART and save the observed session."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from quoteextrema.host import QuoteClient, run_demo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="actual UART COM port, e.g. COM7")
    parser.add_argument("--board-revision", required=True, help="printed revision of the classic iCEBreaker")
    parser.add_argument("--cable", required=True, help="USB data cable / interface description")
    parser.add_argument("--driver", required=True, help="observed FTDI UART driver name and version")
    parser.add_argument("--bitstream", type=Path, default=ROOT / "build/icebreaker/quoteextrema.bin")
    parser.add_argument("--build-report", type=Path, default=ROOT / "build/icebreaker/result.json")
    parser.add_argument("--output", type=Path, required=True, help="new JSON session file; never overwritten")
    parser.add_argument("--seed", type=int, default=1931)
    parser.add_argument("--random-quotes", type=int, default=1000)
    parser.add_argument("--verify-hardware-reset", action="store_true",
                        help="prompt for a physical reset before checking the initial empty state")
    args = parser.parse_args()
    if args.random_quotes < 0:
        parser.error("--random-quotes must be nonnegative")
    if args.output.exists():
        parser.error("--output already exists; use a new session path")
    # A serial checker must identify the image whose build it is reporting.
    build = json.loads(args.build_report.read_text())
    bitstream_hash = hashlib.sha256(args.bitstream.read_bytes()).hexdigest()
    if build.get("status") != "passed" or build.get("artifact_sha256", {}).get("quoteextrema.bin") != bitstream_hash:
        parser.error("bitstream does not match a passing build report")
    if (build.get("device"), build.get("package"), build.get("clock_mhz")) != ("iCE40UP5K", "sg48", 12):
        parser.error("build report is not the expected UP5K-SG48 / 12 MHz target")
    try:
        import serial
    except ImportError:
        parser.error("install requirements-host.txt in a virtual environment first")
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True)
    result = dict(actual_run_utc=datetime.now(timezone.utc).isoformat(), status="started",
                  board="classic iCEBreaker / iCE40UP5K-SG48", board_revision=args.board_revision,
                  declared_clock_hz=12000000, baud=115200, format="8N1", port=args.port,
                  cable=args.cable, uart_driver=args.driver, python=sys.version,
                  pyserial=serial.VERSION, operating_system=platform.platform(),
                  git_revision=revision.stdout.strip() if revision.returncode == 0 else None,
                  bitstream_sha256=bitstream_hash, build_tools=build["versions"],
                  build_seed=build["seed"], lut_mapper=build["lut_mapper"],
                  physical_reset_check_requested=args.verify_hardware_reset,
                  complete_physical_acceptance=False)
    client = None
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Reserve the file before touching hardware, without replacing previous evidence.
    with args.output.open("x") as report:
        try:
            if args.verify_hardware_reset:
                input("Press and release the board reset button, stop other UART traffic, then press Enter: ")
            with serial.Serial(args.port, 115200, bytesize=serial.EIGHTBITS,
                               parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
                               timeout=0.05, write_timeout=1, xonxoff=False,
                               rtscts=False, dsrdtr=False) as port:
                port.reset_input_buffer()
                client = QuoteClient(port)
                client.record("initial_rx_buffer_discard")
                client.record("idle", seconds=0.03)
                client.sleep(0.03)
                result["sequence"] = run_demo(client, seed=args.seed, random_quotes=args.random_quotes,
                                              verify_initial_empty=args.verify_hardware_reset)
            result["status"] = "serial_checks_passed"
            result["physical_reset_empty_passed"] = args.verify_hardware_reset
        except KeyboardInterrupt:
            result["status"] = "interrupted"
            result["error"] = "operator interrupted the serial session"
        except Exception as error:
            result["status"] = "failed"
            result["error"] = f"{type(error).__name__}: {error}"
        finally:
            result["finished_utc"] = datetime.now(timezone.utc).isoformat()
            result["events"] = client.events if client else []
            result["checks"] = client.checks if client else []
            json.dump(result, report, indent=2)
            report.write("\n")
    print(f"{result['status']}: {args.output}")
    if result["status"] != "serial_checks_passed":
        print(result["error"], file=sys.stderr)
        return 1
    print(f"Verified {result['sequence']['snapshots_verified']} snapshots; photos and reset-during-TX evidence remain separate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
