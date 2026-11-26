from dataclasses import dataclass
import errno
import fcntl
import os
import re
import select
import shlex
import signal
import struct
import termios
import time
import tty
from typing import Callable

ALT_SCREEN_SEQUENCES = (b"\x1b[?1049h", b"\x1b[?1047h", b"\x1b[?47h")
PASSWORD_PROMPT_RE = re.compile(
    rb"(?:\[sudo\]\s*password\b|password\s*(?:for\s+[^:]+)?:\s*$|passphrase\s+for\s+[^:]+:\s*$)",
    re.IGNORECASE,
)

DEFAULT_INTERACTIVE_COMMANDS: frozenset[str] = frozenset(
    {
        "vim", "nvim", "vi", "view", "vimdiff", "nano", "micro", "emacs",
        "less", "more", "man", "htop", "top", "btop", "atop", "iotop",
        "ssh", "sftp", "sudo", "su", "doas", "passwd", "tmux", "screen",
        "ipython", "ipython3", "bpython", "gdb", "mc", "ranger", "lf", "fzf",
        "nmtui", "alsamixer", "watch", "tig", "lazygit", "sqlite3", "psql", "mysql",
    }
)


@dataclass(frozen=True)
class HandoffResult:
    exit_code: int | None
    cwd: str | None
    venv: str | None
    duration: float
    detached_by_panic: bool
    used_alt_screen: bool
    captured_output: str
    eof: bool


class HandoffDetector:
    """Layer 1 (kernel/stream signals) and Layer 2 (advisory command hints) detector."""

    def __init__(
        self, interactive_commands: frozenset[str] = DEFAULT_INTERACTIVE_COMMANDS
    ) -> None:
        self.interactive_commands = interactive_commands

    def should_handoff_command(self, command: str) -> tuple[bool, str]:
        stripped = command.strip()
        if not stripped or "\n" in stripped:
            return False, ""
        try:
            tokens = shlex.split(stripped)
        except ValueError:
            tokens = stripped.split()

        idx = 0
        while idx < len(tokens) and "=" in tokens[idx] and not tokens[idx].startswith("-"):
            idx += 1
        if idx >= len(tokens):
            return False, ""

        base = os.path.basename(tokens[idx])
        args = tokens[idx + 1 :]

        if base in self.interactive_commands:
            return True, f"hint:{base}"

        if base in ("python", "python3"):
            if "-i" in args:
                return True, f"hint:{base} -i"
            if not args:
                return True, f"hint:{base}-repl"

        if base == "git" and args:
            sub, rest = args[0], args[1:]
            if sub == "rebase" and any(a in ("-i", "--interactive") for a in rest):
                return True, "hint:git-rebase-i"
            if sub == "add" and any(a in ("-p", "--patch", "-i", "--interactive") for a in rest):
                return True, "hint:git-add-p"
            if sub == "commit" and not any(
                a in ("-m", "--message", "-F", "--file", "--no-edit") or a.startswith("-m")
                for a in rest
            ):
                return True, "hint:git-commit-editor"

        return False, ""

    @staticmethod
    def is_pty_raw_mode(master_fd: int) -> bool:
        try:
            return not bool(termios.tcgetattr(master_fd)[3] & termios.ICANON)
        except OSError:
            return False

    @staticmethod
    def has_alt_screen_entry(data: bytes) -> bool:
        return any(seq in data for seq in ALT_SCREEN_SEQUENCES)

    @staticmethod
    def looks_like_password_prompt(data: bytes) -> bool:
        return bool(PASSWORD_PROMPT_RE.search(data[-256:]))


class PanicChordTracker:
    """Layer 4 escape hatch: detect Ctrl+] (0x1d) pressed 3 times within window_sec."""

    PANIC_BYTE = 0x1D

    def __init__(self, count: int = 3, window_sec: float = 1.5) -> None:
        self.count = count
        self.window_sec = window_sec
        self._timestamps: list[float] = []

    def feed(self, data: bytes, now: float | None = None) -> tuple[bool, bytes]:
        ts = time.monotonic() if now is None else now
        out = bytearray()
        for b in data:
            if b == self.PANIC_BYTE:
                self._timestamps = [
                    t for t in self._timestamps if (ts - t) <= self.window_sec
                ]
                self._timestamps.append(ts)
                if len(self._timestamps) >= self.count:
                    self._timestamps.clear()
                    return True, bytes(out)
            else:
                self._timestamps.clear()
                out.append(b)
        return False, bytes(out)


class _HandoffMarkerScanner:
    PREFIX = b"\x1b]7777;"

    def __init__(self, nonce: str) -> None:
        self.nonce_bytes = nonce.encode("utf-8")
        self._buf = bytearray()

    def feed(self, chunk: bytes) -> tuple[bytes, tuple[int, str, str] | None]:
        if not chunk:
            return b"", None
        self._buf.extend(chunk)
        out = bytearray()
        ready_info: tuple[int, str, str] | None = None

        while self._buf:
            idx = self._buf.find(self.PREFIX)
            if idx == -1:
                keep = self._trailing_prefix_len(self._buf)
                if keep:
                    out.extend(self._buf[:-keep])
                    del self._buf[:-keep]
                else:
                    out.extend(self._buf)
                    self._buf.clear()
                break

            if idx > 0:
                out.extend(self._buf[:idx])
                del self._buf[:idx]

            bel = self._buf.find(b"\x07", len(self.PREFIX))
            st = self._buf.find(b"\x1b\\", len(self.PREFIX))
            term_idx, term_len = (-1, 0)
            if bel != -1 and (st == -1 or bel < st):
                term_idx, term_len = bel, 1
            elif st != -1:
                term_idx, term_len = st, 2

            if term_idx == -1:
                if len(self._buf) > 4096:
                    out.extend(self._buf)
                    self._buf.clear()
                break

            payload = bytes(self._buf[len(self.PREFIX) : term_idx])
            raw_seq = bytes(self._buf[: term_idx + term_len])
            del self._buf[: term_idx + term_len]

            parsed = self._parse_ready(payload)
            if parsed is not None:
                ready_info = parsed
                break
            out.extend(raw_seq)

        return bytes(out), ready_info

    def _parse_ready(self, payload: bytes) -> tuple[int, str, str] | None:
        parts = payload.split(b";")
        if len(parts) >= 5 and parts[0] == b"READY" and parts[1] == self.nonce_bytes:
            try:
                code = int(parts[2].decode("ascii"))
            except ValueError:
                code = 1
            cwd = parts[3].decode("utf-8", errors="replace")
            venv = b";".join(parts[4:]).decode("utf-8", errors="replace")
            return code, cwd, venv
        return None

    @classmethod
    def _trailing_prefix_len(cls, buf: bytearray) -> int:
        for length in range(min(len(buf), len(cls.PREFIX) - 1), 0, -1):
            if cls.PREFIX.startswith(bytes(buf[-length:])):
                return length
        return 0


def _write_all(fd: int, data: bytes) -> None:
    view, written = memoryview(data), 0
    while written < len(view):
        try:
            n = os.write(fd, view[written:])
            if n <= 0:
                break
            written += n
        except InterruptedError:
            continue
        except BlockingIOError:
            select.select([], [fd], [], 0.05)


def _set_pty_winsize(master_fd: int, rows: int, cols: int) -> None:
    try:
        fcntl.ioctl(
            master_fd,
            termios.TIOCSWINSZ,
            struct.pack("HHHH", max(1, rows), max(1, cols), 0, 0),
        )
        os.killpg(os.tcgetpgrp(master_fd), signal.SIGWINCH)
    except OSError:
        pass


def run_handoff_pump(
    master_fd: int,
    nonce: str,
    stdin_fd: int,
    stdout_fd: int,
    initial_buffer: bytes = b"",
    pre_send_command: bytes | None = None,
    size_provider: Callable[[], tuple[int, int]] | None = None,
    install_sigwinch: bool = True,
    max_capture_bytes: int = 65536,
) -> HandoffResult:
    start_time = time.monotonic()
    scanner = _HandoffMarkerScanner(nonce)
    panic = PanicChordTracker()
    used_alt_screen = False
    captured = bytearray()
    exit_code: int | None = None
    cwd: str | None = None
    venv: str | None = None
    detached_by_panic = False
    eof = False

    def _get_size() -> tuple[int, int]:
        if size_provider is not None:
            return size_provider()
        try:
            sz = os.get_terminal_size(stdout_fd)
            return sz.lines, sz.columns
        except OSError:
            return 28, 110

    saved_termios = None
    if os.isatty(stdin_fd):
        try:
            saved_termios = termios.tcgetattr(stdin_fd)
            tty.setraw(stdin_fd)
        except termios.error:
            saved_termios = None

    resize_pending = False
    prev_sigwinch = None

    def _on_sigwinch(signum, frame) -> None:
        nonlocal resize_pending
        resize_pending = True

    if install_sigwinch:
        try:
            prev_sigwinch = signal.signal(signal.SIGWINCH, _on_sigwinch)
        except (ValueError, OSError):
            prev_sigwinch = None

    try:
        rows, cols = _get_size()
        _set_pty_winsize(master_fd, rows, cols)

        if initial_buffer:
            if HandoffDetector.has_alt_screen_entry(initial_buffer):
                used_alt_screen = True
            forward, ready = scanner.feed(initial_buffer)
            if forward:
                _write_all(stdout_fd, forward)
                if not used_alt_screen and len(captured) < max_capture_bytes:
                    captured.extend(forward[: max_capture_bytes - len(captured)])
            if ready is not None:
                exit_code, cwd, venv = ready
                return HandoffResult(
                    exit_code=exit_code,
                    cwd=cwd,
                    venv=venv,
                    duration=max(0.0, time.monotonic() - start_time),
                    detached_by_panic=False,
                    used_alt_screen=used_alt_screen,
                    captured_output="" if used_alt_screen else captured.decode("utf-8", errors="replace"),
                    eof=False,
                )
            _set_pty_winsize(master_fd, rows, cols)

        if pre_send_command:
            _write_all(master_fd, pre_send_command)

        while True:
            if resize_pending:
                resize_pending = False
                _set_pty_winsize(master_fd, *_get_size())

            try:
                readable, _, _ = select.select([stdin_fd, master_fd], [], [], 0.05)
            except InterruptedError:
                continue

            if stdin_fd in readable:
                try:
                    user_bytes = os.read(stdin_fd, 4096)
                except OSError:
                    user_bytes = b""
                if not user_bytes:
                    eof = True
                    break
                triggered, to_send = panic.feed(user_bytes)
                if to_send:
                    _write_all(master_fd, to_send)
                if triggered:
                    detached_by_panic = True
                    break

            if master_fd in readable:
                try:
                    pty_bytes = os.read(master_fd, 4096)
                except BlockingIOError:
                    continue
                except OSError as exc:
                    if exc.errno == errno.EIO:
                        eof = True
                        break
                    raise
                if not pty_bytes:
                    eof = True
                    break
                if HandoffDetector.has_alt_screen_entry(pty_bytes):
                    used_alt_screen = True
                forward, ready = scanner.feed(pty_bytes)
                if forward:
                    _write_all(stdout_fd, forward)
                    if not used_alt_screen and len(captured) < max_capture_bytes:
                        captured.extend(forward[: max_capture_bytes - len(captured)])
                if ready is not None:
                    exit_code, cwd, venv = ready
                    break
    finally:
        if install_sigwinch and prev_sigwinch is not None:
            try:
                signal.signal(signal.SIGWINCH, prev_sigwinch)
            except (ValueError, OSError):
                pass
        if saved_termios is not None:
            try:
                termios.tcsetattr(stdin_fd, termios.TCSANOW, saved_termios)
            except termios.error:
                pass
        if detached_by_panic and used_alt_screen:
            try:
                _write_all(stdout_fd, b"\x1b[?1049l\x1b[?25h")
            except OSError:
                pass

    return HandoffResult(
        exit_code=exit_code,
        cwd=cwd,
        venv=venv,
        duration=max(0.0, time.monotonic() - start_time),
        detached_by_panic=detached_by_panic,
        used_alt_screen=used_alt_screen,
        captured_output="" if used_alt_screen else captured.decode("utf-8", errors="replace"),
        eof=eof,
    )