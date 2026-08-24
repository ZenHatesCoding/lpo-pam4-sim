# DDPS 任务交接说明

> 给接手的 Agent。先读这份，再动手。重点看「非协商约束」和「已踩过的坑」，避免重复走弯路。

## 一、一句话现状

DDPS（Data-Driven Physical Surrogate，数据驱动物理代理优化器）**已经跑通并验证**：白盒、两阶段、不回传真实 BER，
在 112G 下从起点 `1.44e-3` 收敛到 `3.76e-05`（DEEP_1E5，追平 SHC 基线）。代码在分支 `feature/ddps-optimization`，
已推送到远端，最新提交 `047ad2e`，工作树干净。

## 二、非协商约束（甲方底线，别碰）

1. **7-tap 发端 FIR 是固定约束**。仿真器里的 `extract_tx_s21` 只是真实系统"获取 7 个发端抽头"的等效占位；真实
   系统另有手段获取，但**就是 7 个**。**不要加抽头、不要做"换更丰富发端特征"去提升它**——那等于改题目。上次
   我加 15/31 抽头做特征消融，被甲方否了，见下方"需要清理的东西"。
2. **两阶段的核心底线**：
   - Stage 1（离线标定）：**可以崩、可以拿到真实端到端 BER**；
   - Stage 2（在线调优）：**不能崩、只能拿到发端指标**（拿不到真实收端 BER）。
   - 守住这条底线，其余（信任域 vs Model B 谁兜底、在线能不能更新模型）都可折衷。
3. **100% 白盒，面向芯片**：训练/推理、梯度计算，**禁用 sklearn、scipy.optimize 等现成算法**；numpy 最多，能手
   写都手写（Ridge 闭式解、多项式特征、有限差分梯度、GPR 闭式后验均已手写）。
4. **不要"统一架构"**：两阶段 GPR 方案与 DDPS 各自能 work 即可，强行抽象成一套框架是画蛇添足（甲方原话）。
5. **发端 FIR 怎么获取，不用操心**——甲方有办法，仿真器里不用做完整实现。

## 三、架构（已按甲方意图对齐）

- **Stage 1（模型供给）**：在起点 x0 邻域做 LHS 采样（FFE ±0.05 / CTLE ±3 dB），训练两个白盒 Ridge 代理：
  - **Model A**：发端 7-tap FIR → log10(BER)，作**寻优目标**；
  - **Model B**：FFE 9-tap + CTLE → log10(BER)，作**安全约束**。
  - 产出 = 起点 + 双模型，**不追求穷尽地形**（地形 9 维里极窄，全优化域 1000 个随机点 0 命中）。
- **Stage 2（约束下降，不回传真实 BER）**：手写投影梯度下降 `x_{k+1}=clip(x_k - lr·g/|g|, 信任域)`，
  - 梯度 g = Model A 有限差分；
  - 安全 = Model B 相对红线（`Model_B(x) ≤ Model_B(种子)+0.3`，校准无关）+ 信任域（FFE ±0.10 / CTLE ±6 dB）；
  - 步长 0.92 衰减收敛；真实 BER 只记录验证，**不参与方向决策**。

## 四、已验证的结果（可信，别推翻重来）

| 指标 | 数值 |
| --- | --- |
| 起点 x0（次优点） | `1.44e-03` @DEEP_1E5 |
| Stage 2 收敛（Ridge+GD，不回传） | `7.20e-04` @26.5dB → `3.76e-05` @DEEP_1E5 |
| 全程最大 BER（安全） | `7.99e-03`（仅首步过冲，全程 < 1e-2 无掉锁） |
| 跨 SNR 排序迁移 | 真实排序跨 SNR 完全不变（Spearman=1.0），Model A 排序 0.70 且与 SNR 无关 → **不用分桶** |
| 代理对比（Ridge/GPR/GPR+UCB） | 三者都收敛到 3.76e-05；GPR 收敛更快（step2 vs 3）、首步过冲更小；Ridge 最简、最贴芯片 |

## 五、已踩过的坑（接手时注意，别重新踩）

1. **纯随机全优化域采样 = 0 命中**（1000 个点 BER 全 > 0.17）。必须用起点邻域采样。
2. **FIR 提取 argmax 跳变** → Model A 不连续 → 梯度下降震荡。已改成**固定参考对齐**（`_fixed_peak_idx`）。
3. **Model B 绝对阈值失配**（预测偏悲观，绝对 -2.0 会把安全种子点误判成不安全）→ 已改成相对种子点的红线。
4. **scipy SLSQP 会顺着代理外推越界**（实测跳到 post1=0.19 死区）→ 信任域兜底。
5. **SLSQP 内部迭代被折叠成"1 步"**，甲方看不到优化过程 → 已换成手写、逐步可见的梯度下降。
6. **首步过冲 7.99e-3 离 1e-2 只差 1.25×**——这是已知隐患，未根治（可考虑 Armijo 线搜索压过冲），但不是阻塞项。

## 六、需要清理/待定

- **`feature_ablation.py` 是跑题的**（拿配置比 FIR、试 15/31 抽头），甲方明确否了"加抽头"。建议**删除**，并撤销
  `docs/04_Algorithms/DDPS.md` 里"为什么是 0.70"那一节里的抽头消融内容。结论只剩一条有用的："仿真器里配置排序
  更强，但真实系统里实测 FIR 可能更可靠，需真实数据定论"——这句可保留，抽头实验撤掉。
- **`tx_channel_extract.py` 的 `pre_cursors` 参数**是为抽头消融加的，若删 `feature_ablation.py` 可一并还原。
- **分支未合 `main`**：`feature/ddps-optimization` 只在特性分支上，需要的话开 PR / merge。

## 七、关键文件索引

- `ddps_optimizer.py` — 主流程（Stage1 采样/训练 + Stage2 手写梯度下降 + 跨 SNR 深水校验）
- `train_surrogates.py` — 白盒 Ridge + 白盒 GPR（训练/推理，纯 numpy）
- `tx_channel_extract.py` — 7-tap 发端 FIR 提取（固定参考对齐 + s4p 缓存）
- `dataset_generator.py` — 全优化域 LHS 采样（可选死区覆盖数据）
- `compare_surrogates.py` — Ridge/GPR/GPR+UCB 代理对比
- `cross_snr_ranking.py` — 跨 SNR 排序迁移实验
- `feature_ablation.py` — 跑题，待删
- `docs/04_Algorithms/DDPS.md` — DDPS 架构 + 结果 + 记录规范
- `result/latest_comparison/ddps/` — 可追踪的结果报告 + 图（ddps_convergence.png / cross_snr_ranking.png）

## 八、下一步（按甲方意图的候选方向，未经甲方拍板）

1. 把 Model A 的 feature 做成可插拔（`fir` / `config` / `fir+config`），**默认保留 `fir`**，供真实链路数据去定"哪个发端指标在物理世界里更稳"（仿真器定不了这个）。
2. 用 Armijo 线搜索压掉首步过冲，把安全做硬。
3. 对 Model A/B 的**绝对预测值**做单调/分位数校准（跨 SNR 排序已证明可迁移，绝对值需要校准后才能接绝对阈值）。
