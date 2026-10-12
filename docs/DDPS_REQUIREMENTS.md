# DDPS 交付件与重做要求清单

> 本文件是所有要求的沉淀。每次重做前必读。不在这里的要求不复提。

## 一、架构要求（不可改）

### A/B 模型分工
- **Model A（方向代理）**：输入 = [7-tap Tx FIR 探针, drive_rms]（8 维波形域）→ log10(BER) 条件均值。WhiteBoxRidge（二阶多项式 + L2 Ridge 闭式解，带解析梯度）。
- **Model B（风险控制）**：输入 = [4 FFE 旁瓣, gDC, gDC2, drive_rms]（7 维参数域）→ log10(BER) 保守上包络。WhiteBoxRidge。
- **A/B 输入空间不同**（波形域 vs 参数域），误差来源相互独立。
- **梯度**：通过 A 的链式法则——扰动 7 维参数 → 重算探针（含 CTLE！）→ 查 A → 得 gᵢ=(A⁺−A⁻)/(2·epsᵢ)（7 维双边中心差分，eps 分档 0.01/0.1/0.05）。每步 14 次探针 + 14 次 A 前向。
- **gain**：第 7 个搜索维（`u_gain = log10(gain / 0.3399)`），经 drive_rms 进入 A/B 输入，参数箱信任域 ±0.30 dex。per-case target_rms 扫描作为各用例最优 gain 的离线标定参照。

### 物理层（链路口径）
PAM4（电平 [-3,-1,1,3]，RMS = √5）→ 5-tap Tx FFE → DAC(ZOH,ENOB 5.5 量化噪声以 AWGN 注入，满量程=DAC 输出信号自身 max−min) → Tx IL(S4P) → +1mV 噪声 → Tx CTLE(gDC,gDC2, peaking) → Driver(gain) → Driver BW(40GHz) → MZM(Vπ=3,bias=2.25,ER=25dB) → 光纤 → PIN → TIA → Rx IL → +1mV 噪声 → Rx CTLE(固定 gDC=6/gDC2=3) → ADC(ENOB 5.5 量化噪声以 AWGN 注入，满量程=ADC 输出信号自身 max−min) → Rx FFE(22-tap,LMS) → Burg → MLSE(memory=1)。**Tx driver 路径无 VGA、无 RMS 归一化；Rx 侧只有 TIA 一层物理 AGC（目标 RMS = √5 ≈ 2.236 V）。** 量化噪声 σ = V_FS/(2^ENOB·√12)，由 SNR_q = 6.02·ENOB+1.76 dB（满量程正弦）推导。BER 为真逐位 Gray 计数。
- Tx CTLE 为 OIF 2Z3P peaking 拓扑（`gDC` = 高频 peaking gain，直流增益恒 0 dB；`gDC2` = LF shelf gain），零极点比 `fz=2.862/fp1=1.884/fp2=1/flf=40`。
- Rx CTLE 与 Tx 同一拓扑但参数固定（`gDC=6, gDC2=3`），不参与寻优。

### 关键常量
- SEED_TAPS=[-0.034,-0.2987,0.6091,0,0.0582]（5-tap，FFE_PRE=2，主抽头 t2，仅作未提供 seed_config 时的兜底）；次优起点的 7 维全量（tap + gDC + gDC2 + gain）见 `result/seed_config_bad_*.json`
- DRIVER_GAIN_NOMINAL=0.3399；次优起点 gain 见 `result/seed_config_bad_*.json`（经 `apply_seed_config` 装载）
- 步骤：GD 步长 0.05 × 0.97^k × 箱宽（组内归一化），GROUP_GATE=1e-3，MIN_GAIN_DEX=0.01
- MAX_DEGRADE_FRAC=0.25
- 信任域 = 2.0 × ρ（ρ = 32nd nearest neighbor median in B's param domain）

## 二、安全红线逻辑（已修正）

### 根因
- 旧逻辑：红线 = 10^(Model B 对种子的预测) × 1.25
- Model B 用基线训练，在非基线环境预测的绝对值不可信（IL20x20: B预测=2.3e-4 vs 真实=6.0e-2，差260倍）
- 导致红线在多数用例比种子还好（allowed/seed < 1），逻辑矛盾

### 正确逻辑（已实现）
- 红线 = **当前已知最优点**的 Model B 预测 BER × (1 + MAX_DEGRADE_FRAC)
- 每步若 B 预测改善，红线跟着下移——B 预测单调下降时红线不会触发
- 若 B 预测突然变差（方向错），红线才挡住该步
- 不用种子点的 B 预测（绝对值不可信），用"相对最优点变差 25%"

## 三、对比实验：A-only vs A+B（已实现）

### 实现
- `ddps_optimizer.py` 提供 `_stage2_descent_aonly()`：只用 A 梯度，不查 B，不走安全拦截
- `test_generalization.py` 提供 `--a-only` 标志和 `run_case_aonly()` 函数
- 结果输出到 `result/ddps_aonly/`
- 交付件 §6.1/6.2b 显示逐用例对比表与同款图

### 判读标准
- 如果 A-only 就 0 劣化步，说明 Model A 方向已足够好，B 只起保护作用、不是被依赖的拦截
- 如果 A-only 有劣化步而 A+B 没有，说明 B 确实拦住了错误方向

## 三b、对比实验：训练环境对比（历史，v6.0 时代，已归档）

> 该实验系历史时期三组训练对比（基线 vs IL20x20 两种种子），结果已归档在 `archive/`。当前版本只用基线训练单套模型，不再做训练环境对比。

### 实现
- 三组：基线训练(IL10x10) vs IL20x20(BO种子) vs IL20x20(梯度下降种子)
- `optimizers/bo_search_il20.py`：贝叶斯优化在 IL20x20 上搜 6 维全局最优种子点
- `dataset_generator.py --base-env IL20x20 --seed-config result/il20_bo_seed.json`：用 BO 种子点邻域采样
- `test_generalization.py --seed-config result/il20_bo_seed.json`：用 BO 种子点做 Stage-2 起点
- 三组对比交付件（基线 vs IL20(BO种子) vs IL20(GD种子)）已在 v6.0 时通过 `make_deliverable_compare.py` 生成并归档
- 新旧数据/模型/结果全部分开存储：`dataset_il20/`, `models/ddps_v6_il20/`, `result/ddps_v6_il20_main/`

### 判读标准
- 基线训练最稳健（15/15 正向、0 退步；40 dB 总插损用例也推到检测限附近）
- 高损环境训练在重损环境更优但泛化性下降
- 种子点选择决定模型对哪个区域学得准

## 三c、对比实验：direct（有回传通道时的参照，2026-10-12 增）

> 回答的问题：现役方案假设**没有回传通道**（在线拿不到收端端到端 BER，只能靠发端探针训练 Model A/B）。如果端到端 BER 可以回传，直接对真实目标做梯度下降能达到什么水平？direct 是该问题的参照实现，**不是替代方案**。

### 实现
- `ddps_optimizer.py`：`_grad_direct_chain()`（7 维中心差分，目标 = 真实 log10 BER，14 个 ±ε 试探态逐一记账）+ `_stage2_descent_direct()`（此后每步全 7 维 Broyden 割线更新，零试探态）
- 下降机制与现役割线一致：同搜索盒（FFE ±0.10 / CTLE ±3.0 dB / gain ±0.30 dex）、同 GD_LR=0.05 + 0.97^k 衰减 + 组归一化跨度、同 GROUP_GATE=1e-3 组门控、同 MIN_GAIN_DEX=0.01 边际停止
- 与现役的差别只在目标与梯度来源：无 Model A/B → 无解析 gain 梯度（第 0 步 7 维全测）、无 B 红线/候选否决/轨迹信任域（三者都是代理可靠性保障，无代理即无保护对象）
- `test_generalization.py --method direct`；trace 的 `pred_a` 列 = 当前落点目标值（= real_lb），`pred_b/allowed` 恒 0（列结构与其余结果目录一致）
- C++ 一比一复刻：`cpp/src/optimizer.hpp` `grad_direct_chain` + `stage2_descent_direct`，`cpp/main.cpp --method direct`
- 结果目录：`result/ddps_direct_py/`（Python 2^18 全 15 用例）、`result/ddps_cpp_direct_equiv/`（2^18 等价比对，Base_IL10x10 + IL20x20）、`result/ddps_cpp_direct/`（C++ 2^22 全量）
- 交付件 6.5 节页签：结果对比（同协议逐用例表 + 对比图）/ 方案说明（机制对照表）/ C++ 等价比对（实算最大相对差）；数据缺失时自动不渲染

### 判读标准
- 与现役方案同协议（同次优起点 seed_config_bad_1e4、同 15 用例、2^22 符号、单种子 42、同 C++ 实现、同 15 步上限）对比，几何平均改善与逐用例最优 BER 照实并列呈现，谁好用谁
- 预期行为：真实 BER 到 0 错误检测限后梯度信号消失，边际停止判据随即触发（步数普遍比现役省）；这是真实目标的固有属性，不是缺陷

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

## 六、双后端分工与比对口径（不可违反）

- **Python 定原理，C++ 一比一复刻**（算法、物理层模型、参数、调优算法全部一致；见 `AGENTS.md`「开发方式」）。
- **比对口径**：Python 与 C++ 的等价性验证、收敛对比只在 **2^18 小点数低 SNR** 下做——唯一允许的比对口径，不允许在大点数/高 SNR 下比对。
- **规模仿真分工**：全量规模仿真（高 SNR 大点数，如 2^22 在线调优与全量评估）**只用通过比对的 C++ 入口**（`cpp/run_all_cases.py`，现役 `--backend wsl`，见下方「C++ 构建运行环境」）；**不允许用 Python 跑高 SNR 大点数**（`test_generalization.py` / `tools/run_parallel_envs.py` 等 Python 入口只用于小点数低 SNR 验证）。
- **比对工具**：`cpp/compare_traces.py` 逐步（用例 × 步 × 数值列）比对 trace，判据 max_rel < 1e-9（历史基线 ~1e-12 量级）；默认比两侧交集，`--envs` 可指定。
- **C++ 构建运行环境（2026-10-12 起）**：本机 Windows Smart App Control 强制模式拦截本地编译的无签名 exe（含 MinGW cc1plus 依赖的 libisl-23.dll 与既有 run_ddps.exe），Windows 侧编译运行路线不可用；现役路线 = WSL(Ubuntu) g++（`cpp/build_wsl.sh` 构建、`cpp/run_all_cases.py --backend wsl` 调度，产物/结果仍落 Windows 文件树受 git 跟踪）。源码纯标准 C++17，跨平台构建不影响数值行为，等价性以 2^18 比对为准。
