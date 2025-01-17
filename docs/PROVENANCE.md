# FrameLatch reuse

Upstream is the owner's [jacobp112/framelatch](https://github.com/jacobp112/framelatch).
The selected revision is `8d2ce380478418aeb4fc07ed3407d590143f3cdd`.
Reuse was explicitly requested for QuoteExtrema. The receiver was copied
unchanged into `rtl/framelatch.sv` at the RTL checkpoint; it was not present
at the earlier planning checkpoint. Its copied raw SHA-256 matches the
local inspected bytes recorded below.

The inspected upstream tree contains `rtl/framelatch.sv`,
`docs/PROTOCOL.md`, `framelatch/protocol.py`, and reference tests. It has
no LICENSE file. Record owner-provided reuse as the provenance; do not
invent an upstream license or add a third-party license attribution.

The local FrameLatch RTL was compared with the selected revision and
matched after CRLF/LF normalization. Its local raw-file SHA-256 was
`7fdec51b156539a5c4d37f631f74af48ba9f7575b86261269d1ea667cfaeb611`.
That hash also describes the copied file's raw bytes; a normalized LF copy
may have a different raw hash.

The initial import leaves the RTL unchanged. Preserve its payload byte ordering,
ready/valid timing, abort behaviour, and five saturating counters. Implement
UART-specific timeout and errors in the wrapper rather than changing the
receiver contract. Any later receiver change needs a documented reason
and must replay the receiver's directed and randomized verification.

The QuoteExtrema model must implement semantic state independently. Its
CRC oracle should use whole-message polynomial division, distinct from
the RTL bytewise shift-register CRC. Simulation must compare per-event
state and readback bytes, not merely a final accumulated result.

The owner's icebbo protocol was also inspected. It uses a fixed seven-byte
frame, big-endian prices, and different CRC coverage. QuoteExtrema adopts
FrameLatch framing and little-endian payloads as specified in
[PROTOCOL.md](PROTOCOL.md); its host script must not send icebbo frames.
