# DDPS v5 任务交接说明

> 给接手的 Agent。先读 [09. DDPS v5 模型与算法口径](docs/09_DDPS_v5_Model_Update.md) +
> [04. DDPS 寻优架构](docs/04_DDPS_Optimization.md)，再动手。
> 重点看「非协商约束」与「踩过的坑（已修，别回退）」。
> v4 及更早见 [08. DDPS v4](docs/08_DDPS_v4_Model_Update.md)（v4 的"预测降/实测升"根因与 v5 修法在 09）。

## 一、一句话现状

DDPS 已按甲方口径重做为 **v5**（修复 v4 的"预测降/实测升"）：

- **链路**：`FFE → DAC → Tx 电插损 → 1mV 噪声 → CTLE → Driver(可调增益) → Driver 带限 → MZM`。
  **没有 VGA、没有任何 RMS 归一化** —— 入 MZM 摆幅就是"前端电平 × 增益"，因此增益是名副其实的自由度。
- **三组自由度分工（v5 关键改动）**：
  - **gain 维**：**不进代理、不走梯度下降**。每个用例单独细粒度扫描标定自己的 target_rms
    （0.06~0.22 V，步长 0.005），在线调优时每步解析调到该用例的 target_rms。
    因 `drive_rms ∝ gain` 且 k 随 IL 变，解析出的 gain 倍率自动从强信号环境的 ~0.6 调到
    弱信号环境的 ~1.3。**不求几何均值**——每个用例独立优化。
  - **FFE/CTLE**：仍走基线代理泛化（核岭 6 维，R²=0.72）。扫描证实 CTLE 最优方向跨环境一致
    （11/15 case 最优 gDC=−3），可泛化。
- **根因**（v4 坏在哪）：gain 维最优方向随环境反转（基线该降、高插损该升），v4 把它交给基线训练的
  代理盲驱，于是在恶劣环境反方向驱动。v2/v3 能成是因为 gain 被锁死。"训练看不到恶劣信道"是借口。
- **Driver 增益标定**：`tools/calibrate_driver_gain.py` 实测 `DRIVER_GAIN_NOMINAL = 0.4381`，
  使基线种子配置的 MZM 摆幅 = 0.617 Vpp；`create_config.py` 默认值与之一致。
- **拦截判据**：Model B 按 **预测变差百分比**（≤ +25%）放行/否决。
- **数据**：**只用基线环境（IL10x10）** 采样 2000 点，gain 在目标 RMS 附近**窄带**采样（倍率 ×0.40~×0.90），
  使 FFE/CTLE 形状→BER 关系不被增益模糊。
- **评估协议**：262144 符号/点 × 3 仿真实例种子取 log10 均值。

v4 及更早产物已归档到 `archive/20260911_ddps_v4_pre_v5/`、`archive/20260911_ddps_v4_11dim_kernelRidge/`、
`archive/20260911_ddps_v3_pre_no_vga/` 等（磁盘，不入库）。当前分支 `physical-model`。

## 二、非协商约束（甲方底线，别碰）

1. **gain 维不能交给信道盲的代理盲驱**：v5 的 x_shape = `[4 FFE 旁瓣, gDC, gDC2]`（6 维），
   gain 由发端 RMS 物理目标解析驱动。**不要**把 gain 塞回模型输入（会重现 v4 的反方向驱动）。
2. **两阶段底线**：Stage 1（离线标定）可崩、可拿真实端到端 BER；Stage 2（在线调优）
   **不能崩、只能拿发端指标**（真实收端 BER 只记录验证、绝不回传方向决策）。
3. **100% 白盒**：训练/推理/梯度手写（numpy 最多）；无 sklearn/scipy.optimize 黑盒。
4. **统一 BER_MLSE 口径**：全链路指标 = MLSE(memory=1, Burg 白化) 判决输出（Gray 映射）。
5. **评估协议必须全流程一致**：262144 符号/点 × 仿真种子 (42,43,44) 取 log10 均值。
6. **训练数据只用基线环境**：其余 14 场景必须零样本参与测试，否则泛化结论作废。
7. **拦截只能用相对量**：Model B 判据是"预测 BER 相对种子变差 ≤ MAX_DEGRADE_FRAC（25%）"。
8. **三组自由度必须都能被驱动**：FFE/CTLE 走代理梯度，gain 走发端 RMS 物理目标——
   若某维不被驱动，说明特征/链路把它抵消了，必须先修。
9. **文档全中文**（README/docs），图内文字可英文。

## 三、链路顺序（v4/v5 一致，唯一正确顺序）

```
DAC(ZOH, ENOB) → Tx 电插损(S4P, Tx IL) → +1 mV 前端噪声 → Tx 模拟 CTLE(gDC,gDC2)
             → Driver(真实增益 g, 可调) → Driver 带限(40 GHz) → MZM
             → 光纤(CD/DGD) → PIN → TIA → Rx 电插损(S4P, Rx IL) → ADC → Rx DSP
```

- 实现集中在 `channel_imdd.tx_frontend_lti()`；物理探针 `tx_channel_extract` 与真实链路共用它。
- **禁止再加 VGA / RMS 归一化**：任何"后级把幅度归一化掉"的结构都会让 driver_gain 失去意义。

## 四、踩过的坑（已修，勿回退/勿重犯）

### 4.1 v5 修的坑（v4 的失败根因）

1. **gain 维方向随环境反转**：基线最优 gain 偏低（防 MZM 削顶），高插损最优 gain 偏高（补摆幅）。
   v4 把 gain 交给基线代理盲驱（代理对 gain 梯度永远是"降 gain"），在恶劣环境反方向驱动
   → "预测降、实测升"。**v5 把 gain 移出代理，改用发端 RMS 物理目标解析驱动。**
2. **数据集 gain 全箱采样会模糊 FFE/CTLE 方向**：v4 在整箱 gain 采样时模型 R² 仅 0.28。
   v5 在目标 RMS 附近窄带采样，R² 升到 0.72。
3. **target_rms 必须每个用例单独扫描标定**：不是拍脑袋，也不求几何均值。
   `scratch/scan_per_case_rms.py` 对每个用例细扫 RMS（0.06~0.22V，步长 0.005），
   各取最优。换器件后重跑扫描。

### 4.2 v1/v2/v3/v4 的老坑（仍然有效）

1. **LHS 采样器维度与索引必须一致**。
2. **S4P 频率缩放的群时延漂移**：`_peak_idx_for_env` 按信道环境缓存。
3. **代理趋平要停**：保留梯度门控 `GRAD_GATE` 与边际收益门控 `MIN_GAIN_DEX`。
4. **安全红线用百分比**（`MAX_DEGRADE_FRAC=0.25`），不退回绝对 BER 阈值。
5. **不要给 Tx 前端加 VGA/RMS 归一化**。
6. **CTLE 位置**：放在电插损之后、Driver 之前。不要挪回 DAC 输出处。

## 五、v5 标准流程（复现命令）

```bash
# 0) 标定 Driver 增益（换器件时重跑）
python tools/calibrate_driver_gain.py

# 1) 数据集：只用基线环境，gain 窄带采样（使 FFE/CTLE 方向清晰）
python dataset_generator.py --base-samples 2000 --anchor-samples 0 \
    --only-envs Base_IL10x10 --num-symbols 262144 --sim-seeds 42,43,44 \
    --jobs 12 --core-samples 1200 --v5 --v5-gain-lo 0.40 --v5-gain-hi 0.90

# 2) 训练 Model A / B（6 维 FFE+CTLE 核岭，gain 维不进模型）
python -c "from train_surrogates import train_v5; import glob; \
  train_v5(sorted(glob.glob('dataset/ddps_v4_dataset_*.csv'))[-1], 'models/ddps_v5')"

# 3) per-case 细粒度 RMS 扫描标定（每个用例单独扫，换器件/换用例时重跑）
python scratch/scan_per_case_rms.py --jobs 12

# 4) 在线调优（15 场景，gain 用 per-case target_rms 物理驱动）
python test_generalization.py --model-dir models/ddps_v5 --out-dir result/ddps_v5_main \
    --v5 --n-steps 15 --num-symbols 262144 --sim-seeds 42,43,44

# 5) 报告与交付件
python report_ddps_v5.py --test-dir result/ddps_v5_main --model-dir models/ddps_v5 \
    --summary "result/ddps_v5_main:gain发端RMS物理驱动+FFE/CTLE代理泛化" \
    --summary-out result/SUMMARY.md
python make_deliverable_v5.py --baseline result/ddps_v5_main --model-dir models/ddps_v5
```

## 六、当前产物索引

- 数据集：`dataset/ddps_v4_dataset_<ts>.csv`（2001 行，基线环境，gain 窄带）
- 模型：`models/ddps_v5/`（model_a.pkl / model_b.pkl / meta.json，6 维）
- 扫描标定：`result/per_case_target_rms.json`（15 用例各自的 target_rms）、
  `result/per_case_rms_scan.csv`（细粒度 RMS 扫描全量数据）
- 结果：`result/ddps_v5_main/`（case_summary、trace_<用例>.csv、run_config.json、report/）
- 报告：`result/ddps_v5_main/report/ddps_v5_convergence.png`（三曲线核心图）、
  `ddps_v5_gain_rms.png`（gain 物理驱动轨迹图）、`ddps_v5_report.md`
- 汇总：`result/SUMMARY.md`
- 交付件：`DDPS_v5_Deliverable.html`（由 `make_deliverable_v5.py` 生成，自包含）
- 方法记录：`docs/09_DDPS_v5_Model_Update.md`
- 旧版本归档：`archive/20260911_ddps_v4_pre_v5/`、`archive/20260911_ddps_v4_11dim_kernelRidge/`、
  `archive/20260911_ddps_v3_pre_no_vga/`、`archive/20260910_ddps_v2_pre_ctle_reorder/` 等

## 七、已知边界（诚实记录，勿包装成成功）

1. **marginal_gain 停止基于代理预测**：gDC2 走到边界 −3.0 后代理预测改善 <0.01 dex 即停，
   终点可能略劣于最优步，但终点仍远优于种子（15/15 用例终点不劣于种子）。
2. **per-case target_rms 是离线标定的**：每个用例的 target_rms 由 `scratch/scan_per_case_rms.py`
   在种子 FFE/CTLE 下扫描标定。换器件后需重跑扫描。
3. **CTLE 频响形状固定**：只优化双级直流增益，零点/极点比例不在搜索空间内；gDC2 边界 −3.0 限制进一步峰化。
4. **BER 随块长漂移**：报告必须注明协议；跨协议比较无意义。
5. **模型绝对标定弱**：只用其 FFE/CTLE 方向；gain 维完全由物理目标处理。
6. **恶劣 case 绝对 BER 仍在 1e-2 量级**（IL20x20=3.1e-2、Comb_IL20x20=5.1e-2）：
   若要压到 1e-3，需把 CTLE 零极点纳入搜索空间（下一步）。
