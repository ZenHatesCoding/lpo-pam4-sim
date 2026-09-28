// test_equiv.cpp — 读取 config.txt + 自定义 FFE 抽头，跑一次 run_sim 并打印节点校验和，
// 供与 Python（cpp/equiv_py.py）逐节点比对。
#include "../src/physim.hpp"
#include <cstdio>
#include <vector>
#include <sstream>

using namespace dsh;

static std::vector<double> parse_taps(const std::string& v) {
    std::vector<double> t;
    std::string s = v;
    for (auto& c : s) if (c == '[' || c == ']') c = ' ';
    std::stringstream ss(s);
    std::string tok;
    while (std::getline(ss, tok, ',')) {
        tok.erase(0, tok.find_first_not_of(" \t"));
        tok.erase(tok.find_last_not_of(" \t") + 1);
        if (tok.empty()) continue;
        t.push_back(std::stod(tok));
    }
    return t;
}

int main(int argc, char** argv) {
    std::string cfgpath = (argc > 1) ? argv[1] : "cpp/config.txt";
    Config cfg; cfg.load(cfgpath);

    std::vector<double> taps;
    if (cfg.has("tx.custom_taps")) taps = parse_taps(cfg.s("tx.custom_taps", ""));

    std::string s4p_path = cfg.s("channel.s4p_file", "");
    S4P nw;
    bool ok = !s4p_path.empty() && load_s4p(s4p_path, nw);
    if (!ok) { fprintf(stderr, "S4P load failed: %s\n", s4p_path.c_str()); return 2; }

    SimResult r = run_sim(cfg, taps, &nw, &nw);

    printf("chk_tx_out_nonoise %.12e\n", r.chk_tx_out_nonoise);
    printf("chk_tx_out_noisy   %.12e\n", r.chk_tx_out_noisy);
    printf("chk_tx_analog      %.12e\n", r.chk_tx_analog);
    printf("chk_rx_analog      %.12e\n", r.chk_rx_analog);
    printf("chk_rx_adc         %.12e\n", r.chk_rx_adc);
    printf("chk_rx_eq          %.12e\n", r.chk_rx_eq);
    printf("chk_white          %.12e\n", r.chk_white);
    printf("sync_delay %d\n", r.sync_delay);
    printf("phase_offset %d\n", r.phase_offset);
    printf("n_valid %d\n", r.n_valid);
    printf("ffe_ber %.12e\n", r.ffe_ber);
    printf("mlse_ber %.12e\n", r.mlse_ber);
    return 0;
}