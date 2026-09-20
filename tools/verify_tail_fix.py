"""验证尾缘截断修正：修复后 run_sim 的 BER 是否回归真实稳态值。

跑几个点（种子点 vs 更差点），不同块长，看修复后 BER 是否：
- 种子点：0 错误（真实 BER 远低于 1e-5）；
- 更差点：有可分辨错误；
- 同一点不同块长：错误密度一致（不再随块长 -0.3 dex）。

用法：python tools/verify_tail_fix.py
"""
import os
import sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from utils_config import load_config
from main import run_sim

SEED_TAPS = np.array([-0.034, -0.2987, 0.6091, 0.0, 0.0582])
SEEDS = (42, 43, 44)


def eval_point(config, taps, gdc, gdc2, gain, num_symbols, label):
    lbs = []
    for s in SEEDS:
        config['system']['seed'] = int(s)
        config['channel']['seed'] = int(s) + 7919
        config['system']['num_symbols'] = num_symbols
        config['tx']['ctle_g_dc_db'] = float(gdc)
        config['tx']['ctle_g_dc2_db'] = float(gdc2)
        config['channel']['driver_gain'] = float(gain)
        _, mlse_ber = run_sim(config, custom_tx_taps=taps, plot_eyes=False, output_dir=None)
        lbs.append(float(np.log10(max(mlse_ber, 1e-9))))
    mean_lb = float(np.mean(lbs))
    print(f"  {label:28s} n={num_symbols:>9d}  log10BER={mean_lb:+.3f}  BER={10**mean_lb:.3e}  "
          f"(各seed log10: {[f'{x:.3f}' for x in lbs]})", flush=True)
    return mean_lb


def main():
    config = load_config('config.xlsx')
    config['system']['enable_eye_plot'] = False
    config['system']['enable_spectrum_plot'] = False
    # 基线种子点（Base per-case 最优 gain）+ 一个更差点
    points = [
        ('seed (gain 0.1381)', 6.0, 2.0, 0.1381),
        ('gain x1.26 (0.174)', 6.0, 2.0, 0.1740),
        ('gain x0.20 (0.0276)', 6.0, 2.0, 0.0276),
        ('gDC=12 (过均衡)', 12.0, 2.0, 0.1381),
    ]
    for num_symbols in (524288, 1048576):
        print(f"\n=== num_symbols={num_symbols} ===", flush=True)
        for label, gdc, gdc2, gain in points:
            eval_point(config, SEED_TAPS, gdc, gdc2, gain, num_symbols, label)


if __name__ == '__main__':
    main()
