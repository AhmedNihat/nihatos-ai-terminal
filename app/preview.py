from __future__ import annotations

from pathlib import Path
from PyQt6.QtCore import QRect, QSize, Qt, QUrl
from PyQt6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QKeyEvent,
    QKeySequence,
    QPainter,
    QPixmap,
    QShortcut,
    QTextDocument,
)
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".ico", ".svg"}
MAX_PREVIEW_BYTES = 2 * 1024 * 1024  # 2 MB


def _fmt_size(num: int) -> str:
    size = float(num)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0 or unit == "TB":
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{num} B"


def _hex_dump(data: bytes, limit: int = 512) -> str:
    chunk = data[:limit]
    lines = []
    for off in range(0, len(chunk), 16):
        row = chunk[off : off + 16]
        hex_part = " ".join(f"{b:02x}" for b in row).ljust(47)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
        lines.append(f"{off:08x}  {hex_part}  |{ascii_part}|")
    return "\n".join(lines)


class _LineNumberArea(QWidget):
    def __init__(self, editor: "_CodePreviewEdit") -> None:
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self._editor.gutter_width(), 0)

    def paintEvent(self, event) -> None:
        self._editor.paint_gutter(event)


class _CodePreviewEdit(QPlainTextEdit):
    def __init__(self, gutter_bg: str, gutter_fg: str, parent=None) -> None:
        super().__init__(parent)
        self._gutter_bg = gutter_bg
        self._gutter_fg = gutter_fg
        self._gutter = _LineNumberArea(self)

        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        self.blockCountChanged.connect(self._update_gutter_width)
        self.updateRequest.connect(self._update_gutter)
        self._update_gutter_width(0)

    def gutter_width(self) -> int:
        digits = max(3, len(str(max(1, self.blockCount()))))
        return 14 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_gutter_width(self, _count: int) -> None:
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def _update_gutter(self, rect: QRect, dy: int) -> None:
        if dy:
            self._gutter.scroll(0, dy)
        else:
            self._gutter.update(0, rect.y(), self._gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_gutter_width(0)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._gutter.setGeometry(QRect(cr.left(), cr.top(), self.gutter_width(), cr.height()))

    def paint_gutter(self, event) -> None:
        painter = QPainter(self._gutter)
        painter.fillRect(event.rect(), QColor(self._gutter_bg))

        block = self.firstVisibleBlock()
        block_num = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        line_h = self.fontMetrics().height()
        gutter_w = self._gutter.width() - 8

        painter.setPen(QColor(self._gutter_fg))
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.drawText(
                    0,
                    int(top),
                    int(gutter_w),
                    int(line_h),
                    Qt.AlignmentFlag.AlignRight,
                    str(block_num + 1),
                )
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_num += 1


class FilePreviewDialog(QDialog):
    def __init__(self, path: Path, theme: dict, mono_font: QFont, parent=None) -> None:
        super().__init__(parent)
        self.target_path = path
        self.t = theme
        self._is_text_mode = False
        self.editor: _CodePreviewEdit | None = None
        self.search_input: QLineEdit | None = None

        self.setWindowTitle(f"Preview — {path.name or str(path)}")
        self.resize(900, 620)
        self.setStyleSheet(
            f"""
            QDialog {{ background-color: {theme['bg']}; color: {theme['text']}; }}
            #PreviewHeader {{
                background-color: {theme['panel']};
                border: 1px solid {theme['border']};
                border-radius: 10px;
            }}
            #PreviewTitle {{ color: {theme['accent']}; font-weight: bold; font-size: 13px; }}
            #PreviewMeta {{ color: {theme['dim']}; font-size: 11px; }}
            QLineEdit {{
                background-color: {theme['panel2']};
                color: {theme['text']};
                border: 1px solid {theme['border']};
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 12px;
            }}
            QLineEdit:focus {{ border: 1px solid {theme['accent']}; }}
            QPushButton {{
                background-color: {theme['panel2']};
                color: {theme['text']};
                border: 1px solid {theme['border']};
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
            }}
            QPushButton:hover {{ border-color: {theme['accent']}; color: {theme['accent']}; }}
            QPlainTextEdit {{
                background-color: {theme['panel']};
                color: {theme['text']};
                border: 1px solid {theme['border']};
                border-radius: 10px;
                selection-background-color: {theme['accent']};
                selection-color: {theme['bg']};
            }}
            QScrollArea {{
                background-color: {theme['panel']};
                border: 1px solid {theme['border']};
                border-radius: 10px;
            }}
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # Header
        header = QWidget()
        header.setObjectName("PreviewHeader")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(12, 8, 12, 8)
        hl.setSpacing(10)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.title_lbl = QLabel(str(path))
        self.title_lbl.setObjectName("PreviewTitle")
        self.title_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.meta_lbl = QLabel("")
        self.meta_lbl.setObjectName("PreviewMeta")
        title_col.addWidget(self.title_lbl)
        title_col.addWidget(self.meta_lbl)
        hl.addLayout(title_col, stretch=1)

        ext_btn = QPushButton("Open External")
        ext_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))))
        hl.addWidget(ext_btn)

        close_btn = QPushButton("Close (Esc)")
        close_btn.clicked.connect(self.close)
        hl.addWidget(close_btn)
        root.addWidget(header)

        # Content
        if path.is_dir():
            self._setup_text_view(root, mono_font, *self._load_directory(path))
        elif path.suffix.lower() in IMAGE_EXTS:
            self._setup_image_view(root, path)
        else:
            self._setup_text_view(root, mono_font, *self._load_file_text(path))

        QShortcut(QKeySequence("Ctrl+F"), self, activated=self._focus_search)

    def _load_directory(self, path: Path) -> tuple[str, str]:
        try:
            entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return "[Permission denied]", "Directory · Unreadable"

        total = len(entries)
        shown = entries[:2000]
        lines = []
        for item in shown:
            try:
                if item.is_dir():
                    lines.append(f"[DIR]  {'':>10}  {item.name}/")
                else:
                    lines.append(f"[FILE] {_fmt_size(item.stat().st_size):>10}  {item.name}")
            except OSError:
                lines.append(f"[?]    {'':>10}  {item.name}")
        if total > 2000:
            lines.append(f"\n… ({total - 2000} more items omitted)")
        content = "\n".join(lines) if lines else "(empty directory)"
        return content, f"Directory · {total} items"

    def _load_file_text(self, path: Path) -> tuple[str, str]:
        size = path.stat().st_size
        truncated = size > MAX_PREVIEW_BYTES
        with path.open("rb") as fh:
            raw = fh.read(MAX_PREVIEW_BYTES)

        if b"\x00" in raw[:4096]:
            header = f"[Binary file — {_fmt_size(size)} — showing first 512 bytes as hex dump]\n\n"
            return header + _hex_dump(raw), f"Binary · {_fmt_size(size)}"

        text = raw.decode("utf-8", errors="replace")
        line_count = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
        if truncated:
            text += f"\n\n─── [Truncated at 2.0 MB · Full size: {_fmt_size(size)}] ───"
        meta = f"File · {_fmt_size(size)} · {line_count} lines" + (" (truncated)" if truncated else "")
        return text, meta

    def _setup_text_view(self, root: QVBoxLayout, mono_font: QFont, content: str, meta: str) -> None:
        self._is_text_mode = True
        self.meta_lbl.setText(meta)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search text… (Ctrl+F or /)")
        self.search_input.returnPressed.connect(lambda: self._find_text(backward=False))
        toolbar.addWidget(self.search_input, stretch=1)

        prev_btn = QPushButton("▲ Prev")
        prev_btn.clicked.connect(lambda: self._find_text(backward=True))
        toolbar.addWidget(prev_btn)

        next_btn = QPushButton("▼ Next")
        next_btn.clicked.connect(lambda: self._find_text(backward=False))
        toolbar.addWidget(next_btn)

        wrap_btn = QPushButton("Wrap: Off")
        wrap_btn.setCheckable(True)
        wrap_btn.toggled.connect(lambda on: self._toggle_wrap(on, wrap_btn))
        toolbar.addWidget(wrap_btn)

        copy_btn = QPushButton("Copy All")
        copy_btn.clicked.connect(self._copy_all)
        toolbar.addWidget(copy_btn)

        root.addLayout(toolbar)

        self.editor = _CodePreviewEdit(self.t["panel2"], self.t["dim"], self)
        self.editor.setFont(mono_font)
        self.editor.setPlainText(content)
        root.addWidget(self.editor, stretch=1)
        self.editor.setFocus()

    def _setup_image_view(self, root: QVBoxLayout, path: Path) -> None:
        pix = QPixmap(str(path))
        size = path.stat().st_size
        if pix.isNull():
            self.meta_lbl.setText(f"Image · {_fmt_size(size)} · Failed to decode")
            lbl = QLabel("Unable to render this image file.")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            root.addWidget(lbl, stretch=1)
            return

        self.meta_lbl.setText(f"Image · {pix.width()}×{pix.height()} · {_fmt_size(size)}")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        img_lbl = QLabel()
        img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if pix.width() > 860 or pix.height() > 520:
            pix = pix.scaled(
                860,
                520,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        img_lbl.setPixmap(pix)
        scroll.setWidget(img_lbl)
        root.addWidget(scroll, stretch=1)

    def _toggle_wrap(self, enabled: bool, btn: QPushButton) -> None:
        if not self.editor:
            return
        self.editor.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.WidgetWidth if enabled else QPlainTextEdit.LineWrapMode.NoWrap
        )
        btn.setText("Wrap: On" if enabled else "Wrap: Off")

    def _copy_all(self) -> None:
        if self.editor:
            QApplication.clipboard().setText(self.editor.toPlainText())
            self.meta_lbl.setText(self.meta_lbl.text().split(" · Copied")[0] + " · Copied!")

    def _focus_search(self) -> None:
        if self.search_input:
            self.search_input.setFocus()
            self.search_input.selectAll()

    def _find_text(self, backward: bool = False) -> None:
        if not self.editor or not self.search_input:
            return
        query = self.search_input.text()
        if not query:
            return
        flags = QTextDocument.FindFlag.FindBackward if backward else QTextDocument.FindFlag(0)
        if not self.editor.find(query, flags):
            cursor = self.editor.textCursor()
            cursor.movePosition(
                cursor.MoveOperation.End if backward else cursor.MoveOperation.Start
            )
            self.editor.setTextCursor(cursor)
            self.editor.find(query, flags)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        in_search = bool(self.search_input and self.search_input.hasFocus())
        if key == Qt.Key.Key_Escape:
            if in_search and self.search_input.text():
                self.search_input.clear()
                if self.editor:
                    self.editor.setFocus()
            else:
                self.close()
            event.accept()
            return
        if not in_search and key == Qt.Key.Key_Q:
            self.close()
            event.accept()
            return
        if not in_search and key == Qt.Key.Key_Slash and self.search_input:
            self._focus_search()
            event.accept()
            return
        super().keyPressEvent(event)
