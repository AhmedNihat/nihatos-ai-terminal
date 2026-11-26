from pathlib import Path
import re


def search_output_lines(lines: list[str], query: str, limit: int = 30) -> list[tuple[int, str]]:
    """Return list of (1-based line_no, line_text) matching query (case-insensitive)."""
    q = query.strip().lower()
    if not q:
        return []
    matches: list[tuple[int, str]] = []
    for idx, raw in enumerate(lines, start=1):
        text = str(raw)
        if q in text.lower():
            matches.append((idx, text))
    return matches[-limit:]


def export_output_lines(lines: list[str], filename: str, cwd: str = "") -> tuple[bool, str]:
    """Save output lines to a plain-text file."""
    clean = filename.strip().strip('"').strip("'") or "nihatos-log.txt"
    base = Path(cwd) if cwd else Path.cwd()
    target = Path(clean).expanduser()
    if not target.is_absolute():
        target = (base / target).resolve()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(str(line) for line in lines) + "\n"
        target.write_text(content, encoding="utf-8")
        return True, f"Saved {len(lines)} lines to {target}"
    except OSError as exc:
        return False, f"Failed to save log: {exc}"


def extract_shell_command(ai_text: str) -> str:
    """Extract a single clean shell command from an AI response."""
    text = ai_text.strip()
    m = re.search(r"```(?:bash|sh)?\s*\n(.*?)\n```", text, flags=re.DOTALL | re.IGNORECASE)
    if m:
        text = m.group(1).strip()
    for line in text.splitlines():
        cand = line.strip().strip("`").strip()
        if not cand or cand.startswith("#"):
            continue
        if cand.startswith("$ "):
            cand = cand[2:].strip()
        return cand
    return ""
