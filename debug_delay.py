import numpy as np
from utils_config import load_config
from tx_dsp import pam4_map, upsample, tx_ctle, tx_ffe, pulse_shape
from channel_imdd import apply_channel
from rx_dsp import resample_to_dsp
from scipy.signal import correlate

config = load_config('config.xlsx')
baud_rate = config['system']['baud_rate']
sps_sim = int(config['system']['sps_sim'])
sps_dsp = int(config['system']['sps_dsp'])
num_symbols = int(config['system']['num_symbols'])

np.random.seed(42)
tx_symbols = np.random.randint(0, 4, num_symbols)
tx_pam4 = pam4_map(tx_symbols)

tx_up = upsample(tx_pam4, sps_sim)
tx_shaped = pulse_shape(tx_up, sps_sim)

tx_eq = tx_ctle(tx_shaped, sps_sim, baud_rate, config['tx']['ctle_dc_gain'], config['tx']['ctle_peaking'])
tx_taps = np.zeros(int(config['tx']['ffe_taps']))
tx_taps[int(config['tx']['ffe_pre'])] = 1.0
tx_out = tx_ffe(tx_eq, tx_taps, sps_sim)

rx_analog = apply_channel(tx_out, config['channel'], baud_rate, sps_sim)
rx_dsp_in = resample_to_dsp(rx_analog, sps_sim, sps_dsp)

# Decimate to 1 sps to check correlation
rx_1sps = rx_dsp_in[::sps_dsp]
corr = correlate(rx_1sps[:1000], tx_pam4[:1000])
delay = np.argmax(corr) - (len(tx_pam4[:1000]) - 1)
print(f"Estimated Symbol Delay: {delay}")
