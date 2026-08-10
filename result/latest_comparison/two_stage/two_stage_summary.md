# Two-Stage Optimization Comparison

**Goal:** Stage 1 explores and builds a model to find a good starting point and surrogate model. Stage 2 exploits this to perform online tuning with minimal jitter.

- **Symbols**: 1048576
- **SNR**: 28.0 dB
- **Stage 1 Iters**: 20
- **Stage 2 Iters**: 20

![Two-Stage Convergence](file:///C:/DSPPlayground/eLPO_antigravity/result/latest_comparison/two_stage/two_stage_convergence.png)

| Combination (S1->S2) | Best MLSE (Stage 1) | Max MLSE (Stage 2 Jitter) | Std Dev Log(BER) S2 | Final Best MLSE |
| --- | --- | --- | --- | --- |
| **BO->Surrogate** | `3.76e-05` | `4.14e-05` | `0.015` | `3.76e-05` |
| **SA->Surrogate** | `2.98e-04` | `3.25e-04` | `0.030` | `2.51e-04` |
| **GA->Surrogate** | `1.31e-03` | `1.31e-03` | `0.001` | `1.30e-03` |
| **BO->ESC** | `1.35e-04` | `1.72e-01` | `0.101` | `1.35e-04` |
| **BO->SafeQCD** | `1.42e-04` | `1.24e-03` | `0.463` | `3.76e-05` |
