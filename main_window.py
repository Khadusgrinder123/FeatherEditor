import os
import sys
from PySide6.QtCore import Qt, QTimer, QSettings
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QFileDialog, QMessageBox, QToolBar, QTreeView,
    QSplitter, QWidget, QVBoxLayout, QLabel, QStatusBar,
    QApplication, QFileSystemModel, QPushButton, QDialog, QLineEdit,
    QHBoxLayout, QInputDialog
)

import nord
from editor import CodeEditor
from python_completion import complete_members
from visual_debugger import VisualInterpreterDialog


class EditorTab(CodeEditor):
    def __init__(self, theme, file_path=None):
        super().__init__(theme)
        self.file_path = file_path
        self.version = 1


class FindReplaceDialog(QDialog):
    def __init__(self, main_window, replace_mode=False):
        super().__init__(main_window)
        self.main_window = main_window
        self.replace_mode = replace_mode
        self.setWindowTitle("Find and Replace" if replace_mode else "Find")
        self.setWindowFlags(self.windowFlags() | Qt.Tool)
        layout = QVBoxLayout(self)
        find_row = QHBoxLayout()
        find_row.addWidget(QLabel("Find"))
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Text to find")
        find_row.addWidget(self.find_input, 1)
        layout.addLayout(find_row)
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Replace with")
        if replace_mode:
            replace_row = QHBoxLayout()
            replace_row.addWidget(QLabel("Replace"))
            replace_row.addWidget(self.replace_input, 1)
            layout.addLayout(replace_row)
        buttons = QHBoxLayout()
        next_button = QPushButton("Find Next")
        next_button.clicked.connect(self.find_next)
        buttons.addWidget(next_button)
        if replace_mode:
            replace_button = QPushButton("Replace")
            replace_button.clicked.connect(self.replace_current)
            replace_all_button = QPushButton("Replace All")
            replace_all_button.clicked.connect(self.replace_all)
            buttons.addWidget(replace_button)
            buttons.addWidget(replace_all_button)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)
        self.find_input.returnPressed.connect(self.find_next)
        self.resize(520, 90 if not replace_mode else 130)

    def _editor(self):
        return self.main_window.tabs.currentWidget()

    def find_next(self):
        editor = self._editor()
        needle = self.find_input.text()
        if editor is None or not needle:
            return
        cursor = editor.textCursor()
        found = editor.document().find(needle, cursor)
        if found.isNull():
            found = editor.document().find(needle, 0)
        if found.isNull():
            self.main_window.status.showMessage(f"'{needle}' not found", 2500)
            return
        editor.setTextCursor(found)
        editor.setFocus()

    def replace_current(self):
        editor = self._editor()
        needle = self.find_input.text()
        if editor is None or not needle:
            return
        cursor = editor.textCursor()
        if cursor.hasSelection() and cursor.selectedText().casefold() == needle.casefold():
            cursor.insertText(self.replace_input.text())
            editor.setTextCursor(cursor)
        self.find_next()

    def replace_all(self):
        editor = self._editor()
        needle = self.find_input.text()
        if editor is None or not needle:
            return
        document = editor.document()
        cursor = document.find(needle)
        count = 0
        edit_cursor = editor.textCursor()
        edit_cursor.beginEditBlock()
        while not cursor.isNull():
            cursor.insertText(self.replace_input.text())
            count += 1
            cursor = document.find(needle, cursor)
        edit_cursor.endEditBlock()
        self.main_window.status.showMessage(f"Replaced {count} occurrence(s)", 2500)


class MainWindow(QMainWindow):
    def __init__(self, workspace_root=None):
        super().__init__()
        self.setWindowTitle("FeatherEditor")
        self.resize(1200, 800)

        workspace_root = os.path.abspath(workspace_root or os.getcwd())
        self._initial_file = workspace_root if os.path.isfile(workspace_root) else None
        self.workspace_root = os.path.dirname(workspace_root) if self._initial_file else workspace_root
        self.editor_font_size = 11
        self.wrap_enabled = False
        self.recent_files = QSettings("FeatherEditor", "FeatherEditor").value(
            "recentFiles", [], type=list
        )
        self.find_dialog = None
        self.theme = nord.DARK
        self._debugger_dialog = None

        self._build_ui()
        self.apply_theme(self.theme)
        self.new_file()
        if self._initial_file:
            self.open_file(self._initial_file)

    # ------------------------------------------------------------------
    def _build_ui(self):
        # File tree
        self.fs_model = QFileSystemModel()
        self.fs_model.setRootPath(self.workspace_root)
        self.tree = QTreeView()
        self.tree.setModel(self.fs_model)
        self.tree.setRootIndex(self.fs_model.index(self.workspace_root))
        self.tree.setHeaderHidden(True)
        for col in (1, 2, 3):
            self.tree.hideColumn(col)
        self.tree.doubleClicked.connect(self._open_from_tree)

        self.workspace_label = QLabel(os.path.basename(self.workspace_root) or self.workspace_root)
        self.workspace_label.setObjectName("workspaceLabel")
        self.workspace_label.setToolTip(self.workspace_root)
        self.open_folder_button = QPushButton("＋  Open Folder")
        self.open_folder_button.setObjectName("folderButton")
        self.open_folder_button.clicked.connect(self.open_folder_dialog)
        explorer = QWidget()
        explorer.setObjectName("explorerPanel")
        explorer_layout = QVBoxLayout(explorer)
        explorer_layout.setContentsMargins(12, 14, 10, 10)
        explorer_layout.setSpacing(9)
        explorer_heading = QLabel("EXPLORER")
        explorer_heading.setObjectName("sectionHeading")
        explorer_layout.addWidget(explorer_heading)
        explorer_layout.addWidget(self.workspace_label)
        explorer_layout.addWidget(self.open_folder_button)
        explorer_layout.addWidget(self.tree, 1)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(explorer)
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([270, 930])
        self.setCentralWidget(splitter)

        self._build_toolbar()
        self._build_menu()

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.completion_status_label = QLabel("Python completion · ready")
        self.status.addPermanentWidget(self.completion_status_label)
        self.memory_label = QLabel("RAM · —")
        self.memory_label.setToolTip("Resident memory used by FeatherEditor")
        self.status.addPermanentWidget(self.memory_label)
        self._memory_timer = QTimer(self)
        self._memory_timer.timeout.connect(self._update_memory_usage)
        self._memory_timer.start(1500)
        self._update_memory_usage()

    def _build_toolbar(self):
        tb = QToolBar("Main")
        tb.setMovable(False)
        self.addToolBar(tb)

        new_act = QAction("New", self)
        new_act.setShortcut(QKeySequence.New)
        new_act.triggered.connect(self.new_file)
        tb.addAction(new_act)

        open_act = QAction("Open", self)
        open_act.setShortcut(QKeySequence.Open)
        open_act.triggered.connect(self.open_file_dialog)
        tb.addAction(open_act)

        save_act = QAction("Save", self)
        save_act.setShortcut(QKeySequence.Save)
        save_act.triggered.connect(self.save_current)
        tb.addAction(save_act)

        undo_act = QAction("Undo", self)
        undo_act.setShortcut(QKeySequence.Undo)
        undo_act.triggered.connect(self.undo_current)
        self.addAction(undo_act)
        tb.addAction(undo_act)

        redo_act = QAction("Redo", self)
        redo_act.setShortcut(QKeySequence.Redo)
        redo_act.triggered.connect(self.redo_current)
        self.addAction(redo_act)
        tb.addAction(redo_act)

        run_act = QAction("Run", self)
        run_act.setShortcut("F5")
        run_act.triggered.connect(self.run_current)
        tb.addAction(run_act)

        debug_act = QAction("Step Through", self)
        debug_act.setShortcut("F10")
        debug_act.triggered.connect(self.debug_current)
        tb.addAction(debug_act)

        tb.addSeparator()

        theme_menu = self.menuBar().addMenu("&Theme")
        nord_menu = theme_menu.addMenu("Nord")
        nord_dark_act = QAction("Nord Dark", self, checkable=True)
        nord_light_act = QAction("Nord Light (White)", self, checkable=True)
        relaxing_menu = theme_menu.addMenu("Relaxing")
        relaxing_blue_act = QAction("Soft Blue", self, checkable=True)
        relaxing_sage_act = QAction("Muted Sage Green", self, checkable=True)
        self._theme_actions = {
            nord.DARK: nord_dark_act,
            nord.LIGHT: nord_light_act,
            nord.RELAXING_BLUE: relaxing_blue_act,
            nord.RELAXING_SAGE: relaxing_sage_act,
        }
        for theme, action in self._theme_actions.items():
            action.triggered.connect(lambda checked=False, selected=theme: self.apply_theme(selected))
            (nord_menu if theme in (nord.DARK, nord.LIGHT) else relaxing_menu).addAction(action)
        nord_dark_act.setChecked(True)
        theme_act = QAction("Themes ▾", self)
        theme_act.triggered.connect(lambda: theme_menu.popup(self.toolbar.mapToGlobal(self.toolbar.rect().bottomLeft())))
        tb.addAction(theme_act)

        self.toolbar = tb
        folder_act = QAction("Open Folder…", self)
        folder_act.setShortcut("Ctrl+Shift+O")
        folder_act.triggered.connect(self.open_folder_dialog)
        tb.addAction(folder_act)

        self._actions = dict(new=new_act, open=open_act, folder=folder_act,
                  save=save_act, undo=undo_act, redo=redo_act,
                  run=run_act, debug=debug_act, theme=theme_act)

        zoom_in = QAction("Increase Editor Text", self)
        zoom_in.triggered.connect(lambda: self.change_editor_font_size(1))
        zoom_out = QAction("Decrease Editor Text", self)
        zoom_out.triggered.connect(lambda: self.change_editor_font_size(-1))
        zoom_reset = QAction("Reset Editor Text Size", self)
        zoom_reset.triggered.connect(self.reset_editor_font_size)
        self._actions.update(zoom_in=zoom_in, zoom_out=zoom_out, zoom_reset=zoom_reset)

    def _build_menu(self):
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(self._actions["new"])
        file_menu.addAction(self._actions["open"])
        file_menu.addAction(self._actions["folder"])
        file_menu.addAction(self._actions["save"])
        recent_menu = file_menu.addMenu("Open Recent")
        self.recent_menu = recent_menu
        self._refresh_recent_menu()
        file_menu.addSeparator()
        close_tab = QAction("Close Tab", self)
        close_tab.setShortcut("Ctrl+W")
        close_tab.triggered.connect(self.close_current_tab)
        self._actions["close_tab"] = close_tab
        file_menu.addAction(close_tab)
        file_menu.addSeparator()
        quit_act = QAction("Quit", self)
        quit_act.setShortcut(QKeySequence.Quit)
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        edit_menu = self.menuBar().addMenu("&Edit")
        edit_menu.addAction(self._actions["undo"])
        edit_menu.addAction(self._actions["redo"])
        edit_menu.addSeparator()
        find_act = QAction("Find…", self)
        find_act.setShortcut("Ctrl+F")
        find_act.triggered.connect(lambda: self.show_find_dialog(False))
        replace_act = QAction("Find and Replace…", self)
        replace_act.setShortcut("Ctrl+H")
        replace_act.triggered.connect(lambda: self.show_find_dialog(True))
        goto_act = QAction("Go to Line…", self)
        goto_act.setShortcut("Ctrl+G")
        goto_act.triggered.connect(self.go_to_line)
        edit_menu.addAction(find_act)
        edit_menu.addAction(replace_act)
        edit_menu.addAction(goto_act)
        self._actions.update(find=find_act, replace=replace_act, goto=goto_act)

        run_menu = self.menuBar().addMenu("&Run")
        run_menu.addAction(self._actions["run"])
        run_menu.addAction(self._actions["debug"])

        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction(self._actions["theme"])
        view_menu.addSeparator()
        view_menu.addAction(self._actions["zoom_in"])
        view_menu.addAction(self._actions["zoom_out"])
        view_menu.addAction(self._actions["zoom_reset"])
        self.wrap_action = QAction("Word Wrap", self, checkable=True)
        self.wrap_action.setChecked(self.wrap_enabled)
        self.wrap_action.triggered.connect(self.set_word_wrap)
        view_menu.addSeparator()
        view_menu.addAction(self.wrap_action)
        self._actions["wrap"] = self.wrap_action

        self.tabs.currentChanged.connect(self._on_current_tab_changed)
        self._on_current_tab_changed(self.tabs.currentIndex())

    # ---- theme ---------------------------------------------------------
    def apply_theme(self, theme):
        self.theme = theme
        QApplication.instance().setStyleSheet(nord.build_qss(theme))
        for selected_theme, action in self._theme_actions.items():
            action.setChecked(selected_theme is theme)
        for i in range(self.tabs.count()):
            self.tabs.widget(i).apply_theme(theme)

    # ---- tabs / files ----------------------------------------------------
    def new_file(self):
        editor = EditorTab(self.theme)
        editor.set_font_size(self.editor_font_size)
        editor.setLineWrapMode(
            CodeEditor.WidgetWidth if self.wrap_enabled else CodeEditor.NoWrap
        )
        editor.fontZoomRequested.connect(self._on_editor_zoom)
        editor.completionRequested.connect(
            lambda line, col, ed=editor: self._on_completion_requested(ed, line, col))
        idx = self.tabs.addTab(editor, "untitled.py")
        self._bind_editor_actions(editor)
        self.tabs.setCurrentIndex(idx)
        return editor

    def _open_from_tree(self, index):
        path = self.fs_model.filePath(index)
        if os.path.isfile(path):
            self.open_file(path)

    def open_file_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open File", self.workspace_root,
                                               "Python Files (*.py);;All Files (*)")
        if path:
            self.open_file(path)

    def open_folder_dialog(self):
        path = QFileDialog.getExistingDirectory(
            self, "Open Workspace Folder", self.workspace_root,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if path:
            self.set_workspace_root(path)

    def set_workspace_root(self, path):
        path = os.path.abspath(path)
        if not os.path.isdir(path):
            QMessageBox.warning(self, "Open Folder", "Choose an existing folder.")
            return
        self.workspace_root = path
        self.fs_model.setRootPath(path)
        self.tree.setRootIndex(self.fs_model.index(path))
        self.workspace_label.setText(os.path.basename(path) or path)
        self.workspace_label.setToolTip(path)
        self.setWindowTitle(f"FeatherEditor · {os.path.basename(path) or path}")
        self.status.showMessage(f"Workspace opened: {path}", 4000)

    def open_file(self, path):
        path = os.path.abspath(path)
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if getattr(w, "file_path", None) == path:
                self.tabs.setCurrentIndex(i)
                self._add_recent_file(path)
                return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            QMessageBox.warning(self, "Open File", f"Could not open file:\n{e}")
            return
        editor = EditorTab(self.theme, file_path=path)
        editor.set_font_size(self.editor_font_size)
        editor.setLineWrapMode(
            CodeEditor.WidgetWidth if self.wrap_enabled else CodeEditor.NoWrap
        )
        editor.fontZoomRequested.connect(self._on_editor_zoom)
        editor.setPlainText(content)
        editor.completionRequested.connect(
            lambda line, col, ed=editor: self._on_completion_requested(ed, line, col))
        idx = self.tabs.addTab(editor, os.path.basename(path))
        self._bind_editor_actions(editor)
        self.tabs.setCurrentIndex(idx)
        self._add_recent_file(path)

    def _close_tab(self, index):
        self.tabs.removeTab(index)
        if self.tabs.count() == 0:
            self.new_file()

    def close_current_tab(self):
        index = self.tabs.currentIndex()
        if index >= 0:
            self._close_tab(index)

    def _bind_editor_actions(self, editor):
        editor.editorCommandRequested.connect(self._on_editor_command)
        editor.undoAvailable.connect(lambda _available: self._sync_history_actions())
        editor.redoAvailable.connect(lambda _available: self._sync_history_actions())
        self._sync_history_actions()

    def _on_editor_command(self, command):
        commands = {
            "find": lambda: self.show_find_dialog(False),
            "replace": lambda: self.show_find_dialog(True),
            "goto": self.go_to_line,
            "close-tab": self.close_current_tab,
        }
        callback = commands.get(command)
        if callback:
            callback()

    def _on_current_tab_changed(self, _index):
        self._sync_history_actions()

    def _sync_history_actions(self):
        editor = self.tabs.currentWidget()
        self._actions["undo"].setEnabled(bool(editor and editor.document().isUndoAvailable()))
        self._actions["redo"].setEnabled(bool(editor and editor.document().isRedoAvailable()))

    def undo_current(self):
        editor = self.tabs.currentWidget()
        if editor is not None:
            editor.undo()

    def redo_current(self):
        editor = self.tabs.currentWidget()
        if editor is not None:
            editor.redo()

    def show_find_dialog(self, replace_mode=False):
        if self.find_dialog is not None:
            self.find_dialog.close()
        self.find_dialog = FindReplaceDialog(self, replace_mode)
        editor = self.tabs.currentWidget()
        if editor is not None and editor.textCursor().hasSelection():
            self.find_dialog.find_input.setText(editor.textCursor().selectedText())
        self.find_dialog.show()
        self.find_dialog.find_input.setFocus()
        self.find_dialog.find_input.selectAll()
        return self.find_dialog

    def go_to_line(self):
        editor = self.tabs.currentWidget()
        if editor is None:
            return
        current_line = editor.textCursor().blockNumber() + 1
        line, accepted = QInputDialog.getInt(
            self, "Go to Line", "Line number:", current_line, 1,
            max(1, editor.blockCount()),
        )
        if not accepted:
            return
        cursor = editor.textCursor()
        cursor.setPosition(editor.document().findBlockByNumber(line - 1).position())
        editor.setTextCursor(cursor)
        editor.setFocus()

    def set_word_wrap(self, enabled):
        self.wrap_enabled = bool(enabled)
        mode = CodeEditor.WidgetWidth if self.wrap_enabled else CodeEditor.NoWrap
        for index in range(self.tabs.count()):
            self.tabs.widget(index).setLineWrapMode(mode)
        self.status.showMessage(
            "Word wrap enabled" if self.wrap_enabled else "Word wrap disabled", 2000
        )

    def _add_recent_file(self, path):
        path = os.path.abspath(path)
        self.recent_files = [path] + [item for item in self.recent_files if item != path]
        self.recent_files = self.recent_files[:10]
        QSettings("FeatherEditor", "FeatherEditor").setValue("recentFiles", self.recent_files)
        self._refresh_recent_menu()

    def _refresh_recent_menu(self):
        if not hasattr(self, "recent_menu"):
            return
        self.recent_menu.clear()
        existing = [path for path in self.recent_files if os.path.isfile(path)]
        self.recent_files = existing[:10]
        QSettings("FeatherEditor", "FeatherEditor").setValue("recentFiles", self.recent_files)
        if not existing:
            empty = self.recent_menu.addAction("No recent files")
            empty.setEnabled(False)
        else:
            for path in existing:
                action = self.recent_menu.addAction(path)
                action.setToolTip(path)
                action.triggered.connect(lambda checked=False, selected=path: self.open_file(selected))
            self.recent_menu.addSeparator()
            clear_action = self.recent_menu.addAction("Clear Recent Files")
            clear_action.triggered.connect(self.clear_recent_files)

    def clear_recent_files(self):
        self.recent_files = []
        QSettings("FeatherEditor", "FeatherEditor").setValue("recentFiles", [])
        self._refresh_recent_menu()

    def save_current(self):
        editor = self.tabs.currentWidget()
        if editor is None:
            return
        if not editor.file_path:
            path, _ = QFileDialog.getSaveFileName(self, "Save File", self.workspace_root,
                                                   "Python Files (*.py);;All Files (*)")
            if not path:
                return
            editor.file_path = path
            self.tabs.setTabText(self.tabs.currentIndex(), os.path.basename(path))
            self._add_recent_file(path)
        try:
            with open(editor.file_path, "w", encoding="utf-8") as f:
                f.write(editor.toPlainText())
            self._add_recent_file(editor.file_path)
            self.status.showMessage(f"Saved {editor.file_path}", 3000)
        except Exception as e:
            QMessageBox.warning(self, "Save File", f"Could not save file:\n{e}")

    def run_current(self):
        editor = self.tabs.currentWidget()
        if editor is None:
            return
        self.save_current()
        if not editor.file_path:
            return
        import subprocess
        self.status.showMessage(f"Running {editor.file_path} ...")
        try:
            result = subprocess.run([sys.executable, editor.file_path],
                                     capture_output=True, text=True, timeout=30)
            output = result.stdout + (("\n" + result.stderr) if result.stderr else "")
            QMessageBox.information(self, f"Output: {os.path.basename(editor.file_path)}",
                                     output.strip() or "(no output)")
        except Exception as e:
            QMessageBox.warning(self, "Run", f"Failed to run:\n{e}")
        self.status.showMessage("Ready", 2000)

    def debug_current(self):
        editor = self.tabs.currentWidget()
        if editor is None:
            return
        dialog = VisualInterpreterDialog(
            editor.toPlainText(), editor.file_path, self.theme, self,
            working_directory=self.workspace_root,
        )
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        self._debugger_dialog = dialog
        dialog.destroyed.connect(lambda: setattr(self, "_debugger_dialog", None))

    def change_editor_font_size(self, delta):
        self.editor_font_size = max(7, min(40, self.editor_font_size + delta))
        for index in range(self.tabs.count()):
            self.tabs.widget(index).set_font_size(self.editor_font_size)
        self.status.showMessage(f"Editor text size: {self.editor_font_size} pt", 1800)

    def reset_editor_font_size(self):
        self.editor_font_size = 11
        for index in range(self.tabs.count()):
            self.tabs.widget(index).set_font_size(self.editor_font_size)
        self.status.showMessage("Editor text size reset", 1800)

    def _on_editor_zoom(self, amount):
        if amount == 0:
            self.reset_editor_font_size()
        else:
            self.change_editor_font_size(amount)

    def _update_memory_usage(self):
        try:
            with open("/proc/self/statm", "r", encoding="ascii") as statm:
                resident_pages = int(statm.read().split()[1])
            memory_mb = resident_pages * os.sysconf("SC_PAGE_SIZE") / (1024 * 1024)
            self.memory_label.setText(f"RAM · {memory_mb:.0f} MB")
        except (OSError, IndexError, ValueError):
            self.memory_label.setText("RAM · n/a")

    def closeEvent(self, event):
        if self._debugger_dialog is not None:
            self._debugger_dialog.close()
        super().closeEvent(event)

    def _on_completion_requested(self, editor, line, col):
        words = complete_members(editor.toPlainText(), line, col, self.workspace_root)
        if words:
            editor.show_completions(words)
            self.completion_status_label.setText(f"Python completion · {len(words)} members")
        else:
            editor.completion_popup.hide()
            self.completion_status_label.setText("Python completion · no members found")
