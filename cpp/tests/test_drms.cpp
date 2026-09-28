// test_drms.cpp — 对固定 x 的 drive_rms / FIR，与 drms_debug.py 比对。
#include "../src/physim.hpp"
#include "../src/probe.hpp"
#include "../src/optimizer.hpp"
#include <cstdio>
using namespace dsh;

int main() {
    Config cfg; cfg.load("cpp/config.txt");
    std::string s4p_path = cfg.s("channel.s4p_file", "");
    S4P nw; load_s4p(s4p_path, nw);

    std::vector<double> X = { -2.723665325067e-02, -2.922779653869e-01, -1.702005654973e-03, 5.501915279735e-02,
                              5.859391616050e+00, 1.734991920193e+00, -3.000000000000e-02 };
    apply_x_to_config(cfg, X[4], X[5], DRIVER_GAIN_NOMINAL * std::pow(10.0, X[6]));

    auto taps = construct_taps({ X[0], X[1], X[2], X[3] });
    printf("taps       [");
    for (size_t i = 0; i < taps.size(); i++) printf("%s%.15e", i ? ", " : "", taps[i]);
    printf("]\n");
    printf("gain       %.15e\n", DRIVER_GAIN_NOMINAL * std::pow(10.0, X[6]));

    auto fir_v = extract_tx_s21(cfg, &nw, taps, 7);
    auto [fir_norm, drms] = extract_tx_features(cfg, &nw, taps, 7);
    printf("fir_v      [");
    for (size_t i = 0; i < fir_v.size(); i++) printf("%s%.15e", i ? ", " : "", fir_v[i]);
    printf("]\n");
    printf("fir_norm   [");
    for (size_t i = 0; i < fir_norm.size(); i++) printf("%s%.15e", i ? ", " : "", fir_norm[i]);
    printf("]\n");
    printf("drive_rms  %.15e\n", drms);
    return 0;
}