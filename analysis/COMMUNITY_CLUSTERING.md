# Community Area Clustering

This map layer groups Chicago community areas by school/access patterns. It is descriptive only.

## What the model uses

The clustering uses four community-area inputs, all oriented so higher means more concern:

- assigned default weakness: median tract `default_index`
- local school weakness: mean weakness index for high schools physically located in the community area
- selective access weakness: median tract `access_index`
- local school supply gap: fewer CPS high schools located in the area

Race, income, and poverty are not clustering inputs. They stay in the panel as context.
Distance to the nearest strong high school remains a panel metric, but it is not a clustering input because the SAT >= 1010 threshold is mostly selective-enrollment schools in the current data.

## Method

`analysis/12_community_metrics.sql` builds one row per community area in PostGIS and exports `output/community_metrics.json`.
`analysis/13_community_groups.py` requires that SQL-exported file. There is intentionally no GeoJSON fallback. It robust-scales the four model inputs, runs deterministic KMeans for k=3 through k=7, saves PCA coordinates for explanation, and writes:

- `output/community_groups.json`
- `output/community_groups_diagnostics.json`
- `output/community_groups_selective_sensitivity.json`
- `frontend/public/data/community_groups.json`

The public map uses k=5. Along the deterministic path this script runs, k=5 has the strongest silhouette score among k=3 through k=7 while keeping the groups interpretable and avoiding tiny singleton groups. That comparison depends on the initialization — see Validation below.

Public labels are locked in `analysis/community_group_labels.json`; they are not generated silently from each rebuild.

## Validation

`analysis/validate_clustering.py` checks the hand-written k-means, silhouette, and PCA against scikit-learn. It is a development-only check: it needs `requirements-dev.txt`, it never runs in the production pipeline, and it does not rewrite any published output. The current report is `output/clustering_validation.txt`.

What it confirms:

- **k-means, from the same starting centroids**: sklearn's Lloyd algorithm seeded with the hand-written initial centroids returns identical assignments (ARI = 1.000) and identical inertia at every k from 3 to 7.
- **Silhouette**: hand-written and sklearn scores of the same labels agree to ~1e-16.
- **PCA**: explained-variance ratios, loadings, and projected coordinates match sklearn to ~1e-10 once component signs are aligned.

What it flags:

- The initialization is deterministic farthest-point, not k-means++. Against the best of 10 sklearn k-means++ runs over 10 seeds, it reaches the best inertia found at k=4, lands inside the sampled range at k=5 (the published k), and is worse than every sampled seed at k=3, 6, and 7.
- So the silhouette comparison across k is not initialization-neutral. Applying the same maximum-silhouette rule to the best-inertia k-means++ partitions would select **k=6** (silhouette 0.293) over **k=5** (0.268) — a 4.2% relative difference.

The published map still uses k=5. These groups are descriptive, the k=5 labels are hand-reviewed and locked in `analysis/community_group_labels.json`, and the gap is small. Moving to k=6, or to a k-means++ initialization, would be a deliberate re-publish with new labels and a rebuilt frontend data file — not a silent change.

## Limits

These groups are not causal claims, admission odds, school effectiveness estimates, or official CPS categories. Distances are straight-line distances unless a future routing pipeline replaces them.
