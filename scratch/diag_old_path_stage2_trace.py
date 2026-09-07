# -*- coding: utf-8 -*-
"""scratch/diag_old_path_stage2_trace.py

Re-run Stage 2 with the CURRENT (broken-pipeline) models on the three key
generalization cases and dump the full trace, so we can see exactly how
(ModelA down, real up) or (ModelA down, real down) played out per case.
"""
import os, sys, time, pickle
os.environ['OMP_NUM_THREADS'] = '1'
import numpy as np
import pandas as pd
import create_config, utils_config
import ddps_optimizer as D
import train_surrogates as _ts
sys.modules['__main__'].WhiteBoxRidge = _ts.WhiteBoxRidge
sys.modules['__main__'].WhiteBoxGPR = _ts.WhiteBoxGPR

def run_case(cfg, model_a, model_b, name):
    ffe_pre = int(cfg['tx'].get('ffe_pre', 4))
    x0 = D._taps_to_x(D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2, ffe_pre)
    safety_ref = D._predict_b(model_b, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2)
    seed_lb, seed_ber = D._physical_eval(cfg, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2)
    rng = np.random.RandomState(42)
    print(f'\n===== case {name} =====')
    print(f'seed: log10BER={seed_lb:.4f} BER={seed_ber:.3e} | safety_ref={safety_ref:.3f}')
    t0 = time.time()
    trace = D._stage2_descent(cfg, model_a, model_b, x0, ffe_pre, 25, safety_ref, D.GD_LR, rng)
    print(f'case {name}: {len(trace)} steps in {time.time()-t0:.0f}s')
    if not trace:
        print('  NO STEPS TAKEN')
        return
    rows = []
    for t in trace:
        rows.append({'step': t['step'], 'predA': t['pred_a'], 'predB': t['pred_b'],
                     'real': np.log10(max(t['real_mlse'], 1e-12)),
                     'gdc': t['gdc'], 'gdc2': t['gdc2'],
                     'taps': np.round(t['taps'], 4).tolist()})
        print(f"  step {t['step']:2d}: predA={t['pred_a']:+.3f} predB={t['pred_b']:+.3f} "
              f"real_lb={np.log10(max(t['real_mlse'],1e-12)):.4f} "
              f"(BER {t['real_mlse']:.3e}) gdc={t['gdc']:.3f} gdc2={t['gdc2']:.3f}")
    df = pd.DataFrame(rows)
    real = np.array([r['real'] for r in rows]); pa = np.array([r['predA'] for r in rows])
    ibest = int(np.argmin(real))
    print(f'  best real step {ibest}: BER={10**real[ibest]:.3e}; best real {real.min():.4f}; '
          f'worst real {real.max():.4f}; final real {real[-1]:.4f}')
    print(f'  ModelA min at step {int(np.argmin(pa))} (pred {pa.min():.3f}); seed pred {pa[0]:.3f}')
    # when ModelA keeps decreasing but real rises => negative optimization region
    mono_a_down = np.all(np.diff(pa) <= 1e-9)
    mono_real_up_after = np.all(np.diff(real[1:]) >= -1e-9) if len(real) > 2 else False
    print(f'  ModelA monotonically down: {mono_a_down} | real monotonically up after step1: {mono_real_up_after}')
    df.to_csv(f'scratch/diag_trace_{name}.csv', index=False)

def main():
    create_config.generate_config()
    model_a = pickle.load(open('models/model_a_s21.pkl', 'rb'))
    model_b = pickle.load(open('models/model_b_config.pkl', 'rb'))
    cases = [
        ('Base_IL10', dict(il=10.0, cd=0.0, dgd=0.0, pol=0.0)),
        ('IL_Worst_20dB', dict(il=20.0, cd=0.0, dgd=0.0, pol=0.0)),
        ('Combined_Stress', dict(il=20.0, cd=15.0, dgd=5.0, pol=45.0)),
    ]
    for name, cc in cases:
        cfg = utils_config.load_config('config.xlsx')
        cfg['system']['enable_eye_plot'] = False
        cfg['system']['enable_spectrum_plot'] = False
        cfg['channel']['tx_pcb_loss_nyquist_db'] = cc['il']
        cfg['channel']['rx_pcb_loss_nyquist_db'] = cc['il']
        cfg['channel']['cd_ps_nm'] = cc['cd']
        cfg['channel']['dgd_ps'] = cc['dgd']
        cfg['channel']['pol_angle_deg'] = cc['pol']
        run_case(cfg, model_a, model_b, name)

if __name__ == '__main__':
    main()
