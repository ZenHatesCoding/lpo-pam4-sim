import numpy as np
import os
import matplotlib.pyplot as plt
from datetime import datetime
from utils_config import load_config
from main import run_sim
import create_config

from bo_optimizer import BayesianOptimizer
from sa_optimizer import SimulatedAnnealingOptimizer
from ga_optimizer import GeneticAlgorithmOptimizer
from shc_optimizer import SafeHillClimbingOptimizer
from surrogate_shc_optimizer import SurrogateSHCOptimizer
from safe_qcd_optimizer import SafeQCDOptimizer
from esc_optimizer import SafeESCOptimizer
from optimize_tx import objective_function
from surrogate_metric import build_golden_cluster, evaluate_surrogate_metric

def get_optimizer(opt_type, bounds, config, is_surrogate=False):
    if opt_type == 'SA':
        return SimulatedAnnealingOptimizer(bounds, max_regression_ratio=10.0, initial_temp=1.0 if not is_surrogate else 10.0, cooling_rate=0.85)
    elif opt_type == 'GA':
        return GeneticAlgorithmOptimizer(bounds, pop_size=5, mutation_rate=0.5, mutation_scale=0.05)
    elif opt_type == 'SHC':
        return SafeHillClimbingOptimizer(bounds, initial_step_size=0.05, max_regression_ratio=10.0)
    elif opt_type == 'Surrogate_SHC':
        return SurrogateSHCOptimizer(bounds, initial_step_size=0.05, max_regression_ratio=10.0, max_allowed_log_ber=-2.0)
    elif opt_type == 'ESC_Safe':
        return SafeESCOptimizer(bounds, initial_step_size=0.05, max_allowed_log_ber=-2.0, dither_amplitude=0.05)
    elif opt_type == 'SafeQCD':
        return SafeQCDOptimizer(bounds, probe_delta=0.01, max_allowed_log_ber=-2.0)
    elif opt_type == 'BO_Safe':
        return BayesianOptimizer(bounds, noise_var=1e-3)
    else:
        raise ValueError(f"Unknown optimizer: {opt_type}")

def run_two_stage_optimization(combo_name, stage1_type, stage2_type, base_config, bounds, result_dir, n_stage1=20, n_stage2=20, stage2_metric_mode='mlse_ber'):
    print(f"\n==============================================")
    print(f"  Running Combo: {combo_name} ({stage1_type} -> {stage2_type} | Mode: {stage2_metric_mode})")
    print(f"==============================================")
    
    config = {k: v.copy() if isinstance(v, dict) else v for k, v in base_config.items()}
    D = len(bounds)
    
    # Logging
    with open(os.path.join(result_dir, "sim_log.txt"), "a") as f:
        f.write(f"\n{'='*50}\n")
        f.write(f"  Starting Combo: {combo_name}\n")
        f.write(f"  Stage 1: {stage1_type} (Budget: {n_stage1})\n")
        f.write(f"  Stage 2: {stage2_type} (Budget: {n_stage2}) [Metric: {stage2_metric_mode}]\n")
        f.write(f"{'='*50}\n")
        
    X_data = []
    y_data = []
    mlse_history = []
    ffe_history = []
    iter_count = [1]
    
    ffe_pre = int(base_config['tx'].get('ffe_pre', 4))
    if int(base_config['tx']['ffe_taps']) != 9:
        ffe_pre = 1
        
    default_params = np.zeros(D)
    taps_array = np.array([0.0, 0.0, -0.034, -0.2987, 0.6091, 0.0, 0.0582, 0.0, 0.0])
    pre_post = np.zeros(8)
    pre_post[:ffe_pre] = taps_array[:ffe_pre]
    pre_post[ffe_pre:] = taps_array[ffe_pre+1:9]
    default_params[:8] = pre_post
    default_params[8] = config['tx'].get('ctle_g_dc_db', -12.0)
    if D > 9:
        default_params[9] = config['tx'].get('ctle_fz_ratio', 2.5)
        default_params[10] = config['tx'].get('ctle_fp1_ratio', 2.5)
        default_params[11] = config['tx'].get('ctle_fp2_ratio', 1.0)
        
    obj_val, ffe_ber, mlse_ber = objective_function(config, default_params, result_dir, iter_count)
    print(f"Default -> FFE BER: {ffe_ber:.2e} | MLSE BER: {mlse_ber:.2e}")
    
    X_data.append(default_params)
    y_data.append(obj_val)
    mlse_history.append(mlse_ber)
    ffe_history.append(ffe_ber)
    
    # ------------------ STAGE 1 ------------------
    stage1_opt = get_optimizer(stage1_type, bounds, config)
    if stage1_type == 'BO_Safe':
        stage1_opt.fit([default_params], [np.log10(mlse_ber)])
        
    print(f"Entering Stage 1 ({stage1_type}) for {n_stage1} iters...")
    for step in range(n_stage1):
        stage1_opt.fit(X_data, y_data)
        if stage1_type == 'GA':
            next_taps = stage1_opt.suggest_next(X_data=X_data)
        elif stage1_type == 'BO_Safe':
            next_taps = stage1_opt.suggest_next(n_coarse=2000, n_fine_steps=50, patience=15, lr=0.1, max_allowed_log_ber=-2.0)
        else:
            next_taps = stage1_opt.suggest_next(n_coarse=2000, n_fine_steps=50, patience=15, lr=0.1)
            
        obj_val, ffe_ber, mlse_ber = objective_function(config, next_taps, result_dir, iter_count)
        print(f"Stage 1 [{step+1}/{n_stage1}] | Best MLSE: {np.min(mlse_history):.2e} | Cur FFE: {ffe_ber:.2e} | Cur MLSE: {mlse_ber:.2e}")
        
        X_data.append(next_taps)
        y_data.append(obj_val)
        mlse_history.append(mlse_ber)
        ffe_history.append(ffe_ber)
        
    # Identify Stage 1 performance
    best_mlse_stage1 = np.min(mlse_history)
    
    # --- Prepare Stage 2 ---
    is_surrogate = (stage2_metric_mode == 'tx_surrogate')
    stage2_opt = get_optimizer(stage2_type, bounds, config, is_surrogate=is_surrogate)
    
    X_data_stage2 = X_data.copy()
    if is_surrogate:
        print(f"Building TX Surrogate Statistical Model from all Stage 1 results...")
        mu_golden, cov_golden_inv, mapping_params, tx_pam4_eval = build_golden_cluster(X_data, y_data, config)
        
        # We need to re-evaluate history using the surrogate distance to seed the stage 2 optimizer properly
        y_data_stage2 = []
        for x in X_data_stage2:
            pseudo_log = evaluate_surrogate_metric(x, mu_golden, cov_golden_inv, mapping_params, tx_pam4_eval, config)
            y_data_stage2.append(pseudo_log)
    else:
        y_data_stage2 = y_data.copy()
        
    print(f"Entering Stage 2 ({stage2_type}) for {n_stage2} iters (Mode: {stage2_metric_mode})...")
    
    # Replay history to build Stage 2's model state
    for i in range(len(X_data_stage2)):
        stage2_opt.fit(X_data_stage2[:i+1], y_data_stage2[:i+1])
        
    for step in range(n_stage2):
        if stage2_type == 'GA':
            next_taps = stage2_opt.suggest_next(X_data=X_data_stage2)
        elif stage2_type == 'BO_Safe':
            next_taps = stage2_opt.suggest_next(n_coarse=2000, n_fine_steps=50, patience=15, lr=0.1, max_allowed_log_ber=-2.0)
        else:
            next_taps = stage2_opt.suggest_next(n_coarse=2000, n_fine_steps=50, patience=15, lr=0.1)
            
        # We STILL run the true objective_function just to log the actual MLSE BER for our comparison plot
        # But the optimizer will ONLY see the surrogate distance if is_surrogate=True
        obj_val, ffe_ber, mlse_ber = objective_function(config, next_taps, result_dir, iter_count)
        
        if is_surrogate:
            pseudo_log = evaluate_surrogate_metric(next_taps, mu_golden, cov_golden_inv, mapping_params, tx_pam4_eval, config)
            y_val_for_opt = pseudo_log
            print(f"Stage 2 [{step+1}/{n_stage2}] | Best MLSE: {np.min(mlse_history):.2e} | PsLogBER: {pseudo_log:.2f} | Cur MLSE: {mlse_ber:.2e}")
        else:
            y_val_for_opt = obj_val
            print(f"Stage 2 [{step+1}/{n_stage2}] | Best MLSE: {np.min(mlse_history):.2e} | Cur FFE: {ffe_ber:.2e} | Cur MLSE: {mlse_ber:.2e}")
        
        X_data_stage2.append(next_taps)
        y_data_stage2.append(y_val_for_opt)
        mlse_history.append(mlse_ber)
        ffe_history.append(ffe_ber)
        stage2_opt.fit(X_data_stage2, y_data_stage2) # Update model with the new point
        
    # Metrics
    stage2_mlse_data = mlse_history[n_stage1+1:]
    best_mlse_final = np.min(mlse_history)
    max_mlse_stage2 = np.max(stage2_mlse_data) if len(stage2_mlse_data) > 0 else np.inf
    std_mlse_stage2 = np.std(np.log10(stage2_mlse_data)) if len(stage2_mlse_data) > 0 else 0
    
    print(f"Combo Complete: Best Stage 1 MLSE: {best_mlse_stage1:.2e}, Max Stage 2 MLSE: {max_mlse_stage2:.2e}, Final Best MLSE: {best_mlse_final:.2e}")
    
    return {
        'mlse_history': mlse_history,
        'ffe_history': ffe_history,
        'best_mlse_stage1': best_mlse_stage1,
        'max_mlse_stage2': max_mlse_stage2,
        'best_mlse_final': best_mlse_final,
        'std_mlse_stage2_log': std_mlse_stage2
    }

def main():
    print("=== Starting Two-Stage Optimization (1e-5 Level Validation) ===")
    create_config.generate_config()
    base_config = load_config('config.xlsx')
    
    # ==========================================
    # 🚀 Simulation Depth Toggle
    # Options: 'FAST_1E4' (Quick), 'DEEP_1E5' (Thorough)
    # ==========================================
    TEST_MODE = 'DEEP_1E5'
    
    if TEST_MODE == 'FAST_1E4':
        base_config['channel']['snr_db'] = 26.0
        base_config['system']['num_symbols'] = 200000
        base_config['tx']['pattern_length'] = 100000
    elif TEST_MODE == 'DEEP_1E5':
        base_config['channel']['snr_db'] = 28.0
        base_config['system']['num_symbols'] = 1048576
        base_config['tx']['pattern_length'] = 524288
        
    if 'pcb_loss_nyquist_db' not in base_config['channel']:
        base_config['channel']['pcb_loss_nyquist_db'] = 15.0
        
    print(f"Num Symbols: {base_config['system']['num_symbols']}")
    print(f"SNR (dB): {base_config['channel']['snr_db']}")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_dir = os.path.join("result", f"{timestamp}_two_stage")
    if not os.path.exists(result_dir):
        os.makedirs(result_dir)
        
    opt_mode = base_config['tx'].get('optimize_mode', 'JOINT').upper()
    D = 12 if opt_mode == 'JOINT' else 9
    bounds = np.zeros((D, 2))
    for i in range(8):
        bounds[i] = [-0.3, 0.3] 
    bounds[8] = [-20.0, 0.0]
    if D > 9:
        bounds[9] = [1.0, 5.0]
        bounds[10] = [1.0, 5.0]
        bounds[11] = [0.5, 3.0] 
        
    combinations = [
        ('BO->Surrogate', 'BO_Safe', 'Surrogate_SHC'),
        ('SA->Surrogate', 'SA', 'Surrogate_SHC'),
        ('GA->Surrogate', 'GA', 'Surrogate_SHC'),
        ('BO->ESC', 'BO_Safe', 'ESC_Safe'),
        ('BO->SafeQCD', 'BO_Safe', 'SafeQCD')
    ]
    
    results = {}
    n_stage1 = 20
    n_stage2 = 20
    
    for idx, (name, s1, s2) in enumerate(combinations):
        # Generate a unique deterministic seed for this combination
        combo_seed = 42 + idx
        
        # Run Baseline (MLSE BER feedback in Stage 2)
        np.random.seed(combo_seed)
        res_baseline = run_two_stage_optimization(f"{name}_Baseline", s1, s2, base_config, bounds, result_dir, n_stage1, n_stage2, stage2_metric_mode='mlse_ber')
        results[f"{name}_Baseline"] = res_baseline
        
        # Run Surrogate (TX-Only Statistical Feedback in Stage 2)
        # Reset the seed to the exact same value so Stage 1 is mathematically identical
        np.random.seed(combo_seed)
        res_surrogate = run_two_stage_optimization(f"{name}_Surrogate", s1, s2, base_config, bounds, result_dir, n_stage1, n_stage2, stage2_metric_mode='tx_surrogate')
        results[f"{name}_Surrogate"] = res_surrogate
        
    # Group by base combo name (without _Baseline or _Surrogate)
    base_combos = {}
    for key in results.keys():
        if key.endswith('_Baseline'):
            base = key.replace('_Baseline', '')
            if base not in base_combos:
                base_combos[base] = {}
            base_combos[base]['Baseline'] = results[key]
        elif key.endswith('_Surrogate'):
            base = key.replace('_Surrogate', '')
            if base not in base_combos:
                base_combos[base] = {}
            base_combos[base]['Surrogate'] = results[key]
            
    # Plotting
    n_combos = len(base_combos)
    fig, axes = plt.subplots(n_combos, 1, figsize=(12, 4 * n_combos), sharex=True)
    if n_combos == 1:
        axes = [axes]
        
    for ax, (base, modes) in zip(axes, base_combos.items()):
        if 'Baseline' in modes:
            ax.semilogy(modes['Baseline']['mlse_history'], label='RX MLSE Feedback (Baseline)', color='blue', linestyle='-', marker='o', markersize=4)
        if 'Surrogate' in modes:
            ax.semilogy(modes['Surrogate']['mlse_history'], label='TX GPR+UCB Surrogate (Proposed)', color='red', linestyle='--', marker='x', markersize=4)
            
        ax.axvline(x=n_stage1, color='black', linestyle=':', label='Stage 1 / Stage 2 Boundary')
        ax.set_title(f"Optimization Combination: {base} (SNR={base_config['channel']['snr_db']} dB)")
        ax.set_ylabel("MLSE BER")
        ax.grid(True, which="both", ls="--", alpha=0.6)
        ax.legend()
        
    axes[-1].set_xlabel("Evaluation Step")
    plt.tight_layout()
    plot_path = os.path.join(result_dir, "two_stage_convergence.png")
    plt.savefig(plot_path)
    plt.close()
    
    # Write Summary Markdown
    with open(os.path.join(result_dir, 'two_stage_summary.md'), 'w', encoding='utf-8') as f:
        f.write("# 两阶段优化对比报告 (双模式对比)\n\n")
        f.write("此报告对比了 **Baseline (依赖收端 BER反馈)** 和 **Surrogate (搭载 GPR + UCB 护栏的发端统计模型)** 两种模式在第二阶段 (Stage 2) 的表现。\n\n")
        f.write(f"- **Symbols**: {base_config['system']['num_symbols']}\n")
        f.write(f"- **SNR**: {base_config['channel']['snr_db']} dB\n")
        f.write(f"- **Stage 1 Iters**: {n_stage1}\n")
        f.write(f"- **Stage 2 Iters**: {n_stage2}\n\n")
        
        f.write(f"![Two-Stage Convergence](file:///{os.path.abspath(plot_path).replace(os.sep, '/')})\n\n")
        
        for base, modes in base_combos.items():
            f.write(f"## {base}\n")
            f.write("| 模式 (Mode) | 第一阶段最优 (Stage 1 Best) | 第二阶段最差抖动 (Stage 2 Max) | 最终收敛最优 (Final Best) | Stage 2 对数BER标准差 |\n")
            f.write("| --- | --- | --- | --- | --- |\n")
            
            for mode_name, res in modes.items():
                s1_best = res['best_mlse_stage1']
                s2_max = res['max_mlse_stage2']
                final_best = res['best_mlse_final']
                std_log = res['std_mlse_stage2_log']
                f.write(f"| **{mode_name}** | `{s1_best:.2e}` | `{s2_max:.2e}` | `{final_best:.2e}` | `{std_log:.3f}` |\n")
            f.write("\n")
            
    print(f"\nOptimization Complete! Results saved to {os.path.join(result_dir, 'two_stage_summary.md')}")

if __name__ == '__main__':
    main()
