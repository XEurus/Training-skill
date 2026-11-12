# Results, findings, and next experiments

## Establish facts, then discuss meaning

After training, read the actual records for the specified runs and existing topic notes. Organize run status, training progress, main metrics, checkpoints, and differences from the baseline. Retrieve only the history and artifacts needed for the current question. Comparisons of values can be calculated automatically; research benefits and decisions are determined in conversation.

Discuss the following, reusing answers that are already known: What are the main results? What does the user think they show? Which findings are worth keeping? What has been decided for the next step? Show the necessary numbers and plots to support the discussion. If no judgment of success or failure was requested, keep the report to concrete results.

State “the historical best value for each metric” separately from “a group of metrics at the same checkpoint.” The comparison subject, evaluation set, and step in a summary should be traceable.

## Markdown as the main analysis record

Use one note per research topic, which can link to multiple runs; default to `notes/<study>.md`. Common sections cover the question and main changes, related runs, main results, key findings, next decisions, and important artifacts. Keep only sections with actual content.

Retain the key numbers needed to understand the main results; put loss histories, full parameters, and all paths in MLflow or the experiment map. Link each important finding to its relevant run, plot, or artifact. Make clear which statements are observed facts and which are interpretations already discussed. Do not automatically add confidence levels, experiment success/failure labels, or fixed disclaimers.

When the user says “record this,” write the latest content they clearly referred to. If they only ask “what do you think?”, continue the analysis without recording a candidate interpretation as a confirmed finding. If the user explicitly asks to record a hypothesis, save it as a “Hypothesis.”

After multiple experiments, maintain “Current understanding” and keep a brief dated change log. When a conclusion changes, update current understanding and identify the corresponding new evidence. Record dates in the user's current time zone and include the explicit time zone.

## Sync to MLflow

The local topic Markdown is the main analysis record. MLflow stores the summary and attachments for this publication. Use `MlflowClient` with an explicit existing run ID; do not use `start_run` to add analysis, as that could change the run's status or end time.

1. Save the local Markdown and select the summary confirmed for this publication.
2. Use `mlflow.note.content` to update the log-management section in the description, preserving its other existing content.
3. Upload the full Markdown as `analysis/<study>/<revision>.md`. Use a stable revision identifier, such as a timestamp plus content hash; reuse the identifier when publishing the same version again.
4. Record the analysis version and artifact path in custom tags; keep the run association in the topic note and experiment map.

Publish the figures, comparison tables, and map snapshots supporting a finding under the same immutable analysis revision, with a manifest or links resolving to those exact attachments. A versioned note pointing only to overwritten plots does not preserve its evidence. Keep current navigation links separate from historical publication files; preserve prior revisions when adding runs or revising findings, and reuse an existing revision only when its note and supporting evidence are unchanged.

Validate links from the published bundle location, including links inside copied HTML and supporting Markdown, not only those in the main note. Preserve the required directory structure or remap links and include their dependencies; keep links to external training assets explicit.

You may use `<!-- experiment-journal:start -->` and `<!-- experiment-journal:end -->` to mark the managed description section. If an existing description has no markers, append the section; afterward, update only that section.

For a multi-run analysis, write an applicable summary and the same versioned attachment to each related run. Log newly calculated evaluation metrics as metrics according to their definitions; do not put analysis text in params. If only one of the two locations saves successfully, state where it was saved and what remains to sync, then continue that version next time.

## Experiment map and next steps

Update objective information such as run status, code snapshots, and artifact locations. Add only findings summaries and decisions the user has confirmed to the map. Record future ideas as suggestions or plans, distinct from branches already executed. Before reviewing the next round of experiments, first read current understanding and the relevant experiment-map nodes.
