// main.cpp — C++ DDPS 平台统一入口（在线调优）。
//
// 用法：
//   run_ddps <config.txt> [选项]
//     --num-symbols N       仿真符号数（默认取 config）
//     --tx-noise-snr X      Tx 输出加噪 SNR(dB)；0 = 关（真实链路噪声）
//     --seed S              系统种子
//     --n-steps N           Stage-2 最大步数
//     --seed-gain-u U       seed gain 的 u_gain（log10(gain/0.3399)）
//     --seed-config PATH    次优起点 JSON（best_taps 或 best_pre_post + best_gdc/best_gdc2
//                           + best_u_gain|best_gain）
//     --model-dir DIR       model_a.json 所在目录（direct 方式不使用代理）
//     --method M            proxy | direct（proxy = Model A 探针代理在线调优；
//                           direct = 端到端 BER 直接梯度下降，有回传通道时的参照）
//     --grad-mode M         full | rotate | secant（proxy 的形状维梯度刷新方式）
//     --rotate-k K          rotate 模式每步刷新的形状维个数（默认 2）
//     --env-name NAME       用例名（trace/probes CSV 文件名后缀）
//     --out PATH            结果 JSON 输出路径（可选）
//
// 与 Python 一一对应：物理链(run_sim) / 探针(extract_tx_s21+drive_rms) /
// 代理(WhiteBoxRidge) / 在线调优(Stage-2 梯度下降：full / rotate / secant / direct)。
#include "src/physim.hpp"
#include "src/probe.hpp"
#include "src/surrogate.hpp"
#include "src/optimizer.hpp"
#include <cstdio>
#include <cstring>
#include <chrono>
#include <string>
#include <algorithm>
#include <fstream>
#include <sstream>

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

// 把 vector<int> 格式化成 "0,1" 字符串（trace 的 refreshed 列）
static std::string csv_int_list(const std::vector<int>& v) {
    std::string s;
    char buf[16];
    for (size_t i = 0; i < v.size(); i++) {
        snprintf(buf, sizeof(buf), "%d", v[i]);
        if (i) s += ",";
        s += buf;
    }
    return s;
}

int main(int argc, char** argv) {
    std::string config_path = (argc > 1) ? argv[1] : "cpp/config.txt";
    double num_symbols = 0.0;       // 0 = 取 config
    double tx_noise_arg = -1.0;     // <0 = 取 config
    long seed = -1;
    int n_steps = 15;               // 协议口径固定 15 步（N_STEPS）
    double seed_gain_u = 0.0;
    std::string model_dir = "models/ddps";
    std::string out_path;
    std::string seed_config_path;
    std::string env_name;
    std::string method = "proxy";
    std::string grad_mode = "full";
    int rotate_k = ROTATE_K;

    for (int i = 2; i < argc; i++) {
        std::string a = argv[i];
        if (a == "--num-symbols") num_symbols = clamp_arg(a.c_str(), argc, argv, i, 0.0);
        else if (a == "--tx-noise-snr") tx_noise_arg = clamp_arg(a.c_str(), argc, argv, i, -1.0);
        else if (a == "--seed") seed = (long)clamp_arg(a.c_str(), argc, argv, i, -1.0);
        else if (a == "--n-steps") n_steps = (int)clamp_arg(a.c_str(), argc, argv, i, 50.0);
        else if (a == "--seed-gain-u") seed_gain_u = clamp_arg(a.c_str(), argc, argv, i, 0.0);
        else if (a == "--rotate-k") rotate_k = (int)clamp_arg(a.c_str(), argc, argv, i, (double)ROTATE_K);
        else if (a == "--model-dir") { if (i + 1 < argc) model_dir = argv[++i]; }
        else if (a == "--out") { if (i + 1 < argc) out_path = argv[++i]; }
        else if (a == "--env-name") { if (i + 1 < argc) env_name = argv[++i]; }
        else if (a == "--seed-config") { if (i + 1 < argc) seed_config_path = argv[++i]; }
        else if (a == "--method") { if (i + 1 < argc) method = argv[++i]; }
        else if (a == "--grad-mode") { if (i + 1 < argc) grad_mode = argv[++i]; }
    }

    Config cfg; cfg.load(config_path);
    if (num_symbols > 0) cfg.set("system.num_symbols", num_symbols);
    if (tx_noise_arg >= 0) cfg.set("system.tx_noise_snr_db", tx_noise_arg);
    if (seed >= 0) { cfg.set("system.seed", (double)seed); cfg.set("channel.seed", (double)seed + 7919.0); }

    std::string s4p_path = cfg.s("channel.s4p_file", "");
    S4P nw; load_s4p(s4p_path, nw);

    WhiteBoxRidge model_a = load_ridge(model_dir + "/model_a.json");

    // seed 点（与 ddps_optimizer 默认 SEED_TAPS/SEED_GDC/SEED_GDC2 一致；提供 --seed-config
    // 时改用次优起点 JSON：best_taps（5 抽头，Stage-2 口径）或 best_pre_post（旧口径派生））
    std::vector<double> SEED_TAPS = { -0.034, -0.2987, 0.6091, 0.0, 0.0582 };
    double SEED_GDC = 6.0, SEED_GDC2 = 2.0;
    std::vector<double> x0 = { SEED_TAPS[0], SEED_TAPS[1], SEED_TAPS[2], SEED_TAPS[3], SEED_TAPS[4],
                               SEED_GDC, SEED_GDC2, seed_gain_u };
    if (!seed_config_path.empty()) {
        std::ifstream scf(seed_config_path);
        std::stringstream scss; scss << scf.rdbuf();
        std::string sc = scss.str();
        double gdc = json_number(sc, "best_gdc", 6.0);
        double gdc2 = json_number(sc, "best_gdc2", 2.0);
        double gain = 0.0; bool has_gain = false;
        if (sc.find("\"best_u_gain\"") != std::string::npos) {
            gain = gain_from_u(json_number(sc, "best_u_gain", 0.0)); has_gain = true;
        } else if (sc.find("\"best_gain\"") != std::string::npos) {
            gain = json_number(sc, "best_gain", 0.0); has_gain = true;
        }
        std::vector<double> taps_seed;
        if (sc.find("\"best_taps\"") != std::string::npos) {
            taps_seed = json_array(sc, "best_taps");
        } else {
            std::vector<double> pre_post = json_array(sc, "best_pre_post");
            if (pre_post.size() >= 4) taps_seed = construct_taps(pre_post, FFE_PRE);
        }
        if (taps_seed.size() >= (size_t)N_TAP) {
            x0 = { taps_seed[0], taps_seed[1], taps_seed[2], taps_seed[3], taps_seed[4],
                   gdc, gdc2, has_gain ? u_from_gain(gain) : seed_gain_u };
        }
    }
    std::vector<int> sim_seeds = { 42 };

    // --- seed 点评估（与 Python run_case 一致：先实测 seed BER，再下降）---
    std::vector<double> taps0 = taps_of(x0);
    double gdc0 = x0[N_TAP], gdc20 = x0[N_TAP + 1];
    double gain0 = gain_from_u(x0[N_TAP + 2]);
    auto [seed_lb, seed_ber] = physical_eval(cfg, taps0, gdc0, gdc20, gain0, &nw, &nw, sim_seeds);
    double pa_seed, pb_seed = 0.0;               // 无 Model B：pb_seed 恒 0（与 Python 一致）
    if (method == "direct") {
        pa_seed = seed_lb;                       // direct：pa_seed 记目标初值（真实 log10 BER）
    } else {
        auto seed_probe = probe_features(cfg, taps0, gdc0, gdc20, gain0, &nw);
        pa_seed = predict_a_probe(model_a, seed_probe);
    }

    fprintf(stderr, "[run] env=%s config=%s num_symbols=%d tx_noise=%.1f n_steps=%d method=%s grad_mode=%s\n",
            env_name.c_str(), config_path.c_str(), (int)cfg.d("system.num_symbols", 0),
            cfg.d("system.tx_noise_snr_db", 0.0), n_steps, method.c_str(), grad_mode.c_str());

    auto t0 = std::chrono::high_resolution_clock::now();
    std::vector<Stage2Step> trace;
    if (method == "direct") {
        trace = stage2_descent_direct(cfg, x0, n_steps, GD_LR, seed_lb, &nw, &nw, sim_seeds);
    } else {
        trace = stage2_descent_proxy(cfg, model_a, x0, n_steps, GD_LR, grad_mode, rotate_k,
                                     &nw, &nw, sim_seeds);
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
                        "\"n_landed\":0,\"n_probe_states\":0,\"n_real_evals\":0,"
                        "\"max_probe_lb\":0.0,\"max_probe_ber\":0.0,"
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
    int n_probe_states = 0;
    double max_probe_lb = -1e300;
    for (auto& r : trace) {
        n_probe_states += r.n_probe_states;
        for (auto& p : r.probes) max_probe_lb = std::max(max_probe_lb, p.real_logber);
    }
    double max_probe_ber = (n_probe_states > 0) ? std::pow(10.0, max_probe_lb) : 0.0;

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
    printf("n_real_evals=%d (landed=%zu + probes=%d) max_probe_ber=%.3e\n",
           (int)trace.size() + n_probe_states, trace.size(), n_probe_states, max_probe_ber);
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
                        "allowed_ber,stop_reason,pred_a,pred_b,real_lb,real_ber,grad,refreshed,"
                        "n_probe_states,grad_norm\n");
            for (auto& rec : trace) {
                fprintf(ft, "%d,\"%s\",\"%s\",%.12e,%.12e,%.12e,%.12e,%.12e,%.12e,%.12e,"
                            "%.12e,\"%s\",%.12e,%.12e,%.12e,%.12e,\"%s\",\"%s\",%d,%.12e\n",
                        rec.step,
                        csv_list(rec.x, "%.12e").c_str(), csv_list(rec.taps, "%.6f").c_str(),
                        rec.gdc, rec.gdc2, rec.gain, rec.gain_ratio, rec.u_gain, rec.drive_rms,
                        rec.pred_b_ber, rec.allowed_ber, rec.stop_reason.c_str(),
                        rec.pred_a, rec.pred_b, rec.real_logber, rec.real_mlse,
                        csv_list(rec.grad, "%.12e").c_str(), csv_int_list(rec.refreshed).c_str(),
                        rec.n_probe_states, rec.grad_norm);
            }
            fclose(ft);
        }
        FILE* fp = fopen((dir + "probes_" + env_name + ".csv").c_str(), "w");
        if (fp) {
            fprintf(fp, "step,param,sign");
            for (int j = 0; j < N_DIM; j++) fprintf(fp, ",x_%d", j);
            for (int j = 0; j < N_TAP; j++) fprintf(fp, ",tap_%d", j);
            fprintf(fp, ",gdc,gdc2,gain,gain_ratio,u_gain,real_lb,real_ber\n");
            for (auto& rec : trace) {
                for (auto& p : rec.probes) {
                    fprintf(fp, "%d,%d,%d", rec.step, p.param, p.sign);
                    for (int j = 0; j < N_DIM; j++) fprintf(fp, ",%.12e", p.x[j]);
                    for (int j = 0; j < N_TAP; j++) fprintf(fp, ",%.12e", p.taps[j]);
                    fprintf(fp, ",%.12e,%.12e,%.12e,%.12e,%.12e,%.12e,%.12e\n",
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
            fprintf(fo, "  \"n_landed\": %zu,\n  \"n_probe_states\": %d,\n  \"n_real_evals\": %d,\n",
                    trace.size(), n_probe_states, (int)trace.size() + n_probe_states);
            fprintf(fo, "  \"max_probe_lb\": %.12e,\n  \"max_probe_ber\": %.12e,\n",
                    (n_probe_states > 0) ? max_probe_lb : 0.0, max_probe_ber);
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
