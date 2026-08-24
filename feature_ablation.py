import os
import numpy as np
import pandas as pd
from datetime import datetime
from scipy.stats import spearmanr, qmc
import create_config, utils_config
import ddps_optimizer as D
import train_surrogates as T

# ============================================================
# Model A 特征消融：找“发端指标”里最能预测（排序）收端 BER 的表征
#
# 候选特征：
#   FIR7    —— 7-tap 等效 FIR（现状）
#   FIR15   —— 15-tap 等效 FIR
#   FIR31   —— 31-tap 等效 FIR
#   CONFIG  —— 9-tap FFE + CTLE（对照：原始配置，非“物理”指标）
#   FIR7+CONFIG / FIR15+CONFIG —— 物理 + 配置 组合
# 模型统一用白盒 Ridge(二阶多项式)。度量：测试集 R² + 排序 Spearman。
# ============================================================


def _features(df, fir_cols, config_cols, combos):
    """按组合返回特征矩阵 dict。"""
    out = {}
    Xc = df[config_cols].values.astype(float)
    for name in combos:
        if name == 'CONFIG':
            out[name] = Xc
        elif name == 'FIR7':
            out[name] = df[fir_cols[:7]].values.astype(float)
        elif name == 'FIR15':
            out[name] = df[fir_cols[:15]].values.astype(float)
        elif name == 'FIR31':
            out[name] = df[fir_cols[:31]].values.astype(float)
        elif name == 'FIR7+CONFIG':
            out[name] = np.hstack([df[fir_cols[:7]].values.astype(float), Xc])
        elif name == 'FIR15+CONFIG':
            out[name] = np.hstack([df[fir_cols[:15]].values.astype(float), Xc])
    return out


def main(n_configs=300, ffe_spread=0.08, ctle_spread=6.0, seed=42):
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

    print(f"Sampling {n_configs} configs, extracting FIR(7/15/31)+config, running BER @26.5dB ...")
    rows = []
    for i in range(n_configs):
        pre_post = seed_pre_post + (sp[i, :8] * 2 - 1.0) * ffe_spread
        ctle = float(np.clip(D.SEED_CTLE + (sp[i, 8] * 2 - 1.0) * ctle_spread,
                             D.CTLE_MIN, D.CTLE_MAX))
        taps = D.construct_9tap(pre_post, ffe_pre)
        base['tx']['ctle_g_dc_db'] = ctle

        fir7 = D.extract_tx_s21(base, custom_tx_taps=taps, num_taps=7, pre_cursors=2)
        fir15 = D.extract_tx_s21(base, custom_tx_taps=taps, num_taps=15, pre_cursors=2)
        fir31 = D.extract_tx_s21(base, custom_tx_taps=taps, num_taps=31, pre_cursors=4)

        logber, mlse = D._physical_eval(base, taps, ctle)

        row = {'ctle_dc': ctle, 'logber': logber}
        for j in range(9):
            row[f'tap_{j}'] = taps[j]
        for j in range(31):
            row[f'fir_{j}'] = fir31[j] if j < 31 else 0.0
        rows.append(row)
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{n_configs}")

    df = pd.DataFrame(rows)
    fir_cols = [f'fir_{j}' for j in range(31)]
    config_cols = [f'tap_{j}' for j in range(9)] + ['ctle_dc']
    y = df['logber'].values.astype(float)

    combos = ['FIR7', 'FIR15', 'FIR31', 'CONFIG', 'FIR7+CONFIG', 'FIR15+CONFIG']
    F = _features(df, fir_cols, config_cols, combos)

    tr, te = T._train_test_split_idx(len(df), 0.2, seed=42)
    print(f"\n{'feature':<14} {'n_feat':>6} {'test R2':>8} {'test Spearman':>14}")
    results = {}
    for name in combos:
        X = F[name]
        model = T.WhiteBoxRidge(2, 1.0).fit(X[tr], y[tr])
        pred = model.predict(X[te])
        r2 = T._r2_score(y[te], pred)
        sp = spearmanr(pred, y[te]).correlation
        results[name] = (r2, sp)
        print(f"{name:<14} {X.shape[1]:>6} {r2:>8.3f} {sp:>14.3f}")

    out_dir = os.path.join("result", f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_feature_ablation")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "summary.md"), "w", encoding='utf-8') as f:
        f.write("# Model A 特征消融（白盒 Ridge 二阶多项式，26.5 dB）\n\n")
        f.write("| 特征 | 维度 | 测试 R² | 测试 Spearman |\n| --- | --- | --- | --- |\n")
        for name in combos:
            f.write(f"| {name} | {F[name].shape[1]} | `{results[name][0]:.3f}` | `{results[name][1]:.3f}` |\n")
    print(f"\nSaved to {out_dir}/summary.md")
    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--n-configs', type=int, default=300)
    args = parser.parse_args()
    main(n_configs=args.n_configs)
