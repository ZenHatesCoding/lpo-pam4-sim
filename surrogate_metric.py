import numpy as np
from tx_dsp import pam4_map, tx_dsp_chain

def extract_tx_features(tx_pam4, tx_out, sps_dsp):
    """
    Extract statistical features (mean and std of 4 levels) from TX output.
    tx_pam4: original PAM4 symbols (-3, -1, 1, 3)
    tx_out: analog output waveform at sps_dsp
    sps_dsp: samples per symbol
    """
    # Sample the center of each symbol
    # In tx_dsp_chain, pulse shape is rect filter [1, 1] for sps_dsp=2
    # So the symbol center is at index 0 or 1 depending on alignment.
    # Usually, we can just take the first sample of the symbol period.
    sampled_out = tx_out[::sps_dsp]
    
    # Ensure lengths match (tx_out might be slightly shorter due to valid mode convolution, but mode='full'[:len] is used)
    min_len = min(len(tx_pam4), len(sampled_out))
    tx_sym = tx_pam4[:min_len]
    out_sym = sampled_out[:min_len]
    
    features = np.zeros(10)
    levels = [-3.0, -1.0, 1.0, 3.0]
    
    for i, level in enumerate(levels):
        mask = (np.abs(tx_sym - level) < 0.1)
        level_samples = out_sym[mask]
        
        if len(level_samples) > 0:
            features[i] = np.mean(level_samples)
            features[i + 4] = np.std(level_samples)
        else:
            # Fallback if somehow a level doesn't exist (should not happen for long sequences)
            features[i] = 0.0
            features[i + 4] = 0.0
            
    # Feature 8: Global SNDR proxy (MSE from ideal symbols)
    mse = np.mean((out_sym - tx_sym)**2)
    features[8] = -10.0 * np.log10(mse + 1e-12)
    
    # Feature 9: Min Eye Height
    # Eye 1: -1 to -3, Eye 2: 1 to -1, Eye 3: 3 to 1
    eye1 = (features[1] - features[0]) - (features[5] + features[4])
    eye2 = (features[2] - features[1]) - (features[6] + features[5])
    eye3 = (features[3] - features[2]) - (features[7] + features[6])
    features[9] = min(eye1, eye2, eye3)
    
    return features

def build_golden_cluster(X_data, y_data, base_config):
    """
    Build a Linear Regression statistical model mapping TX features to log_ber
    using all points explored in Stage 1.
    """
    rng = np.random.RandomState(42)
    # Use a small block of symbols to calculate TX statistics quickly
    tx_symbols = rng.randint(0, 4, 20000)
    tx_pam4 = pam4_map(tx_symbols)
    
    baud_rate = base_config['system']['baud_rate']
    sps_dsp = int(base_config['system']['sps_dsp'])
    
    feature_list = []
    
    for params in X_data:
        tx_config = base_config['tx'].copy()
        
        pre_post = np.array(params[:8])
        abs_sum = np.sum(np.abs(pre_post))
        if abs_sum > 0.6:
            pre_post = pre_post * (0.6 / abs_sum)
            
        ffe_pre = int(tx_config.get('ffe_pre', 4))
        if int(tx_config['ffe_taps']) != 9:
            ffe_pre = 1
            
        taps = np.zeros(9)
        taps[:ffe_pre] = pre_post[:ffe_pre]
        taps[ffe_pre+1:] = pre_post[ffe_pre:]
        taps[ffe_pre] = 1.0 - np.sum(np.abs(pre_post))
        
        tx_config['custom_taps'] = taps
        
        tx_out = tx_dsp_chain(tx_pam4, sps_dsp, baud_rate, tx_config)
        features = extract_tx_features(tx_pam4, tx_out, sps_dsp)
        # Add bias term
        features = np.append(features, 1.0)
        feature_list.append(features)
        
    F = np.array(feature_list)
    Y = np.array(y_data)
    
    # Ridge Regression: W = inv(F^T F + lambda I) F^T Y
    # lambda = 1.0 for regularization
    lambda_reg = 1.0
    F_T_F = np.dot(F.T, F)
    I = np.eye(F.shape[1])
    W = np.dot(np.dot(np.linalg.pinv(F_T_F + lambda_reg * I), F.T), Y)
    
    # We return W instead of mu_golden, cov_golden_inv, mapping_params
    return W, None, None, tx_pam4

def evaluate_surrogate_metric(params, W, dummy1, dummy2, tx_pam4, base_config):
    """
    Calculate the pseudo log BER using the Linear Regression model.
    """
    baud_rate = base_config['system']['baud_rate']
    sps_dsp = int(base_config['system']['sps_dsp'])
    
    tx_config = base_config['tx'].copy()
    
    pre_post = np.array(params[:8])
    abs_sum = np.sum(np.abs(pre_post))
    if abs_sum > 0.6:
        pre_post = pre_post * (0.6 / abs_sum)
        
    ffe_pre = int(tx_config.get('ffe_pre', 4))
    if int(tx_config['ffe_taps']) != 9:
        ffe_pre = 1
        
    taps = np.zeros(9)
    taps[:ffe_pre] = pre_post[:ffe_pre]
    taps[ffe_pre+1:] = pre_post[ffe_pre:]
    taps[ffe_pre] = 1.0 - np.sum(np.abs(pre_post))
    
    tx_config['custom_taps'] = taps
    
    tx_out = tx_dsp_chain(tx_pam4, sps_dsp, baud_rate, tx_config)
    X_curr = extract_tx_features(tx_pam4, tx_out, sps_dsp)
    X_curr = np.append(X_curr, 1.0) # bias term
    
    pseudo_log_ber = np.dot(W, X_curr)
    
    # Cap the pseudo log_ber to 0 (BER=1.0)
    pseudo_log_ber = min(pseudo_log_ber, 0.0)
    
    return pseudo_log_ber
