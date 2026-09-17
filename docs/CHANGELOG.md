# DDPS 版本变更记录

> 本文件记录每个版本的核心变化。只记"变了什么"，不记排错过程。

## v6.1（当前版本）

### 物理层修正
- Tx CTLE 拓扑改为 OIF 2Z3P peaking 形式：分子 `1 + jf·(K_DC/fz)`，零点位于 `fz/K_DC`，直流增益恒 0 dB。`g_dc_db` 语义改为高频 peaking gain（dB）。原实现 `(g_dc + jf/fz)` 在 `fz==fp1` 时零极点对消成低通，Nyquist 处反而衰减。
- CTLE 零极点比例改为 SJTU 标准：`fz=fb/2.862, fp1=fb/1.884, fp2=fb, flf=fb/40`。
- 新增 Rx 模拟 CTLE 级（TIA→Rx IL→Host Rx 噪声→Rx CTLE→ADC），固定参数 `gDC=6 dB, gDC2=3 dB`（SJTU standard），不参与优化，作为静态均衡基座。
- CTLE 优化边界改为 peaking 语义：`g_dc ∈ [0,12] dB, g_dc2 ∈ [0,4] dB`。种子点 `gDC=6, gDC2=2`。
- 评估符号数拉长至 2^20（数据集）/ 2^21（在线测试），可靠分辨 1e-5 量级。

### 验证
- Tx CTLE 传递函数：gDC=6 dB 时 Nyquist 处 +5.89 dB（修正前为 −7 dB）。
- 最终在线测试（15 用例，2097152 符号 × 3 种子）：15/15 改善、0 劣化，最优 BER_MLSE 全部进入 1e-5 量级（1.93e-5 ~ 4.63e-5）。
- 对比 v6（物理层修正前）：IL20x20 1.52e-3 → 4.61e-5（改善 ~33 倍）；Comb_IL20x20 7.52e-3 → 4.63e-5（~162 倍）。
- 块长研究（Base_IL10x10 最优工作点）：BER 随块长每翻倍约 −0.3 dex（LMS/MLSE 收敛效应），2^18=1.76e-4、2^19=8.21e-5、2^20=4.23e-5、2^21=1.98e-5。

## v6（已归档）

### 架构
- A=探针→BER（8 维波形域：7-tap Tx FIR + drive_rms）
- B=参数→BER（7 维参数域：4 FFE 旁瓣 + gDC + gDC2 + drive_rms）
- 梯度通过 A 的链式法则：扰动 6 维参数 → 重算探针 → 查 A → 得 ΔBER
- gain 不在 A/B 搜索向量，由 per-case target_rms 物理驱动

### 物理层
- 5-tap Tx FFE → DAC → Tx IL → CTLE → Driver → MZM → 光纤 → PIN → TIA → Rx IL → ADC → Rx FFE → MLSE
- 无 VGA，无 RMS 归一化

### 结果
- 15/15 用例正向改善，平均 ×5.16，最高 ×39.44
- 153 步 0 劣化
- CTLE 激活 12/15（gDC 调到 ±2.5）
- A-only 与 A+B 结果完全一致（B 红线全程未触发）

### 安全红线
- 红线 = 当前最优点 B 预测 × 1.25（随最优点下移，不用种子点 B 预测）

### 三组训练对比实验
- 组 A 基线训练 (IL10x10, 工程标定种子): ×5.16, 15/15, 0 劣化
- 组 B IL20x20 训练 (BO 寻优种子, gDC2=-4.95): ×2.66, 14/15, 11 劣化
- 组 C IL20x20 训练 (梯度下降终点种子, gDC2=-2.66): ×6.67, 12/15, 41 劣化
- 结论: 低损环境训练泛化性最好；种子点选择决定模型对哪个区域学得准

## v5（已归档）

- 6 维 x_shape 统一输入（A/B 共用），gain 发端 RMS 物理驱动
- 架构错误：A/B 输入空间相同，误差不独立
- 9-tap FFE，VGA 归一化

## v4（已归档）

- 11 维搜索空间（9-tap FFE + gDC + gDC2 + gain）
- KernelRidge 代理
- VGA 固定 RMS 归一化

## v3（已归档）

- 修正 Tx 链 CTLE 位置和 driver_gain 被 VGA 抵消的问题
- 9-tap FFE，绝对 0.3 log10 安全裕度

## v2（已归档）

- 首次跨环境泛化验证（8 环境）
- 9-tap FFE，7-tap 探针
- 修复 v1 的符号格错位、梯度门控缺失等问题

## v1（已归档）

- 初始版本，负向优化（Model A 下降但真实 BER 反向变差）
- 根因：Stage-1 邻域采样死代码、FFE 参数化不一致、符号格错位
