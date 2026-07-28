# 04. 寻优算法全景图 (Optimization Algorithms Panorama)

[返回主页](../README.md)

在高速 DSP (112G/224G/448G) 的参数调优中，寻找能够“在线、安全、高效”收敛的最佳均衡器权重是本平台的核心研究目标。随着项目演进，我们从经典的全局盲搜算法逐步进化到了基于物理反馈的二阶安全寻优算法。

本文档全面梳理了项目中现存的所有算法，阐述其代码现状、原理机制、测试表现及使用方法。

---

## 1. 算法体系分类 (Taxonomy)

当前 `eLPO_antigravity` 代码库中搭载了 8 种白盒化算法，它们按照“对信道悬崖的感知与规避能力”可以分为三大阵营：

### 阵营 A：全局探索派 (Global Explorers)
这类算法追求理论上的全局极值，存在大步幅的跳跃式搜索，极易在线上触发断链危机（适用于离线仿真，或作为性能天花板的参考底线）。
- **`GA` (Genetic Algorithm, `ga_optimizer.py`)**: 遗传算法。利用种群交叉与变异进行大范围探索，试错成本极高。
- **`SA` (Simulated Annealing, `sa_optimizer.py`)**: 模拟退火。带激进退温机制的局部抖动探索，易陷入次优谷底。
- **`BO` (Bayesian Optimization, `bo_optimizer.py`)**: 标准贝叶斯优化。基于高斯过程建模，利用 UCB/EI 采集函数在全局寻找最优点，但探索阶段依赖大跨度跳跃。

### 阵营 B：一阶局部安全派 (Local Safe 1st-Order Climbers)
以极小步长进行试探，发现恶化立刻退避。防守严密，但面对平缓地带收敛极慢，且本质上仍是盲搜，存在微小踏空风险。
- **`SHC` (Safe Hill Climbing, `shc_optimizer.py`)**: 工业界最基准的安全爬山法。详情见 [SHC 原理](shc_principle.md)。
- **`ESC_Safe` (Extremum Seeking Control, `esc_optimizer.py`)**: 极值搜索控制。通过注入微小抖动信号（Dither）并提取低频包络来追踪梯度。由于超参数敏感，在高度非凸的信道中极易失控。

### 阵营 C：代理与二阶数学防御派 (Surrogate & 2nd-Order Defenders)
本项目针对“零侥幸、防掉线”目标研发的高阶自研算法体系。
- **`Surrogate_SHC` (Directional Tabu Filter, `surrogate_shc_optimizer.py`)**: 
  - **原理**：为 SHC 安装了“方向禁忌雷达”。当某个方向的探索曾导致崩溃，雷达会利用余弦相似度一票否决后续指向该死亡方向的试探。详见 [Surrogate SHC 原理](surrogate_shc_principle.md)。
- **`Safe_GP` (Safe Bayesian Optimization, `safe_gp_optimizer.py`)**: 
  - **原理**：真正的数学防线 (SafeOpt)。通过自研纯 Numpy 的高斯过程，严格限制算法只能在 $UCB < 10^{-2}$ 的置信度安全圈内活动。
- **`SafeQCD` (Safe Quadratic Coordinate Descent, `safe_qcd_optimizer.py`)**: **（当前终极推荐）**
  - **原理**：二阶抛物线求根算法。彻底抛弃概率盲搜，通过极微探针计算信道曲率（Hessian），利用二次方程 $ax^2 + bx + c$ 直接求出悬崖坐标并钳制跳跃步幅。详见 [Safe QCD 原理](safe_qcd_principle.md)。

---

## 2. 方案对比与测试结果 (Comparison & Results)

为了用铁证说明各个方案解决问题的能力，我们设计了以下验证方法：

### 测试方法
- **测试脚本**：`compare_optimizers.py`（算法大乱斗，考察全局收敛深度）和 `prove_surrogate.py`（5 个固定随机种子的最恶劣环境双盲测试，专门压榨算法的 `Worst BER`）。
- **测试环境**：112G 模式，锁死极差的初始 FFE 和 CTLE 权重，强迫算法在悬崖边缘向上攀爬。
- **安全红线**：只要中间测试中出现的 `MLSE BER` 超过 $10^{-2}$，即视为发生严重掉线事故。

### 统计结果对比 (基于 prove_surrogate.py 5种子盲测)

| 算法阵营 | 算法名称 | 原理缺陷/优势 | 盲测平均最差 BER (Max BER) | 安全性评级 |
| :--- | :--- | :--- | :--- | :--- |
| **一阶盲搜** | **SHC** | 步子迈大容易摔，步子小收敛慢。没有记忆，可能重复踩坑。 | **$1.27 \times 10^{-2}$** *(已触碰红线)* | ⚠️ 高风险 |
| **高斯安全集** | **Safe_GP** | 用 UCB 限制探索半径。但因各维度敏感度不均，在敏感维度易越界。 | **$2.09 \times 10^{-2}$** *(越界坠崖)* | ❌ 失败 |
| **二阶防线** | **Safe QCD** | 利用微探针算曲率，求根公式锁死边界。各维度自适应跳跃。 | **$5.54 \times 10^{-3}$** *(绝对压制)* | 🛡️ **绝对安全** |

**结果解读**：
`Safe QCD` 在所有随机种子下的测试中实现了 **0 方差**，最差表现被严格锁定在安全线之下（不到 $6 \times 10^{-3}$）。这证明了它从根本上消灭了探索阶段的“侥幸成分”。

---

## 3. 代码现状与调用用法 (Code Status & Usage)

### 代码现状
目前所有的算法文件均以 `*_optimizer.py` 的格式存放于项目根目录。所有代码均遵循 **White-Box (白盒化)** 准则，采用纯 `numpy/scipy` 实现，未调用任何隐藏梯度的黑盒高阶库。
旧算法的代码及其演进历史完整保留，作为对比基线。

### 平台用法
要在平台中启用不同的算法进行调优，无需修改代码，完全通过全局配置驱动：

1. 打开由 `create_config.py` 生成的 `config.xlsx`。
2. 找到 `tx` (发送端) 配置表。
3. 修改 `optimizer_type` 字段。
   - 设为 `SafeQCD`：启用推荐的安全微探针二阶调优（最稳妥）。
   - 设为 `SHC`：回退至传统安全爬山法。
   - 设为 `BO`：忽略安全性，全速冲击理论最优极值。
4. 运行 `python optimize_tx_ffe.py`，系统将自动挂载指定优化器，输出中间参数的眼图并向着目标 BER 演进。
