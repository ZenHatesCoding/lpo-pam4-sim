# drms_debug.py — 对固定 x 的 drive_rms / FIR 参考值（高精度）。
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('MKL_NUM_THREADS', '1')

from utils_config import load_config
from ddps_cases import apply_env_to_config
from tx_channel_extract import extract_tx_s21, extract_tx_features
from ddps_optimizer import construct_taps

X = [-2.723665325067e-02, -2.922779653869e-01, -1.702005654973e-03, 5.501915279735e-02,
     5.859391616050e+00, 1.734991920193e+00, -3.000000000000e-02]

config = load_config('config.xlsx')
config = apply_env_to_config(config, 'Base_IL10x10')
config['tx']['ctle_g_dc_db'] = X[4]
config['tx']['ctle_g_dc2_db'] = X[5]
config['channel']['driver_gain'] = 0.3399 * 10.0 ** X[6]

taps = construct_taps(np.array(X[:4]))
print('taps       [' + ', '.join('%.15e' % v for v in taps) + ']')
print('gain       %.15e' % (0.3399 * 10.0 ** X[6]))

fir_v = extract_tx_s21(config, custom_tx_taps=taps, num_taps=7)
fir_norm, drms = extract_tx_features(config, custom_tx_taps=taps, num_taps=7)
print('fir_v      [' + ', '.join('%.15e' % v for v in fir_v) + ']')
print('fir_norm   [' + ', '.join('%.15e' % v for v in fir_norm) + ']')
print('drive_rms  %.15e' % drms)