# -*- coding: utf-8 -*-
"""run_ddps_v2_control.py — DDPS v2 单环境训练对照（科学对照，非主结果）

在主报告之外回答方法论问题：如果训练数据只含基准环境 Base_IL10 邻域
（不含其它应力环境锚点），模型在 IL/CD/DGD 漂移环境下的 Stage-2 泛化衰减边界
在哪里？这是 AGENTS.md"控制变量法"要求的实验，主报告采用"混合环境锚定"模型。

用法:
  python run_ddps_v2_control.py --dataset <csv> --base-env Base_IL10 --out result/ddps_v2_control
"""
import os, json, sys
import argparse
import numpy as np
import pandas as pd
from train_surrogates import train_v2, load_models
from ddps_cases import ENV_CASES

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--dataset', required=True, help='v2 数据集 csv（含 env 列）')
    ap.add_argument('--base-env', default='Base_IL10')
    ap.add_argument('--model-dir', default='models/ddps_v2_control')
    ap.add_argument('--test-out', default='result/ddps_v2_control')
    ap.add_argument('--num-symbols', type=int, default=131072)
    a = ap.parse_args()

    df = pd.read_csv(a.dataset)
    sub = df[df['env'] == a.base_env].copy()
    os.makedirs('scratch', exist_ok=True)
    tmp = os.path.join('scratch', f"ddps_v2_{a.base_env}_only_control.csv")
    sub.to_csv(tmp, index=False)
    _, _, meta = train_v2(tmp, model_dir=a.model_dir)
    print(json.dumps({k: meta[k] for k in ('model_a', 'model_b')}, indent=1, default=float))

    import test_generalization as T
    T.run_generalization(a.model_dir, a.test_out, n_steps=25,
                         num_symbols=a.num_symbols, cloud_n=0)
