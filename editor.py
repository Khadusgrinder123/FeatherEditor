"""The code editor widget with syntax highlighting and local completion."""
import re
from PySide6.QtCore import Qt, QRect, QSize, Signal
from PySide6.QtGui import (
    QColor, QPainter, QFont, QTextCursor, QTextFormat, QFontMetricsF
)
from PySide6.QtWidgets import (
    QPlainTextEdit, QWidget, QTextEdit, QListWidget, QListWidgetItem
)

from .highlighter import PythonHighlighter

IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_line_numbers(event)


class CompletionPopup(QListWidget):
    """A sharp-edged, Nord-styled completion list."""
    def __init__(self, editor, theme):
        super().__init__(editor.window())
        self.editor = editor
        self.setWindowFlags(Qt.ToolTip)
        self.setFocusPolicy(Qt.NoFocus)
        self.apply_theme(theme)
        self.itemActivated.connect(self._accept_item)
        self.hide()

    def apply_theme(self, theme):
        self.setStyleSheet(f"""
            QListWidget {{
                background-color: {theme.bg_alt};
                color: {theme.fg};
                border: 1px solid {theme.accent};
                border-radius: 0px;
                outline: 0;
            }}
            QListWidget::item {{ padding: 2px 6px; }}
            QListWidget::item:selected {{
                background-color: {theme.accent};
                color: {theme.accent_fg};
            }}
        """)

    def show_words(self, words, global_pos):
        self.clear()
        for w in words:
            QListWidgetItem(w, self)
        if self.count() == 0:
            self.hide()
            return
        self.setCurrentRow(0)
        self.move(global_pos)
        row_h = self.sizeHintForRow(0) or 16
        self.resize(260, min(8, self.count()) * row_h + 6)
        self.show()
        self.raise_()

    def _accept_item(self, item):
        self.editor.accept_completion(item.text())

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab):
            item = self.currentItem()
            if item:
                self._accept_item(item)
            return
        if event.key() == Qt.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)


class CodeEditor(QPlainTextEdit):
    PAIRS = {"(": ")", "[": "]", "{": "}", "\"": "\"", "'": "'"}

    completionRequested = Signal(int, int)  # line, character (LSP 0-based)
    contentChanged = Signal()
    fontZoomRequested = Signal(int)
    editorCommandRequested = Signal(str)

    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self._font_size = 11
        self.setFont(QFont("JetBrains Mono", self._font_size))
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setTabStopDistance(QFontMetricsF(self.font()).horizontalAdvance(" ") * 4)

        self.line_number_area = LineNumberArea(self)
        self.highlighter = PythonHighlighter(self.document(), theme)
        self.completion_popup = CompletionPopup(self, theme)

        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.textChanged.connect(self._on_text_changed)

        self.update_line_number_area_width(0)
        self.highlight_current_line()
        self.apply_theme(theme)

    # ---- theming ----------------------------------------------------
    def apply_theme(self, theme):
        self.theme = theme
        self.setStyleSheet(
            f"QPlainTextEdit {{ background-color:{theme.bg}; color:{theme.fg}; "
            f"border: none; selection-background-color:{theme.selection}; "
            f"font-size:{self._font_size}pt; }}"
        )
        self.highlighter.theme = theme
        self.highlighter._build_rules()
        self.highlighter.rehighlight()
        self.completion_popup.apply_theme(theme)
        self.highlight_current_line()
        self.viewport().update()

    # ---- line number gutter ------------------------------------------
    def line_number_area_width(self):
        digits = max(2, len(str(max(1, self.blockCount()))))
        return 10 + self.fontMetrics().horizontalAdvance("9") * digits

    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def paint_line_numbers(self, event):
        t = self.theme
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor(t.bg_alt))
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        current_line = self.textCursor().blockNumber()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                color = QColor(t.accent) if block_number == current_line else QColor(t.fg_dim)
                painter.setPen(color)
                painter.drawText(0, int(top), self.line_number_area.width() - 6,
                                  int(self.blockBoundingRect(block).height()),
                                  Qt.AlignRight, number)
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1
        painter.end()

    def highlight_current_line(self):
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(QColor(self.theme.bg_alt))
        selection.format.setProperty(QTextFormat.FullWidthSelection, True)
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        self.setExtraSelections([selection])

    # ---- autocomplete -------------------------------------------------
    def _on_text_changed(self):
        self.contentChanged.emit()

    def current_word_prefix(self):
        cursor = self.textCursor()
        cursor.select(QTextCursor.WordUnderCursor)
        return cursor.selectedText()

    def local_word_candidates(self, prefix):
        if not prefix:
            return []
        text = self.toPlainText()
        words = set(IDENT_RE.findall(text))
        words.discard(prefix)
        return sorted(w for w in words if w.startswith(prefix))[:50]

    def keyPressEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            commands = {
                Qt.Key_F: "find",
                Qt.Key_H: "replace",
                Qt.Key_G: "goto",
                Qt.Key_W: "close-tab",
            }
            command = commands.get(event.key())
            if command:
                self.editorCommandRequested.emit(command)
                return
            if event.key() in (Qt.Key_Plus, Qt.Key_Equal):
                self.fontZoomRequested.emit(1)
                return
            if event.key() == Qt.Key_Minus:
                self.fontZoomRequested.emit(-1)
                return
            if event.key() == Qt.Key_0:
                self.fontZoomRequested.emit(0)
                return
        if self.completion_popup.isVisible():
            if event.key() in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab, Qt.Key_Escape):
                self.completion_popup.keyPressEvent(event)
                return

        typed = event.text()
        if event.modifiers() in (Qt.NoModifier, Qt.ShiftModifier) and typed in self.PAIRS:
            self._insert_pair(typed)
            return
        if event.modifiers() in (Qt.NoModifier, Qt.ShiftModifier) and typed in self.PAIRS.values():
            cursor = self.textCursor()
            if not cursor.hasSelection() and self._character_at(cursor.position()) == typed:
                cursor.movePosition(QTextCursor.NextCharacter)
                self.setTextCursor(cursor)
                return
        if event.key() == Qt.Key_Backspace and self._delete_empty_pair():
            return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not event.modifiers():
            self._insert_indented_newline()
            return

        super().keyPressEvent(event)
        text = event.text()
        if text.isalnum() or text == "_" or text == ".":
            self.trigger_completion()
        elif event.key() == Qt.Key_Space and event.modifiers() == Qt.ControlModifier:
            self.trigger_completion(force=True)
        else:
            self.completion_popup.hide()

    def _character_at(self, position):
        cursor = self.textCursor()
        cursor.setPosition(position)
        cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
        return cursor.selectedText()

    def _insert_pair(self, opening):
        cursor = self.textCursor()
        closing = self.PAIRS[opening]
        selected = cursor.selectedText()
        cursor.beginEditBlock()
        if selected:
            cursor.insertText(opening + selected + closing)
            cursor.movePosition(QTextCursor.Left)
        else:
            cursor.insertText(opening + closing)
            cursor.movePosition(QTextCursor.Left)
        cursor.endEditBlock()
        self.setTextCursor(cursor)

    def _delete_empty_pair(self):
        cursor = self.textCursor()
        if cursor.hasSelection() or cursor.position() == 0:
            return False
        previous = self._character_at(cursor.position() - 1)
        following = self._character_at(cursor.position())
        if self.PAIRS.get(previous) != following:
            return False
        cursor.beginEditBlock()
        cursor.deletePreviousChar()
        cursor.deleteChar()
        cursor.endEditBlock()
        self.setTextCursor(cursor)
        return True

    def _insert_indented_newline(self):
        cursor = self.textCursor()
        block_text = cursor.block().text()
        indent = re.match(r"[ \t]*", block_text).group(0)
        before = block_text[:cursor.positionInBlock()].rstrip()
        after = block_text[cursor.positionInBlock():].lstrip()
        cursor.beginEditBlock()
        if (not cursor.hasSelection() and before and after
                and self.PAIRS.get(before[-1:]) == after[:1]):
            cursor.insertText("\n" + indent + "    \n" + indent)
            cursor.movePosition(QTextCursor.Up)
            cursor.movePosition(QTextCursor.EndOfLine)
        else:
            if before.endswith(":"):
                indent += "    "
            cursor.insertText("\n" + indent)
        cursor.endEditBlock()
        self.setTextCursor(cursor)

    def set_font_size(self, size):
        self._font_size = max(7, min(40, int(size)))
        font = self.font()
        font.setPointSize(self._font_size)
        self.setFont(font)
        self.setStyleSheet(
            f"QPlainTextEdit {{ background-color:{self.theme.bg}; color:{self.theme.fg}; "
            f"border: none; selection-background-color:{self.theme.selection}; "
            f"font-size:{self._font_size}pt; }}"
        )
        self.setTabStopDistance(QFontMetricsF(font).horizontalAdvance(" ") * 4)
        self.update_line_number_area_width(0)

    def change_font_size(self, delta):
        self.set_font_size(self._font_size + delta)

    def trigger_completion(self, force=False):
        prefix = self.current_word_prefix()
        cursor = self.textCursor()
        line_text = cursor.block().text()[:cursor.positionInBlock()]
        if re.search(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\.(?:[A-Za-z_]\w*)?$", line_text):
            self.completionRequested.emit(cursor.blockNumber(), cursor.positionInBlock())
            return
        if not force and len(prefix) < 2:
            self.completion_popup.hide()
            return
        # Instant local word completion for non-member identifiers.
        words = self.local_word_candidates(prefix)
        if words:
            self._show_popup(words)

    def show_completions(self, items):
        prefix = self.current_word_prefix()
        words = [it for it in items if it.lower().startswith(prefix.lower())] or items
        if words:
            self._show_popup(words)

    def _show_popup(self, words):
        cursor_rect = self.cursorRect()
        global_pos = self.mapToGlobal(cursor_rect.bottomLeft())
        self.completion_popup.show_words(words, global_pos)

    def accept_completion(self, word):
        cursor = self.textCursor()
        cursor.select(QTextCursor.WordUnderCursor)
        cursor.insertText(word)
        self.setTextCursor(cursor)
        self.completion_popup.hide()
