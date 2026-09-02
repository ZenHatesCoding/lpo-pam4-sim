# 物理信道建模升级 (Physical Channel Upgrade)

本文档记录了从原有抽象的高斯噪声模型向具体的微观物理器件模型升级的理论基础与实现进度。

## 1. MZM 与 Laser 建模 (E-O Conversion)

在发射端的光电转换中，我们引入了激光器的 RIN（相对强度噪声）和 MZM（马赫-曾德尔调制器）的传递函数。

- **激光器 RIN (Relative Intensity Noise)**
  $$ \sigma_{RIN}^2 = 10^{\frac{RIN}{10}} \cdot \text{BW} \cdot P_{in}^2 $$
  其中，RIN 单位为 dB/Hz，$P_{in}$ 为激光器输出光功率。我们将这个高斯分布的功率波动叠加到恒定光场能量上：
  $$ P_{laser} = P_{in} + \mathcal{N}(0, \sigma_{RIN}^2) $$
  $$ E_{in} = \sqrt{P_{laser}} $$

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

## 3. 测试与验证用例 (Stress Cases)

升级后的 `stress_cases` 现在由物理参数控制，包含：
1. **case_baseline**: 基线状态，低 CD，正常 RIN (-150 dB/Hz)，正常 TIA 噪声。
2. **case_cd_dgd_stress**: 极限色散与群延迟恶化。
3. **case_high_loss**: 极高的 PCB 插损，考察线性补偿能力。
4. **case_high_noise**: 高 RIN 噪声与高 TIA 热噪声恶化环境。
5. **case_combined_stress**: 综合极限恶化。

## 4. 全局 SNR 机制的彻底废弃

在早期的模型中，使用单一的 `snr_db` (如 26.5 dB) 来强行注入 AWGN 以模拟链路衰化。在此次物理模型升级后，已将该代码从 `channel_imdd.py` 以及所有的测试脚本中**彻底移除**。现在的信噪比表现完全是分布式的物理器件特性（RIN、热噪声、散粒噪声、TIA 噪声）叠加微量 Host PCB 噪声（1mV）的自然结果，真正实现了从宏观“黑盒噪声”向微观“白盒物理”的全面对齐。

## 进度记录
- [x] 更新 `config.xlsx`
- [x] 实现器件传递函数
- [x] 修复 MZM 方程中的倍数差异和接收端 AGC 的噪声敏感问题 (使用 RMS)
- [x] 修复光纤传输中的色散分离问题：CD 作用于光场 (Complex FFT)，DGD 作用于检波后功率 (Real FFT)
- [x] 重新生成训练集并训练 Surrogate 模型
- [/] 验证 DDPS/SHC 泛化性能
