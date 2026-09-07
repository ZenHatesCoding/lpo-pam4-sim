import os
# Must set these BEFORE importing numpy/scipy
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['VECLIB_MAXIMUM_THREADS'] = '1'
os.environ['NUMEXPR_NUM_THREADS'] = '1'

# ============================================================================
# DDPS v2 数据集生成器（环境锚定邻域采样）
#
# v2 相对 v1 的关键修正：
#   1. FFE 参数化全局统一：主抽头 = 1 - Σ|旁瓣|（与 Stage-2 下降空间一致），
#      不再使用 v1"主抽头恒置 1.0"的全优化域采样（该约定导致训练域与下降域错配）。
#   2. 数据 = "基准环境邻域密集采样 + 各应力环境邻域稀疏锚点"，覆盖信任域
#      (FFE ±TRUST_FFE / CTLE ±TRUST_CTLE)，使代理在 Stage-2 真正活动的区域有支撑。
#   3. 每行记录：x 空间坐标(10D)、9-tap FFE、CTLE、真实 MLSE BER 与 Tx-FIR 探针。
#
# 输出列:
#   sample_id, env, il_db, cd_ps_nm, dgd_ps, pol_deg,
#   x_0..x_9 (实际生效的 10D 搜索空间坐标),
#   ffe_tap_0..ffe_tap_8, ctle_dc, ctle_dc2,
#   mlse_ber, log10_ber_mlse, tx_fir_0..tx_fir_6
# ============================================================================
import numpy as np
import pandas as pd
from datetime import datetime
from scipy.stats import qmc
import create_config
import ddps_optimizer as D          # 统一参数化 & 种子 & 信任域
from ddps_cases import ENV_CASES, BASE_ENV, apply_env_to_config
from utils_config import load_config
from main import run_sim
from tx_channel_extract import extract_tx_s21

BASE_SPREAD_FFE = D.TRUST_FFE      # ±0.10
BASE_SPREAD_CTLE = D.TRUST_CTLE    # ±3.0 dB


def _taps_without_center(taps, ffe_pre):
    return np.concatenate([taps[:ffe_pre], taps[ffe_pre + 1:]])


def _sample_point(u, seed_pre_post, ffe_pre):
    """u: 10D LHS [0,1]^10 -> (pre_post_raw, gdc, gdc2)。"""
    pre_post = seed_pre_post + (u[:8] * 2 - 1.0) * BASE_SPREAD_FFE
    gdc = float(np.clip(D.SEED_GDC + (u[8] * 2 - 1.0) * BASE_SPREAD_CTLE,
                        D.CTLE_GDC_MIN, D.CTLE_GDC_MAX))
    gdc2 = float(np.clip(D.SEED_GDC2 + (u[9] * 2 - 1.0) * BASE_SPREAD_CTLE,
                         D.CTLE_GDC2_MIN, D.CTLE_GDC2_MAX))
    return pre_post, gdc, gdc2


def _worker_task(args):
    i, env_name, cfg_dict, num_symbols, ffe_pre, seed_pre_post, u, is_seed = args
    import copy
    cfg = copy.deepcopy(cfg_dict)
    cfg['system']['num_symbols'] = int(num_symbols)
    if is_seed:
        gdc, gdc2 = D.SEED_GDC, D.SEED_GDC2
        taps = D.SEED_TAPS.copy()
        x_eff = np.concatenate([_taps_without_center(taps, ffe_pre), [gdc, gdc2]])
    else:
        pre_post, gdc, gdc2 = _sample_point(u, seed_pre_post, ffe_pre)
        taps = D.construct_9tap(pre_post, ffe_pre)
        x_eff = np.concatenate([_taps_without_center(taps, ffe_pre), [gdc, gdc2]])

    cfg['tx']['ctle_g_dc_db'] = float(gdc)
    cfg['tx']['ctle_g_dc2_db'] = float(gdc2)

    try:
        _, mlse_ber = run_sim(cfg, custom_tx_taps=taps, plot_eyes=False, output_dir=None)
        mlse_ber = float(np.clip(mlse_ber, 1e-8, 1.0))
    except Exception:
        mlse_ber = 1.0
    try:
        tx_fir = extract_tx_s21(cfg, custom_tx_taps=taps, num_taps=7)
    except Exception:
        tx_fir = np.zeros(7)

    env = next((e for e in ENV_CASES if e['name'] == env_name), None)
    row = {
        'sample_id': i, 'env': env_name,
        'il_db': env['il'] if env else np.nan,
        'cd_ps_nm': env['cd'] if env else np.nan,
        'dgd_ps': env['dgd'] if env else np.nan,
        'pol_deg': env['pol'] if env else np.nan,
        'mlse_ber': mlse_ber,
        'log10_ber_mlse': np.log10(max(mlse_ber, 1e-8)),
        'ctle_dc': gdc, 'ctle_dc2': gdc2,
    }
    for j in range(10):
        row[f'x_{j}'] = float(x_eff[j])
    for j in range(9):
        row[f'ffe_tap_{j}'] = float(taps[j])
    for j in range(7):
        row[f'tx_fir_{j}'] = float(tx_fir[j])
    return row


def generate_dataset(base_env=BASE_ENV, base_samples=400, anchor_samples=80,
                     num_symbols=131072, seed=42, output_dir="dataset"):
    """生成环境锚定邻域数据集。

    base_env: 密集采样的基准环境名（默认 Base_IL10）
    base_samples: 基准环境邻域采样数（不含种子行）
    anchor_samples: 其余每个应力环境的邻域锚点数（不含种子行）
    num_symbols: 单点仿真符号数（BER_MLSE 评估协议）
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    create_config.generate_config()
    base_cfg = load_config('config.xlsx')
    base_cfg['system']['enable_eye_plot'] = False
    base_cfg['system']['enable_spectrum_plot'] = False

    ffe_pre = int(base_cfg['tx'].get('ffe_pre', 4))
    seed_pre_post = np.zeros(8)
    seed_pre_post[:ffe_pre] = D.SEED_TAPS[:ffe_pre]
    seed_pre_post[ffe_pre:] = D.SEED_TAPS[ffe_pre + 1:]

    print(f"[dataset v2] env-anchored neighborhood sampling | num_symbols={num_symbols}")
    print(f"  spread: FFE ±{BASE_SPREAD_FFE} / CTLE ±{BASE_SPREAD_CTLE} dB "
          f"(= Stage-2 信任域)")

    tasks = []
    idx = 0
    rng_lhs = np.random.RandomState(seed)
    for env in ENV_CASES:
        n = base_samples if env['name'] == base_env else anchor_samples
        if n <= 0:
            continue
        cfg_env = apply_env_to_config(base_cfg, env)
        # 环境专用种子：确保各环境锚点互不相同且可复现
        sampler = qmc.LatinHypercube(d=10, seed=int(seed) + ENV_CASES.index(env) * 7)
        sp = sampler.random(n=n)
        for i in range(n):
            tasks.append((f"{env['name']}:{i}", env['name'], cfg_env,
                          num_symbols, ffe_pre, seed_pre_post, sp[i], False))
            idx += 1
        # 每个环境额外放一个精确种子行
        tasks.append((f"{env['name']}:seed", env['name'], cfg_env,
                      num_symbols, ffe_pre, seed_pre_post, None, True))
        print(f"    env {env['name']:16s} -> {n} pts (+1 seed)")

    print(f"[dataset v2] total {len(tasks)} evaluations, sequential ...")
    rows = []
    for i, task in enumerate(tasks):
        rows.append(_worker_task(task))
        if (i + 1) % 100 == 0 or (i + 1) == len(tasks):
            print(f"    done {i + 1}/{len(tasks)}")

    df = pd.DataFrame(rows)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_file = os.path.join(output_dir, f"ddps_v2_dataset_{ts}.csv")
    df.to_csv(out_file, index=False)

    print(f"[dataset v2] saved to {out_file}")
    print(f"  n={len(df)} | envs={df['env'].nunique()} | "
          f"log10_ber_mlse in [{df['log10_ber_mlse'].min():.3f}, "
          f"{df['log10_ber_mlse'].max():.3f}]")
    return out_file


if __name__ == "__main__":
    import argparse
    import multiprocessing
    multiprocessing.freeze_support()
    p = argparse.ArgumentParser()
    p.add_argument('--base-samples', type=int, default=400)
    p.add_argument('--anchor-samples', type=int, default=80)
    p.add_argument('--num-symbols', type=int, default=131072)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--out-dir', type=str, default='dataset')
    a = p.parse_args()
    generate_dataset(base_samples=a.base_samples, anchor_samples=a.anchor_samples,
                     num_symbols=a.num_symbols, seed=a.seed, output_dir=a.out_dir)
