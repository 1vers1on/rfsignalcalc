"""Circuit Block Builder: assemble a two-port from lumped R / L / C rungs.

The dialog edits a ladder of series / shunt elements, shows a live S21 / S11
preview, and (on accept) hands back a :class:`LumpedCircuit` that the caller
turns into a chain stage. Filter / pad presets seed the ladder with one click.
"""

from __future__ import annotations

import math
from typing import List, Optional

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..core import circuit as ckt
from ..core import units
from . import theme
from .plots import _pen, _style_plot


def _eng_or_none(text: str) -> Optional[float]:
    text = (text or "").strip()
    if not text or text in ("-", "—", "0", "0.0"):
        return None
    try:
        return units.parse_eng(text)
    except ValueError:
        return None


def _fmt_or_blank(value: Optional[float], unit: str) -> str:
    return "" if value is None else units.format_eng(value, unit, 4)


class CircuitBuilderDialog(QDialog):
    """Build / edit a lumped two-port. Use :meth:`result_circuit` after exec()."""

    COLS = ["Arm", "R", "L", "C", "R/L/C combine", "Label"]

    def __init__(self, circuit: Optional[ckt.LumpedCircuit] = None,
                 default_freq_hz: float = 1.0e9, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Circuit Block Builder")
        self.setMinimumSize(880, 560)
        self._default_freq = default_freq_hz or 1.0e9
        self._building = False

        root = QVBoxLayout(self)

        # --- identity / preset header ----------------------------------------
        head = QHBoxLayout()
        idf = QFormLayout()
        self.name = QLineEdit(circuit.name if circuit else "Lumped Block")
        self.z0 = QDoubleSpinBox()
        self.z0.setRange(1.0, 1000.0)
        self.z0.setSuffix(" Ω")
        self.z0.setValue(circuit.z0 if circuit else 50.0)
        idf.addRow("Name", self.name)
        idf.addRow("Z₀", self.z0)
        head.addLayout(idf)
        head.addSpacing(24)

        preset_box = QFormLayout()
        self.preset = QComboBox()
        self.preset.addItems(["Butterworth LPF", "Butterworth HPF",
                              "Butterworth BPF", "π attenuator pad"])
        self.preset.currentIndexChanged.connect(self._sync_preset_fields)
        self.order = QSpinBox()
        self.order.setRange(1, 9)
        self.order.setValue(5)
        self.p_fc = QLineEdit(units.format_eng(self._default_freq, "Hz", 3))
        self.p_bw = QLineEdit(units.format_eng(self._default_freq * 0.1, "Hz", 3))
        self.p_atten = QDoubleSpinBox()
        self.p_atten.setRange(0.5, 60.0)
        self.p_atten.setValue(10.0)
        self.p_atten.setSuffix(" dB")
        prow = QHBoxLayout()
        prow.addWidget(self.order)
        prow.addWidget(QLabel("fc/f0")); prow.addWidget(self.p_fc)
        prow.addWidget(QLabel("BW")); prow.addWidget(self.p_bw)
        prow.addWidget(self.p_atten)
        self.apply_preset_btn = QPushButton("Generate")
        self.apply_preset_btn.clicked.connect(self._apply_preset)
        prow.addWidget(self.apply_preset_btn)
        pr_w = QWidget(); pr_w.setLayout(prow)
        preset_box.addRow("Preset", self.preset)
        preset_box.addRow("Params", pr_w)
        head.addLayout(preset_box, 1)
        root.addLayout(head)

        # --- main split: element table (left) + preview (right) --------------
        body = QHBoxLayout()

        left = QVBoxLayout()
        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.verticalHeader().setDefaultSectionSize(30)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for c in (1, 2, 3):
            hh.setSectionResizeMode(c, QHeaderView.Stretch)
        hh.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.itemChanged.connect(self._on_changed)
        left.addWidget(self.table, 1)

        btns = QHBoxLayout()
        b_series = QPushButton("+ Series")
        b_shunt = QPushButton("+ Shunt")
        b_del = QPushButton("Remove")
        b_up = QPushButton("↑")
        b_down = QPushButton("↓")
        b_series.clicked.connect(lambda: self._add_row(ckt.LumpedElement(arm=ckt.Arm.SERIES, l_h=1e-9)))
        b_shunt.clicked.connect(lambda: self._add_row(ckt.LumpedElement(arm=ckt.Arm.SHUNT, c_f=1e-12)))
        b_del.clicked.connect(self._remove_row)
        b_up.clicked.connect(lambda: self._move_row(-1))
        b_down.clicked.connect(lambda: self._move_row(1))
        for b in (b_series, b_shunt, b_del, b_up, b_down):
            btns.addWidget(b)
        btns.addStretch(1)
        left.addLayout(btns)
        body.addLayout(left, 3)

        right = QVBoxLayout()
        frow = QHBoxLayout()
        frow.addWidget(QLabel("Preview"))
        frow.addWidget(QLabel("from"))
        self.f0 = QLineEdit(units.format_eng(self._default_freq * 0.1, "Hz", 3))
        self.f0.setMaximumWidth(90)
        frow.addWidget(self.f0)
        frow.addWidget(QLabel("to"))
        self.f1 = QLineEdit(units.format_eng(self._default_freq * 3.0, "Hz", 3))
        self.f1.setMaximumWidth(90)
        frow.addWidget(self.f1)
        frow.addStretch(1)
        right.addLayout(frow)

        self.preview = pg.PlotWidget()
        self.preview.addLegend(offset=(-10, 10),
                               labelTextColor=theme.current_palette().text)
        _style_plot(self.preview.getPlotItem(), "Frequency (Hz)", "dB",
                    "S21 / S11 preview")
        right.addWidget(self.preview, 1)
        self.readout = QLabel("")
        self.readout.setObjectName("SubHeading")
        self.readout.setWordWrap(True)
        right.addWidget(self.readout)
        body.addLayout(right, 4)
        root.addLayout(body)

        for w in (self.f0, self.f1):
            w.editingFinished.connect(self._redraw)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

        # seed from an existing circuit, else a starter band-pass-ish ladder
        if circuit and circuit.elements:
            self._load(circuit)
        else:
            self._apply_preset()
        self._sync_preset_fields()

    # ---- preset params show/hide --------------------------------------------
    def _sync_preset_fields(self):
        kind = self.preset.currentText()
        is_pad = "atten" in kind
        is_bpf = "BPF" in kind
        self.order.setVisible(not is_pad)
        self.p_fc.setVisible(not is_pad)
        self.p_bw.setVisible(is_bpf)
        self.p_atten.setVisible(is_pad)

    def _apply_preset(self):
        kind = self.preset.currentText()
        z0 = self.z0.value()
        try:
            if "atten" in kind:
                circ = ckt.pi_pad(self.p_atten.value(), z0)
            else:
                fc = units.parse_frequency(self.p_fc.text())
                n = self.order.value()
                if "LPF" in kind:
                    circ = ckt.butterworth_lpf(n, fc, z0)
                elif "HPF" in kind:
                    circ = ckt.butterworth_hpf(n, fc, z0)
                else:
                    bw = units.parse_frequency(self.p_bw.text())
                    circ = ckt.butterworth_bpf(n, fc, bw, z0)
        except ValueError:
            return
        # Generate is an explicit action: name the block after the preset.
        self.name.setText(circ.name)
        # auto preview band around the preset
        self._autoset_preview_band(circ)
        self._load(circ)

    def _autoset_preview_band(self, circ: ckt.LumpedCircuit):
        try:
            if "atten" in self.preset.currentText():
                f = self._default_freq
                lo, hi = f * 0.1, f * 3.0
            else:
                fc = units.parse_frequency(self.p_fc.text())
                lo, hi = fc * 0.1, fc * 3.0
        except ValueError:
            return
        self.f0.setText(units.format_eng(max(lo, 1e3), "Hz", 3))
        self.f1.setText(units.format_eng(hi, "Hz", 3))

    # ---- table <-> circuit ---------------------------------------------------
    def _load(self, circ: ckt.LumpedCircuit):
        self._building = True
        self.table.setRowCount(0)
        self.z0.setValue(circ.z0)
        for el in circ.elements:
            self._add_row(el, redraw=False)
        self._building = False
        self._redraw()

    def _add_row(self, el: ckt.LumpedElement, redraw: bool = True):
        self._building = True
        r = self.table.rowCount()
        self.table.insertRow(r)

        arm = QComboBox()
        arm.addItem("series", ckt.Arm.SERIES)
        arm.addItem("shunt", ckt.Arm.SHUNT)
        arm.setCurrentIndex(0 if el.arm == ckt.Arm.SERIES else 1)
        arm.currentIndexChanged.connect(self._on_changed)
        self.table.setCellWidget(r, 0, arm)

        self.table.setItem(r, 1, QTableWidgetItem(_fmt_or_blank(el.r_ohm, "Ω")))
        self.table.setItem(r, 2, QTableWidgetItem(_fmt_or_blank(el.l_h, "H")))
        self.table.setItem(r, 3, QTableWidgetItem(_fmt_or_blank(el.c_f, "F")))

        combo = QComboBox()
        combo.addItem("series", ckt.Combo.SERIES)
        combo.addItem("parallel", ckt.Combo.PARALLEL)
        combo.setCurrentIndex(0 if el.combo == ckt.Combo.SERIES else 1)
        combo.currentIndexChanged.connect(self._on_changed)
        self.table.setCellWidget(r, 4, combo)

        self.table.setItem(r, 5, QTableWidgetItem(el.label))
        self._building = False
        if redraw:
            self._redraw()

    def _read_element(self, r: int) -> ckt.LumpedElement:
        # Qt coerces our str-based Enum userData back to plain str, so re-wrap.
        arm = ckt.Arm(self.table.cellWidget(r, 0).currentData())
        combo = ckt.Combo(self.table.cellWidget(r, 4).currentData())

        def cell(c):
            it = self.table.item(r, c)
            return it.text() if it else ""

        return ckt.LumpedElement(
            arm=arm, combo=combo,
            r_ohm=_eng_or_none(cell(1)),
            l_h=_eng_or_none(cell(2)),
            c_f=_eng_or_none(cell(3)),
            label=cell(5).strip(),
        )

    def result_circuit(self) -> ckt.LumpedCircuit:
        els = [self._read_element(r) for r in range(self.table.rowCount())]
        return ckt.LumpedCircuit(elements=els, z0=self.z0.value(),
                                 name=self.name.text().strip() or "Lumped Block")

    # ---- row ops -------------------------------------------------------------
    def _remove_row(self):
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)
            self._redraw()

    def _move_row(self, delta: int):
        r = self.table.currentRow()
        nr = r + delta
        if r < 0 or nr < 0 or nr >= self.table.rowCount():
            return
        circ = self.result_circuit()
        circ.elements[r], circ.elements[nr] = circ.elements[nr], circ.elements[r]
        self._load(circ)
        self.table.setCurrentCell(nr, 0)

    # ---- preview -------------------------------------------------------------
    def _on_changed(self, *_):
        if not self._building:
            self._redraw()

    def _freqs(self) -> np.ndarray:
        try:
            a = units.parse_frequency(self.f0.text())
            b = units.parse_frequency(self.f1.text())
        except ValueError:
            return np.array([])
        if b <= a or a <= 0:
            return np.array([])
        return np.linspace(a, b, 801)

    def _redraw(self):
        pal = theme.current_palette()
        self.preview.clear()
        freqs = self._freqs()
        if freqs.size == 0:
            self.readout.setText("Set a valid preview frequency range.")
            return
        circ = self.result_circuit()
        if not circ.elements:
            self.readout.setText("Add elements (or generate a preset) to preview.")
            return
        net = circ.sparams(freqs)
        self.preview.plot(freqs, net.s21_db(), pen=_pen(pal.accent, 2.2), name="S21")
        self.preview.plot(freqs, net.s11_db(), pen=_pen(pal.warn, 1.6, [6, 5]), name="S11")
        self.preview.enableAutoRange()

        il = circ.insertion_gain_db(self._default_freq)
        peak = float(np.max(net.s21_db()))
        from ..core.sparams import passband_edges_db
        f_lo, f_hi, bw = passband_edges_db(net, drop_db=3.0)
        bw_txt = (f"−3 dB BW {units.format_eng(bw, 'Hz', 3)}"
                  if bw == bw else "−3 dB BW —")
        self.readout.setText(
            f"{len(circ.elements)} elements · peak |S21| {peak:+.2f} dB · "
            f"|S21| @ {units.format_eng(self._default_freq, 'Hz', 3)} = {il:+.2f} dB · {bw_txt}"
        )
