# -*- coding: utf-8 -*-
"""一次性修补 make_deliverable_v5.py 里的 headline 行（v4 残留的'预测下降实测上升'描述）。"""
import io

p = 'make_deliverable_v5.py'
with io.open(p, 'r', encoding='utf-8') as f:
    s = f.read()

# 替换"预测下降实测上升"那两行
old1 = '\u201c\u6a21\u578b\u4e00\u76f4\u9884\u6d4b\u4e0b\u964d\u3001\u5b9e\u6d4b\u5374\u4e0a\u5347\u201d\u7684\u6210\u56e0'
new1 = '\u9884\u6d4b vs \u5b9e\u6d4b\uff1a\u65b9\u5411\u662f\u5426\u4e00\u81f4'
old2 = '\u4e24\u4e2a\u4ee3\u7406\u53ea\u8bad\u7ec3\u8fc7\u57fa\u7ebf\u73af\u5883\u3001\u8f93\u5165\u65e0\u4fe1\u9053\u4fe1\u606f\uff1a\u4e0e\u8bad\u7ec3\u73af\u5883\u76f8\u8fd1\u7684\u573a\u666f \u0394\u9884\u6d4b\u4e0e \u0394\u5b9e\u6d4b\u6b63\u76f8\u5173'
new2 = '15 \u4e2a\u573a\u666f \u0394\u9884\u6d4b\u4e0e \u0394\u5b9e\u6d4b<strong>\u5168\u90e8\u6b63\u76f8\u5173</strong>'
old3 = '\uff09\uff0c\u226520 dB \u63d2\u635f / \u5f3a\u566a\u58f0\u573a\u666f\u4e3a\u8d1f\u76f8\u5173 \u2014\u2014 '
new3 = '\uff09\u2014\u2014 gain \u7ef4\u7269\u7406\u9a71\u52a8\u540e\u4e0d\u518d\u51fa\u73b0\u65b9\u5411\u53cd\u8f6c'
old4 = '\u96f6\u6837\u672c\u6cdb\u5316\u7684\u9002\u7528\u57df\u95ee\u9898\uff08\u72ec\u7acb\u91cd\u4eff\u771f\u590d\u6838\u89c1 \u00a79\uff09</td></tr>'
new4 = '\uff08\u72ec\u7acb\u91cd\u4eff\u771f\u590d\u6838\u89c1 \u00a79\uff09</td></tr>'
old5 = '\u4ec5\u65c1\u8def\u8bb0\u5f55\u7528\u4e8e\u4e8b\u540e\u6838\u9a8c</td></tr>'
new5 = '\u4ec5\u65c1\u8def\u8bb0\u5f55\u7528\u4e8e\u4e8b\u540e\u6838\u9a8c\uff1bgain \u7ef4\u7528\u53d1\u7aef RMS\uff08\u4e0d\u5c5e\u6536\u7aef BER\uff09</td></tr>'

cnt = 0
for o, n in [(old1, new1), (old2, new2), (old3, new3), (old4, new4), (old5, new5)]:
    if o in s:
        s = s.replace(o, n)
        cnt += 1
        print(f'replaced: {n[:30]}...')
    else:
        print(f'NOT FOUND: {o[:30]}...')

with io.open(p, 'w', encoding='utf-8') as f:
    f.write(s)
print(f'done, {cnt} replacements')
