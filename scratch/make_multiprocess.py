import re

def update():
    with open('dataset_generator.py', 'r', encoding='utf-8') as f:
        content = f.read()

    new_imports = "import concurrent.futures\nfrom functools import partial\n"
    if "concurrent.futures" not in content:
        content = content.replace("from scipy.stats import qmc\n", "from scipy.stats import qmc\n" + new_imports)

    process_sample_func = '''
def process_sample(i, sp, config_base, ffe_pre):
    import copy
    from main import run_sim
    from tx_channel_extract import extract_tx_s21
    import numpy as np
    
    config = copy.deepcopy(config_base)
    # FFE pre/post 游标：均匀落在 [-0.3, 0.3]
    pre_post = (sp[:8] * 2 - 1.0) * FFE_BOUND
    taps = _construct_9tap(pre_post, ffe_pre)

    # CTLE DC Gain：均匀落在 [-20, 0] dB
    ctle_dc = CTLE_MIN + sp[8] * (CTLE_MAX - CTLE_MIN)
    config['tx']['ctle_g_dc_db'] = ctle_dc

    try:
        _, mlse_ber = run_sim(config, custom_tx_taps=taps, plot_eyes=False, output_dir=None)
    except Exception as e:
        mlse_ber = 1.0

    mlse_ber_val = max(mlse_ber, 1e-8)

    try:
        tx_fir = extract_tx_s21(config, custom_tx_taps=taps, num_taps=7)
    except Exception as e:
        tx_fir = np.zeros(7)

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

    return record
'''

    content = content.replace("def generate_dataset(num_samples=2000, output_dir=\"dataset\", seed=42):", process_sample_func + "\ndef generate_dataset(num_samples=2000, output_dir=\"dataset\", seed=42):")
    
    # Replace loop with multiprocessing
    loop_start = content.find("for i in range(num_samples):")
    loop_end = content.find("df = pd.DataFrame(dataset)")
    
    new_loop = '''
    print(f"Using ProcessPoolExecutor to accelerate generation...")
    import multiprocessing
    max_workers = multiprocessing.cpu_count() - 2
    if max_workers < 1: max_workers = 1
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for i in range(num_samples):
            futures.append(executor.submit(process_sample, i, sample_points[i], config, ffe_pre))
            
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            dataset.append(future.result())
            if (i + 1) % 100 == 0:
                print(f"Completed {i + 1}/{num_samples}")

    # Sort dataset by sample_id to maintain order
    dataset.sort(key=lambda x: x['sample_id'])
    '''
    
    content = content[:loop_start] + new_loop + content[loop_end:]
    
    with open('dataset_generator.py', 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    update()
