# -*- coding: utf-8 -*-
"""tools/block_length_study.py — BER 估计精度（块长）研究，产出交付件图 5 的数据。

在基线种子点上用多个仿真实例种子测不同块长下的 log10 BER，并回答：
    "一个真实改善（本例取 CTLE gDC = -5 dB）在给定块长下能不能被分辨出来？"

输出：result/ddps_v4_block_length.csv（num_symbols / 均值 / 跨种子标准差 / 参考点位移 dex）

用法：
    python tools/block_length_study.py --num-symbols 65536,131072,262144,524288 \
        --sim-seeds 42,43,44,44,46 --env Base_IL10x10 --ref-gdc -5.0 \
        --out result/ddps_v4_block_length.csv
"""
import argparse
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
    ap.add_argument('--env', default='Base_IL10x10')
    ap.add_argument('--num-symbols', default='65536,131072,262144,524288')
    ap.add_argument('--sim-seeds', default='42,43,44,45,46')
    ap.add_argument('--ref-gdc', type=float, default=-5.0,
                    help='参考改善点（CTLE gDC, dB）；用于“可分辨性”一列')
    ap.add_argument('--out', default='result/ddps_v4_block_length.csv')
    args = ap.parse_args()

    seeds = tuple(int(s) for s in args.sim_seeds.split(','))
    cfg0 = C.apply_env_to_config(load_config('config.xlsx'), args.env)
    rows = []
    for nsym in [int(s) for s in args.num_symbols.split(',')]:
        cfg = {k: (dict(v) if isinstance(v, dict) else v) for k, v in cfg0.items()}
        cfg['system']['num_symbols'] = nsym
        D.set_sim_seeds(seeds)
        lb_seed, ber_seed = D._physical_eval(cfg, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2,
                                             D.SEED_GAIN)
        lb_ref, ber_ref = D._physical_eval(cfg, D.SEED_TAPS.copy(), args.ref_gdc, D.SEED_GDC2,
                                           D.SEED_GAIN)
        lbs = []
        for s in seeds:
            D.set_sim_seeds((s,))
            lb_s, _ = D._physical_eval(cfg, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2,
                                       D.SEED_GAIN)
            lbs.append(lb_s)
        D.set_sim_seeds(seeds)
        rows.append({
            'env': args.env, 'num_symbols': nsym, 'n_seeds': len(seeds),
            'log10_ber_mean': float(np.mean(lbs)), 'log10_ber_std': float(np.std(lbs)),
            'seed_log10_ber_mean': lb_seed, 'seed_ber': ber_seed,
            'ref_gdc_db': args.ref_gdc, 'ref_log10_ber': lb_ref, 'ref_ber': ber_ref,
            'ref_delta_dex': float(lb_ref - lb_seed),
        })
        print(f'[blocklen] {nsym:>7d} symbols: mean={np.mean(lbs):+.3f} std={np.std(lbs):.3f} '
              f'| ref(gDC={args.ref_gdc:g}) delta={lb_ref - lb_seed:+.3f} dex')
    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    pd.DataFrame(rows).to_csv(args.out, index=False, encoding='utf-8-sig')
    print(f'[blocklen] -> {args.out}')


if __name__ == '__main__':
    main()
