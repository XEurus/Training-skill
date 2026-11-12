# Metric semantics and comparison

## Fixed metric dictionary

Before training, read the project's dictionary and map internal code variables to stable MLflow keys. Put model version, date, and improvement name in the run name or tags. Keep the meaning of a given key the same across runs.

Define each metric with a standard key or pattern, meaning, level, formula and implementation location, unit, mask, normalization and reduction, aggregation denominator, applicable dataset, weight relationship, and logging frequency. Fill these in as needed, focusing on definitions that affect comparability.

Use separate `formula`, `implementation`, and `definition_version` fields in new dictionaries, plus `computed`/`logged` when availability differs. During maintenance, expand legacy `formula_or_code` entries without deleting their original references.

For example:

```text
train/raw/total
train/raw/reconstruction
train/raw/reconstruction/position
train/weighted/reconstruction/position
train/objective
val/id/raw/total
val/ood/raw/total
```

Projects without ID/OOD may use `val/raw/...` consistently. Once a naming scheme is chosen, keep using it. When adding a data domain, extend the standard keys and retain existing comparable metrics. Leave missing components empty. If a formula or aggregation convention changes, explicitly record a definition version; use a new semantic key when needed and preserve a common evaluation convention for comparison. Do not treat same-named metrics with different definitions as equivalent.

A changed leaf formula also changes the identity of every group or total that contains it. For example, replacing MSE with Huber requires distinct fitting-group and affected total definitions, not only a new leaf key. Use stable formula-family keys for those changed aggregates; retain unchanged components and common evaluation keys across variants. Do not put variant names or dates into metric keys. Update the dictionary, applicability, views, and launch-time definition versions together. `train/objective` remains the actual optimized objective for every run; attach its definition and use the common evaluation metric for cross-objective comparisons. Changing a configured coefficient within the same declared weighted formula is recorded as a weight/config change, without renaming every metric.

## Raw values, weighted values, and totals

By default, a raw loss is the value after masking, required normalization, and reduction, but before applying loss-combination weights. Sample weights, class weights, or importance sampling in a particular model may be part of the loss definition; state them separately rather than inferring them from the word “raw.”

A weighted component is its contribution to the actual optimized objective. If a parent has weight α and a child has weight β, the child's contribution includes αβ. Compute totals using the project's explicit formula; do not double-count a parent and its children. If a meaningful raw total cannot be defined, log the existing components and actual objective, and explain the choice of total.

Always log `train/objective` as the objective actually used for backpropagation. Log dynamic weight curves under `weights/<component>`; save their initial values and schedule rules in the configuration. When comparing weight schemes, prioritize raw values and evaluation metrics with consistent definitions. If a common total score is needed, agree separately on fixed reference weights.

## Four views

| View | Contents |
|---|---|
| Training raw loss | Total, all components, and scalar subcomponents |
| Training weighted loss | Total and weighted contributions of components at each level |
| Validation raw loss | Same; plot the same component for ID/OOD together by default |
| Validation weighted loss | Same; plot the same component for ID/OOD together by default |

The weighted view supports `auto/on/off`. `auto` enables it when nontrivial multi-term weighting or dynamic weights need inspection, and omits it when the curves would mostly repeat one another. Even with this view off, retain the actual training objective. Log weighted validation values only when there is a clear weighted validation objective. Save large per-sample or per-token details as attachments when needed.

Store these groupings in `tracking.json.loss_views`, with stable view IDs, metric patterns, included levels (`total`, `group`, `leaf`), and paired validation domains. Keep `weighted_views` as the display policy enum; formulas belong in the metric dictionary. The five comparison presets below select runs and metrics within these views; they do not replace the views.

During integration, give every enabled view a usable entry: a saved MLflow layout, a generated page/command, or concrete steps for opening it in the installed UI. Exercise each view on a real run and check that its total, groups, and scalar leaves are accessible, with matching ID/OOD components paired. A metric namespace or `loss_views` configuration alone is not the delivered view. When weighting becomes relevant in a later experiment, update these entries along with the dictionary.

## Sampling, aggregation, and x-axis

Reuse the project's logging frequency. If none is set, first propose a concrete frequency based on training cost and agree on it with the user once; do not impose a fixed frequency on every project. Distinguish current-batch values from window statistics and keep their meanings consistent.

By default, `step` is the number of optimizer updates; log epoch separately. For validation, use the step of the model being evaluated. Aggregate over the entire declared evaluation scope (the fixed quick subset or the full validation split) using its defined denominator. In multi-GPU runs, aggregate numerators and denominators before calculating the mean, rather than averaging means from batches or ranks with unequal sizes. Aggregate ID/OOD separately; if an overall value is needed, state the combination proportions.

When batch size, gradient accumulation, or sequence length changes, you can log `progress/samples_seen` and `progress/tokens_seen` to align runs by training volume. Preserve full historical curves; apply smoothing only for display.

## Routine subset validation and periodic full validation

For new experiment plans without an established evaluation contract, use a **fixed 10–20% validation subset** for routine checks, typically each epoch. Choose a representative subset per domain using the relevant strata (for example, task, length, or rare subgroup), and save its seed, sample IDs, counts, fraction, and manifest/hash. Reuse the same subset across comparable variants. Increase coverage when important groups or metric stability need it; the fraction is a starting range, not a statistical guarantee. Keep the subset resident or preload it under the execution reference's RAM budget.

Run full validation every **2.5% of the planned total epochs**, and at the final checkpoint. Resolve the interval before launch as `max(1, ceil(planned_total_epochs * 0.025))`: a 200-epoch run evaluates every 5 epochs. Save the planned total and resolved `full.every_epochs` in `tracking.json.validation_policy`; count completed epochs from the run's start, including after resume. For step-budgeted training, resolve the equivalent interval from total planned optimizer updates. Short budgeted experiments still receive a final full evaluation; preparation-only smoke checks retain their bounded scope. Before adopting a checkpoint as the reported best, evaluate the candidate on the agreed full validation scope; define separately whether early stopping/scheduling uses quick or full measurements and how its patience is counted. Preserve an existing explicit evaluation contract unless it is intentionally changed and recorded. Full evaluation covers the declared validation split, not the held-out test set, and does not require rereading already cached data.

Keep quick and full curves distinct: retain existing full keys such as `val/{dataset}/raw/{loss}` and use `val_quick/{dataset}/raw/{loss}` for the subset (likewise for weighted values). Record scope identity and actual evaluated counts with each evaluation. Use the same naming and subset manifest across variants; compare quick with quick and full with full. The four loss views and comparison presets should label/select the scope explicitly, with full results as the formal comparison default. Summaries and best-checkpoint reports state which scope produced each result.

## Quick comparisons

Save five project presets: the same metric across improvements; ID/OOD within one run; ID/OOD across improvements; comparisons between components; and the same component before and after weighting. Support direct requests such as “compare the baseline and this improvement's ID/OOD total loss.” First resolve the explicit runs, metrics, and x-axis, then produce the result.

Give each applicable preset a working entry point, such as a saved UI view, link, or short command that accepts selected runs. Exercise the entries against actual recorded metrics; a name in `tracking.json` alone is not a shortcut. If a preset is redundant or inapplicable, state why at that entry rather than displaying missing data as a valid comparison.

The four views are logical display groupings; do not assume MLflow has four native pages. Check what multi-metric plots, layouts, and saving options the installed version supports, and prefer an available interface. If there is no applicable automatic-layout interface, provide concrete configuration steps or use the public API to retrieve metric history and generate comparison plots. Do not claim that writing a namespace automatically creates pages or shortcuts.

Label comparison plots with run, data domain, and component, and keep x-axis and smoothing consistent. Components with different scales or units can use side-by-side plots; choose based on the current analysis. Generate tables at the same checkpoint, final checkpoint, or defined best-checkpoint convention, and state which one was used.
