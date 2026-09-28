// test_txfront.cpp — 读 tx_out_noisy.bin，复刻 Tx 前端各阶段并打印校验和。
#include "../src/physim.hpp"
#include <cstdio>
using namespace dsh;

int main() {
    // 读二进制输入
    std::ifstream f("cpp/build/tx_out_noisy.bin", std::ios::binary);
    std::vector<double> data;
    double v;
    while (f.read((char*)&v, sizeof(double))) data.push_back(v);
    printf("loaded len=%zu sumabs=%.12e\n", data.size(), sumabs(data));

    Config cfg; cfg.load("cpp/config.txt");
    double baud_rate = cfg.d("system.baud_rate", 56e9);
    int sps_dac = cfg.i("system.sps_dac", 2);
    int sps_channel = cfg.i("system.sps_channel", 8);
    int sps_adc = cfg.i("system.sps_adc", 2);
    double nyquist = baud_rate / 2.0;
    double fs_analog = baud_rate * sps_channel;

    std::string s4p_path = cfg.s("channel.s4p_file", "");
    S4P nw; load_s4p(s4p_path, nw);

    int ch_seed = cfg.i("channel.seed", 123);
    RkState rng; rk_seed(rng, (unsigned)ch_seed);

    // 1) DAC quant + ZOH
    std::vector<double> x = data;
    add_quantization_noise(x, cfg.d("channel.dac_enob", 0.0), rng);
    x = dac_zoh(x, sps_dac, sps_channel);
    printf("after zoh sumabs=%.12e\n", sumabs(x));

    // 2) S4P IL
    double loss_db = cfg.d("channel.tx_pcb_loss_nyquist_db", 10.0);
    std::vector<double> xs;
    apply_s4p_filter(nw, x, fs_analog, -std::fabs(loss_db), nyquist, xs);
    printf("after s4p sumabs=%.12e\n", sumabs(xs));
    x = xs;

    // 3) host noise
    double host_tx = cfg.d("channel.host_tx_noise_rms", 0.001);
    for (auto& vv : x) vv += rk_normal(rng, 0.0, host_tx);
    printf("after hostnoise sumabs=%.12e\n", sumabs(x));

    // 4) CTLE
    double fb = baud_rate;
    double f_z = fb / cfg.d("tx.ctle_fz_ratio", 2.862);
    double f_p1 = fb / cfg.d("tx.ctle_fp1_ratio", 1.884);
    double f_p2 = fb / cfg.d("tx.ctle_fp2_ratio", 1.0);
    double f_lf = fb / cfg.d("tx.ctle_flf_ratio", 40.0);
    x = apply_ctle(x, fs_analog, f_z, f_p1, f_p2, cfg.d("tx.ctle_g_dc_db", 0.0),
                   cfg.d("tx.ctle_g_dc2_db", 0.0), f_lf);
    printf("after ctle sumabs=%.12e\n", sumabs(x));

    // 5) driver gain + BW
    double gain = cfg.d("channel.driver_gain", 0.3399);
    for (auto& vv : x) vv *= gain;
    printf("after gain sumabs=%.12e\n", sumabs(x));
    x = lowpass_filter(x, cfg.d("channel.driver_bw", 40e9), fs_analog, 4);
    printf("after driverbw sumabs=%.12e\n", sumabs(x));
    return 0;
}