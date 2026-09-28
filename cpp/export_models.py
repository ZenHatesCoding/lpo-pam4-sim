# export_models.py — 把训练好的双代理模型 (.pkl) 导出为 C++ 可读 JSON。
#   输出：W（二阶多项式权重）、mu/sd（标准化）、local_spacing（Model B 信任域 ρ）。
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
from train_surrogates import load_models


def export(m, path):
    out = {
        'W': [float(v) for v in np.asarray(m.W).ravel()],
        'mu': [float(v) for v in np.asarray(m.mu).ravel()],
        'sd': [float(v) for v in np.asarray(m.sd).ravel()],
        'local_spacing': float(getattr(m, 'local_spacing_', 0.0)),
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    return out


if __name__ == '__main__':
    a, b = load_models('models/ddps')
    os.makedirs('models/ddps', exist_ok=True)
    ea = export(a, 'models/ddps/model_a.json')
    eb = export(b, 'models/ddps/model_b.json')
    print(f'model_a: W={len(ea["W"])} mu={len(ea["mu"])}  (dim {len(ea["mu"])})')
    print(f'model_b: W={len(eb["W"])} mu={len(eb["mu"])}  rho={eb["local_spacing"]:.12f}')
