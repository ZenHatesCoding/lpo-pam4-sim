# LPO PAM4 (112G/224G) DSP 基线仿真平台

本项目是一个基于纯 Python (Numpy/Scipy) 白盒构建的 **Linear Pluggable Optics (LPO)** 系统级仿真器，主要用于 112.5 GBd (224G PAM4) 速率下的高速信道均衡算法研究与评估。

> [!NOTE]
> 本项目的核心理念是 **“白盒化” (White-Box)** 与 **“符合物理直觉”**。我们移除了容易在超高误码率下发生雪崩效应的 DFE，并摒弃了会引入极强相位失真的发射端模拟 IIR-CTLE。系统强制通过真实的 S4P 级联网络与纯线性 FIR 结构探索性能边界。

## 🎯 当前最佳基线 (State-of-the-Art Baseline)
目前，该项目已经在 **-18 dB 的奈奎斯特插入损耗** 与 **25 dB 加性白噪声** 限制下，达到了其单线性理论物理极限：
* **Tx FFE**: 3-tap `[-0.14, 0.8, -0.06]` (无 Tx CTLE)
* **Rx FFE**: 31-tap T/2 Spaced (内置 LMS 泄漏与脊回归，防漂移发散)
* **最终 BER**: **3.0% (3.00e-02)** (稳定无雪崩)

*(这是向 1e-4 目标进军的绝佳跳板，接下来可无缝衔接高阶 MLSE 及 PR 目标解码！)*

## 📚 文档导航 (Documentation Navigation)

为保证项目整洁可读，本平台的文档已进行全面梳理，请通过以下入口深入了解：

👉 **[01. DSP 架构与核心参数详解](docs/01_DSP_Architecture.md)**  
> *了解收发机模型、多采样率机制以及 `config.xlsx` 中几十个神秘参数的详细物理含义。*

👉 **[02. 独立分析与诊断工具集 (Utility Scripts)](docs/02_Utility_Scripts.md)**  
> *探索 `scratch/` 目录下为您准备的信道频响查看器、单纯形寻参脚本等神兵利器。*

---

## 🚀 快速上手 (Quick Start)

### 1. 配置虚拟环境并安装依赖
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install numpy scipy matplotlib scikit-rf pandas openpyxl
```

### 2. 执行主仿真
只需运行 `main.py`，系统将自动读取 `config.xlsx` 并输出 BER 结果：
```bash
python main.py
```
> [!TIP]
> **想看中间眼图？**
> 打开 `config.xlsx`，在 System 栏将 `plot_intermediate_eyes` 改为 `True`，系统将在 `result/` 目录下吐出经过 50Sps 极高平滑度上采的各个物理节点眼图照片（如 ADC 采样端眼图、Tx 出射端眼图等）。

## 📈 后续优化目标
- [ ] 结合 Partial Response (部分响应) Target 与 Viterbi MLSE 算法，在不使用 DFE 的情况下进一步消除 Residual ISI，向 1e-4 BER 逼近。
- [ ] 探索通过高斯过程贝叶斯优化器 (`bo_optimizer.py`)，进行端到端的收发信联合自动寻优。
