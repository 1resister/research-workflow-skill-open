#!/usr/bin/env python3
"""Independent standard-library verification of polynomial benchmark artifacts.

This checker deliberately does not import the generator. It finds extrema by
recursive polynomial root isolation, rather than the generator's peak constants.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

COEFFICIENTS = {
    "quintic": [0.0, 0.0, 0.0, 10.0, -15.0, 6.0],
    "septic": [0.0, 0.0, 0.0, 0.0, 35.0, -84.0, 70.0, -20.0],
}


def derivative(coefficients):
    return [i * value for i, value in enumerate(coefficients)][1:] or [0.0]


def evaluate(coefficients, value):
    result = 0.0
    for coefficient in reversed(coefficients):
        result = result * value + coefficient
    return result


def roots_in_unit_interval(coefficients):
    """Isolate all real roots on [0, 1] using derivative-separated intervals.

    Polynomials of low degree are sufficient here. A root of even multiplicity
    is found among the derivative's roots; simple roots are bisected on monotone
    intervals. This is a numerical audit, not symbolic proof or interval arithmetic.
    """
    coefficients = list(coefficients)
    while len(coefficients) > 1 and coefficients[-1] == 0:
        coefficients.pop()
    if len(coefficients) <= 1:
        return []
    critical = roots_in_unit_interval(derivative(coefficients))
    knots = sorted({0.0, 1.0, *critical})
    tolerance = 1e-12 * max(1.0, sum(abs(x) for x in coefficients))
    roots = [x for x in knots if abs(evaluate(coefficients, x)) < tolerance]
    for left, right in zip(knots, knots[1:]):
        f_left, f_right = evaluate(coefficients, left), evaluate(coefficients, right)
        if f_left * f_right >= 0:
            continue
        for _ in range(80):
            middle = (left + right) / 2
            f_middle = evaluate(coefficients, middle)
            if f_left * f_middle <= 0:
                right = middle
            else:
                left, f_left = middle, f_middle
        roots.append((left + right) / 2)
    result = []
    for root in sorted(roots):
        if not result or abs(root - result[-1]) > 1e-9:
            result.append(root)
    return result


def polynomial_peak(coefficients):
    candidates = [0.0, 1.0] + roots_in_unit_interval(derivative(coefficients))
    return max(abs(evaluate(coefficients, x)) for x in candidates)


def close(actual, expected, scale=1.0, relative=2e-9):
    return abs(actual - expected) <= relative * max(abs(expected), abs(scale), 1e-12)


def verify_output(input_path, output_path):
    input_data = json.loads(Path(input_path).read_text(encoding="utf-8"))
    output_path = Path(output_path)
    summary = json.loads((output_path / "summary.json").read_text(encoding="utf-8"))
    checks = []

    def check(name, condition, detail=""):
        checks.append({"name": name, "passed": bool(condition), "detail": detail})

    cases = {case["id"]: case for case in input_data["cases"]}
    limits = input_data["limits"]
    expected_pairs = {(case_id, family, mode) for case_id in cases
                      for family in COEFFICIENTS for mode in ("minimum", "common")}
    observed_pairs = set()
    for case_result in summary["cases"]:
        case = cases[case_result["id"]]
        displacement = case["end"] - case["start"]
        distance = abs(displacement)
        independently_required = {}
        for family, base in COEFFICIENTS.items():
            derivatives = [base]
            for _ in range(3):
                derivatives.append(derivative(derivatives[-1]))
            peaks = [polynomial_peak(p) for p in derivatives[1:]]
            terms = [distance * peaks[0] / limits["velocity"],
                     math.sqrt(distance * peaks[1] / limits["acceleration"]),
                     (distance * peaks[2] / limits["jerk"]) ** (1 / 3)]
            independently_required[family] = max(terms)
            result = case_result["families"][family]
            check(f"{case['id']}/{family}/minimal_duration",
                  close(result["minimum_duration_s"], max(terms)),
                  "Extrema from generic derivative-root isolation.")
            for mode in ("minimum", "common"):
                trajectory = result[mode]
                observed_pairs.add((case["id"], family, mode))
                duration = trajectory["duration_s"]
                csv_path = output_path / trajectory["csv"]
                with csv_path.open(encoding="utf-8", newline="") as handle:
                    rows = [{key: float(value) for key, value in row.items()}
                            for row in csv.DictReader(handle)]
                expected_count = 1 if distance == 0 else input_data["samples_per_trajectory"]
                check(f"{case['id']}/{family}/{mode}/sample_count", len(rows) == expected_count)
                endpoint_ok = close(rows[0]["position_m"], case["start"]) and close(rows[-1]["position_m"], case["end"])
                endpoint_ok &= close(rows[0]["time_s"], 0.0) and close(rows[-1]["time_s"], duration)
                endpoint_ok &= all(close(row[name], 0.0) for row in (rows[0], rows[-1])
                                   for name in ("velocity_m_s", "acceleration_m_s2"))
                check(f"{case['id']}/{family}/{mode}/endpoints", endpoint_ok)
                if distance == 0:
                    check(f"{case['id']}/{family}/{mode}/stationary", duration == 0 and all(
                        rows[0][name] == 0 for name in ("velocity_m_s", "acceleration_m_s2", "jerk_m_s3")))
                    continue
                analytical_ok = True
                sampled_ok = True
                ordering_ok = True
                previous_time = -math.inf
                for row in rows:
                    time = row["time_s"]
                    ordering_ok &= previous_time < time <= duration + 1e-12
                    previous_time = time
                    u = time / duration
                    names = ["position_m", "velocity_m_s", "acceleration_m_s2", "jerk_m_s3"]
                    for order, name in enumerate(names):
                        expected = displacement * evaluate(derivatives[order], u) / duration ** order
                        if order == 0:
                            expected += case["start"]
                        scale = max(1.0, abs(case["start"]), abs(case["end"])) if order == 0 else limits[["velocity", "acceleration", "jerk"][order - 1]]
                        analytical_ok &= close(row[name], expected, scale)
                        sampled_ok &= order == 0 or abs(row[name]) <= scale * (1 + 2e-9)
                check(f"{case['id']}/{family}/{mode}/strict_time_order", ordering_ok)
                check(f"{case['id']}/{family}/{mode}/independent_sample_values", analytical_ok)
                check(f"{case['id']}/{family}/{mode}/sampled_limits", sampled_ok)
                actual_peaks = [distance * peak / duration ** order
                                for order, peak in enumerate(peaks, 1)]
                analytic_feasible = all(value <= limit * (1 + 2e-9) for value, limit in zip(
                    actual_peaks, (limits["velocity"], limits["acceleration"], limits["jerk"])))
                check(f"{case['id']}/{family}/{mode}/continuous_interval_limits", analytic_feasible,
                      "All critical points plus endpoints, not only sampled points.")
                recorded_peaks = trajectory["peak_absolute"]
                check(f"{case['id']}/{family}/{mode}/recorded_peaks", all(
                    close(recorded_peaks[name], value) for name, value in zip(
                        ("velocity_m_s", "acceleration_m_s2", "jerk_m_s3"), actual_peaks)))
                if mode == "minimum":
                    shortened = duration * (1 - 1e-6)
                    infeasible = any(distance * peak / shortened ** order > limit for order, (peak, limit)
                                     in enumerate(zip(peaks, (limits["velocity"], limits["acceleration"], limits["jerk"])), 1))
                    check(f"{case['id']}/{family}/shorter_is_infeasible", infeasible,
                          "A 0.0001% shortening must violate at least one limit.")
                jerk_endpoints = [rows[0]["jerk_m_s3"], rows[-1]["jerk_m_s3"]]
                check(f"{case['id']}/{family}/{mode}/endpoint_jerk_policy", all(
                    close(value, 0.0, limits["jerk"]) for value in jerk_endpoints) if family == "septic"
                    else all(abs(value) > 0 for value in jerk_endpoints))
        check(f"{case['id']}/common_duration", close(case_result["common_duration_s"], max(independently_required.values()))
              and all(close(case_result["families"][family]["common"]["duration_s"], case_result["common_duration_s"])
                      for family in COEFFICIENTS))
    check("complete_case_family_mode_coverage", observed_pairs == expected_pairs)
    passed = sum(item["passed"] for item in checks)
    return {"status": "passed" if passed == len(checks) else "failed", "checks_passed": passed,
            "checks_total": len(checks), "method": "Independent coefficient evaluation and derivative-root isolation; floating-point numerical audit, not formal proof.",
            "checks": checks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = verify_output(args.input, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
