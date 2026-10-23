# -*- coding: utf-8 -*-
"""组内方向转角表（docs/DDPS_Method.md §3.3 的表格由本脚本生成）。

口径（与 §3.3 正文一致）：
- 用 `trace_<用例>.csv` 的 `grad` 列（当步实际使用的 8 维梯度），不用 `Δx`——
  `Δx` 含物理量程裁剪，`grad` 才直接回答「梯度方向到底转没转」。
- 抽头组 = 前 5 维；CTLE 组 = 第 6~7 维；gain 组 = 第 8 维。
- 每格统计：抽头梯度 vs 第 0 步梯度（逐用例均值 / 全部用例与步的全局最大）、
  相邻步抽头梯度夹角均值、CTLE 2 维 vs 第 0 步均值。

用法：
  python tools/turn_angle_table.py --prefix result/ddps_cpp            # 2^22 全量六格
  python tools/turn_angle_table.py --prefix result/ddps_equiv_cpp      # 2^18 等价目录
"""
import argparse
import glob
import json
import os

import numpy as np
import pandas as pd

ap = argparse.ArgumentParser(description='组内方向转角表（grad 列口径；docs §3.3 表就是这么算的）')
ap.add_argument('--prefix', default='result/ddps_cpp',
                help='结果目录前缀；全量口径 result/ddps_cpp、等价口径 result/ddps_equiv_cpp')
args = ap.parse_args()

# 3×2 矩阵的六个现役格：目录后缀、docs §3.3 表里的行名
CELLS = (
    ('full', '`full`'),
    ('rotate', '`rotate`'),
    ('secant', '`secant`'),
    ('direct_full', '回传 × full'),
    ('direct_rotate', '回传 × rotate'),
    ('direct_secant', '回传 × secant'),
)
GROUP = {'FFE': slice(0, 5), 'CTLE': slice(5, 7), 'gain': slice(7, 8)}
PREFIX = args.prefix
print('数据来源：%s_<格>/trace_<用例>.csv' % PREFIX)


def ang(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-15 or nb < 1e-15:
        return float('nan')
    return float(np.degrees(np.arccos(max(-1.0, min(1.0, float(np.dot(a, b) / (na * nb)))))))


rows = []
for cell, label in CELLS:
    d = os.path.join('%s_%s' % (PREFIX, cell))
    if not os.path.isdir(d):
        continue
    # 与交付件 `_grad_turn_stats` 同一口径：把全部（用例 × 步）的夹角汇总后再取均值 / 全局最大，
    # 不是「先按用例取均值再按用例平均」——两种口径在步数不均的格（回传行 5~15 步）会给出不同数字。
    vs0_all, step_all, ctle_all = [], [], []
    n_cases, n_steps = 0, 0
    for f in sorted(glob.glob(os.path.join(d, 'trace_*.csv'))):
        tr = pd.read_csv(f)
        G = np.array([json.loads(v) for v in tr['grad'].astype(str)], dtype=float)
        if len(G) < 3 or G.shape[1] < 8:
            continue
        taps, ctle = G[:, 0:5], G[:, 5:7]
        vs0_all += [ang(taps[0], taps[k]) for k in range(len(taps))]
        step_all += [ang(taps[k], taps[k + 1]) for k in range(len(taps) - 1)]
        ctle_all += [ang(ctle[0], ctle[k]) for k in range(len(ctle))]
        n_cases += 1
        n_steps += len(G)
    if not vs0_all:
        continue
    rows.append({
        'cell': cell, 'label': label, 'n_cases': n_cases, 'n_steps': n_steps,
        'ffe_mean': float(np.nanmean(vs0_all)),
        'ffe_max': float(np.nanmax(vs0_all)),
        'ffe_step': float(np.nanmean(step_all)),
        'ctle_mean': float(np.nanmean(ctle_all)),
    })

if not rows:
    raise SystemExit('✗ %s_* 里没有可用的 trace_*.csv' % PREFIX)

print('\n=== 逐格汇总（抽头组 / CTLE 组，单位：度）===')
for r in rows:
    print('  %-14s 用例 %2d  步 %3d  抽头 vs0 均值 %5.1f  全局最大 %5.1f  相邻步 %4.1f  CTLE vs0 %5.1f'
          % (r['cell'], r['n_cases'], r['n_steps'], r['ffe_mean'], r['ffe_max'],
             r['ffe_step'], r['ctle_mean']))

print('\n=== docs §3.3 表格行（可直接贴进 DDPS_Method.md）===')
for r in rows:
    bold = r['cell'] in ('secant', 'direct_secant')   # 加粗=结构性的「锁在初始射线」两格
    tag = '**%.1f° / %.1f°**' % (r['ffe_mean'], r['ffe_max']) if bold else '%.1f° / %.1f°' % (r['ffe_mean'], r['ffe_max'])
    stag = '**%.1f°**' % r['ffe_step'] if bold else '%.1f°' % r['ffe_step']
    ctag = '**%.1f°**' % r['ctle_mean'] if bold else '%.1f°' % r['ctle_mean']
    print('| %s | %s | %s | %s |' % (r['label'], tag, stag, ctag))
