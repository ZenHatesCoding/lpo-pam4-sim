import pandas as pd

def generate_config():
    config = {
        'system': {
            'baud_rate': 56e9,        # 56 GBd (112G PAM4)
            'sps_sim': 50,            # 50 samples per symbol for analog simulation
            'sps_dsp': 2,             # DSP operates at 2 sps
            'num_symbols': 10000      # Number of symbols to simulate
        },
        'tx': {
            'ctle_dc_gain': 0.8,      # Simple CTLE dc gain
            'ctle_peaking': 2.0,      # High frequency peaking
            'ffe_taps': 5,            # Number of Tx FFE taps
            'ffe_pre': 1              # Pre-cursor taps
        },
        'channel': {
            'mzm_bw': 35e9,           # 35 GHz MZM bandwidth
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
