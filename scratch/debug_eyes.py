import numpy as np
import matplotlib.pyplot as plt
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils_config import load_config
from tx_dsp import pam4_map, tx_dsp_chain
from channel_imdd import apply_channel, lowpass_filter, rf, apply_ctle, dac_zoh
from rx_dsp import adaptive_ffe_dfe
from mlse_burg import burg_ar, viterbi_mlse_pam4
from metrics import calculate_ber, plot_eye, plot_spectrum
from scipy.signal import correlate

def custom_apply_channel(x_dac, config, baud_rate, sps_dac, sps_channel, sps_adc, out_dir, plot_spectrum_flag=False):
    """ Apply sequential IMDD channel bandwidth limitations at high sps """
    config_ch = config['channel']
    config_tx = config['tx']
    
    nyquist = baud_rate / 2
    loss_db = config_ch.get('pcb_loss_nyquist_db', 15.0)
    fc_pcb = nyquist / np.sqrt(10**(loss_db/10) - 1)
    
    x_analog = dac_zoh(x_dac, sps_dac, sps_channel)
    fs_analog = baud_rate * sps_channel
    
    plot_eye(x_analog[:sps_channel*1000], sps_channel, "01_DAC_ZOH_Out", output_dir=out_dir)
    if plot_spectrum_flag:
        plot_spectrum(x_analog, baud_rate * sps_channel, "01_DAC_ZOH_Out" + "_Spectrum", output_dir=out_dir)

    if config_tx.get('use_ctle', False):
        f_b = baud_rate
        f_z = f_b / config_tx.get('ctle_fz_ratio', 2.5)
        f_p1 = f_b / config_tx.get('ctle_fp1_ratio', 2.5)
        f_p2 = f_b / config_tx.get('ctle_fp2_ratio', 1.0)
        g_dc_db = config_tx.get('ctle_g_dc_db', -10.0)
        x_analog = apply_ctle(x_analog, fs_analog, f_z, f_p1, f_p2, g_dc_db)
        
        plot_eye(x_analog[:sps_channel*1000], sps_channel, "01b_After_Tx_CTLE", output_dir=out_dir)
        if plot_spectrum_flag:
            plot_spectrum(x_analog, baud_rate * sps_channel, "01b_After_Tx_CTLE" + "_Spectrum", output_dir=out_dir)

    # Apply PCB trace filter
    if config_ch.get('use_s4p', False) and rf is not None:
        s4p_path = config_ch.get('s4p_file', '')
        if os.path.exists(s4p_path):
            nw = rf.Network(s4p_path)
            try:
                nw.se2gmm(p=2)
                sdd21 = nw.s[:, 1, 0]
            except Exception:
                sdd21 = nw.s[:, 1, 0] if nw.s.shape[1] == 2 else nw.s[:, 0, 0]
                
            freqs = nw.f
            N = len(x_analog)
            X_analog = np.fft.rfft(x_analog)
            f_sig = np.fft.rfftfreq(N, d=1.0/fs_analog)
            
            f_scale = config_ch.get('s4p_f_scale', 1.0)
            f_sig_scaled = f_sig / f_scale
            
            # CRITICAL CHECK: padding with last value might be an issue if last value is large
            # But what is the last value?
            # Let's print the max frequency of sdd21
            print(f"S-Parameter max frequency: {freqs[-1]/1e9:.2f} GHz")
            print(f"Signal Nyquist frequency: {f_sig[-1]/1e9:.2f} GHz")
            
            sdd21_mag = np.interp(f_sig_scaled, freqs, np.abs(sdd21), left=np.abs(sdd21)[0], right=np.abs(sdd21)[-1])
            sdd21_phase = np.interp(f_sig_scaled, freqs, np.unwrap(np.angle(sdd21)), left=np.angle(sdd21)[0], right=np.angle(sdd21)[-1])
            H_channel = sdd21_mag * np.exp(1j * sdd21_phase)
            
            X_filtered = X_analog * H_channel
            x = np.fft.irfft(X_filtered, n=N)
        else:
            x = lowpass_filter(x_analog, fc_pcb, fs_analog, order=1)
    else:
        x = lowpass_filter(x_analog, fc_pcb, fs_analog, order=1)
        
    plot_eye(x[:sps_channel*1000], sps_channel, "02_After_SParameter", output_dir=out_dir)
    if plot_spectrum_flag:
        plot_spectrum(x, baud_rate * sps_channel, "02_After_SParameter" + "_Spectrum", output_dir=out_dir)

    x = lowpass_filter(x, config_ch['mzm_bw'], fs_analog)
    plot_eye(x[:sps_channel*1000], sps_channel, "03_After_MZM", output_dir=out_dir)
    if plot_spectrum_flag:
        plot_spectrum(x, baud_rate * sps_channel, "03_After_MZM" + "_Spectrum", output_dir=out_dir)
    
    loss_db = config_ch['fiber_length_km'] * config_ch['fiber_loss_db_km']
    loss_linear = 10**(-loss_db / 20.0)
    x = x * loss_linear
    plot_eye(x[:sps_channel*1000], sps_channel, "04_After_Fiber_Loss", output_dir=out_dir)
    if plot_spectrum_flag:
        plot_spectrum(x, baud_rate * sps_channel, "04_After_Fiber_Loss" + "_Spectrum", output_dir=out_dir)
    
    x = lowpass_filter(x, config_ch['pd_bw'], fs_analog)
    plot_eye(x[:sps_channel*1000], sps_channel, "05_After_PD", output_dir=out_dir)
    if plot_spectrum_flag:
        plot_spectrum(x, baud_rate * sps_channel, "05_After_PD" + "_Spectrum", output_dir=out_dir)
    
    x = lowpass_filter(x, config_ch['tia_bw'], fs_analog)
    plot_eye(x[:sps_channel*1000], sps_channel, "06_After_TIA", output_dir=out_dir)
    if plot_spectrum_flag:
        plot_spectrum(x, baud_rate * sps_channel, "06_After_TIA" + "_Spectrum", output_dir=out_dir)
    
    signal_power = np.mean(x**2)
    snr_linear = 10**(config_ch['snr_db'] / 10)
    noise_power = signal_power / snr_linear
    rng = np.random.RandomState(123)
    noise = rng.normal(0, np.sqrt(noise_power), len(x))
    x_noisy = x + noise
    plot_eye(x_noisy[:sps_channel*1000], sps_channel, "07_After_Noise", output_dir=out_dir)
    if plot_spectrum_flag:
        plot_spectrum(x_noisy, baud_rate * sps_channel, "07_After_Noise" + "_Spectrum", output_dir=out_dir)
    
    x_eq = x_noisy
        
    x_adc_in = lowpass_filter(x_eq, config_ch['adc_bw'], fs_analog)
    plot_eye(x_adc_in[:sps_channel*1000], sps_channel, "09_After_ADC_Filter", output_dir=out_dir)
    if plot_spectrum_flag:
        plot_spectrum(x_adc_in, baud_rate * sps_channel, "09_After_ADC_Filter" + "_Spectrum", output_dir=out_dir)
    
    dec_factor = sps_channel // sps_adc
    x_adc_out = x_adc_in[::dec_factor]
    plot_eye(x_adc_out[:sps_adc*1000], sps_adc, "10_ADC_Out_2sps", output_dir=out_dir)
    if plot_spectrum_flag:
        plot_spectrum(x_adc_out, baud_rate * sps_adc, "10_ADC_Out_2sps" + "_Spectrum", output_dir=out_dir)
    
    return x_analog, x_adc_in, x_adc_out

def main():
    config = load_config('config.xlsx')
    
    baud_rate = config['system']['baud_rate']
    if baud_rate == 56e9:
        mode_str = '112G'
    elif baud_rate == 112.5e9:
        mode_str = '224G'
    elif baud_rate == 212.5e9:
        mode_str = '448G'
    else:
        mode_str = 'Custom'
        
    out_dir = f"diagnostic_results/{mode_str}"
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    
    # Force default taps and -12dB CTLE for debugging
    config['tx']['custom_taps'] = [0, 0, 0, 0, 1, 0, 0, 0, 0]
    config['channel']['ctle_g_dc_db'] = -12.0
    
    sps_dsp = int(config['system']['sps_dsp'])
    sps_dac = int(config['system']['sps_dac'])
    sps_channel = int(config['system']['sps_channel'])
    sps_adc = int(config['system']['sps_adc'])
    num_symbols = int(config['system']['num_symbols'])
    
    rng = np.random.RandomState(42)
    tx_symbols = rng.randint(0, 4, num_symbols)
    tx_pam4 = pam4_map(tx_symbols)
    
    plot_spectrum_flag = config['system'].get('enable_spectrum_plot', False)
    
    tx_out = tx_dsp_chain(tx_pam4, sps_dsp, baud_rate, config['tx'])
    plot_eye(tx_out[:sps_dsp*1000], sps_dsp, "00_Tx_DSP_Out", output_dir=out_dir)
    if plot_spectrum_flag:
        plot_spectrum(tx_out, baud_rate * sps_dsp, "00_Tx_DSP_Out_Spectrum", output_dir=out_dir)
    
    _, _, rx_adc = custom_apply_channel(
        tx_out, config, baud_rate, sps_dac, sps_channel, sps_adc, out_dir, plot_spectrum_flag
    )
    
    rx_1sps = rx_adc[::sps_adc]
    corr = correlate(rx_1sps[:1000], tx_pam4[:1000])
    sync_delay = np.argmax(corr) - (len(tx_pam4[:1000]) - 1)
    print(f"sync_delay (even samples): {sync_delay}")
    
    rx_1sps_odd = rx_adc[1::sps_adc]
    corr_odd = correlate(rx_1sps_odd[:1000], tx_pam4[:1000])
    sync_delay_odd = np.argmax(corr_odd) - (len(tx_pam4[:1000]) - 1)
    
    print(f"Max corr even: {np.max(corr)}")
    print(f"Max corr odd: {np.max(corr_odd)}")
    
    rx_eq, w_ffe, w_dfe, error_seq, ffe_decisions = adaptive_ffe_dfe(
        rx_adc, tx_pam4, 
        int(config['rx']['ffe_taps']), 
        int(config['rx']['ffe_pre']),
        0, # no DFE
        config['rx']['lms_mu'], 
        0.0,
        int(config['rx']['train_len']),
        sync_delay=sync_delay
    )
    
    print(f"FFE initial taps LS: {np.round(w_ffe, 3)}")

if __name__ == '__main__':
    main()
