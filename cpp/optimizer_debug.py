# optimizer_debug.py — Stage-2 在线调优参考轨迹（Python 侧，供 C++ 逐位比对）。
#
# 口径与 test_generalization.py 完全一致：8 维搜索向量
#   x = [5 个 Tx FFE 抽头, gDC, gDC2, u_gain]（N_DIM=8 / N_SHAPE=7，抽头全自由无边界）。
# 形状维梯度三档由 --grad-mode {full,rotate,secant} 选择；direct 参照用 --method direct。
# 在线只用 Model A（Model B 已不在线使用），真实 BER_MLSE 只记账、不回传决策。
# 只打印逐步 trace（落点 + 记账），与 cpp/tests/test_optimizer.cpp 对照做逐位比对。
#
# 用法（与 scratch/current_spec.md §5 同口径）：
#   python cpp/optimizer_debug.py --env Base_IL10x10 --num-symbols 262144 --n-steps 15 \
#       --method proxy --grad-mode full --seed-config result/seed_config_bad_1e4.json
#   python cpp/optimizer_debug.py --method direct   # direct 忽略 --grad-mode
import os
import sys
import argparse

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('MKL_NUM_THREADS', '1')

import ddps_optimizer as D                      # noqa: E402
from utils_config import load_config            # noqa: E402
from ddps_cases import apply_env_to_config      # noqa: E402
from train_surrogates import load_models        # noqa: E402


def main():
    ap = argparse.ArgumentParser(
        description='Stage-2 在线调优参考轨迹（Python 侧，与 cpp/build/run_ddps 同口径）')
    ap.add_argument('--env', default='Base_IL10x10', help='环境名（ENV_CASES）')
    ap.add_argument('--model-dir', default='models/ddps', help='冻结模型目录')
    ap.add_argument('--num-symbols', type=int, default=262144,
                    help='每用例符号数；比对口径固定 2^18 小点数低 SNR（AGENTS.md 开发方式）')
    ap.add_argument('--tx-noise-snr-db', type=float, default=0.0)
    ap.add_argument('--sim-seeds', type=str, default='42', help='逗号分隔的仿真种子')
    ap.add_argument('--n-steps', type=int, default=15, help='固定步数（代理档不早停）')
    ap.add_argument('--method', type=str, default='proxy', choices=['proxy', 'direct'],
                    help='proxy = Model A 探针代理在线调优；direct = 端到端真实 BER 直梯（回传参照）')
    ap.add_argument('--grad-mode', type=str, default='full', choices=['full', 'rotate', 'secant'],
                    help='proxy 的形状维梯度刷新方式（direct 忽略该参数）')
    ap.add_argument('--rotate-k', type=int, default=D.ROTATE_K,
                    help='rotate 模式每步刷新的形状维个数')
    ap.add_argument('--seed-config', type=str, default=None,
                    help='次优起点 seed_config JSON（覆盖 taps/gDC/gDC2/gain）')
    a = ap.parse_args()

    if a.seed_config:
        D.apply_seed_config(a.seed_config)
    D.set_sim_seeds(tuple(int(s) for s in a.sim_seeds.split(',') if s.strip()))

    config = load_config('config.xlsx')
    config = apply_env_to_config(config, a.env)
    config['system']['num_symbols'] = int(a.num_symbols)
    config['system']['tx_noise_snr_db'] = float(a.tx_noise_snr_db)

    # Model B 不在线使用：load_models 返回 (A, B)，这里只取 Model A。
    model_a = load_models(a.model_dir)[0]

    x0 = np.concatenate([D.SEED_TAPS.copy(),
                         [D.SEED_GDC, D.SEED_GDC2, D.u_from_gain(D.SEED_GAIN)]])
    tag = f'{a.method}/{a.grad_mode}' if a.method == 'direct' else f'proxy/{a.grad_mode}'
    print('=== Stage-2 %s | env=%s | num_symbols=%d | snr_db=%g | n_steps=%d | seeds=%s ==='
          % (tag, a.env, a.num_symbols, a.tx_noise_snr_db, a.n_steps, D.SIM_SEEDS))
    print('  x0=[' + ', '.join('%.12e' % v for v in x0) + ']')

    if a.method == 'direct':
        trace = D._stage2_descent_direct(config, x0, a.n_steps, D.GD_LR,
                                         grad_mode=a.grad_mode, rotate_k=a.rotate_k)
    else:
        trace = D._stage2_descent_proxy(config, model_a, x0, a.n_steps, D.GD_LR,
                                        grad_mode=a.grad_mode, rotate_k=a.rotate_k)

    print('=== TRACE ===')
    for rec in trace:
        print('step=%d' % rec['step'])
        print('  x=        [' + ', '.join('%.12e' % v for v in np.asarray(rec['x']).ravel()) + ']')
        print('  gdc=%.12e gdc2=%.12e gain=%.12e u_gain=%.12e'
              % (rec['gdc'], rec['gdc2'], rec['gain'], rec['u_gain']))
        print('  drive_rms=%.12e pred_a=%.12e' % (rec['drive_rms'], rec['pred_a']))
        print('  real_logber=%.12e real_mlse=%.12e' % (rec['real_logber'], rec['real_mlse']))
        print('  n_probe_states=%d refreshed=[%s] grad_norm=%.12e'
              % (int(rec.get('n_probe_states', 0)),
                 ','.join(str(i) for i in rec.get('refreshed', [])),
                 float(rec.get('grad_norm', float('nan')))))
        print('  stop_reason=%r' % rec['stop_reason'])


if __name__ == '__main__':
    main()
