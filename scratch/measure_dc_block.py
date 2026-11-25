# -*- coding: utf-8 -*-
"""实测隔直对真实 PAM4 波形的影响：同一用例、同一随机种子，比较
  ① 两处 100 kHz（新口径）② 一处 100 kHz ③ 不做隔直（fc=0）
看 ADC 输出的功率、低频分量和 BER 各变多少。用于交付件 §2.4 的「几乎透明」这句。

只跑 Python 小区（2^16），不做大点数比对。
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

import main as M
from utils_config import load_config

cfg0 = load_config()
cfg0['system']['num_symbols'] = 1 << 16
cfg0['system']['seed'] = 42

rows = []
for label, fc, stages in (('两处 100 kHz（新口径）', 100e3, 2),
                          ('一处 100 kHz', 100e3, 1),
                          ('不做隔直（fc=0）', 0.0, 2)):
    cfg = {k: (dict(v) if isinstance(v, dict) else v) for k, v in cfg0.items()}
    cfg['channel'] = dict(cfg0['channel'])
    cfg['channel']['ac_coupling_fc_hz'] = fc
    cfg['channel']['ac_coupling_stages'] = stages
    ber_mlse, ber_ffe, nodes = M.run_sim(cfg, return_nodes=True)
    adc = np.asarray(nodes['rx_adc'], dtype=float)
    n = len(adc)
    X = np.abs(np.fft.rfft(adc - adc.mean())) ** 2
    f = np.fft.rfftfreq(n, d=1.0 / (cfg['system']['baud_rate'] * cfg['system']['sps_adc']))
    band = lambda lo, hi: float(X[(f >= lo) & (f < hi)].sum())
    total = band(0, 1e12)
    low = band(0, 1e6) / max(total, 1e-30)
    rows.append((label, ber_mlse, ber_ffe, float(np.std(adc)), low, total))

print('%-22s %10s %10s %8s %10s' % ('口径', 'MLSE BER', 'FFE BER', 'ADC std', '1MHz 以下能量占比'))
for label, b1, b2, sd, low, tot in rows:
    print('%-22s %10.3e %10.3e %8.3f %9.3f%%' % (label, b1, b2, sd, 100 * low))
