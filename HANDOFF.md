# HANDOFF — DDPS v6.2.1

## 当前状态（本次 session 结束点）

物理层 v6.2 的 BER 测量存在**尾缘截断 bug**，已修复并全流程重做（v6.2.1）。修复后链路真实性能远优于此前报告值，且"gain 纳入梯度"在极端插损组合上表现出大幅可测改善。

- **根因与修复**：`adaptive_ffe_dfe` 的 FFE 输入索引 `idx = 2*(n + sync_delay) + ffe_pre` 在 `idx >= len(rx_sps)` 时 `continue`，最后约 `sync_delay + ffe_pre/2`（~114）个符号的均衡输出保持 0（垃圾判决），按固定错误数虚增 BER（表现为"每翻倍块长 −0.3 dex"）。修复：BER 窗口限定在有效稳态输出 `[train_len, n_valid)`，`n_valid = (len(rx_adc) − ffe_pre)//2 − sync_delay`；0 错误用 `1/(2N)` 伪计数。
- **块长研究**（Base_IL10x10 最优工作点，gain ×0.41）：2^18~2^22 × 3 种子全程 **0 错误** → 真实 BER < 2.4e-7（95% CL，2^22 × 3 种子）；gDC=0 与 gDC=6 无差（CTLE 也被 Rx FFE+MLSE 补偿）。
- **数据集重做**：2^20 × 3 种子，2001 行，`log10_ber_mlse ∈ [-6.317, -0.770]`，49% 行落在 0 错误检测限。
- **模型**：Model A Spearman=0.847 / R²=0.673；Model B Spearman=0.842 / R²=0.687（rho=1.752）。
- **在线测试**（15 用例，4194304 符号 × 3 种子 42/43/44）：**8/15 可测改善、0 退步**，几何平均 **×3.40**；极端插损组合 IL20x20 ×105.6、Comb_IL20x20_CD15_DGD5 ×182.8；7 个强信号/弱压力用例起点即 0 错误（×1.0，检测限下，保持不退化）。
- A-only 消融（15 用例，同协议）：与主流程**逐点一致**（含 IL20x20 ×105.6、Comb_IL20x20 ×182.8），Model B 全程未触发拦截。

## 本次 session 做的事

1. **修复 BER 尾缘截断**（`main.py`）：BER 窗口排除尾部 ~114 个垃圾符号 + 0 错误 `1/(2N)` 伪计数；新增 `tools/diagnose_ber_head.py`（错误分布定位）与 `tools/verify_tail_fix.py`。
2. **块长研究重做**（`tools/block_length_study.py` 重写）：支持 `--gain`、输出原始错误数、块长到 2^22；确认最优工作点 2^18~2^22 全 0 错误。
3. **评估协议 2^21 → 2^22**：真实 BER 评估块长 4194304 符号 × 3 种子（强信号用例仍落在 0~1 错误检测限，用 95% CL 上界表述）。
4. **数据集重生成**（`dataset_generator.py --v62`，2^20 × 3 种子，12 进程）。
5. **重训**（`train_v6`，`gain_mode='gradient_with_rms_init'`）→ `models/ddps_v6_2`。
6. **全量重跑**：`result/ddps_v6_2_main`（15 用例，2^22）；`result/ddps_v6_2_aonly`（消融，2^22）。旧 buggy 结果备份在 `result/_buggy_v6_2_main` / `_buggy_v6_2_aonly`。
7. **报告 + 交付件**：`report_ddps_v6.py`（协议行 2^22）+ `make_deliverable_v6.py`（测试协议 2^22、块长表"0 错误→检测限"叙事、数据集范围、结论文案）。

## 待办（下一步，仅剩收尾）

1. **commit + push**（见下方「未提交变更」）。remote 带 token，`git push origin` 返回 exit 1 只是 PowerShell 把 git stderr 当错误，看 `xxxxx..yyyyy physical-model -> physical-model` 那行确认成功。

## 未提交变更（当前 working tree）

- `main.py`（BER 尾缘截断修复 + 0 错误伪计数）
- `tools/diagnose_ber_head.py` / `tools/verify_tail_fix.py`（新增）
- `tools/block_length_study.py`（重写：--gain、原始错误数、2^22）
- `report_ddps_v6.py`（协议行 2097152 → 4194304）
- `make_deliverable_v6.py`（测试协议 2^22、块长表/适用边界/数据集范围/结论文案重写）
- `docs/CHANGELOG.md`（v6.2.1 根因 + 协议 + 重做结果）
- `dataset/ddps_v62_dataset_20260920_163244.csv`（新数据集）
- `models/ddps_v6_2/`（重训）
- `result/ddps_v6_2_main/`（2^22 主结果）、`result/ddps_v6_2_aonly/`（2^22 消融，跑完后）
- `result/ddps_v6_2_block_length.csv`（修正后全 0 错误）

## 物理层（v6.2.1，与 v6.2 同链路）

PAM4 → 5-tap Tx FFE → DAC(ZOH,ENOB 5.5) → Tx IL(S4P) → +1mV 噪声 → Tx CTLE(gDC,gDC2, peaking) → Driver(gain) → Driver BW(40GHz) → MZM(Vπ=3,bias=2.25,ER=25dB) → 光纤 → PIN → TIA → Rx IL → +1mV 噪声 → Rx CTLE(固定 gDC=6/gDC2=3) → ADC → Rx FFE(22-tap,LMS) → Burg → MLSE(memory=1)。无 VGA，无 RMS 归一化。

- Tx CTLE 为 OIF 2Z3P peaking 拓扑：`gDC` = 高频 peaking gain（直流增益恒 0 dB），`gDC2` = LF shelf gain。优化边界 `gDC∈[0,12] dB, gDC2∈[0,4] dB`，种子 `gDC=6, gDC2=2`。
- **gain**：线性驱动增益，标称 `DRIVER_GAIN_NOMINAL=0.3399`；per-case 最优 gain 来自 RMS 扫描（×0.30~×0.91），作为第 7 维初值后放开走梯度。
- Rx DSP：LS 初始化 + 数据辅助 LMS 训练 `train_len=10000`，之后权重冻结；BER 窗口 `[train_len, n_valid)`（头部训练 + 尾部垃圾均排除）。

## 架构（v6.2.1）

- **Model A（方向代理）**：输入 = [7-tap Tx FIR 探针, drive_rms]（8 维波形域）→ log10(BER_MLSE)。WhiteBoxRidge（二阶多项式 + L2 Ridge 闭式解，带解析梯度）。
- **Model B（风险控制）**：输入 = [4 FFE 旁瓣, gDC, gDC2, drive_rms]（7 维参数域）→ log10(BER_MLSE) 保守上包络。gain 经 drive_rms 进入 B。
- **梯度（7 维链式法则）**：扰动 7 维参数（4 FFE 旁瓣 + gDC + gDC2 + u_gain）→ 重算探针 → 查 A（中心差分）。gain 维扰动 u_gain → 只有 drive_rms 变。
- 信任域：形状/CTLE 不变；gain ±0.15 dex 围绕 per-case 初值。

## 复现命令

```powershell
# 1) 数据集（2^20 × 3 种子，12 进程，~6h）
.venv\Scripts\python.exe dataset_generator.py --v62 --base-samples 2000 --only-envs Base_IL10x10 --num-symbols 1048576 --sim-seeds 42,43,44 --jobs 12 --core-samples 1200

# 2) 重训
.venv\Scripts\python.exe -c "from train_surrogates import train_v6; import glob; train_v6(sorted(glob.glob('dataset/ddps_v62_dataset_*.csv'))[-1], 'models/ddps_v6_2', pipeline_tag='ddps_v6_2', gain_mode='gradient_with_rms_init')"

# 3) 主流程（2^22 × 3 种子，4 进程，~4h）
.venv\Scripts\python.exe tools/run_parallel_envs.py --model-dir models/ddps_v6_2 --out-dir result/ddps_v6_2_main --v62 --n-steps 15 --num-symbols 4194304 --sim-seeds 42,43,44 --jobs 4

# 4) A-only 消融
.venv\Scripts\python.exe tools/run_parallel_envs.py --model-dir models/ddps_v6_2 --out-dir result/ddps_v6_2_aonly --v62 --a-only --n-steps 15 --num-symbols 4194304 --sim-seeds 42,43,44 --jobs 4

# 5) 报告 + 交付件
.venv\Scripts\python.exe report_ddps_v6.py --test-dir result/ddps_v6_2_main --model-dir models/ddps_v6_2
.venv\Scripts\python.exe report_ddps_v6.py --test-dir result/ddps_v6_2_aonly --model-dir models/ddps_v6_2
.venv\Scripts\python.exe make_deliverable_v6.py
```

## 已知边界

1. **强信号用例低于测量分辨率**：最优工作点真实 BER < 2.4e-7（2^22 × 3 种子 0 错误），7 个强信号/弱压力用例起点即 0 错误，只能用 95% CL 上界（3/N）表述，不可与有效错误点混用点估计。
2. **改善集中在极端插损组合**：IL20x20、Comb_IL20x20 的 per-case RMS 起点 gain（×0.88/×0.91）偏小，BER 位于悬崖边缘；梯度把 gain 推到 ×1.0~1.06 后 BER 从 1e-5 降到检测限附近。中等压力（HighNoise/IL20x10/IL16x10）改善 ×3.7~×12。
3. 改善主要来自 gain 维（第 7 维），形状/CTLE 微调为次要贡献；Model B 全程未触发拦截（价值是"保险"而非被依赖的拦截）。
4. 评估协议固定 4194304 符号 × 3 种子（42/43/44）；跨块长绝对 BER 不可比（0 错误时 log10 随块长下降来自 1/(2N) 检测限，非物理漂移）。
5. per-case target_rms / gain 离线标定，换器件需重扫（≈20min）。
6. 数据集/RMS 扫描强制 OMP=1；在线测试用 `tools/run_parallel_envs.py`（每进程 OMP=1）。
7. **并行内存约束**：`num_symbols=2^22` 时每进程峰值内存约 2GB，`--jobs 4` 安全（实测 free ~14GB）；`--jobs 8` 需留意与用户应用抢内存。
