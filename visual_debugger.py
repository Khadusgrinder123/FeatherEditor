"""A subprocess-backed, line-by-line Python execution visualizer."""
import json
import os
import tempfile
import textwrap
import sys

from PySide6.QtCore import Qt, QProcess
from PySide6.QtGui import QColor, QTextCursor, QTextFormat, QFont
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QSplitter, QTextEdit,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from .highlighter import PythonHighlighter


_RUNNER = textwrap.dedent(r'''
    import json
    import linecache
    import os
    import sys
    import traceback

    source_path = os.path.realpath(sys.argv[1])
    target = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else source_path
    with open(source_path, "r", encoding="utf-8") as stream:
        source = stream.read()
    sys.path.insert(0, os.path.dirname(target))
    code = compile(source, target, "exec")
    linecache.cache[target] = (len(source), None, source.splitlines(True), target)
    stepping = True
    step_number = 0

    def emit(kind, **payload):
        message = {"kind": kind, **payload}
        sys.__stdout__.write(json.dumps(message, ensure_ascii=False) + "\n")
        sys.__stdout__.flush()

    class WireStream:
        def __init__(self, name):
            self.name = name
        def write(self, value):
            if value:
                emit("output", stream=self.name, text=value)
            return len(value)
        def flush(self):
            pass
        def isatty(self):
            return False

    def visual_input(prompt=""):
        if prompt:
            emit("output", stream="stdout", text=str(prompt))
        emit("input_request", prompt=str(prompt))
        message = sys.stdin.readline()
        try:
            response = json.loads(message)
        except ValueError as error:
            raise EOFError("Visual interpreter input was closed") from error
        if response.get("action") != "input":
            raise EOFError("Visual interpreter input was closed")
        return str(response.get("value", ""))

    def safe_repr(value):
        try:
            result = repr(value)
        except BaseException as error:
            result = "<repr failed: " + type(error).__name__ + ">"
        return result[:500] + ("…" if len(result) > 500 else "")

    def trace(frame, event, arg):
        global stepping, step_number
        if frame.f_code.co_filename != target:
            return None
        if event == "line" and stepping:
            step_number += 1
            variables = []
            for name, value in sorted(frame.f_locals.items()):
                if name != "__builtins__":
                    variables.append({"name": name, "type": type(value).__name__, "value": safe_repr(value)})
            emit("pause", line=frame.f_lineno, step=step_number, variables=variables)
            command = sys.stdin.readline()
            try:
                action = json.loads(command).get("action", "step")
            except (ValueError, AttributeError):
                action = "stop"
            if action == "continue":
                stepping = False
            elif action == "stop":
                raise SystemExit
        return trace

    import builtins
    run_builtins = dict(vars(builtins))
    run_builtins["input"] = visual_input
    namespace = {"__name__": "__main__", "__file__": target, "__builtins__": run_builtins}
    original_stdout, original_stderr = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = WireStream("stdout"), WireStream("stderr")
    try:
        sys.settrace(trace)
        exec(code, namespace, namespace)
        emit("done", status="finished")
    except SystemExit:
        emit("done", status="stopped")
    except BaseException:
        emit("exception", traceback=traceback.format_exc())
        emit("done", status="error")
    finally:
        sys.settrace(None)
        sys.stdout, sys.stderr = original_stdout, original_stderr
''')


class VisualInterpreterDialog(QDialog):
    """Run the current buffer in a child process, pausing at each Python line."""

    def __init__(self, source, file_path, theme, parent=None, working_directory=None):
        super().__init__(parent)
        self.theme = theme
        self.file_path = file_path or "untitled.py"
        self.working_directory = os.path.abspath(
            working_directory or os.path.dirname(self.file_path) or os.getcwd()
        )
        self._stdout_buffer = b""
        self._temp_path = None
        self._step_count = 0
        self.setWindowTitle("Feather · Visual Interpreter")
        self.resize(1120, 760)
        self.setMinimumSize(620, 420)
        self.setWindowFlags(Qt.Window | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setSizeGripEnabled(True)
        self._build_ui(source)
        self._start_process(source)

    def _build_ui(self, source):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(12)

        heading = QHBoxLayout()
        title = QLabel("VISUAL INTERPRETER")
        title.setObjectName("debugTitle")
        heading.addWidget(title)
        heading.addStretch(1)
        self.step_label = QLabel("Preparing your program…")
        self.step_label.setObjectName("debugStatus")
        heading.addWidget(self.step_label)
        root.addLayout(heading)

        content = QSplitter(Qt.Horizontal)
        source_panel = QWidget()
        source_layout = QVBoxLayout(source_panel)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.addWidget(QLabel("SOURCE · LIVE EXECUTION"))
        self.source_view = QPlainTextEdit()
        self.source_view.setReadOnly(True)
        self.source_view.setFont(QFont("JetBrains Mono", 11))
        self.source_view.setPlainText(source)
        self.source_highlighter = PythonHighlighter(self.source_view.document(), self.theme)
        source_layout.addWidget(self.source_view, 1)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel("LIVE VARIABLES · NAME / TYPE / VALUE"))
        self.variables = QTreeWidget()
        self.variables.setHeaderLabels(["Variable", "Value"])
        self.variables.setColumnWidth(0, 150)
        self.variables.setAlternatingRowColors(True)
        right_layout.addWidget(self.variables, 3)
        right_layout.addWidget(QLabel("PROGRAM OUTPUT"))
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumBlockCount(1500)
        self.output.setMinimumHeight(150)
        self.output.setFont(QFont("JetBrains Mono", 10))
        right_layout.addWidget(self.output, 2)
        input_row = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Program is waiting for input…")
        self.input_field.returnPressed.connect(self._send_input)
        input_send = QPushButton("Send")
        input_send.clicked.connect(self._send_input)
        input_row.addWidget(self.input_field, 1)
        input_row.addWidget(input_send)
        right_layout.addLayout(input_row)
        self.input_field.hide()
        input_send.hide()
        self._input_send_button = input_send

        content.addWidget(source_panel)
        content.addWidget(right_panel)
        content.setStretchFactor(0, 3)
        content.setStretchFactor(1, 2)
        root.addWidget(content, 1)

        footer = QHBoxLayout()
        hint = QLabel("Step through assignments, branches, loops, and function calls.")
        hint.setObjectName("debugHint")
        footer.addWidget(hint)
        footer.addStretch(1)
        self.step_button = QPushButton("Step  ·  F10")
        self.step_button.setObjectName("primaryButton")
        self.step_button.clicked.connect(self.step_once)
        self.continue_button = QPushButton("Continue  ·  F5")
        self.continue_button.clicked.connect(self.continue_run)
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_run)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        for button in (self.step_button, self.continue_button, self.stop_button, close_button):
            footer.addWidget(button)
        root.addLayout(footer)

        self.step_button.setShortcut("F10")
        self.continue_button.setShortcut("F5")
        self.setStyleSheet(f"""
            QLabel#debugTitle {{ color: {self.theme.accent}; font-size: 15pt; font-weight: 700; letter-spacing: 2px; }}
            QLabel#debugStatus {{ color: {self.theme.fg_dim}; padding: 6px 10px; background: {self.theme.bg_alt}; border: 1px solid {self.theme.border}; }}
            QLabel#debugHint {{ color: {self.theme.fg_dim}; }}
            QPlainTextEdit, QTreeWidget {{ border: 1px solid {self.theme.border}; }}
            QTreeWidget::item {{ padding: 4px; }}
            QPushButton#primaryButton {{ background: {self.theme.accent}; color: {self.theme.accent_fg}; font-weight: 700; }}
        """)

    def _start_process(self, source):
        try:
            suffix = os.path.splitext(self.file_path)[1] or ".py"
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=suffix, delete=False) as stream:
                stream.write(source)
                self._temp_path = stream.name
        except OSError as error:
            self.step_label.setText(f"Could not prepare source: {error}")
            self.step_button.setEnabled(False)
            self.continue_button.setEnabled(False)
            return

        self.process = QProcess(self)
        self.process.setProgram(sys.executable)
        self.process.setWorkingDirectory(self.working_directory)
        self.process.setArguments(["-u", "-c", _RUNNER, self._temp_path, self.file_path])
        self.process.readyReadStandardOutput.connect(self._read_events)
        self.process.readyReadStandardError.connect(self._read_stderr)
        self.process.finished.connect(self._process_finished)
        self.process.errorOccurred.connect(self._process_error)
        self.process.start()
        self.step_label.setText("Starting isolated Python process…")

    def _read_events(self):
        self._stdout_buffer += bytes(self.process.readAllStandardOutput())
        while b"\n" in self._stdout_buffer:
            raw, self._stdout_buffer = self._stdout_buffer.split(b"\n", 1)
            if not raw:
                continue
            try:
                event = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                self.output.appendPlainText(raw.decode("utf-8", errors="replace"))
                continue
            kind = event.get("kind")
            if kind == "pause":
                self._show_pause(event)
            elif kind == "output":
                self._append_output(event.get("text", ""), event.get("stream") == "stderr")
            elif kind == "exception":
                self.output.appendPlainText(event.get("traceback", "Python error"))
            elif kind == "input_request":
                self.step_label.setText("Program is waiting for input")
                self.input_field.show()
                self._input_send_button.show()
                self.input_field.setFocus()
            elif kind == "done":
                self.step_label.setText(f"Program {event.get('status', 'finished')} · {self._step_count} steps")
                self.step_button.setEnabled(False)
                self.continue_button.setEnabled(False)

    def _show_pause(self, event):
        line = max(1, int(event.get("line", 1)))
        self._step_count = int(event.get("step", self._step_count + 1))
        cursor = self.source_view.textCursor()
        cursor.movePosition(QTextCursor.Start)
        for _ in range(line - 1):
            if not cursor.movePosition(QTextCursor.Down):
                break
        self.source_view.setTextCursor(cursor)
        self.source_view.ensureCursorVisible()
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(QColor(self.theme.bg_elevated))
        selection.format.setForeground(QColor(self.theme.accent))
        selection.format.setProperty(QTextFormat.FullWidthSelection, True)
        selection.cursor = cursor
        selection.cursor.select(QTextCursor.LineUnderCursor)
        self.source_view.setExtraSelections([selection])
        self.step_label.setText(f"Paused · line {line} · step {self._step_count}")
        self.variables.clear()
        for variable in event.get("variables", []):
            name = variable.get("name", "")
            value = f"{variable.get('value', '')}    ·    {variable.get('type', 'object')}"
            item = QTreeWidgetItem([name, value])
            item.setToolTip(1, value)
            self.variables.addTopLevelItem(item)
        self.variables.resizeColumnToContents(0)

    def _append_output(self, text, is_error=False):
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.End)
        if is_error:
            fmt = cursor.charFormat()
            fmt.setForeground(QColor(self.theme.error))
            cursor.setCharFormat(fmt)
        cursor.insertText(text)
        self.output.setTextCursor(cursor)
        self.output.ensureCursorVisible()

    def _read_stderr(self):
        text = bytes(self.process.readAllStandardError()).decode("utf-8", errors="replace")
        if text:
            self._append_output(text, True)

    def step_once(self):
        self._send_action("step")

    def continue_run(self):
        self._send_action("continue")
        self.step_label.setText("Running · continue mode")

    def _send_action(self, action):
        if self.process and self.process.state() == QProcess.Running:
            self.process.write((json.dumps({"action": action}) + "\n").encode("utf-8"))

    def _send_input(self):
        if self.process and self.process.state() == QProcess.Running:
            value = self.input_field.text()
            message = json.dumps({"action": "input", "value": value}) + "\n"
            self.process.write(message.encode("utf-8"))
            self.input_field.clear()
            self.input_field.hide()
            self._input_send_button.hide()

    def stop_run(self):
        if self.process and self.process.state() != QProcess.NotRunning:
            self.process.kill()
        self.step_label.setText("Stopping…")

    def _process_error(self, error):
        self.step_label.setText(f"Python process error · {error}")
        self.step_button.setEnabled(False)
        self.continue_button.setEnabled(False)

    def _process_finished(self, *_args):
        self.step_button.setEnabled(False)
        self.continue_button.setEnabled(False)
        if self._temp_path and os.path.exists(self._temp_path):
            try:
                os.unlink(self._temp_path)
            except OSError:
                pass
            self._temp_path = None

    def closeEvent(self, event):
        if self.process and self.process.state() != QProcess.NotRunning:
            self.process.kill()
            self.process.waitForFinished(1000)
        if self._temp_path and os.path.exists(self._temp_path):
            try:
                os.unlink(self._temp_path)
            except OSError:
                pass
        super().closeEvent(event)
