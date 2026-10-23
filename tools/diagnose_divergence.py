# -*- coding: utf-8 -*-
"""tools/diagnose_divergence.py — 逐用例量化“预测下降 vs 实测变化”。

做三件事（全部落在现役 Model A 口径内）：
  1. 逐用例：预测变化总量 Δ_A、实测最优变化 Δ_best、实测末步变化 Δ_end、回归斜率、相关系数；
  2. 代理残差尺度 vs 真实改善幅度（Model A 能不能分辨这个量级）：k 近邻局部散度；
  3. 轨迹在 Model A 标准化的 8 维探针空间（7-tap Tx FIR + drive_rms）里的位移 vs 数据集
     局部颗粒度 ρ（是否走出数据支持区）。

Model B 不在线使用，因此位移/ρ 不再用参数域 Model B 的信任盒口径，改在 Model A 的探针空间
里算：μ/σ 取自 Model A 的标准化参数，ρ = 训练数据在该空间的 33 近邻距离中位数。

输出：result/ddps_divergence.csv（逐用例）+ 终端汇总。

用法：
    python tools/diagnose_divergence.py --test-dir result/ddps_cpp_full \
        --model-dir models/ddps --dataset dataset/ddps_dataset_20260924_144548.csv \
        --out result/ddps_divergence.csv
"""
import argparse
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ddps_optimizer as D                          # noqa: E402
from ddps_cases import ENV_CASES, apply_env_to_config  # noqa: E402
from utils_config import load_config                # noqa: E402
from train_surrogates import load_models, A_COLS    # noqa: E402


def _latest(pattern):
    f = sorted(glob.glob(pattern))
    if not f:
        raise FileNotFoundError(pattern)
    return f[-1]


def _local_spacing(Z, k=33):
    """标准化空间里的局部颗粒度 ρ：k 近邻距离的中位数（与训练期 rho 同口径）。"""
    from scipy.spatial import cKDTree
    tree = cKDTree(Z)
    d, _ = tree.query(Z, k=k)
    return float(np.median(d[:, -1]))


def _as_vector(v):
    return np.asarray(json.loads(v) if isinstance(v, str) else v, dtype=float)


def main():
    ap = argparse.ArgumentParser(description='预测下降 vs 实测变化的逐用例诊断')
    ap.add_argument('--test-dir', default='result/ddps_cpp_full')
    ap.add_argument('--model-dir', default='models/ddps')
    ap.add_argument('--dataset', default=None)
    ap.add_argument('--out', default='result/ddps_divergence.csv')
    a = ap.parse_args()

    order = [e['name'] for e in ENV_CASES]
    env_map = {e['name']: e for e in ENV_CASES}
    summ = pd.read_csv(os.path.join(a.test_dir, 'case_summary.csv')).set_index('env')
    ds_path = a.dataset or _latest('dataset/ddps_dataset_*.csv')
    df = pd.read_csv(ds_path)
    df = df[df['log10_ber_mlse'] < -0.1]
    y = df['log10_ber_mlse'].values.astype(float)

    # 位移/ρ 在 Model A 的 8 维探针空间里算（Model B 不在线使用：load_models 返回 (A, B)，只取 A）
    model_a = load_models(a.model_dir)[0]
    mu, sd = np.asarray(model_a.mu, dtype=float), np.asarray(model_a.sd, dtype=float)
    X = df[A_COLS].values.astype(float)
    Zs = (X - mu) / sd
    rho = _local_spacing(Zs)

    # 代理残差尺度（10% 留出的 k 近邻局部散度近似）
    rs = np.random.RandomState(0)
    idx = rs.permutation(len(X))
    te = idx[:max(50, len(X) // 10)]
    Zte = Zs[te]
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
        cfg = apply_env_to_config(load_config('config.xlsx'), env_map[env])
        seed_lb = float(np.log10(summ.loc[env, 'seed_ber']))
        dA = tr['pred_a'].values - tr['pred_a'].iloc[0]
        dR = tr['real_lb'].values - seed_lb

        # 落点 -> 8 维探针 -> 标准化空间位移（σ 为单位）
        probes = [D._probe_features(cfg, D.taps_of(_as_vector(rec['taps'])),
                                    float(rec['gdc']), float(rec['gdc2']), float(rec['gain']))
                  for _, rec in tr.iterrows()]
        Ztr = (np.asarray(probes, dtype=float) - mu) / sd
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
    print(f'ρ（Model A 探针空间局部颗粒度）={rho:.2f}σ | 代理残差尺度 ≈ {resid_scale:.2f} dex')
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
