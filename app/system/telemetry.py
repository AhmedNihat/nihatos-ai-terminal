from dataclasses import dataclass, field
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time


@dataclass
class SystemSnapshot:
    hostname: str = ""
    os_name: str = ""
    kernel: str = ""
    uptime: str = ""
    cpu_model: str = ""
    cpu_cores: int = 0
    cpu_percent: float = 0.0
    load_avg: str = ""
    ram_used_gb: float = 0.0
    ram_total_gb: float = 0.0
    ram_percent: float = 0.0
    disk_used_gb: float = 0.0
    disk_total_gb: float = 0.0
    disk_percent: float = 0.0
    battery_percent: int | None = None
    battery_status: str = "N/A"
    temps: list[tuple[str, float]] = field(default_factory=list)
    fans: list[tuple[str, int]] = field(default_factory=list)
    net_interfaces: list[tuple[str, str]] = field(default_factory=list)
    usb_devices: list[str] = field(default_factory=list)
    storage_devices: list[str] = field(default_factory=list)


def make_bar(percent: float, width: int = 16) -> str:
    clamped = max(0.0, min(100.0, percent))
    filled = int(round((clamped / 100.0) * width))
    return "█" * filled + "░" * (width - filled)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        return ""


def _get_uptime() -> str:
    raw = _read_text(Path("/proc/uptime"))
    if not raw:
        return "unknown"
    try:
        secs = int(float(raw.split()[0]))
        days, rem = divmod(secs, 86400)
        hrs, rem = divmod(rem, 3600)
        mins, _ = divmod(rem, 60)
        parts = []
        if days:
            parts.append(f"{days}d")
        if hrs or days:
            parts.append(f"{hrs}h")
        parts.append(f"{mins}m")
        return " ".join(parts)
    except ValueError:
        return "unknown"


def _get_cpu_percent() -> float:
    def _read_stat() -> tuple[int, int]:
        line = _read_text(Path("/proc/stat")).splitlines()[0]
        nums = [int(x) for x in line.split()[1:8]]
        idle = nums[3] + nums[4]
        return sum(nums), idle

    try:
        t1, i1 = _read_stat()
        time.sleep(0.12)
        t2, i2 = _read_stat()
        dt = t2 - t1
        di = i2 - i1
        if dt <= 0:
            return 0.0
        return round(((dt - di) / dt) * 100.0, 1)
    except Exception:
        return 0.0


def _get_cpu_model() -> str:
    for line in _read_text(Path("/proc/cpuinfo")).splitlines():
        if line.lower().startswith("model name"):
            return line.split(":", 1)[1].strip()
    return platform.processor() or "Unknown CPU"


def _get_ram() -> tuple[float, float, float]:
    info: dict[str, int] = {}
    for line in _read_text(Path("/proc/meminfo")).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            parts = v.strip().split()
            if parts and parts[0].isdigit():
                info[k.strip()] = int(parts[0])
    total_kb = info.get("MemTotal", 0)
    avail_kb = info.get("MemAvailable", info.get("MemFree", 0))
    used_kb = max(0, total_kb - avail_kb)
    if total_kb <= 0:
        return 0.0, 0.0, 0.0
    total_gb = total_kb / (1024 * 1024)
    used_gb = used_kb / (1024 * 1024)
    pct = (used_kb / total_kb) * 100.0
    return round(used_gb, 2), round(total_gb, 2), round(pct, 1)


def _get_battery() -> tuple[int | None, str]:
    ps_dir = Path("/sys/class/power_supply")
    if not ps_dir.is_dir():
        return None, "No Battery"
    for bat in sorted(ps_dir.glob("BAT*")):
        cap = _read_text(bat / "capacity")
        status = _read_text(bat / "status") or "Unknown"
        if cap.isdigit():
            return int(cap), status
    return None, "AC / No Battery"


def _get_hwmon_temps_and_fans() -> tuple[list[tuple[str, float]], list[tuple[str, int]]]:
    temps: list[tuple[str, float]] = []
    fans: list[tuple[str, int]] = []
    hwmon_root = Path("/sys/class/hwmon")
    if not hwmon_root.is_dir():
        return temps, fans

    for hw in sorted(hwmon_root.glob("hwmon*")):
        chip = _read_text(hw / "name") or hw.name
        for tfile in sorted(hw.glob("temp*_input")):
            raw = _read_text(tfile)
            if raw.lstrip("-").isdigit():
                val_c = int(raw) / 1000.0
                if -10.0 < val_c < 130.0:
                    lbl_file = tfile.with_name(tfile.name.replace("_input", "_label"))
                    lbl = _read_text(lbl_file) or tfile.stem.replace("_input", "")
                    temps.append((f"{chip}/{lbl}", round(val_c, 1)))
        for ffile in sorted(hw.glob("fan*_input")):
            raw = _read_text(ffile)
            if raw.isdigit():
                rpm = int(raw)
                lbl_file = ffile.with_name(ffile.name.replace("_input", "_label"))
                lbl = _read_text(lbl_file) or ffile.stem.replace("_input", "")
                fans.append((f"{chip}/{lbl}", rpm))
    return temps[:8], fans[:6]


def _get_usb_devices() -> list[str]:
    if shutil.which("lsusb"):
        try:
            out = subprocess.check_output(["lsusb"], text=True, timeout=3.0, stderr=subprocess.DEVNULL)
            devices = []
            for line in out.splitlines():
                line = line.strip()
                if not line:
                    continue
                # Hide empty root hubs for cleaner output
                if "root hub" in line.lower():
                    continue
                parts = line.split("ID ", 1)
                devices.append(parts[1] if len(parts) == 2 else line)
            if devices:
                return devices
        except Exception:
            pass

    # Fallback: read /sys/bus/usb/devices/*/product
    found: list[str] = []
    usb_dir = Path("/sys/bus/usb/devices")
    if usb_dir.is_dir():
        for prod in sorted(usb_dir.glob("*/product")):
            name = _read_text(prod)
            if name and "host controller" not in name.lower():
                found.append(name)
    return found


def _get_storage_devices() -> list[str]:
    if not shutil.which("lsblk"):
        return []
    try:
        out = subprocess.check_output(
            ["lsblk", "-d", "-n", "-o", "NAME,SIZE,TRAN,MODEL"],
            text=True,
            timeout=3.0,
            stderr=subprocess.DEVNULL,
        )
        return [" ".join(line.split()) for line in out.splitlines() if line.strip()]
    except Exception:
        return []


def _get_network_interfaces() -> list[tuple[str, str]]:
    if not shutil.which("ip"):
        return []
    try:
        out = subprocess.check_output(
            ["ip", "-br", "-4", "addr"],
            text=True,
            timeout=3.0,
            stderr=subprocess.DEVNULL,
        )
        items: list[tuple[str, str]] = []
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[0] != "lo":
                items.append((parts[0], f"{parts[1]} ({parts[2]})"))
        return items
    except Exception:
        return []


def collect_snapshot() -> SystemSnapshot:
    os_name = platform.system()
    os_release = Path("/etc/os-release")
    if os_release.is_file():
        for line in _read_text(os_release).splitlines():
            if line.startswith("PRETTY_NAME="):
                os_name = line.split("=", 1)[1].strip().strip('"')
                break

    ram_used, ram_total, ram_pct = _get_ram()
    du = shutil.disk_usage("/")
    disk_total = round(du.total / (1024**3), 1)
    disk_used = round(du.used / (1024**3), 1)
    disk_pct = round((du.used / du.total) * 100.0, 1) if du.total else 0.0

    bat_pct, bat_status = _get_battery()
    temps, fans = _get_hwmon_temps_and_fans()
    la = os.getloadavg() if hasattr(os, "getloadavg") else (0.0, 0.0, 0.0)

    return SystemSnapshot(
        hostname=platform.node(),
        os_name=os_name,
        kernel=platform.release(),
        uptime=_get_uptime(),
        cpu_model=_get_cpu_model(),
        cpu_cores=os.cpu_count() or 1,
        cpu_percent=_get_cpu_percent(),
        load_avg=f"{la[0]:.2f}, {la[1]:.2f}, {la[2]:.2f}",
        ram_used_gb=ram_used,
        ram_total_gb=ram_total,
        ram_percent=ram_pct,
        disk_used_gb=disk_used,
        disk_total_gb=disk_total,
        disk_percent=disk_pct,
        battery_percent=bat_pct,
        battery_status=bat_status,
        temps=temps,
        fans=fans,
        net_interfaces=_get_network_interfaces(),
        usb_devices=_get_usb_devices(),
        storage_devices=_get_storage_devices(),
    )


_LAST_CPU_TOTAL: int | None = None
_LAST_CPU_IDLE: int | None = None


def _get_cpu_percent_fast() -> float:
    global _LAST_CPU_TOTAL, _LAST_CPU_IDLE
    try:
        line = _read_text(Path("/proc/stat")).splitlines()[0]
        nums = [int(x) for x in line.split()[1:8]]
        idle = nums[3] + nums[4]
        total = sum(nums)
        if _LAST_CPU_TOTAL is None or _LAST_CPU_IDLE is None:
            _LAST_CPU_TOTAL, _LAST_CPU_IDLE = total, idle
            return 0.0
        dt = total - _LAST_CPU_TOTAL
        di = idle - _LAST_CPU_IDLE
        _LAST_CPU_TOTAL, _LAST_CPU_IDLE = total, idle
        if dt <= 0:
            return 0.0
        return round(((dt - di) / dt) * 100.0, 1)
    except Exception:
        return 0.0


def collect_hud_line(paused: bool = False) -> str:
    cpu = _get_cpu_percent_fast()
    ram_u, ram_t, ram_p = _get_ram()
    bat_p, bat_st = _get_battery()
    temps, fans = _get_hwmon_temps_and_fans()

    max_temp = f"{max(c for _, c in temps):.0f}°C" if temps else "N/A"
    fan_str = f"{fans[0][1]} RPM" if fans else "N/A"
    bat_str = f"{bat_p}%" if bat_p is not None else "AC"
    mode = "⏸ COPY MODE (Ctrl+G: Live)" if paused else "● LIVE 1s (Ctrl+G: Copy)"

    return f" {mode}  |  CPU: {cpu:4.1f}%  |  RAM: {ram_u:.1f}/{ram_t:.0f}G ({ram_p:.0f}%)  |  TEMP: {max_temp}  |  FAN: {fan_str}  |  BAT: {bat_str}"
