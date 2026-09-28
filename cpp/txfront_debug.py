# txfront_debug.py — 保存 tx_out_noisy 并逐段打印 Tx 前端各阶段校验和。
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('OMP_NUM_THREADS', '1')

from utils_config import load_config
from ddps_cases import apply_env_to_config
from channel_imdd import apply_s4p_filter, apply_ctle, lowpass_filter, DRIVER_GAIN_NOMINAL

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

from tx_dsp import pam4_map, tx_dsp_chain
rng = np.random.RandomState(SEED)
tx_symbols = rng.randint(0, 4, NUM_SYM)
tx_pam4 = pam4_map(tx_symbols)
tx_taps = np.array(TAPS)
tx_out = tx_dsp_chain(tx_pam4, config['system']['sps_dsp'], config['system']['baud_rate'],
                      {'custom_taps': tx_taps})
sigma = np.sqrt(5.0) / (10.0 ** (SNR / 20.0))
tx_out = tx_out + rng.normal(0.0, sigma, len(tx_out))

tx_out.astype('<f8').tofile('cpp/build/tx_out_noisy.bin')
print('saved tx_out_noisy len=%d sumabs=%.12e' % (len(tx_out), np.sum(np.abs(tx_out))))

# 复刻 tx_frontend_lti 各阶段
config_ch = config['channel']
config_tx = config['tx']
baud_rate = config['system']['baud_rate']
sps_channel = config['system']['sps_channel']
fs_analog = baud_rate * sps_channel
nyquist = baud_rate / 2

# 1) DAC quant noise (channel rng)
rng_ch = np.random.RandomState(int(config_ch['seed']))
x = tx_out.copy()
enob = config_ch.get('dac_enob', 0)
vfs = float(np.max(x) - np.min(x))
sigma_q = vfs / (2.0 ** enob * np.sqrt(12.0))
x = x + rng_ch.normal(0.0, sigma_q, len(x))
# ZOH
x = np.repeat(x, 4)
print('after zoh sumabs=%.12e' % np.sum(np.abs(x)))

# 2) S4P IL
loss_db = config_ch['tx_pcb_loss_nyquist_db']
x_s4p = apply_s4p_filter(x, fs_analog, config_ch, 'tx_pcb_loss_nyquist_db', nyquist)
print('after s4p sumabs=%.12e' % np.sum(np.abs(x_s4p)))
x = x_s4p

# 3) host noise
x = x + rng_ch.normal(0, config_ch.get('host_tx_noise_rms', 0.001), len(x))
print('after hostnoise sumabs=%.12e' % np.sum(np.abs(x)))

# 4) CTLE
f_b = baud_rate
f_z = f_b / config_tx.get('ctle_fz_ratio', 2.862)
f_p1 = f_b / config_tx.get('ctle_fp1_ratio', 1.884)
f_p2 = f_b / config_tx.get('ctle_fp2_ratio', 1.0)
f_lf = f_b / config_tx.get('ctle_flf_ratio', 40.0)
x = apply_ctle(x, fs_analog, f_z, f_p1, f_p2, config_tx.get('ctle_g_dc_db', 0.0),
               config_tx.get('ctle_g_dc2_db', 0.0), f_lf)
print('after ctle sumabs=%.12e' % np.sum(np.abs(x)))

# 5) driver gain + BW
x = x * config_ch.get('driver_gain', DRIVER_GAIN_NOMINAL)
print('after gain sumabs=%.12e' % np.sum(np.abs(x)))
x = lowpass_filter(x, config_ch.get('driver_bw', 40e9), fs_analog, order=4)
print('after driverbw sumabs=%.12e' % np.sum(np.abs(x)))
