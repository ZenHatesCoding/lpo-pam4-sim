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

FFE_BOUND = 0.3
CTLE_GDC_MIN = -5.0
CTLE_GDC_MAX = 5.0
CTLE_GDC2_MIN = -5.0
CTLE_GDC2_MAX = 5.0
GAIN_MIN = 1.0                # driver_gain 全局边界（v3 新增可调维度）
GAIN_MAX = 3.0
PEAK_SUM_LIMIT = 0.8          # sum(|pre_post|) <= 0.8 -> 主抽头 >= 0.2
SAFETY_MARGIN = 0.3           # Model B 安全裕度：允许相对种子点恶化 0.3 个 log10
                              # v3 标定（11 维空间，262144×3 协议）：在完整 trace 上回放不同裕度——
                              #   0.6 → 164 步中 51 步真实 BER 劣于种子（最多 +0.48 dex），不可接受；
                              #   0.4 → 0 步劣化，平均改善 ×3.42；0.3 → 0 步劣化，×3.13；
                              #   0.2 → 0 步劣化，×2.94。
                              # 取 0.3：既消除劣化，又对轨迹间波动留有余量（只损失约 11% 平均增益）。
TRUST_FFE = 0.10              # Stage 2 信任域半径（FFE，相对起点）：防代理外推越界
TRUST_CTLE = 3.0              # Stage 2 信任域半径（CTLE, dB）
TRUST_GAIN = 0.5              # Stage 2 信任域半径（driver_gain）
GD_LR = 0.02                  # Stage 2 归一化梯度下降初始步长（随 step 以 0.92 衰减）
GRAD_GATE = 0.05              # Stage 2 梯度门控：|g| 低于该值视为代理曲面趋平
                              # （外推区/无效区），停止下降而非沿拟合噪声乱走

# ---------------------------------------------------------------------------
# v3 搜索空间：x = [8 个 FFE 旁瓣, gDC, gDC2, driver_gain]  —— 10D -> 11D
#   * CTLE 移到 Tx 电插损之后、Driver 之前，成为真正的 post-channel 均衡自由度
#   * driver_gain 由固定常数变为可调维度（决定 MZM 驱动幅度：OMA 与线性度的折中）
# 主抽头仍由归一化恒等式 1 - Σ|旁瓣| 派生，不是自由变量。
# ---------------------------------------------------------------------------
N_DIM = 11
# 各维预条件缩放（归一化梯度下降时使用）：FFE 量纲 ±0.3、CTLE ±5 dB、gain ±1。
PRECOND = np.array([1.0] * 8 + [20.0, 20.0, 4.0])

# 评估协议：仿真种子序列。多 seed 时对 log10 BER 取均值，抑制"单一实现"造成的
# BER 估计噪声（比只加长块长更可控，且能同时给出点内标准差）。
SIM_SEEDS = (42,)


def set_sim_seeds(seeds):
    """设置评估用的仿真种子序列（数据集 / 在线测试 / 深水复核共用同一口径）。"""
    global SIM_SEEDS
    SIM_SEEDS = tuple(int(s) for s in seeds)
    return SIM_SEEDS

# 已知“不错的起点”（种子）：来自两阶段实验的初始次优点
SEED_TAPS = np.array([0.0, 0.0, -0.034, -0.2987, 0.6091, 0.0, 0.0582, 0.0, 0.0])
SEED_GDC = 0.0
SEED_GDC2 = 0.0
SEED_GAIN = 2.0               # 标定值：gain=2.0 时 MZM 摆幅 = driver_vpp(0.617V)
FFE_SPREAD = 0.05             # Stage 1 邻域采样幅值（旧 v1 参数，v3 由 TRUST_FFE 决定）
CTLE_SPREAD = 1.0


def construct_9tap(pre_post, ffe_pre):
    abs_sum = np.sum(np.abs(pre_post))
    if abs_sum > PEAK_SUM_LIMIT:
        pre_post = pre_post * (PEAK_SUM_LIMIT / abs_sum)
    taps = np.zeros(9)
    taps[:ffe_pre] = pre_post[:ffe_pre]
    taps[ffe_pre + 1:] = pre_post[ffe_pre:]
    taps[ffe_pre] = 1.0 - np.sum(np.abs(pre_post))
    return taps


def _x_to_taps_ctle(x, ffe_pre):
    """x -> (9-tap FFE, gDC, gDC2, driver_gain)"""
    return construct_9tap(x[:8], ffe_pre), x[8], x[9], x[10]

def _taps_to_x(taps, gdc, gdc2, gain, ffe_pre):
    pre_post = np.zeros(8)
    pre_post[:ffe_pre] = taps[:ffe_pre]
    pre_post[ffe_pre:] = taps[ffe_pre + 1:]
    return np.concatenate([pre_post, [gdc, gdc2, gain]])


def _bounds():
    b = [(-FFE_BOUND, FFE_BOUND)] * 8
    b.append((CTLE_GDC_MIN, CTLE_GDC_MAX))
    b.append((CTLE_GDC2_MIN, CTLE_GDC2_MAX))
    b.append((GAIN_MIN, GAIN_MAX))
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
           'driver_gain': gain, 'drive_rms': drive_rms,
           'mlse_ber': mlse_ber, 'log10_ber': logber}
    for j in range(9):
        row[f'ffe_tap_{j}'] = taps[j]
    for j in range(7):
        row[f'tx_fir_{j}'] = tx_fir[j]
    return row


def _predict_a(model_a, config, taps, gdc, gdc2, gain, ucb_kappa=0.0):
    """Model A 预测：输入 = [7-tap FIR 形状, MZM 驱动 RMS]。

    drive_rms 特征是必需的：driver_gain 在纯线性 Tx 链里只是标量乘子，FIR 形状对整体
    尺度不变；若 Model A 只看 FIR 形状，它对 driver_gain 的梯度恒为 0，寻优无法移动该维。
    """
    _apply_x_to_config(config, gdc, gdc2, gain)
    fir_shape, drive_rms = extract_tx_features(config, custom_tx_taps=taps, num_taps=7)
    feats = np.concatenate([fir_shape, [drive_rms]])
    if hasattr(model_a, 'predict_with_std'):
        mu, sigma = model_a.predict_with_std([feats])
        return float(mu[0] + ucb_kappa * sigma[0])
    return float(model_a.predict([feats])[0])


def _predict_b(model_b, taps, gdc, gdc2, gain):
    full_cfg = list(taps) + [gdc, gdc2, gain]
    return float(model_b.predict([full_cfg])[0])


# ============================================================
# Stage 1：模型供给（采样 + 训练 A/B）
# ============================================================

def _stage1_collect(config, n_samples, ffe_pre, seed=42):
    """围绕起点 x0 做 LHS 邻域采样（11 维），仅为训练 A/B 模型。"""
    seed_pre_post = np.zeros(8)
    seed_pre_post[:ffe_pre] = SEED_TAPS[:ffe_pre]
    seed_pre_post[ffe_pre:] = SEED_TAPS[ffe_pre + 1:]

    sampler = qmc.LatinHypercube(d=N_DIM, seed=seed)
    sp = sampler.random(n=n_samples)

    rows = []
    print(f"[Stage 1] neighborhood sampling ({n_samples} samples around x0)...")
    for i in range(n_samples):
        pre_post = seed_pre_post + (sp[i, :8] * 2 - 1.0) * TRUST_FFE
        gdc = float(np.clip(SEED_GDC + (sp[i, 8] * 2 - 1.0) * TRUST_CTLE,
                            CTLE_GDC_MIN, CTLE_GDC_MAX))
        gdc2 = float(np.clip(SEED_GDC2 + (sp[i, 9] * 2 - 1.0) * TRUST_CTLE,
                             CTLE_GDC2_MIN, CTLE_GDC2_MAX))
        gain = float(np.clip(SEED_GAIN + (sp[i, 10] * 2 - 1.0) * TRUST_GAIN,
                             GAIN_MIN, GAIN_MAX))
        taps = construct_9tap(pre_post, ffe_pre)
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

def _make_objective_a(config, model_a, ffe_pre, ucb_kappa=0.0):
    def objective(x):
        taps = construct_9tap(x[:8], ffe_pre)
        return _predict_a(model_a, config, taps, x[8], x[9], x[10], ucb_kappa)
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

        x_{k+1} = clip( x_k - alpha * PRECOND * g/|g| , 信任域 )

    - 目标：Model A 的负梯度方向（有限差分求得）；ucb_kappa>0 时用 GPR 的 UCB 护栏。
    - 安全：Model B 否决“相对种子点显著恶化”的步子（校准无关的相对红线）。
    - freeze_extra=True：把 CTLE 两维与 driver_gain 冻结在种子值（消融对照）。
    - 只记录真实 BER，不回传。
    """
    objective_a = _make_objective_a(config, model_a, ffe_pre, ucb_kappa)

    # 信任域边界（相对 x0 收紧，并裁剪到全局边界）
    gbounds = _bounds()
    radius = np.array([TRUST_FFE] * 8 + [TRUST_CTLE, TRUST_CTLE, TRUST_GAIN])
    if freeze_extra:
        radius[8:] = 0.0          # 消融：只优化 FFE
    x0 = np.array(x0, dtype=float)
    tr_bounds = np.stack([
        np.maximum(gbounds[:, 0], x0 - radius),
        np.minimum(gbounds[:, 1], x0 + radius),
    ], axis=1)

    safety_limit = safety_ref + SAFETY_MARGIN

    trace = []
    x = x0.copy()

    for step in range(n_steps):
        # 1. 数值梯度 + 归一化下降方向
        g = _numerical_gradient(objective_a, x, eps=0.01)
        gn = np.linalg.norm(g)
        # 梯度门控：代理曲面趋平(外推/无效区)时停止，不沿拟合噪声乱走。
        # 旧版在此处会以 |g|~1e-4 的"噪声方向"继续下降，导致真实 BER 反向爬升。
        if gn < GRAD_GATE:
            print(f"[Stage 2] stop: |grad|={gn:.2e} < gate {GRAD_GATE} "
                  f"(Model A surface flat at step {step})")
            break
        direction = g / gn

        # 2. 回溯线搜索：Model B 保证安全（相对种子点的红线），步长随 step 衰减以收敛
        alpha = lr * (0.92 ** step)
        # 预条件缩放：把量纲差异极大的 FFE(±0.3) / CTLE(±5 dB) / gain(±1) 拉到同一数量级，
        # 否则归一化梯度在 CTLE/gain 维上的实际位移会小到看不见。
        alpha_vec = alpha * PRECOND

        x_new = None
        for _ in range(20):
            x_cand = np.clip(x - alpha_vec * direction, tr_bounds[:, 0], tr_bounds[:, 1])
            taps_c, gdc_c, gdc2_c, gain_c = _x_to_taps_ctle(x_cand, ffe_pre)
            if _predict_b(model_b, taps_c, gdc_c, gdc2_c, gain_c) <= safety_limit:
                x_new = x_cand
                break
            alpha *= 0.5
        if x_new is None:
            break  # 信任域内找不到安全方向，停止

        # 3. 代理预测 + 真实 BER（仅记录验证）
        taps, gdc, gdc2, gain = _x_to_taps_ctle(x_new, ffe_pre)
        pred_a = _predict_a(model_a, config, taps, gdc, gdc2, gain)
        pred_b = _predict_b(model_b, taps, gdc, gdc2, gain)
        real_logber, real_mlse = _physical_eval(config, taps, gdc, gdc2, gain)

        trace.append({
            'step': step,
            'x': x_new,
            'taps': taps,
            'gdc': gdc, 'gdc2': gdc2, 'gain': gain,
            'pred_a': pred_a,
            'pred_b': pred_b,
            'safe': pred_b <= safety_limit,
            'real_logber': real_logber,
            'real_mlse': real_mlse,
            'grad_norm': gn,
        })

        print(f"[Stage 2] gd {step + 1}/{n_steps} | ModelA {10.0 ** pred_a:.2e} "
              f"| ModelB {10.0 ** pred_b:.2e} (safe) | real {real_mlse:.2e} | |g| {gn:.2e}")

        # 4. 收敛判断：位移几乎为零则提前停止
        if np.linalg.norm(x_new - x) < 1e-4:
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