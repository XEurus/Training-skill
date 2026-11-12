<!-- experiment-journal:start -->
## Proactive experiment journal maintenance

This project uses `$mlflow-experiment-journal` (display name `exp/experiment-journal`). Records live under `experiments/`; read requirements.md and current topic needs first, then tracking.json, experiment-map.json, and existing results. During initialization, replace these with the actual record root and requirements document path; all worktrees share that same root.

For requested variant implementation/execution, read the skill’s experiment-execution reference and project execution rules first: independent code variants use branch/worktree isolation, fixed-code seeds/sweeps use separate runs/configs/outputs, and active jobs retain stable source/import paths. Use the canonical absolute record root and tracking backend from every worktree; merge concurrent journal changes through the agreed single writer/lock. Routine worktree preparation is included in authorized experiment execution; journal maintenance alone does not authorize training.

After confirmed requirements changes, experiment-related code/config changes, branch/worktree changes, training start/resume/end events, artifact location changes, or explicitly recorded findings, proactively use the skill before finishing the task: update affected requirements, technical specifications (data/model/objective/training-evaluation), facts, and evidence, maintain the experiment index, and update affected compact configuration/loss/result summaries and change labels, then regenerate compact and full Excalidraw/Markdown views when map facts change. Leave files unchanged when nothing changed.

Automatic maintenance records facts and findings the user already settled or asked to preserve. Retain historical code revisions, user notes, manual diagram layouts, and annotations. Existing logging records training metrics; configured lifecycle callbacks can refresh the map immediately, otherwise reconcile changes when the AI next checks training status.
<!-- experiment-journal:end -->
