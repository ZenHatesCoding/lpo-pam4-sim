# -*- coding: utf-8 -*-
"""「方向到底变了没有」——用**实际走过的路径**回答，而不是只看梯度夹角。

对每一格、每个用例：
  1. 路径共线度：总位移 Δx 中，沿「第 0 步方向」的分量占比（span 归一化坐标下算，否则 dB/dex 量纲会压死抽头）。
  2. 路径自转角：相邻两次位移向量之间的夹角（同一归一化坐标），衡量轨迹有没有真的拐弯。
  3. 横向残差：||Δx_perp|| / ||Δx||，即拐出去的那部分占多大比例。
  4. 组内自由度：把每组分别投影，看每个组自身是沿一条直线走还是真的在面内转。

用法：python scratch/path_collinearity.py --prefix result/ddps_cpp
"""
import argparse
import glob
import json
import os

import numpy as np
import pandas as pd

SPAN = np.array([0.20] * 5 + [6.0, 6.0, 0.60])   # 与代码 STEP_SPAN 一致，用于量纲归一
GROUPS = [('抽头 5 维', slice(0, 5)), ('CTLE 2 维', slice(5, 7)), ('gain 1 维', slice(7, 8))]
CELLS = [('full', '代理 × full'), ('rotate', '代理 × rotate'), ('secant', '代理 × secant'),
         ('direct_full', '回传 × full'), ('direct_rotate', '回传 × rotate'),
         ('direct_secant', '回传 × secant')]


def ang(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-12 or nb < 1e-12:
        return float('nan')
    c = float(np.dot(a, b) / (na * nb))
    return float(np.degrees(np.arccos(max(-1.0, min(1.0, c)))))


def load(f):
    tr = pd.read_csv(f)
    X = np.array([json.loads(v) for v in tr['x'].astype(str)], dtype=float)
    return tr, X


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--prefix', default='result/ddps_cpp')
    a = ap.parse_args()
    rows = []
    for cell, label in CELLS:
        d = '%s_%s' % (a.prefix, cell)
        if not os.path.isdir(d):
            continue
        proj, tort, perp, gproj = [], [], [], {g[0]: [] for g in GROUPS}
        for f in sorted(glob.glob(os.path.join(d, 'trace_*.csv'))):
            tr, X = load(f)
            if len(X) < 3:
                continue
            Xn = X * SPAN                      # 归一化：一步的「标准尺度」=1
            U = np.diff(Xn, axis=0)            # 每步位移
            U = U[np.linalg.norm(U, axis=1) > 1e-9]
            if len(U) < 2:
                continue
            u0 = U[0] / np.linalg.norm(U[0])
            D = Xn[-1] - Xn[0]
            nD = np.linalg.norm(D)
            if nD < 1e-9:
                continue
            c = abs(float(np.dot(D, u0))) / nD
            proj.append(c)
            perp.append(float(np.sqrt(max(0.0, 1.0 - c * c))))
            tort += [ang(U[k], U[k + 1]) for k in range(len(U) - 1)]
            for gname, sl in GROUPS:
                Dg = D[sl]
                u0g = U[0][sl]
                ng = np.linalg.norm(Dg)
                nu = np.linalg.norm(u0g)
                if ng < 1e-9 or nu < 1e-9:
                    continue
                cg = abs(float(np.dot(Dg, u0g))) / (ng * nu)
                gproj[gname].append(cg)
        if not proj:
            continue
        rows.append({
            'cell': cell, 'label': label, 'n': len(proj),
            'proj': float(np.nanmean(proj)), 'perp': float(np.nanmean(perp)),
            'tort': float(np.nanmean(tort)),
            'g_tap': float(np.nanmean(gproj['抽头 5 维'])) if gproj['抽头 5 维'] else float('nan'),
            'g_ctle': float(np.nanmean(gproj['CTLE 2 维'])) if gproj['CTLE 2 维'] else float('nan'),
            'g_gain': float(np.nanmean(gproj['gain 1 维'])) if gproj['gain 1 维'] else float('nan'),
        })
    if not rows:
        print('无数据')
        return
    df = pd.DataFrame(rows)
    print('=== 路径形态（span 归一化坐标，%d 用例平均）===' % df['n'].max())
    print('  共线度 = 总位移里沿第 0 步方向的分量占比（1.0 = 一条直线走到底）')
    print('  转角   = 相邻两步位移向量夹角均值（度）')
    print('  各组共线度 = 该组自身位移沿本组第 0 步方向的分量占比\n')
    hdr = '  %-16s %8s %8s %8s %9s %9s %9s' % ('格', '共线度', '横向残差', '路径转角', '抽头共线', 'CTLE共线', 'gain共线')
    print(hdr)
    for r in rows:
        print('  %-16s %8.3f %8.3f %7.1f° %9.3f %9.3f %9.3f'
              % (r['label'], r['proj'], r['perp'], r['tort'], r['g_tap'], r['g_ctle'], r['g_gain']))
    df.to_csv('scratch/path_collinearity.csv', index=False, encoding='utf-8-sig')
    print('\n  明细已存 scratch/path_collinearity.csv')


if __name__ == '__main__':
    main()
