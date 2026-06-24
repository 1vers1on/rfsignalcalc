"""Detailed component editor dialog (all parameters + tolerances)."""

from __future__ import annotations

import math

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QVBoxLayout, QWidget,
)

from ..core.components import Component, ComponentKind
from ..core import units


def _inf_spin(lo, hi, suffix, decimals=2):
    sb = QDoubleSpinBox()
    sb.setRange(lo, hi)
    sb.setDecimals(decimals)
    sb.setSuffix(suffix)
    sb.setSpecialValueText("∞ (ideal)")   # shown at minimum
    sb.setAlignment(Qt.AlignRight)
    sb.setMinimumWidth(130)
    return sb


class ComponentEditor(QDialog):
    """Edit one component in detail. Call `apply_to()` after `exec()`."""

    def __init__(self, comp: Component, parent=None):
        super().__init__(parent)
        self._comp = comp
        self.setWindowTitle(f"Edit Stage — {comp.name}")
        self.setMinimumWidth(440)

        root = QVBoxLayout(self)

        # --- identity ---------------------------------------------------------
        ident = QGroupBox("Identity")
        f1 = QFormLayout(ident)
        self.name = QLineEdit(comp.name)
        self.kind = QComboBox()
        for k in ComponentKind:
            self.kind.addItem(k.value, k)
        i = self.kind.findData(comp.kind)
        if i >= 0:
            self.kind.setCurrentIndex(i)
        self.enabled = QCheckBox("Stage enabled (included in cascade)")
        self.enabled.setChecked(comp.enabled)
        self.freq = QLineEdit("" if not comp.frequency_hz else units.format_eng(comp.frequency_hz, "Hz", 4))
        self.freq.setPlaceholderText("optional, e.g. 2.4G")
        f1.addRow("Name", self.name)
        f1.addRow("Type", self.kind)
        f1.addRow("Frequency", self.freq)
        f1.addRow("", self.enabled)
        root.addWidget(ident)

        # --- electrical -------------------------------------------------------
        elec = QGroupBox("Electrical")
        f2 = QFormLayout(elec)
        self.gain = QDoubleSpinBox()
        self.gain.setRange(-200, 200)
        self.gain.setSuffix(" dB")
        self.gain.setValue(comp.gain_db)
        self.gain.setAlignment(Qt.AlignRight)

        self.nf_auto = QCheckBox("Auto (NF = insertion loss)")
        self.nf_auto.setChecked(comp.nf_db is None)
        self.nf = QDoubleSpinBox()
        self.nf.setRange(0, 200)
        self.nf.setSuffix(" dB")
        self.nf.setValue(comp.effective_nf_db())
        self.nf.setAlignment(Qt.AlignRight)
        nf_row = QWidget()
        nfl = QHBoxLayout(nf_row)
        nfl.setContentsMargins(0, 0, 0, 0)
        nfl.addWidget(self.nf)
        nfl.addWidget(self.nf_auto)
        self.nf_auto.toggled.connect(lambda on: self.nf.setEnabled(not on))
        self.nf.setEnabled(comp.nf_db is not None)

        self.oip3 = _inf_spin(-100, 120, " dBm")
        self.oip3.setValue(-100 if math.isinf(comp.oip3_dbm) else comp.oip3_dbm)
        self.oip2 = _inf_spin(-100, 160, " dBm")
        self.oip2.setValue(-100 if math.isinf(comp.oip2_dbm) else comp.oip2_dbm)
        self.op1db = _inf_spin(-100, 120, " dBm")
        self.op1db.setValue(-100 if math.isinf(comp.op1db_dbm) else comp.op1db_dbm)

        f2.addRow("Gain", self.gain)
        f2.addRow("Noise figure", nf_row)
        f2.addRow("Output IP3 (OIP3)", self.oip3)
        f2.addRow("Output IP2 (OIP2)", self.oip2)
        f2.addRow("Output P1dB", self.op1db)
        self.derived = QLabel("")
        self.derived.setObjectName("SubHeading")
        f2.addRow("", self.derived)
        root.addWidget(elec)

        # --- tolerances -------------------------------------------------------
        tol = QGroupBox("Monte-Carlo tolerances (1σ)")
        f3 = QFormLayout(tol)
        self.tg = QDoubleSpinBox(); self.tg.setRange(0, 50); self.tg.setSuffix(" dB"); self.tg.setValue(comp.tol_gain_db); self.tg.setAlignment(Qt.AlignRight)
        self.tn = QDoubleSpinBox(); self.tn.setRange(0, 50); self.tn.setSuffix(" dB"); self.tn.setValue(comp.tol_nf_db); self.tn.setAlignment(Qt.AlignRight)
        self.to = QDoubleSpinBox(); self.to.setRange(0, 50); self.to.setSuffix(" dB"); self.to.setValue(comp.tol_oip3_db); self.to.setAlignment(Qt.AlignRight)
        f3.addRow("Gain σ", self.tg)
        f3.addRow("NF σ", self.tn)
        f3.addRow("OIP3 σ", self.to)
        root.addWidget(tol)

        # --- notes ------------------------------------------------------------
        self.notes = QPlainTextEdit(comp.notes)
        self.notes.setPlaceholderText("Notes…")
        self.notes.setFixedHeight(54)
        root.addWidget(self.notes)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

        for w in (self.gain, self.nf, self.oip3, self.op1db):
            w.valueChanged.connect(self._update_derived)
        self.nf_auto.toggled.connect(self._update_derived)
        self._update_derived()

    def _oip3_value(self) -> float:
        return math.inf if self.oip3.value() <= -100 else self.oip3.value()

    def _oip2_value(self) -> float:
        return math.inf if self.oip2.value() <= -100 else self.oip2.value()

    def _op1_value(self) -> float:
        return math.inf if self.op1db.value() <= -100 else self.op1db.value()

    def _update_derived(self, *_):
        g = self.gain.value()
        nf = (-g if self.nf_auto.isChecked() else self.nf.value())
        oip3 = self._oip3_value()
        op1 = self._op1_value()
        iip3 = "—" if math.isinf(oip3) else f"{oip3 - g:.1f}"
        ip1in = "—" if math.isinf(op1) else f"{op1 - g:.1f}"
        te = units.temperature_from_nf(max(0.0, nf))
        self.derived.setText(
            f"Derived:  IIP3 {iip3} dBm   ·   input P1dB {ip1in} dBm   ·   Te ≈ {te:.0f} K"
        )

    def apply_to(self, comp: Component) -> None:
        comp.name = self.name.text().strip() or comp.name
        comp.kind = self.kind.currentData()
        comp.enabled = self.enabled.isChecked()
        text = self.freq.text().strip()
        try:
            comp.frequency_hz = None if not text else units.parse_frequency(text)
        except ValueError:
            comp.frequency_hz = None
        comp.gain_db = self.gain.value()
        comp.nf_db = None if self.nf_auto.isChecked() else self.nf.value()
        comp.oip3_dbm = self._oip3_value()
        comp.oip2_dbm = self._oip2_value()
        comp.op1db_dbm = self._op1_value()
        comp.tol_gain_db = self.tg.value()
        comp.tol_nf_db = self.tn.value()
        comp.tol_oip3_db = self.to.value()
        comp.notes = self.notes.toPlainText()
