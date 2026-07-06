# eLPO_antigravity 核心系统指令 (Workspace Rules)

> [!NOTE] 
> 本文件为项目级 Agent 专属规则。所有在此文件中的条目均作为**最高优先级的系统提示词**，在开发过程中必须无条件遵守。

## 1. 架构范式与编码约束 (Architecture & Coding Paradigms)
- **纯白盒化实现 (Pure White-Box DSP)**：核心信号处理链路（Tx DSP, Channel, Rx DSP）以及任何核心均衡/估计算法，必须使用纯 `numpy` / `scipy` 从底层公式手写实现。绝对禁止引入 `scikit-learn`、`hyperopt` 等黑盒高阶库来替代核心算法逻辑。
- **配置全量驱动 (Config-Driven)**：系统必须保持对各种速率档位（如 112G, 224G, 448G）的高度灵活性。**严禁在代码中硬编码任何波特率、采样率或均衡器抽头数量**。所有物理参数和系统配置必须统一通过 `config.xlsx` 动态下发与读取（修改参数请优先通过 `create_config.py` 更新表格）。
- **极简数据流 (Minimalist Data Flow)**：本项目定位为底层硬件算法的原型验证，拒绝过度封装。避免使用复杂的面向对象 (OO) 继承结构，保持面向过程的清晰数组（Array）信号流转。

## 2. 工作流与系统交互 (Workflow & Interaction)
- **Git 静默推送规范 (Silent Git Push)**：向 GitHub 提交代码时，**严禁触发任何要求用户手动输入密码的弹窗**。必须首先读取用户本地的 GitHub Token（绝对路径：`C:\Users\ZhenpingXing\Desktop\git.txt`），使用该 Token 以 `https://<token>@github.com/...` 的形式配置 remote origin 或直接推送，实现完全免密自动化操作。

## 3. 文档与语言规范 (Language Standards)
- **文档全面中文化 (Chinese Documentation)**：所有全局输出文档（包括 `README.md`、`docs/` 目录下的任何架构或指引说明）必须全部使用**中文**撰写。代码内的局部注释允许使用英文以保持简洁。
- **文档统一路由 (Single Entry Point)**：`README.md` 是全局文档的唯一核心枢纽，任何新增的子文档必须在主页中留有入口，且子文档内必须提供返回主页的跳转链接，保证“可进可退”。
