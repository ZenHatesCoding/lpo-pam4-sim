# DDPS v4 任务交接说明

> 给接手的 Agent。先读 [08. DDPS v4 模型与算法口径](docs/08_DDPS_v4_Model_Update.md) +
> [04. DDPS 寻优架构](docs/04_DDPS_Optimization.md)，再动手。
> 重点看「非协商约束」与「踩过的坑（已修，别回退）」。

## 一、一句话现状

DDPS 已按甲方口径重做为 **v4**：

- **链路**：`FFE → DAC → Tx 电插损 → 1mV 噪声 → CTLE → Driver(可调增益) → Driver 带限 → MZM`。
  **没有 VGA、没有任何 RMS 归一化** —— 入 MZM 摆幅就是"前端电平 × 增益"，因此增益是名副其实的自由度。
- **三组自由度全部可微**：FFE（8 旁瓣）/ CTLE（gDC, gDC2）/ Driver 增益（倍率 ×0.30~×4.00，对数参数化），
  共 7 维，一起交给梯度下降。关键在于 **Model A/B 的输入就是搜索向量 x 本身**（三组同量纲），
  梯度由核岭回归的**解析导数**给出，不存在"某一维量纲被吃掉、梯度恒为 0"的问题。
- **Driver 增益标定**：`tools/calibrate_driver_gain.py` 实测 `DRIVER_GAIN_NOMINAL = 0.4381`，
  使基线播种配置的 MZM 摆幅 = 0.617 Vpp；`create_config.py` 默认值与之一致。
- **拦截判据**：Model B 按 **预测变差百分比**（≤ +25%）放行/否决，不是绝对 BER、也不是 log10 绝对裕度。
- **数据**：**只用基线环境（IL10x10）** 采样 2000 点（7 维 LHS：核心 1200 加密 + 外壳 800 覆盖）训练；其余 14 个场景零样本。
- **评估协议**：262144 符号/点 × 3 仿真实例种子取 log10 均值（块长漂移实测见 docs/08）。

v3 及更早产物已归档到 `archive/20260911_ddps_v3_pre_no_vga/` 与
`archive/20260910_ddps_v2_pre_ctle_reorder/`（磁盘，不入库）。当前分支 `physical-model`。

## 二、非协商约束（甲方底线，别碰）

1. **7 维搜索向量 x 的定义是固定约束**（`ddps_optimizer._taps_to_x` / `_x_to_taps_ctle`）：
   `x = [4 个 FFE 旁瓣（5-tap FFE）, gDC, gDC2, u_gain]`。7-tap 发端 FIR 探针（`tx_channel_extract`）保留为
   数据集的**诊断列**与链路一致性工具，但**不再是模型输入**（原因见 docs/08 §3.1）。
2. **两阶段底线**：Stage 1（离线标定）可崩、可拿真实端到端 BER；Stage 2（在线调优）
   **不能崩、只能拿发端指标**（真实收端 BER 只记录验证、绝不回传方向决策）。
3. **100% 白盒**：训练/推理/梯度手写（numpy 最多）；无 sklearn/scipy.optimize 黑盒。
4. **统一 BER_MLSE 口径**：全链路指标 = MLSE(memory=1, Burg 白化) 判决输出（Gray 映射）。
5. **评估协议必须全流程一致**：262144 符号/点 × 仿真种子 (42,43,44) 取 log10 均值。
   BER 绝对值随块长系统性漂移（每翻倍约 −0.15～−0.25 dex），**不同协议的绝对 BER 不可比**。
6. **训练数据只用基线环境**：不再"按场景分别训练"。唯一训练集是 IL10x10 的采样点
   （v4 为 2000 点），其余场景必须零样本参与测试，否则泛化结论作废。
7. **拦截只能用相对量**：Model B 的判据是"预测 BER 相对种子变差 ≤ MAX_DEGRADE_FRAC（25%）"。
   绝对 BER 的阈值/红线一律无效（代理绝对标定不可信）。
8. **三组自由度必须都能被梯度下降驱动**：FFE / CTLE / Driver 增益。若某维梯度恒为 0，
   说明特征设计或链路结构把它抵消了，必须先修特征，而不是绕过它。
   v4 的保证方式：输入直接取搜索向量 x（§3.1），并用 `tools/validate_local_gradient.py`
   在真实链路上逐轴实测方向命中率（不参与训练）。
9. **文档全中文**（README/docs），图内文字可英文。

## 三、链路顺序（v4 唯一正确顺序）

```
DAC(ZOH, ENOB) → Tx 电插损(S4P, Tx IL) → +1 mV 前端噪声 → Tx 模拟 CTLE(gDC,gDC2)
             → Driver(真实增益 g, 可调) → Driver 带限(40 GHz) → MZM
             → 光纤(CD/DGD) → PIN → TIA → Rx 电插损(S4P, Rx IL) → ADC → Rx DSP
```

- 实现集中在 `channel_imdd.tx_frontend_lti()`；**物理探针 `tx_channel_extract` 与真实链路共用它**，
  改链路顺序只需改这一处。
- **禁止再加 VGA / RMS 归一化**：任何"后级把幅度归一化掉"的结构都会让 driver_gain 失去意义。

## 四、踩过的坑（已修，勿回退/勿重犯）

### 4.4 v1/v2 的老坑（仍然有效）

1. **LHS 采样器维度与索引必须一致**：`LatinHypercube(d=9)` 却取 `sp[i,9]` → 首样本 IndexError →
   Stage-1 邻域数据从未生成，模型退化。v3 为 `d=N_DIM=11`。
2. **S4P 频率缩放的群时延漂移**：不同目标插损下脉冲峰值位置不同（IL10 → idx 1247，IL20 → idx 238）。
   任何"进程级粘滞 argmax"都会在错误符号格取 FIR。v3 的 `_peak_idx_for_env` 按信道环境缓存。
3. **代理趋平要停**：Model A 在训练域外 |∇|≈1e-4 仍会沿拟合噪声乱走 → 负向优化。
   v3 保留梯度门控 `GRAD_GATE=0.05`。
4. **安全红线必须标定（v3 关键）**：Model B 的相对红线 `SAFETY_MARGIN` 决定"允许多少预测恶化"。
   v3 在完整 trace 上回放不同裕度：**0.6 → 164 步中 51 步真实 BER 劣于种子（最多 +0.48 dex，即差 3 倍）**，
   而 0.4 → 0 步劣化（平均改善 ×3.42）、0.3 → 0 步劣化（×3.13）。因此 v3 取 **0.3**。
   **改这个常数前必须重跑标定回放**（否则会重新引入"优化后变差"）。
5. **模型 pickle 用模块路径**（`train_surrogates`），加载用 `load_models()`。

### 4.2 v4 的硬性约束（违反就会让三组自由度退化）

1. **不要给 Tx 前端加 VGA/RMS 归一化**（v3 曾这么做，导致增益的作用被抵消）。
2. **模型输入必须是搜索变量本身**：不要再插入一层“波形特征”当输入——七抽头绝对 FIR 对 7 维配置
   是多对一的，实测二阶基下留出集 R² 只有 0.29（搜索向量 0.56、核方法 0.62）。
3. **driver_gain 必须与 `create_config.py` 的标定值一致**；换器件后重跑
   `tools/calibrate_driver_gain.py`，否则整个搜索箱会整体偏移。
4. **拦截判据用百分比（`MAX_DEGRADE_FRAC = 0.25`）**，不要退回绝对 BER 阈值。
5. **步长是"分组归一化 + 各维箱宽"**（`STEP_SPAN`、`GROUP_GATE`、`GD_LR=0.05`、`ALPHA_DECAY=0.97`）。
   不要退回"整体归一化"——那样振幅大的 FFE 维会独吞步长，增益维 15 步只走 ~0.004 dex。
   步长档位与真值审计见 docs/08 §4.5。

### 4.3 v3 修的坑（仍然有效，勿回退）

6. **CTLE 位置**：v2 把 CTLE 放在 Tx 电插损**之前**，其增益被后续 VGA 归一化与信道衰减吸收，
   实测几乎无杠杆（"CTLE 优化半天没收益"的根因）。v3 移到**电插损之后、Driver 之前**。
   **不要**把它挪回 DAC 输出处。
7. **`driver_gain` 曾是死参数**：v2 的 VGA 归一化里除以 `driver_gain`、紧接着又乘回去，
   二者精确抵消 ⇒ 该参数对信号与噪声都无影响。v3 让 VGA 归一化与 `driver_gain` 解耦。
   改动 VGA 段时务必确认"驱动摆幅确实随 driver_gain 变化"（用
   `report/deep_check.csv` 或直接量 `tx_analog` 的 RMS）。
8. **Model A 对纯增益天然失明**：driver_gain 是线性标量乘子，7-tap FIR 形状对整体尺度不变，
   只看形状 ⇒ 对 driver_gain 梯度恒为 0。v3 给 Model A 增加"MZM 绝对驱动 RMS"特征（8 维）。
   若以后再加"纯增益型"维度，必须以显式标量特征或绝对标定波形呈现，否则该维不可优化。

## 五、v4 标准流程（复现命令）

```bash
# 0) 标定 Driver 增益
python tools/calibrate_driver_gain.py

# 1) 数据集：只用基线环境，2000 点，7 维 LHS（核心 1200 + 外壳 800）
python dataset_generator.py --base-samples 2000 --anchor-samples 0 \
    --only-envs Base_IL10x10 --num-symbols 262144 --sim-seeds 42,43,44 --jobs 14

# 2) 训练 Model A / B（核岭均值 + 保守上包络；输入均为 7 维搜索向量 x）
python -c "from train_surrogates import train_v4; import glob; \
  train_v4(sorted(glob.glob('dataset/ddps_v4_dataset_*.csv'))[-1], 'models/ddps_v4')"

# 3) 模型方向实测标定（11 轴中心差分；不参与训练）
python tools/validate_local_gradient.py --model-dir models/ddps_v4 \
    --env Base_IL10x10 --num-symbols 262144 --sim-seeds 42,43,44 \
    --out result/ddps_v4_local_gradient.csv

# 4) 在线调优（15 场景）；可分片并行后合并
python test_generalization.py --model-dir models/ddps_v4 --out-dir result/ddps_v4_main \
    --num-symbols 262144 --sim-seeds 42,43,44 --n-steps 15 --cloud-n 8
python tools/merge_test_parts.py --out result/ddps_v4_main result/_parts/main_a result/_parts/main_b result/_parts/main_c

# 5) 报告（含三曲线收敛图 Model A / Model B / 实测 BER）与汇总
python report_ddps_v4.py --test-dir result/ddps_v4_main --model-dir models/ddps_v4 \
    --deep-symbols 524288 --summary "result/ddps_v4_main:三组自由度全开" \
    --summary-out result/SUMMARY.md

# 6) 交付件（从产物自动生成，数字不手工转录）
python make_deliverable_v4.py --baseline result/ddps_v4_main --model-dir models/ddps_v4
```

## 六、当前产物索引

- 数据集：`dataset/ddps_v4_dataset_<ts>.csv`（2001 行 = 核心 1200 + 外壳 800 + 种子，只含基线环境）
- 模型：`models/ddps_v4/`（model_a.pkl / model_b.pkl / meta.json）
- 方向标定：`result/ddps_v4_local_gradient.csv`（11 轴实测斜率 vs 模型解析梯度）
- 结果：`result/ddps_v4_main/`（case_summary、trace_<用例>.csv、run_config.json、report/）
- 诊断：`result/ddps_v4_local_gradient.csv`（7 轴方向实测）、`result/ddps_v4_divergence.csv`（Δ预测 vs Δ实测）、
  `result/ddps_v4_trace_check.csv`（独立重仿真复核）、`result/ddps_v4_run_length.csv`
- 报告：`result/ddps_v4_main/report/ddps_v4_convergence.png`（**三曲线核心图**）、
  `ddps_v4_report.md`、逐用例 `_a/_b`、`ddps_v4_overview.png`、`deep_check.csv`
- 汇总：`result/SUMMARY.md`
- 交付件：`DDPS_v4_Deliverable.html`（由 `make_deliverable_v4.py` 生成）
- 方法记录：`docs/08_DDPS_v4_Model_Update.md`
- 旧版本归档：`archive/20260911_ddps_v3_pre_no_vga/`、`archive/20260910_ddps_v2_pre_ctle_reorder/`、
  `archive/20260911_ddps_v4_probe_polyRidge/`（v4 第一轮"波形探针 + 二阶 Ridge"的模型与结果）

## 七、已知边界（诚实记录，勿包装成成功）

1. Model A/B 的**绝对标定弱**（欠/过估真实 BER），只用其排序/方向；拦截判据因此用百分比。
2. **`driver_gain` 最优值依赖标定摆幅**：标定值 0.4381 按 "基线 + 种子 FFE/CTLE ⇒ 0.617 Vpp" 定，
   器件标定变化会让最优增益区间整体平移。
3. **CTLE 频响形状固定**：只优化双级直流增益，零点/极点比例不在搜索空间内。
4. **BER 随块长漂移**：报告必须注明协议；跨协议比较无意义。
5. **局部斜率量级不可全信**：11 轴方向加权命中率 0.93，但各轴斜率量级与实测相关系数只有 0.70；
   因此步长由各维**箱宽**决定，而不是由斜率决定（docs/08 §4.5）。
6. **基线用例的轨迹很快进入平台期是"已到最优"**：真值审计显示梯度下降最优点（−0.342 dex）
   优于任何单旋钮最优组合，手工拼装三个"各自最优"反而更差（docs/08 §4.5）。
