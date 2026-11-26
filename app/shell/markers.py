import codecs
from dataclasses import dataclass
from typing import Union

OSC_START = "\x1b]"
OSC_BEL = "\x07"
OSC_ST = "\x1b\\"
MAX_OSC_BUFFER = 8192


@dataclass(frozen=True)
class OutputEvent:
    text: str


@dataclass(frozen=True)
class ReadyEvent:
    exit_code: int
    cwd: str
    venv: str


@dataclass(frozen=True)
class ContinuationEvent:
    pass


StreamEvent = Union[OutputEvent, ReadyEvent, ContinuationEvent]


class StreamMarkerParser:
    """Stateful stream parser separating printable/SGR output from OSC markers and host metadata."""

    def __init__(self, nonce: str) -> None:
        self.nonce = nonce
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._buf = ""

    def feed(self, raw_bytes: bytes, final: bool = False) -> list[StreamEvent]:
        text = self._decoder.decode(raw_bytes, final=final)
        if not text and not final:
            return []

        self._buf += text
        events: list[StreamEvent] = []

        while True:
            idx = self._buf.find(OSC_START)
            if idx == -1:
                if not final and self._buf.endswith("\x1b"):
                    if len(self._buf) > 1:
                        events.append(OutputEvent(self._buf[:-1]))
                    self._buf = "\x1b"
                else:
                    if self._buf:
                        events.append(OutputEvent(self._buf))
                    self._buf = ""
                break

            if idx > 0:
                events.append(OutputEvent(self._buf[:idx]))
                self._buf = self._buf[idx:]

            bel_idx = self._buf.find(OSC_BEL, len(OSC_START))
            st_idx = self._buf.find(OSC_ST, len(OSC_START))

            term_idx = -1
            term_len = 0
            if bel_idx != -1 and (st_idx == -1 or bel_idx < st_idx):
                term_idx = bel_idx
                term_len = len(OSC_BEL)
            elif st_idx != -1:
                term_idx = st_idx
                term_len = len(OSC_ST)

            if term_idx == -1:
                if len(self._buf) > MAX_OSC_BUFFER:
                    events.append(OutputEvent(self._buf))
                    self._buf = ""
                break

            raw_seq = self._buf[: term_idx + term_len]
            payload = self._buf[len(OSC_START) : term_idx]
            self._buf = self._buf[term_idx + term_len :]

            if payload.startswith("7777;"):
                parsed = self._parse_nihatos_payload(payload[len("7777;") :])
                if parsed is not None:
                    events.append(parsed)
            elif payload.startswith("8;"):
                # Preserve OSC 8 clickable hyperlinks
                events.append(OutputEvent(raw_seq))
            else:
                # Consume host-terminal metadata OSCs (e.g., Fedora OSC 0 title, OSC 3008 systemd context)
                pass

        if final and self._buf:
            events.append(OutputEvent(self._buf))
            self._buf = ""

        return events

    def _parse_nihatos_payload(self, payload: str) -> StreamEvent | None:
        parts = payload.split(";")
        if len(parts) >= 2 and parts[0] == "CONT":
            if parts[1] == self.nonce:
                return ContinuationEvent()
            return None

        if len(parts) >= 5 and parts[0] == "READY":
            nonce = parts[1]
            if nonce != self.nonce:
                return None
            try:
                exit_code = int(parts[2])
            except ValueError:
                exit_code = 1
            cwd = parts[3]
            venv = ";".join(parts[4:])
            return ReadyEvent(exit_code=exit_code, cwd=cwd, venv=venv)

        return None
