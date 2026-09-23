import numpy as np

class SafeGPOptimizer:
    def __init__(self, bounds, max_allowed_log_ber=-2.0, length_scale=0.1, noise_var=1e-4, beta=2.0):
        """
        Pure NumPy White-box implementation of Safe Bayesian Optimization (SafeOpt).
        Uses a Gaussian Process with RBF kernel to predict both Mean (mu) and Uncertainty (sigma).
        Strictly restricts exploration to the "Safe Set" where UCB (Upper Confidence Bound) < threshold.
        """
        self.bounds = np.array(bounds)
        self.D = len(bounds)
        
        self.max_allowed_log_ber = max_allowed_log_ber
        self.length_scale = length_scale
        self.noise_var = noise_var
        self.beta = beta # Confidence interval multiplier
        
        self.X_history = []
        self.y_history = []
        
        # We assume the worst-case BER in completely unknown regions is 0 (log10(BER) = 0, i.e., BER=1)
        # This GP prior mean naturally penalizes unknown regions, acting as a physical safety barrier.
        self.prior_mean = 0.0 

    def _rbf_kernel(self, X1, X2):
        # Normalize features by their physical bounds so all dimensions are scaled equally
        range_scale = self.bounds[:, 1] - self.bounds[:, 0]
        range_scale[range_scale == 0] = 1.0
        
        X1_norm = X1 / range_scale
        X2_norm = X2 / range_scale
        
        # Vectorized squared euclidean distance computation
        sqdist = np.sum(X1_norm**2, 1).reshape(-1, 1) + np.sum(X2_norm**2, 1) - 2 * np.dot(X1_norm, X2_norm.T)
        return np.exp(-0.5 * sqdist / (self.length_scale ** 2))

    def fit(self, X_data, y_data):
        if len(X_data) == 0:
            return
            
        self.X_history = np.array(X_data)
        # Shift y by prior mean
        self.y_history = np.array(y_data) - self.prior_mean
        
        # Precompute K inverse for fast prediction
        K = self._rbf_kernel(self.X_history, self.X_history)
        K += np.eye(len(self.X_history)) * self.noise_var
        self.K_inv = np.linalg.inv(K)

    def predict(self, X_star):
        if len(self.X_history) == 0:
            return np.ones(len(X_star)) * self.prior_mean, np.ones(len(X_star))
            
        K_star = self._rbf_kernel(self.X_history, X_star)
        
        # mu = K_star^T * K_inv * y
        mu = np.dot(K_star.T, np.dot(self.K_inv, self.y_history)) + self.prior_mean
        
        # sigma^2 = K_star_star - K_star^T * K_inv * K_star
        K_star_star = np.ones(len(X_star)) # Diagonal of RBF kernel is always 1
        
        # Efficient computation of the diagonal of K_star^T * K_inv * K_star
        v = np.dot(self.K_inv, K_star)
        sigma2 = K_star_star - np.sum(K_star * v, axis=0)
        sigma2 = np.clip(sigma2, 1e-9, np.inf)
        sigma = np.sqrt(sigma2)
        
        return mu, sigma

    def suggest_next(self, **kwargs):
        if len(self.X_history) == 0:
            return np.random.uniform(self.bounds[:, 0], self.bounds[:, 1], self.D)
            
        current_x = self.X_history[np.argmin(self.y_history)]
        
        # 1. Generate dense candidates around the current best point (local trust region)
        # We sample points at various distances to allow expansion
        n_candidates = 500
        candidates = []
        for _ in range(n_candidates):
            # Scale exploration radius exponentially to cover both micro and macro steps
            radius = np.random.uniform(0.01, 0.2)
            noise = np.random.randn(self.D)
            noise = noise / np.linalg.norm(noise) * radius
            
            # Scale to physical bounds
            range_scale = self.bounds[:, 1] - self.bounds[:, 0]
            range_scale[range_scale == 0] = 1.0
            
            cand = current_x + noise * range_scale
            cand = np.clip(cand, self.bounds[:, 0], self.bounds[:, 1])
            candidates.append(cand)
            
        candidates = np.array(candidates)
        
        # 2. Predict Mean and Uncertainty for all candidates
        mu, sigma = self.predict(candidates)
        
        # 3. Calculate Upper Confidence Bound (Pessimistic Safety Bound)
        ucb = mu + self.beta * sigma
        
        # 4. Filter the Safe Set
        safe_mask = ucb < self.max_allowed_log_ber
        
        if not np.any(safe_mask):
            # Fallback: No strictly safe points found (we are trapped)
            # Take a microscopic conservative step along the safest predicted direction
            safest_idx = np.argmin(ucb)
            safest_cand = candidates[safest_idx]
            # Interpolate 10% of the way towards the safest candidate
            return current_x + 0.1 * (safest_cand - current_x)
            
        safe_candidates = candidates[safe_mask]
        safe_mu = mu[safe_mask]
        safe_sigma = sigma[safe_mask]
        
        # 5. Acquisition Function: Lower Confidence Bound (Optimistic Exploration within Safe Set)
        lcb = safe_mu - self.beta * safe_sigma
        
        best_idx = np.argmin(lcb)
        return safe_candidates[best_idx]
