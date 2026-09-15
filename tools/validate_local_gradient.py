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

# 7 个自由变量：4 个 5-tap FFE 旁瓣 + CTLE 两级 + driver 增益（对数倍率）
DIM_NAMES = ([f'FFE_tap{i}' for i in range(D.N_SIDE)]
             + ['CTLE_gDC', 'CTLE_gDC2', 'driver_gain_u'])
DIM_UNITS = ['tap'] * D.N_SIDE + ['dB', 'dB', 'dex']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model-dir', default='models/ddps_v4')
    ap.add_argument('--env', default='Base_IL10x10')
    ap.add_argument('--num-symbols', type=int, default=262144)
    ap.add_argument('--sim-seeds', default='42,43,44')
    ap.add_argument('--out', default='result/ddps_v4_local_gradient.csv')
    ap.add_argument('--steps', default='0.05,0.05,0.05,0.05,1.0,1.0',
                    help='各轴中心差分步长（FFE 4 个、CTLE 2 个），逗号分隔；6 维 v5 模型')
    ap.add_argument('--seed-config', default=None,
                    help='BO 寻优种子点 JSON（覆盖 SEED_TAPS/SEED_GDC/SEED_GDC2）')
    args = ap.parse_args()

    if args.seed_config:
        import json as _json
        with open(args.seed_config, 'r', encoding='utf-8') as _f:
            _sc = _json.load(_f)
        _pp = np.array(_sc['best_pre_post'], dtype=float)
        _ffe_pre = int(D.FFE_PRE)
        D.SEED_TAPS = D.construct_taps(_pp, _ffe_pre).copy()
        D.SEED_GDC = float(_sc['best_gdc'])
        D.SEED_GDC2 = float(_sc['best_gdc2'])
        print(f"[gradient] 种子点覆盖: taps={np.round(D.SEED_TAPS,4)} gDC={D.SEED_GDC:.2f} gDC2={D.SEED_GDC2:.2f}")

    seeds = tuple(int(s) for s in args.sim_seeds.split(','))
    D.set_sim_seeds(seeds)
    steps = np.array([float(s) for s in args.steps.split(',')])

    cfg = C.apply_env_to_config(load_config('config.xlsx'), args.env)
    cfg['system']['num_symbols'] = int(args.num_symbols)
    ffe_pre = D._ffe_pre(cfg)
    model_a, model_b = load_models(args.model_dir)

    # v5: 6 维 x_shape = [4 旁瓣, gDC, gDC2]；gain 用种子值（不在 shape 里）
    seed_pre_post = np.concatenate([D.SEED_TAPS[:ffe_pre], D.SEED_TAPS[ffe_pre + 1:]])
    x0 = np.concatenate([seed_pre_post, [D.SEED_GDC, D.SEED_GDC2]])
    gain0 = float(D.SEED_GAIN)
    n_dim = len(x0)

    def ev(x):
        taps = D.construct_taps(x[:D.N_SIDE], ffe_pre)
        return D._physical_eval(cfg, taps, float(x[D.N_SIDE]), float(x[D.N_SIDE + 1]), gain0)

    lb0, ber0 = ev(x0)
    # v6: A 吃探针 8 维，梯度走链式法则；B 吃参数 7 维（x_shape+drive_rms）
    if hasattr(D, '_grad_a_chain'):
        g_a = D._grad_a_chain(model_a, cfg, x0, gain0, ffe_pre, eps=0.01)
        rms0 = D._measure_drive_rms(cfg, D.construct_taps(x0[:D.N_SIDE], ffe_pre),
                                     float(x0[D.N_SIDE]), float(x0[D.N_SIDE+1]), gain0)
        g_b = np.asarray(model_b.grad(
            np.concatenate([x0, [rms0]]).reshape(1, -1))[0], dtype=float) \
            if hasattr(model_b, 'grad') else np.full(n_dim, np.nan)
        g_b = g_b[:n_dim]  # 只取前 6 维（x_shape）
    else:
        g_a = D._grad_a(model_a, x0)
        g_b = np.asarray(model_b.grad(x0.reshape(1, -1))[0], dtype=float) \
            if hasattr(model_b, 'grad') else np.full(n_dim, np.nan)

    print(f'[validate] env={args.env} | {args.num_symbols} symbols x seeds{seeds}')
    print(f'[validate] seed log10BER={lb0:+.4f} (BER={ber0:.4e})')

    rows = []
    for i in range(n_dim):
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
