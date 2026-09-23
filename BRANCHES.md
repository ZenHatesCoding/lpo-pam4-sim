# 分支关系与版本导览

[🔙 返回主页](README.md)

## 一句话总结

- 当前工作分支：**`physical-model`**（与 `origin/physical-model` 同步）
- 分支线性历史：`main` → `feature/ddps-optimization` → `sjtu-channel-model` → `physical-model`
- 远端保留最新版本；历史版本（v1~v6.1 中间态）归档在本地 `archive/`，不入远端

## 分支总览

| 分支 | 定位 |
| --- | --- |
| `main` | 项目基线：古典优化器（BO/GA/SA/SHC/ESC） |
| `feature/ddps-optimization` | DDPS v1 建立：双代理架构、Stage-2 梯度下降 |
| `sjtu-channel-model` | SJTU 微观物理信道建模 + 历史归档整理 |
| **`physical-model`（当前）** | DDPS：A=探针→BER + B=参数→BER，7 维链式梯度（4 FFE 旁瓣 + gDC + gDC2 + gain），per-case target_rms 标定参照，次优起点冷启动 |

## 本地归档（不入远端）

`archive/` 目录保留在本地磁盘，git 不跟踪。包含：

| 归档目录 | 内容 |
| --- | --- |
| `archive/20260904_ddps_v1_physical_pre_v2/` | v1 全部产物 |
| `archive/20260910_ddps_v2_pre_ctle_reorder/` | v2 全部产物 |
| `archive/20260911_ddps_v3_pre_no_vga/` | v3 全部产物 |
| `archive/20260911_ddps_v4_probe_polyRidge/` | v4 全部产物 |
| `archive/20260915_ddps_v5_ab_input_merged_wrong/` | v5 全部产物 |
| `archive/20260916_repo_cleanup/` | 仓库整理时归档的历史脚本、结果、模型、文档 |
| `archive/20260921_repo_cleanup_v6_historical/` | v6.0/v6.1 历史结果、模型、数据集、交付件，及 LPO 规范 txt（pdf 提取物） |

## 版本变更记录

详见 [docs/CHANGELOG.md](docs/CHANGELOG.md)。
