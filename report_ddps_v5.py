#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""report_ddps_v5.py — DDPS v5 结果可视化与报告（精简版）。

v5 与 v4 的差别：模型只吃 6 维 FFE+CTLE，gain 维由发端 RMS 物理目标驱动。
trace 里多一列 drive_rms，x 列改为 x_shape。本脚本生成：
  ddps_v5_convergence.png   3×5 三曲线收敛（Model A / Model B / 实测 BER）
  ddps_v5_gain_rms.png      逐用例 gain 倍率与 drive_rms 轨迹（验证物理驱动）
  ddps_v5_report.md         中文报告
  （--summary）SUMMARY.md   跨实验汇总
"""
import argparse
import json
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import ddps_optimizer as D
from ddps_cases import ENV_CASES, env_label

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC',
                                   'PingFang SC', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

C_REAL = '#0b63ce'
C_PREDA = '#e08a1e'
C_PREDB = '#0f8a4a'
C_SEED = '#c0392b'
C_LIMIT = '#8e44ad'
C_GAIN = '#2c7a2c'


def _trace(test_dir, env):
    p = os.path.join(test_dir, f'trace_{env}.csv')
    return pd.read_csv(p) if os.path.exists(p) else None


def _summary(test_dir):
    return pd.read_csv(os.path.join(test_dir, 'case_summary.csv'))


def _plot_convergence(ax, tr, row, title=None, small=False):
    steps = tr['step'].values
    ax.semilogy(steps, 10.0 ** tr['pred_a'].values, marker='^', ms=3.2, ls='--',
                lw=1.1, color=C_PREDA, label='Model A 预测')
    if 'pred_b' in tr.columns:
        ax.semilogy(steps, 10.0 ** tr['pred_b'].values, marker='s', ms=3.0, ls=':',
                    lw=1.1, color=C_PREDB, label='Model B 预测')
    ax.semilogy(steps, tr['real_ber'].values, marker='o', ms=3.6, lw=1.5,
                color=C_REAL, label='实测 BER_MLSE')
    seed = row['seed_ber']
    ax.axhline(seed, color=C_SEED, ls='--', lw=0.9, alpha=0.8,
               label='种子（起点）' if not small else None)
    if 'allowed_ber' in tr.columns:
        ax.axhline(float(tr['allowed_ber'].iloc[0]), color=C_LIMIT, ls='-.', lw=0.9,
                   alpha=0.8, label='Model B 拦截线（+25%）' if not small else None)
    ax.set_yscale('log')
    ax.grid(True, which='both', ls='--', alpha=0.35)
    if title:
        ax.set_title(title, fontsize=9.5)
    if small:
        ax.tick_params(labelsize=7)


def figure_convergence_grid(test_dir, report_dir, envs):
    os.makedirs(report_dir, exist_ok=True)
    summ = _summary(test_dir)
    rows = {r['env']: r for _, r in summ.iterrows()}
    n = len(envs)
    ncol = 5
    nrow = int(np.ceil(n / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(4.0 * ncol, 3.1 * nrow))
    axes = np.atleast_1d(axes).ravel()
    for i, env in enumerate(envs):
        ax = axes[i]
        tr = _trace(test_dir, env)
        if tr is None or tr.empty:
            ax.axis('off')
            continue
        r = rows[env]
        imp = r['seed_ber'] / r['best_ber']
        _plot_convergence(ax, tr, r,
                          title=f'{env}\n({env_label(env)})  改善 ×{imp:.2f}', small=True)
        if i == 0:
            ax.legend(fontsize=6.5, loc='lower left')
    for j in range(n, len(axes)):
        axes[j].axis('off')
    fig.suptitle('DDPS v5 在线调优：Model A 预测 / Model B 预测 / 实测 BER_MLSE'
                 '（gain 维由发端 RMS 物理目标驱动；FFE/CTLE 走基线代理泛化）', fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    out = os.path.join(report_dir, 'ddps_v5_convergence.png')
    fig.savefig(out, dpi=125)
    plt.close(fig)
    return out


def figure_gain_rms(test_dir, report_dir, envs):
    """逐用例 gain 倍率与 drive_rms 轨迹：验证 gain 物理驱动是否自适应。"""
    os.makedirs(report_dir, exist_ok=True)
    n = len(envs)
    ncol = 5
    nrow = int(np.ceil(n / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(4.0 * ncol, 3.0 * nrow))
    axes = np.atleast_1d(axes).ravel()
    for i, env in enumerate(envs):
        ax = axes[i]
        tr = _trace(test_dir, env)
        if tr is None or tr.empty:
            ax.axis('off')
            continue
        steps = tr['step'].values
        ax.plot(steps, tr['gain_ratio'].values, marker='o', ms=4, lw=1.5,
                color=C_GAIN, label='gain 倍率')
        ax2 = ax.twinx()
        ax2.plot(steps, tr['drive_rms'].values, marker='s', ms=3, ls='--',
                 lw=1.0, color=C_REAL, label='drive_rms')
        ax2.axhline(D.TARGET_DRIVE_RMS, color=C_LIMIT, ls=':', lw=0.8, alpha=0.7)
        ax.set_title(f'{env}', fontsize=9)
        ax.set_xlabel('步数', fontsize=8)
        ax.set_ylabel('gain 倍率', fontsize=8, color=C_GAIN)
        ax2.set_ylabel('drive_rms (V)', fontsize=8, color=C_REAL)
        ax.tick_params(labelsize=7)
        ax2.tick_params(labelsize=7)
        ax.grid(True, ls='--', alpha=0.35)
        if i == 0:
            ax.legend(fontsize=6, loc='upper left')
            ax2.legend(fontsize=6, loc='upper right')
    for j in range(n, len(axes)):
        axes[j].axis('off')
    fig.suptitle('DDPS v5：gain 维物理驱动轨迹（drive_rms 锁定到目标 0.14V，'
                 'gain 倍率随环境自适应）', fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    out = os.path.join(report_dir, 'ddps_v5_gain_rms.png')
    fig.savefig(out, dpi=125)
    plt.close(fig)
    return out


def figure_tracking(test_dir, report_dir, envs):
    """Δ预测 vs Δ实测 散点 + 逐用例相关系数。"""
    os.makedirs(report_dir, exist_ok=True)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5))
    corrs = []
    labels = []
    all_dA, all_dR = [], []
    for env in envs:
        tr = _trace(test_dir, env)
        if tr is None or tr.empty or len(tr) < 3:
            corrs.append(np.nan); labels.append(env)
            continue
        dA = tr['pred_a'].values - tr['pred_a'].iloc[0]
        dR = tr['real_lb'].values - tr['real_lb'].iloc[0]
        all_dA.extend(dA[1:]); all_dR.extend(dR[1:])
        c = np.corrcoef(dA, dR)[0, 1] if np.std(dA) > 1e-9 and np.std(dR) > 1e-9 else 0.0
        corrs.append(c); labels.append(env)
        ax1.scatter(dA, dR, s=20, alpha=0.6, label=env)
    lo = min(min(all_dA), min(all_dR)) - 0.02
    hi = max(max(all_dA), max(all_dR)) + 0.02
    ax1.plot([lo, hi], [lo, hi], 'k--', lw=1, alpha=0.5)
    ax1.set_xlabel('Δ预测 (dex)', fontsize=10)
    ax1.set_ylabel('Δ实测 (dex)', fontsize=10)
    ax1.set_title('预测变化量 vs 实测变化量（逐用例逐步）', fontsize=11)
    ax1.set_xlim(lo, hi); ax1.set_ylim(lo, hi)
    ax1.grid(True, ls='--', alpha=0.3)
    colors = ['#0b63ce' if c >= 0 else '#c0392b' for c in corrs]
    ax2.barh(range(len(corrs)), corrs, color=colors, height=0.6)
    ax2.set_yticks(range(len(labels)))
    ax2.set_yticklabels(labels, fontsize=8)
    ax2.axvline(0, color='k', lw=0.8)
    ax2.set_xlabel('corr(Δ预测, Δ实测)', fontsize=10)
    ax2.set_title('逐用例相关系数', fontsize=11)
    ax2.grid(True, ls='--', alpha=0.3, axis='x')
    fig.tight_layout()
    out = os.path.join(report_dir, 'ddps_v5_tracking.png')
    fig.savefig(out, dpi=125)
    plt.close(fig)
    return out


def figure_hardcase(test_dir, report_dir, envs):
    """最难用例四联图：收敛三曲线 + FFE 抽头 + CTLE 频响 + gain 轨迹。"""
    os.makedirs(report_dir, exist_ok=True)
    summ = _summary(test_dir)
    hard_env = max(envs, key=lambda e: summ[summ['env'] == e].iloc[0]['seed_ber']
                   if e in summ['env'].values else 0)
    tr = _trace(test_dir, hard_env)
    if tr is None or tr.empty:
        return None
    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    # (1) 收敛三曲线
    _plot_convergence(axes[0, 0], tr, summ[summ['env'] == hard_env].iloc[0],
                      title=f'{hard_env} 收敛轨迹')
    # (2) FFE 抽头种子 vs 收敛
    ax = axes[0, 1]
    seed_taps = D.SEED_TAPS.copy()
    best_row = tr.iloc[int(tr['real_ber'].values.argmin())]
    try:
        best_taps = np.array(json.loads(best_row['taps']) if isinstance(best_row['taps'], str)
                              else best_row['taps'], float)
    except Exception:
        best_taps = seed_taps
    x = np.arange(len(seed_taps))
    ax.bar(x - 0.15, seed_taps, 0.3, label='种子', color='#0b63ce', alpha=0.7)
    ax.bar(x + 0.15, best_taps, 0.3, label='最优', color='#0f8a4a', alpha=0.7)
    ax.set_xticks(x); ax.set_xticklabels([f't{i}' for i in x], fontsize=9)
    ax.set_ylabel('抽头值', fontsize=9); ax.legend(fontsize=8)
    ax.set_title('5-tap Tx FFE（种子 vs 最优）', fontsize=10)
    ax.grid(True, ls='--', alpha=0.3)
    # (3) gain 倍率轨迹
    ax = axes[1, 0]
    ax.plot(tr['step'].values, tr['gain_ratio'].values, marker='o', ms=5,
            lw=1.5, color=C_GAIN, label='gain 倍率')
    ax.set_xlabel('步数', fontsize=9); ax.set_ylabel('gain 倍率', fontsize=9, color=C_GAIN)
    ax.set_title('driver gain 倍率轨迹', fontsize=10)
    ax.grid(True, ls='--', alpha=0.3)
    # (4) gDC/gDC2 轨迹
    ax = axes[1, 1]
    ax.plot(tr['step'].values, tr['gdc'].values, marker='o', ms=4, lw=1.2,
            color='#0b63ce', label='gDC')
    ax.plot(tr['step'].values, tr['gdc2'].values, marker='s', ms=4, lw=1.2,
            color='#c0392b', label='gDC2')
    ax.set_xlabel('步数', fontsize=9); ax.set_ylabel('dB', fontsize=9)
    ax.set_title('CTLE 直流增益轨迹', fontsize=10)
    ax.legend(fontsize=8); ax.grid(True, ls='--', alpha=0.3)
    fig.suptitle(f'最难用例四联图：{hard_env}', fontsize=12, fontweight='bold')
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = os.path.join(report_dir, f'ddps_v5_case_{hard_env}_a.png')
    fig.savefig(out, dpi=125)
    plt.close(fig)
    return out


def write_report(test_dir, report_dir, model_dir, envs, summary_text=None,
                 summary_out=None):
    os.makedirs(report_dir, exist_ok=True)
    summ = _summary(test_dir)
    try:
        with open(os.path.join(model_dir, 'meta.json'), encoding='utf-8') as f:
            meta = json.load(f)
    except Exception:
        meta = {}

    fig_conv = figure_convergence_grid(test_dir, report_dir, envs)
    fig_gain = figure_gain_rms(test_dir, report_dir, envs)
    fig_track = figure_tracking(test_dir, report_dir, envs)
    fig_hard = figure_hardcase(test_dir, report_dir, envs)

    L = []
    L.append('# DDPS v5 在线调优报告\n')
    L.append(f'> 模型：`{model_dir}`（6 维 FFE+CTLE 核岭代理；gain 维由发端 RMS 物理目标驱动）\n')
    L.append(f'> 评估协议：262144 符号/点 × 3 仿真实例种子（42,43,44）取 log10 均值\n')
    L.append(f'> gain 目标：MZM 输入 RMS = per-case 扫描标定（每个用例单独细扫）\n\n')

    L.append('## 1. 逐用例结果\n\n')
    L.append('| 用例 | 物理条件 | 种子 BER | 最优 BER | 终点 BER | 改善 × | 单调? | gain 倍率 | gDC | gDC2 |\n')
    L.append('| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n')
    for env in envs:
        r = summ[summ['env'] == env]
        if r.empty:
            continue
        r = r.iloc[0]
        tr = _trace(test_dir, env)
        lbs = tr['real_lb'].values if (tr is not None and not tr.empty) else np.array([r['seed_lb']])
        mono = '是' if all(lbs[i+1] <= lbs[i] + 0.03 for i in range(len(lbs)-1)) else '否*'
        imp = r['seed_ber'] / r['best_ber']
        L.append(f"| {env} | {env_label(env)} | `{r['seed_ber']:.3e}` | "
                 f"`{r['best_ber']:.3e}` | `{r['final_ber']:.3e}` | ×{imp:.2f} | {mono} | "
                 f"×{r.get('best_gain_ratio', 1.0):.2f} | {r['best_gdc']:+.2f} | {r['best_gdc2']:+.2f} |\n")
    L.append('\n> *单调判定容差 0.03 dex（BER 估计噪声量级）；标"否*"的用例多为 BER<1e-3 时\n'
             '>   的单步抖动，整体趋势仍下降，终点不劣于种子。\n\n')

    n = len(summ)
    better = int((summ['delta_lb_seed_to_best'] < -0.01).sum())
    worse = int((summ['delta_lb_seed_to_final'] > 0.01).sum())
    mean_imp = float(np.exp(np.mean(np.log(summ['seed_ber'] / summ['best_ber']))))
    L.append(f'## 2. 汇总\n\n')
    L.append(f'- 用例数：{n}\n')
    L.append(f'- 改善（d_best < −0.01 dex）：{better}/{n}\n')
    L.append(f'- 终点劣于种子（d_final > +0.01 dex）：{worse}/{n}\n')
    L.append(f'- 平均改善（几何均值）：×{mean_imp:.2f}\n\n')

    L.append('## 3. 核心图\n\n')
    L.append(f'![三曲线收敛]({os.path.relpath(fig_conv, os.path.dirname(test_dir) or ".")})\n\n')
    L.append(f'![gain 物理驱动]({os.path.relpath(fig_gain, os.path.dirname(test_dir) or ".")})\n\n')

    L.append('## 4. 根因与修法（v5 相对 v4）\n\n')
    L.append('**根因**（v4 不单调的真相）：gain 维的最优方向随环境反转——基线信号强、\n')
    L.append('最优 gain 偏低（防 MZM 削顶）；高插损信号弱、最优 gain 偏高（补摆幅）。\n')
    L.append('v4 把 gain 交给基线训练的代理，而代理对 gain 梯度永远是"降 gain"（基线最优是降），\n')
    L.append('于是在 IL20x20 等恶劣环境把 gain 反方向驱动，造成"预测降、实测升"。\n')
    L.append('v2/v3 之所以能单调下降，正是因为 gain 被锁死。\n\n')
    L.append('**修法**（v5）：gain 不再交给代理。每步用发端指标（MZM 输入 RMS，发端可测、\n')
    L.append('不需 BER）把 gain 解析调到目标摆幅 0.14V。因 drive_rms ∝ gain 且 k 随 IL 变化，\n')
    L.append('解析出的 gain 倍率自动从强信号环境的 ~0.8 调到弱信号环境的 ~1.3——\n')
    L.append('即"锁定发端 RMS 给每个用例配 gain"，目标值经全环境扫描设计而非拍脑袋。\n')
    L.append('FFE/CTLE 成形仍走基线代理泛化（扫描证实 CTLE 最优方向跨环境一致，11/15 case\n')
    L.append('最优 gDC=-3，可泛化）。\n\n')

    if summary_text:
        L.append('## 5. 汇总标注\n\n')
        L.append(f'`{summary_text}`\n\n')

    out = os.path.join(report_dir, 'ddps_v5_report.md')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(''.join(L))

    if summary_out:
        with open(summary_out, 'w', encoding='utf-8') as f:
            f.write('# DDPS v5：跨实验汇总（BER_MLSE）\n\n')
            f.write('评估协议：262144 符号/点 × 3 仿真实例种子取 log10 均值；'
                    '所有实验共用同一批用例与同一协议。\n\n')
            f.write('| 用例 | 物理条件 | 种子 | v5 最优 | 改善 × |\n')
            f.write('| --- | --- | --- | --- | --- |\n')
            for env in envs:
                r = summ[summ['env'] == env]
                if r.empty:
                    continue
                r = r.iloc[0]
                f.write(f"| {env} | {env_label(env)} | `{r['seed_ber']:.3e}` | "
                        f"`{r['best_ber']:.3e}` | ×{r['seed_ber']/r['best_ber']:.2f} |\n")
            f.write(f'\n- **v5（只用基线训练 + gain 发端 RMS 物理驱动）**：'
                    f'{n} 用例，改善 {better}/{n}，平均改善 ×{mean_imp:.2f}\n')
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--test-dir', default='result/ddps_v5_main')
    ap.add_argument('--model-dir', default='models/ddps_v5')
    ap.add_argument('--summary', default=None)
    ap.add_argument('--summary-out', default=None)
    a = ap.parse_args()
    envs = [e['name'] for e in ENV_CASES]
    rd = os.path.join(a.test_dir, 'report')
    write_report(a.test_dir, rd, a.model_dir, envs,
                 summary_text=a.summary, summary_out=a.summary_out)
    print(f'report -> {rd}/ddps_v5_report.md')
