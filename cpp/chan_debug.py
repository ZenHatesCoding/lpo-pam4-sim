# chan_debug.py — 复刻 apply_channel 全链路，逐段打印 sum|x| 校验和（定位 C++ 差异）。
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('OMP_NUM_THREADS', '1')
from scipy import signal
import skrf as rf

from utils_config import load_config
from ddps_cases import apply_env_to_config
from channel_imdd import (apply_s4p_filter, apply_ctle, apply_cd, apply_dgd,
                          lowpass_filter, dac_zoh, add_quantization_noise, RX_AGC_RMS)

TAPS = [-0.053735, -0.277536, 0.499432, 0.075396, 0.093901]
GDC, GDC2, GAIN = 6.864, 0.0, 0.1334
NUM_SYM, SEED, SNR = 262144, 42, 23.0

config = load_config('config.xlsx')
config = apply_env_to_config(config, 'Base_IL10x10')
config['tx']['ctle_g_dc_db'] = GDC
config['tx']['ctle_g_dc2_db'] = GDC2
config['channel']['driver_gain'] = GAIN
config['system']['seed'] = SEED
config['channel']['seed'] = SEED + 7919
config['system']['num_symbols'] = NUM_SYM
config['system']['tx_noise_snr_db'] = SNR

# 读已保存的 tx_out_noisy
tx_out = np.fromfile('cpp/build/tx_out_noisy.bin', dtype='<f8')

config_ch = config['channel']
baud_rate = config['system']['baud_rate']
sps_dac = config['system']['sps_dac']
sps_channel = config['system']['sps_channel']
sps_adc = config['system']['sps_adc']
nyquist = baud_rate / 2
fs_analog = baud_rate * sps_channel

rng = np.random.RandomState(int(config_ch['seed']))
x = tx_out.copy()
x = add_quantization_noise(x, config_ch['dac_enob'], rng)
x = dac_zoh(x, sps_dac, sps_channel)
print('S01 zoh        %.12e' % np.sum(np.abs(x)))

x = apply_s4p_filter(x, fs_analog, config_ch, 'tx_pcb_loss_nyquist_db', nyquist)
print('S02 tx_s4p     %.12e' % np.sum(np.abs(x)))
x = x + rng.normal(0, config_ch['host_tx_noise_rms'], len(x))
print('S03 tx_hostn   %.12e' % np.sum(np.abs(x)))
fb = baud_rate
x = apply_ctle(x, fs_analog, fb/config['tx']['ctle_fz_ratio'], fb/config['tx']['ctle_fp1_ratio'],
               fb/config['tx']['ctle_fp2_ratio'], config['tx']['ctle_g_dc_db'],
               config['tx']['ctle_g_dc2_db'], fb/config['tx']['ctle_flf_ratio'])
print('S04 tx_ctle    %.12e' % np.sum(np.abs(x)))
x = x * config_ch['driver_gain']
x = lowpass_filter(x, config_ch['driver_bw'], fs_analog, order=4)
print('S05 tx_driver  %.12e' % np.sum(np.abs(x)))
x_analog = x.copy()

# E-O
P_in_W = 10**(3.0/10)/1000.0
rin_linear = 10**(config_ch['laser_rin_db_hz']/10)
bw_noise = fs_analog/2
var_rin = rin_linear*bw_noise*(P_in_W**2)
P_laser = P_in_W + rng.normal(0, np.sqrt(var_rin), len(x))
P_laser = np.maximum(P_laser, 0.0)
print('S06 P_laser    %.12e' % np.sum(np.abs(P_laser)))
linewidth = config_ch['laser_linewidth_hz']
dphase = rng.normal(0, np.sqrt(2*np.pi*linewidth/fs_analog), len(x))
phase_noise = np.cumsum(dphase)
E_in = np.sqrt(P_laser)*np.exp(1j*phase_noise)
print('S07 E_in       %.12e' % np.sum(np.abs(E_in)))
v_pi = config_ch['mzm_v_pi']; v_bias = config_ch['mzm_v_bias']; er = config_ch['mzm_er_db']
e_r = 10**(er/10); gamma = (1-1/np.sqrt(e_r))/2
phase = np.pi*(x+v_bias)/v_pi
E_out = E_in*(gamma*np.exp(1j*phase)+(1-gamma)*np.exp(-1j*phase))
print('S08 E_mzm      %.12e' % np.sum(np.abs(E_out)))
E_out = lowpass_filter(E_out, config_ch['mzm_bw'], fs_analog)
print('S09 E_mzm_lpf  %.12e' % np.sum(np.abs(E_out)))
loss_db = config_ch['fiber_length_km']*config_ch['fiber_loss_db_km']
E_out = E_out*np.sqrt(10**(-loss_db/20.0))
print('S10 E_fiber    %.12e' % np.sum(np.abs(E_out)))
E_out = apply_cd(E_out, fs_analog, config_ch['cd_ps_nm'])
print('S11 E_cd       %.12e' % np.sum(np.abs(E_out)))
P_rx = np.abs(E_out)**2
print('S12 P_rx       %.12e' % np.sum(np.abs(P_rx)))
P_rx = apply_dgd(P_rx, fs_analog, config_ch['dgd_ps'], config_ch['pol_angle_deg'])
print('S13 P_dgd      %.12e' % np.sum(np.abs(P_rx)))
I_pd = config_ch['pin_responsivity']*P_rx + config_ch['pin_dark_current_na']*1e-9
print('S14 I_pd       %.12e' % np.sum(np.abs(I_pd)))
q=1.602176634e-19; kB=1.380649e-23
var_shot = 2*q*np.abs(I_pd)*bw_noise
noise_shot = rng.normal(0, np.sqrt(var_shot))
var_thermal = 4*kB*config_ch['temperature_k']/config_ch['rl_ohm']*bw_noise
noise_thermal = rng.normal(0, np.sqrt(var_thermal), len(I_pd))
I_pd_noisy = I_pd + noise_shot + noise_thermal
print('S15 I_noisy    %.12e' % np.sum(np.abs(I_pd_noisy)))
I_pd_noisy = lowpass_filter(I_pd_noisy, config_ch['pd_bw'], fs_analog)
print('S16 I_pd_lpf   %.12e' % np.sum(np.abs(I_pd_noisy)))
V_tia = I_pd_noisy*config_ch['tia_gain_ohm']
tia_noise_pa = config_ch['tia_noise_pa_rthz']*1e-12
var_tia = (tia_noise_pa**2)*bw_noise
V_tia = V_tia + rng.normal(0, np.sqrt(var_tia)*config_ch['tia_gain_ohm'], len(V_tia))
print('S17 V_tia      %.12e' % np.sum(np.abs(V_tia)))
V_tia = lowpass_filter(V_tia, config_ch['tia_bw'], fs_analog)
print('S18 V_tia_lpf  %.12e' % np.sum(np.abs(V_tia)))
V_tia = V_tia - np.mean(V_tia)
V_tia = V_tia*(RX_AGC_RMS/np.std(V_tia))
print('S19 AGC        %.12e' % np.sum(np.abs(V_tia)))
x = V_tia
x = apply_s4p_filter(x, fs_analog, config_ch, 'rx_pcb_loss_nyquist_db', nyquist)
print('S20 rx_s4p     %.12e' % np.sum(np.abs(x)))
x += rng.normal(0, config_ch['host_rx_noise_rms'], len(x))
print('S21 rx_hostn   %.12e' % np.sum(np.abs(x)))
x = apply_ctle(x, fs_analog, fb/config_ch['rx_ctle_fz_ratio'], fb/config_ch['rx_ctle_fp1_ratio'],
               fb/config_ch['rx_ctle_fp2_ratio'], config_ch['rx_ctle_g_dc_db'],
               config_ch['rx_ctle_g_dc2_db'], fb/config_ch['rx_ctle_flf_ratio'])
print('S22 rx_ctle    %.12e' % np.sum(np.abs(x)))
x_adc_in = lowpass_filter(x, config_ch['adc_bw'], fs_analog)
print('S23 adc_lpf    %.12e' % np.sum(np.abs(x_adc_in)))
x_adc_out = x_adc_in[::sps_channel//sps_adc]
x_adc_out = add_quantization_noise(x_adc_out, config_ch['adc_enob'], rng)
print('S24 rx_adc     %.12e' % np.sum(np.abs(x_adc_out)))
