#!/usr/bin/env python
"""Validate the hand-written clustering algorithms against scikit-learn.

This script is a development-time correctness and initialization-quality check.
The production analysis continues to run analysis/13_community_groups.py without
importing sklearn.
"""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np

try:
    import sklearn
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    from sklearn.metrics import adjusted_rand_score
    from sklearn.metrics import silhouette_score as sklearn_silhouette_score
except ModuleNotFoundError as exc:
    raise SystemExit(
        "scikit-learn is required only for this validation. "
        "Install it with: python -m pip install -r requirements-dev.txt"
    ) from exc


ROOT = Path(__file__).resolve().parents[1]
IMPLEMENTATION_PATH = ROOT / "analysis" / "13_community_groups.py"
REPORT_PATH = ROOT / "output" / "clustering_validation.txt"

ARI_TOLERANCE = 0.95
SILHOUETTE_TOLERANCE = 1e-6
PCA_VARIANCE_TOLERANCE = 1e-6
PCA_LOADING_TOLERANCE = 1e-6
PCA_PROJECTION_TOLERANCE = 1e-6
KMEANS_PLUS_PLUS_SEEDS = tuple(range(10))


def load_implementation() -> ModuleType:
    spec = importlib.util.spec_from_file_location("community_groups", IMPLEMENTATION_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {IMPLEMENTATION_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inertia(points: np.ndarray, labels: np.ndarray, centers: np.ndarray) -> float:
    residuals = points - centers[labels]
    return float(np.sum(residuals * residuals))


def status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def inertia_position(hand_inertia: float, sampled_inertias: list[float]) -> str:
    if hand_inertia <= min(sampled_inertias):
        return "at/below min (excellent)"
    if hand_inertia <= max(sampled_inertias):
        return "inside range (fine)"
    return "above max (suboptimal)"


def recover_hand_pca_details(
    points: np.ndarray, hand_projection: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Recover full-precision PCA details from pca()'s unrounded scores.

    The production function rounds displayed loadings and variance ratios, but
    its projected coordinates retain the full-precision component vectors.
    Solving centered_points @ components.T == scores extracts those same vectors
    without changing or duplicating the production PCA implementation.
    """

    centered_points = points - np.mean(points, axis=0)
    components = np.linalg.lstsq(centered_points, hand_projection, rcond=None)[0].T
    reconstructed_projection = centered_points @ components.T
    if not np.allclose(
        reconstructed_projection, hand_projection, atol=1e-12, rtol=0.0
    ):
        raise RuntimeError("Could not recover hand-written PCA components from its scores")
    total_variance = float(np.var(points, axis=0, ddof=1).sum())
    explained_variance_ratio = (
        np.var(hand_projection, axis=0, ddof=1) / total_variance
    )
    return components, explained_variance_ratio


def build_report() -> tuple[str, bool]:
    if (
        len(KMEANS_PLUS_PLUS_SEEDS) < 10
        or len(set(KMEANS_PLUS_PLUS_SEEDS)) != len(KMEANS_PLUS_PLUS_SEEDS)
    ):
        raise RuntimeError("k-means++ validation requires at least 10 distinct seeds")

    hand = load_implementation()
    data = hand.load_metrics()
    metrics = sorted(data["communities"], key=lambda row: row["community_area"])
    hand.assert_source_counts(metrics)
    communities, raw_matrix, _raw_inputs, _imputes = hand.prepare_matrix(metrics)
    scaled_matrix, _scale_stats = hand.robust_scale(raw_matrix)
    points = np.asarray(scaled_matrix, dtype=float)

    identical_start_rows: list[dict[str, float | int | str]] = []
    hand_results: dict[int, dict[str, Any]] = {}
    overall_ok = True
    for k in range(3, 8):
        hand_labels_list, hand_centers_list = hand.kmeans(scaled_matrix, k)
        hand_labels = np.asarray(hand_labels_list, dtype=int)
        hand_centers = np.asarray(hand_centers_list, dtype=float)
        initial_centers = np.asarray(hand.initial_centroids(scaled_matrix, k), dtype=float)

        reference = KMeans(
            n_clusters=k,
            init=initial_centers,
            n_init=1,
            max_iter=200,
            tol=0.0,
            algorithm="lloyd",
        ).fit(points)

        ari = float(adjusted_rand_score(hand_labels, reference.labels_))
        hand_inertia = inertia(points, hand_labels, hand_centers)
        sklearn_inertia = float(reference.inertia_)
        inertia_ratio = hand_inertia / sklearn_inertia if sklearn_inertia else math.inf
        hand_silhouette = float(hand.silhouette_score(scaled_matrix, hand_labels_list))
        sklearn_silhouette = float(sklearn_silhouette_score(points, hand_labels))
        silhouette_delta = abs(hand_silhouette - sklearn_silhouette)
        row_ok = ari >= ARI_TOLERANCE and silhouette_delta <= SILHOUETTE_TOLERANCE
        overall_ok = overall_ok and row_ok
        hand_results[k] = {
            "labels": hand_labels,
            "inertia": hand_inertia,
            "silhouette": hand_silhouette,
        }
        identical_start_rows.append(
            {
                "k": k,
                "ari": ari,
                "hand_inertia": hand_inertia,
                "sklearn_inertia": sklearn_inertia,
                "inertia_ratio": inertia_ratio,
                "hand_silhouette": hand_silhouette,
                "sklearn_silhouette": sklearn_silhouette,
                "silhouette_delta": silhouette_delta,
                "status": status(row_ok),
            }
        )

    initialization_rows: list[dict[str, Any]] = []
    for k in range(3, 8):
        seeded_runs = [
            (
                seed,
                KMeans(
                    n_clusters=k,
                    init="k-means++",
                    n_init=10,
                    random_state=seed,
                ).fit(points),
            )
            for seed in KMEANS_PLUS_PLUS_SEEDS
        ]
        seed_inertias = [float(model.inertia_) for _seed, model in seeded_runs]
        best_seed, best_model = min(seeded_runs, key=lambda item: item[1].inertia_)
        hand_result = hand_results[k]
        initialization_rows.append(
            {
                "k": k,
                "hand_inertia": hand_result["inertia"],
                "min_inertia": min(seed_inertias),
                "median_inertia": float(np.median(seed_inertias)),
                "max_inertia": max(seed_inertias),
                "position": inertia_position(hand_result["inertia"], seed_inertias),
                "best_seed": best_seed,
                "best_ari": float(
                    adjusted_rand_score(hand_result["labels"], best_model.labels_)
                ),
                "hand_silhouette": hand_result["silhouette"],
                "best_silhouette": float(
                    sklearn_silhouette_score(points, best_model.labels_)
                ),
                "seed_inertias": seed_inertias,
            }
        )

    hand_pca = hand.pca(scaled_matrix)
    hand_projection = np.asarray(hand_pca["scores"], dtype=float)
    hand_components, hand_variance = recover_hand_pca_details(
        points, hand_projection
    )

    reference_pca = PCA(n_components=2, svd_solver="full").fit(points)
    sklearn_components = reference_pca.components_
    sklearn_variance = reference_pca.explained_variance_ratio_
    sklearn_projection = reference_pca.transform(points)

    # PCA axes have arbitrary signs. Align each hand-written component to the
    # sklearn reference before comparing loadings or projected coordinates.
    signs = np.where(
        np.sum(hand_components * sklearn_components, axis=1) < 0.0, -1.0, 1.0
    )
    aligned_components = hand_components * signs[:, np.newaxis]
    aligned_projection = hand_projection * signs[np.newaxis, :]

    variance_deltas = np.abs(hand_variance - sklearn_variance)
    loading_deltas = np.max(
        np.abs(aligned_components - sklearn_components), axis=1
    )
    projection_deltas = np.max(
        np.abs(aligned_projection - sklearn_projection), axis=0
    )
    hand_descending = bool(np.all(np.diff(hand_variance) <= 0.0))
    sklearn_descending = bool(np.all(np.diff(sklearn_variance) <= 0.0))
    pca_ok = bool(
        np.all(variance_deltas <= PCA_VARIANCE_TOLERANCE)
        and np.all(loading_deltas <= PCA_LOADING_TOLERANCE)
        and np.all(projection_deltas <= PCA_PROJECTION_TOLERANCE)
        and hand_descending
        and sklearn_descending
    )
    overall_ok = overall_ok and pca_ok

    hand_best_k = max(hand_results, key=lambda k: hand_results[k]["silhouette"])
    kmeans_plus_plus_best = max(
        initialization_rows, key=lambda row: row["best_silhouette"]
    )
    kmeans_plus_plus_best_k = int(kmeans_plus_plus_best["k"])
    chosen_k_row = next(
        row for row in initialization_rows if row["k"] == hand.CHOSEN_K
    )
    chosen_k_changes = kmeans_plus_plus_best_k != hand.CHOSEN_K
    chosen_k_delta = float(
        kmeans_plus_plus_best["best_silhouette"]
        - chosen_k_row["best_silhouette"]
    )
    chosen_k_relative_gain = (
        chosen_k_delta / chosen_k_row["best_silhouette"]
        if chosen_k_row["best_silhouette"]
        else math.inf
    )
    excellent_ks = [
        row["k"]
        for row in initialization_rows
        if row["position"].startswith("at/below")
    ]
    fine_ks = [
        row["k"]
        for row in initialization_rows
        if row["position"].startswith("inside")
    ]
    suboptimal_ks = [
        row["k"]
        for row in initialization_rows
        if row["position"].startswith("above")
    ]
    excellent_k_text = ",".join(str(k) for k in excellent_ks) or "none"
    fine_k_text = ",".join(str(k) for k in fine_ks) or "none"
    suboptimal_k_text = ",".join(str(k) for k in suboptimal_ks) or "none"

    lines = [
        "Chicago School Gap: hand-written clustering validation",
        "=" * 55,
        f"Input: {len(communities)} community areas x {points.shape[1]} features",
        f"Reference: scikit-learn {sklearn.__version__}",
        f"Production cluster count: k={hand.CHOSEN_K}",
        "",
        "1. Identical-start k-means and silhouette correctness",
        "Scope: sklearn receives the hand-written deterministic centroids with n_init=1.",
        "This validates assignment, centroid updates, and convergence from the same start;",
        "ARI=1.0 here does not evaluate whether the hand-written initialization is high quality.",
        "Silhouette comparison: both functions score the identical hand-written labels.",
        "",
        "k  ARI         inertia(hand)  inertia(sk)    ratio       silhouette(hand)  silhouette(sk)    abs delta    result",
        "-  ----------  -------------  -------------  ----------  ----------------  ----------------  -----------  ------",
    ]
    for row in identical_start_rows:
        lines.append(
            f"{row['k']}  {row['ari']:<10.8f}  {row['hand_inertia']:<13.8f}  "
            f"{row['sklearn_inertia']:<13.8f}  {row['inertia_ratio']:<10.8f}  "
            f"{row['hand_silhouette']:<16.10f}  "
            f"{row['sklearn_silhouette']:<16.10f}  "
            f"{row['silhouette_delta']:<11.3e}  {row['status']}"
        )

    lines.extend(
        [
            "",
            "2. Initialization quality: hand-written vs sklearn k-means++",
            f"Seeds: {','.join(str(seed) for seed in KMEANS_PLUS_PLUS_SEEDS)}; each sklearn run uses n_init=10.",
            "ARI compares hand-written labels with the lowest-inertia k-means++ partition and is descriptive only.",
            "",
            "k  inertia(hand)  k++ min        k++ median     k++ max        hand position              best seed  ARI(best)  silhouette(hand)  silhouette(best)",
            "-  -------------  -------------  -------------  -------------  -------------------------  ---------  ---------  ----------------  ----------------",
        ]
    )
    for row in initialization_rows:
        lines.append(
            f"{row['k']}  {row['hand_inertia']:<13.8f}  {row['min_inertia']:<13.8f}  "
            f"{row['median_inertia']:<13.8f}  {row['max_inertia']:<13.8f}  "
            f"{row['position']:<25}  {row['best_seed']:<9}  "
            f"{row['best_ari']:<9.6f}  {row['hand_silhouette']:<16.10f}  "
            f"{row['best_silhouette']:.10f}"
        )
    lines.extend(
        [
            "",
            "Per-seed inertia (seed:value; each value is the best of 10 k-means++ starts):",
        ]
    )
    for row in initialization_rows:
        seed_values = ", ".join(
            f"{seed}:{seed_inertia:.8f}"
            for seed, seed_inertia in zip(
                KMEANS_PLUS_PLUS_SEEDS, row["seed_inertias"]
            )
        )
        lines.append(f"k={row['k']}: {seed_values}")
    lines.extend(
        [
            "",
            "Interpretation:",
            "- Hand inertia <= the minimum across all seeds: deterministic initialization is excellent.",
            "- Hand inertia inside the sampled distribution: initialization is fine; no action needed.",
            "- Hand inertia worse than every seed: initialization leaves quality on the table and published assignments are suboptimal.",
            "",
            f"Silhouette-selected k (hand-written path): {hand_best_k}",
            f"Silhouette-selected k (best-inertia k-means++ partitions): {kmeans_plus_plus_best_k}",
            (
                f"CHOSEN_K WOULD CHANGE: YES, from {hand.CHOSEN_K} to "
                f"{kmeans_plus_plus_best_k}; the k-means++ silhouette gain over "
                f"k={hand.CHOSEN_K} is {chosen_k_delta:.10f} "
                f"({chosen_k_relative_gain:.2%} relative)."
                if chosen_k_changes
                else f"CHOSEN_K WOULD CHANGE: NO; both paths select k={hand.CHOSEN_K}."
            ),
            "",
            f"Initialization summary: excellent at k={excellent_k_text}; "
            f"fine at k={fine_k_text}; suboptimal versus every sampled seed "
            f"at k={suboptimal_k_text}.",
            (
                f"Published-k finding: at k={hand.CHOSEN_K}, hand inertia "
                f"{chosen_k_row['hand_inertia']:.8f} is {chosen_k_row['position']} versus "
                f"the k-means++ range {chosen_k_row['min_inertia']:.8f} to "
                f"{chosen_k_row['max_inertia']:.8f}."
            ),
            (
                f"Selection finding: k={kmeans_plus_plus_best_k} has k-means++ inertia "
                f"{kmeans_plus_plus_best['min_inertia']:.8f} and silhouette "
                f"{kmeans_plus_plus_best['best_silhouette']:.10f}, so applying the "
                "same maximum-silhouette rule to the best-inertia k-means++ partitions "
                f"would publish k={kmeans_plus_plus_best_k}, not k={hand.CHOSEN_K}."
                if chosen_k_changes
                else "Selection finding: the k-means++ quality comparison supports the published CHOSEN_K."
            ),
            "",
            "3. PCA (hand-written signs aligned to scikit-learn by component dot product)",
            "component  variance(hand)  variance(sk)    abs delta    max loading delta  max projection delta",
            "---------  --------------  --------------  -----------  -----------------  --------------------",
        ]
    )
    for component_index in range(2):
        lines.append(
            f"PC{component_index + 1:<8}  "
            f"{hand_variance[component_index]:<14.10f}  "
            f"{sklearn_variance[component_index]:<14.10f}  "
            f"{variance_deltas[component_index]:<11.3e}  "
            f"{loading_deltas[component_index]:<17.3e}  "
            f"{projection_deltas[component_index]:.3e}"
        )
    lines.extend(
        [
            "",
            f"Explained variance descending (hand/sklearn): {hand_descending}/{sklearn_descending}",
            f"PCA result: {status(pca_ok)}",
            "",
            "Thresholds: ARI >= 0.95; silhouette abs delta <= 1e-6; "
            "PCA variance/loading/projection max abs delta <= 1e-6.",
            "Inertia ratio is hand-written / sklearn; values near 1 indicate the same local optimum.",
            "The k-means++ ARI and inertia-quality findings do not alter the correctness thresholds.",
            f"OVERALL CORRECTNESS: {status(overall_ok)}",
            (
                "INITIALIZATION/SELECTION FINDING: REVIEW - CHOSEN_K changes under "
                "the best-inertia k-means++ silhouette comparison."
                if chosen_k_changes
                else "INITIALIZATION/SELECTION FINDING: no CHOSEN_K change."
            ),
        ]
    )
    return "\n".join(lines) + "\n", overall_ok


def main() -> None:
    report, ok = build_report()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(report, end="")
    print(f"Wrote {REPORT_PATH.relative_to(ROOT)}")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
