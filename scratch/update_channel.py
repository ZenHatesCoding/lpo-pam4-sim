import re

def update():
    with open('channel_imdd.py', 'r') as f:
        content = f.read()

    # Define the new helper function
    new_helper = '''
def apply_s4p_filter(x, fs, config_ch, target_il_key, nyquist):
    s4p_path = config_ch.get('s4p_file', '')
    if not os.path.exists(s4p_path):
        return None
    
    nw = _load_s4p_cached(s4p_path)
    try:
        S21 = nw.s[:, 1, 0]
        S23 = nw.s[:, 1, 2]
        S41 = nw.s[:, 3, 0]
        S43 = nw.s[:, 3, 2]
        sdd21 = 0.5 * (S21 - S23 - S41 + S43)
    except Exception:
        sdd21 = nw.s[:, 1, 0] if nw.s.shape[1] == 2 else nw.s[:, 0, 0]
        
    freqs = nw.f
    N = len(x)
    X = np.fft.rfft(x)
    f_sig = np.fft.rfftfreq(N, d=1.0/fs)
    
    # Fallback to old key if new key doesn't exist
    il_key_to_use = target_il_key if target_il_key in config_ch else 'target_il_nyquist_db'
    
    if il_key_to_use in config_ch:
        f_scale = find_f_scale_for_target_il(freqs, sdd21, -abs(config_ch[il_key_to_use]), nyquist)
        print(f"Dynamic S-parameter scaling to hit -{abs(config_ch[il_key_to_use])} dB IL for {target_il_key}. Computed f_scale = {f_scale:.3f}")
    else:
        f_scale = config_ch.get('s4p_f_scale', 1.0)
        
    f_sig_scaled = f_sig / f_scale
    sdd21_mag = np.interp(f_sig_scaled, freqs, np.abs(sdd21), left=np.abs(sdd21)[0], right=0.0)
    sdd21_phase = np.interp(f_sig_scaled, freqs, np.unwrap(np.angle(sdd21)), left=np.angle(sdd21)[0], right=0.0)
    H_channel = sdd21_mag * np.exp(1j * sdd21_phase)
    
    X_filtered = X * H_channel
    return np.fft.irfft(X_filtered, n=N)

def apply_channel(x_dac, config, baud_rate, sps_dac, sps_channel, sps_adc):'''

    # Split the original content
    parts = content.split('def apply_channel(x_dac, config, baud_rate, sps_dac, sps_channel, sps_adc):')
    
    if len(parts) != 2:
        print("Could not find apply_channel function")
        return
        
    new_body = '''
    config_ch = config['channel']
    config_tx = config['tx']
    """ Apply sequential IMDD channel bandwidth limitations at high sps """
    nyquist = baud_rate / 2
    
    # Tx Electrical Loss
    loss_db_tx = config_ch.get('tx_pcb_loss_nyquist_db', config_ch.get('pcb_loss_nyquist_db', 15.0))
    fc_pcb_tx = nyquist / np.sqrt(10**(loss_db_tx/10) - 1)
    
    # Rx Electrical Loss
    loss_db_rx = config_ch.get('rx_pcb_loss_nyquist_db', 15.0)
    fc_pcb_rx = nyquist / np.sqrt(10**(loss_db_rx/10) - 1)
    
    rng = np.random.RandomState(123)

    # 2. DAC Output (ZOH)
    x = dac_zoh(x_dac, sps_dac, sps_channel)
    fs_analog = baud_rate * sps_channel

    # [Host Tx Noise]
    if config_ch.get('use_distributed_noise', False):
        x += rng.normal(0, config_ch.get('host_tx_noise_rms', 0.0), len(x))

    # --- Apply Tx CTLE (Analog Equalization before channel) ---
    if config_tx.get('use_ctle', False):
        f_b = baud_rate
        f_z = f_b / config_tx.get('ctle_fz_ratio', 2.5)
        f_p1 = f_b / config_tx.get('ctle_fp1_ratio', 2.5)
        f_p2 = f_b / config_tx.get('ctle_fp2_ratio', 1.0)
        g_dc_db = config_tx.get('ctle_g_dc_db', -10.0)
        x = apply_ctle(x, fs_analog, f_z, f_p1, f_p2, g_dc_db)
    # ----------------------------------------------------------
    
    # --- ISI BYPASS (DEBUG MODE) ---
    if config_ch.get('disable_isi', False):
        loss_db = config_ch.get('target_il_nyquist_db', 18.0)
        x = x * (10 ** (-abs(loss_db) / 20.0))
        fiber_loss_db = config_ch['fiber_length_km'] * config_ch['fiber_loss_db_km']
        x = x * (10 ** (-fiber_loss_db / 20.0))
        signal_power = np.mean(x**2)
        snr_linear = 10**(config_ch['snr_db'] / 10)
        noise_power = signal_power / snr_linear
        noise = rng.normal(0, np.sqrt(noise_power), len(x))
        x_noisy = x + noise
        dec_factor = sps_channel // sps_adc
        x_adc_out = x_noisy[::dec_factor]
        return x, x_noisy, x_adc_out
    # -------------------------------
    
    # [Host Tx to Module Tx]
    if config_ch.get('use_s4p', False) and rf is not None:
        x_filtered = apply_s4p_filter(x, fs_analog, config_ch, 'tx_pcb_loss_nyquist_db', nyquist)
        if x_filtered is not None:
            x = x_filtered
        else:
            print(f"Warning: S4P file not found. Using analytical filter.")
            x = lowpass_filter(x, fc_pcb_tx, fs_analog, order=1)
    else:
        x = lowpass_filter(x, fc_pcb_tx, fs_analog, order=1)
        
    x_analog = x.copy()
    
    # [Module Tx Noise]
    if config_ch.get('use_distributed_noise', False):
        x += rng.normal(0, config_ch.get('module_tx_noise_rms', 0.0), len(x))

    # 3. E-O Conversion (MZM)
    x = lowpass_filter(x, config_ch['mzm_bw'], fs_analog)
    
    # 3. Fiber Channel
    loss_db = config_ch['fiber_length_km'] * config_ch['fiber_loss_db_km']
    loss_linear = 10**(-loss_db / 20.0)
    x = x * loss_linear
    
    cd_ps_nm = config_ch.get('cd_ps_nm', 0.0)
    dgd_ps = config_ch.get('dgd_ps', 0.0)
    pol_angle_deg = config_ch.get('pol_angle_deg', 45.0)
    if cd_ps_nm != 0 or dgd_ps != 0:
        x = apply_cd_dgd(x, fs_analog, cd_ps_nm, dgd_ps, pol_angle_deg)
    
    # 4. O-E Conversion (PD)
    x = lowpass_filter(x, config_ch['pd_bw'], fs_analog)
    
    # 5. TIA
    x = lowpass_filter(x, config_ch['tia_bw'], fs_analog)
    
    # [Module Rx Noise]
    if config_ch.get('use_distributed_noise', False):
        x += rng.normal(0, config_ch.get('module_rx_noise_rms', 0.0), len(x))

    # [Module Rx to Host Rx]
    if config_ch.get('use_s4p', False) and rf is not None:
        x_filtered = apply_s4p_filter(x, fs_analog, config_ch, 'rx_pcb_loss_nyquist_db', nyquist)
        if x_filtered is not None:
            x = x_filtered
        else:
            x = lowpass_filter(x, fc_pcb_rx, fs_analog, order=1)
    else:
        x = lowpass_filter(x, fc_pcb_rx, fs_analog, order=1)
        
    # [Host Rx Noise] / Fallback Noise
    if config_ch.get('use_distributed_noise', False):
        x += rng.normal(0, config_ch.get('host_rx_noise_rms', 0.0), len(x))
    else:
        signal_power = np.mean(x**2)
        snr_linear = 10**(config_ch['snr_db'] / 10)
        noise_power = signal_power / snr_linear
        noise = rng.normal(0, np.sqrt(noise_power), len(x))
        x = x + noise
        
    x_eq = x
    
    # 8. ADC Analog Front-End (Anti-alias + Bandwidth)
    x_adc_in = lowpass_filter(x_eq, config_ch['adc_bw'], fs_analog)
    
    # 9. ADC Sampling
    dec_factor = sps_channel // sps_adc
    x_adc_out = x_adc_in[::dec_factor]
    
    return x_analog, x_adc_in, x_adc_out
'''

    with open('channel_imdd.py', 'w') as f:
        f.write(parts[0] + new_helper + new_body)

if __name__ == '__main__':
    update()
