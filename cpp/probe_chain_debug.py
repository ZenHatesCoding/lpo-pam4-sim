# probe_chain_debug.py — 逐段打印 drive_rms 链路校验和（定位 4e-6 差异）。
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('OMP_NUM_THREADS', '1'); os.environ.setdefault('OPENBLAS_NUM_THREADS','1'); os.environ.setdefault('MKL_NUM_THREADS','1')

from utils_config import load_config
from ddps_cases import apply_env_to_config
from tx_channel_extract import _drive_rms
from channel_imdd import tx_frontend_lti, apply_s4p_filter, apply_ctle, lowpass_filter, dac_zoh
from tx_dsp import pam4_map, tx_dsp_chain

X = [-2.723665325067e-02, -2.922779653869e-01, -1.702005654973e-03, 5.501915279735e-02,
     5.859391616050e+00, 1.734991920193e+00, -3.000000000000e-02]
TAPS = [-2.723665325067e-02, -2.922779653869e-01, 6.237642229101070e-01, -1.702005654973e-03, 5.501915279735e-02]

config = load_config('config.xlsx')
config = apply_env_to_config(config, 'Base_IL10x10')
config['tx']['ctle_g_dc_db'] = X[4]
config['tx']['ctle_g_dc2_db'] = X[5]
config['channel']['driver_gain'] = 0.3399 * 10.0 ** X[6]

baud = config['system']['baud_rate']; sps_dsp = config['system']['sps_dsp']
sps_dac = config['system']['sps_dac']; sps_ch = config['system']['sps_channel']
fs_analog = baud * sps_ch
n_symbols = 4096
rng = np.random.RandomState(7)
pam4 = pam4_map(rng.randint(0, 4, n_symbols))
tx_out = tx_dsp_chain(pam4, sps_dsp, baud, {'custom_taps': np.array(TAPS)})
print('S1 tx_dsp     %.15e' % np.sum(np.abs(tx_out)))
x = dac_zoh(tx_out, sps_dac, sps_ch)
print('S2 zoh        %.15e' % np.sum(np.abs(x)))
x_s4p = apply_s4p_filter(x, fs_analog, config['channel'], 'tx_pcb_loss_nyquist_db', baud/2)
print('S3 s4p        %.15e' % np.sum(np.abs(x_s4p)))
fb = baud
x_ctle = apply_ctle(x_s4p, fs_analog, fb/config['tx']['ctle_fz_ratio'], fb/config['tx']['ctle_fp1_ratio'],
                    fb/config['tx']['ctle_fp2_ratio'], config['tx']['ctle_g_dc_db'],
                    config['tx']['ctle_g_dc2_db'], fb/config['tx']['ctle_flf_ratio'])
print('S4 ctle       %.15e' % np.sum(np.abs(x_ctle)))
x_gain = x_ctle * config['channel']['driver_gain']
print('S5 gain       %.15e' % np.sum(np.abs(x_gain)))
x_bw = lowpass_filter(x_gain, config['channel']['driver_bw'], fs_analog, order=4)
print('S6 driver_bw  %.15e' % np.sum(np.abs(x_bw)))
skip = 200 * sps_ch
seg = x_bw[skip:]
print('S7 std        %.15e' % np.std(seg))
