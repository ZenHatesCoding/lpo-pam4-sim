import numpy as np
import os
from tx_dsp import tx_dsp_chain
from channel_imdd import apply_ctle, dac_zoh, lowpass_filter, apply_s4p_filter
try:
    import skrf as rf
except ImportError:
    rf = None

_s4p_cache = {}

# 符号格对齐基准缓存：按"物理信道环境"缓存，而不是进程级一次性粘滞锁。
# 背景：S4P 为匹配不同目标插损做频率缩放，脉冲响应的群时延会随 IL 明显漂移
# （实测 Base_IL10 峰值 idx=1247，而 IL_Worst_20dB 在 idx=238），若把首个探测
# 的对齐永久粘滞在进程里，跨环境复用时 FIR 会在错误的符号格上采样。
_ref_peak_by_env = {}


def _load_s4p_cached(path):
    """Cache the Touchstone Network so repeated extractions don't re-parse the file."""
    if path not in _s4p_cache:
        _s4p_cache[path] = rf.Network(path)
    return _s4p_cache[path]


def _env_signature(config):
    """唯一刻画"符号格对齐"所依赖的信道环境（与 FFE/CTLE 无关）。"""
    ch = config['channel']
    return (
        ch.get('use_s4p', False),
        ch.get('s4p_file', ''),
        round(float(ch.get('tx_pcb_loss_nyquist_db', -1.0)), 6),
        round(float(ch.get('driver_bw', ch.get('mzm_bw', 40e9))), 0),
        round(float(ch.get('mzm_bw', 40e9)), 0),
        round(float(ch.get('cd_ps_nm', 0.0)), 4),
        round(float(ch.get('dgd_ps', 0.0)), 4),
        round(float(ch.get('pol_angle_deg', 0.0)), 2),
    )


def _chain_impulse(config, custom_taps, pad_len=100):
    """把理想单位脉冲打过整条 Tx 模拟链（FFE→DAC→CTLE→PCB→Driver→MZM），
    返回 8sps 模拟波形。与 extract_tx_s21 的旧实现逐段等价。"""
    baud_rate = config['system']['baud_rate']
    sps_dsp = int(config['system']['sps_dsp'])
    sps_dac = int(config['system']['sps_dac'])
    sps_channel = int(config['system']['sps_channel'])

    tx_symbols = np.zeros(2 * pad_len + 1)
    tx_symbols[pad_len] = 1.0  # 单位脉冲

    tx_config = config['tx'].copy()
    tx_config['custom_taps'] = custom_taps
    tx_out = tx_dsp_chain(tx_symbols, sps_dsp, baud_rate, tx_config)

    x_analog = dac_zoh(tx_out, sps_dac, sps_channel)
    fs_analog = baud_rate * sps_channel

    if tx_config.get('use_ctle', False):
        f_b = baud_rate
        f_z = f_b / tx_config.get('ctle_fz_ratio', 2.5)
        f_p1 = f_b / tx_config.get('ctle_fp1_ratio', 2.5)
        f_p2 = f_b / tx_config.get('ctle_fp2_ratio', 1.0)
        f_lf = f_b / tx_config.get('ctle_flf_ratio', 40.0)
        g_dc_db = tx_config.get('ctle_g_dc_db', 0.0)
        g_dc2_db = tx_config.get('ctle_g_dc2_db', 0.0)
        x_analog = apply_ctle(x_analog, fs_analog, f_z, f_p1, f_p2, g_dc_db, g_dc2_db, f_lf)

    config_ch = config['channel']
    nyquist = baud_rate / 2
    loss_db = config_ch.get('tx_pcb_loss_nyquist_db', config_ch.get('pcb_loss_nyquist_db', 15.0))
    fc_pcb = nyquist / np.sqrt(10 ** (loss_db / 10) - 1)

    if config_ch.get('use_s4p', False) and rf is not None:
        x_s4p = apply_s4p_filter(x_analog, fs_analog, config_ch, 'tx_pcb_loss_nyquist_db', nyquist)
        if x_s4p is not None:
            x = x_s4p
        else:
            x = lowpass_filter(x_analog, fc_pcb, fs_analog, order=1)
    else:
        x = lowpass_filter(x_analog, fc_pcb, fs_analog, order=1)

    # Driver AGC and band-limit (matching channel_imdd.py exactly)
    sigma_s = np.sqrt(5) / 3
    current_rms = sigma_s * np.sqrt(np.sum(x ** 2) / sps_channel)
    driver_vpp = config_ch.get('driver_vpp', 0.617)
    target_rms = driver_vpp * 0.3726
    if current_rms > 1e-12:
        x = x * (target_rms / current_rms)
    x = lowpass_filter(x, config_ch.get('driver_bw', config_ch.get('mzm_bw', 40e9)),
                       fs_analog, order=4)
    # E-O conversion band-limit
    x = lowpass_filter(x, config_ch['mzm_bw'], fs_analog)
    return x, fs_analog, sps_channel


def _nominal_taps(config):
    n = int(config['tx'].get('ffe_taps', 9))
    taps = np.zeros(n)
    taps[int(config['tx'].get('ffe_pre', n // 2))] = 1.0
    return taps


def _peak_idx_for_env(config):
    """当前信道环境下的符号格基准（主游标位置）。结果按环境缓存。"""
    key = _env_signature(config)
    if key not in _ref_peak_by_env:
        x, _, _ = _chain_impulse(config, _nominal_taps(config))
        _ref_peak_by_env[key] = int(np.argmax(np.abs(x)))
    return _ref_peak_by_env[key]


def reset_probe_cache():
    """清空对齐缓存（多进程/多环境调试时用）。"""
    _ref_peak_by_env.clear()
    _s4p_cache.clear()


def extract_tx_s21(config, custom_tx_taps=None, num_taps=7):
    """提取发端等效 T 间隔 FIR（Tx FFE -> DAC -> CTLE -> PCB -> MZM）。

    - 符号格基准按"物理信道环境"（IL/CD/DGD/S4P 文件等）缓存，保证同一环境下
      FIR 是 FFE/CTLE 的光滑函数、跨环境复用时对齐正确。
    - config: 系统配置字典
    - custom_tx_taps: 9-tap FFE 权重（None 时用配置/透传抽头）
    - num_taps: 提取中心抽头数（默认 7）
    """
    sps_channel = int(config['system']['sps_channel'])
    pre_cursors = 2
    post_cursors = num_taps - pre_cursors - 1

    # 1. 取当前配置的 FFE 权重
    if custom_tx_taps is not None:
        custom_taps = np.asarray(custom_tx_taps, dtype=float)
    else:
        tx_config = config['tx']
        if 'custom_taps' in tx_config and str(tx_config['custom_taps']).lower() not in ('none', 'nan'):
            val = tx_config['custom_taps']
            if isinstance(val, str) and val.strip().startswith('['):
                import ast
                custom_taps = np.array(ast.literal_eval(val), dtype=float)
            else:
                custom_taps = np.asarray(val, dtype=float)
        else:
            custom_taps = _nominal_taps(config)

    # 2. 打理想单位脉冲过整条 Tx 链
    x, _, _ = _chain_impulse(config, custom_taps)

    # 3. 符号格基准 = 当前环境下透传冲激的峰值位置（按环境缓存）
    peak_idx = _peak_idx_for_env(config)

    # 4. 以 sps_channel 间隔取 num_taps 个等效 T 间隔抽头
    fir_taps = np.zeros(num_taps)
    for i in range(num_taps):
        tap_offset = i - pre_cursors
        idx = peak_idx + tap_offset * sps_channel
        if 0 <= idx < len(x):
            fir_taps[i] = x[idx]
    return fir_taps


if __name__ == "__main__":
    from utils_config import load_config
    import create_config
    create_config.generate_config()
    config = load_config('config.xlsx')

    taps = extract_tx_s21(config)
    print("Extracted 7-tap Tx FIR:", np.round(taps, 4))
