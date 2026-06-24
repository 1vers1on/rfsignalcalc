"""The cascade analysis engine.

Given a `SignalSource` and an ordered list of `Component`s, compute per-stage
cumulative system performance:

* Cascaded gain
* Cascaded noise figure (Friis)
* Cascaded input/output IP3 and IP2 (coherent worst-case or power addition)
* Cascaded input/output 1 dB compression point
* Signal power, noise floor and SNR at every node
* System metrics: MDS, two-tone SFDR (IM3 & IM2), compression / IP3 headroom

The distortion-cascade formulas are derived in the module docstring of
``tests/test_cascade.py``; both the coherent (voltage-addition, worst case) and
non-coherent (power-addition) results are supported.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from . import units
from .components import Component, SignalSource


class IMDMode(str, Enum):
    """How intermodulation products from different stages combine."""

    COHERENT = "Coherent (worst case)"   # voltage addition
    POWER = "Power (non-coherent)"       # power addition


@dataclass
class StageResult:
    """Per-stage values plus the cumulative state at this stage's output."""

    index: int
    name: str
    enabled: bool

    # echoed per-stage inputs
    gain_db: float = 0.0
    nf_db: float = 0.0
    oip3_dbm: float = math.inf
    op1db_dbm: float = math.inf

    # cumulative through-this-stage values
    cum_gain_db: float = 0.0
    cum_nf_db: float = 0.0
    cum_iip3_dbm: float = math.inf
    cum_oip3_dbm: float = math.inf
    cum_iip2_dbm: float = math.inf
    cum_oip2_dbm: float = math.inf
    cum_ip1db_in_dbm: float = math.inf
    cum_op1db_dbm: float = math.inf

    # node (this stage output) levels
    node_power_dbm: float = -math.inf
    node_noise_dbm: float = -math.inf
    node_snr_db: float = math.inf
    p1db_headroom_db: float = math.inf   # OP1dB(cum) - node power
    ip3_headroom_db: float = math.inf    # OIP3(cum) - node power


@dataclass
class SystemSummary:
    """End-to-end system metrics."""

    n_stages: int = 0
    total_gain_db: float = 0.0
    total_nf_db: float = 0.0
    noise_temp_k: float = 0.0

    iip3_dbm: float = math.inf
    oip3_dbm: float = math.inf
    iip2_dbm: float = math.inf
    oip2_dbm: float = math.inf
    ip1db_in_dbm: float = math.inf
    op1db_dbm: float = math.inf

    input_power_dbm: float = -math.inf
    output_power_dbm: float = -math.inf
    input_noise_dbm: float = -math.inf
    output_noise_dbm: float = -math.inf
    input_snr_db: float = math.inf
    output_snr_db: float = math.inf

    mds_dbm: float = -math.inf          # minimum detectable signal (SNR=0)
    sensitivity_dbm: float = -math.inf  # MDS + required SNR
    sfdr_db: float = math.inf           # two-tone IM3 SFDR
    sfdr2_db: float = math.inf          # two-tone IM2 SFDR
    dynamic_range_db: float = math.inf  # output P1dB compression DR
    link_margin_db: float = math.inf    # output SNR - required SNR


@dataclass
class CascadeResult:
    stages: List[StageResult] = field(default_factory=list)
    summary: SystemSummary = field(default_factory=SystemSummary)
    source: Optional[SignalSource] = None
    imd_mode: IMDMode = IMDMode.COHERENT

    @property
    def n_active(self) -> int:
        return len(self.stages)


def _inv_safe(x: float) -> float:
    return 0.0 if math.isinf(x) else 1.0 / x


def analyze(
    source: SignalSource,
    components: List[Component],
    imd_mode: IMDMode = IMDMode.COHERENT,
) -> CascadeResult:
    """Run the full cascade analysis.

    Disabled components are skipped. The returned `StageResult` list only
    contains enabled stages (with their original 1-based position preserved in
    ``index``).
    """

    result = CascadeResult(source=source, imd_mode=imd_mode)

    input_noise_dbm = units.thermal_noise_dbm(source.bandwidth_hz, source.temperature_k)
    input_power_dbm = source.power_dbm

    # Cumulative accumulators (all in linear power ratios / mW).
    cum_gain_lin = 1.0          # gain *into* the current stage's input
    friis_terms = 0.0           # Σ (F_i - 1) / G_before_i
    s_iip3 = 0.0                # Σ term for IP3 cascade
    s_iip2 = 0.0                # Σ term for IP2 cascade
    s_ip1db = 0.0              # Σ term for P1dB cascade

    coherent = imd_mode == IMDMode.COHERENT

    for pos, comp in enumerate(components, start=1):
        if not comp.enabled:
            continue

        g_lin = units.db_to_lin(comp.gain_db)
        f_lin = units.nf_to_factor(comp.effective_nf_db())
        cum_before = cum_gain_lin

        # --- noise (Friis) ----------------------------------------------------
        friis_terms += (f_lin - 1.0) / cum_before
        f_total = 1.0 + friis_terms

        # --- gain -------------------------------------------------------------
        cum_gain_lin *= g_lin
        cum_gain_db = units.lin_to_db(cum_gain_lin)

        # --- IP3 (3rd order) --------------------------------------------------
        iip3_lin = units.dbm_to_mw(comp.iip3_dbm)  # 0 contribution if inf -> term 0
        term3 = cum_before * _inv_safe(iip3_lin)
        s_iip3 += term3 * term3 if not coherent else term3

        # --- IP2 (2nd order) --------------------------------------------------
        iip2_lin = units.dbm_to_mw(comp.iip2_dbm)
        base2 = cum_before * _inv_safe(iip2_lin)
        s_iip2 += base2 if not coherent else math.sqrt(base2)

        # --- P1dB (input referred, IP3-like coherent approximation) ----------
        ip1_in_lin = units.dbm_to_mw(comp.ip1db_in_dbm)
        s_ip1db += cum_before * _inv_safe(ip1_in_lin)

        # --- cumulative intercepts -------------------------------------------
        if coherent:
            cum_iip3_lin = 1.0 / s_iip3 if s_iip3 > 0 else math.inf
            cum_iip2_lin = 1.0 / (s_iip2 * s_iip2) if s_iip2 > 0 else math.inf
        else:
            cum_iip3_lin = 1.0 / math.sqrt(s_iip3) if s_iip3 > 0 else math.inf
            cum_iip2_lin = 1.0 / s_iip2 if s_iip2 > 0 else math.inf
        cum_ip1_in_lin = 1.0 / s_ip1db if s_ip1db > 0 else math.inf

        cum_iip3_dbm = units.mw_to_dbm(cum_iip3_lin) if math.isfinite(cum_iip3_lin) else math.inf
        cum_iip2_dbm = units.mw_to_dbm(cum_iip2_lin) if math.isfinite(cum_iip2_lin) else math.inf
        cum_ip1_in_dbm = units.mw_to_dbm(cum_ip1_in_lin) if math.isfinite(cum_ip1_in_lin) else math.inf
        cum_oip3_dbm = cum_iip3_dbm + cum_gain_db if math.isfinite(cum_iip3_dbm) else math.inf
        cum_oip2_dbm = cum_iip2_dbm + cum_gain_db if math.isfinite(cum_iip2_dbm) else math.inf
        cum_op1_dbm = cum_ip1_in_dbm + cum_gain_db if math.isfinite(cum_ip1_in_dbm) else math.inf

        nf_total_db = units.factor_to_nf(f_total)

        # --- node levels ------------------------------------------------------
        node_power = input_power_dbm + cum_gain_db
        node_noise = input_noise_dbm + nf_total_db + cum_gain_db
        node_snr = node_power - node_noise

        sr = StageResult(
            index=pos,
            name=comp.name,
            enabled=True,
            gain_db=comp.gain_db,
            nf_db=comp.effective_nf_db(),
            oip3_dbm=comp.oip3_dbm,
            op1db_dbm=comp.op1db_dbm,
            cum_gain_db=cum_gain_db,
            cum_nf_db=nf_total_db,
            cum_iip3_dbm=cum_iip3_dbm,
            cum_oip3_dbm=cum_oip3_dbm,
            cum_iip2_dbm=cum_iip2_dbm,
            cum_oip2_dbm=cum_oip2_dbm,
            cum_ip1db_in_dbm=cum_ip1_in_dbm,
            cum_op1db_dbm=cum_op1_dbm,
            node_power_dbm=node_power,
            node_noise_dbm=node_noise,
            node_snr_db=node_snr,
            p1db_headroom_db=(cum_op1_dbm - node_power) if math.isfinite(cum_op1_dbm) else math.inf,
            ip3_headroom_db=(cum_oip3_dbm - node_power) if math.isfinite(cum_oip3_dbm) else math.inf,
        )
        result.stages.append(sr)

    _finalize_summary(result, source, input_power_dbm, input_noise_dbm)
    return result


def frequency_response(
    source: SignalSource,
    components: List[Component],
    freqs,
):
    """Cascade every enabled stage's two-port over a frequency grid.

    Returns an :class:`~rfcascade.core.sparams.SParams` for the whole chain.
    Stages with a lumped circuit or measured Touchstone data contribute their
    real frequency shape; ordinary gain/loss stages contribute a flat, matched
    block. The reference impedance is taken from the first stage that defines
    one (default 50 Ω).
    """
    from . import sparams as _sp

    enabled = [c for c in components if c.enabled]
    z0 = next((c.z0_ohm for c in enabled if c.has_network), 50.0)
    nets = [c.network(freqs) for c in enabled]
    return _sp.cascade_all(nets, freqs, z0)


def _finalize_summary(
    result: CascadeResult,
    source: SignalSource,
    input_power_dbm: float,
    input_noise_dbm: float,
) -> None:
    s = SystemSummary()
    s.input_power_dbm = input_power_dbm
    s.input_noise_dbm = input_noise_dbm
    s.input_snr_db = input_power_dbm - input_noise_dbm

    if not result.stages:
        # Pass-through: output == input.
        s.output_power_dbm = input_power_dbm
        s.output_noise_dbm = input_noise_dbm
        s.output_snr_db = s.input_snr_db
        s.mds_dbm = input_noise_dbm
        s.sensitivity_dbm = input_noise_dbm + source.required_snr_db
        s.link_margin_db = s.output_snr_db - source.required_snr_db
        result.summary = s
        return

    last = result.stages[-1]
    s.n_stages = len(result.stages)
    s.total_gain_db = last.cum_gain_db
    s.total_nf_db = last.cum_nf_db
    s.noise_temp_k = units.temperature_from_nf(last.cum_nf_db, source.temperature_k)

    s.iip3_dbm = last.cum_iip3_dbm
    s.oip3_dbm = last.cum_oip3_dbm
    s.iip2_dbm = last.cum_iip2_dbm
    s.oip2_dbm = last.cum_oip2_dbm
    s.ip1db_in_dbm = last.cum_ip1db_in_dbm
    s.op1db_dbm = last.cum_op1db_dbm

    s.output_power_dbm = last.node_power_dbm
    s.output_noise_dbm = last.node_noise_dbm
    s.output_snr_db = last.node_snr_db

    # MDS / sensitivity referred to the system input.
    s.mds_dbm = input_noise_dbm + s.total_nf_db          # SNR = 0 dB
    s.sensitivity_dbm = s.mds_dbm + source.required_snr_db
    s.link_margin_db = s.output_snr_db - source.required_snr_db

    # Two-tone SFDR relative to the in-band noise floor.
    if math.isfinite(s.iip3_dbm):
        s.sfdr_db = (2.0 / 3.0) * (s.iip3_dbm - s.mds_dbm)
    if math.isfinite(s.iip2_dbm):
        s.sfdr2_db = 0.5 * (s.iip2_dbm - s.mds_dbm)

    # Compression-limited dynamic range (output P1dB above output noise floor).
    if math.isfinite(s.op1db_dbm):
        s.dynamic_range_db = s.op1db_dbm - s.output_noise_dbm

    result.summary = s
