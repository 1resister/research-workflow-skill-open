"""Behavioral regression tests; standard-library unittest, no network access."""
from __future__ import annotations

import copy
import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = [ROOT, *sorted((ROOT / "skills").glob("*"))] if (ROOT / "skills").exists() else [ROOT]
SKILL_ROOT = next(path for path in CANDIDATES if (path / "scripts" / "trajectory_benchmark.py").is_file())
sys.path.insert(0, str(SKILL_ROOT / "scripts"))
import trajectory_benchmark as benchmark
import verify_trajectory as verifier


def input_data():
    return json.loads((SKILL_ROOT / "assets" / "trajectory-input.json").read_text(encoding="utf-8"))


class AnalyticBehavior(unittest.TestCase):
    def test_independent_stationary_point_peak_values(self):
        # Independent coefficient root isolation must agree with derived constants.
        expected = {"quintic": (1.875, 5.773502691896258, 60),
                    "septic": (2.1875, 7.513188404399293, 52.5)}
        for family, constants in expected.items():
            polynomial = verifier.COEFFICIENTS[family]
            for expected_peak in constants:
                polynomial = verifier.derivative(polynomial)
                self.assertAlmostEqual(verifier.polynomial_peak(polynomial), expected_peak, places=10)

    def test_septic_negative_jerk_is_global_absolute_peak(self):
        self.assertEqual(benchmark.shape("septic", .5)[3], -52.5)
        self.assertAlmostEqual(benchmark.shape("septic", (5 - math.sqrt(15)) / 10)[3], 42.0)
        self.assertGreater(abs(benchmark.shape("septic", .5)[3]), 42.0)

    def test_known_limit_regimes_and_minimality(self):
        limits = {"velocity": .5, "acceleration": 1., "jerk": 20.}
        cases = [(0.001, "jerk_s"), (0.1, "acceleration_s"), (1., "velocity_s")]
        for distance, expected_constraint in cases:
            for family in benchmark.FAMILIES:
                terms = benchmark.duration_components(family, distance, limits)
                duration = max(terms.values())
                self.assertEqual(max(terms, key=terms.get), expected_constraint)
                shortened = duration * (1 - 1e-5)
                peaks = benchmark.peak_values(family, distance, shortened)
                self.assertTrue(any(value > limit for value, limit in zip(peaks.values(), limits.values())))

    def test_rest_endpoints_and_jerk_continuity_policy(self):
        for family in benchmark.FAMILIES:
            self.assertEqual(benchmark.shape(family, 0)[:3], (0, 0, 0))
            self.assertEqual(benchmark.shape(family, 1)[:3], (1, 0, 0))
        self.assertEqual(benchmark.shape("quintic", 0)[3], 60)
        self.assertEqual(benchmark.shape("quintic", 1)[3], 60)
        self.assertEqual(benchmark.shape("septic", 0)[3], 0)
        self.assertEqual(benchmark.shape("septic", 1)[3], 0)

    def test_signed_motion_symmetry_and_zero_displacement(self):
        for family in benchmark.FAMILIES:
            positive = benchmark.trajectory_rows(family, {"start": 0., "end": .1}, 1., 101)
            negative = benchmark.trajectory_rows(family, {"start": .2, "end": .1}, 1., 101)
            for forward, reverse in zip(positive, negative):
                self.assertAlmostEqual(forward["position_m"] + reverse["position_m"], .2)
                for column in ("velocity_m_s", "acceleration_m_s2", "jerk_m_s3"):
                    self.assertAlmostEqual(forward[column], -reverse[column])
            still = benchmark.trajectory_rows(family, {"start": .1, "end": .1}, 0., 101)
            self.assertEqual(len(still), 1)
            self.assertEqual(still[0]["position_m"], .1)
            self.assertEqual(still[0]["jerk_m_s3"], 0)

    def test_derivative_relations_by_central_difference(self):
        # Evaluate away from joins; this must not hide quintic's endpoint jerk jump.
        step = 1e-5
        for family in benchmark.FAMILIES:
            for u in (.13, .37, .71, .89):
                left, middle, right = (benchmark.shape(family, value) for value in (u-step, u, u+step))
                for order in range(3):
                    numeric = (right[order] - left[order]) / (2 * step)
                    self.assertAlmostEqual(numeric, middle[order+1], delta=1e-6)

    def test_invalid_inputs_are_rejected(self):
        base = input_data()
        invalid = []
        for value in (0, -1, float("inf"), float("nan"), True):
            data = copy.deepcopy(base)
            data["limits"]["velocity"] = value
            invalid.append(data)
        data = copy.deepcopy(base)
        data["units"]["position"] = "mm"
        invalid.append(data)
        data = copy.deepcopy(base)
        data["cases"][0]["id"] = "../escape"
        invalid.append(data)
        data = copy.deepcopy(base)
        data["cases"][1]["id"] = data["cases"][0]["id"]
        invalid.append(data)
        for data in invalid:
            with self.assertRaises(ValueError):
                benchmark.validate_input(data)


class ArtifactBehavior(unittest.TestCase):
    def setUp(self):
        test_work = ROOT / "work" / "test-temporary-files"
        test_work.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=test_work)
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.input = self.directory / "input.json"
        # Keep an end-to-end test small while retaining all three constraint regimes.
        self.data = input_data()
        self.data["samples_per_trajectory"] = 101
        self.input.write_text(json.dumps(self.data), encoding="utf-8")
        self.output = self.directory / "result"

    def test_cli_and_independent_audit_and_manifest(self):
        completed = subprocess.run([sys.executable, str(SKILL_ROOT / "scripts" / "trajectory_benchmark.py"),
                                    "--input", str(self.input), "--output", str(self.output)],
                                   check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(completed.stdout)["quality"], "passed")
        independent = verifier.verify_output(self.input, self.output)
        self.assertEqual(independent["status"], "passed")
        manifest = json.loads((self.output / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["original_input_sha256"], hashlib.sha256(self.input.read_bytes()).hexdigest())
        for relative, detail in manifest["outputs"].items():
            self.assertEqual(detail["sha256"], hashlib.sha256((self.output / relative).read_bytes()).hexdigest())
        for name in ("duration-comparison.svg", "equal-duration-profiles.svg"):
            self.assertEqual(ET.parse(self.output / name).getroot().tag, "{http://www.w3.org/2000/svg}svg")

    def test_audit_detects_modified_csv(self):
        benchmark.run(self.input, self.output)
        path = self.output / "csv" / "move_1mm-quintic-minimum.csv"
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames, rows = reader.fieldnames, list(reader)
        rows[30]["velocity_m_s"] = "1234.0"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        result = verifier.verify_output(self.input, self.output)
        self.assertEqual(result["status"], "failed")
        failures = [item["name"] for item in result["checks"] if not item["passed"]]
        self.assertTrue(any("independent_sample_values" in item for item in failures))
        self.assertTrue(any("sampled_limits" in item for item in failures))

    def test_audit_detects_missing_case(self):
        benchmark.run(self.input, self.output)
        path = self.output / "summary.json"
        summary = json.loads(path.read_text(encoding="utf-8"))
        summary["cases"].pop()
        path.write_text(json.dumps(summary), encoding="utf-8")
        result = verifier.verify_output(self.input, self.output)
        self.assertEqual(result["status"], "failed")
        self.assertTrue(any(item["name"] == "complete_case_family_mode_coverage" and not item["passed"]
                            for item in result["checks"]))

    def test_rerun_same_input_is_deterministic_except_manifest_time(self):
        benchmark.run(self.input, self.output)
        first = json.loads((self.output / "manifest.json").read_text(encoding="utf-8"))
        benchmark.run(self.input, self.output)
        second = json.loads((self.output / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(first["outputs"], second["outputs"])

    def test_nonempty_unrelated_output_is_preserved(self):
        self.output.mkdir()
        sentinel = self.output / "user-notes.txt"
        sentinel.write_text("keep me", encoding="utf-8")
        with self.assertRaises(ValueError):
            benchmark.run(self.input, self.output)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep me")

    def test_stationary_only_and_reverse_only_inputs(self):
        for case in ({"id": "stationary", "start": .1, "end": .1},
                     {"id": "reverse", "start": .1, "end": 0.}):
            self.data["cases"] = [case]
            self.input.write_text(json.dumps(self.data), encoding="utf-8")
            _, result = benchmark.run(self.input, self.directory / case["id"])
            self.assertEqual(result["status"], "passed")
            self.assertTrue((self.directory / case["id"] / "equal-duration-profiles.svg").is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
