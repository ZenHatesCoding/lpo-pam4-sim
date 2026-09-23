# DDPS 版本变更记录

> 本文件记录每个版本的核心变化。只记"变了什么"，不记排错过程。

## v6.2.2（当前版本）

### 代码去版本号 + 历史死代码归档 + MLSE 向量化（2026-09-23）
- **MLSE 向量化（算法等价）**：`mlse_burg.py` 把 Viterbi ACS 改为 NumPy 向量化（memory 0/1），原始标量实现保留为 `_viterbi_mlse_pam4_ref`；入口 `viterbi_mlse_pam4(..., fast=True)` 默认快速分支、`fast=False` 回退原始实现，两条分支逐位一致（生产 memory=1 提速约 2.3×）。开关 `config['system']['mlse_fast']`（默认 True）。LMS/DFE 未动（LMS 是逐样本自适应迭代、无法在不改算法的前提下向量化；DFE 是备用接口）。
- **去版本号命名**：函数 `train_v6→train`、`_stage2_descent_v62→_stage2_descent`、`_stage2_descent_v62_aonly→_stage2_descent_aonly`、`_bounds7→_bounds`、`_grad_a_chain7→_grad_a_chain`、`run_case_v62→run_case`、`run_case_v62_aonly→run_case_aonly`；脚本 `report_ddps_v6.py→report_ddps.py`、`make_deliverable_v6.py→make_deliverable.py`；`test_generalization.py`/`tools/run_parallel_envs.py` 删除 `--v5/--v6/--v62/--target-rms/--cloud-*/--freeze-extra` 死参数。规则写入 AGENTS.md「代码命名」。
- **历史死代码归档**：`archive/20260923_code_versioned_snapshot/` 快照去版本号前的全部 DDPS 代码（现版本 + v2~v6.1 历史函数）；死脚本 `compare_surrogates.py`、`make_deliverable_compare.py`、`make_result_summary.py` 移入 archive 并移出远端。
- **文档以代码为准**：修正「无 VGA/无 RMS 归一化」表述（Tx driver 路径无 RMS 归一化；Rx 侧 TIA/ADC 各有一级 AGC）；HANDOFF 增补「待办（bug/隐患）」清单。

### 在线调优演示改用次优起点（冷启动）
- v6.2.1 的在线调优从 per-case RMS 标定 gain 出发，gain 已接近各用例最优，多个强信号用例起点即 0 错误（低于检测限），看不到在线调优的下降过程。
- 本版改为从一个明确的**次优工作点**出发（7 维全部给定），取自训练数据实测点 `Base_IL10x10:683`（基线环境真实 BER ~1e-5，极端插损组合 ~1e-3）：
  - Tx FFE 5 抽头 `[-0.0654, -0.2834, 0.5587, -0.0045, 0.0880]`（主抽头 0.5587 派生）
  - Tx CTLE `gDC = 5.73 dB`、`gDC2 = 1.45 dB`
  - `driver_gain = 0.2728`（×0.80，`u_gain = −0.0955`）：接近标称、未按用例标定，是次优的主要来源
- 起点配置存为 `result/seed_config_bad_1e5.json`，经 `--seed-config` 传入：
  - `test_generalization.py` 的 seed-config 新增 `best_u_gain`/`best_gain` 覆盖 gain 维（此前只覆盖形状）；
  - `report_ddps_v6.py` 新增 `--seed-config`，让硬用例四联图的「种子」参照画真实次优起点（此前用模块默认名义种子）。

### 结果（15 用例，4194304 符号 × 3 种子 42/43/44）
- 次优起点种子 BER：基线 Base_IL10x10 1.20e-5，整体 1.35e-6 ~ 1.83e-3。
- 调优后最优 BER：整体 1.19e-7 ~ 7.55e-7（多数逼近检测底 1.19e-7 伪计数）。
- 15/15 全部下降，0 持平、0 退步；几何平均改善 ×186.7（v6.2.1 好种子为 ×3.40，其中 7 个用例起点即 0 错误无可下）。
- 极端插损恢复最深：IL20x20 ×3480（1.37e-3→3.95e-7，gain ×0.80→×1.11）、Comb_IL20x20_CD15_DGD5 ×2429（1.83e-3→7.55e-7）；高噪声 HighNoise_IL10x10 ×630。
- gain 维：所有用例从 ×0.80 出发被梯度推到各用例最优倍率附近（强信号 ×0.66~×0.75、弱/高损 ×0.86~×1.11）。
- A-only 与主流程结果逐用例一致（Model B 全程未触发否决）。

### 交付件口径
- 交付件 6.0「起点怎么定的」、6.1 表题、结论、3.3 gain 标定（改为「参照」）、块长研究、适用边界、复现命令均按次优起点口径刷新。
- `run_config.json` 的 gain 字段语义明确：`per_case_gain` = 本跑每用例实际作为 seed 的 gain（本版 ×0.80），`per_case_target_rms` = 离线 RMS 标定参照；`test_generalization.py` 写配置时不再把 per-case RMS 标定值误当 seed gain 写入。

### 仓库清理（2026-09-21）
- 历史产物（v2~v6.1 交付件、v6.0/v6.1 结果与模型、v4 历史数据集）归档到 `archive/20260921_repo_cleanup_v6_historical/`，git 远端只保留 v6.2 现役产物。
- 删除冗余：`models/lim_3ck_01_0319_c2m.zip`（代码只读解压目录）、根目录历史统计输出 `proof_results.txt`；归档 `LPO_MSA_Specification_v1p01.txt`（pdf 提取物）。
- 归档判据 = **现役 vs 历史**，与文件大小无关：v6.2 现役数据/模型/结果（含物理链路 s4p、`lim_3dj` 标准数据包）全部保持 git 跟踪。

### 交付件 HTML 交互化 + 全链表述修正（2026-09-21）
- 交付件交互化：6.2 图 A+B / A-only tab 切换；8 处长表/命令块 details 折叠（2.3 参数、2.4 用例、4.3 复杂度、4.4 可靠性、5 块长、5 采样口径、6.3 核验、9 复现命令）；全文 h2/h3/h4 标题级折叠（点击标题收起下属内容），打印自动展开全部。
- 新增 §4.6 部署走一遍：训练完手上有什么 → 第一步立红线 → 第一个梯度（7 维双边差分）→ 迭代收敛。
- 梯度数字全链统一：交付件 4.2/4.3/4.6/结论 + 图 4 SVG + docs/DDPS_Method、docs/DDPS_REQUIREMENTS 的"每步 8 次评估（1 基准 + 7 维扰动）"改为"7 维双边差分 = 14 探针 + 14 A 前向"，eps 分档 0.01/0.1/0.05。
- 图 1-4 审视：图 2 搜索向量 `x_shape ∈ R⁶` → `x ∈ R⁷ = [4 旁瓣, gDC, gDC2, u_gain]`，种子补 gain ×0.80，组归一化补 gain 组；图 4 种子框补 gain；第 9 节产物清单"7 维 x_shape"→"7 维 x"。
- 去 AI 味：交付件清除"本版/零重训/无第三方库/前者后者/为什么必须"等措辞。

## v6.2.1（已归档）

### BER 测量修正：BER 窗口排除 FFE 尾缘截断
- `adaptive_ffe_dfe` 的 FFE 输入索引 `idx = 2*(n + sync_delay) + ffe_pre` 在 `idx >= len(rx_sps)` 时 `continue`，使最后约 `sync_delay + ffe_pre/2` 个符号的均衡输出保持 0（垃圾判决），按固定错误数虚增 BER——块长越短越明显，表现为观察到的"每翻倍块长 BER 约 −0.3 dex"。
- 修正：BER 窗口与 Burg 噪声估计限定在有效稳态输出范围 `[train_len, n_valid)`，`n_valid = (len(rx_adc) − ffe_pre)//2 − sync_delay`（头部 LMS 训练区间原本就排除，此次补上尾部）；0 错误时用 `1/(2N)` 伪计数避免 `log10(0)`。
- 影响：修复后基准最优工作点真实 BER 已低于 2^20 点估计分辨率（2^21 × 3 种子 0 错误，95% CL < 4.8e-7）；此前报告的最优 ~2e-5 是被截断错误抬高的误测值，训练数据/模型/在线结果全部随之重做。

### 测试评估块长 2^21 → 2^22
- 在线测试的真实 BER 评估块长从 2097152 提到 4194304 符号（× 3 种子）：压力用例（~2e-5）每种子约 84 个错误、充分解析；强信号用例仍落在 0~1 错误的检测限内，用 95% CL 上界（3/N）表述，不与有效错误点混用点估计。

### 重做结果
- **数据集**：2^20（1048576）符号 × 3 种子，2001 行；`log10_ber_mlse ∈ [-6.317, -0.770]`，其中 980 行（49%）落在 0 错误检测限（-6.317 = 1/(2N) 伪计数）。
- **模型**：复用 A/B 白盒 Ridge。Model A Spearman=0.847 / R²=0.673，Model B Spearman=0.842 / R²=0.687（rho=1.752）。
- **在线测试**（15 用例，4194304 符号 × 3 种子）：**8/15 用例可测改善、0 用例退步**，几何平均改善 **×3.40**。极端插损组合改善最大：IL20x20 ×105.6（1.59e-5 → 1.51e-7）、Comb_IL20x20_CD15_DGD5 ×182.8（2.18e-5 → 1.20e-7）；中等压力次之：IL20x10_TxHeavy ×12.06、HighNoise_IL16x16 ×11.66、IL16x10 ×5.94、HighNoise_IL10x10 ×3.66、IL10x20_RxHeavy/Comb_IL20x10 ×1.26。
- **7 个强信号/弱压力用例**（Base、IL14x14、IL10x16、CD15ps、CD28ps、DGD2ps、DGD5ps）起点即 0 错误（1.19e-7 伪计数），低于 2^22 点估计分辨率，无可测改善（×1.0，保持不退化）。
- A-only 消融（15 用例，同协议）：与主流程**逐点一致**（IL20x20 ×105.6、Comb_IL20x20 ×182.8 等全部相同），Model B 风险控制全程未触发拦截——确认为"保险"而非被依赖的拦截。

## v6.2（已归档）

### gain 纳入梯度（第 7 维）
- gain 从"锁定 per-case target_rms"改为**第 7 个搜索维**：参数向量 `x = [4 FFE 旁瓣, gDC, gDC2, u_gain]`，`u_gain = log10(g / g0)`。
- gain 初值仍来自每个 case 单独扫描最优 RMS 解析得的 gain（不是标称值），之后放开走 Model A 的**7 维链式梯度**（gain 维扰动 u_gain → 重算探针，只有 drive_rms 变）。
- gain 信任域收紧到 `±0.15 dex`（围绕 per-case 初值），防止跨环境方向反转；形状/CTLE 信任域不变。

### 标称 gain 重标定
- `DRIVER_GAIN_NOMINAL` 从 0.4381 改为 **0.3399**（按 peaking 链 `rms_at_unity=0.6763` 重标：`g0 = 0.617×0.3726 / 0.6763`）。旧值 0.4381 是 v4 无 peaking 链的残留常量。
- 连带修正了 per-case RMS 扫描的 GAIN_MIN 钳位：旧扫描对低 gain 用例被钳在 GAIN_MIN，报告的目标 RMS 与真实驱动 RMS 对不上（如 IL10x20_RxHeavy 旧值 0.06 → 新标 0.160，CD28ps 0.06 → 0.150）。

### 训练数据重做
- 数据集 `--v62`：driver_gain 作为独立采样维（`x_6 = u_gain`），在 u 空间均匀覆盖**全用例 per-case 最优 gain 邻域 ×0.20~×1.26**（`u ∈ [-0.70, +0.10]`，相对新标称 0.3399）。此前 v6.1 的 gain 窄带（相对旧标称 0.4381 的 ×0.40~×1.00 = 绝对 0.175~0.438）不含基线最优 gain（0.138），训练数据覆盖不到真实操作点。
- 种子行仍锚定基线 per-case 扫描最优 gain；采样盒 7 维 LHS；块长 1048576 符号 × 3 种子（约 2001 行）；12 进程并行。

### 模型 / 结果
- 复用 A/B 白盒 Ridge 结构（A 8 维探针、B 7 维参数域；gain 经 drive_rms 进入两代理）。Model A Spearman=0.832 / R²=0.666，Model B Spearman=0.835 / R²=0.702（rho=1.752）。
- 在线测试（15 用例，2097152 符号 × 3 种子）：**14/15 用例相对起点改善、1 用例持平、0 用例退步**；几何平均改善 ×1.09（最高 ×1.50，Comb_IL20x20_CD15_DGD5）；全程 198 步真实 BER，27 步劣于起点（B 拦截全程未触发）。
- A-only 消融与主流程基本一致（Comb_IL20x20 在 A-only 下 ×1.52 略高于主流程 ×1.49），确认 B 拦截是"保险"而非被依赖的拦截。

## v6.1（已归档）

### 物理层修正
- Tx CTLE 拓扑改为 OIF 2Z3P peaking 形式：分子 `1 + jf·(K_DC/fz)`，零点位于 `fz/K_DC`，直流增益恒 0 dB。`g_dc_db` 语义改为高频 peaking gain（dB）。原实现 `(g_dc + jf/fz)` 在 `fz==fp1` 时零极点对消成低通，Nyquist 处反而衰减。
- CTLE 零极点比例改为 SJTU 标准：`fz=fb/2.862, fp1=fb/1.884, fp2=fb, flf=fb/40`。
- 新增 Rx 模拟 CTLE 级（TIA→Rx IL→Host Rx 噪声→Rx CTLE→ADC），固定参数 `gDC=6 dB, gDC2=3 dB`（SJTU standard），不参与优化，作为静态均衡基座。
- CTLE 优化边界改为 peaking 语义：`g_dc ∈ [0,12] dB, g_dc2 ∈ [0,4] dB`。种子点 `gDC=6, gDC2=2`。
- 评估符号数拉长至 2^20（数据集）/ 2^21（在线测试），可靠分辨 1e-5 量级。

### 验证
- Tx CTLE 传递函数：gDC=6 dB 时 Nyquist 处 +5.89 dB（修正前为 −7 dB）。
- 最终在线测试（15 用例，2097152 符号 × 3 种子）：15/15 改善、0 劣化，最优 BER_MLSE 全部进入 1e-5 量级（1.93e-5 ~ 4.63e-5）。
- 对比 v6（物理层修正前）：IL20x20 1.52e-3 → 4.61e-5（改善 ~33 倍）；Comb_IL20x20 7.52e-3 → 4.63e-5（~162 倍）。
- 块长研究（Base_IL10x10 最优工作点）：BER 随块长每翻倍约 −0.3 dex（LMS/MLSE 收敛效应），2^18=1.76e-4、2^19=8.21e-5、2^20=4.23e-5、2^21=1.98e-5。

## v6（已归档）

### 架构
- A=探针→BER（8 维波形域：7-tap Tx FIR + drive_rms）
- B=参数→BER（7 维参数域：4 FFE 旁瓣 + gDC + gDC2 + drive_rms）
- 梯度通过 A 的链式法则：扰动 6 维参数 → 重算探针 → 查 A → 得 ΔBER
- gain 不在 A/B 搜索向量，由 per-case target_rms 物理驱动

### 物理层
- 5-tap Tx FFE → DAC → Tx IL → CTLE → Driver → MZM → 光纤 → PIN → TIA → Rx IL → ADC → Rx FFE → MLSE
- 无 VGA，无 RMS 归一化

### 结果
- 15/15 用例正向改善，平均 ×5.16，最高 ×39.44
- 153 步 0 劣化
- CTLE 激活 12/15（gDC 调到 ±2.5）
- A-only 与 A+B 结果完全一致（B 红线全程未触发）

### 安全红线
- 红线 = 当前最优点 B 预测 × 1.25（随最优点下移，不用种子点 B 预测）

### 三组训练对比实验
- 组 A 基线训练 (IL10x10, 工程标定种子): ×5.16, 15/15, 0 劣化
- 组 B IL20x20 训练 (BO 寻优种子, gDC2=-4.95): ×2.66, 14/15, 11 劣化
- 组 C IL20x20 训练 (梯度下降终点种子, gDC2=-2.66): ×6.67, 12/15, 41 劣化
- 结论: 低损环境训练泛化性最好；种子点选择决定模型对哪个区域学得准

## v5（已归档）

- 6 维 x_shape 统一输入（A/B 共用），gain 发端 RMS 物理驱动
- 架构错误：A/B 输入空间相同，误差不独立
- 9-tap FFE，VGA 归一化

## v4（已归档）

- 11 维搜索空间（9-tap FFE + gDC + gDC2 + gain）
- KernelRidge 代理
- VGA 固定 RMS 归一化

## v3（已归档）

- 修正 Tx 链 CTLE 位置和 driver_gain 被 VGA 抵消的问题
- 9-tap FFE，绝对 0.3 log10 安全裕度

## v2（已归档）

- 首次跨环境泛化验证（8 环境）
- 9-tap FFE，7-tap 探针
- 修复 v1 的符号格错位、梯度门控缺失等问题

## v1（已归档）

- 初始版本，负向优化（Model A 下降但真实 BER 反向变差）
- 根因：Stage-1 邻域采样死代码、FFE 参数化不一致、符号格错位
