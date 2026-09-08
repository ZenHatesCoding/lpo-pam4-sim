# DDPS v2 全链路重做报告（数据收集 → 训练 → 在线调优泛化测试）

> 本报告与历史版本隔离存放；历史归档见 `archive/20260904_ddps_v1_physical_pre_v2/`（旧数据/模型/结果不参与本报告）。

## 0. 指标口径（BER_MLSE）

- 收端算法：Rx 22-tap T-spaced LMS FFE（DFE=0）→ **MLSE**（Viterbi，memory=1，Burg AR 白化）。当前配置 `mlse_memory=1`，平台所有误码率均为此 MLSE 判决输出（Gray 映射，BER≈SER/2）。
- 因此链路终极指标统一记作 **`BER_MLSE`**（对数域 `log10(BER_MLSE)`）；Stage-2 全程"所测即所发生"，凡下发的系数均记录真实 BER（含最差步）。
- 评估协议：PAM4 131072 符号/点，固定种子（Tx=42，噪声=123）；统计复核见第 4 节更高符号数重测。

## 1. v1 失败根因与 v2 修正（代码层面，已逐一落地）

| # | 根因 | v1 现象 | v2 修正 |
| --- | --- | --- | --- |
| 1 | Stage-1 邻域采样死代码 | LHS 采样器 `d=9` 却索引 `sp[i,9]`，首样本 IndexError，邻域数据从未生成 | `d=10` 修复；由 `dataset_generator.py`统一生成"环境锚定邻域"数据 |
| 2 | FFE 参数化错配 | 数据主抽头恒=1.0；下降空间主抽头=1−Σ|旁瓣|≈0.61，训练域与下降域错位，Model B 完全外推 | 全局统一 `主抽头=1−Σ|旁瓣|`（Σ|taps|≡1，Tx FFE 归一化恒等） |
| 3 | Tx-FIR 探针对齐错误 | S4P 频率缩放随 IL 改变群时延（实测峰值 idx：IL10=1247 vs IL20=238），进程级粘滞锁使跨环境 FIR 在错误符号格采样 → Model A 输入 OOD/趋平 | 对齐基准按"环境"缓存（透传冲激 argmax），训练/在线/跨进程一致 |
| 4 | Stage-2 无梯度门控 | 代理曲面在外推区趋平（|g|~1e-4）仍沿拟合噪声下降 → 真实 BER_MLSE 反向爬升（负向优化） | `|∇ModelA| < 0.05` 即停，不进入无效区乱走 |
| 5 | 模型 pickle 依赖 `__main__` | v1 pkl 无法跨脚本加载 | `train_v2` 以模块路径安全序列化；`load_models()` 兼容旧档 |
| 6 | 报告口径 | docs 声称"彻底告别发散"，result 结论却相反；命名混乱 | 统一 BER_MLSE 口径，报告按实测逐项撰写 |

## 2. 数据集与训练

- 数据：环境锚定邻域采样（每点真实 BER_MLSE），覆盖信任域 FFE ±0.1 / CTLE ±3.0 dB；n_train=257, n_test=64
- 数据文件：`dataset\ddps_v2_Base_IL10_only_control.csv`；标签列：`log10_ber_mlse`
- **Model A**（Tx 7-tap FIR → log10 BER_MLSE，寻优目标）：Test R²=0.241, Spearman=0.497
- **Model B**（FFE+CTLE 配置 → log10 BER_MLSE，安全约束）：Test R²=0.186, Spearman=0.399
- 两模型均为手写二阶多项式 Ridge（闭式解，纯 numpy）；寻优只依赖排序/方向，Spearman 为主评估指标。

Model A 测试集按环境划分的 Spearman（各环境锚点 holdout）：
| 环境 | n_test | Spearman |
| --- | --- | --- |
| Base_IL10 | 64 | 0.497 |

## 3. 泛化测试结果（模型冻结复用，逐环境 Stage-2 在线调优）

| 用例 | 种子 BER_MLSE | Stage-2 最优 (步) | Δlog10 | 步数 | 判定 | 轨迹一致性 |
| --- | --- | --- | --- | --- | --- | --- |
| Base_IL10 | `5.53e-04` | `3.55e-04` (step 2) | `-0.19` | 25 | ✅ 改善 | 0.47 |
| IL_Sweep_14dB | `2.08e-03` | `5.49e-04` (step 10) | `-0.58` | 25 | ✅ 改善 | 0.87 |
| IL_Worst_20dB | `5.82e-02` | `1.47e-02` (step 23) | `-0.60` | 25 | ✅ 改善 | 0.97 |
| CD_Sweep_15ps | `6.57e-04` | `3.55e-04` (step 2) | `-0.27` | 25 | ✅ 改善 | 0.47 |
| CD_Sweep_28ps | `6.94e-04` | `3.55e-04` (step 2) | `-0.29` | 25 | ✅ 改善 | 0.53 |
| DGD_Sweep_2ps | `4.42e-04` | `3.55e-04` (step 2) | `-0.09` | 25 | ✅ 改善 | 0.47 |
| DGD_Sweep_5ps | `4.71e-04` | `3.59e-04` (step 2) | `-0.12` | 25 | ✅ 改善 | -0.12 |
| Combined_Stress | `7.72e-02` | `3.48e-02` (step 22) | `-0.35` | 25 | ✅ 改善 | 0.98 |

> 轨迹一致性 = 收敛轨迹上 Model A 预测与真实 BER_MLSE 的 Spearman（越接近 1 方向越准）。真实 BER 只记录、不参与方向决策。

## 4. 统计复核（更高符号数重测 seed/best）

| 用例 | seed BER_MLSE (deep) | best BER_MLSE (deep) | Δlog10 (deep) |
| --- | --- | --- | --- |
| Base_IL10 | `3.55e-04` | `1.78e-04` | `-0.30` |
| IL_Sweep_14dB | `1.82e-03` | `2.76e-04` | `-0.82` |
| IL_Worst_20dB | `5.76e-02` | `1.58e-02` | `-0.56` |
| CD_Sweep_15ps | `4.50e-04` | `1.78e-04` | `-0.40` |
| CD_Sweep_28ps | `3.95e-04` | `1.80e-04` | `-0.34` |
| DGD_Sweep_2ps | `2.72e-04` | `1.73e-04` | `-0.20` |
| DGD_Sweep_5ps | `2.99e-04` | `1.73e-04` | `-0.24` |
| Combined_Stress | `7.76e-02` | `3.63e-02` | `-0.33` |

## 5. 图件索引

- `ddps_v2_overview.png`：各用例 seed→best 改善量
- `ddps_v2_case_<用例>_a.png`：收敛轨迹(真实/Model A/Model B) + Tx FFE 抽头 + Tx CTLE 频率响应 + Tx FIR 探针（优化前后对照）
- `ddps_v2_case_<用例>_b.png`：seed vs best 的 Tx 模拟眼图、Rx ADC 输入眼图、Rx FFE 均衡电平/直方图、功率谱
- `case_summary.csv/.json`、`trace_*.csv`：全部数值可审计
