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
* **光物理层应力容限测试**：已将 IEEE 标准中的色散 (CD) 和差分群时延 (DGD) 白盒化。可通过 `config.xlsx` 中的 `stress_cases` 工作表进行任意应力组合的独立配置（支持偏振角度动态控制和极限陷波测试）。

## 💡 均衡器配置底座
* **Tx FFE**: 9-tap T-Spaced，架构锁死，权重预留供贝叶斯优化器寻优。
* **Rx FFE**: 31-tap T/2 Spaced，内置 LMS 自适应盲调。
* **DFE**: 默认全关，防止高误码率下的雪崩式错误传播 (Error Propagation)。
* **MLSE**: 默认开启 (Memory=1)，搭配 Burg 算法处理残余色噪，系统优化以拉大 MLSE 的判决裕度为唯一目标。

*(注：历史的 Baseline 测试结果已清空归档，当前系统已全面转向以 **MLSE BER** 为终极目标的严格物理评估。接下来我们将基于此真实的物理底座进行完全自研（White-Box）的寻优与极限冲刺。)*

## 📚 文档导航 (Documentation Navigation)

为保证项目整洁可读，本平台的文档已进行全面梳理，请通过以下入口深入了解：

👉 **[LPO 信道升级与参数依据 (LPO Channel Upgrade Justification)](docs/LPO_Channel_Upgrade_Justification.md)**  
> *LPO_MODE 下的 Tx 9-tap FFE、22-tap T-spaced Rx FFE+1-DFE 及 7dB 典型插损的完全对齐与自检报告。*

👉 **[01. DSP 架构与核心参数详解](docs/01_DSP_Architecture.md)**  
> *了解收发机模型、多采样率机制以及 `config.xlsx` 中几十个神秘参数的详细物理含义。*

👉 **[02. 独立分析与诊断工具集 (Utility Scripts)](docs/02_Utility_Scripts.md)**  
> *探索 `scratch/` 目录下为您准备的信道频响查看器、单纯形寻参脚本等神兵利器。*

👉 **[03. 调试排坑与经验沉淀 (Troubleshooting History)](docs/03_Troubleshooting_History.md)**  
> *查阅过去在 DFE 误差传播、发送端相位失真以及 FFE 抽头对齐上走过的弯路，避免重蹈覆辙。*

👉 **[04. DDPS 数据驱动物理代理寻优框架](docs/04_DDPS_Optimization_Framework.md)**  
> *详解本平台原创的 Zero-Shot 双层代理寻优架构：基于 10D (FFE+双级CTLE) 物理探针的有限差分梯度下降与线搜索安全约束。*

👉 **[05. 微观物理信道模型升级记录](docs/05_Physical_Channel_Upgrade.md)**  
> *记录从抽象的高斯噪声模型升级至 SJTU 级微观光电物理模型（MZM 非线性、光纤色散与DGD、热/散粒噪声）的完整过程及抗噪排坑经验。*

## 三、 核心在线寻优算法 (DDPS)
项目已经彻底抛弃了高代价的传统盲搜算法（如遗传算法、模拟退火等），全面转向完全自研的**数据驱动物理代理寻优框架 (DDPS)**。

👉 **[DDPS 数据驱动物理代理优化器 (Data-Driven Physical Surrogate)](docs/04_Algorithms/DDPS.md)**  **(核心主推架构)**
> *这是应对在线调参“试错成本高、易掉锁”痛点的终极解决方案。DDPS 将优化拆分为两阶段：*
> * **Stage 1 (离线/近线)**：在安全区附近采样（包含对光纤 CD 色散和插损抗性的等效 FIR 映射），训练出纯白盒的 Model A (Tx等效FIR -> log10 BER，负责指引下探方向) 与 Model B (完整软硬件配置 -> log10 BER，包含 GPR 不确定度，负责守住安全红线)。
> * **Stage 2 (在线)**：彻底切断真实物理反馈，在 Model A 的曲面上利用手写有限差分进行**带预条件自适应步长的投影梯度下降**，并由 Model B 进行安全线搜索回溯约束。
> 
> *在最近的纯物理噪音+MLSE深度验证中，DDPS 在应对诸如 `12dB 极限插损` 或 `Combined_Stress (高插损+色散+DGD混合灾变)` 时，均能在零断链风险下平滑收敛，精准权衡 FIR 补偿与 CTLE 高频噪声防爆之间的物理悖论。*

> [!NOTE]
> 早期测试用的古典算法（BO, GA, SA, SHC 等）及其相关对比测试脚本，现已统一清理并封存于 `archive/` 目录下，仅供历史参考。

---

## ⚡ 快速上手 (Quick Start)

### 1. 配置虚拟环境并安装依赖
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 执行单点主仿真
只需运行 `main.py`，系统将自动生成最新的 `config.xlsx` 并输出当前的硬件评估与 BER 结果：
```bash
python main.py
```

### 3. 全链路代理数据集生成与模型训练
若要生成适应当前硬件拓扑特征的代理模型集（自动加载开启 Burg AR 与 Viterbi MLSE 后置滤波），请依次执行：
```bash
# 生成 LHS 随机微扰空间数据集 (默认输出至 dataset_mlse)
python dataset_generator.py --out_dir dataset_mlse

# 白盒矩阵求逆训练 Model A & B (默认输出至 models_mlse)
python train_surrogates.py --dataset dataset_mlse/ddps_dataset_<timestamp>.csv --out_dir models_mlse
```

### 4. DDPS 极致应力泛化测试
使用训好的代理双模型，直接在线引导不同极端信道参数下的寻优：
```bash
python test_generalization.py
```
> [!TIP]
> 运行结束后，请移步至 `result/mlse_comparison/ddps/` 目录查看 `generalization_summary_physical.md` 报表与各个物理用例的收敛下降曲线。你将见证在零物理试错下，Model A 与 Model B 是如何默契配合跨越险崖的！
