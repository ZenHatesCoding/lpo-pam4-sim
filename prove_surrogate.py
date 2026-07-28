import numpy as np
import matplotlib.pyplot as plt
from shc_optimizer import SafeHillClimbingOptimizer
from surrogate_shc_optimizer import SurrogateSHCOptimizer
from safe_qcd_optimizer import SafeQCDOptimizer
from optimize_tx import objective_function
import create_config
from utils_config import load_config
import os
import time

def run_proof():
    print("=== Statistical Proof: Surrogate SHC vs Standard SHC ===")
    create_config.generate_config()
    base_config = load_config('config.xlsx')
    
    # 1e-4 level simulation
    base_config['channel']['snr_db'] = 26.0
    if 'pcb_loss_nyquist_db' not in base_config['channel']:
        base_config['channel']['pcb_loss_nyquist_db'] = 15.0
        
    base_config['system']['num_symbols'] = 65536
    base_config['tx']['pattern_length'] = 32768
    
    D = 12
    bounds = np.zeros((D, 2))
    for i in range(8):
        bounds[i] = [-0.3, 0.3] 
    bounds[8] = [-20.0, 0.0]
    bounds[9] = [1.0, 5.0]
    bounds[10] = [1.0, 5.0]
    bounds[11] = [0.5, 3.0] 
    
    ffe_pre = int(base_config['tx'].get('ffe_pre', 4))
    
    n_seeds = 5
    n_iterations = 30
    
    max_ber_shc = []
    max_ber_surrogate = []
    
    for seed in range(n_seeds):
        np.random.seed(seed + 100)
        print(f"\n--- Running Seed {seed+1}/{n_seeds} ---")
        
        # Exact identical sub-optimal starting point for both
        taps_array = np.array([0.0, 0.0, -0.034, -0.2987, 0.6091, 0.0, 0.0582, 0.0, 0.0])
        pre_post = np.zeros(8)
        pre_post[:ffe_pre] = taps_array[:ffe_pre]
        pre_post[ffe_pre:] = taps_array[ffe_pre+1:9]
        
        start_params = np.zeros(D)
        start_params[:8] = pre_post
        start_params[8] = 0.0  # Safe initial CTLE
        start_params[9] = 2.5
        start_params[10] = 2.5
        start_params[11] = 1.0
        
        for alg in ['SHC', 'SafeQCD']:
            np.random.seed(seed + 100)
            config = {k: v.copy() if isinstance(v, dict) else v for k, v in base_config.items()}
            
            if alg == 'SHC':
                optimizer = SafeHillClimbingOptimizer(bounds, initial_step_size=0.05, max_regression_ratio=5.0)
            else:
                optimizer = SafeQCDOptimizer(bounds, probe_delta=0.01, max_allowed_log_ber=-2.0)
                
            X_data = [start_params.copy()]
            iter_count = [1]
            obj_val, ffe_ber, mlse_ber = objective_function(config, start_params, "result", iter_count)
            y_data = [obj_val]
            
            # We track the WORST MLSE BER encountered during the entire tuning session
            worst_mlse = mlse_ber
            
            for step in range(n_iterations):
                optimizer.fit(X_data, y_data)
                next_taps = optimizer.suggest_next()
                
                obj_val, ffe_ber, mlse_ber = objective_function(config, next_taps, "result", iter_count)
                
                if seed == 0:
                    print(f"    [{alg}] Step {step+1}: FFE BER: {ffe_ber:.2e}, MLSE BER: {mlse_ber:.2e}")
                
                if mlse_ber > worst_mlse:
                    worst_mlse = mlse_ber
                    
                X_data.append(next_taps)
                y_data.append(obj_val)
                
            print(f"  {alg} Worst MLSE BER: {worst_mlse:.2e}")
            if alg == 'SHC':
                max_ber_shc.append(worst_mlse)
            else:
                max_ber_surrogate.append(worst_mlse)
                
    print("\n=== Statistical Summary ===")
    print(f"SHC           Mean Worst BER: {np.mean(max_ber_shc):.2e} (std: {np.std(max_ber_shc):.2e})")
    print(f"SafeQCD       Mean Worst BER: {np.mean(max_ber_surrogate):.2e} (std: {np.std(max_ber_surrogate):.2e})")
    
    # Write to a file so it can be viewed
    with open('proof_results.txt', 'w') as f:
        f.write("=== Statistical Summary ===\n")
        f.write(f"SHC           Mean Worst BER: {np.mean(max_ber_shc):.2e} (std: {np.std(max_ber_shc):.2e})\n")
        f.write(f"SafeQCD       Mean Worst BER: {np.mean(max_ber_surrogate):.2e} (std: {np.std(max_ber_surrogate):.2e})\n")

if __name__ == '__main__':
    run_proof()
