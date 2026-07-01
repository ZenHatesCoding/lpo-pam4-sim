# LPO PAM4 (112G/224G) Simulation Platform

This repository contains a pure Python, white-box simulation platform for Linear Pluggable Optics (LPO) PAM4 systems. It is designed to model High-Speed SerDes links operating at 56 GBd (112G) and is architected to be extensible to 112 GBd (224G).

## Key Features

1. **White-Box Architecture**: All Digital Signal Processing (DSP) algorithms, including adaptive filtering, timing synchronization, and sequence detection, are implemented entirely from scratch using pure `numpy`. No opaque third-party communications or optimization toolboxes are used.
2. **Multi-Rate Processing Domain**:
   - **DSP Domain**: Operates at 2 Samples Per Symbol (sps) representing realistic DAC and ADC clock boundaries.
   - **Analog Channel Domain**: Up-sampled to 8 sps using Zero-Order Hold (ZOH) to accurately simulate continuous-time high-frequency physical layer impairments.
3. **Advanced Equalization**:
   - **Tx DSP**: Configurable Feed-Forward Equalizer (FFE) and Continuous Time Linear Equalizer (CTLE).
   - **Rx DSP**: Adaptive T/2-spaced FFE converging via LMS to Decision-Directed (DD-LMS).
   - **MLSE**: Viterbi sequence detection coupled with the Burg algorithm for dynamic extraction of Partial Response (PR) target coefficients to whiten noise enhancement.
4. **Bayesian Optimization Framework**: Includes a custom-built Gaussian Process Regressor and Expected Improvement (EI) acquisition function for optimizing 9-dimensional Tx FFE taps without relying on external libraries.
5. **Standards Aligned**: Parameterized to reflect IEEE 802.3ck and OIF CEI-112G (e.g., 15dB Host PCB trace loss, 35/40GHz electro-optic component bandwidths).

## Project Structure

- `main.py`: The core simulator entry point. Runs the full link from Tx to Rx and outputs eye diagrams and BER metrics.
- `optimize_tx_ffe.py`: The entry point for Bayesian Optimization of the Tx FFE taps.
- `bo_optimizer.py`: The pure `numpy` Gaussian Process engine.
- `create_config.py`: Generates the `config.xlsx` file used for centralized parameter management.
- `channel_imdd.py`: The IMDD multi-rate physical channel (PCB trace, MZM, Fiber, PD, TIA, ADC).
- `tx_dsp.py` / `rx_dsp.py`: Transmitter and Receiver DSP pipelines.
- `mlse_burg.py`: Burg AR coefficient estimation and Viterbi decoding.
- `docs/`: Contains simulation reports, eye diagrams, and standard parameter explanations.

## Quick Start

1. Install basic dependencies (usually just `numpy`, `scipy`, `matplotlib`, `pandas`, `openpyxl`).
2. Run `create_config.py` to generate or reset `config.xlsx`.
3. Adjust parameters in `config.xlsx` as needed.
4. Run `main.py` for a single-point simulation.
5. Run `optimize_tx_ffe.py` to perform automatic FFE tap optimization.

## Documentation
Check the `docs/` directory for detailed explanations of system parameters and test reports.
