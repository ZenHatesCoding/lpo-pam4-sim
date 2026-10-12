#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""run_all_cases.py — 15 环境 C++ 全量在线调优（单种子 42、2^22 符号、无人工噪声、次优起点）。

全量规模仿真（高 SNR 大点数）的唯一入口（AGENTS.md「开发方式」）：Python 与 C++ 的
比对只在 2^18 小点数低 SNR 下做，通过比对后的全量规模仿真一律走本脚本调度的
run_ddps（不允许用 Python 跑高 SNR 大点数）。

每个环境：apply_env_to_config -> dump per-env config.txt -> run_ddps -> case_summary.json + trace/probes CSV。
聚合输出到 result/<out-dir>/（case_summary.csv/json + trace/probes + run_config.json + _parts/<env>/）。
并行度 = 逻辑核数（每个 run_ddps 单线程）。

后端（--backend）：
  win — 直接调 cpp/build/run_ddps.exe（Windows MinGW 产物）。
  wsl — 经 wsl.exe 调 WSL 内 g++ 编译的 cpp/build/run_ddps（Linux ELF）。
        2026-10-12 起本机 Smart App Control 强制模式拦截本地无签名 exe（含旧
        run_ddps.exe 与 MinGW cc1plus 依赖的 libisl-23.dll），Windows 侧无法编译
        或运行；WSL 内 Linux 进程不受 Windows 代码完整性策略管辖。数值等价性
        仍按 2^18 比对口径验证（cpp/compare_traces.py），通过后才能跑全量。
"""
import os
import sys
import json
import time
import shutil
import argparse
import subprocess
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('MKL_NUM_THREADS', '1')

import numpy as np
from utils_config import load_config
from ddps_cases import ENV_CASES, apply_env_to_config

EXE = r"cpp\build\run_ddps.exe"
EXE_LINUX = "cpp/build/run_ddps"   # WSL g++ 产物（Linux ELF）
WSL_DISTRO = "Ubuntu"
BACKEND = "win"
CFG_DIR = r"cpp\build\cfg"
OUT_DIR = "result/ddps_cpp_main"
METHOD = "chain"
SEED_CONFIG = "result/seed_config_bad_1e4.json"
NUM_SYM = 4194304
SEED = 42
N_STEPS = 15
MODEL_DIR = "models/ddps"


def _fmt(v):
    if v is None:
        return None
    if isinstance(v, (bool, np.bool_)):
        return 'true' if v else 'false'
    if isinstance(v, (int, np.integer)):
        return repr(int(v))
    if isinstance(v, (float, np.floating)):
        return repr(float(v))
    return str(v)


def dump_config(env, path, num_sym):
    cfg = load_config('config.xlsx')
    cfg = apply_env_to_config(cfg, env)
    cfg['system']['num_symbols'] = int(num_sym)
    cfg['system']['tx_noise_snr_db'] = 0.0
    cfg['system']['seed'] = SEED
    cfg['channel']['seed'] = SEED + 7919
    with open(path, 'w', encoding='utf-8') as f:
        f.write('# auto-generated config (run_all_cases.py) env=%s\n' % env['name'])
        for sec in ['system', 'tx', 'channel', 'rx']:
            for k, v in cfg.get(sec, {}).items():
                s = _fmt(v)
                if s is None:
                    continue
                f.write('%s.%s = %s\n' % (sec, k, s))


def _safe(name):
    return name.replace(' ', '_').replace('(', '').replace(')', '')


def run_one(args):
    env, num_sym, n_steps, out_root, method, backend, distro, root_linux = args
    name = env['name']
    safe = _safe(name)
    out_dir = os.path.join(out_root, '_parts', safe)
    os.makedirs(out_dir, exist_ok=True)
    cfg_path = os.path.join(CFG_DIR, 'cfg_%s.txt' % safe)
    out_json = os.path.join(out_dir, 'case_summary.json')
    log = os.path.join(out_dir, 'run.log')
    dump_config(env, cfg_path, num_sym)
    if backend == 'wsl':
        # WSL：Linux 进程不受 Windows 代码完整性策略管辖；所有路径转 posix 相对形式，
        # 由 --cd 锚定仓库根。产物/日志仍落 Windows 文件树（/mnt/c），git 照常跟踪。
        cmd = ['wsl', '-d', distro, '--cd', root_linux, './' + EXE_LINUX,
               _posix(cfg_path), '--num-symbols', str(num_sym), '--tx-noise-snr', '0',
               '--seed', str(SEED), '--n-steps', str(n_steps),
               '--seed-config', _posix(SEED_CONFIG), '--env-name', name,
               '--model-dir', _posix(MODEL_DIR), '--method', method, '--out', _posix(out_json)]
    else:
        cmd = [EXE, cfg_path, '--num-symbols', str(num_sym), '--tx-noise-snr', '0',
               '--seed', str(SEED), '--n-steps', str(n_steps),
               '--seed-config', SEED_CONFIG, '--env-name', name,
               '--model-dir', MODEL_DIR, '--method', method, '--out', out_json]
    t0 = time.time()
    with open(log, 'w', encoding='utf-8') as lf:
        rc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT).returncode
    wall = time.time() - t0
    if rc != 0 or not os.path.exists(out_json):
        return {'env': name, 'ok': False, 'rc': rc, 'wall_sec': wall}
    with open(out_json, encoding='utf-8') as f:
        core = json.load(f)
    full = dict(core)
    full['il_tx'] = env['il_tx']
    full['il_rx'] = env['il_rx']
    full['cd'] = env['cd']
    full['dgd'] = env['dgd']
    full['pol'] = env['pol']
    full['noise_stress'] = bool(env.get('stress'))
    full['n_steps_requested'] = n_steps
    full['freeze_extra'] = False
    full['cloud'] = None
    full['wall_sec'] = wall
    # 与 Python case_summary.json 同构（单记录 list）
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump([full], f, indent=2, ensure_ascii=False)
    full['ok'] = True
    return full


def _posix(p):
    return p.replace('\\', '/')


def _wsl_path(win_abs):
    """C:\\DSPPlayground\\... -> /mnt/c/DSPPlayground/...（仓库根锚定用）"""
    drive = win_abs[0].lower()
    return '/mnt/%s%s' % (drive, win_abs[2:].replace('\\', '/'))


def main():
    global OUT_DIR, METHOD
    ap = argparse.ArgumentParser()
    ap.add_argument('--jobs', type=int, default=15)
    ap.add_argument('--only-envs', type=str, default=None)
    ap.add_argument('--num-symbols', type=int, default=NUM_SYM)
    ap.add_argument('--n-steps', type=int, default=N_STEPS)
    ap.add_argument('--method', type=str, default='chain', choices=['chain', 'secant', 'direct'])
    ap.add_argument('--out-dir', type=str, default=OUT_DIR)
    ap.add_argument('--backend', type=str, default='win', choices=['win', 'wsl'],
                    help='win = 直接调 cpp/build/run_ddps.exe；wsl = WSL 内 g++ 编译的 '
                         'cpp/build/run_ddps（Smart App Control 强制模式下的可用路线）')
    ap.add_argument('--wsl-distro', type=str, default=WSL_DISTRO, help='WSL 发行版名（--backend wsl 时生效）')
    a = ap.parse_args()
    METHOD = a.method
    OUT_DIR = a.out_dir
    backend = a.backend
    distro = a.wsl_distro
    root_linux = _wsl_path(os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')))
    num_sym = a.num_symbols
    n_steps = a.n_steps
    cases = [e for e in ENV_CASES if (a.only_envs is None or e['name'] in a.only_envs.split(','))]
    os.makedirs(CFG_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    jobs = min(a.jobs, len(cases))
    print('[cpp] %d envs, %d parallel workers (num_symbols=%d n_steps=%d backend=%s)' % (
        len(cases), jobs, num_sym, n_steps, backend), flush=True)
    t0 = time.time()
    with Pool(jobs) as pool:
        results = pool.map(run_one, [(e, num_sym, n_steps, OUT_DIR, METHOD, backend, distro,
                                      root_linux) for e in cases])
    total_wall = time.time() - t0

    oks = [r for r in results if r.get('ok')]
    fails = [r for r in results if not r.get('ok')]
    for r in oks:
        r.pop('ok', None)
    print('[cpp] ok=%d fail=%d total_wall=%.1fs' % (len(oks), len(fails), total_wall), flush=True)
    for r in fails:
        print('[cpp] FAIL %s rc=%s' % (r['env'], r.get('rc')), flush=True)

    # 聚合：case_summary.csv/json（字段顺序对齐 Python）
    ordered = ['env', 'il_tx', 'il_rx', 'cd', 'dgd', 'pol', 'noise_stress',
               'seed_lb', 'seed_ber', 'pa_seed', 'pb_seed', 'n_steps_requested',
               'n_steps_actual', 'freeze_extra', 'seed_gain', 'seed_gain_ratio', 'cloud',
               'best_lb', 'best_ber', 'best_step', 'final_lb', 'final_ber', 'max_lb',
               'delta_lb_seed_to_best', 'delta_lb_seed_to_final', 'best_taps',
               'best_gdc', 'best_gdc2', 'best_gain', 'best_gain_ratio', 'best_u_gain',
               'stop_reason', 'early_stop', 'elapsed_sec', 'wall_sec']
    rows = []
    for r in oks:
        rows.append({k: r.get(k) for k in ordered})
    with open(os.path.join(OUT_DIR, 'case_summary.json'), 'w', encoding='utf-8') as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)

    import csv
    with open(os.path.join(OUT_DIR, 'case_summary.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=ordered)
        w.writeheader()
        for r in rows:
            w.writerow({k: (json.dumps(v) if isinstance(v, (list, dict)) else v) for k, v in r.items()})

    # 归集 trace/probes CSV（C++ 已落每 env 到 _parts/<safe>/，复制到顶层供 report_ddps 出图）
    for e in cases:
        name = e['name']
        src_dir = os.path.join(OUT_DIR, '_parts', _safe(name))
        for fn in ('trace_%s.csv' % name, 'probes_%s.csv' % name):
            src = os.path.join(src_dir, fn)
            if os.path.exists(src):
                shutil.copy(src, os.path.join(OUT_DIR, fn))

    run_cfg = {
        'backend': 'cpp' if backend == 'win' else 'cpp-wsl',
        'exe': EXE if backend == 'win' else 'wsl -d %s %s' % (distro, EXE_LINUX),
        'model_dir': MODEL_DIR, 'n_steps': n_steps,
        'num_symbols': num_sym, 'sim_seeds': [SEED], 'seed_config': SEED_CONFIG,
        'tx_noise_snr_db': 0.0, 'envs': [e['name'] for e in cases],
        'jobs': jobs, 'total_wall_sec': total_wall, 'method': METHOD,
    }
    with open(os.path.join(OUT_DIR, 'run_config.json'), 'w', encoding='utf-8') as f:
        json.dump(run_cfg, f, indent=2, ensure_ascii=False)

    print('[cpp] done -> %s/case_summary.csv' % OUT_DIR, flush=True)


if __name__ == '__main__':
    main()
