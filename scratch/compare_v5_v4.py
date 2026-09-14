# -*- coding: utf-8 -*-
"""对比 v5 vs v4：单调性、改善、绝对 BER。"""
import csv, glob, os, numpy as np

def load(d):
    out = {}
    for f in sorted(glob.glob(os.path.join(d, 'trace_*.csv'))):
        rows = list(csv.DictReader(open(f)))
        lbs = [float(r['real_lb']) for r in rows]
        out[rows[0]['env']] = lbs
    return out

v5 = load('result/ddps_v5_main')
v4 = load('result/ddps_v4_main')

print(f"{'env':28s} {'v5_seed':>9} {'v5_best':>9} {'v5_fin':>9} {'v5_dB':>8} {'v5mono':>7} {'v4_dB':>8} {'v4mono':>7}")
print('-' * 100)
v5_db = []; v4_db = []; v5_nw = 0; v4_nw = 0
for env in sorted(v5.keys()):
    l5 = v5[env]; l4 = v4.get(env, [])
    s5 = l5[0]; b5 = min(l5); f5 = l5[-1]
    s4 = l4[0] if l4 else s5; b4 = min(l4) if l4 else b5; f4 = l4[-1] if l4 else f5
    mono5 = all(l5[i+1] <= l5[i] + 0.03 for i in range(len(l5)-1))
    mono4 = all(l4[i+1] <= l4[i] + 0.03 for i in range(len(l4)-1)) if l4 else True
    d5 = b5 - s5; d4 = b4 - s4
    v5_db.append(d5); v4_db.append(d4)
    if f5 > s5 + 0.01: v5_nw += 1
    if f4 > s4 + 0.01: v4_nw += 1
    print(f"{env:28s} {s5:9.3f} {b5:9.3f} {f5:9.3f} {d5:+8.3f} {'Y' if mono5 else 'N':>7} {d4:+8.3f} {'Y' if mono4 else 'N':>7}")
print('-' * 100)
print(f"mean d_best:  v5={np.mean(v5_db):+.3f}   v4={np.mean(v4_db):+.3f}")
print(f"final worse than seed (>+0.01):  v5={v5_nw}   v4={v4_nw}")
print(f"all improved (d_best < -0.005):  v5={sum(1 for d in v5_db if d<-0.005)}/15   v4={sum(1 for d in v4_db if d<-0.005)}/15")

# 绝对 BER 对比
print("\n=== 绝对 BER (best) ===")
print(f"{'env':28s} {'seed':>10} {'v5_best':>10} {'v4_best':>10} {'imp_v5/v4':>10}")
for env in sorted(v5.keys()):
    l5 = v5[env]; l4 = v4.get(env, [])
    s = 10**l5[0]; b5 = 10**min(l5); b4 = 10**min(l4) if l4 else b5
    print(f"{env:28s} {s:10.3e} {b5:10.3e} {b4:10.3e} {b4/b5:10.2f}x")
