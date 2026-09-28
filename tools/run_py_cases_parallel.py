#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""tools/run_py_cases_parallel.py — Python 15 环境全量在线调优（单种子 42、2^18、无噪声、次优起点）。

每个环境跑一个 test_generalization.py --only-envs 分片（_parts/<env>/），全部结束后用
merge_test_parts.py 合并到 result/ddps_main/。
"""
import os
import sys
import time
import argparse
import subprocess
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('MKL_NUM_THREADS', '1')

from ddps_cases import ENV_CASES

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARTS = os.path.join('result', 'ddps_main', '_parts')
OUT_DIR = 'result/ddps_main'
N_STEPS = 15
NUM_SYM = 262144
SEED = '42'
SEED_CONFIG = 'result/seed_config_bad_1e4.json'
MODEL_DIR = 'models/ddps'
A_ONLY = False


def _safe(name):
    return name.replace(' ', '_').replace('(', '').replace(')', '')


def run_one(args):
    env, a_only, parts = args
    name = env['name']
    safe = _safe(name)
    part = os.path.join(parts, safe)
    os.makedirs(part, exist_ok=True)
    log = os.path.join(part, 'run.log')
    cmd = [sys.executable, os.path.join(ROOT, 'test_generalization.py'),
           '--model-dir', MODEL_DIR, '--out-dir', part,
           '--n-steps', str(N_STEPS), '--num-symbols', str(NUM_SYM),
           '--sim-seeds', SEED, '--seed-config', SEED_CONFIG,
           '--only-envs', name]
    if a_only:
        cmd.append('--a-only')
    t0 = time.time()
    with open(log, 'w', encoding='utf-8') as lf:
        rc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT).returncode
    wall = time.time() - t0
    ok = rc == 0 and os.path.exists(os.path.join(part, 'case_summary.csv'))
    print('[py] %-24s rc=%d ok=%s wall=%.1fs' % (name, rc, ok, wall), flush=True)
    return {'env': name, 'ok': ok, 'rc': rc, 'wall_sec': wall}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--jobs', type=int, default=15)
    ap.add_argument('--only-envs', type=str, default=None)
    ap.add_argument('--a-only', action='store_true')
    ap.add_argument('--out-dir', type=str, default='result/ddps_main')
    a = ap.parse_args()
    OUT_DIR = a.out_dir
    PARTS = os.path.join(OUT_DIR, '_parts')
    cases = [e for e in ENV_CASES if (a.only_envs is None or e['name'] in a.only_envs.split(','))]
    os.makedirs(PARTS, exist_ok=True)

    jobs = min(a.jobs, len(cases))
    print('[py] %d envs, %d parallel workers (a_only=%s)' % (len(cases), jobs, a.a_only), flush=True)
    t0 = time.time()
    with Pool(jobs) as pool:
        results = pool.map(run_one, [(e, a.a_only, PARTS) for e in cases])
    total_wall = time.time() - t0
    print('[py] total_wall=%.1fs, ok=%d fail=%d' % (
        total_wall, sum(1 for r in results if r['ok']), sum(1 for r in results if not r['ok'])), flush=True)

    parts = [os.path.join(PARTS, _safe(e['name'])) for e in cases
             if os.path.exists(os.path.join(PARTS, _safe(e['name']), 'case_summary.csv'))]
    if not parts:
        print('[py] no parts produced; skip merge', flush=True)
        return
    from merge_test_parts import merge
    merge(OUT_DIR, parts)
    print('[py] done -> %s/case_summary.csv' % OUT_DIR, flush=True)


if __name__ == '__main__':
    main()