# RF Cascade Studio

A desktop application for **RF signal-chain (cascade) analysis**. Build a chain
of two-port components — amplifiers, mixers, filters, attenuators, cables, and
more — and see the end-to-end system performance update live: gain, noise
figure, intercept points, compression, dynamic range, and per-node signal
levels.

## Features

- **Cascade engine** computing, per stage and for the full chain:
  - Cascaded gain and noise figure (Friis)
  - Input/output IP3 and IP2, with **coherent (worst-case)** or
    **power (non-coherent)** intermodulation combining
  - Input/output 1 dB compression point
  - Signal power, noise floor, and SNR at every node, plus P1dB / IP3 headroom
- **System metrics**: MDS, sensitivity, two-tone SFDR (IM3 & IM2),
  compression-limited dynamic range, and link margin
- **Input-power sweep**: the classic two-tone fundamental / IM3 / IM2 plot that
  shows spurious-free dynamic range graphically
- **Monte-Carlo tolerance analysis**: perturb per-part gain / NF / OIP3 by their
  1-sigma tolerances and view the resulting distributions of system metrics
- **Built-in parts library** of representative RF components to build from
- **Save / load** projects as JSON (`.rfc`) and **export** results to CSV
- Qt-based GUI with live plots

## Requirements

- Python 3.10+
- [PySide6](https://pypi.org/project/PySide6/) ≥ 6.6
- [pyqtgraph](https://pypi.org/project/pyqtgraph/) ≥ 0.13
- [numpy](https://pypi.org/project/numpy/) ≥ 1.24

## Installation

```bash
python -m venv .venv
source .venv/bin/activate        # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

Launch the GUI:

```bash
python main.py
```

Open a saved project on startup:

```bash
python main.py project.rfc
```

## Project layout

```
rfcascade/
  core/        # analysis engine (no GUI dependencies)
    cascade.py     # the cascade analysis engine
    components.py  # Component / SignalSource data models
    library.py     # built-in parts library
    project.py     # save/load (JSON) and CSV export
    sweep.py       # two-tone input-power sweep
    montecarlo.py  # tolerance analysis
    units.py       # dB / dBm / linear / noise-temperature helpers
  gui/         # PySide6 + pyqtgraph user interface
tests/
  test_cascade.py  # engine unit tests
main.py        # entry point
```

## Tests

The cascade engine is covered by a standalone test script:

```bash
python tests/test_cascade.py
```

## Notes on conventions

- Distortion intercepts (OIP3, OIP2, P1dB) are stored **output-referred** in
  dBm, matching how component datasheets typically specify them; input-referred
  values are derived from the stage gain.
- Use `inf` for an ideal / unspecified distortion parameter — it drops out of
  the cascade.
- Passive lossy stages (filters, cables, attenuators) take their noise figure
  equal to their insertion loss.
