# 08. DDPS v4 模型与算法口径

本文是这一版的**唯一方法记录**：链路口径、7 个可调量的定义与标定、两个代理各自在训练什么、
采样设计、在线寻优与全部超参的标定依据、以及"预测下降而实测上升"这一现象的成因与对策。
交付件见 [`DDPS_v4_Deliverable.html`](../DDPS_v4_Deliverable.html)；结果汇总见 [`result/SUMMARY.md`](../result/SUMMARY.md)。

历史版本：`archive/20260911_ddps_v3_pre_no_vga/`（v3 及更早）、
`archive/20260911_ddps_v4_probe_polyRidge/`（v4 首轮：波形探针 + 二阶 Ridge）、
`archive/20260911_ddps_v4_11dim_kernelRidge/`（上一版：9 抽头 / 11 维 / 整箱均匀采样）。均只留磁盘、不入库。

---

## 1. 链路口径：没有 VGA、没有 RMS 固定

```
PAM4 → 5-tap Tx FFE → DAC(ZOH, ENOB 5.5) → Tx 电插损(S4P, Tx IL) → +1 mV 前端噪声
     → Tx 模拟 CTLE(gDC,gDC2) → Driver(真实增益 g) → Driver 带限(40 GHz) → MZM
     → 光纤(CD/DGD) → PIN → TIA → Rx 电插损(S4P, Rx IL) → ADC → Rx FFE(22-tap,LMS)
     → Burg 白化 → Viterbi MLSE(memory=1) → BER_MLSE
```

1. **入 MZM 的摆幅 = 前端电平 × driver_gain**，由物理自然决定；v3 的"VGA 固定 RMS"已删除，
   否则增益会被后级归一化抵消。
2. **标定**：`tools/calibrate_driver_gain.py` 实测 `DRIVER_GAIN_NOMINAL = 0.4381`，
   使基线环境 + 种子 FFE/CTLE 下 MZM 摆幅 = 0.617 Vpp；`create_config.py` 默认值与之一致。
3. **增益搜索箱 = ×0.30 ～ ×4.00**（倍率），参数化 `u = log10(g / g₀)`。

---

## 2. 可调量：5-tap FFE 的 4 个旁瓣 + CTLE 两级 + Driver 增益 = **7 维**

| 组 | 维度 | 物理含义 | 边界 | 种子 |
| --- | --- | --- | --- | --- |
| ① FFE | 4 | 5-tap T-spaced 的 4 个旁瓣；主抽头 `t₂ = 1 − Σ|旁瓣|` 派生 | \|t\| ≤ 0.3，Σ\|旁瓣\| ≤ 0.8 | `[−0.034, −0.2987, ·, 0, 0.0582]` |
| ② CTLE | 2 | post-channel 双级直流增益 | [−5, +5] dB | 0 / 0 dB |
| ③ Driver 增益 | 1 | 入 MZM 摆幅（OMA vs MZM 线性度） | 倍率 ×0.30～×4.00 | ×1.00（标定值） |

搜索向量 `x ∈ R⁷ = [4 旁瓣, gDC, gDC2, u_gain]`；在线搜索盒 = FFE ±0.10、CTLE ±3 dB、增益走满整箱。

**为什么从 9 抽头降到 5 抽头**：上一版 9 抽头的 8 个旁瓣里，外侧 4 个在整条轨迹上基本停在 0，
却同样消耗样本的分辨力。降到 7 维后，同样 2001 个样本的局部斜率可分辨性显著变好（见 §3.4 的逐轴实测）。
抽头数是**架构约束**，不在搜索空间内；改抽头数必须重跑数据集（链路变了，旧 BER 不可比）。

### 2.1 三组可调量各自的实测杠杆（基线种子点，262144 符号 × 3 种子）

| Driver 增益倍率 | BER_MLSE | 相对种子 | | CTLE gDC | BER_MLSE | 相对种子 |
| --- | --- | --- | --- | --- | --- | --- |
| ×0.30 | `5.74e-04` | ×0.65 | | −5 dB | `1.82e-04` | **×2.05** |
| ×0.50 | `1.78e-04` | **×2.11** | | −3 dB | `1.85e-04` | ×2.02 |
| ×0.65 | `1.74e-04` | **×2.15** | | −1 dB | `2.15e-04` | ×1.75 |
| ×1.00（标定） | `3.75e-04` | ×1.00 | | 0 dB（种子） | `3.75e-04` | ×1.00 |
| ×1.50 | `1.06e-02` | ×0.04 | | +3 dB | `7.17e-03` | ×0.05 |
| ×4.00 | `2.81e-01` | ×0.00 | | +5 dB | `2.39e-02` | ×0.02 |

读法：**增益不是越大越好**（摆幅超过约 0.6 Vpp 后 MZM 非线性吃掉全部收益），最优倍率在 ×0.5～×0.65；
CTLE 直流增益同样有内部最优（−3～−5 dB）。这些数字与代理无关，是链路自身的性质。

---

## 3. 两个代理：A 与 B 到底在训练什么

|  | Model A（方向） | Model B（拦截） |
| --- | --- | --- |
| **输入** | 7 维搜索向量 `x` | 同一个 7 维 `x` |
| **标签** | `y = log10(BER_MLSE)`，BER_MLSE = 该配置下 262144 符号 × 3 个仿真实例种子的 MLSE 判决 BER 的 log10 均值 | 同 A |
| **训练集** | 只有基线环境 Base_IL10x10 的 2001 个真实样本；其余 14 场景零样本 | 同 A |
| **拟合目标** | 条件均值 `E[y|x]`：RBF 核岭回归闭式解 + **解析梯度** | 保守上包络 `E[y|x] + c·S(x)`（S = 残差尺度回归，c 标定到 ≈85% 覆盖率） |
| **用途** | 给下降方向；判"每步还能赚多少" | 按"预测 BER 相对种子预测变差 ≤ 25%"放行/否决 |
| **验证** | 留出集 R²/ Spearman + §3.4 的 7 轴方向实测 | 测试集覆盖率（保守性指标） |

两者输入、标签、训练集完全相同，差别只有拟合目标：**A 求准（方向），B 求守（刹车）**。

### 3.1 为什么输入用搜索向量 x，而不是 Tx 端波形探针

探针是**线性冲激响应**，而真实链路在整形级之前还有 `DAC ENOB = 5.5` 量化这类幅度相关非线性，
探针与真实链路并不严格等价；且 7 抽头绝对 FIR 对 7 维配置是**多对一**压缩。实测同一份数据：

| 输入特征 | 二阶多项式 Ridge（留出集 R²） | RBF 核岭（留出集 R²） |
| --- | --- | --- |
| Tx 端 7-tap 绝对 FIR（探针） | 0.29 | 0.61 |
| **搜索向量 x（采用）** | **0.56** | **0.62** |

用 x 的额外好处：同等精度下参数更少、梯度直接落在搜索变量上。波形探针（`tx_fir_*`）仍保留为数据集的**诊断列**。

### 3.2 模型形式与超参

```
Model A : f(x) = ȳ + k(x)ᵀ (K + αI)⁻¹ (y − ȳ),  k(x)_i = exp(−γ‖z(x) − z(x_i)‖²)
          z = 标准化后的 x；γ = 1 / median(‖z_i − z_j‖²)（只看输入分布）；α 由 5 折 CV 选取
Model B : B(x) = f(x) + c · S(x)
```

自检：Model A 的解析梯度与有限差分最大相对偏差 1.6×10⁻³。

### 3.3 模型指标（留出集，20% 样本）

由 `models/ddps_v4/meta.json` 给出，交付件与报告会自动引用（本版数字：Model A R² ≈ 0.6 / Spearman ≈ 0.8；
Model B 覆盖率 ≈ 0.9）。

### 3.4 方向验证：7 轴中心差分实测（不参与训练）

`tools/validate_local_gradient.py`：在真实链路上对种子工作点沿 7 个搜索轴做中心差分
（262144 符号 × 3 种子 = 14 次独立真实 BER 评估），得到真实 `log10 BER` 的局部斜率，与 Model A 的解析梯度逐轴对照：

- 指标：方向命中率、按 |实测斜率| 加权命中率、量级相关系数；
- 明细表：`result/ddps_v4_local_gradient.csv`（交付件 §3.4 原样列出）。

---

## 4. 在线寻优（Stage 2）

1. 安全线：`10^ModelB(x) ≤ 10^ModelB(x₀) × 1.25`（**百分比口径**）。
2. 解析梯度 `g = ∂ModelA/∂x`（7 维）。
3. **分组步长**：FFE(4) / CTLE(2) / 增益(1) 三组，组内把 `g ⊙ 箱宽` 归一化，再乘该组箱宽
   （FFE 0.20 / CTLE 6 dB / 增益 1.12 dex）；`α_k = 0.05 × 0.97^k`。
4. **组梯度门控**：某组"走满整箱"的预测收益 < 1e-3 dex 时冻结该组。
5. **轨迹信任域**：标准化位移 ≤ `1.0 × ρ`，ρ = 训练数据第 32 近邻的中位距离（训练时写入模型）。
6. 投影到搜索盒；红线不过则步长折半重试（≤20 次）；Model A 预测每步改善 < 0.01 dex 即停。
7. 真实 BER_MLSE 逐步写入 trace，**只记账、不回传决策**。

### 4.1 步长选型（基线用例，真实协议 262144×3）

| α₀ | 最优步 | 真实改善（log10） | 末步相对种子 | 现象 |
| --- | --- | --- | --- | --- |
| 0.03 | 11 | −0.342 | −0.322 | 稳，但到位慢 |
| **0.05（采用）** | 10 | **−0.342** | −0.342 | 稳、15 步内到位 |
| 0.08 | 0 | −0.340 | −0.317 | 稳 |
| 0.15 | 2 | −0.335 | **+0.011** | 出现来回振荡 |
| 0.25 | 0 | −0.326 | **+0.171** | 明显振荡，末步更差 |

### 4.2 轨迹信任域 κ 的标定

ρ 是训练数据的局部颗粒度。上一版（11 维、整箱均匀采样）实测：整条 15 步轨迹的标准化位移中位 0.80ρ，
而**实测最优步出现在位移 0.43ρ** 附近 —— 收益集中在约半个数据格内，位移继续增加只会让预测与实测脱钩
（见 §4.3）。因此把 κ 取 1.0（一个数据格）。

### 4.3 "预测一直降、实测却升"的成因（本版新增的诊断）

`tools/diagnose_divergence.py` 逐用例比较每一步的 Δ预测与 Δ实测：

- 两个代理**只在基线环境训练过，输入里没有任何信道信息** → 方向只在"信道条件与训练环境相近"时成立；
- 与训练环境相近的场景（≤16 dB 插损、色散类）Δ预测与 Δ实测**正相关**；
- ≥20 dB 插损 / 强噪声场景**负相关**（预测继续下降、实测却在变差）——零样本泛化的**适用域**问题；
- **不是记账错误**：`tools/verify_trace.py` 用独立重仿真复核 trace 里记录的每一步（逐点一致）。

对策（都不依赖任何真实 BER 反馈）：轨迹信任域（§4 第 5 条）+ 运行长度回放（推荐在线 2～3 步）。

---

## 5. 数据与评估协议

| 项 | 取值 |
| --- | --- |
| 训练环境 | **只有 `Base_IL10x10`**（Tx/Rx 插损 10 dB，无 CD/DGD） |
| 训练规模 | **2001 行** = 核心加密 1200 + 外壳覆盖 800 + 1 个精确种子点 |
| 核心采样范围 | FFE 旁瓣 ±0.075 / CTLE ±2.0 dB / 增益 ±0.20 dex |
| 外壳采样范围 | FFE 旁瓣 ±0.10 / CTLE ±3.0 dB / 增益倍率 ×0.30～×4.00（对数均匀） |
| 测试场景 | 15 个（其余 14 个场景**零样本**进入测试） |
| 评估协议 | **262144 符号/点 × 3 个仿真实例种子（42,43,44）取 log10 均值** |
| 长块复核 | 524288 符号 × 3 种子 |

**为什么分层采样**：2001 个点若均匀铺满 7 维箱，最靠近种子的一圈点仍然很稀，代理在工作点附近的
**增量斜率**没有数据支撑 —— 这正是上一版"预测降、实测升"的直接原因（诊断见 §4.3）。
把 60% 预算放进轨迹真正经过的小邻域后，局部颗粒度 ρ 显著变小，轨迹信任域才有意义。

块长精度实测（`tools/block_length_study.py`）：块长每翻倍绝对 BER 漂移约 −0.14～−0.24 dex，
且**块长越短，同一个真实改善被"看见"的比例越小**（65536 时只剩约 1/5）。全流程固定同一协议。

---

## 6. 复现

```bash
# 0) 标定 driver 增益
python tools/calibrate_driver_gain.py

# 1) 数据集：只用基线，2001 行（核心 1200 + 外壳 800 + 种子），7 维 LHS
python dataset_generator.py --base-samples 2000 --anchor-samples 0 \
    --only-envs Base_IL10x10 --num-symbols 262144 --sim-seeds 42,43,44 \
    --jobs 14 --core-samples 1200

# 2) 训练 A/B
python -c "from train_surrogates import train_v4; import glob; \
  train_v4(sorted(glob.glob('dataset/ddps_v4_dataset_*.csv'))[-1], 'models/ddps_v4')"

# 3) 方向实测标定（7 轴中心差分，不参与训练）
python tools/validate_local_gradient.py --model-dir models/ddps_v4 --env Base_IL10x10 \
    --num-symbols 262144 --sim-seeds 42,43,44 --out result/ddps_v4_local_gradient.csv

# 4) 在线调优（15 场景；可分片并行 + tools/merge_test_parts.py 合并）
python test_generalization.py --model-dir models/ddps_v4 --out-dir result/ddps_v4_main \
    --num-symbols 262144 --sim-seeds 42,43,44 --n-steps 15 --cloud-n 8

# 5) 复核与诊断
python tools/verify_trace.py --test-dir result/ddps_v4_main --envs Base_IL10x10,IL20x20 \
    --steps 0,3,7,14 --num-symbols 262144 --sim-seeds 42,43,44
python tools/diagnose_divergence.py --test-dir result/ddps_v4_main --model-dir models/ddps_v4 \
    --out result/ddps_v4_divergence.csv
python tools/run_length_replay.py --main result/ddps_v4_main --out result/ddps_v4_run_length.csv

# 6) 报告与交付件
python report_ddps_v4.py --test-dir result/ddps_v4_main --model-dir models/ddps_v4 \
    --deep-symbols 524288 --summary "result/ddps_v4_main:三组自由度全开" \
    --summary-out result/SUMMARY.md
python make_deliverable_v4.py --baseline result/ddps_v4_main --model-dir models/ddps_v4
```

## 7. 已知边界

1. **零样本泛化的适用域**：信道条件与训练环境相近时方向可用；≥20 dB 插损 / 强噪声时方向脱钩。
   当前靠轨迹信任域与运行长度限制损失，根治需要信道条件入模 + 每场景少量现场样本。
2. **代理斜率量级不精确**：方向加权命中率高，但逐轴量级比值仍有数倍偏差，因此步长由箱宽决定。
3. **Model B 是保守上包络**：绝对水平偏高，百分比红线在绝对意义上偏松。
4. **`driver_gain` 最优区间依赖摆幅标定**：换器件需重跑 `tools/calibrate_driver_gain.py`。
5. **CTLE 频响形状固定**：只优化双级直流增益；**Tx FFE 固定 5 抽头**，抽头数与主抽头位置不在搜索空间。
6. **场景覆盖有限**：15 个场景覆盖 10/14/16/20 dB 插损组合与 CD/DGD/器件噪声，未穷举。
