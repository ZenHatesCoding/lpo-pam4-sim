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
#include <algorithm>

using namespace dsh;

static double clamp_arg(const char* s, int argc, char** argv, int& i, double def) {
    if (std::string(s) == "" || i + 1 >= argc) return def;
    return std::atof(argv[++i]);
}

// 把 vector<double> 格式化成 "[a, b, c]" 列表字符串（trace 的 x / taps 列）
static std::string csv_list(const std::vector<double>& v, const char* fmt) {
    std::string s = "[";
    char buf[64];
    for (size_t i = 0; i < v.size(); i++) {
        snprintf(buf, sizeof(buf), fmt, v[i]);
        if (i) s += ", ";
        s += buf;
    }
    s += "]";
    return s;
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
    std::string env_name;
    std::string method = "chain";

    for (int i = 2; i < argc; i++) {
        std::string a = argv[i];
        if (a == "--num-symbols") num_symbols = clamp_arg(a.c_str(), argc, argv, i, 0.0);
        else if (a == "--tx-noise-snr") tx_noise_arg = clamp_arg(a.c_str(), argc, argv, i, -1.0);
        else if (a == "--seed") seed = (long)clamp_arg(a.c_str(), argc, argv, i, -1.0);
        else if (a == "--n-steps") n_steps = (int)clamp_arg(a.c_str(), argc, argv, i, 50.0);
        else if (a == "--seed-gain-u") seed_gain_u = clamp_arg(a.c_str(), argc, argv, i, 0.0);
        else if (a == "--model-dir") { if (i + 1 < argc) model_dir = argv[++i]; }
        else if (a == "--out") { if (i + 1 < argc) out_path = argv[++i]; }
        else if (a == "--env-name") { if (i + 1 < argc) env_name = argv[++i]; }
        else if (a == "--seed-config") { if (i + 1 < argc) seed_config_path = argv[++i]; }
        else if (a == "--method") { if (i + 1 < argc) method = argv[++i]; }
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

    // --- seed 点评估（与 Python run_case 一致：先实测 seed BER，再下降）---
    std::vector<double> taps0 = construct_taps({ x0[0], x0[1], x0[2], x0[3] }, FFE_PRE);
    double gdc0 = x0[N_SIDE], gdc20 = x0[N_SIDE + 1];
    double gain0 = gain_from_u(x0[N_SIDE + 2]);
    auto [seed_lb, seed_ber] = physical_eval(cfg, taps0, gdc0, gdc20, gain0, &nw, &nw, sim_seeds);
    auto seed_probe = probe_features(cfg, taps0, gdc0, gdc20, gain0, &nw);
    double pa_seed = predict_a_probe(model_a, seed_probe);
    double rms_seed = measure_drive_rms(cfg, taps0, gdc0, gdc20, gain0, &nw);
    double pb_seed = predict_b_params(model_b, { x0[0], x0[1], x0[2], x0[3], x0[4], x0[5] }, rms_seed);

    fprintf(stderr, "[run] env=%s config=%s num_symbols=%d tx_noise=%.1f n_steps=%d\n",
            env_name.c_str(), config_path.c_str(), (int)cfg.d("system.num_symbols", 0),
            cfg.d("system.tx_noise_snr_db", 0.0), n_steps);

    auto t0 = std::chrono::high_resolution_clock::now();
    std::vector<Stage2Step> trace;
    if (method == "secant") {
        trace = stage2_descent_secant(cfg, model_a, model_b, x0, FFE_PRE, n_steps, GD_LR, &nw, &nw, sim_seeds);
    } else {
        trace = stage2_descent(cfg, model_a, model_b, x0, FFE_PRE, n_steps, GD_LR, &nw, &nw, sim_seeds);
    }
    auto t1 = std::chrono::high_resolution_clock::now();
    double secs = std::chrono::duration<double>(t1 - t0).count();

    // --- 汇总（best = argmin real_logber；final = 最后一步）---
    if (trace.empty()) {
        printf("\n=== RESULT ===\nsteps=0  elapsed_sec=%.3f\nno_steps\n", secs);
        if (!out_path.empty()) {
            FILE* fo = fopen(out_path.c_str(), "w");
            if (fo) {
                fprintf(fo, "{\"env\":\"%s\",\"seed_lb\":%.12e,\"seed_ber\":%.12e,"
                        "\"pa_seed\":%.12e,\"pb_seed\":%.12e,\"n_steps_actual\":0,\"best_step\":-1,"
                        "\"best_lb\":%.12e,\"best_ber\":%.12e,\"final_lb\":%.12e,\"final_ber\":%.12e,"
                        "\"max_lb\":%.12e,\"delta_lb_seed_to_best\":0.0,\"delta_lb_seed_to_final\":0.0,"
                        "\"stop_reason\":\"no_trace\",\"early_stop\":true,\"elapsed_sec\":%.6f}\n",
                        env_name.c_str(), seed_lb, seed_ber, pa_seed, pb_seed,
                        seed_lb, seed_ber, seed_lb, seed_ber, seed_lb, secs);
                fclose(fo);
            }
        }
        return 0;
    }

    size_t best_idx = 0;
    for (size_t i = 1; i < trace.size(); i++)
        if (trace[i].real_logber < trace[best_idx].real_logber) best_idx = i;
    auto& best = trace[best_idx];
    auto& fin = trace.back();
    double max_lb = trace[0].real_logber;
    for (auto& r : trace) max_lb = std::max(max_lb, r.real_logber);

    printf("\n=== RESULT ===\n");
    printf("steps=%zu  elapsed_sec=%.3f\n", trace.size(), secs);
    printf("seed_lb=%.12e seed_ber=%.12e\n", seed_lb, seed_ber);
    printf("best_step=%zu best_lb=%.12e best_ber=%.12e\n",
           best_idx, best.real_logber, best.real_mlse);
    printf("best_taps=[");
    for (size_t i = 0; i < best.taps.size(); i++) printf("%s%.12e", i ? ", " : "", best.taps[i]);
    printf("]\n");
    printf("best_gdc=%.12e best_gdc2=%.12e best_gain=%.12e best_u_gain=%.12e\n",
           best.gdc, best.gdc2, best.gain, best.u_gain);
    printf("stop_reason=%s\n", fin.stop_reason.c_str());

    // 逐步
    printf("\n=== TRACE ===\n");
    for (auto& rec : trace) {
        printf("step=%d gdc=%.6f gdc2=%.6f gain=%.6f pred_a=%.4f real_mlse=%.3e stop=%s\n",
               rec.step, rec.gdc, rec.gdc2, rec.gain, rec.pred_a, rec.real_mlse, rec.stop_reason.c_str());
    }

    // --- 写 trace / probes CSV（与 Python test_generalization 同 schema，供 report_ddps 出图）---
    if (!out_path.empty() && !trace.empty()) {
        std::string dir = out_path.substr(0, out_path.find_last_of("/\\") + 1);
        FILE* ft = fopen((dir + "trace_" + env_name + ".csv").c_str(), "w");
        if (ft) {
            fprintf(ft, "step,x,taps,gdc,gdc2,gain,gain_ratio,u_gain,drive_rms,pred_b_ber,"
                        "allowed_ber,stop_reason,pred_a,pred_b,real_lb,real_ber,grad_norm\n");
            for (auto& rec : trace) {
                fprintf(ft, "%d,\"%s\",\"%s\",%.12e,%.12e,%.12e,%.12e,%.12e,%.12e,%.12e,"
                            "%.12e,\"%s\",%.12e,%.12e,%.12e,%.12e,%.12e\n",
                        rec.step,
                        csv_list(rec.x, "%.12e").c_str(), csv_list(rec.taps, "%.6f").c_str(),
                        rec.gdc, rec.gdc2, rec.gain, rec.gain_ratio, rec.u_gain, rec.drive_rms,
                        rec.pred_b_ber, rec.allowed_ber, rec.stop_reason.c_str(),
                        rec.pred_a, rec.pred_b, rec.real_logber, rec.real_mlse, rec.grad_norm);
            }
            fclose(ft);
        }
        FILE* fp = fopen((dir + "probes_" + env_name + ".csv").c_str(), "w");
        if (fp) {
            fprintf(fp, "step,param,sign,x_0,x_1,x_2,x_3,x_4,x_5,x_6,"
                        "tap_0,tap_1,tap_2,tap_3,tap_4,gdc,gdc2,gain,gain_ratio,u_gain,real_lb,real_ber\n");
            for (auto& rec : trace) {
                for (auto& p : rec.probes) {
                    fprintf(fp, "%d,%d,%d,%.12e,%.12e,%.12e,%.12e,%.12e,%.12e,%.12e,"
                                "%.12e,%.12e,%.12e,%.12e,%.12e,%.12e,%.12e,%.12e,%.12e,%.12e,%.12e,%.12e\n",
                            rec.step, p.param, p.sign,
                            p.x[0], p.x[1], p.x[2], p.x[3], p.x[4], p.x[5], p.x[6],
                            p.taps[0], p.taps[1], p.taps[2], p.taps[3], p.taps[4],
                            p.gdc, p.gdc2, p.gain, p.gain_ratio, p.u_gain, p.real_logber, p.real_mlse);
                }
            }
            fclose(fp);
        }
    }

    if (!out_path.empty()) {
        FILE* fo = fopen(out_path.c_str(), "w");
        if (fo) {
            fprintf(fo, "{\n");
            fprintf(fo, "  \"env\": \"%s\",\n", env_name.c_str());
            fprintf(fo, "  \"seed_lb\": %.12e,\n  \"seed_ber\": %.12e,\n", seed_lb, seed_ber);
            fprintf(fo, "  \"pa_seed\": %.12e,\n  \"pb_seed\": %.12e,\n", pa_seed, pb_seed);
            fprintf(fo, "  \"seed_gain\": %.12e,\n  \"seed_gain_ratio\": %.12e,\n",
                    gain0, gain0 / DRIVER_GAIN_NOMINAL);
            fprintf(fo, "  \"n_steps_actual\": %zu,\n", trace.size());
            fprintf(fo, "  \"best_lb\": %.12e,\n  \"best_ber\": %.12e,\n  \"best_step\": %zu,\n",
                    best.real_logber, best.real_mlse, best_idx);
            fprintf(fo, "  \"final_lb\": %.12e,\n  \"final_ber\": %.12e,\n  \"max_lb\": %.12e,\n",
                    fin.real_logber, fin.real_mlse, max_lb);
            fprintf(fo, "  \"delta_lb_seed_to_best\": %.12e,\n  \"delta_lb_seed_to_final\": %.12e,\n",
                    best.real_logber - seed_lb, fin.real_logber - seed_lb);
            fprintf(fo, "  \"best_taps\": [");
            for (size_t i = 0; i < best.taps.size(); i++)
                fprintf(fo, "%s%.6f", i ? ", " : "", best.taps[i]);
            fprintf(fo, "],\n");
            fprintf(fo, "  \"best_gdc\": %.12e,\n  \"best_gdc2\": %.12e,\n  \"best_gain\": %.12e,\n",
                    best.gdc, best.gdc2, best.gain);
            fprintf(fo, "  \"best_gain_ratio\": %.12e,\n  \"best_u_gain\": %.12e,\n",
                    best.gain / DRIVER_GAIN_NOMINAL, best.u_gain);
            fprintf(fo, "  \"stop_reason\": \"%s\",\n", fin.stop_reason.c_str());
            fprintf(fo, "  \"early_stop\": %s,\n", (trace.size() < (size_t)n_steps) ? "true" : "false");
            fprintf(fo, "  \"elapsed_sec\": %.6f\n", secs);
            fprintf(fo, "}\n");
            fclose(fo);
        }
    }
    return 0;
}