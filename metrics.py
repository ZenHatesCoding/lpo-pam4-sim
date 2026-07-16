import numpy as np
import matplotlib
matplotlib.use('Agg') # prevent window popup
import matplotlib.pyplot as plt

def calculate_ber(tx_sym, rx_sym):
    """
    Calculate Symbol Error Rate and approximated Bit Error Rate
    Assumes standard PAM4 gray mapping (BER ~ SER/2 for Gray code)
    """
    # align signals, assuming they are already aligned by MLSE index
    errors = np.sum(tx_sym != rx_sym)
    ser = errors / len(tx_sym)
    ber = ser / 2.0 # Approximation for Gray mapped PAM4
    return ser, ber

import os

from scipy.signal import resample_poly

def plot_eye(y, sps, title="Eye Diagram", output_dir="diagnostic_results"):
    """
    Plot eye diagram
    y: oversampled signal
    sps: samples per symbol
    """
    target_sps = 50
    # Upsample the entire block for smooth plotting
    y_up = resample_poly(y, target_sps, sps)
    
    num_traces = min(1000, len(y_up) // target_sps - 2)
    
    plt.figure(figsize=(8, 6))
    for i in range(num_traces):
        start = i * target_sps
        end = start + 2 * target_sps
        if end < len(y_up):
            plt.plot(np.linspace(0, 2, 2*target_sps), y_up[start:end], color='b', alpha=0.1)
            
    plt.title(title)
    plt.xlabel("UI")
    plt.ylabel("Amplitude")
    plt.grid(True)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    filename = os.path.join(output_dir, title.replace(" ", "_") + ".png")
    plt.savefig(filename)
    plt.close()
