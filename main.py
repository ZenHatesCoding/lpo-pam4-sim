import numpy as np
import matplotlib.pyplot as plt
import os
from utils_config import load_config
from tx_dsp import pam4_map, tx_dsp_chain
from channel_imdd import apply_channel
from rx_dsp import adaptive_ffe_dfe
from mlse_burg import burg_ar, viterbi_mlse_pam4
from metrics import calculate_ber, plot_eye
from scipy.signal import correlate

def run_sim(config, custom_tx_taps=None, plot_eyes=False):
    """
    Run a single point simulation of the LPO PAM4 link.
    Returns the MLSE BER and FFE BER.
    """
    baud_rate = config['system']['baud_rate']
    sps_dsp = int(config['system']['sps_dsp'])
    sps_dac = int(config['system']['sps_dac'])
    sps_channel = int(config['system']['sps_channel'])
    sps_adc = int(config['system']['sps_adc'])
    num_symbols = int(config['system']['num_symbols'])
    
    rng = np.random.RandomState(42)
    tx_symbols = rng.randint(0, 4, num_symbols)
    tx_pam4 = pam4_map(tx_symbols)
    
    # Optional override for Tx FFE taps
    tx_config = config['tx'].copy()
    if custom_tx_taps is not None:
        tx_config['custom_taps'] = custom_tx_taps
    else:
        # Default symmetric center tap
        default_taps = np.zeros(int(tx_config['ffe_taps']))
        default_taps[int(tx_config['ffe_pre'])] = 1.0
        tx_config['custom_taps'] = default_taps
        
    # Tx DSP
    tx_out = tx_dsp_chain(tx_pam4, sps_dsp, baud_rate, tx_config)
    
    # Channel
    tx_analog, rx_analog, rx_adc = apply_channel(
        tx_out, config['channel'], baud_rate, sps_dac, sps_channel, sps_adc
    )
    
    plot_intermediate = config['system'].get('plot_intermediate_eyes', False)
    result_dir = "result"
    
    if plot_intermediate or plot_eyes:
        if not os.path.exists(result_dir):
            os.makedirs(result_dir)
        plot_eye(tx_analog[:sps_channel*1000], sps_channel, "Tx_Analog_Out_Eye", output_dir=result_dir)
        plot_eye(rx_analog[:sps_channel*1000], sps_channel, "Rx_ADC_Input_Eye", output_dir=result_dir)
        
    # Rx DSP - Find optimal sampling phase
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
        int(config['rx']['ffe_taps']), 
        int(config['rx']['ffe_pre']),
        int(config.get('rx', {}).get('dfe_taps', 1)), # 1-tap DFE
        config['rx']['lms_mu'], 
        config['rx']['lms_mu'], 
        int(config['rx']['train_len']),
        sync_delay=sync_delay
    )
    
    ffe_symbols = np.zeros_like(ffe_decisions)
    ffe_symbols[ffe_decisions == -3] = 0; ffe_symbols[ffe_decisions == -1] = 1
    ffe_symbols[ffe_decisions == 1] = 2; ffe_symbols[ffe_decisions == 3] = 3
    
    # MLSE
    err_ss = error_seq[int(config['rx']['train_len']):]
    ar_order = int(config['rx']['mlse_memory'])
    
    if ar_order > 0:
        ar_coeffs = burg_ar(err_ss, ar_order)
        pr_taps = np.concatenate(([1.0], -ar_coeffs))
    else:
        pr_taps = [1.0]
        
    rx_eq_whitened = np.convolve(rx_eq, pr_taps, mode='full')[:len(rx_eq)]
    rx_decisions = viterbi_mlse_pam4(rx_eq_whitened, pr_taps)
    
    rx_symbols = np.zeros_like(rx_decisions)
    rx_symbols[rx_decisions == -3] = 0; rx_symbols[rx_decisions == -1] = 1
    rx_symbols[rx_decisions == 1] = 2; rx_symbols[rx_decisions == 3] = 3
    
    train_len = int(config['rx']['train_len'])
    tx_aligned = tx_symbols[train_len:]
    ffe_aligned = ffe_symbols[train_len:]
    mlse_aligned = rx_symbols[train_len:]
    
    min_len = min(len(tx_aligned), len(ffe_aligned), len(mlse_aligned))
    ffe_ser, ffe_ber = calculate_ber(tx_aligned[:min_len], ffe_aligned[:min_len])
    mlse_ser, mlse_ber = calculate_ber(tx_aligned[:min_len], mlse_aligned[:min_len])
    
    return ffe_ber, mlse_ber

if __name__ == '__main__':
    print("--- Running Default LPO PAM4 Simulation ---")
    config = load_config('config.xlsx')
    
    ffe_ber, mlse_ber = run_sim(config, plot_eyes=config['system'].get('plot_intermediate_eyes', False))
    
    result_str = f"FFE BER: {ffe_ber:.2e}, MLSE BER: {mlse_ber:.2e}\n"
    print(result_str)
    
    result_dir = "result"
    if not os.path.exists(result_dir):
        os.makedirs(result_dir)
        
    with open(os.path.join(result_dir, "sim_log.txt"), "a") as f:
        f.write("--- Simulation Result ---\n")
        f.write(result_str)
