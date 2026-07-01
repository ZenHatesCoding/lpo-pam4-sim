import numpy as np
import math
from utils_config import load_config
from main import run_sim
from bo_optimizer import BayesianOptimizer

def objective_function(config, taps):
    """
    Run simulation and return log10 of BER.
    We cap the minimum BER at 1e-6 to avoid log(0) and over-optimizing beyond needed bounds.
    """
    ffe_ber, mlse_ber = run_sim(config, custom_tx_taps=taps, plot_eyes=False)
    # Target MLSE BER
    ber_val = max(mlse_ber, 1e-6)
    return math.log10(ber_val), ffe_ber, mlse_ber

def main():
    print("--- Starting Tx FFE Bayesian Optimization (White-Box) ---")
    config = load_config('config.xlsx')
    
    # Enable realistic PCB loss for the challenge
    if 'pcb_loss_nyquist_db' not in config['channel']:
        config['channel']['pcb_loss_nyquist_db'] = 15.0
        
    # We are optimizing 9 taps
    D = 9
    # Constrain the search space to physically meaningful equalizers
    # Center tap (index 4) should be dominant. Others are pre/post cursors.
    bounds = np.zeros((D, 2))
    for i in range(D):
        if i == 4:
            bounds[i] = [0.4, 1.0] # Center tap must be strong and positive
        else:
            bounds[i] = [-0.5, 0.3] # Cursors are typically negative or slightly positive
    
    # Initialize Optimizer
    bo = BayesianOptimizer(bounds, kernel_l=0.5, kernel_sigma_f=1.0, noise_var=1e-3)
    
    X_data = []
    y_data = []
    
    # 1. Evaluate Initial Default Point (Symmetric Center = 1)
    default_taps = np.zeros(D)
    default_taps[4] = 1.0
    print(f"Eval Initial Default Taps: {default_taps}")
    obj_val, ffe_ber, mlse_ber = objective_function(config, default_taps)
    print(f" -> MLSE BER: {mlse_ber:.2e} (FFE BER: {ffe_ber:.2e})")
    
    X_data.append(default_taps)
    y_data.append(obj_val)
    
    # 2. Evaluate Random Perturbations for Initial GP Training (Exploration)
    n_initial = 5
    for i in range(n_initial):
        rand_taps = np.random.uniform(bounds[:, 0], bounds[:, 1], D)
        rand_taps = rand_taps / np.sum(np.abs(rand_taps))
        
        obj_val, ffe_ber, mlse_ber = objective_function(config, rand_taps)
        print(f"Init {i+1}: Taps: {np.round(rand_taps, 2)}")
        print(f" -> MLSE BER: {mlse_ber:.2e}")
        
        X_data.append(rand_taps)
        y_data.append(obj_val)
        
    # 3. Bayesian Optimization Loop
    n_iterations = 20
    print("\n--- Entering Bayesian Optimization Loop ---")
    for step in range(n_iterations):
        # Train GP
        bo.fit(X_data, y_data)
        
        # Acquisition Maximization
        next_taps = bo.suggest_next(n_samples=20000)
        
        # Evaluate Simulator
        obj_val, ffe_ber, mlse_ber = objective_function(config, next_taps)
        
        print(f"Iter {step+1}/{n_iterations} | Best MLSE BER: {10**np.min(y_data):.2e} | "
              f"Current MLSE BER: {mlse_ber:.2e}")
              
        X_data.append(next_taps)
        y_data.append(obj_val)
        
    # 4. Results
    best_idx = np.argmin(y_data)
    best_taps = X_data[best_idx]
    best_ber = 10**y_data[best_idx]
    
    print("\n--- Optimization Complete ---")
    print(f"Optimal Tx FFE Taps: {np.round(best_taps, 4)}")
    print(f"Achieved MLSE BER: {best_ber:.2e}")
    
    # Save a report
    with open('docs/optimization_report.md', 'w') as f:
        f.write("# Tx FFE Bayesian Optimization Report\n\n")
        f.write("## Setup\n")
        f.write("- **Channel**: 112G PAM4 (56 GBd), 15 dB Host PCB trace loss, 35GHz optics.\n")
        f.write("- **Optimizer**: White-Box Gaussian Process Regressor (RBF Kernel) with Expected Improvement.\n")
        f.write("- **Constraint**: Peak sum limit `sum(|w|) = 1.0`.\n\n")
        
        f.write("## Results\n")
        default_ber = 10**y_data[0]
        f.write(f"- **Default Taps [0,0,0,0,1,0,0,0,0] BER**: `{default_ber:.2e}`\n")
        f.write(f"- **Optimal MLSE BER**: `{best_ber:.2e}`\n")
        f.write(f"- **Optimal Taps**: `{np.round(best_taps, 4).tolist()}`\n\n")
        
        f.write("## Convergence Trace\n")
        for i, y in enumerate(y_data):
            f.write(f"- Eval {i}: `{10**y:.2e}`\n")

if __name__ == '__main__':
    main()
