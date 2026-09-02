import numpy as np

class SafeESCOptimizer:
    def __init__(self, bounds, initial_step_size=0.01, max_allowed_log_ber=-2.0, dither_amplitude=0.02):
        """
        White-box implementation of Extremum Seeking Control (ESC) with Barrier Function.
        Maintains a gradient estimate using dither, and repels from safety boundaries.
        """
        self.bounds = np.array(bounds)
        self.D = len(bounds)
        
        self.step_size = initial_step_size
        self.max_allowed_log_ber = max_allowed_log_ber
        self.dither_amplitude = dither_amplitude
        
        self.current_x = None
        self.current_y = np.inf
        
        self.step_count = 0
        self.gradient_estimate = np.zeros(self.D)
        self.last_x = None
        self.last_y = np.inf
        
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
            self.last_x = self.current_x.copy()
            self.last_y = self.current_y
            return
            
        # Update gradient estimate using simple finite difference (discrete ESC)
        if self.last_x is not None and not np.array_equal(latest_x, self.last_x):
            dx = latest_x - self.last_x
            dy = latest_y - self.last_y
            
            # Prevent divide by zero
            norm_dx = np.linalg.norm(dx)
            if norm_dx > 1e-6:
                # Update gradient with momentum
                g = (dy / (norm_dx**2)) * dx
                self.gradient_estimate = 0.5 * self.gradient_estimate + 0.5 * g
        
        # Update state
        if latest_y < self.current_y:
            self.current_x = latest_x.copy()
            self.current_y = latest_y
            
        self.last_x = latest_x.copy()
        self.last_y = latest_y

    def suggest_next(self, **kwargs):
        if self.current_x is None:
             return np.random.uniform(self.bounds[:, 0], self.bounds[:, 1], self.D)
             
        self.step_count += 1
        
        # Base gradient step
        step_dir = -self.gradient_estimate * self.step_size
        
        # Safe Barrier Logic: if we are near or worse than max_allowed_log_ber, 
        # apply a repulsive force to retreat
        if self.current_y >= self.max_allowed_log_ber - 0.5:
            # We are near the danger zone. 
            # The repulsive force should push us against the gradient we just measured.
            # If dy was positive (worse), the gradient points into danger. 
            # -gradient naturally pushes us back. We just magnify it.
            barrier_force = (self.current_y - (self.max_allowed_log_ber - 0.5)) * 10.0
            step_dir -= self.gradient_estimate * barrier_force * self.step_size
            
        # Add orthogonal dither to continue exploring the gradient
        dither = np.random.choice([-1.0, 1.0], size=self.D) * self.dither_amplitude
        # CTLE usually needs larger dither
        dither[-1] *= 5.0
        
        x_new = self.current_x + step_dir + dither
        
        # Reproject to physical bounds
        x_new = np.clip(x_new, self.bounds[:, 0], self.bounds[:, 1])
        return x_new
