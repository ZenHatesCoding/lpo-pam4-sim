# DDPS v3 任务交接说明

> 给接手的 Agent。先读 [07. DDPS v3 模型修正与评估协议](docs/07_DDPS_v3_Model_Update.md) +
> [04. DDPS 寻优架构](docs/04_DDPS_Optimization.md)，再动手。
> 重点看「非协商约束」与「踩过的坑（已修，别回退）」。

## 一、一句话现状

DDPS 已完成 **v3**：修正了 Tx 链两处建模问题（CTLE 位置、`driver_gain` 死参数），搜索空间扩到 11 维，
用例扩到 15 个（含非对称 Tx/Rx 插损与器件噪声），评估协议升级为 262144 符号 × 3 个仿真实例种子，
安全红线按 11 维空间重新标定（0.6 → 0.3）。

**当前状态（诚实版）**：

- ✅ **物理自由度确实有杠杆**（与代理无关的实测）：CTLE `gDC = −5 dB` 相对种子 ×1.78；
  `driver_gain = 1.0` 相对标定值 2.0 为 ×1.85，而 3.0 劣化约 30 倍。
- ✅ **含锚点配置（1175 行训练）已通过安全性核验**：15/15 用例正向、平均 ×3.13（最高 ×6.33），
  68 步真实 BER **0 步劣于种子**；`driver_gain` 被一致拉到 ≈1.976。
- ⚠️ **严格泛化配置（只用 321 行基线训练）当前不可交付**：平均仅 ×1.66，225 步中 **60 步劣于种子**。
  诊断：11 维空间下基线数据不足 → 代理局部排序不可靠（Model A 留出集 Spearman 仅 0.349，
  云校验局部 Spearman 低至 −0.357）。**回放证明收紧红线无效**（裕度取 0 仍有 52 步劣化）。
- 🔧 **下一步（最优先）**：基线采样 321 → 640～960 点（离线约 +18 min，算法不改），再评估严格泛化。

v2 及更早产物已归档到 `archive/20260910_ddps_v2_pre_ctle_reorder/`（磁盘，不入库）；
红线标定用的 margin = 0.6 trace 在 `archive/20260910_ddps_v3_margin060_calibration/`。当前分支 `physical-model`。

## 二、非协商约束（甲方底线，别碰）

1. **7-tap 发端 FIR 探针是固定约束**（`tx_channel_extract.extract_tx_s21(num_taps=7)`）。
   不要加抽头、不要换"更丰富发端特征"——那等于改题目。
2. **两阶段底线**：Stage 1（离线标定）可崩、可拿真实端到端 BER；Stage 2（在线调优）
   **不能崩、只能拿发端指标**（真实收端 BER 只记录验证、绝不回传方向决策）。
3. **100% 白盒**：训练/推理/梯度手写（numpy 最多）；无 sklearn/scipy.optimize 黑盒。
4. **统一 BER_MLSE 口径**：全链路指标 = MLSE(memory=1, Burg 白化) 判决输出（Gray 映射）。
5. **评估协议必须全流程一致**：262144 符号/点 × 仿真种子 (42,43,44) 取 log10 均值。
   BER 绝对值随块长系统性漂移（每翻倍约 −0.15～−0.25 dex），**不同协议的绝对 BER 不可比**。
6. **文档全中文**（README/docs），图内文字可英文。

## 三、链路顺序（v3 修正后的唯一正确顺序）

```
DAC(ZOH, ENOB) → Tx 电插损(S4P, Tx IL) → +1 mV 前端噪声 → Tx 模拟 CTLE(gDC,gDC2)
             → VGA(归一化到固定 vga_out_rms) → Driver 真增益(driver_gain) → Driver 带限
             → MZM → 光纤(CD/DGD) → PIN(+散粒/热噪) → TIA → Rx PCB(Rx IL) → ADC → Rx DSP
```

实现集中在 `channel_imdd.tx_frontend_lti()`，**物理探针 `tx_channel_extract` 与真实链路共用它**，
因此改链路顺序只需改这一处。

## 四、踩过的坑（已修，勿回退/勿重犯）

### 4.1 v1/v2 的钱坑（仍然有效）

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

### 4.2 v3 新修的坑（v2 的两个建模错误）

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

## 五、v3 标准流程（复现命令）

```bash
# 1) 数据集（1175 行；11 维 LHS；多进程；与串行逐位一致）
python dataset_generator.py --base-samples 320 --anchor-samples 60 \
    --num-symbols 262144 --sim-seeds 42,43,44 --jobs 14

# 2) 训练两套模型：带锚点（上限参考）与只用基线（严格泛化）
python -c "from train_surrogates import train_v3; import glob; \
  train_v3(sorted(glob.glob('dataset/ddps_v3_dataset_*.csv'))[-1], 'models/ddps_v3')"
python run_ddps_v3_control.py --dataset dataset/ddps_v3_dataset_<ts>.csv \
    --base-env Base_IL10x10 --model-dir models/ddps_v3_control \
    --test-out result/ddps_v3_control --num-symbols 262144 --sim-seeds 42,43,44

# 3) 在线调优泛化测试（核心 / 消融）
python test_generalization.py --model-dir models/ddps_v3 --out-dir result/ddps_v3_<ts> \
    --num-symbols 262144 --sim-seeds 42,43,44 --n-steps 15 --cloud-n 8
python test_generalization.py --model-dir models/ddps_v3_control \
    --out-dir result/ddps_v3_control_ffe_only --freeze-extra \
    --num-symbols 262144 --sim-seeds 42,43,44 --n-steps 15

# 4) 报告与跨实验汇总
python report_ddps_v3.py --test-dir result/ddps_v3_<ts> --model-dir models/ddps_v3 \
    --deep-symbols 524288 --summary "result/ddps_v3_control:只用基线" \
    "result/ddps_v3_<ts>:带锚点" "result/ddps_v3_control_ffe_only:消融(冻结 CTLE+增益)"
```

## 六、当前产物索引

- 数据集：`dataset/ddps_v3_dataset_<ts>.csv`（含 `driver_gain` / `drive_rms` / `ber_std_log10`）
- 模型：`models/ddps_v3/`（带锚点）、`models/ddps_v3_control/`（只用基线），均含 `meta.json`
- 结果：`result/ddps_v3_<ts>/`、`result/ddps_v3_control/`、`result/ddps_v3_control_ffe_only/`
  （`case_summary.csv/json`、`trace_<用例>.csv`、`run_config.json`、`report/`）
- 汇总：`result/SUMMARY.md`（跨实验对照）
- 对外交付件：`DDPS_v3_Deliverable.html`
- 旧版本归档：`archive/20260910_ddps_v2_pre_ctle_reorder/`（含 README 说明为何不可比）

## 七、已知边界（诚实记录，勿包装成成功）

1. Model A/B 的**绝对标定弱**（欠/过估真实 BER），只用其排序/方向；绝对阈值需另行校准。
2. **`driver_gain` 最优值依赖标定摆幅**：`vga_out_rms` 按 "gain=2.0 ⇒ 0.617 Vpp" 定，
   器件标定变化会让最优增益区间整体平移。
3. **CTLE 频响形状固定**：只优化双级直流增益，零点/极点比例不在搜索空间内。
4. **BER 随块长漂移**：报告必须注明协议；跨协议比较无意义。
5. 种子邻域内"优于种子"的点很少，Stage-2 的增益主要来自信任域内较大步幅的移动。
