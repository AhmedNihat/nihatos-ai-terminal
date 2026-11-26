import asyncio
import os

from app.shell.pty_session import PersistentBashSession


async def _wait_until(predicate, timeout: float = 4.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not predicate():
        if loop.time() >= deadline:
            raise TimeoutError("Condition timed out")
        await asyncio.sleep(0.02)


def test_ctrl_c_interrupts_foreground_job_and_keeps_shell_alive() -> None:
    async def _run() -> None:
        chunks: list[str] = []
        ready_count = 0

        def on_ready(code: int, cwd: str, venv: str, dur: float) -> None:
            nonlocal ready_count
            ready_count += 1

        session = PersistentBashSession(
            on_output=chunks.append,
            on_ready=on_ready,
        )
        try:
            session.start(rows=11, cols=110)
            await _wait_until(lambda: ready_count >= 1)

            session.send_command("sleep 30")
            await asyncio.sleep(0.2)
            session.send_interrupt()

            await _wait_until(lambda: ready_count >= 2, timeout=2.5)
            assert session.last_exit_code == 130

            # Verify persistent shell still executes subsequent commands
            chunks.clear()
            session.send_command("echo STILL_ALIVE")
            await _wait_until(lambda: ready_count >= 3)
            assert "".join(chunks).strip() == "STILL_ALIVE"
        finally:
            session.close()

    asyncio.run(_run())


def test_resize_propagates_tiocswinsz() -> None:
    async def _run() -> None:
        chunks: list[str] = []
        ready_count = 0

        def on_ready(code: int, cwd: str, venv: str, dur: float) -> None:
            nonlocal ready_count
            ready_count += 1

        session = PersistentBashSession(
            on_output=chunks.append,
            on_ready=on_ready,
        )
        try:
            session.start(rows=11, cols=110)
            await _wait_until(lambda: ready_count >= 1)

            chunks.clear()
            session.send_command("stty size")
            await _wait_until(lambda: ready_count >= 2)
            assert "".join(chunks).strip() == "11 110"

            session.resize(rows=19, cols=132)
            chunks.clear()
            session.send_command("stty size")
            await _wait_until(lambda: ready_count >= 3)
            assert "".join(chunks).strip() == "19 132"
        finally:
            session.close()

    asyncio.run(_run())


def test_clean_exit_reaps_child_process() -> None:
    async def _run() -> None:
        ready_count = 0

        def on_ready(code: int, cwd: str, venv: str, dur: float) -> None:
            nonlocal ready_count
            ready_count += 1

        session = PersistentBashSession(on_ready=on_ready)
        session.start(rows=11, cols=110)
        await _wait_until(lambda: ready_count >= 1)

        pid = session.pid
        assert pid is not None
        session.close()

        # Process must be terminated and reaped (no zombies)
        try:
            os.kill(pid, 0)
            alive = True
        except ProcessLookupError:
            alive = False
        assert alive is False

    asyncio.run(_run())