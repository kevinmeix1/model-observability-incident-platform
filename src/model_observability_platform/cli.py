from __future__ import annotations

import argparse
import json
from pathlib import Path

from .checks import run_checks
from .dashboard import render_dashboard
from .incidents import create_incidents
from .io import read_csv, write_json
from .reliability_control import build_reliability_plan
from .telemetry import generate_window


def demo(output: str | Path) -> dict:
    root = Path(output)
    reference_path = generate_window(root / "data" / "reference.csv", window="reference", drift=False, errors=False)
    current_path = generate_window(root / "data" / "current.csv", window="current", drift=True, errors=True)
    report = run_checks(read_csv(reference_path), read_csv(current_path))
    write_json(root / "reports" / "observability_report.json", report)
    incident_summary = create_incidents(root, report)
    reliability_plan = build_reliability_plan(root)
    dashboard = render_dashboard(
        root / "reports" / "model_observability_dashboard.html",
        report=report,
        incident_summary=incident_summary,
        reliability_plan=reliability_plan,
    )
    return {"report": report, "incidents": incident_summary, "reliability_plan": reliability_plan, "dashboard": str(dashboard)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Model observability and incident response platform")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ["demo", "reliability-plan"]:
        cmd = sub.add_parser(command)
        cmd.add_argument("--output", default=".local")
    args = parser.parse_args(argv)
    if args.command == "demo":
        print(json.dumps(demo(args.output), indent=2, sort_keys=True))
    elif args.command == "reliability-plan":
        print(json.dumps(build_reliability_plan(args.output), indent=2, sort_keys=True))
    return 0
