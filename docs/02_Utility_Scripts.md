# 02. 独立分析与诊断工具集

[🔙 返回主页](../README.md)

## optimizers/ 目录

古典优化器（从 sjtu-channel-model 分支恢复，全部 track）。

| 工具 | 用途 |
|------|------|
| `optimizers/bo_optimizer.py` | BayesianOptimizer 类：GP + ARD RBF kernel + Adam 超参调优 + TuRBO 信任域 + LCB acquisition |
| `optimizers/bo_search_il20.py` | IL20x20 环境 6 维贝叶斯寻优种子点（历史，v6.0 三组训练对比用） |
| `optimizers/optimize_tx.py` | Tx FFE 贝叶斯优化统一入口 |
| `optimizers/sa_optimizer.py` | 模拟退火优化器 |
| `optimizers/ga_optimizer.py` | 遗传算法优化器 |
| `optimizers/shc_optimizer.py` | 安全爬山优化器 |
| `optimizers/esc_optimizer.py` | ESC 优化器 |
| `optimizers/safe_gp_optimizer.py` | 安全 GP 优化器 |
| `optimizers/safe_qcd_optimizer.py` | 安全 QCD 优化器 |
| `optimizers/surrogate_shc_optimizer.py` | 代理爬山优化器 |
| `optimizers/two_stage_optimize.py` | 两阶段优化 |
| `optimizers/compare_optimizers.py` | 优化器对比 |

## tools/ 目录

| 工具 | 用途 |
|------|------|
| `tools/validate_local_gradient.py` | 种子点 7 维中心差分 vs Model A 解析梯度：方向命中率、量级相关系数（支持 `--seed-config`） |
| `tools/diagnose_divergence.py` | 预测-实测发散诊断：逐用例 Δ预测 vs Δ实测、相关系数、位移/ρ |
| `tools/verify_trace.py` | trace 记账复核：独立重仿真逐点核对记录值 |
| `tools/scan_per_case_rms.py` | 每用例扫描标定最优发端 RMS（0.06~0.22V，步长 0.005） |
| `tools/scan_env_optimal.py` | 全环境最优参数扫描 |
| `tools/block_length_study.py` | BER 估计精度：块长变化与可分辨性 |
| `tools/calibrate_driver_gain.py` | Driver gain 标定工具 |
| `tools/run_length_replay.py` | 运行长度回放 |
| `tools/merge_test_parts.py` | 测试结果合并 |

## 核心脚本

| 脚本 | 用途 |
|------|------|
| `main.py` | 单点主仿真：PAM4 → 5-tap FFE → DAC → CTLE → MZM → 光纤 → PIN → MLSE |
| `dataset_generator.py` | DDPS 数据集生成：7 维 LHS 邻域采样（含 gain）+ 真实 BER_MLSE 标注（支持 `--base-env`、`--seed-config`） |
| `train_surrogates.py` | A/B 模型训练：WhiteBoxRidge（二阶多项式 + L2 Ridge 闭式解，带解析梯度） |
| `test_generalization.py` | 在线调优泛化测试：15 环境 Stage-2 7 维链式梯度下降（支持 `--a-only`、`--seed-config`） |
| `report_ddps.py` | 可视化报告：收敛三曲线 + gain/rms 轨迹 + 预测散点 + 四联图 |
| `make_deliverable.py` | 交付件生成：自包含 HTML（输出到 `deliverables/`） |
