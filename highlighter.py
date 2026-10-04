"""Lightweight, fast Python syntax highlighter using regex rules only
(no AST/tokenize pass) so it stays cheap on every keystroke."""
import re
from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont

KEYWORDS = [
    "False", "None", "True", "and", "as", "assert", "async", "await",
    "break", "class", "continue", "def", "del", "elif", "else", "except",
    "finally", "for", "from", "global", "if", "import", "in", "is",
    "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try",
    "while", "with", "yield", "match", "case",
]

BUILTINS = [
    "print", "len", "range", "str", "int", "float", "bool", "list", "dict",
    "set", "tuple", "object", "super", "self", "Exception", "isinstance",
    "enumerate", "zip", "map", "filter", "open", "type", "staticmethod",
    "classmethod", "property",
]


class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document, theme):
        super().__init__(document)
        self.theme = theme
        self.rules = []
        self._build_rules()

    def _fmt(self, color, bold=False, italic=False):
        f = QTextCharFormat()
        f.setForeground(QColor(color))
        if bold:
            f.setFontWeight(QFont.Bold)
        if italic:
            f.setFontItalic(True)
        return f

    def _build_rules(self):
        t = self.theme
        kw_fmt = self._fmt(t.keyword, bold=True)
        builtin_fmt = self._fmt(t.function)
        string_fmt = self._fmt(t.string)
        comment_fmt = self._fmt(t.comment, italic=True)
        number_fmt = self._fmt(t.number)
        def_fmt = self._fmt(t.function, bold=True)
        class_fmt = self._fmt(t.klass, bold=True)
        decorator_fmt = self._fmt(t.warning)
        self_fmt = self._fmt(t.klass, italic=True)

        self.rules = []
        for kw in KEYWORDS:
            self.rules.append((QRegularExpression(rf"\b{kw}\b"), kw_fmt))
        for b in BUILTINS:
            self.rules.append((QRegularExpression(rf"\b{b}\b"), builtin_fmt))

        self.rules.append((QRegularExpression(r"\bdef\s+(\w+)"), def_fmt))
        self.rules.append((QRegularExpression(r"\bclass\s+(\w+)"), class_fmt))
        self.rules.append((QRegularExpression(r"@\w+(\.\w+)*"), decorator_fmt))
        self.rules.append((QRegularExpression(r"\bself\b|\bcls\b"), self_fmt))
        self.rules.append((QRegularExpression(r"\b[0-9]+(\.[0-9]+)?\b"), number_fmt))
        self.rules.append((QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), string_fmt))
        self.rules.append((QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), string_fmt))
        self.rules.append((QRegularExpression(r"#[^\n]*"), comment_fmt))

        self.string_fmt = string_fmt
        self.triple_fmt = string_fmt

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)

        # Triple-quoted strings spanning multiple blocks (state machine)
        self._highlight_triple(text, '"""', 1)
        self._highlight_triple(text, "'''", 3)

    def _highlight_triple(self, text, delim, state_id):
        start_idx = 0
        in_triple = self.previousBlockState() == state_id
        if in_triple:
            end_idx = text.find(delim)
            if end_idx == -1:
                self.setFormat(0, len(text), self.triple_fmt)
                self.setCurrentBlockState(state_id)
                return
            else:
                self.setFormat(0, end_idx + len(delim), self.triple_fmt)
                start_idx = end_idx + len(delim)

        while True:
            start = text.find(delim, start_idx)
            if start == -1:
                break
            end = text.find(delim, start + len(delim))
            if end == -1:
                self.setFormat(start, len(text) - start, self.triple_fmt)
                self.setCurrentBlockState(state_id)
                return
            self.setFormat(start, end + len(delim) - start, self.triple_fmt)
            start_idx = end + len(delim)
