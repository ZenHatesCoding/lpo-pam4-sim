# LPO PAM4 System Status Report

## Current Completion Status
The simulation platform has reached **Version 2**, with the following architectural components fully implemented:
1. **Multi-rate Simulation Domain**:
   - **DSP Domain**: Operates at 2 Samples Per Symbol (sps). This perfectly aligns with real hardware ADC/DAC boundaries.
   - **Analog Channel Domain**: The DAC output is up-sampled (using a Zero-Order Hold) to 8 sps. The MZM, Fiber, PD, TIA, and analog front-end of the ADC operate at this higher resolution.
2. **DSP Algorithms**:
   - **Tx DSP**: Pulse shaping, basic CTLE, and T-spaced FFE.
   - **Rx DSP**: Adaptive Rx FFE (T/2 spaced) converging via LMS to DD-LMS with automatic cross-correlation-based channel delay synchronization.
   - **MLSE**: Burg algorithm for extracting Partial Response Target AR parameters, and Viterbi sequence detection supporting configurable memory.

## What is Missing / TODOs
- **Dispersion Models (CD)**: Currently, fiber is modeled merely as an insertion loss. At 1310nm for short reaches (FR4/DR4), chromatic dispersion is small but still non-zero.
- **S-Parameter Integration**: The component frequency responses (MZM, PD) are modeled via multi-order Butterworth filters. Replacing these with `.s4p` Touchstone files from actual hardware characterizations (e.g. OIF CEI reference packages) is required for production-level accuracy.
- **Tx FFE Optimization**: Tx FFE taps are currently pass-through. They should be calculated via Minimum Mean Square Error (MMSE) to pre-emphasize the channel roll-off.
- **224G Adaptations**: The current setup uses 56 GBd (112G). We need to document the 112 GBd parameters and test memory length = 2 for Viterbi.

## System Parameters vs. Standards
The parameters in `config.xlsx` were chosen to mirror standard short-reach pluggable links (e.g., IEEE 802.3cu / OIF CEI-112G):
- **Baud Rate**: 56 GBd (representing 112G PAM4).
- **Component Bandwidths (35 - 40 GHz)**: To support 56 GBd, the Nyquist frequency is 28 GHz. Components are typically required to have a 3dB bandwidth of roughly 0.6x to 0.7x the baud rate to balance noise and ISI. 35 GHz is highly realistic for modern Silicon Photonics MZM and TIAs.
- **Fiber Link**: Modeled as 2 km (representing FR4 specifications).
- **Fiber Loss**: 0.4 dB/km is standard for single-mode fiber (SMF) at 1310 nm.
- **Target SNR**: 25 dB is a typical high-quality electrical interface SNR prior to major channel impairments.
