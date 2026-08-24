import os
import numpy as np
import pandas as pd
from datetime import datetime
from scipy.stats import spearmanr, qmc
import create_config, utils_config
import ddps_optimizer as D
import train_surrogates as T

# ============================================================
# 跨 SNR 排序实验：离线标定（Model A，发端 FIR → logBER）的“排序”能否跨链路条件迁移
#
# 背景（两阶段底线的核心）：
#   Stage 1 离线标定——可以崩、可以拿到真实端到端 BER；在某个 SNR（如 26.5 dB）训 Model A。
#   Stage 2 在线调优——不能崩、只能拿发端指标；可能工作在另一个 SNR（如 28 dB）。
# 问题：离线学到的“哪个配置更好”的排序，在线条件（不同 SNR）下还成不成立？
#
# 做法：
#   1. 邻域采 N 个配置（好→坏都有）；
#   2. 每个配置：提取发端 FIR（与 SNR 无关）+ 在多个 SNR 下跑真实 BER；
#   3. 用 26.5 dB 训 Model A（FIR → logBER）；
#   4. 对每个 SNR 算 Spearman( ModelA预测 , 真实logBER )；
#      同时算 Spearman( 真实26.5 , 真实@SNR ) 作为“真实排序本身跨 SNR 漂移”的上限参照。
# ============================================================

SNRS = [24.0, 26.5, 28.0, 30.0]
TRAIN_SNR = 26.5


def main(n_configs=150, ffe_spread=0.08, ctle_spread=6.0, seed=42):
    create_config.generate_config()
    base = utils_config.load_config('config.xlsx')
    base['system']['enable_eye_plot'] = False
    base['system']['enable_spectrum_plot'] = False
    ffe_pre = int(base['tx'].get('ffe_pre', 4))

    seed_pre_post = np.zeros(8)
    seed_pre_post[:ffe_pre] = D.SEED_TAPS[:ffe_pre]
    seed_pre_post[ffe_pre:] = D.SEED_TAPS[ffe_pre + 1:]

    sampler = qmc.LatinHypercube(d=9, seed=seed)
    sp = sampler.random(n=n_configs)

    print(f"Evaluating {n_configs} configs at SNR {SNRS} ...")
    rows = []
    for i in range(n_configs):
        pre_post = seed_pre_post + (sp[i, :8] * 2 - 1.0) * ffe_spread
        ctle = float(np.clip(D.SEED_CTLE + (sp[i, 8] * 2 - 1.0) * ctle_spread,
                             D.CTLE_MIN, D.CTLE_MAX))
        taps = D.construct_9tap(pre_post, ffe_pre)

        # 发端 FIR 与 SNR 无关，提取一次
        base['tx']['ctle_g_dc_db'] = ctle
        tx_fir = D.extract_tx_s21(base, custom_tx_taps=taps, num_taps=7)

        row = {'ctle_dc': ctle}
        for j in range(7):
            row[f'tx_fir_{j}'] = tx_fir[j]

        for snr in SNRS:
            base['channel']['snr_db'] = snr
            logber, _ = D._physical_eval(base, taps, ctle)
            row[f'logber_{snr}'] = logber
        rows.append(row)
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{n_configs}")

    df = pd.DataFrame(rows)

    # 用 26.5 dB 训 Model A
    XA = df[[f'tx_fir_{i}' for i in range(7)]].values.astype(float)
    y_train = df[f'logber_{TRAIN_SNR}'].values.astype(float)
    ma = T.WhiteBoxRidge(2, 1.0).fit(XA, y_train)
    pred = ma.predict(XA)

    # 计算 Spearman
    table = []
    for snr in SNRS:
        real = df[f'logber_{snr}'].values
        sp_pred = spearmanr(pred, real).correlation
        sp_true = spearmanr(y_train, real).correlation
        table.append((snr, sp_pred, sp_true))
        print(f"SNR {snr:>5} dB | Spearman(ModelA pred, real) = {sp_pred:+.3f} | "
              f"Spearman(real26.5, real) = {sp_true:+.3f}")

    # 图
    out_dir = os.path.join("result", "latest_comparison", "ddps")
    os.makedirs(out_dir, exist_ok=True)
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        snrs_arr = [t[0] for t in table]
        sp_preds = [t[1] for t in table]
        sp_trues = [t[2] for t in table]
        plt.figure(figsize=(8, 5))
        plt.plot(snrs_arr, sp_preds, 'o-', label='Spearman(ModelA 26.5dB pred, real@SNR)')
        plt.plot(snrs_arr, sp_trues, 's--', label='Spearman(real26.5, real@SNR) [ranking drift ceiling]')
        plt.xlabel('SNR (dB)')
        plt.ylabel('Spearman rank correlation')
        plt.title('Cross-SNR ranking transfer of offline-calibrated Model A')
        plt.grid(True, ls='--', alpha=0.6)
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, "cross_snr_ranking.png"))
        plt.close()
        print(f"Figure saved to {out_dir}/cross_snr_ranking.png")
    except Exception as e:
        print(f"(figure skipped: {e})")

    # 落盘
    df.to_csv(os.path.join("result", f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_cross_snr.csv"),
              index=False)
    return table


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--n-configs', type=int, default=150)
    args = parser.parse_args()
    main(n_configs=args.n_configs)
