import numpy as np

class SimulatedAnnealingOptimizer:
    def __init__(self, bounds, max_regression_ratio=5.0, initial_temp=0.1, cooling_rate=0.9):
        """
        White-box implementation of Bounded Simulated Annealing.
        It keeps the search near the current best point and only accepts regressions
        up to a maximum ratio (e.g., 5.0 means it accepts a BER up to 5x worse than current best).
        """
        self.bounds = np.array(bounds)
        self.D = len(bounds)
        
        self.max_regression_ratio = max_regression_ratio
        self.initial_temp = initial_temp
        self.temp = initial_temp
        self.cooling_rate = cooling_rate
        
        self.current_x = None
        self.current_y = np.inf
        self.best_x = None
        self.best_y = np.inf

    def fit(self, X_data, y_data):
        """
        In BO, fit() trains the GP. Here, we use it to update our SA state 
        based on the latest evaluation or initialize from random seeds.
        """
        if len(X_data) == 0:
            return
            
        latest_x = X_data[-1]
        latest_y = y_data[-1]
        
        # Initialization Phase
        if self.current_x is None:
            # We initialize from the best of the initial random points
            best_idx = np.argmin(y_data)
            self.current_x = X_data[best_idx].copy()
            self.current_y = y_data[best_idx]
            self.best_x = self.current_x.copy()
            self.best_y = self.current_y
            return
            
        # SA Acceptance Phase
        # We check if we should accept the latest evaluated point
        ber_latest = 10 ** latest_y
        ber_current = 10 ** self.current_y
        
        accept = False
        if latest_y < self.current_y:
            accept = True
        else:
            # Check regression bound
            if ber_latest <= self.max_regression_ratio * ber_current:
                # Delta E in log scale is roughly proportional to degradation
                delta_e = latest_y - self.current_y
                prob = np.exp(-delta_e / self.temp)
                if np.random.rand() < prob:
                    accept = True
                    
        if accept:
            self.current_x = latest_x.copy()
            self.current_y = latest_y
            
        if latest_y < self.best_y:
            self.best_x = latest_x.copy()
            self.best_y = latest_y
            
        # Cool down
        self.temp *= self.cooling_rate
        # Ensure temp doesn't drop to exactly 0 to allow some small step size
        self.temp = max(self.temp, 1e-4)

    def suggest_next(self, **kwargs):
        """
        Generate a neighbor around current_x for evaluation.
        We accept **kwargs to maintain interface compatibility with BO suggest_next().
        """
        if self.current_x is None:
             # Fallback if suggest is called before fit with any data
             return np.random.uniform(self.bounds[:, 0], self.bounds[:, 1], self.D)
             
        step_scale = np.maximum(0.1, self.temp)
        
        # Perturb current_x
        noise = np.random.randn(self.D) * 0.1 * step_scale
        # CTLE usually has a larger scale (index 9)
        if self.D > 9:
            noise[-1] *= 10.0 
            
        x_new = self.current_x + noise
        
        # Project back to bounds
        x_new = np.clip(x_new, self.bounds[:, 0], self.bounds[:, 1])
        
        # Enforce FFE L1 constraint (first 9 taps)
        if self.D >= 9:
            ffe_sum = np.sum(np.abs(x_new[:9]))
            x_new[:9] = x_new[:9] / max(ffe_sum, 1e-9)
            
        return x_new
