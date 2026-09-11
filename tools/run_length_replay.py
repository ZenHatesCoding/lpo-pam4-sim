# -*- coding: utf-8 -*-
"""tools/run_length_replay.py — 运行长度回放：定"在线调优该跑几步"。

做法（与 v3 的红线标定回放同源）：先跑一个**较长**的轨迹（默认 15 步）并保留逐步真实 BER，
再在 trace 上回放"只跑前 K 步"会发生什么：
    · 正向改善的用例数（best < seed）
    · 平均改善倍数
    · 真实 BER 劣于种子的步数
据此给出推荐运行长度（收益饱和、劣化步开始累积的拐点）。

用法：
    python tools/run_length_replay.py --main result/ddps_v4_main \
        --ablation result/ddps_v4_abl_ffe --out result/ddps_v4_run_length.csv
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ddps_cases import ENV_CASES  # noqa: E402


def _load(d):
    s = pd.read_csv(os.path.join(d, 'case_summary.csv')).set_index('env')
    tr = {}
    for e in [c['name'] for c in ENV_CASES]:
        p = os.path.join(d, f'trace_{e}.csv')
        if os.path.exists(p):
            tr[e] = pd.read_csv(p)
    return s, tr


def _stats(summary, traces, order, K):
    pos, imps, worse, steps = 0, [], 0, 0
    for e in order:
        t = traces.get(e)
        if t is None or t.empty:
            continue
        tt = t.head(K)
        seed = float(summary.loc[e, 'seed_ber'])
        best = float(tt['real_ber'].min())
        imps.append(seed / best)
        if best < seed * 0.999:
            pos += 1
        worse += int((tt['real_ber'].values > seed).sum())
        steps += len(tt)
    return pos, float(np.mean(imps)), worse, steps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--main', default='result/ddps_v4_main')
    ap.add_argument('--ablation', default='result/ddps_v4_abl_ffe')
    ap.add_argument('--out', default='result/ddps_v4_run_length.csv')
    a = ap.parse_args()

    order = [c['name'] for c in ENV_CASES]
    s, tr = _load(a.main)
    order = [e for e in order if e in s.index]
    sa, tra = _load(a.ablation)
    kmax = max(len(tr[e]) for e in order)

    rows = []
    for K in range(1, kmax + 1):
        p1, m1, w1, st1 = _stats(s, tr, order, K)
        p2, m2, w2, st2 = _stats(sa, tra, order, K)
        rows.append({'k_steps': K, 'n_cases': len(order),
                     'main_positive': p1, 'main_mean_improve_x': m1,
                     'main_worse_steps': w1, 'main_steps': st1,
                     'abl_positive': p2, 'abl_mean_improve_x': m2,
                     'abl_worse_steps': w2, 'abl_steps': st2})
        print(f'  K={K:2d} | 主 {p1:2d}/{len(order)} ×{m1:.2f} worse={w1:3d}/{st1:3d} '
              f'| 消融 {p2:2d}/{len(order)} ×{m2:.2f} worse={w2:3d}/{st2:3d}')
    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    pd.DataFrame(rows).to_csv(a.out, index=False, encoding='utf-8-sig')
    print(f'[replay] -> {a.out}')


if __name__ == '__main__':
    main()
