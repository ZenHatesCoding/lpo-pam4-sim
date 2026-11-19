// eval_point.cpp — 单点物理评估（诊断用，不参与在线调优）。
//
// 给定一组 Tx FFE 抽头 / CTLE gDC,gDC2 / driver gain，在该用例的 cfg 上跑一次
// run_sim，打印 BER 与接收机 MLSE 的 AR(1) 白化抽头 a1（pr_taps=[1,a1]）。
// 用于回答「某个最优落点对应的 MLSE alpha 是多少」这类事后问题——在线结果里
// 只落 BER 与搜索向量，不落 a1。
//
// 用法（仓库根目录，WSL 内）：
//   ./cpp/build/eval_point cpp/build/cfg/cfg_IL20x20.txt \
//       --taps "-0.00258,-0.246866,0.459185,0.089054,0.112312" \
//       --gdc 6.365981194373 --gdc2 0.0 --gain 0.224276 --num-symbols 262144 \
//       --seed 42 --env-name IL20x20
#include "src/physim.hpp"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

using namespace dsh;

static std::vector<double> parse_list(const std::string& s) {
    std::vector<double> out;
    std::string cur;
    for (char c : s) {
        if (c == ',' || c == '[' || c == ']' || c == ' ') {
            if (!cur.empty()) { out.push_back(std::atof(cur.c_str())); cur.clear(); }
        } else {
            cur.push_back(c);
        }
    }
    if (!cur.empty()) out.push_back(std::atof(cur.c_str()));
    return out;
}

int main(int argc, char** argv) {
    if (argc < 2) {
        std::fprintf(stderr,
            "usage: eval_point <config.txt> --taps a,b,c,d,e --gdc X --gdc2 X --gain X\n"
            "       [--num-symbols N] [--seed S] [--env-name NAME] [--out PATH]\n");
        return 2;
    }
    std::string cfg_path = argv[1];
    std::vector<double> taps;
    double gdc = 0.0, gdc2 = 0.0, gain = 0.0;
    int num_symbols = 0, seed = 42;
    std::string env = "point", out_path;
    for (int i = 2; i < argc; i++) {
        std::string a = argv[i];
        auto next = [&](double def) { return (i + 1 < argc) ? std::atof(argv[++i]) : def; };
        if (a == "--taps") { if (i + 1 < argc) taps = parse_list(argv[++i]); }
        else if (a == "--gdc") gdc = next(gdc);
        else if (a == "--gdc2") gdc2 = next(gdc2);
        else if (a == "--gain") gain = next(gain);
        else if (a == "--num-symbols") num_symbols = (int)next(num_symbols);
        else if (a == "--seed") seed = (int)next(seed);
        else if (a == "--env-name") { if (i + 1 < argc) env = argv[++i]; }
        else if (a == "--out") { if (i + 1 < argc) out_path = argv[++i]; }
    }
    if (taps.size() != 5) {   // 与 optimizer.hpp 的 N_TAP=5 一致（此处不引 optimizer，避免拉入在线调优依赖）
        std::fprintf(stderr, "error: --taps needs 5 values, got %zu\n", taps.size());
        return 2;
    }

    Config cfg; cfg.load(cfg_path);
    if (num_symbols > 0) cfg.set("system.num_symbols", (double)num_symbols);
    cfg.set("system.tx_noise_snr_db", 0.0);          // 与全量结果同口径：真实链路噪声
    cfg.set("system.seed", (double)seed);
    cfg.set("channel.seed", (double)seed + 7919.0);
    cfg.set("tx.ctle_g_dc_db", gdc);
    cfg.set("tx.ctle_g_dc2_db", gdc2);
    cfg.set("channel.driver_gain", gain);

    std::string s4p_path = cfg.s("channel.s4p_file", "");
    S4P nw; load_s4p(s4p_path, nw);

    SimResult r = run_sim(cfg, taps, &nw, &nw);

    char buf[1024];
    std::snprintf(buf, sizeof(buf),
        "{\"env\": \"%s\", \"num_symbols\": %d, \"seed\": %d, "
        "\"taps\": [%.9g, %.9g, %.9g, %.9g, %.9g], \"gdc\": %.12g, \"gdc2\": %.12g, "
        "\"gain\": %.12g, \"gain_ratio\": %.12g, "
        "\"mlse_ber\": %.12e, \"log10_ber\": %.12e, \"ffe_ber\": %.12e, "
        "\"alpha1\": %.12e, \"sync_delay\": %d, \"phase_offset\": %d, \"n_valid\": %d}\n",
        env.c_str(), cfg.i("system.num_symbols", 0), seed,
        taps[0], taps[1], taps[2], taps[3], taps[4], gdc, gdc2, gain,
        gain / DRIVER_GAIN_NOMINAL,
        r.mlse_ber, (r.mlse_ber > 0.0 ? std::log10(r.mlse_ber) : -99.0), r.ffe_ber,
        r.alpha1, r.sync_delay, r.phase_offset, r.n_valid);

    std::fputs(buf, stdout);
    if (!out_path.empty()) {
        FILE* f = std::fopen(out_path.c_str(), "a");
        if (f) { std::fputs(buf, f); std::fclose(f); }
    }
    return 0;
}
