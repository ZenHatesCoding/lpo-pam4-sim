import numpy as np

class SimulatedAnnealingOptimizer:
    def __init__(self, bounds, max_regression_ratio=5.0, initial_temp=1.0, cooling_rate=0.85):
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
        self.step_size = 0.05 # Initial step size
        
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
                # Delta E in log scale (y is log10(BER))
                delta_e = latest_y - self.current_y
                # When delta_e is 1.0 (10x worse), prob = exp(-1.0 / temp)
                prob = np.exp(-delta_e / self.temp)
                if np.random.rand() < prob:
                    accept = True
                    
        if accept:
            self.current_x = latest_x.copy()
            self.current_y = latest_y
            if latest_y < self.best_y: # Only increase step if we found a new best
                self.step_size = min(self.step_size * 1.05, 0.2)
        else:
            self.step_size = max(self.step_size / 1.05, 0.01)
            
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
             
        # Perturb current_x
        noise = np.zeros(self.D)
        dim_to_perturb = np.random.randint(self.D)
        
        # Use dynamic step size with Gaussian perturbation
        noise[dim_to_perturb] = np.random.randn() * self.step_size
        
        if dim_to_perturb == self.D - 1:
            noise[-1] *= 5.0
            
        x_new = self.current_x + noise
        
        # Project back to bounds
        x_new = np.clip(x_new, self.bounds[:, 0], self.bounds[:, 1])
        
        
        return x_new
