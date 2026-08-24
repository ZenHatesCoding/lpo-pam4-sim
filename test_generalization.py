import os
import pickle
import numpy as np
import pandas as pd
import create_config, utils_config
import ddps_optimizer as D

def run_generalization_test():
    create_config.generate_config()
    
    if not os.path.exists("models/model_a_s21.pkl") or not os.path.exists("models/model_b_config.pkl"):
        print("Models not found, run run_ddps() first.")
        return
        
    with open("models/model_a_s21.pkl", "rb") as f:
        model_a = pickle.load(f)
    with open("models/model_b_config.pkl", "rb") as f:
        model_b = pickle.load(f)
        
    print("Models loaded successfully. Now testing Stage 2 on different conditions...")
    
    test_cases = [
        {"name": "Baseline (SNR=26.5, CD=15dB loss)", "snr": 26.5, "cd": 15.0},
        {"name": "Low SNR (SNR=24.0, CD=15dB loss)", "snr": 24.0, "cd": 15.0},
        {"name": "High SNR (SNR=30.0, CD=15dB loss)", "snr": 30.0, "cd": 15.0},
        {"name": "High Dispersion (SNR=26.5, CD=20dB loss)", "snr": 26.5, "cd": 20.0},
    ]
    
    results = []
    
    for case in test_cases:
        print(f"\n--- Running DDPS Stage 2 for case: {case['name']} ---")
        cfg = utils_config.load_config('config.xlsx')
        cfg['system']['enable_eye_plot'] = False
        cfg['system']['enable_spectrum_plot'] = False
        cfg['channel']['snr_db'] = case['snr']
        cfg['channel']['pcb_loss_nyquist_db'] = case['cd']
        
        ffe_pre = int(cfg['tx'].get('ffe_pre', 4))
        x0 = D._taps_to_x(D.SEED_TAPS.copy(), D.SEED_CTLE, ffe_pre)
        
        # 安全参考 = Model B 对种子点的预测 (相对阈值，不依赖绝对SNR)
        safety_ref = D._predict_b(model_b, D.SEED_TAPS.copy(), D.SEED_CTLE)
        rng = np.random.RandomState(0)
        
        try:
            trace = D._stage2_descent(cfg, model_a, model_b, x0, ffe_pre, 10, safety_ref, D.GD_LR, rng)
            real_mlses = np.array([t['real_mlse'] for t in trace])
            best_mlse = np.min(real_mlses)
            results.append({
                "case": case['name'],
                "final_mlse": best_mlse,
                "steps": len(trace)
            })
            print(f"Case {case['name']} completed in {len(trace)} steps. Best MLSE = {best_mlse:.2e}")
        except Exception as e:
            print(f"Case {case['name']} failed: {e}")
            results.append({
                "case": case['name'],
                "final_mlse": np.nan,
                "steps": 0
            })
            
    df = pd.DataFrame(results)
    out_dir = os.path.join("result", "latest_comparison", "ddps")
    os.makedirs(out_dir, exist_ok=True)
    df.to_csv(os.path.join(out_dir, "generalization_summary.csv"), index=False)
    print("\n--- Generalization Test Summary ---")
    print(df)
    
if __name__ == "__main__":
    run_generalization_test()
