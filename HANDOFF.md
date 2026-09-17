# HANDOFF — DDPS v6.1

## 当前状态

DDPS v6.1 完成物理层重做：Tx CTLE 改为 peaking 拓扑、新增 Rx 固定 CTLE、符号数拉长（数据集 2^20 / 在线测试 2^21）。基线训练 15/15 改善、0 劣化，最优 BER_MLSE 全部进入 1e-5 量级（1.93e-5 ~ 4.63e-5）。交付件 `deliverables/DDPS_v6.1_Deliverable.html` 完成。

## 物理层（v6.1）

PAM4 → 5-tap Tx FFE → DAC(ZOH,ENOB 5.5) → Tx IL(S4P) → +1mV 噪声 → Tx CTLE(gDC,gDC2, peaking) → Driver(gain) → Driver BW(40GHz) → MZM(Vπ=3,bias=2.25,ER=25dB) → 光纤 → PIN → TIA → Rx IL → +1mV 噪声 → Rx CTLE(固定 gDC=6/gDC2=3) → ADC → Rx FFE(22-tap,LMS) → Burg → MLSE(memory=1)。无 VGA，无 RMS 归一化。

- Tx CTLE 为 OIF 2Z3P peaking 拓扑：`gDC` = 高频 peaking gain（直流增益恒 0 dB），`gDC2` = LF shelf gain。零极点比 `fz=2.862/fp1=1.884/fp2=1/flf=40`。优化边界 `gDC∈[0,12] dB, gDC2∈[0,4] dB`，种子 `gDC=6, gDC2=2`。
- Rx CTLE 与 Tx 同一拓扑但参数固定（`gDC=6, gDC2=3`），不参与寻优，位于 Rx 电插损之后、ADC 之前。

## 架构（v6.1）

- **Model A（方向代理）**：输入 = [7-tap Tx FIR 探针, drive_rms]（8 维波形域）→ log10(BER_MLSE) 条件均值。WhiteBoxRidge（二阶多项式 + L2 Ridge 闭式解，带解析梯度）。在线调优拿不到收端 BER，只能拿发端探针，A 建立探针→BER 方向映射。
- **Model B（风险控制）**：输入 = [4 FFE 旁瓣, gDC, gDC2, drive_rms]（7 维参数域）→ log10(BER_MLSE) 保守上包络。WhiteBoxRidge。按变差百分比拒绝候选，理想情况不触发。
- **A/B 输入空间不同**（波形域 vs 参数域），误差来源相互独立。
- **梯度**：通过 A 的链式法则——扰动 6 维参数 → 重算探针（含 CTLE 写入 config！）→ 查 A → 得 ΔBER（6 维中心差分，eps=0.01）。每步 7 次评估。
- **gain**：不在 A/B 输入里，per-case target_rms 物理驱动（每用例单独扫描标定）。
- **安全红线**：红线 = 当前最优点 B 预测 × 1.25（随最优点下移，不用种子点 B 预测）。B 单调下降时红线永不触发；B 突然变差时才挡住。

## 基线训练结果（15 用例，2097152 符号 × 3 种子 42/43/44）

- 15/15 改善，0 劣化（平均改善几何均值 ×81.87）
- 最优 BER_MLSE 全部进入 1e-5 量级：最好 1.93e-5（CD28ps），最差 4.63e-5（Comb_IL20x20_CD15_DGD5）
- Model A Spearman=0.911，Model B Spearman=0.910
- gDC 收敛到 ~5.0-6.0（种子 6.0 附近，peaking 保持），gDC2 收敛到 0~1.7
- 最重损用例改善：IL20x20 2.66e-4 → 4.61e-5（×5.77）；Comb_IL20x20 3.15e-4 → 4.63e-5（×6.79）
- 对比旧物理层（v6）：IL20x20 1.52e-3 → 4.61e-5（改善 ~33 倍）；Comb_IL20x20 7.52e-3 → 4.63e-5（~162 倍）

## 三组训练对比实验

同一套 v6 架构，唯一变量是训练环境与种子点：

| 组 | 训练环境 | 种子点来源 | 种子 gDC2 | 平均改善 | 正向 | 劣化步 | 总步 |
|----|---------|-----------|----------|---------|------|--------|-----|
| A 基线 | Base_IL10x10 | 工程标定 | 0.00 | ×5.16 | 15/15 | 0 | 153 |
| B IL20(BO种子) | IL20x20 | 贝叶斯优化 | -4.95 | ×2.66 | 14/15 | 11 | 84 |
| C IL20(GD种子) | IL20x20 | 梯度下降终点 | -2.66 | ×6.67 | 12/15 | 41 | 216 |

- 组 C 重损环境最优（Comb_IL20x20 ×57.08），但退步最多（41 步劣化）
- 组 B 低损环境早停（gDC2 推到 -5 边界），泛化性下降
- **结论**：低损环境训练 + 工程标定种子的组合泛化性最好

## 关键文件

| 文件 | 用途 |
|---|---|
| `train_surrogates.py` | `train_v6()`：A=探针 8 维，B=参数 7 维，WhiteBoxRidge 带 grad() |
| `ddps_optimizer.py` | `_stage2_descent_v6()`：链式梯度 + B 红线 + gain per-case RMS；`_stage2_descent_v6_aonly()`：A-only |
| `test_generalization.py` | `--v6` / `--a-only` 模式；`--seed-config` 覆盖种子点 |
| `dataset_generator.py` | `--base-env` 指定训练环境；`--seed-config` 覆盖种子点 |
| `report_ddps_v6.py` | 可视化报告：收敛三曲线 + gain/rms + 散点 + 四联图 |
| `make_deliverable_v6.py` | 交付件生成（输出到 `deliverables/DDPS_v6.1_Deliverable.html`） |
| `make_deliverable_compare.py` | 三组训练对比交付件 |
| `optimizers/bo_search_il20.py` | IL20x20 贝叶斯寻优种子点 |
| `optimizers/bo_optimizer.py` | BayesianOptimizer 类（GP+ARD RBF+Adam+TuRBO+LCB） |
| `tools/scan_per_case_rms.py` | per-case target_rms 扫描标定 |
| `tools/validate_local_gradient.py` | 梯度方向验证（支持 `--seed-config`） |
| `tools/diagnose_divergence.py` | 预测-实测发散诊断 |
| `docs/DDPS_Method.md` | v6.1 方法口径 |
| `docs/DDPS_REQUIREMENTS.md` | 全部要求清单 |
| `docs/CHANGELOG.md` | 版本变更记录 |
| `models/ddps_v6_1/` | v6.1 基线训练 A/B 模型（当前） |
| `models/ddps_v6/` | v6 基线训练 A/B 模型（历史） |
| `models/ddps_v6_il20/` | IL20x20 (BO 种子) 训练 A/B 模型 |
| `models/ddps_v6_il20gd/` | IL20x20 (GD 种子) 训练 A/B 模型 |
| `result/ddps_v6_1_main/` | v6.1 基线训练 15 用例泛化结果（当前） |
| `result/ddps_v6_main/` | v6 基线训练 15 用例泛化结果（历史） |
| `result/ddps_v6_aonly/` | A-only 对比结果 |
| `result/ddps_v6_il20_main/` | IL20 (BO 种子) 泛化结果 |
| `result/ddps_v6_il20gd_main/` | IL20 (GD 种子) 泛化结果 |
| `result/per_case_target_rms.json` | 15 用例各自最优 target_rms（v6.1 已重扫） |
| `result/ddps_v6_1_block_length.csv` | v6.1 块长研究数据 |
| `result/il20_bo_seed.json` | BO 寻优 IL20x20 种子点 |
| `result/il20_gd_seed.json` | 梯度下降终点 IL20x20 种子点 |

## 复现流程

### v6.1 基线训练（当前）
```bash
# 1) 数据集（2^20 符号）
python dataset_generator.py --base-samples 2000 --anchor-samples 0 \
    --only-envs Base_IL10x10 --num-symbols 1048576 --sim-seeds 42,43,44 \
    --jobs 14 --core-samples 1200 --v5 --v5-gain-lo 0.40 --v5-gain-hi 0.90

# 2) 训练
python -c "from train_surrogates import train_v6; import glob; \
  train_v6(sorted(glob.glob('dataset/ddps_v4_dataset_*.csv'))[-1], 'models/ddps_v6_1')"

# 3) per-case target_rms
python tools/scan_per_case_rms.py --jobs 14

# 4) 在线调优（2^21 符号）
python test_generalization.py --model-dir models/ddps_v6_1 --out-dir result/ddps_v6_1_main \
    --v6 --n-steps 15 --num-symbols 2097152 --sim-seeds 42,43,44

# 5) 报告 + 交付件
python report_ddps_v6.py --test-dir result/ddps_v6_1_main --model-dir models/ddps_v6_1 \
    --summary-out result/SUMMARY_v6_1.md
python make_deliverable_v6.py --baseline result/ddps_v6_1_main --model-dir models/ddps_v6_1 \
    --out deliverables/DDPS_v6.1_Deliverable.html
```

### IL20x20 训练（组 B，BO 种子）
```bash
# 1) BO 寻优种子点
python optimizers/bo_search_il20.py
# -> result/il20_bo_seed.json (BER=4.29e-4, gDC2=-4.95)

# 2) 数据集（用 BO 种子点邻域采样）
python dataset_generator.py --base-samples 2000 --anchor-samples 0 \
    --only-envs IL20x20 --base-env IL20x20 --seed-config result/il20_bo_seed.json \
    --num-symbols 262144 --sim-seeds 42,43,44 --jobs 12 --core-samples 1200 \
    --v5 --v5-gain-lo 0.90 --v5-gain-hi 1.60 --out-dir dataset_il20

# 3) 训练
python -c "from train_surrogates import train_v6; import glob; \
  train_v6(sorted(glob.glob('dataset_il20/ddps_v4_dataset_*.csv'))[-1], 'models/ddps_v6_il20')"

# 4) 泛化测试（用 BO 种子点做 Stage-2 起点）
python test_generalization.py --model-dir models/ddps_v6_il20 --out-dir result/ddps_v6_il20_main \
    --v6 --n-steps 15 --num-symbols 262144 --sim-seeds 42,43,44 --seed-config result/il20_bo_seed.json

# 5) 对比交付件
python make_deliverable_compare.py
```

## 已知边界

1. 最优 BER_MLSE 达到 1e-5 量级（1.93e-5 ~ 4.63e-5），但尚未突破严格 1e-5；残余差距受限于 5-tap Tx FFE 的均衡能力（架构锁死，不可扩 8-tap）。
2. 块长对 BER 有系统性影响（每翻倍约 −0.3 dex，LMS/MLSE 收敛效应），跨块长绝对 BER 不可比，全流程固定 2^21 × 3 种子。
3. per-case target_rms 是离线标定的，换器件需重跑扫描。
4. 数据集生成与 RMS 扫描强制 OMP_NUM_THREADS=1（防多进程 oversubscribe），单点仿真慢于多线程（约 2-3 倍），但保证并行确定性。
5. Model A 的绝对标定弱（只用于方向），步长由各维箱宽决定。
