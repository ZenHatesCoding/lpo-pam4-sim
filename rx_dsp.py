import numpy as np

def resample_to_dsp(x, sps_sim, sps_dsp):
    """ Decimate from analog simulation domain to DSP domain """
    factor = int(sps_sim // sps_dsp)
    # Simple decimation (ADC sampling phase could be optimized, here we assume index 0)
    return x[::factor]

def adaptive_ffe(x, ref_sym, num_taps, lms_mu, train_len, sync_delay=0):
    """
    Adaptive Rx FFE (T/2 spaced, 2sps in -> 1sps out)
    x: received signal at 2 sps
    ref_sym: reference PAM4 symbols (-3, -1, 1, 3) at 1 sps
    sync_delay: known symbol delay between tx and rx to align FFE training
    """
    w = np.zeros(num_taps)
    # Initialize center tap
    w[num_taps // 2] = 1.0
    
    N_out = len(ref_sym)
    y_out = np.zeros(N_out)
    error_seq = np.zeros(N_out)
    
    for n in range(num_taps, N_out - sync_delay):
        # 1 symbol in ref corresponds to 2 samples in x
        idx = 2 * (n + sync_delay)
        if idx - num_taps + 1 < 0 or idx >= len(x):
            continue
            
        x_slice = x[idx - num_taps + 1 : idx + 1][::-1]
        
        y = np.dot(w, x_slice)
        y_out[n] = y
        
        # Error calculation
        if n < train_len:
            # LMS
            error = ref_sym[n] - y
        else:
            # DD-LMS (Hard decision slicer)
            if y > 2: d = 3
            elif y > 0: d = 1
            elif y > -2: d = -1
            else: d = -3
            error = d - y
            
        error_seq[n] = error
        
        # Tap update
        w = w + lms_mu * error * x_slice
        
    return y_out, w, error_seq
