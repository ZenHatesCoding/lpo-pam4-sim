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
* **Tx FFE**: 5-tap T-Spaced（4 个旁瓣自由变量 + 1 个派生主抽头），架构锁死，权重供 DDPS 梯度下降寻优。
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
| [📄 **DDPS 交付说明（自包含 HTML）**](deliverables/DDPS_Deliverable.html) | Python 参照 + C++ 一比一复刻平台（比对只在 2^18 小点数低 SNR、全量规模仿真只用 C++）、割线在线调优（gain 解析梯度 + shape 割线，除第 0 步外零过渡态）、等价性验证（BER 逐位一致）、单种子（42）2^22 在线调优结果、统一入口 |
| [历史交付件与历史实验](archive/) | v2~v7.3 各版本交付件 HTML、训练环境对比实验、历史结果/模型/数据集（本地归档，不入远端） |
| [01. DSP 架构与核心参数详解](docs/01_DSP_Architecture.md) | 收发机模型、多采样率机制、`config.xlsx` 参数物理含义 |
| [02. 独立分析与诊断工具集](docs/02_Utility_Scripts.md) | optimizers/ + tools/ 目录 + 核心脚本 |
| [DDPS 方法](docs/DDPS_Method.md) | A=探针→BER 方向代理 + B=参数→BER 风险控制、7 维割线梯度（gain 解析 + shape 割线，零后续试探）、安全红线、次优起点 |
| [DDPS 要求清单](docs/DDPS_REQUIREMENTS.md) | 架构、安全红线、对比实验、交付件的全部要求 |
| [版本变更记录](docs/CHANGELOG.md) | 每个版本的核心变化（v1→v8） |
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
# 只用基线环境（Base_IL10x10）采样 2000 点，7 维 LHS（4 FFE 旁瓣 + gDC + gDC2 + u_gain）
python dataset_generator.py --base-samples 2000 --only-envs Base_IL10x10 \
    --num-symbols 1048576 --sim-seeds 42,43,44 --jobs 12 --core-samples 1200

# 训练 A（探针 8 维→BER）+ B（参数 7 维→BER），WhiteBoxRidge 带解析梯度（gain 纳入梯度）
python -c "from train_surrogates import train; import glob; \
  train(sorted(glob.glob('dataset/ddps_dataset_*.csv'))[-1], 'models/ddps', \
           pipeline_tag='ddps', gain_mode='gradient_with_rms_init')"
```

### 4. per-case target_rms 扫描 + Python 小点数低 SNR 验证
```bash
# 每用例扫描标定最优发端 RMS（gain 维标定参照）
python tools/scan_per_case_rms.py --jobs 8

# Python 原理验证（比对口径：2^18 小点数低 SNR、单种子 42、次优起点、割线 + 解析 gain）
python test_generalization.py --model-dir models/ddps --out-dir result/ddps_secant_analytic_py \
    --method secant --seed-config result/seed_config_bad_1e4.json --n-steps 15 \
    --num-symbols 262144 --sim-seeds 42
```

> **Python 只用于小点数低 SNR 验证**（AGENTS.md「开发方式」）：Python 与 C++ 的比对只在 2^18 小点数低 SNR 下做；全量规模仿真（高 SNR 大点数）只用通过比对的 C++ 入口（见 4b），不允许用 Python 跑高 SNR 大点数。

### 4b. C++ 复刻平台（一比一，同一入口同一口径；全量规模仿真唯一入口）
```bash
# 构建：WSL 内 g++（本机 Smart App Control 强制模式拦本地无签名 exe，含旧 run_ddps.exe
#       与 MinGW cc1plus 依赖的 libisl-23.dll；Linux 进程不受 Windows 代码完整性策略管辖，
#       源码纯标准 C++17。Windows 侧 gcc.exe 路线见 cpp/build.ps1，仅在策略放开后可用）
wsl -d Ubuntu --cd /mnt/c/DSPPlayground/eLPO_antigravity bash cpp/build_wsl.sh

# 模型转换（一次性）：pkl → models/ddps/model_{a,b}.json
python cpp\export_models.py

# 全量规模仿真：15 用例 2^22 在线调优（高 SNR 大点数、单种子 42、次优起点；只允许走 C++）
python cpp\run_all_cases.py --backend wsl --method secant --out-dir result/ddps_cpp_secant \
    --num-symbols 4194304 --n-steps 15 --jobs 2

# 快速验证：低 SNR 人为噪声 + 少点数（发端 DSP 出口 SNR=23 dB、2^14 符号）
wsl -d Ubuntu --cd /mnt/c/DSPPlayground/eLPO_antigravity ./cpp/build/run_ddps cpp/config.txt \
    --num-symbols 16384 --tx-noise-snr 23 --seed 42
```
> C++ 与 Python 读同一配置、同一模型转换产物，数值等价（BER 逐位一致、探针/模型 ≤1e-13、下降路径逐步一致）。开发方式：**Python 定原理，C++ 一比一复刻；两者比对只在 2^18 小点数低 SNR 下做，全量规模仿真（高 SNR 大点数）只用通过比对的 C++ 跑，不允许用 Python 跑高 SNR 大点数**。C++ 环境依赖见 [`cpp/requirements.txt`](cpp/requirements.txt)。

### 4c. 对比实验 direct（有回传通道时的参照：端到端 BER 直接梯度下降，不用 Model A/B）
```bash
# 1) Python 小点数低 SNR 验证（比对口径，全 15 用例）
python tools/run_parallel_envs.py --model-dir models/ddps --out-dir result/ddps_direct_py \
    --method direct --seed-config result/seed_config_bad_1e4.json --n-steps 15 \
    --num-symbols 262144 --sim-seeds 42 --jobs 12

# 2) C++ 2^18 等价比对（Base_IL10x10 + IL20x20；与 secant 时代同口径）
python cpp/run_all_cases.py --backend wsl --method direct --out-dir result/ddps_cpp_direct_equiv \
    --only-envs Base_IL10x10,IL20x20 --num-symbols 262144 --n-steps 15 --jobs 2
python cpp/compare_traces.py --py result/ddps_direct_py --cpp result/ddps_cpp_direct_equiv

# 3) C++ 全量规模仿真（2^22、15 用例；与现役方案同协议）
python cpp/run_all_cases.py --backend wsl --method direct --out-dir result/ddps_cpp_direct \
    --num-symbols 4194304 --n-steps 15 --jobs 2
```
> direct 回答的问题：若收端端到端 BER 可回传，直接对真实目标做梯度下降能达到什么水平（下降机制与现役割线一致：同搜索盒/步长调度/组门控/边际停止；差别只在目标与梯度来源，无代理即无 B 红线/否决/轨迹信任域）。用于对照「无回传通道、只能靠发端探针代理」的现役方案。交付件呈现：6.2 收敛图组页签（现役 | direct 同款图组对照）、6.5 对比实验节、10.4 在线调优等价页签。

### 5. 报告与交付件
```bash
# 可视化报告：收敛三曲线 + gain/rms 轨迹 + 预测散点 + 最难用例四联图
python report_ddps.py --test-dir result/ddps_cpp_secant --model-dir models/ddps \
    --seed-config result/seed_config_bad_1e4.json --summary-out result/SUMMARY.md

# direct 结果图组（收敛 / gain·rms / 最难用例，供交付件 6.2 页签）
python report_ddps.py --test-dir result/ddps_cpp_direct --method direct \
    --seed-config result/seed_config_bad_1e4.json

# 交付件（自包含 HTML；direct 内容数据驱动：6.2 图组页签 / 6.5 对比节 / 10.4 等价页签）
python make_deliverable.py --baseline result/ddps_cpp_secant --model-dir models/ddps \
    --direct result/ddps_cpp_direct --out deliverables/DDPS_Deliverable.html
```

### 6. 历史实验（结果已归档）
```bash
# IL20x20 训练对比实验（基线 vs BO种子 vs GD种子），结果见 archive/
python optimizers/bo_search_il20.py
```
