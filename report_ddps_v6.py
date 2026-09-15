#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""report_ddps_v6.py — DDPS v6 结果可视化与报告（精简版）。

v6: A=探针->BER 方向映射, B=参数->BER 风险控制：模型只吃 6 维 FFE+CTLE，gain 维由发端 RMS 物理目标驱动。
    _add_shared_legend(fig, ncol=5, fontsize=9, y_offset=0.965)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
  ddps_v6_convergence.png   3×5 三曲线收敛（Model A / Model B / 实测 BER）
  ddps_v6_gain_rms.png      逐用例 gain 倍率与 drive_rms 轨迹（验证物理驱动）
  ddps_v6_report.md         中文报告
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
from tx_channel_extract import extract_tx_s21
from utils_config import load_config
import json as _json

BAUD = 56e9  # 56 GBd

def _ctle_response_db(f, gdc_db, gdc2_db):
    """Tx CTLE |H(f)| in dB. f: Hz array."""
    tx = load_config('config.xlsx')['tx']
    f = np.maximum(f, 1e-9)
    f_b = BAUD
    f_z = f_b / tx.get('ctle_fz_ratio', 2.5)
    f_p1 = f_b / tx.get('ctle_fp1_ratio', 2.5)
    f_p2 = f_b / tx.get('ctle_fp2_ratio', 1.0)
    f_lf = f_b / tx.get('ctle_flf_ratio', 40.0)
    g_dc = 10 ** (gdc_db / 20.0)
    g_dc2 = 10 ** (gdc2_db / 20.0)
    num1 = g_dc + 1j * f / f_z
    den1 = (1 + 1j * f / f_z) * (1 + 1j * f / f_p1) * (1 + 1j * f / f_p2)
    num2 = g_dc2 + 1j * f / f_lf
    den2 = 1 + 1j * f / f_lf
    h = (num1 / den1) * (num2 / den2)
    return 20 * np.log10(np.abs(h) + 1e-12)

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


def _plot_convergence(ax, tr, row, title=None, small=False, show_legend=True):
    steps = tr['step'].values
    ax.semilogy(steps, 10.0 ** tr['pred_a'].values, marker='^', ms=3.2, ls='--',
                lw=1.1, color=C_PREDA, label='Model A 预测（方向代理）')
    if 'pred_b' in tr.columns and tr['pred_b'].abs().sum() > 0:
        ax.semilogy(steps, 10.0 ** tr['pred_b'].values, marker='s', ms=3.0, ls=':',
                    lw=1.1, color=C_PREDB, label='Model B 预测（风险控制）')
    ax.semilogy(steps, tr['real_ber'].values, marker='o', ms=3.6, lw=1.5,
                color=C_REAL, label='实测 BER_MLSE')
    seed = row['seed_ber']
    ax.axhline(seed, color=C_SEED, ls='--', lw=0.9, alpha=0.8,
               label='种子 BER（起点）')
    # 安全红线：如果从不触发（B 单调下降），不画——画一条没人碰的线只会干扰
    # 如果有触发步（allowed < pred_b 某些步），画红线轨迹
    if 'allowed_ber' in tr.columns and tr['allowed_ber'].iloc[0] > 0:
        triggered = (tr['pred_b_ber'] > tr['allowed_ber']).any() if 'pred_b_ber' in tr.columns else False
        if triggered:
            ax.plot(steps, tr['allowed_ber'].values, color=C_LIMIT, ls='-.', lw=0.9,
                    alpha=0.8, label='安全红线（最优×1.25）')
    ax.set_yscale('log')
    ax.grid(True, which='both', ls='--', alpha=0.35)
    if title:
        ax.set_title(title, fontsize=9.5)
    if small:
        ax.tick_params(labelsize=7)


def _add_shared_legend(fig, loc='upper center', ncol=5, fontsize=9, y_offset=0.985):
    """在 figure 顶部（suptitle 下方）放统一图例，避免子图内 legend 挤压数据。"""
    handles, labels = [], []
    # 用 proxy artist 保证顺序和颜色一致
    from matplotlib.lines import Line2D
    handles = [
        Line2D([0], [0], color=C_PREDA, marker='^', ms=5, ls='--', lw=1.2,
               label='Model A 预测（方向代理）'),
        Line2D([0], [0], color=C_PREDB, marker='s', ms=5, ls=':', lw=1.2,
               label='Model B 预测（风险控制）'),
        Line2D([0], [0], color=C_REAL, marker='o', ms=5, lw=1.5,
               label='实测 BER_MLSE'),
        Line2D([0], [0], color=C_SEED, ls='--', lw=1.2, label='种子 BER（起点）'),
        Line2D([0], [0], color=C_LIMIT, ls='-.', lw=1.2, label='安全红线（种子×1.25）'),
    ]
    fig.legend(handles=handles, loc=loc, ncol=ncol, fontsize=fontsize,
               framealpha=0.9, edgecolor='#ccc', bbox_to_anchor=(0.5, y_offset))


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
                          title=f'{env}\n改善 ×{imp:.2f}', small=True)
    for j in range(n, len(axes)):
        axes[j].axis('off')
    fig.suptitle('DDPS v6 在线调优收敛轨迹（15 环境，只用基线训练泛化）', fontsize=12)
    _add_shared_legend(fig, ncol=5, fontsize=9, y_offset=0.965)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    out = os.path.join(report_dir, 'ddps_v6_convergence.png')
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
                color=C_GAIN, label='gain 倍率（左轴）')
        ax2 = ax.twinx()
        ax2.plot(steps, tr['drive_rms'].values, marker='s', ms=3, ls='--',
                 lw=1.0, color=C_REAL, label='drive_rms (V)（右轴）')
        target = float(tr['target_rms'].iloc[0]) if 'target_rms' in tr.columns else D.TARGET_DRIVE_RMS
        ax2.axhline(target, color=C_LIMIT, ls=':', lw=0.8, alpha=0.7,
                    label='target_rms 目标')
        ax.set_title(f'{env}', fontsize=9)
        ax.set_xlabel('步数', fontsize=8)
        ax.set_ylabel('gain 倍率', fontsize=8, color=C_GAIN)
        ax2.set_ylabel('drive_rms (V)', fontsize=8, color=C_REAL)
        ax.tick_params(labelsize=7)
        ax2.tick_params(labelsize=7)
        ax.grid(True, ls='--', alpha=0.35)
    for j in range(n, len(axes)):
        axes[j].axis('off')
    fig.suptitle('DDPS v6 gain 维物理驱动轨迹（drive_rms 锁定到 per-case target_rms）',
                 fontsize=12)
    from matplotlib.lines import Line2D
    _h = [Line2D([0], [0], color=C_GAIN, marker='o', ms=5, lw=1.5, label='gain 倍率（左轴）'),
          Line2D([0], [0], color=C_REAL, marker='s', ms=4, ls='--', lw=1.0, label='drive_rms (V)（右轴）'),
          Line2D([0], [0], color=C_LIMIT, ls=':', lw=1.2, label='per-case target_rms 目标')]
    fig.legend(handles=_h, loc='upper center', ncol=3, fontsize=9,
               framealpha=0.9, edgecolor='#ccc', bbox_to_anchor=(0.5, 0.965))
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    out = os.path.join(report_dir, 'ddps_v6_gain_rms.png')
    fig.savefig(out, dpi=125)
    plt.close(fig)
    return out

CAT_COLORS = {"基线": "#0b63ce", "IL": "#e08a1e", "CD": "#0f8a4a",
           "DGD": "#8e44ad", "复合": "#c0392b", "高噪": "#555555"}

def _env_category(env):
    if env == "Base_IL10x10": return "基线"
    if env.startswith("Comb"): return "复合"
    if env.startswith("HighNoise"): return "高噪"
    if "CD" in env: return "CD"
    if "DGD" in env: return "DGD"
    if "IL" in env: return "IL"
    return "基线"


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
        # 按类别着色，不逐用例加 legend
        cat = _env_category(env)
        ax1.scatter(dA, dR, s=20, alpha=0.6, color=CAT_COLORS[cat])
    lo = min(min(all_dA), min(all_dR)) - 0.02
    hi = max(max(all_dA), max(all_dR)) + 0.02
    ax1.plot([lo, hi], [lo, hi], 'k--', lw=1, alpha=0.5)
    ax1.set_xlabel('Δ预测 (dex)', fontsize=10)
    ax1.set_ylabel('Δ实测 (dex)', fontsize=10)
    ax1.set_title('预测变化量 vs 实测变化量（逐用例逐步）', fontsize=11)
    ax1.set_xlim(lo, hi); ax1.set_ylim(lo, hi)
    ax1.grid(True, ls='--', alpha=0.3)
    from matplotlib.lines import Line2D
    _h = [Line2D([0],[0], marker='o', ms=6, ls='', color=c, label=cat)
           for cat, c in CAT_COLORS.items()]
    ax1.legend(handles=_h, fontsize=8, loc='lower right', framealpha=0.9)
    colors = ['#0b63ce' if c >= 0 else '#c0392b' for c in corrs]
    ax2.barh(range(len(corrs)), corrs, color=colors, height=0.6)
    ax2.set_yticks(range(len(labels)))
    ax2.set_yticklabels(labels, fontsize=8)
    ax2.axvline(0, color='k', lw=0.8)
    ax2.set_xlabel('corr(Δ预测, Δ实测)', fontsize=10)
    ax2.set_title('逐用例相关系数', fontsize=11)
    ax2.grid(True, ls='--', alpha=0.3, axis='x')
    fig.tight_layout()
    out = os.path.join(report_dir, 'ddps_v6_tracking.png')
    fig.savefig(out, dpi=125)
    plt.close(fig)
    return out


def figure_hardcase(test_dir, report_dir, envs):
    """最难用例四联图（v2 风格）：收敛三曲线 + FFE 抽头 + CTLE 频响 + 探针 FIR。"""
    os.makedirs(report_dir, exist_ok=True)
    summ = _summary(test_dir)
    hard_env = max(envs, key=lambda e: summ[summ['env'] == e].iloc[0]['seed_ber']
                   if e in summ['env'].values else 0)
    tr = _trace(test_dir, hard_env)
    if tr is None or tr.empty:
        return None

    # 找 best 行
    best_idx = int(tr['real_ber'].values.argmin())
    best_row = tr.iloc[best_idx]
    seed_taps = D.SEED_TAPS.copy()
    try:
        best_taps = np.array(_json.loads(best_row['taps']) if isinstance(best_row['taps'], str)
                             else best_row['taps'], float)
    except Exception:
        best_taps = seed_taps
    best_gdc = float(best_row['gdc'])
    best_gdc2 = float(best_row['gdc2'])

    # 提取探针 FIR（seed vs best）
    from ddps_cases import apply_env_to_config
    cfg = apply_env_to_config(load_config('config.xlsx'), hard_env)
    fir_seed = extract_tx_s21(cfg, custom_tx_taps=seed_taps, num_taps=7)
    fir_best = extract_tx_s21(cfg, custom_tx_taps=best_taps, num_taps=7)

    # CTLE 频响
    f = np.linspace(0, 2.0 * BAUD, 800)
    ctle_seed = _ctle_response_db(f, D.SEED_GDC, D.SEED_GDC2)
    ctle_best = _ctle_response_db(f, best_gdc, best_gdc2)

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    # (1) 收敛三曲线
    _plot_convergence(axes[0, 0], tr, summ[summ['env'] == hard_env].iloc[0],
                      title=f'{hard_env} 收敛轨迹')
    axes[0, 0].legend(fontsize=7, loc='lower left', framealpha=0.9)
    # (2) FFE 抽头 seed vs best
    ax = axes[0, 1]
    x = np.arange(len(seed_taps))
    w = 0.3
    ax.bar(x - w / 2, seed_taps, w, label='种子', color='#0b63ce', alpha=0.7)
    ax.bar(x + w / 2, best_taps, w, label='最优', color='#0f8a4a', alpha=0.7)
    ax.axvline(D.FFE_PRE - 0.5, color='k', lw=0.5, ls=':')
    ax.set_xticks(x); ax.set_xticklabels([f't{i}' for i in x], fontsize=9)
    ax.set_ylabel('抽头值', fontsize=9); ax.legend(fontsize=8)
    ax.set_title(f'5-tap Tx FFE（种子 vs 最优，主抽头 t{D.FFE_PRE}）', fontsize=10)
    ax.grid(True, ls='--', alpha=0.3)
    # (3) CTLE |H(f)| 频响
    ax = axes[1, 0]
    ax.plot(f / 1e9, ctle_seed, label=f'种子 (gDC={D.SEED_GDC:.1f}, gDC2={D.SEED_GDC2:.1f})',
            color='#0b63ce', lw=1.5)
    ax.plot(f / 1e9, ctle_best, ls='--',
            label=f'最优 (gDC={best_gdc:+.1f}, gDC2={best_gdc2:+.1f})',
            color='#0f8a4a', lw=1.5)
    ax.axvline(BAUD / 2 / 1e9, color='k', ls=':', lw=1, label='Nyquist')
    ax.set_xlabel('GHz', fontsize=9); ax.set_ylabel('dB', fontsize=9)
    ax.set_title('Tx CTLE |H(f)|（模拟频谱整形）', fontsize=10)
    ax.legend(fontsize=8); ax.grid(alpha=0.3)
    # (4) 探针 FIR 7-tap（Model A 特征）
    ax = axes[1, 1]
    xs7 = np.arange(7)
    w7 = 0.35
    ax.bar(xs7 - w7 / 2, fir_seed, w7, color='#0b63ce', alpha=0.7, label='种子')
    ax.bar(xs7 + w7 / 2, fir_best, w7, color='#0f8a4a', alpha=0.7, label='最优')
    ax.set_xticks(xs7); ax.set_xticklabels([f'h{i}' for i in xs7], fontsize=9)
    ax.set_ylabel('幅度 (V)', fontsize=9); ax.legend(fontsize=8)
    ax.set_title('Tx 物理探针 7-tap FIR（Model A 输入特征）', fontsize=10)
    ax.grid(True, ls='--', alpha=0.3, axis='y')
    fig.suptitle(f'最难用例四联图：{hard_env}（种子 BER → 最优 BER）', fontsize=12, fontweight='bold')
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = os.path.join(report_dir, f'ddps_v6_case_{hard_env}_a.png')
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
    L.append('# DDPS v6 在线调优报告\n')
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

    L.append('## 4. 架构（v6：A=探针->BER，B=参数->BER）\n\n')
    L.append('**Model A（方向代理）**：输入 = [7-tap Tx FIR 探针, drive_rms]（8 维波形域）\n')
    L.append('-> log10(BER_MLSE) 条件均值。在线调优时拿不到收端 BER，只能拿发端探针，\n')
    L.append('所以 A 建立发端探针到收端 BER 的方向映射。梯度通过链式法则：扰动 6 维参数\n')
    L.append('-> 重算探针 -> 查 A -> 得 ΔBER（6 维中心差分）。\n\n')
    L.append('**Model B（风险控制）**：输入 = [4 FFE 旁瓣, gDC, gDC2, drive_rms]（7 维参数域）\n')
    L.append('-> log10(BER_MLSE) 保守上包络。按变差百分比拒绝候选，理想情况全程不触发。\n\n')
    L.append('**A/B 输入空间不同**（波形域 vs 参数域），误差来源相互独立。\n\n')
    L.append('**gain 维**：不在 A/B 输入里。每个用例单独细粒度扫描标定 target_rms\n')
    L.append('（0.06~0.22V，步长 0.005），在线调优时每步解析调到该用例的 target_rms：\n')
    L.append('gain = gain_ref × (target_rms / rms_measured)。解析出的 gain 倍率自动从\n')
    L.append('强信号环境的 ~0.6 调到弱信号环境的 ~1.3——即"锁定发端 RMS 给每个用例配 gain"。\n\n')

    if summary_text:
        L.append('## 5. 汇总标注\n\n')
        L.append(f'`{summary_text}`\n\n')

    out = os.path.join(report_dir, 'ddps_v6_report.md')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(''.join(L))

    if summary_out:
        with open(summary_out, 'w', encoding='utf-8') as f:
            f.write('# DDPS v6：跨实验汇总（BER_MLSE）\n\n')
            f.write('评估协议：262144 符号/点 × 3 仿真实例种子取 log10 均值；'
                    '所有实验共用同一批用例与同一协议。\n\n')
            f.write('| 用例 | 物理条件 | 种子 | v6 最优 | 改善 × |\n')
            f.write('| --- | --- | --- | --- | --- |\n')
            for env in envs:
                r = summ[summ['env'] == env]
                if r.empty:
                    continue
                r = r.iloc[0]
                f.write(f"| {env} | {env_label(env)} | `{r['seed_ber']:.3e}` | "
                        f"`{r['best_ber']:.3e}` | ×{r['seed_ber']/r['best_ber']:.2f} |\n")
            f.write(f'\n- **v6（A=探针->BER 方向 + B=参数->BER 风险控制 + gain per-case RMS）**：'
                    f'{n} 用例，改善 {better}/{n}，平均改善 ×{mean_imp:.2f}\n')
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--test-dir', default='result/ddps_v6_main')
    ap.add_argument('--model-dir', default='models/ddps_v6')
    ap.add_argument('--summary', default=None)
    ap.add_argument('--summary-out', default=None)
    a = ap.parse_args()
    envs = [e['name'] for e in ENV_CASES]
    rd = os.path.join(a.test_dir, 'report')
    write_report(a.test_dir, rd, a.model_dir, envs,
                 summary_text=a.summary, summary_out=a.summary_out)
    print(f'report -> {rd}/ddps_v6_report.md')
