# -*- coding: utf-8 -*-
"""scratch/diag_cross_env_local_validity.py

Cross-environment local-validity check (control-variable generalization test):

Models are trained (globally) at the base IL10 environment. For each target
environment (IL20, CD28, DGD5) we sample an LHS neighborhood around the same
seed x0, evaluate the REAL BER_MLSE there, and compare Model A/B local ranking
& direction vs truth. This answers:
  - Does the IL10-trained Model A/B keep correct *local direction* when the
    physical environment drifts (the thing Stage-2 descent relies on)?
  - Is any "negative optimization" actually an environmental anti-correlation?
"""
import os, sys, time, pickle
os.environ['OMP_NUM_THREADS'] = '1'
import numpy as np
import pandas as pd
from scipy.stats import qmc, spearmanr
import create_config, utils_config
import ddps_optimizer as D
import train_surrogates as _ts
sys.modules['__main__'].WhiteBoxRidge = _ts.WhiteBoxRidge
sys.modules['__main__'].WhiteBoxGPR = _ts.WhiteBoxGPR

def local_check(cfg, model_a, model_b, name, n=40, seed=11):
    ffe_pre = int(cfg['tx'].get('ffe_pre', 4))
    seed_pre_post = np.zeros(8)
    seed_pre_post[:ffe_pre] = D.SEED_TAPS[:ffe_pre]
    seed_pre_post[ffe_pre:] = D.SEED_TAPS[ffe_pre + 1:]
    sampler = qmc.LatinHypercube(d=10, seed=seed)
    sp = sampler.random(n=n)
    seed_lb, seed_ber = D._physical_eval(cfg, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2)
    predA_seed = D._predict_a(model_a, cfg, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2)
    predB_seed = D._predict_b(model_b, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2)

    real, pa, pb = [], [], []
    for i in range(n):
        pre_post = seed_pre_post + (sp[i, :8] * 2 - 1.0) * D.FFE_SPREAD
        gdc = float(np.clip(D.SEED_GDC + (sp[i, 8] * 2 - 1.0) * D.CTLE_SPREAD,
                            D.CTLE_GDC_MIN, D.CTLE_GDC_MAX))
        gdc2 = float(np.clip(D.SEED_GDC2 + (sp[i, 9] * 2 - 1.0) * D.CTLE_SPREAD,
                             D.CTLE_GDC2_MIN, D.CTLE_GDC2_MAX))
        taps = D.construct_9tap(pre_post, ffe_pre)
        lb, ber = D._physical_eval(cfg, taps.copy(), gdc, gdc2)
        real.append(lb)
        pa.append(D._predict_a(model_a, cfg, taps.copy(), gdc, gdc2))
        pb.append(D._predict_b(model_b, taps.copy(), gdc, gdc2))
    real = np.array(real); pa = np.array(pa); pb = np.array(pb)

    rA = spearmanr(real, pa).correlation
    rB = spearmanr(real, pb).correlation
    d_real = real - seed_lb
    dA = pa - predA_seed
    dB = pb - predB_seed
    big = np.abs(d_real) > 0.05
    agreeA = np.sign(dA[big]) == np.sign(d_real[big]) if big.sum() else np.nan
    agreeB = np.sign(dB[big]) == np.sign(d_real[big]) if big.sum() else np.nan

    def ols_grad(yv, Xm):
        Xd = np.hstack([np.ones((len(Xm), 1)), Xm])
        beta, *_ = np.linalg.lstsq(Xd, yv, rcond=None)
        return beta[1:]
    # X coordinates for the cloud (pre/post 8 + gdc,gdc2): need x for each sample
    Xm = np.zeros((n, 10))
    for i in range(n):
        pre_post = seed_pre_post + (sp[i, :8] * 2 - 1.0) * D.FFE_SPREAD
        gdc = float(np.clip(D.SEED_GDC + (sp[i, 8] * 2 - 1.0) * D.CTLE_SPREAD,
                            D.CTLE_GDC_MIN, D.CTLE_GDC_MAX))
        gdc2 = float(np.clip(D.SEED_GDC2 + (sp[i, 9] * 2 - 1.0) * D.CTLE_SPREAD,
                             D.CTLE_GDC2_MIN, D.CTLE_GDC2_MAX))
        Xm[i] = np.concatenate([pre_post, [gdc, gdc2]])
    g_real = ols_grad(real, Xm); g_A = ols_grad(pa, Xm); g_B = ols_grad(pb, Xm)
    cosA = float(np.dot(g_real, g_A) / (np.linalg.norm(g_real) * np.linalg.norm(g_A) + 1e-12))
    cosB = float(np.dot(g_real, g_B) / (np.linalg.norm(g_real) * np.linalg.norm(g_B) + 1e-12))

    print(f'\n===== env {name} (n={n}) =====')
    print(f'  seed real log10BER={seed_lb:.4f} (BER={seed_ber:.3e}); real spread {real.min():.3f}..{real.max():.3f}')
    print(f'  Spearman(real,ModelA)={rA:+.3f} | Spearman(real,ModelB)={rB:+.3f}')
    print(f'  sign-consistency (n_big={big.sum()}): ModelA {np.nanmean(agreeA)*100:.0f}% | ModelB {np.nanmean(agreeB)*100:.0f}%')
    print(f'  cos(g_real,g_ModelA)={cosA:+.3f} | cos(g_real,g_ModelB)={cosB:+.3f}')
    print(f'  #pts better than seed: {(real < seed_lb - 0.02).sum()}/{n}')
    return {'env': name, 'spearA': rA, 'spearB': rB, 'agreeA': float(np.nanmean(agreeA)),
            'agreeB': float(np.nanmean(agreeB)), 'cosA': cosA, 'cosB': cosB,
            'real_min': real.min(), 'seed_lb': seed_lb, 'n_better': int((real < seed_lb - 0.02).sum())}

def main():
    create_config.generate_config()
    model_a = pickle.load(open('archive/20260904_ddps_v1_physical_pre_v2/models/model_a_s21.pkl', 'rb'))
    model_b = pickle.load(open('archive/20260904_ddps_v1_physical_pre_v2/models/model_b_config.pkl', 'rb'))
    cases = [
        ('IL_Sweep_14dB', dict(il=14.0, cd=0.0, dgd=0.0, pol=0.0)),
        ('IL_Worst_20dB', dict(il=20.0, cd=0.0, dgd=0.0, pol=0.0)),
        ('CD_Sweep_28ps', dict(il=10.0, cd=28.0, dgd=0.0, pol=0.0)),
        ('DGD_Sweep_5ps', dict(il=10.0, cd=0.0, dgd=5.0, pol=45.0)),
    ]
    out = []
    for name, cc in cases:
        cfg = utils_config.load_config('config.xlsx')
        cfg['system']['enable_eye_plot'] = False
        cfg['system']['enable_spectrum_plot'] = False
        cfg['channel']['tx_pcb_loss_nyquist_db'] = cc['il']
        cfg['channel']['rx_pcb_loss_nyquist_db'] = cc['il']
        cfg['channel']['cd_ps_nm'] = cc['cd']
        cfg['channel']['dgd_ps'] = cc['dgd']
        cfg['channel']['pol_angle_deg'] = cc['pol']
        out.append(local_check(cfg, model_a, model_b, name))
    pd.DataFrame(out).to_csv('scratch/diag_cross_env_evidence.csv', index=False)
    print('\n[saved] scratch/diag_cross_env_evidence.csv')

if __name__ == '__main__':
    main()
