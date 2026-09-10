import os
# Must set these BEFORE importing numpy/scipy
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['VECLIB_MAXIMUM_THREADS'] = '1'
os.environ['NUMEXPR_NUM_THREADS'] = '1'

# ============================================================================
# DDPS v3 数据集生成器（环境锚定邻域采样，11 维搜索空间，支持多进程并行）
#
# v3 相对 v2 的变化：
#   1. 搜索空间 10D -> 11D：新增 driver_gain（Tx Driver 真实线性增益）。
#   2. CTLE 位于 Tx 电插损之后、Driver 之前（post-channel 均衡），采样盒与 Stage-2
#      信任域严格一致（FFE ±0.10 / CTLE ±3.0 dB / driver_gain ±0.5）。
#   3. 用例支持 Tx/Rx 插损非对称，并可覆盖器件噪声参数（RIN / ER / TIA）。
#   4. 每个采样点可用多个仿真种子重复评估后取 log10 BER 均值，抑制 BER 估计噪声
#      （比单纯加长块长更可控；同时记录点内标准差）。
#   5. `--jobs` 多进程并行：每个点独立、种子固定，因此并行与串行结果逐位一致。
#
# 输出列:
#   sample_id, env, il_tx_db, il_rx_db, cd_ps_nm, dgd_ps, pol_deg,
#   num_symbols, n_sim_seeds, sim_seed0,
#   x_0..x_10 (实际生效的 11D 搜索空间坐标),
#   ffe_tap_0..ffe_tap_8, ctle_dc, ctle_dc2, driver_gain, drive_rms,
#   mlse_ber, log10_ber_mlse, ber_std_log10, tx_fir_0..tx_fir_6
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
from tx_channel_extract import extract_tx_features

BASE_SPREAD_FFE = D.TRUST_FFE      # ±0.10
BASE_SPREAD_CTLE = D.TRUST_CTLE    # ±3.0 dB
BASE_SPREAD_GAIN = D.TRUST_GAIN    # ±0.5


def _taps_without_center(taps, ffe_pre):
    return np.concatenate([taps[:ffe_pre], taps[ffe_pre + 1:]])


def _sample_point(u, seed_pre_post, ffe_pre):
    """u: 11D LHS [0,1]^11 -> (pre_post_raw, gdc, gdc2, gain)。"""
    pre_post = seed_pre_post + (u[:8] * 2 - 1.0) * BASE_SPREAD_FFE
    gdc = float(np.clip(D.SEED_GDC + (u[8] * 2 - 1.0) * BASE_SPREAD_CTLE,
                        D.CTLE_GDC_MIN, D.CTLE_GDC_MAX))
    gdc2 = float(np.clip(D.SEED_GDC2 + (u[9] * 2 - 1.0) * BASE_SPREAD_CTLE,
                         D.CTLE_GDC2_MIN, D.CTLE_GDC2_MAX))
    gain = float(np.clip(D.SEED_GAIN + (u[10] * 2 - 1.0) * BASE_SPREAD_GAIN,
                         D.GAIN_MIN, D.GAIN_MAX))
    return pre_post, gdc, gdc2, gain


def _eval_ber(cfg, taps, sim_seeds):
    """多仿真种子重复评估，返回 (mean_log10, std_log10, n_seeds)。"""
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
    lbs = np.asarray(lbs)
    return float(lbs.mean()), float(lbs.std()), int(len(lbs))


def _worker_task(args):
    (i, env_name, cfg_dict, num_symbols, ffe_pre, seed_pre_post, u, is_seed,
     sim_seeds) = args
    import copy
    cfg = copy.deepcopy(cfg_dict)
    cfg['system']['num_symbols'] = int(num_symbols)

    if is_seed:
        gdc, gdc2, gain = D.SEED_GDC, D.SEED_GDC2, D.SEED_GAIN
        taps = D.SEED_TAPS.copy()
    else:
        pre_post, gdc, gdc2, gain = _sample_point(u, seed_pre_post, ffe_pre)
        taps = D.construct_9tap(pre_post, ffe_pre)

    x_eff = np.concatenate([_taps_without_center(taps, ffe_pre), [gdc, gdc2, gain]])

    cfg['tx']['ctle_g_dc_db'] = float(gdc)
    cfg['tx']['ctle_g_dc2_db'] = float(gdc2)
    cfg['channel']['driver_gain'] = float(gain)

    mean_lb, std_lb, n_seeds = _eval_ber(cfg, taps, sim_seeds)
    try:
        fir_shape, drive_rms = extract_tx_features(cfg, custom_tx_taps=taps, num_taps=7)
    except Exception:
        fir_shape, drive_rms = np.zeros(7), 0.0

    env = next((e for e in ENV_CASES if e['name'] == env_name), None)
    row = {
        'sample_id': i, 'env': env_name,
        'il_tx_db': env['il_tx'] if env else np.nan,
        'il_rx_db': env['il_rx'] if env else np.nan,
        'cd_ps_nm': env['cd'] if env else np.nan,
        'dgd_ps': env['dgd'] if env else np.nan,
        'pol_deg': env['pol'] if env else np.nan,
        'num_symbols': int(num_symbols),
        'n_sim_seeds': n_seeds,
        'sim_seed0': int(sim_seeds[0]),
        'mlse_ber': float(10.0 ** mean_lb),
        'log10_ber_mlse': float(mean_lb),
        'ber_std_log10': float(std_lb),
        'ctle_dc': float(gdc), 'ctle_dc2': float(gdc2),
        'driver_gain': float(gain), 'drive_rms': float(drive_rms),
    }
    for j in range(11):
        row[f'x_{j}'] = float(x_eff[j])
    for j in range(9):
        row[f'ffe_tap_{j}'] = float(taps[j])
    for j in range(7):
        row[f'tx_fir_{j}'] = float(fir_shape[j])
    return row


def generate_dataset(base_env=BASE_ENV, base_samples=320, anchor_samples=60,
                     num_symbols=131072, seed=42, sim_seeds=(42,), output_dir="dataset",
                     jobs=1, include_envs=None):
    """生成环境锚定邻域数据集（v3）。

    base_env: 密集采样的基准环境名（默认 Base_IL10x10）
    base_samples: 基准环境邻域采样数（不含种子行）
    anchor_samples: 其余每个应力环境的邻域锚点数（不含种子行）
    num_symbols: 单次仿真符号数（BER_MLSE 评估协议）
    sim_seeds: 每个采样点使用的仿真种子序列（多seed取均值以抑制BER估计噪声）
    jobs: 并行进程数（1 = 串行；结果与并行逐位一致）
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    if not os.path.exists('config.xlsx'):
        create_config.generate_config()
    base_cfg = load_config('config.xlsx')
    base_cfg['system']['enable_eye_plot'] = False
    base_cfg['system']['enable_spectrum_plot'] = False

    ffe_pre = int(base_cfg['tx'].get('ffe_pre', 4))
    seed_pre_post = np.zeros(8)
    seed_pre_post[:ffe_pre] = D.SEED_TAPS[:ffe_pre]
    seed_pre_post[ffe_pre:] = D.SEED_TAPS[ffe_pre + 1:]

    sim_seeds = tuple(int(s) for s in sim_seeds)

    print(f"[dataset v3] env-anchored neighborhood sampling | dims={D.N_DIM} | "
          f"num_symbols={num_symbols} | sim_seeds={sim_seeds} | jobs={jobs}")
    print(f"  spread: FFE ±{BASE_SPREAD_FFE} / CTLE ±{BASE_SPREAD_CTLE} dB / "
          f"gain ±{BASE_SPREAD_GAIN}  (= Stage-2 信任域)")

    tasks = []
    for env_idx, env in enumerate(ENV_CASES):
        if include_envs is not None and env['name'] not in include_envs:
            continue
        n = base_samples if env['name'] == base_env else anchor_samples
        if n <= 0:
            continue
        cfg_env = apply_env_to_config(base_cfg, env)
        # 环境专用种子：确保各环境锚点互不相同且可复现
        sampler = qmc.LatinHypercube(d=D.N_DIM, seed=int(seed) + env_idx * 7)
        sp = sampler.random(n=n)
        for i in range(n):
            tasks.append((f"{env['name']}:{i}", env['name'], cfg_env,
                          num_symbols, ffe_pre, seed_pre_post, sp[i], False, sim_seeds))
        # 每个环境额外放一个精确种子行
        tasks.append((f"{env['name']}:seed", env['name'], cfg_env,
                      num_symbols, ffe_pre, seed_pre_post, None, True, sim_seeds))
        print(f"    env {env['name']:24s} -> {n} pts (+1 seed)")

    print(f"[dataset v3] total {len(tasks)} evaluations ...")
    if jobs and jobs > 1:
        import multiprocessing as mp
        rows = []
        with mp.Pool(processes=int(jobs)) as pool:
            for k, r in enumerate(pool.imap(_worker_task, tasks, chunksize=4)):
                rows.append(r)
                if (k + 1) % 100 == 0 or (k + 1) == len(tasks):
                    print(f"    done {k + 1}/{len(tasks)}")
    else:
        rows = []
        for i, task in enumerate(tasks):
            rows.append(_worker_task(task))
            if (i + 1) % 100 == 0 or (i + 1) == len(tasks):
                print(f"    done {i + 1}/{len(tasks)}")

    df = pd.DataFrame(rows)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_file = os.path.join(output_dir, f"ddps_v3_dataset_{ts}.csv")
    df.to_csv(out_file, index=False)

    print(f"[dataset v3] saved to {out_file}")
    print(f"  n={len(df)} | envs={df['env'].nunique()} | "
          f"log10_ber_mlse in [{df['log10_ber_mlse'].min():.3f}, "
          f"{df['log10_ber_mlse'].max():.3f}] | "
          f"mean in-point std={df['ber_std_log10'].mean():.3f}")
    return out_file


if __name__ == "__main__":
    import argparse
    import multiprocessing
    multiprocessing.freeze_support()
    p = argparse.ArgumentParser()
    p.add_argument('--base-samples', type=int, default=320)
    p.add_argument('--anchor-samples', type=int, default=60)
    p.add_argument('--num-symbols', type=int, default=131072)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--sim-seeds', type=str, default='42',
                   help='逗号分隔的仿真种子序列，如 "42,43,44"（多seed取log10 BER均值）')
    p.add_argument('--jobs', type=int, default=1, help='并行进程数（1=串行）')
    p.add_argument('--out-dir', type=str, default='dataset')
    p.add_argument('--only-envs', type=str, default=None,
                   help='仅生成指定环境（逗号分隔），用于快速验证')
    a = p.parse_args()
    sim_seeds = tuple(int(s) for s in str(a.sim_seeds).split(',') if s.strip())
    only = tuple(s.strip() for s in a.only_envs.split(',')) if a.only_envs else None
    generate_dataset(base_samples=a.base_samples, anchor_samples=a.anchor_samples,
                     num_symbols=a.num_symbols, seed=a.seed, sim_seeds=sim_seeds,
                     output_dir=a.out_dir, jobs=a.jobs, include_envs=only)
