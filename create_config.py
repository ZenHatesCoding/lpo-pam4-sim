import pandas as pd
import argparse
import os

# ==========================================
# 🚀 核心全局开关 (一键切换物理底层模式)
# 可选值: '112G', '224G', '448G'
# ==========================================
DEFAULT_MODE = '112G'

def generate_config(mode=DEFAULT_MODE):
    print(f"Generating config for {mode} mode...")
    
    if mode == '112G':
        baud_rate = 56e9
        optics_bw = 40e9
        s4p_file = 'models/lim_3ck_01_0319_c2m/lim/100G_C2M_channel_update_part1/Channel1/112G_16dB_(QSFPDD+module card)_TX7_L10/112G_cascaded_CDR6_Module_Thru_1_etch1100_TX7_L10_Full_Footprint.s4p'
        target_il = None # Authentic IEEE 802.3ck file, no artificial scaling
    elif mode == '224G':
        baud_rate = 112.5e9
        optics_bw = 80e9
        s4p_file = 'models/li_dj_CR_DesignA_060523/li_dj_CR_Design_A_Rev1_THRU.s4p'
        target_il = None # Authentic IEEE 802.3dj file, no artificial scaling
    elif mode == '448G':
        baud_rate = 212.5e9
        optics_bw = 150e9
        s4p_file = 'models/li_dj_CR_DesignA_060523/li_dj_CR_Design_A_Rev1_THRU.s4p'
        target_il = -18.0 # No authentic 448G file exists yet. Using ZTE frequency scaling method on 802.3dj file to hit -18dB @ 106GHz.
    else:
        raise ValueError("Invalid mode. Choose from '112G', '224G', '448G'.")

    config = {
        'system': {
            'baud_rate': baud_rate,     
            'sps_dsp': 2,             
            'sps_dac': 2,             
            'sps_channel': 8,         
            'sps_adc': 2,             
            'enable_eye_plot': False,
            'enable_spectrum_plot': False,
            'num_symbols': 65536      
        },
        'tx': {
            'baud_rate': baud_rate,        
            'sps_dac': 2,
            'levels': 4,              
            'pattern_length': 65536,
            'ffe_taps': 9,            
            'ffe_spacing': 1,         
            'custom_taps': "[0.0, 0.0, 0.0, -0.2987, 0.7012, 0.0, 0.0, 0.0, 0.0]", 
            'optimizer_type': 'SHC', 
        },
        'channel': {
            'sps_channel': 8,
            'snr_db': 26.5,           
            
            'use_s4p': True,
            's4p_file': s4p_file,
            's4p_f_scale': 1.0, 
            
            'mzm_bw': optics_bw,           
            'fiber_length_km': 2.0,   
            'fiber_loss_db_km': 0.25, 
            'pd_bw': optics_bw,            
            'tia_bw': optics_bw,           
            'adc_bw': optics_bw,
            
            # Analog Equalization (CTLE)
            'use_ctle': True,
            'ctle_fz_ratio': 2.5,
            'ctle_fp1_ratio': 2.5,
            'ctle_fp2_ratio': 1.0,
            'ctle_g_dc_db': 0.0,
            
            # Debug toggle
            'disable_isi': False,
        },
        'rx': {
            'sps_adc': 2,
            'ffe_taps': 31,           
            'ffe_spacing': 0.5,       
            'ffe_pre': 8,
            'ffe_mu': 1e-4,  
            'lms_mu': 1e-4,  
            'train_len': 10000,
            'dfe_taps': 0,            
            'mlse_memory': 1,         
        }
    }
    
    if target_il is not None:
        config['channel']['target_il_nyquist_db'] = target_il

    with pd.ExcelWriter('config.xlsx') as writer:
        for sheet_name, params in config.items():
            df = pd.DataFrame(list(params.items()), columns=['Parameter', 'Value'])
            df.to_excel(writer, sheet_name=sheet_name, index=False)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate simulation config')
    parser.add_argument('--mode', type=str, choices=['112G', '224G', '448G'], default=DEFAULT_MODE, help='Speed mode')
    args = parser.parse_args()
    
    generate_config(args.mode)
    print("config.xlsx created.")
