# DDPS 数据驱动物理代理优化器 (Data-Driven Physical Surrogate)

[返回算法总览](README.md)

> [!NOTE]
> DDPS 是一条**完全离线**的“数据驱动”寻优路线：不依赖任何在线硬件反馈，而是先把试探全部搬到
> 离线仿真器里，采一批 `(发端配置 → 真实 MLSE BER)` 数据，训练白盒代理模型，再在代理上做有界寻优，
> 并通过“物理回验 + 主动学习”迭代下钻。它与在线安全算法（TuRBO-Safe / Surrogate_SHC）互补，
> 适合在量产前、无代价环境下做精细极限冲刺。

## 1. 原理与方案设计 (Principle & Scheme)

### 关键观察：好解谷底极窄

实测表明，该 LPO 链路的 Tx FFE 优化地形极其陡峭：在 9 维全优化域内做 **1000 个纯随机 LHS 采样，
BER 全部 > 0.17**（没有一个点低于 $10^{-2}$）。也就是说，“盲打”式全局随机采样根本无法命中好解。
因此 DDPS 采用**围绕已知工作点做邻域采样**的现实做法——与真实工程中“在当前工作点附近精细调优”一致。

### 双代理模型 (Dual Surrogate Models)

DDPS 采样后训练两个 **100% 白盒**的 Ridge(二阶多项式) 回归代理：

- **Model A — 物理代理 (S21 → BER)**：输入为发端等效 **7-tap T-spaced FIR**（由 `tx_channel_extract.py`
  对 `Tx FFE → DAC → CTLE → PCB → MZM` 整条发端链路做单位冲激响应提取）。模型“看见”的是真实物理波形形状，
  而非冷冰冰的系数，对链路畸变更具解释力与可迁移性。
- **Model B — 配置代理 (Config → BER)**：输入为 `9-tap FFE + CTLE` 原始配置，作为快速一致性校验。

寻优目标为两者集成：$\mathrm{obj} = 0.7 \cdot \text{ModelA} + 0.3 \cdot \text{ModelB}$。

### 主动学习下钻 (Active Learning)

1. **邻域采样**：以已知次优工作点为种子，在其邻域（FFE 游标 $\pm 0.05$、CTLE $\pm 3\,\mathrm{dB}$）
   用 LHS 采样，逐点跑白盒物理仿真；可选并入一份全局随机覆盖集，用于定义“死区惩罚”地形。
2. **代理寻优**：在代理上用 SLSQP（带边界约束）从当前最优点出发寻优，每 5 轮插入一次随机重启以防代理局部极小。
3. **物理回验**：把代理最优解下发到真实仿真器，得到真实 MLSE BER（忠实记录每一笔代价）。
4. **回灌重训**：把新样本 `(配置, 发端 FIR, 真实 BER)` 追加进数据集，重训代理，进入下一轮。

## 2. 代码现状 (Code Status)

- **代码路径**：
  - [`ddps_optimizer.py`](../../ddps_optimizer.py) — 邻域采样 + 主动学习主循环 + SLSQP 代理寻优
  - [`dataset_generator.py`](../../dataset_generator.py) — 全局随机覆盖采样（可选死区数据）
  - [`train_surrogates.py`](../../train_surrogates.py) — 双 Ridge 代理训练
  - [`tx_channel_extract.py`](../../tx_channel_extract.py) — 发端 7-tap 物理 FIR 特征提取
- **底层架构**：纯 Numpy / Scipy / scikit-learn（Ridge），无黑盒。
- **状态**：离线极限冲刺组，与在线安全算法互补。

## 3. 测试方法与结果 (Test Method & Results)

### 测试方法

```bash
# 直接运行（自动做邻域采样 → 训练代理 → SLSQP 主动学习 → DEEP_1E5 深水校验）
python ddps_optimizer.py --n-seed-samples 600 --n-iter 25
```

也可通过 `config.xlsx` 的 `tx` 表设置 `optimizer_type = 'DDPS'` 后运行 `python optimize_tx.py` 一键触发。

### 结果客观指标

在同口径深水校验（SNR 28.0 dB / 1,048,576 Symbols / 112G 模式）下：

| 方案 | MLSE BER | 说明 |
| --- | --- | --- |
| 种子点（初始次优） | `1.44e-03` | 两阶段实验的“初始次优点” |
| **DDPS（9D，本方案）** | **`4.81e-05`** | 物理 S21 代理 + SLSQP 主动学习，**30× 提升** |
| SHC 参考（9D） | `3.76e-05` | 已知基线（同 9D 口径） |
| SHC 参考（12D, fp2=0.9） | `3.76e-05` | 历史基线（12D 口径） |

- **代理质量**：Model A (S21→BER) 测试集 R² = `0.720`；Model B (Config→BER) 测试集 R² = `0.913`。
- **收敛行为**：SLSQP 在第 1 轮主动学习即从种子点下钻至物理极限底座 `7.20e-04`（热身保真度，SNR 26.5），
  后续 24 轮稳定守在该底座；深水校验对应 `4.81e-05`。
- **关键结论**：DDPS 在**完全离线**、且仅依赖发端物理 FIR 代理的情况下，从次优点出发收敛到与 SHC 基线
  同量级（1.3× 以内）的物理极限，验证了“数据驱动物理代理”路线的可行性。

## 4. 用法 (Usage)

- 关键参数：
  - `--n-seed-samples`：种子邻域采样点数（越大代理越准）。
  - `--n-iter`：主动学习迭代轮数。
  - `--dataset`：可选全局覆盖数据集 CSV（由 `dataset_generator.py` 生成）。
  - `deep_validate=True`：结束时自动切换到 `DEEP_1E5`（SNR 28 dB、1M Symbols）与已知基线做同口径对比。
- 种子点与邻域幅值可通过 `ddps_optimizer.py` 顶部的 `SEED_TAPS / SEED_CTLE / FFE_SPREAD / CTLE_SPREAD` 调整。
