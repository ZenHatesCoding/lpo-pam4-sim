# Optimization Algorithm Comparison (Mode: JOINT)

- **Symbols**: 1048576
- **Noise**: Distributed Physical Modeling
- **Initial Sub-optimal Point**: FFE BER = `5.34e-05`, MLSE BER = `5.87e-05`

![MLSE BER Convergence](file:///C:/DSPPlayground/eLPO_antigravity/result/20260902_105342_comparison/mlse_ber_convergence.png)

| Algorithm | Best MLSE BER | Best FFE BER | Max FFE BER (Safety) | Max MLSE BER (Safety) | Optimal CTLE |
| --- | --- | --- | --- | --- | --- |
| **SHC** | `2.79e-05` | `2.26e-05` | `4.50e-04` | `4.55e-04` | `0.00dB, fz:2.5, p1:2.5, p2:1.0` |
| **Surrogate_SHC** | `2.79e-05` | `2.26e-05` | `1.23e-04` | `1.29e-04` | `0.00dB, fz:2.5, p1:2.5, p2:1.0` |
| **ESC_Safe** | `5.34e-05` | `4.81e-05` | `1.59e-02` | `1.59e-02` | `0.00dB, fz:2.4, p1:2.4, p2:0.7` |
| **BO_Safe** | `2.79e-05` | `2.26e-05` | `6.21e-04` | `6.26e-04` | `0.00dB, fz:2.5, p1:2.4, p2:1.0` |
| **SafeQCD** | `2.98e-05` | `2.46e-05` | `7.37e-05` | `7.90e-05` | `-0.17dB, fz:2.6, p1:2.5, p2:1.2` |

## Optimal Taps
- **SHC**: `[0.0, 0.0, -0.034, -0.2487, 0.6591, 0.0, 0.0582, 0.0, 0.0]`
- **Surrogate_SHC**: `[0.0, 0.0, -0.034, -0.2487, 0.6591, 0.0, 0.0582, 0.0, 0.0]`
- **ESC_Safe**: `[-0.0448, 0.0526, 0.0245, -0.2521, 0.4721, 0.0538, -0.0045, 0.043, -0.0526]`
- **BO_Safe**: `[0.0096, -0.0266, -0.002, -0.2895, 0.5993, -0.0301, 0.0259, 0.0157, -0.0015]`
- **SafeQCD**: `[0.0112, -0.0089, -0.0252, -0.294, 0.6129, -0.0103, 0.0317, 0.0013, 0.0045]`

## Algorithm Configuration & Parameters
- **BO_Safe**: Gaussian Process (RBF Kernel). Safe set penalty added when pred > threshold.
- **Surrogate_SHC**: Ridge Regression sliding window (N=50). Predicts and rejects unsafe steps.
- **ESC_Safe**: Dither-based gradient estimation with repulsive barrier function.
- **SHC**: Blind micro-step Hill Climbing. No safety constraints before physical test.
