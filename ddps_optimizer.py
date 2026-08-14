import numpy as np
import os
import glob
import pandas as pd
from datetime import datetime
from scipy.optimize import minimize
from scipy.stats import qmc
from utils_config import load_config
from main import run_sim
from tx_channel_extract import extract_tx_s21
from train_surrogates import train_from_df

# ============================================================
# DDPS (Data-Driven Physical Surrogate) 数据驱动物理代理优化器
#
# 完全离线的数据驱动寻优路线：
#   1. 以“已知次优工作点”为种子，在其邻域做扰动采样（真实物理仿真），
#      得到一批覆盖好解区域 + 死区的 (配置 -> 真实 MLSE BER) 数据。
#   2. 训练两个白盒 Ridge 代理：
#        Model A (物理代理): 发端 7-tap 等效 FIR -> log10(BER)
#        Model B (配置代理): FFE 9-tap + CTLE    -> log10(BER)
#   3. 用 SLSQP 在代理上寻优，物理回验 + 主动学习迭代下钻。
#
# 说明：纯全局随机采样很难命中这条极窄的“好解谷底”（实测 1000 个全优化域
# 随机样本 BER 全部 > 0.17）。因此 DDPS 采用“围绕已知工作点做邻域采样”的
# 现实做法——这与真实工程中“在当前工作点附近精细调优”的场景一致。
# ============================================================

FFE_BOUND = 0.3
CTLE_MIN = -20.0
CTLE_MAX = 0.0
PEAK_SUM_LIMIT = 0.8     # sum(|pre_post|) <= 0.8 -> 主抽头 >= 0.2
ENSEMBLE_W_A = 0.7       # 物理代理 Model A 在集成目标中的权重

# 已知次优工作点（种子）：来自两阶段实验的“初始次优点”，MLSE ~1.4e-3 @ SNR28/1M
SEED_TAPS = np.array([0.0, 0.0, -0.034, -0.2987, 0.6091, 0.0, 0.0582, 0.0, 0.0])
SEED_CTLE = 0.0
FFE_SPREAD = 0.05        # 邻域采样：FFE 游标扰动幅度（好解谷底极窄，需小步幅）
CTLE_SPREAD = 3.0        # 邻域采样：CTLE DC 扰动幅度


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


def _collect_seed_data(config, n_samples, ffe_pre, seed_taps=SEED_TAPS,
                       seed_ctle=SEED_CTLE, seed=42):
    """围绕已知次优点做 LHS 邻域扰动采样，覆盖好解区域。"""
    seed_pre_post = np.zeros(8)
    seed_pre_post[:ffe_pre] = seed_taps[:ffe_pre]
    seed_pre_post[ffe_pre:] = seed_taps[ffe_pre + 1:]

    sampler = qmc.LatinHypercube(d=9, seed=seed)
    sp = sampler.random(n=n_samples)

    rows = []
    print(f"Phase 1: seed-neighborhood sampling ({n_samples} samples around seed)...")
    for i in range(n_samples):
        pre_post = seed_pre_post + (sp[i, :8] * 2 - 1.0) * FFE_SPREAD
        ctle = float(np.clip(seed_ctle + (sp[i, 8] * 2 - 1.0) * CTLE_SPREAD, CTLE_MIN, CTLE_MAX))
        taps = construct_9tap(pre_post, ffe_pre)
        logber, mlse_ber = _physical_eval(config, taps, ctle)
        tx_fir = extract_tx_s21(config, custom_tx_taps=taps, num_taps=7)
        rows.append(_make_row(i, taps, ctle, logber, mlse_ber, tx_fir))
        if (i + 1) % 100 == 0:
            print(f"  sampled {i + 1}/{n_samples}")
    return pd.DataFrame(rows)


def _make_objective(config, model_a, model_b, ffe_pre):
    def objective(x):
        taps = construct_9tap(x[:8], ffe_pre)
        ctle = x[8]
        config['tx']['ctle_g_dc_db'] = ctle
        tx_fir = extract_tx_s21(config, custom_tx_taps=taps, num_taps=7)
        pred_a = model_a.predict([tx_fir])[0]
        full_cfg = list(taps) + [ctle]
        pred_b = model_b.predict([full_cfg])[0]
        return ENSEMBLE_W_A * pred_a + (1.0 - ENSEMBLE_W_A) * pred_b
    return objective


def _run_slsqp(config, model_a, model_b, x0, ffe_pre, maxiter=20):
    objective = _make_objective(config, model_a, model_b, ffe_pre)
    res = minimize(objective, x0, method='SLSQP', bounds=_bounds(),
                   options={'maxiter': maxiter, 'disp': False, 'eps': 0.01})
    return res.x, res.fun


def _find_latest_dataset():
    files = glob.glob('dataset/ddps_dataset_*.csv')
    if not files:
        return None
    return max(files, key=os.path.getctime)


def run_ddps(dataset_csv=None, model_dir="models", n_seed_samples=600, n_iter=25,
             result_dir=None, deep_validate=True):
    import create_config
    create_config.generate_config()
    config = load_config('config.xlsx')
    config['system']['enable_eye_plot'] = False
    config['system']['enable_spectrum_plot'] = False

    ffe_pre = int(config['tx'].get('ffe_pre', 4))

    # ---- Phase 1: 种子邻域采样 ----
    df = _collect_seed_data(config, n_seed_samples, ffe_pre)

    # ---- 可选：并入全局随机覆盖数据集（定义死区惩罚地形）----
    if dataset_csv is None:
        dataset_csv = _find_latest_dataset()
    if dataset_csv and os.path.exists(dataset_csv):
        df_warm = pd.read_csv(dataset_csv)
        df = pd.concat([df_warm, df], ignore_index=True)
        print(f"Merged global-coverage dataset {dataset_csv}: total {len(df)} samples")
    n_good = (df['mlse_ber'] < 1e-2).sum()
    print(f"Coverage: {len(df)} samples | BER < 1e-2: {n_good} | "
          f"log10_ber in [{df['log10_ber'].min():.3f}, {df['log10_ber'].max():.3f}]")

    # ---- Phase 2: 训练初始代理 ----
    model_a, model_b = train_from_df(df, model_dir, verbose=True)
    print("Initial surrogate models trained.")

    best_idx = df['log10_ber'].idxmin()
    best_logber = float(df.loc[best_idx, 'log10_ber'])
    best_taps = df.loc[best_idx, [f'ffe_tap_{i}' for i in range(9)]].values.astype(float)
    best_ctle = float(df.loc[best_idx, 'ctle_dc'])
    best_x = _taps_to_x(best_taps, best_ctle, ffe_pre)

    # 种子点本身也作为“初始已知”加入对比
    seed_logber, _ = _physical_eval(config, SEED_TAPS.copy(), SEED_CTLE)

    history_logber = [best_logber]
    history_mlse = [10.0 ** best_logber]
    raw_mlse_history = [10.0 ** best_logber]
    rng = np.random.RandomState(0)

    print(f"Seed point MLSE BER: {10.0 ** seed_logber:.2e}")
    print(f"Initial best (from sampling): MLSE BER = {10.0 ** best_logber:.2e}")
    print(f"Phase 2: {n_iter} active-learning SLSQP refinements...")

    for it in range(n_iter):
        x_opt, pred_opt = _run_slsqp(config, model_a, model_b, best_x, ffe_pre)

        if it % 5 == 4:
            x_rand = np.concatenate([rng.uniform(-FFE_BOUND, FFE_BOUND, 8),
                                     rng.uniform(CTLE_MIN, CTLE_MAX, 1)])
            x_rand_opt, pred_rand = _run_slsqp(config, model_a, model_b, x_rand, ffe_pre)
            if pred_rand < pred_opt:
                x_opt, pred_opt = x_rand_opt, pred_rand

        taps, ctle = _x_to_taps_ctle(x_opt, ffe_pre)
        logber, mlse_ber = _physical_eval(config, taps, ctle)
        raw_mlse_history.append(mlse_ber)
        history_logber.append(min(history_logber[-1], logber))
        history_mlse.append(min(history_mlse[-1], mlse_ber))

        tx_fir = extract_tx_s21(config, custom_tx_taps=taps, num_taps=7)
        df = pd.concat([df, pd.DataFrame([_make_row(len(df) + 1, taps, ctle, logber, mlse_ber, tx_fir)])],
                       ignore_index=True)

        improved = logber < best_logber
        if improved:
            best_logber = logber
            best_taps = taps
            best_ctle = ctle
            best_x = x_opt

        model_a, model_b = train_from_df(df, model_dir, verbose=False)

        print(f"Refine {it + 1}/{n_iter} | surrogate pred {10.0 ** pred_opt:.2e} -> "
              f"physical {mlse_ber:.2e} | best {10.0 ** best_logber:.2e}"
              + ("  *new best*" if improved else ""))

    # ---- Phase 3: 深水校验 (DEEP_1E5) ----
    final_mlse = 10.0 ** best_logber
    deep_summary = ""
    if deep_validate:
        deep_config = {k: v.copy() if isinstance(v, dict) else v for k, v in config.items()}
        deep_config['channel']['snr_db'] = 28.0
        deep_config['system']['num_symbols'] = 1048576
        deep_config['tx']['pattern_length'] = 524288
        deep_config['system']['enable_eye_plot'] = False
        deep_config['system']['enable_spectrum_plot'] = False

        _, ddps_deep = _physical_eval(deep_config, best_taps, best_ctle)
        _, seed_deep = _physical_eval(deep_config, SEED_TAPS.copy(), SEED_CTLE)
        shc_taps = np.array([0.0, 0.0, -0.0195, -0.2987, 0.6636, 0.0, 0.0182, 0.0, 0.0])
        _, shc_deep_9d = _physical_eval(deep_config, shc_taps, 0.0)
        deep_config['tx']['ctle_fp2_ratio'] = 0.9
        _, shc_deep_12d = _physical_eval(deep_config, shc_taps, 0.0)

        deep_summary = (f"Seed (initial sub-optimal) @DEEP_1E5: {seed_deep:.2e}\n"
                        f"DDPS best @DEEP_1E5 (9D): {ddps_deep:.2e}\n"
                        f"SHC  ref  @DEEP_1E5 (9D): {shc_deep_9d:.2e}\n"
                        f"SHC  ref  @DEEP_1E5 (12D fp2=0.9): {shc_deep_12d:.2e}")

    # ---- 保存结果 ----
    if result_dir is None:
        result_dir = os.path.join("result", f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_ddps")
    os.makedirs(result_dir, exist_ok=True)

    with open(os.path.join(result_dir, "sim_log.txt"), "w", encoding='utf-8') as f:
        f.write("--- DDPS Data-Driven Physical Surrogate Optimization ---\n")
        f.write(f"Seed-neighborhood samples: {n_seed_samples}\n")
        f.write(f"Active refinement iters: {n_iter}\n")
        f.write(f"Total samples: {len(df)}\n")
        f.write(f"Warm-up fidelity SNR: {config['channel']['snr_db']} dB, "
                f"num_symbols: {config['system']['num_symbols']}\n\n")
        f.write(f"Seed log10(MLSE BER): {seed_logber:.4f} ({10.0 ** seed_logber:.2e})\n")
        f.write(f"Best log10(MLSE BER): {best_logber:.4f} ({final_mlse:.2e})\n")
        f.write(f"Best Taps: {np.round(best_taps, 4).tolist()}\n")
        f.write(f"Best CTLE DC: {best_ctle:.3f} dB\n")
        if deep_summary:
            f.write(f"\n{deep_summary}\n")
        f.write("\n--- Physical cost per refinement step (raw MLSE BER) ---\n")
        for i, v in enumerate(raw_mlse_history):
            f.write(f"Step {i}: {v:.2e}\n")
        f.write("\n--- Best-so-far MLSE BER ---\n")
        for i, v in enumerate(history_mlse):
            f.write(f"Step {i}: {v:.2e}\n")

    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        plt.figure(figsize=(9, 5))
        plt.semilogy(history_mlse, marker='o', markersize=4, label='DDPS best-so-far')
        plt.axhline(10.0 ** seed_logber, color='red', ls='--', label='seed (initial)')
        plt.xlabel('Active-learning step')
        plt.ylabel('MLSE BER')
        plt.title('DDPS Convergence (seed-neighborhood surrogate refinement)')
        plt.grid(True, which='both', ls='--', alpha=0.6)
        plt.legend()
        png = os.path.join(result_dir, "ddps_convergence.png")
        plt.savefig(png)
        plt.close()
        print(f"Convergence plot saved: {png}")
    except Exception as e:
        print(f"(plot skipped: {e})")

    print("\n--- DDPS Optimization Complete ---")
    print(f"Best MLSE BER (warm-up fidelity): {final_mlse:.2e}")
    print(f"Best Taps: {np.round(best_taps, 4)}")
    print(f"Best CTLE DC: {best_ctle:.3f} dB")
    if deep_summary:
        print(deep_summary)
    print(f"Results saved to {result_dir}")

    return {
        'best_taps': best_taps,
        'best_ctle': best_ctle,
        'best_logber': best_logber,
        'history_mlse': history_mlse,
        'result_dir': result_dir,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', type=str, default=None, help='Optional global-coverage dataset CSV')
    parser.add_argument('--n-seed-samples', type=int, default=600, help='Seed-neighborhood samples')
    parser.add_argument('--n-iter', type=int, default=25, help='Active-learning iterations')
    args = parser.parse_args()
    run_ddps(dataset_csv=args.dataset, n_seed_samples=args.n_seed_samples, n_iter=args.n_iter)
