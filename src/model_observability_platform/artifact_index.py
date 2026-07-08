from __future__ import annotations

import html
from pathlib import Path


def _escape(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _breakable(value: object) -> str:
    escaped = _escape(value)
    return escaped.replace("/", "/<wbr>").replace("_", "_<wbr>").replace("-", "-<wbr>")


def render_artifact_index(root: str | Path, *, title: str, description: str, dashboard: str) -> Path:
    root = Path(root)
    cards = [
        ("Reliability Dashboard", dashboard, "HTML incident-command view for checks, affected assets, and recommended action."),
        ("Incident Summary", "incident_summary.json", "Deduplicated incident record with severity, affected checks, and status counts."),
        ("Reliability Plan", "reliability_control_plan.json", "Root-cause and rollback guidance for high-burn or degraded serving windows."),
        ("Governance Evidence", "governance_evidence_bundle.json", "Risk register, system card, approval record, and reproducibility hashes."),
        ("SLO Error Budget", "slo_error_budget.json", "Freshness, quality, latency, and alerting SLO burn-rate evidence."),
        ("Supply Chain Evidence", "supply_chain_evidence.json", "Artifact hashes, GitHub attestations, SLSA provenance, and Sigstore policy controls."),
        ("Cloud Migration Plan", "cloud_migration_plan.json", "Managed cloud observability migration notes for Kubernetes and data platforms."),
        ("Accelerator Plan", "accelerator_capacity_plan.json", "GPU, DRA, Kueue, MIG, and time-slicing plan for monitor workloads."),
        ("Device Allocation", "device_allocation_plan.json", "DRA ResourceClaim templates, Kueue coupling, diagnostic fallbacks, and incident-path guardrails."),
        ("Topology Placement", "topology_placement_plan.json", "Kueue TAS, collector spread, optional GPU diagnostic locality, and incident fallbacks."),
        ("KubeRay Capacity", "kuberay_capacity_plan.json", "Incident fanout RayJobs, Kueue priority queues, optional GPU diagnostics, and rollout-freeze fallback."),
        ("Inference Gateway", "inference_gateway_plan.json", "Observed InferencePools, endpoint picker incident signals, objective priorities, and canary-freeze fallbacks."),
        ("Semantic Telemetry", "semantic_telemetry_plan.json", "OTel, Kubernetes, GenAI-style, SLO, and incident attributes with payload redaction rules."),
        ("Deadline Alerts", "deadline_alert_plan.json", "Airflow 3 telemetry freshness, incident creation, root-cause, and dashboard publish deadline policies."),
        ("Cost Observability", "cost_observability_report.json", "OpenCost incident-path budgets, telemetry retention cost, GPU diagnostics spend, and allocation labels."),
        ("Elastic Workloads", "elastic_workload_plan.json", "Kueue Workload Slices, JobSet incident fanout, drift-backlog replacement, GPU diagnostics, and rollout-freeze capacity recovery."),
        ("Indexed Job Resilience", "indexed_job_resilience_plan.json", "Kubernetes Indexed Jobs, per-index retries, success policy, pod failure policy, and bounded Airflow incident backfills."),
        ("Performance Budget", "performance_budget.json", "Detection latency, incident creation, coverage, routing, and dashboard gates."),
        ("Queue Simulation", "queue_simulation.json", "Kueue quota, incident priority, GPU diagnostics, Airflow pool, and preemption simulation."),
        ("Release Admission", "release_admission_decision.json", "Fail-closed rollout freeze record combining incidents, SLOs, queues, governance, and provenance."),
        ("Tenant Fairness", "tenancy_fairness_report.json", "Incident, drift, and retention tenant quotas with Kueue cohorts and cost labels."),
        ("Workload Identity", "identity_access_report.json", "Keyless identities for telemetry collection, drift evaluation, incident routing, and alerting."),
        ("Resource Optimization", "resource_optimization.json", "Requests, limits, HPA, VPA, KEDA, and capacity guidance for reliability checks."),
        ("Network Security", "network_security.json", "mTLS, network policy, and telemetry-to-incident access topology for the platform."),
        ("Chaos Drill", "chaos_drill_report.json", "Observability failure-injection scenarios with blast radius and recovery objectives."),
        ("GitOps Plan", "gitops_plan.json", "Promotion waves, incident gates, rollback commands, and GitOps-controlled reliability rollout."),
        ("Orchestration Scorecard", "orchestration_scorecard.json", "Automated scan of advanced Airflow, Kubernetes, lineage, and security controls."),
    ]
    card_html = "\n".join(
        f"""
        <a class="card" href="{_escape(href)}">
          <span class="label">{_escape(label)}</span>
          <strong>{_breakable(href)}</strong>
          <small>{_escape(summary)}</small>
        </a>"""
        for label, href, summary in cards
    )
    body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_escape(title)} Evidence Index</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f8fb;
      --panel: #ffffff;
      --ink: #1a2230;
      --muted: #5d6675;
      --line: #dce2ec;
      --accent: #8a2831;
      --accent-soft: #fae8ea;
      --shadow: 0 18px 45px rgba(38, 45, 62, 0.10);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--ink);
      line-height: 1.55;
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 48px 24px 56px; }}
    header {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 28px;
      align-items: end;
      padding-bottom: 28px;
      border-bottom: 1px solid var(--line);
    }}
    h1 {{ margin: 0 0 10px; font-size: clamp(2rem, 4vw, 4rem); line-height: 1; letter-spacing: 0; }}
    p {{ margin: 0; color: var(--muted); max-width: 760px; }}
    .badge {{
      display: inline-flex;
      align-items: center;
      min-height: 36px;
      padding: 0 14px;
      border: 1px solid #e2a7ad;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 0.82rem;
      font-weight: 800;
      text-transform: uppercase;
    }}
    .grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin-top: 28px; }}
    .card {{
      display: flex;
      min-height: 178px;
      flex-direction: column;
      justify-content: space-between;
      gap: 18px;
      padding: 22px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: var(--shadow);
      color: inherit;
      text-decoration: none;
    }}
    .card:hover {{ border-color: #cf7580; transform: translateY(-1px); }}
    .label {{ color: var(--accent); font-size: 0.78rem; font-weight: 800; text-transform: uppercase; }}
    strong {{ font-size: 0.96rem; line-height: 1.3; overflow-wrap: break-word; }}
    small {{ color: var(--muted); font-size: 0.9rem; }}
    footer {{ margin-top: 28px; color: var(--muted); font-size: 0.9rem; }}
    @media (max-width: 880px) {{
      header {{ grid-template-columns: 1fr; }}
      .grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>{_escape(title)}</h1>
        <p>{_escape(description)}</p>
      </div>
      <span class="badge">Demo Evidence</span>
    </header>
    <section class="grid" aria-label="Generated artifacts">
      {card_html}
    </section>
    <footer>Generated by the local demo command. Open the dashboard first, then inspect the JSON evidence behind incident and reliability decisions.</footer>
  </main>
</body>
</html>
"""
    output = root / "reports" / "index.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(body, encoding="utf-8")
    return output
