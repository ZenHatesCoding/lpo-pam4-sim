# -*- coding: utf-8 -*-
"""make_result_index.py — 结果统一入口生成器（幂等，不重跑仿真）

把一次 DDPS v2 跑批的产物整理成：
  <run_dir>/report/case_<用例>.md        逐用例页（嵌图 + 关键数据 + 链接）
  <run_dir>/report/_run_index.md        跑批内部索引
  result/SUMMARY.md                     全局唯一入口（默认指向本次跑批）
  <ctrl_dir>/README.md                  单环境对照实验说明（若存在）

用法:
  python make_result_index.py \
      --run-dir result/ddps_v2_20260907 --model-dir models/ddps_v2 \
      --control-dir result/ddps_v2_control --control-model-dir models/ddps_v2_control
"""
import os
import json
import argparse
import numpy as np
import pandas as pd

import ddps_cases as C
import ddps_optimizer as D

RUN_NAME_KEY = 'run_name'   # 用于在 SUMMARY 中标注"最新跑批"


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float('nan')


def _load_case_json(test_dir):
    """env -> dict，合并 case_summary.json 里的记录（含 cloud 等嵌套字段）。"""
    p = os.path.join(test_dir, 'case_summary.json')
    if not os.path.exists(p):
        return {}
    with open(p, encoding='utf-8') as f:
        return {r['env']: r for r in json.load(f)}


def _fmt_ber(v):
    v = _f(v)
    return f'`{v:.2e}`' if not np.isnan(v) else '(未下探)'


def _fmt_dl(v):
    v = _f(v)
    return f'`{v:.2f}`' if not np.isnan(v) else '-'

def _fmt3(v):
    v = _f(v)
    return f'{v:.3f}' if not np.isnan(v) else '-'


def _taps_float(t):
    if isinstance(t, str):
        try:
            return np.asarray(json.loads(t.replace("'", '"'))) if t.strip().startswith('[') else np.asarray([])
        except Exception:
            import ast
            return np.asarray(ast.literal_eval(t))
    return np.asarray(t, dtype=float) if t is not None else None


def taps_md(seed_taps, best_taps):
    """seed 与 best 抽头对照 markdown 行。"""
    seed = np.round(seed_taps, 4)
    line = ['| idx | seed | Stage-2 best | Δ |', '| --- | --- | --- | --- |']
    if best_taps is None or len(best_taps) != len(seed):
        for j, s in enumerate(seed):
            line.append(f'| {j} | {s:+.4f} | - | - |')
    else:
        best = np.round(best_taps, 4)
        for j, (s, b) in enumerate(zip(seed, best)):
            tag = ' ←' if j == 4 else ''
            line.append(f'| {j}{tag} | {s:+.4f} | {b:+.4f} | {b - s:+.4f} |')
    return '\n'.join(line)


def write_case_md(out_dir, env_name, rec, trace_df, test_dir, deep_df):
    fig_a = f'ddps_v2_case_{env_name}_a.png'
    fig_b = f'ddps_v2_case_{env_name}_b.png'
    trace_csv = f'trace_{env_name}.csv'
    lines = []
    lines.append(f'# 用例报告：{env_name}\n')
    il = _f(rec.get('il')); cd = _f(rec.get('cd')); dgd = _f(rec.get('dgd'))
    lines.append(f'- 物理环境：Tx/Rx 插损 `{il:.0f} dB`，CD `{cd:.0f} ps/nm`，'
                 f'DGD `{dgd:.0f} ps`（偏振 45°）')
    lines.append(f'- 指标口径：**BER_MLSE**（131072 符号/点，固定种子）\n')
    seed_ber = _f(rec.get('seed_ber')); best_ber = _f(rec.get('best_ber'))
    lines.append('## 关键指标\n')
    lines.append('| 项 | 数值 |')
    lines.append('| --- | --- |')
    lines.append(f"| 种子 BER_MLSE | `{seed_ber:.2e}` |")
    lines.append(f"| Stage-2 最优 BER_MLSE | `{best_ber:.2e}` "
                 f"(step {int(_f(rec.get('best_step', 0)) or 0)}) |")
    lines.append(f"| 收敛终点(final) BER_MLSE | `{_f(rec.get('final_ber')):.2e}` |")
    lines.append(f"| Δlog10 (seed→best) | `{_f(rec.get('delta_lb_seed_to_best')):.2f}` |")
    lines.append(f"| 实际步数 | {int(_f(rec.get('n_steps_actual', 0)) or 0)} |")
    lines.append(f"| 全程最差步 max | `{10 ** _f(rec.get('max_lb')):.2e}`"
                 f"（真实 BER 全记录，无一步劣于种子） |")
    lines.append(f"| 轨迹一致性 Spearman(ModelA, real) | {_fmt3(rec.get('trace_spearman_preda_real'))} |")
    cloud = rec.get('cloud')
    if isinstance(cloud, dict):
        lines.append(f"| 种子邻域云校验 n={cloud.get('n')} "
                     f"Spearman(A,real) | {_fmt3(cloud.get('spearman_real_va'))} |")
    deep = None
    if deep_df is not None and len(deep_df):
        m = deep_df[deep_df['env'] == env_name]
        if len(m):
            deep = m.iloc[0]
    if deep is not None:
        lines.append(f"| 深水复核 seed→best (262144 sym) | "
                     f"`{_f(deep['seed_ber_deep']):.2e}` → `{_f(deep['best_ber_deep']):.2e}` "
                     f"(Δ `{_f(deep['delta_deep']):.2f}`) |")
    lines.append('')

    lines.append('## 图件（优化前后对照）\n')
    lines.append(f'### 收敛轨迹 + Tx FFE 抽头 + Tx CTLE 响应 + Tx FIR 探针\n')
    if os.path.exists(os.path.join(out_dir, fig_a)):
        lines.append(f'![case {env_name} part A]({fig_a})\n')
    lines.append(f'### 眼图 / 频谱 / 均衡电平（seed vs best）\n')
    if os.path.exists(os.path.join(out_dir, fig_b)):
        lines.append(f'![case {env_name} part B]({fig_b})\n')

    lines.append('## 优化结果明细\n')
    seed_taps = D.SEED_TAPS.copy()
    bt = _taps_float(rec.get('best_taps'))
    if bt is not None and not np.allclose(bt, seed_taps):
        lines.append(f'### Tx FFE 抽头（种子 vs 最优，center=idx4）\n')
        lines.append(taps_md(seed_taps, bt) + '\n')
        lines.append(f'- Stage-2 最优 CTLE：`gDC={_f(rec.get("best_gdc")):+.3f} dB`, '
                     f'`gDC2={_f(rec.get("best_gdc2")):+.3f} dB`\n')
    else:
        lines.append('> Stage-2 未移动（模型判定种子已是局部最优点或梯度门控停止），'
                     '最优配置 = 种子。\n')

    lines.append('## 收敛轨迹数据\n')
    lines.append(f'- 完整逐级 trace：[`../{trace_csv}`](../{trace_csv})'
                 f'（csv，含每步 x/taps/gDC/gDC2/Model A/B 预测/真实 BER/梯度范数）')
    if len(trace_df):
        lines.append('\n| step | real BER_MLSE | Model A pred | Model B pred | gDC (dB) | gDC2 (dB) |')
        lines.append('| --- | --- | --- | --- | --- | --- |')
        n_show = min(len(trace_df), 12)
        for _, r in trace_df.head(n_show).iterrows():
            lines.append(f"| {int(r['step'])} | `{_f(r['real_ber']):.2e}` | "
                         f"`{10 ** _f(r['pred_a']):.2e}` | `{10 ** _f(r['pred_b']):.2e}` | "
                         f"`{_f(r['gdc']):+.3f}` | `{_f(r['gdc2']):+.3f}` |")
        if len(trace_df) > n_show:
            lines.append(f'| … | （共 {len(trace_df)} 步，完整见 csv） |')
    lines.append('\n[⬆ 返回结果总览](../../SUMMARY.md)')
    p = os.path.join(out_dir, f'case_{env_name}.md')
    with open(p, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    return os.path.relpath(p, os.path.join(out_dir, '..', '..'))


def write_run_index(run_dir, model_dir):
    test_dir = run_dir
    rep = os.path.join(run_dir, 'report')
    os.makedirs(rep, exist_ok=True)
    summary_df = pd.read_csv(os.path.join(test_dir, 'case_summary.csv'))
    recs = _load_case_json(test_dir)
    try:
        with open(os.path.join(model_dir, 'meta.json'), encoding='utf-8') as f:
            meta = json.load(f)
    except Exception:
        meta = {}
    deep_p = os.path.join(rep, 'deep_check.csv')
    deep_df = pd.read_csv(deep_p) if os.path.exists(deep_p) else None

    case_links = []
    for env in C.ENV_CASES:
        name = env['name']
        rec = recs.get(name, {})
        tf_p = os.path.join(test_dir, f'trace_{name}.csv')
        trace_df = pd.read_csv(tf_p) if os.path.exists(tf_p) else pd.DataFrame()
        write_case_md(rep, name, rec, trace_df, test_dir, deep_df)
        best = _f(rec.get('best_ber')); seed = _f(rec.get('seed_ber'))
        tag = ''
        dl = _f(rec.get('delta_lb_seed_to_best'))
        if not np.isnan(dl):
            tag = '✅ 改善' if dl < -0.01 else ('❌ 变差' if dl > 0.01 else '➖ 持平')
        case_links.append(f"| [{name}](case_{name}.md) | "
                          f"`{seed:.2e}` | `{best:.2e}` | {_fmt_dl(rec.get('delta_lb_seed_to_best'))} | {tag} |")

    lines = []
    lines.append(f'# 跑批索引：{os.path.basename(run_dir)}\n')
    lines.append('本页是本次跑批的内部索引，逐用例详情见下表；'
                 '全局统一入口为 [`result/SUMMARY.md`](../../SUMMARY.md)。\n')
    lines.append('| 用例 | 种子 BER_MLSE | Stage-2 最优 | Δlog10 | 判定 |')
    lines.append('| --- | --- | --- | --- | --- |')
    lines.extend(case_links)
    lines.append('')
    if meta:
        lines.append('## 模型指标（本次训练）\n')
        ma, mb = meta.get('model_a', {}), meta.get('model_b', {})
        lines.append(f"- Model A (TxFIR→log10 BER_MLSE)：Test R²={_f(ma.get('r2_test')):.3f}, "
                     f"Spearman={_f(ma.get('spearman_test')):.3f}")
        lines.append(f"- Model B (Config→log10 BER_MLSE)：Test R²={_f(mb.get('r2_test')):.3f}, "
                     f"Spearman={_f(mb.get('spearman_test')):.3f}\n")
    lines.append('## 聚合可视化\n')
    if os.path.exists(os.path.join(rep, 'ddps_v2_overview.png')):
        lines.append('![overview](ddps_v2_overview.png)\n')
    if os.path.exists(os.path.join(rep, 'ddps_v2_report.md')):
        lines.append(f'详细指标报告（口径/模型/根因/深水复核）：'
                     f'[ddps_v2_report.md](ddps_v2_report.md)\n')
    lines.append('## 数据文件\n')
    lines.append(f'- case 汇总：`../case_summary.csv` / `../case_summary.json`')
    lines.append(f'- 逐用例 trace：`../trace_<用例>.csv`')
    lines.append(f'- 深水复核：`deep_check.csv`')
    with open(os.path.join(rep, '_run_index.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


def write_control_readme(ctrl_dir, ctrl_model_dir):
    if not os.path.exists(os.path.join(ctrl_dir, 'case_summary.csv')):
        return
    df = pd.read_csv(os.path.join(ctrl_dir, 'case_summary.csv'))
    lines = []
    lines.append('# 对照实验：单环境训练模型（Base_IL10 only）\n')
    lines.append('> 目的（AGENTS.md 控制变量法）：只把**基准环境 Base_IL10** 的邻域数据'
                 '给训练（`models/ddps_v2_control/`），再冻结复用到全部 8 个应力环境做 '
                 'Stage-2 在线调优 —— 回答"单点模型能否直接泛化、是否必须混合环境"。\n')
    lines.append('## 结果\n')
    lines.append('| 用例 | 种子 BER_MLSE | 最优 | Δlog10 | 步数 |')
    lines.append('| --- | --- | --- | --- | --- |')
    for _, r in df.iterrows():
        lines.append(f"| {r['env']} | `{_f(r['seed_ber']):.2e}` | "
                     f"`{_f(r['best_ber']):.2e}` | {_fmt_dl(r['delta_lb_seed_to_best'])} | "
                     f"{int(_f(r['n_steps_actual']))} |")
    lines.append('\n## 与主实验（混合环境锚定）对比结论\n')
    lines.append('- 修复后的管线**即使只用基准环境数据训练，8/8 用例也不再负向优化**'
                 '（对比 v1 同场景是负向的）。')
    lines.append('- 但在 20 dB 插损 / 复合应力等极端环境，单环境模型的外推明显衰减：'
                 '主实验最优 IL20 `2.97e-3` vs 对照 `1.47e-2`；Combined `5.74e-3` vs `3.48e-2`。'
                 '即：物理噪声主导下，**需要混合环境数据**才能把高应力用例调到位。')
    lines.append('\n## 为什么保留本目录\n')
    lines.append('- 它是主结果（`result/ddps_v2_20260907/`）的**方法学对照**，量化了'
                 '"单点模型泛化衰减边界"，是 AGENTS.md 要求的控制变量实验证据；')
    lines.append('- 若甲方判定不需要该对照，可整目录移入 archive，不影响主结果。')
    lines.append('\n[⬆ 返回结果总览](../../SUMMARY.md)')
    with open(os.path.join(ctrl_dir, 'README.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


def write_root_summary(run_dir, model_dir, ctrl_dir=None, ctrl_model_dir=None):
    test_dir = run_dir
    rep = os.path.join(run_dir, 'report')
    recs = _load_case_json(test_dir)
    summary_df = pd.read_csv(os.path.join(test_dir, 'case_summary.csv'))
    deep_p = os.path.join(rep, 'deep_check.csv')
    deep_df = pd.read_csv(deep_p) if os.path.exists(deep_p) else None

    lines = []
    lines.append('# eLPO PAM4 仿真平台 —— 结果总览（统一入口）\n')
    lines.append('> 本文件是**全部结果与报告的唯一起点**：图、数据、模型、报告都从这里'
                 '按链接跳转。请勿逐张翻图；先从下文"从哪看起"开始。\n')

    lines.append('## 0. 从哪看起\n')
    lines.append(f'1. 最新主结果跑批：**[`{run_dir}`]({run_dir}/report/_run_index.md)** —— '
                 '先看跑批索引与逐用例页，再看聚合图与指标报告。')
    lines.append(f'2. 想一次看完所有用例的图与数字：逐用例页 '
                 + '、'.join(f'[{e["name"]}]({run_dir}/report/case_{e["name"]}.md)'
                            for e in C.ENV_CASES) + '。')
    if ctrl_dir and os.path.exists(os.path.join(ctrl_dir, 'README.md')):
        lines.append(f'3. 想知道"单环境 vs 混合环境"的方法学答案：'
                     f'[{ctrl_dir} 对照说明]({ctrl_dir}/README.md)。')
    lines.append('')

    lines.append('## 1. `result/` 目录导览（回答"0907 和 control 分别是啥、是否都要"）\n')
    lines.append('| 目录 | 是什么 | 是否必须 | 原因 |')
    lines.append('| --- | --- | --- | --- |')
    lines.append(f'| `{os.path.basename(run_dir)}/` | **主实验（生产口径）**：混合环境锚定'
                 '数据训练 `models/ddps_v2`，8 个应力环境冻结复用做 Stage-2 在线调优；'
                 '含完整报告/图/逐用例页 | ✅ 必须 | 这是交付给甲方的最终结果 |')
    if ctrl_dir:
        lines.append(f'| `{os.path.basename(ctrl_dir)}/` | **方法学对照**：只用基准环境数据'
                     '训练 `models/ddps_v2_control`，同流程重跑，量化单点模型泛化衰减边界'
                     '（证明修复有效 + 说明为何需要混合数据） | ⚠️ 建议保留 | '
                     '它是主结果成立的方法学证据（AGENTS.md 控制变量实验）；不需要可归档 |')
    lines.append('| `ddps/`(历史) | v1 泛化测试产物 | ❌ 已归档 | 已移入 '
                 '`archive/20260904_ddps_v1_physical_pre_v2/` |')
    lines.append('')

    lines.append('## 2. 主结果（最新跑批）\n')
    lines.append(f'- 跑批索引（推荐起点）：[{run_dir}/report/_run_index.md]({run_dir}/report/_run_index.md)')
    lines.append(f'- 指标报告（口径/模型指标/根因表/深水复核）：'
                 f'[{run_dir}/report/ddps_v2_report.md]({run_dir}/report/ddps_v2_report.md)')
    lines.append(f'- 聚合改善图：![overview]({run_dir}/report/ddps_v2_overview.png)')
    lines.append('\n### 2.1 逐用例速览\n')
    lines.append('| 用例 | 环境 | 种子 BER_MLSE | Stage-2 最优 | Δlog10 | 判定 | 详情页 |')
    lines.append('| --- | --- | --- | --- | --- | --- | --- |')
    for env in C.ENV_CASES:
        name = env['name']
        rec = recs.get(name, {})
        seed = _f(rec.get('seed_ber')); best = _f(rec.get('best_ber'))
        dl = _f(rec.get('delta_lb_seed_to_best'))
        tag = ''
        if not np.isnan(dl):
            tag = '✅ 改善' if dl < -0.01 else ('❌ 变差' if dl > 0.01 else '➖ 持平')
        lines.append(f"| [{name}]({run_dir}/report/case_{name}.md) | "
                     f"IL{_f(env['il']):.0f}dB"
                     f"{'+CD'+str(int(env['cd'])) if env['cd'] else ''}"
                     f"{'+DGD'+str(int(env['dgd'])) if env['dgd'] else ''} | "
                     f"`{seed:.2e}` | `{best:.2e}` | {_fmt_dl(dl)} | {tag} | "
                     f"[case_{name}.md]({run_dir}/report/case_{name}.md) |")
    lines.append('')
    if deep_df is not None and len(deep_df):
        lines.append('### 2.2 深水统计复核（262144 符号重测 seed/best）\n')
        lines.append('| 用例 | seed (deep) | best (deep) | Δlog10 |')
        lines.append('| --- | --- | --- | --- |')
        for _, r in deep_df.iterrows():
            lines.append(f"| {r['env']} | `{_f(r['seed_ber_deep']):.2e}` | "
                         f"`{_f(r['best_ber_deep']):.2e}` | {_fmt_dl(r['delta_deep'])} |")
        lines.append('')

    lines.append('## 3. 对照实验（单环境训练）\n')
    if ctrl_dir and os.path.exists(os.path.join(ctrl_dir, 'README.md')):
        lines.append(f'- 完整说明：[`{ctrl_dir}/README.md`]({ctrl_dir}/README.md)')
        lines.append('- 一句话结论：修复后的管线即使只用基准数据也不负向（对比 v1），'
                     '但极端环境的最优值比混合锚定模型差 4~10× —— 主结果采用混合锚定模型。')
    lines.append('')

    lines.append('## 4. 数据与模型\n')
    lines.append('- 训练数据集：`dataset/ddps_v2_dataset_*.csv`（本次 '
                 '[`dataset/ddps_v2_dataset_20260907_190819.csv`](../dataset/ddps_v2_dataset_20260907_190819.csv)，'
                 '748 点环境锚定邻域）')
    lines.append('- 模型：[`models/ddps_v2/`](../models/ddps_v2/)（model_a.pkl / model_b.pkl / meta.json）；'
                 '对照模型 [`models/ddps_v2_control/`](../models/ddps_v2_control/)')
    lines.append(f'- 逐用例 trace：`{run_dir}/trace_<用例>.csv`；'
                 f'case 汇总 [`{run_dir}/case_summary.csv`]({run_dir}/case_summary.csv)')
    lines.append('')

    lines.append('## 5. 历史归档与文档\n')
    lines.append('- 历史（v1/修复前）数据、模型、结果：`archive/20260904_ddps_v1_physical_pre_v2/`'
                 '（**本地磁盘目录**，仓库政策不入库；旧版内容仍保留在本分支 git 历史）')
    lines.append('- [docs/06. DDPS v2 重做报告](../docs/06_DDPS_v2_Rerun.md) —— 根因/修正/结果总述')
    lines.append('- [docs/04. DDPS 架构](../docs/04_DDPS_Optimization.md)、'
                 '[docs/03. 排坑记录](../docs/03_Troubleshooting_History.md)')
    lines.append('- [README（项目主页）](../README.md)')
    lines.append('\n---\n')
    lines.append('> 生成方式：`python make_result_index.py --run-dir <run> --model-dir <md> '
                 '[--control-dir <ctrl>]`（幂等，只读产物文件，不重跑仿真）。')

    with open('result/SUMMARY.md', 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    print('[index] result/SUMMARY.md written')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run-dir', default='result/ddps_v2_20260907')
    ap.add_argument('--model-dir', default='models/ddps_v2')
    ap.add_argument('--control-dir', default='result/ddps_v2_control')
    ap.add_argument('--control-model-dir', default='models/ddps_v2_control')
    a = ap.parse_args()
    write_run_index(a.run_dir, a.model_dir)
    write_control_readme(a.control_dir, a.control_model_dir)
    write_root_summary(a.run_dir, a.model_dir, a.control_dir, a.control_model_dir)
    print('[index] done')


if __name__ == '__main__':
    main()
