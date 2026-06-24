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
    QComboBox, QDoubleSpinBox, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QVBoxLayout, QWidget,
)

from ..core.cascade import CascadeResult
from ..core.components import SignalSource, Component
from ..core import sweep as sweep_mod
from ..core import montecarlo as mc_mod
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
