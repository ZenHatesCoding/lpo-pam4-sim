# DDPS 版本变更记录

> 本文件记录每个版本的核心变化。只记"变了什么"，不记排错过程。

## v8（当前版本 · 割线在线调优）

### 在线调优方式重做（模型不重训）
- 把每步 14 个 ±ε 试探态（中心差分链式梯度）换成**一次性初始化 + 割线（Broyden "good"）更新 + 周期性中心差分刷新（K=3）**。
- 第 0 步 `_grad_a_chain` 一次性中心差分初始化梯度；此后每步割线更新 `g_{k+1} = g_k + (ΔA − g_kᵀΔx)·Δx/‖Δx‖²`（Δx=上一步实际位移、ΔA=Model A 预测变化，历史落点探针免费算术）；每 3 步 + Model B 全拒时回退一次中心差分刷新。
- 在线真实评估量从「每步 15 次（14 试探 + 1 落点）」降到「每步 1 次落点 + 每 3 步 14 次刷新」（2^18 实测 86 vs 226 次/用例 = 2.6×）。
- 新增 `ddps_optimizer._stage2_descent_secant`（Python）+ `cpp` `stage2_descent_secant`（一比一）+ `--method {chain,secant}`。

### 低SNR验证（2^18 · 单种子 42 · 15 步 · 次优起点）
- Base_IL10x10：secant=chain=9.92e-7（0 错误地板）。
- IL20x20：纯割线（无刷新）卡 3.02e-4；加周期刷新 K=3 后 3.97e-6 与 chain 一致。（根因：Broyden 只沿已走过方向更新，未探索的 gain 维梯度塌缩被门控。）

### 等价性（低SNR bit级对齐）
- Python vs C++ 割线轨迹（Base + IL20x20 @ 2^16）gdc/gdc2/gain/pred_a/pred_b/real_ber 最大相对差 ~5.9e-13。

### 归档
- v7.3（2^22 链式梯度，Python+C++）归档至 `archive/20260930_ddps_v7.3_2to22/`。

## v7.3（已归档）

### 2^22 全量重跑（Python 与 C++ 双后端）
- 分辨率 2^18（262144 符号）→ **2^22（4194304 符号）**；单种子 42、15 步、15 用例、次优起点，Python 与 C++ 各全量重跑一遍（C++ 另补 trace/probes CSV 落盘，与 Python 同 schema）。
- 0 错误检测底从 9.92e-07 降到 **5.97e-08**（≈1/(2·N_bits)，N_bits=8368608）；单种子 95% CL 上限 ≈3.6e-07。

### 结果图全部改用 C++ trace/probes
- 交付件 §6 收敛图与 §6.4 试探步图全部改用 C++ 的 trace/probes CSV（`result/ddps_cpp_main`），不再用 Python 小点数。

### 2^22 大点数实测速率比
- 单用例全量在线调优（Base_IL10x10，3 步干净测速，单种子 42）：**C++ 1240 s / Python 2236 s = 1.80×**，替换 v7.2 沿用自小点数的 1.76×。

### 结果（15 用例，4194304 符号 × 单种子 42）
- C++ 15/15 改善、0 退步；**11 用例到 0 错误地板 5.97e-08**，4 用例残留（IL20x20 1.2e-07、Comb_IL20x20_CD15_DGD5 2.4e-07、HighNoise_IL16x16 2.4e-07、HighNoise_IL10x10 3.6e-07）。
- Python 与 C++ 逐用例 **best_gdc / best_gain / best_ber 比特级一致**（相对差 ≤1e-13）。
- C++ 全量（12 路并行）实际墙钟 ≈9.4 h（首 12 例受 12 路内存分页拖慢，单例墙钟偏大）。

### 归档
- v7.2 的 2^18 单种子结果归档至 `archive/20260928_ddps_v7.2_2to18/`，约束写清：2^18 分辨率、单种子 42、15 步、检测限 9.9e-7 / CL 5.7e-6，仅作粗等价性与速率参考。
- 一并移入该归档目录：`result_ddps_v72_equiv_base`（2^18 单用例等价性比对）与 `result_ddps_v72_sanity`（2^18 4 步冒烟），均已移出 git 跟踪。

## v7.2（已归档）

### C++ 平台复刻（一比一）
- `cpp/src/*.hpp` 复刻 Python 全链路：`rng`（MT19937/randint/高斯，逐位一致）、`fft`（radix-2 + 非 2 幂 naive DFT）、`filter`（Butterworth 双线性 + lfilter）、`s4p`（S4P 装载 + unwrap + f_scale + SDD21 插值）、`physim`（完整物理链 `run_sim`）、`probe`（发端冲激 + 峰值缓存 + drive_rms）、`surrogate`（WhiteBoxRidge 二阶多项式 + 解析梯度）、`optimizer`（Stage-2 链式梯度下降，含 14 ±ε 试探态真实 BER 记账）。
- 等价性验证：`run_sim` 端到端 BER **逐位一致**（2^18：ffe_ber=3.590842360037e-04，mlse_ber=1.289529024323e-04）；发端探针/代理推理差 ≤1e-13/1e-12；在线调优下降路径逐步一致；差异仅来自 FFT 求和顺序（~1e-13），不改变 BER 判决。
- 模型转换：`cpp/export_models.py` 把 `model_{a,b}.pkl` 转 `models/ddps/model_{a,b}.json`（W/mu/sd/local_spacing），C++ 直接装载、不重训。

### 单种子口径
- 评估种子 `SIM_SEEDS` 从 `(42,43,44)` 改为 `(42,)`。一次交付只用一个种子；换种子是用户复现时的动作，不是交付件的多实现平均。

### 发端人为加噪快模式 + 统一入口
- `system.tx_noise_snr_db` 开关：DSP 出口 AWGN（σ=√5/10^(snr/20)），用于低 SNR、少点数快速验证（如 23 dB + 2^14 符号）。
- `cpp/main.cpp` 统一入口：`--num-symbols / --tx-noise-snr / --seed / --n-steps / --seed-config / --model-dir / --out`；`cpp/build.ps1` 构建（动态链接）。

### 速度与结果（2^18 符号，单种子 42，15 步，无噪声，次优起点）
- **C++ 单用例全量在线调优 424 s，Python 744 s，加速 1.76×**（均单线程，Base_IL10x10）。
- 15 用例全量重跑（C++ 与 Python 各 15 用例，20 核并行）：**15/15 改善、0 退步**；两平台 best_gdc / best_gain / best_ber **逐用例一致**（差 ≤1e-12）；C++ 全量并行合计墙钟 1342 s。
- 单种子 2^18 下降：多数用例到 0 错误地板 9.92e-07；IL20x20 与 Comb_IL20x20_CD15_DGD5 到 3.97e-06（高插损残留）；gDC 6.5~8.2 dB、gDC2 → 0、gain ×0.37~×0.57。

## v7.1（已归档）

### 物理层口径修正（回退 v7 的满量程/增益约定，量化噪声改 AWGN）
- **量化噪声 AWGN 注入**：`channel_imdd.quantize`（确定性 mid-tread、满量程固定 ±1）改为 `add_quantization_noise`——按经典 SNR_q = 6.02·ENOB + 1.76 dB（满量程单音正弦）推导 σ_q = V_FS/(2^ENOB·√12)，V_FS 取 DAC/ADC 输出信号自身 max−min 峰峰值（恰好不 clip）。量化 SNR 随信号缩放、与增益无关，不再因固定满量程而破坏信号幅度物理。
- **PAM4 数字电平回退**：`[-1,-1/3,1/3,1]` → `[-3,-1,1,3]`（RMS = √5）；`tx_dsp.pam4_map/PAM4_LEVELS`、`rx_dsp` 判决界（±2/3、0 → ±2、0）、MLSE 参考同步切换。
- **driver 标称增益回退**：`DRIVER_GAIN_NOMINAL` 1.0197 → **0.3399**（基线 IL=10dB + 种子 FFE 抽头 + Tx CTLE 关闭下 drive RMS @gain=1.0 = 0.6763 V ⇒ g0 = 0.617×0.3726/0.6763，与 v6.2.2 一致）。
- **接收机单层 AGC 目标修正**：单层 TIA AGC 的目标 RMS √5/3（0.7454 V）→ **√5（2.236 V）**，即 v6.2.2 两级 AGC（TIA 0.1863 V + ADC 数字 √5）的级联等效增益。
- **配套**：`create_config.py` driver_gain 0.3399、`config.xlsx` 重生成；`tools/calibrate_driver_gain.py` 标定口径注释与实测一致（复现 0.3399）。

### 试探步 BER 记录（在线调优透明度）
- 7 维中心差分每步产生 14 个 ±ε 微扰态（4 FFE 旁瓣 + gDC + gDC2 + u_gain 各 ±）。真实在线系统里为获取探针而做的这些参数微扰会让链路实际处于这些工作点，因此**每个试探态自身的端到端 MLSE BER 也被逐一记录**（与轨迹同分辨率 4194304 符号 × 3 种子），只用于透明度核验、不参与下降方向（方向仍由代理梯度决定）。
- 产出：每环境 `probes_<用例>.csv`（step/param/sign/x/taps/gdc/gdc2/gain/real_lb/real_ber 等列）；`tools/merge_test_parts.py` 合并时同步归集 `probes_*.csv`。
- 展示：`report_ddps.py` 收敛图叠加灰色试探态散点（包络）；交付件新增 §6.4 试探步 BER 包络表（逐用例统计最小/最大/中位）。

### 结果（15 用例，4194304 符号 × 3 种子 42/43/44）
- 次优起点 `Base_IL10x10:1630`（FFE `[-0.0885,-0.3147,0.4079,0.0845,0.1043]`、gDC=6.73、gDC2=0.85、gain=0.1106 ×0.325），种子 BER 1.1e-4（Base）~ 5.4e-2（IL20x20 极端插损）。
- 在线调优（15 步，7 维含 gain）：**15/15 改善、0 持平、0 退步**，几何平均改善 **×33518.50**（最高 Comb_IL20x10_CD15_DGD5 ×445724）；调优后最优 BER 5.97e-8（检测底）~ 3.0e-7（40 dB 总插损用例）。
- 全程 225 步真实 BER，**0 步劣于种子**；gain 维从 ×0.325 推到各用例最优倍率（强信号 ×0.39~×0.42、中高插损 ×0.47~×0.52、极端插损/高噪声 ×0.54~×0.65）；gDC 微调 6.5~8.2 dB、gDC2 → ~0。
- 每步 14 个 ±ε 试探态端到端 MLSE BER 逐条记录（210 态/用例），试探 BER 最大 1.5e-3 ~ 6.3e-2，全部纳入交付件 §6.4 表 + 收敛图灰点。
- A-only 与 A+B 逐用例一致（B 红线全程未触发）。

## v7（已归档）

### 物理层全流程重做（HANDOFF 13 条处置）
- **真逐位 Gray BER**：`metrics.calculate_ber` 改为 `g = s ^ (s >> 1)` 逐位 Gray 映射、逐位比较（`ber = 位错误数/总位数`），替换 SER/2 近似；`ser` 保留作诊断。0 错误伪计数 = 0.5/(2N) 位（= 1/(4N)）。
- **PAM4 数字域归一化 ±1**：电平 `[-3,-1,1,3]` → `[-1,-1/3,1/3,1]`，峰值满量程 = 1；Tx FFE / Rx 判决 / MLSE 参考同步切换。
- **固定 ±1 DAC/ADC 量化**：`quantize` 用固定满量程（±1）mid-tread 确定性取整，不再按块 max|x| 反推满量程。
- **单层 TIA AGC**：删除 ADC 后数字域 √5 AGC，只保留 TIA 侧一层（目标 RMS = √5/3 ≈ 0.7454 V）；driver/TIA 增益成为 ±1 数字域与物理域的桥梁。
- **driver 标称增益重标定**：`DRIVER_GAIN_NOMINAL` 0.3399 → **1.0197**（±1 满量程下 driver 增益 ≈ 1）。
- **Tx CTLE 收敛**：`tx_dsp.tx_ctle` 旧实现归档，`eval(custom_taps)` 注入点清除（改 `ast.literal_eval`），现役只留 `channel_imdd.apply_ctle`。
- **Burg a1 输出 E 保留 + 合成单测**：`burg_ar` 返回 `(a[1:], E)`，E = 白化噪声方差 σ²；`tests/test_burg_a1.py` 钉死「a1 = 白化抽头 = −φ（AR(1) 系数 φ）」符号约定；`tests/test_viterbi_equiv.py` 转正进 git。
- **report_ddps 单一路径**：删除 6 维 else 分支（报表现役只留「7 维 gain 入梯度」）。
- **config.xlsx 单写者**：`utils_config.ensure_config()` 统一「主进程 spawn 前生成一次、worker 只读」，删除散落各处的「缺了就就地生成」TOCTOU 分支。
- **次优起点一等公民**：`ddps_optimizer.apply_seed_config()` 统一装载 seed_config（tap + gDC + gDC2 + gain）；`SEED_TAPS` 降级为未提供 seed_config 时的兜底；`tools/verify_tail_fix.py` 重复 taps 常量删除、统一引用。
- **optimizers/**：`optimize_tx.py` 等转 UTF-8，`run_ddps` 占位 stub 删除（三阶段管线接口明确）。

### 结果（15 用例，4194304 符号 × 3 种子 42/43/44）
- **次优起点 x₀**：FFE `[0.0342, -0.3222, 0.6173, -0.0148, 0.0115]`（主抽头 0.6173）、gDC=5.66 dB、gDC2=1.57 dB、gain=0.6277（×0.616，u_gain=−0.2107），取自训练数据实测点 `Base_IL10x10:915`。
- **起点种子 BER**：基线 Base_IL10x10 1.36e-4，整体 5.97e-8 ~ 1.09e-2（强信号用例起点即检测底）。
- **调优后最优 BER**：12/15 用例下降、1 用例持平（IL14x14 起点即检测底 5.97e-8）、2 用例退步（IL20x20 ×1.87、Comb_IL20x20_CD15_DGD5 ×1.61，均 40 dB 总插损）。
- **几何平均改善 ×18.69**（15 用例全部计入，含 2 退步拉低）；最深恢复：Base ×2279（1.36e-4→5.97e-8）、CD15ps ×1274、CD28ps ×493、HighNoise_IL10x10 ×317、IL10x20_RxHeavy ×223。
- **gain 维**：所有用例从 ×0.616 出发被梯度推到各用例最优倍率附近（强信号 ×0.66~×0.82、高损/高噪声 ×0.70~×0.85）；2 个 40 dB 总插损用例代理方向失效、gain 推到 ×0.9 附近仍退化。
- **A-only 一致性**：15 用例最优 BER 与主流程逐点一致（B 红线全程未触发，仅起保险作用）；2 个 40 dB 用例 A/B 同时方向失效、红线未拦截。全程真实 BER 217 步中 86 步劣于起点（超调 + 极端插损方向失效）。

## v6.2.2（已归档）

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
