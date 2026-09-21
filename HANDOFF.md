# HANDOFF — DDPS v6.2.2

## 当前状态（本次 session 结束点）

在线调优演示改用**次优工作点冷启动**（v6.2.2）。上一版从 per-case RMS 标定 gain 出发，gain 已接近各用例最优，多个强信号用例起点即 0 错误（检测限下），看不到在线调优的下降过程；本版改为从一个基线约 1e-5 的次优点出发，让 15 用例全部可见下降。

- **种子（次优工作点，7 维全给定）**：取自训练数据实测点 `Base_IL10x10:683`。Tx FFE 5 抽头 `[-0.0654, -0.2834, 0.5587, -0.0045, 0.0880]`（主抽头 0.5587 派生）、Tx CTLE `gDC=5.73 dB, gDC2=1.45 dB`、`driver_gain=0.2728`（×0.80，`u_gain=-0.0955`）。gain 接近标称、未按用例标定，是次优的主要来源。存 `result/seed_config_bad_1e5.json`。
- **在线测试结果**（15 用例，4194304 符号 × 3 种子 42/43/44）：**15/15 全部下降，0 持平、0 退步**，几何平均 **×186.7**。种子 BER 1.35e-6 ~ 1.83e-3（基线 Base 1.20e-5）；调优后最优 BER 1.19e-7 ~ 7.55e-7（多数逼近检测底）。最深：IL20x20 ×3480（gain ×0.80→×1.11）、Comb_IL20x20_CD15_DGD5 ×2429；高噪声 HighNoise_IL10x10 ×630。gain 维从 ×0.80 被梯度推到各用例最优倍率附近（强信号 ×0.66~×0.75、弱/高损 ×0.86~×1.11）。
- **A-only 消融**（15 用例，同协议）：与主流程逐用例一致，Model B 全程未触发否决（价值仍是"保险"）。
- 旧（好种子）结果已归档：`result/ddps_v6_2_main` → `archive/ddps_v6_2_main_goodseed`、`result/ddps_v6_2_aonly` → `archive/ddps_v6_2_aonly_goodseed`（archive/ gitignored）。

## 本次 session 做的事

1. **选次优种子**：扫描训练数据 `dataset/ddps_v62_dataset_20260920_163244.csv`，选基线约 1e-5、gain 接近标称的实测点，导出 `result/seed_config_bad_1e5.json`。
2. **seed-config 支持 gain 维**：`test_generalization.py` 的 `--seed-config` 新增 `best_u_gain`/`best_gain` 覆盖 gain（此前只覆盖形状/CTLE）。
3. **报告修 seed 参照**：`report_ddps_v6.py` 新增 `--seed-config`，硬用例四联图的"种子"参照画真实次优起点（此前用模块默认名义种子）。
4. **交付件口径刷新**：`make_deliverable_v6.py` 6.0"起点"、6.1 表题、结论、3.3 gain 标定改"参照"、块长研究、复现命令，全部按"次优起点冷启动"口径重写。
5. **全量重跑**（主流程 + A-only，2^22 × 3 种子，4 jobs，实测各 ~7h）→ `result/ddps_v6_2_main`、`result/ddps_v6_2_aonly`。
6. **报告 + 交付件**：`report_ddps_v6.py`（带 `--seed-config`）+ `make_deliverable_v6.py` → `deliverables/DDPS_v6.2_Deliverable.html`。

## 未提交变更（当前 working tree）

- `test_generalization.py`（seed-config 覆盖 gain 维）
- `report_ddps_v6.py`（新增 `--seed-config`）
- `make_deliverable_v6.py`（次优起点叙事）
- `docs/CHANGELOG.md`（v6.2.2 条目）
- `result/seed_config_bad_1e5.json`（新增种子配置）
- `result/ddps_v6_2_main/`、`result/ddps_v6_2_aonly/`（2^22 次优起点结果，含 report/）
- `deliverables/DDPS_v6.2_Deliverable.html`（刷新）

## 已知边界 / 元数据缺口

1. **run_config.json 不记录 seed-config 覆盖**：各 part 的 `per_case_gain` 字段存的是 per-case RMS 标定值，不是本跑实际生效的 ×0.80 种子 gain。真实种子以 `result/seed_config_bad_1e5.json` 与 CHANGELOG 为准。此为次要元数据缺口，未改运行中代码（改会致 15 part 不一致）。
2. **极端插损组合的次优种子不在 1e-5**：IL20x20 / Comb_IL20x20 起点 ~1e-3（gain ×0.80 对高损信道偏小、BER 在悬崖边缘），梯度把 gain 推高（→×1.11）恢复；属预期，交付件诚实描述。
3. 强信号用例调优后仍落在 0~1 错误检测限（1.19e-7 伪计数），改善倍数受限于检测底，用 95% CL 上界表述。
4. 改善主要来自 gain 维（第 7 维），形状/CTLE 微调为次要贡献。

## 物理层（v6.2.2，与 v6.2 同链路）

PAM4 → 5-tap Tx FFE → DAC(ZOH,ENOB 5.5) → Tx IL(S4P) → +1mV 噪声 → Tx CTLE(gDC,gDC2, peaking) → Driver(gain) → Driver BW(40GHz) → MZM(Vπ=3,bias=2.25,ER=25dB) → 光纤 → PIN → TIA → Rx IL → +1mV 噪声 → Rx CTLE(固定 gDC=6/gDC2=3) → ADC → Rx FFE(22-tap,LMS) → Burg → MLSE(memory=1)。无 VGA，无 RMS 归一化。

- Tx CTLE 为 OIF 2Z3P peaking 拓扑：`gDC` = 高频 peaking gain（直流增益恒 0 dB），`gDC2` = LF shelf gain。优化边界 `gDC∈[0,12] dB, gDC2∈[0,4] dB`。
- **gain**：线性驱动增益，标称 `DRIVER_GAIN_NOMINAL=0.3399`；`u_gain = log10(gain/0.3399)`。次优种子 gain ×0.80。
- Rx DSP：LS 初始化 + 数据辅助 LMS 训练 `train_len=10000`，之后权重冻结；BER 窗口 `[train_len, n_valid)`（排除尾部垃圾符号），0 错误 `1/(2N)` 伪计数。

## 架构（v6.2.2）

- **Model A（方向代理）**：输入 = [7-tap Tx FIR 探针, drive_rms]（8 维波形域）→ log10(BER_MLSE)。WhiteBoxRidge（二阶多项式 + L2 Ridge 闭式解，带解析梯度）。
- **Model B（风险控制）**：输入 = [4 FFE 旁瓣, gDC, gDC2, drive_rms]（7 维参数域）→ log10(BER_MLSE) 保守上包络。gain 经 drive_rms 进入 B。
- **梯度（7 维链式法则）**：扰动 7 维参数（4 FFE 旁瓣 + gDC + gDC2 + u_gain）→ 重算探针 → 查 A（中心差分）。
- 信任域：形状/CTLE 不变；gain ±0.15 dex 围绕种子。

## 复现命令

```powershell
# 1) 主流程（2^22 × 3 种子，4 进程，从次优起点出发）
.venv\Scripts\python.exe tools/run_parallel_envs.py --model-dir models/ddps_v6_2 --out-dir result/ddps_v6_2_main --v62 --seed-config result/seed_config_bad_1e5.json --n-steps 15 --num-symbols 4194304 --sim-seeds 42,43,44 --jobs 4

# 2) A-only 消融
.venv\Scripts\python.exe tools/run_parallel_envs.py --model-dir models/ddps_v6_2 --out-dir result/ddps_v6_2_aonly --v62 --a-only --seed-config result/seed_config_bad_1e5.json --n-steps 15 --num-symbols 4194304 --sim-seeds 42,43,44 --jobs 4

# 3) 报告 + 交付件
.venv\Scripts\python.exe report_ddps_v6.py --test-dir result/ddps_v6_2_main --model-dir models/ddps_v6_2 --seed-config result/seed_config_bad_1e5.json
.venv\Scripts\python.exe report_ddps_v6.py --test-dir result/ddps_v6_2_aonly --model-dir models/ddps_v6_2 --seed-config result/seed_config_bad_1e5.json
.venv\Scripts\python.exe make_deliverable_v6.py --baseline result/ddps_v6_2_main --a-only result/ddps_v6_2_aonly
```

## 并行内存约束

`num_symbols=2^22` 时每进程峰值内存约 2~4GB；主流程 + A-only 同时 `--jobs 4`（共 8 进程）会互相拖慢（每 env ~135min，吞吐与串行相当），free RAM 实测 10~18GB 健康。换 4 进程单跑每 env ~70min。
