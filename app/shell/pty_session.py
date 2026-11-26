import asyncio, errno, fcntl, os, secrets, shutil, signal, struct, subprocess, termios, time
from pathlib import Path
from typing import Callable

from app.shell.handoff import HandoffDetector
from app.shell.markers import ContinuationEvent, OutputEvent, ReadyEvent, StreamMarkerParser


class PersistentBashSession:
    STARTUP_BUFFER_SEC = 0.10

    def __init__(
        self,
        shell_path: str = "/bin/bash",
        max_single_line_bytes: int = 4096,
        on_output: Callable[[str], None] | None = None,
        on_ready: Callable[[int, str, str, float], None] | None = None,
        on_continuation: Callable[[], None] | None = None,
        on_exit: Callable[[int | None], None] | None = None,
        on_handoff_requested: Callable[[str, bytes], None] | None = None,
    ) -> None:
        self.shell_path = shell_path
        self.max_single_line_bytes = max_single_line_bytes
        self.on_output = on_output
        self.on_ready = on_ready
        self.on_continuation = on_continuation
        self.on_exit = on_exit
        self.on_handoff_requested = on_handoff_requested

        self.nonce = secrets.token_hex(16)
        self.parser = StreamMarkerParser(self.nonce)
        self.master_fd: int | None = None
        self.proc: subprocess.Popen[bytes] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._closed = False
        self._reader_attached = False

        self.bash_pgrp: int | None = None
        self.cwd: str = os.getcwd()
        self.last_exit_code: int = 0
        self.venv: str = ""
        self.is_ready: bool = False
        self.in_continuation: bool = False
        self.command_running: bool = False
        self._cmd_start_time: float | None = None

        self._buffering_startup: bool = False
        self._startup_buffer = bytearray()
        self._startup_timer: asyncio.TimerHandle | None = None
        self._handoff_in_progress: bool = False

    @property
    def pid(self) -> int | None:
        return self.proc.pid if self.proc else None

    def start(self, rows: int = 18, cols: int = 106) -> None:
        if self.proc is not None:
            return
        master_fd, slave_fd = os.openpty()
        try:
            attrs = termios.tcgetattr(slave_fd)
            attrs[3] &= ~termios.ECHO
            attrs[3] |= termios.ISIG | termios.ICANON
            termios.tcsetattr(slave_fd, termios.TCSANOW, attrs)
            fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, struct.pack("HHHH", max(1, rows), max(1, cols), 0, 0))

            rcfile_path = Path(__file__).with_name("nihatos_bashrc").resolve()
            try:
                os.chmod(rcfile_path, 0o444)
            except OSError:
                pass

            child_env = os.environ.copy()
            child_env["NIHATOS_NONCE"] = self.nonce
            child_env["NIHATOS_USER_BASHRC"] = str(Path.home() / ".bashrc")
            child_env["NIHATOS_TERMINAL"] = "1"
            child_env.setdefault("TERM", "xterm-256color")

            setsid_bin = shutil.which("setsid")
            if setsid_bin:
                cmd = [setsid_bin, "--ctty", self.shell_path, "--noediting", "--rcfile", str(rcfile_path), "-i"]
                preexec = None
            else:
                cmd = [self.shell_path, "--noediting", "--rcfile", str(rcfile_path), "-i"]
                preexec = os.setsid

            self.proc = subprocess.Popen(
                cmd, stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
                close_fds=True, env=child_env, preexec_fn=preexec,
            )
        finally:
            os.close(slave_fd)

        os.set_blocking(master_fd, False)
        self.master_fd = master_fd
        try:
            self._loop = asyncio.get_running_loop()
            self.resume_async_reader()
        except RuntimeError:
            self._loop = None

    def pause_async_reader(self) -> None:
        self._cancel_startup_timer()
        if self._loop and self.master_fd is not None and self._reader_attached:
            try:
                self._loop.remove_reader(self.master_fd)
            except Exception:
                pass
            self._reader_attached = False

    def resume_async_reader(self) -> None:
        if self._loop and self.master_fd is not None and not self._closed and not self._reader_attached:
            self._loop.add_reader(self.master_fd, self._on_readable)
            self._reader_attached = True

    def has_foreground_job(self) -> bool:
        if self.master_fd is None or self._closed or self.bash_pgrp is None:
            return False
        try:
            return os.tcgetpgrp(self.master_fd) != self.bash_pgrp
        except OSError:
            return False

    def is_pty_raw_mode(self) -> bool:
        return False if (self.master_fd is None or self._closed) else HandoffDetector.is_pty_raw_mode(self.master_fd)

    def restore_nihatos_termios(self) -> None:
        if self.master_fd is None or self._closed:
            return
        try:
            attrs = termios.tcgetattr(self.master_fd)
            attrs[3] &= ~termios.ECHO
            attrs[3] |= termios.ISIG | termios.ICANON
            termios.tcsetattr(self.master_fd, termios.TCSANOW, attrs)
        except OSError:
            pass

    def poll_for_handoff(self) -> None:
        if (
            not self.command_running or self._handoff_in_progress
            or self.on_handoff_requested is None or self.master_fd is None or self._closed
        ):
            return
        if self.has_foreground_job() and self.is_pty_raw_mode():
            self._trigger_handoff("kernel:raw-mode")

    def _cancel_startup_timer(self) -> None:
        if self._startup_timer is not None:
            self._startup_timer.cancel()
            self._startup_timer = None

    def _flush_startup_buffer(self) -> None:
        self._cancel_startup_timer()
        if not self._buffering_startup:
            return
        self._buffering_startup = False
        if self._startup_buffer:
            buffered = bytes(self._startup_buffer)
            self._startup_buffer.clear()
            self._process_bytes(buffered)

    def _trigger_handoff(self, reason: str) -> None:
        if self._handoff_in_progress or self.on_handoff_requested is None:
            return
        self._handoff_in_progress = True
        self._cancel_startup_timer()
        self._buffering_startup = False
        buffered = bytes(self._startup_buffer)
        self._startup_buffer.clear()
        try:
            self.on_handoff_requested(reason, buffered)
        finally:
            self._handoff_in_progress = False

    def _on_readable(self) -> None:
        if self.master_fd is None or self._closed or self._handoff_in_progress:
            return
        try:
            data = os.read(self.master_fd, 4096)
        except BlockingIOError:
            return
        except OSError as exc:
            if exc.errno == errno.EIO:
                self._handle_eof()
                return
            raise
        if not data:
            self._handle_eof()
            return

        if self.command_running and self.on_handoff_requested is not None:
            if HandoffDetector.has_alt_screen_entry(data):
                self._startup_buffer.extend(data)
                self._trigger_handoff("stream:alt-screen")
                return
            if self.has_foreground_job() and self.is_pty_raw_mode():
                self._startup_buffer.extend(data)
                self._trigger_handoff("kernel:raw-mode")
                return
            if self.has_foreground_job() and HandoffDetector.looks_like_password_prompt(data):
                self._startup_buffer.extend(data)
                self._trigger_handoff("stream:password-prompt")
                return
            if self._buffering_startup:
                self._startup_buffer.extend(data)
                if b"\x1b]7777;" in self._startup_buffer:
                    self._flush_startup_buffer()
                return

        self._process_bytes(data)

    def _process_bytes(self, data: bytes) -> None:
        for event in self.parser.feed(data):
            if isinstance(event, OutputEvent):
                if self.on_output:
                    self.on_output(event.text)
            elif isinstance(event, ReadyEvent):
                duration = 0.0
                if self._cmd_start_time is not None:
                    duration = max(0.0, time.monotonic() - self._cmd_start_time)
                    self._cmd_start_time = None
                self.last_exit_code, self.cwd, self.venv = event.exit_code, event.cwd, event.venv
                self.is_ready, self.in_continuation, self.command_running = True, False, False
                if self.bash_pgrp is None and self.master_fd is not None:
                    try:
                        self.bash_pgrp = os.tcgetpgrp(self.master_fd)
                    except OSError:
                        pass
                if self.on_ready:
                    self.on_ready(event.exit_code, event.cwd, event.venv, duration)
            elif isinstance(event, ContinuationEvent):
                self.in_continuation, self.command_running = True, False
                if self.on_continuation:
                    self.on_continuation()

    def apply_handoff_ready(self, exit_code: int, cwd: str, venv: str, duration: float) -> None:
        self.last_exit_code, self.cwd, self.venv = exit_code, cwd, venv
        self.is_ready, self.in_continuation, self.command_running = True, False, False
        self._cmd_start_time = None
        if self.on_ready:
            self.on_ready(exit_code, cwd, venv, duration)

    def _handle_eof(self) -> None:
        if self._closed:
            return
        self._flush_startup_buffer()
        self._process_bytes(b"")
        code = self.proc.poll() if self.proc else None
        self.close()
        if self.on_exit:
            self.on_exit(code)

    def validate_command(self, text: str) -> tuple[bool, str | None]:
        if self.master_fd is None or self._closed:
            return False, "Shell session is not active."
        for line in text.split("\n"):
            if len(line.encode("utf-8")) > self.max_single_line_bytes:
                return False, f"Single line exceeds {self.max_single_line_bytes}-byte canonical TTY limit."
        return True, None

    def send_command(self, text: str) -> tuple[bool, str | None]:
        ok, err = self.validate_command(text)
        if not ok or self.master_fd is None:
            return False, err
        if self._cmd_start_time is None:
            self._cmd_start_time = time.monotonic()
        self.command_running = True
        if self.on_handoff_requested is not None and self._loop is not None:
            self._buffering_startup = True
            self._startup_buffer.clear()
            self._cancel_startup_timer()
            self._startup_timer = self._loop.call_later(self.STARTUP_BUFFER_SEC, self._flush_startup_buffer)
        payload = text if text.endswith("\n") else f"{text}\n"
        os.write(self.master_fd, payload.encode("utf-8"))
        return True, None

    def send_interrupt(self) -> None:
        if self.master_fd is None or self._closed:
            return
        self._flush_startup_buffer()
        try:
            os.killpg(os.tcgetpgrp(self.master_fd), signal.SIGINT)
        except OSError:
            if self.proc and self.proc.poll() is None:
                try:
                    os.killpg(self.proc.pid, signal.SIGINT)
                except OSError:
                    pass

    def resize(self, rows: int, cols: int) -> None:
        if self.master_fd is None or self._closed:
            return
        try:
            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, struct.pack("HHHH", max(1, rows), max(1, cols), 0, 0))
            os.killpg(os.tcgetpgrp(self.master_fd), signal.SIGWINCH)
        except OSError:
            pass

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._cancel_startup_timer()
        self.pause_async_reader()
        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = None
        if self.proc is not None:
            if self.proc.poll() is None:
                try:
                    os.killpg(self.proc.pid, signal.SIGHUP)
                except OSError:
                    try:
                        self.proc.terminate()
                    except OSError:
                        pass
                try:
                    self.proc.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(self.proc.pid, signal.SIGKILL)
                    except OSError:
                        self.proc.kill()
                    self.proc.wait(timeout=1.0)
            else:
                self.proc.wait()
