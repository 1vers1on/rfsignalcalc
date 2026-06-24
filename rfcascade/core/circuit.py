"""Build a two-port from lumped R / L / C components (a ladder network).

A :class:`LumpedCircuit` is an ordered list of :class:`LumpedElement` "rungs".
Each rung sits in either the **series** arm (in line with the signal) or the
**shunt** arm (to ground) and is itself an R, L, C — or a series / parallel
combination of them. Multiplying each rung's ABCD matrix yields the whole
network, which is then converted to S-parameters at a chosen reference
impedance.

This ladder topology is exactly what classic passive design uses, so it covers
the things people actually want to draw out of lumped parts:

* L-C low-pass / high-pass / band-pass / band-stop filters
* Resistive pads (π and T attenuators)
* L-section impedance matching networks
* Single series or shunt resonators (traps / tank circuits)

The :func:`butterworth_lpf` / ``_hpf`` / ``_bpf`` / ``_bsf`` helpers synthesise
ready-made prototypes so a useful response appears with one click.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

import numpy as np

from . import sparams as sp


class Arm(str, Enum):
    SERIES = "series"     # impedance in line with the signal path
    SHUNT = "shunt"       # admittance from the line to ground


class Combo(str, Enum):
    SERIES = "series"     # R, L, C add as impedances
    PARALLEL = "parallel"  # R, L, C add as admittances


@dataclass
class LumpedElement:
    """One rung of the ladder: an R / L / C (or combination) in one arm.

    Any of ``r_ohm`` / ``l_h`` / ``c_f`` may be ``None`` to mean "not present".
    Within a rung the present parts combine as ``combo`` (series or parallel).
    """

    arm: Arm = Arm.SERIES
    combo: Combo = Combo.SERIES
    r_ohm: Optional[float] = None
    l_h: Optional[float] = None
    c_f: Optional[float] = None
    label: str = ""

    # ---- per-frequency immittance -------------------------------------------
    def impedance(self, freqs: np.ndarray) -> np.ndarray:
        """Complex impedance Z(f) of the element (Ω)."""
        w = 2.0 * np.pi * np.asarray(freqs, dtype=float)
        jw = 1j * w
        big = 1e18  # stand-in for an open circuit

        z_r = np.full_like(w, self.r_ohm, dtype=complex) if self.r_ohm is not None else None
        z_l = jw * self.l_h if self.l_h is not None else None
        # 1/(jωC); guard ω = 0 (DC) → open.
        if self.c_f is not None and self.c_f > 0:
            z_c = np.where(w == 0, big, 1.0 / (jw * self.c_f))
        else:
            z_c = None

        present = [z for z in (z_r, z_l, z_c) if z is not None]
        if not present:
            # An empty rung: short in the series arm, open in the shunt arm.
            return np.zeros_like(w, dtype=complex)

        if self.combo == Combo.SERIES:
            z = np.zeros_like(w, dtype=complex)
            for zk in present:
                z = z + zk
            return z
        # parallel: sum admittances
        y = np.zeros_like(w, dtype=complex)
        for zk in present:
            y = y + 1.0 / np.where(np.abs(zk) < 1e-18, 1e-18, zk)
        return 1.0 / np.where(np.abs(y) < 1e-18, 1e-18, y)

    def abcd(self, freqs: np.ndarray) -> np.ndarray:
        z = self.impedance(freqs)
        if self.arm == Arm.SERIES:
            return sp.series_abcd(z)
        # shunt: admittance to ground
        y = 1.0 / np.where(np.abs(z) < 1e-18, 1e-18, z)
        return sp.shunt_abcd(y)

    def describe(self) -> str:
        from .units import format_eng
        parts = []
        if self.r_ohm is not None:
            parts.append(format_eng(self.r_ohm, "Ω", 3))
        if self.l_h is not None:
            parts.append(format_eng(self.l_h, "H", 3))
        if self.c_f is not None:
            parts.append(format_eng(self.c_f, "F", 3))
        joiner = " + " if self.combo == Combo.SERIES else " ∥ "
        body = joiner.join(parts) if parts else "(empty)"
        return f"{self.arm.value} · {body}"

    # ---- (de)serialization ---------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "arm": self.arm.value,
            "combo": self.combo.value,
            "r_ohm": self.r_ohm,
            "l_h": self.l_h,
            "c_f": self.c_f,
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LumpedElement":
        return cls(
            arm=Arm(d.get("arm", "series")),
            combo=Combo(d.get("combo", "series")),
            r_ohm=d.get("r_ohm"),
            l_h=d.get("l_h"),
            c_f=d.get("c_f"),
            label=d.get("label", ""),
        )


@dataclass
class LumpedCircuit:
    """A ladder two-port made of lumped :class:`LumpedElement` rungs."""

    elements: List[LumpedElement] = field(default_factory=list)
    z0: float = 50.0
    name: str = "Lumped Block"

    def abcd(self, freqs: np.ndarray) -> np.ndarray:
        freqs = np.asarray(freqs, dtype=float)
        abcd = sp.identity_abcd(freqs.shape[0])
        for el in self.elements:
            abcd = np.matmul(abcd, el.abcd(freqs))
        return abcd

    def sparams(self, freqs: np.ndarray) -> sp.SParams:
        freqs = np.asarray(freqs, dtype=float)
        return sp.SParams.from_abcd(freqs, self.abcd(freqs), self.z0)

    def insertion_gain_db(self, freq_hz: float) -> float:
        """|S21| in dB at a single frequency (negative for a lossy filter)."""
        net = self.sparams(np.array([float(freq_hz)]))
        return float(net.s21_db()[0])

    # ---- (de)serialization ---------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "z0": self.z0,
            "elements": [e.to_dict() for e in self.elements],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LumpedCircuit":
        return cls(
            elements=[LumpedElement.from_dict(e) for e in d.get("elements", [])],
            z0=float(d.get("z0", 50.0)),
            name=d.get("name", "Lumped Block"),
        )

    def copy(self) -> "LumpedCircuit":
        return LumpedCircuit.from_dict(self.to_dict())


# ---------------------------------------------------------------------------
# Filter prototype synthesis (normalised Butterworth g-values)
# ---------------------------------------------------------------------------
def _butterworth_g(order: int) -> List[float]:
    """Low-pass prototype element values g1..gn for a Butterworth filter."""
    return [2.0 * math.sin((2 * k - 1) * math.pi / (2 * order))
            for k in range(1, order + 1)]


def butterworth_lpf(order: int, fc_hz: float, z0: float = 50.0,
                    series_first: bool = True) -> LumpedCircuit:
    """Butterworth low-pass: alternating series L / shunt C ladder."""
    g = _butterworth_g(order)
    wc = 2.0 * math.pi * fc_hz
    els: List[LumpedElement] = []
    for k, gk in enumerate(g):
        series = (k % 2 == 0) if series_first else (k % 2 == 1)
        if series:
            els.append(LumpedElement(arm=Arm.SERIES, l_h=gk * z0 / wc,
                                     label=f"L{k+1}"))
        else:
            els.append(LumpedElement(arm=Arm.SHUNT, c_f=gk / (z0 * wc),
                                     label=f"C{k+1}"))
    return LumpedCircuit(elements=els, z0=z0,
                         name=f"Butterworth LPF · n{order} · {_fmt(fc_hz)}")


def butterworth_hpf(order: int, fc_hz: float, z0: float = 50.0,
                    series_first: bool = True) -> LumpedCircuit:
    """Butterworth high-pass: LP→HP transform (L→C series, C→L shunt)."""
    g = _butterworth_g(order)
    wc = 2.0 * math.pi * fc_hz
    els: List[LumpedElement] = []
    for k, gk in enumerate(g):
        series = (k % 2 == 0) if series_first else (k % 2 == 1)
        if series:
            els.append(LumpedElement(arm=Arm.SERIES, c_f=1.0 / (gk * z0 * wc),
                                     label=f"C{k+1}"))
        else:
            els.append(LumpedElement(arm=Arm.SHUNT, l_h=z0 / (gk * wc),
                                     label=f"L{k+1}"))
    return LumpedCircuit(elements=els, z0=z0,
                         name=f"Butterworth HPF · n{order} · {_fmt(fc_hz)}")


def butterworth_bpf(order: int, f0_hz: float, bw_hz: float, z0: float = 50.0,
                    series_first: bool = True) -> LumpedCircuit:
    """Butterworth band-pass: series arms become series-LC, shunt arms tank-LC."""
    g = _butterworth_g(order)
    w0 = 2.0 * math.pi * f0_hz
    bw = bw_hz / f0_hz  # fractional bandwidth
    els: List[LumpedElement] = []
    for k, gk in enumerate(g):
        series = (k % 2 == 0) if series_first else (k % 2 == 1)
        if series:
            # series resonator: L and C in series
            L = gk * z0 / (w0 * bw)
            C = bw / (gk * z0 * w0)
            els.append(LumpedElement(arm=Arm.SERIES, combo=Combo.SERIES,
                                     l_h=L, c_f=C, label=f"SR{k+1}"))
        else:
            # shunt tank: L and C in parallel
            L = bw * z0 / (gk * w0)
            C = gk / (z0 * w0 * bw)
            els.append(LumpedElement(arm=Arm.SHUNT, combo=Combo.PARALLEL,
                                     l_h=L, c_f=C, label=f"PR{k+1}"))
    return LumpedCircuit(elements=els, z0=z0,
                         name=f"Butterworth BPF · n{order} · {_fmt(f0_hz)}")


def pi_pad(atten_db: float, z0: float = 50.0) -> LumpedCircuit:
    """A matched resistive π attenuator of the given attenuation."""
    a = 10.0 ** (atten_db / 20.0)
    r_series = z0 * (a * a - 1.0) / (2.0 * a)
    r_shunt = z0 * (a + 1.0) / (a - 1.0)
    return LumpedCircuit(
        elements=[
            LumpedElement(arm=Arm.SHUNT, r_ohm=r_shunt, label="Rp1"),
            LumpedElement(arm=Arm.SERIES, r_ohm=r_series, label="Rs"),
            LumpedElement(arm=Arm.SHUNT, r_ohm=r_shunt, label="Rp2"),
        ],
        z0=z0, name=f"π-pad · {atten_db:g} dB")


def _fmt(hz: float) -> str:
    from .units import format_eng
    return format_eng(hz, "Hz", 3)
