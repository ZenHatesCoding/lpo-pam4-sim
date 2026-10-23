// optimizer.hpp — DDPS 在线调优（ddps_optimizer.py Stage-2 梯度下降 一比一复刻）。
//
// 搜索空间 8 维：[5 个 Tx FFE 抽头, gDC, gDC2, u_gain]（抽头维无边界）。
// 形状维（5 抽头 + gDC + gDC2）的梯度刷新方式由 grad_mode 决定：
//   full   每步全量中心差分（7 维 × ±ε = 14 个微扰态/步）
//   rotate 每步轮转刷新 k 个维（2k 个微扰态/步），其余维沿用上一轮测到的值
//   secant 只在第 0 步测一轮，此后 Broyden 秩-1 更新维持（此后 0 微扰态/步）
// 三种模式都从同一个"第 0 步全量梯度"出发，gain 维始终走解析梯度（0 微扰态）。
#pragma once

#include "physim.hpp"
#include "probe.hpp"
#include "surrogate.hpp"
#include <vector>
#include <cmath>
#include <cstdio>
#include <string>
#include <algorithm>

namespace dsh {

// ---- 搜索空间常量（ddps_optimizer.py）----
static constexpr int N_FFE_TAPS = 5;
static constexpr int FFE_PRE = 2;
static constexpr int N_SIDE = N_FFE_TAPS - 1;          // 4：Stage-1 采样口径的旁瓣个数（冻结）
static constexpr int N_TAP = N_FFE_TAPS;               // 5：Stage-2 搜索抽头维（全自由、无边界）
static constexpr int N_SHAPE = N_TAP + 2;              // 7：5 抽头 + gDC + gDC2
static constexpr int N_DIM = N_SHAPE + 1;              // 8：+ u_gain

static constexpr double CTLE_GDC_MIN = 0.0;
static constexpr double CTLE_GDC_MAX = 12.0;
static constexpr double CTLE_GDC2_MIN = 0.0;
static constexpr double CTLE_GDC2_MAX = 4.0;
static constexpr double PEAK_SUM_LIMIT = 0.8;          // 仅 Stage-1 采样口径（construct_taps）

static constexpr double TRUST_FFE = 0.10;
static constexpr double TRUST_CTLE = 3.0;
static constexpr double GAIN_TRUST = 0.30;
static constexpr double GD_LR = 0.05;
static constexpr double ALPHA_DECAY = 0.97;
static constexpr double GROUP_GATE = 1e-3;
static constexpr double MIN_GAIN_DEX = 0.01;           // direct 参照方案的边际停止门控
static constexpr int ROTATE_K = 2;                     // rotate 模式每步刷新的形状维个数

static constexpr double INF_BOUND = 1e300;             // 抽头无边界（用有限大数代替 ±inf 便于 clamp）

// STEP_SPAN（各维步长尺度 / 满箱宽度，分组归一化步长）
inline std::vector<double> step_span() {
    return { 2.0 * TRUST_FFE, 2.0 * TRUST_FFE, 2.0 * TRUST_FFE, 2.0 * TRUST_FFE, 2.0 * TRUST_FFE,
             2.0 * TRUST_CTLE, 2.0 * TRUST_CTLE, 2.0 * GAIN_TRUST };
}

// 中心差分步长（抽头 / CTLE dB / gain dex）
inline std::vector<double> eps_vec() {
    return { 0.01, 0.01, 0.01, 0.01, 0.01, 0.1, 0.1, 0.05 };
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

// Stage-2 搜索向量 -> 5 个 Tx FFE 抽头（全自由、无派生、无边界）
inline std::vector<double> taps_of(const std::vector<double>& x) {
    return std::vector<double>(x.begin(), x.begin() + N_TAP);
}

// Stage-1（数据集采样，冻结）口径：4 旁瓣 -> 5-tap FFE（主抽头 = 1 - Σ|旁瓣|，超限缩放）
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

// gain 维解析梯度 ∂A/∂u_gain = ln(10)·Σ_j (∂A/∂feat_j)·feat_j。
// Model A 的 8 维探针 = [绝对标定 7-tap FIR, drive_rms]，driver_gain 是 Tx 链最后的标量乘子，
// 故全部 8 个特征严格 ∝ gain；gain = g0·10^u => ∂feat_j/∂u = ln(10)·feat_j。零微扰态。
inline double analytic_gain_grad(const WhiteBoxRidge& model_a, const std::vector<double>& probe) {
    std::vector<double> xn = model_a.standardize(probe);
    std::vector<double> gn = model_a.grad(xn);          // ∂pred/∂xn
    double s = 0.0;
    for (size_t j = 0; j < probe.size(); j++) {
        double g_raw = gn[j] / model_a.sd[j];           // ∂pred/∂raw_feat
        s += g_raw * probe[j];
    }
    return std::log(10.0) * s;
}

// 搜索边界：抽头维无边界；只有 CTLE / gain 用各自物理量程。
inline void bounds(std::vector<double>& lo, std::vector<double>& hi) {
    static const double bl[N_DIM] = { -INF_BOUND, -INF_BOUND, -INF_BOUND, -INF_BOUND, -INF_BOUND,
                                      CTLE_GDC_MIN, CTLE_GDC2_MIN, GAIN_LOG10_MIN };
    static const double bh[N_DIM] = {  INF_BOUND,  INF_BOUND,  INF_BOUND,  INF_BOUND,  INF_BOUND,
                                      CTLE_GDC_MAX, CTLE_GDC2_MAX, GAIN_LOG10_MAX };
    lo.assign(bl, bl + N_DIM);
    hi.assign(bh, bh + N_DIM);
}

// 单个 ±ε 探针态的真实 BER 记账（与 Python probe_iter 逐一对应）
struct ProbeRecord {
    int param = 0, sign = 0;
    std::vector<double> x, taps;
    double gdc = 0, gdc2 = 0, gain = 0, gain_ratio = 0, u_gain = 0;
    double real_logber = 0, real_mlse = 0;
};

// 链式梯度（中心差分；record_probe_ber=true 时对每个 ±ε 态同步做真实 BER 记账）。
// dims 为空 = 算全部形状 7 维；否则只算给出的维（其余维 g=0），供 rotate 模式轮转刷新。
inline std::pair<std::vector<double>, std::vector<ProbeRecord>>
grad_a_chain(const WhiteBoxRidge& model_a, Config& cfg, const std::vector<double>& x,
             const S4P* s4p_tx, const S4P* s4p_rx,
             const std::vector<int>& sim_seeds, bool record_probe_ber,
             const std::vector<int>& dims) {
    std::vector<double> g(N_DIM, 0.0);
    std::vector<double> eps = eps_vec();
    double gdc = x[N_TAP], gdc2 = x[N_TAP + 1];
    double gain = gain_from_u(x[N_TAP + 2]);
    std::vector<ProbeRecord> probe_iter;

    std::vector<int> idx = dims;
    if (idx.empty()) for (int i = 0; i < N_SHAPE; i++) idx.push_back(i);

    for (int i : idx) {
        std::vector<double> xp = x, xm = x;
        xp[i] += eps[i]; xm[i] -= eps[i];
        std::vector<double> taps_p, taps_m;
        double gdc_p, gdc_m, gdc2_p, gdc2_m, gain_p, gain_m;
        if (i < N_TAP) {
            taps_p = taps_of(xp); taps_m = taps_of(xm);
            gdc_p = gdc_m = gdc;
            gdc2_p = gdc2_m = gdc2;
            gain_p = gain_m = gain;
        } else {
            taps_p = taps_m = taps_of(x);
            gdc_p = xp[N_TAP]; gdc2_p = xp[N_TAP + 1];
            gdc_m = xm[N_TAP]; gdc2_m = xm[N_TAP + 1];
            gain_p = gain_m = gain;
        }
        auto probe_p = probe_features(cfg, taps_p, gdc_p, gdc2_p, gain_p, s4p_tx);
        auto probe_m = probe_features(cfg, taps_m, gdc_m, gdc2_m, gain_m, s4p_tx);
        double ap = predict_a_probe(model_a, probe_p);
        double am = predict_a_probe(model_a, probe_m);
        g[i] = (ap - am) / (2.0 * eps[i]);
        if (record_probe_ber) {
            auto [lb_p, ber_p] = physical_eval(cfg, taps_p, gdc_p, gdc2_p, gain_p, s4p_tx, s4p_rx, sim_seeds);
            auto [lb_m, ber_m] = physical_eval(cfg, taps_m, gdc_m, gdc2_m, gain_m, s4p_tx, s4p_rx, sim_seeds);
            ProbeRecord rp; rp.param = i; rp.sign = +1; rp.x = xp; rp.taps = taps_p;
            rp.gdc = gdc_p; rp.gdc2 = gdc2_p; rp.gain = gain_p;
            rp.gain_ratio = gain_p / DRIVER_GAIN_NOMINAL; rp.u_gain = xp[N_TAP + 2];
            rp.real_logber = lb_p; rp.real_mlse = ber_p;
            probe_iter.push_back(rp);
            ProbeRecord rm; rm.param = i; rm.sign = -1; rm.x = xm; rm.taps = taps_m;
            rm.gdc = gdc_m; rm.gdc2 = gdc2_m; rm.gain = gain_m;
            rm.gain_ratio = gain_m / DRIVER_GAIN_NOMINAL; rm.u_gain = xm[N_TAP + 2];
            rm.real_logber = lb_m; rm.real_mlse = ber_m;
            probe_iter.push_back(rm);
        }
    }
    return { g, probe_iter };
}

struct Stage2Step {
    int step = 0;
    std::vector<double> x, taps, grad;
    std::vector<int> refreshed;
    double gdc = 0, gdc2 = 0, gain = 0, gain_ratio = 0, u_gain = 0, drive_rms = 0;
    double pred_a = 0, pred_b = 0, pred_b_ber = 0, allowed_ber = 0;
    double real_logber = 0, real_mlse = 0;
    double grad_norm = 0;
    int n_probe_states = 0;
    std::vector<ProbeRecord> probes;
    std::string stop_reason;
};

// 组归一化方向（三组各自单位化）。返回是否至少有一组过门控。
inline bool group_direction(const std::vector<double>& g, std::vector<double>& direction) {
    std::vector<double> span = step_span();
    std::vector<double> gs(N_DIM);
    for (int i = 0; i < N_DIM; i++) gs[i] = g[i] * span[i];
    const int group_slices[3][2] = { {0, N_TAP}, {N_TAP, N_TAP + 2}, {N_TAP + 2, N_TAP + 3} };
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

// 在线寻优：8 维链式梯度下降（在线决策只用 Model A；无 Model B / 红线 / 候选否决）。
// grad_mode: "full" / "rotate" / "secant"，语义见文件头。固定 n_steps 步、不早停。
inline std::vector<Stage2Step> stage2_descent_proxy(Config& cfg, const WhiteBoxRidge& model_a,
                                                    const std::vector<double>& x0, int n_steps, double lr,
                                                    const std::string& grad_mode, int rotate_k,
                                                    const S4P* s4p_tx, const S4P* s4p_rx,
                                                    const std::vector<int>& sim_seeds) {
    std::vector<double> x = x0;
    std::vector<double> tr_lo, tr_hi; bounds(tr_lo, tr_hi);
    std::vector<double> span = step_span();

    std::vector<double> taps0 = taps_of(x);
    double gdc0 = x[N_TAP], gdc2_0 = x[N_TAP + 1];
    double gain0 = gain_from_u(x[N_TAP + 2]);
    auto probe0 = probe_features(cfg, taps0, gdc0, gdc2_0, gain0, s4p_tx);
    double a_prev = predict_a_probe(model_a, probe0);

    std::vector<double> g(N_DIM, 0.0);
    g[N_TAP + 2] = analytic_gain_grad(model_a, probe0);

    std::vector<Stage2Step> trace;
    for (int step = 0; step < n_steps; step++) {
        std::vector<ProbeRecord> step_probes;
        std::vector<int> refreshed;
        if (step == 0) {
            for (int i = 0; i < N_SHAPE; i++) refreshed.push_back(i);
            auto r = grad_a_chain(model_a, cfg, x, s4p_tx, s4p_rx, sim_seeds, true, refreshed);
            for (int i = 0; i < N_SHAPE; i++) g[i] = r.first[i];   // 只覆盖形状维，gain 维保留解析梯度
            step_probes = r.second;
        } else if (grad_mode == "full") {
            for (int i = 0; i < N_SHAPE; i++) refreshed.push_back(i);
            auto r = grad_a_chain(model_a, cfg, x, s4p_tx, s4p_rx, sim_seeds, true, refreshed);
            for (int i = 0; i < N_SHAPE; i++) g[i] = r.first[i];
            step_probes = r.second;
        } else if (grad_mode == "rotate") {
            for (int j = 0; j < rotate_k; j++) refreshed.push_back((step * rotate_k + j) % N_SHAPE);
            auto r = grad_a_chain(model_a, cfg, x, s4p_tx, s4p_rx, sim_seeds, true, refreshed);
            for (int i : refreshed) g[i] = r.first[i];
            step_probes = r.second;
        } else {  // secant：第 0 步之后不再为梯度制造任何微扰态
            refreshed.clear();
        }

        std::vector<double> direction(N_DIM, 0.0);
        bool any_active = group_direction(g, direction);
        if (!any_active) {
            printf("[Stage2] stop: all group grads below gate at step %d\n", step);
            break;
        }

        double alpha = lr * std::pow(ALPHA_DECAY, (double)step);
        std::vector<double> x_new(N_DIM);
        for (int i = 0; i < N_DIM; i++) {
            double v = x[i] - alpha * span[i] * direction[i];
            x_new[i] = std::min(std::max(v, tr_lo[i]), tr_hi[i]);
        }
        double diff0 = 0.0;
        for (int i = 0; i < N_DIM; i++) { double d = x_new[i] - x[i]; diff0 += d * d; }
        if (std::sqrt(diff0) < 1e-12) {
            printf("[Stage2] stop: zero step displacement at step %d\n", step);
            break;
        }

        std::vector<double> taps_new = taps_of(x_new);
        double gdc_new = x_new[N_TAP], gdc2_new = x_new[N_TAP + 1];
        double gain_new = gain_from_u(x_new[N_TAP + 2]);
        auto probe_new = probe_features(cfg, taps_new, gdc_new, gdc2_new, gain_new, s4p_tx);
        double pred_a = predict_a_probe(model_a, probe_new);
        double rms_actual = measure_drive_rms(cfg, taps_new, gdc_new, gdc2_new, gain_new, s4p_tx);
        auto [real_logber, real_mlse] = physical_eval(cfg, taps_new, gdc_new, gdc2_new, gain_new,
                                                      s4p_tx, s4p_rx, sim_seeds);

        // gain 维：解析梯度（每步现算，零微扰态、永不陈旧）
        g[N_TAP + 2] = analytic_gain_grad(model_a, probe_new);
        // secant：Broyden 秩-1 更新（只用上一步落点的预测差；剔除 gain 贡献）
        if (grad_mode == "secant") {
            double dA = pred_a - a_prev;
            double dA_shape = dA - g[N_TAP + 2] * (x_new[N_TAP + 2] - x[N_TAP + 2]);
            double dx_norm2 = 0.0, g_dot_dx = 0.0;
            for (int i = 0; i < N_SHAPE; i++) {
                double d = x_new[i] - x[i];
                dx_norm2 += d * d; g_dot_dx += g[i] * d;
            }
            if (dx_norm2 > 1e-18) {
                double c = (dA_shape - g_dot_dx) / dx_norm2;
                for (int i = 0; i < N_SHAPE; i++) g[i] += c * (x_new[i] - x[i]);
            }
        }

        Stage2Step rec;
        rec.step = step; rec.x = x_new; rec.taps = taps_new;
        rec.gdc = gdc_new; rec.gdc2 = gdc2_new; rec.gain = gain_new;
        rec.gain_ratio = gain_new / DRIVER_GAIN_NOMINAL; rec.u_gain = x_new[N_TAP + 2];
        rec.drive_rms = rms_actual; rec.pred_a = pred_a; rec.pred_b = 0.0;
        rec.pred_b_ber = 0.0; rec.allowed_ber = 0.0;
        rec.real_logber = real_logber; rec.real_mlse = real_mlse; rec.grad_norm = norm2(g);
        rec.grad = g; rec.refreshed = refreshed;
        rec.n_probe_states = (int)step_probes.size();
        rec.probes = step_probes;
        trace.push_back(rec);
        printf("[Stage2/%s] gd %d/%d | ModelA %.2e | real %.2e | gain x%.3f | u_gain %+.3f "
               "| gDC %+.2f | gDC2 %+.2f | probes %d\n",
               grad_mode.c_str(), step + 1, n_steps, std::pow(10.0, pred_a), real_mlse,
               gain_new / DRIVER_GAIN_NOMINAL, x_new[N_TAP + 2], gdc_new, gdc2_new,
               (int)step_probes.size());

        double step_diff = 0.0;
        for (int i = 0; i < N_DIM; i++) { double d = x_new[i] - x[i]; step_diff += d * d; }
        if (std::sqrt(step_diff) < 1e-9) break;
        a_prev = pred_a;
        x = x_new;
    }
    return trace;
}

// ---- direct：端到端 BER 直接梯度下降（有回传通道时的参照，不用 Model A）----
// 与代理档同一套下降机制（步长尺度 / 组归一化步长 / 步长衰减 / 组门控）；
// 差别：目标 = 真实 log10(BER)，8 维一律靠真实 BER 中心差分（无解析 gain 梯度可用——
// 那依赖 Model A 的探针比例性）；8 维的刷新方式由 grad_mode 决定，语义与代理档逐字一致：
//   full   每步 8 维全部中心差分（16 个真实评估/步）
//   rotate 第 0 步 8 维全量，此后每步轮转刷新 rotate_k 个维（2·rotate_k 个/步）
//   secant 只第 0 步测一轮（16 个），此后 Broyden 秩一修正（0 个/步）
// direct 档保留边际停止（口径 = 真实改善 dex，step > 0 才判）。
// trace 的 pred_a 列记录当前落点目标值（= real_logber）；pred_b/allowed 恒 0。

inline std::vector<int> all_dims() {
    std::vector<int> v(N_DIM);
    for (int i = 0; i < N_DIM; i++) v[i] = i;
    return v;
}

inline std::pair<std::vector<double>, std::vector<ProbeRecord>>
grad_direct_chain(Config& cfg, const std::vector<double>& x,
                  const S4P* s4p_tx, const S4P* s4p_rx,
                  const std::vector<int>& sim_seeds, const std::vector<int>& dims) {
    std::vector<double> g(N_DIM, 0.0);
    std::vector<double> eps = eps_vec();
    double gain = gain_from_u(x[N_TAP + 2]);
    std::vector<ProbeRecord> probe_iter;

    for (int i : dims) {
        std::vector<double> xp = x, xm = x;
        xp[i] += eps[i]; xm[i] -= eps[i];
        std::vector<double> taps_p, taps_m;
        double gdc_p, gdc_m, gdc2_p, gdc2_m, gain_p, gain_m;
        if (i < N_TAP) {
            taps_p = taps_of(xp); taps_m = taps_of(xm);
            gdc_p = xp[N_TAP]; gdc2_p = xp[N_TAP + 1];
            gdc_m = xm[N_TAP]; gdc2_m = xm[N_TAP + 1];
            gain_p = gain_m = gain;
        } else {
            // 非抽头维：用扰动后的坐标（i=5/6/7 分别落在 gDC/gDC2/u_gain 上），与 Python 一致
            taps_p = taps_m = taps_of(x);
            gdc_p = xp[N_TAP]; gdc2_p = xp[N_TAP + 1];
            gdc_m = xm[N_TAP]; gdc2_m = xm[N_TAP + 1];
            gain_p = gain_from_u(xp[N_TAP + 2]);
            gain_m = gain_from_u(xm[N_TAP + 2]);
        }
        // direct：目标就是端到端真实 BER，±ε 态的实测既供梯度也记账（与 Python 一致）
        auto [lb_p, ber_p] = physical_eval(cfg, taps_p, gdc_p, gdc2_p, gain_p, s4p_tx, s4p_rx, sim_seeds);
        auto [lb_m, ber_m] = physical_eval(cfg, taps_m, gdc_m, gdc2_m, gain_m, s4p_tx, s4p_rx, sim_seeds);
        g[i] = (lb_p - lb_m) / (2.0 * eps[i]);
        ProbeRecord rp; rp.param = i; rp.sign = +1; rp.x = xp; rp.taps = taps_p;
        rp.gdc = gdc_p; rp.gdc2 = gdc2_p; rp.gain = gain_p;
        rp.gain_ratio = gain_p / DRIVER_GAIN_NOMINAL; rp.u_gain = xp[N_TAP + 2];
        rp.real_logber = lb_p; rp.real_mlse = ber_p;
        probe_iter.push_back(rp);
        ProbeRecord rm; rm.param = i; rm.sign = -1; rm.x = xm; rm.taps = taps_m;
        rm.gdc = gdc_m; rm.gdc2 = gdc2_m; rm.gain = gain_m;
        rm.gain_ratio = gain_m / DRIVER_GAIN_NOMINAL; rm.u_gain = xm[N_TAP + 2];
        rm.real_logber = lb_m; rm.real_mlse = ber_m;
        probe_iter.push_back(rm);
    }
    return { g, probe_iter };
}

inline std::vector<Stage2Step> stage2_descent_direct(Config& cfg, const std::vector<double>& x0,
                                                     int n_steps, double lr, double f0,
                                                     const S4P* s4p_tx, const S4P* s4p_rx,
                                                     const std::vector<int>& sim_seeds,
                                                     const std::string& grad_mode,
                                                     int rotate_k) {
    std::vector<double> x = x0;
    std::vector<double> tr_lo, tr_hi; bounds(tr_lo, tr_hi);
    std::vector<double> span = step_span();
    double f_prev = f0;   // 起点目标值（由调用方传入，避免重复评估）

    // 第 0 步：8 维中心差分初始化（唯一一轮 16 个 ±ε 试探态，全真实评估）
    auto [g, probe_iter0] = grad_direct_chain(cfg, x, s4p_tx, s4p_rx, sim_seeds, all_dims());

    std::vector<Stage2Step> trace;
    for (int step = 0; step < n_steps; step++) {
        // 每种模式的在线代价都写在这里：step 0 之后的刷新方式由 grad_mode 决定
        std::vector<ProbeRecord> step_probes;
        std::vector<int> refreshed;
        if (step == 0) {
            step_probes = probe_iter0;
            refreshed = all_dims();
        } else if (grad_mode == "full") {
            auto r = grad_direct_chain(cfg, x, s4p_tx, s4p_rx, sim_seeds, all_dims());
            g = r.first; step_probes = r.second; refreshed = all_dims();
        } else if (grad_mode == "rotate") {
            for (int j = 0; j < rotate_k; j++) refreshed.push_back((step * rotate_k + j) % N_DIM);
            auto r = grad_direct_chain(cfg, x, s4p_tx, s4p_rx, sim_seeds, refreshed);
            for (int j : refreshed) g[j] = r.first[j];
            step_probes = r.second;
        } else {  // secant：第 0 步之后不再为梯度制造任何微扰态
            step_probes = std::vector<ProbeRecord>();
            refreshed.clear();
        }

        std::vector<double> direction(N_DIM, 0.0);
        bool any_active = group_direction(g, direction);
        if (!any_active) {
            printf("[Direct] stop: all group grads below gate at step %d\n", step);
            break;
        }

        double alpha = lr * std::pow(ALPHA_DECAY, (double)step);
        std::vector<double> x_new(N_DIM);
        for (int i = 0; i < N_DIM; i++) {
            double v = x[i] - alpha * span[i] * direction[i];
            x_new[i] = std::min(std::max(v, tr_lo[i]), tr_hi[i]);
        }
        double diff0 = 0.0;
        for (int i = 0; i < N_DIM; i++) { double d = x_new[i] - x[i]; diff0 += d * d; }
        if (std::sqrt(diff0) < 1e-12) break;

        std::vector<double> taps_new = taps_of(x_new);
        double gdc_new = x_new[N_TAP], gdc2_new = x_new[N_TAP + 1];
        double gain_new = gain_from_u(x_new[N_TAP + 2]);
        double rms_actual = measure_drive_rms(cfg, taps_new, gdc_new, gdc2_new, gain_new, s4p_tx);
        auto [f_new, real_mlse] = physical_eval(cfg, taps_new, gdc_new, gdc2_new, gain_new,
                                                s4p_tx, s4p_rx, sim_seeds);

        // secant：Broyden 割线更新（全 8 维；用真实 Δlog10(BER)，零微扰态）
        if (grad_mode == "secant") {
            double dx_norm2 = 0.0, g_dot_dx = 0.0;
            for (int i = 0; i < N_DIM; i++) {
                double d = x_new[i] - x[i];
                dx_norm2 += d * d; g_dot_dx += g[i] * d;
            }
            if (dx_norm2 > 1e-18) {
                double c = ((f_new - f_prev) - g_dot_dx) / dx_norm2;
                for (int i = 0; i < N_DIM; i++) g[i] += c * (x_new[i] - x[i]);
            }
        }

        Stage2Step rec;
        rec.step = step; rec.x = x_new; rec.taps = taps_new;
        rec.gdc = gdc_new; rec.gdc2 = gdc2_new; rec.gain = gain_new;
        rec.gain_ratio = gain_new / DRIVER_GAIN_NOMINAL; rec.u_gain = x_new[N_TAP + 2];
        rec.drive_rms = rms_actual;
        rec.pred_a = f_new; rec.pred_b = 0.0; rec.pred_b_ber = 0.0; rec.allowed_ber = 0.0;
        rec.real_logber = f_new; rec.real_mlse = real_mlse;
        rec.grad_norm = norm2(g);
        rec.grad = g; rec.refreshed = refreshed;
        rec.n_probe_states = (int)step_probes.size();
        rec.probes = step_probes;

        // 边际改善门控（step 0 不判，避免首步误停；口径 = 真实改善 dex）
        if (step > 0 && (f_prev - f_new) < MIN_GAIN_DEX) {
            rec.stop_reason = "marginal_gain";
            trace.push_back(rec);
            printf("[Direct] stop: marginal real gain (%+.4f < %g) at step %d\n",
                   f_prev - f_new, MIN_GAIN_DEX, step);
            break;
        }

        trace.push_back(rec);
        printf("[Direct] gd %d/%d | real %.2e | gain x%.3f | u_gain %+.3f | gDC %+.2f | gDC2 %+.2f\n",
               step + 1, n_steps, real_mlse, gain_new / DRIVER_GAIN_NOMINAL,
               x_new[N_TAP + 2], gdc_new, gdc2_new);

        double step_diff = 0.0;
        for (int i = 0; i < N_DIM; i++) { double d = x_new[i] - x[i]; step_diff += d * d; }
        if (std::sqrt(step_diff) < 1e-9) break;
        f_prev = f_new;
        x = x_new;
    }
    return trace;
}

} // namespace dsh
