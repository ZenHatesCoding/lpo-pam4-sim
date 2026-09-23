"""诊断 BER 测量是否受头部收敛过程污染。

复刻 main.run_sim 的 Rx DSP + MLSE 全链路，但额外返回每个符号的 FFE/MLSE 判决，
统计 train_len 之后的误差位置分布：头部（紧跟 train_len 之后） vs 尾部（稳态）。

用法：
    python tools/diagnose_ber_head.py --num-symbols 2097152 --seed 42 --bins 40
"""
import argparse
import os
import sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np
from utils_config import load_config
from tx_dsp import pam4_map, pam4_symbols, tx_dsp_chain
from channel_imdd import apply_channel
from rx_dsp import adaptive_ffe_dfe
from mlse_burg import burg_ar, viterbi_mlse_pam4
from metrics import calculate_ber
from scipy.signal import correlate


def run_and_profile(config, num_symbols, seed, custom_taps, gdc, gdc2, gain, bins=40):
    config = config.copy()
    config['system'] = dict(config['system'])
    config['system']['num_symbols'] = num_symbols
    config['system']['seed'] = seed
    config['channel'] = dict(config['channel'])
    config['channel']['seed'] = seed + 7919
    config['tx'] = dict(config['tx'])
    config['tx']['ctle_g_dc_db'] = gdc
    config['tx']['ctle_g_dc2_db'] = gdc2
    config['channel']['driver_gain'] = gain
    config['tx']['custom_taps'] = np.asarray(custom_taps, dtype=float)

    baud_rate = config['system']['baud_rate']
    sps_dsp = int(config['system']['sps_dsp'])
    sps_dac = int(config['system']['sps_dac'])
    sps_channel = int(config['system']['sps_channel'])
    sps_adc = int(config['system']['sps_adc'])

    rng = np.random.RandomState(seed)
    tx_symbols = rng.randint(0, 4, num_symbols)
    tx_pam4 = pam4_map(tx_symbols)

    tx_config = dict(config['tx'])
    tx_config['custom_taps'] = np.asarray(custom_taps, dtype=float)
    tx_out = tx_dsp_chain(tx_pam4, sps_dsp, baud_rate, tx_config)
    _, _, rx_adc = apply_channel(tx_out, config, baud_rate, sps_dac, sps_channel, sps_adc)

    # 采样相位
    rx_1sps_even = rx_adc[::sps_adc]
    corr_even = correlate(rx_1sps_even[:1000], tx_pam4[:1000])
    rx_1sps_odd = rx_adc[1::sps_adc]
    corr_odd = correlate(rx_1sps_odd[:1000], tx_pam4[:1000])
    if np.max(corr_even) >= np.max(corr_odd):
        sync_delay = int(np.argmax(corr_even) - (len(tx_pam4[:1000]) - 1))
        phase_offset = 0
    else:
        sync_delay = int(np.argmax(corr_odd) - (len(tx_pam4[:1000]) - 1))
        phase_offset = 1

    mlse_memory = int(config['rx']['mlse_memory'])
    dfe_taps = int(config['rx'].get('dfe_taps', 0))
    if mlse_memory > 0:
        dfe_taps = 0

    rx_eq, _, _, error_seq, ffe_decisions = adaptive_ffe_dfe(
        rx_adc[phase_offset:], tx_pam4,
        int(config['rx']['ffe_taps']), int(config['rx']['ffe_pre']), dfe_taps,
        config['rx']['lms_mu'], config['rx']['lms_mu'],
        int(config['rx']['train_len']), sync_delay=sync_delay)

    ffe_symbols = pam4_symbols(ffe_decisions)

    train_len = int(config['rx']['train_len'])
    err_ss = error_seq[train_len:]
    ar_order = mlse_memory
    if ar_order > 0:
        ar_coeffs, _ = burg_ar(err_ss, ar_order)
        pr_taps = np.concatenate(([1.0], ar_coeffs))
    else:
        pr_taps = np.array([1.0])
    rx_eq_whitened = np.convolve(rx_eq, pr_taps, mode='full')[:len(rx_eq)]
    rx_decisions = viterbi_mlse_pam4(rx_eq_whitened, pr_taps)
    rx_symbols = pam4_symbols(rx_decisions)

    # 稳态窗口 [train_len, N)
    tx_ss = tx_symbols[train_len:]
    ffe_ss = ffe_symbols[train_len:]
    mlse_ss = rx_symbols[train_len:]
    n_ss = len(tx_ss)

    ffe_err = (ffe_ss != tx_ss)
    mlse_err = (mlse_ss != tx_ss)

    # 分箱统计（等宽箱）
    bin_edges = np.linspace(0, n_ss, bins + 1).astype(int)
    ffe_bins = []
    mlse_bins = []
    for b in range(bins):
        ffe_bins.append(int(ffe_err[bin_edges[b]:bin_edges[b + 1]].sum()))
        mlse_bins.append(int(mlse_err[bin_edges[b]:bin_edges[b + 1]].sum()))

    return dict(
        n_ss=n_ss, train_len=train_len, seed=seed,
        ffe_total=int(ffe_err.sum()), mlse_total=int(mlse_err.sum()),
        ffe_bins=np.array(ffe_bins), mlse_bins=np.array(mlse_bins),
        ffe_err=ffe_err, mlse_err=mlse_err, tx_ss=tx_ss,
        sync_delay=sync_delay, phase_offset=phase_offset,
        len_rx_sps=int(len(rx_adc[phase_offset:])),
        rx_eq=rx_eq, ffe_decisions=ffe_decisions,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--num-symbols', type=int, default=2097152)
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--bins', type=int, default=40)
    ap.add_argument('--gdc', type=float, default=6.0)
    ap.add_argument('--gdc2', type=float, default=2.0)
    ap.add_argument('--gain', type=float, default=0.1381)
    ap.add_argument('--taps', type=str, default='-0.034,-0.2987,0.6091,0,0.0582')
    a = ap.parse_args()

    config = load_config('config.xlsx')
    taps = np.array([float(x) for x in a.taps.split(',')])

    print(f"[diag] num_symbols={a.num_symbols} seed={a.seed} gDC={a.gdc} gDC2={a.gdc2} gain={a.gain}")
    r = run_and_profile(config, a.num_symbols, a.seed, taps, a.gdc, a.gdc2, a.gain, a.bins)

    tl = r['train_len']
    n_ss = r['n_ss']
    print(f"[diag] train_len={tl} 稳态窗口 {tl}..{tl + n_ss}（{n_ss} 符号）")
    print(f"[diag] FFE 总错误={r['ffe_total']}  MLSE 总错误={r['mlse_total']}")
    print(f"[diag] 参考 BER: FFE={r['ffe_total'] / n_ss:.3e}  MLSE={r['mlse_total'] / n_ss:.3e}")

    b = a.bins
    print(f"\n[diag] 每箱错误数（{b} 等宽箱，箱宽 {n_ss // b} 符号）:")
    print("bin  FFE_err  MLSE_err")
    for i in range(b):
        print(f"{i:3d}  {r['ffe_bins'][i]:7d}  {r['mlse_bins'][i]:9d}")

    # 头部 vs 尾部：前 10% 箱 vs 后 90% 箱
    n_head = max(1, b // 10)
    head_ffe = int(r['ffe_bins'][:n_head].sum())
    head_mlse = int(r['mlse_bins'][:n_head].sum())
    tail_ffe = int(r['ffe_bins'][n_head:].sum())
    tail_mlse = int(r['mlse_bins'][n_head:].sum())
    head_sym = n_head * (n_ss // b)
    tail_sym = n_ss - head_sym
    print(f"\n[diag] 头部(前{n_head}箱, {head_sym}符号): FFE={head_ffe} MLSE={head_mlse} "
          f"-> FFE率={head_ffe / head_sym:.3e} MLSE率={head_mlse / head_sym:.3e}")
    print(f"[diag] 尾部(后{b - n_head}箱, {tail_sym}符号): FFE={tail_ffe} MLSE={tail_mlse} "
          f"-> FFE率={tail_ffe / tail_sym:.3e} MLSE率={tail_mlse / tail_sym:.3e}")
    if tail_ffe > 0:
        print(f"[diag] 头部/尾部 FFE 错误率比 = {head_ffe / head_sym / (tail_ffe / tail_sym):.2f}x")
    if tail_mlse > 0:
        print(f"[diag] 头部/尾部 MLSE 错误率比 = {head_mlse / head_sym / (tail_mlse / tail_sym):.2f}x")
    else:
        print("[diag] 尾部 MLSE 错误=0，稳态无错（BER 全在头部）")

    # 首个稳态符号附近的精细窗口
    w = 2000
    first_mlse = int(r['mlse_err'][:w].sum())
    last_mlse = int(r['mlse_err'][-w:].sum())
    print(f"\n[diag] 稳态最前 {w} 符号 MLSE 错误={first_mlse}；最后 {w} 符号 MLSE 错误={last_mlse}")

    # 尾缘截断分析
    sd = r['sync_delay']
    print(f"\n[diag] sync_delay={sd} phase_offset={r['phase_offset']} len(rx_sps)={r['len_rx_sps']}")
    # 定位 FFE 判决中"未被写入"的符号（= 初始值 0，非 PAM4 电平）
    from tx_dsp import PAM4_LEVELS
    fd = r['ffe_decisions']
    untouched = np.ones(fd.shape, dtype=bool)
    for lv in PAM4_LEVELS:
        untouched &= (fd != lv)
    ut_idx = np.where(untouched)[0]
    print(f"[diag] FFE 判决未写入(continue)符号数={len(ut_idx)}；位置范围 "
          f"[{ut_idx.min() if len(ut_idx) else -1}, {ut_idx.max() if len(ut_idx) else -1}]")
    if len(ut_idx) and len(ut_idx) < 20:
        print(f"[diag]   -> {ut_idx.tolist()}")
    # 错误位置
    me_idx = np.where(r['mlse_err'])[0]
    print(f"[diag] MLSE 错误位置: 全局符号 {tl + me_idx.min()}..{tl + me_idx.max()} "
          f"（{len(me_idx)} 个）" if len(me_idx) else "[diag] MLSE 无错误")


if __name__ == '__main__':
    main()
