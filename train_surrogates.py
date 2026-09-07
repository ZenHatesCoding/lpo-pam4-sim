import numpy as np
import os
import pickle

# ============================================================
# DDPS 双代理模型训练 —— 100% 白盒（纯 Numpy，面向芯片实现）
#
#   Model A (物理代理): 发端 7-tap 等效 FIR (tx_fir) -> log10(MLSE BER)
#   Model B (安全代理): FFE 9-tap + CTLE 配置          -> log10(MLSE BER)
#
# 不依赖任何第三方现成算法（无 sklearn）。Ridge 用闭式解
#   W = (X^T X + alpha I)^{-1} X^T y  手写；
# 二阶多项式特征、train/test 划分、R^2/MSE 均手写。
# ============================================================

FIR_COLS = [f'tx_fir_{i}' for i in range(7)]
CONFIG_COLS = [f'ffe_tap_{i}' for i in range(9)] + ['ctle_dc', 'ctle_dc2']


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
    """白盒 Ridge 回归：二阶多项式特征 + L2 正则闭式解。"""

    def __init__(self, degree=2, alpha=1.0):
        self.degree = degree
        self.alpha = alpha
        self.W = None

    def fit(self, X, y):
        Xp = _poly_features(X, self.degree)
        self.W = _ridge_fit(Xp, y, self.alpha)
        return self

    def predict(self, X):
        Xp = _poly_features(X, self.degree)
        return Xp @ self.W


# ---------- 白盒高斯过程回归 (GPR, RBF 核) ----------
class WhiteBoxGPR:
    """白盒 GPR：RBF 核 + 噪声的闭式后验。predict 返回 (均值, 标准差)。

    用于对比 Ridge：GPR 自带不确定性 sigma，可构造 UCB = mu + kappa*sigma
    作为“安全/防外推”的寻优目标（与信任域互补）。
    """

    def __init__(self, length_scale=0.5, sigma_f=1.0, noise_var=1e-3):
        self.length_scale = length_scale
        self.sigma_f = sigma_f
        self.noise_var = noise_var
        self.X_train = None
        self.y_train = None
        self.K_inv = None

    def _rbf(self, X1, X2):
        X1s = X1 / self.length_scale
        X2s = X2 / self.length_scale
        sq = (X1s ** 2).sum(1, keepdims=True) + (X2s ** 2).sum(1) - 2.0 * (X1s @ X2s.T)
        return self.sigma_f ** 2 * np.exp(-0.5 * sq)

    def fit(self, X, y):
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float)
        self.X_train = X
        self.y_train = y
        K = self._rbf(X, X) + self.noise_var * np.eye(len(X))
        self.K_inv = np.linalg.inv(K)
        return self

    def predict(self, X, return_std=True):
        X = np.atleast_2d(np.asarray(X, dtype=float))
        Ks = self._rbf(X, self.X_train)
        mu = Ks @ self.K_inv @ self.y_train
        var = self.sigma_f ** 2 - np.sum((Ks @ self.K_inv) * Ks, axis=1)
        var = np.clip(var, 1e-9, None)
        if return_std:
            return mu, np.sqrt(var)
        return mu

    def predict_with_std(self, X):
        return self.predict(X, return_std=True)


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


def train_from_df(df, output_dir="models", verbose=True):
    """由内存中的 DataFrame 训练并保存两个白盒 Ridge 代理。返回 (model_a, model_b)。"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    df_valid = df[df['log10_ber'] < -0.1].copy()

    X_A = df_valid[FIR_COLS].values.astype(float)
    X_B = df_valid[CONFIG_COLS].values.astype(float)
    y = df_valid['log10_ber'].values.astype(float)

    train_idx, test_idx = _train_test_split_idx(len(df_valid), 0.2, seed=42)
    X_A_train, X_A_test = X_A[train_idx], X_A[test_idx]
    X_B_train, X_B_test = X_B[train_idx], X_B[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]

    model_a = WhiteBoxRidge(degree=2, alpha=1.0).fit(X_A_train, y_train)
    model_b = WhiteBoxRidge(degree=2, alpha=1.0).fit(X_B_train, y_train)

    if verbose:
        pa = model_a.predict(X_A_test)
        pb = model_b.predict(X_B_test)
        print(f"Model A (S21 -> BER): n={len(df_valid)} | Test R2={_r2_score(y_test, pa):.3f} "
              f"MSE={_mse(y_test, pa):.3f}")
        print(f"Model B (Config -> BER): n={len(df_valid)} | Test R2={_r2_score(y_test, pb):.3f} "
              f"MSE={_mse(y_test, pb):.3f}")

    model_a_path = os.path.join(output_dir, 'model_a_s21.pkl')
    model_b_path = os.path.join(output_dir, 'model_b_config.pkl')
    with open(model_a_path, 'wb') as f:
        pickle.dump(model_a, f)
    with open(model_b_path, 'wb') as f:
        pickle.dump(model_b, f)

    return model_a, model_b


def train_models(dataset_path, output_dir="models", verbose=True):
    import pandas as pd
    df = pd.read_csv(dataset_path)
    return train_from_df(df, output_dir=output_dir, verbose=verbose)


if __name__ == "__main__":
    import argparse
    import glob

    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', type=str, default=None, help='Path to dataset CSV')
    parser.add_argument('--out_dir', type=str, default='models', help='Output directory for trained models')
    args = parser.parse_args()

    dataset_file = args.dataset
    if dataset_file is None:
        files = glob.glob('dataset/ddps_dataset_*.csv')
        if not files:
            print("No dataset found in dataset/. Run dataset_generator.py first.")
            exit(1)
        dataset_file = max(files, key=os.path.getctime)
        print(f"Auto-selected latest dataset: {dataset_file}")

    train_models(dataset_file, output_dir=args.out_dir)


# ============================================================================
# DDPS v2 训练/加载接口（稳健 pickle + 排序类评估指标）
# ============================================================================
import json

V2_CONFIG_COLS = [f'ffe_tap_{i}' for i in range(9)] + ['ctle_dc', 'ctle_dc2']


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


def train_v2(dataset_csv, model_dir="models", label_col=None, verbose=True,
             test_size=0.2, seed=42):
    """DDPS v2：白盒 Ridge 双代理训练（Model A: Tx-FIR->BER；Model B: 配置->BER）。

    相对 v1：
      - 标签列用 log10_ber_mlse（明确 MLSE 口径）；
      - 附加 Spearman 排序类指标（寻优只依赖排序/方向，比绝对 R² 更贴任务）；
      - 模型以模块路径安全 pickle，并输出 meta.json 供结果可审计。
    返回 (model_a, model_b, meta)。
    """
    import pandas as pd
    if label_col is None:
        label_col = _col(pd.read_csv(dataset_csv, nrows=1), 'log10_ber_mlse', 'log10_ber')
    df = pd.read_csv(dataset_csv)
    df = df[df[label_col] < -0.1].reset_index(drop=True)   # 剔除锁死样本(BER>0.79)

    X_A = df[FIR_COLS].values.astype(float)
    X_B = df[V2_CONFIG_COLS].values.astype(float)
    y = df[label_col].values.astype(float)
    envs = df['env'].values if 'env' in df.columns else None

    tr, te = _train_test_split_idx(len(df), test_size, seed)
    X_A_tr, X_A_te = X_A[tr], X_A[te]
    X_B_tr, X_B_te = X_B[tr], X_B[te]
    y_tr, y_te = y[tr], y[te]

    model_a = WhiteBoxRidge(degree=2, alpha=1.0).fit(X_A_tr, y_tr)
    model_b = WhiteBoxRidge(degree=2, alpha=1.0).fit(X_B_tr, y_tr)

    pa = model_a.predict(X_A_te)
    pb = model_b.predict(X_B_te)
    meta = {
        'dataset_csv': dataset_csv, 'label_col': label_col,
        'n_train': int(len(tr)), 'n_test': int(len(te)),
        'model_a': {
            'r2_test': _r2_score(y_te, pa), 'mse_test': _mse(y_te, pa),
            'spearman_test': _spearman(y_te, pa),
        },
        'model_b': {
            'r2_test': _r2_score(y_te, pb), 'mse_test': _mse(y_te, pb),
            'spearman_test': _spearman(y_te, pb),
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
        print(f"Model A (TxFIR->logBER_MLSE): n={len(df)} | R2={meta['model_a']['r2_test']:.3f} "
              f"| Spearman={meta['model_a']['spearman_test']:.3f}")
        print(f"Model B (Config->logBER_MLSE): n={len(df)} | R2={meta['model_b']['r2_test']:.3f} "
              f"| Spearman={meta['model_b']['spearman_test']:.3f}")

    if not os.path.exists(model_dir):
        os.makedirs(model_dir)
    # 确保 pickle 引用的是模块路径而非 __main__（v1 曾因此无法跨脚本加载）
    WhiteBoxRidge.__module__ = 'train_surrogates'
    WhiteBoxGPR.__module__ = 'train_surrogates'
    with open(os.path.join(model_dir, 'model_a.pkl'), 'wb') as f:
        pickle.dump(model_a, f)
    with open(os.path.join(model_dir, 'model_b.pkl'), 'wb') as f:
        pickle.dump(model_b, f)
    with open(os.path.join(model_dir, 'meta.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False, default=float)
    return model_a, model_b, meta


def load_models(model_dir="models", verbose=False):
    """加载 DDPS v2 模型。向后兼容 v1 的 __main__ pickle 陷阱。"""
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
            sys.modules['__main__'].WhiteBoxRidge = WhiteBoxRidge
            sys.modules['__main__'].WhiteBoxGPR = WhiteBoxGPR
            with open(p, 'rb') as f:
                return pickle.load(f)
    return _load(a_path), _load(b_path)
