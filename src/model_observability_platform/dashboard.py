from __future__ import annotations

import html
from pathlib import Path


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value))


def badge(value: bool) -> str:
    return f'<span class="badge {"pass" if value else "fail"}">{"PASS" if value else "FAIL"}</span>'


def severity_badge(value: str) -> str:
    klass = {"critical": "critical", "high": "high", "medium": "medium"}.get(value, "low")
    return f'<span class="sev {klass}">{esc(value.upper())}</span>'


LABELS = {
    "feature_drift": "Feature drift",
    "prediction_drift": "Prediction drift",
    "latency_slo": "Latency SLO",
    "error_rate": "Error rate",
    "null_rate": "Null rate",
    "freshness": "Freshness",
}


def observed_summary(check: dict) -> object:
    if check.get("name") == "feature_drift":
        psi_scores = check.get("observed", {}).get("psi", {})
        failed = check.get("failed_features", [])
        max_psi = max(psi_scores.values(), default=0.0)
        return f"{len(failed)} features, max PSI {max_psi}"
    return check.get("observed")


def asset_chips(value: list[str]) -> str:
    if not value:
        return '<span class="chip muted">none</span>'
    return "".join(f'<span class="chip">{esc(asset.replace("_", " "))}</span>' for asset in value)


def rows(items: list[dict], columns: list[str]) -> str:
    if not items:
        return f"<tr><td colspan='{len(columns)}'>No records</td></tr>"
    rendered = []
    for item in items:
        cells = []
        for column in columns:
            value = item.get(column, "")
            if isinstance(value, str) and (value.startswith("<span class=") or value.startswith("<span class=\"sev")):
                cells.append(f"<td>{value}</td>")
            else:
                cells.append(f"<td>{esc(value)}</td>")
        rendered.append("<tr>" + "".join(cells) + "</tr>")
    return "\n".join(rendered)


def render_dashboard(output_path: str | Path, *, report: dict, incident_summary: dict, reliability_plan: dict | None = None) -> Path:
    reliability_plan = reliability_plan or {}
    reliability_action = str(reliability_plan.get("recommended_action", "not planned")).replace("_", " ")
    impacted_assets = [str(asset) for asset in reliability_plan.get("impacted_assets", [])]
    check_rows = [
        {
            "check": LABELS.get(check["name"], check["name"]),
            "status": badge(bool(check["passed"])),
            "severity": severity_badge(check.get("severity", "low")),
            "observed": observed_summary(check),
            "threshold": check.get("threshold", ""),
        }
        for check in report.get("checks", [])
    ]
    incident_rows = [
        {
            "incident": incident["incident_id"][:16],
            "check": LABELS.get(incident["check"], incident["check"]),
            "severity": severity_badge(incident["severity"]),
            "root": incident["root_cause"].replace("_", " "),
            "status": incident["status"],
        }
        for incident in incident_summary.get("incidents", [])[-10:]
    ]
    drift_rows = [
        {
            "feature": feature.replace("_", " ").title(),
            "reference": report.get("reference_means", {}).get(feature),
            "current": report.get("current_means", {}).get(feature),
        }
        for feature in report.get("reference_means", {})
    ]
    body = f"""
    <!doctype html>
    <html lang="en">
    <head>
      <title>Model Observability Incident Platform</title>
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <style>
        * {{ box-sizing: border-box; }}
        body {{ margin:0; background:#f5f7fa; color:#1c2733; font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
        header {{ background:#172026; color:white; padding:28px 36px; border-bottom:5px solid #f59e0b; }}
        main {{ max-width:1460px; margin:0 auto; padding:24px 36px 42px; }}
        h1 {{ margin:0; font-size:28px; line-height:1.2; }}
        h2 {{ margin:0 0 14px; font-size:17px; }}
        header p {{ margin:8px 0 0; color:#cbd5df; }}
        .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:14px; margin-bottom:18px; }}
        .metric,.panel {{ background:white; border:1px solid #d7dee7; border-radius:8px; box-shadow:0 1px 2px rgba(23,32,38,.04); }}
        .metric {{ min-height:112px; padding:16px; }}
        .metric span {{ display:block; color:#5b6b7d; font-size:13px; margin-bottom:10px; }}
        .metric strong {{ display:block; font-size:24px; line-height:1.2; overflow-wrap:anywhere; }}
        .metric .badge,.metric .sev {{ width:auto; max-width:max-content; }}
        .layout {{ display:grid; grid-template-columns:minmax(0,1fr) minmax(380px,.43fr); gap:16px; align-items:start; }}
        .panel {{ padding:16px; margin-top:16px; }}
        table {{ width:100%; table-layout:fixed; border-collapse:collapse; }}
        th,td {{ border-bottom:1px solid #e8edf3; padding:11px 12px; text-align:left; font-size:14px; overflow-wrap:anywhere; vertical-align:top; }}
        th {{ background:#f8fafc; color:#334155; }}
        tr:last-child td {{ border-bottom:0; }}
        .badge,.sev {{ display:inline-block; border-radius:999px; padding:4px 10px; font-size:12px; font-weight:800; }}
        .pass {{ color:#166534; background:#dcfce7; }}
        .fail {{ color:#991b1b; background:#fee2e2; }}
        .critical,.high {{ color:#991b1b; background:#fee2e2; }}
        .medium {{ color:#92400e; background:#fef3c7; }}
        .low {{ color:#166534; background:#dcfce7; }}
        .chip {{ display:inline-block; margin:0 5px 5px 0; padding:4px 8px; border-radius:999px; background:#fff7ed; color:#9a3412; font-size:12px; font-weight:800; white-space:nowrap; }}
        .chip.muted {{ background:#f1f5f9; color:#475569; }}
        .summary {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }}
        .summary div {{ border:1px solid #e3e9f0; border-radius:6px; padding:12px; min-height:74px; }}
        .summary span {{ display:block; color:#64748b; font-size:12px; margin-bottom:8px; }}
        .summary strong {{ display:block; font-size:18px; overflow-wrap:anywhere; }}
        @media (max-width:900px) {{ header {{ padding:22px 18px; }} main {{ padding:18px; }} .layout {{ grid-template-columns:1fr; }} }}
      </style>
    </head>
    <body>
      <header>
        <h1>Model Observability Incident Platform</h1>
        <p>Feature drift, prediction drift, serving SLOs, idempotent incidents, likely root cause, and response guidance.</p>
      </header>
      <main>
        <section class="grid">
          <div class="metric"><span>Global health</span><strong>{badge(report.get('passed', False))}</strong></div>
          <div class="metric"><span>Open incidents</span><strong>{esc(incident_summary.get('open_count'))}</strong></div>
          <div class="metric"><span>Top severity</span><strong>{severity_badge(incident_summary.get('severity', 'low'))}</strong></div>
          <div class="metric"><span>New incidents</span><strong>{esc(incident_summary.get('created_count'))}</strong></div>
        </section>
        <section class="layout">
          <div>
            <div class="panel">
              <h2>Health Checks</h2>
              <table><tr><th>Check</th><th>Status</th><th>Severity</th><th>Observed</th><th>Threshold</th></tr>{rows(check_rows, ['check', 'status', 'severity', 'observed', 'threshold'])}</table>
            </div>
            <div class="panel">
              <h2>Open Incidents</h2>
              <table><tr><th>Incident</th><th>Check</th><th>Severity</th><th>Root Cause</th><th>Status</th></tr>{rows(incident_rows, ['incident', 'check', 'severity', 'root', 'status'])}</table>
            </div>
          </div>
          <div>
            <div class="panel">
              <h2>Reliability Control Plane</h2>
              <div class="summary">
                <div><span>Recommended action</span><strong>{esc(reliability_action)}</strong></div>
                <div><span>Error burn rate</span><strong>{esc(reliability_plan.get('error_budget_burn_rate', 'n/a'))}</strong></div>
                <div><span>Owner</span><strong>{esc(reliability_plan.get('routing', {}).get('owner', 'n/a'))}</strong></div>
                <div><span>Impacted assets</span><strong>{asset_chips(impacted_assets)}</strong></div>
              </div>
            </div>
            <div class="panel">
              <h2>Root Cause Summary</h2>
              <div class="summary">
                <div><span>Primary root cause</span><strong>{esc(incident_summary.get('incidents', [{}])[-1].get('root_cause', 'none')).replace('_', ' ')}</strong></div>
                <div><span>Incident status</span><strong>{esc('open' if incident_summary.get('open_count', 0) else 'clear')}</strong></div>
              </div>
            </div>
            <div class="panel">
              <h2>Feature Means</h2>
              <table><tr><th>Feature</th><th>Reference</th><th>Current</th></tr>{rows(drift_rows, ['feature', 'reference', 'current'])}</table>
            </div>
          </div>
        </section>
      </main>
    </body>
    </html>
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(body, encoding="utf-8")
    return output_path
