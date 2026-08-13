# 两阶段优化对比报告 (双模式对比)

此报告对比了 **Baseline (依赖收端 BER反馈)** 和 **Surrogate (搭载 GPR + UCB 护栏的发端统计模型)** 两种模式在第二阶段 (Stage 2) 的表现。

- **Symbols**: 1048576
- **SNR**: 28.0 dB
- **Stage 1 Iters**: 20
- **Stage 2 Iters**: 20

![Two-Stage Convergence](file:///C:/DSPPlayground/eLPO_antigravity/result/20260813_112031_two_stage/two_stage_convergence.png)

## BO->Surrogate
| 模式 (Mode) | 第一阶段最优 (Stage 1 Best) | 第二阶段最差抖动 (Stage 2 Max) | 最终收敛最优 (Final Best) | Stage 2 对数BER标准差 |
| --- | --- | --- | --- | --- |
| **Baseline** | `1.42e-04` | `1.74e-03` | `3.76e-05` | `0.480` |
| **Surrogate** | `1.42e-04` | `1.19e-03` | `3.76e-05` | `0.266` |

## SA->Surrogate
| 模式 (Mode) | 第一阶段最优 (Stage 1 Best) | 第二阶段最差抖动 (Stage 2 Max) | 最终收敛最优 (Final Best) | Stage 2 对数BER标准差 |
| --- | --- | --- | --- | --- |
| **Baseline** | `1.80e-04` | `2.04e-04` | `1.33e-04` | `0.047` |
| **Surrogate** | `1.80e-04` | `2.06e-04` | `1.67e-04` | `0.025` |

## GA->Surrogate
| 模式 (Mode) | 第一阶段最优 (Stage 1 Best) | 第二阶段最差抖动 (Stage 2 Max) | 最终收敛最优 (Final Best) | Stage 2 对数BER标准差 |
| --- | --- | --- | --- | --- |
| **Baseline** | `1.44e-03` | `1.44e-03` | `1.43e-03` | `0.001` |
| **Surrogate** | `1.44e-03` | `1.44e-03` | `1.43e-03` | `0.001` |

## BO->ESC
| 模式 (Mode) | 第一阶段最优 (Stage 1 Best) | 第二阶段最差抖动 (Stage 2 Max) | 最终收敛最优 (Final Best) | Stage 2 对数BER标准差 |
| --- | --- | --- | --- | --- |
| **Baseline** | `1.38e-03` | `1.91e-01` | `1.38e-03` | `0.071` |
| **Surrogate** | `1.38e-03` | `1.90e-01` | `1.38e-03` | `0.067` |

## BO->SafeQCD
| 模式 (Mode) | 第一阶段最优 (Stage 1 Best) | 第二阶段最差抖动 (Stage 2 Max) | 最终收敛最优 (Final Best) | Stage 2 对数BER标准差 |
| --- | --- | --- | --- | --- |
| **Baseline** | `6.92e-04` | `1.41e-03` | `5.32e-04` | `0.131` |
| **Surrogate** | `6.92e-04` | `3.71e-03` | `2.44e-04` | `0.277` |

