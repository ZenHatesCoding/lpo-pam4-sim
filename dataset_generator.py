import os
# Must set these BEFORE importing numpy/scipy
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['VECLIB_MAXIMUM_THREADS'] = '1'
os.environ['NUMEXPR_NUM_THREADS'] = '1'

import numpy as np
import pandas as pd
from utils_config import load_config
from main import run_sim
from tx_channel_extract import extract_tx_s21
from datetime import datetime
from scipy.stats import qmc
import create_config
import concurrent.futures

FFE_BOUND = 0.3
CTLE_GDC_MIN = 0.0
CTLE_GDC_MAX = 5.0
CTLE_GDC2_MIN = 0.0
CTLE_GDC2_MAX = 5.0
PEAK_SUM_LIMIT = 0.8

def _construct_9tap(pre_post, ffe_pre):
    """
    pre_post: length 8 array. [pre_pre..., post_post...]
    """
    taps = np.zeros(9)
    main_idx = ffe_pre
    taps[:main_idx] = pre_post[:main_idx]
    taps[main_idx+1:] = pre_post[main_idx:]
    taps[main_idx] = 1.0
    return taps

def _worker_task_wrapper(args):
    return _worker_task(*args)

def _worker_task(i, sp, config_dict):
    import copy
    config = copy.deepcopy(config_dict)
    
    ffe_pre = int(config['tx'].get('ffe_pre', 4))
    
    pre_post = (sp[:8] * 2 - 1.0) * FFE_BOUND
    taps = _construct_9tap(pre_post, ffe_pre)
    ctle_gdc = CTLE_GDC_MIN + sp[8] * (CTLE_GDC_MAX - CTLE_GDC_MIN)
    ctle_gdc2 = CTLE_GDC2_MIN + sp[9] * (CTLE_GDC2_MAX - CTLE_GDC2_MIN)
    config['tx']['ctle_g_dc_db'] = ctle_gdc
    config['tx']['ctle_g_dc2_db'] = ctle_gdc2

    try:
        _, mlse_ber = run_sim(config, custom_tx_taps=taps, plot_eyes=False, output_dir=None)
        mlse_ber_val = float(np.clip(mlse_ber, 1e-8, 1.0))
    except Exception:
        mlse_ber_val = 1.0

    try:
        tx_fir = extract_tx_s21(config, custom_tx_taps=taps, num_taps=7)
    except Exception as e:
        tx_fir = np.zeros(7)

    record = {
        'sample_id': i,
        'ctle_dc': ctle_gdc,
        'ctle_dc2': ctle_gdc2,
        'mlse_ber': mlse_ber_val,
        'log10_ber': np.log10(mlse_ber_val)
    }
    
    for j in range(9):
        record[f'ffe_tap_{j}'] = float(taps[j])
    for j in range(7):
        record[f'tx_fir_{j}'] = float(tx_fir[j])
        
    return record

def generate_dataset(num_samples=2000, output_dir="dataset", seed=42):
    print(f"Generating LPO dataset: {num_samples} points, D=10 (FFE+GDC+GDC2) ...")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    create_config.generate_config()
    config = load_config('config.xlsx')

    config['system']['enable_eye_plot'] = False
    config['system']['enable_spectrum_plot'] = False

    ffe_pre = int(config['tx'].get('ffe_pre', 4))

    D = 10
    sampler = qmc.LatinHypercube(d=D, seed=seed)
    sample_points = sampler.random(n=num_samples)

    dataset = []

    print(f"Starting DDPS dataset generation of {num_samples} samples (LPO typical: 7dB IL)")
    
    import multiprocessing
    max_workers = max(1, multiprocessing.cpu_count() - 2)
    
    args_list = [(i, sample_points[i], config) for i in range(num_samples)]
    
    # Use ProcessPoolExecutor
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        for i, result in enumerate(executor.map(_worker_task_wrapper, args_list)):
            dataset.append(result)
            if (i + 1) % 50 == 0:
                print(f"Completed {i + 1}/{num_samples}")

    dataset.sort(key=lambda x: x['sample_id'])

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
    import multiprocessing
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser()
    parser.add_argument('--samples', type=int, default=2000, help='Number of samples to generate')
    parser.add_argument('--seed', type=int, default=42, help='LHS random seed')
    parser.add_argument('--out_dir', type=str, default='dataset', help='Output directory')
    args = parser.parse_args()
    generate_dataset(num_samples=args.samples, output_dir=args.out_dir, seed=args.seed)
