# 04. DDPS 数据驱动物理代理寻优

[🔙 返回主页](../README.md)

在高速 LPO（Linear Pluggable Optics）链路中，信道极度受限、不允许长 DFE，系统寻优面临高维非凸挑战。为解决寻优慢、易掉锁的问题，本平台原创了 **DDPS (Data-Driven Physical Surrogate)** 双层代理寻优架构：**绝不在真实硬件上随机试错，而是通过完全脱机的"沙盘推演"寻找收发端联合最优解。**

---

## 1. 背景与设计思路

传统黑盒优化（BO / GA 等）直接把 `[FFE 系数, CTLE]` 扔进黑盒看真实 `BER`，有两大致命缺陷：

1. **真实物理评估极慢**：一次 MLSE BER 涉及光纤色散卷积与维特比解码。
2. **高维空间稀疏**：10 维空间盲目撒点，掉进"不掉锁区域"的概率极低。

**DDPS 的破局思路**：发送端均衡的本质是改变"入纤前的物理冲激响应 (Tx FIR)"。这个 Tx FIR 比冷冰冰的数字系数包含更多与收端眼图质量直接相关的物理特征。若能训练映射 `f(Tx FIR) -> BER`，寻优时就不必跑百万 symbol 过真实信道，只需：

1. 算当前配置下的单脉冲 `Tx FIR`（矩阵运算，瞬间完成）；
2. 丢给模型 `f` 瞬间预测相对 `BER`；
3. 对该模型求偏导，用梯度下降"滑"向最优解。

---

## 2. 发端物理探针（白盒坍缩）

`tx_channel_extract.py` 作为发端物理探针，向系统打入一个理想单位脉冲（Dirac Delta），脉冲依次穿过：数字 Tx FFE → DAC 零阶保持 → 模拟 Tx CTLE → 宿主 PCB 走线（S 参数）→ 电光调制器低通。随后在入纤前捕获并对齐截取 **7-tap 等效数字 FIR**——这就是当前配置对应的"最终物理真实发射波形"。这一步把复杂的硬件参数等效坍缩为纯粹的发射端冲激响应。

---

## 3. 两阶段架构与双代理

### Stage 1：离线探索与代理训练（模型供给）
Stage 1 的任务**不是**找最优解，而是"探明地形、积累数据"。在安全工作点 `x0` 邻域做拉丁超立方 (LHS) 采样，离线评估 `[系数, Tx FIR, 真实 BER]`，训练两个白盒代理。

### Model A（物理代理，指路）
- 输入：探针算出的 7-tap Tx FIR；输出：`log10(MLSE BER)`。
- 价值：复杂频率响应已被探针解完，Model A 只学"发出去的波形长什么样 → 收端 BER 多好"的轻量映射。

### Model B（配置代理，刹车）
- 输入：直接配置 `[8 个 FFE + gDC + gDC2]`（10D）；输出：`log10(MLSE BER)`。
- 价值：不走探针、直接全局映射，在梯度下降中充当"刹车"，评估候选点是否会坠入断崖劣化区（防掉锁）。

---

## 4. 白盒数学（纯 Numpy，面向芯片）

两个模型**不使用任何深度学习黑盒或第三方库（无 sklearn）**，均采用手写二阶多项式 Ridge 回归（`train_surrogates.py`）：

1. **特征扩展**：把输入 $X=[x_1,\dots,x_d]$ 显式展开为常数项 + 一次项 + 平方项 + 两两交叉项：
   $$ \Phi(X)=\big[1,\ \underbrace{x_1,\dots,x_d}_{\text{一次项}},\ \underbrace{x_1^2,\dots,x_d^2}_{\text{平方项}},\ \underbrace{x_1x_2,\dots,x_{d-1}x_d}_{\text{交叉项}}\big] $$
   原始 $d$ 维变为 $D=1+2d+\tfrac{d(d-1)}{2}$ 维。
2. **闭式求解**：$W=(\Phi^T\Phi+\alpha I)^{-1}\Phi^T Y$。
3. **极速推理**：$Y_{pred}=\Phi(X)\cdot W$（一次内积）。

> 另有白盒 `WhiteBoxGPR`（RBF 核 + 闭式后验）作为可选的替代代理，能额外输出不确定性 $\sigma$，用于 UCB 护栏；主流程默认用 Ridge（最简、最贴芯片）。

---

## 5. Stage 2：约束梯度下降（不回传真实 BER）

由 `ddps_optimizer.py` 驱动，从 `x0` 出发做手写投影梯度下降：

1. **代理求导**：在 Model A 上用有限差分算 10D 梯度（毫秒级）。
2. **线搜索安全检查**：沿负梯度给候选点，交给 Model B 审查；越红线则步长折半重试，直到绿灯。
3. **闭环更新**：决策层全程不跑真实物理信道验证，真实 BER 只作旁路记录（验证用，绝不参与下一步决策）。

---

## 6. 10D CTLE 升维

早期模型只抽象一个 CTLE 直流增益（9D）。当前已**完全遵照 IEEE 802.3ck 与 LPO MSA v1.01** 升维：

- `apply_ctle` 引入完整双级增益公式（双零点 + 双增益 gDC/gDC2）；
- 状态空间 9D → **10D**（8 个 FFE + gDC + gDC2）；
- `tx_channel_extract` 与 `dataset_generator` 全量适配 10 自由度 LHS 采样。

---

## 7. 跨环境泛化与免校准

一旦 Model A 学到 `Tx FIR -> 眼图质量` 的单调关系，它在**物理损伤平移**下依然稳健——在 10 dB 基线训练的模型可直接用于 20 dB 极限插损 + CD + DGD，无需重训。跨环境免校准的两个原因：

1. **梯度只依赖相对单调性**：Stage 2 用梯度方向 `g/|g|`，绝对底噪平移不影响方向。
2. **Model B 动态红线**：安全判定是"相对种子点的预测恶化 ≤ 容忍阈值"，天然抵消全局基线漂移。

> **最新突破（物理模型补丁）**：在补回 Driver 显式增益、ENOB 量化、激光相位噪声等硬核物理限制后，链路噪声显著上升。之前曾出现因发端特征提取未同步物理链路中的自动增益控制（AGC）逻辑，导致 Model A 提取的 FIR 振幅剧变、测试 R² 暴跌并引发梯度发散。在 `tx_channel_extract.py` 中严格补偿真实的物理 AGC 和带限衰减后，Model A（7-tap FIR → BER）重新恢复了方向指示能力（R² 回升）。Stage 2 的跨环境在线调优（如极限 20dB 插损、复合色散与偏振模色散）再次实现了从起点稳步下探并成功收敛的泛化神话，彻底告别发散。详见 `result/ddps/generalization_summary_physical.md`。

---

## 8. 日志 / 结果

运行 `test_generalization.py` 后，在 `result/ddps/` 下产生：
- `generalization_summary_physical.md` / `.csv`：各应力用例的最优收敛指标汇总；
- `ddps_gen_physical_*.png`：各用例收敛曲线（实线 Real MLSE vs 虚线 Model A 预测）。

---

## 9. 历史算法索引（已归档）

以下古典优化器及早期原型已从主线移除，完整保留在 **`sjtu-channel-model` 分支**的 `archive/`（`algorithms/` + `docs/`），仅供历史参考：

- **TuRBO-Safe**：贝叶斯模型 + 动态信任域。
- **SafeQCD**：纯数学二阶优化器（微小摄动探测梯度/曲率 + 抛物线悬崖边界）。
- **Two-Stage Online Optimization**：DDPS 前身（BO_Safe + GPR 眼图特征）。
- **Surrogate-SHC**：代理辅助爬山。
- **传统基线 (SHC / GA / SA / ESC)**：详见 `sjtu-channel-model` 分支 `archive/docs/Baselines.md`。
