import numpy as np

def adaptive_ffe(x, ref_sym, num_taps, lms_mu, train_len, sync_delay=0):
    """
    Adaptive Rx FFE (T/2 spaced, 2sps in -> 1sps out)
    """
    w = np.zeros(num_taps)
    w[num_taps // 2] = 1.0
    
    N_out = len(ref_sym)
    y_out = np.zeros(N_out)
    error_seq = np.zeros(N_out)
    decisions = np.zeros(N_out)
    
    for n in range(num_taps, N_out - sync_delay):
        idx = 2 * (n + sync_delay)
        if idx - num_taps + 1 < 0 or idx >= len(x):
            continue
            
        x_slice = x[idx - num_taps + 1 : idx + 1][::-1]
        
        y = np.dot(w, x_slice)
        y_out[n] = y
        
        # Hard decision slicer
        if y > 2: d = 3
        elif y > 0: d = 1
        elif y > -2: d = -1
        else: d = -3
        decisions[n] = d
        
        if n < train_len:
            error = ref_sym[n] - y
        else:
            error = d - y
            
        error_seq[n] = error
        w = w + lms_mu * error * x_slice
        
    return y_out, w, error_seq, decisions
