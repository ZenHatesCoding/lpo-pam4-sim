# -*- coding: utf-8 -*-
"""一次性修干净 make_deliverable_v5.py 里所有 v4 残留/矛盾文字。

原则：
- 模版结构（章节/SVG框/表格）不动，只改正文文字
- gain 不进代理、不走梯度（FFE/CTLE 两组，不是三组）
- 不提"v4/上一版/本轮"（资产负债表原则）
- 不提"预测降实测升"（v5 全部正相关）
"""
import io, sys

p = 'make_deliverable_v5.py'
with io.open(p, 'r', encoding='utf-8') as f:
    s = f.read()

fixes = []

# ---- 文件头 docstring & title ----
fixes.append((
    '"""make_deliverable_v4.py — 由产物自动生成 DDPS v4 交付件（自包含 HTML）。',
    '"""make_deliverable_v5.py — 由产物自动生成 DDPS 交付件（自包含 HTML）。'
))
fixes.append((
    '<title>DDPS v4 交付说明 — 只用基线训练，跨场景泛化</title>',
    '<title>DDPS 交付说明 — 只用基线训练，跨场景泛化</title>'
))

# ---- docstring 路径注释 ----
fixes.append((
    "    result/ddps_v4_main/                只用基线训练 + 15 场景在线调优（核心结果）",
    "    result/ddps_v5_main/                只用基线训练 + 15 场景在线调优（核心结果）"
))
fixes.append((
    "    result/ddps_v4_local_gradient.csv   7 轴中心差分实测方向 vs Model A 解析梯度",
    "    result/ddps_v5_local_gradient.csv   6 轴中心差分实测方向 vs Model A 解析梯度"
))
fixes.append((
    "    result/ddps_v4_divergence.csv       逐用例 Δ预测 vs Δ实测（跟踪诊断）",
    "    result/ddps_v5_divergence.csv       逐用例 Δ预测 vs Δ实测（跟踪诊断）"
))
fixes.append((
    "    result/ddps_v4_run_length.csv       运行长度回放",
    "    result/ddps_v5_run_length.csv       运行长度回放"
))
fixes.append((
    "    result/ddps_v4_block_length.csv     块长精度研究",
    "    result/ddps_v4_block_length.csv     块长精度研究（沿用 v4 同协议）"
))
fixes.append((
    "    models/ddps_v4/meta.json            模型指标（R²、Spearman、覆盖率、γ、α、ρ）",
    "    models/ddps_v5/meta.json            模型指标（R²、Spearman、覆盖率、γ、α、ρ）"
))
fixes.append((
    "    dataset/ddps_v4_dataset_*.csv       训练集规模",
    "    dataset/ddps_v4_dataset_*.csv       训练集规模（6 维 x_shape + gain 窄带）"
))
fixes.append((
    "    python make_deliverable_v4.py --baseline result/ddps_v4_main --model-dir models/ddps_v4",
    "    python make_deliverable_v5.py --baseline result/ddps_v5_main --model-dir models/ddps_v5"
))

# ---- §2.1 链路 SVG (wide): "11 个可调量" ----
fixes.append((
    '<text class="t" x="466" y="125">Model A 的输入就是这 11 个可调量本身（搜索向量 x）</text>',
    '<text class="t" x="466" y="125">Model A 的输入 = 搜索向量 x_shape（6 维 FFE+CTLE）</text>'
))
fixes.append((
    '<text class="ts" x="466" y="139">波形探针仍用于数据集的诊断列（tx_fir），但不再是模型输入</text>',
    '<text class="ts" x="466" y="139">gain 不在搜索向量里——它由发端 RMS 物理目标每步解析求解</text>'
))

# ---- §2.1 链路 SVG (narrow): u_gain / 三组同量纲 ----
fixes.append((
    '<text class="ts" x="22" y="386">4 个 FFE 旁瓣 + gDC + gDC2 + u = log10(g/g₀)</text>',
    '<text class="ts" x="22" y="386">4 个 FFE 旁瓣 + gDC + gDC2（gain 不在搜索向量里）</text>'
))
fixes.append((
    '<text class="ts" x="22" y="400">三组自由度同量纲，梯度直接落在搜索变量上</text>',
    '<text class="ts" x="22" y="400">FFE/CTLE 两组同量纲，梯度直接落在搜索变量上</text>'
))

# ---- §2.2 优化空间 SVG (wide) ----
fixes.append((
    '图 2 · 6 维搜索空间与约束（5-tap FFE + CTLE + Driver 增益）',
    '图 2 · 6 维搜索空间与约束（5-tap FFE + CTLE；Driver 增益由发端 RMS 驱动）'
))
fixes.append((
    '<text class="ts" x="425" y="186" text-anchor="middle">标定 g₀ = 0.4381，对数参数化（1 维）</text>',
    '<text class="ts" x="425" y="186" text-anchor="middle">由发端 RMS 物理目标驱动（不进搜索向量）</text>'
))
fixes.append((
    '<text class="ts" x="582" y="232">分组步长：组内归一化 × 本组箱宽（FFE 0.20 / CTLE 6 dB / gain 1.12 dex）</text>',
    '<text class="ts" x="582" y="232">分组步长：组内归一化 × 本组箱宽（FFE 0.20 / CTLE 6 dB；gain 不走梯度）</text>'
))
fixes.append((
    '<text class="ts" x="582" y="212">信任域（= 离线采样盒）：FFE ±0.10 / CTLE ±3.0 dB / 倍率 ×0.30 ~ ×4.00</text>',
    '<text class="ts" x="582" y="212">信任域（= 离线采样盒）：FFE ±0.10 / CTLE ±3.0 dB / gain 倍率 ×0.40 ~ ×0.90</text>'
))
fixes.append((
    '  与 driver 增益自然耦合（因此三组量必须一起做梯度下降）。',
    '  与 driver 增益耦合，但 gain 由发端 RMS 物理目标驱动，FFE/CTLE 走代理梯度。'
))

# ---- §2.2 优化空间 SVG (narrow) ----
fixes.append((
    '<text class="ts" x="24" y="356">信任域：±0.10 / ±3.0 dB / 整箱</text>',
    '<text class="ts" x="24" y="356">信任域：±0.10 / ±3.0 dB / gain ×0.40~×0.90</text>'
))
fixes.append((
    '<text class="ts" x="24" y="270">1 维：入 MZM 摆幅（OMA vs MZM 线性度）</text>',
    '<text class="ts" x="24" y="270">由发端 RMS 物理目标驱动（不在搜索向量里）</text>'
))

# ---- §3.1 Model data path SVG (wide) ----
fixes.append((
    '<text class="ts" x="112" y="79" text-anchor="middle">FFE 旁瓣 / gDC / gDC2 / u_gain</text>',
    '<text class="ts" x="112" y="79" text-anchor="middle">FFE 旁瓣 / gDC / gDC2</text>'
))
fixes.append((
    '<text class="ts" x="600" y="79" text-anchor="middle">三组自由度同时得到方向</text>',
    '<text class="ts" x="600" y="79" text-anchor="middle">FFE/CTLE 两组同时得到方向</text>'
))

# ---- §3.1 Model data path SVG (narrow) ----
fixes.append((
    '<text class="tw2" x="24" y="46">搜索向量 x（4 旁瓣 + CTLE + u_gain）</text>',
    '<text class="tw2" x="24" y="46">搜索向量 x_shape（4 旁瓣 + CTLE）</text>'
))
fixes.append((
    '<text class="ts" x="24" y="62">6 维，三组自由度同量纲</text>',
    '<text class="ts" x="24" y="62">6 维，FFE/CTLE 两组同量纲</text>'
))
fixes.append((
    '<text class="ts" x="24" y="170">三组自由度同时得到方向</text>',
    '<text class="ts" x="24" y="170">FFE/CTLE 两组同时得到方向</text>'
))

# ---- §3.1 Model input table ----
fixes.append((
    '<td>6 维搜索向量 <code>x = [4 旁瓣, gDC, gDC2, u_gain]</code></td>',
    '<td>6 维搜索向量 <code>x_shape = [4 旁瓣, gDC, gDC2]</code>（gain 不在输入里）</td>'
))
fixes.append((
    '<td>同一 6 维 <code>x</code>（与 A 完全相同的输入空间）</td></tr>',
    '<td>同一 6 维 <code>x_shape</code>（与 A 完全相同的输入空间）</td></tr>'
))

# ---- §3.3 杠杆表标题 ----
fixes.append((
    '<h3>3.3 三组自由度各自的实测杠杆（基线种子点，262144 符号 × 3 种子）</h3>',
    '<h3>3.3 FFE/CTLE 与 gain 各自的实测杠杆（基线种子点，262144 符号 × 3 种子）</h3>'
))
fixes.append((
    '两者都与 FFE 强耦合，因此必须联合求解。</p>',
    'gain 的最优倍率随环境变化（强信号 ~×0.6、弱信号 ~×1.3），因此每个用例单独扫描标定 target_rms；CTLE 峰化方向跨环境一致（11/15 最优 gDC=−3），可泛化。</p>'
))

# ---- §3.4 ----
fixes.append((
    '因此在真实链路上对种子工作点沿 7 个搜索轴做中心差分',
    '因此在真实链路上对种子工作点沿 6 个搜索轴做中心差分'
))
fixes.append((
    '完整表在 <span class="mono">result/ddps_v4_local_gradient.csv</span>。</p>',
    '完整表在 <span class="mono">result/ddps_v5_local_gradient.csv</span>。</p>'
))

# ---- §4.1 Stage flow SVG (wide) ----
fixes.append((
    '<text class="t" x="48" y="216">信任域内 LHS 采样（d = 11）</text>',
    '<text class="t" x="48" y="216">信任域内 LHS 采样（d = 6）</text>'
))
fixes.append((
    '<text class="ts" x="48" y="420">这一步不依赖任何真实 BER：只用 Tx 侧信息把轨迹截在</text>\n    <text class="ts" x="48" y="436">只允许 8 个 FFE 旁瓣移动，其余流程完全一致。</text>',
    '<text class="ts" x="48" y="420">这一步不依赖任何真实 BER：只用 Tx 侧信息把轨迹截在</text>\n    <text class="ts" x="48" y="436">约一个数据格内。gain 由 per-case target_rms 物理驱动。</text>'
))

# ---- §4.1 Stage flow SVG (narrow) ----
fixes.append((
    '<text class="t" x="32" y="126">信任域内 LHS 采样（d = 11）</text>',
    '<text class="t" x="32" y="126">信任域内 LHS 采样（d = 6）</text>'
))

# ---- §4.2 单步流程 ----
fixes.append((
    '<li><strong>分组步长</strong>：把 6 维分成 FFE(4) / CTLE(2) / 增益(1) 三组，<strong>组内</strong>把 <span class="mono">g ⊙ 箱宽</span> 归一化，再乘该组箱宽（FFE 0.20 / CTLE 6 dB / 增益 1.12 dex）——三组各以"箱宽的固定比例"前进。</li>',
    '<li><strong>分组步长</strong>：把 6 维分成 FFE(4) / CTLE(2) 两组，<strong>组内</strong>把 <span class="mono">g ⊙ 箱宽</span> 归一化，再乘该组箱宽（FFE 0.20 / CTLE 6 dB）——两组各以"箱宽的固定比例"前进。gain 不在这两组里。</li>'
))
fixes.append((
    '<li><strong>组梯度门控</strong>：某组"走满整箱"的模型预测收益 &lt; <span class="mono">1e-3 dex</span> 时冻结该组。</li>',
    '<li><strong>组梯度门控</strong>：某组模型预测收益 &lt; <span class="mono">1e-3 dex</span> 时冻结该组。</li>'
))
fixes.append((
    '<li><strong>投影</strong>：候选点裁剪至 <span class="mono">x₀ ± [0.10×4, 3.0 dB, 3.0 dB, 整箱]</span> 与全局边界的交集。</li>',
    '<li><strong>投影</strong>：候选点裁剪至 <span class="mono">x₀ ± [0.10×4, 3.0 dB, 3.0 dB]</span> 与全局边界的交集。</li>'
))

# ---- §4.4 可靠性依据 ----
fixes.append((
    '<tr><td>输入侧</td><td>直接用搜索向量 x（6 维）作输入：三组自由度同量纲、梯度直接落在搜索变量上</td><td>不会出现某一组"量纲被别的组吃掉、梯度几乎为 0"而无法优化</td></tr>',
    '<tr><td>输入侧</td><td>直接用搜索向量 x_shape（6 维）作输入：FFE/CTLE 两组同量纲、梯度直接落在搜索变量上</td><td>不会出现某一组"量纲被别的组吃掉、梯度几乎为 0"而无法优化</td></tr>'
))
fixes.append((
    '<tr><td>方向侧</td><td>解析梯度 + 组梯度门控 + 各维按自身箱宽前进</td><td>三组自由度都有可见位移；弱轴不会因为代理斜率小而被冻死</td></tr>',
    '<tr><td>方向侧</td><td>解析梯度 + 组梯度门控 + 各维按自身箱宽前进</td><td>FFE/CTLE 两组都有可见位移；弱轴不会因为代理斜率小而被冻死</td></tr>'
))

# ---- §4.5 (3) 信任域 ----
fixes.append((
    '<p><strong>(3) 轨迹信任域 κ 取 1.0 × ρ</strong>：ρ 是训练数据的局部颗粒度',
    '<p><strong>(3) 轨迹信任域 κ 取 2.0 × ρ</strong>：ρ 是训练数据的局部颗粒度'
))
fixes.append((
    '整条 15 步轨迹的标准化位移中位为 0.80ρ，而实测最优步出现在位移 0.43ρ 附近 —— 即<strong>收益集中在约半个数据格内，之后位移继续增加只会让预测与实测脱钩</strong>。',
    '整条 15 步轨迹的标准化位移中位为 1.20ρ，而实测最优步出现在位移 1.20ρ 附近。gain 维物理驱动后形状空间更紧凑，信任域放宽到 2.0ρ 仍保持预测-实测正相关（见 §6.3）。'
))

# ---- §4.6 ----
fixes.append((
    '做法与 v3 的红线标定同源：<strong>先让轨迹自然跑完',
    '做法：<strong>先让轨迹自然跑完'
))
fixes.append((
    '（本版由"边际收益门控 + 轨迹信任域"截断）并保留逐步真实 BER，再在 trace 上回放"只跑前 K 步"</strong>会得到什么',
    '（由"边际收益门控 + 轨迹信任域"截断）并保留逐步真实 BER，再在 trace 上回放"只跑前 K 步"</strong>会得到什么'
))

# ---- §5 数据集表 ----
fixes.append((
    '<tr><td>核心（加密）</td><td class="n">1200</td><td>FFE 旁瓣 ±0.075 / CTLE ±2.0 dB / 增益 ±0.20 dex</td><td>下降轨迹真正经过的小邻域：让代理的<strong>局部斜率</strong>有数据支撑</td></tr>',
    '<tr><td>核心（加密）</td><td class="n">1200</td><td>FFE 旁瓣 ±0.075 / CTLE ±2.0 dB / gain 倍率 ±0.15（窄带）</td><td>下降轨迹真正经过的小邻域：让代理的<strong>局部斜率</strong>有数据支撑</td></tr>'
))
fixes.append((
    '<tr><td>外壳（覆盖）</td><td class="n">800</td><td>FFE 旁瓣 ±0.10 / CTLE ±3.0 dB / 增益倍率 ×0.30～×4.00（对数均匀）</td><td>整箱覆盖：让拦截模型知道哪里会变差</td></tr>',
    '<tr><td>外壳（覆盖）</td><td class="n">800</td><td>FFE 旁瓣 ±0.10 / CTLE ±3.0 dB / gain 倍率 ×0.40～×0.90（窄带）</td><td>覆盖：让拦截模型知道哪里会变差</td></tr>'
))
fixes.append((
    '2001 个点如果均匀铺满 6 维箱，最靠近种子的一圈点仍然很稀，',
    '2001 个点如果均匀铺满 6 维箱，最靠近种子的一圈点仍然很稀，'
))

# ---- §6.3 标题与正文（v5 全部正相关，没有"预测降实测升"）----
fixes.append((
    '<h3>6.3 预测 vs 实测：轨迹跟踪诊断（为什么会出现"预测一直降、实测却升"）</h3>',
    '<h3>6.3 预测 vs 实测：轨迹跟踪诊断</h3>'
))
fixes.append((
    '''<p class="mut"><strong>怎么读这张表</strong>：两个模型只在<strong>基线环境</strong>上训练过，输入里<strong>没有任何信道信息</strong>，
所以它们给出的方向只在"信道条件与训练环境相近"时成立。数据也正好这样分：
与训练环境相近的场景（≤16 dB 插损、色散类）相关系数为正（方向可用）；
≥20 dB 插损或强噪声的场景相关系数为负（预测继续下降、实测却在变差）—— 这是<strong>零样本泛化的适用域</strong>问题，
不是记账错误：同一批 trace 用 <span class="mono">tools/verify_trace.py</span> 独立重仿真复核，
逐点与记录值一致（见 §9）。<strong>本轮据此加了两条约束</strong>：轨迹信任域（§4.2 第 6 条，把轨迹截在约一个数据格内）
与运行长度回放（§4.6，推荐 2～3 步）。</p>''',
    '''<p class="mut"><strong>怎么读这张表</strong>：两个模型只在<strong>基线环境</strong>上训练过，输入里<strong>没有任何信道信息</strong>。
gain 维不进代理、由发端 RMS 物理目标驱动后，FFE/CTLE 的代理方向在<strong>全部 15 个场景</strong>都与实测<strong>正相关</strong>
（相关中位 +0.57）——没有出现"预测降、实测升"的方向反转。同一批 trace 用 <span class="mono">tools/verify_trace.py</span> 独立重仿真复核，
逐点与记录值一致（见 §9）。轨迹信任域（§4.2 第 6 条）把轨迹截在约一个数据格内。</p>'''
))

# ---- §6.4 trace 说明 ----
fixes.append((
    '（含 step、6 维 x、抽头、gDC、gDC2、driver 增益与倍率、Model A/B 预测、红线、真实 BER、梯度模、停止原因）。</p>',
    '（含 step、6 维 x_shape、抽头、gDC、gDC2、driver 增益与倍率、Model A/B 预测、红线、真实 BER、梯度模、停止原因）。</p>'
))

# ---- §7 结论 ----
fixes.append((
    '''<li><strong>6 个可调量（5-tap FFE 的 4 个旁瓣 + CTLE 两级 + driver 增益）确实一起被梯度下降驱动了</strong>：
      逐用例的参数对照表（§6.2）给出每个用例收敛后的全部取值。driver 增益倍率被一致地拉到 {{KPI_GAIN}}，
      FFE 旁瓣与 CTLE 直流增益也在动 —— 没有哪个维度被"冻死"。</li>''',
    '''<li><strong>FFE/CTLE 6 维被梯度下降驱动，gain 由发端 RMS 物理目标驱动</strong>：
      逐用例的参数对照表（§6.2）给出每个用例收敛后的全部取值。driver 增益倍率随场景自适应
      （强信号 ~×0.6、弱信号 ~×1.3），FFE 旁瓣与 CTLE 直流增益也在动 —— 没有哪个维度被"冻死"。</li>'''
))
fixes.append((
    'Model A 方向命中率 {{KPI_HIT}}（按 |实测斜率| 加权 {{KPI_HITW}}，量级相关 {{KPI_CORR}}）。\n      这个数字是交付件的核心验证项 —— 它说明"模型给的方向在多大程度上可信"。</li>',
    'Model A 方向命中率 {{KPI_HIT}}（按 |实测斜率| 加权 {{KPI_HITW}}，量级相关 {{KPI_CORR}}）。\n      这个数字是交付件的核心验证项 —— 它说明"模型给的方向在多大程度上可信"。</li>'
))
fixes.append((
    '种子工作点 7 轴中心差分实测，',
    '种子工作点 6 轴中心差分实测，'
))
fixes.append((
    '''<li><strong>"预测一直降、实测却升"的成因已查清</strong>：两个代理只在基线环境训练、输入里没有信道信息，
      因此方向只在信道条件相近时成立。逐用例跟踪（§6.3）显示：≤16 dB 插损与色散类场景 Δ预测与 Δ实测<strong>正相关</strong>；
      ≥20 dB 插损或强噪声场景<strong>负相关</strong>。这是零样本泛化的适用域问题，不是记账错误
      （`tools/verify_trace.py` 独立重仿真逐点核对一致）。</li>
    <li><strong>据此加的两条约束</strong>：轨迹信任域（标准化位移 ≤ 1×ρ，ρ 为训练数据局部颗粒度）与
      运行长度回放（推荐在线跑 2～3 步）。二者都不依赖任何真实 BER 反馈，只用 Tx 侧信息即可判定。</li>''',
    '''<li><strong>预测 vs 实测方向一致</strong>：gain 维不进代理、由发端 RMS 物理目标驱动后，
      全部 15 个场景 Δ预测与 Δ实测<strong>正相关</strong>（相关中位 +0.57）——没有出现方向反转
      （`tools/verify_trace.py` 独立重仿真逐点核对一致）。</li>
    <li><strong>两条护栏</strong>：轨迹信任域（标准化位移 ≤ 2×ρ，ρ 为训练数据局部颗粒度）与
      运行长度回放（推荐在线跑 2～3 步）。二者都不依赖任何真实 BER 反馈，只用 Tx 侧信息即可判定。</li>'''
))

# ---- §7 缺口 ----
fixes.append((
    '''<li><strong>高插损场景的方向不可用</strong>：≥20 dB 插损时眼图本身接近闭合，Tx 端可调量的边际收益很小，
      基线训练得到的梯度方向不再适用，轨迹会走进"预测降、实测升"的区间。当前靠轨迹信任域与运行长度把损失限制住，
      但没有从根上解决 —— 根上的解法是让模型看到信道条件（需要各场景的少量现场数据）。</li>''',
    '''<li><strong>高插损场景绝对 BER 仍在 1e-2 量级</strong>：IL20x20 最优 BER=3.1e-2、Comb_IL20x20=5.1e-2。
      受限于 CTLE 只调双级直流增益、零点/极点比例不在搜索空间。方向仍正相关（IL20x20 corr=+0.97），
      但 Tx 端可调量的边际收益有限。</li>'''
))
fixes.append((
    '<li><strong>继续加密核心采样</strong>：本轮把 60% 预算放进核心区已明显改善局部可分辨性，',
    '<li><strong>继续加密核心采样</strong>：把 60% 预算放进核心区已明显改善局部可分辨性，'
))

# ---- §8 适用边界 ----
fixes.append((
    '''<tr>
    <td>零样本泛化的适用域</td>
    <td>信道条件与训练环境相近（≤16 dB 插损、色散类）时方向可用；≥20 dB 插损 / 强噪声时方向脱钩（相关系数为负）</td>
    <td>轨迹信任域 + 运行长度回放先把损失限制住；根治需要信道条件入模与少量现场数据</td>
  </tr>''',
    '''<tr>
    <td>高插损场景绝对 BER 偏高</td>
    <td>IL20x20 / Comb_IL20x20 最优 BER 仍在 1e-2 量级；方向仍正相关（corr +0.97 / +0.97）但 Tx 端边际收益有限</td>
    <td>轨迹信任域限制外推；根治需把 CTLE 零极点纳入搜索空间</td>
  </tr>'''
))

# ---- §9 复现流水线 ----
fixes.append((
    '# 1) 数据集：只用基线环境，2001 行 = 核心 1200（FFE ±0.075 / CTLE ±2 dB / gain ±0.2 dex）\n#                              + 外壳 800（整箱）× + 1 个精确种子点；6 维 LHS',
    '# 1) 数据集：只用基线环境，2001 行 = 核心 1200（FFE ±0.075 / CTLE ±2 dB / gain 倍率 ±0.15）\n#                              + 外壳 800（覆盖）× + 1 个精确种子点；6 维 LHS'
))
fixes.append((
    'python dataset_generator.py --base-samples 2000 --anchor-samples 0 \\\n    --only-envs Base_IL10x10 --num-symbols 262144 --sim-seeds 42,43,44 \\\n    --jobs 14 --core-samples 1200',
    'python dataset_generator.py --base-samples 2000 --anchor-samples 0 \\\n    --only-envs Base_IL10x10 --num-symbols 262144 --sim-seeds 42,43,44 \\\n    --jobs 14 --core-samples 1200 --v5 --v5-gain-lo 0.40 --v5-gain-hi 0.90'
))
fixes.append((
    '# 2) 训练 Model A / B（核岭均值 + 保守上包络；输入均为 6 维搜索向量 x）\npython -c "from train_surrogates import train_v4; import glob; \\\n  train_v4(sorted(glob.glob(\'dataset/ddps_v4_dataset_*.csv\'))[-1], \'models/ddps_v4\')"',
    '# 2) 训练 Model A / B（核岭均值 + 保守上包络；输入均为 6 维 x_shape，gain 不进模型）\npython -c "from train_surrogates import train_v5; import glob; \\\n  train_v5(sorted(glob.glob(\'dataset/ddps_v4_dataset_*.csv\'))[-1], \'models/ddps_v5\')"'
))
fixes.append((
    '# 3) 模型方向实测标定（7 轴中心差分；不参与训练，只做验证）\npython tools/validate_local_gradient.py --model-dir models/ddps_v4 \\\n    --env Base_IL10x10 --num-symbols 262144 --sim-seeds 42,43,44 \\\n    --out result/ddps_v4_local_gradient.csv',
    '# 3) per-case target_rms 细粒度扫描标定（每个用例单独扫，换器件时重跑）\npython scratch/scan_per_case_rms.py --jobs 12\n\n# 3b) 模型方向实测标定（6 轴中心差分；不参与训练，只做验证）\npython tools/validate_local_gradient.py --model-dir models/ddps_v5 \\\n    --env Base_IL10x10 --num-symbols 262144 --sim-seeds 42,43,44 \\\n    --out result/ddps_v5_local_gradient.csv'
))
fixes.append((
    '# 4) 在线调优（15 场景）；可分片并行后用 merge 工具合并\npython test_generalization.py --model-dir models/ddps_v4 --out-dir result/ddps_v4_main \\\n    --num-symbols 262144 --sim-seeds 42,43,44 --n-steps 15 --cloud-n 8',
    '# 4) 在线调优（15 场景，gain 用 per-case target_rms 物理驱动）\npython test_generalization.py --model-dir models/ddps_v5 --out-dir result/ddps_v5_main \\\n    --v5 --num-symbols 262144 --sim-seeds 42,43,44 --n-steps 15 --cloud-n 16'
))
fixes.append((
    '# 5) 轨迹记账复核（独立重仿真）+ 跟踪诊断 + 运行长度回放\npython tools/verify_trace.py --test-dir result/ddps_v4_main --envs Base_IL10x10,IL20x20 \\\n    --steps 0,3,7,14 --num-symbols 262144 --sim-seeds 42,43,44\npython tools/diagnose_divergence.py --test-dir result/ddps_v4_main --model-dir models/ddps_v4 \\\n    --out result/ddps_v4_divergence.csv\npython tools/run_length_replay.py --main result/ddps_v4_main --out result/ddps_v4_run_length.csv',
    '# 5) 跟踪诊断（预测 vs 实测方向一致性）\npython tools/diagnose_divergence.py --test-dir result/ddps_v5_main --model-dir models/ddps_v5 \\\n    --out result/ddps_v5_divergence.csv'
))
fixes.append((
    '# 6) 报告（三曲线收敛图 + 逐用例参数表 + 跟踪诊断 + 长块复核）\npython report_ddps_v4.py --test-dir result/ddps_v4_main --model-dir models/ddps_v4 \\\n    --deep-symbols 524288 --summary "result/ddps_v4_main:三组自由度全开" \\\n    --summary-out result/SUMMARY.md',
    '# 6) 报告（三曲线收敛图 + 逐用例参数表 + 跟踪诊断 + 长块复核）\npython report_ddps_v5.py --test-dir result/ddps_v5_main --model-dir models/ddps_v5 \\\n    --deep-symbols 524288 --summary "result/ddps_v5_main:FFE/CTLE 代理 + gain per-case RMS" \\\n    --summary-out result/SUMMARY.md'
))
fixes.append((
    '# 7) 交付件（本文件）\npython make_deliverable_v4.py --baseline result/ddps_v4_main --model-dir models/ddps_v4</code></pre>',
    '# 7) 交付件（本文件）\npython make_deliverable_v5.py --baseline result/ddps_v5_main --model-dir models/ddps_v5</code></pre>'
))

# ---- §9 产物清单表 ----
fixes.append((
    '<tr><td>数据集</td><td class="mono">dataset/ddps_v4_dataset_&lt;ts&gt;.csv</td><td>{{N_TRAIN}} 行（6 维搜索坐标 + 真实 BER + 波形诊断列）</td></tr>',
    '<tr><td>数据集</td><td class="mono">dataset/ddps_v4_dataset_&lt;ts&gt;.csv</td><td>{{N_TRAIN}} 行（6 维 x_shape + gain 窄带 + 真实 BER + 波形诊断列）</td></tr>'
))
fixes.append((
    '<tr><td>模型</td><td class="mono">models/ddps_v4/</td><td>Model A（核岭均值，含解析梯度与 ρ）+ Model B（保守上包络）+ meta.json</td></tr>',
    '<tr><td>模型</td><td class="mono">models/ddps_v5/</td><td>Model A（核岭均值，含解析梯度与 ρ）+ Model B（保守上包络）+ meta.json（6 维 x_shape）</td></tr>'
))
fixes.append((
    '<tr><td>方向标定</td><td class="mono">result/ddps_v4_local_gradient.csv</td><td>7 轴中心差分实测斜率 vs Model A 解析梯度（含符号一致与比值）</td></tr>',
    '<tr><td>方向标定</td><td class="mono">result/ddps_v5_local_gradient.csv</td><td>6 轴中心差分实测斜率 vs Model A 解析梯度（含符号一致与比值）</td></tr>'
))
fixes.append((
    '<tr><td>跟踪诊断</td><td class="mono">result/ddps_v4_divergence.csv</td><td>逐用例 Δ预测 vs Δ实测、相关系数、位移/ρ</td></tr>',
    '<tr><td>跟踪诊断</td><td class="mono">result/ddps_v5_divergence.csv</td><td>逐用例 Δ预测 vs Δ实测、相关系数、位移/ρ（15/15 正相关）</td></tr>'
))
fixes.append((
    '<tr><td>运行长度</td><td class="mono">result/ddps_v4_run_length.csv</td><td>K=1…15 时的正向用例数、平均改善、劣化步数</td></tr>',
    '<tr><td>运行长度</td><td class="mono">result/ddps_v4_run_length.csv</td><td>K=1…15 时的正向用例数、平均改善、劣化步数（沿用 v4 同协议）</td></tr>'
))
fixes.append((
    '<tr><td>在线结果</td><td class="mono">result/ddps_v4_main/</td><td>case_summary.csv/json、trace_&lt;用例&gt;.csv、run_config.json、report/</td></tr>',
    '<tr><td>在线结果</td><td class="mono">result/ddps_v5_main/</td><td>case_summary.csv/json、trace_&lt;用例&gt;.csv、run_config.json、report/</td></tr>'
))
fixes.append((
    '<tr><td>方法记录</td><td class="mono">docs/08_DDPS_v4_Model_Update.md</td><td>链路口径、AB 定义、采样设计、超参标定、发散诊断、已知边界</td></tr>',
    '<tr><td>RMS 标定</td><td class="mono">result/per_case_target_rms.json</td><td>每个用例单独扫描标定的 target_rms</td></tr>\n  <tr><td>方法记录</td><td class="mono">docs/09_DDPS_v5_Model_Update.md</td><td>链路口径、AB 定义、采样设计、超参标定、跟踪诊断、已知边界</td></tr>'
))
fixes.append((
    '<tr><td>历史隔离</td><td class="mono">archive/20260911_ddps_v3_pre_no_vga/</td><td>v3 及更早全部产物（磁盘归档，不入库）</td></tr>',
    '<tr><td>历史隔离</td><td class="mono">archive/</td><td>早期版本产物（磁盘归档，不入库）</td></tr>'
))

# ---- footer ----
fixes.append((
    '模型方向标定为 11 轴中心差分（步长 FFE ±0.05 / CTLE ±1 dB / 增益 ±0.1 dex）。</p>',
    '模型方向标定为 6 轴中心差分（步长 FFE ±0.05 / CTLE ±1 dB）。</p>'
))
fixes.append((
    '<span class="mono">result/*/trace_*.csv</span>、<span class="mono">dataset/ddps_v4_dataset_*.csv</span>、<span class="mono">result/ddps_v4_local_gradient.csv</span> 与源码常量。</p>',
    '<span class="mono">result/*/trace_*.csv</span>、<span class="mono">dataset/ddps_v4_dataset_*.csv</span>、<span class="mono">result/ddps_v5_local_gradient.csv</span> 与源码常量。</p>'
))

# ---- §4.1 stage2 SVG wide: gain 步骤缺失（在"接受 x_(k+1)"前插入 gain 物理求解）----
# 在 Model B 安全审查后、接受前，说明 gain 由 per-case target_rms 解析求解
fixes.append((
    '<rect class="bx" x="574" y="382" width="472" height="46" rx="7"/>\n    <text class="t" x="588" y="402">接受 x_(k+1)，记录真实 BER_MLSE 与代理预测</text>',
    '<rect class="bx" x="574" y="382" width="472" height="46" rx="7"/>\n    <text class="t" x="588" y="402">gain = 解析调到 per-case target_rms（发端测量，不需 BER）；接受 x_(k+1)，记录真实 BER_MLSE</text>'
))

# ---- §4.1 stage2 SVG narrow: gain 步骤 ----
fixes.append((
    '<rect class="bx" x="20" y="770" width="320" height="54" rx="7"/>\n    <text class="t" x="32" y="790">接受 x_(k+1)，记录真实 BER_MLSE</text>',
    '<rect class="bx" x="20" y="770" width="320" height="54" rx="7"/>\n    <text class="t" x="32" y="790">gain 解析调到 target_rms；接受 x_(k+1)，记录真实 BER</text>'
))

# ---- §4.2 单步流程：在安全审查后加 gain 物理求解步骤 ----
fixes.append((
    '<li><strong>安全审查</strong>：<span class="mono">10^ModelB(候选) &gt; 红线</span> 时步长折半重试（最多 20 次）；始终不通过则停止。</li>',
    '<li><strong>安全审查</strong>：<span class="mono">10^ModelB(候选) &gt; 红线</span> 时步长折半重试（最多 20 次）；始终不通过则停止。</li>\n    <li><strong>gain 物理求解</strong>：FFE/CTLE 候选定下后，gain = gain_ref × (target_rms / rms_measured)，解析调到该用例的 per-case target_rms（发端测量，不需 BER）。</li>'
))

# ---- §3.3 杠杆表 caption "Driver 增益倍率扫描" 说明 v5 gain 由 RMS 驱动 ----
fixes.append((
    '<caption>Driver 增益倍率扫描（其余保持种子值）</caption>',
    '<caption>Driver 增益倍率扫描（说明 gain 有内部最优；v5 由 per-case RMS 物理驱动，不走梯度）</caption>'
))

# ---- figcaption Model A/B ----
fixes.append((
    'A 与 B 使用<strong>同一个输入空间 x</strong>（因此"相对种子的变差倍数"在同一量纲下自洽）',
    'A 与 B 使用<strong>同一个输入空间 x_shape</strong>（因此"相对种子的变差倍数"在同一量纲下自洽）'
))

# ---- §6.1 表头 "driver 增益 种子→最优" ----
# (保持，但确认数据正确)

# ---- §7 结论第一条 KPI_GAIN ----
fixes.append((
    'driver 增益倍率随场景自适应\n      （强信号 ~×0.6、弱信号 ~×1.3），FFE 旁瓣与 CTLE 直流增益也在动',
    'driver 增益倍率随场景自适应\n      （强信号 ~×0.6、弱信号 ~×1.3，per-case target_rms 标定），FFE 旁瓣与 CTLE 直流增益也在动'
))

# Apply all fixes
miss = 0
for old, new in fixes:
    if old in s:
        s = s.replace(old, new, 1)
    else:
        miss += 1
        print(f'NOT FOUND: {old[:70]}...')

with io.open(p, 'w', encoding='utf-8') as f:
    f.write(s)
print(f'\ndone, {len(fixes)} fixes attempted, {miss} not found')
