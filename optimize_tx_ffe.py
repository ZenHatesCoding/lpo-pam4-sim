import numpy as np
import math
from utils_config import load_config
from main import run_sim
from bo_optimizer import BayesianOptimizer
from sa_optimizer import SimulatedAnnealingOptimizer
from ga_optimizer import GeneticAlgorithmOptimizer
from shc_optimizer import SafeHillClimbingOptimizer
from datetime import datetime
import os

def objective_function(config, params, result_dir, iter_count):
    """
    Run simulation and return log10 of BER.
    params: [0:8] are Tx FFE pre/post cursors, [8] is ctle_g_dc_db
    We construct the full 9-tap FFE here.
    """
    pre_post = np.array(params[:8])
    
    # Enforce physical constraint: sum(|pre_post|) <= 0.6 to guarantee main cursor >= 0.4
    abs_sum = np.sum(np.abs(pre_post))
    if abs_sum > 0.6:
        pre_post = pre_post * (0.6 / abs_sum)
        
    ffe_pre = int(config['tx'].get('ffe_pre', 4))
    if int(config['tx']['ffe_taps']) != 9:
        ffe_pre = 1 # Fallback for non-9-tap
        
    taps = np.zeros(9)
    taps[:ffe_pre] = pre_post[:ffe_pre]
    taps[ffe_pre+1:] = pre_post[ffe_pre:]
    taps[ffe_pre] = 1.0 - np.sum(np.abs(pre_post)) # Main cursor
    
    config['channel']['ctle_g_dc_db'] = params[8]
    
    # We don't save plots for every single iteration
    ffe_ber, mlse_ber = run_sim(config, custom_tx_taps=taps, plot_eyes=False)
    # User explicitly requested MLSE BER as the optimization target
    ber_val = max(mlse_ber, 1e-8)
    
    # Log iteration
    with open(os.path.join(result_dir, "sim_log.txt"), "a") as f:
        f.write(f"Iter {iter_count[0]} | Taps: {np.round(taps, 4).tolist()} | CTLE DC: {params[8]:.2f}dB | FFE BER: {ffe_ber:.2e} | MLSE BER: {mlse_ber:.2e}\n")
    iter_count[0] += 1
    
    return math.log10(ber_val), ffe_ber, mlse_ber

def main():
    print("--- Starting Tx FFE Bayesian Optimization (White-Box) ---")
    import create_config
    create_config.generate_config()
    config = load_config('config.xlsx')
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_dir = os.path.join("result", f"{timestamp}_optimize")
    if not os.path.exists(result_dir):
        os.makedirs(result_dir)
        
    # Enable realistic PCB loss for the challenge
    if 'pcb_loss_nyquist_db' not in config['channel']:
        config['channel']['pcb_loss_nyquist_db'] = 15.0
        
    # We are optimizing 8 Tx FFE pre/post taps + 1 CTLE DC Gain
    D = 9
    # Constrain the search space
    bounds = np.zeros((D, 2))
    for i in range(8):
        bounds[i] = [-0.3, 0.3] # Pre/post cursors constrained
    bounds[8] = [-20.0, 0.0] # CTLE DC Gain from -20dB to 0dB
    
    opt_type = config['tx'].get('optimizer_type', 'BO').upper()
    if opt_type == 'SA':
        optimizer = SimulatedAnnealingOptimizer(bounds, max_regression_ratio=5.0, initial_temp=0.1, cooling_rate=0.85)
    elif opt_type == 'GA':
        optimizer = GeneticAlgorithmOptimizer(bounds, pop_size=10, mutation_rate=0.3, mutation_scale=0.15)
    elif opt_type == 'SHC':
        optimizer = SafeHillClimbingOptimizer(bounds, initial_step_size=0.01, max_regression_ratio=5.0)
    else:
        optimizer = BayesianOptimizer(bounds, noise_var=1e-3)
    
    X_data = []
    y_data = []
    mlse_history = []
    
    # 1. Evaluate Initial Default Point
    default_params = np.zeros(D)
    ffe_pre = int(config['tx'].get('ffe_pre', 4))
    if config['tx'].get('custom_taps') is not None:
        taps_val = config['tx']['custom_taps']
        if isinstance(taps_val, str) and taps_val.strip().startswith('['):
            import ast
            taps_array = np.array(ast.literal_eval(taps_val))
        else:
            taps_array = np.array(taps_val)
        
        # Extract pre/post cursors
        pre_post = np.zeros(8)
        pre_post[:ffe_pre] = taps_array[:ffe_pre]
        pre_post[ffe_pre:] = taps_array[ffe_pre+1:9]
        default_params[:8] = pre_post
    else:
        # Default is all zeros for pre/post, which means main cursor is 1.0
        pass
        
    default_params[8] = config['channel'].get('ctle_g_dc_db', -12.0)
    print(f"Eval Initial Default Params (8 FFE + 1 CTLE): {default_params}")
    
    # We'll use a mutable list to track iteration count
    iter_count = [1]
    
    with open(os.path.join(result_dir, "sim_log.txt"), "w") as f:
        f.write(f"--- Starting Tx FFE {opt_type} Optimization (White-Box) ---\n")
        f.write(f"Baud Rate: {config['system']['baud_rate']/1e9} GBd\n")
        if opt_type == 'SA':
            f.write(f"Optimizer: Bounded Simulated Annealing (Max Regression Ratio: 5.0, Initial Temp: 0.1, Cooling: 0.85)\n")
        elif opt_type == 'GA':
            f.write(f"Optimizer: Genetic Algorithm (Pop: 10, Mut_Rate: 0.3, Mut_Scale: 0.15)\n")
        elif opt_type == 'SHC':
            f.write(f"Optimizer: Safe Micro-Step Hill Climbing (Init Step: 0.01, Max Regression: 5.0)\n")
        else:
            f.write(f"Optimizer: Gaussian Process (RBF Kernel), Acquisition: Expected Improvement (EI)\n")
        f.write(f"Iterations: {40}\n\n")

    obj_val, ffe_ber, mlse_ber = objective_function(config, default_params, result_dir, iter_count)
    print(f" -> MLSE BER: {mlse_ber:.2e} (FFE BER: {ffe_ber:.2e})")
    
    X_data.append(default_params)
    y_data.append(obj_val)
    mlse_history.append(mlse_ber)
    
    # 2. Evaluate Random Perturbations for Initial GP Training (Exploration)
    # We ONLY do this for BO, because other algorithms (especially safe ones) should NOT evaluate terrible random points.
    if opt_type == 'BO':
        n_initial = 10
        print("\n--- Evaluating Initial Random Points for GP ---")
        for i in range(n_initial):
            rand_params = np.random.uniform(bounds[:, 0], bounds[:, 1], D)
            # Physical constraints are now handled safely inside objective_function
            
            obj_val, ffe_ber, mlse_ber = objective_function(config, rand_params, result_dir, iter_count)
            print(f"Init {i+1}: FFE: {np.round(rand_params[:8], 2)}, CTLE: {rand_params[8]:.1f}dB")
            print(f" -> FFE BER: {ffe_ber:.2e} | MLSE BER: {mlse_ber:.2e}")
            
            X_data.append(rand_params)
            y_data.append(obj_val)
            mlse_history.append(mlse_ber)
    else:
        print("\n--- Skipping Random Initialization (Safe Mode) ---")
        
    # 3. Optimization Loop
    n_iterations = 40
    print(f"\n--- Entering {opt_type} Optimization Loop ---")
    for step in range(n_iterations):
        # Update Optimizer State (Train GP or Update SA State)
        optimizer.fit(X_data, y_data)
        
        # Suggest Next Taps
        next_taps = optimizer.suggest_next(n_coarse=20, n_fine_steps=50, patience=15, lr=0.1)
        
        # Evaluate Simulator
        obj_val, ffe_ber, mlse_ber = objective_function(config, next_taps, result_dir, iter_count)
        
        print(f"Iter {step+1}/{n_iterations} | Best MLSE BER: {np.min(mlse_history):.2e} | "
              f"Current FFE BER: {ffe_ber:.2e} | Current MLSE BER: {mlse_ber:.2e}")
              
        X_data.append(next_taps)
        y_data.append(obj_val)
        mlse_history.append(mlse_ber)
        
    # 4. Results
    best_idx = np.argmin(y_data)
    best_params = X_data[best_idx]
    best_ffe_ber = 10**y_data[best_idx]
    best_mlse_ber = mlse_history[best_idx]
    
    # Reconstruct best taps
    pre_post = best_params[:8]
    abs_sum = np.sum(np.abs(pre_post))
    if abs_sum > 0.6:
        pre_post = pre_post * (0.6 / abs_sum)
    taps = np.zeros(9)
    taps[:ffe_pre] = pre_post[:ffe_pre]
    taps[ffe_pre+1:] = pre_post[ffe_pre:]
    taps[ffe_pre] = 1.0 - np.sum(np.abs(pre_post))
    
    print("\n--- Optimization Complete ---")
    print(f"Optimal Tx FFE Taps: {np.round(taps, 4)}")
    print(f"Optimal CTLE DC Gain: {best_params[8]:.2f} dB")
    print(f"Achieved FFE BER: {best_ffe_ber:.2e}")
    print(f"Achieved MLSE BER: {best_mlse_ber:.2e}")
    
    # Save a report
    with open(os.path.join(result_dir, 'optimization_report.md'), 'w') as f:
        f.write(f"# Tx FFE {opt_type} Optimization Report\n\n")
        f.write("## Setup\n")
        f.write("- **Channel**: 112G PAM4 (56 GBd), 15 dB Host PCB trace loss, 35GHz optics.\n")
        if opt_type == 'SA':
            f.write("- **Optimizer**: White-Box Bounded Simulated Annealing (Local Search).\n")
            f.write("- **Parameters**: `Max Regression Ratio = 5.0`, `Initial Temp = 0.1`, `Cooling Rate = 0.85`.\n")
        elif opt_type == 'GA':
            f.write("- **Optimizer**: White-Box Continuous Genetic Algorithm.\n")
            f.write("- **Parameters**: `Population Size = 10`, `Mutation Rate = 0.3`, `Mutation Scale = 0.15`.\n")
        elif opt_type == 'SHC':
            f.write("- **Optimizer**: White-Box Safe Micro-Step Hill Climbing.\n")
            f.write("- **Parameters**: `Initial Step Size = 0.01`, `Max Regression Ratio = 5.0`.\n")
        else:
            f.write("- **Optimizer**: White-Box Gaussian Process Regressor (RBF Kernel) with Expected Improvement.\n")
        f.write("- **Constraint**: Peak sum limit `sum(|w|) = 1.0`.\n\n")
        
        f.write("## Results\n")
        default_ber = mlse_history[0]
        f.write(f"- **Default Taps [0,0,0,0,1,0,0,0,0] MLSE BER**: `{default_ber:.2e}`\n")
        f.write(f"- **Optimal FFE BER**: `{best_ffe_ber:.2e}`\n")
        f.write(f"- **Optimal MLSE BER**: `{best_mlse_ber:.2e}`\n")
        f.write(f"- **Optimal Tx FFE Taps**: `{np.round(taps, 4).tolist()}`\n")
        f.write(f"- **Optimal CTLE DC Gain**: `{best_params[8]:.2f} dB`\n\n")
        
        f.write("## Convergence Trace\n")
        for i, y in enumerate(y_data):
            f.write(f"- Eval {i}: `{10**y:.2e}`\n")
            
    with open(os.path.join(result_dir, "sim_log.txt"), "a") as f:
        f.write("\n--- Optimization Complete ---\n")
        f.write(f"Optimal Tx FFE Taps: {np.round(taps, 4).tolist()}\n")
        f.write(f"Optimal CTLE DC Gain: {best_params[8]:.2f} dB\n")
        f.write(f"Achieved MLSE BER: {best_mlse_ber:.2e}\n")
            
    # Run the best params one more time to generate the eye diagrams if configured
    run_sim(config, custom_tx_taps=taps, plot_eyes=True, output_dir=result_dir)

if __name__ == '__main__':
    main()
