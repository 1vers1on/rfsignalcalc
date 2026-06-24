"""Read-only table model presenting the per-stage cascade results."""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor, QFont

from ..core.cascade import CascadeResult, StageResult
from . import theme
from .fmt import num


class ResultsModel(QAbstractTableModel):
    """Each row is a node (Input row, then one per active stage)."""

    COLUMNS = [
        ("Node", None),
        ("Cum Gain\n(dB)", "cum_gain_db"),
        ("Cum NF\n(dB)", "cum_nf_db"),
        ("IIP3\n(dBm)", "cum_iip3_dbm"),
        ("OIP3\n(dBm)", "cum_oip3_dbm"),
        ("OP1dB\n(dBm)", "cum_op1db_dbm"),
        ("Signal\n(dBm)", "node_power_dbm"),
        ("Noise\n(dBm)", "node_noise_dbm"),
        ("SNR\n(dB)", "node_snr_db"),
        ("P1dB Hdr\n(dB)", "p1db_headroom_db"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._result: Optional[CascadeResult] = None
        self._rows: List = []   # list of ("input"|StageResult)

    def set_result(self, result: CascadeResult) -> None:
        self.beginResetModel()
        self._result = result
        self._rows = ["input"] + list(result.stages)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return self.COLUMNS[section][0]
        if section == 0:
            return "in"
        return str(section)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid() or self._result is None:
            return None
        row = self._rows[index.row()]
        title, key = self.COLUMNS[index.column()]
        pal = theme.current_palette()

        is_input = row == "input"

        if role == Qt.DisplayRole:
            if index.column() == 0:
                if is_input:
                    return "▸ Input"
                return f"{row.index}.  {row.name}"
            if is_input:
                s = self._result.summary
                if key == "cum_gain_db":
                    return "0.00"
                if key == "node_power_dbm":
                    return num(s.input_power_dbm, 2)
                if key == "node_noise_dbm":
                    return num(s.input_noise_dbm, 2)
                if key == "node_snr_db":
                    return num(s.input_snr_db, 2)
                return "—"
            return num(getattr(row, key), 2)

        if role == Qt.TextAlignmentRole:
            if index.column() == 0:
                return int(Qt.AlignVCenter | Qt.AlignLeft)
            return int(Qt.AlignVCenter | Qt.AlignRight)

        if role == Qt.FontRole and index.column() == 0:
            f = QFont()
            f.setBold(True)
            return f

        if role == Qt.ForegroundRole:
            if is_input:
                return QColor(pal.dim_text)
            if key == "node_snr_db" and isinstance(row, StageResult):
                v = row.node_snr_db
                return QColor(pal.good if v >= 10 else pal.warn if v >= 0 else pal.bad)
            if key == "p1db_headroom_db" and isinstance(row, StageResult):
                v = row.p1db_headroom_db
                return QColor(pal.good if v >= 6 else pal.warn if v >= 1 else pal.bad)
            if index.column() == 0:
                return QColor(pal.text)

        if role == Qt.BackgroundRole and is_input:
            return QColor(pal.window)
        return None
