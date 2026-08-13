import numpy as np
from tx_dsp import pam4_map, tx_dsp_chain

# =====================================================================
# GPR Surrogate Engine (White-box implementation extracted and customized)
# =====================================================================
class TX_GPR_Surrogate:
    def __init__(self, noise_var=1e-3):
        self.noise_var = noise_var
        self.kernel_sigma_f = 1.0
        self.kernel_l = 1.0
        self.X_train_scaled = []
        self.y_train = []
        self.K_inv = None
        self.X_mean = None
        self.X_std = None
        
    def rbf_kernel(self, X1, X2, length_scale=None, sigma_f=None):
        if length_scale is None:
            length_scale = self.kernel_l
        if sigma_f is None:
            sigma_f = self.kernel_sigma_f
            
        X1_scaled = X1 / length_scale
        X2_scaled = X2 / length_scale
        sqdist = np.sum(X1_scaled**2, 1).reshape(-1, 1) + np.sum(X2_scaled**2, 1) - 2 * np.dot(X1_scaled, X2_scaled.T)
        return sigma_f**2 * np.exp(-0.5 * sqdist)

    def fit(self, X, y, n_hyper_steps=50, lr_hyper=0.1):
        X = np.array(X)
        self.y_train = np.array(y).reshape(-1, 1)
        
        # Z-Score Standardization for the 10D TX physical features
        self.X_mean = np.mean(X, axis=0)
        self.X_std = np.std(X, axis=0)
        self.X_std[self.X_std < 1e-8] = 1.0 # Prevent division by zero
        self.X_train_scaled = (X - self.X_mean) / self.X_std
        
        # Hyperparameter Tuning (Adam) for Isotropic RBF
        def negative_log_marginal_likelihood(params):
            sigma_f, l_scale = params[0], params[1]
            K = self.rbf_kernel(self.X_train_scaled, self.X_train_scaled, length_scale=l_scale, sigma_f=sigma_f)
            K_noise = K + self.noise_var * np.eye(len(self.X_train_scaled))
            try:
                L = np.linalg.cholesky(K_noise)
            except np.linalg.LinAlgError:
                return np.inf
            alpha = np.linalg.solve(L.T, np.linalg.solve(L, self.y_train))
            nll = 0.5 * np.dot(self.y_train.T, alpha)[0, 0] + np.sum(np.log(np.diag(L))) + 0.5 * len(self.X_train_scaled) * np.log(2*np.pi)
            return nll
            
        params = np.array([self.kernel_sigma_f, self.kernel_l])
        m = np.zeros_like(params)
        v = np.zeros_like(params)
        beta1, beta2, eps_adam = 0.9, 0.999, 1e-8
        
        for step in range(n_hyper_steps):
            current_nll = negative_log_marginal_likelihood(params)
            if current_nll == np.inf:
                break
            grad = np.zeros_like(params)
            eps = 1e-4
            for i in range(len(params)):
                params_plus = params.copy()
                params_plus[i] += eps
                nll_plus = negative_log_marginal_likelihood(params_plus)
                if nll_plus != np.inf:
                    grad[i] = (nll_plus - current_nll) / eps
                    
            m = beta1 * m + (1 - beta1) * grad
            v = beta2 * v + (1 - beta2) * (grad**2)
            m_hat = m / (1 - beta1**(step+1))
            v_hat = v / (1 - beta2**(step+1))
            
            params = params - lr_hyper * m_hat / (np.sqrt(v_hat) + eps_adam)
            params = np.clip(params, 1e-3, 10.0) # Boundaries
            
        self.kernel_sigma_f = params[0]
        self.kernel_l = params[1]
        
        # Precompute K_inv
        K = self.rbf_kernel(self.X_train_scaled, self.X_train_scaled)
        self.K_inv = np.linalg.inv(K + self.noise_var * np.eye(len(self.X_train_scaled)))
        
    def predict(self, X_s):
        # Apply the exact same Z-score normalization as training
        X_s_scaled = (np.atleast_2d(X_s) - self.X_mean) / self.X_std
        
        K_s = self.rbf_kernel(self.X_train_scaled, X_s_scaled)
        mu_s = K_s.T.dot(self.K_inv).dot(self.y_train)
        
        var_s = self.kernel_sigma_f**2 - np.sum(K_s.T.dot(self.K_inv) * K_s.T, axis=1, keepdims=True)
        var_s = np.clip(var_s, 1e-9, None)
        
        return mu_s, np.sqrt(var_s)

# =====================================================================
# Feature Extraction (unchanged physically)
# =====================================================================
def extract_tx_features(tx_pam4, tx_out, sps_dsp):
    sampled_out = tx_out[::sps_dsp]
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
            features[i] = 0.0
            features[i + 4] = 0.0
            
    mse = np.mean((out_sym - tx_sym)**2)
    features[8] = -10.0 * np.log10(mse + 1e-12)
    
    eye1 = (features[1] - features[0]) - (features[5] + features[4])
    eye2 = (features[2] - features[1]) - (features[6] + features[5])
    eye3 = (features[3] - features[2]) - (features[7] + features[6])
    features[9] = min(eye1, eye2, eye3)
    
    return features

# =====================================================================
# Main Integration Entrypoints
# =====================================================================
def build_golden_cluster(X_data, y_data, base_config):
    """
    Build a GPR Surrogate mapping TX features to log_ber
    using all points explored in Stage 1.
    """
    rng = np.random.RandomState(42)
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
        feature_list.append(features)
        
    gpr_model = TX_GPR_Surrogate()
    gpr_model.fit(feature_list, y_data)
    
    # We return the GPR model as the first argument. We pass None for dummy placeholders.
    return gpr_model, None, None, tx_pam4

def evaluate_surrogate_metric(params, gpr_model, dummy1, dummy2, tx_pam4, base_config):
    """
    Calculate the pseudo log BER using the GPR model's UCB (Upper Confidence Bound).
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
    
    mu, sigma = gpr_model.predict(X_curr)
    
    # The magical UCB absolute safety guardrail (3-Sigma)
    pseudo_log_ber = mu[0, 0] + 3.0 * sigma[0, 0]
    
    return pseudo_log_ber
