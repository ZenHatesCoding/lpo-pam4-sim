# DDPS v2 结果（112G 物理模型，BER_MLSE）

修复 v1 的 4 处实现错误（Stage-1 邻域采样死代码 / FFE 主抽头参数化错配 / Tx-FIR 探针跨插损对齐漂移 / 缺梯度门控，详见 [`docs/06`](../docs/06_DDPS_v2_Rerun.md)）后重跑。两组实验对 8 个应力环境的 Stage-2 在线调优，**真实 BER_MLSE 全程无一步劣于种子**；其中混合锚定模型（主实验）在 20 dB 插损用例把 BER 从 `5.8e-2` 降到 `3.0e-3`（约 20×），复合应力从 `7.7e-2` 降到 `5.7e-3`（约 13×）。

**评估口径**：Rx 22-tap LMS FFE（无 DFE）→ MLSE（memory=1，Burg 白化），输出为 BER_MLSE；每点 131072 符号、固定随机种子；种子 x0（Tx FFE 9-tap + Tx CTLE gDC/gDC2）两实验相同；Stage-2 只依据代理模型，真实 BER 仅记录不参与决策。

## 两组实验：同一条测试线，只有“训练数据”不同

| | 主实验 | 对照实验 |
| --- | --- | --- |
| 目录 | [`result/ddps_v2_20260907`](ddps_v2_20260907) | [`result/ddps_v2_control`](ddps_v2_control) |
| 训练数据 | [`dataset/ddps_v2_dataset_20260907_190819.csv`](../dataset/ddps_v2_dataset_20260907_190819.csv)，共 748 行：Base_IL10 邻域 320 点 + 其余 7 个环境各 60 点 + 每环境 1 个种子点（同一文件） | 同一文件里只取 `env == Base_IL10` 的 321 行（320 邻域 + 1 种子） |
| 数据覆盖 | 8 个环境都有邻域锚点（训练域覆盖测试域） | 只在基准环境 IL10 采样 |
| 模型 | [`models/ddps_v2/`](../models/ddps_v2/) | [`models/ddps_v2_control/`](../models/ddps_v2_control/) |
| 模型算法/超参/评估 | 相同：二阶多项式 Ridge（白盒），8 用例、同种子 x0、同 131072 符号协议 | 与主实验完全相同 |
| 想回答的问题 | 交付用结果 | “只用基准环境训练，能不能在漂移环境里直接调优”（AGENTS.md 控制变量法） |

两个实验的差异**只有训练数据构成**，其余完全一致，因此二者的结果差 = 混合锚点数据带来的增益。

## 结果对比（每行为一个用例）

| 用例（环境） | 种子 | 主实验最优 | 对照(仅基训)最优 | 主Δlog10 | 对照Δlog10 | 深水复核(主, 262144 sym) |
| --- | --- | --- | --- | --- | --- | --- |
| Base_IL10 (IL10dB) | `5.53e-04` | `3.35e-04` (×1.7) | `3.55e-04` (×1.6) | `-0.22` | `-0.19` | `1.6e-04` |
| IL_Sweep_14dB (IL14dB) | `2.08e-03` | `5.66e-04` (×3.7) | `5.49e-04` (×3.8) | `-0.56` | `-0.58` | `3.1e-04` |
| IL_Worst_20dB (IL20dB) | `5.82e-02` | `2.97e-03` (×19.6) | `1.47e-02` (×3.9) | `-1.29` | `-0.60` | `2.7e-03` |
| CD_Sweep_15ps (IL10dB+CD15) | `6.57e-04` | `3.35e-04` (×2.0) | `3.55e-04` (×1.8) | `-0.29` | `-0.27` | `1.7e-04` |
| CD_Sweep_28ps (IL10dB+CD28) | `6.94e-04` | `3.39e-04` (×2.0) | `3.55e-04` (×2.0) | `-0.31` | `-0.29` | `1.7e-04` |
| DGD_Sweep_2ps (IL10dB+DGD2ps) | `4.42e-04` | `3.35e-04` (×1.3) | `3.55e-04` (×1.2) | `-0.12` | `-0.09` | `1.7e-04` |
| DGD_Sweep_5ps (IL10dB+DGD5ps) | `4.71e-04` | `3.39e-04` (×1.4) | `3.59e-04` (×1.3) | `-0.14` | `-0.12` | `1.7e-04` |
| Combined_Stress (IL20dB+CD15+DGD5ps) | `7.72e-02` | `5.74e-03` (×13.4) | `3.48e-02` (×2.2) | `-1.13` | `-0.35` | `5.8e-03` |

读数方式：`×` 是相对种子的改善倍数；Δlog10 为负表示变好。两列都有明显改善说明“负向优化”已根治（对照实验即使用基准环境训练也不变差）；主实验在 IL20 / 复合应力上比对照再优 4~10×，说明高噪声环境需要混合环境数据锚定。

## 代理模型指标（混合锚定训练，测试集 holdout）

- Model A（Tx FIR→log10 BER_MLSE，寻优方向）：R²=0.379，Spearman=0.649
- Model B（配置→log10 BER_MLSE，安全约束）：R²=0.242，Spearman=0.475

各环境测试 Spearman（Model A）：
| 环境 | n | Spearman |
| --- | --- | --- |
| Base_IL10 | 65 | 0.637 |
| CD_Sweep_15ps | 11 | 0.345 |
| CD_Sweep_28ps | 7 | 0.643 |
| Combined_Stress | 12 | 0.832 |
| DGD_Sweep_2ps | 12 | 0.238 |
| DGD_Sweep_5ps | 12 | 0.601 |
| IL_Sweep_14dB | 18 | 0.705 |
| IL_Worst_20dB | 12 | 0.692 |

## 图

### 收敛对比（8 用例同轴，便于横向比较）

![收敛对比](ddps_v2_20260907/report/fig_convergence_compare.png)

### 优化前后的 Tx FFE 抽头 / CTLE 设置

![抽头对比](ddps_v2_20260907/report/fig_taps_compare.png)

### seed→best 改善量汇总

![改善量](ddps_v2_20260907/report/ddps_v2_overview.png)

### 各用例节点细节（眼图/频谱/均衡电平，seed vs best）与逐级轨迹

| 用例 | 分析图（收敛+抽头+CTLE+FIR） | 节点图（眼图/频谱/均衡电平） | 逐级 trace |
| --- | --- | --- | --- |
| Base_IL10 | [PNG](ddps_v2_20260907/report/ddps_v2_case_Base_IL10_a.png) | [PNG](ddps_v2_20260907/report/ddps_v2_case_Base_IL10_b.png) | [csv](ddps_v2_20260907/trace_Base_IL10.csv) |
| IL_Sweep_14dB | [PNG](ddps_v2_20260907/report/ddps_v2_case_IL_Sweep_14dB_a.png) | [PNG](ddps_v2_20260907/report/ddps_v2_case_IL_Sweep_14dB_b.png) | [csv](ddps_v2_20260907/trace_IL_Sweep_14dB.csv) |
| IL_Worst_20dB | [PNG](ddps_v2_20260907/report/ddps_v2_case_IL_Worst_20dB_a.png) | [PNG](ddps_v2_20260907/report/ddps_v2_case_IL_Worst_20dB_b.png) | [csv](ddps_v2_20260907/trace_IL_Worst_20dB.csv) |
| CD_Sweep_15ps | [PNG](ddps_v2_20260907/report/ddps_v2_case_CD_Sweep_15ps_a.png) | [PNG](ddps_v2_20260907/report/ddps_v2_case_CD_Sweep_15ps_b.png) | [csv](ddps_v2_20260907/trace_CD_Sweep_15ps.csv) |
| CD_Sweep_28ps | [PNG](ddps_v2_20260907/report/ddps_v2_case_CD_Sweep_28ps_a.png) | [PNG](ddps_v2_20260907/report/ddps_v2_case_CD_Sweep_28ps_b.png) | [csv](ddps_v2_20260907/trace_CD_Sweep_28ps.csv) |
| DGD_Sweep_2ps | [PNG](ddps_v2_20260907/report/ddps_v2_case_DGD_Sweep_2ps_a.png) | [PNG](ddps_v2_20260907/report/ddps_v2_case_DGD_Sweep_2ps_b.png) | [csv](ddps_v2_20260907/trace_DGD_Sweep_2ps.csv) |
| DGD_Sweep_5ps | [PNG](ddps_v2_20260907/report/ddps_v2_case_DGD_Sweep_5ps_a.png) | [PNG](ddps_v2_20260907/report/ddps_v2_case_DGD_Sweep_5ps_b.png) | [csv](ddps_v2_20260907/trace_DGD_Sweep_5ps.csv) |
| Combined_Stress | [PNG](ddps_v2_20260907/report/ddps_v2_case_Combined_Stress_a.png) | [PNG](ddps_v2_20260907/report/ddps_v2_case_Combined_Stress_b.png) | [csv](ddps_v2_20260907/trace_Combined_Stress.csv) |

## 数据文件

- 用例汇总：`result/ddps_v2_20260907/case_summary.csv` / `.json`；对照汇总：`result/ddps_v2_control/case_summary.csv`
- 训练数据：`../dataset/ddps_v2_dataset_20260907_190819.csv`（748 行，含 env/il/cd/dgd/x_0~9/ffe_tap/ctle/log10_ber_mlse/tx_fir 列）
- 模型与指标：`../models/ddps_v2/meta.json`、`../models/ddps_v2_control/meta.json`
- 高符号数复核：`result/ddps_v2_20260907/report/deep_check.csv`

## 相关文档

- [`docs/06` DDPS v2 重做报告](../docs/06_DDPS_v2_Rerun.md)：v1 根因排查与修复清单
- [`docs/04` DDPS 架构](../docs/04_DDPS_Optimization.md) | [`docs/03` 排坑记录](../docs/03_Troubleshooting_History.md)
- v1 历史数据/模型/结果（本地目录，未入库）：`archive/20260904_ddps_v1_physical_pre_v2/`
