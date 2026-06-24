"""Modern dark (and light) theme: Qt palette, global stylesheet, accent colours.

The palette is a refined "graphite" dark theme with a cyan accent, designed to
look at home next to professional RF EDA tools. A light theme is provided too;
both share the same accent so plots and badges stay consistent.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from ..core.components import ComponentKind


@dataclass(frozen=True)
class Palette:
    name: str
    window: str
    base: str
    panel: str
    alt_base: str
    text: str
    dim_text: str
    border: str
    accent: str
    accent_2: str
    grid: str
    plot_bg: str
    good: str
    warn: str
    bad: str
    selection: str


DARK = Palette(
    name="dark",
    window="#1b1e24",
    base="#21252d",
    panel="#272b34",
    alt_base="#242832",
    text="#e3e6ec",
    dim_text="#8b93a3",
    border="#363c47",
    accent="#2dd4bf",      # teal/cyan
    accent_2="#60a5fa",    # blue
    grid="#333a45",
    plot_bg="#181b21",
    good="#4ade80",
    warn="#fbbf24",
    bad="#f87171",
    selection="#2dd4bf",
)

LIGHT = Palette(
    name="light",
    window="#eef1f5",
    base="#ffffff",
    panel="#f6f8fb",
    alt_base="#eef2f7",
    text="#1b2430",
    dim_text="#5b6675",
    border="#d3d9e2",
    accent="#0e9488",
    accent_2="#2563eb",
    grid="#d8dee7",
    plot_bg="#ffffff",
    good="#16a34a",
    warn="#d97706",
    bad="#dc2626",
    selection="#0e9488",
)


#: Distinct accent colour per component kind (used for badges & plot markers).
KIND_COLORS = {
    ComponentKind.AMPLIFIER: "#60a5fa",
    ComponentKind.LNA: "#2dd4bf",
    ComponentKind.ATTENUATOR: "#fb923c",
    ComponentKind.FILTER: "#a78bfa",
    ComponentKind.MIXER: "#f472b6",
    ComponentKind.CABLE: "#94a3b8",
    ComponentKind.SWITCH: "#facc15",
    ComponentKind.GAIN_BLOCK: "#38bdf8",
    ComponentKind.COUPLER: "#c084fc",
    ComponentKind.ISOLATOR: "#cbd5e1",
    ComponentKind.ADC: "#34d399",
    ComponentKind.CUSTOM: "#9ca3af",
}


def kind_color(kind: ComponentKind) -> str:
    return KIND_COLORS.get(kind, "#9ca3af")


def _qpalette(p: Palette) -> QPalette:
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(p.window))
    pal.setColor(QPalette.WindowText, QColor(p.text))
    pal.setColor(QPalette.Base, QColor(p.base))
    pal.setColor(QPalette.AlternateBase, QColor(p.alt_base))
    pal.setColor(QPalette.ToolTipBase, QColor(p.panel))
    pal.setColor(QPalette.ToolTipText, QColor(p.text))
    pal.setColor(QPalette.Text, QColor(p.text))
    pal.setColor(QPalette.Button, QColor(p.panel))
    pal.setColor(QPalette.ButtonText, QColor(p.text))
    pal.setColor(QPalette.BrightText, QColor("#ffffff"))
    pal.setColor(QPalette.Highlight, QColor(p.selection))
    pal.setColor(QPalette.HighlightedText, QColor("#0b0f14" if p.name == "dark" else "#ffffff"))
    pal.setColor(QPalette.Link, QColor(p.accent_2))
    pal.setColor(QPalette.PlaceholderText, QColor(p.dim_text))
    disabled = QColor(p.dim_text)
    pal.setColor(QPalette.Disabled, QPalette.Text, disabled)
    pal.setColor(QPalette.Disabled, QPalette.ButtonText, disabled)
    pal.setColor(QPalette.Disabled, QPalette.WindowText, disabled)
    return pal


def _stylesheet(p: Palette) -> str:
    return f"""
    * {{
        outline: 0;
    }}
    QWidget {{
        font-size: 10.5pt;
        color: {p.text};
    }}
    QMainWindow, QDialog {{
        background: {p.window};
    }}
    QToolBar {{
        background: {p.window};
        border: none;
        spacing: 4px;
        padding: 5px 8px;
    }}
    QToolBar QToolButton {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 7px;
        padding: 6px 11px;
        margin: 0px 1px;
        color: {p.text};
    }}
    QToolBar QToolButton:hover {{
        background: {p.panel};
        border: 1px solid {p.border};
    }}
    QToolBar QToolButton:pressed, QToolBar QToolButton:checked {{
        background: {p.accent};
        color: #06201d;
    }}
    QToolBar::separator {{
        background: {p.border};
        width: 1px;
        margin: 5px 7px;
    }}
    QMenuBar {{ background: {p.window}; padding: 2px; }}
    QMenuBar::item {{ padding: 5px 11px; background: transparent; border-radius: 6px; }}
    QMenuBar::item:selected {{ background: {p.panel}; }}
    QMenu {{ background: {p.panel}; border: 1px solid {p.border}; border-radius: 8px; padding: 5px; }}
    QMenu::item {{ padding: 6px 24px 6px 14px; border-radius: 5px; }}
    QMenu::item:selected {{ background: {p.accent}; color: #06201d; }}
    QMenu::separator {{ height: 1px; background: {p.border}; margin: 5px 8px; }}

    QGroupBox {{
        background: {p.panel};
        border: 1px solid {p.border};
        border-radius: 10px;
        margin-top: 12px;
        padding: 10px 10px 8px 10px;
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 12px;
        padding: 1px 7px;
        color: {p.accent};
        background: transparent;
    }}

    QFrame#Card {{
        background: {p.panel};
        border: 1px solid {p.border};
        border-radius: 10px;
    }}

    QLabel#CardValue {{ font-size: 17pt; font-weight: 700; color: {p.text}; }}
    QLabel#CardLabel {{ font-size: 8.7pt; color: {p.dim_text}; text-transform: uppercase; letter-spacing: 1px; }}
    QLabel#CardUnit {{ font-size: 8.7pt; color: {p.dim_text}; }}
    QLabel#Heading {{ font-size: 12pt; font-weight: 700; color: {p.text}; }}
    QLabel#SubHeading {{ color: {p.dim_text}; }}

    QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{
        background: {p.base};
        border: 1px solid {p.border};
        border-radius: 7px;
        padding: 5px 8px;
        selection-background-color: {p.accent};
        selection-color: #06201d;
    }}
    QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {{
        border: 1px solid {p.accent};
    }}
    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox::down-arrow {{
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {p.dim_text};
        margin-right: 8px;
    }}
    QComboBox QAbstractItemView {{
        background: {p.panel};
        border: 1px solid {p.border};
        border-radius: 8px;
        selection-background-color: {p.accent};
        selection-color: #06201d;
        padding: 4px;
    }}
    QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
    QSpinBox::up-button, QSpinBox::down-button {{ width: 16px; border: none; background: transparent; }}

    QPushButton {{
        background: {p.panel};
        border: 1px solid {p.border};
        border-radius: 7px;
        padding: 7px 16px;
        font-weight: 600;
    }}
    QPushButton:hover {{ border: 1px solid {p.accent}; }}
    QPushButton:pressed {{ background: {p.base}; }}
    QPushButton#Primary {{ background: {p.accent}; color: #06201d; border: none; }}
    QPushButton#Primary:hover {{ background: {p.accent_2}; color: #06201d; }}
    QPushButton:disabled {{ color: {p.dim_text}; border-color: {p.border}; }}

    QHeaderView::section {{
        background: {p.window};
        color: {p.dim_text};
        border: none;
        border-bottom: 1px solid {p.border};
        border-right: 1px solid {p.border};
        padding: 7px 8px;
        font-weight: 600;
    }}
    QTableView, QTreeView, QListView {{
        background: {p.base};
        alternate-background-color: {p.alt_base};
        border: 1px solid {p.border};
        border-radius: 10px;
        gridline-color: {p.border};
        selection-background-color: {p.accent};
        selection-color: #06201d;
    }}
    QTableView::item, QTreeView::item {{ padding: 3px 6px; }}
    QTableView::item:selected, QTreeView::item:selected {{ color: #06201d; }}
    QTableCornerButton::section {{ background: {p.window}; border: none; }}

    QTabWidget::pane {{ border: 1px solid {p.border}; border-radius: 10px; top: -1px; background: {p.base}; }}
    QTabBar::tab {{
        background: transparent;
        color: {p.dim_text};
        padding: 8px 18px;
        margin-right: 2px;
        border: 1px solid transparent;
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
    }}
    QTabBar::tab:selected {{ color: {p.text}; background: {p.base}; border: 1px solid {p.border}; border-bottom-color: {p.base}; }}
    QTabBar::tab:hover:!selected {{ color: {p.text}; }}

    QDockWidget {{ titlebar-close-icon: none; color: {p.text}; }}
    QDockWidget::title {{
        background: {p.window};
        padding: 8px 12px;
        border-bottom: 1px solid {p.border};
        font-weight: 700;
    }}

    QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {p.border}; border-radius: 5px; min-height: 28px; }}
    QScrollBar::handle:vertical:hover {{ background: {p.dim_text}; }}
    QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px; }}
    QScrollBar::handle:horizontal {{ background: {p.border}; border-radius: 5px; min-width: 28px; }}
    QScrollBar::handle:horizontal:hover {{ background: {p.dim_text}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

    QStatusBar {{ background: {p.window}; color: {p.dim_text}; border-top: 1px solid {p.border}; }}
    QStatusBar::item {{ border: none; }}
    QToolTip {{ background: {p.panel}; color: {p.text}; border: 1px solid {p.border}; border-radius: 6px; padding: 5px 8px; }}
    QCheckBox::indicator, QRadioButton::indicator {{ width: 16px; height: 16px; }}
    QCheckBox::indicator:unchecked {{ border: 1px solid {p.border}; border-radius: 4px; background: {p.base}; }}
    QCheckBox::indicator:checked {{ border: 1px solid {p.accent}; border-radius: 4px; background: {p.accent}; }}
    QSplitter::handle {{ background: {p.border}; }}
    QSplitter::handle:horizontal {{ width: 2px; }}
    QSplitter::handle:vertical {{ height: 2px; }}
    """


_CURRENT = {"palette": DARK}


def current_palette() -> Palette:
    return _CURRENT["palette"]


def apply_theme(app: QApplication, palette: Palette) -> None:
    """Apply a full theme (Fusion style + palette + stylesheet) to the app."""
    import pyqtgraph as pg

    _CURRENT["palette"] = palette
    app.setStyle("Fusion")
    app.setPalette(_qpalette(palette))
    app.setStyleSheet(_stylesheet(palette))
    pg.setConfigOptions(antialias=True, background=palette.plot_bg, foreground=palette.text)
