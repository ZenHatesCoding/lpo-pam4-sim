# -*- coding: utf-8 -*-
"""make_result_summary.py — 从现有产物重建「结果页」（不重跑寻优/数据收集）

重点：把【只用基线(Base_IL10)训练 → 跨环境泛化】作为核心结果放在前面；
【带环境锚点训练】作为上限参考/校准式对比放在其后。所有图从已有 csv/png 重绘。

产出：
  result/SUMMARY.md
  result/ddps_v2_control/report/fig_convergence_compare.png   （基线泛化收敛对比）
  result/ddps_v2_control/report/fig_taps_compare.png          （基线泛化抽头对比）
  result/ddps_v2_control/report/fig_delta_compare.png         （基线 vs 锚点 改善量对照）

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
BL_DIR = 'result/ddps_v2_control'       # 核心：只用基线训练 -> 跨环境泛化
BL_MODEL = 'models/ddps_v2_control'
AN_DIR = 'result/ddps_v2_20260907'      # 参考：带环境锚点训练（上限/校准式）
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


# ---------------------------------------------------------------------------
# 图（只读数据；图内文字用英文，避免无中文字体出方块）
# ---------------------------------------------------------------------------
def _env_desc(env):
    d = f"IL{_f(env['il']):.0f}dB"
    if env['cd']:
        d += f"+CD{int(env['cd'])}"
    if env['dgd']:
        d += f"+DGD{int(env['dgd'])}ps"
    return d


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
            label='baseline-only model (core result)')
    ax.barh(y + 0.2, d_an, height=0.38, color='#c9a227',
            label='with env anchors (upper bound)')
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
def build(out_md, bl_df, an_df, bl_deep, an_deep, bl_meta, an_meta):
    # SUMMARY.md 位于 result/ 下：链接一律去掉 'result/' 前缀
    bl = BL_DIR.split('result/', 1)[-1]
    an = AN_DIR.split('result/', 1)[-1]
    L = []
    L.append('# DDPS v2 结果：只用 10dB 基线训练，冻结模型跨环境泛化（BER_MLSE）\n')
    L.append('核心实验：只采集 **Base_IL10 邻域 321 点**（320 采样 + 1 种子；10dB 插损，'
             'CD/DGD=0）训练一套白盒代理模型并**冻结**；把同一个模型直接用于 8 个漂移环境'
             '（IL 14/20 dB、CD 15/28 ps/nm、DGD 2/5 ps、IL20+CD15+DGD5 复合）的 Stage-2 '
             '在线调优。测试全程**没有任何一步重新采样或重训**，模型从未见过这些环境的数据。'
             '结果：8 个环境真实 BER_MLSE **全程无一步劣于种子**（对比 v1 同场景是负向发散），'
             '其中 20 dB 插损 `5.8e-2 → 1.5e-2`（约 ×4），复合应力 `7.7e-2 → 3.5e-2`（约 ×2），'
             '其余 IL10 族环境收敛到约 `3.4–3.6e-4`。\n')
    L.append('**评估口径**：Rx 22-tap LMS FFE（无 DFE）→ MLSE（memory=1，Burg 白化），'
             '输出为 BER_MLSE；每点 131072 符号、固定随机种子；Stage-2 只依据代理模型，'
             '真实 BER 仅记录、不参与方向决策。\n')

    L.append('## 训练 / 测试分工（测试环境从未进过训练集）\n')
    L.append('| 实验 | 目录 | 训练数据 | 模型 | 测试 | 角色 |')
    L.append('| --- | --- | --- | --- | --- | --- |')
    L.append(f'| 只用基线训练 → 跨环境泛化 | [`result/ddps_v2_control`]({bl}) | '
             '321 行 = Base_IL10 邻域 320 + 种子 1（只含 IL10、CD0、DGD0；'
             '来自总 csv 过滤 `env==Base_IL10`） | '
             f'[`models/ddps_v2_control/`](../{BL_MODEL}/) | 同一模型冻结，8 个漂移环境 '
             '逐个 Stage-2，零重训/零校准 | **本页主角（真·泛化）** |')
    L.append(f'| 带环境锚点训练（上限参考） | [`result/ddps_v2_20260907`]({an}) | '
             '748 行 = Base_IL10 320 + 其余 7 环境各 60 + 每环境种子 1'
             '（把少量目标环境邻域样本放进训练集） | '
             f'[`models/ddps_v2/`](../{AN_MODEL}/) | 同样单模型冻结、测试零重训 | '
             '参考/校准式上界，**非严格泛化**（测试环境已被建模见过） |')
    L.append('')
    L.append('两实验差别只有训练集构成；模型结构/超参、种子 x0、8 个测试用例、评估代码与'
             ' 131072 符号协议完全相同。下表与图以“只用基线训练”为主。\n')

    L.append('## 核心结果：只用基线训练 → 跨环境泛化\n')
    L.append('| 用例（环境） | 种子 BER_MLSE | Stage-2 最优 (step) | Δlog10 | 改善× | '
             '深水复核最优 (262144 sym) |')
    L.append('| --- | --- | --- | --- | --- | --- |')
    deep_bl = bl_deep.set_index('env') if bl_deep is not None else None
    for env in ENV_CASES:
        name = env['name']
        s = bl_df.loc[name]
        seed = _f(s['seed_ber'])
        best = _f(s['best_ber'])
        dl = _f(s['delta_lb_seed_to_best'])
        step = int(_f(s.get('best_step', 0)) or 0)
        dp = ''
        if deep_bl is not None and name in deep_bl.index:
            dp = f'`{_f(deep_bl.loc[name, "best_ber_deep"]):.2e}`'
        L.append(f'| {name} ({_env_desc(env)}) | `{seed:.2e}` | `{best:.2e}` (step {step}) | '
                 f'`{dl:.2f}` | ×{_mult(dl):.1f} | {dp} |')
    L.append('')
    L.append('每行 Stage-2 全程真实 BER_MLSE 都记录在 trace csv 中，**任意一步未劣于种子**。'
             'IL10 族环境收敛到同一 ~3.4–3.6e-4 平台；高插损与复合环境（模型纯外推）改善 '
             '约 2–4×，方向仍正确、幅度受外推限制。\n')

    L.append('## 对比：若把少量目标环境样本也放进训练（上限参考）\n')
    L.append('| 用例 | 种子 | 只用基线（本页核心） | 带锚点训练 | 锚点带来的额外增益 |')
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
    L.append('解读：锚点变体仍是单模型、测试零重训，只是把少量目标环境邻域样本放进训练集，'
             '因而不是严格泛化结论，只回答“若允许少量目标环境标定数据，极端环境还能压多少”：'
             'IL20 从 `1.5e-2 → 3.0e-3`，复合应力从 `3.5e-2 → 5.7e-3`。方法学结论以本页核心'
             '实验（只用基线训练）为准。\n')

    if bl_meta:
        ma = bl_meta.get('model_a', {})
        L.append('## 冻结模型指标（基线训练，测试集 holdout）\n')
        L.append(f"- Model A（Tx FIR → log10 BER_MLSE，寻优方向）："
                 f"R²={_f(ma.get('r2_test')):.3f}，"
                 f"Spearman={_f(ma.get('spearman_test')):.3f}")
        L.append(f"- Model B（配置 → log10 BER_MLSE，安全约束）："
                 f"R²={_f(bl_meta.get('model_b', {}).get('r2_test')):.3f}，"
                 f"Spearman={_f(bl_meta.get('model_b', {}).get('spearman_test')):.3f}")
        L.append('')

    L.append('## 图\n')
    L.append('### 基线泛化收敛（8 用例同轴对比）\n')
    L.append(f'![convergence]({bl}/report/fig_convergence_compare.png)\n')
    L.append('### 基线泛化：优化前后 Tx FFE 抽头 / CTLE\n')
    L.append(f'![taps]({bl}/report/fig_taps_compare.png)\n')
    L.append('### 基线 vs 带锚点：改善量对照（绿=只用基线，核心）\n')
    L.append(f'![delta compare]({bl}/report/fig_delta_compare.png)\n')
    L.append('### 逐用例：数据与节点图\n')
    L.append('| 用例 | 基线模型（核心） | 带锚点模型（参考） |')
    L.append('| --- | --- | --- |')
    for env in ENV_CASES:
        name = env['name']
        L.append(f'| {name} | '
                 f'[收敛/抽头/CTLE/FIR 图]({bl}/report/ddps_v2_case_{name}_a.png) · '
                 f'[眼图/频谱]({bl}/report/ddps_v2_case_{name}_b.png) · '
                 f'[trace]({bl}/trace_{name}.csv) | '
                 f'[图]({an}/report/ddps_v2_case_{name}_a.png) · '
                 f'[trace]({an}/trace_{name}.csv) |')
    L.append('')

    L.append('## 数据文件\n')
    L.append('- 总数据集：[`../dataset/ddps_v2_dataset_20260907_190819.csv`]'
             '(../dataset/ddps_v2_dataset_20260907_190819.csv)（748 行：Base 321 + '
             '7 环境锚点各 61）')
    L.append('- 基线模型只用其中 `env==Base_IL10` 的 321 行；锚点模型用全部 748 行')
    L.append(f'- 基线实验汇总：[`case_summary.csv`]({bl}/case_summary.csv)，'
             f'逐级轨迹 `trace_<用例>.csv`（{bl}/ 下，每用例一个文件），'
             f'深水复核 [`deep_check.csv`]({bl}/report/deep_check.csv)')
    L.append(f'- 锚点实验汇总：[`case_summary.csv`]({an}/case_summary.csv)，'
             f'深水复核 [`deep_check.csv`]({an}/report/deep_check.csv)')
    L.append('')

    L.append('## 相关文档\n')
    L.append('- [`docs/06` DDPS v2 重做报告](../docs/06_DDPS_v2_Rerun.md)：v1 根因、修复清单'
             '与两组实验的方法学说明')
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

    bl_rep = os.path.join(a.bl_dir, 'report')
    os.makedirs(bl_rep, exist_ok=True)
    _plot_convergence(
        a.bl_dir, os.path.join(bl_rep, 'fig_convergence_compare.png'),
        'Stage-2 convergence: baseline-only model reused across drifted envs '
        '(solid = real BER_MLSE, dashed = Model A, grey = seed, open circle = best)')
    _plot_taps(a.bl_dir, os.path.join(bl_rep, 'fig_taps_compare.png'),
               'Tx FFE taps: seed vs best (baseline-only model)')
    _plot_delta_compare(bl.reset_index(), an.reset_index(),
                        os.path.join(bl_rep, 'fig_delta_compare.png'))

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
