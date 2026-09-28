// filter.hpp — 巴特沃斯低通（双线性）设计与 lfilter（直接 II 型转置），
// 复刻 scipy.signal.butter(N, Wn, 'low') + scipy.signal.lfilter 的数值口径。
#pragma once

#include <vector>
#include <complex>
#include <cmath>
#include <algorithm>

#include "fft.hpp"

namespace dsh {

// butter_lowpass(order, wn)：wn = 截止频率 / 奈奎斯特频率（0..1）。
// 返回 (b, a)（长度 order+1，a[0]=1）。复刻 scipy 链：buttap -> lp2lp(预畸变) -> 双线性 -> zpk2tf。
inline void butter_lowpass(int N, double wn, std::vector<double>& b, std::vector<double>& a) {
    const double fs2 = 4.0;                       // scipy 数字域 fs=2 -> fs2=4
    const double warped = fs2 * std::tan(DSH_PI * wn / 2.0);   // 预畸变截止 Ω

    // 模拟 Butterworth 极点（左半平面，单位圆），θ_k = π/2 + π(2k+1)/(2N)
    std::vector<std::complex<double>> p(N);
    for (int k = 0; k < N; k++) {
        double th = DSH_PI * (0.5 + (double)(2 * k + 1) / (2.0 * N));
        p[k] = std::complex<double>(std::cos(th), std::sin(th)) * warped;
    }
    // 双线性：p_z = (fs2 + p)/(fs2 - p)；增益 k_z = Ω^N / ∏(fs2 - p)
    std::complex<double> kz = 1.0;
    std::vector<std::complex<double>> pz(N);
    for (int k = 0; k < N; k++) {
        kz *= (fs2 - p[k]);
        pz[k] = (fs2 + p[k]) / (fs2 - p[k]);
    }
    kz = std::complex<double>(std::pow(warped, (double)N), 0.0) / kz;

    // 分子 b = k_z * (z+1)^N（N 个零点全在 -1）
    b.assign(N + 1, 0.0);
    std::vector<double> binom(N + 1, 1.0);
    for (int i = 1; i <= N; i++) binom[i] = binom[i - 1] * (N - i + 1) / i;  // C(N,i)
    double kb = kz.real();
    for (int i = 0; i <= N; i++) b[i] = kb * binom[i];

    // 分母 a = ∏(z - pz_k)，展开为实系数多项式（共轭极点成对）
    std::vector<std::complex<double>> apoly(1, std::complex<double>(1.0, 0.0));
    int k = 0;
    while (k < N) {
        // 极点已按 θ 升序排列，pz[k] 与 pz[N-1-k] 共轭；成对乘二次因子
        std::complex<double> pa = pz[k];
        std::complex<double> pb = pz[N - 1 - k];
        // (z-pa)(z-pb) = z^2 - (pa+pb) z + (pa*pb)
        std::vector<std::complex<double>> q(3);
        q[0] = std::complex<double>(1.0, 0.0);
        q[1] = -(pa + pb);
        q[2] = pa * pb;
        std::vector<std::complex<double>> tp(apoly.size() + 2, std::complex<double>(0.0, 0.0));
        for (size_t i = 0; i < apoly.size(); i++) {
            for (int j = 0; j < 3; j++) {
                tp[i + j] += apoly[i] * q[j];
            }
        }
        apoly = tp;
        k += 2;
    }
    a.assign(N + 1, 0.0);
    for (int i = 0; i <= N; i++) a[i] = apoly[i].real();   // 应为实（共轭成对，取实部去残留虚部）
}

// lfilter：直接 II 型转置（与 scipy.signal.lfilter 相同的递推）。
inline std::vector<double> lfilter(const std::vector<double>& b, const std::vector<double>& a,
                                   const std::vector<double>& x) {
    int M = (int)std::max(b.size(), a.size());
    int n = (int)x.size();
    std::vector<double> y(n, 0.0);
    std::vector<double> d(M, 0.0);      // 状态长度 M（与 scipy 一致：d 长 M-1 用于反馈）

    // scipy 直接 II 型转置：d 长度 = max(len(b),len(a))-1
    int nstate = M - 1;
    std::vector<double> st(nstate, 0.0);
    std::vector<double> bb(M, 0.0), aa(M, 0.0);
    for (size_t i = 0; i < b.size(); i++) bb[i] = b[i];
    for (size_t i = 0; i < a.size(); i++) aa[i] = a[i];

    for (int k = 0; k < n; k++) {
        double yk = bb[0] * x[k] + st[0];
        for (int i = 0; i < nstate - 1; i++) {
            st[i] = bb[i + 1] * x[k] + st[i + 1] - aa[i + 1] * yk;
        }
        st[nstate - 1] = bb[nstate] * x[k] - aa[nstate] * yk;
        y[k] = yk;
    }
    return y;
}

// lowpass_filter（channel_imdd.py）：Butterworth 低通；cutoff>=nyq 时原样返回。
inline std::vector<double> lowpass_filter(const std::vector<double>& x, double bw, double fs, int order = 4) {
    double nyq = 0.5 * fs;
    double wn = bw / nyq;
    if (wn >= 1.0) return x;
    std::vector<double> b, a;
    butter_lowpass(order, wn, b, a);
    return lfilter(b, a, x);
}

} // namespace dsh