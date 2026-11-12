# Experiment map

## Purpose and discussion

The experiment map answers: What research lines exist now? Which Git branch or worktree contains each line? What changed? Which training runs correspond to it? Where are the data, code, and results?

Extract facts from existing configuration, Git, run metadata, and MLflow. Derivation relationships among research lines must come from recorded sources or user statements; do not infer a relationship merely from similar names or better metrics. Clarify which line a new experiment develops from, its main changes, and whether there is a new research judgment to record.

## Files and structure

`experiment-map.json` in the project's agreed directory is the structured source for facts and relationships. Maintain two reading levels from that same data: `experiment-map.overview.excalidraw` is the compact first-read view; `experiment-map.excalidraw` and `experiment-map.md` retain the full provenance diagram, Mermaid, and path tables. The overview has its own short Markdown companion. After updating the JSON, run:

```bash
python <skill-dir>/scripts/render_experiment_map.py <project>/experiments/experiment-map.json
```

By default (`--view both`), generate the detailed pair and the `.overview.excalidraw` / `.overview.md` pair beside the input. Use `--view overview` or `--view detailed` to update one reading level. `--overview-group GROUP` creates a separately suffixed overview for one research line without replacing the combined overview. Use `--format excalidraw` or `--format markdown` for one format, or the default `--format both`. `--output` selects the base Markdown path; `--excalidraw-output` selects the base Excalidraw path, with overview suffixes appended to the stem. The script reads registry facts, renders views, and reads the existing Excalidraw layout; the AI or training event integration collects Git and MLflow information.

Open the diagram in Excalidraw or an editor extension. Stable element IDs support updates: refresh managed factual text and relationships while retaining user-moved positions, layout styling, and unmanaged annotations. Edit facts in JSON; canvas layout and free annotations remain in `.excalidraw`. Show main changes inside nodes; consult Markdown tables and topic notes for full commits, runs, evidence, and paths.

Top-level fields are `schema_version: 1`, `project`, `updated_at`, `nodes`, and `edges`. Each node represents an independently describable experimental improvement or research line; it can be associated with multiple seeds/runs. Use stable IDs such as `exp_001`.

| Node field | Meaning |
|---|---|
| `id`, `title`, `study` | Stable identity, name, and research topic |
| `execution_status` | `planned`/`running`/`finished`/`failed`/`interrupted`/`archived`/`unknown`, the execution state |
| `summary`, `question` | Optional short purpose and research question, shown on the card |
| `results` | Optional list of key measured results, with dataset/checkpoint convention; separate from research judgments |
| `executions` | Backend-neutral training identities, even when no MLflow run is known |
| `display` | Optional detailed-diagram group/order and initial layout preferences |
| `overview` | Curated short title, current key configuration, objective, measured result, group/order, and detail link; see below |
| `changes` | Array of strings describing the main changes relative to the source line |
| `revisions` | Code-state list; preserve history, see below |
| `runs` | MLflow runs, including the code state each belongs to |
| `paths` | Locations for data, output, logs, checkpoints, analysis files, and so on |
| `findings`, `decision`, `note_path` | Summary of confirmed findings, decisions, and topic note location; can be empty |
| `evidence` | Optional list of source IDs from evidence.json |

Keep the baseline → variant → revision/run chain explicit: source/baseline nodes connect to variants through evidenced derivation or comparison edges; each variant retains its successive revisions and all seeds/repeats as runs. Reuse one node for fixed-code repeats; do not create a new research line merely because another seed ran. Put the exact starting commit plus dirty/untracked snapshot identity in baseline revision evidence and link the topic plan.

Each revision includes `id`, `repo`, `branch`, `commit`, `dirty`, `worktree`, `host`, `observed_at`, `code_snapshot`, and `patch_path`. Use `null` for unknown values. The branch name helps locate the code, while the commit and source snapshot identify the actual code; do not rewrite an old revision when a branch later moves. Append a revision for a new code state.

Each run includes `run_id`, `tracking_uri` (shareable address), `experiment_id`, `url` (verified UI link or `null`), `revision_id`, and `status`. Link each real run to an existing revision; if historical code is unknown, create a revision clearly marked unknown instead of substituting the current branch. Record resumed training under the same run and new training under a new run ID.

An optional `executions` entry has `id`, `backend`, `status`, `observed_at`, `directory`, `revision_id`, and `host`. Only `id` is required; use null for missing facts. A non-null revision_id must refer to this node’s revision. Use existing operation-directory/job identities with a stable local ID, and preserve the observation time. `runs` remains reserved for actual MLflow runs. An unavailable MLflow server must not erase locally evidenced training history.

Each path includes `role`, `host`, `location`, and `storage`; `storage` is `external` or `mlflow-artifact`. For example, record a checkpoint's server path separately from its uploaded artifact URI.

An edge includes `from`, `to`, and `relation`. `relation` is `derived_from`, `continues_from`, `compares_to`, or `merges_from`. Direction is source/baseline → new line/comparison subject. Multiple source edges may point to the same node. This is a research relationship graph, not an automatically generated Git commit DAG; if an actual Git merge relationship is recorded, note it separately in `changes`.

Code derivation does not imply checkpoint inheritance. Record actual loaded checkpoint/parent run and load semantics in run metadata and topic notes, and add a model dependency only when used.

Dependency edges additionally support `uses_model` and `uses_data` (consumer → dependency), and `produces` (producer → artifact). Keep these distinct from research derivation. Optional `label` explains the concrete relationship, such as “frozen Stage1 epoch11”; `evidence` lists supporting source IDs. Include known parent models, cache/data versions, and outputs when they explain the experiment. A prepared data version can be shown without claiming an existing run adopted it.

## When to update

Before training, create or update the planned node, known code state, and expected paths. After real training starts, add the run and startup code snapshot. After training, complete status, checkpoints, and artifacts. Update affected lines after experiment code/config/branch/worktree changes. When findings are recorded at the user's request, update `findings`, `decision`, and the note link. Proactively maintain the map when these events occur during the current task, without requiring a separate map-update request.

After initialization writes the proactive convention to project AGENTS.md, subsequent relevant chats read and update the existing index before finishing. Preserve the same fact source and stable IDs across chats; merge differences before rendering and leave updated_at and output files unchanged when nothing changed.

Apply the no-change rule in the project reconciliation entry point as well as the renderer: merge the saved events into current facts, compare the result before changing `updated_at`, and skip unchanged JSON, Markdown, and diagram writes, including their mtimes. Replaying the same saved event is not a new training observation. Exercise reconciliation twice with unchanged input to check this behavior; preserve independently recorded observations when facts actually change.

Keep lifecycle occurrence time distinct from status observation and event delivery time. A later status readback does not restart or extend training: derive start/end times from the authoritative run or lifecycle receipt, recording the source; leave them unknown when that evidence is absent. Merge delayed events by lifecycle/attempt identity and occurrence order, preserving observations without letting an old start regress a completed attempt. An actual resumed attempt is a new lifecycle event. Check both a later readback and a delayed startup receipt against the saved run state and times.

For immediate background-training refreshes, record run start, checkpoint, completion, and exception events in the project's existing main-process/rank-0 lifecycle callbacks. Write events to independent run metadata first, then merge them into the index through one project update entry point and invoke the renderer. All worktrees target the canonical `record_root`. Use a single writer or shared lock for concurrent updates, covering re-read of the latest files, merge by stable IDs, atomic replacement, and rendering. Keep per-run events durable until reconciled and preserve independent worker updates; an atomic write alone does not prevent a stale update from losing another run. Installing the skill alone does not create a persistent watcher; without callbacks, reconcile changes when the AI next checks training status.

Read and write journal JSON and Markdown explicitly as UTF-8, including inside training callbacks. Run map refreshes outside the training exception handler: a rendering failure leaves an event to reconcile, without changing the recorded training outcome.

Maintain existing node IDs, revision IDs, and run associations. If a branch is deleted or a worktree is moved, append a note or new state while preserving historical training locations. Map-only organization does not create or switch branches. This does not restrict routine branch/worktree preparation for authorized experiments under [Experiment execution and isolation](experiment-execution.md). Do not automatically merge or delete experimental branches/worktrees after execution. Leave unknown facts `null` or unrecorded; they do not prevent adding other known information.

## Compact overview and detailed provenance

Use the compact overview as the default reading entry. A card answers **which version, what configuration and loss it uses now, and what was measured**; the incoming edge answers **what changed from its recorded predecessor or comparison baseline**. Keep full run lists, paths, commits, component histories, and narrative analysis in the detailed diagram, Markdown, and linked reports.

Before rendering, curate `node.overview` from its actual configuration and results. Use `include: false` for supporting diagnostics, shared dependencies, and inactive preparation nodes that do not need a full card in this reading view; retain their complete source records. Include active variants and the baselines needed to understand them. State the selection and link to the full history so omitted nodes remain discoverable. This is an editorial projection of the same facts, not a second experiment ledger.

| `node.overview` field | Content |
|---|---|
| `title` | Short version name; a stable short code may help trace long routes |
| `group`, `order` | Research line and reading order within it |
| `config` | One or two short lines: distinguishing input/conditioning, model size, noise, batch, or budget; choose what matters for this experiment |
| `loss` | Current objective and important weights; explain abbreviations once in the context. Include a measured loss only with its split/step and definition |
| `result` | One key result or an explicitly labeled ID/OOD pair, with checkpoint/step, units, and evaluation scope. Label a generation metric as such rather than calling it training loss |
| `detail_path` | One entry to the version's report/specification; no full paths inside the card |
| `include` | Optional boolean; defaults to true |

Top-level `overview` supports `title`, `context` (short shared explanations), and `max_columns` (default 3). Missing summaries should lead the AI to read the relevant existing specification/report; the renderer's fallback is not a substitute for explaining configuration or loss. On maintenance, update affected overview fields together with the underlying facts, including the result checkpoint and observed execution state. Preserve manually arranged overview positions and annotations separately from the detailed diagram.

Use `edge.overview.label` for a short concrete delta, such as “local weight 10 → 1” or “add ESM conditioning; 10k → 50k updates.” Preserve relationship meaning: comparisons stay distinct from derivation, and neither implies weight inheritance. A code change is not automatically an improvement in results. `edge.overview.show: false` can omit an edge in this reading view. If a proven single derivation path skips hidden preparation nodes, identify the collapsed intermediate step; never invent a direct scientific relationship from proximity or similar names. Shared data/model dependencies belong in compact context or detail links rather than repeated long arrows.

Pack nearby versions into bounded-width rows and research-line panels, rather than letting the length of a chain or its edge labels expand the canvas. Keep cards to roughly 6–8 short content lines; shorten or move secondary text to details before reducing font size. Use at least 22 px for important card text and 20 px for edge deltas. Show execution status as text, not only color. Route edges through inter-card gaps and make endpoints and change labels easy to follow; short endpoint codes such as “C1 → C3” help distinguish branches. Provide separate group views when a full project cannot remain readable in one ordinary desktop viewport; do not squeeze every node into a single thumbnail. Group views should also retain enough baseline context to understand changes.

For detailed diagrams, optional `display` retains `group`, `order`, `primary_path`, and initial `x`/`y`/`width`; later rendering preserves manual positions. `--relayout` intentionally recomputes managed layout. `--study STUDY` and `--node NODE_ID` remain available for detailed focus views, including dependency context. The compact view and the full source remain separate outputs.

The renderer shows the first two `context` entries on the canvas and keeps the rest in Markdown. Prioritize the displayed metric's meaning and loss-symbol definitions there. Keep expanded formulas, model-selection rules, historical explanations, and narrative analysis in Markdown; put the units, evaluated step, and sample scope needed to read a result on its card or group title. When a key configuration, loss, result, or change is cut to “... → details”, shorten its JSON summary until the important content is visible.

Deliver the renderer-managed files as the maintained views. Put factual card, context, and edge edits in the registry; use canvas edits for layout, style, and user annotations. Avoid a second hard-coded factual text dictionary or polished diagram copy that normal regeneration does not update. After visual refinements, run the normal render command again and inspect the delivered views: summaries must still match the JSON, group outputs must remain connected to their render commands, and manual layout or annotations must survive.

## Visual inspection

Render the actual `.excalidraw` file using Excalidraw, then open its overview and detail images. Check both reading levels. For the overview, inspect an image at ordinary desktop width (roughly 1440 px), without relying on zoomed details to claim readability: version, key configuration, loss, measured result, and edge changes must be legible. Check compact spacing, arrow endpoints, label/card overlaps, and visible access to omitted history. For the detailed diagram, check provenance, dependency and artifact entry points. Record the canvas dimensions and an actual readable group preview; a huge fitted thumbnail does not pass this check. Rework the affected data or layout and inspect again. JSON/schema validation alone does not establish that the diagram is useful.

The bundled native preview helper exports through `@excalidraw/excalidraw` in Chromium. Reuse available runtime dependencies; otherwise prepare an isolated temporary runtime:

```bash
npm install --prefix /tmp/journal-map-runtime --no-audit --no-fund @excalidraw/excalidraw react react-dom esbuild playwright
node <skill-dir>/scripts/preview_experiment_map.mjs <map.excalidraw> <preview-directory> --runtime-dir /tmp/journal-map-runtime --viewport-width 1440
```

Set `TMPDIR` to an allowed temporary directory when the task constrains writes. On Linux with `/proc` available, the helper gives Chromium a short directory-handle path while keeping its temporary files in that directory; long project paths need no custom browser wrapper.

Use `--browser /absolute/path/to/chromium` for an existing browser, or install the runtime’s Chromium with its Playwright CLI. The output includes `native.svg`, `full.png`, `overview.png`, `detail-top.png`, and `render.json`. Inspect actual images with an image-viewing tool, including additional areas or focused views for long diagrams. Keep a brief note of observations and any changes. If native rendering is unavailable, report that specific unchecked item and retain the editable diagram; do not substitute an approximate redraw and call it verified.
