# DDPS 版本变更记录

> 本文件记录每个版本的核心变化。只记"变了什么"，不记排错过程。

## v6.2（当前版本）

### gain 纳入梯度（第 7 维）
- gain 从"锁定 per-case target_rms"改为**第 7 个搜索维**：参数向量 `x = [4 FFE 旁瓣, gDC, gDC2, u_gain]`，`u_gain = log10(g / g0)`。
- gain 初值仍来自每个 case 单独扫描最优 RMS 解析得的 gain（不是标称值），之后放开走 Model A 的**7 维链式梯度**（gain 维扰动 u_gain → 重算探针，只有 drive_rms 变）。
- gain 信任域收紧到 `±0.15 dex`（围绕 per-case 初值），防止跨环境方向反转；形状/CTLE 信任域不变。

### 标称 gain 重标定
- `DRIVER_GAIN_NOMINAL` 从 0.4381 改为 **0.3399**（按 peaking 链 `rms_at_unity=0.6763` 重标：`g0 = 0.617×0.3726 / 0.6763`）。旧值 0.4381 是 v4 无 peaking 链的残留常量。
- 连带修正了 per-case RMS 扫描的 GAIN_MIN 钳位：旧扫描对低 gain 用例被钳在 GAIN_MIN，报告的目标 RMS 与真实驱动 RMS 对不上（如 IL10x20_RxHeavy 旧值 0.06 → 新标 0.160，CD28ps 0.06 → 0.150）。

### 训练数据重做
- 数据集 `--v62`：driver_gain 作为独立采样维（`x_6 = u_gain`），在 u 空间均匀覆盖**全用例 per-case 最优 gain 邻域 ×0.20~×1.26**（`u ∈ [-0.70, +0.10]`，相对新标称 0.3399）。此前 v6.1 的 gain 窄带（相对旧标称 0.4381 的 ×0.40~×1.00 = 绝对 0.175~0.438）不含基线最优 gain（0.138），训练数据覆盖不到真实操作点。
- 种子行仍锚定基线 per-case 扫描最优 gain；采样盒 7 维 LHS；块长 1048576 符号 × 3 种子（约 2001 行）；12 进程并行。

### 模型 / 结果
- 复用 A/B 白盒 Ridge 结构（A 8 维探针、B 7 维参数域；gain 经 drive_rms 进入两代理）。Model A Spearman=0.832 / R²=0.666，Model B Spearman=0.835 / R²=0.702（rho=1.752）。
- 在线测试（15 用例，2097152 符号 × 3 种子）：**14/15 用例相对起点改善、1 用例持平、0 用例退步**；几何平均改善 ×1.09（最高 ×1.50，Comb_IL20x20_CD15_DGD5）；全程 198 步真实 BER，27 步劣于起点（B 拦截全程未触发）。
- A-only 消融与主流程基本一致（Comb_IL20x20 在 A-only 下 ×1.52 略高于主流程 ×1.49），确认 B 拦截是"保险"而非被依赖的拦截。

## v6.1（已归档）

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
