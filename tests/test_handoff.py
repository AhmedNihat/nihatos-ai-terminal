import asyncio
import os
import threading
import time

from app.shell.handoff import (
    HandoffDetector,
    HandoffResult,
    PanicChordTracker,
    run_handoff_pump,
)
from app.shell.pty_session import PersistentBashSession


async def _wait_until(predicate, timeout: float = 4.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not predicate():
        if loop.time() >= deadline:
            raise TimeoutError("Condition timed out")
        await asyncio.sleep(0.02)


def test_layer2_advisory_hints() -> None:
    det = HandoffDetector()

    for cmd in (
        "vim test.py",
        "nano ~/.bashrc",
        "less /etc/os-release",
        "htop",
        "top",
        "ssh user@server",
        "sudo dnf check-update",
        "man ls",
        "python3",
        "python3 -i script.py",
        "git rebase -i HEAD~3",
        "git add -p",
        "git commit",
        "EDITOR=nano vim file.txt",
    ):
        ok, reason = det.should_handoff_command(cmd)
        assert ok is True, f"Expected handoff hint for: {cmd}"
        assert reason.startswith("hint:")

    for cmd in (
        "ls -la",
        "echo hello",
        "python3 -c 'print(123)'",
        "python3 script.py",
        "git status",
        "git commit -m 'phase 2b'",
        "cat file.txt",
    ):
        ok, _ = det.should_handoff_command(cmd)
        assert ok is False, f"Did not expect handoff hint for: {cmd}"


def test_layer4_panic_chord_tracker() -> None:
    tracker = PanicChordTracker(count=3, window_sec=1.5)

    # 2 presses -> not triggered
    trig, fwd = tracker.feed(b"\x1d\x1d", now=10.0)
    assert trig is False and fwd == b""

    # Interrupted by normal key -> resets count
    trig, fwd = tracker.feed(b"a\x1d\x1d", now=10.2)
    assert trig is False and fwd == b"a"

    # 3rd press within window -> triggers panic detach
    trig, fwd = tracker.feed(b"\x1d", now=10.5)
    assert trig is True and fwd == b""

    # Window expiration resets cleanly
    tracker.feed(b"\x1d\x1d", now=20.0)
    trig, _ = tracker.feed(b"\x1d", now=22.5)
    assert trig is False


def test_layer1_detects_raw_mode_and_handoff_pump_roundtrip() -> None:
    """Real PTY integration test: child enters raw mode, pump handles keystroke, returns cleanly on READY."""
    async def _run() -> None:
        ready_count = 0
        handoff_triggered: list[tuple[str, bytes]] = []

        def on_ready(code: int, cwd: str, venv: str, dur: float) -> None:
            nonlocal ready_count
            ready_count += 1

        def on_handoff(reason: str, buf: bytes) -> None:
            handoff_triggered.append((reason, buf))

        session = PersistentBashSession(
            on_ready=on_ready,
            on_handoff_requested=on_handoff,
        )
        try:
            session.start(rows=18, cols=106)
            await _wait_until(lambda: ready_count >= 1)
            assert session.bash_pgrp is not None

            # Launch a tiny Python program that puts the PTY into raw mode and waits for 'q'
            py_raw_prog = (
                "python3 -c 'import sys,tty,termios;"
                "fd=sys.stdin.fileno(); old=termios.tcgetattr(fd);"
                "tty.setraw(fd); sys.stdout.write(\"RAW_READY\\r\\n\"); sys.stdout.flush();"
                "ch=sys.stdin.read(1); termios.tcsetattr(fd,termios.TCSADRAIN,old);"
                "print(\"GOT:\" + ch)'"
            )
            session.send_command(py_raw_prog)

            # Layer 1 must detect raw mode automatically (not in Layer 2 hints!)
            await _wait_until(lambda: len(handoff_triggered) == 1, timeout=3.0)
            reason, initial_buf = handoff_triggered[0]
            assert reason in ("kernel:raw-mode", "stream:alt-screen")

            # Run real handoff pump over a simulated host PTY pair
            host_master, host_slave = os.openpty()
            session.pause_async_reader()
            result_box: list[HandoffResult] = []

            def _pump_thread() -> None:
                res = run_handoff_pump(
                    master_fd=session.master_fd,
                    nonce=session.nonce,
                    stdin_fd=host_slave,
                    stdout_fd=host_slave,
                    initial_buffer=initial_buf,
                    size_provider=lambda: (28, 110),
                    install_sigwinch=False,
                )
                result_box.append(res)

            t = threading.Thread(target=_pump_thread, daemon=True)
            t.start()

            # Simulate user typing 'q' into the interactive program
            time.sleep(0.1)
            os.write(host_master, b"q")
            t.join(timeout=4.0)
            assert not t.is_alive(), "Handoff pump did not return after program exited"

            os.close(host_slave)
            os.close(host_master)

            session.restore_nihatos_termios()
            session.resume_async_reader()

            assert len(result_box) == 1
            res = result_box[0]
            assert res.detached_by_panic is False
            assert res.exit_code == 0
            assert "GOT:q" in res.captured_output

            # Verify PTY returned to canonical + no-echo mode and shell still works
            assert session.is_pty_raw_mode() is False
            session.apply_handoff_ready(res.exit_code, res.cwd or session.cwd, res.venv or "", res.duration)
            assert ready_count >= 2
        finally:
            session.close()

    asyncio.run(_run())


def test_handoff_pump_panic_chord_detaches_cleanly() -> None:
    """Verify Ctrl+] x3 detaches from a hanging interactive program without killing the shell."""
    async def _run() -> None:
        ready_count = 0

        def on_ready(code: int, cwd: str, venv: str, dur: float) -> None:
            nonlocal ready_count
            ready_count += 1

        session = PersistentBashSession(on_ready=on_ready)
        try:
            session.start(rows=18, cols=106)
            await _wait_until(lambda: ready_count >= 1)

            host_master, host_slave = os.openpty()
            session.pause_async_reader()
            result_box: list[HandoffResult] = []

            def _pump_thread() -> None:
                res = run_handoff_pump(
                    master_fd=session.master_fd,
                    nonce=session.nonce,
                    stdin_fd=host_slave,
                    stdout_fd=host_slave,
                    pre_send_command=b"sleep 30\n",
                    size_provider=lambda: (28, 110),
                    install_sigwinch=False,
                )
                result_box.append(res)

            t = threading.Thread(target=_pump_thread, daemon=True)
            t.start()

            time.sleep(0.15)
            # Send Ctrl+] three times -> must detach immediately
            os.write(host_master, b"\x1d\x1d\x1d")
            t.join(timeout=3.0)
            assert not t.is_alive(), "Panic chord failed to detach handoff pump"

            os.close(host_slave)
            os.close(host_master)

            assert len(result_box) == 1
            assert result_box[0].detached_by_panic is True

            # Clean up the still-running sleep via Ctrl+C and verify shell recovers
            session.restore_nihatos_termios()
            session.resume_async_reader()
            session.send_interrupt()
            await _wait_until(lambda: ready_count >= 2, timeout=3.0)
            assert session.last_exit_code == 130
        finally:
            session.close()

    asyncio.run(_run())
