# Archive（历史归档）

本目录存放**已从主线移除、仅供历史参考与技术沉淀**的产物。所有内容均可由主线脚本重新生成或已不再使用，**不参与当前仿真/寻优流程**。

> 在 `physical-model` 分支（及后续主线）中，本目录不纳入版本控制（见 `.gitignore` 的 `archive/` 规则）；完整历史保留在 `sjtu-channel-model` 分支。

## 目录结构

| 子目录 | 内容 | 来源 |
| --- | --- | --- |
| `algorithms/` | 已被 DDPS 取代的古典/早期优化器（BO / GA / SA / ESC / SHC / SafeQCD / 两阶段等） | 从主线移除的历史算法实现 |
| `docs/` | 上述算法的说明文档 | 与 `algorithms/` 一一对应 |
| `datasets/` | 历次 DDPS 数据集 CSV（含早期 LHS 与 stage1 采样） | 可经 `dataset_generator.py` 再生 |
| `models/` | 历次训练的代理模型 pkl（`legacy` / `lpo` / `mlse` 三个历史版本） | 可经 `train_surrogates.py` 再生 |
| `results/` | 历史运行结果（`latest_comparison` / `mlse_comparison` / `20260902_*_comparison`） | 旧物理底座下的对比报告 |

## 说明

- 当前主线的对应产物在 `dataset/`、`models/`、`result/`（无版本后缀），是唯一活跃的输入/输出目录。
- 归档文件命名中 `legacy` / `lpo` / `mlse` 用于区分历史上不同物理底座训练出的模型，避免与当前 `models/` 下的同名 pkl 混淆。
