import numpy as np
from main import run_sim
from tx_channel_extract import extract_tx_features
from channel_imdd import GAIN_LOG10_MIN, GAIN_LOG10_MAX, DRIVER_GAIN_NOMINAL

# ============================================================
# DDPS (Data-Driven Physical Surrogate) 数据驱动物理代理优化器
#
# 架构（两阶段）：
#   Stage 1（离线）：生成环境锚定邻域数据集 -> 训练两个白盒 Ridge 代理：
#       Model A（方向代理）：发端 8 维探针（7-tap Tx FIR + drive_rms）-> log10(BER_MLSE)
#       Model B（风险控制）：参数域 7 维（4 FFE 旁瓣 + gDC + gDC2 + drive_rms）-> log10(BER_MLSE)
#       Stage 1 的采样/训练实现位于 dataset_generator.py 与 train_surrogates.py；
#       本文件提供搜索空间、物理评估与 Stage 2 在线寻优。
#
#   Stage 2（在线寻优）：7 维（4 FFE 旁瓣 + gDC + gDC2 + u_gain）链式梯度下降。
#       - 方向：Model A 的链式梯度（扰动参数 -> 重算探针 -> 查 A -> 中心差分）。
#       - 安全：Model B 参数域保守上包络 + 红线（相对种子最多变差 25%）+ 轨迹信任域。
#       - 真实 BER_MLSE 仅记账，不回传决策。
#
# 白盒约束：不依赖任何第三方现成算法；Ridge 闭式解、梯度、线搜索均手写。
# ============================================================

# ---------------------------------------------------------------------------
# Tx FFE：**5 抽头**（4 个旁瓣自由变量 + 1 个派生主抽头），T-spaced。
# 主抽头 = 1 - Σ|旁瓣|；Σ|旁瓣| 上界 PEAK_SUM_LIMIT 保证主抽头 >= 0.2。
# ---------------------------------------------------------------------------
N_FFE_TAPS = 5
FFE_PRE = 2                    # 主抽头位置（2 个前游标 + 2 个后游标）
N_SIDE = N_FFE_TAPS - 1        # 4 个旁瓣自由变量

FFE_BOUND = 0.3
# CTLE 搜索边界（peaking 语义）：
#   g_dc  = 高频 peaking gain (dB)，直流增益恒 0 dB。≥0 才有意义（负值=额外衰减高频）。
#   g_dc2 = LF shelf gain (dB)。
CTLE_GDC_MIN = 0.0
CTLE_GDC_MAX = 12.0
CTLE_GDC2_MIN = 0.0
CTLE_GDC2_MAX = 4.0
PEAK_SUM_LIMIT = 0.8          # sum(|pre_post|) <= 0.8 -> 主抽头 >= 0.2

# ---------------------------------------------------------------------------
# Model B 拦截判据：**按"变差的百分比"**（不是绝对 BER，也不是 log10 绝对裕度）
#
#   allowed_ber = ber_seed_pred * (1 + MAX_DEGRADE_FRAC)
#   等价于 log10 空间：pred_b <= pred_b_seed + log10(1 + MAX_DEGRADE_FRAC)
#
# 为什么用百分比：代理的绝对标定不可信（欠/过估），但"相对种子变差多少倍"是可比的；
# 百分比阈值天然与 BER 量级无关，跨用例、跨环境都不用重新标定。
# ---------------------------------------------------------------------------
MAX_DEGRADE_FRAC = 0.25       # 允许 Model B 预测相对种子最多变差 25%

# ---------------------------------------------------------------------------
# Stage 2 信任域 / 步长 / 门控
# ---------------------------------------------------------------------------
TRUST_FFE = 0.10              # FFE 信任域半径（相对起点）
TRUST_CTLE = 3.0              # CTLE 信任域半径（dB）
GAIN_TRUST = 0.15             # gain 信任域半径（log10 dex，围绕 per-case 初值）
GD_LR = 0.05                  # 初始步长（相对各维箱宽的比例，随 step 以 ALPHA_DECAY 衰减）
ALPHA_DECAY = 0.97            # 步长衰减：越走越稳（末期用于收敛落点）
TRUST_PATH_K = 2.0            # 轨迹信任域：标准化位移超过 TRUST_PATH_K × ρ 就停
                              # ρ = 训练数据的局部颗粒度（第 32 近邻中位距离，训练时写入
                              # model.local_spacing_）。
GROUP_GATE = 1e-3             # 组梯度门控：某组"每走满整箱"的预测收益低于该值（dex）就冻结该组
MIN_GAIN_DEX = 0.01           # 边际改善门控：Model A 预测每步改善 < 0.01 个 log10 即停

# ---------------------------------------------------------------------------
# 搜索空间：x = [4 FFE 旁瓣, gDC, gDC2, u_gain]（7 维）
#   u_gain = log10(gain / DRIVER_GAIN_NOMINAL)，对数参数化让"增益步长"与量级无关。
# 各维步长按各自箱宽的比例走（分组归一化），避免某一组量纲吃掉其它组。
# ---------------------------------------------------------------------------
N_DIM = N_SIDE + 3          # 4 旁瓣 + gDC + gDC2 + u_gain = 7

# 评估协议：仿真种子序列。多 seed 时对 log10 BER 取均值，抑制"单一实现"造成的
# BER 估计噪声（比只加长块长更可控，且能同时给出点内标准差）。
SIM_SEEDS = (42,)


def set_sim_seeds(seeds):
    """设置评估用的仿真种子序列（数据集 / 在线测试 / 复核共用同一口径）。"""
    global SIM_SEEDS
    SIM_SEEDS = tuple(int(s) for s in seeds)
    return SIM_SEEDS


# 已知"不错的起点"（种子）：来自两阶段实验的初始次优点
SEED_TAPS = np.array([-0.034, -0.2987, 0.6091, 0.0, 0.0582])   # 5-tap：主抽头 = 1 - Σ|旁瓣|
SEED_GDC = 6.0                  # Tx CTLE peaking seed: moderate 6 dB (Rx adds another fixed 6 dB)
SEED_GDC2 = 2.0                 # Tx CTLE LF shelf seed: 2 dB
SEED_GAIN_U = 0.0             # u = log10(gain / DRIVER_GAIN_NOMINAL)，种子即标定值（0.0）
SEED_GAIN = DRIVER_GAIN_NOMINAL * (10.0 ** SEED_GAIN_U)
GAIN_MIN = DRIVER_GAIN_NOMINAL * (10.0 ** GAIN_LOG10_MIN)   # 实际增益下界
GAIN_MAX = DRIVER_GAIN_NOMINAL * (10.0 ** GAIN_LOG10_MAX)   # 实际增益上界

# 训练数据 gain 采样带（宽口径）：覆盖全部 15 用例 per-case 最优 gain（×0.30~×0.91）
# 及其 ±GAIN_TRUST 在线信任域，避免模型在 drive_rms 轴上对高损用例外推。
# 采样带 = ×0.20~×1.26（u ∈ [-0.70, +0.10]），在 u 空间均匀。
GAIN_SAMPLE_U_LO = -0.70
GAIN_SAMPLE_U_HI = 0.10

# 各维"满箱宽度"（用于分组归一化步长）：FFE 箱宽 = 2×信任域半径，CTLE = 2×信任域半径，
# gain = 2×GAIN_TRUST。
STEP_SPAN = np.array([2.0 * TRUST_FFE] * N_SIDE + [2.0 * TRUST_CTLE] * 2
                     + [2.0 * GAIN_TRUST])
# 三组自由度（用于分组归一化步长 + 分组梯度门控）
GROUP_SLICES = (slice(0, N_SIDE), slice(N_SIDE, N_SIDE + 2), slice(N_SIDE + 2, N_SIDE + 3))
GROUP_NAMES = ('FFE', 'CTLE', 'driver_gain')


def gain_from_u(u):
    """u = log10(g / g0) -> 实际线性增益。"""
    return float(DRIVER_GAIN_NOMINAL * (10.0 ** float(u)))


def u_from_gain(gain):
    """实际线性增益 -> u = log10(g / g0)。"""
    return float(np.log10(max(float(gain), 1e-12) / DRIVER_GAIN_NOMINAL))


def construct_taps(pre_post, ffe_pre=FFE_PRE, n_taps=N_FFE_TAPS):
    """4 个旁瓣 -> 5-tap FFE（主抽头由总能量恒等式派生）。"""
    pre_post = np.asarray(pre_post, dtype=float)
    abs_sum = np.sum(np.abs(pre_post))
    if abs_sum > PEAK_SUM_LIMIT:
        pre_post = pre_post * (PEAK_SUM_LIMIT / abs_sum)
    taps = np.zeros(n_taps)
    taps[:ffe_pre] = pre_post[:ffe_pre]
    taps[ffe_pre + 1:] = pre_post[ffe_pre:]
    taps[ffe_pre] = 1.0 - np.sum(np.abs(pre_post))
    return taps


def _apply_x_to_config(config, gdc, gdc2, gain):
    """把当前搜索点的 CTLE / driver_gain 写入 config（原地写入；顺序调用安全）。"""
    config['tx']['ctle_g_dc_db'] = float(gdc)
    config['tx']['ctle_g_dc2_db'] = float(gdc2)
    config['channel']['driver_gain'] = float(gain)


def _physical_eval(config, taps, gdc, gdc2, gain):
    """真实 BER 评估（对 SIM_SEEDS 里的多个仿真种子取 log10 均值）。

    返回 (log10_mean, 10**log10_mean)。多 seed 平均用于抑制 BER 估计噪声：
    单块长的 BER 绝对值会随实现变化，多实现取均值后轨迹才可比。
    """
    _apply_x_to_config(config, gdc, gdc2, gain)
    lbs = []
    for s in SIM_SEEDS:
        config['system']['seed'] = int(s)
        config['channel']['seed'] = int(s) + 7919
        _, mlse_ber = run_sim(config, custom_tx_taps=taps, plot_eyes=False, output_dir=None)
        mlse_ber = max(min(float(mlse_ber), 1.0), 1e-8)
        lbs.append(float(np.log10(mlse_ber)))
    mean_lb = float(np.mean(lbs))
    return mean_lb, float(10.0 ** mean_lb)


def _measure_drive_rms(config, taps, gdc, gdc2, gain):
    """发端指标：当前配置下 MZM 输入端的驱动 RMS（V）。

    只跑 Tx 模拟前端（FFE->DAC->IL->CTLE->Driver->Driver BW），不含 MZM 与后端，
    因此**不产生真实 BER**，属于 Stage-2 允许拿的发端指标。drive_rms ∝ gain
    （gain 是链路最后的线性乘子）。
    """
    _apply_x_to_config(config, gdc, gdc2, gain)
    _, drive_rms = extract_tx_features(config, custom_tx_taps=taps, num_taps=7)
    return float(drive_rms)


def _probe_features(config, taps, gdc, gdc2, gain):
    """提取 Model A 的 8 维探针特征：7-tap Tx FIR + drive_rms。

    必须先把 gdc/gdc2/gain 写入 config，否则探针用的是上次的 CTLE 设置，
    CTLE 维的链式梯度恒为 0。
    """
    _apply_x_to_config(config, gdc, gdc2, gain)
    fir, drive_rms = extract_tx_features(config, custom_tx_taps=taps, num_taps=7)
    return np.concatenate([fir, [drive_rms]])


def _predict_a_probe(model_a, probe_feat):
    """Model A 对探针特征的直接预测（标准化后）。"""
    x = np.asarray(probe_feat, dtype=float).reshape(1, -1)
    mu = np.asarray(getattr(model_a, 'mu', np.zeros(x.shape[1])), dtype=float)
    sd = np.asarray(getattr(model_a, 'sd', np.ones(x.shape[1])), dtype=float)
    x_n = (x - mu) / sd
    return float(np.asarray(model_a.predict(x_n)).ravel()[0])


def _predict_b_params(model_b, x_shape, drive_rms):
    """Model B 对参数域特征的预测（7 维 = x_shape + drive_rms）。"""
    feat = np.concatenate([np.asarray(x_shape, dtype=float), [drive_rms]])
    x = feat.reshape(1, -1)
    mu = np.asarray(getattr(model_b, 'mu', np.zeros(x.shape[1])), dtype=float)
    sd = np.asarray(getattr(model_b, 'sd', np.ones(x.shape[1])), dtype=float)
    x_n = (x - mu) / sd
    return float(np.asarray(model_b.predict(x_n)).ravel()[0])


def _bounds(x0):
    """七维搜索盒：FFE/CTLE 围绕种子、gain 围绕 per-case 初值收紧。"""
    x0 = np.asarray(x0, dtype=float)
    b = np.array([(-FFE_BOUND, FFE_BOUND)] * N_SIDE
                 + [(CTLE_GDC_MIN, CTLE_GDC_MAX), (CTLE_GDC2_MIN, CTLE_GDC2_MAX),
                    (GAIN_LOG10_MIN, GAIN_LOG10_MAX)])
    radius = np.array([TRUST_FFE] * N_SIDE + [TRUST_CTLE, TRUST_CTLE, GAIN_TRUST])
    return np.stack([np.maximum(b[:, 0], x0 - radius),
                     np.minimum(b[:, 1], x0 + radius)], axis=1)


def _grad_a_chain(model_a, config, x, ffe_pre, eps=0.01, eps_u=0.05):
    """七维链式梯度：∂A/∂x = [∂A/∂shape(6), ∂A/∂u_gain]。

    x = [4 FFE 旁瓣, gDC, gDC2, u_gain]（7 维）。
    shape 维：±eps 扰动参数 -> 重算探针 -> 查 A -> 中心差分（gain 固定）。
    gain 维：±eps_u 扰动 u_gain -> 换算线性 gain -> 重算探针（只有 drive_rms 变）-> 查 A。
    """
    x = np.asarray(x, dtype=float)
    g = np.zeros_like(x)
    taps = construct_taps(x[:N_SIDE], ffe_pre)
    gdc = float(x[N_SIDE])
    gdc2 = float(x[N_SIDE + 1])
    gain = gain_from_u(float(x[N_SIDE + 2]))
    eps_vec = np.array([eps] * N_SIDE + [eps * 10] * 2 + [eps_u])

    for i in range(len(x)):
        xp = x.copy(); xp[i] += eps_vec[i]
        xm = x.copy(); xm[i] -= eps_vec[i]
        if i < N_SIDE + 2:
            taps_p = construct_taps(xp[:N_SIDE], ffe_pre)
            taps_m = construct_taps(xm[:N_SIDE], ffe_pre)
            probe_p = _probe_features(config, taps_p, float(xp[N_SIDE]),
                                      float(xp[N_SIDE + 1]), gain)
            probe_m = _probe_features(config, taps_m, float(xm[N_SIDE]),
                                      float(xm[N_SIDE + 1]), gain)
        else:
            gp = gain_from_u(float(xp[N_SIDE + 2]))
            gm = gain_from_u(float(xm[N_SIDE + 2]))
            probe_p = _probe_features(config, taps, gdc, gdc2, gp)
            probe_m = _probe_features(config, taps, gdc, gdc2, gm)
        ap = _predict_a_probe(model_a, probe_p)
        am = _predict_a_probe(model_a, probe_m)
        g[i] = (ap - am) / (2.0 * eps_vec[i])
    return g


def _stage2_descent(config, model_a, model_b, x0, ffe_pre, n_steps, lr):
    """在线调优：7 维（4 FFE 旁瓣 + gDC + gDC2 + u_gain）链式梯度下降。

    x0 第 7 维 = 该 case per-case RMS 扫描最优 gain 的 u 编码（初值）。
    真实 BER 仅记账，不回传决策。
    """
    x = np.array(x0, dtype=float)
    tr_bounds = _bounds(x)
    span = STEP_SPAN.copy()

    # 初值点的探针 + B 预测（初值 = 种子形状 + per-case 最优 gain）
    taps0 = construct_taps(x[:N_SIDE], ffe_pre)
    gdc0 = float(x[N_SIDE]); gdc2 = float(x[N_SIDE + 1])
    gain0 = gain_from_u(float(x[N_SIDE + 2]))
    rms0 = _measure_drive_rms(config, taps0, gdc0, gdc2, gain0)
    seed_pred_b = _predict_b_params(model_b, x[:N_SIDE + 2], rms0)
    best_pred_b = seed_pred_b
    allowed_ber = (10.0 ** best_pred_b) * (1.0 + MAX_DEGRADE_FRAC)

    # 信任域（B 参数域 6 维 shape；gain 信任域由 _bounds 单独收紧）
    rho = float(getattr(model_b, 'local_spacing_', 0.0) or 0.0)
    sd_vec = np.asarray(getattr(model_b, 'sd', np.ones(7)), dtype=float)[:6]
    mu_vec = np.asarray(getattr(model_b, 'mu', np.zeros(7)), dtype=float)[:6]
    z0 = (x[:6] - mu_vec) / sd_vec
    path_limit = TRUST_PATH_K * rho if rho > 0 else None

    trace = []
    pred_a_prev = None

    for step in range(n_steps):
        g = _grad_a_chain(model_a, config, x, ffe_pre)
        gs = g * span
        direction = np.zeros_like(g)
        active = []
        for sl, name in zip(GROUP_SLICES, GROUP_NAMES):
            nrm = float(np.linalg.norm(gs[sl]))
            if nrm >= GROUP_GATE:
                direction[sl] = gs[sl] / nrm
                active.append(name)
        if not active:
            print(f'[Stage2] stop: 三组梯度均低于门控 {GROUP_GATE:g}（step {step}）')
            break

        # 回溯线搜索 + B 拦截
        alpha = lr * (ALPHA_DECAY ** step)
        x_new = None
        alpha_k = alpha
        for _ in range(20):
            x_cand = np.clip(x - alpha_k * span * direction,
                             tr_bounds[:, 0], tr_bounds[:, 1])
            if np.linalg.norm(x_cand - x) < 1e-9:
                break
            taps_c = construct_taps(x_cand[:N_SIDE], ffe_pre)
            gdc_c = float(x_cand[N_SIDE]); gdc2_c = float(x_cand[N_SIDE + 1])
            gain_c = gain_from_u(float(x_cand[N_SIDE + 2]))
            rms_c = _measure_drive_rms(config, taps_c, gdc_c, gdc2_c, gain_c)
            if _predict_b_params(model_b, x_cand[:N_SIDE + 2], rms_c) <= np.log10(allowed_ber):
                x_new = x_cand
                break
            alpha_k *= 0.5
        if x_new is None:
            print(f'[Stage2] stop: 无候选点通过 Model B 拦截（step {step}）')
            break

        # 轨迹信任域（只对 shape 6 维）
        if path_limit is not None:
            z_new = (x_new[:6] - mu_vec) / sd_vec
            if float(np.linalg.norm(z_new - z0)) > path_limit:
                print(f'[Stage2] stop: 轨迹位移超过信任域（step {step}）')
                break

        taps_new = construct_taps(x_new[:N_SIDE], ffe_pre)
        gdc_new = float(x_new[N_SIDE]); gdc2_new = float(x_new[N_SIDE + 1])
        gain_new = gain_from_u(float(x_new[N_SIDE + 2]))
        probe_new = _probe_features(config, taps_new, gdc_new, gdc2_new, gain_new)
        pred_a = _predict_a_probe(model_a, probe_new)
        rms_actual = _measure_drive_rms(config, taps_new, gdc_new, gdc2_new, gain_new)
        pred_b = _predict_b_params(model_b, x_new[:N_SIDE + 2], rms_actual)
        real_logber, real_mlse = _physical_eval(config, taps_new, gdc_new, gdc2_new, gain_new)

        # 红线基准下移（B 改善时）
        if pred_b < best_pred_b:
            best_pred_b = pred_b
            allowed_ber = (10.0 ** best_pred_b) * (1.0 + MAX_DEGRADE_FRAC)

        # 边际改善门控
        if pred_a_prev is not None and (pred_a_prev - pred_a) < MIN_GAIN_DEX:
            trace.append({
                'step': step, 'x': x_new, 'taps': taps_new,
                'gdc': gdc_new, 'gdc2': gdc2_new, 'gain': gain_new,
                'gain_ratio': gain_new / DRIVER_GAIN_NOMINAL,
                'u_gain': float(x_new[N_SIDE + 2]),
                'drive_rms': rms_actual,
                'pred_a': pred_a, 'pred_b': pred_b,
                'pred_b_ber': 10.0 ** pred_b, 'allowed_ber': allowed_ber,
                'real_logber': real_logber, 'real_mlse': real_mlse,
                'grad_norm': float(np.linalg.norm(g)), 'stop_reason': 'marginal_gain',
            })
            print(f"[Stage2] stop: marginal predicted gain "
                  f"({pred_a_prev - pred_a:+.4f} < {MIN_GAIN_DEX}) at step {step}")
            break
        pred_a_prev = pred_a

        trace.append({
            'step': step, 'x': x_new, 'taps': taps_new,
            'gdc': gdc_new, 'gdc2': gdc2_new, 'gain': gain_new,
            'gain_ratio': gain_new / DRIVER_GAIN_NOMINAL,
            'u_gain': float(x_new[N_SIDE + 2]),
            'drive_rms': rms_actual,
            'pred_a': pred_a, 'pred_b': pred_b,
            'pred_b_ber': 10.0 ** pred_b, 'allowed_ber': allowed_ber,
            'real_logber': real_logber, 'real_mlse': real_mlse,
            'grad_norm': float(np.linalg.norm(g)), 'stop_reason': '',
        })

        print(f"[Stage2] gd {step + 1}/{n_steps} | ModelA {10.0 ** pred_a:.2e} "
              f"| real {real_mlse:.2e} | gain x{gain_new / DRIVER_GAIN_NOMINAL:.3f} "
              f"| u_gain {float(x_new[N_SIDE + 2]):+.3f} | gDC {gdc_new:+.2f} "
              f"| gDC2 {gdc2_new:+.2f} | 组 {active}")

        if np.linalg.norm(x_new - x) < 1e-6:
            break
        x = x_new

    return trace


def _stage2_descent_aonly(config, model_a, x0, ffe_pre, n_steps, lr):
    """A-only：只用 Model A 七维链式梯度，不查 Model B、不走安全拦截。"""
    x = np.array(x0, dtype=float)
    tr_bounds = _bounds(x)
    span = STEP_SPAN.copy()
    trace = []
    pred_a_prev = None

    for step in range(n_steps):
        g = _grad_a_chain(model_a, config, x, ffe_pre)
        gs = g * span
        direction = np.zeros_like(g)
        active = []
        for sl, name in zip(GROUP_SLICES, GROUP_NAMES):
            nrm = float(np.linalg.norm(gs[sl]))
            if nrm >= GROUP_GATE:
                direction[sl] = gs[sl] / nrm
                active.append(name)
        if not active:
            break

        alpha = lr * (ALPHA_DECAY ** step)
        x_new = np.clip(x - alpha * span * direction, tr_bounds[:, 0], tr_bounds[:, 1])
        if np.linalg.norm(x_new - x) < 1e-9:
            break

        taps_new = construct_taps(x_new[:N_SIDE], ffe_pre)
        gdc_new = float(x_new[N_SIDE]); gdc2_new = float(x_new[N_SIDE + 1])
        gain_new = gain_from_u(float(x_new[N_SIDE + 2]))
        probe_new = _probe_features(config, taps_new, gdc_new, gdc2_new, gain_new)
        pred_a = _predict_a_probe(model_a, probe_new)
        rms_actual = _measure_drive_rms(config, taps_new, gdc_new, gdc2_new, gain_new)
        real_logber, real_mlse = _physical_eval(config, taps_new, gdc_new, gdc2_new, gain_new)

        if pred_a_prev is not None and (pred_a_prev - pred_a) < MIN_GAIN_DEX:
            trace.append({
                'step': step, 'x': x_new, 'taps': taps_new,
                'gdc': gdc_new, 'gdc2': gdc2_new, 'gain': gain_new,
                'gain_ratio': gain_new / DRIVER_GAIN_NOMINAL,
                'u_gain': float(x_new[N_SIDE + 2]),
                'drive_rms': rms_actual,
                'pred_a': pred_a, 'pred_b': 0.0,
                'pred_b_ber': 0.0, 'allowed_ber': 0.0,
                'real_logber': real_logber, 'real_mlse': real_mlse,
                'grad_norm': float(np.linalg.norm(g)), 'stop_reason': 'marginal_gain',
            })
            break
        pred_a_prev = pred_a

        trace.append({
            'step': step, 'x': x_new, 'taps': taps_new,
            'gdc': gdc_new, 'gdc2': gdc2_new, 'gain': gain_new,
            'gain_ratio': gain_new / DRIVER_GAIN_NOMINAL,
            'u_gain': float(x_new[N_SIDE + 2]),
            'drive_rms': rms_actual,
            'pred_a': pred_a, 'pred_b': 0.0,
            'pred_b_ber': 0.0, 'allowed_ber': 0.0,
            'real_logber': real_logber, 'real_mlse': real_mlse,
            'grad_norm': float(np.linalg.norm(g)), 'stop_reason': '',
        })

        print(f"[Aonly] gd {step + 1}/{n_steps} | ModelA {10.0 ** pred_a:.2e} "
              f"| real {real_mlse:.2e} | gain x{gain_new / DRIVER_GAIN_NOMINAL:.3f} "
              f"| u_gain {float(x_new[N_SIDE + 2]):+.3f} | gDC {gdc_new:+.2f} | gDC2 {gdc2_new:+.2f}")

        if np.linalg.norm(x_new - x) < 1e-6:
            break
        x = x_new

    return trace


def run_ddps(*args, **kwargs):
    """历史入口已废弃（保留仅为给出明确报错，避免静默误用）。

    请使用现役三段式入口：
      1) dataset_generator.py 生成数据集；
      2) train_surrogates.train() 训练代理；
      3) test_generalization.py 运行在线寻优。
    """
    raise RuntimeError(
        "run_ddps() 已移除：DDPS 已重构为 dataset_generator.py -> "
        "train_surrogates.train() -> test_generalization.py 三段式流水线。"
    )