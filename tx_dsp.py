import numpy as np
from scipy import signal

def pam4_map(symbols):
    """ Map [0,1,2,3] to [-3, -1, 1, 3] """
    return symbols * 2 - 3

def tx_ctle(x, sps, baud_rate, dc_gain, peaking):
    """ Simple CTLE modeled via IIR filter at sps_dsp """
    fs = baud_rate * sps
    wz = 2 * np.pi * (baud_rate / 4)
    wp = 2 * np.pi * (baud_rate / 2)
    
    num = [dc_gain / wz, dc_gain]
    den = [1 / wp, 1]
    
    b, a = signal.bilinear(num, den, fs=fs)
    y = signal.lfilter(b, a, x)
    return y

def tx_ffe(x, taps, sps):
    """ T-spaced Tx FFE applied to DSP signal (sps=2) """
    w = np.zeros(len(taps) * sps)
    w[::sps] = taps
    w = w / np.sum(np.abs(w))
    y = np.convolve(x, w, mode='same')
    return y

def tx_dsp_chain(tx_pam4, sps_dsp, baud_rate, config_tx):
    """ Complete Tx DSP chain running at sps_dsp """
    # Upsample symbols to DSP rate (insert zeros)
    tx_up = np.zeros(len(tx_pam4) * sps_dsp)
    tx_up[::sps_dsp] = tx_pam4
    
    # Pulse shape at DSP (e.g. NRZ rect filter)
    pulse = np.ones(sps_dsp)
    tx_shaped = np.convolve(tx_up, pulse, mode='full')[:len(tx_up)]
    
    # LPO Host ASIC Tx typically only has FFE, not CTLE
    tx_eq = tx_shaped
    
    # FFE
    if 'custom_taps' in config_tx:
        tx_taps = np.array(config_tx['custom_taps'])
    else:
        tx_taps = np.zeros(int(config_tx['ffe_taps']))
        tx_taps[int(config_tx['ffe_pre'])] = 1.0 # Pass-through for now
        
    tx_out = tx_ffe(tx_eq, tx_taps, sps_dsp)
    
    return tx_out
