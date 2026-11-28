import asyncio
import os
from pathlib import Path
from unittest.mock import patch
from textual.geometry import Size

from app.application import N1BroXApp
from app.config import N1BroXConfig
from app.integrations.gemini_ai import (
    GeminiClient,
    GeminiResponse,
    load_api_key,
    redact_secrets,
    save_api_key,
)
from app.shell.history import CommandHistory, is_sensitive_command
from app.ui.input_bar import InputBar


def test_openrouter_key_storage_permissions_and_redaction(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "")
    key_file = tmp_path / "openrouter_key"

    assert load_api_key(key_file)[0] is None
    save_api_key("sk-or-v1-testkey1234567890abcdef", key_file)
    assert (os.stat(key_file).st_mode & 0o777) == 0o600

    loaded, src = load_api_key(key_file)
    assert loaded == "sk-or-v1-testkey1234567890abcdef"
    assert str(key_file) in src

    assert is_sensitive_command("n1brox ai key sk-or-v1-secret1234567890") is True
    hist = CommandHistory(history_path=tmp_path / "hist.jsonl")
    assert hist.add("n1brox ai key sk-or-v1-secret1234567890") is False
    assert len(hist) == 0

    redacted = redact_secrets("export API_KEY=my_secret_val && echo sk-or-v1-abc1234567890")
    assert "my_secret_val" not in redacted
    assert "sk-or-v1-" not in redacted


def test_openrouter_client_missing_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "")
    client = GeminiClient(key_path=tmp_path / "missing_key")
    res = client.ask("how to list files?")
    assert res.ok is False
    assert "not set" in res.error


def test_n1brox_ai_commands_and_explain_in_app(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "")

    async def _run() -> None:
        key_file = tmp_path / "openrouter_key"
        cfg_file = tmp_path / "config.json"
        app = N1BroXApp(
            config=N1BroXConfig(),
            config_path=cfg_file,
            history_path=tmp_path / "hist.jsonl",
            ai_key_path=key_file,
        )
        async with app.run_test(size=(110, 28)) as pilot:
            await pilot.pause(0.25)
            input_bar = app.query_one("#input-bar", InputBar)

            input_bar.set_text("n1brox ai key sk-or-v1-dummykey9876543210")
            await pilot.press("enter")
            await pilot.pause(0.15)
            strips = app.screen._compositor.render_strips(Size(110, 28))
            rendered = "\n".join("".join(seg.text for seg in st) for st in strips)
            assert "sk-or-v1-dummykey9876543210" not in rendered
            assert "[REDACTED]" in rendered
            assert load_api_key(key_file)[0] == "sk-or-v1-dummykey9876543210"

            with patch.object(
                app.ai_client,
                "ask",
                return_value=GeminiResponse(True, "Run ss -tulpn to inspect open ports.", model_used="openrouter/free"),
            ):
                input_bar.set_text("ai check open ports")
                await pilot.press("enter")
                await pilot.pause(0.2)
                strips = app.screen._compositor.render_strips(Size(110, 28))
                rendered = "\n".join("".join(seg.text for seg in st) for st in strips)
                assert "ss -tulpn" in rendered

            input_bar.set_text("n1brox ai auto on")
            await pilot.press("enter")
            await pilot.pause(0.15)
            assert app.config.ai_auto_explain is True
            assert N1BroXConfig.load(cfg_file).ai_auto_explain is True

    asyncio.run(_run())
