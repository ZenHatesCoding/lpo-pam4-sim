import os
import numpy as np
import pandas as pd
from datetime import datetime
from scipy.stats import spearmanr
import create_config, utils_config
import ddps_optimizer as D
import train_surrogates as T

# ============================================================
# 代理模型综合对比（同数据集、同起点、同信任域、同安全约束，不回传真实 BER）
#
# 对比维度：
#   1. Ridge + 梯度下降            （现版 DDPS）
#   2. GPR(均值) + 梯度下降         （更“聪明”的代理，无不确定性护栏）
#   3. GPR(μ + 3σ, UCB) + 梯度下降  （不确定性护栏，防外推/防坠崖）
#
# 所有变体共享：Stage 1 数据集、起点 x0、Model B(安全)、信任域、步长衰减。
# ============================================================


class StandardizingGPR:
    """给 GPR 包一层 Z-Score 标准化，使 RBF 核在各特征尺度上各向同性。"""

    def __init__(self, gpr, mu, std):
        self.gpr = gpr
        self.mu = mu
        self.std = std

    def predict_with_std(self, X):
        Xs = (np.atleast_2d(np.asarray(X, dtype=float)) - self.mu) / self.std
        return self.gpr.predict_with_std(Xs)


def _deep_validate(config, taps, ctle):
    dc = {k: v.copy() if isinstance(v, dict) else v for k, v in config.items()}
    dc['system']['num_symbols'] = 1048576
    dc['tx']['pattern_length'] = 524288
    dc['system']['enable_eye_plot'] = False
    dc['system']['enable_spectrum_plot'] = False
    _, mlse = D._physical_eval(dc, taps, ctle)
    return mlse


def main(n_seed=600, n_steps=40, deep=True):
    create_config.generate_config()
    config = utils_config.load_config('config.xlsx')
    config['system']['enable_eye_plot'] = False
    config['system']['enable_spectrum_plot'] = False
    ffe_pre = int(config['tx'].get('ffe_pre', 4))

    # ---------- Stage 1 数据集（生成一次，共享） ----------
    df = D._stage1_collect(config, n_seed, ffe_pre)
    csv = D._find_latest_dataset()
    if csv:
        df = pd.concat([pd.read_csv(csv), df], ignore_index=True)
    # 保存完整数据集，供复用 / 复现
    _ds_csv = os.path.join("dataset", f"ddps_stage1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    df.to_csv(_ds_csv, index=False)
    print(f"Stage 1 dataset saved to {_ds_csv}")
    df = df[df['log10_ber'] < -0.1].copy()

    XA = df[T.FIR_COLS].values.astype(float)
    XB = df[T.CONFIG_COLS].values.astype(float)
    y = df['log10_ber'].values.astype(float)
    tr, te = T._train_test_split_idx(len(df), 0.2, 42)

    # ---------- 共享 Model B（Ridge 安全代理） ----------
    mb = T.WhiteBoxRidge(2, 1.0).fit(XB[tr], y[tr])
    safety_ref = D._predict_b(mb, D.SEED_TAPS.copy(), D.SEED_CTLE)
    x0 = D._taps_to_x(D.SEED_TAPS.copy(), D.SEED_CTLE, ffe_pre)

    # ---------- 三个变体 ----------
    ma_ridge = T.WhiteBoxRidge(2, 1.0).fit(XA[tr], y[tr])

    mu_a = XA[tr].mean(0)
    std_a = XA[tr].std(0)
    std_a[std_a < 1e-8] = 1.0
    ma_gpr = T.WhiteBoxGPR(length_scale=1.0, sigma_f=1.0, noise_var=1e-3).fit(
        (XA[tr] - mu_a) / std_a, y[tr])
    ma_gpr_wrap = StandardizingGPR(ma_gpr, mu_a, std_a)

    variants = [
        ('Ridge + GD', ma_ridge, 0.0),
        ('GPR(mu) + GD', ma_gpr_wrap, 0.0),
        ('GPR(UCB 3sigma) + GD', ma_gpr_wrap, 3.0),
    ]

    results = {}
    for name, ma, kappa in variants:
        rng = np.random.RandomState(0)
        trace = D._stage2_descent(config, ma, mb, x0, ffe_pre, n_steps,
                                  safety_ref, D.GD_LR, rng, ucb_kappa=kappa)
        real = np.array([t['real_mlse'] for t in trace])
        best_i = int(np.argmin(real))
        pred_a = np.array([t['pred_a'] for t in trace])
        rl = np.array([t['real_logber'] for t in trace])
        sp = spearmanr(pred_a, rl).correlation
        results[name] = {
            'best_mlse': real[best_i], 'best_step': best_i, 'max_mlse': float(real.max()),
            'spearman': sp, 'best_taps': trace[best_i]['taps'], 'best_ctle': trace[best_i]['ctle'],
            'real': real, 'best_so_far': np.minimum.accumulate(real),
        }
        print(f"[{name}] best {real[best_i]:.2e} @step{best_i} | max {real.max():.2e} | "
              f"Spearman {sp:.3f}")

    # ---------- 深水校验 ----------
    if deep:
        for name, r in results.items():
            r['deep_mlse'] = _deep_validate(config, r['best_taps'], r['best_ctle'])
            print(f"[{name}] DEEP_1E5 = {r['deep_mlse']:.2e}")

    # ---------- 对比图（best-so-far 曲线，存到 latest_comparison）----------
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        plt.figure(figsize=(9, 5))
        styles = [('Ridge + GD', 'o-'), ('GPR(mu) + GD', 's--'), ('GPR(UCB 3sigma) + GD', '^:')]
        for (name, fmt), r in zip(styles, [results[k] for k in
                                            ['Ridge + GD', 'GPR(mu) + GD', 'GPR(UCB 3sigma) + GD']]):
            plt.semilogy(r['best_so_far'], fmt, markersize=4, label=name)
        plt.axhline(10.0 ** D._physical_eval(config, D.SEED_TAPS.copy(), D.SEED_CTLE)[0],
                    color='red', ls='--', alpha=0.5, label='start x0')
        plt.xlabel('Stage 2 gradient step')
        plt.ylabel('MLSE BER (best-so-far)')
        plt.title('Surrogate comparison (same data/start/safety, no real-BER feedback)')
        plt.grid(True, which='both', ls='--', alpha=0.6)
        plt.legend()
        lc_dir = os.path.join("result", "latest_comparison", "ddps")
        os.makedirs(lc_dir, exist_ok=True)
        plt.savefig(os.path.join(lc_dir, "surrogate_comparison.png"))
        plt.close()
        print(f"Comparison figure saved to {lc_dir}/surrogate_comparison.png")
    except Exception as e:
        print(f"(comparison figure skipped: {e})")

    # ---------- 输出 ----------
    out_dir = os.path.join("result", f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_surrogate_cmp")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "comparison.md"), "w", encoding='utf-8') as f:
        f.write("# 代理模型综合对比（同数据/同起点/同约束，不回传真实 BER）\n\n")
        f.write("| 变体 | 热身最优 MLSE | 收敛步 | 全程最大 MLSE | Spearman | DEEP_1E5 |\n")
        f.write("| --- | --- | --- | --- | --- | --- |\n")
        for name, r in results.items():
            deep = f"{r.get('deep_mlse', float('nan')):.2e}" if 'deep_mlse' in r else "-"
            f.write(f"| {name} | `{r['best_mlse']:.2e}` | {r['best_step']} | "
                    f"`{r['max_mlse']:.2e}` | `{r['spearman']:.3f}` | `{deep}` |\n")
        f.write("\n- Model B（安全）与起点/信任域/步长衰减对所有变体一致；仅 Model A 代理不同。\n")
        f.write("- GPR(UCB) 用 μ+3σ 作目标，天然惩罚未采样区（不确定性高）的步子。\n")
    print(f"\nComparison saved to {out_dir}/comparison.md")
    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--n-seed', type=int, default=600)
    parser.add_argument('--n-steps', type=int, default=40)
    args = parser.parse_args()
    main(n_seed=args.n_seed, n_steps=args.n_steps)
