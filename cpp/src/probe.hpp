// probe.hpp — 发端物理探针（tx_channel_extract.py 一比一复刻）
//   extract_tx_s21 / _drive_rms / extract_tx_features + 符号格基准缓存。
#pragma once

#include "physim.hpp"
#include <map>
#include <cstdio>

namespace dsh {

inline int argmax_abs(const std::vector<double>& v) {
    int bi = 0; double bv = -1.0;
    for (int i = 0; i < (int)v.size(); i++) { double a = std::fabs(v[i]); if (a > bv) { bv = a; bi = i; } }
    return bi;
}

// 名义 9-tap FFE（主抽头 = 1，其余 0）
inline std::vector<double> nominal_taps(const Config& cfg) {
    int n = cfg.i("tx.ffe_taps", 9);
    std::vector<double> taps(n, 0.0);
    int pre = cfg.i("tx.ffe_pre", n / 2);
    if (pre >= 0 && pre < n) taps[pre] = 1.0;
    return taps;
}

// 符号格对齐所依赖的信道环境签名（与 Python _env_signature 一致）
inline std::string env_signature(const Config& cfg) {
    char buf[640];
    std::snprintf(buf, sizeof(buf), "%d|%s|%.6f|%.0f|%.0f|%.4f|%.4f|%.2f",
        cfg.b("channel.use_s4p", false) ? 1 : 0,
        cfg.s("channel.s4p_file", "").c_str(),
        cfg.d("channel.tx_pcb_loss_nyquist_db", -1.0),
        cfg.d("channel.driver_bw", cfg.d("channel.mzm_bw", 40e9)),
        cfg.d("channel.mzm_bw", 40e9),
        cfg.d("channel.cd_ps_nm", 0.0),
        cfg.d("channel.dgd_ps", 0.0),
        cfg.d("channel.pol_angle_deg", 0.0));
    return std::string(buf);
}

// 单位冲激过整条 Tx 模拟链 -> 8sps 波形（MZM 输入端，单位 V，无噪声）
inline std::vector<double> chain_impulse(const Config& cfg, const std::vector<double>& custom_taps,
                                         const S4P* s4p, int pad_len = 100) {
    double baud_rate = cfg.d("system.baud_rate", 56e9);
    int sps_dsp = cfg.i("system.sps_dsp", 2);
    int sps_dac = cfg.i("system.sps_dac", 2);
    int sps_channel = cfg.i("system.sps_channel", 8);

    std::vector<double> tx_symbols(2 * pad_len + 1, 0.0);
    tx_symbols[pad_len] = 1.0;                       // 单位脉冲（1 sps）
    std::vector<double> tx_out = tx_dsp_chain(tx_symbols, sps_dsp, custom_taps);

    std::vector<double> x = dac_zoh(tx_out, sps_dac, sps_channel);
    double fs_analog = baud_rate * sps_channel;
    double nyquist = baud_rate / 2.0;

    x = tx_frontend_lti(x, cfg, baud_rate, fs_analog, nyquist, nullptr, s4p);
    x = lowpass_filter(x, cfg.d("channel.mzm_bw", 40e9), fs_analog);   // E-O 转换带限
    return x;
}

// 符号格基准（透传冲激峰值位置），按环境缓存
inline int peak_idx_for_env(const Config& cfg, const S4P* s4p) {
    static std::map<std::string, int> cache;
    std::string key = env_signature(cfg);
    auto it = cache.find(key);
    if (it != cache.end()) return it->second;
    auto x = chain_impulse(cfg, nominal_taps(cfg), s4p);
    int peak = argmax_abs(x);
    cache[key] = peak;
    return peak;
}

// 发端等效 T 间隔 FIR（绝对标定，单位 V），num_taps 个中心抽头
inline std::vector<double> extract_tx_s21(const Config& cfg, const S4P* s4p,
                                          const std::vector<double>& custom_taps, int num_taps = 7) {
    int sps_channel = cfg.i("system.sps_channel", 8);
    int pre_cursors = 2;
    std::vector<double> x = chain_impulse(cfg, custom_taps, s4p);
    int peak_idx = peak_idx_for_env(cfg, s4p);

    std::vector<double> fir(num_taps, 0.0);
    for (int i = 0; i < num_taps; i++) {
        int idx = peak_idx + (i - pre_cursors) * sps_channel;
        if (idx >= 0 && idx < (int)x.size()) fir[i] = x[idx];
    }
    return fir;
}

// 该配置下 MZM 输入端的真实驱动 RMS（V），固定 PAM4 序列跑 Tx 前端（无噪声）
inline double drive_rms(const Config& cfg, const S4P* s4p, const std::vector<double>& custom_taps,
                        int n_symbols = 4096, unsigned seed = 7) {
    double baud_rate = cfg.d("system.baud_rate", 56e9);
    int sps_dsp = cfg.i("system.sps_dsp", 2);
    int sps_dac = cfg.i("system.sps_dac", 2);
    int sps_channel = cfg.i("system.sps_channel", 8);

    RkState rng; rk_seed(rng, seed);
    std::vector<int> sym(n_symbols);
    for (int i = 0; i < n_symbols; i++) sym[i] = (int)rk_randint(rng, 0, 4);
    std::vector<double> pam4 = pam4_map(sym);

    std::vector<double> tx_out = tx_dsp_chain(pam4, sps_dsp, custom_taps);
    std::vector<double> x = dac_zoh(tx_out, sps_dac, sps_channel);
    double fs_analog = baud_rate * sps_channel;
    x = tx_frontend_lti(x, cfg, baud_rate, fs_analog, baud_rate / 2.0, nullptr, s4p);

    int skip = 200 * sps_channel;                    // 跳过滤波器暂态
    std::vector<double> seg;
    if ((int)x.size() > skip) seg.assign(x.begin() + skip, x.end());
    else seg = x;

    double mean = 0.0;
    for (double v : seg) mean += v;
    mean /= seg.size();
    double var = 0.0;
    for (double v : seg) var += (v - mean) * (v - mean);
    var /= seg.size();                               // 总体标准差（ddof=0）
    return std::sqrt(var);
}

// Model A 探针特征：(7-tap FIR / DRIVE_RMS_NOMINAL, drive_rms)
inline std::pair<std::vector<double>, double> extract_tx_features(const Config& cfg, const S4P* s4p,
                                                                  const std::vector<double>& custom_taps,
                                                                  int num_taps = 7) {
    std::vector<double> fir = extract_tx_s21(cfg, s4p, custom_taps, num_taps);
    for (auto& v : fir) v /= DRIVE_RMS_NOMINAL;
    return { fir, drive_rms(cfg, s4p, custom_taps) };
}

} // namespace dsh
