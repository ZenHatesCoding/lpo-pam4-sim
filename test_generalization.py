import os
import json
import argparse
import numpy as np
import pandas as pd

# ============================================================================
# DDPS 泛化/在线调优测试（test_generalization.py）
#
# 方法论（控制变量法）：
#   - 模型在离线数据上训练并【固化】（不针对任何评估用例重新采样/重训）；
#   - 对每个物理应力环境（仅改单一/复合物理变量），直接复用同一组模型做
#     Stage-2 在线调优；真实 BER_MLSE 只记录、不参与方向决策（Stage-2 底线）；
#   - 输出：逐 case trace(csv) + 聚合表 + model_meta_snapshot + run_config。
#
# 搜索空间：7 维（4 FFE 旁瓣 + gDC + gDC2 + u_gain）。
#   gain 初值 = 每个用例 per-case RMS 扫描最优 gain（per_case_gain），之后放开走梯度。
# ============================================================================
import utils_config
import ddps_optimizer as D
from train_surrogates import load_models
from ddps_cases import ENV_CASES, apply_env_to_config

# 种子点 gain 覆盖（配合 --seed-config）：非 None 时，gain 初值用它替代 per-case RMS 扫描值，
# 从而支持从一个"次优工作点"（形状 + gain 全部给定）出发做在线调优演示。
SEED_GAIN_OVERRIDE = None


def run_case(cfg, model_a, model_b, env, n_steps=25, per_case_gain=None):
    """在线调优（含 Model B 安全拦截）：7 维梯度下降（4 FFE 旁瓣 + gDC + gDC2 + u_gain）。

    gain 初值 = 该 case per-case RMS 扫描最优 gain（per_case_gain），之后放开走梯度。
    """
    ffe_pre = int(cfg['tx'].get('ffe_pre', D.FFE_PRE))
    seed_pre_post = np.concatenate([D.SEED_TAPS[:ffe_pre], D.SEED_TAPS[ffe_pre + 1:]])
    gain0 = float(per_case_gain) if per_case_gain is not None else float(D.SEED_GAIN)
    x0 = np.concatenate([seed_pre_post, [D.SEED_GDC, D.SEED_GDC2, D.u_from_gain(gain0)]])

    seed_lb, seed_ber = D._physical_eval(cfg, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2, gain0)
    taps_seed = D.construct_taps(x0[:D.N_SIDE], ffe_pre)
    probe_seed = D._probe_features(cfg, taps_seed, float(x0[D.N_SIDE]),
                                   float(x0[D.N_SIDE + 1]), gain0)
    pa_seed = D._predict_a_probe(model_a, probe_seed)
    rms_seed = D._measure_drive_rms(cfg, taps_seed, float(x0[D.N_SIDE]),
                                     float(x0[D.N_SIDE + 1]), gain0)
    pb_seed = D._predict_b_params(model_b, x0[:D.N_SIDE + 2], rms_seed)

    trace = D._stage2_descent(cfg, model_a, model_b, x0, ffe_pre, n_steps, D.GD_LR)

    rows = []
    if trace:
        for t in trace:
            rows.append({
                'step': t['step'], 'x': np.asarray(t['x']).tolist(),
                'taps': np.round(np.asarray(t['taps']), 6).tolist(),
                'gdc': t['gdc'], 'gdc2': t['gdc2'], 'gain': t['gain'],
                'gain_ratio': t['gain'] / D.DRIVER_GAIN_NOMINAL,
                'u_gain': t.get('u_gain'),
                'drive_rms': t.get('drive_rms'),
                'pred_b_ber': t.get('pred_b_ber'), 'allowed_ber': t.get('allowed_ber'),
                'stop_reason': t.get('stop_reason', ''),
                'pred_a': t['pred_a'], 'pred_b': t['pred_b'],
                'real_lb': t['real_logber'], 'real_ber': t['real_mlse'],
                'grad_norm': t['grad_norm'],
            })
    real_lb_t = np.array([r['real_lb'] for r in rows]) if rows else np.array([])

    result = {
        'env': env['name'], 'il_tx': env['il_tx'], 'il_rx': env['il_rx'],
        'cd': env['cd'], 'dgd': env['dgd'], 'pol': env['pol'],
        'noise_stress': bool(env.get('stress')),
        'seed_lb': float(seed_lb), 'seed_ber': float(seed_ber),
        'pa_seed': float(pa_seed), 'pb_seed': float(pb_seed),
        'n_steps_requested': n_steps,
        'n_steps_actual': len(rows),
        'freeze_extra': False,
        'seed_gain': float(gain0),
        'seed_gain_ratio': float(gain0 / D.DRIVER_GAIN_NOMINAL),
        'cloud': None,
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
            'best_taps': rows[ibest]['taps'], 'best_gdc': rows[ibest]['gdc'],
            'best_gdc2': rows[ibest]['gdc2'], 'best_gain': rows[ibest]['gain'],
            'best_gain_ratio': rows[ibest]['gain'] / D.DRIVER_GAIN_NOMINAL,
            'best_u_gain': rows[ibest].get('u_gain'),
            'stop_reason': rows[-1].get('stop_reason', ''),
            'early_stop': len(rows) < n_steps,
        })
    else:
        result.update({
            'best_lb': float(seed_lb), 'best_ber': float(seed_ber), 'best_step': -1,
            'final_lb': float(seed_lb), 'final_ber': float(seed_ber),
            'max_lb': float(seed_lb),
            'delta_lb_seed_to_best': 0.0, 'delta_lb_seed_to_final': 0.0,
            'best_taps': D.SEED_TAPS.tolist(), 'best_gdc': float(D.SEED_GDC),
            'best_gdc2': float(D.SEED_GDC2), 'best_gain': float(gain0),
            'best_gain_ratio': float(gain0 / D.DRIVER_GAIN_NOMINAL),
            'best_u_gain': float(D.u_from_gain(gain0)),
            'stop_reason': 'no_trace', 'early_stop': True,
        })
    return result, rows


def run_case_aonly(cfg, model_a, env, n_steps=25, per_case_gain=None):
    """A-only：只用 Model A 七维链式梯度，不查 Model B、不走安全拦截。"""
    ffe_pre = int(cfg['tx'].get('ffe_pre', D.FFE_PRE))
    seed_pre_post = np.concatenate([D.SEED_TAPS[:ffe_pre], D.SEED_TAPS[ffe_pre + 1:]])
    gain0 = float(per_case_gain) if per_case_gain is not None else float(D.SEED_GAIN)
    x0 = np.concatenate([seed_pre_post, [D.SEED_GDC, D.SEED_GDC2, D.u_from_gain(gain0)]])

    seed_lb, seed_ber = D._physical_eval(cfg, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2, gain0)
    taps_seed = D.construct_taps(x0[:D.N_SIDE], ffe_pre)
    probe_seed = D._probe_features(cfg, taps_seed, float(x0[D.N_SIDE]),
                                   float(x0[D.N_SIDE + 1]), gain0)
    pa_seed = D._predict_a_probe(model_a, probe_seed)

    trace = D._stage2_descent_aonly(cfg, model_a, x0, ffe_pre, n_steps, D.GD_LR)

    rows = []
    if trace:
        for t in trace:
            rows.append({
                'step': t['step'], 'x': np.asarray(t['x']).tolist(),
                'taps': np.round(np.asarray(t['taps']), 6).tolist(),
                'gdc': t['gdc'], 'gdc2': t['gdc2'], 'gain': t['gain'],
                'gain_ratio': t['gain'] / D.DRIVER_GAIN_NOMINAL,
                'u_gain': t.get('u_gain'),
                'drive_rms': t.get('drive_rms'),
                'pred_b_ber': 0.0, 'allowed_ber': 0.0,
                'stop_reason': t.get('stop_reason', ''),
                'pred_a': t['pred_a'], 'pred_b': 0.0,
                'real_lb': t['real_logber'], 'real_ber': t['real_mlse'],
                'grad_norm': t['grad_norm'],
            })
    real_lb_t = np.array([r['real_lb'] for r in rows]) if rows else np.array([])

    result = {
        'env': env['name'], 'il_tx': env['il_tx'], 'il_rx': env['il_rx'],
        'cd': env['cd'], 'dgd': env['dgd'], 'pol': env['pol'],
        'noise_stress': bool(env.get('stress')),
        'seed_lb': float(seed_lb), 'seed_ber': float(seed_ber),
        'pa_seed': float(pa_seed), 'pb_seed': 0.0,
        'n_steps_requested': n_steps,
        'n_steps_actual': len(rows),
        'freeze_extra': False,
        'seed_gain': float(gain0),
        'seed_gain_ratio': float(gain0 / D.DRIVER_GAIN_NOMINAL),
        'cloud': None,
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
            'best_taps': rows[ibest]['taps'], 'best_gdc': rows[ibest]['gdc'],
            'best_gdc2': rows[ibest]['gdc2'], 'best_gain': rows[ibest]['gain'],
            'best_gain_ratio': rows[ibest]['gain'] / D.DRIVER_GAIN_NOMINAL,
            'best_u_gain': rows[ibest].get('u_gain'),
            'stop_reason': rows[-1].get('stop_reason', ''),
            'early_stop': len(rows) < n_steps,
        })
    else:
        result.update({
            'best_lb': float(seed_lb), 'best_ber': float(seed_ber), 'best_step': -1,
            'final_lb': float(seed_lb), 'final_ber': float(seed_ber),
            'max_lb': float(seed_lb),
            'delta_lb_seed_to_best': 0.0, 'delta_lb_seed_to_final': 0.0,
            'best_taps': D.SEED_TAPS.tolist(), 'best_gdc': float(D.SEED_GDC),
            'best_gdc2': float(D.SEED_GDC2), 'best_gain': float(gain0),
            'best_gain_ratio': float(gain0 / D.DRIVER_GAIN_NOMINAL),
            'best_u_gain': float(D.u_from_gain(gain0)),
            'stop_reason': 'no_trace', 'early_stop': True,
        })
    return result, rows


def run_generalization(model_dir, out_dir, n_steps=25, num_symbols=131072,
                       sim_seeds=(42,), only_envs=None, a_only=False,
                       per_case_rms_path=None):
    # config.xlsx 由主进程入口（__main__ / run_parallel_envs）在 spawn worker 前统一
    # 生成/校验；此处只 load_config 只读，绝不在 worker 里就地生成（避免多进程写坏 xlsx）。
    model_a, model_b = load_models(model_dir)
    try:
        with open(os.path.join(model_dir, 'meta.json'), encoding='utf-8') as f:
            meta = json.load(f)
    except Exception:
        meta = {}

    D.set_sim_seeds(sim_seeds)
    tag = 'aonly' if a_only else 'main'

    # per-case gain：每个用例单独扫描标定的最优 gain（作为该用例 gain 初值）。
    per_case_rms = {}
    path = per_case_rms_path or 'result/per_case_target_rms.json'
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            per_case_rms = json.load(f)
        print(f"[test {tag}] per-case target_rms loaded from {path} ({len(per_case_rms)} envs)")
    else:
        print(f"[test {tag}] WARNING: {path} not found, falling back to seed gain")

    print(f"[test {tag}] models from {model_dir} | num_symbols={num_symbols} | "
          f"n_steps={n_steps} | sim_seeds={tuple(sim_seeds)}")

    os.makedirs(out_dir, exist_ok=True)
    results, trace_dfs = [], {}
    # 每个用例本跑实际用于初始化的 gain。给了 --seed-config 的 gain 覆盖时所有用例 = 覆盖值；
    # 否则 = per-case RMS 扫描解析出的最优 gain。用于如实写进 run_config.json（与种子点一致）。
    seed_gain_per_case = {}

    cases = [e for e in ENV_CASES if (only_envs is None or e['name'] in only_envs)]
    for env in cases:
        print(f"\n--- Stage-2 online tuning ({tag}): {env['name']} ---")
        base_cfg = utils_config.load_config('config.xlsx')
        cfg = apply_env_to_config(base_cfg, env)
        cfg['system']['num_symbols'] = int(num_symbols)
        case_gain = None
        if SEED_GAIN_OVERRIDE is not None:
            case_gain = SEED_GAIN_OVERRIDE
            print(f"          seed-config gain override = {case_gain:.4f} "
                  f"(x{case_gain / D.DRIVER_GAIN_NOMINAL:.3f})")
        elif env['name'] in per_case_rms:
            case_gain = float(per_case_rms[env['name']]['gain'])
            print(f"          per-case gain init = {case_gain:.4f} "
                  f"(x{case_gain / D.DRIVER_GAIN_NOMINAL:.3f})")
        seed_gain_per_case[env['name']] = case_gain
        if a_only:
            res, rows = run_case_aonly(cfg, model_a, env, n_steps=n_steps,
                                       per_case_gain=case_gain)
        else:
            res, rows = run_case(cfg, model_a, model_b, env, n_steps=n_steps,
                                 per_case_gain=case_gain)
        results.append(res)
        df = pd.DataFrame(rows) if rows else pd.DataFrame()
        if not df.empty:
            df.insert(0, 'env', env['name'])
        trace_dfs[env['name']] = df
        tag2 = ('+' if res.get('delta_lb_seed_to_best', 0) < -0.01 else
                ('~' if abs(res.get('delta_lb_seed_to_best', 0)) <= 0.01 else '-'))
        print(f"    seed BER_MLSE={res['seed_ber']:.3e} | "
              f"best={res.get('best_ber', np.nan):.3e} "
              f"(step {res.get('best_step', 'NA')}, gain {res.get('best_gain', float('nan')):.3f}) | "
              f"final={res.get('final_ber', np.nan):.3e} | {tag2}")

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
                   'sim_seeds': list(sim_seeds),
                   'a_only': bool(a_only),
                   # per_case_target_rms = 离线 RMS 标定参照（每用例单独细扫，不随 seed 覆盖变化）；
                   # per_case_gain = 本跑每用例实际作为 seed 的 gain（--seed-config 覆盖时为覆盖值，否则 per-case RMS 最优）。
                   'per_case_target_rms': ({k: v['target_rms'] for k, v in per_case_rms.items()}
                                            if per_case_rms else None),
                   'per_case_gain': (seed_gain_per_case if seed_gain_per_case else {k: v['gain'] for k, v in per_case_rms.items()}
                                     if per_case_rms else None),
                   'envs': [e['name'] for e in cases]},
                  f, indent=2, ensure_ascii=False)
    print(f"\n[test {tag}] done -> {out_dir}/case_summary.csv")

    return out_dir


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument('--model-dir', default='models/ddps', help='Frozen model dir')
    ap.add_argument('--out-dir', default='result/ddps_main')
    ap.add_argument('--n-steps', type=int, default=25)
    ap.add_argument('--num-symbols', type=int, default=262144)
    ap.add_argument('--sim-seeds', type=str, default='42,43,44',
                    help='逗号分隔的仿真种子序列（多seed取log10 BER均值）')
    ap.add_argument('--only-envs', type=str, default=None, help='仅跑指定环境（逗号分隔）')
    ap.add_argument('--a-only', action='store_true',
                    help='A-only 对比实验：只用 Model A 梯度，不查 Model B，不走安全拦截')
    ap.add_argument('--per-case-rms-path', type=str, default=None,
                    help='per-case target_rms JSON 路径（默认 result/per_case_target_rms.json）')
    ap.add_argument('--seed-config', type=str, default=None,
                    help='种子点 JSON（best_pre_post/best_gdc/best_gdc2，可选 best_u_gain 或 best_gain）；'
                         '不提供则用默认 SEED_TAPS + per-case RMS gain')
    a = ap.parse_args()
    # 覆盖种子点（用于非基线环境训练的模型 / 次优种子演示）：统一走 apply_seed_config。
    if a.seed_config:
        SEED_GAIN_OVERRIDE = D.apply_seed_config(a.seed_config)
        print(f"[test] 种子点覆盖: taps={np.round(D.SEED_TAPS,4)} gDC={D.SEED_GDC:.2f} gDC2={D.SEED_GDC2:.2f}"
              + (f" gain={SEED_GAIN_OVERRIDE:.4f}" if SEED_GAIN_OVERRIDE is not None else ""))
    utils_config.ensure_config()
    sim_seeds = tuple(int(s) for s in str(a.sim_seeds).split(',') if s.strip())
    only = tuple(s.strip() for s in a.only_envs.split(',')) if a.only_envs else None
    run_generalization(a.model_dir, a.out_dir, n_steps=a.n_steps,
                       num_symbols=a.num_symbols,
                       sim_seeds=sim_seeds,
                       only_envs=only, a_only=a.a_only,
                       per_case_rms_path=a.per_case_rms_path)