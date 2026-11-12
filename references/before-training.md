# Decide what to record before training

## Discussion and logging plan

First read project requirements and the current experiment plan, then inspect the training entry point, loss implementation, configuration, MLflow integration, and existing experiment records. Present the meanings you understand and the decisions that actually remain. Do not ask the user to re-enter information available from the code.

| Decide | Record and meaning | Form |
|---|---|---|
| What is being explored | Research topic, main change, baseline, and comparisons of interest | Opening of the topic note, run tags |
| What to observe | Loss hierarchy, evaluation measures, ID/OOD split, units, and aggregation convention | Metric dictionary, metrics |
| How to observe it | Frequency, x-axis, comparison presets, and weighted-view switch | Project tracking configuration |
| GPU efficiency | Per-device utilization target >90%, sampling windows/intervals, phase boundaries, and useful throughput unit; follow [GPU sampling](experiment-execution.md#gpu-utilization-sample-improve-and-record) | `tracking.json.gpu_utilization`, system metrics, raw-sample artifact |
| Host RAM and I/O | Allowed run RAM, non-cache peak/headroom, cache cap, resident data, and prefetch plan | `tracking.json.memory_cache`, measured memory/throughput, artifact paths |
| Validation cost and scope | Fixed 10–20% subset identity; quick/full cadence, cache policy, and model-selection scope | `tracking.json.validation_policy`, subset manifests, separate quick/full metrics |
| What was run | Actual configuration, training code, data version, and dependencies | Params, configuration and source artifacts |
| Where results are saved | Inputs, run directory, logs, checkpoints, and analysis results | Path inventory, experiment map |

If no success criterion has been defined, record the experiment's purpose. Ask only about gaps that affect the current work; carry forward choices that are already known. Before training, provide a concise logging plan for this task, then integrate it into code within the already authorized scope.

When this task implements or executes variants, read [Experiment execution and isolation](experiment-execution.md) before modifying or launching code. Carry forward the agreed budget and worktree/output rules; a logging-only task does not launch training.

## Specification and experiment changes

Read [Technical specification](technical-spec.md) and the existing project definitions. Record this experiment’s baseline and changes to data, model, objective, and training/evaluation protocol. Resolve the effective configuration through launch scripts and overrides, distinguish the actual dataset from newly prepared versions, and map the objective through leaf losses to published metric keys. Capture versioned specifications at launch with the code/configuration snapshot.

## Identity and lifecycle

An MLflow experiment usually represents a stable project or training task; `study` represents a research question, `variant` an improved version, and each concrete training run and each seed have their own run. Use tags for `study`, `variant`, `baseline_run_id`, and `journal.node_id`; save the random seed as a param. Put application-specific tags in their own namespace.

Key execution records by `run_id` (or an equivalent unique execution ID), with `variant` as a grouping field. The registry must retain repeated runs and different seeds of the same configuration; a learning rate or variant name is not a unique execution identity.

For initial setup, reuse the existing tracking URI, experiment, and authentication method. Once the logging plan is ready, create the run when real training starts, then write its run ID to local run metadata and the experiment map. Training, autologging, and manual logging must share an explicitly selected run; check that they do not create duplicate runs.

For recovery from a failure with the same configuration and objective, resume the same run and restore the global step. If training changes a key configuration, objective, or data, create a linked new run and identify the source checkpoint. For analysis added later, use the client to specify the old run; do not change its status or end time.

For checkpoint inheritance, record the checkpoint actually loaded, its parent run and identity, which model/optimizer/random states were restored or reset, and the child's local and cumulative training budget. Initialization metadata describes the loaded state; a prepared seed checkpoint is only its source when it was actually used.

Keep the training outcome separate from journal synchronization. Save the checkpoint and execution outcome before refreshing the index, diagrams, or reports. If a post-training artifact upload or view update fails, record the affected operation as pending synchronization and retry from saved metadata; do not mark completed training as failed or repeat optimizer steps to repair its records. Keep the original run, metric history, and startup snapshot. Training exceptions still retain their actual failed or interrupted state.

## Metadata allocation

| Category | Where and what to save |
|---|---|
| Fixed hyperparameters | params: initial learning rate, optimizer, batch size, effective batch size, gradient accumulation, precision, seed, and fixed loss weights |
| Values that change over time | metrics: learning rate, loss weights, training progress; GPU training also records sampled per-device utilization, memory, step time, and useful throughput |
| Full configuration | artifact: actual configuration after resolving defaults, inheritance, and command-line overrides, including loss definitions and logging conventions |
| Data | Version or manifest identifier, split, sample count, preprocessing, and actual paths; follow the existing data-version mechanism |
| Environment | Python, framework, CUDA, GPU/process count, and existing dependency lockfile or environment export |
| Launch | Training command, resolved entry point/cwd, interpreter and observed module/local dependency locations, run host, start time, and time zone |
| Checkpoints | Locations of best and final checkpoints, step, selection metric, and corresponding result |

MLflow params express fixed facts. Use tags or descriptions for updateable notes, and artifacts for long text and full configuration. Record a shareable tracking address; use environment configuration for credentials and exclude credentials from configuration exports.

## Training code and paths

At the start of real training, save the commit, branch, uncommitted diff, and a local source snapshot of code involved in training, including new uncommitted files. Include the training entry point, model, loss, data processing, and local dependency code. Save configuration and dependency manifests as well, so the version used at the time can be inspected.

Use the code snapshot to describe uncommitted changes; logging alone does not require a commit or new branch. Independently developed variants follow the branch/worktree policy in the execution reference. The startup snapshot identifies historical code; also keep the source and local dependencies actually read by an active job stable until it exits. Later workspace changes do not redefine that run’s revision.

Each path entry includes its purpose, host/storage location, path or URI, and whether it was uploaded as an MLflow artifact. Handle large data and weights according to project conventions; when saving only a remote path, clearly mark it as an external location. Link the branch, code version, key changes, and artifacts to the experiment map.

## Integration check

Custom training loops usually need explicit logging for their components, so first inspect what autologging already records. Verify with an existing small project run or a minimal viable training/evaluation snippet that the run identity is correct, key metrics can be read back, ID/OOD names are correct, and steps correspond to the code snapshot. In distributed training, have the designated process write aggregate results.

Include the execution reference’s cwd/import/editable-dependency and writable-path checks in the actual launcher environment. After this check, execute the experiment within the user’s existing authorization and budget; record the actual startup identity and measured outcome.
