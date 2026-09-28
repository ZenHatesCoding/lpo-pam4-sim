// fft.hpp — 基数-2 复数 FFT / 实数 FFT，语义与 numpy.fft 对齐。
//
//   fft(x)   : forward, 不归一化（X[k] = Σ x[n] e^{-2πi kn/N}）
//   ifft(X)  : backward, 1/N 归一化
//   rfft(x)  : 实数 x 的 fft 前 N/2+1 个频率桶
//   irfft(X,n): 由 N/2+1 个桶重建实数信号（共轭对称 + ifft 取实部）
//
// 全部信号长度在本项目中都是 2 的幂（num_symbols × sps_channel），故只需 radix-2。
// 数值结果与 numpy.fft 在双精度下相对差 ~1e-15（pocketfft 亦为精确算法）。
#pragma once

#include <vector>
#include <complex>
#include <cmath>

namespace dsh {

static constexpr double TWO_PI = 6.283185307179586476925286766559;
static constexpr double DSH_PI = 3.141592653589793238462643383279502884;

// 就地迭代 Cooley-Tukey radix-2，inverse=true 时使用正旋（ifft 语义，含 1/n 缩放由调用方处理）。
inline void fft_inplace(std::complex<double>* a, int n, bool inverse) {
    // bit-reversal permutation
    for (int i = 1, j = 0; i < n; i++) {
        int bit = n >> 1;
        for (; j & bit; bit >>= 1) j ^= bit;
        j ^= bit;
        if (i < j) std::swap(a[i], a[j]);
    }
    for (int len = 2; len <= n; len <<= 1) {
        double ang = (inverse ? TWO_PI : -TWO_PI) / len;
        std::complex<double> wlen(std::cos(ang), std::sin(ang));
        for (int i = 0; i < n; i += len) {
            std::complex<double> w(1.0, 0.0);
            for (int k = 0; k < len / 2; k++) {
                std::complex<double> u = a[i + k];
                std::complex<double> v = a[i + k + len / 2] * w;
                a[i + k] = u + v;
                a[i + k + len / 2] = u - v;
                w *= wlen;
            }
        }
    }
}

inline void fft(const std::complex<double>* in, std::complex<double>* out, int n) {
    for (int i = 0; i < n; i++) out[i] = in[i];
    fft_inplace(out, n, false);
}

inline void fft(const std::vector<std::complex<double>>& in, std::vector<std::complex<double>>& out) {
    int n = (int)in.size();
    out.resize(n);
    fft(in.data(), out.data(), n);
}

inline void ifft(const std::complex<double>* in, std::complex<double>* out, int n) {
    for (int i = 0; i < n; i++) out[i] = std::conj(in[i]);
    fft_inplace(out, n, false);          // fft(conj(X))
    for (int i = 0; i < n; i++) out[i] = std::conj(out[i]) / (double)n;
}

inline bool is_pow2(int n) { return n > 0 && (n & (n - 1)) == 0; }

// 通用 DFT（naive O(N²)）：X[k] = Σ_n x[n] e^{∓2πi kn/N}，inverse=true 时 ×1/N。
// 供非 2 的幂长度使用（探针冲激 N=1608）。与 numpy pocketfft 同数学定义，
// 双精度相对差 ~1e-13（求和顺序不同），对探针/模型/寻优路径无实质影响。
inline void dft(const std::complex<double>* in, std::complex<double>* out, int n, bool inverse) {
    double sign = inverse ? TWO_PI : -TWO_PI;
    for (int k = 0; k < n; k++) {
        std::complex<double> acc(0.0, 0.0);
        for (int t = 0; t < n; t++) {
            double ang = sign * (double)k * (double)t / (double)n;
            acc += in[t] * std::complex<double>(std::cos(ang), std::sin(ang));
        }
        out[k] = inverse ? acc / (double)n : acc;
    }
}

// rfft：实数输入 -> 前 N/2+1 个复数桶（与 numpy.fft.rfft 一致，不归一化）。
inline std::vector<std::complex<double>> rfft(const std::vector<double>& x) {
    int n = (int)x.size();
    std::vector<std::complex<double>> c(n);
    for (int i = 0; i < n; i++) c[i] = std::complex<double>(x[i], 0.0);
    if (is_pow2(n)) {
        fft_inplace(c.data(), n, false);
    } else {
        std::vector<std::complex<double>> tmp(n);
        dft(c.data(), tmp.data(), n, false);
        c = tmp;
    }
    c.resize(n / 2 + 1);
    return c;
}

// irfft：N/2+1 个桶 -> 实数序列（与 numpy.fft.irfft(X, n=n) 一致）。
inline std::vector<double> irfft(const std::vector<std::complex<double>>& X, int n) {
    std::vector<std::complex<double>> full(n);
    int half = (int)X.size() - 1;        // = n/2
    for (int k = 0; k <= half; k++) full[k] = X[k];
    for (int k = half + 1; k < n; k++) full[k] = std::conj(X[n - k]);
    if (is_pow2(n)) {
        ifft(full.data(), full.data(), n);
    } else {
        std::vector<std::complex<double>> tmp(n);
        dft(full.data(), tmp.data(), n, true);
        full = tmp;
    }
    std::vector<double> out(n);
    for (int i = 0; i < n; i++) out[i] = full[i].real();
    return out;
}

} // namespace dsh