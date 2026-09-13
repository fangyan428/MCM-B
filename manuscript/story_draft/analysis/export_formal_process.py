"""Export plotting data from the six existing formal runs; never call the simulator.

Run from any directory: python manuscript/story_draft/analysis/export_formal_process.py
Original action logs stay local. Only compact derived data and provenance are exported.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "manuscript/story_draft/plot_data/20260913_process"
RUNS = [(3, 1, 1), (3, 2, 2), (3, 3, 4), (4, 1, 1), (4, 2, 2), (4, 3, 3)]


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_csv(name, rows):
    with (OUT / name).open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def seconds(value):
    # The simulator responses expose virtual time to six decimal places.
    return f"{value:.6f}"


def provenance(path):
    return {"path": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    points, summaries, events, sources = [], [], [], []
    wide = [{"k_cleared": k} for k in range(17)]
    for problem, formal_index, directory_index in RUNS:
        run_dir = ROOT / f"question{problem}/results/windows_q{problem}_final_{directory_index:03d}"
        jlogs = list((ROOT / f"question{problem}/results/jlog_question{problem}").glob(f"formal-p{problem}-{formal_index}-*.jlog"))
        assert len(jlogs) == 1
        jlog = jlogs[0]
        raw = jlog.read_bytes()
        # Only inspect the public JSON header. Do not decrypt the behavior body.
        header_size = int.from_bytes(raw[10:14], "big")
        header = json.loads(raw[14:14 + header_size])
        assert header["package_type"] == "formal_behavior_log"
        assert (header["problem_no"], header["formal_index"]) == (problem, formal_index)
        case_code = header["case_code"]
        series = f"Q{problem}-正式{formal_index}"
        common = {"problem": f"Q{problem}", "formal_index": formal_index,
                  "case_code": case_code, "series_id": series}
        actions = read_jsonl(run_dir / "actions.jsonl")
        strategy = read_jsonl(run_dir / "strategy.jsonl")
        result = json.loads((run_dir / "result.json").read_text())
        requests, accepted_ids = {}, set()
        cleared, discovered = set(), set()
        counts = Counter()
        previous_time = 0.0
        enter_time = enter_real = exit_real = None
        fallback_channel = None
        local_points = []
        fallback_episodes = 0
        no_signal_known = 0
        for line_number, record in enumerate(actions, 1):
            if record["type"] == "request":
                requests[record["payload"]["request_id"]] = record
                continue
            assert record["type"] == "response", (run_dir, line_number, record["type"])
            response = record["response"]
            assert record["http_status"] == 200 and response["accepted"] is True
            request_id = record["request_id"]
            # Count each accepted request only once, including if a log is retried.
            if request_id in accepted_ids:
                continue
            accepted_ids.add(request_id)
            request = requests[request_id]
            path, phase = record["path"], request["phase"]
            assert request["path"] == path
            payload = request["payload"]
            channel = payload.get("channel", "")
            virtual_time = float(response["virtual_time_s"])
            assert virtual_time >= previous_time
            before = len(cleared)
            event_common = {**common, "k_cleared_before": before, "channel": channel,
                            "phase": phase, "channel_previously_discovered": int(channel in discovered),
                            "response_line": line_number}

            def event(kind, when, timing_basis, after=None):
                events.append({**event_common, "event": kind, "virtual_time_s": seconds(when),
                               "k_cleared_after": len(cleared) if after is None else after,
                               "timing_basis": timing_basis})

            if path == "/enter":
                enter_time = virtual_time
                enter_real = response["real_timestamp_ms"]
                assert enter_time == 0.0
                local_points.append({**common, "k_cleared": 0, "virtual_time_s": seconds(0),
                                     "event": "enter", "channel": "", "phase": "control",
                                     "response_line": line_number})
            elif path == "/measure":
                counts["measure"] += 1
                kind = response["measure_result"]
                counts[kind] += 1
                if kind in ("direction", "near"):
                    discovered.add(channel)
                else:
                    assert kind == "no_signal"
                    if problem == 4:
                        event("no_signal", virtual_time, "response_end")
                        no_signal_known += int(channel in discovered)
                fallback_channel = None
            elif path == "/clear":
                counts["clear"] += 1
                if problem == 4 and phase == "optical_fallback" and fallback_channel != channel:
                    fallback_episodes += 1
                    # Beginning of the first fallback action, before its movement/optical costs.
                    event("optical_fallback_start", previous_time, "preceding_response_end")
                fallback_channel = channel if phase == "optical_fallback" else None
                kind = response["clear_result"]
                if kind == "success":
                    assert channel not in cleared
                    assert channel in discovered
                    cleared.add(channel)
                    counts["clear_success"] += 1
                    local_points.append({**common, "k_cleared": len(cleared),
                                         "virtual_time_s": seconds(virtual_time), "event": "clear_success",
                                         "channel": channel, "phase": phase, "response_line": line_number})
                    if problem == 4 and phase == "optical_fallback":
                        event("optical_fallback_success", virtual_time, "response_end")
                    fallback_channel = None
                else:
                    assert kind == "no_target_in_range"
                    counts["clear_failure"] += 1
                    if problem == 4:
                        event("clear_no_target_in_range", virtual_time, "response_end")
            elif path == "/exit":
                exit_real = response["real_timestamp_ms"]
                assert response["exit_reason"] == "user_exit"
            else:
                raise AssertionError(path)
            previous_time = virtual_time
        assert enter_time is not None and exit_real is not None
        assert result["status"] == "complete"
        assert set(result["cleared_channels"] if problem == 3 else result["cleared"]) == cleared
        metrics = result["metrics"]
        assert abs(metrics["virtual_time_s"] - previous_time) < 1e-6
        for key in ("measure", "clear", "clear_success", "clear_failure"):
            assert metrics["counts"].get(key, 0) == counts[key]
        if problem == 4:
            assert sum(r["event"] == "optical_cover" for r in strategy) == fallback_episodes
        created_ms = datetime.fromisoformat(header["created_at_utc"].replace("Z", "+00:00")).timestamp() * 1000
        header_gap = round(created_ms - exit_real)
        assert 0 <= header_gap < 100
        last_clear = float(local_points[-1]["virtual_time_s"])
        summaries.append({**common, "run_directory": str(run_dir.relative_to(ROOT)),
                          "n_cleared": len(cleared), "last_clear_virtual_time_s": seconds(last_clear),
                          "exit_virtual_time_s": seconds(previous_time),
                          "post_last_clear_virtual_time_s": seconds(previous_time - last_clear),
                          "measure_count": counts["measure"], "no_signal_count": counts["no_signal"],
                          "known_channel_no_signal_count": no_signal_known if problem == 4 else "",
                          "clear_failure_count": counts["clear_failure"],
                          "optical_fallback_episodes": fallback_episodes if problem == 4 else "",
                          "formal_header_after_exit_ms": header_gap})
        points.extend(local_points)
        lookup = {p["k_cleared"]: p["virtual_time_s"] for p in local_points}
        for row in wide:
            row[f"Q{problem}_formal_{formal_index}_T_s"] = lookup.get(row["k_cleared"], "")
        sources.append({**common, "inputs": [provenance(run_dir / name) for name in
                        ("actions.jsonl", "strategy.jsonl", "result.json", "config.json")] + [provenance(jlog)],
                        "validation": "accepted request/response pairing; unique clear channels; final result metrics; public formal header and exit timing"})
    assert len(points) == 80  # 74 successful clears and six entry points.
    write_csv("formal_clear_trajectories.csv", points)
    write_csv("formal_clear_times_wide.csv", wide)
    write_csv("formal_run_summary.csv", summaries)
    write_csv("formal_q4_events.csv", events)
    manifest = {"time_definition": "Simulator response.virtual_time_s, measured from successful /enter; never wall time.",
                "curve_definition": "Entry (0,0) and cumulative virtual time at each unique successful /clear response.",
                "exit_definition": "The exit time can exceed the last clear time; it is not another successful clear.",
                "event_definition": "No-signal and clear events use response end time. Fallback starts use the preceding response time, before the first fallback action.",
                "formal_directory_correction": "Q3 formal test 3 is windows_q3_final_004. Directory 003 failed before entry.",
                "sources": sources, "outputs": {"clear_rows_including_origins": len(points), "q4_event_rows": len(events)}}
    (OUT / "formal_data_provenance.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"runs": len(summaries), "curve_rows": len(points), "q4_events": len(events),
                      "last_clear_to_exit_s": {r["series_id"]: r["post_last_clear_virtual_time_s"] for r in summaries}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
