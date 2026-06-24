"""Application bootstrap."""

from __future__ import annotations

import sys
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from . import theme
from .main_window import MainWindow, APP_NAME
from ..core import project as project_mod


def run(argv: Optional[list] = None) -> int:
    argv = list(sys.argv if argv is None else argv)

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("rfcascade")

    # Prefer a clean modern UI font when available.
    for family in ("Inter", "Segoe UI", "SF Pro Text", "Roboto", "Noto Sans", "DejaVu Sans"):
        if family in app.font().family() or True:
            f = QFont(family, 10)
            if f.exactMatch() or family == "DejaVu Sans":
                app.setFont(f)
                break

    theme.apply_theme(app, theme.DARK)

    proj = None
    file_args = [a for a in argv[1:] if not a.startswith("-")]
    if file_args:
        try:
            proj = project_mod.Project.load(file_args[0])
        except Exception:  # noqa: BLE001
            proj = None

    win = MainWindow(proj)
    win._refresh_icons()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
