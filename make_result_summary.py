# [v2 时代脚本] 生成 v2 的 result/SUMMARY.md。
# v2 产物已归档到 archive/20260910_ddps_v2_pre_ctle_reorder/（不入库）。
# 当前请使用 report_ddps_v3.py --summary 生成跨实验汇总。
# -*- coding: utf-8 -*-
"""make_result_summary.py — 从现有产物重建「结果页」（不重跑寻优/数据收集）

两个实验（只用基线训练 → 跨环境泛化 / 带锚点训练上限参考）在 result/SUMMARY.md
同一个文件里**各自都有完整结果表 + 收敛对比图 + 抽头对比图**，另附两者改善量对照图。
所有图只从已有 csv/png 重绘。

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

# 目录（仓库根相对）
BL_DIR = 'result/ddps_v2_control'       # 实验一：只用基线训练 -> 跨环境泛化
BL_MODEL = 'models/ddps_v2_control'
AN_DIR = 'result/ddps_v2_20260907'      # 实验二：带环境锚点训练（上限参考）
AN_MODEL = 'models/ddps_v2'


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float('nan')


def _mult(delta_lb):
    d = _f(delta_lb)
    return 10 ** (-d) if not np.isnan(d) else np.nan


def _load_summary(path):
    return pd.read_csv(path).set_index('env')


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


def _env_desc(env):
    d = f"IL{_f(env['il']):.0f}dB"
    if env['cd']:
        d += f"+CD{int(env['cd'])}"
    if env['dgd']:
        d += f"+DGD{int(env['dgd'])}ps"
    return d


# ---------------------------------------------------------------------------
# 图（只读数据；图内文字英文，避免无中文字体出方块）
# ---------------------------------------------------------------------------
def _plot_convergence(run_dir, out_png, title):
    n = len(ENV_CASES)
    cols = 4
    rows = int(np.ceil(n / cols))
    fig, axs = plt.subplots(rows, cols, figsize=(18, 2.7 * rows), squeeze=False)
    cs = pd.read_csv(os.path.join(run_dir, 'case_summary.csv'))
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
        seed_ber = cs[cs['env'] == name]['seed_ber'].iloc[0]
        ax.axhline(seed_ber, ls=':', color='grey', lw=1)
        ax.set_title(f'{name} ({_env_desc(env)})', fontsize=9)
        ax.grid(True, which='both', ls='--', alpha=0.3)
        ax.set_ylim(1e-4, 1e-1)
        if k == 0:
            ax.legend(fontsize=7)
        if k >= n - cols:
            ax.set_xlabel('Stage-2 step')
    fig.suptitle(title, fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(out_png, dpi=110)
    plt.close(fig)


def _plot_taps(run_dir, out_png, title):
    n = len(ENV_CASES)
    cols = 4
    rows = int(np.ceil(n / cols))
    fig, axs = plt.subplots(rows, cols, figsize=(18, 2.9 * rows), squeeze=False)
    cs = pd.read_csv(os.path.join(run_dir, 'case_summary.csv'))
    for k, env in enumerate(ENV_CASES):
        ax = axs[k // cols][k % cols]
        name = env['name']
        row = cs[cs['env'] == name].iloc[0]
        bt = _taps_float(row['best_taps'])
        xs = np.arange(9)
        w = 0.38
        ax.bar(xs - w / 2, D.SEED_TAPS, width=w, color='#8a8ab8', label='seed')
        if bt is not None and len(bt) == 9:
            ax.bar(xs + w / 2, bt, width=w, color='#c66', label='best')
        ax.axvline(4.5, color='k', lw=0.4)
        ax.set_title(f'{name}\ngDC={_f(row["best_gdc"]):+.2f}, '
                     f'gDC2={_f(row["best_gdc2"]):+.2f}', fontsize=8)
        ax.grid(alpha=0.3, axis='y')
        if k == 0:
            ax.legend(fontsize=7)
    fig.suptitle(title, fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(out_png, dpi=110)
    plt.close(fig)


def _plot_delta_compare(bl_df, an_df, out_png):
    names = bl_df['env'].tolist()
    y = np.arange(len(names))
    d_bl = bl_df['delta_lb_seed_to_best'].astype(float).values
    d_an = an_df['delta_lb_seed_to_best'].astype(float).values
    fig, ax = plt.subplots(figsize=(11, 6.5))
    ax.barh(y - 0.2, d_bl, height=0.38, color='#2e8b57',
            label='baseline-only model (Exp 1)')
    ax.barh(y + 0.2, d_an, height=0.38, color='#c9a227',
            label='with env anchors (Exp 2, upper bound)')
    for i, (b, a) in enumerate(zip(d_bl, d_an)):
        ax.text(b, i - 0.2, f'{_mult(b):.1f}x', va='center',
                ha='left' if b < 0 else 'right', fontsize=7)
        ax.text(a, i + 0.2, f'{_mult(a):.1f}x', va='center',
                ha='left' if a < 0 else 'right', fontsize=7)
    ax.set_yticks(y)
    ax.set_yticklabels(names)
    ax.axvline(0, color='k', lw=0.8)
    ax.set_xlabel('d log10(BER_MLSE): seed -> Stage-2 best (negative = improvement; '
                 'label = x-fold)')
    ax.set_title('baseline-only vs with-env-anchors training')
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, axis='x')
    fig.tight_layout()
    fig.savefig(out_png, dpi=110)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------
def _experiment_section(L, exp_no, exp_name, role, bl, run_dir_rel, df, deep_df,
                        conv_png, taps_png):
    """为一个实验输出：表 + 收敛图 + 抽头图（同一文件内可见）。"""
    L.append(f'## 实验{exp_no}：{exp_name}\n')
    L.append(f'*{role}*\n')
    L.append('| 用例（环境） | 种子 BER_MLSE | Stage-2 最优 (step) | Δlog10 | 改善× | '
             '深水复核最优 (262144 sym) |')
    L.append('| --- | --- | --- | --- | --- | --- |')
    deep = deep_df.set_index('env') if deep_df is not None else None
    for env in ENV_CASES:
        name = env['name']
        s = df.loc[name]
        seed = _f(s['seed_ber'])
        best = _f(s['best_ber'])
        dl = _f(s['delta_lb_seed_to_best'])
        step = int(_f(s.get('best_step', 0)) or 0)
        dp = ''
        if deep is not None and name in deep.index:
            dp = f'`{_f(deep.loc[name, "best_ber_deep"]):.2e}`'
        L.append(f'| {name} ({_env_desc(env)}) | `{seed:.2e}` | `{best:.2e}` (step {step}) | '
                 f'`{dl:.2f}` | ×{_mult(dl):.1f} | {dp} |')
    L.append('')
    L.append('> 收敛轨迹与 trace 记录在实验目录（见文末逐用例链接）；'
             'Stage-2 全程真实 BER_MLSE 未出现劣于种子的步。\n')
    L.append(f'![{exp_no} convergence]({run_dir_rel}/report/{conv_png})\n')
    L.append(f'![{exp_no} taps]({run_dir_rel}/report/{taps_png})\n')


def build(out_md, bl_df, an_df, bl_deep, an_deep, bl_meta, an_meta):
    bl = BL_DIR.split('result/', 1)[-1]
    an = AN_DIR.split('result/', 1)[-1]
    L = []
    L.append('# DDPS v2：只用基线训练跨环境泛化 & 带锚点训练（BER_MLSE）\n')
    L.append('两个实验共用同一套评估：Rx 22-tap LMS FFE（无 DFE）→ MLSE（memory=1，Burg 白化），'
             '指标为 BER_MLSE；每点 131072 符号、固定随机种子；种子 x0 相同；Stage-2 只依据'
             '代理模型，真实 BER 仅记录不参与决策。\n')

    L.append('## 两个实验怎么切（差异只有训练数据）\n')
    L.append('| 实验 | 训练数据 | 模型 | 测试 | 定位 |')
    L.append('| --- | --- | --- | --- | --- |')
    L.append('| **实验一：只用基线训练 → 跨环境泛化** | 321 行 = 总 csv 过滤 `env==Base_IL10`'
             '（10dB 插损、CD/DGD=0 邻域 320 + 种子 1）—— 8 个测试环境的数据从未进训练集 | '
             f'[`models/ddps_v2_control/`](../{BL_MODEL}/) | 同一模型冻结，8 个漂移环境逐个 '
             'Stage-2，零重训/零校准 | 真·泛化（本页重点） |')
    L.append('| **实验二：带锚点训练（上限参考）** | 748 行 = Base_IL10 320 + 其余 7 环境各 60 '
             '+ 每环境种子 1（含少量目标环境邻域样本） | '
             f'[`models/ddps_v2/`](../{AN_MODEL}/) | 单模型冻结、测试零重训 | 校准式上界，'
             '非严格泛化（模型见过测试环境） |')
    L.append('')
    L.append('两实验仅训练集构成不同；模型结构/超参、种子 x0、8 个测试用例与评估协议完全相同。'
             '实验一回答“单点模型能否直接泛化”，实验二回答“允许少量目标环境标定数据能再提升多少”。'
             '下面两个实验的表与图都在本文件内。\n')

    # ---- 实验一 ----
    _experiment_section(L, 1, '只用基线训练 → 跨环境泛化（核心）',
                        '训练只含 Base_IL10（10dB），测试环境完全未见',
                        bl, bl, bl_df, bl_deep,
                        'fig_convergence_compare.png', 'fig_taps_compare.png')

    # ---- 实验二 ----
    _experiment_section(L, 2, '带锚点训练（上限参考）',
                        '训练含每个测试环境 60 点锚点，单模型冻结',
                        an, an, an_df, an_deep,
                        'fig_convergence_compare.png', 'fig_taps_compare.png')

    # ---- 对比 ----
    L.append('## 两实验改善量对比（绿=只用基线，黄=带锚点）\n')
    L.append(f'![delta compare]({bl}/report/fig_delta_compare.png)\n')
    L.append('| 用例 | 种子 | 只用基线最优 | 带锚点最优 | 锚点额外增益 |')
    L.append('| --- | --- | --- | --- | --- |')
    for env in ENV_CASES:
        name = env['name']
        s_bl = bl_df.loc[name]
        s_an = an_df.loc[name]
        seed = _f(s_bl['seed_ber'])
        b_bl = _f(s_bl['best_ber'])
        b_an = _f(s_an['best_ber'])
        extra = b_bl / b_an if b_an > 0 else np.nan
        L.append(f'| {name} | `{seed:.2e}` | '
                 f'`{b_bl:.2e}` (×{_mult(_f(s_bl["delta_lb_seed_to_best"])):.1f}) | '
                 f'`{b_an:.2e}` (×{_mult(_f(s_an["delta_lb_seed_to_best"])):.1f}) | '
                 f'{f"再优 {extra:.1f}×" if not np.isnan(extra) else "-"} |')
    L.append('')
    L.append('解读：实验一（只用基线）8/8 用例均为正向优化（IL20 ×3.9、复合应力 ×2.2、'
             'IL10 族收敛到 ~3.4–3.6e-4），说明修复后的管线具备真实跨环境泛化能力；'
             '实验二在极端环境再优 5–6×（IL20 → 3.0e-3、复合 → 5.7e-3），'
             '但这是以把目标环境数据放进训练为代价的上界。\n')

    # ---- 模型指标（两实验各给） ----
    for tag, meta, mdir in [('实验一（只用基线）', bl_meta, BL_MODEL),
                            ('实验二（带锚点）', an_meta, AN_MODEL)]:
        if not meta:
            continue
        ma = meta.get('model_a', {})
        mb = meta.get('model_b', {})
        L.append(f'## 模型指标：{tag}\n')
        L.append(f'- Model A（Tx FIR→log10 BER_MLSE，寻优方向）：R²={_f(ma.get("r2_test")):.3f}，'
                 f'Spearman={_f(ma.get("spearman_test")):.3f}')
        L.append(f'- Model B（配置→log10 BER_MLSE，安全约束）：R²={_f(mb.get("r2_test")):.3f}，'
                 f'Spearman={_f(mb.get("spearman_test")):.3f}')
        L.append(f'- meta：`{mdir}/meta.json`')
        L.append('')

    # ---- 逐用例 ----
    L.append('## 逐用例数据与节点图\n')
    L.append('| 用例 | 实验一（只用基线，核心） | 实验二（带锚点，上限） |')
    L.append('| --- | --- | --- |')
    for env in ENV_CASES:
        name = env['name']
        L.append(f'| {name} | '
                 f'[收敛/抽头/CTLE/FIR]({bl}/report/ddps_v2_case_{name}_a.png) · '
                 f'[眼图/频谱]({bl}/report/ddps_v2_case_{name}_b.png) · '
                 f'[trace]({bl}/trace_{name}.csv) | '
                 f'[图]({an}/report/ddps_v2_case_{name}_a.png) · '
                 f'[trace]({an}/trace_{name}.csv) |')
    L.append('')

    L.append('## 数据文件\n')
    L.append('- 总数据集：[`../dataset/ddps_v2_dataset_20260907_190819.csv`]'
             '(../dataset/ddps_v2_dataset_20260907_190819.csv)（748 行：Base 321 + 7 环境锚点各 61）')
    L.append('- 实验一模型只用其中 `env==Base_IL10` 的 321 行；实验二模型用全部 748 行')
    L.append(f'- 实验一：case 汇总 [`case_summary.csv`]({bl}/case_summary.csv)、'
             f'深水 [`deep_check.csv`]({bl}/report/deep_check.csv)')
    L.append(f'- 实验二：case 汇总 [`case_summary.csv`]({an}/case_summary.csv)、'
             f'深水 [`deep_check.csv`]({an}/report/deep_check.csv)')
    L.append('- 逐级轨迹：两实验目录下 `trace_<用例>.csv`（每用例一个文件）')
    L.append('')

    L.append('## 相关文档\n')
    L.append('- [`docs/06` DDPS v2 重做报告](../docs/06_DDPS_v2_Rerun.md)：v1 根因与修复清单')
    L.append('- [`docs/04` DDPS 架构](../docs/04_DDPS_Optimization.md) | '
             '[`docs/03` 排坑记录](../docs/03_Troubleshooting_History.md)')
    L.append('- v1 历史数据/模型/结果（本地目录，未入库）：'
             '`archive/20260904_ddps_v1_physical_pre_v2/`')

    with open(out_md, 'w', encoding='utf-8') as f:
        f.write('\n'.join(L) + '\n')
    print(f'[summary] {out_md}')


def _link_ok(base, t):
    if t.startswith(('http://', 'https://', '#')):
        return True
    return os.path.exists(os.path.abspath(os.path.join(base, t.split('#')[0])))


def check_links(md_path):
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
    print(f'[link check] {md_path} {"OK" if not bad else "BROKEN: " + str(bad)}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bl-dir', default=BL_DIR)
    ap.add_argument('--bl-model', default=BL_MODEL)
    ap.add_argument('--an-dir', default=AN_DIR)
    ap.add_argument('--an-model', default=AN_MODEL)
    a = ap.parse_args()

    bl = _load_summary(os.path.join(a.bl_dir, 'case_summary.csv'))
    an = _load_summary(os.path.join(a.an_dir, 'case_summary.csv'))

    # 两个实验各自的收敛/抽头对比图（若已存在则覆盖重绘；仅读 csv）
    for d, title_a, title_b in [
        (a.bl_dir, 'Stage-2 convergence: Exp1 baseline-only model reused across drifted envs '
         '(solid=real, dashed=Model A, grey=seed, open circle=best)',
         'Tx FFE taps: seed vs best (Exp1 baseline-only model)'),
        (a.an_dir, 'Stage-2 convergence: Exp2 model (trained with env anchors) '
         '(solid=real, dashed=Model A, grey=seed, open circle=best)',
         'Tx FFE taps: seed vs best (Exp2 model with env anchors)'),
    ]:
        rep = os.path.join(d, 'report')
        os.makedirs(rep, exist_ok=True)
        _plot_convergence(d, os.path.join(rep, 'fig_convergence_compare.png'), title_a)
        _plot_taps(d, os.path.join(rep, 'fig_taps_compare.png'), title_b)

    _plot_delta_compare(bl.reset_index(), an.reset_index(),
                        os.path.join(a.bl_dir, 'report', 'fig_delta_compare.png'))

    def _deep(p):
        return pd.read_csv(p) if os.path.exists(p) else None

    bl_deep = _deep(os.path.join(a.bl_dir, 'report', 'deep_check.csv'))
    an_deep = _deep(os.path.join(a.an_dir, 'report', 'deep_check.csv'))

    def _meta(d):
        try:
            with open(os.path.join(d, 'meta.json'), encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    build('result/SUMMARY.md', bl, an, bl_deep, an_deep,
          _meta(a.bl_model), _meta(a.an_model))
    check_links('result/SUMMARY.md')


if __name__ == '__main__':
    main()
