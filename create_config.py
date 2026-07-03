import pandas as pd
import os

def generate_config():
    config = {
        'system': {
            'baud_rate': 212.5e9,     # 212.5 GBd (448G PAM4/PAM6)
            'sps_dsp': 2,             # DSP operates at 2 sps
            'sps_dac': 2,             # DAC operates at 2 sps
            'sps_channel': 8,         # Analog channel simulation at 8 sps
            'sps_adc': 2,             # ADC operates at 2 sps
            'num_symbols': 10000      # Number of symbols to simulate
        },
        'tx': {
            'ctle_dc_gain': 0.8,      # Simple CTLE dc gain
            'ctle_peaking': 2.0,      # High frequency peaking
            'ffe_taps': 9,            # Number of Tx FFE taps
            'ffe_pre': 4              # Pre-cursor taps (center symmetric at index 4)
        },
        'channel': {
            'pcb_loss_nyquist_db': 15.0, # 15 dB loss at Nyquist for Host PCB trace (if analytical)
            'use_s4p': True,          # Use S-parameter file instead of analytical PCB loss
            's4p_file': 'models/li_dj_CR_DesignA_060523/li_dj_CR_Design_A_Rev1_THRU.s4p',

            'mzm_bw': 110e9,          # 110 GHz MZM bandwidth (scaled up for 448G)
            'fiber_length_km': 2.0,   # 2 km typical FR4 reach
            'fiber_loss_db_km': 0.4,  # 0.4 dB/km at 1310nm
            'pd_bw': 110e9,           # 110 GHz PD bandwidth
            'tia_bw': 110e9,          # 110 GHz TIA bandwidth
            'adc_bw': 110e9,          # 110 GHz ADC bandwidth
            'snr_db': 25,             # Additive electrical SNR
            'use_ctle': True,         # Enable analog CTLE
            'ctle_g_dc_db': -12.0,    # -12 dB DC gain (12 dB high frequency peaking)
            'ctle_fz_ratio': 2.5,     # fb / 2.5
            'ctle_fp1_ratio': 2.5,    # fb / 2.5
            'ctle_fp2_ratio': 1.0,    # fb / 1.0
        },
        'rx': {
            'ffe_taps': 31,           # Number of Rx FFE taps (T/2 spaced)
            'ffe_pre': 8,             # Pre-cursor taps
            'lms_mu': 1e-3,           # LMS step size
            'train_len': 2000,        # Number of symbols for training
            'mlse_memory': 1          # MLSE memory length (e.g. 1 means 1+a*z^-1)
        }
    }

    with pd.ExcelWriter('config.xlsx') as writer:
        for sheet_name, params in config.items():
            df = pd.DataFrame(list(params.items()), columns=['Parameter', 'Value'])
            df.to_excel(writer, sheet_name=sheet_name, index=False)

if __name__ == '__main__':
    generate_config()
    print("config.xlsx created.")
