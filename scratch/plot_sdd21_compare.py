import numpy as np
import matplotlib.pyplot as plt
import skrf as rf
from utils_config import load_config
import os

def plot_s21():
    config = load_config('config.xlsx')
    s4p_path = config['channel']['s4p_file']
    nw = rf.Network(s4p_path)
    
    # 1. skrf se2gmm
    nw_copy = nw.copy()
    try:
        nw_copy.se2gmm(p=2)
        sdd21_skrf = nw_copy.s[:, 1, 0]
    except:
        sdd21_skrf = nw_copy.s[:, 1, 0] if nw.s.shape[1] == 2 else nw.s[:, 0, 0]
        
    # 2. Manual calculation assuming 1=In+, 3=In-, 2=Out+, 4=Out-
    S21 = nw.s[:, 1, 0]
    S23 = nw.s[:, 1, 2]
    S41 = nw.s[:, 3, 0]
    S43 = nw.s[:, 3, 2]
    sdd21_manual_13_24 = 0.5 * (S21 - S23 - S41 + S43)
    
    # 3. Manual calculation assuming 1=In+, 2=In-, 3=Out+, 4=Out-
    S31 = nw.s[:, 2, 0]
    S32 = nw.s[:, 2, 1]
    S41 = nw.s[:, 3, 0]
    S42 = nw.s[:, 3, 1]
    sdd21_manual_12_34 = 0.5 * (S31 - S32 - S41 + S42)
    
    freqs = nw.f / 1e9
    
    plt.figure()
    plt.plot(freqs, 20 * np.log10(np.abs(sdd21_skrf) + 1e-12), label="skrf se2gmm Sdd21", alpha=0.5)
    plt.plot(freqs, 20 * np.log10(np.abs(sdd21_manual_13_24) + 1e-12), label="Manual 1&3 -> 2&4", alpha=0.5)
    plt.plot(freqs, 20 * np.log10(np.abs(sdd21_manual_12_34) + 1e-12), label="Manual 1&2 -> 3&4", alpha=0.5)
    plt.legend()
    plt.title("Sdd21 Comparison")
    plt.xlabel("Frequency (GHz)")
    plt.ylabel("Magnitude (dB)")
    plt.grid(True)
    plt.savefig("diagnostic_results/sdd21_comparison.png")

if __name__ == '__main__':
    plot_s21()
