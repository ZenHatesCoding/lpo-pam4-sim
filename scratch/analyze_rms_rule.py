# -*- coding: utf-8 -*-
"""分析最优 RMS 与信道参数的关系，设计 gain 维的目标 RMS 规则。"""
import pandas as pd
import numpy as np
from collections import Counter
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ddps_cases import ENV_CASES

df = pd.read_csv('result/env_optimal_scan.csv')
ec = {e['name']: e for e in ENV_CASES}

print("env                          il_tx il_rx cd dgd stress best_rms best_ratio best_ber")
print("-" * 100)
rows = []
for env in sorted(df['env'].unique()):
    sub = df[df.env == env]
    ib = int(sub['log10_ber'].idxmin())
    b = sub.loc[ib]
    e = ec[env]
    st = 1 if e.get('stress') else 0
    print(f"{env:28s} {e['il_tx']:.0f}    {e['il_rx']:.0f}   {e['cd']:.0f} {e['dgd']:.0f} {st}     {b.drive_rms:.4f}   {b.ratio:.2f}      {b.ber:.3e}")
    rows.append((env, e['il_tx'], e['il_rx'], e['cd'], e['dgd'], st, b.drive_rms, b.ratio, b.ber))

ratios = [r[7] for r in rows]
print("\noptimal ratio Counter:", Counter(ratios))

# 关键：看是否"信号弱(IL>=16 or noise) -> ratio高(1.0~1.3)，信号强 -> ratio低(0.4~0.6)"
print("\n== 按信号强度分组 ==")
for r in rows:
    weak = (r[1] >= 16 or r[2] >= 16 or r[5] == 1)
    tag = "WEAK" if weak else "STRONG"
    print(f"  {tag} {r[0]:28s} il_tx={r[1]:.0f} il_rx={r[2]:.0f} noise={r[5]} -> ratio={r[7]} rms={r[6]:.4f}")

# 如果目标 drive_rms 取一个适中值，看各环境在"解析 gain= target/k"下 BER 如何
# k 可在线标定：k = drive_rms@seed_gain / seed_ratio
# 这里假设 target_rms，算每环境 gain ratio = target_rms / k_env
print("\n== 试不同 target_rms，看解析 gain 后 BER (用各 env k) ==")
# 每环境 k（drive_rms per ratio，从 ratio=1.0 行取）
kmap = {}
for env in sorted(df['env'].unique()):
    sub = df[(df.env == env) & (df.gdc == -3) & (df.gdc2 == -3) & (df.ratio == 1.0)]
    if len(sub):
        kmap[env] = float(sub['drive_rms'].iloc[0])  # = k * 1.0
for target in [0.10, 0.11, 0.12, 0.13, 0.14, 0.15, 0.16, 0.17, 0.18]:
    print(f"  target_rms={target:.2f}:")
    bers = []
    for r in rows:
        env = r[0]
        k = kmap.get(env)
        if k is None:
            continue
        ratio = target / k
        # 从扫描表插值找最近 ratio 的 BER（gDC=gDC2=-3）
        sub = df[(df.env == env) & (df.gdc == -3) & (df.gdc2 == -3)].sort_values('ratio')
        ber = float(np.interp(ratio, sub['ratio'], sub['ber']))
        bers.append(ber)
    # 几何平均
    gmean = np.exp(np.mean(np.log(np.array(bers))))
    print(f"    geometric mean BER = {gmean:.3e}, max BER = {max(bers):.3e}, min BER = {min(bers):.3e}")
