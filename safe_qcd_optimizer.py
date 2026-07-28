import numpy as np

class SafeQCDOptimizer:
    def __init__(self, bounds, probe_delta=0.01, max_allowed_log_ber=-2.0):
        """
        Safe Quadratic Coordinate Descent (Safe QCD).
        Uses 1D parabolic interpolation to compute the exact curvature (Hessian diagonal)
        and gradient. Jumps to the exact minimum bounded by the calculated parabolic safety roots.
        """
        self.bounds = np.array(bounds)
        self.D = len(bounds)
        
        self.probe_delta = probe_delta
        self.max_allowed_log_ber = max_allowed_log_ber
        
        self.current_x = None
        self.current_y = np.inf
        
        self.dim_idx = 0
        self.state = "INIT" # INIT -> PROBE_PLUS -> PROBE_MINUS -> JUMP
        
        self.y_0 = None
        self.y_plus = None
        self.y_minus = None
        
        self.jump_target = None
        
    def fit(self, X_data, y_data):
        if len(X_data) == 0: return
        latest_y = y_data[-1]
        latest_x = X_data[-1]
        
        if self.current_x is None:
            best_idx = np.argmin(y_data)
            self.current_x = X_data[best_idx].copy()
            self.current_y = y_data[best_idx]
            self.y_0 = self.current_y
            self.state = "PROBE_PLUS"
            return
            
        if self.state == "PROBE_PLUS":
            self.y_plus = latest_y
            self.state = "PROBE_MINUS"
            return
            
        if self.state == "PROBE_MINUS":
            self.y_minus = latest_y
            delta = self.probe_delta
            if self.dim_idx == self.D - 1: delta *= 5.0 # CTLE probe
                
            y0 = self.y_0
            yp = self.y_plus
            ym = self.y_minus
            
            a = (yp + ym - 2*y0) / (2 * delta**2)
            b = (yp - ym) / (2 * delta)
            c = y0
            
            Y_max = self.max_allowed_log_ber
            C = c - Y_max
            
            safe_min = -np.inf
            safe_max = np.inf
            
            if a > 0:
                discriminant = b**2 - 4*a*C
                if discriminant >= 0:
                    r1 = (-b - np.sqrt(discriminant)) / (2*a)
                    r2 = (-b + np.sqrt(discriminant)) / (2*a)
                    safe_min = min(r1, r2)
                    safe_max = max(r1, r2)
            
            if a > 1e-6: # Convex
                x_opt = -b / (2*a)
                if safe_min != -np.inf:
                    x_opt = max(x_opt, safe_min + 0.1 * delta)
                if safe_max != np.inf:
                    x_opt = min(x_opt, safe_max - 0.1 * delta)
            else: # Concave or linear
                step = -np.sign(b) * delta * 2.0
                x_opt = step
                
            x_opt = np.clip(x_opt, -delta*10, delta*10)
            
            self.jump_target = self.current_x.copy()
            self.jump_target[self.dim_idx] += x_opt
            self.jump_target = np.clip(self.jump_target, self.bounds[:, 0], self.bounds[:, 1])
            
            self.state = "JUMP"
            return
            
        if self.state == "JUMP":
            if latest_y < self.current_y:
                self.current_x = latest_x.copy()
                self.current_y = latest_y
                
            self.y_0 = self.current_y
            
            # Move to next dimension randomly to avoid cyclical traps
            self.dim_idx = np.random.randint(self.D)
            self.state = "PROBE_PLUS"
            return

    def suggest_next(self, **kwargs):
        if self.current_x is None:
             return np.random.uniform(self.bounds[:, 0], self.bounds[:, 1], self.D)
             
        delta = self.probe_delta
        if self.dim_idx == self.D - 1: delta *= 5.0
            
        if self.state == "PROBE_PLUS":
            x_new = self.current_x.copy()
            x_new[self.dim_idx] += delta
            return np.clip(x_new, self.bounds[:, 0], self.bounds[:, 1])
            
        if self.state == "PROBE_MINUS":
            x_new = self.current_x.copy()
            x_new[self.dim_idx] -= delta
            return np.clip(x_new, self.bounds[:, 0], self.bounds[:, 1])
            
        if self.state == "JUMP":
            return self.jump_target
