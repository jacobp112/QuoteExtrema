# QuoteExtrema protocol, version 1

This specification is the contract for the RTL and Python reference model.
Prices are unsigned 32-bit integers in host-defined units. Every value from
zero to `0xFFFFFFFF` is valid. There is one instrument and no quantity,
withdrawal, or order identifier. Historical bid and ask extremes may cross.

## Transport and framing

UART is full duplex, nominally 115200 baud, 8 data bits, no parity, one stop
bit, least-significant bit first, idle high. There is no RTS/CTS flow control.
Do not confuse UART bit order with multibyte integer order: integers in the
payload are little endian.

A frame is `0xA5 | length:u8 | payload:length bytes | crc:u8`. Length must be
1..16 inclusive. CRC-8 covers the length byte and every payload byte, in
wire order. The polynomial is `0x07` (`x^8 + x^2 + x + 1`), initialization
`0x00`, no input/output reflection, and final XOR `0x00`. The check for
ASCII `123456789` is `0xF4`. The marker is outside CRC coverage.

The reused FrameLatch receiver searches for `0xA5`, then consumes length,
exactly that many payload bytes, and CRC. A marker inside payload or CRC is
ordinary data. Invalid lengths and failing CRC bytes are consumed and are
not reconsidered as markers. After either rejection, marker search resumes.
CRC success publishes one complete payload through ready/valid; individual
price bytes never reach the quote core. There is no separate end marker.

At the serial wrapper, an incomplete frame aborts after 24,000 system-clock
cycles (2 ms at 12 MHz) without a completed UART byte. A byte completing on
the timeout edge takes priority and restarts the timer. UART framing error
has priority over a byte and aborts assembly immediately. Only a pending
partial frame produces an incomplete-frame count; an idle timeout does not.
Timeout uses byte-completion strobes, not individual line transitions.
Within a frame, successive byte completions must be less than 2 ms apart.
At nominal baud, a byte takes about 86.8 microseconds, so the host should
keep idle gaps between bytes below 1.8 ms to leave a margin.

After suspected byte loss, wait at least 2 ms with RX idle high before
starting a new frame. This protocol cannot guarantee immediate recovery
under arbitrary byte loss. CRC-8 detects many corruptions but is not an
authentication mechanism and cannot reject every possible corrupted stream.

## Payloads

Exact lengths are mandatory; trailing bytes make a command invalid even
when the frame CRC passes. Reserved message types are rejected.

| Type | Payload length | Bytes after type | Meaning |
| --- | ---: | --- | --- |
| `0x01` | 5 | `price:u32` | Bid observation |
| `0x02` | 5 | `price:u32` | Ask observation |
| `0x03` | 3 | `request_id:u16` | Read snapshot |
| `0x04` | 1 | None | Reset quote state |
| `0x83` | 12 | `request_id:u16 flags:u8 bid:u32 ask:u32` | Device snapshot response |

`0x83` is an output type and is rejected if received as a command.
The opaque request ID is echoed; it is not a deduplication sequence counter.
Quotes and resets have no response. Invalid commands have no response.

For the response, payload offset 0 is `0x83`, offsets 1..2 are request ID,
offset 3 is flags, offsets 4..7 are bid, and offsets 8..11 are ask. Flags
bit 0 is bid observed, bit 1 is ask observed, and bits 7..2 are zero. A price
whose flag is clear is serialized as zero. The response uses the same
framing and CRC as a request and occupies 15 UART bytes.

## State, ordering, and reset

The state is `(bid_valid, bid, ask_valid, ask)`. On a valid bid, set its flag
and update bid if its flag was clear or `price > bid`. On a valid ask, set
its flag and update ask if its flag was clear or `price < ask`. Equal or
worse prices preserve the stored extreme. Updating one side preserves the
other side, including its flag. A malformed command preserves all four
state fields. A read also preserves all four.

Commands take effect in received order at the completed-payload handshake.
If FrameLatch accepts a good CRC on edge N, its output becomes valid after
edge N and the core consumes it on edge N+1. Quote state or a read snapshot
is observable after edge N+1. There is no additional candidate pipeline.
Only one complete command may be consumed per clock edge.

An accepted read captures both prices and flags atomically at its handshake
edge. Subsequent quotes or serial resets cannot alter that snapshot. The
serializer holds its snapshot stable until the final response stop bit has
finished. Receipt of the first response byte does not reopen the slot.

There is one response slot. At most one read may be outstanding. While it
is busy, a further correctly framed read is rejected without response and
increments `busy_reads`. Quotes and resets continue to be accepted. If a
response finishes on the same edge as another read handshake, the read is
treated as busy using the pre-edge slot state. The host should wait for the
complete response before issuing its next read. Back-to-back quote frames
remain supported during transmission; the receive path never stalls for TX.

Hardware reset is synchronous active high inside the design, and has
priority over every handshake and timeout. It clears quote values/flags,
parser assembly and completed output, response slot, UART state, timeout,
and all diagnostic counters. It may truncate a response in flight. After
hardware reset the host discards any partial response and allows an idle
gap before starting a new request. Board startup invokes the same reset.

The serial reset command clears only the four quote state fields. It does
not reset UART reception, abort the next frame, clear counters, or cancel
an earlier read response. There is no simultaneous quote/read action for
that command. Hardware reset still wins if asserted on its handshake edge.
Following a serial reset with a read provides a reset acknowledgment through
zero flags and values, subject to the one-outstanding-read rule.

## Diagnostics

All counters are unsigned 32-bit, saturate at `0xFFFFFFFF`, and clear only
on hardware reset. They are internal verification/debug signals, not fields
of the version-1 readback response. Each event can increment its own counter
once per edge; simultaneous different events may increment different counters.

| Counter | Increment event |
| --- | --- |
| `valid_frames` | FrameLatch publishes a payload after matching CRC, including unsupported commands |
| `crc_errors` | FrameLatch consumes a mismatching CRC |
| `invalid_lengths` | FrameLatch consumes length zero or greater than 16 |
| `incomplete_frames` | FrameLatch receives abort while a partial frame exists |
| `discarded_bytes` | FrameLatch accepts a non-marker byte in marker search |
| `semantic_errors` | Complete CRC-valid payload has unsupported type or wrong command length |
| `busy_reads` | Complete, correctly sized read arrives while the response slot is busy |
| `uart_errors` | RX rejects a byte because its stop-bit sample is low |

A busy read is not a semantic error. No-op quotes are valid frames, and
serial reset is a valid frame. CRC-invalid data does not reach the semantic
decoder. UART framing errors are not CRC errors; if they interrupt assembly
they also cause one incomplete-frame event. FrameLatch abort leaves a
previously completed output intact; that earlier valid command may still
be consumed. Reset edges produce no counted event.

## Examples

The final byte of every row is CRC. Request ID `0x1234` is sent as `34 12`.
These examples were cross-checked using polynomial division and a separate
bytewise CRC calculation; they are intended as fixed regression vectors.

| Message | Complete frame, hexadecimal bytes |
| --- | --- |
| Bid zero | `A5 05 01 00 00 00 00 EF` |
| Ask maximum | `A5 05 02 FF FF FF FF 97` |
| Bid 100 | `A5 05 01 64 00 00 00 E2` |
| Ask 90 | `A5 05 02 5A 00 00 00 29` |
| Read `0x1234` | `A5 03 03 34 12 54` |
| Serial reset | `A5 01 04 09` |
| Empty snapshot `0x1234` | `A5 0C 83 34 12 00 00 00 00 00 00 00 00 00 6F` |
| Both valid, bid 100, ask 90 | `A5 0C 83 34 12 03 64 00 00 00 5A 00 00 00 7A` |
