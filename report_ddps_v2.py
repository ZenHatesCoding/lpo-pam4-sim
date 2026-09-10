# [v2 时代脚本] 用于 v2 物理模型（CTLE 位置 / driver_gain 修正前）的结果报告。
# v2 产物已归档到 archive/20260910_ddps_v2_pre_ctle_reorder/（不入库），本脚本默认路径已不存在。
# 当前请使用 report_ddps_v3.py（见 docs/07_DDPS_v3_Model_Update.md）。
# -*- coding: utf-8 -*-
"""report_ddps_v2.py — DDPS v2 可视化结果报告生成器。

输入:
  --test-dir : test_generalization.py 的输出目录（case_summary.json/csv + trace_*.csv）
  --model-dir: 训练模型目录（meta.json 含代理评估指标）
  --deep-symbols: 对 seed/best 配置做更高符号数统计复核（默认 262144, 0=关闭）

输出:
  <out>/ddps_v2_report.md / .csv       中文总结报告（含 BER_MLSE 口径说明）
  <out>/ddps_v2_overview.png           全用例改善总览
  <out>/ddps_v2_case_<name>_a.png      收敛+抽头+CTLE 响应+Tx-FIR
  <out>/ddps_v2_case_<name>_b.png      眼图+频谱+均衡电平 (seed vs best)
  <out>/deep_check.csv                  高符号数统计复核
"""
import os
import json
import ast
import argparse
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.signal import welch, resample_poly

import create_config, utils_config
import ddps_optimizer as D
from ddps_cases import ENV_CASES, apply_env_to_config
from main import run_sim
from tx_channel_extract import extract_tx_s21

BAUD = None  # set from config


# ---------------------------------------------------------------------------
# 物理量曲线
# ---------------------------------------------------------------------------
def ctle_response_db(f, gdc_db, gdc2_db, tx):
    """Tx CTLE |H(f)|（与 channel_imdd.apply_ctle 同式），f: Hz 数组 -> dB。"""
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


def eye_ax(ax, y, sps, title, n_traces=320, target_sps=32, color='C0'):
    """在 ax 上画 2-UI 眼图。y: 过采样实信号 (sps 样点/符号)。"""
    y = np.asarray(y, dtype=float)
    if len(y) < sps * 20:
        ax.set_title(title + ' (too short)', fontsize=9)
        return
    k_symbols = n_traces + 4
    y_up = resample_poly(y[: k_symbols * sps], target_sps, sps)
    for i in range(n_traces):
        s = i * target_sps
        ax.plot(np.linspace(0, 2, 2 * target_sps),
                y_up[s:s + 2 * target_sps], color=color, alpha=0.12, lw=0.7)
    ax.set_title(title, fontsize=9)
    ax.set_xlabel('UI'); ax.set_ylabel('amp')
    ax.grid(True, alpha=0.3)


def psd_ax(ax, y, fs, title, fmax_hz=None):
    f, p = welch(np.asarray(y, dtype=float), fs=fs, nperseg=2048, return_onesided=True)
    ax.plot(f / 1e9, 10 * np.log10(p + 1e-30), lw=0.8)
    if fmax_hz:
        ax.set_xlim(0, fmax_hz / 1e9)
    ax.set_title(title, fontsize=9)
    ax.set_xlabel('GHz'); ax.set_ylabel('dB')
    ax.grid(True, alpha=0.3)


def level_scatter_ax(ax, rx_eq, tx_pam4, train_len, title, n_show=5000):
    """Rx FFE 均衡输出(T 间隔)按真实符号着色的电平散点（喂给 MLSE 前的软信息）。"""
    eq = rx_eq[train_len + 20:]
    ref = tx_pam4[train_len + 20:]
    m = min(len(eq), len(ref))
    eq, ref = eq[:m], ref[:m]
    colors = {0: '#1f77b4', 1: '#ff7f0e', 2: '#2ca02c', 3: '#d62728'}
    for sym in range(4):
        sel = np.where(ref == sym * 2 - 3)[0]
        if len(sel) > n_show:
            sel = sel[np.linspace(0, len(sel) - 1, n_show).astype(int)]
        ax.plot(sel, eq[sel], '.', ms=1.0, color=colors[sym], label=f'L{sym}')
    ax.set_title(title, fontsize=9)
    ax.set_xlabel('sample idx'); ax.set_ylabel('rx_eq (FFE out)')
    ax.legend(fontsize=6, markerscale=2, ncol=2)
    ax.grid(True, alpha=0.3)


def capture_cfg(env, taps, gdc, gdc2, num_symbols=32768):
    """在指定系数下跑一次带节点捕获的仿真（BER 数字另由 131072 协议给出）。"""
    cfg = apply_env_to_config(utils_config.load_config('config.xlsx'), env)
    cfg['system']['num_symbols'] = int(num_symbols)
    cfg['tx']['ctle_g_dc_db'] = float(gdc)
    cfg['tx']['ctle_g_dc2_db'] = float(gdc2)
    _, _, nodes = run_sim(cfg, custom_tx_taps=np.asarray(taps, dtype=float),
                          plot_eyes=False, output_dir=None, return_nodes=True)
    nodes['tx_fir'] = extract_tx_s21(cfg, custom_tx_taps=np.asarray(taps, dtype=float),
                                     num_taps=7)
    return nodes


def _best_taps_from_row(row):
    """从 summary 行解析 best_taps (ndarray or None)。"""
    if 'best_taps' not in row or pd.isna(row['best_taps']):
        return None
    v = row['best_taps']
    if isinstance(v, str):
        try:
            v = ast.literal_eval(v)
        except Exception:
            v = np.fromstring(v.strip('[]'), sep=' ')
    return np.asarray(v, dtype=float)


def _fval(v):
    try:
        return float(v)
    except Exception:
        return np.nan


# ---------------------------------------------------------------------------
# 图
# ---------------------------------------------------------------------------
def plot_case_a(out_dir, name, summary, trace_df, tx_cfg, fir_seed, fir_best,
                ctle_seed, ctle_best):
    fig, axs = plt.subplots(2, 2, figsize=(15, 9))
    ax = axs[0, 0]
    if len(trace_df):
        ax.plot(trace_df['step'], trace_df['real_lb'], 'o-', ms=4,
                label='real BER_MLSE (log10, recorded only)')
        ax.plot(trace_df['step'], trace_df['pred_a'], 'x--', ms=4,
                label='Model A pred (Tx FIR)')
        ax.plot(trace_df['step'], trace_df['pred_b'], 's:', ms=3,
                label='Model B pred (config, safety)')
    ax.axhline(_fval(summary['seed_lb']), color='red', ls=':', label='seed x0')
    if not pd.isna(summary.get('best_step')):
        ax.axvline(int(summary['best_step']), color='green', ls=':', lw=1)
    ax.set_title(f'{name}: Stage-2 online tuning (BER_MLSE)', fontsize=10)
    ax.set_xlabel('Stage-2 step'); ax.set_ylabel('log10(BER_MLSE)')
    ax.grid(True, which='both', ls='--', alpha=0.4)
    ax.legend(fontsize=7)

    ax = axs[0, 1]
    xs = np.arange(9)
    w = 0.4
    seed_taps = D.SEED_TAPS.copy()
    ax.bar(xs - w / 2, seed_taps, width=w, color='#8888cc', label='seed')
    if summary.get('best_taps') is not None and not pd.isna(summary['best_taps']):
        bt = _best_taps_from_row(summary)
        if bt is not None:
            ax.bar(xs + w / 2, bt, width=w, color='#cc5555', label='best (Stage-2)')
    ax.axvline(4.5, color='k', lw=0.5)
    ax.set_title('Tx FFE taps (9-tap, center=idx4)', fontsize=10)
    ax.set_xticks(xs); ax.legend(fontsize=7); ax.grid(alpha=0.3, axis='y')

    ax = axs[1, 0]
    f = np.linspace(0, 2.0 * BAUD, 800)
    ax.plot(f / 1e9, ctle_seed,
            label=f'seed (gDC={D.SEED_GDC:.2f}, gDC2={D.SEED_GDC2:.2f})')
    if ctle_best is not None:
        ax.plot(f / 1e9, ctle_best, ls='--',
                label=f'best (gDC={_fval(summary.get("best_gdc")):.2f}, '
                      f'gDC2={_fval(summary.get("best_gdc2")):.2f})')
    ax.axvline(BAUD / 2 / 1e9, color='k', ls=':', lw=1, label='Nyquist')
    ax.set_title('Tx CTLE |H(f)| (analog EQ)', fontsize=10)
    ax.set_xlabel('GHz'); ax.set_ylabel('dB')
    ax.legend(fontsize=8); ax.grid(alpha=0.3)

    ax = axs[1, 1]
    xs7 = np.arange(7)
    w7 = 0.35
    ax.bar(xs7 - w7 / 2, fir_seed, width=w7, color='#8888cc', label='seed')
    if fir_best is not None:
        ax.bar(xs7 + w7 / 2, fir_best, width=w7, color='#cc5555', label='best')
    ax.set_title('Tx physical FIR probe (7-tap, Model-A feature)', fontsize=10)
    ax.set_xticks(xs7); ax.legend(fontsize=7); ax.grid(alpha=0.3, axis='y')

    fig.suptitle(f'DDPS v2 case: {name}', fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(os.path.join(out_dir, f'ddps_v2_case_{name}_a.png'), dpi=110)
    plt.close(fig)


def plot_case_b(out_dir, name, seed_nodes, best_nodes, has_best):
    sps_ch = 8
    fs_ch = BAUD * sps_ch
    fig, axs = plt.subplots(3, 4, figsize=(18, 11))
    best_tag = 'best' if has_best else 'seed(=no move)'
    eye_ax(axs[0, 0], seed_nodes['tx_analog'], sps_ch, 'Tx analog eye (seed)')
    eye_ax(axs[0, 1], best_nodes['tx_analog'], sps_ch, f'Tx analog eye ({best_tag})')
    eye_ax(axs[1, 0], seed_nodes['rx_analog'], sps_ch, 'Rx ADC-in eye (seed)')
    eye_ax(axs[1, 1], best_nodes['rx_analog'], sps_ch, f'Rx ADC-in eye ({best_tag})')
    level_scatter_ax(axs[2, 0], seed_nodes['rx_eq'], seed_nodes['tx_pam4'],
                     seed_nodes['train_len'], 'Rx FFE output levels (seed)')
    level_scatter_ax(axs[2, 1], best_nodes['rx_eq'], best_nodes['tx_pam4'],
                     best_nodes['train_len'], f'Rx FFE output levels ({best_tag})')

    psd_ax(axs[0, 2], seed_nodes['tx_analog'], fs_ch, 'PSD Tx analog (seed)', 2 * BAUD)
    psd_ax(axs[0, 3], best_nodes['tx_analog'], fs_ch, f'PSD Tx analog ({best_tag})', 2 * BAUD)
    psd_ax(axs[1, 2], seed_nodes['rx_analog'], fs_ch, 'PSD Rx ADC-in (seed)', 2 * BAUD)
    psd_ax(axs[1, 3], best_nodes['rx_analog'], fs_ch, f'PSD Rx ADC-in ({best_tag})', 2 * BAUD)

    for col, nd, tag in [(2, seed_nodes, 'seed'), (3, best_nodes, best_tag)]:
        eq = nd['rx_eq'][nd['train_len'] + 50:]
        ref = nd['tx_pam4'][nd['train_len'] + 50:]
        m = min(len(eq), len(ref))
        eq, ref = eq[:m], ref[:m]
        for sym in range(4):
            v = eq[ref == sym * 2 - 3]
            if len(v):
                axs[2, col].hist(v, bins=40, alpha=0.55, histtype='stepfilled',
                                 label=f'L{sym} (n={len(v)})')
        axs[2, col].set_title(f'Rx FFE output histogram ({tag})', fontsize=9)
        axs[2, col].set_xlabel('rx_eq'); axs[2, col].legend(fontsize=6)
    fig.suptitle(f'DDPS v2 node views: {name}', fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(os.path.join(out_dir, f'ddps_v2_case_{name}_b.png'), dpi=100)
    plt.close(fig)


def plot_overview(out_dir, summary_df):
    fig, ax = plt.subplots(figsize=(12, 7))
    names = summary_df['env'].tolist()
    y = np.arange(len(names))
    delta = summary_df['delta_lb_seed_to_best'].astype(float).fillna(0.0).values
    best_lb = summary_df['best_lb'].astype(float).values
    colors = ['#2e8b57' if d < -0.01 else '#d62728' if d > 0.01 else '#999999'
              for d in delta]
    ax.barh(y, delta, color=colors)
    for i, (d, blb) in enumerate(zip(delta, best_lb)):
        if not np.isnan(blb):
            ax.text(d + (0.01 if d >= 0 else -0.01), i,
                    f'{10 ** blb:.2e}', va='center', ha='left' if d >= 0 else 'right',
                    fontsize=8)
    ax.set_yticks(y); ax.set_yticklabels(names)
    ax.axvline(0, color='k', lw=0.8)
    ax.set_xlabel(r'$\Delta \log_{10}(BER\_MLSE)$: seed $\rightarrow$ Stage-2 best (negative = improvement)')
    ax.set_title('DDPS v2: per-case improvement (frozen models, no real-BER feedback)')
    ax.grid(alpha=0.3, axis='x')
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, 'ddps_v2_overview.png'), dpi=110)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Markdown 总结
# ---------------------------------------------------------------------------
def write_md(out_dir, model_meta, summary_df, deep_df):
    rows = []
    for _, r in summary_df.iterrows():
        env = r['env']
        seed = _fval(r['seed_ber'])
        best = _fval(r.get('best_ber'))
        dl = _fval(r.get('delta_lb_seed_to_best'))
        ts = _fval(r.get('trace_spearman_preda_real'))
        nsteps = int(_fval(r.get('n_steps_actual', 0)) or 0)
        bstep = int(_fval(r.get('best_step', 0)) or 0)
        if not np.isnan(best):
            best_s = f'`{best:.2e}` (step {bstep})'
            tag = ('✅ 改善' if dl < -0.01 else
                   ('❌ 变差' if dl > 0.01 else '➖ 持平'))
        else:
            best_s = '(未下探)'; tag = '➖ 持平'
        ts_s = f'{ts:.2f}' if not np.isnan(ts) else '-'
        rows.append(f"| {env} | `{seed:.2e}` | {best_s} | `{dl:.2f}` | {nsteps} | "
                    f"{tag} | {ts_s} |")
    tbl = "\n".join(rows)

    lines = []
    lines.append('# DDPS v2 全链路重做报告（数据收集 → 训练 → 在线调优泛化测试）\n')
    lines.append('> 本报告与历史版本隔离存放；历史归档见 '
                 '`archive/20260904_ddps_v1_physical_pre_v2/`（旧数据/模型/结果不参与本报告）。\n')
    lines.append('## 0. 指标口径（BER_MLSE）\n')
    lines.append('- 收端算法：Rx 22-tap T-spaced LMS FFE（DFE=0）→ **MLSE**'
                 '（Viterbi，memory=1，Burg AR 白化）。当前配置 `mlse_memory=1`，'
                 '平台所有误码率均为此 MLSE 判决输出（Gray 映射，BER≈SER/2）。')
    lines.append('- 因此链路终极指标统一记作 **`BER_MLSE`**（对数域 `log10(BER_MLSE)`）；'
                 'Stage-2 全程"所测即所发生"，凡下发的系数均记录真实 BER（含最差步）。')
    lines.append('- 评估协议：PAM4 131072 符号/点，固定种子（Tx=42，噪声=123）；'
                 '统计复核见第 4 节更高符号数重测。\n')
    lines.append('## 1. v1 失败根因与 v2 修正（代码层面，已逐一落地）\n')
    lines.append('| # | 根因 | v1 现象 | v2 修正 |')
    lines.append('| --- | --- | --- | --- |')
    lines.append('| 1 | Stage-1 邻域采样死代码 | LHS 采样器 `d=9` 却索引 `sp[i,9]`，'
                 '首样本 IndexError，邻域数据从未生成 | `d=10` 修复；由 `dataset_generator.py`'
                 '统一生成"环境锚定邻域"数据 |')
    lines.append('| 2 | FFE 参数化错配 | 数据主抽头恒=1.0；下降空间主抽头=1−Σ|旁瓣|≈0.61，'
                 '训练域与下降域错位，Model B 完全外推 | 全局统一 `主抽头=1−Σ|旁瓣|`'
                 '（Σ|taps|≡1，Tx FFE 归一化恒等） |')
    lines.append('| 3 | Tx-FIR 探针对齐错误 | S4P 频率缩放随 IL 改变群时延（实测峰值 idx：'
                 'IL10=1247 vs IL20=238），进程级粘滞锁使跨环境 FIR 在错误符号格采样 → '
                 'Model A 输入 OOD/趋平 | 对齐基准按"环境"缓存（透传冲激 argmax），'
                 '训练/在线/跨进程一致 |')
    lines.append('| 4 | Stage-2 无梯度门控 | 代理曲面在外推区趋平（|g|~1e-4）仍沿拟合噪声'
                 '下降 → 真实 BER_MLSE 反向爬升（负向优化） | `|∇ModelA| < 0.05` 即停，'
                 '不进入无效区乱走 |')
    lines.append('| 5 | 模型 pickle 依赖 `__main__` | v1 pkl 无法跨脚本加载 | `train_v2` 以'
                 '模块路径安全序列化；`load_models()` 兼容旧档 |')
    lines.append('| 6 | 报告口径 | docs 声称"彻底告别发散"，result 结论却相反；'
                 '命名混乱 | 统一 BER_MLSE 口径，报告按实测逐项撰写 |\n')

    lines.append('## 2. 数据集与训练\n')
    if model_meta:
        mm = model_meta
        lines.append(f"- 数据：环境锚定邻域采样（每点真实 BER_MLSE），覆盖信任域"
                     f" FFE ±{D.TRUST_FFE} / CTLE ±{D.TRUST_CTLE} dB；"
                     f"n_train={mm.get('n_train')}, n_test={mm.get('n_test')}")
        lines.append(f"- 数据文件：`{mm.get('dataset_csv')}`；标签列：`{mm.get('label_col')}`")
        ma, mb = mm.get('model_a', {}), mm.get('model_b', {})
        lines.append(f"- **Model A**（Tx 7-tap FIR → log10 BER_MLSE，寻优目标）："
                     f"Test R²={_fval(ma.get('r2_test')):.3f}, "
                     f"Spearman={_fval(ma.get('spearman_test')):.3f}")
        lines.append(f"- **Model B**（FFE+CTLE 配置 → log10 BER_MLSE，安全约束）："
                     f"Test R²={_fval(mb.get('r2_test')):.3f}, "
                     f"Spearman={_fval(mb.get('spearman_test')):.3f}")
        lines.append('- 两模型均为手写二阶多项式 Ridge（闭式解，纯 numpy）；寻优只依赖'
                     '排序/方向，Spearman 为主评估指标。')
        byenv = mm.get('model_a_by_env')
        if byenv:
            lines.append('\nModel A 测试集按环境划分的 Spearman（各环境锚点 holdout）：')
            lines.append('| 环境 | n_test | Spearman |')
            lines.append('| --- | --- | --- |')
            for e, v in byenv.items():
                lines.append(f'| {e} | {v.get("n", "-")} | {_fval(v.get("spearman_test")):.3f} |')
        lines.append('')
    lines.append('## 3. 泛化测试结果（模型冻结复用，逐环境 Stage-2 在线调优）\n')
    lines.append('| 用例 | 种子 BER_MLSE | Stage-2 最优 (步) | Δlog10 | 步数 | 判定 | 轨迹一致性 |')
    lines.append('| --- | --- | --- | --- | --- | --- | --- |')
    lines.append(tbl)
    lines.append('\n> 轨迹一致性 = 收敛轨迹上 Model A 预测与真实 BER_MLSE 的 Spearman'
                 '（越接近 1 方向越准）。真实 BER 只记录、不参与方向决策。\n')
    if deep_df is not None and len(deep_df):
        lines.append('## 4. 统计复核（更高符号数重测 seed/best）\n')
        lines.append('| 用例 | seed BER_MLSE (deep) | best BER_MLSE (deep) | Δlog10 (deep) |')
        lines.append('| --- | --- | --- | --- |')
        for _, r in deep_df.iterrows():
            lines.append(f"| {r['env']} | `{_fval(r['seed_ber_deep']):.2e}` | "
                         f"`{_fval(r['best_ber_deep']):.2e}` | "
                         f"`{_fval(r['delta_deep']):.2f}` |")
        lines.append('')
    lines.append('## 5. 图件索引\n')
    lines.append('- `ddps_v2_overview.png`：各用例 seed→best 改善量')
    lines.append('- `ddps_v2_case_<用例>_a.png`：收敛轨迹(真实/Model A/Model B) + '
                 'Tx FFE 抽头 + Tx CTLE 频率响应 + Tx FIR 探针（优化前后对照）')
    lines.append('- `ddps_v2_case_<用例>_b.png`：seed vs best 的 Tx 模拟眼图、Rx ADC 输入眼图、'
                 'Rx FFE 均衡电平/直方图、功率谱')
    lines.append('- `case_summary.csv/.json`、`trace_*.csv`：全部数值可审计')

    with open(os.path.join(out_dir, 'ddps_v2_report.md'), 'w', encoding='utf-8') as f:
        f.write("\n".join(lines) + "\n")
    print('[report] ddps_v2_report.md written')


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--test-dir', required=True)
    ap.add_argument('--model-dir', default='models/ddps_v2')
    ap.add_argument('--out-dir', default=None)
    ap.add_argument('--deep-symbols', type=int, default=262144)
    ap.add_argument('--capture-symbols', type=int, default=32768)
    a = ap.parse_args()

    global BAUD
    create_config.generate_config()
    cfg0 = utils_config.load_config('config.xlsx')
    BAUD = float(cfg0['system']['baud_rate'])
    tx_cfg = cfg0['tx']

    out = a.out_dir or os.path.join(a.test_dir, 'report')
    os.makedirs(out, exist_ok=True)

    summary = pd.read_csv(os.path.join(a.test_dir, 'case_summary.csv'))
    try:
        with open(os.path.join(a.model_dir, 'meta.json'), encoding='utf-8') as f:
            model_meta = json.load(f)
    except Exception:
        model_meta = None

    deep_rows = []
    for env in ENV_CASES:
        name = env['name']
        srow = summary[summary['env'] == name].iloc[0]
        tf_path = os.path.join(a.test_dir, f'trace_{name}.csv')
        trace_df = pd.read_csv(tf_path) if os.path.exists(tf_path) else pd.DataFrame()

        cfg_e = apply_env_to_config(utils_config.load_config('config.xlsx'), env)
        seed_taps = D.SEED_TAPS.copy()
        bt = _best_taps_from_row(srow)
        if bt is not None and np.allclose(bt, seed_taps, atol=1e-6):
            bt = None
        has_best = bt is not None
        bg, bg2 = (float(srow['best_gdc']), float(srow['best_gdc2'])) if has_best \
            else (D.SEED_GDC, D.SEED_GDC2)

        # Tx FIR & CTLE 曲线（seed vs best）
        fir_seed = extract_tx_s21(cfg_e, custom_tx_taps=seed_taps, num_taps=7)
        fir_best = None
        if has_best:
            cfg_b = apply_env_to_config(utils_config.load_config('config.xlsx'), env)
            cfg_b['tx']['ctle_g_dc_db'] = bg
            cfg_b['tx']['ctle_g_dc2_db'] = bg2
            fir_best = extract_tx_s21(cfg_b, custom_tx_taps=bt, num_taps=7)
        f = np.linspace(0, 2.0 * BAUD, 800)
        ctle_seed = ctle_response_db(f, D.SEED_GDC, D.SEED_GDC2, tx_cfg)
        ctle_best = ctle_response_db(f, bg, bg2, tx_cfg) if has_best else None
        plot_case_a(out, name, srow.to_dict(), trace_df, tx_cfg,
                    fir_seed, fir_best, ctle_seed, ctle_best)

        # 节点捕获（短序列，仅作可视化）
        print(f'[report] capture nodes: {name}')
        seed_nodes = capture_cfg(env, seed_taps, D.SEED_GDC, D.SEED_GDC2,
                                 num_symbols=a.capture_symbols)
        best_nodes = (capture_cfg(env, bt, bg, bg2, num_symbols=a.capture_symbols)
                      if has_best else seed_nodes)
        plot_case_b(out, name, seed_nodes, best_nodes, has_best)

        # deep 复核
        if a.deep_symbols > 0:
            cde = apply_env_to_config(utils_config.load_config('config.xlsx'), env)
            cde['system']['num_symbols'] = a.deep_symbols
            _, sb = D._physical_eval(cde, seed_taps, D.SEED_GDC, D.SEED_GDC2)
            if has_best:
                _, bb = D._physical_eval(cde, bt, bg, bg2)
            else:
                bb = sb
            deep_rows.append({'env': name, 'seed_ber_deep': sb, 'best_ber_deep': bb,
                              'delta_deep': float(np.log10(max(bb, 1e-12)) -
                                                  np.log10(max(sb, 1e-12)))})
            print(f'    deep({a.deep_symbols} sym): seed={sb:.3e} best={bb:.3e}')

    deep_df = pd.DataFrame(deep_rows) if deep_rows else None
    if deep_df is not None:
        deep_df.to_csv(os.path.join(out, 'deep_check.csv'), index=False)
    plot_overview(out, summary)
    write_md(out, model_meta, summary, deep_df)
    print(f'[report] done -> {out}')


if __name__ == '__main__':
    main()
