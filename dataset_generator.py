import os
# Must set these BEFORE importing numpy/scipy
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['VECLIB_MAXIMUM_THREADS'] = '1'
os.environ['NUMEXPR_NUM_THREADS'] = '1'

# ============================================================================
# DDPS 数据集生成器（环境锚定邻域采样，7 维搜索空间，支持多进程并行）
#
# 搜索空间 7 维：4 FFE 旁瓣 + gDC + gDC2 + u_gain（driver_gain 经 u=log10 倍率进入）。
# CTLE 位于 Tx 电插损之后、Driver 之前（post-channel 均衡），采样盒与 Stage-2 信任域一致
# （FFE ±0.10 / CTLE ±3.0 dB / gain ±0.15 dex）。
# gain 作为独立采样维：在基线 per-case 扫描最优 gain 的 u 邻域（宽口径 ×0.20~×1.26）均匀
# 采样，覆盖全部用例 per-case 最优 gain 及其在线信任域；种子行锚定基线 per-case 最优 gain。
# 用例支持 Tx/Rx 插损非对称，并可覆盖器件噪声参数（RIN / ER / TIA）。
# 每个采样点可用多个仿真种子重复评估后取 log10 BER 均值，抑制 BER 估计噪声。
# `--jobs` 多进程并行：每个点独立、种子固定，因此并行与串行结果逐位一致。
#
# 输出列:
#   sample_id, env, il_tx_db, il_rx_db, cd_ps_nm, dgd_ps, pol_deg,
#   num_symbols, n_sim_seeds, sim_seed0,
#   x_0..x_6 (实际生效的 7D 搜索空间坐标),
#   ffe_tap_0..ffe_tap_4, ctle_dc, ctle_dc2, driver_gain, drive_rms,
#   mlse_ber, log10_ber_mlse, ber_std_log10, tx_fir_0..tx_fir_6
# ============================================================================
import numpy as np
import pandas as pd
from datetime import datetime
from scipy.stats import qmc
import ddps_optimizer as D          # 统一参数化 & 种子 & 信任域
from ddps_cases import ENV_CASES, BASE_ENV, apply_env_to_config
from utils_config import load_config, ensure_config
from main import run_sim
from tx_channel_extract import extract_tx_features

BASE_SPREAD_FFE = D.TRUST_FFE      # ±0.10（外壳：整个信任域）
BASE_SPREAD_CTLE = D.TRUST_CTLE    # ±3.0 dB

# ---------------------------------------------------------------------------
# 采样设计：**核心加密 + 外壳覆盖**
#
# 病根：全部点在高维箱里均匀铺开时，局部数据间距太大，整条下降轨迹落在同一个数据格里，
# 代理的"增量斜率"没有数据支撑，于是出现"预测一直下降、实测却走平甚至上升"。
#
# 对策：把 60% 的样本预算放进下降轨迹真正经过的小邻域（核心），40% 覆盖整箱（外壳）。
# 这不会改变模型形式，只是把数据放对地方。
# ---------------------------------------------------------------------------
CORE_SAMPLES = 1200
CORE_SPREAD_FFE = 0.075            # 核心：FFE ±0.075
CORE_SPREAD_CTLE = 2.0             # 核心：CTLE ±2.0 dB


def _taps_without_center(taps, ffe_pre):
    return np.concatenate([taps[:ffe_pre], taps[ffe_pre + 1:]])


def _sample_point(u, seed_pre_post, ffe_pre, spread_ffe=None, spread_ctle=None,
                  u_gain_range=None):
    """u: 7D LHS [0,1]^7 -> (pre_post_raw, gdc, gdc2, gain)。

    FFE / CTLE 在种子点的信任域内采样；driver_gain 在 u 空间（log10 倍率）[lo,hi]
    均匀采样（覆盖全用例 per-case 最优 gain 操作区间）。
    """
    sf = BASE_SPREAD_FFE if spread_ffe is None else float(spread_ffe)
    sc = BASE_SPREAD_CTLE if spread_ctle is None else float(spread_ctle)
    pre_post = seed_pre_post + (u[:D.N_SIDE] * 2 - 1.0) * sf
    gdc = float(np.clip(D.SEED_GDC + (u[D.N_SIDE] * 2 - 1.0) * sc,
                        D.CTLE_GDC_MIN, D.CTLE_GDC_MAX))
    gdc2 = float(np.clip(D.SEED_GDC2 + (u[D.N_SIDE + 1] * 2 - 1.0) * sc,
                         D.CTLE_GDC2_MIN, D.CTLE_GDC2_MAX))
    if u_gain_range is not None:
        lo, hi = u_gain_range
        u_gain = float(lo + u[D.N_SIDE + 2] * (hi - lo))
        gain = D.gain_from_u(u_gain)
    else:
        u_gain = float(D.GAIN_LOG10_MIN + u[D.N_SIDE + 2]
                       * (D.GAIN_LOG10_MAX - D.GAIN_LOG10_MIN))
        gain = D.gain_from_u(u_gain)
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
     sim_seeds, spread) = args
    import copy
    cfg = copy.deepcopy(cfg_dict)
    cfg['system']['num_symbols'] = int(num_symbols)

    if is_seed:
        gdc, gdc2 = D.SEED_GDC, D.SEED_GDC2
        taps = D.SEED_TAPS.copy()
        if spread[2] is not None:
            lo, hi = spread[2]
            u_gain = 0.5 * (lo + hi)                # 种子 gain = 基线 per-case 扫描最优 gain
            gain = D.gain_from_u(u_gain)
        else:
            u_gain = D.SEED_GAIN_U
            gain = D.SEED_GAIN
    else:
        # spread = (spread_ffe, spread_ctle, u_gain_range)
        pre_post, gdc, gdc2, gain = _sample_point(u, seed_pre_post, ffe_pre,
                                                    spread[0], spread[1],
                                                    u_gain_range=spread[2])
        u_gain = D.u_from_gain(gain)
        taps = D.construct_taps(pre_post, ffe_pre)

    x_eff = np.concatenate([_taps_without_center(taps, ffe_pre), [gdc, gdc2, u_gain]])

    cfg['tx']['ctle_g_dc_db'] = float(gdc)
    cfg['tx']['ctle_g_dc2_db'] = float(gdc2)
    cfg['channel']['driver_gain'] = float(gain)

    mean_lb, std_lb, n_seeds = _eval_ber(cfg, taps, sim_seeds)
    try:
        tx_fir, drive_rms = extract_tx_features(cfg, custom_tx_taps=taps, num_taps=7)
    except Exception:
        tx_fir, drive_rms = np.zeros(7), 0.0

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
        'driver_gain': float(gain),
        'gain_u': float(u_gain),
        'gain_ratio': float(gain / D.DRIVER_GAIN_NOMINAL),
        'drive_rms': float(drive_rms),
    }
    for j in range(len(x_eff)):
        row[f'x_{j}'] = float(x_eff[j])
    for j in range(len(taps)):
        row[f'ffe_tap_{j}'] = float(taps[j])
    for j in range(7):
        row[f'tx_fir_{j}'] = float(tx_fir[j])
    return row


def generate_dataset(base_env=BASE_ENV, base_samples=320, anchor_samples=60,
                     num_symbols=131072, seed=42, sim_seeds=(42,), output_dir="dataset",
                     jobs=1, include_envs=None, core_samples=CORE_SAMPLES,
                     gain_anchor_path=None, seed_config=None):
    """生成环境锚定邻域数据集（7 维：4 FFE 旁瓣 + gDC + gDC2 + u_gain）。

    seed_config: dict with keys 'best_pre_post', 'best_gdc', 'best_gdc2' —
    覆盖默认种子点（D.SEED_TAPS/SEED_GDC/SEED_GDC2），用于非基线环境训练。

    gain 作为独立采样维，在**基线 per-case 扫描最优 gain 的 u 邻域**（宽口径
    ×0.20~×1.26，即 u ∈ [GAIN_SAMPLE_U_LO, GAIN_SAMPLE_U_HI]）均匀采样，覆盖全部
    用例 per-case 最优 gain 及其 ±0.15 dex 在线信任域；种子行锚定基线最优 gain。
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # config.xlsx 由主进程入口（__main__）在 spawn worker 前统一生成/校验；
    # worker（_worker_task）只拿深拷贝的 cfg 只读，绝不在 worker 里就地生成。
    base_cfg = load_config('config.xlsx')
    base_cfg['system']['enable_eye_plot'] = False
    base_cfg['system']['enable_spectrum_plot'] = False

    ffe_pre = int(base_cfg['tx'].get('ffe_pre', D.FFE_PRE))

    # 种子点：默认用 D.SEED_*；若 seed_config 提供则覆盖（BO 寻优结果）
    if seed_config is not None:
        seed_pre_post = np.array(seed_config['best_pre_post'], dtype=float)
        seed_gdc = float(seed_config['best_gdc'])
        seed_gdc2 = float(seed_config['best_gdc2'])
        # 覆盖模块级常量，让 _sample_point / _worker_task / construct_taps 自动用新种子
        taps_full = D.construct_taps(seed_pre_post, ffe_pre)
        D.SEED_TAPS = taps_full.copy()
        D.SEED_GDC = seed_gdc
        D.SEED_GDC2 = seed_gdc2
        print(f"[dataset] 使用 BO 寻优种子点: pre_post={np.round(seed_pre_post,4)} "
              f"gDC={seed_gdc:.2f} gDC2={seed_gdc2:.2f} | full taps={np.round(taps_full,4)}")
    else:
        seed_pre_post = np.concatenate([D.SEED_TAPS[:ffe_pre], D.SEED_TAPS[ffe_pre + 1:]])
        seed_gdc = D.SEED_GDC
        seed_gdc2 = D.SEED_GDC2

    sim_seeds = tuple(int(s) for s in sim_seeds)

    # gain 采样带（宽口径）：u ∈ [GAIN_SAMPLE_U_LO, GAIN_SAMPLE_U_HI]，
    # 覆盖全部用例 per-case 最优 gain 及其 ±0.15 dex 在线信任域；种子行锚定基线最优 gain。
    anchor_path = gain_anchor_path or 'result/per_case_target_rms.json'
    anchor_gain = None
    if os.path.exists(anchor_path):
        import json as _json
        with open(anchor_path, encoding='utf-8') as f:
            pcm = _json.load(f)
        if base_env in pcm:
            anchor_gain = float(pcm[base_env]['gain'])
    if not anchor_gain or anchor_gain <= 0:
        anchor_gain = D.SEED_GAIN
    u_anchor = D.u_from_gain(anchor_gain)
    gain_range = (float(D.GAIN_SAMPLE_U_LO), float(D.GAIN_SAMPLE_U_HI))
    print(f"[dataset] gain 纳入搜索维：基线 {base_env} 扫描最优 gain={anchor_gain:.4f} "
          f"(u={u_anchor:+.3f}) 作种子锚点；采样带 u ∈ [{gain_range[0]:+.3f}, {gain_range[1]:+.3f}] "
          f"(ratio ×{10**gain_range[0]:.2f}..×{10**gain_range[1]:.2f})，覆盖全用例 gain 操作区间")

    print(f"[dataset] env-anchored neighborhood sampling | dims={D.N_DIM}（FFE+CTLE+gain） | "
          f"num_symbols={num_symbols} | sim_seeds={sim_seeds} | jobs={jobs}")
    print(f"  spread: FFE/CTLE 核心加密 + gain u 均匀采样（宽口径全用例操作区间）")

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
        n_core = min(int(core_samples), n) if env['name'] == base_env else 0
        core_spread = (CORE_SPREAD_FFE, CORE_SPREAD_CTLE, gain_range)
        shell_spread = (None, None, gain_range)
        for i in range(n):
            spread = core_spread if i < n_core else shell_spread
            tasks.append((f"{env['name']}:{i}", env['name'], cfg_env,
                          num_symbols, ffe_pre, seed_pre_post, sp[i], False, sim_seeds,
                          spread))
        # 每个环境额外放一个精确种子行（种子 gain = 基线 per-case 扫描最优 gain）
        seed_spread = (None, None, (u_anchor, u_anchor))
        tasks.append((f"{env['name']}:seed", env['name'], cfg_env,
                      num_symbols, ffe_pre, seed_pre_post, None, True, sim_seeds,
                      seed_spread))
        print(f"    env {env['name']:24s} -> {n} pts (+1 seed)"
              + (f"  [核心 {n_core} 点：FFE ±{CORE_SPREAD_FFE} / CTLE ±{CORE_SPREAD_CTLE} dB"
                 f" / gain u 宽口径；其余 {n - n_core} 点覆盖整箱]" if n_core else ""))

    print(f"[dataset] total {len(tasks)} evaluations ...")
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
    out_file = os.path.join(output_dir, f"ddps_dataset_{ts}.csv")
    df.to_csv(out_file, index=False)

    print(f"[dataset ddps] saved to {out_file}")
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
    p.add_argument('--core-samples', type=int, default=CORE_SAMPLES,
                   help='基线环境下投入“核心加密”的样本数（其余覆盖整箱，0=纯整箱均匀）')
    p.add_argument('--gain-anchor-path', type=str, default=None,
                   help='gain 锚点 JSON 路径（默认 result/per_case_target_rms.json）')
    p.add_argument('--base-env', type=str, default=None,
                   help='基线训练环境名（默认 Base_IL10x10）；设为 IL20x20 则用 20dB 环境训练')
    p.add_argument('--seed-config', type=str, default=None,
                   help='BO 寻优种子点 JSON 路径（含 best_pre_post/best_gdc/best_gdc2）；'
                        '不提供则用默认 SEED_TAPS')
    a = p.parse_args()
    ensure_config()
    sim_seeds = tuple(int(s) for s in str(a.sim_seeds).split(',') if s.strip())
    only = tuple(s.strip() for s in a.only_envs.split(',')) if a.only_envs else None
    base_env = a.base_env if a.base_env else BASE_ENV
    seed_cfg = None
    if a.seed_config:
        import json as _json
        with open(a.seed_config, 'r', encoding='utf-8') as _f:
            seed_cfg = _json.load(_f)
    generate_dataset(base_samples=a.base_samples, anchor_samples=a.anchor_samples,
                     num_symbols=a.num_symbols, seed=a.seed, sim_seeds=sim_seeds,
                     output_dir=a.out_dir, jobs=a.jobs, include_envs=only,
                     core_samples=a.core_samples, gain_anchor_path=a.gain_anchor_path,
                     base_env=base_env, seed_config=seed_cfg)
