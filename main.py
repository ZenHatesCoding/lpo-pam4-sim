import numpy as np
import matplotlib.pyplot as plt
from utils_config import load_config
from tx_dsp import pam4_map, upsample, tx_ctle, tx_ffe, pulse_shape
from channel_imdd import apply_channel
from rx_dsp import resample_to_dsp, adaptive_ffe
from mlse_burg import burg_ar, viterbi_mlse_pam4
from metrics import calculate_ber, plot_eye

def main():
    # 1. Load config
    config = load_config('config.xlsx')
    
    baud_rate = config['system']['baud_rate']
    sps_sim = int(config['system']['sps_sim'])
    sps_dsp = int(config['system']['sps_dsp'])
    num_symbols = int(config['system']['num_symbols'])
    
    print(f"--- Running LPO PAM4 Simulation ---")
    print(f"Baud Rate: {baud_rate/1e9} GBd")
    
    # 2. Tx DSP
    print("Generating Tx sequence...")
    np.random.seed(42)
    tx_symbols = np.random.randint(0, 4, num_symbols)
    tx_pam4 = pam4_map(tx_symbols)
    
    tx_up = upsample(tx_pam4, sps_sim)
    tx_shaped = pulse_shape(tx_up, sps_sim)
    
    # Tx CTLE & FFE
    tx_eq = tx_ctle(tx_shaped, sps_sim, baud_rate, 
                    config['tx']['ctle_dc_gain'], 
                    config['tx']['ctle_peaking'])
    
    tx_taps = np.zeros(int(config['tx']['ffe_taps']))
    tx_taps[int(config['tx']['ffe_pre'])] = 1.0 # simplistic initialization
    # In a real system, Tx taps are pre-calculated. We just set a pass-through here
    
    tx_out = tx_ffe(tx_eq, tx_taps, sps_sim)
    
    # Eye Diagram at Tx
    plot_eye(tx_out[:sps_sim*1000], sps_sim, "Tx Output Eye")
    
    # 3. Channel
    print("Applying IMDD Channel...")
    rx_analog = apply_channel(tx_out, config['channel'], baud_rate, sps_sim)
    plot_eye(rx_analog[:sps_sim*1000], sps_sim, "Rx ADC Output Eye")
    
    # 4. Rx DSP
    print("Rx DSP processing...")
    rx_dsp_in = resample_to_dsp(rx_analog, sps_sim, sps_dsp)
    
    # Delay matching for reference symbols
    from scipy.signal import correlate
    rx_1sps = rx_dsp_in[::sps_dsp]
    # compute correlation on the first 1000 symbols
    corr = correlate(rx_1sps[:1000], tx_pam4[:1000])
    sync_delay = np.argmax(corr) - (len(tx_pam4[:1000]) - 1)
    print(f"Estimated Channel Symbol Delay: {sync_delay}")
    
    ref_sym = tx_pam4
    
    # Rx FFE
    rx_eq, w_ffe, error_seq = adaptive_ffe(rx_dsp_in, ref_sym, 
                                           int(config['rx']['ffe_taps']), 
                                           config['rx']['lms_mu'], 
                                           int(config['rx']['train_len']),
                                           sync_delay=sync_delay)
    
    # 5. MLSE with Burg
    print("Running MLSE with Burg AR estimation...")
    # Estimate AR parameters on the steady-state error
    err_ss = error_seq[int(config['rx']['train_len']):]
    ar_order = int(config['rx']['mlse_memory'])
    
    if ar_order > 0:
        ar_coeffs = burg_ar(err_ss, ar_order)
        print(f"Estimated PR target taps (AR coeffs): {ar_coeffs}")
        pr_taps = np.concatenate(([1.0], -ar_coeffs))
    else:
        pr_taps = [1.0]
        
    rx_decisions = viterbi_mlse_pam4(rx_eq, pr_taps)
    
    # Map back to symbols
    rx_symbols = np.zeros_like(rx_decisions)
    rx_symbols[rx_decisions == -3] = 0
    rx_symbols[rx_decisions == -1] = 1
    rx_symbols[rx_decisions == 1] = 2
    rx_symbols[rx_decisions == 3] = 3
    
    # 6. Metrics
    # Align for BER calculation due to filter delays
    align_offset = 0 # adaptive FFE attempts to align to ref_sym directly
    tx_aligned = tx_symbols[int(config['rx']['train_len']):]
    rx_aligned = rx_symbols[int(config['rx']['train_len']):]
    
    ser, ber = calculate_ber(tx_aligned, rx_aligned)
    print(f"SER: {ser:.2e}, BER: {ber:.2e}")
    print("Simulation Complete. Eye diagrams saved as PNG.")

if __name__ == '__main__':
    main()
