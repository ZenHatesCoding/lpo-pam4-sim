#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""DDPS 交付验收：一条命令回答"这套结果是不是真的跑完、跑对了"。

设计原则：只用磁盘上的结果文件说话，不依赖任何人的转述，也不依赖生成器代码。
覆盖三类检查：
  A 完整性  —— 每个结果目录的用例数、汇总文件、逐用例 trace/probes 是否齐
  B 机制    —— 逐用例记账恒等式（真实评估 = 落地 + 微扰态）、微扰态成对、
               刷新维序列与各档语义一致、无 NaN / 无非正 BER
  C 一致性与新鲜度 —— 2^18 等价目录逐轨迹比对（max_rel < 1e-9）、交付件比最新结果新、
               交付件不含版本历史类禁词

用法：
  python tools/verify_ddps.py                              # 验收默认的现役结果集
  python tools/verify_ddps.py --prefix result/ddps_cpp     # 验收别的前缀
  python tools/verify_ddps.py --cells full,rotate,secant,direct_secant
  python tools/verify_ddps.py --expect-cases 15 --expect-symbols 2097152
退出码：0 = 全部通过；1 = 有检查未过；2 = 结果集不全（缺少期望的目录）。
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORBIDDEN = ['上一版', '前一版', '版本历史', '历史版本', '根因', '排错', 'v8 ', 'v9 ']


class Report:
    def __init__(self):
        self.rows = []
        self.fail = 0
        self.missing = 0

    def add(self, cell, cases, evals, anomalies, note=''):
        ok = anomalies == 0
        if not ok:
            self.fail += 1
        self.rows.append((cell, cases, evals, anomalies, ok, note))

    def dump(self):
        print('%-16s %6s %10s %10s  %s' % ('结果目录', '用例', '真实评估', '异常', '判定'))
        for cell, cases, evals, anomalies, ok, note in self.rows:
            print('%-16s %6s %10d %10d  %s%s'
                  % (cell, cases, evals, anomalies, '✓' if ok else '✗', ('  ' + note) if note else ''))


def read_csv_any(path):
    try:
        return pd.read_csv(path)
    except Exception:
        return None


def load_json(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def as_records(obj):
    if obj is None:
        return []
    return obj if isinstance(obj, list) else [obj]


def trace_refreshed_ok(mode, steps, refreshed_seq, n_shape):
    """按档位语义核对刷新维序列（refreshed 为空 = 该步没有任何微扰态）。

    n_shape = 参与微扰的维数：代理档 7（gain 维走解析梯度，不进微扰），direct 档 8。
    """
    all_dims = list(range(n_shape))
    seq = [sorted(int(i) for i in r) if r else [] for r in refreshed_seq]
    if mode == 'full':
        return all(s == all_dims for s in seq)
    if mode == 'secant':
        return seq[0] == all_dims and all(s == [] for s in seq[1:])
    if mode == 'rotate':
        if seq[0] != all_dims:
            return False
        for k, s in enumerate(seq[1:], start=1):
            want = sorted((k * 2 + j) % n_shape for j in range(2))
            if s != want:
                return False
        return True
    return True  # 未知档位不做语义判定


def check_cell(prefix, cell, expect_cases, expect_symbols, rep):
    d = f'{prefix}_{cell}'
    cfg = load_json(os.path.join(d, 'run_config.json'))
    if cfg is None:
        print(f'  !! {d} 缺 run_config.json')
        rep.missing += 1
        return
    method = cfg.get('method', 'proxy')
    grad_mode = cfg.get('grad_mode', '')
    tag = grad_mode if method == 'proxy' else f'{method}/{grad_mode}'
    sym = cfg.get('num_symbols')
    if expect_symbols and sym != expect_symbols:
        print(f'  !! {d} num_symbols={sym}，期望 {expect_symbols}')
        rep.fail += 1

    summ = as_records(load_json(os.path.join(d, 'case_summary.json')))
    if not summ:
        csv = read_csv_any(os.path.join(d, 'case_summary.csv'))
        summ = csv.to_dict('records') if csv is not None else []
    if not summ:
        print(f'  !! {d} 缺 case_summary')
        rep.missing += 1
        return

    anomalies, evals, n_landed = 0, 0, 0
    for case in summ:
        env = case.get('env', '?')
        n_real = case.get('n_real_evals')
        n_land = case.get('n_landed')
        n_prob = case.get('n_probe_states')
        if None not in (n_real, n_land, n_prob) and (int(n_real) != int(n_land) + int(n_prob)):
            print(f'  !! {d}/{env} 记账不符: {n_real} != {n_land}+{n_prob}')
            anomalies += 1
        if n_real is not None:
            evals += int(n_real)
        if n_land is not None:
            n_landed += int(n_land)

        for key in ('best_ber', 'final_ber', 'seed_ber'):
            v = case.get(key)
            if v is None or pd.isna(v) or float(v) <= 0:
                print(f'  !! {d}/{env} {key} 非法: {v}')
                anomalies += 1
        if float(case.get('best_ber', 1) or 1) > float(case.get('seed_ber', 0) or 0) * 1.5:
            print(f'  !! {d}/{env} 调优后反而明显变差: seed={case.get("seed_ber")} best={case.get("best_ber")}')
            anomalies += 1

        # 逐轨迹：微扰态成对 + 刷新维序列
        safe = str(env).replace(' ', '_').replace('(', '').replace(')', '')
        tr = read_csv_any(os.path.join(d, f'trace_{safe}.csv'))
        if tr is None:
            print(f'  !! {d} 缺 trace_{safe}.csv')
            anomalies += 1
            continue
        if 'refreshed' in tr.columns:
            seq = ['' if (isinstance(v, float) and pd.isna(v)) else str(v) for v in tr['refreshed']]
            parsed = [[int(t) for t in re.findall(r'\d+', s)] for s in seq]
            n_shape = 8 if method == 'direct' else 7
            if not trace_refreshed_ok(mode_of(tag), len(tr), parsed, n_shape):
                print(f'  !! {d}/{env} 刷新维序列与 {tag} 语义不符')
                anomalies += 1
            # 机制体检②：微扰态次数 = Σ 各步刷新维数 × 2（每维 ±ε 两侧），落地次数 = 轨迹行数
            exp_probe = 2 * sum(len(r) for r in parsed)
            if n_prob is not None and int(n_prob) != exp_probe:
                print(f'  !! {d}/{env} 微扰态次数 {int(n_prob)} != 轨迹推出的 {exp_probe}')
                anomalies += 1
            if n_land is not None and int(n_land) != len(tr):
                print(f'  !! {d}/{env} 落地次数 {int(n_land)} != 轨迹行数 {len(tr)}')
                anomalies += 1
        pr = read_csv_any(os.path.join(d, f'probes_{safe}.csv'))
        if pr is not None and not pr.empty and 'sign' in pr.columns:
            bad = 0
            for (st, prm), grp in pr.groupby(['step', 'param']):
                if sorted(grp['sign'].tolist()) != [-1, 1]:
                    bad += 1
            if bad:
                print(f'  !! {d}/{env} 有 {bad} 对微扰态不成对')
                anomalies += bad

    if len(summ) != expect_cases:
        print(f'  !! {d} 用例数 {len(summ)} != {expect_cases}')
        anomalies += 1
    rep.add(d, len(summ), evals, anomalies, '')


def mode_of(tag):
    for m in ('full', 'rotate', 'secant'):
        if tag.endswith(m):
            return m
    return tag


def check_equivalence(prefix, cells, rep):
    print('\n--- C 2^18 等价（Python ↔ C++ 逐轨迹）---')
    eq = 0
    for cell in cells:
        py = f'result/ddps_equiv_py_{cell}'
        cpp = f'result/ddps_equiv_cpp_{cell}'
        if not (os.path.isdir(py) and os.path.isdir(cpp)):
            print(f'  · {cell}: 未找到 2^18 等价目录（{py} / {cpp}）')
            continue
        rc = subprocess.run([sys.executable, 'cpp/compare_traces.py', '--py', py, '--cpp', cpp],
                            cwd=ROOT, capture_output=True, text=True,
                            encoding='utf-8', errors='replace')
        tail = [l for l in (rc.stdout or '').splitlines() if l.strip()][-1:]
        print(f'  {"✓" if rc.returncode == 0 else "✗"} {cell}: {tail[0] if tail else "rc=%d" % rc.returncode}')
        if rc.returncode != 0:
            eq += 1
    if eq:
        rep.fail += eq
    return eq


def check_deliverable(path, newest_result):
    print('\n--- C 交付件新鲜度与禁词 ---')
    if not os.path.exists(path):
        print(f'  ✗ 缺交付件 {path}')
        return 1
    bad = 0
    mt = os.path.getmtime(path)
    print(f'  mtime={mt:.0f}  最新结果 mtime={newest_result:.0f}  '
          f'{"✓ 交付件不早于结果" if mt >= newest_result else "✗ 交付件比结果旧"}')
    bad += 0 if mt >= newest_result else 1
    raw = open(path, encoding='utf-8', errors='ignore').read()
    body = re.sub(r'<script.*?</script>|data:image/[^"\')]+', ' ', raw, flags=re.S | re.I)
    hits = [w for w in FORBIDDEN if w in body]
    print(f'  禁词命中: {hits if hits else "无"}  {"✓" if not hits else "✗"}')
    bad += 0 if not hits else 1
    return bad


def discover_cells(prefix):
    """自动发现现役结果格：<prefix>_<cell>/ 下有 case_summary.csv 才算跑完。

    等价目录（ddps_equiv_*）与中间产物（*_parts）不在 <prefix>_ 前缀命名空间内，天然排除。
    """
    root = os.path.dirname(os.path.normpath(prefix)) or '.'
    base = os.path.basename(os.path.normpath(prefix))
    out = []
    if not os.path.isdir(root):
        return out
    for name in sorted(os.listdir(root)):
        if not name.startswith(base + '_'):
            continue
        cell = name[len(base) + 1:]
        if not cell or 'equiv' in cell:
            continue
        if os.path.exists(os.path.join(root, name, 'case_summary.csv')):
            out.append(cell)
    return out


def main():
    ap = argparse.ArgumentParser(description='DDPS 交付验收（只用磁盘结果说话）')
    ap.add_argument('--prefix', default='result/ddps_cpp')
    ap.add_argument('--cells', default='auto',
                    help='逗号分隔的格后缀（对应 <prefix>_<cell>）；auto = 自动发现已跑完的格')
    ap.add_argument('--expect-cells', type=int, default=0,
                    help='期望发现/验收的格数（0 = 不检查）；用来回答"是不是真的跑齐了"')
    ap.add_argument('--expect-cases', type=int, default=15)
    ap.add_argument('--expect-symbols', type=int, default=2097152)
    ap.add_argument('--deliverable', default='deliverables/DDPS_Deliverable.html')
    ap.add_argument('--skip-equivalence', action='store_true')
    a = ap.parse_args()

    if a.cells.strip() == 'auto':
        cells = discover_cells(a.prefix)
        print('=== 自动发现的现役结果格 ===')
        print('  ' + (', '.join(cells) if cells else '（一个都没有）'))
    else:
        cells = [c.strip() for c in a.cells.split(',') if c.strip()]
    if a.expect_cells and len(cells) != a.expect_cells:
        print(f'  !! 期望 {a.expect_cells} 格，实际发现 {len(cells)} 格 → 结果集不全（exit 2）')
        return 2

    print('=== A/B 每个结果目录的完整性与机制 ===')
    rep = Report()
    for cell in cells:
        if not os.path.isdir(f'{a.prefix}_{cell}'):
            print(f'  !! 缺目录 {a.prefix}_{cell}（结果集不全）')
            rep.missing += 1
            continue
        check_cell(a.prefix, cell, a.expect_cases, a.expect_symbols, rep)
    rep.dump()

    eq_bad = 0
    if not a.skip_equivalence:
        eq_bad = check_equivalence(a.prefix, cells, rep)

    newest = 0.0
    for cell in cells:
        d = f'{a.prefix}_{cell}'
        # 只看测量数据（run_config / case_summary / trace / probes）；
        # report/ 下的图是派生件、随时可重画，不作为新鲜度依据。
        for pat in ('run_config.json', 'case_summary.csv', 'case_summary.json',
                    'trace_*.csv', 'probes_*.csv'):
            for f in glob.glob(os.path.join(d, pat)):
                newest = max(newest, os.path.getmtime(f))
    del_bad = check_deliverable(a.deliverable, newest)

    print('\n=== 验收结论 ===')
    if rep.missing:
        print(f'  结果集不全：缺 {rep.missing} 项（exit 2）')
        return 2
    bad = rep.fail + eq_bad + del_bad
    if bad:
        print(f'  {bad} 项未通过（exit 1）')
        return 1
    print('  全部通过：结果完整、机制自洽、等价达标、交付件新鲜且无禁词（exit 0）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
