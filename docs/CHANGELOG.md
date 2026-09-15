# DDPS 版本变更记录

> 本文件记录每个版本的核心变化。只记"变了什么"，不记排错过程。

## v6（当前版本）

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
