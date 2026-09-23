# -*- coding: utf-8 -*-
"""tools/pick_seed_config.py — 从训练数据集挑一个次优工作点导出 seed_config JSON。

按 HANDOFF 第 13 条：次优起点应使**基线环境 Base_IL10x10 的真实 BER ≈ 1e-4
（log10 ≈ −4.0）**——高于检测限（可统计）、低于信道失效区（有下降空间）。

用法：
  python tools/pick_seed_config.py --dataset dataset/ddps_dataset_<ts>.csv \
      --target-log10 -4.0 --env Base_IL10x10 --out result/seed_config_bad_1e4.json
"""
import argparse
import copy
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ddps_optimizer as D  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dataset', default=None, help='数据集 CSV（默认取最新）')
    ap.add_argument('--env', default='Base_IL10x10')
    ap.add_argument('--target-log10', type=float, default=-4.0,
                    help='次优起点目标 log10 BER（默认 -4.0 即 ~1e-4）')
    ap.add_argument('--tol', type=float, default=0.5,
                    help='与目标 log10 BER 的允许偏差（dex）')
    ap.add_argument('--out', default='result/seed_config_bad_1e4.json')
    a = ap.parse_args()

    if a.dataset is None:
        import glob
        f = sorted(glob.glob('dataset/ddps_dataset_*.csv'))
        if not f:
            raise SystemExit('no dataset/ddps_dataset_*.csv found')
        a.dataset = f[-1]
    df = pd.read_csv(a.dataset)

    sub = df[df['env'] == a.env].copy().reset_index(drop=True)
    if sub.empty:
        raise SystemExit(f'no rows for env {a.env} in {a.dataset}')

    # 候选：BER 在目标 ±tol 窗口内
    lo = a.target_log10 - a.tol
    hi = a.target_log10 + a.tol
    cand = sub[(sub['log10_ber_mlse'] >= lo) & (sub['log10_ber_mlse'] <= hi)].reset_index(drop=True)
    if cand.empty:
        # 放宽：取离目标最近的一行
        cand = sub.iloc[[int((sub['log10_ber_mlse'] - a.target_log10).abs().argmin())]]

    # 取 log10 BER 最接近目标的一行（在其 ±tol 窗口内）
    row = cand.iloc[int((cand['log10_ber_mlse'] - a.target_log10).abs().argmin())]

    ffe_pre = D.FFE_PRE
    taps = np.array([float(row[f'ffe_tap_{j}']) for j in range(D.N_FFE_TAPS)])
    pre_post = np.concatenate([taps[:ffe_pre], taps[ffe_pre + 1:]]).tolist()
    gdc = float(row['ctle_dc'])
    gdc2 = float(row['ctle_dc2'])
    if 'gain_u' in row and not pd.isna(row['gain_u']):
        u_gain = float(row['gain_u'])
        sc = {'best_u_gain': u_gain}
    else:
        sc = {'best_gain': float(row['driver_gain'])}

    out = copy.deepcopy(sc)
    out['best_pre_post'] = pre_post
    out['best_gdc'] = gdc
    out['best_gdc2'] = gdc2
    out['_source'] = {
        'dataset': os.path.basename(a.dataset),
        'sample_id': str(row.get('sample_id', '')),
        'env': a.env,
        'log10_ber_mlse': float(row['log10_ber_mlse']),
        'ber': float(row['mlse_ber']),
        'gain': float(row['driver_gain']),
        'gain_ratio': float(row['gain_ratio']),
    }

    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print(f'[pick] seed_config -> {a.out}')
    print(f'  pre_post={np.round(pre_post, 4)}  gDC={gdc:.2f}  gDC2={gdc2:.2f}')
    print(f'  gain={float(row["driver_gain"]):.4f} (x{float(row["gain_ratio"]):.3f})  '
          f'log10BER={float(row["log10_ber_mlse"]):+.4f}  '
          f'BER={float(row["mlse_ber"]):.2e}')


if __name__ == '__main__':
    main()