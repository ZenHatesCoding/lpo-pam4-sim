# probe_debug.py — 探针 + Model A 参考值（供 C++ 逐位比对）。
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('OMP_NUM_THREADS', '1')

from utils_config import load_config
from ddps_cases import apply_env_to_config
from tx_channel_extract import extract_tx_s21, extract_tx_features
from channel_imdd import DRIVE_RMS_NOMINAL
from train_surrogates import load_models

TAPS = [-0.053735, -0.277536, 0.499432, 0.075396, 0.093901]
GDC, GDC2, GAIN = 6.864, 0.0, 0.1334

config = load_config('config.xlsx')
config = apply_env_to_config(config, 'Base_IL10x10')
config['tx']['ctle_g_dc_db'] = GDC
config['tx']['ctle_g_dc2_db'] = GDC2
config['channel']['driver_gain'] = GAIN

taps = np.array(TAPS)
fir_v = extract_tx_s21(config, custom_tx_taps=taps, num_taps=7)
fir_norm, drms = extract_tx_features(config, custom_tx_taps=taps, num_taps=7)

print('fir_v      [' + ', '.join('%.12e' % v for v in fir_v) + ']')
print('fir_norm   [' + ', '.join('%.12e' % v for v in fir_norm) + ']')
print('drive_rms  %.12e' % drms)
print('DRIVE_RMS_NOMINAL %.12e' % DRIVE_RMS_NOMINAL)

# Model A 预测
model_a, _ = load_models('models/ddps')
probe = np.concatenate([fir_norm, [drms]])
xn = (probe - model_a.mu) / model_a.sd
pa = float(np.asarray(model_a.predict(xn.reshape(1, -1))).ravel()[0])
print('pred_a     %.12e' % pa)
print('mu_a       [' + ', '.join('%.12e' % v for v in model_a.mu) + ']')
print('sd_a       [' + ', '.join('%.12e' % v for v in model_a.sd) + ']')
print('W_a        [' + ', '.join('%.12e' % v for v in np.asarray(model_a.W).ravel()) + ']')
