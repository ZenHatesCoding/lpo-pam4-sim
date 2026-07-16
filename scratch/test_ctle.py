import numpy as np
import matplotlib.pyplot as plt
import sys

def apply_ctle(fs, f_z, f_p1, f_p2, g_dc_db):
    f = np.linspace(0, 150e9, 1000)
    g_dc = 10**(g_dc_db / 20)
    num = g_dc + 1j * f / f_z
    den = (1 + 1j * f / f_p1) * (1 + 1j * f / f_p2)
    H_ctle = num / den
    
    plt.figure()
    plt.plot(f/1e9, 20*np.log10(np.abs(H_ctle)))
    plt.title('CTLE Frequency Response')
    plt.xlabel('Frequency (GHz)')
    plt.ylabel('Magnitude (dB)')
    plt.grid(True)
    plt.savefig('diagnostic_results/ctle_response.png')
    print("CTLE response plotted.")

if __name__ == "__main__":
    f_b = 212.5e9
    f_z = f_b / 2.5
    f_p1 = f_b / 2.5
    f_p2 = f_b / 1.0
    apply_ctle(f_b*8, f_z, f_p1, f_p2, -12.0)
