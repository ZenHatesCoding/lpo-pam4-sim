# -*- coding: utf-8 -*-
"""scratch/diag_neighborhood_sign_test.py

Root-cause diagnostic for the "Model A descends but real BER worsens" symptom.

Questions answered (around the DDPS seed x0, baseline IL10 physical model):
  1. Local ranking: Spearman(real log10BER, Model A/B prediction) over an
     LHS neighborhood of x0.
  2. Sign consistency: for each neighbor, does sign(ModelA_pred - seed_pred)
     agree with sign(real - seed_real)?
  3. Local linear trend: OLS gradient g_real of real log10BER over the cloud
     vs the same linear trend of Model A predictions -> cosine similarity.
  4. Train-domain mismatch: how far is x0's 9-tap config (center ~0.61) from
     the global training data (center tap pinned to 1.0)?
  5. Determinism / resolution: repeat the seed evaluation N times.
"""
import os, sys, time, pickle
os.environ['OMP_NUM_THREADS'] = '1'
import numpy as np
import pandas as pd
from scipy.stats import qmc, spearmanr
import create_config, utils_config
import ddps_optimizer as D
from train_surrogates import FIR_COLS, CONFIG_COLS

def main():
    create_config.generate_config()
    cfg = utils_config.load_config('config.xlsx')
    cfg['system']['enable_eye_plot'] = False
    cfg['system']['enable_spectrum_plot'] = False
    ffe_pre = int(cfg['tx'].get('ffe_pre', 4))

    # --- load the models that the latest generalization run actually used ---
    # (historical pkls were dumped with the class living in __main__)
    import sys, train_surrogates as _ts
    sys.modules['__main__'].WhiteBoxRidge = _ts.WhiteBoxRidge
    sys.modules['__main__'].WhiteBoxGPR = _ts.WhiteBoxGPR
    ma = pickle.load(open('archive/20260904_ddps_v1_physical_pre_v2/models/model_a_s21.pkl', 'rb'))
    mb = pickle.load(open('archive/20260904_ddps_v1_physical_pre_v2/models/model_b_config.pkl', 'rb'))

    x0 = D._taps_to_x(D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2, ffe_pre)
    print('x0 (10D pre/post + gDC,gDC2):', np.round(x0, 4))
    print('x0 9-tap config:', np.round(D.construct_9tap(x0[:8], ffe_pre), 4))

    # --- train-domain mismatch: global datasets have center tap pinned to 1.0 ---
    for p in ['archive/20260904_ddps_v1_physical_pre_v2/dataset/ddps_dataset_20260904_093954.csv']:
        dfg = pd.read_csv(p)
        print(f'\n[train domain] {p}: center tap range = '
              f'[{dfg["ffe_tap_4"].min():.4f}, {dfg["ffe_tap_4"].max():.4f}] (pinned to 1.0)')
    print(f'[train domain] seed/descent center tap ~ '
          f'{1.0 - np.abs(x0[:8]).sum():.4f}  -> OUTSIDE training box of Model B')

    # --- determinism / resolution check at seed ---
    print('\n[determinism] evaluating seed 3x (baseline IL10, 65536 sym)...')
    reps = []
    for k in range(3):
        lb, ber = D._physical_eval(cfg, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2)
        reps.append(lb)
        print(f'  rep{k+1}: log10BER = {lb:.6f}  (BER={ber:.3e})')
    print(f'  -> identical across reps: {np.allclose(reps, reps[0])}')

    # --- neighborhood LHS around x0 (same spread as Stage-1 collect) ---
    n = 60
    seed_pre_post = np.zeros(8)
    seed_pre_post[:ffe_pre] = D.SEED_TAPS[:ffe_pre]
    seed_pre_post[ffe_pre:] = D.SEED_TAPS[ffe_pre + 1:]
    sampler = qmc.LatinHypercube(d=10, seed=7)
    sp = sampler.random(n=n)

    seed_lb, seed_ber = D._physical_eval(cfg, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2)
    print(f'\n[neighborhood] seed real: log10BER={seed_lb:.6f} BER={seed_ber:.3e}')

    rows, X = [], []
    t0 = time.time()
    for i in range(n):
        pre_post = seed_pre_post + (sp[i, :8] * 2 - 1.0) * D.FFE_SPREAD
        gdc = float(np.clip(D.SEED_GDC + (sp[i, 8] * 2 - 1.0) * D.CTLE_SPREAD,
                            D.CTLE_GDC_MIN, D.CTLE_GDC_MAX))
        gdc2 = float(np.clip(D.SEED_GDC2 + (sp[i, 9] * 2 - 1.0) * D.CTLE_SPREAD,
                             D.CTLE_GDC2_MIN, D.CTLE_GDC2_MAX))
        taps = D.construct_9tap(pre_post, ffe_pre)
        x = np.concatenate([pre_post, [gdc, gdc2]])
        lb, ber = D._physical_eval(cfg, taps.copy(), gdc, gdc2)
        pa = D._predict_a(ma, cfg, taps.copy(), gdc, gdc2)
        pb = D._predict_b(mb, taps.copy(), gdc, gdc2)
        rows.append({'x': x, 'real_lb': lb, 'real_ber': ber, 'predA': pa, 'predB': pb})
        X.append(x)
    dt = time.time() - t0
    print(f'[neighborhood] evaluated {n} pts in {dt:.0f}s ({dt/n:.2f}s/pt)')

    R = pd.DataFrame(rows)
    Xm = np.array(X)
    real = R['real_lb'].values
    pa = R['predA'].values
    pb = R['predB'].values

    # 1) local ranking
    print('\n[1] LOCAL ranking (n=%d around seed):' % n)
    print(f'    Spearman(real, ModelA) = {spearmanr(real, pa).correlation:.3f} '
          f'(p={spearmanr(real, pa).pvalue:.3f})')
    print(f'    Spearman(real, ModelB) = {spearmanr(real, pb).correlation:.3f} '
          f'(p={spearmanr(real, pb).pvalue:.3f})')

    # 2) sign consistency of deltas vs seed
    d_real = real - seed_lb
    dA = pa - np.float64(D._predict_a(ma, cfg, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2))
    dB = pb - np.float64(D._predict_b(mb, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2))
    big = np.abs(d_real) > 0.05  # keep only neighbors with a meaningful real change
    if big.sum() > 0:
        agreeA = np.sign(dA[big]) == np.sign(d_real[big])
        agreeB = np.sign(dB[big]) == np.sign(d_real[big])
        print(f'[2] sign-consistency (|dreal|>0.05, n={big.sum()}): '
              f'ModelA {agreeA.mean()*100:.0f}% | ModelB {agreeB.mean()*100:.0f}%')
        # how much real change is attributable to noise ~ integer count quantization?
    print(f'    real logBER spread: {real.min():.3f}..{real.max():.3f} '
          f'(seed {seed_lb:.3f}) ; ModelA pred spread: {pa.min():.3f}..{pa.max():.3f}')

    # 3) local linear trend: OLS on X -> real vs Model A
    def ols_grad(yv, Xm2):
        Xd = np.hstack([np.ones((len(Xm2), 1)), Xm2])
        beta, *_ = np.linalg.lstsq(Xd, yv, rcond=None)
        return beta[1:]
    g_real = ols_grad(real, Xm)
    g_A = ols_grad(pa, Xm)
    g_B = ols_grad(pb, Xm)
    def cosine(a, b):
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))
    def lin_r2(yv, Xm2):
        Xd = np.hstack([np.ones((len(Xm2), 1)), Xm2])
        beta, *_ = np.linalg.lstsq(Xd, yv, rcond=None)
        pred = Xd @ beta
        return 1.0 - np.sum((yv - pred) ** 2) / np.sum((yv - yv.mean()) ** 2)
    print('[3] local OLS gradient cosine:')
    print(f'    cos(g_real, g_ModelA) = {cosine(g_real, g_A):+.3f}')
    print(f'    cos(g_real, g_ModelB) = {cosine(g_real, g_B):+.3f}')
    print(f'    cos(g_ModelA,g_ModelB)= {cosine(g_A, g_B):+.3f}')
    print(f'    local linear R2 of real logBER ~ x: {lin_r2(real, Xm):.3f} '
          f'(if ~0 the real surface is flat/quantized at this fidelity)')

    # save evidence table
    out = pd.DataFrame({
        'real_lb': real, 'real_ber': R['real_ber'].values, 'predA': pa, 'predB': pb})
    for j in range(10):
        out[f'x{j}'] = Xm[:, j]
    out.to_csv('scratch/diag_neighborhood_evidence.csv', index=False)
    print('\n[saved] scratch/diag_neighborhood_evidence.csv')
    print('\nSummary for human:')
    print('  Model A locally:', 'ANTI-correlated' if spearmanr(real, pa).correlation < -0.1 else
          ('correlated' if spearmanr(real, pa).correlation > 0.1 else 'UNINFORMATIVE (~0)'))

if __name__ == '__main__':
    main()
