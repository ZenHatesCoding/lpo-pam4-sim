# -*- coding: utf-8 -*-
"""构造「更差的起点」：给候选 seed 配置，用 C++ 在 2^18 下实测其真实 BER。

每个候选只跑 1 步（--n-steps 1），读 case_summary 里的 seed_ber —— 这是链路真实评估出来的，
不是模型预测。用于把起点校准到指定量级（约 1e-3）。

用法：
  python scratch/probe_seed_ber.py                 # 评估 seeds/ 下所有候选
  python scratch/probe_seed_ber.py --pattern s2    # 只评文件名含 s2 的
"""
import argparse
import glob
import json
import os
import subprocess
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = 'cpp/build/run_ddps'
CASES = ['Base_IL10x10', 'IL14x14', 'IL20x20']


def wsl_path(p):
    p = os.path.abspath(p)
    return '/mnt/%s%s' % (p[0].lower(), p[2:].replace('\\', '/'))


def probe(seed_path, env):
    out = tempfile.mktemp(suffix='.json', dir=os.path.join(ROOT, 'scratch'))
    cfg = os.path.join(ROOT, 'scratch', 'seedcfg_probe.txt')
    # 用 run_all_cases 的 dump_config 保证与正式跑批同一配置口径
    import sys
    sys.path.insert(0, os.path.join(ROOT, 'cpp'))
    import importlib
    rac = importlib.import_module('run_all_cases')
    env_case = [e for e in rac.ENV_CASES if e['name'] == env][0]
    rac.dump_config(env_case, cfg, 262144)
    cmd = ['wsl', '-d', 'Ubuntu', '--cd', wsl_path(ROOT), './' + EXE,
           wsl_path(cfg), '--num-symbols', '262144', '--tx-noise-snr', '0', '--seed', '42',
           '--n-steps', '1', '--seed-config', wsl_path(seed_path), '--env-name', env,
           '--model-dir', 'models/ddps', '--method', 'proxy', '--grad-mode', 'secant',
           '--out', wsl_path(out)]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    try:
        with open(out, encoding='utf-8') as f:
            d = json.load(f)
        return d.get('seed_ber'), d.get('seed_lb')
    except Exception:
        return None, None
    finally:
        if os.path.exists(out):
            os.remove(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pattern', default='')
    ap.add_argument('--cases', default=','.join(CASES))
    a = ap.parse_args()
    cases = a.cases.split(',')
    files = sorted(f for f in glob.glob(os.path.join(ROOT, 'seeds', '*.json'))
                   if a.pattern in os.path.basename(f))
    print('%-26s ' % 'seed' + ' '.join('%12s' % c for c in cases))
    for f in files:
        vals = []
        for c in cases:
            ber, _ = probe(f, c)
            vals.append('%.3e' % ber if ber else 'FAIL')
        print('%-26s ' % os.path.basename(f) + ' '.join('%12s' % v for v in vals), flush=True)


if __name__ == '__main__':
    main()
