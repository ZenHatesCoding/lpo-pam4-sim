# -*- coding: utf-8 -*-
"""验证：固定 target_drive_rms 是否能让 ratio 自适应到各环境最优。

核心假说：drive_rms ∝ gain（链路里 gain 是最后乘子），而 drive_rms 的"可达性"随 IL 变
（IL 越大，同样 gain 下 drive_rms 越小，因为信号被 IL 衰减后到 MZM 前更弱... 实际上
drive_rms 测的是 MZM 输入端，IL 在 drive_rms 之前，所以 IL 大 -> k 小 -> 同 ratio 下 rms 小）。
所以"固定 target_rms" => "IL 大的环境 ratio 自动变大" => 自适应补摆幅。

但问题：这个自适应是否够？IL20x20 最优 ratio=1.3（已达搜索箱上限），固定 rms 能否给出 1.3？
"""
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ddps_cases import ENV_CASES

df = pd.read_csv('result/env_optimal_scan.csv')
ec = {e['name']: e for e in ENV_CASES}

# 每环境 k = drive_rms @ ratio=1.0 (gDC=gDC2=-3，与最优 CTLE 一致)
kmap = {}
for env in sorted(df['env'].unique()):
    sub = df[(df.env == env) & (df.gdc == -3) & (df.gdc2 == -3) & (df.ratio == 1.0)]
    if len(sub):
        kmap[env] = float(sub['drive_rms'].iloc[0])

print("env                          k(@r=1)  optimal_ratio  optimal_rms")
print("-" * 80)
opt = {}
for env in sorted(df['env'].unique()):
    sub = df[df.env == env]
    ib = int(sub['log10_ber'].idxmin())
    b = sub.loc[ib]
    opt[env] = b
    print(f"{env:28s} {kmap.get(env,0):.5f}   {b.ratio:.2f}          {b.drive_rms:.5f}")

print("\n== 固定 target_rms => 解析 ratio = target/k ==")
for target in [0.12, 0.13, 0.14, 0.15, 0.16]:
    print(f"\ntarget_rms = {target}")
    print(f"  {'env':28s} {'parsed_ratio':>11} {'opt_ratio':>10} {'match':>6} {'ber@parsed':>11} {'ber@opt':>10}")
    for env in sorted(df['env'].unique()):
        k = kmap.get(env)
        if k is None:
            continue
        pr = target / k
        # 扫描表插值 BER（gDC=gDC2=-3 这条线，因为 CTLE 也走代理往负方向调，最终落到 -3 附近）
        sub = df[(df.env == env) & (df.gdc == -3) & (df.gdc2 == -3)].sort_values('ratio')
        ber_p = float(np.interp(pr, sub['ratio'], sub['ber']))
        o = opt[env]
        match = "OK" if abs(pr - o.ratio) < 0.25 else "off"
        print(f"  {env:28s} {pr:11.2f} {o.ratio:10.2f} {match:>6} {ber_p:11.3e} {o.ber:10.3e}")
