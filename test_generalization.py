import os
import json
import argparse
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from scipy.stats import qmc

# ============================================================================
# DDPS v2 泛化/在线调优测试（test_generalization.py）
#
# 方法论（遵循 AGENTS.md 控制变量法）：
#   - 模型在离线数据上训练并【固化】（不针对任何评估用例重新采样/重训）；
#   - 对每个物理应力环境（仅改单一/复合物理变量），直接复用同一组模型做
#     Stage-2 在线调优；真实 BER_MLSE 只记录、不参与方向决策（Stage-2 底线）；
#   - 输出：逐 case trace(json/csv) + 聚合表 + 每环境"局部有效性"记录
#     （方向/排序真实性为离线证据，不喂给在线算法）。
#
# v2 相对 v1 的修正（均已落进 ddps_optimizer / tx_channel_extract / 数据管线）：
#   - FFE 参数化统一 + Stage-1 邻域采样 d=10 修复；
#   - FIR 探针符号格按环境对齐（修复跨 IL 峰值漂移导致的 OOD 特征）；
#   - Stage-2 梯度门控（代理曲面趋平即停，杜绝负向乱走）。
# ============================================================================
import create_config, utils_config
import ddps_optimizer as D
from train_surrogates import load_models
from ddps_cases import ENV_CASES, apply_env_to_config


def local_validity_cloud(cfg, model_a, model_b, n=24, seed=11, spread_ffe=None,
                         spread_ctle=None):
    """在 seed 邻域做 LHS 云采样，衡量"真实 BER 排序/方向 vs 模型预测"的一致性。
    仅作离线证据记录，绝不回传给 Stage-2 决策。"""
    ffe_pre = int(cfg['tx'].get('ffe_pre', 4))
    spread_ffe = spread_ffe or D.TRUST_FFE
    spread_ctle = spread_ctle or D.TRUST_CTLE
    seed_pre_post = np.zeros(8)
    seed_pre_post[:ffe_pre] = D.SEED_TAPS[:ffe_pre]
    seed_pre_post[ffe_pre:] = D.SEED_TAPS[ffe_pre + 1:]

    seed_lb, seed_ber = D._physical_eval(cfg, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2)
    pa_seed = D._predict_a(model_a, cfg, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2)
    pb_seed = D._predict_b(model_b, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2)

    sampler = qmc.LatinHypercube(d=10, seed=seed)
    sp = sampler.random(n=n)
    real, pa, pb = [], [], []
    for i in range(n):
        pre_post = seed_pre_post + (sp[i, :8] * 2 - 1.0) * spread_ffe
        gdc = float(np.clip(D.SEED_GDC + (sp[i, 8] * 2 - 1.0) * spread_ctle,
                            D.CTLE_GDC_MIN, D.CTLE_GDC_MAX))
        gdc2 = float(np.clip(D.SEED_GDC2 + (sp[i, 9] * 2 - 1.0) * spread_ctle,
                             D.CTLE_GDC2_MIN, D.CTLE_GDC2_MAX))
        taps = D.construct_9tap(pre_post, ffe_pre)
        lb, _ = D._physical_eval(cfg, taps.copy(), gdc, gdc2)
        real.append(lb)
        pa.append(D._predict_a(model_a, cfg, taps.copy(), gdc, gdc2))
        pb.append(D._predict_b(model_b, taps.copy(), gdc, gdc2))
    real = np.array(real); pa = np.array(pa); pb = np.array(pb)

    d_real = real - seed_lb
    dA = pa - pa_seed
    dB = pb - pb_seed
    big = np.abs(d_real) > 0.05
    agree_a = float(np.mean(np.sign(dA[big]) == np.sign(d_real[big]))) if big.sum() else np.nan
    agree_b = float(np.mean(np.sign(dB[big]) == np.sign(d_real[big]))) if big.sum() else np.nan
    return {
        'n': n,
        'seed_lb': float(seed_lb), 'seed_ber': float(seed_ber),
        'real_lb_min': float(real.min()), 'real_lb_max': float(real.max()),
        'spearman_real_va': float(spearmanr(real, pa).correlation),
        'spearman_real_vb': float(spearmanr(real, pb).correlation),
        'agree_a': agree_a, 'agree_b': agree_b,
        'n_better_than_seed': int((real < seed_lb - 0.02).sum()),
    }


def run_case(cfg, model_a, model_b, env, n_steps=25, cloud_n=0):
    """对单一环境运行完整 Stage-2 在线调优。真实 BER 仅记录。"""
    ffe_pre = int(cfg['tx'].get('ffe_pre', 4))
    x0 = D._taps_to_x(D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2, ffe_pre)
    safety_ref = D._predict_b(model_b, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2)
    seed_lb, seed_ber = D._physical_eval(cfg, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2)
    pa_seed = D._predict_a(model_a, cfg, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2)
    pb_seed = D._predict_b(model_b, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2)

    trace = D._stage2_descent(cfg, model_a, model_b, x0, ffe_pre, n_steps,
                              safety_ref, D.GD_LR, np.random.RandomState(42))

    rows = []
    if trace:
        for t in trace:
            rows.append({
                'step': t['step'], 'x': np.asarray(t['x']).tolist(),
                'taps': np.round(np.asarray(t['taps']), 6).tolist(),
                'gdc': t['gdc'], 'gdc2': t['gdc2'],
                'pred_a': t['pred_a'], 'pred_b': t['pred_b'],
                'real_lb': t['real_logber'], 'real_ber': t['real_mlse'],
                'grad_norm': t['grad_norm'],
            })
    real_lb_t = np.array([r['real_lb'] for r in rows]) if rows else np.array([])

    # 云校验（离线证据，不参与决策）
    cloud = None
    if cloud_n > 0:
        cloud = local_validity_cloud(cfg, model_a, model_b, n=cloud_n)

    result = {
        'env': env['name'], 'il': env['il'], 'cd': env['cd'], 'dgd': env['dgd'],
        'pol': env['pol'],
        'seed_lb': float(seed_lb), 'seed_ber': float(seed_ber),
        'pa_seed': float(pa_seed), 'pb_seed': float(pb_seed),
        'n_steps_requested': n_steps,
        'n_steps_actual': len(rows),
    }
    if rows:
        ibest = int(np.argmin(real_lb_t))
        result.update({
            'best_lb': float(real_lb_t[ibest]),
            'best_ber': float(rows[ibest]['real_ber']),
            'best_step': int(rows[ibest]['step']),
            'final_lb': float(real_lb_t[-1]), 'final_ber': float(rows[-1]['real_ber']),
            'max_lb': float(real_lb_t.max()),
            'delta_lb_seed_to_best': float(real_lb_t[ibest] - seed_lb),
            'delta_lb_seed_to_final': float(real_lb_t[-1] - seed_lb),
            'trace_spearman_preda_real': float(
                spearmanr([r['pred_a'] for r in rows], real_lb_t).correlation),
            'trace_spearman_predb_real': float(
                spearmanr([r['pred_b'] for r in rows], real_lb_t).correlation),
            'best_taps': rows[ibest]['taps'], 'best_gdc': rows[ibest]['gdc'],
            'best_gdc2': rows[ibest]['gdc2'],
            'early_stop': len(rows) < n_steps,
        })
    result['cloud'] = cloud
    return result, rows


def run_generalization(model_dir, out_dir, n_steps=25, num_symbols=131072,
                       cloud_n=0, validity_envs=None):
    create_config.generate_config()
    model_a, model_b = load_models(model_dir)
    try:
        with open(os.path.join(model_dir, 'meta.json'), encoding='utf-8') as f:
            meta = json.load(f)
    except Exception:
        meta = {}
    print(f"[test v2] models from {model_dir} | num_symbols={num_symbols} | "
          f"n_steps={n_steps} | cloud_n={cloud_n}")

    os.makedirs(out_dir, exist_ok=True)
    results, trace_dfs = [], {}

    for env in ENV_CASES:
        print(f"\n--- Stage-2 online tuning: {env['name']} ---")
        base_cfg = utils_config.load_config('config.xlsx')
        cfg = apply_env_to_config(base_cfg, env)
        cfg['system']['num_symbols'] = int(num_symbols)
        if cloud_n > 0 and (validity_envs is None or env['name'] in validity_envs):
            c = cloud_n
        else:
            c = 0
        res, rows = run_case(cfg, model_a, model_b, env, n_steps=n_steps, cloud_n=c)
        results.append(res)
        df = pd.DataFrame(rows) if rows else pd.DataFrame()
        df.insert(0, 'env', env['name'])
        trace_dfs[env['name']] = df
        tag = ('+' if res.get('delta_lb_seed_to_best', 0) < -0.01 else
               ('~' if abs(res.get('delta_lb_seed_to_best', 0)) <= 0.01 else '-'))
        print(f"    seed BER_MLSE={res['seed_ber']:.3e} | "
              f"best={res.get('best_ber', np.nan):.3e} "
              f"(step {res.get('best_step', 'NA')}) | "
              f"final={res.get('final_ber', np.nan):.3e} | {tag}")

    out = pd.DataFrame(results)
    out.to_json(os.path.join(out_dir, 'case_summary.json'), orient='records', indent=2)
    out.to_csv(os.path.join(out_dir, 'case_summary.csv'), index=False)
    for name, df in trace_dfs.items():
        safe = name.replace(' ', '_').replace('(', '').replace(')', '')
        df.to_csv(os.path.join(out_dir, f'trace_{safe}.csv'), index=False)
    with open(os.path.join(out_dir, 'model_meta_snapshot.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n[test v2] done -> {out_dir}/case_summary.csv")

    return out_dir


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument('--model-dir', default='models/ddps_v2', help='Frozen model dir')
    ap.add_argument('--out-dir', default='result/ddps_v2')
    ap.add_argument('--n-steps', type=int, default=25)
    ap.add_argument('--num-symbols', type=int, default=131072)
    ap.add_argument('--cloud-n', type=int, default=16,
                    help='每环境种子邻域云校验点数(0=关, 仅离线证据)')
    a = ap.parse_args()
    run_generalization(a.model_dir, a.out_dir, n_steps=a.n_steps,
                       num_symbols=a.num_symbols, cloud_n=a.cloud_n)
