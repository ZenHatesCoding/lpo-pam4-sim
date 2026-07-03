import numpy as np

def adaptive_ffe(x, ref_sym, num_taps, lms_mu, train_len, sync_delay=0):
    """
    Adaptive Rx FFE (T/2 spaced, 2sps in -> 1sps out)
    Uses Least Squares (LS) for initial tap weights over the training sequence,
    then switches to Decision-Directed LMS (DD-LMS) for tracking.
    """
    start_n = num_taps
    
    # 1. Least Squares (LS) Initialization over training sequence
    X_mat = []
    Y_vec = []
    
    for n in range(start_n, train_len):
        idx = 2 * (n + sync_delay)
        if idx - num_taps + 1 < 0 or idx >= len(x):
            continue
        x_slice = x[idx - num_taps + 1 : idx + 1][::-1]
        X_mat.append(x_slice)
        Y_vec.append(ref_sym[n])
        
    X_mat = np.array(X_mat)
    Y_vec = np.array(Y_vec)
    
    if len(X_mat) > num_taps:
        # Ridge regression to prevent singular matrix
        ridge_alpha = 1e-4 * np.eye(num_taps)
        w = np.linalg.solve(X_mat.T @ X_mat + ridge_alpha, X_mat.T @ Y_vec)
    else:
        # Fallback to blind start if training sequence is too short
        w = np.zeros(num_taps)
        w[num_taps // 2] = 1.0
        
    # 2. Apply FFE and track with DD-LMS
    N_out = len(ref_sym)
    y_out = np.zeros(N_out)
    error_seq = np.zeros(N_out)
    decisions = np.zeros(N_out)
    
    for n in range(start_n, N_out - sync_delay):
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
            # We already optimized w for n < train_len via LS, no need to update
        else:
            # DD-LMS tracking
            error = d - y
            w = w + lms_mu * error * x_slice
            
        error_seq[n] = error
        
    return y_out, w, error_seq, decisions
