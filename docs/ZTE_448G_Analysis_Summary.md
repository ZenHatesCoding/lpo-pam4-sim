# 448G Channel Modeling and Simulation References
**Based on**: ZTE 448G Channel Bandwidth Requirement Analysis (2026 ODCC)

This document extracts the specific channel models, simulation tools, and parameter configurations used by ZTE to accurately simulate 448G (212.5 GBd) signaling. These references can be used to calibrate and improve our own LPO DSP and channel simulations.

## 1. Channel S-Parameter Models (Where to Download)
The report relies on 9 passive channel prototype S-parameter models. Based on their naming conventions, these are contributions submitted to the **IEEE P802.3dj Task Force** (which standardizes 200G/lane Ethernet). 

You can download the raw `.s4p` Touchstone files for these channels from the **IEEE 802.3dj Task Force public meeting materials directory** (look for the dates in 2023/2024 meetings):
* `lim_3dj_03_230629` (June 2023, PCB + Cable)
* `lim_3dj_04_230629` (June 2023, PCB + Cable)
* `lim_3dj_07_2309` (Sept 2023, PCB + Cable)
* `tracy_efai_03a_250430` (Likely a typo in the slide for `tracy_3dj_...`, CPC + Cable)
* `kocsis_3dj_02_2305` (May 2023, PCB + Cable)
* `shanbhag_3dj_02_2305` (May 2023, NPC + Cable)
* `akinwale_3dj_02_2311_VendorX` (Nov 2023, PCB + Cable)
* `akinwale_3dj_02_2311_VendorY` (Nov 2023, PCB + Cable)
* `weaver_3dj_02_2311` (Nov 2023, PCB + Cable)

**Actionable Takeaway**: To make our channel simulations realistic, we should stop using synthetically generated simple AWGN or ideal low-pass channels, and instead download these exact `.s4p` files from the IEEE 802.3dj website to use as our baseline channel models.

## 2. Simulation Tool (COM)
* **COM Version**: `com_ieee8023_4p14p0.m` (IEEE 802.3 Channel Operating Margin script, version 4.14.0).
* **Base Configuration**: `config_07_07_2025_400G_KR_PAM x.xlsx`

## 3. High-Accuracy 448G (212.5 GBd) Component Parameters
To simulate 212.5 GBd accurately without the package/die bottlenecks masking the channel effects, ZTE applied specific scaling to standard IEEE COM parameters. We should mirror these settings in our `config.xlsx` or `channel_imdd.py`:

### A. Baud Rate
* $f_b = 212.5$ GBd (For 448G PAM4/PAM6)

### B. Package Model Tuning (To achieve >150 GHz BW)
* **Trace Length**: Shortened to **30 mm**
* **Parasitic Capacitance ($C_p$)**: Reduced to **$0.1 \times 10^{-4}$ fF** (essentially negating package capacitance).

### C. Die Termination Scaling (To achieve ~110 GHz BW)
* The parasitic components $C_d$, $L_s$, and $C_b$ are scaled by a factor of **$1/1.4$**.

### D. Tx/Rx Capability Scaling
Because the baud rate is roughly doubled compared to 106.25 GBd (800G Ethernet), the time-domain limitations and noise floors need to be scaled accordingly:
* **Rise Time ($T_r$)**: Scaled by **$1/2$**
* **Noise Filter ($f_r$)**: Scaled by **$2$** (doubling the filter bandwidth)
* **Jitter and Noise**: Random Jitter ($\sigma_{RJ}$), Deterministic Jitter ($A_{DD}$), and Gaussian Noise ($\eta_0$) are all scaled by **$1/2$**.

### E. Equalization Architecture (DSP Baseline)
To successfully equalize the 448G signal, the following DSP architecture is assumed (we should ensure our DSP algorithms match this baseline capability):
* **CTLE Poles/Zeros**: $[f_z, f_{p1}, f_{p2}, f_{HP\_PZ}] = f_b / [2.5, 2.5, 1, 160]$
* **Rx FFE (Feed-Forward Equalizer)**:
  * Fixed taps: **8 pre-taps, 22 post-taps**
  * Floating taps: **2 groups of 6 consecutive taps** (can float up to 160 UI)
* **DFE (Decision Feedback Equalizer)**: **1 tap** only (to minimize error propagation at extreme speeds).
* **MLSD (Maximum Likelihood Sequence Detection)**: **ON** (Indicates that Viterbi-like sequence detection is necessary for 448G, which aligns with our `mlse_burg.py` requirement).
