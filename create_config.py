import pandas as pd
import os

def generate_config():
    config = {
        'system': {
            'baud_rate': 56e9,        # 56 GBd (112G PAM4)
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
            'pcb_loss_nyquist_db': 15.0, # 15 dB loss at Nyquist for Host PCB trace
            'mzm_bw': 35e9,           # 35 GHz MZM bandwidth
            'fiber_length_km': 2.0,   # 2 km typical FR4 reach
            'fiber_loss_db_km': 0.4,  # 0.4 dB/km at 1310nm
            'pd_bw': 40e9,            # 40 GHz PD bandwidth
            'tia_bw': 35e9,           # 35 GHz TIA bandwidth
            'adc_bw': 35e9,           # 35 GHz ADC bandwidth
            'snr_db': 25,             # Additive electrical SNR
        },
        'rx': {
            'ffe_taps': 15,           # Number of Rx FFE taps (T/2 spaced)
            'ffe_pre': 3,             # Pre-cursor taps
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
