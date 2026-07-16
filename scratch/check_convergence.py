import numpy as np
import sys
sys.path.append('.')
from utils_config import load_config
import create_config
import matplotlib.pyplot as plt
import os
from main import run_sim
from rx_dsp import adaptive_ffe_dfe
from tx_dsp import pam4_map, tx_dsp_chain
from channel_imdd import apply_channel
from scipy.signal import correlate

def check_convergence():
    create_config.generate_config()
    config = load_config('config.xlsx')
    config['channel']['pcb_loss_nyquist_db'] = 15.0
    
    baud_rate = config['system']['baud_rate']
    sps_dsp = int(config['system']['sps_dsp'])
    sps_dac = int(config['system']['sps_dac'])
    sps_channel = int(config['system']['sps_channel'])
    sps_adc = int(config['system']['sps_adc'])
    num_symbols = 50000  # Increase to 50k to really see the curve
    config['system']['num_symbols'] = num_symbols
    config['rx']['train_len'] = 10000
    
    rng = np.random.RandomState(42)
    tx_symbols = rng.randint(0, 4, num_symbols)
    tx_pam4 = pam4_map(tx_symbols)
    
    tx_config = config['tx'].copy()
    default_taps = np.zeros(9)
    default_taps[4] = 1.0
    tx_config['custom_taps'] = default_taps
        
    tx_out = tx_dsp_chain(tx_pam4, sps_dsp, baud_rate, tx_config)
    
    tx_analog, rx_analog, rx_adc = apply_channel(
        tx_out, config['channel'], baud_rate, sps_dac, sps_channel, sps_adc
    )
    
    rx_1sps_even = rx_adc[::sps_adc]
    corr_even = correlate(rx_1sps_even[:1000], tx_pam4[:1000])
    max_even = np.max(corr_even)
    
    rx_1sps_odd = rx_adc[1::sps_adc]
    corr_odd = correlate(rx_1sps_odd[:1000], tx_pam4[:1000])
    max_odd = np.max(corr_odd)
    
    if max_even >= max_odd:
        sync_delay = np.argmax(corr_even) - (len(tx_pam4[:1000]) - 1)
        phase_offset = 0
    else:
        sync_delay = np.argmax(corr_odd) - (len(tx_pam4[:1000]) - 1)
        phase_offset = 1
        
    rx_eq, w_ffe, w_dfe, error_seq, ffe_decisions = adaptive_ffe_dfe(
        rx_adc[phase_offset:], tx_pam4, 
        31, 
        8,
        0, 
        config['rx']['lms_mu'], 
        config['rx']['lms_mu'], 
        10000,
        sync_delay=sync_delay
    )
    
    # Let's save the error curve
    mse = np.zeros(num_symbols//100)
    for i in range(len(mse)):
        mse[i] = np.mean(error_seq[i*100:(i+1)*100]**2)
        
    np.savetxt("scratch/mse_curve.txt", mse)
    print("MSE at end of 2k:", np.mean(error_seq[1900:2000]**2))
    print("MSE at end of 10k:", np.mean(error_seq[9900:10000]**2))
    print("MSE at end of 50k:", np.mean(error_seq[49900:50000]**2))

if __name__ == '__main__':
    check_convergence()
