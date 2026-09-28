// test_probe_chain.cpp — 逐段打印 drive_rms 链路校验和。
#include "../src/physim.hpp"
#include "../src/optimizer.hpp"
#include <cstdio>
using namespace dsh;

int main() {
    Config cfg; cfg.load("cpp/config.txt");
    std::string s4p_path = cfg.s("channel.s4p_file", "");
    S4P nw; load_s4p(s4p_path, nw);

    std::vector<double> X = { -2.723665325067e-02, -2.922779653869e-01, -1.702005654973e-03, 5.501915279735e-02,
                              5.859391616050e+00, 1.734991920193e+00, -3.000000000000e-02 };
    std::vector<double> TAPS = { -2.723665325067e-02, -2.922779653869e-01, 6.237642229101070e-01,
                                 -1.702005654973e-03, 5.501915279735e-02 };
    apply_x_to_config(cfg, X[4], X[5], DRIVER_GAIN_NOMINAL * std::pow(10.0, X[6]));

    double baud = cfg.d("system.baud_rate", 56e9);
    int sps_dsp = cfg.i("system.sps_dsp", 2);
    int sps_dac = cfg.i("system.sps_dac", 2);
    int sps_ch = cfg.i("system.sps_channel", 8);
    double fs_analog = baud * sps_ch;
    int n_symbols = 4096;
    RkState rng; rk_seed(rng, 7);
    std::vector<int> sym(n_symbols);
    for (int i = 0; i < n_symbols; i++) sym[i] = (int)rk_randint(rng, 0, 4);
    auto pam4 = pam4_map(sym);
    auto tx_out = tx_dsp_chain(pam4, sps_dsp, TAPS);
    printf("S1 tx_dsp     %.15e\n", sumabs(tx_out));
    auto x = dac_zoh(tx_out, sps_dac, sps_ch);
    printf("S2 zoh        %.15e\n", sumabs(x));
    std::vector<double> x_s4p;
    double loss_db = cfg.d("channel.tx_pcb_loss_nyquist_db", cfg.d("channel.pcb_loss_nyquist_db", 15.0));
    apply_s4p_filter(nw, x, fs_analog, -std::fabs(loss_db), baud/2.0, x_s4p);
    printf("S3 s4p        %.15e\n", sumabs(x_s4p));
    double fb = baud;
    double f_z = fb/cfg.d("tx.ctle_fz_ratio",2.862), f_p1 = fb/cfg.d("tx.ctle_fp1_ratio",1.884), f_p2 = fb/cfg.d("tx.ctle_fp2_ratio",1.0);
    double f_lf = fb/cfg.d("tx.ctle_flf_ratio",40.0);
    auto x_ctle = apply_ctle(x_s4p, fs_analog, f_z, f_p1, f_p2, cfg.d("tx.ctle_g_dc_db",0.0), cfg.d("tx.ctle_g_dc2_db",0.0), f_lf);
    printf("S4 ctle       %.15e\n", sumabs(x_ctle));
    double gain = cfg.d("channel.driver_gain", 0.3399);
    std::vector<double> x_gain = x_ctle; for (auto& v : x_gain) v *= gain;
    printf("S5 gain       %.15e\n", sumabs(x_gain));
    auto x_bw = lowpass_filter(x_gain, cfg.d("channel.driver_bw", cfg.d("channel.mzm_bw",40e9)), fs_analog, 4);
    printf("S6 driver_bw  %.15e\n", sumabs(x_bw));
    int skip = 200 * sps_ch;
    std::vector<double> seg(x_bw.begin()+skip, x_bw.end());
    double mean = 0.0; for (double v : seg) mean += v; mean /= seg.size();
    double var = 0.0; for (double v : seg) var += (v-mean)*(v-mean); var /= seg.size();
    printf("S7 std        %.15e\n", std::sqrt(var));
    return 0;
}