"""Core RF cascade calculation engine (no GUI dependencies)."""

from __future__ import annotations

from .components import Component, ComponentKind, SignalSource, KIND_DEFAULTS
from .cascade import (
    CascadeResult,
    StageResult,
    SystemSummary,
    analyze,
    IMDMode,
)
from . import units
from . import library
from . import project
from . import sweep
from . import montecarlo

__all__ = [
    "Component",
    "ComponentKind",
    "SignalSource",
    "KIND_DEFAULTS",
    "CascadeResult",
    "StageResult",
    "SystemSummary",
    "IMDMode",
    "analyze",
    "units",
    "library",
    "project",
    "sweep",
    "montecarlo",
]
