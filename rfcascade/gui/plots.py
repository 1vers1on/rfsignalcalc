"""pyqtgraph-based analysis views: level diagram, metric plots, power sweep,
and Monte-Carlo histograms."""

from __future__ import annotations

import math
from typing import List, Optional

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from ..core.cascade import CascadeResult, frequency_response
from ..core.components import SignalSource, Component
from ..core import sweep as sweep_mod
from ..core import montecarlo as mc_mod
from ..core import sparams as sparams_mod
from ..core import units
from ..core.cascade import IMDMode
from . import theme


def _pen(color: str, width: float = 2.0, dash: Optional[List[int]] = None):
    pen = pg.mkPen(color=color, width=width)
    if dash:
        pen.setDashPattern(dash)
    return pen


def _style_plot(p: pg.PlotItem, xlabel: str, ylabel: str, title: str = ""):
    pal = theme.current_palette()
    p.showGrid(x=True, y=True, alpha=0.25)
    p.getAxis("left").setPen(pal.grid)
    p.getAxis("bottom").setPen(pal.grid)
    p.getAxis("left").setTextPen(pal.dim_text)
    p.getAxis("bottom").setTextPen(pal.dim_text)
    if xlabel:
        p.setLabel("bottom", xlabel, color=pal.dim_text)
    if ylabel:
        p.setLabel("left", ylabel, color=pal.dim_text)
    if title:
        p.setTitle(title, color=pal.text, size="10pt")


def _stage_ticks(result: CascadeResult):
    ticks = [(0, "in")]
    for i, st in enumerate(result.stages, start=1):
        name = st.name if len(st.name) <= 11 else st.name[:10] + "…"
        ticks.append((i, name))
    return [ticks]


# ---------------------------------------------------------------------------
class LevelDiagram(QWidget):
    """The classic system level diagram: signal / noise / P1dB / IP3 vs node."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        self.plot = pg.PlotWidget()
        self.legend = self.plot.addLegend(offset=(-10, 10), labelTextColor=theme.current_palette().text)
        _style_plot(self.plot.getPlotItem(), "Node", "Power (dBm)", "Signal Level Diagram")
        lay.addWidget(self.plot)

    def update_result(self, result: CascadeResult):
        pal = theme.current_palette()
        self.plot.clear()
        self.legend.clear()
        if result.summary.n_stages == 0:
            return

        n = len(result.stages)
        x = list(range(0, n + 1))
        sig = [result.summary.input_power_dbm] + [s.node_power_dbm for s in result.stages]
        noise = [result.summary.input_noise_dbm] + [s.node_noise_dbm for s in result.stages]

        xs = list(range(1, n + 1))
        op1 = [s.cum_op1db_dbm for s in result.stages]
        oip3 = [s.cum_oip3_dbm for s in result.stages]

        # Headroom shading between signal and OP1dB.
        self.plot.plot(x, sig, pen=_pen(pal.accent, 2.6),
                       symbol="o", symbolSize=7, symbolBrush=pal.accent,
                       symbolPen=pal.accent, name="Signal")
        self.plot.plot(x, noise, pen=_pen(pal.bad, 2.0),
                       symbol="t", symbolSize=6, symbolBrush=pal.bad,
                       symbolPen=pal.bad, name="Noise floor")

        op1_f = [v if math.isfinite(v) else np.nan for v in op1]
        oip3_f = [v if math.isfinite(v) else np.nan for v in oip3]
        if any(math.isfinite(v) for v in op1):
            self.plot.plot(xs, op1_f, pen=_pen(pal.warn, 1.8, [6, 5]),
                           symbol="s", symbolSize=5, symbolBrush=pal.warn,
                           symbolPen=pal.warn, name="Cum OP1dB")
        if any(math.isfinite(v) for v in oip3):
            self.plot.plot(xs, oip3_f, pen=_pen(pal.accent_2, 1.6, [3, 4]),
                           symbol="d", symbolSize=5, symbolBrush=pal.accent_2,
                           symbolPen=pal.accent_2, name="Cum OIP3")

        ax = self.plot.getAxis("bottom")
        ax.setTicks(_stage_ticks(result))
        self.plot.getPlotItem().setTitle("Signal Level Diagram", color=pal.text, size="10pt")
        self.plot.enableAutoRange()


# ---------------------------------------------------------------------------
class MetricsView(QWidget):
    """2×2 grid of cumulative metric plots vs stage."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        self.glw = pg.GraphicsLayoutWidget()
        lay.addWidget(self.glw)

        self.p_gain = self.glw.addPlot(row=0, col=0)
        self.p_nf = self.glw.addPlot(row=0, col=1)
        self.p_ip3 = self.glw.addPlot(row=1, col=0)
        self.p_snr = self.glw.addPlot(row=1, col=1)
        _style_plot(self.p_gain, "", "dB", "Cumulative Gain")
        _style_plot(self.p_nf, "", "dB", "Cumulative Noise Figure")
        _style_plot(self.p_ip3, "Stage", "dBm", "Cumulative IIP3 / OIP3")
        _style_plot(self.p_snr, "Stage", "dB", "SNR through chain")

    def update_result(self, result: CascadeResult):
        pal = theme.current_palette()
        for p in (self.p_gain, self.p_nf, self.p_ip3, self.p_snr):
            p.clear()
        if result.summary.n_stages == 0:
            return

        n = len(result.stages)
        xs = list(range(1, n + 1))
        ticks = _stage_ticks(result)

        gain = [s.cum_gain_db for s in result.stages]
        per_stage_gain = [s.gain_db for s in result.stages]
        self.p_gain.plot([0] + xs, [0] + gain, pen=_pen(pal.accent, 2.4),
                         symbol="o", symbolSize=6, symbolBrush=pal.accent, symbolPen=pal.accent)
        bg = pg.BarGraphItem(x=xs, height=per_stage_gain, width=0.35,
                             brush=QColor(pal.accent_2), pen=None)
        self.p_gain.addItem(bg)

        nf = [s.cum_nf_db for s in result.stages]
        self.p_nf.plot(xs, nf, pen=_pen(pal.warn, 2.4),
                       symbol="o", symbolSize=6, symbolBrush=pal.warn, symbolPen=pal.warn)

        iip3 = [s.cum_iip3_dbm if math.isfinite(s.cum_iip3_dbm) else np.nan for s in result.stages]
        oip3 = [s.cum_oip3_dbm if math.isfinite(s.cum_oip3_dbm) else np.nan for s in result.stages]
        self.p_ip3.plot(xs, iip3, pen=_pen(pal.good, 2.2), symbol="o",
                        symbolSize=6, symbolBrush=pal.good, symbolPen=pal.good)
        self.p_ip3.plot(xs, oip3, pen=_pen(pal.accent_2, 2.2, [4, 4]), symbol="d",
                        symbolSize=6, symbolBrush=pal.accent_2, symbolPen=pal.accent_2)

        snr = [result.summary.input_snr_db] + [s.node_snr_db for s in result.stages]
        self.p_snr.plot(list(range(0, n + 1)), snr, pen=_pen(pal.accent, 2.4),
                        symbol="o", symbolSize=6, symbolBrush=pal.accent, symbolPen=pal.accent)

        for p in (self.p_gain, self.p_nf, self.p_ip3, self.p_snr):
            p.getAxis("bottom").setTicks(ticks)
            p.enableAutoRange()


# ---------------------------------------------------------------------------
class SweepView(QWidget):
    """Two-tone input-power sweep: fundamental / IM3 / IM2 / noise floor."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._source: Optional[SignalSource] = None
        self._components: List[Component] = []
        self._imd = IMDMode.COHERENT

        root = QVBoxLayout(self)
        root.setContentsMargins(2, 2, 2, 2)

        ctl = QHBoxLayout()
        ctl.addWidget(QLabel("Pin start"))
        self.start = self._spin(-120, 30, -70, " dBm")
        ctl.addWidget(self.start)
        ctl.addWidget(QLabel("Pin stop"))
        self.stop = self._spin(-120, 50, 10, " dBm")
        ctl.addWidget(self.stop)
        ctl.addWidget(QLabel("Points"))
        self.points = QSpinBox()
        self.points.setRange(11, 1001)
        self.points.setValue(161)
        ctl.addWidget(self.points)
        self.run_btn = QPushButton("Run Sweep")
        self.run_btn.setObjectName("Primary")
        self.run_btn.clicked.connect(self.run)
        ctl.addWidget(self.run_btn)
        ctl.addStretch(1)
        self.readout = QLabel("")
        self.readout.setObjectName("SubHeading")
        ctl.addWidget(self.readout)
        root.addLayout(ctl)

        self.plot = pg.PlotWidget()
        self.legend = self.plot.addLegend(offset=(10, 10))
        _style_plot(self.plot.getPlotItem(), "Per-tone input power (dBm)",
                    "Output power (dBm)", "Two-Tone Sweep — Fundamental vs IMD")
        root.addWidget(self.plot)

    def _spin(self, lo, hi, val, suffix):
        sb = QDoubleSpinBox()
        sb.setRange(lo, hi)
        sb.setValue(val)
        sb.setSuffix(suffix)
        sb.setAlignment(Qt.AlignRight)
        return sb

    def set_inputs(self, source: SignalSource, components: List[Component], imd: IMDMode):
        self._source, self._components, self._imd = source, components, imd

    def run(self):
        if self._source is None:
            return
        pal = theme.current_palette()
        r = sweep_mod.input_power_sweep(
            self._source, self._components,
            self.start.value(), self.stop.value(), self.points.value(), self._imd,
        )
        self.plot.clear()
        self.legend.clear()

        self.plot.plot(r.pin_dbm, r.fundamental_dbm, pen=_pen(pal.accent, 2.6), name="Fundamental")
        if np.all(np.isfinite(r.im3_dbm)):
            self.plot.plot(r.pin_dbm, r.im3_dbm, pen=_pen(pal.bad, 2.2), name="IM3")
        if np.all(np.isfinite(r.im2_dbm)):
            self.plot.plot(r.pin_dbm, r.im2_dbm, pen=_pen(pal.warn, 2.0, [5, 4]), name="IM2")

        nf_line = pg.InfiniteLine(pos=r.noise_floor_dbm, angle=0,
                                  pen=_pen(pal.dim_text, 1.4, [3, 4]),
                                  label=f"noise {r.noise_floor_dbm:.0f} dBm",
                                  labelOpts={"color": pal.dim_text, "position": 0.05})
        self.plot.addItem(nf_line)

        if math.isfinite(r.oip3_dbm):
            oip3_line = pg.InfiniteLine(pos=r.oip3_dbm, angle=0,
                                        pen=_pen(pal.accent_2, 1.2, [2, 4]),
                                        label=f"OIP3 {r.oip3_dbm:.0f}",
                                        labelOpts={"color": pal.accent_2, "position": 0.9})
            self.plot.addItem(oip3_line)

        # SFDR estimate where IM3 meets the noise floor.
        sfdr_txt = ""
        if math.isfinite(r.oip3_dbm):
            res = sweep_mod.analyze(self._source, self._components, self._imd).summary
            sfdr_txt = f"   SFDR(IM3) ≈ {res.sfdr_db:.1f} dB"
        self.readout.setText(f"Gain {r.gain_db:.1f} dB · OIP3 {r.oip3_dbm:.1f} dBm{sfdr_txt}")
        self.plot.enableAutoRange()


# ---------------------------------------------------------------------------
class MonteCarloView(QWidget):
    """Monte-Carlo tolerance histograms with summary statistics."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._source: Optional[SignalSource] = None
        self._components: List[Component] = []
        self._imd = IMDMode.COHERENT
        self._result: Optional[mc_mod.MonteCarloResult] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(2, 2, 2, 2)

        ctl = QHBoxLayout()
        ctl.addWidget(QLabel("Trials"))
        self.trials = QSpinBox()
        self.trials.setRange(100, 200000)
        self.trials.setValue(3000)
        self.trials.setSingleStep(500)
        ctl.addWidget(self.trials)
        ctl.addWidget(QLabel("Metric"))
        self.metric_combo = QComboBox()
        for k, label in mc_mod.MonteCarloResult.METRIC_LABELS.items():
            self.metric_combo.addItem(label, k)
        self.metric_combo.currentIndexChanged.connect(self._redraw)
        ctl.addWidget(self.metric_combo)
        self.run_btn = QPushButton("Run Monte Carlo")
        self.run_btn.setObjectName("Primary")
        self.run_btn.clicked.connect(self.run)
        ctl.addWidget(self.run_btn)
        ctl.addStretch(1)
        root.addLayout(ctl)

        self.stats = QLabel("Set per-component tolerances (gain / NF / OIP3) then run.")
        self.stats.setObjectName("SubHeading")
        root.addWidget(self.stats)

        self.plot = pg.PlotWidget()
        _style_plot(self.plot.getPlotItem(), "Value", "Count", "Distribution")
        root.addWidget(self.plot)

    def set_inputs(self, source: SignalSource, components: List[Component], imd: IMDMode):
        self._source, self._components, self._imd = source, components, imd

    def run(self):
        if self._source is None:
            return
        self.run_btn.setEnabled(False)
        self.run_btn.setText("Running…")
        self.run_btn.repaint()
        try:
            self._result = mc_mod.run_montecarlo(
                self._source, self._components, self.trials.value(), self._imd)
        finally:
            self.run_btn.setEnabled(True)
            self.run_btn.setText("Run Monte Carlo")
        self._redraw()

    def _redraw(self):
        pal = theme.current_palette()
        self.plot.clear()
        if self._result is None or self._result.trials == 0:
            return
        key = self.metric_combo.currentData()
        data = self._result.samples.get(key)
        if data is None:
            return
        data = data[np.isfinite(data)]
        if len(data) == 0:
            self.stats.setText("No finite samples for this metric.")
            return

        counts, edges = np.histogram(data, bins=40)
        centers = (edges[:-1] + edges[1:]) / 2.0
        width = (edges[1] - edges[0]) * 0.92
        bars = pg.BarGraphItem(x=centers, height=counts, width=width,
                               brush=QColor(pal.accent), pen=None)
        self.plot.addItem(bars)

        st = self._result.stats(key)
        for pos, col, lbl in ((st["p2.5"], pal.warn, "2.5%"),
                              (st["mean"], pal.bad, "mean"),
                              (st["p97.5"], pal.warn, "97.5%")):
            self.plot.addItem(pg.InfiniteLine(pos=pos, angle=90,
                              pen=_pen(col, 1.6, [4, 4]),
                              label=lbl, labelOpts={"color": col, "position": 0.95}))

        label = mc_mod.MonteCarloResult.METRIC_LABELS[key]
        self.plot.getPlotItem().setLabel("bottom", label, color=pal.dim_text)
        self.stats.setText(
            f"{label}:   μ = {st['mean']:.2f}   σ = {st['std']:.3f}   "
            f"95% CI [{st['p2.5']:.2f}, {st['p97.5']:.2f}]   "
            f"min {st['min']:.2f} / max {st['max']:.2f}   "
            f"({self._result.trials} trials)"
        )
        self.plot.enableAutoRange()


# ---------------------------------------------------------------------------
class FreqResponseView(QWidget):
    """Cascaded S-parameter frequency response: |S21| / |S11| / |S22|, VSWR,
    group delay and phase of the whole chain over a swept frequency band."""

    MODES = ["Magnitude (dB)", "VSWR", "Group delay (ns)", "S21 phase (deg)"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._source: Optional[SignalSource] = None
        self._components: List[Component] = []
        self._range_user_set = False
        self._net: Optional[sparams_mod.SParams] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(2, 2, 2, 2)

        ctl = QHBoxLayout()
        ctl.addWidget(QLabel("From"))
        self.fstart = QLineEdit("0.1 GHz")
        self.fstart.setMaximumWidth(96)
        ctl.addWidget(self.fstart)
        ctl.addWidget(QLabel("to"))
        self.fstop = QLineEdit("3 GHz")
        self.fstop.setMaximumWidth(96)
        ctl.addWidget(self.fstop)
        ctl.addWidget(QLabel("Points"))
        self.points = QSpinBox()
        self.points.setRange(51, 8001)
        self.points.setValue(601)
        self.points.setSingleStep(50)
        ctl.addWidget(self.points)

        ctl.addSpacing(10)
        self.mode = QComboBox()
        self.mode.addItems(self.MODES)
        ctl.addWidget(self.mode)

        self.cb_s21 = QCheckBox("S21"); self.cb_s21.setChecked(True)
        self.cb_s11 = QCheckBox("S11"); self.cb_s11.setChecked(True)
        self.cb_s22 = QCheckBox("S22")
        for cb in (self.cb_s21, self.cb_s11, self.cb_s22):
            ctl.addWidget(cb)

        self.auto_btn = QPushButton("Auto span")
        self.auto_btn.clicked.connect(self._auto_range)
        ctl.addWidget(self.auto_btn)
        ctl.addStretch(1)
        root.addLayout(ctl)

        self.readout = QLabel("")
        self.readout.setObjectName("SubHeading")
        root.addWidget(self.readout)

        self.plot = pg.PlotWidget()
        self.legend = self.plot.addLegend(offset=(-10, 10),
                                          labelTextColor=theme.current_palette().text)
        _style_plot(self.plot.getPlotItem(), "Frequency (Hz)", "dB",
                    "Cascaded Frequency Response")
        root.addWidget(self.plot)

        for w in (self.fstart, self.fstop):
            w.editingFinished.connect(self._on_range_edited)
        self.points.valueChanged.connect(self.refresh)
        self.mode.currentIndexChanged.connect(self.refresh)
        for cb in (self.cb_s21, self.cb_s11, self.cb_s22):
            cb.toggled.connect(self.refresh)

    # ---- inputs --------------------------------------------------------------
    def set_inputs(self, source: SignalSource, components: List[Component], imd=None):
        first = self._source is None
        self._source, self._components = source, components
        if (first or not self._range_user_set) and source is not None:
            self._auto_range(silent=True)
        self.refresh()

    def _on_range_edited(self):
        self._range_user_set = True
        self.refresh()

    def _auto_range(self, silent: bool = False):
        """Pick a sensible band centred on the source / stage frequencies."""
        fset = []
        if self._source is not None and self._source.frequency_hz:
            fset.append(self._source.frequency_hz)
        for c in self._components:
            if c.enabled and c.frequency_hz:
                fset.append(c.frequency_hz)
        if not fset:
            fset = [1e9]
        lo, hi = min(fset), max(fset)
        start = max(lo * 0.2, 1e3)
        stop = hi * 3.0 if hi == lo else hi * 1.6
        self.fstart.setText(units.format_eng(start, "Hz", 3))
        self.fstop.setText(units.format_eng(stop, "Hz", 3))
        self._range_user_set = False
        if not silent:
            self.refresh()

    def _freqs(self) -> np.ndarray:
        try:
            f0 = units.parse_frequency(self.fstart.text())
            f1 = units.parse_frequency(self.fstop.text())
        except ValueError:
            return np.array([])
        if f1 <= f0 or f0 <= 0:
            return np.array([])
        return np.linspace(f0, f1, self.points.value())

    # ---- draw ----------------------------------------------------------------
    def refresh(self):
        if self._source is None:
            return
        pal = theme.current_palette()
        self.plot.clear()
        self.legend.clear()

        freqs = self._freqs()
        active = [c for c in self._components if c.enabled]
        if freqs.size == 0 or not active:
            self.readout.setText("Add stages and set a valid frequency span.")
            return

        net = frequency_response(self._source, self._components, freqs)
        self._net = net
        mode = self.mode.currentText()

        if mode == self.MODES[0]:       # magnitude dB
            self.plot.getPlotItem().setLabel("left", "Magnitude (dB)", color=pal.dim_text)
            if self.cb_s21.isChecked():
                self.plot.plot(freqs, net.s21_db(), pen=_pen(pal.accent, 2.4), name="S21")
            if self.cb_s11.isChecked():
                self.plot.plot(freqs, net.s11_db(), pen=_pen(pal.warn, 1.8, [6, 5]), name="S11")
            if self.cb_s22.isChecked():
                self.plot.plot(freqs, net.s22_db(), pen=_pen(pal.accent_2, 1.8, [3, 4]), name="S22")
        elif mode == self.MODES[1]:     # VSWR
            self.plot.getPlotItem().setLabel("left", "VSWR", color=pal.dim_text)
            self.plot.plot(freqs, net.vswr_in(), pen=_pen(pal.accent, 2.2), name="VSWR in")
            self.plot.plot(freqs, net.vswr_out(), pen=_pen(pal.accent_2, 1.8, [4, 4]), name="VSWR out")
        elif mode == self.MODES[2]:     # group delay
            self.plot.getPlotItem().setLabel("left", "Group delay (ns)", color=pal.dim_text)
            self.plot.plot(freqs, net.group_delay() * 1e9, pen=_pen(pal.accent, 2.2), name="S21 GD")
        else:                            # phase
            self.plot.getPlotItem().setLabel("left", "Phase (deg)", color=pal.dim_text)
            self.plot.plot(freqs, net.s21_phase_deg(), pen=_pen(pal.accent, 2.2), name="S21 phase")

        # marker at the source design frequency
        if self._source.frequency_hz and freqs[0] <= self._source.frequency_hz <= freqs[-1]:
            self.plot.addItem(pg.InfiniteLine(
                pos=self._source.frequency_hz, angle=90,
                pen=_pen(pal.dim_text, 1.2, [2, 4]),
                label="f0", labelOpts={"color": pal.dim_text, "position": 0.04}))

        self._update_readout(net)
        self.plot.enableAutoRange()

    def _update_readout(self, net: sparams_mod.SParams):
        il = sparams_mod.insertion_loss_db_at(net, self._source.frequency_hz) \
            if self._source.frequency_hz else net.s21_db().max()
        f_lo, f_hi, bw = sparams_mod.passband_edges_db(net, drop_db=3.0)
        rl_in = -float(np.max(net.s11_db()))
        bw_txt = f"−3 dB BW {units.format_eng(bw, 'Hz', 3)}" if bw == bw else "−3 dB BW —"
        edge_txt = (f"[{units.format_eng(f_lo, 'Hz', 3)} … {units.format_eng(f_hi, 'Hz', 3)}]"
                    if f_lo == f_lo else "")
        self.readout.setText(
            f"S21 @ f0: {il:+.2f} dB    ·    {bw_txt} {edge_txt}    ·    "
            f"worst input return loss {rl_in:.1f} dB    ·    Z0 {net.z0:g} Ω"
        )
