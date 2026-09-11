import numpy as np
import os
from tx_dsp import pam4_map, tx_dsp_chain
from channel_imdd import (apply_ctle, dac_zoh, lowpass_filter, apply_s4p_filter,
                          tx_frontend_lti, DRIVER_GAIN_NOMINAL, DRIVE_RMS_NOMINAL)
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
    """把理想单位脉冲打过整条 Tx 模拟链，返回 8sps 波形（MZM 输入端，单位 V）。

    链路顺序与 channel_imdd.apply_channel **完全一致**（共用 tx_frontend_lti）：
        FFE -> DAC(ZOH) -> Tx 电插损 -> VGA -> Tx CTLE -> Driver 真增益 -> Driver 带限 -> MZM 带限
    """
    baud_rate = config['system']['baud_rate']
    sps_dsp = int(config['system']['sps_dsp'])
    sps_dac = int(config['system']['sps_dac'])
    sps_channel = int(config['system']['sps_channel'])

    tx_symbols = np.zeros(2 * pad_len + 1)
    tx_symbols[pad_len] = 1.0  # 单位脉冲（1 sps）

    tx_config = config['tx'].copy()
    tx_config['custom_taps'] = custom_taps
    tx_out = tx_dsp_chain(tx_symbols, sps_dsp, baud_rate, tx_config)

    x = dac_zoh(tx_out, sps_dac, sps_channel)
    fs_analog = baud_rate * sps_channel
    nyquist = baud_rate / 2

    x = tx_frontend_lti(x, config, baud_rate, fs_analog, nyquist, rng=None)
    # E-O conversion band-limit
    x = lowpass_filter(x, config['channel']['mzm_bw'], fs_analog)
    return x, fs_analog, sps_channel


def _drive_rms(config, custom_taps, n_symbols=4096, seed=7):
    """该配置下 MZM 输入端的真实驱动 RMS（V）。

    用一段固定 PAM4 测试序列跑同一套模拟前端（不含 MZM 与后端），把 driver_gain 与
    CTLE 直流增益对"实际驱动幅度"的影响变成一个显式标量特征。

    为什么必须有它：driver_gain 在纯线性 Tx 链里只是一个标量乘子，而 7-tap FIR 形状
    对整体尺度是不变的 —— 若 Model A 只看 FIR 形状，它对 driver_gain 的梯度恒为 0，
    寻优将永远无法移动这一维。驱动幅度正是决定 MZM 非线性（以及 OMA/SNR）的物理量。
    """
    baud_rate = config['system']['baud_rate']
    sps_dsp = int(config['system']['sps_dsp'])
    sps_dac = int(config['system']['sps_dac'])
    sps_channel = int(config['system']['sps_channel'])

    rng = np.random.RandomState(seed)
    pam4 = pam4_map(rng.randint(0, 4, n_symbols))

    tx_config = config['tx'].copy()
    tx_config['custom_taps'] = custom_taps
    tx_out = tx_dsp_chain(pam4, sps_dsp, baud_rate, tx_config)

    x = dac_zoh(tx_out, sps_dac, sps_channel)
    fs_analog = baud_rate * sps_channel
    x = tx_frontend_lti(x, config, baud_rate, fs_analog, baud_rate / 2, rng=None)

    skip = 200 * sps_channel          # 跳过滤波器暂态
    seg = x[skip:] if len(x) > skip else x
    return float(np.std(seg))


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


def _resolve_taps(config, custom_tx_taps=None):
    """解析当前生效的 9-tap FFE 权重（显式传入优先，其次 config，最后名义抽头）。"""
    if custom_tx_taps is not None:
        return np.asarray(custom_tx_taps, dtype=float)
    tx_config = config['tx']
    if 'custom_taps' in tx_config and str(tx_config['custom_taps']).lower() not in ('none', 'nan'):
        val = tx_config['custom_taps']
        if isinstance(val, str) and val.strip().startswith('['):
            import ast
            return np.array(ast.literal_eval(val), dtype=float)
        return np.asarray(val, dtype=float)
    return _nominal_taps(config)


def extract_tx_s21(config, custom_tx_taps=None, num_taps=7):
    """提取发端等效 T 间隔 FIR（绝对标定，单位 V）。

    链序：Tx FFE -> DAC -> Tx 电插损 -> VGA -> Tx CTLE -> Driver 真增益 -> MZM。

    - 符号格基准按"物理信道环境"（IL/CD/DGD/S4P 文件等）缓存，保证同一环境下
      FIR 是 FFE/CTLE/Driver 增益的光滑函数、跨环境复用时对齐正确。
    - 注意：整条 Tx 链是线性时不变的，因此该 FIR 的**形状**对纯增益（driver_gain）
      不敏感；需要感知驱动幅度时请使用 extract_tx_features()。
    - config: 系统配置字典
    - custom_tx_taps: 9-tap FFE 权重（None 时用配置/透传抽头）
    - num_taps: 提取中心抽头数（默认 7）
    """
    sps_channel = int(config['system']['sps_channel'])
    pre_cursors = 2
    custom_taps = _resolve_taps(config, custom_tx_taps)

    # 1. 打理想单位脉冲过整条 Tx 链
    x, _, _ = _chain_impulse(config, custom_taps)

    # 2. 符号格基准 = 当前环境下透传冲激的峰值位置（按环境缓存）
    peak_idx = _peak_idx_for_env(config)

    # 3. 以 sps_channel 间隔取 num_taps 个等效 T 间隔抽头
    fir_taps = np.zeros(num_taps)
    for i in range(num_taps):
        tap_offset = i - pre_cursors
        idx = peak_idx + tap_offset * sps_channel
        if 0 <= idx < len(x):
            fir_taps[i] = x[idx]
    return fir_taps


def extract_tx_features(config, custom_tx_taps=None, num_taps=7):
    """Model A 的输入 = **(绝对标定的) num_taps 个 T 间隔抽头**（单位 V），另返回驱动 RMS 供诊断。

    为什么必须绝对标定（v4 关键）：
      driver_gain 在因果上就是"Tx 链的标量乘子"。若把 FIR 做峰值归一化，波形**形状**对增益不变，
      于是 Model A 对 driver_gain 的偏导数恒为 0，梯度下降根本无法移动这一维（这正是上一版
      需要额外塞一个 drive_rms 特征的原因）。改成绝对量纲后，7 个抽头同时携带：
        · FFE 抽头 → 波形形状
        · CTLE 直流增益/峰化 → 抽头间的相对关系与整体幅度
        · driver_gain → 整体幅度
      三类信息都进了 Model A 的输入，因此 FFE / CTLE / driver_gain 三组自由度都能拿到非零梯度。

    返回 (fir_absolute, drive_rms)。

    数值约定：FIR 以标称驱动 RMS（DRIVE_RMS_NOMINAL = 0.617Vpp 对应的 RMS）为单位，
    便于回归条件数，同时不损失增益信息（增益倍率仍是特征上的乘法因子）。
    """
    custom_taps = _resolve_taps(config, custom_tx_taps)
    fir = extract_tx_s21(config, custom_tx_taps=custom_taps, num_taps=num_taps)
    return fir / DRIVE_RMS_NOMINAL, _drive_rms(config, custom_taps)


if __name__ == "__main__":
    from utils_config import load_config
    import create_config
    create_config.generate_config()
    config = load_config('config.xlsx')

    taps = extract_tx_s21(config)
    print("Extracted 7-tap Tx FIR:", np.round(taps, 4))
