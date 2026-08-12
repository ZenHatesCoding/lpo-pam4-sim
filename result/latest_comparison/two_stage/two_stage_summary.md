# 两阶段优化对比报告 (双模式对比)

此报告对比了 **Baseline (依赖收端 BER反馈)** 和 **Surrogate (依赖发端统计特征距离)** 两种模式在第二阶段 (Stage 2) 的表现。

- **Symbols**: 1048576
- **SNR**: 28.0 dB
- **Stage 1 Iters**: 20
- **Stage 2 Iters**: 20

![Two-Stage Convergence](file:///C:/DSPPlayground/eLPO_antigravity/result/20260812_162252_two_stage/two_stage_convergence.png)

## BO->Surrogate
| 模式 (Mode) | 第一阶段最优 (Stage 1 Best) | 第二阶段最差抖动 (Stage 2 Max) | 最终收敛最优 (Final Best) | Stage 2 对数BER标准差 |
| --- | --- | --- | --- | --- |
| **Baseline** | `1.42e-04` | `1.74e-03` | `3.76e-05` | `0.480` |
| **Surrogate** | `1.42e-04` | `1.52e-02` | `3.76e-05` | `0.876` |

## SA->Surrogate
| 模式 (Mode) | 第一阶段最优 (Stage 1 Best) | 第二阶段最差抖动 (Stage 2 Max) | 最终收敛最优 (Final Best) | Stage 2 对数BER标准差 |
| --- | --- | --- | --- | --- |
| **Baseline** | `1.80e-04` | `2.04e-04` | `1.33e-04` | `0.047` |
| **Surrogate** | `1.80e-04` | `1.17e-03` | `1.80e-04` | `0.202` |

## GA->Surrogate
| 模式 (Mode) | 第一阶段最优 (Stage 1 Best) | 第二阶段最差抖动 (Stage 2 Max) | 最终收敛最优 (Final Best) | Stage 2 对数BER标准差 |
| --- | --- | --- | --- | --- |
| **Baseline** | `1.44e-03` | `1.44e-03` | `1.43e-03` | `0.001` |
| **Surrogate** | `1.44e-03` | `1.73e-03` | `1.04e-03` | `0.063` |

## BO->ESC
| 模式 (Mode) | 第一阶段最优 (Stage 1 Best) | 第二阶段最差抖动 (Stage 2 Max) | 最终收敛最优 (Final Best) | Stage 2 对数BER标准差 |
| --- | --- | --- | --- | --- |
| **Baseline** | `1.38e-03` | `1.91e-01` | `1.38e-03` | `0.071` |
| **Surrogate** | `1.38e-03` | `1.87e-01` | `1.38e-03` | `0.071` |

## BO->SafeQCD
| 模式 (Mode) | 第一阶段最优 (Stage 1 Best) | 第二阶段最差抖动 (Stage 2 Max) | 最终收敛最优 (Final Best) | Stage 2 对数BER标准差 |
| --- | --- | --- | --- | --- |
| **Baseline** | `6.92e-04` | `1.41e-03` | `5.32e-04` | `0.131` |
| **Surrogate** | `6.92e-04` | `6.37e-03` | `6.92e-04` | `0.206` |

