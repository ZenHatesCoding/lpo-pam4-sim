// test_optimizer.cpp — Stage-2 在线调优参考轨迹（C++ 侧，与 cpp/optimizer_debug.py 逐位比对）。
//
// 口径 = cpp/main.cpp 现役入口：8 维搜索向量 [5 个 Tx FFE 抽头, gDC, gDC2, u_gain]，
// 形状维梯度三档 full / rotate / secant（argv[1]）；direct 参照用 argv[2]=direct。
// 在线只用 Model A（Model B 已不在线使用）；代理档固定步数、不早停。
//
// 本文件不在 cpp/build_wsl.sh 的主构建里（该脚本只编译 main.cpp），单独编译核验：
//   wsl -d Ubuntu --cd /mnt/c/DSPPlayground/eLPO_antigravity bash -lc \
//       "g++ -std=c++17 -fsyntax-only cpp/tests/test_optimizer.cpp"
// 运行（仓库根目录，需先有 cpp/config.txt）：
//   g++ -O2 -std=c++17 cpp/tests/test_optimizer.cpp -o cpp/build/test_optimizer
//   ./cpp/build/test_optimizer full proxy
#include "../src/physim.hpp"
#include "../src/probe.hpp"
#include "../src/surrogate.hpp"
#include "../src/optimizer.hpp"
#include <cstdio>
#include <string>
using namespace dsh;

int main(int argc, char** argv) {
    // argv[1] = grad_mode(full/rotate/secant)，argv[2] = method(proxy/direct)
    std::string grad_mode = (argc > 1) ? argv[1] : "full";
    std::string method = (argc > 2) ? argv[2] : "proxy";

    Config cfg; cfg.load("cpp/config.txt");
    cfg.set("system.num_symbols", 262144.0);          // 2^18：唯一允许的比对口径
    cfg.set("system.tx_noise_snr_db", 0.0);
    cfg.set("system.seed", 42.0);
    cfg.set("channel.seed", 42.0 + 7919.0);

    std::string s4p_path = cfg.s("channel.s4p_file", "");
    S4P nw; load_s4p(s4p_path, nw);

    // Model B 不在线使用：只加载 Model A。
    WhiteBoxRidge model_a = load_ridge("models/ddps/model_a.json");

    // 现役次优起点（= result/seed_config_bad_1e4.json）：8 维
    std::vector<double> x0 = { -0.0885155201144294, -0.3147075644763699, 0.4079144179648486,
                               0.0845180360695101, 0.104344461374842,
                               6.726158576880279, 0.8457515411559222, -0.4875075052640998 };
    const int n_steps = 15;
    std::vector<int> sim_seeds = { 42 };

    printf("=== Stage-2 %s | grad_mode=%s | n_steps=%d ===\n",
           method.c_str(), grad_mode.c_str(), n_steps);
    printf("  x0=[");
    for (size_t i = 0; i < x0.size(); i++) printf("%s%.12e", i ? ", " : "", x0[i]);
    printf("]\n");

    std::vector<Stage2Step> trace;
    if (method == "direct") {
        auto [seed_lb, seed_ber] = physical_eval(cfg, taps_of(x0), x0[N_TAP], x0[N_TAP + 1],
                                                 gain_from_u(x0[N_TAP + 2]), &nw, &nw, sim_seeds);
        printf("  seed log10BER=%.12e BER=%.12e\n", seed_lb, seed_ber);
        trace = stage2_descent_direct(cfg, x0, n_steps, GD_LR, seed_lb, &nw, &nw, sim_seeds);
    } else {
        trace = stage2_descent_proxy(cfg, model_a, x0, n_steps, GD_LR,
                                     grad_mode, ROTATE_K, &nw, &nw, sim_seeds);
    }

    printf("\n=== TRACE ===\n");
    for (auto& rec : trace) {
        printf("step=%d\n", rec.step);
        printf("  x=        [");
        for (size_t i = 0; i < rec.x.size(); i++) printf("%s%.12e", i ? ", " : "", rec.x[i]);
        printf("]\n");
        printf("  gdc=%.12e gdc2=%.12e gain=%.12e u_gain=%.12e\n",
               rec.gdc, rec.gdc2, rec.gain, rec.u_gain);
        printf("  drive_rms=%.12e pred_a=%.12e\n", rec.drive_rms, rec.pred_a);
        printf("  real_logber=%.12e real_mlse=%.12e\n", rec.real_logber, rec.real_mlse);
        printf("  n_probe_states=%d refreshed=[", rec.n_probe_states);
        for (size_t i = 0; i < rec.refreshed.size(); i++) printf("%s%d", i ? "," : "", rec.refreshed[i]);
        printf("] grad_norm=%.12e\n", rec.grad_norm);
        printf("  stop_reason=%s\n", rec.stop_reason.c_str());
    }
    return 0;
}
