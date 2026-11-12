# 实验路径图

## 用途与交流

路径图同时回答：现在有哪些研究路线；各路线在哪个 Git 分支或 worktree；做了什么改动；对应哪些训练 runs；数据、代码和结果在哪里。

从已有配置、Git、运行元数据及 MLflow 提取事实。研究路线间的派生关系来自已记录来源或用户说明；仅因名称相似或指标更好，不推断路线关系。需要明确的是新实验从哪条路线发展、主要改动是什么，以及是否有新的研究判断需要记录。

## 文件与结构

项目约定目录下的 `experiment-map.json` 是事实与关系的结构化来源。同一份数据维护两个阅读层级：`experiment-map.overview.excalidraw` 是优先阅读的紧凑重要信息版；`experiment-map.excalidraw` 和 `experiment-map.md` 保留完整溯源图、Mermaid 与路径表。重要信息版另有简明 Markdown。更新 JSON 后运行：

```bash
python <skill-dir>/scripts/render_experiment_map.py <project>/experiments/experiment-map.json
```

默认（`--view both`）在同目录生成详细图文件对，以及 `.overview.excalidraw` / `.overview.md` 文件对。`--view overview` 或 `--view detailed` 只维护一个层级；`--overview-group GROUP` 生成带独立后缀的研究路线概览，不覆盖组合概览。`--format excalidraw` 或 `--format markdown` 可只生成一种，`--format both` 为默认；`--output` 指定 Markdown 基础路径，`--excalidraw-output` 指定 Excalidraw 基础路径，概览在基础文件名后追加后缀。脚本从索引读取事实、渲染图表，并读取已有 Excalidraw 布局；Git 和 MLflow 信息由使用 skill 的 AI 或训练事件接入收集。

Excalidraw 图可在 Excalidraw 中打开，也可使用编辑器扩展。稳定的元素 ID 用于更新：刷新管理节点的事实文字和关系，保留用户移动的位置、布局样式以及非管理批注。事实修改写入 JSON；画布上的布局和自由批注保留在 `.excalidraw` 中。主要改动显示在节点里，完整 commit、runs、证据和路径查看 Markdown 表格与主题笔记。

顶层字段为 `schema_version: 1`、`project`、`updated_at`、`nodes`、`edges`。每个 node 表示一个可独立描述的实验改进或研究路线；它可以关联多个 seeds/runs。使用稳定 ID，例如 `exp_001`。

| node 字段 | 含义 |
|---|---|
| `id`, `title`, `study` | 稳定身份、名称、研究主题 |
| `execution_status` | planned/running/finished/failed/interrupted/archived/unknown，表示执行状态 |
| `summary`、`question` | 可选的简短目的和研究问题，显示在卡片上 |
| `results` | 可选的主要测量结果列表，注明数据集/checkpoint 口径；与研究判断分开 |
| `executions` | 不依赖 MLflow 的训练身份，未取得 MLflow run 时也能记录 |
| `display` | 详细图的分组/顺序和初始布局偏好 |
| `overview` | 整理后的短名称、当前重要配置、loss、主要结果、分组/顺序和详情入口，见下文 |
| `changes` | 相对来源路线的具体主要改动，字符串数组 |
| `revisions` | 代码状态列表，保留历史，见下文 |
| `runs` | MLflow runs，包含所属代码状态 |
| `paths` | 数据、输出、日志、checkpoint、分析文件等位置 |
| `findings`, `decision`, `note_path` | 已确定发现摘要、决定和主题笔记位置；可为空 |
| `evidence` | 可选，关联 evidence.json 中的来源 ID 列表 |

明确 baseline → variant → revision/run 链：来源/基线节点通过有证据的派生或比较边连接变体；各变体保留历次 revision 和全部 seeds/重复 runs。固定代码的重复运行复用节点，不仅因另一个 seed 就新建研究路线。基线 revision 的证据中注明准确起点 commit 加 dirty/untracked 快照身份，并关联主题计划。

每个 revision 包含 `id`、`repo`、`branch`、`commit`、`dirty`、`worktree`、`host`、`observed_at`、`code_snapshot`、`patch_path`。未知值使用 null。分支名便于定位，commit 与源码快照确定实际代码；分支后续移动不改写旧 revision。新代码状态追加 revision。

每个 run 包含 `run_id`、`tracking_uri`（可分享地址）、`experiment_id`、`url`（已核实 UI 链接或 null）、`revision_id`、`status`。真实 run 关联存在的 revision；历史代码不明时建立明确标为未知的 revision，不拿当前分支代替。恢复训练沿用同一 run 记录，新的训练使用新 run ID。

可选 `executions` 条目包含 `id`、`backend`、`status`、`observed_at`、`directory`、`revision_id`、`host`。仅 id 必填；其他未知事实用 null。非空 revision_id 必须关联本节点版本。沿用操作目录/作业身份并建立稳定本地 ID，保留状态观察时间；`runs` 仍专用于真实 MLflow run。MLflow 暂不可访问不应导致本地有证据的训练历史缺席。

每个 path 包含 `role`、`host`、`location`、`storage`，storage 取 `external` 或 `mlflow-artifact`。例如 checkpoint 的服务器路径与已经上传的 artifact URI 分别记录。

edge 包含 `from`、`to`、`relation`。relation 为 `derived_from`、`continues_from`、`compares_to` 或 `merges_from`。方向规定：来源/基线 → 新路线/比较对象。多个来源可以多条边指向同一节点。这是研究关系图，不是自动生成的 Git commit DAG；真实 Git 合并关系有记录时另在 changes 中注明。

代码派生不等于权重继承。实际加载的 checkpoint/父 run 和 load 语义写入运行元数据及主题笔记，确实使用时才增加模型依赖。

依赖边另支持 `uses_model` 和 `uses_data`（使用者→依赖对象），以及 `produces`（生产者→产物）；与研究派生关系分开。可选 `label` 写具体关系，如“冻结 Stage1 epoch11”；`evidence` 关联来源 ID。已有证据的父模型、缓存/数据版本和输出，凡是能解释实验来源的都纳入图中。已准备的数据版本可以显示，但不表示旧 run 已采用。

## 更新时机

训练前创建或更新计划节点、已知代码状态和预期路径；真实训练启动后加入 run 与启动代码快照。训练后补全状态、checkpoint 和产物。实验代码/配置/分支/worktree 变化后更新受影响路线；按用户要求记录发现时，更新 findings、decision 和笔记链接。上述事件发生在当前任务中时主动维护，无需用户单独要求更新图。

初始化把主动维护规则写入项目 AGENTS.md 后，后续相关会话在收尾时读取已有索引并更新。跨会话保留同一事实来源和稳定 ID；先合并差异再渲染，没有变化时不改写 updated_at 或输出文件。

项目的记录合并入口和 renderer 都应落实无变化规则：先把已保存事件合并到当前事实，在改 `updated_at` 前比较结果；未变的 JSON、Markdown 和图都跳过写入，也不改变 mtime。重放同一已保存事件不是新的训练观测。用相同输入连续执行两次维护，核对这一行为；事实确有变化时保留独立记录的观测。

区分生命周期的发生时间、状态观测时间和事件投递时间。后来查询状态不表示重新启动或延长训练：开始/结束时间采用权威 run 或生命周期回执并记录来源，缺少证据时留空。迟到事件按生命周期/attempt 身份及发生顺序合并，保留观测，但不能让旧启动事件倒退已完成 attempt 的状态；真正恢复运行是新的生命周期事件。用后续状态查询和延迟启动回执核对已保存的状态与起止时间。

后台训练要实时刷新时，在项目已有的主进程/rank 0 生命周期回调中记录 run 启动、checkpoint、完成或异常事件。事件先写入独立运行元数据，再由项目的单一更新入口合并索引并调用渲染器；所有 worktree 指向规范 `record_root`。并发更新采用单一写入者或共享锁，覆盖重新读取最新文件、按稳定 ID 合并、原子替换和渲染。各 run 事件在补齐前持久保留，保留独立工作进程的变化；仅原子写入并不能避免旧文件覆盖其他 run。单纯安装 skill 不创建常驻监听进程；尚未接入回调时，在 AI 下次检查训练状态时补齐变化。

记录用的 JSON 和 Markdown 显式按 UTF-8 读写，训练回调内也如此。地图刷新放在训练异常处理范围之外；渲染失败时留下待处理事件，不改变已记录的训练结果。

维护现有节点 ID、revision ID 和 run 关联。分支已删除或 worktree 已迁移时追加说明或新状态，保留历史训练定位信息。仅整理图不创建或切换分支；这不限制按[实验执行与隔离](experiment-execution.zh.md)为已授权实验常规准备 branch/worktree。执行后不自动合并或删除实验分支/worktree。未知事实保持 null/未记录；不影响其他已知内容入图。

## 重要信息概览与完整溯源

优先提供重要信息概览。节点回答**这是哪个版本、当前采用什么关键配置与损失、测得什么结果**；入边回答**相对已记录前版本或对照基线改了什么**。完整 run 列表、路径、commit、loss 分量历史和长篇分析放在详细图、Markdown 和关联报告里。

渲染前从实际配置与结果整理 `node.overview`。辅助诊断、共享依赖和已替换的准备节点不需要完整卡片时，用 `include: false` 排除在本次概览之外，保留其完整来源记录。选入活跃变体及理解它们所需的基线，说明选入范围并连接完整历史。这只是同一事实来源的展示摘要，不另建一套实验台账。

| `node.overview` 字段 | 内容 |
|---|---|
| `title` | 简短版本名；较长路线可以加稳定短编号 |
| `group`, `order` | 研究路线与组内阅读顺序 |
| `config` | 一至两行关键配置：输入/条件、模型规模、噪声、batch 或预算，按本实验的重要性选择 |
| `loss` | 当前目标公式及重要权重，缩写在背景说明中解释一次；展示实测 loss 时注明 split/step 与定义 |
| `result` | 一个主要结果或明确标识的 ID/OOD 对，保留 checkpoint/step、单位和评估范围；生成指标写明是生成指标，不写成训练 loss |
| `detail_path` | 一个版本报告/规格入口，不在卡片里铺完整路径 |
| `include` | 可选布尔值，默认 true |

顶层 `overview` 支持 `title`、`context`（简短公共背景）和 `max_columns`（默认 3）。缺少摘要时，AI 应读取相关已有规格/报告再整理，不能把 renderer 的回退文字当作配置和 loss 说明。后续维护事实时同步更新受影响的概览字段，包括结果 checkpoint 和观察到的执行状态；概览自己的人工位置与批注独立保留，不沿用详细图的巨大布局。

`edge.overview.label` 写简短、具体的改动，例如“局部权重 10 → 1”或“加入 ESM 条件；10k → 50k 更新”。保留关系含义：对照与派生使用不同样式，两者都不等于加载权重；改了配置也不自动表示结果改善。`edge.overview.show: false` 可在概览隐藏某条边。如果有证据的单一派生路径跳过了准备节点，应标明折叠的中间步骤，不能凭位置或名字相近补造直接科学关系。共享数据/模型依赖归纳进公共说明或详情入口，不从每张卡片拉长线。

版本按有界宽度的行和研究路线面板紧凑排列，不让链长或边标签撑大整张图。每张卡片约 6–8 行简短内容；文字多时先缩写或移到详情，重要内容字号至少 22 px，边上的改动至少 20 px。执行状态直接写文字，不只靠颜色区分。连线走卡片间隙，起终点和标签易于追踪；分支较多时用“C1 → C3”这样的短编号标明端点。完整项目无法在普通桌面视窗清楚阅读时提供独立分组视图，不把所有节点挤成一张小字缩略图；分组图也应保留理解改动所需的基线背景。

详细图继续支持 `display` 的 `group`、`order`、`primary_path` 和初始 `x`/`y`/`width`，后续保留手动位置。`--relayout` 用于有意重新排布管理节点。`--study STUDY`、`--node NODE_ID` 仍可生成带依赖上下文的详细聚焦图；重要信息版与完整来源各自保留。

renderer 只把前两条 `context` 显示在画布，其余保留在 Markdown；优先用这两条解释结果指标和 loss 符号。公式展开、选模规则、历史说明和长段分析放 Markdown；读懂结果所需的单位、评估 step 和样本规模留在卡片或分组标题。关键配置、loss、结果或改动被截成“… → 详情”时，缩写 JSON 中的摘要，让重要内容完整显示。

交付由 renderer 持续维护的文件。卡片、背景和连线的事实修改写回索引，画布修改用于布局、样式和用户批注。不要另建一份硬编码事实文字或正常刷新不会更新的美化副本。视觉调整后，再运行一次正常渲染命令并检查交付图：摘要仍与 JSON 一致，分组文件仍由对应命令更新，人工位置与批注继续保留。

## 视觉检查

用 Excalidraw 渲染实际 `.excalidraw` 文件，再打开总览和局部图片。分别检查两个层级。重要信息版按普通桌面宽度（约 1440 px）查看，不依赖放大局部来宣称可读：版本、关键配置、loss、结果和边上的改动都应可辨。检查间距、箭头起终点、文字/卡片重叠及完整历史入口；详细图检查来源、依赖和产物入口。记录画布尺寸并交付一份实际可读的分组预览，巨幅图缩成的缩略图不算通过。修改相应内容或布局后再次查看。JSON/schema 正确不等于图有用。

随附原生预览脚本在 Chromium 中调用 `@excalidraw/excalidraw` 导出。复用已有依赖，缺少时在独立临时目录准备：

```bash
npm install --prefix /tmp/journal-map-runtime --no-audit --no-fund @excalidraw/excalidraw react react-dom esbuild playwright
node <skill-dir>/scripts/preview_experiment_map.mjs <map.excalidraw> <preview-directory> --runtime-dir /tmp/journal-map-runtime --viewport-width 1440
```

任务限定写入范围时，把 `TMPDIR` 设为允许的临时目录。Linux 的 `/proc` 可用时，helper 通过短目录句柄路径启动 Chromium，实际临时文件仍保存在该目录，长项目路径无需另外编写浏览器 wrapper。

使用 `--browser /absolute/path/to/chromium`，否则用该 runtime 的 Playwright CLI 安装 Chromium。输出 `native.svg`、`full.png`、`overview.png`、`detail-top.png` 和 `render.json`。使用图片查看工具实际查看；长图增加局部或聚焦视图检查，简短记录观察及修订。原生渲染不可用时明确这项尚未检查并保留可编辑图，不把近似重画的图片当作已验证。
