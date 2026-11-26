from pathlib import Path
from app.system.preview import render_file_preview


def test_file_preview_text_binary_and_missing(tmp_path: Path) -> None:
    sample = tmp_path / "demo.py"
    sample.write_text("# comment\ndef hello():\n    return 42\n", encoding="utf-8")

    ok, header, rows = render_file_preview("demo.py", cwd=str(tmp_path))
    assert ok is True
    assert "demo.py" in header
    assert any("def hello():" in txt and kind == "keyword" for txt, kind in rows)
    assert any("# comment" in txt and kind == "comment" for txt, kind in rows)

    bin_file = tmp_path / "data.bin"
    bin_file.write_bytes(b"\x00\x01\x02\x03binary")
    ok_bin, msg_bin, _ = render_file_preview("data.bin", cwd=str(tmp_path))
    assert ok_bin is False
    assert "Binary file" in msg_bin

    ok_miss, msg_miss, _ = render_file_preview("nope.txt", cwd=str(tmp_path))
    assert ok_miss is False
    assert "not found" in msg_miss
