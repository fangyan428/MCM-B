"""Reproduce the manuscript's Q1/Q2 geometric claims without changing source data.

Run from the project root: python manuscript/analysis/q12_verify.py
All design scenarios are constructed examples, not official simulator trials.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def import_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


q1 = import_file("q12_first", ROOT / "question1/solve.py")
q2 = import_file("q12_second", ROOT / "question2/strategy.py")


def grid(error_deg, nr=301, na=11, ne=11):
    delta = np.deg2rad(error_deg)
    r, a, e = np.meshgrid(
        np.linspace(5.001, 1500, nr),
        np.linspace(-delta, delta, na),
        np.linspace(-delta, delta, ne),
        indexing="ij",
    )
    return np.column_stack(((r * np.cos(a)).ravel(), (r * np.sin(a)).ravel())), e.ravel()


def certificate(q, error_deg):
    a, b = q
    delta = np.deg2rad(error_deg)
    norm2 = a * a + b * b
    h = a * np.cos(delta) - abs(b) * np.sin(delta)
    cross_lower = abs(b) * np.cos(delta) - a * np.sin(delta)
    max_distance = np.sqrt(max(norm2 + 25 - 10 * h, norm2 + 1500**2 - 3000 * h))
    return {
        "near_endpoint_reception_margin_m2": float(1000**2 - (norm2 + 25 - 10 * h)),
        "range_1000_reception_margin_m2": float(2000 * h - norm2),
        "distance_lower_m": float(cross_lower),
        "distance_upper_m": float(max_distance),
        "acute_intersection_angle_lower_deg": float(np.rad2deg(np.arcsin(cross_lower / max_distance))),
    }


def main():
    source_paths = [
        "question1/solve.py", "question1/test_solve.py", "question1/example_result.json",
        "question1/第一问_建模与求解.md", "question2/strategy.py", "question2/test_strategy.py",
        "question2/results.json", "question2/round1_tradeoff.json", "question2/第二问_建模与求解.md",
        "question2/第二问_复核补充.md", "question2/第二问_第一轮权衡分析.md", "B题/B题.pdf",
        "B题/附件/附件1.docx", "B题/附件/附件2.docx",
    ]
    report = {
        "scope": "Q1 analytical geometry and Q2 constructed design scenarios; not official trials",
        "source_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in source_paths},
        "unit_tests": [],
    }
    for directory in ("question1", "question2"):
        run = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", directory, "-v"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        report["unit_tests"].append({"directory": directory, "exit_code": run.returncode,
                                     "output": run.stdout + run.stderr})
    triangle = q1.solve(q1.triangle_measurements())
    expected = json.loads((ROOT / "question1/example_result.json").read_text())["result"]
    assert abs(triangle["diameter"] - expected["diameter"]) < 1e-9
    assert triangle["diameter_circle_covers"] is False
    report["q1_triangle"] = triangle
    report["q1_triangle"]["minimum_enclosing_diameter_m"] = float(40 / np.sqrt(3))

    original = json.loads((ROOT / "question2/results.json").read_text())
    best, count = q2.search()
    assert count == original["candidates_evaluated"]
    assert np.allclose(best[2:], original["recommendation"], rtol=0, atol=1e-9)
    assert abs(best[0] - original["sampled_search_worst"]) < 1e-9
    report["q2_legacy_search_1deg"] = {"best": list(best), "candidates_evaluated": count}

    fixed = json.loads((ROOT / "question2/round1_tradeoff.json").read_text())
    source, second_error = grid(1.005)
    radius = np.linalg.norm(source, axis=1)
    rows = []
    max_discrepancy = 0.0
    cross_checks = 0
    sparse_source, sparse_error = grid(1.005, 3, 3, 3)
    for old in fixed["rows"]:
        q = np.asarray(old["offset"], dtype=float)
        assert q2.candidate(q, error_deg=1.005)
        assert q2.candidate(q * [1, -1], error_deg=1.005)
        diameter = q2.diameters(q, source, second_error, error_deg=1.005)
        worst = int(diameter.argmax())
        discrepancy = abs(float(diameter[worst]) - old["dense_sample_worst_D"])
        assert discrepancy < 1e-8
        distance = np.linalg.norm(source - q, axis=1)
        sine = np.abs(source[:, 0] * q[1] - source[:, 1] * q[0]) / (radius * distance)
        assert np.all(distance <= np.maximum(1000, radius) + 1e-8)
        assert np.all(distance > 5)
        assert np.all(sine >= np.sin(np.deg2rad(20)) - 1e-12)
        rows.append({**old, "recomputed_worst_D_m": float(diameter[worst]),
                     "worst_source_m": source[worst].tolist(),
                     "worst_second_error_deg": float(np.rad2deg(second_error[worst])),
                     "certificate": certificate(q, 1.005)})
        for mirror in (1, -1):
            candidate = q * [1, mirror]
            expected_d = q2.diameters(candidate, sparse_source, sparse_error, error_deg=1.005)
            for i in range(0, len(sparse_source), 3):
                angle = np.rad2deg(np.arctan2(*(sparse_source[i] - candidate)[::-1]) + sparse_error[i])
                general = q1.solve([
                    {"x": 0, "y": 0, "bearing_deg": 0},
                    {"x": float(candidate[0]), "y": float(candidate[1]), "bearing_deg": float(angle)},
                ], error_deg=1.005)
                assert general["status"] == "bounded"
                difference = abs(general["diameter"] - expected_d[i])
                assert difference < 1e-6
                max_discrepancy = max(max_discrepancy, difference)
                cross_checks += 1
    # Recompute the finite-library dominance relation from the two reported metrics.
    for row in rows:
        dominated = any(
            other["move_m"] <= row["move_m"] + 1e-9
            and other["recomputed_worst_D_m"] <= row["recomputed_worst_D_m"] + 1e-9
            and (other["move_m"] < row["move_m"] - 1e-9
                 or other["recomputed_worst_D_m"] < row["recomputed_worst_D_m"] - 1e-9)
            for other in rows
        )
        assert row["pareto_within_fixed_library"] == (not dominated)
    report["q2_fixed_library_1_005deg"] = {
        "dense_samples_per_candidate": len(source), "rows": rows,
        "general_solver_cross_checks": cross_checks,
        "largest_general_solver_difference_m": max_discrepancy,
        "continuous_worst_case_certified": False,
        "continuous_global_optimum_certified": False,
    }
    report["status"] = "PASS"
    output = Path(__file__).with_name("q12_verification.json")
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "output": str(output),
                      "dense_samples_per_candidate": len(source),
                      "general_solver_cross_checks": cross_checks,
                      "largest_general_solver_difference_m": max_discrepancy}, ensure_ascii=False))


if __name__ == "__main__":
    main()
