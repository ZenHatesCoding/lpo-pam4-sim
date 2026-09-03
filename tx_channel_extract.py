import numpy as np
import os
from tx_dsp import tx_dsp_chain
from channel_imdd import apply_ctle, dac_zoh, lowpass_filter, find_f_scale_for_target_il, apply_s4p_filter
try:
    import skrf as rf
except ImportError:
    rf = None

_s4p_cache = {}
_ref_peak_idx = None


def _load_s4p_cached(path):
    """Cache the Touchstone Network so repeated extractions don't re-parse the file."""
    if path not in _s4p_cache:
        _s4p_cache[path] = rf.Network(path)
    return _s4p_cache[path]


def _fixed_peak_idx(x):
    """固定参考对齐：首次调用时锁定峰值位置，之后所有提取共用同一基准。

    （argmax 会在两个近等峰值之间跳变，导致 FIR 特征在 FFE 系数上不连续，
      进而污染梯度下降。固定对齐使 FIR 成为 x 的光滑函数。）
    """
    global _ref_peak_idx
    if _ref_peak_idx is None:
        _ref_peak_idx = int(np.argmax(np.abs(x)))
    return _ref_peak_idx

def extract_tx_s21(config, custom_tx_taps=None, num_taps=7):
    pre_cursors = 2
    """
    Extract the equivalent T-spaced FIR representation of the entire 
    transmitter (Tx FFE -> DAC -> CTLE -> PCB -> MZM Modulator).
    
    config: system configuration dict
    custom_tx_taps: 9-tap FFE weights (if None, reads from config)
    num_taps: number of central taps to extract (default 7)
    pre_cursors: number of pre-cursors before the main cursor (default 2)
    
    Returns:
        np.ndarray of shape (num_taps,) representing the Tx equivalent impulse response.
    """
    baud_rate = config['system']['baud_rate']
    sps_dsp = int(config['system']['sps_dsp'])
    sps_dac = int(config['system']['sps_dac'])
    sps_channel = int(config['system']['sps_channel'])
    
    # 1. Create a clean digital impulse (Dirac delta) at baud rate
    # Need enough padding to avoid boundary effects
    pad_len = 100
    tx_symbols = np.zeros(2 * pad_len + 1)
    tx_symbols[pad_len] = 1.0 # The impulse
    
    # Optional override for Tx FFE taps
    tx_config = config['tx'].copy()
    if custom_tx_taps is not None:
        tx_config['custom_taps'] = custom_tx_taps
    elif 'custom_taps' in tx_config:
        val = tx_config['custom_taps']
        if isinstance(val, str) and val.strip().startswith('['):
            import ast
            tx_config['custom_taps'] = np.array(ast.literal_eval(val))
        else:
            tx_config['custom_taps'] = np.array(val)
    else:
        default_taps = np.zeros(int(tx_config['ffe_taps']))
        default_taps[int(tx_config['ffe_pre'])] = 1.0
        tx_config['custom_taps'] = default_taps
        
    # 2. Digital Tx DSP (FFE)
    tx_out = tx_dsp_chain(tx_symbols, sps_dsp, baud_rate, tx_config)
    
    # 3. DAC (ZOH) -> Upsample to channel rate
    x_analog = dac_zoh(tx_out, sps_dac, sps_channel)
    fs_analog = baud_rate * sps_channel
    
    # 4. CTLE (if enabled)
    if tx_config.get('use_ctle', False):
        f_b = baud_rate
        f_z = f_b / tx_config.get('ctle_fz_ratio', 2.5)
        f_p1 = f_b / tx_config.get('ctle_fp1_ratio', 2.5)
        f_p2 = f_b / tx_config.get('ctle_fp2_ratio', 1.0)
        f_lf = f_b / tx_config.get('ctle_flf_ratio', 40.0)
        g_dc_db = tx_config.get('ctle_g_dc_db', 0.0)
        g_dc2_db = tx_config.get('ctle_g_dc2_db', 0.0)
        x_analog = apply_ctle(x_analog, fs_analog, f_z, f_p1, f_p2, g_dc_db, g_dc2_db, f_lf)
        
    # 5. Host PCB Trace (same IL scaling as apply_channel for consistency)
    config_ch = config['channel']
    nyquist = baud_rate / 2
    loss_db = config_ch.get('tx_pcb_loss_nyquist_db', config_ch.get('pcb_loss_nyquist_db', 15.0))
    fc_pcb = nyquist / np.sqrt(10**(loss_db/10) - 1)
    
    if config_ch.get('use_s4p', False) and rf is not None:
        x_s4p = apply_s4p_filter(x_analog, fs_analog, config_ch, 'tx_pcb_loss_nyquist_db', nyquist)
        if x_s4p is not None:
            x = x_s4p
        else:
            x = lowpass_filter(x_analog, fc_pcb, fs_analog, order=1)
    else:
        x = lowpass_filter(x_analog, fc_pcb, fs_analog, order=1)
        
    # 6. E-O Conversion (MZM Modulator)
    x = lowpass_filter(x, config_ch['mzm_bw'], fs_analog)
    
    # 7. Extract the T-spaced equivalent FIR from the overall impulse response
    # The signal `x` is sampled at `sps_channel`. We want to downsample to 1 sps.
    # 用固定参考对齐（而非每次 argmax），保证 FIR 特征对 FFE 系数光滑。
    peak_idx = _fixed_peak_idx(x)
    
    # We want to extract `num_taps` around the peak at `sps_channel` intervals.
    # The peak is the main cursor.
    # We usually take some pre-cursors and some post-cursors.
    # E.g., for 7 taps, we might take 2 pre, 1 main, 4 post.
    # However, depending on the actual FFE configuration, the peak might shift.
    # Let's align such that the main cursor index corresponds to the original impulse.
    
    # Alternative to argmax: we know the impulse was at `pad_len`. 
    # The delay introduced by tx_dsp (pulse shaping) is `pad_len * sps_channel`.
    # Let's just find the global peak and extract relative to it.
    
    post_cursors = num_taps - pre_cursors - 1
    
    fir_taps = np.zeros(num_taps)
    for i in range(num_taps):
        tap_offset = i - pre_cursors
        idx = peak_idx + tap_offset * sps_channel
        if 0 <= idx < len(x):
            fir_taps[i] = x[idx]
            
    # Normalize for scale invariance? Or keep absolute scale?
    # Keeping absolute scale preserves loss information, but normalization might be better for ML.
    # We will keep absolute values so the model sees the real attenuation.
    return fir_taps

if __name__ == "__main__":
    from utils_config import load_config
    import create_config
    create_config.generate_config()
    config = load_config('config.xlsx')
    
    # Test extraction
    taps = extract_tx_s21(config)
    print("Extracted 7-tap Tx FIR:", np.round(taps, 4))
