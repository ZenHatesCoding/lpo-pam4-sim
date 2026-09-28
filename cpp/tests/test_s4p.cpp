#include "../src/s4p.hpp"
#include <cstdio>
using namespace dsh;
int main() {
    S4P nw;
    bool ok = load_s4p("models/lim_3ck_01_0319_c2m/lim/100G_C2M_channel_update_part1/Channel1/112G_16dB_(QSFPDD+module card)_TX7_L10/112G_cascaded_CDR6_Module_Thru_1_etch1100_TX7_L10_Full_Footprint.s4p", nw);
    printf("ok=%d nfreq=%zu\n", ok, nw.freq.size());
    if (ok) {
        printf("f[0]=%.17g f[-1]=%.17g\n", nw.freq[0], nw.freq[nw.freq.size()-1]);
        printf("sdd21[0]=(%.17g, %.17g)\n", nw.sdd21[0].real(), nw.sdd21[0].imag());
        printf("sdd21[-1]=(%.17g, %.17g)\n", nw.sdd21.back().real(), nw.sdd21.back().imag());
        double fs10 = find_f_scale_for_target_il(nw.freq, nw.sdd21, -10.0, 28e9);
        double fs14 = find_f_scale_for_target_il(nw.freq, nw.sdd21, -14.0, 28e9);
        printf("f_scale@10dB=%.17g\n", fs10);
        printf("f_scale@14dB=%.17g\n", fs14);
    }
    return 0;
}