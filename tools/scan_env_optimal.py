# -*- coding: utf-8 -*-
"""全环境扫描：标定每个环境最优 (gain, gDC, gDC2) 与对应的 drive_rms。

目的（按用户要求）：先扫描看最优性能，再据此设计 gain 维的发端 RMS 目标值。

策略：
  - 用 65536 符号 × 3 seed 做快速筛选（比 262144 快 4 倍；docs 已验证块长只影响
    绝对 BER 的系统性变化，不改变最优点位置与排序）。
  - 网格：gain ratio ×5（0.4,0.6,0.8,1.0,1.3）、gDC ×3（-3,0,+3）、gDC2 ×3（-3,0,+3）= 45 点/环境。
  - 15 环境，多进程并行。
  - 输出 result/env_optimal_scan.csv：每个环境的全部网格点 + 最优行标注。
  - 最后用 262144 协议复核每个环境最优点，得到"真"最优 RMS。
"""
import os, sys, copy, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['NUMEXPR_NUM_THREADS'] = '1'

import numpy as np
import pandas as pd
import create_config, utils_config
import ddps_optimizer as D
from ddps_cases import ENV_CASES, apply_env_to_config
from tx_channel_extract import extract_tx_features
from main import run_sim

if not os.path.exists('config.xlsx'):
    create_config.generate_config()
BASE = utils_config.load_config('config.xlsx')
BASE['system']['enable_eye_plot'] = False
BASE['system']['enable_spectrum_plot'] = False

SCAN_SYMBOLS = 65536
SIM_SEEDS = (42, 43, 44)
FFE_PRE = int(BASE['tx'].get('ffe_pre', D.FFE_PRE))

RATIOS = [0.40, 0.60, 0.80, 1.00, 1.30]
GDCS = [-3.0, 0.0, 3.0]
GDC2S = [-3.0, 0.0, 3.0]


def _eval(cfg, taps, gdc, gdc2, gain, num_symbols, sim_seeds):
    cfg = copy.deepcopy(cfg)
    cfg['tx']['ctle_g_dc_db'] = float(gdc)
    cfg['tx']['ctle_g_dc2_db'] = float(gdc2)
    cfg['channel']['driver_gain'] = float(gain)
    cfg['system']['num_symbols'] = int(num_symbols)
    lbs = []
    for s in sim_seeds:
        cfg['system']['seed'] = int(s)
        cfg['channel']['seed'] = int(s) + 7919
        try:
            _, mlse_ber = run_sim(cfg, custom_tx_taps=taps, plot_eyes=False, output_dir=None)
        except Exception:
            mlse_ber = 1.0
        mlse_ber = float(np.clip(mlse_ber, 1e-8, 1.0))
        lbs.append(float(np.log10(mlse_ber)))
    return float(np.mean(lbs))


def _worker(args):
    (env_name, cfg_env, ratio, gdc, gdc2) = args
    gain = D.DRIVER_GAIN_NOMINAL * float(ratio)
    taps = D.SEED_TAPS.copy()
    lb = _eval(cfg_env, taps, gdc, gdc2, gain, SCAN_SYMBOLS, SIM_SEEDS)
    # drive_rms（发端 MZM 输入 RMS）
    cfgp = copy.deepcopy(cfg_env)
    cfgp['tx']['ctle_g_dc_db'] = float(gdc)
    cfgp['tx']['ctle_g_dc2_db'] = float(gdc2)
    cfgp['channel']['driver_gain'] = float(gain)
    cfgp['system']['num_symbols'] = SCAN_SYMBOLS
    try:
        _, drms = extract_tx_features(cfgp, custom_tx_taps=taps, num_taps=7)
    except Exception:
        drms = np.nan
    return {
        'env': env_name,
        'ratio': ratio, 'gain': gain,
        'gdc': gdc, 'gdc2': gdc2,
        'log10_ber': lb, 'ber': float(10.0 ** lb),
        'drive_rms': float(drms),
        'symbols': SCAN_SYMBOLS,
    }


def main(jobs=8):
    envs = ENV_CASES
    tasks = []
    for env in envs:
        cfg_env = apply_env_to_config(BASE, env)
        for r in RATIOS:
            for g1 in GDCS:
                for g2 in GDC2S:
                    tasks.append((env['name'], cfg_env, r, g1, g2))
    print(f"[scan] {len(tasks)} points across {len(envs)} envs, "
          f"{SCAN_SYMBOLS} sym x {len(SIM_SEEDS)} seeds, jobs={jobs}")
    t0 = time.time()
    if jobs and jobs > 1:
        import multiprocessing as mp
        rows = []
        with mp.Pool(processes=int(jobs)) as pool:
            for k, r in enumerate(pool.imap(_worker, tasks, chunksize=1)):
                rows.append(r)
                if (k + 1) % 100 == 0 or (k + 1) == len(tasks):
                    print(f"    done {k+1}/{len(tasks)}  ({time.time()-t0:.0f}s)")
    else:
        rows = []
        for k, tsk in enumerate(tasks):
            rows.append(_worker(tsk))
            if (k + 1) % 50 == 0:
                print(f"    done {k+1}/{len(tasks)}  ({time.time()-t0:.0f}s)")
    df = pd.DataFrame(rows)
    os.makedirs('result', exist_ok=True)
    out = 'result/env_optimal_scan.csv'
    df.to_csv(out, index=False)
    print(f"\n[scan] saved {out}  ({time.time()-t0:.0f}s)\n")
    # 每环境最优点汇总
    print(f"{'env':28s} {'best_ratio':>10s} {'best_gdc':>8s} {'best_gdc2':>9s} "
          f"{'best_lb':>9s} {'best_ber':>10s} {'drive_rms':>9s} {'seed_lb':>9s}")
    print('-' * 96)
    for env in envs:
        sub = df[df['env'] == env['name']]
        ib = int(sub['log10_ber'].idxmin())
        b = sub.loc[ib]
        seed_lb = float(sub[(sub['ratio'] == 1.0) & (sub['gdc'] == 0.0) & (sub['gdc2'] == 0.0)]['log10_ber'].iloc[0])
        print(f"{env['name']:28s} {b['ratio']:10.2f} {b['gdc']:8.1f} {b['gdc2']:9.1f} "
              f"{b['log10_ber']:9.4f} {b['ber']:10.3e} {b['drive_rms']:9.5f} {seed_lb:9.4f}")
    # 看最优 RMS 的分布（用于设计统一的 RMS 目标）
    print("\n[optimal drive_rms distribution across envs]")
    for env in envs:
        sub = df[df['env'] == env['name']]
        ib = int(sub['log10_ber'].idxmin())
        print(f"  {env['name']:28s} optimal drive_rms = {sub.loc[ib,'drive_rms']:.5f} V  "
              f"(ratio {sub.loc[ib,'ratio']:.2f})")


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--jobs', type=int, default=8)
    a = ap.parse_args()
    main(jobs=a.jobs)
