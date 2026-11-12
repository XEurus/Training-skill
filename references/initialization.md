# Initialize an existing project

Initialization turns existing code, historical training, and scattered evidence into maintainable experiment records. Build the overall outline and populate known information, then discuss decisions that actually affect recording. Reuse existing directories, metric names, MLflow experiments, and document structures.

## 1. Scope and inventory

Start with the current project and the branches or experiments specified by the user. Read project documentation, AGENTS.md, training entry points, configuration, notes, and run metadata, then follow their references. For large logs, read indexes, summaries, and metric files first rather than traversing every checkpoint or dataset payload.

| Source | Collect | Establish |
|---|---|---|
| Git and worktrees | Current and relevant historical branches, commits, diffs, workspace locations | What changed in each line and how code relates |
| Training code and configuration | Model entry points, loss hierarchy, weights, evaluation splits, hyperparameters | Recording items and meanings |
| MLflow | Accessible experiments/runs, params, metrics, tags, artifacts | Historical run identities, results, code snapshots |
| Local or connected storage | Logs, config snapshots, run manifests, checkpoint metadata, evaluation tables and figures | Additional evidence and artifact locations |
| Existing documents and user statements | Experiment purposes, recorded findings, decisions, baselines | Research topics, current understanding, historical conclusions |

Inspect Git history with read-only commands rather than switching branches for inventory. Mark inaccessible remote sources as pending and complete the accessible portion. Local historical records can enter the index without first migrating them into MLflow.

## 2. Explain the project before building the index

Read [Technical specification](technical-spec.md). Identify active research lines and their real launch configurations, then trace each distinct execution path from samples through model, objective, evaluation, and model selection. Use representative runs and follow their source snapshots; summarize archival lines separately. Explain the question and baseline change for each active line using existing plans.

Populate the eight technical areas in reusable project documents. Include a readable end-to-end account with shapes/units and dependencies, formulas with implementation references, and actual configuration values attributed to their run. Reuse complete specialist documents and fill gaps. Keep inferred research interpretations in discussion.

Record technical coverage in initialization.md: area, what was established, source/version, document location, and any specific missing evidence. This describes coverage of the investigation, not just files created. Separate recorded results, implemented behavior, planned changes, and user decisions.

## 3. Establish the overall outline

First create or update `requirements.md` to explicitly record the project's current needs. It guides subsequent experiments; `initialization.md` describes how those records are organized and integrated. Link the two documents.

The requirements record covers current goals and priority questions, the results the user wants, recording items with their meaning and form, agreed constraints, existing evidence, and concrete open choices. Record success criteria or acceptance methods when already defined; otherwise record the goals. User statements and existing requirements documents establish requirements. Code and logs describe the current state; label AI-proposed additions as “To discuss” rather than treating the current implementation as the user's requirement.

Populate established information with sources or evidence IDs instead of creating an empty template. Reuse an existing document when it already serves this purpose. Put an individual experiment's needs in the “Current needs and plan” section of `notes/<study>.md`: question, intended observations, baseline, changes, and recording approach, linked to project requirements. When the user explicitly changes goals, priorities, or recording needs, update current requirements and retain a brief dated change reason.

Draft `initialization.md` from the inventory. For each research topic, tabulate the question, recording items, meaning/calculation convention, source, storage form, comparison views, and update timing. Populate actual information rather than delivering empty templates.

Establish project defaults for experiment naming/grouping, metric dictionary, four views, ID/OOD relationships, paths, code snapshots, checkpoint conventions, notes, and proactive maintenance triggers. Populate definitions confirmed by code and existing conventions directly. Propose choices for ambiguities and discuss a small set that affects the results. Do not reconfirm choices the user already settled.

Read [Metrics and comparison](metrics-and-comparison.md) when populating `tracking.json`. Keep the four loss views (`train_raw`, `train_weighted`, `validation_raw`, `validation_weighted`) separate from the five comparison presets (`variants`, `id_ood`, `id_ood_across_variants`, `components`, `weight_effect`). Populate each view with the total, groups, and all scalar leaves; record unavailable values explicitly. Preserve `weighted_views` as `auto`, `on`, or `off`; put formulas and weight explanations in the metric dictionary. Save concrete metric keys or resolvable patterns in both views and presets, with availability by training/evaluation profile when it differs.

Read [Experiment execution and isolation](experiment-execution.md) when establishing execution conventions, even if this task only initializes records. Record actual rules in `tracking.json.execution` or existing project conventions: worktree root, branch/path naming, baseline commit plus dirty/untracked preservation, fixed-code seeds/sweeps, source stability during jobs, environment/import verification, per-run output/cache scopes, resource budget defaults, and ownership/concurrency. Inspect existing locations first; fill reusable defaults now so later launches discuss only changes.

For a project with multiple worktrees, establish one shared record root and put its actual location in the conventions used by each workspace. Experiment code may live on different branches while the index and maps accumulate in one place. Reuse an existing shared location; otherwise choose and explain a stable location, discussing it with the user when needed.

Keep the canonical journal stable outside disposable variant trees, or explicitly preserve its lifetime. All variants use the same absolute MLflow tracking location/backend and experiment. Specify a single writer or shared lock for re-read/merge/atomic-write/render of shared records; per-run events must survive until merged.

Store a locally accessible absolute path in `tracking.json.record_root` inside the shared directory. Write that same path into each workspace's managed AGENTS.md section and read configuration and indexes there directly rather than copying them into each workspace. Update entry points for workspaces covered by initialization; list unvisited workspaces as pending integration.

When historical records use different metric names, record aliases and definition mappings first. Compare together only when meanings and aggregation conventions match. Retain original records while future training adopts standard project names.

## 4. Index evidence and historical relationships

Save `evidence.json` with `schema_version: 1` and `sources: [...]`. Each source contains at least:

- `id`: stable identifier.
- `kind`: git, config, metric, artifact, document, or user_statement.
- `location`: file path, URI, run reference, or locatable user statement; optionally include `host`.
- `locator`: a commit, file line, JSON key, metric key/step, document section, or equivalent precise location.
- `observed_at`: collection time; use separate `recorded_at` for the original experiment time when available, otherwise null.
- `supports`: facts, values, or existing conclusions directly supported by the evidence.
- `node_ids`: associated experiment nodes.

Use evidence to connect branches, code states, runs, artifacts, and existing findings. Deduplicate by existing run/node IDs, combining multiple files for one run. Use `unknown` for an unknown execution state and an unknown revision for missing historical code. A historical run with an unknown tracking URI remains an evidence entry until enough information is available for a formal run association.

Preserve conclusions explicitly recorded in existing documents with their source and historical date. Keep newly inferred research benefits in discussion. When sources conflict, retain their specific locations and list the discrepancy in the outline for clarification.

## 5. Build maintainable project records

Create or incrementally complete these files from known information:

| File | Populated content after initialization |
|---|---|
| `requirements.md` or the existing requirements document | Current project needs, priorities, recording items/meanings/forms, constraints, evidence, open choices |
| `initialization.md` | Recording outline, inventory scope, material gaps, choices to discuss |
| `specs/data.md`, `model.md`, `objective.md`, `training-eval.md` or reused documents | Populated definitions for all eight technical areas, execution flow, source/version references, and actual run differences |
| `tracking.json` | Existing MLflow configuration, metric dictionary, frequencies, paths, comparison presets |
| `evidence.json` | Locatable historical evidence index |
| `experiment-map.json` | Research lines, branches, revisions, runs, paths; nodes may include an `evidence` ID list |
| `experiment-map.excalidraw` and `.md` | Visual routes with main changes/results, model/data dependencies, code and output entry points; complete path tables from the same source |
| `notes/<study>.md` | Current experiment needs and plan, existing main results, attributed findings, current understanding |

Initial onboarding organizes existing facts. Import historical data into MLflow only when the user requests migration, preserving sources and original times. Building an index alone does not rewrite old runs or substitute import times for training times. Use the pre-training workflow for logging integration needed by future runs.

Merge the project's proactive maintenance convention into the `<!-- experiment-journal:start -->` managed section in AGENTS.md, using the project hook template with actual record paths. Update only that section if it exists and preserve other content. Later experiment tasks then proactively update records and maps before finishing.

Repeated initialization merges by stable identifiers and preserves user notes, manual diagram layouts, and annotations. Do not duplicate records when facts have not changed.

## 6. Deliver

Before delivery, verify that a reader can reconstruct the main execution flow, locate each loss definition, distinguish current/run/planned versions, and identify the protocol behind a main result. Check the explanations against code and one representative configuration/result; schema and link validation alone are insufficient. Verify that the recording plan retains the four loss views and five comparison presets, and that each can resolve to the documented metrics or an explicit availability gap. Report concrete remaining sources instead of generic cautionary paragraphs.

Link the populated requirements record and overall outline, and present covered topics/branches/runs, an openable Excalidraw map, and the few decisions still needed. State which sources were read and which remain inaccessible. Read current requirements first next time and continue from these conventions rather than repeating a full inventory.
