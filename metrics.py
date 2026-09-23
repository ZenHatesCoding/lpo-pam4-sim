import os

import numpy as np
import matplotlib
matplotlib.use('Agg')  # prevent window popup
import matplotlib.pyplot as plt
from scipy.signal import resample_poly, welch


def _symbols_to_gray_bits(sym):
    """PAM4 symbol index [0,1,2,3] -> 2 Gray bits (value = s ^ (s >> 1)).

    标准 Gray 映射：符号 0/1/2/3 -> 00/01/11/10，相邻电平只差 1 bit。
    返回 (lsb, msb) 两个 bit 向量，逐位比较即可得真逐位 BER。
    """
    s = np.asarray(sym, dtype=int)
    g = s ^ (s >> 1)          # 整数 Gray 码 0/1/3/2
    return (g & 1), (g >> 1)


def calculate_ber(tx_sym, rx_sym):
    """真逐位 BER（Gray 映射 PAM4）+ 符号错误率（诊断用）。

    信号已在 MLSE 索引对齐后传入。ser = 符号错误数 / 符号总数（诊断）；
    ber = 位错误数 / 总位数（2 bit / 符号，标准 Gray 码逐位比较），
    不再使用「SER/2 近似」——该近似只在高误码接近真值，次优起点 ~1e-3
    量级会低估真实逐位 BER。
    """
    tx_sym = np.asarray(tx_sym, dtype=int)
    rx_sym = np.asarray(rx_sym, dtype=int)
    ser = float(np.mean(tx_sym != rx_sym))
    tx_lsb, tx_msb = _symbols_to_gray_bits(tx_sym)
    rx_lsb, rx_msb = _symbols_to_gray_bits(rx_sym)
    bit_errors = int(np.sum(tx_lsb != rx_lsb) + np.sum(tx_msb != rx_msb))
    ber = bit_errors / (2.0 * tx_sym.size)
    return ser, ber


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


def plot_spectrum(signal, fs, title="Spectrum", output_dir="diagnostic_results"):
    """
    Plot Power Spectral Density (PSD) using Welch's method
    """
    f, Pxx = welch(signal, fs, nperseg=1024, return_onesided=True)

    plt.figure(figsize=(8, 6))
    plt.plot(f / 1e9, 10 * np.log10(Pxx), color='r')
    plt.title(title)
    plt.xlabel("Frequency (GHz)")
    plt.ylabel("PSD (dB/Hz)")
    plt.grid(True)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    filename = os.path.join(output_dir, title.replace(" ", "_") + ".png")
    plt.savefig(filename)
    plt.close()
