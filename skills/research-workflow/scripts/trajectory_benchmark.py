#!/usr/bin/env python3
"""Reproduce a fixed-shape single-axis polynomial trajectory comparison.

Python 3.10+, standard library only. SI units. The resulting durations are the
minimum feasible durations within each prescribed polynomial shape; they do not
solve globally time-optimal jerk-limited motion planning.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import html
import json
import math
from pathlib import Path
import platform
import re
import sys

from verify_trajectory import verify_output

FAMILIES = {
    "quintic": {"velocity": 15 / 8, "acceleration": 10 / math.sqrt(3), "jerk": 60.0},
    "septic": {"velocity": 35 / 16, "acceleration": 84 / (5 * math.sqrt(5)), "jerk": 105 / 2},
}
COLORS = {"quintic": "#2563eb", "septic": "#dc2626"}


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_input(data):
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data.get("schema_version") != 1:
        raise ValueError("Input must be an object with schema_version=1.")
    if data.get("units") != {"position": "m", "time": "s"}:
        raise ValueError("Units must be position=m and time=s; convert input explicitly.")
    limits = data.get("limits")
    if not isinstance(limits, dict) or set(limits) != {"velocity", "acceleration", "jerk"}:
        raise ValueError("limits must contain exactly velocity, acceleration, and jerk.")
    for name, value in limits.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"Limit {name} must be a finite positive number.")
    samples = data.get("samples_per_trajectory")
    if isinstance(samples, bool) or not isinstance(samples, int) or not 101 <= samples <= 10001:
        raise ValueError("samples_per_trajectory must be an integer from 101 to 10001.")
    cases = data.get("cases")
    if not isinstance(cases, list) or not 1 <= len(cases) <= 32:
        raise ValueError("Provide between 1 and 32 cases.")
    seen = set()
    for case in cases:
        if not isinstance(case, dict) or set(case) != {"id", "start", "end"}:
            raise ValueError("Each case must contain exactly id, start, and end.")
        case_id = case["id"]
        if not isinstance(case_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", case_id):
            raise ValueError("Case ids must be 1–64 ASCII letters, numbers, underscores, or hyphens.")
        if case_id in seen:
            raise ValueError(f"Duplicate case id: {case_id}")
        seen.add(case_id)
        for name in ("start", "end"):
            value = case[name]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{case_id}.{name} must be a finite number.")
        if not math.isfinite(case["end"] - case["start"]):
            raise ValueError("Displacement overflow; rescale input.")
    return data


def shape(family, u):
    """Return dimensionless position and first three time-normalized derivatives."""
    if family == "quintic":
        return (u ** 3 * (10 + u * (-15 + 6 * u)),
                30 * u ** 2 * (1 - u) ** 2,
                60 * u * (1 - u) * (1 - 2 * u),
                60 * (1 - 6 * u + 6 * u ** 2))
    if family == "septic":
        return (u ** 4 * (35 + u * (-84 + u * (70 - 20 * u))),
                140 * u ** 3 * (1 - u) ** 3,
                420 * u ** 2 * (1 - u) ** 2 * (1 - 2 * u),
                840 * u * (1 - u) * (1 - 5 * u + 5 * u ** 2))
    raise ValueError(f"Unknown polynomial family: {family}")


def duration_components(family, distance, limits):
    if distance < 0 or not math.isfinite(distance):
        raise ValueError("distance must be nonnegative and finite.")
    constants = FAMILIES[family]
    terms = {"velocity_s": distance * constants["velocity"] / limits["velocity"],
             "acceleration_s": math.sqrt(distance * constants["acceleration"] / limits["acceleration"]),
             "jerk_s": (distance * constants["jerk"] / limits["jerk"]) ** (1 / 3)}
    if any(not math.isfinite(value) for value in terms.values()) or (distance > 0 and max(terms.values()) == 0):
        raise ValueError("Duration is outside representable range; rescale input.")
    return terms


def trajectory_rows(family, case, duration, samples):
    displacement = case["end"] - case["start"]
    if displacement == 0:
        return [{"time_s": 0.0, "position_m": case["start"], "velocity_m_s": 0.0,
                 "acceleration_m_s2": 0.0, "jerk_m_s3": 0.0}]
    rows = []
    for i in range(samples):
        u = i / (samples - 1)
        p, v, a, j = shape(family, u)
        rows.append({"time_s": duration * u, "position_m": case["start"] + displacement * p,
                     "velocity_m_s": displacement * v / duration,
                     "acceleration_m_s2": displacement * a / duration ** 2,
                     "jerk_m_s3": displacement * j / duration ** 3})
    return rows


def peak_values(family, distance, duration):
    names = ("velocity_m_s", "acceleration_m_s2", "jerk_m_s3")
    if duration == 0:
        return dict.fromkeys(names, 0.0)
    return {name: distance * FAMILIES[family][metric] / duration ** order
            for order, (name, metric) in enumerate(zip(names, ("velocity", "acceleration", "jerk")), 1)}


def svg_start(width, height, description):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
            f'<title>{html.escape(description)}</title>', '<rect width="100%" height="100%" fill="white"/>',
            '<style>text{font-family:Arial,sans-serif;font-size:13px;fill:#172033}.grid{stroke:#e2e8f0;stroke-width:1}.axis{stroke:#475569;stroke-width:1}</style>']


def duration_svg(summary, path):
    cases = [case for case in summary["cases"] if abs(case["displacement_m"]) > 0]
    width, height, left, top, plot_width, plot_height = 960, 420, 80, 70, 830, 270
    items = svg_start(width, height, "Minimum feasible duration within two polynomial families")
    items.append('<text x="40" y="30" style="font-size:20px;font-weight:bold">Fixed-shape feasible durations under identical limits</text>')
    max_t = max((case["common_duration_s"] for case in cases), default=1.0) * 1.1
    for tick in range(6):
        y = top + plot_height * (1 - tick / 5)
        items.extend([f'<line class="grid" x1="{left}" y1="{y}" x2="{left + plot_width}" y2="{y}"/>',
                      f'<text x="{left-12}" y="{y+4}" text-anchor="end">{max_t*tick/5:.2f}</text>'])
    items.append(f'<text x="20" y="{top-15}">Time (s)</text>')
    group = plot_width / max(1, len(cases))
    if not cases:
        items.append('<text x="300" y="200">All cases are stationary: duration = 0 s.</text>')
    for i, case in enumerate(cases):
        center = left + group * (i + 0.5)
        for j, family in enumerate(FAMILIES):
            value = case["families"][family]["minimum_duration_s"]
            bar_height = value / max_t * plot_height
            x = center + (j - 1) * 52 + 6
            y = top + plot_height - bar_height
            items.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="40" height="{bar_height:.2f}" fill="{COLORS[family]}"/>')
            items.append(f'<text x="{x+20:.2f}" y="{y-6:.2f}" text-anchor="middle">{value:.3f}</text>')
        items.append(f'<text x="{center}" y="{top+plot_height+24}" text-anchor="middle">{case["displacement_m"]*1000:g} mm</text>')
    for j, family in enumerate(FAMILIES):
        items.append(f'<rect x="{300+j*190}" y="385" width="15" height="15" fill="{COLORS[family]}"/>')
        items.append(f'<text x="{322+j*190}" y="397">{family}</text>')
    items.append('</svg>')
    path.write_text("\n".join(items), encoding="utf-8")


def profiles_svg(case, rowsets, path):
    width, height, left, top, panel_width, panel_height = 1100, 760, 92, 85, 400, 235
    items = svg_start(width, height, "Equal-duration position, velocity, acceleration, and jerk")
    items.append(f'<text x="35" y="30" style="font-size:20px;font-weight:bold">Equal-duration profiles: {html.escape(case["id"])}; T = {case["common_duration_s"]:.6f} s</text>')
    items.append('<text x="35" y="53">Same displacement, limits, and duration; the two shapes use different endpoint jerk conditions.</text>')
    columns = [("position_m", "Position (m)"), ("velocity_m_s", "Velocity (m/s)"),
               ("acceleration_m_s2", "Acceleration (m/s^2)"), ("jerk_m_s3", "Jerk (m/s^3)")]
    duration = case["common_duration_s"]
    for i, (column, label) in enumerate(columns):
        x0 = left + (i % 2) * 510
        y0 = top + (i // 2) * 320
        values = [row[column] for rows in rowsets.values() for row in rows]
        minimum, maximum = min(values), max(values)
        padding = max((maximum - minimum) * .08, 1e-9)
        minimum -= padding
        maximum += padding
        items.append(f'<text x="{x0}" y="{y0-13}" style="font-weight:bold">{label}</text>')
        for tick in range(5):
            y = y0 + panel_height * tick / 4
            value = maximum - (maximum - minimum) * tick / 4
            items.extend([f'<line class="grid" x1="{x0}" y1="{y}" x2="{x0+panel_width}" y2="{y}"/>',
                          f'<text x="{x0-8}" y="{y+4}" text-anchor="end">{value:.3g}</text>'])
        for tick in range(5):
            x = x0 + panel_width * tick / 4
            items.append(f'<text x="{x}" y="{y0+panel_height+20}" text-anchor="middle">{duration*tick/4:.3f}</text>')
        items.append(f'<text x="{x0+panel_width}" y="{y0+panel_height+39}" text-anchor="end">Time (s)</text>')
        for family, rows in rowsets.items():
            points = " ".join(f'{x0+row["time_s"]/duration*panel_width:.3f},{y0+(maximum-row[column])/(maximum-minimum)*panel_height:.3f}' for row in rows[::4])
            if (len(rows) - 1) % 4:
                row = rows[-1]
                points += f' {x0+panel_width:.3f},{y0+(maximum-row[column])/(maximum-minimum)*panel_height:.3f}'
            items.append(f'<polyline points="{points}" fill="none" stroke="{COLORS[family]}" stroke-width="2.2"/>')
    for i, family in enumerate(FAMILIES):
        items.append(f'<rect x="{380+i*170}" y="730" width="15" height="15" fill="{COLORS[family]}"/>')
        items.append(f'<text x="{402+i*170}" y="742">{family}</text>')
    items.append('</svg>')
    path.write_text("\n".join(items), encoding="utf-8")


def make_report(summary, quality):
    lines = ["# 单轴多项式轨迹规划：可复现科研小实验", "",
             "研究问题：在同一位移、速度/加速度/jerk 绝对值上限下，固定五次与七次多项式轨迹的最小可行时长如何变化？七次轨迹额外要求两端 jerk 为零。", "",
             "**结论范围：这是两个固定形状族的时间缩放比较，不是全局时间最优求解，也不是机器人或机床硬件性能结论。**", "",
             "## 输入与假设", "",
             f"- SI 单位：位移 m，时间 s；速度上限 {summary['limits']['velocity']:g} m/s，加速度上限 {summary['limits']['acceleration']:g} m/s²，jerk 上限 {summary['limits']['jerk']:g} m/s³。",
             "- 单轴运动，初末速度、加速度均为零；起点和终点之间采用单调多项式，不含障碍物、力矩、伺服、共振、采样控制器、轴间同步或拐角拼接模型。",
             "- 真实控制器必须另外核实插补周期、位置精度、轴耦合与驱动饱和。本实验不声称论文新颖性。", "",
             "## 原创推导", "",
             "令 u=t/T，Δq=q₁−q₀，D=|Δq|。q(t)=q₀+Δq·f(u)。", "",
             "五次：f₅(u)=10u³−15u⁴+6u⁵。七次：f₇(u)=35u⁴−84u⁵+70u⁶−20u⁷。", "",
             "由 v=Δq f′/T、a=Δq f″/T²、j=Δq f‴/T³，在 [0,1] 上检查导数零点和端点，得到：", "",
             "| 形状 | 速度峰值 Cᵥ | 加速度峰值 Cₐ | jerk 峰值 Cⱼ |", "|---|---:|---:|---:|",
             "| 五次 | 15/8 | 10/√3 | 60 |", "| 七次 | 35/16 | 84/(5√5) | 105/2 |", "",
             "五次速度峰值在 u=1/2；加速度绝对峰值在 u=(3±√3)/6；jerk 绝对峰值在 u=0、1（中点值 −30）。",
             "七次速度峰值在 u=1/2；加速度绝对峰值在 u=(5±√5)/10；jerk 的内部极值在 u=(5±√15)/10、1/2，对应值 42、−105/2、42，端点为零。", "",
             "对每个固定形状，T*=max(D·Cᵥ/Vmax, √(D·Cₐ/Amax), ∛(D·Cⱼ/Jmax))。",
             "必要性来自三个峰值约束；充分性来自这些峰值已经覆盖整个连续区间。每个峰值随 T 增大而按 T⁻¹、T⁻²、T⁻³ 单调减小，因此该最大值就是该形状族的最小可行时长。D=0 采用 T=0 的静止约定。", "",
             "## 结果", "",
             "| 工况 | 位移 m | 五次 T* s | 主导约束 | 七次 T* s | 主导约束 | (七次/五次−1) |",
             "|---|---:|---:|---|---:|---|---:|"]
    for case in summary["cases"]:
        q, s = (case["families"][name] for name in FAMILIES)
        ratio = f"{(s['minimum_duration_s']/q['minimum_duration_s']-1)*100:+.2f}%" if q["minimum_duration_s"] else "不适用"
        lines.append(f"| {case['id']} | {case['displacement_m']:.6g} | {q['minimum_duration_s']:.9f} | {', '.join(q['active_constraints'])} | {s['minimum_duration_s']:.9f} | {', '.join(s['active_constraints'])} | {ratio} |")
    lines += ["", "![时长比较](duration-comparison.svg)", "", "![同工况共同时间的轨迹曲线](equal-duration-profiles.svg)", "",
              "本输入下，短行程可能由 jerk 约束主导，中行程可能由加速度主导，长行程可能由速度主导。七次多项式的归一化 jerk 峰值更低，但速度和加速度峰值更高，因此不保证时长更短。请以上表实际主导约束为准。", "",
              "每个工况还提供共同时间 T_common=max(T*₅,T*₇) 的两条轨迹，避免仅比较不同完成时刻的曲线。summary.json 同时记录各自最小时长与共同时间下的全部解析峰值；csv/ 提供两种模式的采样数据。", "",
              "## 端点 jerk 与静止延拓", "",
              "五次轨迹在运动区间内部的两端单侧 jerk 为 60Δq/T³，静止段 jerk 为零。与静止段拼接后，位置函数属于 C²；经典三阶导数在拼接点不存在，但几乎处处有界的弱 jerk 不含冲量，因为加速度连续。只要求区间内或几乎处处 jerk 上界时，本实验五次方案满足上限；若要求全局连续 jerk 或拼接点处经典 jerk 存在，五次方案不满足。",
              "七次轨迹端点 jerk=0，与静止段拼接后属于 C³；snap 仍可跳变。额外端点条件改变了候选族，因此比较不能证明任何一族整体优于另一族。", "",
              "## 质量检查与复现", "",
              f"本次独立检查：**{quality['checks_passed']}/{quality['checks_total']} 通过**（详见 quality-checks.json）。",
              "生成器使用解析峰值常数；独立检查器从多项式系数递归隔离导数根，再核查整个 [0,1] 上的极值、所有 CSV 样点、端点、时间排序、正反向工况及轻微缩短后的约束违反。浮点计算和数值根隔离属于数值审计，不是形式化证明；解析推导另见上文。",
              "采样数据用于复现和画图，采样本身不能证明连续时间约束。manifest.json 记录原始输入、实际运行输入和脚本 SHA-256、Python 版本、UTC 运行时间及输出文件哈希。", "",
              "在 Skill 目录执行：", "", "```text",
              "python scripts/trajectory_benchmark.py --input assets/trajectory-input.json --output ../../examples/trajectory-planning",
              "python scripts/verify_trajectory.py --input assets/trajectory-input.json --output ../../examples/trajectory-planning",
              "```", "",
              "输出目录可改为任意新的目录。仓库根目录执行 python -m unittest discover -s tests -v；本报告不将单元测试未执行的状态描述为通过。", "",
              "## 后续可证伪假设", "",
              "在包含拐角和多轴同步的实际轨迹上，连续 jerk 端点是否降低跟踪误差，必须结合相同控制器、采样周期、路径公差、负载和硬件实验验证。当前输出只支持固定形状的运动学比较。", ""]
    return "\n".join(lines)


def run(input_path, output_path):
    input_path, output_path = Path(input_path).resolve(), Path(output_path).resolve()
    data = validate_input(json.loads(input_path.read_text(encoding="utf-8-sig")))
    if output_path == input_path.parent or output_path in input_path.parents:
        raise ValueError("Use a separate output directory, not the input directory or its ancestor.")
    if output_path.exists() and any(output_path.iterdir()):
        previous_manifest = output_path / "manifest.json"
        if not previous_manifest.is_file() or json.loads(previous_manifest.read_text(encoding="utf-8")).get("original_input_sha256") != digest(input_path):
            raise ValueError("A nonempty output directory may only be reused with the same recorded input. Choose a new output directory.")
    output_path.mkdir(parents=True, exist_ok=True)
    csv_directory = output_path / "csv"
    csv_directory.mkdir(exist_ok=True)
    summary = {"schema_version": 1, "experiment": "fixed_shape_polynomial_duration_comparison",
               "units": data["units"], "limits": data["limits"], "dimensionless_peaks": FAMILIES,
               "duration_scope": "minimum feasible duration within each fixed polynomial shape; not global time optimality",
               "endpoint_jerk_policy": "quintic: one-sided values on the moving interval, undefined classical jerk at rest joins; septic: zero and continuous at rest joins",
               "cases": []}
    profiles = {}
    for case in data["cases"]:
        displacement = case["end"] - case["start"]
        distance = abs(displacement)
        components = {family: duration_components(family, distance, data["limits"]) for family in FAMILIES}
        durations = {family: max(terms.values()) for family, terms in components.items()}
        common_duration = max(durations.values())
        result = {"id": case["id"], "start_m": case["start"], "end_m": case["end"], "displacement_m": displacement,
                  "common_duration_s": common_duration, "families": {}}
        for family in FAMILIES:
            entry = {"minimum_duration_s": durations[family], "duration_bounds_s": components[family],
                     "active_constraints": [name.removesuffix("_s") for name, value in components[family].items()
                                            if distance and math.isclose(value, durations[family], rel_tol=1e-10, abs_tol=0.0)]}
            if not distance:
                entry["active_constraints"] = ["stationary"]
            for mode, duration in (("minimum", durations[family]), ("common", common_duration)):
                rows = trajectory_rows(family, case, duration, data["samples_per_trajectory"])
                relative_csv = f"csv/{case['id']}-{family}-{mode}.csv"
                with (output_path / relative_csv).open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=rows[0].keys(), lineterminator="\n")
                    writer.writeheader()
                    writer.writerows(rows)
                entry[mode] = {"duration_s": duration, "peak_absolute": peak_values(family, distance, duration),
                               "csv": relative_csv, "samples": len(rows)}
                if mode == "common" and distance:
                    profiles.setdefault(case["id"], {})[family] = rows
            result["families"][family] = entry
        summary["cases"].append(result)
    write_json(output_path / "summary.json", summary)
    write_json(output_path / "input.json", data)
    quality = verify_output(input_path, output_path)
    write_json(output_path / "quality-checks.json", quality)
    (output_path / "report.md").write_text(make_report(summary, quality), encoding="utf-8")
    duration_svg(summary, output_path / "duration-comparison.svg")
    profile_case = next((case for case in summary["cases"] if case["id"] == "move_100mm"),
                        next((case for case in summary["cases"] if case["displacement_m"] != 0), None))
    if profile_case:
        profiles_svg(profile_case, profiles[profile_case["id"]], output_path / "equal-duration-profiles.svg")
    else:
        note = svg_start(900, 160, "Stationary trajectories")
        note.extend(['<text x="35" y="80">All trajectories are stationary: q(t)=q0; v=a=j=0; duration convention T=0.</text>', '</svg>'])
        (output_path / "equal-duration-profiles.svg").write_text("\n".join(note), encoding="utf-8")
    source_directory = Path(__file__).resolve().parent
    manifest = {"schema_version": 1, "run_time_utc": datetime.now(timezone.utc).isoformat(),
                "python_version": platform.python_version(), "implementation": platform.python_implementation(),
                "reproduction": "python scripts/trajectory_benchmark.py --input assets/trajectory-input.json --output <new-output-directory>",
                "original_input_sha256": digest(input_path), "normalized_input_sha256": digest(output_path / "input.json"),
                "code_sha256": {name: digest(source_directory / name) for name in ("trajectory_benchmark.py", "verify_trajectory.py")},
                "quality_status": quality["status"],
                "outputs": {path.relative_to(output_path).as_posix(): {"sha256": digest(path), "bytes": path.stat().st_size}
                            for path in sorted(output_path.rglob("*")) if path.is_file() and path.name != "manifest.json"}}
    write_json(output_path / "manifest.json", manifest)
    return summary, quality


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        summary, quality = run(args.input, args.output)
    except (ValueError, OSError, OverflowError) as error:
        parser.exit(2, f"Input/output error: {error}\n")
    print(json.dumps({"cases": len(summary["cases"]), "output": str(args.output),
                      "quality": quality["status"], "checks_passed": quality["checks_passed"],
                      "checks_total": quality["checks_total"]}, ensure_ascii=False))
    return 0 if quality["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
