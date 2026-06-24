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
- **S-parameter / frequency-response simulation**: cascade the full complex
  two-port of every stage and plot the chain's |S21|, |S11|, |S22|, VSWR,
  group delay and phase versus frequency — see filter shapes, passband ripple,
  −3 dB bandwidth and return loss
- **Lumped-component circuit-block builder**: assemble a two-port from series /
  shunt R-L-C ladder rungs with a live S21 / S11 preview, then drop it into the
  chain as a stage. One-click Butterworth LPF / HPF / BPF and π-pad presets
- **Touchstone import / export**: pull a measured part in from a `.s1p` / `.s2p`
  file, or write the cascaded chain response back out as Touchstone
- **Built-in parts library** of representative RF components (including ready-made
  lumped filter blocks) to build from
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
    cascade.py     # the cascade analysis engine + frequency_response()
    components.py  # Component / SignalSource data models
    sparams.py     # 2-port S-parameters: S<->ABCD, cascading, VSWR, group delay
    circuit.py     # lumped R/L/C ladder -> S-parameters, filter synthesis
    touchstone.py  # .s1p / .s2p Touchstone read & write
    library.py     # built-in parts library (incl. lumped filter blocks)
    project.py     # save/load (JSON) and CSV export
    sweep.py       # two-tone input-power sweep
    montecarlo.py  # tolerance analysis
    units.py       # dB / dBm / linear / noise-temperature helpers
  gui/         # PySide6 + pyqtgraph user interface
    circuit_builder.py  # lumped circuit-block builder dialog
tests/
  test_cascade.py  # cascade engine unit tests
  test_sparams.py  # S-parameter / lumped-circuit / Touchstone tests
main.py        # entry point
```

## Tests

The engine is covered by standalone test scripts (no pytest required):

```bash
python tests/test_cascade.py
python tests/test_sparams.py
```

## Notes on conventions

- Distortion intercepts (OIP3, OIP2, P1dB) are stored **output-referred** in
  dBm, matching how component datasheets typically specify them; input-referred
  values are derived from the stage gain.
- Use `inf` for an ideal / unspecified distortion parameter — it drops out of
  the cascade.
- Passive lossy stages (filters, cables, attenuators) take their noise figure
  equal to their insertion loss.
- The frequency-response view is independent of the scalar cascade: stages with
  a lumped circuit or imported Touchstone data contribute their real two-port
  shape, while plain gain/loss stages are modelled as ideal, matched flat blocks.
  Two-ports are cascaded through their ABCD (chain) matrices at a common
  reference impedance (default 50 Ω). NF / IP3 remain single-frequency.
