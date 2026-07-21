import re

def rewrite_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        code = f.read()

    # 1. Update objective_function
    if "config['tx']['ctle_g_dc_db'] = params[8]" in code:
        old_obj = '''    config['tx']['ctle_g_dc_db'] = params[8]
    config['tx']['ctle_fz_ratio'] = params[9]
    config['tx']['ctle_fp1_ratio'] = params[10]
    config['tx']['ctle_fp2_ratio'] = params[11]'''
        new_obj = '''    config['tx']['ctle_g_dc_db'] = params[8]
    if len(params) > 9:
        config['tx']['ctle_fz_ratio'] = params[9]
        config['tx']['ctle_fp1_ratio'] = params[10]
        config['tx']['ctle_fp2_ratio'] = params[11]'''
        code = code.replace(old_obj, new_obj)

    # 2. Update bounds & modes
    old_bounds_opt = '''    D = 12
    # Constrain the search space
    bounds = np.zeros((D, 2))
    for i in range(8):
        bounds[i] = [-0.3, 0.3] # Pre/post cursors constrained
    bounds[8] = [-20.0, 0.0] # CTLE DC Gain from -20dB to 0dB
    bounds[9] = [1.0, 5.0]   # fz_ratio
    bounds[10] = [1.0, 5.0]  # fp1_ratio
    bounds[11] = [0.5, 3.0]  # fp2_ratio'''
    new_bounds_opt = '''    opt_mode = config['tx'].get('optimize_mode', 'JOINT').upper()
    D = 12 if opt_mode == 'JOINT' else 9
    
    # Constrain the search space
    bounds = np.zeros((D, 2))
    for i in range(8):
        bounds[i] = [-0.3, 0.3] # Pre/post cursors constrained
    bounds[8] = [-20.0, 0.0] # CTLE DC Gain from -20dB to 0dB
    if D > 9:
        bounds[9] = [1.0, 5.0]   # fz_ratio
        bounds[10] = [1.0, 5.0]  # fp1_ratio
        bounds[11] = [0.5, 3.0]  # fp2_ratio'''
    
    old_bounds_comp = '''    # We are optimizing 8 Tx FFE pre/post taps + 4 CTLE Params
    D = 12
    bounds = np.zeros((D, 2))
    for i in range(8):
        bounds[i] = [-0.3, 0.3] 
    bounds[8] = [-20.0, 0.0]
    bounds[9] = [1.0, 5.0]
    bounds[10] = [1.0, 5.0]
    bounds[11] = [0.5, 3.0]'''
    new_bounds_comp = '''    opt_mode = base_config['tx'].get('optimize_mode', 'JOINT').upper()
    D = 12 if opt_mode == 'JOINT' else 9
    bounds = np.zeros((D, 2))
    for i in range(8):
        bounds[i] = [-0.3, 0.3] 
    bounds[8] = [-20.0, 0.0]
    if D > 9:
        bounds[9] = [1.0, 5.0]
        bounds[10] = [1.0, 5.0]
        bounds[11] = [0.5, 3.0]'''
        
    code = code.replace(old_bounds_opt, new_bounds_opt)
    code = code.replace(old_bounds_comp, new_bounds_comp)

    # 3. Update defaults assignment
    old_default = '''    default_params[8] = config['tx'].get('ctle_g_dc_db', -12.0)
    default_params[9] = config['tx'].get('ctle_fz_ratio', 2.5)
    default_params[10] = config['tx'].get('ctle_fp1_ratio', 2.5)
    default_params[11] = config['tx'].get('ctle_fp2_ratio', 1.0)
    print(f"Eval Initial Default Params (8 FFE + 4 CTLE): {default_params}")'''
    new_default = '''    default_params[8] = config['tx'].get('ctle_g_dc_db', -12.0)
    if D > 9:
        default_params[9] = config['tx'].get('ctle_fz_ratio', 2.5)
        default_params[10] = config['tx'].get('ctle_fp1_ratio', 2.5)
        default_params[11] = config['tx'].get('ctle_fp2_ratio', 1.0)
    print(f"Eval Initial Default Params (Mode: {opt_mode}): {default_params}")'''
    code = code.replace(old_default, new_default)

    old_default2 = '''        default_params[8] = config['tx'].get('ctle_g_dc_db', -12.0)
        default_params[9] = config['tx'].get('ctle_fz_ratio', 2.5)
        default_params[10] = config['tx'].get('ctle_fp1_ratio', 2.5)
        default_params[11] = config['tx'].get('ctle_fp2_ratio', 1.0)'''
    new_default2 = '''        default_params[8] = config['tx'].get('ctle_g_dc_db', -12.0)
        if D > 9:
            default_params[9] = config['tx'].get('ctle_fz_ratio', 2.5)
            default_params[10] = config['tx'].get('ctle_fp1_ratio', 2.5)
            default_params[11] = config['tx'].get('ctle_fp2_ratio', 1.0)'''
    code = code.replace(old_default2, new_default2)

    # 4. Update random sampling for BO
    old_bo = '''                rand_params[8] = default_params[8] + np.random.randn() * 1.0 # CTLE wider
                rand_params[9] = default_params[9] + np.random.randn() * 0.5
                rand_params[10] = default_params[10] + np.random.randn() * 0.5
                rand_params[11] = default_params[11] + np.random.randn() * 0.2
                rand_params = np.clip(rand_params, bounds[:, 0], bounds[:, 1])'''
    new_bo = '''                rand_params[8] = default_params[8] + np.random.randn() * 1.0 # CTLE wider
                if D > 9:
                    rand_params[9] = default_params[9] + np.random.randn() * 0.5
                    rand_params[10] = default_params[10] + np.random.randn() * 0.5
                    rand_params[11] = default_params[11] + np.random.randn() * 0.2
                rand_params = np.clip(rand_params, bounds[:, 0], bounds[:, 1])'''
    code = code.replace(old_bo, new_bo)

    # 5. Fix printing
    old_print1 = '''print(f"Optimal CTLE: DC Gain={best_params[8]:.2f}dB, fz_ratio={best_params[9]:.2f}, fp1_ratio={best_params[10]:.2f}, fp2_ratio={best_params[11]:.2f}")'''
    new_print1 = '''if len(best_params) > 9:
        print(f"Optimal CTLE: DC Gain={best_params[8]:.2f}dB, fz={best_params[9]:.2f}, fp1={best_params[10]:.2f}, fp2={best_params[11]:.2f}")
    else:
        print(f"Optimal CTLE: DC Gain={best_params[8]:.2f}dB")'''
    code = code.replace(old_print1, new_print1)
    
    old_print2 = '''f.write(f"- **Optimal CTLE**: DC Gain=`{best_params[8]:.2f}dB`, fz_ratio=`{best_params[9]:.2f}`, fp1_ratio=`{best_params[10]:.2f}`, fp2_ratio=`{best_params[11]:.2f}`\\n\\n")'''
    new_print2 = '''if len(best_params) > 9:
            f.write(f"- **Optimal CTLE**: DC Gain=`{best_params[8]:.2f}dB`, fz=`{best_params[9]:.2f}`, fp1=`{best_params[10]:.2f}`, fp2=`{best_params[11]:.2f}`\\n\\n")
        else:
            f.write(f"- **Optimal CTLE**: DC Gain=`{best_params[8]:.2f}dB`\\n\\n")'''
    code = code.replace(old_print2, new_print2)
    
    old_print3 = '''f.write(f"Optimal CTLE: DC Gain={best_params[8]:.2f}dB, fz_ratio={best_params[9]:.2f}, fp1_ratio={best_params[10]:.2f}, fp2_ratio={best_params[11]:.2f}\\n")'''
    new_print3 = '''if len(best_params) > 9:
            f.write(f"Optimal CTLE: DC Gain={best_params[8]:.2f}dB, fz={best_params[9]:.2f}, fp1={best_params[10]:.2f}, fp2={best_params[11]:.2f}\\n")
        else:
            f.write(f"Optimal CTLE: DC Gain={best_params[8]:.2f}dB\\n")'''
    code = code.replace(old_print3, new_print3)

    old_print4 = '''            'Best_CTLE': f"{best_params[8]:.2f}dB, fz:{best_params[9]:.1f}, p1:{best_params[10]:.1f}, p2:{best_params[11]:.1f}"'''
    new_print4 = '''            'Best_CTLE': f"{best_params[8]:.2f}dB, fz:{best_params[9]:.1f}, p1:{best_params[10]:.1f}, p2:{best_params[11]:.1f}" if D > 9 else f"{best_params[8]:.2f}dB"'''
    code = code.replace(old_print4, new_print4)

    # 6. Update markdown summaries to report Mode
    if "comparison_summary.md" in code:
        code = code.replace(
            "f.write(f\"# Optimization Algorithm Comparison\\n\\n\")",
            "f.write(f\"# Optimization Algorithm Comparison (Mode: {opt_mode})\\n\\n\")"
        )
    if "optimization_report.md" in code:
        code = code.replace(
            "f.write(f\"# Tx FFE {opt_type} Optimization Report\\n\\n\")",
            "f.write(f\"# Tx FFE {opt_type} Optimization Report (Mode: {opt_mode})\\n\\n\")"
        )
        
    if "import compare_optimizers" in code:
        code = code.replace("import compare_optimizers", "import optimize_tx") # this shouldn't trigger but in case
    code = code.replace("from optimize_tx_ffe import", "from optimize_tx import")

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(code)

rewrite_file('optimize_tx.py')
rewrite_file('compare_optimizers.py')

# Ensure create_config properly injects optimize_mode in all profiles
with open('create_config.py', 'r', encoding='utf-8') as f:
    ccode = f.read()

import re
ccode = re.sub(r"('optimizer_type': '[A-Z]+',)", r"\1\n        'optimize_mode': 'JOINT',", ccode)
with open('create_config.py', 'w', encoding='utf-8') as f:
    f.write(ccode)

