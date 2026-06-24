"""Unit conversions and RF helper functions.

All "power ratio" conversions use the 10*log10 convention (dB of power).
Power is expressed in dBm or mW unless noted.
"""

from __future__ import annotations

import math

#: Boltzmann constant [J/K]
K_BOLTZMANN = 1.380649e-23
#: Standard reference noise temperature [K]
T0 = 290.0


def db_to_lin(db: float) -> float:
    """Convert a power ratio in dB to linear."""
    return 10.0 ** (db / 10.0)


def lin_to_db(lin: float) -> float:
    """Convert a linear power ratio to dB."""
    if lin <= 0.0:
        return -math.inf
    return 10.0 * math.log10(lin)


def dbm_to_mw(dbm: float) -> float:
    """Convert dBm to milliwatts."""
    return 10.0 ** (dbm / 10.0)


def mw_to_dbm(mw: float) -> float:
    """Convert milliwatts to dBm."""
    if mw <= 0.0:
        return -math.inf
    return 10.0 * math.log10(mw)


def dbm_to_watt(dbm: float) -> float:
    return dbm_to_mw(dbm) * 1e-3


def watt_to_dbm(watt: float) -> float:
    return mw_to_dbm(watt * 1e3)


def nf_to_factor(nf_db: float) -> float:
    """Noise figure (dB) -> noise factor (linear)."""
    return db_to_lin(nf_db)


def factor_to_nf(factor: float) -> float:
    """Noise factor (linear) -> noise figure (dB)."""
    return lin_to_db(factor)


def thermal_noise_dbm(bandwidth_hz: float, temperature_k: float = T0) -> float:
    """Available thermal noise power in a bandwidth, in dBm.

    At T = 290 K this returns about -174 dBm/Hz + 10*log10(B).
    """
    if bandwidth_hz <= 0.0:
        return -math.inf
    p_watt = K_BOLTZMANN * temperature_k * bandwidth_hz
    return watt_to_dbm(p_watt)


def noise_density_dbm_per_hz(temperature_k: float = T0) -> float:
    """Thermal noise spectral density in dBm/Hz."""
    return watt_to_dbm(K_BOLTZMANN * temperature_k)


def temperature_from_nf(nf_db: float, t0: float = T0) -> float:
    """Equivalent noise temperature (K) from noise figure (dB)."""
    return (nf_to_factor(nf_db) - 1.0) * t0


def nf_from_temperature(te_k: float, t0: float = T0) -> float:
    """Noise figure (dB) from equivalent noise temperature (K)."""
    return factor_to_nf(1.0 + te_k / t0)


def format_eng(value: float, unit: str = "", sig: int = 4) -> str:
    """Format a value with an SI engineering prefix (e.g. 1.5 GHz)."""
    if value == 0 or not math.isfinite(value):
        return f"{value:g} {unit}".strip()
    prefixes = {
        -24: "y", -21: "z", -18: "a", -15: "f", -12: "p", -9: "n",
        -6: "u", -3: "m", 0: "", 3: "k", 6: "M", 9: "G", 12: "T", 15: "P",
    }
    exp = int(math.floor(math.log10(abs(value)) / 3.0) * 3)
    exp = max(min(exp, 15), -24)
    scaled = value / (10.0 ** exp)
    prefix = prefixes.get(exp, f"e{exp}")
    return f"{scaled:.{sig}g} {prefix}{unit}".strip()


def parse_frequency(text: str) -> float:
    """Parse a frequency string like '1.5G', '900M', '2.4 GHz' into Hz."""
    text = text.strip().lower().replace("hz", "").strip()
    if not text:
        raise ValueError("empty frequency")
    mult = 1.0
    suffixes = {"t": 1e12, "g": 1e9, "m": 1e6, "k": 1e3}
    if text[-1] in suffixes:
        mult = suffixes[text[-1]]
        text = text[:-1].strip()
    return float(text) * mult


#: Case-sensitive SI prefixes for component values (note: 'm' = milli, 'M' = mega).
_SI_PREFIX = {
    "f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3,
    "k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9, "T": 1e12,
}


def parse_eng(text: str) -> float:
    """Parse an engineering-notation value like '2.2p', '10nH', '4.7k', '50Ω'.

    Understands SI prefixes (case-sensitive: ``m`` = milli, ``M`` / ``meg`` =
    mega) and tolerates trailing unit letters (H, F, s, Ω, ohm).
    """
    t = text.strip().replace("Ω", "").replace("ohm", "").replace("Ohm", "").strip()
    if not t:
        raise ValueError("empty value")
    if t.lower().endswith("meg"):
        return float(t[:-3]) * 1e6
    # drop a trailing unit letter that is not itself an SI prefix
    if t[-1] in ("H", "F", "s"):
        t = t[:-1].strip()
    mult = 1.0
    if t and t[-1] in _SI_PREFIX:
        mult = _SI_PREFIX[t[-1]]
        t = t[:-1].strip()
    return float(t) * mult
