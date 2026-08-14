import numpy as np
import os
import pandas as pd
from utils_config import load_config
from main import run_sim
from tx_channel_extract import extract_tx_s21
from datetime import datetime
from scipy.stats import qmc

# ============================================================
# DDPS 离线数据集生成器
# 在“发端 FFE 预/后游标 (8 维) + CTLE DC Gain (1 维)”共 9 维
# 的全优化域内用 Latin Hypercube 采样，逐点跑白盒物理仿真，
# 记录 (FFE 配置, 发端 7-tap 等效 FIR, 真实 MLSE BER)。
# ============================================================

# 与 ddps_optimizer.py 的 SLSQP 搜索边界严格一致
FFE_BOUND = 0.3          # 每个 pre/post 游标范围 [-0.3, 0.3]
CTLE_MIN = -20.0
CTLE_MAX = 0.0
PEAK_SUM_LIMIT = 0.8     # sum(|pre_post|) <= 0.8 -> 主抽头 >= 0.2


def _construct_9tap(pre_post, ffe_pre):
    """由 8 个自由 pre/post 游标构造 9-tap T-spaced FFE（主抽头 = 1 - sum(|pre_post|)）。"""
    abs_sum = np.sum(np.abs(pre_post))
    if abs_sum > PEAK_SUM_LIMIT:
        pre_post = pre_post * (PEAK_SUM_LIMIT / abs_sum)
    taps = np.zeros(9)
    taps[:ffe_pre] = pre_post[:ffe_pre]
    taps[ffe_pre + 1:] = pre_post[ffe_pre:]
    taps[ffe_pre] = 1.0 - np.sum(np.abs(pre_post))
    return taps


def generate_dataset(num_samples=2000, output_dir="dataset", seed=42):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    import create_config
    create_config.generate_config()
    config = load_config('config.xlsx')

    # 关闭画图，避免 output_dir=None 时报错，同时提速
    config['system']['enable_eye_plot'] = False
    config['system']['enable_spectrum_plot'] = False

    ffe_pre = int(config['tx'].get('ffe_pre', 4))

    # 9 维 Latin Hypercube 采样：8 个 FFE 游标 + 1 个 CTLE DC
    D = 9
    sampler = qmc.LatinHypercube(d=D, seed=seed)
    sample_points = sampler.random(n=num_samples)

    dataset = []

    print(f"Starting DDPS dataset generation of {num_samples} samples "
          f"(FFE +/-{FFE_BOUND}, CTLE [{CTLE_MIN}, {CTLE_MAX}] dB)...")
    for i in range(num_samples):
        sp = sample_points[i]

        # FFE pre/post 游标：均匀落在 [-0.3, 0.3]
        pre_post = (sp[:8] * 2 - 1.0) * FFE_BOUND
        taps = _construct_9tap(pre_post, ffe_pre)

        # CTLE DC Gain：均匀落在 [-20, 0] dB
        ctle_dc = CTLE_MIN + sp[8] * (CTLE_MAX - CTLE_MIN)
        config['tx']['ctle_g_dc_db'] = ctle_dc

        # 1. 跑物理仿真，得到真实 MLSE BER
        try:
            _, mlse_ber = run_sim(config, custom_tx_taps=taps, plot_eyes=False, output_dir=None)
        except Exception as e:
            print(f"Simulation failed at sample {i}: {e}")
            mlse_ber = 1.0

        mlse_ber_val = max(mlse_ber, 1e-8)

        # 2. 提取发端 7-tap 等效 FIR（物理特征）
        try:
            tx_fir = extract_tx_s21(config, custom_tx_taps=taps, num_taps=7)
        except Exception as e:
            print(f"Extraction failed at sample {i}: {e}")
            tx_fir = np.zeros(7)

        # 3. 记录
        record = {
            'sample_id': i,
            'ctle_dc': ctle_dc,
            'mlse_ber': mlse_ber_val,
            'log10_ber': np.log10(mlse_ber_val)
        }
        for j in range(9):
            record[f'ffe_tap_{j}'] = taps[j]
        for j in range(7):
            record[f'tx_fir_{j}'] = tx_fir[j]

        dataset.append(record)

        if (i + 1) % 100 == 0:
            print(f"Completed {i + 1}/{num_samples}")

    df = pd.DataFrame(dataset)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = os.path.join(output_dir, f"ddps_dataset_{timestamp}.csv")
    df.to_csv(out_file, index=False)

    n_good = (df['mlse_ber'] < 1e-2).sum()
    print(f"Dataset saved to {out_file}")
    print(f"Coverage: {len(df)} samples | BER < 1e-2: {n_good} | "
          f"log10_ber in [{df['log10_ber'].min():.3f}, {df['log10_ber'].max():.3f}]")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--samples', type=int, default=2000, help='Number of samples to generate')
    parser.add_argument('--seed', type=int, default=42, help='LHS random seed')
    args = parser.parse_args()
    generate_dataset(num_samples=args.samples, seed=args.seed)
