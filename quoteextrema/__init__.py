"""QuoteExtrema protocol and independent state model."""

from .model import DeviceModel, QuoteState
from .protocol import Snapshot, ask, bid, decode_snapshot, frame, read, reset

__all__ = ["DeviceModel", "QuoteState", "Snapshot", "ask", "bid",
           "decode_snapshot", "frame", "read", "reset"]
