# exp/experiment-journal

面向机器学习实验的 Codex skill：从已有项目分析、训练前约定，到隔离执行模型变体、记录结果和维护实验路线图。MLflow 保存数值、配置、源码与产物，Markdown 保存主要结果、交流后确定的发现和下一步决定。

这个 skill 围绕四个问题组织工作：**和人明确什么、记录什么、内容是什么意思、用什么形式保存和呈现**。

- 展示名称：`exp/experiment-journal`
- 调用名称：`$mlflow-experiment-journal`
- AI 执行入口：[SKILL.md](SKILL.md)，正文为英文，skill 描述为中文。
- 中文维护入口：[zh/SKILL.zh.md](zh/SKILL.zh.md)。用户修改中文版本，需要时要求 AI 同步英文。

## 适用场景

| 场景 | 主要工作 |
| --- | --- |
| 初始化已有项目 | 阅读实际训练链路和历史证据，建立当前需求、技术说明、记录方案与实验索引 |
| 训练前准备 | 明确研究问题、基线、loss 含义、评估口径、资源预算和本次记录内容 |
| 执行模型变体 | 隔离 branch/worktree，保留真实基线和启动源码，运行小测试及已授权实验 |
| 比较实验 | 用稳定指标命名横向比较版本、纵向比较 loss 分量，同图查看 ID/OOD |
| 训练后记录 | 整理实际结果，与用户讨论后写入发现、收益和后续决定 |
| 持续维护 | 更新代码、runs、checkpoint、数据及产物位置，刷新 Excalidraw 和 Markdown 路线图 |

AI 可以提取事实、核对数值并参与分析。实验是否成功、收益在哪里、下一步走哪条路线，由用户在交流中决定；用户要求记录后，AI 将结论写入文档。

## 安装与开始使用

将本仓库克隆到 Codex 的 skills 目录，目录名使用调用名称：

```bash
git clone git@github.com:XEurus/Training-skill.git \
  ~/.codex/skills/mlflow-experiment-journal
```

如果该目录已有版本，先保留本地修改，再按自己的更新方式合并。也可以先克隆到普通工作目录，直接让 AI 读取其中的 `SKILL.md`。

安装后，在 Codex 中显式调用：

```text
使用 $mlflow-experiment-journal 初始化当前项目。
先分析实际训练入口、数据、模型、损失和历史结果，建立当前需求与实验记录，
再讨论本次需要补齐的内容。
```

```text
使用 $mlflow-experiment-journal 准备两种模型变体：改变输入条件、改变局部损失权重。
沿用当前基线和评估协议，分别建立工作区，先做小测试并记录资源利用情况。
```

```text
使用 $mlflow-experiment-journal 比较 baseline 和新版本的 ID/OOD 结果。
我们讨论后，把确定的发现写入主题笔记，并更新实验路线图。
```

skill 会复用项目现有目录与约定。初始化时将主动维护约定合并进项目 `AGENTS.md`，之后相关代码、配置、运行状态或发现发生变化时增量更新。后台训练的即时更新需要项目回调接入；仅安装 skill 不会启动后台监控。

## 工作流与记录内容

推荐在项目初始化、训练前、训练后分别使用；执行和比较实验时也可以直接调用。训练循环负责连续记录，skill 负责确定规则、接入、分析与维护。

1. **初始化**：从真实入口追踪数据加载、模型、loss、反向传播、验证与选模，读取历史 runs 和证据，生成已填写的需求记录与记录纲要。
2. **训练前**：明确本次基线和改动，记录实际配置、源码身份、指标映射、路径、算力/时间和内存预算，确定验证与采样方案。
3. **执行**：独立开发的代码变体默认分别使用 branch/worktree；固定代码的 seeds 或配置扫描可以共用工作区，各自使用独立 run、配置快照与输出目录。
4. **训练后**：核对 checkpoint 和测量口径，汇总主要结果，与用户讨论发现，再写入 Markdown 和 MLflow 附件/描述并更新路线图。

所有工作区共用一个 canonical journal root。历史代码由 commit、dirty diff、未跟踪文件与源码快照共同标识；branch 名称用于定位，不能替代实际训练版本。运行中的任务读取的源码保持稳定。

技术说明覆盖八类内容：任务与样本、数据来源与版本、清洗与预处理、划分与采样、架构与初始化、损失与目标、训练协议、评估与模型选择。损失同时记录可读公式与实现位置，数据记录从原始到清洗、特征与缓存的血缘。

新项目默认结构如下；已有项目复用原目录：

```text
experiments/
  requirements.md                 # 当前需求、优先级和约束
  initialization.md               # 记录纲要、历史范围与待补内容
  tracking.json                   # 连接、指标、视图、资源与评估配置
  evidence.json                   # 历史证据索引
  specs/                          # 数据、模型、目标、训练评估说明
  notes/<study>.md                # 研究计划、主要结果、发现与决定
  experiment-map.json             # 路线、版本、runs 和路径的事实源
  experiment-map.overview.excalidraw
  experiment-map.overview.md       # 重要版本概览与详情入口
  experiment-map.excalidraw
  experiment-map.md               # 完整来源、Mermaid 与路径表
```

## MLflow 指标与比较

loss 名称在不同版本间保持稳定。版本、日期、seed 和变体名放在 run 身份与配置中；公式含义变化时更新定义身份。加权与非加权分开，记录总量、分组和所有标量叶子项，实际反向传播目标使用 `train/objective`。

| 视图 | 指标示例 | 内容 |
| --- | --- | --- |
| 训练原始损失 | `train/raw/{loss}` | 总量、分组、叶子 |
| 训练加权损失 | `train/weighted/{loss}` | 各层对目标的加权贡献 |
| 验证原始损失 | `val/{dataset}/raw/{loss}` | ID/OOD 同分量成对展示 |
| 验证加权损失 | `val/{dataset}/weighted/{loss}` | 有明确加权验证目标时展示 |

加权视图为 `auto/on/off`；权重简单、曲线重复时可以省略。常规子集验证使用 `val_quick/...`，与 `val/...` 全量结果分开。比较预设涵盖跨版本、ID/OOD、分量间和加权前后；具体入口根据项目安装的 MLflow UI/API 接入。

MLflow 服务、训练 logging 和比较入口在项目中配置。仓库提供规范、模板和地图脚本；安装 skill 后，需要结合项目训练程序完成接入。配置示例见 [assets/tracking.example.json](assets/tracking.example.json)，其中的空值和示例 loss 需替换为实际内容。

## GPU、内存与验证默认规则

这些规则用于新实验计划；已有明确协议沿用，调整时记录变更。

| 项目 | 默认规则 |
| --- | --- |
| GPU 利用率 | 稳态训练时，每张已分配 GPU 的时间加权平均计算利用率原则上 **>90%**；同时记录各阶段及完整执行窗口统计 |
| GPU 采样 | 代表性短测预热后每 **1 秒**采样、持续 **120 秒**；训练中每 **5 秒**采样；保存逐卡原始数据和吞吐 |
| 主机 RAM 份额 | 逐主机计算：**总 RAM × 0.95 × 本实验 GPU 数 ÷ 主机总 GPU 数** |
| 缓存预算 | 从实际 RAM 预算扣除非缓存峰值和运行余量，覆盖本机全部 ranks/workers，优先减少训练 I/O |
| 常规验证 | 各域固定 **10–20%** 代表性子集，通常每 epoch 一次；保存清单，常驻或提前加载 |
| 全量验证间隔 | **`max(1, ceil(计划总 epoch 数 × 0.025))`**；200 epoch 时每 **5 epoch** 一次；保留 final 全量验证 |
| 重要验证缓存 | 内存充足且训练无 I/O 瓶颈时，可将 OOD 等重要验证集全量常驻；全量验证复用已有缓存 |

例如 512 GiB、8 卡主机使用 2 卡时，默认 RAM 份额为 **121.6 GiB**；实际预算还受作业/容器上限及其他任务约束。95% 是整机分配上限，缓存占用由实测吞吐和内存峰值决定。

GPU 未达目标时，定位加载、同步、算子或负载均衡瓶颈，在既定预算内调整并复测。Markdown 保留主要利用率、内存/吞吐结果、调整和证据路径。利用率属于执行效率，科研收益仍按用户讨论结果记录。

## 实验路线图

重要版本概览的卡片简短呈现版本、状态、当前关键配置、loss 和主要结果；连线标注相对来源版本的具体改动。完整图保留分支/worktree、历史源码、runs、证据与产物位置。

使用同一份 JSON 维护两个阅读层级，保留手工位置和批注。概览默认正文至少 22 px、连线说明至少 20 px，超过正常屏幕阅读范围时提供分组视图，并检查实际 Excalidraw 原生预览。共享依赖进入背景或详情，比较关系与派生关系区分展示。

在仓库根目录执行：

```bash
# 生成完整图与重要版本概览，产物写入索引所在目录
python scripts/render_experiment_map.py /path/to/experiments/experiment-map.json

# 只生成重要版本概览
python scripts/render_experiment_map.py /path/to/experiments/experiment-map.json --view overview

# 生成独立分组概览，GROUP 替换为该项目的实际 overview.group
python scripts/render_experiment_map.py /path/to/experiments/experiment-map.json \
  --view overview --overview-group "GROUP"
```

`--format excalidraw|markdown|both` 选择输出格式，默认 `both`。`--view detailed|overview|both` 默认 `both`；概览追加 `.overview` 后缀，分组概览追加独立分组后缀。字段定义和手工布局规则见 [实验路径图规范](zh/references/experiment-map.zh.md)。

原生预览需要 Node.js、Chromium 以及独立安装的依赖：

```bash
npm install --prefix /tmp/journal-map-runtime --no-audit --no-fund \
  @excalidraw/excalidraw react react-dom esbuild playwright

node /tmp/journal-map-runtime/node_modules/playwright/cli.js install chromium

node scripts/preview_experiment_map.mjs \
  /path/to/experiments/experiment-map.overview.excalidraw /tmp/journal-map-preview \
  --runtime-dir /tmp/journal-map-runtime --viewport-width 1440
```

已有 Chromium 时用 `--browser /absolute/path/to/chromium`。预览目录包含 `native.svg`、`full.png`、`overview.png`、`detail-top.png` 和 `render.json`。

## 中文维护与目录导航

中文版本供用户编辑，英文版本供 AI 使用。日常使用直接读取英文，不执行双语检查或自动翻译；需要同步时说“同步英文版本”。修改 skill 时在同一范围维护中英文。

| 内容 | 中文 | English |
| --- | --- | --- |
| 主入口 | [SKILL.zh.md](zh/SKILL.zh.md) | [SKILL.md](SKILL.md) |
| 项目初始化 | [初始化](zh/references/initialization.zh.md) | [Initialization](references/initialization.md) |
| 技术说明 | [数据/模型/损失/协议](zh/references/technical-spec.zh.md) | [Technical specification](references/technical-spec.md) |
| 实验执行 | [隔离、GPU、内存与缓存](zh/references/experiment-execution.zh.md) | [Experiment execution](references/experiment-execution.md) |
| 训练前 | [记录与元数据](zh/references/before-training.zh.md) | [Before training](references/before-training.md) |
| 指标与比较 | [loss、视图与验证](zh/references/metrics-and-comparison.zh.md) | [Metrics and comparison](references/metrics-and-comparison.md) |
| 结果与发现 | [训练后记录](zh/references/results-and-findings.zh.md) | [Results and findings](references/results-and-findings.md) |
| 实验路径图 | [Excalidraw 与 Markdown](zh/references/experiment-map.zh.md) | [Experiment map](references/experiment-map.md) |

`agents/` 保存展示元数据，`assets/` 保存项目模板，`scripts/` 提供地图渲染与预览，`tests/` 验证渲染和更新行为。

## 开发验证

Python 地图渲染器和常规测试使用标准库：

```bash
python -m unittest discover -s tests -v
node --check scripts/preview_experiment_map.mjs
```

原生 Excalidraw 回归需要指定上述 Node runtime；已有浏览器可另指定路径：

```bash
EXPERIMENT_JOURNAL_NATIVE_RUNTIME=/tmp/journal-map-runtime \
  python -m unittest discover -s tests -v
```

浏览器路径可通过 `EXPERIMENT_JOURNAL_NATIVE_BROWSER` 设置。独立评估环境中的真实项目 fixture 不随 skill 发布，对应检查在 fixture 缺失时跳过。

skill 元数据可使用 Codex 自带的 `skill-creator/scripts/quick_validate.py` 校验。自动测试覆盖渲染格式、字体与空间、关系语义、人工布局/批注保留，以及无变化时字节和 mtime 稳定；实际可读性仍通过原生预览检查。
