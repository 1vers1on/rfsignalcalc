"""Editable table model + delegate for the signal-chain component list."""

from __future__ import annotations

import math
from typing import List, Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QComboBox, QStyledItemDelegate, QWidget

from ..core.components import Component, ComponentKind
from . import theme
from .fmt import num, parse_float


class ChainModel(QAbstractTableModel):
    """Holds the ordered list of `Component`s; edits emit `chainChanged`."""

    chainChanged = Signal()

    COLUMNS = [
        ("", "enabled"),
        ("Stage", "name"),
        ("Type", "kind"),
        ("Gain\n(dB)", "gain_db"),
        ("NF\n(dB)", "nf_db"),
        ("OIP3\n(dBm)", "oip3_dbm"),
        ("OP1dB\n(dBm)", "op1db_dbm"),
        ("Freq", "frequency_hz"),
    ]

    def __init__(self, components: Optional[List[Component]] = None, parent=None):
        super().__init__(parent)
        self._items: List[Component] = components or []

    # ---- container access ----------------------------------------------------
    @property
    def items(self) -> List[Component]:
        return self._items

    def set_items(self, items: List[Component]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()
        self.chainChanged.emit()

    def component_at(self, row: int) -> Optional[Component]:
        if 0 <= row < len(self._items):
            return self._items[row]
        return None

    # ---- Qt model API --------------------------------------------------------
    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._items)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                return self.COLUMNS[section][0]
        elif role == Qt.DisplayRole:
            return str(section + 1)
        return None

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.NoItemFlags
        f = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        key = self.COLUMNS[index.column()][1]
        if key == "enabled":
            return f | Qt.ItemIsUserCheckable
        return f | Qt.ItemIsEditable

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        comp = self._items[index.row()]
        key = self.COLUMNS[index.column()][1]
        disabled = not comp.enabled

        if role == Qt.CheckStateRole and key == "enabled":
            return Qt.Checked if comp.enabled else Qt.Unchecked

        if role in (Qt.DisplayRole, Qt.EditRole):
            if key == "enabled":
                return None
            if key == "name":
                return comp.name
            if key == "kind":
                return comp.kind.value
            if key == "frequency_hz":
                from ..core.units import format_eng
                if comp.frequency_hz:
                    return format_eng(comp.frequency_hz, "Hz", 3)
                return "" if role == Qt.EditRole else "—"
            if key == "nf_db":
                val = comp.effective_nf_db()
                txt = num(val, 2)
                if comp.nf_db is None and role == Qt.DisplayRole:
                    return f"{txt}*"   # auto (= loss)
                return txt if role == Qt.DisplayRole else f"{val:.2f}"
            val = getattr(comp, key)
            if role == Qt.EditRole:
                if isinstance(val, float) and math.isinf(val):
                    return ""
                return f"{val:.3f}" if isinstance(val, float) else val
            return num(val, 2)

        if role == Qt.TextAlignmentRole:
            if key in ("name", "kind"):
                return int(Qt.AlignVCenter | Qt.AlignLeft)
            return int(Qt.AlignVCenter | Qt.AlignRight)

        if role == Qt.ForegroundRole:
            if disabled:
                return QColor(theme.current_palette().dim_text)
            if key == "kind":
                return QColor(theme.kind_color(comp.kind))
            if key == "gain_db":
                return QColor(theme.current_palette().good if comp.gain_db >= 0
                              else theme.current_palette().warn)

        if role == Qt.FontRole and key == "kind":
            font = QFont()
            font.setBold(True)
            return font

        if role == Qt.ToolTipRole:
            return (f"{comp.name} · {comp.kind.value}\n"
                    f"Gain {comp.gain_db:+.2f} dB · NF {comp.effective_nf_db():.2f} dB\n"
                    f"OIP3 {num(comp.oip3_dbm)} dBm · IIP3 {num(comp.iip3_dbm)} dBm\n"
                    f"OP1dB {num(comp.op1db_dbm)} dBm")
        return None

    def setData(self, index: QModelIndex, value, role=Qt.EditRole) -> bool:
        if not index.isValid():
            return False
        comp = self._items[index.row()]
        key = self.COLUMNS[index.column()][1]

        if role == Qt.CheckStateRole and key == "enabled":
            comp.enabled = Qt.CheckState(value) == Qt.Checked
            self.dataChanged.emit(index, index)
            self.chainChanged.emit()
            return True

        if role != Qt.EditRole:
            return False
        try:
            if key == "name":
                comp.name = str(value).strip() or comp.name
            elif key == "kind":
                comp.kind = ComponentKind(value)
            elif key == "frequency_hz":
                from ..core.units import parse_frequency
                text = str(value).strip()
                comp.frequency_hz = None if not text else parse_frequency(text)
            elif key == "nf_db":
                text = str(value).strip()
                comp.nf_db = None if text in ("", "*", "auto") else float(text)
            else:
                setattr(comp, key, parse_float(str(value)))
        except (ValueError, TypeError):
            return False

        # NF column may render differently for the whole row; refresh the row.
        left = self.index(index.row(), 0)
        right = self.index(index.row(), self.columnCount() - 1)
        self.dataChanged.emit(left, right)
        self.chainChanged.emit()
        return True

    # ---- editing operations --------------------------------------------------
    def insert_component(self, comp: Component, row: Optional[int] = None) -> int:
        if row is None or row < 0 or row > len(self._items):
            row = len(self._items)
        self.beginInsertRows(QModelIndex(), row, row)
        self._items.insert(row, comp)
        self.endInsertRows()
        self.chainChanged.emit()
        return row

    def remove_rows(self, rows: List[int]) -> None:
        for r in sorted(set(rows), reverse=True):
            if 0 <= r < len(self._items):
                self.beginRemoveRows(QModelIndex(), r, r)
                del self._items[r]
                self.endRemoveRows()
        self.chainChanged.emit()

    def duplicate_row(self, row: int) -> int:
        if not (0 <= row < len(self._items)):
            return -1
        new = self._items[row].copy()
        new.name = self._items[row].name + " copy"
        return self.insert_component(new, row + 1)

    def move_row(self, row: int, delta: int) -> int:
        new_row = row + delta
        if not (0 <= row < len(self._items)) or not (0 <= new_row < len(self._items)):
            return row
        self.beginMoveRows(QModelIndex(), row, row,
                           QModelIndex(), new_row + (1 if delta > 0 else 0))
        self._items.insert(new_row, self._items.pop(row))
        self.endMoveRows()
        self.chainChanged.emit()
        return new_row

    def update_component(self, row: int) -> None:
        """Notify the view that an externally-edited component row changed."""
        if 0 <= row < len(self._items):
            left = self.index(row, 0)
            right = self.index(row, self.columnCount() - 1)
            self.dataChanged.emit(left, right)
            self.chainChanged.emit()

    def refresh_rows(self, rows: List[int]) -> None:
        """Repaint the given rows without signalling a chain change.

        Used for derived updates made *during* recompute (e.g. a network
        stage's gain re-sampled at the source frequency); emitting
        ``chainChanged`` here would recurse back into recompute.
        """
        for r in rows:
            if 0 <= r < len(self._items):
                left = self.index(r, 0)
                right = self.index(r, self.columnCount() - 1)
                self.dataChanged.emit(left, right)


class KindDelegate(QStyledItemDelegate):
    """Combo-box editor for the component Type column."""

    def createEditor(self, parent: QWidget, option, index) -> QWidget:
        combo = QComboBox(parent)
        for k in ComponentKind:
            combo.addItem(k.value, k.value)
        return combo

    def setEditorData(self, editor: QComboBox, index) -> None:
        val = index.data(Qt.EditRole)
        i = editor.findData(val)
        if i >= 0:
            editor.setCurrentIndex(i)

    def setModelData(self, editor: QComboBox, model, index) -> None:
        model.setData(index, editor.currentData(), Qt.EditRole)
