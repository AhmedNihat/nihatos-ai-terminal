import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess

DEFAULT_BOOKMARKS_FILE = Path.home() / ".config" / "nihatos-terminal" / "bookmarks.json"


# --- 1. Quick Folder Bookmarks ---
def load_bookmarks(path: Path = DEFAULT_BOOKMARKS_FILE) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except Exception:
        pass
    return {}


def save_bookmark(name: str, directory: str, path: Path = DEFAULT_BOOKMARKS_FILE) -> tuple[bool, str]:
    clean = re.sub(r"[^A-Za-z0-9_\-]", "", name.strip())
    if not clean:
        return False, "Invalid bookmark name. Use letters, numbers, '-' or '_'."
    target = str(Path(directory).expanduser().resolve())
    data = load_bookmarks(path)
    data[clean] = target
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return True, f"Saved bookmark '{clean}' -> {target}"


def remove_bookmark(name: str, path: Path = DEFAULT_BOOKMARKS_FILE) -> tuple[bool, str]:
    data = load_bookmarks(path)
    if name not in data:
        return False, f"Bookmark '{name}' not found."
    del data[name]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return True, f"Removed bookmark '{name}'."


# --- 2. Listening Ports & Port Killer ---
def list_listening_ports() -> list[tuple[str, str, str, str]]:
    """Return list of (proto, port, pid, process_name)."""
    if not shutil.which("ss"):
        return []
    try:
        out = subprocess.check_output(
            ["ss", "-tulpnH"],
            text=True,
            timeout=3.0,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return []

    rows: list[tuple[str, str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        proto = parts[0]
        local_addr = parts[4]
        port = local_addr.rsplit(":", 1)[-1]
        proc_col = " ".join(parts[6:]) if len(parts) > 6 else ""
        m_pid = re.search(r"pid=(\d+)", proc_col)
        m_name = re.search(r'"([^"]+)"', proc_col)
        pid = m_pid.group(1) if m_pid else "-"
        pname = m_name.group(1) if m_name else "unknown"
        key = (proto, port, pid)
        if key not in seen:
            seen.add(key)
            rows.append((proto, port, pid, pname))
    return rows


def kill_port(port_str: str) -> tuple[bool, str]:
    if not port_str.isdigit():
        return False, "Usage: killport <port_number> (e.g., killport 8000)"
    target_port = port_str.strip()
    matches = [r for r in list_listening_ports() if r[1] == target_port and r[2].isdigit()]
    if not matches:
        return False, f"No user-accessible process found listening on port {target_port}."

    killed: list[str] = []
    errors: list[str] = []
    for _, _, pid_s, pname in matches:
        try:
            os.kill(int(pid_s), signal.SIGTERM)
            killed.append(f"{pname} (PID {pid_s})")
        except PermissionError:
            errors.append(f"PID {pid_s} needs sudo")
        except ProcessLookupError:
            pass
        except OSError as exc:
            errors.append(f"PID {pid_s}: {exc}")

    if killed:
        msg = f"Terminated on port {target_port}: " + ", ".join(killed)
        if errors:
            msg += " | Skipped: " + ", ".join(errors)
        return True, msg
    return False, f"Could not kill port {target_port}: " + ", ".join(errors or ["unknown error"])


# --- 3. USB / Serial Port Detector (Arduino / Embedded Boards) ---
def list_serial_ports() -> list[tuple[str, str]]:
    """Return list of (device_path, description) for connected USB serial devices."""
    found: dict[str, str] = {}
    by_id = Path("/dev/serial/by-id")
    if by_id.is_dir():
        for link in sorted(by_id.iterdir()):
            try:
                real = str(link.resolve())
                found[real] = link.name
            except OSError:
                pass

    dev_dir = Path("/dev")
    for pattern in ("ttyUSB*", "ttyACM*"):
        for dev in sorted(dev_dir.glob(pattern)):
            p_str = str(dev)
            if p_str not in found:
                found[p_str] = "USB Serial Device"

    return sorted(found.items())
