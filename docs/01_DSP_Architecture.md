# 01. DSP 架构与参数说明

[🔙 返回主页](../README.md)

本项目是一个纯白盒实现的 112G/224G PAM4 LPO (Linear Pluggable Optics) 通信链路仿真平台。它主要由三个模块构成：发送端 (Tx DSP)、信道模型 (Channel) 和接收端 (Rx DSP)。所有参数均通过根目录下的 `config.xlsx` 进行管理和下发（也可在运行时动态覆盖）。

---

## 1. 核心架构说明

### 1.1 发送端 (Tx DSP)
由于 LPO (Linear Pluggable Optics) 模块内部不包含 DSP，所有的发送端均衡均由 Host ASIC 完成。
- **纯线性 FFE**：我们移除了会引入严重相位失真的 IIR 连续时间 CTLE，只使用 FIR 结构的 Tx FFE。
- **预加重 (Pre-emphasis)**：为了抵抗信道严重的高频衰减，Tx FFE 的抽头（如 `[-0.14, 0.8, -0.06]`）会故意对高频分量进行预放大。

### 1.2 信道模型 (Channel)
- **多采样率仿真**：DSP 核心以 2 Sps（每个符号 2 个采样点）运行，而在信道（包括 MZM 调制器、光纤色散模型、探测器）中，信号将被上采至 8 Sps，以更精确地模拟模拟链路的物理特性。
- **插损归一化 (Insertion Loss Scaling)**：为了保证物理模型贴近标准，信道响应在应用前会经过动态频率缩放（`f_scale`），强行对齐在奈奎斯特频率（Nyquist Frequency）处产生精确的 `-18 dB` 插入损耗。

### 1.3 接收端 (Rx DSP)
- **模拟 CTLE**：LPO 模块本身仅包含模拟驱动器，这里我们实现了一阶连续时间线性均衡器（CTLE），提供一定程度的高频提振。
- **数字 FFE (T/2 Spaced)**：Host ASIC 接收端使用分数间隔 (Fractional-Spaced) FFE 均衡器。通过内置的 LMS (最小均方差) 算法结合泄漏系数 (Tap Leakage) 和岭回归 (Ridge Regression)，有效防止了在强衰减频带上的抽头发散和爆炸。
- **完全解耦的 DFE**：由于误差传播在极高误码率下会导致系统雪崩，我们默认关闭了 DFE (`dfe_taps = 0`)，仅用其作为基线对照组。
- **高阶 MLSE**：内置了基于 Viterbi 算法的 MLSE，支持基于信道脉冲响应 (或部分响应目标) 的序列估计，用以突破线性 FFE 的理论物理极限。

---

## 2. `config.xlsx` 关键参数字典

### [System] 全局配置
- `baud_rate`: 112.5e9 (即 112.5 GBd，对应 224G PAM4)。
- `sps_dsp` / `sps_channel`: DSP 与模拟信道的采样率（通常为 2 和 8）。
- `snr_db`: 加性白高斯噪声 (AWGN) 的信噪比设定，默认 `25 dB`。
- `plot_intermediate_eyes`: `True`/`False`。控制是否绘制中间各个物理节点的 50Sps 高清平滑眼图，输出至 `result/`。

### [Tx] 发送端配置
- `ffe_taps`: Tx FFE 总抽头数。
- `ffe_pre`: Tx FFE 前向（Pre-cursor）抽头数，决定了中心主抽头的位置。
- `custom_taps`: 手动指定的固定抽头数组。

### [Rx] 接收端配置
- `ffe_taps` / `ffe_pre`: Rx FFE 的总抽头与前向抽头数配置。
- `dfe_taps`: DFE 抽头数（设为 0 即为纯线性均衡）。
- `train_len`: LMS 训练序列长度（目前前 2000 个符号用于训练，之后冻结抽头以防误码传播）。
- `lms_mu`: 训练步长。
- `mlse_memory`: 维特比算法的记忆深度。

---

[🔙 返回主页](../README.md)
