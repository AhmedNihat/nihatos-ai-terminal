from dataclasses import asdict, dataclass
import json
from pathlib import Path
import shutil
from typing import Literal

try:
    from app.themes.palettes import THEMES
except ImportError:
    THEMES = {
        "nihatos": {"name": "Nihat.O.S", "accent": "#00e5ff", "accent2": "#ffb300"},
        "ultron": {"name": "U.L.T.R.O.N", "accent": "#ff1f33", "accent2": "#ff8a00"},
    }

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "nihatos-terminal"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.json"
DEFAULT_BACKUP_FILE = DEFAULT_CONFIG_DIR / "config.backup.json"
DEFAULT_DATA_DIR = Path.home() / ".local" / "share" / "nihatos-terminal"


@dataclass
class NihatOSConfig:
    """Validated user-level configuration for NihatOS Terminal."""

    theme: str = "holographic_blue"
    center_mode: Literal["usable", "geometric"] = "usable"
    max_output_lines: int = 2000
    max_history_items: int = 1000
    max_single_line_bytes: int = 4096
    shell_path: str = "/bin/bash"
    greeting: str = "Welcome, Nihat Sir"
    hud_subtitle: str = "Sir, you are the Best.. just command me.."
    ai_model: str = "openrouter/free"
    ai_auto_explain: bool = False
    os_name: str = "Nihat.O.S"

    def validate(self) -> "NihatOSConfig":
        if self.theme not in THEMES:
            self.theme = "holographic_blue"
        if self.center_mode not in ("usable", "geometric"):
            self.center_mode = "usable"
        self.max_output_lines = max(50, min(50000, int(self.max_output_lines)))
        self.max_history_items = max(50, min(50000, int(self.max_history_items)))
        self.max_single_line_bytes = max(512, min(4096, int(self.max_single_line_bytes)))
        if not self.shell_path or not isinstance(self.shell_path, str):
            self.shell_path = "/bin/bash"
        if not isinstance(self.greeting, str) or not self.greeting.strip():
            self.greeting = "Welcome, Nihat Sir"
        if not isinstance(self.hud_subtitle, str) or not self.hud_subtitle.strip():
            self.hud_subtitle = "Sir, you are the Best.. just command me.."
        if not isinstance(self.ai_model, str) or not self.ai_model.strip():
            self.ai_model = "openrouter/free"
        self.ai_auto_explain = bool(self.ai_auto_explain)
        if not isinstance(self.os_name, str) or not self.os_name.strip():
            self.os_name = "Nihat.O.S"
        return self

    @classmethod
    def load(cls, path: Path = DEFAULT_CONFIG_FILE) -> "NihatOSConfig":
        cfg = cls()
        if not path.is_file():
            return cfg
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return cfg
            valid_fields = set(asdict(cfg).keys())
            filtered = {k: v for k, v in raw.items() if k in valid_fields}
            return cls(**filtered).validate()
        except (OSError, ValueError, TypeError):
            return cfg

    def save(self, path: Path = DEFAULT_CONFIG_FILE) -> Path:
        self.validate()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
        return path

    @staticmethod
    def backup(
        config_path: Path = DEFAULT_CONFIG_FILE,
        backup_path: Path = DEFAULT_BACKUP_FILE,
    ) -> tuple[bool, str]:
        if not config_path.is_file():
            return False, f"No config file found at {config_path} to back up."
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(config_path, backup_path)
        return True, f"Configuration backed up to {backup_path}"

    @classmethod
    def restore(
        cls,
        config_path: Path = DEFAULT_CONFIG_FILE,
        backup_path: Path = DEFAULT_BACKUP_FILE,
    ) -> tuple["NihatOSConfig | None", str]:
        if not backup_path.is_file():
            return None, f"No backup found at {backup_path}"
        restored = cls.load(backup_path)
        restored.save(config_path)
        return restored, f"Configuration restored from {backup_path}"
