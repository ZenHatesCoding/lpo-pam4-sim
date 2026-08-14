# DDPS 数据驱动物理代理优化器 (Data-Driven Physical Surrogate)

[返回算法总览](README.md)

> [!NOTE]
> DDPS 是一条**完全离线**的“数据驱动”寻优路线。它把一个在线优化问题拆成两段：
> **Stage 1 负责“供给”（给出一个不错起点 + 两个代理模型），Stage 2 负责“下降”（在代理上做带安全约束的
> 梯度下降，不再回传真实 BER）**。核心是让第二阶段通过“优化发端指标”来“等效地优化收端 MLSE BER”。

## 1. 架构分工（这是本方案最关键的定位）

### Stage 1 —— 模型供给，而非“画全地图”

Stage 1 的目标**不是**“穷尽地形、找到全局最优”。真实地形是 9 维里的极窄谷底（实测全优化域 1000 个随机
样本 BER 全部 > 0.17，命中好解≈0），永远无法穷尽。Stage 1 真正要产出的是两样东西：

1. **一个“不错的起点” `x0`**：例如上一版已经能用的工作点（不必是全局最优）。
2. **两个白盒代理模型**：
   - **Model A（物理代理，寻优目标）**：`发端 7-tap 等效 FIR → log10(BER)`。输入是发端链路的物理等效冲激
     响应（`tx_channel_extract.py` 对 `Tx FFE → DAC → CTLE → PCB → MZM` 做单位冲激提取），不是冷冰冰的系数。
   - **Model B（安全代理，安全约束）**：`FFE 9-tap + CTLE → log10(BER)`，用于在下降过程中否决会“掉锁”的步子。

> Stage 1 在 `x0` 邻域采样，**只是为了训练这两个模型**，采样覆盖范围不代表“完整地图”。

### Stage 2 —— 带约束的梯度下降，且不回传真实 BER

从 `x0` 出发，在 **Model A** 上做 SLSQP 梯度下降：

- **目标**：`min Model_A(x)` —— 直接优化发端指标，等效地优化收端 MLSE BER。
- **约束**：`Model_B(x) ≤ 安全红线`（预测 BER 不越 `1e-2` 掉锁线）+ **信任域**（不跑出起点邻域，防代理在
  未采样区外推越界）。
- **不回传真实 MLSE_BER**：真实 BER 只被**记录**用于事后验证，**不参与**下一步的方向决策。

> 因此 Stage 2 是“真正的梯度下降”，而不是“在 Stage 1 见过的点附近挑一个”。理想情况下它能沿 Model A 的
> 梯度走到 **Stage 1 采样没见过的更优点**。

### “等效优化”原理

优化 `Model_A(x)`（发端指标）之所以能等效地优化收端 MLSE BER，是因为：信道、噪声、收端均衡都是固定的，
发端等效 FIR 唯一决定了收端信号质量。只要 Model A 的**相对排序**正确（哪个 x 更好），那么
`argmin_x Model_A ≈ argmin_x 真实BER`——哪怕 Model A 的绝对值偏乐观/悲观，下降方向仍是对的。

### 为什么需要信任域（本次发现的关键坑）

纯 Ridge 代理没有“不确定性”，SLSQP 会顺着代理的**外推误差**一路跑到未采样区（实测：从起点一路跳到
`post1=0.19` 的死区，代理预测 `7e-3`、真实却 `5.5e-2`）。解决办法是给 Stage 2 加**信任域**：SLSQP 边界
收紧到起点邻域（FFE `±0.10` / CTLE `±6 dB`），把下降约束在“模型见过、且预测可信”的范围内。

## 2. 跨 SNR 迁移

`1e-5` 量级应在 28 dB / 大点数下找，但**不必**为每个 SNR 重新建数据集重训模型。验证方式：用 26.5 dB 训练
的 Model A/B 引导下降，沿下降轨迹在 28 dB 深水回测——若 28 dB 真实 BER 也随下降而下降，说明模型的
**排序信息跨 SNR 可迁移**。若不可迁移，未来才考虑按链路条件（拓扑→插损→SNR，系统已知）分桶建数据集。

## 3. 代码现状 (Code Status)

- **代码路径**：
  - [`ddps_optimizer.py`](../../ddps_optimizer.py) — Stage1 采样/训练 + Stage2 信任域约束下降 + 跨 SNR 回测
  - [`dataset_generator.py`](../../dataset_generator.py) — 全局随机覆盖采样（可选死区数据）
  - [`train_surrogates.py`](../../train_surrogates.py) — 双 Ridge 代理训练
  - [`tx_channel_extract.py`](../../tx_channel_extract.py) — 发端 7-tap 物理 FIR 特征提取
- **底层架构**：纯 Numpy / Scipy / scikit-learn（Ridge），无黑盒。
- **状态**：离线极限冲刺组，与在线安全算法互补。

## 4. 测试方法与结果 (Test Method & Results)

### 测试方法

```bash
python ddps_optimizer.py --n-stage1-samples 600 --n-stage2-steps 25
```

也可通过 `config.xlsx` 的 `tx` 表设置 `optimizer_type = 'DDPS'` 后运行 `python optimize_tx.py` 一键触发。

### 结果客观指标

热身保真度（SNR 26.5 dB / 65,536 Symbols）：

| 指标 | 数值 | 说明 |
| --- | --- | --- |
| 起点 x0 | `1.69e-03` | Stage 1 供给的“不错起点” |
| Stage 1 采样最优 | `2.05e-03` | 邻域采样里的最优点（**不是** Stage 2 目标） |
| **Stage 2 最优（不回传）** | **`8.82e-04`** | 沿 Model A 梯度下降，**超出 Stage 1 地图** |
| Stage 2 最大（安全） | `9.27e-04` | 全程无掉锁 |
| 等效性 Spearman | `0.575` | Model A 预测 vs 真实 logBER 的秩相关 |

深水校验（SNR 28.0 dB / 1,048,576 Symbols）：

| 方案 | MLSE BER | 说明 |
| --- | --- | --- |
| 起点 x0 | `1.44e-03` | 初始次优点 |
| **DDPS（9D）** | **`8.95e-05`** | 16× 提升 |
| SHC 参考（9D） | `3.76e-05` | 基线 |
| SHC 参考（12D） | `3.76e-05` | 历史基线 |

**跨 SNR 迁移**：26.5 dB 训练的模型引导下降后，所有步在 26.5 dB 都收敛到 `~8.82e-04`（正确的“区域”），
但在 28 dB 深水下，这些点分化成 `8.95e-05` ~ `1.84e-04`（**区域级迁移成立、精细级不可迁移**）。这印证了：
模型能把你带进“对的盆地”，但盆地内部的精修需要 28 dB（或对应链路条件）的数据。

**代理质量**：Model A (S21→BER) 测试集 R²=`0.720`；Model B (Config→BER) 测试集 R²=`0.913`。

## 5. 日志 / 图 / Summary 记录规范（回答“该记录什么”）

记录内容围绕本方案要证明的四件事展开——**①超出地图 ②不崩 ③等效优化 ④跨 SNR 迁移**：

| 要证明的命题 | 记录什么 | 落在哪里 |
| --- | --- | --- |
| ① Stage 2 超出 Stage 1 地图 | Stage 1 采样最优 BER vs Stage 2 最优 BER；起点 x0 BER | summary 顶部 + 收敛图横向参考线 |
| ② 不崩（安全） | 每步 Model B 预测值 + 是否越安全红线；Stage 2 全程**最大真实 BER** | sim_log 逐步 trace + summary |
| ③ 等效优化（不回传） | 每步 Model A 预测值 vs **仅记录**的真实 BER；`Spearman(ModelA, 真实logBER)`；下降曲线两条线（预测 vs 真实） | 收敛图（双曲线）+ summary |
| ④ 跨 SNR 迁移 | 沿 26.5 dB 引导的下降轨迹，在 28 dB 深水回测的逐点 BER | sim_log + summary 迁移表 |

- **sim_log.txt**：逐步 `step | ModelA | ModelB | safe? | 真实MLSE(仅记录)` 全量 trace。
- **ddps_convergence.png**：真实 BER（实线）与 Model A 预测（虚线）随 step 变化，并画起点/Stage1最优参考线。
- **ddps_summary.md**：架构说明 + 上述四个命题的关键数字 + 深水校验对照表。
