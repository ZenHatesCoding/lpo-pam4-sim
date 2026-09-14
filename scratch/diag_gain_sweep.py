# -*- coding: utf-8 -*-
"""决定性诊断：gain 维的最优方向是否随环境反转。

在 3 个环境（基线 / IL14x14 / IL20x20）里，固定种子 FFE/CTLE，扫一遍 driver_gain
倍率，记录真实 BER 与发端 MZM 驱动 RMS（drive_rms）。

读法：
  - 若基线最优 gain 偏低（防削顶）、高插损最优 gain 偏高（补摆幅）=> gain 方向随环境
    反转，这正是 v4 在恶劣环境不单调的根因。
  - drive_rms 是发端指标（Stage-2 允许拿，不需 BER）；若各环境的最优 BER 都落在
    接近的 drive_rms（≈MZM 线性最优摆幅）附近，则"用发端摆幅目标驱动 gain"是正确修法。
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import create_config, utils_config
import ddps_optimizer as D
from ddps_cases import apply_env_to_config, env_case
from tx_channel_extract import extract_tx_features

if not os.path.exists('config.xlsx'):
    create_config.generate_config()
base = utils_config.load_config('config.xlsx')
D.set_sim_seeds((42, 43, 44))

ratios = [0.30, 0.50, 0.65, 0.80, 1.00, 1.30, 1.60, 2.00, 2.50, 3.00, 4.00]
envs = ['Base_IL10x10', 'IL14x14', 'IL20x20', 'IL20x10_TxHeavy', 'IL10x20_RxHeavy']

print(f"{'env':16s} {'ratio':>6s} {'gain':>7s} {'BER':>11s} {'log10':>8s} {'drive_rms':>10s} {'rel_seed':>9s}")
print('-' * 78)
t0 = time.time()
for ename in envs:
    cfg = apply_env_to_config(base, env_case(ename))
    cfg['system']['num_symbols'] = 262144
    cfg['system']['enable_eye_plot'] = False
    cfg['system']['enable_spectrum_plot'] = False
    seed_lb = None
    for r in ratios:
        gain = D.DRIVER_GAIN_NOMINAL * r
        lb, ber = D._physical_eval(cfg, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2, gain)
        fir, drms = extract_tx_features(cfg, custom_tx_taps=D.SEED_TAPS.copy(), num_taps=7)
        if seed_lb is None:
            seed_lb = lb
        rel = 10.0 ** (lb - seed_lb)
        print(f"{ename:16s} {r:6.2f} {gain:7.4f} {ber:11.4e} {lb:8.4f} {drms:10.5f} {rel:9.3f}")
    print('-' * 78)
print(f"total {time.time()-t0:.0f}s")
