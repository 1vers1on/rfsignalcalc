"""Input signal-source configuration panel."""

from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QVBoxLayout, QWidget,
)

from ..core.components import SignalSource
from ..core.cascade import IMDMode
from ..core import units


class _FreqEdit(QLineEdit):
    """Line edit that parses/echoes engineering-notation frequencies."""

    valueChanged = Signal(float)

    def __init__(self, value_hz: float, parent=None):
        super().__init__(parent)
        self._hz = value_hz
        self.setText(units.format_eng(value_hz, "Hz", 4))
        self.editingFinished.connect(self._commit)
        self.setMinimumWidth(110)

    def _commit(self):
        try:
            self._hz = units.parse_frequency(self.text())
        except ValueError:
            pass
        self.setText(units.format_eng(self._hz, "Hz", 4))
        self.valueChanged.emit(self._hz)

    def value(self) -> float:
        return self._hz


class SourcePanel(QGroupBox):
    """Editing widget for the `SignalSource`. Emits `sourceChanged`."""

    sourceChanged = Signal()
    imdModeChanged = Signal(object)

    def __init__(self, source: SignalSource, imd_mode: IMDMode, parent=None):
        super().__init__("Signal Source & Analysis", parent)
        self._source = source

        def spin(lo, hi, val, step, suffix, decimals=2):
            sb = QDoubleSpinBox()
            sb.setRange(lo, hi)
            sb.setValue(val)
            sb.setSingleStep(step)
            sb.setSuffix(suffix)
            sb.setDecimals(decimals)
            sb.setMinimumWidth(110)
            sb.setAlignment(Qt.AlignRight)
            return sb

        self.power = spin(-200, 100, source.power_dbm, 1.0, " dBm")
        self.freq = _FreqEdit(source.frequency_hz)
        self.bw = _FreqEdit(source.bandwidth_hz)
        self.temp = spin(0, 5000, source.temperature_k, 10.0, " K", 1)
        self.snr = spin(-50, 200, source.required_snr_db, 1.0, " dB")

        self.imd = QComboBox()
        for m in IMDMode:
            self.imd.addItem(m.value, m)
        i = self.imd.findData(imd_mode)
        if i >= 0:
            self.imd.setCurrentIndex(i)

        # Two compact columns of fields.
        col1 = QFormLayout()
        col1.setLabelAlignment(Qt.AlignRight)
        col1.addRow("Input power", self.power)
        col1.addRow("Frequency", self.freq)
        col1.addRow("Bandwidth", self.bw)

        col2 = QFormLayout()
        col2.setLabelAlignment(Qt.AlignRight)
        col2.addRow("Source temp", self.temp)
        col2.addRow("Required SNR", self.snr)
        col2.addRow("IM3/IM2 add", self.imd)

        cols = QHBoxLayout()
        cols.addLayout(col1)
        cols.addSpacing(18)
        cols.addLayout(col2)
        cols.addStretch(1)

        self.hint = QLabel()
        self.hint.setObjectName("SubHeading")
        self._update_hint()

        root = QVBoxLayout(self)
        root.addLayout(cols)
        root.addWidget(self.hint)

        for w in (self.power, self.temp, self.snr):
            w.valueChanged.connect(self._on_change)
        self.freq.valueChanged.connect(self._on_change)
        self.bw.valueChanged.connect(self._on_change)
        self.imd.currentIndexChanged.connect(self._on_imd)

    def _update_hint(self):
        nfloor = units.thermal_noise_dbm(self._source.bandwidth_hz, self._source.temperature_k)
        self.hint.setText(
            f"Thermal noise floor: {nfloor:.1f} dBm  "
            f"({units.noise_density_dbm_per_hz(self._source.temperature_k):.1f} dBm/Hz "
            f"+ {units.lin_to_db(self._source.bandwidth_hz):.1f} dB·Hz)"
        )

    def _pull(self):
        self._source.power_dbm = self.power.value()
        self._source.frequency_hz = self.freq.value()
        self._source.bandwidth_hz = self.bw.value()
        self._source.temperature_k = self.temp.value()
        self._source.required_snr_db = self.snr.value()

    def _on_change(self, *_):
        self._pull()
        self._update_hint()
        self.sourceChanged.emit()

    def _on_imd(self, *_):
        self.imdModeChanged.emit(self.imd.currentData())

    def imd_mode(self) -> IMDMode:
        return self.imd.currentData()

    def set_source(self, source: SignalSource):
        self._source = source
        self.power.setValue(source.power_dbm)
        self.freq.setText(units.format_eng(source.frequency_hz, "Hz", 4))
        self.bw.setText(units.format_eng(source.bandwidth_hz, "Hz", 4))
        self.temp.setValue(source.temperature_k)
        self.snr.setValue(source.required_snr_db)
        self._update_hint()
