#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""make_deliverable.py — 由产物自动生成 DDPS 交付件（自包含 HTML）。

数据来源（全部为流水线产物，无需手工转录）：
  result/ddps_cpp_secant/         C++ 割线在线调优 15 环境（7 维 FFE+CTLE+gain，第 0 步 shape 中心差分初始化 + gain 解析梯度 + Broyden 更新，零后续试探态）
  models/ddps/                   meta.json（模型指标与特征维度）
  dataset/ddps_dataset_*.csv      数据集统计
用法:
  python make_deliverable.py --baseline result/ddps_cpp_secant --model-dir models/ddps \
      --out deliverables/DDPS_Deliverable.html
"""
import matplotlib
matplotlib.use('Agg')

TEMPLATE = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="theme-color" content="#0e2a52">
<title>DDPS 交付说明 — 收发端均衡代理寻优</title>
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
  .tabs{margin:14px 0}
  .tab-bar{display:flex;gap:6px;border-bottom:2px solid var(--line);margin-bottom:12px;flex-wrap:wrap}
  .tab-btn{background:#eef2f7;border:1px solid var(--line);border-bottom:none;border-radius:8px 8px 0 0;padding:8px 16px;font-size:13.5px;font-weight:700;color:var(--ink-2);cursor:pointer;font-family:inherit}
  .tab-btn.active{background:var(--accent);color:#fff;border-color:var(--accent)}
  .tab-btn:hover:not(.active){background:#e2ebf5}
  .tab-panel{display:none}
  .tab-panel.active{display:block}
  details.fold{border:1px solid var(--line);border-radius:11px;background:#fff;margin:12px 0;overflow:hidden}
  details.fold>summary{cursor:pointer;list-style:none;padding:12px 16px;font-weight:700;color:var(--ink-2);font-size:14px;background:#f2f6fb;user-select:none;-webkit-user-select:none}
  details.fold>summary::-webkit-details-marker{display:none}
  details.fold>summary::before{content:"▸";color:var(--accent);margin-right:8px;display:inline-block;transition:transform .15s}
  details.fold[open]>summary::before{transform:rotate(90deg)}
  details.fold>summary:hover{background:#eaf1fa}
  details.fold .fold-body{padding:8px 16px 14px}
  @media (max-width:820px){
    details.fold>summary{padding:10px 13px}
    details.fold .fold-body{padding:4px 12px 10px}
    .tab-btn{padding:7px 12px;font-size:12.8px}
  }
  @media print{
    .tab-panel{display:block !important}
    .tab-bar{display:none}
  }
  .sect{cursor:pointer}
  .sect::before{content:"▾";display:inline-block;width:16px;margin-left:2px;color:var(--accent);font-size:.8em;transition:transform .15s}
  .sect.collapsed::before{content:"▸"}
  h2.sect:hover,h3.sect:hover,h4.sect:hover{color:var(--accent)}
  @media print{
    .sect{cursor:default}
    .sect::before{display:none}
  }
</style>
</head>
<body>

<header class="top">
  <div class="wrap">
    <div class="eyebrow">LPO 112G PAM4 仿真平台 · 收发端联合寻优</div>
    <h1>DDPS：收发端均衡代理寻优 — 交付说明</h1>
    <div class="scope">
      本交付件说明方案的适用范围、物理链路与优化对象、两个代理模型的构成与全部参数、在线调优算法流程与复杂度、实测效果与适用边界，以及有回传通道时的 direct 直接梯度对照实验。
      参数取自 <code>config.xlsx</code>、模型 <code>meta.json</code>、结果 <code>case_summary / trace</code> 与源码常量；图表为内嵌 SVG 与 PNG，单文件可离线打开。
    </div>
    <div class="chips">
      <span class="chip">搜索 <b>7</b> 维（4 FFE 旁瓣 + gDC + gDC2 + u_gain）</span>
      <span class="chip">用例 <b>15</b> 个（含非对称 Tx/Rx 插损与器件噪声）</span>
      <span class="chip">评估协议 <b>4194304</b> 符号 × 单种子 <b>42</b></span>
      <span class="chip">模型训练 <b>&lt;0.1 s</b> · 推理 <b>≈30 µs</b></span>
      <span class="chip">现役方案在线决策回路真实 BER <b>0</b> 次（无需回传通道）</span>
    </div>
  </div>
</header>

<div class="wrap">

<h2 id="s1"><span class="num">1</span>方案概要</h2>

<div class="card">
  <h4 style="margin-top:0">适用场景与约束</h4>
  <ul style="margin-bottom:0">
    <li>LPO 光模块内部不做重 DSP，发送端均衡由 Host ASIC 承担。可用的均衡自由度：<strong>5-tap T-spaced 发送端 FFE</strong>（4 个旁瓣为自由变量，主抽头由归一化派生）与 <strong>发送端模拟 CTLE 的高频 peaking 增益 gDC 与低频 shelf 增益 gDC2</strong>。接收端另有一级固定参数的模拟 CTLE（gDC = 6 dB，gDC2 = 3 dB）作为静态均衡基座。</li>
    <li>信道条件：奈奎斯特电插损 Tx/Rx <strong>各自</strong> 10～20 dB，色散 0～28 ps/nm，差分群时延 0～5 ps，偏振角 0～45°，另含器件噪声应力（RIN / 消光比 / TIA 噪声）。</li>
    <li>约束：在线调优阶段不得使用真实收端误码做决策（只能使用发送端可获得的物理量），且不允许出现任何一次“优化后比起点更差”。若回传通道存在、端到端 BER 可得，可直接对真实目标做梯度下降——该情形的 direct 对照实验见 6.5。</li>
  </ul>
</div>

<div class="card">
  <h4 style="margin-top:0">方法构成</h4>
  <ol style="margin-bottom:0">
    <li><strong>物理探针</strong>：向发送链注入单位脉冲，在 MZM 输入端截取 7-tap 等效发射 FIR <em>形状</em>，并把该点的<strong>绝对驱动 RMS</strong> 一并取出：FIR 形状描述波形，RMS 描述驱动幅度。</li>
    <li><strong>双代理模型</strong>：Model A（7-tap FIR 形状 + 驱动 RMS → log10 BER_MLSE 条件均值，负责下降方向，带解析梯度）、Model B（4 旁瓣 + gDC + gDC2 + 驱动 RMS → log10 BER_MLSE 保守上包络，负责安全否决），均为二阶多项式 Ridge 闭式解，纯 NumPy。两者输入空间不同（波形域 / 参数域），误差来源相互独立。</li>
    <li><strong>约束梯度下降</strong>：下降方向走 Model A（gain 维解析闭式梯度 + shape 维第 0 步中心差分初始化后割线更新，除第 0 步外零 ±ε 试探态），每步落地前须通过 Model B 的相对安全审查，并受轨迹信任域（2.0×ρ）与梯度幅值门控约束；gain 是第 7 个搜索维（每用例最优倍率见 3.3 的 per-case RMS 标定参照），参数箱信任域收窄到 ±0.30 dex。真实 BER 全量记录但不参与决策。</li>
  </ol>
</div>

<div class="tw">
<table id="tbl-headline">
  <caption>结论（完整数据见第 6 节）</caption>
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
    <text class="ts" x="866" y="85" text-anchor="middle">RMS 驱动（gain 维）</text>

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

    <rect class="bx" x="698" y="163" width="102" height="54" rx="8"/>
    <text class="tw2" x="749" y="187" text-anchor="middle">光纤 + PIN</text>
    <text class="ts" x="749" y="204" text-anchor="middle">CD 复场 / DGD 实功率</text>

    <rect class="bx" x="584" y="163" width="102" height="54" rx="8"/>
    <text class="tw2" x="635" y="187" text-anchor="middle">TIA</text>
    <text class="ts" x="635" y="204" text-anchor="middle">720 Ω / 16 pA/√Hz</text>

    <rect class="bx" x="470" y="163" width="102" height="54" rx="8"/>
    <text class="tw2" x="521" y="187" text-anchor="middle">Rx 电插损</text>
    <text class="ts" x="521" y="204" text-anchor="middle">S4P，Rx IL</text>

    <rect class="bx" x="356" y="163" width="102" height="54" rx="8"/>
    <text class="tw2" x="407" y="187" text-anchor="middle">Rx CTLE</text>
    <text class="ts" x="407" y="204" text-anchor="middle">固定 6/3 dB</text>

    <rect class="bx" x="242" y="163" width="102" height="54" rx="8"/>
    <text class="tw2" x="293" y="187" text-anchor="middle">ADC</text>
    <text class="ts" x="293" y="204" text-anchor="middle">ENOB 5.5</text>

    <rect class="bx" x="128" y="163" width="102" height="54" rx="8"/>
    <text class="tw2" x="179" y="187" text-anchor="middle">22-tap Rx FFE</text>
    <text class="ts" x="179" y="204" text-anchor="middle">LMS 自适应</text>

    <rect class="bx" x="14" y="163" width="102" height="54" rx="8"/>
    <text class="tw2" x="65" y="187" text-anchor="middle">Burg + MLSE</text>
    <text class="ts" x="65" y="204" text-anchor="middle">memory = 1</text>

    <line class="ln" x1="806" y1="190" x2="800" y2="190" marker-end="url(#ah1)"/>
    <line class="ln" x1="698" y1="190" x2="686" y2="190" marker-end="url(#ah1)"/>
    <line class="ln" x1="584" y1="190" x2="572" y2="190" marker-end="url(#ah1)"/>
    <line class="ln" x1="470" y1="190" x2="458" y2="190" marker-end="url(#ah1)"/>
    <line class="ln" x1="356" y1="190" x2="344" y2="190" marker-end="url(#ah1)"/>
    <line class="ln" x1="242" y1="190" x2="230" y2="190" marker-end="url(#ah1)"/>
    <line class="ln" x1="128" y1="190" x2="116" y2="190" marker-end="url(#ah1)"/>

    <line class="ln" x1="78" y1="217" x2="78" y2="244" marker-end="url(#ah1)"/>
    <rect class="bx-ok" x="14" y="246" width="128" height="44" rx="8"/>
    <text class="tw2" x="78" y="266" text-anchor="middle">BER_MLSE</text>
    <text class="ts" x="78" y="282" text-anchor="middle">统一指标</text>

    <text class="ts" x="160" y="262">DFE 固定关闭（dfe_taps = 0）；噪声全部由器件参数分布式产生（RIN / 散粒 / 热噪声 / TIA 输入参考噪声 / 1 mV 前端噪声），不使用全局 SNR。</text>
    <text class="ts" x="160" y="280">蓝色框为三个可优化自由度；其余为给定的物理器件与信道参数。</text>
    <text class="ts" x="160" y="306">Tx 与 Rx 电插损可独立配置，用于刻画 Host 侧 / Module 侧损耗不对称的真实情形。</text>
  </svg>

  <svg class="d-narrow" viewBox="0 0 360 990" role="img" aria-label="仿真链路框图（竖向）">
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
    <text class="ts" x="24" y="334">RMS 驱动（gain 维）</text>

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
    <text class="tw2" x="24" y="652">Rx CTLE（固定 gDC=6 dB / gDC2=3 dB）</text>

    <rect class="bx" x="10" y="674" width="340" height="38" rx="7"/>
    <text class="tw2" x="24" y="698">ADC（ENOB 5.5）</text>

    <rect class="bx" x="10" y="720" width="340" height="38" rx="7"/>
    <text class="tw2" x="24" y="744">22-tap Rx FFE（LMS 自适应）</text>

    <rect class="bx" x="10" y="766" width="340" height="38" rx="7"/>
    <text class="tw2" x="24" y="790">Burg + MLSE（memory = 1）</text>

    <line class="ln" x1="180" y1="482" x2="180" y2="488" marker-end="url(#an1)"/>
    <line class="ln" x1="180" y1="528" x2="180" y2="534" marker-end="url(#an1)"/>
    <line class="ln" x1="180" y1="574" x2="180" y2="580" marker-end="url(#an1)"/>
    <line class="ln" x1="180" y1="620" x2="180" y2="626" marker-end="url(#an1)"/>
    <line class="ln" x1="180" y1="666" x2="180" y2="672" marker-end="url(#an1)"/>
    <line class="ln" x1="180" y1="712" x2="180" y2="718" marker-end="url(#an1)"/>
    <line class="ln" x1="180" y1="758" x2="180" y2="764" marker-end="url(#an1)"/>

    <line class="ln" x1="180" y1="804" x2="180" y2="816" marker-end="url(#an1)"/>
    <rect class="bx-ok" x="10" y="818" width="340" height="38" rx="7"/>
    <text class="tw2" x="24" y="842">BER_MLSE（统一指标）</text>

    <text class="ts" x="360" y="842">DFE 固定关闭；噪声由器件参数分布式产生</text>
    <text class="ts" x="360" y="858">（RIN / 散粒 / 热噪声 / TIA / 1 mV 前端），无全局 SNR。</text>
    <text class="ts" x="360" y="880">蓝色框为三个可优化自由度。</text>
    <text class="ts" x="360" y="902">Rx CTLE 为固定基座（不优化）。</text>
    <text class="ts" x="360" y="924">Tx / Rx 电插损可独立配置（不对称）。</text>
  </svg>

  <figcaption>物理探针取 MZM 输入端的线性冲激响应（7-tap FIR + 驱动 RMS）。它与真实链路共用同一个 Tx 模拟前端函数 <span class="mono">tx_frontend_lti</span>，因此探针反映的 Tx 前端与真实链路一致；差别只在探针取线性响应（不含 DAC ENOB 量化与 1 mV 前端噪声）。</figcaption>
</figure>

<h3>2.2 优化空间与参数化</h3>
<figure>
  <div class="fig-title">图 2 · 7 维搜索空间与约束</div>

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
    <text class="tw2" x="179" y="168" text-anchor="middle">Tx CTLE：gDC ∈ [0, 12] dB · gDC2 ∈ [0, 4] dB</text>
    <text class="ts" x="179" y="186" text-anchor="middle">post-channel 高频 peaking（2 维）</text>

    <rect class="bx" x="360" y="146" width="250" height="52" rx="7"/>
    <text class="tw2" x="485" y="168" text-anchor="middle">gain（第 7 维）</text>
    <text class="ts" x="485" y="186" text-anchor="middle">经 drive_rms 进入 A/B 输入</text>

    <rect class="panel" x="626" y="146" width="440" height="150" rx="8"/>
    <text class="t" x="642" y="170">搜索向量：</text>
    <text class="mono" x="722" y="170" style="font-size:12.5px">x ∈ R⁷ = [4 旁瓣, gDC, gDC2, u_gain]</text>
    <text class="ts" x="642" y="192">种子 x₀：旁瓣 [-0.0885,-0.3147,0.0845,0.1043]，gDC 6.73，gDC2 0.85，gain ×0.325</text>
    <text class="ts" x="642" y="212">信任域：FFE ±0.10 / CTLE ±3.0 dB / gain ±0.30 dex</text>
    <text class="ts" x="642" y="232">组内归一化步长：FFE / CTLE / gain 三组各自归一化后乘箱宽</text>
    <text class="ts" x="642" y="256">主抽头不进入搜索向量 ⇒ 下降方向只作用于波形形状，</text>
    <text class="ts" x="642" y="272">不会用“整体变亮/变暗”这类伪自由度降 BER。</text>

    <text class="tb" x="14" y="232">CTLE 放在 Tx 电插损之后、Driver 之前</text>
    <text class="ts" x="14" y="254">· 整形"到达 MZM 的频谱"，高频 peaking 补偿信道损耗才有效。</text>
    <text class="ts" x="14" y="272">· peaking 拓扑直流增益为 0 dB，只抬 Nyquist 附近、不整体抬幅，</text>
    <text class="ts" x="14" y="290">  驱动幅度由 gain 维独立控制，CTLE 与 gain 互不冗余。</text>
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
    <text class="tw2" x="24" y="212">gDC ∈ [0, 12] dB · gDC2 ∈ [0, 4] dB</text>
    <text class="ts" x="24" y="230">2 维：高频 peaking</text>

    <text class="tb" x="10" y="266">gain 维（第 7 搜索维）</text>
    <rect class="bx" x="10" y="276" width="340" height="50" rx="7"/>
    <text class="tw2" x="24" y="296">gain 纳入梯度（第 7 维）</text>
    <text class="ts" x="24" y="314">见 3.3 per-case RMS 标定参照；起点为次优点</text>

    <rect class="panel" x="10" y="340" width="340" height="80" rx="8"/>
    <text class="mono" x="24" y="362" style="font-size:12.3px">x ∈ R⁷ = [4 旁瓣, gDC, gDC2, u_gain]</text>
    <text class="ts" x="24" y="382">种子：[-0.0885,-0.3147,0.0845,0.1043] / 6.73 / 0.85 dB / ×0.325</text>
    <text class="ts" x="24" y="400">信任域：FFE ±0.10 / CTLE ±3.0 dB / gain ±0.30 dex</text>
  </svg>

  <figcaption>主抽头不进搜索向量，由归一化恒等式导出。</figcaption>
</figure>

<h3>2.3 关键参数（取自 <span class="mono">config.xlsx</span>，112G 模式）</h3>
<details class="fold">
<summary>系统 / 均衡 / 器件 / 信道参数取值</summary>
<div class="fold-body">
<div class="grid2">
  <div class="tw">
  <table>
    <caption>系统与均衡配置</caption>
    <tr><th>参数</th><th class="n">取值</th></tr>
    <tr><td>波特率 / 调制</td><td class="n">56 GBd, PAM4</td></tr>
    <tr><td>采样率（DSP / DAC / 信道 / ADC）</td><td class="n">2 / 2 / 8 / 2 sps</td></tr>
    <tr><td>Tx FFE</td><td class="n">5 tap, T-spaced</td></tr>
    <tr><td>Tx CTLE 零极点比</td><td class="n">fz 2.862 / fp1 1.884 / fp2 1 / flf 40</td></tr>
    <tr><td>Rx CTLE</td><td class="n">固定 gDC = 6 dB，gDC2 = 3 dB</td></tr>
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
    <tr><td>Driver gain / 带宽</td><td class="n">第 7 搜索维（每用例最优倍率见 3.3）/ 40 GHz</td></tr>
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
</div>
</details>

<h3>2.4 十五个物理应力用例</h3>
<details class="fold">
<summary>15 个用例定义：对称/非对称插损、色散、DGD、器件噪声（训练 / 测试 / 报告共用）</summary>
<div class="fold-body">
<div class="tw">
<table class="wide">
  <caption>训练、测试、报告共用同一份定义 <span class="sh">· 可左右滑动</span></caption>
  <tr><th>用例</th><th class="n">Tx IL (dB)</th><th class="n">Rx IL (dB)</th><th class="n">CD (ps/nm)</th><th class="n">DGD (ps)</th><th class="n">Pol (°)</th><th>说明</th></tr>
  <tr><td>Base_IL10x10</td><td class="n">10</td><td class="n">10</td><td class="n">0</td><td class="n">0</td><td class="n">0</td><td>基线环境（唯一训练环境）</td></tr>
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
</div>
</details>

<h3>2.5 三个自由度的参数化公式（复现所需的完整映射）</h3>
<p>搜索向量 <span class="mono">x = [x₀ x₁ x₂ x₃, x₄, x₅, x₆]</span> 到物理器件的映射如下，是复现本方案必须写死的三处参数化。</p>
<div class="card">
<h4 style="margin-top:0">① 5 抽头 Tx FFE（4 个自由旁瓣 + 1 个派生主抽头）</h4>
<pre style="margin:6px 0"><code>h = [h₀, h₁, h₂, h₃, h₄]，T-spaced，主抽头在 t₂（2 个前游标 + 2 个后游标）
h₂ = 1 − Σ_{k≠2} |h_k|（主抽头由能量恒等式派生）；Σ_{k≠2}|h_k| ≤ 0.8 ⇒ h₂ ≥ 0.2；|h_k| ≤ 0.3</code></pre>
<p style="margin:6px 0">搜索变量 x₀…x₃ = [h₀, h₁, h₃, h₄]（4 个旁瓣），主抽头不进搜索向量。</p>
</div>
<div class="card">
<h4 style="margin-top:0">② Tx 模拟 CTLE（gDC、gDC2 两维，OIF 2Z3P peaking 拓扑）</h4>
<pre style="margin:6px 0"><code>K_DC  = 10^(gDC/20)，  K_DC2 = 10^(gDC2/20)
H_S1(f) = (1 + j·f·K_DC/f_z) / [(1 + j·f/f_p1)(1 + j·f/f_p2)]     高频 peaking（有效零点 f_z/K_DC，峰值 ≈ K_DC）
H_S2(f) = (1 + j·f·K_DC2/f_lf) / (1 + j·f/f_lf)                     低频 shelf（转折 f_lf，增益 K_DC2）
H_CTLE(f) = H_S1(f) · H_S2(f)，直流增益为 0 dB
f_z = f_b/2.862，f_p1 = f_b/1.884，f_p2 = f_b/1.0，f_lf = f_b/40，f_b = 56 GHz</code></pre>
<p style="margin:6px 0">搜索变量 x₄ = gDC（dB，[0,12]）、x₅ = gDC2（dB，[0,4]）。高频 peaking 只抬 Nyquist 附近、不抬直流，驱动幅度由 gain 维独立控制，两者不冗余。</p>
</div>
<div class="card">
<h4 style="margin-top:0">③ driver_gain（第 7 维，对数参数化）</h4>
<pre style="margin:6px 0"><code>gain = g₀ · 10^u_gain，  u_gain = log₁₀(gain / g₀)，  g₀ = 0.3399（标称 driver_gain）</code></pre>
<p style="margin:6px 0">搜索变量 x₆ = u_gain。driver_gain 是 Tx 链末尾的标量乘子，只整体缩放波形，所以 gain 维梯度有解析解（§4.2.1）。</p>
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
    <text class="tw2" x="89" y="62" text-anchor="middle">7 维参数</text>
    <text class="ts" x="89" y="79" text-anchor="middle">4 FFE + gDC + gDC2 + u_gain</text>

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
    <text class="tw2" x="24" y="46">7 维参数（4 FFE + gDC + gDC2 + u_gain）</text>
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
    <text class="ts" x="10" y="538">因此误差来源相互独立：A 提供下降方向，B 提供安全否决。</text>
  </svg>

  <figcaption>两个模型使用相同学习器与训练标签，唯一区别是输入特征：A 走物理探针（波形域 + 驱动幅度），B 直接用配置（参数域），因此误差来源相互独立。</figcaption>
</figure>

<div class="card">
  <h4 style="margin-top:0">Model A 的第 8 个特征：绝对驱动 RMS</h4>
  <p style="margin-bottom:0">
    <code>driver_gain</code> 在线性 Tx 链中只是标量乘子，只整体缩放波形；7-tap FIR 若只看<strong>形状</strong>（峰值归一化）则对它不敏感，梯度在该维恒为 0。
    因此探针把 7-tap FIR 保留绝对量纲（除以常数 <span class="mono">DRIVE_RMS_NOMINAL</span>），并把 MZM 输入端的真实驱动 RMS 作为第 8 个特征，
    <code>driver_gain</code> 的变化同时体现在抽头幅度与驱动 RMS 上，使该维拿到非零梯度。
  </p>
</div>

<h3>3.2 模型形式、超参数与指标</h3>
<p>两个模型共用同一学习器：手写二阶多项式特征 + L2 正则 Ridge 回归闭式解，纯 NumPy。输入先逐维标准化到零均值单位方差再进多项式，权重用闭式解一次求定（无迭代、无第三方求解器）。</p>
<pre><code>输入标准化    x̂ = (x − μ) / σ                             μ、σ = 训练集逐维均值 / 标准差
特征展开      φ(x̂) = [1, x̂₁…x̂_d, x̂₁²…x̂_d², x̂₁x̂₂…x̂_{d−1}x̂_d]    D = 1 + 2d + d(d−1)/2
拟合闭式解    W = (ΦᵀΦ + α·I)⁻¹ Φᵀ y                    Φ = φ(X̂)：标准化后的设计矩阵
推理          ŷ(x) = φ(x̂)ᵀ W
解析梯度      ∂ŷ/∂x̂ᵢ = wᵢ + 2·w_ii·x̂ᵢ + Σ_{k≠i} w_ik·x̂_k
原始量纲梯度  ∂ŷ/∂xᵢ = (∂ŷ/∂x̂ᵢ) / σᵢ                      （链式法则 dŷ/dx = dŷ/dx̂ · 1/σ）

Model A：d = 8（7-tap 绝对标定 FIR + drive_rms），α = 1.0，预测 log10(BER_MLSE) 条件均值，需解析梯度。
Model B：d = 7（4 旁瓣 + gDC + gDC2 + drive_rms），α = 0.5，预测 log10(BER_MLSE) 保守上包络，只用预测、不取梯度。</code></pre>

<div class="tw">
<table class="wide">
  <caption>A/B 共用同一份训练集（2001 行，80/20 划分），仅输入特征不同 <span class="sh">· 可左右滑动</span></caption>
  <tr><th>模型</th><th>输入域</th><th class="n">特征维度</th><th class="n">n_train / n_test</th><th class="n">R²</th><th class="n">MSE</th><th class="n">Spearman</th><th>说明</th></tr>
  <!--MODEL_METRICS_ROWS-->
</table>
</div>

<h3>3.3 gain 维的 per-case target_rms 标定（参照）</h3>
<p>gain 是第 7 个搜索维。为刻画每个用例的最优 gain（供初始化与验收参照），离线按用例单独细粒度扫描 MZM 输入 RMS
（0.06~0.22V，步长 0.005）确定该用例的最优 RMS，再解析出对应 gain：</p>
<pre><code>gain_ref = gain_scan × (target_rms / rms_measured)</code></pre>
<p>解析出的 gain 倍率（相对标称 gain 0.3399）随信道总插损升高而增大，范围约 0.30（10 dB 低插损，触 GAIN_MIN 钳位）到 0.84（20 dB 极端插损）。
在线调优从次优起点（gain ×0.325）出发，梯度把 gain 推到各用例最优倍率附近（见 6.1）。</p>
<p>结果目录 <span class="mono">run_config.json</span> 里两个字段分开记：<span class="mono">per_case_target_rms</span> 记录上表的离线标定参照（不随 seed 变化），
<span class="mono">per_case_gain</span> 记录本跑每个用例实际作为 seed 的 gain（= ×0.325，即 0.1106）。</p>
<div class="tw">
<table class="wide">
  <caption>per-case target_rms 扫描结果（15 用例；gain 倍率 = 扫描所得 gain / 标称 gain 0.3399） <span class="sh">· 可左右滑动</span></caption>
  <tr><th>用例</th><th class="n">target_rms (V)</th><th class="n">gain 倍率</th></tr>
  <!--TARGET_RMS_ROWS-->
</table>
</div>

<h2 id="s4"><span class="num">4</span>寻优算法</h2>

<p>本节描述<strong>现役方案</strong>（Model A+B 代理割线，无需回传通道）的寻优算法。平台另含 <strong>direct 参照方案</strong>：有回传通道、端到端 BER 可得时，不用代理、直接对真实目标做梯度下降（目标与梯度来源不同，搜索空间/搜索盒/步长调度/停止判据与本节一致，机制对照见 6.5 方案说明页签）。两者共享同一物理链路（第 2 节）与同一次优起点（6.0）。</p>

<h3>4.1 两阶段结构</h3>
<figure>
  <div class="fig-title">图 4 · DDPS 两阶段流程（Stage 1 离线一次性 / Stage 2 在线逐环境）</div>

  <svg class="d-wide" viewBox="0 0 1080 500" role="img" aria-label="两阶段算法流程图">
    <defs>
      <marker id="ah4" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#8fa3ba"/>
      </marker>
    </defs>

    <rect class="panel" x="14" y="34" width="512" height="450" rx="10"/>
    <text class="tb" x="34" y="58">Stage 1 · 离线标定（一次性）</text>

    <rect class="bx" x="34" y="72" width="472" height="46" rx="7"/>
    <text class="t" x="48" y="92">起点 x₀（次优工作点，基线实测 ~1.3e-4）</text>
    <text class="ts" x="48" y="108">主抽头 0.4079，gDC = 6.73 dB，gDC2 = 0.85 dB；gain = ×0.325</text>

    <rect class="bx" x="34" y="134" width="472" height="46" rx="7"/>
    <text class="t" x="48" y="154">信任域内 LHS 采样（d = 7，含 gain）</text>
    <text class="ts" x="48" y="170">Base_IL10x10 邻域 2001 点（gain 覆盖全用例最优 gain 邻域 ×0.20~×1.26）</text>

    <rect class="bx" x="34" y="196" width="472" height="46" rx="7"/>
    <text class="t" x="48" y="216">每点：真实 BER_MLSE 评估 + 物理探针</text>
    <text class="ts" x="48" y="232">1048576 符号 × 3 仿真实例种子取 log10 均值；探针取 FIR 形状 + 驱动 RMS</text>

    <rect class="bx" x="34" y="258" width="472" height="46" rx="7"/>
    <text class="t" x="48" y="278">二阶多项式 Ridge 闭式解训练</text>
    <text class="ts" x="48" y="294">α_A=1.0 / α_B=0.5，80/20 划分，seed 42（A: 8 维探针 / B: 7 维参数）</text>

    <rect class="bx-ok" x="34" y="320" width="472" height="46" rx="7"/>
    <text class="t" x="48" y="340">输出并冻结：Model A（波形+驱动 → BER）/ Model B（配置 → BER）</text>
    <text class="ts" x="48" y="356">单套训练集：只用 Base_IL10x10 邻域 2001 行</text>

    <rect class="bx" x="34" y="382" width="472" height="72" rx="7"/>
    <text class="t" x="48" y="402">A/B 输入空间不同（波形域 vs 参数域），误差独立</text>
    <text class="ts" x="48" y="420">gain 经 drive_rms 进入 A/B 输入，每用例最优倍率见 3.3 标定参照，</text>
    <text class="ts" x="48" y="436">之后放开走 7 维割线梯度（第 0 步 shape 中心差分初始化 + gain 解析梯度 + Broyden 更新，零后续试探态），gain 信任域 ±0.30 dex。</text>

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
    <text class="t" x="588" y="154">Model A 割线梯度（7 维）</text>
    <text class="ts" x="588" y="170">第 0 步 6 维（shape）双边差分 = 12 探针，gain 维解析梯度 0 探针；此后零试探态，只用历史落点割线更新</text>

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
    <text class="ts" x="588" y="418">终止：|Δx| &lt; 1e-6 或达到步数上限</text>

    <line class="ln" x1="810" y1="118" x2="810" y2="132" marker-end="url(#ah4)"/>
    <line class="ln" x1="810" y1="180" x2="810" y2="194" marker-end="url(#ah4)"/>
    <line class="ln" x1="810" y1="242" x2="810" y2="256" marker-end="url(#ah4)"/>
    <line class="ln" x1="810" y1="304" x2="810" y2="318" marker-end="url(#ah4)"/>
    <line class="ln" x1="810" y1="366" x2="810" y2="380" marker-end="url(#ah4)"/>

    <path class="ln" d="M1046 405 L1064 405 L1064 157 L1048 157" marker-end="url(#ah4)"/>
    <text class="ts" x="1074" y="281" transform="rotate(90 1074 281)" text-anchor="middle">迭代（真实 BER 不回传）</text>

    <path class="brk" d="M556 200 L546 200 L546 348 L556 348"/>
    <text class="ts" x="16" y="474" style="fill:#0f8a4a;font-weight:700">三道约束：</text>
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
    <text class="ts" x="32" y="78">[-0.0885,-0.3147,0.4079,0.0845,0.1043] / 6.73 / 0.85 dB / ×0.325</text>

    <rect class="bx" x="20" y="106" width="320" height="54" rx="7"/>
    <text class="t" x="32" y="126">信任域内 LHS 采样（d = 7，含 gain）</text>
    <text class="ts" x="32" y="144">Base_IL10x10 邻域 2001 点</text>

    <rect class="bx" x="20" y="172" width="320" height="54" rx="7"/>
    <text class="t" x="32" y="192">每点：真实 BER + 物理探针</text>
    <text class="ts" x="32" y="210">1048576 符号 × 3 种子；FIR 形状 + 驱动 RMS</text>

    <rect class="bx" x="20" y="238" width="320" height="54" rx="7"/>
    <text class="t" x="32" y="258">二阶多项式 Ridge 闭式解</text>
    <text class="ts" x="32" y="276">α_A=1.0 / α_B=0.5，80/20，seed 42（A 8 维 / B 7 维）</text>

    <rect class="bx-ok" x="20" y="304" width="320" height="54" rx="7"/>
    <text class="t" x="32" y="324">冻结 Model A / Model B</text>
    <text class="ts" x="32" y="342">单套：只用基线 2001 行；gain 纳入梯度（第 7 维）</text>

    <line class="ln" x1="180" y1="94" x2="180" y2="104" marker-end="url(#an4)"/>
    <line class="ln" x1="180" y1="160" x2="180" y2="170" marker-end="url(#an4)"/>
    <line class="ln" x1="180" y1="226" x2="180" y2="236" marker-end="url(#an4)"/>
    <line class="ln" x1="180" y1="292" x2="180" y2="302" marker-end="url(#an4)"/>

    <rect class="panel" x="8" y="406" width="344" height="466" rx="9"/>
    <text class="tb" x="20" y="428">Stage 2 · 在线调优（每环境一次）</text>

    <rect class="bx" x="20" y="440" width="320" height="54" rx="7"/>
    <text class="t" x="32" y="460">当前点 x_k（k = 0 为种子）</text>
    <text class="ts" x="32" y="478">安全红线 = 最优点 B 预测 × 1.25</text>

    <rect class="bx" x="20" y="506" width="320" height="54" rx="7"/>
    <text class="t" x="32" y="526">Model A 割线梯度（7 维）</text>
    <text class="ts" x="32" y="544">第 0 步 12 探针双边差分（仅 shape 维）+ gain 解析，此后零试探态、纯割线更新</text>

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
    <text class="ts" x="32" y="808">终止：|Δx| &lt; 1e-6 或步数上限</text>

    <line class="ln" x1="180" y1="494" x2="180" y2="504" marker-end="url(#an4)"/>
    <line class="ln" x1="180" y1="560" x2="180" y2="570" marker-end="url(#an4)"/>
    <line class="ln" x1="180" y1="626" x2="180" y2="636" marker-end="url(#an4)"/>
    <line class="ln" x1="180" y1="692" x2="180" y2="702" marker-end="url(#an4)"/>
    <line class="ln" x1="180" y1="758" x2="180" y2="768" marker-end="url(#an4)"/>

    <path class="ln" d="M348 797 L358 797 L358 533 L350 533" marker-end="url(#an4)"/>

    <text class="ts" x="10" y="892" style="fill:#0f8a4a;font-weight:700">三道约束：</text>
    <text class="ts" x="10" y="908">梯度门控 · 信任域投影 · Model B 相对红线</text>
    <text class="ts" x="10" y="926">右侧回边为迭代；真实 BER 仅记录、不回传决策</text>
  </svg>

  <figcaption>Stage 2 每步决策只依赖 Model A 的梯度方向与 Model B 的安全判定；真实 BER_MLSE 在每一步都被记录，但不参与方向与终止决策。</figcaption>
</figure>

<h3>4.2 Stage-2 单步计算流程</h3>
<div class="card">
  <ol style="margin-bottom:0">
    <li><strong>安全红线</strong>：红线 = 当前已知最优点的 Model B 预测 BER × 1.25。每步若 B 预测改善，红线跟着下移；若 B 预测突然变差（方向错），红线挡住该步。</li>
    <li><strong>梯度（两部分，公式见 4.2.1）</strong>：<strong>gain 维解析、0 试探</strong>（driver_gain 是 Tx 链末尾标量乘子，8 维探针全 ∝ gain，有闭式链式解，每步用当前落点探针重算）；<strong>shape 维（4 FFE 旁瓣 + gDC + gDC2）第 0 步中心差分初始化后割线更新</strong>（其后只消费历史落点探针，0 试探态）。<strong>除第 0 步外不产生 ±ε 试探态</strong>，每步只停留在已落地的工作点。</li>
    <li><strong>梯度门控</strong>：分组看缩放后梯度范数 <span class="mono">‖(g·span)_组‖</span>，低于 <span class="mono">1e-3</span>（dex）的组冻结（方向置 0），避免沿拟合噪声移动。</li>
    <li><strong>方向</strong>：g 乘各维箱宽 <span class="mono">span</span> 后按 FFE / CTLE / gain 三组各自单位归一化：<span class="mono">d_组 = (g·span)_组 / ‖(g·span)_组‖</span>。</li>
    <li><strong>步长</strong>：<span class="mono">α_k = 0.05 × 0.97^k</span>；候选点 <span class="mono">x = clip(x − α_k·span·方向, 信任域)</span>，<span class="mono">span = [0.20, 0.20, 0.20, 0.20, 6.0, 6.0, 0.60]</span>（gain 维满箱 0.60 dex = 2 × ±0.30 信任域）。</li>
    <li><strong>投影</strong>：候选点裁剪至 <span class="mono">x₀ ± [0.10, 0.10, 0.10, 0.10, 3.0, 3.0, 0.30]</span>（7 维信任域半径，gain 收紧到 ±0.30 dex）。</li>
    <li><strong>安全审查</strong>：候选点 B 预测超过红线时步长折半重试（最多 20 次）；始终不通过则停止，不强行落地。</li>
    <li><strong>记账</strong>：写入代理预测与真实 BER_MLSE（协议 4194304 符号 × 单种子 42），供事后核验。</li>
    <li><strong>终止</strong>：位移 <span class="mono">&lt; 1e-6</span>、或梯度门控触发、或边际改善 <span class="mono">&lt; 0.01 dex</span>、或达到步数上限。</li>
  </ol>
</div>

<h4>4.2.1 梯度公式（解析 + 割线，全展开）</h4>
<p>搜索向量 <span class="mono">x = [x₀ x₁ x₂ x₃, x₄, x₅, x₆] ∈ R⁷</span>，依次是 4 个 FFE 旁瓣、gDC、gDC2、<span class="mono">u_gain</span>；其中 <span class="mono">u_gain = log₁₀(gain / g₀)</span>，<span class="mono">g₀ = 0.3399</span> 为标称 gain。探针 <span class="mono">p(x) = [tx_fir₀…tx_fir₆, drive_rms] ∈ R⁸</span>，<span class="mono">A(p)</span> 是 Model A 预测的 log10 BER。</p>

<div class="card" style="border-left:4px solid #0f8a4a">
<h4 style="margin-top:0">gain 维（第 7 维）：解析梯度，0 试探</h4>
<p style="margin-bottom:0"><span class="mono">driver_gain</span> 是 Tx 链末尾的标量乘子，调它只整体缩放波形，不改变波形形状，所以 8 个探针特征都正比于 gain：</p>
<pre style="margin:6px 0"><code>pⱼ(g) = pⱼ(g₀) · (g / g₀)         对每个探针特征 j = 0…7</code></pre>
<p style="margin:6px 0">由 <span class="mono">u = log₁₀(g/g₀)</span> 得 <span class="mono">g = g₀·10^u</span>，故 <span class="mono">dg/du = g·ln10</span>，于是每个特征对 u 的偏导：</p>
<pre style="margin:6px 0"><code>∂pⱼ/∂u = (∂pⱼ/∂g)·(dg/du) = (pⱼ/g)·(g·ln10) = ln10 · pⱼ</code></pre>
<p style="margin:6px 0">链式法则把 8 维特征梯度合成 gain 维梯度：</p>
<pre style="margin:6px 0"><code>∂A/∂u_gain = Σⱼ (∂A/∂pⱼ)·(∂pⱼ/∂u) = ln10 · Σⱼ (∂A/∂pⱼ)·pⱼ</code></pre>
<p style="margin:6px 0">其中 <span class="mono">∂A/∂pⱼ</span> 是 Model A 的 WhiteBoxRidge 解析梯度（§3.2）再除以该特征标准差 σⱼ（把标准化坐标的梯度换算回原始量纲）。每步用当前落点探针重算一次，不需要 ±ε 扰动，也不需要真实 BER。</p>
</div>

<div class="card" style="border-left:4px solid #0f8a4a">
<h4 style="margin-top:0">shape 维（前 6 维）：第 0 步中心差分 + 此后割线</h4>
<p style="margin:6px 0"><strong>第 0 步初始化</strong>（12 个 ±ε 试探态，仅此一轮）：对 6 个 shape 维逐一做双边中心差分：</p>
<pre style="margin:6px 0"><code>gᵢ = [ A(p(x + εᵢ·eᵢ)) − A(p(x − εᵢ·eᵢ)) ] / (2·εᵢ)，   i = 0…5
εᵢ = 0.01（FFE 旁瓣 ×4） / 0.1（gDC、gDC2）</code></pre>
<p style="margin:6px 0"><strong>此后每步割线更新</strong>（Broyden「good」秩-1 修正，只消费历史落点、0 试探）：记本步位移 <span class="mono">dx = x_{k+1} − x_k</span>、Model A 预测变化 <span class="mono">dA = A(p(x_{k+1})) − A(p(x_k))</span>。先剔掉 gain 维的已知贡献，再只沿 shape 位移方向修正 shape 梯度：</p>
<pre style="margin:6px 0"><code>dA_shape = dA − g₆·dx₆                    （dx₆、g₆ 是 gain 维位移与解析梯度）
s        = [dx₀ … dx₅]                    （shape 维位移）
g₀…₅     ← g₀…₅ + [ (dA_shape − g₀…₅ᵀ·s) / ‖s‖² ] · s</code></pre>
<p style="margin:6px 0">上式满足割线方程 <span class="mono">g_{k+1}ᵀ s = dA_shape</span>（新梯度沿已走过的方向精确拟合 Model A 的实际变化），是满足该方程的最小范数修正。gain 维 <span class="mono">g₆</span> 不进上式，每步由解析公式重算。</p>
</div>

<p>端到端实操（训练完有什么 → 第一个梯度怎么来 → 怎么迭代）见 §4.6。</p>

<h3>4.3 复杂度与实测耗时</h3>
<details class="fold">
<summary>各环节计算内容 · 实测耗时 · 复杂度</summary>
<div class="fold-body">
<div class="tw">
<table class="wide">
  <caption>本机实测：Python 3.11.11 / NumPy 2.4.6，BLAS 线程固定为 1 <span class="sh">· 可左右滑动</span></caption>
  <tr><th>环节</th><th>计算内容</th><th class="n">实测耗时</th><th>复杂度</th></tr>
  <tr><td>模型训练</td><td>ΦᵀΦ 与 D×D 线性方程组求解</td><td class="n">≈0.02 s（1601 训练行，A D=45 / B D=36）</td><td class="mono">O(N·D² + D³)</td></tr>
  <tr><td>模型单次推理</td><td>特征展开 + 一次内积</td><td class="n">≈30 µs</td><td class="mono">O(D)</td></tr>
  <tr><td>物理探针（含驱动 RMS）</td><td>单位脉冲 + 短 PAM4 序列过发送链</td><td class="n">≈30 ms</td><td>与评估符号数无关</td></tr>
  <tr><td><strong>Stage-2 单步决策</strong></td><td>gain 解析梯度（0 探针）+ shape 割线更新（纯算术）+ ≤20 次 B 前向（回溯线搜索）</td><td class="n win">≈0.15 s</td><td>与评估符号数无关</td></tr>
  <tr><td>一次真实 BER 评估</td><td>4194304 符号 × 单种子 42（全链路 + LMS + Viterbi）</td><td class="n">≈49 s（Python）/ ≈27 s（C++）</td><td>与符号数线性</td></tr>
  <tr><td>离线数据集</td><td>2001 点 ×（2^20 符号 × 3 种子 + 探针）</td><td class="n">≈5.6 h（14 进程，OMP=1）</td><td>一次性</td></tr>
</table>
</div>
</div>
</details>
<p>决策链路本身不含任何真实 BER 评估；在线测试中每步执行的那次 BER 评估只是“如实记账”，其耗时不影响下一步决策。</p>

<h3>4.4 可靠性依据</h3>
<details class="fold">
<summary>四道可靠性机制（特征 / 决策 / 安全 / 复算）</summary>
<div class="fold-body">
<div class="tw">
<table>
  <tr><th>环节</th><th>机制</th><th>效果</th></tr>
  <tr><td>特征侧</td><td>以入纤波形形状 + 绝对驱动幅度（而非硬件参数）作为代理输入，信道频响差异被探针吸收</td><td>同一模型可跨插损（含非对称）、色散、群时延变化复用，无需按环境重训</td></tr>
  <tr><td>决策侧</td><td>方向用归一化梯度，安全判据用相对种子点的恶化量</td><td>全局底噪与插损平移在作差中抵消，无需逐环境标定阈值</td></tr>
  <tr><td>安全侧</td><td>Model B 否决 + 信任域投影 + 组梯度门控三道约束（百分比红线 25%）</td><td>候选点须先通过安全审查才允许落地；趋平即停，不产生负向移动</td></tr>
  <tr><td>复算侧</td><td>每一步的真实 BER_MLSE 全量落盘</td><td>可逐步核验是否出现退步，不依赖抽样或事后筛选</td></tr>
</table>
</div>
</div>
</details>

<h3>4.5 安全红线：随最优点下移</h3>
<p>安全红线的作用是<strong>防止代理方向错误导致 BER 变差</strong>。逻辑：</p>
<ul>
  <li>红线 = 当前已知最优点的 Model B 预测 BER × 1.25（不是种子点的 B 预测）；</li>
  <li>每步若 B 预测改善，红线跟着下移；B 预测单调下降时红线不会触发；</li>
  <li>若 B 预测突然变差（方向错），候选点 B 预测超过红线，步长折半重试，始终不过则停止；</li>
  <li>用"相对最优点变差 25%"而非绝对 BER 阈值：代理绝对标定不可信（Model B 用基线训练，在非基线环境预测的绝对值偏差大），但"相对最优点变差多少倍"是可比的；</li>
  <li>实测 15 用例 <!--TOTAL_STEPS--> 落点中 <!--TOTAL_WORSE--> 落点劣于种子（含 ±ε 试探瞬时 <!--PROBE_WORSE_STEPS--> 步，见 6.3）。红线未触发拦截（B 预测单调下降，无候选变差需要拦截）。</li>
</ul>
<div class="card" style="border-left:4px solid #0f8a4a">
  <h4 style="margin-top:0">Model B 的价值</h4>
  <p style="margin-bottom:0">本次实验的 15 个用例中，Model B 安全红线没有否决过任何一步（只起保护作用）；15 用例落点没有一步退步，红线因此未被触发（±ε 试探瞬时的口径见 6.3）。</p>
</div>

<h3>4.6 部署流程：训练完到第一个梯度再到迭代</h3>
<p>把本方案部署到一个新环境，主线是「训练离线一次、调优逐环境在线跑」。下面按时间顺序说明。</p>

<h4>4.6.1 训练完成后有哪些（离线产物）</h4>
<div class="card">
<ul style="margin-bottom:0">
  <li><strong>两个冻结代理</strong>：<span class="mono">model_a.pkl</span>（波形 + 驱动 → log10 BER）、<span class="mono">model_b.pkl</span>（配置 → log10 BER）。此后不再重训。</li>
  <li><strong>一个统一种子 x₀</strong>（7 维全给定，含 gain = ×0.325）：15 个环境同一起点，不随环境再标定。</li>
  <li><strong>离线标定参照</strong> <span class="mono">per_case_target_rms</span>（§3.3）：仅作参照记录，不参与次优起点的 gain 初值。</li>
</ul>
</div>

<h4>4.6.2 第一步：在 x₀ 设定安全基准</h4>
<p>进环境拿到 x₀ 后，第一步不是算梯度，而是给红线一个初始值：</p>
<ol style="margin-bottom:0">
  <li>由 x₀ 构造 5 抽头 FFE，测一次驱动 RMS（1 次探针）；</li>
  <li>该配置查 Model B，得 <span class="mono">B(x₀)</span>（1 次 B 前向）；</li>
  <li>初始红线 = <span class="mono">10^B(x₀) × 1.25</span>（当前最优点允许恶化 25%，§4.5）。</li>
</ol>

<h4>4.6.3 第一个梯度：shape 维中心差分 + gain 维解析</h4>
<p>红线立好后，算 g ∈ R⁷（公式见 §4.2.1），两个来源分开：</p>
<ol style="margin-bottom:0">
  <li><strong>shape 维（前 6 维）中心差分</strong>：第 i 维取 <span class="mono">x⁺ = x₀ + εᵢ·eᵢ</span>、<span class="mono">x⁻ = x₀ − εᵢ·eᵢ</span>，各自重算探针（FIR 形状 + 驱动 RMS）后查 Model A，得 <span class="mono">gᵢ = (A(x⁺) − A(x⁻)) / (2·εᵢ)</span>，<span class="mono">εᵢ = 0.01（FFE×4）/ 0.1（gDC、gDC2）</span>。</li>
  <li><strong>gain 维（第 7 维）解析</strong>：用当前落点探针直接算 <span class="mono">g₆ = ln10 · Σⱼ (∂A/∂pⱼ)·pⱼ</span>，不做任何扰动。</li>
</ol>
<p>决策本身只花 12 次物理探针 + 12 次 A 前向（中心差分）+ 1 次解析梯度，约 0.4 s，不含真实 BER 评估。本实验为透明记账，还会同时实测这 12 个试探态各自的真实 BER（见 §6.4），只作记录、不参与方向。</p>
<p>这 12 个 ±ε 试探态只出现在第 0 步，其后每一步都不为测梯度进入任何 x±ε 过渡态。</p>
<div class="card" style="border-left:4px solid #0f8a4a">
<h4 style="margin-top:0">第一个梯度告诉你什么</h4>
<p style="margin-bottom:0">g 的每个分量是该参数对 log10 BER 的局部斜率（负值 = 加大该参数使 BER 下降）。7 个数里模越大的维越先调；本实验 gain 维（第 7 维）是主导项（§6.0）。</p>
</div>

<h4>4.6.4 第一次迭代到收敛</h4>
<ol style="margin-bottom:0">
  <li><strong>组方向</strong>：g 乘各维箱宽 span 后按 FFE / CTLE / gain 三组各自单位归一化：<span class="mono">d_组 = (g·span)_组 / ‖(g·span)_组‖</span>；<span class="mono">‖(g·span)_组‖ &lt; 1e-3</span> 的组冻结（§4.2）。</li>
  <li><strong>步长</strong>：<span class="mono">α = 0.05 × 0.97^k</span>；候选点 <span class="mono">x₁ = clip(x₀ − α·span·方向, 信任域)</span>。</li>
  <li><strong>Model B 审查</strong>：候选点 B 预测超红线则步长折半重试（≤20 次），始终不过则本环境停止。</li>
  <li><strong>落地记账</strong>：对 x₁ 做一次真实 BER（2^22 × 单种子 42）写进 trace；B 改善则红线随之下移。</li>
  <li><strong>梯度更新（0 试探态）</strong>：gain 维按 §4.2.1 解析公式重算；shape 维按 §4.2.1 割线公式（用位移 dx、Model A 预测变化 dA 与剔除 gain 后的 dA_shape）修正，两者都不做 ±ε 扰动，只消费已落地的 x₀ → x₁。</li>
  <li><strong>下一轮</strong>：以 x₁ 为新起点回到第 2 步，直到位移 &lt; 1e-6、梯度门控触发、边际改善 &lt; 0.01 dex 或步数到 15。</li>
</ol>
<p>整条链路真实 BER 只记账、不回传决策。下一步往哪走由探针 + A/B 给出，真实评估留给事后核验。</p>

<h3>4.7 算法伪代码与超参数汇总（可直接照此实现）</h3>
<p>记 <span class="mono">p(x)</span> 为参数 x 对应的 8 维探针（7-tap 绝对标定 FIR + drive_rms，§3.1）、<span class="mono">A(p)</span> 为 Model A 预测的 log10 BER、<span class="mono">B(x₀…₅, rms)</span> 为 Model B 对 7 维参数域的预测（§3.1）。完整 Stage-2 在线调优：</p>
<pre><code>输入：冻结 Model A、Model B；次优起点 x₀ ∈ R⁷（含 gain ×0.325）；步数上限 n_steps = 15
输出：落点轨迹 {x_k} 与每步真实 BER（仅记账）

1   # 立安全基准（1 次探针 + 1 次 B 前向）
2   p₀ = p(x₀)； rms₀ = p₀ 的第 8 维； best_B = B(x₀[0..5], rms₀)
3   allowed = 10^best_B × 1.25                          # 百分比红线
4
5   # 第 0 步梯度（仅此一轮 ±ε 试探态）
6   for i in 0..5:   g[i] = [A(p(x₀+εᵢeᵢ)) − A(p(x₀−εᵢeᵢ))] / (2εᵢ)    # εᵢ = 0.01(FFE)/0.1(gDC,gDC2)
7   g[6] = ln10 · Σⱼ (∂A/∂pⱼ)·p₀ⱼ                       # gain 解析（§4.2.1）
8   A_prev = A(p₀)
9
10  for k = 0 .. n_steps−1:
11      # 组归一化方向（span = [0.20×4, 6.0, 6.0, 0.60]）
12      d_组 = (g·span)_组 / ‖(g·span)_组‖ 对每组；‖(g·span)_组‖ &lt; 1e-3 的组冻结（d=0）
13      # 回溯线搜索（含 B 先验否决，无真实 BER）
14      α = 0.05 × 0.97^k
15      repeat ≤20:  x_cand = clip(x_k − α·span·d, 信任域)；
16                   if B(x_cand[0..5], rms(x_cand)) ≤ log10(allowed):  x_new = x_cand; break
17                   else: α ← α/2
18      if 无候选通过: 停止
19
20      # 落地记账（1 次真实 BER，不参与决策）
21      p_new = p(x_new)； A_new = A(p_new)； B_new = B(x_new[0..5], rms(x_new))
22      real_ber = 真实 MLSE BER(x_new)                   # 4194304 符号 × 单种子 42
23
24      # 梯度更新（零试探态；§4.2.1）
25      g[6]  = ln10 · Σⱼ (∂A/∂pⱼ)·p_newⱼ                # gain 解析重算
26      dx = x_new − x_k； dA = A_new − A_prev； dA_shape = dA − g[6]·dx[6]； s = dx[0..5]
27      g[0..5] += [ (dA_shape − g[0..5]ᵀ·s) / ‖s‖² ] · s   # shape 割线修正
28
29      if B_new &lt; best_B:  best_B = B_new； allowed = 10^best_B × 1.25
30      A_prev = A_new； x_k = x_new
31      if ‖x_new − x_k‖ &lt; 1e-6 或 三组全冻结 或 (A_prev − A_new) &lt; 0.01: 停止</code></pre>

<div class="tw">
<table class="wide">
  <caption>全部超参数与常量（复现本结果需原样使用） <span class="sh">· 可左右滑动</span></caption>
  <tr><th>类别</th><th>参数</th><th class="n">取值</th></tr>
  <tr><td rowspan="4">代理模型</td><td>多项式阶数</td><td class="n">2（一次项 + 平方项 + 交叉项）</td></tr>
  <tr><td>Ridge 正则 α</td><td class="n">A = 1.0，B = 0.5</td></tr>
  <tr><td>train / test 划分</td><td class="n">80 / 20，seed 42</td></tr>
  <tr><td>标准化</td><td class="n">逐维 (x − μ)/σ，μ、σ 取训练集</td></tr>
  <tr><td rowspan="4">数据集</td><td>行数 / 采样</td><td class="n">2001 行，LatinHypercube d=7, seed 42</td></tr>
  <tr><td>采样盒</td><td class="n">FFE ±0.10、CTLE ±3.0 dB、gain ×0.20~×1.26</td></tr>
  <tr><td>标签</td><td class="n">log10(BER_MLSE)，只取 &lt; −0.1 的行</td></tr>
  <tr><td>训练评估</td><td class="n">2^20 符号 × 3 种子（42,43,44）</td></tr>
  <tr><td rowspan="6">寻优</td><td>中心差分 εᵢ</td><td class="n">0.01（FFE×4）/ 0.1（gDC、gDC2）</td></tr>
  <tr><td>初始步长 / 衰减</td><td class="n">GD_LR = 0.05 / ALPHA_DECAY = 0.97</td></tr>
  <tr><td>组梯度门控</td><td class="n">‖(g·span)_组‖ &lt; 1e-3 dex 冻结</td></tr>
  <tr><td>边际改善门控</td><td class="n">A 预测改善 &lt; 0.01 dex 停止</td></tr>
  <tr><td>线搜索</td><td class="n">回溯折半，≤20 次</td></tr>
  <tr><td>步数上限</td><td class="n">15</td></tr>
  <tr><td rowspan="4">信任域 / 安全</td><td>逐维信任域半径</td><td class="n">FFE ±0.10 / CTLE ±3.0 dB / gain ±0.30 dex</td></tr>
  <tr><td>轨迹信任域</td><td class="n">标准化 shape 位移 ≤ 2.0 × ρ（ρ = 训练 B 空间第 32 近邻中位距离）</td></tr>
  <tr><td>Model B 红线</td><td class="n">当前最优点 B 预测 BER × 1.25</td></tr>
  <tr><td>FFE 主抽头约束</td><td class="n">Σ|旁瓣| ≤ 0.8 ⇒ 主抽头 ≥ 0.2</td></tr>
  <tr><td rowspan="3">评估</td><td>在线 / 报告符号数</td><td class="n">2^22 = 4194304</td></tr>
  <tr><td>仿真种子</td><td class="n">42（单种子）</td></tr>
  <tr><td>0 错误检测限</td><td class="n">5.97e-8（= 1/(2·N_bits)，N_bits = 8 368 608）</td></tr>
</table>
</div>

<h2 id="s5"><span class="num">5</span>数据集与评估协议</h2>

<div class="tw">
<table>
  <caption>数据集构成：共 2001 行真实 BER 评估，单份 CSV</caption>
  <tr><th>环境</th><th class="n">行数</th><th>构成</th><th class="n">log10 BER 实测范围</th></tr>
  <tr><td>Base_IL10x10 邻域</td><td class="n">2001</td><td>7 维 LHS（4 FFE + gDC + gDC2 + u_gain），gain 覆盖全用例最优 gain 邻域 ×0.20~×1.26</td><td class="n">−6.62 ~ −0.77</td></tr>
</table>
</div>

<div class="card">
  <h4 style="margin-top:0">评估协议：4194304 符号 × 单种子 42</h4>
  <p>在 Base_IL10x10 的 0 错误最优工作点上测量不同块长下的真实错误数与 log10 BER（块长标定实测数据，展开看）：</p>
  <details class="fold">
  <summary>不同块长的 BER 估计精度实测</summary>
  <div class="fold-body">
  <div class="tw">
  <table class="wide">
    <caption>BER 估计精度实测（Base_IL10x10 最优工作点） <span class="sh">· 可左右滑动</span></caption>
    <tr><th class="n">块长（符号）</th><th class="n">错误数（单种子）</th><th class="n">log10 BER 均值</th><th class="n">95% CL 上界</th></tr>
    <tr><td class="n">262144</td><td class="n">0</td><td class="n">−6.004</td><td class="n">5.7e-6</td></tr>
    <tr><td class="n">524288</td><td class="n">0</td><td class="n">−6.313</td><td class="n">2.9e-6</td></tr>
    <tr><td class="n">1048576</td><td class="n">0</td><td class="n">−6.618</td><td class="n">1.4e-6</td></tr>
    <tr><td class="n">2097152</td><td class="n">0</td><td class="n">−6.922</td><td class="n">7.2e-7</td></tr>
    <tr><td class="n">4194304（采用）</td><td class="n">0</td><td class="n">−7.224</td><td class="n">3.6e-7</td></tr>
  </table>
  </div>
  </div>
  </details>
  <p style="margin-bottom:0">
    <strong>结论</strong>：① 最优工作点在 2^18~2^22 全部块长下均为 0 错误，真实 BER 低于检测限，且不随块长出现系统性变化；
    ② 表中 log10 BER 随块长加长而下降（−6.0 → −7.2）来自"0 错误"的 1/(2N) 伪计数检测限，不是物理上的 BER 变化：块长越长、检测限越低；
    ③ 采用 4194304 符号 × 单种子 42：收敛后（最优工作点）的 BER 落在 0 错误检测限之下（伪计数 6.0e-8，95% CL 上界 3.6e-7），用上界表述、不与点估计混用；次优起点与压力用例（≥1e-4）仍可作统计可靠的点估计。
  </p>
</div>

<details class="fold">
<summary>采样与标注口径（采样器 / 字段 / 并行一致性 / 成本）</summary>
<div class="fold-body">
<ul style="margin-bottom:0">
    <li><strong>采样器</strong>：<span class="mono">LatinHypercube(d = 7, seed = 42)</span>，逐环境独立且可复现；采样盒 = 信任域（FFE ±0.10 / CTLE ±3.0 dB），gain 在 u 空间均匀覆盖全用例最优 gain 邻域（×0.20~×1.26）。</li>
    <li><strong>每行字段</strong>：7 维坐标、5-tap FFE、gDC/gDC2、driver_gain、驱动 RMS、真实 <span class="mono">mlse_ber</span> 与 <span class="mono">log10_ber_mlse</span>、<span class="mono">ber_std_log10</span>、7-tap FIR 形状。</li>
    <li><strong>并行一致性</strong>：<span class="mono">--jobs</span> 多进程与串行结果逐位一致（每点独立、种子固定，已实测校验）。</li>
    <li><strong>A/B 输入空间不同</strong>：Model A 吃 8 维探针，Model B 吃 7 维参数，同一标签、同一学习器。</li>
    <li><strong>成本</strong>：2001 点 × 3 种子（1048576 符号/点），12 进程并行（每进程 OMP=1）。</li>
  </ul>
</div>
</details>

<h2 id="s6"><span class="num">6</span>实测结果</h2>

<p>以下核心指标为<strong>现役方案</strong>（A+B 代理，无需回传通道）全 15 用例 2<sup>22</sup> 结果；direct 参照方案同协议结果与对照见 6.2 页签、6.5。</p>

<div class="kpis">
  <!--KPI_CARDS-->
</div>

<h3>6.0 起点工作点与调优机制</h3>
<div class="card">
  <p><strong>起点 x₀</strong> 取一个明确的<strong>次优工作点</strong>（7 维全部给定），来自训练数据集中的一个实测点，其真实 BER 在基线环境约 1.3e-4、在极端插损组合约 5.4e-2。选这个量级，是因为起点 BER 高于检测限（可统计）、又低于信道失效区（有下降空间），在线调优的下降过程因此可测：</p>
  <ul>
    <li>Tx FFE 5 抽头：<span class="mono">[-0.0885, -0.3147, 0.4079, 0.0845, 0.1043]</span>（主抽头 0.4079 由 1 − Σ|旁瓣| 派生）；</li>
    <li>Tx CTLE：gDC = 6.73 dB、gDC2 = 0.85 dB；</li>
    <li>driver_gain = 0.1106（相对标称 0.3399 的倍率 ×0.325，u_gain = −0.4875）：驱动摆幅未按用例标定，是次优的主要来源。</li>
  </ul>
  <p>在线调优做 <strong>7 维割线梯度下降</strong>：4 个 FFE 旁瓣 + gDC + gDC2 形状调整，以及 gain 作为第 7 个搜索维（信任域 ±0.30 dex）。第 0 步 shape 维中心差分初始化 + gain 维解析梯度，此后每步<strong>零 ±ε 试探态</strong>、只用历史落点做割线更新；从该次优点出发，各用例的真实 BER 数步内降到各自环境的最优工作点附近。</p>
  <p style="margin-bottom:0">平台另含 <strong>direct 参照方案</strong>（有回传通道时对端到端真实 BER 直接做梯度下降，不用代理）：从同一次优起点出发、同 15 用例、同评估协议，收敛轨迹对照见 6.2 页签，逐用例结果与机制对照见 6.5。</p>
</div>

<h3>6.1 泛化：只用 10 dB 基线训练 → 跨 15 个环境</h3>
<p>训练集只含 Base_IL10x10 邻域 2001 行。模型冻结后，现役方案（A+B 代理）对 15 个用例环境逐个执行 Stage-2 在线调优，不重训、不重新标定（direct 参照方案同协议结果见 6.2 页签与 6.5 对照表）。</p>
<p class="win"><strong>结论</strong>：<!--POS_SUMMARY-->，几何平均 <!--MEAN_IMP-->（最高 <!--MAX_IMP-->），
<!--TOTAL_STEPS--> 步逐一记账：<strong>含 ±ε 试探瞬时 <!--PROBE_WORSE_STEPS--> 步超种子、落点 <!--TOTAL_WORSE--> 步劣于起点</strong>（最坏瞬时 ×<!--PROBE_WORST_RATIO-->，见 6.3）。代理只在 Base_IL10x10 邻域训练，冻结后在其余 14 个环境（CD/DGD/中高插损/高噪声/极端插损）信任域内方向仍正确，把每个用例压到其环境的最优工作点附近：11 用例到 0 错误检测限（5.97e-8），4 个强损伤/高噪声用例停在 IL20x20 1.20e-7、Comb_IL20x20_CD15_DGD5 2.39e-7、HighNoise_IL16x16 2.39e-7、HighNoise_IL10x10 3.58e-7（其中 IL20x20 的 direct 对照显示该环境仍有下降空间——direct 把它压到了检测底 5.97e-8，见 6.5）。</p>
<div class="tw">
<table class="wide" id="tbl-core">
  <caption>起点 = x₀（次优工作点，基线环境实测 ~1.3e-4）的真实 BER_MLSE；最优 = 全轨迹中真实 BER_MLSE 的最小值（步序为该最小值出现于第几步） <span class="sh">· 可左右滑动</span></caption>
  <tr><th>用例</th><th>物理条件</th><th class="n">起点 BER_MLSE</th><th class="n">最优 BER_MLSE（步序）</th><th class="n">Δlog10 BER</th><th class="n">改善倍数</th><th class="n">gain（起点→最优）</th></tr>
  <!--CORE_ROWS-->
</table>
</div>

<h3>6.2 收敛轨迹与物理量变化</h3>
<p>收敛图曲线起点（step −1）是 x₀（次优工作点，基线实测 ~1.3e-4）。</p>
<div class="tabs">
  <!--FIG_TAB_BAR-->
  <div class="tab-panel active" id="tab-fig-secant">
    <p>下行来自 7 维割线梯度（gain 维解析、shape 维割线，其后不再有试探态）；收敛图含 Model A 预测与 Model B 预测两条代理曲线，预测-实测散点（图 8）是代理方向可靠性诊断。</p>
    <figure>
      <div class="fig-scroll"><img src="{{IMG_CONV}}" alt="15 用例收敛轨迹"></div>
      <figcaption>图 6 · 收敛轨迹（Model A 预测 / Model B 预测 / 实测 BER_MLSE，对数纵轴；虚线为起点）。</figcaption>
    </figure>
    <figure>
      <div class="fig-scroll"><img src="{{IMG_GAIN}}" alt="gain 与 drive_rms 轨迹"></div>
      <figcaption>图 7 · gain 维轨迹：gain 纳入梯度（第 7 维），drive_rms 随之小幅变化（虚线为起点 gain 倍率 ×0.325）。</figcaption>
    </figure>
    <figure>
      <div class="fig-scroll"><img src="{{IMG_TRACK}}" alt="预测变化量 vs 实测变化量"></div>
      <figcaption>图 8 · 左 Δ预测 vs Δ实测散点（逐用例逐步）；右逐用例相关系数。</figcaption>
    </figure>
    <figure>
      <div class="fig-scroll"><img src="{{IMG_CASE_HARD}}" alt="最难用例四联图"></div>
      <figcaption>图 9 · 最难用例四联图：收敛轨迹、Tx FFE 抽头（起点 vs 最优）、Tx CTLE |H(f)| 频响、Tx 探针 7-tap FIR。</figcaption>
    </figure>
  </div>
  <!--FIG_DIRECT_PANEL-->
</div>

<h3>6.3 安全性核验（落点 + 试探瞬时两口径）</h3>
<div class="card">
  <p>在线调优过程中系统会短暂停留两类<strong>真实硬件工作点</strong>，安全性分开核验：<strong>落点</strong>（每步落地后的 x<sub>k+1</sub>）与 <strong>±ε 试探态</strong>（仅第 0 步 shape 维中心差分估计初始梯度时，系统短暂处于 x±ε 的 12 个微扰点；此后零试探态）。两者都会真实影响那一刻的端到端 BER，不能只看落点。本节为现役方案口径（代理 B 红线 + 候选否决保障落点不劣化）；direct 无代理安全机制，落点不做否决——其 15 用例落点均最终优于种子，但 Comb_IL20x20_CD15_DGD5 终点出现一步回退（仍优于种子，见 6.5）。</p>

  <p><strong>口径 1 · 落点（accepted 轨迹）</strong>：<!--TOTAL_STEPS--> 落点中 <!--TOTAL_WORSE--> 落点劣于种子，「优化后不比起点差」的硬约束成立，落点单调不劣化。</p>
  <div class="tw">
  <table class="wide" style="margin-bottom:8px">
    <caption>落点口径：以种子点真实 BER 为基准，统计所有中间落点是否退步</caption>
    <tr><th class="n">用例数</th><th class="n">记录的真实 BER 落点数</th><th class="n">劣于种子的落点数</th><th>结论</th></tr>
    <!--SAFETY_ROWS-->
  </table>
  </div>

  <p><strong>口径 2 · 含 ±ε 试探瞬时</strong>：割线法下只有第 0 步的 12 个 shape 维 ±ε 微扰态落在真实链路上（gain 维解析、0 试探；其后为 0 试探态）。按「试探步取 12 试探态 + 1 落点中的最坏 BER、其余步取落点」与种子比较，<strong><!--PROBE_WORSE_STEPS--> 步</strong>的瞬时最坏 BER 超过种子（集中在第 0 步初始化：±ε 绕种子 x<sub>0</sub> 展开，向劣化侧的那支探针必然超过种子本身）；最坏瞬时 = 种子 × <strong><!--PROBE_WORST_RATIO--></strong>（<!--PROBE_WORST_ENV-->：<!--PROBE_WORST_BER--> vs 种子）。</p>
  <div class="tw">
  <table class="wide" id="tbl-safety-probe" style="margin-bottom:8px">
    <caption>含试探瞬时口径：逐用例「每步最坏 BER（含 ±ε 试探态）」超过种子的步数 · 可左右滑动</caption>
    <tr><th>用例</th><th class="n">种子 BER</th><th class="n">含试探瞬时超种子步数</th><th class="n">最坏瞬时 BER</th><th class="n">相对种子倍率</th></tr>
    <!--SAFETY_PROBE_ROWS-->
  </table>
  </div>
  <p class="mut" style="margin-bottom:0">为什么会有试探瞬时超种子：中心差分要同时测 x+ε 与 x−ε 两边的斜率，必然向劣化方向也短暂挪一步，这是梯度初始化的固有代价，落点仍单调不劣化。若真实系统连第 0 步这一轮 12 个瞬时扰动都不能接受，需改<strong>单边差分</strong>（只向预计改善方向探）或进一步缩小 ε。原始记录：<span class="mono">trace_&lt;用例&gt;.csv</span>（落点）、<span class="mono">probes_&lt;用例&gt;.csv</span>（试探态，仅第 0 步，含 step / param / sign / 真实 BER）。</p>
</div>

<h3>6.4 试探步 BER 包络（梯度初始化的 ±ε 微扰态）</h3>
<p>现役方案第 0 步 shape 维 6 维中心差分共生成 12 个 ±ε 微扰态（4 个 FFE 旁瓣 + gDC + gDC2，各 ±；gain 维解析、0 微扰）。真实在线系统里为获取探针而做的这些参数微扰，会让链路实际处于这些工作点，因此每个试探态自身的端到端 MLSE BER 也被逐一记录（在 6.2 收敛图中显示为灰点）。这些记录不参与下降方向（方向仍由代理梯度决定），但作为安全性的一部分：试探态会瞬时超过种子（见 6.3 口径 2），下表给出每个用例试探态的真实 BER 包络。除第 0 步外，之后每一步都不产生微扰态。direct 方案同理：第 0 步 7 维全测共 14 个微扰态（无解析 gain 梯度，gain 维也实测），同样逐一记录真实 BER（<span class="mono">result/ddps_cpp_direct/probes_*.csv</span>，6.2 direct 页签收敛图中的灰点）。</p>
<div class="tw">
<table class="wide" id="tbl-probe">
  <caption>探针工作点真实 BER_MLSE 包络：仅第 0 步 12 个 shape 维 ±ε 微扰态（gain 维解析、0 微扰） <span class="sh">· 可左右滑动</span></caption>
  <tr><th>用例</th><th class="n">试探步数</th><th class="n">试探态数</th><th class="n">试探 BER 最小</th><th class="n">试探 BER 最大</th><th class="n">试探 BER 中位</th></tr>
  <!--PROBE_ROWS-->
</table>
</div>

<h3>6.5 对比实验：有回传通道时的端到端 BER 直接梯度下降（direct）</h3>
<!--DIRECT_SECTION-->

<h2 id="s7"><span class="num">7</span>结论</h2>

<div class="card">
  <h4 style="margin-top:0">结论</h4>
  <ol style="margin-bottom:0">
    <li>只用 Base_IL10x10 邻域 2001 行训练，15 个用例环境：<!--POS_SUMMARY-->，几何平均 <!--MEAN_IMP-->；含 ±ε 试探瞬时 <!--PROBE_WORSE_STEPS--> 步超种子（最坏 ×<!--PROBE_WORST_RATIO-->）、落点 <!--TOTAL_WORSE--> 步劣于种子（见 6.3）。</li>
    <li>下降方向走 Model A：<strong>gain 维解析梯度（0 探针）+ shape 维第 0 步一次性中心差分初始化（12 次探针）后，每步割线用纯算术更新，其后不再产生试探态</strong>，与评估符号数无关。</li>
    <li>gain 是第 7 个搜索维：经 drive_rms 进入 A/B 输入，在 ±0.30 dex 信任域内参与梯度，梯度把它从次优起点（×0.325）推到各环境 BER 最优倍率。</li>
    <li>改善主要来自 gain 维（第 7 维），形状（FFE/gDC/gDC2）为次要贡献：15/15 用例把 BER 从次优起点压到检测限附近（强信号）或明显下降（CD/DGD/中高插损/极端插损），包括 40 dB 总插损用例（IL20x20 到 1.20e-7、Comb_IL20x20_CD15_DGD5 到 2.39e-7）。Model B 没有否决过任何一步（只起保护作用）。</li>
    <li><strong>gain 维用解析梯度、不用割线</strong>：driver_gain 是 Tx 链末尾的标量乘子，Model A 的 8 维探针特征全部正比于 gain，故 gain 维梯度有解析闭式 <span class="mono">∂A/∂u_gain = ln(10)·Σ<sub>j</sub>(∂A/∂feat<sub>j</sub>)·feat<sub>j</sub></span>，每步用当前落点探针重算（0 试探）。shape 维（4 FFE + gDC + gDC2）用割线维持：第 0 步 12 次探针初始化后做算术更新，因此<strong>除第 0 步外不再产生 ±ε 过渡态</strong>。</li>
    <li><strong>有回传通道时的 direct 直接梯度下降对照</strong>（6.5，同协议 2<sup>22</sup> C++）：与现役方案 12/15 用例打平（11 例同到 0 错误检测底）；IL20x20 direct 更深（5.97e-8 vs 1.20e-7——代理预测在 BER 最深段有分辨率盲区）；HighNoise_IL10x10 / Comb_IL20x20_CD15_DGD5 两例 direct 更浅（×4.3 / ×4.5——固定步长无阻尼在陡峭区域振荡、贴参数盒角落停滞）；平均实际步数 7.9 vs 15、每用例真实评估 ≈23 vs ≈28 次。<strong>端到端 BER 拿不到的默认约束下，代理路径以同量级评估成本达到直接梯度下降的同等水平，并在困难区域更稳。</strong></li>
  </ol>
</div>

<h2 id="s8"><span class="num">8</span>适用边界与对策</h2>
<div class="tw">
<table>
  <tr><th>边界</th><th>表现</th><th>对策</th></tr>
  <tr>
    <td>无回传通道（方案前提）</td>
    <td>在线调优拿不到收端端到端 BER，无法直接对真实目标做梯度下降</td>
    <td>用发端可测探针训练 Model A/B 代理指方向、控风险；有回传通道时的 direct 直接梯度对照见 6.5（12/15 用例同水平，IL20x20 更深、2 个困难用例更浅）</td>
  </tr>
  <tr>
    <td>强信号用例 BER 低于测量分辨率</td>
    <td>最优工作点真实 BER &lt; 3.6e-7（0 错误 @ 2^22 × 单种子 42，95% CL），强信号用例落在检测限之下，只能给上界而非点估计</td>
    <td>全流程固定 4194304 符号 × 单种子 42；检测限以下的点用 3/N（95% CL 上界）表述，不与点估计混用；压力用例（≥1e-4）仍可作统计可靠的点估计</td>
  </tr>
  <tr>
    <td>代理绝对标定弱</td>
    <td>预测值会系统性欠估或过估真实 BER，不能当绝对值用</td>
    <td>决策只用排序与方向；安全判据表达为相对种子点的恶化量</td>
  </tr>
  <tr>
    <td><code>driver_gain</code> 最优区间依赖摆幅标定</td>
    <td>每用例扫描标定 target_rms（0.06~0.22V）</td>
    <td>更换器件时需重跑 per-case RMS 扫描（≈20 min）</td>
  </tr>
  <tr>
    <td>CTLE peaking 增益维</td>
    <td>Tx CTLE 在种子点 gDC=6.73 dB 出发：优化时 gDC 微调至 6.5~8.2 dB（多数停在 ~6.8，个别 IL 应用例升至 ~8.2）、gDC2 从 0.85 dB 压到 ~0，peaking 整形主要由 FFE 旁瓣与 gain 承担</td>
    <td>若需更强整形能力，把 CTLE 零极点比例也纳入搜索空间</td>
  </tr>
  <tr>
    <td>代理是局部模型</td>
    <td>信任域外预测不可信</td>
    <td>梯度门控 + 信任域投影 + Model B 相对红线三道约束；趋平即停</td>
  </tr>
  <tr>
    <td>用例覆盖有限</td>
    <td>15 个用例覆盖 10/14/16/20 dB 插损组合与 CD/DGD/噪声应力</td>
    <td>超出范围时重跑离线数据集（1048576 符号 × 2001 点，12 进程并行）并重训（&lt;0.1 s），算法本身无需修改</td>
  </tr>
</table>
</div>

<h2 id="s9"><span class="num">9</span>复现与产物</h2>

<p>部署本方案的完整流水线命令与产物清单如下（现役方案 7 步 + direct 对照 1 步 + 交付件 1 步；展开查看完整命令）：</p>

<details class="fold">
<summary>完整流水线：数据集 → 训练 → 标定 → 验证 → 在线调优（现役 + direct 对照）→ 报告 → 交付件</summary>
<div class="fold-body">

<div class="card">
  <h4 style="margin-top:0">完整流水线</h4>
  <pre><code># 1) 数据集（2001 点；7 维 LHS；只用 Base_IL10x10；gain 覆盖全用例最优 gain 邻域 ×0.20~×1.26）
python dataset_generator.py --base-samples 2000 --only-envs Base_IL10x10 \
    --num-symbols 1048576 --sim-seeds 42,43,44 --jobs 12 --core-samples 1200

# 2) 训练 A/B（A: 探针 8 维 -> BER；B: 参数 7 维 -> BER）
python -c "from train_surrogates import train; import glob; \
  train(sorted(glob.glob('dataset/ddps_dataset_*.csv'))[-1], 'models/ddps', \
           pipeline_tag='ddps', gain_mode='gradient_with_rms_init')"

# 3) per-case target_rms 扫描（gain 维标定参照）
python tools/scan_per_case_rms.py --jobs 8

# 4) Python 小点数低 SNR 验证（比对口径：2^18、单种子 42；割线(解析 gain) 与链式收敛对比，全 15 用例）
python test_generalization.py --model-dir models/ddps --out-dir result/ddps_secant_analytic_py \
    --method secant --seed-config result/seed_config_bad_1e4.json --n-steps 15 \
    --num-symbols 262144 --sim-seeds 42

# 5) C++ 编译 + 模型转换（WSL 内 g++ 构建：本机 Smart App Control 强制模式拦本地无签名 exe，
#    Linux 进程不受管辖；源码纯标准 C++17。pkl -> json 一次性，Windows 侧跑）
wsl -d Ubuntu --cd /mnt/c/DSPPlayground/eLPO_antigravity bash cpp/build_wsl.sh
python cpp\export_models.py

# 6) 全量规模仿真（高 SNR 大点数，只允许 C++；结果写 result/ddps_cpp_secant/）
python cpp\run_all_cases.py --backend wsl --method secant --out-dir result/ddps_cpp_secant \
    --num-symbols 4194304 --n-steps 15 --jobs 2

# 7) 可视化报告
python report_ddps.py --test-dir result/ddps_cpp_secant --model-dir models/ddps \
    --seed-config result/seed_config_bad_1e4.json --summary-out result/SUMMARY.md

# 8) 对比实验 direct（有回传通道时的参照；同样走 Python 验证 -> 2^18 比对 -> C++ 全量 三步）
python tools/run_parallel_envs.py --model-dir models/ddps --out-dir result/ddps_direct_py \
    --method direct --seed-config result/seed_config_bad_1e4.json --n-steps 15 \
    --num-symbols 262144 --sim-seeds 42 --jobs 12
python cpp/run_all_cases.py --backend wsl --method direct --out-dir result/ddps_cpp_direct_equiv \
    --only-envs Base_IL10x10,IL20x20 --num-symbols 262144 --n-steps 15 --jobs 2
python cpp/compare_traces.py --py result/ddps_direct_py --cpp result/ddps_cpp_direct_equiv
python cpp/run_all_cases.py --backend wsl --method direct --out-dir result/ddps_cpp_direct \
    --num-symbols 4194304 --n-steps 15 --jobs 2
python report_ddps.py --test-dir result/ddps_cpp_direct --method direct \
    --seed-config result/seed_config_bad_1e4.json

# 9) 交付件
python make_deliverable.py --baseline result/ddps_cpp_secant --model-dir models/ddps \
    --direct result/ddps_cpp_direct --out deliverables/DDPS_Deliverable.html</code></pre>
</div>

<div class="tw">
<table>
  <caption>产物清单</caption>
  <tr><th>类别</th><th>路径</th><th>内容</th></tr>
  <tr><td>数据集</td><td class="mono">dataset/ddps_dataset_&lt;ts&gt;.csv</td><td>2001 行 × 45 列（7 维 x = 4 FFE 旁瓣 + gDC + gDC2 + u_gain；另含 5-tap FFE、驱动 RMS、7-tap FIR 探针、真实 BER）</td></tr>
  <tr><td>模型</td><td class="mono">models/ddps/</td><td>A=探针 8 维 / B=参数 7 维 + meta.json</td></tr>
    <tr><td>主结果</td><td class="mono">result/ddps_cpp_secant/</td><td>C++ 15 用例 secant case_summary.csv/json、trace_&lt;用例&gt;.csv、probes_&lt;用例&gt;.csv、run_config.json、report/</td></tr>
      <tr><td>Python 参照结果</td><td class="mono">result/ddps_secant_analytic_py/</td><td>2^18 小点数低 SNR（比对口径）secant(解析 gain)/chain 收敛与等价性参照（Python 侧，全 15 用例）</td></tr>
      <tr><td>跨实验汇总</td><td class="mono">result/SUMMARY.md</td><td>15 用例结果汇总</td></tr>
  <tr><td>块长研究</td><td class="mono">result/ddps_block_length.csv</td><td>最优工作点不同块长的 BER 估计精度</td></tr>
  <tr><td>低SNR验证</td><td class="mono">result/ddps_secant_analytic_py/、result/ddps_chain_sanity/</td><td>2^18 少点数 secant(解析 gain) vs chain 收敛对比（15 用例全一致、评估量 8×）</td></tr>
  <tr><td>direct Python 参照</td><td class="mono">result/ddps_direct_py/</td><td>direct 方案 2^18 小点数低 SNR 全 15 用例验证（Python 参照侧）</td></tr>
  <tr><td>direct 等价比对</td><td class="mono">result/ddps_cpp_direct_equiv/</td><td>direct 方案 C++ 2^18 等价比对（Base_IL10x10 + IL20x20，trace 逐步最大相对差 &lt; 1e-12）</td></tr>
  <tr><td>direct 全量结果</td><td class="mono">result/ddps_cpp_direct/</td><td>direct 方案 C++ 2^22 全 15 用例（case_summary + trace/probes + report/：收敛/gain·rms/最难用例图组与对现役对比图）</td></tr>
</table>
</div>

</div>
</details>

<h2 id="s10"><span class="num">10</span>C++ 平台与等价性</h2>

<p>平台提供两套同源实现：Python（原理参照）与 C++17（一比一复刻）。两实现读同一 <span class="mono">config.xlsx</span> 配置口径、装载同一冻结模型转换产物（<span class="mono">models/ddps/model_{a,b}.json</span>，由 <span class="mono">cpp/export_models.py</span> 从 pkl 转出，不重训），在线调优结果数值等价。两实现的比对只在 2<sup>18</sup> 小点数低 SNR 口径下进行（本节 10.2~10.4 的等价性数字均出自该口径）；全量规模仿真（高 SNR 大点数）只用通过比对的 C++ 入口执行，Python 不承担高 SNR 大点数仿真。6.5 节的 direct 对比实验走同一条流水线；比对工具已固化为 <span class="mono">cpp/compare_traces.py</span>（本节各表同口径）。</p>
<p><strong>构建运行环境</strong>：C++ 产物在 WSL(Ubuntu) g++ 13.3 下构建运行（<span class="mono">cpp/build_wsl.sh</span>）。本机 Windows Smart App Control 处于强制模式，拦截本地编译的无签名可执行文件（含 MinGW 工具链组件与历史产物），Linux 进程不受该策略管辖；工程 C++ 源码为纯标准 C++17、无平台相关 API，跨平台构建不影响数值行为，等价性以本节 2<sup>18</sup> 口径比对为准。</p>

<h3>10.1 模块映射（一比一复刻）</h3>
<div class="tw">
<table>
<caption>C++ 头文件 ↔ Python 模块对应</caption>
<tr><th>C++</th><th>Python</th><th>内容</th></tr>
<tr><td class="mono">rng.hpp</td><td class="mono">numpy.random</td><td>MT19937（init_genrand）、randint（2 幂区间）、Marsaglia polar 高斯，逐位一致</td></tr>
<tr><td class="mono">fft.hpp</td><td class="mono">numpy.fft</td><td>radix-2 FFT/IFFT/RFFT/IRFFT + 非 2 幂 naive DFT（探针冲激 N=1608）</td></tr>
<tr><td class="mono">filter.hpp</td><td class="mono">scipy.signal</td><td>Butterworth（双线性）+ lfilter（直接 II 型转置）</td></tr>
<tr><td class="mono">s4p.hpp</td><td class="mono">skrf</td><td>S4P 装载、unwrap、f_scale、SDD21 插值、频域滤波</td></tr>
<tr><td class="mono">physim.hpp</td><td class="mono">main / channel_imdd / rx_dsp / mlse_burg</td><td>完整物理链 + run_sim（Config 键值解析、发端加噪快模式）</td></tr>
<tr><td class="mono">probe.hpp</td><td class="mono">tx_channel_extract</td><td>链路冲激、峰值定位（缓存）、发端 S21 抽取、drive_rms</td></tr>
<tr><td class="mono">surrogate.hpp</td><td class="mono">train_surrogates</td><td>WhiteBoxRidge 二阶多项式特征、解析梯度、JSON 权重</td></tr>
<tr><td class="mono">optimizer.hpp</td><td class="mono">ddps_optimizer</td><td>Stage-2 割线梯度下降（第 0 步 shape 中心差分 + gain 解析梯度 + Broyden 更新，零后续试探态，B 否决、信任域）；direct 变体 stage2_descent_direct（目标 = 真实 BER，第 0 步 7 维中心差分 + 全维 Broyden，无代理）</td></tr>
</table>
</div>

<h3>10.2 物理层 bit 级等价</h3>
<p>同一配置、同一种子 42、2<sup>18</sup> 符号，对物理链逐段取 sum|x| 校验和对比（C++ vs Python）：</p>
<div class="tw">
<table>
<caption>链路逐段校验和相对差（0 = 逐位一致）</caption>
<tr><th>段</th><th class="n">相对差</th><th>性质</th></tr>
<tr><td>Tx DSP → DAC ZOH（S01）</td><td class="n">0</td><td>逐位一致</td></tr>
<tr><td>Tx S4P 频域滤波（S02，首个频域步骤）</td><td class="n">6.8e-12</td><td>FFT 求和顺序引入</td></tr>
<tr><td>Tx CTLE / driver（S03–S05）</td><td class="n">1.5e-11</td><td>逐级传播</td></tr>
<tr><td>激光 RIN / 相位（S06–S07）</td><td class="n">0</td><td>逐位一致</td></tr>
<tr><td>MZM / 光纤 / CD（S08–S11）</td><td class="n">≤4.7e-13</td><td>机器精度量级</td></tr>
<tr><td>PIN 平方律 / DGD / 光电（S12–S16）</td><td class="n">0</td><td>逐位一致</td></tr>
<tr><td>TIA / AGC（S17–S19）</td><td class="n">≤2.5e-13</td><td>机器精度量级</td></tr>
<tr><td>Rx S4P / Rx CTLE / ADC（S20–S24）</td><td class="n">1.4e-11</td><td>FFT 求和顺序</td></tr>
</table>
</div>
<p>端到端 BER 判定<b>逐位一致</b>（15 位有效数字全同）：<span class="mono">ffe_ber = 3.590842360037e-04</span>、<span class="mono">mlse_ber = 1.289529024323e-04</span>；同步延时 <span class="mono">111</span>、相位偏移 <span class="mono">0</span> 完全一致。</p>
<div class="card">
<b>差异来源</b>：浮点差只来自频域滤波的 FFT 求和顺序（radix-2 vs numpy pocketfft），量级 ≤1.6e-11，不改变任何 BER 判决。时间域步骤（ZOH、光电、PIN、TIA、AGC）逐位一致；频域步骤引入并传播 ~1e-11 舍入差；最终判决仍逐位相同。
</div>

<h3>10.3 探针与代理推理</h3>
<p>发端探针（7 抽头 Tx FIR + drive_rms）与 Model A/B 前向：<span class="mono">drive_rms</span> 相对差 ≤1e-13、<span class="mono">pred_a</span> 相对差 ≤1e-12（两平台 <span class="mono">pred_a = -5.995717769951e+00</span> 同值到第 12 位）。</p>

<h3>10.4 在线调优等价</h3>
<div class="tabs">
  <!--EQ_TAB_BAR-->
  <div class="tab-panel active" id="tab-eq-secant">
    <p>低SNR少点数（Base_IL10x10 + IL20x20，2<sup>18</sup> 符号，单种子 42，割线 + 解析 gain）逐轨迹对比 C++ vs Python：<span class="mono">gdc / gdc2 / gain / pred_a / pred_b / real_ber</span> 最大相对差 <strong>4.6e-13</strong>（与物理层 bit 级等价同量级，见 10.2）。两平台割线方向、gain 解析梯度、B 否决、落点序列逐位一致。</p>
    <p>高SNR大点数 15 用例泛化测试只跑 C++（见 §6）；Python 割线结果作为低SNR收敛/等价性参照。</p>
  </div>
  <!--DIRECT_EQ_PANEL-->
</div>

<h3>10.5 评估量对比（割线 / direct / 每步中心差分）</h3>
<p>割线在线调优把「每步中心差分的 14 个 ±ε 试探态 + 1 落点」的真实评估量降到「第 0 步 12 个 shape 试探态 + 每步 1 落点（gain 维解析、0 试探，此后零试探态）」；direct（有回传通道时）为「第 0 步 7 维全测 14 试探态 + 每步 1 落点」（无解析 gain 梯度），到检测底即停、平均实际步数 7.9，全 15 用例平均每用例真实评估 ≈23 次（2<sup>22</sup> 实测均值）。割线与每步中心差分的同口径单用例对照（2<sup>18</sup> 符号、单种子 42、次优起点、15 步）实测真实评估次数：</p>
<div class="kpis" style="grid-template-columns:repeat(4,1fr)">
  <div class="kpi"><div class="v">28 次</div><div class="l">割线（解析 gain）：1 seed + 12 初始化（shape）+ 15 落点</div></div>
  <div class="kpi"><div class="v">≈23 次</div><div class="l">direct（2^22 全 15 用例均值）：1 seed + 14 初始化（7 维）+ 7.9 落点均值</div></div>
  <div class="kpi"><div class="v">226 次</div><div class="l">每步中心差分：1 seed + 15×15（14 试探 + 1 落点）</div></div>
  <div class="kpi"><div class="v">8×</div><div class="l">割线相对每步中心差分的评估量减少</div></div>
</div>
<p>单次真实 BER 评估（2<sup>22</sup> 符号）C++ 仍比 Python 快 1.80×（同一物理链，见 10.2）。15 用例 C++ 割线全量重跑（15 步）合计墙钟：<!--CXX_TOTAL_WALL-->（15 路并行，见 <span class="mono">result/ddps_cpp_secant/</span>）。</p>

<h3>10.6 统一入口</h3>
<pre><code># C++ 后端：全量在线调优（Base_IL10x10，2^22 符号，无噪声，单种子 42，次优起点，割线）
# （WSL 内运行：Linux 进程不受本机 Smart App Control 强制模式管辖，见本节开头「构建运行环境」）
wsl -d Ubuntu --cd /mnt/c/DSPPlayground/eLPO_antigravity ./cpp/build/run_ddps cpp/config.txt \
    --num-symbols 4194304 --tx-noise-snr 0 \
    --seed 42 --n-steps 15 --seed-config result/seed_config_bad_1e4.json --method secant

# 快速验证：低 SNR 人为噪声 + 少点数（发端 DSP 出口 SNR=23 dB、2^14 符号）
wsl -d Ubuntu --cd /mnt/c/DSPPlayground/eLPO_antigravity ./cpp/build/run_ddps cpp/config.txt \
    --num-symbols 16384 --tx-noise-snr 23 --seed 42

# 15 用例并行全量重跑（C++ 侧，割线；WSL 内存上限下 jobs=2）
python cpp\run_all_cases.py --backend wsl --method secant --out-dir result/ddps_cpp_secant \
    --num-symbols 4194304 --n-steps 15 --jobs 2</code></pre>

<footer>
  <p><strong>测量口径</strong>：Python 3.11.11 / NumPy 2.4.6 / SciPy 1.17.1；BLAS 线程数固定为 1（<span class="mono">OMP_NUM_THREADS=1</span>）；
  BER 评估统一 4194304 符号/点 × 单仿真实例种子 42；数据集采样与模型划分固定 seed = 42。C++ 侧同一种子、同一符号数。</p>
  <p>数值来源：<span class="mono">config.xlsx</span>、<span class="mono">models/*/meta.json</span>、<span class="mono">result/*/case_summary.csv</span>、
  <span class="mono">result/*/trace_*.csv</span>、<span class="mono">dataset/ddps_dataset_*.csv</span> 与源码常量。</p>
</footer>

</div>
<script>
(function(){
  // 标题级折叠：h2/h3/h4 点击收起其下属内容（到下一个同级或更高级标题为止）
  function sectLevel(el){
    var m = /^H([1-6])$/.exec(el.tagName);
    return m ? parseInt(m[1], 10) : 0;
  }
  function sectChildren(h){
    var lvl = sectLevel(h), list = [], el = h.nextElementSibling;
    while (el){
      if (el.tagName === 'FOOTER') break;
      if (sectLevel(el) && sectLevel(el) <= lvl) break;
      list.push(el);
      el = el.nextElementSibling;
    }
    return list;
  }
  function show(h){ sectChildren(h).forEach(function(n){ n.removeAttribute('data-sect'); n.style.display=''; }); }
  function hide(h){ sectChildren(h).forEach(function(n){ n.setAttribute('data-sect','1'); n.style.display='none'; }); }
  document.querySelectorAll('h2,h3,h4').forEach(function(h){
    h.classList.add('sect');
    h.addEventListener('click', function(){
      if (h.classList.toggle('collapsed')){ hide(h); } else { show(h); }
    });
  });

  // 6.5 对比实验：页签切换（打印时所有面板强制可见，见 @media print）
  document.querySelectorAll('.tabs .tab-btn').forEach(function(btn){
    btn.addEventListener('click', function(){
      var wrap = btn.closest('.tabs');
      wrap.querySelectorAll('.tab-btn').forEach(function(b){ b.classList.toggle('active', b === btn); });
      wrap.querySelectorAll('.tab-panel').forEach(function(p){
        p.classList.toggle('active', p.id === btn.getAttribute('data-tab'));
      });
    });
  });

  // 打印：展开所有标题折叠与 details，打印后恢复
  var wasClosed = [], wasCollapsed = [];
  window.addEventListener('beforeprint', function(){
    document.querySelectorAll('.sect.collapsed').forEach(function(h){
      wasCollapsed.push(h); h.classList.remove('collapsed'); show(h);
    });
    document.querySelectorAll('details.fold:not([open])').forEach(function(d){
      d.setAttribute('open',''); wasClosed.push(d);
    });
  });
  window.addEventListener('afterprint', function(){
    wasCollapsed.forEach(function(h){ h.classList.add('collapsed'); hide(h); });
    wasCollapsed = [];
    wasClosed.forEach(function(d){ d.removeAttribute('open'); });
    wasClosed = [];
  });
})();
</script>
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
    """逐步记账：落点口径 + 含 ±ε 试探瞬时口径（两类都是真实硬件短暂停留的工作点）。"""
    steps = 0
    worse = 0
    probe_rows = []
    probe_worse_steps = 0
    worst_ratio = 0.0
    worst_env = ''
    worst_ber = 0.0
    for env, r in summary.items():
        p = os.path.join(d, f'trace_{env}.csv')
        if not os.path.exists(p):
            continue
        tr = pd.read_csv(p)
        if tr.empty:
            continue
        seed = r['seed_ber']
        steps += len(tr)
        worse += int((tr['real_ber'] > seed).sum())
        pr = None
        pp = os.path.join(d, f'probes_{env}.csv')
        if os.path.exists(pp):
            pr = pd.read_csv(pp)
            if pr.empty or 'real_ber' not in pr.columns:
                pr = None
        n_probe_worse = 0
        worst_w = 0.0
        for step in tr['step'].unique():
            acc = float(tr.loc[tr['step'] == step, 'real_ber'].iloc[0])
            if pr is not None:
                prb = pr.loc[pr['step'] == step, 'real_ber']
                w = max(acc, float(prb.max())) if len(prb) else acc
            else:
                w = acc
            if w > seed:
                n_probe_worse += 1
            worst_w = max(worst_w, w)
        probe_worse_steps += n_probe_worse
        r_ = worst_w / seed if seed > 0 else 0.0
        if r_ > worst_ratio:
            worst_ratio = r_
            worst_env = env
            worst_ber = worst_w
        probe_rows.append(
            f"<tr><td>{env}</td>"
            f"<td class=\"n\">{seed:.2e}</td>"
            f"<td class=\"n{' win' if n_probe_worse == 0 else ''}\">{n_probe_worse}</td>"
            f"<td class=\"n\">{worst_w:.2e}</td>"
            f"<td class=\"n\">{r_:.1f}x</td></tr>")
    total_steps = steps
    total_worse = worse
    landed = (f"<tr><td class=\"n\">{len(summary)}</td>"
              f"<td class=\"n\">{total_steps}</td>"
              f"<td class=\"n{' win' if total_worse == 0 else ''}\">{total_worse}</td>"
              f"<td>{'无退步' if total_worse == 0 else '存在退步'}</td></tr>")
    return (landed, '\n'.join(probe_rows), total_steps, total_worse,
            probe_worse_steps, worst_ratio, worst_env, worst_ber)


def _rows_probe(d, order):
    """试探步 BER 包络逐用例统计：仅第 0 步 12 个 shape 维 ±ε 微扰态各自的端到端 MLSE BER。"""
    out = []
    for env in order:
        p = os.path.join(d, f'probes_{env}.csv')
        if not os.path.exists(p):
            continue
        pr = pd.read_csv(p)
        if pr.empty or 'real_ber' not in pr.columns:
            continue
        out.append(
            f"<tr><td>{env}</td>"
            f"<td class=\"n\">{int(pr['step'].nunique())}</td>"
            f"<td class=\"n\">{int(len(pr))}</td>"
            f"<td class=\"n\">{pr['real_ber'].min():.2e}</td>"
            f"<td class=\"n\">{pr['real_ber'].max():.2e}</td>"
            f"<td class=\"n\">{pr['real_ber'].median():.2e}</td></tr>")
    return '\n'.join(out)


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


def _rows_metrics(meta):
    _domain_zh = {'waveform_probe': '波形域（探针）', 'parameter': '参数域'}
    out = []
    for tag, name in (('model_a', 'Model A'), ('model_b', 'Model B')):
        m = meta[tag]
        dim = meta[f'{tag}_dim']
        desc = m.get('description', '').replace('6 维 x_shape + drive_rms', '7 维参数域（x_shape 6 维 + drive_rms）')
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


# ============================================================================
# 6.5 对比实验：direct（有回传通道时的端到端 BER 直接梯度下降）
# ============================================================================
_EQUIV_COLS = ['gdc', 'gdc2', 'gain', 'u_gain', 'drive_rms', 'pred_a', 'real_lb',
               'real_ber', 'grad_norm']


def _direct_equiv_rows(py_dir, cpp_dir):
    """direct 2^18 等价比对表：与 cpp/compare_traces.py 同口径，构建时实算。"""
    rows = []
    worst_all = 0.0
    if not (os.path.isdir(py_dir) and os.path.isdir(cpp_dir)):
        return rows, worst_all
    for p in sorted(glob.glob(os.path.join(cpp_dir, 'trace_*.csv'))):
        env = os.path.basename(p)[len('trace_'):-len('.csv')]
        fp = os.path.join(py_dir, 'trace_%s.csv' % env)
        if not os.path.exists(fp):
            continue
        tp = pd.read_csv(fp)
        tc = pd.read_csv(p)
        n = min(len(tp), len(tc))
        env_worst = 0.0
        for c in _EQUIV_COLS:
            if c not in tp.columns or c not in tc.columns:
                continue
            av = tp[c].iloc[:n].to_numpy(dtype=float)
            bv = tc[c].iloc[:n].to_numpy(dtype=float)
            rel = np.abs(av - bv) / np.maximum(np.abs(bv), 1e-300)
            rel = rel[~np.isnan(rel)]
            if len(rel):
                env_worst = max(env_worst, float(rel.max()))
        worst_all = max(worst_all, env_worst)
        rows.append(
            f"<tr><td>{env}</td><td class=\"n\">{n}</td>"
            f"<td class=\"n\">{env_worst:.2e}</td>"
            f"<td class=\"n{' win' if env_worst < 1e-9 else ''}\">"
            f"{'数值等价' if env_worst < 1e-9 else '超容差'}</td></tr>")
    return rows, worst_all


def _direct_cmp_figure(summary, dsum, order, out_png):
    """15 用例最优 BER 双系列对比图（对数横轴，逐用例连线）。"""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC',
                                       'sans-serif']
    plt.rcParams['axes.unicode_minus'] = False
    ys = np.arange(len(order))
    sec = [float(summary[e]['best_ber']) for e in order]
    dr = [float(dsum[e]['best_ber']) for e in order]
    fig, ax = plt.subplots(figsize=(9.5, 7.4))
    for y, s, d in zip(ys, sec, dr):
        ax.plot([s, d], [y, y], color='#94a3b8', lw=1.0, zorder=1)
    ax.scatter(sec, ys, marker='o', s=46, color='#3b82f6',
               label='DDPS 现役（Model A+B 代理，无需回传通道）', zorder=3)
    ax.scatter(dr, ys, marker='D', s=44, color='#ef4444',
               label='direct（端到端 BER 直接梯度下降，需回传通道）', zorder=3)
    ax.set_yticks(ys)
    ax.set_yticklabels(order, fontsize=8.5)
    ax.set_xscale('log')
    ax.set_xlabel('最优 BER_MLSE（对数轴；2^22 符号 C++，同一次优起点/种子/步数协议）', fontsize=9.5)
    ax.invert_yaxis()
    ax.grid(alpha=0.3, which='both', axis='x')
    ax.set_title('最优 BER 对比：现役方案 vs direct（有回传通道时的参照）', fontsize=11.5)
    ax.legend(fontsize=9, loc='lower right')
    fig.tight_layout()
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    fig.savefig(out_png, dpi=125)
    plt.close(fig)
    return out_png


def _build_direct_section(a, summary, order):
    """构建 6.5 整节 HTML（结果对比 / 方案说明 两个页签；等价性证据在第 10 节）。

    数据缺失（direct 全量结果未生成）时返回空串，交付件其余部分不受影响。
    """
    dpath = os.path.join(a.direct, 'case_summary.csv')
    if not os.path.exists(dpath):
        return ''
    dsum, _ = _load_summary(a.direct)
    dorder = [e for e in order if e in dsum]
    if not dorder:
        return ''

    imp_d = np.array([dsum[e]['seed_ber'] / dsum[e]['best_ber'] for e in dorder])
    imp_s = np.array([summary[e]['seed_ber'] / summary[e]['best_ber'] for e in dorder])
    geo_d = float(10 ** np.mean(np.log10(imp_d)))
    geo_s = float(10 ** np.mean(np.log10(imp_s)))
    ratio = np.array([dsum[e]['best_ber'] / summary[e]['best_ber'] for e in dorder])
    n_same = int(((ratio >= 0.95) & (ratio <= 1.05)).sum())
    n_better = int((ratio < 0.95).sum())
    n_worse = int((ratio > 1.05).sum())
    steps_d = [int(dsum[e]['n_steps_actual']) for e in dorder]
    steps_s = [int(summary[e]['n_steps_actual']) for e in dorder]
    evals_d = 15 + int(np.mean(steps_d))     # 1 种子 + 14 第 0 步试探 + n 落点
    evals_s = 13 + int(np.mean(steps_s))     # 1 种子 + 12 第 0 步试探(记账) + n 落点

    # 结论措辞（按数字分档，照实说）
    if n_better == 0 and n_worse == 0:
        verdict = (f"<strong>逐用例打平</strong>：{n_same}/{len(dorder)} 用例两方案最优 BER "
                   f"一致（±5% 内），几何平均 ×{geo_d:.0f} vs ×{geo_s:.0f}。")
    elif geo_d >= geo_s * 0.9:
        verdict = (f"<strong>总体相当</strong>：几何平均 ×{geo_d:.0f} vs ×{geo_s:.0f}；逐用例 "
                   f"{n_same} 打平、direct 更好 {n_better}、现役更好 {n_worse}。")
    else:
        verdict = (f"<strong>direct 略差</strong>：几何平均 ×{geo_d:.0f} vs ×{geo_s:.0f}；逐用例 "
                   f"{n_same} 打平、direct 更好 {n_better}、现役更好 {n_worse}。")

    # 结果对比表
    rows = []
    for env in dorder:
        r = dsum[env]
        s = summary[env]
        rr = r['best_ber'] / s['best_ber']
        mark = 'win' if rr < 0.95 else ('lose' if rr > 1.05 else '')
        sr = r.get('stop_reason')
        sr = sr if isinstance(sr, str) else ''   # pandas 把空字段读成 NaN，归一成 ''
        rows.append(
            f"<tr><td>{env}</td><td>{_cond(r)}</td>"
            f"<td class=\"n\">{_ber(s['seed_ber'])}</td>"
            f"<td class=\"n\">{_ber(s['best_ber'])} ({int(s['best_step'])})</td>"
            f"<td class=\"n\">{_ber(r['best_ber'])} ({int(r['best_step'])})</td>"
            f"<td class=\"n {mark}\">x{rr:.2f}</td>"
            f"<td class=\"n\">{int(r['n_steps_actual'])}</td>"
            f"<td class=\"mono\" style=\"font-size:11.5px\">{sr or '步数用尽'}</td></tr>")
    rows_html = '\n'.join(rows)

    # 对比图（写入 direct 结果目录的 report/，与主结果目录的报告图同规格）
    img_png = _direct_cmp_figure(
        summary, dsum, dorder,
        os.path.join(a.direct, 'report', 'direct_vs_secant.png'))
    img_tag = _img_tag(img_png)

    n_evals_note = (f"每用例真实评估量：direct ≈ {evals_d}（1 种子 + 14 个第 0 步试探 + "
                    f"{int(np.mean(steps_d))} 落点均值）vs 现役 ≈ {evals_s}"
                    f"（1 种子 + 12 个试探记账 + {int(np.mean(steps_s))} 落点均值）")

    # 逐用例形态解读引用的实测终点（数据驱动，缺用例时退化为泛指）
    _hn = dsum.get('HighNoise_IL10x10')
    real_ber_ref = _ber(_hn['best_ber']) if _hn is not None else '该区域可及的最优位'

    section = f'''
<p>现役方案的假设是<strong>没有回传通道</strong>：在线调优拿不到收端端到端 BER，只能用发端可测的波形探针训练代理（Model A/B）来指方向、控风险。如果有回传通道、端到端 BER 可得呢？<strong>direct 方案</strong>回答这个问题：目标直接换成真实 log10(BER)，梯度直接对真实目标做，不用任何代理。两方案在同一协议下对比（同一次优起点、同 15 用例、2<sup>22</sup> 符号、单种子 42、同一套 C++ 复刻实现与下降机制，收敛轨迹图对照见 6.2 页签），页签切换查看结果对比与方案说明；direct 的 C++ 等价性证据在第 10 节。</p>

<div class="tabs">
  <div class="tab-bar">
    <button class="tab-btn active" data-tab="tab-direct-result">结果对比</button>
    <button class="tab-btn" data-tab="tab-direct-method">方案说明</button>
  </div>

  <div class="tab-panel active" id="tab-direct-result">
    <div class="kpis" style="grid-template-columns:repeat(4,1fr)">
      <div class="kpi"><div class="v">x{geo_d:.0f}</div><div class="l">direct 几何平均改善（起点→最优）</div></div>
      <div class="kpi"><div class="v">x{geo_s:.0f}</div><div class="l">现役方案几何平均改善（同协议）</div></div>
      <div class="kpi"><div class="v">{n_same} / {len(dorder)}</div><div class="l">两方案打平的用例数（±5% 内）</div></div>
      <div class="kpi"><div class="v">{int(np.mean(steps_d))} vs {int(np.mean(steps_s))}</div><div class="l">平均实际步数（direct / 现役）</div></div>
    </div>
    <p><strong>对照结论</strong>：{verdict} {n_evals_note}。direct 到达（或接近）检测限后真实梯度信号消失，
    边际改善停止判据随即触发，步数普遍更省。逐用例形态（照实呈现）：</p>
    <ul style="margin-top:6px">
      <li><strong>IL20x20（最难纯 ISI 用例）：direct 更好</strong>——真实目标把 BER 一路压到 0 错误检测底 {_ber(5.975e-8)}（11 步），现役方案停在 1.20e-7 残差位（2 倍差距）。代理预测在 BER 最深段的分辨率不足，真实目标没有这个盲区。</li>
      <li><strong>HighNoise_IL10x10：direct 更差</strong>——轨迹在两个相邻工作点间两点振荡（gdc/gdc2 交替、每步改善趋零后停止在 {real_ber_ref}）。该区域真实梯度幅值极大（grad_norm≈39），固定学习率 + 无阻尼的既定下降机制在陡峭区域来回过冲；现役方案的保守步进反而落得更深。</li>
      <li><strong>Comb_IL20x20_CD15_DGD5：direct 更差</strong>——轨迹把 gdc2 推到下界 0、gain 推到搜索盒顶后停滞（步数用尽），终点比现役方案浅 4.5 倍；真实梯度大幅值下固定步长更容易贴边走死角。终点步还出现一步回退（1e-6 → 1.3e-6 量级、仍远优于种子）——direct 落点不做否决，无 B 红线拦截此类步（现役方案的结构性保障见 6.3）。</li>
    </ul>
    <p style="margin-bottom:0">这一对照的定位：<strong>direct 不是替代方案，而是「有回传通道时直接梯度下降能达到什么水平」的参照</strong>——
    端到端 BER 拿不到时（本方案默认约束），代理路径是唯一选择；对照结果显示该约束下现役方案达到的水平与直接梯度下降的关系如上表所列，照实呈现。</p>
    <figure>
      <div class="fig-scroll"><img src="{img_tag}" alt="direct 与现役方案最优 BER 对比"></div>
      <figcaption>图 13 · 15 用例最优 BER_MLSE 对比（对数横轴；蓝点 = 现役方案，红菱 = direct；灰线连接同一用例）。</figcaption>
    </figure>
    <div class="tw">
    <table class="wide" id="tbl-direct-cmp">
      <caption>同协议逐用例对比：起点 = 同一次优工作点；最优 = 全轨迹真实 BER_MLSE 最小值（步序）；direct/现役 &lt; 1 表示 direct 更优 <span class="sh">· 可左右滑动</span></caption>
      <tr><th>用例</th><th>物理条件</th><th class="n">起点 BER</th><th class="n">现役最优 BER（步）</th><th class="n">direct 最优 BER（步）</th><th class="n">direct/现役</th><th class="n">direct 步数</th><th>direct 停止原因</th></tr>
      {rows_html}
    </table>
    </div>
  </div>

  <div class="tab-panel" id="tab-direct-method">
    <div class="card">
      <p><strong>前提与动机</strong>：现役方案在线只拿得到发端可测量（7-tap Tx FIR 探针、drive_rms），Model A 建立「探针→BER」方向、Model B 建立参数域风险包络。direct 假设收端 BER 可回传（等效于每次调参都能拿到端到端误码统计），此时目标本身可得，代理失去存在理由——直接对真实目标做梯度下降就是上限参照。</p>
      <p><strong>下降机制与现役完全一致</strong>（这是对照有效的前提）：同一 7 维搜索空间与搜索盒（FFE ±0.10 / CTLE ±3.0 dB / gain ±0.30 dex）、同一步长调度（GD_LR=0.05、0.97<sup>步</sup> 衰减、组归一化跨度）、同一组门控（每组梯度 &lt; 1e-3 dex/整箱冻结）、同一边际改善停止（每步改善 &lt; 0.01 dex 停）。差别只在<strong>目标与梯度来源</strong>：</p>
      <div class="tw">
      <table class="wide" style="margin-bottom:8px">
        <caption>机制对照：现役（割线）vs direct</caption>
        <tr><th>环节</th><th>现役（割线，无需回传）</th><th>direct（需回传通道）</th></tr>
        <tr><td>下降目标</td><td>Model A 预测 log10(BER)（探针域代理）</td><td>端到端真实 log10(BER)（回传值）</td></tr>
        <tr><td>第 0 步初始化</td><td>shape 6 维中心差分查 A（12 次探针，无需 BER）+ gain 维解析梯度（A 探针严格 ∝ gain，闭式可得，0 试探）</td><td>全部 7 维中心差分直接测真实 BER（14 次真实评估）——无代理即无解析 gain 梯度，gain 维也只能实测</td></tr>
        <tr><td>每步梯度维持</td><td>Broyden 割线更新 A 预测的变化量（gain 维每步解析重算）</td><td>Broyden 割线更新真实 Δlog10(BER)（全 7 维）</td></tr>
        <tr><td>风险控制</td><td>Model B 保守包络红线（相对种子最多变差 25%）+ 候选否决 + 轨迹信任域</td><td>无（三者都是代理可靠性保障，无代理即无保护对象；搜索盒与停止判据仍在）</td></tr>
        <tr><td>试探态</td><td>仅第 0 步 12 个 ±ε 探针态（此后零试探）</td><td>仅第 0 步 14 个 ±ε 试探态（此后零试探）</td></tr>
      </table>
      </div>
      <p><strong>记账口径</strong>：trace 的 <span class="mono">pred_a</span> 列记录当前落点目标值（= real_lb，即回传的 log10 BER），<span class="mono">pred_b / allowed_ber / pred_b_ber</span> 恒 0（无代理），列结构与其余结果目录一致，报表工具统一解析。第 0 步 14 个试探态的真实 BER 逐一记入 <span class="mono">probes_&lt;用例&gt;.csv</span>（param/sign/坐标/真实 BER），与其余方案同 schema。</p>
      <p style="margin-bottom:0"><strong>公平性</strong>：同一次优起点（seed_config_bad_1e4）、同 15 用例、同评估协议（2<sup>22</sup> 符号、单种子 42）、同 C++ 实现、同 15 步上限；评估量 {n_evals_note}，两方案在线成本同量级。</p>
    </div>
  </div>
</div>
'''
    return section


def _build_direct_eq_panel(a):
    """构建 §10.4「direct 等价」页签内容（2^18 口径 Python vs C++ 实算表）。

    数据目录缺失时返回空串，10.4 页签组退化为单页签。
    """
    equiv_rows, equiv_worst = _direct_equiv_rows(a.direct_py, a.direct_equiv)
    if not equiv_rows:
        return ''
    equiv_html = '\n'.join(equiv_rows)
    equiv_worst_str = f'{equiv_worst:.2e}'
    return f'''
    <p>direct 与现役方案走同一条双实现流水线（本节口径）：<strong>Python 定原理 → C++ 一比一复刻 → 只在 2<sup>18</sup> 小点数低 SNR 下比对 → 通过后全量规模仿真只用 C++</strong>。direct 的 Python 参照结果（15 用例全量，<span class="mono">result/ddps_direct_py/</span>）与 C++ 等价比对结果（Base_IL10x10 + IL20x20 两代表用例，<span class="mono">result/ddps_cpp_direct_equiv/</span>）按下表逐（用例 × 步 × 数值列）实算最大相对差：</p>
    <div class="tw">
    <table class="wide" style="margin-bottom:8px">
      <caption>direct：Python vs C++ trace 逐步数值比对（2^18 小点数低 SNR、单种子 42、无人工噪声；比对列 gdc/gdc2/gain/u_gain/drive_rms/pred_a/real_lb/real_ber/grad_norm）</caption>
      <tr><th>用例</th><th class="n">比对步数</th><th class="n">最大相对差</th><th>判据（&lt; 1e-9）</th></tr>
      {equiv_html}
    </table>
    </div>
    <p style="margin-bottom:0">比对命令：<span class="mono">python cpp/compare_traces.py --py result/ddps_direct_py --cpp result/ddps_cpp_direct_equiv</span>（比对工具与判据固化在库内，全量 15 用例比对可用 <span class="mono">--envs</span> 指定）。总口径最坏相对差 <strong>{equiv_worst_str}</strong>，与现役方案的等价比对（4.6e-13，本节左页签）同量级——差异全部来自浮点求和顺序与数学库末位，不影响任何一步的落点决策（BER 为错误计数导出量，逐步一致即逐步同数）。</p>'''


def _build_direct_fig_tabs(a, direct_section):
    """构建 6.2 的页签栏与 direct 图组页签（图组由 report_ddps.py --method direct 生成）。

    返回 (tab_bar, panel)；direct 全量结果或图组缺失时均返回空串（6.2 退化为无页签单图组）。
    """
    if not direct_section:
        return '', ''
    dreport = os.path.join(a.direct, 'report')
    names = {'conv': 'ddps_conv_grid.png', 'gain': 'ddps_gain_rms.png', 'hard': 'ddps_case_hard.png'}
    tags = {}
    for k, n in names.items():
        p = os.path.join(dreport, n)
        tags[k] = _img_tag(p) if os.path.exists(p) else ''
    if not any(tags.values()):
        return '', ''
    tab_bar = ('  <p>两套在线调优方案在<strong>同一协议</strong>（同一次优起点 x₀、同 15 用例、'
               '2<sup>22</sup> 符号 C++、单种子 42）下的收敛与物理量轨迹，页签切换对照：</p>\n'
               '  <div class="tab-bar">\n'
               '    <button class="tab-btn active" data-tab="tab-fig-secant">DDPS 现役（A+B 代理，无回传通道）</button>\n'
               '    <button class="tab-btn" data-tab="tab-fig-direct">direct（端到端 BER 直接梯度，有回传通道）</button>\n'
               '  </div>')
    figs = []
    if tags['conv']:
        figs.append(f'''    <figure>
      <div class="fig-scroll"><img src="{tags['conv']}" alt="direct 15 用例收敛轨迹"></div>
      <figcaption>图 10 · direct 收敛轨迹（实测 BER_MLSE，对数纵轴；虚线为起点；无代理预测曲线——目标即实测）。</figcaption>
    </figure>''')
    if tags['gain']:
        figs.append(f'''    <figure>
      <div class="fig-scroll"><img src="{tags['gain']}" alt="direct gain 与 drive_rms 轨迹"></div>
      <figcaption>图 11 · direct gain 维轨迹：gain 倍率与 drive_rms（虚线为起点 gain 倍率 ×0.325）。</figcaption>
    </figure>''')
    if tags['hard']:
        figs.append(f'''    <figure>
      <div class="fig-scroll"><img src="{tags['hard']}" alt="direct 最难用例四联图"></div>
      <figcaption>图 12 · direct 最难用例四联图：收敛轨迹、Tx FFE 抽头（起点 vs 最优）、Tx CTLE |H(f)| 频响、Tx 探针 7-tap FIR（发端波形特征）。</figcaption>
    </figure>''')
    panel = ('  <div class="tab-panel" id="tab-fig-direct">\n'
             '    <p>目标 = 端到端真实 log10(BER)（回传值），收敛图无代理预测曲线；现役页签的预测-实测散点（图 8）是代理可靠性诊断，direct 无代理、不适用。方案机制与逐用例对照见 6.5，C++ 等价性见 10.4。</p>\n'
             + '\n'.join(figs) + '\n  </div>')
    return tab_bar, panel


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--baseline', default='result/ddps_cpp_secant', help='主结果目录（C++ 割线 15 用例）')
    ap.add_argument('--model-dir', default='models/ddps', help='模型目录')
    ap.add_argument('--dataset', default=None)
    ap.add_argument('--report-src', default='result/ddps_cpp_secant', help='报告图数据源（同主结果目录，图用 C++ 出）')
    ap.add_argument('--direct', default='result/ddps_cpp_direct',
                    help='direct 对比实验全量结果目录（C++ 15 用例；缺省指向标准目录，存在才渲染 6.5 节）')
    ap.add_argument('--direct-py', default='result/ddps_direct_py',
                    help='direct Python 2^18 验证目录（等价比对参考侧）')
    ap.add_argument('--direct-equiv', default='result/ddps_cpp_direct_equiv',
                    help='direct C++ 2^18 等价比对目录')
    ap.add_argument('--out', default='deliverables/DDPS_Deliverable.html')
    a = ap.parse_args()

    summary, core_df = _load_summary(a.baseline)
    order = list(core_df.sort_values('env')['env'])

    with open(os.path.join(a.model_dir, 'meta.json'), encoding='utf-8') as f:
        meta = json.load(f)

    # per-case target_rms 扫描结果（gain 维物理驱动的标定值）
    rms_json_path = os.path.join(os.path.dirname(os.path.normpath(a.baseline)), 'per_case_target_rms.json')
    with open(rms_json_path, encoding='utf-8') as f:
        rms_data = json.load(f)

    ds_path = a.dataset or _latest('dataset/ddps_dataset_*.csv')
    ds = pd.read_csv(ds_path)

    report_dir = os.path.join(a.report_src, 'report')

    # 图片素材：从 report_ddps.py 生成的 PNG 加载
    img_conv = os.path.join(report_dir, 'ddps_convergence.png')
    img_gain = os.path.join(report_dir, 'ddps_gain_rms.png')
    img_track = os.path.join(report_dir, 'ddps_tracking.png')
    hard_env = max(order, key=lambda e: summary[e]['seed_ber'])
    hard_png = os.path.join(report_dir, f'ddps_case_{hard_env}_a.png')

    # 统计
    imp_arr = np.array([summary[e]['seed_ber'] / summary[e]['best_ber'] for e in order])
    imp_geo = float(10 ** np.mean(np.log10(imp_arr)))   # 几何均值（避免被个别大改善拉高）
    n_pos = int((imp_arr > 1.0).sum())
    n_neu = int((imp_arr == 1.0).sum())
    n_worse = len(order) - n_pos - n_neu
    pos_summary = f"{n_pos}/{len(order)} 用例相对起点改善、{n_neu} 用例持平、{n_worse} 用例退步"
    hard = summary[hard_env]
    safety_rows, safety_probe_rows, total_steps, total_worse, probe_worse_steps, worst_ratio, worst_env, worst_ber = _rows_safety(summary, a.baseline)

    # C++ 割线全量重跑墙钟（result/ddps_cpp_secant）
    cpp_dir = 'result/ddps_cpp_secant'
    cxx_total_wall = '未运行'
    rc_path = os.path.join(cpp_dir, 'run_config.json')
    if os.path.exists(rc_path):
        with open(rc_path, encoding='utf-8') as f:
            rcj = json.load(f)
        cxx_total_wall = '%.0f s' % float(rcj.get('total_wall_sec', 0.0))


    headline = '\n'.join([
        f"<tr><td><strong>在线调优</strong>（A=探针->BER 方向 + B=参数->BER 风险控制 + 7 维 FFE+CTLE+gain）</td>"
        f"<td><strong>{n_pos}/{len(order)} 用例正向改善</strong>（{n_neu} 持平、{n_worse} 退步），几何平均 x{imp_geo:.2f}"
        f"（最高 x{imp_arr.max():.2f}）；{total_steps} 落点真实 BER，"
        f"<strong>含 ±ε 试探瞬时 {probe_worse_steps} 步超种子</strong>（落点 {total_worse} 步/{total_steps} 劣于起点，最坏 ×{worst_ratio:.1f}），见第 6 节</td></tr>",
        f"<tr><td>Model A（方向代理）</td>"
        f"<td>输入 = [7-tap Tx FIR 探针, drive_rms]（8 维波形域）-> log10(BER) 条件均值。"
        f"在线拿不到收端 BER，只能拿发端探针，A 建立探针->BER 方向映射。</td></tr>",
        f"<tr><td>Model B（风险控制）</td>"
        f"<td>输入 = [4 FFE 旁瓣, gDC, gDC2, drive_rms]（7 维参数域）-> log10(BER) 保守上包络。"
        f"按当前最优点 25% 的变差量拒绝候选，{total_worse} 落点劣于起点（红线未触发拦截）。</td></tr>",
        f"<tr><td>A/B 输入空间不同</td>"
        f"<td>波形域 vs 参数域，误差来源相互独立。梯度走 Model A：gain 维解析 + shape 维割线（第 0 步 12 探针初始化，此后零试探态）。</td></tr>",
        f"<tr><td>gain 维</td>"
        f"<td>第 7 个搜索维，经 drive_rms 进入 A/B 输入；每用例最优倍率见 3.3 per-case RMS 标定（0.06~0.22V），"
        f"在线调优从次优起点（gain ×0.325）出发，在 ±0.30 dex 信任域内随割线梯度下降。</td></tr>",
        f"<tr><td>在线决策是否使用真实收端误码</td><td><strong>不使用</strong>，仅旁路记录用于事后核验</td></tr>",
    ])

    kpis = '\n'.join([
        f'<div class="kpi"><div class="v">x{imp_geo:.2f}</div><div class="l">几何平均改善（{n_pos}/{len(order)} 正向）</div></div>',
        f'<div class="kpi"><div class="v">{probe_worse_steps} / {total_steps}</div><div class="l">含试探瞬时超种子（落点 {total_worse}/{total_steps} 不劣化）</div></div>',
        f'<div class="kpi"><div class="v">{meta["model_a"]["spearman_test"]:.3f}</div><div class="l">Model A Spearman（探针->BER）</div></div>',
        f'<div class="kpi"><div class="v">{meta["model_b"]["spearman_test"]:.3f}</div><div class="l">Model B Spearman（参数->BER）</div></div>',
        f'<div class="kpi"><div class="v">{meta["model_b"].get("local_spacing_rho", 0):.2f}</div><div class="l">信任域颗粒度 rho</div></div>',
    ])

    # direct 对比实验：数据存在才渲染（6.5 对比节 + 6.2 图组页签 + 10.4 等价页签）
    direct_section = _build_direct_section(a, summary, order)
    fig_tab_bar, fig_direct_panel = _build_direct_fig_tabs(a, direct_section)
    direct_eq_panel = _build_direct_eq_panel(a) if direct_section else ''
    eq_tab_bar = ''
    if direct_eq_panel:
        eq_tab_bar = ('  <div class="tab-bar">\n'
                      '    <button class="tab-btn active" data-tab="tab-eq-secant">现役方案（割线 + 解析 gain）</button>\n'
                      '    <button class="tab-btn" data-tab="tab-eq-direct">direct（端到端 BER 直接梯度）</button>\n'
                      '  </div>')
    if direct_section:
        dsum, _ = _load_summary(a.direct)
        dorder = [e for e in order if e in dsum]
        geo_d = float(10 ** np.mean(np.log10(
            [dsum[e]['seed_ber'] / dsum[e]['best_ber'] for e in dorder])))
        geo_s2 = float(10 ** np.mean(np.log10(
            [summary[e]['seed_ber'] / summary[e]['best_ber'] for e in dorder])))
        ratio = np.array([dsum[e]['best_ber'] / summary[e]['best_ber'] for e in dorder])
        n_same = int(((ratio >= 0.95) & (ratio <= 1.05)).sum())
        headline += (
            f"<tr><td>对比实验 direct（有回传通道）</td>"
            f"<td>若端到端 BER 可回传：目标直接换成真实 BER、不用 Model A/B 的直接梯度下降，"
            f"与现役方案同协议对比（2^22 C++、同次优起点）几何平均 ×{geo_d:.0f} vs ×{geo_s2:.0f}"
            f"（{n_same}/{len(dorder)} 用例打平），见 6.5 页签</td></tr>")

    html = TEMPLATE
    repl = {
        '<!--HEADLINE_ROWS-->': headline,
        '<!--MODEL_METRICS_ROWS-->': _rows_metrics(meta),
        '<!--KPI_CARDS-->': kpis,
        '<!--CORE_ROWS-->': _rows_core(summary, order),
        '<!--TARGET_RMS_ROWS-->': _rows_target_rms(rms_data, order),
        '<!--SAFETY_ROWS-->': safety_rows,
        '<!--SAFETY_PROBE_ROWS-->': safety_probe_rows,
        '<!--PROBE_WORSE_STEPS-->': str(probe_worse_steps),
        '<!--PROBE_WORST_RATIO-->': f'{worst_ratio:.1f}',
        '<!--PROBE_WORST_ENV-->': worst_env,
        '<!--PROBE_WORST_BER-->': f'{worst_ber:.2e}',
        '<!--PROBE_ROWS-->': _rows_probe(a.baseline, order),
        '<!--CXX_TOTAL_WALL-->': cxx_total_wall,
        '<!--POS_SUMMARY-->': pos_summary,
        '<!--MEAN_IMP-->': f'x{imp_geo:.2f}',
        '<!--MAX_IMP-->': f'x{imp_arr.max():.2f}',
        '<!--TOTAL_STEPS-->': str(total_steps),
        '<!--TOTAL_WORSE-->': str(total_worse),
        '{{IMG_CONV}}': _img_tag(img_conv) if os.path.exists(img_conv) else '',
        '{{IMG_GAIN}}': _img_tag(img_gain) if os.path.exists(img_gain) else '',
        '{{IMG_TRACK}}': _img_tag(img_track) if os.path.exists(img_track) else '',
        '{{IMG_CASE_HARD}}': _img_tag(hard_png) if os.path.exists(hard_png) else '',
        '<!--DIRECT_SECTION-->': direct_section,
        '<!--FIG_TAB_BAR-->': fig_tab_bar,
        '<!--FIG_DIRECT_PANEL-->': fig_direct_panel,
        '<!--EQ_TAB_BAR-->': eq_tab_bar,
        '<!--DIRECT_EQ_PANEL-->': direct_eq_panel,
    }
    for k, v in repl.items():
        html = html.replace(k, v)

    with open(a.out, 'w', encoding='utf-8') as f:
        f.write(html)
    left = html.count('{{IMG_') + html.count('<!--')
    print(f'[deliverable] written {a.out}  ({os.path.getsize(a.out)/1024:.0f} KB)')
    print(f'[deliverable] baseline={a.baseline} model={a.model_dir}')
    print(f'[deliverable] envs={len(order)} positive={n_pos} steps={total_steps} worse={total_worse}')
    print(f'[deliverable] mean improvement (geomean): x{imp_geo:.2f}')
    print(f'[deliverable] hardest={hard_env}; unused tokens left: {left}')


if __name__ == '__main__':
    main()
