"""tests/test_burg_a1.py — Burg a1 估计合成单测。

生成已知 AR(1) 系数的有色噪声，走「判决误差 → Burg」流程，验证 Burg 能定出
白化抽头 a1；同时核对输出 E（白化后噪声方差）≈ 创新方差 σ_w²。

噪声模型 x[n] = φ·x[n-1] + w[n]（φ 为 AR(1) 系数，w ~ N(0, σ²)）。
白化滤波器 [1, a1] 满足 x[n] + a1·x[n-1] ≈ w[n]，因此 a1 = −φ。
main.py 用 pr_taps=[1, a1] 同时作白化滤波与 Viterbi 目标（同号），本测试钉死该符号约定。

用法：python tests/test_burg_a1.py
"""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import mlse_burg as M


def _ar1(rng, phi, n, sigma=1.0):
    """x[k] = phi * x[k-1] + w[k]，w ~ N(0, sigma^2)。"""
    w = rng.normal(0.0, sigma, n)
    x = np.zeros(n)
    for k in range(1, n):
        x[k] = phi * x[k - 1] + w[k]
    return x, w


def test_burg_recovers_whitening_tap():
    rng = np.random.RandomState(0)
    n = 200000
    sigma = 0.7
    for phi in (0.3, 0.6, -0.4):
        x, _ = _ar1(rng, phi, n, sigma)
        coeffs, E = M.burg_ar(x, 1)
        # a1 = 白化抽头 = −φ（反射系数 k_1 = −r(1)/r(0) = −φ）
        assert abs(coeffs[0] + phi) < 0.02, (phi, coeffs[0])
        # E = 白化后噪声方差 ≈ 创新方差 σ_w²
        assert abs(E - sigma ** 2) < 0.05, (phi, E)


if __name__ == "__main__":
    test_burg_recovers_whitening_tap()
    print("BURG a1 SYNTHETIC TEST PASSED")
