<!-- experiment-journal:start -->
## 实验记录的主动维护

本项目使用 `$mlflow-experiment-journal`（展示名称 `exp/experiment-journal`）。记录目录为 `experiments/`，先读取 requirements.md 和当前主题需求，再读取 tracking.json、experiment-map.json 与已有结果。初始化时把这里替换为实际记录根目录和需求文档路径；多 worktree 共同指向同一个记录根目录。

用户要求实现/执行变体时，先读取 skill 的实验执行文档和项目执行规则：独立代码变体使用 branch/worktree 隔离，固定代码的 seeds/sweeps 分别有 run/配置/输出，运行中的任务保持源码/import 路径稳定。各 worktree 使用相同的绝对记录根和 tracking backend；并发日志变化按约定单一写入者/锁合并。已授权实验执行包含常规 worktree 准备；仅维护日志不授权训练。

需求被明确调整，或完成实验相关代码/配置修改、分支/worktree 调整、训练启动/恢复/结束、产物路径变化、明确记录发现后，在任务结束前主动使用该 skill：更新相关需求、技术说明（数据/模型/目标/训练评估）、事实与证据，维护实验索引；图中事实变化时同步关键配置/loss/结果摘要与版本改动标签，生成紧凑概览及完整 Excalidraw/Markdown 视图。没有变化时保持文件不动。

自动维护只把事实及用户已经确定或要求保留的发现写入记录。保留历史代码版本、用户笔记、图上的手动布局和批注。已有 logging 负责训练指标；已配置生命周期回调时可即时刷新路径图，否则在 AI 下次检查训练状态时补齐变化。
<!-- experiment-journal:end -->
