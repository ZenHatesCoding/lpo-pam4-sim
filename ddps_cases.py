# -*- coding: utf-8 -*-
"""ddps_cases.py — DDPS v3 统一的环境用例清单与配置改写工具。

数据收集（dataset_generator）、在线调优测试（test_generalization）与可视化报告
（report_ddps_v3）共用同一份环境定义，保证"训练-测试-报告"口径一致。

v3 相对 v2 的变化：
  1. **Tx / Rx 插损可独立配置**（v2 只有单一 IL，Tx=Rx 恒等）。Host 侧与 Module 侧
     的通道损耗在真实系统里并不对称，非对称用例能暴露"均衡该放在链路哪一段"的差异。
  2. 用例数量增加：对称插损、非对称插损、色散、群时延、复合应力、以及器件噪声
     （RIN / 消光比 / TIA 噪声）用例。

每个环境 = 名称 + Tx/Rx 奈奎斯特插损 + CD + DGD + 偏振角（+ 可选器件应力覆盖）。
"""
import copy

# ---------------------------------------------------------------------------
# DDPS v3 物理应力环境清单
#   基础环境（BASE_ENV）用于"只用基线训练 -> 跨环境泛化"的核心实验，其余为漂移环境。
# ---------------------------------------------------------------------------
ENV_CASES = [
    # --- 对称插损 ---
    {"name": "Base_IL10x10", "il_tx": 10.0, "il_rx": 10.0, "cd": 0.0, "dgd": 0.0, "pol": 0.0},
    {"name": "IL14x14", "il_tx": 14.0, "il_rx": 14.0, "cd": 0.0, "dgd": 0.0, "pol": 0.0},
    {"name": "IL20x20", "il_tx": 20.0, "il_rx": 20.0, "cd": 0.0, "dgd": 0.0, "pol": 0.0},
    # --- 非对称插损（Host 侧 vs Module 侧）---
    {"name": "IL20x10_TxHeavy", "il_tx": 20.0, "il_rx": 10.0, "cd": 0.0, "dgd": 0.0, "pol": 0.0},
    {"name": "IL10x20_RxHeavy", "il_tx": 10.0, "il_rx": 20.0, "cd": 0.0, "dgd": 0.0, "pol": 0.0},
    {"name": "IL16x10", "il_tx": 16.0, "il_rx": 10.0, "cd": 0.0, "dgd": 0.0, "pol": 0.0},
    {"name": "IL10x16", "il_tx": 10.0, "il_rx": 16.0, "cd": 0.0, "dgd": 0.0, "pol": 0.0},
    # --- 色散 ---
    {"name": "CD15ps", "il_tx": 10.0, "il_rx": 10.0, "cd": 15.0, "dgd": 0.0, "pol": 0.0},
    {"name": "CD28ps", "il_tx": 10.0, "il_rx": 10.0, "cd": 28.0, "dgd": 0.0, "pol": 0.0},
    # --- 偏振模色散 ---
    {"name": "DGD2ps", "il_tx": 10.0, "il_rx": 10.0, "cd": 0.0, "dgd": 2.0, "pol": 45.0},
    {"name": "DGD5ps", "il_tx": 10.0, "il_rx": 10.0, "cd": 0.0, "dgd": 5.0, "pol": 45.0},
    # --- 复合应力（对称 / 非对称）---
    {"name": "Comb_IL20x20_CD15_DGD5", "il_tx": 20.0, "il_rx": 20.0, "cd": 15.0, "dgd": 5.0, "pol": 45.0},
    {"name": "Comb_IL20x10_CD15_DGD5", "il_tx": 20.0, "il_rx": 10.0, "cd": 15.0, "dgd": 5.0, "pol": 45.0},
    # --- 器件噪声应力（RIN / 消光比 / TIA 噪声）---
    {"name": "HighNoise_IL10x10", "il_tx": 10.0, "il_rx": 10.0, "cd": 0.0, "dgd": 0.0, "pol": 0.0,
     "stress": {"laser_rin_db_hz": -140.0, "mzm_er_db": 15.0, "tia_noise_pa_rthz": 25.0}},
    {"name": "HighNoise_IL16x16", "il_tx": 16.0, "il_rx": 16.0, "cd": 0.0, "dgd": 0.0, "pol": 0.0,
     "stress": {"laser_rin_db_hz": -142.0, "mzm_er_db": 18.0, "tia_noise_pa_rthz": 20.0}},
]

# 核心实验的训练环境（"只用基线训练"）
BASE_ENV = "Base_IL10x10"


def env_case(name):
    for c in ENV_CASES:
        if c["name"] == name:
            return copy.deepcopy(c)
    raise KeyError(f"unknown env case: {name}")


def apply_env_to_config(config, env):
    """把某个环境(名称或 dict)的物理参数覆盖到 config 副本上，返回新 config。"""
    cfg = copy.deepcopy(config)
    if isinstance(env, str):
        env = env_case(env)
    cfg["channel"]["tx_pcb_loss_nyquist_db"] = float(env["il_tx"])
    cfg["channel"]["rx_pcb_loss_nyquist_db"] = float(env["il_rx"])
    cfg["channel"]["cd_ps_nm"] = float(env["cd"])
    cfg["channel"]["dgd_ps"] = float(env["dgd"])
    cfg["channel"]["pol_angle_deg"] = float(env["pol"])
    for key, val in (env.get("stress") or {}).items():
        cfg["channel"][key] = float(val)
    cfg["system"]["enable_eye_plot"] = False
    cfg["system"]["enable_spectrum_plot"] = False
    return cfg


def env_label(env):
    """用例的简短物理标签，用于报告/表头。"""
    if isinstance(env, str):
        env = env_case(env)
    lab = f"IL{env['il_tx']:g}x{env['il_rx']:g}"
    if env["cd"]:
        lab += f"+CD{env['cd']:g}"
    if env["dgd"]:
        lab += f"+DGD{env['dgd']:g}"
    if env.get("stress"):
        lab += "+Noise"
    return lab
