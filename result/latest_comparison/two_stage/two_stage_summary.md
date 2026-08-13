# 两阶段优化对比报告 (双模式对比)

此报告对比了 **Baseline (依赖收端 BER反馈)** 和 **Surrogate (依赖发端统计特征距离)** 两种模式在第二阶段 (Stage 2) 的表现。

- **Symbols**: 200000
- **SNR**: 26.0 dB
- **Stage 1 Iters**: 20
- **Stage 2 Iters**: 20

![Two-Stage Convergence](file:///C:/DSPPlayground/eLPO_antigravity/result/20260813_090855_two_stage/two_stage_convergence.png)

## BO->Surrogate
| 模式 (Mode) | 第一阶段最优 (Stage 1 Best) | 第二阶段最差抖动 (Stage 2 Max) | 最终收敛最优 (Final Best) | Stage 2 对数BER标准差 |
| --- | --- | --- | --- | --- |
| **Baseline** | `1.43e-03` | `6.20e-03` | `1.97e-04` | `0.376` |
| **Surrogate** | `1.43e-03` | `6.29e-03` | `3.58e-04` | `0.232` |

## SA->Surrogate
| 模式 (Mode) | 第一阶段最优 (Stage 1 Best) | 第二阶段最差抖动 (Stage 2 Max) | 最终收敛最优 (Final Best) | Stage 2 对数BER标准差 |
| --- | --- | --- | --- | --- |
| **Baseline** | `4.11e-04` | `4.47e-04` | `3.45e-04` | `0.024` |
| **Surrogate** | `4.11e-04` | `4.29e-04` | `3.97e-04` | `0.015` |

## GA->Surrogate
| 模式 (Mode) | 第一阶段最优 (Stage 1 Best) | 第二阶段最差抖动 (Stage 2 Max) | 最终收敛最优 (Final Best) | Stage 2 对数BER标准差 |
| --- | --- | --- | --- | --- |
| **Baseline** | `1.50e-03` | `1.50e-03` | `1.50e-03` | `0.000` |
| **Surrogate** | `1.50e-03` | `1.50e-03` | `1.50e-03` | `0.000` |

## BO->ESC
| 模式 (Mode) | 第一阶段最优 (Stage 1 Best) | 第二阶段最差抖动 (Stage 2 Max) | 最终收敛最优 (Final Best) | Stage 2 对数BER标准差 |
| --- | --- | --- | --- | --- |
| **Baseline** | `1.07e-03` | `1.80e-01` | `1.07e-03` | `0.069` |
| **Surrogate** | `1.07e-03` | `1.80e-01` | `1.07e-03` | `0.126` |

## BO->SafeQCD
| 模式 (Mode) | 第一阶段最优 (Stage 1 Best) | 第二阶段最差抖动 (Stage 2 Max) | 最终收敛最优 (Final Best) | Stage 2 对数BER标准差 |
| --- | --- | --- | --- | --- |
| **Baseline** | `1.37e-03` | `5.38e-03` | `6.97e-04` | `0.279` |
| **Surrogate** | `1.37e-03` | `8.47e-03` | `1.34e-03` | `0.232` |

