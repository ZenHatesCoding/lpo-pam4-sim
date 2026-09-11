# -*- coding: utf-8 -*-
"""tools/merge_test_parts.py — 把分片并行跑出来的 test_generalization 结果合并成一个结果目录。

多进程并行时每个分片只写自己那部分用例；本工具按 ENV_CASES 的规范顺序合并
case_summary.csv / trace_*.csv，并沿用第一个分片的 run_config.json 与模型快照。

用法：
    python tools/merge_test_parts.py --out result/ddps_v4_main \
        result/_parts/main_a result/_parts/main_b result/_parts/main_c
"""
import argparse
import json
import os
import shutil
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ddps_cases import ENV_CASES  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('parts', nargs='+', help='分片结果目录（按任意顺序）')
    ap.add_argument('--out', required=True, help='合并输出目录')
    args = ap.parse_args()

    frames, traces = [], {}
    for d in args.parts:
        p = os.path.join(d, 'case_summary.csv')
        if not os.path.exists(p):
            raise SystemExit(f'缺少 {p}')
        frames.append(pd.read_csv(p))
        for f in os.listdir(d):
            if f.startswith('trace_') and f.endswith('.csv'):
                traces[f] = os.path.join(d, f)

    summ = pd.concat(frames, ignore_index=True)
    order = {e['name']: i for i, e in enumerate(ENV_CASES)}
    summ['__o'] = summ['env'].map(lambda x: order.get(x, 999))
    summ = summ.sort_values('__o').drop(columns='__o').reset_index(drop=True)

    os.makedirs(args.out, exist_ok=True)
    summ.to_csv(os.path.join(args.out, 'case_summary.csv'), index=False)
    summ.to_json(os.path.join(args.out, 'case_summary.json'), orient='records', indent=2)
    for name, src in sorted(traces.items()):
        shutil.copyfile(src, os.path.join(args.out, name))
    first = args.parts[0]
    for f in ('run_config.json', 'model_meta_snapshot.json'):
        s = os.path.join(first, f)
        if os.path.exists(s):
            shutil.copyfile(s, os.path.join(args.out, f))
    # 汇总 run_config 里记录全部用例
    rc = os.path.join(args.out, 'run_config.json')
    if os.path.exists(rc):
        with open(rc, encoding='utf-8') as fh:
            cfg = json.load(fh)
        cfg['envs'] = list(summ['env'])
        cfg['merged_from'] = list(args.parts)
        with open(rc, 'w', encoding='utf-8') as fh:
            json.dump(cfg, fh, indent=2, ensure_ascii=False)
    print(f'[merge] {len(summ)} cases from {len(args.parts)} parts -> {args.out}')
    print(summ[['env', 'seed_ber', 'best_ber', 'delta_lb_seed_to_best', 'best_step',
                'best_gain_ratio', 'n_steps_actual']].to_string(index=False))


if __name__ == '__main__':
    main()
