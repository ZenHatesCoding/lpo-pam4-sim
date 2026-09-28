// test_dft.cpp — 非 2 幂 rfft/irfft 与 numpy 比对。
#include "../src/fft.hpp"
#include <cstdio>
#include <fstream>
using namespace dsh;

int main(int argc, char** argv) {
    int N = (argc > 1) ? std::atoi(argv[1]) : 1608;
    // 读输入（float64 二进制）
    std::vector<double> x(N);
    std::ifstream f("cpp/build/dft_in.bin", std::ios::binary);
    f.read((char*)x.data(), sizeof(double) * N);

    auto X = rfft(x);
    auto y = irfft(X, N);

    // 输出 X（实部+虚部）与 y
    std::ofstream fo("cpp/build/dft_out.bin", std::ios::binary);
    for (auto c : X) { double re = c.real(), im = c.imag(); fo.write((char*)&re, 8); fo.write((char*)&im, 8); }
    std::ofstream fy("cpp/build/dft_y.bin", std::ios::binary);
    fy.write((char*)y.data(), sizeof(double) * N);
    printf("done N=%d\n", N);
    return 0;
}