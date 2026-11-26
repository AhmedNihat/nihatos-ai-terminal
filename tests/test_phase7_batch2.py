from pathlib import Path
from app.system.batch2 import export_output_lines, extract_shell_command, search_output_lines


def test_batch2_search_export_and_extract(tmp_path: Path) -> None:
    lines = ["hello world", "Error: port 8000 busy", "all good"]
    hits = search_output_lines(lines, "port 8000")
    assert len(hits) == 1
    assert hits[0][0] == 2

    ok, msg = export_output_lines(lines, "out.txt", cwd=str(tmp_path))
    assert ok is True
    assert (tmp_path / "out.txt").read_text(encoding="utf-8").splitlines() == lines

    assert extract_shell_command("```bash\nls -la\n```") == "ls -la"
    assert extract_shell_command("$ dnf check-update") == "dnf check-update"
