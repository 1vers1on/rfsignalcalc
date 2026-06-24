"""Right-hand system summary: a grid of metric "cards"."""

from __future__ import annotations

from typing import Dict

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QLabel, QScrollArea, QVBoxLayout, QWidget,
)

from ..core.cascade import SystemSummary
from . import theme
from .fmt import num


class Card(QFrame):
    """A single labelled metric readout."""

    def __init__(self, label: str, unit: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 9, 12, 9)
        lay.setSpacing(1)

        self.label = QLabel(label.upper())
        self.label.setObjectName("CardLabel")
        self.value = QLabel("—")
        self.value.setObjectName("CardValue")
        self.unit = QLabel(unit)
        self.unit.setObjectName("CardUnit")

        lay.addWidget(self.label)
        lay.addWidget(self.value)
        lay.addWidget(self.unit)

    def set_value(self, text: str, color: str | None = None):
        self.value.setText(text)
        pal = theme.current_palette()
        self.value.setStyleSheet(f"color: {color or pal.text};")


class SummaryPanel(QWidget):
    """Scrollable grid of cards summarising the whole system."""

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        head = QLabel("System Performance")
        head.setObjectName("Heading")
        outer.addWidget(head)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        host = QWidget()
        self.grid = QGridLayout(host)
        self.grid.setContentsMargins(0, 4, 0, 0)
        self.grid.setHorizontalSpacing(8)
        self.grid.setVerticalSpacing(8)
        scroll.setWidget(host)
        outer.addWidget(scroll, 1)

        self._cards: Dict[str, Card] = {}
        specs = [
            ("gain", "Total Gain", "dB"),
            ("nf", "Noise Figure", "dB"),
            ("oip3", "Output IP3", "dBm"),
            ("iip3", "Input IP3", "dBm"),
            ("op1db", "Output P1dB", "dBm"),
            ("snr", "Output SNR", "dB"),
            ("opwr", "Output Power", "dBm"),
            ("onoise", "Output Noise", "dBm"),
            ("mds", "MDS (SNR=0)", "dBm"),
            ("sens", "Sensitivity", "dBm"),
            ("sfdr", "SFDR (IM3)", "dB"),
            ("dr", "Dynamic Range", "dB"),
            ("tn", "Noise Temp", "K"),
            ("margin", "Link Margin", "dB"),
        ]
        for i, (key, label, unit) in enumerate(specs):
            card = Card(label, unit)
            self._cards[key] = card
            self.grid.addWidget(card, i // 2, i % 2)
        self.grid.setRowStretch(len(specs) // 2 + 1, 1)

    def update_summary(self, s: SystemSummary):
        pal = theme.current_palette()
        c = self._cards

        c["gain"].set_value(num(s.total_gain_db, 2),
                            pal.good if s.total_gain_db >= 0 else pal.warn)
        c["nf"].set_value(num(s.total_nf_db, 2),
                          pal.good if s.total_nf_db < 3 else pal.warn if s.total_nf_db < 8 else pal.bad)
        c["oip3"].set_value(num(s.oip3_dbm, 1))
        c["iip3"].set_value(num(s.iip3_dbm, 1))
        c["op1db"].set_value(num(s.op1db_dbm, 1))
        c["snr"].set_value(num(s.output_snr_db, 1),
                           pal.good if s.output_snr_db >= s.input_snr_db - 3 else pal.warn)
        c["opwr"].set_value(num(s.output_power_dbm, 1))
        c["onoise"].set_value(num(s.output_noise_dbm, 1))
        c["mds"].set_value(num(s.mds_dbm, 1))
        c["sens"].set_value(num(s.sensitivity_dbm, 1))
        c["sfdr"].set_value(num(s.sfdr_db, 1),
                            pal.good if s.sfdr_db >= 70 else pal.warn if s.sfdr_db >= 50 else pal.bad)
        c["dr"].set_value(num(s.dynamic_range_db, 1))
        c["tn"].set_value(num(s.noise_temp_k, 0))
        c["margin"].set_value(num(s.link_margin_db, 1),
                              pal.good if s.link_margin_db >= 0 else pal.bad)
