import numpy as np
from scipy import signal
import os

try:
    import skrf as rf
except ImportError:
    rf = None

_s4p_cache = {}

# ---------------------------------------------------------------------------
# Tx front-end calibration constants.
#
# The SJTU-derived calibration is: the MZM must be driven at driver_vpp = 0.617 V (PAM4
# Vpp), i.e. an RMS of 0.617 * 0.3726, and the nominal driver gain is 2.0. The VGA is a
# swing-control stage *upstream* of the driver: it normalises the module-input signal to a
# FIXED level that does NOT depend on the driver gain. This is what makes driver_gain a real
# degree of freedom (it changes the actual MZM drive amplitude, hence the optical OMA versus
# MZM-linearity trade-off) instead of a cancelled-out no-op.
# ---------------------------------------------------------------------------
DRIVER_VPP_NOMINAL = 0.617
PAM4_RMS_FACTOR = 0.3726
DRIVER_GAIN_NOMINAL = 2.0
VGA_OUT_RMS_NOMINAL = DRIVER_VPP_NOMINAL * PAM4_RMS_FACTOR / DRIVER_GAIN_NOMINAL   # 0.11497 V


def wgn(rng, sigma, n):
    """White Gaussian noise vector (helper kept explicit for clarity)."""
    return rng.normal(0, sigma, n)


def _load_s4p_cached(path):
    """Cache the Touchstone Network so repeated simulations don't re-parse the file."""
    if path not in _s4p_cache:
        _s4p_cache[path] = rf.Network(path)
    return _s4p_cache[path]

def lowpass_filter(x, bw, fs, order=4):
    """ Butterworth low-pass filter """
    nyq = 0.5 * fs
    normal_cutoff = bw / nyq
    if normal_cutoff >= 1.0:
        return x
    b, a = signal.butter(order, normal_cutoff, btype='low', analog=False)
    y = signal.lfilter(b, a, x)
    return y

def apply_ctle(x, fs, f_z, f_p1, f_p2, g_dc_db, g_dc2_db, f_lf):
    """
    Apply IEEE 802.3ck / LPO MSA dual-gain CTLE in the frequency domain.
    """
    N = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(N, d=1.0/fs)
    
    g_dc = 10**(g_dc_db / 20)
    g_dc2 = 10**(g_dc2_db / 20)
    
    # Avoid 0 division in formula by adding a small epsilon to f, or just handle f=0
    # Actually f_z, f_p1, f_p2, f_lf are strictly > 0 so no division by zero.
    num1 = g_dc + 1j * f / f_z
    den1 = (1 + 1j * f / f_z) * (1 + 1j * f / f_p1) * (1 + 1j * f / f_p2)
    
    num2 = g_dc2 + 1j * f / f_lf
    den2 = 1 + 1j * f / f_lf
    
    H_ctle = (num1 / den1) * (num2 / den2)
    
    X_filtered = X * H_ctle
    return np.fft.irfft(X_filtered, n=N)

def apply_cd(E, fs, cd_ps_nm):
    if cd_ps_nm == 0:
        return E
    N = len(E)
    E_f = np.fft.fft(E)
    f = np.fft.fftfreq(N, d=1.0/fs)
    # CD phase: phi(f) = -pi * lambda^2 * D_total * 1e-3 * f^2 / c
    # D_total = cd_ps_nm [ps/nm]. The 1e-3 converts ps/nm -> s/m (group delay per wavelength);
    # a 1e-12 here (a previous units bug) made CD ~1e9 too small, effectively disabling it.
    D = cd_ps_nm * 1e-3
    lmbda = 1550e-9
    c = 3e8
    phase_cd = -np.pi * D * (lmbda**2) / c * (f**2)
    H_cd = np.exp(1j * phase_cd)
    return np.fft.ifft(E_f * H_cd)

def apply_dgd(P, fs, dgd_ps, pol_angle_deg=45.0):
    if dgd_ps == 0:
        return P
    N = len(P)
    P_f = np.fft.rfft(P)
    f = np.fft.rfftfreq(N, d=1.0/fs)
    theta = np.radians(pol_angle_deg)
    tau = dgd_ps * 1e-12
    H_dgd = np.cos(theta)**2 + np.sin(theta)**2 * np.exp(-1j * 2 * np.pi * f * tau)
    return np.fft.irfft(P_f * H_dgd, n=N)

def dac_zoh(x, sps_in, sps_out):
    """ DAC Zero-Order Hold upsampling """
    factor = sps_out // sps_in
    return np.repeat(x, factor)

def quantize(x, enob):
    """ Mid-tread uniform quantizer (ENOB bits, full-scale = max|x|, no clipping).

    Matches the SJTU `quantization.m` behavior: step = 2*max|x| / 2^ENOB,
    nearest-level rounding, zero is a reconstruction level.
    """
    if enob <= 0:
        return x
    A = np.max(np.abs(x))
    if A <= 1e-30:
        return x
    q = 2.0 * A / (2.0 ** enob)
    return np.round(x / q) * q

def find_f_scale_for_target_il(freqs, sdd21, target_il_db, nyquist):
    """ Find the frequency scaling factor to hit exactly target_il_db at nyquist """
    mag_db = 20 * np.log10(np.abs(sdd21) + 1e-12)
    idx = np.where(mag_db <= target_il_db)[0]
    if len(idx) > 0:
        first_cross_idx = idx[0]
        if first_cross_idx > 0:
            f1, f2 = freqs[first_cross_idx-1], freqs[first_cross_idx]
            m1, m2 = mag_db[first_cross_idx-1], mag_db[first_cross_idx]
            f_match = f1 + (target_il_db - m1) / (m2 - m1) * (f2 - f1)
        else:
            f_match = freqs[0]
    else:
        f_match = freqs[-1]
        
    if f_match <= 0:
        f_match = 1e9
        
    f_scale = nyquist / f_match
    return f_scale


def apply_s4p_filter(x, fs, config_ch, target_il_key, nyquist):
    s4p_path = config_ch.get('s4p_file', '')
    if not os.path.exists(s4p_path):
        return None
    
    nw = _load_s4p_cached(s4p_path)
    try:
        S21 = nw.s[:, 1, 0]
        S23 = nw.s[:, 1, 2]
        S41 = nw.s[:, 3, 0]
        S43 = nw.s[:, 3, 2]
        sdd21 = 0.5 * (S21 - S23 - S41 + S43)
    except Exception:
        sdd21 = nw.s[:, 1, 0] if nw.s.shape[1] == 2 else nw.s[:, 0, 0]
        
    freqs = nw.f
    N = len(x)
    X = np.fft.rfft(x)
    f_sig = np.fft.rfftfreq(N, d=1.0/fs)
    
    # Fallback to old key if new key doesn't exist
    il_key_to_use = target_il_key if target_il_key in config_ch else 'target_il_nyquist_db'
    
    if il_key_to_use in config_ch:
        f_scale = find_f_scale_for_target_il(freqs, sdd21, -abs(config_ch[il_key_to_use]), nyquist)
    else:
        f_scale = config_ch.get('s4p_f_scale', 1.0)
        
    f_sig_scaled = f_sig / f_scale
    sdd21_mag = np.interp(f_sig_scaled, freqs, np.abs(sdd21), left=np.abs(sdd21)[0], right=0.0)
    sdd21_phase = np.interp(f_sig_scaled, freqs, np.unwrap(np.angle(sdd21)), left=np.angle(sdd21)[0], right=0.0)
    H_channel = sdd21_mag * np.exp(1j * sdd21_phase)
    
    X_filtered = X * H_channel
    return np.fft.irfft(X_filtered, n=N)

def tx_frontend_lti(x, config, baud_rate, fs_analog, nyquist, rng=None):
    """Tx 模拟前端（线性时不变部分），顺序与物理链路严格一致：

        Tx 电插损(S4P/解析) -> [1 mV 前端噪声] -> Tx 模拟 CTLE -> VGA(AGC) -> Driver 真增益 -> Driver 带限

    要点：
    - Tx 模拟 CTLE 位于电插损之后、Driver 之前（post-channel 均衡）。
    - VGA 紧跟在 CTLE 之后，把信号归一化到固定 RMS（vga_out_rms）：这样 CTLE 主要负责
      **频谱整形**（其直流增益被 VGA 吸收），而驱动摆幅只由 driver_gain 决定 ——
      两个搜索维度在物理上互不冗余。
    - driver_gain 是真实、独立的自由度（决定 MZM 驱动幅度，即 OMA 与 MZM 线性度的折中）。
    - 该函数被 channel_imdd.apply_channel 与 tx_channel_extract 物理探针共用，
      保证"真实链路"与"探针"永不漂移。
    """
    config_ch = config['channel']
    config_tx = config['tx']

    loss_db = config_ch.get('tx_pcb_loss_nyquist_db', config_ch.get('pcb_loss_nyquist_db', 15.0))
    fc_pcb = nyquist / np.sqrt(10 ** (loss_db / 10) - 1)

    # 1) Tx 电插损（Host Tx -> Module Tx）
    if config_ch.get('use_s4p', False) and rf is not None:
        x_s4p = apply_s4p_filter(x, fs_analog, config_ch, 'tx_pcb_loss_nyquist_db', nyquist)
        if x_s4p is not None:
            x = x_s4p
        else:
            print("Warning: S4P file not found. Using analytical filter.")
            x = lowpass_filter(x, fc_pcb, fs_analog, order=1)
    else:
        x = lowpass_filter(x, fc_pcb, fs_analog, order=1)

    # 2) 模块输入端的 1 mV 前端噪声（在 VGA/Driver 增益之前，故随补偿增益一起被放大）
    if rng is not None:
        x = x + rng.normal(0, config_ch.get('host_tx_noise_rms', 0.001), len(x))

    # 3) Tx 模拟 CTLE（电插损之后、Driver 之前）。放在 VGA 之前，使其主要作用是
    #    "频谱整形/峰化"而不是"改摆幅"：直流增益会被后面的 VGA 归一化掉，
    #    因此 CTLE 与 driver_gain 两个维度在物理上互不冗余。
    if config_tx.get('use_ctle', False):
        f_b = baud_rate
        f_z = f_b / config_tx.get('ctle_fz_ratio', 2.5)
        f_p1 = f_b / config_tx.get('ctle_fp1_ratio', 2.5)
        f_p2 = f_b / config_tx.get('ctle_fp2_ratio', 1.0)
        f_lf = f_b / config_tx.get('ctle_flf_ratio', 40.0)
        x = apply_ctle(x, fs_analog, f_z, f_p1, f_p2,
                       config_tx.get('ctle_g_dc_db', 0.0),
                       config_tx.get('ctle_g_dc2_db', 0.0), f_lf)

    # 4) VGA：归一化到固定模块输入 RMS（与 driver_gain 解耦）。
    #    放在 CTLE 之后 => 驱动摆幅由 driver_gain 单独决定，CTLE 只改变波形形状。
    x = x - np.mean(x)
    current_rms = np.std(x)
    vga_out_rms = config_ch.get('vga_out_rms', VGA_OUT_RMS_NOMINAL)
    if current_rms > 1e-12:
        x = x * (vga_out_rms / current_rms)

    # 5) Driver：真实线性增益（可调搜索维度）+ 自身带限
    x = x * config_ch.get('driver_gain', DRIVER_GAIN_NOMINAL)
    x = lowpass_filter(x, config_ch.get('driver_bw', config_ch.get('mzm_bw', 40e9)),
                       fs_analog, order=4)
    return x


def apply_channel(x_dac, config, baud_rate, sps_dac, sps_channel, sps_adc):
    config_ch = config['channel']
    config_tx = config['tx']
    """ Apply sequential IMDD channel bandwidth limitations at high sps """
    nyquist = baud_rate / 2
    
    # Tx Electrical Loss
    loss_db_tx = config_ch.get('tx_pcb_loss_nyquist_db', config_ch.get('pcb_loss_nyquist_db', 15.0))
    fc_pcb_tx = nyquist / np.sqrt(10**(loss_db_tx/10) - 1)
    
    # Rx Electrical Loss
    loss_db_rx = config_ch.get('rx_pcb_loss_nyquist_db', 15.0)
    fc_pcb_rx = nyquist / np.sqrt(10**(loss_db_rx/10) - 1)
    
    rng = np.random.RandomState(int(config_ch.get('seed', 123)))

    # 2. DAC Output: ENOB quantization -> ZOH
    if config_ch.get('dac_enob', 0) > 0:
        x_dac = quantize(x_dac, config_ch['dac_enob'])
    x = dac_zoh(x_dac, sps_dac, sps_channel)
    fs_analog = baud_rate * sps_channel

    # [Host Tx Noise]
    if config_ch.get('use_distributed_noise', False):
        x += rng.normal(0, config_ch.get('host_tx_noise_rms', 0.0), len(x))

    # NOTE: the Tx analog CTLE is NOT applied here any more. It belongs AFTER the Tx
    # electrical insertion loss and BEFORE the driver (see the module-input section below).
    # Applying it at the DAC output made it largely ineffective: the post-channel VGA
    # re-normalisation absorbed its flat gain, so it could not shape the spectrum that
    # actually reaches the MZM.

    # --- ISI BYPASS (DEBUG MODE) ---
    if config_ch.get('disable_isi', False):
        loss_db = config_ch.get('target_il_nyquist_db', 18.0)
        x = x * (10 ** (-abs(loss_db) / 20.0))
        fiber_loss_db = config_ch['fiber_length_km'] * config_ch['fiber_loss_db_km']
        x = x * (10 ** (-fiber_loss_db / 20.0))
        signal_power = np.mean(x**2)
        snr_linear = 10**(config_ch['snr_db'] / 10)
        noise_power = signal_power / snr_linear
        noise = rng.normal(0, np.sqrt(noise_power), len(x))
        x_noisy = x + noise
        dec_factor = sps_channel // sps_adc
        x_adc_out = x_noisy[::dec_factor]
        return x, x_noisy, x_adc_out
    # -------------------------------
    
    # [Host Tx to Module Tx] -> 1 mV 前端噪声 -> VGA -> Tx 模拟 CTLE -> Driver(真增益 + 带限)
    # 与物理探针共用同一实现（tx_frontend_lti），保证"探针 = 真实链路"，永不漂移。
    x = tx_frontend_lti(x, config, baud_rate, fs_analog, nyquist, rng=rng)

    x_analog = x.copy()
    
    # --- E-O Conversion (Laser + MZM) ---
    P_in_W = 10**(3.0/10) / 1000.0  # 3 dBm average laser power
    rin_db_hz = config_ch.get('laser_rin_db_hz', -150)
    rin_linear = 10**(rin_db_hz / 10)
    bw_noise = fs_analog / 2
    var_rin = rin_linear * bw_noise * (P_in_W**2)
    
    P_laser = P_in_W + rng.normal(0, np.sqrt(var_rin), len(x))
    P_laser = np.maximum(P_laser, 0.0)

    # Laser phase noise (linewidth -> Wiener phase random walk). In a direct-detection IMDD
    # link this only converts to intensity noise through fiber dispersion (CD), so it is
    # transparent at CD=0 and stresses the CD cases — matching the physical model.
    linewidth_hz = config_ch.get('laser_linewidth_hz', 0.0)
    if linewidth_hz > 0:
        dphase = rng.normal(0, np.sqrt(2.0 * np.pi * linewidth_hz / fs_analog), len(x))
        phase_noise = np.cumsum(dphase)
    else:
        phase_noise = np.zeros(len(x))
    E_in = np.sqrt(P_laser) * np.exp(1j * phase_noise)
    
    v_pi = config_ch.get('mzm_v_pi', 3.0)
    v_bias = config_ch.get('mzm_v_bias', 2.25)
    er_db = config_ch.get('mzm_er_db', 25.0)
    
    e_r = 10**(er_db / 10)
    gamma = (1 - 1/np.sqrt(e_r)) / 2
    phase = np.pi * (x + v_bias) / v_pi
    E_out = E_in * (gamma * np.exp(1j * phase) + (1 - gamma) * np.exp(-1j * phase))
    
    E_out = lowpass_filter(E_out, config_ch['mzm_bw'], fs_analog)
    
    # --- Fiber Channel ---
    loss_db = config_ch['fiber_length_km'] * config_ch['fiber_loss_db_km']
    loss_linear = 10**(-loss_db / 20.0)
    E_out = E_out * np.sqrt(loss_linear)  # Field scales with sqrt of power loss
    
    cd_ps_nm = config_ch.get('cd_ps_nm', 0.0)
    E_out = apply_cd(E_out, fs_analog, cd_ps_nm)
    
    # 7. Receiver - O-E Conversion (PIN + TIA)
    # PIN Detection (Square Law)
    P_rx = np.abs(E_out)**2
    
    # Apply DGD on detected power
    dgd_ps = config_ch.get('dgd_ps', 0.0)
    pol_angle_deg = config_ch.get('pol_angle_deg', 45.0)
    P_rx = apply_dgd(P_rx, fs_analog, dgd_ps, pol_angle_deg)
    resp = config_ch.get('pin_responsivity', 0.6)
    dark_current = config_ch.get('pin_dark_current_na', 10.0) * 1e-9
    I_pd = resp * P_rx + dark_current
    
    q_charge = 1.602176634e-19
    k_B = 1.380649e-23
    temp_k = config_ch.get('temperature_k', 298.15)
    rl_ohm = config_ch.get('rl_ohm', 50.0)
    
    var_shot = 2 * q_charge * np.abs(I_pd) * bw_noise
    noise_shot = rng.normal(0, np.sqrt(var_shot))
    
    var_thermal = 4 * k_B * temp_k / rl_ohm * bw_noise
    noise_thermal = rng.normal(0, np.sqrt(var_thermal), len(I_pd))
    
    I_pd_noisy = I_pd + noise_shot + noise_thermal
    I_pd_noisy = lowpass_filter(I_pd_noisy, config_ch['pd_bw'], fs_analog)
    
    # --- TIA ---
    tia_gain = config_ch.get('tia_gain_ohm', 720.0)
    V_tia = I_pd_noisy * tia_gain
    
    tia_noise_pa = config_ch.get('tia_noise_pa_rthz', 16.0) * 1e-12
    var_tia = (tia_noise_pa**2) * bw_noise
    noise_tia_v = rng.normal(0, np.sqrt(var_tia) * tia_gain, len(V_tia))
    
    V_tia = V_tia + noise_tia_v
    V_tia = lowpass_filter(V_tia, config_ch['tia_bw'], fs_analog)
    
    # AGC / TIA output swing control
    V_tia = V_tia - np.mean(V_tia)
    # Target 500mV Vpp. For PAM4, V_rms = Vpp * 0.3726 = 0.5 * 0.3726 = 0.1863
    current_rms_tia = np.std(V_tia)
    if current_rms_tia > 1e-12:
        V_tia = V_tia * (0.1863 / current_rms_tia)
        
    x = V_tia
    
    # [Module Rx to Host Rx]
    if config_ch.get('use_s4p', False) and rf is not None:
        x_filtered = apply_s4p_filter(x, fs_analog, config_ch, 'rx_pcb_loss_nyquist_db', nyquist)
        if x_filtered is not None:
            x = x_filtered
        else:
            x = lowpass_filter(x, fc_pcb_rx, fs_analog, order=1)
    else:
        x = lowpass_filter(x, fc_pcb_rx, fs_analog, order=1)
        
    # [Host Rx Noise]
    x += rng.normal(0, config_ch.get('host_rx_noise_rms', 0.001), len(x))
        
    x_eq = x
    
    # 8. ADC Analog Front-End (Anti-alias + Bandwidth)
    x_adc_in = lowpass_filter(x_eq, config_ch['adc_bw'], fs_analog)
    
    # 9. ADC Sampling
    dec_factor = sps_channel // sps_adc
    x_adc_out = x_adc_in[::dec_factor]
    
    # ADC quantization (ENOB)
    if config_ch.get('adc_enob', 0) > 0:
        x_adc_out = quantize(x_adc_out, config_ch['adc_enob'])
    
    # Ideal Digital AGC: Normalize ADC output to match PAM4 Tx RMS (sqrt(5))
    x_adc_out = x_adc_out - np.mean(x_adc_out)
    rms_adc = np.std(x_adc_out)
    if rms_adc > 1e-12:
        x_adc_out = x_adc_out * (np.sqrt(5.0) / rms_adc)
    
    return x_analog, x_adc_in, x_adc_out
