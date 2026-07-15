import numpy as np
import os
from datetime import datetime
from utils_config import load_config
from main import run_sim
import create_config

from bo_optimizer import BayesianOptimizer
from sa_optimizer import SimulatedAnnealingOptimizer
from ga_optimizer import GeneticAlgorithmOptimizer
from shc_optimizer import SafeHillClimbingOptimizer
from optimize_tx_ffe import objective_function

def main():
    print("=== Starting Multi-Algorithm Optimization Comparison ===")
    create_config.generate_config()
    base_config = load_config('config.xlsx')
    
    # 1e-5 level simulation (1 Million symbols)
    base_config['channel']['snr_db'] = 28.0
    print(f"Num Symbols: {base_config['system']['num_symbols']}")
    print(f"SNR (dB): {base_config['channel']['snr_db']}")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_dir = os.path.join("result", f"{timestamp}_comparison")
    if not os.path.exists(result_dir):
        os.makedirs(result_dir)
        
    algorithms = ['BO', 'GA', 'SA', 'SHC']
    results_summary = {}
    
    # Enable realistic PCB loss
    if 'pcb_loss_nyquist_db' not in base_config['channel']:
        base_config['channel']['pcb_loss_nyquist_db'] = 15.0
        
    # We are optimizing 8 Tx FFE pre/post taps + 1 CTLE DC Gain
    D = 9
    bounds = np.zeros((D, 2))
    for i in range(8):
        bounds[i] = [-0.3, 0.3] 
    bounds[8] = [-20.0, 0.0] 
    
    # Extract ffe_pre
    ffe_pre = int(base_config['tx'].get('ffe_pre', 4))
    base_config['system']['num_symbols'] = 1048576
    base_config['tx']['pattern_length'] = 1048576
    if int(base_config['tx']['ffe_taps']) != 9:
        ffe_pre = 1
    
    n_iterations = 40

    for opt_type in algorithms:
        print(f"\n==============================================")
        print(f"    Running Optimizer: {opt_type}")
        print(f"==============================================")
        
        # Clone config
        config = {k: v.copy() if isinstance(v, dict) else v for k, v in base_config.items()}
        config['tx']['optimizer_type'] = opt_type
        
        if opt_type == 'SA':
            optimizer = SimulatedAnnealingOptimizer(bounds, max_regression_ratio=10.0, initial_temp=1.0, cooling_rate=0.85)
        elif opt_type == 'GA':
            optimizer = GeneticAlgorithmOptimizer(bounds, pop_size=5, mutation_rate=0.5, mutation_scale=0.05)
        elif opt_type == 'SHC':
            optimizer = SafeHillClimbingOptimizer(bounds, initial_step_size=0.05, max_regression_ratio=10.0)
        else:
            optimizer = BayesianOptimizer(bounds, noise_var=1e-3)
            
        # Write algorithm header to sim_log.txt
        with open(os.path.join(result_dir, "sim_log.txt"), "a") as f:
            f.write(f"\n{'='*50}\n")
            f.write(f"  Starting Optimizer: {opt_type}\n")
            f.write(f"  Config: {type(optimizer).__name__} (Budget: {n_iterations} iters)\n")
            f.write(f"{'='*50}\n")
            
        X_data = []
        y_data = []
        mlse_history = []
        ffe_history = []
        iter_count = [1]
        
        default_params = np.zeros(D)
        # Force the exact sub-optimal starting point visited by SA with MLSE BER 1.48e-03
        taps_array = np.array([0.0, 0.0, -0.034, -0.2987, 0.6091, 0.0, 0.0582, 0.0, 0.0])
        pre_post = np.zeros(8)
        pre_post[:ffe_pre] = taps_array[:ffe_pre]
        pre_post[ffe_pre:] = taps_array[ffe_pre+1:9]
        default_params[:8] = pre_post
            
        default_params[8] = config['channel'].get('ctle_g_dc_db', -12.0)
        
        obj_val, ffe_ber, mlse_ber = objective_function(config, default_params, result_dir, iter_count)
        print(f"Default -> FFE BER: {ffe_ber:.2e} | MLSE BER: {mlse_ber:.2e}")
        
        X_data.append(default_params)
        y_data.append(obj_val)
        mlse_history.append(mlse_ber)
        ffe_history.append(ffe_ber)
        
        # Initial random points for BO
        if opt_type == 'BO':
            print("Evaluating 10 Local Initial Points for BO...")
            for i in range(10):
                # Localized sampling around default_params for sample efficiency
                rand_params = default_params + np.random.randn(D) * 0.05
                rand_params[-1] = default_params[-1] + np.random.randn() * 1.0 # CTLE wider
                rand_params = np.clip(rand_params, bounds[:, 0], bounds[:, 1])
                
                obj_val, ffe_ber, mlse_ber = objective_function(config, rand_params, result_dir, iter_count)
                X_data.append(rand_params)
                y_data.append(obj_val)
                mlse_history.append(mlse_ber)
                ffe_history.append(ffe_ber)
                
        # Optimization Loop
        print(f"Entering {opt_type} Optimization Loop ({n_iterations} iters)...")
        for step in range(n_iterations):
            optimizer.fit(X_data, y_data)
            if opt_type == 'GA':
                next_taps = optimizer.suggest_next(X_data=X_data)
            else:
                next_taps = optimizer.suggest_next(n_coarse=2000, n_fine_steps=50, patience=15, lr=0.1)
            
            obj_val, ffe_ber, mlse_ber = objective_function(config, next_taps, result_dir, iter_count)
            print(f"Iter {step+1}/{n_iterations} [{opt_type}] | Best MLSE: {np.min(mlse_history):.2e} | Cur FFE: {ffe_ber:.2e} | Cur MLSE: {mlse_ber:.2e}")
            
            X_data.append(next_taps)
            y_data.append(obj_val)
            mlse_history.append(mlse_ber)
            ffe_history.append(ffe_ber)
            
        # Collect results
        best_idx = np.argmin(y_data)
        best_params = X_data[best_idx]
        best_ffe_ber = ffe_history[best_idx]
        best_mlse_ber = mlse_history[best_idx]
        
        # Max FFE BER encountered during standard loop (ignore BO initialization)
        if opt_type == 'BO':
            loop_ffe_data = ffe_history[10:]
            loop_mlse_data = mlse_history[10:]
        else:
            loop_ffe_data = ffe_history[1:]
            loop_mlse_data = mlse_history[1:]
        max_ffe_ber_in_loop = np.max(loop_ffe_data) if len(loop_ffe_data) > 0 else best_ffe_ber
        max_mlse_ber_in_loop = np.max(loop_mlse_data) if len(loop_mlse_data) > 0 else best_mlse_ber
        
        # Reconstruct optimal taps
        pre_post = best_params[:8]
        abs_sum = np.sum(np.abs(pre_post))
        if abs_sum > 0.6:
            pre_post = pre_post * (0.6 / abs_sum)
        taps = np.zeros(9)
        taps[:ffe_pre] = pre_post[:ffe_pre]
        taps[ffe_pre+1:] = pre_post[ffe_pre:]
        taps[ffe_pre] = 1.0 - np.sum(np.abs(pre_post))
        
        results_summary[opt_type] = {
            'Best_FFE_BER': best_ffe_ber,
            'Best_MLSE_BER': best_mlse_ber,
            'Max_FFE_BER_Tested': max_ffe_ber_in_loop,
            'Max_MLSE_BER_Tested': max_mlse_ber_in_loop,
            'Best_Taps': np.round(taps, 4).tolist(),
            'Best_CTLE': round(best_params[8], 2)
        }
        
    # Write Summary Markdown
    with open(os.path.join(result_dir, 'comparison_summary.md'), 'w') as f:
        f.write(f"# Optimization Algorithm Comparison\n\n")
        f.write(f"- **Symbols**: {base_config['system']['num_symbols']}\n")
        f.write(f"- **SNR**: {base_config['channel']['snr_db']} dB\n\n")
        f.write("| Algorithm | Best MLSE BER | Best FFE BER | Max FFE BER (Safety) | Max MLSE BER (Safety) | Optimal CTLE |\n")
        f.write("| --- | --- | --- | --- | --- | --- |\n")
        
        for alg in algorithms:
            r = results_summary[alg]
            f.write(f"| **{alg}** | `{r['Best_MLSE_BER']:.2e}` | `{r['Best_FFE_BER']:.2e}` | `{r['Max_FFE_BER_Tested']:.2e}` | `{r['Max_MLSE_BER_Tested']:.2e}` | `{r['Best_CTLE']} dB` |\n")
            
        f.write("\n## Optimal Taps\n")
        for alg in algorithms:
            f.write(f"- **{alg}**: `{results_summary[alg]['Best_Taps']}`\n")
            
        f.write("\n## Algorithm Configuration & Parameters\n")
        f.write("- **BO**: Gaussian Process (RBF Kernel). (10 initial random points)\n")
        f.write("- **GA**: Continuous Genetic Algorithm. (Population: 10, Mutation Rate: 0.3, Scale: 0.15)\n")
        f.write("- **SA**: Aggressive Simulated Annealing. (Initial Temp: 0.5, Cooling: 0.95, Max Regression: 10.0)\n")
        f.write("- **SHC**: Aggressive Hill Climbing. (Initial Step: 0.05, Max Regression: 10.0)\n")
            
    print(f"\nComparison Complete! Results saved to {result_dir}/comparison_summary.md")

if __name__ == '__main__':
    main()
