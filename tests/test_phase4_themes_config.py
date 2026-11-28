import asyncio
from pathlib import Path
from textual.geometry import Size

from app.application import N1BroXApp
from app.config import N1BroXConfig
from app.ui.input_bar import InputBar


def test_config_save_load_validation_backup_and_restore(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.json"
    bak_file = tmp_path / "config.backup.json"

    cfg = N1BroXConfig(theme="graphite", max_output_lines=5000)
    cfg.save(cfg_file)
    loaded = N1BroXConfig.load(cfg_file)
    assert loaded.theme == "graphite"
    assert loaded.max_output_lines == 5000

    # Backup and mutate
    ok, _ = N1BroXConfig.backup(cfg_file, bak_file)
    assert ok is True
    N1BroXConfig(theme="minimal_dark").save(cfg_file)
    assert N1BroXConfig.load(cfg_file).theme == "minimal_dark"

    # Restore recovers graphite
    restored, _ = N1BroXConfig.restore(cfg_file, bak_file)
    assert restored is not None and restored.theme == "graphite"

    # Corrupt file safely falls back to defaults without crashing
    cfg_file.write_text("{broken json!!!", encoding="utf-8")
    fallback = N1BroXConfig.load(cfg_file)
    assert fallback.theme == "holographic_blue"

    # Invalid theme name sanitizes back to default
    invalid = N1BroXConfig(theme="nonexistent_neon").validate()
    assert invalid.theme == "holographic_blue"


def test_live_theme_switching_and_n1brox_commands(tmp_path: Path) -> None:
    async def _run() -> None:
        cfg_file = tmp_path / "config.json"
        app = N1BroXApp(config=N1BroXConfig(), config_path=cfg_file)
        async with app.run_test(size=(110, 28)) as pilot:
            await pilot.pause(0.25)
            input_bar = app.query_one("#input-bar", InputBar)

            assert app.screen.has_class("theme-holographic_blue")

            # Switch via `n1brox theme graphite`
            input_bar.set_text("n1brox theme graphite")
            await pilot.press("enter")
            await pilot.pause(0.15)
            assert app.config.theme == "graphite"
            assert app.screen.has_class("theme-graphite")
            assert not app.screen.has_class("theme-holographic_blue")
            assert N1BroXConfig.load(cfg_file).theme == "graphite"

            # Cycle via F2 -> minimal_dark
            await pilot.press("f2")
            await pilot.pause(0.1)
            assert app.config.theme == "minimal_dark"
            assert app.screen.has_class("theme-minimal_dark")

            # Run `n1brox help` and verify rendered output
            input_bar.set_text("n1brox help")
            await pilot.press("enter")
            await pilot.pause(0.15)
            strips = app.screen._compositor.render_strips(Size(110, 28))
            rendered = "\n".join("".join(seg.text for seg in st) for st in strips)
            assert "Built-in Commands" in rendered
            assert "n1brox theme" in rendered

    asyncio.run(_run())
