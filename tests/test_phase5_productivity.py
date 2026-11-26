import asyncio
from pathlib import Path
import subprocess
from textual.geometry import Size

from app.application import NihatOSApp
from app.config import NihatOSConfig
from app.integrations.error_hints import explain_failure
from app.integrations.git import get_git_status
from app.shell.completion import CompletionEngine
from app.shell.history import CommandHistory, is_sensitive_command
from app.themes.palettes import get_palette
from app.ui.input_bar import InputBar


def test_persistent_history_and_secret_filtering(tmp_path: Path) -> None:
    hist_file = tmp_path / "history.jsonl"
    h1 = CommandHistory(max_items=100, history_path=hist_file)

    assert h1.add("ls -la", cwd="/tmp") is True
    h1.update_last_result(0, 0.012)
    assert h1.add("echo hello_world", cwd="/tmp") is True
    # Sensitive commands must be rejected from persistent storage
    assert is_sensitive_command("export API_KEY=super_secret_123") is True
    assert h1.add("export API_KEY=super_secret_123", cwd="/tmp") is False
    assert h1.add("curl -u admin:pass123 https://example.com") is False

    # Reload from disk and verify persistence + secret absence
    h2 = CommandHistory(max_items=100, history_path=hist_file)
    assert len(h2) == 2
    assert h2.suggest("echo h") == "echo hello_world"
    assert all("super_secret" not in e.command for e in h2.search(""))

    export_file = tmp_path / "exported.txt"
    assert h2.export_to(export_file) == 2
    assert "echo hello_world" in export_file.read_text(encoding="utf-8")


def test_autocomplete_and_syntax_highlighting(tmp_path: Path) -> None:
    (tmp_path / "nihat_alpha.txt").write_text("ok", encoding="utf-8")
    (tmp_path / "nihat_dir").mkdir()

    engine = CompletionEngine()

    # Path completion for file and dir
    new_line, _, matches = engine.complete("cat nihat_a", len("cat nihat_a"), str(tmp_path))
    assert new_line == "cat nihat_alpha.txt"
    assert matches == ["nihat_alpha.txt"]

    new_line, _, matches = engine.complete("cd nihat_d", len("cd nihat_d"), str(tmp_path))
    assert new_line == "cd nihat_dir/"

    # Built-in nihatos subcommand & theme completion
    new_line, _, _ = engine.complete("nihatos th", len("nihatos th"), str(tmp_path))
    assert new_line == "nihatos theme "
    new_line, _, _ = engine.complete("nihatos theme gr", len("nihatos theme gr"), str(tmp_path))
    assert new_line == "nihatos theme graphite "

    # Syntax highlighting distinguishes valid vs unknown command
    pal = get_palette("holographic_blue")
    valid_text = engine.highlight_line("echo -n 'hi' | cat", str(tmp_path), pal)
    assert any(pal.ok in str(sp.style) for sp in valid_text.spans)
    invalid_text = engine.highlight_line("definitely_not_a_cmd_xyz", str(tmp_path), pal)
    assert any(pal.err in str(sp.style) for sp in invalid_text.spans)


def test_git_integration_readonly(tmp_path: Path) -> None:
    assert get_git_status(str(tmp_path)).is_repo is False

    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "untracked.py").write_text("print(1)\n", encoding="utf-8")

    st = get_git_status(str(tmp_path))
    assert st.is_repo is True
    assert st.branch == "main"
    assert st.untracked == 1
    assert "git:(main ?1)" == st.format_badge()


def test_error_hints_and_interactive_ghost_and_ctrl_r(tmp_path: Path) -> None:
    hint = explain_failure("nonexistent_tool_99", 127, "command not found", {"ls", "grep"})
    assert hint is not None and "dnf provides" in hint

    async def _run() -> None:
        hist_file = tmp_path / "history.jsonl"
        app = NihatOSApp(
            config=NihatOSConfig(),
            config_path=tmp_path / "config.json",
            history_path=hist_file,
        )
        async with app.run_test(size=(110, 28)) as pilot:
            await pilot.pause(0.25)
            input_bar = app.query_one("#input-bar", InputBar)

            # Seed history via real command
            input_bar.set_text("echo NIHATOS_AUTOSUGGEST_TARGET")
            await pilot.press("enter")
            await pilot.pause(0.25)

            # Ghost autosuggestion appears and accepts on Right arrow
            input_bar.set_text("echo NIHATOS_AUTO")
            await pilot.pause(0.05)
            assert input_bar.get_ghost_suffix() == "SUGGEST_TARGET"
            await pilot.press("right")
            assert input_bar.text == "echo NIHATOS_AUTOSUGGEST_TARGET"

            # Ctrl+R reverse search finds the command and Tab loads it for editing
            input_bar.clear_input()
            await pilot.press("ctrl+r")
            assert input_bar.search_mode is True
            for ch in "TARGET":
                await pilot.press(ch)
            await pilot.press("tab")
            assert input_bar.search_mode is False
            assert input_bar.text == "echo NIHATOS_AUTOSUGGEST_TARGET"

            # Trigger failed command -> verify [NihatOS Hint] appears in output
            input_bar.set_text("definitely_missing_nihat_cmd_404")
            await pilot.press("enter")
            await pilot.pause(0.35)
            strips = app.screen._compositor.render_strips(Size(110, 28))
            rendered = "\n".join("".join(seg.text for seg in st) for st in strips)
            assert "[NihatOS Hint]" in rendered

    asyncio.run(_run())
