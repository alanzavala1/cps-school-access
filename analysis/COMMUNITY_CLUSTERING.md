# Community clustering

[Back to README](../README.md) · [Metrics and interpretation](FINDINGS.md)

The map groups 77 community areas using four school and access measures. The
groups are descriptive categories, not school-effectiveness estimates, official
CPS classifications, or admission probabilities.

## Inputs and preprocessing

[`12_community_metrics.sql`](12_community_metrics.sql) aggregates tract and
school measures to `output/community_metrics.json`.
[`13_community_groups.py`](13_community_groups.py) requires that SQL export;
there is no fallback to frontend GeoJSON.

| Model input | Definition |
| --- | --- |
| `assigned_default_index` | Median tract `default_index`: weakness across six assigned-school outcomes |
| `local_school_index` | Mean available-component weakness of high schools physically inside the area, normalized across all high schools |
| `selective_access_index` | Median tract `access_index`: nearest-selective SAT and straight-line distance to a SAT ≥1250 selective |
| `local_supply_gap` | `1 - min(local_hs_count, 4) / 4`; counts saturate at four schools |

All four inputs are oriented so larger values mean more concern. Missing input
values are filled with the citywide median for that feature and flagged in the
output. Features are centered on their median and divided by their interquartile
range; a zero interquartile range falls back to the larger of the full range and 1.

Race, income, poverty, and routed travel times are not inputs. Distance to a
school with SAT ≥1010 is available as context but does not enter the model.
Local school count measures geographic supply, not seats or eligibility.

## Grouping and outputs

The implementation uses deterministic farthest-point initialization and Lloyd
k-means for k=3 through k=7. Among those deterministic runs, k=5 has the highest
silhouette score. The public map uses the fixed `CHOSEN_K = 5`; it does not
automatically select a new k on each rebuild. Two PCA coordinates summarize the
scaled inputs for diagnostics; k-means uses all four features.

Labels, colors, and descriptions come from
[`community_group_labels.json`](community_group_labels.json). Review that file
alongside diagnostic group profiles when refreshing inputs: fixed labels do not
guarantee that a changed dataset gives each group the same interpretation.

| Output | Purpose |
| --- | --- |
| `output/community_groups.json` | Assignments, labels, drivers, PCA coordinates, and input flags; also written to `frontend/public/data/` |
| `output/community_groups_diagnostics.json` | Scaling, imputations, per-k scores, group profiles, and PCA details |
| `output/community_groups_selective_sensitivity.json` | Comparison after excluding selective schools from local quality and supply |

## Validation

Run [`validate_clustering.py`](validate_clustering.py) with `requirements-dev.txt`
installed; [commands are in the README](../README.md#rebuild-and-validate-the-analysis).
It writes [`output/clustering_validation.txt`](../output/clustering_validation.txt)
without changing published group data. The check is separate from `run_all.sh`.

The committed report, using scikit-learn 1.9.0, finds identical k-means assignments
and inertia at k=3–7 when sklearn receives the same starting centroids.
Silhouette scores agree within floating-point precision; PCA variance ratios,
loadings, and projections agree within the check's 1e-6 tolerance after signs
are aligned. The correctness exit status does not test initialization quality.

Across ten seeds with ten k-means++ starts each, deterministic initialization
matches the best inertia found at k=4, lies within the sampled range at k=5,
and has worse inertia than every sampled run at k=3, 6, and 7. Comparing the
best-inertia k-means++ partitions would select k=6 by silhouette: **0.293**, versus
**0.281** for that comparison's k=5. This is the report's 4.2% relative gain.
The published deterministic k=5 partition has silhouette **0.268**. These are
different comparisons; identical-start correctness does not establish an
optimal partition or cluster count.

## Sensitivity and limits

The selective-school sensitivity check substitutes
`local_nonselective_school_index` and `local_nonselective_hs_count`, retaining
the selective-access input and k=5. In the committed result, **42 of 77 areas**
change group. Local nonselective quality requires median imputation for 16 areas.
This shows that whether local selective schools count as local supply materially
affects the classification; presence inside an area does not guarantee admission.

Assigned-school and access indices use straight-line distances, while the panel
also shows routed minutes. Community aggregation hides differences within an
area. Missing-value imputation, capped school counts, normalization, and fixed
labels all affect the groups. Interpret the colors with the underlying panel
metrics and the [coverage limits](FINDINGS.md#coverage-and-limits).
