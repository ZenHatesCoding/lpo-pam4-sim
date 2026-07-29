# Optimization Algorithm Comparison (Mode: JOINT)

- **Symbols**: 1048576
- **SNR**: 28.0 dB
- **Initial Sub-optimal Point**: FFE BER = `2.33e-02`, MLSE BER = `1.44e-03`

![MLSE BER Convergence](file:///C:/DSPPlayground/eLPO_antigravity/result/20260729_095728_comparison/mlse_ber_convergence.png)

| Algorithm | Best MLSE BER | Best FFE BER | Max FFE BER (Safety) | Max MLSE BER (Safety) | Optimal CTLE |
| --- | --- | --- | --- | --- | --- |
| **SHC** | `3.76e-05` | `1.05e-02` | `4.49e-02` | `3.63e-02` | `0.00dB, fz:2.5, p1:2.5, p2:0.9` |
| **Surrogate_SHC** | `5.30e-05` | `1.67e-02` | `4.35e-02` | `1.68e-02` | `0.00dB, fz:2.5, p1:2.5, p2:0.9` |
| **ESC_Safe** | `1.44e-03` | `2.33e-02` | `1.85e-01` | `1.85e-01` | `0.00dB, fz:2.5, p1:2.5, p2:1.0` |
| **BO_Safe** | `8.33e-05` | `1.73e-02` | `2.90e-02` | `5.59e-03` | `-0.00dB, fz:2.4, p1:2.5, p2:0.8` |
| **SafeQCD** | `1.15e-03` | `2.19e-02` | `3.06e-02` | `6.74e-03` | `0.00dB, fz:2.5, p1:2.5, p2:1.0` |

## Optimal Taps
- **SHC**: `[0.0, 0.0, -0.0195, -0.2987, 0.6636, 0.0, 0.0182, 0.0, 0.0]`
- **Surrogate_SHC**: `[0.0, 0.0, -0.034, -0.2856, 0.6472, 0.0, 0.0332, 0.0, 0.0]`
- **ESC_Safe**: `[0.0, 0.0, -0.034, -0.2987, 0.6091, 0.0, 0.0582, 0.0, 0.0]`
- **BO_Safe**: `[0.0119, 0.0026, -0.025, -0.2951, 0.6083, -0.0028, 0.0454, -0.0074, -0.0014]`
- **SafeQCD**: `[0.001, -0.0029, -0.0327, -0.2993, 0.6056, -0.0021, 0.0539, -0.0011, -0.0014]`

## Algorithm Configuration & Parameters
- **BO_Safe**: Gaussian Process (RBF Kernel). Safe set penalty added when pred > threshold.
- **Surrogate_SHC**: Ridge Regression sliding window (N=50). Predicts and rejects unsafe steps.
- **ESC_Safe**: Dither-based gradient estimation with repulsive barrier function.
- **SHC**: Blind micro-step Hill Climbing. No safety constraints before physical test.
