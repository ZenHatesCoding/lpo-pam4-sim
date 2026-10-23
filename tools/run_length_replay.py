# -*- coding: utf-8 -*-
"""tools/run_length_replay.py — 运行长度回放：定"在线调优该跑几步"。

做法（沿已保存的 trace 回放，不重跑仿真）：先用现役入口跑一个**较长**的轨迹
（如 15 步）并保留逐步真实 BER，再在 trace 上回放"只跑前 K 步"会发生什么：
    · 正向改善的用例数（best < seed）
    · 平均改善倍数
    · 真实 BER 劣于种子的步数
据此给出推荐运行长度（收益饱和、劣化步开始累积的拐点）。

读取的是现役结果目录口径（`case_summary.csv` 的 seed_ber + `trace_<env>.csv` 的 real_ber，
Python / C++ 两侧同列名）。

用法：
    # 主实验 = 2^22 全量；对照 = 同口径的另一档（这里用 rotate）
    python tools/run_length_replay.py --main result/ddps_cpp_full \
        --ablation result/ddps_cpp_rotate --out result/ddps_run_length.csv
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ddps_cases import ENV_CASES  # noqa: E402


def _load(d):
    if not d or not os.path.exists(os.path.join(d, 'case_summary.csv')):
        return None, {}
    s = pd.read_csv(os.path.join(d, 'case_summary.csv')).set_index('env')
    if 'seed_ber' not in s.columns:
        raise SystemExit(f'{d}/case_summary.csv 缺少 seed_ber 列——不是现役结果目录口径')
    tr = {}
    for e in [c['name'] for c in ENV_CASES]:
        p = os.path.join(d, f'trace_{e}.csv')
        if os.path.exists(p):
            t = pd.read_csv(p)
            if 'real_ber' not in t.columns:
                raise SystemExit(f'{p} 缺少 real_ber 列——不是现役 trace 口径')
            tr[e] = t
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
    ap.add_argument('--main', default='result/ddps_cpp_full',
                    help='主实验结果目录（现役口径：case_summary.csv + trace_<env>.csv）')
    ap.add_argument('--ablation', default=None,
                    help='可选的对照实验目录（同口径的另一档，如 rotate；不给则只输出主实验列）')
    ap.add_argument('--out', default='result/ddps_run_length.csv')
    a = ap.parse_args()

    order = [c['name'] for c in ENV_CASES]
    s, tr = _load(a.main)
    order = [e for e in order if e in s.index]
    sa, tra = _load(a.ablation)
    has_abl = sa is not None and len(tra) > 0
    kmax = max(len(tr[e]) for e in order)

    rows = []
    for K in range(1, kmax + 1):
        p1, m1, w1, st1 = _stats(s, tr, order, K)
        row = {'k_steps': K, 'n_cases': len(order),
               'main_positive': p1, 'main_mean_improve_x': m1,
               'main_worse_steps': w1, 'main_steps': st1}
        msg = f'  K={K:2d} | {p1:2d}/{len(order)} 正向 ×{m1:.2f} 劣化={w1:3d}/{st1:3d}'
        if has_abl:
            p2, m2, w2, st2 = _stats(sa, tra, order, K)
            row.update({'abl_positive': p2, 'abl_mean_improve_x': m2,
                        'abl_worse_steps': w2, 'abl_steps': st2})
            msg += f' | 对照 {p2:2d}/{len(order)} ×{m2:.2f} 劣化={w2:3d}/{st2:3d}'
        rows.append(row)
        print(msg)
    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    pd.DataFrame(rows).to_csv(a.out, index=False, encoding='utf-8-sig')
    print(f'[replay] -> {a.out}')


if __name__ == '__main__':
    main()
