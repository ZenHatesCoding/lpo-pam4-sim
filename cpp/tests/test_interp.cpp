#include "../src/s4p.hpp"
#include <cstdio>
using namespace dsh;
int main() {
    S4P nw;
    load_s4p("models/lim_3ck_01_0319_c2m/lim/100G_C2M_channel_update_part1/Channel1/112G_16dB_(QSFPDD+module card)_TX7_L10/112G_cascaded_CDR6_Module_Thru_1_etch1100_TX7_L10_Full_Footprint.s4p", nw);
    std::vector<double> mag(nw.sdd21.size());
    for (size_t i = 0; i < mag.size(); i++) mag[i] = std::abs(nw.sdd21[i]);
    auto ph = unwrap(nw.sdd21);
    double test_f[] = {0.0, 1e6, 5e9, 12.3e9, 15.87e9, 20e9, 30e9, 45e9, 50e9, 60e9, 88e9, 127e9};
    std::vector<double> tf(test_f, test_f + 12);
    auto mi = interp(tf, nw.freq, mag, mag[0], 0.0);
    auto pi = interp(tf, nw.freq, ph, angle_c(nw.sdd21[0]), 0.0);
    for (int i = 0; i < 12; i++) printf("%.6e %.15e %.15e\n", tf[i], mi[i], pi[i]);
    printf("mag[0] %.16g\n", mag[0]);
    printf("angle[0] %.16g\n", angle_c(nw.sdd21[0]));
    printf("freqs[1] %.16g freqs[-1] %.16g\n", nw.freq[1], nw.freq.back());
    return 0;
}