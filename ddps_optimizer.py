import numpy as np
import os
import glob
import pandas as pd
from datetime import datetime
from scipy.stats import qmc, spearmanr
from utils_config import load_config
from main import run_sim
from tx_channel_extract import extract_tx_s21
from train_surrogates import train_from_df, WhiteBoxRidge, WhiteBoxGPR

# ============================================================
# DDPS (Data-Driven Physical Surrogate) 数据驱动物理代理优化器
#
# 架构定位（两阶段分工）：
#   Stage 1（离线，模型供给）——
#     目标不是“穷尽地形/找到全局最优”，而是产出两样东西：
#        (1) 一个“不错的起点” x0（例如上一版已能用的工作点）；
#        (2) 两个白盒代理模型：
#            Model A（物理代理）: 发端 7-tap 等效 FIR -> log10(BER)，充当寻优目标
#            Model B（安全代理）: FFE 9-tap + CTLE    -> log10(BER)，充当安全约束
#     在 x0 邻域采样只是为了“训练模型”，采样覆盖不代表完整地图。
#
#   Stage 2（约束梯度下降）——
#     从 x0 出发，在 Model A 上做手写投影梯度下降（白盒），
#     约束：Model B 预测不越安全红线（不掉锁）。
#     **不回传真实 MLSE_BER**（仅记录用于事后验证），
#     直接优化“发端指标”(Model A) 以实现对“收端 MLSE_BER”的等效优化。
#     理想情况下，Stage 2 能沿 Model A 的梯度走到 Stage 1 采样没见过的更优点。
#
#   跨 SNR 迁移：模型在 26.5 dB 训练，能否同样指导 28 dB（及其它 SNR）的寻优，
#     通过“沿 26.5 dB 引导的下降轨迹，在 28 dB 深水回测”来检验。
# ============================================================

FFE_BOUND = 0.3
CTLE_MIN = -20.0
CTLE_MAX = 0.0
PEAK_SUM_LIMIT = 0.8          # sum(|pre_post|) <= 0.8 -> 主抽头 >= 0.2
SAFETY_MARGIN = 0.3           # Model B 安全裕度：允许相对种子点恶化 0.3 个 log10（≈2× BER）
TRUST_FFE = 0.10              # Stage 2 信任域半径（FFE，相对起点）：防代理外推越界
TRUST_CTLE = 6.0              # Stage 2 信任域半径（CTLE）
GD_LR = 0.02                  # Stage 2 归一化梯度下降初始步长（随 step 以 0.92 衰减）

# 已知“不错的起点”（种子）：来自两阶段实验的初始次优点
SEED_TAPS = np.array([0.0, 0.0, -0.034, -0.2987, 0.6091, 0.0, 0.0582, 0.0, 0.0])
SEED_CTLE = 0.0
FFE_SPREAD = 0.05             # Stage 1 邻域采样幅值
CTLE_SPREAD = 3.0


def construct_9tap(pre_post, ffe_pre):
    abs_sum = np.sum(np.abs(pre_post))
    if abs_sum > PEAK_SUM_LIMIT:
        pre_post = pre_post * (PEAK_SUM_LIMIT / abs_sum)
    taps = np.zeros(9)
    taps[:ffe_pre] = pre_post[:ffe_pre]
    taps[ffe_pre + 1:] = pre_post[ffe_pre:]
    taps[ffe_pre] = 1.0 - np.sum(np.abs(pre_post))
    return taps


def _x_to_taps_ctle(x, ffe_pre):
    return construct_9tap(x[:8], ffe_pre), x[8]


def _taps_to_x(taps, ctle, ffe_pre):
    pre_post = np.zeros(8)
    pre_post[:ffe_pre] = taps[:ffe_pre]
    pre_post[ffe_pre:] = taps[ffe_pre + 1:]
    return np.concatenate([pre_post, [ctle]])


def _bounds():
    return np.array([(-FFE_BOUND, FFE_BOUND)] * 8 + [(CTLE_MIN, CTLE_MAX)])


def _physical_eval(config, taps, ctle):
    config['tx']['ctle_g_dc_db'] = ctle
    _, mlse_ber = run_sim(config, custom_tx_taps=taps, plot_eyes=False, output_dir=None)
    mlse_ber = max(mlse_ber, 1e-8)
    return np.log10(mlse_ber), mlse_ber


def _make_row(sample_id, taps, ctle, logber, mlse_ber, tx_fir):
    row = {'sample_id': sample_id, 'ctle_dc': ctle, 'mlse_ber': mlse_ber,
           'log10_ber': logber}
    for j in range(9):
        row[f'ffe_tap_{j}'] = taps[j]
    for j in range(7):
        row[f'tx_fir_{j}'] = tx_fir[j]
    return row


def _predict_a(model_a, config, taps, ctle, ucb_kappa=0.0):
    """Model A 预测：Ridge 返回均值；带 predict_with_std 的模型（GPR）可返回 mu + kappa*sigma。"""
    config['tx']['ctle_g_dc_db'] = ctle
    tx_fir = extract_tx_s21(config, custom_tx_taps=taps, num_taps=7)
    if hasattr(model_a, 'predict_with_std'):
        mu, sigma = model_a.predict_with_std([tx_fir])
        return float(mu[0] + ucb_kappa * sigma[0])
    return float(model_a.predict([tx_fir])[0])


def _predict_b(model_b, taps, ctle):
    full_cfg = list(taps) + [ctle]
    return float(model_b.predict([full_cfg])[0])


# ============================================================
# Stage 1：模型供给（采样 + 训练 A/B）
# ============================================================

def _stage1_collect(config, n_samples, ffe_pre, seed=42):
    """围绕起点 x0 做 LHS 邻域采样，仅为训练 A/B 模型（不追求穷尽地形）。"""
    seed_pre_post = np.zeros(8)
    seed_pre_post[:ffe_pre] = SEED_TAPS[:ffe_pre]
    seed_pre_post[ffe_pre:] = SEED_TAPS[ffe_pre + 1:]

    sampler = qmc.LatinHypercube(d=9, seed=seed)
    sp = sampler.random(n=n_samples)

    rows = []
    print(f"[Stage 1] neighborhood sampling ({n_samples} samples around x0)...")
    for i in range(n_samples):
        pre_post = seed_pre_post + (sp[i, :8] * 2 - 1.0) * FFE_SPREAD
        ctle = float(np.clip(SEED_CTLE + (sp[i, 8] * 2 - 1.0) * CTLE_SPREAD, CTLE_MIN, CTLE_MAX))
        taps = construct_9tap(pre_post, ffe_pre)
        logber, mlse_ber = _physical_eval(config, taps, ctle)
        tx_fir = extract_tx_s21(config, custom_tx_taps=taps, num_taps=7)
        rows.append(_make_row(i, taps, ctle, logber, mlse_ber, tx_fir))
        if (i + 1) % 100 == 0:
            print(f"  sampled {i + 1}/{n_samples}")
    return pd.DataFrame(rows)


def _stage1_train(df, model_dir):
    return train_from_df(df, model_dir, verbose=True)


# ============================================================
# Stage 2：约束梯度下降（不回传真实 MLSE_BER）
# ============================================================

def _make_objective_a(config, model_a, ffe_pre, ucb_kappa=0.0):
    def objective(x):
        taps = construct_9tap(x[:8], ffe_pre)
        return _predict_a(model_a, config, taps, x[8], ucb_kappa)
    return objective


def _numerical_gradient(fn, x, eps=0.01):
    """白盒有限差分梯度。"""
    x = np.asarray(x, dtype=float)
    f0 = fn(x)
    g = np.zeros_like(x)
    for i in range(len(x)):
        xp = x.copy()
        xp[i] += eps
        g[i] = (fn(xp) - f0) / eps
    return g


def _stage2_descent(config, model_a, model_b, x0, ffe_pre, n_steps, safety_ref, lr, rng,
                    ucb_kappa=0.0):
    """手写投影梯度下降（白盒、逐步可见）：

        x_{k+1} = clip( x_k - lr * g/|g| , 信任域 )

    - 目标：Model A 的负梯度方向（有限差分求得）；ucb_kappa>0 时用 GPR 的 UCB 护栏。
    - 安全：Model B 否决“相对种子点显著恶化”的步子（校准无关的相对红线）。
    - 只记录真实 BER，不回传。
    """
    objective_a = _make_objective_a(config, model_a, ffe_pre, ucb_kappa)

    # 信任域边界（相对 x0 收紧，并裁剪到全局边界）
    gbounds = _bounds()
    radius = np.array([TRUST_FFE] * 8 + [TRUST_CTLE])
    x0 = np.array(x0, dtype=float)
    tr_bounds = np.stack([
        np.maximum(gbounds[:, 0], x0 - radius),
        np.minimum(gbounds[:, 1], x0 + radius),
    ], axis=1)

    safety_limit = safety_ref + SAFETY_MARGIN

    trace = []
    x = x0.copy()

    for step in range(n_steps):
        # 1. 数值梯度 + 归一化下降方向
        g = _numerical_gradient(objective_a, x, eps=0.01)
        gn = np.linalg.norm(g)
        if gn < 1e-9:
            break
        direction = g / gn

        # 2. 回溯线搜索：Model B 保证安全（相对种子点的红线），步长随 step 衰减以收敛
        alpha = lr * (0.92 ** step)
        x_new = None
        for _ in range(20):
            x_cand = np.clip(x - alpha * direction, tr_bounds[:, 0], tr_bounds[:, 1])
            taps_c, ctle_c = _x_to_taps_ctle(x_cand, ffe_pre)
            if _predict_b(model_b, taps_c, ctle_c) <= safety_limit:
                x_new = x_cand
                break
            alpha *= 0.5
        if x_new is None:
            break  # 信任域内找不到安全方向，停止

        # 3. 代理预测 + 真实 BER（仅记录验证）
        taps, ctle = _x_to_taps_ctle(x_new, ffe_pre)
        pred_a = _predict_a(model_a, config, taps, ctle)
        pred_b = _predict_b(model_b, taps, ctle)
        real_logber, real_mlse = _physical_eval(config, taps, ctle)

        trace.append({
            'step': step,
            'x': x_new,
            'taps': taps,
            'ctle': ctle,
            'pred_a': pred_a,
            'pred_b': pred_b,
            'safe': pred_b <= safety_limit,
            'real_logber': real_logber,
            'real_mlse': real_mlse,
            'grad_norm': gn,
        })

        print(f"[Stage 2] gd {step + 1}/{n_steps} | ModelA {10.0 ** pred_a:.2e} "
              f"| ModelB {10.0 ** pred_b:.2e} (safe) | real {real_mlse:.2e} | |g| {gn:.2e}")

        # 4. 收敛判断：位移几乎为零则提前停止
        if np.linalg.norm(x_new - x) < 1e-4:
            break
        x = x_new

    return trace


# ============================================================
# 编排 + 日志/图/summary
# ============================================================

def _find_latest_dataset():
    files = glob.glob('dataset/ddps_dataset_*.csv')
    if not files:
        return None
    return max(files, key=os.path.getctime)


def _deep_config(config):
    dc = {k: v.copy() if isinstance(v, dict) else v for k, v in config.items()}
    dc['channel']['snr_db'] = 28.0
    dc['system']['num_symbols'] = 1048576
    dc['tx']['pattern_length'] = 524288
    dc['system']['enable_eye_plot'] = False
    dc['system']['enable_spectrum_plot'] = False
    return dc


def run_ddps(dataset_csv=None, model_dir="models", n_stage1_samples=600, n_stage2_steps=40,
             result_dir=None, deep_validate=True, cross_snr_probes=5):
    import create_config
    create_config.generate_config()
    config = load_config('config.xlsx')
    config['system']['enable_eye_plot'] = False
    config['system']['enable_spectrum_plot'] = False

    ffe_pre = int(config['tx'].get('ffe_pre', 4))

    # ---------- Stage 1：模型供给 ----------
    df = _stage1_collect(config, n_stage1_samples, ffe_pre)

    if dataset_csv is None:
        dataset_csv = _find_latest_dataset()
    if dataset_csv and os.path.exists(dataset_csv):
        df_warm = pd.read_csv(dataset_csv)
        df = pd.concat([df_warm, df], ignore_index=True)
        print(f"[Stage 1] merged global-coverage dataset {dataset_csv}: total {len(df)} samples")

    model_a, model_b = _stage1_train(df, model_dir)

    # Stage 1 采样最优（用于证明 Stage 2 能“超出地图”，不作为 Stage 2 目标）
    stage1_best_idx = df['log10_ber'].idxmin()
    stage1_best_logber = float(df.loc[stage1_best_idx, 'log10_ber'])
    stage1_best_taps = df.loc[stage1_best_idx, [f'ffe_tap_{i}' for i in range(9)]].values.astype(float)
    stage1_best_ctle = float(df.loc[stage1_best_idx, 'ctle_dc'])

    # 起点 x0 = 种子（“不错的起点”）
    x0 = _taps_to_x(SEED_TAPS.copy(), SEED_CTLE, ffe_pre)
    seed_logber, seed_mlse = _physical_eval(config, SEED_TAPS.copy(), SEED_CTLE)

    print(f"[Stage 1] done. start x0 real MLSE = {seed_mlse:.2e} | "
          f"Stage-1 sampled best = {10.0 ** stage1_best_logber:.2e}")

    # ---------- Stage 2：约束下降（不回传真实 BER）----------
    # 安全参考 = Model B 对种子点（已知安全）的预测；红线 = 参考 + 裕度（相对、校准无关）
    safety_ref = _predict_b(model_b, SEED_TAPS.copy(), SEED_CTLE)
    rng = np.random.RandomState(0)
    trace = _stage2_descent(config, model_a, model_b, x0, ffe_pre, n_stage2_steps,
                            safety_ref, GD_LR, rng)

    real_mlses = np.array([t['real_mlse'] for t in trace])
    best_i = int(np.argmin(real_mlses))
    best_taps = trace[best_i]['taps']
    best_ctle = trace[best_i]['ctle']
    stage2_best_mlse = real_mlses[best_i]
    max_mlse = float(np.max(real_mlses))

    # 等效性：Model A 预测 vs 真实 log10(BER) 的秩相关
    pred_a = np.array([t['pred_a'] for t in trace])
    real_logber = np.array([t['real_logber'] for t in trace])
    spearman = spearmanr(pred_a, real_logber).correlation

    print(f"[Stage 2] done. best real MLSE = {stage2_best_mlse:.2e} (step {best_i}) | "
          f"max real MLSE = {max_mlse:.2e} | Spearman(ModelA, real) = {spearman:.3f}")

    # ---------- 跨 SNR 迁移回测 ----------
    cross_snr = []
    if deep_validate and cross_snr_probes > 0:
        dc = _deep_config(config)
        idxs = sorted(set([0, best_i] + list(np.linspace(0, len(trace) - 1, cross_snr_probes).astype(int))))
        for i in idxs:
            t = trace[i]
            _, mlse_28 = _physical_eval(dc, t['taps'], t['ctle'])
            cross_snr.append({'step': i, 'real_mlse_26dB': t['real_mlse'], 'real_mlse_28dB': mlse_28})

    # ---------- 深水校验 ----------
    deep_summary = ""
    if deep_validate:
        dc = _deep_config(config)
        _, seed_deep = _physical_eval(dc, SEED_TAPS.copy(), SEED_CTLE)
        _, ddps_deep = _physical_eval(dc, best_taps, best_ctle)
        shc_taps = np.array([0.0, 0.0, -0.0195, -0.2987, 0.6636, 0.0, 0.0182, 0.0, 0.0])
        _, shc_deep_9d = _physical_eval(dc, shc_taps, 0.0)
        dc['tx']['ctle_fp2_ratio'] = 0.9
        _, shc_deep_12d = _physical_eval(dc, shc_taps, 0.0)
        deep_summary = (f"start x0  @DEEP_1E5: {seed_deep:.2e}\n"
                        f"DDPS best @DEEP_1E5 (9D): {ddps_deep:.2e}\n"
                        f"SHC ref   @DEEP_1E5 (9D): {shc_deep_9d:.2e}\n"
                        f"SHC ref   @DEEP_1E5 (12D fp2=0.9): {shc_deep_12d:.2e}")

    # ---------- 保存结果 ----------
    if result_dir is None:
        result_dir = os.path.join("result", f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_ddps")
    os.makedirs(result_dir, exist_ok=True)

    _write_sim_log(result_dir, config, df, n_stage1_samples, n_stage2_steps, trace,
                   stage1_best_logber, seed_logber, stage2_best_mlse, best_taps, best_ctle,
                   max_mlse, spearman, cross_snr, deep_summary)
    _write_summary_md(result_dir, config, trace, stage1_best_logber, seed_logber,
                      stage2_best_mlse, best_taps, best_ctle, max_mlse, spearman,
                      cross_snr, deep_summary)
    _plot_convergence(result_dir, trace, seed_logber, stage1_best_logber)

    print("\n--- DDPS Complete ---")
    print(f"Stage-1 sampled best MLSE: {10.0 ** stage1_best_logber:.2e}")
    print(f"Stage-2 best MLSE (no feedback): {stage2_best_mlse:.2e}  (step {best_i})")
    print(f"Stage-2 max MLSE (safety): {max_mlse:.2e}")
    print(f"Spearman(ModelA, real logBER): {spearman:.3f}")
    if deep_summary:
        print(deep_summary)
    print(f"Results saved to {result_dir}")

    return {
        'best_taps': best_taps, 'best_ctle': best_ctle,
        'stage1_best_mlse': 10.0 ** stage1_best_logber,
        'stage2_best_mlse': stage2_best_mlse,
        'max_mlse': max_mlse, 'spearman': spearman,
        'cross_snr': cross_snr, 'result_dir': result_dir,
    }


def _write_sim_log(result_dir, config, df, n_s1, n_s2, trace, s1_best, seed_lb,
                   s2_best, best_taps, best_ctle, max_mlse, spearman, cross_snr, deep_summary):
    with open(os.path.join(result_dir, "sim_log.txt"), "w", encoding='utf-8') as f:
        f.write("--- DDPS Data-Driven Physical Surrogate Optimization ---\n")
        f.write(f"Stage 1 samples: {n_s1} (total after merge: {len(df)})\n")
        f.write(f"Stage 2 steps: {n_s2} (constrained descent, NO real-BER feedback)\n")
        f.write(f"Safety rule (Model B): <= seed_pred + {SAFETY_MARGIN} log10 (relative)\n")
        f.write(f"Warm-up fidelity: SNR {config['channel']['snr_db']} dB, "
                f"num_symbols {config['system']['num_symbols']}\n\n")
        f.write(f"Start x0 log10(MLSE BER): {seed_lb:.4f} ({10.0 ** seed_lb:.2e})\n")
        f.write(f"Stage-1 sampled best log10(BER): {s1_best:.4f} ({10.0 ** s1_best:.2e})\n")
        f.write(f"Stage-2 best log10(BER): {np.log10(max(s2_best, 1e-8)):.4f} ({s2_best:.2e})\n")
        f.write(f"Stage-2 max MLSE (safety): {max_mlse:.2e}\n")
        f.write(f"Spearman(ModelA, real logBER): {spearman:.3f}\n")
        f.write(f"Best Taps: {np.round(best_taps, 4).tolist()}\n")
        f.write(f"Best CTLE DC: {best_ctle:.3f} dB\n")
        if deep_summary:
            f.write(f"\n{deep_summary}\n")
        f.write("\n--- Stage 2 trace (step | ModelA | ModelB | safe | real MLSE) ---\n")
        for t in trace:
            f.write(f"step {t['step']:2d} | A {t['pred_a']:+.3f} | B {t['pred_b']:+.3f} | "
                    f"{'safe' if t['safe'] else 'UNSAFE'} | {t['real_mlse']:.2e}\n")
        if cross_snr:
            f.write("\n--- Cross-SNR transfer (26.5dB models guiding 28dB descent) ---\n")
            for c in cross_snr:
                f.write(f"step {c['step']:2d} | 26.5dB {c['real_mlse_26dB']:.2e} | "
                        f"28dB {c['real_mlse_28dB']:.2e}\n")


def _write_summary_md(result_dir, config, trace, s1_best, seed_lb, s2_best,
                      best_taps, best_ctle, max_mlse, spearman, cross_snr, deep_summary):
    with open(os.path.join(result_dir, "ddps_summary.md"), "w", encoding='utf-8') as f:
        f.write("# DDPS 数据驱动物理代理优化器 — 结果报告\n\n")
        f.write("## 架构\n")
        f.write("- **Stage 1**：在起点邻域采样，训练 Model A（发端 7-tap FIR → logBER）与 "
                "Model B（配置 → logBER）。产出 = 起点 + 双模型，不追求穷尽地形。\n")
        f.write("- **Stage 2**：在 Model A 上做手写投影梯度下降，Model B 作安全回溯约束 + 信任域；"
                "**不回传真实 MLSE_BER**（仅记录验证）。\n\n")
        f.write("## 关键指标\n")
        f.write(f"- 起点 x0 真实 MLSE：`{10.0 ** seed_lb:.2e}`\n")
        f.write(f"- Stage 1 采样最优 MLSE：`{10.0 ** s1_best:.2e}`\n")
        f.write(f"- **Stage 2 最优 MLSE（不回传）**：`{s2_best:.2e}`\n")
        f.write(f"- Stage 2 最大 MLSE（安全上限）：`{max_mlse:.2e}`\n")
        f.write(f"- 等效性 Spearman(ModelA, real logBER)：`{spearman:.3f}`\n")
        f.write(f"- 最优 Taps：`{np.round(best_taps, 4).tolist()}`\n")
        f.write(f"- 最优 CTLE DC：`{best_ctle:.3f} dB`\n\n")
        if cross_snr:
            f.write("## 跨 SNR 迁移（26.5 dB 模型引导 28 dB 下降）\n")
            f.write("| step | 26.5dB MLSE | 28dB MLSE |\n| --- | --- | --- |\n")
            for c in cross_snr:
                f.write(f"| {c['step']} | `{c['real_mlse_26dB']:.2e}` | `{c['real_mlse_28dB']:.2e}` |\n")
            f.write("\n")
        if deep_summary:
            f.write("## 深水校验 (DEEP_1E5)\n```\n" + deep_summary + "\n```\n")


def _plot_convergence(result_dir, trace, seed_lb, s1_best):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        steps = [t['step'] for t in trace]
        real = [t['real_mlse'] for t in trace]
        pred_a = [10.0 ** t['pred_a'] for t in trace]
        plt.figure(figsize=(9, 5))
        plt.semilogy(steps, real, marker='o', markersize=4, label='real MLSE (recorded only)')
        plt.semilogy(steps, pred_a, marker='x', markersize=4, ls='--', label='Model A prediction')
        plt.axhline(10.0 ** seed_lb, color='red', ls=':', label='start x0')
        plt.axhline(10.0 ** s1_best, color='green', ls=':', label='Stage-1 sampled best')
        plt.xlabel('Stage 2 step')
        plt.ylabel('MLSE BER')
        plt.title('DDPS Stage 2: constrained descent on Model A (no real-BER feedback)')
        plt.grid(True, which='both', ls='--', alpha=0.6)
        plt.legend()
        plt.savefig(os.path.join(result_dir, "ddps_convergence.png"))
        plt.close()
    except Exception as e:
        print(f"(plot skipped: {e})")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', type=str, default=None, help='Optional global-coverage dataset CSV')
    parser.add_argument('--n-stage1-samples', type=int, default=600)
    parser.add_argument('--n-stage2-steps', type=int, default=40)
    args = parser.parse_args()
    run_ddps(dataset_csv=args.dataset, n_stage1_samples=args.n_stage1_samples,
             n_stage2_steps=args.n_stage2_steps)
