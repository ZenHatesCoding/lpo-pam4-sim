import pandas as pd
import argparse
import os

# ==========================================
# 🚀 核心全局开关 (一键切换物理底层模式)
# 可选值: '112G', '224G', '448G'
# ==========================================
DEFAULT_MODE = '112G'

# ==========================================
# LPO 标准模式开关
# ==========================================
LPO_MODE = True  # True: 使用典型 LPO (分布式噪声, Tx/Rx 插损分别为 10dB)；False: 传统模式

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
            'target_case': 'case_baseline', # Pointer to a row in stress_cases
            'baud_rate': baud_rate,     
            'sps_dsp': 2,             
            'sps_dac': 2,             
            'sps_channel': 8,         
            'sps_adc': 2,             
            'enable_eye_plot': True,
            'enable_spectrum_plot': True,
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
            'optimize_mode': 'JOINT',
            'safe_bo_max_log_ber': -3.0, # (e.g. -3.0 for 1e-3). Set to None to disable Safe-BO
            # Analog Equalization (Tx CTLE)
            'use_ctle': True,
            'ctle_fz_ratio': 2.5,
            'ctle_fp1_ratio': 2.5,
            'ctle_fp2_ratio': 1.0,
            'ctle_flf_ratio': 40.0,
            'ctle_g_dc_db': 0.0,
            'ctle_g_dc2_db': 0.0,
        },
        'channel': {
            'sps_channel': 8,
            
            # --- Electrical Channel Insertion Loss ---
            'tx_pcb_loss_nyquist_db': 7.0 if LPO_MODE else 15.0,
            'rx_pcb_loss_nyquist_db': 7.0 if LPO_MODE else 15.0,
            
            # --- Physical Device Parameters (SJTU Model) ---
            'driver_vpp': 0.617,          # Volts (Optimal swing for linear MZM region)
            'laser_rin_db_hz': -150.0,    # dB/Hz
            'mzm_v_pi': 3.0,              # Volts
            'mzm_v_bias': 2.25,           # Volts
            'mzm_er_db': 25.0,            # dB
            'pin_responsivity': 0.6,      # A/W
            'pin_dark_current_na': 10.0,  # nA
            'temperature_k': 298.15,      # Kelvin
            'rl_ohm': 50.0,               # Ohms
            'tia_gain_ohm': 720.0,        # Ohms
            'tia_noise_pa_rthz': 16.0,    # pA/sqrt(Hz)
            
            # --- Added legacy host noise for frontend ---
            'host_rx_noise_rms': 0.001,   # 1mV RMS for Tx/Rx generic noise
            'host_tx_noise_rms': 0.001,   # 1mV RMS for Tx/Rx generic noise
            
            'use_s4p': True,
            's4p_file': s4p_file,
            's4p_f_scale': 1.0, 
            
            'mzm_bw': optics_bw,           
            'fiber_length_km': 2.0,   
            'fiber_loss_db_km': 0.25, 
            'pd_bw': optics_bw,            
            'tia_bw': optics_bw,           
            'adc_bw': optics_bw,
            
            # Debug toggle
            'disable_isi': False,
        },
        'rx': {
            'sps_adc': 2,
            # LPO MSA Spec 9.10 specifies: 22-tap T-spaced FFE and 1-tap DFE
            'ffe_taps': 22 if LPO_MODE else 31,
            'ffe_spacing': 1.0 if LPO_MODE else 0.5,
            'ffe_pre': 6 if LPO_MODE else 8,
            'ffe_mu': 1e-4,
            'lms_mu': 1e-4,
            'train_len': 10000,
            'dfe_taps': 1 if LPO_MODE else 0,
            # Standard reference equalizer does not use MLSE
            'mlse_memory': 0 if LPO_MODE else 1,
        }
    }
    
    # Define physical stress cases
    stress_cases = [
        {'case_id': 'case_baseline', 'cd_ps_nm': 0.0, 'dgd_ps': 0.0, 'pol_angle_deg': 0.0, 'laser_rin_db_hz': -150.0, 'mzm_er_db': 25.0, 'tia_noise_pa_rthz': 16.0, 'tx_pcb_loss_nyquist_db': 7.0, 'rx_pcb_loss_nyquist_db': 7.0},
        {'case_id': 'case_cd_dgd_stress', 'cd_ps_nm': 28.0, 'dgd_ps': 5.0, 'pol_angle_deg': 45.0, 'laser_rin_db_hz': -150.0, 'mzm_er_db': 25.0, 'tia_noise_pa_rthz': 16.0, 'tx_pcb_loss_nyquist_db': 7.0, 'rx_pcb_loss_nyquist_db': 7.0},
        {'case_id': 'case_high_loss', 'cd_ps_nm': 0.0, 'dgd_ps': 0.0, 'pol_angle_deg': 0.0, 'laser_rin_db_hz': -150.0, 'mzm_er_db': 25.0, 'tia_noise_pa_rthz': 16.0, 'tx_pcb_loss_nyquist_db': 12.0, 'rx_pcb_loss_nyquist_db': 12.0},
        {'case_id': 'case_high_noise', 'cd_ps_nm': 0.0, 'dgd_ps': 0.0, 'pol_angle_deg': 0.0, 'laser_rin_db_hz': -140.0, 'mzm_er_db': 15.0, 'tia_noise_pa_rthz': 25.0, 'tx_pcb_loss_nyquist_db': 7.0, 'rx_pcb_loss_nyquist_db': 7.0},
        {'case_id': 'case_combined_stress', 'cd_ps_nm': 15.0, 'dgd_ps': 3.0, 'pol_angle_deg': 45.0, 'laser_rin_db_hz': -142.0, 'mzm_er_db': 18.0, 'tia_noise_pa_rthz': 20.0, 'tx_pcb_loss_nyquist_db': 10.0, 'rx_pcb_loss_nyquist_db': 10.0},
    ]
    
    if target_il is not None and not LPO_MODE:
        config['channel']['tx_pcb_loss_nyquist_db'] = target_il
        config['channel']['rx_pcb_loss_nyquist_db'] = target_il

    with pd.ExcelWriter('config.xlsx') as writer:
        # Write basic param sheets
        for sheet_name, params in config.items():
            df = pd.DataFrame(list(params.items()), columns=['Parameter', 'Value'])
            df.to_excel(writer, sheet_name=sheet_name, index=False)
        # Write stress_cases sheet
        df_stress = pd.DataFrame(stress_cases)
        df_stress.to_excel(writer, sheet_name='stress_cases', index=False)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate simulation config')
    parser.add_argument('--mode', type=str, choices=['112G', '224G', '448G'], default=DEFAULT_MODE, help='Speed mode')
    args = parser.parse_args()
    
    generate_config(args.mode)
    print("config.xlsx created.")
