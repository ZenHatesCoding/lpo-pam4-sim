#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""compare_traces.py — Python vs C++ trace 逐步数值比对（比对口径：2^18 小点数低 SNR）。

按 AGENTS.md「开发方式」：Python 与 C++ 的等价性验证只在 2^18 小点数低 SNR 下做。
本脚本逐（环境 × 步 × 数值列）对比两个结果目录的 trace_*.csv，报告每列最大相对差，
作为 C++ 复刻一致性的机器判据（历史基线：secant 等价比对最大相对差 ~4.6e-13）。

用法：
  python cpp/compare_traces.py --py result/ddps_direct_py --cpp result/ddps_cpp_direct_equiv

判据：max_rel < 1e-9 视为数值等价（BER 为错误计数导出量，逐点一致即逐位一致）。
"""
import argparse
import glob
import os

import pandas as pd

# 参与比对的数值列（direct 方式 pred_b/allowed 恒 0，无比较意义，剔除）
COLS = ['gdc', 'gdc2', 'gain', 'u_gain', 'drive_rms', 'pred_a', 'real_lb', 'real_ber',
        'grad_norm']
REL_TOL = 1e-9


def _max_rel(a, b):
    import numpy as np
    a = a.to_numpy(dtype=float)
    b = b.to_numpy(dtype=float)
    denom = np.maximum(np.abs(b), 1e-300)
    rel = np.abs(a - b) / denom
    rel = rel[~np.isnan(rel)]
    return float(rel.max()) if len(rel) else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--py', required=True, help='Python 结果目录（参考实现）')
    ap.add_argument('--cpp', required=True, help='C++ 结果目录')
    ap.add_argument('--cols', default=','.join(COLS))
    ap.add_argument('--envs', default=None,
                    help='仅比对指定环境（逗号分隔）；缺省 = 两侧 trace 的交集 '
                         '（等价比对通常 C++ 只跑 2 个代表环境，其余记为 py-only）')
    a = ap.parse_args()
    cols = [c for c in a.cols.split(',') if c]

    py_envs = set(os.path.basename(p)[len('trace_'):-len('.csv')]
                  for p in glob.glob(os.path.join(a.py, 'trace_*.csv')))
    cpp_envs = set(os.path.basename(p)[len('trace_'):-len('.csv')]
                   for p in glob.glob(os.path.join(a.cpp, 'trace_*.csv')))
    if not py_envs:
        raise SystemExit('no trace_*.csv under %s' % a.py)
    if a.envs:
        envs = [e for e in a.envs.split(',') if e]
    else:
        envs = sorted(py_envs & cpp_envs)
    py_only = sorted(py_envs - cpp_envs)
    cpp_only = sorted(cpp_envs - py_envs)
    if py_only:
        print('[info] py-only envs (not compared): %s' % ', '.join(py_only))
    if cpp_only:
        print('[info] cpp-only envs (not compared): %s' % ', '.join(cpp_only))
    if not envs:
        raise SystemExit('no common envs to compare')

    worst = 0.0
    n_mismatch = 0
    for env in envs:
        fp = os.path.join(a.py, 'trace_%s.csv' % env)
        fc = os.path.join(a.cpp, 'trace_%s.csv' % env)
        if not os.path.exists(fc):
            print('[%s] MISSING in cpp dir' % env)
            n_mismatch += 1
            continue
        tp = pd.read_csv(fp)
        tc = pd.read_csv(fc)
        n = min(len(tp), len(tc))
        if len(tp) != len(tc):
            print('[%s] length mismatch py=%d cpp=%d' % (env, len(tp), len(tc)))
            n_mismatch += 1
        row = []
        env_worst = 0.0
        for c in cols:
            if c not in tp.columns or c not in tc.columns:
                continue
            r = _max_rel(tp[c].iloc[:n], tc[c].iloc[:n])
            env_worst = max(env_worst, r)
            row.append('%s=%.2e' % (c, r))
        worst = max(worst, env_worst)
        print('[%s] steps=%d %s -> worst %.2e' % (env, n, ' '.join(row), env_worst))

    print('---- verdict ----')
    print('worst max_rel = %.3e (tol %g)' % (worst, REL_TOL))
    if worst < REL_TOL and n_mismatch == 0:
        print('PASS: C++ 与 Python 数值等价（2^18 比对口径）')
        return 0
    print('FAIL: 超出容差或缺轨迹（%d 处不一致）' % n_mismatch)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
