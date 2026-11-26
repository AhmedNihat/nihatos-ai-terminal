import asyncio
import os
from pathlib import Path
import tempfile

from app.shell.pty_session import PersistentBashSession


async def _wait_until(predicate, timeout: float = 4.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not predicate():
        if loop.time() >= deadline:
            raise TimeoutError("Condition timed out")
        await asyncio.sleep(0.02)


def test_startup_no_readline_escapes_and_no_echo() -> None:
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

            startup_text = "".join(chunks)
            # Bracketed paste escape emitted by active Readline must not appear
            assert "\x1b[?2004h" not in startup_text

            chunks.clear()
            ok, err = session.send_command("echo NIHATOS_NO_ECHO_CHECK")
            assert ok and err is None
            await _wait_until(lambda: ready_count >= 2)

            out = "".join(chunks)
            lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
            # Output must contain only the result, NOT the echoed command string
            assert lines == ["NIHATOS_NO_ECHO_CHECK"]
        finally:
            session.close()

    asyncio.run(_run())


def test_persistent_bash_state_and_bangla_unicode() -> None:
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

            with tempfile.TemporaryDirectory() as tmpdir:
                real_tmp = os.path.realpath(tmpdir)

                # 1. Directory persistence
                session.send_command(f"cd '{real_tmp}'")
                await _wait_until(lambda: ready_count >= 2)

                chunks.clear()
                session.send_command("pwd")
                await _wait_until(lambda: ready_count >= 3)
                assert os.path.realpath("".join(chunks).strip()) == real_tmp
                assert os.path.realpath(session.cwd) == real_tmp

                # 2. Exported environment variable persistence
                session.send_command("export NIHATOS_ENV_CHECK='fedora45_ok'")
                await _wait_until(lambda: ready_count >= 4)

                chunks.clear()
                session.send_command('echo "$NIHATOS_ENV_CHECK"')
                await _wait_until(lambda: ready_count >= 5)
                assert "".join(chunks).strip() == "fedora45_ok"

                # 3. Alias & Shell Function persistence
                session.send_command("alias nihat_alias='echo ALIAS_WORKS'")
                await _wait_until(lambda: ready_count >= 6)

                chunks.clear()
                session.send_command("nihat_alias")
                await _wait_until(lambda: ready_count >= 7)
                assert "".join(chunks).strip() == "ALIAS_WORKS"

                session.send_command('nihat_fn() { echo "FN:$1"; }')
                await _wait_until(lambda: ready_count >= 8)

                chunks.clear()
                session.send_command("nihat_fn active")
                await _wait_until(lambda: ready_count >= 9)
                assert "".join(chunks).strip() == "FN:active"

                # 4. Bangla UTF-8 Unicode handling
                chunks.clear()
                session.send_command('echo "নিহাত ওএস টার্মিনাল"')
                await _wait_until(lambda: ready_count >= 10)
                assert "".join(chunks).strip() == "নিহাত ওএস টার্মিনাল"
        finally:
            session.close()

    asyncio.run(_run())


def test_multiline_continuation_and_spoofed_marker() -> None:
    async def _run() -> None:
        chunks: list[str] = []
        ready_count = 0
        cont_count = 0

        def on_ready(code: int, cwd: str, venv: str, dur: float) -> None:
            nonlocal ready_count
            ready_count += 1

        def on_cont() -> None:
            nonlocal cont_count
            cont_count += 1

        session = PersistentBashSession(
            on_output=chunks.append,
            on_ready=on_ready,
            on_continuation=on_cont,
        )
        try:
            session.start(rows=11, cols=110)
            await _wait_until(lambda: ready_count >= 1)

            # Incomplete `if` triggers PS2 continuation marker
            session.send_command("if true; then")
            await _wait_until(lambda: cont_count >= 1)
            assert session.in_continuation is True

            chunks.clear()
            session.send_command("echo MULTILINE_OK; fi")
            await _wait_until(lambda: ready_count >= 2)
            assert session.in_continuation is False
            assert "".join(chunks).strip() == "MULTILINE_OK"

            # Attempt to spoof READY marker with wrong nonce
            real_cwd = session.cwd
            session.send_command(
                r"printf '\033]7777;READY;bad_nonce;99;/spoofed/path;fakevenv\007'"
            )
            await _wait_until(lambda: ready_count >= 3)
            assert session.cwd == real_cwd
            assert session.last_exit_code == 0
        finally:
            session.close()

    asyncio.run(_run())