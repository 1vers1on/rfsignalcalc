"""Project (de)serialization: save / load chains to JSON, export to CSV."""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, field
from typing import List, Optional

from .components import Component, SignalSource
from .cascade import CascadeResult, IMDMode, analyze

PROJECT_VERSION = 1


@dataclass
class Project:
    source: SignalSource = field(default_factory=SignalSource)
    components: List[Component] = field(default_factory=list)
    imd_mode: IMDMode = IMDMode.COHERENT
    name: str = "Untitled"

    def analyze(self) -> CascadeResult:
        return analyze(self.source, self.components, self.imd_mode)

    # ---- JSON ----------------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "version": PROJECT_VERSION,
            "name": self.name,
            "imd_mode": self.imd_mode.value,
            "source": self.source.to_dict(),
            "components": [c.to_dict() for c in self.components],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Project":
        source = SignalSource.from_dict(d.get("source", {}))
        components = [Component.from_dict(c) for c in d.get("components", [])]
        mode = IMDMode.COHERENT
        for m in IMDMode:
            if m.value == d.get("imd_mode"):
                mode = m
                break
        return cls(source=source, components=components, imd_mode=mode,
                   name=d.get("name", "Untitled"))

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)

    @classmethod
    def load(cls, path: str) -> "Project":
        with open(path, "r", encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))


def _fmt(v: float) -> str:
    if v is None or (isinstance(v, float) and math.isinf(v)):
        return "" if v is None or v > 0 else "-inf"
    return f"{v:.3f}"


def export_results_csv(path: str, result: CascadeResult) -> None:
    """Write the per-stage cascade table to a CSV file."""
    cols = [
        ("Stage", lambda s: s.index),
        ("Name", lambda s: s.name),
        ("Gain (dB)", lambda s: _fmt(s.gain_db)),
        ("NF (dB)", lambda s: _fmt(s.nf_db)),
        ("OIP3 (dBm)", lambda s: _fmt(s.oip3_dbm)),
        ("Cum Gain (dB)", lambda s: _fmt(s.cum_gain_db)),
        ("Cum NF (dB)", lambda s: _fmt(s.cum_nf_db)),
        ("Cum IIP3 (dBm)", lambda s: _fmt(s.cum_iip3_dbm)),
        ("Cum OIP3 (dBm)", lambda s: _fmt(s.cum_oip3_dbm)),
        ("Cum OP1dB (dBm)", lambda s: _fmt(s.cum_op1db_dbm)),
        ("Node Pwr (dBm)", lambda s: _fmt(s.node_power_dbm)),
        ("Node Noise (dBm)", lambda s: _fmt(s.node_noise_dbm)),
        ("Node SNR (dB)", lambda s: _fmt(s.node_snr_db)),
        ("P1dB Hdrm (dB)", lambda s: _fmt(s.p1db_headroom_db)),
    ]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([c[0] for c in cols])
        for st in result.stages:
            w.writerow([fn(st) for _, fn in cols])
