# 09. DDPS v5 模型与算法口径

> 本版是 v4 之后**修复"预测降/实测升"的版本**。先读 [08. DDPS v4](08_DDPS_v4_Model_Update.md)
> 了解 v4 的链路口径与失败现象，再读本文件看根因与修法。

## 1. 一句话现状

DDPS v5：链路口径与 v4 完全一致（CTLE 在 Tx 电插损之后、Driver 之前；driver_gain 可调
×0.30~×4.00；无 VGA、无 RMS 归一化）。**唯一改变的是 gain 维的处理方式**：

- **v4（失败）**：gain 维交给基线训练的代理梯度盲驱。代理对 gain 的梯度永远是"降 gain"
  （基线最优是降 gain），于是在 IL20x20 等恶劣环境把 gain 反方向驱动，造成"预测降、实测升"。
- **v5（修复）**：gain 维**不进代理**。每步用发端指标（MZM 输入端 RMS，发端可测、不需 BER）
  把 gain 解析调到目标摆幅 `TARGET_DRIVE_RMS = 0.14 V`。FFE/CTLE 成形仍走基线代理泛化。

## 2. 根因：v4 为什么"做不出来"是真的没做好

### 2.1 决定性证据：gain 维的最优方向随环境反转

固定种子 FFE/CTLE，扫 gain 倍率（`scratch/diag_gain_sweep.py`，262144 符号 × 3 种子）：

| 环境 | 最优 ratio | 方向 | 物理含义 |
| --- | --- | --- | --- |
| Base_IL10x10 | 0.65 | 降 gain | 信号强，降 gain 防 MZM 削顶 |
| IL14x14 | 0.65 | 降 gain | 同上 |
| **IL20x20** | **1.30** | **升 gain** | 信号弱，升 gain 补摆幅 |
| IL20x10_TxHeavy | 0.80~1.00 | 基本不动 | |
| IL10x20_RxHeavy | 0.65 | 降 gain | |

**基线训练的代理对 gain 的梯度永远是"降 gain"**（因为基线最优是降 gain），但 IL20x20 最优是
**升 gain** → 代理在 IL20x20 把 gain 维**反方向驱动**。

### 2.2 v4 的 divergence.csv 直接抓现行

`result/ddps_v4_divergence.csv` 的 `corr_pred_real` 列（预测下降 vs 实测下降的相关）：

- 基线/低插损/色散/噪声类（信号不弱）：corr **正**（0.73~0.99），方向对 → 改善
- **IL20x20、Comb_IL20x20、HighNoise_IL16x16、Comb_IL20x10**：corr **负**（−0.35~−0.59），方向反了 → 变差

且模型对所有 case 预测的下降总量都是 **−0.294 dex**（完全相同），因为 v4 模型输入 x 里
**没有任何信道信息**，它对每个环境吐的是**同一条基线轨迹**。

### 2.3 为什么 v2/v3 能成

v2/v3 同样只训练基线、模型同样信道盲，却全部 case 改善——**因为 gain 被锁死**，只有跨环境
泛化的 FFE/CTLE 成形在动。所以"训练看不到恶劣信道"作为"做不出来"的理由**是错的**：
问题不在缺信道信息，而在 v4 把"方向随环境反转的 gain 维"交给了信道盲的代理。

## 3. 修法：gain 维发端 RMS 物理目标驱动

### 3.1 物理机制

链路里 `x = x * driver_gain`（gain 是 Tx 前端最后的线性乘子），所以 MZM 输入端 RMS
`drive_rms ∝ gain`（实测在固定 FFE/CTLE 下 `rms/gain` 为常数 k）。给定目标 RMS：

```
gain_target = gain_ref * (target_rms / rms_ref)      # 一次发端测量即可标定 k
```

### 3.2 目标 RMS 的设计：全环境扫描标定（不是拍脑袋）

`scratch/scan_env_optimal.py` 在 15 环境 × (gain, gDC, gDC2) 网格扫描（65536 符号快速筛选），
找到每个环境最优点的 drive_rms 分布在 0.09~0.18 V。关键发现：

**固定 target_rms = 0.14 V 时，因 k 随 IL 变化，解析出的 gain 倍率自动从强信号环境的 ~0.8
调到弱信号环境的 ~1.3** ——即"锁定发端 RMS 给每个用例配 gain"，且目标值经扫描设计。

验证（`scratch/verify_rms_target.py`）：固定 target_rms=0.14 时各环境 BER 接近各环境真实最优
（Base 7.77e-4 vs opt 7.62e-4；IL20x20 1.57e-2 vs opt 1.51e-2；HighNoise_IL16x16 1.73e-3
vs opt 1.52e-3）。

### 3.3 CTLE 方向跨环境一致（可泛化）

扫描证实 11/15 case 最优 gDC=−3（峰化/低频衰减），gDC=−3 的中位 BER 1.3e-3 vs gDC=+3 的
5.2e-3。**CTLE 峰化方向跨环境一致**，因此基线代理能学到这个方向并泛化。

## 4. v5 模型与 Stage-2

### 4.1 模型（6 维，不含 gain）

Model A/B 输入 = `x_shape = [4 FFE 旁瓣, gDC, gDC2]`（6 维），与 v4 的 7 维相比只去掉 u_gain。
训练数据用基线环境 Base_IL10x10 的 2001 点，但 **gain 在目标 RMS 附近窄带采样**（倍率
×0.40~×0.90），使 FFE/CTLE 形状→BER 关系不被增益模糊。留出集 R²=0.72、Spearman=0.84
（v4 全 gain 箱采样时 R² 仅 0.28）。

### 4.2 Stage-2（v5：`ddps_optimizer._stage2_descent_v5`）

每步：
1. FFE/CTLE 代理梯度 → 组内归一化方向 + 投影到 shape 搜索盒
2. gain = 解析调到 `TARGET_DRIVE_RMS`（发端测量，不需 BER）
3. Model B 按百分比拦截候选点
4. 真实 BER 仅记账
5. 信任域放宽到 `TRUST_PATH_K_V5 = 2.0ρ`（v5 形状空间更紧凑、映射更清晰）

## 5. 结果（v5 vs v4，262144 符号 × 3 种子）

| 指标 | v5 | v4 |
| --- | --- | --- |
| 终点劣于种子（>+0.01 dex） | **0/15** | 3/15 |
| 全部改善（d_best < −0.005） | **14/15** | 13/15 |
| 平均改善 d_best | **−0.066** | −0.036 |
| IL20x20 最优 BER | **3.10e-2** | 5.32e-2 |
| Comb_IL20x20 最优 BER | **5.10e-2** | 7.28e-2 |
| HighNoise_IL16x16 最优 BER | **4.13e-4** | 6.44e-4 |

v5 在恶劣 case 的绝对 BER 显著好于 v4，且**没有任何一个 case 终点劣于种子**。

## 6. 已知边界

1. **marginal_gain 停止基于代理预测**：gDC2 走到信任域边界 −3.0 后代理预测改善 <0.01 dex 即停，
   终点可能略劣于最优步（如 IL20x20 best=3.10e-2 @step11、final=3.57e-2 @step12），
   但终点仍远优于种子。
2. **target_rms=0.14 是离线标定的常数**：换器件（MZM Vπ/ER、Driver BW）后需重跑扫描。
3. **CTLE 只优化双级直流增益**：零点/极点比例不在搜索空间内；gDC2 信任域边界 −3.0 限制进一步峰化。
4. **模型绝对标定弱**（欠/过估真实 BER），只用其 FFE/CTLE 方向；gain 维完全由物理目标处理。
