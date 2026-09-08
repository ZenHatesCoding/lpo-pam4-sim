# 06. DDPS v2 全链路重做报告（数据收集 → 训练 → 在线调优泛化）

[🔙 返回主页](../README.md)

> 本文件是 **v2 修正后的正式结果页**。v1（物理模型修复前）出现“Model A 下降但真实 BER 反向变差”
> 的负向优化现象，根因排查结论、修正清单与最终结果见下文。历史数据/模型/结果完整归档于
> `archive/20260904_ddps_v1_physical_pre_v2/`（本分支 git 历史与 `origin/physical-model` 亦保留旧版）。
>
> **📊 结果与图件索引：[`result/SUMMARY.md`](../result/SUMMARY.md)** —— 主实验 vs 对照实验的
> 数据区别、8 用例横向对比表与全部图/数据链接。

---

## 1. v1 失败根因（代码层面，均已修复并验证）

| # | 根因 | 现象 | 证据 |
| --- | --- | --- | --- |
| 1 | **Stage-1 邻域采样是死代码** | `ddps_optimizer._stage1_collect` 中 LHS 采样器维度 `d=9` 却索引 `sp[i,9]`，首个样本即 `IndexError`；v1 模型实际只由全优化域数据集训练 | 逐行复现：`CRASH: IndexError index 9 out of bounds ... size 9` |
| 2 | **FFE 主抽头参数化不一致** | 数据生成时主抽头恒置 `1.0`；Stage-2 下降空间主抽头 `=1−Σ|旁瓣|`（种子 ≈0.609）。Model B（安全模型）在种子邻域完全处于训练域之外 | 数据与代码比对：两数据集 `ffe_tap_4 ≡ 1.0`；种子 0.609 在其外 |
| 3 | **Tx-FIR 探针跨环境符号格错位** | S4P 为匹配不同目标插损做频率缩放，群时延随 IL 剧烈漂移（实测单位脉冲峰值 idx：IL10=`1247` vs IL20=`238`）；旧代码把首个探测的峰值永久粘滞在进程里 → 跨环境复用（test_generalization 顺序跑 8 用例）时 FIR 特征在**错误符号格**上采样 | 本仓库诊断实验复现上述 idx；修复后 FIR 特征在 IL10/IL14/IL20/CD/DGD 均正确对齐 |
| 4 | **Stage-2 无梯度门控** | 代理曲面在外推区趋平（|∇ModelA|≈6.6e-4，比有效区小 6000×），仍沿拟合噪声做归一化下降 → 真实 BER 单调爬升（IL20: 5.8e-2→9.0e-2） | 旧路径 trace：`IL_Worst_20dB` 7 步真实 BER 5.92e-2→9.01e-2，Model A 预测纹丝不动 |
| 5 | 模型 pickle 依赖 `__main__` | 历史 pkl 无法跨脚本加载 | 见 v1 归档 pkl |
| 6 | 报告口径混乱 | `docs/04` 曾声称“彻底告别发散”，同期 `result/ddps` 结论却写明发散；summary 表文矛盾；命名不一 | 归档文件互证 |

> 第 3 条是“看着像恰好反过来”的最直接原因：跨环境时 Model A 的输入特征根本不在正确的
> 符号网格上，等于喂给代理的是一堆与其训练分布无关的数值 —— 模型既无法正确排序、局部
> 曲面又趋平，梯度下降自然变成负向随机游走。

## 2. v2 修正清单

1. `dataset_generator.py` 重写：**环境锚定邻域采样**（基准环境密集 + 各应力环境锚点），
   FFE 参数化全局统一为 `主抽头=1−Σ|旁瓣|`（信任域内 Σ|taps|≡1，Tx FFE 归一化为恒等）。
2. `ddps_optimizer.py`：LHS `d=10` 修复；新增 **梯度门控** `|∇ModelA| < 0.05 即停`；
   安全裕度 `SAFETY_MARGIN` 0.3→0.6（v2 实测标定：0.3 会在真实 BER 仍在改善时过早刹车）。
3. `tx_channel_extract.py` 重构：符号格对齐基准**按物理信道环境缓存**（透传冲激 argmax），
   训练/在线/跨进程/跨环境一致。
4. `train_surrogates.py`：`train_v2()`/`load_models()`；R² 之外增加 **Spearman（排序/方向）**
   评估并按环境拆分；模型以模块路径安全序列化。
5. `test_generalization.py` 重写：冻结模型逐环境 Stage-2 在线调优 + 每环境邻域云校验
   （仅离线记录、不回传）+ trace/case 数值落盘。
6. `report_ddps_v2.py`：收敛轨迹、Tx FFE 抽头、Tx CTLE |H(f)|、Tx-FIR 探针、眼图、
   频谱、Rx FFE 均衡电平、中文 summary、深水统计复核。

## 3. v2 结果（评估协议：PAM4 131072 符号/点，固定种子；指标 = BER_MLSE）

| 用例 | 环境 | 种子 BER_MLSE | Stage-2 最优 | 改善倍数 | Δlog10 |
| --- | --- | --- | --- | --- | --- |
| Base_IL10 | IL10 | `5.53e-4` | `3.35e-4`（step4） | ×1.65 | −0.22 |
| IL_Sweep_14dB | IL14 | `2.08e-3` | `5.66e-4`（step5） | ×3.7 | −0.56 |
| IL_Worst_20dB | IL20 | `5.82e-2` | `2.97e-3`（step7） | ×19.6 | −1.29 |
| CD_Sweep_15ps | IL10+CD15 | `6.57e-4` | `3.35e-4`（step5） | ×2.0 | −0.29 |
| CD_Sweep_28ps | IL10+CD28 | `6.94e-4` | `3.39e-4`（step6） | ×2.0 | −0.31 |
| DGD_Sweep_2ps | IL10+DGD2 | `4.42e-4` | `3.35e-4`（step4） | ×1.32 | −0.12 |
| DGD_Sweep_5ps | IL10+DGD5 | `4.71e-4` | `3.39e-4`（step4） | ×1.39 | −0.14 |
| Combined_Stress | IL20+CD15+DGD5 | `7.72e-2` | `5.74e-3`（step9） | ×13.4 | −1.13 |

- **8/8 用例全程真实 BER_MLSE 无任何一步劣于种子**（“所测即所发生”全记录），负向优化现象消失；
  高应力用例（20 dB 插损、复合应力）获益最大（约 13~20×）。
- 收敛轨迹上 Model A 预测与真实 BER 的方向一致（最恶劣复合用例轨迹一致性 Spearman=0.99）。
- 统计复核：`result/ddps_v2_20260907/report/deep_check.csv`（262144 符号重测 seed/best）。

## 4. 产物位置（与历史隔离）

- 数据集：`dataset/ddps_v2_dataset_20260907_190819.csv`
- 模型：`models/ddps_v2/`（`model_a.pkl` / `model_b.pkl` / `meta.json`）
- 泛化测试：`result/ddps_v2_20260907/`（`case_summary.csv/.json` + `trace_*.csv` + `model_meta_snapshot.json`）
- 可视化报告：`result/ddps_v2_20260907/report/`（`ddps_v2_report.md`、`ddps_v2_overview.png`、
  各用例 `ddps_v2_case_*_a/_b.png`、`deep_check.csv`）
- 根因诊断脚本与证据（v1 复现）：`scratch/diag_*.py` + `scratch/diag_*_evidence*.csv`

## 5. 方法论说明

- 训练：**混合环境锚定**数据（基准环境密集 + 各应力环境稀疏锚点），单组冻结模型；
  遵循 AGENTS.md 控制变量法 —— 评估阶段绝不针对用例重采样/重训。
- Stage-2 底线不变：方向只来自 Model A（发端物理探针 7-tap FIR）；安全由 Model B 相对红线
  + 信任域 + 梯度门控保证；真实 BER_MLSE 只记录不参与决策。

### 5.1 单环境训练对照（衰减边界）

为回答"单点模型能否直接泛化、是否必须混合环境"（AGENTS.md 方法论问题），用**仅基准环境
(Base_IL10) 数据**训练的同一套流程重跑（`run_ddps_v2_control.py`）：

| 用例 | 种子 BER_MLSE | 单环境模型最优 | 混合锚定模型最优 |
| --- | --- | --- | --- |
| Base_IL10 | `5.53e-4` | `3.55e-4` | `3.35e-4` |
| IL_Sweep_14dB | `2.08e-3` | `5.49e-4` | `5.66e-4` |
| IL_Worst_20dB | `5.82e-2` | `1.47e-2` | `2.97e-3` |
| Combined_Stress | `7.72e-2` | `3.48e-2` | `5.74e-3` |

结论：修复后的管线**即使只用基准环境数据也不会负向优化**（单环境模型 8/8 用例仍全程改善，
因为参数化、探针对齐、梯度门控等实现层错误已修）；但在 20 dB 插损等极端环境，单环境模型的
FIR→BER 外推明显衰减，混合环境锚点可将最优结果再提升 4~10× —— 这量化回答了
"物理噪声主导下需要混合环境数据" 的问题。

[🔙 返回主页](../README.md)
