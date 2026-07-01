import numpy as np
from scipy import signal

def lowpass_filter(x, bw, fs, order=4):
    """ Butterworth low-pass filter """
    nyq = 0.5 * fs
    normal_cutoff = bw / nyq
    if normal_cutoff >= 1.0:
        return x
    b, a = signal.butter(order, normal_cutoff, btype='low', analog=False)
    y = signal.lfilter(b, a, x)
    return y

def apply_channel(x, config, baud_rate, sps):
    """ Apply sequential IMDD channel bandwidth limitations """
    fs = baud_rate * sps
    
    # E-O Conversion (MZM)
    x = lowpass_filter(x, config['mzm_bw'], fs)
    
    # O-E Conversion (PD)
    x = lowpass_filter(x, config['pd_bw'], fs)
    
    # TIA
    x = lowpass_filter(x, config['tia_bw'], fs)
    
    # Add noise based on electrical SNR
    signal_power = np.mean(x**2)
    snr_linear = 10**(config['snr_db'] / 10)
    noise_power = signal_power / snr_linear
    noise = np.random.normal(0, np.sqrt(noise_power), len(x))
    x_noisy = x + noise
    
    # ADC
    x_adc = lowpass_filter(x_noisy, config['adc_bw'], fs)
    
    return x_adc
