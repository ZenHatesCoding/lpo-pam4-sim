import numpy as np

def adaptive_ffe_dfe(rx_sps, tx_ref, num_taps_ffe, ffe_pre, num_taps_dfe, mu_ffe, mu_dfe, train_len, sync_delay=0, pr_alpha=0.0):
    """
    T/2 FFE followed by T-spaced DFE with LS initialization and DD-LMS.
    rx_sps: 2sps signal
    tx_ref: 1sps reference symbols
    """
    N_sym = len(tx_ref)
    
    # Initialize with LS using training sequence
    ls_len = min(train_len, N_sym // 2)
    X_mat = []
    Y_vec = []
    
    for n in range(num_taps_ffe, ls_len):
        idx = 2 * (n + sync_delay) + ffe_pre
        if idx - num_taps_ffe + 1 < 0 or idx >= len(rx_sps):
            continue
        # FFE input
        x_slice = rx_sps[idx - num_taps_ffe + 1 : idx + 1][::-1]
        
        # DFE input (using known training symbols)
        if n >= num_taps_dfe:
            d_slice = tx_ref[n - num_taps_dfe : n][::-1]
        else:
            d_slice = np.zeros(num_taps_dfe)
            
        # Concatenate for joint LS [FFE, -DFE]
        v_slice = np.concatenate((x_slice, -d_slice))
        X_mat.append(v_slice)
        # FFE output target
        target = tx_ref[n] + pr_alpha * tx_ref[n-1]
        Y_vec.append(target)
        
    X_mat = np.array(X_mat)
    Y_vec = np.array(Y_vec)
    
    # Solve Joint LS with Ridge Regularization to prevent FSE tap explosion
    # w_ls = (X^T X + lambda I)^-1 X^T Y
    try:
        # Scale lambda with the number of training samples
        lambda_ridge = 0.05 * len(X_mat)
        XTX = X_mat.T @ X_mat
        XTY = X_mat.T @ Y_vec
        w_ls = np.linalg.solve(XTX + lambda_ridge * np.eye(XTX.shape[0]), XTY)
        
        # Initialize weights
        w_ffe = w_ls[:num_taps_ffe].copy()
        w_dfe = w_ls[num_taps_ffe:]
    except np.linalg.LinAlgError:
        print("Warning: LS failed, using default init.")
        w_ffe = np.zeros(num_taps_ffe)
        w_ffe[num_taps_ffe // 2] = 1.0
        w_dfe = np.zeros(num_taps_dfe)
        
    rx_eq = np.zeros(N_sym)
    error_seq = np.zeros(N_sym)
    ffe_decisions = np.zeros(N_sym)
    past_decisions = np.zeros(num_taps_dfe)
    
    # Run LMS loop
    d_prev = 0
    for n in range(N_sym):
        idx = 2 * (n + sync_delay) + ffe_pre
        if idx - num_taps_ffe + 1 < 0 or idx >= len(rx_sps):
            continue
            
        x_slice = rx_sps[idx - num_taps_ffe + 1 : idx + 1][::-1]
        if len(x_slice) < num_taps_ffe:
            continue
            
        # Compute output
        y_ffe = np.dot(w_ffe, x_slice)
        y_dfe = np.dot(w_dfe, past_decisions)
        y = y_ffe - y_dfe
        
        rx_eq[n] = y
        
        # Slicer
        if y > 2: d = 3
        elif y > 0: d = 1
        elif y > -2: d = -1
        else: d = -3
        
        ffe_decisions[n] = d
        
        if n < train_len:
            # Reference (for LMS)
            if n > 0:
                ref = tx_ref[n] + pr_alpha * tx_ref[n-1]
            else:
                ref = tx_ref[n]
            # In training, feed correct symbol into DFE
            d_out = tx_ref[n]
        else:
            ref = d + pr_alpha * d_prev
            d_out = d
            
        error = ref - y
        error_seq[n] = error
        
        # Update weights (LMS with tap leakage to prevent tap wandering)
        if n < train_len:
            leakage = 1e-5
            w_ffe = w_ffe * (1 - mu_ffe * leakage) + mu_ffe * error * x_slice
            if num_taps_dfe > 0:
                w_dfe = w_dfe * (1 - mu_dfe * leakage) - mu_dfe * error * past_decisions
        
        # Update DFE shift register and d_prev
        if num_taps_dfe > 0:
            past_decisions = np.roll(past_decisions, 1)
            past_decisions[0] = d_out
        d_prev = d_out
            
    return rx_eq, w_ffe, w_dfe, error_seq, ffe_decisions
