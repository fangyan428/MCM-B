"""Export Q3 plotting data; read existing logs only, never run an arena session.

Run from the repository root:
    python manuscript/story_draft/analysis/export_q3_convergence.py
Use --geometry-only when the local-only official logs are unavailable.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from question3.innovation.geometry import SLACK, bbox, clip, initial, wedge

RUNS = (
    ("windows_q3_final_001", "5ER6-BK3Y-KHDQ-MUQT", 1),
    ("windows_q3_final_002", "VUK9-G6FH-ACSC-KFYG", 2),
    ("windows_q3_final_004", "3BEW-YK5X-AE2M-SJND", 3),
)
OUT = ROOT / "manuscript/story_draft/plot_data/20260913_process"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def diameter(poly):
    return float(np.linalg.norm(poly[:, None, :] - poly[None, :, :], axis=2).max())


def geometric_example(out):
    # The manuscript's teaching example has fixed Cartesian bbox axes, +/-1 deg,
    # and a square prior. It deliberately differs from the official algorithm.
    source = np.array([600., 100.])
    poly = np.array([[-1500., -1500.], [1500., -1500.],
                     [1500., 1500.], [-1500., 1500.]])
    rows, vertices = [], []
    for count, point in enumerate(((0., 0.), (350., -250.), (500., 100.)), 1):
        point = np.asarray(point)
        bearing = math.degrees(math.atan2(*(source - point)[::-1])) % 360
        # Exact geometric boundary, no numerical expansion of the wedge.
        for sign in (-1, 1):
            angle = math.radians(bearing + sign)
            normal = np.array([-sign * math.sin(angle), sign * math.cos(angle)])
            poly = clip(poly, normal, float(normal @ point))
        centre = (poly.min(axis=0) + poly.max(axis=0)) / 2
        radius = float(np.linalg.norm(poly - centre, axis=1).max())
        rows.append(dict(example_id="fig17_geometric_recalculation", bearing_count=count,
                         covering_radius_m=radius, region_diameter_m=diameter(poly),
                         clear_threshold_m=20., centre_x_m=float(centre[0]),
                         centre_y_m=float(centre[1]), measure_x_m=float(point[0]),
                         measure_y_m=float(point[1]), bearing_deg=bearing,
                         bearing_error_halfwidth_deg=1.,
                         source_x_m=float(source[0]), source_y_m=float(source[1]),
                         vertex_count=len(poly), direct_clear_geometrically_certified=radius < 20))
        vertices.append(dict(bearing_count=count, vertices_m=poly.tolist()))
    expected = [(762.68, 1525.36), (23.78, 47.57), (10.66, 21.26)]
    for row, (radius, diam) in zip(rows, expected):
        assert round(row["covering_radius_m"], 2) == radius
        assert round(row["region_diameter_m"], 2) == diam
    write_csv(out / "q3_convergence_geometric_example.csv", rows)
    write_json(out / "q3_convergence_geometric_vertices.json", vertices)
    return dict(
        data_kind="按论文明确参数复算的几何算例；不是正式测试或平均结果",
        source="manuscript/story_draft/中文论文初稿.md, 5.3.2, fig17_shrink",
        original_figure_generator_found=False,
        precision="float64 复算结果按 Python 最短往返表示保存，不补造原绘图程序的末位数值",
        match="半径、直径保留两位小数与现论文完全一致",
        initial_region="[-1500,1500]^2", centre_definition="固定全局坐标轴包围盒中心",
        error_halfwidth_deg=1., centreline_error_deg=0., numeric_wedge_expansion_m=0.,
        independent_layouts=1, formal_test=False,
    )


def accepted_actions(path):
    requests, seen, accepted = {}, set(), []
    for line, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        record = json.loads(raw)
        if record["type"] == "request":
            requests[record["payload"]["request_id"]] = record
        elif record["type"] == "response" and record.get("response", {}).get("accepted"):
            ident = record["request_id"]
            if ident in seen:
                continue  # A retried idempotent action is one observation.
            seen.add(ident)
            request = requests[ident]
            assert request["path"] == record["path"]
            accepted.append(dict(request=request, response=record["response"],
                                 path=record["path"], line=line))
    return accepted


def official_run(run_id, case_code, formal_index):
    folder = ROOT / "question3/results" / run_id
    lock = json.loads((folder / "code_sha256.json").read_text())
    config = json.loads((folder / "config.json").read_text())
    hashes = {}
    for name in ("innovation/geometry.py", "innovation/strategy.py"):
        actual = sha(ROOT / "question3" / name)
        expected = lock[name.replace("/", "\\")]
        if actual != expected:
            raise RuntimeError(f"{run_id}: source hash mismatch: {name}")
        hashes[name] = actual
    if config["mechanism"] != "gated_tour_multi_parallax":
        raise RuntimeError(f"{run_id}: this exporter is scoped to the recorded recommended policy")
    events = [(line, json.loads(raw)) for line, raw in enumerate(
        (folder / "strategy.jsonl").read_text(encoding="utf-8").splitlines(), 1)]
    actions = accepted_actions(folder / "actions.jsonl")
    directions = [a for a in actions if a["response"].get("measure_result") == "direction"]
    updates = [(line, e) for line, e in events if e["type"] == "feasible_update"]
    assert len(directions) == len(updates)
    error = config["baseline_config"]["error_deg"]
    polygons, counts, bearings, rows = {}, Counter(), {}, []
    max_vertex_difference = 0.
    for action, (line, event) in zip(directions, updates):
        payload, response = action["request"]["payload"], action["response"]
        channel, point = payload["channel"], [payload["position"][axis] for axis in ("x", "y")]
        angle = response["svd_deg"]
        assert channel == event["channel"] and angle == event["bearing"]
        np.testing.assert_array_equal(point, event["point"])
        rebuilt = (initial(point, angle, error) if channel not in polygons
                   else wedge(polygons[channel], point, angle, error))
        recorded = np.asarray(event["vertices"], dtype=float)
        np.testing.assert_allclose(rebuilt, recorded, atol=1e-8, rtol=0)
        max_vertex_difference = max(max_vertex_difference, float(np.abs(rebuilt - recorded).max()))
        # Export metrics of the ORIGINAL logged vertices, not the rebuilt array.
        centre, certified_radius, *_ = bbox(recorded, angle)
        radius = float(np.linalg.norm(recorded - centre, axis=1).max())
        counts[channel] += 1
        polygons[channel], bearings[channel] = recorded, angle
        rows.append(dict(
            run_id=run_id, formal_index=formal_index, case_code=case_code,
            source_curve_id=f"Q3-{formal_index}-ch{channel:02d}", channel=channel,
            bearing_count=counts[channel], covering_radius_m=radius,
            algorithm_radius_with_slack_m=certified_radius,
            region_diameter_m=diameter(recorded), clear_threshold_m=20.,
            centre_x_m=float(centre[0]), centre_y_m=float(centre[1]),
            measure_x_m=point[0], measure_y_m=point[1], bearing_deg=angle,
            virtual_time_s=response["virtual_time_s"], phase=action["request"]["phase"],
            vertex_count=len(recorded), action_response_line=action["line"],
            strategy_update_line=line,
        ))
    # Cross-check all certificates against the same latest recorded region.
    current, last_angle, clear_certs, checked = {}, {}, {}, Counter()
    max_certificate_difference = 0.
    for _, event in events:
        if event["type"] == "feasible_update":
            current[event["channel"]] = np.asarray(event["vertices"])
            last_angle[event["channel"]] = event["bearing"]
        elif event["type"] in ("certified_measure", "certified_clear"):
            channel = event["channel"]
            np.testing.assert_array_equal(event["vertices"], current[channel])
            expected = float(np.linalg.norm(current[channel] - event["point"], axis=1).max() + SLACK)
            difference = abs(expected - event["radius"])
            max_certificate_difference = max(max_certificate_difference, difference)
            assert difference <= 1e-8
            if event["type"] == "certified_clear":
                centre, radius, *_ = bbox(current[channel], last_angle[channel])
                np.testing.assert_allclose(event["point"], centre, atol=1e-8, rtol=0)
                assert radius <= 20 - 1e-5
                clear_certs[channel] = event
            checked[event["type"]] += 1
    by_channel = defaultdict(list)
    for row in rows:
        by_channel[row["channel"]].append(row)
    clears = [a for a in actions if a["response"].get("clear_result") == "success"]
    summary = []
    assert len({a["request"]["payload"]["channel"] for a in clears}) == len(clears)
    for action in clears:
        payload = action["request"]["payload"]
        channel = payload["channel"]
        curve = by_channel[channel]
        near = action["request"]["phase"] == "near"
        if not near:
            assert channel in clear_certs
        summary.append(dict(
            run_id=run_id, formal_index=formal_index, case_code=case_code,
            source_curve_id=f"Q3-{formal_index}-ch{channel:02d}", channel=channel,
            valid_direction_count=len(curve),
            first_radius_m=curve[0]["covering_radius_m"] if curve else "",
            last_radius_m=curve[-1]["covering_radius_m"] if curve else "",
            clear_method="near_feedback" if near else "certified_region_circle",
            successful_clear_virtual_time_s=action["response"]["virtual_time_s"],
            clear_x_m=payload["position"]["x"], clear_y_m=payload["position"]["y"],
            action_response_line=action["line"],
        ))
    result = json.loads((folder / "result.json").read_text())
    assert sorted(r["channel"] for r in summary) == result["cleared_channels"]
    summary.sort(key=lambda r: r["channel"])
    return rows, summary, dict(
        run_id=run_id, case_code=case_code, formal_index=formal_index,
        normal_bearing_states=len(rows), source_curves=len(by_channel), cleared_sources=len(clears),
        clear_methods=dict(Counter(r["clear_method"] for r in summary)),
        source_code_sha256=hashes,
        input_sha256={name: sha(folder / name) for name in (
            "actions.jsonl", "strategy.jsonl", "config.json", "code_sha256.json", "result.json")},
        error_halfwidth_deg=error, max_rebuilt_vertex_error_m=max_vertex_difference,
        checked_certificates=dict(checked), max_certificate_radius_error_m=max_certificate_difference,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=OUT)
    parser.add_argument("--geometry-only", action="store_true")
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    metadata = dict(
        export_script="manuscript/story_draft/analysis/export_q3_convergence.py",
        geometric_example=geometric_example(args.out_dir),
        units=dict(distance="m", time="simulator virtual seconds", angle="degrees"),
        csv_encoding="UTF-8 with BOM", floating_point_export="Python float repr, no decimal rounding",
    )
    if not args.geometry_only:
        all_rows, all_summary, audits = [], [], []
        for run in RUNS:
            rows, summary, audit = official_run(*run)
            all_rows.extend(rows)
            all_summary.extend(summary)
            audits.append(audit)
        write_csv(args.out_dir / "q3_convergence_official.csv", all_rows)
        write_csv(args.out_dir / "q3_convergence_official_source_summary.csv", all_summary)
        metadata["official"] = dict(
            provenance="从正式策略日志 feasible_update.vertices 计算指标；另用动作响应和哈希一致源码独立重建核验",
            independent_official_runs=3, new_runs_performed=0,
            excluded_run="windows_q3_final_003: enter connection interruption, no accepted arena entry",
            radius_definition="q 为最新示向方向旋转包围盒中心；covering_radius_m=max_v||v-q||",
            algorithm_radius_definition="algorithm_radius_with_slack_m=covering_radius_m+1e-7",
            count_definition="每个频道的 direction 正常测向次数；不计 no_signal 或 near",
            interpretation="每条线是一个源的真实运行轨迹；三个正式测试共38源，不是38独立布局",
            terminal_note="near 后直接清除不产生新的多边形；7条此类轨迹不额外添加 R=5 或 R=0 点",
            region_nesting_note="区域嵌套不自动保证旋转包围盒中心的覆盖半径严格单调，不平滑或修正数据",
            raw_logs_local_only=True, runs=audits,
        )
    write_json(args.out_dir / "q3_convergence_metadata.json", metadata)
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
