import numpy as np
import matplotlib.pyplot as plt
import skrf as rf
from utils_config import load_config
import os

def plot_s21():
    config = load_config('config.xlsx')
    s4p_path = config['channel']['s4p_file']
    nw = rf.Network(s4p_path)
    try:
        nw.se2gmm(p=2)
        sdd21 = nw.s[:, 1, 0]
    except:
        sdd21 = nw.s[:, 1, 0] if nw.s.shape[1] == 2 else nw.s[:, 0, 0]
        
    freqs = nw.f
    mag_db = 20 * np.log10(np.abs(sdd21))
    
    plt.figure()
    plt.plot(freqs / 1e9, mag_db)
    plt.title("Sdd21 Magnitude (Raw S4P)")
    plt.xlabel("Frequency (GHz)")
    plt.ylabel("Magnitude (dB)")
    plt.grid(True)
    plt.savefig("diagnostic_results/sdd21_raw.png")
    
    # Also plot the H_channel that our channel_imdd applies
    fs_analog = 212.5e9 * int(config['system']['sps_channel'])
    N = int(config['system']['num_symbols']) * int(config['system']['sps_channel'])
    f_sig = np.fft.rfftfreq(N, d=1.0/fs_analog)
    
    f_scale = config.get('s4p_f_scale', 1.0)
    f_sig_scaled = f_sig / f_scale
    
    sdd21_mag = np.interp(f_sig_scaled, freqs, np.abs(sdd21), left=np.abs(sdd21)[0], right=0.0)
    
    plt.figure()
    plt.plot(f_sig / 1e9, 20 * np.log10(sdd21_mag + 1e-12))
    plt.title(f"H_channel Magnitude (f_scale={f_scale})")
    plt.xlabel("Frequency (GHz)")
    plt.ylabel("Magnitude (dB)")
    plt.xlim(0, 150)
    plt.grid(True)
    plt.savefig("scratch/h_channel_applied.png")

if __name__ == '__main__':
    plot_s21()
