import os
import json
import time
import argparse
import numpy as np
import pandas as pd

# ============================================================================
# DDPS 泛化/在线调优测试（test_generalization.py）
#
# 运行口径（AGENTS.md「开发方式」）：本脚本是 Python 原理参照入口，只用于
# 小点数低 SNR 验证与 Python↔C++ 比对（2^18 及以下）；全量规模仿真
# （高 SNR 大点数，如 2^22）只用通过比对的 C++ 入口（cpp/run_all_cases.py），
# 不允许用 Python 跑高 SNR 大点数。
#
# 方法论（控制变量法）：
#   - 模型在离线数据上训练并【固化】（不针对任何评估用例重新采样/重训）；
#   - 对每个物理应力环境（仅改单一/复合物理变量），直接复用同一组模型做
#     Stage-2 在线调优；真实 BER_MLSE 只记录、不参与方向决策（Stage-2 底线）；
#   - 输出：逐 case trace(csv) + 聚合表 + model_meta_snapshot + run_config。
#
# 搜索空间：8 维（5 个 Tx FFE 抽头 + gDC + gDC2 + u_gain）。抽头无边界。
#   gain 初值 = seed_config 给定的次优工作点 gain，之后放开走梯度。
# ============================================================================
import utils_config
import ddps_optimizer as D
from train_surrogates import load_models
from ddps_cases import ENV_CASES, apply_env_to_config

# 种子点 gain 覆盖（配合 --seed-config）：非 None 时，gain 初值用它替代 per-case RMS 扫描值，
# 从而支持从一个"次优工作点"（形状 + gain 全部给定）出发做在线调优演示。
SEED_GAIN_OVERRIDE = None


def _trace_rows(trace):
    """把 optimizer 的 trace 转成 (落点行, 微扰态行)。列结构与历史结果目录保持一致。"""
    rows, probe_rows = [], []
    for t in trace:
        for p in t.get('probes', []):
            xv = np.asarray(p['x']).tolist()
            tv = np.asarray(p['taps']).tolist()
            rec = {'step': t['step'], 'param': int(p['param']), 'sign': int(p['sign'])}
            for j in range(len(xv)):
                rec[f'x_{j}'] = float(xv[j])
            for j in range(len(tv)):
                rec[f'tap_{j}'] = float(tv[j])
            rec.update({
                'gdc': float(p['gdc']), 'gdc2': float(p['gdc2']),
                'gain': float(p['gain']), 'gain_ratio': float(p['gain_ratio']),
                'u_gain': float(p['u_gain']),
                'real_lb': float(p['real_logber']), 'real_ber': float(p['real_mlse']),
            })
            probe_rows.append(rec)
        rows.append({
            'step': t['step'], 'x': np.asarray(t['x']).tolist(),
            'taps': np.round(np.asarray(t['taps']), 6).tolist(),
            'gdc': t['gdc'], 'gdc2': t['gdc2'], 'gain': t['gain'],
            'gain_ratio': t['gain'] / D.DRIVER_GAIN_NOMINAL,
            'u_gain': t.get('u_gain'),
            'drive_rms': t.get('drive_rms'),
            'pred_b_ber': t.get('pred_b_ber', 0.0), 'allowed_ber': t.get('allowed_ber', 0.0),
            'stop_reason': t.get('stop_reason', ''),
            'pred_a': t['pred_a'], 'pred_b': t.get('pred_b', 0.0),
            'real_lb': t['real_logber'], 'real_ber': t['real_mlse'],
            'grad': np.asarray(t.get('grad', np.zeros(D.N_DIM))).tolist(),
            'refreshed': ','.join(str(i) for i in t.get('refreshed', [])),
            'n_probe_states': int(t.get('n_probe_states', 0)),
            'grad_norm': t['grad_norm'],
        })
    return rows, probe_rows


def _summarize(env, rows, probe_rows, seed_lb, seed_ber, gain0, n_steps, extra=None):
    """聚合单个用例的结果字典（与历史 case_summary 列结构兼容）。"""
    real_lb_t = np.array([r['real_lb'] for r in rows]) if rows else np.array([])
    probe_lb_t = np.array([p['real_lb'] for p in probe_rows]) if probe_rows else np.array([])
    result = {
        'env': env['name'], 'il_tx': env['il_tx'], 'il_rx': env['il_rx'],
        'cd': env['cd'], 'dgd': env['dgd'], 'pol': env['pol'],
        'noise_stress': bool(env.get('stress')),
        'seed_lb': float(seed_lb), 'seed_ber': float(seed_ber),
        'n_steps_requested': n_steps,
        'n_steps_actual': len(rows),
        'seed_gain': float(gain0),
        'seed_gain_ratio': float(gain0 / D.DRIVER_GAIN_NOMINAL),
        # 在线真实评估次数 = 落点数 + 微扰态数（微扰态是真实的在线性能代价，必须计入）
        'n_landed': int(len(rows)),
        'n_probe_states': int(len(probe_rows)),
        'n_real_evals': int(len(rows) + len(probe_rows)),
        'max_probe_lb': float(probe_lb_t.max()) if probe_lb_t.size else float('nan'),
        'max_probe_ber': float(10.0 ** probe_lb_t.max()) if probe_lb_t.size else float('nan'),
    }
    if extra:
        result.update(extra)
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
    return result


def run_case(cfg, model_a, env, n_steps=25, per_case_gain=None,
             grad_mode='full', rotate_k=D.ROTATE_K):
    """在线调优（Model A 方向代理）：8 维梯度下降（5 抽头 + gDC + gDC2 + u_gain）。

    grad_mode：形状维梯度刷新方式（full / rotate / secant），详见 ddps_optimizer。
    direct：端到端 BER 直接梯度下降（有回传通道时的参照）。
    """
    ffe_pre = int(cfg['tx'].get('ffe_pre', D.FFE_PRE))
    gain0 = float(per_case_gain) if per_case_gain is not None else float(D.SEED_GAIN)
    x0 = np.concatenate([D.SEED_TAPS.copy(),
                         [D.SEED_GDC, D.SEED_GDC2, D.u_from_gain(gain0)]])

    seed_lb, seed_ber = D._physical_eval(cfg, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2, gain0)
    taps_seed = D.taps_of(x0)
    probe_seed = D._probe_features(cfg, taps_seed, float(x0[D.N_TAP]),
                                   float(x0[D.N_TAP + 1]), gain0)
    pa_seed = D._predict_a_probe(model_a, probe_seed)

    trace = D._stage2_descent_proxy(cfg, model_a, x0, n_steps, D.GD_LR,
                                    grad_mode=grad_mode, rotate_k=rotate_k)

    rows, probe_rows = _trace_rows(trace)
    result = _summarize(env, rows, probe_rows, seed_lb, seed_ber, gain0, n_steps,
                        extra={'pa_seed': float(pa_seed), 'pb_seed': 0.0,
                               'grad_mode': grad_mode, 'rotate_k': int(rotate_k),
                               'ffe_pre': ffe_pre})
    return result, rows, probe_rows


def run_case_direct(cfg, env, n_steps=25, per_case_gain=None):
    """direct 参照：端到端真实 BER 直接梯度下降（无 Model A/B，假设有回传通道）。"""
    gain0 = float(per_case_gain) if per_case_gain is not None else float(D.SEED_GAIN)
    x0 = np.concatenate([D.SEED_TAPS.copy(),
                         [D.SEED_GDC, D.SEED_GDC2, D.u_from_gain(gain0)]])
    seed_lb, seed_ber = D._physical_eval(cfg, D.SEED_TAPS.copy(), D.SEED_GDC, D.SEED_GDC2, gain0)
    trace = D._stage2_descent_direct(cfg, x0, n_steps, D.GD_LR, f0=seed_lb)
    rows, probe_rows = _trace_rows(trace)
    result = _summarize(env, rows, probe_rows, seed_lb, seed_ber, gain0, n_steps,
                        extra={'pa_seed': float(seed_lb), 'pb_seed': 0.0,
                               'grad_mode': 'direct', 'rotate_k': 0})
    return result, rows, probe_rows


def run_generalization(model_dir, out_dir, n_steps=25, num_symbols=131072,
                       sim_seeds=(42,), only_envs=None,
                       per_case_rms_path=None, tx_noise_snr_db=0.0,
                       method='proxy', grad_mode='full', rotate_k=D.ROTATE_K):
    # config.xlsx 由主进程入口（__main__ / run_parallel_envs）在 spawn worker 前统一
    # 生成/校验；此处只 load_config 只读，绝不在 worker 里就地生成（避免多进程写坏 xlsx）。
    # 在线方向只来自 8 维探针域的方向代理（Model A）；Stage-1 一并导出的参数域产物不在线使用。
    # direct 档不需要任何代理，不加载模型。
    model_a = None
    if method != 'direct':
        model_a, _ = load_models(model_dir)
    try:
        with open(os.path.join(model_dir, 'meta.json'), encoding='utf-8') as f:
            meta = json.load(f)
    except Exception:
        meta = {}

    D.set_sim_seeds(sim_seeds)
    tag = 'direct' if method == 'direct' else f'proxy-{grad_mode}'

    per_case_rms = {}
    path = per_case_rms_path or 'result/per_case_target_rms.json'
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            per_case_rms = json.load(f)
        print(f"[test {tag}] per-case target_rms loaded from {path} ({len(per_case_rms)} envs)")
    else:
        print(f"[test {tag}] WARNING: {path} not found, falling back to seed gain")

    print(f"[test {tag}] models from {model_dir} | num_symbols={num_symbols} | "
          f"n_steps={n_steps} | sim_seeds={tuple(sim_seeds)} | n_dim={D.N_DIM}")

    os.makedirs(out_dir, exist_ok=True)
    results, trace_dfs, probe_dfs = [], {}, {}
    # 每个用例本跑实际用于初始化的 gain。给了 --seed-config 的 gain 覆盖时所有用例 = 覆盖值；
    # 否则 = per-case RMS 扫描解析出的最优 gain。用于如实写进 run_config.json（与种子点一致）。
    seed_gain_per_case = {}

    cases = [e for e in ENV_CASES if (only_envs is None or e['name'] in only_envs)]
    for env in cases:
        print(f"\n--- Stage-2 online tuning ({tag}): {env['name']} ---")
        base_cfg = utils_config.load_config('config.xlsx')
        cfg = apply_env_to_config(base_cfg, env)
        cfg['system']['num_symbols'] = int(num_symbols)
        cfg['system']['tx_noise_snr_db'] = float(tx_noise_snr_db)
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
        _t0 = time.perf_counter()
        if method == 'direct':
            res, rows, probe_rows = run_case_direct(cfg, env, n_steps=n_steps,
                                                    per_case_gain=case_gain)
        else:
            res, rows, probe_rows = run_case(cfg, model_a, env, n_steps=n_steps,
                                             per_case_gain=case_gain,
                                             grad_mode=grad_mode, rotate_k=rotate_k)
        # 与 C++ case_summary 对齐的两列：单用例墙钟（elapsed_sec）与含启动/落盘的总墙钟
        res['elapsed_sec'] = float(time.perf_counter() - _t0)
        res['wall_sec'] = float(res['elapsed_sec'])
        results.append(res)
        df = pd.DataFrame(rows) if rows else pd.DataFrame()
        if not df.empty:
            df.insert(0, 'env', env['name'])
        trace_dfs[env['name']] = df
        pdf = pd.DataFrame(probe_rows) if probe_rows else pd.DataFrame()
        if not pdf.empty:
            pdf.insert(0, 'env', env['name'])
        probe_dfs[env['name']] = pdf
        tag2 = ('+' if res.get('delta_lb_seed_to_best', 0) < -0.01 else
                ('~' if abs(res.get('delta_lb_seed_to_best', 0)) <= 0.01 else '-'))
        print(f"    seed BER_MLSE={res['seed_ber']:.3e} | "
              f"best={res.get('best_ber', np.nan):.3e} "
              f"(step {res.get('best_step', 'NA')}, gain {res.get('best_gain', float('nan')):.3f}) | "
              f"final={res.get('final_ber', np.nan):.3e} | "
              f"真实评估 {res.get('n_real_evals', 'NA')} 次 | {tag2}")

    out = pd.DataFrame(results)
    out.to_json(os.path.join(out_dir, 'case_summary.json'), orient='records', indent=2)
    out.to_csv(os.path.join(out_dir, 'case_summary.csv'), index=False)
    for name, df in trace_dfs.items():
        safe = name.replace(' ', '_').replace('(', '').replace(')', '')
        df.to_csv(os.path.join(out_dir, f'trace_{safe}.csv'), index=False)
    for name, pdf in probe_dfs.items():
        safe = name.replace(' ', '_').replace('(', '').replace(')', '')
        pdf.to_csv(os.path.join(out_dir, f'probes_{safe}.csv'), index=False)
    with open(os.path.join(out_dir, 'model_meta_snapshot.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False, default=str)
    with open(os.path.join(out_dir, 'run_config.json'), 'w', encoding='utf-8') as f:
        json.dump({'model_dir': model_dir, 'n_steps': n_steps, 'num_symbols': int(num_symbols),
                   'sim_seeds': list(sim_seeds),
                   'method': method, 'grad_mode': (grad_mode if method != 'direct' else 'direct'),
                   'rotate_k': (int(rotate_k) if method != 'direct' else 0),
                   'n_dim': int(D.N_DIM),
                   'seed_taps': D.SEED_TAPS.tolist(),
                   'seed_gdc': float(D.SEED_GDC), 'seed_gdc2': float(D.SEED_GDC2),
                   # per_case_target_rms = 离线 RMS 标定参照（每用例单独细扫，不随 seed 覆盖变化）；
                   # per_case_gain = 本跑每用例实际作为 seed 的 gain（--seed-config 覆盖时为覆盖值）。
                   'per_case_target_rms': ({k: v['target_rms'] for k, v in per_case_rms.items()}
                                            if per_case_rms else None),
                   'per_case_gain': (seed_gain_per_case if seed_gain_per_case else
                                     {k: v['gain'] for k, v in per_case_rms.items()}
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
    ap.add_argument('--sim-seeds', type=str, default='42',
                    help='逗号分隔的仿真种子序列（单种子口径：一次交付只用一个种子；'
                         '如需稳健性检查，用户自己换种子重跑）')
    ap.add_argument('--only-envs', type=str, default=None, help='仅跑指定环境（逗号分隔）')
    ap.add_argument('--per-case-rms-path', type=str, default=None,
                    help='per-case target_rms JSON 路径（默认 result/per_case_target_rms.json）')
    ap.add_argument('--seed-config', type=str, default=None,
                    help='种子点 JSON（best_taps 或 best_pre_post + best_gdc/best_gdc2，'
                         '可选 best_u_gain 或 best_gain）；不提供则用模块兜底 SEED_TAPS')
    ap.add_argument('--tx-noise-snr-db', type=float, default=0.0,
                    help='发端人为加噪 SNR（dB，相对 PAM4 满量程 RMS=√5）；>0 抬升 BER 地板用于快速验证')
    ap.add_argument('--method', type=str, default='proxy', choices=['proxy', 'direct'],
                    help='proxy = Model A 探针代理在线调优；direct = 端到端 BER 直接梯度下降（参照）')
    ap.add_argument('--grad-mode', type=str, default='full', choices=['full', 'rotate', 'secant'],
                    help='proxy 的形状维梯度刷新方式：full 每步全量微扰；'
                         'rotate 每步轮转刷新 k 个维；secant 只第 0 步测一次')
    ap.add_argument('--rotate-k', type=int, default=D.ROTATE_K,
                    help=f'rotate 模式每步刷新的形状维个数（默认 {D.ROTATE_K}）')
    a = ap.parse_args()
    # 覆盖种子点（用于非基线环境训练的模型 / 次优种子演示）：统一走 apply_seed_config。
    if a.seed_config:
        SEED_GAIN_OVERRIDE = D.apply_seed_config(a.seed_config)
        print(f"[test] 种子点覆盖: taps={np.round(D.SEED_TAPS, 4)} gDC={D.SEED_GDC:.2f} "
              f"gDC2={D.SEED_GDC2:.2f}"
              + (f" gain={SEED_GAIN_OVERRIDE:.4f}" if SEED_GAIN_OVERRIDE is not None else ""))
    utils_config.ensure_config()
    sim_seeds = tuple(int(s) for s in str(a.sim_seeds).split(',') if s.strip())
    only = tuple(s.strip() for s in a.only_envs.split(',')) if a.only_envs else None
    run_generalization(a.model_dir, a.out_dir, n_steps=a.n_steps,
                       num_symbols=a.num_symbols,
                       sim_seeds=sim_seeds,
                       only_envs=only,
                       per_case_rms_path=a.per_case_rms_path,
                       tx_noise_snr_db=a.tx_noise_snr_db,
                       method=a.method, grad_mode=a.grad_mode, rotate_k=a.rotate_k)
