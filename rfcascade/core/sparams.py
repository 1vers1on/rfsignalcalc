"""Two-port S-parameter networks over frequency.

This module adds the *frequency-domain* dimension to the analyzer. Where the
cascade engine (``cascade.py``) is scalar and single-frequency, an
:class:`SParams` object carries the full complex S-matrix of a two-port versus
frequency, so filters, matching networks and measured parts can be combined and
plotted as |S21| / |S11| / VSWR / group-delay curves.

Conventions
-----------
* Everything is a **two-port** referenced to a real impedance ``z0`` (default
  50 Ω). One-ports are stored as two-ports with the second port open / ignored
  where needed.
* ``s`` has shape ``(F, 2, 2)`` with the usual index order
  ``[[S11, S12], [S21, S22]]``.
* Cascading is done through **ABCD (chain) parameters** which multiply for
  series-connected two-ports; the result is converted back to S.

The S↔ABCD relations used here are the standard ones (e.g. Pozar, *Microwave
Engineering*, Table 4.2), valid for a real reference impedance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional

import numpy as np


@dataclass
class SParams:
    """Complex two-port S-parameters sampled on a frequency grid."""

    freqs: np.ndarray            # Hz, shape (F,)
    s: np.ndarray                # complex, shape (F, 2, 2)
    z0: float = 50.0

    # ---- construction --------------------------------------------------------
    def __post_init__(self) -> None:
        self.freqs = np.asarray(self.freqs, dtype=float)
        self.s = np.asarray(self.s, dtype=complex)
        if self.s.ndim != 3 or self.s.shape[1:] != (2, 2):
            raise ValueError("S-parameter array must have shape (F, 2, 2)")
        if self.s.shape[0] != self.freqs.shape[0]:
            raise ValueError("frequency / S-parameter length mismatch")

    @property
    def n(self) -> int:
        return self.freqs.shape[0]

    # ---- individual parameters ----------------------------------------------
    @property
    def s11(self) -> np.ndarray:
        return self.s[:, 0, 0]

    @property
    def s12(self) -> np.ndarray:
        return self.s[:, 0, 1]

    @property
    def s21(self) -> np.ndarray:
        return self.s[:, 1, 0]

    @property
    def s22(self) -> np.ndarray:
        return self.s[:, 1, 1]

    # ---- derived magnitude / phase quantities --------------------------------
    @staticmethod
    def db(values: np.ndarray) -> np.ndarray:
        """20·log10|x| with a floor so zeros don't blow up the plot."""
        mag = np.abs(np.asarray(values, dtype=complex))
        return 20.0 * np.log10(np.maximum(mag, 1e-12))

    def s21_db(self) -> np.ndarray:
        return self.db(self.s21)

    def s11_db(self) -> np.ndarray:
        return self.db(self.s11)

    def s22_db(self) -> np.ndarray:
        return self.db(self.s22)

    def s12_db(self) -> np.ndarray:
        return self.db(self.s12)

    @staticmethod
    def _vswr(reflection: np.ndarray) -> np.ndarray:
        g = np.clip(np.abs(reflection), 0.0, 0.999999)
        return (1.0 + g) / (1.0 - g)

    def vswr_in(self) -> np.ndarray:
        return self._vswr(self.s11)

    def vswr_out(self) -> np.ndarray:
        return self._vswr(self.s22)

    def s21_phase_deg(self, unwrap: bool = True) -> np.ndarray:
        ph = np.angle(self.s21)
        if unwrap:
            ph = np.unwrap(ph)
        return np.degrees(ph)

    def group_delay(self) -> np.ndarray:
        """S21 group delay (s) = -dφ/dω, by finite differences."""
        if self.n < 2:
            return np.zeros(self.n)
        phase = np.unwrap(np.angle(self.s21))
        omega = 2.0 * np.pi * self.freqs
        gd = -np.gradient(phase, omega)
        return gd

    # ---- ABCD (chain) conversion --------------------------------------------
    def to_abcd(self) -> np.ndarray:
        """Return ABCD parameters, shape (F, 2, 2)."""
        z0 = self.z0
        s11, s12, s21, s22 = self.s11, self.s12, self.s21, self.s22
        s21 = np.where(np.abs(s21) < 1e-15, 1e-15, s21)
        abcd = np.empty((self.n, 2, 2), dtype=complex)
        abcd[:, 0, 0] = ((1 + s11) * (1 - s22) + s12 * s21) / (2 * s21)          # A
        abcd[:, 0, 1] = z0 * ((1 + s11) * (1 + s22) - s12 * s21) / (2 * s21)     # B
        abcd[:, 1, 0] = (1.0 / z0) * ((1 - s11) * (1 - s22) - s12 * s21) / (2 * s21)  # C
        abcd[:, 1, 1] = ((1 - s11) * (1 + s22) + s12 * s21) / (2 * s21)          # D
        return abcd

    @classmethod
    def from_abcd(cls, freqs: np.ndarray, abcd: np.ndarray, z0: float = 50.0) -> "SParams":
        """Build S-parameters from ABCD parameters of a two-port."""
        a = abcd[:, 0, 0]
        b = abcd[:, 0, 1]
        c = abcd[:, 1, 0]
        d = abcd[:, 1, 1]
        denom = a + b / z0 + c * z0 + d
        denom = np.where(np.abs(denom) < 1e-30, 1e-30, denom)
        s = np.empty((freqs.shape[0], 2, 2), dtype=complex)
        s[:, 0, 0] = (a + b / z0 - c * z0 - d) / denom          # S11
        s[:, 0, 1] = 2.0 * (a * d - b * c) / denom              # S12
        s[:, 1, 0] = 2.0 / denom                                # S21
        s[:, 1, 1] = (-a + b / z0 - c * z0 + d) / denom         # S22
        return cls(freqs=np.asarray(freqs, dtype=float), s=s, z0=z0)

    # ---- combination ---------------------------------------------------------
    def cascade(self, other: "SParams") -> "SParams":
        """Cascade ``self`` then ``other`` (output of self feeds other's input).

        ``other`` is resampled onto ``self``'s frequency grid if needed.
        """
        if other.n != self.n or not np.allclose(other.freqs, self.freqs):
            other = other.interpolated(self.freqs)
        abcd = np.matmul(self.to_abcd(), other.to_abcd())
        return SParams.from_abcd(self.freqs, abcd, self.z0)

    # ---- (de)serialization ---------------------------------------------------
    def to_dict(self) -> dict:
        """Compact JSON-friendly form (split complex into real/imag lists)."""
        flat = self.s.reshape(self.n, 4)
        return {
            "z0": self.z0,
            "freqs": self.freqs.tolist(),
            "s_re": flat.real.tolist(),
            "s_im": flat.imag.tolist(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SParams":
        freqs = np.asarray(d["freqs"], dtype=float)
        re = np.asarray(d["s_re"], dtype=float)
        im = np.asarray(d["s_im"], dtype=float)
        s = (re + 1j * im).reshape(freqs.shape[0], 2, 2)
        return cls(freqs=freqs, s=s, z0=float(d.get("z0", 50.0)))

    def interpolated(self, new_freqs: np.ndarray) -> "SParams":
        """Linear interpolation of each S-parameter onto ``new_freqs``.

        Outside the measured band the nearest endpoint value is held (this keeps
        cascades well-behaved when a measured part is narrower than the sweep).
        """
        new_freqs = np.asarray(new_freqs, dtype=float)
        if self.n == 1:
            s = np.repeat(self.s, new_freqs.shape[0], axis=0)
            return SParams(freqs=new_freqs, s=s, z0=self.z0)
        out = np.empty((new_freqs.shape[0], 2, 2), dtype=complex)
        f = self.freqs
        for i in range(2):
            for j in range(2):
                vals = self.s[:, i, j]
                out[:, i, j] = (
                    np.interp(new_freqs, f, vals.real)
                    + 1j * np.interp(new_freqs, f, vals.imag)
                )
        return SParams(freqs=new_freqs, s=out, z0=self.z0)


# ---------------------------------------------------------------------------
# Element / canonical two-port builders
# ---------------------------------------------------------------------------
def identity_abcd(n: int) -> np.ndarray:
    """A length-``n`` stack of identity ABCD matrices (a perfect thru)."""
    abcd = np.zeros((n, 2, 2), dtype=complex)
    abcd[:, 0, 0] = 1.0
    abcd[:, 1, 1] = 1.0
    return abcd


def series_abcd(z: np.ndarray) -> np.ndarray:
    """ABCD of a series impedance ``z`` (shape (F,))."""
    n = z.shape[0]
    abcd = identity_abcd(n)
    abcd[:, 0, 1] = z
    return abcd


def shunt_abcd(y: np.ndarray) -> np.ndarray:
    """ABCD of a shunt admittance ``y`` (shape (F,))."""
    n = y.shape[0]
    abcd = identity_abcd(n)
    abcd[:, 1, 0] = y
    return abcd


def flat_gain(freqs: np.ndarray, gain_db: float, z0: float = 50.0,
              reciprocal: bool = True) -> SParams:
    """An ideal, perfectly matched flat two-port with the given |S21|.

    Used to represent ordinary gain/loss stages (amplifiers, pads) in a
    frequency cascade: S11 = S22 = 0, |S21| = 10^(gain/20). When
    ``reciprocal`` (passives) S12 = S21; otherwise S12 = 0 (unilateral, like an
    amplifier or isolator).
    """
    freqs = np.asarray(freqs, dtype=float)
    n = freqs.shape[0]
    a = 10.0 ** (gain_db / 20.0)
    s = np.zeros((n, 2, 2), dtype=complex)
    s[:, 1, 0] = a
    s[:, 0, 1] = a if reciprocal else 0.0
    return SParams(freqs=freqs, s=s, z0=z0)


def cascade_all(networks: List[SParams], freqs: np.ndarray,
                z0: float = 50.0) -> SParams:
    """Cascade a list of two-ports on a common frequency grid."""
    freqs = np.asarray(freqs, dtype=float)
    abcd = identity_abcd(freqs.shape[0])
    for net in networks:
        if net.n != freqs.shape[0] or not np.allclose(net.freqs, freqs):
            net = net.interpolated(freqs)
        abcd = np.matmul(abcd, net.to_abcd())
    return SParams.from_abcd(freqs, abcd, z0)


# ---------------------------------------------------------------------------
# Small analysis helpers used by the GUI read-outs
# ---------------------------------------------------------------------------
def insertion_loss_db_at(sp: SParams, freq_hz: float) -> float:
    """|S21| in dB interpolated at a single frequency."""
    if sp.n == 0:
        return 0.0
    return float(np.interp(freq_hz, sp.freqs, sp.s21_db()))


def passband_edges_db(sp: SParams, ref_db: Optional[float] = None,
                      drop_db: float = 3.0):
    """Find the lower/upper frequencies where |S21| falls ``drop_db`` below the
    passband peak (a quick −3 dB bandwidth estimate).

    Returns ``(f_lo, f_hi, bw)`` in Hz, with NaNs where no crossing is found.
    """
    if sp.n < 2:
        return math.nan, math.nan, math.nan
    s21 = sp.s21_db()
    peak = float(np.max(s21)) if ref_db is None else ref_db
    threshold = peak - drop_db
    above = s21 >= threshold
    if not np.any(above):
        return math.nan, math.nan, math.nan
    idx = np.where(above)[0]
    lo_i, hi_i = idx[0], idx[-1]

    def _cross(i_inside: int, i_outside: int) -> float:
        if i_outside < 0 or i_outside >= sp.n:
            return float(sp.freqs[i_inside])
        f0, f1 = sp.freqs[i_outside], sp.freqs[i_inside]
        y0, y1 = s21[i_outside], s21[i_inside]
        if y1 == y0:
            return float(f1)
        t = (threshold - y0) / (y1 - y0)
        return float(f0 + t * (f1 - f0))

    f_lo = _cross(lo_i, lo_i - 1)
    f_hi = _cross(hi_i, hi_i + 1)
    return f_lo, f_hi, f_hi - f_lo
