"""Component and signal-source data models for the cascade analyzer.

A `Component` is a generic two-port stage. Different `ComponentKind`s only
change the sensible defaults and the icon/colour shown in the GUI — the cascade
math treats every stage uniformly. Distortion parameters are stored *output
referred* (OIP3, OIP2, output P1dB) because that is how component datasheets
almost always specify them; input-referred values are derived from the gain.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


class ComponentKind(str, Enum):
    AMPLIFIER = "Amplifier"
    LNA = "LNA"
    ATTENUATOR = "Attenuator"
    FILTER = "Filter"
    MIXER = "Mixer"
    CABLE = "Cable"
    SWITCH = "Switch"
    GAIN_BLOCK = "Gain Block"
    COUPLER = "Coupler"
    ISOLATOR = "Isolator"
    ADC = "ADC"
    CUSTOM = "Custom"

    @property
    def is_passive(self) -> bool:
        return self in {
            ComponentKind.ATTENUATOR,
            ComponentKind.FILTER,
            ComponentKind.CABLE,
            ComponentKind.SWITCH,
            ComponentKind.COUPLER,
            ComponentKind.ISOLATOR,
        }


#: Default parameter templates per kind (gain_db, nf_db, oip3_dbm, op1db_dbm).
#: NF of None means "passive: NF == loss". inf means "ideal / not specified".
KIND_DEFAULTS = {
    ComponentKind.AMPLIFIER: dict(gain_db=20.0, nf_db=4.0, oip3_dbm=35.0, op1db_dbm=20.0),
    ComponentKind.LNA: dict(gain_db=18.0, nf_db=1.2, oip3_dbm=30.0, op1db_dbm=15.0),
    ComponentKind.ATTENUATOR: dict(gain_db=-10.0, nf_db=None, oip3_dbm=math.inf, op1db_dbm=math.inf),
    ComponentKind.FILTER: dict(gain_db=-2.0, nf_db=None, oip3_dbm=math.inf, op1db_dbm=math.inf),
    ComponentKind.MIXER: dict(gain_db=-7.0, nf_db=7.0, oip3_dbm=25.0, op1db_dbm=10.0),
    ComponentKind.CABLE: dict(gain_db=-1.5, nf_db=None, oip3_dbm=math.inf, op1db_dbm=math.inf),
    ComponentKind.SWITCH: dict(gain_db=-1.0, nf_db=None, oip3_dbm=50.0, op1db_dbm=30.0),
    ComponentKind.GAIN_BLOCK: dict(gain_db=15.0, nf_db=5.0, oip3_dbm=33.0, op1db_dbm=18.0),
    ComponentKind.COUPLER: dict(gain_db=-1.0, nf_db=None, oip3_dbm=math.inf, op1db_dbm=math.inf),
    ComponentKind.ISOLATOR: dict(gain_db=-0.5, nf_db=None, oip3_dbm=math.inf, op1db_dbm=math.inf),
    ComponentKind.ADC: dict(gain_db=0.0, nf_db=25.0, oip3_dbm=40.0, op1db_dbm=10.0),
    ComponentKind.CUSTOM: dict(gain_db=0.0, nf_db=0.0, oip3_dbm=math.inf, op1db_dbm=math.inf),
}


@dataclass
class Component:
    """A single two-port stage in the signal chain.

    Distortion intercepts are *output referred* and in dBm. Use ``math.inf`` to
    mark a parameter as ideal / unspecified (it then drops out of the cascade).
    """

    name: str = "Stage"
    kind: ComponentKind = ComponentKind.AMPLIFIER
    enabled: bool = True

    gain_db: float = 20.0
    nf_db: float = 4.0
    oip3_dbm: float = 35.0          # output third-order intercept
    oip2_dbm: float = math.inf      # output second-order intercept
    op1db_dbm: float = 20.0         # output 1 dB compression point

    frequency_hz: Optional[float] = None   # informational / for plotting
    notes: str = ""

    # Per-parameter 1-sigma tolerances (in dB / dBm) for Monte-Carlo analysis.
    tol_gain_db: float = 0.0
    tol_nf_db: float = 0.0
    tol_oip3_db: float = 0.0

    # ---- frequency-domain (S-parameter) model --------------------------------
    # A stage optionally carries a two-port S-parameter description used by the
    # frequency-response analysis. It is either synthesised from a lumped
    # ladder (`circuit`, a serialised LumpedCircuit) or sampled from a measured
    # Touchstone file (`sparams_data`, a serialised SParams). When neither is
    # present the stage behaves as an ideal, matched, flat gain/loss block.
    z0_ohm: float = 50.0
    circuit: Optional[dict] = None
    sparams_data: Optional[dict] = None

    uid: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    # ---- derived (input-referred) values -------------------------------------
    @property
    def iip3_dbm(self) -> float:
        return self.oip3_dbm - self.gain_db

    @property
    def iip2_dbm(self) -> float:
        return self.oip2_dbm - self.gain_db

    @property
    def ip1db_in_dbm(self) -> float:
        return self.op1db_dbm - self.gain_db

    @property
    def is_loss(self) -> bool:
        return self.gain_db < 0.0

    def effective_nf_db(self) -> float:
        """NF actually used in the cascade.

        For passive lossy stages NF equals the insertion loss (a standard
        approximation valid at the reference temperature).
        """
        if self.nf_db is None:
            return max(0.0, -self.gain_db)
        return self.nf_db

    # ---- frequency-domain network --------------------------------------------
    @property
    def has_network(self) -> bool:
        """True if this stage carries an explicit S-parameter description."""
        return self.circuit is not None or self.sparams_data is not None

    @property
    def network_kind(self) -> str:
        if self.circuit is not None:
            return "lumped"
        if self.sparams_data is not None:
            return "touchstone"
        return "flat"

    def get_circuit(self):
        """Return the lumped :class:`LumpedCircuit` for this stage, or None."""
        if self.circuit is None:
            return None
        from .circuit import LumpedCircuit
        return LumpedCircuit.from_dict(self.circuit)

    def get_sparams(self):
        """Return the stored sampled :class:`SParams`, or None."""
        if self.sparams_data is None:
            return None
        from .sparams import SParams
        return SParams.from_dict(self.sparams_data)

    def network(self, freqs):
        """Two-port :class:`SParams` of this stage on the ``freqs`` grid.

        Lumped circuits are synthesised exactly at every frequency; sampled
        (Touchstone) data is interpolated; everything else is modelled as an
        ideal, matched flat block at the stage's scalar gain.
        """
        from . import sparams as _sp
        if self.circuit is not None:
            return self.get_circuit().sparams(freqs)
        if self.sparams_data is not None:
            return self.get_sparams().interpolated(freqs)
        return _sp.flat_gain(freqs, self.gain_db, self.z0_ohm,
                             reciprocal=self.kind.is_passive)

    def set_circuit(self, circ, sync_gain_at_hz: Optional[float] = None) -> None:
        """Attach a lumped circuit; optionally sync scalar gain to its |S21|."""
        self.circuit = circ.to_dict()
        self.sparams_data = None
        self.z0_ohm = circ.z0
        if sync_gain_at_hz:
            self.gain_db = circ.insertion_gain_db(sync_gain_at_hz)

    def set_sparams(self, net, sync_gain_at_hz: Optional[float] = None) -> None:
        """Attach measured/sampled S-parameters (e.g. from Touchstone)."""
        self.sparams_data = net.to_dict()
        self.circuit = None
        self.z0_ohm = net.z0
        if sync_gain_at_hz:
            from .sparams import insertion_loss_db_at
            self.gain_db = insertion_loss_db_at(net, sync_gain_at_hz)

    def clear_network(self) -> None:
        self.circuit = None
        self.sparams_data = None

    # ---- (de)serialization ---------------------------------------------------
    def to_dict(self) -> dict:
        d = asdict(self)
        d["kind"] = self.kind.value
        # JSON cannot represent inf; encode as a sentinel string.
        for k in ("oip3_dbm", "oip2_dbm", "op1db_dbm", "gain_db", "nf_db"):
            v = d.get(k)
            if isinstance(v, float) and math.isinf(v):
                d[k] = "inf" if v > 0 else "-inf"
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Component":
        d = dict(d)
        if "kind" in d:
            try:
                d["kind"] = ComponentKind(d["kind"])
            except ValueError:
                d["kind"] = ComponentKind.CUSTOM
        for k in ("oip3_dbm", "oip2_dbm", "op1db_dbm", "gain_db", "nf_db"):
            if d.get(k) == "inf":
                d[k] = math.inf
            elif d.get(k) == "-inf":
                d[k] = -math.inf
        # Drop unknown keys to stay forward/backward compatible.
        valid = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        d = {k: v for k, v in d.items() if k in valid}
        return cls(**d)

    @classmethod
    def make(cls, kind: ComponentKind, name: Optional[str] = None, **overrides) -> "Component":
        """Create a component pre-filled with this kind's typical parameters."""
        defaults = dict(KIND_DEFAULTS.get(kind, KIND_DEFAULTS[ComponentKind.CUSTOM]))
        nf = defaults["nf_db"]
        comp = cls(
            name=name or kind.value,
            kind=kind,
            gain_db=defaults["gain_db"],
            nf_db=(-defaults["gain_db"] if nf is None else nf),
            oip3_dbm=defaults["oip3_dbm"],
            op1db_dbm=defaults["op1db_dbm"],
        )
        for k, v in overrides.items():
            setattr(comp, k, v)
        return comp

    def copy(self) -> "Component":
        c = Component.from_dict(self.to_dict())
        c.uid = uuid.uuid4().hex[:8]
        c.name = self.name
        return c


@dataclass
class SignalSource:
    """The input signal / generator feeding the chain."""

    power_dbm: float = -40.0
    frequency_hz: float = 1.0e9
    bandwidth_hz: float = 1.0e6
    temperature_k: float = 290.0
    required_snr_db: float = 10.0     # for demod / link-margin readouts
    label: str = "Source"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "SignalSource":
        valid = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in valid})
