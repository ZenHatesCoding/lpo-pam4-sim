# LPO PAM4 (112G/224G/448G) DSP 基线仿真平台

本项目是一个基于纯 Python (Numpy/Scipy) 白盒构建的 **Linear Pluggable Optics (LPO)** 系统级仿真器，主要用于跨多代速率（112G/224G/448G）下的高速信道纯线性均衡算法研究与评估。

> [!NOTE]
> 本项目的核心理念是 **“白盒化” (White-Box)** 与 **“符合物理直觉”**。
> 我们移除了容易在超高误码率下发生雪崩效应的 DFE，并禁止对发送端架构做随意扩增（锁死在 T-spaced 5 抽头）。系统强制通过真实的 S4P 级联网络与纯线性 FIR 结构探索性能边界。

## 🚀 核心架构与多模切换 (Multi-Mode Switch)

本平台已全面打通 IEEE 802.3ck (112G) 与 IEEE 802.3dj (224G) 的原生物理参数库，支持一键无缝切换：

打开 `create_config.py`，在文件头部修改全局开关 `DEFAULT_MODE`：
```python
# 可选值: '112G', '224G', '448G'
DEFAULT_MODE = '112G'
```
直接运行 `python main.py`，系统将自动装载：
* **112G 模式**：56 GBd，40 GHz 光电器件，自动挂载 **IEEE 802.3ck** C2M 16dB 原生信道模型。
* **224G 模式**：112.5 GBd，80 GHz 光电器件，自动挂载 **IEEE 802.3dj** 原生信道模型。
* **448G 模式**：212.5 GBd，150 GHz 光电器件，自动启动 ZTE 频轴缩放算法拟合 150GHz CBW 极限物理环境。
* **光物理层应力容限测试**：已将 IEEE 标准中的色散 (CD) 和差分群时延 (DGD) 白盒化。可通过 `config.xlsx` 中的 `stress_cases` 工作表进行任意应力组合的独立配置。

## 💡 均衡器配置底座
* **Tx FFE**: 5-tap T-Spaced（4 个旁瓣自由变量 + 1 个派生主抽头），架构锁死，权重供 DDPS 梯度下降寻优。
* **Rx FFE**: 22-tap T-Spaced（LPO 模式），内置 LMS 自适应盲调。
* **DFE**: 默认全关（`dfe_taps=0`），防止高误码率下的雪崩式错误传播。
* **MLSE**: 默认开启 (Memory=1) + Burg AR 白化，Viterbi 4 态联合解码。开启时自动锁死 DFE。

> [!IMPORTANT]
> 平台统一终极指标 = **`BER_MLSE`**（MLSE 判决输出、Gray 映射 BER）。
> 所有代理训练标签、收敛曲线与报告均以 `log10(BER_MLSE)` 为准。

*(注：历史 Baseline 与 DDPS v1（物理模型修复前）的测试结果已归档到 `archive/20260904_ddps_v1_physical_pre_v2/`，见 [06. DDPS v2 重做报告](docs/06_DDPS_v2_Rerun.md)。)*

> [!TIP]
> 📊 **结果与图件索引见 [`result/SUMMARY.md`](result/SUMMARY.md)**：以“只用基线训练 → 跨环境
> 泛化”为核心，15 用例横向对比、逐用例参数对照、预测-实测跟踪诊断与全部图/数据链接。

## 📚 文档导航 (Documentation Navigation)

| 文档 | 内容 |
| --- | --- |
| [📄 **DDPS v4 交付说明（对外呈现件 · 自包含 HTML）**](DDPS_v4_Deliverable.html) | **一份文件讲清整件事**：链路与三组自由度（FFE/CTLE/Driver 增益）、A/B 双代理如何适配、百分比拦截判据、11 轴方向实测标定、数据与评估协议、逐用例 A/B/实测**三曲线收敛图**与全部结果（9 节结构，可离线打开直接呈现） |
| [01. DSP 架构与核心参数详解](docs/01_DSP_Architecture.md) | 收发机模型、多采样率机制、`config.xlsx` 参数物理含义 |
| [02. 独立分析与诊断工具集](docs/02_Utility_Scripts.md) | `scratch/` 下的信道频响查看器、寻参脚本 |
| [03. 调试排坑与经验沉淀](docs/03_Troubleshooting_History.md) | DFE 误差传播、发送端相位失真、FFE 抽头对齐等踩坑记录 |
| [04. DDPS 数据驱动物理代理寻优](docs/04_DDPS_Optimization.md) | Zero-Shot 双层代理寻优架构（Model A/B、Stage 2 约束梯度下降、7 维搜索空间） |
| [05. 微观物理信道模型升级记录](docs/05_Physical_Channel_Upgrade.md) | 抽象高斯噪声 → SJTU 级微观光电物理模型的升级过程 |
| [06. DDPS v2 重做报告](docs/06_DDPS_v2_Rerun.md) | v1 负向优化根因排查与 v2 全链路重做（数据/训练/在线调优/可视化） |
| [**07. DDPS v3 模型修正与评估协议**](docs/07_DDPS_v3_Model_Update.md) | （v4 之前的记录）CTLE 位置修正、driver_gain 可调、块长/种子实测 —— 已被 v4 取代 |
| [**08. DDPS v4 模型与算法口径**](docs/08_DDPS_v4_Model_Update.md) | 无 VGA/无 RMS 固定的链路口径、Driver 增益标定与倍率搜索箱、三组自由度杠杆实测、**A/B 双代理（核岭均值 + 保守上包络）与按变差百分比拦截**、11 轴方向实测标定、只用基线 2001 点的数据与协议 |
| [LPO MSA 规范核心参数提炼](docs/LPO_MSA_Specification_Summary.md) | 电气/光学/信道参数标准依据（插损、噪声分配等） |
| [分支关系与版本导览](BRANCHES.md) | 仓库各分支（main / feature / sjtu-channel-model / physical-model）的关系与差异，以及本文档地图 |

> 早期古典优化器（BO / GA / SA / SHC 等）已归档在 **`sjtu-channel-model` 分支** 的 `archive/`，
> 分支关系与“archive/ 去哪了”速查见 [分支关系与版本导览](BRANCHES.md)。
> **v3 与更早**的数据/模型/结果/交付件归档于 `archive/`（按仓库政策不入库，仅留磁盘；git 历史完整保留）：
> `archive/20260904_ddps_v1_physical_pre_v2/`、`archive/20260910_ddps_v2_pre_ctle_reorder/`、
> `archive/20260911_ddps_v3_pre_no_vga/`（后者含 v3 全部产物，并说明 v4 为何与之不可比）、
> `archive/20260911_ddps_v4_probe_polyRidge/`（v4 第一轮"波形探针 + 二阶 Ridge"的模型与结果）。

## ⚡ 快速上手 (Quick Start)

### 1. 配置虚拟环境并安装依赖
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 执行单点主仿真
```bash
python main.py
```

### 3. 全链路代理数据集生成与模型训练（DDPS v4）
```bash
# 只用基线环境（IL10x10）采样 2000 点，7 维 LHS（5-tap FFE 的 4 个旁瓣 + CTLE×2 + 增益）：
#   核心 1200 点：FFE ±0.075 / CTLE ±2.0 dB / 增益 ±0.20 dex（下降轨迹真正经过的小邻域）
#   外壳  800 点：FFE ±0.10  / CTLE ±3.0 dB / 增益倍率 ×0.30~×4.00（整箱覆盖）
# 单点真实 BER_MLSE = 262144 符号 × 3 个仿真种子取 log10 均值；--jobs 多进程并行（与串行逐位一致）
python dataset_generator.py --base-samples 2000 --anchor-samples 0 \
    --only-envs Base_IL10x10 --num-symbols 262144 --sim-seeds 42,43,44 \
    --jobs 14 --core-samples 1200

# 白盒核岭回归训练 Model A（方向，解析梯度）& B（保守上包络）；输入均为 7 维搜索向量 x
python -c "from train_surrogates import train_v4; import glob;\
f=sorted(glob.glob('dataset/ddps_v4_dataset_*.csv'))[-1]; train_v4(f, 'models/ddps_v4')"
```

### 4. DDPS v4 在线调优泛化测试 + 可视化报告
```bash
# 冻结模型，逐场景（对称/非对称插损、CD、DGD、复合、器件噪声）做 Stage-2 约束下降；
# 真实 BER_MLSE 只记录不回传；拦截按 Model B 预测的变差百分比（≤ +25%）
python test_generalization.py --model-dir models/ddps_v4 --out-dir result/ddps_v4_main \
    --num-symbols 262144 --sim-seeds 42,43,44 --n-steps 15 --cloud-n 8

# 可视化报告：**三曲线收敛图（Model A / Model B / 实测 BER）** + 抽头/CTLE/增益轨迹/眼图 + 深水复核
python report_ddps_v4.py --test-dir result/ddps_v4_main --model-dir models/ddps_v4 \
    --deep-symbols 524288 --summary "result/ddps_v4_main:三组自由度全开" \
    --summary-out result/SUMMARY.md
```

### 5. 模型方向实测标定（回答"模型到底对不对"）
```bash
# 在真实链路上对种子工作点沿 11 个搜索轴做中心差分（22 次真实 BER 评估，不参与训练），
# 与 Model A 的解析梯度逐轴对照：方向命中率 / 加权命中率 / 量级相关系数
python tools/validate_local_gradient.py --model-dir models/ddps_v4 --env Base_IL10x10 \
    --num-symbols 262144 --sim-seeds 42,43,44 --out result/ddps_v4_local_gradient.csv

# 顺带把"预测下降而实测上升"这件事量化清楚（逐用例 Δ预测 vs Δ实测）
python tools/diagnose_divergence.py --test-dir result/ddps_v4_main \
    --model-dir models/ddps_v4 --out result/ddps_v4_divergence.csv
# trace 记账复核：用独立重仿真逐点核对记录值
python tools/verify_trace.py --test-dir result/ddps_v4_main \
    --envs Base_IL10x10,IL20x20 --steps 0,3,7,14
```
> 运行结束后，报告在 `result/ddps_v4_main/report/`：**`ddps_v4_convergence.png`（每个用例的
> Model A / Model B / 实测 BER 三曲线，用来看在线调优是否单调下降）**、`ddps_v4_report.md`、
> 各用例 `_a/_b` 图（收敛/抽头/CTLE 频响/增益倍率轨迹/眼图/频谱/FFE 输出分布）、
> `ddps_v4_overview.png`、`deep_check.csv`；跨实验汇总写到 `report/SUMMARY.md`。
>
> **链路口径、增益标定、三组自由度杠杆、拦截判据与数据协议** 见
> [08. DDPS v4 模型与算法口径](docs/08_DDPS_v4_Model_Update.md)。
