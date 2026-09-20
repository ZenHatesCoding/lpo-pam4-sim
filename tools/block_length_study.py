# -*- coding: utf-8 -*-
"""tools/block_length_study.py — BER 估计精度（块长）研究，产出交付件图 5 的数据。

在基线最优工作点（per-case 最优 gain + 形状种子）上用多个仿真实例种子测不同块长下的
log10 BER，并回答：
    "在给定块长下，1e-6 量级的真实 BER 能否被稳定测量？"
    "相邻块长的 BER 是否还有系统性漂移（此前观察到的每翻倍约 -0.3 dex）？"

输出：result/ddps_v6_2_block_length.csv
  （num_symbols / 错误数 / log10 BER 均值 / 跨种子标准差 / 等效 BER / 参考点位移 dex）

用法：
    python tools/block_length_study.py --num-symbols 262144,524288,1048576,2097152,4194304 \
        --sim-seeds 42,43,44 --env Base_IL10x10 --gain 0.138 \
        --ref-gdc 0.0 --out result/ddps_v6_2_block_length.csv
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
    ap.add_argument('--num-symbols', default='262144,524288,1048576,2097152,4194304')
    ap.add_argument('--sim-seeds', default='42,43,44')
    ap.add_argument('--gain', type=float, default=float(D.SEED_GAIN),
                    help='最优工作点 gain（默认取 SEED_GAIN；per-case 扫描最优 gain 见 '
                         'result/per_case_target_rms.json）')
    ap.add_argument('--ref-gdc', type=float, default=0.0,
                    help='参考退化点（CTLE gDC, dB）；用于"可分辨性"一列')
    ap.add_argument('--out', default='result/ddps_v6_2_block_length.csv')
    args = ap.parse_args()

    seeds = tuple(int(s) for s in args.sim_seeds.split(','))
    cfg0 = C.apply_env_to_config(load_config('config.xlsx'), args.env)
    rows = []
    for nsym in [int(s) for s in args.num_symbols.split(',')]:
        cfg = {k: (dict(v) if isinstance(v, dict) else v) for k, v in cfg0.items()}
        cfg['system']['num_symbols'] = nsym
        D.set_sim_seeds(seeds)
        lb_seed, ber_seed = D._physical_eval(cfg, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2,
                                             args.gain)
        lb_ref, ber_ref = D._physical_eval(cfg, D.SEED_TAPS.copy(), args.ref_gdc, D.SEED_GDC2,
                                           args.gain)
        lbs, bers = [], []
        for s in seeds:
            D.set_sim_seeds((s,))
            lb_s, ber_s = D._physical_eval(cfg, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2,
                                           args.gain)
            lbs.append(lb_s)
            bers.append(ber_s)
        D.set_sim_seeds(seeds)
        # 原始错误数：run_sim 0 错误时返回 1/(2·min_len) 伪计数，b·min_len≈0.5；
        # 1 错误≈1.0、k 错误≈k。sync_delay 会随块长漂移 ±1~2，使 0.5 略高于/低于 0.5，
        # 因此用 0.75 阈值把“0 错误伪计数”与“1 错误”分开，而不是直接 round。
        min_len = max(1, nsym - 10114)  # ≈ 有效稳态符号数（10000 训练头 + 114 尾缘截断）
        def _nerr(b):
            raw = b * min_len
            return 0 if raw < 0.75 else int(round(raw))
        n_seed = _nerr(ber_seed)
        n_ref = _nerr(ber_ref)
        n_per = [_nerr(b) for b in bers]
        rows.append({
            'env': args.env, 'num_symbols': nsym, 'n_seeds': len(seeds),
            'seed_gain': args.gain,
            'seed_n_errors': n_seed, 'seed_ber': ber_seed,
            'seed_log10_ber_mean': float(np.mean(lbs)),
            'seed_log10_ber_std': float(np.std(lbs)),
            'per_seed_n_errors': n_per,
            'ref_gdc_db': args.ref_gdc, 'ref_n_errors': n_ref, 'ref_ber': ber_ref,
            'ref_delta_dex': float(lb_ref - lb_seed),
        })
        print(f'[blocklen] {nsym:>7d} sym: n_errors={n_per} mean={np.mean(lbs):+.3f} '
              f'std={np.std(lbs):.3f} | ref(gDC={args.ref_gdc:g}) {n_ref} err '
              f'delta={lb_ref - lb_seed:+.3f} dex', flush=True)
    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    pd.DataFrame(rows).to_csv(args.out, index=False, encoding='utf-8-sig')
    print(f'[blocklen] -> {args.out}')


if __name__ == '__main__':
    main()
