# HANDOFF — DDPS v6.1

## 当前状态（本次 session 结束点）

物理层 v6.1 已完成（Tx CTLE peaking + Rx 固定 CTLE + 符号数拉长），基线 15/15 改善、0 劣化，最优 BER_MLSE 全部 1e-5 量级（1.93e-5 ~ 4.63e-5），几何平均改善 ×81.87。

上一轮交接遗留的「图/表对不上」问题（A1–A10、B1–B2、C1）**已全部修复**，交付件 `deliverables/DDPS_v6.1_Deliverable.html` 已重新生成，6.1 / 6.1b / 6.2 / 6.3 四节「种子 BER、最优 BER、改善倍数、劣化步数」四个量互相对得上。**结论**：A-only 与 A+B 在 15 用例上收敛到同一最优点、A-only 也 0 劣化步 —— Model A 方向已足够好，Model B 是「保险」而非被触发的拦截器。

## 本次 session 做的事（已 commit 的下一步）

1. **新增并行跑外器** `tools/run_parallel_envs.py`：把 `test_generalization` 的 15 环境串行改成多进程分片（每环境一个子进程 + 每进程 `OMP_NUM_THREADS=1`，复用 `tools/merge_test_parts.py` 按 ENV_CASES 顺序合并）。A-only 全程从 ~7.5h 降到 **~50min**。
   - **内存教训（重要）**：`num_symbols=2^21` 时每进程峰值内存 ~2.5-3GB，**14 进程并发会 OOM**（本机 32GB）。默认/推荐 `--jobs 8`（8 进程 ~消耗 17GB，稳）。
   - `tools/merge_test_parts.py` 重构出可复用的 `merge(out_dir, parts)`，`main()` 仍作 CLI 入口。
2. **重跑 A-only（新物理层 v6.1）** → `result/ddps_v6_1_aonly/`（15 用例 × 15 步 × 2^21×3 种子，全部收敛、0 劣化步）。
3. **修 C1（`make_deliverable_v6.py` `_rows_ablation`）**：`_rows_ablation` 增加 `d_ab` 参数，A+B 劣化步改读 `--baseline` 的 trace（不再 hardcode 旧 `ddps_v6_main`）；`main()` 的 `aonly_dir` 默认改指 `ddps_v6_1_aonly`。旧物理层 `result/ddps_v6_aonly` 与 `result/ddps_v6_main` 都是错误数据源，**勿再引用**。
4. 交付件重新生成 + 三节数字 grep 核对通过。
5. **交付件第二版**（用户反馈）：① 6.2 改为 A+B 与 A-only 两套图（各 4 张，共 8 张，`report_ddps_v6.py` 新增 `_is_aonly` 识别）；② 新增 6.0「种子点怎么定的、调优主要改什么」；③ 文案去 AI 味 + 正确性修正（「数据驱动」「已确认的结论」等措辞、55min→5.6h、平均→几何平均、4.9~6.0dB 对齐）。A-only 报告图落在 `result/ddps_v6_1_aonly/report/`。

## 待办（下一步，仅剩收尾）

1. **commit + push**：见下方「未提交变更」。
   - remote 带 token，`git push origin` 返回 exit 1 只是 PowerShell 把 git stderr 当错误，看 `xxxxx..yyyyy physical-model -> physical-model` 那行确认成功。

### 未提交变更（当前 working tree）

- `tools/run_parallel_envs.py`（新增）
- `tools/merge_test_parts.py`（重构出 `merge()`）
- `make_deliverable_v6.py`（C1 修复）
- `deliverables/DDPS_v6.1_Deliverable.html`（重新生成）
- `result/ddps_v6_1_aonly/`（新增 A-only 结果，含 `_parts/` 分片、`case_summary.csv/json`、`trace_*.csv`、`run_config.json`、`model_meta_snapshot.json`）

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
- **A-only（新物理层 v6.1）**：15 用例同样全部收敛、0 劣化步，A-only 与 A+B 最优 BER 逐用例一致（B 未被触发，B 的价值是「保险」）。

## 关键文件

| 文件 | 用途 |
|---|---|
| `train_surrogates.py` | `train_v6()`：A=探针 8 维，B=参数 7 维，WhiteBoxRidge 带 grad() |
| `ddps_optimizer.py` | `_stage2_descent_v6()` / `_stage2_descent_v6_aonly()` |
| `test_generalization.py` | `--v6` / `--a-only`；`run_generalization()`（line 441）串行 ← 用 parallel 跑外器并行 |
| `tools/run_parallel_envs.py` | **新增**：多进程并行跑 15 环境 + 合并（推荐 `--jobs 8`） |
| `tools/merge_test_parts.py` | 分片合并；`merge(out_dir, parts)` 可复用 |
| `main.py` | `run_sim()`（line 13）单点仿真 ← 瓶颈 |
| `rx_dsp.py` | `adaptive_ffe_dfe()` LMS 主循环（line 64）← 纯 Python 单线程瓶颈 |
| `mlse_burg.py` | `burg_ar()` + `viterbi_mlse_pam4()` ← 纯 Python 单线程瓶颈 |
| `channel_imdd.py` | 链路 + Tx/Rx CTLE（apply_ctle peaking）；Rx CTLE 固定 6/3 |
| `dataset_generator.py` | 数据集生成（`--jobs 14` 多进程，OMP=1） |
| `tools/scan_per_case_rms.py` | per-case target_rms 扫描（`--jobs 14`，OMP=1） |
| `report_ddps_v6.py` | 报告 + 图（`_plot_convergence`/`figure_gain_rms` 已补种子点；`_is_aonly` 自动识别 A-only，收敛图例去掉 Model B/红线并标图题） |
| `make_deliverable_v6.py` | 交付件生成；`_rows_ablation`（line 1208）对齐 v6.1 A-only；6.0 种子说明 + 6.2/6.2b 两套图（A+B / A-only） |
| `models/ddps_v6_1/` | v6.1 基线 A/B 模型（当前） |
| `result/ddps_v6_1_main/` | v6.1 基线 15 用例泛化结果（含 `run_config.json` 记录跑法） |
| `result/ddps_v6_1_aonly/` | **A-only 结果（新物理层，本次重跑完成）** |
| `result/ddps_v6_aonly/` | 旧物理层 A-only（**错误数据源，勿再用**） |
| `result/ddps_v6_main/` | 旧物理层 v6 泛化结果（历史） |
| `result/per_case_target_rms.json` | 15 用例各自 target_rms |
| `config.xlsx` | 主配置（由 `create_config.py` 生成） |
| `AGENTS.md` | 硬规矩：交付件只讲现状（资产负债表），不提"之前/修改/现金流" |

## 复现流程（v6.1 基线 + A-only）

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

# 4) 在线调优（2^21 符号；基线，可用并行跑外器）
python test_generalization.py --model-dir models/ddps_v6_1 --out-dir result/ddps_v6_1_main \
    --v6 --n-steps 15 --num-symbols 2097152 --sim-seeds 42,43,44

# 4b) A-only 对比（并行，~50min）
python tools/run_parallel_envs.py --model-dir models/ddps_v6_1 \
    --out-dir result/ddps_v6_1_aonly --a-only --n-steps 15 \
    --num-symbols 2097152 --sim-seeds 42,43,44 --jobs 8

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
4. 数据集/RMS 扫描强制 OMP=1；在线测试用 `tools/run_parallel_envs.py` 并行（OMP=1 每进程）。
5. Model A 绝对标定弱（只用方向），步长由各维箱宽决定。
6. **并行内存约束**：`--jobs 14` 会 OOM（每进程 ~2.5-3GB），推荐 `--jobs 8`。