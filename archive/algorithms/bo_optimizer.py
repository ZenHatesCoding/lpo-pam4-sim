import numpy as np
from scipy.stats import norm

class BayesianOptimizer:
    def __init__(self, bounds, noise_var=1e-4):
        self.bounds = np.array(bounds) # Shape (D, 2)
        self.D = len(bounds)
        self.noise_var = noise_var
        
        # Hyperparameters (Will be tuned by white-box Adam in fit())
        self.kernel_sigma_f = 1.0
        self.kernel_l = np.ones(self.D)
        self.kernel_l[-1] = 20.0 # CTLE has a larger range
        
        self.X_train = []
        self.y_train = []
        self.K_inv = None
        self.y_best = np.inf

    def rbf_kernel(self, X1, X2, length_scale=None, sigma_f=None):
        """ ARD Anisotropic RBF Kernel """
        if length_scale is None:
            length_scale = self.kernel_l
        if sigma_f is None:
            sigma_f = self.kernel_sigma_f
            
        X1_scaled = X1 / length_scale
        X2_scaled = X2 / length_scale
        sqdist = np.sum(X1_scaled**2, 1).reshape(-1, 1) + np.sum(X2_scaled**2, 1) - 2 * np.dot(X1_scaled, X2_scaled.T)
        return sigma_f**2 * np.exp(-0.5 * sqdist)

    def fit(self, X, y, n_hyper_steps=50, lr_hyper=0.05):
        self.X_train = np.array(X)
        self.y_train = np.array(y).reshape(-1, 1)
        self.y_best = np.min(self.y_train)
        
        # Negative Log Marginal Likelihood for Hyperparameter Tuning
        def negative_log_marginal_likelihood(params):
            sigma_f = params[0]
            length_scale = params[1:]
            
            K = self.rbf_kernel(self.X_train, self.X_train, length_scale, sigma_f)
            K_noise = K + self.noise_var * np.eye(len(self.X_train))
            
            try:
                L = np.linalg.cholesky(K_noise)
            except np.linalg.LinAlgError:
                return np.inf # Penalize invalid configurations
                
            alpha = np.linalg.solve(L.T, np.linalg.solve(L, self.y_train))
            nll = 0.5 * np.dot(self.y_train.T, alpha)[0, 0] + np.sum(np.log(np.diag(L))) + 0.5 * len(self.X_train) * np.log(2*np.pi)
            return nll
            
        # -------------------------------------------------------------
        # White-Box Hyperparameter Tuning (Adam Gradient Descent)
        # -------------------------------------------------------------
        params = np.concatenate(([self.kernel_sigma_f], self.kernel_l))
        m = np.zeros_like(params)
        v = np.zeros_like(params)
        beta1, beta2, eps_adam = 0.9, 0.999, 1e-8
        
        for step in range(n_hyper_steps):
            current_nll = negative_log_marginal_likelihood(params)
            if current_nll == np.inf:
                break
                
            grad = np.zeros_like(params)
            eps = 1e-4
            
            # Finite difference for gradient
            for i in range(len(params)):
                params_plus = params.copy()
                params_plus[i] += eps
                nll_plus = negative_log_marginal_likelihood(params_plus)
                if nll_plus != np.inf:
                    grad[i] = (nll_plus - current_nll) / eps
                
            # Adam update rules
            m = beta1 * m + (1 - beta1) * grad
            v = beta2 * v + (1 - beta2) * (grad**2)
            m_hat = m / (1 - beta1**(step+1))
            v_hat = v / (1 - beta2**(step+1))
            
            params = params - lr_hyper * m_hat / (np.sqrt(v_hat) + eps_adam)
            
            # Projected Bounds (Clipping)
            params[0] = np.clip(params[0], 1e-3, 5.0) # sigma_f bounds
            params[1:-1] = np.clip(params[1:-1], 0.05, 0.5) # L_FFE bounds (prevent collapse)
            params[-1] = np.clip(params[-1], 1.0, 20.0) # L_CTLE bounds

        # Update with tuned parameters
        self.kernel_sigma_f = params[0]
        self.kernel_l = params[1:]
        
        print(f"  [BO Tuned] sigma_f={self.kernel_sigma_f:.2f} | L_FFE_avg={np.mean(self.kernel_l[:-1]):.2f} | L_CTLE={self.kernel_l[-1]:.1f}")
        
        # Finalize K_inv for predictions
        K = self.rbf_kernel(self.X_train, self.X_train)
        self.K_inv = np.linalg.inv(K + self.noise_var * np.eye(len(self.X_train)))
        
        # TR Length Update
        if hasattr(self, 'tr_length') and len(self.y_train) >= 2:
            if self.y_train[-1] < np.min(self.y_train[:-1]):
                self.success_count += 1
                self.failure_count = 0
            else:
                self.success_count = 0
                self.failure_count += 1
                
            if self.success_count >= 2:
                self.tr_length = min(self.tr_length * 2.0, 2.0)
                self.success_count = 0
            elif self.failure_count >= 3:
                self.tr_length = max(self.tr_length * 0.5, 1e-3)
                self.failure_count = 0

    def predict(self, X_s):
        X_s = np.atleast_2d(X_s)
        K_s = self.rbf_kernel(self.X_train, X_s)
        
        mu_s = K_s.T.dot(self.K_inv).dot(self.y_train)
        
        var_s = self.kernel_sigma_f**2 - np.sum(K_s.T.dot(self.K_inv) * K_s.T, axis=1, keepdims=True)
        var_s = np.clip(var_s, 1e-9, None) # Prevent numerical negative variance
        
        return mu_s, np.sqrt(var_s)

    def acquisition_function(self, X_s, kappa=0.5, max_allowed_log_ber=None):
        """ Lower Confidence Bound (inverted for maximization) 
            We want to minimize mu (BER) and maximize sigma (exploration).
            So we maximize: -mu + kappa * sigma
        """
        mu, sigma = self.predict(X_s)
        acq = -mu + kappa * sigma
        return acq

    def suggest_next(self, n_coarse=2000, n_fine_steps=50, patience=15, lr=0.1, max_allowed_log_ber=None):
        """ TuRBO-Safe: Trust Region with strict 3-sigma Safe-UCB filtering """
        # Initialize TR state if not present
        if not hasattr(self, 'tr_length'):
            self.tr_length = 0.5 # Initial normalized trust region length
            self.success_count = 0
            self.failure_count = 0
            
        best_x = self.X_train[np.argmin(self.y_train)] if len(self.X_train) > 0 else np.zeros(self.D)
        
        # Determine sampling bounds based on TR length and dimension sensitivities
        tr_bounds = np.zeros((self.D, 2))
        for i in range(self.D):
            scale = 0.3 if i < 8 else (20.0 if i == 8 else 4.0)
            tr_min = max(self.bounds[i, 0], best_x[i] - self.tr_length * scale)
            tr_max = min(self.bounds[i, 1], best_x[i] + self.tr_length * scale)
            tr_bounds[i] = [tr_min, tr_max]
            
        # Dynamically shrink TR until safe candidates are found
        safe_candidates = []
        safe_ei = []
        
        while len(safe_candidates) == 0 and self.tr_length > 1e-4:
            X_coarse = np.random.uniform(tr_bounds[:, 0], tr_bounds[:, 1], size=(n_coarse, self.D))
            
            # Inject best known point to ensure at least one fallback
            if len(self.X_train) > 0:
                X_coarse[0] = best_x
                
            mu, sigma = self.predict(X_coarse)
            
            if max_allowed_log_ber is not None:
                # Safe-UCB (99.7% confidence upper bound)
                ucb = mu + 3.0 * sigma
                safe_mask = ucb.flatten() <= max_allowed_log_ber
                
                # We require at least ONE new safe point (besides X_coarse[0] which is best_x)
                if np.sum(safe_mask) > 1:
                    safe_candidates = X_coarse[safe_mask]
                    safe_ei = (-mu[safe_mask] + 0.5 * sigma[safe_mask]).flatten() # Standard LCB
                else:
                    # Shrink TR if no new safe points found (forces sampling closer to known safe point)
                    self.tr_length *= 0.5
                    safe_candidates = [] # Force while loop to continue
                    for i in range(self.D):
                        scale = 0.3 if i < 8 else (20.0 if i == 8 else 4.0)
                        tr_bounds[i, 0] = max(self.bounds[i, 0], best_x[i] - self.tr_length * scale)
                        tr_bounds[i, 1] = min(self.bounds[i, 1], best_x[i] + self.tr_length * scale)
            else:
                safe_candidates = X_coarse
                safe_ei = (-mu + 0.5 * sigma).flatten()
                
        if len(safe_candidates) == 0:
            # Absolute fallback if GP collapses
            return best_x
            
        best_idx = np.argmax(safe_ei)
        X_best = safe_candidates[best_idx].copy()
        
        # Phase 2: PGA (Constrained inside TR and Physical Bounds)
        current_ei = float(safe_ei[best_idx])
        eps = 1e-5
        
        for step in range(n_fine_steps):
            grad = np.zeros(self.D)
            for i in range(self.D):
                X_plus = X_best.copy()
                X_plus[i] += eps
                X_plus = np.clip(X_plus, tr_bounds[:, 0], tr_bounds[:, 1])
                mu_p, sig_p = self.predict(np.array([X_plus]))
                
                if max_allowed_log_ber is not None and (mu_p + 3.0 * sig_p)[0, 0] > max_allowed_log_ber:
                    ei_plus = -np.inf
                else:
                    ei_plus = (-mu_p + 0.5 * sig_p)[0, 0]
                    
                grad[i] = (ei_plus - current_ei) / eps if ei_plus != -np.inf else 0.0
                
            if np.all(grad == 0):
                break
                
            X_new = X_best + lr * grad
            X_new = np.clip(X_new, tr_bounds[:, 0], tr_bounds[:, 1])
            
            mu_n, sig_n = self.predict(np.array([X_new]))
            if max_allowed_log_ber is not None and (mu_n + 3.0 * sig_n)[0, 0] > max_allowed_log_ber:
                break
                
            new_ei = (-mu_n + 0.5 * sig_n)[0, 0]
            if new_ei > current_ei + 1e-7:
                current_ei = new_ei
                X_best = X_new
            else:
                break
                
        return X_best
