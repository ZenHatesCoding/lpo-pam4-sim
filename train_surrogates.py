import pandas as pd
import numpy as np
import os
import pickle
from sklearn.linear_model import Ridge
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

# ============================================================
# DDPS 双代理模型训练
#   Model A (物理代理): 发端 7-tap 等效 FIR (tx_fir) -> log10(MLSE BER)
#   Model B (安全代理): FFE 9-tap + CTLE DC 配置          -> log10(MLSE BER)
# 两者均为白盒 Ridge(二阶多项式) 回归，无黑盒。
# ============================================================

FIR_COLS = [f'tx_fir_{i}' for i in range(7)]
CONFIG_COLS = [f'ffe_tap_{i}' for i in range(9)] + ['ctle_dc']


def train_from_df(df, output_dir="models", verbose=True):
    """由内存中的 DataFrame 训练并保存两个代理模型。返回 (model_a, model_b)。"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 剔除完全死区点 (BER=1.0 -> log10_ber=0.0)，仅保留有物理意义的区间
    df_valid = df[df['log10_ber'] < -0.1].copy()

    X_A = df_valid[FIR_COLS].values
    X_B = df_valid[CONFIG_COLS].values
    y = df_valid['log10_ber'].values

    X_A_train, X_A_test, X_B_train, X_B_test, y_train, y_test = train_test_split(
        X_A, X_B, y, test_size=0.2, random_state=42
    )

    model_a = Pipeline([
        ('poly', PolynomialFeatures(degree=2, include_bias=True)),
        ('ridge', Ridge(alpha=1.0))
    ])
    model_b = Pipeline([
        ('poly', PolynomialFeatures(degree=2, include_bias=True)),
        ('ridge', Ridge(alpha=1.0))
    ])

    model_a.fit(X_A_train, y_train)
    model_b.fit(X_B_train, y_train)

    if verbose:
        y_pred_A_test = model_a.predict(X_A_test)
        y_pred_B_test = model_b.predict(X_B_test)
        print(f"Model A (S21 -> BER): n={len(df_valid)} | Test R2={r2_score(y_test, y_pred_A_test):.3f} "
              f"MSE={mean_squared_error(y_test, y_pred_A_test):.3f}")
        print(f"Model B (Config -> BER): n={len(df_valid)} | Test R2={r2_score(y_test, y_pred_B_test):.3f} "
              f"MSE={mean_squared_error(y_test, y_pred_B_test):.3f}")

    model_a_path = os.path.join(output_dir, 'model_a_s21.pkl')
    model_b_path = os.path.join(output_dir, 'model_b_config.pkl')
    with open(model_a_path, 'wb') as f:
        pickle.dump(model_a, f)
    with open(model_b_path, 'wb') as f:
        pickle.dump(model_b, f)

    return model_a, model_b


def train_models(dataset_path, output_dir="models", verbose=True):
    df = pd.read_csv(dataset_path)
    return train_from_df(df, output_dir=output_dir, verbose=verbose)


if __name__ == "__main__":
    import argparse
    import glob

    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', type=str, default=None, help='Path to dataset CSV')
    args = parser.parse_args()

    dataset_file = args.dataset
    if dataset_file is None:
        files = glob.glob('dataset/ddps_dataset_*.csv')
        if not files:
            print("No dataset found in dataset/. Run dataset_generator.py first.")
            exit(1)
        dataset_file = max(files, key=os.path.getctime)
        print(f"Auto-selected latest dataset: {dataset_file}")

    train_models(dataset_file)
