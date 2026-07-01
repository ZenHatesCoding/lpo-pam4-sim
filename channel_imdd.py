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

def dac_zoh(x, sps_in, sps_out):
    """ DAC Zero-Order Hold upsampling """
    factor = sps_out // sps_in
    return np.repeat(x, factor)

def apply_channel(x_dac, config, baud_rate, sps_dac, sps_channel, sps_adc):
    """ Apply sequential IMDD channel bandwidth limitations at high sps """
    # 1. DAC Output (ZOH)
    x_analog = dac_zoh(x_dac, sps_dac, sps_channel)
    fs_analog = baud_rate * sps_channel
    
    # 2. E-O Conversion (MZM)
    x = lowpass_filter(x_analog, config['mzm_bw'], fs_analog)
    
    # 3. Fiber Channel
    # Simple insertion loss model (linear scaling)
    # LPO does not have retimers, total loss budget is critical
    loss_db = config['fiber_length_km'] * config['fiber_loss_db_km']
    loss_linear = 10**(-loss_db / 20.0) # Voltage/Amplitude scaling
    x = x * loss_linear
    
    # 4. O-E Conversion (PD)
    x = lowpass_filter(x, config['pd_bw'], fs_analog)
    
    # 5. TIA
    x = lowpass_filter(x, config['tia_bw'], fs_analog)
    
    # 6. Add noise based on electrical SNR
    signal_power = np.mean(x**2)
    snr_linear = 10**(config['snr_db'] / 10)
    noise_power = signal_power / snr_linear
    noise = np.random.normal(0, np.sqrt(noise_power), len(x))
    x_noisy = x + noise
    
    # 7. ADC Analog Front-End (Anti-alias + Bandwidth)
    x_adc_in = lowpass_filter(x_noisy, config['adc_bw'], fs_analog)
    
    # 8. ADC Sampling
    # Downsample from sps_channel to sps_adc
    dec_factor = sps_channel // sps_adc
    x_adc_out = x_adc_in[::dec_factor]
    
    # Return both the high-rate analog signal (for plotting) and ADC output
    return x_analog, x_adc_in, x_adc_out
