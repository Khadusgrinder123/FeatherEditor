#!/usr/bin/env python3
"""FeatherEditor entry point.

Python completion is handled in-process; no background language server is
started during application startup.
"""
import sys
import os


def main():
    from PySide6.QtWidgets import QApplication
    from main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("FeatherEditor")

    workspace = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    window = MainWindow(workspace_root=workspace)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
