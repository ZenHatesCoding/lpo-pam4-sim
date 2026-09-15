# -*- coding: utf-8 -*-
"""
在 IL20x20 环境上用贝叶斯优化搜全局最优 FFE/CTLE 种子点。

6 维搜索空间：4 FFE 旁瓣 + gDC + gDC2
gain 用 per-case target_rms 物理驱动（IL20x20 target_rms=0.195V）
目标：最小化 log10(BER_MLSE)
"""
import numpy as np
import os, json, math
import ddps_optimizer as D
from ddps_cases import apply_env_to_config
from utils_config import load_config
from main import run_sim
from optimizers.bo_optimizer import BayesianOptimizer

ENV_NAME = 'IL20x20'
N_SYMBOLS = 131072  # BO 阶段用较短符号数加速
FFE_PRE = D.FFE_PRE
TARGET_RMS = 0.195  # IL20x20 的 per-case 标定值


def objective(params):
    """6 维 params -> log10(BER_MLSE)。"""
    pre_post = np.array(params[:4])
    gdc, gdc2 = params[4], params[5]

    # 构造 5-tap FFE
    taps = D.construct_taps(pre_post, FFE_PRE)

    # gain 解析调到 target_rms
    cfg = apply_env_to_config(load_config('config.xlsx'),
                              next(e for e in D.ENV_CASES if e['name'] == ENV_NAME))
    cfg['system']['num_symbols'] = N_SYMBOLS
    D._apply_x_to_config(cfg, gdc, gdc2, D.SEED_GAIN)
    rms = D._measure_drive_rms(cfg, taps, gdc, gdc2, D.SEED_GAIN)
    gain = D.SEED_GAIN * (TARGET_RMS / rms) if rms > 1e-9 else D.SEED_GAIN
    gain = float(np.clip(gain, D.GAIN_MIN, D.GAIN_MAX))

    # 跑仿真
    D._apply_x_to_config(cfg, gdc, gdc2, gain)
    _, mlse_ber = run_sim(cfg, custom_tx_taps=taps, plot_eyes=False)
    return math.log10(max(mlse_ber, 1e-8)), mlse_ber


def main():
    bounds = [
        [-0.3, 0.3],  # FFE 旁瓣 0
        [-0.3, 0.3],  # FFE 旁瓣 1
        [-0.3, 0.3],  # FFE 旁瓣 2
        [-0.3, 0.3],  # FFE 旁瓣 3
        [-5.0, 5.0],  # gDC
        [-5.0, 5.0],  # gDC2
    ]

    bo = BayesianOptimizer(bounds)
    # 修正 kernel length scale：CTLE 维（idx 4,5）用更大量纲
    bo.kernel_l = np.array([0.15, 0.15, 0.15, 0.15, 5.0, 5.0])

    # 初始种子点（Base_IL10x10 的种子，作为 IL20x20 的起点参考）
    seed_pre_post = np.concatenate([D.SEED_TAPS[:FFE_PRE], D.SEED_TAPS[FFE_PRE + 1:]])
    x0 = np.concatenate([seed_pre_post, [D.SEED_GDC, D.SEED_GDC2]])

    print(f"[BO] IL20x20 贝叶斯寻优 | 6 维 | {N_SYMBOLS} 符号/点")
    print(f"[BO] 种子点: {np.round(x0, 4).tolist()}")

    # 评估种子点
    log_ber, ber = objective(x0)
    print(f"[BO] 种子 BER_MLSE = {ber:.4e} (log10={log_ber:.4f})")

    X_train = [x0]
    y_train = [log_ber]

    n_iter = 50
    for i in range(n_iter):
        bo.fit(X_train, y_train, n_hyper_steps=30)
        x_next = bo.suggest_next(n_coarse=1000, n_fine_steps=30)

        log_ber, ber = objective(x_next)
        X_train.append(x_next)
        y_train.append(log_ber)

        best_idx = np.argmin(y_train)
        print(f"[BO] iter {i+1}/{n_iter} | BER={ber:.4e} (log10={log_ber:.4f}) | "
              f"best={y_train[best_idx]:.4f} | x={np.round(x_next, 4).tolist()}")

        # 收敛检查
        if i >= 5 and abs(y_train[best_idx] - y_train[best_idx - 1]) < 0.01:
            print(f"[BO] 收敛，停止")
            break

    best_idx = np.argmin(y_train)
    best_x = X_train[best_idx]
    best_y = y_train[best_idx]

    result = {
        'env': ENV_NAME,
        'best_x': np.round(best_x, 6).tolist(),
        'best_log10_ber': best_y,
        'best_ber': 10 ** best_y,
        'n_iter': len(X_train),
        'best_pre_post': np.round(best_x[:4], 6).tolist(),
        'best_gdc': best_x[4],
        'best_gdc2': best_x[5],
        'seed_pre_post': np.round(seed_pre_post, 6).tolist(),
        'seed_gdc': D.SEED_GDC,
        'seed_gdc2': D.SEED_GDC2,
    }
    print(f"\n[BO] 最优: BER={10**best_y:.4e} | x={np.round(best_x,4).tolist()}")
    print(f"[BO] FFE旁瓣={np.round(best_x[:4],4)} gDC={best_x[4]:.2f} gDC2={best_x[5]:.2f}")

    os.makedirs('result', exist_ok=True)
    with open('result/il20_bo_seed.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"[BO] -> result/il20_bo_seed.json")


if __name__ == '__main__':
    main()
