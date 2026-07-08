from __future__ import annotations

import argparse
import json
from pathlib import Path

from .accelerator_plan import build_accelerator_capacity_plan
from .artifact_index import render_artifact_index
from .chaos import run_chaos_drill
from .checks import run_checks
from .cloud_migration import build_cloud_migration_plan
from .dashboard import render_dashboard
from .device_allocation import build_device_allocation_plan
from .disaster_recovery import build_disaster_recovery_plan
from .gitops_release import build_gitops_plan
from .governance import build_governance_bundle
from .identity import build_identity_access_report
from .incidents import create_incidents
from .inference_gateway import build_inference_gateway_plan
from .io import read_csv, write_json
from .kuberay_capacity import build_kuberay_capacity_plan
from .network_security import build_network_security_report
from .orchestration_scorecard import build_orchestration_scorecard
from .policy_audit import audit_platform_policy
from .performance_budget import build_performance_budget_report
from .queue_simulator import build_queue_simulation
from .release_admission import build_release_admission_decision
from .reliability_control import build_reliability_plan
from .resource_optimizer import build_resource_optimization_report
from .slo import build_slo_report
from .supply_chain import build_supply_chain_evidence
from .tenancy import build_tenancy_report
from .telemetry import generate_window
from .topology_placement import build_topology_placement_plan
from .traceability import build_trace_report


def demo(output: str | Path) -> dict:
    root = Path(output)
    reference_path = generate_window(root / "data" / "reference.csv", window="reference", drift=False, errors=False)
    current_path = generate_window(root / "data" / "current.csv", window="current", drift=True, errors=True)
    report = run_checks(read_csv(reference_path), read_csv(current_path))
    write_json(root / "reports" / "observability_report.json", report)
    incident_summary = create_incidents(root, report)
    reliability_plan = build_reliability_plan(root)
    policy_audit = audit_platform_policy(Path.cwd(), output_root=root)
    trace_report = build_trace_report(root)
    chaos_drill = run_chaos_drill(root)
    resource_optimization = build_resource_optimization_report(root)
    network_security = build_network_security_report(root)
    gitops_plan = build_gitops_plan(root)
    disaster_recovery = build_disaster_recovery_plan(root)
    governance_bundle = build_governance_bundle(root)
    slo_error_budget = build_slo_report(root)
    cloud_migration = build_cloud_migration_plan(root)
    accelerator_capacity = build_accelerator_capacity_plan(
        root,
        project="Model Observability Incident Platform",
        primary_workload="telemetry diagnostics, drift checks, and incident review probes",
    )
    device_allocation = build_device_allocation_plan(root)
    topology_placement = build_topology_placement_plan(root)
    kuberay_capacity = build_kuberay_capacity_plan(root)
    inference_gateway = build_inference_gateway_plan(root)
    tenancy = build_tenancy_report(root)
    identity_access = build_identity_access_report(root)
    performance_budget = build_performance_budget_report(root)
    queue_simulation = build_queue_simulation(root)
    dashboard = render_dashboard(
        root / "reports" / "model_observability_dashboard.html",
        report=report,
        incident_summary=incident_summary,
        reliability_plan=reliability_plan,
    )
    supply_chain = build_supply_chain_evidence(
        root,
        project="Model Observability Incident Platform",
        artifact_name="model-observability-demo-artifacts",
        workflow="Model Observability CI",
        namespace="mlops-observability",
    )
    release_admission = build_release_admission_decision(root)
    artifact_index = render_artifact_index(
        root,
        title="Model Observability Incident Platform",
        description="Reviewer landing page for generated reliability dashboard, incident evidence, SLOs, migration, and governance artifacts.",
        dashboard="model_observability_dashboard.html",
    )
    orchestration_scorecard = build_orchestration_scorecard(root, project="Model Observability Incident Platform")
    return {
        "report": report,
        "incidents": incident_summary,
        "reliability_plan": reliability_plan,
        "policy_audit": policy_audit,
        "trace_report": trace_report,
        "chaos_drill": chaos_drill,
        "resource_optimization": resource_optimization,
        "network_security": network_security,
        "gitops_plan": gitops_plan,
        "disaster_recovery": disaster_recovery,
        "governance_bundle": governance_bundle,
        "slo_error_budget": slo_error_budget,
        "cloud_migration": cloud_migration,
        "accelerator_capacity": accelerator_capacity,
        "device_allocation": device_allocation,
        "topology_placement": topology_placement,
        "kuberay_capacity": kuberay_capacity,
        "inference_gateway": inference_gateway,
        "tenancy": tenancy,
        "identity_access": identity_access,
        "performance_budget": performance_budget,
        "queue_simulation": queue_simulation,
        "release_admission": release_admission,
        "dashboard": str(dashboard),
        "artifact_index": str(artifact_index),
        "orchestration_scorecard": orchestration_scorecard,
        "supply_chain": supply_chain,
    }


def governance(output: str | Path) -> dict:
    root = Path(output)
    if not (root / "reports" / "observability_report.json").exists():
        reference_path = generate_window(root / "data" / "reference.csv", window="reference", drift=False, errors=False)
        current_path = generate_window(root / "data" / "current.csv", window="current", drift=True, errors=True)
        report = run_checks(read_csv(reference_path), read_csv(current_path))
        write_json(root / "reports" / "observability_report.json", report)
        create_incidents(root, report)
        build_reliability_plan(root)
    return build_governance_bundle(root)


def slo_report(output: str | Path) -> dict:
    root = Path(output)
    if not (root / "reports" / "reliability_control_plan.json").exists():
        governance(root)
    return build_slo_report(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Model observability and incident response platform")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in [
        "demo",
        "reliability-plan",
        "policy-audit",
        "trace-report",
        "chaos-drill",
        "optimize-resources",
        "network-security",
        "gitops-plan",
        "dr-plan",
        "governance-bundle",
        "slo-report",
        "cloud-plan",
        "supply-chain",
        "orchestration-scorecard",
        "accelerator-plan",
        "device-plan",
        "topology-plan",
        "kuberay-plan",
        "inference-gateway-plan",
        "tenancy-report",
        "identity-report",
        "performance-budget",
        "queue-simulation",
        "release-admission",
    ]:
        cmd = sub.add_parser(command)
        cmd.add_argument("--output", default=".local")
    args = parser.parse_args(argv)
    if args.command == "demo":
        print(json.dumps(demo(args.output), indent=2, sort_keys=True))
    elif args.command == "reliability-plan":
        print(json.dumps(build_reliability_plan(args.output), indent=2, sort_keys=True))
    elif args.command == "policy-audit":
        print(json.dumps(audit_platform_policy(Path.cwd(), output_root=args.output), indent=2, sort_keys=True))
    elif args.command == "trace-report":
        print(json.dumps(build_trace_report(args.output), indent=2, sort_keys=True))
    elif args.command == "chaos-drill":
        print(json.dumps(run_chaos_drill(args.output), indent=2, sort_keys=True))
    elif args.command == "optimize-resources":
        print(json.dumps(build_resource_optimization_report(args.output), indent=2, sort_keys=True))
    elif args.command == "network-security":
        print(json.dumps(build_network_security_report(args.output), indent=2, sort_keys=True))
    elif args.command == "gitops-plan":
        print(json.dumps(build_gitops_plan(args.output), indent=2, sort_keys=True))
    elif args.command == "dr-plan":
        print(json.dumps(build_disaster_recovery_plan(args.output), indent=2, sort_keys=True))
    elif args.command == "governance-bundle":
        print(json.dumps(governance(args.output), indent=2, sort_keys=True))
    elif args.command == "slo-report":
        print(json.dumps(slo_report(args.output), indent=2, sort_keys=True))
    elif args.command == "cloud-plan":
        print(json.dumps(build_cloud_migration_plan(args.output), indent=2, sort_keys=True))
    elif args.command == "supply-chain":
        print(json.dumps(build_supply_chain_evidence(args.output, project="Model Observability Incident Platform", artifact_name="model-observability-demo-artifacts", workflow="Model Observability CI", namespace="mlops-observability"), indent=2, sort_keys=True))
    elif args.command == "orchestration-scorecard":
        print(json.dumps(build_orchestration_scorecard(args.output, project="Model Observability Incident Platform"), indent=2, sort_keys=True))
    elif args.command == "accelerator-plan":
        print(json.dumps(build_accelerator_capacity_plan(args.output, project="Model Observability Incident Platform", primary_workload="telemetry diagnostics, drift checks, and incident review probes"), indent=2, sort_keys=True))
    elif args.command == "device-plan":
        print(json.dumps(build_device_allocation_plan(args.output), indent=2, sort_keys=True))
    elif args.command == "topology-plan":
        print(json.dumps(build_topology_placement_plan(args.output), indent=2, sort_keys=True))
    elif args.command == "kuberay-plan":
        print(json.dumps(build_kuberay_capacity_plan(args.output), indent=2, sort_keys=True))
    elif args.command == "inference-gateway-plan":
        print(json.dumps(build_inference_gateway_plan(args.output), indent=2, sort_keys=True))
    elif args.command == "tenancy-report":
        print(json.dumps(build_tenancy_report(args.output), indent=2, sort_keys=True))
    elif args.command == "identity-report":
        print(json.dumps(build_identity_access_report(args.output), indent=2, sort_keys=True))
    elif args.command == "performance-budget":
        print(json.dumps(build_performance_budget_report(args.output), indent=2, sort_keys=True))
    elif args.command == "queue-simulation":
        print(json.dumps(build_queue_simulation(args.output), indent=2, sort_keys=True))
    elif args.command == "release-admission":
        print(json.dumps(build_release_admission_decision(args.output), indent=2, sort_keys=True))
    return 0
