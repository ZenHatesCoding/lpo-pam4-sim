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

## 📚 文档导航 (Documentation Navigation)

| 文档 | 内容 |
| --- | --- |
| [01. DSP 架构与核心参数详解](docs/01_DSP_Architecture.md) | 收发机模型、多采样率机制、`config.xlsx` 参数物理含义 |
| [02. 独立分析与诊断工具集](docs/02_Utility_Scripts.md) | `scratch/` 下的信道频响查看器、寻参脚本 |
| [03. 调试排坑与经验沉淀](docs/03_Troubleshooting_History.md) | DFE 误差传播、发送端相位失真、FFE 抽头对齐等踩坑记录 |
| [04. DDPS 数据驱动物理代理寻优](docs/04_DDPS_Optimization.md) | Zero-Shot 双层代理寻优架构（Model A/B、Stage 2 约束梯度下降） |
| [05. 微观物理信道模型升级记录](docs/05_Physical_Channel_Upgrade.md) | 抽象高斯噪声 → SJTU 级微观光电物理模型的升级过程 |
| [06. DDPS v2 重做报告](docs/06_DDPS_v2_Rerun.md) | v1 负向优化根因排查与 v2 全链路重做（数据/训练/在线调优/可视化） |
| [LPO MSA 规范核心参数提炼](docs/LPO_MSA_Specification_Summary.md) | 电气/光学/信道参数标准依据（插损、噪声分配等） |

> 早期古典优化器（BO / GA / SA / SHC 等）已归档在 **`sjtu-channel-model` 分支** 的 `archive/`。
> DDPS v1（物理模型修复前）的数据/模型/结果在磁盘上归档于 `archive/20260904_ddps_v1_physical_pre_v2/`
> （按仓库政策不入库，git 历史仍完整保留本分支旧版）。

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

### 3. 全链路代理数据集生成与模型训练（DDPS v2）
```bash
# 生成"环境锚定邻域"数据集（基准环境 320 点密集 + 7 个应力环境各 60 点锚点，
# 覆盖 Stage-2 信任域 FFE ±0.1 / CTLE ±3 dB；单点真实 BER_MLSE 评估 131072 符号）
python dataset_generator.py --base-samples 320 --anchor-samples 60 --num-symbols 131072

# 白盒多项式 Ridge 训练 Model A & B（输出 models/ddps_v2/ + meta.json）
python -c "from train_surrogates import train_v2; import glob;\
f=sorted(glob.glob('dataset/ddps_v2_dataset_*.csv'))[-1]; train_v2(f, 'models/ddps_v2')"
```

### 4. DDPS v2 在线调优泛化测试 + 可视化报告
```bash
# 冻结模型，逐环境（IL/CD/DGD/复合）Stage-2 约束下降；真实 BER_MLSE 只记录不回传
python test_generalization.py --model-dir models/ddps_v2 --out-dir result/ddps_v2_<ts> \
    --num-symbols 131072 --n-steps 30 --cloud-n 16

# 可视化报告：收敛/抽头/CTLE 响应/眼图/频谱/均衡电平 + 中文 summary + 深水复核
python report_ddps_v2.py --test-dir result/ddps_v2_<ts> --model-dir models/ddps_v2 \
    --deep-symbols 262144
```
> 运行结束后，汇总报告在 `result/ddps_v2_<ts>/report/`：`ddps_v2_report.md`（含
> BER_MLSE 口径、模型指标、逐用例收敛表、统计复核）+ `ddps_v2_overview.png` +
> 各用例 `_a/_b` 图（收敛轨迹、Tx FFE 抽头、Tx CTLE 频率响应、Tx FIR 探针、
> 眼图、频谱、Rx FFE 均衡电平）。
