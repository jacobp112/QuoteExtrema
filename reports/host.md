# Host checker verification

Actual verification date: 4 October 2026. All tests use a reference serial
transport or a mocked port-opening failure. No board or physical COM port
was used. Machine-readable results and source hashes are in
[host.json](host.json).

Executed `py -3 scripts/run.py unit`: 24 tests passed, comprising the
previous 11 model/corpus tests, ten host transaction tests, and three
CLI failure/evidence-preservation tests. A virtual environment installed
the pinned pySerial 3.5 dependency successfully. `scripts/demo.py --help`
also passed; no physical serial invocation was attempted.

The reference-transport sequence verifies 81 snapshots for seed 1931 with
1,000 random quotes. It records 8,734 requested TX bytes and 1,215 received
bytes, exactly one busy-read rejection, three CRC errors, and one truncated
frame abort. Responses arrive in two-byte chunks to exercise assembly.
The transport advances input in UART-byte periods and holds a response
busy for fifteen periods. This simplified model checks host ordering and
admission assumptions; it is not a bit-level UART or electrical simulation.
The separate RTL UART tests cover actual bit timing in simulation.

Fault injection confirms that bad CRC, wrong ID, wrong state, duplicate
response, missing response, truncated response, and partial write fail.
A final chunk arriving after the overall deadline also fails. A raised
write exception retains the requested packet and its unknown write count
in the failure log, without retrying it.
Tests also check snapshot survival across a later serial reset, stale
state detection when checking physical-reset emptiness, ID wrap, and
seed reproducibility. CLI tests confirm nonzero exit plus saved failure
data when opening a port fails, preservation of existing evidence, and
image/hash rejection before opening the port.

A14 is implemented and verified through simulated transport. Actual USB
driver timing, electrical communication, programming, physical reset, and
photographs/video remain pending A15. The [hardware procedure](../docs/HARDWARE.md)
describes those remaining checks. No host test result is a board result.
