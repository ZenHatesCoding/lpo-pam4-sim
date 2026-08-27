# LPO MSA Specification (v1.01) - 核心参数提炼与指南

本文档总结了从 `LPO_MSA_Specification_v1p01.pdf` 中提取的关键电气、光学和信道物理参数。这些参数是配置 `config.xlsx` 和底层信道模型的重要依据。

## 1. 系统与拓扑总览
- **速率与调制**: 100 Gb/s 每通道, **53.125 GBd PAM4**。
- **介质与传输**: 单模光纤 (SMF)，波长 1310 nm，目标传输距离 **0.5 m 至 500 m**。
- **FEC**: 假定系统采用主机的 RS(544,514) FEC，要求 FEC 纠错前误码率 (Raw BER) $\le 2.0 \times 10^{-4}$，纠错后 FLR (Frame Loss Ratio) $\le 6.2 \times 10^{-11}$。

## 2. 电气信道插损 (Electrical Channel Insertion Loss)
LPO 规范在 OIF CEI-112G-LINEAR-PAM4 基础上扩展了最大允许电插损。所有测量基准点在奈奎斯特频率 (**Nyquist = 26.56 GHz**)。
- **总端到端插损 (Host ASIC die to Module die)**: 推荐不超过 **20 dB**。
- **主机侧链路分配 (Host ASIC die to Module connector)**: 最大允许 **16 dB** (较原有 CEI 的 13 dB 增加 3 dB)。
- **各物理段参考损耗分配**:
  - Host PCB: 最大 12 dB
  - Connector: 2 dB
  - Module PCB (含耦合电容): 2 dB

## 3. 电气节点规范与噪声分布 (Distributed Electrical Parameters)

### 3.1 Host Tx (TP1a: Host Output)
- **VMA (Voltage Modulation Amplitude)**:
  - 若 Host loss > 13 dB: 175 mV ~ 350 mV
  - 若 Host loss $\le$ 13 dB: 200 mV ~ 350 mV
- **测试参考均衡器 (Reference FFE)**: 9 抽头 (9-tap) 前馈均衡器。
- **EECQ (Electrical Eye Closure PAM4)**: 最大允许 3.5 dB (对于损耗 > 13dB)。

### 3.2 Module Tx (TP1: Module Input / Stressor)
测试 Module Input 时使用的压力测试参数：
- **随机抖动 (Random Jitter, RJ)**: 最大 10 mUI RMS。
- **正弦抖动 (Sinusoidal Jitter)**: 约 0.05 UI pk-pk (高频处)。

### 3.3 Module Rx (TP4: Module Output)
- 模块输出端 **EECQ**: 最大 7 dB。

### 3.4 Host Rx (TP4a / TP4: Stressed Host Input)
对主机接收端进行压力测试时（模拟最劣模块和链路情况），校准注入的幅值噪声 (Amplitude Noise) 和抖动：
- **Host Loss = 5 dB 时**: 注入幅度噪声 = **3 mV RMS**
- **Host Loss = 13 dB 或 16 dB 时**: 注入幅度噪声 = **6 mV RMS**
- **随机抖动**: 最大 10 mUI RMS。

## 4. 光学规范 (Optical Specifications)

### 4.1 发送端 (TP2: Transmit Optical)
- **平均发射功率 (Average Launch Power)**: -2.9 dBm ~ 4.0 dBm。
- **OMA (Optical Modulation Amplitude)**: 最大 4.2 dBm。
- **TECQ / TDECQ**: 最大 3.4 dB。

### 4.2 接收端 (TP3: Receive Optical)
- **接收灵敏度 (OMA_outer) (TECQ $\le$ 1.4 dB)**: 最大 -5.1 dBm。
- **加压接收灵敏度 (Stressed Receiver Sensitivity, OMA_outer)**: -3.1 dBm。
- **测试参考均衡器**: 9-tap 符号间隔 FFE 均衡器。

## 5. 对仿真模型的指导意义
在 `channel_imdd.py` 中的实施原则：
1. **去中心化噪声**: 废弃原本利用统一电 `snr_db` 拟合全链路的简单模型。根据标准，需要在 DAC 输出端、驱动端 (VGA)、TIA 输出端以及 ADC 输入端分别根据物理等效（如 3~6 mV RMS）来分配分布式的加性高斯白噪声。
2. **非对称电插损滤波**: Host->Module (Tx) 和 Module->Host (Rx) 两段独立配置电气信道，允许两端的插损不一样，最高支持 16 dB（26.56GHz）的损耗滤波。对于 S4P 滤波器的接入，需要针对 Tx 和 Rx 的目标插损分别进行频率轴缩放 (Frequency Scaling)。
