// test_probe.cpp — 探针 + Model A 预测，与 Python probe_debug.py 逐位比对。
#include "../src/physim.hpp"
#include "../src/probe.hpp"
#include "../src/surrogate.hpp"
#include <cstdio>
using namespace dsh;

int main() {
    Config cfg; cfg.load("cpp/config.txt");
    std::string s4p_path = cfg.s("channel.s4p_file", "");
    S4P nw; load_s4p(s4p_path, nw);
    printf("[1] config+s4p loaded, nfreq=%zu\n", nw.freq.size());
    fflush(stdout);

    std::vector<double> taps = {-0.053735, -0.277536, 0.499432, 0.075396, 0.093901};

    auto fir_v = extract_tx_s21(cfg, &nw, taps, 7);
    printf("[2] extract_tx_s21 ok, size=%zu\n", fir_v.size());
    fflush(stdout);

    auto [fir_norm, drms] = extract_tx_features(cfg, &nw, taps, 7);
    printf("[3] extract_tx_features ok\n");
    fflush(stdout);

    printf("fir_v      [");
    for (size_t i = 0; i < fir_v.size(); i++) printf("%s%.12e", i ? ", " : "", fir_v[i]);
    printf("]\n");
    printf("fir_norm   [");
    for (size_t i = 0; i < fir_norm.size(); i++) printf("%s%.12e", i ? ", " : "", fir_norm[i]);
    printf("]\n");
    printf("drive_rms  %.12e\n", drms);
    printf("DRIVE_RMS_NOMINAL %.12e\n", DRIVE_RMS_NOMINAL);

    WhiteBoxRidge model_a = load_ridge("models/ddps/model_a.json");
    printf("[4] model loaded, dim=%d W=%zu mu=%zu\n", model_a.dim, model_a.W.size(), model_a.mu.size());
    fflush(stdout);
    std::vector<double> probe = fir_norm; probe.push_back(drms);
    auto xn = model_a.standardize(probe);
    double pa = model_a.predict(xn);
    printf("pred_a     %.12e\n", pa);
    return 0;
}