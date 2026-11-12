---
name: mlflow-experiment-journal
description: 围绕研究问题实现、执行和比较多模型变体，管理隔离 branch/worktree 与共享实验日志；梳理数据、模型、损失和训练评估，维护 MLflow、实验发现与 Excalidraw/Markdown 溯源图。适用于实验执行、项目初始化、历史证据整理及 ID/OOD 对比。
---

# exp/experiment-journal

Implement and execute requested experiment variants as well as recording them. Organize the work around four questions: **what to agree with the user, what to record, what the information means, and how to save and present it**. MLflow stores values, configuration, code, and artifacts. Markdown stores the main results, findings, and next decisions. The experiment map connects research lines, code branches, runs, and actual file locations. Maintain a compact first-read overview of key configurations, losses, results, and version-to-version changes alongside the detailed provenance map.

## Maintaining the Chinese and English versions

`zh/SKILL.zh.md` and `zh/references/*.zh.md` are the user-edited Chinese source files; the root `SKILL.md` and `references/*.md` are their English counterparts for AI use.

The user manually arranges version updates. During normal use, read the English version directly without bilingual change checks, automatic translation, or synchronization. When the user asks to sync English, update it from the Chinese source. When asked to change the skill, maintain both versions within the requested scope.

Keep technical identifiers, fields, defaults, and file links aligned between the versions. Links within Chinese files point to Chinese references; English links point to English references. The user can simply say “sync the English version.” Use Chinese with the user by default; use the project's customary language for records.

## Workflow

First read the current project requirements, topic-specific experiment needs, existing conventions, relevant configuration, and recent records. Organize what is already known and discuss only missing decisions that affect this record. Offer concise, concrete options or recommendations, such as “keep the original validation loss and add paired ID/OOD plots.” Determine reusable defaults during the initial setup; later, focus discussions on changes.

AI can extract facts, check values, and take part in analysis. The user determines in conversation whether an experiment succeeded, where its benefit lies, and what to do next. Keep candidate interpretations in the conversation; when the user explicitly says “record this” or equivalent, write the relevant finding directly without asking them to confirm each item again. Record training status separately from research conclusions.

Read references for the current task:

| Scenario | Read | Output |
|---|---|---|
| Onboarding an existing project, organizing historical experiments, or initialization | [Project initialization](references/initialization.md), plus relevant topics below | Populated requirements record, recording outline, evidence inventory, project conventions, initial maps, and existing findings |
| Establishing or changing data, architecture, objectives, or protocols | [Technical specification](references/technical-spec.md) | Readable data/model/objective/training-evaluation definitions with versioned evidence |
| Implementing, executing, or comparing model/code variants; parallel experimental development | [Experiment execution and isolation](references/experiment-execution.md), then the relevant specifications below | Isolated variants, checked launch paths, actual runs, and a traceable comparison |
| Preparing before training or first-time integration | [Before training and metadata](references/before-training.md); also read [Metrics and comparison](references/metrics-and-comparison.md) when metrics are involved | This run's logging plan, configuration, and integration work |
| Viewing curves, comparing runs, or comparing ID/OOD | [Metrics and comparison](references/metrics-and-comparison.md) | Plots or a comparison of the main results |
| Organizing post-training results or recording findings | [Results and findings](references/results-and-findings.md) | Markdown, an MLflow summary, and attachments |
| Viewing or updating research lines, branches, or paths | [Experiment map](references/experiment-map.md) | Structured index, Excalidraw diagram, and Markdown/Mermaid overview |

Initialization and pre-training work also read [Technical specification](references/technical-spec.md) and [Metrics and comparison](references/metrics-and-comparison.md). Cover all eight areas, trace the actual execution path, and explain formulas and data flow. An inventory or valid diagram alone does not establish project understanding.

For execution, follow question/budget → isolated variants → implementation/specification → small checks → authorized runs → measured comparison → discussed findings. Independently developed code variants use separate branches/worktrees by default; seeds/repeats of fixed code use independent runs. All worktrees share one canonical journal root. Read the execution reference before preparing these workspaces.

GPU runs must sample utilization before and during training; in principle, each device's steady-state training mean should exceed 90%. Follow the execution reference's sampling, bottleneck adjustment, and evidence-recording procedure.

State the run's host RAM and cache budgets before preloading; prioritize training I/O, then resident or prefetched validation subsets. New plans normally use a fixed 10–20% quick-validation subset and full validation every 2.5% of the planned total epochs plus final (every 5 epochs for a 200-epoch run), with distinct metric scopes as defined in the execution and metrics references.

The training program is responsible for continuous logging; the skill does not need to be called at every step. Preparing a logging plan or recording a finding does not launch a full training run. Execute training according to the authorization for the user's current task.

## Proactive maintenance

In projects with `tracking.json`, `experiment-map.json`, or established journal conventions, invoke this skill for incremental maintenance after confirmed requirements changes, experiment-related code or branch changes, run start/resume/end events, artifact location changes, or explicitly recorded findings. Update the requirements record when goals or recording needs change; update affected technical specifications, map nodes, and evidence and regenerate views when map facts change. Do not wait for a separate maintenance request; leave files unchanged when nothing changed.

During initialization, merge the convention in `assets/project-hook.zh.md` or its English counterpart into project `AGENTS.md`, preserving existing content and language so later chats also select the skill proactively. This mechanism acts when the AI performs related work or observes a change. For immediate updates from background training, integrate event updates into existing training callbacks as described in the map reference.

## Project conventions

Prefer existing directories and naming. For a new project, default to `experiments/`:

```text
experiments/
  requirements.md        # Current project goals, recording needs, priorities, and agreed constraints
  specs/                 # Data, model, objective, training/evaluation; reuse existing documents
  tracking.json          # URI, metric dictionary, logging frequency, comparison presets
  initialization.md      # Recording outline, historical scope, and open questions
  evidence.json          # Index of existing data and evidence
  experiment-map.json    # Structured links among experiments, branches, code versions, runs, and paths
  experiment-map.overview.excalidraw # Compact configurations, losses, results, and change arrows
  experiment-map.overview.md # Overview context, selection, and detail links
  experiment-map.excalidraw # Full provenance map with editable layout and annotations
  experiment-map.md      # Mermaid overview and detailed tables from the same source
  notes/<study>.md        # Topic-specific needs and plan, main results, and findings
```

`assets/tracking.example.json` provides an adaptable structural example; replace example values with the actual configuration during first-time integration. `assets/experiment-map.empty.json` is an empty index for the experiment map. `assets/note-template.zh.md` and `assets/note-template.en.md` provide note templates. Create only files needed for the current task.

Initialization always creates or updates a populated requirements record, using `assets/requirements-template.zh.md` or its English counterpart. Reuse and link an existing requirements document when it already serves this purpose. For one experiment, record its current needs and plan in its topic note and link applicable project requirements; do not create duplicate project documents for each run.

Write confirmed loss semantics, mappings, and display choices into the project configuration. Save a configuration snapshot with every run; later changes to project defaults must not change historical records.

## Writing and delivery

Focus on purpose, defaults, and concrete results. Use one paragraph per point, and tables for fields and comparisons; include examples when they help understanding. Findings should include the necessary key numbers, comparison subjects, and evidence links. Mention a limitation only when a specific issue affects this interpretation; do not add fixed confidence scores or a cautious closing disclaimer. Omit sections that have not been discussed.

At the end, briefly state where information was saved, which runs are related, whether the experiment map was updated, and any specific items still missing. Save newly discovered project-specific exceptions in project conventions; add general practices to the skill only after they recur.
