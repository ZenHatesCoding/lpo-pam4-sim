# optimizer_debug.py — Stage-2 在线调优参考（供 C++ 逐位比对）。
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('MKL_NUM_THREADS', '1')

from utils_config import load_config
from ddps_cases import apply_env_to_config
from train_surrogates import load_models
from ddps_optimizer import _stage2_descent, FFE_PRE

config = load_config('config.xlsx')
config = apply_env_to_config(config, 'Base_IL10x10')
config['system']['num_symbols'] = 16384
config['system']['tx_noise_snr_db'] = 23.0
config['system']['seed'] = 42
config['channel']['seed'] = 42 + 7919

model_a, model_b = load_models('models/ddps')

x0 = np.array([-0.034, -0.2987, 0.0, 0.0582, 6.0, 2.0, 0.0])
trace = _stage2_descent(config, model_a, model_b, x0, FFE_PRE, n_steps=30, lr=0.05)

print('=== TRACE ===')
for rec in trace:
    print('step=%d' % rec['step'])
    print('  x=        [' + ', '.join('%.12e' % v for v in np.asarray(rec['x']).ravel()) + ']')
    print('  gdc=%.12e gdc2=%.12e gain=%.12e u_gain=%.12e' % (rec['gdc'], rec['gdc2'], rec['gain'], rec['u_gain']))
    print('  drive_rms=%.12e pred_a=%.12e pred_b=%.12e' % (rec['drive_rms'], rec['pred_a'], rec['pred_b']))
    print('  real_logber=%.12e real_mlse=%.12e' % (rec['real_logber'], rec['real_mlse']))
    print('  stop_reason=%r' % rec['stop_reason'])
