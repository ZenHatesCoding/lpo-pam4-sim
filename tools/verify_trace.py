# -*- coding: utf-8 -*-
"""tools/verify_trace.py — 用独立重仿真复核 trace 记账（排除“记错了/串了”的可能）。

对指定用例的若干步，按 trace 里记录的 x 重新构造配置并**重新跑真实仿真**，
与 trace 里记录的 real_ber 对比。若一致，说明“预测下降而实测上升”不是记账/索引错误，
而是模型本身在该区域的预测与真实脱钩。

用法：
    python tools/verify_trace.py --test-dir result/ddps_v4_main --envs Base_IL10x10,IL20x20 \
        --steps 0,3,7,14 --num-symbols 262144 --sim-seeds 42,43,44
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ddps_optimizer as D          # noqa: E402
import ddps_cases as C              # noqa: E402
from utils_config import load_config  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--test-dir', default='result/ddps_v4_main')
    ap.add_argument('--envs', default='Base_IL10x10,IL20x20')
    ap.add_argument('--steps', default='0,3,7,14')
    ap.add_argument('--num-symbols', type=int, default=262144)
    ap.add_argument('--sim-seeds', default='42,43,44')
    ap.add_argument('--out', default='result/ddps_v4_trace_check.csv')
    a = ap.parse_args()

    D.set_sim_seeds(tuple(int(s) for s in a.sim_seeds.split(',')))
    steps = [int(s) for s in a.steps.split(',')]
    base = load_config('config.xlsx')
    rows = []
    for env in a.envs.split(','):
        p = os.path.join(a.test_dir, f'trace_{env}.csv')
        if not os.path.exists(p):
            print('missing', p)
            continue
        tr = pd.read_csv(p)
        cfg = C.apply_env_to_config(base, env)
        cfg['system']['num_symbols'] = int(a.num_symbols)
        ffe_pre = D._ffe_pre(cfg)
        for st in steps:
            m = tr[tr['step'] == st]
            if m.empty:
                continue
            r = m.iloc[0]
            x = np.asarray(json.loads(r['x']) if isinstance(r['x'], str) else r['x'], float)
            taps, gdc, gdc2, gain = D._x_to_taps_ctle(x, ffe_pre)
            lb, ber = D._physical_eval(cfg, taps, gdc, gdc2, gain)
            rows.append({'env': env, 'step': st,
                         'recorded_log10': float(r['real_lb']),
                         'resim_log10': float(lb),
                         'diff_dex': float(lb - r['real_lb']),
                         'recorded_ber': float(r['real_ber']), 'resim_ber': float(ber)})
            print(f"  {env:22s} step{st:2d} recorded={r['real_ber']:.4e} "
                  f"resim={ber:.4e} diff={lb - r['real_lb']:+.4f} dex")
    out = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    out.to_csv(a.out, index=False, encoding='utf-8-sig')
    if len(out):
        print(f"\n最大偏差 = {out['diff_dex'].abs().max():.4f} dex "
              f"（≤0.01 dex 视为逐位一致，说明 trace 记账无误）")
    print(f'[verify] -> {a.out}')


if __name__ == '__main__':
    main()
