import numpy as np

class SafeHillClimbingOptimizer:
    def __init__(self, bounds, initial_step_size=0.01, max_regression_ratio=5.0):
        """
        White-box implementation of Safe Micro-Step Hill Climbing.
        It strictly guarantees small parameter changes so the hardware doesn't drop the link.
        If a step causes a regression worse than max_regression_ratio, it dynamically shrinks the step size.
        """
        self.bounds = np.array(bounds)
        self.D = len(bounds)
        
        self.step_size = initial_step_size
        self.max_regression_ratio = max_regression_ratio
        
        self.current_x = None
        self.current_y = np.inf
        self.best_x = None
        self.best_y = np.inf

    def fit(self, X_data, y_data):
        if len(X_data) == 0:
            return
            
        latest_x = X_data[-1]
        latest_y = y_data[-1]
        
        # Initialization Phase
        if self.current_x is None:
            best_idx = np.argmin(y_data)
            self.current_x = X_data[best_idx].copy()
            self.current_y = y_data[best_idx]
            self.best_x = self.current_x.copy()
            self.best_y = self.current_y
            return
            
        # Acceptance logic
        ber_latest = 10 ** latest_y
        ber_best = 10 ** self.best_y
        
        if latest_y < self.current_y:
            # Improvement: Accept and maybe slightly increase step size to accelerate
            self.current_x = latest_x.copy()
            self.current_y = latest_y
            self.step_size = min(self.step_size * 1.05, 0.05)
            
            if latest_y < self.best_y:
                self.best_x = latest_x.copy()
                self.best_y = latest_y
        else:
            # Regression
            if ber_latest > self.max_regression_ratio * ber_best:
                # Terrible regression! Shrink step size to be safer.
                self.step_size *= 0.5
            else:
                # Mild regression within safe limits: just reject it (standard hill climbing)
                # Or could probabilistically accept like SA, but user wants strict optimization.
                pass

    def suggest_next(self, **kwargs):
        if self.current_x is None:
             return np.random.uniform(self.bounds[:, 0], self.bounds[:, 1], self.D)
             
        # Generate a candidate by taking a micro-step
        # We perturb a single random dimension (Coordinate Descent style) or all with tiny noise
        x_new = self.current_x.copy()
        
        # Micro random walk direction
        direction = np.random.randn(self.D)
        direction /= np.linalg.norm(direction) # unit vector
        
        noise = direction * self.step_size
        if self.D > 9:
            noise[-1] *= 5.0 # CTLE has larger scale
            
        x_new = x_new + noise
        
        # Project back to bounds
        x_new = np.clip(x_new, self.bounds[:, 0], self.bounds[:, 1])
        
        # Enforce FFE L1 constraint (first 9 taps)
        if self.D >= 9:
            ffe_sum = np.sum(np.abs(x_new[:9]))
            x_new[:9] = x_new[:9] / max(ffe_sum, 1e-9)
            
        return x_new
