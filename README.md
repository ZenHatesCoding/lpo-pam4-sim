# LPO PAM4 (112G/224G/448G) DSP 基线仿真平台

本项目是一个基于纯 Python (Numpy/Scipy) 白盒构建的 **Linear Pluggable Optics (LPO)** 系统级仿真器，主要用于跨多代速率（112G/224G/448G）下的高速信道纯线性均衡算法研究与评估。

> [!NOTE]
> 本项目的核心理念是 **“白盒化” (White-Box)** 与 **“符合物理直觉”**。
> 我们移除了容易在超高误码率下发生雪崩效应的 DFE，并禁止对发送端架构做随意扩增（锁死在 T-spaced 9 抽头）。系统强制通过真实的 S4P 级联网络与纯线性 FIR 结构探索性能边界。

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
* **Tx FFE**: 9-tap T-Spaced，架构锁死，权重预留供 DDPS 贝叶斯/梯度类优化器寻优。
* **Rx FFE**: 22-tap T-Spaced（LPO 模式），内置 LMS 自适应盲调。
* **DFE**: 默认全关（`dfe_taps=0`），防止高误码率下的雪崩式错误传播。
* **MLSE**: 默认开启 (Memory=1) + Burg AR 白化，Viterbi 4 态联合解码。开启时自动锁死 DFE。

> [!IMPORTANT]
> 平台统一终极指标 = **`BER_MLSE`**（MLSE 判决输出、Gray 映射 BER）。
> 所有代理训练标签、收敛曲线与报告均以 `log10(BER_MLSE)` 为准。

*(注：历史 Baseline 与 DDPS v1（物理模型修复前）的测试结果已归档到 `archive/20260904_ddps_v1_physical_pre_v2/`，见 [06. DDPS v2 重做报告](docs/06_DDPS_v2_Rerun.md)。)*

> [!TIP]
> 📊 **结果与图件索引见 [`result/SUMMARY.md`](result/SUMMARY.md)**：以“只用基线训练 → 跨环境
> 泛化”为核心（另附带锚点训练的上限对比与“冻结新增维度”的消融对照），15 用例横向对比、全部图与数据链接。

## 📚 文档导航 (Documentation Navigation)

| 文档 | 内容 |
| --- | --- |
| [📄 **DDPS v3 交付说明（对外呈现件 · 自包含 HTML）**](DDPS_v3_Deliverable.html) | **一份文件讲清整件事**：任务约束、平台全参数、模型如何建立与全部超参数、算法流程与复杂度、实测效果与边界（含全部图表，可离线打开直接呈现） |
| [01. DSP 架构与核心参数详解](docs/01_DSP_Architecture.md) | 收发机模型、多采样率机制、`config.xlsx` 参数物理含义 |
| [02. 独立分析与诊断工具集](docs/02_Utility_Scripts.md) | `scratch/` 下的信道频响查看器、寻参脚本 |
| [03. 调试排坑与经验沉淀](docs/03_Troubleshooting_History.md) | DFE 误差传播、发送端相位失真、FFE 抽头对齐等踩坑记录 |
| [04. DDPS 数据驱动物理代理寻优](docs/04_DDPS_Optimization.md) | Zero-Shot 双层代理寻优架构（Model A/B、Stage 2 约束梯度下降、11 维搜索空间） |
| [05. 微观物理信道模型升级记录](docs/05_Physical_Channel_Upgrade.md) | 抽象高斯噪声 → SJTU 级微观光电物理模型的升级过程 |
| [06. DDPS v2 重做报告](docs/06_DDPS_v2_Rerun.md) | v1 负向优化根因排查与 v2 全链路重做（数据/训练/在线调优/可视化） |
| [**07. DDPS v3 模型修正与评估协议**](docs/07_DDPS_v3_Model_Update.md) | CTLE 位置修正、driver_gain 由死参数变为可调维度、11 维空间、评估协议选择依据（块长/种子实测） |
| [LPO MSA 规范核心参数提炼](docs/LPO_MSA_Specification_Summary.md) | 电气/光学/信道参数标准依据（插损、噪声分配等） |
| [分支关系与版本导览](BRANCHES.md) | 仓库各分支（main / feature / sjtu-channel-model / physical-model）的关系与差异，以及本文档地图 |

> 早期古典优化器（BO / GA / SA / SHC 等）已归档在 **`sjtu-channel-model` 分支** 的 `archive/`，
> 分支关系与“archive/ 去哪了”速查见 [分支关系与版本导览](BRANCHES.md)。
> **v2 与更早**的数据/模型/结果/v1 归档于 `archive/`（按仓库政策不入库，仅留在磁盘；git 历史完整保留）：
> `archive/20260904_ddps_v1_physical_pre_v2/`、`archive/20260910_ddps_v2_pre_ctle_reorder/`
> （后者含 v2 数据集/模型/结果与旧交付件，并说明为何在 CTLE 位置与 driver_gain 修正后不可比）。

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

### 3. 全链路代理数据集生成与模型训练（DDPS v3）
```bash
# 生成"环境锚定邻域"数据集：基准环境 320 点密集 + 14 个应力环境各 60 点锚点，
# 覆盖 Stage-2 信任域（FFE ±0.10 / CTLE ±3 dB / driver_gain ±0.5），11 维 LHS；
# 单点真实 BER_MLSE 用 262144 符号 × 3 个仿真种子取均值（抑制 BER 估计噪声）；
# --jobs 多进程并行（结果与串行逐位一致）
python dataset_generator.py --base-samples 320 --anchor-samples 60 \
    --num-symbols 262144 --sim-seeds 42,43,44 --jobs 14

# 白盒多项式 Ridge 训练 Model A & B（Model A: 7-tap FIR 形状 + MZM 驱动 RMS；Model B: 12 维配置）
python -c "from train_surrogates import train_v3; import glob;\
f=sorted(glob.glob('dataset/ddps_v3_dataset_*.csv'))[-1]; train_v3(f, 'models/ddps_v3')"
```

### 4. DDPS v3 在线调优泛化测试 + 可视化报告
```bash
# 冻结模型，逐环境（对称/非对称插损、CD、DGD、复合、器件噪声）Stage-2 约束下降；
# 真实 BER_MLSE 只记录不回传（11 维：8 FFE 旁瓣 + gDC + gDC2 + driver_gain）
python test_generalization.py --model-dir models/ddps_v3 --out-dir result/ddps_v3_<ts> \
    --num-symbols 262144 --sim-seeds 42,43,44 --n-steps 15 --cloud-n 8

# 消融对照：冻结 CTLE 与 driver_gain，只优化 FFE（量化新增维度的贡献）
python test_generalization.py --model-dir models/ddps_v3_control \
    --out-dir result/ddps_v3_control_ffe_only --freeze-extra \
    --num-symbols 262144 --sim-seeds 42,43,44 --n-steps 15

# 可视化报告：收敛/抽头/CTLE 响应/driver_gain 轨迹/眼图/频谱 + 中文报告 + 深水复核
python report_ddps_v3.py --test-dir result/ddps_v3_<ts> --model-dir models/ddps_v3 \
    --deep-symbols 524288 --summary "result/ddps_v3_control:只用基线" \
    "result/ddps_v3_<ts>:带锚点" "result/ddps_v3_control_ffe_only:消融(冻结 CTLE+增益)"
```
> 运行结束后，报告在 `result/ddps_v3_<ts>/report/`：`ddps_v3_report.md`（BER_MLSE 口径、
> 模型指标、逐用例收敛表、云校验、深水复核）+ `ddps_v3_overview.png` + 各用例 `_a/_b` 图
> （收敛轨迹、Tx FFE 抽头、CTLE 频响、driver_gain 轨迹、眼图、频谱、Rx FFE 输出分布），
> 跨实验汇总写到 `report/SUMMARY.md`。
>
> **模型修正与评估协议的选择依据**（CTLE 位置、driver_gain 为何曾是死参数、块长/种子实测）
> 见 [07. DDPS v3 模型修正与评估协议](docs/07_DDPS_v3_Model_Update.md)。
