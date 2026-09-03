# 物理信道建模升级 (Physical Channel Upgrade)

本文档记录了从原有抽象的高斯噪声模型向具体的微观物理器件模型升级的理论基础与实现进度。

## 1. MZM 与 Laser 建模 (E-O Conversion)

在发射端的光电转换中，我们引入了激光器的 RIN（相对强度噪声）和 MZM（马赫-曾德尔调制器）的传递函数。

- **激光器 RIN (Relative Intensity Noise)**
  $$ \sigma_{RIN}^2 = 10^{\frac{RIN}{10}} \cdot \text{BW} \cdot P_{in}^2 $$
  其中，RIN 单位为 dB/Hz，$P_{in}$ 为激光器输出光功率。我们将这个高斯分布的功率波动叠加到恒定光场能量上：
  $$ P_{laser} = P_{in} + \mathcal{N}(0, \sigma_{RIN}^2) $$
  $$ E_{in} = \sqrt{P_{laser}} $$

- **激光器相位噪声 (Phase Noise / Linewidth)**
  线宽 $\Delta\nu$ 对应一个维纳相位随机游走（Wiener process）：
  $$ \Delta\phi \sim \mathcal{N}\!\left(0, \sqrt{2\pi\,\Delta\nu\,\Delta t}\right),\qquad \phi(t) = \sum_t \Delta\phi $$
  $$ E_{in} = \sqrt{P_{laser}}\cdot e^{\,j\phi(t)} $$
  在 IMDD 直接探测链路中，单激光器相位噪声是两臂共模量，只有在光纤色散 (CD) 把相位调制转化为强度调制后才会进入判决统计；因此 **CD=0 时相位噪声透明、CD 应力用例下才真正加压**——这与物理一致。

- **MZM 传递函数**
  对于推挽式 MZM，电光响应描述为：
  $$ E_{out} = E_{in} \cdot \left(\gamma e^{j\frac{\pi}{V_\pi}(V_{in}(t) + V_{bias})} + (1-\gamma)e^{-j\frac{\pi}{V_\pi}(V_{in}(t) + V_{bias})}\right) $$
  其中 $\gamma$ 由消光比 ER 决定。
  **特别注意 (MZM 驱动摆幅坑点)**：若使用过大的 $V_{pp}$ (如 2.0V) 驱动 $V_\pi = 3V$ 的 MZM，信号将严重超出余弦曲线的线性区，导致中间眼图极大、上下眼图闭合的极度非线性失真。通过代码排查确认，SJTU 实际入 MZM 的摆幅为 `0.617V`。我们将 `driver_vpp` 校准为此值以保证光调制的线性度。

## 2. PIN 与 TIA 建模 (O-E Conversion)

在接收端，PIN 光电二极管将光场转换回电流，并加入散粒噪声与热噪声。TIA 负责电压放大并叠加自身的等效输入噪声。

- **散粒噪声 (Shot Noise)**
  $$ \sigma_{shot}^2 = 2 \cdot q \cdot I_{pd} \cdot \text{BW} $$
  其中 $q$ 是电子电荷，$\text{BW}$ 是奈奎斯特仿真带宽。

- **热噪声 (Thermal Noise)**
  $$ \sigma_{thermal}^2 = \frac{4 \cdot k_B \cdot T}{R_L} \cdot \text{BW} $$
  其中 $k_B$ 是玻尔兹曼常数，$T$ 为温度，$R_L$ 是等效负载电阻。

- **TIA 输入参考噪声**
  $$ \sigma_{tia\_v} = Gain_{TIA} \cdot \text{Noise}_{TIA} \cdot \sqrt{\text{BW}} $$
  这里 $\text{Noise}_{TIA}$ 单位为 $\text{A}/\sqrt{\text{Hz}}$。

## 2.5 Driver 显式增益 + DAC/ADC 量化 (补回的有源/数字器件损伤)

这是本轮对齐 SJTU 模型的核心补全。此前 Driver 只是一个"纯摆幅归一化"（没有真正的增益、没有带限、没有把前端噪声随增益一起放大），DAC/ADC 是理想器件。这导致高插损下性能被过度乐观估计。

- **Driver 显式增益（与带限解耦）**
  链路顺序严格对齐 SJTU：`电信道插损 -> 1mV 前端热噪声 -> VGA 摆幅控制 -> Driver 真增益 -> Driver 带限`。
  - `driver_gain = 2.0`（线性，≈6 dB，对应 SJTU `DriverParams.Vpp=2.0`）是一个**固定真增益**，不随插损变化；
  - VGA 摆幅控制位于增益之前，负责把信号缩放到"经固定增益后恰好 `driver_vpp=0.617 V`"；
  - 关键点：1 mV 前端热噪声被放在**增益之前**，因此会被 VGA+Driver 增益一起放大——插损越高、补偿增益越大、前端噪声被放大越多。这纠正了此前"增益免费、噪声不放大"的错误。
  - `driver_bw`（默认 40 GHz）是独立的带限滤波（与增益解耦），其平坦损耗由下游 TIA/ADC 的 AGC 归一化吸收。

- **DAC / ADC 量化 (ENOB)**
  `dac_enob = adc_enob = 5.5`（0 表示理想）。采用中平 (mid-tread) 均匀量化器，满量程 = `max|x|`，无削波：
  $$ \Delta = \frac{2\cdot\max|x|}{2^{ENOB}},\qquad x_q = \text{round}(x/\Delta)\cdot\Delta $$
  DAC 量化施加在 ZOH 之前（2 sps 数字样点），ADC 量化施加在抽取之后（2 sps 数字样点）。

## 3. 测试与验证用例 (Stress Cases)

升级后的 `stress_cases` 现在由物理参数控制，包含（插损均为每方向 Tx/Rx 对称）：
1. **case_baseline**: 基线状态，默认插损 **10 dB**，低 CD，正常 RIN (-150 dB/Hz)，正常 TIA 噪声。
2. **case_cd_dgd_stress**: 10 dB 插损 + 极限色散 (28 ps/nm) 与群延迟 (5 ps) 恶化。
3. **case_high_loss**: 最差插损 **20 dB**（对齐 LPO MSA 7.2.1 的 die-to-die 上限），考察线性补偿能力。
4. **case_high_noise**: 10 dB 插损 + 高 RIN (-140 dB/Hz)、低 ER (15 dB)、高 TIA 噪声 (25 pA/√Hz)。
5. **case_combined_stress**: 20 dB 插损 + CD (15 ps/nm) + DGD (3 ps) + 高噪声综合极限。

> 插损基准依据 `docs/LPO_MSA_Specification_Summary.md`：LPO MSA 7.2 将 OIF 最大电插损由 13 dB 扩展至 16 dB（奈奎斯特），7.2.1 规定 **Host ASIC die 到 Module die 的端到端插损不超过 20 dB**（= Host package 4 dB + Host PCB 12 dB + Connector 2 dB + Module PCB 2 dB）。因此最差用例取 **20 dB die-to-die**。

## 4. 全局 SNR 机制的彻底废弃

在早期的模型中，使用单一的 `snr_db` (如 26.5 dB) 来强行注入 AWGN 以模拟链路衰化。在此次物理模型升级后，已将该代码从 `channel_imdd.py` 以及所有的测试脚本中**彻底移除**。现在的信噪比表现完全是分布式的物理器件特性（RIN、热噪声、散粒噪声、TIA 噪声）叠加微量 Host PCB 噪声（1mV）的自然结果，真正实现了从宏观“黑盒噪声”向微观“白盒物理”的全面对齐。

## 进度记录
- [x] 更新 `config.xlsx`
- [x] 实现器件传递函数
- [x] 修复 MZM 方程中的倍数差异和接收端 AGC 的噪声敏感问题 (使用 RMS)
- [x] 修复光纤传输中的色散分离问题：CD 作用于光场 (Complex FFT)，DGD 作用于检波后功率 (Real FFT)
- [x] 重新生成训练集并训练 Surrogate 模型
- [/] 验证 DDPS/SHC 泛化性能
- [x] 补回 Driver 显式增益 + 带限（与摆幅控制解耦），前端噪声移到增益之前
- [x] 补回 DAC/ADC ENOB 量化 (5.5 bit)
- [x] 补回激光器相位噪声 (线宽 10 MHz)
- [x] 刷新应力用例：默认插损 10 dB、最差 20 dB（LPO MSA 7.2.1 die-to-die）
- [x] 修复 CD 单位 bug：`apply_cd` 的 `D` 系数由 `1e-12` 改为 `1e-3`（此前 CD 相位被削弱 1e9 倍，色散应力近乎失效）
- [x] 修复发端 FIR 提取的插损缩放一致性（此前 `extract_tx_s21` 用原始 S4P 16 dB，与实际信道 10/20 dB 不一致）
- [x] 全流程重跑（dataset_v2 / models_v2 / result_v2）
