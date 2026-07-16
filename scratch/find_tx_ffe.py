import numpy as np
from main import run_sim
from utils_config import load_config
from rx_dsp import adaptive_ffe_dfe
import copy

def find_tx_ffe():
    config = load_config('config.xlsx')
    config['rx']['dfe_taps'] = 0
    config['channel']['snr_db'] = 50 # High SNR to find perfect channel inverse
    
    # We want to find a 9-tap Tx FFE. 
    # Since Tx FFE is T-spaced (1 sps), we can simulate a T-spaced Rx FFE to find the inverse.
    # Actually, we can just run the normal simulation with a 9-tap T-spaced Rx FFE.
    # But our Rx FFE is T/2 spaced. 
    # Let's just use scipy.optimize.minimize on the BER or MSE.
    pass

if __name__ == '__main__':
    find_tx_ffe()
