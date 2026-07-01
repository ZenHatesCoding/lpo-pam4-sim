# Tx FFE Bayesian Optimization Report

## Setup
- **Channel**: 112G PAM4 (56 GBd), 15 dB Host PCB trace loss, 35GHz optics.
- **Optimizer**: White-Box Gaussian Process Regressor (RBF Kernel) with Expected Improvement.
- **Constraint**: Peak sum limit `sum(|w|) = 1.0`.

## Results
- **Default Taps [0,0,0,0,1,0,0,0,0] BER**: `1.57e-01`
- **Optimal MLSE BER**: `1.57e-01`
- **Optimal Taps**: `[0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0]`

## Convergence Trace
- Eval 0: `1.57e-01`
- Eval 1: `3.41e-01`
- Eval 2: `3.44e-01`
- Eval 3: `3.11e-01`
- Eval 4: `3.53e-01`
- Eval 5: `3.09e-01`
- Eval 6: `3.03e-01`
- Eval 7: `3.30e-01`
- Eval 8: `3.06e-01`
- Eval 9: `3.40e-01`
- Eval 10: `3.37e-01`
- Eval 11: `3.22e-01`
- Eval 12: `2.84e-01`
- Eval 13: `3.35e-01`
- Eval 14: `2.66e-01`
- Eval 15: `3.28e-01`
- Eval 16: `3.40e-01`
- Eval 17: `3.59e-01`
- Eval 18: `3.44e-01`
- Eval 19: `3.42e-01`
- Eval 20: `2.53e-01`
- Eval 21: `3.24e-01`
- Eval 22: `2.82e-01`
- Eval 23: `3.26e-01`
- Eval 24: `3.48e-01`
- Eval 25: `3.45e-01`
