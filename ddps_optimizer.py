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
GAIN_TRUST = 0.30             # gain 信任域半径（log10 dex，围绕 per-case 初值）
                               # 物理层 per-case 最优 gain 跨 ×0.30~×0.91（0.48 dex），
                               # 需 ±0.30 才能从居中次优点覆盖全用例（仍落在训练采样带 ×0.20~×1.26 内）
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


# 兜底种子（未提供 --seed-config 时使用）：名义工程种子，不是次优演示起点。
# 次优演示起点（次优工作点，形状 + CTLE + gain 全给定）通过 result/seed_config_bad_*.json
# 经 apply_seed_config() 显式装载为一等公民；此处 SEED_* 仅作兜底并写清。
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


def apply_seed_config(path):
    """把 seed_config JSON 显式装载为全局种子点（次优起点的一等公民接口）。

    JSON 字段：
      best_pre_post : 4 个 FFE 旁瓣
      best_gdc      : Tx CTLE peaking gain (dB)
      best_gdc2     : Tx CTLE LF shelf gain (dB)
      best_u_gain 或 best_gain : gain 覆盖（可选，二者给一）

    返回 gain 覆盖值（None 表示未覆盖，用模块默认 SEED_GAIN）。
    未提供 seed_config 时，SEED_TAPS/SEED_GDC/SEED_GDC2/SEED_GAIN 为模块级兜底。
    """
    import json
    global SEED_TAPS, SEED_GDC, SEED_GDC2, SEED_GAIN, SEED_GAIN_U
    with open(path, 'r', encoding='utf-8') as f:
        sc = json.load(f)
    pre_post = np.asarray(sc['best_pre_post'], dtype=float)
    SEED_TAPS = construct_taps(pre_post, FFE_PRE).copy()
    SEED_GDC = float(sc['best_gdc'])
    SEED_GDC2 = float(sc['best_gdc2'])
    if 'best_u_gain' in sc:
        gain = float(gain_from_u(float(sc['best_u_gain'])))
    elif 'best_gain' in sc:
        gain = float(sc['best_gain'])
    else:
        gain = None
    if gain is not None:
        SEED_GAIN = gain
        SEED_GAIN_U = u_from_gain(gain)
    return gain


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


def _analytic_gain_grad(model_a, probe_feat):
    """gain 维解析梯度 ∂A/∂u_gain（零试探态）。

    Model A 的 8 维探针 = [绝对标定 7-tap FIR, drive_rms]；driver_gain 是 Tx 链最后的
    标量乘子，故全部 8 个特征都严格 ∝ gain。gain = g0·10^u => ∂feat_j/∂u = ln(10)·feat_j。

        ∂A/∂u_gain = Σ_j (∂A/∂feat_j)·(∂feat_j/∂u) = ln(10)·Σ_j (∂A/∂feat_j)·feat_j

    其中 ∂A/∂feat_j 由 WhiteBoxRidge.grad() 解析给出（输入为标准化特征，需除以 sd 换算回
    原始量纲）。零 ±ε 扰动、零真实 BER，只消耗当前落点的探针特征。
    """
    x = np.asarray(probe_feat, dtype=float).reshape(1, -1)
    mu = np.asarray(getattr(model_a, 'mu', np.zeros(x.shape[1])), dtype=float)
    sd = np.asarray(getattr(model_a, 'sd', np.ones(x.shape[1])), dtype=float)
    xn = (x - mu) / sd
    gn = np.asarray(model_a.grad(xn), dtype=float)   # ∂pred/∂xn (1, d)
    g_raw = (gn / sd).ravel()                         # ∂pred/∂raw_feat (d,)
    return np.log(10.0) * float(np.sum(g_raw * x.ravel()))


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


def _grad_a_chain(model_a, config, x, ffe_pre, eps=0.01, eps_u=0.05, record_probe_ber=False, dims=None):
    """链式梯度：∂A/∂x = [∂A/∂shape(6), ∂A/∂u_gain]；dims 给定则只算指定维（其余维 g=0）。

    x = [4 FFE 旁瓣, gDC, gDC2, u_gain]（7 维）。
    shape 维：±eps 扰动参数 -> 重算探针 -> 查 A -> 中心差分（gain 固定）。
    gain 维：±eps_u 扰动 u_gain -> 换算线性 gain -> 重算探针（只有 drive_rms 变）-> 查 A。

    record_probe_ber=True 时，每个 ±ε 试探步（真实在线系统里为拿探针所做的参数微扰状态）
    同步做一次端到端 MLSE BER 实测并随梯度一并返回——仅记账，不参与方向决策。
    返回 (g, probe_iter)；probe_iter 每个元素为 {'param','sign','x','taps','gdc','gdc2',
    'gain','gain_ratio','u_gain','real_logber','real_mlse'}。
    """
    x = np.asarray(x, dtype=float)
    g = np.zeros_like(x)
    taps = construct_taps(x[:N_SIDE], ffe_pre)
    gdc = float(x[N_SIDE])
    gdc2 = float(x[N_SIDE + 1])
    gain = gain_from_u(float(x[N_SIDE + 2]))
    eps_vec = np.array([eps] * N_SIDE + [eps * 10] * 2 + [eps_u])
    probe_iter = []

    for i in (range(len(x)) if dims is None else dims):
        xp = x.copy(); xp[i] += eps_vec[i]
        xm = x.copy(); xm[i] -= eps_vec[i]
        if i < N_SIDE + 2:
            taps_p = construct_taps(xp[:N_SIDE], ffe_pre)
            taps_m = construct_taps(xm[:N_SIDE], ffe_pre)
            gdc_p = float(xp[N_SIDE]); gdc2_p = float(xp[N_SIDE + 1])
            gdc_m = float(xm[N_SIDE]); gdc2_m = float(xm[N_SIDE + 1])
            gain_p = gain_m = gain
        else:
            taps_p = taps_m = taps
            gdc_p = gdc_m = gdc; gdc2_p = gdc2_m = gdc2
            gain_p = gain_from_u(float(xp[N_SIDE + 2]))
            gain_m = gain_from_u(float(xm[N_SIDE + 2]))
        probe_p = _probe_features(config, taps_p, gdc_p, gdc2_p, gain_p)
        probe_m = _probe_features(config, taps_m, gdc_m, gdc2_m, gain_m)
        ap = _predict_a_probe(model_a, probe_p)
        am = _predict_a_probe(model_a, probe_m)
        g[i] = (ap - am) / (2.0 * eps_vec[i])
        if record_probe_ber:
            lb_p, ber_p = _physical_eval(config, taps_p, gdc_p, gdc2_p, gain_p)
            lb_m, ber_m = _physical_eval(config, taps_m, gdc_m, gdc2_m, gain_m)
            probe_iter.append({
                'param': i, 'sign': +1, 'x': np.asarray(xp),
                'taps': np.asarray(taps_p), 'gdc': gdc_p, 'gdc2': gdc2_p,
                'gain': gain_p, 'gain_ratio': gain_p / DRIVER_GAIN_NOMINAL,
                'u_gain': float(xp[N_SIDE + 2]),
                'real_logber': lb_p, 'real_mlse': ber_p,
            })
            probe_iter.append({
                'param': i, 'sign': -1, 'x': np.asarray(xm),
                'taps': np.asarray(taps_m), 'gdc': gdc_m, 'gdc2': gdc2_m,
                'gain': gain_m, 'gain_ratio': gain_m / DRIVER_GAIN_NOMINAL,
                'u_gain': float(xm[N_SIDE + 2]),
                'real_logber': lb_m, 'real_mlse': ber_m,
            })
    return g, probe_iter


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
        g, probe_iter = _grad_a_chain(model_a, config, x, ffe_pre, record_probe_ber=True)
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
                'probes': probe_iter,
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
            'probes': probe_iter,
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
        g, probe_iter = _grad_a_chain(model_a, config, x, ffe_pre, record_probe_ber=True)
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
                'probes': probe_iter,
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
            'probes': probe_iter,
            'grad_norm': float(np.linalg.norm(g)), 'stop_reason': '',
        })

        print(f"[Aonly] gd {step + 1}/{n_steps} | ModelA {10.0 ** pred_a:.2e} "
              f"| real {real_mlse:.2e} | gain x{gain_new / DRIVER_GAIN_NOMINAL:.3f} "
              f"| u_gain {float(x_new[N_SIDE + 2]):+.3f} | gDC {gdc_new:+.2f} | gDC2 {gdc2_new:+.2f}")

        if np.linalg.norm(x_new - x) < 1e-6:
            break
        x = x_new

    return trace


# ---------------------------------------------------------------------------
# 在线调优：割线（secant / Broyden "good"）梯度维持 + gain 维解析梯度。
#
#   核心约束（在线系统的物理事实）：Model A 的输入是物理探针，而拿到探针 = 已经把
#   参数真应用到系统 = 真实改变该时刻链路 BER。所以除了第 0 步获取初始梯度，后续
#   每一步绝不为了测梯度把 live 链路摆进任何 x±ε 过渡态——每步只短暂停留在「已落地
#   的工作点」，梯度只能用历史落点的结果来维持。
#
#   梯度来源（三件事缺一不可）：
#     - gain 维：解析 ∂A/∂u_gain = ln(10)·Σ_j (∂A/∂feat_j)·feat_j（8 维探针特征全部 ∝ gain），
#       每步用当前落点探针现算，零试探、永不陈旧。
#     - shape 维（4 FFE + 2 CTLE）：第 0 步一次中心差分初始化（唯一一轮 12 个 ±ε 试探态），
#       此后每步用「历史落点位移 + Model A 预测变化」做割线更新（免费算术）。
#       割线方程剔除 gain 的贡献：dA_shape = dA - g_gain·dx_gain。
#     - Model B 输入 = 新参数；在新参数 apply 到系统之前就能预测，用于拒绝候选。
#   全程无周期刷新、无 B 全拒刷新：live 链路步间只落一个点，绝不进入 x±ε 过渡态。
# ---------------------------------------------------------------------------



def _secant_direction(g):
    """把梯度估计转成组归一化方向（与 _stage2_descent 同口径）。返回 (direction, active)。"""
    gs = g * STEP_SPAN
    direction = np.zeros_like(g)
    active = []
    for sl, name in zip(GROUP_SLICES, GROUP_NAMES):
        nrm = float(np.linalg.norm(gs[sl]))
        if nrm >= GROUP_GATE:
            direction[sl] = gs[sl] / nrm
            active.append(name)
    return direction, active


def _secant_line_search(model_b, config, x, direction, tr_bounds, alpha, ffe_pre, allowed_ber):
    """回溯线搜索 + Model B 先验拒绝（参数域，无真实 BER）。返回 x_new 或 None。"""
    alpha_k = alpha
    for _ in range(20):
        x_cand = np.clip(x - alpha_k * STEP_SPAN * direction,
                         tr_bounds[:, 0], tr_bounds[:, 1])
        if np.linalg.norm(x_cand - x) < 1e-9:
            break
        taps_c = construct_taps(x_cand[:N_SIDE], ffe_pre)
        gdc_c = float(x_cand[N_SIDE]); gdc2_c = float(x_cand[N_SIDE + 1])
        gain_c = gain_from_u(float(x_cand[N_SIDE + 2]))
        rms_c = _measure_drive_rms(config, taps_c, gdc_c, gdc2_c, gain_c)
        if _predict_b_params(model_b, x_cand[:N_SIDE + 2], rms_c) <= np.log10(allowed_ber):
            return x_cand
        alpha_k *= 0.5
    return None


def _stage2_descent_secant(config, model_a, model_b, x0, ffe_pre, n_steps, lr):
    """在线调优：第 0 步 shape 维中心差分初始化 + gain 维解析梯度；此后零试探态。

    满足的核心约束：除第 0 步获取初始梯度外，live 链路每一步只短暂停留在「已落地的工作点」，
    绝不为了测梯度进入任何 x±ε 过渡态。梯度来源（详见模块头注释）：

      - gain 维：解析 ∂A/∂u_gain（零试探、每步现算、永不陈旧）。
      - shape 维：第 0 步一次中心差分初始化（唯一一轮 12 个 ±ε 试探态），此后每步
        割线更新，割线方程剔除 gain 贡献（dA_shape = dA - g_gain·dx_gain）。

    搜索空间 / 信任域 / B 拦截 / 红线 / 边际门控与 _stage2_descent 一致；真实 BER 仅记账。
    """
    x = np.array(x0, dtype=float)
    tr_bounds = _bounds(x)
    span = STEP_SPAN.copy()

    taps0 = construct_taps(x[:N_SIDE], ffe_pre)
    gdc0 = float(x[N_SIDE]); gdc2 = float(x[N_SIDE + 1])
    gain0 = gain_from_u(float(x[N_SIDE + 2]))
    rms0 = _measure_drive_rms(config, taps0, gdc0, gdc2, gain0)
    seed_pred_b = _predict_b_params(model_b, x[:N_SIDE + 2], rms0)
    best_pred_b = seed_pred_b
    allowed_ber = (10.0 ** best_pred_b) * (1.0 + MAX_DEGRADE_FRAC)

    rho = float(getattr(model_b, 'local_spacing_', 0.0) or 0.0)
    sd_vec = np.asarray(getattr(model_b, 'sd', np.ones(7)), dtype=float)[:6]
    mu_vec = np.asarray(getattr(model_b, 'mu', np.zeros(7)), dtype=float)[:6]
    z0 = (x[:6] - mu_vec) / sd_vec
    path_limit = TRUST_PATH_K * rho if rho > 0 else None

    # 第 0 步：shape 维中心差分（唯一一轮 12 个 ±ε 试探态）；gain 维解析（0 试探）。
    g, probe_iter0 = _grad_a_chain(model_a, config, x, ffe_pre, record_probe_ber=True, dims=range(N_SIDE + 2))
    probe0 = _probe_features(config, taps0, gdc0, gdc2, gain0)
    g[N_SIDE + 2] = _analytic_gain_grad(model_a, probe0)
    a_prev = _predict_a_probe(model_a, probe0)

    trace = []
    for step in range(n_steps):
        # 只有第 0 步携带初始化那轮的 12 个 ±ε 试探态（透明记账）；此后每步 0 试探态。
        step_probes = probe_iter0 if step == 0 else []

        direction, active = _secant_direction(g)
        if not active:
            print(f'[Secant] stop: 三组梯度均低于门控 {GROUP_GATE:g}（step {step}）')
            break

        alpha = lr * (ALPHA_DECAY ** step)
        x_new = _secant_line_search(model_b, config, x, direction, tr_bounds, alpha, ffe_pre, allowed_ber)
        if x_new is None:
            print(f'[Secant] stop: 无候选点通过 Model B 拦截（step {step}）')
            break

        if path_limit is not None:
            z_new = (x_new[:6] - mu_vec) / sd_vec
            if float(np.linalg.norm(z_new - z0)) > path_limit:
                print(f'[Secant] stop: 轨迹位移超过信任域（step {step}）')
                break

        taps_new = construct_taps(x_new[:N_SIDE], ffe_pre)
        gdc_new = float(x_new[N_SIDE]); gdc2_new = float(x_new[N_SIDE + 1])
        gain_new = gain_from_u(float(x_new[N_SIDE + 2]))
        probe_new = _probe_features(config, taps_new, gdc_new, gdc2_new, gain_new)
        pred_a = _predict_a_probe(model_a, probe_new)
        rms_actual = _measure_drive_rms(config, taps_new, gdc_new, gdc2_new, gain_new)
        pred_b = _predict_b_params(model_b, x_new[:N_SIDE + 2], rms_actual)
        real_logber, real_mlse = _physical_eval(config, taps_new, gdc_new, gdc2_new, gain_new)

        # gain 维：解析梯度（每步现算，零试探、永不陈旧）
        g[N_SIDE + 2] = _analytic_gain_grad(model_a, probe_new)
        # shape 维：割线更新（只用历史落点；剔除 gain 的贡献）
        dx = x_new - x
        dA = pred_a - a_prev
        dA_shape = dA - g[N_SIDE + 2] * dx[N_SIDE + 2]
        dx_shape = dx[:N_SIDE + 2]
        dx_norm2 = float(np.dot(dx_shape, dx_shape))
        if dx_norm2 > 1e-18:
            g[:N_SIDE + 2] = g[:N_SIDE + 2] + ((dA_shape - float(np.dot(g[:N_SIDE + 2], dx_shape))) / dx_norm2) * dx_shape

        if pred_b < best_pred_b:
            best_pred_b = pred_b
            allowed_ber = (10.0 ** best_pred_b) * (1.0 + MAX_DEGRADE_FRAC)

        # 边际改善门控（step 0 不判，避免首步误停）
        if step > 0 and (a_prev - pred_a) < MIN_GAIN_DEX:
            trace.append({
                'step': step, 'x': x_new, 'taps': taps_new,
                'gdc': gdc_new, 'gdc2': gdc2_new, 'gain': gain_new,
                'gain_ratio': gain_new / DRIVER_GAIN_NOMINAL,
                'u_gain': float(x_new[N_SIDE + 2]),
                'drive_rms': rms_actual,
                'pred_a': pred_a, 'pred_b': pred_b,
                'pred_b_ber': 10.0 ** pred_b, 'allowed_ber': allowed_ber,
                'real_logber': real_logber, 'real_mlse': real_mlse,
                'probes': step_probes,
                'grad_norm': float(np.linalg.norm(g)), 'stop_reason': 'marginal_gain',
            })
            print(f"[Secant] stop: marginal predicted gain "
                  f"({a_prev - pred_a:+.4f} < {MIN_GAIN_DEX}) at step {step}")
            break

        trace.append({
            'step': step, 'x': x_new, 'taps': taps_new,
            'gdc': gdc_new, 'gdc2': gdc2_new, 'gain': gain_new,
            'gain_ratio': gain_new / DRIVER_GAIN_NOMINAL,
            'u_gain': float(x_new[N_SIDE + 2]),
            'drive_rms': rms_actual,
            'pred_a': pred_a, 'pred_b': pred_b,
            'pred_b_ber': 10.0 ** pred_b, 'allowed_ber': allowed_ber,
            'real_logber': real_logber, 'real_mlse': real_mlse,
            'probes': step_probes,
            'grad_norm': float(np.linalg.norm(g)), 'stop_reason': '',
        })

        print(f"[Secant] gd {step + 1}/{n_steps} | ModelA {10.0 ** pred_a:.2e} "
              f"| real {real_mlse:.2e} | gain x{gain_new / DRIVER_GAIN_NOMINAL:.3f} "
              f"| u_gain {float(x_new[N_SIDE + 2]):+.3f} | gDC {gdc_new:+.2f} "
              f"| gDC2 {gdc2_new:+.2f} | 组 {active}")

        if np.linalg.norm(x_new - x) < 1e-6:
            break
        a_prev = pred_a
        x = x_new

    return trace


# ---------------------------------------------------------------------------
# DDPS 现役接口关系（三段式流水线，无单一 run_ddps 入口）：
#   1) dataset_generator.py  生成环境锚定邻域数据集；
#   2) train_surrogates.train()  训练 A/B 双代理（固化模型）；
#   3) test_generalization.py  在线寻优泛化测试。
# 历史单一入口 run_ddps() 已删除；optimizers/* 里的旧优化器不再引用 DDPS 入口。
# ---------------------------------------------------------------------------