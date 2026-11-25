# LPO PAM4 (112G/224G/448G) DSP 基线仿真平台

本项目是一个基于纯 Python (Numpy/Scipy) 白盒构建的 **Linear Pluggable Optics (LPO)** 系统级仿真器，主要用于跨多代速率（112G/224G/448G）下的高速信道纯线性均衡算法研究与评估。

> [!NOTE]
> 本项目的核心理念是 **"白盒化" (White-Box)** 与 **"符合物理直觉"**。
> 我们移除了容易在超高误码率下发生雪崩效应的 DFE，并禁止对发送端架构做随意扩增（锁死在 T-spaced 5 抽头）。系统强制通过真实的 S4P 级联网络与纯线性 FIR 结构探索性能边界。

## 🚀 核心架构与多模切换 (Multi-Mode Switch)

本平台已全面打通 IEEE 802.3ck (112G) 与 IEEE 802.3dj (224G) 的原生物理参数库，支持一键无缝切换：

打开 `create_config.py`，在文件头部修改全局开关 `DEFAULT_MODE`：
```python
# 可选值: '112G', '224G', '448G'
DEFAULT_MODE = '112G'
```
直接运行 `python main.py`，系统将自动装载：
* **112G 模式**：56 GBd，40 GHz 光电器件，自动挂载 **IEEE 802.3ck** C2M 16dB 原生信道模型。
* **224G 模式**：112.5 GBd，80 GHz 光电器件，自动挂载 **IEEE 802.3dj** 原生信道模型。
* **448G 模式**：212.5 GBd，150 GHz 光电器件，自动启动 ZTE 频轴缩放算法拟合 150GHz CBW 极限物理环境。
* **光物理层应力容限测试**：已将 IEEE 标准中的色散 (CD) 和差分群时延 (DGD) 白盒化。可通过 `config.xlsx` 中的 `stress_cases` 工作表进行任意应力组合的独立配置。

## 💡 均衡器配置底座
* **Tx FFE**: 5-tap T-Spaced，架构锁死。DDPS 在线搜索把 5 个抽头全部当自由变量（无边界、无峰值和约束）；主抽头由归一化恒等式 `1 − Σ|旁瓣|` 派生只存在于 Stage-1 数据集采样口径，用于构型与评估，不是在线约束。
* **Rx FFE**: 22-tap T-Spaced（LPO 模式），内置 LMS 自适应盲调。
* **DFE**: 默认全关（`dfe_taps=0`），防止高误码率下的雪崩式错误传播。
* **MLSE**: 默认开启 (Memory=1) + Burg AR 白化，Viterbi 4 态联合解码。开启时自动锁死 DFE。

> [!IMPORTANT]
> 平台统一终极指标 = **`BER_MLSE`**（MLSE 判决输出、Gray 映射 BER）。
> 所有代理训练标签、收敛曲线与报告均以 `log10(BER_MLSE)` 为准。

> [!TIP]
> 📊 **结果与图件索引见 [`result/SUMMARY.md`](result/SUMMARY.md)**

## 📚 文档导航 (Documentation Navigation)

| 文档 | 内容 |
| --- | --- |
| [📄 **DDPS 交付说明（自包含 HTML）**](deliverables/DDPS_Deliverable.html) | Python 参照 + C++ 一比一复刻平台（比对只在 2^18 小点数低 SNR、全量规模仿真只用 C++）、Model A 方向代理 + 8 维在线搜索（5 抽头全自由无边界 + gDC + gDC2 + u_gain）、梯度获取 3×2 矩阵（3 种形状维取法 full / rotate / secant × 2 种来源：Model A 发端代理 / 真实 BER 回传）+ gain 解析梯度、六格 2^18 逐轨迹等价（判据 `max_rel < 1e-9`）、单种子（42）2^21 在线调优结果、统一入口 |
| [📝 **DDPS 交付说明（Word 版，按需生成）**](deliverables/DDPS_Deliverable.docx) | 由 HTML 版派生（`make_deliverable_docx.py`），内容逐字一致；页签平铺为顺序小节、走查帧全展开、Word 原生目录域与导航窗格。**默认不生成**：常规交付只出 HTML，用户明确要 Word 时再跑 |
| [历史交付件与历史实验](archive/) | v2~v7.3 历史交付件 HTML、训练环境对比实验、被取代的历史结果/模型/数据集（本地归档，不入远端） |
| [01. DSP 架构与核心参数详解](docs/01_DSP_Architecture.md) | 收发机模型、多采样率机制、`config.xlsx` 参数物理含义 |
| [02. 独立分析与诊断工具集](docs/02_Utility_Scripts.md) | optimizers/ + tools/ 目录 + 核心脚本 |
| [DDPS 方法](docs/DDPS_Method.md) | Model A 方向代理（唯一在线代理）、8 维在线搜索空间（抽头全自由无边界）、gain 维解析梯度 + 形状 7 维三种取法（full / rotate / secant）、梯度来源两行（发端代理 / 真实 BER 回传）、真实评估代价口径、次优起点 |
| [DDPS 要求清单](docs/DDPS_REQUIREMENTS.md) | 架构、物理代价口径、对比实验、交付件的全部要求 |
| [变更记录](docs/CHANGELOG.md) | 按日期记录每次变更（历史版本号只出现在归档条目） |
| [LPO MSA 规范核心参数提炼](docs/LPO_MSA_Specification_Summary.md) | 电气/光学/信道参数标准依据 |
| [分支关系与版本导览](BRANCHES.md) | 仓库各分支的关系与差异 |

## ⚡ 快速上手 (Quick Start)

### 1. 配置虚拟环境并安装依赖
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 执行单点主仿真
```bash
python main.py
```

### 3. 数据集生成与模型训练
```bash
# Stage-1 采样（离线，只产数据集自变量）：基线环境 Base_IL10x10 采 2000 点，
# 7 维 LHS（4 FFE 旁瓣 + gDC + gDC2 + u_gain），主抽头由 1 − Σ|旁瓣| 派生
python dataset_generator.py --base-samples 2000 --only-envs Base_IL10x10 \
    --num-symbols 1048576 --sim-seeds 42,43,44 --jobs 12 --core-samples 1200

# 训练方向代理（探针 8 维 → BER）与参数域产物（参数 7 维 → BER，仅离线归档，不在线使用）
python -c "from train_surrogates import train; import glob; \
  train(sorted(glob.glob('dataset/ddps_dataset_*.csv'))[-1], 'models/ddps', \
           pipeline_tag='ddps', gain_mode='gradient_with_rms_init')"
```

### 4. per-case target_rms 扫描 + Python 小点数低 SNR 验证（2^18 等价参照）
```bash
# 每用例扫描标定最优发端 RMS（gain 维标定参照）
python tools\scan_per_case_rms.py --jobs 8

# Python 参照（比对口径：2^18 小点数低 SNR、单种子 42、次优起点）
python tools\run_parallel_envs.py --model-dir models/ddps --out-dir result\ddps_equiv_py_full \
    --method proxy --grad-mode full --only-envs Base_IL10x10,IL20x20 \
    --num-symbols 262144 --n-steps 15 --sim-seeds 42 --jobs 2 \
    --seed-config result/seed_config_bad_1e4.json
# 换形状梯度档：--grad-mode rotate|secant（--rotate-k 2）；direct 用 --method direct
```

> **Python 只用于小点数低 SNR 验证**（AGENTS.md「开发方式」）：Python 与 C++ 的比对只在 2^18 小点数低 SNR 下做；全量规模仿真（高 SNR 大点数）只用通过比对的 C++ 入口（见 4b），不允许用 Python 跑高 SNR 大点数。

### 4b. C++ 复刻平台（一比一，同一入口同一口径；全量规模仿真唯一入口）
```bash
# 构建：WSL 内 g++（本机 Smart App Control 强制模式拦本地无签名 exe，含旧 run_ddps.exe
#       与 MinGW cc1plus 依赖的 libisl-23.dll；Linux 进程不受 Windows 代码完整性策略管辖，
#       源码纯标准 C++17。Windows 侧 gcc.exe 路线见 cpp/build.ps1，仅在策略放开后可用）
wsl -d Ubuntu --cd /mnt/c/DSPPlayground/eLPO_antigravity bash cpp/build_wsl.sh

# 模型转换（一次性）：pkl → models/ddps/model_{a,b}.json
#   model_a = 在线方向代理；model_b = Stage-1 离线参数域产物（不在线使用）
python cpp\export_models.py

# 全量规模仿真：15 用例 2^21 在线调优（高 SNR 大点数、单种子 42、次优起点；只允许走 C++）
python cpp\run_all_cases.py --backend wsl --num-symbols 2097152 --n-steps 15 --jobs 4 \
    --method proxy --grad-mode full --out-dir result\ddps_cpp_full
# 换取法：--grad-mode rotate|secant（--rotate-k 2）；换梯度来源：--method direct

# 2^18 等价比对（C++ 侧，与 Python 参照同环境、同参数；判据 max_rel < 1e-9）
#   代理三格：--method proxy  --grad-mode full|rotate|secant → result/ddps_equiv_cpp_<取法>
#   回传三格：--method direct --grad-mode full|rotate|secant → result/ddps_equiv_cpp_direct_<取法>
python cpp\run_all_cases.py --backend wsl --only-envs Base_IL10x10,IL20x20 --num-symbols 262144 \
    --n-steps 15 --jobs 2 --method proxy --grad-mode full --out-dir result\ddps_equiv_cpp_full
python cpp\compare_traces.py --py result/ddps_equiv_py_full --cpp result/ddps_equiv_cpp_full
#   其余五格同款命令，只换 --method / --grad-mode / --out-dir 三处（Python 侧参照用 tools\run_parallel_envs.py 出）

# 快速验证：低 SNR 人为噪声 + 少点数（发端 DSP 出口 SNR=23 dB、2^14 符号）
wsl -d Ubuntu --cd /mnt/c/DSPPlayground/eLPO_antigravity ./cpp/build/run_ddps cpp/config.txt \
    --num-symbols 16384 --tx-noise-snr 23 --seed 42
```
> C++ 与 Python 读同一配置、同一模型转换产物，六格 2^18 逐轨迹比对 `max_rel < 1e-9`（实测代理 full 1.42e-12 / 代理 rotate 1.20e-12 / 代理 secant 8.53e-12 / 回传 full 8.655e-13 / 回传 rotate 7.964e-13 / 回传 secant 8.894e-13）。开发方式：**Python 定原理，C++ 一比一复刻；两者比对只在 2^18 小点数低 SNR 下做，全量规模仿真（高 SNR 大点数）只用通过比对的 C++ 跑，不允许用 Python 跑高 SNR 大点数**。C++ 环境依赖见 [`cpp/requirements.txt`](cpp/requirements.txt)。

### 4c. 对比实验 direct（有回传通道时的参照：端到端真实 BER 直接梯度下降，不用代理）
```bash
# 1) Python 2^18 参照
python tools\run_parallel_envs.py --model-dir models/ddps --out-dir result\ddps_equiv_py_direct_secant \
    --method direct --only-envs Base_IL10x10,IL20x20 --num-symbols 262144 --n-steps 15 \
    --sim-seeds 42 --jobs 2 --seed-config result/seed_config_bad_1e4.json

# 2) C++ 2^18 + 逐轨迹比对（六个格各自一对目录：代理 <取法> / 回传 direct_<取法>）
python cpp\run_all_cases.py --backend wsl --method direct --out-dir result\ddps_equiv_cpp_direct_secant \
    --only-envs Base_IL10x10,IL20x20 --num-symbols 262144 --n-steps 15 --jobs 2
python cpp\compare_traces.py --py result/ddps_equiv_py_direct_secant --cpp result/ddps_equiv_cpp_direct_secant

# 3) C++ 全量规模仿真（2^21、15 用例；与代理行三格同协议）
python cpp\run_all_cases.py --backend wsl --method direct --out-dir result\ddps_cpp_direct_secant \
    --num-symbols 2097152 --n-steps 15 --jobs 4
```
> direct（真实 BER 回传行）回答的问题：若收端端到端 BER 可回传，直接对真实目标做梯度下降能达到什么水平。第 0 步恒为全 8 维中心差分（16 个 `±ε 微扰态`，真实 BER 实测），此后按 `--grad-mode` 选取法（`full` 每步 16 态 / `rotate` 每步 4 态 / `secant` 0 态）；无代理，因此没有 gain 解析梯度、没有代理预测。与代理行三格共用同一 8 维搜索空间 / 步长调度 / 组门控 / 15 步上限，差别只在目标与梯度来源。

### 4d. 起点鲁棒性（换多个差起点，六格全跑，看结论是否只在某个起点成立）
```bash
# 1) 先挑起点：给定候选 seed 配置，用链路真实评估报出起点 BER（每个候选 1 步、2^18）
python tools\probe_start_point.py --pattern s1 --cases Base_IL10x10,IL14x14,IL20x20

# 2) 三个差起点 × 六格全跑（起点 ≈1e-3；2^21 符号/点、15 用例、单种子 42、固定 15 步）
python tools\run_seed_study.py --jobs 12 --num-symbols 2097152 \
    --seeds s1_gain-2.6dB,s2_ctle_g3.0_1.5,s3_shape3.0

# 3) 每格出图（结果目录在 result/seed_study/<起点>/ddps_cpp_<格>）
python report_ddps.py --test-dir result/seed_study/s1_gain-2.6dB/ddps_cpp_full --model-dir models/ddps \
    --seed-config seeds/seed_s1_gain-2.6dB.json
```
> 起点文件在 `seeds/`（`best_taps` / `best_gdc` / `best_gdc2` / `best_u_gain` 四个字段，`_source` 说明这个起点坏在哪）。
> `cpp\run_all_cases.py` 与 `tools\run_parallel_envs.py` 都接受 `--seed-config`，换起点不改代码。
> 结果写进 `result/seed_study/<起点>/`，**故意不放在 `result/` 顶层**——否则会被 `tools\verify_ddps.py` 的
> `result/ddps_cpp_*` 自动发现当成现役格，`--expect-cells 6` 会直接失败。
> 倍率可独立复算：`python tools\seed_study_table.py --root result/seed_study --md`（按用例名对齐，不按行序）。

### 5. 报告与交付件
```bash
# 可视化报告（逐格出图：--test-dir result/ddps_cpp_<格>）
#   注意：逐格出图时不要加 --summary-out，否则会用单格覆盖整轮汇总
python report_ddps.py --test-dir result/ddps_cpp_full --model-dir models/ddps \
    --seed-config result/seed_config_bad_1e4.json

# 回传行的格出图时加 --method direct
python report_ddps.py --test-dir result/ddps_cpp_direct_secant --method direct \
    --seed-config result/seed_config_bad_1e4.json

# 交付件（自包含 HTML；六格全给才生成，规模不一致默认拒绝）
python make_deliverable.py --baseline result/ddps_cpp_full --mode full \
    --rotate result/ddps_cpp_rotate --secant result/ddps_cpp_secant \
    --direct result/ddps_cpp_direct_secant --direct-full result/ddps_cpp_direct_full \
    --direct-rotate result/ddps_cpp_direct_rotate --out deliverables/DDPS_Deliverable.html

# 交付件 Word 版（**按需**，默认不做；从 HTML 派生；内联 SVG 经无头 Edge 栅格化，缓存 _parts/svg_png/）
python make_deliverable_docx.py
```

**结果目录**

| 目录 | 内容 |
| --- | --- |
| `result/ddps_cpp_full/`、`result/ddps_cpp_rotate/`、`result/ddps_cpp_secant/` | C++ 2^21 代理行三格全量（15 用例、单种子 42、固定 15 步） |
| `result/ddps_cpp_direct_secant/`、`result/ddps_cpp_direct_full/`、`result/ddps_cpp_direct_rotate/` | C++ 2^21 真实 BER 回传三格全量（同上协议） |
| `result/ddps_equiv_{py,cpp}_<格>/` | 2^18 六格等价参照（Python / C++ 两平台，`compare_traces.py` 逐轨迹比对） |
| `result/seed_study/<起点>/ddps_cpp_<格>/` | 起点鲁棒性对照：三个差起点 × 六格（2^21），结构同现役格 |

每个结果目录含 `case_summary.csv/json`、`trace_<用例>.csv`、`probes_<用例>.csv`、`run_config.json`、`report/`。

### 6. 历史实验（结果与脚本已归档）
```bash
# IL20x20 训练对比实验（基线 vs BO种子 vs GD种子）：脚本与结果均在 archive/ 下，不在现役代码里
ls archive/20261022_retire_stale_tools/optimizers/
```
