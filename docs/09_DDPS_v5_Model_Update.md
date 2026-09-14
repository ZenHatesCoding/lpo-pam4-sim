# 09. DDPS v5 模型与算法口径

> 本版修复 v4 的"预测降/实测升"。先读 [08. DDPS v4](08_DDPS_v4_Model_Update.md)
> 了解 v4 的链路口径与失败现象，再读本文件看修法。

## 1. 一句话现状

DDPS v5：链路口径与 v4 完全一致（CTLE 在 Tx 电插损之后、Driver 之前；driver_gain 可调
×0.30~×4.00；无 VGA、无 RMS 归一化）。**改变的是 gain 维与 FFE/CTLE 的分工**：

- **gain 维**：**不进代理、不走梯度下降**。每个用例单独细粒度扫描标定自己的 target_rms
  （0.06~0.22 V，步长 0.005），在线调优时每步解析调到该用例的 target_rms。
- **FFE/CTLE**：仍走基线代理泛化（核岭 6 维，R²=0.72）。模型只吃 6 维 x_shape，gain 不是输入。

## 2. 根因：v4 为什么"预测降/实测升"

gain 维最优方向随环境反转：基线信号强、最优 gain 偏低（防 MZM 削顶）；高插损信号弱、
最优 gain 偏高（补摆幅）。v4 把 gain 交给基线训练的代理盲驱，代理对 gain 梯度永远是"降 gain"
（基线最优是降），于是在 IL20x20 等恶劣环境把 gain 维反方向驱动。

v2/v3 之所以能单调下降，正是因为 gain 被锁死。问题不在缺信道信息，而在 v4 把"方向随环境
反转的 gain 维"交给了信道盲的代理。

证据：`result/ddps_v4_divergence.csv` 的 corr_pred_real 在 IL20x20/Comb_IL20x20/
HighNoise_IL16x16/Comb_IL20x10 为负（−0.35~−0.59）。

## 3. 修法：gain 维 per-case RMS 物理目标驱动

### 3.1 物理机制

链路里 `x = x * driver_gain`（gain 是 Tx 前端最后的线性乘子），所以 MZM 输入端 RMS
`drive_rms ∝ gain`（在固定 FFE/CTLE 下 `rms/gain` 为常数 k）。给定目标 RMS：

```
gain_target = gain_ref * (target_rms / rms_ref)      # 一次发端测量即可标定 k
```

### 3.2 per-case 细粒度扫描（每个用例单独标定，不求几何均值）

`scratch/scan_per_case_rms.py` 对每个用例在种子 FFE/CTLE 配置下细扫 target_rms
（0.06~0.22 V，步长 0.005，共 33 点/用例），每个 target_rms 解析求解 gain → 跑全链路
仿真 → 记录 BER，取每个用例 BER 最低的 target_rms。

结果（`result/per_case_target_rms.json`）：每个用例的 target_rms 各不相同——

| 用例 | target_rms (V) | gain 倍率 |
| --- | --- | --- |
| Base_IL10x10 | 0.145 | ×0.631 |
| IL14x14 | 0.140 | ×0.747 |
| IL20x20 | 0.195 | ×1.271 |
| Comb_IL20x20 | 0.195 | ×1.271 |
| HighNoise_IL10x10 | 0.160 | ×0.696 |
| HighNoise_IL16x16 | 0.150 | ×0.865 |
| DGD2ps | 0.110 | ×0.479 |
| DGD5ps | 0.155 | ×0.674 |
| （其余 7 个见 JSON） | | |

强信号环境 target_rms 偏低（~0.11~0.15V，gain ×0.48~0.73）、弱信号环境偏高
（~0.19~0.20V，gain ×1.27）——即"每个用例单独优化 gain"，而非全局几何均值。

### 3.3 数据集 gain 窄带采样

基线环境 Base_IL10x10 的 per-case 最优 gain 倍率 = ×0.631。数据集在 gain 倍率 [0.40, 0.90]
窄带采样（围绕 0.631 上下覆盖），使 FFE/CTLE 形状→BER 关系不被增益模糊。v4 在整箱 gain
采样时 R² 仅 0.28；v5 窄带采样后 R²=0.72。

### 3.4 CTLE 方向跨环境一致（可泛化）

扫描证实 11/15 case 最优 gDC=−3（峰化/低频衰减）。CTLE 峰化方向跨环境一致，
因此基线代理能学到并泛化。FFE/CTLE 仍交给代理梯度下降。

## 4. v5 模型与 Stage-2

### 4.1 模型（6 维，不含 gain）

Model A/B 输入 = `x_shape = [4 FFE 旁瓣, gDC, gDC2]`（6 维）。训练数据用基线环境
Base_IL10x10 的 2001 点，gain 在 [0.40, 0.90] 窄带采样。留出集 R²=0.72、Spearman=0.84。

### 4.2 Stage-2（v5：`ddps_optimizer._stage2_descent_v5`）

每步：
1. FFE/CTLE 代理梯度 → 组内归一化方向 + 投影到 shape 搜索盒
2. Model B 按百分比拦截候选点
3. **gain = 解析调到该用例的 per-case target_rms**（发端测量，不需 BER）
4. 真实 BER 仅记账
5. 信任域放宽到 `TRUST_PATH_K_V5 = 2.0ρ`

### 4.3 验证：方向不再反转

`result/ddps_v5_divergence.csv`：15 个场景 corr_pred_real **全部为正**
（中位 +0.57，v4 有 4 个为负）。gain 维物理驱动后，FFE/CTLE 代理方向在全环境一致。

## 5. 结果（v5，262144 符号 × 3 种子）

| 指标 | v5 | v4 |
| --- | --- | --- |
| 终点劣于种子（>+0.01 dex） | **0/15** | 3/15 |
| 全部改善（d_best < −0.005） | **14/15** | 13/15 |
| 平均改善 d_best | **−0.066** | −0.036 |
| corr_pred_real 正相关 | **15/15** | 11/15 |
| IL20x20 最优 BER | **3.10e-2** | 5.32e-2 |
| HighNoise_IL16x16 最优 BER | **4.13e-4** | 6.44e-4 |

## 6. 已知边界

1. **恶劣场景绝对 BER 仍在 1e-2 量级**：IL20x20=3.1e-2、Comb_IL20x20=5.1e-2。
   受限于 CTLE 只调双级直流增益、零点/极点比例不在搜索空间。
2. **marginal_gain 停止基于代理预测**：gDC2 走到边界 −3.0 后代理预测改善 <0.01 dex 即停，
   终点可能略劣于最优步，但终点仍远优于种子。
3. **per-case target_rms 是离线标定的**：换器件后需重跑 `scratch/scan_per_case_rms.py`。
4. **模型绝对标定弱**：只用其 FFE/CTLE 方向；gain 维完全由物理目标处理。
