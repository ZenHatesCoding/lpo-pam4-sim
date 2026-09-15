# -*- coding: utf-8 -*-
"""修最后一批残留：分组步长行(弯引号)、KPI卡(7轴)、safety行标签、RUNLEN_NOTE(本版)、整箱覆盖、v4路径。"""
import io
p = 'make_deliverable_v5.py'
with io.open(p, 'r', encoding='utf-8') as f:
    s = f.read()

LQ = '\u201c'  # 左弯引号
RQ = '\u201d'  # 右弯引号

fixes = [
    # 分组步长行（弯引号版）
    (f'<li><strong>\u5206\u7ec4\u6b65\u957f</strong>\uff1a\u628a 6 \u7ef4\u5206\u6210 FFE(4) / CTLE(2) / \u589e\u76ca(1) \u4e09\u7ec4\uff0c<strong>\u7ec4\u5185</strong>\u628a <span class="mono">g \u2299 \u7bb1\u5bbd</span> \u5f52\u4e00\u5316\uff0c\u518d\u4e58\u8be5\u7ec4\u7bb1\u5bbd\uff08FFE 0.20 / CTLE 6 dB / \u589e\u76ca 1.12 dex\uff09\u2014\u2014\u4e09\u7ec4\u5404\u4ee5{LQ}\u7bb1\u5bbd\u7684\u56fa\u5b9a\u6bd4\u4f8b{RQ}\u524d\u8fdb\u3002</li>',
     '<li><strong>\u5206\u7ec4\u6b65\u957f</strong>\uff1a\u628a 6 \u7ef4\u5206\u6210 FFE(4) / CTLE(2) \u4e24\u7ec4\uff0c<strong>\u7ec4\u5185</strong>\u628a <span class="mono">g \u2299 \u7bb1\u5bbd</span> \u5f52\u4e00\u5316\uff0c\u518d\u4e58\u8be5\u7ec4\u7bb1\u5bbd\uff08FFE 0.20 / CTLE 6 dB\uff09\u2014\u2014\u4e24\u7ec4\u5404\u4ee5\u7bb1\u5bbd\u7684\u56fa\u5b9a\u6bd4\u4f8b\u524d\u8fdb\u3002gain \u4e0d\u5728\u8fd9\u4e24\u7ec4\u91cc\u3002</li>'),
    # KPI 卡 7 轴 → 6 轴
    ('Model A \u65b9\u5411\u52a0\u6743\u547d\u4e2d\u7387\uff087 \u8f74\u5b9e\u6d4b\uff09',
     'Model A \u65b9\u5411\u52a0\u6743\u547d\u4e2d\u7387\uff086 \u8f74\u5b9e\u6d4b\uff09'),
    # safety 行标签
    ('\u4e09\u7ec4\u81ea\u7531\u5ea6\u5168\u5f00\uff08\u53ea\u7528\u57fa\u7ebf\u8bad\u7ec3\uff09',
     'FFE/CTLE \u4ee3\u7406 + gain per-case RMS\uff08\u53ea\u7528\u57fa\u7ebf\u8bad\u7ec3\uff09'),
    # RUNLEN_NOTE "本版"
    ('\u672c\u7248\u8f68\u8ff9\u5728<strong>\u4fe1\u4efb\u57df\u5185\u81ea\u7136\u505c\u6b62</strong>\uff08\u672c\u6279\u6700\u591a',
     '\u8f68\u8ff9\u5728<strong>\u4fe1\u4efb\u57df\u5185\u81ea\u7136\u505c\u6b62</strong>\uff08\u672c\u6279\u6700\u591a'),
    # 整箱覆盖
    ('40% \u7528\u4e8e\u6574\u7bb1\u8986\u76d6\uff08\u5916\u58f3\uff09\u3002',
     '40% \u7528\u4e8e\u8986\u76d6\uff08\u5916\u58f3\uff09\u3002'),
    # trace_check 路径
    ('result/ddps_v4_trace_check.csv',
     'result/ddps_v4_trace_check.csv\uff08\u6cbf\u7528 v4 \u540c\u534f\u8bae\uff09'),
    # safety 行里有退步说明
    ('\u6709\u9000\u6b65\uff08\u6210\u56e0\u89c1 6.3\uff09',
     '\u6709\u9000\u6b65\uff08\u9010\u6b65\u8bb0\u8d26\uff0c\u89c1 6.5\uff09'),
    # fig suptitle DDPS v4
    ('DDPS v4\uff1a\u53ea\u7528 10 dB \u57fa\u7ebf\u8bad\u7ec3 \u2192 \u8de8 15 \u73af\u5883\u6cdb\u5316',
     'DDPS\uff1a\u53ea\u7528 10 dB \u57fa\u7ebf\u8bad\u7ec3 \u2192 \u8de8 15 \u73af\u5883\u6cdb\u5316'),
]

miss = 0
for old, new in fixes:
    if old in s:
        s = s.replace(old, new, 1)
        print(f'OK: {new[:60]}...')
    else:
        miss += 1
        print(f'MISS: {old[:60]}...')

with io.open(p, 'w', encoding='utf-8') as f:
    f.write(s)
print(f'\n{len(fixes)} attempted, {miss} missed')
