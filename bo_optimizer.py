import numpy as np
from scipy.stats import norm

class BayesianOptimizer:
    def __init__(self, bounds, kernel_l=1.0, kernel_sigma_f=1.0, noise_var=1e-4):
        self.bounds = np.array(bounds) # Shape (D, 2)
        self.D = len(bounds)
        self.kernel_l = kernel_l
        self.kernel_sigma_f = kernel_sigma_f
        self.noise_var = noise_var
        
        self.X_train = []
        self.y_train = []
        self.K_inv = None
        self.y_best = np.inf

    def rbf_kernel(self, X1, X2):
        # Squared Euclidean distance
        sqdist = np.sum(X1**2, 1).reshape(-1, 1) + np.sum(X2**2, 1) - 2 * np.dot(X1, X2.T)
        return self.kernel_sigma_f**2 * np.exp(-0.5 / self.kernel_l**2 * sqdist)

    def fit(self, X, y):
        self.X_train = np.array(X)
        self.y_train = np.array(y).reshape(-1, 1)
        self.y_best = np.min(self.y_train)
        
        K = self.rbf_kernel(self.X_train, self.X_train)
        # Add noise variance to diagonal for numerical stability and observation noise
        self.K_inv = np.linalg.inv(K + self.noise_var * np.eye(len(self.X_train)))

    def predict(self, X_s):
        X_s = np.atleast_2d(X_s)
        K_s = self.rbf_kernel(self.X_train, X_s)
        
        mu_s = K_s.T.dot(self.K_inv).dot(self.y_train)
        
        # Only compute diagonal of K_ss which is simply kernel_sigma_f^2
        var_s = self.kernel_sigma_f**2 - np.sum(K_s.T.dot(self.K_inv) * K_s.T, axis=1, keepdims=True)
        var_s = np.clip(var_s, 1e-9, None) # Prevent negative variance from numerical issues
        
        return mu_s, np.sqrt(var_s)

    def expected_improvement(self, X_s, xi=0.01):
        """ Calculate Expected Improvement (EI). We are MINIMIZING y. """
        mu, sigma = self.predict(X_s)
        
        with np.errstate(divide='warn'):
            imp = self.y_best - mu - xi
            Z = imp / sigma
            ei = imp * norm.cdf(Z) + sigma * norm.pdf(Z)
            ei[sigma == 0.0] = 0.0
            
        return ei

    def suggest_next(self, n_samples=10000):
        """ Generate random points, constrain them, and pick max EI """
        # 1. Random sampling in [-1, 1] for all dimensions
        X_random = np.random.uniform(self.bounds[:, 0], self.bounds[:, 1], size=(n_samples, self.D))
        
        # 2. Enforce constraint: sum(|w|) = 1
        abs_sum = np.sum(np.abs(X_random), axis=1, keepdims=True)
        X_random = X_random / abs_sum
        
        # 3. Predict EI
        ei = self.expected_improvement(X_random)
        
        # 4. Return point with max EI
        best_idx = np.argmax(ei)
        return X_random[best_idx]
