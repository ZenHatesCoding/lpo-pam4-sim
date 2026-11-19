# -*- coding: utf-8 -*-
"""起点鲁棒性对照实验：同一套算法，换多个「差起点」，六格全跑，看结论是否随起点变化。

每个起点 × 六格（3 种形状维取法 × 2 种梯度来源）各产出一个结果目录：
    result/seed_study/<起点>/ddps_cpp_<格>/
放在 result/seed_study/ 下（不是在 result/ 顶层），避免被 verify_ddps 的
`result/ddps_cpp_*` 自动发现当成现役格。

用法：
    python tools/run_seed_study.py --jobs 6 --num-symbols 2097152
    python tools/run_seed_study.py --seeds s1_gain,s2_ctle --only-cell full
"""
import argparse
import os
import json
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CELLS = [
    ('proxy', 'full'), ('proxy', 'rotate'), ('proxy', 'secant'),
    ('direct', 'full'), ('direct', 'rotate'), ('direct', 'secant'),
]


def cell_dirname(method, mode):
    return 'ddps_cpp_%s' % (mode if method == 'proxy' else 'direct_' + mode)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--jobs', type=int, default=6)
    ap.add_argument('--num-symbols', type=int, default=2097152)
    ap.add_argument('--n-steps', type=int, default=15)
    ap.add_argument('--only-cell', default=None, help='只跑某一格（full/rotate/secant/direct_full/...）')
    ap.add_argument('--seeds', default=None, help='起点名逗号分隔，默认 seeds/ 下所有 seed_*.json')
    ap.add_argument('--out-root', default=os.path.join('result', 'seed_study'),
                    help='结果根目录；小点数版式探针请指到 scratch/ 下，绝不与正式跑批共用')
    a = ap.parse_args()

    seed_files = []
    if a.seeds:
        for s in a.seeds.split(','):
            p = os.path.join(ROOT, 'seeds', 'seed_%s.json' % s)
            if not os.path.exists(p):
                sys.exit('缺 seed 文件: %s' % p)
            seed_files.append((s, p))
    else:
        sdir = os.path.join(ROOT, 'seeds')
        for f in sorted(os.listdir(sdir)):
            if f.startswith('seed_') and f.endswith('.json'):
                seed_files.append((f[5:-5], os.path.join(sdir, f)))

    runs = []
    for sname, spath in seed_files:
        for method, mode in CELLS:
            name = cell_dirname(method, mode)
            if a.only_cell and a.only_cell not in (name.replace('ddps_cpp_', ''), name):
                continue
            out = os.path.join(a.out_root, sname, name)
            runs.append((sname, method, mode, spath, out))

    print('[study] %d 个起点 × %d 格 = %d 次跑批，num_symbols=%d jobs=%d'
          % (len(seed_files), len(CELLS), len(runs), a.num_symbols, a.jobs), flush=True)
    t_all = time.time()
    fails = []
    for i, (sname, method, mode, spath, out) in enumerate(runs, 1):
        t0 = time.time()
        _rc = os.path.join(ROOT, out, 'run_config.json')
        if os.path.exists(_rc):
            try:
                with open(_rc, encoding='utf-8') as f:
                    _old = int(json.load(f).get('num_symbols') or 0)
            except Exception:
                _old = -1
            if _old and _old != a.num_symbols:
                sys.exit('拒绝覆盖：%s 已有 num_symbols=%d 的结果，本次是 %d。'
                         '换 --out-root，或先用 --only-cell 明确重跑。' % (out, _old, a.num_symbols))
        cmd = [sys.executable, os.path.join('cpp', 'run_all_cases.py'),
               '--backend', 'wsl', '--num-symbols', str(a.num_symbols),
               '--n-steps', str(a.n_steps), '--jobs', str(a.jobs),
               '--method', method, '--grad-mode', mode,
               '--seed-config', spath, '--out-dir', out]
        print('[study] %d/%d %s %s/%s -> %s' % (i, len(runs), sname, method, mode, out), flush=True)
        rc = subprocess.run(cmd, cwd=ROOT).returncode
        wall = time.time() - t0
        print('[study] %d/%d rc=%d wall=%.0fs' % (i, len(runs), rc, wall), flush=True)
        if rc != 0:
            fails.append((sname, method, mode))
    print('[study] ALL DONE wall=%.0fs fails=%s' % (time.time() - t_all, fails or 'none'), flush=True)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
