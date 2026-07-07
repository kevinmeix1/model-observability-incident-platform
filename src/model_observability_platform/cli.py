from __future__ import annotations

import argparse
import json
from pathlib import Path

from .artifact_index import render_artifact_index
from .chaos import run_chaos_drill
from .checks import run_checks
from .cloud_migration import build_cloud_migration_plan
from .dashboard import render_dashboard
from .disaster_recovery import build_disaster_recovery_plan
from .gitops_release import build_gitops_plan
from .governance import build_governance_bundle
from .incidents import create_incidents
from .io import read_csv, write_json
from .network_security import build_network_security_report
from .policy_audit import audit_platform_policy
from .reliability_control import build_reliability_plan
from .resource_optimizer import build_resource_optimization_report
from .slo import build_slo_report
from .supply_chain import build_supply_chain_evidence
from .telemetry import generate_window
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
    dashboard = render_dashboard(
        root / "reports" / "model_observability_dashboard.html",
        report=report,
        incident_summary=incident_summary,
        reliability_plan=reliability_plan,
    )
    artifact_index = render_artifact_index(
        root,
        title="Model Observability Incident Platform",
        description="Reviewer landing page for generated reliability dashboard, incident evidence, SLOs, migration, and governance artifacts.",
        dashboard="model_observability_dashboard.html",
    )
    supply_chain = build_supply_chain_evidence(
        root,
        project="Model Observability Incident Platform",
        artifact_name="model-observability-demo-artifacts",
        workflow="Model Observability CI",
        namespace="mlops-observability",
    )
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
        "dashboard": str(dashboard),
        "artifact_index": str(artifact_index),
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
    return 0
