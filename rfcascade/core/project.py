"""Project (de)serialization: save / load chains to JSON, export to CSV."""

from __future__ import annotations

import csv
import json
import math
import numbers
import os
import tempfile
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
        """Serialize the project to JSON, writing atomically.

        The project is fully serialized to a string *before* the destination is
        touched, then written through a temporary file that atomically replaces
        the target. A failure at any point — a serialization error or a write
        error — therefore never truncates or corrupts an existing file: the old
        contents survive intact and a half-written temp file is cleaned up.
        """
        text = json.dumps(self.to_dict(), indent=2, default=_json_default)

        path = os.fspath(path)
        directory = os.path.dirname(os.path.abspath(path))
        os.makedirs(directory, exist_ok=True)

        fd, tmp = tempfile.mkstemp(prefix=".rfc-", suffix=".tmp", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
        except BaseException:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise

    @classmethod
    def load(cls, path: str) -> "Project":
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        if not text.strip():
            raise ValueError("Project file is empty or corrupt.")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Not a valid project file: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError("Project file does not contain a project object.")
        return cls.from_dict(data)


def _json_default(o):
    """Fallback JSON encoder for stray non-native values (e.g. NumPy scalars).

    Keeps :meth:`Project.save` robust if a NumPy type or similar leaks into a
    field, instead of failing the whole save with a bare ``TypeError`` (which,
    before the save was made atomic, also wiped the target file).
    """
    if isinstance(o, numbers.Integral):
        return int(o)
    if isinstance(o, numbers.Real):
        v = float(o)
        if math.isinf(v):
            return "inf" if v > 0 else "-inf"
        return v
    if isinstance(o, complex):
        return [o.real, o.imag]
    if hasattr(o, "tolist"):          # NumPy arrays and the like
        return o.tolist()
    if hasattr(o, "item"):            # 0-d / scalar NumPy values
        return o.item()
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    raise TypeError(f"{type(o).__name__} is not JSON serializable")


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
