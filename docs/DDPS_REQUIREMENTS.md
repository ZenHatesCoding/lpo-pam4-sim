# DDPS 交付件与重做要求清单

> 本文件是所有要求的沉淀。每次重做前必读。不在这里的要求不复提。

## 一、架构要求（v6.2，不可改）

### A/B 模型分工
- **Model A（方向代理）**：输入 = [7-tap Tx FIR 探针, drive_rms]（8 维波形域）→ log10(BER) 条件均值。WhiteBoxRidge（二阶多项式 + L2 Ridge 闭式解，带解析梯度）。
- **Model B（风险控制）**：输入 = [4 FFE 旁瓣, gDC, gDC2, drive_rms]（7 维参数域）→ log10(BER) 保守上包络。WhiteBoxRidge。
- **A/B 输入空间不同**（波形域 vs 参数域），误差来源相互独立。
- **梯度**：通过 A 的链式法则——扰动 7 维参数 → 重算探针（含 CTLE！）→ 查 A → 得 gᵢ=(A⁺−A⁻)/(2·epsᵢ)（7 维双边中心差分，eps 分档 0.01/0.1/0.05）。每步 14 次探针 + 14 次 A 前向。
- **gain**：第 7 个搜索维（`u_gain = log10(gain / 0.3399)`），经 drive_rms 进入 A/B 输入，参数箱信任域 ±0.15 dex。per-case target_rms 扫描（0.06~0.22V）作为各用例最优 gain 的离线标定参照。

### 物理层（v6.2 口径）
PAM4 → 5-tap Tx FFE → DAC(ZOH,ENOB 5.5) → Tx IL(S4P) → +1mV 噪声 → Tx CTLE(gDC,gDC2, peaking) → Driver(gain) → Driver BW(40GHz) → MZM(Vπ=3,bias=2.25,ER=25dB) → 光纤 → PIN → TIA → Rx IL → +1mV 噪声 → Rx CTLE(固定 gDC=6/gDC2=3) → ADC → Rx FFE(22-tap,LMS) → Burg → MLSE(memory=1)。**无 VGA，无 RMS 归一化。**
- Tx CTLE 为 OIF 2Z3P peaking 拓扑（`gDC` = 高频 peaking gain，直流增益恒 0 dB；`gDC2` = LF shelf gain），零极点比 `fz=2.862/fp1=1.884/fp2=1/flf=40`。
- Rx CTLE 与 Tx 同一拓扑但参数固定（`gDC=6, gDC2=3`），不参与寻优。

### 关键常量
- SEED_TAPS=[-0.034,-0.299,0.609,0,0.058]（5-tap，FFE_PRE=2，主抽头 t2）；次优起点的 FFE 见 `result/seed_config_bad_1e5.json`
- DRIVER_GAIN_NOMINAL=0.3399；次优起点 driver_gain=0.2728（×0.80，u_gain=−0.0955）
- 步骤：GD 步长 0.05 × 0.97^k × 箱宽（组内归一化），GROUP_GATE=1e-3，MIN_GAIN_DEX=0.01
- MAX_DEGRADE_FRAC=0.25
- 信任域 = 2.0 × ρ（ρ = 32nd nearest neighbor median in B's param domain）

## 二、安全红线逻辑（已修正）

### 根因
- 旧逻辑：红线 = 10^(Model B 对种子的预测) × 1.25
- Model B 用基线训练，在漂移环境预测的绝对值不可信（IL20x20: B预测=2.3e-4 vs 真实=6.0e-2，差260倍）
- 导致红线在多数用例比种子还好（allowed/seed < 1），逻辑矛盾

### 正确逻辑（已实现）
- 红线 = **当前已知最优点**的 Model B 预测 BER × (1 + MAX_DEGRADE_FRAC)
- 每步若 B 预测改善，红线跟着下移——B 单调下降时红线永不触发
- 若 B 预测突然变差（方向错），红线才挡住该步
- 不用种子点的 B 预测（绝对值不可信），用"相对最优点变差 25%"

## 三、对比实验：A-only vs A+B（已实现）

### 实现
- `ddps_optimizer.py` 新增 `_stage2_descent_v62_aonly()`：只用 A 梯度，不查 B，不走安全拦截
- `test_generalization.py` 新增 `--a-only` 标志和 `run_case_v62_aonly()` 函数
- 结果输出到 `result/ddps_v6_2_aonly/`
- 交付件 §6.1/6.2b 显示逐用例对比表与同款图

### 判读标准
- 如果 A-only 就 0 劣化步，说明 Model A 方向已足够好，B 的价值是"保险"而非"必需"
- 如果 A-only 有劣化步而 A+B 没有，说明 B 确实拦住了错误方向

## 三b、对比实验：训练环境对比（历史，v6.0 时代，已归档）

> 该实验系 v6.0 时代三组训练对比（基线 vs IL20x20 两种种子），结果已归档在 `archive/`。当前版本（v6.2）只用基线训练单套模型，不再做训练环境对比。

### 实现
- 三组：基线训练(IL10x10) vs IL20x20(BO种子) vs IL20x20(梯度下降种子)
- `optimizers/bo_search_il20.py`：贝叶斯优化在 IL20x20 上搜 6 维全局最优种子点
- `dataset_generator.py --base-env IL20x20 --seed-config result/il20_bo_seed.json`：用 BO 种子点邻域采样
- `test_generalization.py --seed-config result/il20_bo_seed.json`：用 BO 种子点做 Stage-2 起点
- `make_deliverable_compare.py`：三组对比交付件
- 新旧数据/模型/结果全部分开存储：`dataset_il20/`, `models/ddps_v6_il20/`, `result/ddps_v6_il20_main/`

### 判读标准
- 基线训练应最稳健（15/15 正向，0 劣化）
- 高损环境训练在重损环境更优但泛化性下降
- 种子点选择决定模型对哪个区域学得准

## 四、交付件要求（AGENTS.md 硬规矩）

### 资产负债表原则
- 只讲现状：系统现在是什么样、能干什么、结果数字是多少
- 不假设读者有前置信息，只看这一个材料就能看懂
- 不从"为什么改、怎么修"开始，不写排错过程
- 不提"上一版/前一版/v3/v4/v5"
- 不用"消融""锚点""上限参考"等对照实验语言

### 图的要求
- 图例必须清晰：figure 级统一图例，不要挤在子图内
- 每条线/每个点都要有明确标注
- 收敛图要有三条线：Model A 预测、Model B 预测、实测 BER + 种子线 + 安全红线
- 四联图（最难用例）：收敛轨迹 + FFE 抽头对比 + CTLE 频响 + 探针 FIR
- 散点图按物理类别着色（基线/IL/CD/DGD/复合/高噪）
- 安全红线如果逻辑正确且从不触发，图上可以不画或标注"全程未触发"

### 表的要求
- 每个表有真实数据，无占位行
- 列标题清晰（中文，带单位）
- 无空洞的"无 XX 对照组"表
- 科学计数法格式统一（如 3.75e-04）

## 五、文档要求
- 所有重做要求沉淀到本文件
- 代码变更记录到 docs/ 和 git commit
- 交付件不包含版本历史、排错过程
