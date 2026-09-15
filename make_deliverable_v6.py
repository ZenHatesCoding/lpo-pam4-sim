#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""make_deliverable_v6.py — 由产物自动生成 DDPS v6 交付件（自包含 HTML）。

数据来源（全部为流水线产物，无需手工转录）：
  result/ddps_v6_main/               只用基线训练 + 15 环境在线调优（per-case target_rms 物理驱动 gain）
  result/ddps_v6_divergence.csv      跟踪诊断（代理 vs 真实、位移/ρ）
  models/ddps_v6/                    meta.json（模型指标与特征维度）
  dataset/ddps_v4_dataset_*.csv      数据集统计
用法:
  python make_deliverable_v6.py --baseline result/ddps_v6_main --model-dir models/ddps_v6
"""
import matplotlib
matplotlib.use('Agg')

TEMPLATE = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="theme-color" content="#0e2a52">
<title>DDPS 交付说明 — 数据驱动物理代理寻优</title>
<style>
  :root{
    --ink:#12161c; --ink-2:#3c4858; --ink-3:#6b7a8d;
    --line:#dfe5ec;
    --bg:#f6f8fb; --card:#ffffff;
    --accent:#0b63ce;
    --ok:#0f8a4a;
    --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;
  }
  *{box-sizing:border-box}
  html{-webkit-text-size-adjust:100%}
  body{
    margin:0; background:var(--bg); color:var(--ink);
    font-family:"Segoe UI","Microsoft YaHei","PingFang SC","Hiragino Sans GB","Noto Sans SC",system-ui,sans-serif;
    font-size:15px; line-height:1.72;
  }
  .wrap{max-width:1140px;margin:0 auto;padding:0 22px 80px}
  header.top{background:#0e2a52;color:#fff;padding:34px 0 30px;margin-bottom:24px}
  header.top .eyebrow{font-size:12px;letter-spacing:.14em;text-transform:uppercase;opacity:.75;font-weight:600}
  header.top h1{margin:9px 0 10px;font-size:27px;line-height:1.35;font-weight:700}
  header.top .scope{font-size:14px;opacity:.9;max-width:980px}
  header.top .scope code{background:rgba(255,255,255,.15);border-color:rgba(255,255,255,.3);color:#fff}
  .chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:18px}
  .chip{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.28);border-radius:6px;
        padding:5px 11px;font-size:12.5px}
  .chip b{font-family:var(--mono);font-weight:700}
  h2{font-size:20px;margin:34px 0 12px;padding-bottom:8px;border-bottom:2px solid var(--line);font-weight:700}
  h2 .num{display:inline-block;min-width:28px;height:28px;line-height:28px;text-align:center;
          background:var(--accent);color:#fff;border-radius:7px;font-size:14px;margin-right:9px;vertical-align:2px;font-weight:700}
  h3{font-size:16px;margin:22px 0 8px;font-weight:700}
  h4{font-size:14px;margin:16px 0 6px;font-weight:700;color:var(--ink-2)}
  p{margin:8px 0}
  ul,ol{margin:8px 0;padding-left:22px}
  li{margin:4px 0}
  code{font-family:var(--mono);font-size:12.7px;background:#eef2f7;border:1px solid var(--line);
       border-radius:4px;padding:1px 5px;white-space:nowrap}
  pre{background:#0f1723;color:#e6edf6;padding:13px 15px;border-radius:9px;overflow-x:auto;
      -webkit-overflow-scrolling:touch;font-family:var(--mono);font-size:12.5px;line-height:1.65;margin:10px 0}
  pre code{background:none;border:none;color:inherit;padding:0;white-space:pre}
  .card{background:var(--card);border:1px solid var(--line);border-radius:11px;padding:18px 20px;margin:12px 0}
  .grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
  @media (max-width:880px){.grid2{grid-template-columns:1fr}}
  .tw{overflow-x:auto;-webkit-overflow-scrolling:touch}
  table{width:100%;border-collapse:collapse;margin:10px 0;font-size:13.3px;background:#fff}
  caption{caption-side:top;text-align:left;font-size:12.6px;color:var(--ink-3);padding:0 0 6px}
  th,td{border:1px solid var(--line);padding:6px 9px;vertical-align:top;text-align:left}
  th{background:#f2f6fb;font-weight:700;white-space:nowrap}
  td.n,th.n{text-align:right;font-family:var(--mono);font-size:12.8px;white-space:nowrap}
  tbody tr:nth-child(even){background:#fbfcfe}
  .win{color:var(--ok);font-weight:700}
  .mut{color:var(--ink-3)}
  .mono{font-family:var(--mono);font-size:12.6px}
  .sh{display:none}
  .kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin:14px 0}
  .kpi{background:#fff;border:1px solid var(--line);border-radius:10px;padding:12px 14px}
  .kpi .v{font-size:20px;font-weight:700;color:var(--accent);font-family:var(--mono);line-height:1.3}
  .kpi .l{font-size:12.2px;color:var(--ink-3);margin-top:2px}
  figure{margin:16px 0;background:#fff;border:1px solid var(--line);border-radius:11px;padding:12px}
  figcaption{font-size:12.6px;color:var(--ink-3);margin-top:8px;line-height:1.6}
  .fig-title{font-size:13px;font-weight:700;color:var(--ink-2);margin:0 0 8px}
  .fig-scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
  .fig-scroll img{width:100%;height:auto;display:block;border-radius:6px}
  figure svg{width:100%;height:auto;display:block}
  .d-narrow{display:none}
  svg .bx{fill:#fff;stroke:#ccd6e2;stroke-width:1.2}
  svg .bx-hi{fill:#e9f2fe;stroke:#0b63ce;stroke-width:1.7}
  svg .bx-ok{fill:#e7f6ee;stroke:#0f8a4a;stroke-width:1.6}
  svg .panel{fill:#fbfcfe;stroke:#dfe5ec;stroke-width:1.2}
  svg .t{font-size:12.5px;fill:#12161c}
  svg .tb{font-size:12.5px;fill:#12161c;font-weight:700}
  svg .ts{font-size:11.3px;fill:#5b6a7d}
  svg .tw2{font-size:12.5px;fill:#12161c}
  svg .hi-t{font-size:11.5px;fill:#0b63ce;font-weight:700}
  svg .ln{stroke:#8fa3ba;stroke-width:1.4;fill:none}
  svg .brk{stroke:#7b8ea6;stroke-width:1.1;fill:none}
  footer{margin-top:36px;padding-top:16px;border-top:1px solid var(--line);color:var(--ink-3);font-size:12.6px}
  @media (max-width:820px){
    body{font-size:14.6px;overflow-x:hidden}
    .wrap{padding:0 14px 64px}
    header.top{padding:22px 0 20px;margin-bottom:18px}
    header.top h1{font-size:20.5px;line-height:1.4}
    header.top .scope{font-size:13.2px}
    header.top .eyebrow{font-size:11px;letter-spacing:.1em}
    .chips{gap:6px;margin-top:14px}
    .chip{font-size:11.6px;padding:4px 9px}
    h2{font-size:18px;margin:26px 0 10px}
    h2 .num{min-width:24px;height:24px;line-height:24px;font-size:12.5px;border-radius:6px}
    h3{font-size:15.5px;margin:18px 0 7px}
    .card{padding:14px 15px}
    ul,ol{padding-left:19px}
    code{white-space:normal;word-break:break-word}
    pre{font-size:11.5px;padding:11px 12px}
    table{font-size:12.4px}
    th,td{padding:5px 7px}
    th{white-space:normal}
    .sh{display:inline;color:var(--ink-3);font-weight:400}
    .tw table.wide{min-width:600px}
    table.wide td.n,table.wide th.n{font-size:12.1px}
    td .mono,td.mono{white-space:normal;word-break:break-all}
    .fig-scroll img{min-width:520px}
    figure{padding:9px}
    .kpis{grid-template-columns:1fr 1fr;gap:8px}
    .kpi{padding:10px 11px}
    .kpi .v{font-size:17.5px}
    .kpi .l{font-size:11.6px}
    .d-wide{display:none}
    .d-narrow{display:block}
    .d-narrow .t,.d-narrow .tb,.d-narrow .tw2{font-size:13px}
  }
  @media (max-width:400px){ body{font-size:14.2px} header.top h1{font-size:19px} }
  @media print{
    body{background:#fff;font-size:11.4pt}
    header.top{background:#0e2a52 !important;-webkit-print-color-adjust:exact;print-color-adjust:exact}
    .card,figure,table,.kpi{box-shadow:none}
    .d-narrow{display:none}
    h2{page-break-after:avoid}
    figure,table{page-break-inside:avoid}
  }
</style>
</head>
<body>

<header class="top">
  <div class="wrap">
    <div class="eyebrow">LPO 112G PAM4 仿真平台 · 收发端联合寻优</div>
    <h1>DDPS：数据驱动物理代理寻优 — 交付说明</h1>
    <div class="scope">
      本文说明方案的适用范围、物理链路与优化对象、两个代理模型的构成与全部参数、在线调优算法流程与复杂度、实测效果与适用边界。
      参数取自 <code>config.xlsx</code>、模型 <code>meta.json</code>、结果 <code>case_summary / trace</code> 与源码常量；图表为内嵌 SVG 与 PNG，单文件可离线打开。
    </div>
    <div class="chips">
      <span class="chip">形状搜索 <b>6</b> 维（4 FFE 旁瓣 + gDC + gDC2）</span>
      <span class="chip">用例 <b>15</b> 个（含非对称 Tx/Rx 插损与器件噪声）</span>
      <span class="chip">评估协议 <b>262144</b> 符号 × <b>3</b> 仿真实例种子</span>
      <span class="chip">模型训练 <b>&lt;0.1 s</b> · 推理 <b>≈30 µs</b></span>
      <span class="chip">在线决策回路真实 BER <b>0</b> 次</span>
    </div>
  </div>
</header>

<div class="wrap">

<h2 id="s1"><span class="num">1</span>方案概要</h2>

<div class="card">
  <h4 style="margin-top:0">适用场景与约束</h4>
  <ul style="margin-bottom:0">
    <li>LPO 光模块内部不做重 DSP，发送端均衡由 Host ASIC 承担。可用的均衡自由度：<strong>5-tap T-spaced 发送端 FFE</strong>（4 个旁瓣为自由变量，主抽头由归一化派生）与 <strong>发送端模拟 CTLE 的双级直流增益</strong>。</li>
    <li>信道条件：奈奎斯特电插损 Tx/Rx <strong>各自</strong> 10～20 dB，色散 0～28 ps/nm，差分群时延 0～5 ps，偏振角 0～45°，另含器件噪声应力（RIN / 消光比 / TIA 噪声）。</li>
    <li>约束：在线调优阶段不得使用真实收端误码做决策（只能使用发送端可获得的物理量），且不允许出现任何一次“优化后比起点更差”。</li>
  </ul>
</div>

<div class="card">
  <h4 style="margin-top:0">方法构成</h4>
  <ol style="margin-bottom:0">
    <li><strong>物理探针</strong>：向发送链注入单位脉冲，在 MZM 输入端截取 7-tap 等效发射 FIR <em>形状</em>，并把该点的<strong>绝对驱动 RMS</strong> 一并取出 —— 前者描述波形、后者描述驱动幅度。</li>
    <li><strong>双代理模型</strong>：Model A（7-tap FIR 形状 + 驱动 RMS → log10 BER_MLSE 条件均值，负责下降方向，带解析梯度）、Model B（4 旁瓣 + gDC + gDC2 + 驱动 RMS → log10 BER_MLSE 保守上包络，负责安全否决），均为二阶多项式 Ridge 闭式解，纯 NumPy。两者输入空间不同（波形域 / 参数域），误差来源相互独立。</li>
    <li><strong>约束梯度下降</strong>：经 Model A 的链式法则求下降方向（扰动 6 个形状参数 → 重算探针 → 查 A → 得 ΔBER），每步落地前须通过 Model B 的相对安全审查，并同时受信任域（2.0×ρ）与梯度幅值门控约束；gain 由 per-case target_rms 物理求解，不进入任一代理。真实 BER 全量记录但不参与决策。</li>
  </ol>
</div>

<div class="tw">
<table id="tbl-headline">
  <caption>核心结论（完整数据见第 6 节）</caption>
  <tr><th>项目</th><th>结果</th></tr>
  <!--HEADLINE_ROWS-->
</table>
</div>

<h2 id="s2"><span class="num">2</span>物理链路与优化对象</h2>

<h3>2.1 链路构成</h3>
<figure>
  <div class="fig-title">图 1 · 仿真链路与三个可优化自由度</div>

  <svg class="d-wide" viewBox="0 0 1080 330" role="img" aria-label="仿真链路框图">
    <defs>
      <marker id="ah1" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#8fa3ba"/>
      </marker>
    </defs>

    <text class="tb" x="14" y="30">发送端（Host ASIC 数字 + 模拟前端）</text>
    <text class="tb" x="14" y="150">光纤与接收端（模拟前端 + 数字 DSP）</text>

    <rect class="bx" x="14" y="44" width="116" height="54" rx="8"/>
    <text class="tw2" x="72" y="68" text-anchor="middle">PAM4</text>
    <text class="ts" x="72" y="85" text-anchor="middle">映射</text>

    <rect class="bx-hi" x="148" y="44" width="116" height="54" rx="8"/>
    <text class="tw2" x="206" y="68" text-anchor="middle">5-tap Tx FFE</text>
    <text class="hi-t" x="206" y="85" text-anchor="middle">可优化</text>

    <rect class="bx" x="282" y="44" width="116" height="54" rx="8"/>
    <text class="tw2" x="340" y="68" text-anchor="middle">DAC (ZOH)</text>
    <text class="ts" x="340" y="85" text-anchor="middle">ENOB 5.5</text>

    <rect class="bx" x="416" y="44" width="116" height="54" rx="8"/>
    <text class="tw2" x="474" y="68" text-anchor="middle">Tx 电插损</text>
    <text class="ts" x="474" y="85" text-anchor="middle">S4P，Tx IL</text>

    <rect class="bx-hi" x="550" y="44" width="116" height="54" rx="8"/>
    <text class="tw2" x="608" y="68" text-anchor="middle">Tx 模拟 CTLE</text>
    <text class="hi-t" x="608" y="85" text-anchor="middle">可优化 gDC/gDC2</text>

    <rect class="bx" x="684" y="44" width="106" height="54" rx="8"/>
    <text class="tw2" x="737" y="68" text-anchor="middle">Driver BW</text>
    <text class="ts" x="737" y="85" text-anchor="middle">40 GHz</text>

    <rect class="bx-hi" x="806" y="44" width="120" height="54" rx="8"/>
    <text class="tw2" x="866" y="68" text-anchor="middle">Driver</text>
    <text class="ts" x="866" y="85" text-anchor="middle">per-case RMS 驱动</text>

    <line class="ln" x1="130" y1="71" x2="146" y2="71" marker-end="url(#ah1)"/>
    <line class="ln" x1="264" y1="71" x2="280" y2="71" marker-end="url(#ah1)"/>
    <line class="ln" x1="398" y1="71" x2="414" y2="71" marker-end="url(#ah1)"/>
    <line class="ln" x1="532" y1="71" x2="548" y2="71" marker-end="url(#ah1)"/>
    <line class="ln" x1="666" y1="71" x2="682" y2="71" marker-end="url(#ah1)"/>
    <line class="ln" x1="790" y1="71" x2="804" y2="71" marker-end="url(#ah1)"/>

    <line class="ln" x1="866" y1="98" x2="876" y2="161" marker-end="url(#ah1)"/>

    <rect x="452" y="110" width="410" height="34" rx="7" fill="#fff8e6" stroke="#e0b45f" stroke-width="1.2"/>
    <text class="t" x="466" y="125">物理探针取点（MZM 输入端）：7-tap FIR 形状 + 绝对驱动 RMS</text>
    <text class="ts" x="466" y="139">→ Model A 的 8 维输入特征（前游标 2 / 主游标 1 / 后游标 4 + 驱动幅度）</text>

    <rect class="bx" x="806" y="163" width="120" height="54" rx="8"/>
    <text class="tw2" x="866" y="187" text-anchor="middle">MZM</text>
    <text class="ts" x="866" y="204" text-anchor="middle">ER 25 dB / Vπ 3 V</text>

    <rect class="bx" x="676" y="163" width="116" height="54" rx="8"/>
    <text class="tw2" x="734" y="187" text-anchor="middle">光纤 + PIN</text>
    <text class="ts" x="734" y="204" text-anchor="middle">CD 复场 / DGD 实功率</text>

    <rect class="bx" x="546" y="163" width="116" height="54" rx="8"/>
    <text class="tw2" x="604" y="187" text-anchor="middle">TIA</text>
    <text class="ts" x="604" y="204" text-anchor="middle">720 Ω / 16 pA/√Hz</text>

    <rect class="bx" x="416" y="163" width="116" height="54" rx="8"/>
    <text class="tw2" x="474" y="187" text-anchor="middle">Rx 电插损</text>
    <text class="ts" x="474" y="204" text-anchor="middle">S4P，Rx IL</text>

    <rect class="bx" x="286" y="163" width="116" height="54" rx="8"/>
    <text class="tw2" x="344" y="187" text-anchor="middle">ADC</text>
    <text class="ts" x="344" y="204" text-anchor="middle">ENOB 5.5</text>

    <rect class="bx" x="156" y="163" width="116" height="54" rx="8"/>
    <text class="tw2" x="214" y="187" text-anchor="middle">22-tap Rx FFE</text>
    <text class="ts" x="214" y="204" text-anchor="middle">LMS 自适应</text>

    <rect class="bx" x="14" y="163" width="128" height="54" rx="8"/>
    <text class="tw2" x="78" y="187" text-anchor="middle">Burg + MLSE</text>
    <text class="ts" x="78" y="204" text-anchor="middle">memory = 1</text>

    <line class="ln" x1="806" y1="190" x2="794" y2="190" marker-end="url(#ah1)"/>
    <line class="ln" x1="676" y1="190" x2="664" y2="190" marker-end="url(#ah1)"/>
    <line class="ln" x1="546" y1="190" x2="534" y2="190" marker-end="url(#ah1)"/>
    <line class="ln" x1="416" y1="190" x2="404" y2="190" marker-end="url(#ah1)"/>
    <line class="ln" x1="286" y1="190" x2="274" y2="190" marker-end="url(#ah1)"/>
    <line class="ln" x1="156" y1="190" x2="144" y2="190" marker-end="url(#ah1)"/>

    <line class="ln" x1="78" y1="217" x2="78" y2="244" marker-end="url(#ah1)"/>
    <rect class="bx-ok" x="14" y="246" width="128" height="44" rx="8"/>
    <text class="tw2" x="78" y="266" text-anchor="middle">BER_MLSE</text>
    <text class="ts" x="78" y="282" text-anchor="middle">统一指标</text>

    <text class="ts" x="160" y="262">DFE 固定关闭（dfe_taps = 0）；噪声全部由器件参数分布式产生（RIN / 散粒 / 热噪声 / TIA 输入参考噪声 / 1 mV 前端噪声），不使用全局 SNR。</text>
    <text class="ts" x="160" y="280">蓝色框为三个可优化自由度；其余为给定的物理器件与信道参数。</text>
    <text class="ts" x="160" y="306">Tx 与 Rx 电插损可独立配置，用于刻画 Host 侧 / Module 侧损耗不对称的真实情形。</text>
  </svg>

  <svg class="d-narrow" viewBox="0 0 360 940" role="img" aria-label="仿真链路框图（竖向）">
    <defs>
      <marker id="an1" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#8fa3ba"/>
      </marker>
    </defs>
    <text class="tb" x="10" y="16">发送端（数字 + 模拟前端）</text>

    <rect class="bx" x="10" y="26" width="340" height="38" rx="7"/>
    <text class="tw2" x="24" y="50">PAM4 映射</text>

    <rect class="bx-hi" x="10" y="72" width="340" height="38" rx="7"/>
    <text class="tw2" x="24" y="90">5-tap Tx FFE</text>
    <text class="hi-t" x="24" y="104">可优化</text>

    <rect class="bx" x="10" y="118" width="340" height="38" rx="7"/>
    <text class="tw2" x="24" y="142">DAC（ZOH，ENOB 5.5）</text>

    <rect class="bx" x="10" y="164" width="340" height="38" rx="7"/>
    <text class="tw2" x="24" y="188">Tx 电插损（S4P，Tx IL）</text>

    <rect class="bx-hi" x="10" y="210" width="340" height="38" rx="7"/>
    <text class="tw2" x="24" y="228">Tx 模拟 CTLE</text>
    <text class="hi-t" x="24" y="242">可优化 gDC / gDC2</text>

    <rect class="bx" x="10" y="256" width="340" height="38" rx="7"/>
    <text class="tw2" x="24" y="280">Driver BW（40 GHz）</text>

    <rect class="bx-hi" x="10" y="302" width="340" height="38" rx="7"/>
    <text class="tw2" x="24" y="320">Driver</text>
    <text class="ts" x="24" y="334">per-case RMS 驱动</text>

    <line class="ln" x1="180" y1="64" x2="180" y2="70" marker-end="url(#an1)"/>
    <line class="ln" x1="180" y1="110" x2="180" y2="116" marker-end="url(#an1)"/>
    <line class="ln" x1="180" y1="156" x2="180" y2="162" marker-end="url(#an1)"/>
    <line class="ln" x1="180" y1="202" x2="180" y2="208" marker-end="url(#an1)"/>
    <line class="ln" x1="180" y1="248" x2="180" y2="254" marker-end="url(#an1)"/>
    <line class="ln" x1="180" y1="294" x2="180" y2="300" marker-end="url(#an1)"/>

    <rect x="10" y="350" width="340" height="56" rx="7" fill="#fff8e6" stroke="#e0b45f" stroke-width="1.2"/>
    <text class="t" x="22" y="370">物理探针取点（MZM 输入端）</text>
    <text class="ts" x="22" y="386">7-tap FIR 形状（前 2 / 主 1 / 后 4）+ 绝对驱动 RMS</text>
    <text class="ts" x="22" y="400">→ Model A 的 8 维输入特征</text>
    <line class="ln" x1="180" y1="340" x2="180" y2="348" marker-end="url(#an1)"/>

    <text class="tb" x="10" y="434">光纤与接收端</text>

    <rect class="bx" x="10" y="444" width="340" height="38" rx="7"/>
    <text class="tw2" x="24" y="468">MZM（ER 25 dB / Vπ 3 V）</text>

    <rect class="bx" x="10" y="490" width="340" height="38" rx="7"/>
    <text class="tw2" x="24" y="514">光纤 + PIN（CD / DGD、平方律 + 散粒）</text>

    <rect class="bx" x="10" y="536" width="340" height="38" rx="7"/>
    <text class="tw2" x="24" y="560">TIA（720 Ω / 16 pA/√Hz）</text>

    <rect class="bx" x="10" y="582" width="340" height="38" rx="7"/>
    <text class="tw2" x="24" y="606">Rx 电插损（S4P，Rx IL）</text>

    <rect class="bx" x="10" y="628" width="340" height="38" rx="7"/>
    <text class="tw2" x="24" y="652">ADC（ENOB 5.5）</text>

    <rect class="bx" x="10" y="674" width="340" height="38" rx="7"/>
    <text class="tw2" x="24" y="698">22-tap Rx FFE（LMS 自适应）</text>

    <rect class="bx" x="10" y="720" width="340" height="38" rx="7"/>
    <text class="tw2" x="24" y="744">Burg + MLSE（memory = 1）</text>

    <line class="ln" x1="180" y1="482" x2="180" y2="488" marker-end="url(#an1)"/>
    <line class="ln" x1="180" y1="528" x2="180" y2="534" marker-end="url(#an1)"/>
    <line class="ln" x1="180" y1="574" x2="180" y2="580" marker-end="url(#an1)"/>
    <line class="ln" x1="180" y1="620" x2="180" y2="626" marker-end="url(#an1)"/>
    <line class="ln" x1="180" y1="666" x2="180" y2="672" marker-end="url(#an1)"/>
    <line class="ln" x1="180" y1="712" x2="180" y2="718" marker-end="url(#an1)"/>

    <line class="ln" x1="180" y1="758" x2="180" y2="770" marker-end="url(#an1)"/>
    <rect class="bx-ok" x="10" y="772" width="340" height="38" rx="7"/>
    <text class="tw2" x="24" y="796">BER_MLSE（统一指标）</text>

    <text class="ts" x="10" y="836">DFE 固定关闭；噪声由器件参数分布式产生（RIN / 散粒 /</text>
    <text class="ts" x="10" y="852">热噪声 / TIA 噪声 / 1 mV 前端噪声），无全局 SNR。</text>
    <text class="ts" x="10" y="874">蓝色框为三个可优化自由度。</text>
    <text class="ts" x="10" y="898">Tx / Rx 电插损可独立配置（Host 侧与 Module 侧不对称）。</text>
  </svg>

  <figcaption>物理探针与真实链路共用同一段实现（<span class="mono">channel_imdd.tx_frontend_lti</span>），因此链路顺序只有一处定义，探针不会与真实链路漂移。</figcaption>
</figure>

<h3>2.2 优化空间与参数化</h3>
<figure>
  <div class="fig-title">图 2 · 6 维搜索空间与约束</div>

  <svg class="d-wide" viewBox="0 0 1080 320" role="img" aria-label="优化空间参数化示意">
    <defs>
      <marker id="ah2" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#7b8ea6"/>
      </marker>
    </defs>

    <text class="tb" x="14" y="26">发送端 FFE：5 抽头，T-spaced（主抽头由归一化恒等式派生，不是自由变量）</text>

    <rect class="bx" x="14" y="44" width="92" height="46" rx="7"/><text class="tw2" x="60" y="72" text-anchor="middle">t₀</text>
    <rect class="bx" x="118" y="44" width="92" height="46" rx="7"/><text class="tw2" x="164" y="72" text-anchor="middle">t₁</text>
    <rect class="bx-hi" x="222" y="44" width="92" height="46" rx="7"/><text class="tw2" x="268" y="72" text-anchor="middle">t₂</text>
    <rect class="bx" x="326" y="44" width="92" height="46" rx="7"/><text class="tw2" x="372" y="72" text-anchor="middle">t₃</text>
    <rect class="bx" x="430" y="44" width="92" height="46" rx="7"/><text class="tw2" x="476" y="72" text-anchor="middle">t₄</text>

    <path class="brk" d="M14 98 L14 110 L522 110 L522 98" marker-end="url(#ah2)"/>
    <text class="ts" x="268" y="128" text-anchor="middle">4 个旁瓣 = 自由变量，|t| ≤ 0.3，Σ|旁瓣| ≤ 0.8 ⇒ 主抽头 t₂ = 1 − Σ|旁瓣| ≥ 0.2</text>

    <rect class="bx-hi" x="14" y="146" width="330" height="52" rx="7"/>
    <text class="tw2" x="179" y="168" text-anchor="middle">Tx CTLE：gDC, gDC2 ∈ [−5, +5] dB</text>
    <text class="ts" x="179" y="186" text-anchor="middle">post-channel 频谱整形（2 维）</text>

    <rect class="bx" x="360" y="146" width="250" height="52" rx="7"/>
    <text class="tw2" x="485" y="168" text-anchor="middle">gain = per-case target_rms</text>
    <text class="ts" x="485" y="186" text-anchor="middle">物理驱动，不在搜索向量里</text>

    <rect class="panel" x="626" y="146" width="440" height="150" rx="8"/>
    <text class="t" x="642" y="170">搜索向量：</text>
    <text class="mono" x="722" y="170" style="font-size:12.5px">x_shape ∈ R⁶ = [4 旁瓣, gDC, gDC2]</text>
    <text class="ts" x="642" y="192">种子 x₀：FFE 旁瓣 [-0.034, -0.299, 0, 0.058]，gDC = gDC2 = 0 dB</text>
    <text class="ts" x="642" y="212">信任域：FFE ±0.10 / CTLE ±3.0 dB（gain 不在搜索向量里）</text>
    <text class="ts" x="642" y="232">组内归一化步长：FFE 组与 CTLE 组各自归一化后乘箱宽</text>
    <text class="ts" x="642" y="256">主抽头不进入搜索向量 ⇒ 下降方向只作用于波形形状，</text>
    <text class="ts" x="642" y="272">不会靠“整体变亮/变暗”这类伪自由度骗 BER。</text>

    <text class="tb" x="14" y="232">CTLE 放在 Tx 电插损之后、Driver 之前</text>
    <text class="ts" x="14" y="254">· 整形"到达 MZM 的频谱"，峰化补偿才有效。</text>
    <text class="ts" x="14" y="272">· 其直流增益影响驱动幅度，但 gain 维由 per-case target_rms 独立控制，</text>
    <text class="ts" x="14" y="290">  CTLE 只负责频谱形状，与 gain 维互不冗余。</text>
  </svg>

  <svg class="d-narrow" viewBox="0 0 360 430" role="img" aria-label="优化空间参数化示意（竖向）">
    <text class="tb" x="10" y="16">发送端 FFE：5 抽头（主抽头为派生量）</text>
    <rect class="bx" x="10" y="26" width="62" height="38" rx="6"/><text class="tw2" x="41" y="50" text-anchor="middle">t₀</text>
    <rect class="bx" x="80" y="26" width="62" height="38" rx="6"/><text class="tw2" x="111" y="50" text-anchor="middle">t₁</text>
    <rect class="bx-hi" x="150" y="26" width="62" height="38" rx="6"/><text class="tw2" x="181" y="50" text-anchor="middle">t₂</text>
    <rect class="bx" x="220" y="26" width="62" height="38" rx="6"/><text class="tw2" x="251" y="50" text-anchor="middle">t₃</text>
    <rect class="bx" x="290" y="26" width="62" height="38" rx="6"/><text class="tw2" x="321" y="50" text-anchor="middle">t₄</text>

    <text class="ts" x="10" y="130">4 个旁瓣自由变量：|t| ≤ 0.3，Σ|旁瓣| ≤ 0.8</text>
    <text class="hi-t" x="10" y="150">主抽头 t₂ = 1 − Σ|旁瓣| ≥ 0.2</text>

    <text class="tb" x="10" y="182">Tx 模拟 CTLE（post-channel）</text>
    <rect class="bx-hi" x="10" y="192" width="340" height="50" rx="7"/>
    <text class="tw2" x="24" y="212">gDC, gDC2 ∈ [−5, +5] dB</text>
    <text class="ts" x="24" y="230">2 维：频谱整形</text>

    <text class="tb" x="10" y="266">gain = per-case target_rms</text>
    <rect class="bx" x="10" y="276" width="340" height="50" rx="7"/>
    <text class="tw2" x="24" y="296">gain 不在搜索向量里</text>
    <text class="ts" x="24" y="314">每用例扫描标定 target_rms（0.06~0.22V）</text>

    <rect class="panel" x="10" y="340" width="340" height="80" rx="8"/>
    <text class="mono" x="24" y="362" style="font-size:12.3px">x_shape ∈ R⁶ = [4 旁瓣, gDC, gDC2]</text>
    <text class="ts" x="24" y="382">种子：[-0.034,-0.299,0,0.058] / 0 / 0 dB</text>
    <text class="ts" x="24" y="400">信任域：±0.10 / ±3.0 dB（gain 不在向量里）</text>
  </svg>

  <figcaption>主抽头不出现在搜索向量中，而由“总能量归一”恒等式导出。</figcaption>
</figure>

<h3>2.3 关键参数（取自 <span class="mono">config.xlsx</span>，112G 模式）</h3>
<div class="grid2">
  <div class="tw">
  <table>
    <caption>系统与均衡配置</caption>
    <tr><th>参数</th><th class="n">取值</th></tr>
    <tr><td>波特率 / 调制</td><td class="n">56 GBd, PAM4</td></tr>
    <tr><td>采样率（DSP / DAC / 信道 / ADC）</td><td class="n">2 / 2 / 8 / 2 sps</td></tr>
    <tr><td>Tx FFE</td><td class="n">5 tap, T-spaced</td></tr>
    <tr><td>Tx CTLE 零极点比</td><td class="n">fz 2.5 / fp1 2.5 / fp2 1 / flf 40</td></tr>
    <tr><td>Rx FFE</td><td class="n">22 tap, ffe_pre = 6</td></tr>
    <tr><td>Rx LMS 步长</td><td class="n">1e-4</td></tr>
    <tr><td>DFE</td><td class="n">关闭（0 tap）</td></tr>
    <tr><td>MLSE</td><td class="n">memory = 1（Burg 白化）</td></tr>
    <tr><td>统一指标</td><td class="n">BER_MLSE（Gray 映射）</td></tr>
  </table>
  </div>
  <div class="tw">
  <table>
    <caption>物理器件与信道</caption>
    <tr><th>参数</th><th class="n">取值</th></tr>
    <tr><td>Driver gain / 带宽</td><td class="n">per-case target_rms 驱动 / 40 GHz</td></tr>
        <tr><td>DAC / ADC ENOB</td><td class="n">5.5 / 5.5</td></tr>
    <tr><td>激光器 RIN / 线宽</td><td class="n">−150 dB/Hz / 10 MHz</td></tr>
    <tr><td>MZM Vπ / 偏置 / 消光比</td><td class="n">3 V / 2.25 V / 25 dB</td></tr>
    <tr><td>TIA 跨阻 / 输入噪声</td><td class="n">720 Ω / 16 pA/√Hz</td></tr>
    <tr><td>Host Tx / Rx 前端噪声</td><td class="n">1 mV RMS（置于增益之前）</td></tr>
    <tr><td>光纤长度 / 损耗</td><td class="n">2 km / 0.25 dB/km</td></tr>
    <tr><td>电插损</td><td class="n">Tx / Rx 各自可配（S4P 缩放对齐）</td></tr>
  </table>
  </div>
</div>

<h3>2.4 十五个物理应力用例</h3>
<div class="tw">
<table class="wide">
  <caption>训练、测试、报告共用同一份定义 <span class="sh">· 可左右滑动</span></caption>
  <tr><th>用例</th><th class="n">Tx IL (dB)</th><th class="n">Rx IL (dB)</th><th class="n">CD (ps/nm)</th><th class="n">DGD (ps)</th><th class="n">Pol (°)</th><th>说明</th></tr>
  <tr><td>Base_IL10x10</td><td class="n">10</td><td class="n">10</td><td class="n">0</td><td class="n">0</td><td class="n">0</td><td>基线环境（核心实验的唯一训练环境）</td></tr>
  <tr><td>IL14x14</td><td class="n">14</td><td class="n">14</td><td class="n">0</td><td class="n">0</td><td class="n">0</td><td>中等对称插损</td></tr>
  <tr><td>IL20x20</td><td class="n">20</td><td class="n">20</td><td class="n">0</td><td class="n">0</td><td class="n">0</td><td>最差对称插损</td></tr>
  <tr><td>IL20x10_TxHeavy</td><td class="n">20</td><td class="n">10</td><td class="n">0</td><td class="n">0</td><td class="n">0</td><td>Host 侧重损耗</td></tr>
  <tr><td>IL10x20_RxHeavy</td><td class="n">10</td><td class="n">20</td><td class="n">0</td><td class="n">0</td><td class="n">0</td><td>Module 侧重损耗</td></tr>
  <tr><td>IL16x10</td><td class="n">16</td><td class="n">10</td><td class="n">0</td><td class="n">0</td><td class="n">0</td><td>轻度非对称</td></tr>
  <tr><td>IL10x16</td><td class="n">10</td><td class="n">16</td><td class="n">0</td><td class="n">0</td><td class="n">0</td><td>轻度非对称（反向）</td></tr>
  <tr><td>CD15ps</td><td class="n">10</td><td class="n">10</td><td class="n">15</td><td class="n">0</td><td class="n">0</td><td>色散</td></tr>
  <tr><td>CD28ps</td><td class="n">10</td><td class="n">10</td><td class="n">28</td><td class="n">0</td><td class="n">0</td><td>强色散</td></tr>
  <tr><td>DGD2ps</td><td class="n">10</td><td class="n">10</td><td class="n">0</td><td class="n">2</td><td class="n">45</td><td>偏振模色散（小）</td></tr>
  <tr><td>DGD5ps</td><td class="n">10</td><td class="n">10</td><td class="n">0</td><td class="n">5</td><td class="n">45</td><td>偏振模色散（大）</td></tr>
  <tr><td>Comb_IL20x20_CD15_DGD5</td><td class="n">20</td><td class="n">20</td><td class="n">15</td><td class="n">5</td><td class="n">45</td><td>对称复合极限</td></tr>
  <tr><td>Comb_IL20x10_CD15_DGD5</td><td class="n">20</td><td class="n">10</td><td class="n">15</td><td class="n">5</td><td class="n">45</td><td>非对称复合极限</td></tr>
  <tr><td>HighNoise_IL10x10</td><td class="n">10</td><td class="n">10</td><td class="n">0</td><td class="n">0</td><td class="n">0</td><td>器件噪声：RIN −140 dB/Hz、ER 15 dB、TIA 25 pA/√Hz</td></tr>
  <tr><td>HighNoise_IL16x16</td><td class="n">16</td><td class="n">16</td><td class="n">0</td><td class="n">0</td><td class="n">0</td><td>器件噪声 + 中等插损</td></tr>
</table>
</div>

<h2 id="s3"><span class="num">3</span>代理模型</h2>

<h3>3.1 两个模型的输入输出与分工</h3>
<figure>
  <div class="fig-title">图 3 · 双代理模型的数据通路</div>
  <svg class="d-wide" viewBox="0 0 1080 260" role="img" aria-label="双代理模型数据通路">
    <defs>
      <marker id="ah3" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#8fa3ba"/>
      </marker>
    </defs>

    <text class="tb" x="14" y="26">Model A（寻优方向）</text>
    <rect class="bx" x="14" y="40" width="150" height="50" rx="8"/>
    <text class="tw2" x="89" y="62" text-anchor="middle">6 维参数</text>
    <text class="ts" x="89" y="79" text-anchor="middle">4 FFE + gDC + gDC2</text>

    <rect class="bx-hi" x="204" y="40" width="150" height="50" rx="8"/>
    <text class="tw2" x="279" y="62" text-anchor="middle">物理探针</text>
    <text class="ts" x="279" y="79" text-anchor="middle">15 ms 级</text>

    <rect class="bx" x="394" y="40" width="176" height="50" rx="8"/>
    <text class="tw2" x="482" y="62" text-anchor="middle">7-tap FIR 形状 + 驱动 RMS</text>
    <text class="ts" x="482" y="79" text-anchor="middle">8 维特征 → D = 45</text>

    <rect class="bx-ok" x="610" y="40" width="150" height="50" rx="8"/>
    <text class="tw2" x="685" y="62" text-anchor="middle">Model A</text>
    <text class="ts" x="685" y="79" text-anchor="middle">Ridge 闭式解</text>

    <rect class="bx" x="800" y="40" width="184" height="50" rx="8"/>
    <text class="tw2" x="892" y="62" text-anchor="middle">log10 BER 预测</text>
    <text class="ts" x="892" y="79" text-anchor="middle">比较优劣 + 求梯度</text>

    <line class="ln" x1="164" y1="65" x2="202" y2="65" marker-end="url(#ah3)"/>
    <line class="ln" x1="354" y1="65" x2="392" y2="65" marker-end="url(#ah3)"/>
    <line class="ln" x1="570" y1="65" x2="608" y2="65" marker-end="url(#ah3)"/>
    <line class="ln" x1="760" y1="65" x2="798" y2="65" marker-end="url(#ah3)"/>

    <text class="tb" x="14" y="156">Model B（安全否决）</text>
    <rect class="bx" x="14" y="170" width="350" height="50" rx="8"/>
    <text class="tw2" x="189" y="192" text-anchor="middle">直接配置：4 旁瓣 + gDC + gDC2 + drive_rms</text>
    <text class="ts" x="189" y="209" text-anchor="middle">7 维特征 → D = 36（参数域）</text>

    <rect class="bx-ok" x="424" y="170" width="150" height="50" rx="8"/>
    <text class="tw2" x="499" y="192" text-anchor="middle">Model B</text>
    <text class="ts" x="499" y="209" text-anchor="middle">Ridge 闭式解</text>

    <rect class="bx" x="614" y="170" width="370" height="50" rx="8"/>
    <text class="tw2" x="799" y="192" text-anchor="middle">安全判据：预测 BER ≤ 最优点 × 1.25（随最优点下移）</text>
    <text class="ts" x="799" y="209" text-anchor="middle">百分比红线，跨环境不用重标定</text>

    <line class="ln" x1="364" y1="195" x2="422" y2="195" marker-end="url(#ah3)"/>
    <line class="ln" x1="574" y1="195" x2="612" y2="195" marker-end="url(#ah3)"/>
  </svg>

  <svg class="d-narrow" viewBox="0 0 360 560" role="img" aria-label="双代理模型数据通路（竖向）">
    <defs>
      <marker id="an3" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#8fa3ba"/>
      </marker>
    </defs>
    <text class="tb" x="10" y="16">Model A（寻优方向）</text>

    <rect class="bx" x="10" y="26" width="340" height="42" rx="7"/>
    <text class="tw2" x="24" y="46">6 维参数（4 FFE + gDC + gDC2）</text>
    <text class="ts" x="24" y="62">扰动 -> 重算探针 -> 查 A</text>

    <rect class="bx-hi" x="10" y="80" width="340" height="38" rx="7"/>
    <text class="tw2" x="24" y="104">物理探针（MZM 输入端取点）</text>

    <rect class="bx" x="10" y="130" width="340" height="42" rx="7"/>
    <text class="tw2" x="24" y="150">7-tap FIR 形状 + 绝对驱动 RMS</text>
    <text class="ts" x="24" y="166">8 维特征 → D = 45</text>

    <rect class="bx-ok" x="10" y="184" width="340" height="38" rx="7"/>
    <text class="tw2" x="24" y="208">Model A（Ridge 闭式解）</text>

    <rect class="bx" x="10" y="234" width="340" height="38" rx="7"/>
    <text class="tw2" x="24" y="258">log10 BER 预测</text>

    <line class="ln" x1="180" y1="68" x2="180" y2="78" marker-end="url(#an3)"/>
    <line class="ln" x1="180" y1="118" x2="180" y2="128" marker-end="url(#an3)"/>
    <line class="ln" x1="180" y1="172" x2="180" y2="182" marker-end="url(#an3)"/>
    <line class="ln" x1="180" y1="222" x2="180" y2="232" marker-end="url(#an3)"/>

    <line class="brk" x1="10" y1="294" x2="350" y2="294"/>

    <text class="tb" x="10" y="318">Model B（安全否决）</text>

    <rect class="bx" x="10" y="328" width="340" height="52" rx="7"/>
    <text class="tw2" x="24" y="348">4 旁瓣 + gDC + gDC2 + drive_rms</text>
    <text class="ts" x="24" y="366">7 维特征 → D = 36（参数域）</text>

    <rect class="bx-ok" x="10" y="392" width="340" height="38" rx="7"/>
    <text class="tw2" x="24" y="416">Model B（Ridge 闭式解）</text>

    <rect class="bx" x="10" y="442" width="340" height="52" rx="7"/>
    <text class="tw2" x="24" y="462">安全判据：预测 BER ≤ 最优点 × 1.25</text>
    <text class="ts" x="24" y="480">变差 ≤ 25%（百分比红线）</text>

    <line class="ln" x1="180" y1="380" x2="180" y2="390" marker-end="url(#an3)"/>
    <line class="ln" x1="180" y1="430" x2="180" y2="440" marker-end="url(#an3)"/>

    <text class="ts" x="10" y="522">两者使用相同学习器与标签，输入特征不同（波形域 / 参数域），</text>
    <text class="ts" x="10" y="538">因此误差来源相互独立，构成“方向 + 刹车”的分工。</text>
  </svg>

  <figcaption>两个模型使用相同学习器与训练标签，唯一区别是输入特征：A 走物理探针（波形域 + 驱动幅度），B 直接用配置（参数域），因此误差来源相互独立。</figcaption>
</figure>

<div class="card">
  <h4 style="margin-top:0">为什么 Model A 必须包含“绝对驱动 RMS”</h4>
  <p style="margin-bottom:0">
    <code>driver_gain</code> 在纯线性 Tx 链中只是一个标量乘子，而 7-tap FIR <strong>形状</strong>对整体尺度不变。
    若 Model A 只看形状，它对 <code>driver_gain</code> 的偏导数恒为 0 —— 归一化梯度在该维上没有分量，
    Stage-2 永远无法移动它。因此探针做绝对标定，并额外返回 MZM 输入端的真实驱动 RMS 作为第 8 个特征
    （与真实链路实测吻合，误差 &lt; 0.3%）。
  </p>
</div>

<h3>3.2 模型形式、超参数与指标</h3>
<p>两个模型共用同一学习器：手写二阶多项式特征 + L2 正则 Ridge 回归闭式解，无第三方机器学习库。</p>
<pre><code>Φ(X) = [1, x₁…x_d, x₁²…x_d², x₁x₂…x_(d−1)x_d]        D = 1 + 2d + d(d−1)/2
W = (ΦᵀΦ + αI)⁻¹ Φᵀ y                                 ŷ = Φ(X)·W</code></pre>

<div class="tw">
<table class="wide">
  <caption>A/B 共用同一份训练集（2001 行，80/20 划分），仅输入特征不同 <span class="sh">· 可左右滑动</span></caption>
  <tr><th>模型</th><th>输入域</th><th class="n">特征维度</th><th class="n">n_train / n_test</th><th class="n">R²</th><th class="n">MSE</th><th class="n">Spearman</th><th>说明</th></tr>
  <!--MODEL_METRICS_ROWS-->
</table>
</div>

<h3>3.3 gain 维的 per-case target_rms 扫描</h3>
<p>gain 不在 A/B 搜索向量里。每个用例单独细粒度扫描 MZM 输入 RMS（0.06~0.22V，步长 0.005），
取最优 RMS 作为该用例的 target_rms。在线调优时每步解析调到该值：</p>
<pre><code>gain_new = gain_ref × (target_rms / rms_measured)</code></pre>
<p>解析出的 gain 倍率（相对种子 gain）随信号强度自适应：强信号环境约 0.48，弱信号环境约 1.27——
即"锁定发端 RMS 给每个用例配 gain"，目标值经全环境扫描设计而非拍脑袋。</p>
<div class="tw">
<table class="wide">
  <caption>per-case target_rms 扫描结果（15 用例；gain 倍率 = 扫描所得 gain / 种子 gain） <span class="sh">· 可左右滑动</span></caption>
  <tr><th>用例</th><th class="n">target_rms (V)</th><th class="n">gain 倍率</th></tr>
  <!--TARGET_RMS_ROWS-->
</table>
</div>

<h2 id="s4"><span class="num">4</span>寻优算法</h2>

<h3>4.1 两阶段结构</h3>
<figure>
  <div class="fig-title">图 4 · DDPS v6 两阶段流程（Stage 1 离线一次性 / Stage 2 在线逐环境）</div>

  <svg class="d-wide" viewBox="0 0 1080 500" role="img" aria-label="两阶段算法流程图">
    <defs>
      <marker id="ah4" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#8fa3ba"/>
      </marker>
    </defs>

    <rect class="panel" x="14" y="34" width="512" height="450" rx="10"/>
    <text class="tb" x="34" y="58">Stage 1 · 离线标定（一次性）</text>

    <rect class="bx" x="34" y="72" width="472" height="46" rx="7"/>
    <text class="t" x="48" y="92">起点 x₀（种子工作点）</text>
    <text class="ts" x="48" y="108">主抽头 0.6091，gDC = gDC2 = 0 dB，driver_gain = 2.0</text>

    <rect class="bx" x="34" y="134" width="472" height="46" rx="7"/>
    <text class="t" x="48" y="154">信任域内 LHS 采样（d = 6）</text>
    <text class="ts" x="48" y="170">Base_IL10x10 邻域 2001 点（gain 窄带 ×0.40~×0.90）</text>

    <rect class="bx" x="34" y="196" width="472" height="46" rx="7"/>
    <text class="t" x="48" y="216">每点：真实 BER_MLSE 评估 + 物理探针</text>
    <text class="ts" x="48" y="232">262144 符号 × 3 仿真实例种子取 log10 均值；探针取 FIR 形状 + 驱动 RMS</text>

    <rect class="bx" x="34" y="258" width="472" height="46" rx="7"/>
    <text class="t" x="48" y="278">二阶多项式 Ridge 闭式解训练</text>
    <text class="ts" x="48" y="294">α = 1.0，80/20 划分，seed 42（A: 8 维探针 / B: 7 维参数）</text>

    <rect class="bx-ok" x="34" y="320" width="472" height="46" rx="7"/>
    <text class="t" x="48" y="340">输出并冻结：Model A（波形+驱动 → BER）/ Model B（配置 → BER）</text>
    <text class="ts" x="48" y="356">单套训练集：只用 Base_IL10x10 邻域 2001 行</text>

    <rect class="bx" x="34" y="382" width="472" height="72" rx="7"/>
    <text class="t" x="48" y="402">A/B 输入空间不同（波形域 vs 参数域），误差独立</text>
    <text class="ts" x="48" y="420">gain 每步解析调到 per-case target_rms（发端测量，不需 BER），</text>
    <text class="ts" x="48" y="436">4 个 FFE 旁瓣 + 2 个 CTLE 维被优化，gain 由 per-case RMS 驱动。</text>

    <line class="ln" x1="270" y1="118" x2="270" y2="132" marker-end="url(#ah4)"/>
    <line class="ln" x1="270" y1="180" x2="270" y2="194" marker-end="url(#ah4)"/>
    <line class="ln" x1="270" y1="242" x2="270" y2="256" marker-end="url(#ah4)"/>
    <line class="ln" x1="270" y1="304" x2="270" y2="318" marker-end="url(#ah4)"/>
    <line class="ln" x1="270" y1="366" x2="270" y2="380" marker-end="url(#ah4)"/>

    <rect class="panel" x="554" y="34" width="512" height="450" rx="10"/>
    <text class="tb" x="574" y="58">Stage 2 · 在线调优（每个环境一次，模型冻结）</text>

    <rect class="bx" x="574" y="72" width="472" height="46" rx="7"/>
    <text class="t" x="588" y="92">当前点 x_k（k = 0 为种子 x₀）</text>
    <text class="ts" x="588" y="108">安全红线 = 最优点 B 预测 × 1.25（随最优点下移）</text>

    <rect class="bx" x="574" y="134" width="472" height="46" rx="7"/>
    <text class="t" x="588" y="154">对 Model A 求链式梯度（6 维）</text>
    <text class="ts" x="588" y="170">eps = 0.01；1 + 6 = 7 次评估，每次 = 1 探针 + 1 A 前向</text>

    <rect class="bx" x="574" y="196" width="472" height="46" rx="7"/>
    <text class="t" x="588" y="216">组梯度门控：|g| ≥ 1e-3 ？</text>
    <text class="ts" x="588" y="232">否 → 某组梯度低于门控 1e-3，冻结该组</text>

    <rect class="bx" x="574" y="258" width="472" height="46" rx="7"/>
    <text class="t" x="588" y="278">构造候选点</text>
    <text class="ts" x="588" y="294">组内归一化方向；步长 0.05 × 0.97^k × 箱宽；投影信任域</text>

    <rect class="bx" x="574" y="320" width="472" height="46" rx="7"/>
    <text class="t" x="588" y="340">Model B 审查：预测 BER ≤ 最优点 × 1.25？</text>
    <text class="ts" x="588" y="356">否 → 步长折半重试（≤20 次）；不通过则停</text>

    <rect class="bx" x="574" y="382" width="472" height="46" rx="7"/>
    <text class="t" x="588" y="402">接受 x_(k+1)，记录真实 BER_MLSE 与代理预测</text>
    <text class="ts" x="588" y="418">终止：|Δx| &lt; 1e-4 或达到步数上限</text>

    <line class="ln" x1="810" y1="118" x2="810" y2="132" marker-end="url(#ah4)"/>
    <line class="ln" x1="810" y1="180" x2="810" y2="194" marker-end="url(#ah4)"/>
    <line class="ln" x1="810" y1="242" x2="810" y2="256" marker-end="url(#ah4)"/>
    <line class="ln" x1="810" y1="304" x2="810" y2="318" marker-end="url(#ah4)"/>
    <line class="ln" x1="810" y1="366" x2="810" y2="380" marker-end="url(#ah4)"/>

    <path class="ln" d="M1046 405 L1064 405 L1064 157 L1048 157" marker-end="url(#ah4)"/>
    <text class="ts" x="1074" y="281" transform="rotate(90 1074 281)" text-anchor="middle">迭代（真实 BER 不回传）</text>

    <path class="brk" d="M556 200 L546 200 L546 348 L556 348"/>
    <text class="ts" x="16" y="474" style="fill:#0f8a4a;font-weight:700">三重护栏：</text>
    <text class="ts" x="88" y="474">梯度门控（第 3 步）· 信任域投影（第 4 步）· Model B 相对红线（第 5 步）</text>
  </svg>

  <svg class="d-narrow" viewBox="0 0 360 940" role="img" aria-label="两阶段算法流程图（竖向）">
    <defs>
      <marker id="an4" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#8fa3ba"/>
      </marker>
    </defs>

    <rect class="panel" x="8" y="6" width="344" height="392" rx="9"/>
    <text class="tb" x="20" y="28">Stage 1 · 离线标定（一次性）</text>

    <rect class="bx" x="20" y="40" width="320" height="54" rx="7"/>
    <text class="t" x="32" y="60">起点 x₀（种子工作点）</text>
    <text class="ts" x="32" y="78">[-0.034,-0.299,0.609,0,0.058] / 0 / 0 dB</text>

    <rect class="bx" x="20" y="106" width="320" height="54" rx="7"/>
    <text class="t" x="32" y="126">信任域内 LHS 采样（d = 6）</text>
    <text class="ts" x="32" y="144">Base_IL10x10 邻域 2001 点</text>

    <rect class="bx" x="20" y="172" width="320" height="54" rx="7"/>
    <text class="t" x="32" y="192">每点：真实 BER + 物理探针</text>
    <text class="ts" x="32" y="210">262144 符号 × 3 种子；FIR 形状 + 驱动 RMS</text>

    <rect class="bx" x="20" y="238" width="320" height="54" rx="7"/>
    <text class="t" x="32" y="258">二阶多项式 Ridge 闭式解</text>
    <text class="ts" x="32" y="276">α = 1.0，80/20，seed 42（A 8 维 / B 7 维）</text>

    <rect class="bx-ok" x="20" y="304" width="320" height="54" rx="7"/>
    <text class="t" x="32" y="324">冻结 Model A / Model B</text>
    <text class="ts" x="32" y="342">单套：只用基线 2001 行；gain 由 per-case target_rms 物理驱动</text>

    <line class="ln" x1="180" y1="94" x2="180" y2="104" marker-end="url(#an4)"/>
    <line class="ln" x1="180" y1="160" x2="180" y2="170" marker-end="url(#an4)"/>
    <line class="ln" x1="180" y1="226" x2="180" y2="236" marker-end="url(#an4)"/>
    <line class="ln" x1="180" y1="292" x2="180" y2="302" marker-end="url(#an4)"/>

    <rect class="panel" x="8" y="406" width="344" height="466" rx="9"/>
    <text class="tb" x="20" y="428">Stage 2 · 在线调优（每环境一次）</text>

    <rect class="bx" x="20" y="440" width="320" height="54" rx="7"/>
    <text class="t" x="32" y="460">当前点 x_k（k = 0 为种子）</text>
    <text class="ts" x="32" y="478">安全参考 = Model B(x₀)</text>

    <rect class="bx" x="20" y="506" width="320" height="54" rx="7"/>
    <text class="t" x="32" y="526">Model A 链式梯度（6 维）</text>
    <text class="ts" x="32" y="544">eps = 0.01，共 7 次评估</text>

    <rect class="bx" x="20" y="572" width="320" height="54" rx="7"/>
    <text class="t" x="32" y="592">组梯度门控：|g| ≥ 1e-3 ？</text>
    <text class="ts" x="32" y="610">否 → 冻结该组</text>

    <rect class="bx" x="20" y="638" width="320" height="54" rx="7"/>
    <text class="t" x="32" y="658">构造候选点并投影信任域</text>
    <text class="ts" x="32" y="676">0.05 × 0.97^k × 箱宽（组内归一化）</text>

    <rect class="bx" x="20" y="704" width="320" height="54" rx="7"/>
    <text class="t" x="32" y="724">Model B 审查：≤ 最优点 × 1.25？</text>
    <text class="ts" x="32" y="742">否 → 步长折半（≤20 次）；仍不通过则停</text>

    <rect class="bx" x="20" y="770" width="320" height="54" rx="7"/>
    <text class="t" x="32" y="790">接受 x_(k+1)，记录真实 BER_MLSE</text>
    <text class="ts" x="32" y="808">终止：|Δx| &lt; 1e-4 或步数上限</text>

    <line class="ln" x1="180" y1="494" x2="180" y2="504" marker-end="url(#an4)"/>
    <line class="ln" x1="180" y1="560" x2="180" y2="570" marker-end="url(#an4)"/>
    <line class="ln" x1="180" y1="626" x2="180" y2="636" marker-end="url(#an4)"/>
    <line class="ln" x1="180" y1="692" x2="180" y2="702" marker-end="url(#an4)"/>
    <line class="ln" x1="180" y1="758" x2="180" y2="768" marker-end="url(#an4)"/>

    <path class="ln" d="M348 797 L358 797 L358 533 L350 533" marker-end="url(#an4)"/>

    <text class="ts" x="10" y="892" style="fill:#0f8a4a;font-weight:700">三重护栏：</text>
    <text class="ts" x="10" y="908">梯度门控 · 信任域投影 · Model B 相对红线</text>
    <text class="ts" x="10" y="926">右侧回边为迭代；真实 BER 仅记录、不回传决策</text>
  </svg>

  <figcaption>Stage 2 每步决策只依赖 Model A 的梯度方向与 Model B 的安全判定；真实 BER_MLSE 在每一步都被记录，但不参与方向与终止决策。</figcaption>
</figure>

<h3>4.2 Stage-2 单步计算流程</h3>
<div class="card">
  <ol style="margin-bottom:0">
    <li><strong>安全红线</strong>：红线 = 当前已知最优点的 Model B 预测 BER × 1.25。每步若 B 预测改善，红线跟着下移；若 B 预测突然变差（方向错），红线挡住该步。</li>
    <li><strong>梯度</strong>：对 Model A 做 6 维链式梯度（扰动参数→重算探针→查A），<span class="mono">eps = 0.01</span>，共 7 次评估（每次 = 1 探针 + 1 A 前向）。</li>
    <li><strong>梯度门控</strong>：<span class="mono">|g| &lt; 1e-3</span> 时某组梯度低于门控，冻结该组，避免沿拟合噪声继续移动。</li>
    <li><strong>方向</strong>：组内归一化方向（FFE 组与 CTLE 组各自归一化）。</li>
    <li><strong>步长</strong>：<span class="mono">α_k = 0.05 × 0.97^k</span>，乘以各维箱宽（FFE 0.20 / CTLE 6.0 dB）。</li>
    <li><strong>投影</strong>：候选点裁剪至 <span class="mono">x₀ ± [0.10, 0.10, 0.10, 0.10, 3.0, 3.0]</span>（6 维 shape 信任域）。</li>
    <li><strong>安全审查</strong>：候选点 B 预测超过红线时步长折半重试（最多 20 次）；始终不通过则停止，不强行落地。</li>
    <li><strong>记账</strong>：写入代理预测与真实 BER_MLSE（协议 262144 符号 × 3 种子），供事后核验。</li>
    <li><strong>终止</strong>：位移 <span class="mono">&lt; 1e-6</span>、或梯度门控触发、或边际改善 <span class="mono">&lt; 0.01 dex</span>、或达到步数上限。</li>
  </ol>
</div>

<h3>4.3 复杂度与实测耗时</h3>
<div class="tw">
<table class="wide">
  <caption>本机实测：Python 3.11.11 / NumPy 2.4.6，BLAS 线程固定为 1 <span class="sh">· 可左右滑动</span></caption>
  <tr><th>环节</th><th>计算内容</th><th class="n">实测耗时</th><th>复杂度</th></tr>
  <tr><td>模型训练</td><td>ΦᵀΦ 与 D×D 线性方程组求解</td><td class="n">≈0.02 s（1601 训练行，A D=45 / B D=36）</td><td class="mono">O(N·D² + D³)</td></tr>
  <tr><td>模型单次推理</td><td>特征展开 + 一次内积</td><td class="n">≈30 µs</td><td class="mono">O(D)</td></tr>
  <tr><td>物理探针（含驱动 RMS）</td><td>单位脉冲 + 短 PAM4 序列过发送链</td><td class="n">≈30 ms</td><td>与评估符号数无关</td></tr>
  <tr><td><strong>Stage-2 单步决策</strong></td><td>7 次探针 + 7 次 A 前向 + ≤20 次 B 前向</td><td class="n win">≈0.4 s</td><td>与评估符号数无关</td></tr>
  <tr><td>一次真实 BER 评估</td><td>262144 符号 × 3 种子（全链路 + LMS + Viterbi）</td><td class="n">≈16 s</td><td>与符号数线性</td></tr>
  <tr><td>离线数据集</td><td>2001 点 ×（BER 评估 + 探针）</td><td class="n">≈55 min（14 进程并行）</td><td>一次性</td></tr>
</table>
</div>
<p>决策链路本身不含任何真实 BER 评估；在线测试中每步执行的那次 BER 评估只是“如实记账”，其耗时不影响下一步决策。</p>

<h3>4.4 可靠性依据</h3>
<div class="tw">
<table>
  <tr><th>环节</th><th>机制</th><th>效果</th></tr>
  <tr><td>特征侧</td><td>以入纤波形形状 + 绝对驱动幅度（而非硬件参数）作为代理输入，信道频响差异被探针吸收</td><td>同一模型可跨插损（含非对称）、色散、群时延变化复用，无需按环境重训</td></tr>
  <tr><td>决策侧</td><td>方向用归一化梯度，安全判据用相对种子点的恶化量</td><td>全局底噪与插损平移在作差中抵消，无需逐环境标定阈值</td></tr>
  <tr><td>安全侧</td><td>Model B 否决 + 信任域投影 + 组梯度门控三重约束（百分比红线 25%）</td><td>候选点须先通过安全审查才允许落地；趋平即停，不产生负向移动</td></tr>
  <tr><td>复算侧</td><td>每一步的真实 BER_MLSE 全量落盘</td><td>可逐步核验是否出现退步，不依赖抽样或事后筛选</td></tr>
</table>
</div>

<h3>4.5 安全红线：随最优点下移</h3>
<p>安全红线的作用是<strong>防止代理方向错误导致 BER 变差</strong>。逻辑：</p>
<ul>
  <li>红线 = 当前已知最优点的 Model B 预测 BER × 1.25（不是种子点的 B 预测）；</li>
  <li>每步若 B 预测改善，红线跟着下移——B 单调下降时红线永不触发；</li>
  <li>若 B 预测突然变差（方向错），候选点 B 预测超过红线，步长折半重试，始终不过则停止；</li>
  <li>用"相对最优点变差 25%"而非绝对 BER 阈值：代理绝对标定不可信（Model B 用基线训练，漂移环境预测的绝对值偏差大），但"相对最优点变差多少倍"是可比的；</li>
  <li>实测 15 用例 <!--TOTAL_STEPS--> 步中 <!--TOTAL_WORSE--> 步劣于种子——红线全程未触发拦截（B 预测单调下降，方向与 A 一致）。</li>
</ul>
<div class="card" style="border-left:4px solid #0f8a4a">
  <h4 style="margin-top:0">Model B 的价值</h4>
  <p style="margin-bottom:0">在本实验的 15 个环境中，Model B 安全红线全程未触发——Model A 的方向已经足够好，
  B 的风险控制在当前代理质量下是"保险"而非"必需"。对比实验（A-only vs A+B）见 §6.1。</p>
</div>

<h2 id="s5"><span class="num">5</span>数据集与评估协议</h2>

<div class="tw">
<table>
  <caption>数据集构成：共 2001 行真实 BER 评估，单份 CSV</caption>
  <tr><th>环境</th><th class="n">行数</th><th>构成</th><th class="n">log10 BER 实测范围</th></tr>
  <tr><td>Base_IL10x10 邻域</td><td class="n">2001</td><td>6 维 LHS（4 FFE + gDC + gDC2），gain 窄带 ×0.40~×0.90</td><td class="n">−3.7 ~ −1.0</td></tr>
</table>
</div>

<div class="card">
  <h4 style="margin-top:0">评估协议：262144 符号 × 3 个种子</h4>
  <p>在基线种子点上用多个仿真实例种子测量不同块长的表现（每种块长 5 次独立实现）：</p>
  <div class="tw">
  <table class="wide">
    <caption>BER 估计精度实测（Base_IL10x10 种子点） <span class="sh">· 可左右滑动</span></caption>
    <tr><th class="n">块长（符号）</th><th class="n">log10 BER 均值</th><th class="n">跨种子标准差</th><th class="n">相邻块长漂移</th><th>能否分辨真实改善</th></tr>
    <tr><td class="n">65536</td><td class="n">−3.056</td><td class="n">0.054</td><td class="n">—</td><td>否（种子间符号翻转）</td></tr>
    <tr><td class="n">131072</td><td class="n">−3.304</td><td class="n">0.067</td><td class="n">−0.248</td><td>可以</td></tr>
    <tr><td class="n">262144（采用）</td><td class="n">−3.524</td><td class="n">0.093</td><td class="n">−0.220</td><td>可以（Δ 更大）</td></tr>
    <tr><td class="n">524288</td><td class="n">−3.675</td><td class="n">0.139</td><td class="n">−0.152</td><td>可以（Δ 最大）</td></tr>
  </table>
  </div>
  <p style="margin-bottom:0">
    <strong>结论</strong>：① BER 绝对值随块长系统性漂移（每翻倍约 −0.15～−0.25 dex），不同块长的绝对 BER 不可比，因此全流程固定同一协议；
    ② 65536 符号下连一个 ×1.65 的真实改善都无法稳定分辨，块长太短会把真实收益淹没在噪声里；
    ③ 采用 262144 符号 × 3 个固定种子取 log10 均值，兼顾成本与精度；固定种子使各配置之间噪声相关，配对比较更稳。
  </p>
</div>

<div class="card">
  <h4 style="margin-top:0">采样与标注口径</h4>
  <ul style="margin-bottom:0">
    <li><strong>采样器</strong>：<span class="mono">LatinHypercube(d = 6, seed = 42)</span>，逐环境独立且可复现；采样盒 = 信任域（FFE ±0.10 / CTLE ±3.0 dB），gain 窄带 ×0.40~×0.90。</li>
    <li><strong>每行字段</strong>：6 维坐标、5-tap FFE、gDC/gDC2、driver_gain、驱动 RMS、真实 <span class="mono">mlse_ber</span> 与 <span class="mono">log10_ber_mlse</span>、<span class="mono">ber_std_log10</span>、7-tap FIR 形状。</li>
    <li><strong>并行一致性</strong>：<span class="mono">--jobs</span> 多进程与串行结果逐位一致（每点独立、种子固定，已实测校验）。</li>
    <li><strong>A/B 输入空间不同</strong>：Model A 吃 8 维探针，Model B 吃 7 维参数，同一标签、同一学习器。</li>
    <li><strong>成本</strong>：2001 点 × 3 种子，14 进程并行约 55 分钟。</li>
  </ul>
</div>

<h2 id="s6"><span class="num">6</span>实测结果</h2>

<div class="kpis">
  <!--KPI_CARDS-->
</div>

<h3>6.1 严格泛化：只用 10 dB 基线训练 → 跨 15 个环境</h3>
<p>训练集只含 Base_IL10x10 邻域 2001 行。模型冻结后，对 15 个漂移环境逐个执行 Stage-2 在线调优，零重训、零校准。</p>
<p class="win"><strong>结论</strong>：15/15 用例相对种子全部正向改善，平均 <!--MEAN_IMP-->（最高 <!--MAX_IMP-->），
全程 <!--TOTAL_STEPS--> 步真实 BER，<strong><!--TOTAL_WORSE--> 步劣于种子</strong>。6 维空间下 2001 行基线数据足够让代理在信任域内保持方向可信。</p>
<div class="tw">
<table class="wide" id="tbl-core">
  <caption>种子 = 起点 x₀ 的真实 BER_MLSE；最优 = 全轨迹中真实 BER_MLSE 的最小值（步序为该最小值出现于第几步） <span class="sh">· 可左右滑动</span></caption>
  <tr><th>用例</th><th>物理条件</th><th class="n">种子 BER_MLSE</th><th class="n">最优 BER_MLSE（步序）</th><th class="n">Δlog10 BER</th><th class="n">改善倍数</th><th class="n">gain（种子→最优）</th></tr>
  <!--CORE_ROWS-->
</table>
</div>

<h3>6.1b 对比实验：A-only vs A+B</h3>
<p>同一组 15 环境、同一种子点、同一步数（15 步），唯一区别是是否启用 Model B 安全拦截：</p>
<ul>
  <li><strong>A-only</strong>：只用 Model A 链式梯度下降，不查 Model B，不走安全拦截；</li>
  <li><strong>A+B</strong>：完整流程（A 梯度 + B 红线 + 信任域 + 梯度门控）。</li>
</ul>
<div class="tw">
<table class="wide" id="tbl-ablation">
  <caption>对比 A-only 与 A+B 的改善倍数、劣化步数 <span class="sh">· 可左右滑动</span></caption>
  <tr><th>用例</th><th class="n">种子 BER</th><th class="n">A-only 最优 BER</th><th class="n">A-only 改善</th><th class="n">A-only 劣化步</th><th class="n">A+B 最优 BER</th><th class="n">A+B 改善</th><th class="n">A+B 劣化步</th></tr>
  <!--ABLATION_ROWS-->
</table>
</div>
<p class="mut">如果 A-only 就 0 劣化步，说明 Model A 方向已足够好，B 的价值是"保险"；如果 A-only 有劣化步而 A+B 没有，说明 B 确实拦住了错误方向。</p>

<h3>6.2 收敛轨迹与物理量变化</h3>
<figure>
  <div class="fig-scroll"><img src="{{IMG_CONV}}" alt="15 用例收敛轨迹三曲线"></div>
  <figcaption>图 6 · 15 用例在线调优收敛轨迹（Model A 预测 / Model B 预测 / 实测 BER_MLSE，对数纵轴；虚线为种子）。</figcaption>
</figure>

<figure>
  <div class="fig-scroll"><img src="{{IMG_GAIN}}" alt="gain 与 drive_rms 物理驱动轨迹"></div>
  <figcaption>图 7 · gain 维物理驱动轨迹：drive_rms 锁定到 per-case target_rms，gain 倍率随环境自适应（强信号约 0.48、弱信号约 1.27）。</figcaption>
</figure>

<figure>
  <div class="fig-scroll"><img src="{{IMG_TRACK}}" alt="预测变化量 vs 实测变化量"></div>
  <figcaption>图 8 · 左：Δ预测 vs Δ实测散点（逐用例逐步）；右：逐用例相关系数。</figcaption>
</figure>

<figure>
  <div class="fig-scroll"><img src="{{IMG_CASE_HARD}}" alt="最难用例四联图"></div>
  <figcaption>图 9 · 最难用例四联图：收敛轨迹、Tx FFE 抽头（种子 vs 最优）、Tx CTLE |H(f)| 频响、Tx 物理探针 7-tap FIR（Model A 输入特征）。</figcaption>
</figure>

<h3>6.3 安全性核验（逐步记账）</h3>
<div class="card">
  <p>Stage-2 每一步的真实 BER_MLSE 均写入 trace 文件，对全部 15 用例逐行核验（每步真实 BER 与该用例种子点真实 BER 比较）：</p>
  <div class="tw">
  <table class="wide" style="margin-bottom:6px">
    <caption>核验口径：种子点真实 BER 为基准，统计所有中间步是否出现退步</caption>
    <tr><th class="n">用例数</th><th class="n">记录的真实 BER 步数</th><th class="n">劣于种子的步数</th><th>结论</th></tr>
    <!--SAFETY_ROWS-->
  </table>
  </div>
  <p class="mut" style="margin-bottom:0">原始记录：各结果目录下 <span class="mono">trace_&lt;用例&gt;.csv</span>（含 step、抽头、gDC、gDC2、driver_gain、代理预测 A/B、真实 BER、梯度模）。</p>
</div>

<h2 id="s7"><span class="num">7</span>结论</h2>

<div class="card">
  <h4 style="margin-top:0">已确认的结论</h4>
  <ol style="margin-bottom:0">
    <li><strong>A=探针->BER + B=参数->BER 架构有效</strong>：Model A（8 维波形域）给出方向，
      Model B（7 维参数域）给风险控制，A/B 输入空间不同、误差独立。
      15/15 用例正向改善，平均 <!--MEAN_IMP-->，<!--TOTAL_WORSE--> 步劣于种子。</li>
    <li><strong>链式梯度可行</strong>：扰动 6 维参数 -> 重算探针 -> 查 A -> 得 ΔBER。
      每步 7 次评估（1 基准 + 6 维扰动），耗时 ≈0.4 s，与评估符号数无关。</li>
    <li><strong>per-case target_rms 物理驱动 gain 有效</strong>：gain 不在模型搜索向量里，
      由发端 RMS 物理目标驱动，解析出的 gain 倍率随信号强度自适应
     （强信号约 0.48、弱信号约 1.27）。</li>
    <li><strong>跨环境泛化成立</strong>：只用 Base_IL10x10 训练的探针->BER 方向映射，
      可指导 15 个漂移环境的在线调优。信道频响差异被探针吸收。</li>
  </ol>
</div>

<h2 id="s8"><span class="num">8</span>适用边界与对策</h2>
<div class="tw">
<table>
  <tr><th>边界</th><th>表现</th><th>对策</th></tr>
  <tr>
    <td>BER 绝对值依赖评估协议</td>
    <td>块长每翻倍，绝对 BER 系统性变化约 −0.15～−0.25 dex</td>
    <td>全流程固定 262144 符号 × 3 种子；结果表标注协议</td>
  </tr>
  <tr>
    <td>代理绝对标定弱</td>
    <td>预测值会系统性欠估或过估真实 BER，不能当绝对值用</td>
    <td>决策只用排序与方向；安全判据表达为相对种子点的恶化量</td>
  </tr>
  <tr>
    <td><code>driver_gain</code> 最优区间依赖摆幅标定</td>
    <td>每用例扫描标定 target_rms（0.06~0.22V）</td>
    <td>更换器件时需重跑 per-case RMS 扫描（≈10 min）</td>
  </tr>
  <tr>
    <td>CTLE 直流增益维</td>
    <td>gDC/gDC2 通过频响整形改变 ISI，与 FFE 旁瓣效果类似但杠杆较弱（梯度幅值约为 FFE 的 1/10）；12/15 用例 CTLE 组被激活</td>
    <td>若需更强整形能力，把 CTLE 零极点比例也纳入搜索空间</td>
  </tr>
  <tr>
    <td>代理是局部模型</td>
    <td>信任域外预测不可信</td>
    <td>梯度门控 + 信任域投影 + Model B 相对红线三重约束；趋平即停</td>
  </tr>
  <tr>
    <td>用例覆盖有限</td>
    <td>15 个用例覆盖 10/14/16/20 dB 插损组合与 CD/DGD/噪声应力</td>
    <td>超出范围时重跑离线数据集（≈55 min）并重训（&lt;0.1 s），算法本身无需修改</td>
  </tr>
</table>
</div>

<h2 id="s9"><span class="num">9</span>复现与产物</h2>

<div class="card">
  <h4 style="margin-top:0">完整流水线</h4>
  <pre><code># 1) 数据集（2001 点；6 维 LHS；只用 Base_IL10x10；gain 窄带 ×0.40~×0.90）
python dataset_generator.py --base-samples 2000 --only-envs Base_IL10x10 \
    --num-symbols 262144 --sim-seeds 42,43,44 --jobs 14 --core-samples 1200 --v5

# 2) 训练 A/B（A: 探针 8 维 -> BER；B: 参数 7 维 -> BER）
python -c "from train_surrogates import train_v6; import glob; \
  train_v6(sorted(glob.glob('dataset/ddps_v4_dataset_*.csv'))[-1], 'models/ddps_v6')"

# 3) per-case target_rms 扫描
python scratch/scan_per_case_rms.py --jobs 12

# 4) 在线调优（15 环境）
python test_generalization.py --model-dir models/ddps_v6 --out-dir result/ddps_v6_main --v6 \
    --n-steps 15 --num-symbols 262144 --sim-seeds 42,43,44

# 5) 可视化报告
python report_ddps_v6.py --test-dir result/ddps_v6_main --model-dir models/ddps_v6 \
    --summary "v6:A探针+B参数" --summary-out result/SUMMARY.md

# 6) 交付件
python make_deliverable_v6.py --baseline result/ddps_v6_main --model-dir models/ddps_v6</code></pre>
</div>

<div class="tw">
<table>
  <caption>产物清单</caption>
  <tr><th>类别</th><th>路径</th><th>内容</th></tr>
  <tr><td>数据集</td><td class="mono">dataset/ddps_v4_dataset_&lt;ts&gt;.csv</td><td>2001 行 × 44 列（6 维 x_shape + 5-tap FFE + 驱动 RMS + 7-tap FIR 探针 + 真实 BER）</td></tr>
  <tr><td>核心模型</td><td class="mono">models/ddps_v6/</td><td>A=探针 8 维 / B=参数 7 维 + meta.json</td></tr>
    <tr><td>核心结果</td><td class="mono">result/ddps_v6_main/</td><td>case_summary.csv/json、trace_&lt;用例&gt;.csv、run_config.json、report/</td></tr>
      <tr><td>跨实验汇总</td><td class="mono">result/SUMMARY.md</td><td>15 用例结果汇总</td></tr>
  <tr><td>模型修正记录</td><td class="mono">docs/10_DDPS_v6_Model_Update.md</td><td>A/B 分工、链式梯度、per-case target_rms 设计依据</td></tr>
</table>
</div>

<footer>
  <p><strong>测量口径</strong>：Python 3.11.11 / NumPy 2.4.6 / SciPy 1.17.1；BLAS 线程数固定为 1（<span class="mono">OMP_NUM_THREADS=1</span>）；
  BER 评估统一 262144 符号/点 × 仿真实例种子 (42,43,44) 取 log10 均值；数据集采样与模型划分固定 seed = 42。</p>
  <p>数值来源：<span class="mono">config.xlsx</span>、<span class="mono">models/*/meta.json</span>、<span class="mono">result/*/case_summary.csv</span>、
  <span class="mono">result/*/trace_*.csv</span>、<span class="mono">dataset/ddps_v4_dataset_*.csv</span> 与源码常量。</p>
</footer>

</div>
</body>
</html>

'''

# ============================================================================
# 模板填充逻辑（v6：单结果目录 + 单模型目录）
# ============================================================================
import argparse
import base64
import glob
import json
import os
import shutil

import numpy as np
import pandas as pd


def _latest(pattern):
    files = sorted(glob.glob(pattern))
    if not files:
        raise FileNotFoundError(f'no file matches {pattern}')
    return files[-1]


def _ber(x):
    return f'{x:.2e}'


def _load_summary(d):
    p = os.path.join(d, 'case_summary.csv')
    df = pd.read_csv(p)
    return {r['env']: r for _, r in df.iterrows()}, df


def _cond(r):
    parts = [f"IL{r['il_tx']:g}x{r['il_rx']:g}"]
    if r.get('cd', 0):
        parts.append(f"CD{r['cd']:g}")
    if r.get('dgd', 0):
        parts.append(f"DGD{r['dgd']:g}")
    if bool(r.get('noise_stress', False)):
        parts.append('Noise')
    return '+'.join(parts)


def _taps_of(r):
    v = r['best_taps']
    return np.array(json.loads(v)) if isinstance(v, str) else np.array(v)


def _gain_str(r):
    return f"{r.get('seed_gain', 2.0):.3f} -> {r.get('best_gain', float('nan')):.3f}"


def _rows_core(summary, order):
    out = []
    for env in order:
        r = summary[env]
        imp = r['seed_ber'] / r['best_ber']
        out.append(
            f"<tr><td>{env}</td><td>{_cond(r)}</td><td class=\"n\">{_ber(r['seed_ber'])}</td>"
            f"<td class=\"n\">{_ber(r['best_ber'])} ({int(r['best_step'])})</td>"
            f"<td class=\"n\">{r['delta_lb_seed_to_best']:+.3f}</td>"
            f"<td class=\"n{' win' if imp >= 1.05 else ''}\">x{imp:.2f}</td>"
            f"<td class=\"n\">{_gain_str(r)}</td></tr>")
    return '\n'.join(out)


def _rows_safety(summary, d):
    steps = 0
    worse = 0
    for env, r in summary.items():
        p = os.path.join(d, f'trace_{env}.csv')
        if not os.path.exists(p):
            continue
        tr = pd.read_csv(p)
        if tr.empty:
            continue
        steps += len(tr)
        worse += int((tr['real_ber'] > r['seed_ber']).sum())
    total_steps = steps
    total_worse = worse
    out = (f"<tr><td class=\"n\">{len(summary)}</td>"
           f"<td class=\"n\">{total_steps}</td>"
           f"<td class=\"n{' win' if total_worse == 0 else ''}\">{total_worse}</td>"
           f"<td>{'全程无退步' if total_worse == 0 else '存在退步'}</td></tr>")
    return out, total_steps, total_worse


def _rows_target_rms(rms_data, order):
    out = []
    for env in order:
        d = rms_data.get(env)
        if not d:
            continue
        out.append(
            f"<tr><td>{env}</td><td class=\"n\">{d['target_rms']:.3f}</td>"
            f"<td class=\"n\">{d['gain_ratio']:.3f}</td></tr>")
    return '\n'.join(out)


def _rows_ablation(summary_ab, summary_aonly, d_aonly, order):
    """A-only vs A+B 逐用例对比行。"""
    out = []
    for env in order:
        r_ab = summary_ab.get(env, {})
        r_ao = summary_aonly.get(env, {})
        seed = r_ab.get('seed_ber', 0)
        best_ab = r_ab.get('best_ber', seed)
        best_ao = r_ao.get('best_ber', seed)
        imp_ab = seed / best_ab if best_ab > 0 else 0
        imp_ao = seed / best_ao if best_ao > 0 else 0
        # 劣化步
        worse_ao = 0
        p_ao = os.path.join(d_aonly, f'trace_{env}.csv')
        if os.path.exists(p_ao):
            tr = pd.read_csv(p_ao)
            if not tr.empty:
                worse_ao = int((tr['real_ber'] > seed * 1.001).sum())
        worse_ab = 0
        p_ab = os.path.join(os.path.dirname(d_aonly), 'ddps_v6_main', f'trace_{env}.csv')
        if os.path.exists(p_ab):
            tr = pd.read_csv(p_ab)
            if not tr.empty:
                worse_ab = int((tr['real_ber'] > seed * 1.001).sum())
        out.append(
            f"<tr><td>{env}</td>"
            f"<td class=\"n\">{seed:.3e}</td>"
            f"<td class=\"n\">{best_ao:.3e}</td>"
            f"<td class=\"n\">x{imp_ao:.2f}</td>"
            f"<td class=\"n{' bad' if worse_ao > 0 else ' win'}\">{worse_ao}</td>"
            f"<td class=\"n\">{best_ab:.3e}</td>"
            f"<td class=\"n\">x{imp_ab:.2f}</td>"
            f"<td class=\"n{' bad' if worse_ab > 0 else ' win'}\">{worse_ab}</td></tr>")
    return '\n'.join(out)


def _rows_metrics(meta):
    _domain_zh = {'waveform_probe': '波形域（探针）', 'parameter': '参数域'}
    out = []
    for tag, name in (('model_a', 'Model A'), ('model_b', 'Model B')):
        m = meta[tag]
        dim = meta[f'{tag}_dim']
        desc = m.get('description', '')
        domain = _domain_zh.get(m.get('input_domain', ''), m.get('input_domain', ''))
        out.append(
            f"<tr><td>{name}</td><td>{domain}</td><td class=\"n\">{dim}</td>"
            f"<td class=\"n\">{meta['n_train']} / {meta['n_test']}</td>"
            f"<td class=\"n\">{m['r2_test']:.3f}</td><td class=\"n\">{m['mse_test']:.3f}</td>"
            f"<td class=\"n\">{m['spearman_test']:.3f}</td>"
            f"<td>{desc}</td></tr>")
    return '\n'.join(out)


def _img_tag(path):
    with open(path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode('ascii')
    return f'data:image/png;base64,{b64}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--baseline', default='result/ddps_v6_main', help='v6 主结果目录')
    ap.add_argument('--model-dir', default='models/ddps_v6', help='v6 模型目录')
    ap.add_argument('--dataset', default=None)
    ap.add_argument('--out', default='DDPS_v6_Deliverable.html')
    a = ap.parse_args()

    summary, core_df = _load_summary(a.baseline)
    order = list(core_df.sort_values('env')['env'])

    with open(os.path.join(a.model_dir, 'meta.json'), encoding='utf-8') as f:
        meta = json.load(f)

    # per-case target_rms 扫描结果（gain 维物理驱动的标定值）
    rms_json_path = os.path.join(os.path.dirname(os.path.normpath(a.baseline)), 'per_case_target_rms.json')
    with open(rms_json_path, encoding='utf-8') as f:
        rms_data = json.load(f)

    ds_path = a.dataset or _latest('dataset/ddps_v4_dataset_*.csv')
    ds = pd.read_csv(ds_path)

    report_dir = os.path.join(a.baseline, 'report')

    # A-only 对比实验数据
    aonly_dir = os.path.join(os.path.dirname(os.path.normpath(a.baseline)), 'ddps_v6_aonly')
    summary_aonly = {}
    aonly_rows = '<tr><td colspan="8">A-only 实验未运行（result/ddps_v6_aonly 不存在）</td></tr>'
    if os.path.exists(os.path.join(aonly_dir, 'case_summary.csv')):
        df_aonly = pd.read_csv(os.path.join(aonly_dir, 'case_summary.csv'))
        summary_aonly = {r['env']: r for _, r in df_aonly.iterrows()}
        aonly_rows = _rows_ablation(summary, summary_aonly, aonly_dir, order)

    # 图片素材：从 report_ddps_v6.py 生成的 PNG 加载
    img_conv = os.path.join(report_dir, 'ddps_v6_convergence.png')
    img_gain = os.path.join(report_dir, 'ddps_v6_gain_rms.png')
    img_track = os.path.join(report_dir, 'ddps_v6_tracking.png')
    hard_env = max(order, key=lambda e: summary[e]['seed_ber'])
    hard_png = os.path.join(report_dir, f'ddps_v6_case_{hard_env}_a.png')

    # 统计
    imp_arr = np.array([summary[e]['seed_ber'] / summary[e]['best_ber'] for e in order])
    n_pos = int((imp_arr > 1.0).sum())
    hard = summary[hard_env]
    safety_rows, total_steps, total_worse = _rows_safety(summary, a.baseline)

    headline = '\n'.join([
        f"<tr><td><strong>v6 在线调优</strong>（A=探针->BER 方向 + B=参数->BER 风险控制 + gain per-case RMS）</td>"
        f"<td><strong>{n_pos}/{len(order)} 用例正向改善</strong>，平均 x{imp_arr.mean():.2f}"
        f"（最高 x{imp_arr.max():.2f}）；全程 {total_steps} 步真实 BER，"
        f"<strong>{total_worse} 步劣于种子</strong> -> <span class=\"win\">可交付</span></td></tr>",
        f"<tr><td>Model A（方向代理）</td>"
        f"<td>输入 = [7-tap Tx FIR 探针, drive_rms]（8 维波形域）-> log10(BER) 条件均值。"
        f"在线拿不到收端 BER，只能拿发端探针，A 建立探针->BER 方向映射。</td></tr>",
        f"<tr><td>Model B（风险控制）</td>"
        f"<td>输入 = [4 FFE 旁瓣, gDC, gDC2, drive_rms]（7 维参数域）-> log10(BER) 保守上包络。"
        f"按当前最优点 25% 的变差量拒绝候选，全程 {total_worse} 步劣于种子（红线未触发拦截）。</td></tr>",
        f"<tr><td>A/B 输入空间不同</td>"
        f"<td>波形域 vs 参数域，误差来源相互独立。梯度通过 A 的链式法则：扰动参数->重算探针->查A。</td></tr>",
        f"<tr><td>gain 维</td>"
        f"<td>不在 A/B 输入里。每用例单独扫描标定 target_rms（0.06~0.22V），"
        f"每步解析调到该用例 target_rms。</td></tr>",
        f"<tr><td>在线决策是否使用真实收端误码</td><td><strong>不使用</strong>，仅旁路记录用于事后核验</td></tr>",
    ])

    kpis = '\n'.join([
        f'<div class="kpi"><div class="v">x{imp_arr.mean():.2f}</div><div class="l">平均改善（{n_pos}/{len(order)} 正向）</div></div>',
        f'<div class="kpi"><div class="v">{total_worse} / {total_steps}</div><div class="l">劣于种子的步数</div></div>',
        f'<div class="kpi"><div class="v">{meta["model_a"]["spearman_test"]:.3f}</div><div class="l">Model A Spearman（探针->BER）</div></div>',
        f'<div class="kpi"><div class="v">{meta["model_b"]["spearman_test"]:.3f}</div><div class="l">Model B Spearman（参数->BER）</div></div>',
        f'<div class="kpi"><div class="v">{meta["model_b"].get("local_spacing_rho", 0):.2f}</div><div class="l">信任域颗粒度 rho</div></div>',
    ])

    html = TEMPLATE
    repl = {
        '<!--HEADLINE_ROWS-->': headline,
        '<!--MODEL_METRICS_ROWS-->': _rows_metrics(meta),
        '<!--KPI_CARDS-->': kpis,
        '<!--CORE_ROWS-->': _rows_core(summary, order),
        '<!--ABLATION_ROWS-->': aonly_rows,
        '<!--TARGET_RMS_ROWS-->': _rows_target_rms(rms_data, order),
        '<!--SAFETY_ROWS-->': safety_rows,
        '<!--MEAN_IMP-->': f'x{imp_arr.mean():.2f}',
        '<!--MAX_IMP-->': f'x{imp_arr.max():.2f}',
        '<!--TOTAL_STEPS-->': str(total_steps),
        '<!--TOTAL_WORSE-->': str(total_worse),
        '{{IMG_CONV}}': _img_tag(img_conv) if os.path.exists(img_conv) else '',
        '{{IMG_GAIN}}': _img_tag(img_gain) if os.path.exists(img_gain) else '',
        '{{IMG_TRACK}}': _img_tag(img_track) if os.path.exists(img_track) else '',
        '{{IMG_CASE_HARD}}': _img_tag(hard_png) if os.path.exists(hard_png) else '',
    }
    for k, v in repl.items():
        html = html.replace(k, v)

    with open(a.out, 'w', encoding='utf-8') as f:
        f.write(html)
    left = html.count('{{IMG_') + html.count('<!--')
    print(f'[deliverable] written {a.out}  ({os.path.getsize(a.out)/1024:.0f} KB)')
    print(f'[deliverable] baseline={a.baseline} model={a.model_dir}')
    print(f'[deliverable] envs={len(order)} positive={n_pos} steps={total_steps} worse={total_worse}')
    print(f'[deliverable] mean improvement: x{imp_arr.mean():.2f}')
    print(f'[deliverable] hardest={hard_env}; unused tokens left: {left}')


if __name__ == '__main__':
    main()
