# -*- coding: utf-8 -*-
"""tools/validate_local_gradient.py — Model A 的**局部方向**实测标定（离线验证，不参与训练）。

做一件模型指标表看不出来的事：在**真实链路**上，对种子工作点沿 8 个搜索轴
（5 个 Tx FFE 抽头 + gDC + gDC2 + u_gain）做中心差分，测出真实 log10 BER 的局部斜率，
再与 Model A 的解析梯度逐轴对照，回答：

    "这个方向代理给出来的方向，到底对不对？"

指标：
    hit   —— 8 轴方向命中率（符号一致）
    w_hit —— 按 |实测斜率| 加权的方向命中率（陡的轴权重更大）
    corr  —— 代理梯度与实测梯度的相关系数（量级是否同序）

Model B 不在线使用，本工具只标定 Model A：形状 7 维走 `_grad_a_chain` 链式法则，
gain 维走 `_analytic_gain_grad` 解析梯度（与在线调优同一条路径）。

用法（2^18 小点数低 SNR，AGENTS.md「开发方式」）：
    python tools/validate_local_gradient.py --model-dir models/ddps \
        --env Base_IL10x10 --num-symbols 262144 --sim-seeds 42 \
        --seed-config result/seed_config_bad_1e4.json \
        --out result/ddps_local_gradient.csv
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ddps_optimizer as D            # noqa: E402
import ddps_cases as C                # noqa: E402
from utils_config import load_config  # noqa: E402
from train_surrogates import load_models  # noqa: E402

# 8 个搜索维：5 个自由 FFE 抽头 + CTLE 两级 + driver 增益（对数倍率 u_gain）
DIM_NAMES = ([f'FFE_tap{i}' for i in range(D.N_TAP)]
             + ['CTLE_gDC', 'CTLE_gDC2', 'driver_gain_u'])
DIM_UNITS = ['tap'] * D.N_TAP + ['dB', 'dB', 'dex']


def main():
    ap = argparse.ArgumentParser(
        description='Model A 局部方向实测标定：真实链路中心差分 vs 代理解析梯度')
    ap.add_argument('--model-dir', default='models/ddps')
    ap.add_argument('--env', default='Base_IL10x10')
    ap.add_argument('--num-symbols', type=int, default=262144,
                    help='每点符号数；只允许 2^18 小点数低 SNR（AGENTS.md 开发方式）')
    ap.add_argument('--tx-noise-snr-db', type=float, default=0.0)
    ap.add_argument('--sim-seeds', default='42')
    ap.add_argument('--out', default='result/ddps_local_gradient.csv')
    ap.add_argument('--steps', default=None,
                    help='各轴中心差分步长（8 个，顺序 = [5 抽头, gDC, gDC2, u_gain]），'
                         '逗号分隔；缺省用 ddps_optimizer.EPS_VEC')
    ap.add_argument('--seed-config', default=None,
                    help='次优起点 seed_config JSON（覆盖 taps/gDC/gDC2/gain）')
    args = ap.parse_args()

    if args.seed_config:
        D.apply_seed_config(args.seed_config)
        print(f"[gradient] 种子点覆盖: taps={np.round(D.SEED_TAPS, 4)} "
              f"gDC={D.SEED_GDC:.2f} gDC2={D.SEED_GDC2:.2f} u_gain={D.SEED_GAIN_U:+.3f}")

    seeds = tuple(int(s) for s in args.sim_seeds.split(',') if s.strip())
    D.set_sim_seeds(seeds)
    steps = (D.EPS_VEC.copy() if args.steps is None
             else np.array([float(s) for s in args.steps.split(',') if s.strip()]))
    if len(steps) != D.N_DIM:
        raise SystemExit(f'--steps 需要 {D.N_DIM} 个值（顺序 = [5 抽头, gDC, gDC2, u_gain]），'
                         f'收到 {len(steps)} 个')

    cfg = C.apply_env_to_config(load_config('config.xlsx'), args.env)
    cfg['system']['num_symbols'] = int(args.num_symbols)
    cfg['system']['tx_noise_snr_db'] = float(args.tx_noise_snr_db)
    # Model B 不在线使用：load_models 返回 (A, B)，这里只取 Model A。
    model_a = load_models(args.model_dir)[0]

    # 8 维搜索向量，gain 用 u_gain 表示
    x0 = np.concatenate([D.SEED_TAPS.copy(),
                         [D.SEED_GDC, D.SEED_GDC2, D.u_from_gain(D.SEED_GAIN)]])
    n_dim = D.N_DIM

    def ev(x):
        return D._physical_eval(cfg, D.taps_of(x), float(x[D.N_TAP]),
                                float(x[D.N_TAP + 1]), D.gain_from_u(float(x[D.N_TAP + 2])))

    lb0, ber0 = ev(x0)

    # 代理梯度：形状 7 维走 _grad_a_chain（链式法则），gain 维走 _analytic_gain_grad（解析、零微扰）
    g_shape, _probe_iter = D._grad_a_chain(model_a, cfg, x0)
    g_a = np.asarray(g_shape, dtype=float).copy()
    probe0 = D._probe_features(cfg, D.taps_of(x0), float(x0[D.N_TAP]),
                               float(x0[D.N_TAP + 1]), D.gain_from_u(float(x0[D.N_TAP + 2])))
    g_a[D.N_TAP + 2] = D._analytic_gain_grad(model_a, probe0)

    print(f'[validate] env={args.env} | {args.num_symbols} symbols x seeds{seeds} '
          f'| snr_db={args.tx_noise_snr_db}')
    print(f'[validate] seed log10BER={lb0:+.4f} (BER={ber0:.4e})')

    rows = []
    for i in range(n_dim):
        s = float(steps[i])
        xp, xm = x0.copy(), x0.copy()
        xp[i] += s
        xm[i] -= s
        lp, _bp = ev(xp)
        lm, _bm = ev(xm)
        real = (lp - lm) / (2.0 * s)
        rows.append({
            'dim': DIM_NAMES[i], 'unit': DIM_UNITS[i], 'step': s,
            'real_log10_plus': lp, 'real_log10_minus': lm,
            'real_d_plus': lp - lb0, 'real_d_minus': lm - lb0,
            'real_slope': real,
            'model_a_slope': float(g_a[i]),
            'sign_match_a': int(np.sign(g_a[i]) == np.sign(real)),
            'ratio_a': float(g_a[i] / real) if real != 0 else np.nan,
        })
        print(f'   {DIM_NAMES[i]:14s} step={s:+.3f} real d(+){lp - lb0:+.3f} d(-){lm - lb0:+.3f} '
              f'slope={real:+.3f} | A={g_a[i]:+.3f}')

    real_g = np.array([r['real_slope'] for r in rows])
    w = np.abs(real_g) / np.abs(real_g).sum()

    hit_a = float((np.sign(g_a) == np.sign(real_g)).mean())
    wh_a = float((w * (np.sign(g_a) == np.sign(real_g))).sum())
    corr_a = (float(np.corrcoef(g_a, real_g)[0, 1]) if np.std(g_a) > 0 else float('nan'))
    print(f'[validate] Model A: hit={hit_a:.2f} w_hit={wh_a:.2f} corr={corr_a:+.2f}')

    import pandas as pd
    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    pd.DataFrame(rows).to_csv(args.out, index=False, encoding='utf-8-sig')
    summary = os.path.splitext(args.out)[0] + '_summary.csv'
    pd.DataFrame([{
        'env': args.env, 'num_symbols': args.num_symbols, 'sim_seeds': args.sim_seeds,
        'tx_noise_snr_db': args.tx_noise_snr_db,
        'seed_log10_ber': lb0, 'seed_ber': ber0,
        'model_a_hit': hit_a, 'model_a_w_hit': wh_a, 'model_a_corr': corr_a,
    }]).to_csv(summary, index=False, encoding='utf-8-sig')
    print(f'[validate] -> {args.out} | {summary}')


if __name__ == '__main__':
    main()
