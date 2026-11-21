# -*- coding: utf-8 -*-
"""从 `result/seed_study` 重算 §6b.1 的两张表，并写回 docs/DDPS_Method.md 的标记区间。

用法：python tools\\study_doc_tables.py [--check]
- `--check` 只比对、不写文件（退出码 1 表示文档与结果不一致）。

口径与交付件 §6.6 完全一致：倍率 = 该格落点 / 同一起点下 `代理 × full` 落点，
逐用例算完再取几何均值；用例按名字对齐（不按行序）。
"""
import argparse
import csv
import io
import math
import os
import sys

DOC = os.path.join('docs', 'DDPS_Method.md')
ROOT = os.path.join('result', 'seed_study')
START = '<!--STUDY_TABLES_START-->'
END = '<!--STUDY_TABLES_END-->'

CELLS = [('full', '代理 × full'), ('rotate', '代理 × rotate'), ('secant', '代理 × secant'),
         ('direct_full', '回传 × full'), ('direct_rotate', '回传 × rotate'),
         ('direct_secant', '回传 × secant')]
SEED_LABEL = {'s1_gain-2.6dB': '纯幅度错', 's2_ctle_g3.0_1.5': '纯均衡错',
              's3_shape3.0': '形状+幅度都错'}


def read_cases(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        return {r['env']: float(r['best_ber']) for r in csv.DictReader(f)}


def geomean(vals):
    v = [x for x in vals if x > 0]
    return math.exp(sum(math.log(x) for x in v) / len(v)) if v else float('nan')


def num_sym(path):
    p = os.path.join(path, 'run_config.json')
    if not os.path.exists(p):
        return None
    import json
    with open(p, encoding='utf-8') as f:
        return int(json.load(f).get('num_symbols', 0)) or None


def scan():
    seeds = []
    for seed in sorted(os.listdir(ROOT)):
        sdir = os.path.join(ROOT, seed)
        if not os.path.isdir(sdir):
            continue
        cells, nsym = {}, None
        for key, _label in CELLS:
            d = os.path.join(sdir, 'ddps_cpp_' + key)
            p = os.path.join(d, 'case_summary.csv')
            if os.path.exists(p):
                cells[key] = read_cases(p)
                nsym = nsym or num_sym(d)
        if cells.get('full'):
            seeds.append({'name': seed, 'cells': cells, 'nsym': nsym})
    return seeds


def fmt_ratio(x):
    if x is None:
        return '—'
    if x < 0.1 or 0.9 <= x <= 1.1:
        return '%.3f×' % x
    return '%.2f×' % x


def tables(seeds):
    if not seeds:
        return '（尚无结果）\n'
    nsym = seeds[0]['nsym']
    floor = 0.5 / (2.0 * nsym) if nsym else float('nan')
    names = [s['name'] for s in seeds]
    cols = ' | '.join(SEED_LABEL.get(n, n) for n in names)

    out = []
    out.append('倍率 = 该格落点 / 同一起点下 `代理 × full` 的落点（逐用例算完再取几何均值）。'
               '差起点用 %s 符号/点、检测底 %.2e；现役六格是 2^22，两栏只比绝对落点、不比强弱'
               '（跨规模的差分不清是起点造成的还是检测底/量化造成的）。\n' % (num_label(nsym), floor))
    out.append('| 格 | %s |' % cols)
    out.append('|---|%s' % ('---|' * len(names)))
    for key, label in CELLS:
        cells = []
        for s in seeds:
            v = s['cells'].get(key)
            ref = s['cells'].get('full')
            if v is None or not ref:
                cells.append('—')
                continue
            if key == 'full':
                cells.append('1.000×')
                continue
            rr = geomean([v[k] / ref[k] for k in v if k in ref and ref[k] > 0])
            cells.append(fmt_ratio(rr))
        out.append('| %s | %s |' % (label, ' | '.join(cells)))
    out.append('')
    out.append('绝对落点（15 用例几何均值 best BER；差起点检测底 %.2e，现役 2^22 检测底 5.96e-08）：\n' % floor)
    out.append('| 起点 | 代理 × full | 代理 × rotate | 代理 × secant | 回传 × full |')
    out.append('|---|---|---|---|---|')
    for s in seeds:
        row = []
        for key in ('full', 'rotate', 'secant', 'direct_full'):
            v = s['cells'].get(key)
            row.append('%.2e' % geomean(list(v.values())) if v else '—')
        out.append('| %s（%s） | %s |' % (SEED_LABEL.get(s['name'], s['name']), num_label(s['nsym']),
                                          ' | '.join(row)))
    out.append('')
    return '\n'.join(out)


def num_label(n):
    if not n:
        return '?'
    return '2^%d' % round(math.log2(n))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只比对，不写文件')
    a = ap.parse_args()
    body = tables(scan())
    s = io.open(DOC, encoding='utf-8').read()
    i, j = s.find(START), s.find(END)
    if i < 0 or j < 0:
        print('文档里没有标记区间，先跑一次标记脚本')
        return 2
    new = s[:i] + START + '\n' + body + '\n' + s[j:]
    if a.check:
        ok = (new == s)
        print('文档与结果一致' if ok else '文档与结果不一致，请重跑本脚本')
        return 0 if ok else 1
    io.open(DOC, 'w', encoding='utf-8', newline='').write(new)
    print('§6b.1 两张表已按结果重算写回')
    sys.stdout.write(body)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
