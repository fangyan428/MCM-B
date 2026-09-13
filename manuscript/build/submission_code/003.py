"""Read-only reconstruction of Q3 manuscript evidence; no simulator is started.

Run from the repository root: python manuscript/analysis/q3_verify.py
Only manuscript/analysis/q3_* files are written. Official records are read via
SQLite mode=ro; encrypted logs are inspected only for their public envelopes.
"""
from __future__ import annotations
import csv
import hashlib
import json
import math
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "manuscript/analysis"
INNOV = ROOT / "question3/innovation"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_csv(name, rows):
    with (OUT / name).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def block_bootstrap(rows, selected, fixtures):
    by = {v: {r["case_id"]: r for r in rows if r["variant"] == v}
          for v in ("BASE", selected)}
    ids_by_seed = {}
    for f in fixtures:
        ids_by_seed.setdefault(str(f["seed"]), []).append(f["id"])
    seeds = sorted(ids_by_seed)
    family = {str(f["seed"]): f["family"] for f in fixtures}
    assert len(seeds) == 120 and all(len(x) == 4 for x in ids_by_seed.values())
    data = {v: np.array([[by[v][k]["penalized_virtual_s"]
                         for k in sorted(ids_by_seed[s])] for s in seeds]) for v in by}
    rng = np.random.default_rng(20260912)
    indices = []
    for f in sorted(set(family.values())):
        ids = np.array([i for i, s in enumerate(seeds) if family[s] == f])
        assert len(ids) == 20
        indices.append(rng.choice(ids, size=(20000, len(ids)), replace=True))
    idx = np.concatenate(indices, axis=1)
    means = {v: x.mean(axis=1)[idx].mean(axis=1) for v, x in data.items()}
    change = 100 * (means[selected] / means["BASE"] - 1)
    p95 = {v: np.percentile(x[idx].reshape(20000, -1), 95, axis=1)
           for v, x in data.items()}
    return {"layouts": len(seeds), "resamples": 20000,
            "mean_change_pct_ci95": np.percentile(change, [2.5, 97.5]).tolist(),
            "p95_change_seconds_ci95": np.percentile(p95[selected] - p95["BASE"], [2.5, 97.5]).tolist()}


def main():
    evidence = read(INNOV / "FINAL_EVIDENCE.json")
    lock = read(INNOV / "validation_lock.json")
    generation = read(INNOV / "validation_generation.json")
    selected = lock["selected"]
    assert selected == evidence["selected"] == "GATED_TOUR_MULTI_PARALLAX"
    assert read(INNOV / "best_candidate.json") == lock["configs"][selected]
    assert generation["after_lock_sha256"] == sha(INNOV / "validation_lock.json")
    assert generation["fixtures_sha256"] == sha(INNOV / "final_validation_cases.json")
    assert datetime.fromisoformat(lock["created_utc"]) < datetime.fromisoformat(generation["generated_utc"])
    for p, h in lock["code_sha256"].items():
        assert sha(INNOV / p) == h, p
    manifest = read(INNOV / "EXPORT_MANIFEST.json")
    for p, entry in manifest["files"].items():
        assert sha(INNOV / p) == entry["sha256"], p
    fixtures = read(INNOV / "final_validation_cases.json")
    dev = read(INNOV / "structured_development.json")
    assert {f["seed"] for f in fixtures}.isdisjoint(f["seed"] for f in dev)
    final, costs, families, pair_rows = [], [], [], []
    verification = {"selected": selected, "source_lock_verified": True,
                    "export_files_verified": len(manifest["files"]),
                    "selection_before_final_generation": True,
                    "final_layouts": len({f["seed"] for f in fixtures}),
                    "final_case_error_pairs_per_rounding": len(fixtures), "bootstrap": {}}
    for rounding in ("bounded", "pre_round_stress"):
        folder = INNOV / "final_validation" / rounding
        rows = read(folder / "summary.json")["rows"]
        assert len(rows) == 3840
        configs = read(folder / "configs.json")
        assert all(config == lock["configs"][name] for name, config in configs.items())
        by = {v: {r["case_id"]: r for r in rows if r["variant"] == v}
              for v in configs}
        assert all(set(x) == {f["id"] for f in fixtures} for x in by.values())
        for variant, runs in by.items():
            times = np.array([r["penalized_virtual_s"] for r in runs.values()])
            raw = np.array([r["metrics"]["virtual_time_s"] for r in runs.values()])
            assert all(r["success"] and r["status"] == "complete" and
                       r["total"] == r["cleared"] and r["audit"] == "pass" and
                       not r["timeout"] and not r["false_complete"] for r in runs.values())
            assert np.array_equal(times, raw)
            source = evidence["final"][rounding]["aggregates"][variant]
            stats = {"mean": float(times.mean()), "p95": float(np.percentile(times, 95)),
                     "maximum": float(times.max()),
                     "mean_per_cleared": float(np.mean([r["metrics"]["virtual_time_s"] / r["cleared"] for r in runs.values()]))}
            for key, val in stats.items():
                assert math.isclose(val, source[key], abs_tol=1e-8), (rounding, variant, key)
            final.append({"rounding": rounding, "variant": variant, "runs": len(runs), "complete": len(runs), **stats})
            if variant in ("BASE", selected):
                for component in ("movement_s", "switch_s", "detection_s", "optical_s", "laser_s"):
                    value = float(np.mean([r["metrics"]["components"][component] for r in runs.values()]))
                    assert math.isclose(value, source["movement_detection_etc"][component], abs_tol=1e-8)
                    costs.append({"rounding": rounding, "variant": variant, "component": component, "mean_s": value})
                for f in sorted({f["family"] for f in fixtures}):
                    ids = {x["id"] for x in fixtures if x["family"] == f}
                    values = [runs[k]["penalized_virtual_s"] for k in sorted(ids)]
                    families.append({"rounding": rounding, "variant": variant, "family": f,
                                     "layouts": 20, "runs": len(values), "mean_s": float(np.mean(values)),
                                     "p95_s": float(np.percentile(values, 95))})
        for case_id, b in by["BASE"].items():
            c = by[selected][case_id]
            pair_rows.append({"rounding": rounding, "case_id": case_id,
                              "baseline_s": b["penalized_virtual_s"], "candidate_s": c["penalized_virtual_s"],
                              "change_s": c["penalized_virtual_s"] - b["penalized_virtual_s"],
                              "change_pct": 100 * (c["penalized_virtual_s"] / b["penalized_virtual_s"] - 1)})
        boot = block_bootstrap(rows, selected, fixtures)
        for key, val in boot.items():
            assert np.allclose(val, evidence["final"][rounding]["bootstrap"][key], atol=1e-10)
        verification["bootstrap"][rounding] = boot
    save_csv("q3_final_statistics.csv", final)
    save_csv("q3_cost_components.csv", costs)
    save_csv("q3_family_statistics.csv", families)
    save_csv("q3_final_pairs.csv", pair_rows)
    rounds = []
    for name, item in evidence["rounds"].items():
        for rounding, batch in item["batches"].items():
            rounds.append({"round": name, "candidate": item["variant"], "parent": item["parent"],
                           "rounding": rounding, "stage": "development",
                           "baseline_mean_s": batch["baseline"]["mean"],
                           "candidate_mean_s": batch["candidate"]["mean"],
                           "vs_baseline_pct": batch["candidate"]["mean_change_pct"],
                           "vs_parent_pct": batch["direct_parent_mean_change_pct"]})
    save_csv("q3_mechanism_development.csv", rounds)
    # Read official practice summaries without exporting team identity or tickets.
    official = ROOT / "JammersSimulatorData"
    snapshot = read(OUT / 'q3_official_snapshot.json')
    if (official / 'practice-statistics-queue.sqlite3').exists():
        conn = sqlite3.connect(f"file:{official / 'practice-statistics-queue.sqlite3'}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        records = [dict(r) for r in conn.execute("SELECT practice_run_no,case_code,problem_no,entered,end_reason,cleared_jammer_count,jammer_count,virtual_time_us,measure_accepted_count,channel_switch_count,clear_failure_count,state,created_at_ms FROM practice_statistics_tasks ORDER BY created_at_ms")]
        conn.close()
    else:
        records = snapshot['records']
    official_rows = []
    for r in records:
        base = official / "behavior-logs" / f"practice-p{r['problem_no']}-{r['practice_run_no']}-{r['case_code']}"
        result_path = base.with_suffix(".result.json")
        result = read(result_path)
        assert result["practice_run_no"] == r["practice_run_no"] and result["jammer_count"] == r["jammer_count"]
        log_path = base.with_suffix(".jlog")
        log_hash = sha(log_path) if log_path.exists() else snapshot["log_projection"][log_path.name]["sha256"]
        assert result["package_sha256"] == log_hash
        for ext, kind in ((".jlog", "practice_behavior_log"), (".psum", "practice_summary")):
            log_path = base.with_suffix(ext)
            if log_path.exists():
                data = log_path.read_bytes()
                n = int.from_bytes(data[10:14], "big")
                header = json.loads(data[14:14+n])
            else:
                header = snapshot["log_projection"][log_path.name]["public_header"]
            assert header["package_type"] == kind and header["problem_no"] == 3
            assert header["formal_index"] is None and header["practice_run_no"] == r["practice_run_no"]
            assert header["case_code"] == r["case_code"]
        official_rows.append({"case_code": r["case_code"], "problem_no": r["problem_no"],
                              "started_utc": result["window_started_at_utc"], "ended_utc": result["ended_at_utc"],
                              "entered": r["entered"], "end_reason": r["end_reason"],
                              "cleared": r["cleared_jammer_count"], "total": r["jammer_count"],
                              "virtual_time_s": r["virtual_time_us"] / 1e6,
                              "mean_per_cleared_s": r["virtual_time_us"] / 1e6 / r["cleared_jammer_count"],
                              "measures": r["measure_accepted_count"], "switches": r["channel_switch_count"],
                              "failed_clears": r["clear_failure_count"], "local_queue_state": r["state"],
                              "algorithm_configuration": "unresolved",
                              "result_sha256": sha(result_path), "jlog_sha256": result["package_sha256"]})
    save_csv("q3_official_practice.csv", official_rows)
    if (official / 'formal-statistics-queue.sqlite3').exists():
        conn = sqlite3.connect(f"file:{official / 'formal-statistics-queue.sqlite3'}?mode=ro", uri=True)
        formal_count = conn.execute("SELECT COUNT(*) FROM statistics_tasks").fetchone()[0]
        conn.close()
        conn = sqlite3.connect(f"file:{official / 'upload-queue.sqlite3'}?mode=ro", uri=True)
        upload_count = conn.execute("SELECT COUNT(*) FROM upload_tasks").fetchone()[0]
        conn.close()
    else:
        formal_count = snapshot['formal_local_rows']
        upload_count = snapshot['upload_local_rows']
    values = np.array([r["virtual_time_s"] for r in official_rows])
    practice_summary = {"runs": len(official_rows), "unique_case_codes": len({r["case_code"] for r in official_rows}),
                        "complete_by_official_counts": sum(r["entered"] == 1 and r["cleared"] == r["total"] for r in official_rows),
                        "queue_states": dict(Counter(r["local_queue_state"] for r in official_rows)),
                        "end_reasons": dict(Counter(r["end_reason"] for r in official_rows)),
                        "mean_s": float(values.mean()), "p95_s": float(np.percentile(values, 95)),
                        "minimum_s": float(values.min()), "maximum_s": float(values.max()),
                        "total_cleared": sum(r["cleared"] for r in official_rows),
                        "mean_per_cleared_s": float(np.mean([r["mean_per_cleared_s"] for r in official_rows])),
                        "formal_local_rows": formal_count, "upload_local_rows": upload_count,
                        "algorithm_attribution": "not established; encrypted logs do not expose algorithm configuration",
                        "scope": "local official-simulator records; no live backend or formal score verification"}
    practice_summary["source_mode"] = "original_local_records" if (official / "practice-statistics-queue.sqlite3").exists() else "anonymous_snapshot_with_original_hashes"
    verification["official_practice"] = practice_summary
    verification["environment"] = {"numpy": np.__version__}
    verification["input_sha256"] = {str(p.relative_to(ROOT)): sha(p) for p in
                                     [INNOV / "FINAL_EVIDENCE.json", INNOV / "validation_lock.json",
                                      INNOV / "final_validation/bounded/summary.json",
                                      INNOV / "final_validation/pre_round_stress/summary.json"]}
    (OUT / "q3_verification.json").write_text(json.dumps(verification, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(verification, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
