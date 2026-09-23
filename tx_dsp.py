import ast

import numpy as np
from scipy import signal

# 数字域 PAM4 电平：满量程 ±1（外圈电平 = 峰值 = 1）。
# 符号索引 [0,1,2,3] <-> 电平 [-1, -1/3, +1/3, +1]，标准 Gray 顺序（见 metrics.calculate_ber）。
PAM4_LEVELS = np.array([-1.0, -1.0 / 3.0, 1.0 / 3.0, 1.0])


def pam4_map(symbols):
    """符号索引 [0,1,2,3] -> 归一化 PAM4 电平（峰值 ±1，满量程 ±1）。"""
    return (np.asarray(symbols) * (2.0 / 3.0)) - 1.0


def pam4_symbols(levels):
    """归一化 PAM4 电平 -> 最近符号索引 [0,1,2,3]。"""
    levels = np.asarray(levels)
    return np.argmin(np.abs(levels[..., None] - PAM4_LEVELS[None, ...]), axis=-1)


def tx_ffe(x, taps, sps):
    """ T-spaced Tx FFE applied to DSP signal (sps=2) """
    w = np.zeros(len(taps) * sps)
    w[::sps] = taps
    w = w / np.sum(np.abs(w))
    y = np.convolve(x, w, mode='same')
    return y


def tx_dsp_chain(tx_pam4, sps_dsp, baud_rate, config_tx):
    """ Complete Tx DSP chain running at sps_dsp """
    # Upsample symbols to DSP rate (insert zeros)
    tx_up = np.zeros(len(tx_pam4) * sps_dsp)
    tx_up[::sps_dsp] = tx_pam4

    # Pulse shape at DSP (e.g. NRZ rect filter)
    pulse = np.ones(sps_dsp)
    tx_shaped = np.convolve(tx_up, pulse, mode='full')[:len(tx_up)]

    # LPO Host ASIC Tx typically only has FFE, not CTLE
    tx_eq = tx_shaped

    # FFE
    custom_taps = config_tx.get('custom_taps')
    if custom_taps is not None and str(custom_taps).lower() not in ['none', 'nan']:
        if isinstance(custom_taps, str):
            tx_taps = np.array(ast.literal_eval(custom_taps))
        else:
            tx_taps = np.array(custom_taps)
    else:
        tx_taps = np.zeros(int(config_tx['ffe_taps']))
        ffe_pre = int(config_tx.get('ffe_pre', max(0, int(config_tx['ffe_taps']) // 2)))
        tx_taps[ffe_pre] = 1.0  # Pass-through for now

    tx_out = tx_ffe(tx_eq, tx_taps, sps_dsp)

    return tx_out
