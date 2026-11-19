# -*- coding: utf-8 -*-
"""起点鲁棒性实验的独立汇总表（不复用交付件生成器的代码，用来交叉核对交付件里的倍率）。

用法：
  python tools\\seed_study_table.py                       # 汇总 result/seed_study 下所有起点
  python tools\\seed_study_table.py --root result/seed_study --csv out.csv

口径：
  每一格 → 同一起点下 `代理 × full` 的逐用例 BER 比值，取几何均值；小于 1 表示该格更好。
  逐用例对齐按用例名（不是 CSV 行序），缺哪个用例就在分母里去掉哪个，绝不拿错行相除。
"""
import argparse
import csv
import math
import os

CELLS = [('full', '代理 × full'), ('rotate', '代理 × rotate'), ('secant', '代理 × secant'),
         ('direct_full', '回传 × full'), ('direct_rotate', '回传 × rotate'),
         ('direct_secant', '回传 × secant')]


def load(path):
    """读 case_summary.csv -> {env: best_ber}"""
    out = {}
    with open(path, encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            try:
                out[row['env']] = float(row['best_ber'])
            except (KeyError, TypeError, ValueError):
                continue
    return out


def geomean_ratio(a, b):
    """a/b 的几何均值（只用两边都有的用例，且两边都 > 0）。"""
    keys = sorted(set(a) & set(b))
    vals = [(a[k] / b[k]) for k in keys if a[k] > 0 and b[k] > 0]
    if not vals:
        return None, 0
    return math.exp(sum(math.log(v) for v in vals) / len(vals)), len(vals)


def one_seed(root, seed):
    rows = []
    ref = load(os.path.join(root, seed, 'ddps_cpp_full', 'case_summary.csv')) \
        if os.path.exists(os.path.join(root, seed, 'ddps_cpp_full', 'case_summary.csv')) else None
    for key, label in CELLS:
        p = os.path.join(root, seed, 'ddps_cpp_%s' % key, 'case_summary.csv')
        if not os.path.exists(p):
            rows.append((label, None, 0))
            continue
        cur = load(p)
        if key == 'full' or ref is None:
            rows.append((label, 1.0 if key == 'full' else None, len(cur)))
            continue
        g, n = geomean_ratio(cur, ref)
        rows.append((label, g, n))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='result/seed_study')
    ap.add_argument('--csv', default=None, help='另存一份长表 CSV')
    ap.add_argument('--md', action='store_true', help='输出 markdown 表（可直接粘进 docs）')
    a = ap.parse_args()

    seeds = [d for d in sorted(os.listdir(a.root))
             if os.path.isdir(os.path.join(a.root, d))] if os.path.isdir(a.root) else []
    flat = []
    for s in seeds:
        rows = one_seed(a.root, s)
        print('\n== %s ==' % s)
        for label, g, n in rows:
            print('  %-14s %s' % (label, '—' if g is None else '%.3f×  (用例 %d)' % (g, n)))
            flat.append((s, label, '' if g is None else '%.4f' % g, n))

    if a.md:
        # 行 = 格，列 = 起点（现役在最左）
        seed_list = seeds
        print('\n| 格 | ' + ' | '.join(seed_list) + ' |')
        print('|' + '---|' * (len(seed_list) + 1))
        for key, label in CELLS:
            cells = []
            for sd in seed_list:
                g = dict((lb, gg) for lb, gg, _n in one_seed(a.root, sd)).get(label)
                if g is None:
                    cells.append('—')
                elif key == 'full':
                    cells.append('1.000×')
                else:
                    cells.append('%.3f×' % g)
            print('| %s | %s |' % (label, ' | '.join(cells)))
        print('')
        for sd in seed_list:
            p = os.path.join(a.root, sd, 'ddps_cpp_full', 'case_summary.csv')
            if os.path.exists(p):
                cur = load(p)
                gm = math.exp(sum(math.log(v) for v in cur.values()) / len(cur))
                print('%s：代理 × full 的 15 用例几何均值 %.3e' % (sd, gm))

    if a.csv:
        with open(a.csv, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f)
            w.writerow(['seed', 'cell', 'geo_ratio', 'n_cases'])
            w.writerows(flat)
        print('\n[out] %s' % a.csv)


if __name__ == '__main__':
    main()
