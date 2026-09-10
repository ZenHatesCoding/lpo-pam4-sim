# -*- coding: utf-8 -*-
"""run_ddps_v3_control.py — DDPS v3 单环境训练对照（科学对照：只用基线训练）

回答方法论问题：如果训练数据**只含基准环境**（不含其它应力环境锚点），冻结模型在
非对称插损 / 色散 / 群时延 / 噪声漂移环境下的 Stage-2 泛化边界在哪里？
这是"控制变量法"要求的核心实验（严格泛化），另有含锚点的版本作为上限参考。

用法:
  python run_ddps_v3_control.py --dataset dataset/ddps_v3_dataset_<ts>.csv \
      --base-env Base_IL10x10 --out result/ddps_v3_control \
      --model-dir models/ddps_v3_control --num-symbols 262144 --sim-seeds 42,43
"""
import os, json, sys
import argparse
import numpy as np
import pandas as pd
from train_surrogates import train_v3

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--dataset', required=True, help='v3 数据集 csv（含 env 列）')
    ap.add_argument('--base-env', default='Base_IL10x10')
    ap.add_argument('--model-dir', default='models/ddps_v3_control')
    ap.add_argument('--test-out', default='result/ddps_v3_control')
    ap.add_argument('--num-symbols', type=int, default=131072)
    ap.add_argument('--sim-seeds', type=str, default='42')
    ap.add_argument('--n-steps', type=int, default=25)
    ap.add_argument('--cloud-n', type=int, default=16)
    a = ap.parse_args()

    df = pd.read_csv(a.dataset)
    sub = df[df['env'] == a.base_env].copy()
    os.makedirs('scratch', exist_ok=True)
    tmp = os.path.join('scratch', f"ddps_v3_{a.base_env}_only_control.csv")
    sub.to_csv(tmp, index=False)
    print(f"[control] 只用基线环境 {a.base_env}: {len(sub)} 行 -> {tmp}")

    _, _, meta = train_v3(tmp, model_dir=a.model_dir)
    print(json.dumps({k: meta[k] for k in ('model_a', 'model_b')}, indent=1, default=float))

    import test_generalization as T
    sim_seeds = tuple(int(s) for s in str(a.sim_seeds).split(',') if s.strip())
    T.run_generalization(a.model_dir, a.test_out, n_steps=a.n_steps,
                         num_symbols=a.num_symbols, cloud_n=a.cloud_n,
                         sim_seeds=sim_seeds)
