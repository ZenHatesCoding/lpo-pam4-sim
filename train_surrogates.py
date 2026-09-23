import numpy as np
import os
import pickle
import json

# ============================================================
# DDPS 双代理模型训练 —— 100% 白盒（纯 Numpy，面向芯片实现）
#
#   Model A (方向代理): 发端 8 维探针（7-tap Tx FIR + drive_rms）-> log10(MLSE BER)
#   Model B (风险控制): 参数域 7 维（4 FFE 旁瓣 + gDC + gDC2 + drive_rms）-> log10(MLSE BER)
#
# 不依赖任何第三方现成算法（无 sklearn）。Ridge 用闭式解
#   W = (X^T X + alpha I)^{-1} X^T y  手写；
# 二阶多项式特征、train/test 划分、R^2/MSE/Spearman 均手写。
# ============================================================

A_COLS = [f'tx_fir_{i}' for i in range(7)] + ['drive_rms']
B_COLS = [f'x_{i}' for i in range(6)] + ['drive_rms']


# ---------- 白盒多项式特征（degree 2） ----------
def _poly_features(X, degree=2):
    """X: (n, d) -> (n, 1 + d + d + C(d,2))，含 bias、一次项、平方项、交叉项。"""
    X = np.asarray(X, dtype=float)
    n, d = X.shape
    cols = [np.ones((n, 1))]
    for j in range(d):                      # 一次项
        cols.append(X[:, j:j + 1])
    for j in range(d):                      # 平方项
        cols.append((X[:, j:j + 1]) ** 2)
    for j in range(d):                      # 交叉项
        for k in range(j + 1, d):
            cols.append(X[:, j:j + 1] * X[:, k:k + 1])
    return np.hstack(cols)


# ---------- 白盒 Ridge 回归（闭式解） ----------
def _ridge_fit(Xp, y, alpha=1.0):
    n, f = Xp.shape
    A = Xp.T @ Xp + alpha * np.eye(f)
    b = Xp.T @ y
    return np.linalg.solve(A, b)


class WhiteBoxRidge:
    """白盒 Ridge 回归：二阶多项式特征 + L2 正则闭式解。

    提供 grad() 解析梯度：predict 的输出对原始输入的偏导数。
    二阶多项式 f(x) = w_0 + Σ w_j x_j + Σ w_jj x_j^2 + Σ w_jk x_j x_k
    => ∂f/∂x_i = w_i + 2 w_ii x_i + Σ_{k≠i} w_{ik} x_k
    """

    def __init__(self, degree=2, alpha=1.0):
        self.degree = degree
        self.alpha = alpha
        self.W = None
        self._dim = None

    def fit(self, X, y):
        X = np.asarray(X, dtype=float)
        self._dim = X.shape[1]
        Xp = _poly_features(X, self.degree)
        self.W = _ridge_fit(Xp, y, self.alpha)
        return self

    def predict(self, X):
        Xp = _poly_features(X, self.degree)
        return Xp @ self.W

    def grad(self, X):
        """解析梯度：∂f/∂x，返回与 X 同形状。

        特征排列（_poly_features）：
          [0]          bias
          [1..d]       一次项 x_j
          [d+1..2d]    平方项 x_j^2
          [2d+1..]     交叉项 x_j*x_k (j<k)
        """
        X = np.atleast_2d(np.asarray(X, dtype=float))
        n, d = X.shape
        w = self.W
        g = np.zeros_like(X, dtype=float)
        # 一次项
        for j in range(d):
            g[:, j] += w[1 + j]
        # 平方项
        for j in range(d):
            g[:, j] += 2.0 * w[1 + d + j] * X[:, j]
        # 交叉项
        idx = 1 + 2 * d
        for j in range(d):
            for k in range(j + 1, d):
                g[:, j] += w[idx] * X[:, k]
                g[:, k] += w[idx] * X[:, j]
                idx += 1
        return g


# ---------- 白盒 train/test 划分与评估 ----------
def _train_test_split_idx(n, test_size=0.2, seed=42):
    rng = np.random.RandomState(seed)
    idx = rng.permutation(n)
    n_test = int(n * test_size)
    return idx[n_test:], idx[:n_test]


def _r2_score(y_true, y_pred):
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    return 1.0 - ss_res / (ss_tot + 1e-12)


def _mse(y_true, y_pred):
    return float(np.mean((y_true - y_pred) ** 2))


def _spearman(y_true, y_pred):
    r = np.corrcoef(
        np.argsort(np.argsort(y_true)), np.argsort(np.argsort(y_pred))
    )[0, 1]
    return float(r)


def _col(df, *names):
    for n in names:
        if n in df.columns:
            return n
    raise KeyError(f"none of {names} in columns {list(df.columns)[:20]}...")


# ============================================================================
# 双代理训练（当前唯一训练入口）
#
#   Model A（方向代理）：输入 = [7-tap Tx FIR 探针, drive_rms]（8 维，波形域）
#       -> log10(BER_MLSE) 的条件均值。在线调优时拿不到收端 BER，只能拿发端探针，
#       所以 A 的全部意义就是建立发端探针到收端 BER 的方向映射。
#   Model B（风险控制）：输入 = [4 个 FFE 旁瓣, gDC, gDC2, drive_rms]（7 维，参数域）
#       -> log10(BER_MLSE) 的保守上包络。基于调优后参数预测性能，按变差幅度拒绝候选。
#       理想情况下全程不触发。
#
# A/B 输入空间不同（波形域 vs 参数域），误差来源相互独立。
# 梯度下降通过 A 的链式法则：扰动 7 维参数 -> 重算探针 -> 查 A -> 得方向。
# ============================================================================


def train(dataset_csv, model_dir="models", label_col=None, verbose=True,
          test_size=0.2, seed=42, pipeline_tag='ddps',
          gain_mode='gradient_with_rms_init'):
    """白盒 Ridge 双代理训练（A: 探针->BER；B: 参数->BER）。

    A 输入 = 7-tap Tx FIR 探针 + drive_rms（8 维波形域）。
    B 输入 = 6 维 x_shape（4 FFE 旁瓣 + gDC + gDC2）+ drive_rms（7 维参数域）。
    两者均用 WhiteBoxRidge（二阶多项式 + L2 正则闭式解，A 带解析梯度）。

    返回 (model_a, model_b, meta)。
    """
    import pandas as pd
    if label_col is None:
        label_col = _col(pd.read_csv(dataset_csv, nrows=1), 'log10_ber_mlse', 'log10_ber')
    df = pd.read_csv(dataset_csv)
    df = df[df[label_col] < -0.1].reset_index(drop=True)

    X_A = df[A_COLS].values.astype(float)
    X_B = df[B_COLS].values.astype(float)
    y = df[label_col].values.astype(float)
    envs = df['env'].values if 'env' in df.columns else None

    mu_A, sd_A = X_A.mean(0), X_A.std(0) + 1e-9
    mu_B, sd_B = X_B.mean(0), X_B.std(0) + 1e-9
    X_A_n = (X_A - mu_A) / sd_A
    X_B_n = (X_B - mu_B) / sd_B

    tr, te = _train_test_split_idx(len(df), test_size, seed)
    X_A_tr, X_A_te = X_A_n[tr], X_A_n[te]
    X_B_tr, X_B_te = X_B_n[tr], X_B_n[te]
    y_tr, y_te = y[tr], y[te]

    model_a = WhiteBoxRidge(degree=2, alpha=1.0).fit(X_A_tr, y_tr)
    model_b = WhiteBoxRidge(degree=2, alpha=0.5).fit(X_B_tr, y_tr)

    model_a.mu = mu_A
    model_a.sd = sd_A
    model_b.mu = mu_B
    model_b.sd = sd_B

    from scipy.spatial import cKDTree
    tree = cKDTree(X_B_n)
    d32, _ = tree.query(X_B_n, k=33)
    rho_B = float(np.median(d32[:, -1]))
    model_b.local_spacing_ = rho_B

    pa = model_a.predict(X_A_te)
    pb = model_b.predict(X_B_te)
    meta = {
        'dataset_csv': dataset_csv, 'label_col': label_col, 'pipeline': pipeline_tag,
        'gain_mode': gain_mode,
        'n_rows': int(len(df)), 'n_train': int(len(tr)), 'n_test': int(len(te)),
        'model_a_features': A_COLS, 'model_b_features': B_COLS,
        'model_a_dim': int(len(A_COLS)), 'model_b_dim': int(len(B_COLS)),
        'model_a': {
            'r2_test': _r2_score(y_te, pa), 'mse_test': _mse(y_te, pa),
            'spearman_test': _spearman(y_te, pa),
            'input_domain': 'waveform_probe',
            'description': '7-tap Tx FIR + drive_rms -> log10 BER 条件均值（方向映射）',
        },
        'model_b': {
            'r2_test': _r2_score(y_te, pb), 'mse_test': _mse(y_te, pb),
            'spearman_test': _spearman(y_te, pb),
            'input_domain': 'parameter',
            'description': '7 维参数域（4 FFE 旁瓣 + gDC + gDC2 + drive_rms）-> log10 BER 保守上包络（风险控制）',
            'local_spacing_rho': rho_B,
        },
    }
    if envs is not None:
        env_te = envs[te]
        for tag, pred in [('model_a', pa), ('model_b', pb)]:
            by_env = {}
            for e in np.unique(env_te):
                m = env_te == e
                if m.sum() >= 5:
                    by_env[str(e)] = {'n': int(m.sum()),
                                      'spearman_test': _spearman(y_te[m], pred[m])}
            meta[f'{tag}_by_env'] = by_env

    if verbose:
        print(f"Model A (探针 8 维 -> logBER): n={len(df)} | R2={meta['model_a']['r2_test']:.3f} "
              f"| Spearman={meta['model_a']['spearman_test']:.3f}")
        print(f"Model B (参数 7 维 -> logBER): n={len(df)} | R2={meta['model_b']['r2_test']:.3f} "
              f"| Spearman={meta['model_b']['spearman_test']:.3f} | rho={rho_B:.3f}")

    if not os.path.exists(model_dir):
        os.makedirs(model_dir)
    WhiteBoxRidge.__module__ = 'train_surrogates'
    with open(os.path.join(model_dir, 'model_a.pkl'), 'wb') as f:
        pickle.dump(model_a, f)
    with open(os.path.join(model_dir, 'model_b.pkl'), 'wb') as f:
        pickle.dump(model_b, f)
    with open(os.path.join(model_dir, 'meta.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False, default=float)
    return model_a, model_b, meta


def load_models(model_dir="models", verbose=False):
    """加载双代理模型（model_a.pkl / model_b.pkl），兼容历史 __main__ pickle。"""
    import sys
    a_path = os.path.join(model_dir, 'model_a.pkl')
    b_path = os.path.join(model_dir, 'model_b.pkl')
    if not (os.path.exists(a_path) and os.path.exists(b_path)):
        raise FileNotFoundError(f"models missing in {model_dir}")

    def _load(p):
        try:
            with open(p, 'rb') as f:
                return pickle.load(f)
        except AttributeError:
            sys.modules['__main__'].__dict__['WhiteBoxRidge'] = WhiteBoxRidge
            with open(p, 'rb') as f:
                return pickle.load(f)
    return _load(a_path), _load(b_path)