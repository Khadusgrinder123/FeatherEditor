"""Nord color palette (https://www.nordtheme.com) and the two FeatherEditor
themes built from it: nord-dark and nord-light. Everything in the app's QSS
is generated from these tokens, and buttons are always sharp (0px radius).
"""

# --- Canonical Nord palette -------------------------------------------------
NORD0 = "#2E3440"
NORD1 = "#3B4252"
NORD2 = "#434C5E"
NORD3 = "#4C566A"
NORD4 = "#D8DEE9"
NORD5 = "#E5E9F0"
NORD6 = "#ECEFF4"
NORD7 = "#8FBCBB"
NORD8 = "#88C0D0"
NORD9 = "#81A1C1"
NORD10 = "#5E81AC"
NORD11 = "#BF616A"  # red
NORD12 = "#D08770"  # orange
NORD13 = "#EBCB8B"  # yellow
NORD14 = "#A3BE8C"  # green
NORD15 = "#B48EAD"  # purple

# Buttons are square everywhere: no rounded corners, ever.
RADIUS = "0px"


class Theme:
    def __init__(self, name, bg, bg_alt, bg_elevated, fg, fg_dim, border,
                 accent, accent_fg, selection, keyword, string, comment,
                 number, function, klass, error, warning):
        self.name = name
        self.bg = bg
        self.bg_alt = bg_alt
        self.bg_elevated = bg_elevated
        self.fg = fg
        self.fg_dim = fg_dim
        self.border = border
        self.accent = accent
        self.accent_fg = accent_fg
        self.selection = selection
        self.keyword = keyword
        self.string = string
        self.comment = comment
        self.number = number
        self.function = function
        self.klass = klass
        self.error = error
        self.warning = warning


DARK = Theme(
    name="Nord Dark",
    bg=NORD0, bg_alt=NORD1, bg_elevated=NORD2,
    fg=NORD6, fg_dim=NORD4,
    border=NORD3,
    accent=NORD8, accent_fg=NORD0,
    selection=NORD3,
    keyword=NORD9, string=NORD14, comment=NORD3,
    number=NORD15, function=NORD8, klass=NORD7,
    error=NORD11, warning=NORD13,
)

LIGHT = Theme(
    name="Nord Light",
    bg=NORD6, bg_alt=NORD5, bg_elevated=NORD4,
    fg=NORD0, fg_dim=NORD2,
    border=NORD3,
    accent=NORD10, accent_fg=NORD6,
    selection=NORD4,
    keyword=NORD10, string=NORD7, comment=NORD3,
    number=NORD15, function=NORD9, klass=NORD12,
    error=NORD11, warning="#9A7B21",
)

RELAXING_BLUE = Theme(
    name="Relaxing · Soft Blue",
    bg="#202B3C", bg_alt="#26364A", bg_elevated="#31455C",
    fg="#D9E6F2", fg_dim="#9FB3C8", border="#425A73",
    accent="#83B5D1", accent_fg="#172635", selection="#39516B",
    keyword="#9ABBDD", string="#A9C89F", comment="#71869A",
    number="#C5A9D4", function="#8FC8D9", klass="#A7C8D7",
    error="#D98282", warning="#D9BC85",
)

RELAXING_SAGE = Theme(
    name="Relaxing · Muted Sage Green",
    bg="#242F2B", bg_alt="#2D3B35", bg_elevated="#38483F",
    fg="#E0E9E0", fg_dim="#AEBDB1", border="#53665A",
    accent="#A6C5A5", accent_fg="#243129", selection="#435A4C",
    keyword="#B2C99D", string="#B9CE9B", comment="#879B8D",
    number="#D5B38A", function="#9BC8B5", klass="#B8D2AF",
    error="#D7877F", warning="#D8C18E",
)


def build_qss(t: Theme) -> str:
    """Build the application stylesheet for a given theme. All buttons and
    inputs use square (0px radius) corners by design."""
    return f"""
    QWidget {{
        background-color: {t.bg};
        color: {t.fg};
        font-family: "JetBrains Mono", "Cascadia Code", Consolas, monospace;
        font-size: 10pt;
    }}

    QMainWindow, QDialog {{
        background-color: {t.bg};
    }}

    /* ---- Sharp, square buttons everywhere ---- */
    QPushButton, QToolButton {{
        background-color: {t.bg_elevated};
        color: {t.fg};
        border: 1px solid {t.border};
        border-radius: {RADIUS};
        padding: 7px 13px;
    }}
    QPushButton:hover, QToolButton:hover {{
        background-color: {t.border};
    }}
    QPushButton:pressed, QToolButton:pressed {{
        background-color: {t.accent};
        color: {t.accent_fg};
    }}
    QPushButton:disabled, QToolButton:disabled {{
        color: {t.fg_dim};
        background-color: {t.bg_alt};
    }}
    QPushButton:default {{
        border: 1px solid {t.accent};
    }}

    QToolBar {{
        background-color: {t.bg_alt};
        border: 0px;
        border-bottom: 1px solid {t.border};
        spacing: 5px;
        padding: 6px 8px;
    }}
    QToolBar QToolButton {{
        border-radius: {RADIUS};
    }}
    QToolBar::separator {{
        background-color: {t.border};
        width: 1px;
        margin: 5px 8px;
    }}

    QMenuBar {{
        background-color: {t.bg_alt};
        color: {t.fg};
        border-bottom: 1px solid {t.border};
    }}
    QMenuBar::item:selected {{
        background-color: {t.border};
    }}
    QMenu {{
        background-color: {t.bg_alt};
        color: {t.fg};
        border: 1px solid {t.border};
        border-radius: {RADIUS};
    }}
    QMenu::item:selected {{
        background-color: {t.accent};
        color: {t.accent_fg};
    }}

    QStatusBar {{
        background-color: {t.bg_alt};
        color: {t.fg_dim};
        border-top: 1px solid {t.border};
        padding: 3px 8px;
    }}
    QStatusBar::item {{
        border: 0;
    }}

    QTabWidget::pane {{
        border: 1px solid {t.border};
        top: -1px;
        background-color: {t.bg};
    }}
    QTabBar::tab {{
        background-color: {t.bg_alt};
        color: {t.fg_dim};
        border: 1px solid {t.border};
        border-radius: {RADIUS};
        padding: 8px 16px;
        margin-right: 2px;
    }}
    QTabBar::tab:selected {{
        background-color: {t.bg};
        color: {t.fg};
        border-bottom: 2px solid {t.accent};
    }}
    QTabBar::tab:hover {{
        background-color: {t.bg_elevated};
    }}

    QTreeView, QListView {{
        background-color: {t.bg_alt};
        color: {t.fg};
        border: 1px solid {t.border};
        border-radius: {RADIUS};
        selection-background-color: {t.accent};
        selection-color: {t.accent_fg};
        outline: 0;
    }}
    QTreeView::item {{
        padding: 4px 3px;
        border: 0;
    }}
    QTreeView::item:selected, QListView::item:selected {{
        background-color: {t.selection};
        color: {t.fg};
    }}
    QTreeView::item:hover, QListView::item:hover {{
        background-color: {t.bg_elevated};
    }}

    QLineEdit, QPlainTextEdit, QTextEdit {{
        background-color: {t.bg};
        color: {t.fg};
        border: 1px solid {t.border};
        border-radius: {RADIUS};
        selection-background-color: {t.selection};
    }}
    QLineEdit:focus {{
        border: 1px solid {t.accent};
    }}

    QScrollBar:vertical {{
        background: {t.bg};
        width: 12px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {t.border};
        min-height: 24px;
        border-radius: {RADIUS};
    }}
    QScrollBar::handle:vertical:hover {{
        background: {t.accent};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar:horizontal {{
        background: {t.bg};
        height: 12px;
        margin: 0;
    }}
    QScrollBar::handle:horizontal {{
        background: {t.border};
        min-width: 24px;
        border-radius: {RADIUS};
    }}

    QSplitter::handle {{
        background-color: {t.border};
        width: 3px;
    }}
    QLabel#sectionHeading {{
        color: {t.fg_dim};
        font-size: 9pt;
        font-weight: 700;
        letter-spacing: 1px;
    }}
    QLabel#workspaceLabel {{
        color: {t.fg};
        font-size: 12pt;
        font-weight: 700;
        padding: 4px 2px;
    }}
    QWidget#explorerPanel {{
        background-color: {t.bg_alt};
    }}
    QWidget#explorerPanel QTreeView {{
        border: 0;
        background-color: {t.bg_alt};
    }}
    QPushButton#folderButton {{
        text-align: left;
        color: {t.accent};
        background-color: {t.bg};
        border: 1px solid {t.border};
        padding: 8px 10px;
    }}
    QPushButton#folderButton:hover {{
        background-color: {t.bg_elevated};
        border-color: {t.accent};
    }}

    QToolTip {{
        background-color: {t.bg_elevated};
        color: {t.fg};
        border: 1px solid {t.border};
        padding: 4px;
    }}

    QComboBox {{
        background-color: {t.bg_elevated};
        border: 1px solid {t.border};
        border-radius: {RADIUS};
        padding: 3px 8px;
    }}

    QCheckBox::indicator {{
        width: 14px; height: 14px;
        border: 1px solid {t.border};
        border-radius: {RADIUS};
        background: {t.bg};
    }}
    QCheckBox::indicator:checked {{
        background: {t.accent};
    }}
    """
