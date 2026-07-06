import numpy as np
from scipy import signal
import os

try:
    import skrf as rf
except ImportError:
    rf = None

def lowpass_filter(x, bw, fs, order=4):
    """ Butterworth low-pass filter """
    nyq = 0.5 * fs
    normal_cutoff = bw / nyq
    if normal_cutoff >= 1.0:
        return x
    b, a = signal.butter(order, normal_cutoff, btype='low', analog=False)
    y = signal.lfilter(b, a, x)
    return y

def apply_ctle(x, fs, f_z, f_p1, f_p2, g_dc_db):
    """
    Apply IEEE COM standard 2-pole 1-zero CTLE in the frequency domain.
    H(f) = (10^(G_DC/20) + j*f/f_z) / (1 + j*f/f_p1) / (1 + j*f/f_p2)
    """
    N = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(N, d=1.0/fs)
    
    g_dc = 10**(g_dc_db / 20)
    
    # Avoid 0 division in formula by adding a small epsilon to f, or just handle f=0
    # Actually f_z, f_p1, f_p2 are strictly > 0 so no division by zero.
    num = g_dc + 1j * f / f_z
    den = (1 + 1j * f / f_z) * (1 + 1j * f / f_p1) * (1 + 1j * f / f_p2)
    
    H_ctle = num / den
    
    X_filtered = X * H_ctle
    return np.fft.irfft(X_filtered, n=N)

def dac_zoh(x, sps_in, sps_out):
    """ DAC Zero-Order Hold upsampling """
    factor = sps_out // sps_in
    return np.repeat(x, factor)

def find_f_scale_for_target_il(freqs, sdd21, target_il_db, nyquist):
    """ Find the frequency scaling factor to hit exactly target_il_db at nyquist """
    mag_db = 20 * np.log10(np.abs(sdd21) + 1e-12)
    idx = np.where(mag_db <= target_il_db)[0]
    if len(idx) > 0:
        first_cross_idx = idx[0]
        if first_cross_idx > 0:
            f1, f2 = freqs[first_cross_idx-1], freqs[first_cross_idx]
            m1, m2 = mag_db[first_cross_idx-1], mag_db[first_cross_idx]
            f_match = f1 + (target_il_db - m1) / (m2 - m1) * (f2 - f1)
        else:
            f_match = freqs[0]
    else:
        f_match = freqs[-1]
        
    if f_match <= 0:
        f_match = 1e9
        
    f_scale = nyquist / f_match
    return f_scale

def apply_channel(x_dac, config, baud_rate, sps_dac, sps_channel, sps_adc):
    """ Apply sequential IMDD channel bandwidth limitations at high sps """
    # 1. PCB Trace (Host Tx to Module)
    # Model as 1st order lowpass filter.
    # We want a specific insertion loss at Nyquist (e.g., 15 dB at 28 GHz)
    # -10 * log10(1 + (f/fc)^2) = -loss_db  =>  fc = nyquist / sqrt(10**(loss_db/10) - 1)
    nyquist = baud_rate / 2
    loss_db = config.get('pcb_loss_nyquist_db', 15.0)
    fc_pcb = nyquist / np.sqrt(10**(loss_db/10) - 1)
    
    # 2. DAC Output (ZOH)
    x_analog = dac_zoh(x_dac, sps_dac, sps_channel)
    fs_analog = baud_rate * sps_channel
    
    # --- ISI BYPASS (DEBUG MODE) ---
    if config.get('disable_isi', False):
        # 1. Apply flat attenuation (target IL) instead of frequency-dependent PCB loss
        loss_db = config.get('target_il_nyquist_db', 18.0)
        x = x_analog * (10 ** (-abs(loss_db) / 20.0))
        
        # 2. Add fiber loss
        fiber_loss_db = config['fiber_length_km'] * config['fiber_loss_db_km']
        x = x * (10 ** (-fiber_loss_db / 20.0))
        
        # 3. Add noise
        signal_power = np.mean(x**2)
        snr_linear = 10**(config['snr_db'] / 10)
        noise_power = signal_power / snr_linear
        rng = np.random.RandomState(123)
        noise = rng.normal(0, np.sqrt(noise_power), len(x))
        x_noisy = x + noise
        
        # 4. Downsample to ADC directly
        dec_factor = sps_channel // sps_adc
        x_adc_out = x_noisy[::dec_factor]
        return x_analog, x_noisy, x_adc_out
    # -------------------------------
    
    # Apply PCB trace filter
    if config.get('use_s4p', False) and rf is not None:
        s4p_path = config.get('s4p_file', '')
        if os.path.exists(s4p_path):
            # Load Touchstone file
            nw = rf.Network(s4p_path)
            
            # Sdd21 for differential. The 802.3dj models are usually 4-port:
            # 1,3 are input, 2,4 are output. Sdd21 = 0.5 * (S21 - S23 - S41 + S43)
            # skrf handles mixed mode conversion: 
            # nw_mm = nw.copy()
            # nw_mm.se2gmm(p=2) # 2 differential ports
            try:
                # IEEE 802.3dj port mapping: 1,3 are input, 2,4 are output
                S21 = nw.s[:, 1, 0]
                S23 = nw.s[:, 1, 2]
                S41 = nw.s[:, 3, 0]
                S43 = nw.s[:, 3, 2]
                sdd21 = 0.5 * (S21 - S23 - S41 + S43)
            except Exception:
                # Fallback if it's a 2-port file or different mapping
                sdd21 = nw.s[:, 1, 0] if nw.s.shape[1] == 2 else nw.s[:, 0, 0]
                
            freqs = nw.f
            
            # FFT of the signal
            N = len(x_analog)
            X_analog = np.fft.rfft(x_analog)
            f_sig = np.fft.rfftfreq(N, d=1.0/fs_analog)
            
            # Interpolate S-parameter to signal frequencies
            # Sdd21 is complex. Apply mathematical frequency stretching (ZTE CBW scaling)
            if 'target_il_nyquist_db' in config:
                f_scale = find_f_scale_for_target_il(freqs, sdd21, -abs(config['target_il_nyquist_db']), nyquist)
                print(f"Dynamic S-parameter scaling to hit -{abs(config['target_il_nyquist_db'])} dB IL. Computed f_scale = {f_scale:.3f}")
            else:
                f_scale = config.get('s4p_f_scale', 1.0)
                
            f_sig_scaled = f_sig / f_scale
            
            sdd21_mag = np.interp(f_sig_scaled, freqs, np.abs(sdd21), left=np.abs(sdd21)[0], right=0.0)
            sdd21_phase = np.interp(f_sig_scaled, freqs, np.unwrap(np.angle(sdd21)), left=np.angle(sdd21)[0], right=0.0)
            H_channel = sdd21_mag * np.exp(1j * sdd21_phase)
            
            # Apply filter
            X_filtered = X_analog * H_channel
            x = np.fft.irfft(X_filtered, n=N)
        else:
            print(f"Warning: S4P file {s4p_path} not found. Using analytical filter.")
            x = lowpass_filter(x_analog, fc_pcb, fs_analog, order=1)
    else:
        x = lowpass_filter(x_analog, fc_pcb, fs_analog, order=1)
    
    # 3. E-O Conversion (MZM)
    x = lowpass_filter(x, config['mzm_bw'], fs_analog)
    
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
    rng = np.random.RandomState(123)
    noise = rng.normal(0, np.sqrt(noise_power), len(x))
    x_noisy = x + noise
    
    # 7. Apply CTLE (Analog Equalization before ADC)
    if config.get('use_ctle', False):
        f_b = baud_rate
        f_z = f_b / config.get('ctle_fz_ratio', 2.5)
        f_p1 = f_b / config.get('ctle_fp1_ratio', 2.5)
        f_p2 = f_b / config.get('ctle_fp2_ratio', 1.0)
        g_dc_db = config.get('ctle_g_dc_db', -10.0) # E.g., -10 dB DC gain means 10dB peaking
        
        x_eq = apply_ctle(x_noisy, fs_analog, f_z, f_p1, f_p2, g_dc_db)
    else:
        x_eq = x_noisy
    
    # 8. ADC Analog Front-End (Anti-alias + Bandwidth)
    x_adc_in = lowpass_filter(x_eq, config['adc_bw'], fs_analog)
    
    # 9. ADC Sampling
    # Downsample from sps_channel to sps_adc
    dec_factor = sps_channel // sps_adc
    x_adc_out = x_adc_in[::dec_factor]
    
    # Return both the high-rate analog signal (for plotting) and ADC output
    return x_analog, x_adc_in, x_adc_out
