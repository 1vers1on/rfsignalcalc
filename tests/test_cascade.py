"""Engine tests with hand-checked reference values.

Distortion cascade derivation (input-referred, linear power, per stage i with
linear gain g_i, input intercept IIPn_i, and c_i = product of gains *before*
stage i so c_1 = 1):

    IM_n product referred to the system output from stage i is proportional to
    P^n * c_i^(n-1) * G_total / IIPn_i^(n-1).

Equating the summed IM output to the fundamental output P*G_total at the input
intercept gives, for third order:

    coherent (voltage add):   1/IIP3_tot = Σ c_i / IIP3_i
    power add:                1/IIP3_tot = sqrt( Σ (c_i / IIP3_i)^2 )

and for second order:

    coherent:                 1/sqrt(IIP2_tot) = Σ sqrt(c_i / IIP2_i)
    power:                    1/IIP2_tot       = Σ c_i / IIP2_i

All intercepts are in linear power (mW); convert to dBm at the end.
"""

from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rfcascade.core import units
from rfcascade.core.components import Component, ComponentKind, SignalSource
from rfcascade.core.cascade import analyze, IMDMode

TOL = 1e-6


def approx(a: float, b: float, tol: float = 1e-4) -> bool:
    return abs(a - b) <= tol


# ---------------------------------------------------------------------------
def test_unit_conversions():
    assert approx(units.db_to_lin(10.0), 10.0)
    assert approx(units.db_to_lin(0.0), 1.0)
    assert approx(units.lin_to_db(100.0), 20.0)
    assert approx(units.dbm_to_mw(0.0), 1.0)
    assert approx(units.mw_to_dbm(1.0), 0.0)
    assert math.isinf(units.lin_to_db(0.0)) and units.lin_to_db(0.0) < 0


def test_thermal_noise():
    # -174 dBm/Hz at 290 K, +60 dB for 1 MHz.
    n = units.thermal_noise_dbm(1e6, 290.0)
    assert approx(n, -113.975, 0.01)
    assert approx(units.noise_density_dbm_per_hz(290.0), -173.975, 0.01)


def test_nf_temperature_roundtrip():
    te = units.temperature_from_nf(3.0)
    assert approx(units.nf_from_temperature(te), 3.0)


def test_single_stage_passthrough():
    src = SignalSource(power_dbm=-30.0, bandwidth_hz=1e6)
    c = Component.make(ComponentKind.AMPLIFIER, gain_db=20.0, nf_db=5.0,
                       oip3_dbm=40.0, op1db_dbm=25.0)
    r = analyze(src, [c])
    s = r.summary
    assert approx(s.total_gain_db, 20.0)
    assert approx(s.total_nf_db, 5.0)
    assert approx(s.iip3_dbm, 20.0)          # OIP3 - gain
    assert approx(s.oip3_dbm, 40.0)
    assert approx(s.output_power_dbm, -10.0)  # -30 + 20


def test_friis_two_stage():
    src = SignalSource(power_dbm=-50.0, bandwidth_hz=1e6)
    c1 = Component(name="A", gain_db=10.0, nf_db=3.0, oip3_dbm=math.inf, op1db_dbm=math.inf)
    c2 = Component(name="B", gain_db=20.0, nf_db=10.0, oip3_dbm=math.inf, op1db_dbm=math.inf)
    r = analyze(src, [c1, c2])
    s = r.summary
    # F = 1.99526 + (10-1)/10 = 2.89526 -> 4.617 dB
    assert approx(s.total_nf_db, 4.6170, 1e-3)
    assert approx(s.total_gain_db, 30.0)


def test_friis_lna_dominates():
    """A high-gain low-NF first stage should set system NF close to its own."""
    src = SignalSource()
    lna = Component(name="LNA", gain_db=30.0, nf_db=1.0, oip3_dbm=math.inf, op1db_dbm=math.inf)
    amp = Component(name="AMP", gain_db=20.0, nf_db=15.0, oip3_dbm=math.inf, op1db_dbm=math.inf)
    s = analyze(src, [lna, amp]).summary
    # F = 1.2589 + (31.62-1)/1000 = 1.2895 -> 1.104 dB (second stage suppressed)
    assert approx(s.total_nf_db, 1.104, 1e-3)
    assert s.total_nf_db < 1.15


def test_passive_nf_equals_loss():
    src = SignalSource()
    pad = Component.make(ComponentKind.ATTENUATOR, gain_db=-10.0)  # nf auto = loss
    s = analyze(src, [pad]).summary
    assert approx(s.total_nf_db, 10.0)
    assert approx(s.total_gain_db, -10.0)


def test_ip3_cascade_coherent():
    src = SignalSource()
    c1 = Component(name="A", gain_db=10.0, nf_db=0.0, oip3_dbm=30.0, op1db_dbm=math.inf)
    c2 = Component(name="B", gain_db=20.0, nf_db=0.0, oip3_dbm=40.0, op1db_dbm=math.inf)
    # IIP3_1 = 20 dBm (100 mW), IIP3_2 = 20 dBm (100 mW), c2 = 10
    # s = 1/100 + 10/100 = 0.11 -> IIP3 = 9.0909 mW = 9.586 dBm
    s = analyze(src, [c1, c2], IMDMode.COHERENT).summary
    assert approx(s.iip3_dbm, 9.5861, 1e-3)
    assert approx(s.oip3_dbm, s.iip3_dbm + 30.0, 1e-3)


def test_ip3_cascade_power_addition():
    src = SignalSource()
    c1 = Component(name="A", gain_db=10.0, nf_db=0.0, oip3_dbm=30.0, op1db_dbm=math.inf)
    c2 = Component(name="B", gain_db=20.0, nf_db=0.0, oip3_dbm=40.0, op1db_dbm=math.inf)
    # power add: 1/IIP3 = sqrt((1/100)^2 + (10/100)^2) = sqrt(0.0001+0.01)=0.10050
    # IIP3 = 9.950 mW = 9.978 dBm  (slightly higher than coherent)
    s = analyze(src, [c1, c2], IMDMode.POWER).summary
    assert approx(s.iip3_dbm, 9.9785, 1e-3)
    assert s.iip3_dbm > 9.5861   # power addition is less pessimistic


def test_node_levels_and_snr():
    src = SignalSource(power_dbm=-40.0, bandwidth_hz=1e6, temperature_k=290.0)
    amp = Component(name="A", gain_db=20.0, nf_db=5.0, oip3_dbm=40.0, op1db_dbm=25.0)
    s = analyze(src, [amp]).summary
    nfloor_in = units.thermal_noise_dbm(1e6, 290.0)  # ~ -113.975
    assert approx(s.output_power_dbm, -20.0)         # -40 + 20
    assert approx(s.output_noise_dbm, nfloor_in + 5.0 + 20.0, 1e-3)
    # SNR = input SNR - NF
    assert approx(s.output_snr_db, (-40.0 - nfloor_in) - 5.0, 1e-3)


def test_mds_and_sfdr():
    src = SignalSource(power_dbm=-80.0, bandwidth_hz=1e6, required_snr_db=10.0)
    lna = Component(name="LNA", gain_db=20.0, nf_db=2.0, oip3_dbm=30.0, op1db_dbm=15.0)
    s = analyze(src, [lna]).summary
    nfloor_in = units.thermal_noise_dbm(1e6, 290.0)
    assert approx(s.mds_dbm, nfloor_in + 2.0, 1e-3)
    assert approx(s.sensitivity_dbm, s.mds_dbm + 10.0, 1e-3)
    # SFDR = 2/3 (IIP3 - MDS)
    assert approx(s.sfdr_db, (2.0 / 3.0) * (s.iip3_dbm - s.mds_dbm), 1e-3)


def test_disabled_stage_skipped():
    src = SignalSource()
    c1 = Component(name="A", gain_db=10.0, nf_db=3.0)
    c2 = Component(name="B", gain_db=10.0, nf_db=3.0, enabled=False)
    c3 = Component(name="C", gain_db=10.0, nf_db=3.0)
    r = analyze(src, [c1, c2, c3])
    assert r.n_active == 2
    assert approx(r.summary.total_gain_db, 20.0)


def test_serialization_roundtrip():
    c = Component.make(ComponentKind.FILTER, "BPF")
    d = c.to_dict()
    c2 = Component.from_dict(d)
    assert c2.kind == ComponentKind.FILTER
    assert math.isinf(c2.oip3_dbm)
    assert approx(c2.gain_db, c.gain_db)


def test_empty_chain():
    src = SignalSource(power_dbm=-10.0)
    r = analyze(src, [])
    assert r.summary.output_power_dbm == -10.0
    assert r.n_active == 0


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
