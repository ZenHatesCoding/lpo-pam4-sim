# -*- coding: utf-8 -*-
"""tools/validate_local_gradient.py — Model A/B 的**局部方向**实测标定（离线验证，不参与训练）。

做一件模型指标表看不出来的事：在**真实链路**上，对种子工作点沿 11 个搜索轴做中心差分，
测出真实 log10 BER 的局部斜率，再与 Model A / Model B 的解析梯度逐轴对照，回答：

    "这个代理模型给出来的方向，到底对不对？"

指标：
    hit   —— 11 轴方向命中率（符号一致）
    w_hit —— 按 |实测斜率| 加权的方向命中率（陡的轴权重更大）
    corr  —— 模型梯度与实测梯度的相关系数（量级是否同序）

用法：
    python tools/validate_local_gradient.py --model-dir models/ddps_v4 \
        --env Base_IL10x10 --num-symbols 262144 --sim-seeds 42,43,44 \
        --out result/ddps_v4_local_gradient.csv
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ddps_optimizer as D          # noqa: E402
import ddps_cases as C              # noqa: E402
from utils_config import load_config  # noqa: E402
from train_surrogates import load_models  # noqa: E402

DIM_NAMES = [f'FFE_side{i}' for i in range(8)] + ['CTLE_gDC', 'CTLE_gDC2', 'driver_gain_u']
DIM_UNITS = ['tap'] * 8 + ['dB', 'dB', 'dex']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model-dir', default='models/ddps_v4')
    ap.add_argument('--env', default='Base_IL10x10')
    ap.add_argument('--num-symbols', type=int, default=262144)
    ap.add_argument('--sim-seeds', default='42,43,44')
    ap.add_argument('--out', default='result/ddps_v4_local_gradient.csv')
    ap.add_argument('--steps', default='0.05,0.05,0.05,0.05,0.05,0.05,0.05,0.05,1.0,1.0,0.10',
                    help='各轴中心差分步长（FFE 8 个、CTLE 2 个、gain 1 个）')
    args = ap.parse_args()

    seeds = tuple(int(s) for s in args.sim_seeds.split(','))
    D.set_sim_seeds(seeds)
    steps = np.array([float(s) for s in args.steps.split(',')])

    cfg = C.apply_env_to_config(load_config('config.xlsx'), args.env)
    cfg['system']['num_symbols'] = int(args.num_symbols)
    ffe_pre = D._ffe_pre(cfg)
    model_a, model_b = load_models(args.model_dir)

    x0 = D._taps_to_x(D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2, D.SEED_GAIN, ffe_pre)

    def ev(x):
        taps, gdc, gdc2, gain = D._x_to_taps_ctle(x, ffe_pre)
        return D._physical_eval(cfg, taps, gdc, gdc2, gain)

    lb0, ber0 = ev(x0)
    g_a = D._grad_a(model_a, x0)
    g_b = np.asarray(model_b.grad(x0.reshape(1, -1))[0], dtype=float) \
        if hasattr(model_b, 'grad') else np.full(11, np.nan)

    print(f'[validate] env={args.env} | {args.num_symbols} symbols x seeds{seeds}')
    print(f'[validate] seed log10BER={lb0:+.4f} (BER={ber0:.4e})')

    rows = []
    for i in range(11):
        s = steps[i]
        xp, xm = x0.copy(), x0.copy()
        xp[i] += s
        xm[i] -= s
        lp, bp = ev(xp)
        lm, bm = ev(xm)
        real = (lp - lm) / (2.0 * s)
        rows.append({
            'dim': DIM_NAMES[i], 'unit': DIM_UNITS[i], 'step': float(s),
            'real_log10_plus': lp, 'real_log10_minus': lm,
            'real_d_plus': lp - lb0, 'real_d_minus': lm - lb0,
            'real_slope': real,
            'model_a_slope': float(g_a[i]), 'model_b_slope': float(g_b[i]),
            'sign_match_a': int(np.sign(g_a[i]) == np.sign(real)),
            'sign_match_b': int(np.sign(g_b[i]) == np.sign(real)),
            'ratio_a': float(g_a[i] / real) if real != 0 else np.nan,
        })
        print(f'   {DIM_NAMES[i]:14s} step={s:+.3f} real d(+){lp - lb0:+.3f} d(-){lm - lb0:+.3f} '
              f'slope={real:+.3f} | A={g_a[i]:+.3f} B={g_b[i]:+.3f}')

    real_g = np.array([r['real_slope'] for r in rows])
    w = np.abs(real_g) / np.abs(real_g).sum()

    def _metrics(g):
        ok = np.sign(g) == np.sign(real_g)
        return (float(ok.mean()), float((w * ok).sum()),
                float(np.corrcoef(g, real_g)[0, 1]) if np.std(g) > 0 else float('nan'))

    hit_a, wh_a, corr_a = _metrics(g_a)
    hit_b, wh_b, corr_b = _metrics(g_b)
    print(f'[validate] Model A: hit={hit_a:.2f} w_hit={wh_a:.2f} corr={corr_a:+.2f}')
    print(f'[validate] Model B: hit={hit_b:.2f} w_hit={wh_b:.2f} corr={corr_b:+.2f}')

    import pandas as pd
    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    pd.DataFrame(rows).to_csv(args.out, index=False, encoding='utf-8-sig')
    summary = os.path.splitext(args.out)[0] + '_summary.csv'
    pd.DataFrame([{
        'env': args.env, 'num_symbols': args.num_symbols, 'sim_seeds': args.sim_seeds,
        'seed_log10_ber': lb0, 'seed_ber': ber0,
        'model_a_hit': hit_a, 'model_a_w_hit': wh_a, 'model_a_corr': corr_a,
        'model_b_hit': hit_b, 'model_b_w_hit': wh_b, 'model_b_corr': corr_b,
    }]).to_csv(summary, index=False, encoding='utf-8-sig')
    print(f'[validate] -> {args.out} | {summary}')


if __name__ == '__main__':
    main()
