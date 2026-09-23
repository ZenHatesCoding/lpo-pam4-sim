# -*- coding: utf-8 -*-
"""tools/run_parallel_envs.py — 多进程并行跑 test_generalization 的 15 个环境。

问题：`test_generalization.py` 的 `run_generalization()` 是 15 环境串行循环，
每个环境里的 LMS FFE + MLSE Viterbi 又是纯 Python 单线程逐样本循环（GIL 绑定），
所以 15 环境串行会把 A+B 全程推到 ~7.5h。CPU 是 12 物理核 / 20 逻辑线程，
进程间天然并行。

方案：用子进程并发（不用 in-process multiprocessing.Pool，避免 Windows spawn 的
pickle 问题），每个环境用 `--only-envs <env>` 让 test_generalization 只跑单一用例、
写到独立分片目录；每个子进程设 OMP_NUM_THREADS=1 防止 BLAS 超订阅；
全部完成后复用 `merge_test_parts.merge()` 按 ENV_CASES 顺序合并成一个结果目录。

用法（等价于「串行跑 15 环境」，只是 14 并发，从 ~7.5h 降到 ~40-60min）：
    python tools/run_parallel_envs.py --model-dir models/ddps \
        --out-dir result/ddps_aonly --a-only --n-steps 15 \
        --num-symbols 2097152 --sim-seeds 42,43,44 --jobs 14
"""
import argparse
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ddps_cases import ENV_CASES  # noqa: E402
import merge_test_parts  # noqa: E402

TEST_SCRIPT = os.path.join(ROOT, 'test_generalization.py')

# 与 dataset_generator / tools 一致的 BLAS 线程压制（防止每个进程抢满线程导致超订阅），
# 同时让子进程 stdout 不带块缓冲，后台运行时也能实时看到每个用例的进度。
_OMP_ENV = {
    'OMP_NUM_THREADS': '1',
    'OPENBLAS_NUM_THREADS': '1',
    'MKL_NUM_THREADS': '1',
    'NUMEXPR_NUM_THREADS': '1',
    'PYTHONUNBUFFERED': '1',
}


def _run_one(env, args, parts_dir, model_dir):
    part_dir = os.path.join(parts_dir, env)
    os.makedirs(part_dir, exist_ok=True)
    cmd = [
        sys.executable, TEST_SCRIPT,
        '--model-dir', model_dir,
        '--out-dir', part_dir,
        '--only-envs', env,
        '--n-steps', str(args.n_steps),
        '--num-symbols', str(args.num_symbols),
        '--sim-seeds', args.sim_seeds,
    ]
    if args.a_only:
        cmd += ['--a-only']
    if args.per_case_rms_path:
        cmd += ['--per-case-rms-path', args.per_case_rms_path]
    if args.seed_config:
        cmd += ['--seed-config', args.seed_config]

    env_vars = dict(os.environ)
    env_vars.update(_OMP_ENV)

    t0 = time.time()
    proc = subprocess.run(cmd, env=env_vars, cwd=ROOT)
    return env, proc.returncode, time.time() - t0


def main():
    ap = argparse.ArgumentParser(
        description='多进程并行跑 test_generalization 的 15 环境并合并结果')
    ap.add_argument('--model-dir', default='models/ddps')
    ap.add_argument('--out-dir', default='result/ddps_main')
    ap.add_argument('--n-steps', type=int, default=15)
    ap.add_argument('--num-symbols', type=int, default=2097152)
    ap.add_argument('--sim-seeds', type=str, default='42,43,44')
    ap.add_argument('--only-envs', type=str, default=None,
                    help='只跑指定环境（逗号分隔）；缺省跑全部 15 环境')
    ap.add_argument('--a-only', action='store_true',
                    help='A-only 对比实验：只用 Model A 梯度，不查 Model B，不走安全拦截')
    ap.add_argument('--per-case-rms-path', type=str, default=None)
    ap.add_argument('--seed-config', type=str, default=None)
    ap.add_argument('--jobs', type=int, default=None,
                    help='并发进程数；缺省 = min(14, 环境数)')
    args = ap.parse_args()

    model_dir = os.path.abspath(args.model_dir)
    out_dir = os.path.abspath(args.out_dir)
    if args.per_case_rms_path:
        args.per_case_rms_path = os.path.abspath(args.per_case_rms_path)
    if args.seed_config:
        args.seed_config = os.path.abspath(args.seed_config)

    envs = [e['name'] for e in ENV_CASES]
    if args.only_envs:
        keep = {s.strip() for s in args.only_envs.split(',') if s.strip()}
        envs = [e for e in envs if e in keep]
    if not envs:
        ap.error('--only-envs 未匹配到任何环境')

    jobs = args.jobs or min(14, len(envs))

    parts_dir = os.path.join(out_dir, '_parts')
    os.makedirs(parts_dir, exist_ok=True)
    tag = 'aonly' if args.a_only else 'main'
    print(f'[parallel {tag}] {len(envs)} envs x {jobs} procs -> {out_dir}')

    done = {}
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futs = {pool.submit(_run_one, env, args, parts_dir, model_dir): env
                for env in envs}
        for fut in as_completed(futs):
            env, rc, dt = fut.result()
            done[env] = (rc, dt)
            mark = 'OK' if rc == 0 else f'FAIL(rc={rc})'
            print(f'[parallel {tag}] {env}: {mark} {dt/60:.1f} min')

    failures = [e for e, (rc, _) in done.items() if rc != 0]
    if failures:
        print(f'[parallel {tag}] {len(failures)} failed: {failures}')
        print(f'[parallel {tag}] 分片保留在 {parts_dir}，修正后可用 merge_test_parts 手动合并')
        return 2

    part_dirs = [os.path.join(parts_dir, e) for e in envs]
    merge_test_parts.merge(out_dir, part_dirs)
    print(f'[parallel {tag}] done -> {out_dir}')
    return 0


if __name__ == '__main__':
    sys.exit(main())