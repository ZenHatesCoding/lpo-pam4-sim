# 分支关系与版本导览 (Branch & Version Map)

[🔙 返回主页](README.md) ｜ 相关文档：[06. DDPS v2 重做报告](docs/06_DDPS_v2_Rerun.md) ｜ [结果索引 result/SUMMARY.md](result/SUMMARY.md) ｜ [Agent 交接 HANDOFF](HANDOFF.md)

> 本文档回答三类问题：仓库里有哪些分支、它们之间是什么关系、尤其是 **`sjtu-channel-model`** 与 **`physical-model`** 到底差在哪。

---

## 1. 一句话总结

- 本仓库的四条分支 **main → `feature/ddps-optimization` → `sjtu-channel-model` → `physical-model`** 构成一条 **没有分叉的线性历史**：每一条后出现的分支都 100% 包含前一条分支的全部提交，分支本质只是“不同里程碑上的标签”。
- 当前工作分支是 **`physical-model`**（与 `origin/physical-model` 完全同步，工作区干净）。
- `sjtu-channel-model`（2026-09-03）＝ **SJTU 微观物理信道建模 + 历史归档整理** 的存档线，`archive/` 完整入库。
- `physical-model`（2026-09-08）＝ 在 sjtu 之上继续的 **活跃开发线**：DDPS v2 全链路重做、`result/SUMMARY.md` 结果重构，并把 `archive/` 移出版本控制（磁盘与 sjtu 分支仍保留）。

---

## 2. 分支总览表

| 分支 | tip commit | 时间 | 上游 | 相对前一条 | 定位 / 关键词 |
| --- | --- | --- | --- | --- | --- |
| `main` | `1b0d56b` | 2026-08-13 | `origin/main` | —（`origin/HEAD` 指向它） | 项目基线：古典优化器（BO/GA/SA/SHC/ESC/Two-Stage）均在根目录，`docs/04_Algorithms/` 结构 |
| `feature/ddps-optimization` | `ddf0ee4` | 2026-08-27 | `origin/feature/ddps-optimization` | `main` + 18 提交 | DDPS v1 建立与白盒化：新增 `ddps_optimizer.py` / `train_surrogates.py` / `test_generalization.py` / `HANDOFF.md` |
| `sjtu-channel-model` | `afacc74` | 2026-09-03 | `origin/sjtu-channel-model` | `feature/ddps-optimization` + 11 提交 | LPO MSA 信道升级 → 去全局 SNR 改微观物理参数 → 古典优化器归档进 `archive/` → SJTU 信道整理（`result/ddps/`、`dataset/`、`models/`） |
| **`physical-model`（当前）** | `9444245` | 2026-09-08 | `origin/physical-model` | `sjtu-channel-model` + 9 提交 | **DDPS v2 全链路重做** + 结果重构（`result/SUMMARY.md`、`result/ddps_v2_20260907/`、`result/ddps_v2_control/`）；`archive/` 停跟 |

> 另有已删除的本地分支 `lpo_channel_upgrade`（2026-09-02 的临时存档点，内容已完全包含在 sjtu 历史中），为保持本地与远端一致已删除，不产生任何历史丢失。

---

## 3. 拓扑与演进（为什么没有“冲突”）

```
main (08-13) ──(+18)──▶ feature/ddps-optimization (08-27)
   ──(+11)──▶ sjtu-channel-model (09-03)
   ──(+9)──▶ physical-model (09-08)   ← 当前 HEAD
```

- 任意相邻两条：`git merge-base A B` 等于前一条的 tip，`git rev-list --left-right --count A...B` 的结果是 `0 N`，即**后一条只多不差、没有任何独有提交在前一条里**。
- 因此切换分支不会“丢东西”：在 `physical-model` 上能看到全部历史；想翻古典优化器或 v1 时期的原始归档，去 `sjtu-channel-model`（`archive/` 在那条分支上入库）。
- 校验命令：
  ```bash
  git log --oneline --graph --decorate -20 physical-model
  git merge-base sjtu-channel-model physical-model      # = afacc74（sjtu 的 tip）
  git rev-list --left-right --count sjtu-channel-model...physical-model   # = 9   0
  git rev-list --left-right --count feature/ddps-optimization...sjtu-channel-model  # = 11  0
  ```

---

## 4. 逐分支说明

### 4.1 `main` —— 古典优化器基线时代
早期主线，DSP 链路 + 多种黑盒/白盒优化器平铺在根目录；文档用 `docs/04_Algorithms/` 目录（Baselines / SafeQCD / TuRBO_Safe / Surrogate_SHC / Two_Stage_Optimization 等）。后来的 `docs/04_DDPS_Optimization.md` 是这些内容在 sjtu/physical 上的重构形态。

### 4.2 `feature/ddps-optimization` —— DDPS 雏形与白盒化
DDPS（Data-Driven Physical Surrogate）从 0 到 1 的阶段：架构对齐 Stage-1 供给 / Stage-2 约束下降，做 feature ablation、跨 SNR 排序、Ridge vs GPR vs GPR+UCB 对比等；产物 `docs/04_Algorithms/DDPS.md`。两条测试/训练脚本自此成型。

### 4.3 `sjtu-channel-model` —— SJTU 微观物理信道 + 历史归档线
在 feature 之上完成“物理化”大升级：信道参数对齐 **LPO MSA**（`f7bbaa1`）→ 移除全局 `SNR_dB`、改用 RIN/Shot/Thermal/TIA 等微观器件噪声（`7346c55`）→ 旧优化器逐步归档进 `archive/algorithms/` + `archive/docs/`（`7c257f4`/`bb69baa`/`3287837`）→ 显式 Driver 增益 / DAC-ADC ENOB / 激光器相位噪声补齐并重跑 DDPS（`76f90b4`）→ 最终目录大整理（`afacc74`：`dataset/`、`models/`、`result/ddps/` 成型）。**如果你要的是“物理模型升级完成、历史干净可查”的存档基线，用这条分支。**

### 4.4 `physical-model`（当前）—— DDPS v2 活跃开发线
在 sjtu 之上：
1. 把 `archive/` 移出版本控制（磁盘保留，`.gitignore` 新增 `archive/`），历史引用改指 sjtu 分支（`1b73a2b` / `ab58fac`）；
2. 修复高噪声下 Tx FIR 提取的 AGC 归一化（`550bb5a`）；
3. **DDPS v2 全链路重做**，修复 v1 负向优化（`7fc90d2`，见 [docs/06](docs/06_DDPS_v2_Rerun.md)）；
4. 结果呈现重构为单页横向对比 + 统一入口 [`result/SUMMARY.md`](result/SUMMARY.md)（`efa9e3c`→`9444245`）。
**所有新开发默认落在这一条。**

---

## 5. 重点：`sjtu-channel-model` vs `physical-model`

### 5.1 血缘关系
`physical-model` = `sjtu-channel-model` + **恰好 9 个提交**（`merge-base` 就是 `afacc74`），sjtu 侧没有任何独有提交。因此两者“内容差”＝这 9 个提交的净改动，不存在分叉合并问题。

### 5.2 这 9 个提交是什么

| # | commit | 作用 |
| --- | --- | --- |
| 1 | `1b73a2b` | `archive/` 停跟（历史产物只留磁盘，`.gitignore` 加 `archive/`） |
| 2 | `ab58fac` | 历史算法引用改指向 `sjtu-channel-model` 分支（本分支不再含 archive/） |
| 3 | `550bb5a` | Tx FIR 提取加 AGC 归一化，修复高噪声物理模型梯度方向 |
| 4 | `7fc90d2` | **DDPS v2 全链路重做**（修 v1 负向优化，数据/训练/在线调优/可视化） |
| 5 | `ae5109e` | v1 诊断脚本输入改指向 `archive/20260904_ddps_v1_physical_pre_v2/` |
| 6 | `efa9e3c` | 新增统一结果入口 `result/SUMMARY.md` + 逐用例报告页 |
| 7 | `6614394` | 结果重构为单页横向对比、修掉失效链接 |
| 8 | `3d53e0a` | 结果页聚焦“只用基线训练 → 跨环境泛化” |
| 9 | `9444245` | SUMMARY 补齐实验一/实验二表格与收敛/抽头图 |

### 5.3 文件层面净变化（sjtu → physical，共 182 文件，+4459 / −26467）

- **删除（出库）**：`archive/`（69 个历史算法/数据集/结果文件）、旧 `result/ddps/` 图与汇总、旧 `models/*.pkl`、`dataset/ddps_dataset_20260903_112922.csv` 等。
- **新增**：`dataset/ddps_v2_dataset_20260907_190819.csv`；`models/ddps_v2/` 与 `models/ddps_v2_control/`；`result/SUMMARY.md` + `result/ddps_v2_20260907/`（66 个结果/图/trace）+ `result/ddps_v2_control/`；`docs/06_DDPS_v2_Rerun.md`；脚本 `ddps_cases.py` / `make_result_summary.py` / `report_ddps_v2.py` / `run_ddps_v2_control.py` / `scratch/diag_*.py`。
- **修改**：`.gitignore`、`README.md`、`HANDOFF.md`、`config.xlsx`、`dataset_generator.py`、`ddps_optimizer.py`、`main.py`、`test_generalization.py`、`tx_channel_extract.py`、`docs/01` `03` `04` `05`。
- 一键查看：`git diff --stat sjtu-channel-model physical-model`

### 5.4 “archive/ 去哪了”速查

| 你想找的东西 | 在哪 |
| --- | --- |
| 古典优化器源码 + 文档（BO/GA/SA/SHC/TuRBO/SafeQCD/Two-Stage…） | `sjtu-channel-model` 分支的 `archive/algorithms/` + `archive/docs/`（入库）；本机磁盘目录 `archive/`（未入库，与 sjtu 内容一致） |
| DDPS v1（物理模型修复前）数据/模型/结果 | 本机磁盘 `archive/20260904_ddps_v1_physical_pre_v2/`（不入库）；git 历史保留旧版 |
| DDPS v2 全部产物 | `physical-model`：`result/ddps_v2_20260907/`、`result/ddps_v2_control/`（入口 `result/SUMMARY.md`） |

### 5.5 什么时候用哪条

- 继续开发 / 复现 v2 结果 / 出报告 → **`physical-model`**（当前）。
- 需要“物理模型升级完成 + 历史完整入库”的干净存档基线 → `sjtu-channel-model`。
- 对比 DDPS v1 早期实现 / 古典优化器 → `main` / `feature/ddps-optimization` / `sjtu-channel-model` 的归档均可。

---

## 6. 文档地图（README → 各文档）

`README.md` 是唯一入口；每条文档都可一键返回主页。各文档随分支演进出现过不同形态，跨分支可用性如下：

| 文档 | 内容 | main | feature | sjtu | physical |
| --- | --- | --- | --- | --- | --- |
| [README.md](README.md) | 项目主页 / 导航枢纽 | ✅ | ✅ | ✅ | ✅ |
| [01. DSP 架构与核心参数](docs/01_DSP_Architecture.md) | 收发机模型、config.xlsx 参数 | ✅ | ✅ | ✅ | ✅ |
| [02. 独立分析与诊断工具](docs/02_Utility_Scripts.md) | scratch/ 工具集 | ✅ | ✅ | ✅ | ✅ |
| [03. 调试排坑与经验沉淀](docs/03_Troubleshooting_History.md) | 踩坑记录 | ✅ | ✅ | ✅ | ✅ |
| [04. DDPS 数据驱动物理代理寻优](docs/04_DDPS_Optimization.md) | DDPS 架构（重构自 `docs/04_Algorithms/DDPS.md`） | — | 旧版 | ✅ | ✅ |
| [05. 物理信道模型升级](docs/05_Physical_Channel_Upgrade.md) | 高斯噪声 → 微观物理模型 | — | — | ✅ | ✅ |
| [06. DDPS v2 重做报告](docs/06_DDPS_v2_Rerun.md) | v2 根因与结果（本分支新文档） | — | — | — | ✅ |
| [LPO MSA 规范提炼](docs/LPO_MSA_Specification_Summary.md) | 电气/光学参数依据 | — | — | ✅ | ✅ |
| [结果索引 result/SUMMARY.md](result/SUMMARY.md) | v2 两实验对比表 + 全部图/数据 | — | — | — | ✅ |
| [HANDOFF.md](HANDOFF.md) | Agent 任务交接说明 | — | ✅ | ✅ | ✅ |
| 古典优化器文档 | Baselines/SafeQCD/TuRBO_Safe/Surrogate_SHC/Two-Stage | `docs/04_Algorithms/` | 同左 | `archive/docs/` | 磁盘 `archive/`（或 sjtu） |

---

## 7. 常用命令速查

```bash
# 查看整条线性历史
git log --oneline --graph --decorate -30 physical-model

# 两条分支的提交差（谁多谁少）
git rev-list --left-right --count sjtu-channel-model...physical-model

# 文件级差异
git diff --stat sjtu-channel-model physical-model

# 看某文件在另一分支的版本
git show sjtu-channel-model:archive/algorithms/bo_optimizer.py | head -50

# 切换（无本地改动时直接切）
git checkout physical-model
```

---

[🔙 返回主页](README.md)
