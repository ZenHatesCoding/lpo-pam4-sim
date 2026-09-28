// test_dsp.cpp — FFT / butter / lfilter 与 numpy/scipy 比对（打印参考值）。
#include "../src/rng.hpp"
#include "../src/fft.hpp"
#include "../src/filter.hpp"
#include <cstdio>
#include <vector>

int main() {
    using namespace dsh;
    // 用固定 RNG 生成测试信号（与 Python RandomState(7) 对齐）
    RkState s;
    rk_seed(s, 7u);
    std::vector<double> x(64);
    for (auto& v : x) v = rk_normal(s, 0.0, 1.0);

    // rfft 前 5 桶
    auto X = rfft(x);
    printf("rfft[0..4]:\n");
    for (int i = 0; i < 5; i++) printf("%.15g %.15g\n", X[i].real(), X[i].imag());

    // irfft(rfft) 前 3
    auto xr = irfft(X, 64);
    printf("irfft[0..2]:\n");
    for (int i = 0; i < 3; i++) printf("%.15g\n", xr[i]);

    // butter_lowpass(4, 40e9 / 224e9)
    std::vector<double> b, a;
    double wn = 40e9 / 224e9;
    butter_lowpass(4, wn, b, a);
    printf("butter b:\n");
    for (double v : b) printf("%.17g\n", v);
    printf("butter a:\n");
    for (double v : a) printf("%.17g\n", v);

    // lfilter
    std::vector<double> xs(64);
    RkState t;
    rk_seed(t, 1234u);
    for (auto& v : xs) v = rk_normal(t, 0.0, 1.0);
    auto y = lfilter(b, a, xs);
    printf("lfilter[0..4]:\n");
    for (int i = 0; i < 5; i++) printf("%.15g\n", y[i]);

    // fft/ifft 复数组
    std::vector<std::complex<double>> f(8);
    for (int i = 0; i < 8; i++) f[i] = std::complex<double>(x[i], 0.0);
    fft_inplace(f.data(), 8, false);
    printf("fft[0..2]:\n");
    for (int i = 0; i < 3; i++) printf("%.15g %.15g\n", f[i].real(), f[i].imag());
    return 0;
}