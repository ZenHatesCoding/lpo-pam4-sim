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
            params[1:-1] = np.clip(params[1:-1], 0.01, 0.3) # L_FFE MUST be very small to allow fast sigma growth
            params[-1] = np.clip(params[-1], 1.0, 20.0) # L_CTLE bounds

        # Update with tuned parameters
        self.kernel_sigma_f = params[0]
        self.kernel_l = params[1:]
        
        print(f"  [BO Tuned] sigma_f={self.kernel_sigma_f:.2f} | L_FFE_avg={np.mean(self.kernel_l[:-1]):.2f} | L_CTLE={self.kernel_l[-1]:.1f}")
        
        # Finalize K_inv for predictions
        K = self.rbf_kernel(self.X_train, self.X_train)
        self.K_inv = np.linalg.inv(K + self.noise_var * np.eye(len(self.X_train)))

    def predict(self, X_s):
        X_s = np.atleast_2d(X_s)
        K_s = self.rbf_kernel(self.X_train, X_s)
        
        mu_s = K_s.T.dot(self.K_inv).dot(self.y_train)
        
        var_s = self.kernel_sigma_f**2 - np.sum(K_s.T.dot(self.K_inv) * K_s.T, axis=1, keepdims=True)
        var_s = np.clip(var_s, 1e-9, None) # Prevent numerical negative variance
        
        return mu_s, np.sqrt(var_s)

    def acquisition_function(self, X_s, kappa=10.0):
        """ Lower Confidence Bound (inverted for maximization) 
            We want to minimize mu (BER) and maximize sigma (exploration).
            So we maximize: -mu + kappa * sigma
        """
        mu, sigma = self.predict(X_s)
        return -mu + kappa * sigma

    def suggest_next(self, n_coarse=20, n_fine_steps=50, patience=15, lr=0.1):
        """ GS-EI: Phase 1 Coarse Sampling + Phase 2 Projected Gradient Ascent """
        # -------------------------------------------------------------
        # Phase 1: Coarse Sampling (Multi-Start Seed: Global + Local)
        # -------------------------------------------------------------
        X_coarse = np.zeros((n_coarse, self.D))
        half_n = n_coarse // 2
        
        # 1. Global Exploration
        X_coarse[:half_n] = np.random.uniform(self.bounds[:, 0], self.bounds[:, 1], size=(half_n, self.D))
        
        # 2. Local Exploitation (Perturb around best known point)
        if len(self.X_train) > 0:
            best_x = self.X_train[np.argmin(self.y_train)]
            local_noise = np.random.randn(n_coarse - half_n, self.D) * 0.05
            local_noise[:, -1] *= 10.0 # CTLE has larger scale
            X_coarse[half_n:] = np.clip(best_x + local_noise, self.bounds[:, 0], self.bounds[:, 1])
        else:
            X_coarse[half_n:] = np.random.uniform(self.bounds[:, 0], self.bounds[:, 1], size=(n_coarse - half_n, self.D))
        
        # Enforce L1 constraint ONLY on FFE taps
        ffe_taps = X_coarse[:, :9]
        abs_sum = np.sum(np.abs(ffe_taps), axis=1, keepdims=True)
        X_coarse[:, :9] = ffe_taps / np.maximum(abs_sum, 1e-9)
        
        # Inject best known points to ensure we don't start from pure garbage
        if len(self.X_train) > 0:
            X_coarse = np.vstack((X_coarse, self.X_train))
        
        ei_coarse = self.acquisition_function(X_coarse)
        best_idx = np.argmax(ei_coarse)
        
        X_best = X_coarse[best_idx].copy()
        best_ei = ei_coarse[best_idx, 0]
        
        # -------------------------------------------------------------
        # Phase 2: Projected Gradient Ascent on Acquisition Function
        # -------------------------------------------------------------
        no_improve_count = 0
        eps = 1e-5
        lr_current = lr
        
        for step in range(n_fine_steps):
            current_ei = self.acquisition_function(np.array([X_best]))[0, 0]
            grad = np.zeros(self.D)
            
            # Calculate numerical gradient for EI (with projection implicitly included)
            for i in range(self.D):
                X_plus = X_best.copy()
                X_plus[i] += eps
                
                # Projection (Bound clipping + L1 norm)
                X_plus = np.clip(X_plus, self.bounds[:, 0], self.bounds[:, 1])
                ffe_sum = np.sum(np.abs(X_plus[:9]))
                X_plus[:9] = X_plus[:9] / max(ffe_sum, 1e-9)
                
                ei_plus = self.acquisition_function(np.array([X_plus]))[0, 0]
                grad[i] = (ei_plus - current_ei) / eps
                
            # Escaping flat regions (if gradient is exactly zero)
            if np.all(grad == 0):
                grad = np.random.randn(self.D) * 0.1
                
            # Ascent Step
            X_new = X_best + lr_current * grad
            
            # Reproject to physical bounds
            X_new = np.clip(X_new, self.bounds[:, 0], self.bounds[:, 1])
            ffe_sum_new = np.sum(np.abs(X_new[:9]))
            X_new[:9] = X_new[:9] / max(ffe_sum_new, 1e-9)
            
            # Evaluate new LCB
            new_ei = self.acquisition_function(np.array([X_new]))[0, 0]
            
            # Adaptive learning rate and state update
            if new_ei > best_ei + 1e-7:
                best_ei = new_ei
                X_best = X_new
                no_improve_count = 0
                lr_current *= 1.2 # Accelerate on success
            else:
                no_improve_count += 1
                lr_current *= 0.5 # Decelerate / refine on failure
                
            if no_improve_count >= patience:
                break
                
        return X_best
