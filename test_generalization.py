import os
import json
import argparse
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from scipy.stats import qmc

# ============================================================================
# DDPS v3 泛化/在线调优测试（test_generalization.py）
#
# 方法论（控制变量法）：
#   - 模型在离线数据上训练并【固化】（不针对任何评估用例重新采样/重训）；
#   - 对每个物理应力环境（仅改单一/复合物理变量），直接复用同一组模型做
#     Stage-2 在线调优；真实 BER_MLSE 只记录、不参与方向决策（Stage-2 底线）；
#   - 输出：逐 case trace(csv) + 聚合表 + 每环境"局部有效性"记录（离线证据）。
#
# v3 相对 v2 的变化：
#   - 搜索空间 11 维：新增 driver_gain（Tx Driver 真实线性增益）；
#   - CTLE 位于 Tx 电插损之后、Driver 之前；
#   - 用例支持 Tx/Rx 插损非对称，并新增器件噪声用例；
#   - 真实 BER 评估支持多仿真种子取均值（--sim-seeds），抑制 BER 估计噪声。
# ============================================================================
import create_config, utils_config
import ddps_optimizer as D
from train_surrogates import load_models
from ddps_cases import ENV_CASES, apply_env_to_config


def local_validity_cloud(cfg, model_a, model_b, n=16, seed=11, spread_ffe=None,
                         spread_ctle=None):
    """在 seed 邻域做 LHS 云采样，衡量"真实 BER 排序/方向 vs 模型预测"的一致性。
    仅作离线证据记录，绝不回传给 Stage-2 决策。"""
    ffe_pre = int(cfg['tx'].get('ffe_pre', D.FFE_PRE))
    spread_ffe = spread_ffe or D.TRUST_FFE
    spread_ctle = spread_ctle or D.TRUST_CTLE
    seed_pre_post = np.concatenate([D.SEED_TAPS[:ffe_pre], D.SEED_TAPS[ffe_pre + 1:]])

    seed_lb, seed_ber = D._physical_eval(cfg, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2,
                                         D.SEED_GAIN)
    pa_seed = D._predict_a(model_a, cfg, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2, D.SEED_GAIN)
    pb_seed = D._predict_b(model_b, cfg, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2, D.SEED_GAIN)

    sampler = qmc.LatinHypercube(d=D.N_DIM, seed=seed)
    sp = sampler.random(n=n)
    real, pa, pb = [], [], []
    for i in range(n):
        pre_post = seed_pre_post + (sp[i, :D.N_SIDE] * 2 - 1.0) * spread_ffe
        gdc = float(np.clip(D.SEED_GDC + (sp[i, D.N_SIDE] * 2 - 1.0) * spread_ctle,
                            D.CTLE_GDC_MIN, D.CTLE_GDC_MAX))
        gdc2 = float(np.clip(D.SEED_GDC2 + (sp[i, D.N_SIDE + 1] * 2 - 1.0) * spread_ctle,
                             D.CTLE_GDC2_MIN, D.CTLE_GDC2_MAX))
        u_gain = float(D.GAIN_LOG10_MIN + sp[i, D.N_SIDE + 2] * (D.GAIN_LOG10_MAX - D.GAIN_LOG10_MIN))
        gain = D.gain_from_u(u_gain)
        taps = D.construct_taps(pre_post, ffe_pre)
        lb, _ = D._physical_eval(cfg, taps.copy(), gdc, gdc2, gain)
        real.append(lb)
        pa.append(D._predict_a(model_a, cfg, taps.copy(), gdc, gdc2, gain))
        pb.append(D._predict_b(model_b, cfg, taps.copy(), gdc, gdc2, gain))
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


def run_case(cfg, model_a, model_b, env, n_steps=25, cloud_n=0, freeze_extra=False,
             cloud_symbols=None, cloud_sim_seeds=None):
    """对单一环境运行完整 Stage-2 在线调优。真实 BER 仅记录。

    freeze_extra=True 时把 CTLE 两维与 driver_gain 冻结在种子值（只优化 FFE），
    用于量化"新增维度到底贡献了多少"。
    """
    ffe_pre = int(cfg['tx'].get('ffe_pre', D.FFE_PRE))
    x0 = D._taps_to_x(D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2, D.SEED_GAIN, ffe_pre)
    safety_ref = D._predict_b(model_b, cfg, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2, D.SEED_GAIN)
    seed_lb, seed_ber = D._physical_eval(cfg, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2,
                                         D.SEED_GAIN)
    pa_seed = D._predict_a(model_a, cfg, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2, D.SEED_GAIN)
    pb_seed = D._predict_b(model_b, cfg, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2, D.SEED_GAIN)

    trace = D._stage2_descent(cfg, model_a, model_b, x0, ffe_pre, n_steps,
                              safety_ref, D.GD_LR, np.random.RandomState(42),
                              freeze_extra=freeze_extra)

    rows = []
    if trace:
        for t in trace:
            rows.append({
                'step': t['step'], 'x': np.asarray(t['x']).tolist(),
                'taps': np.round(np.asarray(t['taps']), 6).tolist(),
                'gdc': t['gdc'], 'gdc2': t['gdc2'], 'gain': t['gain'],
                'gain_ratio': t['gain'] / D.DRIVER_GAIN_NOMINAL,
                'pred_b_ber': t.get('pred_b_ber'), 'allowed_ber': t.get('allowed_ber'),
                'stop_reason': t.get('stop_reason', ''),
                'pred_a': t['pred_a'], 'pred_b': t['pred_b'],
                'real_lb': t['real_logber'], 'real_ber': t['real_mlse'],
                'grad_norm': t['grad_norm'],
            })
    real_lb_t = np.array([r['real_lb'] for r in rows]) if rows else np.array([])

    # 云校验（离线证据，不参与决策）。可用更便宜的协议（更短块长 / 更少种子）单独评估，
    # 避免"每环境 16 点 × 主协议"把运行时间推高一个量级。
    cloud = None
    if cloud_n > 0:
        saved_seeds = D.SIM_SEEDS
        saved_nsym = cfg['system'].get('num_symbols')
        try:
            if cloud_sim_seeds is not None:
                D.set_sim_seeds(cloud_sim_seeds)
            if cloud_symbols is not None:
                cfg['system']['num_symbols'] = int(cloud_symbols)
            cloud = local_validity_cloud(cfg, model_a, model_b, n=cloud_n)
        finally:
            D.set_sim_seeds(saved_seeds)
            if saved_nsym is not None:
                cfg['system']['num_symbols'] = saved_nsym

    result = {
        'env': env['name'], 'il_tx': env['il_tx'], 'il_rx': env['il_rx'],
        'cd': env['cd'], 'dgd': env['dgd'], 'pol': env['pol'],
        'noise_stress': bool(env.get('stress')),
        'seed_lb': float(seed_lb), 'seed_ber': float(seed_ber),
        'pa_seed': float(pa_seed), 'pb_seed': float(pb_seed),
        'n_steps_requested': n_steps,
        'n_steps_actual': len(rows),
        'freeze_extra': bool(freeze_extra),
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
            'best_gdc2': rows[ibest]['gdc2'], 'best_gain': rows[ibest]['gain'],
            'best_gain_ratio': rows[ibest]['gain'] / D.DRIVER_GAIN_NOMINAL,
            'seed_gain': float(D.SEED_GAIN), 'seed_gain_ratio': 1.0,
            'stop_reason': rows[-1].get('stop_reason', ''),
            'early_stop': len(rows) < n_steps,
        })
    else:
        # 没有任何一步被接受（例如梯度门控在第 0 步就触发）：用种子值补齐字段，
        # 保证下游报告/汇总不会因缺列而崩。
        result.update({
            'best_lb': float(seed_lb), 'best_ber': float(seed_ber), 'best_step': -1,
            'final_lb': float(seed_lb), 'final_ber': float(seed_ber),
            'max_lb': float(seed_lb),
            'delta_lb_seed_to_best': 0.0, 'delta_lb_seed_to_final': 0.0,
            'trace_spearman_preda_real': float('nan'),
            'trace_spearman_predb_real': float('nan'),
            'best_taps': D.SEED_TAPS.tolist(), 'best_gdc': float(D.SEED_GDC),
            'best_gdc2': float(D.SEED_GDC2), 'best_gain': float(D.SEED_GAIN),
            'best_gain_ratio': 1.0,
            'seed_gain': float(D.SEED_GAIN), 'seed_gain_ratio': 1.0,
            'stop_reason': 'no_step_accepted', 'early_stop': True,
        })
    result['cloud'] = cloud
    return result, rows


def run_generalization(model_dir, out_dir, n_steps=25, num_symbols=131072,
                       cloud_n=0, validity_envs=None, sim_seeds=(42,),
                       freeze_extra=False, only_envs=None,
                       cloud_symbols=65536, cloud_sim_seeds=(42, 43)):
    # 只在缺失时生成配置：config.xlsx 是受版本管理的唯一配置源，多进程并发重写会造成
    # 文件损坏竞态（实测三进程同时 generate_config() 会把 xlsx 写坏）。
    if not os.path.exists('config.xlsx'):
        create_config.generate_config()
    model_a, model_b = load_models(model_dir)
    try:
        with open(os.path.join(model_dir, 'meta.json'), encoding='utf-8') as f:
            meta = json.load(f)
    except Exception:
        meta = {}

    D.set_sim_seeds(sim_seeds)
    print(f"[test v3] models from {model_dir} | num_symbols={num_symbols} | "
          f"n_steps={n_steps} | cloud_n={cloud_n} | sim_seeds={tuple(sim_seeds)} | "
          f"freeze_extra={freeze_extra}")
    print(f"          cloud protocol: {cloud_symbols} symbols x seeds {tuple(cloud_sim_seeds)}")

    os.makedirs(out_dir, exist_ok=True)
    results, trace_dfs = [], {}

    cases = [e for e in ENV_CASES if (only_envs is None or e['name'] in only_envs)]
    for env in cases:
        print(f"\n--- Stage-2 online tuning: {env['name']} ---")
        base_cfg = utils_config.load_config('config.xlsx')
        cfg = apply_env_to_config(base_cfg, env)
        cfg['system']['num_symbols'] = int(num_symbols)
        if cloud_n > 0 and (validity_envs is None or env['name'] in validity_envs):
            c = cloud_n
        else:
            c = 0
        res, rows = run_case(cfg, model_a, model_b, env, n_steps=n_steps, cloud_n=c,
                             freeze_extra=freeze_extra, cloud_symbols=cloud_symbols,
                             cloud_sim_seeds=cloud_sim_seeds)
        results.append(res)
        df = pd.DataFrame(rows) if rows else pd.DataFrame()
        if not df.empty:
            df.insert(0, 'env', env['name'])
        trace_dfs[env['name']] = df
        tag = ('+' if res.get('delta_lb_seed_to_best', 0) < -0.01 else
               ('~' if abs(res.get('delta_lb_seed_to_best', 0)) <= 0.01 else '-'))
        print(f"    seed BER_MLSE={res['seed_ber']:.3e} | "
              f"best={res.get('best_ber', np.nan):.3e} "
              f"(step {res.get('best_step', 'NA')}, gain {res.get('best_gain', float('nan')):.3f}) | "
              f"final={res.get('final_ber', np.nan):.3e} | {tag}")

    out = pd.DataFrame(results)
    out.to_json(os.path.join(out_dir, 'case_summary.json'), orient='records', indent=2)
    out.to_csv(os.path.join(out_dir, 'case_summary.csv'), index=False)
    for name, df in trace_dfs.items():
        safe = name.replace(' ', '_').replace('(', '').replace(')', '')
        df.to_csv(os.path.join(out_dir, f'trace_{safe}.csv'), index=False)
    with open(os.path.join(out_dir, 'model_meta_snapshot.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False, default=str)
    with open(os.path.join(out_dir, 'run_config.json'), 'w', encoding='utf-8') as f:
        json.dump({'model_dir': model_dir, 'n_steps': n_steps, 'num_symbols': int(num_symbols),
                   'cloud_n': cloud_n, 'sim_seeds': list(sim_seeds),
                   'cloud_symbols': int(cloud_symbols),
                   'cloud_sim_seeds': list(cloud_sim_seeds),
                   'freeze_extra': bool(freeze_extra),
                   'envs': [e['name'] for e in cases]},
                  f, indent=2, ensure_ascii=False)
    print(f"\n[test v3] done -> {out_dir}/case_summary.csv")

    return out_dir


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument('--model-dir', default='models/ddps_v3', help='Frozen model dir')
    ap.add_argument('--out-dir', default='result/ddps_v3')
    ap.add_argument('--n-steps', type=int, default=25)
    ap.add_argument('--num-symbols', type=int, default=262144)
    ap.add_argument('--cloud-n', type=int, default=16,
                    help='每环境种子邻域云校验点数(0=关, 仅离线证据)')
    ap.add_argument('--sim-seeds', type=str, default='42,43,44',
                    help='逗号分隔的仿真种子序列（多seed取log10 BER均值）')
    ap.add_argument('--cloud-symbols', type=int, default=65536,
                    help='云校验专用块长（比主协议便宜，仅作离线证据）')
    ap.add_argument('--cloud-sim-seeds', type=str, default='42,43')
    ap.add_argument('--freeze-extra', action='store_true',
                    help='冻结 CTLE 与 driver_gain（只优化 FFE），用于消融对比')
    ap.add_argument('--only-envs', type=str, default=None, help='仅跑指定环境（逗号分隔）')
    a = ap.parse_args()
    sim_seeds = tuple(int(s) for s in str(a.sim_seeds).split(',') if s.strip())
    cloud_seeds = tuple(int(s) for s in str(a.cloud_sim_seeds).split(',') if s.strip())
    only = tuple(s.strip() for s in a.only_envs.split(',')) if a.only_envs else None
    run_generalization(a.model_dir, a.out_dir, n_steps=a.n_steps,
                       num_symbols=a.num_symbols, cloud_n=a.cloud_n,
                       sim_seeds=sim_seeds, freeze_extra=a.freeze_extra,
                       only_envs=only, cloud_symbols=a.cloud_symbols,
                       cloud_sim_seeds=cloud_seeds)
