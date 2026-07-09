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
    
    # 2 million symbols
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
        
    D = 10
    bounds = np.zeros((D, 2))
    for i in range(9):
        if i == 4:
            bounds[i] = [0.4, 1.0]
        else:
            bounds[i] = [-0.5, 0.3]
    bounds[9] = [-20.0, 0.0]
    
    n_iterations = 40

    for opt_type in algorithms:
        print(f"\n==============================================")
        print(f"    Running Optimizer: {opt_type}")
        print(f"==============================================")
        
        # Clone config
        config = {k: v.copy() if isinstance(v, dict) else v for k, v in base_config.items()}
        config['tx']['optimizer_type'] = opt_type
        
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
        iter_count = [1]
        
        # Initial point
        default_params = np.zeros(D)
        taps_val = config['tx'].get('custom_taps', None)
        if taps_val is not None:
            if isinstance(taps_val, str) and taps_val.strip().startswith('['):
                import ast
                default_params[:9] = np.array(ast.literal_eval(taps_val))
            else:
                default_params[:9] = np.array(taps_val)
        else:
            default_params[4] = 1.0
        default_params[9] = config['channel'].get('ctle_g_dc_db', -12.0)
        
        obj_val, ffe_ber, mlse_ber = objective_function(config, default_params, result_dir, iter_count)
        print(f"Default -> FFE BER: {ffe_ber:.2e} | MLSE BER: {mlse_ber:.2e}")
        
        X_data.append(default_params)
        y_data.append(obj_val)
        mlse_history.append(mlse_ber)
        
        # Initial random points for BO
        if opt_type == 'BO':
            print("Evaluating 10 Random Initial Points for BO...")
            for i in range(10):
                rand_params = np.random.uniform(bounds[:, 0], bounds[:, 1], D)
                rand_params[:9] = rand_params[:9] / np.sum(np.abs(rand_params[:9]))
                
                obj_val, ffe_ber, mlse_ber = objective_function(config, rand_params, result_dir, iter_count)
                X_data.append(rand_params)
                y_data.append(obj_val)
                mlse_history.append(mlse_ber)
                
        # Optimization Loop
        print(f"Entering {opt_type} Optimization Loop ({n_iterations} iters)...")
        for step in range(n_iterations):
            optimizer.fit(X_data, y_data)
            next_taps = optimizer.suggest_next(n_coarse=20, n_fine_steps=50, patience=15, lr=0.1)
            
            obj_val, ffe_ber, mlse_ber = objective_function(config, next_taps, result_dir, iter_count)
            print(f"Iter {step+1}/{n_iterations} [{opt_type}] | Best MLSE: {np.min(mlse_history):.2e} | Cur FFE: {ffe_ber:.2e} | Cur MLSE: {mlse_ber:.2e}")
            
            X_data.append(next_taps)
            y_data.append(obj_val)
            mlse_history.append(mlse_ber)
            
        # Collect results
        best_idx = np.argmin(y_data)
        best_params = X_data[best_idx]
        best_ffe_ber = 10**y_data[best_idx]
        best_mlse_ber = mlse_history[best_idx]
        
        # Max FFE BER encountered during standard loop (ignore BO initialization)
        if opt_type == 'BO':
            loop_y_data = y_data[11:]
        else:
            loop_y_data = y_data[1:]
        max_ffe_ber_in_loop = 10**np.max(loop_y_data) if len(loop_y_data) > 0 else best_ffe_ber
        
        results_summary[opt_type] = {
            'Best_FFE_BER': best_ffe_ber,
            'Best_MLSE_BER': best_mlse_ber,
            'Max_FFE_BER_Tested': max_ffe_ber_in_loop,
            'Best_Taps': np.round(best_params[:9], 4).tolist(),
            'Best_CTLE': round(best_params[9], 2)
        }
        
    # Write Summary Markdown
    with open(os.path.join(result_dir, 'comparison_summary.md'), 'w') as f:
        f.write(f"# Optimization Algorithm Comparison\n\n")
        f.write(f"- **Symbols**: {base_config['system']['num_symbols']}\n")
        f.write(f"- **SNR**: {base_config['channel']['snr_db']} dB\n\n")
        f.write("| Algorithm | Best MLSE BER | Best FFE BER | Max FFE BER (Safety Test) | Optimal CTLE |\n")
        f.write("| --- | --- | --- | --- | --- |\n")
        
        for alg in algorithms:
            r = results_summary[alg]
            f.write(f"| **{alg}** | `{r['Best_MLSE_BER']:.2e}` | `{r['Best_FFE_BER']:.2e}` | `{r['Max_FFE_BER_Tested']:.2e}` | `{r['Best_CTLE']} dB` |\n")
            
        f.write("\n## Optimal Taps\n")
        for alg in algorithms:
            f.write(f"- **{alg}**: `{results_summary[alg]['Best_Taps']}`\n")
            
    print(f"\nComparison Complete! Results saved to {result_dir}/comparison_summary.md")

if __name__ == '__main__':
    main()
