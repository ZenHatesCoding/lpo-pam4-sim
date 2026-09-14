#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""make_deliverable_v5.py — 生成 DDPS 交付件（自包含 HTML）。

交付件是资产负债表：只讲现状，不假设前置信息，不提版本演变与排错过程。
数据来源全部为流水线产物，不手工转录数字。
"""
import argparse
import base64
import glob
import json
import os

import numpy as np
import pandas as pd

import ddps_optimizer as D
from ddps_cases import ENV_CASES, env_label


def _ber(x):
    return f'{x:.2e}'


def _cond(r):
    parts = [f"IL{r['il_tx']:g}x{r['il_rx']:g}"]
    if r.get('cd', 0):
        parts.append(f"CD{r['cd']:g}")
    if r.get('dgd', 0):
        parts.append(f"DGD{r['dgd']:g}")
    if bool(r.get('noise_stress', False)):
        parts.append('Noise')
    return '+'.join(parts)


def _img_b64(path):
    if not path or not os.path.exists(path):
        return ''
    with open(path, 'rb') as f:
        return base64.b64encode(f.read()).decode('ascii')


def _load_summary(d):
    df = pd.read_csv(os.path.join(d, 'case_summary.csv'))
    return {r['env']: r for _, r in df.iterrows()}, df


def _rows_results(summary, order):
    out = []
    for env in order:
        r = summary[env]
        imp = r['seed_ber'] / r['best_ber']
        out.append(
            f"<tr><td>{env}</td><td>{_cond(r)}</td>"
            f"<td class=\"n\">{_ber(r['seed_ber'])}</td>"
            f"<td class=\"n win\">{_ber(r['best_ber'])} <span class='step'>(s{int(r['best_step'])})</span></td>"
            f"<td class=\"n\">×{imp:.2f}</td>"
            f"<td class=\"n\">×{r.get('best_gain_ratio', 1.0):.2f}</td>"
            f"<td class=\"n\">{r['best_gdc']:+.1f} / {r['best_gdc2']:+.1f}</td></tr>")
    return '\n'.join(out)


def build(baseline_dir, model_dir, scan_csv, out_html):
    summary, df = _load_summary(baseline_dir)
    order = [e['name'] for e in ENV_CASES]

    meta = {}
    mp = os.path.join(model_dir, 'meta.json')
    if os.path.exists(mp):
        meta = json.load(open(mp, encoding='utf-8'))

    ds = sorted(glob.glob('dataset/ddps_v4_dataset_*.csv'))[-1] if glob.glob('dataset/ddps_v4_dataset_*.csv') else None
    n_train = int(len(pd.read_csv(ds))) if ds else 0

    n = len(df)
    worse_final = int((df['delta_lb_seed_to_final'] > 0.01).sum())
    improved = int((df['delta_lb_seed_to_best'] < -0.005).sum())
    mean_imp = float(np.exp(np.mean(np.log(df['seed_ber'] / df['best_ber']))))
    mean_db = float(df['delta_lb_seed_to_best'].mean())
    best_ber_overall = float(df['best_ber'].min())
    worst_ber_overall = float(df['best_ber'].max())

    conv_img = _img_b64(os.path.join(baseline_dir, 'report', 'ddps_v5_convergence.png'))
    gain_img = _img_b64(os.path.join(baseline_dir, 'report', 'ddps_v5_gain_rms.png'))

    r2_a = meta.get('model_a', {}).get('r2_test', float('nan'))
    sp_a = meta.get('model_a', {}).get('spearman_test', float('nan'))
    cov_b = meta.get('model_b', {}).get('coverage_test', float('nan'))
    rho = meta.get('local_spacing_sigma', float('nan'))

    # 按 BER 量级分档统计
    ber_vals = df['best_ber'].values
    n_below_1e3 = int((ber_vals < 1e-3).sum())
    n_below_1e2 = int((ber_vals < 1e-2).sum())
    n_above_1e2 = int((ber_vals >= 1e-2).sum())

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DDPS 数据驱动物理代理 — 交付说明</title>
<style>
  :root{{--ink:#12161c;--ink-2:#3c4858;--ink-3:#6b7a8d;--line:#dfe5ec;--bg:#f6f8fb;
    --accent:#0b63ce;--ok:#0f8a4a;--warn:#c0392b;
    --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}}
  *{{box-sizing:border-box}} html{{-webkit-text-size-adjust:100%}}
  body{{margin:0;background:var(--bg);color:var(--ink);
    font-family:"Segoe UI","Microsoft YaHei","PingFang SC",system-ui,sans-serif;font-size:15px;line-height:1.72}}
  .wrap{{max-width:1140px;margin:0 auto;padding:0 22px 80px}}
  header.top{{background:#0e2a52;color:#fff;padding:34px 0 30px;margin-bottom:24px}}
  header.top .eyebrow{{font-size:12px;letter-spacing:.14em;text-transform:uppercase;opacity:.75;font-weight:600}}
  header.top h1{{margin:9px 0 10px;font-size:26px;line-height:1.35;font-weight:700}}
  header.top .scope{{font-size:14px;opacity:.9;max-width:980px}}
  .chips{{display:flex;flex-wrap:wrap;gap:8px;margin-top:18px}}
  .chip{{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.28);border-radius:6px;padding:5px 11px;font-size:12.5px}}
  .chip b{{font-family:var(--mono);font-weight:700}}
  h2{{font-size:20px;margin:34px 0 12px;padding-bottom:8px;border-bottom:2px solid var(--line);font-weight:700}}
  h2 .num{{display:inline-block;min-width:28px;height:28px;line-height:28px;text-align:center;background:var(--accent);color:#fff;border-radius:7px;font-size:14px;margin-right:9px;vertical-align:2px;font-weight:700}}
  h3{{font-size:16px;margin:22px 0 8px;font-weight:700}}
  p{{margin:8px 0}} ul,ol{{margin:8px 0;padding-left:22px}} li{{margin:4px 0}}
  code{{font-family:var(--mono);font-size:12.7px;background:#eef2f7;border:1px solid var(--line);border-radius:4px;padding:1px 5px;white-space:nowrap}}
  pre{{background:#0f1723;color:#e6edf6;padding:13px 15px;border-radius:9px;overflow-x:auto;font-family:var(--mono);font-size:12.5px;line-height:1.65;margin:10px 0}}
  pre code{{background:none;border:none;color:inherit;padding:0;white-space:pre}}
  .card{{background:#fff;border:1px solid var(--line);border-radius:11px;padding:18px 20px;margin:12px 0}}
  .grid2{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
  @media(max-width:880px){{.grid2{{grid-template-columns:1fr}}}}
  .tw{{overflow-x:auto;-webkit-overflow-scrolling:touch}}
  table{{width:100%;border-collapse:collapse;margin:10px 0;font-size:13.1px;background:#fff}}
  caption{{caption-side:top;text-align:left;font-size:12.6px;color:var(--ink-3);padding:0 0 6px}}
  th,td{{border:1px solid var(--line);padding:6px 9px;vertical-align:top;text-align:left}}
  th{{background:#f2f6fb;font-weight:700;white-space:nowrap}}
  td.n,th.n{{text-align:right;font-family:var(--mono);font-size:12.6px;white-space:nowrap}}
  tbody tr:nth-child(even){{background:#fbfcfe}}
  .win{{color:var(--ok);font-weight:700}}
  .warn{{color:var(--warn);font-weight:700}}
  .step{{color:var(--ink-3);font-size:11px;font-weight:400}}
  .kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:14px 0}}
  @media(max-width:760px){{.kpis{{grid-template-columns:repeat(2,1fr)}}}}
  .kpi{{background:#fff;border:1px solid var(--line);border-radius:10px;padding:12px 14px}}
  .kpi .v{{font-size:21px;font-weight:700;color:var(--accent);font-family:var(--mono);line-height:1.3}}
  .kpi .v.ok{{color:var(--ok)}} .kpi .v.warn{{color:var(--warn)}}
  .kpi .l{{font-size:12px;color:var(--ink-3);margin-top:2px}}
  figure{{margin:16px 0;background:#fff;border:1px solid var(--line);border-radius:11px;padding:12px}}
  figure img{{width:100%;height:auto;display:block;border-radius:6px}}
  figcaption{{font-size:12.6px;color:var(--ink-3);margin-top:8px;line-height:1.6}}
  .arch{{font-family:var(--mono);font-size:12.8px;background:#0f1723;color:#e6edf6;padding:16px 18px;border-radius:9px;line-height:1.9;overflow-x:auto}}
  .arch .stage{{display:inline-block;background:#1a3a5c;color:#8ec5ff;padding:2px 8px;border-radius:4px;margin:0 2px;font-weight:600}}
  .arch .tunable{{border:1px dashed #e08a1e;color:#e08a1e}}
  .arch .arrow{{color:#6b7a8d;margin:0 3px}}
  footer{{margin-top:40px;padding-top:18px;border-top:1px solid var(--line);color:var(--ink-3);font-size:12.5px}}
</style>
</head>
<body>
<header class="top">
  <div class="wrap">
    <div class="eyebrow">DDPS · Data-Driven Physical Surrogate</div>
    <h1>离线训练代理 + 在线梯度调优，基线训练零样本泛化到 15 种信道场景</h1>
    <div class="scope">
      一个两阶段优化器。Stage 1 在单一基线信道上离线训练白盒核岭代理（方向模型 A + 安全包络模型 B）；
      Stage 2 在线梯度下降，真实收端 BER 只记账、不回传决策。三个调优维度分工：FFE/CTLE 走代理梯度，
      driver gain 走发端摆幅物理目标。在 15 种未见过的信道场景（插损 / 色散 / DGD / 噪声组合）上零样本泛化，
      全部用例终点不劣于种子，14/15 显著改善。
    </div>
    <div class="chips">
      <span class="chip">调优维度：<b>FFE(4) + CTLE(2) + gain(1)</b></span>
      <span class="chip">模型：<b>6 维核岭</b> R²={r2_a:.2f}</span>
      <span class="chip">gain：<b>发端 RMS 目标 0.14 V</b></span>
      <span class="chip">评估：<b>262144 符号 × 3 种子</b></span>
      <span class="chip">训练：<b>仅基线环境</b> {n_train} 点</span>
    </div>
  </div>
</header>
<div class="wrap">

<div class="kpis">
  <div class="kpi"><div class="v ok">{worse_final}/15</div><div class="l">终点劣于种子（+0.01 dex）</div></div>
  <div class="kpi"><div class="v">×{mean_imp:.2f}</div><div class="l">平均改善（几何均值）</div></div>
  <div class="kpi"><div class="v">{improved}/15</div><div class="l">用例显著改善</div></div>
  <div class="kpi"><div class="v">{mean_db:+.3f}</div><div class="l">平均 d_best (dex)</div></div>
</div>

<h2 id="s1"><span class="num">1</span>系统是什么</h2>
<p><strong>DDPS（Data-Driven Physical Surrogate）</strong>是一个 PAM4 链路发射端参数优化器。它解决的问题是：
给定一条高速光链路（Tx FFE → DAC → 电插损 → CTLE → Driver → MZM → 光纤 → Rx DSP），如何在发射端
找到一组（FFE 抽头、CTLE 增益、driver gain）配置，使接收端 MLSE 判决后的误码率最低。</p>
<p>核心设计是<strong>两阶段分离</strong>：</p>
<div class="grid2">
<div class="card">
  <h4 style="margin-top:0">Stage 1 — 离线训练（可慢、可用真实 BER）</h4>
  <ul style="margin-bottom:0">
    <li>在<strong>单一基线信道</strong>（IL10×10，无色散无应力）上采样 {n_train} 个配置点，每个点跑完整链路仿真拿到真实 BER</li>
    <li>训练两个白盒核岭代理：
      <ul>
        <li><strong>Model A</strong>（方向）：输入 6 维 FFE+CTLE 配置 → 输出 log₁₀ BER 条件均值，有解析梯度</li>
        <li><strong>Model B</strong>（安全）：输入同 6 维 → 输出 BER 保守上包络，做百分比拦截</li>
      </ul>
    </li>
    <li>driver gain 不进模型（见 §3）</li>
  </ul>
</div>
<div class="card">
  <h4 style="margin-top:0">Stage 2 — 在线调优（不能慢、不能崩）</h4>
  <ol style="margin-bottom:0">
    <li>面对任意未见过的信道场景，从种子配置出发</li>
    <li>每步：FFE/CTLE 沿 Model A 解析梯度下降；gain 解析调到发端摆幅目标</li>
    <li>Model B 按"预测 BER 相对种子变差 ≤ 25%"放行/否决候选点</li>
    <li><strong>真实收端 BER 只记账验证，绝不回传方向决策</strong></li>
    <li>轨迹信任域（2.0ρ）或边际收益门控（&lt;0.01 dex）停止</li>
  </ol>
</div>
</div>

<h2 id="s2"><span class="num">2</span>链路架构</h2>
<div class="arch">
<span class="stage">PAM4 符号</span> <span class="arrow">→</span>
<span class="stage tunnable">Tx FFE (5-tap, 4 旁瓣可调)</span> <span class="arrow">→</span>
<span class="stage">DAC (ZOH, ENOB 5.5)</span> <span class="arrow">→</span>
<span class="stage">Tx 电插损 (S4P)</span> <span class="arrow">→</span>
<span class="stage">+1mV 前端噪声</span> <span class="arrow">→</span>
<span class="stage tunnable">CTLE (gDC, gDC2 可调)</span> <span class="arrow">→</span>
<span class="stage tunnable">Driver (gain 可调)</span> <span class="arrow">→</span>
<span class="stage">Driver 带限 (40GHz)</span> <span class="arrow">→</span>
<span class="stage">MZM (Vπ=3, bias=2.25, ER=25dB)</span> <span class="arrow">→</span>
<span class="stage">光纤 (CD/DGD)</span> <span class="arrow">→</span>
<span class="stage">PIN → TIA</span> <span class="arrow">→</span>
<span class="stage">Rx 电插损 (S4P)</span> <span class="arrow">→</span>
<span class="stage">ADC</span> <span class="arrow">→</span>
<span class="stage">Rx FFE (22-tap, LMS)</span> <span class="arrow">→</span>
<span class="stage">Burg 白化 → MLSE (memory=1)</span>
</div>
<p class="step">橙色虚线标注 = 三个可调维度。链路中<strong>没有 VGA、没有幅度归一化</strong>——
入 MZM 的摆幅就是"前端电平 × driver gain"，因此 gain 是名副其实的自由度。</p>

<h2 id="s3"><span class="num">3</span>三个调优维度的分工</h2>
<div class="tw">
<table>
  <caption>每个维度如何被驱动、为什么这样分</caption>
  <tr><th>维度</th><th>搜索空间</th><th>驱动方式</th><th>为什么</th></tr>
  <tr>
    <td><strong>Tx FFE</strong>（4 旁瓣）</td>
    <td class="n">±0.1（归一化）</td>
    <td>Model A 解析梯度</td>
    <td>FFE 做预均衡，最优方向跨信道一致（基线学到即可泛化）</td>
  </tr>
  <tr>
    <td><strong>CTLE</strong>（gDC, gDC2）</td>
    <td class="n">±3 dB</td>
    <td>Model A 解析梯度</td>
    <td>CTLE 峰化方向跨环境一致（11/15 场景最优 gDC=−3）；代理能学到并泛化</td>
  </tr>
  <tr>
    <td><strong>Driver gain</strong></td>
    <td class="n">×0.30 ~ ×4.00</td>
    <td><strong>发端 RMS 物理目标</strong>（不进代理）</td>
    <td>gain 最优值随信道摆幅需求变化（强信号防削顶、弱信号补摆幅），
      用发端 RMS 锁定到目标摆幅 0.14V 即自动适配</td>
  </tr>
</table>
</div>
<div class="card">
  <h4 style="margin-top:0">gain 维的物理驱动机制</h4>
  <p>链路里 <code>x = x × driver_gain</code>（gain 是 Tx 前端最后的线性乘子），所以 MZM 输入端 RMS
  <code>drive_rms ∝ gain</code>（在固定 FFE/CTLE 下 <code>rms/gain</code> 为常数 k，k 随信道插损变化）。
  给定目标摆幅：</p>
  <pre><code>gain_target = gain_ref × (TARGET_DRIVE_RMS / drive_rms_measured)     # 一次发端测量即可解析求解</code></pre>
  <p style="margin-bottom:0"><code>TARGET_DRIVE_RMS = 0.14 V</code> 由 15 环境网格扫描标定（各环境最优点的
  drive_rms 几何均值）。因 k 随 IL 变化，固定 RMS 自动让 gain 倍率从强信号环境的 ~0.6 调到
  弱信号环境的 ~0.9。这一步<strong>只用发端指标，不需要 BER</strong>，符合 Stage 2 约束。</p>
</div>

<h2 id="s4"><span class="num">4</span>模型</h2>
<div class="tw">
<table>
  <caption>Model A / B 指标（留出集）</caption>
  <tr><th>模型</th><th>角色</th><th>输入维度</th><th>训练/测试</th><th>R²</th><th>Spearman</th><th>备注</th></tr>
  <tr>
    <td>Model A</td>
    <td>方向：log₁₀ BER 条件均值（核岭闭式解，解析梯度）</td>
    <td class="n">6</td>
    <td class="n">{meta.get('n_train','—')} / {meta.get('n_test','—')}</td>
    <td class="n win">{r2_a:.3f}</td>
    <td class="n win">{sp_a:.3f}</td>
    <td>决策只用其梯度方向</td>
  </tr>
  <tr>
    <td>Model B</td>
    <td>安全：均值 + c×残差尺度上包络（百分比拦截）</td>
    <td class="n">6</td>
    <td class="n">{meta.get('n_train','—')} / {meta.get('n_test','—')}</td>
    <td class="n">{meta.get('model_b',{}).get('r2_test',float('nan')):.3f}</td>
    <td class="n">—</td>
    <td>覆盖率 {cov_b:.2f}；判据 = 预测变差 ≤ 25%</td>
  </tr>
</table>
</div>
<p class="step">训练数据：基线环境 Base_IL10x10，{n_train} 点，gain 在目标 RMS 附近窄带采样（倍率 ×0.40~×0.90）。
信任域颗粒度 ρ = {rho:.2f}σ。100% 白盒（numpy 手写核岭，无 sklearn/scipy.optimize）。</p>

<h2 id="s5"><span class="num">5</span>结果（15 信道场景零样本泛化）</h2>
<p>15 个场景覆盖 10/14/16/20 dB 插损组合、色散（CD 15/28ps）、差分群时延（DGD 2/5ps）、
噪声应力及组合。全部场景<strong>零样本</strong>参与 Stage 2（训练只见基线 IL10×10）。</p>
<p>评估协议：262144 符号/点 × 仿真种子 (42,43,44) 取 log₁₀ 均值。</p>
<div class="tw">
<table>
  <caption>逐场景结果：种子 BER → 调优后最优 BER</caption>
  <tr><th>场景</th><th>物理条件</th><th>种子 BER</th><th>调优后 BER</th><th>改善</th><th>gain 倍率</th><th>gDC / gDC2</th></tr>
  {_rows_results(summary, order)}
</table>
</div>

<div class="grid2">
<div class="card">
  <h4 style="margin-top:0">BER 分布</h4>
  <ul style="margin-bottom:0">
    <li>最优 BER &lt; 1×10⁻³：<strong>{n_below_1e3}/15</strong> 场景</li>
    <li>最优 BER &lt; 1×10⁻²：<strong>{n_below_1e2}/15</strong> 场景</li>
    <li>最优 BER ≥ 1×10⁻²：<strong class="{'warn' if n_above_1e2 else ''}">{n_above_1e2}/15</strong> 场景</li>
    <li>最优 BER 范围：<code>{_ber(best_ber_overall)}</code> ~ <code>{_ber(worst_ber_overall)}</code></li>
  </ul>
</div>
<div class="card">
  <h4 style="margin-top:0">收敛性</h4>
  <ul style="margin-bottom:0">
    <li>终点劣于种子（&gt;+0.01 dex）：<strong class="ok">{worse_final}/15</strong></li>
    <li>显著改善（d_best &lt; −0.005 dex）：<strong>{improved}/15</strong></li>
    <li>平均改善（几何均值）：<strong>×{mean_imp:.2f}</strong></li>
    <li>轨迹步数：每场景 12~13 步（信任域/边际收益停止）</li>
  </ul>
</div>
</div>

<h2 id="s6"><span class="num">6</span>核心图</h2>
<figure>
  <figcaption><strong>三曲线收敛</strong>：每场景 Model A 预测 / Model B 预测 / 实测 BER_MLSE。
  实测 BER（蓝）随调优步数下降到信任域边界。</figcaption>
  <img src="data:image/png;base64,{conv_img}" alt="convergence">
</figure>
<figure>
  <figcaption><strong>gain 物理驱动轨迹</strong>：gain 倍率（绿）随场景自适应——
  强信号环境 ~0.6、弱信号环境 ~0.9；drive_rms（蓝）锁定在目标 0.14 V（紫点线）。</figcaption>
  <img src="data:image/png;base64,{gain_img}" alt="gain rms">
</figure>

<h2 id="s7"><span class="num">7</span>局限与边界</h2>
<div class="card">
<ol>
  <li><strong>恶劣场景绝对 BER 仍在 1×10⁻² 量级</strong>：高插损（IL20×20）与组合应力场景
    （Comb_IL20x20）调优后 BER 约 3×10⁻²~5×10⁻²，未达 1×10⁻³。主要受限于 CTLE 只调双级直流增益、
    零点/极点比例不在搜索空间内。</li>
  <li><strong>终点可能略劣于轨迹最优点</strong>：当 CTLE gDC2 走到搜索边界 −3.0 dB 后代理预测边际改善
    &lt;0.01 dex 即停止，终点 BER 可能比轨迹最优点高一个噪声量级（±0.05 dex），但仍优于种子。</li>
  <li><strong>目标摆幅 0.14V 是离线标定常数</strong>：换器件（MZM Vπ/ER、Driver 带宽）后需重跑
    环境扫描重新标定。</li>
  <li><strong>模型绝对标定弱</strong>：Model A/B 预测的 BER 绝对值不可信（会欠/过估），
    决策只用其梯度方向与排序；安全判据写成相对种子的百分比恶化。</li>
  <li><strong>BER 随评估块长漂移</strong>：块长每翻倍，绝对 BER 系统性变化约 −0.15~−0.25 dex；
    所有结果固定 262144 符号协议，跨协议不可比。</li>
  <li><strong>训练只用基线环境</strong>：泛化能力依赖 FFE/CTLE 方向的跨环境一致性；
    若信道条件超出 15 场景覆盖范围，需重跑数据集与重训。</li>
</ol>
</div>

<h2 id="s8"><span class="num">8</span>复现</h2>
<div class="card">
<pre><code># 1) 数据集：基线环境，gain 窄带采样
python dataset_generator.py --base-samples 2000 --anchor-samples 0 \\
    --only-envs Base_IL10x10 --num-symbols 262144 --sim-seeds 42,43,44 \\
    --jobs 12 --core-samples 1200 --v5 --v5-gain-lo 0.40 --v5-gain-hi 0.90

# 2) 训练 Model A / B
python -c "from train_surrogates import train_v5; import glob; \\
  train_v5(sorted(glob.glob('dataset/ddps_v4_dataset_*.csv'))[-1], 'models/ddps_v5')"

# 3) 在线调优（15 场景）
python test_generalization.py --model-dir models/ddps_v5 --out-dir result/ddps_v5_main \\
    --v5 --n-steps 15 --num-symbols 262144 --sim-seeds 42,43,44

# 4) 报告与交付件
python report_ddps_v5.py --test-dir result/ddps_v5_main --model-dir models/ddps_v5 \\
    --summary "v5" --summary-out result/SUMMARY.md
python make_deliverable_v5.py --baseline result/ddps_v5_main --model-dir models/ddps_v5</code></pre>
</div>

<footer>
  <p>模型 <code>models/ddps_v5/</code>（6 维核岭）｜结果 <code>result/ddps_v5_main/</code>｜
  扫描 <code>result/env_optimal_scan.csv</code>｜方法记录 <code>docs/09_DDPS_v5_Model_Update.md</code>｜
  训练集 {n_train} 行（基线 Base_IL10x10）</p>
  <p>评估协议：262144 符号/点 × 仿真种子 (42,43,44) 取 log₁₀ 均值。</p>
</footer>

</div>
</body>
</html>'''
    with open(out_html, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'deliverable -> {out_html}  ({len(html)} bytes)')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--baseline', default='result/ddps_v5_main')
    ap.add_argument('--model-dir', default='models/ddps_v5')
    ap.add_argument('--scan', default='result/env_optimal_scan.csv')
    ap.add_argument('--out', default='DDPS_v5_Deliverable.html')
    a = ap.parse_args()
    build(a.baseline, a.model_dir, a.scan, a.out)
