from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from model_observability_platform.checks import likely_root_cause, run_checks
from model_observability_platform.cli import demo
from model_observability_platform.incidents import create_incidents
from model_observability_platform.io import read_csv
from model_observability_platform.telemetry import generate_window


class ModelObservabilityPlatformTest(unittest.TestCase):
    def test_advanced_observability_control_plane_assets_exist(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        dag = repo / "airflow" / "dags" / "model_reliability_control_plane_dag.py"
        workloads = repo / "kubernetes" / "observability-control-plane.yaml"

        dag_text = dag.read_text(encoding="utf-8")
        workload_text = workloads.read_text(encoding="utf-8")

        for expected in ["KubernetesPodOperator", "task_group", "BranchPythonOperator", "Asset", "expand("]:
            self.assertIn(expected, dag_text)
        for expected in ["CronJob", "RoleBinding", "ConfigMap", "PSI_THRESHOLD", "securityContext"]:
            self.assertIn(expected, workload_text)

    def test_demo_creates_incidents_and_dashboard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = demo(root)

            self.assertFalse(result["report"]["passed"])
            self.assertGreaterEqual(result["incidents"]["open_count"], 4)
            self.assertTrue((root / "reports" / "model_observability_dashboard.html").exists())

    def test_clean_window_passes_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reference = read_csv(generate_window(root / "reference.csv", window="reference", seed=1))
            current = read_csv(generate_window(root / "current.csv", window="current", rows=620, seed=1))
            report = run_checks(reference, current)

            self.assertTrue(report["passed"])

    def test_drift_and_serving_degradation_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reference = read_csv(generate_window(root / "reference.csv", window="reference"))
            current = read_csv(generate_window(root / "current.csv", window="current", drift=True, errors=True))
            report = run_checks(reference, current)
            failing = {check["name"] for check in report["checks"] if not check["passed"]}

            self.assertIn("feature_drift", failing)
            self.assertIn("prediction_drift", failing)
            self.assertIn("latency_slo", failing)
            self.assertIn("error_rate", failing)

    def test_incident_creation_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reference = read_csv(generate_window(root / "reference.csv", window="reference"))
            current = read_csv(generate_window(root / "current.csv", window="current", drift=True, errors=True))
            report = run_checks(reference, current)

            first = create_incidents(root, report)
            second = create_incidents(root, report)

            self.assertGreater(first["created_count"], 0)
            self.assertEqual(second["created_count"], 0)
            self.assertEqual(first["open_count"], second["open_count"])

    def test_compound_root_cause_is_classified(self) -> None:
        failed = [
            {"name": "feature_drift"},
            {"name": "prediction_drift"},
            {"name": "latency_slo"},
        ]

        self.assertEqual(likely_root_cause(failed), "compound_population_shift_and_serving_degradation")


if __name__ == "__main__":
    unittest.main()
