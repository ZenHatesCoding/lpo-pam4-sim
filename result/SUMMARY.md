# eLPO PAM4 仿真平台 —— 结果总览（统一入口）

> 本文件是**全部结果与报告的唯一起点**：图、数据、模型、报告都从这里按链接跳转。请勿逐张翻图；先从下文"从哪看起"开始。

## 0. 从哪看起

1. 最新主结果跑批：**[`result/ddps_v2_20260907`](result/ddps_v2_20260907/report/_run_index.md)** —— 先看跑批索引与逐用例页，再看聚合图与指标报告。
2. 想一次看完所有用例的图与数字：逐用例页 [Base_IL10](result/ddps_v2_20260907/report/case_Base_IL10.md)、[IL_Sweep_14dB](result/ddps_v2_20260907/report/case_IL_Sweep_14dB.md)、[IL_Worst_20dB](result/ddps_v2_20260907/report/case_IL_Worst_20dB.md)、[CD_Sweep_15ps](result/ddps_v2_20260907/report/case_CD_Sweep_15ps.md)、[CD_Sweep_28ps](result/ddps_v2_20260907/report/case_CD_Sweep_28ps.md)、[DGD_Sweep_2ps](result/ddps_v2_20260907/report/case_DGD_Sweep_2ps.md)、[DGD_Sweep_5ps](result/ddps_v2_20260907/report/case_DGD_Sweep_5ps.md)、[Combined_Stress](result/ddps_v2_20260907/report/case_Combined_Stress.md)。
3. 想知道"单环境 vs 混合环境"的方法学答案：[result/ddps_v2_control 对照说明](result/ddps_v2_control/README.md)。

## 1. `result/` 目录导览（回答"0907 和 control 分别是啥、是否都要"）

| 目录 | 是什么 | 是否必须 | 原因 |
| --- | --- | --- | --- |
| `ddps_v2_20260907/` | **主实验（生产口径）**：混合环境锚定数据训练 `models/ddps_v2`，8 个应力环境冻结复用做 Stage-2 在线调优；含完整报告/图/逐用例页 | ✅ 必须 | 这是交付给甲方的最终结果 |
| `ddps_v2_control/` | **方法学对照**：只用基准环境数据训练 `models/ddps_v2_control`，同流程重跑，量化单点模型泛化衰减边界（证明修复有效 + 说明为何需要混合数据） | ⚠️ 建议保留 | 它是主结果成立的方法学证据（AGENTS.md 控制变量实验）；不需要可归档 |
| `ddps/`(历史) | v1 泛化测试产物 | ❌ 已归档 | 已移入 `archive/20260904_ddps_v1_physical_pre_v2/` |

## 2. 主结果（最新跑批）

- 跑批索引（推荐起点）：[result/ddps_v2_20260907/report/_run_index.md](result/ddps_v2_20260907/report/_run_index.md)
- 指标报告（口径/模型指标/根因表/深水复核）：[result/ddps_v2_20260907/report/ddps_v2_report.md](result/ddps_v2_20260907/report/ddps_v2_report.md)
- 聚合改善图：![overview](result/ddps_v2_20260907/report/ddps_v2_overview.png)

### 2.1 逐用例速览

| 用例 | 环境 | 种子 BER_MLSE | Stage-2 最优 | Δlog10 | 判定 | 详情页 |
| --- | --- | --- | --- | --- | --- | --- |
| [Base_IL10](result/ddps_v2_20260907/report/case_Base_IL10.md) | IL10dB | `5.53e-04` | `3.35e-04` | `-0.22` | ✅ 改善 | [case_Base_IL10.md](result/ddps_v2_20260907/report/case_Base_IL10.md) |
| [IL_Sweep_14dB](result/ddps_v2_20260907/report/case_IL_Sweep_14dB.md) | IL14dB | `2.08e-03` | `5.66e-04` | `-0.56` | ✅ 改善 | [case_IL_Sweep_14dB.md](result/ddps_v2_20260907/report/case_IL_Sweep_14dB.md) |
| [IL_Worst_20dB](result/ddps_v2_20260907/report/case_IL_Worst_20dB.md) | IL20dB | `5.82e-02` | `2.97e-03` | `-1.29` | ✅ 改善 | [case_IL_Worst_20dB.md](result/ddps_v2_20260907/report/case_IL_Worst_20dB.md) |
| [CD_Sweep_15ps](result/ddps_v2_20260907/report/case_CD_Sweep_15ps.md) | IL10dB+CD15 | `6.57e-04` | `3.35e-04` | `-0.29` | ✅ 改善 | [case_CD_Sweep_15ps.md](result/ddps_v2_20260907/report/case_CD_Sweep_15ps.md) |
| [CD_Sweep_28ps](result/ddps_v2_20260907/report/case_CD_Sweep_28ps.md) | IL10dB+CD28 | `6.94e-04` | `3.39e-04` | `-0.31` | ✅ 改善 | [case_CD_Sweep_28ps.md](result/ddps_v2_20260907/report/case_CD_Sweep_28ps.md) |
| [DGD_Sweep_2ps](result/ddps_v2_20260907/report/case_DGD_Sweep_2ps.md) | IL10dB+DGD2 | `4.42e-04` | `3.35e-04` | `-0.12` | ✅ 改善 | [case_DGD_Sweep_2ps.md](result/ddps_v2_20260907/report/case_DGD_Sweep_2ps.md) |
| [DGD_Sweep_5ps](result/ddps_v2_20260907/report/case_DGD_Sweep_5ps.md) | IL10dB+DGD5 | `4.71e-04` | `3.39e-04` | `-0.14` | ✅ 改善 | [case_DGD_Sweep_5ps.md](result/ddps_v2_20260907/report/case_DGD_Sweep_5ps.md) |
| [Combined_Stress](result/ddps_v2_20260907/report/case_Combined_Stress.md) | IL20dB+CD15+DGD5 | `7.72e-02` | `5.74e-03` | `-1.13` | ✅ 改善 | [case_Combined_Stress.md](result/ddps_v2_20260907/report/case_Combined_Stress.md) |

### 2.2 深水统计复核（262144 符号重测 seed/best）

| 用例 | seed (deep) | best (deep) | Δlog10 |
| --- | --- | --- | --- |
| Base_IL10 | `3.55e-04` | `1.65e-04` | `-0.33` |
| IL_Sweep_14dB | `1.82e-03` | `3.07e-04` | `-0.77` |
| IL_Worst_20dB | `5.76e-02` | `2.73e-03` | `-1.32` |
| CD_Sweep_15ps | `4.50e-04` | `1.67e-04` | `-0.43` |
| CD_Sweep_28ps | `3.95e-04` | `1.71e-04` | `-0.36` |
| DGD_Sweep_2ps | `2.72e-04` | `1.67e-04` | `-0.21` |
| DGD_Sweep_5ps | `2.99e-04` | `1.71e-04` | `-0.24` |
| Combined_Stress | `7.76e-02` | `5.78e-03` | `-1.13` |

## 3. 对照实验（单环境训练）

- 完整说明：[`result/ddps_v2_control/README.md`](result/ddps_v2_control/README.md)
- 一句话结论：修复后的管线即使只用基准数据也不负向（对比 v1），但极端环境的最优值比混合锚定模型差 4~10× —— 主结果采用混合锚定模型。

## 4. 数据与模型

- 训练数据集：`dataset/ddps_v2_dataset_*.csv`（本次 [`dataset/ddps_v2_dataset_20260907_190819.csv`](../dataset/ddps_v2_dataset_20260907_190819.csv)，748 点环境锚定邻域）
- 模型：[`models/ddps_v2/`](../models/ddps_v2/)（model_a.pkl / model_b.pkl / meta.json）；对照模型 [`models/ddps_v2_control/`](../models/ddps_v2_control/)
- 逐用例 trace：`result/ddps_v2_20260907/trace_<用例>.csv`；case 汇总 [`result/ddps_v2_20260907/case_summary.csv`](result/ddps_v2_20260907/case_summary.csv)

## 5. 历史归档与文档

- 历史（v1/修复前）数据、模型、结果：`archive/20260904_ddps_v1_physical_pre_v2/`（**本地磁盘目录**，仓库政策不入库；旧版内容仍保留在本分支 git 历史）
- [docs/06. DDPS v2 重做报告](../docs/06_DDPS_v2_Rerun.md) —— 根因/修正/结果总述
- [docs/04. DDPS 架构](../docs/04_DDPS_Optimization.md)、[docs/03. 排坑记录](../docs/03_Troubleshooting_History.md)
- [README（项目主页）](../README.md)

---

> 生成方式：`python make_result_index.py --run-dir <run> --model-dir <md> [--control-dir <ctrl>]`（幂等，只读产物文件，不重跑仿真）。
