"""S-parameter / lumped-circuit / Touchstone engine tests.

Reference values are hand-derived from the canonical two-port relations:

* A bare **series impedance** Z between Z0 terminations has
  S21 = 2·Z0/(2·Z0 + Z),  S11 = Z/(2·Z0 + Z).
* A bare **shunt admittance** Y has S21 = 2/(2 + Y·Z0).
* A **doubly-terminated Butterworth** low-pass of order n has
  |S21|² = 1/(1 + (f/fc)^{2n}), so exactly −3.0103 dB at f = fc.
* A matched **π attenuator** has S21 = 1/10^{dB/20} and S11 = 0.
"""

from __future__ import annotations

import math
import os
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rfcascade.core import sparams as sp
from rfcascade.core import circuit as ckt
from rfcascade.core import touchstone as ts


def approx(a: float, b: float, tol: float = 1e-4) -> bool:
    return abs(a - b) <= tol


# ---------------------------------------------------------------------------
def test_series_impedance_two_port():
    f = np.array([1e9])
    z0 = 50.0
    z = np.array([50.0 + 0j])            # series 50 Ω resistor
    net = sp.SParams.from_abcd(f, sp.series_abcd(z), z0)
    # S21 = 2*50/(2*50+50) = 100/150 = 0.6667 -> -3.5218 dB
    assert approx(abs(net.s21[0]), 2.0 / 3.0)
    assert approx(net.s21_db()[0], -3.52183, 1e-3)
    # S11 = 50/150 = 0.3333
    assert approx(abs(net.s11[0]), 1.0 / 3.0)


def test_shunt_impedance_two_port():
    f = np.array([1e9])
    z0 = 50.0
    el = ckt.LumpedElement(arm=ckt.Arm.SHUNT, r_ohm=50.0)
    net = sp.SParams.from_abcd(f, el.abcd(f), z0)
    # S21 = 2/(2 + Z0/R) = 2/3
    assert approx(abs(net.s21[0]), 2.0 / 3.0)
    assert approx(abs(net.s11[0]), 1.0 / 3.0)


def test_s_abcd_roundtrip():
    f = np.array([0.5e9, 1e9, 2e9])
    # arbitrary-ish lossy two-port
    s = np.zeros((3, 2, 2), dtype=complex)
    s[:, 0, 0] = 0.2 + 0.1j
    s[:, 0, 1] = 0.05 - 0.02j
    s[:, 1, 0] = 0.7 - 0.3j
    s[:, 1, 1] = -0.1 + 0.05j
    net = sp.SParams(f, s, 50.0)
    back = sp.SParams.from_abcd(f, net.to_abcd(), 50.0)
    assert np.allclose(net.s, back.s, atol=1e-9)


def test_thru_cascade_identity():
    f = np.linspace(1e8, 3e9, 25)
    thru = sp.flat_gain(f, 0.0)
    casc = thru.cascade(thru)
    assert np.allclose(casc.s21, 1.0, atol=1e-9)
    assert np.allclose(np.abs(casc.s11), 0.0, atol=1e-9)


def test_flat_gain_levels():
    f = np.array([1e9])
    net = sp.flat_gain(f, 20.0)          # +20 dB
    assert approx(net.s21_db()[0], 20.0, 1e-6)
    assert approx(abs(net.s11[0]), 0.0, 1e-9)
    # cascaded with a −6 dB pad gives +14 dB
    pad = sp.flat_gain(f, -6.0)
    assert approx(net.cascade(pad).s21_db()[0], 14.0, 1e-6)


def test_butterworth_lpf_minus3db_at_cutoff():
    fc = 1e9
    for order in (1, 2, 3, 5):
        c = ckt.butterworth_lpf(order, fc)
        net = c.sparams(np.array([1e3, fc]))
        # passband (well below fc) ~ 0 dB, lossless
        assert net.s21_db()[0] > -0.01
        # exactly −3.0103 dB at the cutoff for a doubly-terminated Butterworth
        assert approx(net.s21_db()[1], -3.0103, 2e-2)
        # lossless: |S11|^2 + |S21|^2 = 1
        p = abs(net.s11[1]) ** 2 + abs(net.s21[1]) ** 2
        assert approx(p, 1.0, 1e-6)


def test_lpf_is_low_pass():
    c = ckt.butterworth_lpf(3, 1e9)
    net = c.sparams(np.array([1e6, 1e9, 1e10]))
    # monotonic roll-off: stopband well below passband
    assert net.s21_db()[0] > net.s21_db()[1] > net.s21_db()[2]
    assert net.s21_db()[2] < -40.0


def test_highpass_passes_high():
    c = ckt.butterworth_hpf(3, 1e9)
    net = c.sparams(np.array([1e7, 1e9, 1e11]))
    assert net.s21_db()[2] > net.s21_db()[1] > net.s21_db()[0]
    assert net.s21_db()[0] < -40.0


def test_bandpass_peaks_at_center():
    f0, bw = 1e9, 1e8
    c = ckt.butterworth_bpf(3, f0, bw)
    net = c.sparams(np.array([0.5e9, 1e9, 2e9]))
    assert net.s21_db()[1] > net.s21_db()[0]
    assert net.s21_db()[1] > net.s21_db()[2]
    assert net.s21_db()[1] > -0.5          # low loss at center


def test_pi_pad_matched_attenuation():
    f = np.array([1e9])
    for atten in (3.0, 6.0, 10.0, 20.0):
        c = ckt.pi_pad(atten)
        net = c.sparams(f)
        assert approx(net.s21_db()[0], -atten, 1e-3)
        assert abs(net.s11[0]) < 1e-6      # perfectly matched
        # reciprocal
        assert approx(abs(net.s12[0]), abs(net.s21[0]), 1e-9)


def test_reciprocity_of_passive_circuit():
    c = ckt.butterworth_bpf(5, 2.4e9, 2e8)
    net = c.sparams(np.linspace(2e9, 3e9, 50))
    assert np.allclose(net.s12, net.s21, atol=1e-9)


def test_interpolation():
    f = np.array([1e9, 2e9, 3e9])
    s = np.zeros((3, 2, 2), dtype=complex)
    s[:, 1, 0] = np.array([1.0, 0.5, 0.0])
    net = sp.SParams(f, s, 50.0)
    out = net.interpolated(np.array([1.5e9, 2.5e9]))
    assert approx(out.s21[0].real, 0.75)
    assert approx(out.s21[1].real, 0.25)


def test_group_delay_sign():
    # an ideal delay line: S21 = exp(-j*w*tau) -> constant positive group delay
    tau = 1e-9
    f = np.linspace(1e8, 1e9, 200)
    s = np.zeros((f.size, 2, 2), dtype=complex)
    s[:, 1, 0] = np.exp(-1j * 2 * np.pi * f * tau)
    s[:, 0, 1] = s[:, 1, 0]
    net = sp.SParams(f, s, 50.0)
    gd = net.group_delay()
    assert approx(float(np.median(gd)), tau, 1e-11)


def test_touchstone_roundtrip():
    f = np.linspace(1e9, 2e9, 11)
    c = ckt.butterworth_bpf(3, 1.5e9, 2e8)
    net = c.sparams(f)
    with tempfile.TemporaryDirectory() as d:
        for fmt in ("DB", "MA", "RI"):
            path = os.path.join(d, f"net_{fmt}.s2p")
            ts.write_touchstone(path, net, fmt=fmt)
            back = ts.read_touchstone(path)
            assert np.allclose(back.freqs, net.freqs, rtol=1e-6)
            assert np.allclose(back.s, net.s, atol=1e-4)


def test_touchstone_parse_inline():
    text = (
        "! demo\n"
        "# GHZ S DB R 50\n"
        "1.0  -0.5 0   -20 90   -20 90   -0.5 0\n"
        "2.0  -0.6 0   -18 90   -18 90   -0.6 0\n"
    )
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "demo.s2p")
        with open(path, "w") as fh:
            fh.write(text)
        net = ts.read_touchstone(path)
    assert net.n == 2
    assert approx(net.freqs[0], 1e9)
    assert approx(net.freqs[1], 2e9)
    assert approx(net.s21_db()[0], -20.0, 1e-3)


def test_serialization_roundtrip():
    c = ckt.butterworth_lpf(4, 1.2e9)
    d = c.to_dict()
    c2 = ckt.LumpedCircuit.from_dict(d)
    f = np.linspace(1e8, 3e9, 30)
    assert np.allclose(c.sparams(f).s, c2.sparams(f).s, atol=1e-9)


# ---------------------------------------------------------------------------
def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        fn()
        passed += 1
        print(f"  ok  {fn.__name__}")
    print(f"\n{passed}/{len(fns)} tests passed.")


if __name__ == "__main__":
    _run_all()
