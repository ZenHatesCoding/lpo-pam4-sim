# DDPS v2 结果：只用 10dB 基线训练，冻结模型跨环境泛化（BER_MLSE）

核心实验：只采集 **Base_IL10 邻域 321 点**（320 采样 + 1 种子；10dB 插损，CD/DGD=0）训练一套白盒代理模型并**冻结**；把同一个模型直接用于 8 个漂移环境（IL 14/20 dB、CD 15/28 ps/nm、DGD 2/5 ps、IL20+CD15+DGD5 复合）的 Stage-2 在线调优。测试全程**没有任何一步重新采样或重训**，模型从未见过这些环境的数据。结果：8 个环境真实 BER_MLSE **全程无一步劣于种子**（对比 v1 同场景是负向发散），其中 20 dB 插损 `5.8e-2 → 1.5e-2`（约 ×4），复合应力 `7.7e-2 → 3.5e-2`（约 ×2），其余 IL10 族环境收敛到约 `3.4–3.6e-4`。

**评估口径**：Rx 22-tap LMS FFE（无 DFE）→ MLSE（memory=1，Burg 白化），输出为 BER_MLSE；每点 131072 符号、固定随机种子；Stage-2 只依据代理模型，真实 BER 仅记录、不参与方向决策。

## 训练 / 测试分工（测试环境从未进过训练集）

| 实验 | 目录 | 训练数据 | 模型 | 测试 | 角色 |
| --- | --- | --- | --- | --- | --- |
| 只用基线训练 → 跨环境泛化 | [`result/ddps_v2_control`](ddps_v2_control) | 321 行 = Base_IL10 邻域 320 + 种子 1（只含 IL10、CD0、DGD0；来自总 csv 过滤 `env==Base_IL10`） | [`models/ddps_v2_control/`](../models/ddps_v2_control/) | 同一模型冻结，8 个漂移环境 逐个 Stage-2，零重训/零校准 | **本页主角（真·泛化）** |
| 带环境锚点训练（上限参考） | [`result/ddps_v2_20260907`](ddps_v2_20260907) | 748 行 = Base_IL10 320 + 其余 7 环境各 60 + 每环境种子 1（把少量目标环境邻域样本放进训练集） | [`models/ddps_v2/`](../models/ddps_v2/) | 同样单模型冻结、测试零重训 | 参考/校准式上界，**非严格泛化**（测试环境已被建模见过） |

两实验差别只有训练集构成；模型结构/超参、种子 x0、8 个测试用例、评估代码与 131072 符号协议完全相同。下表与图以“只用基线训练”为主。

## 核心结果：只用基线训练 → 跨环境泛化

| 用例（环境） | 种子 BER_MLSE | Stage-2 最优 (step) | Δlog10 | 改善× | 深水复核最优 (262144 sym) |
| --- | --- | --- | --- | --- | --- |
| Base_IL10 (IL10dB) | `5.53e-04` | `3.55e-04` (step 2) | `-0.19` | ×1.6 | `1.78e-04` |
| IL_Sweep_14dB (IL14dB) | `2.08e-03` | `5.49e-04` (step 10) | `-0.58` | ×3.8 | `2.76e-04` |
| IL_Worst_20dB (IL20dB) | `5.82e-02` | `1.47e-02` (step 23) | `-0.60` | ×3.9 | `1.58e-02` |
| CD_Sweep_15ps (IL10dB+CD15) | `6.57e-04` | `3.55e-04` (step 2) | `-0.27` | ×1.8 | `1.78e-04` |
| CD_Sweep_28ps (IL10dB+CD28) | `6.94e-04` | `3.55e-04` (step 2) | `-0.29` | ×2.0 | `1.80e-04` |
| DGD_Sweep_2ps (IL10dB+DGD2ps) | `4.42e-04` | `3.55e-04` (step 2) | `-0.09` | ×1.2 | `1.73e-04` |
| DGD_Sweep_5ps (IL10dB+DGD5ps) | `4.71e-04` | `3.59e-04` (step 2) | `-0.12` | ×1.3 | `1.73e-04` |
| Combined_Stress (IL20dB+CD15+DGD5ps) | `7.72e-02` | `3.48e-02` (step 22) | `-0.35` | ×2.2 | `3.63e-02` |

每行 Stage-2 全程真实 BER_MLSE 都记录在 trace csv 中，**任意一步未劣于种子**。IL10 族环境收敛到同一 ~3.4–3.6e-4 平台；高插损与复合环境（模型纯外推）改善 约 2–4×，方向仍正确、幅度受外推限制。

## 对比：若把少量目标环境样本也放进训练（上限参考）

| 用例 | 种子 | 只用基线（本页核心） | 带锚点训练 | 锚点带来的额外增益 |
| --- | --- | --- | --- | --- |
| Base_IL10 | `5.53e-04` | `3.55e-04` (×1.6) | `3.35e-04` (×1.7) | 再优 1.1× |
| IL_Sweep_14dB | `2.08e-03` | `5.49e-04` (×3.8) | `5.66e-04` (×3.7) | 再优 1.0× |
| IL_Worst_20dB | `5.82e-02` | `1.47e-02` (×3.9) | `2.97e-03` (×19.6) | 再优 5.0× |
| CD_Sweep_15ps | `6.57e-04` | `3.55e-04` (×1.8) | `3.35e-04` (×2.0) | 再优 1.1× |
| CD_Sweep_28ps | `6.94e-04` | `3.55e-04` (×2.0) | `3.39e-04` (×2.0) | 再优 1.0× |
| DGD_Sweep_2ps | `4.42e-04` | `3.55e-04` (×1.2) | `3.35e-04` (×1.3) | 再优 1.1× |
| DGD_Sweep_5ps | `4.71e-04` | `3.59e-04` (×1.3) | `3.39e-04` (×1.4) | 再优 1.1× |
| Combined_Stress | `7.72e-02` | `3.48e-02` (×2.2) | `5.74e-03` (×13.4) | 再优 6.1× |

解读：锚点变体仍是单模型、测试零重训，只是把少量目标环境邻域样本放进训练集，因而不是严格泛化结论，只回答“若允许少量目标环境标定数据，极端环境还能压多少”：IL20 从 `1.5e-2 → 3.0e-3`，复合应力从 `3.5e-2 → 5.7e-3`。方法学结论以本页核心实验（只用基线训练）为准。

## 冻结模型指标（基线训练，测试集 holdout）

- Model A（Tx FIR → log10 BER_MLSE，寻优方向）：R²=0.241，Spearman=0.497
- Model B（配置 → log10 BER_MLSE，安全约束）：R²=0.186，Spearman=0.399

## 图

### 基线泛化收敛（8 用例同轴对比）

![convergence](ddps_v2_control/report/fig_convergence_compare.png)

### 基线泛化：优化前后 Tx FFE 抽头 / CTLE

![taps](ddps_v2_control/report/fig_taps_compare.png)

### 基线 vs 带锚点：改善量对照（绿=只用基线，核心）

![delta compare](ddps_v2_control/report/fig_delta_compare.png)

### 逐用例：数据与节点图

| 用例 | 基线模型（核心） | 带锚点模型（参考） |
| --- | --- | --- |
| Base_IL10 | [收敛/抽头/CTLE/FIR 图](ddps_v2_control/report/ddps_v2_case_Base_IL10_a.png) · [眼图/频谱](ddps_v2_control/report/ddps_v2_case_Base_IL10_b.png) · [trace](ddps_v2_control/trace_Base_IL10.csv) | [图](ddps_v2_20260907/report/ddps_v2_case_Base_IL10_a.png) · [trace](ddps_v2_20260907/trace_Base_IL10.csv) |
| IL_Sweep_14dB | [收敛/抽头/CTLE/FIR 图](ddps_v2_control/report/ddps_v2_case_IL_Sweep_14dB_a.png) · [眼图/频谱](ddps_v2_control/report/ddps_v2_case_IL_Sweep_14dB_b.png) · [trace](ddps_v2_control/trace_IL_Sweep_14dB.csv) | [图](ddps_v2_20260907/report/ddps_v2_case_IL_Sweep_14dB_a.png) · [trace](ddps_v2_20260907/trace_IL_Sweep_14dB.csv) |
| IL_Worst_20dB | [收敛/抽头/CTLE/FIR 图](ddps_v2_control/report/ddps_v2_case_IL_Worst_20dB_a.png) · [眼图/频谱](ddps_v2_control/report/ddps_v2_case_IL_Worst_20dB_b.png) · [trace](ddps_v2_control/trace_IL_Worst_20dB.csv) | [图](ddps_v2_20260907/report/ddps_v2_case_IL_Worst_20dB_a.png) · [trace](ddps_v2_20260907/trace_IL_Worst_20dB.csv) |
| CD_Sweep_15ps | [收敛/抽头/CTLE/FIR 图](ddps_v2_control/report/ddps_v2_case_CD_Sweep_15ps_a.png) · [眼图/频谱](ddps_v2_control/report/ddps_v2_case_CD_Sweep_15ps_b.png) · [trace](ddps_v2_control/trace_CD_Sweep_15ps.csv) | [图](ddps_v2_20260907/report/ddps_v2_case_CD_Sweep_15ps_a.png) · [trace](ddps_v2_20260907/trace_CD_Sweep_15ps.csv) |
| CD_Sweep_28ps | [收敛/抽头/CTLE/FIR 图](ddps_v2_control/report/ddps_v2_case_CD_Sweep_28ps_a.png) · [眼图/频谱](ddps_v2_control/report/ddps_v2_case_CD_Sweep_28ps_b.png) · [trace](ddps_v2_control/trace_CD_Sweep_28ps.csv) | [图](ddps_v2_20260907/report/ddps_v2_case_CD_Sweep_28ps_a.png) · [trace](ddps_v2_20260907/trace_CD_Sweep_28ps.csv) |
| DGD_Sweep_2ps | [收敛/抽头/CTLE/FIR 图](ddps_v2_control/report/ddps_v2_case_DGD_Sweep_2ps_a.png) · [眼图/频谱](ddps_v2_control/report/ddps_v2_case_DGD_Sweep_2ps_b.png) · [trace](ddps_v2_control/trace_DGD_Sweep_2ps.csv) | [图](ddps_v2_20260907/report/ddps_v2_case_DGD_Sweep_2ps_a.png) · [trace](ddps_v2_20260907/trace_DGD_Sweep_2ps.csv) |
| DGD_Sweep_5ps | [收敛/抽头/CTLE/FIR 图](ddps_v2_control/report/ddps_v2_case_DGD_Sweep_5ps_a.png) · [眼图/频谱](ddps_v2_control/report/ddps_v2_case_DGD_Sweep_5ps_b.png) · [trace](ddps_v2_control/trace_DGD_Sweep_5ps.csv) | [图](ddps_v2_20260907/report/ddps_v2_case_DGD_Sweep_5ps_a.png) · [trace](ddps_v2_20260907/trace_DGD_Sweep_5ps.csv) |
| Combined_Stress | [收敛/抽头/CTLE/FIR 图](ddps_v2_control/report/ddps_v2_case_Combined_Stress_a.png) · [眼图/频谱](ddps_v2_control/report/ddps_v2_case_Combined_Stress_b.png) · [trace](ddps_v2_control/trace_Combined_Stress.csv) | [图](ddps_v2_20260907/report/ddps_v2_case_Combined_Stress_a.png) · [trace](ddps_v2_20260907/trace_Combined_Stress.csv) |

## 数据文件

- 总数据集：[`../dataset/ddps_v2_dataset_20260907_190819.csv`](../dataset/ddps_v2_dataset_20260907_190819.csv)（748 行：Base 321 + 7 环境锚点各 61）
- 基线模型只用其中 `env==Base_IL10` 的 321 行；锚点模型用全部 748 行
- 基线实验汇总：[`case_summary.csv`](ddps_v2_control/case_summary.csv)，逐级轨迹 `trace_<用例>.csv`（ddps_v2_control/ 下，每用例一个文件），深水复核 [`deep_check.csv`](ddps_v2_control/report/deep_check.csv)
- 锚点实验汇总：[`case_summary.csv`](ddps_v2_20260907/case_summary.csv)，深水复核 [`deep_check.csv`](ddps_v2_20260907/report/deep_check.csv)

## 相关文档

- [`docs/06` DDPS v2 重做报告](../docs/06_DDPS_v2_Rerun.md)：v1 根因、修复清单与两组实验的方法学说明
- [`docs/04` DDPS 架构](../docs/04_DDPS_Optimization.md) | [`docs/03` 排坑记录](../docs/03_Troubleshooting_History.md)
- v1 历史数据/模型/结果（本地目录，未入库）：`archive/20260904_ddps_v1_physical_pre_v2/`
