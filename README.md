# LPO PAM4 (112G/224G/448G) DSP 基线仿真平台

本项目是一个基于纯 Python (Numpy/Scipy) 白盒构建的 **Linear Pluggable Optics (LPO)** 系统级仿真器，主要用于跨多代速率（112G/224G/448G）下的高速信道纯线性均衡算法研究与评估。

> [!NOTE]
> 本项目的核心理念是 **"白盒化" (White-Box)** 与 **"符合物理直觉"**。
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

> [!TIP]
> 📊 **结果与图件索引见 [`result/SUMMARY.md`](result/SUMMARY.md)**

## 📚 文档导航 (Documentation Navigation)

| 文档 | 内容 |
| --- | --- |
| [📄 **DDPS v6.2 交付说明（自包含 HTML）**](deliverables/DDPS_v6.2_Deliverable.html) | 链路架构、A/B 双代理、7 维链式梯度（含 gain）、安全红线、次优起点冷启动、15 用例结果（几何平均 ×186.7）；可折叠大纲 + A+B/A-only 图切换 |
| [历史交付件与历史实验](archive/) | v2~v6.1 各版本交付件 HTML、训练环境对比实验、历史结果/模型/数据集（本地归档，不入远端） |
| [01. DSP 架构与核心参数详解](docs/01_DSP_Architecture.md) | 收发机模型、多采样率机制、`config.xlsx` 参数物理含义 |
| [02. 独立分析与诊断工具集](docs/02_Utility_Scripts.md) | optimizers/ + tools/ 目录 + 核心脚本 |
| [DDPS 方法](docs/DDPS_Method.md) | A=探针→BER 方向代理 + B=参数→BER 风险控制、7 维链式梯度（含 gain）、安全红线、次优起点 |
| [DDPS 要求清单](docs/DDPS_REQUIREMENTS.md) | 架构、安全红线、对比实验、交付件的全部要求 |
| [版本变更记录](docs/CHANGELOG.md) | 每个版本的核心变化（v1→v6.2.2） |
| [LPO MSA 规范核心参数提炼](docs/LPO_MSA_Specification_Summary.md) | 电气/光学/信道参数标准依据 |
| [分支关系与版本导览](BRANCHES.md) | 仓库各分支的关系与差异 |

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

### 3. 数据集生成与模型训练
```bash
# 只用基线环境（Base_IL10x10）采样 2000 点，7 维 LHS（4 FFE 旁瓣 + gDC + gDC2 + u_gain）
python dataset_generator.py --base-samples 2000 --only-envs Base_IL10x10 \
    --num-symbols 1048576 --sim-seeds 42,43,44 --jobs 12 --core-samples 1200 --v62

# 训练 A（探针 8 维→BER）+ B（参数 7 维→BER），WhiteBoxRidge 带解析梯度（gain 纳入梯度）
python -c "from train_surrogates import train_v6; import glob; \
  train_v6(sorted(glob.glob('dataset/ddps_v62_dataset_*.csv'))[-1], 'models/ddps_v6_2', \
           pipeline_tag='ddps_v6_2', gain_mode='gradient_with_rms_init')"
```

### 4. per-case target_rms 扫描 + 在线调优泛化测试
```bash
# 每用例扫描标定最优发端 RMS（gain 维标定参照）
python tools/scan_per_case_rms.py --jobs 8

# 冻结模型，15 环境 Stage-2 7 维链式梯度下降 + B 风险控制；从次优起点出发
python test_generalization.py --model-dir models/ddps_v6_2 --out-dir result/ddps_v6_2_main \
    --v62 --seed-config result/seed_config_bad_1e5.json --n-steps 15 --num-symbols 4194304 --sim-seeds 42,43,44

# A-only 对比实验（只用 A 梯度，不查 B）
python test_generalization.py --model-dir models/ddps_v6_2 --out-dir result/ddps_v6_2_aonly \
    --v62 --a-only --seed-config result/seed_config_bad_1e5.json --n-steps 15 --num-symbols 4194304 --sim-seeds 42,43,44
```

### 5. 报告与交付件
```bash
# 可视化报告：收敛三曲线 + gain/rms 轨迹 + 预测散点 + 最难用例四联图
python report_ddps_v6.py --test-dir result/ddps_v6_2_main --model-dir models/ddps_v6_2 \
    --seed-config result/seed_config_bad_1e5.json --summary-out result/SUMMARY.md

# 交付件（自包含 HTML）
python make_deliverable_v6.py --baseline result/ddps_v6_2_main --a-only result/ddps_v6_2_aonly
```

### 6. 历史实验（v6.0 时代，结果已归档）
```bash
# IL20x20 训练对比实验（基线 vs BO种子 vs GD种子）与模型方向验证工具
# 结果见 archive/，方法见 docs/CHANGELOG.md（v6.0 三组对比）
python optimizers/bo_search_il20.py
python make_deliverable_compare.py
```
