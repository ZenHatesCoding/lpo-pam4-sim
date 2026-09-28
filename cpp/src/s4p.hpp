// s4p.hpp — Touchstone .s4p 解析 + sdd21 + 频率缩放 + np.interp/np.unwrap 复刻。
//
// 只复刻本项目链路用到的部分（channel_imdd.apply_s4p_filter）：
//   sdd21 = 0.5*(S21 - S23 - S41 + S43)，Sij 为 4 端口混合模（skrf Network.s[:,i,j]）。
#pragma once

#include <vector>
#include <complex>
#include <cmath>
#include <string>
#include <fstream>
#include <sstream>
#include <algorithm>

#include "fft.hpp"

namespace dsh {

struct S4P {
    std::vector<double> freq;               // Hz
    std::vector<std::complex<double>> sdd21;
};

// 解析 .s4p（Touchstone，支持 `# hz S ma R 50` 幅角格式；db/ri 亦支持）。
// 数据可能按行包裹（本项目的 .s4p 每频点 4 行 + 空行分隔），故按"扁平数值流 +
// 每频点 33 个数值（freq + 16×mag/ang 或 re/im）"整体 reshape，与 skrf 读法一致。
inline bool load_s4p(const std::string& path, S4P& out) {
    std::ifstream f(path);
    if (!f) return false;
    std::string line;
    enum { FMT_MA, FMT_DB, FMT_RI } fmt = FMT_MA;
    std::vector<double> data;
    bool got_fmt = false;
    while (std::getline(f, line)) {
        while (!line.empty() && (line.back() == '\r' || line.back() == ' ' || line.back() == '\t')) line.pop_back();
        if (line.empty()) continue;
        if (line[0] == '!') continue;
        if (line[0] == '#') {
            std::istringstream ss(line);
            std::string hash, unit, param, format;
            ss >> hash >> unit >> param >> format;
            if (format == "ma") fmt = FMT_MA;
            else if (format == "db") fmt = FMT_DB;
            else if (format == "ri") fmt = FMT_RI;
            got_fmt = true;
            continue;
        }
        std::istringstream ss(line);
        double v;
        while (ss >> v) data.push_back(v);
    }
    if (data.empty()) return false;
    const int PER = 33;              // freq + 16×(两分量)
    int npt = (int)data.size() / PER;
    if (npt == 0) return false;
    for (int p = 0; p < npt; p++) {
        double freq = data[p * PER];
        auto at = [&](int port_idx) -> std::complex<double> {   // port_idx = 0..15（行优先 S11..S44）
            double a = data[p * PER + 1 + 2 * port_idx];
            double b = data[p * PER + 1 + 2 * port_idx + 1];
            if (fmt == FMT_MA) return std::polar(a, b * DSH_PI / 180.0);
            if (fmt == FMT_DB) return std::polar(std::pow(10.0, a / 20.0), b * DSH_PI / 180.0);
            return std::complex<double>(a, b);
        };
        std::complex<double> S21 = at(4), S23 = at(6), S41 = at(12), S43 = at(14);
        out.freq.push_back(freq);
        out.sdd21.push_back(0.5 * (S21 - S23 - S41 + S43));
    }
    return !out.freq.empty();
}

// np.angle = atan2(imag, real)
inline double angle_c(std::complex<double> z) { return std::atan2(z.imag(), z.real()); }

// np.unwrap：按**原始**相邻相位差判定跳变，累计 ±2π（与 numpy 语义一致）。
inline std::vector<double> unwrap(const std::vector<std::complex<double>>& z) {
    int n = (int)z.size();
    std::vector<double> raw(n);
    for (int i = 0; i < n; i++) raw[i] = angle_c(z[i]);
    std::vector<double> up(n);
    up[0] = raw[0];
    double off = 0.0;
    for (int i = 1; i < n; i++) {
        double d = raw[i] - raw[i - 1];
        if (d > DSH_PI) off -= 2.0 * DSH_PI;
        else if (d < -DSH_PI) off += 2.0 * DSH_PI;
        up[i] = raw[i] + off;
    }
    return up;
}

// np.interp(x, xp, fp, left, right)：xp 升序，线性插值，越界取 left/right。
inline std::vector<double> interp(const std::vector<double>& x, const std::vector<double>& xp,
                                  const std::vector<double>& fp, double left, double right) {
    std::vector<double> y(x.size());
    size_t np = xp.size();
    for (size_t i = 0; i < x.size(); i++) {
        double xi = x[i];
        if (xi < xp[0]) { y[i] = left; continue; }
        if (xi > xp[np - 1]) { y[i] = right; continue; }
        // 二分定位 k: xp[k] <= xi < xp[k+1]
        size_t lo = 0, hi = np - 1;
        while (hi - lo > 1) {
            size_t mid = (lo + hi) / 2;
            if (xp[mid] <= xi) lo = mid; else hi = mid;
        }
        double t = (xi - xp[lo]) / (xp[lo + 1] - xp[lo]);
        y[i] = fp[lo] + (fp[lo + 1] - fp[lo]) * t;
    }
    return y;
}

// channel_imdd.find_f_scale_for_target_il
inline double find_f_scale_for_target_il(const std::vector<double>& freqs,
                                         const std::vector<std::complex<double>>& sdd21,
                                         double target_il_db, double nyquist) {
    std::vector<double> mag_db(freqs.size());
    for (size_t i = 0; i < freqs.size(); i++) mag_db[i] = 20.0 * std::log10(std::abs(sdd21[i]) + 1e-12);
    long first = -1;
    for (size_t i = 0; i < mag_db.size(); i++) { if (mag_db[i] <= target_il_db) { first = (long)i; break; } }
    double f_match;
    if (first >= 0) {
        if (first > 0) {
            double f1 = freqs[first - 1], f2 = freqs[first];
            double m1 = mag_db[first - 1], m2 = mag_db[first];
            f_match = f1 + (target_il_db - m1) / (m2 - m1) * (f2 - f1);
        } else {
            f_match = freqs[0];
        }
    } else {
        f_match = freqs[freqs.size() - 1];
    }
    if (f_match <= 0) f_match = 1e9;
    return nyquist / f_match;
}

// channel_imdd.apply_s4p_filter：返回过滤后实数信号；失败返回空。
inline bool apply_s4p_filter(const S4P& nw, const std::vector<double>& x, double fs,
                             double target_il_db, double nyquist, std::vector<double>& out) {
    int N = (int)x.size();
    auto X = rfft(x);
    int nh = (int)X.size();
    // f_sig = rfftfreq(N, d=1/fs) = k*fs/N
    std::vector<double> f_sig(nh);
    for (int k = 0; k < nh; k++) f_sig[k] = (double)k * fs / (double)N;

    double f_scale = find_f_scale_for_target_il(nw.freq, nw.sdd21, target_il_db, nyquist);
    std::vector<double> f_scaled(nh);
    for (int k = 0; k < nh; k++) f_scaled[k] = f_sig[k] / f_scale;

    // mag 插值
    std::vector<double> mag(nw.sdd21.size());
    for (size_t i = 0; i < mag.size(); i++) mag[i] = std::abs(nw.sdd21[i]);
    std::vector<double> mag_i = interp(f_scaled, nw.freq, mag, mag[0], 0.0);

    // phase 插值（unwrap(angle)）
    std::vector<double> ph = unwrap(nw.sdd21);
    std::vector<double> ph_i = interp(f_scaled, nw.freq, ph, angle_c(nw.sdd21[0]), 0.0);

    std::vector<std::complex<double>> H(nh);
    for (int k = 0; k < nh; k++) H[k] = std::polar(mag_i[k], ph_i[k]);

    for (int k = 0; k < nh; k++) X[k] *= H[k];
    out = irfft(X, N);
    return true;
}

} // namespace dsh