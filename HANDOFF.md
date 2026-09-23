# HANDOFF — DDPS

> **新 session 必读**：下一轮要做的全部事，看下方 **「## 待办：v7 全流程重做」+「## v7 开工检查清单」**。上面的「当前状态 / session 做的事 / 物理层 / 架构 / 复现命令」是背景与上下文。动手前先读 `AGENTS.md`。

## 当前状态（本次 session 结束点）

在线调优演示改用**次优工作点冷启动**（v6.2.2）。上一版从 per-case RMS 标定 gain 出发，gain 已接近各用例最优，多个强信号用例起点即 0 错误（检测限下），看不到在线调优的下降过程；本版改为从一个基线约 1e-5 的次优点出发，让 15 用例全部可见下降。

- **种子（次优工作点，7 维全给定）**：取自训练数据实测点 `Base_IL10x10:683`。Tx FFE 5 抽头 `[-0.0654, -0.2834, 0.5587, -0.0045, 0.0880]`（主抽头 0.5587 派生）、Tx CTLE `gDC=5.73 dB, gDC2=1.45 dB`、`driver_gain=0.2728`（×0.80，`u_gain=-0.0955`）。gain 接近标称、未按用例标定，是次优的主要来源。存 `result/seed_config_bad_1e5.json`。
- **在线测试结果**（15 用例，4194304 符号 × 3 种子 42/43/44）：**15/15 全部下降，0 持平、0 退步**，几何平均 **×186.7**。种子 BER 1.35e-6 ~ 1.83e-3（基线 Base 1.20e-5）；调优后最优 BER 1.19e-7 ~ 7.55e-7（多数逼近检测底）。最深：IL20x20 ×3480（gain ×0.80→×1.11）、Comb_IL20x20_CD15_DGD5 ×2429；高噪声 HighNoise_IL10x10 ×630。gain 维从 ×0.80 被梯度推到各用例最优倍率附近（强信号 ×0.66~×0.75、弱/高损 ×0.86~×1.11）。
- **A-only 消融**（15 用例，同协议）：与主流程逐用例一致，Model B 全程未触发否决（价值仍是"保险"）。
- **交付件交互化**：`deliverables/DDPS_v6.2_Deliverable.html` 全文 h2/h3/h4 标题可点击折叠（大纲式），6.2 图 A+B / A-only tab 切换，8 处长表/命令块 details 折叠；打印自动展开全部。梯度口径统一为 7 维双边差分（14 探针 + 14 A，eps 0.01/0.1/0.05）。
- 旧（好种子）结果已归档：`result/ddps_v6_2_main` → `archive/ddps_v6_2_main_goodseed`、`result/ddps_v6_2_aonly` → `archive/ddps_v6_2_aonly_goodseed`（archive/ gitignored）。

## 本次 session 做的事

1. **选次优种子**：扫描训练数据 `dataset/ddps_v62_dataset_20260920_163244.csv`，选基线约 1e-5、gain 接近标称的实测点，导出 `result/seed_config_bad_1e5.json`。
2. **seed-config 支持 gain 维**：`test_generalization.py` 的 `--seed-config` 新增 `best_u_gain`/`best_gain` 覆盖 gain（此前只覆盖形状/CTLE）。
3. **报告修 seed 参照**：`report_ddps.py`（原 `report_ddps_v6.py`）新增 `--seed-config`，硬用例四联图的"种子"参照画真实次优起点（此前用模块默认名义种子）。
4. **交付件口径刷新**：`make_deliverable.py`（原 `make_deliverable_v6.py`）6.0"起点"、6.1 表题、结论、3.3 gain 标定改"参照"、块长研究、复现命令，全部按"次优起点冷启动"口径重写。
5. **全量重跑**（主流程 + A-only，2^22 × 3 种子，4 jobs，实测各 ~7h）→ `result/ddps_v6_2_main`、`result/ddps_v6_2_aonly`。
6. **报告 + 交付件**：`report_ddps.py`（原 `report_ddps_v6.py`，带 `--seed-config`）+ `make_deliverable.py`（原 `make_deliverable_v6.py`）→ `deliverables/DDPS_v6.2_Deliverable.html`。
7. **run_config 如实记录 seed gain**：`test_generalization.py` 写 `run_config.json` 时，`per_case_gain` 现在写的是本跑每个用例实际作为 seed 的 gain（`--seed-config` 覆盖时为覆盖值），不再误写 per-case RMS 标定值；`per_case_target_rms` 仍记离线标定参照。两处 `run_config.json` 已回填 ×0.80。
8. **文档刷新到现状 + 去 AI 味**：修复交付件里 v6.1 残留（图 2/图 4 SVG 的 "gain 不在搜索向量""d=6""安全参考=Model B(x₀)" 等旧文字，参数表 gDC 范围）；刷新 README/BRANCHES/result SUMMARY/docs 01/02/DDPS_Method/DDPS_REQUIREMENTS 到 v6.2.2 口径（7 维含 gain、次优起点、2^22 协议、×186.7、标称 0.3399）。版本号维持对外 v6.2 / 内部 v6.2.2，不升 v7（架构/链路/搜索空间/算法均未变，只改演示起点与元数据）。
9. **仓库清理归档**：历史产物（v2~v6.1 交付件、v6.0/v6.1 结果与模型、v4 历史数据集）归档到 `archive/20260921_repo_cleanup_v6_historical/`（本地保留、移出远端）；删除冗余 `models/lim_3ck_01_0319_c2m.zip`（代码读解压目录）与 `proof_results.txt`（历史统计输出）；归档 `LPO_MSA_Specification_v1p01.txt`（pdf 提取物）。判据是现役 vs 历史，与大小无关——现役数据/模型/结果（含物理链路 s4p）保持跟踪。

## 本轮 session（交付件交互化 + 表述修正）

1. **交付件 HTML 交互化**：6.2 图改 tab 切换（A+B / A-only）；第 9 节复现命令、4.3 复杂度、4.4 可靠性、2.3 参数表、2.4 用例表、5 块长表、5 采样口径、6.3 核验表共 8 处 details 折叠；全文 h2/h3/h4 标题级折叠（点击标题收起下属内容，打印时自动展开、打印后恢复）。
2. **梯度数字全链修正**：交付件 4.2/4.3/4.6/结论 + 图 4 两个 SVG + docs/DDPS_Method、docs/DDPS_REQUIREMENTS 里的"每步 8 次评估（1 基准 + 7 维扰动）"统一改为"7 维双边中心差分 = 14 次探针 + 14 次 A 前向"，eps 分档补齐 0.01/0.1/0.05。
3. **图 1-4 审视修正**：图 2 搜索向量 `x_shape ∈ R⁶` → `x ∈ R⁷ = [4 旁瓣, gDC, gDC2, u_gain]`，种子补 gain ×0.80，组归一化补 gain 组；图 4 种子框补 gain；第 9 节产物清单"7 维 x_shape"→"7 维 x"。新增 §4.6 部署走一遍（训练完 → 第一步 → 第一个梯度 → 迭代）。
4. **去 AI 味**：交付件清除"本版/零重训/无第三方库/前者后者/为什么必须/接近标称"等措辞。

## 本轮 session（去版本号 + 归档 + MLSE 向量化 + 待办）

1. **MLSE 向量化（算法等价，可回退）**：`mlse_burg.py` 把 Viterbi ACS 从三重纯 Python 循环改为 NumPy 向量化（memory=0/1），原始标量实现保留为 `_viterbi_mlse_pam4_ref`；入口 `viterbi_mlse_pam4(..., fast=True)` 默认走向量化分支、`fast=False` 回退原始分支，两条分支逐位一致（`scratch/test_viterbi_equiv.py` 验证，生产 memory=1 提速约 2.3×）。开关走 `config['system']['mlse_fast']`（默认 True）。LMS 与 DFE 未动（LMS 是逐样本自适应迭代、无法在不改算法的前提下向量化；DFE 是备用接口）。
2. **历史死代码归档**：`archive/20260923_code_versioned_snapshot/` 快照了去版本号前的全部 DDPS 代码（现版本 + v2~v6.1 历史函数）；死脚本 `compare_surrogates.py`、`make_deliverable_compare.py`、`make_result_summary.py` 移入 archive 并移出远端。
3. **去版本号命名**：函数 `train_v6→train`、`_stage2_descent_v62→_stage2_descent`、`_stage2_descent_v62_aonly→_stage2_descent_aonly`、`_bounds7→_bounds`、`_grad_a_chain7→_grad_a_chain`、`run_case_v62→run_case`、`run_case_v62_aonly→run_case_aonly`；脚本 `report_ddps_v6.py→report_ddps.py`、`make_deliverable_v6.py→make_deliverable.py`；`test_generalization.py` / `tools/run_parallel_envs.py` 删除 `--v5/--v6/--v62/--target-rms/--cloud-*/--freeze-extra` 等死参数（现役管线即默认）；`dataset_generator.py` 删除 `--v62/--v5` 开关（gain 宽口径采样即默认）。规则写入 AGENTS.md。
4. **现役产物去版本号**：目录/文件 `result/ddps_v6_2_main→result/ddps_main`、`result/ddps_v6_2_aonly→result/ddps_aonly`、`models/ddps_v6_2→models/ddps`、`dataset/ddps_v62_dataset_*→dataset/ddps_dataset_*`、`deliverables/DDPS_v6.2_Deliverable.html→deliverables/DDPS_Deliverable.html`、`result/ddps_v6_2_block_length.csv→result/ddps_block_length.csv`、报告图 `ddps_v6_*.png/md→ddps_*.png/md`；所有引用（README/HANDOFF/docs/交付件/复现命令）同步更新，冻结 meta/run_config 里的版本串一并替换。
5. **冒烟验证**：`train()` 在现有数据集上复现冻结 meta.json（A R²=0.6729 / B R²=0.6874 / rho=1.7525）；`load_models` 正常加载冻结模型；单用例 1 步端到端跑通（含 MLSE 快速分支）。

## 未提交变更（当前 working tree）

- 无。上一轮「去版本号 + 归档 + MLSE 向量化」已 commit `739fbf7` 并推送。

## 已知边界 / 元数据缺口

1. **run_config.json 的 gain 字段语义**：`per_case_gain` = 本跑每个用例实际作为 seed 的 gain（本版 = ×0.80 / 0.2728，已如实写入）；`per_case_target_rms` = 离线 RMS 标定参照（不随 seed 变化）。离线标定的完整扫描数据在 `result/per_case_target_rms.json` 与 `result/per_case_rms_scan.csv`。
2. **极端插损组合的次优种子不在 1e-5**：IL20x20 / Comb_IL20x20 起点 ~1e-3（gain ×0.80 对高损信道偏小、BER 在悬崖边缘），梯度把 gain 推高（→×1.11）恢复；属预期，交付件诚实描述。
3. 强信号用例调优后仍落在 0~1 错误检测限（1.19e-7 伪计数），改善倍数受限于检测底，用 95% CL 上界表述。
4. 改善主要来自 gain 维（第 7 维），形状/CTLE 微调为次要贡献。

## 待办：v7 全流程重做（13 条处置方案 · 已评审定案）

> 下一版本 **v7**。执行顺序：先改完所有代码并逐条验证（第 6 条用**合成单测**验证 Burg 还原 `a1`；第 10 条等价测试转正），最后全流程重跑（数据生成 → 训练 → 在线调优 → 报告 → 交付件）。被取代的 v6.2.2 全套产物（结果/模型/数据集/交付件）归档进 `archive/`（归档目录名带版本号）；重跑后的现役产物仍用不带版本号的名字（`result/ddps_main`、`models/ddps`、`dataset/ddps_dataset_*`、`deliverables/DDPS_Deliverable.html`）。「v7」只记进 CHANGELOG/HANDOFF 正文。

### 1. 真逐位 BER（`metrics.calculate_ber`）
- **现状**：`ber = ser / 2.0`，注释写「Approximation for Gray mapped PAM4」。溯源：`a989e95`（2026-07-01 初始提交，作者 Hermes Agent）第 6–15 行就存在，v1→v6.2.2 全程未改，所有结果与交付件数字都基于它。
- **问题**：SER/2 只在低误码接近真 BER；高误码（次优起点 ~1e-3）低估，最大偏约 +0.125 dex；且「BER_MLSE」错标为符号错误率/2。
- **处置（定案）**：改成真 Gray 逐位 BER——PAM4 符号 → 2 bit（Gray 映射），逐位比 `tx_bits != rx_bits`，`ber = 位错误数 / 总位数`；`ser` 保留作诊断。需新增「符号→bit」的 Gray 映射函数（当前只有符号级比较）。
- **影响**：所有 log10(BER)、改善倍数、收敛图 y 轴变真值。现有产物不存符号序列，无法重算 → 纳入 v7 全流程重跑。

### 2. ENOB 标准量化（`channel_imdd.quantize`）
- **现状**：`q = 2*max|x| / 2^ENOB`，每 block 峰值当满量程 + 确定性 mid-tread 取整。
- **正确口径**：`ENOB = (SINAD_dB − 1.76) / 6.02`（满量程单音正弦测得），等效量化噪声 `σ_q = V_FS / (2^ENOB · √12)`，V_FS 固定。
- **处置（定案）**：**DAC、ADC 满量程都固定到 ±1**（峰值 1）。quantize 用固定满量程（确定性取整 `Δ = 1/2^(ENOB-1)`，或加噪声 `σ = 1/(2^ENOB·√12)`——实现时定一种并写注释）。**不去反推满量程**；而是调 **driver 增益** 与 **TIA 增益** 做「±1 数字域 ↔ 物理域」的桥梁：driver 增益把 ±1 DAC 输出放大到 MZM 所需驱动摆幅；TIA 增益把接收信号放大到 ±1 ADC 输入。
- **影响**：driver 标称增益不再是 0.3399；`u_gain` 网格、gain 采样带（`GAIN_SAMPLE_U_LO/HI`）、per-case target 全部要变 → 训练数据集与标定参照重新生成（已在重跑范围内）。

### 3. `apply_s4p_filter` 高频硬截断
- **处置**：不改，保持现状。

### 4. 双重 AGC（并入第 2 条）
- **现状**：Rx 侧 TIA 输出归一化到 0.1863 V + ADC 数字域再归一化到 √5，两层。
- **处置（定案）**：确认是 bug。只留**一层**——TIA 那层作为「把信号定到 ±1 ADC 满量程的合适比例」的物理 AGC；ADC 数字域 √5 第二层删除。与第 2 条一起做（AGC 定电平 ↔ ADC 满量程 ↔ ENOB 是关键耦合，拆开改必自相矛盾）。

### 5. `report_ddps.py` 6 维 else 分支
- **现状**：`_has_gain_dim()` 对现役数据恒 True，`else`（6 维、drive_rms 锁定、gain 物理驱动文字）只对已归档旧数据可达。
- **处置**：把 6 维画法分支归档、现役代码删，报告只留「7 维 gain 入梯度」单一路径。

### 6. MLSE 的 a1 估计（Burg 定噪声白化抽头）
- **正确结构（简单，不是 Forney 谱分解那套）**：Viterbi 只需要 `[1, a1]` 里的 `a1`；`a1` 用 Burg 从**噪声**里定；同一个 `a1` 既当白化滤波器抽头、又当 Viterbi 目标（记忆长 1）。
- **现状**（`main.py` 139–154）：`err_ss = error_seq[train_len:n_valid]`（FFE 判决反馈段误差 `= slicer(y) − y`）→ `burg_ar(err_ss)` 得 `a1` → `pr_taps = [1, a1]` → `convolve` 白化 + Viterbi 用 `[1, a1]` 当目标。结构对，白化/目标同用同一个 `a1`、同号。
- **噪声源（定案）**：MLSE 实现时**没有真实符号**，现网只有**判决误差** `slicer(y) − y`。所以喂给 Burg 的噪声 = 判决误差 = FFE 判决反馈段误差，这正是现有代码 `error_seq[train_len:]` 在做的——**不改**。
- **处置（定案）**：① 加合成有色噪声单测——生成已知 AR(1) 系数的有色噪声 → 走「判决误差 → Burg」流程 → 验证能还原真实 `a1`（Burg 算法本体已逐行核对正确，用测试钉死）；② `E` = 白化后噪声方差 σ²，作输出**保留**（硬判决时 σ² 常数抵消、不影响判决方向，但它是 Burg 的正经输出，不丢）。

### 7. `tx_dsp.tx_ctle` 旧 CTLE
- **处置**：归档，现役只保留 `channel_imdd.apply_ctle`；`eval(custom_taps)` 注入点一并清除。

### 8. `metrics.py` 中部 import
- **处置**：`os`、`resample_poly`、`welch` 移到文件顶部。

### 9. `main.py` 的 `rx_adc[::sps_adc]` 命名
- **处置**：变量名改成表达「取 ADC 输出某一路/相位」的语义，去掉「下采样相位」的歧义。

### 10. MLSE 等价性测试转正
- **处置**：`scratch/test_viterbi_equiv.py` 挪进 `tests/` 进 git，作 fast/ref 逐位一致的常驻回归。

### 11. `optimizers/` 做干净、保留
- **定位**：用于给训练数据找格点初值，保留，不归档。
- **处置**：`optimize_tx.py` 转 UTF-8；理清 `ddps_optimizer.run_ddps` 占位 stub（不再靠 stub 兜 AttributeError）——补真实现或明确接口关系。

### 12. config.xlsx 并发重构（干净方案，不打补丁）
- **现状**：`if not os.path.exists('config.xlsx'): generate_config()` 的 TOCTOU 散在 `test_generalization.py`/`dataset_generator.py`/`tools/*`/`optimizers/*`，`test_generalization.py` 第 194 行已注释承认「实测三进程并发会把 xlsx 写坏」。
- **处置（干净重构）**：收敛成「**主进程在 spawn 任何 worker 之前统一生成/校验一次，worker 只 `load_config` 只读**」，删掉所有「缺了就就地生成」分支。并发写入口只剩主进程，从根上消除竞态。

### 13. 次优起点机制显式化（干净方案）
- **本意（用户原话）**：在线调优从「不那么好的起点」出发，**对基线来说 ~1e-4 量级的起点**。
- **现状**：模块级 `SEED_TAPS`（名义默认）+ 一堆 `--seed-config` 覆盖逻辑；当前 `seed_config_bad_1e5.json` 基线 Base 约 1.2e-5（比本意的 ~1e-4 好约 10×）；`tools/verify_tail_fix.py` 第 20 行还有一份重复 taps 常量。
- **处置（干净重构）**：① 把「次优起点」做成显式一等公民——`seed_config`（tap + gDC + gDC2 + gain/drive_rms）；② 按本意做出**基线 ~1e-4** 的次优点；③ `SEED_TAPS` 降级为「未提供 seed_config 时的兜底」并写清注释；④ 删除重复常量、统一引用。

## v7 开工检查清单（新 session 照此顺序执行）

1. **读** `AGENTS.md`（交付件原则 / 归档判据 / 代码命名）+ 本 HANDOFF 全部。
2. **代码改动（由小到大，每步 `py_compile` + import + 冒烟）**：
   - 第 8（`metrics.py` import 上移）→ 第 9（`main.py` 命名）→ 第 6（Burg 合成单测 + `E` 保留）→ 第 10（等价测试转正进 `tests/`）
   - 第 5（`report_ddps.py` 6 维 else 归档删）→ 第 7（`tx_dsp.tx_ctle` 归档）→ 第 11（`optimizers/` 转 UTF-8 + 理清 `run_ddps` stub）
   - 第 12（config.xlsx 主进程统一生成、worker 只读）→ 第 13（次优起点显式化，基线 ~1e-4）
   - 第 2 + 4（ENOB 固定 ±1 + 去双重 AGC，driver/TIA 增益做桥梁）——**注意：改完物理层后 driver 标称增益、`u_gain` 网格、gain 采样带、per-case target 全变**
   - 第 1（真逐位 Gray BER）
3. **全量验证**：第 6 条合成单测绿、第 10 条 fast/ref 等价绿、全链路冒烟（含 MLSE + 真 BER）。
4. **全流程重跑**：生成训练数据 → 训练 → 在线调优（主 + A-only）→ 报告 → 交付件。
5. **收尾**：v6.2.2 产物归档进 `archive/`（目录名带版本号）；新产物 track 进 git；CHANGELOG 记 v7；`deliverables/DDPS_Deliverable.html` 用 present 发给用户。

## 物理层

PAM4 → 5-tap Tx FFE → DAC(ZOH,ENOB 5.5) → Tx IL(S4P) → +1mV 噪声 → Tx CTLE(gDC,gDC2, peaking) → Driver(gain) → Driver BW(40GHz) → MZM(Vπ=3,bias=2.25,ER=25dB) → 光纤 → PIN → TIA → Rx IL → +1mV 噪声 → Rx CTLE(固定 gDC=6/gDC2=3) → ADC → Rx FFE(22-tap,LMS) → Burg → MLSE(memory=1)。**Tx driver 路径无 VGA、无 RMS 归一化**（gain 是链路最后一个不被下游吸收的线性乘子，故可作独立搜索维）；**Rx 侧 TIA 输出与 ADC 数字域各有一级 AGC**（分别归一化到 0.1863 V 与 √5，见 `channel_imdd.py`）。

- Tx CTLE 为 OIF 2Z3P peaking 拓扑：`gDC` = 高频 peaking gain（直流增益恒 0 dB），`gDC2` = LF shelf gain。优化边界 `gDC∈[0,12] dB, gDC2∈[0,4] dB`。
- **gain**：线性驱动增益，标称 `DRIVER_GAIN_NOMINAL=0.3399`；`u_gain = log10(gain/0.3399)`。次优种子 gain ×0.80。
- Rx DSP：LS 初始化 + 数据辅助 LMS 训练 `train_len=10000`，之后权重冻结；BER 窗口 `[train_len, n_valid)`（排除尾部垃圾符号），0 错误 `1/(2N)` 伪计数。

## 架构

- **Model A（方向代理）**：输入 = [7-tap Tx FIR 探针, drive_rms]（8 维波形域）→ log10(BER_MLSE)。WhiteBoxRidge（二阶多项式 + L2 Ridge 闭式解，带解析梯度）。
- **Model B（风险控制）**：输入 = [4 FFE 旁瓣, gDC, gDC2, drive_rms]（7 维参数域）→ log10(BER_MLSE) 保守上包络。gain 经 drive_rms 进入 B。
- **梯度（7 维链式法则）**：扰动 7 维参数（4 FFE 旁瓣 + gDC + gDC2 + u_gain）→ 重算探针 → 查 A（中心差分）。
- 信任域：形状/CTLE 不变；gain ±0.15 dex 围绕种子。

## 复现命令

```powershell
# 1) 主流程（2^22 × 3 种子，4 进程，从次优起点出发）
.venv\Scripts\python.exe tools/run_parallel_envs.py --model-dir models/ddps --out-dir result/ddps_main --seed-config result/seed_config_bad_1e5.json --n-steps 15 --num-symbols 4194304 --sim-seeds 42,43,44 --jobs 4

# 2) A-only 消融
.venv\Scripts\python.exe tools/run_parallel_envs.py --model-dir models/ddps --out-dir result/ddps_aonly --a-only --seed-config result/seed_config_bad_1e5.json --n-steps 15 --num-symbols 4194304 --sim-seeds 42,43,44 --jobs 4

# 3) 报告 + 交付件
.venv\Scripts\python.exe report_ddps.py --test-dir result/ddps_main --model-dir models/ddps --seed-config result/seed_config_bad_1e5.json
.venv\Scripts\python.exe report_ddps.py --test-dir result/ddps_aonly --model-dir models/ddps --seed-config result/seed_config_bad_1e5.json
.venv\Scripts\python.exe make_deliverable.py --baseline result/ddps_main --a-only result/ddps_aonly
```

## 并行内存约束

`num_symbols=2^22` 时每进程峰值内存约 2~4GB；主流程 + A-only 同时 `--jobs 4`（共 8 进程）会互相拖慢（每 env ~135min，吞吐与串行相当），free RAM 实测 10~18GB 健康。换 4 进程单跑每 env ~70min。
