// main.cpp — C++ DDPS 平台统一入口（在线调优）。
//
// 用法：
//   run_ddps.exe <config.txt> [选项]
//     --num-symbols N       仿真符号数（默认取 config）
//     --tx-noise-snr X      Tx 输出加噪 SNR(dB)；0 = 关（真实链路噪声）
//     --seed S              系统种子
//     --n-steps N           Stage-2 最大步数
//     --seed-gain-u U       seed gain 的 u_gain（log10(gain/0.3399)）
//     --model-dir DIR       model_a.json / model_b.json 所在目录
//     --out PATH            结果 JSON 输出路径（可选）
//
// 与 Python 一一对应：物理链(run_sim) / 探针(extract_tx_s21+drive_rms) /
// 代理(WhiteBoxRidge) / 在线调优(Stage-2 链式梯度下降)。
#include "src/physim.hpp"
#include "src/probe.hpp"
#include "src/surrogate.hpp"
#include "src/optimizer.hpp"
#include <cstdio>
#include <cstring>
#include <chrono>
#include <string>

using namespace dsh;

static double clamp_arg(const char* s, int argc, char** argv, int& i, double def) {
    if (std::string(s) == "" || i + 1 >= argc) return def;
    return std::atof(argv[++i]);
}

int main(int argc, char** argv) {
    std::string config_path = (argc > 1) ? argv[1] : "cpp/config.txt";
    double num_symbols = 0.0;       // 0 = 取 config
    double tx_noise_arg = -1.0;     // <0 = 取 config
    long seed = -1;
    int n_steps = 50;
    double seed_gain_u = 0.0;
    std::string model_dir = "models/ddps";
    std::string out_path;
    std::string seed_config_path;

    for (int i = 2; i < argc; i++) {
        std::string a = argv[i];
        if (a == "--num-symbols") num_symbols = clamp_arg(a.c_str(), argc, argv, i, 0.0);
        else if (a == "--tx-noise-snr") tx_noise_arg = clamp_arg(a.c_str(), argc, argv, i, -1.0);
        else if (a == "--seed") seed = (long)clamp_arg(a.c_str(), argc, argv, i, -1.0);
        else if (a == "--n-steps") n_steps = (int)clamp_arg(a.c_str(), argc, argv, i, 50.0);
        else if (a == "--seed-gain-u") seed_gain_u = clamp_arg(a.c_str(), argc, argv, i, 0.0);
        else if (a == "--model-dir") { if (i + 1 < argc) model_dir = argv[++i]; }
        else if (a == "--out") { if (i + 1 < argc) out_path = argv[++i]; }
        else if (a == "--seed-config") { if (i + 1 < argc) seed_config_path = argv[++i]; }
    }

    Config cfg; cfg.load(config_path);
    if (num_symbols > 0) cfg.set("system.num_symbols", num_symbols);
    if (tx_noise_arg >= 0) cfg.set("system.tx_noise_snr_db", tx_noise_arg);
    if (seed >= 0) { cfg.set("system.seed", (double)seed); cfg.set("channel.seed", (double)seed + 7919.0); }

    std::string s4p_path = cfg.s("channel.s4p_file", "");
    S4P nw; load_s4p(s4p_path, nw);

    WhiteBoxRidge model_a = load_ridge(model_dir + "/model_a.json");
    WhiteBoxRidge model_b = load_ridge(model_dir + "/model_b.json");

    // seed 点（与 ddps_optimizer 默认 SEED_TAPS/SEED_GDC/SEED_GDC2 + per-case gain 一致；
    // 提供 --seed-config 时改用次优起点 JSON：best_pre_post/best_gdc/best_gdc2/best_u_gain|best_gain）
    std::vector<double> SEED_TAPS = { -0.034, -0.2987, 0.6091, 0.0, 0.0582 };
    double SEED_GDC = 6.0, SEED_GDC2 = 2.0;
    std::vector<double> x0 = { SEED_TAPS[0], SEED_TAPS[1], SEED_TAPS[3], SEED_TAPS[4],
                               SEED_GDC, SEED_GDC2, seed_gain_u };
    if (!seed_config_path.empty()) {
        std::ifstream scf(seed_config_path);
        std::stringstream scss; scss << scf.rdbuf();
        std::string sc = scss.str();
        std::vector<double> pre_post = json_array(sc, "best_pre_post");
        double gdc = json_number(sc, "best_gdc", 6.0);
        double gdc2 = json_number(sc, "best_gdc2", 2.0);
        double gain = 0.0; bool has_gain = false;
        if (sc.find("\"best_u_gain\"") != std::string::npos) {
            gain = gain_from_u(json_number(sc, "best_u_gain", 0.0)); has_gain = true;
        } else if (sc.find("\"best_gain\"") != std::string::npos) {
            gain = json_number(sc, "best_gain", 0.0); has_gain = true;
        }
        if (pre_post.size() >= 4) {
            x0 = { pre_post[0], pre_post[1], pre_post[2], pre_post[3], gdc, gdc2,
                   has_gain ? u_from_gain(gain) : seed_gain_u };
        }
    }
    std::vector<int> sim_seeds = { 42 };

    fprintf(stderr, "[run] config=%s num_symbols=%d tx_noise=%.1f seed_gain_u=%.4f n_steps=%d\n",
            config_path.c_str(), (int)cfg.d("system.num_symbols", 0), cfg.d("system.tx_noise_snr_db", 0.0),
            seed_gain_u, n_steps);

    auto t0 = std::chrono::high_resolution_clock::now();
    auto trace = stage2_descent(cfg, model_a, model_b, x0, FFE_PRE, n_steps, GD_LR, &nw, &nw, sim_seeds);
    auto t1 = std::chrono::high_resolution_clock::now();
    double secs = std::chrono::duration<double>(t1 - t0).count();

    // 打印 trace + 最终结果
    printf("\n=== RESULT ===\n");
    printf("steps=%zu  elapsed_sec=%.3f\n", trace.size(), secs);
    if (trace.empty()) { printf("no_steps\n"); return 0; }

    auto& fin = trace.back();
    printf("stop_reason=%s\n", fin.stop_reason.c_str());
    printf("x_final=[");
    for (size_t i = 0; i < fin.x.size(); i++) printf("%s%.12e", i ? ", " : "", fin.x[i]);
    printf("]\n");
    printf("taps_final=[");
    for (size_t i = 0; i < fin.taps.size(); i++) printf("%s%.12e", i ? ", " : "", fin.taps[i]);
    printf("]\n");
    printf("gdc=%.12e gdc2=%.12e gain=%.12e gain_ratio=%.12e u_gain=%.12e\n",
           fin.gdc, fin.gdc2, fin.gain, fin.gain_ratio, fin.u_gain);
    printf("pred_a_log10ber=%.12e  real_mlse_ber=%.12e  real_log10ber=%.12e\n",
           fin.pred_a, fin.real_mlse, fin.real_logber);

    // 逐步
    printf("\n=== TRACE ===\n");
    for (auto& rec : trace) {
        printf("step=%d gdc=%.6f gdc2=%.6f gain=%.6f pred_a=%.4f real_mlse=%.3e stop=%s\n",
               rec.step, rec.gdc, rec.gdc2, rec.gain, rec.pred_a, rec.real_mlse, rec.stop_reason.c_str());
    }

    if (!out_path.empty()) {
        FILE* fo = fopen(out_path.c_str(), "w");
        if (fo) {
            fprintf(fo, "{\n  \"steps\": %zu,\n  \"elapsed_sec\": %.6f,\n", trace.size(), secs);
            fprintf(fo, "  \"stop_reason\": \"%s\",\n", fin.stop_reason.c_str());
            fprintf(fo, "  \"gdc\": %.12e,\n  \"gdc2\": %.12e,\n  \"gain\": %.12e,\n",
                    fin.gdc, fin.gdc2, fin.gain);
            fprintf(fo, "  \"pred_a_log10ber\": %.12e,\n  \"real_mlse_ber\": %.12e,\n  \"real_log10ber\": %.12e\n",
                    fin.pred_a, fin.real_mlse, fin.real_logber);
            fprintf(fo, "}\n");
            fclose(fo);
        }
    }
    return 0;
}