#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""report_ddps_v3.py — DDPS v3 结果可视化与汇总报告。

产出（全部落盘到 <test-dir>/report/）：
  ddps_v3_case_<env>_a.png   单用例四联图：收敛轨迹 / Tx FFE 抽头 / CTLE |H(f)| / driver_gain 轨迹
  ddps_v3_case_<env>_b.png   节点视图：Rx 眼图（种子 vs 最优）+ Rx FFE 输出直方图 + Tx 频谱
  ddps_v3_overview.png       全部用例 seed -> best 改善总览
  ddps_v3_report.md          中文报告（含逐用例表、模型指标、评估协议）
  deep_check.csv             长块独立复核（--deep-symbols）
另可生成跨实验汇总：--summary "dir:label" "dir:label" ... -> SUMMARY.md + fig_delta_compare.png
"""
import os
import json
import argparse
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# 中文字体（图内标注为中文；缺字体会退化为方块）
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC',
                                   'PingFang SC', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

import create_config
import utils_config
import ddps_optimizer as D
from ddps_cases import ENV_CASES, env_case, apply_env_to_config, env_label
from train_surrogates import load_models
from main import run_sim

# ---------------------------------------------------------------------------
# 物理量绘制助手
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
    num1 = g_dc + 1j * f / f_z
    den1 = (1 + 1j * f / f_z) * (1 + 1j * f / f_p1) * (1 + 1j * f / f_p2)
    num2 = g_dc2 + 1j * f / f_lf
    den2 = 1 + 1j * f / f_lf
    H = (num1 / den1) * (num2 / den2)
    return 20 * np.log10(np.abs(H) + 1e-12)


def eye_diagram(ax, x, sps, span=2, title=''):
    """简易眼图：按 span 个符号宽度折叠。"""
    n = (len(x) // (sps * span)) * sps * span
    seg = x[:n].reshape(-1, sps * span)
    t = np.arange(sps * span) / sps
    for row in seg[:600]:
        ax.plot(t, row, color='#2a6fbf', alpha=0.06, lw=0.6)
    ax.set_title(title, fontsize=9)
    ax.grid(True, ls='--', alpha=0.35)


# ---------------------------------------------------------------------------
# 单用例图
# ---------------------------------------------------------------------------

def figure_case(test_dir, env_name, report_dir, baud_rate):
    trace_p = os.path.join(test_dir, f'trace_{env_name}.csv')
    if not os.path.exists(trace_p):
        return None
    tr = pd.read_csv(trace_p)
    if tr.empty:
        return None

    summ_p = os.path.join(test_dir, 'case_summary.csv')
    summ = pd.read_csv(summ_p)
    row = summ[summ['env'] == env_name].iloc[0]

    steps = tr['step'].values
    real_lb = tr['real_lb'].values
    pred_a = tr['pred_a'].values

    best_taps = np.array(json.loads(row['best_taps'])) if isinstance(row['best_taps'], str) \
        else np.array(row['best_taps'])

    fig, axs = plt.subplots(2, 2, figsize=(12, 7.2))

    ax = axs[0, 0]
    ax.plot(steps, 10.0 ** real_lb, marker='o', ms=4, label='真实 BER_MLSE（仅记录）')
    ax.plot(steps, 10.0 ** pred_a, marker='x', ms=4, ls='--', label='Model A 预测')
    ax.axhline(10.0 ** row['seed_lb'], color='#c0392b', ls=':', label='种子 x0')
    ax.set_yscale('log')
    ax.set_xlabel('Stage-2 step'); ax.set_ylabel('BER_MLSE')
    ax.set_title(f'{env_name} 收敛：seed {row["seed_ber"]:.2e} -> best {row["best_ber"]:.2e}', fontsize=10)
    ax.grid(True, which='both', ls='--', alpha=0.5); ax.legend(fontsize=8)

    ax = axs[0, 1]
    idx = np.arange(9)
    ax.bar(idx - 0.2, D.SEED_TAPS, width=0.4, label='种子', color='#8fa3ba')
    ax.bar(idx + 0.2, best_taps, width=0.4, label='最优', color='#0b63ce')
    ax.set_xticks(idx); ax.set_xticklabels([f't{i}' for i in range(9)], fontsize=8)
    ax.set_title('Tx FFE 9-tap（t4 = 主抽头，派生）', fontsize=10)
    ax.grid(True, axis='y', ls='--', alpha=0.5); ax.legend(fontsize=8)

    ax = axs[1, 0]
    f = np.linspace(1e9, 60e9, 400)
    ax.plot(f / 1e9, ctle_response_db(f, baud_rate, D.SEED_GDC, D.SEED_GDC2),
            label=f'种子 (gDC={D.SEED_GDC:g}, gDC2={D.SEED_GDC2:g})', color='#8fa3ba')
    ax.plot(f / 1e9, ctle_response_db(f, baud_rate, row['best_gdc'], row['best_gdc2']),
            label=f'最优 (gDC={row["best_gdc"]:.2f}, gDC2={row["best_gdc2"]:.2f})', color='#0b63ce')
    ax.axvline(baud_rate / 2 / 1e9, color='k', ls=':', lw=0.8, label='Nyquist')
    ax.set_xlabel('频率 (GHz)'); ax.set_ylabel('|H(f)| (dB)')
    ax.set_title('Tx 模拟 CTLE 频响（电插损之后 / Driver 之前）', fontsize=10)
    ax.grid(True, ls='--', alpha=0.5); ax.legend(fontsize=8)

    ax = axs[1, 1]
    if 'gain' in tr.columns:
        ax.plot(steps, tr['gain'].values, marker='o', ms=4, color='#0f8a4a')
        ax.axhline(D.SEED_GAIN, color='#c0392b', ls=':', label=f'种子 gain={D.SEED_GAIN:g}')
        ax.set_ylabel('driver_gain (线性)'); ax.set_xlabel('Stage-2 step')
        ax.set_title(f'driver_gain 轨迹（seed {row.get("seed_gain", D.SEED_GAIN):.2f} -> '
                     f'best {row.get("best_gain", float("nan")):.3f}）', fontsize=10)
        ax.grid(True, ls='--', alpha=0.5); ax.legend(fontsize=8)

    fig.suptitle(f'DDPS v3 case: {env_name}  ({env_label(env_name)})', fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = os.path.join(report_dir, f'ddps_v3_case_{env_name}_a.png')
    fig.savefig(out, dpi=110); plt.close(fig)
    return out


def figure_nodes(test_dir, env_name, report_dir, num_symbols=32768):
    """节点视图：种子 vs 最优的 Rx 眼图 / Rx FFE 输出直方图 / Tx 频谱。"""
    summ = pd.read_csv(os.path.join(test_dir, 'case_summary.csv'))
    row = summ[summ['env'] == env_name].iloc[0]
    env = env_case(env_name)

    if not os.path.exists('config.xlsx'):
        create_config.generate_config()
    base_cfg = utils_config.load_config('config.xlsx')
    cfg = apply_env_to_config(base_cfg, env)
    cfg['system']['num_symbols'] = int(num_symbols)

    best_taps = np.array(json.loads(row['best_taps'])) if isinstance(row['best_taps'], str) \
        else np.array(row['best_taps'])

    def run(taps, gdc, gdc2, gain):
        c = {k: (dict(v) if isinstance(v, dict) else v) for k, v in cfg.items()}
        D._apply_x_to_config(c, gdc, gdc2, gain)
        return run_sim(c, custom_tx_taps=taps, plot_eyes=False, output_dir=None,
                       return_nodes=True)

    _, _, n_seed = run(D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2, D.SEED_GAIN)
    _, _, n_best = run(best_taps, row['best_gdc'], row['best_gdc2'], row.get('best_gain', D.SEED_GAIN))

    sps = int(cfg['system']['sps_channel'])
    fig, axs = plt.subplots(2, 2, figsize=(12, 7.2))

    eye_diagram(axs[0, 0], n_seed['rx_analog'], sps, 2, 'Rx ADC 输入眼图 — 种子')
    eye_diagram(axs[0, 1], n_best['rx_analog'], sps, 2, 'Rx ADC 输入眼图 — 最优')
    axs[0, 0].set_ylabel('幅度 (a.u.)')

    axs[1, 0].hist(n_seed['rx_eq'], bins=120, alpha=0.6, label='种子', color='#8fa3ba', density=True)
    axs[1, 0].hist(n_best['rx_eq'], bins=120, alpha=0.6, label='最优', color='#0b63ce', density=True)
    axs[1, 0].set_title('Rx FFE 均衡输出分布', fontsize=9)
    axs[1, 0].grid(True, ls='--', alpha=0.4); axs[1, 0].legend(fontsize=8)

    fs = cfg['system']['baud_rate'] * sps
    for sig, lab, col in ((n_seed['tx_analog'], '种子', '#8fa3ba'), (n_best['tx_analog'], '最优', '#0b63ce')):
        sp = np.abs(np.fft.rfft(sig * np.hanning(len(sig)))) ** 2
        fr = np.fft.rfftfreq(len(sig), d=1.0 / fs)
        sp_db = 10 * np.log10(sp / sp.max() + 1e-14)
        axs[1, 1].plot(fr / 1e9, sp_db, lw=1.0, label=lab, color=col)
    axs[1, 1].set_xlim(0, 80); axs[1, 1].set_ylim(-60, 3)
    axs[1, 1].set_xlabel('频率 (GHz)'); axs[1, 1].set_ylabel('功率谱 (dB)')
    axs[1, 1].set_title('MZM 前 Tx 驱动频谱', fontsize=9)
    axs[1, 1].grid(True, ls='--', alpha=0.4); axs[1, 1].legend(fontsize=8)

    fig.suptitle(f'DDPS v3 节点视图: {env_name}', fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = os.path.join(report_dir, f'ddps_v3_case_{env_name}_b.png')
    fig.savefig(out, dpi=100); plt.close(fig)
    return out


def figure_overview(test_dir, report_dir):
    summ = pd.read_csv(os.path.join(test_dir, 'case_summary.csv'))
    summ = summ.sort_values('delta_lb_seed_to_best')
    fig, ax = plt.subplots(figsize=(11, 4.6))
    x = np.arange(len(summ))
    ax.bar(x, -summ['delta_lb_seed_to_best'].values, color='#0f8a4a')
    for i, (_, r) in enumerate(summ.iterrows()):
        ax.text(i, -r['delta_lb_seed_to_best'] + 0.01,
                f'×{r["seed_ber"] / r["best_ber"]:.1f}', ha='center', fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels([f'{e}\n({env_label(e)})' for e in summ['env']], fontsize=7.5)
    ax.set_ylabel('Δlog10 BER（seed → best）')
    ax.set_title('DDPS v3：逐用例改善（冻结模型，真实 BER 不回传）', fontsize=11)
    ax.grid(True, axis='y', ls='--', alpha=0.5)
    fig.tight_layout()
    out = os.path.join(report_dir, 'ddps_v3_overview.png')
    fig.savefig(out, dpi=110); plt.close(fig)
    return out


def deep_check(test_dir, report_dir, deep_symbols, sim_seeds, only_envs=None):
    """长块 + 多种子独立复核 seed/best 两点。"""
    summ = pd.read_csv(os.path.join(test_dir, 'case_summary.csv'))
    if not os.path.exists('config.xlsx'):
        create_config.generate_config()
    base_cfg = utils_config.load_config('config.xlsx')
    rows = []
    for _, r in summ.iterrows():
        env_name = r['env']
        if only_envs is not None and env_name not in only_envs:
            continue
        env = env_case(env_name)
        cfg = apply_env_to_config(base_cfg, env)
        cfg['system']['num_symbols'] = int(deep_symbols)
        best_taps = np.array(json.loads(r['best_taps'])) if isinstance(r['best_taps'], str) \
            else np.array(r['best_taps'])
        D.set_sim_seeds(sim_seeds)
        _, seed_ber = D._physical_eval(cfg, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2, D.SEED_GAIN)
        _, best_ber = D._physical_eval(cfg, best_taps, r['best_gdc'], r['best_gdc2'],
                                       r.get('best_gain', D.SEED_GAIN))
        rows.append({'env': env_name, 'deep_symbols': int(deep_symbols),
                     'seed_ber_deep': seed_ber, 'best_ber_deep': best_ber,
                     'improve_x': seed_ber / best_ber if best_ber > 0 else np.nan})
        print(f'  [deep] {env_name:26s} seed={seed_ber:.3e} best={best_ber:.3e} '
              f'x{rows[-1]["improve_x"]:.2f}')
    df = pd.DataFrame(rows)
    out = os.path.join(report_dir, 'deep_check.csv')
    df.to_csv(out, index=False)
    return out


# ---------------------------------------------------------------------------
# Markdown 报告
# ---------------------------------------------------------------------------

def write_report(test_dir, model_dir, report_dir, protocol):
    os.makedirs(report_dir, exist_ok=True)
    summ = pd.read_csv(os.path.join(test_dir, 'case_summary.csv'))
    meta = {}
    mp = os.path.join(model_dir, 'meta.json')
    if os.path.exists(mp):
        with open(mp, encoding='utf-8') as f:
            meta = json.load(f)

    L = []
    L.append('# DDPS v3 在线调优结果报告\n')
    L.append(f'- 模型：`{model_dir}`（冻结；测试零重训、零校准）')
    L.append(f'- 评估协议：{protocol}')
    L.append(f'- 用例数：{len(summ)}；全部用例真实 BER_MLSE 逐步落盘于 `trace_<用例>.csv`\n')

    L.append('## 逐用例结果（BER_MLSE）\n')
    L.append('| 用例 | 物理条件 | 种子 | Stage-2 最优 | Δlog10 | 改善 | 最优步 | gain 种子→最优 | 劣于种子的步数 |')
    L.append('| --- | --- | --- | --- | --- | --- | --- | --- | --- |')
    worse_total = 0
    for _, r in summ.iterrows():
        trp = os.path.join(test_dir, f'trace_{r["env"]}.csv')
        worse = np.nan
        if os.path.exists(trp):
            tr = pd.read_csv(trp)
            if not tr.empty:
                worse = int((tr['real_ber'] > r['seed_ber']).sum())
                worse_total += worse
        L.append(f'| {r["env"]} | {env_label(r["env"])} | `{r["seed_ber"]:.3e}` | '
                 f'`{r["best_ber"]:.3e}` | {r["delta_lb_seed_to_best"]:+.3f} | '
                 f'×{r["seed_ber"] / r["best_ber"]:.2f} | {int(r["best_step"])} | '
                 f'{r.get("seed_gain", D.SEED_GAIN):.2f} → {r.get("best_gain", float("nan")):.3f} | {worse} |')
    L.append(f'\n> 全部用例合计：记录真实 BER 步数 {int(summ["n_steps_actual"].sum())}，'
             f'其中劣于种子的步数 **{worse_total}**。\n')

    if 'cloud' in summ.columns and summ['cloud'].notna().any():
        L.append('## 种子邻域云校验（离线证据，不参与决策）\n')
        L.append('| 用例 | 邻域点数 | Model A 方向一致率 | Model B 方向一致率 | Model A 局部 Spearman | 邻域内优于种子点数 |')
        L.append('| --- | --- | --- | --- | --- | --- |')
        for _, r in summ.iterrows():
            c = r['cloud']
            if isinstance(c, str) and c.strip():
                try:
                    c = json.loads(c.replace("'", '"'))
                except Exception:
                    continue
                L.append(f'| {r["env"]} | {c.get("n")} | {c.get("agree_a"):.3f} | '
                         f'{c.get("agree_b"):.3f} | {c.get("spearman_real_va"):.3f} | '
                         f'{c.get("n_better_than_seed")} |')
        L.append('')

    if meta:
        L.append('## 模型指标（留出集）\n')
        L.append('| 模型 | 输入维度 | R² | MSE | Spearman |')
        L.append('| --- | --- | --- | --- | --- |')
        L.append(f'| Model A（7-tap FIR + 驱动 RMS → log10 BER） | {meta.get("model_a_dim")} | '
                 f'{meta["model_a"]["r2_test"]:.3f} | {meta["model_a"]["mse_test"]:.3f} | '
                 f'{meta["model_a"]["spearman_test"]:.3f} |')
        L.append(f'| Model B（9 抽头 + gDC + gDC2 + driver_gain → log10 BER） | {meta.get("model_b_dim")} | '
                 f'{meta["model_b"]["r2_test"]:.3f} | {meta["model_b"]["mse_test"]:.3f} | '
                 f'{meta["model_b"]["spearman_test"]:.3f} |')
        L.append('')

    L.append('## 图件\n')
    L.append('- `ddps_v3_overview.png`：逐用例改善总览')
    L.append('- `ddps_v3_case_<用例>_a.png`：收敛 / FFE 抽头 / CTLE 频响 / driver_gain 轨迹')
    L.append('- `ddps_v3_case_<用例>_b.png`：Rx 眼图（种子 vs 最优）/ FFE 输出分布 / Tx 频谱')
    L.append('- `deep_check.csv`：长块 + 多种子独立复核\n')

    out = os.path.join(report_dir, 'ddps_v3_report.md')
    with open(out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(L))
    return out


def write_summary(entries, report_dir, out_path):
    os.makedirs(report_dir, exist_ok=True)
    """跨实验汇总（例如 核心=只用基线 / 上限=带锚点 / 消融=冻结新增维度）。"""
    frames = {}
    for d, lab in entries:
        p = os.path.join(d, 'case_summary.csv')
        if os.path.exists(p):
            frames[lab] = pd.read_csv(p)

    L = ['# DDPS v3：跨实验汇总（BER_MLSE）\n']
    baseline_label = entries[0][1] if entries else ''
    if baseline_label in frames:
        L.append(f'主表以 **{baseline_label}** 为基准；所有实验共用同一套评估协议与同一批用例。\n')
        base = frames[baseline_label]
        L.append('| 用例 | 物理条件 | 种子 | ' +
                 ' | '.join([f'{lab} 最优' for lab in frames]) + ' | 改善（' + baseline_label + '） |')
        L.append('| --- | --- | --- | ' + ' | '.join(['---'] * len(frames)) + ' | --- |')
        for _, r0 in base.iterrows():
            env = r0['env']
            cells = []
            for lab, df in frames.items():
                m = df[df['env'] == env]
                cells.append(f'`{m.iloc[0]["best_ber"]:.3e}`' if len(m) else '—')
            L.append(f'| {env} | {env_label(env)} | `{r0["seed_ber"]:.3e}` | ' +
                     ' | '.join(cells) + f' | ×{r0["seed_ber"] / r0["best_ber"]:.2f} |')
        L.append('')
        for lab, df in frames.items():
            worse = 0
            for _, r in df.iterrows():
                trp = None
                for d, l in entries:
                    if l == lab:
                        trp = os.path.join(d, f'trace_{r["env"]}.csv')
                if trp and os.path.exists(trp):
                    tr = pd.read_csv(trp)
                    if not tr.empty:
                        worse += int((tr['real_ber'] > r['seed_ber']).sum())
            L.append(f'- **{lab}**：{len(df)} 用例，记录步数 {int(df["n_steps_actual"].sum())}，'
                     f'劣于种子的步数 {worse}；平均改善 '
                     f'×{float((df["seed_ber"] / df["best_ber"]).mean()):.2f}')
        L.append('')

    out = os.path.join(report_dir, out_path)
    with open(out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(L))
    return out


def figure_delta(entries, report_dir):
    os.makedirs(report_dir, exist_ok=True)
    frames = {lab: pd.read_csv(os.path.join(d, 'case_summary.csv'))
              for d, lab in entries if os.path.exists(os.path.join(d, 'case_summary.csv'))}
    if len(frames) < 2:
        return None
    base = list(frames.values())[0]
    envs = list(base['env'])
    fig, ax = plt.subplots(figsize=(12, 5))
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
    ax.set_title('DDPS v3：不同训练集/消融的改善量对照', fontsize=11)
    ax.grid(True, axis='y', ls='--', alpha=0.5); ax.legend(fontsize=9)
    fig.tight_layout()
    out = os.path.join(report_dir, 'fig_delta_compare.png')
    fig.savefig(out, dpi=110); plt.close(fig)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--test-dir', required=True)
    ap.add_argument('--model-dir', default='models/ddps_v3')
    ap.add_argument('--deep-symbols', type=int, default=0,
                    help='深水复核符号数（0=不复核）')
    ap.add_argument('--sim-seeds', type=str, default='42')
    ap.add_argument('--summary', nargs='*', default=None,
                    help='跨实验汇总，形如 "result/ddps_v3_control:只用基线" '
                         '"result/ddps_v3_20260910:带锚点"')
    ap.add_argument('--summary-out', default='SUMMARY.md')
    ap.add_argument('--skip-nodes', action='store_true', help='跳过眼图/频谱节点视图（省时）')
    a = ap.parse_args()

    report_dir = os.path.join(a.test_dir, 'report')
    os.makedirs(report_dir, exist_ok=True)

    if not os.path.exists('config.xlsx'):
        create_config.generate_config()
    baud_rate = float(utils_config.load_config('config.xlsx')['system']['baud_rate'])
    sim_seeds = tuple(int(s) for s in str(a.sim_seeds).split(',') if s.strip())

    summ = pd.read_csv(os.path.join(a.test_dir, 'case_summary.csv'))
    envs = list(summ['env'])
    print(f'[report v3] {len(envs)} cases -> {report_dir}')

    for e in envs:
        figure_case(a.test_dir, e, report_dir, baud_rate)
        if not a.skip_nodes:
            try:
                figure_nodes(a.test_dir, e, report_dir)
            except Exception as ex:
                print(f'  (node view skipped for {e}: {ex})')
    figure_overview(a.test_dir, report_dir)

    protocol = (f'BER_MLSE @ {int(summ["n_steps_actual"].sum())} 步记录；'
                f'用例 {len(envs)} 个；真实 BER 逐步落盘')
    if os.path.exists(os.path.join(a.test_dir, 'run_config.json')):
        with open(os.path.join(a.test_dir, 'run_config.json'), encoding='utf-8') as f:
            rc = json.load(f)
        protocol = (f'{rc["num_symbols"]} 符号/点 × 仿真种子 {rc["sim_seeds"]} 取 log10 均值；'
                    f'用例 {len(envs)} 个；n_steps 上限 {rc["n_steps"]}；'
                    f'freeze_extra={rc.get("freeze_extra")}')

    print(write_report(a.test_dir, a.model_dir, report_dir, protocol))

    if a.deep_symbols and a.deep_symbols > 0:
        print(f'[deep] {a.deep_symbols} 符号独立复核 ...')
        print(deep_check(a.test_dir, report_dir, a.deep_symbols, sim_seeds))

    if a.summary:
        entries = []
        for item in a.summary:
            if ':' in item:
                d, lab = item.rsplit(':', 1)
            else:
                d, lab = item, os.path.basename(item.rstrip('/'))
            entries.append((d, lab))
        if len(entries) >= 2:
            print(figure_delta(entries, report_dir) or '(delta figure skipped)')
        print(write_summary(entries, report_dir, a.summary_out))
