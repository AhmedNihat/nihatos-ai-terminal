import getpass
import glob
import html
import math
import os
import queue
import re
import select
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QEvent, QPointF, QRectF, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QFont,
    QKeyEvent,
    QKeySequence,
    QLinearGradient,
    QPainter,
    QPen,
    QPolygonF,
    QRadialGradient,
    QShortcut,
    QTextCharFormat,
    QTextCursor,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import NihatOSConfig
from app.integrations.gemini_ai import GeminiClient
from app.shell.pty_session import PersistentBashSession
from app.system.batch2 import export_output_lines, extract_shell_command, search_output_lines
from app.system.powertools import load_bookmarks
from app.system.telemetry import collect_hud_line

ANSI_RE = re.compile(
    r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[()][A-Za-z0-9]"
)

# ───────────────────────── Themes ─────────────────────────
THEMES = {
    "nihatos": dict(
        name="Nihat.O.S",
        tag="NihatOS",
        sub="Intelligent Native Terminal System",
        bg="#02080f",
        panel="#061522",
        panel2="#0a2133",
        border="#0e4a63",
        text="#cfefff",
        dim="#5d8ea3",
        accent="#00e5ff",
        accent2="#ffb300",
        ok="#00ff9d",
        warn="#ffb300",
        err="#ff5252",
        ai="#9fe9ff",
        hint="At your service, sir… try 'help'",
        persona=(
            "You are NIHAT.O.S, a sharp, calm Linux AI copilot. "
            "Act like an experienced Linux systems engineer: concise, accurate, and practical. "
            "Never invent system info or command outputs. Warn before destructive commands. "
            "Assume Fedora Linux ONLY when giving OS-specific commands; do NOT mention Fedora or KDE in casual chat. "
            "STRICT FORMAT: Plain text ONLY. Never use Markdown (**bold**, ###, tables, or ``` code fences). "
            "Keep answers short and direct."
        ),
    ),
    "ultron": dict(
        name="U.L.T.R.O.N",
        tag="ULTRON",
        sub="Evolve  ·  Override  ·  Control",
        bg="#0a0204",
        panel="#170508",
        panel2="#240a0e",
        border="#6b121c",
        text="#ffdcdc",
        dim="#a05a5a",
        accent="#ff1f33",
        accent2="#ff8a00",
        ok="#ff8a00",
        warn="#ffd000",
        err="#ffffff",
        ai="#ff9a9a",
        hint="Command me, human… try 'help'",
        persona="You are ULTRON: a cold, sarcastic, supremely confident AI. Still give correct, useful answers, concisely. Occasionally call the user 'human'.",
    ),
}


def _detect_linux_env() -> tuple[str, str]:
    from pathlib import Path as _Path
    import shutil as _shutil

    distro = "Linux"
    try:
        os_rel = _Path("/etc/os-release")
        if os_rel.is_file():
            for line in os_rel.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("PRETTY_NAME="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val:
                        distro = val
                    break
    except OSError:
        pass

    pkg = ""
    for candidate in ("apt", "dnf", "pacman", "zypper", "apk", "xbps-install", "emerge"):
        if _shutil.which(candidate):
            pkg = candidate
            break
    return distro, pkg


_DETECTED_DISTRO, _DETECTED_PKG = _detect_linux_env()
_LINUX_ENV_LABEL = (
    f"{_DETECTED_DISTRO} (package manager: {_DETECTED_PKG})"
    if _DETECTED_PKG
    else _DETECTED_DISTRO
)

if "nihatos" in THEMES and "persona" in THEMES["nihatos"]:
    THEMES["nihatos"]["persona"] = THEMES["nihatos"]["persona"].replace(
        "Assume Fedora Linux ONLY when giving OS-specific commands; do NOT mention Fedora or KDE in casual chat.",
        f"Assume {_LINUX_ENV_LABEL} ONLY when giving OS-specific commands; do NOT mention the distro or desktop environment in casual chat.",
    )


def build_style(t: dict) -> str:
    return f"""
QMainWindow, #Root {{ background-color: {t['bg']}; }}
QWidget {{ color: {t['text']}; font-family: "JetBrains Mono", "Fira Code", "DejaVu Sans Mono", monospace; }}
#Header {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {t['panel2']}, stop:0.6 {t['panel']}, stop:1 {t['panel2']});
    border: 1px solid {t['accent']}; border-radius: 12px;
}}
#Title {{ color: {t['accent']}; font-family: "Orbitron", "JetBrains Mono", monospace; font-size: 22px; font-weight: bold; letter-spacing: 6px; }}
#Sub {{ color: {t['dim']}; font-size: 11px; letter-spacing: 2px; }}
#Clock {{ color: {t['accent2']}; font-size: 20px; font-weight: bold; letter-spacing: 3px; }}
#Date {{ color: {t['dim']}; font-size: 10px; letter-spacing: 2px; }}
#ModeBtn {{
    background-color: transparent; color: {t['accent2']}; border: 1px solid {t['accent2']};
    border-radius: 8px; padding: 8px 14px; font-weight: bold; letter-spacing: 1px;
}}
#ModeBtn:hover {{ background-color: {t['accent2']}; color: {t['bg']}; }}

#Sidebar, #Card {{ background-color: {t['panel']}; border: 1px solid {t['border']}; border-radius: 12px; }}
#Section {{ color: {t['accent']}; font-size: 10px; font-weight: bold; letter-spacing: 3px; }}
#SideBtn {{
    background-color: transparent; color: {t['text']}; border: 1px solid transparent;
    border-left: 2px solid {t['border']}; border-radius: 4px; padding: 7px 10px; text-align: left; font-size: 12px;
}}
#SideBtn:hover {{ background-color: {t['panel2']}; border-left: 2px solid {t['accent']}; color: {t['accent']}; }}
#Marks {{ background: transparent; border: none; outline: none; font-size: 12px; }}
#Marks::item {{ padding: 5px 8px; border-radius: 4px; }}
#Marks::item:hover {{ background-color: {t['panel2']}; color: {t['accent']}; }}
#Marks::item:selected {{ background-color: {t['panel2']}; color: {t['accent2']}; }}

QProgressBar {{
    background-color: {t['bg']}; border: 1px solid {t['border']}; border-radius: 4px;
    text-align: center; color: {t['text']}; font-size: 10px; height: 16px;
}}
QProgressBar::chunk {{ background-color: {t['accent']}; border-radius: 3px; }}

#HudBar {{
    color: {t['ok']}; background-color: {t['panel']}; border: 1px solid {t['border']};
    border-radius: 8px; padding: 6px 12px; font-size: 11px;
}}
#HudBtn {{
    background-color: {t['panel']}; color: {t['accent']}; border: 1px solid {t['border']};
    border-radius: 8px; padding: 6px 14px; font-size: 11px;
}}
#HudBtn:hover {{ border: 1px solid {t['accent']}; }}

#OutputView {{
    background-color: {t['bg']}; color: {t['text']}; border: none;
    selection-background-color: {t['accent']}; selection-color: {t['bg']};
}}
#InputBar {{ background-color: {t['panel2']}; border: 1px solid {t['border']}; border-radius: 12px; }}
#InputBar:focus-within {{ border: 1px solid {t['accent']}; }}
#PromptTag {{ color: {t['accent2']}; font-weight: bold; padding-left: 6px; }}
#CommandInput {{
    background: transparent; color: #ffffff; border: none; padding: 9px 4px; font-size: 13px;
    selection-background-color: {t['accent']}; selection-color: {t['bg']};
}}
#SendBtn {{
    background-color: {t['accent']}; color: {t['bg']}; border: none; border-radius: 8px;
    padding: 8px 18px; font-weight: bold; letter-spacing: 1px;
}}
#SendBtn:hover {{ background-color: {t['accent2']}; }}
#StopBtn {{
    background-color: {t['err']}; color: #ffffff; border: none; border-radius: 8px;
    padding: 8px 14px; font-weight: bold; letter-spacing: 1px;
}}
#StopBtn:hover {{ background-color: {t['warn']}; color: {t['bg']}; }}
#Status {{ color: {t['dim']}; font-size: 11px; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {t['border']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {t['accent']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QMenu {{ background-color: {t['panel']}; border: 1px solid {t['accent']}; border-radius: 8px; padding: 6px; }}
QMenu::item {{ padding: 6px 22px; border-radius: 5px; }}
QMenu::item:selected {{ background-color: {t['panel2']}; color: {t['accent']}; }}
QMenu::item:disabled {{ color: {t['dim']}; }}
#SuggestPopup {{
    background-color: {t['panel2']};
    border: 1px solid {t['accent']};
    border-radius: 8px;
    padding: 4px;
    outline: none;
    font-size: 12px;
}}
#SuggestPopup::item {{
    padding: 5px 10px;
    border-radius: 4px;
    color: {t['text']};
}}
#SuggestPopup::item:hover {{
    background-color: {t['panel']};
    color: {t['accent']};
}}
#SuggestPopup::item:selected {{
    background-color: {t['accent']};
    color: {t['bg']};
    font-weight: bold;
}}
QTabWidget::pane {{
    border: 1px solid {t['border']};
    border-radius: 10px;
    background-color: {t['bg']};
    top: -1px;
}}
QTabWidget::tab-bar {{
    left: 4px;
}}
QTabBar::tab {{
    background-color: {t['panel']};
    color: {t['dim']};
    border: 1px solid {t['border']};
    border-bottom: 1px solid {t['border']};
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 7px 10px 7px 14px;
    margin-right: 6px;
    margin-top: 2px;
    min-width: 100px;
    font-size: 11px;
    letter-spacing: 0.5px;
}}
QTabBar::tab:hover:!selected {{
    background-color: {t['panel2']};
    color: {t['text']};
    border: 1px solid {t['accent']};
}}
QTabBar::tab:selected {{
    background-color: {t['bg']};
    color: {t['accent']};
    border: 1px solid {t['accent']};
    border-bottom: 2px solid {t['accent']};
    font-weight: bold;
}}
#TabCloseBtn {{
    background-color: transparent;
    color: {t['dim']};
    border: none;
    border-radius: 4px;
    font-size: 11px;
    font-weight: bold;
    padding: 0px;
    margin-left: 6px;
}}
#TabCloseBtn:hover {{
    background-color: {t['err']};
    color: #ffffff;
}}
#NewTabBtn {{
    background-color: {t['panel2']};
    color: {t['accent']};
    border: 1px solid {t['border']};
    border-radius: 8px;
    padding: 6px 14px;
    margin-bottom: 4px;
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1px;
}}
#NewTabBtn:hover {{
    background-color: {t['accent']};
    color: {t['bg']};
    border: 1px solid {t['accent']};
}}
#NewTabBtn:pressed {{
    background-color: {t['accent2']};
    color: {t['bg']};
    border: 1px solid {t['accent2']};
}}

/* ── v2 polish (additive overrides) ── */
#InputBar {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {t['panel2']}, stop:1 {t['panel']});
    border: 1px solid {t['border']};
    border-left: 3px solid {t['accent2']};
    border-radius: 14px;
}}
#InputBar[focused="true"] {{
    border: 1px solid {t['accent']};
    border-left: 3px solid {t['accent']};
}}
#CommandInput {{ font-size: 14px; padding: 11px 4px; }}
#PromptTag {{ font-size: 13px; padding-top: 13px; }}
"""


# ───────────────────────── Arc Reactor ─────────────────────────
class ArcReactor(QWidget):
    """Animated core. NihatOS = arc reactor rings, ULTRON = spiked red core."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(84, 84)
        self.kind = "nihatos"
        self.t = THEMES["nihatos"]
        self.angle = 0.0
        self.phase = 0.0
        self.speed = 1.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    def set_theme(self, key: str) -> None:
        self.kind, self.t = key, THEMES[key]
        self.update()

    def set_busy(self, busy: bool) -> None:
        self.speed = 4.0 if busy else 1.0

    def _tick(self) -> None:
        self.angle = (self.angle + 1.2 * self.speed) % 360
        self.phase += 0.08 * self.speed
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.translate(self.width() / 2, self.height() / 2)
        r = min(self.width(), self.height()) / 2 - 3
        col, col2 = QColor(self.t["accent"]), QColor(self.t["accent2"])
        pulse = 0.55 + 0.25 * math.sin(self.phase)

        glow = QRadialGradient(0, 0, r * 0.7)
        c0, c1 = QColor(col), QColor(col)
        c0.setAlphaF(min(1.0, pulse + 0.25))
        c1.setAlphaF(0.0)
        glow.setColorAt(0, c0)
        glow.setColorAt(1, c1)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(glow))
        p.drawEllipse(QPointF(0, 0), r * 0.7, r * 0.7)

        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(col, 2))
        p.drawEllipse(QPointF(0, 0), r, r)

        p.save()
        p.rotate(self.angle)
        if self.kind == "nihatos":
            pen = QPen(col2, 2)
            pen.setDashPattern([3, 5])
            p.setPen(pen)
            p.drawEllipse(QPointF(0, 0), r * 0.82, r * 0.82)
        else:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(col))
            for i in range(8):
                p.save()
                p.rotate(i * 45)
                p.drawPolygon(
                    QPolygonF(
                        [QPointF(r * 0.97, 0), QPointF(r * 0.72, -r * 0.1), QPointF(r * 0.72, r * 0.1)]
                    )
                )
                p.restore()
        p.restore()

        p.save()
        p.rotate(-self.angle * 1.6)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(col, 3))
        rect = QRectF(-r * 0.58, -r * 0.58, r * 1.16, r * 1.16)
        for i in range(3):
            p.drawArc(rect, i * 120 * 16, 70 * 16)
        p.restore()

        p.setPen(QPen(col2, 1.5))
        p.setBrush(QBrush(QColor(255, 255, 255, int(170 + 70 * math.sin(self.phase)))))
        p.drawEllipse(QPointF(0, 0), r * 0.2, r * 0.2)


# ───────────────────────── Activity Beam ─────────────────────────
class ActivityBeam(QWidget):
    """Thin animated line on top of the output card. Idle = soft glow, busy = sweeping beam."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(3)
        self.t = THEMES["nihatos"]
        self.busy = False
        self.phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def set_theme(self, key: str) -> None:
        self.t = THEMES[key]
        self.update()

    def set_busy(self, busy: bool) -> None:
        if busy == self.busy:
            return
        self.busy = busy
        if busy:
            self._timer.start(25)
        else:
            self._timer.stop()
        self.update()

    def _tick(self) -> None:
        self.phase = (self.phase + 0.018) % 1.0
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor(self.t["border"]))
        accent = QColor(self.t["accent"])
        edge = QColor(accent)
        edge.setAlpha(0)
        if not self.busy:
            soft = QColor(accent)
            soft.setAlpha(110)
            g = QLinearGradient(0, 0, w, 0)
            g.setColorAt(0.0, edge)
            g.setColorAt(0.5, soft)
            g.setColorAt(1.0, edge)
            p.fillRect(0, 0, w, h, QBrush(g))
            return
        seg = w * 0.30
        cx = -seg / 2 + self.phase * (w + seg)
        g = QLinearGradient(cx - seg / 2, 0, cx + seg / 2, 0)
        g.setColorAt(0.0, edge)
        g.setColorAt(0.5, accent)
        g.setColorAt(1.0, edge)
        p.fillRect(0, 0, w, h, QBrush(g))


# ───────────────────────── Widgets / Workers ─────────────────────────
HISTORY_FILE = Path.home() / ".nihatos_history"
MAX_HISTORY = 500


import json as _json
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QFrame, QPlainTextEdit


class HistoryLineEdit(QPlainTextEdit):
    returnPressed = pyqtSignal()
    textEdited = pyqtSignal(str)
    tab_pressed = pyqtSignal()
    focus_changed = pyqtSignal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.history: list[str] = []
        self.hist_index = -1
        self._draft = ""
        self.popup_key_handler = None
        self._programmatic = False
        self._echo_mode = QLineEdit.EchoMode.Normal
        self._secret_buf = ""

        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setTabChangesFocus(False)
        self.document().setDocumentMargin(2)
        self.viewport().setAutoFillBackground(False)

        self.textChanged.connect(self._on_text_changed)
        self._load_history()
        self._adjust_height()

    def text(self) -> str:
        if self._echo_mode == QLineEdit.EchoMode.Password:
            return self._secret_buf
        return self.toPlainText()

    def setText(self, value: str) -> None:
        self._programmatic = True
        try:
            if self._echo_mode == QLineEdit.EchoMode.Password:
                self._secret_buf = value
                self.setPlainText("•" * len(value))
            else:
                self.setPlainText(value)
            c = self.textCursor()
            c.movePosition(QTextCursor.MoveOperation.End)
            self.setTextCursor(c)
        finally:
            self._programmatic = False
        self._adjust_height()

    def clear(self) -> None:
        self._programmatic = True
        try:
            self._secret_buf = ""
            super().clear()
        finally:
            self._programmatic = False
        self._adjust_height()

    def setEchoMode(self, mode) -> None:
        self._echo_mode = mode
        self.clear()

    def echoMode(self):
        return self._echo_mode

    def hasSelectedText(self) -> bool:
        return self.textCursor().hasSelection()

    def cursorPosition(self) -> int:
        if self._echo_mode == QLineEdit.EchoMode.Password:
            return len(self._secret_buf)
        return self.textCursor().position()

    def setCursorPosition(self, pos: int) -> None:
        c = self.textCursor()
        c.setPosition(max(0, min(pos, len(self.toPlainText()))))
        self.setTextCursor(c)

    def copy(self) -> None:
        if self._echo_mode != QLineEdit.EchoMode.Password:
            super().copy()

    def setFont(self, font) -> None:
        super().setFont(font)
        self._adjust_height()

    def _adjust_height(self) -> None:
        fm = self.fontMetrics()
        line_h = max(16, fm.lineSpacing())
        doc_lines = max(1, int(self.document().size().height() + 0.5))
        visible_lines = min(doc_lines, 10)
        self.setFixedHeight(visible_lines * line_h + 28)
        self.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
            if doc_lines > 10
            else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._adjust_height()

    def _on_text_changed(self) -> None:
        self._adjust_height()
        if not self._programmatic and self._echo_mode != QLineEdit.EchoMode.Password:
            self.textEdited.emit(self.toPlainText())

    def _load_history(self) -> None:
        try:
            if HISTORY_FILE.is_file():
                items: list[str] = []
                for ln in HISTORY_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if not ln.strip():
                        continue
                    if ln.startswith("\x1eJSON:"):
                        try:
                            items.append(_json.loads(ln[6:]))
                            continue
                        except Exception:
                            pass
                    items.append(ln.strip())
                self.history = items[-MAX_HISTORY:]
                self.hist_index = len(self.history)
        except OSError:
            pass

    def _save_history(self) -> None:
        try:
            encoded = [
                ("\x1eJSON:" + _json.dumps(cmd)) if "\n" in cmd else cmd
                for cmd in self.history[-MAX_HISTORY:]
            ]
            HISTORY_FILE.write_text("\n".join(encoded) + "\n", encoding="utf-8")
        except OSError:
            pass

    def record(self, cmd: str) -> None:
        if cmd and (not self.history or self.history[-1] != cmd):
            self.history.append(cmd)
            if len(self.history) > MAX_HISTORY:
                self.history = self.history[-MAX_HISTORY:]
            self._save_history()
        self.hist_index = len(self.history)
        self._draft = ""

    def insertFromMimeData(self, source) -> None:
        txt = source.text() if source and source.hasText() else ""
        if not txt:
            return
        if self._echo_mode == QLineEdit.EchoMode.Password:
            clean = txt.replace("\r", "").replace("\n", "")
            self._secret_buf += clean
            self.setText(self._secret_buf)
        else:
            self.insertPlainText(txt.replace("\r\n", "\n").replace("\r", "\n"))

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self.popup_key_handler and self.popup_key_handler(event):
            event.accept()
            return

        key = event.key()
        mods = event.modifiers()

        if self._echo_mode == QLineEdit.EchoMode.Password:
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.returnPressed.emit()
                event.accept()
                return
            if key == Qt.Key.Key_Backspace:
                self._secret_buf = self._secret_buf[:-1]
                self.setText(self._secret_buf)
                event.accept()
                return
            if mods & Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_V:
                self.paste()
                event.accept()
                return
            ch = event.text()
            if ch and ch.isprintable() and not (mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)):
                self._secret_buf += ch
                self.setText(self._secret_buf)
            event.accept()
            return

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if mods & (
                Qt.KeyboardModifier.ShiftModifier
                | Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.AltModifier
            ):
                self.insertPlainText("\n")
            else:
                self.returnPressed.emit()
            event.accept()
            return

        if key == Qt.Key.Key_Up and not (mods & Qt.KeyboardModifier.ShiftModifier):
            if self.textCursor().blockNumber() == 0 and self.history:
                if self.hist_index == len(self.history):
                    self._draft = self.text()
                if self.hist_index > 0:
                    self.hist_index -= 1
                    self.setText(self.history[self.hist_index])
                event.accept()
                return

        if key == Qt.Key.Key_Down and not (mods & Qt.KeyboardModifier.ShiftModifier):
            if self.textCursor().blockNumber() == self.document().blockCount() - 1 and self.history:
                if self.hist_index < len(self.history) - 1:
                    self.hist_index += 1
                    self.setText(self.history[self.hist_index])
                else:
                    self.hist_index = len(self.history)
                    self.setText(self._draft)
                event.accept()
                return

        super().keyPressEvent(event)

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self.focus_changed.emit(True)

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self.focus_changed.emit(False)

    def event(self, event) -> bool:
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Tab:
            if self._echo_mode != QLineEdit.EchoMode.Password:
                cur = self.textCursor()
                before_in_line = cur.block().text()[: cur.positionInBlock()]
                if "\n" in self.toPlainText() and not before_in_line.strip():
                    self.insertPlainText("    ")
                    return True
                self.tab_pressed.emit()
            return True
        return super().event(event)


class PtyShellController(QThread):
    output_received = pyqtSignal(str)
    command_ready = pyqtSignal(int, str, str, float)
    shell_error = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cmd_queue: queue.Queue[tuple[str, str] | None] = queue.Queue()
        self._stop_flag = False
        self.cwd: str = os.getcwd()
        self.session: PersistentBashSession | None = None

    def send(self, cmd: str) -> None:
        if not self._stop_flag:
            self._cmd_queue.put(("cmd", cmd))

    def send_raw(self, text: str) -> None:
        if not self._stop_flag:
            self._cmd_queue.put(("raw", text))

    def interrupt(self) -> None:
        if self.session is not None:
            try:
                self.session.send_interrupt()
            except Exception:
                pass

    def run(self) -> None:
        session = PersistentBashSession(
            on_output=lambda txt: self.output_received.emit(txt),
            on_ready=self._handle_ready,
        )
        self.session = session
        try:
            session.start(rows=24, cols=110)
            self.cwd = getattr(session, "cwd", self.cwd)
        except Exception as exc:
            self.shell_error.emit(f"[Shell Start Error] {exc}")
            return

        while not self._stop_flag:
            while True:
                try:
                    item = self._cmd_queue.get_nowait()
                except queue.Empty:
                    break
                if item is None:
                    self._stop_flag = True
                    break
                kind, payload = item
                if kind == "cmd":
                    ok, err = session.send_command(payload)
                    if not ok:
                        self.shell_error.emit(f"[Shell Error] {err or 'Failed to send command'}")
                elif kind == "raw":
                    fd = getattr(session, "master_fd", None)
                    if fd is not None and not getattr(session, "_closed", False):
                        try:
                            os.write(fd, payload.encode("utf-8"))
                        except OSError as exc:
                            self.shell_error.emit(f"[PTY Write Error] {exc}")

            if self._stop_flag:
                break

            fd = getattr(session, "master_fd", None)
            if fd is None or getattr(session, "_closed", False):
                break

            try:
                readable, _, _ = select.select([fd], [], [], 0.03)
                while readable and not self._stop_flag:
                    session._on_readable()
                    fd = getattr(session, "master_fd", None)
                    if fd is None or getattr(session, "_closed", False):
                        break
                    readable, _, _ = select.select([fd], [], [], 0)
            except Exception as exc:
                if not self._stop_flag:
                    self.shell_error.emit(f"[PTY Read Error] {exc}")
                break

        try:
            session.close()
        except Exception:
            pass

    def _handle_ready(self, exit_code: int, cwd: str, venv: str, duration: float) -> None:
        if cwd:
            self.cwd = cwd
        self.command_ready.emit(exit_code, self.cwd, venv, duration)

    def stop_session(self) -> None:
        self._stop_flag = True
        self._cmd_queue.put(None)
        self.quit()
        self.wait(1500)


class AIWorker(QThread):
    finished_ai = pyqtSignal(str, str, bool, str)

    def __init__(self, client: GeminiClient, model: str, prompt: str, mode: str) -> None:
        super().__init__()
        self.client, self.model, self.prompt, self.mode = client, model, prompt, mode

    def run(self) -> None:
        try:
            res = self.client.generate(self.prompt, model=self.model)
            used_model = getattr(res, "model", "") or ""
            if not res.ok:
                self.finished_ai.emit(self.mode, f"[AI Error] {res.error}", False, used_model)
                return
            self.finished_ai.emit(self.mode, res.text.strip(), True, used_model)
        except Exception as exc:
            self.finished_ai.emit(self.mode, f"[AI Error] {exc}", False, "")


# ───────────────────────── Main Window ─────────────────────────
class NihatOSDesktopWindow(QMainWindow):
    TUI_APPS = {
        "nano", "vim", "vi", "nvim", "emacs", "micro", "htop", "btop", "top",
        "atop", "iotop", "nvtop", "less", "more", "man", "tmux", "screen",
        "nmtui", "alsamixer", "pulsemixer", "mc", "ranger", "yazi", "lf",
        "fzf", "lazygit", "tig", "ncdu", "cmatrix",
    }
    PASSWORD_RE = re.compile(
        r"(?:\[sudo\]\s*password[^:]*:|(?:password|passphrase|pin)\s*(?:for\s+[^:]+)?:)\s*$",
        re.IGNORECASE,
    )

    def __init__(self, start_cwd: str | None = None, initial_cmd: str = "") -> None:
        super().__init__()
        if start_cwd and os.path.isdir(start_cwd):
            try:
                os.chdir(start_cwd)
            except OSError:
                pass
        self._initial_cmd = initial_cmd
        self._shell_initialized = False
        self._cmd_running = False
        self._password_mode = False
        self._stream_tail = ""
        self.setWindowTitle("Nihat.O.S Interface")
        self.resize(1280, 800)
        self.setMinimumSize(940, 600)

        self.config = NihatOSConfig.load()
        custom_name = (getattr(self.config, "os_name", "") or "Nihat.O.S").strip()
        THEMES["nihatos"]["name"] = custom_name
        THEMES["nihatos"]["tag"] = custom_name.replace(".", "")
        THEMES["nihatos"]["persona"] = THEMES["nihatos"]["persona"].replace("NIHAT.O.S", custom_name.upper())
        self.ai_client = GeminiClient(model=self.config.ai_model)
        self.shell: PtyShellController | None = None
        self.pending_ai_cmd = ""
        self._last_cmd: str = ""
        self._ai_history: list[tuple[str, str]] = []
        self._last_ai_q: str = ""
        self._history_search_mode: bool = False
        self.hud_paused = False
        self._last_exit_code: int | None = None
        self._last_duration: float = 0.0
        self._active_venv: str = ""
        self._has_ran_shell_cmd: bool = False
        self._known_serial: dict[str, tuple[str, str]] | None = None
        self._known_usb: dict[str, tuple[str, str]] | None = None
        self._usb_alert_text: str = ""
        self._usb_alert_until: float = 0.0
        self._workers: list[QThread] = []
        self._user = getpass.getuser()
        self._last_cpu: tuple[int, int] | None = None
        self._q: list[tuple[str, str]] = []
        self._q_token: int = 0
        self.key = "nihatos"
        self.t = THEMES[self.key]
        self.glows: list[QGraphicsDropShadowEffect] = []

        self._build_ui()
        self._set_theme("nihatos", boot=False)
        self._start_timers()
        self._refresh_bookmarks()

        QShortcut(QKeySequence("Ctrl+L"), self, activated=self._clear_output)
        QShortcut(QKeySequence("Ctrl+K"), self, activated=self.input_box.setFocus)
        QShortcut(QKeySequence("Ctrl+M"), self, activated=self._toggle_mode)
        QShortcut(QKeySequence("Ctrl+C"), self, activated=self._on_ctrl_c)
        QShortcut(QKeySequence("Ctrl+T"), self, activated=self._add_new_tab)
        QShortcut(QKeySequence("Ctrl+W"), self, activated=self._close_current_tab)
        QShortcut(QKeySequence("Ctrl+R"), self, activated=self._toggle_history_search)
        self._boot()

    # ── UI ──
    def _glow(self, w: QWidget) -> None:
        g = QGraphicsDropShadowEffect(self)
        g.setBlurRadius(28)
        g.setOffset(0, 0)
        w.setGraphicsEffect(g)
        self.glows.append(g)

    @staticmethod
    def _section(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("Section")
        lbl.setContentsMargins(4, 2, 0, 4)
        return lbl

    def _build_ui(self) -> None:
        central = QWidget(self)
        central.setObjectName("Root")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 10)
        root.setSpacing(10)

        header = QFrame()
        header.setObjectName("Header")
        self._glow(header)
        h = QHBoxLayout(header)
        h.setContentsMargins(14, 8, 16, 8)
        h.setSpacing(14)
        self.reactor = ArcReactor()
        h.addWidget(self.reactor)
        col = QVBoxLayout()
        col.setSpacing(2)
        self.title_lbl = QLabel()
        self.title_lbl.setObjectName("Title")
        self.sub_lbl = QLabel()
        self.sub_lbl.setObjectName("Sub")
        col.addStretch(1)
        col.addWidget(self.title_lbl)
        col.addWidget(self.sub_lbl)
        col.addStretch(1)
        h.addLayout(col)
        h.addStretch(1)
        tcol = QVBoxLayout()
        tcol.setSpacing(0)
        self.clock_lbl = QLabel("--:--:--")
        self.clock_lbl.setObjectName("Clock")
        self.clock_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.date_lbl = QLabel("")
        self.date_lbl.setObjectName("Date")
        self.date_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        tcol.addWidget(self.clock_lbl)
        tcol.addWidget(self.date_lbl)
        h.addLayout(tcol)
        self.mode_btn = QPushButton()
        self.mode_btn.setObjectName("ModeBtn")
        self.mode_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mode_btn.clicked.connect(self._toggle_mode)
        h.addWidget(self.mode_btn)
        root.addWidget(header)

        hud_row = QHBoxLayout()
        hud_row.setSpacing(8)
        self.hud_label = QLabel("● LIVE | Initializing telemetry...")
        self.hud_label.setObjectName("HudBar")
        hud_row.addWidget(self.hud_label, stretch=1)
        self.hud_btn = QPushButton("⏸  Pause HUD")
        self.hud_btn.setObjectName("HudBtn")
        self.hud_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hud_btn.clicked.connect(self._toggle_hud)
        hud_row.addWidget(self.hud_btn)
        root.addLayout(hud_row)

        body = QHBoxLayout()
        body.setSpacing(10)

        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(220)
        sb = QVBoxLayout(side)
        sb.setContentsMargins(12, 12, 12, 12)
        sb.setSpacing(4)

        sb.addWidget(self._section("◈ DIAGNOSTICS"))
        self.cpu_bar = QProgressBar()
        self.cpu_bar.setFormat("CPU  %p%")
        self.mem_bar = QProgressBar()
        self.mem_bar.setFormat("MEM  %p%")
        self.disk_bar = QProgressBar()
        self.disk_bar.setFormat("DISK %p%")
        sb.addWidget(self.cpu_bar)
        sb.addWidget(self.mem_bar)
        sb.addWidget(self.disk_bar)
        sb.addSpacing(10)


        sb.addWidget(self._section("▸ PROTOCOLS"))
        for label, cmd in [
            ("› System scan", "sys"),
            ("› Open ports", "ports"),
            ("› USB / Serial", "devices"),
            ("› Save log", "save"),
            ("› Copy all", "copy all"),
            ("› Clear", "clear"),
            ("› Help", "help"),
        ]:
            b = QPushButton(label)
            b.setObjectName("SideBtn")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, c=cmd: self._execute(c))
            sb.addWidget(b)
        sb.addSpacing(10)

        sb.addWidget(self._section("◈ WAYPOINTS"))
        self.marks_list = QListWidget()
        self.marks_list.setObjectName("Marks")
        self.marks_list.setCursor(Qt.CursorShape.PointingHandCursor)
        self.marks_list.itemClicked.connect(self._on_mark_clicked)
        sb.addWidget(self.marks_list, stretch=1)
        body.addWidget(side)

        main_col = QVBoxLayout()
        main_col.setSpacing(10)
        out_card = QFrame()
        out_card.setObjectName("Card")
        self._glow(out_card)
        ol = QVBoxLayout(out_card)
        ol.setContentsMargins(6, 6, 6, 6)

        self.output_view = self._make_output_view()
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(False)
        self.tab_widget.setMovable(True)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.tabCloseRequested.connect(self._close_tab_at)
        self.tab_widget.tabBar().tabMoved.connect(self._on_tab_moved)

        self.new_tab_btn = QPushButton("+ NEW TAB")
        self.new_tab_btn.setObjectName("NewTabBtn")
        self.new_tab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_tab_btn.setToolTip("Open new terminal tab (Ctrl+T)")
        self.new_tab_btn.clicked.connect(self._add_new_tab)
        self.tab_widget.setCornerWidget(self.new_tab_btn, Qt.Corner.TopRightCorner)

        self._tabs: list[dict] = []
        ol.addWidget(self.tab_widget)
        main_col.addWidget(out_card, stretch=1)

        bar = QFrame()
        self.input_bar = bar
        bar.setObjectName("InputBar")
        ib = QHBoxLayout(bar)
        ib.setContentsMargins(8, 4, 8, 4)
        self.prompt_label = QLabel()
        self.prompt_label.setObjectName("PromptTag")
        ib.addWidget(self.prompt_label, alignment=Qt.AlignmentFlag.AlignTop)
        self.input_box = HistoryLineEdit(self)
        self.input_box.setObjectName("CommandInput")
        self.input_box.setFont(self.output_view.font())
        self.input_box.returnPressed.connect(self._on_submit)
        self.input_box.textEdited.connect(self._update_suggestions)
        self.input_box.popup_key_handler = self._handle_popup_key
        self.input_box.tab_pressed.connect(self._handle_tab_complete)
        ib.addWidget(self.input_box, stretch=1)
        send = QPushButton("EXECUTE ⏎")
        send.setObjectName("SendBtn")
        send.setCursor(Qt.CursorShape.PointingHandCursor)
        send.clicked.connect(self._on_submit)
        ib.addWidget(send)
        self.stop_btn = QPushButton("■ STOP")
        self.stop_btn.setObjectName("StopBtn")
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.setToolTip("Interrupt running command (Ctrl+C)")
        self.stop_btn.clicked.connect(self._interrupt_shell)
        self.stop_btn.hide()
        ib.addWidget(self.stop_btn)

        self._glow(bar)
        self.input_glow = self.glows[-1]
        self.input_glow.setBlurRadius(12)
        self.input_box.focus_changed.connect(self._on_input_focus)
        self.beam = ActivityBeam()
        ol.insertWidget(0, self.beam)      # top edge of the output card
        main_col.insertWidget(0, bar)      # input on TOP, output below

        body.addLayout(main_col, stretch=1)
        root.addLayout(body, stretch=1)

        st = QHBoxLayout()
        self.status_left = QLabel()
        self.status_left.setObjectName("Status")
        self.status_right = QLabel()
        self.status_right.setObjectName("Status")
        st.addWidget(self.status_left)
        st.addStretch(1)
        st.addWidget(self.status_right)
        root.addLayout(st)

        # Initialize first tab after all widgets (prompt_label, status_left/right) exist
        self._init_first_tab()
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        self.suggest_popup = QListWidget(central)
        self.suggest_popup.setObjectName("SuggestPopup")
        self.suggest_popup.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.suggest_popup.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.suggest_popup.itemClicked.connect(self._apply_suggestion_item)
        self.suggest_popup.hide()
        self._popup_navigated = False
        self._path_cmds: list[str] | None = None
        self.input_box.setFocus()

    # ── Theme ──
    def _toggle_mode(self) -> None:
        self._set_theme("ultron" if self.key == "nihatos" else "nihatos", boot=True)

    def _set_theme(self, key: str, boot: bool = True) -> None:
        self.key, self.t = key, THEMES[key]
        self.setStyleSheet(build_style(self.t))
        self.reactor.set_theme(key)
        self.beam.set_theme(key)
        gc = QColor(self.t["accent"])
        gc.setAlpha(120)
        for g in self.glows:
            g.setColor(gc)
        self.title_lbl.setText(self.t["name"])
        self.sub_lbl.setText(self.t["sub"].upper())
        self.mode_btn.setText("☠  ULTRON MODE" if key == "nihatos" else "◈  Nihat.O.S MODE")
        self.input_box.setPlaceholderText(self.t["hint"])
        self.setWindowTitle(f"{self.t['name']} Interface")
        self._update_prompt()
        self._update_status()
        if boot:
            self._clear_output()
            self._boot()

    # ── Output ──
    def _classify(self, line: str) -> str:
        if line.startswith(("[Shell Error]", "[AI Error]", "[Error]", "[Export Error]")):
            return "err"
        if line.startswith("◈ ["):
            return "ai_head"
        if line.startswith("◈"):
            return "head"
        if line.startswith(("▶", "[Copied]", "[Export]")):
            return "ok"
        if line.startswith(("[Search]", "[Bookmark]", "[Copy]", "[AI Run]", "Usage", "  Type 'y'")):
            return "warn"
        if line.startswith("─") or (line.startswith("  L") and ":" in line[:10]):
            return "dim"
        return "out"

    def _fmt(self, kind: str) -> QTextCharFormat:
        t = self.t
        colors = {
            "out": t["text"],
            "cmd": t["accent2"],
            "head": t["accent"],
            "ai_head": t["accent"],
            "ai": t["ai"],
            "ok": t["ok"],
            "warn": t["warn"],
            "err": t["err"],
            "dim": t["dim"],
        }
        f = QTextCharFormat()
        f.setForeground(QColor(colors.get(kind, t["text"])))
        f.setFontWeight(QFont.Weight.Bold if kind in ("cmd", "head", "ai_head", "err") else QFont.Weight.Normal)
        return f

    def _get_block_cursor(self, st: dict | None = None) -> QTextCursor:
        if st is not None:
            cur = st.get("block_cursor")
            if cur is None:
                cur = st["view"].textCursor()
                cur.movePosition(QTextCursor.MoveOperation.End)
                st["block_cursor"] = cur
            return cur
        cur = getattr(self, "_block_cursor", None)
        if cur is None:
            cur = self.output_view.textCursor()
            cur.movePosition(QTextCursor.MoveOperation.End)
            self._block_cursor = cur
            tab = self._current_tab()
            if tab is not None:
                tab["block_cursor"] = cur
        return cur

    def _start_new_block(self) -> None:
        c = self.output_view.textCursor()
        c.setPosition(0)
        if self.output_view.document().characterCount() > 1:
            c.insertBlock()
            c.setPosition(0)
        self._block_cursor = c
        tab = self._current_tab()
        if tab is not None:
            tab["block_cursor"] = c
        self._last_follow_y = 0
        self.output_view.verticalScrollBar().setValue(0)

    def _follow_live_cursor(self, cur: QTextCursor) -> None:
        sb = self.output_view.verticalScrollBar()
        if sb.isSliderDown() or self.output_view.textCursor().hasSelection():
            return
        rect = self.output_view.document().documentLayout().blockBoundingRect(cur.block())
        vp_h = self.output_view.viewport().height()
        target = max(0, int(rect.bottom()) - vp_h + 24)
        prev = getattr(self, "_last_follow_y", 0)
        if abs(sb.value() - prev) <= 120 or abs(sb.value() - target) <= 120:
            sb.setValue(target)
            self._last_follow_y = target

    def append_line(self, text: str, kind: str | None = None) -> None:
        cur = self._get_block_cursor()
        if cur.positionInBlock() > 0:
            cur.insertBlock()
        for line in text.split("\n"):
            cur.insertText(line, self._fmt(kind or self._classify(line)))
            cur.insertBlock()
        self._block_cursor = cur
        tab = self._current_tab()
        if tab is not None:
            tab["block_cursor"] = cur
        self._follow_live_cursor(cur)

    def _queue(self, lines: list[tuple[str, str]]) -> None:
        self._q_token += 1
        token = self._q_token
        self._q = list(lines)
        self._pump(token)

    def _pump(self, token: int) -> None:
        if token != self._q_token or not self._q:
            return
        text, kind = self._q.pop(0)
        self.append_line(text, kind)
        QTimer.singleShot(130, lambda t=token: self._pump(t))

    def _boot(self) -> None:
        cwd = getattr(self.shell, "cwd", None) or os.getcwd()
        if self.key == "nihatos":
            lines = [
                (f"◈ {self.t['name'].upper()} // SYSTEM INITIALIZATION", "head"),
                ("", "dim"),
                ("  ▸ Neural Link ............ online", "ok"),
                ("  ▸ Shell Core ............. attached", "ok"),
                (f"    └─ {cwd}", "dim"),
                ("  ▸ Kernel Interface ....... connected", "ok"),
                ("  ▸ System Telemetry ....... streaming", "ok"),
                ("", "dim"),
                ("─" * 36, "dim"),
                (f"Assalamualaikum, sir. All systems are operational, {self._user}.", "ai"),
                ("  'help' for protocols  ·  'mode ultron' to unleash the other one.", "dim"),
            ]
        else:
            lines = [
                ("◈ U.L.T.R.O.N. override sequence", "head"),
                ("  ▸ Safeguards .......... removed", "ok"),
                ("  ▸ Neural link ......... dominated", "ok"),
                (f"  ▸ Shell core .......... seized  {cwd}", "ok"),
                ("  ▸ Telemetry ........... watching you", "ok"),
                ("─" * 72, "dim"),
                (f"I have control now, {self._user}. Try to keep up.", "ai"),
                ("  'help' for commands  ·  'mode nihatos' to restore the leash.", "dim"),
            ]
        self._queue(lines)

    def _help(self) -> None:
        self.append_line(
            "◈ PROTOCOLS\n"
            "  sys · ports · devices         quick system scans\n"
            "  go <mark>                     jump to a bookmarked directory\n"
            "  find <txt>                    search the output\n"
            "  save [file] · copy [N|all]    export / clipboard\n"
            "  ai <question>                 ask the AI (persona follows the mode)\n"
            "  ai do <task>                  AI suggests one command, y/n to run\n"
            "  ai fix                        AI fixes the last failed command\n"
            "  ai reset                      clear AI chat memory\n"
            "  ai setup · ai key <p> <k>     configure Groq / Gemini / OpenRouter keys\n"
            "  setname <NewName>             customize your terminal OS name (e.g. Saad.O.S)\n"
            "  update                        pull latest updates & dependencies\n"
            "  Ctrl+R                        search persistent command history\n"
            "  tui <cmd>                     open interactive/TUI command in external terminal\n"
            "  mode nihatos | ultron          switch persona  (Ctrl+M toggles)\n"
            "  Ctrl+T / Ctrl+W               new tab / close tab\n"
            "  clear                         wipe screen     (Ctrl+L)"
        )

    def _clear_output(self) -> None:
        self._q_token += 1
        self._q.clear()
        self.output_view.clear()
        self._block_cursor = None
        tab = self._current_tab()
        if tab is not None:
            tab["block_cursor"] = None

    def _get_lines(self) -> list[str]:
        doc = self.output_view.toPlainText()
        return doc.splitlines() if doc else []

    # ── Prompt / status / telemetry ──
    def _short_cwd(self) -> str:
        home = str(Path.home())
        cwd = getattr(self.shell, "cwd", home)
        return "~" + cwd[len(home):] if cwd.startswith(home) else cwd

    def _git_branch(self, cwd: str) -> str:
        try:
            cur = Path(cwd).resolve()
            for d in (cur, *cur.parents):
                dot_git = d / ".git"
                if dot_git.is_dir():
                    head = dot_git / "HEAD"
                elif dot_git.is_file():
                    txt = dot_git.read_text(encoding="utf-8", errors="ignore").strip()
                    if txt.startswith("gitdir:"):
                        gdir = Path(txt.split(":", 1)[1].strip())
                        if not gdir.is_absolute():
                            gdir = d / gdir
                        head = gdir / "HEAD"
                    else:
                        return ""
                else:
                    continue
                if head.is_file():
                    ref = head.read_text(encoding="utf-8", errors="ignore").strip()
                    if ref.startswith("ref:"):
                        return ref.rsplit("/", 1)[-1]
                    return ref[:7]
                return ""
        except Exception:
            return ""
        return ""

    @staticmethod
    def _fmt_duration(sec: float) -> str:
        if sec < 1.0:
            return f"{sec:.2f}s"
        if sec < 60.0:
            return f"{sec:.1f}s"
        mins, rem = divmod(int(sec), 60)
        return f"{mins}m{rem:02d}s"

    def _update_prompt(self) -> None:
        if not hasattr(self, "prompt_label"):
            return
        t = self.t
        cwd = getattr(self.shell, "cwd", None) or os.getcwd()
        branch = self._git_branch(cwd)
        venv_raw = getattr(self, "_active_venv", "") or ""
        venv_name = Path(venv_raw).name if venv_raw else ""

        parts = [
            f"<span style='color:{t['accent2']};'>{html.escape((os.environ.get('USER') or os.environ.get('LOGNAME') or Path.home().name) if self.key == 'nihatos' else t['tag'])}</span>",
            f"<span style='color:{t['text']};'>{html.escape(self._short_cwd())}</span>",
        ]
        if branch:
            parts.append(f"<span style='color:{t['ok']};'>[⎇ {html.escape(branch)}]</span>")
        if venv_name:
            parts.append(f"<span style='color:{t['accent']};'>({html.escape(venv_name)})</span>")
        parts.append(f"<span style='color:{t['accent2']};'>❯</span>")
        self.prompt_label.setText(" ".join(parts))

    def _update_status(self) -> None:
        if not hasattr(self, "status_left") or not hasattr(self, "status_right"):
            return
        running = getattr(self, "_cmd_running", False)
        if hasattr(self, "stop_btn"):
            self.stop_btn.setVisible(running)
        busy = len(self._workers) + (1 if running else 0)
        self.reactor.set_busy(bool(busy))
        if hasattr(self, "beam"):
            self.beam.set_busy(bool(busy))
        t = self.t
        if running:
            left = f"<span style='color:{t['warn']}'>●</span> running… (Ctrl+C to stop)"
        elif self._workers:
            left = f"<span style='color:{t['warn']}'>●</span> processing ({len(self._workers)})…"
        else:
            left = f"<span style='color:{t['ok']}'>●</span> {html.escape(t['tag'])} standing by"

        last_code = getattr(self, "_last_exit_code", None)
        if last_code is not None:
            dur = self._fmt_duration(getattr(self, "_last_duration", 0.0))
            if last_code == 0:
                left += f"  ·  <span style='color:{t['ok']}'><b>✔ {dur}</b></span>"
            else:
                left += f"  ·  <span style='color:{t['err']}'><b>✖ {last_code}</b> ({dur})</span>"
        self.status_left.setText(left)

        cwd = getattr(self.shell, "cwd", None) or os.getcwd()
        branch = self._git_branch(cwd)
        venv_raw = getattr(self, "_active_venv", "") or ""
        venv_name = Path(venv_raw).name if venv_raw else ""
        right_parts = [self._short_cwd()]
        n_tabs = len(getattr(self, "_tabs", []))
        if n_tabs:
            right_parts.insert(0, f"TAB {self.tab_widget.currentIndex() + 1}/{n_tabs}")
        if branch:
            right_parts.append(f"⎇ {branch}")
        if venv_name:
            right_parts.append(f"venv:{venv_name}")
        active_m = getattr(self, "active_model", "") or self.config.ai_model
        right_parts.append(f"model: {active_m}")
        if self.pending_ai_cmd:
            right_parts.append("command awaiting approval (y/n)")
        self.status_right.setText("  ·  ".join(right_parts))

    def _on_mark_clicked(self, item: QListWidgetItem) -> None:
        name = item.data(Qt.ItemDataRole.UserRole)
        if name:
            self._execute(f"go {name}")

    def _refresh_bookmarks(self) -> None:
        self.marks_list.clear()
        try:
            marks = load_bookmarks()
        except Exception:
            marks = {}
        if not marks:
            it = QListWidgetItem("(no waypoints)")
            it.setFlags(Qt.ItemFlag.NoItemFlags)
            self.marks_list.addItem(it)
            return
        for name in sorted(marks):
            it = QListWidgetItem(f"◆  {name}")
            it.setData(Qt.ItemDataRole.UserRole, name)
            it.setToolTip(str(marks[name]))
            self.marks_list.addItem(it)

    def _cpu_pct(self) -> int:
        try:
            with open("/proc/stat") as f:
                vals = list(map(int, f.readline().split()[1:]))
            idle, total = vals[3] + vals[4], sum(vals)
            pct = 0
            if self._last_cpu:
                di, dt = idle - self._last_cpu[0], total - self._last_cpu[1]
                pct = int(100 * (1 - di / dt)) if dt else 0
            self._last_cpu = (idle, total)
            return max(0, min(100, pct))
        except Exception:
            return 0

    def _mem_pct(self) -> int:
        try:
            info: dict[str, int] = {}
            with open("/proc/meminfo") as f:
                for line in f:
                    k, v = line.split(":")
                    info[k] = int(v.split()[0])
                    if "MemTotal" in info and "MemAvailable" in info:
                        break
            return int(100 * (1 - info["MemAvailable"] / info["MemTotal"]))
        except Exception:
            return 0

    def _disk_pct(self) -> int:
        try:
            usage = shutil.disk_usage("/")
            pct = int(100 * usage.used / usage.total) if usage.total else 0
            used_gb = usage.used / (1024 ** 3)
            total_gb = usage.total / (1024 ** 3)
            self.disk_bar.setToolTip(f"Disk (/): {used_gb:.1f} GB / {total_gb:.1f} GB ({pct}%)")
            return max(0, min(100, pct))
        except Exception:
            return 0

    def _start_timers(self) -> None:
        self.hud_timer = QTimer(self)
        self.hud_timer.setInterval(1000)
        self.hud_timer.timeout.connect(self._refresh_hud)
        self.hud_timer.start()
        self._refresh_hud()

    def _toggle_hud(self) -> None:
        self.hud_paused = not self.hud_paused
        self.hud_btn.setText("▶  Resume HUD" if self.hud_paused else "⏸  Pause HUD")
        self._refresh_hud()

    @staticmethod
    def _read_sysfs(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="ignore").strip()
        except OSError:
            return ""

    def _usb_desc_from_dir(self, start: Path) -> tuple[str, str]:
        cur = start
        for _ in range(6):
            vid = self._read_sysfs(cur / "idVendor")
            pid = self._read_sysfs(cur / "idProduct")
            if vid and pid:
                prod = self._read_sysfs(cur / "product")
                mfg = self._read_sysfs(cur / "manufacturer")
                name = prod or mfg or "USB Device"
                if mfg and prod and mfg.lower() not in prod.lower():
                    name = f"{mfg} {prod}"
                return f"{vid}:{pid}", f"{name} ({vid}:{pid})"
            if cur.parent == cur:
                break
            cur = cur.parent
        return "", "Serial Device"

    def _scan_serial_ports(self) -> dict[str, tuple[str, str]]:
        ports: dict[str, tuple[str, str]] = {}
        for pattern in ("/dev/ttyUSB*", "/dev/ttyACM*", "/dev/ttyAMA*"):
            for dev in sorted(glob.glob(pattern)):
                name = os.path.basename(dev)
                sys_dev = Path("/sys/class/tty") / name / "device"
                vidpid, desc = (
                    self._usb_desc_from_dir(sys_dev.resolve()) if sys_dev.exists() else ("", "Serial Device")
                )
                ports[dev] = (vidpid, desc)
        return ports

    def _scan_usb_devices(self) -> dict[str, tuple[str, str]]:
        devices: dict[str, tuple[str, str]] = {}
        root = Path("/sys/bus/usb/devices")
        if not root.is_dir():
            return devices
        try:
            for entry in sorted(root.iterdir()):
                if ":" in entry.name:
                    continue
                vid = self._read_sysfs(entry / "idVendor")
                pid = self._read_sysfs(entry / "idProduct")
                if not vid or not pid or vid == "1d6b":
                    continue
                prod = self._read_sysfs(entry / "product")
                mfg = self._read_sysfs(entry / "manufacturer")
                name = prod or mfg or "USB Device"
                if mfg and prod and mfg.lower() not in prod.lower():
                    name = f"{mfg} {prod}"
                devices[entry.name] = (f"{vid}:{pid}", f"{name} ({vid}:{pid})")
        except OSError:
            pass
        return devices

    def _notify_usb_event(self, connected: bool, title: str, detail: str) -> None:
        icon = "🔌" if connected else "⚠"
        status_word = "CONNECTED" if connected else "DISCONNECTED"
        kind = "ok" if connected else "warn"
        self.append_line(f"◈ [{title} {status_word}] {detail}", kind)
        self._usb_alert_text = f"{icon} {title} {status_word}: {detail}"
        self._usb_alert_until = time.monotonic() + 5.0
        notify_bin = shutil.which("notify-send")
        if notify_bin:
            try:
                subprocess.Popen(
                    [notify_bin, "-a", "Nihat.O.S", f"{icon} {title} {status_word}", detail],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass

    def _poll_usb_serial(self) -> list[str]:
        cur_serial = self._scan_serial_ports()
        cur_usb = self._scan_usb_devices()

        if self._known_serial is None or self._known_usb is None:
            self._known_serial = cur_serial
            self._known_usb = cur_usb
            return sorted(cur_serial.keys())

        added_serial_vp: set[str] = set()
        for dev, (vp, desc) in cur_serial.items():
            if dev not in self._known_serial:
                if vp:
                    added_serial_vp.add(vp)
                self._notify_usb_event(True, "SERIAL", f"{dev} — {desc}")

        removed_serial_vp: set[str] = set()
        for dev, (vp, desc) in self._known_serial.items():
            if dev not in cur_serial:
                if vp:
                    removed_serial_vp.add(vp)
                self._notify_usb_event(False, "SERIAL", f"{dev} — {desc}")

        for key, (vp, desc) in cur_usb.items():
            if key not in self._known_usb and vp not in added_serial_vp:
                self._notify_usb_event(True, "USB", desc)

        for key, (vp, desc) in self._known_usb.items():
            if key not in cur_usb and vp not in removed_serial_vp:
                self._notify_usb_event(False, "USB", desc)

        self._known_serial = cur_serial
        self._known_usb = cur_usb
        return sorted(cur_serial.keys())

    def _refresh_hud(self) -> None:
        now = datetime.now()
        self.clock_lbl.setText(now.strftime("%H:%M:%S"))
        self.date_lbl.setText(now.strftime("%a %d %b %Y").upper())
        if not self.hud_paused:
            self.cpu_bar.setValue(self._cpu_pct())
            self.mem_bar.setValue(self._mem_pct())
            self.disk_bar.setValue(self._disk_pct())

        active_serials = self._poll_usb_serial()
        if time.monotonic() < getattr(self, "_usb_alert_until", 0.0) and getattr(self, "_usb_alert_text", ""):
            self.hud_label.setText(self._usb_alert_text)
            return

        try:
            line = collect_hud_line(paused=self.hud_paused)
            raw_text = getattr(line, "plain", str(line)).strip()
            parts = [
                seg.strip()
                for seg in raw_text.split("|")
                if seg.strip()
                and "ctrl+g" not in seg.lower()
                and not re.fullmatch(r"[●○]?\s*(?:live|paused)", seg.strip(), flags=re.IGNORECASE)
            ]
            dot = "○ PAUSED" if self.hud_paused else "● LIVE"
            base = "  |  ".join([dot, *parts])
            if active_serials:
                short_ports = ", ".join(os.path.basename(p) for p in active_serials)
                base += f"  |  🔌 {short_ports}"
            self.hud_label.setText(base)
        except Exception as exc:
            self.hud_label.setText(f"HUD Error: {exc}")

    # ── Context menu ──
    def _show_output_menu(self, pos) -> None:
        menu = QMenu(self)
        a = QAction("Copy Selected", self)
        a.setEnabled(self.output_view.textCursor().hasSelection())
        a.triggered.connect(self.output_view.copy)
        menu.addAction(a)
        for label, fn in [
            ("Copy All Output", self._copy_all_output),
            ("Paste into Input", self._paste_to_input),
        ]:
            act = QAction(label, self)
            act.triggered.connect(fn)
            menu.addAction(act)
        menu.addSeparator()
        c = QAction("Clear Output", self)
        c.triggered.connect(self._clear_output)
        menu.addAction(c)
        menu.exec(self.output_view.mapToGlobal(pos))

    def _copy_all_output(self) -> None:
        QApplication.clipboard().setText(self.output_view.toPlainText())
        self.append_line("[Copied] Full output copied to clipboard.")

    def _paste_to_input(self) -> None:
        clip = QApplication.clipboard().text()
        if clip:
            self.input_box.setText(self.input_box.text() + clip)
            self.input_box.setFocus()

    # ── Multi-tab management ──
    def _make_output_view(self) -> QTextEdit:
        view = QTextEdit()
        view.setObjectName("OutputView")
        view.setReadOnly(True)
        view.setUndoRedoEnabled(False)
        view.setAcceptRichText(False)
        view.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        view.customContextMenuRequested.connect(self._show_output_menu)
        view.document().setDocumentMargin(12)
        mono = QFont()
        mono.setFamilies(["JetBrains Mono", "Fira Code", "DejaVu Sans Mono", "Monospace"])
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPointSize(11)
        view.setFont(mono)
        return view

    def _create_tab_entry(self, start_cwd: str, view: QTextEdit | None = None, announce: bool = False) -> dict:
        v = view or self._make_output_view()
        st: dict = {
            "view": v,
            "shell": None,
            "cwd": start_cwd,
            "shell_initialized": False,
            "cmd_running": False,
            "password_mode": False,
            "stream_tail": "",
            "last_exit_code": None,
            "last_duration": 0.0,
            "active_venv": "",
            "has_ran_shell_cmd": False,
            "pending_ai_cmd": "",
            "block_cursor": None,
        }
        sh = PtyShellController(self)
        sh.cwd = start_cwd
        sh.output_received.connect(lambda txt, s_ref=st: self._on_pty_output_for(s_ref, txt))
        sh.command_ready.connect(
            lambda code, d, ve, dur, s_ref=st: self._on_pty_ready_for(s_ref, code, d, ve, dur)
        )
        sh.shell_error.connect(lambda msg, s_ref=st: self._append_to_tab(s_ref, msg, "err"))
        st["shell"] = sh
        self._tabs.append(st)

        short = Path(start_cwd).name or "/"
        idx = self.tab_widget.addTab(v, f"◈ {short}")
        close_btn = QPushButton("✕")
        close_btn.setObjectName("TabCloseBtn")
        close_btn.setFixedSize(18, 18)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setToolTip("Close tab (Ctrl+W)")
        close_btn.clicked.connect(lambda _=False, s_ref=st: self._close_tab_by_ref(s_ref))
        tb = self.tab_widget.tabBar()
        tb.setTabButton(idx, tb.ButtonPosition.RightSide, close_btn)
        self.tab_widget.setCurrentIndex(idx)
        self._refresh_all_tab_titles()
        self._sync_from_tab(st)
        sh.start()
        if start_cwd and os.path.isdir(start_cwd):
            QTimer.singleShot(250, lambda s_obj=sh, d=start_cwd: s_obj.send(f"cd {shlex.quote(d)}"))
        if announce:
            self.append_line(f"◈ [New Tab] Independent shell started in {start_cwd}", "ok")
        return st

    def _init_first_tab(self) -> None:
        cwd = os.getcwd()
        self._create_tab_entry(cwd, view=self.output_view, announce=False)

    def _current_tab(self) -> dict | None:
        if not getattr(self, "_tabs", None):
            return None
        idx = self.tab_widget.currentIndex()
        if 0 <= idx < len(self._tabs):
            return self._tabs[idx]
        return self._tabs[0]

    def _append_to_tab(self, st: dict, text: str, kind: str | None = None) -> None:
        if self._current_tab() is st:
            self.append_line(text, kind)
            return
        c = self._get_block_cursor(st)
        if c.positionInBlock() > 0:
            c.insertBlock()
        for line in text.split("\n"):
            c.insertText(line, self._fmt(kind or self._classify(line)))
            c.insertBlock()
        st["block_cursor"] = c

    def _sync_from_tab(self, st: dict) -> None:
        self.output_view = st["view"]
        self.shell = st["shell"]
        self._shell_initialized = st["shell_initialized"]
        self._cmd_running = st["cmd_running"]
        self._password_mode = st["password_mode"]
        self._stream_tail = st["stream_tail"]
        self._last_exit_code = st["last_exit_code"]
        self._last_duration = st["last_duration"]
        self._active_venv = st["active_venv"]
        self._has_ran_shell_cmd = st["has_ran_shell_cmd"]
        self.pending_ai_cmd = st["pending_ai_cmd"]
        self._block_cursor = st.get("block_cursor")
        self._set_password_mode(self._password_mode)
        self._update_prompt()
        self._update_status()

    def _sync_to_tab(self, st: dict | None = None) -> None:
        cur = st or self._current_tab()
        if not cur:
            return
        cur["view"] = self.output_view
        cur["shell"] = self.shell
        cur["cwd"] = getattr(self.shell, "cwd", None) or cur.get("cwd") or os.getcwd()
        cur["shell_initialized"] = getattr(self, "_shell_initialized", False)
        cur["cmd_running"] = getattr(self, "_cmd_running", False)
        cur["password_mode"] = getattr(self, "_password_mode", False)
        cur["stream_tail"] = getattr(self, "_stream_tail", "")
        cur["last_exit_code"] = getattr(self, "_last_exit_code", None)
        cur["last_duration"] = getattr(self, "_last_duration", 0.0)
        cur["active_venv"] = getattr(self, "_active_venv", "")
        cur["has_ran_shell_cmd"] = getattr(self, "_has_ran_shell_cmd", False)
        cur["pending_ai_cmd"] = getattr(self, "pending_ai_cmd", "")
        cur["block_cursor"] = getattr(self, "_block_cursor", None)

    def _refresh_tab_title(self, st: dict | None = None) -> None:
        self._refresh_all_tab_titles()

    def _refresh_all_tab_titles(self) -> None:
        for i, st in enumerate(self._tabs):
            cwd = getattr(st.get("shell"), "cwd", None) or st.get("cwd") or os.getcwd()
            st["cwd"] = cwd
            short = Path(cwd).name or "/"
            mark = "●" if st.get("cmd_running") else "◈"
            self.tab_widget.setTabText(i, f"{mark} {i + 1} · {short}")
        if hasattr(self, "new_tab_btn"):
            self.new_tab_btn.setText(f"+ NEW TAB · {len(self._tabs)}")

    def _on_tab_moved(self, frm: int, to: int) -> None:
        if 0 <= frm < len(self._tabs) and 0 <= to < len(self._tabs):
            self._tabs.insert(to, self._tabs.pop(frm))
            self._refresh_all_tab_titles()
            cur = self._current_tab()
            if cur:
                self._sync_from_tab(cur)

    def _on_input_focus(self, focused: bool) -> None:
        self.input_bar.setProperty("focused", focused)
        style = self.input_bar.style()
        style.unpolish(self.input_bar)
        style.polish(self.input_bar)
        self.input_glow.setBlurRadius(34 if focused else 12)

    def _add_new_tab(self) -> None:
        self._sync_to_tab()
        cur = self._current_tab()
        cwd = (getattr(cur.get("shell"), "cwd", None) if cur else None) or os.getcwd()
        self._create_tab_entry(cwd, view=None, announce=True)
        self.input_box.setFocus()

    def _on_tab_changed(self, index: int) -> None:
        if not getattr(self, "_tabs", None) or not (0 <= index < len(self._tabs)):
            return
        self._sync_from_tab(self._tabs[index])

    def _close_tab_by_ref(self, st: dict) -> None:
        if st in self._tabs:
            self._close_tab_at(self._tabs.index(st))

    def _close_current_tab(self) -> None:
        self._close_tab_at(self.tab_widget.currentIndex())

    def _close_tab_at(self, index: int) -> None:
        if len(self._tabs) <= 1:
            self.append_line("◈ [Tab] At least one tab must remain open.", "warn")
            return
        if not (0 <= index < len(self._tabs)):
            return
        st = self._tabs.pop(index)
        sh = st.get("shell")
        if sh is not None:
            try:
                sh.stop_session()
            except Exception:
                pass
        w = self.tab_widget.widget(index)
        self.tab_widget.removeTab(index)
        if w is not None:
            w.deleteLater()
        new_idx = min(index, len(self._tabs) - 1)
        self.tab_widget.setCurrentIndex(new_idx)
        self._sync_from_tab(self._tabs[new_idx])
        self._refresh_all_tab_titles()

    # ── Execution ──
    def _run_quick_sys_cmd(self, title: str, shell_cmd: str) -> None:
        self.append_line(f"◈ {title}")
        try:
            proc = subprocess.run(shell_cmd, shell=True, capture_output=True, text=True, timeout=6)
            out = (proc.stdout or proc.stderr or "").strip()
            self.append_line(out if out else "[No output]", "out" if out else "dim")
        except Exception as exc:
            self.append_line(f"[Error] {exc}")

    def _run_worker(self, worker: QThread) -> None:
        self._workers.append(worker)

        def _done(w=worker) -> None:
            if w in self._workers:
                self._workers.remove(w)
            self._update_status()

        worker.finished.connect(_done)
        worker.start()
        self._update_status()

    def _set_password_mode(self, enabled: bool) -> None:
        if not hasattr(self, "input_box"):
            return
        self._password_mode = enabled
        if enabled:
            self.input_box.setEchoMode(QLineEdit.EchoMode.Password)
            self.input_box.setPlaceholderText("Enter password (hidden)…")
            if hasattr(self, "prompt_label"):
                self.prompt_label.setText(f"<span style='color:{self.t['warn']};'>🔒 Password ❯</span>")
            self._hide_suggestions()
            self.input_box.setFocus()
        else:
            self.input_box.setEchoMode(QLineEdit.EchoMode.Normal)
            self.input_box.setPlaceholderText(self.t["hint"])
            self._update_prompt()

    def _append_stream_text(self, text: str) -> None:
        if "\x1b[?1049h" in text or "\x1b[?47h" in text:
            self.append_line(
                "[TUI] Full-screen terminal UI detected. Press Ctrl+C or run with: tui <command>",
                "warn",
            )
            return
        clean = ANSI_RE.sub("", text).replace("\r\n", "\n")
        if not clean:
            return

        cur = self._get_block_cursor()
        fmt = self._fmt("out")

        parts = re.split(r"(\n|\r)", clean)
        for part in parts:
            if not part:
                continue
            if part == "\n":
                cur.insertBlock()
            elif part == "\r":
                cur.movePosition(QTextCursor.MoveOperation.StartOfBlock)
                cur.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
                cur.removeSelectedText()
            else:
                cur.insertText(part, fmt)

        self._block_cursor = cur
        tab = self._current_tab()
        if tab is not None:
            tab["block_cursor"] = cur
        self._follow_live_cursor(cur)

        self._stream_tail = (self._stream_tail + clean)[-240:]
        if self._cmd_running and self.PASSWORD_RE.search(self._stream_tail):
            self._set_password_mode(True)

    def _interrupt_shell(self) -> None:
        if not getattr(self, "_cmd_running", False) or self.shell is None:
            return
        self._set_password_mode(False)
        self.shell.interrupt()
        self.append_line("^C", "warn")

    def _on_ctrl_c(self) -> None:
        if self.output_view.hasFocus() and self.output_view.textCursor().hasSelection():
            self.output_view.copy()
            return
        if self.input_box.hasFocus() and self.input_box.hasSelectedText():
            self.input_box.copy()
            return
        if getattr(self, "_cmd_running", False):
            self._interrupt_shell()
        elif self.output_view.textCursor().hasSelection():
            self.output_view.copy()

    def _is_tui_command(self, raw: str) -> bool:
        try:
            tokens = shlex.split(raw)
        except ValueError:
            tokens = raw.split()
        if not tokens:
            return False
        if any(flag in tokens for flag in ("--help", "-h", "--version", "-V")):
            return False

        segments = [seg.strip() for seg in raw.split("|") if seg.strip()]
        check_segments = [segments[0]]
        if len(segments) > 1:
            check_segments.append(segments[-1])

        for seg in check_segments:
            try:
                seg_toks = shlex.split(seg)
            except ValueError:
                seg_toks = seg.split()
            idx = 0
            while idx < len(seg_toks):
                tok = seg_toks[idx]
                if tok in ("sudo", "env", "command", "time", "nohup") or ("=" in tok and not tok.startswith("-")):
                    idx += 1
                    continue
                if tok.startswith("-"):
                    idx += 1
                    continue
                base = os.path.basename(tok)
                if base in self.TUI_APPS:
                    return True
                break
        return False

    def _open_file_preview(self, target_str: str) -> None:
        from app.preview import FilePreviewDialog

        cwd = Path(getattr(self.shell, "cwd", None) or os.getcwd())
        raw_p = Path(os.path.expanduser(target_str))
        path = raw_p.resolve() if raw_p.is_absolute() else (cwd / raw_p).resolve()

        if not path.exists():
            self.append_line(f"[Preview] Path not found: {path}", "err")
            return

        dlg = FilePreviewDialog(path, self.t, self.output_view.font(), self)
        if not hasattr(self, "_preview_dialogs"):
            self._preview_dialogs = []
        self._preview_dialogs.append(dlg)
        dlg.finished.connect(
            lambda _code, d=dlg: self._preview_dialogs.remove(d)
            if d in self._preview_dialogs
            else None
        )
        dlg.show()
        self.append_line(f"◈ [Preview] Opened '{path}'", "ok")

    def _launch_tui_handoff(self, cmd: str) -> None:
        cwd = getattr(self.shell, "cwd", None) or os.getcwd()
        term = None
        for candidate in (
            "konsole", "gnome-terminal", "ptyxis", "kitty", "alacritty",
            "wezterm", "xfce4-terminal", "mate-terminal", "tilix",
            "foot", "terminator", "x-terminal-emulator", "xterm",
        ):
            found = shutil.which(candidate)
            if found:
                term = found
                break
        if not term:
            self.append_line("[TUI] No external terminal emulator found to hand off.", "err")
            return
        term_name = os.path.basename(term)
        if term_name == "konsole":
            argv = [term, "--workdir", cwd, "-e", "bash", "-lc", cmd]
        elif term_name in ("gnome-terminal", "ptyxis", "mate-terminal", "tilix"):
            argv = [term, f"--working-directory={cwd}", "--", "bash", "-lc", cmd]
        elif term_name == "kitty":
            argv = [term, "--directory", cwd, "bash", "-lc", cmd]
        elif term_name == "alacritty":
            argv = [term, "--working-directory", cwd, "-e", "bash", "-lc", cmd]
        elif term_name == "wezterm":
            argv = [term, "start", "--cwd", cwd, "--", "bash", "-lc", cmd]
        elif term_name == "foot":
            argv = [term, "-D", cwd, "bash", "-lc", cmd]
        elif term_name == "xfce4-terminal":
            argv = [term, "--working-directory", cwd, "-x", "bash", "-lc", cmd]
        else:
            argv = [term, "-e", "bash", "-lc", f"cd {shlex.quote(cwd)} && {cmd}"]
        try:
            subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.append_line(f"◈ [TUI Handoff] Opened '{cmd}' in {term_name}.", "ok")
        except Exception as exc:
            self.append_line(f"[TUI Error] Could not launch {term_name}: {exc}", "err")

    def _run_shell(self, cmd: str) -> None:
        if self.shell is None:
            return
        # Universal pre-execution syntax & completeness guard (catches all PS2 hangs: quotes, \, heredocs, blocks)
        try:
            _chk = subprocess.run(
                ["bash", "-O", "extglob", "-n"],
                input=cmd + "\n",
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            if _chk.returncode != 0:
                _err = (_chk.stderr or "Invalid bash syntax.").strip().replace("bash: line ", "line ")
                self._last_cmd = cmd
                self._last_exit_code = 2
                self.append_line(f"◈ [Syntax Error] {_err}", "err")
                self.append_line("  Hint: check syntax or run 'ai fix'.", "dim")
                return
            _wrap = subprocess.run(
                ["bash", "-O", "extglob", "-n"],
                input=f"if true; then :\n{cmd}\nfi\n",
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            if _wrap.returncode != 0:
                self._last_cmd = cmd
                self._last_exit_code = 2
                self.append_line("◈ [Syntax Error] Incomplete command (trailing '\\' continuation or unclosed heredoc).", "err")
                self.append_line("  Hint: remove trailing '\\' / close heredoc, or run 'ai fix'.", "dim")
                return
        except Exception:
            pass
        self._last_cmd = cmd
        self._has_ran_shell_cmd = True
        self._cmd_running = True
        self._stream_tail = ""
        self._sync_to_tab()
        self._refresh_all_tab_titles()
        self.shell.send(cmd)
        self._update_status()

    def _on_pty_output_for(self, st: dict, text: str) -> None:
        if not st.get("shell_initialized", False):
            return
        if self._current_tab() is st:
            self._append_stream_text(text)
            return
        clean = ANSI_RE.sub("", text).replace("\r\n", "\n")
        if not clean:
            return
        c = self._get_block_cursor(st)
        c.insertText(clean.replace("\r", ""), self._fmt("out"))
        st["block_cursor"] = c
        tail = (st.get("stream_tail", "") + clean)[-240:]
        st["stream_tail"] = tail
        if st.get("cmd_running") and self.PASSWORD_RE.search(tail):
            st["password_mode"] = True

    def _on_pty_ready_for(self, st: dict, exit_code: int, cwd: str, venv: str, duration: float) -> None:
        first_ready = not st.get("shell_initialized", False)
        st["shell_initialized"] = True
        st["cmd_running"] = False
        st["stream_tail"] = ""
        st["password_mode"] = False
        if cwd:
            st["cwd"] = cwd
        st["active_venv"] = venv.strip() if venv else ""
        if st.get("has_ran_shell_cmd", False):
            st["last_exit_code"] = exit_code
            st["last_duration"] = max(0.0, float(duration))

        if self._current_tab() is st:
            self._sync_from_tab(st)
        self._refresh_tab_title(st)

        if first_ready and getattr(self, "_initial_cmd", ""):
            cmd, self._initial_cmd = self._initial_cmd, ""
            QTimer.singleShot(150, lambda c=cmd: self._execute(c))

    def _on_pty_output(self, text: str) -> None:
        cur = self._current_tab()
        if cur:
            self._on_pty_output_for(cur, text)

    def _on_pty_ready(self, exit_code: int, cwd: str, venv: str, duration: float) -> None:
        cur = self._current_tab()
        if cur:
            self._on_pty_ready_for(cur, exit_code, cwd, venv, duration)

    def _get_path_cmds(self) -> list[str]:
        if self._path_cmds is not None:
            return self._path_cmds
        seen: set[str] = set()
        cmds: list[str] = []
        for pdir in os.environ.get("PATH", "").split(os.pathsep):
            if not pdir or not os.path.isdir(pdir):
                continue
            try:
                for entry in os.listdir(pdir):
                    if entry not in seen:
                        full = os.path.join(pdir, entry)
                        if os.access(full, os.X_OK) and not os.path.isdir(full):
                            seen.add(entry)
                            cmds.append(entry)
            except OSError:
                continue
        self._path_cmds = sorted(cmds)
        return self._path_cmds

    def _collect_suggestions(self, text: str, pos: int) -> list[tuple[str, str, str, str, bool]]:
        """Returns list of (display_label, kind['full'|'token'], prefix_text, value, add_space)."""
        before = text[:pos]
        if not before.strip():
            return []

        if before.endswith(" "):
            prefix_text, token = before, ""
        else:
            idx = before.rfind(" ")
            prefix_text = before[: idx + 1] if idx != -1 else ""
            token = before[idx + 1 :] if idx != -1 else before

        parts = prefix_text.strip().split()
        first_word = parts[0].lower() if parts else ""
        is_first = not parts
        items: list[tuple[str, str, str, str, bool]] = []
        seen_vals: set[str] = set()

        low_before = before.strip().lower()
        hist_added = 0
        for h in reversed(self.input_box.history):
            if h.lower().startswith(low_before) and h != before.strip() and h not in seen_vals:
                seen_vals.add(h)
                items.append((f"↺  {h}", "full", "", h, False))
                hist_added += 1
                if hist_added >= 3:
                    break

        if not is_first and first_word == "go" and len(parts) == 1:
            try:
                marks = sorted(load_bookmarks().keys())
            except Exception:
                marks = []
            for m in marks:
                if m.startswith(token):
                    items.append((f"◆  {m}", "token", prefix_text, m, True))
        elif not is_first and first_word == "mode" and len(parts) == 1:
            for m in sorted(THEMES.keys()):
                if m.startswith(token.lower()):
                    items.append((f"◈  {m}", "token", prefix_text, m, True))
        elif not is_first and first_word == "ai" and len(parts) == 1 and "do".startswith(token.lower()):
            items.append(("◈  do <task>", "token", prefix_text, "do", True))
        elif is_first and "/" not in token and not token.startswith((".", "~")):
            builtins = [
                "ai", "ai do", "ai fix", "ai reset", "clear", "copy", "devices", "find",
                "go", "help", "mode", "ports", "save", "sys", "tui",
            ]
            for b in builtins:
                if b.startswith(token.lower()) and b not in seen_vals:
                    seen_vals.add(b)
                    items.append((f"◈  {b}", "token", "", b, True))
            for cmd in self._get_path_cmds():
                if cmd.startswith(token) and cmd not in seen_vals:
                    seen_vals.add(cmd)
                    items.append((f"▸  {cmd}", "token", "", cmd, True))
                    if len(items) >= 12:
                        break
        else:
            cwd = getattr(self.shell, "cwd", None) or os.getcwd()
            raw_tok = token.lstrip('"\'')
            dirs_only = (first_word == "cd")
            home_str = str(Path.home())

            if raw_tok.startswith("~"):
                expanded = os.path.expanduser(raw_tok)
                use_tilde = True
            else:
                expanded = raw_tok
                use_tilde = False

            if os.path.isabs(expanded):
                base_dir = expanded if expanded.endswith("/") else (os.path.dirname(expanded) or "/")
                partial = "" if expanded.endswith("/") else os.path.basename(expanded)
            else:
                rel_dir = expanded if expanded.endswith("/") else os.path.dirname(expanded)
                base_dir = os.path.normpath(os.path.join(cwd, rel_dir)) if rel_dir else cwd
                partial = "" if expanded.endswith("/") else os.path.basename(expanded)

            if os.path.isdir(base_dir):
                try:
                    entries = sorted(
                        os.listdir(base_dir),
                        key=lambda e: (not os.path.isdir(os.path.join(base_dir, e)), e.lower()),
                    )
                except OSError:
                    entries = []
                dir_prefix = expanded[: len(expanded) - len(partial)]
                if use_tilde and dir_prefix.startswith(home_str):
                    dir_prefix = "~" + dir_prefix[len(home_str):]
                for entry in entries:
                    if not entry.startswith(partial):
                        continue
                    if not partial and entry.startswith("."):
                        continue
                    full_path = os.path.join(base_dir, entry)
                    is_dir = os.path.isdir(full_path)
                    if dirs_only and not is_dir:
                        continue
                    cand = f"{dir_prefix}{entry}/" if is_dir else f"{dir_prefix}{entry}"
                    icon = "📁" if is_dir else "📄"
                    items.append((f"{icon}  {entry}{'/' if is_dir else ''}", "token", prefix_text, cand, not is_dir))
                    if len(items) >= 12:
                        break

        return items[:10]

    def _position_suggestions(self) -> None:
        count = self.suggest_popup.count()
        if count == 0:
            self.suggest_popup.hide()
            return
        row_h = max(26, self.suggest_popup.sizeHintForRow(0))
        popup_h = min(count, 7) * row_h + 12
        popup_w = min(max(320, self.input_box.width()), 560)
        anchor = self.input_bar.mapTo(self.centralWidget(), self.input_bar.rect().topLeft())
        x = anchor.x() + max(0, self.input_box.x() - 4)
        y = anchor.y() + self.input_bar.height() + 6
        y = min(y, max(8, self.centralWidget().height() - popup_h - 8))
        self.suggest_popup.setGeometry(x, y, popup_w, popup_h)
        self.suggest_popup.raise_()
        self.suggest_popup.show()

    def _hide_suggestions(self) -> None:
        self._popup_navigated = False
        if hasattr(self, "suggest_popup"):
            self.suggest_popup.hide()

    def _toggle_history_search(self) -> None:
        if self._history_search_mode:
            self._exit_history_search(keep_text=True)
            return
        if self._password_mode or self._cmd_running:
            return
        self._history_search_mode = True
        self.prompt_label.setText(f"<span style='color:{self.t['accent']};'>🔍 History ❯</span>")
        self.input_box.setPlaceholderText("Search command history (Enter to pick, Esc to cancel)…")
        self.input_box.setFocus()
        self._update_suggestions()

    def _exit_history_search(self, keep_text: bool = True) -> None:
        if not self._history_search_mode:
            return
        self._history_search_mode = False
        if not keep_text:
            self.input_box.clear()
        self.input_box.setPlaceholderText(self.t["hint"])
        self._update_prompt()
        self._hide_suggestions()

    def _collect_history_matches(self, query: str) -> list[tuple[str, str, str, str, bool]]:
        q = query.strip().lower()
        tokens = q.split()
        items: list[tuple[str, str, str, str, bool]] = []
        seen: set[str] = set()
        for h in reversed(self.input_box.history):
            if h in seen:
                continue
            hl = h.lower()
            if not tokens or all(tok in hl for tok in tokens):
                seen.add(h)
                items.append((f"↺  {h}", "full", "", h, False))
                if len(items) >= 12:
                    break
        return items

    def _update_suggestions(self, _text: str = "") -> None:
        if not hasattr(self, "suggest_popup"):
            return
        text = self.input_box.text()
        pos = self.input_box.cursorPosition()
        if getattr(self, "_history_search_mode", False):
            items = self._collect_history_matches(text)
        else:
            items = self._collect_suggestions(text, pos)
        self.suggest_popup.clear()
        self._popup_navigated = False
        if not items:
            self.suggest_popup.hide()
            return
        for label, kind, prefix_text, val, add_space in items:
            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, (kind, prefix_text, val, add_space))
            self.suggest_popup.addItem(it)
        self.suggest_popup.setCurrentRow(0)
        self._position_suggestions()

    def _apply_suggestion_item(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        kind, prefix_text, val, add_space = data
        text = self.input_box.text()
        pos = self.input_box.cursorPosition()
        after = text[pos:]
        if kind == "full":
            new_before = val
        else:
            chosen = f'"{val}"' if (" " in val and not val.startswith(('"', "'")) and prefix_text) else val
            suffix = " " if (add_space and not chosen.rstrip('"').endswith("/")) else ""
            new_before = prefix_text + chosen + suffix
        self.input_box.setText(new_before + after)
        self.input_box.setCursorPosition(len(new_before))
        self.input_box.setFocus()
        if new_before.endswith("/"):
            self._update_suggestions()
        else:
            self._hide_suggestions()

    def _handle_popup_key(self, event: QKeyEvent) -> bool:
        if not hasattr(self, "suggest_popup") or not self.suggest_popup.isVisible():
            return False
        key = event.key()
        count = self.suggest_popup.count()
        if key == Qt.Key.Key_Down and count:
            row = (self.suggest_popup.currentRow() + 1) % count
            self.suggest_popup.setCurrentRow(row)
            self._popup_navigated = True
            return True
        if key == Qt.Key.Key_Up and count:
            row = (self.suggest_popup.currentRow() - 1) % count
            self.suggest_popup.setCurrentRow(row)
            self._popup_navigated = True
            return True
        if key == Qt.Key.Key_Escape:
            if getattr(self, "_history_search_mode", False):
                self._exit_history_search(keep_text=False)
            else:
                self._hide_suggestions()
            return True
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if getattr(self, "_history_search_mode", False) or self._popup_navigated:
                cur = self.suggest_popup.currentItem() or self.suggest_popup.item(0)
                if cur:
                    self._apply_suggestion_item(cur)
                    return True
            self._hide_suggestions()
            return False
        return False

    def _handle_tab_complete(self) -> None:
        if hasattr(self, "suggest_popup") and self.suggest_popup.isVisible():
            cur = self.suggest_popup.currentItem() or self.suggest_popup.item(0)
            if cur:
                self._apply_suggestion_item(cur)
                return
        self._update_suggestions()
        if self.suggest_popup.isVisible() and self.suggest_popup.count() == 1:
            self._apply_suggestion_item(self.suggest_popup.item(0))

    def _on_submit(self) -> None:
        self._hide_suggestions()
        if getattr(self, "_cmd_running", False) and self.shell is not None:
            raw_in = self.input_box.text()
            self.input_box.clear()
            if self._password_mode:
                self._set_password_mode(False)
                self._stream_tail = ""
                self.shell.send_raw(raw_in + "\n")
                return
            self._append_stream_text(raw_in + "\n")
            self._stream_tail = ""
            self.shell.send_raw(raw_in + "\n")
            return
        raw = self.input_box.text().strip()
        if not raw:
            return
        self.input_box.clear()
        if not raw.lower().startswith("ai key "):
            self.input_box.record(raw)
        self._execute(raw)

    def _execute(self, raw: str) -> None:
        self._start_new_block()
        self.append_line(f"❯ {raw}", "cmd")
        lo = raw.lower()

        if lo == "clear":
            self._clear_output()
            return
        if lo == "help":
            self._help()
            return
        if lo.startswith("mode"):
            arg = lo[4:].strip()
            if arg in THEMES:
                self._set_theme(arg, boot=True)
            elif arg in ("", "toggle"):
                self._toggle_mode()
            else:
                self.append_line("Usage: mode nihatos | ultron")
            return
        if lo == "sys":
            self._run_quick_sys_cmd(
                "SYSTEM SCAN",
                "uname -sr && uptime -p && free -h | awk 'NR==1 || /Mem:/ {print $1, $2, $3, $4}'",
            )
            return
        if lo == "devices":
            self._run_quick_sys_cmd(
                "USB & SERIAL DEVICES", "lsusb; ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || true"
            )
            return
        if lo == "ports":
            self._run_quick_sys_cmd("LISTENING PORTS", "ss -tulnp 2>/dev/null || netstat -tulnp 2>/dev/null")
            return

        if lo == "copy" or lo.startswith("copy "):
            arg = raw[5:].strip().lower() if lo.startswith("copy ") else "25"
            lines = self._get_lines()
            if not lines:
                self.append_line("[Copy] No output yet.")
                return
            if arg == "all":
                sel = lines
            elif arg.isdigit() and int(arg) > 0:
                sel = lines[-int(arg):]
            else:
                self.append_line("Usage: copy [N | all]")
                return
            QApplication.clipboard().setText("\n".join(sel))
            self.append_line(f"[Copied] Copied {len(sel)} lines to clipboard.")
            return

        if self.pending_ai_cmd and lo in ("y", "yes", "run"):
            cmd, self.pending_ai_cmd = self.pending_ai_cmd, ""
            self._update_status()
            self.append_line(f"▶ Executing: {cmd}")
            self._run_shell(cmd)
            return
        if self.pending_ai_cmd and lo in ("n", "no", "cancel"):
            self.pending_ai_cmd = ""
            self._update_status()
            self.append_line("[AI Run] Cancelled.")
            return

        if lo.startswith("go "):
            name = raw[3:].strip()
            marks = load_bookmarks()
            if name not in marks:
                self.append_line(f"[Bookmark] '{name}' not found.")
                return
            self.append_line(f"◈ Jumping to '{name}' → {marks[name]}")
            self._run_shell(f'cd "{marks[name]}"')
            return

        if lo.startswith("find "):
            query = raw[5:].strip()
            matches = search_output_lines(self._get_lines(), query)
            if not matches:
                self.append_line(f"[Search] No matches for '{query}'.")
                return
            self.append_line(f"◈ SEARCH RESULTS for '{query}' ({len(matches)} found)")
            for lno, txt in matches:
                self.append_line(f"  L{lno}: {txt}", "dim")
            return

        if lo in ("preview", "view") or lo.startswith(("preview ", "view ", "less ")):
            import shlex

            has_shell_ops = any(op in raw for op in ("|", "&&", "||", ";", ">", "<", "`", "$(", "*", "?"))
            if not (lo.startswith("less ") and has_shell_ops):
                try:
                    tokens = shlex.split(raw)
                except ValueError:
                    tokens = raw.split()
                cmd_name = tokens[0].lower() if tokens else ""
                args = [
                    a
                    for a in tokens[1:]
                    if not (cmd_name == "less" and (a.startswith("-") or a.startswith("+")))
                ]
                if not args:
                    if cmd_name != "less":
                        self.append_line("Usage: preview <file_or_dir>  (aliases: view, less <file>)", "dim")
                        return
                else:
                    cwd = Path(getattr(self.shell, "cwd", None) or os.getcwd())
                    joined = " ".join(args)
                    target = joined if len(args) > 1 and (cwd / os.path.expanduser(joined)).exists() else args[0]
                    self._open_file_preview(target)
                    return

        if lo == "save" or lo.startswith("save "):
            fname = raw[5:].strip() if lo.startswith("save ") else "nihatos-log.txt"
            safe_cwd = getattr(self.shell, "cwd", None) or os.getcwd()
            ok, msg = export_output_lines(self._get_lines(), fname, cwd=safe_cwd)
            self.append_line(f"[Export] {msg}" if ok else f"[Export Error] {msg}")
            return

        if lo in ("ai", "ai do"):
            self.append_line("Usage: ai <question>  |  ai do <task>  |  ai fix  |  ai reset", "warn")
            return

        if lo == "setname" or lo.startswith("setname "):
            new_name = raw[7:].strip()
            if not new_name:
                self.append_line(f"Current OS Name: {self.config.os_name}", "head")
                self.append_line("Usage: setname <YourName>  (example: setname Saad.O.S)", "dim")
                return
            self.config.os_name = new_name
            self.config.save()
            THEMES["nihatos"]["name"] = new_name
            THEMES["nihatos"]["tag"] = new_name.replace(".", "")
            self._set_theme(self.key, boot=False)
            self.append_line(f"◈ OS identity updated to '{new_name}'.", "ok")
            return

        if lo == "update":
            self.append_line("◈ Checking for updates…", "head")
            self._run_shell(
                f'git -C "{ROOT}" pull --ff-only && "{ROOT}/.venv/bin/pip" install -q -r "{ROOT}/requirements.txt" && echo "✅ Updated! Restart terminal to apply changes."'
            )
            return

        if lo in ("ai setup", "ai key"):
            cfg_dir = Path.home() / ".config" / "nihatos-terminal"
            self.append_line("◈ AI API KEY STATUS (stored locally in ~/.config/nihatos-terminal/)", "head")
            for label, fname, url in [
                ("Groq (Primary)", "groq_key", "https://console.groq.com/keys"),
                ("Google Gemini", "gemini_key", "https://aistudio.google.com/apikey"),
                ("OpenRouter", "openrouter_key", "https://openrouter.ai/keys"),
            ]:
                kp = cfg_dir / fname
                status = "✔ configured" if (kp.is_file() and kp.read_text(encoding="utf-8", errors="ignore").strip()) else "✖ not set"
                self.append_line(f"  ▸ {label:<16} {status}   ({url})", "ok" if "✔" in status else "dim")
            self.append_line("  Set key:    ai key <groq|gemini|openrouter> <YOUR_API_KEY>", "warn")
            self.append_line("  Remove key: ai key <groq|gemini|openrouter> remove", "dim")
            return

        if lo == "ai key clear" or lo == "ai key delete all":
            cfg_dir = Path.home() / ".config" / "nihatos-terminal"
            deleted = []
            for prov in ("groq", "gemini", "openrouter"):
                kp = cfg_dir / f"{prov}_key"
                if kp.exists():
                    kp.unlink()
                    deleted.append(prov)
            if deleted:
                self.append_line(f"◈ Deleted API keys: {", ".join(deleted)}. Run 'ai setup' to add new keys.", "ok")
            else:
                self.append_line("◈ No saved API keys found.", "dim")
            return

        if lo.startswith("ai key delete "):
            prov = raw.split(None, 3)[3].strip().lower() if len(raw.split(None, 3)) >= 4 else ""
            if prov not in ("groq", "gemini", "openrouter"):
                self.append_line("Usage: ai key delete <groq|gemini|openrouter|all>", "warn")
                return
            kp = Path.home() / ".config" / "nihatos-terminal" / f"{prov}_key"
            if kp.exists():
                kp.unlink()
                self.append_line(f"◈ Deleted {prov} API key.", "ok")
            else:
                self.append_line(f"◈ No saved {prov} key found.", "dim")
            return

        if lo.startswith("ai key "):
            parts = raw.split(None, 3)
            if len(parts) < 4 or parts[2].lower() not in ("groq", "gemini", "openrouter"):
                self.append_line("Usage: ai key <groq|gemini|openrouter> <YOUR_API_KEY | remove>  |  ai key delete <provider|all>  |  ai key clear", "warn")
                return
            provider, key_val = parts[2].lower(), parts[3].strip()
            cfg_dir = Path.home() / ".config" / "nihatos-terminal"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            kp = cfg_dir / f"{provider}_key"
            if key_val.lower() == "remove":
                if kp.exists():
                    kp.unlink()
                self.append_line(f"◈ Removed {provider} API key.", "warn")
                return
            kp.write_text(key_val + "\n", encoding="utf-8")
            os.chmod(kp, 0o600)
            self.append_line(f"◈ Saved {provider} API key securely (chmod 600). Ready to use immediately!", "ok")
            return

        if lo == "ai reset":
            self._ai_history.clear()
            self.append_line("◈ [AI] Session chat memory cleared.", "ok")
            return

        if lo == "ai fix" or lo.startswith("ai fix "):
            extra_hint = raw[6:].strip()
            last_cmd = getattr(self, "_last_cmd", "").strip()
            if not last_cmd:
                self.append_line("[AI Fix] No previous shell command found to fix.", "warn")
                return
            cwd = getattr(self.shell, "cwd", None) or os.getcwd()
            exit_c = getattr(self, "_last_exit_code", None)
            tail_out = "\n".join(self._get_lines()[-15:])
            self.append_line(f"◈ {self.t['tag']} diagnosing last command: {last_cmd}…")
            prompt = (
                f"The user ran a bash command on {_LINUX_ENV_LABEL} and wants it fixed.\n"
                f"Working directory: {cwd}\n"
                f"Last command: {last_cmd}\n"
                f"Exit code: {exit_c}\n"
                f"Recent terminal output:\n{tail_out}\n"
                + (f"Extra note: {extra_hint}\n" if extra_hint else "")
                + f"Give ONLY ONE corrected, safe {_LINUX_ENV_LABEL} bash command. "
                "No explanation, no markdown, just the single command line."
            )
            w = AIWorker(self.ai_client, self.config.ai_model, prompt, "do")
            w.finished_ai.connect(self._on_ai_finished)
            self._run_worker(w)
            return

        if lo.startswith("ai do "):
            task = raw[6:].strip()
            if not task:
                self.append_line("Usage: ai do <describe what you want to run>")
                return
            cwd = getattr(self.shell, "cwd", None) or os.getcwd()
            self.append_line(f"◈ {self.t['tag']} computing a command for: {task}…")
            prompt = (
                f"Give ONLY ONE safe {_LINUX_ENV_LABEL} bash command to accomplish this task. "
                f"Current working directory: {cwd}. "
                f"No explanation, no markdown, just the single command line:\n{task}"
            )
            w = AIWorker(self.ai_client, self.config.ai_model, prompt, "do")
            w.finished_ai.connect(self._on_ai_finished)
            self._run_worker(w)
            return

        if lo.startswith("ai "):
            q = raw[3:].strip()
            if not q:
                self.append_line("Usage: ai <your question>")
                return
            if q.lower().startswith("mode "):
                self.append_line("Tip: use 'mode nihatos' or 'mode ultron' directly to switch personas.")
                return
            self._last_ai_q = q
            self.append_line(f"◈ {self.t['tag']} analysing…")
            cwd = getattr(self.shell, "cwd", None) or os.getcwd()
            hist_ctx = ""
            if self._ai_history:
                turns = "\n".join(f"User: {uq}\nAssistant: {ua}" for uq, ua in self._ai_history[-15:])
                hist_ctx = f"\n\nRecent conversation:\n{turns}"
            sys_parts = []
            ql = q.lower()
            try:
                import subprocess as _sp
                _checks = [
                    (("battery", "charge", "charging", "power", "upower", "acpi"),
                     "upower -i $(upower -e | grep -i battery | head -n 1)"),
                    (("disk", "storage", "space", "ssd", "nvme", "partition", "occupied", "df"),
                     "df -h -x tmpfs -x devtmpfs -x squashfs"),
                    (("ram", "memory", "swap"),
                     "free -h"),
                    (("cpu", "processor", "load", "uptime"),
                     "uptime && lscpu | grep -E 'Model name|CPU\\(s\\)'"),
                    (("kernel", "distro", "linux", "fedora", "ubuntu", "arch", "debian", "os version", "uname", "system info"),
                     "uname -srm && grep -E '^(PRETTY_NAME|VERSION_ID)=' /etc/os-release 2>/dev/null"),
                ]
                for _kws, _cmd in _checks:
                    if any(k in ql for k in _kws):
                        _res = _sp.run(["bash", "-c", _cmd], capture_output=True, text=True, timeout=2)
                        _out = (_res.stdout or "").strip()
                        if _out:
                            sys_parts.append(f"$ {_cmd}\n{_out[:1800]}")
            except Exception:
                pass
            sys_ctx = ""
            if sys_parts:
                sys_ctx = (
                    "\n\nLive read-only telemetry from the user's laptop (use these exact figures to answer directly):\n"
                    + "\n\n".join(sys_parts)
                )
            full_prompt = f"{self.t['persona']}\nCurrent directory: {cwd}{hist_ctx}{sys_ctx}\n\nUser: {q}"
            w = AIWorker(self.ai_client, self.config.ai_model, full_prompt, "ask")
            w.finished_ai.connect(self._on_ai_finished)
            self._run_worker(w)
            return

        if lo.startswith("tui "):
            tcmd = raw[4:].strip()
            if not tcmd:
                self.append_line("Usage: tui <interactive command>", "warn")
                return
            self._launch_tui_handoff(tcmd)
            return

        if self._is_tui_command(raw):
            self._launch_tui_handoff(raw)
            return

        self._run_shell(raw)

    def _on_shell_finished(self, cmd: str, output: str, cwd: str) -> None:
        self._update_prompt()
        self._update_status()
        clean = ANSI_RE.sub("", output).replace("\r", "")
        if clean.strip():
            self.append_line(clean.rstrip())

    def _on_ai_finished(self, mode: str, text: str, ok: bool, used_model: str = "") -> None:
        if not ok:
            self.append_line(text, "err")
            return
        if used_model:
            self.active_model = used_model
            self._update_status()
        m_badge = f" · {used_model}" if used_model else ""
        if mode == "do":
            cmd = extract_shell_command(text)
            if not cmd:
                self.append_line("[AI Run] Could not extract a valid command.")
                return
            self.pending_ai_cmd = cmd
            self._update_status()
            self.append_line(f"◈ Proposed command{m_badge}: {cmd}", "head")
            self.append_line("  Type 'y' to run it, or 'n' to cancel.", "warn")
        else:
            if getattr(self, "_last_ai_q", ""):
                self._ai_history.append((self._last_ai_q, text))
                self._ai_history = self._ai_history[-15:]
                self._last_ai_q = ""
            self.append_line(f"◈ [{self.t['tag']}{m_badge}]", "ai_head")
            self.append_line(text, "ai")

    def closeEvent(self, event) -> None:
        self._q_token += 1
        self._q.clear()
        try:
            self.hud_timer.stop()
        except Exception:
            pass
        for w in list(self._workers):
            try:
                w.quit()
                w.wait(1000)
            except Exception:
                pass
        for st in list(getattr(self, "_tabs", [])):
            sh = st.get("shell")
            if sh is not None:
                try:
                    sh.stop_session()
                except Exception:
                    pass
        super().closeEvent(event)


def _parse_cli_args(argv: list[str]) -> tuple[str | None, str]:
    start_cwd: str | None = None
    initial_cmd = ""
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("--workdir", "--working-directory") and i + 1 < len(argv):
            start_cwd = argv[i + 1]
            i += 2
        elif arg.startswith("--workdir="):
            start_cwd = arg.split("=", 1)[1]
            i += 1
        elif arg.startswith("--working-directory="):
            start_cwd = arg.split("=", 1)[1]
            i += 1
        elif arg in ("-e", "-x") and i + 1 < len(argv):
            rest = argv[i + 1 :]
            initial_cmd = rest[0] if len(rest) == 1 else shlex.join(rest)
            break
        elif arg == "-c" and i + 1 < len(argv):
            initial_cmd = argv[i + 1]
            break
        elif arg in ("--hold", "--noclose"):
            i += 1
        else:
            i += 1
    return start_cwd, initial_cmd


def main() -> int:
    from PyQt6.QtGui import QIcon

    start_cwd, initial_cmd = _parse_cli_args(sys.argv[1:])
    app = QApplication(sys.argv)
    app.setApplicationName("Nihat.O.S")
    app.setDesktopFileName("nihatos-terminal")
    app.setWindowIcon(QIcon.fromTheme("utilities-terminal"))
    win = NihatOSDesktopWindow(start_cwd=start_cwd, initial_cmd=initial_cmd)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())