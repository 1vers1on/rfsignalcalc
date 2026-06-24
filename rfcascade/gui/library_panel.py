"""Dockable component-library browser. Double-click (or button) adds a part."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QLabel, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from ..core import library
from ..core.components import Component, ComponentKind
from . import theme
from .fmt import num


class LibraryPanel(QWidget):
    """Tree of preset parts grouped by category."""

    addRequested = Signal(object)   # emits a fresh Component copy

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)

        title = QLabel("Component Library")
        title.setObjectName("Heading")
        lay.addWidget(title)
        sub = QLabel("Double-click or “Add” to insert into the chain.")
        sub.setObjectName("SubHeading")
        sub.setWordWrap(True)
        lay.addWidget(sub)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setColumnCount(1)
        self.tree.setIndentation(14)
        self.tree.itemDoubleClicked.connect(self._on_double)
        self.tree.currentItemChanged.connect(self._on_select)
        lay.addWidget(self.tree, 1)

        self.detail = QLabel("")
        self.detail.setObjectName("SubHeading")
        self.detail.setWordWrap(True)
        self.detail.setMinimumHeight(56)
        lay.addWidget(self.detail)

        self.add_btn = QPushButton("Add to Chain")
        self.add_btn.setObjectName("Primary")
        self.add_btn.clicked.connect(self._on_add)
        self.add_btn.setEnabled(False)
        lay.addWidget(self.add_btn)

        self._populate()

    def _populate(self):
        pal = theme.current_palette()
        bold = QFont()
        bold.setBold(True)
        for group, parts in library.LIBRARY.items():
            top = QTreeWidgetItem([group])
            top.setFont(0, bold)
            top.setForeground(0, QColor(pal.dim_text))
            top.setFlags(Qt.ItemIsEnabled)
            for part in parts:
                child = QTreeWidgetItem([part.name])
                child.setForeground(0, QColor(theme.kind_color(part.kind)))
                child.setData(0, Qt.UserRole, part)
                child.setToolTip(0, self._summary(part))
                top.addChild(child)
            self.tree.addTopLevelItem(top)
            top.setExpanded(True)

    @staticmethod
    def _summary(part: Component) -> str:
        return (f"{part.kind.value}\n"
                f"Gain {part.gain_db:+.1f} dB   NF {part.effective_nf_db():.1f} dB\n"
                f"OIP3 {num(part.oip3_dbm, 1)} dBm   OP1dB {num(part.op1db_dbm, 1)} dBm")

    def _current_part(self):
        item = self.tree.currentItem()
        if item is None:
            return None
        return item.data(0, Qt.UserRole)

    def _on_select(self, *_):
        part = self._current_part()
        self.add_btn.setEnabled(part is not None)
        self.detail.setText(self._summary(part) if part else "")

    def _on_double(self, item, _col):
        part = item.data(0, Qt.UserRole)
        if part is not None:
            self.addRequested.emit(part.copy())

    def _on_add(self):
        part = self._current_part()
        if part is not None:
            self.addRequested.emit(part.copy())
