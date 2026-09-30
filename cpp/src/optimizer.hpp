// optimizer.hpp — DDPS 在线调优（ddps_optimizer.py Stage-2 链式梯度下降 一比一复刻）。
#pragma once

#include "physim.hpp"
#include "probe.hpp"
#include "surrogate.hpp"
#include <vector>
#include <cmath>
#include <cstdio>
#include <string>

namespace dsh {

// ---- 搜索空间常量（ddps_optimizer.py）----
static constexpr int N_FFE_TAPS = 5;
static constexpr int FFE_PRE = 2;
static constexpr int N_SIDE = N_FFE_TAPS - 1;          // 4
static constexpr int N_DIM = N_SIDE + 3;               // 7

static constexpr double FFE_BOUND = 0.3;
static constexpr double CTLE_GDC_MIN = 0.0;
static constexpr double CTLE_GDC_MAX = 12.0;
static constexpr double CTLE_GDC2_MIN = 0.0;
static constexpr double CTLE_GDC2_MAX = 4.0;
static constexpr double PEAK_SUM_LIMIT = 0.8;

static constexpr double MAX_DEGRADE_FRAC = 0.25;
static constexpr double TRUST_FFE = 0.10;
static constexpr double TRUST_CTLE = 3.0;
static constexpr double GAIN_TRUST = 0.30;
static constexpr double GD_LR = 0.05;
static constexpr double ALPHA_DECAY = 0.97;
static constexpr double TRUST_PATH_K = 2.0;
static constexpr double GROUP_GATE = 1e-3;
static constexpr double MIN_GAIN_DEX = 0.01;
static constexpr int SECANT_REFRESH_EVERY = 3;    // v8 割线周期性中心差分刷新间隔

// STEP_SPAN（满箱宽度，分组归一化步长）
inline std::vector<double> step_span() {
    return { 2.0 * TRUST_FFE, 2.0 * TRUST_FFE, 2.0 * TRUST_FFE, 2.0 * TRUST_FFE,
             2.0 * TRUST_CTLE, 2.0 * TRUST_CTLE, 2.0 * GAIN_TRUST };
}

inline double gain_from_u(double u) {
    return DRIVER_GAIN_NOMINAL * std::pow(10.0, u);
}
inline double u_from_gain(double gain) {
    return std::log10(std::max(gain, 1e-12) / DRIVER_GAIN_NOMINAL);
}

inline double sum_abs(const std::vector<double>& v) {
    double s = 0.0; for (double x : v) s += std::fabs(x); return s;
}
inline double norm2(const std::vector<double>& v) {
    double s = 0.0; for (double x : v) s += x * x; return std::sqrt(s);
}

// 4 旁瓣 -> 5-tap FFE（主抽头 = 1 - Σ|旁瓣|，超限时按比例缩放）
inline std::vector<double> construct_taps(const std::vector<double>& pre_post, int ffe_pre = 2, int n_taps = 5) {
    std::vector<double> pp = pre_post;
    double abs_sum = sum_abs(pp);
    if (abs_sum > PEAK_SUM_LIMIT) {
        double scale = PEAK_SUM_LIMIT / abs_sum;
        for (auto& v : pp) v *= scale;
    }
    std::vector<double> taps(n_taps, 0.0);
    for (int i = 0; i < ffe_pre; i++) taps[i] = pp[i];
    for (int i = ffe_pre + 1; i < n_taps; i++) taps[i] = pp[i - 1];
    taps[ffe_pre] = 1.0 - sum_abs(pp);
    return taps;
}

// 把当前搜索点的 CTLE / gain 写入 config（原地）
inline void apply_x_to_config(Config& cfg, double gdc, double gdc2, double gain) {
    cfg.set("tx.ctle_g_dc_db", gdc);
    cfg.set("tx.ctle_g_dc2_db", gdc2);
    cfg.set("channel.driver_gain", gain);
}

// 真实 BER 评估（多仿真种子 log10 均值）
inline std::pair<double, double> physical_eval(Config& cfg, const std::vector<double>& taps,
                                               double gdc, double gdc2, double gain,
                                               const S4P* s4p_tx, const S4P* s4p_rx,
                                               const std::vector<int>& sim_seeds) {
    apply_x_to_config(cfg, gdc, gdc2, gain);
    double sum_lb = 0.0;
    for (int s : sim_seeds) {
        cfg.set("system.seed", (double)s);
        cfg.set("channel.seed", (double)s + 7919.0);
        SimResult r = run_sim(cfg, taps, s4p_tx, s4p_rx);
        double ber = std::max(std::min(r.mlse_ber, 1.0), 1e-8);
        sum_lb += std::log10(ber);
    }
    double mean_lb = sum_lb / (double)sim_seeds.size();
    return { mean_lb, std::pow(10.0, mean_lb) };
}

inline double measure_drive_rms(Config& cfg, const std::vector<double>& taps, double gdc, double gdc2,
                                double gain, const S4P* s4p) {
    apply_x_to_config(cfg, gdc, gdc2, gain);
    auto [fir, drms] = extract_tx_features(cfg, s4p, taps, 7);
    return drms;
}

inline std::vector<double> probe_features(Config& cfg, const std::vector<double>& taps, double gdc, double gdc2,
                                          double gain, const S4P* s4p) {
    apply_x_to_config(cfg, gdc, gdc2, gain);
    auto [fir, drms] = extract_tx_features(cfg, s4p, taps, 7);
    std::vector<double> feat = fir; feat.push_back(drms);
    return feat;
}

inline double predict_a_probe(const WhiteBoxRidge& model_a, const std::vector<double>& probe) {
    return model_a.predict(model_a.standardize(probe));
}
inline double predict_b_params(const WhiteBoxRidge& model_b, const std::vector<double>& x_shape, double drive_rms) {
    std::vector<double> feat = x_shape; feat.push_back(drive_rms);
    return model_b.predict(model_b.standardize(feat));
}

// 7 维搜索盒（围绕 x0 + 全局边界收紧）
inline void bounds(const std::vector<double>& x0, std::vector<double>& lo, std::vector<double>& hi) {
    static const double bl[N_DIM] = { -FFE_BOUND, -FFE_BOUND, -FFE_BOUND, -FFE_BOUND,
                                      CTLE_GDC_MIN, CTLE_GDC2_MIN, GAIN_LOG10_MIN };
    static const double bh[N_DIM] = {  FFE_BOUND,  FFE_BOUND,  FFE_BOUND,  FFE_BOUND,
                                      CTLE_GDC_MAX, CTLE_GDC2_MAX, GAIN_LOG10_MAX };
    static const double rad[N_DIM] = { TRUST_FFE, TRUST_FFE, TRUST_FFE, TRUST_FFE,
                                       TRUST_CTLE, TRUST_CTLE, GAIN_TRUST };
    lo.resize(N_DIM); hi.resize(N_DIM);
    for (int i = 0; i < N_DIM; i++) {
        lo[i] = std::max(bl[i], x0[i] - rad[i]);
        hi[i] = std::min(bh[i], x0[i] + rad[i]);
    }
}

// 单个 ±ε 探针态的真实 BER 记账（与 Python probe_iter 逐一对应）
struct ProbeRecord {
    int param = 0, sign = 0;
    std::vector<double> x, taps;
    double gdc = 0, gdc2 = 0, gain = 0, gain_ratio = 0, u_gain = 0;
    double real_logber = 0, real_mlse = 0;
};

// 七维链式梯度（中心差分；record_probe_ber=true 时对每个 ±ε 态同步做真实 BER 记账）
inline std::pair<std::vector<double>, std::vector<ProbeRecord>>
grad_a_chain(const WhiteBoxRidge& model_a, Config& cfg, const std::vector<double>& x,
             int ffe_pre, const S4P* s4p_tx, const S4P* s4p_rx,
             const std::vector<int>& sim_seeds, double eps = 0.01, double eps_u = 0.05,
             bool record_probe_ber = false) {
    std::vector<double> g(N_DIM, 0.0);
    std::vector<double> taps = construct_taps({ x[0], x[1], x[2], x[3] }, ffe_pre);
    double gdc = x[N_SIDE], gdc2 = x[N_SIDE + 1];
    double gain = gain_from_u(x[N_SIDE + 2]);
    double eps_vec[N_DIM] = { eps, eps, eps, eps, eps * 10.0, eps * 10.0, eps_u };
    std::vector<ProbeRecord> probe_iter;

    for (int i = 0; i < N_DIM; i++) {
        std::vector<double> xp = x, xm = x;
        xp[i] += eps_vec[i]; xm[i] -= eps_vec[i];
        std::vector<double> taps_p, taps_m;
        double gdc_p, gdc_m, gdc2_p, gdc2_m, gain_p, gain_m;
        if (i < N_SIDE + 2) {
            taps_p = construct_taps({ xp[0], xp[1], xp[2], xp[3] }, ffe_pre);
            taps_m = construct_taps({ xm[0], xm[1], xm[2], xm[3] }, ffe_pre);
            gdc_p = xp[N_SIDE]; gdc2_p = xp[N_SIDE + 1];
            gdc_m = xm[N_SIDE]; gdc2_m = xm[N_SIDE + 1];
            gain_p = gain_m = gain;
        } else {
            taps_p = taps_m = taps;
            gdc_p = gdc_m = gdc; gdc2_p = gdc2_m = gdc2;
            gain_p = gain_from_u(xp[N_SIDE + 2]);
            gain_m = gain_from_u(xm[N_SIDE + 2]);
        }
        auto probe_p = probe_features(cfg, taps_p, gdc_p, gdc2_p, gain_p, s4p_tx);
        auto probe_m = probe_features(cfg, taps_m, gdc_m, gdc2_m, gain_m, s4p_tx);
        double ap = predict_a_probe(model_a, probe_p);
        double am = predict_a_probe(model_a, probe_m);
        g[i] = (ap - am) / (2.0 * eps_vec[i]);
        if (record_probe_ber) {
            auto [lb_p, ber_p] = physical_eval(cfg, taps_p, gdc_p, gdc2_p, gain_p, s4p_tx, s4p_rx, sim_seeds);
            auto [lb_m, ber_m] = physical_eval(cfg, taps_m, gdc_m, gdc2_m, gain_m, s4p_tx, s4p_rx, sim_seeds);
            ProbeRecord rp; rp.param = i; rp.sign = +1; rp.x = xp; rp.taps = taps_p;
            rp.gdc = gdc_p; rp.gdc2 = gdc2_p; rp.gain = gain_p;
            rp.gain_ratio = gain_p / DRIVER_GAIN_NOMINAL; rp.u_gain = xp[N_SIDE + 2];
            rp.real_logber = lb_p; rp.real_mlse = ber_p;
            probe_iter.push_back(rp);
            ProbeRecord rm; rm.param = i; rm.sign = -1; rm.x = xm; rm.taps = taps_m;
            rm.gdc = gdc_m; rm.gdc2 = gdc2_m; rm.gain = gain_m;
            rm.gain_ratio = gain_m / DRIVER_GAIN_NOMINAL; rm.u_gain = xm[N_SIDE + 2];
            rm.real_logber = lb_m; rm.real_mlse = ber_m;
            probe_iter.push_back(rm);
        }
    }
    return { g, probe_iter };
}

struct Stage2Step {
    int step = 0;
    std::vector<double> x, taps;
    double gdc = 0, gdc2 = 0, gain = 0, gain_ratio = 0, u_gain = 0, drive_rms = 0;
    double pred_a = 0, pred_b = 0, pred_b_ber = 0, allowed_ber = 0;
    double real_logber = 0, real_mlse = 0;
    double grad_norm = 0;
    std::vector<ProbeRecord> probes;
    std::string stop_reason;
};

// 在线调优：7 维链式梯度下降（真实 BER 仅记账，不回传决策）
inline std::vector<Stage2Step> stage2_descent(Config& cfg, const WhiteBoxRidge& model_a,
                                              const WhiteBoxRidge& model_b,
                                              const std::vector<double>& x0, int ffe_pre, int n_steps, double lr,
                                              const S4P* s4p_tx, const S4P* s4p_rx,
                                              const std::vector<int>& sim_seeds) {
    std::vector<double> x = x0;
    std::vector<double> tr_lo, tr_hi; bounds(x, tr_lo, tr_hi);
    std::vector<double> span = step_span();

    std::vector<double> taps0 = construct_taps({ x[0], x[1], x[2], x[3] }, ffe_pre);
    double gdc0 = x[N_SIDE], gdc2 = x[N_SIDE + 1];
    double gain0 = gain_from_u(x[N_SIDE + 2]);
    double rms0 = measure_drive_rms(cfg, taps0, gdc0, gdc2, gain0, s4p_tx);
    double seed_pred_b = predict_b_params(model_b, { x[0], x[1], x[2], x[3], x[4], x[5] }, rms0);
    double best_pred_b = seed_pred_b;
    double allowed_ber = std::pow(10.0, best_pred_b) * (1.0 + MAX_DEGRADE_FRAC);

    double rho = model_b.local_spacing;
    std::vector<double> mu6(model_b.mu.begin(), model_b.mu.begin() + 6);
    std::vector<double> sd6(model_b.sd.begin(), model_b.sd.begin() + 6);
    std::vector<double> z0(6);
    for (int i = 0; i < 6; i++) z0[i] = (x[i] - mu6[i]) / sd6[i];
    bool has_path = (rho > 0.0);
    double path_limit = TRUST_PATH_K * rho;

    std::vector<Stage2Step> trace;
    double pred_a_prev = 0.0;
    bool has_prev = false;

    for (int step = 0; step < n_steps; step++) {
        auto [g, probe_iter] = grad_a_chain(model_a, cfg, x, ffe_pre, s4p_tx, s4p_rx,
                                            sim_seeds, 0.01, 0.05, true);
        // 分组归一化方向
        std::vector<double> gs(N_DIM);
        for (int i = 0; i < N_DIM; i++) gs[i] = g[i] * span[i];
        const int group_slices[3][2] = { {0, N_SIDE}, {N_SIDE, N_SIDE + 2}, {N_SIDE + 2, N_SIDE + 3} };
        std::vector<double> direction(N_DIM, 0.0);
        std::vector<std::string> active_names;
        bool any_active = false;
        for (int gi = 0; gi < 3; gi++) {
            int a = group_slices[gi][0], b = group_slices[gi][1];
            double acc = 0.0;
            for (int i = a; i < b; i++) acc += gs[i] * gs[i];
            double nrm = std::sqrt(acc);
            if (nrm >= GROUP_GATE) {
                for (int i = a; i < b; i++) direction[i] = gs[i] / nrm;
                any_active = true;
            }
        }
        if (!any_active) {
            printf("[Stage2] stop: all group grads below gate at step %d\n", step);
            break;
        }

        // 回溯线搜索 + B 拦截
        double alpha = lr * std::pow(ALPHA_DECAY, (double)step);
        double alpha_k = alpha;
        std::vector<double> x_new;
        for (int it = 0; it < 20; it++) {
            std::vector<double> x_cand(N_DIM);
            for (int i = 0; i < N_DIM; i++) {
                double v = x[i] - alpha_k * span[i] * direction[i];
                x_cand[i] = std::min(std::max(v, tr_lo[i]), tr_hi[i]);
            }
            double diff = 0.0;
            for (int i = 0; i < N_DIM; i++) { double d = x_cand[i] - x[i]; diff += d * d; }
            if (std::sqrt(diff) < 1e-9) break;

            std::vector<double> taps_c = construct_taps({ x_cand[0], x_cand[1], x_cand[2], x_cand[3] }, ffe_pre);
            double gdc_c = x_cand[N_SIDE], gdc2_c = x_cand[N_SIDE + 1];
            double gain_c = gain_from_u(x_cand[N_SIDE + 2]);
            double rms_c = measure_drive_rms(cfg, taps_c, gdc_c, gdc2_c, gain_c, s4p_tx);
            double pb = predict_b_params(model_b, { x_cand[0], x_cand[1], x_cand[2], x_cand[3], x_cand[4], x_cand[5] }, rms_c);
            if (pb <= std::log10(allowed_ber)) { x_new = x_cand; break; }
            alpha_k *= 0.5;
        }
        if (x_new.empty()) {
            printf("[Stage2] stop: no candidate passes Model B veto at step %d\n", step);
            break;
        }

        // 轨迹信任域（shape 6 维）
        if (has_path) {
            std::vector<double> z_new(6);
            for (int i = 0; i < 6; i++) z_new[i] = (x_new[i] - mu6[i]) / sd6[i];
            double d = 0.0;
            for (int i = 0; i < 6; i++) { double e = z_new[i] - z0[i]; d += e * e; }
            if (std::sqrt(d) > path_limit) {
                printf("[Stage2] stop: path displacement exceeds trust region at step %d\n", step);
                break;
            }
        }

        std::vector<double> taps_new = construct_taps({ x_new[0], x_new[1], x_new[2], x_new[3] }, ffe_pre);
        double gdc_new = x_new[N_SIDE], gdc2_new = x_new[N_SIDE + 1];
        double gain_new = gain_from_u(x_new[N_SIDE + 2]);
        auto probe_new = probe_features(cfg, taps_new, gdc_new, gdc2_new, gain_new, s4p_tx);
        double pred_a = predict_a_probe(model_a, probe_new);
        double rms_actual = measure_drive_rms(cfg, taps_new, gdc_new, gdc2_new, gain_new, s4p_tx);
        double pred_b = predict_b_params(model_b, { x_new[0], x_new[1], x_new[2], x_new[3], x_new[4], x_new[5] }, rms_actual);

        // 真实 BER 记账（grad_a_chain 内已对 14 个 ±ε 状态做过实测；这里只做被接受点）
        auto [real_logber, real_mlse] = physical_eval(cfg, taps_new, gdc_new, gdc2_new, gain_new, s4p_tx, s4p_rx, sim_seeds);

        if (pred_b < best_pred_b) {
            best_pred_b = pred_b;
            allowed_ber = std::pow(10.0, best_pred_b) * (1.0 + MAX_DEGRADE_FRAC);
        }

        double grad_norm = norm2(g);

        Stage2Step rec;
        rec.step = step; rec.x = x_new; rec.taps = taps_new;
        rec.gdc = gdc_new; rec.gdc2 = gdc2_new; rec.gain = gain_new;
        rec.gain_ratio = gain_new / DRIVER_GAIN_NOMINAL; rec.u_gain = x_new[N_SIDE + 2];
        rec.drive_rms = rms_actual; rec.pred_a = pred_a; rec.pred_b = pred_b;
        rec.pred_b_ber = std::pow(10.0, pred_b); rec.allowed_ber = allowed_ber;
        rec.real_logber = real_logber; rec.real_mlse = real_mlse; rec.grad_norm = grad_norm;
        rec.probes = probe_iter;

        if (has_prev && (pred_a_prev - pred_a) < MIN_GAIN_DEX) {
            rec.stop_reason = "marginal_gain";
            trace.push_back(rec);
            printf("[Stage2] stop: marginal predicted gain (%+.4f < %g) at step %d\n",
                   pred_a_prev - pred_a, MIN_GAIN_DEX, step);
            break;
        }
        pred_a_prev = pred_a; has_prev = true;

        trace.push_back(rec);
        printf("[Stage2] gd %d/%d | ModelA %.2e | real %.2e | gain x%.3f | u_gain %+.3f | gDC %+.2f | gDC2 %+.2f\n",
               step + 1, n_steps, std::pow(10.0, pred_a), real_mlse, gain_new / DRIVER_GAIN_NOMINAL,
               x_new[N_SIDE + 2], gdc_new, gdc2_new);

        double step_diff = 0.0;
        for (int i = 0; i < N_DIM; i++) { double d = x_new[i] - x[i]; step_diff += d * d; }
        if (std::sqrt(step_diff) < 1e-6) break;
        x = x_new;
    }
    return trace;
}

// ---- v8 割线（secant / Broyden good）梯度维持 ----
// 与 stage2_descent 唯一区别：梯度不再每步 14 试探，而是第 0 步一次中心差分 + 割线更新。

inline bool secant_direction(const std::vector<double>& g, std::vector<double>& direction) {
    std::vector<double> span = step_span();
    std::vector<double> gs(N_DIM);
    for (int i = 0; i < N_DIM; i++) gs[i] = g[i] * span[i];
    const int group_slices[3][2] = { {0, N_SIDE}, {N_SIDE, N_SIDE + 2}, {N_SIDE + 2, N_SIDE + 3} };
    std::fill(direction.begin(), direction.end(), 0.0);
    bool any_active = false;
    for (int gi = 0; gi < 3; gi++) {
        int a = group_slices[gi][0], b = group_slices[gi][1];
        double acc = 0.0;
        for (int i = a; i < b; i++) acc += gs[i] * gs[i];
        double nrm = std::sqrt(acc);
        if (nrm >= GROUP_GATE) {
            for (int i = a; i < b; i++) direction[i] = gs[i] / nrm;
            any_active = true;
        }
    }
    return any_active;
}

inline bool secant_line_search(const WhiteBoxRidge& model_b, Config& cfg, const std::vector<double>& x,
                               const std::vector<double>& direction, const std::vector<double>& tr_lo,
                               const std::vector<double>& tr_hi, double alpha, int ffe_pre,
                               double allowed_ber, const S4P* s4p_tx, std::vector<double>& x_new_out) {
    std::vector<double> span = step_span();
    double alpha_k = alpha;
    for (int it = 0; it < 20; it++) {
        std::vector<double> x_cand(N_DIM);
        for (int i = 0; i < N_DIM; i++) {
            double v = x[i] - alpha_k * span[i] * direction[i];
            x_cand[i] = std::min(std::max(v, tr_lo[i]), tr_hi[i]);
        }
        double diff = 0.0;
        for (int i = 0; i < N_DIM; i++) { double d = x_cand[i] - x[i]; diff += d * d; }
        if (std::sqrt(diff) < 1e-9) return false;
        std::vector<double> taps_c = construct_taps({ x_cand[0], x_cand[1], x_cand[2], x_cand[3] }, ffe_pre);
        double gdc_c = x_cand[N_SIDE], gdc2_c = x_cand[N_SIDE + 1];
        double gain_c = gain_from_u(x_cand[N_SIDE + 2]);
        double rms_c = measure_drive_rms(cfg, taps_c, gdc_c, gdc2_c, gain_c, s4p_tx);
        double pb = predict_b_params(model_b, { x_cand[0], x_cand[1], x_cand[2], x_cand[3], x_cand[4], x_cand[5] }, rms_c);
        if (pb <= std::log10(allowed_ber)) { x_new_out = x_cand; return true; }
        alpha_k *= 0.5;
    }
    return false;
}

// v8 在线调优：一次性中心差分初始化 + 割线（Broyden good）更新梯度。
inline std::vector<Stage2Step> stage2_descent_secant(Config& cfg, const WhiteBoxRidge& model_a,
                                                     const WhiteBoxRidge& model_b,
                                                     const std::vector<double>& x0, int ffe_pre, int n_steps, double lr,
                                                     const S4P* s4p_tx, const S4P* s4p_rx,
                                                     const std::vector<int>& sim_seeds) {
    std::vector<double> x = x0;
    std::vector<double> tr_lo, tr_hi; bounds(x, tr_lo, tr_hi);
    std::vector<double> span = step_span();

    std::vector<double> taps0 = construct_taps({ x[0], x[1], x[2], x[3] }, ffe_pre);
    double gdc0 = x[N_SIDE], gdc2 = x[N_SIDE + 1];
    double gain0 = gain_from_u(x[N_SIDE + 2]);
    double rms0 = measure_drive_rms(cfg, taps0, gdc0, gdc2, gain0, s4p_tx);
    double seed_pred_b = predict_b_params(model_b, { x[0], x[1], x[2], x[3], x[4], x[5] }, rms0);
    double best_pred_b = seed_pred_b;
    double allowed_ber = std::pow(10.0, best_pred_b) * (1.0 + MAX_DEGRADE_FRAC);

    double rho = model_b.local_spacing;
    std::vector<double> mu6(model_b.mu.begin(), model_b.mu.begin() + 6);
    std::vector<double> sd6(model_b.sd.begin(), model_b.sd.begin() + 6);
    std::vector<double> z0(6);
    for (int i = 0; i < 6; i++) z0[i] = (x[i] - mu6[i]) / sd6[i];
    bool has_path = (rho > 0.0);
    double path_limit = TRUST_PATH_K * rho;

    // 一次性中心差分初始化梯度（唯一一轮 14 试探态）；种子点 A 预测（历史落点探针）。
    auto [g, probe_iter0] = grad_a_chain(model_a, cfg, x, ffe_pre, s4p_tx, s4p_rx, sim_seeds, 0.01, 0.05, true);
    auto probe0 = probe_features(cfg, taps0, gdc0, gdc2, gain0, s4p_tx);
    double a_prev = predict_a_probe(model_a, probe0);

    std::vector<Stage2Step> trace;
    for (int step = 0; step < n_steps; step++) {
        std::vector<ProbeRecord> step_probes = (step == 0) ? probe_iter0 : std::vector<ProbeRecord>();
        if (SECANT_REFRESH_EVERY > 0 && step > 0 && (step % SECANT_REFRESH_EVERY) == 0) {
            auto fr = grad_a_chain(model_a, cfg, x, ffe_pre, s4p_tx, s4p_rx, sim_seeds, 0.01, 0.05, true);
            g = fr.first; step_probes = fr.second;
        }

        std::vector<double> direction(N_DIM, 0.0);
        bool any_active = secant_direction(g, direction);
        if (!any_active) {
            printf("[Secant] stop: all group grads below gate at step %d\n", step);
            break;
        }

        double alpha = lr * std::pow(ALPHA_DECAY, (double)step);
        std::vector<double> x_new;
        bool found = secant_line_search(model_b, cfg, x, direction, tr_lo, tr_hi, alpha, ffe_pre, allowed_ber, s4p_tx, x_new);

        // 割线方向被 B 全部拒绝 -> 回退一次中心差分刷新 g，再重试
        if (!found) {
            auto fr = grad_a_chain(model_a, cfg, x, ffe_pre, s4p_tx, s4p_rx, sim_seeds, 0.01, 0.05, true);
            g = fr.first; step_probes = fr.second;
            any_active = secant_direction(g, direction);
            if (any_active) {
                found = secant_line_search(model_b, cfg, x, direction, tr_lo, tr_hi, alpha, ffe_pre, allowed_ber, s4p_tx, x_new);
            }
        }
        if (!found) {
            printf("[Secant] stop: no candidate passes Model B veto at step %d\n", step);
            break;
        }

        if (has_path) {
            std::vector<double> z_new(6);
            for (int i = 0; i < 6; i++) z_new[i] = (x_new[i] - mu6[i]) / sd6[i];
            double d = 0.0;
            for (int i = 0; i < 6; i++) { double e = z_new[i] - z0[i]; d += e * e; }
            if (std::sqrt(d) > path_limit) {
                printf("[Secant] stop: path displacement exceeds trust region at step %d\n", step);
                break;
            }
        }

        std::vector<double> taps_new = construct_taps({ x_new[0], x_new[1], x_new[2], x_new[3] }, ffe_pre);
        double gdc_new = x_new[N_SIDE], gdc2_new = x_new[N_SIDE + 1];
        double gain_new = gain_from_u(x_new[N_SIDE + 2]);
        auto probe_new = probe_features(cfg, taps_new, gdc_new, gdc2_new, gain_new, s4p_tx);
        double pred_a = predict_a_probe(model_a, probe_new);
        double rms_actual = measure_drive_rms(cfg, taps_new, gdc_new, gdc2_new, gain_new, s4p_tx);
        double pred_b = predict_b_params(model_b, { x_new[0], x_new[1], x_new[2], x_new[3], x_new[4], x_new[5] }, rms_actual);
        auto [real_logber, real_mlse] = physical_eval(cfg, taps_new, gdc_new, gdc2_new, gain_new, s4p_tx, s4p_rx, sim_seeds);

        // 割线更新：g += (ΔA - g^T Δx) · Δx / ‖Δx‖²
        double dA = pred_a - a_prev;
        double dx_norm2 = 0.0, g_dot_dx = 0.0;
        std::vector<double> dx(N_DIM);
        for (int i = 0; i < N_DIM; i++) {
            dx[i] = x_new[i] - x[i]; dx_norm2 += dx[i] * dx[i]; g_dot_dx += g[i] * dx[i];
        }
        if (dx_norm2 > 1e-18) {
            double c = (dA - g_dot_dx) / dx_norm2;
            for (int i = 0; i < N_DIM; i++) g[i] += c * dx[i];
        }

        if (pred_b < best_pred_b) {
            best_pred_b = pred_b;
            allowed_ber = std::pow(10.0, best_pred_b) * (1.0 + MAX_DEGRADE_FRAC);
        }

        double grad_norm = norm2(g);

        Stage2Step rec;
        rec.step = step; rec.x = x_new; rec.taps = taps_new;
        rec.gdc = gdc_new; rec.gdc2 = gdc2_new; rec.gain = gain_new;
        rec.gain_ratio = gain_new / DRIVER_GAIN_NOMINAL; rec.u_gain = x_new[N_SIDE + 2];
        rec.drive_rms = rms_actual; rec.pred_a = pred_a; rec.pred_b = pred_b;
        rec.pred_b_ber = std::pow(10.0, pred_b); rec.allowed_ber = allowed_ber;
        rec.real_logber = real_logber; rec.real_mlse = real_mlse; rec.grad_norm = grad_norm;
        rec.probes = step_probes;

        if (step > 0 && (a_prev - pred_a) < MIN_GAIN_DEX) {
            rec.stop_reason = "marginal_gain";
            trace.push_back(rec);
            printf("[Secant] stop: marginal predicted gain (%+.4f < %g) at step %d\n",
                   a_prev - pred_a, MIN_GAIN_DEX, step);
            break;
        }

        trace.push_back(rec);
        printf("[Secant] gd %d/%d | ModelA %.2e | real %.2e | gain x%.3f | u_gain %+.3f | gDC %+.2f | gDC2 %+.2f\n",
               step + 1, n_steps, std::pow(10.0, pred_a), real_mlse, gain_new / DRIVER_GAIN_NOMINAL,
               x_new[N_SIDE + 2], gdc_new, gdc2_new);

        double step_diff = 0.0;
        for (int i = 0; i < N_DIM; i++) { double d = x_new[i] - x[i]; step_diff += d * d; }
        if (std::sqrt(step_diff) < 1e-6) break;
        a_prev = pred_a;
        x = x_new;
    }
    return trace;
}

} // namespace dsh