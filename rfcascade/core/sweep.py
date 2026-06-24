"""Input-power sweep: the classic two-tone fundamental / IM3 / IM2 plot.

For a swept per-tone input power it computes the ideal fundamental output, the
third- and second-order intermodulation product levels at the output, and the
(constant) output noise floor. Where IM3 crosses the noise floor defines the
spurious-free dynamic range graphically.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List

import numpy as np

from .components import SignalSource, Component
from .cascade import analyze, IMDMode


@dataclass
class SweepResult:
    pin_dbm: np.ndarray = field(default_factory=lambda: np.array([]))
    fundamental_dbm: np.ndarray = field(default_factory=lambda: np.array([]))
    im3_dbm: np.ndarray = field(default_factory=lambda: np.array([]))
    im2_dbm: np.ndarray = field(default_factory=lambda: np.array([]))
    noise_floor_dbm: float = -math.inf
    gain_db: float = 0.0
    oip3_dbm: float = math.inf
    oip2_dbm: float = math.inf
    op1db_dbm: float = math.inf


def input_power_sweep(
    source: SignalSource,
    components: List[Component],
    pin_start: float = -60.0,
    pin_stop: float = 10.0,
    points: int = 141,
    imd_mode: IMDMode = IMDMode.COHERENT,
) -> SweepResult:
    res = analyze(source, components, imd_mode)
    s = res.summary

    pin = np.linspace(pin_start, pin_stop, points)
    g = s.total_gain_db

    fundamental = pin + g

    if math.isfinite(s.iip3_dbm):
        im3 = g + 3.0 * pin - 2.0 * s.iip3_dbm
    else:
        im3 = np.full_like(pin, -np.inf)

    if math.isfinite(s.iip2_dbm):
        im2 = g + 2.0 * pin - s.iip2_dbm
    else:
        im2 = np.full_like(pin, -np.inf)

    return SweepResult(
        pin_dbm=pin,
        fundamental_dbm=fundamental,
        im3_dbm=im3,
        im2_dbm=im2,
        noise_floor_dbm=s.output_noise_dbm,
        gain_db=g,
        oip3_dbm=s.oip3_dbm,
        oip2_dbm=s.oip2_dbm,
        op1db_dbm=s.op1db_dbm,
    )
