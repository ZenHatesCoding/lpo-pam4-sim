# DDPS v2 任务交接说明

> 给接手的 Agent。先读 [06. DDPS v2 重做报告](docs/06_DDPS_v2_Rerun.md) + `archive/20260904_ddps_v1_physical_pre_v2/README.md`，
> 再动手。重点看「非协商约束」与「v1 踩过的坑（已修，别回退）」。

## 一、一句话现状

DDPS 已完成 **v2 全链路重做**（数据收集 → 训练 → 在线调优泛化测试 → 可视化报告），
8/8 物理应力用例全程真实 BER_MLSE **无负向优化**并显著改善（20dB 插损用例改善约 20×，
复合应力约 13×）。分支 `physical-model`，v1 旧产物归档于 `archive/20260904_ddps_v1_physical_pre_v2/`。

## 二、非协商约束（甲方底线，别碰）

1. **7-tap 发端 FIR 探针是固定约束**（`tx_channel_extract.extract_tx_s21(num_taps=7)`）。
   不要加抽头、不要换"更丰富发端特征"——那等于改题目。
2. **两阶段底线**：Stage 1（离线标定）可崩、可拿真实端到端 BER；Stage 2（在线调优）
   **不能崩、只能拿发端指标**（真实收端 BER 只记录验证、绝不回传方向决策）。
3. **100% 白盒**：训练/推理/梯度手写（numpy 最多）；无 sklearn/scipy.optimize 黑盒。
4. **统一 BER_MLSE 口径**：全链路指标 = MLSE(memory=1, Burg 白化) 判决输出（Gray 映射）。
5. **文档全中文**（README/docs），图内文字可英文。

## 三、v1 踩过的坑（已修，勿回退/勿重犯）

1. **LHS 采样器维度与索引必须一致**：v1 `LatinHypercube(d=9)` 却取 `sp[i,9]` → 首样本
   IndexError → Stage-1 邻域数据从未生成，模型退化为只在全优化域（主抽头恒 1.0）上训练，
   与下降空间（主抽头=1−Σ|旁瓣|≈0.61）错配。v2 已统一参数化 + d=10。
2. **S4P 频率缩放的群时延漂移**：不同目标插损（10/14/20dB）下脉冲峰值位置不同
   （idx 1247 vs 238）。任何"进程级粘滞 argmax"在多环境复用都会在错误符号格取 FIR。
   v2 的 `_peak_idx_for_env` 按信道环境缓存、透传冲激决定对齐。改对齐逻辑前先跑
   `scratch/diag_*.py` 确认。
3. **代理趋平要停**：Model A 在训练域外 |∇|≈1e-4 仍会沿拟合噪声乱走 → 负向优化。
   v2 加了梯度门控 `GRAD_GATE=0.05`（`ddps_optimizer.py`）。
4. **安全裕度标定**：`SAFETY_MARGIN=0.3` 会在真实 BER 仍在改善时过早刹车；0.6 可到真实
   平台区且全程无恶化（实测 IL20）。改裕度请先做单用例 margin 扫描。
5. **模型 pickle 用模块路径**：`train_v2()` 已把类指到 `train_surrogates`；加载用
   `train_surrogates.load_models()`（兼容 v1 `__main__` 旧档）。

## 四、v2 标准流程（复现命令）

```bash
python dataset_generator.py --base-samples 320 --anchor-samples 60 --num-symbols 131072
python -c "from train_surrogates import train_v2; import glob; \
train_v2(sorted(glob.glob('dataset/ddps_v2_dataset_*.csv'))[-1], 'models/ddps_v2')"
python test_generalization.py --model-dir models/ddps_v2 --out-dir result/ddps_v2_<ts> \
    --num-symbols 131072 --n-steps 30 --cloud-n 16
python report_ddps_v2.py --test-dir result/ddps_v2_<ts> --model-dir models/ddps_v2 --deep-symbols 262144
```

方法学对照（可选）：`python run_ddps_v2_control.py --dataset <csv> --model-dir models/ddps_v2_control`。

## 五、当前产物索引

- 数据集：`dataset/ddps_v2_dataset_20260907_190819.csv`
- 模型：`models/ddps_v2/`（model_a.pkl / model_b.pkl / meta.json；meta 含 R²+Spearman 及按环境拆分）
- 泛化测试：`result/ddps_v2_20260907/`（case_summary.csv/.json、trace_*.csv、model_meta_snapshot.json）
- 可视化报告：`result/ddps_v2_20260907/report/`（ddps_v2_report.md、overview png、逐用例 _a/_b png、deep_check.csv）
- 单环境对照：`result/ddps_v2_control/` + `models/ddps_v2_control/`
- v1 诊断证据脚本：`scratch/diag_*.py` / `scratch/diag_*_evidence*.csv`

## 六、已知边界（诚实记录，勿包装成成功）

1. Model A/B 的**绝对标定弱**（欠/过估真实 BER），只用其排序/方向；任何"绝对红线/阈值"
   用法都需要另行校准（跨环境标定不可迁移）。
2. 种子邻域采样云内的"优于种子"点很少（混合锚定模型的 seed 附近基本已是局部平台），
   Stage-2 的增益来自信任域内更大步幅的移动。
3. BER_MLSE 评估随块长有系统漂移（65536/131072/262144 符号给出不同绝对值），
   报告必须固定协议并注明。
