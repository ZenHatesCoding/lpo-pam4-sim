import numpy as np

class SurrogateSHCOptimizer:
    def __init__(self, bounds, initial_step_size=0.05, max_regression_ratio=10.0, max_allowed_log_ber=-2.0, window_size=50):
        """
        White-box implementation of Surrogate-Assisted Safe Hill Climbing.
        Uses a Directional Tabu Filter to strictly memorize and avoid 
        stepping into specific gradient directions that previously led to a cliff.
        """
        self.bounds = np.array(bounds)
        self.D = len(bounds)
        
        self.step_size = initial_step_size
        self.max_regression_ratio = max_regression_ratio
        self.max_allowed_log_ber = max_allowed_log_ber
        self.window_size = window_size
        
        self.current_x = None
        self.current_y = np.inf
        self.best_x = None
        self.best_y = np.inf
        
        self.X_history = []
        self.y_history = []
        
    def fit(self, X_data, y_data):
        if len(X_data) == 0:
            return
            
        latest_x = X_data[-1]
        latest_y = y_data[-1]
        
        self.X_history.append(latest_x)
        self.y_history.append(latest_y)
        
        if len(self.X_history) > self.window_size:
            self.X_history.pop(0)
            self.y_history.pop(0)
            
        if self.current_x is None:
            best_idx = np.argmin(y_data)
            self.current_x = X_data[best_idx].copy()
            self.current_y = y_data[best_idx]
            self.best_x = self.current_x.copy()
            self.best_y = self.current_y
            return
            
        ber_latest = 10 ** latest_y
        ber_best = 10 ** self.best_y
        
        if latest_y < self.current_y:
            self.current_x = latest_x.copy()
            self.current_y = latest_y
            self.step_size = min(self.step_size * 1.05, 0.05)
            
            if latest_y < self.best_y:
                self.best_x = latest_x.copy()
                self.best_y = latest_y
        else:
            if ber_latest > self.max_regression_ratio * ber_best:
                self.step_size *= 0.5

    def suggest_next(self, **kwargs):
        if self.current_x is None:
             return np.random.uniform(self.bounds[:, 0], self.bounds[:, 1], self.D)
             
        # Extract tabu directions from history around the current point
        tabu_directions = []
        if len(self.X_history) > 0:
            for i in range(len(self.X_history)):
                if self.y_history[i] > self.max_allowed_log_ber:
                    # This was a bad point (cliff).
                    vec_bad = self.X_history[i] - self.current_x
                    norm = np.linalg.norm(vec_bad)
                    if norm > 1e-9:
                        # Only consider it tabu if it originated close to our current position
                        if norm < 0.3:  
                            tabu_directions.append(vec_bad / norm)
             
        # Generate random SHC steps and apply Directional Tabu Filter
        max_trials = 30
        for _ in range(max_trials):
            x_new = self.current_x.copy()
            dim_to_perturb = np.random.randint(self.D)
            noise = np.zeros(self.D)
            noise[dim_to_perturb] = np.random.choice([-1.0, 1.0]) * self.step_size
            
            if dim_to_perturb == self.D - 1:
                noise[-1] *= 5.0
                
            x_new = x_new + noise
            x_new = np.clip(x_new, self.bounds[:, 0], self.bounds[:, 1])
            
            # Check if this step is pointing into a tabu direction
            vec_new = x_new - self.current_x
            norm_new = np.linalg.norm(vec_new)
            is_tabu = False
            
            if norm_new > 1e-9:
                dir_new = vec_new / norm_new
                for tabu_dir in tabu_directions:
                    # Cosine similarity > 0.99 means it's exactly the same direction
                    if np.dot(dir_new, tabu_dir) > 0.99:
                        is_tabu = True
                        break
                        
            if is_tabu:
                continue # Veto this step, it points to a known cliff!
                
            return x_new
            
        # Fallback: surrounded by tabu directions.
        # This implies we are at a highly constrained peak/valley.
        # Micro-step to safely escape.
        x_micro = self.current_x.copy()
        dim = np.random.randint(self.D)
        n = np.zeros(self.D)
        n[dim] = np.random.choice([-1.0, 1.0]) * (self.step_size * 0.1)
        if dim == self.D - 1:
            n[-1] *= 5.0
        return np.clip(x_micro + n, self.bounds[:, 0], self.bounds[:, 1])
