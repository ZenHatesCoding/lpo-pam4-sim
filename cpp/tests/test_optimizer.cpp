// test_optimizer.cpp — Stage-2 在线调优，与 Python optimizer_debug.py 逐位比对。
#include "../src/physim.hpp"
#include "../src/probe.hpp"
#include "../src/surrogate.hpp"
#include "../src/optimizer.hpp"
#include <cstdio>
using namespace dsh;

int main() {
    Config cfg; cfg.load("cpp/config.txt");
    cfg.set("system.num_symbols", 16384.0);
    cfg.set("system.tx_noise_snr_db", 23.0);
    cfg.set("system.seed", 42.0);
    cfg.set("channel.seed", 42.0 + 7919.0);

    std::string s4p_path = cfg.s("channel.s4p_file", "");
    S4P nw; load_s4p(s4p_path, nw);

    WhiteBoxRidge model_a = load_ridge("models/ddps/model_a.json");
    WhiteBoxRidge model_b = load_ridge("models/ddps/model_b.json");

    std::vector<double> x0 = { -0.034, -0.2987, 0.0, 0.0582, 6.0, 2.0, 0.0 };
    std::vector<int> sim_seeds = { 42 };

    auto trace = stage2_descent(cfg, model_a, model_b, x0, FFE_PRE, 30, GD_LR, &nw, &nw, sim_seeds);

    printf("\n=== TRACE ===\n");
    for (auto& rec : trace) {
        printf("step=%d\n", rec.step);
        printf("  x=        [");
        for (size_t i = 0; i < rec.x.size(); i++) printf("%s%.12e", i ? ", " : "", rec.x[i]);
        printf("]\n");
        printf("  gdc=%.12e gdc2=%.12e gain=%.12e u_gain=%.12e\n", rec.gdc, rec.gdc2, rec.gain, rec.u_gain);
        printf("  drive_rms=%.12e pred_a=%.12e pred_b=%.12e\n", rec.drive_rms, rec.pred_a, rec.pred_b);
        printf("  real_logber=%.12e real_mlse=%.12e\n", rec.real_logber, rec.real_mlse);
        printf("  stop_reason=%s\n", rec.stop_reason.c_str());
    }
    return 0;
}