# 07. DDPS v3 模型修正与评估协议

本文记录 v3 相对 v2 的**两处建模修正**、搜索空间升维、评估协议的选择依据，以及复现方式。
结果数据见 [`result/SUMMARY.md`](../result/SUMMARY.md)；对外呈现件见 `DDPS_v3_Deliverable.html`。

---

## 1. 修正一：Tx 模拟 CTLE 的位置

**问题**：v2 把 Tx 模拟 CTLE 放在 DAC 零阶保持之后、Tx 电插损（S4P）**之前**。
其后紧接着是 VGA 的 RMS 归一化，CTLE 的直流增益被归一化吸收；峰化部分又随后的信道衰减一起被吃掉。
结果是：CTLE 对"真正到达 MZM 的频谱"几乎没有影响力，优化器在 gDC/gDC2 两维上动来动去但收益微弱。

**修正**：CTLE 移到 **Tx 电插损之后、Driver 之前**（post-channel equaliser）。
新的 Tx 前端顺序（`channel_imdd.tx_frontend_lti` 与物理探针共用同一实现）：

```
DAC(ZOH) → Tx 电插损(S4P) → +1 mV 前端噪声 → Tx 模拟 CTLE → VGA → Driver 真增益 → Driver 带限 → MZM
```

**为什么 VGA 放在 CTLE 之后**：这样 VGA 会把 CTLE 的直流增益归一化掉，CTLE 只负责**频谱整形**，
驱动摆幅则由 `driver_gain` 单独决定 —— 两个新维度在物理上互不冗余。
（若 VGA 在 CTLE 之前，CTLE 的直流增益会直接改变 MZM 驱动幅度，退化成"第二个增益旋钮"。）

**实测杠杆**（Base_IL10x10 种子点，131072 符号）：

| 配置 | BER_MLSE | 相对种子 | MZM 驱动 RMS |
| --- | --- | --- | --- |
| gDC = −5 dB | `3.35e-04` | **×1.65** | 0.2287 V |
| gDC = 0（种子） | `5.53e-04` | ×1.00 | 0.2292 V |
| gDC = +5 dB | `8.22e-04` | ×0.67 | 0.2294 V |

可见驱动 RMS 几乎不变（VGA 吸收了直流增益），BER 却随 CTLE 形状单调变化 —— CTLE 已成为真正的均衡手柄。

---

## 2. 修正二：`driver_gain` 曾是死参数

**问题**：v2 的 VGA 段写成

```python
x = x * (target_rms / (current_rms * driver_gain))   # 除 driver_gain
x = x * driver_gain                                  # 又乘回去
```

两者精确抵消 ⇒ `driver_gain` 对信号、对噪声都没有任何影响。它在配置里存在、在文档里被描述为
"真实线性增益"，但实际上是一个**完全无效的参数**。

**修正**：VGA 归一化到**固定 RMS**（`vga_out_rms = 0.617 × 0.3726 / 2.0 ≈ 0.11497 V`，与 `driver_gain` 无关），
随后 Driver 施加真实的 `driver_gain`。于是驱动摆幅 ≈ `vga_out_rms × driver_gain`，
标定值 2.0 恰好对应 `driver_vpp = 0.617 V`（与 v2 的名义摆幅一致，保证前后可比）。

**实测杠杆**（131072 符号）：

| driver_gain | BER_MLSE | 相对种子 | MZM 驱动 RMS |
| --- | --- | --- | --- |
| 1.0 | `3.59e-04` | **×1.54** | 0.1146 V |
| 1.5 | `3.63e-04` | ×1.52 | 0.1719 V |
| 2.0（标定/种子） | `5.53e-04` | ×1.00 | 0.2292 V |
| 2.5 | `3.04e-03` | ×0.18 | 0.2865 V |
| 3.0 | `1.02e-02` | ×0.05 | 0.3438 V |

即：**标定值 2.0 并非最优**，降低增益（1.0～1.5）可换约 1.5 倍改善；而增大增益会迅速把 MZM 推入
非线性区，BER 劣化一个数量级以上。这正是把 `driver_gain` 作为可调维度的价值。

---

## 3. 搜索空间：10D → 11D

```
x ∈ R^11 = [ 8 个 FFE 旁瓣, gDC, gDC2, driver_gain ]
主抽头 = 1 − Σ|旁瓣|（派生，非自由变量）；Σ|旁瓣| ≤ 0.8 ⇒ 主抽头 ≥ 0.2
```

| 维度 | 边界 | 种子 | 信任域半径 | 预条件缩放 |
| --- | --- | --- | --- | --- |
| 8 × FFE 旁瓣 | ±0.30 | `[0, 0, −0.034, −0.2987, ·, 0, 0.0582, 0, 0]` | ±0.10 | ×1 |
| gDC (CTLE 一级直流增益) | [−5, +5] dB | 0.0 dB | ±3.0 dB | ×20 |
| gDC2 (CTLE 二级直流增益) | [−5, +5] dB | 0.0 dB | ±3.0 dB | ×20 |
| driver_gain | [1.0, 3.0] | 2.0 | ±0.5 | ×4 |

预条件缩放的作用：把量纲差异极大的三类参数拉到同一数量级，否则归一化梯度在 CTLE/gain 维上的
实际位移会小到不可见。

**模型特征（v3）**

| 模型 | 输入 | 维度 | 二阶多项式特征维度 D |
| --- | --- | --- | --- |
| Model A（指路） | 7-tap Tx FIR **形状**（峰值归一）+ **MZM 驱动 RMS** | 8 | 45 |
| Model B（刹车） | 9 抽头 + gDC + gDC2 + driver_gain | 12 | 91 |

> **为什么 Model A 必须带"驱动 RMS"**：`driver_gain` 在纯线性 Tx 链里只是标量乘子，而 FIR 形状
> 对整体尺度不变 —— 只看形状时 Model A 对 `driver_gain` 的梯度**恒为 0**，Stage-2 永远无法移动该维。
> 探针改为绝对标定后额外返回 MZM 输入端的真实驱动 RMS（与真实链路实测吻合误差 < 0.3%），
> 作为第 8 个特征显式喂给 Model A。

---

## 4. 评估协议：为什么从 131072 提到 262144 × 3 seeds

v2 使用 131072 符号 × 单种子。v3 前先做了精度实测（Base_IL10x10 种子点，5 个仿真种子）：

| 块长 | log10 BER 均值 | 跨种子标准差 | 均值标准误 (K=5) | 相邻块长漂移 |
| --- | --- | --- | --- | --- |
| 65536 | −3.056 | 0.054 dex | 0.024 | — |
| 131072 | −3.304 | 0.067 dex | 0.030 | −0.248 dex |
| 262144 | −3.524 | 0.093 dex | 0.042 | −0.220 dex |
| 524288 | −3.675 | 0.139 dex | 0.062 | −0.152 dex |

同时测"一个真实改善（gDC = −5 dB 相对种子）能否被稳定分辨"：

| 块长 | Δlog10 均值 ± 标准差 | 5 个种子是否同号 |
| --- | --- | --- |
| 65536 | −0.049 ± 0.051 | ✗ 符号翻转 |
| 131072 | −0.142 ± 0.074 | ✓ |
| 262144 | −0.217 ± 0.084 | ✓ |
| 524288 | −0.393 ± 0.132 | ✓ |

结论：
1. **BER 绝对值随块长系统性漂移**（每翻倍约 −0.15～−0.25 dex），因此**不同块长的绝对 BER 不可比**，
   必须全流程固定同一协议；
2. 65536 符号下连一个 ×1.65 的真实改善都无法稳定分辨，**太短的块长会掩盖真实收益**；
3. 采用 **262144 符号 × 3 个固定仿真种子（42/43/44）取 log10 均值**：既避开短块偏置，又把均值
   标准误压到 ~0.05 dex；固定种子使不同配置之间的噪声高度相关，配对比较的精度优于该标准误。
4. 云校验（种子邻域方向一致性）用更便宜的**独立协议 65536 符号 × 2 seeds**，仅作离线定性证据。
5. 最终结果另用 **524288 符号**做独立复核（`report/deep_check.csv`）。

> 依据 AGENTS.md：BER 只作"旁路记录"，不参与 Stage-2 决策；因此提高评估精度是为了让
> **结果与复核可信**，而不是把真实 BER 喂回算法。

---

## 5. 安全红线标定（Model B 相对裕度 `SAFETY_MARGIN`）

Stage-2 的"不许变差"完全依赖 Model B 的相对红线：`safety_limit = Model B(x₀) + SAFETY_MARGIN`。
这个裕度必须按当前搜索空间标定——**11 维空间下的合理值与 10 维不同**。

标定方法：先用一个较大的裕度（0.6）跑完整在线调优并保留逐步 trace，然后**在 trace 上回放**不同裕度
（"若某步的 Model B 预测越过红线则该步不落地、迭代停止"），统计真实 BER 表现：

| `SAFETY_MARGIN` | 接受的步数 | 劣于种子的步数 | 平均改善 | 最大相对种子的劣化 |
| --- | --- | --- | --- | --- |
| 0.6（未标定） | 164 | **51** | ×3.53 | **+0.48 dex（约差 3 倍）** |
| 0.4 | 85 | 0 | ×3.42 | −0.07 dex |
| **0.3（采用）** | 68 | **0** | **×3.13** | **−0.07 dex** |
| 0.2 | 58 | 0 | ×2.94 | −0.07 dex |
| 0.1 | 37 | 0 | ×2.07 | −0.07 dex |

结论与取舍：
1. 0.6 的裕度允许真实 BER 爬升到种子的 3 倍（劣化最严重的都是种子 BER 最低的用例，此时代理的绝对误差
   相对 BER 本身最大），**必须收紧**；
2. 收紧到 **0.3**：劣化步数归零，且最差点仍比种子好 7%（−0.07 dex），平均改善只从 ×3.53 降到 ×3.13（约 −11%）；
3. 采用 0.3 而非 0.4，是为轨迹之间的波动留余量（宁可少赚一点，也不允许任何一次变差）。
4. 标定用的原始 trace 保存在 `archive/20260910_ddps_v3_margin060_calibration/`（磁盘，不入库）。

> **改这个常数必须重跑标定回放**，否则会重新引入"优化后比起点更差"。

### 5.1 重要：红线只能约束“预测恶化”，代理不可信时收紧裕度无效

对三组 trace 分别回放不同裕度（`result/ddps_v3_control`、`result/ddps_v3_20260910`、
`result/ddps_v3_control_ffe_only`）：

| 训练数据 | margin 0.30 | 0.15 | 0.05 | 0.00 | 平均改善 |
| --- | --- | --- | --- | --- | --- |
| 1175 行（含每环境锚点） | **0 步劣化** | 0 | 0 | 0 | ×3.13 |
| 321 行（只用基线） | **60 步劣化** | 60 | 54 | 52 | ×1.66 |

结论：**弱代理下把裕度收到 0 仍有 52 步真实劣化** —— 因为 Model B 沿下降方向把真实劣化误判为改善，
红线（相对种子的*预测*恶化量）对此无能为力。因此：

1. **“不许变差”的成立前提是代理在信任域内方向可信**，而不是裕度取得足够小；
2. 判定“能否上线”应看**方向可信度指标**（见 §5.2），而不是只看红线；
3. 代理不可信时的正确动作是**补数据 / 减特征 / 加正则**，而不是继续收紧红线。

### 5.2 方向可信度（种子邻域云校验，离线证据）

每环境在种子邻域做 8 点 LHS 采样（65536 符号 × 2 种子），比较模型预测与真实 BER 的方向一致性：

| 模型 | 方向一致率（Model A） | 局部 Spearman（Model A） | 结论 |
| --- | --- | --- | --- |
| 1175 行（含锚点） | 0.75 ～ 1.00（均值 0.967） | 0.238 ～ 0.929 | 方向可用 |
| 321 行（只用基线） | 0.75 ～ 1.00（均值 0.967） | **−0.357 ～ 0.500** | 排序能力不足 → Stage-2 会走偏 |

这解释了为什么“只用基线”配置虽然 15/15 用例最终都优于种子，却在中途劣化：**方向一致率尚可但局部排序退化**，
一旦代理在该点的排序与真实相反，梯度方向就会把候选点推向更差的位置。

---

## 6. 用例集：8 → 15（含非对称 Tx/Rx 插损与器件噪声）

v2 所有用例的 Tx/Rx 插损恒等。v3 支持两者独立配置（Host 侧与 Module 侧损耗在真实系统中并不对称）：

| 类别 | 用例 |
| --- | --- |
| 对称插损 | `Base_IL10x10`（基线/训练环境）、`IL14x14`、`IL20x20` |
| 非对称插损 | `IL20x10_TxHeavy`、`IL10x20_RxHeavy`、`IL16x10`、`IL10x16` |
| 色散 | `CD15ps`、`CD28ps` |
| 偏振模色散 | `DGD2ps`、`DGD5ps` |
| 复合应力 | `Comb_IL20x20_CD15_DGD5`、`Comb_IL20x10_CD15_DGD5` |
| 器件噪声 | `HighNoise_IL10x10`（RIN −140 dB/Hz, ER 15 dB, TIA 25 pA/√Hz）、`HighNoise_IL16x16` |

用例定义在 `ddps_cases.py`，训练 / 测试 / 报告共用同一份，保证口径一致。

---

## 7. 复现

```bash
# 1) 数据集：基线密集 + 各环境锚点，11 维 LHS，多进程并行
python dataset_generator.py --base-samples 320 --anchor-samples 60 \
    --num-symbols 262144 --sim-seeds 42,43,44 --jobs 14
#   -> dataset/ddps_v3_dataset_<ts>.csv   （1175 行，含 drive_rms / driver_gain）

# 2) 训练 Model A/B（带锚点版本 + 只用基线版本）
python -c "from train_surrogates import train_v3; import glob; \
  train_v3(sorted(glob.glob('dataset/ddps_v3_dataset_*.csv'))[-1], 'models/ddps_v3')"
python run_ddps_v3_control.py --dataset dataset/ddps_v3_dataset_<ts>.csv \
    --base-env Base_IL10x10 --model-dir models/ddps_v3_control \
    --test-out result/ddps_v3_control --num-symbols 262144 --sim-seeds 42,43,44

# 3) 在线调优泛化测试（冻结模型，真实 BER 只记录不回传）
python test_generalization.py --model-dir models/ddps_v3 --out-dir result/ddps_v3_<ts> \
    --num-symbols 262144 --sim-seeds 42,43,44 --n-steps 15 --cloud-n 8
#   消融对照：冻结 CTLE 与 driver_gain，只优化 FFE
python test_generalization.py --model-dir models/ddps_v3_control \
    --out-dir result/ddps_v3_control_ffe_only --freeze-extra \
    --num-symbols 262144 --sim-seeds 42,43,44 --n-steps 15

# 4) 报告与跨实验汇总
python report_ddps_v3.py --test-dir result/ddps_v3_<ts> --model-dir models/ddps_v3 \
    --deep-symbols 524288 --summary "result/ddps_v3_control:只用基线" \
    "result/ddps_v3_<ts>:带锚点" "result/ddps_v3_control_ffe_only:消融(冻结CTLE+增益)"
```

产物命名：数据 `dataset/ddps_v3_dataset_<ts>.csv`；模型 `models/ddps_v3/`（带锚点）、
`models/ddps_v3_control/`（只用基线）；结果 `result/ddps_v3_<ts>/`、`result/ddps_v3_control/`、
`result/ddps_v3_control_ffe_only/`。

---

## 8. 已知边界

1. **绝对 BER 只能在同一协议内比较**：块长改变会引起系统性漂移（见第 4 节）。
2. **`driver_gain` 的最优值依赖标定摆幅**：`vga_out_rms` 是按 "gain=2.0 ⇒ 0.617 Vpp" 定的；
   若器件标定变化，最优增益区间会整体平移。
3. **CTLE 频响形状固定**：只优化双级直流增益，零点/极点比例由配置给定，不在搜索空间内。
4. **代理仍是局部模型**：信任域外的预测不可信（因此有梯度门控 + 信任域 + Model B 三重约束）。
5. 非对称插损用例只覆盖 10/16/20 dB 的若干组合，未穷举。
