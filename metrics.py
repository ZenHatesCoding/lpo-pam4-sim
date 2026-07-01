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

def plot_eye(y, sps, title="Eye Diagram"):
    """
    Plot eye diagram
    y: oversampled signal
    sps: samples per symbol
    """
    num_traces = min(1000, len(y) // sps - 2)
    
    plt.figure(figsize=(8, 6))
    for i in range(num_traces):
        start = i * sps
        end = start + 2 * sps
        if end < len(y):
            plt.plot(np.linspace(0, 2, 2*sps), y[start:end], color='b', alpha=0.1)
            
    plt.title(title)
    plt.xlabel("UI")
    plt.ylabel("Amplitude")
    plt.grid(True)
    plt.savefig(title.replace(" ", "_") + ".png")
    plt.close()
