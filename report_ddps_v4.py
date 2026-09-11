#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""report_ddps_v4.py — DDPS v4 结果可视化与报告。

核心图（v2 风格，本版重点恢复）：
  ddps_v4_convergence.png        3×5 面板：每个用例下 **Model A 预测 / Model B 预测 / 实测 BER_MLSE**
                                 三条曲线 vs Stage-2 步数（虚线为种子水平与 Model B 拦截线）
                                 —— 用来直接看在线调优是否单调下降、以及 A/B 是否跟得上真实。
  ddps_v4_case_<env>_a.png       单用例四联图：收敛（三曲线）/ FFE 抽头 / CTLE 频响 / 增益倍率轨迹
  ddps_v4_case_<env>_b.png       节点视图：Rx 眼图（种子 vs 最优）/ FFE 输出分布 / Tx 频谱
  ddps_v4_overview.png           逐用例改善总览
  deep_check.csv                 长块独立复核（--deep-symbols）
  ddps_v4_report.md              中文报告
跨实验汇总（--summary）另生成 fig_delta_compare.png 与 SUMMARY.md。
"""
import argparse
import json
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import create_config
import utils_config
import ddps_optimizer as D
from ddps_cases import ENV_CASES, env_case, apply_env_to_config, env_label
from main import run_sim

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC',
                                   'PingFang SC', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

C_REAL = '#0b63ce'
C_PREDA = '#e08a1e'
C_PREDB = '#0f8a4a'
C_SEED = '#c0392b'
C_LIMIT = '#8e44ad'


# ---------------------------------------------------------------------------
# 物理量助手
# ---------------------------------------------------------------------------

def ctle_response_db(f, baud_rate, gdc, gdc2,
                     fz_ratio=2.5, fp1_ratio=2.5, fp2_ratio=1.0, flf_ratio=40.0):
    """Tx 模拟 CTLE 的 |H(f)|（dB），与 channel_imdd.apply_ctle 同式。"""
    f = np.asarray(f, dtype=float)
    f_z = baud_rate / fz_ratio
    f_p1 = baud_rate / fp1_ratio
    f_p2 = baud_rate / fp2_ratio
    f_lf = baud_rate / flf_ratio
    g_dc = 10 ** (gdc / 20)
    g_dc2 = 10 ** (gdc2 / 20)
    H = ((g_dc + 1j * f / f_z) / ((1 + 1j * f / f_z) * (1 + 1j * f / f_p1) * (1 + 1j * f / f_p2))
         * (g_dc2 + 1j * f / f_lf) / (1 + 1j * f / f_lf))
    return 20 * np.log10(np.abs(H) + 1e-12)


def eye_diagram(ax, x, sps, span=2, title=''):
    n = (len(x) // (sps * span)) * sps * span
    seg = x[:n].reshape(-1, sps * span)
    t = np.arange(sps * span) / sps
    for row in seg[:600]:
        ax.plot(t, row, color=C_REAL, alpha=0.06, lw=0.6)
    ax.set_title(title, fontsize=9)
    ax.grid(True, ls='--', alpha=0.35)


def _trace(test_dir, env):
    p = os.path.join(test_dir, f'trace_{env}.csv')
    return pd.read_csv(p) if os.path.exists(p) else None


def _summary(test_dir):
    return pd.read_csv(os.path.join(test_dir, 'case_summary.csv'))


# ---------------------------------------------------------------------------
# 核心图：三曲线收敛
# ---------------------------------------------------------------------------

def _plot_convergence(ax, tr, row, title=None, small=False):
    """在一个轴上画 Model A 预测 / Model B 预测 / 实测 BER 三条曲线。"""
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
    else:
        ax.set_xlabel('Stage-2 步数')
        ax.set_ylabel('BER_MLSE')


def figure_convergence_grid(test_dir, report_dir, envs):
    os.makedirs(report_dir, exist_ok=True)
    """3×5 网格：每个用例一张三曲线收敛图（v2 风格的核心交付图）。"""
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
        _plot_convergence(ax, tr, r, title=f'{env}\n({env_label(env)})  改善 ×{imp:.2f}', small=True)
        if i == 0:
            ax.legend(fontsize=6.5, loc='lower left')
    for j in range(n, len(axes)):
        axes[j].axis('off')
    fig.suptitle('DDPS v4 在线调优：每个用例的 Model A 预测 / Model B 预测 / 实测 BER_MLSE'
                 '（所有曲线共用对数纵轴；虚红线为种子、紫点划线为 Model B 拦截线）', fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    out = os.path.join(report_dir, 'ddps_v4_convergence.png')
    fig.savefig(out, dpi=125)
    plt.close(fig)
    return out


def figure_case(test_dir, env_name, report_dir, baud_rate):
    os.makedirs(report_dir, exist_ok=True)
    tr = _trace(test_dir, env_name)
    if tr is None or tr.empty:
        return None
    summ = _summary(test_dir)
    row = summ[summ['env'] == env_name].iloc[0]
    best_taps = np.array(json.loads(row['best_taps'])) if isinstance(row['best_taps'], str) \
        else np.array(row['best_taps'])

    fig, axs = plt.subplots(2, 2, figsize=(12.5, 7.6))

    _plot_convergence(axs[0, 0], tr, row, title='收敛：Model A / Model B / 实测')
    axs[0, 0].legend(fontsize=7.5)

    ax = axs[0, 1]
    idx = np.arange(len(best_taps))
    ax.bar(idx - 0.2, D.SEED_TAPS, width=0.4, label='种子', color='#8fa3ba')
    ax.bar(idx + 0.2, best_taps, width=0.4, label='最优', color=C_REAL)
    ax.set_xticks(idx)
    ax.set_xticklabels([f't{i}' for i in range(len(best_taps))], fontsize=8)
    ax.set_title(f'Tx FFE {len(best_taps)}-tap（t{int((len(best_taps)-1)/2)} 为主抽头，派生）', fontsize=10)
    ax.grid(True, axis='y', ls='--', alpha=0.5)
    ax.legend(fontsize=8)

    ax = axs[1, 0]
    f = np.linspace(1e9, 60e9, 400)
    ax.plot(f / 1e9, ctle_response_db(f, baud_rate, D.SEED_GDC, D.SEED_GDC2),
            label=f'种子 (gDC={D.SEED_GDC:g}, gDC2={D.SEED_GDC2:g})', color='#8fa3ba')
    ax.plot(f / 1e9, ctle_response_db(f, baud_rate, row['best_gdc'], row['best_gdc2']),
            label=f'最优 (gDC={row["best_gdc"]:.2f}, gDC2={row["best_gdc2"]:.2f})', color=C_REAL)
    ax.axvline(baud_rate / 2 / 1e9, color='k', ls=':', lw=0.8, label='Nyquist')
    ax.set_xlabel('频率 (GHz)')
    ax.set_ylabel('|H(f)| (dB)')
    ax.set_title('Tx 模拟 CTLE 频响（电插损之后 / Driver 之前）', fontsize=10)
    ax.grid(True, ls='--', alpha=0.5)
    ax.legend(fontsize=8)

    ax = axs[1, 1]
    if 'gain_ratio' in tr.columns:
        ax.plot(tr['step'].values, tr['gain_ratio'].values, marker='o', ms=4, color='#0f8a4a')
        ax.axhline(1.0, color=C_SEED, ls=':', label='种子（×1.00 标定）')
        ax.set_ylabel('driver_gain 倍率（相对标定值）')
        ax.set_xlabel('Stage-2 步数')
        ax.set_title(f'driver_gain 轨迹：×{tr["gain_ratio"].iloc[0]:.2f} → '
                     f'×{tr["gain_ratio"].iloc[-1]:.2f}', fontsize=10)
        ax.grid(True, ls='--', alpha=0.5)
        ax.legend(fontsize=8)

    fig.suptitle(f'DDPS v4 case: {env_name}  ({env_label(env_name)})', fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = os.path.join(report_dir, f'ddps_v4_case_{env_name}_a.png')
    fig.savefig(out, dpi=115)
    plt.close(fig)
    return out


def figure_nodes(test_dir, env_name, report_dir, num_symbols=32768):
    os.makedirs(report_dir, exist_ok=True)
    summ = _summary(test_dir)
    row = summ[summ['env'] == env_name].iloc[0]
    env = env_case(env_name)
    if not os.path.exists('config.xlsx'):
        create_config.generate_config()
    cfg = apply_env_to_config(utils_config.load_config('config.xlsx'), env)
    cfg['system']['num_symbols'] = int(num_symbols)
    best_taps = np.array(json.loads(row['best_taps'])) if isinstance(row['best_taps'], str) \
        else np.array(row['best_taps'])

    def run(taps, gdc, gdc2, gain):
        c = {k: (dict(v) if isinstance(v, dict) else v) for k, v in cfg.items()}
        D._apply_x_to_config(c, gdc, gdc2, gain)
        return run_sim(c, custom_tx_taps=taps, plot_eyes=False, output_dir=None,
                       return_nodes=True)

    _, _, n_seed = run(D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2, D.SEED_GAIN)
    _, _, n_best = run(best_taps, row['best_gdc'], row['best_gdc2'],
                       row.get('best_gain', D.SEED_GAIN))

    sps = int(cfg['system']['sps_channel'])
    fs = cfg['system']['baud_rate'] * sps
    fig, axs = plt.subplots(2, 2, figsize=(12.5, 7.6))
    eye_diagram(axs[0, 0], n_seed['rx_analog'], sps, 2, 'Rx ADC 输入眼图 — 种子')
    eye_diagram(axs[0, 1], n_best['rx_analog'], sps, 2, 'Rx ADC 输入眼图 — 最优')
    axs[0, 0].set_ylabel('幅度 (a.u.)')
    axs[1, 0].hist(n_seed['rx_eq'], bins=120, alpha=0.6, label='种子', color='#8fa3ba', density=True)
    axs[1, 0].hist(n_best['rx_eq'], bins=120, alpha=0.6, label='最优', color=C_REAL, density=True)
    axs[1, 0].set_title('Rx FFE 均衡输出分布', fontsize=9)
    axs[1, 0].grid(True, ls='--', alpha=0.4)
    axs[1, 0].legend(fontsize=8)
    for sig, lab, col in ((n_seed['tx_analog'], '种子', '#8fa3ba'),
                          (n_best['tx_analog'], '最优', C_REAL)):
        sp = np.abs(np.fft.rfft(sig * np.hanning(len(sig)))) ** 2
        fr = np.fft.rfftfreq(len(sig), d=1.0 / fs)
        axs[1, 1].plot(fr / 1e9, 10 * np.log10(sp / sp.max() + 1e-14), lw=1.0, label=lab, color=col)
    axs[1, 1].set_xlim(0, 80)
    axs[1, 1].set_ylim(-60, 3)
    axs[1, 1].set_xlabel('频率 (GHz)')
    axs[1, 1].set_ylabel('功率谱 (dB)')
    axs[1, 1].set_title('MZM 前 Tx 驱动频谱', fontsize=9)
    axs[1, 1].grid(True, ls='--', alpha=0.4)
    axs[1, 1].legend(fontsize=8)
    fig.suptitle(f'DDPS v4 节点视图: {env_name}', fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = os.path.join(report_dir, f'ddps_v4_case_{env_name}_b.png')
    fig.savefig(out, dpi=100)
    plt.close(fig)
    return out


def figure_overview(test_dir, report_dir):
    os.makedirs(report_dir, exist_ok=True)
    summ = _summary(test_dir).sort_values('delta_lb_seed_to_best')
    fig, ax = plt.subplots(figsize=(12, 4.8))
    x = np.arange(len(summ))
    ax.bar(x, -summ['delta_lb_seed_to_best'].values, color='#0f8a4a')
    for i, (_, r) in enumerate(summ.iterrows()):
        ax.text(i, -r['delta_lb_seed_to_best'] + 0.01, f'×{r["seed_ber"]/r["best_ber"]:.1f}',
                ha='center', fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels([f'{e}\n({env_label(e)})' for e in summ['env']], fontsize=7.5)
    ax.set_ylabel('Δlog10 BER（seed → best）')
    ax.set_title('DDPS v4：逐用例改善（冻结模型，真实 BER 不回传）', fontsize=11)
    ax.grid(True, axis='y', ls='--', alpha=0.5)
    fig.tight_layout()
    out = os.path.join(report_dir, 'ddps_v4_overview.png')
    fig.savefig(out, dpi=115)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# 深水复核 / 报告 / 汇总
# ---------------------------------------------------------------------------

def deep_check(test_dir, report_dir, deep_symbols, sim_seeds, only_envs=None):
    summ = _summary(test_dir)
    if not os.path.exists('config.xlsx'):
        create_config.generate_config()
    base_cfg = utils_config.load_config('config.xlsx')
    rows = []
    D.set_sim_seeds(sim_seeds)
    for _, r in summ.iterrows():
        env_name = r['env']
        if only_envs is not None and env_name not in only_envs:
            continue
        cfg = apply_env_to_config(base_cfg, env_case(env_name))
        cfg['system']['num_symbols'] = int(deep_symbols)
        best_taps = np.array(json.loads(r['best_taps'])) if isinstance(r['best_taps'], str) \
            else np.array(r['best_taps'])
        _, seed_ber = D._physical_eval(cfg, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2, D.SEED_GAIN)
        _, best_ber = D._physical_eval(cfg, best_taps, r['best_gdc'], r['best_gdc2'],
                                       r.get('best_gain', D.SEED_GAIN))
        rows.append({'env': env_name, 'deep_symbols': int(deep_symbols),
                     'seed_ber_deep': seed_ber, 'best_ber_deep': best_ber,
                     'improve_x': seed_ber / best_ber if best_ber > 0 else np.nan})
        print(f'  [deep] {env_name:26s} seed={seed_ber:.3e} best={best_ber:.3e} '
              f'x{rows[-1]["improve_x"]:.2f}')
    out = os.path.join(report_dir, 'deep_check.csv')
    pd.DataFrame(rows).to_csv(out, index=False)
    return out


def _params_of(row):
    """(种子, 收敛) 的完整参数对：4 个 FFE 旁瓣 + 派生主抽头 + gDC + gDC2 + 增益倍率。"""
    def _taps(r, key):
        v = r[key]
        return np.array(json.loads(v)) if isinstance(v, str) else np.array(v, dtype=float)
    seed_t = D.SEED_TAPS.astype(float)
    best_t = _taps(row, 'best_taps')
    return seed_t, best_t


def _rows_params(summ):
    """逐用例"种子 → 收敛"的全参数对照表（甲方要求：每个用例最后一列出来）。"""
    out = []
    for _, r in summ.iterrows():
        seed_t, best_t = _params_of(r)
        n_tap = len(seed_t)
        c_seed, c_best = seed_t[int((n_tap - 1) / 2)], best_t[int((n_tap - 1) / 2)]
        mid = int((len(seed_t) - 1) / 2)
        ffe = ' / '.join(f't{k}: {a:+.4f}→{b:+.4f}'
                         for k, (a, b) in enumerate(zip(seed_t, best_t)) if abs(a - b) > 1e-9)
        unchanged = sum(1 for k, (a, b) in enumerate(zip(seed_t, best_t))
                        if k != mid and abs(a - b) <= 1e-9)
        gain_s = float(r.get('seed_gain_ratio', 1.0))
        gain_b = float(r.get('best_gain_ratio', float('nan')))
        out.append(
            f"| {r['env']} | {r['best_step']} | {ffe or '（无变化）'} "
            f"| {unchanged}/{n_tap} | {c_seed:+.4f} → {c_best:+.4f} "
            f"| {r['best_gdc']:+.2f} | {r['best_gdc2']:+.2f} "
            f"| ×{gain_s:.2f} → ×{gain_b:.2f} "
            f"| `{r['seed_ber']:.3e}` → `{r['best_ber']:.3e}` |")
    return '\n'.join(out)


def figure_tracking(test_dir, report_dir):
    """预测变化量 vs 实测变化量（逐用例逐步散点）：直接回答“预测一直降、实测却升”是什么问题。"""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    summ = _summary(test_dir)
    fig, axs = plt.subplots(1, 2, figsize=(13.2, 4.6))
    corrs = {}
    for _, r in summ.iterrows():
        tr = _trace(test_dir, r['env'])
        if tr is None or tr.empty:
            continue
        seed_lb = float(np.log10(r['seed_ber']))
        dA = tr['pred_a'].values - tr['pred_a'].iloc[0]
        dR = tr['real_lb'].values - seed_lb
        low_il = ('20x' not in r['env']) and ('Comb_IL20' not in r['env']) and \
                 ('HighNoise_IL16' not in r['env'])
        axs[0].plot(dA, dR, marker='o', ms=3.4, lw=0.9, alpha=0.85,
                    color=('#0b63ce' if low_il else '#c0392b'))
        corrs[r['env']] = (float(np.corrcoef(dA, dR)[0, 1])
                           if np.std(dA) > 1e-9 and np.std(dR) > 1e-9 else np.nan)
    lim = axs[0].get_xlim()
    axs[0].axhline(0, color='k', lw=0.8, ls=':')
    axs[0].axvline(0, color='k', lw=0.8, ls=':')
    axs[0].plot(lim, [-v for v in lim], color='k', lw=0.9, ls='--', label='y = −x（预测与实测等量）')
    axs[0].set_xlabel('Model A 预测的 log10 BER 变化量（dex）')
    axs[0].set_ylabel('实测 log10 BER 变化量（dex）')
    axs[0].set_title('蓝=与训练环境相近（≤16 dB IL / CD）；红=远离训练环境（≥20 dB IL / 强噪声）', fontsize=9)
    axs[0].grid(True, ls='--', alpha=0.4)
    axs[0].legend(fontsize=8)

    names = list(corrs)
    vals = [corrs[k] for k in names]
    cols = ['#c0392b' if v < 0 else '#0b63ce' for v in vals]
    axs[1].barh(np.arange(len(names)), vals, color=cols)
    axs[1].set_yticks(np.arange(len(names)))
    axs[1].set_yticklabels(names, fontsize=7.5)
    axs[1].axvline(0, color='k', lw=0.8)
    axs[1].set_xlabel('corr(ΔModel A, Δ实测)')
    axs[1].set_title('逐用例：预测变化与实测变化的相关性（<0 = 方向脱钩）', fontsize=10)
    axs[1].grid(True, axis='x', ls='--', alpha=0.4)
    fig.tight_layout()
    out = os.path.join(report_dir, 'ddps_v4_tracking.png')
    fig.savefig(out, dpi=118)
    plt.close(fig)
    return out


def _worse_count(test_dir, env, seed_ber):
    tr = _trace(test_dir, env)
    if tr is None or tr.empty:
        return 0, 0
    return int((tr['real_ber'] > seed_ber).sum()), len(tr)


def write_report(test_dir, model_dir, report_dir, protocol):
    summ = _summary(test_dir)
    meta = {}
    if os.path.exists(os.path.join(model_dir, 'meta.json')):
        with open(os.path.join(model_dir, 'meta.json'), encoding='utf-8') as f:
            meta = json.load(f)

    L = ['# DDPS v4 在线调优结果报告\n']
    L.append(f'- 模型：`{model_dir}`（**只用基线环境训练**，冻结后跨环境复用；测试零重训、零校准）')
    L.append(f'- 评估协议：{protocol}')
    L.append(f'- 用例数：{len(summ)}；逐步 trace（含 Model A/B 预测与实测 BER）在 `trace_<用例>.csv`\n')

    L.append('## 逐用例结果\n')
    L.append('| 用例 | 物理条件 | 种子 BER_MLSE | 最优 BER_MLSE | Δlog10 | 改善 | 最优步 | gain 倍率 种子→最优 | 记录步数 | 劣于种子的步数 |')
    L.append('| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |')
    tot_steps = tot_worse = 0
    for _, r in summ.iterrows():
        w, n = _worse_count(test_dir, r['env'], r['seed_ber'])
        tot_steps += n
        tot_worse += w
        L.append(f'| {r["env"]} | {env_label(r["env"])} | `{r["seed_ber"]:.3e}` | `{r["best_ber"]:.3e}` | '
                 f'{r["delta_lb_seed_to_best"]:+.3f} | ×{r["seed_ber"]/r["best_ber"]:.2f} | '
                 f'{int(r["best_step"])} | ×{r.get("seed_gain", D.SEED_GAIN)/D.DRIVER_GAIN_NOMINAL:.2f} → '
                 f'×{r.get("best_gain", D.SEED_GAIN)/D.DRIVER_GAIN_NOMINAL:.2f} | {n} | {w} |')
    L.append(f'\n> 合计：记录 {tot_steps} 步，其中真实 BER 劣于种子的 **{tot_worse}** 步。'
             f'平均改善 ×{float((summ["seed_ber"]/summ["best_ber"]).mean()):.2f}。\n')

    L.append('## 逐用例：收敛后的全部可调参数 vs 起点\n')
    L.append('`best_step` 为轨迹中真实 BER 最小的那一步；FFE 列出 5 个抽头里**发生变化的那些**'
             '（t2 为主抽头，由 1 − Σ|旁瓣| 派生）；"未动的旁瓣"统计 4 个自由旁瓣里没变的个数。\n')
    L.append('| 用例 | 最优步 | FFE 5 抽头 种子→收敛（t2 为主抽头，派生） | 未动的旁瓣 | 主抽头 种子→收敛 | gDC (dB) | gDC2 (dB) | 增益倍率 | BER 种子→最优 |')
    L.append('| --- | --- | --- | --- | --- | --- | --- | --- | --- |')
    L.append(_rows_params(summ))
    L.append('')

    div = os.path.join(os.path.dirname(test_dir.rstrip('/\\')), 'ddps_v4_divergence.csv')
    if not os.path.exists(div):
        div = 'result/ddps_v4_divergence.csv'
    if os.path.exists(div):
        L.append('## 预测 vs 实测：轨迹跟踪诊断\n')
        L.append('每一步的 Model A 预测变化量（Δ_A）与实测变化量（Δ_real）逐用例对照。'
                 '`corr_pred_real < 0` 表示该用例上模型"越预测越好、实测越走越差"，即方向脱钩。\n')
        g = pd.read_csv(div)
        L.append('| 用例 | 预测下降总量 (dex) | 实测最优变化 (dex) | 实测末步变化 (dex) | 最优步 | 斜率 Δ_A→Δ_real | corr | 最优步位移 (ρ) |')
        L.append('| --- | --- | --- | --- | --- | --- | --- | --- |')
        for _, r in g.iterrows():
            L.append(f"| {r['env']} | {r['pred_drop_total_dex']:+.3f} | {r['real_best_delta_dex']:+.3f} "
                     f"| {r['real_final_delta_dex']:+.3f} | {int(r['best_step'])} "
                     f"| {r['reg_slope_pred_to_real']:+.2f} | {r['corr_pred_real']:+.2f} "
                     f"| {r['disp_best_over_rho']:.2f} |")
        L.append(f"\n> 预测下降总量 {g['pred_drop_total_dex'].sum():+.2f} dex vs 实测最优改善 "
                 f"{g['real_best_delta_dex'].sum():+.2f} dex；相关中位 {g['corr_pred_real'].median():+.2f}，"
                 f"正向用例 {int((g['corr_pred_real'] > 0).sum())}/{len(g)}。\n")

    if 'cloud' in summ.columns and summ['cloud'].notna().any():
        L.append('## 种子邻域云校验（离线证据，不参与决策）\n')
        L.append('| 用例 | 点数 | Model A 方向一致率 | Model B 方向一致率 | Model A 局部 Spearman |')
        L.append('| --- | --- | --- | --- | --- |')
        for _, r in summ.iterrows():
            c = r['cloud']
            if isinstance(c, str) and c.strip():
                try:
                    c = json.loads(c.replace("'", '"'))
                except Exception:
                    continue
                L.append(f'| {r["env"]} | {c.get("n")} | {c.get("agree_a"):.3f} | '
                         f'{c.get("agree_b"):.3f} | {c.get("spearman_real_va"):.3f} |')
        L.append('')

    if meta:
        L.append('## 模型指标（留出集，20% 样本）\n')
        L.append('| 模型 | 角色 | 输入 | 维度 | R² | MSE | Spearman |')
        L.append('| --- | --- | --- | --- | --- | --- | --- |')
        L.append(f'| Model A | 方向（log10 BER 条件均值） | 搜索向量 x | {meta.get("model_a_dim")} | '
                 f'{meta["model_a"]["r2_test"]:.3f} | {meta["model_a"]["mse_test"]:.3f} | '
                 f'{meta["model_a"]["spearman_test"]:.3f} |')
        L.append(f'| Model B | 拦截（均值 + 残差尺度保守上包络） | 搜索向量 x | {meta.get("model_b_dim")} | '
                 f'{meta["model_b"]["r2_test"]:.3f} | {meta["model_b"]["mse_test"]:.3f} | '
                 f'{meta["model_b"]["spearman_test"]:.3f} |')
        L.append(f'\n- `x = [8 个 FFE 旁瓣, gDC, gDC2, u_gain]`；Model A：RBF 核岭回归（γ={meta.get("gamma", float("nan")):.4f}，'
                 f'α={meta.get("alpha")}，5 折 CV 选型；解析梯度）。')
        L.append(f'- Model B 上包络系数 c={meta.get("envelope_c")}，测试集覆盖率 '
                 f'{meta.get("envelope_coverage_test", float("nan")):.2f}（保守性由覆盖率定义，故其 R² 天然不为正）。\n')

    lgf = os.path.join(os.path.dirname(test_dir.rstrip('/\\')), 'ddps_v4_local_gradient.csv')
    if not os.path.exists(lgf):
        lgf = 'result/ddps_v4_local_gradient.csv'
    if os.path.exists(lgf):
        L.append('## 模型方向验证：与实测局部梯度逐轴对照\n')
        L.append('在真实链路上对种子工作点沿 11 个搜索轴做中心差分（262144 symbols × 3 种子），'
                 '得到真实 log10 BER 的局部斜率，与 Model A 的解析梯度比较：\n')
        g = pd.read_csv(lgf)
        L.append('| 轴 | 步长 | 实测 d(+) | 实测 d(−) | 实测斜率 | Model A 斜率 | 符号一致 | 比值 |')
        L.append('| --- | --- | --- | --- | --- | --- | --- | --- |')
        for _, r in g.iterrows():
            L.append(f'| {r["dim"]} | {r["step"]:+.2f} {r["unit"]} | {r["real_d_plus"]:+.3f} | '
                     f'{r["real_d_minus"]:+.3f} | {r["real_slope"]:+.3f} | {r["model_a_slope"]:+.3f} | '
                     f'{"✓" if r["sign_match_a"] else "✗"} | {r["ratio_a"]:+.2f} |')
        real_g = g['real_slope'].values
        ma = g['model_a_slope'].values
        w = np.abs(real_g) / np.abs(real_g).sum()
        ok = np.sign(ma) == np.sign(real_g)
        L.append(f'\n> 方向命中率 **{ok.mean():.2f}**（按 |实测斜率| 加权 **{(w * ok).sum():.2f}**），'
                 f'量级相关系数 {np.corrcoef(ma, real_g)[0, 1]:+.2f}。\n')

    L.append('## 图件\n')
    L.append('- `ddps_v4_convergence.png`：**每个用例的 Model A / Model B / 实测 BER 三曲线收敛图**')
    L.append('- `ddps_v4_case_<用例>_a.png`：收敛（三曲线）/ FFE 抽头 / CTLE 频响 / 增益倍率轨迹')
    L.append('- `ddps_v4_case_<用例>_b.png`：Rx 眼图（种子 vs 最优）/ FFE 输出分布 / Tx 频谱')
    L.append('- `deep_check.csv`：长块 + 多种子独立复核\n')

    out = os.path.join(report_dir, 'ddps_v4_report.md')
    with open(out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(L))
    return out


def write_summary(entries, report_dir, out_path):
    os.makedirs(report_dir, exist_ok=True)
    frames = {}
    for d, lab in entries:
        p = os.path.join(d, 'case_summary.csv')
        if os.path.exists(p):
            frames[lab] = pd.read_csv(p)
    L = ['# DDPS v4：跨实验汇总（BER_MLSE）\n']
    if not frames:
        L.append('（无数据）')
    else:
        base_lab = entries[0][1]
        base = frames.get(base_lab, list(frames.values())[0])
        L.append(f'评估协议：262144 符号/点 × 3 仿真实例种子取 log10 均值；'
                 f'所有实验共用同一批用例与同一协议。\n')
        L.append('| 用例 | 物理条件 | 种子 | ' + ' | '.join(f'{l} 最优' for l in frames) + ' |')
        L.append('| --- | --- | --- | ' + ' | '.join(['---'] * len(frames)) + ' |')
        for _, r0 in base.iterrows():
            env = r0['env']
            cells = []
            for lab, df in frames.items():
                m = df[df['env'] == env]
                cells.append(f'`{m.iloc[0]["best_ber"]:.3e}`' if len(m) else '—')
            L.append(f'| {env} | {env_label(env)} | `{r0["seed_ber"]:.3e}` | ' + ' | '.join(cells) + ' |')
        L.append('')
        for lab, df in frames.items():
            worse = 0
            steps = 0
            for _, r in df.iterrows():
                for d, l in entries:
                    if l == lab:
                        w, n = _worse_count(d, r['env'], r['seed_ber'])
                        worse += w
                        steps += n
            L.append(f'- **{lab}**：{len(df)} 用例，记录 {steps} 步，劣于种子 {worse} 步；'
                     f'平均改善 ×{float((df["seed_ber"]/df["best_ber"]).mean()):.2f}')
        L.append('')
    out = (out_path if (os.path.isabs(out_path) or os.sep in out_path or '/' in out_path)
           else os.path.join(report_dir, out_path))
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(L))
    return out


def figure_delta(entries, report_dir):
    os.makedirs(report_dir, exist_ok=True)
    frames = {}
    for d, lab in entries:
        p = os.path.join(d, 'case_summary.csv')
        if os.path.exists(p):
            frames[lab] = pd.read_csv(p)
    if len(frames) < 2:
        return None
    base = list(frames.values())[0]
    envs = list(base['env'])
    fig, ax = plt.subplots(figsize=(12.5, 5))
    w = 0.8 / len(frames)
    for k, (lab, df) in enumerate(frames.items()):
        vals = []
        for e in envs:
            m = df[df['env'] == e]
            vals.append(float(m.iloc[0]['seed_ber'] / m.iloc[0]['best_ber']) if len(m) else np.nan)
        ax.bar(np.arange(len(envs)) + k * w, vals, width=w, label=lab)
    ax.axhline(1.0, color='k', lw=0.8)
    ax.set_xticks(np.arange(len(envs)) + 0.4 - w / 2)
    ax.set_xticklabels([f'{e}\n({env_label(e)})' for e in envs], fontsize=7.5)
    ax.set_ylabel('改善倍数（seed / best）')
    ax.set_title('DDPS v4：不同配置的改善量对照', fontsize=11)
    ax.grid(True, axis='y', ls='--', alpha=0.5)
    ax.legend(fontsize=9)
    fig.tight_layout()
    out = os.path.join(report_dir, 'fig_delta_compare.png')
    fig.savefig(out, dpi=115)
    plt.close(fig)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--test-dir', required=True)
    ap.add_argument('--model-dir', default='models/ddps_v4')
    ap.add_argument('--deep-symbols', type=int, default=0)
    ap.add_argument('--sim-seeds', type=str, default='42,43,44')
    ap.add_argument('--summary', nargs='*', default=None,
                    help='形如 "result/ddps_v4_xxx:只用基线" "result/ddps_v4_ablation:消融"')
    ap.add_argument('--summary-out', default='SUMMARY.md')
    ap.add_argument('--skip-nodes', action='store_true')
    ap.add_argument('--only-figures', action='store_true')
    a = ap.parse_args()

    report_dir = os.path.join(a.test_dir, 'report')
    os.makedirs(report_dir, exist_ok=True)
    if not os.path.exists('config.xlsx'):
        create_config.generate_config()
    baud_rate = float(utils_config.load_config('config.xlsx')['system']['baud_rate'])
    sim_seeds = tuple(int(s) for s in str(a.sim_seeds).split(',') if s.strip())

    summ = _summary(a.test_dir)
    envs = list(summ['env'])
    print(f'[report v4] {len(envs)} cases -> {report_dir}')

    print(figure_convergence_grid(a.test_dir, report_dir, envs))
    for e in envs:
        figure_case(a.test_dir, e, report_dir, baud_rate)
        if not a.skip_nodes:
            try:
                figure_nodes(a.test_dir, e, report_dir)
            except Exception as ex:
                print(f'  (node view skipped for {e}: {ex})')
    figure_overview(a.test_dir, report_dir)
    print(figure_tracking(a.test_dir, report_dir))

    protocol = '262144 符号/点 × 仿真种子 (42,43,44) 取 log10 均值'
    if os.path.exists(os.path.join(a.test_dir, 'run_config.json')):
        with open(os.path.join(a.test_dir, 'run_config.json'), encoding='utf-8') as f:
            rc = json.load(f)
        protocol = (f'{rc["num_symbols"]} 符号/点 × 仿真种子 {rc["sim_seeds"]} 取 log10 均值；'
                    f'n_steps 上限 {rc["n_steps"]}；拦截=预测相对种子变差 ≤ '
                    f'{100*D.MAX_DEGRADE_FRAC:.0f}%')
    if not a.only_figures:
        print(write_report(a.test_dir, a.model_dir, report_dir, protocol))
        if a.deep_symbols and a.deep_symbols > 0:
            print(f'[deep] {a.deep_symbols} 符号独立复核 ...')
            print(deep_check(a.test_dir, report_dir, a.deep_symbols, sim_seeds))

    if a.summary:
        entries = []
        for item in a.summary:
            d, lab = item.rsplit(':', 1) if ':' in item else (item, os.path.basename(item.rstrip('/')))
            entries.append((d, lab))
        if len(entries) >= 2:
            print(figure_delta(entries, report_dir) or '(delta figure skipped)')
        print(write_summary(entries, report_dir, a.summary_out))
