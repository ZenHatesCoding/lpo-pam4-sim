import numpy as np
from main import run_sim
from tx_channel_extract import extract_tx_features
from channel_imdd import GAIN_LOG10_MIN, GAIN_LOG10_MAX, DRIVER_GAIN_NOMINAL

# ============================================================
# DDPS (Data-Driven Physical Surrogate) 数据驱动物理代理优化器
#
# 架构（两阶段）：
#   Stage 1（离线，冻结）：在基线环境生成锚定邻域数据集 -> 训练白盒 Ridge 方向代理：
#       Model A：发端 8 维探针（7-tap Tx FIR + drive_rms）-> log10(BER_MLSE)
#       Stage 1 的采样/训练位于 dataset_generator.py 与 train_surrogates.py；
#       本文件提供 Stage-2 搜索空间、物理评估与在线寻优。
#
#   Stage 2（在线寻优）：8 维（5 个 Tx FFE 抽头 + gDC + gDC2 + u_gain）链式梯度下降。
#       - 方向 = Model A 的链式梯度（扰动参数 -> 重算探针 -> 查 A -> 中心差分）。
#       - 抽头维 5 个全部自由、**无边界**（无 ±0.3 盒、无派生主抽头、无 Σ|旁瓣| 上限）；
#         只有 CTLE / gain 保留各自的物理量程。
#       - gain 维走解析梯度：8 维探针特征全部严格 ∝ gain，零微扰态、每步现算、永不陈旧。
#       - 形状维（5 抽头 + gDC + gDC2）的梯度刷新方式由 grad_mode 决定：
#           full   每步全量中心差分（7 维 × ±ε = 14 个微扰态/步）
#           rotate 每步轮转刷新 k 个维（2k 个微扰态/步），其余维沿用上一轮测到的值
#           secant 只在第 0 步测一轮，此后 Broyden 秩-1 更新维持（此后 0 微扰态/步）
#       - 在线决策只用 Model A。真实 BER_MLSE 只记账、不回传决策。
#
#   参照方案（_stage2_descent_direct）：端到端 BER 直接梯度下降。假设存在回传通道、
#       端到端 BER 可得，则不再需要 Model A——目标 = 真实 log10(BER)。
#       用于回答"如果能回传端到端 BER，直接梯度下降能达到什么水平"。
#
# 在线代价的口径（不可违反）：只要有 ±ε 微扰态被下发到链路，它就是一次真实的性能
# 损失，必须全量做真实 BER 实测并计入结果（AGENTS.md 物理代价忠实记录）。所以 full
# 模式每步 14 次真实评估不是"记账开销"，而是这个模式的真实代价。
#
# 白盒约束：不依赖任何第三方现成算法；Ridge 闭式解、梯度、步长规则均手写。
# ============================================================

# ---------------------------------------------------------------------------
# Tx FFE：**5 抽头**，T-spaced。抽头数由发端架构锁死（5），但抽头值全部自由。
#
# 两套口径必须分清：
#   Stage 1（数据集采样，冻结）——4 个旁瓣为自由变量、主抽头由 1-Σ|旁瓣| 派生，
#     见 construct_taps()。数据集与 Model A 已按这套口径生成并冻结，不再改动。
#   Stage 2（在线搜索，现役）——5 个抽头全部是搜索维，无派生、无边界。
# ---------------------------------------------------------------------------
N_FFE_TAPS = 5
FFE_PRE = 2                    # 主抽头位置（2 个前游标 + 2 个后游标）
N_SIDE = N_FFE_TAPS - 1        # 4：Stage-1 采样口径的旁瓣个数（冻结口径，勿动）
N_TAP = N_FFE_TAPS             # 5：Stage-2 搜索口径的抽头维个数（全自由、无边界）
N_SHAPE = N_TAP + 2            # 7：5 抽头 + gDC + gDC2
N_DIM = N_SHAPE + 1            # 8：+ u_gain

# CTLE 物理量程（peaking 语义）：
#   g_dc  = 高频 peaking gain (dB)，直流增益恒 0 dB。≥0 才有意义（负值=额外衰减高频）。
#   g_dc2 = LF shelf gain (dB)。
CTLE_GDC_MIN = 0.0
CTLE_GDC_MAX = 12.0
CTLE_GDC2_MIN = 0.0
CTLE_GDC2_MAX = 4.0
PEAK_SUM_LIMIT = 0.8          # 仅 Stage-1 采样口径使用（construct_taps），与在线搜索无关

# ---------------------------------------------------------------------------
# Stage 2 步长 / 门控
#   抽头维没有信任盒：边界会把次优起点的可用范围截成单侧半宽，所以抽头不设边界。
#   TRUST_FFE 退化为"步长尺度"——只决定每步走多远，不限制能走到哪里。
# ---------------------------------------------------------------------------
TRUST_FFE = 0.10              # 抽头维步长尺度（满箱宽度 = 2×该值）
TRUST_CTLE = 3.0              # CTLE 步长尺度（dB）
GAIN_TRUST = 0.30             # gain 步长尺度（log10 dex）
GD_LR = 0.05                  # 初始步长（相对各维步长尺度的比例，随 step 以 ALPHA_DECAY 衰减）
ALPHA_DECAY = 0.97            # 步长衰减：越走越稳（末期用于收敛落点）
GROUP_GATE = 1e-3             # 组梯度门控：某组"每走满整箱"的预测收益低于该值（dex）就冻结该组
MIN_GAIN_DEX = 0.01           # direct 参照方案的边际改善停止门控（代理方案固定步数、不早停）

# ---------------------------------------------------------------------------
# 搜索空间：x = [5 个 Tx FFE 抽头, gDC, gDC2, u_gain]（8 维）
#   u_gain = log10(gain / DRIVER_GAIN_NOMINAL)，对数参数化让"增益步长"与量级无关。
# 各维步长按各自步长尺度的比例走（分组归一化），避免某一组量纲吃掉其它组。
# ---------------------------------------------------------------------------
EPS_VEC = np.array([0.01] * N_TAP + [0.1] * 2 + [0.05])   # 中心差分步长（抽头 / CTLE dB / gain dex）
ROTATE_K = 2                  # rotate 模式每步刷新的形状维个数（7 维 / 2 = 每 4 步刷满一轮）

# 各维"满箱宽度"（步长尺度）：抽头 = 2×TRUST_FFE，CTLE = 2×TRUST_CTLE，gain = 2×GAIN_TRUST。
STEP_SPAN = np.array([2.0 * TRUST_FFE] * N_TAP + [2.0 * TRUST_CTLE] * 2
                     + [2.0 * GAIN_TRUST])
# 三组自由度（用于分组归一化步长 + 分组梯度门控）
GROUP_SLICES = (slice(0, N_TAP), slice(N_TAP, N_TAP + 2), slice(N_TAP + 2, N_TAP + 3))
GROUP_NAMES = ('FFE', 'CTLE', 'driver_gain')

# 评估协议：仿真种子序列。多 seed 时对 log10 BER 取均值，抑制"单一实现"造成的
# BER 估计噪声（比只加长块长更可控，且能同时给出点内标准差）。
SIM_SEEDS = (42,)


def set_sim_seeds(seeds):
    """设置评估用的仿真种子序列（数据集 / 在线测试 / 复核共用同一口径）。"""
    global SIM_SEEDS
    SIM_SEEDS = tuple(int(s) for s in seeds)
    return SIM_SEEDS


# 兜底种子（未提供 --seed-config 时使用）：名义工程种子，不是次优演示起点。
# 次优演示起点（形状 + CTLE + gain 全给定）通过 result/seed_config_bad_*.json
# 经 apply_seed_config() 显式装载为一等公民；此处 SEED_* 仅作兜底并写清。
SEED_TAPS = np.array([-0.034, -0.2987, 0.6091, 0.0, 0.0582])   # 5 抽头：主抽头位置 FFE_PRE=2
SEED_GDC = 6.0                  # Tx CTLE peaking seed: moderate 6 dB (Rx adds another fixed 6 dB)
SEED_GDC2 = 2.0                 # Tx CTLE LF shelf seed: 2 dB
SEED_GAIN_U = 0.0             # u = log10(gain / DRIVER_GAIN_NOMINAL)，种子即标定值（0.0）
SEED_GAIN = DRIVER_GAIN_NOMINAL * (10.0 ** SEED_GAIN_U)
GAIN_MIN = DRIVER_GAIN_NOMINAL * (10.0 ** GAIN_LOG10_MIN)   # 实际增益下界
GAIN_MAX = DRIVER_GAIN_NOMINAL * (10.0 ** GAIN_LOG10_MAX)   # 实际增益上界

# 训练数据 gain 采样带（宽口径）：覆盖全部 15 用例 per-case 最优 gain（×0.30~×0.91）
# 及其在线步长尺度，避免模型在 drive_rms 轴上对高损用例外推。
# 采样带 = ×0.20~×1.26（u ∈ [-0.70, +0.10]），在 u 空间均匀。
GAIN_SAMPLE_U_LO = -0.70
GAIN_SAMPLE_U_HI = 0.10


def gain_from_u(u):
    """u = log10(g / g0) -> 实际线性增益。"""
    return float(DRIVER_GAIN_NOMINAL * (10.0 ** float(u)))


def u_from_gain(gain):
    """实际线性增益 -> u = log10(g / g0)。"""
    return float(np.log10(max(float(gain), 1e-12) / DRIVER_GAIN_NOMINAL))


def taps_of(x):
    """Stage-2 搜索向量 -> 5 个 Tx FFE 抽头（全自由、无派生、无边界）。"""
    return np.asarray(x[:N_TAP], dtype=float).copy()


# ---------------------------------------------------------------------------
# Stage-1（数据集采样）口径：4 个旁瓣 -> 5-tap FFE（主抽头由 1-Σ|旁瓣| 派生）。
# 冻结口径，保留给 dataset_generator.py 复现数据集；Stage-2 搜索不走这条参数化。
# ---------------------------------------------------------------------------
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
      best_taps     : 5 个 Tx FFE 抽头（Stage-2 搜索口径，优先）
      best_pre_post : 4 个 FFE 旁瓣（旧口径；无 best_taps 时按 Stage-1 派生规则换算）
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
    if 'best_taps' in sc:
        SEED_TAPS = np.asarray(sc['best_taps'], dtype=float).copy()
    else:
        SEED_TAPS = construct_taps(np.asarray(sc['best_pre_post'], dtype=float), FFE_PRE)
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
    """gain 维解析梯度 ∂A/∂u_gain（零微扰态）。

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


def _search_bounds():
    """搜索边界：**抽头维无边界**；只有 CTLE / gain 用各自物理量程。

    抽头不设信任盒——边界会把次优起点的可用范围截成单侧半宽（实测 15/15 用例的最低
    抽头都被钉在盒壁上、只能单向移动）。步长尺度由 STEP_SPAN 单独承担，与边界无关。
    """
    return np.array([(-np.inf, np.inf)] * N_TAP
                    + [(CTLE_GDC_MIN, CTLE_GDC_MAX), (CTLE_GDC2_MIN, CTLE_GDC2_MAX),
                       (GAIN_LOG10_MIN, GAIN_LOG10_MAX)])


def _grad_a_chain(model_a, config, x, dims=None, record_probe_ber=False):
    """链式梯度：∂A/∂x（形状 7 维）；dims 给定则只算这些维，其余维返回 0。

    x = [5 个 FFE 抽头, gDC, gDC2, u_gain]（8 维）。
    形状维：±eps 扰动参数 -> 重算探针 -> 查 A -> 中心差分（gain 固定）。
    gain 维不在这里算——它走解析梯度 _analytic_gain_grad（零微扰态）。

    record_probe_ber=True 时，每个 ±ε 微扰步（真实在线系统里为拿探针所做的参数微扰状态）
    同步做一次端到端 MLSE BER 实测并随梯度一并返回——那是真实的在线性能代价，必须全量
    记账。返回 (g, probe_iter)；probe_iter 每个元素为 {'param','sign','x','taps','gdc',
    'gdc2','gain','gain_ratio','u_gain','real_logber','real_mlse'}。
    """
    x = np.asarray(x, dtype=float)
    g = np.zeros(N_DIM)
    gdc = float(x[N_TAP])
    gdc2 = float(x[N_TAP + 1])
    gain = gain_from_u(float(x[N_TAP + 2]))
    probe_iter = []

    for i in (range(N_SHAPE) if dims is None else dims):
        xp = x.copy(); xp[i] += EPS_VEC[i]
        xm = x.copy(); xm[i] -= EPS_VEC[i]
        if i < N_TAP:
            taps_p = taps_of(xp); taps_m = taps_of(xm)
            gdc_p = gdc_m = gdc
            gdc2_p = gdc2_m = gdc2
            gain_p = gain_m = gain
        else:
            taps_p = taps_m = taps_of(x)
            gdc_p = float(xp[N_TAP]); gdc2_p = float(xp[N_TAP + 1])
            gdc_m = float(xm[N_TAP]); gdc2_m = float(xm[N_TAP + 1])
            gain_p = gain_m = gain
        probe_p = _probe_features(config, taps_p, gdc_p, gdc2_p, gain_p)
        probe_m = _probe_features(config, taps_m, gdc_m, gdc2_m, gain_m)
        ap = _predict_a_probe(model_a, probe_p)
        am = _predict_a_probe(model_a, probe_m)
        g[i] = (ap - am) / (2.0 * EPS_VEC[i])
        if record_probe_ber:
            lb_p, ber_p = _physical_eval(config, taps_p, gdc_p, gdc2_p, gain_p)
            lb_m, ber_m = _physical_eval(config, taps_m, gdc_m, gdc2_m, gain_m)
            probe_iter.append({
                'param': i, 'sign': +1, 'x': np.asarray(xp),
                'taps': np.asarray(taps_p), 'gdc': gdc_p, 'gdc2': gdc2_p,
                'gain': gain_p, 'gain_ratio': gain_p / DRIVER_GAIN_NOMINAL,
                'u_gain': float(xp[N_TAP + 2]),
                'real_logber': lb_p, 'real_mlse': ber_p,
            })
            probe_iter.append({
                'param': i, 'sign': -1, 'x': np.asarray(xm),
                'taps': np.asarray(taps_m), 'gdc': gdc_m, 'gdc2': gdc2_m,
                'gain': gain_m, 'gain_ratio': gain_m / DRIVER_GAIN_NOMINAL,
                'u_gain': float(xm[N_TAP + 2]),
                'real_logber': lb_m, 'real_mlse': ber_m,
            })
    return g, probe_iter


def _group_direction(g):
    """把梯度估计转成组归一化方向（三组各自单位化）。返回 (direction, active)。

    抽头维无边界，所以这里只做方向，不做投影；步长尺度由 STEP_SPAN 承担。
    """
    gs = g * STEP_SPAN
    direction = np.zeros_like(g)
    active = []
    for sl, name in zip(GROUP_SLICES, GROUP_NAMES):
        nrm = float(np.linalg.norm(gs[sl]))
        if nrm >= GROUP_GATE:
            direction[sl] = gs[sl] / nrm
            active.append(name)
    return direction, active


def _stage2_descent_proxy(config, model_a, x0, n_steps, lr, grad_mode='full', rotate_k=ROTATE_K):
    """在线寻优：8 维链式梯度下降，在线决策只用 Model A（无 Model B、无红线、无否决）。

    grad_mode 决定形状维（5 抽头 + gDC + gDC2）的梯度刷新方式：
      full   每步 7 维全量中心差分（14 个 ±ε 微扰态/步）
      rotate 第 0 步全量测一轮，此后每步轮转刷新 rotate_k 个维（2·rotate_k 个微扰态/步），
             其余维沿用上一轮测到的值（rotate_k=2 时 4 步就把 7 个维各刷新一遍，此后循环）
      secant 只在第 0 步全量测一轮，此后 Broyden 秩-1 更新维持（此后 0 微扰态/步）

    三种模式都从同一个"第 0 步全量梯度"出发，差别只在之后怎么让方向更新。gain 维三种
    模式都走解析梯度（零微扰态）。固定 n_steps 步、不早停（步数是在线调优的给定预算）。
    真实 BER_MLSE 只记账、不回传决策。
    """
    if grad_mode not in ('full', 'rotate', 'secant'):
        raise ValueError(f'grad_mode 必须是 full/rotate/secant，收到 {grad_mode!r}')
    x = np.asarray(x0, dtype=float).copy()
    tr_bounds = _search_bounds()
    span = STEP_SPAN.copy()

    taps0 = taps_of(x)
    gdc0 = float(x[N_TAP]); gdc2_0 = float(x[N_TAP + 1])
    gain0 = gain_from_u(float(x[N_TAP + 2]))
    probe0 = _probe_features(config, taps0, gdc0, gdc2_0, gain0)
    a_prev = _predict_a_probe(model_a, probe0)

    g = np.zeros(N_DIM)
    g[N_TAP + 2] = _analytic_gain_grad(model_a, probe0)

    trace = []
    for step in range(n_steps):
        # ---- 形状维梯度刷新（每种模式的在线代价都写在这里）----
        if step == 0:
            gs, step_probes = _grad_a_chain(model_a, config, x, dims=range(N_SHAPE),
                                            record_probe_ber=True)
            g[:N_SHAPE] = gs[:N_SHAPE]
            refreshed = list(range(N_SHAPE))
        elif grad_mode == 'full':
            gs, step_probes = _grad_a_chain(model_a, config, x, dims=range(N_SHAPE),
                                            record_probe_ber=True)
            g[:N_SHAPE] = gs[:N_SHAPE]
            refreshed = list(range(N_SHAPE))
        elif grad_mode == 'rotate':
            refreshed = [int((step * rotate_k + j) % N_SHAPE) for j in range(rotate_k)]
            gs, step_probes = _grad_a_chain(model_a, config, x, dims=refreshed,
                                            record_probe_ber=True)
            for j in refreshed:
                g[j] = gs[j]
        else:  # secant：第 0 步之后不再为梯度制造任何微扰态
            step_probes = []
            refreshed = []

        direction, active = _group_direction(g)
        if not active:
            print(f'[Stage2] stop: 三组梯度均低于门控 {GROUP_GATE:g}（step {step}）')
            break

        alpha = lr * (ALPHA_DECAY ** step)
        x_new = np.clip(x - alpha * span * direction, tr_bounds[:, 0], tr_bounds[:, 1])
        if np.linalg.norm(x_new - x) < 1e-12:
            print(f'[Stage2] stop: 候选点位移为 0（step {step}）')
            break

        taps_new = taps_of(x_new)
        gdc_new = float(x_new[N_TAP]); gdc2_new = float(x_new[N_TAP + 1])
        gain_new = gain_from_u(float(x_new[N_TAP + 2]))
        probe_new = _probe_features(config, taps_new, gdc_new, gdc2_new, gain_new)
        pred_a = _predict_a_probe(model_a, probe_new)
        rms_actual = _measure_drive_rms(config, taps_new, gdc_new, gdc2_new, gain_new)
        real_logber, real_mlse = _physical_eval(config, taps_new, gdc_new, gdc2_new, gain_new)

        # gain 维：解析梯度（每步现算，零微扰态、永不陈旧）
        g[N_TAP + 2] = _analytic_gain_grad(model_a, probe_new)
        # secant：Broyden 秩-1 更新（只用上一步落点的预测差；剔除 gain 贡献）
        if grad_mode == 'secant':
            dx = x_new - x
            dA = pred_a - a_prev
            dA_shape = dA - g[N_TAP + 2] * dx[N_TAP + 2]
            dx_shape = dx[:N_SHAPE]
            dx_norm2 = float(np.dot(dx_shape, dx_shape))
            if dx_norm2 > 1e-18:
                g[:N_SHAPE] = g[:N_SHAPE] + ((dA_shape - float(np.dot(g[:N_SHAPE], dx_shape)))
                                             / dx_norm2) * dx_shape

        trace.append({
            'step': step, 'x': x_new, 'taps': taps_new,
            'gdc': gdc_new, 'gdc2': gdc2_new, 'gain': gain_new,
            'gain_ratio': gain_new / DRIVER_GAIN_NOMINAL,
            'u_gain': float(x_new[N_TAP + 2]),
            'drive_rms': rms_actual,
            'pred_a': pred_a, 'pred_b': 0.0,
            'pred_b_ber': 0.0, 'allowed_ber': 0.0,
            'real_logber': real_logber, 'real_mlse': real_mlse,
            'probes': step_probes,
            'grad': g.copy(), 'refreshed': refreshed,
            'n_probe_states': len(step_probes),
            'grad_norm': float(np.linalg.norm(g)), 'stop_reason': '',
        })

        print(f"[Stage2/{grad_mode}] gd {step + 1}/{n_steps} | ModelA {10.0 ** pred_a:.2e} "
              f"| real {real_mlse:.2e} | gain x{gain_new / DRIVER_GAIN_NOMINAL:.3f} "
              f"| u_gain {float(x_new[N_TAP + 2]):+.3f} | gDC {gdc_new:+.2f} "
              f"| gDC2 {gdc2_new:+.2f} | 本步微扰 {len(step_probes)} | 组 {active}")

        if np.linalg.norm(x_new - x) < 1e-9:
            break
        a_prev = pred_a
        x = x_new

    return trace


def _grad_direct_chain(config, x):
    """direct 梯度初始化：8 维中心差分，目标 = 端到端真实 log10(BER_MLSE)。

    有回传通道时端到端 BER 可得，梯度直接对真实目标做中心差分：
    每维 ±eps 都是一次真实在线评估（共 16 次）。16 个 ±ε 试探态的真实 BER
    逐一记账（与链式/割线的 probe 记录同 schema），用于透明度核验。
    eps 分档与链式一致：抽头 0.01 / CTLE 0.1（dB）/ u_gain 0.05（dex）。
    """
    x = np.asarray(x, dtype=float)
    g = np.zeros(N_DIM)
    probe_iter = []
    for i in range(N_DIM):
        xp = x.copy(); xp[i] += EPS_VEC[i]
        xm = x.copy(); xm[i] -= EPS_VEC[i]
        taps_p = taps_of(xp); taps_m = taps_of(xm)
        gdc_p = float(xp[N_TAP]); gdc2_p = float(xp[N_TAP + 1])
        gain_p = gain_from_u(float(xp[N_TAP + 2]))
        gdc_m = float(xm[N_TAP]); gdc2_m = float(xm[N_TAP + 1])
        gain_m = gain_from_u(float(xm[N_TAP + 2]))
        lb_p, ber_p = _physical_eval(config, taps_p, gdc_p, gdc2_p, gain_p)
        lb_m, ber_m = _physical_eval(config, taps_m, gdc_m, gdc2_m, gain_m)
        g[i] = (lb_p - lb_m) / (2.0 * EPS_VEC[i])
        probe_iter.append({
            'param': i, 'sign': +1, 'x': xp.copy(), 'taps': taps_p,
            'gdc': gdc_p, 'gdc2': gdc2_p, 'gain': gain_p,
            'gain_ratio': gain_p / DRIVER_GAIN_NOMINAL,
            'u_gain': float(xp[N_TAP + 2]),
            'real_logber': lb_p, 'real_mlse': ber_p,
        })
        probe_iter.append({
            'param': i, 'sign': -1, 'x': xm.copy(), 'taps': taps_m,
            'gdc': gdc_m, 'gdc2': gdc2_m, 'gain': gain_m,
            'gain_ratio': gain_m / DRIVER_GAIN_NOMINAL,
            'u_gain': float(xm[N_TAP + 2]),
            'real_logber': lb_m, 'real_mlse': ber_m,
        })
    return g, probe_iter


def _stage2_descent_direct(config, x0, n_steps, lr, f0=None):
    """direct：端到端 BER 直接梯度下降（有回传通道时的参照方案，不用 Model A）。

    回答的问题：如果收端 BER 可以回传（在线调优拿得到端到端 BER），直接对
    真实目标做梯度下降能达到什么水平——以此对照"拿不到 BER、只能靠发端探针
    代理"的代理方案。

    与代理方案同一套下降机制（步长尺度 / 组归一化步长 / 步长衰减 / 组门控）；
    差别只在目标与梯度来源：
      - 目标 = 端到端真实 log10(BER)（回传通道），不是代理预测；
      - 第 0 步 8 维全部中心差分初始化（唯一一轮 16 个 ±ε 试探态；无解析 gain
        梯度可用——那依赖 Model A 的探针比例性）；
      - 此后每步 Broyden 全 8 维割线更新（用真实 Δlog10(BER)，零微扰态）；
    无 Model A/B 代理，因此也没有代理侧的候选否决。
    trace 的 pred_a 列记录当前落点目标值（= real_lb）；pred_b / allowed 恒 0。
    """
    x = np.asarray(x0, dtype=float).copy()
    tr_bounds = _search_bounds()
    span = STEP_SPAN.copy()

    taps0 = taps_of(x)
    gdc0 = float(x[N_TAP]); gdc2_0 = float(x[N_TAP + 1])
    gain0 = gain_from_u(float(x[N_TAP + 2]))
    if f0 is None:
        f_prev, _ = _physical_eval(config, taps0, gdc0, gdc2_0, gain0)
    else:
        f_prev = float(f0)

    # 第 0 步：8 维中心差分初始化（唯一一轮 16 个 ±ε 试探态，全真实评估）
    g, probe_iter0 = _grad_direct_chain(config, x)

    trace = []
    for step in range(n_steps):
        # 只有第 0 步携带初始化那轮的 16 个 ±ε 试探态（透明记账）；此后每步 0 微扰态。
        step_probes = probe_iter0 if step == 0 else []

        direction, active = _group_direction(g)
        if not active:
            print(f'[Direct] stop: 三组梯度均低于门控 {GROUP_GATE:g}（step {step}）')
            break

        alpha = lr * (ALPHA_DECAY ** step)
        x_new = np.clip(x - alpha * span * direction, tr_bounds[:, 0], tr_bounds[:, 1])
        if np.linalg.norm(x_new - x) < 1e-12:
            break

        taps_new = taps_of(x_new)
        gdc_new = float(x_new[N_TAP]); gdc2_new = float(x_new[N_TAP + 1])
        gain_new = gain_from_u(float(x_new[N_TAP + 2]))
        rms_actual = _measure_drive_rms(config, taps_new, gdc_new, gdc2_new, gain_new)
        f_new, real_mlse = _physical_eval(config, taps_new, gdc_new, gdc2_new, gain_new)

        # Broyden 割线更新（全 8 维；用真实 Δlog10(BER)，零微扰态）
        dx = x_new - x
        df = f_new - f_prev
        dx_norm2 = float(np.dot(dx, dx))
        if dx_norm2 > 1e-18:
            g = g + ((df - float(np.dot(g, dx))) / dx_norm2) * dx

        stop_reason = ''
        # 边际改善门控（step 0 不判，避免首步误停；口径 = 真实改善 dex）
        if step > 0 and (f_prev - f_new) < MIN_GAIN_DEX:
            stop_reason = 'marginal_gain'
            print(f"[Direct] stop: marginal real gain "
                  f"({f_prev - f_new:+.4f} < {MIN_GAIN_DEX}) at step {step}")

        trace.append({
            'step': step, 'x': x_new, 'taps': taps_new,
            'gdc': gdc_new, 'gdc2': gdc2_new, 'gain': gain_new,
            'gain_ratio': gain_new / DRIVER_GAIN_NOMINAL,
            'u_gain': float(x_new[N_TAP + 2]),
            'drive_rms': rms_actual,
            'pred_a': f_new, 'pred_b': 0.0,
            'pred_b_ber': 0.0, 'allowed_ber': 0.0,
            'real_logber': f_new, 'real_mlse': real_mlse,
            'probes': step_probes,
            'grad': g.copy(), 'refreshed': (list(range(N_DIM)) if step == 0 else []),
            'n_probe_states': len(step_probes),
            'grad_norm': float(np.linalg.norm(g)), 'stop_reason': stop_reason,
        })

        print(f"[Direct] gd {step + 1}/{n_steps} | real {real_mlse:.2e} "
              f"| gain x{gain_new / DRIVER_GAIN_NOMINAL:.3f} "
              f"| u_gain {float(x_new[N_TAP + 2]):+.3f} | gDC {gdc_new:+.2f} "
              f"| gDC2 {gdc2_new:+.2f} | 组 {active}")

        if stop_reason:
            break
        if np.linalg.norm(x_new - x) < 1e-9:
            break
        f_prev = f_new
        x = x_new

    return trace


# ---------------------------------------------------------------------------
# DDPS 现役接口关系（三段式流水线，无单一 run_ddps 入口）：
#   1) dataset_generator.py  生成环境锚定邻域数据集（Stage-1 采样口径，冻结）；
#   2) train_surrogates.train()  训练 Model A（固化模型）；
#   3) test_generalization.py  在线寻优泛化测试（grad_mode = full / rotate / secant）。
# 历史单一入口 run_ddps() 已删除；optimizers/* 里的旧优化器不再引用 DDPS 入口。
# ---------------------------------------------------------------------------
