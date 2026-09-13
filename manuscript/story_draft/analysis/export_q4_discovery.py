#!/usr/bin/env python3
"""Recover Q4 station-discovery curves with the frozen historical SELF code.

No HTTP transport, official testing, plotting, or new independent validation.
Raw action logs live only in worker memory; only derived plot data are exported.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import types

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "manuscript/story_draft/plot_data/20260913_process"
BATCHES = ("round9_main", "round9_rounding")
ARMS = {"BASE": "baseline31", "FINAL": "recommended25"}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_csv(path, rows):
    assert rows
    with Path(path).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def assert_metrics(actual, expected, context):
    """Require integer microsecond clocks/counts exactly; tolerate float sums."""
    assert actual["virtual_time_s"] == expected["virtual_time_s"], context
    assert actual["counts"] == expected["counts"], context
    for group in ("components", "phases"):
        assert actual[group].keys() == expected[group].keys(), context
        for key, value in actual[group].items():
            assert math.isclose(value, expected[group][key], rel_tol=1e-12, abs_tol=1e-8), (
                context, group, key, value, expected[group][key]
            )


def worker(batch, output):
    folder = ROOT / "question4/results" / batch
    lock = read_json(folder / "lock.json")
    snapshot = folder / "code_snapshot"
    for relative, expected in lock["code_sha256"].items():
        assert digest(snapshot / relative) == expected, (batch, relative, "snapshot changed")

    # A separate interpreter per batch prevents modules from another batch or
    # the current repository from replacing a historically locked dependency.
    for name in ("question3", "question4"):
        package = types.ModuleType(name)
        package.__path__ = [str(snapshot / name)]
        sys.modules[name] = package
    from question3.interface import Client
    from question4.audit import audit
    from question4.simulator import Simulator
    from question4.strategy import Strategy

    fixtures = read_json(folder / "fixtures.json")
    historical = {
        (r["case_id"], r["config"]): r for r in read_json(folder / "summary.json")["rows"]
    }
    runs = []
    station_rows = []
    for case in fixtures:
        for config, arm in ARMS.items():
            records = []
            env = Simulator(case, rounding=lock["rounding"])
            client = Client(env, "SELF", records.append)
            strategy = Strategy(client, lock["configs"][config])
            observations = []

            class CompletedStations(set):
                def add(self, station_id):
                    assert station_id not in self
                    super().add(station_id)
                    # Called by the original Strategy.run immediately after
                    # its complete channel loop, including near/clear actions.
                    discovered = set(strategy.known) | strategy.cleared
                    observations.append({
                        "completed_stations": len(self),
                        "station_id": station_id,
                        "discovered_channels": len(discovered),
                        "cleared_channels": len(strategy.cleared),
                        "virtual_time_s": client.virtual,
                    })

            strategy.done = CompletedStations()
            result = strategy.run()
            checked = audit(case, records, result)
            truth = env.evaluation()
            previous = historical[(case["id"], config)]
            context = (batch, case["id"], config)
            assert result["status"] == previous["status"] == "complete", context
            assert checked["passed"] and previous["audit"]["passed"], context
            assert truth["cleared"] == previous["cleared"] == previous["total"] == truth["total"], context
            assert checked["accepted_actions"] == previous["audit"]["accepted_actions"], context
            assert_metrics(client.metrics(), previous["metrics"], context)
            assert observations[-1]["discovered_channels"] == truth["total"], context
            assert all(a["discovered_channels"] <= b["discovered_channels"] for a, b in zip(observations, observations[1:])), context
            budget = len(strategy.stations)
            assert budget == (31 if config == "BASE" else 25), context
            common = dict(batch=batch, rounding=lock["rounding"], layout_id=case["id"],
                          family=case["family"], error_mode=case["error_mode"],
                          source_count=truth["total"], arm=arm, original_config=config,
                          station_budget=budget, conditions_per_layout_per_arm=1)
            completed = len(observations)
            first_all = next(o["completed_stations"] for o in observations
                             if o["discovered_channels"] == truth["total"])
            runs.append(common | dict(actual_completed_stations=completed,
                first_all_discovered_station=first_all,
                first_16_discovered_station=first_all if truth["total"] == 16 else "",
                stopped_before_station_budget=int(completed < budget),
                stop_certificate=result["stop_certificate"]["kind"],
                final_cleared=truth["cleared"], final_virtual_time_s=client.virtual,
                historical_metrics_match=1, replay_physics_audit_passed=1))
            initial = dict(completed_stations=0, station_id="", discovered_channels=0,
                           cleared_channels=0, virtual_time_s=0.0)
            for observation in [initial] + observations:
                station_rows.append(common | observation | dict(
                    discovered_fraction=observation["discovered_channels"] / truth["total"]))
    Path(output).write_text(json.dumps(dict(runs=runs, station_rows=station_rows), ensure_ascii=False), encoding="utf-8")
    print(f"{batch}: {len(fixtures)} paired layouts, {len(runs)} replayed runs match historical metrics", flush=True)


def export(output):
    import numpy as np
    output.mkdir(parents=True, exist_ok=True)
    all_runs, observed = [], []
    with tempfile.TemporaryDirectory(prefix="cumcm_q4_discovery_") as temp:
        for batch in BATCHES:
            temporary = Path(temp) / f"{batch}.json"
            subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", batch,
                            "--worker-output", str(temporary)], check=True, cwd=ROOT)
            data = read_json(temporary)
            all_runs.extend(data["runs"])
            observed.extend(data["station_rows"])

    # One physical fixture and one prespecified error condition per batch/arm.
    # No condition averaging is needed; the run is the layout-level observation.
    keyed = collections.defaultdict(list)
    for row in observed:
        keyed[(row["batch"], row["layout_id"], row["arm"])].append(row)
    layout_curves = []
    for run in all_runs:
        curve = keyed[(run["batch"], run["layout_id"], run["arm"])]
        for n in range(32):
            endpoint = curve[min(n, len(curve) - 1)]
            carried = n > run["actual_completed_stations"]
            layout_curves.append({k: run[k] for k in (
                "batch", "rounding", "layout_id", "family", "error_mode", "source_count", "arm",
                "station_budget", "conditions_per_layout_per_arm", "actual_completed_stations")}
                | dict(station_index=n, discovered_channels=endpoint["discovered_channels"],
                       discovered_fraction=endpoint["discovered_fraction"],
                       value_kind="post_stop_carry_forward" if carried else "observed_scan_endpoint" if n else "initial",
                       beyond_station_budget=int(n > run["station_budget"])))

    grouped = collections.defaultdict(list)
    for row in layout_curves:
        for stratum in ("all_10_to_16", f"n_sources_{row['source_count']}"):
            grouped[(row["batch"], row["arm"], stratum, row["station_index"])].append(row)
    summaries = []
    for (batch, arm, stratum, n), rows in sorted(grouped.items()):
        count_q = np.quantile([r["discovered_channels"] for r in rows], [0.25, 0.5, 0.75], method="linear")
        fraction_q = np.quantile([r["discovered_fraction"] for r in rows], [0.25, 0.5, 0.75], method="linear")
        summaries.append(dict(batch=batch, arm=arm, source_stratum=stratum, station_index=n,
            n_independent_layouts=len(rows), n_observed_scan_endpoints=sum(r["value_kind"] != "post_stop_carry_forward" for r in rows),
            n_carried_forward=sum(r["value_kind"] == "post_stop_carry_forward" for r in rows),
            count_q1=float(count_q[0]), count_median=float(count_q[1]), count_q3=float(count_q[2]),
            fraction_q1=float(fraction_q[0]), fraction_median=float(fraction_q[1]), fraction_q3=float(fraction_q[2])))

    run_lookup = {(r["batch"], r["layout_id"], r["arm"]): r for r in all_runs}
    pairs = []
    for run in all_runs:
        if run["arm"] != "baseline31":
            continue
        matched = run_lookup[(run["batch"], run["layout_id"], "recommended25")]
        pairs.append({k: run[k] for k in ("batch", "rounding", "layout_id", "family", "error_mode", "source_count")}
                     | dict(baseline31_first_all=run["first_all_discovered_station"],
                            recommended25_first_all=matched["first_all_discovered_station"],
                            paired_difference_recommended_minus_baseline=matched["first_all_discovered_station"]-run["first_all_discovered_station"],
                            baseline31_actual_completed=run["actual_completed_stations"],
                            recommended25_actual_completed=matched["actual_completed_stations"]))

    write_csv(output / "q4_discovery_runs.csv", all_runs)
    write_csv(output / "q4_discovery_observed_stations.csv", observed)
    write_csv(output / "q4_discovery_layout_curves.csv", layout_curves)
    write_csv(output / "q4_discovery_summary.csv", summaries)
    write_csv(output / "q4_discovery_paired_first_all.csv", pairs)
    sources = {}
    for batch in BATCHES:
        folder = ROOT / "question4/results" / batch
        fixture = read_json(folder / "fixtures.json")
        sources[batch] = dict(
            source_directory=str(folder.relative_to(ROOT)),
            source_sha256={name: digest(folder / name) for name in ("fixtures.json", "summary.json", "lock.json")},
            independent_layouts=len(fixture),
            source_count_distribution=dict(sorted(collections.Counter(len(f["sources"]) for f in fixture).items())),
            error_mode_distribution=dict(collections.Counter(f["error_mode"] for f in fixture)),
            original_environment=read_json(folder / "summary.json").get("environment"),
        )
    manifest = dict(
        provenance="offline reconstruction with individually SHA256-verified frozen historical source; not new validation or official testing",
        original_action_logs_available=False, batches=sources,
        original_arms=ARMS, independent_layouts_total=192, paired_runs_total=384,
        matched_historical_runs=sum(r["historical_metrics_match"] for r in all_runs),
        station_endpoint_definition="after original Strategy.run completes its station channel loop and calls done.add(i)",
        discovered_definition="cardinality of known union cleared; includes earlier discoveries after clearing",
        extension_definition="hold last discovery count after actual final scan through display index31; no unperformed measurements inferred",
        quartile_method="numpy.quantile(method='linear'); distribution quartiles, not confidence intervals",
        output_rows={"runs":len(all_runs), "observed_stations":len(observed), "layout_curves":len(layout_curves), "summary":len(summaries), "paired_first_all":len(pairs)},
        output_sha256={p.name:digest(p) for p in sorted(output.glob("q4_discovery_*.csv"))},
    )
    (output / "q4_discovery_provenance.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(manifest["output_rows"], ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--worker", choices=BATCHES, help=argparse.SUPPRESS)
    parser.add_argument("--worker-output", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker(args.worker, args.worker_output)
    else:
        export(args.output)


if __name__ == "__main__":
    main()
