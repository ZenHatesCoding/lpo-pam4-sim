# Tx FFE Bayesian Optimization Report

## Setup
- **Channel**: 112G PAM4 (56 GBd), 15 dB Host PCB trace loss, 35GHz optics.
- **Optimizer**: White-Box Gaussian Process Regressor (RBF Kernel) with Expected Improvement.
- **Constraint**: Peak sum limit `sum(|w|) = 1.0`.

## Results
- **Default Taps [0,0,0,0,1,0,0,0,0] BER**: `8.82e-02`
- **Optimal MLSE BER**: `8.82e-02`
- **Optimal Tx FFE Taps**: `[0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0]`
- **Optimal CTLE DC Gain**: `-12.00 dB`

## Convergence Trace
- Eval 0: `8.82e-02`
- Eval 1: `3.34e-01`
- Eval 2: `3.17e-01`
- Eval 3: `3.18e-01`
- Eval 4: `3.18e-01`
- Eval 5: `3.04e-01`
- Eval 6: `2.12e-01`
- Eval 7: `2.40e-01`
- Eval 8: `3.12e-01`
- Eval 9: `1.75e-01`
- Eval 10: `2.87e-01`
- Eval 11: `3.00e-01`
- Eval 12: `2.02e-01`
- Eval 13: `2.95e-01`
- Eval 14: `2.76e-01`
- Eval 15: `2.18e-01`
- Eval 16: `2.69e-01`
- Eval 17: `2.06e-01`
- Eval 18: `2.84e-01`
- Eval 19: `3.10e-01`
- Eval 20: `1.13e-01`
- Eval 21: `2.14e-01`
- Eval 22: `1.95e-01`
- Eval 23: `1.38e-01`
- Eval 24: `2.00e-01`
- Eval 25: `2.49e-01`
