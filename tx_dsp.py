import numpy as np
from scipy import signal

def pam4_map(symbols):
    """ Map [0,1,2,3] to [-3, -1, 1, 3] """
    return symbols * 2 - 3

def upsample(x, sps):
    """ Upsample by inserting zeros """
    n = len(x)
    y = np.zeros(n * sps)
    y[::sps] = x
    return y

def tx_ctle(x, sps, baud_rate, dc_gain, peaking):
    """ Simple CTLE modeled via IIR filter """
    fs = baud_rate * sps
    # Simplistic continuous-time to discrete-time mapping for peaking
    # Using butterworth for simple roll-off and a peaking shelf
    wz = 2 * np.pi * (baud_rate / 4)
    wp = 2 * np.pi * (baud_rate / 2)
    
    num = [dc_gain / wz, dc_gain]
    den = [1 / wp, 1]
    
    b, a = signal.bilinear(num, den, fs=fs)
    y = signal.lfilter(b, a, x)
    return y

def tx_ffe(x, taps, sps):
    """ T-spaced Tx FFE applied to upsampled signal """
    w = np.zeros(len(taps) * sps)
    w[::sps] = taps
    # normalize
    w = w / np.sum(np.abs(w))
    y = np.convolve(x, w, mode='same')
    return y

def pulse_shape(x, sps):
    """ Rectangular pulse shaping (NRZ-like PAM4) """
    pulse = np.ones(sps)
    y = np.convolve(x, pulse, mode='full')[:len(x)]
    return y
