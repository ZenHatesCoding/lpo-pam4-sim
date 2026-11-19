#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""report_ddps.py — DDPS 结果可视化与报告。

在线调优：8 维（5 个 Tx FFE 抽头 + gDC + gDC2 + u_gain），抽头无边界；
形状维梯度获取方式由 run_config.json 的 grad_mode 决定（full / rotate / secant）。
从 case_summary / trace / probes 生成：
  ddps_convergence.png   3×5 收敛图（Model A 预测 / 实测 BER / ±ε 微扰态 + 种子线）
  ddps_gain_rms.png      逐用例 gain 倍率与 drive_rms 轨迹
  ddps_tracking.png      Δ预测 vs Δ实测 散点 + 逐用例相关系数
  ddps_case_<最难用例>.png  最难用例四联图
  ddps_report.md         中文报告（含真实评估次数记账）

--method direct（端到端 BER 直接梯度下降，无代理）只出三张图（不出 tracking
诊断图、不写报告/SUMMARY.md、不读 model-dir）：
  ddps_conv_grid.png     3×5 实测 BER 收敛（无代理预测曲线）
  ddps_gain_rms.png      逐用例 gain 倍率与 drive_rms 轨迹
  ddps_case_hard.png     最难用例四联图
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

BAUD = 56e9  # 56 GBd

# 三种梯度获取模式的人话说明（报告与图标题共用）
GRAD_MODE_TEXT = {
    'full': 'full：每步全量微扰（7 个形状维各 ±ε = 14 个微扰态/步）',
    'rotate': 'rotate：每步轮转微扰（每步 2 个形状维 ×±ε = 4 个微扰态/步）',
    'secant': 'secant：第 0 步微扰一次，此后割线维持（0 微扰态/步）',
    'direct': 'direct：端到端 BER 直接梯度下降（无代理）',
}


def _ctle_response_db(f, gdc_db, gdc2_db):
    """Tx CTLE |H(f)| in dB (peaking topology, DC gain = 0 dB). f: Hz array."""
    tx = load_config('config.xlsx')['tx']
    f = np.maximum(f, 1e-9)
    f_b = BAUD
    f_z = f_b / tx.get('ctle_fz_ratio', 2.862)
    f_p1 = f_b / tx.get('ctle_fp1_ratio', 1.884)
    f_p2 = f_b / tx.get('ctle_fp2_ratio', 1.0)
    f_lf = f_b / tx.get('ctle_flf_ratio', 40.0)
    K_DC = 10 ** (gdc_db / 20.0)
    K_DC2 = 10 ** (gdc2_db / 20.0)
    num1 = 1.0 + 1j * f * (K_DC / f_z)
    den1 = (1.0 + 1j * f / f_p1) * (1.0 + 1j * f / f_p2)
    num2 = 1.0 + 1j * f * (K_DC2 / f_lf)
    den2 = 1.0 + 1j * f / f_lf
    h = (num1 / den1) * (num2 / den2)
    return 20 * np.log10(np.abs(h) + 1e-12)

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC',
                                   'PingFang SC', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

C_REAL = '#0b63ce'
C_PREDA = '#e08a1e'
C_SEED = '#c0392b'
C_GAIN = '#2c7a2c'


def _trace(test_dir, env):
    p = os.path.join(test_dir, f'trace_{env}.csv')
    return pd.read_csv(p) if os.path.exists(p) else None


def _probes(test_dir, env):
    """某个用例梯度估计期间实际落到链路上的 ±ε 微扰态（每行 = 一次真实 BER 评估）。"""
    p = os.path.join(test_dir, f'probes_{env}.csv')
    return pd.read_csv(p) if os.path.exists(p) else None


def _probe_stats(test_dir, envs):
    """逐用例的微扰态 BER 概览（真实链路上为估计梯度而经历的工作点包络）。"""
    rows = []
    for env in envs:
        pr = _probes(test_dir, env)
        if pr is None or pr.empty or 'real_ber' not in pr.columns:
            continue
        rows.append({
            'env': env,
            'n_steps': int(pr['step'].nunique()),
            'n_probes': int(len(pr)),
            'ber_min': float(pr['real_ber'].min()),
            'ber_max': float(pr['real_ber'].max()),
            'ber_med': float(pr['real_ber'].median()),
        })
    return rows


def _summary(test_dir):
    return pd.read_csv(os.path.join(test_dir, 'case_summary.csv'))


def _run_meta(test_dir):
    """读 run_config.json（没有则回落到 C++ run_config / 缺省）。"""
    for name in ('run_config.json',):
        p = os.path.join(test_dir, name)
        if os.path.exists(p):
            try:
                with open(p, encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
    return {}


def _mode_text(meta):
    if not meta:
        return ''
    method = meta.get('method', 'proxy')
    if method == 'direct':
        return GRAD_MODE_TEXT['direct']
    gm = meta.get('grad_mode', 'full')
    if gm == 'rotate':
        k = int(meta.get('rotate_k', D.ROTATE_K))
        return f'rotate：每步轮转微扰（每步 {k} 个形状维 ×±ε = {2 * k} 个微扰态/步）'
    return GRAD_MODE_TEXT.get(gm, gm)


def _plot_convergence(ax, tr, row, title=None, small=False, pr=None, direct=False):
    steps = tr['step'].values
    # 种子点（step -1）作为曲线起点：trace 从梯度第 1 步开始记录，
    # 种子点（次优工作点）的 BER 高于后续各步，不 prepend 就看不到"种子→最优"的下降。
    seed = float(row['seed_ber'])
    seed_lb = float(row['seed_lb'])
    steps_ext = np.concatenate([[-1], steps])
    real_ber_ext = np.concatenate([[seed], tr['real_ber'].values])
    if direct:
        # direct：无代理预测曲线（pred_a 列 = 当前落点目标值、pred_b 恒 0，无预测含义）
        ax.semilogy(steps_ext, real_ber_ext, marker='o', ms=3.6, lw=1.5,
                    color=C_REAL, label='实测 BER_MLSE')
    else:
        pred_a_ext = np.concatenate([[seed_lb], tr['pred_a'].values])
        ax.semilogy(steps_ext, 10.0 ** pred_a_ext, marker='^', ms=3.2, ls='--',
                    lw=1.1, color=C_PREDA, label='Model A 预测（探针代理）')
        ax.semilogy(steps_ext, real_ber_ext, marker='o', ms=3.6, lw=1.5,
                    color=C_REAL, label='实测 BER_MLSE')
    # ±ε 微扰态：为估计梯度而让链路真实经过的工作点（full 每步 14 个、rotate 每步 4 个、
    # secant 仅第 0 步 14 个）
    if pr is not None and not pr.empty:
        for step in steps:
            ps = pr[pr['step'] == step]['real_ber'].values
            if len(ps):
                ax.scatter([step] * len(ps), ps, s=7, color='#9aa0a6', alpha=0.45,
                           zorder=2.6, edgecolors='none')
    ax.axhline(seed, color=C_SEED, ls='--', lw=0.9, alpha=0.8,
               label='种子 BER（起点 x0）')
    ax.set_yscale('log')
    ax.grid(True, which='both', ls='--', alpha=0.35)
    if title:
        ax.set_title(title, fontsize=9.5)
    if small:
        ax.tick_params(labelsize=7)


def _add_shared_legend(fig, loc='upper center', ncol=5, fontsize=9, y_offset=0.985,
                       direct=False, mode_text=None):
    """在 figure 顶部（suptitle 下方）放统一图例，避免子图内 legend 挤压数据。"""
    from matplotlib.lines import Line2D
    if direct:
        handles = [
            Line2D([0], [0], color=C_REAL, marker='o', ms=5, lw=1.5,
                   label='实测 BER_MLSE'),
            Line2D([0], [0], marker='o', ms=5, color='#9aa0a6', ls='none', alpha=0.6,
                   markeredgecolor='none', label='±ε 微扰态 BER（第 0 步 8 维全测 = 16 次）'),
            Line2D([0], [0], color=C_SEED, ls='--', lw=1.2, label='种子 BER（起点 x0）'),
        ]
    else:
        handles = [
            Line2D([0], [0], color=C_PREDA, marker='^', ms=5, ls='--', lw=1.2,
                   label='Model A 预测（探针代理）'),
            Line2D([0], [0], color=C_REAL, marker='o', ms=5, lw=1.5,
                   label='实测 BER_MLSE'),
            Line2D([0], [0], marker='o', ms=5, color='#9aa0a6', ls='none', alpha=0.6,
                   markeredgecolor='none', label='±ε 微扰态 BER（为估计梯度真实经过的工作点）'),
            Line2D([0], [0], color=C_SEED, ls='--', lw=1.2, label='种子 BER（起点 x0）'),
        ]
    fig.legend(handles=handles, loc=loc, ncol=ncol, fontsize=fontsize,
               framealpha=0.9, edgecolor='#ccc', bbox_to_anchor=(0.5, y_offset))


def figure_convergence_grid(test_dir, report_dir, envs, direct=False):
    os.makedirs(report_dir, exist_ok=True)
    summ = _summary(test_dir)
    rows = {r['env']: r for _, r in summ.iterrows()}
    meta = _run_meta(test_dir)
    mode_text = _mode_text(meta)
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
                          title=f'{env}\n改善 ×{imp:.2f}', small=True,
                          pr=_probes(test_dir, env), direct=direct)
    for j in range(n, len(axes)):
        axes[j].axis('off')
    if direct:
        fig.suptitle('DDPS 在线调优收敛轨迹 — direct（端到端 BER 直接梯度下降）'
                     '（15 环境，8 维 FFE+CTLE+gain）', fontsize=12)
        _add_shared_legend(fig, ncol=3, fontsize=9, y_offset=0.965, direct=True)
        out_name = 'ddps_conv_grid.png'
    else:
        fig.suptitle(f'DDPS 在线调优收敛轨迹 — Model A 探针代理，{mode_text}'
                     f'（15 环境，8 维 FFE+CTLE+gain，抽头无边界）', fontsize=12)
        _add_shared_legend(fig, ncol=4, fontsize=9, y_offset=0.965)
        out_name = 'ddps_convergence.png'
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    out = os.path.join(report_dir, out_name)
    fig.savefig(out, dpi=125)
    plt.close(fig)
    return out


def figure_gain_rms(test_dir, report_dir, envs, direct=False):
    """逐用例 gain 倍率与 drive_rms 轨迹（gain = 第 8 个搜索维，走解析梯度）。"""
    os.makedirs(report_dir, exist_ok=True)
    summ = _summary(test_dir)
    rows = {r['env']: r for _, r in summ.iterrows()}
    meta = _run_meta(test_dir)
    mode_text = _mode_text(meta)
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
        seed_gr = float(rows[env].get('seed_gain_ratio', tr['gain_ratio'].iloc[0]))
        seed_rms = float(tr['drive_rms'].iloc[0])
        steps_ext = np.concatenate([[-1], steps])
        gr_ext = np.concatenate([[seed_gr], tr['gain_ratio'].values])
        dr_ext = np.concatenate([[seed_rms], tr['drive_rms'].values])
        ax.plot(steps_ext, gr_ext, marker='o', ms=4, lw=1.5,
                color=C_GAIN, label='gain 倍率（左轴）')
        ax2 = ax.twinx()
        ax2.plot(steps_ext, dr_ext, marker='s', ms=3, ls='--',
                 lw=1.0, color=C_REAL, label='drive_rms (V)（右轴）')
        ax.set_title(f'{env}', fontsize=9)
        ax.set_xlabel('步数', fontsize=8)
        ax.set_ylabel('gain 倍率', fontsize=8, color=C_GAIN)
        ax2.set_ylabel('drive_rms (V)', fontsize=8, color=C_REAL)
        ax.tick_params(labelsize=7)
        ax2.tick_params(labelsize=7)
        ax.grid(True, ls='--', alpha=0.35)
    for j in range(n, len(axes)):
        axes[j].axis('off')
    if direct:
        fig.suptitle('DDPS gain / drive_rms 轨迹 — direct（gain 为第 8 维，实测差分）', fontsize=12)
    else:
        fig.suptitle(f'DDPS gain / drive_rms 轨迹 — {mode_text}（gain 为第 8 维，解析梯度 0 微扰）',
                     fontsize=12)
    from matplotlib.lines import Line2D
    _h = [Line2D([0], [0], color=C_GAIN, marker='o', ms=5, lw=1.5, label='gain 倍率（左轴）'),
          Line2D([0], [0], color=C_REAL, marker='s', ms=4, ls='--', lw=1.0, label='drive_rms (V)（右轴）')]
    fig.legend(handles=_h, loc='upper center', ncol=2, fontsize=9,
               framealpha=0.9, edgecolor='#ccc', bbox_to_anchor=(0.5, 0.965))
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    out = os.path.join(report_dir, 'ddps_gain_rms.png')
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
    """Δ预测 vs Δ实测 散点 + 逐用例相关系数（代理方向可靠性诊断）。"""
    os.makedirs(report_dir, exist_ok=True)
    mode_text = _mode_text(_run_meta(test_dir))
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
        cat = _env_category(env)
        ax1.scatter(dA, dR, s=20, alpha=0.6, color=CAT_COLORS[cat])
    if not all_dA or not all_dR:
        lo, hi = -0.1, 0.1
    else:
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
    fig.suptitle(f'预测变化量 vs 实测变化量 — Model A 探针代理，{mode_text}', fontsize=12)
    fig.tight_layout()
    out = os.path.join(report_dir, 'ddps_tracking.png')
    fig.savefig(out, dpi=125)
    plt.close(fig)
    return out


def _seed_point(meta):
    """起点的 5 抽头 / gDC / gDC2 / gain：优先读 run_config.json 里的 seed_config 文件。

    换起点做对照实验时，模块级 D.SEED_* 还是默认值，必须按这次跑批实际用的起点读。
    """
    taps = np.array(D.SEED_TAPS, dtype=float)
    gdc, gdc2, gain = D.SEED_GDC, D.SEED_GDC2, D.SEED_GAIN
    p = (meta or {}).get('seed_config')
    if p and os.path.exists(p):
        try:
            with open(p, encoding='utf-8') as f:
                sc = json.load(f)
            if 'best_taps' in sc:
                taps = np.asarray(sc['best_taps'], dtype=float)
            elif 'best_pre_post' in sc:
                taps = D.construct_taps(np.asarray(sc['best_pre_post'], dtype=float), D.FFE_PRE)
            gdc = float(sc.get('best_gdc', gdc))
            gdc2 = float(sc.get('best_gdc2', gdc2))
            if 'best_u_gain' in sc:
                gain = float(D.gain_from_u(float(sc['best_u_gain'])))
            elif 'best_gain' in sc:
                gain = float(sc['best_gain'])
        except Exception:
            pass
    return {'taps': taps, 'gdc': gdc, 'gdc2': gdc2, 'gain': gain}


def _tx_psd_db(f, taps, gdc_db, gdc2_db, gain):
    """发端频谱的相对电平（dB）：Tx FFE 频响 ⊗ DAC 零阶保持 ⊗ Tx CTLE ⊗ 驱动增益。

    只比较形状与相对电平，因此载波（PAM4 数据）按白谱处理——同一批数据下两点的差别
    全部来自这三个线性环节，这正是「起点 vs 最优」想看的。
    """
    f = np.maximum(f, 1e-9)
    t = 1.0 / BAUD
    h = np.zeros_like(f, dtype=complex)
    for k, a in enumerate(taps):
        h += a * np.exp(-1j * 2 * np.pi * f * k * t)
    mag = np.abs(h) + 1e-12
    zoh = np.abs(np.sinc(f / (2.0 * BAUD))) + 1e-12      # DAC 零阶保持在 2 sps
    ctle = 10 ** (_ctle_response_db(f, gdc_db, gdc2_db) / 20.0)
    return 20 * np.log10(mag * zoh * ctle * max(gain, 1e-12))


def figure_hardcase(test_dir, report_dir, envs, direct=False):
    """最难用例四联图：收敛曲线 + FFE 抽头 + CTLE 频响 + 探针 FIR。"""
    os.makedirs(report_dir, exist_ok=True)
    summ = _summary(test_dir)
    mode_text = _mode_text(_run_meta(test_dir))
    hard_env = max(envs, key=lambda e: summ[summ['env'] == e].iloc[0]['seed_ber']
                   if e in summ['env'].values else 0)
    tr = _trace(test_dir, hard_env)
    if tr is None or tr.empty:
        return None

    best_idx = int(tr['real_ber'].values.argmin())
    best_row = tr.iloc[best_idx]
    _sp = _seed_point(_run_meta(test_dir))
    seed_taps = np.array(_sp['taps'], dtype=float).copy()
    seed_gdc, seed_gdc2, seed_gain = _sp['gdc'], _sp['gdc2'], _sp['gain']
    try:
        best_taps = np.array(json.loads(best_row['taps']) if isinstance(best_row['taps'], str)
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
    ctle_seed = _ctle_response_db(f, seed_gdc, seed_gdc2)
    ctle_best = _ctle_response_db(f, best_gdc, best_gdc2)

    fig, axes = plt.subplots(2, 3, figsize=(19.5, 10))
    _plot_convergence(axes[0, 0], tr, summ[summ['env'] == hard_env].iloc[0],
                      title=f'{hard_env} 收敛轨迹', pr=_probes(test_dir, hard_env),
                      direct=direct)
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
    ax.set_title('5-tap Tx FFE（种子 vs 最优；5 个抽头全部自由、无边界）', fontsize=10)
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
    # (4) 探针 FIR 7-tap
    ax = axes[1, 1]
    xs7 = np.arange(7)
    w7 = 0.35
    ax.bar(xs7 - w7 / 2, fir_seed, w7, color='#0b63ce', alpha=0.7, label='种子')
    ax.bar(xs7 + w7 / 2, fir_best, w7, color='#0f8a4a', alpha=0.7, label='最优')
    ax.set_xticks(xs7); ax.set_xticklabels([f'h{i}' for i in xs7], fontsize=9)
    ax.set_ylabel('幅度 (V)', fontsize=9); ax.legend(fontsize=8)
    ax.set_title('Tx 物理探针 7-tap FIR（发端波形特征）' if direct
                 else 'Tx 物理探针 7-tap FIR（Model A 输入特征）', fontsize=10)
    ax.grid(True, ls='--', alpha=0.3, axis='y')
    # (5)(6) 发端频谱：起点 vs 最优，以及逐频点差值
    best_gain = None
    try:
        import math as _m
        best_gain = float(_m.pow(10.0, float(best_row['u_gain']))) * D.DRIVER_GAIN_NOMINAL
    except Exception:
        best_gain = seed_gain
    psd_seed = _tx_psd_db(f, seed_taps, seed_gdc, seed_gdc2, seed_gain)
    psd_best = _tx_psd_db(f, best_taps, best_gdc, best_gdc2, best_gain)
    ref = float(np.max(psd_seed))
    psd_seed -= ref
    psd_best -= ref
    ax = axes[1, 1]
    ax.plot(f / 1e9, psd_seed, color='#0b63ce', lw=1.6, label='起点')
    ax.plot(f / 1e9, psd_best, ls='--', color='#0f8a4a', lw=1.6, label='最优')
    ax.axvline(BAUD / 2 / 1e9, color='k', ls=':', lw=1, label='Nyquist')
    ax.set_xlabel('GHz', fontsize=9); ax.set_ylabel('相对电平 (dB)', fontsize=9)
    ax.set_title('发端频谱对比（FFE ⊗ DAC ZOH ⊗ Tx CTLE ⊗ 增益）', fontsize=10)
    ax.legend(fontsize=8); ax.grid(alpha=0.3); ax.set_ylim(-40, 5)
    ax = axes[1, 2]
    ax.plot(f / 1e9, psd_best - psd_seed, color='#b8860b', lw=1.6)
    ax.axhline(0, color='k', lw=0.6)
    ax.axvline(BAUD / 2 / 1e9, color='k', ls=':', lw=1)
    ax.fill_between(f / 1e9, 0, psd_best - psd_seed, color='#b8860b', alpha=0.18)
    ax.set_xlabel('GHz', fontsize=9); ax.set_ylabel('ΔdB（最优 − 起点）', fontsize=9)
    ax.set_title('频谱改变量：正=最优在高频抬得更多', fontsize=10)
    ax.grid(alpha=0.3)
    if direct:
        label = 'direct（端到端 BER 直接梯度下降）'
        out_name = 'ddps_case_hard.png'
    else:
        label = f'Model A 探针代理，{mode_text}'
        out_name = f'ddps_case_{hard_env}.png'
    fig.suptitle(f'最难用例四联图 — {label}：{hard_env}（种子 BER → 最优 BER）',
                 fontsize=12, fontweight='bold')
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = os.path.join(report_dir, out_name)
    fig.savefig(out, dpi=125)
    plt.close(fig)
    return out


def write_report(test_dir, report_dir, model_dir, envs, summary_text=None,
                 summary_out=None):
    os.makedirs(report_dir, exist_ok=True)
    summ = _summary(test_dir)
    meta = _run_meta(test_dir)
    # 起点 gain 倍率以数据为准（种子配置随运行而变，模块常量只是兜底）
    seed_ratio = None
    if 'seed_gain_ratio' in summ.columns:
        _sr = pd.to_numeric(summ['seed_gain_ratio'], errors='coerce').dropna()
        if len(_sr):
            seed_ratio = float(_sr.mean())
    if seed_ratio is None:
        seed_ratio = D.SEED_GAIN / D.DRIVER_GAIN_NOMINAL
    mode_text = _mode_text(meta)
    try:
        with open(os.path.join(model_dir, 'meta.json'), encoding='utf-8') as f:
            mmeta = json.load(f)
    except Exception:
        mmeta = {}

    fig_conv = figure_convergence_grid(test_dir, report_dir, envs)
    fig_gain = figure_gain_rms(test_dir, report_dir, envs)
    fig_track = figure_tracking(test_dir, report_dir, envs)
    fig_hard = figure_hardcase(test_dir, report_dir, envs)

    L = []
    L.append('# DDPS 在线调优报告\n')
    L.append(f'> 模型：`{model_dir}`（Model A：8 维探针 → log10 BER_MLSE 条件均值，核岭闭式解）\n')
    L.append(f'> 搜索空间：8 维 = 5 个 Tx FFE 抽头（全自由、无边界）+ gDC + gDC2 + u_gain\n')
    L.append(f'> 梯度获取：{mode_text or "见 run_config.json"}\n')
    L.append(f'> 评估协议：{meta.get("num_symbols", 4194304)} 符号/点 × 单种子 '
             f'{meta.get("sim_seeds", [42])[0] if meta.get("sim_seeds") else 42}\n\n')

    L.append('## 1. 逐用例结果\n\n')
    L.append('| 用例 | 物理条件 | 种子 BER | 最优 BER | 终点 BER | 改善 × | 真实评估（落点/微扰） | 最坏微扰 BER | gain 倍率 | gDC | gDC2 |\n')
    L.append('| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n')
    for env in envs:
        r = summ[summ['env'] == env]
        if r.empty:
            continue
        r = r.iloc[0]
        tr = _trace(test_dir, env)
        imp = r['seed_ber'] / r['best_ber']
        n_land = int(r.get('n_landed', len(tr) if tr is not None else 0) or 0)
        n_prob = int(r.get('n_probe_states', 0) or 0)
        worst = r.get('max_probe_ber', float('nan'))
        worst_s = f'`{worst:.2e}`' if worst == worst and worst > 0 else '—'
        L.append(f"| {env} | {env_label(env)} | `{r['seed_ber']:.3e}` | "
                 f"`{r['best_ber']:.3e}` | `{r['final_ber']:.3e}` | ×{imp:.2f} | "
                 f"{n_land + n_prob}（{n_land}/{n_prob}） | {worst_s} | "
                 f"×{r.get('best_gain_ratio', 1.0):.2f} | {r['best_gdc']:+.2f} | {r['best_gdc2']:+.2f} |\n")

    n = len(summ)
    better = int((summ['delta_lb_seed_to_best'] < -0.01).sum())
    worse = int((summ['delta_lb_seed_to_final'] > 0.01).sum())
    mean_imp = float(np.exp(np.mean(np.log(summ['seed_ber'] / summ['best_ber']))))
    tot_land = int(summ['n_landed'].sum()) if 'n_landed' in summ.columns else 0
    tot_prob = int(summ['n_probe_states'].sum()) if 'n_probe_states' in summ.columns else 0
    L.append(f'## 2. 汇总\n\n')
    L.append(f'- 用例数：{n}\n')
    L.append(f'- 改善（d_best < −0.01 dex）：{better}/{n}\n')
    L.append(f'- 终点劣于种子（d_final > +0.01 dex）：{worse}/{n}\n')
    L.append(f'- 平均改善（几何均值）：×{mean_imp:.2f}\n')
    L.append(f'- 在线真实 BER 评估：合计 {tot_land + tot_prob} 次'
             f'（落点 {tot_land} 次 + 为估计梯度制造的 ±ε 微扰态 {tot_prob} 次）；'
             f'每用例平均 {(tot_land + tot_prob) / max(n, 1):.1f} 次\n\n')

    def _rel_img(path):
        # Markdown 图片链接统一用正斜杠相对路径（Windows 反斜杠在别的查看器里不可点）
        return os.path.relpath(path, os.path.dirname(test_dir) or '.').replace(os.sep, '/')

    L.append('## 3. 核心图\n\n')
    L.append(f'![收敛轨迹]({_rel_img(fig_conv)})\n\n')
    L.append(f'![gain 倍率与 drive_rms 轨迹]({_rel_img(fig_gain)})\n\n')
    L.append(f'![预测-实测跟踪]({_rel_img(fig_track)})\n\n')
    if fig_hard:
        L.append(f'![最难用例四联图]({_rel_img(fig_hard)})\n\n')

    probe_rows = _probe_stats(test_dir, envs)
    if probe_rows:
        L.append('## 4. ±ε 微扰态的真实 BER（梯度估计的物理代价）\n\n')
        L.append(f'{mode_text}。这些微扰态是真实在线系统里为得到探针而必须施加的参数扰动，'
                 '链路会真实经过这些工作点，因此逐一记录各自的端到端 MLSE BER（核心图灰点）。'
                 '这些记录不参与下降方向决策，只做代价记账。\n\n')
        L.append('| 用例 | 有微扰的步数 | 微扰态数 | 微扰 BER 最小 | 微扰 BER 最大 | 微扰 BER 中位 |\n')
        L.append('| --- | --- | --- | --- | --- | --- |\n')
        for r in probe_rows:
            L.append(f"| {r['env']} | {r['n_steps']} | {r['n_probes']} | "
                     f"`{r['ber_min']:.2e}` | `{r['ber_max']:.2e}` | `{r['ber_med']:.2e}` |\n")
        L.append('\n')

    L.append('## 5. 架构（只有 Model A）\n\n')
    L.append('**Model A（方向代理）**：输入 = [7-tap Tx FIR 探针, drive_rms]（8 维波形域）\n')
    L.append('-> log10(BER_MLSE) 条件均值。在线调优拿不到收端 BER，只能拿发端探针，\n')
    L.append('所以 A 建立「发端探针 → 收端 BER」的方向映射。梯度走链式法则：扰动 8 维参数\n')
    L.append('（5 个 FFE 抽头 + gDC + gDC2 + u_gain）-> 重算探针 -> 查 A -> 得 ΔBER（中心差分）。\n\n')
    L.append('**gain 维（第 8 维）**：driver_gain 是 Tx 链末尾的标量乘子，Model A 的 8 维探针\n')
    L.append('特征全部正比于 gain，故 gain 维梯度有解析闭式（0 微扰态）；\n')
    L.append('每用例最优倍率见 per-case target_rms 标定参照（per-case target_rms -> 解析 gain）。\n')
    L.append(f'在线调优从次优起点（gain ×{seed_ratio:.3f}）出发，'
             '随梯度下降把 gain 推到各用例最优倍率附近。\n\n')
    if mmeta:
        ma = mmeta.get('model_a', {})
        if ma:
            L.append(f"Model A 训练指标（离线基线环境 80/20 划分）："
                     f"R²={ma.get('r2_test', float('nan')):.3f}、"
                     f"Spearman={ma.get('spearman_test', float('nan')):.3f}\n\n")

    if summary_text:
        L.append('## 6. 汇总标注\n\n')
        L.append(f'`{summary_text}`\n\n')

    out = os.path.join(report_dir, 'ddps_report.md')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(''.join(L))

    if summary_out:
        with open(summary_out, 'w', encoding='utf-8') as f:
            f.write('# DDPS：跨实验汇总（BER_MLSE）\n\n')
            f.write(f'评估协议：{meta.get("num_symbols", 4194304)} 符号/点 × 单种子 '
                    f'{meta.get("sim_seeds", [42])[0] if meta.get("sim_seeds") else 42}；'
                    f'梯度获取：{mode_text}\n\n')
            f.write('| 用例 | 物理条件 | 种子 | DDPS 最优 | 改善 × |\n')
            f.write('| --- | --- | --- | --- | --- |\n')
            for env in envs:
                r = summ[summ['env'] == env]
                if r.empty:
                    continue
                r = r.iloc[0]
                f.write(f"| {env} | {env_label(env)} | `{r['seed_ber']:.3e}` | "
                        f"`{r['best_ber']:.3e}` | ×{r['seed_ber']/r['best_ber']:.2f} |\n")
            f.write(f'\n- **DDPS（Model A 探针代理 + {mode_text} + gain 解析梯度）**：'
                    f'{n} 用例，改善 {better}/{n}，平均改善 ×{mean_imp:.2f}，'
                    f'在线真实评估合计 {tot_land + tot_prob} 次\n')
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--test-dir', default='result/ddps_cpp_full')
    ap.add_argument('--model-dir', default='models/ddps')
    ap.add_argument('--method', choices=['proxy', 'direct'], default='proxy',
                    help='proxy=现役（Model A 探针代理，梯度获取方式由 run_config 的 grad_mode 决定，'
                         '全量输出）；direct=端到端 BER 直接梯度（只出三张图：收敛/gain·rms/最难用例，'
                         '不出代理诊断图、不写报告与 SUMMARY）')
    ap.add_argument('--summary', default=None)
    ap.add_argument('--summary-out', default=None)
    ap.add_argument('--seed-config', default=None,
                    help='种子点 JSON（best_taps 或 best_pre_post + best_gdc/best_gdc2，'
                         '可选 best_u_gain/best_gain）；不提供则用默认 SEED_TAPS')
    a = ap.parse_args()
    if a.seed_config:
        D.apply_seed_config(a.seed_config)
        print(f'[report] 种子点覆盖: taps={np.round(D.SEED_TAPS,4)} gDC={D.SEED_GDC:.2f} '
              f'gDC2={D.SEED_GDC2:.2f} gain={D.SEED_GAIN:.4f}')
    envs = [e['name'] for e in ENV_CASES]
    rd = os.path.join(a.test_dir, 'report')
    if a.method == 'direct':
        # direct：无代理（无预测曲线/诊断图），只出三张图；不读 model-dir、不写报告与汇总
        figure_convergence_grid(a.test_dir, rd, envs, direct=True)
        figure_gain_rms(a.test_dir, rd, envs, direct=True)
        figure_hardcase(a.test_dir, rd, envs, direct=True)
        print(f'report (direct) -> {rd}/ddps_conv_grid.png, ddps_gain_rms.png, ddps_case_hard.png')
    else:
        write_report(a.test_dir, rd, a.model_dir, envs,
                     summary_text=a.summary, summary_out=a.summary_out)
        print(f'report -> {rd}/ddps_report.md')
