# equiv_py.py — 生成 config.txt 并跑一次 Python 参考仿真，打印与 C++ test_equiv 同口径的校验和。
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('MKL_NUM_THREADS', '1')

from utils_config import load_config
from ddps_cases import apply_env_to_config
from main import run_sim

# --- 工作点（v7.1 Base_IL10x10 最优）---
TAPS = [-0.053735, -0.277536, 0.499432, 0.075396, 0.093901]
GDC, GDC2, GAIN = 6.864, 0.0, 0.1334
NUM_SYM = 262144
SEED = 42
SNR = 23.0

config = load_config('config.xlsx')
config = apply_env_to_config(config, 'Base_IL10x10')
config['tx']['ctle_g_dc_db'] = float(GDC)
config['tx']['ctle_g_dc2_db'] = float(GDC2)
config['channel']['driver_gain'] = float(GAIN)
config['system']['seed'] = SEED
config['channel']['seed'] = SEED + 7919
config['system']['num_symbols'] = NUM_SYM
config['system']['tx_noise_snr_db'] = SNR

# --- dump config.txt ---
def _fmt(v):
    if v is None:
        return None
    if isinstance(v, (bool, np.bool_)):
        return 'true' if v else 'false'
    if isinstance(v, (int, np.integer)):
        return repr(int(v))
    if isinstance(v, (float, np.floating)):
        return repr(float(v))
    return str(v)

with open('cpp/config.txt', 'w', encoding='utf-8') as f:
    f.write('# auto-generated config dump (equiv_py.py)\n')
    for sec in ['system', 'tx', 'channel', 'rx']:
        for k, v in config.get(sec, {}).items():
            s = _fmt(v)
            if s is None:
                continue
            f.write(f'{sec}.{k} = {s}\n')
    f.write('tx.custom_taps = ' + ','.join(repr(float(t)) for t in TAPS) + '\n')

# --- tx_out 校验和（复刻 run_sim 的 rng 序列）---
from tx_dsp import pam4_map, tx_dsp_chain
rng = np.random.RandomState(SEED)
tx_symbols = rng.randint(0, 4, NUM_SYM)
tx_pam4 = pam4_map(tx_symbols)
tx_taps = np.array(TAPS, dtype=float)
tx_out = tx_dsp_chain(tx_pam4, config['system']['sps_dsp'], config['system']['baud_rate'],
                      {'custom_taps': tx_taps})
chk_nonoise = float(np.sum(np.abs(tx_out)))
sigma = np.sqrt(5.0) / (10.0 ** (SNR / 20.0))
tx_out_noisy = tx_out + rng.normal(0.0, sigma, len(tx_out))
chk_noisy = float(np.sum(np.abs(tx_out_noisy)))

# --- 主仿真 ---
ffe_ber, mlse_ber, nodes = run_sim(config, custom_tx_taps=tx_taps, plot_eyes=False,
                                   return_nodes=True)

print('chk_tx_out_nonoise %.12e' % chk_nonoise)
print('chk_tx_out_noisy   %.12e' % chk_noisy)
print('chk_tx_analog      %.12e' % float(np.sum(np.abs(nodes['tx_analog']))))
print('chk_rx_analog      %.12e' % float(np.sum(np.abs(nodes['rx_analog']))))
print('chk_rx_adc         %.12e' % float(np.sum(np.abs(nodes['rx_adc']))))
print('chk_rx_eq          %.12e' % float(np.sum(np.abs(nodes['rx_eq']))))
print('chk_white          %.12e' % float(np.sum(np.abs(nodes['rx_eq_whitened']))))
print('sync_delay %d' % nodes['sync_delay'])
print('phase_offset %d' % nodes['phase_offset'])
print('ffe_ber %.12e' % ffe_ber)
print('mlse_ber %.12e' % mlse_ber)