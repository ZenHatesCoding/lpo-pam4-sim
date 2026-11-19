# 分支关系与版本导览

[🔙 返回主页](README.md)

## 一句话总结

- 当前工作分支：**`physical-model`**（与 `origin/physical-model` 同步）
- 分支线性历史：`main` → `feature/ddps-optimization` → `sjtu-channel-model` → `physical-model`
- 远端只保留最新版本；被取代的历史版本与历史产物归档在本地 `archive/`（目录名带日期，完整清单见该目录）

## 分支总览

| 分支 | 定位 |
| --- | --- |
| `main` | 项目基线：古典优化器（BO/GA/SA/SHC/ESC） |
| `feature/ddps-optimization` | DDPS v1 建立：双代理架构、Stage-2 梯度下降 |
| `sjtu-channel-model` | SJTU 微观物理信道建模 + 历史归档整理 |
| **`physical-model`（当前）** | DDPS：Model A 探针方向代理（唯一在线代理）+ 8 维在线搜索（5 抽头全自由无边界 + gDC + gDC2 + u_gain），gain 解析梯度 + 形状 7 维三种取法（\ull\ / otate\ / \secant\）× 两种梯度来源（发端代理 / 真实 BER 回传），固定 15 步、代理行不早停，per-case target_rms 标定参照，次优起点冷启动 |

## 本地归档（不入远端）

`archive/` 目录保留在本地磁盘，用于历史产物追溯。包含：

| 归档目录 | 内容 |
| --- | --- |
| `archive/20260904_ddps_v1_physical_pre_v2/` | v1 全部产物 |
| `archive/20260910_ddps_v2_pre_ctle_reorder/`、`archive/20260910_ddps_v3_margin060_calibration/` | v2 全部产物；v3 margin 0.60 标定快照 |
| `archive/20260911_ddps_v3_pre_no_vga/` | v3 全部产物 |
| `archive/20260911_ddps_v4_probe_polyRidge/`、`archive/20260911_ddps_v4_pre_v5/`、`archive/20260911_ddps_v4_11dim_kernelRidge/` | v4 三份快照（探针 + 多项式 Ridge / 11 维 KernelRidge / 交付件与诊断表） |
| `archive/20260911_ddps_v5_global_rms_wrong/`、`archive/20260915_ddps_v5_global_rms_wrong/`、`archive/20260915_ddps_v5_ab_input_merged_wrong/` | v5 错误口径快照（全局 RMS 两份日期快照；A/B 输入空间合并） |
| `archive/20260916_repo_cleanup/` | 仓库整理时归档的历史脚本、结果、模型、文档 |
| `archive/20260920_ddps_v6.2.2_final/` | v6.2.2 全套产物 |
| `archive/20260921_repo_cleanup_v6_historical/` | v6.0/v6.1 历史结果、模型、数据集、交付件，及 LPO 规范 txt（pdf 提取物） |
| `archive/20260923_code_versioned_snapshot/` | 去版本号前的 DDPS 代码快照（含历史版本函数与死脚本） |
| `archive/20260924_ddps_v7_physical_model/`、`archive/20260928_ddps_v7.1/`、`archive/20260928_ddps_v7.2_2to18/` | v7 / v7.1 / v7.2 结果、模型与交付件 |
| `archive/20260930_ddps_v7.3_2to22/` | v7.3 全量结果与交付件 |
| `archive/20260930_ddps_secant_k3_scratch/` | 割线 K=3 刷新时期的 scratch（等价/自检/诊断） |
| `archive/20261022_ddps_ab_secant_2to22/` | 重构前的 A+B 割线 2^22 secant / direct 结果 |
| `archive/20261022_retire_stale_tools/` | 退役的旧工具脚本（如 `run_py_cases_parallel.py`） |
| `archive/20261023_superseded_secant_direct_equiv/` | 被六格等价目录取代的旧等价结果（direct、secant 解析梯度各一套） |
| `archive/20261119_superseded_result_dirs/` | 被六格现役目录取代的 `result/` 旁证目录：`_integrity_py`、`_integrity_rebuild`、`ddps_chain_sanity`、`ddps_direct_py`、`ddps_secant_analytic_py` |
| `archive/ddps_v6_2_*`、`archive/_buggy_v6_2_*` | v6.2 时期的 goodseed 结果与问题版结果 |

## 版本变更记录

详见 [docs/CHANGELOG.md](docs/CHANGELOG.md)。
