import numpy as np
import math
from utils_config import load_config
from main import run_sim
from bo_optimizer import BayesianOptimizer
from datetime import datetime
import os

def objective_function(config, params):
    """
    Run simulation and return log10 of BER.
    params: [0:9] are Tx FFE taps, [9] is ctle_g_dc_db
    We cap the minimum BER at 1e-6 to avoid log(0) and over-optimizing beyond needed bounds.
    """
    taps = params[:9]
    config['channel']['ctle_g_dc_db'] = params[9]
    
    # We don't save plots for every single iteration of BO to save disk space
    ffe_ber, mlse_ber = run_sim(config, custom_tx_taps=taps, plot_eyes=False)
    # Target MLSE BER
    ber_val = max(mlse_ber, 1e-6)
    return math.log10(ber_val), ffe_ber, mlse_ber

def main():
    print("--- Starting Tx FFE Bayesian Optimization (White-Box) ---")
    config = load_config('config.xlsx')
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_dir = os.path.join("result", f"{timestamp}_optimize")
    if not os.path.exists(result_dir):
        os.makedirs(result_dir)
        
    # Enable realistic PCB loss for the challenge
    if 'pcb_loss_nyquist_db' not in config['channel']:
        config['channel']['pcb_loss_nyquist_db'] = 15.0
        
    # We are optimizing 9 Tx FFE taps + 1 CTLE DC Gain
    D = 10
    # Constrain the search space
    bounds = np.zeros((D, 2))
    for i in range(9):
        if i == 4:
            bounds[i] = [0.4, 1.0] # Center tap must be strong and positive
        else:
            bounds[i] = [-0.5, 0.3] # Cursors are typically negative or slightly positive
    bounds[9] = [-20.0, 0.0] # CTLE DC Gain from -20dB to 0dB
    
    # Initialize Optimizer
    bo = BayesianOptimizer(bounds, kernel_l=0.5, kernel_sigma_f=1.0, noise_var=1e-3)
    
    X_data = []
    y_data = []
    
    # 1. Evaluate Initial Default Point
    default_params = np.zeros(D)
    default_params[4] = 1.0
    default_params[9] = -12.0 # Default CTLE
    print(f"Eval Initial Default Params: {default_params}")
    obj_val, ffe_ber, mlse_ber = objective_function(config, default_params)
    print(f" -> MLSE BER: {mlse_ber:.2e} (FFE BER: {ffe_ber:.2e})")
    
    X_data.append(default_params)
    y_data.append(obj_val)
    
    # 2. Evaluate Random Perturbations for Initial GP Training (Exploration)
    n_initial = 5
    for i in range(n_initial):
        rand_params = np.random.uniform(bounds[:, 0], bounds[:, 1], D)
        # Normalize the FFE taps part only
        rand_params[:9] = rand_params[:9] / np.sum(np.abs(rand_params[:9]))
        
        obj_val, ffe_ber, mlse_ber = objective_function(config, rand_params)
        print(f"Init {i+1}: FFE: {np.round(rand_params[:9], 2)}, CTLE: {rand_params[9]:.1f}dB")
        print(f" -> MLSE BER: {mlse_ber:.2e}")
        
        X_data.append(rand_params)
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
    best_params = X_data[best_idx]
    best_ber = 10**y_data[best_idx]
    
    print("\n--- Optimization Complete ---")
    print(f"Optimal Tx FFE Taps: {np.round(best_params[:9], 4)}")
    print(f"Optimal CTLE DC Gain: {best_params[9]:.2f} dB")
    print(f"Achieved MLSE BER: {best_ber:.2e}")
    
    # Save a report
    with open(os.path.join(result_dir, 'optimization_report.md'), 'w') as f:
        f.write("# Tx FFE Bayesian Optimization Report\n\n")
        f.write("## Setup\n")
        f.write("- **Channel**: 112G PAM4 (56 GBd), 15 dB Host PCB trace loss, 35GHz optics.\n")
        f.write("- **Optimizer**: White-Box Gaussian Process Regressor (RBF Kernel) with Expected Improvement.\n")
        f.write("- **Constraint**: Peak sum limit `sum(|w|) = 1.0`.\n\n")
        
        f.write("## Results\n")
        default_ber = 10**y_data[0]
        f.write(f"- **Default Taps [0,0,0,0,1,0,0,0,0] BER**: `{default_ber:.2e}`\n")
        f.write(f"- **Optimal MLSE BER**: `{best_ber:.2e}`\n")
        f.write(f"- **Optimal Tx FFE Taps**: `{np.round(best_params[:9], 4).tolist()}`\n")
        f.write(f"- **Optimal CTLE DC Gain**: `{best_params[9]:.2f} dB`\n\n")
        
        f.write("## Convergence Trace\n")
        for i, y in enumerate(y_data):
            f.write(f"- Eval {i}: `{10**y:.2e}`\n")
            
    # Run the best params one more time to generate the eye diagrams if configured
    run_sim(config, custom_tx_taps=best_params[:9], plot_eyes=True, output_dir=result_dir)

if __name__ == '__main__':
    main()
