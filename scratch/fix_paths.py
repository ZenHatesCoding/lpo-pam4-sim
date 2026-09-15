# -*- coding: utf-8 -*-
"""去掉'沿用 v4 同协议'版本历史措辞 + docs/08→docs/09。"""
import io
p = 'make_deliverable_v5.py'
with io.open(p, 'r', encoding='utf-8') as f:
    s = f.read()

fixes = [
    ('result/ddps_v4_trace_check.csv\uff08\u6cbf\u7528 v4 \u540c\u534f\u8bae\uff09',
     'result/ddps_v4_trace_check.csv'),
    ('K=1\u202615 \u65f6\u7684\u6b63\u5411\u7528\u4f8b\u6570\u3001\u5e73\u5747\u6539\u5584\u3001\u52a3\u5316\u6b65\u6570\uff08\u6cbf\u7528 v4 \u540c\u534f\u8bae\uff09',
     'K=1\u202615 \u65f6\u7684\u6b63\u5411\u7528\u4f8b\u6570\u3001\u5e73\u5747\u6539\u5584\u3001\u52a3\u5316\u6b65\u6570'),
    ('\u539f\u59cb\u6570\u636e\u89c1 <span class="mono">docs/08</span> \u00a74.1',
     '\u539f\u59cb\u6570\u636e\u89c1 <span class="mono">docs/09</span> \u00a74.1'),
]

miss = 0
for old, new in fixes:
    if old in s:
        s = s.replace(old, new, 1)
        print(f'OK: {new[:50]}...')
    else:
        miss += 1
        print(f'MISS: {old[:50]}...')

with io.open(p, 'w', encoding='utf-8') as f:
    f.write(s)
print(f'{len(fixes)} attempted, {miss} missed')
