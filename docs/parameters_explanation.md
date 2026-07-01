# IMDD LPO Simulation Parameter Standards

This document records the standard alignments and parameter selections for the Linear Pluggable Optics (LPO) simulation platform, specifically focusing on the 112G (56 GBd) PAM4 ecosystem.

## 1. IEEE 802.3ck / OIF CEI-112G Reference Architecture
Linear Pluggable Optics removes the DSP from the optical module to save power and latency. This places the burden of channel compensation entirely on the Host ASIC's DSP.
The signal chain involves:
`Host Tx DSP -> PCB Trace (Host) -> Optics (Linear Driver + MZM) -> Fiber -> Optics (PD + Linear TIA) -> PCB Trace (Host) -> Host Rx DSP`

### System Baud Rate
- **112G PAM4**: Operates at 56 GBd (gigabaud) or 53.125 GBd depending on FEC overhead. The Nyquist frequency is exactly half the baud rate: **28 GHz**.

### Component Bandwidths
To balance Inter-Symbol Interference (ISI) and noise, the 3dB bandwidth of analog components is typically targeted at 0.6x to 0.75x the baud rate.
- **MZM (Mach-Zehnder Modulator)**: 35 GHz
- **PD (Photodetector)**: 40 GHz
- **TIA (Transimpedance Amplifier)**: 35 GHz
- **ADC Analog Front-End**: 35 GHz

*Simulation note:* Using a cascade of 4th-order Butterworth filters at 35GHz only yields ~2.15 dB of insertion loss at 28 GHz. This alone is too ideal to represent a real channel.

### Insertion Loss (Host PCB Trace)
- **CEI-112G-VSR**: Defines the Very Short Reach electrical channel. The insertion loss from the Host ASIC package bump to the optical module connector can be up to **15 to 16 dB at the Nyquist frequency (28 GHz)**.
- *Simulation Implementation*: Modeled as a 1st-order RC low-pass filter configured to drop exactly 15 dB at 28 GHz. This introduces severe high-frequency roll-off (ISI), which necessitates heavy Tx Pre-emphasis (FFE) and Rx Equalization.

### Fiber Link (Optical Domain)
- **FR4 / DR4 Specifications**: Single-mode fiber operating at 1310 nm.
- **Loss**: 0.4 dB/km. Typical LPO short-reach links are up to 2 km.
- *Simulation Note*: At 1310nm, chromatic dispersion is near zero. Therefore, fiber is modeled strictly as a flat amplitude attenuation (linear loss).

## 2. DSP Algorithm Settings
### Tx FFE (Feed-Forward Equalizer)
- **Taps**: 9 taps (T-spaced) are used. 
- **Pre-cursor vs Post-cursor**: Configured symmetrically with the center tap at index 4 (4 pre-cursors, 1 main, 4 post-cursors). 
- **Normalization Constraint**: To prevent DAC clipping, the peak swing is constrained: $\sum_{i} |w_i| = 1.0$.

### Rx FFE & MLSE
- **Rx FFE**: 15 taps (T/2 spaced) converging via LMS.
- **MLSE**: Viterbi sequence detection with Partial Response target extracted via Burg algorithm to whiten the noise enhancement introduced by forcing the FFE over a heavily attenuated channel.
