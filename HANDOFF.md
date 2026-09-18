# HANDOFF — DDPS v6.1

## 当前状态（本次 session 结束点）

物理层 v6.1 已完成（Tx CTLE peaking + Rx 固定 CTLE + 符号数拉长），基线 15/15 改善、0 劣化，最优 BER_MLSE 全部 1e-5 量级（1.93e-5 ~ 4.63e-5），几何平均改善 ×81.87。

用户本 session 的核心投诉：**交付件里表格说改善很多，但图和表对不起来**。下面逐项列出所有"对不上"的根因与修复状态，这是交接的重点。

---

## ⚠️ 图/表对不上问题全清单（交接重点）

### A. 已修复（已 commit 7d2bcb9）

这些是 stale 数值/文字，模板 `make_deliverable_v6.py` 里逐处核对后修正。**审计方法**：用 grep 在模板和渲染后的 HTML 里搜旧数值（如 `0.48`、`55 min`、`12/15`、`0 / 0 dB`），确认无残留。

| # | 症状（对不上的地方） | 根因 | 修法 | 位置 |
|---|---|---|---|---|
| A1 | 桌面端主框图缺 Rx CTLE（用户直接指出） | 之前只给竖向小框图加了 Rx CTLE，横向主框图漏了 | Rx 链补 Rx CTLE 框（固定 6/3 dB），重算连线 | `make_deliverable_v6.py` d-wide SVG |
| A2 | 图4 种子点写「0 / 0 dB」 | 旧物理层种子 gDC=gDC2=0，新种子 6/2 | 改为 gDC=6 dB, gDC2=2 dB（横向+竖向两处） | 图4 两版 SVG |
| A3 | 图4 数据集符号数写 2097152 | 数据集实际 2^20=1048576，在线测试才是 2^21 | 数据集步骤改为 1048576（两处） | 图4 Stage1 |
| A4 | gain 倍率写「强信号 0.48 / 弱信号 1.27」 | 旧物理层实测值，新实测 0.30~1.09 | 改为强信号 0.30 / 弱信号 1.0（4 处） | 正文 + 图7 caption + 结论 |
| A5 | 块长漂移写「−0.15~−0.25 dex」 | 实测 −0.287~−0.332（≈−0.3） | 改为 ≈−0.3 dex | 第 8 节边界表 |
| A6 | 耗时写「RMS ≈10min / 数据集 ≈55min」 | 实测 RMS≈20min(1198s)、数据集≈5.6h(OMP=1) | 改为 20min / 5.6h（两处） | 4.3 复杂度表 + 第8节 |
| A7 | 「12/15 CTLE 激活 / 梯度 1/10」 | 旧物理层结论；新物理层 gDC 微调、gDC2 收敛 0~1.7 | 改为「gDC 种子 6dB 已近最优，仅 5~6dB 微调、gDC2 收敛 0~1.7」 | 第8节 |
| A8 | 训练 α 只写「1.0」 | 实际 A=1.0 / B=0.5（train_v6） | 改为 α_A=1.0 / α_B=0.5（两处） | 图4 |
| A9 | 终止位移写「1e-4」 | 代码是 1e-6 | 改为 1e-6（横向+竖向两处） | 图4 Stage2 |
| A10 | 平均改善 ×417（算术平均） | 被 8 个 ×820+ 的大改善拉高；报告用的是几何均值 | 改为几何均值 ×81.87（`imp_geo`，与报告一致） | `make_deliverable_v6.py` headline/KPI/结论 |

### B. 已修复（working tree 未提交）

这是本 session 最核心的"表格说改善多、图里看不到"问题。

| # | 症状 | 根因 | 修法 | 位置 |
|---|---|---|---|---|
| B1 | 6.2 收敛图（图6）曲线全程贴在 2e-5，种子线画在 1.6e-2，中间空着——表格说改善 ×826，图里看不出任何下降 | **trace 文件漏记种子点**。trace 从梯度第 1 步开始记，而第 1 步的 gain 已被 per-case target_rms 标定（0.4381→0.143）、BER 已掉到 2e-5；真正的种子点（gain=0.4381 未标定、BER 1.6e-2）没进 trace | 绘图时把种子点 prepend 成 step -1 | `report_ddps_v6.py` `_plot_convergence`（约 line 70） |
| B2 | 图7 gain 轨迹看不到「种子 gain 1.0 → 标定后 0.325」的跳跃 | 同上，trace 无种子点 | gain_ratio prepend 1.0、drive_rms 反算 rms_ref（=target/gr0） | `report_ddps_v6.py` `figure_gain_rms`（约 line 146） |

**B 的深层口径**（务必让新 session 知道）：改善 ×826 里约 ×800 来自 gain 标定（种子 gain=0.4381 未标定 → per-case RMS 标定到 0.14~0.31），真正的 FFE/CTLE 梯度只贡献约 ×1.06（2e-5→1.9e-5）。这不是 bug，是设计（gain 由 per-case RMS 物理驱动），但之前图里没体现这一步，所以"表图对不上"。几何均值 ×81.87 已计入。

**B 已重新生成的产物**：`result/ddps_v6_1_main/report/*.png`（convergence/gain_rms/case_hard 三张）+ `deliverables/DDPS_v6.1_Deliverable.html`。图6 现在能看到 1.6e-2 → 2e-5 → 1.9e-5 的完整下降。

### C. 未修复（待办，需要重跑数据）

| # | 症状 | 根因 | 修法 | 位置 |
|---|---|---|---|---|
| C1 | 6.1b「A-only vs A+B」表对不起来：种子 BER 是新 v6.1（1.6e-2），但 A-only 列读旧物理层，A+B「劣化步」算成 15，与 6.3（实际 0 步劣化）直接矛盾 | 本次 v6.1 没跑 A-only，`_rows_ablation` 数据源错配：A-only 读旧 `result/ddps_v6_aonly`；A+B 劣化步 hardcode 去读旧 `ddps_v6_main` 的 trace（line 1227） | ①重跑新物理层 A-only → `result/ddps_v6_1_aonly`；②改 `_rows_ablation`：A-only 目录用 `ddps_v6_1_aonly`，`worse_ab` 读 `a.baseline`（=ddps_v6_1_main）的 trace；③同步改 main() 里 `aonly_dir` 默认（line 1292 现指向 ddps_v6_aonly） | `make_deliverable_v6.py` `_rows_ablation`（line 1208-1241） |

---

## 性能瓶颈分析（重跑 A-only 前先磨刀）

**结论：仿真慢不是点数多，是 (a) LMS FFE + MLSE Viterbi 纯 Python 单线程逐样本循环，(b) test_generalization 串行跑 15 环境。并行空间巨大。**

- CPU：i7-12700，12 物理核 / 20 逻辑线程，32GB RAM。
- `run_sim`（`main.py:13`）三大耗时点：
  - `adaptive_ffe_dfe`（`rx_dsp.py:64`）`for n in range(N_sym)`：2^21 次纯 Python 循环（切片 + np.dot + 判决 + LMS 更新），**单线程，OMP/BLAS 无效**。
  - `viterbi_mlse_pam4`（`mlse_burg.py`）`for n in range(N)`：2^21 次纯 Python 循环（trellis 前向/后向），**单线程**。
  - `apply_channel`（`channel_imdd.py`）卷积/lfilter：BLAS 绑定，OMP 有效（这是 OMP=1 让 2^20 从 20s→46s 的唯一来源，次要）。
- 实测：2^20 run_sim 多线程 ≈20s、OMP=1 ≈46.3s；在线单 eval（2^21 × 3 种子）≈120s。A+B 全程 219 步 ≈7.5h 是 **15 环境串行**造成的。
- 线程设置现状：`dataset_generator.py`、`tools/scan_per_case_rms.py`、`tools/scan_env_optimal.py` 文件头强制 OMP/OPENBLAS/MKL/NUMEXPR=1（防 oversubscribe）。**`test_generalization.py` 不设 OMP 且串行**。
- 正确并行策略：**多进程、每进程 OMP=1（或 2）**。LMS/MLSE 是单线程 Python，进程间天然并行；OMP 只救 apply_channel 小块。CPU 20 线程 → 12~15 并行进程较稳。

---

## 待办（下一步，按顺序）

1. **并行化 test_generalization**（磨刀，别直接串行重跑）：把 `run_generalization`（`test_generalization.py:441`）改成多进程并行 15 环境（`multiprocessing.Pool`，每进程 `OMP_NUM_THREADS=1`），或写 wrapper 用 `--only-envs` 分片 + 多进程。每进程内 15 步仍串行（算法顺序依赖，不能并）。预计 A-only 从 ~7.5h 降到 ~40-60min。
   - 备选：不改 test_generalization，写 `tools/run_parallel_envs.py`，参数化 `--only-envs`，并发跑 15 个单环境进程，最后合并 case_summary。**注意**：合并要复用 test_generalization 现成的 case_summary 生成逻辑（先确认它是否支持单环境/增量输出）。
2. **重跑 A-only（新物理层）**：`python test_generalization.py --model-dir models/ddps_v6_1 --out-dir result/ddps_v6_1_aonly --v6 --a-only --n-steps 15 --num-symbols 2097152 --sim-seeds 42,43,44 --cloud-n 16 --cloud-symbols 65536 --cloud-sim-seeds 42,43`（本次已试跑、已 kill，`result/ddps_v6_1_aonly` 目录已建但空）。
3. **修 `_rows_ablation`**（见 C1）对齐 6.1b。
4. **重新生成交付件**：`python report_ddps_v6.py --test-dir result/ddps_v6_1_main --model-dir models/ddps_v6_1 --summary-out result/SUMMARY_v6_1.md`，然后 `python make_deliverable_v6.py --baseline result/ddps_v6_1_main --model-dir models/ddps_v6_1 --out deliverables/DDPS_v6.1_Deliverable.html`。**最后 grep 核对 6.1 / 6.1b / 6.2 三节数字一致**（种子 BER、最优 BER、改善倍数、劣化步数四个量互相对得上）。
5. **commit + push**。当前 working tree 未提交：`report_ddps_v6.py`（B1/B2 种子点 prepend）、`deliverables/DDPS_v6.1_Deliverable.html`、`result/ddps_v6_1_main/report/*.png`（3 张）、`HANDOFF.md`。分支 `physical-model`，remote 带 token（`git push origin` 返回 exit 1 只是 PowerShell 把 git stderr 当错误，实际成功，看 `xxxxx..yyyyy physical-model -> physical-model` 那行）。

---

## 物理层（v6.1）

PAM4 → 5-tap Tx FFE → DAC(ZOH,ENOB 5.5) → Tx IL(S4P) → +1mV 噪声 → Tx CTLE(gDC,gDC2, peaking) → Driver(gain) → Driver BW(40GHz) → MZM(Vπ=3,bias=2.25,ER=25dB) → 光纤 → PIN → TIA → Rx IL → +1mV 噪声 → Rx CTLE(固定 gDC=6/gDC2=3) → ADC → Rx FFE(22-tap,LMS) → Burg → MLSE(memory=1)。无 VGA，无 RMS 归一化。

- Tx CTLE 为 OIF 2Z3P peaking 拓扑：`gDC` = 高频 peaking gain（直流增益恒 0 dB），`gDC2` = LF shelf gain。零极点比 `fz=2.862/fp1=1.884/fp2=1/flf=40`。优化边界 `gDC∈[0,12] dB, gDC2∈[0,4] dB`，种子 `gDC=6, gDC2=2`。
- Rx CTLE 与 Tx 同一拓扑但参数固定（`gDC=6, gDC2=3`），不参与寻优，位于 Rx 电插损之后、ADC 之前。

## 架构（v6.1）

- **Model A（方向代理）**：输入 = [7-tap Tx FIR 探针, drive_rms]（8 维波形域）→ log10(BER_MLSE)。WhiteBoxRidge（二阶多项式 + L2 Ridge 闭式解，带解析梯度）。
- **Model B（风险控制）**：输入 = [4 FFE 旁瓣, gDC, gDC2, drive_rms]（7 维参数域）→ log10(BER_MLSE) 保守上包络。
- **梯度**：链式法则——扰动 6 维参数 → 重算探针 → 查 A → ΔBER（6 维中心差分 eps=0.01，每步 7 次评估）。
- **gain**：不在 A/B 输入里，per-case target_rms 物理驱动（每用例单独扫描标定）。
- **安全红线**：当前最优点 B 预测 × 1.25（随最优点下移）。

## 基线训练结果（15 用例，2097152 符号 × 3 种子 42/43/44）

- 15/15 改善，0 劣化；几何平均改善 ×81.87
- 最优 BER_MLSE：最好 1.93e-5（CD28ps），最差 4.63e-5（Comb_IL20x20_CD15_DGD5）
- Model A Spearman=0.911，Model B Spearman=0.910
- gDC 收敛 ~5.0-6.0（种子 6.0），gDC2 收敛 0~1.7
- 最重损：IL20x20 2.66e-4→4.61e-5（×5.77）；Comb_IL20x20 3.15e-4→4.63e-5（×6.79）

## 关键文件

| 文件 | 用途 |
|---|---|
| `train_surrogates.py` | `train_v6()`：A=探针 8 维，B=参数 7 维，WhiteBoxRidge 带 grad() |
| `ddps_optimizer.py` | `_stage2_descent_v6()` / `_stage2_descent_v6_aonly()` |
| `test_generalization.py` | `--v6` / `--a-only`；`run_generalization()`（line 441）串行 ← 待并行化 |
| `main.py` | `run_sim()`（line 13）单点仿真 ← 瓶颈 |
| `rx_dsp.py` | `adaptive_ffe_dfe()` LMS 主循环（line 64）← 纯 Python 单线程瓶颈 |
| `mlse_burg.py` | `burg_ar()` + `viterbi_mlse_pam4()` ← 纯 Python 单线程瓶颈 |
| `channel_imdd.py` | 链路 + Tx/Rx CTLE（apply_ctle peaking）；Rx CTLE 固定 6/3 |
| `dataset_generator.py` | 数据集生成（`--jobs 14` 多进程，OMP=1） |
| `tools/scan_per_case_rms.py` | per-case target_rms 扫描（`--jobs 14`，OMP=1） |
| `report_ddps_v6.py` | 报告 + 图（`_plot_convergence`/`figure_gain_rms` 已补种子点） |
| `make_deliverable_v6.py` | 交付件生成；`_rows_ablation`（line 1208）← 待修 A-only 数据源 |
| `models/ddps_v6_1/` | v6.1 基线 A/B 模型（当前） |
| `result/ddps_v6_1_main/` | v6.1 基线 15 用例泛化结果（含 `run_config.json` 记录跑法） |
| `result/ddps_v6_1_aonly/` | A-only 结果（**空，待重跑**） |
| `result/ddps_v6_aonly/` | 旧物理层 A-only（**错误数据源，勿再用**） |
| `result/ddps_v6_main/` | 旧物理层 v6 泛化结果（历史） |
| `result/per_case_target_rms.json` | 15 用例各自 target_rms |
| `config.xlsx` | 主配置（由 `create_config.py` 生成） |
| `AGENTS.md` | 硬规矩：交付件只讲现状（资产负债表），不提"之前/修改/现金流" |

## 复现流程（v6.1 基线）

```bash
# 1) 数据集（2^20 符号，多进程 OMP=1）
python dataset_generator.py --base-samples 2000 --anchor-samples 0 \
    --only-envs Base_IL10x10 --num-symbols 1048576 --sim-seeds 42,43,44 \
    --jobs 14 --core-samples 1200 --v5 --v5-gain-lo 0.40 --v5-gain-hi 0.90

# 2) 训练
python -c "from train_surrogates import train_v6; import glob; \
  train_v6(sorted(glob.glob('dataset/ddps_v4_dataset_*.csv'))[-1], 'models/ddps_v6_1')"

# 3) per-case target_rms
python tools/scan_per_case_rms.py --jobs 14

# 4) 在线调优（2^21 符号；串行，待改并行）
python test_generalization.py --model-dir models/ddps_v6_1 --out-dir result/ddps_v6_1_main \
    --v6 --n-steps 15 --num-symbols 2097152 --sim-seeds 42,43,44

# 5) 报告 + 交付件
python report_ddps_v6.py --test-dir result/ddps_v6_1_main --model-dir models/ddps_v6_1 \
    --summary-out result/SUMMARY_v6_1.md
python make_deliverable_v6.py --baseline result/ddps_v6_1_main --model-dir models/ddps_v6_1 \
    --out deliverables/DDPS_v6.1_Deliverable.html
```

## 已知边界

1. 最优 BER_MLSE 达到 1e-5 量级（1.93e-5 ~ 4.63e-5），尚未突破严格 1e-5；受限于 5-tap Tx FFE（架构锁死，**不可扩 8-tap，用户明令禁止**）。
2. 块长对 BER 有系统性影响（每翻倍约 −0.3 dex，LMS/MLSE 收敛效应），跨块长绝对 BER 不可比，全流程固定 2^21 × 3 种子。
3. per-case target_rms 离线标定，换器件需重扫（≈20min）。
4. 数据集/RMS 扫描强制 OMP=1；test_generalization 目前不设 OMP 且串行（见"待办"）。
5. Model A 绝对标定弱（只用方向），步长由各维箱宽决定。
