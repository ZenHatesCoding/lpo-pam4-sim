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

# ---------------------------------------------------------------------------
# v5：driver_gain 维从"代理梯度盲驱"改为"发端 RMS 物理目标解析驱动"
#
# 根因（详见 scratch/diag_gain_sweep.py 与 result/ddps_v4_divergence.csv）：
#   gain 维的最优方向随环境反转——基线信号强、最优 gain 偏低（防 MZM 削顶）；
#   高插损信号弱、最优 gain 偏高（补摆幅）。基线训练的代理对 gain 梯度永远是
#   "降 gain"（基线最优是降 gain），于是在 IL20x20 等恶劣环境把 gain 维反方向驱动，
#   造成"预测一直降、实测却升"。v2/v3 之所以能单调下降，正是因为 gain 被锁死。
#
# 修法：gain 不再交给代理。每步用发端指标（MZM 输入端 RMS，发端可测、不需 BER）
#   把 gain 解析调到目标摆幅：
#       drive_rms ∝ gain（链路里 gain 是最后乘子，线性关系，实测 k 为常数）
#       => gain = gain_seed * (target_rms / measured_rms_at_seed)
#   target_rms 由 per-case 细粒度扫描标定（scratch/scan_per_case_rms.py）：
#   每个用例单独扫 RMS（0.06~0.22 V，步长 0.005），各自取最优——不求几何均值。
#   因为 k 随 IL 变化，同样的 target_rms 在不同用例解析出的 gain 倍率不同
#   （强信号 ~0.6、弱信号 ~0.9）。FFE/CTLE 成形仍走基线代理泛化（扫描证实
#   CTLE 最优方向跨环境一致，11/15 case 最优 gDC=-3，可泛化）。
# ---------------------------------------------------------------------------
TARGET_DRIVE_RMS = 0.14       # 全局兜底值（V）；实际用 per-case 扫描结果覆盖

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
TRUST_PATH_K_V5 = 2.0         # v5 信任域放宽：gain 维物理驱动后形状空间更紧凑、映射更清晰
                              # （v5 数据集 gain 窄带使 FFE/CTLE→BER 映射 R²=0.72 vs v4 0.28），
                              # 形状方向可信范围更大；v5 用 2.0ρ 让轨迹多走几步拿到更多改善。
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


def _measure_drive_rms(config, taps, gdc, gdc2, gain):
    """发端指标：当前配置下 MZM 输入端的驱动 RMS（V）。

    只跑 Tx 模拟前端（FFE->DAC->IL->CTLE->Driver->Driver BW），不含 MZM 与后端，
    因此**不产生真实 BER**，属于 Stage-2 允许拿的发端指标（与 tx_channel_extract
    的 _drive_rms 同一实现）。drive_rms ∝ gain（gain 是链路最后的线性乘子，实测
    在固定 FFE/CTLE 下 rms/gain 为常数 k），所以给定目标 RMS 可解析反推 gain。
    """
    _apply_x_to_config(config, gdc, gdc2, gain)
    _, drive_rms = extract_tx_features(config, custom_tx_taps=taps, num_taps=7)
    return float(drive_rms)


def _solve_gain_for_rms(config, taps, gdc, gdc2, target_rms, gain_init=None,
                        gain_bounds=(None, None)):
    """解析地把 driver_gain 调到使 MZM 输入 RMS = target_rms。

    drive_rms(gain) = k * gain（k 由 FFE/CTLE/IL 决定，与 gain 无关），故
        gain_target = gain_ref * (target_rms / rms_ref)
    只需一次发端测量即可标定 k。裁到搜索箱内。
    """
    g_ref = float(gain_init if gain_init is not None else SEED_GAIN)
    rms_ref = _measure_drive_rms(config, taps, gdc, gdc2, g_ref)
    if rms_ref <= 1e-9:
        return g_ref
    g_new = g_ref * (target_rms / rms_ref)
    lo = gain_bounds[0] if gain_bounds[0] is not None else GAIN_MIN
    hi = gain_bounds[1] if gain_bounds[1] is not None else GAIN_MAX
    return float(np.clip(g_new, lo, hi))


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
# Stage 2 v5：FFE/CTLE 走基线代理泛化 + gain 走发端 RMS 物理目标
#
# 这是 v4 之后真正修复"预测降/实测升"的版本。关键差别：
#   - 模型只建模 **FFE+CTLE（6 维成形）**，不再含 gain 维（gain 维方向随环境反转，
#     信道盲代理无法处理）。
#   - gain 维每步解析调到 target_rms：drive_rms ∝ gain（一次发端测量标定 k），
#     gain = gain_ref * (target_rms / rms_ref)。target_rms 由 per-case 细粒度扫描
#     标定（每个用例单独扫，不求几何均值），因 k 随 IL 变，解析 ratio 随用例自适应。
#   - FFE/CTLE 成形方向跨环境一致（扫描证实 11/15 case 最优 gDC=-3），可泛化。
# ============================================================

# v5 形成空间的步长箱宽（FFE/CTLE 两组）
SHAPE_STEP_SPAN = np.array([2.0 * TRUST_FFE] * N_SIDE + [2.0 * TRUST_CTLE] * 2)
SHAPE_GROUPS = (slice(0, N_SIDE), slice(N_SIDE, N_SIDE + 2))
SHAPE_GROUP_NAMES = ('FFE', 'CTLE')


def _shape_bounds(x0_shape):
    """FFE/CTLE 的搜索盒（相对种子收紧，防代理外推）。"""
    b = [(-FFE_BOUND, FFE_BOUND)] * N_SIDE + [(CTLE_GDC_MIN, CTLE_GDC_MAX),
                                               (CTLE_GDC2_MIN, CTLE_GDC2_MAX)]
    b = np.array(b)
    radius = np.array([TRUST_FFE] * N_SIDE + [TRUST_CTLE, TRUST_CTLE])
    return np.stack([np.maximum(b[:, 0], x0_shape - radius),
                     np.minimum(b[:, 1], x0_shape + radius)], axis=1)


def _stage2_descent_v5(config, model_a, model_b, x0_shape, gain0, ffe_pre, n_steps,
                        safety_ref, lr, target_rms=TARGET_DRIVE_RMS,
                        freeze_extra=False, gain_bounds=(None, None)):
    """v5 在线调优：FFE/CTLE 代理梯度 + gain 发端 RMS 物理目标驱动。

    输入：
        x0_shape : 6 维 = [4 FFE 旁瓣, gDC, gDC2]（不含 gain）
        gain0    : 种子 driver_gain（线性）
        model_a/b: 只吃 6 维 x_shape 的代理（A 给方向，B 给拦截）
    每步：
        1. g = ∇_shape ModelA(x_shape)（6 维，解析）
        2. 组内归一化方向 + 投影到 shape 搜索盒
        3. gain = 解析调到 target_rms（发端测量，不需 BER）
        4. Model B 按百分比拦截候选点
        5. 真实 BER 仅记账
    """
    tr_bounds = _shape_bounds(np.asarray(x0_shape, dtype=float))
    x_shape = np.array(x0_shape, dtype=float)
    gain = float(gain0)

    # 种子点的发端 RMS 标定（用种子 gain 测一次 k）
    taps_seed = construct_taps(x_shape[:N_SIDE], ffe_pre)
    rms_seed = _measure_drive_rms(config, taps_seed, x_shape[N_SIDE], x_shape[N_SIDE + 1], gain)

    # 拦截红线（百分比口径）：允许 BER = 种子预测 × (1 + MAX_DEGRADE_FRAC)
    seed_pred_ber = 10.0 ** safety_ref
    allowed_ber = seed_pred_ber * (1.0 + MAX_DEGRADE_FRAC)

    # 轨迹信任域（标准化空间，仅 FFE/CTLE 6 维）——v5 放宽到 2.0ρ
    rho = float(getattr(model_a, 'local_spacing_', 0.0) or 0.0)
    sd_vec = np.asarray(getattr(model_a, 'sd', np.ones_like(x_shape)), dtype=float)
    mu_vec = np.asarray(getattr(model_a, 'mu', np.zeros_like(x_shape)), dtype=float)
    z0 = (x_shape - mu_vec) / sd_vec
    path_limit = TRUST_PATH_K_V5 * rho if rho > 0 else None

    trace = []
    pred_a_prev = None
    span = SHAPE_STEP_SPAN.copy()
    if freeze_extra:
        span[N_SIDE:] = 0.0          # 消融：只优化 FFE

    for step in range(n_steps):
        # 1. FFE/CTLE 代理梯度 -> 组内归一化方向
        g = _grad_a(model_a, x_shape)
        gs = g * span
        direction = np.zeros_like(g)
        active = []
        for sl, name in zip(SHAPE_GROUPS, SHAPE_GROUP_NAMES):
            nrm = float(np.linalg.norm(gs[sl]))
            if nrm >= GROUP_GATE:
                direction[sl] = gs[sl] / nrm
                active.append(name)
        if not active:
            print(f'[Stage2v5] stop: 成形梯度均低于门控 {GROUP_GATE:g}（step {step}）')
            break

        # 2. 回溯线搜索：候选 shape 必须通过 Model B 的百分比拦截
        alpha = lr * (ALPHA_DECAY ** step)
        x_shape_new = None
        alpha_k = alpha
        for _ in range(20):
            x_cand = np.clip(x_shape - alpha_k * span * direction,
                              tr_bounds[:, 0], tr_bounds[:, 1])
            if np.linalg.norm(x_cand - x_shape) < 1e-9:
                break
            if _pred_b_ber(model_b, x_cand) <= allowed_ber:
                x_shape_new = x_cand
                break
            alpha_k *= 0.5
        if x_shape_new is None:
            print(f'[Stage2v5] stop: 无候选点通过 Model B 拦截 {allowed_ber:.2e}（step {step}）')
            break

        # 2b. 轨迹信任域
        if path_limit is not None:
            z_new = (x_shape_new - mu_vec) / sd_vec
            if float(np.linalg.norm(z_new - z0)) > path_limit:
                print(f'[Stage2v5] stop: 轨迹位移超过信任域 {path_limit:.2f}σ '
                      f'(= {TRUST_PATH_K:g} × ρ, ρ={rho:.2f}σ) at step {step}')
                break

        # 3. gain 解析调到 target_rms（发端物理目标，不需 BER）
        taps_new = construct_taps(x_shape_new[:N_SIDE], ffe_pre)
        gdc_new = float(x_shape_new[N_SIDE])
        gdc2_new = float(x_shape_new[N_SIDE + 1])
        # 用当前 gain 做参考测 k，反推 target gain（参考点用上一步 gain 更稳）
        gain_ref = gain
        rms_ref = _measure_drive_rms(config, taps_new, gdc_new, gdc2_new, gain_ref)
        if rms_ref > 1e-9:
            gain_new = gain_ref * (target_rms / rms_ref)
        else:
            gain_new = gain_ref
        lo = gain_bounds[0] if gain_bounds[0] is not None else GAIN_MIN
        hi = gain_bounds[1] if gain_bounds[1] is not None else GAIN_MAX
        gain_new = float(np.clip(gain_new, lo, hi))

        # 4. 代理预测 + 真实 BER（仅记录）
        pred_a = _predict_a_x(model_a, x_shape_new)
        pred_b = _predict_b_x(model_b, x_shape_new)
        real_logber, real_mlse = _physical_eval(config, taps_new, gdc_new, gdc2_new, gain_new)
        rms_actual = _measure_drive_rms(config, taps_new, gdc_new, gdc2_new, gain_new)

        # 5. 边际改善门控（基于代理预测改善）
        if pred_a_prev is not None and (pred_a_prev - pred_a) < MIN_GAIN_DEX:
            trace.append({
                'step': step, 'x_shape': x_shape_new, 'taps': taps_new,
                'gdc': gdc_new, 'gdc2': gdc2_new, 'gain': gain_new,
                'gain_ratio': gain_new / DRIVER_GAIN_NOMINAL,
                'drive_rms': rms_actual,
                'pred_a': pred_a, 'pred_b': pred_b,
                'pred_b_ber': 10.0 ** pred_b, 'allowed_ber': allowed_ber,
                'real_logber': real_logber, 'real_mlse': real_mlse,
                'grad_norm': float(np.linalg.norm(g)), 'stop_reason': 'marginal_gain',
            })
            print(f"[Stage2v5] stop: marginal predicted gain "
                  f"({pred_a_prev - pred_a:+.4f} < {MIN_GAIN_DEX}) at step {step}")
            break
        pred_a_prev = pred_a

        trace.append({
            'step': step, 'x_shape': x_shape_new, 'taps': taps_new,
            'gdc': gdc_new, 'gdc2': gdc2_new, 'gain': gain_new,
            'gain_ratio': gain_new / DRIVER_GAIN_NOMINAL,
            'drive_rms': rms_actual,
            'pred_a': pred_a, 'pred_b': pred_b,
            'pred_b_ber': 10.0 ** pred_b, 'allowed_ber': allowed_ber,
            'real_logber': real_logber, 'real_mlse': real_mlse,
            'grad_norm': float(np.linalg.norm(g)), 'stop_reason': '',
        })

        print(f"[Stage2v5] gd {step + 1}/{n_steps} | ModelA {10.0 ** pred_a:.2e} "
              f"| real {real_mlse:.2e} | gain x{gain_new / DRIVER_GAIN_NOMINAL:.3f} "
              f"| rms {rms_actual:.4f} | gDC {gdc_new:+.2f} | gDC2 {gdc2_new:+.2f} | 组 {active}")

        if np.linalg.norm(x_shape_new - x_shape) < 1e-6:
            break
        x_shape = x_shape_new
        gain = gain_new

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

# ============================================================
# v6：A=探针->BER 方向映射 + B=参数->BER 风险控制
# ============================================================

def _probe_features(config, taps, gdc, gdc2, gain):
    """提取 Model A 的 8 维探针特征：7-tap Tx FIR + drive_rms。"""
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


def _grad_a_chain(model_a, config, x_shape, gain, ffe_pre, eps=0.01):
    """通过 A 的链式法则计算 6 维参数梯度。

    对每个参数 i 做 ±eps 中心差分：
        1. 扰动 x_shape[i] -> 新 taps/gdc/gdc2
        2. 重算探针特征（7-tap FIR + drive_rms，用参考 gain）
        3. 查 Model A -> 得 ΔBER
    链式法则：∂BER/∂param_i = ∂A/∂probe × ∂probe/∂param_i ≈ ΔA / Δparam_i
    """
    x_shape = np.asarray(x_shape, dtype=float)
    g = np.zeros_like(x_shape)
    eps_vec = np.array([eps] * N_SIDE + [eps * 10] * 2)  # CTLE 步长更大

    for i in range(len(x_shape)):
        xp = x_shape.copy(); xp[i] += eps_vec[i]
        xm = x_shape.copy(); xm[i] -= eps_vec[i]

        taps_p = construct_taps(xp[:N_SIDE], ffe_pre)
        taps_m = construct_taps(xm[:N_SIDE], ffe_pre)
        probe_p = _probe_features(config, taps_p, float(xp[N_SIDE]), float(xp[N_SIDE+1]), gain)
        probe_m = _probe_features(config, taps_m, float(xm[N_SIDE]), float(xm[N_SIDE+1]), gain)

        ap = _predict_a_probe(model_a, probe_p)
        am = _predict_a_probe(model_a, probe_m)
        g[i] = (ap - am) / (2.0 * eps_vec[i])

    return g


SHAPE_STEP_SPAN_V6 = np.array([2.0 * TRUST_FFE] * N_SIDE + [2.0 * TRUST_CTLE] * 2)
SHAPE_GROUPS_V6 = (slice(0, N_SIDE), slice(N_SIDE, N_SIDE + 2))
SHAPE_GROUP_NAMES_V6 = ('FFE', 'CTLE')
TRUST_PATH_K_V6 = 2.0


def _stage2_descent_v6(config, model_a, model_b, x0_shape, gain0, ffe_pre, n_steps,
                        safety_ref, lr, target_rms=TARGET_DRIVE_RMS,
                        gain_bounds=(None, None)):
    """v6 在线调优：A 探针链式梯度 + B 参数域风险控制 + gain per-case RMS 物理驱动。

    每步：
        1. g = ∂A/∂x_shape（链式法则：扰动参数->重算探针->查A，6 维中心差分）
        2. 组内归一化方向 + 投影到 shape 搜索盒
        3. gain = 解析调到 target_rms（发端测量，不需 BER）
        4. Model B 对候选参数预测 BER，按百分比拦截（理想情况不触发）
        5. 真实 BER 仅记账
    """
    tr_bounds = _shape_bounds(np.asarray(x0_shape, dtype=float))
    x_shape = np.array(x0_shape, dtype=float)
    gain = float(gain0)

    # 种子点探针 + B 预测
    taps_seed = construct_taps(x_shape[:N_SIDE], ffe_pre)
    rms_seed = _measure_drive_rms(config, taps_seed, float(x_shape[N_SIDE]),
                                   float(x_shape[N_SIDE+1]), gain)
    probe_seed = _probe_features(config, taps_seed, float(x_shape[N_SIDE]),
                                 float(x_shape[N_SIDE+1]), gain)
    seed_pred_a = _predict_a_probe(model_a, probe_seed)
    seed_pred_b = _predict_b_params(model_b, x_shape, rms_seed)

    # B 拦截红线
    seed_pred_ber = 10.0 ** seed_pred_b
    allowed_ber = seed_pred_ber * (1.0 + MAX_DEGRADE_FRAC)

    # 信任域（B 的参数域）
    rho = float(getattr(model_b, 'local_spacing_', 0.0) or 0.0)
    sd_vec = np.asarray(getattr(model_b, 'sd', np.ones(7)), dtype=float)[:6]
    mu_vec = np.asarray(getattr(model_b, 'mu', np.zeros(7)), dtype=float)[:6]
    z0 = (x_shape - mu_vec) / sd_vec
    path_limit = TRUST_PATH_K_V6 * rho if rho > 0 else None

    span = SHAPE_STEP_SPAN_V6.copy()
    trace = []
    pred_a_prev = None

    for step in range(n_steps):
        # 1. A 链式梯度
        g = _grad_a_chain(model_a, config, x_shape, gain, ffe_pre, eps=0.01)
        gs = g * span
        direction = np.zeros_like(g)
        active = []
        for sl, name in zip(SHAPE_GROUPS_V6, SHAPE_GROUP_NAMES_V6):
            nrm = float(np.linalg.norm(gs[sl]))
            if nrm >= GROUP_GATE:
                direction[sl] = gs[sl] / nrm
                active.append(name)
        if not active:
            print(f'[Stage2v6] stop: 成形梯度均低于门控 {GROUP_GATE:g}（step {step}）')
            break

        # 2. 回溯线搜索 + B 拦截
        alpha = lr * (ALPHA_DECAY ** step)
        x_shape_new = None
        alpha_k = alpha
        for _ in range(20):
            x_cand = np.clip(x_shape - alpha_k * span * direction,
                              tr_bounds[:, 0], tr_bounds[:, 1])
            if np.linalg.norm(x_cand - x_shape) < 1e-9:
                break
            # B 对候选参数预测
            taps_cand = construct_taps(x_cand[:N_SIDE], ffe_pre)
            rms_cand = _measure_drive_rms(config, taps_cand, float(x_cand[N_SIDE]),
                                           float(x_cand[N_SIDE+1]), gain)
            if _predict_b_params(model_b, x_cand, rms_cand) * np.log(10) <= np.log10(allowed_ber):
                x_shape_new = x_cand
                break
            alpha_k *= 0.5
        if x_shape_new is None:
            print(f'[Stage2v6] stop: 无候选点通过 Model B 拦截（step {step}）')
            break

        # 2b. 信任域
        if path_limit is not None:
            z_new = (x_shape_new - mu_vec) / sd_vec
            if float(np.linalg.norm(z_new - z0)) > path_limit:
                print(f'[Stage2v6] stop: 轨迹位移超过信任域 {path_limit:.2f}（step {step}）')
                break

        # 3. gain 解析调到 target_rms
        taps_new = construct_taps(x_shape_new[:N_SIDE], ffe_pre)
        gdc_new = float(x_shape_new[N_SIDE])
        gdc2_new = float(x_shape_new[N_SIDE + 1])
        gain_ref = gain
        rms_ref = _measure_drive_rms(config, taps_new, gdc_new, gdc2_new, gain_ref)
        if rms_ref > 1e-9:
            gain_new = gain_ref * (target_rms / rms_ref)
        else:
            gain_new = gain_ref
        lo = gain_bounds[0] if gain_bounds[0] is not None else GAIN_MIN
        hi = gain_bounds[1] if gain_bounds[1] is not None else GAIN_MAX
        gain_new = float(np.clip(gain_new, lo, hi))

        # 4. A 探针预测 + B 参数预测 + 真实 BER（仅记录）
        probe_new = _probe_features(config, taps_new, gdc_new, gdc2_new, gain_new)
        pred_a = _predict_a_probe(model_a, probe_new)
        rms_actual = _measure_drive_rms(config, taps_new, gdc_new, gdc2_new, gain_new)
        pred_b = _predict_b_params(model_b, x_shape_new, rms_actual)
        real_logber, real_mlse = _physical_eval(config, taps_new, gdc_new, gdc2_new, gain_new)

        # 5. 边际改善门控
        if pred_a_prev is not None and (pred_a_prev - pred_a) < MIN_GAIN_DEX:
            trace.append({
                'step': step, 'x_shape': x_shape_new, 'taps': taps_new,
                'gdc': gdc_new, 'gdc2': gdc2_new, 'gain': gain_new,
                'gain_ratio': gain_new / DRIVER_GAIN_NOMINAL,
                'drive_rms': rms_actual,
                'pred_a': pred_a, 'pred_b': pred_b,
                'pred_b_ber': 10.0 ** pred_b, 'allowed_ber': allowed_ber,
                'real_logber': real_logber, 'real_mlse': real_mlse,
                'grad_norm': float(np.linalg.norm(g)), 'stop_reason': 'marginal_gain',
            })
            print(f"[Stage2v6] stop: marginal predicted gain "
                  f"({pred_a_prev - pred_a:+.4f} < {MIN_GAIN_DEX}) at step {step}")
            break
        pred_a_prev = pred_a

        trace.append({
            'step': step, 'x_shape': x_shape_new, 'taps': taps_new,
            'gdc': gdc_new, 'gdc2': gdc2_new, 'gain': gain_new,
            'gain_ratio': gain_new / DRIVER_GAIN_NOMINAL,
            'drive_rms': rms_actual,
            'pred_a': pred_a, 'pred_b': pred_b,
            'pred_b_ber': 10.0 ** pred_b, 'allowed_ber': allowed_ber,
            'real_logber': real_logber, 'real_mlse': real_mlse,
            'grad_norm': float(np.linalg.norm(g)), 'stop_reason': '',
        })

        print(f"[Stage2v6] gd {step + 1}/{n_steps} | ModelA {10.0 ** pred_a:.2e} "
              f"| real {real_mlse:.2e} | gain x{gain_new / DRIVER_GAIN_NOMINAL:.3f} "
              f"| rms {rms_actual:.4f} | gDC {gdc_new:+.2f} | gDC2 {gdc2_new:+.2f} | 组 {active}")

        if np.linalg.norm(x_shape_new - x_shape) < 1e-6:
            break
        x_shape = x_shape_new
        gain = gain_new

    return trace
