# -*- coding: utf-8 -*-
"""tools/calibrate_driver_gain.py — 标定 driver_gain 的名义值。

定义（v4 口径）：
  在基线环境（Tx/Rx 插损 = 10 dB）+ 种子 FFE/CTLE 下，driver_gain = g0 时，
  进入 MZM 的驱动摆幅恰好等于 driver_vpp = 0.617 V（PAM4 Vpp，即 RMS = 0.617*0.3726）。

链路：FFE -> DAC(ZOH) -> Tx 电插损(S4P) -> TX CTLE -> Driver(gain) -> Driver 带限
（无 VGA、无任何 RMS 归一化），因此整条链对 gain 线性 ⇒ g0 可一次算出。

用法：
  python tools/calibrate_driver_gain.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import create_config                     # noqa: E402
import utils_config                      # noqa: E402
import ddps_optimizer as D               # noqa: E402
from ddps_cases import apply_env_to_config, env_case   # noqa: E402
from channel_imdd import (dac_zoh, tx_frontend_lti, DRIVER_VPP_NOMINAL,   # noqa: E402
                          PAM4_RMS_FACTOR)
from tx_dsp import pam4_map, tx_dsp_chain   # noqa: E402


def main():
    if not os.path.exists('config.xlsx'):
        create_config.generate_config()
    base = utils_config.load_config('config.xlsx')
    cfg = apply_env_to_config(base, env_case('Base_IL10x10'))

    baud = cfg['system']['baud_rate']
    sps_dsp = int(cfg['system']['sps_dsp'])
    sps_dac = int(cfg['system']['sps_dac'])
    sps_ch = int(cfg['system']['sps_channel'])
    fs = baud * sps_ch

    rng = np.random.RandomState(7)
    pam4 = pam4_map(rng.randint(0, 4, 4096))
    tx_config = cfg['tx'].copy()
    tx_config['custom_taps'] = D.SEED_TAPS
    x = dac_zoh(tx_dsp_chain(pam4, sps_dsp, baud, tx_config), sps_dac, sps_ch)

    cfg['channel']['driver_gain'] = 1.0
    y = tx_frontend_lti(x, cfg, baud, fs, baud / 2, rng=None)
    skip = 200 * sps_ch
    rms_at_unity = float(np.std(y[skip:]))

    target_rms = DRIVER_VPP_NOMINAL * PAM4_RMS_FACTOR
    g0 = target_rms / rms_at_unity
    print('drive RMS @ gain=1.0 : %.6f V  (PAM4 Vpp = %.4f V)'
          % (rms_at_unity, rms_at_unity / PAM4_RMS_FACTOR))
    print('target  RMS (0.617Vpp): %.6f V' % target_rms)
    print('=> DRIVER_GAIN_NOMINAL = %.4f' % g0)

    cfg['channel']['driver_gain'] = g0
    y2 = tx_frontend_lti(x, cfg, baud, fs, baud / 2, rng=None)
    rms2 = float(np.std(y2[skip:]))
    print('check  drive RMS @ g0 : %.6f V  (PAM4 Vpp = %.4f V)'
          % (rms2, rms2 / PAM4_RMS_FACTOR))


if __name__ == '__main__':
    main()
