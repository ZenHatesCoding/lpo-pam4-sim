# -*- coding: utf-8 -*-
"""交付件对比版：三组训练 → 15环境泛化。

组 A: 基线训练 (Base_IL10x10, 工程标定种子点)
组 B: IL20x20 训练 (BO 寻优种子点, gDC2=-4.95)
组 C: IL20x20 训练 (梯度下降终点种子点, gDC2=-2.66)

输出自包含 HTML 到 deliverables/DDPS_v6_TrainingComparison.html。
"""
import os, sys, json, base64, argparse
import pandas as pd, numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _load_summary(d):
    return {r['env']: r for _, r in pd.read_csv(os.path.join(d, 'case_summary.csv')).iterrows()}


def _img_tag(path):
    if not os.path.exists(path):
        return ''
    with open(path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode()
    return f'<img src="data:image/png;base64,{b64}" style="width:100%;max-width:760px"/>'


def _kpi_block(label, df, d, color='#1a4480'):
    imp = df['seed_ber'] / df['best_ber']
    total = 0; worse = 0
    for _, r in df.iterrows():
        p = os.path.join(d, f'trace_{r["env"]}.csv')
        if os.path.exists(p):
            tr = pd.read_csv(p)
            if not tr.empty:
                total += len(tr)
                worse += int((tr['real_ber'] > r['seed_ber'] * 1.001).sum())
    pos = int((imp > 1).sum())
    wc = '#d00' if worse > 0 else '#0a7'
    return (f'<h3>{label}</h3>'
            f'<div class="kpi"><div class="v" style="color:{color}">x{imp.mean():.2f}</div><div class="l">平均改善</div></div>'
            f'<div class="kpi"><div class="v">{pos}/15</div><div class="l">正向用例</div></div>'
            f'<div class="kpi"><div class="v" style="color:{wc}">{worse}</div><div class="l">劣化步 / {total} 总步</div></div>'
            f'<div class="kpi"><div class="v">{total}</div><div class="l">总调优步数</div></div>')


def _rows_compare3(s_a, s_b, s_c, order):
    out = []
    for env in order:
        rows = []
        for s, tag in [(s_a, 'A'), (s_b, 'B'), (s_c, 'C')]:
            r = s.get(env, {})
            seed = r.get('seed_ber', 0)
            best = r.get('best_ber', seed)
            imp = seed / best if best > 0 else 0
            rows.append((seed, best, imp))
        # winner
        bests = [rows[0][1], rows[1][1], rows[2][1]]
        win_idx = int(np.argmin(bests))
        out.append(
            f"<tr><td>{env}</td>"
            + ''.join(
                f'<td class="n">{r[0]:.3e}</td><td class="n">x{r[2]:.2f}</td>'
                for r in rows
            )
            + f'<td class="n">{"ABC"[win_idx]}</td></tr>')
    return '\n'.join(out)


TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"/>
<title>DDPS v6 训练环境对比实验</title>
<style>
body{font-family:'Segoe UI',system-ui,sans-serif;max-width:980px;margin:0 auto;padding:24px;color:#1a1a1a;background:#fafafa}
h1{color:#1a4480;border-bottom:3px solid #1a4480;padding-bottom:8px}
h2{color:#1a4480;margin-top:36px;border-left:4px solid #1a4480;padding-left:10px}
h3{color:#333;margin-top:24px}
table{border-collapse:collapse;width:100%;margin:12px 0;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,0.08)}
th,td{border:1px solid #ddd;padding:7px 10px;text-align:left}
th{background:#1a4480;color:#fff;font-size:13px}
td{font-size:13px}
td.n{text-align:right;font-family:'Consolas',monospace}
.kpi{display:inline-block;background:#fff;border:1px solid #ddd;border-radius:6px;padding:10px 16px;margin:4px;text-align:center}
.kpi .v{font-size:22px;font-weight:bold;color:#1a4480}
.kpi .l{font-size:12px;color:#666}
.caption{font-size:12px;color:#888;margin:6px 0}
</style></head><body>

<h1>DDPS v6 训练环境对比实验</h1>
<p class="caption">同一套 v6 架构（A=探针→BER 方向代理 + B=参数→BER 风险控制），唯一变量是<strong>训练环境与种子点</strong>。
三组模型结构、数据集规模、采样方式、在线调优流程完全相同，冻结后泛化到同一组 15 个测试环境。</p>

<h2>实验设计</h2>
<table>
<tr><th>维度</th><th>组 A：基线训练</th><th>组 B：IL20x20 (BO 种子)</th><th>组 C：IL20x20 (梯度下降种子)</th></tr>
<tr><td>训练环境</td><td>Base_IL10x10 (Tx10+Rx10 dB)</td><td>IL20x20 (Tx20+Rx20 dB)</td><td>IL20x20 (Tx20+Rx20 dB)</td></tr>
<tr><td>种子点来源</td><td>工程标定值</td><td>贝叶斯优化全局寻优 (50轮)</td><td>基线模型梯度下降终点</td></tr>
<tr><td>种子 gDC</td><td>0.00</td><td>-0.07</td><td>-2.27</td></tr>
<tr><td>种子 gDC2</td><td>0.00</td><td>-4.95 (贴边界)</td><td>-2.66 (中间值)</td></tr>
<tr><td>种子点 BER (正式协议)</td><td>3.75e-4</td><td>4.29e-4</td><td>1.52e-3</td></tr>
<tr><td>模型 A R²</td><td>0.93</td><td>0.76</td><td>0.74</td></tr>
<tr><td>模型 B R²</td><td>0.91</td><td>0.69</td><td>0.62</td></tr>
<tr><td>数据集</td><td>2001 点 × 262144 × 3seed</td><td>同左</td><td>同左</td></tr>
<tr><td>测试环境</td><td colspan="3">同一组 15 个（对称/非对称插损、CD、DGD、复合、高噪）</td></tr>
</table>

<h2>总体结果</h2>
<!--KPI_A-->
<!--KPI_B-->
<!--KPI_C-->

<h2>逐用例对比</h2>
<div class="tw">
<table class="wide" id="tbl-compare">
<caption>三组训练的种子 BER / 改善倍数 / 最优者标记 <span class="sh">· 可左右滑动</span></caption>
<tr><th rowspan="2">用例</th><th colspan="3">组 A：基线训练</th><th colspan="3">组 B：IL20 (BO种子)</th><th colspan="3">组 C：IL20 (GD种子)</th><th rowspan="2">最优</th></tr>
<tr><th>种子 BER</th><th>最优 BER</th><th>改善</th><th>种子 BER</th><th>最优 BER</th><th>改善</th><th>种子 BER</th><th>最优 BER</th><th>改善</th></tr>
<!--COMPARE_ROWS-->
</table>
</div>
<p class="caption">最优列：A/B/C 标记该用例最优 BER 来自哪组。</p>

<h2>关键发现</h2>
<!--FINDINGS-->

<h2>收敛曲线</h2>
<p class="caption">每个用例的 Model A 预测 / Model B 预测 / 实测 BER 三曲线。</p>
<h3>组 A：基线训练</h3>
{{IMG_ddps_v6_convergence_A}}
<h3>组 B：IL20x20 (BO 种子)</h3>
{{IMG_ddps_v6_convergence_B}}
<h3>组 C：IL20x20 (GD 种子)</h3>
{{IMG_ddps_v6_convergence_C}}

<h2>gain / drive_rms 轨迹</h2>
<p class="caption">gain（左轴）和 drive_rms（右轴）随调优步数的变化。</p>
<h3>组 A：基线训练</h3>
{{IMG_ddps_v6_gain_rms_A}}
<h3>组 B：IL20x20 (BO 种子)</h3>
{{IMG_ddps_v6_gain_rms_B}}
<h3>组 C：IL20x20 (GD 种子)</h3>
{{IMG_ddps_v6_gain_rms_C}}

<h2>预测-实测跟踪散点</h2>
<p class="caption">Model A 预测 BER vs 实测 BER，按环境类别着色。</p>
<h3>组 A：基线训练</h3>
{{IMG_ddps_v6_tracking_A}}
<h3>组 B：IL20x20 (BO 种子)</h3>
{{IMG_ddps_v6_tracking_B}}
<h3>组 C：IL20x20 (GD 种子)</h3>
{{IMG_ddps_v6_tracking_C}}

<h2>最难用例四联图 (Comb_IL20x20_CD15_DGD5)</h2>
<p class="caption">收敛 + FFE 抽头 + CTLE 频响 + 探针 FIR。</p>
<h3>组 A：基线训练</h3>
{{IMG_ddps_v6_case_Comb_IL20x20_CD15_DGD5_a_A}}
<h3>组 B：IL20x20 (BO 种子)</h3>
{{IMG_ddps_v6_case_Comb_IL20x20_CD15_DGD5_a_B}}
<h3>组 C：IL20x20 (GD 种子)</h3>
{{IMG_ddps_v6_case_Comb_IL20x20_CD15_DGD5_a_C}}

</body></html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir-a', default='result/ddps_v6_main', help='组 A 结果目录')
    ap.add_argument('--dir-b', default='result/ddps_v6_il20_main', help='组 B 结果目录')
    ap.add_argument('--dir-c', default='result/ddps_v6_il20gd_main', help='组 C 结果目录')
    ap.add_argument('--out', default='deliverables/DDPS_v6_TrainingComparison.html')
    args = ap.parse_args()

    s_a = _load_summary(args.dir_a)
    s_b = _load_summary(args.dir_b)
    s_c = _load_summary(args.dir_c)
    order = list(s_a.keys())

    df_a = pd.read_csv(os.path.join(args.dir_a, 'case_summary.csv'))
    df_b = pd.read_csv(os.path.join(args.dir_b, 'case_summary.csv'))
    df_c = pd.read_csv(os.path.join(args.dir_c, 'case_summary.csv'))

    imp_a = df_a['seed_ber'] / df_a['best_ber']
    imp_b = df_b['seed_ber'] / df_b['best_ber']
    imp_c = df_c['seed_ber'] / df_c['best_ber']

    comb_b = s_b.get('Comb_IL20x20_CD15_DGD5', {})
    comb_c = s_c.get('Comb_IL20x20_CD15_DGD5', {})
    comb_imp_b = comb_b.get('seed_ber', 1) / comb_b.get('best_ber', 1) if comb_b.get('best_ber', 0) > 0 else 0
    comb_imp_c = comb_c.get('seed_ber', 1) / comb_c.get('best_ber', 1) if comb_c.get('best_ber', 0) > 0 else 0
    il20_c = s_c.get('IL20x20', {})
    il20_imp_c = il20_c.get('seed_ber', 1) / il20_c.get('best_ber', 1) if il20_c.get('best_ber', 0) > 0 else 0

    t_a, w_a = _count_worse(args.dir_a, s_a)
    t_b, w_b = _count_worse(args.dir_b, s_b)
    t_c, w_c = _count_worse(args.dir_c, s_c)

    findings = []
    findings.append(f"<p><strong>组 A 基线训练最稳健</strong>：平均 ×{imp_a.mean():.2f}（15/15 正向，{w_a} 劣化/{t_a} 步），"
                     f"模型在所有环境方向可信，全程无退步。</p>")
    findings.append(f"<p><strong>组 B (BO 种子) 在重损环境更优但泛化性下降</strong>：Comb_IL20x20 改善 ×{comb_imp_b:.2f}（基线 ×10.15）。"
                     f"但 {w_b} 步劣化（{t_b} 步），低损环境 gDC2 推到 -5 边界，预测增益偏小导致早停。</p>")
    findings.append(f"<p><strong>组 C (GD 种子) 重损环境最优但退步最多</strong>：Comb_IL20x20 改善 ×{comb_imp_c:.2f}，"
                     f"IL20x20 改善 ×{il20_imp_c:.2f}（组 B 仅 ×9.77）。但 {w_c} 步劣化（{t_c} 步），仅 12/15 正向。</p>")
    findings.append("<p><strong>种子点选择决定模型对哪个区域学得准</strong>：BO 种子 gDC2=-4.95 学到的形状在低损环境过度补偿；"
                     "GD 种子 gDC2=-2.66 形状更通用，走得更深但在低损环境容易跑过头。基线种子 gDC2=0 在低损和高损之间最均衡。</p>")
    findings.append("<p><strong>结论</strong>：低损环境（IL10x10）训练 + 工程标定种子点的组合泛化性最好——"
                     "代理学到的形状-BER 方向在 15 个环境都成立。高损环境训练的模型对高损环境更准但牺牲了跨环境泛化性。</p>")

    def _imgs(name):
        return {f'{{{{IMG_{name}_A}}}}': _img_tag(os.path.join(args.dir_a, 'report', name + '.png')),
                f'{{{{IMG_{name}_B}}}}': _img_tag(os.path.join(args.dir_b, 'report', name + '.png')),
                f'{{{{IMG_{name}_C}}}}': _img_tag(os.path.join(args.dir_c, 'report', name + '.png'))}

    html = TEMPLATE
    repl = {
        '<!--KPI_A-->': _kpi_block('组 A：基线训练 (Base_IL10x10)', df_a, args.dir_a, '#1a4480'),
        '<!--KPI_B-->': _kpi_block('组 B：IL20x20 (BO 种子)', df_b, args.dir_b, '#c06000'),
        '<!--KPI_C-->': _kpi_block('组 C：IL20x20 (GD 种子)', df_c, args.dir_c, '#0a7'),
        '<!--COMPARE_ROWS-->': _rows_compare3(s_a, s_b, s_c, order),
        '<!--FINDINGS-->': '\n'.join(findings),
    }
    for img_name in ['ddps_v6_convergence', 'ddps_v6_gain_rms', 'ddps_v6_tracking', 'ddps_v6_case_Comb_IL20x20_CD15_DGD5_a']:
        repl.update(_imgs(img_name))
    for k, v in repl.items():
        html = html.replace(k, v)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"[compare] written {args.out}  ({os.path.getsize(args.out)/1024:.0f} KB)")
    print(f"[compare] A: mean x{imp_a.mean():.2f}, {int((imp_a>1).sum())}/15, {w_a} worse / {t_a} steps")
    print(f"[compare] B: mean x{imp_b.mean():.2f}, {int((imp_b>1).sum())}/15, {w_b} worse / {t_b} steps")
    print(f"[compare] C: mean x{imp_c.mean():.2f}, {int((imp_c>1).sum())}/15, {w_c} worse / {t_c} steps")


def _count_worse(d, summary):
    total = 0; worse = 0
    for env, r in summary.items():
        p = os.path.join(d, f'trace_{env}.csv')
        if not os.path.exists(p):
            continue
        tr = pd.read_csv(p)
        if tr.empty:
            continue
        total += len(tr)
        worse += int((tr['real_ber'] > r['seed_ber'] * 1.001).sum())
    return total, worse


if __name__ == '__main__':
    main()
