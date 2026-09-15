# HANDOFF — DDPS v6

## 当前状态

DDPS v6 架构正确，15 用例泛化全部改善，交付件生成中。

## 架构（v6 = 正确分工）

- **Model A（方向代理）**：输入 = [7-tap Tx FIR 探针, drive_rms]（8 维波形域）→ log10(BER_MLSE) 条件均值。WhiteBoxRidge（二阶多项式 + L2 Ridge 闭式解，带解析梯度）。在线调优拿不到收端 BER，只能拿发端探针，A 建立探针→BER 方向映射。
- **Model B（风险控制）**：输入 = [4 FFE 旁瓣, gDC, gDC2, drive_rms]（7 维参数域）→ log10(BER_MLSE) 保守上包络。WhiteBoxRidge。按变差百分比拒绝候选，理想情况不触发。
- **A/B 输入空间不同**（波形域 vs 参数域），误差来源相互独立。
- **梯度**：通过 A 的链式法则——扰动 6 维参数 → 重算探针 → 查 A → 得 ΔBER（6 维中心差分）。
- **gain**：不在 A/B 输入里，per-case target_rms 物理驱动（每用例单独扫描标定）。

## 物理层（v6 = v5 口径）

PAM4 → 5-tap Tx FFE → DAC(ZOH,ENOB 5.5) → Tx IL(S4P) → +1mV 噪声 → CTLE(gDC,gDC2) → Driver(gain) → Driver BW(40GHz) → MZM(Vπ=3,bias=2.25,ER=25dB) → 光纤 → PIN → TIA → Rx IL → ADC → Rx FFE(22-tap,LMS) → Burg → MLSE(memory=1)。无 VGA，无 RMS 归一化。

## 结果（15 用例，262144 符号 × 3 种子 42/43/44）

- 15/15 改善，0/15 终点劣于种子
- 平均改善 ×2.03
- 预测-实测正相关 11/15（中位 +0.48）

## 关键文件

| 文件 | 用途 |
|---|---|
| `train_surrogates.py` | `train_v6()`：A=探针 8 维，B=参数 7 维，WhiteBoxRidge 带 grad() |
| `ddps_optimizer.py` | `_stage2_descent_v6()`：链式梯度 + B 拦截 + gain per-case RMS |
| `test_generalization.py` | `--v6` 模式，`run_case_v6()` |
| `make_deliverable_v6.py` | 交付件生成（v3 模板适配 v6 物理层） |
| `report_ddps_v6.py` | 可视化报告 |
| `docs/10_DDPS_v6_Model_Update.md` | v6 方法口径 |
| `models/ddps_v6/` | 训练好的 A/B 模型 + meta.json |
| `result/ddps_v6_main/` | 15 用例泛化结果 + traces |
| `result/per_case_target_rms.json` | 15 用例各自最优 target_rms |

## 复现流程

```
# 1) 数据集
python dataset_generator.py --base-samples 2000 --only-envs Base_IL10x10 --num-symbols 262144 --sim-seeds 42,43,44 --jobs 14 --core-samples 1200 --v5 --v5-gain-lo 0.40 --v5-gain-hi 0.90

# 2) 训练
python -c "from train_surrogates import train_v6; import glob; train_v6(sorted(glob.glob('dataset/ddps_v4_dataset_*.csv'))[-1], 'models/ddps_v6')"

# 3) per-case target_rms
python scratch/scan_per_case_rms.py --jobs 12

# 4) 在线调优
python test_generalization.py --model-dir models/ddps_v6 --out-dir result/ddps_v6_main --v6 --n-steps 15 --num-symbols 262144 --sim-seeds 42,43,44

# 5) 诊断
python tools/diagnose_divergence.py --test-dir result/ddps_v6_main --model-dir models/ddps_v6 --out result/ddps_v6_divergence.csv

# 6) 报告
python report_ddps_v6.py --test-dir result/ddps_v6_main --model-dir models/ddps_v6 --summary "v6:A探针+B参数" --summary-out result/SUMMARY.md

# 7) 交付件
python make_deliverable_v6.py --baseline result/ddps_v6_main --model-dir models/ddps_v6
```

## 已知边界

1. CTLE 组在多数用例未激活（探针对 CTLE 直流增益灵敏度低于 FFE 旁瓣）。后续可调步长或用解析链式雅可比。
2. 恶劣场景绝对 BER 仍在 1e-2 量级。
3. per-case target_rms 是离线标定的，换器件需重跑扫描。

## 归档

- `archive/20260915_ddps_v5_ab_input_merged_wrong/`：v5 版（A/B 输入合并的错误版本，含 make_deliverable_v5.py、DDPS_v5_Deliverable.html、models/ddps_v5、result/ddps_v5_*）

## 待完成

- [x] report_ddps_v6.py 创建
- [ ] make_deliverable_v6.py 适配 + 生成 DDPS_v6_Deliverable.html
- [ ] 提交推送
