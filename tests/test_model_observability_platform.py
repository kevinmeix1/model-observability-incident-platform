from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from model_observability_platform.accelerator_plan import build_accelerator_capacity_plan
from model_observability_platform.chaos import run_chaos_drill
from model_observability_platform.checks import likely_root_cause, run_checks
from model_observability_platform.cloud_migration import build_cloud_migration_plan
from model_observability_platform.cli import demo
from model_observability_platform.cost_observability import build_cost_observability_report
from model_observability_platform.deadline_alerts import build_deadline_alert_plan
from model_observability_platform.device_allocation import build_device_allocation_plan
from model_observability_platform.disaster_recovery import build_disaster_recovery_plan
from model_observability_platform.elastic_workload import build_elastic_workload_plan
from model_observability_platform.gitops_release import build_gitops_plan
from model_observability_platform.governance import build_governance_bundle
from model_observability_platform.identity import build_identity_access_report
from model_observability_platform.incidents import create_incidents
from model_observability_platform.indexed_job_resilience import build_indexed_job_resilience_plan
from model_observability_platform.inference_gateway import build_inference_gateway_plan
from model_observability_platform.io import read_csv, read_json, write_json
from model_observability_platform.kuberay_capacity import build_kuberay_capacity_plan
from model_observability_platform.multikueue_dispatch import build_multikueue_dispatch_plan
from model_observability_platform.network_security import build_network_security_report
from model_observability_platform.orchestration_scorecard import build_orchestration_scorecard
from model_observability_platform.policy_audit import audit_platform_policy
from model_observability_platform.performance_budget import build_performance_budget_report
from model_observability_platform.provisioning_admission import build_provisioning_admission_plan
from model_observability_platform.queue_simulator import build_queue_simulation
from model_observability_platform.release_admission import build_release_admission_decision, evaluate_release_admission
from model_observability_platform.reliability_control import build_reliability_plan, burn_rate
from model_observability_platform.resource_optimizer import build_resource_optimization_report
from model_observability_platform.semantic_telemetry import build_semantic_telemetry_plan
from model_observability_platform.slo import build_slo_report
from model_observability_platform.supply_chain import build_supply_chain_evidence
from model_observability_platform.tenancy import build_tenancy_report
from model_observability_platform.telemetry import generate_window
from model_observability_platform.topology_placement import build_topology_placement_plan
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

    def test_queue_simulation_models_incident_priority(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        manifest = (repo / "kubernetes" / "queue-simulation-policy.yaml").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = build_queue_simulation(root)

            self.assertTrue(report["passed"])
            self.assertGreaterEqual(report["preempted_count"], 1)
            self.assertTrue(any(item["name"] == "incident-critical-root-cause" for item in report["simulation"]["admitted"]))
            self.assertTrue((root / "reports" / "queue_simulation.json").exists())
            self.assertIn("PriorityClass", manifest)
            self.assertIn("ObservabilityQueuePressureHigh", manifest)

    def test_release_admission_freezes_rollouts_during_incidents(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        manifest = (repo / "kubernetes" / "release-admission-policy.yaml").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "reports" / "slo_error_budget.json", {"max_burn_rate": 0.2, "release_freeze": False, "recommended_action": "healthy"})
            write_json(root / "reports" / "performance_budget.json", {"passed": True, "checks": []})
            write_json(root / "reports" / "queue_simulation.json", {"passed": True, "pending_count": 0, "simulation": {"pending": []}})
            write_json(root / "reports" / "governance_evidence_bundle.json", {"release": {"decision": "healthy"}})
            write_json(root / "reports" / "supply_chain_evidence.json", {"artifact_count": 8, "subject": {"attestation_action": "actions/attest@v4"}})
            write_json(root / "reports" / "reliability_control_plan.json", {"recommended_action": "healthy"})
            write_json(root / "reports" / "incident_summary.json", {"open_count": 0, "severity": "low"})

            decision = build_release_admission_decision(root)
            frozen = evaluate_release_admission(
                slo={"max_burn_rate": 100.0, "release_freeze": True, "recommended_action": "freeze_rollouts_and_page"},
                performance={"passed": True, "checks": []},
                queue={"passed": True, "pending_count": 0, "simulation": {"pending": []}},
                governance={"release": {"decision": "incident_review_required"}},
                supply_chain={"artifact_count": 8, "subject": {"attestation_action": "actions/attest@v4"}},
                reliability_plan={"recommended_action": "page_and_freeze_rollouts"},
                incidents={"open_count": 5, "severity": "high"},
            )

            self.assertEqual(decision["decision"]["recommended_action"], "admit_observability_change")
            self.assertFalse(decision["decision"]["unsafe_allow"])
            self.assertEqual(frozen["recommended_action"], "freeze_rollouts_and_page")
            self.assertTrue((root / "reports" / "release_admission_decision.json").exists())
            self.assertIn("ValidatingAdmissionPolicy", manifest)
            self.assertIn("AnalysisTemplate", manifest)
            self.assertIn("ObservabilityAdmissionUnsafeAllow", manifest)

    def test_performance_budget_report_and_prometheus_assets_exist(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        manifest = (repo / "kubernetes" / "performance-budget-policy.yaml").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = demo(root)
            report = build_performance_budget_report(root)
            names = {check["name"] for check in report["checks"]}

            self.assertTrue(result["performance_budget"]["passed"])
            self.assertTrue(report["passed"])
            self.assertIn("incident_creation_seconds", names)
            self.assertIn("failed_check_incident_coverage", names)
            self.assertIn("reliability_action_available", names)
            self.assertTrue((root / "reports" / "performance_budget.json").exists())
            self.assertIn("PrometheusRule", manifest)
            self.assertIn("histogram_quantile", manifest)
            self.assertIn("ObservabilityIncidentCreationBudgetExceeded", manifest)

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
            self.assertIn("immutable_image_digest", passed)
            self.assertIn("no_latest_image_tags", report["failed_checks"])

    def test_trace_report_and_otel_collector_exist(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        collector = (repo / "kubernetes" / "opentelemetry-collector.yaml").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            trace = build_trace_report(tmp)

            self.assertEqual(trace["span_count"], 5)
            self.assertEqual(trace["root_service"], "collector")
            self.assertTrue(any(span["name"] == "incident.dedupe" for span in trace["spans"]))
            ingest_attrs = trace["spans"][0]["attributes"]
            self.assertEqual(ingest_attrs["gen_ai.request.model"], "credit-risk-v2")
            self.assertEqual(ingest_attrs["gen_ai.usage.input_tokens"], 96)
            self.assertTrue(any(span["attributes"].get("incident.severity") == "high" for span in trace["spans"]))
            self.assertTrue((Path(tmp) / "reports" / "trace_report.json").exists())
        for expected in ["kind: ConfigMap", "otlp", "k8sattributes", "memory_limiter", "attributes/semantic_redaction", "gen_ai.input.messages", "incident.payload", "prometheus", "batch"]:
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

    def test_gitops_plan_and_progressive_delivery_assets_exist(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        gitops = (repo / "gitops" / "gitops-promotion.yaml").read_text(encoding="utf-8")

        for expected in ["kind: Application", "kind: AppProject", "AnalysisTemplate", "Rollout", "argocd.argoproj.io/sync-wave"]:
            self.assertIn(expected, gitops)
        with tempfile.TemporaryDirectory() as tmp:
            plan = build_gitops_plan(tmp)

            self.assertEqual(plan["deployment_controller"], "Argo CD")
            self.assertIn("incident SLO", plan["progressive_delivery"])
            self.assertTrue(any("burn-rate" in gate for gate in plan["gates"]))
            self.assertTrue((Path(tmp) / "reports" / "gitops_plan.json").exists())

    def test_disaster_recovery_plan_and_backup_assets_exist(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        dr = (repo / "kubernetes" / "disaster-recovery.yaml").read_text(encoding="utf-8")

        for expected in ["kind: Schedule", "BackupStorageLocation", "VolumeSnapshotClass", "restore-order"]:
            self.assertIn(expected, dr)
        with tempfile.TemporaryDirectory() as tmp:
            plan = build_disaster_recovery_plan(tmp)

            self.assertLessEqual(plan["rpo_minutes"], 15)
            self.assertEqual(plan["restore_sequence"][0]["asset"], "namespace and observability CRDs")
            self.assertTrue(any(item["asset"] == "incident records" for item in plan["restore_sequence"]))
            self.assertTrue((Path(tmp) / "reports" / "disaster_recovery_plan.json").exists())

    def test_governance_evidence_bundle_and_kubernetes_assets_exist(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        governance = (repo / "kubernetes" / "governance-evidence.yaml").read_text(encoding="utf-8")

        for expected in ["kind: ConfigMap", "kind: Job", "model-card", "risk-register", "reproducibility-manifest"]:
            self.assertIn(expected, governance)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = demo(root)
            bundle = build_governance_bundle(root)
            approval = read_json(root / "governance" / "approval_record.json")
            manifest = read_json(root / "governance" / "reproducibility_manifest.json")

            self.assertEqual(result["governance_bundle"]["release"]["decision"], "incident_review_required")
            self.assertEqual(bundle["release"]["system_name"], "model-observability-policy")
            self.assertEqual(approval["severity"], "high")
            self.assertTrue(any(item["exists"] and len(item["sha256"]) == 64 for item in manifest["artifact_hashes"]))
            self.assertTrue((root / "reports" / "governance_evidence_bundle.json").exists())

    def test_slo_error_budget_report_and_alert_assets_exist(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        alerts = (repo / "kubernetes" / "slo-alerts.yaml").read_text(encoding="utf-8")

        for expected in ["PrometheusRule", "SLOBurnRateHigh", "multiwindow", "error-budget-freeze"]:
            self.assertIn(expected, alerts)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = demo(root)
            report = build_slo_report(root)

            self.assertEqual(result["slo_error_budget"]["recommended_action"], "freeze_rollouts_and_page")
            self.assertEqual(report["slos"][0]["name"], "observed_serving_availability")
            self.assertEqual(report["reliability_action"], "page_and_freeze_rollouts")
            self.assertTrue((root / "reports" / "slo_error_budget.json").exists())

    def test_cloud_migration_plan_and_infra_assets_exist(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        nodepools = (repo / "kubernetes" / "cloud-nodepools.yaml").read_text(encoding="utf-8")
        terraform = (repo / "infra" / "terraform" / "aws" / "main.tf").read_text(encoding="utf-8")

        for expected in ["NodePool", "EC2NodeClass", "WhenEmptyOrUnderutilized"]:
            self.assertIn(expected, nodepools)
        for expected in ["cluster_compute_config", "node_pools", "aws_s3_bucket"]:
            self.assertIn(expected, terraform)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = demo(root)
            plan = build_cloud_migration_plan(root)

            self.assertEqual(result["cloud_migration"]["primary_target"], "AWS EKS Auto Mode")
            self.assertEqual(plan["managed_service_mapping"]["monitoring"], "Amazon Managed Service for Prometheus and Grafana")
            self.assertTrue((root / "reports" / "cloud_migration_plan.json").exists())

    def test_ci_workflow_uploads_artifacts_and_validates_outputs(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        workflow = (repo / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        makefile = (repo / "Makefile").read_text(encoding="utf-8")

        for expected in ["actions/upload-artifact@v6", "actions/attest@v4", "attestations: write", "GITHUB_STEP_SUMMARY", "make ci-verify", "concurrency"]:
            self.assertIn(expected, workflow)
        for expected in ["ci-verify:", "index.html", "tenancy_fairness_report.json", "identity_access_report.json", "multikueue_dispatch_plan.json", "provisioning_admission_plan.json", "indexed_job_resilience_plan.json", "elastic_workload_plan.json", "cost_observability_report.json", "deadline_alert_plan.json", "semantic_telemetry_plan.json", "inference_gateway_plan.json", "kuberay_capacity_plan.json", "topology_placement_plan.json", "release_admission_decision.json", "queue_simulation.json", "performance_budget.json", "device_allocation_plan.json", "accelerator_capacity_plan.json", "orchestration_scorecard.json", "supply_chain_evidence.json", "governance_evidence_bundle.json", "cloud_migration_plan.json"]:
            self.assertIn(expected, makefile)

    def test_accelerator_capacity_plan_and_kubernetes_assets_exist(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        manifest = (repo / "kubernetes" / "accelerator-scheduling.yaml").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = build_accelerator_capacity_plan(root, project="Model Observability Incident Platform", primary_workload="observability")

            self.assertEqual(len(plan["profiles"]), 3)
            self.assertIn("gpu-a100-mig", {profile["kueue_flavor"] for profile in plan["profiles"]})
            self.assertTrue((root / "reports" / "accelerator_capacity_plan.json").exists())
            self.assertIn("ResourceFlavor", manifest)
            self.assertIn("ResourceClaimTemplate", manifest)
            self.assertIn("nvidia.com/mig-1g.10gb", manifest)

    def test_device_allocation_plan_and_dra_assets_exist(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        manifest = (repo / "kubernetes" / "dynamic-resource-allocation.yaml").read_text(encoding="utf-8")
        docs = (repo / "docs" / "dynamic-resource-allocation.md").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = build_device_allocation_plan(root)

            self.assertTrue(report["passed"])
            self.assertEqual(report["recommended_action"], "admit_dra_backed_diagnostics")
            self.assertTrue(any(workload["resource_claim_template"] == "l4-shared-drift" for workload in report["workloads"]))
            self.assertTrue(any(not workload["requires_dra"] for workload in report["workloads"]))
            self.assertTrue((root / "reports" / "device_allocation_plan.json").exists())
            for expected in ["DeviceClass", "ResourceClaimTemplate", "CronJob", "incident-root-cause-probe", "kueue.x-k8s.io/queue-name", "kube_resourceclaim_status_phase"]:
                self.assertIn(expected, manifest)
            for expected in ["Dynamic Resource Allocation", "time-slicing", "MIG", "CPU fallback", "ResourceClaim"]:
                self.assertIn(expected, docs)

    def test_topology_placement_plan_and_kubernetes_assets_exist(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        manifest = (repo / "kubernetes" / "topology-aware-scheduling.yaml").read_text(encoding="utf-8")
        docs = (repo / "docs" / "topology-aware-scheduling.md").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = build_topology_placement_plan(root)

            self.assertTrue(report["passed"])
            self.assertEqual(report["recommended_action"], "enable_topology_aware_diagnostics")
            self.assertTrue((root / "reports" / "topology_placement_plan.json").exists())
            self.assertTrue(any(workload["queue"] == "incident-critical-queue" for workload in report["workloads"]))
        for expected in ["kind: Topology", "topologyName", "kueue.x-k8s.io/podset-preferred-topology", "topologySpreadConstraints", "ObservabilityTopologyAssignmentDelayed"]:
            self.assertIn(expected, manifest)
        for expected in ["Topology-Aware Scheduling", "topology spread constraints", "AdmissionChecks", "incident"]:
            self.assertIn(expected, docs)

    def test_kuberay_capacity_plan_and_kubernetes_assets_exist(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        manifest = (repo / "kubernetes" / "kuberay-kueue-workloads.yaml").read_text(encoding="utf-8")
        docs = (repo / "docs" / "kuberay-kueue.md").read_text(encoding="utf-8")
        dag = (repo / "airflow" / "dags" / "model_reliability_control_plane_dag.py").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = build_kuberay_capacity_plan(root)

            self.assertTrue(report["passed"])
            self.assertEqual(report["recommended_action"], "enable_kuberay_incident_fanout")
            self.assertTrue((root / "reports" / "kuberay_capacity_plan.json").exists())
            self.assertEqual(report["capacity"]["max_gpu_demand"], 6)
        for expected in ["RayJob", "enableInTreeAutoscaling", "kueue.x-k8s.io/elastic-job", "incident-root-cause-fanout", "ObservabilityRayIncidentFanoutDelayed"]:
            self.assertIn(expected, manifest)
        for expected in ["KubeRay", "Kueue", "incident", "GPU"]:
            self.assertIn(expected, docs)
        for expected in ["submit_kuberay_incident_fanout", "wait_for_kuberay_incident_fanout_deferrable", "rayjob/incident-root-cause-fanout"]:
            self.assertIn(expected, dag)

    def test_inference_gateway_plan_and_kubernetes_assets_exist(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        manifest = (repo / "kubernetes" / "inference-gateway-routing.yaml").read_text(encoding="utf-8")
        docs = (repo / "docs" / "inference-gateway.md").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = build_inference_gateway_plan(root)

            self.assertTrue(report["passed"])
            self.assertEqual(report["recommended_action"], "monitor_inference_gateway_objectives")
            self.assertTrue(any(signal == "endpoint_picker_up" for signal in report["signals"]))
            self.assertTrue((root / "reports" / "inference_gateway_plan.json").exists())
        for expected in ["InferencePool", "InferenceObjective", "endpointPickerRef", "FailOpen", "HTTPRoute", "ObservedEndpointPickerUnavailable"]:
            self.assertIn(expected, manifest)
        for expected in ["Gateway API Inference Extension", "InferencePool", "Endpoint Picker", "incident"]:
            self.assertIn(expected, docs)

    def test_semantic_telemetry_plan_and_collector_assets_exist(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        collector = (repo / "kubernetes" / "opentelemetry-collector.yaml").read_text(encoding="utf-8")
        docs = (repo / "docs" / "semantic-telemetry.md").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = build_semantic_telemetry_plan(root)

            self.assertTrue(report["passed"])
            self.assertEqual(report["recommended_action"], "enforce_semantic_telemetry_contract")
            self.assertIn("incident.root_cause", report["schema"]["required_attributes"])
            self.assertIn("gen_ai.input.messages", report["schema"]["redacted_attributes"])
            self.assertTrue((root / "reports" / "semantic_telemetry_plan.json").exists())
        for expected in ["attributes/semantic_redaction", "deployment.environment.name", "incident.routing.mode", "gen_ai.output.messages"]:
            self.assertIn(expected, collector)
        for expected in ["Semantic Telemetry", "GenAI-style", "payload", "incident"]:
            self.assertIn(expected, docs)

    def test_airflow_deadline_alert_plan_and_docs_exist(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        docs = (repo / "docs" / "airflow-deadline-alerts.md").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = build_deadline_alert_plan(root)

            self.assertTrue(report["passed"])
            self.assertEqual(report["recommended_action"], "enable_airflow3_observability_deadline_alerts")
            self.assertEqual(report["runtime_config"]["AIRFLOW__CALLBACKS__CALLBACK_EXECUTION_TIMEOUT"], "300")
            self.assertTrue(any(policy["name"] == "incident_creation_latency" for policy in report["deadline_policies"]))
            self.assertTrue((root / "reports" / "deadline_alert_plan.json").exists())
        for expected in ["Deadline Alerts", "legacy Airflow 2 SLA", "incident", "freshness"]:
            self.assertIn(expected, docs)

    def test_cost_observability_report_and_opencost_assets_exist(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        manifest = (repo / "kubernetes" / "opencost-finops.yaml").read_text(encoding="utf-8")
        docs = (repo / "docs" / "cost-observability.md").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = build_cost_observability_report(root)

            self.assertTrue(report["passed"])
            self.assertEqual(report["recommended_action"], "enable_observability_opencost_guardrails")
            self.assertIn("cost_per_high_severity_incident_detected", report["unit_economics"]["primary_kpi"])
            self.assertTrue(any(item["incident_path"] == "diagnostics" for item in report["observability_budgets"]))
            self.assertTrue((root / "reports" / "cost_observability_report.json").exists())
        for expected in ["PrometheusRule", "opencost", "ObservabilityIncidentFanoutCostHigh", "ObservabilityIdleGpuDiagnosticSpend", "label_severity"]:
            self.assertIn(expected, manifest)
        for expected in ["OpenCost", "incident", "ResourceQuota", "GPU"]:
            self.assertIn(expected, docs)

    def test_elastic_workload_plan_and_jobset_assets_exist(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        manifest = (repo / "kubernetes" / "kueue-elastic-workloads.yaml").read_text(encoding="utf-8")
        docs = (repo / "docs" / "kueue-elastic-workloads.md").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = build_elastic_workload_plan(root)

            self.assertTrue(report["passed"])
            self.assertEqual(report["recommended_action"], "enable_kueue_elastic_incident_slices")
            self.assertEqual(report["feature_gate"], "ElasticJobsViaWorkloadSlices")
            self.assertTrue(any(item["replacement_for"] for item in report["workload_slices"]))
            self.assertTrue((root / "reports" / "elastic_workload_plan.json").exists())
        for expected in ["JobSet", "workload-slice-name", "workload-slice-replacement-for", "ObservabilityElasticWorkloadSlicePending"]:
            self.assertIn(expected, manifest)
        for expected in ["Elastic Workloads", "Workload Slices", "JobSet", "rollback"]:
            self.assertIn(expected, docs)

    def test_indexed_job_resilience_plan_and_kubernetes_assets_exist(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        manifest = (repo / "kubernetes" / "indexed-job-resilience.yaml").read_text(encoding="utf-8")
        docs = (repo / "docs" / "indexed-job-resilience.md").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = build_indexed_job_resilience_plan(root)

            self.assertTrue(report["passed"])
            self.assertEqual(report["recommended_action"], "enable_indexed_observability_job_resilience")
            self.assertEqual(report["kubernetes_job"]["completion_mode"], "Indexed")
            self.assertEqual(report["retry_policy"]["backoff_limit_per_index"], 1)
            self.assertTrue(any(item["stage"] == "rollback_freeze" for item in report["incident_shards"]))
            self.assertTrue((root / "reports" / "indexed_job_resilience_plan.json").exists())
        for expected in ["completionMode: Indexed", "backoffLimitPerIndex", "maxFailedIndexes", "successPolicy", "podFailurePolicy", "JOB_COMPLETION_INDEX", "ObservabilityIndexedJobFailedIndexesHigh"]:
            self.assertIn(expected, manifest)
        for expected in ["Indexed Job Resilience", "Airflow Backfill Create", "successPolicy", "podFailurePolicy", "backoffLimitPerIndex"]:
            self.assertIn(expected, docs)

    def test_provisioning_admission_plan_and_kubernetes_assets_exist(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        manifest = (repo / "kubernetes" / "provisioning-admission-checks.yaml").read_text(encoding="utf-8")
        docs = (repo / "docs" / "provisioning-admission.md").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = build_provisioning_admission_plan(root)

            self.assertTrue(report["passed"])
            self.assertEqual(report["recommended_action"], "enable_kueue_provisioning_admission_for_incidents")
            self.assertTrue(report["incident_policy"]["fresh_incidents_before_backfills"])
            self.assertTrue(any(check["name"] == "incident_path_prioritized" for check in report["checks"]))
            self.assertTrue((root / "reports" / "provisioning_admission_plan.json").exists())
        for expected in ["AdmissionCheck", "ProvisioningRequestConfig", "kueue.x-k8s.io/provisioning-request", "admissionChecksStrategy", "check-capacity.autoscaling.x-k8s.io", "podSetUpdates", "ObservabilityProvisioningAdmissionPendingTooLong"]:
            self.assertIn(expected, manifest)
        for expected in ["Kueue Provisioning Admission", "ProvisioningRequest", "Cluster Autoscaler", "incident"]:
            self.assertIn(expected, docs)

    def test_multikueue_dispatch_plan_and_kubernetes_assets_exist(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        manifest = (repo / "kubernetes" / "multikueue-dispatch.yaml").read_text(encoding="utf-8")
        docs = (repo / "docs" / "multikueue-dispatch.md").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = build_multikueue_dispatch_plan(root)

            self.assertTrue(report["passed"])
            self.assertEqual(report["recommended_action"], "enable_multikueue_incident_dispatch")
            self.assertTrue(report["incident_policy"]["fresh_incidents_before_backfills"])
            self.assertEqual(report["incident_policy"]["missing_worker_assignment_action"], "freeze_repair_automation_and_keep_rollout_freeze")
            self.assertEqual(report["manager_quota"]["nvidia_com_gpu"], 2)
            self.assertIn("status.clusterName", report["dispatch_policy"]["status_fields"])
            self.assertTrue(any(check["name"] == "repair_automation_waits_for_dispatch" for check in report["checks"]))
            self.assertTrue((root / "reports" / "multikueue_dispatch_plan.json").exists())
        for expected in ["MultiKueueConfig", "MultiKueueCluster", "kueue.x-k8s.io/multikueue", "admissionChecksStrategy", "fresh-incident-diagnostics", "kueue.x-k8s.io/prebuilt-workload-name", "ObservabilityMultiKueueDispatchStalled"]:
            self.assertIn(expected, manifest)
        for expected in ["MultiKueue Incident Dispatch", "fresh incident", "status.clusterName", "repair automation"]:
            self.assertIn(expected, docs)

    def test_tenancy_fairness_report_and_kubernetes_assets_exist(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        manifest = (repo / "kubernetes" / "multitenancy-fairness.yaml").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = build_tenancy_report(root)
            tenant_names = {tenant["name"] for tenant in report["tenants"]}

            self.assertTrue(report["passed"])
            self.assertIn("incident-response", tenant_names)
            self.assertIn("ml-observability-cohort", report["fairness"]["cohort"])
            self.assertTrue((root / "reports" / "tenancy_fairness_report.json").exists())
            for expected in ["ResourceQuota", "LimitRange", "RoleBinding", "NetworkPolicy", "Cohort", "ClusterQueue", "airflow-tenant-pools"]:
                self.assertIn(expected, manifest)

    def test_identity_access_report_and_kubernetes_assets_exist(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        manifest = (repo / "kubernetes" / "workload-identity.yaml").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = build_identity_access_report(root)
            service_accounts = {identity["service_account"] for identity in report["identities"]}

            self.assertTrue(report["passed"])
            self.assertIn("drift-evaluator", service_accounts)
            self.assertTrue((root / "reports" / "identity_access_report.json").exists())
            for expected in ["ServiceAccount", "automountServiceAccountToken: false", "SecretStore", "ExternalSecret", "refreshInterval: 30m", "eks.amazonaws.com/role-arn", "spiffe.io/spiffe-id", "airflow-workload-identity-policy"]:
                self.assertIn(expected, manifest)

    def test_orchestration_scorecard_covers_advanced_controls(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scorecard = build_orchestration_scorecard(root, repo_root=repo, project="Model Observability Incident Platform")
            names = {check["name"] for check in scorecard["checks"] if check["passed"]}

            self.assertTrue(scorecard["passed"])
            self.assertGreaterEqual(scorecard["score"], 90.0)
            self.assertIn("dynamic_task_mapping", names)
            self.assertIn("kueue_admission", names)
            self.assertIn("semantic_telemetry_contract", names)
            self.assertIn("airflow_deadline_alerts", names)
            self.assertIn("opencost_finops", names)
            self.assertIn("kueue_elastic_workloads", names)
            self.assertIn("indexed_job_resilience", names)
            self.assertIn("provisioning_admission_checks", names)
            self.assertIn("multikueue_dispatch", names)
            self.assertIn("supply_chain_provenance", names)
            self.assertTrue((root / "reports" / "orchestration_scorecard.json").exists())

    def test_supply_chain_evidence_and_policy_assets_exist(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        policy = (repo / "kubernetes" / "supply-chain-policy.yaml").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "reports" / "demo.json", {"status": "ok"})
            evidence = build_supply_chain_evidence(
                root,
                project="Model Observability Incident Platform",
                artifact_name="model-observability-demo-artifacts",
                workflow="Model Observability CI",
                namespace="mlops-observability",
            )

            self.assertEqual(evidence["artifact_count"], 1)
            self.assertEqual(len(evidence["artifacts"][0]["sha256"]), 64)
            self.assertEqual(evidence["subject"]["attestation_action"], "actions/attest@v4")
            self.assertTrue((root / "supply-chain" / "subject.checksums.txt").exists())
            self.assertIn("ClusterImagePolicy", policy)
            self.assertIn("predicateType: https://slsa.dev/provenance/v1", policy)
            self.assertIn("policy.sigstore.dev/include", policy)

    def test_artifact_index_links_key_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = demo(root)
            index = (root / "reports" / "index.html").read_text(encoding="utf-8")

            self.assertTrue(result["artifact_index"].endswith("index.html"))
            for expected in [
                "model_observability_dashboard.html",
                "incident_summary.json",
                "reliability_control_plan.json",
                "governance_evidence_bundle.json",
                "slo_error_budget.json",
                "accelerator_capacity_plan.json",
                "device_allocation_plan.json",
                "topology_placement_plan.json",
                "kuberay_capacity_plan.json",
                "inference_gateway_plan.json",
                "semantic_telemetry_plan.json",
                "deadline_alert_plan.json",
                "cost_observability_report.json",
                "elastic_workload_plan.json",
                "indexed_job_resilience_plan.json",
                "provisioning_admission_plan.json",
                "multikueue_dispatch_plan.json",
                "tenancy_fairness_report.json",
                "identity_access_report.json",
                "performance_budget.json",
                "queue_simulation.json",
                "release_admission_decision.json",
                "resource_optimization.json",
                "network_security.json",
                "chaos_drill_report.json",
                "gitops_plan.json",
                "orchestration_scorecard.json",
                "supply_chain_evidence.json",
                "cloud_migration_plan.json",
            ]:
                self.assertIn(expected, index)

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
            self.assertTrue((root / "reports" / "index.html").exists())
            self.assertTrue((root / "reports" / "accelerator_capacity_plan.json").exists())
            self.assertTrue((root / "reports" / "device_allocation_plan.json").exists())
            self.assertTrue((root / "reports" / "topology_placement_plan.json").exists())
            self.assertTrue((root / "reports" / "kuberay_capacity_plan.json").exists())
            self.assertTrue((root / "reports" / "inference_gateway_plan.json").exists())
            self.assertTrue((root / "reports" / "semantic_telemetry_plan.json").exists())
            self.assertTrue((root / "reports" / "deadline_alert_plan.json").exists())
            self.assertTrue((root / "reports" / "cost_observability_report.json").exists())
            self.assertTrue((root / "reports" / "elastic_workload_plan.json").exists())
            self.assertTrue((root / "reports" / "indexed_job_resilience_plan.json").exists())
            self.assertTrue((root / "reports" / "multikueue_dispatch_plan.json").exists())
            self.assertTrue((root / "reports" / "tenancy_fairness_report.json").exists())
            self.assertTrue((root / "reports" / "identity_access_report.json").exists())
            self.assertTrue((root / "reports" / "performance_budget.json").exists())
            self.assertTrue((root / "reports" / "queue_simulation.json").exists())
            self.assertTrue((root / "reports" / "release_admission_decision.json").exists())
            self.assertTrue((root / "reports" / "orchestration_scorecard.json").exists())
            self.assertTrue((root / "reports" / "supply_chain_evidence.json").exists())

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
