// physim.hpp — LPO PAM4 链路物理仿真，一比一复刻 Python 参考实现
// (main.run_sim + channel_imdd + tx_dsp + rx_dsp + mlse_burg + metrics)。
#pragma once

#include <vector>
#include <complex>
#include <cmath>
#include <string>
#include <unordered_map>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <algorithm>

#include "rng.hpp"
#include "fft.hpp"
#include "filter.hpp"
#include "s4p.hpp"

namespace dsh {

// ---------------------------------------------------------------------------
// Config：key = value 文本（key 用点分 section.param），类型化读取。
// ---------------------------------------------------------------------------
struct Config {
    std::unordered_map<std::string, std::string> kv;
    void load(const std::string& path) {
        std::ifstream f(path);
        std::string line;
        while (std::getline(f, line)) {
            while (!line.empty() && (line.back() == '\r' || line.back() == ' ' || line.back() == '\t')) line.pop_back();
            if (line.empty() || line[0] == '#') continue;
            size_t eq = line.find('=');
            if (eq == std::string::npos) continue;
            std::string k = line.substr(0, eq), v = line.substr(eq + 1);
            while (!k.empty() && k.back() == ' ') k.pop_back();
            while (!v.empty() && v.front() == ' ') v.erase(v.begin());
            kv[k] = v;
        }
    }
    bool has(const std::string& k) const { return kv.count(k) != 0; }
    double d(const std::string& k, double def) const {
        auto it = kv.find(k);
        if (it == kv.end()) return def;
        std::string v = it->second;
        std::transform(v.begin(), v.end(), v.begin(), ::tolower);
        if (v == "true") return 1.0;
        if (v == "false") return 0.0;
        try { return std::stod(it->second); } catch (...) { return def; }
    }
    int i(const std::string& k, int def) const {
        auto it = kv.find(k);
        if (it == kv.end()) return def;
        std::string v = it->second;
        std::transform(v.begin(), v.end(), v.begin(), ::tolower);
        if (v == "true") return 1;
        if (v == "false") return 0;
        try { return (int)std::stod(it->second); } catch (...) { return def; }
    }
    bool b(const std::string& k, bool def) const {
        auto it = kv.find(k);
        if (it == kv.end()) return def;
        std::string v = it->second;
        std::transform(v.begin(), v.end(), v.begin(), ::tolower);
        return !(v == "false" || v == "0" || v == "no" || v == "off" || v == "");
    }
    std::string s(const std::string& k, const std::string& def) const {
        auto it = kv.find(k);
        return it == kv.end() ? def : it->second;
    }
    void set(const std::string& k, double v) {
        // 注意：不能用 std::to_string（只保留 6 位有效数字），会截断调优写入的
        // gdc/gdc2/gain 等高精度值。用 17 位有效数字保证与 Python 双精度往返一致。
        std::ostringstream ss;
        ss << std::setprecision(17) << v;
        kv[k] = ss.str();
    }
};

// ---------------------------------------------------------------------------
// DDPS 标定常量（channel_imdd.py，与 Python 位一致）
// ---------------------------------------------------------------------------
static constexpr double DRIVER_VPP_NOMINAL = 0.617;
static constexpr double PAM4_RMS_FACTOR = 0.3726;
static constexpr double DRIVER_GAIN_NOMINAL = 0.3399;
static constexpr double DRIVE_RMS_NOMINAL = DRIVER_VPP_NOMINAL * PAM4_RMS_FACTOR;  // 0.2298942
static constexpr double RX_AGC_RMS = std::sqrt(5.0);
static constexpr double GAIN_LOG10_MIN = -0.52;
static constexpr double GAIN_LOG10_MAX = 0.60;

// ---------------------------------------------------------------------------
// 卷积（np.convolve 'full'/'same' 语义）
// ---------------------------------------------------------------------------
inline std::vector<double> convolve_full(const std::vector<double>& x, const std::vector<double>& w) {
    int n = (int)x.size(), m = (int)w.size();
    std::vector<double> out(n + m - 1, 0.0);
    for (int k = 0; k < n + m - 1; k++) {
        double s = 0.0;
        int i0 = std::max(0, k - m + 1), i1 = std::min(k, n - 1);
        for (int i = i0; i <= i1; i++) s += x[i] * w[k - i];
        out[k] = s;
    }
    return out;
}
inline std::vector<double> convolve_same(const std::vector<double>& x, const std::vector<double>& w) {
    auto full = convolve_full(x, w);
    int n = (int)x.size(), m = (int)w.size();
    if (m <= n) {
        int start = (m - 1) / 2;
        return std::vector<double>(full.begin() + start, full.begin() + start + n);
    }
    int start = (n - 1) / 2;
    return std::vector<double>(full.begin() + start, full.begin() + start + m);
}

// np.correlate(a, v, 'full')（实数）：c[j] = Σ_n a[n + j - (M-1)] * v[n]
inline std::vector<double> correlate_full(const std::vector<double>& a, const std::vector<double>& v) {
    int N = (int)a.size(), M = (int)v.size();
    std::vector<double> c(N + M - 1, 0.0);
    for (int j = 0; j < N + M - 1; j++) {
        double s = 0.0;
        int n0 = std::max(0, M - 1 - j), n1 = std::min(M - 1, N + M - 2 - j);
        for (int n = n0; n <= n1; n++) {
            s += a[n + j - (M - 1)] * v[n];
        }
        c[j] = s;
    }
    return c;
}
inline int argmax(const std::vector<double>& v) {
    int bi = 0;
    for (int i = 1; i < (int)v.size(); i++) if (v[i] > v[bi]) bi = i;
    return bi;
}

// 复数信号低通（scipy lfilter 对复数按实部/虚部分别滤波）
inline std::vector<std::complex<double>> lowpass_complex(const std::vector<std::complex<double>>& x,
                                                        double bw, double fs, int order = 4) {
    double nyq = 0.5 * fs;
    double wn = bw / nyq;
    if (wn >= 1.0) return x;
    std::vector<double> b, a;
    butter_lowpass(order, wn, b, a);
    std::vector<double> re(x.size()), im(x.size());
    for (size_t i = 0; i < x.size(); i++) { re[i] = x[i].real(); im[i] = x[i].imag(); }
    auto yr = lfilter(b, a, re), yi = lfilter(b, a, im);
    std::vector<std::complex<double>> out(x.size());
    for (size_t i = 0; i < x.size(); i++) out[i] = std::complex<double>(yr[i], yi[i]);
    return out;
}

// ---------------------------------------------------------------------------
// PAM4 映射
// ---------------------------------------------------------------------------
inline double PAM4_LEVEL(int s) { return s * 2.0 - 3.0; }   // [0,1,2,3] -> [-3,-1,1,3]
inline std::vector<double> pam4_map(const std::vector<int>& sym) {
    std::vector<double> out(sym.size());
    for (size_t i = 0; i < sym.size(); i++) out[i] = sym[i] * 2.0 - 3.0;
    return out;
}
inline int pam4_sym_of_level(double l) {
    double best = 1e30; int bi = 0;
    for (int s = 0; s < 4; s++) { double d = std::fabs(l - PAM4_LEVEL(s)); if (d < best) { best = d; bi = s; } }
    return bi;
}

// ---------------------------------------------------------------------------
// Tx DSP（tx_dsp.py）
// ---------------------------------------------------------------------------
inline std::vector<double> tx_ffe(const std::vector<double>& x, const std::vector<double>& taps, int sps) {
    int nt = (int)taps.size();
    std::vector<double> w(nt * sps, 0.0);
    for (int i = 0; i < nt; i++) w[i * sps] = taps[i];
    double sabs = 0.0; for (double v : w) sabs += std::fabs(v);
    for (auto& v : w) v /= sabs;
    return convolve_same(x, w);
}

inline std::vector<double> tx_dsp_chain(const std::vector<double>& tx_pam4, int sps_dsp,
                                        const std::vector<double>& tx_taps) {
    int N = (int)tx_pam4.size();
    std::vector<double> tx_up(N * sps_dsp, 0.0);
    for (int i = 0; i < N; i++) tx_up[i * sps_dsp] = tx_pam4[i];
    std::vector<double> pulse(sps_dsp, 1.0);
    auto full = convolve_full(tx_up, pulse);
    std::vector<double> tx_shaped(full.begin(), full.begin() + tx_up.size());
    return tx_ffe(tx_shaped, tx_taps, sps_dsp);
}

// ---------------------------------------------------------------------------
// 量化噪声 / ZOH（channel_imdd.py）
// ---------------------------------------------------------------------------
inline void add_quantization_noise(std::vector<double>& x, double enob, RkState& rng) {
    if (enob <= 0) return;
    double mn = x[0], mx = x[0];
    for (double v : x) { if (v < mn) mn = v; if (v > mx) mx = v; }
    double vfs = mx - mn;
    if (vfs <= 1e-30) return;
    double sq = vfs / (std::pow(2.0, enob) * std::sqrt(12.0));
    for (size_t i = 0; i < x.size(); i++) x[i] += rk_normal(rng, 0.0, sq);
}

inline std::vector<double> dac_zoh(const std::vector<double>& x, int sps_in, int sps_out) {
    int factor = sps_out / sps_in;
    std::vector<double> out(x.size() * factor);
    for (size_t i = 0; i < x.size(); i++)
        for (int k = 0; k < factor; k++) out[i * factor + k] = x[i];
    return out;
}

// ---------------------------------------------------------------------------
// CTLE / CD / DGD（频域，channel_imdd.py）
// ---------------------------------------------------------------------------
inline std::vector<double> apply_ctle(const std::vector<double>& x, double fs,
                                      double f_z, double f_p1, double f_p2, double g_dc_db,
                                      double g_dc2_db, double f_lf) {
    int N = (int)x.size();
    auto X = rfft(x);
    int nh = (int)X.size();
    double K_DC = std::pow(10.0, g_dc_db / 20.0);
    double K_DC2 = std::pow(10.0, g_dc2_db / 20.0);
    for (int k = 0; k < nh; k++) {
        double f = (double)k * fs / (double)N;
        std::complex<double> num1(1.0, f * (K_DC / f_z));
        std::complex<double> den1 = std::complex<double>(1.0, f / f_p1) * std::complex<double>(1.0, f / f_p2);
        std::complex<double> num2(1.0, f * (K_DC2 / f_lf));
        std::complex<double> den2(1.0, f / f_lf);
        X[k] *= (num1 / den1) * (num2 / den2);
    }
    return irfft(X, N);
}

inline std::vector<std::complex<double>> apply_cd(const std::vector<std::complex<double>>& E, double fs, double cd_ps_nm) {
    if (cd_ps_nm == 0.0) return E;
    int N = (int)E.size();
    std::vector<std::complex<double>> Ef(N);
    fft(E.data(), Ef.data(), N);
    double D = cd_ps_nm * 1e-3;
    double lmbda = 1550e-9, c = 3e8;
    std::vector<std::complex<double>> H(N);
    for (int k = 0; k < N; k++) {
        double f = (k <= N / 2) ? (double)k * fs / N : (double)(k - N) * fs / N;
        double phase = -DSH_PI * D * (lmbda * lmbda) / c * (f * f);
        H[k] = std::complex<double>(std::cos(phase), std::sin(phase));
        Ef[k] *= H[k];
    }
    std::vector<std::complex<double>> out(N);
    ifft(Ef.data(), out.data(), N);
    return out;
}

inline std::vector<double> apply_dgd(const std::vector<double>& P, double fs, double dgd_ps, double pol_angle_deg) {
    if (dgd_ps == 0.0) return P;
    int N = (int)P.size();
    auto Pf = rfft(P);
    int nh = (int)Pf.size();
    double theta = pol_angle_deg * DSH_PI / 180.0;
    double tau = dgd_ps * 1e-12;
    double c2 = std::cos(theta) * std::cos(theta);
    double s2 = std::sin(theta) * std::sin(theta);
    for (int k = 0; k < nh; k++) {
        double f = (double)k * fs / (double)N;
        double ang = -2.0 * DSH_PI * f * tau;
        std::complex<double> Hdgd = std::complex<double>(c2, 0.0) +
            std::complex<double>(s2 * std::cos(ang), s2 * std::sin(ang));
        Pf[k] *= Hdgd;
    }
    return irfft(Pf, N);
}

// ---------------------------------------------------------------------------
// Tx 模拟前端 LTI（channel_imdd.tx_frontend_lti）
// ---------------------------------------------------------------------------
inline std::vector<double> tx_frontend_lti(std::vector<double> x, const Config& cfg, double baud_rate,
                                           double fs_analog, double nyquist, RkState* rng,
                                           const S4P* s4p_tx) {
    double loss_db = cfg.d("channel.tx_pcb_loss_nyquist_db", cfg.d("channel.pcb_loss_nyquist_db", 15.0));
    double fc_pcb = nyquist / std::sqrt(std::pow(10.0, loss_db / 10.0) - 1.0);

    if (cfg.b("channel.use_s4p", false) && s4p_tx != nullptr) {
        std::vector<double> xf;
        if (apply_s4p_filter(*s4p_tx, x, fs_analog, -std::fabs(loss_db), nyquist, xf)) x = xf;
        else x = lowpass_filter(x, fc_pcb, fs_analog, 1);
    } else {
        x = lowpass_filter(x, fc_pcb, fs_analog, 1);
    }

    double host_tx = cfg.d("channel.host_tx_noise_rms", 0.001);
    if (rng != nullptr) for (auto& v : x) v += rk_normal(*rng, 0.0, host_tx);

    if (cfg.b("tx.use_ctle", false)) {
        double fb = baud_rate;
        double f_z = fb / cfg.d("tx.ctle_fz_ratio", 2.862);
        double f_p1 = fb / cfg.d("tx.ctle_fp1_ratio", 1.884);
        double f_p2 = fb / cfg.d("tx.ctle_fp2_ratio", 1.0);
        double f_lf = fb / cfg.d("tx.ctle_flf_ratio", 40.0);
        x = apply_ctle(x, fs_analog, f_z, f_p1, f_p2, cfg.d("tx.ctle_g_dc_db", 0.0),
                       cfg.d("tx.ctle_g_dc2_db", 0.0), f_lf);
    }

    double gain = cfg.d("channel.driver_gain", 0.3399);
    for (auto& v : x) v *= gain;
    x = lowpass_filter(x, cfg.d("channel.driver_bw", cfg.d("channel.mzm_bw", 40e9)), fs_analog, 4);
    return x;
}

// ---------------------------------------------------------------------------
// 完整模拟链路（channel_imdd.apply_channel）
// ---------------------------------------------------------------------------
struct ChannelNodes { std::vector<double> tx_analog, rx_analog, rx_adc; };

inline ChannelNodes apply_channel(const std::vector<double>& x_dac0, const Config& cfg, double baud_rate,
                                  int sps_dac, int sps_channel, int sps_adc, const S4P* s4p_tx, const S4P* s4p_rx) {
    double nyquist = baud_rate / 2.0;
    double loss_db_tx = cfg.d("channel.tx_pcb_loss_nyquist_db", cfg.d("channel.pcb_loss_nyquist_db", 15.0));
    double loss_db_rx = cfg.d("channel.rx_pcb_loss_nyquist_db", 15.0);
    double fc_pcb_tx = nyquist / std::sqrt(std::pow(10.0, loss_db_tx / 10.0) - 1.0);
    double fc_pcb_rx = nyquist / std::sqrt(std::pow(10.0, loss_db_rx / 10.0) - 1.0);

    int sys_seed = cfg.i("system.seed", 42);
    int ch_seed = cfg.has("channel.seed") ? cfg.i("channel.seed", 123) : (sys_seed + 7919);
    RkState rng; rk_seed(rng, (unsigned)ch_seed);

    std::vector<double> x = x_dac0;
    add_quantization_noise(x, cfg.d("channel.dac_enob", 0.0), rng);
    x = dac_zoh(x, sps_dac, sps_channel);
    double fs_analog = baud_rate * sps_channel;

    if (cfg.b("channel.use_distributed_noise", false)) {
        double htx = cfg.d("channel.host_tx_noise_rms", 0.0);
        for (auto& v : x) v += rk_normal(rng, 0.0, htx);
    }

    x = tx_frontend_lti(x, cfg, baud_rate, fs_analog, nyquist, &rng, s4p_tx);
    std::vector<double> x_analog = x;

    // E-O（激光 + MZM）
    double P_in_W = std::pow(10.0, 3.0 / 10.0) / 1000.0;
    double rin_db = cfg.d("channel.laser_rin_db_hz", -150.0);
    double rin_linear = std::pow(10.0, rin_db / 10.0);
    double bw_noise = fs_analog / 2.0;
    double var_rin = rin_linear * bw_noise * (P_in_W * P_in_W);
    double s_rin = std::sqrt(var_rin);

    std::vector<double> P_laser(x.size());
    for (size_t i = 0; i < x.size(); i++) {
        double p = P_in_W + rk_normal(rng, 0.0, s_rin);
        P_laser[i] = p > 0.0 ? p : 0.0;
    }

    double linewidth = cfg.d("channel.laser_linewidth_hz", 0.0);
    std::vector<double> phase_noise(x.size(), 0.0);
    if (linewidth > 0) {
        double sd = std::sqrt(2.0 * DSH_PI * linewidth / fs_analog);
        double acc = 0.0;
        for (size_t i = 0; i < x.size(); i++) { acc += rk_normal(rng, 0.0, sd); phase_noise[i] = acc; }
    }
    std::vector<std::complex<double>> E_in(x.size());
    for (size_t i = 0; i < x.size(); i++)
        E_in[i] = std::complex<double>(std::sqrt(P_laser[i]) * std::cos(phase_noise[i]),
                                       std::sqrt(P_laser[i]) * std::sin(phase_noise[i]));

    double v_pi = cfg.d("channel.mzm_v_pi", 3.0);
    double v_bias = cfg.d("channel.mzm_v_bias", 2.25);
    double er_db = cfg.d("channel.mzm_er_db", 25.0);
    double e_r = std::pow(10.0, er_db / 10.0);
    double gamma = (1.0 - 1.0 / std::sqrt(e_r)) / 2.0;

    std::vector<std::complex<double>> E_out(x.size());
    for (size_t i = 0; i < x.size(); i++) {
        double phase = DSH_PI * (x[i] + v_bias) / v_pi;
        std::complex<double> e1(std::cos(phase), std::sin(phase));
        std::complex<double> e2(std::cos(-phase), std::sin(-phase));
        E_out[i] = E_in[i] * (gamma * e1 + (1.0 - gamma) * e2);
    }
    E_out = lowpass_complex(E_out, cfg.d("channel.mzm_bw", 40e9), fs_analog, 4);

    // 光纤
    double loss_db = cfg.d("channel.fiber_length_km", 2.0) * cfg.d("channel.fiber_loss_db_km", 0.25);
    double loss_linear = std::pow(10.0, -loss_db / 20.0);
    double sqrt_loss = std::sqrt(loss_linear);
    for (auto& e : E_out) e *= sqrt_loss;
    E_out = apply_cd(E_out, fs_analog, cfg.d("channel.cd_ps_nm", 0.0));

    // O-E（PIN 平方律 + DGD + 散粒/热噪声）
    std::vector<double> P_rx(E_out.size());
    for (size_t i = 0; i < E_out.size(); i++) P_rx[i] = std::norm(E_out[i]);
    P_rx = apply_dgd(P_rx, fs_analog, cfg.d("channel.dgd_ps", 0.0), cfg.d("channel.pol_angle_deg", 45.0));

    double resp = cfg.d("channel.pin_responsivity", 0.6);
    double dark = cfg.d("channel.pin_dark_current_na", 10.0) * 1e-9;
    std::vector<double> I_pd(P_rx.size());
    for (size_t i = 0; i < P_rx.size(); i++) I_pd[i] = resp * P_rx[i] + dark;

    double q = 1.602176634e-19, kB = 1.380649e-23;
    double temp_k = cfg.d("channel.temperature_k", 298.15);
    double rl = cfg.d("channel.rl_ohm", 50.0);
    double var_thermal = 4.0 * kB * temp_k / rl * bw_noise;
    double s_thermal = std::sqrt(var_thermal);

    std::vector<double> I_pd_noisy(I_pd.size());
    // 先抽全部散粒噪声（逐元素 scale），再抽全部热噪声（标量 scale）——与 numpy 顺序一致
    for (size_t i = 0; i < I_pd.size(); i++) {
        double var_shot = 2.0 * q * std::fabs(I_pd[i]) * bw_noise;
        I_pd_noisy[i] = I_pd[i] + rk_normal(rng, 0.0, std::sqrt(var_shot));
    }
    for (size_t i = 0; i < I_pd.size(); i++) {
        I_pd_noisy[i] += rk_normal(rng, 0.0, s_thermal);
    }
    I_pd_noisy = lowpass_filter(I_pd_noisy, cfg.d("channel.pd_bw", 40e9), fs_analog, 4);

    // TIA
    double tia_gain = cfg.d("channel.tia_gain_ohm", 720.0);
    std::vector<double> V_tia(I_pd_noisy.size());
    for (size_t i = 0; i < I_pd_noisy.size(); i++) V_tia[i] = I_pd_noisy[i] * tia_gain;

    double tia_noise_pa = cfg.d("channel.tia_noise_pa_rthz", 16.0) * 1e-12;
    double var_tia = (tia_noise_pa * tia_noise_pa) * bw_noise;
    double s_tia = std::sqrt(var_tia) * tia_gain;
    for (auto& v : V_tia) v += rk_normal(rng, 0.0, s_tia);
    V_tia = lowpass_filter(V_tia, cfg.d("channel.tia_bw", 40e9), fs_analog, 4);

    // 单层 Rx AGC（目标 RMS = √5）
    double mean = 0.0;
    for (double v : V_tia) mean += v;
    mean /= V_tia.size();
    for (auto& v : V_tia) v -= mean;
    double var = 0.0;
    for (double v : V_tia) var += v * v;
    var /= V_tia.size();
    double rms = std::sqrt(var);
    if (rms > 1e-12) {
        double scale = std::sqrt(5.0) / rms;
        for (auto& v : V_tia) v *= scale;
    }
    std::vector<double> xr = V_tia;

    // Rx 电插损
    if (cfg.b("channel.use_s4p", false) && s4p_rx != nullptr) {
        std::vector<double> xf;
        if (apply_s4p_filter(*s4p_rx, xr, fs_analog, -std::fabs(loss_db_rx), nyquist, xf)) xr = xf;
        else xr = lowpass_filter(xr, fc_pcb_rx, fs_analog, 1);
    } else {
        xr = lowpass_filter(xr, fc_pcb_rx, fs_analog, 1);
    }

    double host_rx = cfg.d("channel.host_rx_noise_rms", 0.001);
    for (auto& v : xr) v += rk_normal(rng, 0.0, host_rx);

    if (cfg.b("channel.use_rx_ctle", true)) {
        double fb = baud_rate;
        double f_z = fb / cfg.d("channel.rx_ctle_fz_ratio", 2.862);
        double f_p1 = fb / cfg.d("channel.rx_ctle_fp1_ratio", 1.884);
        double f_p2 = fb / cfg.d("channel.rx_ctle_fp2_ratio", 1.0);
        double f_lf = fb / cfg.d("channel.rx_ctle_flf_ratio", 40.0);
        xr = apply_ctle(xr, fs_analog, f_z, f_p1, f_p2, cfg.d("channel.rx_ctle_g_dc_db", 6.0),
                        cfg.d("channel.rx_ctle_g_dc2_db", 3.0), f_lf);
    }

    // ADC
    std::vector<double> x_adc_in = lowpass_filter(xr, cfg.d("channel.adc_bw", 40e9), fs_analog, 4);
    int dec = sps_channel / sps_adc;
    std::vector<double> x_adc_out(x_adc_in.size() / dec);
    for (size_t i = 0; i < x_adc_out.size(); i++) x_adc_out[i] = x_adc_in[i * dec];
    add_quantization_noise(x_adc_out, cfg.d("channel.adc_enob", 0.0), rng);

    ChannelNodes n; n.tx_analog = x_analog; n.rx_analog = x_adc_in; n.rx_adc = x_adc_out;
    return n;
}

// ---------------------------------------------------------------------------
// Rx DSP（rx_dsp.adaptive_ffe_dfe）：LS 初始化 + DD-LMS（DFE=0, pr_alpha=0）
// ---------------------------------------------------------------------------
inline void solve_linear(std::vector<std::vector<double>> A, std::vector<double>& b) {
    int n = (int)A.size();
    for (int col = 0; col < n; col++) {
        int piv = col;
        for (int r = col + 1; r < n; r++) if (std::fabs(A[r][col]) > std::fabs(A[piv][col])) piv = r;
        if (piv != col) { std::swap(A[piv], A[col]); std::swap(b[piv], b[col]); }
        double d = A[col][col];
        for (int r = col + 1; r < n; r++) {
            double f = A[r][col] / d;
            for (int c = col; c < n; c++) A[r][c] -= f * A[col][c];
            b[r] -= f * b[col];
        }
    }
    for (int r = n - 1; r >= 0; r--) {
        double s = b[r];
        for (int c = r + 1; c < n; c++) s -= A[r][c] * b[c];
        b[r] = s / A[r][r];
    }
}

struct FfeResult { std::vector<double> rx_eq, error_seq, ffe_decisions; };

inline FfeResult adaptive_ffe_dfe(const std::vector<double>& rx_sps, const std::vector<double>& tx_ref,
                                  int num_taps_ffe, int ffe_pre, int num_taps_dfe, double mu_ffe,
                                  double mu_dfe, int train_len, int sync_delay) {
    int N_sym = (int)tx_ref.size();
    int ls_len = std::min(train_len, N_sym / 2);
    std::vector<std::vector<double>> XTX(num_taps_ffe, std::vector<double>(num_taps_ffe, 0.0));
    std::vector<double> XTY(num_taps_ffe, 0.0);
    int nrow = 0;
    for (int n = num_taps_ffe; n < ls_len; n++) {
        int idx = 2 * (n + sync_delay) + ffe_pre;
        if (idx - num_taps_ffe + 1 < 0 || idx >= (int)rx_sps.size()) continue;
        // x_slice = rx_sps[idx-nt+1 .. idx] 反转
        std::vector<double> xs(num_taps_ffe);
        for (int t = 0; t < num_taps_ffe; t++) xs[t] = rx_sps[idx - t];
        for (int i = 0; i < num_taps_ffe; i++) {
            XTY[i] += xs[i] * tx_ref[n];
            for (int j = 0; j < num_taps_ffe; j++) XTX[i][j] += xs[i] * xs[j];
        }
        nrow++;
    }
    double lambda = 0.05 * (double)nrow;
    for (int i = 0; i < num_taps_ffe; i++) XTX[i][i] += lambda;
    std::vector<double> w_ffe = XTY;
    solve_linear(XTX, w_ffe);

    std::vector<double> rx_eq(N_sym, 0.0), error_seq(N_sym, 0.0), ffe_decisions(N_sym, 0.0);
    double d_prev = 0.0;
    for (int n = 0; n < N_sym; n++) {
        int idx = 2 * (n + sync_delay) + ffe_pre;
        if (idx - num_taps_ffe + 1 < 0 || idx >= (int)rx_sps.size()) continue;
        double y = 0.0;
        for (int t = 0; t < num_taps_ffe; t++) y += w_ffe[t] * rx_sps[idx - t];
        rx_eq[n] = y;
        double d;
        if (y > 2.0) d = 3.0;
        else if (y > 0.0) d = 1.0;
        else if (y > -2.0) d = -1.0;
        else d = -3.0;
        ffe_decisions[n] = d;
        double ref;
        if (n < train_len) ref = (n > 0) ? tx_ref[n] : tx_ref[n];   // pr_alpha=0
        else ref = d;   // pr_alpha=0
        double error = ref - y;
        error_seq[n] = error;
        if (n < train_len) {
            double leak = 1e-5;
            double k = mu_ffe;
            for (int t = 0; t < num_taps_ffe; t++) {
                w_ffe[t] = w_ffe[t] * (1.0 - k * leak) + k * error * rx_sps[idx - t];
            }
        }
        d_prev = d;
    }
    FfeResult r; r.rx_eq = rx_eq; r.error_seq = error_seq; r.ffe_decisions = ffe_decisions;
    return r;
}

// ---------------------------------------------------------------------------
// Burg AR + Viterbi MLSE（mlse_burg.py）
// ---------------------------------------------------------------------------
inline std::vector<double> burg_ar(const std::vector<double>& x, int order) {
    int N = (int)x.size();
    std::vector<double> ef = x, eb = x;
    std::vector<double> a(order + 1, 0.0);
    a[0] = 1.0;
    double E = 0.0;
    for (double v : x) E += v * v;
    E /= N;
    for (int m = 1; m <= order; m++) {
        double num = 0.0, den = 0.0;
        for (int i = m; i < N; i++) {
            num += ef[i] * eb[i - 1];
            den += ef[i] * ef[i] + eb[i - 1] * eb[i - 1];
        }
        double k = -2.0 * num / den;
        std::vector<double> a_prev = a;
        for (int i = 1; i <= m; i++) {
            a[i] = (i == m) ? k : a_prev[i] + k * a_prev[m - i];
        }
        std::vector<double> ef_new(N, 0.0), eb_new(N, 0.0);
        for (int i = m; i < N; i++) {
            ef_new[i] = ef[i] + k * eb[i - 1];
            eb_new[i] = eb[i - 1] + k * ef[i];
        }
        ef = ef_new; eb = eb_new;
        E *= (1.0 - k * k);
    }
    return std::vector<double>(a.begin() + 1, a.end());
}

// Viterbi MLSE（memory=1，4 状态，与 _viterbi_mlse_pam4_fast 一致）
inline std::vector<double> viterbi_mlse_pam4_mem1(const std::vector<double>& y, double pr0, double pr1) {
    int N = (int)y.size();
    std::vector<std::vector<int>> pointers(4, std::vector<int>(N, 0));
    std::vector<double> pm(4, 0.0);
    // expected[next][prev] = pr0*levels[next] + pr1*levels[prev]
    double lv[4] = {-3.0, -1.0, 1.0, 3.0};
    double expected[4][4];
    for (int ns = 0; ns < 4; ns++)
        for (int ps = 0; ps < 4; ps++) expected[ns][ps] = pr0 * lv[ns] + pr1 * lv[ps];
    for (int n = 0; n < N; n++) {
        std::vector<double> npm(4, 1e300);
        for (int ns = 0; ns < 4; ns++) {
            double best = 1e300; int bp = 0;
            for (int ps = 0; ps < 4; ps++) {
                double sq = (y[n] - expected[ns][ps]);
                sq *= sq;
                double m = pm[ps] + sq;
                if (m < best) { best = m; bp = ps; }
            }
            npm[ns] = best;
            pointers[ns][n] = bp;
        }
        pm = npm;
    }
    std::vector<double> decisions(N);
    int cs = 0;
    for (int s = 1; s < 4; s++) if (pm[s] < pm[cs]) cs = s;
    for (int n = N - 1; n >= 0; n--) {
        decisions[n] = lv[cs];
        cs = pointers[cs][n];
    }
    return decisions;
}

// ---------------------------------------------------------------------------
// BER（metrics.calculate_ber，Gray 映射）
// ---------------------------------------------------------------------------
inline std::pair<double, double> calculate_ber(const std::vector<int>& tx, const std::vector<int>& rx) {
    int n = (int)tx.size();
    long ser = 0, ber = 0;
    for (int i = 0; i < n; i++) {
        if (tx[i] != rx[i]) ser++;
        int gt = tx[i] ^ (tx[i] >> 1), gr = rx[i] ^ (rx[i] >> 1);
        int d = gt ^ gr;
        ber += (d & 1) + ((d >> 1) & 1);
    }
    return { (double)ser / n, (double)ber / (2.0 * n) };
}

// ---------------------------------------------------------------------------
// run_sim（main.run_sim）
// ---------------------------------------------------------------------------
inline double sumabs(const std::vector<double>& v) { double s = 0.0; for (double x : v) s += std::fabs(x); return s; }
inline double sumabs(const std::vector<std::complex<double>>& v) { double s = 0.0; for (auto x : v) s += std::abs(x); return s; }

struct SimResult {
    double ffe_ber, mlse_ber; double ffe_ser, mlse_ser;
    // 逐节点校验和（sum |x|），用于 C++/Python 等价性逐节点比对
    double chk_tx_out_nonoise, chk_tx_out_noisy, chk_tx_analog, chk_rx_analog, chk_rx_adc, chk_rx_eq, chk_white;
    int sync_delay, phase_offset, n_valid;
};

inline SimResult run_sim(const Config& cfg, const std::vector<double>& custom_taps,
                         const S4P* s4p_tx, const S4P* s4p_rx) {
    double baud_rate = cfg.d("system.baud_rate", 56e9);
    int sps_dsp = cfg.i("system.sps_dsp", 2);
    int sps_dac = cfg.i("system.sps_dac", 2);
    int sps_channel = cfg.i("system.sps_channel", 8);
    int sps_adc = cfg.i("system.sps_adc", 2);
    int num_symbols = cfg.i("system.num_symbols", 262144);
    int seed = cfg.i("system.seed", 42);

    RkState rng; rk_seed(rng, (unsigned)seed);
    std::vector<int> tx_symbols(num_symbols);
    for (int i = 0; i < num_symbols; i++) tx_symbols[i] = (int)rk_randint(rng, 0, 4);
    std::vector<double> tx_pam4 = pam4_map(tx_symbols);

    // Tx FFE taps（run_sim 里 custom_taps 覆盖）
    std::vector<double> tx_taps = custom_taps;

    std::vector<double> tx_out = tx_dsp_chain(tx_pam4, sps_dsp, tx_taps);
    double chk_tx_nonoise = sumabs(tx_out);

    // 发端人为加噪（快速验证模式）
    double tx_noise = cfg.d("system.tx_noise_snr_db", 0.0);
    if (tx_noise > 0.0) {
        double sigma = std::sqrt(5.0) / std::pow(10.0, tx_noise / 20.0);
        for (auto& v : tx_out) v += rk_normal(rng, 0.0, sigma);
    }
    double chk_tx_noisy = sumabs(tx_out);

    ChannelNodes ch = apply_channel(tx_out, cfg, baud_rate, sps_dac, sps_channel, sps_adc, s4p_tx, s4p_rx);
    const std::vector<double>& rx_adc = ch.rx_adc;
    double chk_tx_analog = sumabs(ch.tx_analog);
    double chk_rx_analog = sumabs(ch.rx_analog);
    double chk_rx_adc = sumabs(rx_adc);

    // 2 相位同步（scipy.signal.correlate）
    std::vector<double> adc_even(rx_adc.size() / sps_adc);
    std::vector<double> adc_odd(rx_adc.size() / sps_adc);
    for (size_t i = 0; i < adc_even.size(); i++) {
        adc_even[i] = rx_adc[i * sps_adc];
        adc_odd[i] = (i * sps_adc + 1 < rx_adc.size()) ? rx_adc[i * sps_adc + 1] : 0.0;
    }
    int nref = std::min(1000, num_symbols);
    std::vector<double> a1(adc_even.begin(), adc_even.begin() + nref);
    std::vector<double> a2(adc_odd.begin(), adc_odd.begin() + nref);
    std::vector<double> refv(tx_pam4.begin(), tx_pam4.begin() + nref);
    auto corr_even = correlate_full(a1, refv);
    auto corr_odd = correlate_full(a2, refv);
    double max_even = *std::max_element(corr_even.begin(), corr_even.end());
    double max_odd = *std::max_element(corr_odd.begin(), corr_odd.end());
    int sync_delay, phase_offset;
    if (max_even >= max_odd) {
        sync_delay = argmax(corr_even) - (nref - 1);
        phase_offset = 0;
    } else {
        sync_delay = argmax(corr_odd) - (nref - 1);
        phase_offset = 1;
    }

    int mlse_memory = cfg.i("rx.mlse_memory", 1);
    int dfe_taps = cfg.i("rx.dfe_taps", 0);
    if (mlse_memory > 0) dfe_taps = 0;

    // rx_adc[phase_offset:] 作为 2sps 输入
    std::vector<double> rx_sps(rx_adc.size() - phase_offset);
    for (size_t i = 0; i < rx_sps.size(); i++) rx_sps[i] = rx_adc[i + phase_offset];

    int ffe_taps = cfg.i("rx.ffe_taps", 22);
    int ffe_pre = cfg.i("rx.ffe_pre", 6);
    double lms_mu = cfg.d("rx.lms_mu", 1e-4);
    int train_len = cfg.i("rx.train_len", 10000);

    FfeResult ffe = adaptive_ffe_dfe(rx_sps, tx_pam4, ffe_taps, ffe_pre, dfe_taps,
                                     lms_mu, lms_mu, train_len, sync_delay);

    std::vector<int> ffe_symbols(ffe.ffe_decisions.size());
    for (size_t i = 0; i < ffe_symbols.size(); i++) ffe_symbols[i] = pam4_sym_of_level(ffe.ffe_decisions[i]);

    int n_valid = ((int)rx_sps.size() - ffe_pre) / 2 - sync_delay;
    if (n_valid <= train_len) n_valid = train_len + 1;

    int ar_order = mlse_memory;
    std::vector<double> pr_taps;
    if (ar_order > 0) {
        std::vector<double> err_ss(ffe.error_seq.begin() + train_len, ffe.error_seq.begin() + n_valid);
        auto ar = burg_ar(err_ss, ar_order);
        pr_taps.push_back(1.0);
        pr_taps.insert(pr_taps.end(), ar.begin(), ar.end());
    } else {
        pr_taps.push_back(1.0);
    }

    double chk_rx_eq = sumabs(ffe.rx_eq);
    auto full_w = convolve_full(ffe.rx_eq, pr_taps);
    std::vector<double> whitened(full_w.begin(), full_w.begin() + ffe.rx_eq.size());
    double chk_white = sumabs(whitened);

    std::vector<double> rx_decisions;
    if (ar_order == 1) rx_decisions = viterbi_mlse_pam4_mem1(whitened, pr_taps[0], pr_taps[1]);
    else { // memory==0：直接切片器
        rx_decisions.resize(whitened.size());
        for (size_t i = 0; i < whitened.size(); i++) rx_decisions[i] = PAM4_LEVEL(pam4_sym_of_level(whitened[i]));
    }

    std::vector<int> rx_symbols(rx_decisions.size());
    for (size_t i = 0; i < rx_decisions.size(); i++) rx_symbols[i] = pam4_sym_of_level(rx_decisions[i]);

    std::vector<int> tx_aligned(tx_symbols.begin() + train_len, tx_symbols.begin() + n_valid);
    std::vector<int> ffe_aligned(ffe_symbols.begin() + train_len, ffe_symbols.begin() + n_valid);
    std::vector<int> mlse_aligned(rx_symbols.begin() + train_len, rx_symbols.begin() + n_valid);

    int min_len = (int)std::min({ tx_aligned.size(), ffe_aligned.size(), mlse_aligned.size() });
    auto [ffe_ser, ffe_ber] = calculate_ber(
        std::vector<int>(tx_aligned.begin(), tx_aligned.begin() + min_len),
        std::vector<int>(ffe_aligned.begin(), ffe_aligned.begin() + min_len));
    auto [mlse_ser, mlse_ber] = calculate_ber(
        std::vector<int>(tx_aligned.begin(), tx_aligned.begin() + min_len),
        std::vector<int>(mlse_aligned.begin(), mlse_aligned.begin() + min_len));

    if (mlse_ber <= 0.0) mlse_ber = 0.5 / (2.0 * std::max(min_len, 1));
    if (ffe_ber <= 0.0) ffe_ber = 0.5 / (2.0 * std::max(min_len, 1));

    SimResult r; r.ffe_ber = ffe_ber; r.mlse_ber = mlse_ber; r.ffe_ser = ffe_ser; r.mlse_ser = mlse_ser;
    r.chk_tx_out_nonoise = chk_tx_nonoise; r.chk_tx_out_noisy = chk_tx_noisy;
    r.chk_tx_analog = chk_tx_analog; r.chk_rx_analog = chk_rx_analog;
    r.chk_rx_adc = chk_rx_adc; r.chk_rx_eq = chk_rx_eq; r.chk_white = chk_white;
    r.sync_delay = sync_delay; r.phase_offset = phase_offset; r.n_valid = n_valid;
    return r;
}

} // namespace dsh