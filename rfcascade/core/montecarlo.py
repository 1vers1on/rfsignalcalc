"""Monte-Carlo tolerance analysis.

Each component's gain / NF / OIP3 is perturbed by a Gaussian with the per-part
1-sigma tolerances (``tol_gain_db``, ``tol_nf_db``, ``tol_oip3_db``). The chain
is re-analyzed over many trials to produce distributions of the key system
metrics.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np

from .components import SignalSource, Component
from .cascade import analyze, IMDMode


@dataclass
class MonteCarloResult:
    trials: int = 0
    samples: Dict[str, np.ndarray] = field(default_factory=dict)

    METRIC_LABELS = {
        "total_gain_db": "Total Gain (dB)",
        "total_nf_db": "Total NF (dB)",
        "iip3_dbm": "IIP3 (dBm)",
        "oip3_dbm": "OIP3 (dBm)",
        "output_snr_db": "Output SNR (dB)",
        "output_power_dbm": "Output Power (dBm)",
        "sfdr_db": "SFDR (dB)",
    }

    def stats(self, key: str) -> Dict[str, float]:
        data = self.samples.get(key)
        if data is None or len(data) == 0:
            return {}
        finite = data[np.isfinite(data)]
        if len(finite) == 0:
            return {}
        return {
            "mean": float(np.mean(finite)),
            "std": float(np.std(finite)),
            "min": float(np.min(finite)),
            "max": float(np.max(finite)),
            "p2.5": float(np.percentile(finite, 2.5)),
            "p50": float(np.percentile(finite, 50.0)),
            "p97.5": float(np.percentile(finite, 97.5)),
        }


def run_montecarlo(
    source: SignalSource,
    components: List[Component],
    trials: int = 2000,
    imd_mode: IMDMode = IMDMode.COHERENT,
    seed: int | None = None,
) -> MonteCarloResult:
    rng = np.random.default_rng(seed)
    keys = list(MonteCarloResult.METRIC_LABELS.keys())
    acc: Dict[str, List[float]] = {k: [] for k in keys}

    enabled = [c for c in components if c.enabled]
    n = len(enabled)
    if n == 0:
        return MonteCarloResult(trials=0, samples={k: np.array([]) for k in keys})

    g_tol = np.array([c.tol_gain_db for c in enabled])
    nf_tol = np.array([c.tol_nf_db for c in enabled])
    o3_tol = np.array([c.tol_oip3_db for c in enabled])

    base_gain = np.array([c.gain_db for c in enabled])
    base_nf = np.array([c.effective_nf_db() for c in enabled])
    base_o3 = np.array([c.oip3_dbm for c in enabled])

    for _ in range(trials):
        dg = rng.normal(0.0, 1.0, n) * g_tol
        dn = rng.normal(0.0, 1.0, n) * nf_tol
        do = rng.normal(0.0, 1.0, n) * o3_tol

        perturbed: List[Component] = []
        for i, c in enumerate(enabled):
            pc = c.copy()
            pc.enabled = True
            pc.gain_db = base_gain[i] + dg[i]
            pc.nf_db = max(0.0, base_nf[i] + dn[i])
            if math.isfinite(base_o3[i]):
                pc.oip3_dbm = base_o3[i] + do[i]
            perturbed.append(pc)

        s = analyze(source, perturbed, imd_mode).summary
        for k in keys:
            acc[k].append(getattr(s, k))

    samples = {k: np.array(v, dtype=float) for k, v in acc.items()}
    return MonteCarloResult(trials=trials, samples=samples)
