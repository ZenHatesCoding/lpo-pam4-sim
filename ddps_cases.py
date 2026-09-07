# -*- coding: utf-8 -*-
"""ddps_cases.py — DDPS v2 统一的环境用例清单与配置改写工具。

数据收集（dataset_generator）、在线调优测试（test_generalization）与可视化报告
（report_ddps_v2）共用同一份环境定义，保证"训练-测试-报告"口径一致。

每个环境 = (名称, Tx/Rx 奈奎斯特插损 dB, CD ps/nm, DGD ps, 偏振角 deg)。
"""
import copy

# ---------------------------------------------------------------------------
# DDPS v2 物理应力环境清单（与既有 test_generalization 用例一致，供横向对比）
# ---------------------------------------------------------------------------
ENV_CASES = [
    {"name": "Base_IL10",       "il": 10.0, "cd": 0.0,  "dgd": 0.0, "pol": 0.0},
    {"name": "IL_Sweep_14dB",   "il": 14.0, "cd": 0.0,  "dgd": 0.0, "pol": 0.0},
    {"name": "IL_Worst_20dB",   "il": 20.0, "cd": 0.0,  "dgd": 0.0, "pol": 0.0},
    {"name": "CD_Sweep_15ps",   "il": 10.0, "cd": 15.0, "dgd": 0.0, "pol": 0.0},
    {"name": "CD_Sweep_28ps",   "il": 10.0, "cd": 28.0, "dgd": 0.0, "pol": 0.0},
    {"name": "DGD_Sweep_2ps",   "il": 10.0, "cd": 0.0,  "dgd": 2.0, "pol": 45.0},
    {"name": "DGD_Sweep_5ps",   "il": 10.0, "cd": 0.0,  "dgd": 5.0, "pol": 45.0},
    {"name": "Combined_Stress", "il": 20.0, "cd": 15.0, "dgd": 5.0, "pol": 45.0},
]

# 默认"训练锚定环境"组合（Base 密集 + 其余环境稀疏锚点）
BASE_ENV = "Base_IL10"


def env_case(name):
    for c in ENV_CASES:
        if c["name"] == name:
            return dict(c)
    raise KeyError(f"unknown env case: {name}")


def apply_env_to_config(config, env):
    """把某个环境(名称或 dict)的物理参数覆盖到 config 副本上，返回新 config。"""
    cfg = copy.deepcopy(config)
    if isinstance(env, str):
        env = env_case(env)
    cfg["channel"]["tx_pcb_loss_nyquist_db"] = float(env["il"])
    cfg["channel"]["rx_pcb_loss_nyquist_db"] = float(env["il"])
    cfg["channel"]["cd_ps_nm"] = float(env["cd"])
    cfg["channel"]["dgd_ps"] = float(env["dgd"])
    cfg["channel"]["pol_angle_deg"] = float(env["pol"])
    cfg["system"]["enable_eye_plot"] = False
    cfg["system"]["enable_spectrum_plot"] = False
    return cfg
