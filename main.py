import numpy as np
import matplotlib.pyplot as plt
import os
from utils_config import load_config
from tx_dsp import pam4_map, tx_dsp_chain
from channel_imdd import apply_channel
from rx_dsp import adaptive_ffe
from mlse_burg import burg_ar, viterbi_mlse_pam4
from metrics import calculate_ber, plot_eye
from scipy.signal import correlate

def main():
    if not os.path.exists('docs'):
        os.makedirs('docs')
        
    # 1. Load config
    config = load_config('config.xlsx')
    
    baud_rate = config['system']['baud_rate']
    sps_dsp = int(config['system']['sps_dsp'])
    sps_dac = int(config['system']['sps_dac'])
    sps_channel = int(config['system']['sps_channel'])
    sps_adc = int(config['system']['sps_adc'])
    num_symbols = int(config['system']['num_symbols'])
    
    print(f"--- Running LPO PAM4 Simulation (V2) ---")
    print(f"Baud Rate: {baud_rate/1e9} GBd")
    print(f"Sampling Rates -> DSP/DAC: {sps_dsp}sps, Channel: {sps_channel}sps, ADC: {sps_adc}sps")
    
    # 2. Tx DSP
    print("Generating Tx sequence and running Tx DSP...")
    np.random.seed(42)
    tx_symbols = np.random.randint(0, 4, num_symbols)
    tx_pam4 = pam4_map(tx_symbols)
    
    # Tx DSP runs at sps_dsp (2sps)
    tx_out = tx_dsp_chain(tx_pam4, sps_dsp, baud_rate, config['tx'])
    
    # 3. Channel
    print("Applying IMDD Channel (Analog Domain)...")
    tx_analog, rx_analog, rx_adc = apply_channel(
        tx_out, config['channel'], baud_rate, sps_dac, sps_channel, sps_adc
    )
    
    # Plot High-Rate Analog Eyes
    plot_eye(tx_analog[:sps_channel*1000], sps_channel, "docs/Tx_Analog_Output_Eye")
    plot_eye(rx_analog[:sps_channel*1000], sps_channel, "docs/Rx_ADC_Input_Eye")
    
    # 4. Rx DSP
    print("Rx DSP processing...")
    
    # Delay matching
    rx_1sps = rx_adc[::sps_adc]
    corr = correlate(rx_1sps[:1000], tx_pam4[:1000])
    sync_delay = np.argmax(corr) - (len(tx_pam4[:1000]) - 1)
    print(f"Estimated Channel Symbol Delay: {sync_delay}")
    
    ref_sym = tx_pam4
    
    rx_eq, w_ffe, error_seq, ffe_decisions = adaptive_ffe(
        rx_adc, ref_sym, 
        int(config['rx']['ffe_taps']), 
        config['rx']['lms_mu'], 
        int(config['rx']['train_len']),
        sync_delay=sync_delay
    )
    
    # Map FFE decisions to symbols
    ffe_symbols = np.zeros_like(ffe_decisions)
    ffe_symbols[ffe_decisions == -3] = 0
    ffe_symbols[ffe_decisions == -1] = 1
    ffe_symbols[ffe_decisions == 1] = 2
    ffe_symbols[ffe_decisions == 3] = 3
    
    # 5. MLSE with Burg
    print("Running MLSE with Burg AR estimation...")
    err_ss = error_seq[int(config['rx']['train_len']):]
    ar_order = int(config['rx']['mlse_memory'])
    
    if ar_order > 0:
        ar_coeffs = burg_ar(err_ss, ar_order)
        print(f"Estimated PR target taps (AR coeffs): {ar_coeffs}")
        pr_taps = np.concatenate(([1.0], -ar_coeffs))
    else:
        pr_taps = [1.0]
        
    # [BUG FIX]: The FFE output (rx_eq) contains colored noise. 
    # We must filter it with the PR target (whitening filter) before Viterbi MLSE.
    rx_eq_whitened = np.convolve(rx_eq, pr_taps, mode='full')[:len(rx_eq)]
    
    rx_decisions = viterbi_mlse_pam4(rx_eq_whitened, pr_taps)
    
    # Map MLSE decisions back to symbols
    rx_symbols = np.zeros_like(rx_decisions)
    rx_symbols[rx_decisions == -3] = 0
    rx_symbols[rx_decisions == -1] = 1
    rx_symbols[rx_decisions == 1] = 2
    rx_symbols[rx_decisions == 3] = 3
    
    # 6. Metrics
    train_len = int(config['rx']['train_len'])
    tx_aligned = tx_symbols[train_len:]
    ffe_aligned = ffe_symbols[train_len:]
    mlse_aligned = rx_symbols[train_len:]
    
    # We must ensure we don't index out of bounds due to delay clipping in FFE
    min_len = min(len(tx_aligned), len(ffe_aligned), len(mlse_aligned))
    tx_aligned = tx_aligned[:min_len]
    ffe_aligned = ffe_aligned[:min_len]
    mlse_aligned = mlse_aligned[:min_len]
    
    ffe_ser, ffe_ber = calculate_ber(tx_aligned, ffe_aligned)
    mlse_ser, mlse_ber = calculate_ber(tx_aligned, mlse_aligned)
    
    print("-" * 30)
    print(f"FFE  Output SER: {ffe_ser:.2e}, BER: {ffe_ber:.2e}")
    print(f"MLSE Output SER: {mlse_ser:.2e}, BER: {mlse_ber:.2e}")
    print("-" * 30)
    print("Simulation Complete. Eye diagrams saved to docs/ directory.")

if __name__ == '__main__':
    main()
