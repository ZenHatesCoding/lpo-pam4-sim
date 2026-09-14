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
            for _cls in (WhiteBoxRidge, WhiteBoxGPR, WhiteBoxKernelRidge, WhiteBoxEnvelope):
                sys.modules['__main__'].__dict__[_cls.__name__] = _cls
            with open(p, 'rb') as f:
                return pickle.load(f)
    return _load(a_path), _load(b_path)


# ============================================================================
# DDPS v3 训练接口
#
#   Model A 输入 = [7-tap Tx FIR 形状, MZM 驱动 RMS]        -> 8 维，D = 45
#       * drive_rms 是必需的：driver_gain 在纯线性 Tx 链里只是标量乘子，FIR 形状对整体
#         尺度不变；把"实际驱动幅度"显式喂给 Model A，它才能对 driver_gain 产生非零梯度。
#   Model B 输入 = [9 个 FFE 抽头, gDC, gDC2, driver_gain]  -> 12 维，D = 91
# ============================================================================
# v4: Model A 输入 = **绝对标定的** 7-tap FIR（含 FFE 形状 / CTLE 频响 / driver_gain 幅度）
V3_A_COLS = [f'tx_fir_{i}' for i in range(7)]
V3_CONFIG_COLS = [f'ffe_tap_{i}' for i in range(9)] + ['ctle_dc', 'ctle_dc2', 'driver_gain']


def train_v3(dataset_csv, model_dir="models", label_col=None, verbose=True,
             test_size=0.2, seed=42):
    """DDPS v3：白盒 Ridge 双代理训练（11 维搜索空间的代理模型）。

    与 train_v2 的区别：
      - Model A 特征 = 7-tap FIR 形状 + MZM 驱动 RMS（8 维）；
      - Model B 特征 = 9 抽头 + gDC + gDC2 + driver_gain（12 维）；
      - meta.json 额外记录特征维度，便于审计与复算。
    返回 (model_a, model_b, meta)。
    """
    import pandas as pd
    if label_col is None:
        label_col = _col(pd.read_csv(dataset_csv, nrows=1), 'log10_ber_mlse', 'log10_ber')
    df = pd.read_csv(dataset_csv)
    df = df[df[label_col] < -0.1].reset_index(drop=True)   # 剔除锁死样本(BER>0.79)

    X_A = df[V3_A_COLS].values.astype(float)
    X_B = df[V3_CONFIG_COLS].values.astype(float)
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
        'dataset_csv': dataset_csv, 'label_col': label_col, 'pipeline': 'ddps_v3',
        'n_rows': int(len(df)), 'n_train': int(len(tr)), 'n_test': int(len(te)),
        'model_a_features': V3_A_COLS, 'model_b_features': V3_CONFIG_COLS,
        'model_a_dim': int(len(V3_A_COLS)), 'model_b_dim': int(len(V3_CONFIG_COLS)),
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
        print(f"Model A (FIR+drive -> logBER): n={len(df)} | R2={meta['model_a']['r2_test']:.3f} "
              f"| Spearman={meta['model_a']['spearman_test']:.3f}")
        print(f"Model B (config -> logBER):    n={len(df)} | R2={meta['model_b']['r2_test']:.3f} "
              f"| Spearman={meta['model_b']['spearman_test']:.3f}")

    if not os.path.exists(model_dir):
        os.makedirs(model_dir)
    WhiteBoxRidge.__module__ = 'train_surrogates'
    WhiteBoxGPR.__module__ = 'train_surrogates'
    with open(os.path.join(model_dir, 'model_a.pkl'), 'wb') as f:
        pickle.dump(model_a, f)
    with open(os.path.join(model_dir, 'model_b.pkl'), 'wb') as f:
        pickle.dump(model_b, f)
    with open(os.path.join(model_dir, 'meta.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False, default=float)
    return model_a, model_b, meta


# ============================================================================
# DDPS v4 双代理：A/B 共用**搜索向量 x**（11 维）作为输入，训练目标不同
#
#   x = [8 个 FFE 旁瓣(绝对抽头值), gDC(dB), gDC2(dB), u_gain = log10(g/g0)]
#
#   Model A（方向模型）：x -> log10 BER 的**条件均值**。要"准"：平滑、可解析求导，
#       梯度直接落在三组自由度上（FFE / CTLE / driver_gain），量纲可比。
#   Model B（拦截模型）：x -> log10 BER 的**保守上包络**。要"保守"：宁可误拦不可放过。
#       实现为 A(x) + c·S(x)，S 是残差尺度（|残差| 的核岭回归），c 标定到目标覆盖率。
#
# 为什么输入不再是 Tx 端波形探针：探针是**线性冲激响应**，而真实链路在整形级之前还有
# DAC ENOB 量化（config: dac_enob=5.5）这类幅度相关非线性，探针与真实链路并不严格等价；
# 同时"绝对 FIR"到"11 维配置"存在多对一压缩。实测同一份数据上，二阶多项式基对 7 抽头
# 特征的 R² 仅 0.29，而 11 维配置 / 核方法可到 0.62 —— 用配置空间既省参数又让三组
# 自由度的梯度同量纲可比（旧版"增益维梯度几乎为 0"的根因之一）。
# ============================================================================
V4_X_COLS = [f'x_{i}' for i in range(7)]        # 4 个 5-tap FFE 旁瓣 + gDC + gDC2 + u_gain


class WhiteBoxKernelRidge:
    """白盒 RBF 核岭回归（闭式解，纯 Numpy，面向芯片实现）。

        f(x) = y_mean + k(x)^T (K + alpha I)^{-1} (y - y_mean)

    - 输入先按训练集均值/标准差标准化（各维同尺度，核宽才有统一含义）；
    - 核宽取"中位距离启发式" gamma = 1 / median(||z_i - z_j||²)（只看数据，不看标签）；
    - alpha 由训练集内 5 折 CV 选取；
    - 提供**解析梯度** grad()，Stage 2 投影梯度下降直接使用，无需有限差分。

    这仍是白盒：全部参数（训练点、系数、带宽、正则）都是显式可审计的闭式量，
    没有黑盒迭代训练；推理 = 训练点上的核加权求和。
    """

    def __init__(self, gamma=None, alpha=0.1):
        self.gamma = gamma
        self.alpha = alpha

    def fit(self, X, y):
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float)
        self.mu = X.mean(axis=0)
        self.sd = X.std(axis=0) + 1e-12
        self.Z = (X - self.mu) / self.sd
        d2 = ((self.Z[:, None, :] - self.Z[None, :, :]) ** 2).sum(-1)
        if self.gamma is None:
            pos = d2[d2 > 0]
            self.gamma = 1.0 / float(np.median(pos)) if pos.size else 1.0
        self.ymu = float(y.mean())
        K = np.exp(-self.gamma * d2)
        self.coef_ = np.linalg.solve(K + self.alpha * np.eye(len(self.Z)), y - self.ymu)
        self.n_train_ = len(self.Z)
        return self

    def _kernel(self, X):
        Zq = (np.asarray(X, dtype=float) - self.mu) / self.sd
        d2 = ((Zq[:, None, :] - self.Z[None, :, :]) ** 2).sum(-1)
        return np.exp(-self.gamma * d2), Zq

    def predict(self, X):
        K, _ = self._kernel(X)
        return K @ self.coef_ + self.ymu

    def grad(self, X):
        """d f / d x（解析），返回 (n, 11)。"""
        K, Zq = self._kernel(X)
        n, d = Zq.shape
        G = np.zeros((n, d))
        for j in range(d):
            # dK_ij/dx_j = -2*gamma*K_ij*(z_j - z_ij)/sd_j
            G[:, j] = (K * (-2.0 * self.gamma) * (Zq[:, j:j + 1] - self.Z[None, :, j])) @ self.coef_ / self.sd[j]
        return G


class WhiteBoxEnvelope:
    """保守上包络回归（Model B）：B(x) = A(x) + c · S(x)。

    S 为"残差尺度"回归（对 |y - A(x)| 做同样的核岭回归），c 由标定覆盖率确定。
    语义：B 估计"在该配置下 log10 BER 可能坏到什么程度"，因此按百分比拦截时是保守的。
    """

    def __init__(self, mean_model, scale_model, c=1.0):
        self.mean_model = mean_model
        self.scale_model = scale_model
        self.c = float(c)

    def predict(self, X):
        return self.mean_model.predict(X) + self.c * self.scale_model.predict(X)

    def grad(self, X):
        return self.mean_model.grad(X) + self.c * self.scale_model.grad(X)


def _kernel_gamma_grid(X, n_sub=500, seed=0):
    """核宽候选网格：以"中位距离启发式"为中心，上下各取 4x。

    gamma = 1 / median(||z_i - z_j||²)（只依赖输入分布，不看标签）；
    中位数用至多 n_sub 个点的子样估计，避免 n² 距离矩阵过大。
    """
    Zs = (X - X.mean(0)) / (X.std(0) + 1e-12)
    rs = np.random.RandomState(seed)
    sub = Zs if len(Zs) <= n_sub else Zs[rs.choice(len(Zs), n_sub, replace=False)]
    d2 = ((sub[:, None, :] - sub[None, :, :]) ** 2).sum(-1)
    pos = d2[d2 > 0]
    g_med = 1.0 / float(np.median(pos)) if pos.size else 1.0
    return [g_med * 4.0, g_med, g_med / 4.0, g_med / 16.0]


def _cv_kernel_alpha(X, y, gammas, alphas, folds=5, seed=0):
    """训练集内 5 折 CV 选 (gamma, alpha)：返回 (gamma, alpha, cv_mse)。"""
    rs = np.random.RandomState(seed)
    perm = rs.permutation(len(X))
    parts = np.array_split(perm, folds)
    best = (gammas[0], alphas[0], np.inf)
    for g in gammas:
        for a in alphas:
            errs = []
            for k in range(folds):
                m = np.zeros(len(X), dtype=bool)
                m[parts[k]] = True
                mdl = WhiteBoxKernelRidge(gamma=g, alpha=a).fit(X[~m], y[~m])
                errs.append(float(np.mean((mdl.predict(X[m]) - y[m]) ** 2)))
            e = float(np.mean(errs))
            if e < best[2]:
                best = (g, a, e)
    return best


def _local_spacing(Z, k=32, sub=900, seed=1):
    """标准化空间里“第 k 近邻距离”的中位数 —— 数据自身的局部颗粒度 ρ。

    用途：Stage-2 用它做**轨迹信任域**——模型只在走过约一个数据格的范围内可信，
    再往外它给出的“还能继续降”没有数据支撑（诊断见 result/ddps_v4_divergence.csv）。
    """
    rs = np.random.RandomState(seed)
    idxs = rs.choice(len(Z), min(sub, len(Z)), replace=False)
    d = np.sqrt(((Z[idxs][:, None, :] - Z[None, :, :]) ** 2).sum(-1))
    d.sort(axis=1)
    kk = min(k, d.shape[1] - 1)
    return float(np.median(d[:, kk]))


def train_v4(dataset_csv, model_dir="models", label_col=None, verbose=True,
             test_size=0.2, seed=42, env_filter="Base_IL10x10"):
    """DDPS v4：训练 A（方向，核岭均值）/ B（拦截，均值 + 残差尺度包络）。

    只使用**基线环境**的样本（与"只用基线训练、向其它场景泛化"的实验口径一致）。
    """
    import pandas as pd
    import json as _json
    if label_col is None:
        label_col = _col(pd.read_csv(dataset_csv, nrows=1), 'log10_ber_mlse', 'log10_ber')
    df = pd.read_csv(dataset_csv)
    df = df[df[label_col] < -0.1].reset_index(drop=True)   # 剔除锁死样本(BER>0.79)
    if env_filter and 'env' in df.columns:
        df = df[df['env'] == env_filter].reset_index(drop=True)

    xcols = sorted([c for c in df.columns if c.startswith('x_')],
                   key=lambda c: int(c.split('_')[1]))
    X = df[xcols].values.astype(float)
    y = df[label_col].values.astype(float)
    tr, te = _train_test_split_idx(len(df), test_size, seed)

    gammas = _kernel_gamma_grid(X)
    alphas = [0.01, 0.03, 0.1, 0.3, 1.0]
    g_best, a_best, cv = _cv_kernel_alpha(X[tr], y[tr], gammas, alphas)

    model_a = WhiteBoxKernelRidge(gamma=g_best, alpha=a_best).fit(X[tr], y[tr])
    rho = _local_spacing((X[tr] - model_a.mu) / model_a.sd)
    resid = np.abs(y[tr] - model_a.predict(X[tr]))
    model_s = WhiteBoxKernelRidge(gamma=g_best, alpha=max(a_best, 0.1)).fit(X[tr], resid)
    # 覆盖率标定：在测试集上取满足 >=85% 覆盖的最小 c
    c_cal, cov_cal = 1.0, 0.0
    for c in (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0):
        cov = float(np.mean(y[te] <= model_a.predict(X[te]) + c * model_s.predict(X[te])))
        if cov >= 0.85:
            c_cal, cov_cal = c, cov
            break
        c_cal, cov_cal = c, cov
    model_b = WhiteBoxEnvelope(model_a, model_s, c_cal)
    model_a.local_spacing_ = rho
    model_b.local_spacing_ = rho

    pa = model_a.predict(X[te])
    pb = model_b.predict(X[te])
    meta = {
        'dataset_csv': dataset_csv, 'label_col': label_col, 'pipeline': 'ddps_v4',
        'n_rows': int(len(df)), 'n_train': int(len(tr)), 'n_test': int(len(te)),
        'env_filter': env_filter,
        'model_a_features': xcols, 'model_b_features': xcols,
        'model_a_dim': len(xcols), 'model_b_dim': len(xcols),
        'model_a_type': 'WhiteBoxKernelRidge(RBF, closed form)',
        'model_b_type': 'WhiteBoxEnvelope(mean + c*residual-scale ridge)',
        'gamma': float(model_a.gamma), 'alpha': float(model_a.alpha),
        'cv_mse': float(cv), 'envelope_c': float(c_cal), 'envelope_coverage_test': float(cov_cal),
        'local_spacing_sigma': float(rho),
        'model_a': {
            'r2_test': _r2_score(y[te], pa), 'mse_test': _mse(y[te], pa),
            'spearman_test': _spearman(y[te], pa), 'pred_std_test': float(np.std(pa)),
        },
        'model_b': {
            'r2_test': _r2_score(y[te], pb), 'mse_test': _mse(y[te], pb),
            'spearman_test': _spearman(y[te], pb), 'pred_std_test': float(np.std(pb)),
            'coverage_test': float(np.mean(y[te] <= pb)),
        },
    }
    if verbose:
        print(f"Model A (x -> mean logBER):  R2={meta['model_a']['r2_test']:.3f} "
              f"Spearman={meta['model_a']['spearman_test']:.3f} "
              f"(gamma={model_a.gamma:.4f}, alpha={model_a.alpha:g}, CV-MSE={cv:.4f})")
        print(f"Model B (x -> upper envelope): R2={meta['model_b']['r2_test']:.3f} "
              f"Spearman={meta['model_b']['spearman_test']:.3f} "
              f"(c={c_cal:g}, coverage={meta['model_b']['coverage_test']:.2f})")

    if not os.path.exists(model_dir):
        os.makedirs(model_dir)
    WhiteBoxKernelRidge.__module__ = 'train_surrogates'
    WhiteBoxEnvelope.__module__ = 'train_surrogates'
    WhiteBoxRidge.__module__ = 'train_surrogates'
    WhiteBoxGPR.__module__ = 'train_surrogates'
    with open(os.path.join(model_dir, 'model_a.pkl'), 'wb') as f:
        pickle.dump(model_a, f)
    with open(os.path.join(model_dir, 'model_b.pkl'), 'wb') as f:
        pickle.dump(model_b, f)
    with open(os.path.join(model_dir, 'meta.json'), 'w', encoding='utf-8') as f:
        _json.dump(meta, f, indent=2, ensure_ascii=False, default=float)
    return model_a, model_b, meta
