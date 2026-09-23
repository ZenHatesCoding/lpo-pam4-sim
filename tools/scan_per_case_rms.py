# -*- coding: utf-8 -*-
"""per-case 细粒度 RMS 扫描：每个用例单独扫 target_rms，找该用例自己的最优值。

用户要求：
  - 每个用例的 gain 分开优化，RMS 扫细一点
  - 每个用例可以不一样，不求几何平均
  - gain 不走梯度下降，但可以给每个用例单独优化

策略：
  - 对每个用例，在种子 FFE/CTLE 配置下，细扫 target_rms（0.06~0.22 V，步长 0.005）
  - 每个 target_rms：解析求解 gain → 跑全链路仿真 → 记录 BER
  - 找每个用例 BER 最低的 target_rms
  - 输出 result/per_case_target_rms.json + result/per_case_rms_scan.csv

注意：gain 的扫描是独立的逻辑，不属于代理模型/梯度下降。FFE/CTLE 由后续梯度下降处理。
"""
import os, sys, copy, time, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['NUMEXPR_NUM_THREADS'] = '1'

import numpy as np
import pandas as pd
import utils_config
import ddps_optimizer as D
from ddps_cases import ENV_CASES, apply_env_to_config
from tx_channel_extract import extract_tx_features
from main import run_sim

SCAN_SYMBOLS = 262144
SIM_SEEDS = (42, 43, 44)

# 细粒度 RMS 扫描范围
RMS_LO = 0.06
RMS_HI = 0.22
RMS_STEP = 0.005
TARGET_RMS_GRID = np.round(np.arange(RMS_LO, RMS_HI + RMS_STEP / 2, RMS_STEP), 4)


def _eval_ber(cfg, taps, gdc, gdc2, gain, num_symbols, sim_seeds):
    """跑全链路仿真拿 BER_MLSE（3 seed log10 均值）。"""
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


def _measure_rms(cfg, taps, gdc, gdc2, gain):
    """发端 RMS（只跑 Tx 前端，不产生 BER）。"""
    cfgp = copy.deepcopy(cfg)
    cfgp['tx']['ctle_g_dc_db'] = float(gdc)
    cfgp['tx']['ctle_g_dc2_db'] = float(gdc2)
    cfgp['channel']['driver_gain'] = float(gain)
    try:
        _, drms = extract_tx_features(cfgp, custom_tx_taps=taps, num_taps=7)
        return float(drms)
    except Exception:
        return 0.0


def _solve_gain_for_target(cfg, taps, gdc, gdc2, target_rms, gain_ref):
    """解析求 gain 使 drive_rms = target_rms。"""
    rms_ref = _measure_rms(cfg, taps, gdc, gdc2, gain_ref)
    if rms_ref <= 1e-9:
        return gain_ref
    g_new = gain_ref * (target_rms / rms_ref)
    return float(np.clip(g_new, D.GAIN_MIN, D.GAIN_MAX))


def _worker(args):
    (env_name, cfg_env, target_rms) = args
    taps = D.SEED_TAPS.copy()
    gdc = D.SEED_GDC
    gdc2 = D.SEED_GDC2
    gain_ref = D.DRIVER_GAIN_NOMINAL
    # 解析求 gain
    gain = _solve_gain_for_target(cfg_env, taps, gdc, gdc2, target_rms, gain_ref)
    # 实测 drive_rms（验证）
    rms_actual = _measure_rms(cfg_env, taps, gdc, gdc2, gain)
    # BER
    lb = _eval_ber(cfg_env, taps, gdc, gdc2, gain, SCAN_SYMBOLS, SIM_SEEDS)
    return {
        'env': env_name,
        'target_rms': target_rms,
        'gain': gain,
        'gain_ratio': gain / D.DRIVER_GAIN_NOMINAL,
        'drive_rms_actual': rms_actual,
        'log10_ber': lb,
        'ber': float(10.0 ** lb),
    }


def main(jobs=12):
    utils_config.ensure_config()
    BASE = utils_config.load_config('config.xlsx')
    BASE['system']['enable_eye_plot'] = False
    BASE['system']['enable_spectrum_plot'] = False

    envs = ENV_CASES
    tasks = []
    for env in envs:
        cfg_env = apply_env_to_config(BASE, env)
        for trms in TARGET_RMS_GRID:
            tasks.append((env['name'], cfg_env, float(trms)))
    n_pts = len(tasks)
    print(f"[per-case RMS scan] {n_pts} points ({len(envs)} envs x {len(TARGET_RMS_GRID)} rms), "
          f"{SCAN_SYMBOLS} sym x {len(SIM_SEEDS)} seeds, jobs={jobs}")
    print(f"  RMS range: {RMS_LO}~{RMS_HI} V, step={RMS_STEP}")
    t0 = time.time()
    if jobs and jobs > 1:
        import multiprocessing as mp
        rows = []
        with mp.Pool(processes=int(jobs)) as pool:
            for k, r in enumerate(pool.imap(_worker, tasks, chunksize=1)):
                rows.append(r)
                if (k + 1) % 100 == 0 or (k + 1) == n_pts:
                    print(f"    done {k+1}/{n_pts}  ({time.time()-t0:.0f}s)")
    else:
        rows = []
        for k, tsk in enumerate(tasks):
            rows.append(_worker(tsk))
            if (k + 1) % 50 == 0:
                print(f"    done {k+1}/{n_pts}  ({time.time()-t0:.0f}s)")

    df = pd.DataFrame(rows)
    os.makedirs('result', exist_ok=True)
    csv_out = 'result/per_case_rms_scan.csv'
    df.to_csv(csv_out, index=False)

    # 每用例最优 target_rms
    per_case = {}
    print(f"\n{'env':28s} {'best_rms':>9s} {'best_gain':>9s} {'best_lb':>9s} "
          f"{'best_ber':>10s} {'seed_lb':>9s} {'d_dex':>7s}")
    print('-' * 92)
    for env in envs:
        sub = df[df['env'] == env['name']]
        ib = int(sub['log10_ber'].idxmin())
        b = sub.loc[ib]
        # 种子 BER（target_rms 对应 gain_ratio=1.0 附近）
        seed_row = sub.iloc[(sub['gain_ratio'] - 1.0).abs().argmin()]
        seed_lb = float(seed_row['log10_ber'])
        per_case[env['name']] = {
            'target_rms': float(b['target_rms']),
            'gain_ratio': float(b['gain_ratio']),
            'gain': float(b['gain']),
            'best_ber': float(b['ber']),
            'best_log10_ber': float(b['log10_ber']),
            'seed_log10_ber': seed_lb,
        }
        print(f"{env['name']:28s} {b['target_rms']:9.4f} {b['gain_ratio']:9.3f} "
              f"{b['log10_ber']:9.4f} {b['ber']:10.3e} {seed_lb:9.4f} "
              f"{b['log10_ber']-seed_lb:+7.3f}")

    json_out = 'result/per_case_target_rms.json'
    with open(json_out, 'w', encoding='utf-8') as f:
        json.dump(per_case, f, indent=2, ensure_ascii=False)
    print(f"\n[scan] saved {csv_out}")
    print(f"[scan] saved {json_out}  ({time.time()-t0:.0f}s total)")
    print(f"\nper-case target_rms values:")
    for env_name, v in per_case.items():
        print(f"  {env_name:28s} target_rms = {v['target_rms']:.4f} V  "
              f"(gain x{v['gain_ratio']:.3f})")


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--jobs', type=int, default=12)
    a = ap.parse_args()
    main(jobs=a.jobs)
