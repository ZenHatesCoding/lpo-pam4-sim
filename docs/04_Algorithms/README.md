# 核心寻优算法全景图 (Optimization Algorithms Panorama)

[返回项目主页](../../README.md)

本项目定位为底层硬件算法的原型验证，核心宗旨是彻底拒绝将算法细节封装隐藏的“黑盒”。目前平台搭载了 8 种完全自研（White-Box）的物理梯度搜索与连续优化算法。

> [!IMPORTANT]
> **Live Tuning (在线硬调) 的绝对红线**
> 在真实的 112G/224G 光电链路在线调优中，任何探索行为如果导致测试误码率突破 $10^{-2}$，将引发硬件纠错码 (FEC) 击穿与物理链路“掉锁”。
> 所有的离线大范围探索算法（如传统 GA、SA、标准 BO）在在线环境中均具有极高的坠崖断链风险，我们必须设计带有严格物理安全约束的新型算法。

为应对离线寻优与在线硬调的不同场景需求，本目录对现有算法进行了分类梳理：

## 1. 两阶段在线调优架构 (Two-Stage Workflow)
这是针对 LPO 链路极为苛刻的防掉锁要求所设计的混合架构方案。

👉 **[两阶段在线优化工作流 (Two-Stage Online Optimization)](Two_Stage_Optimization.md)**  
**当前状态**：核心服役中 | **代码路径**：`two_stage_optimize.py`  
**简介**：通过将优化过程拆分为“Stage 1: 离线探索获取好初值与地形记忆”以及“Stage 2: 基于 Surrogate 代理约束的零抖动在线微调”，完美融合了全局深层探索能力与在线零坠崖的绝对安全跟踪能力。我们在 1e-4 及 1e-5 (百万 Symbols) 级别证明了 **SA $\rightarrow$ Surrogate_SHC** 与 **BO $\rightarrow$ Surrogate_SHC** 是兼顾深度与安全性的绝佳组合。

👉 **[DDPS 数据驱动物理代理优化器 (Data-Driven Physical Surrogate)](DDPS.md)**  
**当前状态**：离线极限冲刺组 | **代码路径**：`ddps_optimizer.py`  
**简介**：完全离线的“数据驱动”路线。离线采一批 `(配置 → 真实 BER)` 数据，训练双 Ridge 代理（Model A 看发端物理 FIR、Model B 看原始配置），再用 SLSQP 在代理上寻优，并通过“物理回验 + 主动学习”迭代下钻。与在线安全算法互补，适合无代价环境下的深度冲刺。

## 2. 在线安全调优单体算法 (Live Tuning)
这是专门为物理链路“不掉锁”设计的单体防御性算法。

👉 **[TuRBO-Safe (推荐极品)](TuRBO_Safe.md)**  
**当前状态**：核心服役中 | **代码路径**：`bo_optimizer.py`  
**简介**：为了在“不掉锁”和“寻优深度”之间实现不可调和的融合，我们设计并实现了 **TuRBO-Safe** 算法。该算法通过贝叶斯模型 ($3\sigma$ 置信度) 与动态信任域的结合，成为目前唯一能够同时满足严苛安全限制与全局最优深度的生产级方案。

👉 **[SafeQCD (数学微探针方案)](SafeQCD.md)**  
**当前状态**：核心服役中 | **代码路径**：`safe_qcd_optimizer.py`  
**简介**：纯数学推导的二阶优化器。改用微小摄动（Micro-Probe）探测局部梯度与曲率，并通过抛物线方程精确计算悬崖边界，从而在数学层面阻断坠崖风险。极度安全，但极易陷入局部极小。

👉 **[Surrogate_SHC (代理辅助爬山)](Surrogate_SHC.md)**  
**当前状态**：核心服役中 | **代码路径**：`surrogate_shc_optimizer.py`  
**简介**：通过 IDW (逆距离权重) 等代理记忆模型在物理下发前进行数学推演，主动规避历史危险点。在“两阶段架构”中作为完美的 Stage 2 跟踪收尾算法。

## 2. 传统基线与离线参考组 (Baselines)
这些是业界标准算法的白盒化实现。虽然在寻优深度上表现不俗，但由于缺乏“事前安全预测”，在在线环境中具有极高的“一脚踏空”断链风险，主要用于离线理论极值探索与作为测试对照组。

👉 **[传统基线算法详解 (SHC / GA / SA / ESC)](Baselines.md)**
- **SHC (Safe Hill Climbing)** (`shc_optimizer.py`)：工业界最原始的步进退避爬山法，无预判能力。
- **ESC_Safe (极值搜索控制)** (`esc_optimizer.py`)：基于连续 Dither 的梯度解调，极易被信道噪声淹没跑飞。
- **GA (遗传算法)** (`ga_optimizer.py`)：全局演化王者，但变异跃迁会直接引发物理断链。
- **SA (模拟退火)** (`sa_optimizer.py`)：带概率接受机制的局部退火，高温期等同于随机送死。

## 3. 测试方法与用法通用说明
所有算法的性能对照验证可通过执行 `compare_optimizers.py` 进行。
该脚本会自动初始化各算法，统一调用 `objective_function` 进行硬核物理试错，并忠实记录每次评估代价，最终输出对比日志与收敛图表（保存在 `result/latest_comparison/` 中）。

要在主仿真模块 `main.py` 或 `optimize_tx.py` 中切换算法，只需在全局配置文件 `config.xlsx` 的 `tx` 表格中修改：
```yaml
optimizer_type: 'BO_Safe'  # 或 'SafeQCD', 'SHC', 'GA' 等
```
