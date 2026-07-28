# LPO PAM4 (112G/224G/448G) DSP 基线仿真平台

本项目是一个基于纯 Python (Numpy/Scipy) 白盒构建的 **Linear Pluggable Optics (LPO)** 系统级仿真器，主要用于跨多代速率（112G/224G/448G）下的高速信道纯线性均衡算法研究与评估。

> [!NOTE]
> 本项目的核心理念是 **“白盒化” (White-Box)** 与 **“符合物理直觉”**。
> 我们移除了容易在超高误码率下发生雪崩效应的 DFE，并禁止对发送端架构做随意扩增（锁死在 T-spaced 9 抽头）。系统强制通过真实的 S4P 级联网络与纯线性 FIR 结构探索性能边界。

## 🚀 核心架构与多模切换 (Multi-Mode Switch)

本平台已全面打通 IEEE 802.3ck (112G) 与 IEEE 802.3dj (224G) 的原生物理参数库，支持一键无缝切换：

打开 `create_config.py`，在文件头部修改全局开关 `DEFAULT_MODE`：
```python
# ==========================================
# 🚀 核心全局开关 (一键切换物理底层模式)
# 可选值: '112G', '224G', '448G'
# ==========================================
DEFAULT_MODE = '112G'
```
直接运行 `python main.py`，系统将自动装载：
* **112G 模式**：56 GBd，40 GHz 光电器件，自动挂载 **IEEE 802.3ck** C2M 16dB 原生信道模型。
* **224G 模式**：112.5 GBd，80 GHz 光电器件，自动挂载 **IEEE 802.3dj** 原生信道模型。
* **448G 模式**：212.5 GBd，150 GHz 光电器件，自动启动 ZTE 频轴缩放算法拟合 150GHz CBW 极限物理环境。

## 💡 均衡器配置底座
* **Tx FFE**: 9-tap T-Spaced，架构锁死，权重预留供贝叶斯优化器寻优。
* **Rx FFE**: 31-tap T/2 Spaced，内置 LMS 自适应盲调。
* **DFE**: 默认全关，防止高误码率下的雪崩式错误传播 (Error Propagation)。
* **MLSE**: 默认开启 (Memory=1)，搭配 Burg 算法处理残余色噪，系统优化以拉大 MLSE 的判决裕度为唯一目标。

*(注：历史的 Baseline 测试结果已清空归档，当前系统已全面转向以 **MLSE BER** 为终极目标的严格物理评估。接下来我们将基于此真实的物理底座进行完全自研（White-Box）的寻优与极限冲刺。)*

## 📚 文档导航 (Documentation Navigation)

为保证项目整洁可读，本平台的文档已进行全面梳理，请通过以下入口深入了解：

👉 **[01. DSP 架构与核心参数详解](docs/01_DSP_Architecture.md)**  
> *了解收发机模型、多采样率机制以及 `config.xlsx` 中几十个神秘参数的详细物理含义。*

👉 **[02. 独立分析与诊断工具集 (Utility Scripts)](docs/02_Utility_Scripts.md)**  
> *探索 `scratch/` 目录下为您准备的信道频响查看器、单纯形寻参脚本等神兵利器。*

👉 **[03. 调试排坑与经验沉淀 (Troubleshooting History)](docs/03_Troubleshooting_History.md)**  
> *查阅过去在 DFE 误差传播、发送端相位失真以及 FFE 抽头对齐上走过的弯路，避免重蹈覆辙。*

## 三、 核心寻优算法 (Core Algorithms)
项目当前搭载了多种白盒化重构的寻优算法，用以对比各类元启发式搜索在物理约束下的表现：
- **GA (Genetic Algorithm)**: 经典连续遗传算法，全局寻优能力极强，但在线试错代价极大。
- **SA (Simulated Annealing)**: 带激进退温机制的模拟退火算法，容易陷入次优谷底。
- **SHC (Safe Hill Climbing)**: 针对 LPO 链路优化的安全爬山算法，微小步进，对链路冲击极小，但存在盲搜坠崖风险。

### 在线安全寻优 (Safe Online Optimization) 原型验证
在“所测即所发生”的硬性限制下，我们实现并对比了以下算法解决掉锁危机的能力：
- [Safe Hill Climbing (SHC)](docs/shc_principle.md): 工业界最保守、带退避机制的安全爬山法。
- [Safe Quadratic Coordinate Descent (Safe QCD)](docs/safe_qcd_principle.md): **(推荐)** 纯数学架构的二阶优化器。它通过微探针 (Micro-Probe) 探测物理梯度，利用二次抛物线精确求解悬崖边界与极值点。在 112G 的多种子盲测中表现出零方差的绝对稳定性，从理论和实测两方面彻底根除了 SHC 随机大步幅引发的掉锁危机。
- Bayesian Optimization (BO): 用作理论极值探索的对照组，非白盒。

👉 **[04. 寻优算法全景图 (Optimization Algorithms Panorama)](docs/04_Optimization_Algorithms.md)**  
> *全面梳理项目中现存的 8 种白盒化算法（BO, GA, SA, SHC, ESC, Surrogate_SHC, Safe_GP, Safe_QCD），阐述其代码现状、原理机制、测试表现及多模无缝切换用法。*

---

## ⚡ 快速上手 (Quick Start)

### 1. 配置虚拟环境并安装依赖
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```
*(注：本项目已彻底移除所有第三方黑盒优化库，所有算法（如 BO, GA, SA 等）均已实现 100% 纯 Numpy/Scipy 白盒化，确保每一行梯度与探索逻辑均可追溯。)*

### 2. 执行主仿真
只需运行 `main.py`，系统将自动生成最新的 `config.xlsx` 并输出当前的 BER 结果：
```bash
python main.py
```

### 3. 发端权重智能寻优 (Tx FFE Auto-Optimization)
如果要在当前 Mode 下寻找最优的 Tx FFE 权重，只需运行：
```bash
python optimize_tx_ffe.py
```
> [!NOTE]
> 优化器支持在 `config.xlsx` (由 `create_config.py` 生成) 的 `tx` 表格中通过 `optimizer_type` 无缝切换以下四种完全自研的白盒算法：
> 1. **`BO` (贝叶斯优化)**：适用于从零开始的全局探索与局部收敛混合寻优。
> 2. **`GA` (连续型遗传算法)**：基于种群的锦标赛交叉与多点高斯变异，用于大范围连续演化。
> 3. **`SA` (受限模拟退火)**：局部抖动探索，增加硬性退化拒绝阈值，防止优化跑飞。
> 4. **`SHC` (安全微步爬山)**：**针对在线实时调参专门设计**。严格锁定极微小步长，跳过危险的全局随机探索，确保硬件评估过程中的中间参数也始终稳定在极低误码率，彻底杜绝调参导致掉线的风险。
> [!TIP]
> **想看中间眼图？**
> 打开 `create_config.py`，在 `system` 栏将 `plot_intermediate_eyes` 改为 `True`，系统将自动吐出经过高平滑度上采样的各个物理节点眼图照片（如 ADC 采样端、Tx 出射端等）。
