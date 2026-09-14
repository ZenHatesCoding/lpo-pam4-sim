import numpy as np
import os
import glob
import pandas as pd
from datetime import datetime
from scipy.stats import qmc, spearmanr
from utils_config import load_config
from main import run_sim
from tx_channel_extract import extract_tx_s21, extract_tx_features
from train_surrogates import train_from_df, WhiteBoxRidge, WhiteBoxGPR

# ============================================================
# DDPS (Data-Driven Physical Surrogate) 数据驱动物理代理优化器
#
# 架构定位（两阶段分工）：
#   Stage 1（离线，模型供给）——
#     目标不是“穷尽地形/找到全局最优”，而是产出两样东西：
#        (1) 一个“不错的起点” x0（例如上一版已能用的工作点）；
#        (2) 两个白盒代理模型：
#            Model A（物理代理）: 发端 7-tap 等效 FIR -> log10(BER)，充当寻优目标
#            Model B（安全代理）: FFE 9-tap + CTLE    -> log10(BER)，充当安全约束
#     在 x0 邻域采样只是为了“训练模型”，采样覆盖不代表完整地图。
#
#   Stage 2（约束梯度下降）——
#     从 x0 出发，在 Model A 上做手写投影梯度下降（白盒），
#     约束：Model B 预测不越安全红线（不掉锁）。
#     **不回传真实 MLSE_BER**（仅记录用于事后验证），
#     直接优化“发端指标”(Model A) 以实现对“收端 MLSE_BER”的等效优化。
#     理想情况下，Stage 2 能沿 Model A 的梯度走到 Stage 1 采样没见过的更优点。
#
#   跨 SNR 迁移：模型在 26.5 dB 训练，能否同样指导 28 dB（及其它 SNR）的寻优，
#     通过“沿 26.5 dB 引导的下降轨迹，在 28 dB 深水回测”来检验。
# ============================================================

# ---------------------------------------------------------------------------
# Tx FFE：**5 抽头**（4 个旁瓣自由变量 + 1 个派生主抽头），T-spaced
#
#   方案数从 11 维降到 7 维（4 FFE 旁瓣 + gDC + gDC2 + u_gain）。定 5 抽头的理由：
#   原 9 抽头里外侧 4 个抽头在整条轨迹上基本停在 0 附近，却同样消耗数据分辨力；
#   7 维下 2001 个样本的局部斜率可分辨性显著好于 11 维（实测见 result/ddps_v4_local_gradient.csv）。
# ---------------------------------------------------------------------------
N_FFE_TAPS = 5
FFE_PRE = 2                    # 主抽头位置（2 个前游标 + 2 个后游标）
N_SIDE = N_FFE_TAPS - 1        # 4 个旁瓣自由变量

FFE_BOUND = 0.3
CTLE_GDC_MIN = -5.0
CTLE_GDC_MAX = 5.0
CTLE_GDC2_MIN = -5.0
CTLE_GDC2_MAX = 5.0
PEAK_SUM_LIMIT = 0.8          # sum(|pre_post|) <= 0.8 -> 主抽头 >= 0.2

# ---------------------------------------------------------------------------
# Model B 拦截判据：**按"变差的百分比"**（不是绝对 BER，也不是 log10 绝对裕度）
#
#   allowed_ber = ber_seed_pred * (1 + MAX_DEGRADE_FRAC)
#   等价于 log10 空间：pred_b <= pred_b_seed + log10(1 + MAX_DEGRADE_FRAC)
#
# 为什么用百分比：代理的绝对标定不可信（欠/过估），但"相对种子变差多少倍"是可比的；
# 百分比阈值天然与 BER 量级无关，跨用例、跨环境都不用重新标定。
# 阈值由 trace 回放标定（见 docs/08）。
# ---------------------------------------------------------------------------
MAX_DEGRADE_FRAC = 0.25       # 允许 Model B 预测相对种子最多变差 25%

TRUST_FFE = 0.10              # Stage 2 信任域半径（FFE，相对起点）：防代理外推越界
TRUST_CTLE = 3.0              # Stage 2 信任域半径（CTLE, dB）
                              # driver_gain 不设"半径"，直接在整个搜索箱内寻优（见下）
GD_LR = 0.05                  # Stage 2 初始步长（相对各维箱宽的比例，随 step 以 ALPHA_DECAY 衰减）
ALPHA_DECAY = 0.97            # 步长衰减：越走越稳（末期用于收敛落点）
TRUST_PATH_K = 1.0            # 轨迹信任域：标准化位移超过 TRUST_PATH_K × ρ 就停
                              # ρ = 训练数据的局部颗粒度（第 32 近邻中位距离，训练时写入
                              # model.local_spacing_）。理由：模型只在“走过约一个数据格”的
                              # 范围内可信；再往外它给出的“还能继续降”没有数据支撑
                              # （实测：预测下降总量 −0.77 dex/用例 vs 实测最优 −0.34 dex）。
GROUP_GATE = 1e-3             # 组梯度门控：某组"每走满整箱"的预测收益低于该值（dex）就冻结该组，
                              # 不沿拟合噪声推动无油水的自由度
MIN_GAIN_DEX = 0.01           # 边际改善门控：Model A 预测每步改善 < 0.01 个 log10 即停

# ---------------------------------------------------------------------------
# v4 搜索空间：x = [8 个 FFE 旁瓣, gDC, gDC2, u_gain]   （11 维）
#
#   * FFE 旁瓣：8 维自由变量（主抽头 = 1 - Σ|旁瓣| 派生）
#   * CTLE：gDC / gDC2 两个直流增益（post-channel 频谱整形）
#   * driver_gain：按 **log10 相对标定值的倍率** 参数化，u = log10(g / g0)
#     —— 对数参数化让"增益步长"与增益量级无关（10~20 dB 插损补偿需要 ~3 倍增益范围）。
#   三组自由度都会被 Model A 的梯度下降直接优化。
# ---------------------------------------------------------------------------
N_DIM = N_SIDE + 3          # 4 旁瓣 + gDC + gDC2 + u_gain = 7
from channel_imdd import GAIN_LOG10_MIN, GAIN_LOG10_MAX, DRIVER_GAIN_NOMINAL   # noqa: E402

# 各维"满箱宽度"：步长按各维自身箱宽的固定比例走 —— 三组自由度的步长各自与其箱宽成比例，
# 因此不会因为 Model A 对某一组的斜率天然偏大/偏小而被"吃掉"（旧版把 11 维梯度整体归一化，
# 结果振幅大的 FFE 维独吞步长，增益/CTLE 几乎不动）。
#   FFE  ：箱宽 = 2 × 信任域半径 = 0.20
#   CTLE ：箱宽 = 2 × 信任域半径 = 6.0 dB
#   gain ：箱宽 = 整个设计箱 = GAIN_LOG10_MAX - GAIN_LOG10_MIN
STEP_SPAN = np.array([2.0 * TRUST_FFE] * N_SIDE + [2.0 * TRUST_CTLE] * 2
                     + [GAIN_LOG10_MAX - GAIN_LOG10_MIN])
# 三组自由度（用于分组归一化步长 + 分组梯度门控）
GROUP_SLICES = (slice(0, N_SIDE), slice(N_SIDE, N_SIDE + 2), slice(N_SIDE + 2, N_SIDE + 3))
GROUP_NAMES = ('FFE', 'CTLE', 'driver_gain')

# 评估协议：仿真种子序列。多 seed 时对 log10 BER 取均值，抑制"单一实现"造成的
# BER 估计噪声（比只加长块长更可控，且能同时给出点内标准差）。
SIM_SEEDS = (42,)


def set_sim_seeds(seeds):
    """设置评估用的仿真种子序列（数据集 / 在线测试 / 深水复核共用同一口径）。"""
    global SIM_SEEDS
    SIM_SEEDS = tuple(int(s) for s in seeds)
    return SIM_SEEDS

# 已知“不错的起点”（种子）：来自两阶段实验的初始次优点
SEED_TAPS = np.array([-0.034, -0.2987, 0.6091, 0.0, 0.0582])   # 5-tap：主抽头 = 1 - Σ|旁瓣|
SEED_GDC = 0.0
SEED_GDC2 = 0.0
SEED_GAIN_U = 0.0             # u = log10(gain / DRIVER_GAIN_NOMINAL)，种子即标定值（0.0）
SEED_GAIN = DRIVER_GAIN_NOMINAL * (10.0 ** SEED_GAIN_U)
GAIN_MIN = DRIVER_GAIN_NOMINAL * (10.0 ** GAIN_LOG10_MIN)   # 便于阅读/打印的实际增益下界
GAIN_MAX = DRIVER_GAIN_NOMINAL * (10.0 ** GAIN_LOG10_MAX)   # 实际增益上界
FFE_SPREAD = 0.05             # Stage 1 邻域采样幅值（旧 v1 参数，v4 由 TRUST_FFE 决定）
CTLE_SPREAD = 1.0


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


def _x_to_taps_ctle(x, ffe_pre=FFE_PRE):
    """x -> (5-tap FFE, gDC, gDC2, driver_gain[线性]) —— 增益维按 log10 倍率解码。"""
    return (construct_taps(x[:N_SIDE], ffe_pre), x[N_SIDE], x[N_SIDE + 1],
            gain_from_u(x[N_SIDE + 2]))

def _taps_to_x(taps, gdc, gdc2, gain, ffe_pre=FFE_PRE):
    """(5-tap FFE, gDC, gDC2, driver_gain[线性]) -> x（增益维编码为 log10 倍率）。"""
    taps = np.asarray(taps, dtype=float)
    pre_post = np.concatenate([taps[:ffe_pre], taps[ffe_pre + 1:]])
    return np.concatenate([pre_post, [gdc, gdc2, u_from_gain(gain)]])


def _bounds():
    b = [(-FFE_BOUND, FFE_BOUND)] * N_SIDE
    b.append((CTLE_GDC_MIN, CTLE_GDC_MAX))
    b.append((CTLE_GDC2_MIN, CTLE_GDC2_MAX))
    b.append((GAIN_LOG10_MIN, GAIN_LOG10_MAX))
    return np.array(b)


def _apply_x_to_config(config, gdc, gdc2, gain):
    """把当前搜索点的 CTLE / driver_gain 写入 config（原地写入；顺序调用安全）。"""
    config['tx']['ctle_g_dc_db'] = float(gdc)
    config['tx']['ctle_g_dc2_db'] = float(gdc2)
    config['channel']['driver_gain'] = float(gain)
    return config


def _physical_eval(config, taps, gdc, gdc2, gain):
    """真实 BER 评估（对 SIM_SEEDS 里的多个仿真种子取 log10 均值）。

    返回 (log10_mean, 10**log10_mean)。多 seed 平均用于抑制 BER 估计噪声：
    单块长的 BER 绝对值会随实现漂移，多实现取均值后轨迹才可比。
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


def _make_row(sample_id, taps, gdc, gdc2, gain, logber, mlse_ber, tx_fir, drive_rms):
    row = {'sample_id': sample_id, 'ctle_dc': gdc, 'ctle_dc2': gdc2,
           'driver_gain': gain, 'gain_u': u_from_gain(gain), 'drive_rms': drive_rms,
           'mlse_ber': mlse_ber, 'log10_ber': logber}
    for j in range(len(taps)):
        row[f'ffe_tap_{j}'] = taps[j]
    for j in range(7):
        row[f'tx_fir_{j}'] = tx_fir[j]
    return row


def _ffe_pre(config):
    return int(config['tx'].get('ffe_pre', FFE_PRE))


def _predict_a_x(model_a, x, ucb_kappa=0.0):
    """Model A（方向模型）对搜索向量 x 的直接预测（log10 BER）。"""
    x = np.asarray(x, dtype=float).reshape(1, -1)
    if ucb_kappa and hasattr(model_a, 'predict_with_std'):
        mu, sigma = model_a.predict_with_std(x)
        return float(mu[0] + ucb_kappa * sigma[0])
    return float(np.asarray(model_a.predict(x)).ravel()[0])


def _predict_a(model_a, config, taps, gdc, gdc2, gain, ucb_kappa=0.0):
    """Model A 预测（按物理量调用）：内部换算成搜索向量 x 再预测。

        x = [8 个 FFE 旁瓣, gDC, gDC2, u_gain = log10(gain / DRIVER_GAIN_NOMINAL)]

    v4 修订：Model A 与 Model B 共用**搜索向量本身**作为输入（不再经过 Tx 端波形探针）。
    理由（详见 docs/08 与 train_surrogates.train_v4）：
      1. 三组自由度（FFE / CTLE / driver_gain）在 x 上天然同量纲，梯度直接落在搜索变量上，
         不会出现"某一组量纲被其它组吃掉"的问题；
      2. 波形探针是线性冲激响应，而真实链路在整形级之前还有 DAC ENOB 量化这类幅度相关
         非线性，探针与真实链路并不严格等价；且 7 抽头绝对 FIR 对 11 维配置是多对一压缩。
    """
    return _predict_a_x(model_a, _taps_to_x(np.asarray(taps, dtype=float), gdc, gdc2, gain,
                                            _ffe_pre(config)), ucb_kappa)


def _predict_b_x(model_b, x):
    """Model B（拦截模型）对搜索向量 x 的直接预测（log10 BER 的保守上包络）。"""
    return float(np.asarray(model_b.predict(np.asarray(x, dtype=float).reshape(1, -1))).ravel()[0])


def _pred_b_ber(model_b, x):
    """Model B 预测的 BER（用于百分比拦截判据）。"""
    return 10.0 ** _predict_b_x(model_b, x)


def _predict_b(model_b, config, taps, gdc, gdc2, gain):
    """Model B 预测（按物理量调用）。"""
    return _predict_b_x(model_b, _taps_to_x(np.asarray(taps, dtype=float), gdc, gdc2, gain,
                                            _ffe_pre(config)))


def _grad_a(model_a, x):
    """Model A 对 x 的梯度（解析优先；模型无解析梯度时退回有限差分）。"""
    x = np.asarray(x, dtype=float)
    if hasattr(model_a, 'grad'):
        return np.asarray(model_a.grad(x.reshape(1, -1))[0], dtype=float)
    return _numerical_gradient(lambda z: _predict_a_x(model_a, z), x, eps=0.01)


# ============================================================
# Stage 1：模型供给（采样 + 训练 A/B）
# ============================================================

def _stage1_collect(config, n_samples, ffe_pre, seed=42):
    """围绕起点 x0 做 LHS 邻域采样（11 维），仅为训练 A/B 模型。"""
    seed_pre_post = np.concatenate([SEED_TAPS[:ffe_pre], SEED_TAPS[ffe_pre + 1:]])

    sampler = qmc.LatinHypercube(d=N_DIM, seed=seed)
    sp = sampler.random(n=n_samples)

    rows = []
    print(f"[Stage 1] neighborhood sampling ({n_samples} samples around x0)...")
    for i in range(n_samples):
        pre_post = seed_pre_post + (sp[i, :N_SIDE] * 2 - 1.0) * TRUST_FFE
        gdc = float(np.clip(SEED_GDC + (sp[i, N_SIDE] * 2 - 1.0) * TRUST_CTLE,
                            CTLE_GDC_MIN, CTLE_GDC_MAX))
        gdc2 = float(np.clip(SEED_GDC2 + (sp[i, N_SIDE + 1] * 2 - 1.0) * TRUST_CTLE,
                             CTLE_GDC2_MIN, CTLE_GDC2_MAX))
        gain = float(np.clip(SEED_GAIN + (sp[i, N_SIDE + 2] * 2 - 1.0) * TRUST_GAIN,
                             GAIN_MIN, GAIN_MAX))
        taps = construct_taps(pre_post, ffe_pre)
        logber, mlse_ber = _physical_eval(config, taps, gdc, gdc2, gain)
        fir_shape, drive_rms = extract_tx_features(config, custom_tx_taps=taps, num_taps=7)
        rows.append(_make_row(i, taps, gdc, gdc2, gain, logber, mlse_ber, fir_shape, drive_rms))
        if (i + 1) % 100 == 0:
            print(f"  sampled {i + 1}/{n_samples}")
    return pd.DataFrame(rows)


def _stage1_train(df, model_dir):
    return train_from_df(df, model_dir, verbose=True)


# ============================================================
# Stage 2：约束梯度下降（不回传真实 MLSE_BER）
# ============================================================

def _make_objective_a(model_a, ucb_kappa=0.0):
    """Model A 目标函数（输入直接是搜索向量 x）。保留该包装便于自检/画剖面。"""
    def objective(x):
        return _predict_a_x(model_a, x, ucb_kappa)
    return objective


def _numerical_gradient(fn, x, eps=0.01):
    """白盒有限差分梯度。"""
    x = np.asarray(x, dtype=float)
    f0 = fn(x)
    g = np.zeros_like(x)
    for i in range(len(x)):
        xp = x.copy()
        xp[i] += eps
        g[i] = (fn(xp) - f0) / eps
    return g


def _stage2_descent(config, model_a, model_b, x0, ffe_pre, n_steps, safety_ref, lr, rng,
                    ucb_kappa=0.0, freeze_extra=False):
    """手写投影梯度下降（白盒、逐步可见）：

        x_{k+1} = clip( x_k - alpha_k * STEP_SPAN * dir , 搜索箱 )

    设计要点（v4 修订）：
    - 目标：Model A（搜索向量 x → log10 BER 条件均值）的负梯度，**解析求导**；
      FFE / CTLE / driver_gain 三组自由度一起被优化。
    - 步长按**组内归一化**：每组先在组内把梯度方向归一化，再乘以该组自己的箱宽
      （FFE 0.20 / CTLE 6 dB / gain 1.12 dex），三组各以"箱宽的固定比例"前进。
      这样不会因为 Model A 对某一组的斜率天然偏大就独吞步长（旧版整体归一化时，
      增益维每步只走 ~0.004 dex，15 步几乎不动，等于"增益不可调"）。
    - 组梯度门控：某组"走满整箱"的预测收益 < GROUP_GATE 就冻结该组。
    - 拦截：Model B 按 **变差百分比** 否决候选点 —— 预测 BER 相对种子点预测值
      变差超过 MAX_DEGRADE_FRAC 就折半步长重试。
    - 停止：边际改善门控（Model A 预测每步改善 < MIN_GAIN_DEX）。
    - freeze_extra=True：把 CTLE 两维与 driver_gain 冻结在种子值（消融对照）。
    - 只记录真实 BER，不回传决策。
    """
    # 搜索箱：FFE / CTLE 相对种子收紧（防代理外推），driver_gain 允许走满整个设计箱
    gbounds = _bounds()
    gain_radius = max(abs(GAIN_LOG10_MIN), abs(GAIN_LOG10_MAX))
    radius = np.array([TRUST_FFE] * N_SIDE + [TRUST_CTLE, TRUST_CTLE, gain_radius])
    span = STEP_SPAN.copy()
    if freeze_extra:
        radius[8:] = 0.0          # 消融：只优化 FFE
        span[8:] = 0.0
    x0 = np.array(x0, dtype=float)
    tr_bounds = np.stack([
        np.maximum(gbounds[:, 0], x0 - radius),
        np.minimum(gbounds[:, 1], x0 + radius),
    ], axis=1)

    # 拦截红线（百分比口径）：允许的 BER = 种子点预测值 × (1 + MAX_DEGRADE_FRAC)
    seed_pred_ber = 10.0 ** safety_ref
    allowed_ber = seed_pred_ber * (1.0 + MAX_DEGRADE_FRAC)

    # 轨迹信任域：标准化空间里从 x0 出发的位移上限
    rho = float(getattr(model_a, 'local_spacing_', 0.0) or 0.0)
    sd_vec = np.asarray(getattr(model_a, 'sd', np.ones_like(x0)), dtype=float)
    mu_vec = np.asarray(getattr(model_a, 'mu', np.zeros_like(x0)), dtype=float)
    z0 = (x0 - mu_vec) / sd_vec
    path_limit = TRUST_PATH_K * rho if rho > 0 else None

    trace = []
    x = x0.copy()
    pred_a_prev = None

    for step in range(n_steps):
        # 1. 解析梯度 -> 逐组归一化方向（组内保留相对大小；组间各按自己的箱宽前进）
        g = _grad_a(model_a, x)
        gs = g * span
        direction = np.zeros_like(g)
        active = []
        for sl, name in zip(GROUP_SLICES, GROUP_NAMES):
            nrm = float(np.linalg.norm(gs[sl]))
            if nrm >= GROUP_GATE:
                direction[sl] = gs[sl] / nrm
                active.append(name)
        if not active:
            print(f'[Stage 2] stop: 三组梯度均低于门控 {GROUP_GATE:g}（Model A 曲面趋平，step {step}）')
            break

        # 2. 回溯线搜索：候选点必须通过 Model B 的"变差百分比"拦截
        alpha = lr * (ALPHA_DECAY ** step)
        x_new = None
        alpha_k = alpha
        for _ in range(20):
            x_cand = np.clip(x - alpha_k * span * direction, tr_bounds[:, 0], tr_bounds[:, 1])
            if np.linalg.norm(x_cand - x) < 1e-9:
                break
            if _pred_b_ber(model_b, x_cand) <= allowed_ber:
                x_new = x_cand
                break
            alpha_k *= 0.5
        if x_new is None:
            print(f'[Stage 2] stop: 无候选点通过 Model B 拦截线 {allowed_ber:.2e}（step {step}）')
            break

        # 2b. 轨迹信任域：走出数据支持的邻域就停（不等它继续“预测下降”）
        if path_limit is not None:
            z_new = (x_new - mu_vec) / sd_vec
            if float(np.linalg.norm(z_new - z0)) > path_limit:
                print(f'[Stage 2] stop: 轨迹位移超过信任域 {path_limit:.2f}σ '
                      f'(= {TRUST_PATH_K:g} × ρ, ρ={rho:.2f}σ) at step {step}')
                break

        # 3. 代理预测 + 真实 BER（仅记录验证）
        taps, gdc, gdc2, gain = _x_to_taps_ctle(x_new, ffe_pre)
        pred_a = _predict_a_x(model_a, x_new)
        pred_b = _predict_b_x(model_b, x_new)
        real_logber, real_mlse = _physical_eval(config, taps, gdc, gdc2, gain)

        # 4. 边际改善门控：Model A 已经"没什么可赚"时停手（避免无意义地走远）
        if pred_a_prev is not None and (pred_a_prev - pred_a) < MIN_GAIN_DEX:
            trace.append({
                'step': step, 'x': x_new, 'taps': taps,
                'gdc': gdc, 'gdc2': gdc2, 'gain': gain,
                'pred_a': pred_a, 'pred_b': pred_b,
                'pred_b_ber': 10.0 ** pred_b, 'allowed_ber': allowed_ber,
                'safe': (10.0 ** pred_b) <= allowed_ber,
                'real_logber': real_logber, 'real_mlse': real_mlse,
                'grad_norm': float(np.linalg.norm(g)), 'stop_reason': 'marginal_gain',
            })
            print(f"[Stage 2] stop: marginal predicted gain "
                  f"({pred_a_prev - pred_a:+.4f} < {MIN_GAIN_DEX}) at step {step}")
            break
        pred_a_prev = pred_a

        trace.append({
            'step': step,
            'x': x_new,
            'taps': taps,
            'gdc': gdc, 'gdc2': gdc2, 'gain': gain,
            'pred_a': pred_a,
            'pred_b': pred_b,
            'pred_b_ber': 10.0 ** pred_b,
            'allowed_ber': allowed_ber,
            'safe': (10.0 ** pred_b) <= allowed_ber,
            'real_logber': real_logber,
            'real_mlse': real_mlse,
            'grad_norm': float(np.linalg.norm(g)),
            'stop_reason': '',
        })

        print(f"[Stage 2] gd {step + 1}/{n_steps} | ModelA {10.0 ** pred_a:.2e} "
              f"| ModelB {10.0 ** pred_b:.2e} (<= {allowed_ber:.2e}) | "
              f"real {real_mlse:.2e} | gain x{gain / DRIVER_GAIN_NOMINAL:.3f} "
              f"| gDC {gdc:+.2f} | gDC2 {gdc2:+.2f} | 组 {active}")

        # 5. 收敛判断：位移几乎为零则提前停止
        if np.linalg.norm(x_new - x) < 1e-6:
            break
        x = x_new

    return trace



# ============================================================
# 已废弃的单进程入口
# ============================================================

def run_ddps(*args, **kwargs):
    """[已移除] v1/v2 时代的单进程端到端入口。

    DDPS v3 的正式流程（产物互相隔离、可复现）：
        python dataset_generator.py ...                        # 数据
        python -c "... train_surrogates.train_v3 ..."          # 训练 A/B
        python test_generalization.py ...                      # 在线调优泛化测试
        python report_ddps_v3.py ...                           # 可视化报告
    历史实现见 git 历史（v2 及更早）。
    """
    raise RuntimeError(
        "run_ddps() 已移除：请使用 v3 流水线 "
        "(dataset_generator.py -> train_surrogates.train_v3 -> test_generalization.py -> report_ddps_v3.py)。"
    )


if __name__ == "__main__":
    raise SystemExit(
        "该入口已废弃。请运行:\n"
        "  1) python dataset_generator.py --base-samples 320 --anchor-samples 60 --num-symbols <N>\n"
        "  2) python -c \"from train_surrogates import train_v3; import glob; "
        "train_v3(sorted(glob.glob('dataset/ddps_v3_dataset_*.csv'))[-1], 'models/ddps_v3')\"\n"
        "  3) python test_generalization.py --model-dir models/ddps_v3 --out-dir result/ddps_v3_<ts>\n"
        "  4) python report_ddps_v3.py --test-dir result/ddps_v3_<ts> --model-dir models/ddps_v3"
    )