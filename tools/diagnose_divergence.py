# -*- coding: utf-8 -*-
"""tools/diagnose_divergence.py — 逐用例量化“预测下降 vs 实测变化”（甲方问题 #2 的答卷）。

做三件事：
  1. 逐用例：预测变化总量 Δ_A、实测最优变化 Δ_best、实测末步变化 Δ_end、回归斜率、相关系数；
  2. 代理残差尺度 vs 真实改善幅度（模型能不能分辨这个量级）；
  3. 轨迹在标准化搜索空间里的位移 vs 数据局部颗粒度 ρ（是否走出数据支持区）。

输出：result/ddps_v4_divergence.csv（逐用例）+ 终端汇总。

用法：
    python tools/diagnose_divergence.py --test-dir result/ddps_v4_main \
        --model-dir models/ddps_v4 --dataset dataset/ddps_v4_dataset_<ts>.csv \
        --out result/ddps_v4_divergence.csv
"""
import argparse
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ddps_cases import ENV_CASES          # noqa: E402
from train_surrogates import load_models, _local_spacing  # noqa: E402


def _latest(pattern):
    f = sorted(glob.glob(pattern))
    if not f:
        raise FileNotFoundError(pattern)
    return f[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--test-dir', default='result/ddps_v4_main')
    ap.add_argument('--model-dir', default='models/ddps_v4')
    ap.add_argument('--dataset', default=None)
    ap.add_argument('--out', default='result/ddps_v4_divergence.csv')
    a = ap.parse_args()

    order = [e['name'] for e in ENV_CASES]
    summ = pd.read_csv(os.path.join(a.test_dir, 'case_summary.csv')).set_index('env')
    ds_path = a.dataset or _latest('dataset/ddps_v4_dataset_*.csv')
    df = pd.read_csv(ds_path)
    df = df[df['log10_ber_mlse'] < -0.1]
    xcols = [c for c in df.columns if c.startswith('x_')]
    X = df[xcols].values.astype(float)
    y = df['log10_ber_mlse'].values.astype(float)
    model_a, model_b = load_models(a.model_dir)
    mu, sd = np.asarray(model_a.mu), np.asarray(model_a.sd)
    rho = float(getattr(model_a, 'local_spacing_', np.nan))

    # 代理残差尺度（用 10% 留出的简单近似：k 近邻局部散度）
    rs = np.random.RandomState(0)
    idx = rs.permutation(len(X))
    te = idx[:max(50, len(X) // 10)]
    Zs = (X - mu) / sd
    Zte = Zs[te]
    d = np.sqrt(((Zte[:, None, :] - Zs[None, :, :]) ** 2).sum(-1))
    d.sort(axis=1)
    k = 16
    yhat = np.array([y[np.argsort(((Zs - z) ** 2).sum(1))[:k]].mean() for z in Zte])
    resid_scale = float(np.mean(np.abs(y[te] - yhat)))

    rows = []
    for env in order:
        p = os.path.join(a.test_dir, f'trace_{env}.csv')
        if env not in summ.index or not os.path.exists(p):
            continue
        tr = pd.read_csv(p)
        if tr.empty:
            continue
        seed_lb = float(np.log10(summ.loc[env, 'seed_ber']))
        dA = tr['pred_a'].values - tr['pred_a'].iloc[0]
        dR = tr['real_lb'].values - seed_lb
        Ztr = np.array([(np.asarray(json.loads(v) if isinstance(v, str) else v, float) - mu) / sd
                        for v in tr['x']])
        disp = np.linalg.norm(Ztr - Ztr[0], axis=1)
        ib = int(np.argmin(tr['real_ber'].values))
        slope = float(np.polyfit(dA, dR, 1)[0]) if np.std(dA) > 1e-9 else np.nan
        corr = (float(np.corrcoef(dA, dR)[0, 1])
                if np.std(dA) > 1e-9 and np.std(dR) > 1e-9 else np.nan)
        rows.append({
            'env': env, 'n_steps': len(tr),
            'pred_drop_total_dex': float(dA[-1]),
            'real_best_delta_dex': float(dR[ib]), 'real_final_delta_dex': float(dR[-1]),
            'best_step': ib, 'reg_slope_pred_to_real': slope, 'corr_pred_real': corr,
            'disp_best_sigma': float(disp[ib]), 'disp_end_sigma': float(disp[-1]),
            'disp_best_over_rho': float(disp[ib] / rho) if rho else np.nan,
            'disp_end_over_rho': float(disp[-1] / rho) if rho else np.nan,
        })

    out = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    out.to_csv(a.out, index=False, encoding='utf-8-sig')
    print(f'ρ（局部颗粒度）={rho:.2f}σ | 代理残差尺度 ≈ {resid_scale:.2f} dex')
    print(out.round(3).to_string(index=False))
    print(f"\n预测下降总量 = {out['pred_drop_total_dex'].sum():+.2f} dex | "
          f"实测最优改善总量 = {out['real_best_delta_dex'].sum():+.2f} dex | "
          f"实测末步 = {out['real_final_delta_dex'].sum():+.2f} dex")
    print(f"相关中位 = {out['corr_pred_real'].median():+.2f} | "
          f"斜率中位 = {out['reg_slope_pred_to_real'].median():+.2f} | "
          f"正向相关用例 = {int((out['corr_pred_real'] > 0).sum())}/{len(out)}")
    print(f"实测最优步位移中位 = {out['disp_best_over_rho'].median():.2f} ρ | "
          f"末步位移中位 = {out['disp_end_over_rho'].median():.2f} ρ")
    print(f'[divergence] -> {a.out}')


if __name__ == '__main__':
    main()
