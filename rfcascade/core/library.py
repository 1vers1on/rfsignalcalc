"""A built-in library of representative RF parts, grouped by category.

Numbers are typical / illustrative values inspired by real catalogue parts so
that the analyzer has useful building blocks out of the box. Edit freely.
"""

from __future__ import annotations

import math
from typing import Dict, List

from .components import Component, ComponentKind


def _c(name, kind, gain, nf, oip3, p1db, **kw) -> Component:
    return Component(
        name=name, kind=kind, gain_db=gain, nf_db=nf,
        oip3_dbm=oip3, op1db_dbm=p1db, **kw,
    )


LIBRARY: Dict[str, List[Component]] = {
    "Low-Noise Amplifiers": [
        _c("LNA · 0.5 dB NF", ComponentKind.LNA, 22.0, 0.5, 32.0, 18.0),
        _c("LNA · 0.9 dB NF", ComponentKind.LNA, 18.0, 0.9, 30.0, 15.0),
        _c("LNA · 1.5 dB NF", ComponentKind.LNA, 15.0, 1.5, 28.0, 14.0),
        _c("Wideband LNA", ComponentKind.LNA, 20.0, 2.0, 36.0, 20.0),
    ],
    "Gain / Driver Amps": [
        _c("Gain Block 15 dB", ComponentKind.GAIN_BLOCK, 15.0, 4.0, 33.0, 18.0),
        _c("Driver Amp 20 dB", ComponentKind.AMPLIFIER, 20.0, 5.0, 38.0, 24.0),
        _c("High-Linearity Amp", ComponentKind.AMPLIFIER, 16.0, 6.0, 45.0, 30.0),
        _c("Power Amp 30 dB", ComponentKind.AMPLIFIER, 30.0, 7.0, 48.0, 36.0),
    ],
    "Mixers": [
        _c("Passive Mixer", ComponentKind.MIXER, -7.0, 7.0, 25.0, 12.0),
        _c("Active Mixer", ComponentKind.MIXER, 6.0, 9.0, 22.0, 8.0),
        _c("High-Linearity Mixer", ComponentKind.MIXER, -6.0, 6.5, 35.0, 18.0),
    ],
    "Filters": [
        _c("Cavity BPF", ComponentKind.FILTER, -1.0, None, math.inf, math.inf),
        _c("SAW Filter", ComponentKind.FILTER, -3.0, None, math.inf, math.inf),
        _c("LC LPF", ComponentKind.FILTER, -0.8, None, math.inf, math.inf),
        _c("Ceramic BPF", ComponentKind.FILTER, -2.5, None, math.inf, math.inf),
    ],
    "Attenuators / Pads": [
        _c("Pad 3 dB", ComponentKind.ATTENUATOR, -3.0, None, math.inf, math.inf),
        _c("Pad 6 dB", ComponentKind.ATTENUATOR, -6.0, None, math.inf, math.inf),
        _c("Pad 10 dB", ComponentKind.ATTENUATOR, -10.0, None, math.inf, math.inf),
        _c("Digital Step Atten", ComponentKind.ATTENUATOR, -15.0, None, 55.0, 30.0),
    ],
    "Passives / Interconnect": [
        _c("Coax 1 m", ComponentKind.CABLE, -1.5, None, math.inf, math.inf),
        _c("RF Switch", ComponentKind.SWITCH, -1.0, None, 50.0, 30.0),
        _c("Isolator", ComponentKind.ISOLATOR, -0.5, None, math.inf, math.inf),
        _c("Directional Coupler", ComponentKind.COUPLER, -1.0, None, math.inf, math.inf),
    ],
    "Data Converters": [
        _c("ADC 14-bit", ComponentKind.ADC, 0.0, 25.0, 40.0, 10.0),
        _c("ADC 16-bit", ComponentKind.ADC, 0.0, 22.0, 45.0, 8.0),
    ],
}


def default_chain() -> List[Component]:
    """A sensible example receiver front-end to populate a new project."""
    return [
        Component.make(ComponentKind.FILTER, "Preselect BPF", gain_db=-1.5, nf_db=1.5),
        Component.make(ComponentKind.LNA, "LNA", gain_db=20.0, nf_db=0.9, oip3_dbm=30.0, op1db_dbm=15.0),
        Component.make(ComponentKind.FILTER, "Image Filter", gain_db=-2.0, nf_db=2.0),
        Component.make(ComponentKind.MIXER, "Down-Mixer", gain_db=-7.0, nf_db=7.0, oip3_dbm=25.0, op1db_dbm=12.0),
        Component.make(ComponentKind.FILTER, "IF Filter", gain_db=-3.0, nf_db=3.0),
        Component.make(ComponentKind.GAIN_BLOCK, "IF Amp", gain_db=20.0, nf_db=4.0, oip3_dbm=38.0, op1db_dbm=22.0),
        Component.make(ComponentKind.ATTENUATOR, "Level Set", gain_db=-6.0),
    ]


def all_parts() -> List[Component]:
    parts: List[Component] = []
    for group in LIBRARY.values():
        parts.extend(group)
    return parts
