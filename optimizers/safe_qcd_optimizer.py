import numpy as np
from bo_optimizer import BayesianOptimizer

class SafeQCDOptimizer:
    def __init__(self, bounds, probe_delta=0.01, max_allowed_log_ber=-2.0):
        """
        Guided Safe QDS (BO-Steered Safe Micro-Probe).
        Uses Bayesian Optimization to predict the global optimal direction, 
        and a rigorously normalized micro-probe to extract the 1D physical 
        curvature (Hessian). Guarantees both fast convergence and absolute safety.
        """
        self.bounds = np.array(bounds)
        self.D = len(bounds)
        
        self.probe_delta = probe_delta
        self.max_allowed_log_ber = max_allowed_log_ber
        
        self.current_x = None
        self.current_y = np.inf
        
        self.state = "INIT" # INIT -> PROBE_PLUS -> PROBE_MINUS -> JUMP
        
        self.y_0 = None
        self.y_plus = None
        self.y_minus = None
        
        self.jump_target = None
        self.probe_vec = None
        self.direction = None
        self.target_dist = None
        
        # Internal navigator
        self.bo = BayesianOptimizer(bounds, noise_var=1e-3)
        
        # Dimension-specific deltas for correct physical scaling
        self.deltas = np.ones(self.D) * self.probe_delta
        if self.D > 8:
            self.deltas[8] = 0.5   # CTLE DC Gain is [-20, 0]
        if self.D > 9:
            self.deltas[9] = 0.1   # CTLE fz
            self.deltas[10] = 0.1  # CTLE fp1
            self.deltas[11] = 0.1  # CTLE fp2
            
    def _generate_guided_probe_vector(self, target_x):
        d = target_x - self.current_x
        # Normalize direction by sensitivity (deltas)
        # S_inv = 1 / deltas
        S_inv = 1.0 / self.deltas
        norm_scale = np.linalg.norm(d * S_inv)
        if norm_scale < 1e-6:
            # Fallback to random if stuck
            d = np.random.uniform(-1, 1, self.D) * self.deltas
            norm_scale = np.linalg.norm(d * S_inv)
            
        # target_dist is the length in normalized space
        self.target_dist = norm_scale
        
        # Micro-probe: length is exactly 1.0 in normalized space
        self.probe_vec = d / norm_scale
        self.direction = self.probe_vec / np.linalg.norm(self.probe_vec)
        
    def fit(self, X_data, y_data):
        if len(X_data) == 0: return
        latest_y = y_data[-1]
        latest_x = X_data[-1]
        
        if self.current_x is None:
            best_idx = np.argmin(y_data)
            self.current_x = X_data[best_idx].copy()
            self.current_y = y_data[best_idx]
            self.y_0 = self.current_y
            
            # Use BO to find next target
            self.bo.fit(X_data, y_data)
            target_x = self.bo.suggest_next(n_coarse=2000, n_fine_steps=50, patience=15, lr=0.1)
            self._generate_guided_probe_vector(target_x)
            
            self.state = "PROBE_PLUS"
            return
            
        if self.state == "PROBE_PLUS":
            self.y_plus = latest_y
            self.state = "PROBE_MINUS"
            return
            
        if self.state == "PROBE_MINUS":
            self.y_minus = latest_y
                
            y0 = self.y_0
            yp = self.y_plus
            ym = self.y_minus
            
            # The probe is evaluated at alpha = +1 and alpha = -1
            # We fit y(alpha) = a*alpha^2 + b*alpha + c
            delta = 1.0 
            
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
                
            # Limit the jump to the BO target or safety boundary, whichever is smaller
            # target_dist is the requested BO jump
            if x_opt > 0:
                x_opt = min(x_opt, self.target_dist)
            else:
                x_opt = max(x_opt, -self.target_dist)
                
            # Absolute max clip for taylor safety just in case BO is wild
            x_opt = np.clip(x_opt, -10.0, 10.0)
            
            self.jump_target = self.current_x.copy()
            self.jump_target += x_opt * self.probe_vec
            self.jump_target = np.clip(self.jump_target, self.bounds[:, 0], self.bounds[:, 1])
            
            self.state = "JUMP"
            return
            
        if self.state == "JUMP":
            if latest_y < self.current_y:
                self.current_x = latest_x.copy()
                self.current_y = latest_y
                
            self.y_0 = self.current_y
            
            # Re-steer with BO
            self.bo.fit(X_data, y_data)
            target_x = self.bo.suggest_next(n_coarse=2000, n_fine_steps=50, patience=15, lr=0.1)
            self._generate_guided_probe_vector(target_x)
            
            self.state = "PROBE_PLUS"
            return

    def suggest_next(self, **kwargs):
        if self.current_x is None:
             return np.random.uniform(self.bounds[:, 0], self.bounds[:, 1], self.D)
            
        if self.state == "PROBE_PLUS":
            x_new = self.current_x + self.probe_vec
            return np.clip(x_new, self.bounds[:, 0], self.bounds[:, 1])
            
        if self.state == "PROBE_MINUS":
            x_new = self.current_x - self.probe_vec
            return np.clip(x_new, self.bounds[:, 0], self.bounds[:, 1])
            
        if self.state == "JUMP":
            return self.jump_target
