# Technical specification: data, model, objective, and evaluation

Establish this specification during initialization, check experiment changes before training, and record the version actually used afterward. It should let the next investigation answer what constitutes a sample, how it was processed, what the model computes and optimizes, and how results can be compared. Source snapshots and path indexes provide evidence; readable explanations establish meaning.

## Eight required areas

Inspect every area and populate known facts. Briefly identify inapplicable items and the specific missing sources for unresolved material facts. Extract information from code, configurations, and artifacts rather than asking the user to transcribe it.

| Area | Content and meaning | Default location |
|---|---|---|
| Task and sample | Task objective; sample/entity/frame identity; input, conditioning, target, and output fields, shapes, units, masks, and label sources | `specs/data.md` |
| Data provenance and version | Original sources, generation procedure, versions/manifests/hashes; raw→cleaned→features→cache lineage; paths, counts, and generating code; identity actually consumed by training | `specs/data.md`; MLflow data identifiers and manifest artifacts |
| Cleaning and preprocessing | Ordered operations, filters/deduplication/missing-value rules, thresholds and boundaries, affected units and splits, intersections/unions; normalization fit scope, truncation/padding/features; before/after counts, exclusion reasons and manifests | `specs/data.md`; configuration and statistics artifacts |
| Splits and sampling | Concrete train/val/test and ID/OOD definitions, split unit/seed/manifest; what is shared across splits; augmentation, resampling, mixture proportions, frame/sequence selection and effective sample counts | `specs/data.md`; run configuration |
| Architecture and initialization | Input-to-output module flow, dimensions/layers/connections; total and trainable parameters; pretrained sources, frozen/trainable modules, conditioning and gradient flow; changes from baseline | `specs/model.md`; model configuration and source artifacts |
| Loss and objective | Formulas AND implementation locations for the total, groups, and every leaf; symbols, units, target sources, masks, normalization/denominators/reductions; fixed/dynamic and ancestor weights, gradient recipients | `specs/objective.md`; metric dictionary and weight configuration/curves |
| Training protocol | Actual entry point, command, resolved configuration; optimizer, schedule, effective batch, unequal-rank batches/accumulation, updates, precision, clipping, seeds; host RAM/cache budget and preload strategy; stages, resume source and restored state | `specs/training-eval.md`; params/config/code artifacts |
| Evaluation and model selection | Full-set/fixed quick-subset identities and cache scope; inference/sampling/rollout/postprocessing; metric formulas and aggregation; quick/full cadence, best/final selection and tie rules; compared checkpoints and common protocol | `specs/training-eval.md`; metrics and evaluation artifacts |

Reuse and link existing documents covering these areas; combine files for smaller projects. Centralize definitions in the specification. Topic notes capture experiment changes, main results, and findings rather than duplicating the entire specification for each run.

## Understand the actual execution path

Start from a recent real run's launch configuration or manifest. Follow the entry point through loading and transforms, batch/collate, model forward, loss, backward, validation, and checkpoint selection. If no run exists, trace the agreed planned entry point and identify it as planned. Use the README to navigate and the run configuration with its corresponding source to explain the experiment. For source archives containing legacy or nested copies, identify the exact member and import path used by the entry point rather than selecting by basename.

Use an existing small sample or sample schema to explain how key tensors change shape, units, masks, and meaning. Prefer static tracing; use an existing small check when needed rather than launching full training for initialization. Explain dependencies for frozen models, offline caches, online conditioning, and training stages: identify cache producers and checkpoints and determine which branches execute.

For every active training line, explain its input, model, objective, evaluation, and changes from baseline. Reference shared definitions and expand only differences. Distinguish current defaults, actual run configuration, deployed source snapshots, and planned changes. Attribute implementations in different worktrees separately; the newest cleaning policy does not automatically describe older runs.

Loss definitions require **readable formulas and implementation locations**, not just function paths. Cover totals, groups, and leaves participating in the objective. Describe computed but unpublished leaf metrics and distinguish “computed” from “logged.” Express non-additive objectives faithfully. Explain variables named `raw` that already include child weights rather than classifying by name alone.

For example, dividing coordinate squared error by N versus 3N, or averaging per-sample square roots versus taking a square root after aggregation, changes comparisons. State these choices beside the formula and relate training objectives to evaluation metrics. Expand details relevant to the investigation and link complete specialist documents for complex definitions.

## Versioning and maintenance

Link key statements to files/symbols/configuration keys and code or data versions. Current uncommitted files may use content hashes; historical experiments should use their own snapshots. Identify the configuration and measurement method for quantities such as parameter counts; name the specific missing evidence when unavailable.

Before training, record the baseline, changes to data/model/objective/protocol, and intended observations in the topic note. At actual launch, save the specification and resolved configuration as snapshots or immutable version references associated with the run; `specs/` is a suitable MLflow artifact path. Later project edits must not alter historical run specifications.

After training, record actual departures from the planned configuration, data, or evaluation and connect main results. Newly inferred benefits still follow the user-discussion-and-recording workflow. Changes to data, model, objective, or protocol also update the affected specification, metric definitions, and map nodes. Update only affected sections.

## Discussion with the user

Present the extracted project understanding first. Then ask about decisions that affect the investigation, such as the comparison baseline, data version, or component curves. List missing factual sources separately. The user decides research direction and benefits; AI explains implementation and evidence.
