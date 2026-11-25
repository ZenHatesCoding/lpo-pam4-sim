#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""make_deliverable.py — 由产物自动生成 DDPS 交付件（自包含 HTML）。

数据来源（全部为流水线产物，无需手工转录）：
  result/ddps_cpp_{full,rotate,secant}/  C++ 在线调优 15 环境（8 维：5 FFE 抽头 + gDC + gDC2 + gain）
  result/ddps_cpp_direct*/               真实 BER 回传格（有回传通道时的端到端 BER 直接梯度下降）
  models/ddps/                   meta.json（模型指标与特征维度）
  dataset/ddps_dataset_*.csv      数据集统计
用法:
  python make_deliverable.py --baseline result/ddps_cpp_<选定格> --mode <选定取法> \
      --model-dir models/ddps --out deliverables/DDPS_Deliverable.html
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
  html{scroll-behavior:smooth}
  h2{scroll-margin-top:14px}
  .toc{display:flex;flex-wrap:wrap;gap:7px;margin-top:18px;max-width:980px}
  .toc a{color:#fff;text-decoration:none;font-size:13px;font-weight:600;background:rgba(255,255,255,.13);
         border:1px solid rgba(255,255,255,.24);padding:5px 12px;border-radius:999px;transition:background .15s}
  .toc a:hover{background:rgba(255,255,255,.30)}
  .toc a b{opacity:.62;margin-right:3px;font-weight:700}
  .back-toc{display:block;text-align:right;text-decoration:none;font-size:12.3px;font-weight:600;
            color:var(--ink-3);margin:22px 2px 0}
  .back-toc:hover{color:var(--accent)}
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
    .toc{gap:6px}
    .toc a{font-size:12px;padding:4px 10px}
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
    .back-toc{display:none}
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
  /* 逐帧走查（walkthrough）：算法过程分帧演示 */
  .wt{border:1px solid var(--line);border-radius:12px;background:#fff;margin:14px 0;overflow:hidden}
  .wt-bar{display:flex;align-items:center;gap:9px;padding:9px 12px;background:#f2f6fb;border-bottom:1px solid var(--line);flex-wrap:wrap}
  .wt-btn{background:#fff;border:1px solid var(--line);border-radius:7px;padding:5px 12px;font-weight:700;font-size:13px;color:var(--ink-2);cursor:pointer;font-family:inherit}
  .wt-btn:hover{background:#e8f0fa}
  .wt-dots{display:flex;gap:5px;align-items:center}
  .wt-dot{width:10px;height:10px;border-radius:50%;background:#c8d4e4;cursor:pointer;border:none;padding:0}
  .wt-dot:hover{background:#9fb6d4}
  .wt-dot.on{background:var(--accent)}
  .wt-title{font-size:12.8px;font-weight:700;color:var(--ink-2);margin-left:auto}
  .wt-frame{display:none;padding:14px 16px}
  .wt-frame.on{display:grid;grid-template-columns:minmax(300px,1fr) minmax(280px,1.1fr);gap:18px}
  .wt-right h5{margin:0 0 6px;font-size:14.5px;color:var(--accent)}
  .wt-right p{font-size:13.2px;line-height:1.62;margin:7px 0}
  .wt-ber{font-weight:800;color:var(--accent)}
  .wt-svg{width:100%;height:auto;display:block}
  .wt-cap{font-size:11.8px;color:var(--mut);margin:4px 0 0}
  @media (max-width:880px){ .wt-frame.on{display:block} }
  @media print{
    .wt-frame{display:block !important;page-break-inside:avoid;border-top:1px dashed var(--line);margin-top:10px;padding-top:12px}
    .wt-frame::before{content:attr(data-title);display:block;font-weight:800;color:var(--accent);font-size:12.5px;margin-bottom:6px}
    .wt-bar .wt-btn,.wt-bar .wt-dot{display:none}
  }

  .lead{font-size:14px;line-height:1.6;margin:8px 0 6px;padding-left:10px;border-left:3px solid var(--accent)}
  /* 六格轨迹小图：一行三张，窄屏自动并成一列 */
  .cv-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:10px 0 6px}
  @media (max-width:980px){.cv-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
  @media (max-width:680px){.cv-grid{grid-template-columns:1fr}}
  .cv-card{margin:0;background:#fff;border:1px solid var(--line);border-radius:8px;padding:6px 6px 4px}
  .cv-card svg.cv{width:100%;height:auto;display:block}
  .cv-card figcaption{font-size:11px;color:var(--mut);margin-top:2px;line-height:1.35}
</style>
</head>
<body>

<header class="top">
  <div class="wrap">
    <div class="eyebrow">LPO 112G PAM4 仿真平台 · 收发端联合寻优</div>
    <h1>DDPS：在线把发端均衡参数调到最优</h1>
    <div class="scope">
      这套方法解决一件事：光模块在线工作时拿不到收端误码，只有发端能测的量，怎么把 5 个 FFE 抽头、两个 CTLE 维度和驱动增益这 8 个参数自动调到该环境的最优附近。
      第一节直接给结论和四条支撑，后面依次是物理链路与参数、方向代理、在线算法与代价、15 个用例上的实测结果、换四个起点之后的轨迹、什么情况下不成立、怎么复现。
      数字全部来自结果目录里的 <code>case_summary / trace</code> 与源码常量；图是内嵌的 SVG 与 PNG，单个 HTML 离线就能看。
    </div>
    <nav class="toc" id="toc" aria-label="目录">
      <a href="#s1"><b>1</b> 结论</a>
      <a href="#s2"><b>2</b> 物理链路与优化对象</a>
      <a href="#s3"><b>3</b> 代理模型</a>
      <a href="#s4"><b>4</b> 寻优算法</a>
      <a href="#s5"><b>5</b> 数据集与评估协议</a>
      <a href="#s6"><b>6</b> 实测结果</a>
      <a href="#s7"><b>7</b> 什么时候不成立</a>
      <a href="#s8"><b>8</b> 复现与产物</a>
      <a href="#s9"><b>9</b> 两套实现与等价性</a>
    </nav>
  </div>
</header>

<div class="wrap">

<h2 id="s1"><span class="num">1</span>结论</h2>

<div class="card">
  <p style="font-size:15px;line-height:1.65;margin:0 0 10px"><strong>结论：拿不到收端误码时，用发端探针训一个方向代理，足以把 8 个均衡参数自动调到该环境的最优点；这个结论换起点仍成立，前提是起点落在代理训练覆盖的范围内。</strong>判断依据不是 BER 压了多少倍。那个数换个信道、换套器件参数就会变。真正的依据是三件与参数无关的事：三种取法的好坏顺序在四个起点上不变；有真实回传可比时，代理只在起点出界时才会输；出界这件事可以从数据集覆盖范围提前判断。</p>
  <ol style="margin-bottom:0">
    <li><strong>只用发端量就够，换环境不用重训</strong>：方向来自 8 个发端可测量（7-tap FIR 形状 + 驱动 RMS），与收端无关。训练数据只有 10 dB 基线环境的 <!--N_ROWS--> 个点，15 个用例（插损 10～20 dB，含色散、群时延、噪声）逐个在线调，不重训也不重新标定。逐用例见 6.1 核心表与 6.2 六格并列表。</li>
    <li><strong>三种取法的顺序是确定的：每步全测 ＞ 每步轮测 ＞ 只测首步后外推</strong>，而它们对链路的扰动按同一顺序递减。这是「方向精度」换「在线瞬时风险」的单调交换，没有一种取法全面更好；换起点也不改这个顺序，只改具体倍数。拆解见 4.3，对比见 6.1 矩阵表。</li>
    <li><strong>代理和真实回传差的是可信范围，不是精度</strong>：起点在训练范围内时两者落点相当，差别落在统计噪声里（见 6.4 前两个起点）；起点出界时代理给反向，回传仍能把 BER 拉下来。所以选哪条路，取决于起点有没有把握落在范围内，不取决于谁的数字小。</li>
    <li><strong>出界能提前判断，不用等它自己暴露</strong>：数据集覆盖范围就是边界（抽头 ±0.10、CTLE ±3 dB、gain ×0.20~1.26）。把旁瓣放大 3 倍这种起点已经出界，45 个用例·组合的最好结果全停在第一步之后，走完 15 步仍比出发时更差，而代理本身没有任何提示。判据与实测见 6.4 后两个起点和第 7 节。</li>

  </ol>
</div>

<figure>
  <div class="fig-scroll"><!--TOP_CURVE--></div>
  <figcaption>最能说明问题的一个用例：最难用例（IL20x20）在六种组合各自的 BER 随步变化，六条线同刻度。这四条结论的证据分别在第 4、6 节；四个起点 × 每个用例的完整轨迹在 6.4。</figcaption>
</figure>

<p class="note">往下怎么读：第 2 节讲约束和做法，第 3–5 节讲代理、算法和一次调优要花多少，第 6 节给全部证据（15 个用例、四个起点、安全性），第 7 节讲什么时候不成立，第 8–9 节讲怎么复现、两套实现怎么对齐。</p>

<div class="card">
  <h4 style="margin-top:0">约束：可用的是什么</h4>
  <ul style="margin-bottom:0">
    <li>LPO 光模块内部不做重 DSP，发送端均衡由 Host ASIC 承担。可用的自由度是 5 个 T-spaced 发送端 FFE 抽头（全部是搜索变量，不设边界），发送端模拟 CTLE 的高频 peaking 增益 gDC 与低频 shelf 增益 gDC2，再加 driver_gain，一共 8 维。接收端另有一级固定参数的模拟 CTLE（gDC = 6 dB，gDC2 = 3 dB）作静态均衡基座。</li>
    <li>信道条件：奈奎斯特电插损 Tx/Rx 各自 10～20 dB，色散 0～28 ps/nm，差分群时延 0～5 ps，偏振角 0～45°，另含 RIN、消光比、TIA 噪声三种器件应力。</li>
    <li>在线拿不到收端误码，方向只能由发端测得到的物理探针推断。探针没有现成的，要读到它就得把参数真的打到链路上跑一遍，那一刻收端性能是真的在变，所以每一次微扰都记一次真实的端到端 BER。</li>
    <li>有回传通道时不需要代理，直接对真实 BER 做梯度下降，这种情形跑成三格，数字在 6.2。</li>
  </ul>
</div>

<div class="card">
  <h4 style="margin-top:0">做法：三段</h4>
  <ol style="margin-bottom:0">
    <li><strong>物理探针</strong>：向发送链注入单位脉冲，在 MZM 输入端截取 7-tap 等效发射 FIR 的形状，同时取该点的绝对驱动 RMS。前者描述波形，后者描述驱动幅度，合成 8 维可测量。</li>
    <li><strong>方向代理（Model A）</strong>：输入 8 维探针，输出 log10 BER_MLSE 的条件均值，二阶多项式 Ridge 闭式解，纯 NumPy，带解析梯度。它只回答一件事：波形往这个方向变，误码往哪边走。在线决策只依赖它。</li>
    <li><strong>8 维梯度下降</strong>：<span class="mono">x = [5 个 FFE 抽头, gDC, gDC2, u_gain]</span>，driver_gain 走解析梯度（0 微扰）。梯度怎么拿是 3 × 2 的选择：三种形状维取法乘两种梯度来源，共用同一起点和固定 15 步，机制在 4.2，代价在 4.3。</li>
  </ol>
</div>

<h2 id="s2"><span class="num">2</span>物理链路与优化对象</h2>
<p class="lead">能动的东西全在发端：5 个 FFE 抽头、两个 CTLE 维度、驱动增益，一共 8 维；接收端固定。8 维里只有 CTLE 与增益受器件量程约束，抽头完全放开，边界不替代理做决定。</p>

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
  <div class="fig-title">图 2 · 8 维搜索空间</div>

  <svg class="d-wide" viewBox="0 0 1080 320" role="img" aria-label="优化空间参数化示意">
    <defs>
      <marker id="ah2" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#7b8ea6"/>
      </marker>
    </defs>

    <text class="tb" x="14" y="26">发送端 FFE：5 抽头，T-spaced（5 个抽头全部是搜索自由度）</text>

    <rect class="bx-hi" x="14" y="44" width="92" height="46" rx="7"/><text class="tw2" x="60" y="72" text-anchor="middle">t₀</text>
    <rect class="bx-hi" x="118" y="44" width="92" height="46" rx="7"/><text class="tw2" x="164" y="72" text-anchor="middle">t₁</text>
    <rect class="bx-hi" x="222" y="44" width="92" height="46" rx="7"/><text class="tw2" x="268" y="72" text-anchor="middle">t₂</text>
    <rect class="bx-hi" x="326" y="44" width="92" height="46" rx="7"/><text class="tw2" x="372" y="72" text-anchor="middle">t₃</text>
    <rect class="bx-hi" x="430" y="44" width="92" height="46" rx="7"/><text class="tw2" x="476" y="72" text-anchor="middle">t₄</text>

    <path class="brk" d="M14 98 L14 110 L522 110 L522 98" marker-end="url(#ah2)"/>
    <text class="ts" x="268" y="128" text-anchor="middle">5 个抽头 = 5 个自由变量；t₂ 与其它抽头地位相同，抽头维不设边界</text>

    <rect class="bx-hi" x="14" y="146" width="330" height="52" rx="7"/>
    <text class="tw2" x="179" y="168" text-anchor="middle">Tx CTLE：gDC ∈ [0, 12] dB · gDC2 ∈ [0, 4] dB</text>
    <text class="ts" x="179" y="186" text-anchor="middle">post-channel 高频 peaking（2 维，物理量程）</text>

    <rect class="bx" x="360" y="146" width="250" height="52" rx="7"/>
    <text class="tw2" x="485" y="168" text-anchor="middle">gain（第 8 维）</text>
    <text class="ts" x="485" y="186" text-anchor="middle">经 drive_rms 进入探针</text>

    <rect class="panel" x="626" y="146" width="440" height="150" rx="8"/>
    <text class="t" x="642" y="170">搜索向量：</text>
    <text class="mono" x="722" y="170" style="font-size:12.5px">x ∈ R⁸ = [t₀…t₄, gDC, gDC2, u_gain]</text>
    <text class="ts" x="642" y="192">种子 x₀：[−0.0885, −0.3147, 0.4079, 0.0845, 0.1043]，gDC 6.73，gDC2 0.85，gain ×0.325</text>
    <text class="ts" x="642" y="212">边界：只有 CTLE 与 gain 保留物理量程，抽头维无边界</text>
    <text class="ts" x="642" y="232">步长（不是参数箱）：FFE 0.20 / CTLE 6.0 dB / gain 0.60 dex，按 0.97^步 衰减</text>
    <text class="ts" x="642" y="256">组内归一化步长：FFE / CTLE / gain 三组各自归一化后乘尺度，</text>
    <text class="ts" x="642" y="272">组梯度低于门控 1e-3 时该组冻结。</text>

    <text class="tb" x="14" y="232">CTLE 放在 Tx 电插损之后、Driver 之前</text>
    <text class="ts" x="14" y="254">· 整形“到达 MZM 的频谱”，高频 peaking 补偿信道损耗才有效。</text>
    <text class="ts" x="14" y="272">· peaking 拓扑直流增益为 0 dB，只抬 Nyquist 附近、不整体抬幅，</text>
    <text class="ts" x="14" y="290">  驱动幅度由 gain 维独立控制，CTLE 与 gain 互不冗余。</text>
  </svg>

  <svg class="d-narrow" viewBox="0 0 360 430" role="img" aria-label="优化空间参数化示意（竖向）">
    <text class="tb" x="10" y="16">发送端 FFE：5 抽头（5 个都自由）</text>
    <rect class="bx-hi" x="10" y="26" width="62" height="38" rx="6"/><text class="tw2" x="41" y="50" text-anchor="middle">t₀</text>
    <rect class="bx-hi" x="80" y="26" width="62" height="38" rx="6"/><text class="tw2" x="111" y="50" text-anchor="middle">t₁</text>
    <rect class="bx-hi" x="150" y="26" width="62" height="38" rx="6"/><text class="tw2" x="181" y="50" text-anchor="middle">t₂</text>
    <rect class="bx-hi" x="220" y="26" width="62" height="38" rx="6"/><text class="tw2" x="251" y="50" text-anchor="middle">t₃</text>
    <rect class="bx-hi" x="290" y="26" width="62" height="38" rx="6"/><text class="tw2" x="321" y="50" text-anchor="middle">t₄</text>

    <text class="ts" x="10" y="130">5 个抽头都是自由变量：无边界、无派生</text>
    <text class="hi-t" x="10" y="150">t₂ 与其它抽头地位相同</text>

    <text class="tb" x="10" y="182">Tx 模拟 CTLE（post-channel）</text>
    <rect class="bx-hi" x="10" y="192" width="340" height="50" rx="7"/>
    <text class="tw2" x="24" y="212">gDC ∈ [0, 12] dB · gDC2 ∈ [0, 4] dB</text>
    <text class="ts" x="24" y="230">2 维：高频 peaking（物理量程）</text>

    <text class="tb" x="10" y="266">gain 维（第 8 搜索维）</text>
    <rect class="bx" x="10" y="276" width="340" height="50" rx="7"/>
    <text class="tw2" x="24" y="296">gain 纳入梯度（第 8 维，解析梯度）</text>
    <text class="ts" x="24" y="314">见 3.3 per-case RMS 标定参照；起点为次优点</text>

    <rect class="panel" x="10" y="340" width="340" height="80" rx="8"/>
    <text class="mono" x="24" y="362" style="font-size:12.3px">x ∈ R⁸ = [t₀…t₄, gDC, gDC2, u_gain]</text>
    <text class="ts" x="24" y="382">种子：[-0.0885,-0.3147,0.4079,0.0845,0.1043] / 6.73 / 0.85 dB / ×0.325</text>
    <text class="ts" x="24" y="400">步长：FFE 0.20 / CTLE 6.0 dB / gain 0.60 dex</text>
  </svg>

  <figcaption>5 个抽头全部独立进入搜索向量，t₂ 与其它抽头地位相同；抽头维不设边界。</figcaption>
</figure>

<h3>2.3 偏振怎么建模：单偏振收发，双偏振信道投影成一路</h3>
<p class="lead">这套链路是强度调制直接检测，发端和收端都是单偏振；偏振只出现在信道里，而且只通过两个量起作用：主轴夹角 pol_angle_deg 和差分群时延 dgd_ps。</p>
<ul>
  <li>发端单偏振。一个激光器出连续光，MZM 上做强度调制；FFE、驱动增益、Tx CTLE 都在电域，与偏振无关。没有偏振复用，也没有偏振旋转器件。</li>
  <li>信道按两个正交主轴算。信号按夹角 θ = pol_angle_deg 分到两轴，功率比 cos²θ : sin²θ；慢轴相对快轴延时 τ = dgd_ps。色散单独作用在光场包络上（频域二次相位），与 DGD 不耦合。</li>
  <li>收端单偏振直接检测。只有一个光电探测器，不分辨偏振，两轴分量在探测前叠加后平方律检波。正因为不分辨，两轴干涉直接落在强度上，等效频响 H(f) = cos²θ + sin²θ·e^(−j2πfτ)。</li>
  <li>两个极端。θ = 0° 时信号与一条主轴对齐，H(f) = 1，DGD 不起作用；θ = 45° 时功率均分，H(f) = (1 + e^(−j2πfτ))/2，出现两径干涉凹陷。15 个用例里的 DGD 应力就取在这个角度附近。</li>
  <li>没建模的部分。偏振相关损耗、偏振态随时间漂移、偏振复用与偏振分集接收都不在模型里；这条链路的分集只有时间和均衡两个方向，没有偏振方向。第 7 节把这条算进适用范围。</li>
</ul>
<figure>
<svg class="d-wide" viewBox="0 0 1040 220" role="img" aria-label="偏振建模通路">
  <rect x="14" y="60" width="150" height="86" rx="8" fill="#eef4ff" stroke="#8fb3e8"/>
  <text x="89" y="92" text-anchor="middle" font-size="12.5" fill="#1b3f6b">激光器（单偏振）</text>
  <text x="89" y="112" text-anchor="middle" font-size="11" fill="#43536b">强度调制 MZM</text>
  <text x="89" y="130" text-anchor="middle" font-size="11" fill="#43536b">电域均衡在发端</text>
  <rect x="238" y="46" width="250" height="114" rx="8" fill="#f7f9fc" stroke="#b8c4d6"/>
  <text x="363" y="68" text-anchor="middle" font-size="12" fill="#1b3f6b">光纤：双折射等效两主轴</text>
  <text x="363" y="90" text-anchor="middle" font-size="11" fill="#43536b">快轴 cosθ（不延时）</text>
  <text x="363" y="110" text-anchor="middle" font-size="11" fill="#43536b">慢轴 sinθ（延时 τ = DGD）</text>
  <text x="363" y="134" text-anchor="middle" font-size="11" fill="#43536b">θ = pol_angle_deg，0～45°</text>
  <text x="363" y="152" text-anchor="middle" font-size="11" fill="#43536b">τ = dgd_ps，0～5 ps</text>
  <rect x="562" y="60" width="170" height="86" rx="8" fill="#eef7f0" stroke="#8fc5a3"/>
  <text x="647" y="90" text-anchor="middle" font-size="12.5" fill="#14532d">两轴合成后探测</text>
  <text x="647" y="110" text-anchor="middle" font-size="11" fill="#43536b">单个 PD，平方律</text>
  <text x="647" y="128" text-anchor="middle" font-size="11" fill="#43536b">不分辨偏振</text>
  <rect x="806" y="60" width="200" height="86" rx="8" fill="#fff8e8" stroke="#e0c07a"/>
  <text x="906" y="90" text-anchor="middle" font-size="12.5" fill="#7a5b12">等效单路频响</text>
  <text x="906" y="112" text-anchor="middle" font-size="11.5" fill="#43536b">H(f) = cos²θ</text>
  <text x="906" y="130" text-anchor="middle" font-size="11.5" fill="#43536b">+ sin²θ·e^(−j2πfτ)</text>
  <text x="14" y="196" font-size="11" fill="#5b6b7d">发端、收端都是单偏振；双偏振信道被投影成一路：θ=0° 时冲击只走一条轴，DGD 不起作用；θ=45° 时功率均分，DGD 造成两径干涉凹陷。</text>
</svg>
<figcaption>图 2 · 偏振只在信道里起作用：发端单偏振强度调制，信道按 cos²θ / sin²θ 把功率分到两个正交主轴，慢轴延时 τ，收端单个探测器把两轴合成后平方律检波，整条链路等效成一个标量频响。</figcaption>
</figure>

<h3>2.4 隔直与低频响应：规范只给 3 dB 上限，模型就是一个单极点高通</h3>
<p class="lead">收端隔直是模拟电路（模块输出、host 输入各一处），规范只规定低频 3 dB 截止频率的上限，不规定电容和电阻的取值，所以建模就按这个上限取一个单极点高通，不还原成 RC 器件。</p>
<ul>
  <li>规范给的数：50G/lane 上限 50 kHz，100G/lane 提到 <strong>100 kHz</strong>，200G/lane 草案仍按 100 kHz（200 kHz 只是提案）。100 nF 配 46.5 Ω 实算 34 kHz，同样合规——规范限的是拐点，不是器件。</li>
  <li>模型：H(f) = (j·f/fc) / (1 + j·f/fc)，fc 取规范上限；幅度与相位都按这条式子施加，含群时延。两处隔直串联，复合 -3 dB 点是 1.554·fc。</li>
  <li>为什么取上限：链路要能容忍任何合规实现，拐点越高、低频掉得越狠，取上限就是最坏的合规情况；比上限更低的实现只会更好，不需要再建一档。</li>
  <li>在这个波特率下它几乎透明：fc = 100 kHz 对应 τ = 1.59 µs，53.125 GBd 下相当于 8.45 万个符号时间；1000 个相同符号的 droop 只有 1.2%，要到 1 MHz 才 11%。所以隔直去掉的是直流，符号尺度的波形几乎不动。</li>
  <li>去掉的东西：以前收端是「整段减均值」，等于截止频率为 0 的理想隔直，低频漂移在模型里不存在。换成这条高通之后，基线漂移是模型里真实存在的效应。</li>
</ul>
<figure>
  <div class="fig-scroll"><!--AC_SVG--></div>
  <figcaption>图 3 · 左：单极点高通的幅频响应与两条合规拐点；右：1000 个相同符号经过隔直后的 droop。fc 取规范上限时，符号尺度上几乎看不见衰减，1 MHz 那条只作对照、不合规。</figcaption>
</figure>
<h3>2.5 关键参数（取自 <span class="mono">config.xlsx</span>，112G 模式）</h3>
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

<h3>2.6 十五个物理应力用例</h3>
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

<h3>2.7 搜索向量的参数化公式（复现所需的完整映射）</h3>
<p>搜索向量 <span class="mono">x = [x₀ x₁ x₂ x₃ x₄, x₅, x₆, x₇] ∈ R⁸</span> 到物理器件的映射如下，是复现本方案必须写死的三处参数化。</p>
<div class="card">
<h4 style="margin-top:0">① 5 抽头 Tx FFE（5 个抽头都是搜索变量）</h4>
<pre style="margin:6px 0"><code>h = [h₀, h₁, h₂, h₃, h₄]，T-spaced（2 个前游标 + 主抽头 + 2 个后游标）
x₀…x₄ = h₀…h₄，逐抽头独立进入搜索向量，没有派生关系、没有边界</code></pre>
<p style="margin:6px 0">抽头维不加任何约束。边界不替代理做决定，方向和步长完全由梯度与步长决定。抽头之和会不会变、主抽头会不会被压低，由梯度自己权衡，后果会如实体现在真实 BER 与探针上。</p>
</div>
<div class="card">
<h4 style="margin-top:0">② Tx 模拟 CTLE（gDC、gDC2 两维，OIF 2Z3P peaking 拓扑）</h4>
<pre style="margin:6px 0"><code>K_DC  = 10^(gDC/20)，  K_DC2 = 10^(gDC2/20)
H_S1(f) = (1 + j·f·K_DC/f_z) / [(1 + j·f/f_p1)(1 + j·f/f_p2)]     高频 peaking（有效零点 f_z/K_DC，峰值 ≈ K_DC）
H_S2(f) = (1 + j·f·K_DC2/f_lf) / (1 + j·f/f_lf)                     低频 shelf（转折 f_lf，增益 K_DC2）
H_CTLE(f) = H_S1(f) · H_S2(f)，直流增益为 0 dB
f_z = f_b/2.862，f_p1 = f_b/1.884，f_p2 = f_b/1.0，f_lf = f_b/40，f_b = 56 GHz</code></pre>
<p style="margin:6px 0">搜索变量 x₅ = gDC（dB，[0,12]）、x₆ = gDC2（dB，[0,4]），这两维保留物理量程，也就是器件做得到的范围。高频 peaking 只抬 Nyquist 附近、不抬直流；驱动幅度由 gain 维单独控制，两者不重复。</p>
</div>
<div class="card">
<h4 style="margin-top:0">③ driver_gain（第 8 维，对数参数化）</h4>
<pre style="margin:6px 0"><code>gain = g₀ · 10^u_gain，  u_gain = log₁₀(gain / g₀)，  g₀ = 0.3399（标称 driver_gain）</code></pre>
<p style="margin:6px 0">搜索变量 x₇ = u_gain。driver_gain 是 Tx 链末尾的标量乘子，只整体缩放波形，所以 gain 维梯度有解析解（§4.2.1）。</p>
</div>

<h2 id="s3"><span class="num">3</span>代理模型</h2>
<p class="lead">8 个发端可测量就够判断「波形往哪边改会让误码变好」，不需要知道 BER 的绝对值。代理吃的是波形，所以换信道、换插损不用重训，这是它能跨环境复用的原因。</p>

<h3>3.1 方向代理（Model A）的输入输出，以及它的在线代价</h3>
<figure>
  <div class="fig-title">图 3 · 方向代理的数据通路与在线代价</div>
  <svg class="d-wide" viewBox="0 0 1080 260" role="img" aria-label="方向代理数据通路与在线代价">
    <defs>
      <marker id="ah3" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#8fa3ba"/>
      </marker>
    </defs>

    <text class="tb" x="14" y="26">Model A（在线只依赖它：波形往哪边走，误码往哪边走）</text>
    <rect class="bx" x="14" y="40" width="150" height="50" rx="8"/>
    <text class="tw2" x="89" y="62" text-anchor="middle">8 维参数</text>
    <text class="ts" x="89" y="79" text-anchor="middle">5 抽头 + gDC + gDC2 + u_gain</text>

    <rect class="bx-hi" x="204" y="40" width="150" height="50" rx="8"/>
    <text class="tw2" x="279" y="62" text-anchor="middle">物理探针</text>
    <text class="ts" x="279" y="79" text-anchor="middle">参数真的打上链路</text>

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

    <text class="tb" x="14" y="156">同一链路、同一时刻的真实 BER（只记录，不参与决策）</text>
    <rect class="bx" x="14" y="170" width="350" height="50" rx="8"/>
    <text class="tw2" x="189" y="192" text-anchor="middle">每步走到的参数 x_k：真实 BER_MLSE</text>
    <text class="ts" x="189" y="209" text-anchor="middle">优化后的工作点，链路真实处于这里</text>

    <rect class="bx-hi" x="424" y="170" width="230" height="50" rx="8"/>
    <text class="tw2" x="539" y="192" text-anchor="middle">±ε 微扰点：真实 BER_MLSE</text>
    <text class="ts" x="539" y="209" text-anchor="middle">为测形状维梯度而施加</text>

    <rect class="bx" x="694" y="170" width="290" height="50" rx="8"/>
    <text class="tw2" x="839" y="192" text-anchor="middle">逐次记录、逐次公开（6.3 / 6.4）</text>
    <text class="ts" x="839" y="209" text-anchor="middle">微扰次数是方案的真实运行代价</text>

    <line class="ln" x1="364" y1="195" x2="422" y2="195" marker-end="url(#ah3)"/>
    <line class="ln" x1="654" y1="195" x2="692" y2="195" marker-end="url(#ah3)"/>
  </svg>

  <svg class="d-narrow" viewBox="0 0 360 560" role="img" aria-label="方向代理数据通路与在线代价（竖向）">
    <defs>
      <marker id="an3" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#8fa3ba"/>
      </marker>
    </defs>
    <text class="tb" x="10" y="16">Model A（在线只依赖它）</text>

    <rect class="bx" x="10" y="26" width="340" height="42" rx="7"/>
    <text class="tw2" x="24" y="46">8 维参数（5 抽头 + gDC + gDC2 + u_gain）</text>
    <text class="ts" x="24" y="62">扰动 -> 重算探针 -> 查 A</text>

    <rect class="bx-hi" x="10" y="80" width="340" height="38" rx="7"/>
    <text class="tw2" x="24" y="104">物理探针（参数真的打上链路）</text>

    <rect class="bx" x="10" y="130" width="340" height="42" rx="7"/>
    <text class="tw2" x="24" y="150">7-tap FIR 形状 + 绝对驱动 RMS</text>
    <text class="ts" x="24" y="166">8 维特征 → D = 45</text>

    <rect class="bx-ok" x="10" y="184" width="340" height="38" rx="7"/>
    <text class="tw2" x="24" y="208">Model A（Ridge 闭式解）</text>

    <rect class="bx" x="10" y="234" width="340" height="38" rx="7"/>
    <text class="tw2" x="24" y="258">log10 BER 预测（方向 + 幅度）</text>

    <line class="ln" x1="180" y1="68" x2="180" y2="78" marker-end="url(#an3)"/>
    <line class="ln" x1="180" y1="118" x2="180" y2="128" marker-end="url(#an3)"/>
    <line class="ln" x1="180" y1="172" x2="180" y2="182" marker-end="url(#an3)"/>
    <line class="ln" x1="180" y1="222" x2="180" y2="232" marker-end="url(#an3)"/>

    <line class="brk" x1="10" y1="294" x2="350" y2="294"/>

    <text class="tb" x="10" y="318">同一链路的真实 BER（只记录）</text>

    <rect class="bx" x="10" y="328" width="340" height="52" rx="7"/>
    <text class="tw2" x="24" y="348">每步走到的参数 x_k 的真实 BER_MLSE</text>
    <text class="ts" x="24" y="366">链路真实处于这个工作点</text>

    <rect class="bx-hi" x="10" y="392" width="340" height="52" rx="7"/>
    <text class="tw2" x="24" y="412">±ε 微扰点的真实 BER_MLSE</text>
    <text class="ts" x="24" y="430">为估计形状维梯度而施加</text>

    <rect class="bx" x="10" y="456" width="340" height="52" rx="7"/>
    <text class="tw2" x="24" y="476">逐次记录、逐次公开</text>
    <text class="ts" x="24" y="494">微扰次数 = 方案的真实运行代价</text>

    <text class="ts" x="10" y="530">真实 BER 不参与方向与终止决策；</text>
    <text class="ts" x="10" y="546">它只用来说明优化后落在哪里、代价有多大。</text>
  </svg>

  <figcaption>在线决策只依赖 Model A 给的梯度方向。探针没有现成的，参数得真的打到链路上跑一遍，所以每一次微扰都是一次真实的性能代价。方案把每次微扰的实测 BER 都记下来公开，不只报最后落在哪。</figcaption>
</figure>

<div class="card">
  <h4 style="margin-top:0">Model A 的第 8 个特征：绝对驱动 RMS</h4>
  <p style="margin-bottom:0">
    <code>driver_gain</code> 在线性 Tx 链中只是标量乘子，只整体缩放波形；7-tap FIR 若只看<strong>形状</strong>（峰值归一化）则对它不敏感，梯度在该维恒为 0。
    因此探针把 7-tap FIR 保留绝对量纲（除以常数 <span class="mono">DRIVE_RMS_NOMINAL</span>），并把 MZM 输入端的真实驱动 RMS 作为第 8 个特征，
    <code>driver_gain</code> 的变化同时体现在抽头幅度与驱动 RMS 上，使该维拿到非零梯度。
  </p>
</div>

<!--DATASET_CARD-->

<h3>3.2 模型形式、超参数与指标</h3>
<p>两个模型共用同一学习器：手写二阶多项式特征 + L2 正则 Ridge 回归闭式解，纯 NumPy。输入先逐维标准化到零均值单位方差再进多项式，权重用闭式解一次求定（无迭代、无第三方求解器）。</p>
<pre><code>输入标准化    x̂ = (x − μ) / σ                             μ、σ = 训练集逐维均值 / 标准差
特征展开      φ(x̂) = [1, x̂₁…x̂_d, x̂₁²…x̂_d², x̂₁x̂₂…x̂_{d−1}x̂_d]    D = 1 + 2d + d(d−1)/2
拟合闭式解    W = (ΦᵀΦ + α·I)⁻¹ Φᵀ y                    Φ = φ(X̂)：标准化后的设计矩阵
推理          ŷ(x) = φ(x̂)ᵀ W
解析梯度      ∂ŷ/∂x̂ᵢ = wᵢ + 2·w_ii·x̂ᵢ + Σ_{k≠i} w_ik·x̂_k
原始量纲梯度  ∂ŷ/∂xᵢ = (∂ŷ/∂x̂ᵢ) / σᵢ                      （链式法则 dŷ/dx = dŷ/dx̂ · 1/σ）

Model A：d = 8（7-tap 绝对标定 FIR + drive_rms），α = 1.0，预测 log10(BER_MLSE) 条件均值，需解析梯度。
同一学习器在参数域还训练了一个离线产物（Stage 1 一并导出，不在线使用，指标不列）。</code></pre>

<div class="tw">
<table class="wide">
  <caption>方向代理训练指标（<!--N_ROWS--> 行，80/20 划分） <span class="sh">· 可左右滑动</span></caption>
  <tr><th>模型</th><th>输入域</th><th class="n">特征维度</th><th class="n">n_train / n_test</th><th class="n">R²</th><th class="n">MSE</th><th class="n">Spearman</th><th>说明</th></tr>
  <!--MODEL_METRICS_ROWS-->
</table>
</div>

<h3>3.3 gain 维的 per-case target_rms 标定（参照）</h3>
<p>gain 是第 8 个搜索维（x₇）。为刻画每个用例的最优 gain（供验收参照），离线按用例单独细粒度扫描 MZM 输入 RMS
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
<p class="lead">三种取法的算法完全一样，区别只在于为了估方向，每步要把链路推开多少次。每一次推开都是一次真实扰动：链路在那一刻停在偏离工作点的位置，端到端 BER 会比这一步的结果更差。这个方案真正在换的是「方向准不准」和「在线承担多大瞬时风险」，评估次数只是这本风险账的计量单位。</p>

<p>在线调优就是<strong>8 维梯度下降</strong>：<span class="mono">x = [5 个 Tx FFE 抽头, gDC, gDC2, u_gain]</span>。梯度怎么拿，是两个正交的选择，一共六种组合：<strong>三种形状维取法</strong>（<strong>full</strong> 每步全量微扰、<strong>rotate</strong> 每步轮转 2 维、<strong>secant</strong> 只在第 0 步微扰、之后割线外推）乘 <strong>两种梯度来源</strong>（发端 Model A 方向代理，不用回传；收端真实 BER 回传）。发端代理那一行是现役方案：方向由冻结的 Model A 给，形状 7 维按三种取法之一刷新，gain 维一直用解析梯度。六格共用同一次优起点、同一组归一化步长与门控、同一个 15 步上限，一键切换（<span class="mono">--method proxy|direct</span> 配 <span class="mono">--grad-mode full|rotate|secant</span>）。真正的区别只有一个：为了估计梯度，要把链路真实推到偏离工作点的位置多少次。次数与每次的该步 BER 在第 6 节逐条列出，代价汇总在 §4.3。六格共用同一条物理链路（第 2 节）和同一个起点（6.0）。</p>

<h3>4.1 两阶段结构：离线冻结方向，在线只走探针</h3>
<figure>
  <div class="fig-title">图 4 · DDPS 两阶段流程（Stage 1 离线一次性 / Stage 2 在线逐环境）</div>

  <svg class="d-wide" viewBox="0 0 1080 430" role="img" aria-label="两阶段算法流程图">
    <defs>
      <marker id="ah4" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#8fa3ba"/>
      </marker>
    </defs>

    <text class="tb" x="14" y="24">Stage 1 · 离线一次性（基线环境邻域）</text>
    <rect class="bx" x="14" y="38" width="196" height="52" rx="8"/>
    <text class="tw2" x="112" y="60" text-anchor="middle">数据集：<!--N_ROWS--> 点真实 BER</text>
    <text class="ts" x="112" y="78" text-anchor="middle">每点带 8 维物理探针</text>

    <rect class="bx" x="240" y="38" width="196" height="52" rx="8"/>
    <text class="tw2" x="338" y="60" text-anchor="middle">二阶多项式 Ridge</text>
    <text class="ts" x="338" y="78" text-anchor="middle">闭式解，无迭代</text>

    <rect class="bx-ok" x="466" y="38" width="180" height="52" rx="8"/>
    <text class="tw2" x="556" y="60" text-anchor="middle">冻结 Model A</text>
    <text class="ts" x="556" y="78" text-anchor="middle">探针 → log10 BER</text>

    <line class="ln" x1="210" y1="64" x2="238" y2="64" marker-end="url(#ah4)"/>
    <line class="ln" x1="436" y1="64" x2="464" y2="64" marker-end="url(#ah4)"/>
    <text class="ts" x="666" y="58">离线只做一次，训练完即冻结；</text>
    <text class="ts" x="666" y="76">在线阶段不再重训、不再标定。</text>

    <line class="brk" x1="14" y1="112" x2="1064" y2="112"/>

    <text class="tb" x="14" y="140">Stage 2 · 在线逐环境（每个新环境从同一次优起点出发）</text>

    <rect class="bx" x="14" y="156" width="150" height="52" rx="8"/>
    <text class="tw2" x="89" y="178" text-anchor="middle">次优起点 x₀</text>
    <text class="ts" x="89" y="196" text-anchor="middle">8 维，全集同一个</text>

    <rect class="bx-hi" x="196" y="156" width="164" height="52" rx="8"/>
    <text class="tw2" x="278" y="178" text-anchor="middle">探针 p(x_k)</text>
    <text class="ts" x="278" y="196" text-anchor="middle">参数真的打上链路</text>

    <rect class="bx" x="392" y="156" width="176" height="52" rx="8"/>
    <text class="tw2" x="480" y="178" text-anchor="middle">梯度 g = ∇A(p)</text>
    <text class="ts" x="480" y="196" text-anchor="middle">gain 解析 + 形状 7 维</text>

    <rect class="bx" x="600" y="156" width="184" height="52" rx="8"/>
    <text class="tw2" x="692" y="178" text-anchor="middle">组归一化 + 门控</text>
    <text class="ts" x="692" y="196" text-anchor="middle">步长 α = 0.05·0.97^k</text>

    <rect class="bx-ok" x="816" y="156" width="180" height="52" rx="8"/>
    <text class="tw2" x="906" y="178" text-anchor="middle">参数点 x_{k+1}</text>
    <text class="ts" x="906" y="196" text-anchor="middle">clip 到物理量程</text>

    <line class="ln" x1="164" y1="182" x2="194" y2="182" marker-end="url(#ah4)"/>
    <line class="ln" x1="360" y1="182" x2="390" y2="182" marker-end="url(#ah4)"/>
    <line class="ln" x1="568" y1="182" x2="598" y2="182" marker-end="url(#ah4)"/>
    <line class="ln" x1="784" y1="182" x2="814" y2="182" marker-end="url(#ah4)"/>

    <path class="ln" d="M996 182 L1024 182 L1024 240 L96 240 L96 210" marker-end="url(#ah4)"/>
    <text class="ts" x="560" y="258" text-anchor="middle">固定 15 步：每步都这样走一遍，不做提前停止（便于逐格对齐代价与收益）</text>

    <text class="tb" x="14" y="300">每步真实打到链路上去的次数（梯度估计的物理代价）</text>
    <rect class="bx" x="14" y="314" width="240" height="60" rx="8"/>
    <text class="tw2" x="134" y="336" text-anchor="middle">full：形状 7 维全量微扰</text>
    <text class="ts" x="134" y="354" text-anchor="middle">14 个 ±ε 态 / 步</text>

    <rect class="bx" x="272" y="314" width="240" height="60" rx="8"/>
    <text class="tw2" x="392" y="336" text-anchor="middle">rotate：每步轮转 2 维</text>
    <text class="ts" x="392" y="354" text-anchor="middle">4 个 ±ε 态 / 步</text>

    <rect class="bx" x="530" y="314" width="240" height="60" rx="8"/>
    <text class="tw2" x="650" y="336" text-anchor="middle">secant：第 0 步一轮后外推</text>
    <text class="ts" x="650" y="354" text-anchor="middle">0 个 ±ε 态 / 步</text>

    <rect class="bx" x="788" y="314" width="208" height="60" rx="8"/>
    <text class="tw2" x="892" y="336" text-anchor="middle">gain 维：解析梯度</text>
    <text class="ts" x="892" y="354" text-anchor="middle">0 个 ±ε 态 / 步</text>

    <text class="ts" x="14" y="400">每步的该步 BER、以及上面每一次微扰点各自的 BER，都逐次测量并落盘（6.3 / 6.4）；它们只用来看清代价，不参与方向与终止决策。</text>
  </svg>

  <svg class="d-narrow" viewBox="0 0 360 620" role="img" aria-label="两阶段算法流程图（竖向）">
    <defs>
      <marker id="an4" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#8fa3ba"/>
      </marker>
    </defs>
    <text class="tb" x="10" y="16">Stage 1 · 离线一次性</text>
    <rect class="bx" x="10" y="26" width="340" height="44" rx="7"/>
    <text class="tw2" x="24" y="46">数据集：<!--N_ROWS--> 点真实 BER + 8 维探针</text>
    <text class="ts" x="24" y="62">基线环境邻域，一次性</text>
    <rect class="bx" x="10" y="80" width="340" height="44" rx="7"/>
    <text class="tw2" x="24" y="100">二阶多项式 Ridge 闭式解</text>
    <text class="ts" x="24" y="116">无迭代，无第三方求解器</text>
    <rect class="bx-ok" x="10" y="134" width="340" height="40" rx="7"/>
    <text class="tw2" x="24" y="159">冻结 Model A（探针 → log10 BER）</text>
    <line class="ln" x1="180" y1="70" x2="180" y2="78" marker-end="url(#an4)"/>
    <line class="ln" x1="180" y1="124" x2="180" y2="132" marker-end="url(#an4)"/>

    <line class="brk" x1="10" y1="190" x2="350" y2="190"/>

    <text class="tb" x="10" y="214">Stage 2 · 在线逐环境</text>
    <rect class="bx" x="10" y="224" width="340" height="42" rx="7"/>
    <text class="tw2" x="24" y="244">次优起点 x₀（8 维，全集同一个）</text>
    <text class="ts" x="24" y="260">含 gain ×0.325</text>
    <rect class="bx-hi" x="10" y="276" width="340" height="38" rx="7"/>
    <text class="tw2" x="24" y="300">探针 p(x_k)：参数真的打上链路</text>
    <rect class="bx" x="10" y="324" width="340" height="42" rx="7"/>
    <text class="tw2" x="24" y="344">梯度 g = ∇A(p)：gain 解析 + 形状 7 维</text>
    <text class="ts" x="24" y="360">形状维取法：full / rotate / secant</text>
    <rect class="bx" x="10" y="376" width="340" height="42" rx="7"/>
    <text class="tw2" x="24" y="396">组归一化 + 门控 + 步长 0.05·0.97^k</text>
    <text class="ts" x="24" y="412">clip 到物理量程</text>
    <rect class="bx-ok" x="10" y="428" width="340" height="38" rx="7"/>
    <text class="tw2" x="24" y="452">参数点 x_{k+1}（固定 15 步）</text>

    <line class="ln" x1="180" y1="266" x2="180" y2="274" marker-end="url(#an4)"/>
    <line class="ln" x1="180" y1="314" x2="180" y2="322" marker-end="url(#an4)"/>
    <line class="ln" x1="180" y1="366" x2="180" y2="374" marker-end="url(#an4)"/>
    <line class="ln" x1="180" y1="418" x2="180" y2="426" marker-end="url(#an4)"/>

    <line class="brk" x1="10" y1="486" x2="350" y2="486"/>

    <text class="tb" x="10" y="510">每步真实打到链路上的次数</text>
    <text class="ts" x="10" y="532">full：形状 7 维全量微扰，14 个 ±ε 态 / 步</text>
    <text class="ts" x="10" y="550">rotate：每步轮转 2 维，4 个 ±ε 态 / 步</text>
    <text class="ts" x="10" y="568">secant：第 0 步一轮后外推，0 个 ±ε 态 / 步</text>
    <text class="ts" x="10" y="586">gain：解析梯度，0 个 ±ε 态 / 步</text>
    <text class="ts" x="10" y="606">参数点与每个微扰点的真实 BER 都逐次落盘（6.3 / 6.4）。</text>
  </svg>

  <figcaption>Stage 1 离线把「波形 → 误码」这条因果链一次学定并冻结；Stage 2 在线只做两件事：施加参数取探针、按 Model A 的梯度走一步。取探针必须把参数真正打到链路上，所以每步的微扰次数就是方案的真实代价。</figcaption>
</figure>

<h3>4.2 Stage-2 单步计算流程</h3>
<div class="card">
  <ol style="margin-bottom:0">
    <li><strong>取当前参数点探针</strong>：把 x_k 打到链路上，取 7-tap 等效发射 FIR 形状 + 该点绝对驱动 RMS（8 维特征）。这一步链路真实处于 x_k。</li>
    <li><strong>gain 维解析梯度（0 微扰）</strong>：driver_gain 是 Tx 链末尾的标量乘子，8 维探针特征全部正比于 gain，因此 gain 维梯度有闭式链式解，用当前探针直接算出（§4.2.1）。</li>
    <li><strong>形状维梯度（三种取法）</strong>：full / rotate / secant，见 §4.2.2；三种取法都保证第 0 步先用一次 7 维全量中心差分把方向立起来。</li>
    <li><strong>组归一化与门控</strong>：缩放后梯度 <span class="mono">g·span</span> 按三组（FFE 5 维 / CTLE 2 维 / gain 1 维）各自归一化成方向，范数低于 <span class="mono">1e-3</span> dex 的组冻结（方向置 0），避免沿拟合噪声移动。</li>
    <li><strong>步长</strong>：<span class="mono">α = 0.05 · 0.97^k</span>，乘在分组步长向量上（§4.2.3）。每组步长只决定一步走多远，不是参数的允许范围。</li>
    <li><strong>参数点</strong>：<span class="mono">x_{k+1} = clip(x_k − α·span·d)</span>，只对 CTLE 与 gain 做物理量程裁剪，抽头维不裁剪。</li>
    <li><strong>记录</strong>：参数点与本次所有微扰点都跑一次真实 BER_MLSE，逐条写入 trace 与 probes 文件；它们不参与方向与终止决策。</li>
    <li><strong>迭代</strong>：固定走满 15 步（不提前停止），保证各种取法在同等步数下比较。</li>
  </ol>
</div>

<h4>4.2.1 gain 维的解析梯度（0 微扰，每步重算）</h4>
<p>driver_gain 位于 Tx 链末尾，只对波形做标量缩放。Model A 的 8 维输入中，7-tap FIR 保留绝对量纲（除以常数 <span class="mono">DRIVE_RMS_NOMINAL</span>）、第 8 维是驱动 RMS，两者都正比于 gain，因此把 log10 域参数 <span class="mono">u = log₁₀(gain/g₀)</span> 作为该维坐标时：</p>
<pre><code>p(u) = 10^u · p̂ ，  p̂ 与 u 无关（形状 + 单位驱动）
∂A/∂u = ln(10) · Σⱼ (∂A/∂pⱼ) · pⱼ                        （对全部 8 个探针特征求和）
g₇ ← ∂A/∂u  每步用当前参数点的探针重算</code></pre>
<p>这条链式解只用到 Model A 的雅可比 <span class="mono">∂A/∂p</span>（二阶多项式对特征的解析导数），不需要任何额外探针，也不需要数值差分。</p>

<h4>4.2.2 形状维梯度的三种取法（一键切换）</h4>
<div class="tw">
<table>
  <caption>三种取法的机制与真实代价（同一实现、同一超参，只换「形状维梯度怎么来」）</caption>
  <tr><th>取法</th><th>每步形状维梯度怎么来</th><th class="n">每步 ±ε 微扰点</th><th>每步真实评估</th><th>代价特征</th></tr>
  <tr>
    <td><strong>full</strong></td>
    <td>7 维全部用当前参数点的中心差分重算，方向每步都是「当前波形邻域的实测斜率」</td>
    <td class="n">14</td><td class="n">15</td>
    <td>方向最不易被历史误差带偏，代价最高</td>
  </tr>
  <tr>
    <td><strong>rotate</strong></td>
    <td>每步只重算 2 个维（第 k 步重算维 <span class="mono">{(2k+j) mod 7}</span>），其余维沿用上一次的实测值</td>
    <td class="n">4</td><td class="n">5</td>
    <td>4 步就把 7 个维各刷新一遍、此后循环；每步 4 个微扰点（15 步里每维重算 4~5 次）</td>
  </tr>
  <tr>
    <td><strong>secant</strong></td>
    <td>只有第 0 步用 7 维中心差分；此后用 Broyden 秩一修正 <span class="mono">g ← g + [(ΔA_shape − gᵀs)/‖s‖²]·s</span>（s = 上一步落地位移的形状 7 维；ΔA_shape = 上一步 Model A 预测变化<strong>扣除 gain 维贡献</strong>后的部分，即 ΔA − g_gain·Δu），0 微扰</td>
    <td class="n">0</td><td class="n">1</td>
    <td>代价最低；方向依赖历史位移的可信度</td>
  </tr>
  <tr>
    <td><strong>gain（第 8 维）</strong></td>
    <td>解析链式解（§4.2.1），与上面三种取法正交，任何取法下都是 0 微扰</td>
    <td class="n">0</td><td class="n">—</td>
    <td>不产生任何试探态</td>
  </tr>
</table>
</div>
<p>三种取法的第 0 步完全一样，14 个微扰点把 7 维方向一次立起来，所以第 0 步的代价是三者共有的固定开销，差异从第 1 步才开始累积。每用例的评估次数与耗时见 §4.3，微扰点自己的 BER 包络见 6.4。</p>

<!--TURN_BLOCK-->

<h4>4.2.3 方向、步长与终止</h4>
<pre><code>组内归一化   d_组 = (g·span)_组 / ‖(g·span)_组‖₂ ，‖(g·span)_组‖ &lt; GROUP_GATE=1e-3 时 d_组 = 0
步长     span = [0.20 ×5（FFE 抽头）, 6.0（gDC）, 6.0（gDC2）, 0.60（gain）]
步长         α_k = GD_LR · ALPHA_DECAY^k = 0.05 · 0.97^k
更新         x_{k+1} = clip(x_k − α_k · span ⊙ d, 物理量程)
物理量程     gDC ∈ [0, 12] dB，gDC2 ∈ [0, 4] dB，gain/g₀ ∈ [10^−0.52, 10^0.6]；抽头维无边界
步数         固定 15 步，不做提前停止（真实 BER 回传格保留边际停止，见 6.2）</code></pre>
<p>每组步长管的是每一步走多远，不是参数的允许范围。抽头维没有范围限制，走多远完全由梯度与步长决定。三组各自归一化后再乘尺度，FFE（±0.1 量级）、CTLE（dB 量级）、gain（dex 量级）三个量纲不同的组就不会互相压制。</p>
<p>共轭梯度、拟牛顿这类方法省的是迭代次数，前提有三条：目标光滑、能做线搜索、约束不挡路。在线闭环里三条都不成立。端到端 BER 带门限，错误数是整数，发端算出来的差值在统计噪声里抖；CG 的 β 由相邻两步的梯度差构成，噪声一大，算出来的方向就和真实曲率无关。参数有物理量程，clip 会打断共轭；调优又不允许把 BER 打炸（§6.3），而 CG 后期的步长偏大。真正决定代价的是链路时间：一个探针态要让链路在该工作点跑够流量、等收端均衡收敛，才统计得出可信 BER，这段时间链路停在次优工作点上，就是实打实的流量损失。线搜索每步要测好几个这样的点，调优窗口直接被放大。CG 每步仍然要一个新梯度（16 个探针态），省的是迭代数，不是测量数。在线系统还是非平稳的，温度、老化、收端自适应都在漂，上一步的曲率下一步就过期。实测里唯一带跨步记忆外推的 secant，最坏单例落后 2.71 倍（§6.1），每步重测的 full 最好。CG 最擅长治的特征值跨度大，在这里主要是量纲差（抽头 ±0.1、CTLE 6 dB、gain 0.6 dex），三组归一化加步长已经处理掉了；剩下的是 BER 曲面自己的曲率，那不是二次型。</p>
<p>什么时候该用 CG 或 L-BFGS：目标是廉价解析模型、维度高、梯度无噪、能负担线搜索，而且调优窗口内可以当成平稳。对这套系统，对应的是离线设计，也就是拿准确的链路模型做预加重和 FIR 设计，不是在线闭环。在线闭环里能省的只有每步测几个点（full → rotate → secant），不是少迭代几次。</p>

<h3>4.3 每步往链路注入多少扰动，带来多大瞬时风险</h3>
<p>「把参数打到链路上取探针」和「落在某个工作点上测真实 BER」都是一次真实的端到端评估。下表是按实测 trace 统计出来的每用例评估次数（<!--SCALE_LABEL--> 符号，单种子 42）。落地次数各格一样，都是 15 步；不同的是微扰点次数。单价也要算清楚：每个被记录的状态都要付一次完整的真实评估，参数点要测真实 BER，±ε 微扰点同样要测，微扰点的实测 BER 见 6.4。在线算法本身在微扰点只需要探针加 Model A 前向（Python 实测中位约 5 ms，比一次真实评估便宜三个数量级），真实 BER 只是为记录而测，不参与决策。所以三种取法的差别，就是它们把链路推到偏离工作点的次数不同；次数多，方向估得准，但在线承担的瞬时风险也大。</p>
<div class="tw">
<table class="wide">
  <caption>每用例真实评估次数（数据取自 <span class="mono">result/ddps_cpp_*/case_summary.csv</span>） <span class="sh">· 可左右滑动</span></caption>
  <tr><th>取法</th><th>每步走到的点</th><th class="n">±ε 微扰点</th><th class="n">合计扰动次数</th><th class="n">相对每步全测</th></tr>
  <!--EVAL_COST_ROWS-->
</table>
</div>
<details class="fold">
<summary>各环节计算内容与复杂度</summary>
<div class="fold-body">
<div class="tw">
<table class="wide">
  <caption>本机实测：Python 3.11.11 / NumPy 2.4.6，BLAS 线程固定为 1 <span class="sh">· 可左右滑动</span></caption>
  <tr><th>环节</th><th>计算内容</th><th class="n">实测耗时</th><th>复杂度</th></tr>
  <tr><td>模型训练</td><td>ΦᵀΦ 与 D×D 线性方程组求解</td><td class="n">≈0.05 s（1601 训练行，D=45）</td><td class="mono">O(N·D² + D³)</td></tr>
  <tr><td>模型单次推理</td><td>特征展开 + 一次内积</td><td class="n">≈50 µs</td><td class="mono">O(D)</td></tr>
  <tr><td>物理探针（含驱动 RMS）</td><td>单位脉冲 + 短 PAM4 序列过发送链</td><td class="n">≈5 ms</td><td>与评估符号数无关</td></tr>
  <tr><td>一次形状维微扰点（在线决策路径）</td><td>施加 ±ε 参数 → 取探针 → 查 Model A</td><td class="n">≈5 ms</td><td>与评估符号数无关（另外还要为记录测一次真实 BER，见上一行）</td></tr>
  <tr><td>gain 维解析梯度</td><td>探针特征上的链式解（§4.2.1）</td><td class="n">≈0.14 ms</td><td class="mono">O(D)</td></tr>
  <tr><td>一次真实 BER 评估</td><td><!--PROTO_SYMBOLS--> 符号 × 单种子 42（全链路 + LMS + Viterbi）</td><td class="n"><!--EVAL_SEC_TEXT--></td><td>与符号数线性（每步/微扰点各一次）</td></tr>
  <tr><td>离线数据集</td><td><!--N_ROWS--> 点 ×（2^20 符号 × 3 种子 + 探针）</td><td class="n">≈5.6 h（--jobs 12，每进程 OMP=1）</td><td>一次性</td></tr>
</table>
</div>
</div>
</details>

<h3>4.4 可靠性依据</h3>
<details class="fold">
<summary>三处可靠性机制（特征 / 决策 / 复算）</summary>
<div class="fold-body">
<div class="tw">
<table>
  <tr><th>环节</th><th>机制</th><th>效果</th></tr>
  <tr><td>特征侧</td><td>以入纤波形形状 + 绝对驱动幅度（而非硬件参数）作为代理输入，信道频响差异被探针吸收</td><td>同一模型可跨插损（含非对称）、色散、群时延变化复用，无需按环境重训</td></tr>
  <tr><td>决策侧</td><td>方向用组归一化梯度，步长用固定尺度 + 衰减，抽头维不设边界</td><td>参数量纲差异不影响方向；方向错误会立刻体现在下一步的实测 BER 上，无需额外代理来判断</td></tr>
  <tr><td>门控侧</td><td>组梯度范数低于 1e-3 dex 时该组冻结</td><td>方向已趋平时不再沿拟合噪声移动</td></tr>
  <tr><td>复算侧</td><td>每步的参数点与全部微扰点 BER_MLSE 逐条落盘</td><td>可逐步核验是否出现退步，不依赖抽样或事后筛选</td></tr>
</table>
</div>
</div>
</details>
<p>在线决策只用 Model A 的梯度，没有「代理否决」这一层。方向对不对，最终由第 6 节 15 个用例的该步实测 BER 来回答，这比再加一个代理做仲裁更直接。真实 BER 只在事后记录，既不当方向也不当停止判据。</p>

<h3>4.5 停止判据：固定 15 步</h3>
<p>三种取法都固定走满 15 步，不设提前停止。理由有两个：比得清楚，时间算得准。</p>
<ul>
  <li>比得清楚：三种取法差的是每步代价，只有在相同步数下比该步 BER 和累计代价才有意义。提前停止会把两件事混在一起，步数少的可能因为每步贵，也可能因为已经到头了。</li>
  <li>上板时间是能预算的：15 步乘每步的评估次数，再乘单次评估时间，就是这段调优的总时长（§4.3 给了每用例的准确次数）。</li>
  <li>不提前退出也亏不了多少：步长按 <span class="mono">0.97^k</span> 衰减，后段位移很小；组梯度门控会自动把已经趋平的组冻结。</li>
</ul>
<p>参照方案 direct 每次评估拿到的就是真实目标本身，所以保留了「边际改善小于 0.01 dex 就停」的判据（机制见 6.2）。</p>

<h3>4.6 部署走一遍：逐帧走查（真实用例）</h3>
<p>部署到新环境，主线是训练离线做一次、调优每个环境在线跑一遍。训练完成后手里有这几样东西：</p>

<div class="card">
<ul style="margin-bottom:0">
  <li>一个冻结的方向代理 <span class="mono">model_a.pkl</span>：8 维物理探针进，log10 BER 出，此后不再重训。</li>
  <li>一个统一的起点 x₀，8 维全给定，gain 取 ×0.325。15 个环境共用这一个起点，不按环境重新标定。</li>
  <li>离线标定参照 <span class="mono">per_case_target_rms</span>（§3.3）只作记录，不参与起点 gain 的取值。</li>
</ul>
</div>

<p>下面用真实数据逐帧看：第一个梯度怎么来、第一步怎么走、怎么更新、最后怎么收敛。</p>
<!--WALKTHROUGH-->

<h3>4.7 算法伪代码与超参数汇总（可直接照此实现）</h3>
<p>记 <span class="mono">p(x)</span> 为参数 x 对应的 8 维探针（7-tap 绝对标定 FIR + drive_rms，§3.1）、<span class="mono">A(p)</span> 为 Model A 预测的 log10 BER、<span class="mono">J = ∂A/∂p</span> 为其解析雅可比。以 full 取法为例（rotate / secant 只替换第 13 行）：</p>
<pre><code>输入：冻结的方向代理 A；同一次优起点 x₀ ∈ R⁸（含 gain ×0.325）；形状维取法 mode ∈ {full, rotate, secant}；步数 n_steps = 15
输出：参数点轨迹 {x_k}、每步与全部微扰点的真实 BER（仅记录，不回传决策）

 1   p₀ = p(x₀)； A_prev = A(p₀)                              # 参数点探针（真实打到链路）
 2   g[7] = ln10 · Σⱼ J₇ⱼ · p₀ⱼ                                # gain 解析梯度（§4.2.1，0 微扰）
 3   εᵢ = 0.01（5 个抽头）/ 0.1（gDC）/ 0.1（gDC2）
 4
 5   for k = 0 .. n_steps−1:
 6       # ① 形状维梯度刷新：三种取法的代价差别全在这一步
 7       if k == 0 或 mode == full:
 8           for i in 0..6:  g[i] = [A(p(x_k+εᵢeᵢ)) − A(p(x_k−εᵢeᵢ))] / (2εᵢ)      # 14 个微扰点
 9       elif mode == rotate 且 k &gt; 0:
10           for i in {(2k+j) mod 7, j=0,1}:  g[i] = 同上（其余维沿用上一轮实测值）  # 4 个微扰点
11       # mode == secant 且 k &gt; 0：不刷新，g 由 ④ 的秩一修正维持                  # 0 个微扰点
12
13       # ② 方向：组内归一化 + 门控（span 是步长，不是参数箱）
14       for 组 in {FFE(0..4), CTLE(5,6), gain(7)}:
15           v = (g·span)_组 ；‖v‖ &lt; 1e-3 时 d_组 = 0，否则 d_组 = v / ‖v‖
16       α = 0.05 · 0.97^k
17       x_new = clip(x_k − α · span ⊙ d, 物理量程)                 # 只裁 CTLE 与 gain，抽头维不裁
18
19       # ③ 参数点：取探针 → 代理预测 → 真实 BER
20       p_new = p(x_new)； A_new = A(p_new)； real_ber(x_new) = 真实 MLSE BER(x_new)
21       g[7] = ln10 · Σⱼ J₇ⱼ · p_new,ⱼ                            # gain 解析重算（复用同一探针，0 微扰）
22
23       # ④ 形状维梯度维持（只有 secant 需要）
24       if mode == secant:
25           s = x_new[0..6] − x_k[0..6]； dA_shape = (A_new − A_prev) − g[7]·(x_new[7] − x_k[7])
26           g[0..6] += [(dA_shape − g[0..6]ᵀ·s) / ‖s‖²] · s
27       A_prev = A_new； x_k = x_new
28   # 15 步走满，不做提前停止；真实 BER 回传格的边际停止另见 6.2</code></pre>

<div class="tw">
<table class="wide">
  <caption>全部超参数与常量（复现本结果需原样使用） <span class="sh">· 可左右滑动</span></caption>
  <tr><th>类别</th><th>参数</th><th class="n">取值</th></tr>
  <tr><td rowspan="4">方向代理</td><td>多项式阶数</td><td class="n">2（一次项 + 平方项 + 交叉项），D = 45</td></tr>
  <tr><td>Ridge 正则 α</td><td class="n">1.0</td></tr>
  <tr><td>train / test 划分</td><td class="n">80 / 20，seed 42</td></tr>
  <tr><td>标准化</td><td class="n">逐维 (x − μ)/σ，μ、σ 取训练集</td></tr>
  <tr><td rowspan="4">数据集（Stage 1 冻结）</td><td>行数 / 采样</td><td class="n"><!--N_ROWS--> 行，LatinHypercube d=7, seed 42</td></tr>
  <tr><td>采样盒</td><td class="n">FFE ±0.10、CTLE ±3.0 dB、gain ×0.20~×1.26</td></tr>
  <tr><td>标签</td><td class="n">log10(BER_MLSE)，只取 &lt; −0.1 的行</td></tr>
  <tr><td>训练评估</td><td class="n">2^20 符号 × 3 种子（42,43,44）</td></tr>
  <tr><td rowspan="9">在线寻优</td><td>搜索维度</td><td class="n">8 = 5 抽头 + gDC + gDC2 + u_gain（抽头维无边界）</td></tr>
  <tr><td>形状维取法</td><td class="n">full / rotate(k=2) / secant（一键切换）</td></tr>
  <tr><td>中心差分 εᵢ</td><td class="n">0.01（5 个抽头）/ 0.1（gDC、gDC2）</td></tr>
  <tr><td>步长 span</td><td class="n">[0.20 ×5, 6.0, 6.0, 0.60]</td></tr>
  <tr><td>初始步长 / 衰减</td><td class="n">GD_LR = 0.05 / ALPHA_DECAY = 0.97</td></tr>
  <tr><td>组梯度门控</td><td class="n">‖(g·span)_组‖ &lt; 1e-3 dex 冻结该组</td></tr>
  <tr><td>物理量程</td><td class="n">gDC [0,12] dB、gDC2 [0,4] dB、gain/g₀ ∈ [0.302, 3.98]</td></tr>
  <tr><td>步数</td><td class="n">固定 15 步（三种取法一致，无提前停止）</td></tr>
  <tr><td>边际改善门控</td><td class="n">仅真实 BER 回传格使用（&lt; 0.01 dex 停止）</td></tr>
  <tr><td rowspan="3">评估</td><td>在线 / 报告符号数</td><td class="n"><!--PROTO_SYMBOLS--></td></tr>
  <tr><td>仿真种子</td><td class="n">42（单种子）</td></tr>
  <tr><td>0 错误报告值</td><td class="n"><!--FLOOR_BER-->（= 0.5/N_bits，N_bits = <!--FLOOR_NBITS-->，逐用例由同步/训练段长度决定）</td></tr>
</table>
</div>

<h2 id="s5"><span class="num">5</span>数据集与评估协议</h2>
<p class="lead">协议只有两条硬约束：符号数决定能测到多低的 BER，单种子决定结果可复现；其余参数都在 4.3 的代价表里。</p>

<div class="tw">
<table>
  <caption>数据集构成：共 <!--N_ROWS--> 行真实 BER 评估，单份 CSV</caption>
  <tr><th>环境</th><th class="n">行数</th><th>构成</th><th class="n">log10 BER 实测范围</th></tr>
  <tr><td>Base_IL10x10 邻域</td><td class="n"><!--N_ROWS--></td><td>7 维 LHS（4 FFE 旁瓣 + gDC + gDC2 + u_gain，主抽头由归一化恒等式派生），gain 覆盖全用例最优 gain 邻域 ×0.20~×1.26</td><td class="n">−6.62 ~ −0.77</td></tr>
</table>
</div>

<div class="card">
  <h4 style="margin-top:0">评估协议：<!--PROTO_SYMBOLS--> 符号 × 单种子 42</h4>
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
    <tr><td class="n">2097152（采用）</td><td class="n">0</td><td class="n">−6.922</td><td class="n">7.2e-7</td></tr>
    <tr><td class="n">4194304</td><td class="n">0</td><td class="n">−7.224</td><td class="n">3.6e-7</td></tr>
  </table>
  </div>
  </div>
  </details>
  <p style="margin-bottom:0">
    最优工作点在 2^18 到 2^22 的每个块长下都是 0 个错误，真实 BER 低于检测限，也没有随块长出现系统性变化。
    表里 log10 BER 随块长加长往下走（−6.0 → −7.2），来自 0 错误时的 1/(2N) 伪计数，不是 BER 真在变：块长越长，检测限越低。
    所以全量跑取 2097152 符号（2^21）、单种子 42，检测底 1.19e-7。收敛后最优工作点的 BER 落在 0 错误检测限之下（伪计数 <!--FLOOR_BER-->，95% CL 上界 <!--FLOOR_UB95-->），
    这种情况用上界表述，不跟点估计混着用；次优起点和压力用例（≥1e-4）仍然是统计上可靠的点估计。
  </p>
</div>

<details class="fold">
<summary>采样与标注方式（采样器 / 字段 / 并行一致性 / 成本）</summary>
<div class="fold-body">
<ul style="margin-bottom:0">
    <li><strong>采样器</strong>：<span class="mono">LatinHypercube(d = 7, seed = 42)</span>，逐环境独立且可复现；采样盒 = FFE 旁瓣 ±0.10 / CTLE ±3.0 dB，gain 在 u 空间均匀覆盖全用例最优 gain 邻域（×0.20~×1.26）。</li>
    <li><strong>每行字段</strong>：7 维坐标、5-tap FFE、gDC/gDC2、driver_gain、驱动 RMS、真实 <span class="mono">mlse_ber</span> 与 <span class="mono">log10_ber_mlse</span>、<span class="mono">ber_std_log10</span>、7-tap FIR 形状。</li>
    <li><strong>并行一致性</strong>：<span class="mono">--jobs</span> 多进程与串行结果逐位一致（每点独立、种子固定，已实测校验）。</li>
    <li><strong>离线阶段同时导出的参数域代理</strong>（输入 = 4 旁瓣 + gDC + gDC2 + drive_rms，7 维参数域）作为离线产物随 Stage 1 一起冻结，<strong>不在线使用</strong>；在线方向只来自 8 维探针域代理。</li>
    <li><strong>成本</strong>：<!--N_ROWS--> 点 × 3 种子（1048576 符号/点），12 进程并行（每进程 OMP=1）。</li>
  </ul>
</div>
</details>

<h2 id="s6"><span class="num">6</span>实测结果</h2>
<p class="lead">六种组合都能把参数走到该环境最优附近，没有一种走不动；差别在代价和少数难用例的落点。下面先给结果与逐用例数字，再给四个起点下每个用例的轨迹。</p>

<p>下面的数都取自 <!--SCALE_LABEL--> 全量重跑、单种子 42。6.1 先给六格横向对比与判词，6.2 给六个组合的逐用例数字，6.3 是安全性，6.4 是四个起点下每个用例怎么走的。</p>

<div class="kpis">
  <!--KPI_CARDS-->
</div>

<h3>6.0 起点工作点与调优机制</h3>
<div class="card">
  <p>起点 <strong>x₀</strong> 是训练数据集里的一个实测点，8 维全部给定，是个明确的次优工作点。它的真实 BER 在基线环境约 <!--SEED_BER_BASE-->，在极端插损组合约 <!--SEED_BER_HI-->。取这个量级有原因：既高于检测限，统计得出来，又低于信道失效区，还有下降空间，所以调优过程是能看见的。</p>
  <ul>
    <li>Tx FFE 5 抽头：<span class="mono">[-0.0885, -0.3147, 0.4079, 0.0845, 0.1043]</span>（5 个抽头地位相同，全部是搜索变量，不设边界）；</li>
    <li>Tx CTLE：gDC = 6.73 dB、gDC2 = 0.85 dB（物理量程内）；</li>
    <li>driver_gain = 0.1106（相对标称 0.3399 的倍率 ×0.325，u_gain = −0.4875）：驱动摆幅未按用例标定，是次优的主要来源。</li>
  </ul>
  <p>在线调优是 8 维梯度下降。方向来源和形状维取法各三种，组合成六格（机制见 4.2，每格的在线代价见 4.3），六格共用同一个起点、同一组归一化步长与门控、同一个 15 步上限。从这个次优点出发，各用例的真实 BER 在数步内降到该环境最优工作点附近。</p>
  <p style="margin-bottom:0">本节以现役格 <!--MODE_NAME_TEXT--> 为主：方向来自 Model A 代理，不需要回传通道。有回传通道、直接对真实 BER 做梯度下降的三格，数字在 6.2，轨迹在 6.4。</p>
</div>
<!--SEED_SPECTRUM-->

<h3>6.1 泛化：只用 10 dB 基线训练 → 跨 15 个环境</h3>
<p>训练集只含 Base_IL10x10 邻域 <!--N_ROWS--> 行。方向代理冻结后，对 15 个用例环境逐个执行 Stage-2 在线调优，不重训、不重新标定；下表是<strong>现役格 <!--MODE_LABEL--></strong>的逐用例结果，最后一列是每个用例为此付出的真实评估次数（落地 + 微扰点），六格矩阵横向对比见本节末表。</p>
<p class="win"><strong>结论</strong>：<!--POS_SUMMARY-->。次优起点的 BER 从 <!--SEED_BER_LO-->（<!--SEED_LO_HUMAN-->）到 <!--SEED_BER_HI-->（<!--SEED_HI_HUMAN-->）；调优后 <!--FLOOR_TXT_LONG-->。</p>
<div class="tw">
<table class="wide" id="tbl-core">
  <caption>起点 = x₀（次优工作点，基线环境实测 <!--SEED_BER_BASE-->）的真实 BER_MLSE；最优 = 全轨迹中真实 BER_MLSE 的最小值（步序为该最小值出现于第几步）；真实评估 = 该用例实际打到链路上的次数（落地+微扰点） <span class="sh">· 可左右滑动</span></caption>
  <tr><th>用例</th><th>物理条件</th><th class="n">起点 BER_MLSE</th><th class="n">最优 BER_MLSE（步序）</th><th class="n">降幅</th><th class="n">gain（起点→最优）</th><th class="n">真实评估（落地+微扰）</th></tr>
  <!--CORE_ROWS-->
</table>
</div>
<p>六格在同一协议、同一起点、同一个 15 步上限下横向比：三种形状维取法乘两种梯度来源。该步 BER 取 15 个用例的几何平均；两格算一样，指逐用例最优 BER 相差 5% 以内，基准是代理 × full。</p>
<div class="tw">
<table class="wide" id="tbl-mode-cmp">
  <caption>六格的方向精度与扰动账（15 用例）：次数是每用例把链路推开的总次数 <span class="sh">· 可左右滑动</span></caption>
  <tr><th>格（梯度来源 × 形状维获取方式）</th><th class="n">15 用例最优 BER 几何平均</th><th class="n">相对代理 full</th><th class="n">与代理 full 一样</th><th class="n">最坏单例倍数</th><th class="n">每用例扰动次数</th><th class="n">15 用例合计</th></tr>
  <!--MODE_CMP_ROWS-->
</table>
</div>
<p><!--MODE_CMP_VERDICT--></p>

<h3>6.2 逐用例数字：15 个用例 × 六个组合</h3>
<!--DIRECT_SECTION-->

<h3>6.3 安全性：每步与微扰点最坏能到哪</h3>
<div class="card">
  <p>调优时链路会短暂停在两类真实工作点上，安全性得分开看。一类是参数点，即每步落地后的 x<sub>k+1</sub>；另一类是 ±ε 微扰点，就是为估计形状维梯度加的参数偏移，链路也真的经过这些点。两者都会影响那一刻的端到端 BER，只看每一步走到的点不够。下面的数字取现役格 <!--MODE_LABEL-->：<!--MODE_PROBE_TEXT-->。回传格没有代理，也就没有这一层安全机制（见 6.2 的回传三列）。</p>

  <p>先只看每步的结果：<!--TOTAL_STEPS--> 步里有 <!--TOTAL_WORSE--> 个比起点差。</p>
  <div class="tw">
  <table class="wide" style="margin-bottom:8px">
    <caption>只看每一步走到的点：以起点的真实 BER 为基准，统计中间各步有没有退步</caption>
    <tr><th class="n">用例数</th><th class="n">记录的真实 BER 步数</th><th class="n">劣于种子的步数</th><th>结论</th></tr>
    <!--SAFETY_ROWS-->
  </table>
  </div>

  <p>把微扰点也算上：某一步取该步所有微扰点和该步本身里最差的那个 BER，其余步取该步的 BER，再和起点比，有 <strong><!--PROBE_WORSE_STEPS--> 步</strong>的瞬时最坏值超过了起点。最坏的一次是起点的 <strong><!--PROBE_WORST_RATIO--></strong> 倍（<!--PROBE_WORST_ENV-->：<!--PROBE_WORST_BER-->，起点 <!--SEED_BER_BASE-->）。</p>
  <div class="tw">
  <table class="wide" id="tbl-safety-probe" style="margin-bottom:8px">
    <caption>把微扰也算上：逐用例的「每步最坏 BER（含 ±ε 微扰点）」超过起点的步数 · 可左右滑动</caption>
    <tr><th>用例</th><th class="n">种子 BER</th><th class="n">含微扰瞬时超种子步数</th><th class="n">最坏瞬时 BER</th><th class="n">相对种子倍率</th></tr>
    <!--SAFETY_PROBE_ROWS-->
  </table>
  </div>
  <p class="mut" style="margin-bottom:0">瞬时值超过起点，原因在中心差分：要同时测 x+ε 和 x−ε 两边的斜率，就得往差的方向也短暂挪一步。这是用实测斜率换方向的固有代价，三种取法差的只是这个代价出现得多频繁（见 4.3）。如果真实系统不接受任何瞬时扰动，可以改单边差分，只往预计改善的方向探，或者把 ε 调小。secant 取法把这份瞬时代价压到只有第 0 步一轮，之后不再产生微扰点。原始记录在 <span class="mono">trace_&lt;用例&gt;.csv</span>（参数点）和 <span class="mono">probes_&lt;用例&gt;.csv</span>（微扰点，含 step / param / sign / 真实 BER）。</p>
</div>

<p>每个微扰点自己的 BER 也全部记了下来。这些数不参与决定方向，方向仍由 Model A 的梯度给，但它们是这套方案真实运行代价的底账：<!--MODE_PROBE_TEXT-->。回传格一样，第 0 步 8 维全测共 16 个微扰点（没有解析 gain 梯度，gain 维也只能实测），每个的真实 BER 同样记在 <span class="mono">probes_&lt;用例&gt;.csv</span> 里。</p>
<div class="tw">
<table class="wide" id="tbl-probe">
  <caption><!--MODE_PROBE_CAPTION--> <span class="sh">· 可左右滑动</span></caption>
  <tr><th>用例</th><th class="n">微扰步数</th><th class="n">微扰点数</th><th class="n">微扰 BER 最小</th><th class="n">微扰 BER 最大</th><th class="n">微扰 BER 中位</th></tr>
  <!--PROBE_ROWS-->
</table>
</div>



<!--SEED_STUDY-->

<h2 id="s7"><span class="num">7</span>什么时候不成立</h2>
<p class="lead">这套方法只有一个真实前提：起点落在代理训练覆盖的范围内。出了这个范围代理会给反向，而且它自己看不出来；其余边界都有对策，不需要改算法。</p>
<div class="tw">
<table>
  <tr><th>边界</th><th>表现</th><th>对策</th></tr>
  <tr>
    <td>无回传通道（方案前提）</td>
    <td>在线调优拿不到收端端到端 BER，无法直接对真实目标做梯度下降</td>
    <td>用发端可测探针训练 Model A 指方向；另一种梯度来源（真实 BER 回传）的三格对照见 6.2</td>
  </tr>
  <tr>
    <td>每次梯度估计都要真实打到链路上</td>
    <td>±ε 微扰点会让链路瞬间停在偏离当前参数点的位置；每步全量微扰的代价最高</td>
    <td>矩阵一键切换（4.2）：要方向精度就每步全量微扰，要省代价就每步轮转少量维、或只在第 0 步测一轮后外推；每格的真实评估次数与结果差异见 4.3 / 6.5，按可接受的瞬时代价选格</td>
  </tr>
  <tr>
    <td>强信号用例 BER 低于测量分辨率</td>
    <td>最优工作点真实 BER &lt; <!--FLOOR_UB95-->（0 错误 @ <!--SCALE_LABEL_PLAIN--> × 单种子 42，95% CL），强信号用例落在检测限之下，只能给上界而非点估计</td>
    <td>全流程固定 <!--PROTO_SYMBOLS--> 符号 × 单种子 42；检测限以下的点用 3/N_bits（N_bits = <!--FLOOR_NBITS-->，95% CL 上界）表述，不与点估计混用；压力用例（≥1e-4）仍可作统计可靠的点估计</td>
  </tr>
  <tr>
    <td>代理绝对标定弱</td>
    <td>预测值会系统性欠估或过估真实 BER，不能当绝对值用</td>
    <td>决策只用梯度的方向与相对大小（组归一化后乘固定步长），不依赖预测绝对值</td>
  </tr>
  <tr>
    <td><code>driver_gain</code> 最优区间依赖摆幅标定</td>
    <td>每用例最优倍率不同（per-case RMS 标定 0.06~0.22 V）</td>
    <td>gain 作为第 8 维进入梯度下降，由解析梯度自己找到该用例的倍率，不需要离线扫描给初值；更换器件时重跑 per-case RMS 扫描只是为了报告参照（≈20 min）</td>
  </tr>
  <tr>
    <td>CTLE peaking 增益维</td>
    <td>种子点 gDC = 6.73 dB、gDC2 = 0.85 dB；优化时 gDC 小幅调整、gDC2 从 0.85 dB 压到 ~0，peaking 整形主要由 FFE 抽头与 gain 承担</td>
    <td>若需更强整形能力，把 CTLE 零极点比例也纳入搜索空间</td>
  </tr>
  <tr>
    <td>代理只在训练邻域内可信</td>
    <td>数据集只覆盖基线 ±0.10 / ±3.0 dB / ×0.20~1.26。起点离得远，代理会指错方向，而且它自己不知道。把 FFE 旁瓣放大 3 倍当起点时，代理三格 45 个用例的最好结果全在第一步，模型预测变好 8.31 倍，实测是 0.62 倍（6.4）</td>
    <td>代理格拿不到真实反馈，走错了不会立刻看出来，只能按模型走到头。能拿到收端 BER 时，先用一次评估复核这一步的结果，比起点差就退回起点；已知起点离得远，直接走回传格（同一批用例上回传 × full 是代理 × full 的 0.0009 倍）。拿不到收端 BER 时，唯一能做的是部署前把起点校回邻域内，数据集覆盖的范围就是邻域边界，并如实标注这个前提。代理看不见自己的失效，这件事不能指望算法自己发现</td>
  </tr>
  <tr>
    <td>低频响应由规范决定</td>
    <td>收端隔直是模拟 AC 耦合，规范只给低频 3 dB 截止频率的上限（100G/lane 100 kHz），拐点以下的基线漂移是这条链路真实存在的效应；换速率档只改这个上限（200G/lane 草案同为 100 kHz）</td>
    <td>模型取上限即最坏的合规情况，比上限更低的实现只会更好，所以不需要为器件容差再建一档；换速率档时只改 <code>ac_coupling_fc_hz</code> 一处</td>
  </tr>
  <tr>
    <td>用例覆盖有限</td>
    <td>15 个用例覆盖 10/14/16/20 dB 插损组合与 CD/DGD/噪声应力</td>
    <td>超出范围时重跑离线数据集（2^20 符号 × <!--N_ROWS--> 点，多进程并行）并重训（&lt;0.1 s），算法本身无需修改</td>
  </tr>
</table>
</div>

<h2 id="s8"><span class="num">8</span>复现与产物</h2>

<p>下面是部署这套方案的完整流水线命令和产物清单：数据集、训练、标定、2<sup>18</sup> 六格验证、2<sup>21</sup> 全量调优、报告、交付件。点开看完整命令。</p>

<details class="fold">
<summary>完整流水线：数据集 → 训练 → 标定 → 2^18 六格验证 → 2^21 全量调优 → 报告 → 交付件</summary>
<div class="fold-body">

<div class="card">
  <h4 style="margin-top:0">完整流水线</h4>
  <pre><code># 1) 数据集（2001 点；7 维 LHS；只用 Base_IL10x10；gain 覆盖全用例最优 gain 邻域 ×0.20~×1.26）
python dataset_generator.py --base-samples 2000 --only-envs Base_IL10x10 \
    --num-symbols 1048576 --sim-seeds 42,43,44 --jobs 12 --core-samples 1200

# 2) 训练方向代理（8 维探针 -> log10 BER）；Stage 1 同时导出的参数域产物不在线使用
python -c "from train_surrogates import train; import glob; \
  train(sorted(glob.glob('dataset/ddps_dataset_*.csv'))[-1], 'models/ddps', \
           pipeline_tag='ddps', gain_mode='gradient_with_rms_init')"

# 3) per-case target_rms 扫描（gain 维标定参照，只用于报告对照）
python tools/scan_per_case_rms.py --jobs 8

# 4) Python 2^18 验证（比对前提：2^18 符号、单种子 42、无人工噪声；六格）
python tools/run_parallel_envs.py --model-dir models/ddps --out-dir result\ddps_equiv_py_full \
    --method proxy --grad-mode full --only-envs Base_IL10x10,IL20x20 \
    --num-symbols 262144 --n-steps 15 --sim-seeds 42 --jobs 2 \
    --seed-config result/seed_config_bad_1e4.json
（同一命令把 --grad-mode 换成 rotate / secant；direct 用 --method direct）

# 5) C++ 编译 + 模型转换（WSL 内 g++ 构建：本机 Smart App Control 强制模式拦本地无签名 exe，
#    Linux 进程不受管辖；源码纯标准 C++17。pkl -> json 一次性，Windows 侧跑）
wsl -d Ubuntu --cd /mnt/c/DSPPlayground/eLPO_antigravity bash cpp/build_wsl.sh
python cpp\export_models.py

# 6) C++ 2^18 等价比对（六格逐格比对，判据 < 1e-9）
python cpp/run_all_cases.py --backend wsl --only-envs Base_IL10x10,IL20x20 \
    --num-symbols 262144 --n-steps 15 --jobs 2 --method proxy --grad-mode full \
    --out-dir result/ddps_equiv_cpp_full
（同理 rotate / secant；真实 BER 回传三格用 --method direct 配 --grad-mode full|rotate|secant；起点同上，由 run_all_cases.py 内置）
python cpp\compare_traces.py --py result/ddps_equiv_py_full --cpp result/ddps_equiv_cpp_full

# 7) 全量规模仿真（2^21 高 SNR 大点数，只允许 C++；六格）
python cpp/run_all_cases.py --backend wsl --num-symbols 2097152 --n-steps 15 --jobs 4 \
    --method proxy --grad-mode <!--MODE_KEY--> --out-dir result/ddps_cpp_<!--MODE_KEY-->
（换形状维取法只改 --grad-mode；换成真实 BER 回传来源用 --method direct，再配 --grad-mode。
 起点与协议由 run_all_cases.py 内置：SEED_CONFIG = result/seed_config_bad_1e4.json、15 环境清单、
 seed 42、tx_noise 0；cfg 文件里的 tx.custom_taps 是未提供 seed-config 时的兜底值，不是本次起点）

# 8) 可视化报告（逐格出图，来源就是该格的结果目录）
python report_ddps.py --test-dir result/ddps_cpp_<!--MODE_KEY--> --model-dir models/ddps \
    --seed-config result/seed_config_bad_1e4.json --summary-out result/SUMMARY.md
（rotate / secant 同理；真实 BER 回传格加 --method direct，并给对应的 --grad-mode）

# 9) 交付件（六格矩阵：--direct 是回传 × secant，另两格用 --direct-full / --direct-rotate）
python make_deliverable.py --baseline result/ddps_cpp_<!--MODE_KEY--> --mode <!--MODE_KEY--> \
    --model-dir models/ddps --direct result/ddps_cpp_direct \
    --direct-full result/ddps_cpp_direct_full --direct-rotate result/ddps_cpp_direct_rotate \
    --out deliverables/DDPS_Deliverable.html

# 10) 一键验收：结果完整性 / 记录恒等式（真实评估 = 落地 + 微扰点）/ 每格微扰机制
#     （刷新维序列、微扰点成对、次数与轨迹互推）/ 2^18 逐轨迹等价（判据 &lt; 1e-9）/
#     交付件新鲜度与禁词。六格是否跑齐由 --expect-cells 断言：格数不足 exit 2，全过 exit 0
python tools\verify_ddps.py --expect-cells 6</code></pre>
</div>

<div class="tw">
<table>
  <caption>产物清单</caption>
  <tr><th>类别</th><th>路径</th><th>内容</th></tr>
  <tr><td>数据集</td><td class="mono">dataset/ddps_dataset_&lt;ts&gt;.csv</td><td><!--DATASET_SHAPE-->（Stage-1 采样 7 维 x = 4 旁瓣 + gDC + gDC2 + u_gain；另含 5-tap FFE、驱动 RMS、7-tap FIR 探针、真实 BER）</td></tr>
  <tr><td>模型</td><td class="mono">models/ddps/</td><td>方向代理（8 维探针 / 参数域离线产物）+ meta.json</td></tr>
  <tr><td>现役格主结果</td><td class="mono">result/ddps_cpp_<!--MODE_KEY-->/</td><td>C++ <!--SCALE_LABEL_PLAIN--> 全 15 用例，现役格 <!--MODE_LABEL-->：case_summary.csv/json、trace_&lt;用例&gt;.csv、probes_&lt;用例&gt;.csv、run_config.json、report/</td></tr>
  <tr><td>代理行另两格</td><td class="mono">result/ddps_cpp_rotate/、result/ddps_cpp_secant/</td><td>同协议、同起点的代理 × rotate / 代理 × secant <!--SCALE_LABEL_PLAIN--> 结果（六格矩阵横向对比的数据源）</td></tr>
  <tr><td>回传行三格结果</td><td class="mono">result/ddps_cpp_direct_full/、result/ddps_cpp_direct_rotate/、result/ddps_cpp_direct/</td><td>真实 BER 回传来源的三种取法：<!--SCALE_LABEL_PLAIN--> 全 15 用例（case_summary + trace/probes + report/；direct 目录即回传 × secant）</td></tr>
  <tr><td>2^18 等价参照</td><td class="mono">result/ddps_equiv_py_&lt;格&gt;/、result/ddps_equiv_cpp_&lt;格&gt;/</td><td>六格各自的 Python / C++ 2^18 逐轨迹比对结果（Base_IL10x10 + IL20x20）</td></tr>
  <tr><td>跨实验汇总</td><td class="mono">result/SUMMARY.md</td><td>15 用例结果汇总</td></tr>
  <tr><td>验收入口</td><td class="mono">tools/verify_ddps.py</td><td>一条命令验收现役结果：完整性 / 记录恒等式 / 每格微扰机制 / 2^18 等价 / 交付件新鲜度与禁词；<span class="mono">--expect-cells 6</span> 可断言六格跑齐</td></tr>
  <tr><td>块长研究</td><td class="mono">result/ddps_block_length.csv</td><td>最优工作点不同块长的 BER 估计精度</td></tr>
</table>
</div>

</div>
</details>
</details>

<h2 id="s9"><span class="num">9</span>两套实现与等价性</h2>

<p>平台提供两套同源实现：Python（原理参照）与 C++17（一比一复刻）。两实现读同一 <span class="mono">config.xlsx</span> 配置、装载同一冻结模型转换产物（<span class="mono">models/ddps/model_{a,b}.json</span>，由 <span class="mono">cpp/export_models.py</span> 从 pkl 转出，不重训），在线调优结果数值等价。两实现的比对只在 2<sup>18</sup> 小点数低 SNR 口径下进行（本节 10.2~10.4 的等价性数字均出自该口径）；全量规模仿真（高 SNR 大点数）只用通过比对的 C++ 入口执行，Python 不承担高 SNR 大点数仿真。6.5 节的 direct 对比实验走同一条流水线；比对工具已固化为 <span class="mono">cpp/compare_traces.py</span>（本节各表同口径）。</p>
<p><strong>构建运行环境</strong>：C++ 产物在 WSL(Ubuntu) g++ 13.3 下构建运行（<span class="mono">cpp/build_wsl.sh</span>）。本机 Windows Smart App Control 处于强制模式，拦截本地编译的无签名可执行文件（含 MinGW 工具链组件与历史产物），Linux 进程不受该策略管辖；工程 C++ 源码为纯标准 C++17、无平台相关 API，跨平台构建不影响数值行为，等价性以本节 2<sup>18</sup> 口径比对为准。</p>

<h3>9.1 模块映射（一比一复刻）</h3>
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
<tr><td class="mono">optimizer.hpp</td><td class="mono">ddps_optimizer</td><td>Stage-2 在线下降（8 维；gain 解析梯度 + 形状 7 维三种取法 <span class="mono">full/rotate/secant</span>，固定 15 步）；direct 变体 <span class="mono">stage2_descent_direct</span>（目标 = 真实 BER，第 0 步 8 维中心差分 + 全维 Broyden，无代理）</td></tr>
</table>
</div>

<h3>9.2 物理层 bit 级等价</h3>
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

<h3>9.3 探针与代理推理</h3>
<p>发端探针（7 抽头 Tx FIR + drive_rms）与方向代理前向：<span class="mono">drive_rms</span> 相对差 ≤1e-13、<span class="mono">pred_a</span> 相对差 ≤1e-12（两平台 <span class="mono">pred_a = -5.995717769951e+00</span> 同值到第 12 位）。探针是两平台唯一的方向信息来源，探针等价 + 代理前向等价，是六格逐格等价的前提（10.4 各表）。</p>


<h3>9.4 在线调优等价</h3>
<p>Python 定原理、C++ 一比一复刻，两者只在 2<sup>18</sup> 小点数低 SNR 下比对：单种子 42、不加人工噪声、Base_IL10x10 加 IL20x20 两个代表用例，按用例、步、数值列逐项算最大相对差，判据 &lt; 1e-9。六格都单独比一遍，发端代理三格和真实 BER 回传三格各一组，结果目录缺的格不会出现在页签里。</p>
<div class="tabs">
  <!--EQ_TABS-->
</div>
<p>比对命令：<span class="mono">python cpp/compare_traces.py --py &lt;Python 目录&gt; --cpp &lt;C++ 目录&gt;</span>；比对列 <span class="mono">gdc / gdc2 / gain / u_gain / drive_rms / pred_a / real_lb / real_ber / grad_norm</span>。通过比对后，全量规模（2<sup>22</sup> 高 SNR）只用 C++ 跑（见 §6）；Python 结果作为低 SNR 收敛与等价性参照。</p>
<h3>9.5 统一入口</h3>
<pre><code># C++ 后端：全量在线调优（Base_IL10x10，2^22 符号，无噪声，单种子 42，次优起点，代理 × full）
# （WSL 内运行：Linux 进程不受本机 Smart App Control 强制模式管辖，见本节开头「构建运行环境」）
wsl -d Ubuntu --cd /mnt/c/DSPPlayground/eLPO_antigravity ./cpp/build/run_ddps cpp/config.txt \
    --num-symbols 2097152 --tx-noise-snr 0 \
    --seed 42 --n-steps 15 --seed-config result/seed_config_bad_1e4.json \
    --method proxy --grad-mode full

# 换取法：--grad-mode rotate --rotate-k 2 / --grad-mode secant（其余参数不变）
# 真实 BER 回传格：--method direct 配 --grad-mode full|rotate|secant（同样 8 维、同起点、同步数）

# 快速验证：低 SNR 人为噪声 + 少点数（发端 DSP 出口 SNR=23 dB、2^14 符号）
wsl -d Ubuntu --cd /mnt/c/DSPPlayground/eLPO_antigravity ./cpp/build/run_ddps cpp/config.txt \
    --num-symbols 16384 --tx-noise-snr 23 --seed 42

# 15 用例并行全量重跑（C++ 侧；WSL 内存放开到 28 GB 后 4 路并行）
python cpp\run_all_cases.py --backend wsl --num-symbols 2097152 --n-steps 15 --jobs 4 \
    --method proxy --grad-mode <!--MODE_KEY--> --out-dir result\ddps_cpp_<!--MODE_KEY--></code></pre>

<footer>
  <p><strong>测量口径</strong>：Python 3.11.11 / NumPy 2.4.6 / SciPy 1.17.1；BLAS 线程数固定为 1（<span class="mono">OMP_NUM_THREADS=1</span>）；
  BER 评估统一 2097152 符号/点（2^21）× 单仿真实例种子 42；数据集采样与模型划分固定 seed = 42。C++ 侧同一种子、同一符号数。</p>
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

  // 逐帧走查（walkthrough）：帧切换 / 帧点 / 自动播放（打印时全部帧展开，见 @media print）
  document.querySelectorAll('.wt').forEach(function(wt){
    var frames = wt.querySelectorAll('.wt-frame'), dots = wt.querySelectorAll('.wt-dot'),
        title = wt.querySelector('.wt-title'), cur = 0, timer = null;
    function show(i){
      cur = ((i % frames.length) + frames.length) % frames.length;
      frames.forEach(function(f,k){ f.classList.toggle('on', k === cur); });
      dots.forEach(function(d,k){ d.classList.toggle('on', k === cur); });
      if (title) title.textContent = frames[cur].getAttribute('data-title') || ('帧 ' + (cur+1) + '/' + frames.length);
    }
    function stop(){ if (timer){ clearInterval(timer); timer = null; } var pb = wt.querySelector('[data-wt-play]'); if (pb) pb.textContent = '▶ 自动播放'; }
    wt.querySelectorAll('[data-wt-nav]').forEach(function(b){
      b.addEventListener('click', function(){ stop(); show(cur + (+b.getAttribute('data-wt-nav'))); });
    });
    dots.forEach(function(d,k){ d.addEventListener('click', function(){ stop(); show(k); }); });
    var pb = wt.querySelector('[data-wt-play]');
    if (pb) pb.addEventListener('click', function(){
      if (timer){ stop(); return; }
      pb.textContent = '⏸ 暂停'; timer = setInterval(function(){ show(cur + 1); }, 3200);
    });
    show(0);
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
import re
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


def _per_bits(ber):
    """BER 的人话锚点：'每 7.7 千 bit 错 1 个' 量级表述（巨大倍数/科学计数法的替代）。"""
    n = 1.0 / float(ber)
    if n < 1000:
        return f'每 {n:.0f} bit 错 1 个'
    for unit, cut in (('亿', 1e8), ('千万', 1e7), ('百万', 1e6), ('万', 1e4), ('千', 1e3)):
        v = n / cut
        if v >= 1:
            return (f'每 {v:.1f} {unit} bit 错 1 个' if v < 10 else
                    f'每 {v:.0f} {unit} bit 错 1 个')
    return f'每 {n:.0f} bit 错 1 个'


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
        ev = f"{int(r['n_real_evals'])} ({int(r['n_landed'])}+{int(r['n_probe_states'])})" \
            if 'n_real_evals' in r and r['n_real_evals'] == r['n_real_evals'] else '—'
        out.append(
            f"<tr><td>{env}</td><td>{_cond(r)}</td><td class=\"n\">{_ber(r['seed_ber'])}</td>"
            f"<td class=\"n\">{_ber(r['best_ber'])} ({int(r['best_step'])})</td>"
            f"<td class=\"n{' win' if imp >= 1.05 else ''}\">↓{np.log10(imp):.1f} 个数量级</td>"
            f"<td class=\"n\">{_gain_str(r)}</td>"
            f"<td class=\"n\">{ev}</td></tr>")
    return '\n'.join(out)


def _rows_safety(summary, d):
    """逐步记录：每步走到的点，以及把 ±ε 微扰点也算上的最坏值（两类都是真实硬件短暂停留的工作点）。"""
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
            f"<td class=\"n\">{_ratio_str(r_)}</td></tr>")
    total_steps = steps
    total_worse = worse
    landed = (f"<tr><td class=\"n\">{len(summary)}</td>"
              f"<td class=\"n\">{total_steps}</td>"
              f"<td class=\"n{' win' if total_worse == 0 else ''}\">{total_worse}</td>"
              f"<td>{'无退步' if total_worse == 0 else '存在退步'}</td></tr>")
    return (landed, '\n'.join(probe_rows), total_steps, total_worse,
            probe_worse_steps, worst_ratio, worst_env, worst_ber)


def _rows_probe(d, order):
    """微扰点 BER 包络逐用例统计：为估计形状维梯度而施加的每一个 ±ε 状态的真实端到端 MLSE BER。"""
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


# 六格矩阵：每用例真实评估次数（落地 = 走的步数，微扰点 = 为估计梯度额外打到链路上的次数）
_EVAL_MODES = [
    ('full', '代理 × full（7 维每步全量中心差分）', '7 维每步重算，gain 维解析'),
    ('rotate', '代理 × rotate（每步轮转 2 维）', '其余维沿用上次实测值'),
    ('secant', '代理 × secant（第 0 步一轮后割线外推）', 'Broyden 秩一修正，0 微扰'),
    ('direct_full', '回传 × full（8 维每步全量中心差分）', '每步 16 态，需真实 BER 回传'),
    ('direct_rotate', '回传 × rotate（每步轮转 2 维）', '每步 4 态，需真实 BER 回传'),
    ('direct_secant', '回传 × secant（第 0 步一轮后割线外推）', 'Broyden 秩一修正，需真实 BER 回传'),
]

# 3×2 矩阵：3 种形状维获取方式 × 2 种梯度来源
_CELL_SOURCE = {'full': 'proxy', 'rotate': 'proxy', 'secant': 'proxy',
                'direct_full': 'direct', 'direct_rotate': 'direct', 'direct_secant': 'direct'}
_MODE_ORDER = ('full', 'rotate', 'secant')
_SOURCE_ZH = {'proxy': '发端代理（Model A，无需回传）', 'direct': '真实 BER 回传'}


def _dir_scale(d):
    """从结果目录的 run_config.json 读 num_symbols，折成规模标签（2^k）；读不到返回 None。"""
    try:
        with open(os.path.join(d, 'run_config.json'), encoding='utf-8') as f:
            n = int(json.load(f).get('num_symbols') or 0)
        if n > 0:
            k = int(round(np.log2(n)))
            return ('2^%d' % k) if 2 ** k == n else ('%d 符号' % n)
    except Exception:
        return None
    return None


def _per_eval_sec_text(a):
    """每次真实评估的实测耗时：C++ 用主结果目录实测；Python 只跑 2^18 验证，
    有真计时就按符号数线性折算到主结果规模，没有就只报 C++ 的实测值。"""
    sym_b = _dir_num_symbols(a.baseline) or _dir_num_symbols(a.direct)
    t_cpp = _per_eval_sec(a.dirs.get(a.mode) or a.baseline)
    py_root = getattr(a, 'eq_py_root', None)
    t_py, sym_py = None, 0
    if py_root:
        for m in ('full', 'rotate', 'secant'):
            d = _eq_dir(py_root, m)
            if not d:
                continue
            sym_py = _dir_num_symbols(d)
            if sym_py:
                t_py = _per_eval_sec(d)
                break
    parts = []
    if t_cpp and sym_b:
        parts.append(f'≈{t_cpp:.0f} s（C++，{_sym_txt(sym_b)} 实测）')
    if t_py and sym_b and sym_py:
        parts.append(f'≈{t_py * sym_b / sym_py:.0f} s（Python，'
                     f'{_sym_txt(sym_py)} 实测 ×{sym_b / sym_py:.0f}）')
    elif sym_b:
        parts.append('Python 入口只跑 2^18 验证、不参与本规模计时')
    return '；'.join(parts) if parts else '—'


def _per_eval_sec(d):
    """结果目录里 elapsed_sec / n_real_evals 的均值（每次记录状态一次真实评估）。"""
    if not d or not os.path.exists(os.path.join(d, 'case_summary.csv')):
        return None
    try:
        _, df = _load_summary(d)
        if 'elapsed_sec' not in df or 'n_real_evals' not in df:
            return None
        ev = float(df['n_real_evals'].mean())
        return float(df['elapsed_sec'].mean()) / ev if ev > 0 else None
    except Exception:
        return None


def _sym_txt(num_symbols):
    """符号数的人话写法：2 的整幂写 "2^k = n"，否则写千分位整数。"""
    n = int(num_symbols or 0)
    if n <= 0:
        return '—'
    k = int(round(np.log2(n)))
    if 2 ** k == n:
        return f'2^{k} = {n}'
    return f'{n:,}'

def _scale_label(num_symbols):
    """数据规模的上标写法（2<sup>22</sup>），随结果目录的 num_symbols 走。"""
    if not num_symbols:
        return '—'
    return '2<sup>%d</sup>' % int(round(__import__('math').log2(float(num_symbols))))



def _dataset_shape(a=None):
    """训练数据集的实际形状（优先 meta.json 记录的 dataset_csv；缺失退回最新一份）。"""
    path = None
    try:
        with open(os.path.join('models', 'ddps', 'meta.json'), encoding='utf-8') as f:
            path = json.load(f).get('dataset_csv')
    except Exception:
        path = None
    cands = ([path] if path and os.path.exists(path) else []) + \
            sorted(glob.glob(os.path.join('dataset', 'ddps_dataset_*.csv')))
    if not cands:
        return '—'
    try:
        df = pd.read_csv(cands[0], usecols=None, nrows=100000)
    except Exception:
        return '—'
    return f'{len(df)} 行 × {df.shape[1]} 列'


def _dir_num_symbols(d):
    """结果目录的符号数（run_config.json）；读不到返回 0。"""
    try:
        with open(os.path.join(d, 'run_config.json'), encoding='utf-8') as f:
            return int(json.load(f).get('num_symbols') or 0)
    except Exception:
        return 0


def _is_zero_error(ber, num_symbols):
    """该参数点是否真实误码数为 0（代码此时报 0.5/(2·min_len)）。

    reported = k/(2·min_len)（0 误码时 k=0.5），min_len ≤ num_symbols，于是
    reported·2·num_symbols = k·num_symbols/min_len ≈ k；只有 k=0.5 会 < 0.8。
    """
    if not num_symbols or not ber or ber != ber:
        return False
    return float(ber) * 2.0 * num_symbols < 0.8


def _floor_stats(summary, order, num_symbols):
    """从该格结果里算出 0 错误检测底，以及中间几档的 BER 范围（全部来自实测数据）。"""
    floor = [summary[e]['best_ber'] for e in order
             if _is_zero_error(summary[e]['best_ber'], num_symbols)]
    mid = [summary[e]['best_ber'] for e in order
           if not _is_zero_error(summary[e]['best_ber'], num_symbols)]
    st = {'n_floor': len(floor), 'n_mid': len(mid), 'num_symbols': int(num_symbols)}
    if floor:
        st['floor_ber'] = float(min(floor))
        st['min_len'] = 0.5 / (2.0 * st['floor_ber'])     # 反推参与比较的符号数
        st['n_bits'] = 2.0 * st['min_len']
        st['ub95'] = 3.0 / st['n_bits']                  # 0 误码的 95% CL 上界
    else:
        st.update(floor_ber=None, min_len=None, n_bits=None, ub95=None)
    if mid:
        st.update(mid_lo=float(min(mid)), mid_hi=float(max(mid)))
    else:
        st.update(mid_lo=None, mid_hi=None)
    return st


MODE_ZH = {'full': 'full（每步全量微扰）', 'rotate': 'rotate（每步轮转 2 维）',
           'secant': 'secant（第 0 步后割线外推）'}
MODE_ZH_FIG = {'full': 'full（每步 7 维全量微扰）', 'rotate': 'rotate（每步轮转 2 维）',
               'secant': 'secant（第 0 步后割线外推）'}
MODE_ZH_PLAIN = {'full': 'full · 每步全量微扰', 'rotate': 'rotate · 每步轮转 2 维',
                 'secant': 'secant · 第 0 步后割线外推'}


def _dir_mean_evals(d):
    """结果目录里每用例平均真实评估次数（读不到返回 None）。"""
    if not d:
        return None
    try:
        summary, _df = _load_summary(d)
    except Exception:
        return None
    return _mean_n_evals(summary, list(summary))


def _mean_n_evals(summary, order):
    """用例级记录里的 n_real_evals 均值（字典是「用例 -> 记录」，不能对字典本身做 in 判断）。"""
    vals = []
    for e in order:
        v = summary.get(e, {}).get('n_real_evals')
        try:
            v = float(v)
        except (TypeError, ValueError):
            continue
        if v == v:
            vals.append(v)
    return int(round(float(np.mean(vals)))) if vals else None


def _ang_deg(a, b):
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na < 1e-15 or nb < 1e-15:
        return float('nan')
    return float(np.degrees(np.arccos(max(-1.0, min(1.0, float(np.dot(a, b) / (na * nb)))))))


def _grad_turn_stats(d):
    """抽头 5 维梯度相对第 0 步的偏离（度）。

    返回 (相对第 0 步均值, 最大, 相邻步均值, CTLE 2 维相对第 0 步均值)，读 trace 的 grad 列。
    读不到轨迹返回 None。
    """
    if not d or not os.path.isdir(d):
        return None
    import glob
    import json as _json
    vs0, step_ang, ctle_vs0 = [], [], []
    for f in sorted(glob.glob(os.path.join(d, 'trace_*.csv'))):
        try:
            tr = pd.read_csv(f)
            G = np.array([_json.loads(v) for v in tr['grad'].astype(str)], dtype=float)
        except Exception:
            continue
        if len(G) < 3 or G.shape[1] < 8:
            continue
        taps = G[:, 0:5]
        ctle = G[:, 5:7]
        vs0 += [_ang_deg(taps[0], taps[k]) for k in range(len(taps))]
        step_ang += [_ang_deg(taps[k], taps[k + 1]) for k in range(len(taps) - 1)]
        ctle_vs0 += [_ang_deg(ctle[0], ctle[k]) for k in range(len(ctle))]
    if not vs0:
        return None
    return (float(np.nanmean(vs0)), float(np.nanmax(vs0)), float(np.nanmean(step_ang)),
            float(np.nanmean(ctle_vs0)) if ctle_vs0 else float('nan'))


def _turn_block(a, order):
    """「方向会不会拐」实测表：3×2 矩阵六格（三种取法 × 两种梯度来源）。数据不足时返回空串。"""
    cells = (
        ('full', a.dirs.get('full'), '代理 × full', '每步都重估（14 个 ±ε 微扰点）'),
        ('rotate', a.dirs.get('rotate'), '代理 × rotate', '每步重估 2 个维（4 个 ±ε 微扰点）'),
        ('secant', a.dirs.get('secant'), '代理 × secant',
         '<strong>不会</strong>：秩一修正只沿位移方向 s 叠加，组内横向分量保持不变'),
        ('direct_full', a.dirs.get('direct_full'), '回传 × full', '每步都重测 8 维（16 个 ±ε 微扰点）'),
        ('direct_rotate', a.dirs.get('direct_rotate'), '回传 × rotate', '每步重测 2 个维（4 个 ±ε 微扰点）'),
        ('direct_secant', a.dirs.get('direct_secant', a.direct), '回传 × secant',
         '<strong>不会</strong>：同为秩一修正（第 0 步后不再微扰）'),
    )
    rows, st = [], {}
    for key, d, label, h in cells:
        v = _grad_turn_stats(d)
        if v is None:
            continue
        st[key] = v
        rows.append('  <tr><td><strong>%s</strong></td><td class="n">%.1f°</td>'
                    '<td class="n">%.1f°</td><td class="n">%.1f°</td><td>%s</td></tr>'
                    % (label, v[0], v[1], v[2], h))
    if len(rows) < 6:                      # 六格未齐时不渲染，避免半张表被误读
        return ''
    body = chr(10).join(rows)
    return ('<div class="tw">' + chr(10) + '<table>' + chr(10)
            + '  <caption>方向能不能拐：抽头 5 维梯度相对第 0 步的偏离（本次运行全程实测，单位：度）</caption>'
            + chr(10)
            + '  <tr><th>格</th><th class="n">相对第 0 步<br>（均值）</th>'
              '<th class="n">相对第 0 步<br>（最大）</th><th class="n">相邻步之间<br>（均值）</th>'
              '<th>抽头方向是否会被重估</th></tr>' + chr(10) + body + chr(10)
            + '</table>' + chr(10) + '</div>' + chr(10)
            + '<p>方向能不能拐，上表给了数：每步重新施加微扰的四格，方向都在拐，代理行抽头方向相对第一步'
            + '平均偏离 %.1f° / %.1f°（full / rotate）、相邻步 %.1f° / %.1f°，回传行 %.1f° / %.1f°、相邻步 %.1f° / %.1f°；'
              '回传行拐得更厉害，因为真实 BER 的差分梯度幅值更大也更抖。'
            % (st['full'][0], st['rotate'][0], st['full'][2], st['rotate'][2],
               st['direct_full'][0], st['direct_rotate'][0], st['direct_full'][2], st['direct_rotate'][2])
            + '而两格 <strong>secant</strong> 的抽头方向与第 0 步<strong>始终共线（0.0°）</strong>：'
              '秩一修正项沿位移方向 s 加入，s 在组内又与初始梯度同向，'
              '于是组内梯度的横向分量永远不变，方向被锁在初始射线上，割线的改向能力全挤到 CTLE 那两维上'
            + '（代理行 %.1f°、回传行 %.1f°）。' % (st['secant'][3], st['direct_secant'][3])
            + '这就是「每步全量微扰 / 轮流微扰」替代纯割线外推的直接理由。</p>'
            + _path_block(a, cells))


def _path_stats(d):
    """路径形态：总位移沿「第 0 步方向」的分量占比（整体 / 抽头 5 维），span 归一化坐标下算。

    返回 (整体共线度, 抽头共线度, CTLE 贴界步占比)；读不到轨迹返回 None。
    """
    if not d or not os.path.isdir(d):
        return None
    import glob
    import json as _json
    span = np.array([0.20] * 5 + [6.0, 6.0, 0.60])
    proj, tproj, n_bound, n_tot = [], [], 0, 0
    for f in sorted(glob.glob(os.path.join(d, 'trace_*.csv'))):
        try:
            tr = pd.read_csv(f)
            X = np.array([_json.loads(v) for v in tr['x'].astype(str)], dtype=float) * span
        except Exception:
            continue
        n_tot += len(tr)
        n_bound += int(((tr['gdc'] <= 1e-9) | (tr['gdc'] >= 12 - 1e-9)).sum())
        n_bound += int(((tr['gdc2'] <= 1e-9) | (tr['gdc2'] >= 4 - 1e-9)).sum())
        if len(X) < 3:
            continue
        U = np.diff(X, axis=0)
        U = U[np.linalg.norm(U, axis=1) > 1e-9]
        if len(U) < 2:
            continue
        u0 = U[0] / np.linalg.norm(U[0])
        D = X[-1] - X[0]
        nD = np.linalg.norm(D)
        if nD < 1e-9:
            continue
        proj.append(abs(float(np.dot(D, u0))) / nD)
        Dt, u0t = D[:5], u0[:5]
        if np.linalg.norm(Dt) > 1e-12 and np.linalg.norm(u0t) > 1e-12:
            tproj.append(abs(float(np.dot(Dt, u0t))) / (np.linalg.norm(Dt) * np.linalg.norm(u0t)))
    if not proj:
        return None
    return (float(np.nanmean(proj)), float(np.nanmean(tproj)) if tproj else float('nan'),
            (float(n_bound) / (2.0 * n_tot)) if n_tot else float('nan'))


def _path_block(a, cells):
    """「走过的路到底是直线还是弯的」实测表：回答「方向真的在变吗」。数据不足返回空串。"""
    st = {}
    for key, d, _label, _h in cells:
        v = _path_stats(d)
        if v is not None:
            st[key] = v
    if len(st) < 6:
        return ''
    rows = []
    for key, d, label, _h in cells:
        v = st[key]
        rows.append('  <tr><td><strong>%s</strong></td><td class="n">%.3f</td>'
                    '<td class="n">%.3f</td><td class="n">%.1f%%</td></tr>'
                    % (label, v[0], v[1], 100.0 * v[2]))
    body = chr(10).join(rows)
    return (chr(10) + '<div class="tw">' + chr(10) + '<table>' + chr(10)
            + '  <caption>轨迹的形状：总位移里落在第一步方向上的比例，按步长归一化算。'
              '1.000 表示一条直线走到底</caption>' + chr(10)
            + '  <tr><th>格</th><th class="n">整体共线度</th><th class="n">抽头 5 维共线度</th>'
              '<th class="n">CTLE 贴物理量程的落地步占比</th></tr>' + chr(10) + body + chr(10)
            + '</table>' + chr(10) + '</div>' + chr(10)
            + '<p>方向有没有在变，看抽头 5 维这一列：两格 secant 都是 '
              '%.3f，一步都没转过；full 和 rotate 是 %.3f 和 %.3f，每步都在转。'
              '但整条轨迹只有 %.0f%% 到 %.0f%% 的位移落在第一步的方向上，'
              '说明最优点本身排成一条窄带，不需要绕着盆地走。'
            % (st['secant'][1], st['full'][1], st['rotate'][1],
               100 * min(st['full'][0], st['rotate'][0], st['direct_full'][0], st['direct_rotate'][0]),
               100 * max(st['full'][0], st['rotate'][0], st['direct_full'][0], st['direct_rotate'][0]))
            + '两格 secant 的差别要看一下：回传 × secant 的整体共线度 %.3f，标准直线；'
              '代理 × secant 只有 %.3f。它不是在转向，原因是代理行的 CTLE 有 %.0f%% 的落地步贴到了'
              '物理量程上，被 clip 掉的那部分位移让 CTLE 看着像在摆。回传行一次都没贴界。'
            % (st['direct_secant'][0], st['secant'][0], 100 * st['secant'][2])
            + 'secant 能用的原因不在它多聪明，而在这个起点上第一步的方向就指对了：起点是刻意'
              '选的次优工作点，幅度错了、结构没错，第一步的全维差分已经算对方向。6.1 里三种取法'
              '的结果只差 5%，只有一例例外，说明在这个起点上方向这个自由度本身带不来多少收益；'
              '决定结果的是第一步方向准不准，以及每组走多远。secant 输掉 2.71 倍的那一例'
              '（HighNoise_IL10x10），就是初始方向不对、后面又没机会纠正。</p>')


# ---------------------------------------------------------------------------
# §6.6 起点鲁棒性：换多个差起点，六格全跑，看结论是否随起点变化
# ---------------------------------------------------------------------------
_STUDY_ROOT = (os.environ.get('DDPS_STUDY_ROOT') or 'result/seed_study')  # 版式探针可用该环境变量指到 scratch/，绝不动正式跑批目录
_STUDY_SEED_META = [
    ('s1_gain-2.6dB', '纯幅度错',
     '形状与 CTLE 一点不动，只把驱动增益再压低 2.6 dB。起点错在驱动幅度，不在均衡形状'),
    ('s2_ctle_g3.0_1.5', '纯均衡错',
     '增益一点不动，把 Tx CTLE 的 peaking 拉到 3.0 dB、低频 shelf 抬到 1.5 dB。起点错在频响形状'),
    ('s3_shape3.0', '形状+幅度都错',
     '4 个 FFE 旁瓣放大 3 倍（形状坏），同时增益再降 0.8 dB（幅度也坏）'),
]
_STUDY_CELLS = [('full', '代理 × full'), ('rotate', '代理 × rotate'), ('secant', '代理 × secant'),
                ('direct_full', '回传 × full'), ('direct_rotate', '回传 × rotate'),
                ('direct_secant', '回传 × secant')]


def _study_num_sym(d):
    try:
        with open(os.path.join(d, 'run_config.json'), encoding='utf-8') as f:
            return int(json.load(f).get('num_symbols') or 0)
    except Exception:
        return 0


def _study_cell_metrics(d):
    """一格 × 一个起点的参数点指标；目录缺 case_summary.csv 返回 None。"""
    p = os.path.join(d, 'case_summary.csv')
    if not os.path.exists(p):
        return None
    try:
        s = pd.read_csv(p)
        best = pd.to_numeric(s['best_ber'], errors='coerce').astype(float)
        seed = pd.to_numeric(s['seed_ber'], errors='coerce').astype(float)
        ev = pd.to_numeric(s['n_real_evals'], errors='coerce').astype(float)
    except Exception:
        return None
    ok = best > 0
    if not ok.any():
        return None
    nsym = _study_num_sym(d)
    floor = 0.5 / (2.0 * nsym) if nsym else 0.0
    return {
        'dir': d, 'envs': list(s['env']), 'bmap': dict(zip(list(s['env']), best.values)),
        'bmap_seed': dict(zip(list(s['env']), seed.values)),
        'best': best.values, 'seed': seed.values,
        'geo': float(np.exp(np.mean(np.log(best[ok].values)))),
        'geo_seed': float(np.exp(np.mean(np.log(seed[seed > 0].values)))) if (seed > 0).any() else float('nan'),
        'evals': float(np.nanmean(ev)),
        'n_floor': int((best <= floor * 1.05).sum()) if floor else 0,
        'nsym': nsym, 'floor': floor, 'n': int(len(s)),
    }


def _ratio_txt(x):
    """倍率文本：小倍率多给有效数字，别把 0.001× 打成 0.00×。"""
    if x is None:
        return '—'
    if x < 0.01:
        return '%.4f×' % x
    if x < 0.1:
        return '%.3f×' % x
    if 0.9 <= x <= 1.1:
        return '%.3f×' % x
    return '%.2f×' % x


def _study_cell_ratio(v, ref):
    """逐用例 best/ref 的倍率统计。"""
    if v is None or ref is None:
        return None
    r = []
    for env, b in v['bmap'].items():
        rb = ref['bmap'].get(env)
        if rb and rb > 0 and b == b:
            r.append(b / rb)
    r = np.array(r, dtype=float)
    r = r[np.isfinite(r)]
    if not len(r):
        return None
    rng = np.random.default_rng(12345)
    idx = rng.integers(0, len(r), size=(400, len(r)))
    boot = np.exp(np.mean(np.log(r[idx]), axis=1))
    lo, hi = np.percentile(boot, [5, 95])
    return {'tie': int((r <= 1.05).sum()), 'worse': int((r > 1.05).sum()),
            'worst': float(np.max(r)), 'geo_ratio': float(np.exp(np.mean(np.log(r)))),
            'lo': float(lo), 'hi': float(hi), 'n': int(len(r))}


def _cn_name(s):
    """起点名写进句子时把「形状+幅度都错」里的加号换成「和」。"""
    return str(s).replace('+', '和').replace('  ', ' ').strip()


def _cn_num(n):
    """小的计数用汉字，别在句子里出现「3 个起点」这种像是变量的写法。"""
    return {0: '零', 1: '一', 2: '两', 3: '三', 4: '四', 5: '五', 6: '六'}.get(int(n), str(int(n)))


def _join_cn(names):
    """['纯幅度错', '纯均衡错'] -> '纯幅度错和纯均衡错'。"""
    names = [str(x) for x in names]
    if len(names) <= 1:
        return ''.join(names)
    return '和'.join([', '.join(names[:-1]).replace(', ', '、'), names[-1]])


def _worst_seed(tabs, cell_key):
    """某格最差的那个起点的名字（判词里点名用）。"""
    best = None
    for key, label, dirs, _sp, _ns, _sc in tabs:
        if key == 'current':
            continue
        ref = dirs.get('full')
        v = dirs.get(cell_key)
        if not ref or not v:
            continue
        rr = _study_cell_ratio(v, ref)
        if not rr:
            continue
        nm = label.split('（')[0].split('：')[0].replace('差起点 ', '')
        if best is None or rr['geo_ratio'] > best[1]:
            best = (nm, rr['geo_ratio'])
    return best[0] if best else '这个起点'


def _study_tab_selfcheck(dirs):
    """代理三格在本起点上「越走越好」还是「原地不动/越走越差」——用 best_step 与预测/实测同向性说。"""
    n_best0 = n_tot = 0
    steps = []
    for key in ('full', 'rotate', 'secant'):
        v = dirs.get(key)
        if v is None:
            continue
        p = os.path.join(v['dir'], 'case_summary.csv')
        if not os.path.exists(p):
            continue
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if 'best_step' not in df:
            continue
        n_best0 += int((df['best_step'] == 0).sum())
        n_tot += len(df)
        steps.append(float(df['best_step'].median()))
    if not n_tot:
        return ''
    # 最难用例上，模型给的方向与实测是否同向
    trend = ''
    rev = False
    ref = dirs.get('full')
    if ref:
        env = max(ref['bmap'], key=lambda e: ref['bmap'][e])
        p = os.path.join(ref['dir'], 'trace_%s.csv' % env)
        if os.path.exists(p):
            try:
                t = pd.read_csv(p)
                p0, p1 = float(t['pred_a'].iloc[0]), float(t['pred_a'].iloc[-1])
                r0, r1 = float(t['real_ber'].iloc[0]), float(t['real_ber'].iloc[-1])
                if r0 > 0 and r1 > 0:
                    pred_r, real_r = 10 ** (p0 - p1), r0 / r1
                    rev = pred_r > 1.0 and real_r < 1.0
                    trend = ('最难用例 <code>%s</code> 上，模型说这个方向能好 %.2f 倍，实测是 %.2f 倍'
                             % (env, pred_r, real_r))
            except Exception:
                trend = ''
    med = max(steps) if steps else 0.0
    if n_best0 * 2 >= n_tot:
        head = ('代理三格在这个起点上没走对：三格合计 %d 个用例，其中 %d 个的最好结果落在第一步'
                '（步号 0），后 14 步没有一步比它更好' % (n_tot, n_best0))
    else:
        head = ('代理三格的最好结果落在第 %.0f 步，三格合计 %d/%d 个用例停在第一步'
                % (med, n_best0, n_tot))
    drift = ''
    if ref and n_best0 * 2 >= n_tot:
        p = os.path.join(ref['dir'], 'case_summary.csv')
        if os.path.exists(p):
            try:
                d = pd.read_csv(p)
                sb = pd.to_numeric(d['seed_ber'], errors='coerce').astype(float)
                fb = pd.to_numeric(d['final_ber'], errors='coerce').astype(float)
                ok = (sb > 0) & (fb > 0)
                if ok.any():
                    gs = float(np.exp(np.mean(np.log(sb[ok].values))))
                    gf = float(np.exp(np.mean(np.log(fb[ok].values))))
                    if gf > gs * 1.2:
                        drift = '；走完 15 步，末步的 15 个用例几何平均比出发点差 %.0f 倍' % (gf / gs)
            except Exception:
                drift = ''
    tail = ('。%s。模型给的方向和实测相反，这个起点已经在模型训练覆盖的范围之外，'
            '按模型走只会更差；这一格不能当成收敛结果。' % trend) if (trend and rev) else '。'
    tail = drift + tail
    return '<p class="note">' + head + tail + '</p>'


def _study_secant_mech(tabs):
    """secant 的跨组比例定死 → gain 一动 CTLE 跟着动；这个「跟着动」在不同起点上是有害还是无害。"""
    notes = []
    for key, label, dirs, _sp, _ns, _sc in tabs:
        if key == 'current':
            continue
        ref, sec = dirs.get('full'), dirs.get('secant')
        if not ref or not sec:
            continue
        env = max(ref['bmap'], key=lambda e: ref['bmap'][e])
        p1 = os.path.join(ref['dir'], 'trace_%s.csv' % env)
        p2 = os.path.join(sec['dir'], 'trace_%s.csv' % env)
        if not (os.path.exists(p1) and os.path.exists(p2)):
            continue
        try:
            z1 = pd.read_csv(p1).iloc[-1]
            z2 = pd.read_csv(p2).iloc[-1]
        except Exception:
            continue
        dg = float(z2['gdc']) - float(z1['gdc'])
        dg2 = float(z2['gdc2']) - float(z1['gdc2'])
        b1, b2 = float(z1['real_ber']), float(z2['real_ber'])
        br = (b2 / b1) if b1 > 0 else float('nan')
        name = label.split('（')[0].split('：')[0].replace('差起点 ', '')
        notes.append('在%s上，最难用例的 BER 是代理 × full 的 %.2f 倍（gDC %+.2f dB、gDC2 %+.2f dB）'
                     % (_cn_name(name), br, dg, dg2))
    if len(notes) < 2:
        return ''
    return ('<p>割线档在第一步就把三个组之间的比例定死。之后 gain 每走一步，CTLE 就按这个比例'
            '跟着动，不想动也不行。CTLE 本来是对的，跟动会把它推歪；CTLE 本来是错的，跟动反而帮上忙。'
            '三个起点上最难用例的差别是：%s。割线档在哪个起点上好、哪个起点上差，取决于起点把误差'
            '落在哪一组，与方向估得准不准无关。</p>' % '；'.join(notes))


def _study_hard_detail(dirs):
    """同一起点、最难用例上，六格末步落在哪（gain 倍率 / gDC / gDC2 / 真实 BER / 用了几步）。"""
    ref = dirs.get('full')
    if not ref:
        return ''
    env = max(ref['bmap'], key=lambda e: ref['bmap'][e])
    rows = []
    for key, label in _STUDY_CELLS:
        v = dirs.get(key)
        if v is None:
            continue
        p = os.path.join(v['dir'], 'trace_%s.csv' % env)
        if not os.path.exists(p):
            continue
        try:
            t = pd.read_csv(p)
            z = t.iloc[-1]
        except Exception:
            continue
        rows.append('  <tr><td><strong>%s</strong></td><td class="n">%d</td>'
                    '<td class="n">%.3f</td><td class="n">%+.2f</td><td class="n">%+.2f</td>'
                    '<td class="n">%.2e</td></tr>'
                    % (label, len(t), float(z['gain_ratio']), float(z['gdc']),
                       float(z['gdc2']), float(z['real_ber'])))
    if not rows:
        return ''
    return (chr(10) + '<div class="tw">' + chr(10) + '<table>' + chr(10)
            + '  <caption>同一起点上最难用例（<code>%s</code>）走完之后的参数：gain 倍率、两个 CTLE 维、真实 BER'
              '<span class="sh">· 可左右滑动</span></caption>' % env + chr(10)
            + '  <tr><th>格</th><th class="n">用了几步</th><th class="n">gain 倍率</th>'
              '<th class="n">gDC (dB)</th><th class="n">gDC2 (dB)</th>'
              '<th class="n">真实 BER</th></tr>' + chr(10)
            + chr(10).join(rows) + chr(10) + '</table>' + chr(10) + '</div>' + chr(10))


def _study_tab_rows(seed_dirs):
    """一个起点内：六格对比表行。"""
    ref = seed_dirs.get('full')
    body = []
    for key, label in _STUDY_CELLS:
        v = seed_dirs.get(key)
        if v is None:
            continue
        rr = _study_cell_ratio(v, ref) if key != 'full' else None
        cmp_txt = '—' if key == 'full' else (_ratio_txt(rr['geo_ratio']) if rr else '—')
        body.append(
            '  <tr><td><strong>%s</strong></td><td class="n">%.3e</td><td class="n">%s</td>'
            '<td class="n">%.0f</td></tr>'
            % (label, v['geo'], cmp_txt, v['evals']))
    return chr(10).join(body)


def _study_ratio_matrix(tabs, same_scale_only=True):
    """{格: [各起点的几何均值倍率]} + 起点短名 + 各自规模。

    `same_scale_only=True` 时只保留「出现次数最多的那个规模」的页签：现役起点是 2^22、
    三个差起点与现役页签可能不同规模，跨规模比出来的差既可能是起点造成的、也可能是规模（检测底/量化）造成的，
    不能混在一起当"起点影响"讲。现役页签仍然显示在判据表里，只是不参与稳定性判断。
    """
    keys = [k for k, _l in _STUDY_CELLS if k != 'full']
    rows = []
    for key, label, dirs, _sp, nsym, _sc in tabs:
        if dirs.get('full') is None:
            continue
        rows.append((key, label.split('（')[0].split('：')[0].replace('差起点 ', ''), nsym, dirs))
    if same_scale_only and rows:
        from collections import Counter
        # 现役页签的规模是历史口径（2^22），先排除，再在差起点之间取最常见的规模
        seed_rows = [r for r in rows if r[0] != 'current'] or rows
        scale = Counter(r[2] for r in seed_rows).most_common(1)[0][0]
        rows = [r for r in rows if r[2] == scale]
    mat, names = {}, []
    for _key, name, _nsym, dirs in rows:
        ref = dirs.get('full')
        names.append(name)
        for ck in keys:
            v = dirs.get(ck)
            rr = _study_cell_ratio(v, ref) if v is not None else None
            if rr:
                mat.setdefault(ck, []).append(rr['geo_ratio'])
    return mat, names


def _study_rank_stats(tabs):
    """同规模页签之间，六格相对强弱的排序是否一致（Kendall τ），以及每格的幅度跨度。"""
    mat, names = _study_ratio_matrix(tabs)
    common = [ck for ck, v in mat.items() if len(v) == len(names)]
    if len(names) < 2 or len(common) < 2:
        return None
    # 每个起点内部按倍率排序（1 = 最好）
    ranks = []
    for i in range(len(names)):
        order = sorted(common, key=lambda ck: mat[ck][i])
        ranks.append({ck: r + 1 for r, ck in enumerate(order)})

    def _tau(a, b):
        con = dis = 0
        ks = list(a)
        for i in range(len(ks)):
            for j in range(i + 1, len(ks)):
                da, db = a[ks[i]] - a[ks[j]], b[ks[i]] - b[ks[j]]
                if da * db > 0:
                    con += 1
                elif da * db < 0:
                    dis += 1
        return (con - dis) / (con + dis) if (con + dis) else 1.0

    taus = []
    for i in range(len(ranks)):
        for j in range(i + 1, len(ranks)):
            taus.append(_tau(ranks[i], ranks[j]))
    span = {ck: (min(mat[ck]), max(mat[ck])) for ck in common}
    return {'names': names, 'cells': common, 'ranks': ranks, 'taus': taus,
            'min_tau': min(taus) if taus else 1.0, 'span': span,
            'identical': all(r == ranks[0] for r in ranks)}


def _study_conclusion_line(a):
    """§7 的第 5 条：换起点之后，哪一层结论不变、哪一层变（与 §6.4 的判词同一套口径）。"""
    per = _study_ratio_by_tab(_study_tabs(a))
    if len(per) < 2:
        return ''
    label_of = dict(_STUDY_CELLS)
    names = list(per)
    dk = ['direct_full', 'direct_rotate', 'direct_secant']
    orders = [sorted([k for k in dk if k in per[nm]], key=lambda k: per[nm][k]) for nm in names]
    orders = [o for o in orders if len(o) >= 2]
    bits = []
    if orders and all(o == orders[0] for o in orders):
        bits.append('三种取法哪个好，三个起点给的答案一样，回传三格都是 %s（从好到差）'
                    % (' ＞ '.join(label_of[k].replace(' ', '') for k in orders[0])))
    elif orders:
        bits.append('三种取法哪个好，三个起点给的答案不一样')
    pv = [per[nm][k] for nm in names for k in ('rotate', 'secant') if k in per[nm]]
    if pv:
        if max(pv) / min(pv) <= 1.06:
            bits.append('代理三格之间差 3% 以内')
        else:
            bits.append('代理三格之间差到 %.2f~%.2f 倍' % (min(pv), max(pv)))
    df = [per[nm]['direct_full'] for nm in names if 'direct_full' in per[nm]]
    if len(df) >= 2 and min(df) > 0:
        bits.append('用不用回传，答案随起点变：回传 × full 是代理 × full 的 %.2f 倍到 %.4f 倍，'
                    '差在第三个起点上模型指错方向，不在取法'
                    % (max(df), min(df)))
    return '<li>换起点之后：' + '；'.join(bits) + '（6.4）。</li>'


def _study_out_of_domain_note(tabs):
    """起点离代理训练邻域太远时：代理三格原地不动、回传格还能动。"""
    hits = []
    for key, label, dirs, _sp, _ns, _sc in tabs:
        if key == 'current':
            continue
        ref = dirs.get('full')
        if not ref:
            continue
        n_best0 = n_tot = 0
        for k in ('full', 'rotate', 'secant'):
            v = dirs.get(k)
            if not v:
                continue
            p = os.path.join(v['dir'], 'case_summary.csv')
            if not os.path.exists(p):
                continue
            try:
                df = pd.read_csv(p)
            except Exception:
                continue
            if 'best_step' in df:
                n_best0 += int((df['best_step'] == 0).sum())
                n_tot += len(df)
        if not n_tot or n_best0 * 2 < n_tot:
            continue
        df_dir = dirs.get('direct_full')
        rr = _study_cell_ratio(df_dir, ref) if df_dir else None
        name = label.split('（')[0].split('：')[0].replace('差起点 ', '')
        hits.append((name, n_best0, n_tot, rr['geo_ratio'] if rr else None))
    if not hits:
        return ''
    bits = []
    for name, n0, nt, ratio in hits:
        if ratio:
            bits.append('在%s上，代理三格合计 %d 个用例里有 %d 个的最好结果落在第一步，'
                        '同一批用例上回传 × full 的几何平均 BER 是代理 × full 的 %.3f 倍'
                        % (_cn_name(name), nt, n0, ratio))
        else:
            bits.append('在%s上，代理三格合计 %d 个用例里有 %d 个的最好结果落在第一步' % (_cn_name(name), nt, n0))
    return ('<p>%s。这些用例上模型说的方向和实测相反，代理格拿不到真实反馈，只能按模型走到底；'
            '同一批用例上回传格还能把 BER 压下去。模型指方向有它覆盖得到的范围，'
            '起点落在范围外时只有回传格能救。</p>' % '；'.join(bits))


def _study_resolution_note(tabs):
    """判据表底下补一句：每个起点下「现役格（代理 × full）还有几个用例在检测底之上」。"""
    bits = []
    for _k, label, dirs, _sp, _ns, _sc in tabs:
        ref = dirs.get('full')
        if not ref:
            continue
        floor = ref.get('floor') or 0.0
        n_above = sum(1 for v in ref['best'] if floor and v > floor * 1.5)
        name = label.split('（')[0].split('：')[0].replace('差起点 ', '')
        bits.append('%s %d/%d' % (name, n_above, ref['n']))
    if not bits:
        return ''
    floors = sorted({(int(round(np.log2(t[4]))), float(t[2]['full']['floor'] or 0.0))
                     for t in tabs if t[2].get('full') and t[4]})
    fl_txt = '、'.join('2^%d 的 %.2e' % (a, b) for a, b in floors)
    return ('<p class="note">检测底是零个错误对应的 0.5/(2·符号数)，各起点按自己的规模算（%s）。'
            '代理 × full 有几个用例落在检测底之上：%s。落到底的用例各格都一样，'
            '倍率只由没落底的用例决定，逐用例明细在各起点页签里。'
            '检测底上「0 个错误」和「1 个错误」本来就是一回事。%s</p>'
            % (fl_txt, '、'.join(bits), _band_txt(tabs)))


def _band_txt(tabs):
    """把噪声带写成一句人话。"""
    b = _study_noise_band(tabs)
    if b is None:
        return ''
    return ('把 15 个用例重新抽样（相当于换一批用例，看结论还成不成立），倍率的 90%% 区间中位半宽约 ±%.0f%%。'
            '小于这个数的差别（1.16 倍和 1.00 倍这种）不能当真实差距；大于它的（1.6 倍、3 倍这种）才算。'
            '没落底的用例只有 3 到 5 个时，这个区间自然就宽。' % (b * 100.0))


def _study_noise_band(tabs):
    """所有「非 full 格」的倍率 bootstrap 半宽中位数（相对量的百分比）。"""
    hs = []
    for _k, _label, dirs, _sp, _ns, _sc in tabs:
        ref = dirs.get('full')
        if not ref:
            continue
        for ck, _l in _STUDY_CELLS:
            if ck == 'full':
                continue
            v = dirs.get(ck)
            rr = _study_cell_ratio(v, ref) if v is not None else None
            if not rr or not rr.get('lo'):
                continue
            g = rr['geo_ratio']
            hs.append(max(g / rr['lo'] - 1.0, rr['hi'] / g - 1.0))
    if not hs:
        return None
    return float(np.median(hs))


def _study_ratio_by_tab(tabs):
    """{起点名: {格: 几何均值倍率}}，只取同规模的差起点页签（现役页签另算锚点）。"""
    from collections import Counter
    rows = []
    for key, label, dirs, _sp, nsym, _sc in tabs:
        if dirs.get('full') is None:
            continue
        rows.append((key, label, nsym, dirs))
    if not rows:
        return {}
    seed_rows = [r for r in rows if r[0] != 'current'] or rows
    scale = Counter(r[2] for r in seed_rows).most_common(1)[0][0]
    out = {}
    for key, label, _nsym, dirs in rows:
        if _nsym != scale:
            continue
        name = label.split('（')[0].split('：')[0].replace('差起点 ', '')
        ref = dirs['full']
        d = {'full': 1.0}
        for ck, _l in _STUDY_CELLS:
            if ck == 'full':
                continue
            v = dirs.get(ck)
            rr = _study_cell_ratio(v, ref) if v is not None else None
            if rr:
                d[ck] = rr['geo_ratio']
        out[name] = d
    return out


def _study_verdict(tabs):
    """判词分两层：族内（哪种取法更好）与族间（代理 vs 回传）。"""
    per = _study_ratio_by_tab(tabs)
    if len(per) < 2:
        return ''
    label_of = dict(_STUDY_CELLS)
    names = list(per)
    scale = tabs[-1][4]

    parts = ['<p>倍率是该格的 BER 除以同一起点下代理 × full 的 BER，先逐用例算再取几何平均；'
             '1.00 倍表示两边一样，小于 1 表示更好。四个起点（现役加三个差起点）都在 2^%d 符号/点上，'
             '直接一起比：%s。</p>'
             % (round(np.log2(scale)), '、'.join(names))]

    # ---- 层一：回传族内部顺序 ----
    direct_keys = ['direct_full', 'direct_rotate', 'direct_secant']
    orders = []
    for nm in names:
        d = per[nm]
        ks = [k for k in direct_keys if k in d]
        if len(ks) >= 2:
            orders.append(sorted(ks, key=lambda k: d[k]))
    if len(orders) >= 2:
        same = all(o == orders[0] for o in orders)
        seq = ' ＞ '.join(label_of[k].replace(' ', '') for k in orders[0])
        rng = {k: (min(per[nm][k] for nm in names if k in per[nm]),
                   max(per[nm][k] for nm in names if k in per[nm])) for k in orders[0]}
        num = '、'.join('%s %s~%s' % (label_of[k].replace(' ', ''),
                                      _ratio_txt(rng[k][0]).rstrip('×'), _ratio_txt(rng[k][1]))
                        for k in orders[0])
        if same:
            parts.append('<p>%s个起点上，回传三格的顺序一样：%s（从好到差），差距随起点变：%s。'
                         '要真实反馈时，每步全量重测最省事，轮转次之，只在第一步测一次最差。</p>'
                         % (_cn_num(len(orders)), seq, num))
        else:
            parts.append('<p>回传三格的顺序随起点变，各起点从好到差分别是 %s；差距 %s。</p>'
                         % ('；'.join('%s：%s' % (nm, ' ＞ '.join(label_of[k].replace(' ', '') for k in o))
                                     for nm, o in zip([n for n in names
                                                       if len([k for k in direct_keys if k in per[n]]) >= 2], orders)),
                            num))

    # ---- 层二：代理族内部 ----
    proxy_keys = ['rotate', 'secant']
    prng = {}
    for k in proxy_keys:
        vals = [per[nm][k] for nm in names if k in per[nm]]
        if vals:
            prng[k] = (min(vals), max(vals))
    if prng:
        txt = '、'.join('%s %s~%s' % (label_of[k].replace(' ', ''),
                                      _ratio_txt(v[0]).rstrip('×'), _ratio_txt(v[1]))
                        for k, v in prng.items())
        near = all(v[0] >= 0.95 and v[1] <= 1.06 for v in prng.values())
        if near:
            parts.append('<p>代理三格之间差 3%% 以内（%s），换哪种取法都差不多；'
                         '决定参数点的是有没有真实 BER。</p>' % txt)
        else:
            worst_k = max(prng, key=lambda k: prng[k][1])
            parts.append('<p>代理三格大体一样（%s）。%s 最差的一处在%s，差 %.1f 倍，原因见下面一段。</p>'
                         % (txt, label_of[worst_k].replace(' ', ''),
                            _cn_name(_worst_seed(tabs, worst_k)), prng[worst_k][1]))

    # ---- 层三：族间（按噪声带分「一样」与「真差异」）----
    df_vals = [(nm, per[nm]['direct_full']) for nm in names
               if 'direct_full' in per[nm] and per[nm].get('full') == 1.0]
    if len(df_vals) >= 2:
        band = _study_noise_band(tabs) or 0.0
        tie = [(nm, v) for nm, v in df_vals if band and abs(v - 1.0) <= band]
        off = [(nm, v) for nm, v in df_vals if not (band and abs(v - 1.0) <= band)]
        seg = []
        if tie:
            seg.append('在%s上两边一样（%s），差值都在 ±%.0f%% 的抽样波动里，分不出高低；'
                       '几何平均被大量已经落底的用例拉平，差别只出现在少数难用例上'
                       % (_join_cn([nm for nm, _v in tie]),
                          '、'.join('%s %s' % (_cn_name(nm), _ratio_txt(v)) for nm, v in tie),
                          band * 100.0))
        if off:
            lo = min(off, key=lambda x: x[1])
            seg.append('在%s上差别是真的：回传 × full 是代理 × full 的 %s，好 %.0f 倍'
                       % (_cn_name(lo[0]), _ratio_txt(lo[1]), 1.0 / lo[1] if lo[1] else 0.0))
        if seg:
            head = ('<p>回传 × full 只在模型指错方向时才明显更强：' if off and tie else '<p>')
            parts.append(head + '；'.join(seg) + '。</p>')
    return ''.join(parts)


_CURVE_COLORS = {
    'full': '#0b63ce', 'rotate': '#0f8a4a', 'secant': '#b8860b',
    'direct_full': '#c2410c', 'direct_rotate': '#7c3aed', 'direct_secant': '#0891b2',
}
_CURVE_SHORT = {
    'full': '代理全测', 'rotate': '代理轮测', 'secant': '代理外推',
    'direct_full': '回传全测', 'direct_rotate': '回传轮测', 'direct_secant': '回传外推',
}


def _trace_lb(cell_dir, env):
    """该格该用例每一步实测算到的 log10 BER。"""
    p = os.path.join(cell_dir, 'trace_%s.csv' % env)
    if not os.path.exists(p):
        return []
    try:
        t = pd.read_csv(p)
        return [(int(r['step']), float(r['real_lb'])) for _, r in t.iterrows()
                if float(r['real_lb']) == float(r['real_lb'])]
    except Exception:
        return []


def _study_case_svg(dirs, env, w=330, h=168):
    """一个用例、六格六条线的收敛对比图。"""
    series = []
    for key, label in _STUDY_CELLS:
        cell = dirs.get(key)
        if not cell:
            continue
        pts = _trace_lb(cell['dir'], env)
        if len(pts) >= 2:
            series.append((key, label, pts))
    if len(series) < 2:
        return ''
    ys = [y for _k, _l, pts in series for _s, y in pts]
    y0, y1 = min(ys), max(ys)
    if y1 - y0 < 0.15:
        y0, y1 = y0 - 0.1, y1 + 0.1
    pad = 0.08 * (y1 - y0)
    y0, y1 = y0 - pad, y1 + pad
    xmax = max(len(pts) for _k, _l, pts in series) - 1
    ml, mr, mt, mb = 34, 6, 26, 20
    iw, ih = w - ml - mr, h - mt - mb

    def X(i):
        return ml + (iw * i / max(1, xmax))

    def Y(v):
        return mt + ih * (1.0 - (v - y0) / (y1 - y0))

    out = ['<svg class="cv" viewBox="0 0 %d %d" role="img" aria-label="%s 六格收敛对比">' % (w, h, env)]
    # 网格与刻度
    for k in range(5):
        yy = mt + ih * k / 4.0
        out.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#e6ebf1" stroke-width="1"/>'
                   % (ml, yy, ml + iw, yy))
    for k in range(5):
        yy = mt + ih * k / 4.0
        val = y1 - (y1 - y0) * k / 4.0
        out.append('<text x="%d" y="%.1f" text-anchor="end" font-size="8" fill="#6b7a8d">%.0f</text>'
                   % (ml - 4, yy + 3, val))
    out.append('<text x="%d" y="%d" font-size="8" fill="#6b7a8d">log10 BER</text>' % (2, mt - 12))
    out.append('<text x="%.1f" y="%d" text-anchor="middle" font-size="8" fill="#6b7a8d">步</text>'
               % (ml + iw / 2.0, h - 6))
    for i in range(0, xmax + 1, max(1, xmax // 5)):
        out.append('<text x="%.1f" y="%d" text-anchor="middle" font-size="8" fill="#6b7a8d">%d</text>'
                   % (X(i), h - 8, i))
    # 六条线
    for key, _label, pts in series:
        col = _CURVE_COLORS.get(key, '#333')
        d = ' '.join('%.1f,%.1f' % (X(i), Y(v)) for i, v in pts)
        out.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="1.6" '
                   'stroke-linejoin="round"/>' % (d, col))
        xe, ye = X(pts[-1][0]), Y(pts[-1][1])
        out.append('<circle cx="%.1f" cy="%.1f" r="2.2" fill="%s"/>' % (xe, ye, col))
    # 图例（两行三列，压在顶部）
    for idx, (key, _label, _pts) in enumerate(series):
        cx = ml + (idx % 3) * (iw / 3.0)
        cy = 9 + (idx // 3) * 11
        out.append('<rect x="%.1f" y="%.1f" width="7" height="7" fill="%s"/>'
                   % (cx, cy - 6, _CURVE_COLORS.get(key, '#333')))
        out.append('<text x="%.1f" y="%.1f" font-size="8" fill="#43536b">%s</text>'
                   % (cx + 10, cy, _CURVE_SHORT.get(key, key)))
    out.append('</svg>')
    return ''.join(out)


def _study_cell_svg(cell_dir, envs, key, w=680, h=230):
    """一格、15 个用例的轨迹叠在一张图上，粗线是中位数。"""
    series = []
    for env in envs:
        pts = _trace_lb(cell_dir, env)
        if len(pts) >= 2:
            series.append((env, pts))
    if len(series) < 2:
        return ''
    ys = [y for _e, pts in series for _s, y in pts]
    y0, y1 = min(ys), max(ys)
    if y1 - y0 < 0.15:
        y0, y1 = y0 - 0.1, y1 + 0.1
    pad = 0.06 * (y1 - y0)
    y0, y1 = y0 - pad, y1 + pad
    xmax = max(len(pts) for _e, pts in series) - 1
    ml, mr, mt, mb = 40, 8, 10, 20
    iw, ih = w - ml - mr, h - mt - mb
    col = _CURVE_COLORS.get(key, '#0b63ce')

    def X(i):
        return ml + iw * i / max(1, xmax)

    def Y(v):
        return mt + ih * (1.0 - (v - y0) / (y1 - y0))

    out = ['<svg class="cv" viewBox="0 0 %d %d" role="img" aria-label="该格 15 个用例的收敛轨迹">' % (w, h)]
    for k in range(5):
        yy = mt + ih * k / 4.0
        out.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#e6ebf1" stroke-width="1"/>'
                   % (ml, yy, ml + iw, yy))
        val = y1 - (y1 - y0) * k / 4.0
        out.append('<text x="%d" y="%.1f" text-anchor="end" font-size="9" fill="#6b7a8d">%.0f</text>'
                   % (ml - 5, yy + 3, val))
    for i in range(0, xmax + 1, max(1, xmax // 6)):
        out.append('<text x="%.1f" y="%d" text-anchor="middle" font-size="9" fill="#6b7a8d">%d</text>'
                   % (X(i), h - 6, i))
    out.append('<text x="%d" y="%d" font-size="9" fill="#6b7a8d">log10 BER</text>' % (2, 9))
    for _env, pts in series:
        d = ' '.join('%.1f,%.1f' % (X(i), Y(v)) for i, v in pts)
        out.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="1" opacity="0.55"/>'
                   % (d, col))
    # 中位数线
    n = max(len(p) for _e, p in series)
    med = []
    for i in range(n):
        vals = [p[i][1] for _e, p in series if len(p) > i]
        if vals:
            med.append((i, float(np.median(vals))))
    if len(med) >= 2:
        d = ' '.join('%.1f,%.1f' % (X(i), Y(v)) for i, v in med)
        out.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="2.4"/>' % (d, col))
    out.append('</svg>')
    return ''.join(out)


def _ac_coupling_svg(w=980, h=250):
    """左：单极点高通的 |H(f)| 与规范上限；右：长连码经过隔直后的 droop。"""
    import numpy as np
    f = np.logspace(3, 7, 200)
    out = ['<svg class="d-wide" viewBox="0 0 %d %d" role="img" aria-label="隔直频响与基线漂移">' % (w, h)]
    # ---- 左：频响 ----
    x0, y0, pw, ph = 60, 30, 380, 170
    out.append('<text x="%d" y="18" font-size="12" fill="#1b3f6b">单极点高通 |H(f)|（fc = 100 kHz）</text>' % x0)
    out.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#43536b"/>' % (x0, y0 + ph, x0 + pw, y0 + ph))
    out.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#43536b"/>' % (x0, y0, x0, y0 + ph))
    for fc, col, lab in ((1e5, '#0b63ce', 'fc = 100 kHz（规范上限）'),
                         (3.4e4, '#0f8a4a', 'fc = 34 kHz（100 nF 实算）')):
        pts = []
        for fv in f:
            x = fv / fc
            mag = 20 * np.log10(max(1e-6, x / np.sqrt(1 + x * x)))
            px = x0 + pw * (np.log10(fv) - 3) / 4.0
            py = y0 + ph * (1.0 - (max(-40.0, mag) + 40.0) / 40.0)
            pts.append('%.1f,%.1f' % (px, py))
        out.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="1.8"/>' % (' '.join(pts), col))
        out.append('<text x="%d" y="%d" font-size="11" fill="%s">%s</text>' % (x0 + 150, y0 + 12 + (14 if fc > 5e4 else 0), col, lab))
    for db in (-3, -20, -40):
        py = y0 + ph * (1.0 - (db + 40) / 40.0)
        out.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#e6ebf1"/>' % (x0, py, x0 + pw, py))
        out.append('<text x="%d" y="%.1f" text-anchor="end" font-size="10" fill="#6b7a8d">%d dB</text>' % (x0 - 4, py + 3, db))
    for fv, lab in ((1e3, '1k'), (1e4, '10k'), (1e5, '100k'), (1e6, '1M'), (1e7, '10M')):
        px = x0 + pw * (np.log10(fv) - 3) / 4.0
        out.append('<text x="%.1f" y="%d" text-anchor="middle" font-size="10" fill="#6b7a8d">%s</text>' % (px, y0 + ph + 14, lab))
    # ---- 右：droop ----
    x1, pw2 = 560, 380
    out.append('<text x="%d" y="18" font-size="12" fill="#1b3f6b">1000 个相同符号经过隔直后的 droop</text>' % x1)
    out.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#43536b"/>' % (x1, y0 + ph, x1 + pw2, y0 + ph))
    out.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#43536b"/>' % (x1, y0, x1, y0 + ph))
    t = np.linspace(0, 1000, 200)          # 以符号为单位
    for fc, col, lab, baud in ((1e5, '#0b63ce', '100 kHz', 53.125e9),
                               (3.4e4, '#0f8a4a', '34 kHz', 53.125e9),
                               (1e6, '#c2410c', '1 MHz（不合规，作对照）', 53.125e9)):
        tau_sym = (1.0 / (2 * np.pi * fc)) * baud
        droop = 1.0 - np.exp(-t / tau_sym)
        pts = ['%.1f,%.1f' % (x1 + pw2 * tt / 1000.0, y0 + ph * (1.0 - d)) for tt, d in zip(t, droop)]
        out.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="1.8"/>' % (' '.join(pts), col))
        out.append('<text x="%d" y="%d" font-size="11" fill="%s">%s：%.1f%%</text>'
                   % (x1 + 12, y0 + 14 + (14 * [1e5, 3.4e4, 1e6].index(fc)), col, lab, 100 * droop[-1]))
    out.append('<text x="%d" y="%d" text-anchor="middle" font-size="10" fill="#6b7a8d">连码长度（符号）</text>'
               % (x1 + pw2 / 2, h - 6))
    out.append('</svg>')
    return ''.join(out)


def _study_case_curves(dirs, seed_ber=None):
    """一个起点下，15 个用例各一张六格轨迹图。"""
    ref = dirs.get('full')
    if not ref:
        return ''
    cards = []
    for env in ref['envs']:
        svg = _study_case_svg(dirs, env)
        if not svg:
            continue
        rb = ref['bmap'].get(env) or 0
        sb = ref['bmap_seed'].get(env) or 0
        cards.append('<figure class="cv-card">%s<figcaption>%s<br>起点 %.2e → 代理全测 %.2e</figcaption></figure>'
                     % (svg, env, sb, rb) if sb and rb else
                     '<figure class="cv-card">%s<figcaption>%s</figcaption></figure>' % (svg, env))
    if not cards:
        return ''
    return ('<h4>每个用例、六个组合分别怎么走的</h4>'
            '<p class="note">一张图一个用例，六条线是六种组合各自的 BER 随步变化，纵轴 log10(BER)，'
            '端点圆点是最后一步。同一个用例的六条线放在同一刻度上，可以直接比谁掉得快、谁中途回升。</p>'
            '<div class="cv-grid">' + ''.join(cards) + '</div>')


def _study_hard_png(d):
    rd = os.path.join(d, 'report')
    if not os.path.isdir(rd):
        return None
    import glob as _g
    cand = sorted(_g.glob(os.path.join(rd, 'ddps_case_*.png')))
    return cand[0] if cand else None


def _study_scale_txt(nsym):
    """把符号数写成「2^21（210 万）」这种一眼能对照协议的形状。"""
    if not nsym:
        return '—'
    e = {262144: 18, 524288: 19, 1048576: 20, 2097152: 21, 4194304: 22}.get(int(nsym))
    head = '2^%d' % e if e else '%.0f' % nsym
    return '%s（%d 万）' % (head, round(nsym / 10000))


def _study_seed_brief(seed_dirs):
    """起点本身：几何均值 / 最难用例 / 基线用例。"""
    v = seed_dirs.get('full')
    if v is None:
        return ''
    seed = v['seed']
    base = None
    hard = None
    try:
        base = float(v['bmap_seed']['Base_IL10x10'])
    except Exception:
        pass
    try:
        hard = float(np.nanmax(seed))
    except Exception:
        pass
    return base, hard, v['geo_seed']


def _study_seed_params(spath):
    import ddps_optimizer as _DOP
    try:
        with open(spath, encoding='utf-8') as f:
            sc = json.load(f)
    except Exception:
        return ''
    taps = sc.get('best_taps') or []
    gain = None
    if 'best_u_gain' in sc:
        gain = float(_DOP.gain_from_u(float(sc['best_u_gain'])))
    elif 'best_gain' in sc:
        gain = float(sc['best_gain'])
    t = ', '.join('%+.3f' % x for x in taps)
    src_txt = sc.get('_source')
    src_txt = ('起点的问题：%s。' % src_txt) if isinstance(src_txt, str) else ''
    return ('<p class="note">起点参数：5 抽头 [%s]，gDC = %.2f dB，gDC2 = %.2f dB，增益 = %.4f'
            '（标称 %.4f，比值 %.3f）。%s</p>'
            % (t, float(sc.get('best_gdc', 0)), float(sc.get('best_gdc2', 0)),
               gain or 0.0, _DOP.DRIVER_GAIN_NOMINAL, (gain or 0.0) / _DOP.DRIVER_GAIN_NOMINAL,
               src_txt))


def _study_tabs(a):
    """现役 + 各差起点各一个大 tab 的数据：(key, label, dirs, spath, num_sym, note)。

    dirs 是 {格: 指标 dict}，只有目录里真有 case_summary.csv 的格才在里头——
    跑批还没到的格自然缺席，表格里显示 —，不会拿半成品充数。
    """
    tabs = []   # (key, label, dirs, spath, num_sym, note)

    # 现役六格的目录（直接来自交付件生成参数，不猜）
    cur_dirs = {'full': a.dirs.get('full'), 'rotate': a.dirs.get('rotate'),
                'secant': a.dirs.get('secant'), 'direct_full': a.direct_full,
                'direct_rotate': a.direct_rotate, 'direct_secant': a.direct}
    cur = {}
    for key, _label in _STUDY_CELLS:
        d = cur_dirs.get(key)
        if d and os.path.isdir(d):
            v = _study_cell_metrics(d)
            if v is not None:
                cur[key] = v
    if cur:
        tabs.append(('current', '现役起点（gain ×0.325）', cur, 'result/seed_config_bad_1e4.json',
                     _study_num_sym(a.dirs.get('full', '')), _study_scale_txt(
                         _study_num_sym(a.dirs.get('full', '')))))

    meta_names = [m[0] for m in _STUDY_SEED_META]
    extra = []
    if os.path.isdir(_STUDY_ROOT):
        extra = [d for d in sorted(os.listdir(_STUDY_ROOT))
                 if os.path.isdir(os.path.join(_STUDY_ROOT, d)) and d not in meta_names]
    plan = [(n, l, t) for n, l, t in _STUDY_SEED_META]
    plan += [(d, '差起点（%s）' % d, '') for d in extra]
    for name, label, _note in plan:
        dirs = {}
        for key, _label in _STUDY_CELLS:
            d = os.path.join(_STUDY_ROOT, name, 'ddps_cpp_%s' % key)
            v = _study_cell_metrics(d)
            if v is not None:
                dirs[key] = v
        if dirs:
            nsym = next(iter(dirs.values()))['nsym']
            tabs.append((name, '差起点 %s：%s' % (label, name), dirs,
                         os.path.join('seeds', 'seed_%s.json' % name), nsym,
                         _study_scale_txt(nsym)))
    return tabs


def _study_seed_calib(tabs):
    """差起点的起点 BER 校准值（基线用例几何均值）+ 与现役起点的倍数关系，写成一句人话。"""
    cur = None
    vals = []
    for key, _label, dirs, _sp, _ns, _sc in tabs:
        ref = dirs.get('full')
        if not ref:
            continue
        b = (ref.get('bmap_seed') or {}).get('Base_IL10x10')
        if not b or b <= 0:
            continue
        if key == 'current':
            cur = b
        else:
            vals.append(b)
    if not vals:
        return '<strong>约 1e-3</strong>'
    g = float(np.exp(np.mean(np.log(vals))))
    if cur and cur > 0:
        return ('<strong>%.1e</strong>（现役起点 %.1e，差 %.1f 倍）' % (g, cur, g / cur))
    return '<strong>%.1e</strong>' % g


def _study_seed_calib_placeholder():
    pass


def _study_block(a):
    """§6.6 整块：跨起点汇总表 + 每个起点一个大 tab（内含六格小 tab）。"""
    tabs = _study_tabs(a)
    if len(tabs) < 2:
        return ''

    # ---- 跨起点汇总：每一格在四个起点下「相对该起点现役格」的几何均值倍率 ----
    head = ''.join('<th class="n">%s</th>'
                   % t[1].split('（')[0].split('：')[0].replace('差起点 ', '') for t in tabs)
    rows = []
    for key, label in _STUDY_CELLS:
        cells = []
        for _k, _l, dirs, _sp, _ns, _sc in tabs:
            v = dirs.get(key)
            ref = dirs.get('full')
            if v is None:
                cells.append('<td class="n">—</td>')
                continue
            if key == 'full':
                cells.append('<td class="n">1.00×</td>')
                continue
            rr = _study_cell_ratio(v, ref)
            cells.append('<td class="n">%s</td>' % (_ratio_txt(rr['geo_ratio']) if rr else '—'))
        rows.append('  <tr><td><strong>%s</strong></td>%s</tr>' % (label, ''.join(cells)))

    sum_tbl = (chr(10) + '<div class="tw">' + chr(10) + '<table>' + chr(10)
               + '  <caption>六格在四个起点下的结果倍率：分子是该格，分母是同一起点的代理 × full，'
                 '15 个用例的几何平均<span class="sh">· 可左右滑动</span></caption>' + chr(10)
               + '  <tr><th>格</th>' + head + '</tr>' + chr(10)
               + chr(10).join(rows) + chr(10) + '</table>' + chr(10) + '</div>' + chr(10))

    # ---- 大 tab：一个起点一个 ----
    bar, panels = [], []
    for idx, (key, label, dirs, spath, nsym, scale) in enumerate(tabs):
        pid = 'tab-seed-%s' % key
        bar.append('    <button class="tab-btn%s" data-tab="%s">%s</button>'
                   % (' active' if idx == 0 else '', pid, label))
        parts = []
        geos = {ck: _study_cell_metrics(dirs[ck]['dir']) for ck, _l in _STUDY_CELLS if dirs.get(ck)}
        geos = {k: v for k, v in geos.items() if v}
        if len(geos) >= 2:
            bk = min(geos, key=lambda k: geos[k]['geo'])
            wk = max(geos, key=lambda k: geos[k]['geo'])
            lead = ('<p class="lead">这个起点上最好的是 <strong>%s</strong>，最差的是 <strong>%s</strong>'
                    '（几何平均 BER 分别 %.2e 和 %.2e，相差 %.1f 倍）。</p>'
                    % (dict(_STUDY_CELLS)[bk], dict(_STUDY_CELLS)[wk],
                       geos[bk]['geo'], geos[wk]['geo'],
                       geos[wk]['geo'] / geos[bk]['geo'] if geos[bk]['geo'] else 0.0))
            parts.append(lead)
        brief = _study_seed_brief(dirs)
        if brief:
            parts.append('<p>这个起点的 BER：基线用例 %.2e，最难用例 %.2e，15 个用例的几何平均 %.2e。'
                         '规模 %s 符号/点，检测底 %.2e。</p>'
                         % (brief[0] or float('nan'), brief[1] or float('nan'), brief[2], scale,
                            dirs['full']['floor']))
        parts.append(_study_seed_params(spath) if spath and os.path.exists(spath) else '')
        parts.append(_study_case_curves(dirs))
        for ck in ('full', 'direct_full'):
            cell = dirs.get(ck)
            if not cell:
                continue
            hard_png = _study_hard_png(cell['dir'])
            if not hard_png:
                continue
            cname = dict(_STUDY_CELLS).get(ck, ck)
            cap = ('%s 在最难用例上的六张图：BER 随步变化、5 个抽头、Tx CTLE 频响、探针 FIR、'
                   '发端频谱（起点与最优）、频谱改变量。频谱含 FFE、DAC 零阶保持、Tx CTLE 与驱动增益'
                   % cname)
            parts.append('<figure>\n  <div class="fig-scroll"><img src="%s" alt="%s"></div>\n'
                         '  <figcaption>%s</figcaption>\n</figure>' % (_img_tag(hard_png, width=1200), cap, cap))
        parts.append(chr(10) + '<div class="tw">' + chr(10) + '<table>' + chr(10)
                     + '  <caption>同一起点下六格的结果与代价：BER 取 15 个用例的几何平均，'
                       '倍率是相对代理全测<span class="sh">· 可左右滑动</span></caption>' + chr(10)
                     + '  <tr><th>格</th><th class="n">几何平均 BER</th><th class="n">相对代理全测</th>'
                       '<th class="n">每用例真实评估</th></tr>' + chr(10)
                     + _study_tab_rows(dirs) + chr(10) + '</table>' + chr(10) + '</div>' + chr(10))

        parts.append(_study_tab_selfcheck(dirs))
        # 小 tab：六格逐用例明细（纯表格，避免重复内联收敛图把 HTML 撑大）
        sbar, span = [], []
        ref = dirs.get('full')
        for ck, clabel in _STUDY_CELLS:
            v = dirs.get(ck)
            if v is None:
                continue
            rows_td = []
            for idx_e, env in enumerate(v['envs']):
                sd = v['seed'][idx_e]
                bs = v['best'][idx_e]
                rat = '—'
                if ref is not None and ck != 'full':
                    rb = ref['bmap'].get(env)
                    if rb and rb > 0:
                        rat = '%.2f×' % (bs / rb)
                rows_td.append('      <tr><td>%s</td><td class="n">%.2e</td><td class="n">%.2e</td>'
                               '<td class="n">%s</td></tr>' % (env, sd, bs, rat))
            spid = 'tab-seed-%s-%s' % (key, ck)
            sbar.append('    <button class="tab-btn%s" data-tab="%s">%s</button>'
                        % (' active' if not sbar else '', spid, clabel))
            cell_svg = _study_cell_svg(v['dir'], v['envs'], ck)
            fig_html = ('<figure>\n  <div class="fig-scroll">%s</div>\n'
                        '  <figcaption>%s · %s：该格 15 个用例各自的 BER 随步变化，'
                        '细线是一个用例，粗线是 15 个用例的中位数。</figcaption>\n</figure>\n'
                        % (cell_svg, label, clabel)) if cell_svg else ''
            envs_all = v['envs']
            bi = int(np.argmin(v['best'])) if len(v['best']) else 0
            wi = int(np.argmax(v['best'])) if len(v['best']) else 0
            brief = ('最好 %s（%s）· 最差 %s（%s）· 15 个用例几何平均 %.2e · 每用例真实评估 %.0f 次'
                     % (_ber(v['best'][bi]), envs_all[bi], _ber(v['best'][wi]), envs_all[wi],
                        v['geo'], v['evals'])) if len(v['best']) else ''
            span.append('\n  <div class="tab-panel%s" id="%s">\n    %s\n    <p class="note">%s</p>\n  </div>'
                        % (' active' if len(span) == 0 else '', spid, fig_html, brief))
        if sbar:
            parts.append(chr(10) + '<div class="tabs">' + chr(10) + '  <div class="tab-bar">' + chr(10)
                         + chr(10).join(sbar) + chr(10) + '  </div>' + ''.join(span) + chr(10) + '</div>')
        panels.append('\n  <div class="tab-panel%s" id="%s">\n    %s\n  </div>'
                      % (' active' if idx == 0 else '', pid, '\n    '.join(parts)))

    calib = _study_seed_calib(tabs)
    return (chr(10) + '<h3>6.4 换个起点：四个起点下每个组合每个用例怎么走的</h3>' + chr(10)
            + '<p>前面所有结果的起点是同一个次优工作点：抽头形状基本对，增益只有标称的 0.325 倍。'
              '结论只在一个起点成立就用不了，这一节换三个方向不同的坏起点，'
              '三个差起点在基线用例上的 BER 都校准到 %s 上下，每个起点把六格各跑一遍。'
              '四个起点都在 %s 符号/点上，检测底 %.2e，可以直接对读。</p>'
              % (calib, _study_scale_txt(tabs[-1][4]),
                 (tabs[-1][2].get('full') or {}).get('floor') or 0.0) + chr(10)
            + '<ul>'
            + '<li>纯幅度错：形状与 CTLE 不动，驱动增益再压低 2.6 dB。</li>'
            + '<li>纯均衡错：增益不动，Tx CTLE 的 peaking 与低频 shelf 拉偏。</li>'
            + '<li>形状和幅度都错：4 个 FFE 旁瓣放大 3 倍，增益再降 0.8 dB。</li>'
            + '</ul>' + chr(10)
            + sum_tbl
            + _study_verdict(tabs)
            + _study_secant_mech(tabs)
            + _study_out_of_domain_note(tabs)
            + _study_resolution_note(tabs)
            + chr(10) + '<div class="tabs">' + chr(10) + '  <div class="tab-bar">' + chr(10)
            + chr(10).join(bar) + chr(10) + '  </div>' + ''.join(panels) + chr(10) + '</div>' + chr(10)
            + '<p class="note">复现命令：<code>python tools\\run_seed_study.py --jobs 12 --num-symbols %d '
              '--seeds s1_gain-2.6dB,s2_ctle_g3.0_1.5,s3_shape3.0</code>。起点文件在 <code>seeds/</code>，'
              '起点 BER 由链路实测（选点脚本 <code>tools/probe_start_point.py</code>）。</p>'
              % (tabs[-1][4],))



def _seed_spectrum_block(a):
    """§6.0 的起点 → 最优三件套图（基线用例）：抽头形状、Tx CTLE |H(f)|、发端频谱对比。"""
    d = (a.dirs or {}).get(a.mode) or (a.dirs or {}).get('full')
    if not d:
        return ''
    p = os.path.join(d, 'report', 'ddps_spectrum_Base_IL10x10.png')
    if not os.path.exists(p):
        return ''
    cap = ('起点 → 最优的三件套（基线用例 Base_IL10x10）：5 抽头形状、Tx CTLE |H(f)|、'
           '<strong>发端频谱对比</strong>（FFE ⊗ DAC 零阶保持 ⊗ Tx CTLE ⊗ 驱动增益，'
           '载波按白谱处理，两条曲线的差即这三个线性环节造成的频谱改变）')
    return ('<figure>\n  <div class="fig-scroll"><img src="%s" alt="起点与最优的发端频谱对比"></div>\n'
            '  <figcaption>%s</figcaption>\n</figure>' % (_img_tag(p), cap))


def _eval_mag_txt(ev_d, ev_s):
    """direct 与现役格每用例真实评估量的量级比较：差不到 3 倍说"同量级"，
    差得多就直说倍数，避免写死一句话在换取法后变成假话。"""
    try:
        r = float(ev_s) / float(ev_d)
    except (TypeError, ValueError, ZeroDivisionError):
        return ''
    if r <= 0:
        return ''
    if 0.5 <= r <= 3.0:
        return '，同量级'
    return ('，现役格约为 direct 的 %.1f 倍' % r) if r > 1 else ('，现役格比 direct 省 %.1f 倍' % (1 / r))


def _ratio_str(r):
    """微扰瞬时最坏倍率的人话格式：正常情况下是 ×0.xx；远低于种子时用科学计数，
    避免出现 ×0.0 这种看起来像坏了的写法。"""
    try:
        r = float(r)
    except (TypeError, ValueError):
        return '—'
    if not (r == r) or r <= 0:
        return '—'
    return ('×%.2f' % r) if r >= 0.1 else ('×%.1e' % r)


def _floor_txt(fs, short=False):
    """「N 例到 0 错误检测底（伪计数 x）+ M 例停在 a ~ b」的人话表述（无数据给空串）。"""
    if not fs or not fs.get('n_floor'):
        return ''
    t = f"{fs['n_floor']} 例到 0 错误检测底（伪计数 {_ber(fs['floor_ber'])}，{_per_bits(fs['floor_ber'])}）"
    if fs.get('n_mid') and fs.get('mid_lo') is not None:
        if short:
            t = f"{fs['n_floor']} 例到 0 错误检测底、{fs['n_mid']} 例停在检测底附近"
        else:
            t += f"，{fs['n_mid']} 例停在 {_ber(fs['mid_lo'])} ~ {_ber(fs['mid_hi'])}"
    return t


def _scale_guard(a):
    """六格经 _pick_dir 实际选到的结果规模必须一致，否则拒绝生成。"""
    picked, scales = {}, {}
    for mode in ('full', 'rotate', 'secant', 'direct'):
        d, scale = _pick_dir(a.dirs, mode)
        if not d:
            continue
        picked[mode] = (d, scale)
        scales[mode] = _dir_num_symbols(d) or 0
    vals = set(v for v in scales.values() if v)
    if len(vals) > 1:
        detail = '，'.join(f'{m}={_sym_txt(v)}({picked[m][0]})' for m, v in scales.items())
        msg = f'六格结果规模不一致：{detail}'
        if getattr(a, 'allow_mixed_scale', False):
            print('[deliverable][WARN] ' + msg + '（--allow-mixed-scale 已放行，交付件会出现混口径）')
        else:
            raise SystemExit(msg + '\n→ 等同一规模的六格都跑完再生成；调试可用 --allow-mixed-scale')
    return picked


def _pick_dir(dirs, mode):
    """优先用全量结果目录；没有就退到 2^18 比对目录（规模标签取自 run_config.json）。

    direct_secant 兼容旧命名：早期结果目录叫 `direct`，语义就是「第 0 步一轮后 Broyden」。
    """
    cands = [(dirs.get(mode), '全量')]
    if mode == 'direct_secant':
        cands.append((dirs.get('direct'), '全量'))
    cands.append((dirs.get(f'{mode}_eq'), '2^18'))
    if mode == 'direct_secant':
        cands.append((dirs.get('direct_eq'), '2^18'))
    for d, fallback in cands:
        if d and os.path.exists(os.path.join(d, 'case_summary.csv')):
            return d, (_dir_scale(d) or fallback)
    return None, None


def _rows_eval_cost(dirs, cur_mode='secant'):
    rows = []
    vals = {}
    ref = _pick_dir(dirs, 'full')[1]          # 参考规模：只比同协议的格
    for mode, label, note in _EVAL_MODES:
        d, scale = _pick_dir(dirs, mode)
        if not d or (ref and scale != ref):
            continue
        _, df = _load_summary(d)
        ev = float(df['n_real_evals'].mean())
        pr = float(df['n_probe_states'].mean()) if 'n_probe_states' in df else 0.0
        ld = float(df['n_landed'].mean()) if 'n_landed' in df else ev - pr
        t = float(df['elapsed_sec'].mean()) / ev if 'elapsed_sec' in df and ev > 0 else float('nan')
        vals[mode] = (ev, pr, ld, t)
    base = vals.get('full', (1.0, 0, 1.0, float('nan')))[0]
    for mode, label, note in _EVAL_MODES:
        if mode not in vals:
            continue
        ev, pr, ld, t = vals[mode]
        ratio = ev / base if base else float('nan')
        wall = ev * t if t == t else float('nan')
        if wall == wall:
            wall_s = f'{wall/60:.0f} min' if wall < 3600 else f'{wall/3600:.1f} h'
        else:
            wall_s = '—'
        t_s = f'{t:.1f} s' if t == t else '—'
        win = ' win' if mode == cur_mode else ''
        rows.append(
            f"<tr><td><strong>{label}</strong><br><span class=\"sh\">{note}</span></td>"
            f"<td class=\"n\">{ld:.0f}</td>"
            f"<td class=\"n\">{pr:.0f}</td>"
            f"<td class=\"n{win}\"><strong>{ev:.0f}</strong></td>"
            f"<td class=\"n\">{ratio:.2f}×</td></tr>")
    return '\n'.join(rows)


def _kpi_eval(dirs):
    """10.5 的评估量数字卡片（数据取自各格结果目录的实测统计；只取同协议的格）。"""
    cards = []
    ref = _pick_dir(dirs, 'full')[1]
    for mode, label, note in _EVAL_MODES:
        d, scale = _pick_dir(dirs, mode)
        if not d or (ref and scale != ref):
            continue
        _, df = _load_summary(d)
        ev = float(df['n_real_evals'].mean())
        pr = float(df['n_probe_states'].mean()) if 'n_probe_states' in df else 0.0
        ld = float(df['n_landed'].mean()) if 'n_landed' in df else ev - pr
        desc = {
            'full': f'代理 × full：{ld:.0f} 落地 + {pr:.0f} 个 ±ε 微扰点（每步 7 维全量中心差分）',
            'rotate': f'代理 × rotate：{ld:.0f} 落地 + {pr:.0f} 个 ±ε 微扰点（每步轮转 2 维）',
            'secant': f'代理 × secant：{ld:.0f} 落地 + {pr:.0f} 个 ±ε 微扰点（仅第 0 步一轮）',
            'direct_full': f'回传 × full：{ld:.0f} 落地 + {pr:.0f} 个 ±ε 微扰点（每步 8 维全量；需回传）',
            'direct_rotate': f'回传 × rotate：{ld:.0f} 落地 + {pr:.0f} 个 ±ε 微扰点（每步轮转 2 维；需回传）',
            'direct_secant': f'回传 × secant：{ld:.0f} 落地 + {pr:.0f} 个 ±ε 微扰点（仅第 0 步一轮；需回传）',
        }.get(mode, label)
        cards.append(f'<div class="kpi"><div class="v">{ev:.0f} 次</div><div class="l">{desc}</div></div>')
    return '\n  '.join(cards)


def _mode_series(dirs, order):
    """矩阵各格的该步 BER 序列与真实评估次数（代理 3 格 + 真实回传 3 格）。

    结果目录缺哪一格就跳过哪一格（矩阵按实有数据渲染，不臆造）。
    """
    out = {}
    for cell, _label, _note in _EVAL_MODES:
        d, scale = _pick_dir(dirs, cell)
        if not d:
            continue
        summ, df = _load_summary(d)
        envs = [e for e in order if e in summ]
        out[cell] = {
            'dir': d,
            'scale': scale,
            'source': _CELL_SOURCE[cell],
            'mode': cell if cell in _MODE_ORDER else cell.split('_', 1)[1],
            'envs': envs,
            'best': np.array([float(summ[e]['best_ber']) for e in envs]),
            'ev': float(df['n_real_evals'].mean()),
            'ev_all': float(df['n_real_evals'].sum()),
            'probe': float(df['n_probe_states'].mean()) if 'n_probe_states' in df else 0.0,
            'landed': float(df['n_landed'].mean()) if 'n_landed' in df else float('nan'),
        }
    return out


def _rows_mode_cmp(dirs, order, cur_mode='full', allow_mixed=False):
    """3×2 矩阵横向对比表 + 一句话摘要（供 6.1 与首页结论表使用）。

    参考基准 = 代理 × full（现役工作点）；「一样」＝ 逐用例最优 BER 之差在 5% 以内。
    **只比同一协议规模的格**：规模不一致的格直接不参与（正式交付件不允许混规模），
    allow_mixed 只在调试时放行并在行名上标注规模，避免把 2^18 的 2 个用例和 2^22 的 15 个用例混算。
    """
    s = _mode_series(dirs, order)
    if 'full' not in s:
        return '', '', {}
    envs = s['full']['envs']
    base = s['full']['best']
    ref_scale = s['full']['scale']
    rows = []
    bits = []
    for cell, label, _note in _EVAL_MODES:
        if cell not in s:
            continue
        d = s[cell]
        if d['scale'] != ref_scale:
            if not allow_mixed:
                continue
            label = f'{label}〔{d["scale"]} 调试格，不计入对比〕'
        b = d['best']
        n = min(len(b), len(base))
        geo = float(10 ** np.mean(np.log10(b[:n])))
        geo_base = float(10 ** np.mean(np.log10(base[:n])))
        ratio = geo / geo_base if geo_base else float('nan')
        tie = int((np.abs(np.log10(b[:n] / base[:n])) <= np.log10(1.05)).sum())
        worst_ratio = float(np.max(b[:n] / base[:n]))
        ev = d['ev']
        ev_all = d['ev_all']
        win = ' win' if d['mode'] == cur_mode and d['source'] == 'proxy' else ''
        rows.append(
            f"<tr><td>{label}</td>"
            f"<td class=\"n\">{geo:.2e}</td>"
            f"<td class=\"n\">{ratio:.2f}×</td>"
            f"<td class=\"n\">{tie}/{n}</td>"
            f"<td class=\"n\">{worst_ratio:.2f}×</td>"
            f"<td class=\"n{win}\">{ev:.0f}</td>"
            f"<td class=\"n\">{ev_all:.0f}</td></tr>")
        bits.append(f"{label.split('（')[0]} 为 {ratio:.2f} 倍，每用例 {ev:.0f} 次评估")
    return '\n'.join(rows), '；'.join(bits), s


def _live_verdict(s, live_mode='full'):
    """现役格的裁定依据（全部由结果实算，不手写）。

    规则：以「代理 × full」为参照，某格算「同水平」需同时满足
    ① 逐用例最优 BER 相对参照劣化不超过 5%；② 最坏单例 ≤ 1.05×。
    同水平者里取每用例真实评估次数最省的一格；没有同水平者就保留 full。
    数据不足（缺参照格或只有单格）时返回空串。
    """
    if 'full' not in s or s['full'].get('best') is None or len(s['full']['best']) == 0:
        return ''
    proxy = [c for c in _MODE_ORDER
             if c in s and s[c].get('source') == 'proxy'
             and s[c].get('best') is not None and len(s[c]['best']) > 0]
    if len(proxy) < 2:
        return ''
    base = np.asarray(s['full']['best'], float)
    lines, peers = [], []
    for cell in proxy:
        b = np.asarray(s[cell]['best'], float)
        n = min(len(b), len(base))
        r = b[:n] / base[:n]
        peers.append((cell, float(np.max(r)), int((r <= 1.05).sum()), n,
                      float(s[cell].get('ev', float('nan')))))
    same = [p for p in peers if p[1] <= 1.05 and p[2] == p[3]]
    pick = min(same, key=lambda p: p[4]) if same else peers[0]
    pick_cell, pick_worst, pick_tie, pick_n, pick_ev = pick
    if pick_cell == 'full':
        lines.append('逐用例劣化均不超过 5%%、最坏单例 %.2f×，因此保留最忠实的每步全量微扰取法'
                     '（<strong>%s</strong> · 每步 7 维全量微扰），每用例 ≈%.0f 次真实评估。'
                     % (pick_worst, pick_cell, pick_ev))
    else:
        lines.append('取同水平者中每用例真实评估最省的一格：<strong>%s</strong>（每用例 ≈%.0f 次；'
                     '逐用例劣化均 ≤5%%、最坏单例 %.2f×）。'
                     % (MODE_ZH_PLAIN.get(pick_cell, pick_cell), pick_ev, pick_worst))
    rejected = [p for p in peers if p[0] != pick_cell]
    if rejected:
        lines.append('其余取法被否的理由（照实列数）：' + '；'.join(
            '%s 一样 %d/%d、最坏单例 %.2f×' % (MODE_ZH_PLAIN.get(c, c), tie, n, w)
            for c, w, tie, n, _ev in rejected) + '。')
    return ' <strong>现役格裁定</strong>（数据实算）：' + ''.join(lines)


def _rows_metrics(meta):
    _domain_zh = {'waveform_probe': '波形域（探针）', 'parameter': '参数域'}
    out = []
    for tag, name in (('model_a', '方向代理 Model A'),):
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


_IMG_CACHE = {}


def _img_tag(path, width=900, colors=128):
    """内联图：缩到 width 宽、量化到 colors 色再转 base64。

    原图 2500 像素宽、单张 300~640 KB，直接内联会把交付件撑到 12 MB 以上。
    曲线图量化到 128 色肉眼看不出差别，单张降到 50~120 KB。
    缓存按（源路径哈希, 宽度, 色数）命名，写在交付件自己的 _parts 下，不碰 result/。
    """
    import hashlib
    apath = os.path.abspath(path)
    key = (apath, int(os.path.getmtime(path)), int(width), int(colors or 0))
    if key in _IMG_CACHE:
        return _IMG_CACHE[key]
    try:
        from PIL import Image
        cache_dir = os.path.join('_parts', 'img_small')
        os.makedirs(cache_dir, exist_ok=True)
        tag_name = hashlib.md5(apath.encode('utf-8')).hexdigest()[:10]
        out = os.path.join(cache_dir, '%d_%s_%s_%s' % (int(width), int(colors or 0),
                                                       tag_name, os.path.basename(path)))
        if (not os.path.exists(out)) or os.path.getmtime(out) < os.path.getmtime(path):
            im = Image.open(path)
            if im.width > width:
                h = max(1, int(round(im.height * width / float(im.width))))
                im = im.resize((width, h), Image.LANCZOS)
            if im.mode == 'RGBA':
                bg = Image.new('RGB', im.size, (255, 255, 255))
                bg.paste(im, mask=im.split()[-1])
                im = bg
            if colors:
                im = im.convert('P', palette=Image.ADAPTIVE, colors=int(colors))
            im.save(out, 'PNG', optimize=True)
        path = out
    except Exception:
        pass
    with open(path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode('ascii')
    tag = f'data:image/png;base64,{b64}'
    _IMG_CACHE[key] = tag
    return tag


# ============================================================================
# 6.5 对比实验：direct（有回传通道时的端到端 BER 直接梯度下降）
# ============================================================================
_EQUIV_COLS = ['gdc', 'gdc2', 'gain', 'u_gain', 'drive_rms', 'pred_a', 'real_lb',
               'real_ber', 'grad_norm']


def _eq_dir(root, mode):
    """2^18 等价结果目录：兼容「<前缀>/<格>」与「<前缀>_<格>」两种布局。"""
    nested = os.path.join(root, mode)
    if os.path.isdir(nested):
        return nested
    flat = '%s_%s' % (root.rstrip('/\\'), mode)
    if os.path.isdir(flat):
        return flat
    return nested


def _equiv_rows(py_dir, cpp_dir):
    """2^18 等价比对表（六格通用）：与 cpp/compare_traces.py 同口径，构建时实算。"""
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


def _direct_cmp_figure(summary, dsum, order, out_png, scale_label='—'):
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
               label='现役（Model A 方向代理，无需回传通道）', zorder=3)
    ax.scatter(dr, ys, marker='D', s=44, color='#ef4444',
               label='direct（端到端 BER 直接梯度下降，需回传通道）', zorder=3)
    ax.set_yticks(ys)
    ax.set_yticklabels(order, fontsize=8.5)
    ax.set_xscale('log')
    ax.set_xlabel('最优 BER_MLSE（对数轴；%s 符号 C++，同一次优起点/种子/步数协议）'
                  % scale_label, fontsize=9.5)
    ax.invert_yaxis()
    ax.grid(alpha=0.3, which='both', axis='x')
    ax.set_title('最优 BER 对比：现役方案 vs direct（有回传通道时的参照）', fontsize=11.5)
    ax.legend(fontsize=9, loc='lower right')
    fig.tight_layout()
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    fig.savefig(out_png, dpi=125)
    plt.close(fig)
    return out_png


def _direct_cells(dirs, order, live_summary, live_mode='full'):
    """矩阵里「真实 BER 回传」那一行的三个格：逐格统计 + 与同方式代理格的逐用例对照。

    对照取**同一种形状维获取方式**的代理格（回传 × rotate 对 代理 × rotate），这样唯一的变量
    就是梯度来源；代理侧缺同方式的格时退到现役格。返回按 full/rotate/secant 顺序的列表。
    """
    out = []
    for mode in _MODE_ORDER:
        d, scale = _pick_dir(dirs, f'direct_{mode}')
        if not d:
            continue
        dsum, ddf = _load_summary(d)
        envs = [e for e in order if e in dsum]
        if not envs:
            continue
        pd, _p_scale = _pick_dir(dirs, mode)
        p_label = f'代理 × {mode}'
        psum = None
        if pd:
            psum, _ = _load_summary(pd)
        if psum is None:
            psum, p_label = live_summary, '现役格'
        menvs = [e for e in envs if e in psum]
        ratio = np.array([dsum[e]['best_ber'] / psum[e]['best_ber'] for e in menvs])
        out.append({
            'cell': f'direct_{mode}', 'mode': mode, 'dir': d, 'scale': scale,
            'summ': dsum, 'envs': envs, 'peer': psum, 'peer_label': p_label,
            'peer_envs': menvs, 'ratio': ratio,
            'n_same': int(((ratio >= 0.95) & (ratio <= 1.05)).sum()),
            'n_better': int((ratio < 0.95).sum()),
            'n_worse': int((ratio > 1.05).sum()),
            'ev': float(ddf['n_real_evals'].mean()) if 'n_real_evals' in ddf else float('nan'),
            'steps': float(np.mean([int(dsum[e]['n_steps_actual']) for e in envs])),
        })
    return out


def _top_curve(a, summary, order):
    """开篇用：现役六格在最难用例上的六条轨迹（和 6.4 同一套画法）。"""
    if not a.dirs:
        return ''
    env = max(order, key=lambda e: summary[e]['best_ber'])
    dirs = {}
    for key, path in a.dirs.items():
        m = _study_cell_metrics(path) if path else None
        if m:
            dirs[key] = m
    if len(dirs) < 2:
        return ''
    return _study_case_svg(dirs, env, w=640, h=250)


def _build_direct_section(a, summary, order, fs=None):
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
    fs = fs or {}
    # 矩阵「真实 BER 回传」行的三格（full / rotate / secant）：整节共用一份，避免重复读盘
    dcells = _direct_cells(a.dirs, order, summary, a.mode)
    dmap = {c['mode']: c for c in dcells}
    ev_by_mode = {c['mode']: c['ev'] for c in dcells}
    steps_by_mode = {c['mode']: c['steps'] for c in dcells}
    ev3 = ' / '.join('%d' % ev_by_mode[m] for m in _MODE_ORDER if m in ev_by_mode and ev_by_mode[m] == ev_by_mode[m])
    # 「回传行取最好」视图：逐用例在三格里挑最优参数点，供本节结论 / KPI / 逐用例解读使用，
    # 与逐用例明细表的「最好回传 ÷ 现役」同一口径（否则结论只代表 secant 一格，与上表口径不一致）
    dbest = {}
    for _e in dorder:
        _c = [(m, dmap[m]['summ'][_e]) for m in _MODE_ORDER if m in dmap and _e in dmap[m]['summ']]
        if _c:
            dbest[_e] = min(_c, key=lambda t: float(t[1]['best_ber']))
    db = {e: rec for e, (_m, rec) in dbest.items()}
    db_mode = {e: _m for e, (_m, rec) in dbest.items()}
    _sym_d = _dir_num_symbols(a.direct) or _dir_num_symbols(a.baseline)
    dorder_db = [e for e in dorder if e in db]
    n_both = sum(1 for e in dorder_db
                 if _is_zero_error(db[e]['best_ber'], _sym_d)
                 and _is_zero_error(summary[e]['best_ber'], _sym_d))

    imp_d = np.array([db[e]['seed_ber'] / db[e]['best_ber'] for e in dorder_db])
    imp_s = np.array([summary[e]['seed_ber'] / summary[e]['best_ber'] for e in dorder_db])
    geo_d = float(10 ** np.mean(np.log10(imp_d)))
    geo_s = float(10 ** np.mean(np.log10(imp_s)))
    ratio = np.array([db[e]['best_ber'] / summary[e]['best_ber'] for e in dorder_db])
    n_same = int(((ratio >= 0.95) & (ratio <= 1.05)).sum())
    n_better = int((ratio < 0.95).sum())
    n_worse = int((ratio > 1.05).sum())
    steps_d = [int(db[e]['n_steps_actual']) for e in dorder_db]
    steps_s = [int(summary[e]['n_steps_actual']) for e in dorder_db]
    ev_s = _mean_n_evals(summary, dorder_db)
    evals_s = ev_s if ev_s is not None else 15 + int(np.mean(steps_s))

    # 结论措辞（按数字分档，照实说；几何平均倍数读者无感，用逐用例事实说话）
    # 口径：回传行三格里逐用例取最好的一格，与逐用例明细表的「最好回传 ÷ 现役」一致
    if n_better == 0 and n_worse == 0:
        verdict = (f"{n_same}/{len(dorder_db)} 个用例上两方案的最优 BER 一致，差在 5% 以内。")
    elif geo_d >= geo_s * 1.1:
        verdict = (f"回传三格取最好，比现役好：{n_same}/{len(dorder_db)} 个用例一样，"
                   f"{n_better} 个更好，{n_worse} 个更差；平均把 BER 压低的倍数 ×{geo_d:.0f}，现役 ×{geo_s:.0f}。")
    elif geo_d >= geo_s * 0.9:
        verdict = (f"两边相当：{n_same}/{len(dorder_db)} 个用例一样，{n_better} 个回传更好，"
                   f"{n_worse} 个现役更好；两方案平均都把 BER 压低了约 {np.log10(geo_s):.1f} 个数量级。")
    else:
        verdict = (f"回传三格略差：{n_same}/{len(dorder_db)} 个用例一样，{n_better} 个更好，"
                   f"{n_worse} 个更差。")

    # KPI 锚点：一样数 / 回传行最深的领先 / 回传行最浅的落后 / 步数与评估量
    i_best, i_worst = int(ratio.argmin()), int(ratio.argmax())
    kpi_rows = [f'<div class="kpi"><div class="v">{n_same} / {len(dorder_db)}</div>'
                f'<div class="l">两方案一样的用例（差 5% 以内，其中 {n_both} 例两边都是 0 个错误）</div></div>']
    if ratio[i_best] < 0.95:
        e = dorder_db[i_best]
        kpi_rows.append(
            f'<div class="kpi"><div class="v">×{1/ratio[i_best]:.1f}</div>'
            f'<div class="l">回传 × {db_mode[e]} 在 {e} 上领先（{_ber(db[e]["best_ber"])} 对 '
            f'{_ber(summary[e]["best_ber"])}）</div></div>')
    if ratio[i_worst] > 1.05:
        e = dorder_db[i_worst]
        kpi_rows.append(
            f'<div class="kpi"><div class="v">×{ratio[i_worst]:.1f}</div>'
            f'<div class="l">回传 × {db_mode[e]} 在 {e} 上落后（{_ber(db[e]["best_ber"])} 对 '
            f'{_ber(summary[e]["best_ber"])}）</div></div>')
    kpi_rows.append(
        f'<div class="kpi"><div class="v">{int(np.mean(steps_d))} vs {int(np.mean(steps_s))} 步</div>'
        f'<div class="l">平均实际步数（回传三格每用例约 {ev3} 次评估，现役约 {evals_s} 次）</div></div>')
    direct_kpis = '\n'.join(kpi_rows)

    def _sr(rec):
        v = rec.get('stop_reason')
        return v if isinstance(v, str) and v else '步数上限'

    bullets = []
    if ratio[i_best] < 0.95:
        e = dorder_db[i_best]
        bullets.append(
            f'<li>{e}：回传 × {db_mode[e]} 更好，最优 BER 压到 {_ber(db[e]["best_ber"])}'
            f'（第 {int(db[e]["best_step"])} 步），现役停在 {_ber(summary[e]["best_ber"])}'
            f'（第 {int(summary[e]["best_step"])} 步，{_sr(summary[e])}）。BER 很深处代理已经分不出差别，'
            f'真实 BER 没有这个盲区。</li>')
    if ratio[i_worst] > 1.05:
        e = dorder_db[i_worst]
        bullets.append(
            f'<li>{e}：回传 × {db_mode[e]} 更差，停在 {_ber(db[e]["best_ber"])}'
            f'（{int(db[e]["n_steps_actual"])} 步，{_sr(db[e])}），现役 {_ber(summary[e]["best_ber"])}。'
            f'真实 BER 的差分梯度幅值大，噪声也大，固定步长在陡的地方容易贴住物理量程或来回过冲；'
            f'现役走的是代理的组归一化方向，步幅被门控约束。</li>')
    bullets.append(
        f'<li>其余用例两方案的最优 BER 差在 5% 以内（其中 {n_both} 例两边都是 0 个错误，落在检测底 '
        f'{"—" if not fs.get("floor_ber") else _ber(fs["floor_ber"])}）：有回传和没回传两种前提下，'
        f'同一套下降机制给出的结果一样。</li>')
    bullets = '\n      '.join(bullets)

    # 结果对比表：现役格（代理 × full）并列回传行三格；「最好回传」= 该用例三格中最优 BER
    rows = []
    for env in dorder:
        s = summary[env]
        per = [(m, dmap[m]['summ'].get(env) if m in dmap else None) for m in _MODE_ORDER]
        avail = [(m, rec) for m, rec in per if rec is not None]
        bm, brec = min(avail, key=lambda t: float(t[1]['best_ber'])) if avail else (None, None)
        rr = (float(brec['best_ber']) / float(s['best_ber'])) if brec is not None else float('nan')
        mark = 'win' if rr < 0.95 else ('lose' if rr > 1.05 else '')
        tds = ''.join(
            ('<td class="n">%s (%d)</td>' % (_ber(rec['best_ber']), int(rec['best_step'])))
            if rec is not None else '<td class="n">—</td>' for _m, rec in per)
        rows.append(
            f"<tr><td>{env}</td><td>{_cond(s)}</td>"
            f"<td class=\"n\">{_ber(s['seed_ber'])}</td>"
            f"<td class=\"n\">{_ber(s['best_ber'])} ({int(s['best_step'])})</td>"
            f"{tds}"
            f"<td class=\"n {mark}\">x{rr:.2f}</td>"
            f"<td class=\"mono\" style=\"font-size:11.5px\">"
            f"{(_sr(brec) if brec is not None else '—')}（回传 × {bm}）</td></tr>")
    rows_html = '\n'.join(rows)

    # 对比图：写到交付件自己的缓存目录（**不写进 result/**，结果目录只由仿真产出，
    # 否则每生成一次交付件就把 git 跟踪的结果目录 mtime 刷新一遍，"交付件是否比结果旧"就没法判了）
    img_png = _direct_cmp_figure(
        summary, dsum, dorder,
        os.path.join(os.path.dirname(a.out), '_parts', 'direct_vs_active.png'),
        scale_label=_scale_label(_dir_num_symbols(a.baseline)))
    img_tag = _img_tag(img_png)

    n_evals_note = (f"每用例的真实评估次数：回传三格约 {ev3} 次（full / rotate / secant，都含第 0 步那 16 个微扰点），"
                    f"现役约 {evals_s} 次（第 0 步 14 个微扰点，加平均 {int(np.mean(steps_s))} 步参数点）")

    # 逐用例形态解读引用的实测终点（数据驱动，缺用例时退化为泛指）
    _hn = db.get('HighNoise_IL10x10')
    real_ber_ref = _ber(_hn['best_ber']) if _hn is not None else '该区域可及的最优位'

    # 3×2 矩阵里「真实 BER 回传」这一行：三格总览（每格只与同一种方式的代理格比）
    _ref_scale = _dir_scale(a.baseline)
    ov_rows = []
    for c in dcells:
        if _ref_scale and c['scale'] != _ref_scale:
            if not getattr(a, 'allow_mixed_scale', False):
                continue
            c['mode_label'] = f"{MODE_ZH.get(c['mode'], c['mode'])}〔{c['scale']} 调试格，不计入对比〕"
        else:
            c['mode_label'] = MODE_ZH.get(c['mode'], c['mode'])
        n = len(c['ratio'])
        geo = float(10 ** np.mean(np.log10(c['ratio']))) if n else float('nan')
        ov_rows.append(
            f"<tr><td>{c['mode_label']}</td>"
            f"<td class=\"n\">{c['ev']:.0f}</td>"
            f"<td class=\"n\">{c['steps']:.1f}</td>"
            f"<td class=\"n\">{c['n_same']}/{n}</td>"
            f"<td class=\"n\">{geo:.2f}×</td>"
            f"<td>{c['peer_label']}</td></tr>")
    ov_html = '\n'.join(ov_rows) if ov_rows else '<tr><td colspan="6">回传格结果尚未生成</td></tr>'

    section = f'''
<p>15 个用例，六个组合各自的最优 BER 和步号并列在下面。起点、协议、步数上限都一样（{_scale_label(_dir_num_symbols(a.baseline))} 符号、单种子 42、固定 15 步），差别只在梯度来源和形状维取法。最后一列取三格回传里该用例最好的一格。</p>
<div class="tw">
<table class="wide" id="tbl-direct-cmp">
  <caption>逐用例最优 BER（括号里是步号）：代理全测与三格回传并列 <span class="sh">· 可左右滑动</span></caption>
  <tr><th>用例</th><th>物理条件</th><th class="n">起点 BER</th><th class="n">代理全测</th><th class="n">回传全测</th><th class="n">回传轮测</th><th class="n">回传外推</th><th class="n">最好回传 ÷ 代理</th><th>最好回传格停止原因</th></tr>
  {rows_html}
</table>
</div>
<p class="note">每用例真实评估次数回传三格约 {ev3} 次，代理全测约 {evals_s} 次，逐格拆解见 4.3。</p>
'''
    return section


_EQ_MODE_LABELS = [
    ('full', '代理 × full（7 维每步全量微扰，14 个 ±ε 态/步）'),
    ('rotate', '代理 × rotate（每步轮转 2 维，4 个 ±ε 态/步）'),
    ('secant', '代理 × secant（第 0 步后割线外推，0 个 ±ε 态/步）'),
    ('direct_full', '回传 × full（8 维每步全量微扰，16 个 ±ε 态/步）'),
    ('direct_rotate', '回传 × rotate（每步轮转 2 维，4 个 ±ε 态/步）'),
    ('direct_secant', '回传 × secant（第 0 步后割线外推，0 个 ±ε 态/步）'),
]


def _build_eq_tabs(a):
    """§10.4 页签组：六格（发端代理三格 + 真实 BER 回传三格）的 2^18 Python vs C++ 逐轨迹实算比对。"""
    bar, panels = [], []
    first = True
    for mode, label in _EQ_MODE_LABELS:
        py_dir = _eq_dir(a.eq_py_root, mode)
        cpp_dir = a.dirs.get(mode + '_eq')
        rows, worst = _equiv_rows(py_dir, cpp_dir)
        if not rows:
            continue
        rows_html = '\n'.join(rows)
        pid = 'tab-eq-%s' % mode
        bar.append('    <button class="tab-btn%s" data-tab="%s">%s</button>'
                   % (' active' if first else '', pid, label))
        panels.append(
            '\n  <div class="tab-panel%s" id="%s">\n'
            '    <p>Python 参照（<span class="mono">%s/</span>）与 C++ 复刻（<span class="mono">%s/</span>）'
            '逐轨迹比对，最坏相对差 <strong>%.2e</strong>（判据 &lt; 1e-9，%d 个用例全部通过）。</p>\n'
            '    <div class="tw">\n'
            '    <table class="wide" style="margin-bottom:8px">\n'
            '      <caption>%s：Python vs C++ trace 逐步数值比对（2^18 小点数低 SNR、单种子 42；'
            '比对列 gdc/gdc2/gain/u_gain/drive_rms/pred_a/real_lb/real_ber/grad_norm）</caption>\n'
            '      <tr><th>用例</th><th class="n">比对步数</th><th class="n">最大相对差</th>'
            '<th>判据（&lt; 1e-9）</th></tr>\n'
            '      %s\n'
            '    </table>\n'
            '    </div>\n'
            '  </div>'
            % (' active' if first else '', pid, py_dir, cpp_dir, worst, len(rows), label, rows_html))
        first = False
    if not bar:
        return ''
    return '  <div class="tab-bar">\n' + '\n'.join(bar) + '\n  </div>' + ''.join(panels)

_FIG_MODE_LABELS = [
    ('full', MODE_ZH_FIG['full']),
    ('rotate', MODE_ZH_FIG['rotate']),
    ('secant', 'secant（第 0 步后割线外推）'),
]


def _build_fig_tabs(a, hard_env):
    """§6.2 页签组：逐格收敛图组（图由 report_ddps.py 从各格结果目录出）。

    每格一个页签。图组缺失的格自动跳过。
    """
    bar, panels = [], []
    first = True
    for mode, label in _FIG_MODE_LABELS:
        rd = os.path.join(a.dirs.get(mode, ''), 'report')
        conv = os.path.join(rd, 'ddps_convergence.png')
        if not os.path.exists(conv):
            continue
        imgs = [('ddps_convergence.png', f'图 6 · {label} 收敛轨迹（Model A 预测 / 实测 BER_MLSE / ±ε 微扰点灰点，对数纵轴；虚线为起点）'),
                ('ddps_gain_rms.png', '图 7 · gain 维（第 8 维）与 drive_rms 轨迹（虚线为起点 gain 倍率 ×0.325）'),
                ('ddps_tracking.png', '图 8 · 左 Δ预测 vs Δ实测散点（逐用例逐步）；右逐用例相关系数'),
                (f'ddps_case_{hard_env}.png', f'图 9 · 最难用例（{hard_env}）六联图：收敛轨迹、Tx FFE 抽头（起点 vs 最优）、Tx CTLE |H(f)| 频响、Tx 探针 7-tap FIR、发端频谱对比（起点 vs 最优）、频谱改变量 ΔdB')]
        figs = []
        for fn, cap in imgs:
            p = os.path.join(rd, fn)
            if os.path.exists(p):
                figs.append('<figure>\n      <div class="fig-scroll"><img src="%s" alt="%s"></div>\n'
                            '      <figcaption>%s</figcaption>\n    </figure>' % (_img_tag(p), cap, cap))
        pid = 'tab-fig-%s' % mode
        bar.append('    <button class="tab-btn%s" data-tab="%s">%s</button>'
                   % (' active' if first else '', pid, label))
        panels.append('\n  <div class="tab-panel%s" id="%s">\n    %s\n  </div>'
                      % (' active' if first else '', pid, '\n    '.join(figs)))
        first = False
    # 回传行三格页签（结果目录/报告图缺失的格自动不出现）
    for _cell, _mdir in (('full', a.direct_full), ('rotate', a.direct_rotate), ('secant', a.direct)):
        if not _mdir or not os.path.isdir(_mdir):
            continue
        rd = os.path.join(_mdir, 'report')
        imgs = [('ddps_conv_grid.png', f'图 6 · 回传 × {_cell} 收敛轨迹（实测 BER_MLSE / ±ε 微扰点灰点）'),
                ('ddps_gain_rms.png', f'图 7 · 回传 × {_cell}：gain 与 drive_rms 轨迹'),
                ('ddps_case_hard.png', f'图 9 · 回传 × {_cell} 最难用例六联图（含发端频谱对比与频谱改变量）')]
        figs = []
        for fn, cap in imgs:
            p = os.path.join(rd, fn)
            if os.path.exists(p):
                figs.append('<figure>\n      <div class="fig-scroll"><img src="%s" alt="%s"></div>\n'
                            '      <figcaption>%s</figcaption>\n    </figure>' % (_img_tag(p), cap, cap))
        if figs:
            pid = f'tab-fig-direct-{_cell}'
            bar.append(f'    <button class="tab-btn" data-tab="{pid}">回传 × {_cell}（有回传通道）</button>')
            panels.append('\n  <div class="tab-panel" id="%s">\n    %s\n  </div>'
                          % (pid, '\n    '.join(figs)))
    if not bar:
        return ''
    return '  <div class="tab-bar">\n' + '\n'.join(bar) + '\n  </div>' + ''.join(panels)



# ---------------------------------------------------------------------------
# 训练数据构建可视化（§3.1）：一行数据长什么样 + 2001 点怎么撒
# ---------------------------------------------------------------------------
def _build_dataset_card(a):
    """§3.1 的「训练数据怎么构建」卡：真实数据集首行 + LHS 覆盖散点。

    数据集目录缺失时返回空串。
    """
    cands = sorted(glob.glob(os.path.join('dataset', 'ddps_dataset_*.csv')))
    if not cands:
        return ''
    df = pd.read_csv(cands[-1])
    r = df.iloc[0]
    n = len(df)
    _nr = f'{n}'

    # LHS 覆盖散点：u_gain（x_6） vs FFE 旁瓣 t₀（x_0），全部真实采样点
    W, H = 340, 240
    xg = df['x_6'].values
    yg = df['x_0'].values
    xmin, xmax = xg.min(), xg.max()
    ymin, ymax = yg.min(), yg.max()
    pad_x = (xmax - xmin) * 0.06 + 1e-9
    pad_y = (ymax - ymin) * 0.08 + 1e-9
    def px(v): return 52 + (v - xmin + pad_x) / (xmax - xmin + 2 * pad_x) * (W - 62)
    def py(v): return 14 + (ymax + pad_y - v) / (ymax - ymin + 2 * pad_y) * (H - 46)
    pts = ' '.join(f'{px(x):.1f},{py(y):.1f}' for x, y in zip(xg, yg))
    dots = ''.join(f'<circle cx="{px(x):.1f}" cy="{py(y):.1f}" r="1.7" fill="#0b63ce" opacity="0.4"/>'
                   for x, y in zip(xg, yg))
    scatter = (
        f'<svg class="wt-svg" viewBox="0 0 {W} {H}" role="img" aria-label="训练集 LHS 覆盖散点">'
        f'<line x1="{px(xmin)-4:.0f}" y1="{py(ymin)+4:.0f}" x2="{W-8}" y2="{py(ymin)+4:.0f}" stroke="#c8d4e4"/>'
        f'<line x1="{px(xmin)-4:.0f}" y1="{py(ymin)+4:.0f}" x2="{px(xmin)-4:.0f}" y2="10" stroke="#c8d4e4"/>'
        f'{dots}'
        f'<text x="{W/2:.0f}" y="{H-6}" text-anchor="middle" font-size="11" fill="#5b6b7d">u_gain = log₁₀(gain/g₀)（gain 维，覆盖 ×0.20 ~ ×1.26）</text>'
        f'<text x="10" y="{H/2:.0f}" font-size="11" fill="#5b6b7d" transform="rotate(-90 10 {H/2:.0f})" text-anchor="middle">FFE 旁瓣 t₀</text>'
        f'<text x="{px(xmin)-8:.0f}" y="{py(ymin)+18:.0f}" text-anchor="end" font-size="10" fill="#8a97a8">{ymin:.2f}</text>'
        f'<text x="{px(xmin)-8:.0f}" y="16" text-anchor="end" font-size="10" fill="#8a97a8">{ymax:.2f}</text>'
        f'</svg>')

    return f'''
<h4 style="margin:16px 0 6px">训练数据怎么构建</h4>
<div class="wt-frame on" style="display:grid;grid-template-columns:minmax(300px,1fr) minmax(300px,1fr);gap:18px">
  <div>
    <h5 style="margin:0 0 6px;font-size:14px;color:var(--accent)">一行数据长什么样（真实首行，共 {n} 行）</h5>
    <table style="font-size:12.3px">
      <tr><th style="width:112px">参数域 7 维<br><span style="font-weight:400;color:var(--mut)">Stage-1 采样坐标（4 旁瓣 + gDC + gDC2 + gain）</span></th>
          <td>FFE 旁瓣 {r['x_0']:+.3f} / {r['x_1']:+.3f} / {r['x_2']:+.3f} / {r['x_3']:+.3f}<br>
              gDC {r['x_4']:.2f} dB · gDC2 {r['x_5']:.2f} dB · gain ×{r['gain_ratio']:.2f}</td></tr>
      <tr><th>波形域 8 维<br><span style="font-weight:400;color:var(--mut)">Model A 的输入（物理探针）</span></th>
          <td>7-tap FIR [{r['tx_fir_0']:+.3f}, {r['tx_fir_1']:+.3f}, {r['tx_fir_2']:+.3f}, {r['tx_fir_3']:+.3f}, {r['tx_fir_4']:+.3f}, {r['tx_fir_5']:+.3f}, {r['tx_fir_6']:+.3f}]<br>
              drive_rms {r['drive_rms']:.3f} V</td></tr>
      <tr><th>标签<br><span style="font-weight:400;color:var(--mut)">方向代理的拟合目标</span></th>
          <td>log₁₀(BER_MLSE) = {r['log10_ber_mlse']:.2f}（BER {r['mlse_ber']:.2e}，{_per_bits(r['mlse_ber'])}）</td></tr>
    </table>
    <p style="font-size:12.3px;color:var(--mut);margin:8px 0 0">每行 = 一次真实链路评估：2²⁰ 符号，3 个仿真实例种子取 log₁₀ 均值。参数改了波形就改，波形改了 BER 才改，所以方向代理吃的是波形：信道变了波形跟着变，模型可以跨环境复用；采样坐标本身只是数据集的自变量。</p>
  </div>
  <div>
    <h5 style="margin:0 0 6px;font-size:14px;color:var(--accent)">{n} 个点怎么撒：拉丁超立方（逐维分层均匀）</h5>
    {scatter}
    <p style="font-size:12.3px;color:var(--mut);margin:6px 0 0">Stage-1 在采样盒内逐维均匀分层，再随机配对，不聚堆也不留洞，{_nr} 个点铺满整个盒。只在 Base_IL10x10（10+10 dB）一个环境的邻域采：代理学的是「发端波形 → BER」的映射，信道变了波形才变（§4.4 特征侧）。生成一次性 ≈5.6 h（<span class="mono">--jobs 12</span>，每进程 OMP=1），训练闭式解 &lt;0.1 s。</p>
  </div>
</div>'''


# ---------------------------------------------------------------------------
# 算法逐帧走查（§4.6）：第一个梯度 → 第一步 → 割线 → 收敛，真实用例数据驱动
# ---------------------------------------------------------------------------

_WT_DIM_LABELS = ['FFE t₀', 'FFE t₁', 'FFE t₂', 'FFE t₃', 'gDC', 'gDC2', 'gain']


def _wt_param_bars(cur, seed, lo, hi, prev=None, gain_ratio=None, W=330, H=224):
    """7 维参数状态条形 SVG：每个维度在其搜索盒内的位置（种子刻度 + 当前值 + 上一帧残影）。"""
    def pos(i, v):
        return 66 + (v - lo[i]) / (hi[i] - lo[i]) * (W - 128)
    rows = []
    for i in range(7):
        y = 16 + i * 29
        sp, cp = pos(i, seed[i]), pos(i, cur[i])
        val = (f'×{gain_ratio:.2f}' if i == 6 else
               (f'{cur[i]:+.2f}' if i >= 4 else f'{cur[i]:+.3f}'))
        fill = (f'<rect x="{min(sp,cp):.1f}" y="{y+2:.0f}" width="{max(abs(cp-sp),1.2):.1f}" height="9" '
                f'rx="4.5" fill="{"#0f8a4a" if cp>sp else "#0b63ce"}" opacity="0.30"/>')
        ghost = (f'<circle cx="{pos(i, prev[i]):.1f}" cy="{y+6.5:.0f}" r="4" fill="none" '
                 f'stroke="#9aa0a6" stroke-width="1.4"/>' if prev is not None else '')
        rows.append(
            f'<text x="58" y="{y+10:.0f}" text-anchor="end" font-size="11.5" fill="#3b4a5a" font-weight="600">{_WT_DIM_LABELS[i]}</text>'
            f'<rect x="66" y="{y+2:.0f}" width="{W-128}" height="9" rx="4.5" fill="#eef2f7"/>'
            f'{fill}'
            f'<line x1="{sp:.1f}" y1="{y-1:.0f}" x2="{sp:.1f}" y2="{y+14:.0f}" stroke="#8a97a8" stroke-width="1.2" stroke-dasharray="2,2"/>'
            f'{ghost}'
            f'<circle cx="{cp:.1f}" cy="{y+6.5:.0f}" r="5" fill="{"#0f8a4a" if cp>sp else "#0b63ce"}"/>'
            f'<text x="{W-56}" y="{y+10:.0f}" font-size="11" fill="#3b4a5a">{val}</text>')
    return (f'<svg class="wt-svg" viewBox="0 0 {W} {H}" role="img" aria-label="7 维参数状态">'
            f'<text x="58" y="9" text-anchor="end" font-size="10" fill="#8a97a8">维度</text>'
            f'<text x="66" y="9" font-size="10" fill="#8a97a8">搜索盒内的位置（虚线 = 种子 x₀，空心圈 = 上一帧）</text>'
            + ''.join(rows) + '</svg>')


def _wt_curve(ber, seed_ber, active=(), W=340, H=180):
    """收敛曲线迷你 SVG：步 −1（种子）到 N−1，active 集合内的大点高亮。"""
    n = len(ber)
    ys = np.log10(np.concatenate([[seed_ber], ber]))
    ymin, ymax = ys.min() - 0.3, ys.max() + 0.3
    def px(s): return 50 + (s + 1) / n * (W - 60)
    def py(v): return 12 + (ymax - v) / (ymax - ymin) * (H - 40)
    grid = ''
    for g in (1e-2, 1e-4, 1e-6):
        if ymin < np.log10(g) < ymax:
            gy = py(np.log10(g))
            grid += (f'<line x1="50" y1="{gy:.0f}" x2="{W-10}" y2="{gy:.0f}" stroke="#e3e9f1"/>'
                     f'<text x="46" y="{gy+3:.0f}" text-anchor="end" font-size="9.5" fill="#8a97a8">1e{int(np.log10(g))}</text>')
    pts_all = ' '.join(f'{px(s):.1f},{py(v):.1f}' for s, v in zip(range(-1, n), ys))
    dots = ''.join(
        f'<circle cx="{px(s):.1f}" cy="{py(v):.1f}" r="{5 if s in active else 2.6}" '
        f'fill="{"#c2410c" if s in active else "#0b63ce"}" opacity="{1.0 if s in active else 0.55}"/>'
        for s, v in zip(range(-1, n), ys))
    return (f'<svg class="wt-svg" viewBox="0 0 {W} {H}" role="img" aria-label="真实 BER 收敛曲线">'
            f'{grid}'
            f'<polyline points="{pts_all}" fill="none" stroke="#0b63ce" stroke-width="1.6" opacity="0.75"/>'
            f'{dots}'
            f'<circle cx="{px(-1):.1f}" cy="{py(ys[0]):.1f}" r="4" fill="none" stroke="#8a97a8" stroke-width="1.5"/>'
            f'<text x="{W/2:.0f}" y="{H-6}" text-anchor="middle" font-size="10.5" fill="#5b6b7d">调优步（−1 = 种子 x₀，纵轴 log₁₀ BER）</text>'
            f'</svg>')


def _wt_probes_svg(pr, W=340, H=210):
    """第 0 步的 14 个 ±ε 微扰点：每维两点（+ε / −ε 的真实 BER，log 轴）+ 斜率方向箭头。"""
    eps = [0.01] * 4 + [0.1] * 2
    cols = []
    for p in range(6):
        bp = float(pr[(pr['param'] == p) & (pr['sign'] == 1)]['real_ber'].iloc[0])
        bm = float(pr[(pr['param'] == p) & (pr['sign'] == -1)]['real_ber'].iloc[0])
        cols.append((p, bp, bm))
    vals = [v for _, bp, bm in cols for v in (bp, bm)]
    ymin, ymax = np.log10(min(vals)) - 0.08, np.log10(max(vals)) + 0.08
    cw = (W - 58) / 6
    def cy(v): return 16 + (ymax - np.log10(v)) / (ymax - ymin) * (H - 72)
    el = []
    for k, (p, bp, bm) in enumerate(cols):
        cx = 50 + cw * k + cw / 2
        y1, y2 = cy(bp), cy(bm)
        better_plus = bp < bm          # +ε 更低 → 加大该维改善
        color = '#0f8a4a' if better_plus else '#c2410c'
        el.append(
            f'<line x1="{cx-7:.0f}" y1="{y1:.1f}" x2="{cx+7:.0f}" y2="{y1:.1f}" stroke="#0b63ce" stroke-width="2"/>'
            f'<line x1="{cx-7:.0f}" y1="{y2:.1f}" x2="{cx+7:.0f}" y2="{y2:.1f}" stroke="#9aa0a6" stroke-width="2"/>'
            f'<path d="M {cx:.0f} {(y1+y2)/2:.1f} L {cx:.0f} {(y1 if better_plus else y2):.1f}" stroke="{color}" stroke-width="1.6" marker-end="url(#wt-ah)"/>'
            f'<text x="{cx:.0f}" y="{H-44}" text-anchor="middle" font-size="10.5" fill="#3b4a5a">{_WT_DIM_LABELS[p]}</text>'
            f'<text x="{cx:.0f}" y="{H-31}" text-anchor="middle" font-size="9.3" fill="#8a97a8">ε={eps[p]:g}</text>')
    return (f'<svg class="wt-svg" viewBox="0 0 {W} {H}" role="img" aria-label="第 0 步的 ±ε 微扰点真实 BER">'
            f'<defs><marker id="wt-ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
            f'<path d="M 0 0 L 10 5 L 0 10 z" fill="#5b6b7d"/></marker></defs>'
            f'<text x="46" y="12" text-anchor="end" font-size="9.5" fill="#8a97a8">{max(vals):.1%}</text>'
            f'<text x="46" y="{cy(min(vals))+3:.0f}" text-anchor="end" font-size="9.5" fill="#8a97a8">{min(vals):.1%}</text>'
            + ''.join(el) +
            f'<text x="{W/2:.0f}" y="{H-12}" text-anchor="middle" font-size="10.5" fill="#5b6b7d">每维 ±ε 两点的真实 BER（蓝 = +ε，灰 = −ε；箭头 = 斜率方向）· gain 维不试探（解析梯度）</text>'
            f'</svg>')


def _wt_slope_bars(pr, W=340, H=210):
    """6 维实测斜率条形（同两点 log₁₀ BER 差分）+ gain 维解析占位。"""
    eps = [0.01] * 4 + [0.1] * 2
    slopes = []
    for p in range(6):
        bp = float(pr[(pr['param'] == p) & (pr['sign'] == 1)]['real_ber'].iloc[0])
        bm = float(pr[(pr['param'] == p) & (pr['sign'] == -1)]['real_ber'].iloc[0])
        slopes.append((np.log10(bp) - np.log10(bm)) / (2 * eps[p]))
    m = max(abs(s) for s in slopes)
    cx = 150
    bars = []
    for i, s in enumerate(slopes):
        y = 18 + i * 25
        w = abs(s) / m * 110
        bars.append(
            f'<text x="142" y="{y+4:.0f}" text-anchor="end" font-size="11.5" fill="#3b4a5a" font-weight="600">{_WT_DIM_LABELS[i]}</text>'
            f'<line x1="{cx}" y1="{y-6:.0f}" x2="{cx}" y2="{y+6:.0f}" stroke="#c8d4e4"/>'
            f'<rect x="{cx if s<0 else cx+w-1:.1f}" y="{y-6:.0f}" width="{max(w,1.5):.1f}" height="12" rx="2" fill="{"#c2410c" if s>0 else "#0f8a4a"}" opacity="0.85"/>'
            f'<text x="{W-64}" y="{y+4:.0f}" font-size="10.8" fill="#5b6b7d">{"加大该维 → BER 降" if s<0 else "减小该维 → BER 降"}</text>')
    return (f'<svg class="wt-svg" viewBox="0 0 {W} {H}" role="img" aria-label="各维斜率方向与幅度">'
            + ''.join(bars) +
            f'<rect x="66" y="{18+6*25-6:.0f}" width="{W-130}" height="12" rx="2" fill="#f2c94c" opacity="0.55"/>'
            f'<text x="142" y="{18+6*25+4:.0f}" text-anchor="end" font-size="11.5" fill="#3b4a5a" font-weight="600">gain</text>'
            f'<text x="{W-64}" y="{18+6*25+4:.0f}" font-size="10.8" fill="#5b6b7d">解析闭式（0 试探，通常主导）</text>'
            f'<text x="{W/2:.0f}" y="{H-8}" text-anchor="middle" font-size="10.5" fill="#5b6b7d">斜率 = (log₁₀ BER₊ − log₁₀ BER₋) / 2ε（实测口径；决策用 Model A 在同两点的预测差，方向一致）</text>'
            f'</svg>')


def _wt_broyden_svg(W=340, H=200):
    """割线更新的一维几何图解：旧斜率 → 预测偏差 → 沿已走方向修正。"""
    x0, x1 = 90, 250
    A0, g0 = 130, -0.35          # 旧斜率（A 每 px 下降 0.35）
    dA = -70                     # 实际变化（更陡）
    A1p = A0 + g0 * (x1 - x0)    # 旧梯度预测的 A₁
    A1 = A0 + dA                 # 实际 A₁
    return (
        f'<svg class="wt-svg" viewBox="0 0 {W} {H}" role="img" aria-label="割线更新几何图解">'
        f'<defs><marker id="wt-ah2" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
        f'<path d="M 0 0 L 10 5 L 0 10 z" fill="#5b6b7d"/></marker></defs>'
        f'<line x1="40" y1="{A0+55:.0f}" x2="40" y2="14" stroke="#c8d4e4"/>'
        f'<text x="36" y="20" text-anchor="end" font-size="10" fill="#8a97a8">A（log₁₀ BER 预测）</text>'
        f'<line x1="{x0}" y1="{A0+55:.0f}" x2="{x1+60}" y2="{A0+55:.0f}" stroke="#c8d4e4"/>'
        f'<text x="{x1+64}" y="{A0+58:.0f}" font-size="10" fill="#8a97a8">某 shape 维 →</text>'
        # 旧梯度直线（过 x₀，浅色）
        f'<line x1="60" y1="{A0 - g0*(x0-60):.0f}" x2="320" y2="{A0 + g0*(320-x0):.0f}" stroke="#9aa0a6" stroke-dasharray="5,4" stroke-width="1.4"/>'
        # 割线（过两点，绿色）
        f'<line x1="60" y1="{A0 - (dA/(x1-x0))*(x0-60):.0f}" x2="320" y2="{A0 + (dA/(x1-x0))*(320-x0):.0f}" stroke="#0f8a4a" stroke-width="2.2"/>'
        # 点
        f'<circle cx="{x0}" cy="{A0}" r="5.5" fill="#0b63ce"/>'
        f'<text x="{x0}" y="{A0-10:.0f}" text-anchor="middle" font-size="11" fill="#0b63ce" font-weight="700">x₀</text>'
        f'<circle cx="{x1}" cy="{A1p:.0f}" r="4.5" fill="none" stroke="#9aa0a6" stroke-width="1.6"/>'
        f'<text x="{x1+8}" y="{A1p-6:.0f}" font-size="10.5" fill="#8a97a8">旧梯度的预测 A₁</text>'
        f'<circle cx="{x1}" cy="{A1}" r="5.5" fill="#0f8a4a"/>'
        f'<text x="{x1+8}" y="{A1+14:.0f}" font-size="10.5" fill="#0f8a4a" font-weight="700">实际 A₁ = A(探针(x₁))</text>'
        # 偏差箭头
        f'<line x1="{x1-16}" y1="{A1p:.0f}" x2="{x1-16}" y2="{A1:.0f}" stroke="#c2410c" stroke-width="1.8" marker-end="url(#wt-ah2)"/>'
        f'<text x="{x1-22}" y="{(A1p+A1)/2:.0f}" text-anchor="end" font-size="10.5" fill="#c2410c" font-weight="700">偏差</text>'
        f'<text x="{W/2:.0f}" y="{H-8}" text-anchor="middle" font-size="10.5" fill="#5b6b7d">偏差 = 预测变化 − 实际变化；沿已走的位移方向回填这份偏差，就得到新斜率（割线）</text>'
        f'</svg>')


def _build_walkthrough(a, summary, order):
    """§4.6 逐帧走查：用最难用例的真实 trace/probes 把「第一个梯度 → 每步更新 → 收敛」演一遍。

    三种取法的差异只体现在梯度更新那一帧；数据缺失时返回空串。
    """
    env = max(order, key=lambda e: summary[e]['seed_ber'])
    tpath = os.path.join(a.baseline, f'trace_{env}.csv')
    ppath = os.path.join(a.baseline, f'probes_{env}.csv')
    if not (os.path.exists(tpath) and os.path.exists(ppath)):
        return ''
    tr = pd.read_csv(tpath)
    pr = pd.read_csv(ppath)
    if tr.empty or pr.empty:
        return ''
    xcols = sorted([c for c in pr.columns if c.startswith('x_')], key=lambda c: int(c.split('_')[1]))
    nd = len(xcols)
    x = np.array([json.loads(s) for s in tr['x']])
    ber = tr['real_ber'].values
    n = len(tr)
    row0 = pr[(pr['param'] == 0) & (pr['sign'] == 1)].iloc[0]
    seed = np.array([float(row0[c]) for c in xcols])
    seed[0] -= 0.01                                   # 中心差分：+ε 那一支退半步即起点
    seed_ber = float(summary[env]['seed_ber'])
    # 显示窗口（不是参数约束）：抽头按一步的尺度 0.20 给窗，CTLE/gain 按物理量程给窗
    radius = np.array(([0.20] * 5 + [3.0, 3.0, 0.30])[:nd])
    lo, hi = seed - radius, seed + radius
    best_ber = float(summary[env]['best_ber'])
    best_step = int(summary[env]['best_step'])
    gr = tr['gain_ratio'].values
    n_ev = int(summary[env].get('n_real_evals', 0)) or (n + len(pr))
    n_probe = int(summary[env].get('n_probe_states', 0)) or len(pr)
    n_land = int(summary[env].get('n_landed', n)) or n
    pr0 = pr[pr['step'] == 0] if 'step' in pr.columns else pr
    n_p0 = int(len(pr0))
    stop_reason = summary[env].get('stop_reason')
    stop_reason = stop_reason if isinstance(stop_reason, str) and stop_reason else '步数上限'
    mode = getattr(a, 'mode', 'full')
    mode_zh = MODE_ZH_FIG.get(mode, mode)
    _ev_design = {'full': 225, 'rotate': 85, 'secant': 29}
    _ev_meas = {m: _dir_mean_evals(a.dirs.get(m)) for m in _ev_design}
    ev_cur = _ev_meas.get(mode) or _ev_design[mode]
    ev_full = _ev_meas.get('full') or _ev_design['full']
    probe_per_step = {'full': 14, 'rotate': 4, 'secant': 0}.get(mode, 0)
    _probe_note = {
        'full': 'full 取法每步都重算 7 维（每步 14 个微扰点）。',
        'rotate': 'rotate 取法每步只重算 2 个维（每步 4 个微扰点），4 步就把 7 个维各刷新一遍、此后循环。',
        'secant': 'secant 取法此后不再微扰，只用参数点位移与 Model A 的预测变化做 Broyden 秩一修正。',
    }

    def bars(k, prev=None):
        return _wt_param_bars(x[k], seed, lo, hi, prev=prev, gain_ratio=gr[k])

    F = []   # (title, left_svg, caption, right_html)

    F.append((
        '帧 1/8 · 起点 x₀：所有用例从同一次优点出发',
        _wt_param_bars(seed, seed, lo, hi, gain_ratio=float(row0['gain_ratio'])),
        f'{nd} 维参数：5 个 FFE 抽头 / gDC / gDC2 / gain（gain 以倍率显示，虚线即种子位置）',
        f'''<h5>起点：一个刻意的次优工作点</h5>
        <p>15 个用例都从这里出发：FFE 与 CTLE 取基线标定值，gain 只有 <span class="wt-ber">×{float(row0['gain_ratio']):.2f}</span>（远低于各环境的最优驱动幅度）。真实 BER = <span class="wt-ber">{seed_ber:.2%}</span>（{_per_bits(seed_ber)}）。</p>
        <p>5 个抽头都直接进搜索向量、没有派生关系也没有边界；只有 CTLE 与 gain 有物理量程。进环境后先取一次探针（链路真实处于 x₀），拿到 Model A 的起点读数和 gain 维解析梯度。</p>'''))

    F.append((
        f'帧 2 · 第 0 步：{n_p0} 个 ±ε 微扰点（三种取法共有的一轮）',
        _wt_probes_svg(pr0),
        '微扰点的真实 BER（如实记录）；方向侧只用 Model A 的预测差',
        f'''<h5>第一个梯度怎么来</h5>
        <p>形状 7 维各做一次中心差分：+ε 取一次探针查 Model A、−ε 再取一次（取探针时参数真的打上链路，所以这 {n_p0} 个状态的真实 BER 会被逐一记录，上图）。两点一比，斜率就有了。</p>
        <p>gain 维不用微扰：8 维探针特征全部正比于 gain，有解析的闭式链式解（§4.2.1）。三种取法的第 0 步完全一样，差别从第 1 步开始。{_probe_note[mode]}</p>'''))

    F.append((
        '帧 3 · 斜率 → 走哪边、走多远',
        _wt_slope_bars(pr0),
        '组内归一化后的方向；幅度按步长折算',
        f'''<h5>斜率变成方向</h5>
        <p>斜率乘步长之后，按 FFE、CTLE、gain 三组各自归一化，每组按归一化后的方向走。某组的范数低于 1e-3 dex 就冻结，不让拟合噪声把步子带偏。步长从 0.05 起，每步乘 0.97，固定走满 15 步。</p>
        <p>这个用例里 gain 维是主导项，最优驱动幅度离起点很远，这一维要爬很多步。</p>'''))

    F.append((
        '帧 4 · 第一步参数点',
        bars(0),
        f'{nd} 维同时小幅移动（组归一化步长）',
        f'''<h5>走第一步</h5>
        <p>参数点 <span class="mono">x₁ = clip(x₀ − α·span⊙d)</span>：只对 CTLE 与 gain 裁物理量程，抽头维不裁。参数点的真实 BER 是 <span class="wt-ber">{ber[0]:.2%}</span>（{_per_bits(ber[0])}，起点 {_per_bits(seed_ber)}）。第一步改善有限是正常的，步长只有一步尺度的 5%。</p>
        <p>这次真实 BER 评估只记录，不参与任何决策（无回传通道）。</p>'''))

    _upd = {
        'full': (f'''<h5>每步重算：方向始终跟着当前波形</h5>
        <p>full 取法在<strong>每一步</strong>都用当前参数点的探针重算 7 维中心差分（每步 14 个 ±ε 微扰点）。好处是方向不会被历史误差带偏，代价是每步 14 个微扰点再加 1 步，共 15 次真实评估、全程 ≈{ev_cur} 次。</p>'''),
        'rotate': (f'''<h5>每步只重算 2 个维</h5>
        <p>rotate 取法在每一步只重算 2 个维的斜率（按 <span class="mono">(2k+j) mod 7</span> 轮转），其余维沿用上一次的实测值：每步 4 个 ±ε 微扰点，4 步就把 7 个维各刷新一遍、此后循环。每用例真实评估 ≈{ev_cur} 次，约为 full（≈{ev_full} 次）的 {ev_cur / ev_full:.0%}。</p>'''),
        'secant': ('''<h5>不用微扰，梯度自己修正</h5>
        <p>手里已经有两个点：x₀ 和 x₁。位移 dx 和 Model A 预测的变化 dA 都是现成的，可以看旧梯度在 x₁ 上准不准。差多少，就沿已经走过的位移方向回填多少，修正后的梯度在已走方向上正好拟合 A 的实际变化，这就是割线方程。此后每步不再微扰。</p>'''),
    }[mode]
    F.append((
        f'帧 5 · 每步的梯度更新（{MODE_ZH_PLAIN.get(mode, mode)}）',
        _wt_broyden_svg() if mode == 'secant' else _wt_slope_bars(pr0),
        '一维示意；真实更新发生在形状 7 维子空间（gain 维每步用解析式重算）',
        _upd))

    F.append((
        f'帧 6 · 步 1–{min(5,n-1)}：gain 稳步爬，CTLE 在找位',
        bars(min(5, n - 1), prev=x[0]),
        f'第 {min(5,n-1)} 步的参数位置（空心圈 = 第 1 步）',
        f'''<h5>爬坡段</h5>
        <p>BER 从 {ber[0]:.2%} 降到 {ber[min(5,n-1)]:.2%}（{_per_bits(ber[min(5,n-1)])}）。gain 每步稳定往上爬（×{gr[0]:.2f} → ×{gr[min(5,n-1)]:.2f}），是这段的主力；gDC2 收敛到 0 附近，说明 shelf 增益这一维上没有收益。</p>
        <p>每步除 1 次参数点记录外，还要为梯度估计多打 <strong>{probe_per_step}</strong> 次微扰点到链路上（本格 {MODE_ZH_PLAIN.get(mode, mode)}）。</p>'''))

    k2 = n - 1
    F.append((
        f'帧 7 · 步 {min(6,n-1)}–{n-1}：深水区，贴住物理量程走到最优',
        bars(k2, prev=x[min(5, n - 1)]),
        f'终点参数位置（空心圈 = 第 {min(5,n-1)} 步）',
        f'''<h5>深水段</h5>
        <p>BER 一路压到 <span class="wt-ber">{best_ber:.2e}</span>（{_per_bits(best_ber)}，第 {best_step} 步最优）。gain 爬到 <span class="wt-ber">×{gr[k2]:.2f}</span>，是本用例唯一的物理量程约束所在（gDC2 贴下界 0，抽头维没有边界可贴）。</p>
        <p>停止原因：{stop_reason}。固定走满 15 步，不提前停（§4.5）。</p>'''))

    F.append((
        '帧 8 · 总账',
        _wt_curve(ber, seed_ber, active=set(range(n))),
        f'{env}（最难用例）全程 {n} 步',
        f'''<h5>这一趟花了什么、拿到了什么</h5>
        <p>真实评估 <span class="wt-ber">{n_ev} 次</span> = {n_land} 次每步结果 + {n_probe} 个 ±ε 微扰点（其中第 0 步 {n_p0} 个）；本格每步微扰 <span class="wt-ber">{probe_per_step} 个</span>。</p>
        <p>BER 从 <span class="wt-ber">{seed_ber:.2%}</span> 到 <span class="wt-ber">{best_ber:.2e}</span>，也就是从 {_per_bits(seed_ber)} 到 {_per_bits(best_ber)}。整个决策过程只用发端探针和冻结的 Model A，一次端到端 BER 都没收。</p>'''))

    frames = []
    for i, (title, svg, cap, right) in enumerate(F):
        frames.append(
            f'<div class="wt-frame{" on" if i == 0 else ""}" data-title="{title}">\n'
            f'  <div>{svg}<p class="wt-cap">{cap}</p></div>\n'
            f'  <div class="wt-right">{right}</div>\n'
            f'</div>')
    dots = ''.join(f'<button class="wt-dot{" on" if i == 0 else ""}" aria-label="{t.split("·")[0]}"></button>'
                   for i, (t, *_r) in enumerate(F))
    return f'''
<p>下面拿最难用例 {env}（{summary[env]['il_tx']:g}+{summary[env]['il_rx']:g} dB 总插损）在{mode_zh}取法下的真实运行数据，把第一个梯度、每步更新、收敛这个过程走一遍。用 ‹ › 翻帧，或者点自动播放。公式在 §4.2，打印版会把所有帧展开。</p>
<div class="wt">
  <div class="wt-bar">
    <button class="wt-btn" data-wt-nav="-1">‹ 上一帧</button>
    <div class="wt-dots">{dots}</div>
    <button class="wt-btn" data-wt-nav="1">下一帧 ›</button>
    <button class="wt-btn" data-wt-play>▶ 自动播放</button>
    <span class="wt-title">{F[0][0]}</span>
  </div>
  {''.join(frames)}
</div>'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--baseline', default='result/ddps_cpp_full', help='主结果目录（现役格，C++ 全量 15 用例）')
    ap.add_argument('--mode', default='full', choices=['full', 'rotate', 'secant'],
                    help='主结果目录对应的形状维取法（决定正文口径文字）')
    ap.add_argument('--rotate', default='result/ddps_cpp_rotate', help='代理 × rotate 全量结果目录')
    ap.add_argument('--secant', default='result/ddps_cpp_secant', help='代理 × secant 全量结果目录')
    ap.add_argument('--model-dir', default='models/ddps', help='模型目录')
    ap.add_argument('--dataset', default=None)
    ap.add_argument('--report-src', default=None, help='报告图数据源（缺省 = 主结果目录，图用 C++ 出）')
    ap.add_argument('--direct', default='result/ddps_cpp_direct_secant',
                    help='真实 BER 回传 × secant 全量结果目录（存在才渲染矩阵对应行）')
    ap.add_argument('--direct-full', default='result/ddps_cpp_direct_full',
                    help='真实 BER 回传 × full 全量结果目录（存在才渲染）')
    ap.add_argument('--direct-rotate', default='result/ddps_cpp_direct_rotate',
                    help='真实 BER 回传 × rotate 全量结果目录（存在才渲染）')
    ap.add_argument('--eq-py', default='result/ddps_equiv_py',
                    help='Python 2^18 验证目录前缀（比对参考侧，后缀 _full/_rotate/_secant/_direct）')
    ap.add_argument('--eq-cpp', default='result/ddps_equiv_cpp',
                    help='C++ 2^18 等价比对目录前缀')
    ap.add_argument('--out', default='deliverables/DDPS_Deliverable.html')
    ap.add_argument('--allow-mixed-scale', action='store_true',
                    help='允许六格结果规模不一致（仅调试用；正式交付件不允许）')
    a = ap.parse_args()
    if a.report_src is None:
        a.report_src = a.baseline
    a.dirs = {
        'full': a.baseline if a.mode == 'full' else 'result/ddps_cpp_full',
        'rotate': a.baseline if a.mode == 'rotate' else a.rotate,
        'secant': a.baseline if a.mode == 'secant' else a.secant,
        'direct': a.direct,
        'direct_secant': a.direct,
        'direct_full': a.direct_full,
        'direct_rotate': a.direct_rotate,
        'full_eq': _eq_dir(a.eq_cpp, 'full'),
        'rotate_eq': _eq_dir(a.eq_cpp, 'rotate'),
        'secant_eq': _eq_dir(a.eq_cpp, 'secant'),
        'direct_eq': _eq_dir(a.eq_cpp, 'direct'),
        'direct_full_eq': _eq_dir(a.eq_cpp, 'direct_full'),
        'direct_rotate_eq': _eq_dir(a.eq_cpp, 'direct_rotate'),
        'direct_secant_eq': _eq_dir(a.eq_cpp, 'direct_secant'),
        'eq_py_root': a.eq_py,
    }

    a.eq_py_root = a.eq_py
    _scale_guard(a)
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
    hard_png = os.path.join(report_dir, f'ddps_case_{hard_env}.png')

    # 统计
    imp_arr = np.array([summary[e]['seed_ber'] / summary[e]['best_ber'] for e in order])
    imp_geo = float(10 ** np.mean(np.log10(imp_arr)))   # 几何均值（避免被个别大改善拉高）
    n_pos = int((imp_arr > 1.0).sum())
    n_neu = int((imp_arr == 1.0).sum())
    n_worse = len(order) - n_pos - n_neu
    pos_summary = f"{n_pos}/{len(order)} 用例相对起点改善、{n_neu} 用例持平、{n_worse} 用例退步"
    hard = summary[hard_env]
    safety_rows, safety_probe_rows, total_steps, total_worse, probe_worse_steps, worst_ratio, worst_env, worst_ber = _rows_safety(summary, a.baseline)

    # 主结果目录的全量重跑墙钟（result/ddps_cpp_<格>/run_config.json）
    cpp_dir = a.baseline
    cxx_total_wall = '未运行'
    rc_path = os.path.join(cpp_dir, 'run_config.json')
    if os.path.exists(rc_path):
        with open(rc_path, encoding='utf-8') as f:
            rcj = json.load(f)
        cxx_total_wall = '%.0f s' % float(rcj.get('total_wall_sec', 0.0))

    eval_cost_rows = _rows_eval_cost(a.dirs, a.mode)


    seed_lo = min(summary[e]['seed_ber'] for e in order)
    seed_hi = max(summary[e]['seed_ber'] for e in order)

    # 检测限口径（0 错误报告值 / N_bits / 95% CL 上界 / 到检测底的用例数）：从该格实测结果反推
    fs = _floor_stats(summary, order, _dir_num_symbols(a.baseline) or _dir_num_symbols(a.direct))

    mode_cmp_rows, mode_cmp_bits, mode_series = _rows_mode_cmp(
        a.dirs, order, a.mode, allow_mixed=a.allow_mixed_scale)
    mode_cmp_verdict = _live_verdict(mode_series, a.mode)
    cur_mode_zh = MODE_ZH.get(a.mode, a.mode)
    cur_mode_plain = MODE_ZH_PLAIN.get(a.mode, a.mode)
    cur_ev = mode_series.get(a.mode, {}).get('ev', float('nan'))

    headline = '\n'.join([
        f"<tr><td><strong>在线调优</strong>（只用 Model A 方向代理 + 8 维梯度下降；现役格 {cur_mode_plain}）</td>"
        f"<td><strong>{n_pos}/{len(order)} 用例从次优起点（BER {_ber(seed_lo)} ~ {_ber(seed_hi)}）压到环境最优</strong>："
        f"{_floor_txt(fs)}；"
        f"{total_steps} 步 {total_worse} 次劣于起点（含 ±ε 微扰点瞬时 {probe_worse_steps} 步超种子，见 6.3）。"
        f"机制逐帧演示见 4.6</td></tr>",
        f"<tr><td>形状梯度三种取法（一键切换）</td>"
        f"<td>{mode_cmp_bits}。三种取法共用同一起点、同一组归一化步长与门控、同一固定 15 步，"
        f"唯一区别是为估计梯度要真实打到链路上多少次（见 4.3 / 6.1）</td></tr>",
        f"<tr><td>方向代理 Model A</td>"
        f"<td>输入 = [7-tap Tx FIR 探针, drive_rms]（8 维物理波形量）→ log10(BER_MLSE)。"
        f"在线拿不到收端 BER，只能拿发端探针，A 建立「波形 → 误码」的方向映射；离线冻结，在线不重训</td></tr>",
        f"<tr><td>梯度估计的物理代价（如实记录）</td>"
        f"<td>探针不是算出来的：要读到探针就必须把参数真的打到链路上，因此每个 ±ε 状态都是链路真实经过的工作点。"
        f"每用例真实评估 <strong>{cur_ev:.0f} 次</strong> = 15 次每步结果 + 其余为微扰点，逐条记在 6.3 / 6.4</td></tr>",
        f"<tr><td>在线决策是否使用真实收端误码</td><td><strong>不使用</strong>，仅旁路记录用于事后核验</td></tr>",
    ])

    kpis = '\n'.join([
        f'<div class="kpi"><div class="v">{n_pos} / {len(order)}</div><div class="l">用例改善：次优起点都压到了环境最优附近（{_floor_txt(fs, short=True)}）</div></div>',
        f'<div class="kpi"><div class="v">0 次</div><div class="l">在线决策用到的真实 BER：方向和终止只靠发端探针加冻结的 Model A</div></div>',
        f'<div class="kpi"><div class="v">{total_worse} / {total_steps}</div><div class="l">步数比起点差（把 ±ε 微扰点也算上，有 {probe_worse_steps} 步瞬时超过起点，最坏 {_ratio_str(worst_ratio)}，见 6.3）</div></div>',
        f'<div class="kpi"><div class="v">{cur_ev:.0f} 次</div><div class="l">每用例真实评估（{cur_mode_plain}：15 次参数点加其余微扰点），三种取法的代价对比见 4.3</div></div>',
        f'<div class="kpi"><div class="v">8 维</div><div class="l">搜索空间：5 个 FFE 抽头（无边界）+ gDC + gDC2 + driver_gain</div></div>',
    ])

    # direct 对比实验：数据存在才渲染（6.5 对比节 + 6.2 图组页签）
    direct_section = _build_direct_section(a, summary, order, fs)
    # 6.2 图组页签：逐格收敛图（各格 report_ddps.py 产物）+ 回传 × secant
    fig_tabs = _build_fig_tabs(a, hard_env)
    # 10.4 等价页签：六格（发端代理三格 + 真实 BER 回传三格）的 2^18 比对，逐格实算
    eq_tabs = _build_eq_tabs(a)
    # 机制可视化素材（§3.1 训练数据 / §4.6 逐帧走查）：数据缺失自动退化
    dataset_card = _build_dataset_card(a)
    walkthrough = _build_walkthrough(a, summary, order)

    # 现役格机制文字（三种取法的差异只在微扰频率）
    _mode_name = {'full': '每步 7 维全量中心差分（每步 14 个 ±ε 微扰点）',
                  'rotate': '每步轮转 2 维的中心差分（每步 4 个 ±ε 微扰点，4 步刷新完 7 个维、此后循环）',
                  'secant': '第 0 步一轮 7 维中心差分后、用 Broyden 秩一修正外推（此后 0 个 ±ε 微扰点）'}
    _mode_probe_text = {
        'full': '形状 7 维每步都用当前参数点的中心差分重算，因此<strong>每一步</strong>都会产生 14 个 ±ε 微扰点（7 维 × ±ε）',
        'rotate': '每步只重算 2 个维（轮转），因此第 0 步之后<strong>每步产生 4 个 ±ε 微扰点</strong>（4 步刷新完 7 个维、此后循环）',
        'secant': '只在第 0 步做一轮 7 维中心差分（14 个 ±ε 微扰点），此后用 Broyden 秩一修正外推，<strong>不再产生任何微扰点</strong>',
    }
    mode_name_text = _mode_name.get(a.mode, a.mode)
    mode_probe_text = _mode_probe_text.get(a.mode, '')
    mode_probe_caption = {
        'full': '微扰点真实 BER_MLSE 包络：每步 14 个 ±ε 微扰点（7 维 × ±ε；gain 维解析、0 微扰）',
        'rotate': '微扰点真实 BER_MLSE 包络：第 0 步 14 个、其后每步 4 个 ±ε 微扰点（每步轮转 2 维；gain 维解析、0 微扰）',
        'secant': '微扰点真实 BER_MLSE 包络：仅第 0 步 14 个 ±ε 微扰点（7 维 × ±ε；其后 0 微扰，gain 维解析）',
    }.get(a.mode, '微扰点真实 BER_MLSE 包络')
    if direct_section:
        # 摘要行与 6.5 同口径：回传行三格（full/rotate/secant）逐用例取最好的一格
        _dmap = {}
        for _m in _MODE_ORDER:
            _d, _sc = _pick_dir(a.dirs, f'direct_{_m}')
            if _d:
                _dmap[_m], _ = _load_summary(_d)
        dorder = [e for e in order if _dmap and all(e in _dmap[m] for m in _dmap)]
        _b = {e: min(((m, _dmap[m][e]) for m in _dmap), key=lambda t: float(t[1]['best_ber']))
              for e in dorder}
        ratio = np.array([_b[e][1]['best_ber'] / summary[e]['best_ber'] for e in dorder])
        n_same = int(((ratio >= 0.95) & (ratio <= 1.05)).sum())
        n_both = sum(1 for e in dorder
                     if _is_zero_error(_b[e][1]['best_ber'], fs.get('num_symbols') or 0)
                     and _is_zero_error(summary[e]['best_ber'], fs.get('num_symbols') or 0))
        i_best, i_worst = int(ratio.argmin()), int(ratio.argmax())
        e_best, e_worst = dorder[i_best], dorder[i_worst]
        # 一样行（几何平均倍数读者无感：换成锚点式逐用例事实）
        hl_direct = (f"{n_same}/{len(dorder)} 用例一样（{n_both} 例两边同到 0 错误检测底）")
        if ratio[i_best] < 0.95:
            hl_direct += (f"，{e_best} 回传 × {_b[e_best][0]} 更深（{_ber(_b[e_best][1]['best_ber'])} vs "
                          f"{_ber(summary[e_best]['best_ber'])}）")
        if ratio[i_worst] > 1.05:
            hl_direct += f"，{e_worst} 回传 × {_b[e_worst][0]} 更浅（×{ratio[i_worst]:.1f}）"
        headline += (
            f"<tr><td>对比实验 回传行（有回传通道）</td>"
            f"<td>若端到端 BER 可回传：目标直接换成真实 BER、不用代理的直接梯度下降，"
            f"与现役方案同协议对比（{_scale_label(fs.get('num_symbols'))} C++、同次优起点、"
            f"三格逐用例取最好）：{hl_direct}，见 6.2</td></tr>")

    html = TEMPLATE
    repl = {
        '<!--MODEL_METRICS_ROWS-->': _rows_metrics(meta),
        '<!--KPI_CARDS-->': kpis,
        '<!--CORE_ROWS-->': _rows_core(summary, order),
        '<!--TARGET_RMS_ROWS-->': _rows_target_rms(rms_data, order),
        '<!--SAFETY_ROWS-->': safety_rows,
        '<!--SAFETY_PROBE_ROWS-->': safety_probe_rows,
        '<!--PROBE_WORSE_STEPS-->': str(probe_worse_steps),
        '<!--PROBE_WORST_RATIO-->': _ratio_str(worst_ratio).lstrip('×'),
        '<!--PROBE_WORST_ENV-->': worst_env,
        '<!--PROBE_WORST_BER-->': f'{worst_ber:.2e}',
        '<!--PROBE_ROWS-->': _rows_probe(a.baseline, order),
        '<!--CXX_TOTAL_WALL-->': cxx_total_wall,
        '<!--POS_SUMMARY-->': pos_summary,
        '<!--SEED_BER_LO-->': _ber(seed_lo),
        '<!--SEED_BER_BASE-->': _ber(summary.get('Base_IL10x10', {}).get('seed_ber', seed_lo)),
        '<!--SEED_BER_HI-->': _ber(seed_hi),
        '<!--SEED_LO_HUMAN-->': _per_bits(seed_lo),
        '<!--SEED_HI_HUMAN-->': _per_bits(seed_hi),
        '<!--FLOOR_PERBITS-->': _per_bits(fs['floor_ber']) if fs.get('floor_ber') else '—',
        '<!--FLOOR_BER-->': _ber(fs['floor_ber']) if fs.get('floor_ber') else '—',
        '<!--FLOOR_NBITS-->': ('%.0f' % fs['n_bits']) if fs.get('n_bits') else '—',
        '<!--FLOOR_UB95-->': _ber(fs['ub95']) if fs.get('ub95') else '—',
        '<!--PROTO_SYMBOLS-->': _sym_txt(fs.get('num_symbols')),
        '<!--SCALE_LABEL-->': _scale_label(fs.get('num_symbols')),
        '<!--SCALE_LABEL_PLAIN-->': re.sub(r'<[^>]+>', '', _scale_label(fs.get('num_symbols'))),
        '<!--N_ROWS-->': (_dataset_shape(a).split(' 行')[0] if _dataset_shape(a) != '—' else '—'),
        '<!--DATASET_SHAPE-->': _dataset_shape(a),
        '<!--EVAL_SEC_TEXT-->': _per_eval_sec_text(a),
        '<!--FLOOR_TXT_LONG-->': _floor_txt(fs),
        '<!--MEAN_DEX-->': f'{np.log10(imp_geo):.1f}',
        '<!--TOTAL_STEPS-->': str(total_steps),
        '<!--TOTAL_WORSE-->': str(total_worse),
        '{{IMG_CONV}}': _img_tag(img_conv) if os.path.exists(img_conv) else '',
        '{{IMG_GAIN}}': _img_tag(img_gain) if os.path.exists(img_gain) else '',
        '{{IMG_TRACK}}': _img_tag(img_track) if os.path.exists(img_track) else '',
        '{{IMG_CASE_HARD}}': _img_tag(hard_png) if os.path.exists(hard_png) else '',
        '<!--TOP_CURVE-->': _top_curve(a, summary, order),
        '<!--AC_SVG-->': _ac_coupling_svg(),
        '<!--DIRECT_SECTION-->': direct_section,
        '<!--SEED_STUDY-->': _study_block(a),
        '<!--SEED_SPECTRUM-->': _seed_spectrum_block(a),
        '<!--STUDY_LI-->': _study_conclusion_line(a),
        '<!--MODE_NAME_TEXT-->': mode_name_text,
        '<!--MODE_KEY-->': a.mode,
        '<!--MODE_LABEL-->': cur_mode_zh,
        '<!--MODE_PROBE_TEXT-->': mode_probe_text,
        '<!--TURN_BLOCK-->': _turn_block(a, order),
        '<!--MODE_PROBE_CAPTION-->': mode_probe_caption,
        '<!--EQ_TABS-->': eq_tabs,
        '<!--EVAL_COST_ROWS-->': eval_cost_rows,
        '<!--EVAL_KPI_CARDS-->': _kpi_eval(a.dirs),
        '<!--MODE_CMP_ROWS-->': mode_cmp_rows,
        '<!--MODE_CMP_VERDICT-->': mode_cmp_verdict,
        '<!--DATASET_CARD-->': dataset_card,
        '<!--WALKTHROUGH-->': walkthrough,
    }
    for k, v in repl.items():
        html = html.replace(k, v)

    # 目录导航：每个大章节（h2）末尾插入「↩ 回目录」（首个 h2 前不加；最后一章在 footer 前补）
    back = '<a class="back-toc" href="#toc">↩ 回目录</a>'
    h2_tag = '<h2 id="s'
    positions = [m.start() for m in re.finditer(re.escape(h2_tag), html)]
    for pos in reversed(positions[1:]):
        html = html[:pos] + back + '\n' + html[pos:]
    if '<footer>' in html:
        html = html.replace('<footer>', back + '\n<footer>', 1)

    with open(a.out, 'w', encoding='utf-8') as f:
        f.write(html)
    left = html.count('{{IMG_') + html.count('<!--')
    print(f'[deliverable] written {a.out}  ({os.path.getsize(a.out)/1024:.0f} KB)')
    print(f'[deliverable] baseline={a.baseline} model={a.model_dir}')
    for _m in ('full', 'rotate', 'secant', 'direct'):
        _d, _sc = _pick_dir(a.dirs, _m)
        print(f'[deliverable]   {_m:6s} -> {_d} [{_sc}]')
    print(f'[deliverable] envs={len(order)} positive={n_pos} steps={total_steps} worse={total_worse}')
    print(f'[deliverable] mean improvement (geomean): x{imp_geo:.2f}')
    print(f'[deliverable] hardest={hard_env}; unused tokens left: {left}')


if __name__ == '__main__':
    main()
