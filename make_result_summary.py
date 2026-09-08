# -*- coding: utf-8 -*-
"""make_result_summary.py — 从现有产物重建"结果对比页"（不重跑任何仿真）

只读已有文件并产出：
  result/ddps_v2_20260907/report/fig_convergence_compare.png   8 用例收敛对比（同轴对数）
  result/ddps_v2_20260907/report/fig_taps_compare.png          8 用例抽头对比（seed vs best）
  result/SUMMARY.md                                            单页结果文档（两组实验并列对比）

用法: python make_result_summary.py
"""
import os
import re
import json
import argparse
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import ddps_optimizer as D
from ddps_cases import ENV_CASES


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float('nan')


def _mult(delta_lb):
    """Δlog10 -> 改善倍数（正值>1 表示改善多少倍）。"""
    d = _f(delta_lb)
    return 10 ** (-d) if not np.isnan(d) else np.nan


def _load_summary(path):
    df = pd.read_csv(path)
    return df.set_index('env')


def _load_json_recs(path):
    with open(path, encoding='utf-8') as f:
        recs = json.load(f)
    return {r['env']: r for r in recs}


def _taps_float(t):
    if isinstance(t, str):
        try:
            return np.asarray(json.loads(t))
        except Exception:
            import ast
            try:
                return np.asarray(ast.literal_eval(t))
            except Exception:
                return None
    return np.asarray(t, dtype=float) if t is not None else None


def _plot_convergence_compare(run_dir, out_png):
    n = len(ENV_CASES)
    cols = 4
    rows = int(np.ceil(n / cols))
    fig, axs = plt.subplots(rows, cols, figsize=(18, 2.6 * rows), squeeze=False)
    for k, env in enumerate(ENV_CASES):
        ax = axs[k // cols][k % cols]
        name = env['name']
        tf = pd.read_csv(os.path.join(run_dir, f'trace_{name}.csv'))
        real = tf['real_ber'].values
        ax.semilogy(tf['step'].values, real, 'o-', ms=3.5, lw=1.2, color='#1f77b4',
                    label='real BER_MLSE')
        pred = np.clip(10.0 ** tf['pred_a'].values, 1e-8, 1)
        ax.semilogy(tf['step'].values, pred, 'x--', ms=3, lw=0.9, color='#ff7f0e',
                    label='Model A pred')
        if len(tf):
            i = int(np.argmin(real))
            ax.plot(tf['step'].values[i], real[i], 'o', ms=9, mfc='none', mec='#d62728')
        # seed 水平线
        cs = pd.read_csv(os.path.join(run_dir, 'case_summary.csv'))
        seed_ber = cs[cs['env'] == name]['seed_ber'].iloc[0]
        ax.axhline(seed_ber, ls=':', color='grey', lw=1)
        ax.set_title(f"{name}  (IL{env['il']:.0f}dB"
                     f"{'+CD'+str(int(env['cd'])) if env['cd'] else ''}"
                     f"{'+DGD'+str(int(env['dgd'])) if env['dgd'] else ''})", fontsize=9)
        ax.grid(True, which='both', ls='--', alpha=0.3)
        ax.set_ylim(1e-4, 1e-1)
        if k == 0:
            ax.legend(fontsize=7)
        if k >= n - cols:
            ax.set_xlabel('Stage-2 step')
    fig.suptitle('DDPS v2 Stage-2 convergence per case (solid = real BER_MLSE, '
                 'dashed = Model A pred, grey = seed, open red circle = trace best)',
                 fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(out_png, dpi=110)
    plt.close(fig)


def _plot_taps_compare(run_dir, out_png):
    n = len(ENV_CASES)
    cols = 4
    rows = int(np.ceil(n / cols))
    fig, axs = plt.subplots(rows, cols, figsize=(18, 2.8 * rows), squeeze=False)
    for k, env in enumerate(ENV_CASES):
        ax = axs[k // cols][k % cols]
        name = env['name']
        cs = pd.read_csv(os.path.join(run_dir, 'case_summary.csv'))
        row = cs[cs['env'] == name].iloc[0]
        bt = _taps_float(row['best_taps'])
        xs = np.arange(9)
        w = 0.38
        ax.bar(xs - w / 2, D.SEED_TAPS, width=w, color='#8a8ab8', label='seed')
        if bt is not None and len(bt) == 9:
            ax.bar(xs + w / 2, bt, width=w, color='#c66', label='best')
        ax.axvline(4.5, color='k', lw=0.4)
        g = row['best_gdc']; g2 = row['best_gdc2']
        ax.set_title(f"{name}\ngDC={_f(g):+.2f} dB, gDC2={_f(g2):+.2f} dB", fontsize=8)
        ax.grid(alpha=0.3, axis='y')
        if k == 0:
            ax.legend(fontsize=7)
    fig.suptitle('Tx FFE taps: seed vs Stage-2 best (center = idx4, main tap = 1-Sum|side|)',
                 fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(out_png, dpi=110)
    plt.close(fig)


def _plot_overview_english(run_dir, out_png):
    """重画 seed→best 改善量（英文标注；只读 case_summary，不跑仿真）。"""
    df = pd.read_csv(os.path.join(run_dir, 'case_summary.csv'))
    names = df['env'].tolist()
    y = np.arange(len(names))
    delta = df['delta_lb_seed_to_best'].astype(float).fillna(0.0).values
    best_lb = df['best_lb'].astype(float).values
    colors = ['#2e8b57' if d < -0.01 else '#d62728' if d > 0.01 else '#999999'
              for d in delta]
    fig, ax = plt.subplots(figsize=(11, 6.5))
    ax.barh(y, delta, color=colors)
    for i, (d, blb) in enumerate(zip(delta, best_lb)):
        if not np.isnan(blb):
            ax.text(d + (0.01 if d >= 0 else -0.01), i, f'{10 ** blb:.2e}',
                    va='center', ha='left' if d >= 0 else 'right', fontsize=8)
    ax.set_yticks(y); ax.set_yticklabels(names)
    ax.axvline(0, color='k', lw=0.8)
    ax.set_xlabel('d log10(BER_MLSE): seed -> Stage-2 best (negative = improvement)')
    ax.set_title('DDPS v2 per-case improvement (frozen mixed-env models, no real-BER feedback)')
    ax.grid(alpha=0.3, axis='x')
    fig.tight_layout()
    fig.savefig(out_png, dpi=110)
    plt.close(fig)


def _link_ok(base_dir, target):
    if target.startswith(('http://', 'https://', '#')):
        return True
    t = target.split('#')[0]
    return os.path.exists(os.path.abspath(os.path.join(base_dir, t)))


def check_links(md_path):
    """粗略校验 md 内相对链接/图片是否存在。"""
    with open(md_path, encoding='utf-8') as f:
        text = f.read()
    base = os.path.dirname(os.path.abspath(md_path))
    bad = []
    for m in re.finditer(r'\[[^\]]*\]\(([^)]+)\)', text):
        if not _link_ok(base, m.group(1).strip()):
            bad.append(m.group(1))
    for m in re.finditer(r'!\[[^\]]*\]\(([^)]+)\)', text):
        if not _link_ok(base, m.group(1).strip()):
            bad.append(m.group(1))
    if bad:
        print(f'[link check] {md_path} BROKEN: {bad}')
    else:
        print(f'[link check] {md_path} OK')
    return bad


def build_summary(run_dir, model_dir, ctrl_dir, ctrl_model_dir, out_md):
    main = _load_summary(os.path.join(run_dir, 'case_summary.csv'))
    ctrl = _load_summary(os.path.join(ctrl_dir, 'case_summary.csv'))
    recs = _load_json_recs(os.path.join(run_dir, 'case_summary.json'))
    deep = None
    dp = os.path.join(run_dir, 'report', 'deep_check.csv')
    if os.path.exists(dp):
        deep = pd.read_csv(dp)
    meta_m = {}
    meta_c = {}
    for p, d in [(os.path.join(model_dir, 'meta.json'), meta_m),
                 (os.path.join(ctrl_model_dir, 'meta.json'), meta_c)]:
        try:
            with open(p, encoding='utf-8') as f:
                d.update(json.load(f))
        except Exception:
            pass

    L = []  # lines
    L.append('# DDPS v2 结果（112G 物理模型，BER_MLSE）\n')
    L.append('修复 v1 的 4 处实现错误（Stage-1 邻域采样死代码 / FFE 主抽头参数化错配 / '
             'Tx-FIR 探针跨插损对齐漂移 / 缺梯度门控，详见 [`docs/06`](../docs/06_DDPS_v2_Rerun.md)）'
             '后重跑。两组实验对 8 个应力环境的 Stage-2 在线调优，**真实 BER_MLSE 全程无一步'
             '劣于种子**；其中混合锚定模型（主实验）在 20 dB 插损用例把 BER 从 `5.8e-2` 降到 '
             '`3.0e-3`（约 20×），复合应力从 `7.7e-2` 降到 `5.7e-3`（约 13×）。\n')
    L.append('**评估口径**：Rx 22-tap LMS FFE（无 DFE）→ MLSE（memory=1，Burg 白化），'
             '输出为 BER_MLSE；每点 131072 符号、固定随机种子；种子 x0（Tx FFE 9-tap + '
             'Tx CTLE gDC/gDC2）两实验相同；Stage-2 只依据代理模型，真实 BER 仅记录不参与决策。\n')

    # ---- 两组实验的区别 ----
    L.append('## 两组实验：同一条测试线，只有“训练数据”不同\n')
    L.append('| | 主实验 | 对照实验 |')
    L.append('| --- | --- | --- |')
    L.append('| 目录 | [`result/ddps_v2_20260907`](ddps_v2_20260907) | '
             '[`result/ddps_v2_control`](ddps_v2_control) |')
    L.append('| 训练数据 | [`dataset/ddps_v2_dataset_20260907_190819.csv`]'
             '(../dataset/ddps_v2_dataset_20260907_190819.csv)，共 748 行：'
             'Base_IL10 邻域 320 点 + 其余 7 个环境各 60 点 + 每环境 1 个种子点（同一文件） | '
             '同一文件里只取 `env == Base_IL10` 的 321 行（320 邻域 + 1 种子） |')
    L.append('| 数据覆盖 | 8 个环境都有邻域锚点（训练域覆盖测试域） | 只在基准环境 IL10 采样 |')
    L.append('| 模型 | [`models/ddps_v2/`](../models/ddps_v2/) | '
             '[`models/ddps_v2_control/`](../models/ddps_v2_control/) |')
    L.append('| 模型算法/超参/评估 | 相同：二阶多项式 Ridge（白盒），8 用例、同种子 x0、'
             '同 131072 符号协议 | 与主实验完全相同 |')
    L.append('| 想回答的问题 | 交付用结果 | “只用基准环境训练，能不能在漂移环境里直接调优”'
             '（AGENTS.md 控制变量法） |')
    L.append('')
    L.append('两个实验的差异**只有训练数据构成**，其余完全一致，因此二者的结果差 = 混合锚点'
             '数据带来的增益。\n')

    # ---- 主表：两实验并列 ----
    L.append('## 结果对比（每行为一个用例）\n')
    L.append('| 用例（环境） | 种子 | 主实验最优 | 对照(仅基训)最优 | '
             '主Δlog10 | 对照Δlog10 | 深水复核(主, 262144 sym) |')
    L.append('| --- | --- | --- | --- | --- | --- | --- |')
    for env in ENV_CASES:
        name = env['name']
        s = main.loc[name]
        c = ctrl.loc[name]
        rec = recs.get(name, {})
        seed = _f(s['seed_ber'])
        mb = _f(s['best_ber']); cb = _f(c['best_ber'])
        mdel = _f(s['delta_lb_seed_to_best']); cdel = _f(c['delta_lb_seed_to_best'])
        drow = deep[deep['env'] == name].iloc[0] if deep is not None and len(deep) else None
        ds = (f'{_f(drow["best_ber_deep"]):.1e}' if drow is not None else '-')
        envdesc = f"IL{_f(env['il']):.0f}dB"
        if env['cd']:
            envdesc += f"+CD{int(env['cd'])}"
        if env['dgd']:
            envdesc += f"+DGD{int(env['dgd'])}ps"
        mult_m = _mult(mdel); mult_c = _mult(cdel)
        L.append(f"| {name} ({envdesc}) | `{seed:.2e}` | "
                 f"`{mb:.2e}` (×{mult_m:.1f}) | `{cb:.2e}` (×{mult_c:.1f}) | "
                 f"`{mdel:.2f}` | `{cdel:.2f}` | `{ds}` |")
    L.append('')
    L.append('读数方式：`×` 是相对种子的改善倍数；Δlog10 为负表示变好。两列都有明显改善说明'
             '“负向优化”已根治（对照实验即使用基准环境训练也不变差）；主实验在 IL20 / '
             '复合应力上比对照再优 4~10×，说明高噪声环境需要混合环境数据锚定。\n')

    # ---- 模型指标 ----
    ma = meta_m.get('model_a', {})
    if ma:
        L.append('## 代理模型指标（混合锚定训练，测试集 holdout）\n')
        L.append(f"- Model A（Tx FIR→log10 BER_MLSE，寻优方向）：R²={_f(ma.get('r2_test')):.3f}，"
                 f"Spearman={_f(ma.get('spearman_test')):.3f}")
        L.append(f"- Model B（配置→log10 BER_MLSE，安全约束）："
                 f"R²={_f(meta_m.get('model_b', {}).get('r2_test')):.3f}，"
                 f"Spearman={_f(meta_m.get('model_b', {}).get('spearman_test')):.3f}")
        by = ma.get('model_a_by_env') or meta_m.get('model_a_by_env')
        if by:
            L.append('\n各环境测试 Spearman（Model A）：')
            L.append('| 环境 | n | Spearman |')
            L.append('| --- | --- | --- |')
            for e, v in sorted(by.items(), key=lambda kv: kv[0]):
                L.append(f"| {e} | {v.get('n', '-')} | {_f(v.get('spearman_test')):.3f} |")
        L.append('')

    # ---- 图 ----
    L.append('## 图\n')
    L.append('### 收敛对比（8 用例同轴，便于横向比较）\n')
    L.append('![收敛对比](ddps_v2_20260907/report/fig_convergence_compare.png)\n')
    L.append('### 优化前后的 Tx FFE 抽头 / CTLE 设置\n')
    L.append('![抽头对比](ddps_v2_20260907/report/fig_taps_compare.png)\n')
    L.append('### seed→best 改善量汇总\n')
    L.append('![改善量](ddps_v2_20260907/report/ddps_v2_overview.png)\n')
    L.append('### 各用例节点细节（眼图/频谱/均衡电平，seed vs best）与逐级轨迹\n')
    L.append('| 用例 | 分析图（收敛+抽头+CTLE+FIR） | 节点图（眼图/频谱/均衡电平） | 逐级 trace |')
    L.append('| --- | --- | --- | --- |')
    for env in ENV_CASES:
        name = env['name']
        L.append(f"| {name} | [PNG](ddps_v2_20260907/report/ddps_v2_case_{name}_a.png) | "
                 f"[PNG](ddps_v2_20260907/report/ddps_v2_case_{name}_b.png) | "
                 f"[csv](ddps_v2_20260907/trace_{name}.csv) |")
    L.append('')

    # ---- 数据 ----
    L.append('## 数据文件\n')
    L.append('- 用例汇总：`result/ddps_v2_20260907/case_summary.csv` / `.json`；'
             '对照汇总：`result/ddps_v2_control/case_summary.csv`')
    L.append('- 训练数据：`../dataset/ddps_v2_dataset_20260907_190819.csv`（748 行，含 env/il/cd/dgd/'
             'x_0~9/ffe_tap/ctle/log10_ber_mlse/tx_fir 列）')
    L.append('- 模型与指标：`../models/ddps_v2/meta.json`、`../models/ddps_v2_control/meta.json`')
    L.append('- 高符号数复核：`result/ddps_v2_20260907/report/deep_check.csv`\n')
    L.append('## 相关文档\n')
    L.append('- [`docs/06` DDPS v2 重做报告](../docs/06_DDPS_v2_Rerun.md)：v1 根因排查与修复清单')
    L.append('- [`docs/04` DDPS 架构](../docs/04_DDPS_Optimization.md) | '
             '[`docs/03` 排坑记录](../docs/03_Troubleshooting_History.md)')
    L.append('- v1 历史数据/模型/结果（本地目录，未入库）：`archive/20260904_ddps_v1_physical_pre_v2/`')

    with open(out_md, 'w', encoding='utf-8') as f:
        f.write('\n'.join(L) + '\n')
    print(f'[summary] {out_md}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run-dir', default='result/ddps_v2_20260907')
    ap.add_argument('--model-dir', default='models/ddps_v2')
    ap.add_argument('--ctrl-dir', default='result/ddps_v2_control')
    ap.add_argument('--ctrl-model-dir', default='models/ddps_v2_control')
    a = ap.parse_args()

    rep = os.path.join(a.run_dir, 'report')
    os.makedirs(rep, exist_ok=True)
    _plot_convergence_compare(a.run_dir, os.path.join(rep, 'fig_convergence_compare.png'))
    _plot_taps_compare(a.run_dir, os.path.join(rep, 'fig_taps_compare.png'))
    _plot_overview_english(a.run_dir, os.path.join(rep, 'ddps_v2_overview.png'))
    build_summary(a.run_dir, a.model_dir, a.ctrl_dir, a.ctrl_model_dir,
                  'result/SUMMARY.md')
    check_links('result/SUMMARY.md')


if __name__ == '__main__':
    main()
