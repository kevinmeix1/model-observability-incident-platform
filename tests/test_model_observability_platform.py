from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from model_observability_platform.chaos import run_chaos_drill
from model_observability_platform.checks import likely_root_cause, run_checks
from model_observability_platform.cli import demo
from model_observability_platform.incidents import create_incidents
from model_observability_platform.io import read_csv, write_json
from model_observability_platform.network_security import build_network_security_report
from model_observability_platform.policy_audit import audit_platform_policy
from model_observability_platform.reliability_control import build_reliability_plan, burn_rate
from model_observability_platform.resource_optimizer import build_resource_optimization_report
from model_observability_platform.telemetry import generate_window
from model_observability_platform.traceability import build_trace_report


class ModelObservabilityPlatformTest(unittest.TestCase):
    def test_advanced_observability_control_plane_assets_exist(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        dag = repo / "airflow" / "dags" / "model_reliability_control_plane_dag.py"
        workloads = repo / "kubernetes" / "observability-control-plane.yaml"

        dag_text = dag.read_text(encoding="utf-8")
        workload_text = workloads.read_text(encoding="utf-8")

        for expected in ["KubernetesPodOperator", "task_group", "BranchPythonOperator", "Asset", "expand("]:
            self.assertIn(expected, dag_text)
        for expected in ["deferrable=True", "pod_template_file", "slo_budget_and_capacity", "reserve_kueue_observability_quota"]:
            self.assertIn(expected, dag_text)
        for expected in ["CronJob", "RoleBinding", "ConfigMap", "PSI_THRESHOLD", "securityContext", "kueue.x-k8s.io/queue-name"]:
            self.assertIn(expected, workload_text)

    def test_kubernetes_governance_and_airflow_pod_template_exist(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        governance = (repo / "kubernetes" / "platform-governance.yaml").read_text(encoding="utf-8")
        pod_template = (repo / "kubernetes" / "airflow-kubernetes-executor-pod-template.yaml").read_text(encoding="utf-8")

        for expected in ["ResourceQuota", "LimitRange", "PriorityClass", "HTTPRoute"]:
            self.assertIn(expected, governance)
        for expected in ["initContainers", "topologySpreadConstraints", "securityContext", "envFrom"]:
            self.assertIn(expected, pod_template)

    def test_kueue_observability_admission_assets_exist(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        admission = (repo / "kubernetes" / "kueue-admission-control.yaml").read_text(encoding="utf-8")

        for expected in [
            "ResourceFlavor",
            "ClusterQueue",
            "LocalQueue",
            "WorkloadPriorityClass",
            "observability-checks-queue",
            "incident-critical",
            "borrowingLimit",
            "preemption",
            "kueue.x-k8s.io/queue-name",
        ]:
            self.assertIn(expected, admission)

    def test_event_driven_autoscaling_assets_exist(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        autoscaling = (repo / "kubernetes" / "event-driven-autoscaling.yaml").read_text(encoding="utf-8")

        for expected in ["ScaledJob", "kafka", "lagThreshold", "limitToPartitionsWithLag", "observability-checks-queue"]:
            self.assertIn(expected, autoscaling)

    def test_admission_policies_and_policy_audit_exist(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        admission = (repo / "kubernetes" / "admission-policies.yaml").read_text(encoding="utf-8")

        for expected in ["ValidatingAdmissionPolicy", "ValidatingAdmissionPolicyBinding", "ImageValidatingPolicy", "slsa-provenance"]:
            self.assertIn(expected, admission)
        with tempfile.TemporaryDirectory() as tmp:
            report = audit_platform_policy(repo, output_root=tmp)
            passed = {check["name"] for check in report["checks"] if check["passed"]}
            self.assertIn("incident_priority", passed)
            self.assertIn("event_driven_scaling", passed)
            self.assertIn("no_latest_image_tags", report["failed_checks"])
            self.assertIn("immutable_image_digest", report["failed_checks"])

    def test_trace_report_and_otel_collector_exist(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        collector = (repo / "kubernetes" / "opentelemetry-collector.yaml").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            trace = build_trace_report(tmp)

            self.assertEqual(trace["span_count"], 5)
            self.assertEqual(trace["root_service"], "collector")
            self.assertTrue(any(span["name"] == "incident.dedupe" for span in trace["spans"]))
            self.assertTrue((Path(tmp) / "reports" / "trace_report.json").exists())
        for expected in ["kind: ConfigMap", "otlp", "k8sattributes", "memory_limiter", "prometheus", "batch"]:
            self.assertIn(expected, collector)

    def test_chaos_drill_and_chaos_mesh_assets_exist(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        chaos_manifest = (repo / "kubernetes" / "chaos-experiments.yaml").read_text(encoding="utf-8")

        for expected in ["PodChaos", "NetworkChaos", "StressChaos", "Schedule", "concurrencyPolicy: Forbid", "observability-collector-pod-kill"]:
            self.assertIn(expected, chaos_manifest)
        with tempfile.TemporaryDirectory() as tmp:
            report = run_chaos_drill(tmp)

            self.assertTrue(report["passed"])
            self.assertEqual(report["scenario_count"], 3)
            self.assertTrue(any(scenario["fault"] == "NetworkChaos" for scenario in report["scenarios"]))
            self.assertTrue((Path(tmp) / "reports" / "chaos_drill_report.json").exists())

    def test_resource_optimization_and_autoscaling_assets_exist(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        optimization = (repo / "kubernetes" / "resource-optimization.yaml").read_text(encoding="utf-8")

        for expected in ["VerticalPodAutoscaler", "HorizontalPodAutoscaler", "PrometheusRule", "airflow-capacity-pools", "stabilizationWindowSeconds: 300"]:
            self.assertIn(expected, optimization)
        with tempfile.TemporaryDirectory() as tmp:
            report = build_resource_optimization_report(tmp)

            self.assertEqual(report["summary"]["workload_count"], 3)
            self.assertIn("incident creation", " ".join(report["guardrails"]))
            self.assertTrue(any("prewarm_replicas" in item["actions"] for item in report["recommendations"]))
            self.assertTrue((Path(tmp) / "reports" / "resource_optimization.json").exists())

    def test_network_security_topology_and_manifests_exist(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        network_security = (repo / "kubernetes" / "network-security.yaml").read_text(encoding="utf-8")

        for expected in ["kind: NetworkPolicy", "default-deny-all", "PeerAuthentication", "mode: STRICT", "AuthorizationPolicy"]:
            self.assertIn(expected, network_security)
        with tempfile.TemporaryDirectory() as tmp:
            report = build_network_security_report(tmp)

            self.assertEqual(report["mtls_mode"], "STRICT")
            self.assertEqual(report["allowed_flow_count"], 3)
            self.assertTrue(any(flow["destination"] == "telemetry-collector" for flow in report["allowed_flows"]))
            self.assertTrue((Path(tmp) / "reports" / "network_security.json").exists())

    def test_reliability_control_escalates_high_burn_incident(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(
                root / "reports" / "observability_report.json",
                {
                    "checks": [
                        {"name": "error_rate", "passed": False, "observed": 0.04},
                        {"name": "latency_slo", "passed": False, "observed": 120.0},
                    ]
                },
            )
            write_json(root / "reports" / "incident_summary.json", {"open_count": 4, "severity": "high"})

            plan = build_reliability_plan(root)

            self.assertGreaterEqual(burn_rate(0.04), 8.0)
            self.assertEqual(plan["recommended_action"], "page_and_freeze_rollouts")
            self.assertIn("rollback_decision", plan["impacted_assets"])

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
