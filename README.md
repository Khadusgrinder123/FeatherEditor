# FeatherEditor

A lightweight Python IDE built with PySide6.

## Features

- **Two theme families** — Nord is the default and includes Nord Dark and Nord
  Light (white). Relaxing offers Soft Blue and Muted Sage Green; these are independent
  palettes, not dark/light variants. Choose from **Theme** or the **Themes**
  toolbar button.
- **Sharp, square buttons** — every control (`QPushButton`, `QToolButton`,
  tabs, inputs, scrollbars) is styled with `border-radius: 0px`. No rounded corners anywhere.
- **Built-in Python member completion** — after an imported module, imported
  name, or inferred local variable and a dot, FeatherEditor lists available
  members without starting a language server. It includes
  Python's full public `list` API, such as `append`, `extend`, `insert`, `pop`,
  `remove`, `sort`, and `clear`.
- **Workspace explorer** — open a folder as the workspace and browse its
  files and subfolders from the sidebar; folders can also be supplied on the
  command line.
- **Smart editing** — matching `()`, `[]`, `{}`, single quotes, and double
  quotes are inserted automatically. Backspace removes an empty pair, and
  Enter preserves indentation. Use **Ctrl++** to zoom in, **Ctrl+-** to zoom
  out, and **Ctrl+0** to reset.
- **Editor essentials** — Find/Replace, Undo/Redo, close-tab, Open Recent,
  Go to Line, and a toggle for word wrapping are available from the menus and
  shortcuts below.
- **Live memory indicator** — the status bar reports FeatherEditor's resident
  memory usage.
- **Visual interpreter** — **Run → Step Through** (F10) executes the current
  buffer in a child Python process, pauses on each source line, and shows live
  variables and output. Step with F10, continue with F5, and answer `input()`
  prompts in the debugger panel. This is not a security sandbox; user code
  runs with the same permissions as FeatherEditor.

## Install & run

```bash
pip install -r requirements.txt
python3 main.py [optional/workspace/folder]
```

## Layout

```
FeatherEditor/
  main.py                   entry point
  nord.py                   Nord palette + QSS theme builder
  highlighter.py             regex-based Python syntax highlighter
  editor.py                  CodeEditor widget (gutter, completion popup)
  python_completion.py       in-process import/member introspection
  visual_debugger.py          resizable step-through execution window
  main_window.py              tabs, file tree, toolbar, menu, status bar
```

## Shortcuts

| Action        | Shortcut |
|---------------|----------|
| New file      | Ctrl+N   |
| Open file     | Ctrl+O   |
| Open workspace folder | Ctrl+Shift+O |
| Open recent file | File → Open Recent |
| Save file     | Ctrl+S   |
| Close current tab | Ctrl+W |
| Undo / Redo | Ctrl+Z / Ctrl+Y |
| Find / Replace | Ctrl+F / Ctrl+H |
| Go to line | Ctrl+G |
| Toggle word wrap | View → Word Wrap |
| Run file      | F5       |
| Step through  | F10      |
| Zoom in / out / reset | Ctrl++ / Ctrl+- / Ctrl+0 |
| Force autocomplete | Ctrl+Space |




This thing is vibe coded not coded by me sorry for it i wont include it as my real project :(
