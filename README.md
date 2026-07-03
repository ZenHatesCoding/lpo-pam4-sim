# LPO PAM4/PAM6 (448G) Simulation Platform

This repository contains a pure Python, white-box simulation platform for Linear Pluggable Optics (LPO) systems. Originally designed for 112G/224G, it has been upgraded to model High-Speed SerDes links operating at **212.5 GBd (448G)**, aligned with IEEE P802.3dj standards.

## Key Features

1. **White-Box Architecture**: All Digital Signal Processing (DSP) algorithms, including adaptive filtering, timing synchronization, and sequence detection, are implemented entirely from scratch using pure `numpy`. No opaque third-party communications or optimization toolboxes are used.
2. **Multi-Rate Processing Domain**:
   - **DSP Domain**: Operates at 2 Samples Per Symbol (sps) representing realistic DAC and ADC clock boundaries.
   - **Analog Channel Domain**: Up-sampled to 8 sps to accurately simulate continuous-time high-frequency physical layer impairments and realistic **S-parameter (Touchstone `.s4p`) frequency responses** via FFT/IFFT convolution (`scikit-rf`).
3. **Advanced Equalization**:
   - **Tx DSP**: Configurable Feed-Forward Equalizer (FFE).
   - **Rx Analog**: Standard IEEE COM Continuous Time Linear Equalizer (CTLE) with tunable DC gain and peaking.
   - **Rx DSP**: Adaptive T/2-spaced FFE using **Least Squares (LS) training initialization** followed by Decision-Directed LMS (DD-LMS) tracking.
   - **MLSE**: Viterbi sequence detection coupled with the Burg algorithm for dynamic extraction of Partial Response (PR) target coefficients to whiten noise enhancement.
4. **Bayesian Optimization Framework**: Includes a custom-built Gaussian Process Regressor and Expected Improvement (EI) acquisition function for optimizing Tx FFE taps without relying on external libraries.
5. **Standards Aligned**: Scaled and parameterized to reflect **IEEE P802.3dj (448G)**, including >110 GHz die termination bandwidth scaling and real vendor-submitted Cable Reach (CR) and PCB S-parameter models.

## Project Structure

- `main.py`: The core simulator entry point. Runs the full link from Tx to Rx and outputs eye diagrams and BER metrics.
- `optimize_tx_ffe.py`: The entry point for Bayesian Optimization of the Tx FFE taps.
- `bo_optimizer.py`: The pure `numpy` Gaussian Process engine.
- `create_config.py`: Generates the `config.xlsx` file used for centralized parameter management.
- `channel_imdd.py`: The IMDD multi-rate physical channel (PCB trace, MZM, Fiber, PD, TIA, ADC).
- `tx_dsp.py` / `rx_dsp.py`: Transmitter and Receiver DSP pipelines.
- `mlse_burg.py`: Burg AR coefficient estimation and Viterbi decoding.
- `scratch/download_s4p.py`: Utility script to fetch raw IEEE 802.3dj S-parameter zip files.
- `docs/`: Contains simulation reports, eye diagrams, and standard parameter explanations (e.g., `ZTE_448G_Analysis_Summary.md`).

## Quick Start

1. Install basic dependencies: `pip install numpy scipy matplotlib pandas openpyxl scikit-rf`.
2. Run `python scratch/download_s4p.py` to fetch the real 448G IEEE `.s4p` channel models.
3. Run `python create_config.py` to generate or reset `config.xlsx`.
3. Adjust parameters in `config.xlsx` as needed.
4. Run `main.py` for a single-point simulation.
5. Run `optimize_tx_ffe.py` to perform automatic FFE tap optimization.

## Documentation
Check the `docs/` directory for detailed explanations of system parameters and test reports.
