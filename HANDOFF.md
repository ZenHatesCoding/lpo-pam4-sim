# HANDOFF — DDPS v6.2

## 当前状态（本次 session 结束点）

物理层 v6.2 已完成并归档：**gain 从"锁定 per-case target_rms"改为第 7 个搜索维**，初值由每个 case 单独扫描最优 RMS 解析得到，之后放开走 7 维链式梯度继续优化。

- 在线测试（15 用例，2097152 符号 × 3 种子 42/43/44）：**14/15 用例相对起点改善、1 用例持平、0 用例退步**；几何平均改善 **×1.09**（最高 ×1.50，Comb_IL20x20_CD15_DGD5）。
- 最优 BER_MLSE 全部进入 1e-5 量级（1.94e-5 ~ 4.66e-5，起点已含 gain 标定）。
- Model A Spearman=0.832（R²=0.666）；Model B Spearman=0.835（R²=0.702，rho=1.752）。
- A-only 消融与主流程基本一致（Model B 全程未触发拦截，价值是「保险」而非被依赖的拦截）。
- 交付件 `deliverables/DDPS_v6.2_Deliverable.html` 已生成，四节「种子 BER / 最优 BER / 改善倍数 / 劣化步数」四张量互相对得上。

## 本次 session 做的事

1. **gain 纳入梯度**：`x = [4 FFE 旁瓣, gDC, gDC2, u_gain]`（7 维），`u_gain = log10(g / DRIVER_GAIN_NOMINAL)`；gain 初值来自 `result/per_case_target_rms.json` 的 per-case 扫描最优 gain，之后在 ±0.15 dex 信任域内参与 Model A 链式梯度（gain 维扰动 u_gain → 重算 probe，只有 drive_rms 变）。
2. **标称 gain 重标定**：`DRIVER_GAIN_NOMINAL` 0.4381 → **0.3399**（按 peaking 链 `rms_at_unity=0.6763` 重标：`g0 = 0.617×0.3726 / 0.6763`）。旧值 0.4381 是 v4 无 peaking 链的残留常量，连带修正了 per-case RMS 扫描的 GAIN_MIN 钳位。
3. **训练数据重做（关键）**：gain 作为独立采样维，采样带取**宽口径 ×0.20~×1.26（u ∈ [-0.70, +0.10]）**，覆盖全部 15 用例 per-case 最优 gain（×0.30~×0.91）及其 ±0.15 dex 在线信任域。**教训**：若采样带只围绕基线最优 gain（±0.25），训练数据覆盖不到高损用例（×0.88）的操作点，Model A 在 drive_rms 轴上外推、跨环境给错 gain/CTLE 方向 → IL20x20 退步。块长 2^20（1048576）符号 × 3 种子，2001 行，12 进程并行（~5.5h）。
4. **并行化**：数据集用 `--jobs 12`（每进程 OMP=1，2^20 时每进程 WS ~1GB，稳）；在线 15 环境用 `tools/run_parallel_envs.py --v62 --jobs 8`。
5. **重训 + 全量重跑**：`models/ddps_v6_2`；`result/ddps_v6_2_main`（15 用例）；`result/ddps_v6_2_aonly`（消融）。
6. **报告 + 交付件**：`report_ddps_v6.py`（v6.2 gain 图叠加种子 gain_ratio；两套图）+ `make_deliverable_v6.py`（7 维、gain 纳入梯度、"起点=形状种子+per-case gain 初值"新口径、6.0/6.2/6.2b 节、POS_SUMMARY 占位符）。

## 待办（下一步，仅剩收尾）

1. **commit + push**（见下方「未提交变更」）。remote 带 token，`git push origin` 返回 exit 1 只是 PowerShell 把 git stderr 当错误，看 `xxxxx..yyyyy physical-model -> physical-model` 那行确认成功。

## 未提交变更（当前 working tree）

- `channel_imdd.py`（DRIVER_GAIN_NOMINAL 重标定 0.3399）
- `dataset_generator.py`（`--v62`：gain 独立采样维 + 宽采样带 + 种子行锚定 per-case 最优 gain）
- `ddps_optimizer.py`（v6.2 7 维链式梯度 `_grad_a_chain7` / `_stage2_descent_v62(_aonly)`、`_bounds7`、GAIN_TRUST/GAIN_SAMPLE_* 常量）
- `train_surrogates.py`（`train_v6` 支持 `gain_mode='gradient_with_rms_init'` 与 pipeline tag）
- `test_generalization.py`（`--v62` / `run_case_v62(_aonly)` / `run_generalization` 支持 v62）
- `tools/run_parallel_envs.py`（`--v62` flag + v62-Aonly dispatch）
- `report_ddps_v6.py`（v6.2 分支：gain 图、收敛图题/文案）
- `make_deliverable_v6.py`（v6.2 模板重写 + POS_SUMMARY 占位符 + 宽采样带/2^20 文案）
- `docs/CHANGELOG.md`（v6.2 节，结果已补全）
- `result/per_case_rms_scan.csv` / `result/per_case_target_rms.json`（新标称下重扫）
- `result/ddps_v6_2_block_length.csv`（从 v6.1 拷贝；块长研究为协议级，版本无关）
- `result/ddps_v6_2_main/`、`result/ddps_v6_2_aonly/`、`models/ddps_v6_2/`、`dataset/ddps_v62_dataset_20260919_004651.csv`
- `deliverables/DDPS_v6.2_Deliverable.html`

## 物理层（v6.2，与 v6.1 同链路）

PAM4 → 5-tap Tx FFE → DAC(ZOH,ENOB 5.5) → Tx IL(S4P) → +1mV 噪声 → Tx CTLE(gDC,gDC2, peaking) → Driver(gain) → Driver BW(40GHz) → MZM(Vπ=3,bias=2.25,ER=25dB) → 光纤 → PIN → TIA → Rx IL → +1mV 噪声 → Rx CTLE(固定 gDC=6/gDC2=3) → ADC → Rx FFE(22-tap,LMS) → Burg → MLSE(memory=1)。无 VGA，无 RMS 归一化。

- Tx CTLE 为 OIF 2Z3P peaking 拓扑：`gDC` = 高频 peaking gain（直流增益恒 0 dB），`gDC2` = LF shelf gain。零极点比 `fz=2.862/fp1=1.884/fp2=1/flf=40`。优化边界 `gDC∈[0,12] dB, gDC2∈[0,4] dB`，种子 `gDC=6, gDC2=2`。
- **gain**：线性驱动增益，标称 `DRIVER_GAIN_NOMINAL=0.3399`；逐 case 最优 gain 来自 per-case RMS 扫描（强信号环境低、弱信号环境高，比值 ×0.30~×0.91）。

## 架构（v6.2）

- **Model A（方向代理）**：输入 = [7-tap Tx FIR 探针, drive_rms]（8 维波形域）→ log10(BER_MLSE)。WhiteBoxRidge（二阶多项式 + L2 Ridge 闭式解，带解析梯度）。
- **Model B（风险控制）**：输入 = [4 FFE 旁瓣, gDC, gDC2, drive_rms]（7 维参数域）→ log10(BER_MLSE) 保守上包络。gain 经 drive_rms 进入 B（B 输入里不含 u_gain 本身）。
- **梯度（7 维链式法则）**：扰动 6 维 shape 参数 → 重算探针 → 查 A（中心差分 eps=0.01）；扰动 u_gain（eps_u=0.05）→ 重算 drive_rms → 查 A。gain 维只有 drive_rms 变。
- **gain 信任域**：±0.15 dex（围绕 per-case 初值）；FFE ±0.10 / CTLE ±3.0 dB（围绕形状种子，不变）。
- **安全红线**：当前最优点 B 预测 × 1.25（随最优点下移）；本版 B 全程未触发拦截。

## 基线训练 + 泛化结果（15 用例，2097152 符号 × 3 种子 42/43/44）

- 14/15 改善、1 持平、0 退化；几何平均 ×1.09（最高 ×1.50）
- 起点 BER_MLSE（形状种子 + per-case gain 初值）：1.94e-5 ~ 6.97e-5
- 最优 BER_MLSE：1.94e-5 ~ 4.66e-5
- 最难/改善最大：Comb_IL20x20_CD15_DGD5 6.97e-5→4.66e-5（×1.50）；IL20x20 6.28e-5→4.65e-5（×1.35）
- Model A Spearman=0.832 / R²=0.666；Model B Spearman=0.835 / R²=0.702（rho=1.752）
- gDC 收敛 ~5.3-7.1（种子 6.0），gDC2 收敛 0~4.0
- gain（比值）起点 ×0.30~×0.91（per-case 标定）→ 最优 ×0.31~×1.28（高低损环境方向正确：高损提 gain、低损稳 gain）
- **A-only**：与主流程逐用例一致（少数用例 gain 略更激进，如 Comb ×1.52 vs ×1.49），0 退化步 → Model B 是「保险」而非被依赖的拦截器。

## 关键文件

| 文件 | 用途 |
|---|---|
| `train_surrogates.py` | `train_v6()`：A=探针 8 维，B=参数 7 维，WhiteBoxRidge 带 grad() |
| `ddps_optimizer.py` | `_stage2_descent_v62()` / `_stage2_descent_v62_aonly()`；`_grad_a_chain7()`；`_bounds7()` |
| `test_generalization.py` | `--v62` / `--a-only`；`run_case_v62(_aonly)`；`run_generalization(v62=...)` |
| `tools/run_parallel_envs.py` | 多进程并行 15 环境 + 合并（推荐 `--jobs 8`；`--v62` / `--a-only` 组合） |
| `tools/merge_test_parts.py` | 分片合并；`merge(out_dir, parts)` 可复用 |
| `dataset_generator.py` | 数据集生成（`--v62`，gain 宽采样带 ×0.20~×1.26，`--jobs 12`，OMP=1） |
| `tools/scan_per_case_rms.py` | per-case target_rms / gain 扫描（`--jobs 8`，OMP=1） |
| `main.py` | `run_sim()`（line 13）单点仿真 ← 瓶颈 |
| `rx_dsp.py` | `adaptive_ffe_dfe()` LMS 主循环（line 64）← 纯 Python 单线程瓶颈 |
| `mlse_burg.py` | `burg_ar()` + `viterbi_mlse_pam4()` ← 纯 Python 单线程瓶颈 |
| `channel_imdd.py` | 链路 + Tx/Rx CTLE（apply_ctle peaking）；`DRIVER_GAIN_NOMINAL=0.3399` |
| `report_ddps_v6.py` | 报告 + 图（v6.2 gain 图叠加种子 gain 前缀；`_is_aonly` 自动识别） |
| `make_deliverable_v6.py` | 交付件生成（v6.2 7 维口径；`POS_SUMMARY` 占位符；宽采样带文案） |
| `models/ddps_v6_2/` | v6.2 基线 A/B 模型（当前） |
| `result/ddps_v6_2_main/` | v6.2 主流程 15 用例泛化结果（含 `report/`、`run_config.json`） |
| `result/ddps_v6_2_aonly/` | v6.2 A-only 消融结果 |
| `result/ddps_v6_1_main/` · `_aonly/` | v6.1（已归档；gain 锁定版，勿与 v6.2 混淆） |
| `result/per_case_target_rms.json` | 15 用例各自 target_rms / gain（新标称） |
| `config.xlsx` | 主配置（由 `create_config.py` 生成） |
| `AGENTS.md` | 硬规矩：交付件只讲现状（资产负债表），不提"之前/修改/现金流" |

## 复现流程（v6.2）

```bash
# 1) 数据集（gain 独立采样维，宽覆盖 ×0.20~×1.26；2^20 符号，12 进程 OMP=1）
python dataset_generator.py --base-samples 2000 --anchor-samples 0 \
    --only-envs Base_IL10x10 --num-symbols 1048576 --sim-seeds 42,43,44 \
    --jobs 12 --core-samples 1200 --v62

# 2) 训练（gain_mode=gradient_with_rms_init）
python -c "from train_surrogates import train_v6; import glob; \
  train_v6(sorted(glob.glob('dataset/ddps_v62_dataset_*.csv'))[-1], 'models/ddps_v6_2', \
           pipeline_tag='ddps_v6_2', gain_mode='gradient_with_rms_init')"

# 3) per-case target_rms（一次离线标定，产出 gain 初值）
python tools/scan_per_case_rms.py --jobs 8

# 4) 在线调优（2^21；并行跑外器 --v62）
python tools/run_parallel_envs.py --model-dir models/ddps_v6_2 --out-dir result/ddps_v6_2_main \
    --v62 --n-steps 15 --num-symbols 2097152 --sim-seeds 42,43,44 \
    --cloud-n 16 --cloud-symbols 65536 --cloud-sim-seeds 42,43 --jobs 8

# 4b) A-only 消融
python tools/run_parallel_envs.py --model-dir models/ddps_v6_2 --out-dir result/ddps_v6_2_aonly \
    --v62 --a-only --n-steps 15 --num-symbols 2097152 --sim-seeds 42,43,44 \
    --cloud-n 16 --cloud-symbols 65536 --cloud-sim-seeds 42,43 --jobs 8

# 5) 报告 + 交付件
python report_ddps_v6.py --test-dir result/ddps_v6_2_main --model-dir models/ddps_v6_2
python report_ddps_v6.py --test-dir result/ddps_v6_2_aonly --model-dir models/ddps_v6_2
python make_deliverable_v6.py
```

## 已知边界

1. 最优 BER_MLSE 达到 1e-5 量级（1.94e-5 ~ 4.66e-5），尚未突破严格 1e-5；受限于 5-tap Tx FFE（架构锁死，**不可扩 8-tap，用户明令禁止**）。
2. 改善全部来自"起点已含 gain 标定"之后的 7 维梯度微调，因此改善倍数为 ×1.09（小步），不是 v6.1 那种含 gain 标定的 ×81.87 大步口径——两者不可比。
3. gain 梯度跨环境可靠性依赖训练数据覆盖全用例 gain 操作区间（×0.20~×1.26）；若将来缩小采样带，需先验证高损用例（IL20x20 / Comb）不退步。
4. 块长对 BER 有系统性影响（每翻倍约 −0.3 dex，LMS/MLSE 收敛效应），跨块长绝对 BER 不可比，全流程固定 2^21 × 3 种子。
5. per-case target_rms / gain 离线标定，换器件需重扫（≈20min）。
6. 数据集/RMS 扫描强制 OMP=1；在线测试用 `tools/run_parallel_envs.py` 并行（每进程 OMP=1）。
7. **并行内存约束**：`num_symbols=2^21` 时每进程峰值内存 ~2.5-3GB，`--jobs 14` 会 OOM（本机 32GB）；在线测试推荐 `--jobs 8`。