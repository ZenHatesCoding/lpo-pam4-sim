// test_chan.cpp — 读 tx_out_noisy.bin，复刻 apply_channel 全链路，逐段打印 sum|x|。
#include "../src/physim.hpp"
#include <cstdio>
using namespace dsh;

int main() {
    std::ifstream f("cpp/build/tx_out_noisy.bin", std::ios::binary);
    std::vector<double> data;
    double v;
    while (f.read((char*)&v, sizeof(double))) data.push_back(v);

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

    std::vector<double> x = data;
    add_quantization_noise(x, cfg.d("channel.dac_enob", 0.0), rng);
    x = dac_zoh(x, sps_dac, sps_channel);
    printf("S01 zoh        %.12e\n", sumabs(x));

    double loss_db_tx = cfg.d("channel.tx_pcb_loss_nyquist_db", 10.0);
    std::vector<double> xs;
    apply_s4p_filter(nw, x, fs_analog, -std::fabs(loss_db_tx), nyquist, xs);
    x = xs;
    printf("S02 tx_s4p     %.12e\n", sumabs(x));
    double host_tx = cfg.d("channel.host_tx_noise_rms", 0.001);
    for (auto& vv : x) vv += rk_normal(rng, 0.0, host_tx);
    printf("S03 tx_hostn   %.12e\n", sumabs(x));
    double fb = baud_rate;
    x = apply_ctle(x, fs_analog, fb/cfg.d("tx.ctle_fz_ratio", 2.862), fb/cfg.d("tx.ctle_fp1_ratio", 1.884),
                   fb/cfg.d("tx.ctle_fp2_ratio", 1.0), cfg.d("tx.ctle_g_dc_db", 0.0),
                   cfg.d("tx.ctle_g_dc2_db", 0.0), fb/cfg.d("tx.ctle_flf_ratio", 40.0));
    printf("S04 tx_ctle    %.12e\n", sumabs(x));
    for (auto& vv : x) vv *= cfg.d("channel.driver_gain", 0.3399);
    x = lowpass_filter(x, cfg.d("channel.driver_bw", 40e9), fs_analog, 4);
    printf("S05 tx_driver  %.12e\n", sumabs(x));

    // E-O
    double P_in_W = std::pow(10.0, 3.0/10.0)/1000.0;
    double rin_linear = std::pow(10.0, cfg.d("channel.laser_rin_db_hz", -150.0)/10.0);
    double bw_noise = fs_analog/2.0;
    double var_rin = rin_linear*bw_noise*(P_in_W*P_in_W);
    double s_rin = std::sqrt(var_rin);
    std::vector<double> P_laser(x.size());
    for (size_t i = 0; i < x.size(); i++) { double p = P_in_W + rk_normal(rng,0.0,s_rin); P_laser[i] = p>0?p:0; }
    printf("S06 P_laser    %.12e\n", sumabs(P_laser));
    double linewidth = cfg.d("channel.laser_linewidth_hz", 0.0);
    double sd = std::sqrt(2.0*DSH_PI*linewidth/fs_analog);
    std::vector<double> phase_noise(x.size(), 0.0);
    double acc = 0.0;
    for (size_t i = 0; i < x.size(); i++) { acc += rk_normal(rng,0.0,sd); phase_noise[i]=acc; }
    std::vector<std::complex<double>> E_in(x.size());
    for (size_t i = 0; i < x.size(); i++) E_in[i] = std::complex<double>(std::sqrt(P_laser[i])*std::cos(phase_noise[i]), std::sqrt(P_laser[i])*std::sin(phase_noise[i]));
    printf("S07 E_in       %.12e\n", sumabs(E_in));
    double v_pi = cfg.d("channel.mzm_v_pi", 3.0), v_bias = cfg.d("channel.mzm_v_bias", 2.25), er = cfg.d("channel.mzm_er_db", 25.0);
    double e_r = std::pow(10.0, er/10.0), gamma = (1.0-1.0/std::sqrt(e_r))/2.0;
    std::vector<std::complex<double>> E_out(x.size());
    for (size_t i = 0; i < x.size(); i++) {
        double ph = DSH_PI*(x[i]+v_bias)/v_pi;
        E_out[i] = E_in[i]*(gamma*std::complex<double>(std::cos(ph),std::sin(ph)) + (1.0-gamma)*std::complex<double>(std::cos(-ph),std::sin(-ph)));
    }
    printf("S08 E_mzm      %.12e\n", sumabs(E_out));
    E_out = lowpass_complex(E_out, cfg.d("channel.mzm_bw", 40e9), fs_analog, 4);
    printf("S09 E_mzm_lpf  %.12e\n", sumabs(E_out));
    double loss_db = cfg.d("channel.fiber_length_km", 2.0)*cfg.d("channel.fiber_loss_db_km", 0.25);
    double sqrt_loss = std::sqrt(std::pow(10.0, -loss_db/20.0));
    for (auto& e : E_out) e *= sqrt_loss;
    printf("S10 E_fiber    %.12e\n", sumabs(E_out));
    E_out = apply_cd(E_out, fs_analog, cfg.d("channel.cd_ps_nm", 0.0));
    printf("S11 E_cd       %.12e\n", sumabs(E_out));
    std::vector<double> P_rx(E_out.size());
    for (size_t i = 0; i < E_out.size(); i++) P_rx[i] = std::norm(E_out[i]);
    printf("S12 P_rx       %.12e\n", sumabs(P_rx));
    P_rx = apply_dgd(P_rx, fs_analog, cfg.d("channel.dgd_ps", 0.0), cfg.d("channel.pol_angle_deg", 45.0));
    printf("S13 P_dgd      %.12e\n", sumabs(P_rx));
    double resp = cfg.d("channel.pin_responsivity", 0.6);
    double dark = cfg.d("channel.pin_dark_current_na", 10.0)*1e-9;
    std::vector<double> I_pd(P_rx.size());
    for (size_t i = 0; i < P_rx.size(); i++) I_pd[i] = resp*P_rx[i] + dark;
    printf("S14 I_pd       %.12e\n", sumabs(I_pd));
    double q = 1.602176634e-19, kB = 1.380649e-23;
    double var_thermal = 4.0*kB*cfg.d("channel.temperature_k", 298.15)/cfg.d("channel.rl_ohm", 50.0)*bw_noise;
    double s_thermal = std::sqrt(var_thermal);
    std::vector<double> I_pd_noisy(I_pd.size());
    for (size_t i = 0; i < I_pd.size(); i++) {
        double var_shot = 2.0*q*std::fabs(I_pd[i])*bw_noise;
        I_pd_noisy[i] = I_pd[i] + rk_normal(rng,0.0,std::sqrt(var_shot));
    }
    for (size_t i = 0; i < I_pd.size(); i++) {
        I_pd_noisy[i] += rk_normal(rng,0.0,s_thermal);
    }
    printf("S15 I_noisy    %.12e\n", sumabs(I_pd_noisy));
    I_pd_noisy = lowpass_filter(I_pd_noisy, cfg.d("channel.pd_bw", 40e9), fs_analog, 4);
    printf("S16 I_pd_lpf   %.12e\n", sumabs(I_pd_noisy));
    double tia_gain = cfg.d("channel.tia_gain_ohm", 720.0);
    std::vector<double> V_tia(I_pd_noisy.size());
    for (size_t i = 0; i < I_pd_noisy.size(); i++) V_tia[i] = I_pd_noisy[i]*tia_gain;
    double tia_noise_pa = cfg.d("channel.tia_noise_pa_rthz", 16.0)*1e-12;
    double var_tia = (tia_noise_pa*tia_noise_pa)*bw_noise;
    double s_tia = std::sqrt(var_tia)*tia_gain;
    for (auto& vv : V_tia) vv += rk_normal(rng,0.0,s_tia);
    printf("S17 V_tia      %.12e\n", sumabs(V_tia));
    V_tia = lowpass_filter(V_tia, cfg.d("channel.tia_bw", 40e9), fs_analog, 4);
    printf("S18 V_tia_lpf  %.12e\n", sumabs(V_tia));
    double mean = 0.0; for (double vv : V_tia) mean += vv; mean /= V_tia.size();
    for (auto& vv : V_tia) vv -= mean;
    double var = 0.0; for (double vv : V_tia) var += vv*vv; var /= V_tia.size();
    double rms = std::sqrt(var);
    if (rms > 1e-12) { double sc = std::sqrt(5.0)/rms; for (auto& vv : V_tia) vv *= sc; }
    printf("S19 AGC        %.12e\n", sumabs(V_tia));
    std::vector<double> xr = V_tia;
    double loss_db_rx = cfg.d("channel.rx_pcb_loss_nyquist_db", 15.0);
    std::vector<double> xr2;
    apply_s4p_filter(nw, xr, fs_analog, -std::fabs(loss_db_rx), nyquist, xr2);
    xr = xr2;
    printf("S20 rx_s4p     %.12e\n", sumabs(xr));
    double host_rx = cfg.d("channel.host_rx_noise_rms", 0.001);
    for (auto& vv : xr) vv += rk_normal(rng,0.0,host_rx);
    printf("S21 rx_hostn   %.12e\n", sumabs(xr));
    xr = apply_ctle(xr, fs_analog, fb/cfg.d("channel.rx_ctle_fz_ratio", 2.862), fb/cfg.d("channel.rx_ctle_fp1_ratio", 1.884),
                    fb/cfg.d("channel.rx_ctle_fp2_ratio", 1.0), cfg.d("channel.rx_ctle_g_dc_db", 6.0),
                    cfg.d("channel.rx_ctle_g_dc2_db", 3.0), fb/cfg.d("channel.rx_ctle_flf_ratio", 40.0));
    printf("S22 rx_ctle    %.12e\n", sumabs(xr));
    std::vector<double> x_adc_in = lowpass_filter(xr, cfg.d("channel.adc_bw", 40e9), fs_analog, 4);
    printf("S23 adc_lpf    %.12e\n", sumabs(x_adc_in));
    int dec = sps_channel/sps_adc;
    std::vector<double> x_adc_out(x_adc_in.size()/dec);
    for (size_t i = 0; i < x_adc_out.size(); i++) x_adc_out[i] = x_adc_in[i*dec];
    add_quantization_noise(x_adc_out, cfg.d("channel.adc_enob", 0.0), rng);
    printf("S24 rx_adc     %.12e\n", sumabs(x_adc_out));
    return 0;
}