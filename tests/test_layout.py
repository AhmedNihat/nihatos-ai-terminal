import asyncio
import os
import tempfile
from textual.geometry import Size

from app.application import NihatOSApp
from app.config import NihatOSConfig
from app.ui.input_bar import InputBar
from app.ui.output_panel import OutputPanel


def _render_rows(app: NihatOSApp) -> list[str]:
    w, h = app.size.width, app.size.height
    strips = app.screen._compositor.render_strips(Size(w, h))
    return ["".join(seg.text for seg in strip) for strip in strips]


def _find_prompt_row(app: NihatOSApp) -> int:
    for row_idx, plain in enumerate(_render_rows(app)):
        if "NIHATOS " in plain and "❯" in plain:
            return row_idx
    raise AssertionError("Could not find 'NIHATOS <cwd> ❯' prompt on rendered screen")


def test_two_box_layout_28x110_and_flood_invariance() -> None:
    async def _run() -> None:
        config = NihatOSConfig(max_output_lines=200)
        app = NihatOSApp(config=config)
        async with app.run_test(size=(110, 28)) as pilot:
            await pilot.pause(0.2)

            input_bar = app.query_one("#input-bar", InputBar)
            output = app.query_one("#output-panel", OutputPanel)

            # Box 1 (Input): rows 3..5 (prompt at row 4); Box 2 (Output): rows 6..25 (height 20)
            assert input_bar.region.y == 3
            assert input_bar.region.height == 3
            assert _find_prompt_row(app) == 4
            assert output.region.y == 7
            assert output.region.height == 20

            # Flood output with 2,500 lines; memory capped and input box stays fixed at row 3
            for i in range(2500):
                output.write_system_line(f"Flood line #{i}")
            await pilot.pause(0.15)

            assert len(output.lines) <= 200
            assert _find_prompt_row(app) == 4

            # Multiline input expands Input Box downward while prompt stays at row 4
            input_bar.set_text("echo line1\necho line2\necho line3")
            await pilot.pause(0.1)
            assert _find_prompt_row(app) == 4
            assert input_bar.region.height == 5
            assert output.region.y == 9

            # Reject >4KB single line safely
            input_bar.clear_input()
            input_bar.set_text("a" * 4500)
            await pilot.press("enter")
            await pilot.pause(0.1)
            assert _find_prompt_row(app) == 4

    asyncio.run(_run())


def test_latest_answer_stays_on_top_and_older_moves_below() -> None:
    async def _run() -> None:
        app = NihatOSApp()
        async with app.run_test(size=(110, 28)) as pilot:
            await pilot.pause(0.3)
            input_bar = app.query_one("#input-bar", InputBar)

            input_bar.set_text("echo OLD_ANSWER_FIRST")
            await pilot.press("enter")
            await pilot.pause(0.3)

            input_bar.set_text("echo NEW_ANSWER_SECOND")
            await pilot.press("enter")
            await pilot.pause(0.3)

            rows = _render_rows(app)
            # Verify centered header greeting
            assert "NIHAT OS" in rows[0] and "NihatOS Terminal" in rows[0]
            assert "Welcome, Nihat Sir" in rows[1]

            # Verify output block header shows directory + ❯ + command
            cmd_header_row = next(i for i, r in enumerate(rows) if "❯ echo NEW_ANSWER_SECOND" in r)
            assert 6 < cmd_header_row < 25

            new_row = next(i for i, r in enumerate(rows) if "NEW_ANSWER_SECOND" in r and "❯" not in r)
            old_row = next(i for i, r in enumerate(rows) if "OLD_ANSWER_FIRST" in r and "❯" not in r)

            # Latest answer must appear ABOVE the older answer inside the Output Box
            assert 6 < cmd_header_row < new_row < old_row < 25
            assert _find_prompt_row(app) == 4

    asyncio.run(_run())


def test_responsive_layout_resizes_and_history() -> None:
    async def _run() -> None:
        app = NihatOSApp()
        async with app.run_test(size=(110, 28)) as pilot:
            await pilot.pause(0.2)
            output = app.query_one("#output-panel", OutputPanel)
            assert _find_prompt_row(app) == 4
            assert output.region.height == 20

            await pilot.resize_terminal(120, 35)
            await pilot.pause(0.1)
            assert _find_prompt_row(app) == 4
            assert output.region.height == 27

            await pilot.resize_terminal(80, 21)
            await pilot.pause(0.1)
            assert _find_prompt_row(app) == 4
            assert output.region.height == 13

            await pilot.resize_terminal(110, 28)
            await pilot.pause(0.1)
            assert _find_prompt_row(app) == 4
            assert output.region.height == 20

            input_bar = app.query_one("#input-bar", InputBar)
            input_bar.set_text("echo first_cmd")
            await pilot.press("enter")
            await pilot.pause(0.1)
            input_bar.set_text("echo second_cmd")
            await pilot.press("enter")
            await pilot.pause(0.1)

            await pilot.press("up")
            assert input_bar.text == "echo second_cmd"
            await pilot.press("up")
            assert input_bar.text == "echo first_cmd"
            await pilot.press("down")
            assert input_bar.text == "echo second_cmd"

    asyncio.run(_run())


def test_prompt_shows_current_directory_and_updates_on_cd() -> None:
    async def _run() -> None:
        app = NihatOSApp()
        async with app.run_test(size=(110, 28)) as pilot:
            await pilot.pause(0.3)

            with tempfile.TemporaryDirectory(prefix="nihatos_dir_") as tmpdir:
                real_tmp = os.path.realpath(tmpdir)
                dir_name = os.path.basename(real_tmp)

                input_bar = app.query_one("#input-bar", InputBar)
                input_bar.set_text(f"cd '{real_tmp}'")
                await pilot.press("enter")
                await pilot.pause(0.3)

                prompt_line = _render_rows(app)[_find_prompt_row(app)]
                assert "NIHATOS " in prompt_line
                assert dir_name in prompt_line
                assert _find_prompt_row(app) == 4

    asyncio.run(_run())


def test_multiline_paste_warns_and_does_not_auto_execute() -> None:
    async def _run() -> None:
        app = NihatOSApp()
        async with app.run_test(size=(110, 28)) as pilot:
            await pilot.pause(0.2)
            input_bar = app.query_one("#input-bar", InputBar)

            input_bar.insert_pasted_text("echo line_one\necho line_two")
            await pilot.pause(0.1)

            assert input_bar.text == "echo line_one\necho line_two"
            assert "WARNING: Multiline paste (2 lines)" in app._hud_notice
            assert _find_prompt_row(app) == 4

    asyncio.run(_run())


def test_clear_command_clears_output_box() -> None:
    async def _run() -> None:
        app = NihatOSApp()
        async with app.run_test(size=(110, 28)) as pilot:
            await pilot.pause(0.3)
            input_bar = app.query_one("#input-bar", InputBar)

            input_bar.set_text("echo BEFORE_CLEAR_MARKER")
            await pilot.press("enter")
            await pilot.pause(0.3)
            assert any("BEFORE_CLEAR_MARKER" in r for r in _render_rows(app))

            input_bar.set_text("clear")
            await pilot.press("enter")
            await pilot.pause(0.3)

            output_rows = "\n".join(_render_rows(app)[7:25])
            assert "BEFORE_CLEAR_MARKER" not in output_rows
            assert _find_prompt_row(app) == 4

    asyncio.run(_run())
